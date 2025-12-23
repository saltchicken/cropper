import sys
import os
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QRadioButton,
    QFileDialog,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QButtonGroup,
    QMessageBox,
    QLabel,
)
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QPen, QColor, QImage
from PIL import Image


class CropBox(QGraphicsRectItem):
    def __init__(self, rect, image_rect):
        super().__init__(rect)
        self.image_rect = image_rect
        self.setPen(QPen(QColor("red"), 2))
        self.setBrush(QColor(255, 0, 0, 50))  # Semi-transparent red
        self.setFlags(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

    def itemChange(self, change, value):
        if (
            change == QGraphicsRectItem.GraphicsItemChange.ItemPositionChange
            and self.scene()
        ):
            new_pos = value
            rect = self.rect()

            # Calculate where the rectangle would be in scene coordinates
            # Note: The item's local rect is usually (0,0,w,h), the position is the offset
            proposed_x = new_pos.x()
            proposed_y = new_pos.y()

            if proposed_x < 0:
                proposed_x = 0
            if proposed_y < 0:
                proposed_y = 0

            # If (x + width) > image_width, clamp x to (image_width - width)
            if proposed_x + rect.width() > self.image_rect.width():
                proposed_x = self.image_rect.width() - rect.width()

            if proposed_y + rect.height() > self.image_rect.height():
                proposed_y = self.image_rect.height() - rect.height()

            return QPointF(proposed_x, proposed_y)

        return super().itemChange(change, value)


class ImageCropper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 Fixed Size Cropper")
        self.resize(1200, 800)

        # Variables
        self.image_path = None
        self.pixmap_item = None
        self.crop_item = None


        self.crop_sizes = [
            (512, 512),
            (768, 768),
            (1024, 1024),
            (720, 1280),
            (1280, 720),
        ]
        self.current_crop_size = self.crop_sizes[0]

        self.scene = QGraphicsScene()

        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Sidebar ---
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar.setFixedWidth(200)

        # Open Button
        btn_open = QPushButton("Open Image")
        btn_open.clicked.connect(self.load_image)
        sidebar_layout.addWidget(btn_open)

        sidebar_layout.addSpacing(20)
        sidebar_layout.addWidget(QLabel("Crop Size:"))

        self.size_group = QButtonGroup(self)
        self.radios = []


        for i, (w, h) in enumerate(self.crop_sizes):
            rb = QRadioButton(f"{w}x{h}")
            if i == 0:
                rb.setChecked(True)
            self.size_group.addButton(rb, i)
            sidebar_layout.addWidget(rb)
            self.radios.append(rb)

        self.size_group.idClicked.connect(self.change_crop_size)

        sidebar_layout.addStretch()

        btn_save = QPushButton("Overwrite Original")
        btn_save.setStyleSheet(
            "background-color: #8b0000; color: white; font-weight: bold; padding: 10px;"
        )
        btn_save.clicked.connect(self.overwrite_image)
        sidebar_layout.addWidget(btn_save)

        main_layout.addWidget(sidebar)

        # --- Graphics View ---
        self.view = QGraphicsView(self.scene)
        self.view.setBackgroundBrush(QColor("#333333"))
        main_layout.addWidget(self.view)

    def load_image(self, file_path=None):
        # If file_path is None or False (from button click), open dialog
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
            )

        if file_path:
            self.image_path = file_path
            self.scene.clear()
            self.crop_item = None

            # Load image
            original_image = QImage(self.image_path)
            self.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(original_image))
            self.scene.addItem(self.pixmap_item)

            # Set scene bounds to match image
            rect = QRectF(self.pixmap_item.pixmap().rect())
            self.scene.setSceneRect(rect)

            self.add_crop_box()
            self.setWindowTitle(f"Cropper - {os.path.basename(file_path)}")

    def change_crop_size(self, size_id):

        self.current_crop_size = self.crop_sizes[size_id]
        if self.pixmap_item:
            self.add_crop_box()

    def add_crop_box(self):
        if not self.pixmap_item:
            return

        # Remove old box if exists
        if self.crop_item:
            self.scene.removeItem(self.crop_item)


        w, h = self.current_crop_size

        # Create new rect (0, 0, width, height)
        rect = QRectF(0, 0, w, h)
        image_rect = self.pixmap_item.boundingRect()

        self.crop_item = CropBox(rect, image_rect)

        # Reset position to (0,0) or clamp if somehow out of bounds immediately
        self.crop_item.setPos(0, 0)

        self.scene.addItem(self.crop_item)

    def overwrite_image(self):
        if not self.image_path or not self.crop_item:
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Overwrite",
            "This will PERMANENTLY overwrite the original file.\nAre you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            # Get coordinates relative to the image
            pos = self.crop_item.pos()
            x = int(pos.x())
            y = int(pos.y())


            w, h = self.current_crop_size

            try:
                with Image.open(self.image_path) as img:
                    # Box tuple is (left, upper, right, lower)

                    crop_box = (x, y, x + w, y + h)
                    cropped_img = img.crop(crop_box)
                    cropped_img.save(self.image_path)

                self.load_image(self.image_path)
                QMessageBox.information(self, "Success", "Image cropped and saved!")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save image: {str(e)}")


if __name__ == "__main__":
    # os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"

    app = QApplication(sys.argv)
    window = ImageCropper()
    window.show()
    sys.exit(app.exec())