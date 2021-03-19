from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


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
