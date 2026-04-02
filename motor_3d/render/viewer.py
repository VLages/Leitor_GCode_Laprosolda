from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QCursor, QFont
from PyQt5.QtCore import Qt, QTimer, QPoint
import numpy as np
import math
from .camera import Camera
from .projection import Projection
from ..gcode_model import GCodeModel


class GCodeViewer3D(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model         = None
        self.camera        = None
        self.projection    = None
        self.current_layer = -1

        # Arrays pré-computados
        self._verts_start = None
        self._verts_end   = None
        self._types       = None
        self._layers_arr  = None

        # ── Câmera orbital (trackball) ───────────────────────────────────────
        self._target     = np.array([0.0, 0.0, 0.0])
        self._orbit_dist = 150.0
        self._MIN_DIST   = 1.0
        self._MAX_DIST   = 5000.0

        # Orientação da câmera armazenada como matriz de rotação 3×3.
        # Começa com uma vista isométrica agradável.
        self._rot = self._make_initial_rotation()

        # ── Estado do mouse ──────────────────────────────────────────────────
        self._mouse_last   = QPoint()
        self._mouse_button = None

        # ── Timer ────────────────────────────────────────────────────────────
        self._dirty = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._timer.start(16)

        self.setFocusPolicy(Qt.StrongFocus)

    # ────────────────────────────────────────────────────────────────────────
    # Rotação inicial (vista isométrica — igual ao SolidWorks ao abrir)
    # ────────────────────────────────────────────────────────────────────────

    def _make_initial_rotation(self):
        """Rotação inicial: 30° de pitch + 45° de yaw — vista isométrica."""
        pitch = math.radians(30)
        yaw   = math.radians(45)
        Rx = np.array([
            [1,             0,              0],
            [0,  math.cos(pitch), -math.sin(pitch)],
            [0,  math.sin(pitch),  math.cos(pitch)],
        ])
        Ry = np.array([
            [ math.cos(yaw), 0, math.sin(yaw)],
            [0,              1,             0],
            [-math.sin(yaw), 0, math.cos(yaw)],
        ])
        return Ry @ Rx

    # ────────────────────────────────────────────────────────────────────────
    # Carregamento do modelo
    # ────────────────────────────────────────────────────────────────────────

    def set_model(self, model: GCodeModel):
        self.model = model
        W = max(self.width(),  1)
        H = max(self.height(), 1)
        self.camera     = Camera(W, H)
        self.projection = Projection(self.camera, W, H)
        self._precompute_geometry()
        self._fit_view()
        self._dirty = True

    def _precompute_geometry(self):
        segs = self.model.segments
        if not segs:
            return
        starts = np.array([s.start for s in segs], dtype=np.float64)
        ends   = np.array([s.end   for s in segs], dtype=np.float64)
        ones   = np.ones((len(segs), 1), dtype=np.float64)
        self._verts_start = np.hstack([starts, ones])
        self._verts_end   = np.hstack([ends,   ones])
        self._types      = np.array([0 if s.type == 'travel' else 1 for s in segs])
        self._layers_arr = np.array([s.layer for s in segs])

    def _fit_view(self):
        """Centraliza no bounding box e ajusta distância. Reseta a rotação."""
        if self.model is None or self.model.bounds is None:
            return
        xmin, ymin, zmin, xmax, ymax, zmax = self.model.bounds
        self._target = np.array([
            (xmin + xmax) / 2,
            (ymin + ymax) / 2,
            (zmin + zmax) / 2,
        ])
        diagonal = math.sqrt((xmax-xmin)**2 + (ymax-ymin)**2 + (zmax-zmin)**2)
        self._orbit_dist = max(diagonal * 1.5, 10.0)
        self._rot = self._make_initial_rotation()
        self._update_camera()

    # ────────────────────────────────────────────────────────────────────────
    # Trackball — coração do sistema de rotação estilo SolidWorks
    # ────────────────────────────────────────────────────────────────────────

    def _trackball_rotate(self, dx: int, dy: int):
        """
        Converte deslocamento de pixels (dx, dy) em uma rotação 3D incremental
        aplicada à matriz de orientação _rot.

        Lógica idêntica ao SolidWorks / Blender (middle mouse):
          - dx  →  rotação em torno do eixo Y do MUNDO (girar esquerda/direita)
          - dy  →  rotação em torno do eixo X da CÂMERA (inclinar cima/baixo)

        Isso garante que:
          • Arrastar horizontalmente sempre gira em torno do eixo vertical da tela.
          • Arrastar verticalmente sempre inclina em relação ao eixo horizontal da tela.
          • Não há gimbal lock nem rotações indesejadas em outros eixos.
        """
        sensitivity = 0.004   # rad/pixel — ajuste fino

        angle_yaw   =  dx * sensitivity   # rotação horizontal
        angle_pitch = -dy * sensitivity   # rotação vertical (−dy: arrastar para cima = inclinar para cima)

        # Rotação horizontal: em torno do eixo Y do MUNDO (fixo)
        # Isso imita o SolidWorks — girar a peça em torno do eixo vertical
        # é sempre previsível independente da orientação atual.
        cos_y, sin_y = math.cos(angle_yaw), math.sin(angle_yaw)
        Ry = np.array([
            [ cos_y, 0, sin_y],
            [     0, 1,     0],
            [-sin_y, 0, cos_y],
        ])

        # Rotação vertical: em torno do eixo X da CÂMERA (eixo right atual).
        # Extraímos o vetor right da matriz de rotação atual (primeira coluna de _rot.T)
        right = self._rot[0, :]   # linha 0 de _rot = vetor right no espaço do mundo
        right = right / (np.linalg.norm(right) + 1e-10)
        Rx = self._axis_angle_matrix(right, angle_pitch)

        # Aplica: primeiro inclina (câmera), depois gira (mundo)
        # A ordem Ry @ Rx @ _rot produz o comportamento idêntico ao SolidWorks
        self._rot = Ry @ Rx @ self._rot

        # Reortogonaliza a matriz para evitar acúmulo de erro numérico
        self._rot = self._orthonormalize(self._rot)

    @staticmethod
    def _axis_angle_matrix(axis: np.ndarray, angle: float) -> np.ndarray:
        """Rodrigues' rotation formula — rotação de 'angle' rad em torno de 'axis'."""
        x, y, z = axis / (np.linalg.norm(axis) + 1e-10)
        c, s    = math.cos(angle), math.sin(angle)
        t       = 1 - c
        return np.array([
            [t*x*x + c,   t*x*y - s*z, t*x*z + s*y],
            [t*x*y + s*z, t*y*y + c,   t*y*z - s*x],
            [t*x*z - s*y, t*y*z + s*x, t*z*z + c  ],
        ])

    @staticmethod
    def _orthonormalize(R: np.ndarray) -> np.ndarray:
        """Gram-Schmidt: mantém a matriz de rotação ortonormal."""
        r0 = R[0] / (np.linalg.norm(R[0]) + 1e-10)
        r1 = R[1] - np.dot(R[1], r0) * r0
        r1 = r1   / (np.linalg.norm(r1) + 1e-10)
        r2 = np.cross(r0, r1)
        return np.array([r0, r1, r2])

    # ────────────────────────────────────────────────────────────────────────
    # Atualização da câmera a partir de _rot + _target + _orbit_dist
    # ────────────────────────────────────────────────────────────────────────

    def _update_camera(self):
        """
        Reconstrói posição e vetores da câmera a partir da matriz _rot.

        _rot é uma matriz 3×3 onde:
          linha 0 = vetor right  (X da câmera no espaço do mundo)
          linha 1 = vetor up     (Y da câmera no espaço do mundo)
          linha 2 = vetor forward invertido (-Z, pois a câmera olha para -Z)
        """
        if self.camera is None:
            return

        right   = self._rot[0]
        up      = self._rot[1]
        fwd_inv = self._rot[2]          # aponta PARA FORA da câmera
        forward = -fwd_inv              # forward = direção para onde a câmera OLHA

        # Posição: recua ao longo de fwd_inv pelo orbit_dist a partir do target
        cam_pos = self._target + fwd_inv * self._orbit_dist

        self.camera.position = np.array([cam_pos[0], cam_pos[1], cam_pos[2], 1.0])
        self.camera.forward  = np.array([forward[0], forward[1], forward[2], 1.0])
        self.camera.right    = np.array([right[0],   right[1],   right[2],   1.0])
        self.camera.up       = np.array([up[0],      up[1],      up[2],      1.0])

    # ────────────────────────────────────────────────────────────────────────
    # Timer e renderização
    # ────────────────────────────────────────────────────────────────────────

    def _on_timer(self):
        if self._dirty:
            self.update()
            self._dirty = False

    def paintEvent(self, event):
        if self.model is None or self._verts_start is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(30, 30, 40))
        self._draw_segments_batched(painter)
        self._draw_hint(painter)

    def _draw_hint(self, painter):
        painter.setPen(QPen(QColor(100, 100, 120)))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(
            8, self.height() - 8,
            "Esq: orbitar  |  Scroll: zoom  |  Meio: pan  |  F: centralizar"
        )

    def _project_batch(self, verts: np.ndarray):
        cam_mat  = self.camera.camera_matrix()
        proj_mat = self.projection.projection_matrix
        scr_mat  = self.projection.to_screen_matrix
        v = verts @ cam_mat @ proj_mat
        w = v[:, -1:].copy()
        w[np.abs(w) < 1e-6] = 1e-6
        v = v / w
        valid = ~np.any((v > 2) | (v < -2), axis=1)
        v = v @ scr_mat
        return v[:, :2].astype(np.int32), valid

    def _draw_segments_batched(self, painter: QPainter):
        if self._verts_start is None:
            return
        if self.current_layer >= 0:
            mask   = self._layers_arr == self.current_layer
            starts = self._verts_start[mask]
            ends   = self._verts_end[mask]
            types  = self._types[mask]
        else:
            starts = self._verts_start
            ends   = self._verts_end
            types  = self._types
        if len(starts) == 0:
            return
        pts0, valid0 = self._project_batch(starts)
        pts1, valid1 = self._project_batch(ends)
        valid = valid0 & valid1
        for is_extrude, pen in [
            (False, QPen(QColor( 80,  80, 180), 1)),
            (True,  QPen(QColor(255, 140,   0), 1)),
        ]:
            painter.setPen(pen)
            for i in np.where((types == (1 if is_extrude else 0)) & valid)[0]:
                painter.drawLine(
                    int(pts0[i, 0]), int(pts0[i, 1]),
                    int(pts1[i, 0]), int(pts1[i, 1])
                )

    # ────────────────────────────────────────────────────────────────────────
    # Eventos de mouse
    # ────────────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        self.setFocus()
        self._mouse_last   = event.pos()
        self._mouse_button = event.button()

    def mouseReleaseEvent(self, event):
        self._mouse_button = None
        self.setCursor(QCursor(Qt.ArrowCursor))

    def mouseMoveEvent(self, event):
        if self._mouse_button is None or self.camera is None:
            return
        dx = event.x() - self._mouse_last.x()
        dy = event.y() - self._mouse_last.y()
        self._mouse_last = event.pos()

        if self._mouse_button == Qt.LeftButton:
            self.setCursor(QCursor(Qt.SizeAllCursor))
            self._trackball_rotate(dx, dy)

        elif self._mouse_button == Qt.MiddleButton:
            self.setCursor(QCursor(Qt.SizeAllCursor))
            pan = self._orbit_dist * 0.001
            right = self.camera.right[:3]
            up    = self.camera.up[:3]
            self._target -= right * dx * pan
            self._target += up    * dy * pan

        self._update_camera()
        self._dirty = True

    def wheelEvent(self, event):
        if self.camera is None:
            return
        factor = 0.1 if event.angleDelta().y() > 0 else -0.1
        self._orbit_dist *= (1.0 - factor)
        self._orbit_dist  = max(self._MIN_DIST, min(self._MAX_DIST, self._orbit_dist))
        self._update_camera()
        self._dirty = True

    # ────────────────────────────────────────────────────────────────────────
    # Teclado
    # ────────────────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if self.camera is None:
            return
        key = event.key()
        if key == Qt.Key_F:
            self._fit_view()
            self._dirty = True
            return
        changed = True
        step = 0.05
        if   key == Qt.Key_Left:  self._trackball_rotate(-10,   0)
        elif key == Qt.Key_Right: self._trackball_rotate( 10,   0)
        elif key == Qt.Key_Up:    self._trackball_rotate(  0,  10)
        elif key == Qt.Key_Down:  self._trackball_rotate(  0, -10)
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self._orbit_dist = max(self._MIN_DIST, self._orbit_dist * 0.9)
        elif key == Qt.Key_Minus:
            self._orbit_dist = min(self._MAX_DIST, self._orbit_dist * 1.1)
        else:
            changed = False
        if changed:
            self._update_camera()
            self._dirty = True

    # ────────────────────────────────────────────────────────────────────────
    # Redimensionamento
    # ────────────────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        if self.camera is not None:
            W = max(self.width(),  1)
            H = max(self.height(), 1)
            self.camera.WIDTH  = W
            self.camera.HEIGHT = H
            self.camera.v_fov  = self.camera.h_fov * (H / W)
            self.projection    = Projection(self.camera, W, H)
            self._dirty = True
        super().resizeEvent(event)