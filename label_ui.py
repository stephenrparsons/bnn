import argparse
import math
import os
import re
import sys

from PIL import Image
from PIL.ImageQt import ImageQt
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QPoint
from PyQt5.QtGui import QImage, QPixmap, QPainterPath, QPen, QBrush
from PyQt5.QtWidgets import QApplication, QGraphicsView, QGraphicsScene
import rawpy

from label_db import LabelDB


class LabelUI(QGraphicsView):
    """PyQt image viewer adapted from
    https://github.com/marcel-goldschen-ohm/PyQtImageViewer/blob/master/QtImageViewer.py

    Mouse interaction:
        - Left mouse button drag: Pan image.
        - Right mouse button drag: Zoom box.
        - Right mouse button double click: Zoom to show entire image.
    """

    # Create signals for mouse events.
    # Note that mouse button signals emit (x, y) coordinates
    # but image matrices are indexed (y, x).
    leftMouseButtonPressed = pyqtSignal(float, float)
    rightMouseButtonPressed = pyqtSignal(float, float)
    leftMouseButtonReleased = pyqtSignal(float, float)
    rightMouseButtonReleased = pyqtSignal(float, float)
    leftMouseButtonDoubleClicked = pyqtSignal(float, float)
    rightMouseButtonDoubleClicked = pyqtSignal(float, float)

    def __init__(self, label_db_filename, img_dir):
        QGraphicsView.__init__(self)
        self.setWindowTitle(label_db_filename)

        # what images to review?
        # note: drop trailing / in dir name (if present)
        self.img_dir = re.sub('/$', '', img_dir)
        self.files = os.listdir(img_dir)
        self.files = sorted(self.files)

        # label db
        self.label_db = LabelDB(label_db_filename)
        self.label_db.create_if_required()

        # A lookup table from bug x,y to any rectangles that have been drawn
        # in case we want to remove one. the keys of this dict represent all
        # the bug x,y in current image.
        self.x_y_to_boxes = {}  # { (x, y): canvas_id, ... }

        # a flag to denote if bugs are being displayed or not
        # while no displayed we lock down all img navigation
        self.bugs_on = True

        # Main review loop
        self.file_idx = 0

        # Image is displayed as a QPixmap in a QGraphicsScene attached to this QGraphicsView.
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # Store a local handle to the scene's current image pixmap.
        self._pixmapHandle = None

        # Image aspect ratio mode.
        # !!! ONLY applies to full image. Aspect ratio is always ignored when zooming.
        #   Qt.IgnoreAspectRatio: Scale image to fit viewport.
        #   Qt.KeepAspectRatio: Scale image to fit inside viewport, preserving aspect ratio.
        #   Qt.KeepAspectRatioByExpanding: Scale image to fill the viewport, preserving aspect ratio.
        self.aspectRatioMode = Qt.KeepAspectRatio

        # Scroll bar behaviour.
        #   Qt.ScrollBarAlwaysOff: Never shows a scroll bar.
        #   Qt.ScrollBarAlwaysOn: Always shows a scroll bar.
        #   Qt.ScrollBarAsNeeded: Shows a scroll bar only when zoomed.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Stack of QRectF zoom boxes in scene coordinates.
        self.zoomStack = []

        # Flags for enabling/disabling mouse interaction.
        self.canZoom = True
        self.canPan = True

        # Initialize some other variables used occasionally
        self.tmp_x_y = []
        self.click_start_pos = QPoint(0, 0)

        self.display_image()
        self.show()

    def has_image(self):
        """ Returns whether or not the scene contains an image pixmap.
        """
        return self._pixmapHandle is not None

    def clear_image(self):
        """ Removes the current image pixmap from the scene if it exists.
        """
        if self.has_image():
            self.scene.removeItem(self._pixmapHandle)
            self._pixmapHandle = None

    def pixmap(self):
        """ Returns the scene's current image pixmap as a QPixmap, or else None if no image exists.
        :rtype: QPixmap | None
        """
        if self.has_image():
            return self._pixmapHandle.pixmap()
        return None

    def set_image(self, image):
        """ Set the scene's current image pixmap to the input QImage or QPixmap.
        Raises a RuntimeError if the input image has type other than QImage or QPixmap.
        """
        if type(image) is QPixmap:
            pixmap = image
        elif isinstance(image, QImage):
            pixmap = QPixmap.fromImage(image)
        else:
            raise RuntimeError("ImageViewer.setImage: Argument must be a QImage or QPixmap.")
        if self.has_image():
            self._pixmapHandle.setPixmap(pixmap)
        else:
            self._pixmapHandle = self.scene.addPixmap(pixmap)
        self.setSceneRect(QRectF(pixmap.rect()))  # Set scene size to image size.
        self.update_viewer()

    def update_viewer(self):
        """ Show current zoom (if showing entire image, apply current aspect ratio mode).
        """
        if not self.has_image():
            return
        if len(self.zoomStack) and self.sceneRect().contains(self.zoomStack[-1]):
            self.fitInView(self.zoomStack[-1], Qt.IgnoreAspectRatio)  # Show zoomed rect (ignore aspect ratio).
        else:
            self.zoomStack = []  # Clear the zoom stack (in case we got here because of an invalid zoom).
            self.fitInView(self.sceneRect(), self.aspectRatioMode)  # Show entire image (use current aspect ratio mode).

    def resizeEvent(self, event):
        """ Maintain current zoom on resize.
        """
        self.update_viewer()

    def mousePressEvent(self, event):
        """ Start mouse pan or zoom mode.
        """
        scene_pos = self.mapToScene(event.pos())
        self.click_start_pos = event.pos()
        if event.button() == Qt.LeftButton:
            if self.canPan:
                self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.leftMouseButtonPressed.emit(scene_pos.x(), scene_pos.y())
        elif event.button() == Qt.RightButton:
            if self.canZoom:
                self.setDragMode(QGraphicsView.RubberBandDrag)
            self.rightMouseButtonPressed.emit(scene_pos.x(), scene_pos.y())
        QGraphicsView.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        """ Stop mouse pan or zoom mode (apply zoom if valid).
        """
        QGraphicsView.mouseReleaseEvent(self, event)
        scene_pos = self.mapToScene(event.pos())
        movement_vector = event.pos() - self.click_start_pos
        click_distance = math.sqrt(movement_vector.x() ** 2 + movement_vector.y() ** 2)
        if event.button() == Qt.LeftButton:
            self.setDragMode(QGraphicsView.NoDrag)
            if click_distance < 1:
                self.add_bug_event(event)
            self.leftMouseButtonReleased.emit(scene_pos.x(), scene_pos.y())
        elif event.button() == Qt.RightButton:
            if self.canZoom:
                view_bbox = self.zoomStack[-1] if len(self.zoomStack) else self.sceneRect()
                selection_bbox = self.scene.selectionArea().boundingRect().intersected(view_bbox)
                self.scene.setSelectionArea(QPainterPath())  # Clear current selection area.
                if selection_bbox.isValid() and (selection_bbox != view_bbox):
                    self.zoomStack.append(selection_bbox)
                    self.update_viewer()
            self.setDragMode(QGraphicsView.NoDrag)
            if click_distance < 1:
                self.remove_closest_bug_event(event)
            self.rightMouseButtonReleased.emit(scene_pos.x(), scene_pos.y())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.display_next_image()
        elif event.key() == Qt.Key_Left:
            self.display_previous_image()
        elif event.key() == Qt.Key_Up:
            self.toggle_bugs()
        elif event.key() == Qt.Key_N:
            self.display_next_unlabelled_image()
        elif event.key() == Qt.Key_Q:
            QApplication.instance().quit()
        elif event.key() == Qt.Key_Escape:
            if self.canZoom:
                self.zoomStack = []  # Clear zoom stack.
                self.update_viewer()

    def display_image(self):
        # Open image
        img_name = self.files[self.file_idx]
        img_path = os.path.join(self.img_dir, img_name)
        if img_path.endswith('.cr2'):
            # Read raw file
            raw = rawpy.imread(img_path)
            # Convert to PIL Image
            img = Image.fromarray(raw.postprocess())
            # For some reason this is needed to get these to display in the interface
            img = img.convert('RGBA')
            # Turn all .cr2 images right side up
            img = img.transpose(Image.ROTATE_180)
            # Convert to QImage
            img = ImageQt(img)
        else:
            img = ImageQt(Image.open(img_path))
        self.set_image(img)

        # Draw image title
        title = f'{img_name} ({self.file_idx + 1} of {len(self.files)})'
        self.setWindowTitle(title)

        # Look up any existing bugs in DB for this image and add them
        existing_labels = self.label_db.get_labels(img_name)
        for x, y in existing_labels:
            self.add_bug_at(x, y)

    def display_next_image(self):
        if not self.bugs_on:
            print("ignore move to next image; bugs not on")
            return
        self._flush_pending_x_y_to_boxes()
        self.file_idx += 1
        if self.file_idx == len(self.files):
            print("Can't move to image past last image.")
            self.file_idx = len(self.files) - 1
        self.display_image()

    def display_previous_image(self):
        if not self.bugs_on:
            print("ignore move to previous image; bugs not on")
            return
        self._flush_pending_x_y_to_boxes()
        self.file_idx -= 1
        if self.file_idx < 0:
            print("Can't move to image previous to first image.")
            self.file_idx = 0
        self.display_image()

    def display_next_unlabelled_image(self):
        self._flush_pending_x_y_to_boxes()
        while True:
            self.file_idx += 1
            if self.file_idx == len(self.files):
                print("Can't move to image past last image.")
                self.file_idx = len(self.files) - 1
                break
            if not self.label_db.has_labels(self.files[self.file_idx]):
                break
        self.display_image()

    def add_bug_at(self, x, y, size=8):
        rectangle_id = self.scene.addRect(x - size // 2, y - size // 2, size, size, QPen(Qt.black), QBrush(Qt.red))
        self.x_y_to_boxes[(x, y)] = rectangle_id

    def add_bug_event(self, e):
        scene_pos = self.mapToScene(e.pos())
        if not self.bugs_on:
            print("ignore add bug; bugs not on")
            return
        self.add_bug_at(scene_pos.x(), scene_pos.y())

    def _flush_pending_x_y_to_boxes(self):
        # Flush existing points.
        img_name = self.files[self.file_idx]
        self.label_db.set_labels(img_name, self.x_y_to_boxes.keys())
        for rect in self.x_y_to_boxes.values():
            self.scene.removeItem(rect)
        self.x_y_to_boxes.clear()

    def toggle_bugs(self):
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

    def remove_bug(self, rectangle_id):
        self.scene.removeItem(rectangle_id)

    def remove_closest_bug_event(self, e):
        scene_pos = self.mapToScene(e.pos())
        if not self.bugs_on:
            print("ignore remove bug; bugs not on")
            return
        if len(self.x_y_to_boxes) == 0:
            return
        closest_point = None
        closest_sqr_distance = 0.0
        for x, y in self.x_y_to_boxes.keys():
            sqr_distance = (scene_pos.x() - x) ** 2 + (scene_pos.y() - y) ** 2
            if sqr_distance < closest_sqr_distance or closest_point is None:
                closest_point = (x, y)
                closest_sqr_distance = sqr_distance
        self.remove_bug(self.x_y_to_boxes.pop(closest_point))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image-dir', type=str, required=True)
    parser.add_argument('--label-db', type=str, required=True)
    args = parser.parse_args()

    print("""Usage:
    Left click: label bug
    Right click: Remove nearest bug label
    Drag right mouse: zoom to box
    Drag left mouse: Pan (when zoomed in)

    RIGHT: next image
    LEFT: previous image
    UP: toggle labels
    N: next image with no labels
    ESC: reset zoom
    Q: quit
    """
          )

    app = QApplication(sys.argv)
    _ = LabelUI(args.label_db, args.image_dir)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
