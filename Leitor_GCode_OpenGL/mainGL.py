import sys 
import math
from PyQt5.QtWidgets import (
    QApplication, QDialog, QFileDialog, QMessageBox,
    QCheckBox, QVBoxLayout,
    QLabel, QDialogButtonBox, QGroupBox, 
    QRadioButton, QLineEdit, QFormLayout,
    QWidget, QPushButton
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRectF, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen

from ui.editor_graficoGL import Ui_editor_grafico
from motor_3d.gcode_parserGL import GCodeParser
from motor_3d.render.viewerGL import GCodeViewer3D

# ────────────────────────────────────────────────────────────────────────────
# Temas
# ────────────────────────────────────────────────────────────────────────────

DARK_THEME = {
    "bg":            "#16161f",
    "bg2":           "#0e0e16",
    "text":          "#d2d2dc",
    "text_dim":      "#8888a0",
    "accent":        "#2267fc",
    "border":        "#2a2a3a",
    "btn":           "#23233a",
    "btn_hover":     "#2e2e4a",
    "viewer_bg":     QColor(22, 22, 32),
    "label_dm":      "Dark",
}

LIGHT_THEME = {
    "bg":            "#f0f0f5",
    "bg2":           "#ffffff",
    "text":          "#222230",
    "text_dim":      "#666680",
    "accent":        "#2267fc",
    "border":        "#c0c0d0",
    "btn":           "#e0e0ee",
    "btn_hover":     "#d0d0e0",
    "viewer_bg":     QColor(240, 240, 248),
    "label_dm":      "Light",
}


def build_stylesheet(t: dict) -> str:
    return f"""
    QDialog, QWidget {{
        background-color: {t['bg']};
        color: {t['text']};
        font-family: Consolas, 'Courier New', monospace;
        font-size: 12px;
    }}
    QPushButton {{
        background-color: {t['btn']};
        color: {t['text']};
        border: 1px solid {t['border']};
        border-radius: 4px;
        padding: 5px 10px;
        min-height: 26px;
    }}
    QPushButton:hover {{
        background-color: {t['btn_hover']};
        border-color: {t['accent']};
        color: {t['text']};
    }}
    QPushButton:pressed {{
        background-color: {t['accent']};
        color: {t['bg']};
    }}
    QPushButton:disabled {{
        background-color: {t['bg']};
        color: {t['text_dim']};
        border-color: {t['border']};
    }}
    QPlainTextEdit {{
        background-color: {t['bg2']};
        color: {t['text_dim']};
        border: 1px solid {t['border']};
        border-radius: 3px;
        font-family: Consolas, monospace;
        font-size: 11px;
        selection-background-color: {t['accent']};
        selection-color: {t['bg']};
    }}
    QSlider::groove:horizontal {{
        background: {t['btn']};
        height: 6px;
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {t['accent']};
        width: 14px; height: 14px;
        margin: -4px 0;
        border-radius: 7px;
    }}
    QSlider::sub-page:horizontal {{
        background: {t['accent']};
        border-radius: 3px;
    }}
    QRadioButton {{ spacing: 6px; }}
    QRadioButton::indicator {{
        width: 14px; height: 14px;
        border-radius: 7px;
        border: 2px solid {t['border']};
        background: {t['bg']};
    }}
    QRadioButton::indicator:checked {{
        background: {t['accent']};
        border-color: {t['accent']};
    }}
    QCheckBox {{ spacing: 6px; color: {t['text']}; }}
   
    QLabel {{ color: {t['text_dim']}; font-size: 11px; }}
    QGroupBox {{
        color: {t['text_dim']};
        border: 1px solid {t['border']};
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 4px;
    }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 8px; }}
    QFrame[frameShape="4"], QFrame[frameShape="5"] {{ color: {t['border']}; }}
    """

# ────────────────────────────────────────────────────────────────────────────
# Dialogo de configuracoes
# ────────────────────────────────────────────────────────────────────────────

class ConfigDialog(QDialog):
    def __init__(self, current_w, current_d, model_bounds, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações de Bancada - Laprosolda")
        self.setModal(True)
        self.resize(350, 400)
        
        self.model_bounds = model_bounds
        self.clamps = getattr(parent, 'clamps', []).copy() # Puxa da janela principal
        
        self.result_w, self.result_d = current_w, current_d
        layout = QVBoxLayout(self)

        grp_grid = QGroupBox("Dimensões do Grid (Bancada)")
        grid_lay = QVBoxLayout(grp_grid)
        self.rad1 = QRadioButton("1000 x 1000 mm (1m x 1m)")
        self.rad2 = QRadioButton("700 x 500 mm (70cm x 50cm)")
        self.rad3 = QRadioButton("1130 x 800 mm (113cm x 80cm)")
        self.rad_custom = QRadioButton("Customizado (mm):")
        
        grid_lay.addWidget(self.rad1); grid_lay.addWidget(self.rad2)
        grid_lay.addWidget(self.rad3); grid_lay.addWidget(self.rad_custom)

        self.custom_w = QLineEdit(str(current_w))
        self.custom_d = QLineEdit(str(current_d))
        self.custom_w.setEnabled(False); self.custom_d.setEnabled(False)
        
        form = QFormLayout()
        form.addRow("Largura X:", self.custom_w)
        form.addRow("Profundidade Y:", self.custom_d)
        grid_lay.addLayout(form)
        layout.addWidget(grp_grid)

        # --- GRUPO DO SUBSTRATO E FIXADORES ---
        grp_subst = QGroupBox("Elementos Adicionais")
        subst_lay = QVBoxLayout(grp_subst)
        self.chk_subst = QCheckBox("Adicionar Substrato")
        self.chk_subst.setChecked(getattr(parent, 'substrate_enabled', False))
        self.sub_w = QLineEdit(str(getattr(parent, 'substrate_w', 100)))
        self.sub_d = QLineEdit(str(getattr(parent, 'substrate_d', 100)))
        
        sub_form = QFormLayout()
        sub_form.addRow("Largura (X) mm:", self.sub_w)
        sub_form.addRow("Profundidade (Y) mm:", self.sub_d)
        
        self.btn_posicionar = QPushButton("Posicionar Fixadores...")
        self.btn_posicionar.clicked.connect(self.abrir_posicionador)
        
        subst_lay.addWidget(self.chk_subst)
        subst_lay.addLayout(sub_form)
        subst_lay.addWidget(self.btn_posicionar)
        layout.addWidget(grp_subst)

        # Conexões Dinâmicas
        self.chk_subst.toggled.connect(lambda b: (self.sub_w.setEnabled(b), self.sub_d.setEnabled(b), self._validate_substrate()))
        self.sub_w.textChanged.connect(self._validate_substrate)
        self.sub_d.textChanged.connect(self._validate_substrate)
        self.rad_custom.toggled.connect(lambda b: (self.custom_w.setEnabled(b), self.custom_d.setEnabled(b)))

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._handle_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._validate_substrate() # Validação Inicial

    def _validate_substrate(self):
        """Desativa o botão de fixadores se o substrato for menor que a peça."""
        is_valid = True
        try:
            sw, sd = float(self.sub_w.text()), float(self.sub_d.text())
        except ValueError:
            is_valid = False
            sw = sd = 0
            
        if hasattr(self, '_last_sw') and hasattr(self, '_last_sd'):
            if self._last_sw != sw or self._last_sd != sd:
                self.clamps = [] 
                
        self._last_sw = sw
        self._last_sd = sd
        # ----------------------------------------------------------------------------------
            
        if is_valid and self.chk_subst.isChecked() and self.model_bounds:
            xmin, ymin, zmin, xmax, ymax, zmax = self.model_bounds
            hw, hd = sw / 2.0, sd / 2.0
            if (xmin < -hw) or (xmax > hw) or (ymin < -hd) or (ymax > hd):
                is_valid = False 
                
        self.btn_posicionar.setEnabled(self.chk_subst.isChecked() and is_valid)

    def _handle_accept(self):
        self.result_sub_enabled = self.chk_subst.isChecked()
        try:
            self.result_sub_w = int(self.sub_w.text())
            self.result_sub_d = int(self.sub_d.text())
        except:
            self.result_sub_w, self.result_sub_d = 100, 100
        if self.rad1.isChecked(): 
            self.result_w, self.result_d = 1000, 1000
        elif self.rad2.isChecked(): 
            self.result_w, self.result_d = 700, 500
        elif self.rad3.isChecked(): 
            self.result_w, self.result_d = 1130, 800
        elif self.rad_custom.isChecked():
            try:
                self.result_w = int(self.custom_w.text())
                self.result_d = int(self.custom_d.text())
            except ValueError:
                QMessageBox.warning(self, "Erro", "Por favor, insira valores numéricos válidos.")
                return 
        self.accept()

    def abrir_posicionador(self):
        try:
            sw, sd = float(self.sub_w.text()), float(self.sub_d.text())
        except ValueError: 
            return
        
        viewer_ref = self.parent().viewer if hasattr(self.parent(), 'viewer') else None
        
        # --- CORREÇÃO DO BUG DO CANCELAR: Cria um backup seguro ---
        backup_clamps = [c.copy() for c in self.clamps]
        
        dlg = ClampPlacementDialog(sw, sd, self.model_bounds, self.clamps, viewer_ref, self)
        
        if dlg.exec_():
            self.clamps = [c.copy() for c in dlg.canvas.clamps]
        else:
            # Se cancelar, desfaz as alterações feitas ao vivo no motor 3D
            if viewer_ref:
                viewer_ref.set_clamps(backup_clamps)
# ────────────────────────────────────────────────────────────────────────────
# Editor 2D de Fixadores
# ────────────────────────────────────────────────────────────────────────────
class ClampEditorWidget(QWidget):
    def __init__(self, sub_w, sub_d, bounds, clamps, viewer=None): # Adicionado viewer
        super().__init__()
        self.setMouseTracking(True)
        self.sub_w, self.sub_d = sub_w, sub_d
        self.bounds = bounds
        self.clamps = clamps.copy()
        self.viewer = viewer # Salva a referência para usar a matemática do NumPy
        self.hover_clamp = None
        self.setMinimumSize(450, 450)
        
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        # --- DETECÇÃO INTELIGENTE DO TEMA ---
        is_dark = getattr(self.viewer, 'dark_mode', True) if self.viewer else True
        
        if is_dark:
            c_bg = QColor(22, 22, 32)               # Fundo igual ao 3D Dark
            c_sub_fill = QColor(100, 100, 120)      # Substrato escuro
            c_sub_line = QColor(80, 80, 100)
            c_clamp_fill = QColor(80, 80, 100)      # Fixador escuro
            c_clamp_line = QColor(40, 40, 50)
            c_alert_fill = QColor(255, 220, 0, 180) # Alerta Amarelo
            c_alert_line = QColor(200, 150, 0)
            c_alert_hover = QColor(255, 220, 0, 220)
        else:
            c_bg = QColor(240, 240, 248)            # Fundo igual ao 3D Light
            c_sub_fill = QColor(180, 180, 200)      # Substrato claro
            c_sub_line = QColor(140, 140, 160)
            c_clamp_fill = QColor(140, 140, 160)    # Fixador claro
            c_clamp_line = QColor(100, 100, 120)
            c_alert_fill = QColor(130, 0, 255, 180) # Alerta Roxo
            c_alert_line = QColor(100, 0, 200)
            c_alert_hover = QColor(130, 0, 255, 220)

        # Preenche o fundo do mapa com a cor correta
        p.fillRect(self.rect(), c_bg) 
        
        cx, cy = self.width() / 2, self.height() / 2
        s = min((self.width() - 80) / max(1, self.sub_w), (self.height() - 80) / max(1, self.sub_d))
        
        # Desenha o Substrato
        sw, sd = self.sub_w * s, self.sub_d * s
        p.setBrush(c_sub_fill)
        p.setPen(QPen(c_sub_line, 2))
        p.drawRect(QRectF(cx - sw/2, cy - sd/2, sw, sd))
        
        # Desenha os limites do GCode (A linha pontilhada azul)
        if self.bounds:
            xmin, ymin, zmin, xmax, ymax, zmax = self.bounds
            p.setBrush(QColor(34, 103, 252, 60 if is_dark else 30)) # Mais translúcido no claro
            p.setPen(QPen(QColor(34, 103, 252), 1, Qt.DashLine))
            p.drawRect(QRectF(cx + xmin * s, cy - ymax * s, (xmax - xmin) * s, (ymax - ymin) * s))
            
        def draw_clamp(c, is_hover=False):
            p.save()
            p.translate(cx + c['x'] * s, cy - c['y'] * s)
            p.rotate(-c['angle'])
            cw, cd = 20 * s, 30 * s
            
            color_alert = c_alert_fill if not is_hover else c_alert_hover
            
            if is_hover:
                if getattr(self, 'hover_valid', True):
                    # Verde para posicionamento válido
                    p.setBrush(QColor(100, 255, 100, 150) if is_dark else QColor(50, 200, 50, 150))
                    p.setPen(QPen(QColor(50, 200, 50) if is_dark else QColor(20, 150, 20), 2))
                else:
                    # Vermelho para sobreposição de fixadores
                    p.setBrush(QColor(255, 100, 100, 150) if is_dark else QColor(220, 50, 50, 150))
                    p.setPen(QPen(QColor(200, 50, 50) if is_dark else QColor(180, 20, 20), 2))
            elif c.get('collision', False): 
                # Amarelo/Roxo para colisão com a trajetória de solda
                p.setBrush(color_alert)
                p.setPen(QPen(c_alert_line, 2))
            else:
                # Cor normal do fixador na mesa
                p.setBrush(c_clamp_fill)
                p.setPen(QPen(c_clamp_line, 2))
            
            p.drawRect(QRectF(-cw/2, -cd/2, cw, cd))
            p.restore()
            
        # Pinta primeiro todos que já estão posicionados, depois o que está no mouse
        for c in self.clamps: draw_clamp(c)
        if self.hover_clamp:  draw_clamp(self.hover_clamp, is_hover=True)

    def mouseMoveEvent(self, event):
        cx, cy = self.width() / 2, self.height() / 2
        s = min((self.width() - 80) / max(1, self.sub_w), (self.height() - 80) / max(1, self.sub_d))
        px, py = (event.x() - cx) / s, -(event.y() - cy) / s
        hw, hd = self.sub_w / 2, self.sub_d / 2
        
        edges = [
            (abs(py - hd), hd, max(-hw, min(hw, px)), 180),
            (abs(py - (-hd)), -hd, max(-hw, min(hw, px)), 0),
            (abs(px - hw), max(-hd, min(hd, py)), hw, 90),
            (abs(px - (-hw)), max(-hd, min(hd, py)), -hw, -90)
        ]
        
        min_dist, c_y, c_x, angle = min(edges, key=lambda e: e[0])
        
        if min_dist > 30:
            self.hover_clamp = None
        else:
            self.hover_clamp = {'x': c_x, 'y': c_y, 'angle': angle}
            # REAJUSTE: Verifica validade (colisão) para mudar a cor no PaintEvent
            self.hover_valid = True
            for c in self.clamps:
                dist = math.hypot(c['x'] - c_x, c['y'] - c_y)
                if dist < 20.0:
                    self.hover_valid = False
                    break
                    
        self.update()
        
    def mousePressEvent(self, event):
            if event.button() == Qt.LeftButton and self.hover_clamp:
                # --- PROTEÇÃO CONTRA SOBREPOSIÇÃO (Anti-Stacking) ---
                pode_colocar = True
                for c in self.clamps:
                    # Calcula a distância física (em mm) entre os centros
                    dist = math.hypot(c['x'] - self.hover_clamp['x'], c['y'] - self.hover_clamp['y'])
                    
                    # O fixador tem 20mm de largura. Se a distância for menor que isso, eles vão se bater.
                    if dist < 20.0: 
                        pode_colocar = False
                        break
                
                if pode_colocar:
                    self.clamps.append(self.hover_clamp)
                # ----------------------------------------------------
                
            elif event.button() == Qt.RightButton:
                cx, cy = self.width() / 2, self.height() / 2
                s = min((self.width() - 80) / max(1, self.sub_w), (self.height() - 80) / max(1, self.sub_d))
                px, py = (event.x() - cx) / s, -(event.y() - cy) / s
                
                for c in reversed(self.clamps): # Inverte para checar o último desenhado
                    dx, dy = px - c['x'], py - c['y']
                    rad = math.radians(-c['angle'])
                    # Rotaciona o clique para alinhar com a geometria do fixador
                    lx = dx * math.cos(rad) - dy * math.sin(rad)
                    ly = dx * math.sin(rad) + dy * math.cos(rad)
                    
                    if abs(lx) <= 10 and abs(ly) <= 15: # Colisão com a caixa 20x30
                        self.clamps.remove(c)
                        break
            if self.viewer:
                self.viewer.clamps = self.clamps
                self.viewer._check_clamp_collisions()
            self.update()

class ClampPlacementDialog(QDialog):
    # Adicionamos o 'viewer' nos argumentos recebidos
    def __init__(self, sub_w, sub_d, bounds, clamps, viewer, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Posicionamento de Fixadores - Laprosolda")
        layout = QVBoxLayout(self)
        
        lbl = QLabel("<b>Botão Esquerdo:</b> Adicionar Fixador | <b>Botão Direito:</b> Remover Fixador<br>Passe o mouse próximo às bordas para visualizar.")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)
        
        # Repassa o viewer para o Canvas (onde a colisão é calculada)
        self.canvas = ClampEditorWidget(sub_w, sub_d, bounds, clamps, viewer)
        layout.addWidget(self.canvas)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

class GCodeLoaderThread(QThread):
    """
    OTIMIZAÇÃO: Move o carregamento e o parse O(N) para uma thread secundária.
    Resolve o congelamento da interface (Bloqueante) em arquivos grandes.
    """
    finished = pyqtSignal(object, str)
    error = pyqtSignal(str)

    def __init__(self, parser, path, grid_w, grid_d):
        super().__init__()
        self.parser = parser
        self.path = path
        self.grid_w = grid_w
        self.grid_d = grid_d

    def run(self):
        try:
            # 1. Resolve parcialmente o duplo IO (O(L)x2): Lemos o texto na thread.
            # Como o parser.parse() roda na sequência, o Sistema Operacional 
            # servirá o arquivo diretamente da memória RAM (Cache de Disco), 
            # tornando a segunda leitura praticamente instantânea.
            with open(self.path, 'r', encoding='utf-8', errors='replace') as f:
                raw_text = f.read()
            
            # 2. Faz o parse matemático em segundo plano
            model = self.parser.parse(self.path, self.grid_w, self.grid_d)
            
            # 3. Envia os dados prontos de volta para a interface principal
            self.finished.emit(model, raw_text)
        except Exception as e:
            self.error.emit(str(e))

# ────────────────────────────────────────────────────────────────────────────
# Janela principal
# ────────────────────────────────────────────────────────────────────────────

class editor_grafico(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ui = Ui_editor_grafico()
        self.ui.setupUi(self)
        self._selected_line = 1

        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )

        self.parser = GCodeParser()
        self.model  = None

        # Viewer 3D
        self.viewer = GCodeViewer3D(self)
        # Coloca o viewer dentro do placeholder (que ja esta no splitter_v)
        placeholder_layout = QVBoxLayout(self.ui.grafico)
        placeholder_layout.setContentsMargins(0, 0, 0, 0)
        placeholder_layout.addWidget(self.viewer)
        self.viewer.on_segment_changed = self._on_segment_changed
        self.viewer.on_layer_changed   = self._on_layer_changed
        self.viewer.fps_changed.connect(self.atualizar_titulo_fps)

        self.viewer.show_travel   = True

        # Aplica tema inicial
        self._dark_mode = True
        self._apply_theme(self._dark_mode)

        # ── Conexoes ─────────────────────────────────────────────────────────
        self.ui.importbut.clicked.connect(self.importar_gcode)
        self.ui.exportbut.clicked.connect(self.exportar_imagem)
        self.ui.fullscreembut.clicked.connect(self.tela_cheia)
        self.ui.darkModeToggle.toggled.connect(self._toggle_dark_mode)

        # Inicializa o botão silenciosamente
        self.ui.darkModeToggle.blockSignals(True)
        self.ui.darkModeToggle.setChecked(self._dark_mode)
        self.ui.darkModeToggle.blockSignals(False)
        
        # Simulacao
        self.ui.playbut.clicked.connect(self.iniciar_simulacao)
        self.ui.stopbut.clicked.connect(self.parar_simulacao)
        self.ui.voltarbut.clicked.connect(self.retroceder_simulacao)
        self.ui.voltarbut.setText("◀◀")
        self.ui.prev_linebut.clicked.connect(self.linha_anterior)
        self.ui.next_linebut.clicked.connect(self.proxima_linha)

        # Camadas
        self.ui.camdinfBut.clicked.connect(self.layer_anterior)
        self.ui.camdsupBut.clicked.connect(self.layer_seguinte)
        self.ui.chkIsolate.toggled.connect(self._toggle_isolate)
        self.ui.chkAutoLayer.toggled.connect(self._toggle_auto_layer)

        # Modo
        self.ui.camadasRadio.toggled.connect(self.modo_camadas)
        self.ui.objetoRadio.toggled.connect(self.modo_objeto)

        # Velocidade
        self.ui.velocidadebar.valueChanged.connect(self.ajustar_velocidade)
        self.ajustar_velocidade(self.ui.velocidadebar.value())

        # Clique no codigo -> highlight no viewer
        self.ui.codigo.cursorPositionChanged.connect(self._on_code_cursor_changed)

        self.ui.configbut.setEnabled(True)

        self._set_controls_enabled(False)

        # Configurações
        self.clamps = []
        self.ui.configbut.clicked.connect(self.abrir_configuracoes)
        self.grid_w = 500
        self.grid_d = 500

    # ────────────────────────────────────────────────────────────────────────
    # Tema dark/light
    # ────────────────────────────────────────────────────────────────────────

    def _toggle_dark_mode(self, checked: bool):
        self._dark_mode = checked
        self._apply_theme(checked)

    def _apply_theme(self, dark: bool):
        t = DARK_THEME if dark else LIGHT_THEME
        self.setStyleSheet(build_stylesheet(t))

        # Atualiza label do toggle
        lbl = self.findChild(QLabel, "lbl_dark_mode")
        if lbl:
            lbl.setText(t["label_dm"])

        # Cor de fundo do viewer e flag de tema
        self.viewer.color_background = t["viewer_bg"]
        self.viewer.dark_mode = dark
        if dark:
            self.viewer.color_extrude = QColor(14, 83, 222)   
            self.viewer.color_travel  = QColor(220, 60, 60, 100)
            self.viewer.color_extrude_old = QColor( 20,  50, 110)
            self.viewer.color_travel_old  = QColor(100,  25,  25)
            self.viewer.color_extrude_dim = QColor( 10,  33,  80)
            self.viewer.color_travel_dim  = QColor( 75,  15,  15)
        else:
            self.viewer.color_extrude = QColor(14, 83, 222)   
            self.viewer.color_travel  = QColor(220, 60, 60, 100)
            self.viewer.color_extrude_old = QColor(175, 205, 255)
            self.viewer.color_travel_old  = QColor(255, 160, 160)
            self.viewer.color_extrude_dim = QColor(205, 225, 255)
            self.viewer.color_travel_dim  = QColor(255, 190, 190)
        self.viewer._dirty = True

        # Atualiza cor de acento dos labels de camada/linha
        accent = t["accent"]
        self.ui.lbl_layer.setStyleSheet(f"color: {accent}; font-size: 13px; min-width: 44px;")

    # ────────────────────────────────────────────────────────────────────────
    # Importar GCode
    # ────────────────────────────────────────────────────────────────────────

    def importar_gcode(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Abrir GCode', '', '*.gcode *.nc *.txt'
        )
        if not path:
            return
        
        self.parar_simulacao()
            
        self.current_file_path = path
        
        # Desabilita a interface durante o carregamento para evitar crash
        self._set_controls_enabled(False)
        self.ui.codigo.setLineWrapMode(self.ui.codigo.NoWrap)
        self.ui.codigo.setPlainText("Carregando arquivo e calculando matrizes 3D...\nIsso pode levar alguns segundos em arquivos grandes. Aguarde.")
        self.ui.lbl_info.setText("Processando...")

        # Inicia a Thread Secundária
        self.loader_thread = GCodeLoaderThread(self.parser, path, self.grid_w, self.grid_d)
        self.loader_thread.finished.connect(self._on_import_finished)
        self.loader_thread.error.connect(self._on_import_error)
        self.loader_thread.start()

    def _on_import_finished(self, model, raw_text):
        self.model = model
        self.ui.codigo.setPlainText(raw_text)
        self.ui.objetoRadio.setChecked(True)
        self.ui.chkIsolate.setChecked(False)
        self.viewer.set_model(self.model)
        self._update_info()
        self._update_layer_label()
        self._set_controls_enabled(True)

    def _on_import_error(self, err_msg):
        QMessageBox.critical(self, "Erro ao abrir arquivo", err_msg)
        self.ui.codigo.setPlainText(f"Erro no carregamento: {err_msg}")
        self._set_controls_enabled(True)
        self.ui.lbl_info.setText("Erro")

    # ────────────────────────────────────────────────────────────────────────
    # Exportar imagem
    # ────────────────────────────────────────────────────────────────────────

    def exportar_imagem(self):
        if self.model is None:
            QMessageBox.warning(self, "Aviso", "Nenhum modelo carregado.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Salvar Imagem', 'gcode_render.png', '*.png *.jpg'
        )
        if not path:
            return
        pixmap = self.viewer.grab()
        if pixmap.save(path):
            QMessageBox.information(self, "Exportado", f"Imagem salva em:\n{path}")
        else:
            QMessageBox.critical(self, "Erro", "Falha ao salvar a imagem.")

    # ────────────────────────────────────────────────────────────────────────
    # Selecao de linha no codigo -> highlight 3D
    # ────────────────────────────────────────────────────────────────────────

    def _on_code_cursor_changed(self):
        cursor = self.ui.codigo.textCursor()
        line   = cursor.blockNumber() + 1   # 1-based
        
        # OTIMIZAÇÃO: Evita recálculo O(N) desnecessário no render 3D.
        # Se o cursor apenas andou para os lados na MESMA linha vertical, encerra a função.
        if getattr(self, '_selected_line', -1) == line:
            return
            
        self._selected_line = line 

        self.ui.lbl_current_line.setText(f"Linha: {line}")
        if self.model is not None:
            self.viewer.highlight_line(line)

    # ────────────────────────────────────────────────────────────────────────
    # Simulacao
    # ────────────────────────────────────────────────────────────────────────

    # -- helpers de estado dos botoes -----------------------------------------

    def _reset_playbut(self):
        """Coloca playbut no estado parado (playbut -> iniciar_simulacao)."""
        self.ui.playbut.setText("▶▶")
        try:
            self.ui.playbut.clicked.disconnect()
        except TypeError:
            pass
        self.ui.playbut.clicked.connect(self.iniciar_simulacao)

    def _reset_voltarbut(self):
        """Coloca voltarbut no estado parado (voltarbut -> retroceder_simulacao)."""
        self.ui.voltarbut.setText("◀◀")
        try:
            self.ui.voltarbut.clicked.disconnect()
        except TypeError:
            pass
        self.ui.voltarbut.clicked.connect(self.retroceder_simulacao)

    # -- acoes de simulacao ---------------------------------------------------

    def iniciar_simulacao(self):
        if self.model is None:
            return
        
        if hasattr(self, "_selected_line"):
            self.viewer.set_simulation_from_line(self._selected_line)

        self.viewer.iniciar_simulacao()
        self._reset_voltarbut()   # sincroniza voltarbut se estava em modo reverso
        self.ui.playbut.setText("⏸")
        self.ui.playbut.clicked.disconnect()
        self.ui.playbut.clicked.connect(self._pausar_simulacao)

    def _pausar_simulacao(self):
        self.viewer.parar_simulacao()
        self._reset_playbut()

    def parar_simulacao(self):
        self.viewer.resetar_simulacao()
        self._reset_playbut()
        self._reset_voltarbut()
        self.ui.lbl_current_line.setText("Linha: —")

    def retroceder_simulacao(self):
        """Inicia simulacao reversa — espelho exato do iniciar_simulacao."""
        if self.model is None:
            return
        
        if hasattr(self, "_selected_line"):
            self.viewer.set_simulation_from_line(self._selected_line)

        self.viewer.iniciar_reverso()
        self._reset_playbut()   # sincroniza playbut se estava em modo forward
        self.ui.voltarbut.setText("⏸")
        self.ui.voltarbut.clicked.disconnect()
        self.ui.voltarbut.clicked.connect(self._pausar_reverso)

    def _pausar_reverso(self):
        """Pausa a simulacao reversa — espelho exato do _pausar_simulacao."""
        self.viewer.parar_reverso()
        self._reset_voltarbut()

    def proxima_linha(self):
        if self.model is None:
            return
        n = len(self.model.segments)
        if self.viewer._sim_index < n - 1:
            self.viewer._sim_index += 1
            self.viewer._notify_segment()
            self.viewer._dirty = True

    def linha_anterior(self):
        if self.model is None:
            return
        if self.viewer._sim_index > 0:
            self.viewer._sim_index -= 1
            self.viewer._notify_segment()
            self.viewer._dirty = True
        elif self.viewer._sim_index == 0:
            self.viewer._sim_index = -1
            self.viewer._dirty = True

    def _on_segment_changed(self, seg):
        """Chamado pelo viewer quando o segmento da simulacao muda."""
        self.ui.lbl_current_line.setText(f"Linha: {seg.line_number}")
        doc   = self.ui.codigo.document()
        block = doc.findBlockByLineNumber(seg.line_number - 1)
        if block.isValid():
            cursor = self.ui.codigo.textCursor()
            cursor.setPosition(block.position())
            self.ui.codigo.setTextCursor(cursor)
            self.ui.codigo.ensureCursorVisible()

    def _on_layer_changed(self, layer_index: int):
        """Chamado pelo viewer quando auto-camada detecta mudanca de Z."""
        self._update_layer_label()

    # ────────────────────────────────────────────────────────────────────────
    # Camadas
    # ────────────────────────────────────────────────────────────────────────

    def _toggle_auto_layer(self, checked: bool):
        self.viewer.auto_layer = checked
        # Auto-camada so faz sentido no modo camadas
        if checked and self.ui.objetoRadio.isChecked():
            self.ui.camadasRadio.setChecked(True)

    def layer_anterior(self):
        if self.model is None:
            return
        self.viewer.layer_anterior()
        self._update_layer_label()

    def layer_seguinte(self):
        if self.model is None:
            return
        self.viewer.layer_seguinte()
        self._update_layer_label()

    def _toggle_isolate(self, checked: bool):
        self.viewer.layer_isolated = checked
        self.viewer._dirty = True

    def _update_layer_label(self):
        if self.model is None:
            self.ui.lbl_layer.setText("—")
            return
        lyr = self.viewer.current_layer
        if lyr < 0:
            self.ui.lbl_layer.setText("Todas")
        else:
            total = self.model.layer_count
            self.ui.lbl_layer.setText(f"{lyr + 1}/{total}")

    # ────────────────────────────────────────────────────────────────────────
    # Modo de visualizacao
    # ────────────────────────────────────────────────────────────────────────

    def modo_camadas(self, checked):
        if not checked:
            return
        if self.model is None:
            return
        if self.viewer.current_layer < 0:
            self.viewer.set_layer(0)
        self.ui.camdinfBut.setEnabled(True)
        self.ui.camdsupBut.setEnabled(True)
        self.ui.chkIsolate.setEnabled(True)
        self.ui.chkAutoLayer.setEnabled(True)
        self._update_layer_label()

    def modo_objeto(self, checked):
        if not checked:
            return
        self.viewer.set_layer(-1)
        self.ui.camdinfBut.setEnabled(False)
        self.ui.camdsupBut.setEnabled(False)
        self.ui.chkIsolate.setEnabled(False)
        self.ui.chkAutoLayer.setEnabled(False)
        self._update_layer_label()

    # ────────────────────────────────────────────────────────────────────────
    # Velocidade
    # ────────────────────────────────────────────────────────────────────────

    def ajustar_velocidade(self, value):
        if value <= 50:
            ms = int(200 - (value * 3))
        else:
            ms = int(50 - ((value - 50) * 0.9))
        ms = max(5, min(200, ms))
        self.viewer.set_sim_speed(ms)
        self.ui.lbl_speed.setText(f"Velocidade: {value}%")

    # ────────────────────────────────────────────────────────────────────────
    # UI helpers
    # ────────────────────────────────────────────────────────────────────────

    def _set_controls_enabled(self, enabled: bool):
        for w in (self.ui.exportbut, self.ui.playbut, self.ui.stopbut,
                  self.ui.voltarbut, self.ui.prev_linebut, self.ui.next_linebut,
                  self.ui.velocidadebar):
            w.setEnabled(enabled)
        in_layer = self.ui.camadasRadio.isChecked()
        self.ui.camdinfBut.setEnabled(enabled and in_layer)
        self.ui.camdsupBut.setEnabled(enabled and in_layer)
        self.ui.chkIsolate.setEnabled(enabled and in_layer)
        self.ui.chkAutoLayer.setEnabled(enabled and in_layer)

    def _update_info(self):
        if self.model is None:
            self.ui.lbl_info.setText("Nenhum arquivo carregado")
            return
        b = self.model.bounds
        dims = ""
        if b:
            w = b[3]-b[0]; d = b[4]-b[1]; h = b[5]-b[2]
            dims = f"Dim: {w:.1f} x {d:.1f} x {h:.1f} mm\n"
        info = (f"Segmentos: {len(self.model.segments)}\n"
                f"Camadas: {self.model.layer_count}\n"
                f"{dims}"
                f"Percurso: {self.model.total_length:.0f} mm")
        self.ui.lbl_info.setText(info)

    def tela_cheia(self):
        if self.isFullScreen():
            self.showNormal()
            self.ui.fullscreembut.setText("⛶  Tela Cheia")
        else:
            self.showFullScreen()
            self.ui.fullscreembut.setText("⊡  Janela Normal")

    def atualizar_titulo_fps(self, fps):
        """Atualiza a barra superior da janela do Windows com o FPS."""
        self.setWindowTitle(f"Leitor GCode — Laprosolda | FPS: {fps}")

    def abrir_configuracoes(self):
        # --- REAJUSTE DA SIMULAÇÃO: Força a PAUSA em vez do STOP ---
        self._pausar_simulacao()
        self._pausar_reverso()
        # -----------------------------------------------------------

        bnds = self.model.bounds if self.model else None
        
        # --- CORREÇÃO DO BUG DO CANCELAR: Backup dos fixadores originais ---
        backup_clamps = [c.copy() for c in self.clamps]
        
        dlg = ConfigDialog(self.grid_w, self.grid_d, bnds, self) 
        
        if dlg.exec_():
            # (Removemos o self.parar_simulacao() daqui para não zerar a linha)

            self.clamps = dlg.clamps

            self.grid_w = dlg.result_w
            self.grid_d = dlg.result_d

            self.substrate_enabled = dlg.result_sub_enabled
            self.substrate_w = dlg.result_sub_w
            self.substrate_d = dlg.result_sub_d

            self.viewer.set_clamps(self.clamps)

            self.viewer.substrate_enabled = self.substrate_enabled
            self.viewer.substrate_w = self.substrate_w
            self.viewer.substrate_d = self.substrate_d

            if hasattr(self, 'current_file_path'): 
                self._layer_backup = self.viewer.current_layer
                self.recarregar_modelo()
            
            self.viewer._dirty = True
        else:
            # --- CANCELOU GERAL: Restaura o 3D para como era antes de abrir a tela ---
            self.viewer.set_clamps(backup_clamps)

    def recarregar_modelo(self):
        if not hasattr(self, 'current_file_path'): 
            return
            
        self._set_controls_enabled(False)
        self.ui.lbl_info.setText("Recalculando grid...")
        
        self.loader_thread = GCodeLoaderThread(self.parser, self.current_file_path, self.grid_w, self.grid_d)
        self.loader_thread.finished.connect(self._on_reload_finished)
        self.loader_thread.error.connect(self._on_import_error)
        self.loader_thread.start()

    def _on_reload_finished(self, model, raw_text):
        self.model = model
        self.viewer.set_model(self.model, preserve_camera=True)
        if self.ui.camadasRadio.isChecked():
            if hasattr(self, '_layer_backup'):
                self.viewer.set_layer(self._layer_backup)
            self.viewer.layer_isolated = self.ui.chkIsolate.isChecked()
        self._update_layer_label()
        self._update_info()
        self._set_controls_enabled(True)

    def showEvent(self, event):
        super().showEvent(event)
        
        # --- A SOLUÇÃO DEFINITIVA DO PRIMEIRO CLIQUE ---
        # Como a janela agora já existe, o botão sabe a própria largura.
        # Nós o invertemos e desinvertemos silenciosamente para forçar
        # o cálculo exato de onde a "bolinha" deve ficar.
        if hasattr(self.ui, 'darkModeToggle'):
            self.ui.darkModeToggle.blockSignals(True)
            self.ui.darkModeToggle.setChecked(not self._dark_mode)
            self.ui.darkModeToggle.setChecked(self._dark_mode)
            self.ui.darkModeToggle.blockSignals(False)

    def closeEvent(self, event):
        super().closeEvent(event)


# ────────────────────────────────────────────────────────────────────────────
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QSurfaceFormat

if __name__ == '__main__':
    # 1. Prepara o "Canvas" do PyQt5 para suportar frações de pixel (MSAA 8x)
    fmt = QSurfaceFormat()
    fmt.setSamples(8) # Liga o Anti-Aliasing de hardware no máximo
    fmt.setSwapInterval(0)
    fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
    QSurfaceFormat.setDefaultFormat(fmt)

    # 2. Destrava o OpenGL nativo do Windows
    QApplication.setAttribute(Qt.AA_UseDesktopOpenGL)

    # 3. Cria o motor da aplicação
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 4. Cria a janela do seu editor
    window = editor_grafico()
    window.show()

    # 5. Inicia o loop do programa
    sys.exit(app.exec_())