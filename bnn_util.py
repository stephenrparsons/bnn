import io
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import tensorflow as tf
import yaml


# Example input and output:
# /Users/Paullaptop/Desktop/DATA/ DATA 2018/04/60D/ HR 48/IMG_1763.png
# 202012 Paul/training/DATA - Aggregation 2018/04 - 180404 CIN-11/60D/ HR 48/IMG_1763.png
def get_path_relative_to_drive(filepath):
    filepath = Path(filepath)
    if '/Users/Paullaptop/Desktop/DATA' in str(filepath):
        filepath = filepath.relative_to('/Users/Paullaptop/Desktop/DATA')
        filepath = Path(str(filepath).replace(' DATA 2018', 'DATA - Aggregation 2018'))
        filepath = Path(str(filepath).replace('/04/', '/04 - 180404 CIN-11/'))
        filepath = 'training' / filepath
    return str(filepath)


def xys_to_bitmap(xys, height, width, rescale=1.0):
    # Note: include trailing 1 dim to easier match model output
    bitmap = np.zeros((int(height * rescale), int(width * rescale), 1), dtype=np.float32)
    for x, y in xys:
        try:
            bitmap[int(y * rescale), int(x * rescale), 0] = 1.0  # recall images are (height, width)
        except IndexError as e:
            print('IndexError: are --height and --width correct?')
            raise e
    return bitmap


def bitmap_to_single_channel_pil_image(bitmap):
    h, w, c = bitmap.shape
    assert c == 1
    bitmap = np.uint8(bitmap[:, :, 0] * 255)
    return Image.fromarray(bitmap, mode='L')  # L => (8-bit pixels, black and white)


def bitmap_to_pil_image(bitmap):
    assert bitmap.dtype == np.float32
    h, w, c = bitmap.shape
    assert c == 1
    rgb_array = np.zeros((h, w, 3), dtype=np.uint8)
    single_channel = bitmap[:, :, 0] * 255
    rgb_array[:, :, 0] = single_channel
    rgb_array[:, :, 1] = single_channel
    rgb_array[:, :, 2] = single_channel
    return Image.fromarray(rgb_array)


def zero_centered_array_to_pil_image(orig_array):
    assert orig_array.dtype == np.float32
    h, w, c = orig_array.shape
    assert c == 3
    array = orig_array + 1  # 0.0 -> 2.0
    array *= 127.5  # 0.0 -> 255.0
    array = array.copy().astype(np.uint8)
    assert np.min(array) >= 0
    assert np.max(array) <= 255
    return Image.fromarray(array)


def side_by_side(rgb, bitmap):
    h, w, _ = rgb.shape
    canvas = Image.new('RGB', (w * 2, h), (50, 50, 50))
    # paste RGB on left hand side
    lhs = zero_centered_array_to_pil_image(rgb)
    canvas.paste(lhs, (0, 0))
    # paste bitmap version of labels on right hand side
    # black with white dots at labels
    rhs = bitmap_to_pil_image(bitmap)
    rhs = rhs.resize((w, h))
    canvas.paste(rhs, (w, 0))
    # draw on a blue border (and blue middle divider) to make it
    # easier to see relative positions.
    draw = ImageDraw.Draw(canvas)
    draw.polygon([0, 0, w * 2 - 1, 0, w * 2 - 1, h - 1, 0, h - 1], outline='blue')
    draw.line([w, 0, w, h], fill='blue')
    canvas = canvas.resize((w, h // 2))
    return canvas


def latest_checkpoint_in_dir(ckpt_dir):
    checkpoint_info = yaml.load(open("%s/checkpoint" % ckpt_dir).read())
    return checkpoint_info['model_checkpoint_path']


def explicit_summaries(tag_values):
    values = [tf.compat.v1.Summary.value(tag=tag, simple_value=value) for tag, value in tag_values.items()]
    return tf.compat.v1.Summary.value(value=values)


# def pil_image_to_tf_summary(img, tag="debug_img"):
#     # serialise png bytes
#     sio = io.BytesIO()
#     img.save(sio, format="png")
#     png_bytes = sio.getvalue()
#
#     # https://github.com/tensorflow/tensorflow/blob/master/tensorflow/core/framework/summary.proto
#     return tf.Summary(
#         value=[tf.Summary.Value(
#             tag=tag,
#             image=tf.Summary.Image(
#                 height=img.size[0],
#                 width=img.size[1],
#                 colorspace=3,  # RGB
#                 encoded_image_string=png_bytes
#             )
#         )]
#     )


def hms(secs):
    if secs < 0:
        return "<0"  # clumsy
    secs = int(secs)
    mins, secs = divmod(secs, 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
        return "%d:%02d:%02d" % (hrs, mins, secs)
    elif mins > 0:
        return "%02d:%02d" % (mins, secs)
    else:
        return "%02d" % secs


class SetComparison(object):
    def __init__(self):
        self.true_positive_count = 0
        self.false_negative_count = 0
        self.false_positive_count = 0

    def compare_sets(self, true_pts, predicted_pts, threshold=10.0):
        # compare two sets of true & predicted centroids and calculate TP, FP and FN rate.

        # iteratively find closest point in each set and if they are close enough (according
        # to threshold) declare them them a match (i.e. true positive). once the closest
        # match is above the threshold, or we run out of points to match, stop comparing.
        # whatever remains in true_pts & predicted_pts after matching is done are false
        # negatives & positives respectively.
        tp = 0
        while len(true_pts) > 0 and len(predicted_pts) > 0:
            # find indexes of closest pair
            closest_pair = None
            closest_sqr_distance = None
            for t_i, t in enumerate(true_pts):
                for p_i, p in enumerate(predicted_pts):
                    sqr_distance = (t[0] - p[0]) ** 2 + (t[1] - p[1]) ** 2
                    if closest_sqr_distance is None or sqr_distance < closest_sqr_distance:
                        closest_pair = t_i, p_i
                        closest_sqr_distance = sqr_distance
            # if closest pair is above threshold so comparing
            closest_distance = math.sqrt(closest_sqr_distance)
            if closest_distance > threshold:
                break
            # otherwise delete closest pair & declare them a match
            t_i, p_i = closest_pair
            del true_pts[t_i]
            del predicted_pts[p_i]
            tp += 1

        # remaining unmatched entries are false positives & negatives.
        fn = len(true_pts)
        fp = len(predicted_pts)

        # aggregate
        self.true_positive_count += tp
        self.false_negative_count += fn
        self.false_positive_count += fp

        # return for just this comparison
        return tp, fn, fp

    def precision_recall_f1(self):
        try:
            precision = self.true_positive_count / (self.true_positive_count + self.false_positive_count)
            recall = self.true_positive_count / (self.true_positive_count + self.false_negative_count)
            f1 = 2 * (precision * recall) / (precision + recall)
            return precision, recall, f1
        except ZeroDivisionError:
            return 0, 0, 0
