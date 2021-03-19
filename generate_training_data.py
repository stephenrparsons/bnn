#!/usr/bin/env python3

import os

import tensorflow as tf
import tensorflow_addons as tfa

import bnn_util


def img_xys_iterator(image_dir, label_dir, batch_size, patch_width_height, distort_rgb,
                     flip_left_right, random_rotation, repeat, label_rescale=0.5):
    # return dataset of (image, xys_bitmap) for training

    # materialise list of rgb filenames and corresponding numpy bitmaps
    rgb_filenames = []  # (H, W, 3) pngs
    bitmap_filenames = []  # (H/2, W/2, 1) pngs
    for fname in os.listdir(image_dir):
        rgb_filename = os.path.join(image_dir, fname)
        bitmap_filename = os.path.join(label_dir, os.path.splitext(fname)[0] + '_train_bitmap_bugs.png')
        if not os.path.isfile(bitmap_filename):
            raise Exception(
                "label bitmap img [%s] doesn't exist for training example [%s]. did you run materialise_label_db.py?"
                % (bitmap_filename, rgb_filename))
        rgb_filenames.append(rgb_filename)
        bitmap_filenames.append(bitmap_filename)

    def decode_images(rgb_f, bitmap_f):
        rgb = tf.image.decode_image(tf.io.read_file(rgb_f))
        rgb = tf.cast(rgb, tf.float32)
        rgb = (rgb / 127.5) - 1.0  # -1.0 -> 1.0
        bitmap = tf.image.decode_image(tf.io.read_file(bitmap_f))
        bitmap = tf.cast(bitmap, tf.float32)
        bitmap /= 256  # 0 -> 1
        return rgb, bitmap

    def random_crop(rgb, bitmap):
        # we want to use the same crop for both RGB input and bitmap labels
        if patch_width_height is not None:
            patch_width = patch_height = patch_width_height
            height, width = tf.shape(rgb)[0], tf.shape(rgb)[1]
            offset_height = tf.random.uniform([], 0, height - patch_height, dtype=tf.int32)
            offset_width = tf.random.uniform([], 0, width - patch_width, dtype=tf.int32)
            rgb = tf.image.crop_to_bounding_box(rgb, offset_height, offset_width, patch_height, patch_width)
            rgb = tf.reshape(rgb, (patch_height, patch_width, 3))
            # TODO: remove this cast uglyness :/
            bitmap = tf.image.crop_to_bounding_box(
                bitmap,
                tf.cast(tf.cast(offset_height, tf.float32) * label_rescale, tf.int32),
                tf.cast(tf.cast(offset_width, tf.float32) * label_rescale, tf.int32),
                int(patch_height * label_rescale), int(patch_width * label_rescale)
            )
            bitmap = tf.reshape(bitmap, (int(patch_height * label_rescale), int(patch_width * label_rescale), 1))
        return rgb, bitmap

    def augment(rgb, bitmap):
        if flip_left_right:
            random = tf.random.uniform([], 0, 1, dtype=tf.float32)
            rgb, bitmap = tf.cond(random < 0.5,
                                  lambda: (rgb, bitmap),
                                  lambda: (tf.image.flip_left_right(rgb),
                                           tf.image.flip_left_right(bitmap)))
        if distort_rgb:
            rgb = tf.image.random_brightness(rgb, 0.1)
            rgb = tf.image.random_contrast(rgb, 0.9, 1.1)
            #    rgb = tf.image.per_image_standardization(rgb)  # works great, but how to have it done for predict?
            rgb = tf.clip_by_value(rgb, clip_value_min=-1.0, clip_value_max=1.0)

        if random_rotation:
            # we want to use the same crop for both RGB input and bitmap labels
            random_rotation_angle = tf.random.uniform([], -0.4, 0.4, dtype=tf.float32)
            rgb, bitmap = (tfa.image.rotate(rgb, random_rotation_angle),
                           tfa.image.rotate(bitmap, random_rotation_angle))

        return rgb, bitmap

    dataset = tf.data.Dataset.from_tensor_slices((tf.constant(rgb_filenames),
                                                  tf.constant(bitmap_filenames)))

    dataset = dataset.map(decode_images, num_parallel_calls=8)

    if repeat:
        if len(rgb_filenames) < 1000:
            dataset = dataset.cache()
        print("len(rgb_filenames)", len(rgb_filenames), ("CACHE" if len(rgb_filenames) < 1000 else "NO CACHE"))
        dataset = dataset.shuffle(1000).repeat()

    dataset = dataset.map(random_crop, num_parallel_calls=8)

    if flip_left_right or distort_rgb or random_rotation:
        dataset = dataset.map(augment, num_parallel_calls=8)

    # NOTE: keras.fit wants the iterator directly (not .get_next())
    return dataset.batch(batch_size).prefetch(tf.data.experimental.AUTOTUNE)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--image-dir', type=str, required=True,
                        help='location of RGB input images')
    parser.add_argument('--label-dir', type=str, required=True,
                        help='location of corresponding label files. (note: we assume for'
                             'each image-dir image there is a label-dir image)')
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--patch-width-height', type=int, default=256,
                        help="what size square patches to sample. None => no patch, i.e. use full res image"
                             " (in which case --width & --height are required)")
    parser.add_argument('--label-rescale', type=float, default=0.5,
                        help='relative scale of label bitmap compared to input image')
    parser.add_argument('--distort', action='store_true')
    parser.add_argument('--rotate', action='store_true')
    opts = parser.parse_args()

    imgs_xyss = img_xys_iterator(
        image_dir=opts.image_dir,
        label_dir=opts.label_dir,
        batch_size=opts.batch_size,
        patch_width_height=opts.patch_width_height,
        distort_rgb=opts.distort,
        flip_left_right=opts.distort,
        random_rotation=opts.rotate,
        repeat=True,
        label_rescale=opts.label_rescale
    )

    for b, (img_batch, xys_batch) in enumerate(imgs_xyss.take(16)):
        for i, (img, xys) in enumerate(zip(img_batch, xys_batch)):
            if tf.math.count_nonzero(xys) > 0:
                filename = "test_%03d_%03d.png" % (b, i)
                print("batch", b, "element", i, "filename", filename)
                bnn_util.side_by_side(rgb=img.numpy(), bitmap=xys.numpy()).save(filename)
