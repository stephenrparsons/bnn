#!/usr/bin/env python3

# given a label_db create a single channel image corresponding to each image.

import argparse
import os

from PIL import Image

import bnn_util
from label_db import LabelDB

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--label-db', type=str, help='label_db to materialise bitmaps from', required=True)
parser.add_argument('--image-output-dir', type=str, help='where to dump the rgb images', required=True)
parser.add_argument('--label-output-dir', type=str, help='where to dump the label images', required=True)
parser.add_argument('--label-rescale', type=float, default=0.5,
                    help='relative scale of label bitmap compared to input image')
opts = parser.parse_args()

os.makedirs(opts.image_output_dir, exist_ok=True)
os.makedirs(opts.label_output_dir, exist_ok=True)
label_db = LabelDB(label_db_file=opts.label_db)

filenames = list(label_db.imgs())
for filename in filenames:
    original_filename = filename
    filename = bnn_util.get_path_relative_to_drive(filename)
    drive_base_path = os.path.expanduser('~/data/srpa226-drive/Sharing/202012 Paul/')
    filename = os.path.join(drive_base_path, filename)
    if not os.path.exists(filename):
        print(f'File not found, skipping: {filename}')
    else:
        img = Image.open(filename)
        width, height = img.size
        if not label_db.get_complete(original_filename):
            print(f'Image labeling not complete, skipping: {filename}')
        else:
            bitmap = bnn_util.xys_to_bitmap(xys=label_db.get_bugs(original_filename),
                                            height=height, width=width,
                                            rescale=opts.label_rescale)
            single_channel_img = bnn_util.bitmap_to_single_channel_pil_image(bitmap)
            print(f'Processing {filename}')
            img_new_filename = os.path.join(opts.image_output_dir, os.path.basename(filename))
            bitmap_filename = os.path.basename(os.path.splitext(filename)[0] + '_train_bitmap_bugs.png')
            bitmap_filename = os.path.join(opts.label_output_dir, bitmap_filename)
            img.save(img_new_filename)
            single_channel_img.save(bitmap_filename)
