from pathlib import Path

import numpy as np
from PIL import Image


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
