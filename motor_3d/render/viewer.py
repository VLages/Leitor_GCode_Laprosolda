from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QCursor, QFont, QBrush
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect
import numpy as np
import math
from .camera import Camera
from .projection import Projection
from ..gcode_model import GCodeModel


class AxisWidget(QWidget):
    """
    Widget de gizmo 3D (canto inferior direito) mostrando os eixos X/Y/Z
    com setas clicaveis para alinhar a camera a um eixo.
    Inspirado no gizmo do nc-viewer / SolidWorks.
    """

    AXIS_COLORS = {
        'X': QColor(220,  60,  60),
        'Y': QColor( 60, 200,  60),
        'Z': QColor( 60, 110, 220),
    }
    NEG_COLORS = {
        'X': QColor(120,  30,  30),
        'Y': QColor( 30, 110,  30),
        'Z': QColor( 30,  55, 130),
    }
    # Vetor de cada eixo no espaco do modelo
    AXES = {
        'X': np.array([1.0, 0.0, 0.0]),
        'Y': np.array([0.0, 1.0, 0.0]),
        'Z': np.array([0.0, 0.0, 1.0]),
    }

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer   = viewer
        self.SIZE     = 90
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self._hovered = None   # nome do eixo/face em hover

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx, cy = self.SIZE // 2, self.SIZE // 2
        R = 28   # comprimento das setas

        # Fundo semi-transparente
        painter.setBrush(QBrush(QColor(20, 20, 35, 160)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, self.SIZE, self.SIZE)

        if self.viewer.camera is None:
            return

        rot = self.viewer._rot   # 3x3 matriz de rotacao atual

        # Projeta cada eixo no plano 2D do widget
        # A camera olha ao longo de -rot[2], entao usamos rot[0] (right) e rot[1] (up)
        right = rot[0]
        up    = rot[1]

        def project(axis_vec):
            x2d =  np.dot(axis_vec, right) * R
            y2d = -np.dot(axis_vec, up)    * R   # Y invertido (tela)
            return int(cx + x2d), int(cy + y2d)

        # Ordena os eixos por profundidade (mais afastados primeiro)
        fwd = rot[2]   # forward invertido: positivo = afastado da camera
        depths = {name: np.dot(vec, fwd) for name, vec in self.AXES.items()}
        ordered = sorted(self.AXES.items(), key=lambda kv: -depths[kv[0]])

        tip_radius = 7

        for name, vec in ordered:
            ex, ey = project(vec)
            nx, ny = project(-vec)

            # Eixo negativo (linha tracejada mais fina)
            pen = QPen(self.NEG_COLORS[name], 1, Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(cx, cy, nx, ny)

            # Eixo positivo (linha solida)
            pen = QPen(self.AXIS_COLORS[name], 2)
            painter.setPen(pen)
            painter.drawLine(cx, cy, ex, ey)

            # Bolinha na ponta + label
            is_hov = (self._hovered == name)
            color  = self.AXIS_COLORS[name].lighter(130) if is_hov else self.AXIS_COLORS[name]
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(ex - tip_radius, ey - tip_radius, tip_radius*2, tip_radius*2)

            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont("Consolas", 7, QFont.Bold))
            painter.drawText(QRect(ex - tip_radius, ey - tip_radius, tip_radius*2, tip_radius*2),
                             Qt.AlignCenter, name)

    def _axis_at(self, pos):
        """Retorna o nome do eixo mais proximo do ponto clicado, ou None."""
        if self.viewer.camera is None:
            return None
        cx, cy = self.SIZE // 2, self.SIZE // 2
        R  = 28
        rot   = self.viewer._rot
        right = rot[0]
        up    = rot[1]

        best, best_d = None, 12
        for name, vec in self.AXES.items():
            ex = cx + np.dot(vec, right) * R
            ey = cy - np.dot(vec, up)    * R
            d  = math.hypot(pos.x() - ex, pos.y() - ey)
            if d < best_d:
                best, best_d = name, d
        return best

    def mouseMoveEvent(self, event):
        prev = self._hovered
        self._hovered = self._axis_at(event.pos())
        if self._hovered != prev:
            self.update()

    def leaveEvent(self, event):
        self._hovered = None
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        name = self._axis_at(event.pos())
        if name is None:
            return
        self._align_to_axis(name)

    def _align_to_axis(self, axis_name):
        """
        Alinha a camera para olhar ao longo do eixo oposto ao clicado
        (similar ao comportamento do nc-viewer e SolidWorks).
        """
        v = self.viewer
        targets = {
            'X': (np.array([1,0,0]), np.array([0,0,1])),  # olha de +X, up=Z
            'Y': (np.array([0,1,0]), np.array([0,0,1])),  # olha de +Y, up=Z
            'Z': (np.array([0,0,1]), np.array([0,1,0])),  # olha de +Z, up=Y
        }
        fwd_inv, up_vec = targets[axis_name]
        right = np.cross(up_vec, fwd_inv)
        right = right / (np.linalg.norm(right) + 1e-10)
        up2   = np.cross(fwd_inv, right)
        v._rot = np.array([right, up2, fwd_inv])
        v._rot = v._orthonormalize(v._rot)
        v._update_camera()
        v._dirty = True
        self.update()


class GCodeViewer3D(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model         = None
        self.camera        = None
        self.projection    = None
        self.current_layer = -1   # -1 = objeto completo
        self.layer_isolated = False  # True = so mostra a camada atual, sem inferiores

        # Arrays pre-computados
        self._verts_start = None
        self._verts_end   = None
        self._types       = None
        self._layers_arr  = None
        self._line_nums   = None   # linha original de cada segmento

        # Indice do segmento atual na simulacao (-1 = todos)
        self._sim_index   = -1

        # Segmento destacado por selecao no codigo
        self._highlighted_seg = None  # int | None

        # Callbacks
        self.on_segment_changed = None

        # ── Camera orbital ───────────────────────────────────────────────────
        self._target     = np.array([0.0, 0.0, 0.0])
        self._orbit_dist = 150.0
        self._MIN_DIST   = 1.0
        self._MAX_DIST   = 5000.0
        self._rot        = self._make_initial_rotation()

        # ── Inercia ──────────────────────────────────────────────────────────
        self._vel_dx  = 0.0
        self._vel_dy  = 0.0
        self._INERTIA = 0.88
        self._dragging = False

        # ── Mouse ────────────────────────────────────────────────────────────
        self._mouse_last   = QPoint()
        self._mouse_button = None

        # ── Timers ───────────────────────────────────────────────────────────
        self._dirty = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._timer.start(16)

        self._sim_timer    = QTimer(self)
        self._sim_timer.timeout.connect(self._sim_step)
        self._sim_speed_ms = 50
        self._sim_running  = False

        # ── Cores (alteradas por tema/config) ────────────────────────────────
        self.show_travel      = True
        self.color_travel     = QColor(60, 60, 180)
        self.color_extrude    = QColor(255, 140, 0)
        self.color_background = QColor(22, 22, 32)

        self.setFocusPolicy(Qt.StrongFocus)

        # ── Gizmo de eixos ───────────────────────────────────────────────────
        self._axis_widget = AxisWidget(self, self)
        self._axis_widget.raise_()

    # ────────────────────────────────────────────────────────────────────────
    # Posicionamento do gizmo ao redimensionar
    # ────────────────────────────────────────────────────────────────────────

    def _reposition_gizmo(self):
        margin = 8
        s = self._axis_widget.SIZE
        self._axis_widget.move(self.width() - s - margin, self.height() - s - margin)

    def resizeEvent(self, event):
        if self.camera is not None:
            W = max(self.width(),  1)
            H = max(self.height(), 1)
            self.camera.WIDTH  = W
            self.camera.HEIGHT = H
            self.camera.v_fov  = self.camera.h_fov * (H / W)
            self.projection    = Projection(self.camera, W, H)
            self._dirty = True
        self._reposition_gizmo()
        super().resizeEvent(event)

    # ────────────────────────────────────────────────────────────────────────
    # Rotacao inicial
    # ────────────────────────────────────────────────────────────────────────

    def _make_initial_rotation(self):
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
    # Modelo
    # ────────────────────────────────────────────────────────────────────────

    def set_model(self, model: GCodeModel):
        self.model = model
        self._sim_index       = -1
        self._highlighted_seg = None
        self._sim_running     = False
        self._sim_timer.stop()
        W = max(self.width(),  1)
        H = max(self.height(), 1)
        self.camera     = Camera(W, H)
        self.projection = Projection(self.camera, W, H)
        self._precompute_geometry()
        self._fit_view()
        self._reposition_gizmo()
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
        self._types       = np.array([0 if s.type == 'travel' else 1 for s in segs])
        self._layers_arr  = np.array([s.layer for s in segs])
        self._line_nums   = np.array([s.line_number for s in segs])

    def _fit_view(self):
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
    # Highlight por linha de codigo
    # ────────────────────────────────────────────────────────────────────────

    def highlight_line(self, line_number: int):
        """
        Recebe um numero de linha do codigo GCode e destaca o segmento
        correspondente na renderizacao.
        """
        if self._line_nums is None:
            return
        matches = np.where(self._line_nums == line_number)[0]
        if len(matches) > 0:
            self._highlighted_seg = int(matches[0])
        else:
            # Procura a linha mais proxima (anterior)
            candidates = np.where(self._line_nums <= line_number)[0]
            self._highlighted_seg = int(candidates[-1]) if len(candidates) > 0 else None
        self._dirty = True

    def clear_highlight(self):
        self._highlighted_seg = None
        self._dirty = True

    # ────────────────────────────────────────────────────────────────────────
    # Simulacao
    # ────────────────────────────────────────────────────────────────────────

    def iniciar_simulacao(self):
        if self.model is None:
            return
        if self._sim_index < 0:
            self._sim_index = 0
        self._sim_running = True
        self._sim_timer.start(self._sim_speed_ms)

    def parar_simulacao(self):
        self._sim_running = False
        self._sim_timer.stop()

    def retroceder_simulacao(self):
        self.parar_simulacao()
        if self._sim_index > 0:
            self._sim_index -= 1
        self._notify_segment()
        self._dirty = True

    def resetar_simulacao(self):
        self.parar_simulacao()
        self._sim_index = -1
        self._dirty = True

    def set_sim_speed(self, ms: int):
        self._sim_speed_ms = max(1, ms)
        if self._sim_running:
            self._sim_timer.setInterval(self._sim_speed_ms)

    def _sim_step(self):
        if self.model is None:
            self.parar_simulacao()
            return
        n = len(self.model.segments)
        if self._sim_index >= n - 1:
            self.parar_simulacao()
            self._sim_index = n - 1
        else:
            self._sim_index += 1
        self._notify_segment()
        self._dirty = True

    def _notify_segment(self):
        if self.on_segment_changed and self.model and 0 <= self._sim_index < len(self.model.segments):
            seg = self.model.segments[self._sim_index]
            self.on_segment_changed(seg)

    # ────────────────────────────────────────────────────────────────────────
    # Camadas
    # ────────────────────────────────────────────────────────────────────────

    def set_layer(self, layer_index: int):
        self.current_layer = layer_index
        self._dirty = True

    def layer_anterior(self):
        if self.model is None:
            return
        max_layer = self.model.layer_count - 1
        if self.current_layer < 0:
            self.current_layer = max_layer
        elif self.current_layer > 0:
            self.current_layer -= 1
        self._dirty = True
        return self.current_layer

    def layer_seguinte(self):
        if self.model is None:
            return
        max_layer = self.model.layer_count - 1
        if self.current_layer < 0:
            self.current_layer = 0
        elif self.current_layer < max_layer:
            self.current_layer += 1
        self._dirty = True
        return self.current_layer

    # ────────────────────────────────────────────────────────────────────────
    # Trackball + inercia
    # ────────────────────────────────────────────────────────────────────────

    def _trackball_rotate(self, dx: float, dy: float):
        sensitivity = 0.004
        angle_yaw   =  dx * sensitivity
        angle_pitch = -dy * sensitivity

        cos_y, sin_y = math.cos(angle_yaw), math.sin(angle_yaw)
        Ry = np.array([
            [ cos_y, 0, sin_y],
            [     0, 1,     0],
            [-sin_y, 0, cos_y],
        ])
        right = self._rot[0, :]
        right = right / (np.linalg.norm(right) + 1e-10)
        Rx = self._axis_angle_matrix(right, angle_pitch)
        self._rot = Ry @ Rx @ self._rot
        self._rot = self._orthonormalize(self._rot)
        # Atualiza o gizmo tambem
        self._axis_widget.update()

    @staticmethod
    def _axis_angle_matrix(axis: np.ndarray, angle: float) -> np.ndarray:
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
        r0 = R[0] / (np.linalg.norm(R[0]) + 1e-10)
        r1 = R[1] - np.dot(R[1], r0) * r0
        r1 = r1   / (np.linalg.norm(r1) + 1e-10)
        r2 = np.cross(r0, r1)
        return np.array([r0, r1, r2])

    # ────────────────────────────────────────────────────────────────────────
    # Camera
    # ────────────────────────────────────────────────────────────────────────

    def _update_camera(self):
        if self.camera is None:
            return
        right   = self._rot[0]
        up      = self._rot[1]
        fwd_inv = self._rot[2]
        forward = -fwd_inv
        cam_pos = self._target + fwd_inv * self._orbit_dist
        self.camera.position = np.array([cam_pos[0], cam_pos[1], cam_pos[2], 1.0])
        self.camera.forward  = np.array([forward[0], forward[1], forward[2], 1.0])
        self.camera.right    = np.array([right[0],   right[1],   right[2],   1.0])
        self.camera.up       = np.array([up[0],      up[1],      up[2],      1.0])

    # ────────────────────────────────────────────────────────────────────────
    # Timer
    # ────────────────────────────────────────────────────────────────────────

    def _on_timer(self):
        if not self._dragging and (abs(self._vel_dx) > 0.05 or abs(self._vel_dy) > 0.05):
            self._trackball_rotate(self._vel_dx, self._vel_dy)
            self._vel_dx *= self._INERTIA
            self._vel_dy *= self._INERTIA
            self._update_camera()
            self._dirty = True

        if self._dirty:
            self.update()
            self._dirty = False

    # ────────────────────────────────────────────────────────────────────────
    # Renderizacao
    # ────────────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        if self.model is None or self._verts_start is None:
            painter = QPainter(self)
            painter.fillRect(self.rect(), self.color_background)
            hint_color = QColor(180, 180, 200) if self.color_background.lightness() > 128 else QColor(80, 80, 100)
            painter.setPen(QPen(hint_color))
            painter.setFont(QFont("Consolas", 11))
            painter.drawText(self.rect(), Qt.AlignCenter, "Importe um arquivo GCode para comecar")
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), self.color_background)
        self._draw_segments_batched(painter)
        self._draw_hint(painter)

    def _draw_hint(self, painter):
        hint_color = QColor(100, 100, 120) if self.color_background.lightness() < 128 else QColor(120, 120, 140)
        painter.setPen(QPen(hint_color))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(8, self.height() - 8,
            "Esq: orbitar  |  Scroll: zoom  |  Meio: pan  |  F: centralizar")

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

        total = len(self._verts_start)

        # Filtro por camada
        if self.current_layer >= 0:
            if self.layer_isolated:
                # Mostra SOMENTE a camada atual, sem inferiores
                layer_mask = self._layers_arr == self.current_layer
            else:
                # Mostra camada atual + inferiores (apagadas)
                layer_mask = self._layers_arr == self.current_layer
        else:
            layer_mask = np.ones(total, dtype=bool)

        # Filtro por simulacao
        if self._sim_index >= 0:
            sim_done    = np.arange(total) <= self._sim_index
            sim_pending = np.arange(total) >  self._sim_index
        else:
            sim_done    = np.ones(total,  dtype=bool)
            sim_pending = np.zeros(total, dtype=bool)

        pts0, valid0 = self._project_batch(self._verts_start)
        pts1, valid1 = self._project_batch(self._verts_end)
        valid = valid0 & valid1

        def draw_group(mask, color, width=1):
            m = mask & valid
            if not np.any(m):
                return
            painter.setPen(QPen(color, width))
            for i in np.where(m)[0]:
                painter.drawLine(int(pts0[i,0]), int(pts0[i,1]),
                                 int(pts1[i,0]), int(pts1[i,1]))

        extrude = self._types == 1
        travel  = self._types == 0

        # Camadas inferiores apagadas (apenas quando nao isolado)
        if self.current_layer >= 0 and not self.layer_isolated:
            older = self._layers_arr < self.current_layer
            draw_group(older & extrude, QColor(80, 60, 30))
            if self.show_travel:
                draw_group(older & travel, QColor(30, 30, 60))

        # Pendentes da simulacao
        if self._sim_index >= 0:
            draw_group(layer_mask & extrude & sim_pending, QColor(60, 45, 20))
            if self.show_travel:
                draw_group(layer_mask & travel & sim_pending, QColor(25, 25, 50))

        # Completos
        if self.show_travel:
            draw_group(layer_mask & travel & sim_done, self.color_travel)
        draw_group(layer_mask & extrude & sim_done, self.color_extrude)

        # Segmento atual da simulacao
        if 0 <= self._sim_index < total:
            i = self._sim_index
            if valid[i]:
                painter.setPen(QPen(QColor(255, 255, 100), 2))
                painter.drawLine(int(pts0[i,0]), int(pts0[i,1]),
                                 int(pts1[i,0]), int(pts1[i,1]))

        # Segmento destacado por selecao no codigo
        if self._highlighted_seg is not None:
            hi = self._highlighted_seg
            if 0 <= hi < total and valid[hi]:
                # Ponto inicial destacado (circulo)
                painter.setPen(QPen(QColor(0, 220, 255), 2))
                painter.setBrush(QBrush(QColor(0, 220, 255, 180)))
                r = 5
                painter.drawEllipse(pts0[hi,0]-r, pts0[hi,1]-r, r*2, r*2)
                # Linha destacada
                painter.setPen(QPen(QColor(0, 220, 255), 3))
                painter.setBrush(Qt.NoBrush)
                painter.drawLine(int(pts0[hi,0]), int(pts0[hi,1]),
                                 int(pts1[hi,0]), int(pts1[hi,1]))
                # Ponto final
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(255, 80, 80, 200)))
                painter.drawEllipse(pts1[hi,0]-r, pts1[hi,1]-r, r*2, r*2)

    # ────────────────────────────────────────────────────────────────────────
    # Mouse
    # ────────────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        self.setFocus()
        self._mouse_last   = event.pos()
        self._mouse_button = event.button()
        self._dragging     = True
        self._vel_dx = 0.0
        self._vel_dy = 0.0

    def mouseReleaseEvent(self, event):
        self._mouse_button = None
        self._dragging     = False
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
            self._vel_dx = dx * 0.6
            self._vel_dy = dy * 0.6
        elif self._mouse_button == Qt.MiddleButton:
            self.setCursor(QCursor(Qt.SizeAllCursor))
            pan   = self._orbit_dist * 0.001
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
        if   key == Qt.Key_Left:  self._trackball_rotate(-10,  0)
        elif key == Qt.Key_Right: self._trackball_rotate( 10,  0)
        elif key == Qt.Key_Up:    self._trackball_rotate(  0, 10)
        elif key == Qt.Key_Down:  self._trackball_rotate(  0,-10)
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self._orbit_dist = max(self._MIN_DIST, self._orbit_dist * 0.9)
        elif key == Qt.Key_Minus:
            self._orbit_dist = min(self._MAX_DIST, self._orbit_dist * 1.1)
        else:
            changed = False
        if changed:
            self._update_camera()
            self._dirty = True
