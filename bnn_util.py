import numpy as np
from PIL import Image

# /Users/Paullaptop/Desktop/DATA/ DATA 2018/04/60D/ HR 48/IMG_1763.png
# 202012 Paul/training/DATA - Aggregation 2018/04 - 180404 CIN-11/60D/ HR 48/IMG_1763.png
def get_drive_path(filename):
    pass


def xys_to_bitmap(xys, height, width, rescale=1.0):
    # Note: include trailing 1 dim to easier match model output
    bitmap = np.zeros((int(height * rescale), int(width * rescale), 1), dtype=np.float32)
    for x, y in xys:
        try:
            bitmap[int(y * rescale), int(x * rescale), 0] = 1.0  # recall images are (height, width)
        except IndexError as e:
            print("IndexError: are --height and --width correct?")
            raise e
    return bitmap


def bitmap_to_single_channel_pil_image(bitmap):
    h, w, c = bitmap.shape
    assert c == 1
    bitmap = np.uint8(bitmap[:, :, 0] * 255)
    return Image.fromarray(bitmap, mode='L')  # L => (8-bit pixels, black and white)
