from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QCursor, QFont, QBrush, QPolygon, QPixmap, QTransform, QPolygonF
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QLine, QPointF, pyqtSignal
import time
import numpy as np
import math
from .camera import Camera
from .projection import Projection
from ..gcode_model import GCodeModel

class ViewCubeWidget(QWidget):
    """
    Widget interativo de View Cube 3D com Texturas Mapeadas em Perspectiva.
    """
    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.SIZE = 120
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        
        self._hovered_part = None 
        self._texture_cache = {} # Cache para as texturas geradas

        self.targets = {}
        for x in [-1, 0, 1]:
            for y in [-1, 0, 1]:
                for z in [-1, 0, 1]:
                    if x == 0 and y == 0 and z == 0: continue
                    self.targets[(x, y, z)] = np.array([x, y, z], dtype=float)

        S = 26
        self.v = np.array([
            [ S, -S,  S], [ S,  S,  S], [-S,  S,  S], [-S, -S,  S], 
            [ S, -S, -S], [ S,  S, -S], [-S,  S, -S], [-S, -S, -S]  
        ])
        
        # Ordem corrigida do Mapeamento UV: [Topo-Esq, Topo-Dir, Baixo-Dir, Baixo-Esq]
        # Agora respeitando o vetor 'Right' da câmera para não espelhar o texto
        self.faces = [
            ([3, 0, 1, 2], 'TOP',   (0, 0, 1)),
            ([6, 5, 4, 7], 'BASE',   (0, 0, -1)),
            ([1, 0, 4, 5], 'RIGHT',    (1, 0, 0)),
            ([3, 2, 6, 7], 'LEFT',    (-1, 0, 0)),
            ([2, 1, 5, 6], 'BACK',   (0, 1, 0)),
            ([0, 3, 7, 4], 'FRONT', (0, -1, 0)),
        ]

    def _get_face_texture(self, label, is_hovered):
        """Gera e guarda em memória uma textura plana para a face do cubo."""
        key = (label, is_hovered)
        if key in self._texture_cache:
            return self._texture_cache[key]

        size = 128 # Resolução da textura interna
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)

        bg_color = QColor(140, 180, 255) if is_hovered else QColor(220, 220, 230)
        p.setBrush(QBrush(bg_color))
        
        # Desenha a "moldura" da face
        p.setPen(QPen(QColor(100, 100, 110), 6, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
        p.drawRect(0, 0, size, size)

        # Desenha o Texto centralizado
        p.setPen(QColor(40, 40, 50))
        p.setFont(QFont("Consolas", 26, QFont.Bold))
        p.drawText(QRect(0, 0, size, size), Qt.AlignCenter, label)
        p.end()

        self._texture_cache[key] = pixmap
        return pixmap

    def paintEvent(self, event):
        if self.viewer.camera is None: return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx, cy = self.width() / 2, self.height() / 2 - 10
        
        painter.setBrush(QBrush(QColor(20, 20, 35, 100)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(10, 0, self.SIZE-20, self.SIZE-20)

        R = self.viewer.camera.camera_matrix()[:3, :3]
        self._draw_mini_axes(painter, R)

        v_cam = self.v @ R
        centers = []
        for idx, (verts, label, norm) in enumerate(self.faces):
            center_cam = np.mean(v_cam[verts], axis=0)
            centers.append((center_cam[2], idx)) 
            
        centers.sort(key=lambda x: x[0], reverse=True)

        # 4 Cantos da nossa Textura original plana (128x128 pixels)
        square = QPolygonF([
            QPointF(0, 0), QPointF(128, 0),
            QPointF(128, 128), QPointF(0, 128)
        ])

        for depth, idx in centers:
            verts, label, norm = self.faces[idx]
            n_cam = np.array(norm) @ R

            # Backface culling (só desenha se estiver virada para a câmera)
            if n_cam[2] < 0.1: 
                is_face_hovered = (self._hovered_part == norm)
                
                # Coleta os 4 pontos projetados (Float para precisão matemática)
                polygon_f = QPolygonF()
                for vi in verts:
                    x = cx + v_cam[vi, 0]
                    y = cy - v_cam[vi, 1]
                    polygon_f.append(QPointF(x, y))

                # --- MÁGICA DA PERSPECTIVA (Quad-to-Quad) ---
                transform = QTransform()
                if QTransform.quadToQuad(square, polygon_f, transform):
                    painter.save()
                    # Aplica a matriz de distorção no "pincel"
                    painter.setTransform(transform)
                    
                    # Desenha a imagem plana, que sairá distorcida automaticamente
                    pixmap = self._get_face_texture(label, is_face_hovered)
                    painter.drawPixmap(0, 0, pixmap)
                    painter.restore()

                    # Iluminação: Desenha uma sombra semi-transparente por cima da textura
                    if not is_face_hovered:
                        light_dir = np.array([0.4, 0.4, -0.8])
                        intensity = max(0.0, min(1.0, np.dot(n_cam, light_dir)))
                        
                        # Quanto menor a luz, maior o Alpha (mais preto)
                        shadow_alpha = int(255 * (1.0 - (0.4 + 0.6 * intensity)))
                        painter.setBrush(QBrush(QColor(0, 0, 0, shadow_alpha)))
                        painter.setPen(Qt.NoPen)
                        
                        # Para desenhar a sombra, voltamos para QPolygon inteiro
                        poly_int = QPolygon([QPoint(int(p.x()), int(p.y())) for p in polygon_f])
                        painter.drawPolygon(poly_int)

        # Highlight de Arestas e Vértices
        if self._hovered_part and self._hovered_part.count(0) < 2:
            h_vec = np.array(self._hovered_part, dtype=float) * 26
            h_cam = h_vec @ R
            hx2d = cx + h_cam[0]
            hy2d = cy - h_cam[1]

            painter.setBrush(QBrush(QColor(100, 150, 255, 180)))
            painter.setPen(Qt.NoPen)
            if self._hovered_part.count(0) == 1: 
                painter.drawEllipse(int(hx2d)-6, int(hy2d)-6, 12, 12)
            else: 
                painter.drawEllipse(int(hx2d)-5, int(hy2d)-5, 10, 10)

    def _draw_mini_axes(self, painter, R):
        ax_cx, ax_cy = 20, self.height() - 20
        L = 14
        axes = [
            (np.array([1, 0, 0]), QColor(220, 60, 60), 'X'),
            (np.array([0, 1, 0]), QColor(60, 200, 60), 'Y'),
            (np.array([0, 0, 1]), QColor(60, 110, 220), 'Z')
        ]
        
        axes_proj = []
        for vec, color, name in axes:
            v_cam = vec @ R
            axes_proj.append((v_cam[2], v_cam, color, name))
        axes_proj.sort(key=lambda x: x[0], reverse=True)

        for depth, v_cam, color, name in axes_proj:
            ex = ax_cx + v_cam[0] * L
            ey = ax_cy - v_cam[1] * L
            painter.setPen(QPen(color, 2, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(ax_cx, ax_cy, int(ex), int(ey))

    def mouseMoveEvent(self, event):
        if self.viewer.camera is None: return
        
        mx, my = event.x(), event.y()
        best_dist = 20 
        best_target = None

        R = self.viewer.camera.camera_matrix()[:3, :3]
        cx, cy = self.width() / 2, self.height() / 2 - 10
        S = 26

        for key, vec in self.targets.items():
            surf_p = vec * S
            v_cam = surf_p @ R

            if v_cam[2] > 5: 
                continue

            x2d = cx + v_cam[0]
            y2d = cy - v_cam[1]

            dist = math.hypot(mx - x2d, my - y2d)
            if dist < best_dist:
                best_dist = dist
                best_target = key

        if self._hovered_part != best_target:
            self._hovered_part = best_target
            self.setCursor(QCursor(Qt.PointingHandCursor if best_target else Qt.ArrowCursor))
            self.update()

    def mousePressEvent(self, event):
        if self._hovered_part and event.button() == Qt.LeftButton:
            x, y, z = self._hovered_part
            D = np.array([x, y, z], dtype=float)
            norm = np.linalg.norm(D)
            if norm < 1e-6: return

            pitch = math.asin(D[2] / norm)
            yaw = math.atan2(D[0], D[1])

            self.viewer.animate_camera_to(yaw, pitch)

    def leaveEvent(self, event):
        self._hovered_part = None
        self.setCursor(QCursor(Qt.ArrowCursor))
        self.update()


class GCodeViewer3D(QWidget):
    fps_changed = pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)

        self.substrate_enabled = False
        self.substrate_w = 100
        self.substrate_d = 100
        self.substrate_h = 5.0

        self.model         = None
        self.camera        = None
        self.projection    = None
        self.current_layer = -1   
        self.layer_isolated = False  

        self._verts_start = None
        self._verts_end   = None
        self._types       = None
        self._layers_arr  = None
        self._line_nums   = None   

        self._sim_index   = -1
        self._highlighted_seg = None  

        self.on_segment_changed = None
        self.on_layer_changed   = None  

        self._target     = np.array([0.0, 0.0, 0.0])
        self._orbit_dist = 150.0
        self._MIN_DIST   = 1.0
        self._MAX_DIST   = 5000.0

        self._dragging = False

        self._mouse_last   = QPoint()
        self._mouse_button = None
        self._last_mouse_pos = None

        self._dirty = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._timer.start(16)

        self._sim_timer    = QTimer(self)
        self._sim_timer.timeout.connect(self._sim_step)
        self._sim_speed_ms = 50
        self._sim_running  = False

        self._rev_timer   = QTimer(self)
        self._rev_timer.timeout.connect(self._rev_step)
        self._rev_running = False

        self.auto_layer   = False

        self.show_travel      = True
        self.dark_mode        = True
        self.color_travel     = QColor(220, 60, 60)    
        self.color_extrude    = QColor(34, 103, 252)   

        self.color_extrude_dim  = QColor(15, 38, 85)    
        self.color_travel_dim   = QColor(80, 20, 20)    
        self.color_extrude_old  = QColor(20, 50, 110)   
        self.color_travel_old   = QColor(100, 25, 25)   
        self.color_background = QColor(22, 22, 32)

        self.setFocusPolicy(Qt.StrongFocus)  

        # Guarda a geometria estática da tocha na RAM
        self._torch_verts = self._generate_torch_geometry()

        self._frame_count = 0
        self._last_fps_time = time.time()
        self._current_fps = 0.0

        # ── View Cube Inteiriço ──────────────────────────────────────────────
        self._axis_widget = ViewCubeWidget(self, self)
        self._axis_widget.raise_()

    def _generate_torch_geometry(self):
        """OTIMIZAÇÃO O(1): Calcula os 64 vértices da tocha uma única vez."""
        r, h_cone, h_cyl, segments = 5, 10, 35, 32
        tip = [0, 0, 0, 1]
        cone_base = [[r * math.cos(2 * math.pi * i / segments), r * math.sin(2 * math.pi * i / segments), h_cone, 1] for i in range(segments)]
        cyl_top = [[r * math.cos(2 * math.pi * i / segments), r * math.sin(2 * math.pi * i / segments), h_cone + h_cyl, 1] for i in range(segments)]
        return np.array([tip] + cone_base + cyl_top)

    # ────────────────────────────────────────────────────────────────────────
    # Animação de Câmera (View Cube)
    # ────────────────────────────────────────────────────────────────────────
    
    def animate_camera_to(self, target_yaw, target_pitch):
        self._anim_start_yaw = self.camera.yaw
        self._anim_start_pitch = self.camera.pitch

        # Calcula o caminho mais curto na rotação
        dy = (target_yaw - self._anim_start_yaw)
        dy = (dy + math.pi) % (2 * math.pi) - math.pi
        self._anim_target_yaw = self._anim_start_yaw + dy

        self._anim_target_pitch = target_pitch
        self._anim_progress = 0.0

        if not hasattr(self, '_anim_timer'):
            self._anim_timer = QTimer(self)
            self._anim_timer.timeout.connect(self._anim_step)
        self._anim_timer.start(16)

    def _anim_step(self):
        self._anim_progress += 0.06 # Velocidade da animação
        if self._anim_progress >= 1.0:
            self.camera.yaw = self._anim_target_yaw
            self.camera.pitch = self._anim_target_pitch
            self.camera.update_position()
            self._dirty = True
            self._anim_timer.stop()
        else:
            # Interpolação suave (Cubic Ease Out)
            t = self._anim_progress
            ease = 1 - (1 - t)**3 
            self.camera.yaw = self._anim_start_yaw + (self._anim_target_yaw - self._anim_start_yaw) * ease
            self.camera.pitch = self._anim_start_pitch + (self._anim_target_pitch - self._anim_start_pitch) * ease
            self.camera.update_position()
            self._dirty = True

    # ────────────────────────────────────────────────────────────────────────
    # Ponta da Tocha
    # ────────────────────────────────────────────────────────────────────────    

    def _draw_torch_head(self, painter, pos_3d, cam_mat):
        """Usa a geometria pré-calculada em vez de criar o modelo do zero a cada frame."""
        all_verts = self._torch_verts.copy()
        all_verts[:, 0] += pos_3d[0]
        all_verts[:, 1] += pos_3d[1]
        all_verts[:, 2] += pos_3d[2]

        pts_2d, valid = self._project_batch(all_verts, cam_mat)
        if not np.all(valid): return

        segments = 32
        color_body = QColor(100, 100, 110, 90)
        color_tip = QColor(100, 100, 110, 90)
        
        painter.setPen(Qt.NoPen)
        
        p_tip = QPoint(pts_2d[0,0], pts_2d[0,1])
        for i in range(segments):
            next_i = (i + 1) % segments + 1
            poly = [p_tip, QPoint(pts_2d[i+1,0], pts_2d[i+1,1]), QPoint(pts_2d[next_i,0], pts_2d[next_i,1])]
            painter.setBrush(QBrush(color_tip))
            painter.drawPolygon(*poly)

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
        segs = self.model.segments
        if segs:
            starts = np.array([s.start for s in segs], dtype=np.float64)
            ends   = np.array([s.end   for s in segs], dtype=np.float64)
            ones   = np.ones((len(segs), 1), dtype=np.float64)
            self._verts_start = np.hstack([starts, ones])
            self._verts_end   = np.hstack([ends,   ones])
            offset_z = self.substrate_h if self.substrate_enabled else 0.0
            if offset_z > 0:
                self._verts_start[:, 2] += offset_z
                self._verts_end[:, 2] += offset_z
            self._types       = np.array([0 if s.type == 'travel' else 1 for s in segs])
            self._layers_arr  = np.array([s.layer for s in segs])
            self._line_nums   = np.array([s.line_number for s in segs])
            self._base_arange = np.arange(len(segs))

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
        if segs:
            self._line_nums   = np.array([s.line_number for s in segs])
            self._base_arange = np.arange(len(segs))

    def _fit_view(self):
        self.camera.yaw = math.radians(-45)
        self.camera.pitch = math.radians(30)
        if self.model is None or not self.model.bounds:
            self.camera.target = np.array([0.0, 0.0, 0.0])
            self.camera.distance = 700.0
        else:
            xmin, ymin, zmin, xmax, ymax, zmax = self.model.bounds
            center = np.array([
                (xmin + xmax) / 2,
                (ymin + ymax) / 2,
                (zmin + zmax) / 2
            ])
            self.camera.target = center
            
            size = max(xmax - xmin, ymax - ymin, zmax - zmin)
            self.camera.distance = size * 2.5 

        self.camera.update_position()
        self.update()

    def highlight_line(self, line_number: int):
        if self._line_nums is None:
            return
        matches = np.where(self._line_nums == line_number)[0]
        if len(matches) > 0:
            self._highlighted_seg = int(matches[0])
        else:
            candidates = np.where(self._line_nums <= line_number)[0]
            self._highlighted_seg = int(candidates[-1]) if len(candidates) > 0 else None
        self._dirty = True

    def clear_highlight(self):
        self._highlighted_seg = None
        self._dirty = True

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
            if self.auto_layer and self.current_layer >= 0:
                if seg.layer != self.current_layer:
                    self.current_layer = seg.layer
                    if self.on_layer_changed:
                        self.on_layer_changed(self.current_layer)
            self.on_segment_changed(seg)

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

    def _on_timer(self):
        if self._dirty:
            self.update()
            self._dirty = False

    def paintEvent(self, event):
        # 1. Se não tiver modelo aberto, desenha só a tela de fundo e o texto
        if self.model is None or self._verts_start is None:
            painter = QPainter(self)
            painter.fillRect(self.rect(), self.color_background)
            hint_color = QColor(180, 180, 200) if self.color_background.lightness() > 128 else QColor(80, 80, 100)
            painter.setPen(QPen(hint_color))
            painter.setFont(QFont("Consolas", 11))
            painter.drawText(self.rect(), Qt.AlignCenter, "Importe um arquivo GCode para comecar")
            return

        # 2. Se tiver modelo, liga o modo de desenho
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        
        # Pinta o fundo da janela de azul escuro (Laprosolda)
        painter.fillRect(self.rect(), self.color_background)
        
        # Desenha o Substrato de 5mm por baixo da peça (se habilitado)
        self._draw_substrate(painter)
        
        # Desenha o Grid da bancada e as linhas do GCode por cima
        self._draw_segments_batched(painter)
        
        # Escreve o texto com os comandos do mouse no rodapé
        self._draw_hint(painter)

        self._update_fps()

    def _draw_hint(self, painter):
        hint_color = QColor(100, 100, 120) if self.color_background.lightness() < 128 else QColor(120, 120, 140)
        painter.setPen(QPen(hint_color))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(8, self.height() - 8,
            "Esq: orbitar  |  Scroll: zoom  |  Meio: pan  |  F: centralizar")
        
    def _update_fps(self):
        self._frame_count += 1
        current_time = time.time()
        elapsed = current_time - self._last_fps_time
        
        if elapsed >= 0.5:
            self._current_fps = self._frame_count / elapsed
            self._frame_count = 0
            self._last_fps_time = current_time
            
            # Envia o número inteiro para a interface principal
            self.fps_changed.emit(int(self._current_fps))

    def _project_batch(self, verts: np.ndarray, cam_mat=None):
        if cam_mat is None:
            cam_mat = self.camera.camera_matrix()

        # 1. ÚNICA ALOCAÇÃO: Multiplica pela matriz da câmera para gerar o array base (N, 4)
        v_cam = verts @ cam_mat

        # 2. Cria "Views" (Referências) para as colunas SEM gastar memória RAM
        x = v_cam[:, 0]
        y = v_cam[:, 1]
        w = v_cam[:, 2] # Na nossa matemática Z-UP (Laprosolda), a profundidade W é o eixo Z da câmera

        # 3. Calcula quais pontos estão na frente do plano da câmera
        valid = w > self.camera.near_plane

        # 4. Modifica o W "In-Place" para evitar a falha de Divisão por Zero
        w[w < 1e-6] = 1e-6

        # 5. Aplica a Projeção Perspectiva manualmente (Pula a matriz de projeção 4x4)
        m00 = self.projection.projection_matrix[0, 0]
        m11 = self.projection.projection_matrix[1, 1]
        
        x *= m00
        x /= w
        y *= m11
        y /= w

        # 6. Converte para o Espaço da Tela (Screen Space) In-Place (Pula a to_screen_matrix)
        HW = self.camera.WIDTH / 2.0
        HH = self.camera.HEIGHT / 2.0

        # Matemática do X: screen_x = (x + 1) * HW
        x += 1.0
        x *= HW

        # Matemática do Y: screen_y = (1 - y) * HH -> Alterado In-Place
        y *= -1.0
        y += 1.0
        y *= HH

        # 7. Corta os pontos que estão fora do limite do Canvas do PyQt (-30000, 30000) In-Place
        np.clip(x, -30000, 30000, out=x)
        np.clip(y, -30000, 30000, out=y)

        # 8. Extrai as 2 primeiras colunas (X e Y) já calculadas e converte para Inteiro
        v_int = v_cam[:, :2].astype(np.int32)

        return v_int, valid

    def _draw_segments_batched(self, painter: QPainter):
        # 1. CACHE DE FRAME: Calcula a matriz da câmera apenas UMA VEZ por frame
        cam_mat = self.camera.camera_matrix()

        # 2. OTIMIZAÇÃO O(1): Desenho do Grid em Lote (Batching)
        if hasattr(self, '_grid_v_start') and self._grid_v_start is not None:
            # Repassa a matriz cacheada
            g_pts0, g_valid0 = self._project_batch(self._grid_v_start, cam_mat)
            g_pts1, g_valid1 = self._project_batch(self._grid_v_end, cam_mat)
            g_valid = g_valid0 & g_valid1
            
            grid_color = QColor(100, 100, 120, 150) if self.dark_mode else QColor(160, 160, 180, 200) 
            painter.setPen(QPen(grid_color, 1, Qt.SolidLine))
        
            # Troca o FOR loop lento do Python por um envio direto ao C++ via QLine
            indices = np.where(g_valid)[0]
            lines = [QLine(int(g_pts0[i,0]), int(g_pts0[i,1]), int(g_pts1[i,0]), int(g_pts1[i,1])) for i in indices]
            painter.drawLines(lines)

        if self._verts_start is None:
            return
        
        pts0, valid0 = self._project_batch(self._verts_start, cam_mat)
        pts1, valid1 = self._project_batch(self._verts_end, cam_mat)
        valid = valid0 & valid1

        total = len(self._verts_start)

        if self.current_layer >= 0:
            if self.layer_isolated: layer_mask = self._layers_arr == self.current_layer
            else: layer_mask = self._layers_arr <= self.current_layer
        else:
            layer_mask = np.ones(total, dtype=bool)

        if self._sim_index >= 0:
            # 3. OTIMIZAÇÃO O(1): Usa o array cacheado em vez de np.arange()
            sim_done    = self._base_arange <= self._sim_index
            sim_pending = self._base_arange >  self._sim_index
        else:
            sim_done    = np.ones(total,  dtype=bool)
            sim_pending = np.zeros(total, dtype=bool)

        def draw_group(mask, color, width=1):
            m = mask & valid
            if not np.any(m): return
            painter.setPen(QPen(color, width))
            indices = np.where(m)[0]
            lines = [QLine(int(pts0[i,0]), int(pts0[i,1]), int(pts1[i,0]), int(pts1[i,1])) for i in indices]
            painter.drawLines(lines)

        extrude = self._types == 1
        travel  = self._types == 0

        if self.current_layer >= 0 and not self.layer_isolated:
            older = self._layers_arr < self.current_layer
            draw_group(older & extrude, self.color_extrude_old)
            if self.show_travel: draw_group(older & travel, self.color_travel_old)

        if self._sim_index >= 0:
            draw_group(layer_mask & extrude & sim_pending, self.color_extrude_dim)
            if self.show_travel: draw_group(layer_mask & travel & sim_pending, self.color_travel_dim)

        if self.show_travel: draw_group(layer_mask & travel & sim_done, self.color_travel)
        draw_group(layer_mask & extrude & sim_done, self.color_extrude)

        # 4. Passa a matriz cacheada para o desenho da tocha
        if self._highlighted_seg is not None:
            hi = self._highlighted_seg
            if 0 <= hi < total and valid[hi]:
                painter.setPen(QPen(QColor(0, 220, 255), 3, Qt.SolidLine))
                painter.drawLine(int(pts0[hi,0]), int(pts0[hi,1]), int(pts1[hi,0]), int(pts1[hi,1]))
                
                # Pega a posição XYZ (índices 0, 1, 2) já com o offset de 5mm aplicado
                pos_torch = self._verts_end[hi][:3]
                self._draw_torch_head(painter, pos_torch, cam_mat)
            
        if 0 <= self._sim_index < total:
            i = self._sim_index
            if valid[i]:
                painter.setPen(QPen(QColor(255, 255, 50), 3, Qt.SolidLine))
                painter.drawLine(int(pts0[i,0]), int(pts0[i,1]), int(pts1[i,0]), int(pts1[i,1]))
                
                # Pega a posição XYZ (índices 0, 1, 2) já com o offset de 5mm aplicado
                pos_torch = self._verts_end[i][:3]
                self._draw_torch_head(painter, pos_torch, cam_mat)

    def mousePressEvent(self, event):
        self._last_mouse_pos = event.pos()
        super().mousePressEvent(event)
        self.setFocus()
        self._mouse_last   = event.pos()
        self._mouse_button = event.button()
        self._dragging     = True

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
        
        if event.buttons() & Qt.LeftButton:
            sensitivity = 0.005
            self.camera.yaw += dx * sensitivity
            self.camera.pitch -= dy * sensitivity 
            
            limit = math.radians(89)
            self.camera.pitch = max(-limit, min(limit, self.camera.pitch))
            
        elif event.buttons() & Qt.MidButton:
            pan_sensitivity = self.camera.distance * 0.001
            
            forward = self.camera.target - self.camera.position[:3]
            forward = forward / np.linalg.norm(forward)
            
            world_up = np.array([0, 0, 1])
            right = np.cross(world_up, forward)
            
            if np.linalg.norm(right) < 1e-6:
                right = np.array([1, 0, 0])
            else:
                right = right / np.linalg.norm(right)
                
            screen_up = np.cross(forward, right)
            screen_up = screen_up / np.linalg.norm(screen_up)
            
            self.camera.target -= right * dx * pan_sensitivity
            self.camera.target += screen_up * dy * pan_sensitivity

        self.camera.update_position()
        self._last_mouse_pos = event.pos()
        self.update()

    def wheelEvent(self, event):
        zoom_speed = 1.2
        if event.angleDelta().y() > 0:
            self.camera.distance /= zoom_speed
        else:
            self.camera.distance *= zoom_speed
            
        self.camera.update_position()
        self.update()

    def keyPressEvent(self, event):
        if self.camera is None:
            return
        key = event.key()
        if key == Qt.Key_F:
            self._fit_view()
            self._dirty = True
            return
        changed = True
        
        # Como removemos o _trackball_rotate antigo, o teclado agora apenas orbita os ângulos diretamente
        if   key == Qt.Key_Left:  self.camera.yaw -= 0.1
        elif key == Qt.Key_Right: self.camera.yaw += 0.1
        elif key == Qt.Key_Up:    self.camera.pitch += 0.1
        elif key == Qt.Key_Down:  self.camera.pitch -= 0.1
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self.camera.distance = max(self._MIN_DIST, self.camera.distance * 0.9)
        elif key == Qt.Key_Minus:
            self.camera.distance = min(self._MAX_DIST, self.camera.distance * 1.1)
        else:
            changed = False
            
        if changed:
            limit = math.radians(89)
            self.camera.pitch = max(-limit, min(limit, self.camera.pitch))
            self.camera.update_position()
            self._dirty = True

    def set_simulation_from_line(self, line_number: int):
        if self._line_nums is None:
            return
        matches = np.where(self._line_nums == line_number)[0]
        if len(matches) > 0:
            self._sim_index = int(matches[0])
        else:
            candidates = np.where(self._line_nums <= line_number)[0]
            if len(candidates) > 0:
                self._sim_index = int(candidates[-1])
            else:
                self._sim_index = 0

        self._notify_segment()
        self._dirty
        
    def _draw_substrate(self, painter):
        if not self.substrate_enabled:
            return

        # Dimensões (centro em 0,0,0)
        hw = self.substrate_w / 2
        hd = self.substrate_d / 2
        hh = self.substrate_h 

        # 8 Vértices do Cubo (Substrato)
        # Z de -2.5 a 2.5 para manter o centro em 0
        verts = np.array([
            [ hw,  hd,  hh, 1], [ hw, -hd,  hh, 1], [-hw, -hd,  hh, 1], [-hw,  hd,  hh, 1], # Topo em Z=5
            [ hw,  hd,   0, 1], [ hw, -hd,   0, 1], [-hw, -hd,   0, 1], [-hw,  hd,   0, 1]  # Base em Z=0
        ])

        pts, valid = self._project_batch(verts)
        if not np.all(valid): return

        # Faces (índices dos vértices)
        faces = [
            [0, 1, 2, 3], # Topo
            [4, 5, 6, 7], # Base
            [0, 1, 5, 4], # Dir
            [2, 3, 7, 6], # Esq
            [0, 3, 7, 4], # Frente
            [1, 2, 6, 5]  # Trás
        ]

        # Estilo do Substrato (Cinza metálico semi-transparente)
        color = QColor(130, 130, 140, 160)
        painter.setPen(QPen(QColor(100, 100, 110), 1))
        
        for f in faces:
            poly = QPolygon([QPoint(pts[i,0], pts[i,1]) for i in f])
            painter.setBrush(QBrush(color))
            painter.drawPolygon(poly)