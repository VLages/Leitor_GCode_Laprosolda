from PyQt5.QtWidgets import QWidget, QOpenGLWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QCursor, QFont, QBrush, QPolygon, QPixmap, QTransform, QPolygonF
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QLine, QPointF, pyqtSignal
import time
import numpy as np
import math

# Bibliotecas do Motor OpenGL
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.arrays import vbo

from .cameraGL import Camera
from .projectionGL import Projection
from ..gcode_modelGL import GCodeModel

# ────────────────────────────────────────────────────────────────────────────
# WIDGET DO CUBO 3D (Mantido 100% original, pois já funciona perfeitamente)
# ────────────────────────────────────────────────────────────────────────────
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
        self._texture_cache = {} 

        self.targets = {}
        for x in [-1, 0, 1]:
            for y in [-1, 0, 1]:
                for z in [-1, 0, 1]:
                    if x == 0 and y == 0 and z == 0: continue
                    self.targets[(x, y, z)] = np.array([x, y, z], dtype=float)

        S = 26
        # Vértices Originais da Caixa
        self.v = np.array([
            [ S, -S,  S], # 0
            [ S,  S,  S], # 1
            [-S,  S,  S], # 2
            [-S, -S,  S], # 3
            [ S, -S, -S], # 4
            [ S,  S, -S], # 5
            [-S,  S, -S], # 6
            [-S, -S, -S]  # 7
        ])
        
        # Mapeamento Matemático 100% Corrigido
        # Ordem: [Top-Left, Top-Right, Bottom-Right, Bottom-Left]
        self.faces = [
            ([3, 0, 1, 2], 'TOP',   (0, 0, 1)),   # Z+
            ([6, 5, 4, 7], 'BASE',  (0, 0, -1)),  # Z-
            ([0, 3, 7, 4], 'FRONT', (0, -1, 0)),  # Y-
            ([2, 1, 5, 6], 'BACK',  (0, 1, 0)),   # Y+
            ([1, 0, 4, 5], 'RIGHT', (1, 0, 0)),   # X+
            ([3, 2, 6, 7], 'LEFT',  (-1, 0, 0))   # X-
        ]

    def _get_face_texture(self, label, is_hovered):
        key = (label, is_hovered)
        if key in self._texture_cache:
            return self._texture_cache[key]

        size = 128
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)

        bg_color = QColor(140, 180, 255) if is_hovered else QColor(220, 220, 230)
        p.setBrush(QBrush(bg_color))
        p.setPen(QPen(QColor(100, 100, 110), 6, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
        p.drawRect(0, 0, size, size)
        p.setPen(QColor(40, 40, 50))
        p.setFont(QFont("Consolas", 26, QFont.Bold))
        p.drawText(QRect(0, 0, size, size), Qt.AlignCenter, label)
        p.end()

        self._texture_cache[key] = pixmap
        return pixmap

    def _get_rotation_matrix(self):
        """Calcula a matriz exata baseada nos ângulos da câmera, isolando o cubo do Pan do Mouse."""
        yaw = self.viewer.camera.yaw
        pitch = self.viewer.camera.pitch

        cyaw = math.cos(yaw)
        syaw = math.sin(yaw)
        cpit = math.cos(pitch)
        spit = math.sin(pitch)

        # Colunas calculadas a partir da trigonometria do sistema Z-UP
        rx, ry, rz = -cyaw, syaw, 0.0
        ux, uy, uz = -spit * syaw, -spit * cyaw, cpit
        dx, dy, dz = -cpit * syaw, -cpit * cyaw, -spit

        return np.array([
            [rx, ux, dx],
            [ry, uy, dy],
            [rz, uz, dz]
        ])

    def paintEvent(self, event):
        if self.viewer.camera is None: return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx, cy = self.width() / 2, self.height() / 2 - 10
        painter.setBrush(QBrush(QColor(20, 20, 35, 100)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(10, 0, self.SIZE-20, self.SIZE-20)

        # Busca a matriz calculada nativamente
        R = self._get_rotation_matrix()
        self._draw_mini_axes(painter, R)

        v_cam = self.v @ R
        centers = []
        for idx, (verts, label, norm) in enumerate(self.faces):
            center_cam = np.mean(v_cam[verts], axis=0)
            centers.append((center_cam[2], idx)) 
            
        centers.sort(key=lambda x: x[0], reverse=True)

        square = QPolygonF([
            QPointF(128, 0), QPointF(0, 0),       # Topo invertido
            QPointF(0, 128), QPointF(128, 128)    # Base invertida
        ])

        for depth, idx in centers:
            verts, label, norm = self.faces[idx]
            n_cam = np.array(norm) @ R

            # Backface culling
            if n_cam[2] < 0.1: 
                is_face_hovered = (self._hovered_part == norm)
                polygon_f = QPolygonF()
                for vi in verts:
                    x = cx + v_cam[vi, 0]
                    y = cy - v_cam[vi, 1]
                    polygon_f.append(QPointF(x, y))

                transform = QTransform()
                if QTransform.quadToQuad(square, polygon_f, transform):
                    painter.save()
                    painter.setTransform(transform)
                    pixmap = self._get_face_texture(label, is_face_hovered)
                    painter.drawPixmap(0, 0, pixmap)
                    painter.restore()

                    if not is_face_hovered:
                        light_dir = np.array([0.4, 0.4, -0.8])
                        intensity = max(0.0, min(1.0, np.dot(n_cam, light_dir)))
                        shadow_alpha = int(255 * (1.0 - (0.4 + 0.6 * intensity)))
                        painter.setBrush(QBrush(QColor(0, 0, 0, shadow_alpha)))
                        painter.setPen(Qt.NoPen)
                        poly_int = QPolygon([QPoint(int(p.x()), int(p.y())) for p in polygon_f])
                        painter.drawPolygon(poly_int)

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
        
        # O mouse também puxa da mesma matriz unificada
        R = self._get_rotation_matrix()
        cx, cy = self.width() / 2, self.height() / 2 - 10
        S = 26

        for key, vec in self.targets.items():
            surf_p = vec * S
            v_cam = surf_p @ R
            if v_cam[2] > 5: continue

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


# ────────────────────────────────────────────────────────────────────────────
# RENDERIZADOR PRINCIPAL EM OPENGL
# ────────────────────────────────────────────────────────────────────────────
class GCodeViewer3D(QOpenGLWidget):
    fps_changed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)

        self.substrate_enabled = False
        self.substrate_w = 100
        self.substrate_d = 100
        self.substrate_h = 5.0

        self.model         = None
        self.camera        = None
        self.current_layer = -1   
        self.layer_isolated = False  

        self._line_nums   = None   
        self._sim_index   = -1
        self._highlighted_seg = None  

        self.on_segment_changed = None
        self.on_layer_changed   = None  

        self._MIN_DIST   = 1.0
        self._MAX_DIST   = 5000.0
        self._last_mouse_pos = None

        self._dirty = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._timer.start(0)

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

        self._torch_verts = self._generate_torch_geometry()

        self._frame_count = 0
        self._last_fps_time = time.time()
        self._current_fps = 0.0

        self._axis_widget = ViewCubeWidget(self, self)
        self._axis_widget.raise_()

    # ─── CILOS DO OPENGL ────────────────────────────────────────────────────

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        
        # Resolve o problema de transparência bloqueando outras linhas no Z-Buffer
        # glEnable(GL_ALPHA_TEST)
        # glAlphaFunc(GL_GREATER, 0.01)

    def resizeGL(self, w, h):
        if self.camera is None: return
        self.camera.WIDTH = w
        self.camera.HEIGHT = h
        self.camera.v_fov = self.camera.h_fov * (h / w if w > 0 else 1)
        
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(math.degrees(self.camera.v_fov), w / h if h > 0 else 1, 
                       self.camera.near_plane, self.camera.far_plane)

    def paintGL(self):
        r, g, b, a = self.color_background.getRgbF()
        glClearColor(r, g, b, a)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_LINE_SMOOTH)
        
        if self.camera is None or self.model is None:
            painter = QPainter(self)
            painter.setPen(QColor(180, 180, 200))
            painter.setFont(QFont("Consolas", 11))
            painter.drawText(self.rect(), Qt.AlignCenter, "Importe um arquivo GCode para comecar")
            painter.end()
            return

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        pos = self.camera.position[:3]
        target = self.camera.target
        gluLookAt(pos[0], pos[1], pos[2], target[0], target[1], target[2], 0, 0, 1)

        self._draw_substrate_gl()
        show_warning_text = self._draw_substrate_warning_gl()

        # 1. DESENHA O GRID (Garante que a matriz de cores está desligada)
        if hasattr(self, '_vbo_grid'):
            glDisableClientState(GL_COLOR_ARRAY) # <--- CORREÇÃO DO BUG AQUI
            glEnableClientState(GL_VERTEX_ARRAY)
            self._vbo_grid.bind()
            glVertexPointer(3, GL_FLOAT, 0, self._vbo_grid)
            rg, gg, bg, ag = (80/255, 80/255, 100/255, 150/255) if self.dark_mode else (140/255, 140/255, 160/255, 200/255)
            glColor4f(rg, gg, bg, ag)
            glDrawArrays(GL_LINES, 0, len(self._grid_array))
            self._vbo_grid.unbind()
            glDisableClientState(GL_VERTEX_ARRAY)

        # 2. ATUALIZA AS CORES DO GCODE
        state_hash = (self._sim_index, self.current_layer, self.layer_isolated, self.dark_mode, self.show_travel)
        if getattr(self, '_last_state_hash', None) != state_hash:
            self._update_colors_vbo()
            self._last_state_hash = state_hash

        # 3. DESENHA O GCODE (Com a divisão de profundidade)
        # 3. DESENHA O GCODE (Com espessuras independentes)
        if hasattr(self, '_vbo_vertices') and hasattr(self, '_idx_ex_bg'):
            glEnableClientState(GL_VERTEX_ARRAY)
            glEnableClientState(GL_COLOR_ARRAY) 
            
            self._vbo_vertices.bind()
            glVertexPointer(3, GL_FLOAT, 0, self._vbo_vertices)
            self._vbo_colors.bind()
            glColorPointer(4, GL_FLOAT, 0, self._vbo_colors)
            
            # Sub-função inteligente que ajusta a espessura antes de desenhar
            def draw_lines(indices, width):
                if len(indices) > 0:
                    glLineWidth(width)
                    glDrawElements(GL_LINES, len(indices), GL_UNSIGNED_INT, indices)

            glDisable(GL_DEPTH_TEST)   # ← Linhas de fundo nunca mais bloqueadas pelo substrato
            glDepthMask(GL_FALSE)
            draw_lines(self._idx_ex_bg, 1.2)
            if self.show_travel: draw_lines(self._idx_tr_bg, 0.2)
            glDepthMask(GL_TRUE)

            glDisable(GL_DEPTH_TEST)
            draw_lines(self._idx_ex_pr, 1.2) 
            if self.show_travel: draw_lines(self._idx_tr_pr, 0.2) 
            
            glEnable(GL_DEPTH_TEST)
            
            self._vbo_colors.unbind()
            self._vbo_vertices.unbind()
            glDisableClientState(GL_COLOR_ARRAY)
            glDisableClientState(GL_VERTEX_ARRAY)
            glLineWidth(1.0)

        # 4. DESENHA A TOCHA
        self._draw_torches_gl()

        if self.dark_mode:
            aviso = (255, 220, 0)
        else:
            aviso = (130, 0, 255)

        # Textos 2D
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if show_warning_text:
            painter.setPen(QPen(QColor(*aviso))) 
            painter.setFont(QFont("Consolas", 10, QFont.Bold))
            painter.drawText(10, 40, "⚠ AVISO: O GCode excede as dimensões do substrato!")
            
        self._draw_hint(painter)
        self._update_fps()
        painter.end()

    # ─── PREPARAÇÃO DOS DADOS (VRAM) ────────────────────────────────────────

    def _precompute_geometry(self):
        segs = self.model.segments
        if segs:
            starts = np.array([s.start for s in segs], dtype=np.float32)
            ends   = np.array([s.end   for s in segs], dtype=np.float32)

            offset_z = self.substrate_h if self.substrate_enabled else 0.0
            if offset_z > 0:
                starts[:, 2] += offset_z
                ends[:, 2] += offset_z

            self._vertex_array = np.empty((len(segs) * 2, 3), dtype=np.float32)
            self._vertex_array[0::2] = starts
            self._vertex_array[1::2] = ends

            self._types_repeated = np.empty(len(segs) * 2, dtype=np.int32)
            types = np.array([0 if s.type == 'travel' else 1 for s in segs])
            self._types_repeated[0::2] = types
            self._types_repeated[1::2] = types

            self._layers_repeated = np.empty(len(segs) * 2, dtype=np.int32)
            layers = np.array([s.layer for s in segs])
            self._layers_repeated[0::2] = layers
            self._layers_repeated[1::2] = layers

            self._sim_repeated = np.empty(len(segs) * 2, dtype=np.int32)
            base_arange = np.arange(len(segs))
            self._sim_repeated[0::2] = base_arange
            self._sim_repeated[1::2] = base_arange

            self._line_nums = np.array([s.line_number for s in segs])

            self._color_array = np.zeros((len(segs) * 2, 4), dtype=np.float32)

            self._vbo_vertices = vbo.VBO(self._vertex_array)
            self._vbo_colors = vbo.VBO(self._color_array, usage='GL_DYNAMIC_DRAW')

        grid = self.model.grid_segments
        if grid:
            g_starts = np.array([s.start for s in grid], dtype=np.float32)
            g_ends   = np.array([s.end   for s in grid], dtype=np.float32)
            self._grid_array = np.empty((len(grid) * 2, 3), dtype=np.float32)
            self._grid_array[0::2] = g_starts
            self._grid_array[1::2] = g_ends
            self._vbo_grid = vbo.VBO(self._grid_array)
            
        self._last_state_hash = None 

    def _update_colors_vbo(self):
        if not hasattr(self, '_color_array'): return
        total_verts = len(self._vertex_array)
        
        if self.current_layer >= 0:
            active_mask = self._layers_repeated == self.current_layer
            older_mask = np.zeros(total_verts, dtype=bool) if self.layer_isolated else self._layers_repeated < self.current_layer
        else:
            active_mask = np.ones(total_verts, dtype=bool)
            older_mask = np.zeros(total_verts, dtype=bool)

        sim_done = self._sim_repeated <= self._sim_index if self._sim_index >= 0 else np.ones(total_verts, bool)
        sim_pending = self._sim_repeated > self._sim_index if self._sim_index >= 0 else np.zeros(total_verts, bool)

        extrude = self._types_repeated == 1
        travel = self._types_repeated == 0
        self._color_array[:] = (0, 0, 0, 0) 

        def apply_color(mask, qcolor, alpha):
            if not np.any(mask): return
            r, g, b, _ = qcolor.getRgbF()
            self._color_array[mask] = (r, g, b, alpha)

        # 1. Passado e Futuro: Alpha baixo
        apply_color(older_mask & extrude & sim_done,    self.color_extrude_old, 0.5)
        apply_color(active_mask & extrude & sim_pending, self.color_extrude_dim, 0.8)
        if self.show_travel:
            apply_color(older_mask & travel & sim_done,    self.color_travel_old, 0.5)
            apply_color(active_mask & travel & sim_pending, self.color_travel_dim, 0.8)

        # 2. PRESENTE (Linhas atuais): Alpha 1.0
        apply_color(active_mask & extrude & sim_done, self.color_extrude, 1.0)
        if self.show_travel: 
            apply_color(active_mask & travel & sim_done, self.color_travel, 1.0)

        self._vbo_colors.bind()
        glBufferSubData(GL_ARRAY_BUFFER, 0, self._color_array.nbytes, self._color_array)
        self._vbo_colors.unbind()

        # --- NOVA LÓGICA: Separa os índices para aplicar espessuras diferentes ---
        bg_mask = (older_mask & sim_done) | (active_mask & sim_pending)
        pr_mask = active_mask & sim_done

        self._idx_ex_bg = np.where(extrude & bg_mask)[0].astype(np.uint32)
        self._idx_tr_bg = np.where(travel & bg_mask)[0].astype(np.uint32)
        self._idx_ex_pr = np.where(extrude & pr_mask)[0].astype(np.uint32)
        self._idx_tr_pr = np.where(travel & pr_mask)[0].astype(np.uint32)

    # ─── DESENHOS 3D ────────────────────────────────────────────────────────

    def _draw_substrate_gl(self):
        if not self.substrate_enabled: return
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # --- A SOLUÇÃO DEFINITIVA ---
        # Abaixamos o teto do substrato em 0.05mm. Isso cria uma "folga de ar"
        # que impede o Z-Buffer de cortar as bordas suaves (anti-aliasing) do GCode!
        hw, hd = self.substrate_w / 2.0, self.substrate_d / 2.0
        hh = self.substrate_h - 0.05 
        # ----------------------------

        faces = [
            [(hw, hd, hh), (-hw, hd, hh), (-hw, -hd, hh), (hw, -hd, hh)], 
            [(hw, hd, 0), (hw, -hd, 0), (-hw, -hd, 0), (-hw, hd, 0)], 
            [(hw, hd, hh), (hw, -hd, hh), (hw, -hd, 0), (hw, hd, 0)], 
            [(-hw, -hd, hh), (-hw, hd, hh), (-hw, hd, 0), (-hw, -hd, 0)], 
            [(hw, -hd, hh), (-hw, -hd, hh), (-hw, -hd, 0), (hw, -hd, 0)], 
            [(-hw, hd, hh), (hw, hd, hh), (hw, hd, 0), (-hw, hd, 0)] 
        ]

        if self.dark_mode:
            cinza_escuro = (100/255, 100/255, 120/255, 0.8)
            cinza_borda = (80/255, 80/255, 100/255, 1.0)
        else:
            cinza_escuro = (160/255, 160/255, 180/255, 0.8)
            cinza_borda = (140/255, 140/255, 160/255, 1.0)

        glEnable(GL_POLYGON_OFFSET_FILL)
        glPolygonOffset(1.0, 1.0)
        
        # Desenha as faces (sem hacks de DepthMask)
        glColor4f(*cinza_escuro)
        glBegin(GL_QUADS)
        for face in faces:
            for v in face: glVertex3f(*v)
        glEnd()
        
        glDisable(GL_POLYGON_OFFSET_FILL)

        # Desenha as bordas
        glColor4f(*cinza_borda)
        glLineWidth(2.0)
        for face in faces:
            glBegin(GL_LINE_LOOP)
            for v in face: glVertex3f(*v)
            glEnd()
        glLineWidth(1.0)
        # ----------------------------------------------------------------------

    def _draw_substrate_warning_gl(self):
        if not self.substrate_enabled or self.model is None or not self.model.bounds: return False
        xmin, ymin, zmin, xmax, ymax, zmax = self.model.bounds
        sub_hw, sub_hd = self.substrate_w / 2.0, self.substrate_d / 2.0

        if (xmin < -sub_hw) or (xmax > sub_hw) or (ymin < -sub_hd) or (ymax > sub_hd):
            # 1. EVITA Z-FIGHTING: Criamos um envelope 1mm maior que o substrato cinza
            pad = 0.01
            req_xmin, req_xmax = min(xmin, -sub_hw) - pad, max(xmax, sub_hw) + pad
            req_ymin, req_ymax = min(ymin, -sub_hd) - pad, max(ymax, sub_hd) + pad
            
            # Altura ligeiramente maior para o envelope amarelo
            z_top = self.substrate_h + pad
            z_bot = -pad
            
            faces = [
                [(req_xmax, req_ymax, z_top), (req_xmin, req_ymax, z_top), (req_xmin, req_ymin, z_top), (req_xmax, req_ymin, z_top)],
                [(req_xmax, req_ymax, z_bot), (req_xmax, req_ymin, z_bot), (req_xmin, req_ymin, z_bot), (req_xmin, req_ymax, z_bot)],
                [(req_xmax, req_ymax, z_top), (req_xmax, req_ymin, z_top), (req_xmax, req_ymin, z_bot), (req_xmax, req_ymax, z_bot)],
                [(req_xmin, req_ymin, z_top), (req_xmin, req_ymax, z_top), (req_xmin, req_ymax, z_bot), (req_xmin, req_ymin, z_bot)],
                [(req_xmax, req_ymin, z_top), (req_xmin, req_ymin, z_top), (req_xmin, req_ymin, z_bot), (req_xmax, req_ymin, z_bot)],
                [(req_xmin, req_ymax, z_top), (req_xmax, req_ymax, z_top), (req_xmax, req_ymax, z_bot), (req_xmin, req_ymax, z_bot)]
            ]
            
            # 2. FORÇA ESTADO DE TRANSPARÊNCIA (Resolve o problema da "caixa sólida")
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glDepthMask(GL_FALSE) # Permite ver o substrato através da caixa

            if self.dark_mode:
                alerta_color = (255/255, 220/255, 0/255, 38/255)
                alerta_borda = (255/255, 220/255, 0/255, 204/255)
            else: 
                alerta_color = (130/255, 0/255, 255/255, 38/255)
                alerta_borda = (130/255, 0/255, 255/255, 204/255)
            
            # Desenha as faces amarelas translúcidas (Alpha 0.15)
            glColor4f(*alerta_color)
            glBegin(GL_QUADS)
            for face in faces:
                for v in face: glVertex3f(*v)
            glEnd()
            
            # Desenha as bordas amarelas mais fortes (Alpha 0.8)
            glColor4f(*alerta_borda)
            glLineWidth(1.0)
            for face in faces:
                glBegin(GL_LINE_LOOP)
                for v in face: glVertex3f(*v)
                glEnd()
            
            glLineWidth(1.0)
            glDepthMask(GL_TRUE) # Restaura escrita no Z-Buffer
            return True 
        return False

    def _generate_torch_geometry(self):
        self._torch_segments = 8
        r, h_cone, h_cyl = 5, 10, 35
        seg = self._torch_segments
        tip = [0, 0, 0]
        cone_base = [[r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), h_cone] for i in range(seg)]
        cyl_top = [[r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), h_cone + h_cyl] for i in range(seg)]
        return np.array([tip] + cone_base + cyl_top, dtype=np.float32)

    def _draw_torches_gl(self):
        """Desenha apenas o cursor/tocha atual sem o rastro do cometa."""
        if not hasattr(self, '_vertex_array'): return
        total_segs = len(self._vertex_array) // 2

        def draw_torch_3d(idx, r, g, b):
            # 1. DESLIGA O DEPTH TEST (Tudo desenhado daqui pra frente fica por cima)
            glDisable(GL_DEPTH_TEST)
            glLineWidth(1.5)
            
            # Desenha a linha de solda (Destaque Amarelo ou Ciano)
            glColor4f(r, g, b, 1.0)
            glBegin(GL_LINES)
            glVertex3f(*self._vertex_array[idx * 2])
            glVertex3f(*self._vertex_array[idx * 2 + 1])
            glEnd()
            
            glLineWidth(1.0)

            # 2. Prepara as cores da Tocha (Sólido e Borda)
            pos_end = self._vertex_array[idx * 2 + 1]
            glPushMatrix()
            glTranslatef(pos_end[0], pos_end[1], pos_end[2])
            
            if self.dark_mode:
                cinza_metalico = (80/255, 80/255, 100/255, 0.9)
                cinza_borda    = (60/255, 60/255,  80/255, 0.5) # Borda escura e discreta
            else:
                cinza_metalico = (140/255, 140/255, 160/255, 0.9)
                cinza_borda    = (120/255,  120/255,  140/255, 0.5) # Borda cinza e discreta

            # --- CAMADA A: O PREENCHIMENTO SÓLIDO (Smooth) ---
            seg = self._torch_segments # Puxa o valor definido lá na geração
            
            # --- CAMADA A: O PREENCHIMENTO SÓLIDO (Smooth) ---
            glColor4f(*cinza_metalico)
            
            # Bico (Sólido)
            glBegin(GL_TRIANGLE_FAN)
            glVertex3f(*self._torch_verts[0][:3])
            for i in range(1, seg + 2): 
                glVertex3f(*self._torch_verts[i if i <= seg else 1][:3])
            glEnd()
            
            # Corpo (Sólido)
            glBegin(GL_QUAD_STRIP)
            for i in range(1, seg + 2):
                idx_v = i if i <= seg else 1
                glVertex3f(*self._torch_verts[idx_v][:3])
                glVertex3f(*self._torch_verts[idx_v + seg][:3]) # Usa a matemática do segmento
            glEnd()


            # --- CAMADA B: A BORDA ESTRUTURAL (Wireframe Sutil) ---
            glColor4f(*cinza_borda)
            glLineWidth(0.5) 
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE) 

            # Redesenha o Bico (linhas)
            glBegin(GL_TRIANGLE_FAN)
            glVertex3f(*self._torch_verts[0][:3])
            for i in range(1, seg + 2): 
                glVertex3f(*self._torch_verts[i if i <= seg else 1][:3])
            glEnd()
            
            # Redesenha o Corpo (linhas)
            glBegin(GL_QUAD_STRIP)
            for i in range(1, seg + 2):
                idx_v = i if i <= seg else 1
                glVertex3f(*self._torch_verts[idx_v][:3])
                glVertex3f(*self._torch_verts[idx_v + seg][:3])
            glEnd()

            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL) 
            glLineWidth(1.0)
            # ------------------------------------------------------

            glPopMatrix()

            # 3. RELIGA O DEPTH TEST (Apenas no final de tudo)
            glEnable(GL_DEPTH_TEST)

        # Chama a função principal passando a cor correta
        if self._highlighted_seg is not None and 0 <= self._highlighted_seg < total_segs:
            draw_torch_3d(self._highlighted_seg, 0.0, 0.86, 1.0) # Azul Cyan
        if 0 <= self._sim_index < total_segs:
            draw_torch_3d(self._sim_index, 1.0, 1.0, 0.2) # Amarelo vibrante
    # ─── CONTROLES DE INTERFACE E EVENTOS ───────────────────────────────────

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
            self.camera = Camera(W, H)
            self.makeCurrent()
            self.resizeGL(W, H)
            self.doneCurrent()
            self._fit_view()

        self._precompute_geometry()
        self._reposition_gizmo()
        self._dirty = True
        self.update()

    def _reposition_gizmo(self):
        margin = 8
        s = self._axis_widget.SIZE
        self._axis_widget.move(self.width() - s - margin, self.height() - s - margin)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_gizmo()

    def mousePressEvent(self, event):
        self._last_mouse_pos = event.pos()
        self.setFocus()

    def mouseMoveEvent(self, event):
        if self._last_mouse_pos is None:
            self._last_mouse_pos = event.pos()
            return
        if event.buttons() == Qt.NoButton: return

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
            
            if np.linalg.norm(right) < 1e-6: right = np.array([1, 0, 0])
            else: right = right / np.linalg.norm(right)
                
            screen_up = np.cross(forward, right)
            screen_up = screen_up / np.linalg.norm(screen_up)
            
            self.camera.target += right * dx * pan_sensitivity
            self.camera.target += screen_up * dy * pan_sensitivity

        self.camera.update_position()
        self._last_mouse_pos = event.pos()
        # --- ALTERAÇÃO AQUI ---
        self._dirty = True

    def wheelEvent(self, event):
        zoom_speed = 1.2
        if event.angleDelta().y() > 0: 
            self.camera.distance /= zoom_speed
        else: 
            self.camera.distance *= zoom_speed
            
        self.camera.update_position()
        # --- ALTERAÇÃO AQUI ---
        self._dirty = True

    def keyPressEvent(self, event):
        if self.camera is None: return
        key = event.key()
        if key == Qt.Key_F:
            self._fit_view()
            self._dirty = True
            return
        changed = True
        if   key == Qt.Key_Left:  self.camera.yaw -= 0.1
        elif key == Qt.Key_Right: self.camera.yaw += 0.1
        elif key == Qt.Key_Up:    self.camera.pitch += 0.1
        elif key == Qt.Key_Down:  self.camera.pitch -= 0.1
        elif key in (Qt.Key_Plus, Qt.Key_Equal): self.camera.distance = max(self._MIN_DIST, self.camera.distance * 0.9)
        elif key == Qt.Key_Minus: self.camera.distance = min(self._MAX_DIST, self.camera.distance * 1.1)
        else: changed = False
            
        if changed:
            limit = math.radians(89)
            self.camera.pitch = max(-limit, min(limit, self.camera.pitch))
            self.camera.update_position()
            self._dirty = True

    # ─── MÉTODOS DE SIMULAÇÃO E CÂMERA ──────────────────────────────────────

    def _fit_view(self):
        self.camera.yaw = math.radians(-45)
        self.camera.pitch = math.radians(30)
        if self.model is None or not self.model.bounds:
            self.camera.target = np.array([0.0, 0.0, 0.0])
            self.camera.distance = 700.0
        else:
            xmin, ymin, zmin, xmax, ymax, zmax = self.model.bounds
            center = np.array([(xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2])
            self.camera.target = center
            size = max(xmax - xmin, ymax - ymin, zmax - zmin)
            self.camera.distance = size * 2.5 
        self.camera.update_position()
        self.update()

    def animate_camera_to(self, target_yaw, target_pitch):
        self._anim_start_yaw = self.camera.yaw
        self._anim_start_pitch = self.camera.pitch
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
        self._anim_progress += 0.06 
        if self._anim_progress >= 1.0:
            self.camera.yaw = self._anim_target_yaw
            self.camera.pitch = self._anim_target_pitch
            self.camera.update_position()
            self._dirty = True
            self._anim_timer.stop()
        else:
            t = self._anim_progress
            ease = 1 - (1 - t)**3 
            self.camera.yaw = self._anim_start_yaw + (self._anim_target_yaw - self._anim_start_yaw) * ease
            self.camera.pitch = self._anim_start_pitch + (self._anim_target_pitch - self._anim_start_pitch) * ease
            self.camera.update_position()
            self._dirty = True

    def highlight_line(self, line_number: int):
        if self._line_nums is None: return
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

    def set_simulation_from_line(self, line_number: int):
        if self._line_nums is None: return
        matches = np.where(self._line_nums == line_number)[0]
        if len(matches) > 0: self._sim_index = int(matches[0])
        else:
            candidates = np.where(self._line_nums <= line_number)[0]
            if len(candidates) > 0: self._sim_index = int(candidates[-1])
            else: self._sim_index = 0
        self._notify_segment()
        self._dirty = True

    def iniciar_simulacao(self):
        if self.model is None: return
        self._rev_running = False
        self._rev_timer.stop()
        if self._sim_index < 0: self._sim_index = 0
        self._sim_running = True
        self._sim_timer.start(self._sim_speed_ms)

    def parar_simulacao(self):
        self._sim_running = False
        self._sim_timer.stop()

    def iniciar_reverso(self):
        if self.model is None: return
        self.parar_simulacao()
        if self._sim_index < 0: self._sim_index = len(self.model.segments) - 1
        self._rev_running = True
        self._rev_timer.start(self._sim_speed_ms)

    def parar_reverso(self):
        self._rev_running = False
        self._rev_timer.stop()

    def retroceder_simulacao(self):
        self.parar_simulacao()
        self.parar_reverso()
        if self._sim_index > 0: self._sim_index -= 1
        elif self._sim_index < 0 and self.model: self._sim_index = len(self.model.segments) - 1
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
        if self._sim_running: self._sim_timer.setInterval(self._sim_speed_ms)
        if self._rev_running: self._rev_timer.setInterval(self._sim_speed_ms)

    def _sim_step(self):
        if self.model is None:
            self.parar_simulacao()
            return
        n = len(self.model.segments)
        if self._sim_index >= n - 1:
            self.parar_simulacao()
            self._sim_index = n - 1
        else: self._sim_index += 1
        self._notify_segment()
        self._dirty = True

    def _rev_step(self):
        if self.model is None:
            self.parar_reverso()
            return
        if self._sim_index <= 0:
            self.parar_reverso()
            self._sim_index = 0
        else: self._sim_index -= 1
        self._notify_segment()
        self._dirty = True

    def _notify_segment(self):
        if self.on_segment_changed and self.model and 0 <= self._sim_index < len(self.model.segments):
            seg = self.model.segments[self._sim_index]
            if self.auto_layer and self.current_layer >= 0:
                if seg.layer != self.current_layer:
                    self.current_layer = seg.layer
                    if self.on_layer_changed: self.on_layer_changed(self.current_layer)
            self.on_segment_changed(seg)

    def set_layer(self, layer_index: int):
        self.current_layer = layer_index
        self._dirty = True

    def layer_anterior(self):
        if self.model is None: return
        max_layer = self.model.layer_count - 1
        if self.current_layer < 0: self.current_layer = max_layer
        elif self.current_layer > 0: self.current_layer -= 1
        self._dirty = True
        return self.current_layer

    def layer_seguinte(self):
        if self.model is None: return
        max_layer = self.model.layer_count - 1
        if self.current_layer < 0: self.current_layer = 0
        elif self.current_layer < max_layer: self.current_layer += 1
        self._dirty = True
        return self.current_layer

    def _on_timer(self):
        """O 'Batedor de Ponto' do Render Loop. Atualiza a tela a 60 FPS se houver mudanças."""
        if self._dirty:
            self.update()              # Atualiza o OpenGL (G-Code)
            self._axis_widget.update() # Atualiza o Cubo 3D (Overlay)
            self._dirty = False

    def _draw_hint(self, painter):
        hint_color = QColor(100, 100, 120) if self.color_background.lightness() < 128 else QColor(120, 120, 140)
        painter.setPen(QPen(hint_color))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(8, self.height() - 8, "Esq: orbitar  |  Scroll: zoom  |  Meio: pan  |  F: centralizar")
        
    def _update_fps(self):
        self._frame_count += 1
        current_time = time.time()
        elapsed = current_time - self._last_fps_time
        if elapsed >= 0.5:
            self._current_fps = self._frame_count / elapsed
            self._frame_count = 0
            self._last_fps_time = current_time
            self.fps_changed.emit(int(self._current_fps))