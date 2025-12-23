import sys
import os
import subprocess
import shutil
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
    QProgressDialog,
)
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QPen, QColor, QImage
import cv2


class CropBox(QGraphicsRectItem):
    def __init__(self, rect, image_rect):
        super().__init__(rect)
        self.image_rect = image_rect
        self.setPen(QPen(QColor("red"), 2))
        self.setBrush(QColor(255, 0, 0, 50))
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

            proposed_x = new_pos.x()
            proposed_y = new_pos.y()

            if proposed_x < 0:
                proposed_x = 0
            if proposed_y < 0:
                proposed_y = 0

            if proposed_x + rect.width() > self.image_rect.width():
                proposed_x = self.image_rect.width() - rect.width()
            if proposed_y + rect.height() > self.image_rect.height():
                proposed_y = self.image_rect.height() - rect.height()

            return QPointF(proposed_x, proposed_y)

        return super().itemChange(change, value)


class VideoCropper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 Fixed Size VIDEO Cropper")
        self.resize(1200, 800)

        self.video_path = None
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

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Sidebar ---
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar.setFixedWidth(200)

        btn_open = QPushButton("Open Video")
        btn_open.clicked.connect(self.load_video)
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
        btn_save.clicked.connect(self.overwrite_video)
        btn_save.setShortcut("Return")
        sidebar_layout.addWidget(btn_save)

        main_layout.addWidget(sidebar)

        # --- Graphics View ---
        self.view = QGraphicsView(self.scene)
        self.view.setBackgroundBrush(QColor("#333333"))
        main_layout.addWidget(self.view)

    def load_video(self, file_path=None):
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open Video", "", "Videos (*.mp4 *.mkv *.avi *.mov *.webm)"
            )

        if file_path:
            self.video_path = file_path
            self.scene.clear()
            self.crop_item = None

            cap = cv2.VideoCapture(self.video_path)
            ret, frame = cap.read()
            cap.release()

            if not ret:
                QMessageBox.critical(self, "Error", "Could not read video frame.")
                return

            # Convert BGR (OpenCV) to RGB (Qt)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w

            # Create QImage from data
            qt_image = QImage(
                frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888
            )
            self.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(qt_image))
            self.scene.addItem(self.pixmap_item)

            rect = QRectF(self.pixmap_item.pixmap().rect())
            self.scene.setSceneRect(rect)

            self.add_crop_box()
            self.setWindowTitle(f"Video Cropper - {os.path.basename(file_path)}")

    def change_crop_size(self, size_id):
        self.current_crop_size = self.crop_sizes[size_id]
        if self.pixmap_item:
            self.add_crop_box()

    def add_crop_box(self):
        if not self.pixmap_item:
            return
        if self.crop_item:
            self.scene.removeItem(self.crop_item)

        w, h = self.current_crop_size
        rect = QRectF(0, 0, w, h)
        image_rect = self.pixmap_item.boundingRect()
        self.crop_item = CropBox(rect, image_rect)
        self.crop_item.setPos(0, 0)
        self.scene.addItem(self.crop_item)


    def get_next_file(self):
        if not self.video_path:
            return None

        directory = os.path.dirname(self.video_path)
        filename = os.path.basename(self.video_path)
        extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm"}

        files = []
        try:
            for f in sorted(os.listdir(directory)):
                if os.path.splitext(f)[1].lower() in extensions:
                    files.append(f)
        except OSError:
            return None

        if filename not in files:
            return None

        current_index = files.index(filename)
        if current_index + 1 < len(files):
            return os.path.join(directory, files[current_index + 1])

        return None

    def overwrite_video(self):
        if not self.video_path or not self.crop_item:
            return


        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Confirm Overwrite")
        msg_box.setText(
            "This will process the ENTIRE video using ffmpeg.\nIt will overwrite the original file.\nAre you sure?"
        )

        btn_overwrite = msg_box.addButton(
            "Overwrite", QMessageBox.ButtonRole.AcceptRole
        )
        btn_overwrite_next = msg_box.addButton(
            "Overwrite & Next", QMessageBox.ButtonRole.AcceptRole
        )
        btn_cancel = msg_box.addButton(QMessageBox.StandardButton.Cancel)

        msg_box.setDefaultButton(
            btn_overwrite_next
        )

        msg_box.exec()
        clicked_button = msg_box.clickedButton()


        if clicked_button in (btn_overwrite, btn_overwrite_next):
            pos = self.crop_item.pos()
            x = int(pos.x())
            y = int(pos.y())

            w, h = self.current_crop_size

            temp_output = self.video_path + "_temp_crop.mp4"

            # -vf crop=w:h:x:y -> Applies the crop video filter
            # -c:a copy -> Copies audio without re-encoding (fast)
            # -y -> Overwrite temp file if exists
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                self.video_path,
                "-vf",
                f"crop={w}:{h}:{x}:{y}",
                "-c:a",
                "copy",
                temp_output,
            ]

            print(f"Running: {' '.join(cmd)}")

            # Show a simple modal dialog so user knows it's working
            progress = QProgressDialog(
                "Processing video with FFmpeg...", None, 0, 0, self
            )
            progress.setWindowTitle("Please Wait")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            QApplication.processEvents()

            try:
                # Run ffmpeg
                result = subprocess.run(cmd, capture_output=True, text=True)

                progress.close()

                if result.returncode == 0:
                    shutil.move(temp_output, self.video_path)


                    if clicked_button == btn_overwrite_next:
                        next_file = self.get_next_file()
                        if next_file:
                            self.load_video(next_file)
                        else:
                            QMessageBox.information(
                                self,
                                "Success",
                                "Video saved!\n(No next video found in directory)",
                            )
                            self.load_video(self.video_path)
                    else:
                        self.load_video(self.video_path)
                        QMessageBox.information(
                            self, "Success", "Video cropped and saved!"
                        )
                else:
                    QMessageBox.critical(
                        self, "FFmpeg Error", f"Error:\n{result.stderr}"
                    )
                    if os.path.exists(temp_output):
                        os.remove(temp_output)

            except Exception as e:
                progress.close()
                QMessageBox.critical(self, "Error", f"Execution failed: {str(e)}")


if __name__ == "__main__":
    # os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
    app = QApplication(sys.argv)
    window = VideoCropper()
    window.show()
    sys.exit(app.exec())