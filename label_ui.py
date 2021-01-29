import argparse
import math
import os
import sys

from PIL import Image
from PIL.ImageQt import ImageQt
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QPoint
from PyQt5.QtGui import QImage, QPixmap, QPainterPath, QPen, QBrush, QFont, QFontMetrics
from PyQt5.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QInputDialog
import rawpy

from label_db import LabelDB


class Label:
    """Base class for labels, to be subclassed
    """
    def __init__(self, x, y, canvas_id):
        self.x = x
        self.y = y
        self.canvas_id = canvas_id


class Bug(Label):
    """Bug label
    """
    def __init__(self, x, y, canvas_id):
        super().__init__(x, y, canvas_id)


class Tickmark(Label):
    """Tickmark label for the mark itself, not the numbers
    """
    def __init__(self, x, y, canvas_id):
        super().__init__(x, y, canvas_id)


class TickmarkNumber(Label):
    """Label surrounding the numbers written next to a tickmark
    """
    def __init__(self, x, y, canvas_id, width, height, value, number_canvas_id):
        super().__init__(x, y, canvas_id)
        self.width = width
        self.height = height
        self.value = value
        self.number_canvas_id = number_canvas_id


class LabelUI(QGraphicsView):
    """PyQt image viewer adapted from
    https://github.com/marcel-goldschen-ohm/PyQtImageViewer/blob/master/QtImageViewer.py
    """

    # Create signals for mouse events. Note that mouse button signals
    # emit (x, y) coordinates but image matrices are indexed (y, x).
    leftMouseButtonPressed = pyqtSignal(float, float)
    rightMouseButtonPressed = pyqtSignal(float, float)
    leftMouseButtonReleased = pyqtSignal(float, float)
    rightMouseButtonReleased = pyqtSignal(float, float)
    leftMouseButtonDoubleClicked = pyqtSignal(float, float)
    rightMouseButtonDoubleClicked = pyqtSignal(float, float)

    def __init__(self, label_db_filename, img_dir):
        QGraphicsView.__init__(self)
        self.setWindowTitle(label_db_filename)

        self.img_dir = img_dir
        files_list = []
        # Walk through directory tree, get all files
        for dir_path, dir_names, filenames in os.walk(img_dir):
            files_list += [os.path.join(dir_path, f) for f in filenames]
        files_list = sorted(files_list)
        self.files = files_list

        # Label db
        self.label_db = LabelDB(label_db_filename)
        self.label_db.create_if_required()

        # A lookup table from bug x,y to any labels that have been added
        self.x_y_to_labels = {}  # { (x, y): Label, ... }

        # Flag to denote if bugs are being displayed or not.
        # While not displayed, we lock down all image navigation
        self.bugs_on = True

        # Main review loop
        self.file_idx = 0

        # Image is displayed as a QPixmap in a QGraphicsScene attached to this QGraphicsView
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # Store a local handle to the scene's current image pixmap
        self._pixmapHandle = None

        # Scale image to fit inside viewport, preserving aspect ratio
        self.aspectRatioMode = Qt.KeepAspectRatio

        # Shows a scroll bar only when zoomed
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Stack of QRectF zoom boxes in scene coordinates
        self.zoomStack = []

        # Initialize some other variables used occasionally
        self.tmp_x_y = []
        self.click_start_pos = QPoint(0, 0)
        self._t_key_pressed = False
        self._started_tickmark_click = False
        self.complete = False

        self.display_image()
        self.show()

    def update_title(self):
        name = os.path.basename(self.files[self.file_idx])
        num_bugs = 0
        for label in self.x_y_to_labels.values():
            if isinstance(label, Bug):
                num_bugs += 1
        title = f'{name} ({self.file_idx + 1} of {len(self.files)}): {num_bugs} bugs'
        if self.complete:
            title += ' [COMPLETE]'
        self.setWindowTitle(title)

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
            raise RuntimeError('ImageViewer.setImage: Argument must be a QImage or QPixmap.')
        if self.has_image():
            self._pixmapHandle.setPixmap(pixmap)
        else:
            self._pixmapHandle = self.scene.addPixmap(pixmap)
        self.setSceneRect(QRectF(pixmap.rect()))  # Set scene size to image size
        self.update_viewer()

    def update_viewer(self):
        """ Show current zoom (if showing entire image, apply current aspect ratio mode).
        """
        if not self.has_image():
            return
        if len(self.zoomStack) and self.sceneRect().contains(self.zoomStack[-1]):
            self.fitInView(self.zoomStack[-1], Qt.IgnoreAspectRatio)  # Show zoomed rect (ignore aspect ratio)
        else:
            # Clear the zoom stack (in case we got here because of an invalid zoom)
            self.zoomStack = []
            # Show entire image (use current aspect ratio mode)
            self.fitInView(self.sceneRect(), self.aspectRatioMode)

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
            if self._t_key_pressed:
                self._started_tickmark_click = True
                self.setDragMode(QGraphicsView.RubberBandDrag)
            else:
                self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.leftMouseButtonPressed.emit(scene_pos.x(), scene_pos.y())
        elif event.button() == Qt.RightButton:
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
            if self._started_tickmark_click:
                if click_distance < 1:
                    self.add_tickmark_event(event)
                view_bbox = self.zoomStack[-1] if len(self.zoomStack) else self.sceneRect()
                selection_bbox = self.scene.selectionArea().boundingRect().intersected(view_bbox)
                self.scene.setSelectionArea(QPainterPath())  # Clear current selection area.
                if selection_bbox.isValid() and (selection_bbox != view_bbox):
                    self.add_tickmark_number_event(selection_bbox)
            else:
                if click_distance < 1:
                    self.add_bug_event(event)
            self.setDragMode(QGraphicsView.NoDrag)
            self.leftMouseButtonReleased.emit(scene_pos.x(), scene_pos.y())
        elif event.button() == Qt.RightButton:
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
        self._started_tickmark_click = False

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
            self.zoomStack = []  # Clear zoom stack.
            self.update_viewer()
        elif event.key() == Qt.Key_T:
            self._t_key_pressed = True
        elif event.key() == Qt.Key_G:
            self.complete = False if self.complete else True
            self.update_title()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_T:
            self._t_key_pressed = False

    def display_image(self):
        # Open image
        img_name = self.files[self.file_idx]
        img_path = os.path.join(self.img_dir, img_name)
        # If this is a raw file it gets special treatment
        if img_path.lower().endswith('.cr2'):
            # Read raw file
            raw = rawpy.imread(img_path)
            # Convert to PIL Image
            img = Image.fromarray(raw.postprocess())
        else:
            img = Image.open(img_path)
        # For some reason RGB images do not like to display in the interface.
        # RGBA seems to work
        img = img.convert('RGBA')
        # Convert to QImage
        img = ImageQt(img)
        self.set_image(img)

        # Look up any existing labels in DB for this image and add them
        existing_bugs = self.label_db.get_bugs(img_name)
        for x, y in existing_bugs:
            self.add_bug_at(x, y)
        existing_tickmarks = self.label_db.get_tickmarks(img_name)
        for x, y in existing_tickmarks:
            self.add_tickmark_at(x, y)
        existing_tickmark_numbers = self.label_db.get_tickmark_numbers(img_name)
        for x, y, w, h, val in existing_tickmark_numbers:
            self.add_tickmark_number_at(x, y, w, h, val)
        complete = self.label_db.get_complete(img_name)
        self.complete = complete
        self.update_title()

    def display_next_image(self):
        if not self.bugs_on:
            print('ignore move to next image; bugs not on')
            return
        self._flush_pending_x_y_to_boxes()
        self.file_idx += 1
        if self.file_idx == len(self.files):
            print("Can't move to image past last image.")
            self.file_idx = len(self.files) - 1
        self.display_image()

    def display_previous_image(self):
        if not self.bugs_on:
            print('ignore move to previous image; bugs not on')
            return
        self._flush_pending_x_y_to_boxes()
        self.file_idx -= 1
        if self.file_idx < 0:
            print("Can't move to image previous to first image.")
            self.file_idx = 0
        self.display_image()

    def display_next_incomplete_image(self):
        self._flush_pending_x_y_to_boxes()
        while True:
            self.file_idx += 1
            if self.file_idx == len(self.files):
                print("Can't move to image past last image.")
                self.file_idx = len(self.files) - 1
                break
            if not self.label_db.get_complete(self.files[self.file_idx]):
                break
        self.display_image()

    def add_bug_at(self, x, y):
        size = self.scene.width() // 300
        rectangle_id = self.scene.addRect(x - size // 2, y - size // 2, size, size, QPen(Qt.black), QBrush(Qt.red))
        self.x_y_to_labels[(x, y)] = Bug(x, y, rectangle_id)
        self.update_title()

    def add_bug_event(self, e):
        scene_pos = self.mapToScene(e.pos())
        if not self.bugs_on:
            print('ignore add bug; bugs not on')
            return
        self.add_bug_at(scene_pos.x(), scene_pos.y())

    def add_tickmark_number_event(self, box):
        if not self.bugs_on:
            print('ignore add tickmark; bugs not on')
            return
        rectangle_id = self.scene.addRect(box, QPen(Qt.blue, self.scene.width() // 300))
        val, _ = QInputDialog.getInt(self, 'Input', 'Enter tickmark value:')
        font = QFont()
        font_pixel_size = 1
        font.setPixelSize(font_pixel_size)
        while QFontMetrics(font).boundingRect(str(val)).width() < box.width()\
                and QFontMetrics(font).boundingRect(str(val)).height() < box.height():
            font_pixel_size += 1
            font.setPixelSize(font_pixel_size)
        font_pixel_size -= 1
        number_canvas_id = self.scene.addText(str(val), font)
        number_canvas_id.setDefaultTextColor(Qt.blue)
        number_canvas_id.setPos(QPoint(int(box.x()), int(box.y())))
        self.x_y_to_labels[(box.x, box.y)] = TickmarkNumber(box.x, box.y, rectangle_id,
                                                            box.width(), box.height(), val,
                                                            number_canvas_id)
        # TODO LEFT OFF make t toggle tickmark mode rather than current thing

    def _flush_pending_x_y_to_boxes(self):
        # TODO fix this to handle all things
        # Flush existing points.
        img_name = self.files[self.file_idx]
        self.label_db.set_labels(img_name, self.x_y_to_labels.keys())
        for rect in self.x_y_to_labels.values():
            self.scene.removeItem(rect)
        self.x_y_to_labels.clear()

    def toggle_bugs(self):
        if self.bugs_on:
            # store x,y s in tmp list and delete all rectangles from canvas
            self.tmp_x_y = []
            for (x, y), rectangle_id in self.x_y_to_labels.items():
                self.remove_bug(rectangle_id)
                self.tmp_x_y.append((x, y))
            self.x_y_to_labels = {}
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
            print('ignore remove bug; bugs not on')
            return
        if len(self.x_y_to_labels) == 0:
            return
        closest_point = None
        closest_sqr_distance = 0.0
        for x, y in self.x_y_to_labels.keys():
            sqr_distance = (scene_pos.x() - x) ** 2 + (scene_pos.y() - y) ** 2
            if sqr_distance < closest_sqr_distance or closest_point is None:
                closest_point = (x, y)
                closest_sqr_distance = sqr_distance
        self.remove_bug(self.x_y_to_labels.pop(closest_point))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image-dir', type=str, required=True)
    parser.add_argument('--label-db', type=str, required=True)
    args = parser.parse_args()

    print('''Usage:
    Left click: label bug
    Right click: Remove nearest bug label
    Drag right mouse: zoom to box
    Drag left mouse: Pan (when zoomed in)
    Drag left mouse while holding T: identify tick mark

    RIGHT: next image
    LEFT: previous image
    UP: toggle labels
    N: next image with no labels
    ESC: reset zoom
    Q: quit
    '''
          )

    app = QApplication(sys.argv)
    _ = LabelUI(args.label_db, args.image_dir)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
