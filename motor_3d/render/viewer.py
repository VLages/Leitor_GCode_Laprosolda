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
        self.current_layer = -1   # -1 = mostrar tudo

        # Arrays pré-computados (reconstruídos apenas ao trocar o modelo)
        self._verts_start = None  # (N,4) pontos iniciais homogêneos
        self._verts_end   = None  # (N,4) pontos finais homogêneos
        self._types       = None  # (N,) 0=travel 1=extrude
        self._layers_arr  = None  # (N,) índice de camada

        # ── Estado da câmera orbital ─────────────────────────────────────────
        # A câmera orbita ao redor de _target em coordenadas esféricas.
        self._target      = np.array([0.0, 0.0, 0.0])
        self._orbit_yaw   = 0.4    # ângulo horizontal (rad)
        self._orbit_pitch = 0.4    # ângulo vertical   (rad)
        self._orbit_dist  = 150.0  # distância ao target
        self._MIN_DIST    = 1.0
        self._MAX_DIST    = 5000.0

        # ── Estado do mouse ──────────────────────────────────────────────────
        self._mouse_last   = QPoint()
        self._mouse_button = None

        # ── Timer — só redesenha quando _dirty=True ──────────────────────────
        self._dirty = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._timer.start(16)   # tick a 60 FPS, mas só pinta se necessário

        self.setFocusPolicy(Qt.StrongFocus)

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
        self._fit_view()      # posiciona câmera no centro da peça
        self._dirty = True

    def _precompute_geometry(self):
        """Converte os segmentos em arrays NumPy uma única vez."""
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

    # ────────────────────────────────────────────────────────────────────────
    # Câmera orbital
    # ────────────────────────────────────────────────────────────────────────

    def _fit_view(self):
        """Centraliza o target no bounding box da peça e ajusta a distância."""
        if self.model is None or self.model.bounds is None:
            return
        xmin, ymin, zmin, xmax, ymax, zmax = self.model.bounds
        self._target = np.array([
            (xmin + xmax) / 2,
            (ymin + ymax) / 2,
            (zmin + zmax) / 2,
        ])
        diagonal = math.sqrt((xmax-xmin)**2 + (ymax-ymin)**2 + (zmax-zmin)**2)
        self._orbit_dist  = max(diagonal * 1.5, 10.0)
        self._orbit_yaw   = 0.4
        self._orbit_pitch = 0.4
        self._update_camera()

    def _update_camera(self):
        """
        Recalcula posição e orientação da câmera a partir das coordenadas
        esféricas (_orbit_yaw, _orbit_pitch, _orbit_dist) e do _target.

        Convenção da engine: vetores armazenados como (x, y, z, w=1).
        A rotate_matrix() monta as colunas [right | up | forward], então
        os vetores precisam estar na base do espaço VIEW — não invertidos.
        """
        if self.camera is None:
            return

        yaw   = self._orbit_yaw
        pitch = self._orbit_pitch
        dist  = self._orbit_dist

        # 1. Posição da câmera em coordenadas esféricas ao redor do target
        cam_x = self._target[0] + dist * math.cos(pitch) * math.sin(yaw)
        cam_y = self._target[1] + dist * math.sin(pitch)
        cam_z = self._target[2] + dist * math.cos(pitch) * math.cos(yaw)

        self.camera.position = np.array([cam_x, cam_y, cam_z, 1.0])

        # 2. Vetor forward: da câmera em direção ao target (normalizado)
        fwd = self._target - np.array([cam_x, cam_y, cam_z])
        fwd = fwd / (np.linalg.norm(fwd) + 1e-10)

        # 3. Vetor right: produto vetorial de world_up × forward
        #    Perto dos polos (pitch ≈ ±90°) troca world_up para evitar flip
        if abs(pitch) > math.pi / 2 - 0.05:
            world_up = np.array([0.0, 0.0, 1.0])
        else:
            world_up = np.array([0.0, 1.0, 0.0])

        right = np.cross(fwd, world_up)          # ← ordem correta para câmera look-at
        right = right / (np.linalg.norm(right) + 1e-10)

        # 4. Vetor up real: perpendicular a forward e right
        up = np.cross(right, fwd)
        up = up / (np.linalg.norm(up) + 1e-10)

        # 5. Armazena no formato homogêneo que rotate_matrix() espera
        self.camera.forward = np.array([fwd[0],   fwd[1],   fwd[2],   1.0])
        self.camera.right   = np.array([right[0], right[1], right[2], 1.0])
        self.camera.up      = np.array([up[0],    up[1],    up[2],    1.0])

    # ────────────────────────────────────────────────────────────────────────
    # Loop de renderização
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

    # ────────────────────────────────────────────────────────────────────────
    # Projeção vetorizada em lote
    # ────────────────────────────────────────────────────────────────────────

    def _project_batch(self, verts: np.ndarray):
        """Projeta (N,4) vértices → (N,2) pixels. camera_matrix() chamada 1× por lote."""
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
            # Orbitar
            self.setCursor(QCursor(Qt.SizeAllCursor))
            self._orbit_yaw   += dx * 0.005
            self._orbit_pitch += dy * 0.005
            self._orbit_pitch  = max(-math.pi/2 + 0.05,
                                     min( math.pi/2 - 0.05, self._orbit_pitch))

        elif self._mouse_button == Qt.MiddleButton:
            # Pan — desloca o target nos eixos right/up da câmera
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
        if   key == Qt.Key_Left:  self._orbit_yaw   -= 0.05
        elif key == Qt.Key_Right: self._orbit_yaw   += 0.05
        elif key == Qt.Key_Up:
            self._orbit_pitch = min( math.pi/2 - 0.05, self._orbit_pitch + 0.05)
        elif key == Qt.Key_Down:
            self._orbit_pitch = max(-math.pi/2 + 0.05, self._orbit_pitch - 0.05)
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