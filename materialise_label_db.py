#!/usr/bin/env python3

# given a label_db create a single channel image corresponding to each image.

import argparse
import os
import sys
import bnn_util

from label_db import LabelDB

# TODO: make this multiprocess, too slow as is...

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--label-db', type=str, help='label_db to materialise bitmaps from')
parser.add_argument('--directory', type=str, help='directory to store bitmaps')
parser.add_argument('--width', type=int, default=768, help='input image width')
parser.add_argument('--height', type=int, default=1024, help='input image height')
parser.add_argument('--label-rescale', type=float, default=0.5,
                    help='relative scale of label bitmap compared to input image')
opts = parser.parse_args()

label_db = LabelDB(label_db_file=opts.label_db)

if not os.path.exists(opts.directory):
    os.makedirs(opts.directory)

filenames = list(label_db.imgs())
for i, filename in enumerate(filenames):
    print(filename)
    # TODO transform path to canonical version relative to "Paul" or whatever
    # TODO add it to base path
    # TODO get height and width from image

    bitmap = bnn_util.xys_to_bitmap(xys=label_db.get_bugs(filename),
                                    height=opts.height,
                                    width=opts.width,
                                    rescale=opts.label_rescale)
    single_channel_img = bnn_util.bitmap_to_single_channel_pil_image(bitmap)
    single_channel_img.save("%s/%s" % (opts.directory, filename.replace(".jpg", ".png")))
    sys.stdout.write("%d/%d   \r" % (i, len(filenames)))
