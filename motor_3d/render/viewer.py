from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QCursor, QFont, QBrush
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QLine
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

    def leaveEvent(self, event):
        self._hovered = None
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
        self.on_layer_changed   = None  # callback(layer_index) para auto-camada

        # ── Camera orbital ───────────────────────────────────────────────────
        self._target     = np.array([0.0, 0.0, 0.0])
        self._orbit_dist = 150.0
        self._MIN_DIST   = 1.0
        self._MAX_DIST   = 5000.0
        self._rot        = self._make_initial_rotation()

        # ── Inercia ──────────────────────────────────────────────────────────
        self._dragging = False

        # ── Mouse ────────────────────────────────────────────────────────────
        self._mouse_last   = QPoint()
        self._mouse_button = None
        self._last_mouse_pos = None

        # ── Timers ───────────────────────────────────────────────────────────
        self._dirty = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._timer.start(16)

        self._sim_timer    = QTimer(self)
        self._sim_timer.timeout.connect(self._sim_step)
        self._sim_speed_ms = 50
        self._sim_running  = False

        # Simulacao reversa
        self._rev_timer   = QTimer(self)
        self._rev_timer.timeout.connect(self._rev_step)
        self._rev_running = False

        # Acompanhamento automatico de camada
        self.auto_layer   = False

        # ── Cores (alteradas por tema/config) ────────────────────────────────
        self.show_travel      = True
        self.dark_mode        = True
        self.color_travel     = QColor(220, 60, 60)    # vermelho G0
        self.color_extrude    = QColor(34, 103, 252)   # azul G1 (#2267fc)

        # Cores das linhas ainda nao lidas (pendentes/apagadas) — ajustadas por tema
        self.color_extrude_dim  = QColor(15, 38, 85)    # G1 pendente (padrao dark)
        self.color_travel_dim   = QColor(80, 20, 20)    # G0 pendente (padrao dark)
        self.color_extrude_old  = QColor(20, 50, 110)   # G1 camada inferior (padrao dark)
        self.color_travel_old   = QColor(100, 25, 25)   # G0 camada inferior (padrao dark)
        self.color_background = QColor(22, 22, 32)

        self.setFocusPolicy(Qt.StrongFocus)

        # ── Gizmo de eixos ───────────────────────────────────────────────────
        self._axis_widget = AxisWidget(self, self)
        self._axis_widget.raise_()

    # ────────────────────────────────────────────────────────────────────────
    # Ponta da Tocha
    # ────────────────────────────────────────────────────────────────────────    

    def _draw_torch_head(self, painter, pos_3d):
        """Desenha uma tocha 3D (cilindro + cone) na posição especificada."""
        # Configurações da Tocha (em mm)
        r = 5           # Raio do corpo
        h_cone = 10     # Altura da ponta cônica
        h_cyl = 35      # Altura do corpo cilíndrico
        segments = 32    # Resolução (8 lados para visual profissional/técnico)

        # 1. Definir vértices locais (relativos à ponta 0,0,0)
        # Ponta da tocha (onde a solda ocorre)
        tip = np.array([0, 0, 0, 1])
        
        # Base do cone / Início do cilindro
        cone_base = []
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            cone_base.append([r * math.cos(angle), r * math.sin(angle), h_cone, 1])
        
        # Topo do cilindro
        cyl_top = []
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            cyl_top.append([r * math.cos(angle), r * math.sin(angle), h_cone + h_cyl, 1])

        # 2. Transladar para a posição real da peça
        all_verts = np.array([tip] + cone_base + cyl_top)
        all_verts[:, 0] += pos_3d[0]
        all_verts[:, 1] += pos_3d[1]
        all_verts[:, 2] += pos_3d[2]

        # 3. Projetar para a tela
        pts_2d, valid = self._project_batch(all_verts)
        if not np.all(valid): return

        # Cores da Tocha (Metálico/Cinza)
        color_body = QColor(100, 100, 110, 90)
        color_tip = QColor(100, 100, 110, 90)
        
        # 4. Desenhar Faces (Cone e Cilindro)
        painter.setPen(Qt.NoPen)
        
        # Faces do Cone (triângulos da ponta até a base circular)
        p_tip = QPoint(pts_2d[0,0], pts_2d[0,1])
        for i in range(segments):
            next_i = (i + 1) % segments + 1
            poly = [p_tip, QPoint(pts_2d[i+1,0], pts_2d[i+1,1]), QPoint(pts_2d[next_i,0], pts_2d[next_i,1])]
            painter.setBrush(QBrush(color_tip))
            painter.drawPolygon(*poly)

        # Faces do Cilindro (quadriláteros entre as duas circunferências)
        for i in range(segments):
            idx = i + 1
            next_idx = (i + 1) % segments + 1
            top_idx = idx + segments
            next_top_idx = next_idx + segments
            
            poly = [
                QPoint(pts_2d[idx,0], pts_2d[idx,1]), QPoint(pts_2d[next_idx,0], pts_2d[next_idx,1]),
                QPoint(pts_2d[next_top_idx,0], pts_2d[next_top_idx,1]), QPoint(pts_2d[top_idx,0], pts_2d[top_idx,1])
            ]
            painter.setBrush(QBrush(color_body))
            painter.drawPolygon(*poly)

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
        pitch = math.radians(-30)
        yaw   = math.radians(-30)
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

    def set_model(self, model: GCodeModel, preserve_camera=False):
        self.model = model
        self._sim_index       = -1
        self._highlighted_seg = None
        self._sim_running     = False
        self._sim_timer.stop()
        self.current_layer    = -1 
        self.layer_isolated   = False

        if not preserve_camera or self.camera is None:
            W = max(self.width(),  1)
            H = max(self.height(), 1)
            self.camera     = Camera(W, H)
            self.projection = Projection(self.camera, W, H)
            self._fit_view()

        self._precompute_geometry()
        self._reposition_gizmo()
        self._dirty = True

    def _precompute_geometry(self):
        # 1. Processa os segmentos da peça (G1/G0)
        segs = self.model.segments
        if segs:
            starts = np.array([s.start for s in segs], dtype=np.float64)
            ends   = np.array([s.end   for s in segs], dtype=np.float64)
            ones   = np.ones((len(segs), 1), dtype=np.float64)
            self._verts_start = np.hstack([starts, ones])
            self._verts_end   = np.hstack([ends,   ones])
            self._types       = np.array([0 if s.type == 'travel' else 1 for s in segs])
            self._layers_arr  = np.array([s.layer for s in segs])
            self._line_nums   = np.array([s.line_number for s in segs])

        # 2. Processa os segmentos do GRID (Bancada)
        # É aqui que a atualização do tamanho acontece!
        grid = self.model.grid_segments
        if grid:
            g_starts = np.array([s.start for s in grid], dtype=np.float64)
            g_ends   = np.array([s.end   for s in grid], dtype=np.float64)
            g_ones   = np.ones((len(grid), 1), dtype=np.float64)
            self._grid_v_start = np.hstack([g_starts, g_ones])
            self._grid_v_end   = np.hstack([g_ends, g_ones])
        else:
            self._grid_v_start = None
            self._grid_v_end   = None

    def _fit_view(self):
        self.camera.yaw = math.radians(-45)
        self.camera.pitch = math.radians(30)
        if self.model is None or not self.model.bounds:
            # Se não houver peça, foca no centro do grid de 500mm
            self.camera.target = np.array([0.0, 0.0, 0.0])
            self.camera.distance = 700.0
        else:
            # Foca no centro da peça (Cilindro no Laprosolda)
            xmin, ymin, zmin, xmax, ymax, zmax = self.model.bounds
            center = np.array([
                (xmin + xmax) / 2,
                (ymin + ymax) / 2,
                (zmin + zmax) / 2
            ])
            self.camera.target = center
            
            # Calcula distância ideal baseada no tamanho da peça
            size = max(xmax - xmin, ymax - ymin, zmax - zmin)
            self.camera.distance = size * 2.5 # Margem de segurança

        # MUITO IMPORTANTE: Sincroniza a posição após mudar o alvo/distância
        self.camera.update_position()
        self.update()

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
        self._rev_running = False
        self._rev_timer.stop()
        if self._sim_index < 0:
            self._sim_index = 0
        self._sim_running = True
        self._sim_timer.start(self._sim_speed_ms)

    def parar_simulacao(self):
        self._sim_running = False
        self._sim_timer.stop()

    def iniciar_reverso(self):
        """Inicia simulacao reversa a partir do indice atual."""
        if self.model is None:
            return
        self.parar_simulacao()
        if self._sim_index < 0:
            self._sim_index = len(self.model.segments) - 1
        self._rev_running = True
        self._rev_timer.start(self._sim_speed_ms)

    def parar_reverso(self):
        self._rev_running = False
        self._rev_timer.stop()

    def retroceder_simulacao(self):
        """Volta uma linha e inicia simulacao reversa a partir dali."""
        self.parar_simulacao()
        self.parar_reverso()
        if self._sim_index > 0:
            self._sim_index -= 1
        elif self._sim_index < 0 and self.model:
            self._sim_index = len(self.model.segments) - 1
        self._notify_segment()
        self._dirty = True
        self._rev_running = True
        self._rev_timer.start(self._sim_speed_ms)

    def resetar_simulacao(self):
        self.parar_simulacao()
        self.parar_reverso()
        self._sim_index = -1
        self._dirty = True

    def set_sim_speed(self, ms: int):
        self._sim_speed_ms = max(1, ms)
        if self._sim_running:
            self._sim_timer.setInterval(self._sim_speed_ms)
        if self._rev_running:
            self._rev_timer.setInterval(self._sim_speed_ms)

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

    def _rev_step(self):
        """Passo da simulacao reversa."""
        if self.model is None:
            self.parar_reverso()
            return
        if self._sim_index <= 0:
            self.parar_reverso()
            self._sim_index = 0
        else:
            self._sim_index -= 1
        self._notify_segment()
        self._dirty = True

    def _notify_segment(self):
        if self.on_segment_changed and self.model and 0 <= self._sim_index < len(self.model.segments):
            seg = self.model.segments[self._sim_index]
            # Auto-camada: troca de layer ao detectar mudanca de Z
            if self.auto_layer and self.current_layer >= 0:
                if seg.layer != self.current_layer:
                    self.current_layer = seg.layer
                    if self.on_layer_changed:
                        self.on_layer_changed(self.current_layer)
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
        v_cam = verts @ cam_mat
        v = v_cam @ proj_mat
        w = v[:, -1:].copy()
        valid = w.flatten() > self.camera.near_plane
        w[w < 1e-6] = 1e-6 
        v = v / w
        v = v @ scr_mat
        v_safe = np.nan_to_num(v[:, :2], nan=0.0, posinf=30000.0, neginf=-30000.0)
        with np.errstate(invalid='ignore', over='ignore'):
            v_int = np.clip(v_safe, -30000, 30000).astype(np.int32)
        return v_int, valid

    def _draw_segments_batched(self, painter: QPainter):
        # --- DESENHO DA GRADE DA BANCADA ---
        if hasattr(self, '_grid_v_start'):
            g_pts0, g_valid0 = self._project_batch(self._grid_v_start)
            g_pts1, g_valid1 = self._project_batch(self._grid_v_end)
            g_valid = g_valid0 & g_valid1
            
            # Lógica de cores aprimorada para visibilidade
            if self.dark_mode:
                # No modo escuro: Linhas contínuas e mais claras (cinza azulado suave)
                grid_color = QColor(100, 100, 120, 150) # Aumentamos a opacidade e brilho
            else:
                # No modo claro: Linhas contínuas e mais escuras (contraste com fundo branco/claro)
                grid_color = QColor(160, 160, 180, 200) 
            
            # Configuração da caneta: Qt.SolidLine para linha contínua
            pen = QPen(grid_color, 1, Qt.SolidLine)
            painter.setPen(pen)
        
        for i in range(len(self._grid_v_start)):
            if g_valid[i]:
                painter.drawLine(
                    int(g_pts0[i,0]), int(g_pts0[i,1]), 
                    int(g_pts1[i,0]), int(g_pts1[i,1])
                )

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
            indices = np.where(m)[0]
            lines = [
                QLine(int(pts0[i,0]), int(pts0[i,1]), int(pts1[i,0]), int(pts1[i,1])) 
                for i in indices
            ]
            painter.drawLines(lines)

        extrude = self._types == 1
        travel  = self._types == 0

        # Camadas inferiores apagadas (apenas quando nao isolado)
        if self.current_layer >= 0 and not self.layer_isolated:
            older = self._layers_arr < self.current_layer
            draw_group(older & extrude, self.color_extrude_old)
            if self.show_travel:
                draw_group(older & travel, self.color_travel_old)

        # Pendentes da simulacao
        if self._sim_index >= 0:
            draw_group(layer_mask & extrude & sim_pending, self.color_extrude_dim)
            if self.show_travel:
                draw_group(layer_mask & travel & sim_pending, self.color_travel_dim)

        # Completos
        if self.show_travel:
            draw_group(layer_mask & travel & sim_done, self.color_travel)
        draw_group(layer_mask & extrude & sim_done, self.color_extrude)

        # Segmento atual da simulacao
        if self._highlighted_seg is not None:
                hi = self._highlighted_seg
                if 0 <= hi < total and valid[hi]:
                    # Destaque da linha selecionada (Ciano/Azul claro, espessura 3)
                    painter.setPen(QPen(QColor(0, 220, 255), 3, Qt.SolidLine))
                    painter.drawLine(int(pts0[hi,0]), int(pts0[hi,1]), 
                                    int(pts1[hi,0]), int(pts1[hi,1]))
                    
                    # Desenha a tocha no ponto final da linha selecionada
                    self._draw_torch_head(painter, self.model.segments[hi].end)
            
            # 2. Destaque da Simulação Independente (Pausado/Rodando)
        if 0 <= self._sim_index < total:
            i = self._sim_index
            if valid[i]:
                # Destaque da linha de simulação (Amarelo brilhante, espessura 3)
                painter.setPen(QPen(QColor(255, 255, 50), 3, Qt.SolidLine))
                painter.drawLine(int(pts0[i,0]), int(pts0[i,1]), 
                                int(pts1[i,0]), int(pts1[i,1]))
                
                # Desenha a tocha no ponto final (destino) da simulação
                self._draw_torch_head(painter, self.model.segments[i].end)

    # ────────────────────────────────────────────────────────────────────────
    # Mouse
    # ────────────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        self._last_mouse_pos = event.pos()
        super().mousePressEvent(event)
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
        if self._last_mouse_pos is None:
            self._last_mouse_pos = event.pos()
            return
        if event.buttons() == Qt.NoButton:
            return

        dx = event.x() - self._last_mouse_pos.x()
        dy = event.y() - self._last_mouse_pos.y()
        
        # Botão Esquerdo: Orbita (Gira ao redor do objeto)
        if event.buttons() & Qt.LeftButton:
            sensitivity = 0.005
            self.camera.yaw += dx * sensitivity
            self.camera.pitch -= dy * sensitivity # Invertido para ser intuitivo
            
            # Trava para não "dar a volta" por cima do objeto
            limit = math.radians(89)
            self.camera.pitch = max(-limit, min(limit, self.camera.pitch))
            
        # Botão Direito ou Meio: Pan (Move o Alvo)
        elif event.buttons() & Qt.MidButton:
            pan_sensitivity = self.camera.distance * 0.001
            
            # 1. Descobre a direção exata para onde a lente está olhando
            forward = self.camera.target - self.camera.position[:3]
            forward = forward / np.linalg.norm(forward)
            
            # 2. Usa Produto Vetorial (Cross Product) para achar a "Direita" e "Cima" da tela
            world_up = np.array([0, 0, 1])
            right = np.cross(world_up, forward)
            
            # Prevenção matemática caso olhe perfeitamente de cima para baixo
            if np.linalg.norm(right) < 1e-6:
                right = np.array([1, 0, 0])
            else:
                right = right / np.linalg.norm(right)
                
            screen_up = np.cross(forward, right)
            screen_up = screen_up / np.linalg.norm(screen_up)
            
            # 3. Move o alvo usando apenas os eixos paralelos ao seu monitor
            # Invertemos os sinais para dar o efeito mecânico de "agarrar e puxar" a peça
            self.camera.target -= right * dx * pan_sensitivity
            self.camera.target += screen_up * dy * pan_sensitivity

        self.camera.update_position()
        self._last_mouse_pos = event.pos()
        self.update()

    def wheelEvent(self, event):
        # Scroll: Zoom (Altera a distância orbital)
        zoom_speed = 1.2
        if event.angleDelta().y() > 0:
            self.camera.distance /= zoom_speed
        else:
            self.camera.distance *= zoom_speed
            
        self.camera.update_position()
        self.update()

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

    def set_simulation_from_line(self, line_number: int):
        """
        Define o ponto inicial da simulação baseado na linha do GCode.
        """
        if self._line_nums is None:
            return

        matches = np.where(self._line_nums == line_number)[0]

        if len(matches) > 0:
            self._sim_index = int(matches[0])
        else:
            # pega o mais próximo anterior
            candidates = np.where(self._line_nums <= line_number)[0]
            if len(candidates) > 0:
                self._sim_index = int(candidates[-1])
            else:
                self._sim_index = 0

        self._notify_segment()
        self._dirty = True