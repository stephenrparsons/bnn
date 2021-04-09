from PIL import Image, ImageDraw
import math
import numpy as np


def debug_img(img, bitmap, logistic_output):
    # create a debug image with three columns; 1) original RGB. 2) black/white
    # bitmap of labels 3) black/white bitmap of predictions (with centroids coloured
    # red.
    h, w, _channels = bitmap.shape
    canvas = Image.new('RGB', (w * 3, h), (50, 50, 50))
    # original input image on left
    img = zero_centered_array_to_pil_image(img)
    img = img.resize((w, h))
    canvas.paste(img, (0, 0))
    # label bitmap in center
    canvas.paste(bitmap_to_pil_image(bitmap), (w, 0))
    # logistic output on right
    canvas.paste(bitmap_to_pil_image(logistic_output), (w * 2, 0))
    # draw red dots on right hand side image corresponding to
    # final thresholded prediction
    draw = ImageDraw.Draw(canvas)
    for y, x in centroids_of_connected_components(logistic_output):
        draw.rectangle((w * 2 + x, y, w * 2 + x, y), fill='red')
    # finally draw blue lines between the three to delimit boundaries
    draw.line([w, 0, w, h], fill='blue')
    draw.line([2 * w, 0, 2 * w, h], fill='blue')
    draw.line([3 * w, 0, 3 * w, h], fill='blue')
    # done
    return canvas


# def dice_loss(y, y_hat, batch_size, smoothing=0):
#  y = tf.reshape(y, (batch_size, -1))
#  y_hat = tf.reshape(y_hat, (batch_size, -1))
#  intersection = y * y_hat
#  intersection_rs = tf.reduce_sum(intersection, axis=1)
#  nom = intersection_rs + smoothing
#  denom = tf.reduce_sum(y, axis=1) + tf.reduce_sum(y_hat, axis=1) + smoothing
#  score = 2.0 * (nom / denom)
#  loss = 1.0 - score
#  loss = tf.Print(loss, [intersection, intersection_rs, nom, denom], first_n=100, summarize=10000)
#  return loss


def bitmap_from_centroids(centroids, h, w):
    bitmap = np.zeros((h, w, 1))
    for cx, cy in centroids:
        bitmap[cx, cy] = 1.0
    return bitmap


def check_images(fnames):
    prev_width, prev_height = 0, 0
    for i, fname in enumerate(fnames):
        try:
            im = Image.open(fname)
        except IOError as e:
            print("Image is corrupted or does not exist:", fname)
            raise e
        width, height = im.size
        if i == 0:
            prev_width = width
            prev_height = height
        elif not prev_width == width or not prev_height == height:
            print("Image size does not match others:", fname, "wh:", width, height)
            exit()
    return width, height
