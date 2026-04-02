from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QTimer
import numpy as np
from .camera import *
from .projection import Projection
from .matrix import translate, rotate_x, rotate_y
from ..gcode_parser import GCodeModel

class GCodeViewer3D(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None   # GCodeModel
        self.camera = None   # Camera (da 3D Engine adaptada)
        self.projection = None   # Projection (da 3D Engine — sem mudanças)
        self.current_layer = -1  # -1 = mostrar tudo
        # Timer para atualização do viewport (30 FPS)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(33)

    def keyPressEvent(self, event):  # no GCodeViewer3D
        key = event.key()
        cam = self.camera
        speed = cam.moving_speed
        if key == Qt.Key_W: cam.position += cam.forward * speed
        if key == Qt.Key_S: cam.position -= cam.forward * speed
        if key == Qt.Key_A: cam.position -= cam.right   * speed
        if key == Qt.Key_D: cam.position += cam.right   * speed
        if key == Qt.Key_Left:  cam.camera_yaw(-cam.rotation_speed)
        if key == Qt.Key_Right: cam.camera_yaw( cam.rotation_speed)
        if key == Qt.Key_Up:    cam.camera_pitch(-cam.rotation_speed)
        if key == Qt.Key_Down:  cam.camera_pitch( cam.rotation_speed)
        self.update()

    def set_model(self, model: GCodeModel):
        self.model = model
        W, H = self.width(), self.height()
        self.camera = Camera(W, H, position=[-5, 6, -50])
        self.projection = Projection(self.camera, W, H)
        self.update()

    def paintEvent(self, event):
        if not self.model: return
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30, 30, 40))
        self._draw_segments(painter)

    def _project_point(self, x, y, z):
        v = np.array([[x, y, z, 1.0]])
        v = v @ self.camera.camera_matrix()
        v = v @ self.projection.projection_matrix
        v /= v[:, -1].reshape(-1, 1)
        v = v @ self.projection.to_screen_matrix
        return int(v[0, 0]), int(v[0, 1])

    def _draw_segments(self, painter):
        travel_pen  = QPen(QColor(80, 80, 120), 1)
        extrude_pen = QPen(QColor(255, 140, 0), 1)
        for seg in self.model.segments:
            if self.current_layer >= 0 and seg.layer != self.current_layer:
                continue
            painter.setPen(travel_pen if seg.type == 'travel' else extrude_pen)
            x0,y0 = self._project_point(*seg.start)
            x1,y1 = self._project_point(*seg.end)
            painter.drawLine(x0, y0, x1, y1)