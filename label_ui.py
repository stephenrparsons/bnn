import argparse
import tkinter as tk
import os
import platform
import random
import re
import sqlite3

from PIL import Image, ImageTk, ImageDraw

from label_db import LabelDB


class LabelUI():
  def __init__(self, label_db_filename, img_dir, width, height, sort=True):

    # what images to review?
    # note: drop trailing / in dir name (if present)
    self.img_dir = re.sub("/$", "", img_dir)
    self.files = os.listdir(img_dir)
    if sort:
      self.files = sorted(self.files)
    else:
      random.shuffle(self.files)
    print("%d files to review" % len(self.files))

    # label db
    self.label_db = LabelDB(label_db_filename)
    self.label_db.create_if_required()

    # TK UI
    root = tk.Tk()
    root.lift()
    root.title(label_db_filename)

    # Bind buttons
    root.bind('<Right>', self.display_next_image)
    root.bind('<Left>', self.display_previous_image)
    root.bind('<Up>', self.toggle_bugs)
    root.bind('n', self.display_next_unlabelled_image)
    root.bind('N', self.display_next_unlabelled_image)
    root.bind('q', self.quit)
    root.bind('Q', self.quit)

    # Set up canvas
    self.canvas = tk.Canvas(root, cursor='tcross')
    self.canvas.config(width=width, height=height)
    self.canvas.bind('<Button-1>', self.add_bug_event)  # left mouse button
    self.canvas.bind('<Button-2>', self.remove_closest_bug_event)  # right mouse button on macbook, evidently
    self.canvas.bind('<Button-3>', self.remove_closest_bug_event)  # right mouse button
    self.canvas.pack()

    # A lookup table from bug x,y to any rectangles that have been drawn
    # in case we want to remove one. the keys of this dict represent all
    # the bug x,y in current image.
    self.x_y_to_boxes = {}  # { (x, y): canvas_id, ... }

    # a flag to denote if bugs are being displayed or not
    # while no displayed we lock down all img navigation
    self.bugs_on = True

    # Main review loop
    self.file_idx = 0
    self.display_new_image()

    # Kind of ridiculous but OK! To make the window show in front of others
    # From here: https://fyngyrz.com/?p=898&cpage=1
    if platform.system() == 'Darwin':  # Only do this on Mac
        os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "Python" to true' ''')

    root.mainloop()

  def quit(self, e):
        exit()

  def add_bug_event(self, e):
    if not self.bugs_on:
      print("ignore add bug; bugs not on")
      return
    self.add_bug_at(e.x, e.y)

  def add_bug_at(self, x, y):
    rectangle_id = self.canvas.create_rectangle(x-2,y-2,x+2,y+2, fill='red')
    self.x_y_to_boxes[(x, y)] = rectangle_id

  def remove_bug(self, rectangle_id):
    self.canvas.delete(rectangle_id)

  def toggle_bugs(self, e):
    if self.bugs_on:
      # store x,y s in tmp list and delete all rectangles from canvas
      self.tmp_x_y = []
      for (x, y), rectangle_id in self.x_y_to_boxes.items():
        self.remove_bug(rectangle_id)
        self.tmp_x_y.append((x, y))
      self.x_y_to_boxes = {}
      self.bugs_on = False
    else:  # bugs not on
      # restore all temp stored bugs
      for x, y in self.tmp_x_y:
        self.add_bug_at(x, y)
      self.bugs_on = True

  def remove_closest_bug_event(self, e):
    if not self.bugs_on:
      print("ignore remove bug; bugs not on")
      return
    if len(self.x_y_to_boxes) == 0: return
    closest_point = None
    closest_sqr_distance = 0.0
    for x, y in self.x_y_to_boxes.keys():
      sqr_distance = (e.x-x)**2 + (e.y-y)**2
      if sqr_distance < closest_sqr_distance or closest_point is None:
        closest_point = (x, y)
        closest_sqr_distance = sqr_distance
    self.remove_bug(self.x_y_to_boxes.pop(closest_point))

  def display_next_image(self, e=None):
    if not self.bugs_on:
      print("ignore move to next image; bugs not on")
      return
    self._flush_pending_x_y_to_boxes()
    self.file_idx += 1
    if self.file_idx == len(self.files):
      print("Can't move to image past last image.")
      self.file_idx = len(self.files) - 1
    self.display_new_image()

  def display_next_unlabelled_image(self, e=None):
    self._flush_pending_x_y_to_boxes()
    while True:
      self.file_idx += 1
      if self.file_idx == len(self.files):
        print("Can't move to image past last image.")
        self.file_idx = len(self.files) - 1
        break
      if not self.label_db.has_labels(self.files[self.file_idx]):
        break
    self.display_new_image()

  def display_previous_image(self, e=None):
    if not self.bugs_on:
      print("ignore move to previous image; bugs not on")
      return
    self._flush_pending_x_y_to_boxes()
    self.file_idx -= 1
    if self.file_idx < 0:
      print("Can't move to image previous to first image.")
      self.file_idx = 0
    self.display_new_image()

  def _flush_pending_x_y_to_boxes(self):
    # Flush existing points.
    img_name = self.files[self.file_idx]
    self.label_db.set_labels(img_name, self.x_y_to_boxes.keys())
    self.x_y_to_boxes.clear()

  def display_new_image(self):
    # Get current canvas size
    self.canvas.update()  # https://stackoverflow.com/a/49216638
    canvas_width = self.canvas.winfo_width()
    canvas_height = self.canvas.winfo_height()

    # Open image
    img_name = self.files[self.file_idx]
    img = Image.open(os.path.join(self.img_dir, img_name))

    # Resize image: https://stackoverflow.com/a/273962
    img.thumbnail((canvas_width, canvas_height), Image.ANTIALIAS)

    # Draw image title
    draw = ImageDraw.Draw(img)
    title = f'{img_name} {self.file_idx + 1} of {len(self.files)}'
    draw.text((10, 10), title, fill='black')

    # Draw image on screen
    self.tk_img = ImageTk.PhotoImage(img)
    self.canvas.create_image(0, 0, image=self.tk_img, anchor=tk.NW)

    # Look up any existing bugs in DB for this image and add them
    existing_labels = self.label_db.get_labels(img_name)
    for x, y in existing_labels:
      self.add_bug_at(x, y)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image-dir', type=str, required=True)
    parser.add_argument('--label-db', type=str, required=True)
    parser.add_argument('--width', type=int, default=768, help='starting window width')
    parser.add_argument('--height', type=int, default=1024, help='starting window height')
    parser.add_argument('--no-sort', action='store_true')
    args = parser.parse_args()

    print("RIGHT\tnext image")
    print("LEFT\tprevious image")
    print("UP\ttoggle labels")
    print("N\tnext image with 0 labels")
    print("Q\tquit")

    LabelUI(args.label_db, args.image_dir, args.width, args.height, sort=not args.no_sort)


if __name__ == '__main__':
    main()
