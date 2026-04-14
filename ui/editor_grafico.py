# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtGui, QtWidgets


class ToggleSwitch(QtWidgets.QAbstractButton):
    """Toggle switch estilo iOS para dark/light mode."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.substrate_enabled = False
        self.substrate_w = 150
        self.substrate_d = 150
        self.setCheckable(True)
        self.setFixedSize(44, 22)
        self._offset_val = 3
        self._anim = QtCore.QPropertyAnimation(self, b"_offset", self)
        self._anim.setDuration(150)

    def _get_offset(self): return self._offset_val
    def _set_offset(self, v):
        self._offset_val = v
        self.update()
    _offset = QtCore.pyqtProperty(int, _get_offset, _set_offset)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == QtCore.Qt.LeftButton:
            target = 23 if self.isChecked() else 3
            self._anim.setStartValue(self._offset_val)
            self._anim.setEndValue(target)
            self._anim.start()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        # Track
        track_color = QtGui.QColor(34, 103, 252) if self.isChecked() else QtGui.QColor(80, 80, 100)
        p.setBrush(QtGui.QBrush(track_color))
        p.setPen(QtCore.Qt.NoPen)
        p.drawRoundedRect(0, 0, w, h, h//2, h//2)
        # Thumb
        p.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        thumb_size = h - 6
        p.drawEllipse(self._offset_val, 3, thumb_size, thumb_size)


class Ui_editor_grafico(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("editor_grafico")
        Dialog.resize(1140, 720)
        Dialog.setMinimumSize(800, 500)

        self._grp_style = (
            "QGroupBox { color: #8888a0; border: 1px solid #2a2a3a; border-radius:4px;"
            " margin-top:8px; padding-top:4px; }"
            " QGroupBox::title { subcontrol-origin: margin; left: 8px; }"
        )

        # Layout principal com splitters redimensionaveis
        root_layout = QtWidgets.QVBoxLayout(Dialog)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(0)

        # Splitter horizontal: painel esquerdo | area direita
        self.splitter_h = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter_h.setHandleWidth(5)
        self.splitter_h.setChildrenCollapsible(False)

        # Splitter vertical: viewer | controles inferiores
        self.splitter_v = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.splitter_v.setHandleWidth(5)
        self.splitter_v.setChildrenCollapsible(False)

        # ── Painel esquerdo ────────────────────────────────────────────────
        self.panel_left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(self.panel_left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        # Cabecalho + toggle dark mode
        header_row = QtWidgets.QHBoxLayout()
        col_title = QtWidgets.QVBoxLayout()
        lbl_title = QtWidgets.QLabel("LEITOR GCODE")
        lbl_title.setStyleSheet("color: #2267fc; font-size: 13px; font-weight: bold; letter-spacing: 2px;")
        lbl_sub   = QtWidgets.QLabel("Laprosolda")
        lbl_sub.setStyleSheet("color: #555566; font-size: 10px; letter-spacing: 1px;")
        col_title.addWidget(lbl_title)
        col_title.addWidget(lbl_sub)
        header_row.addLayout(col_title)
        header_row.addStretch()

        # Dark/Light toggle
        toggle_col = QtWidgets.QVBoxLayout()
        self.darkModeToggle = ToggleSwitch()
        self.darkModeToggle.setChecked(True)
        lbl_dm = QtWidgets.QLabel("Dark")
        lbl_dm.setObjectName("lbl_dark_mode")
        lbl_dm.setAlignment(QtCore.Qt.AlignCenter)
        lbl_dm.setStyleSheet("color: #8888a0; font-size: 9px;")
        toggle_col.addWidget(self.darkModeToggle)
        toggle_col.addWidget(lbl_dm)
        header_row.addLayout(toggle_col)
        left_layout.addLayout(header_row)

        sep1 = QtWidgets.QFrame(); sep1.setFrameShape(QtWidgets.QFrame.HLine)
        left_layout.addWidget(sep1)

        # Botoes de arquivo
        self.importbut = QtWidgets.QPushButton("⬆  Importar GCode")
        self.exportbut = QtWidgets.QPushButton("⬇  Exportar Imagem")
        self.configbut = QtWidgets.QPushButton("⚙  Configuracoes")
        for b in (self.importbut, self.exportbut, self.configbut):
            left_layout.addWidget(b)

        sep2 = QtWidgets.QFrame(); sep2.setFrameShape(QtWidgets.QFrame.HLine)
        left_layout.addWidget(sep2)

        # Codigo
        lbl_code = QtWidgets.QLabel("CODIGO GCODE")
        lbl_code.setStyleSheet("color: #555566; font-size: 10px; letter-spacing: 1px;")
        left_layout.addWidget(lbl_code)

        self.codigo = QtWidgets.QPlainTextEdit()
        self.codigo.setReadOnly(True)
        self.codigo.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        left_layout.addWidget(self.codigo)

        sep3 = QtWidgets.QFrame(); sep3.setFrameShape(QtWidgets.QFrame.HLine)
        left_layout.addWidget(sep3)

        self.lbl_info = QtWidgets.QLabel("Nenhum arquivo carregado")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet("color: #555566; font-size: 10px; padding: 4px 0;")
        left_layout.addWidget(self.lbl_info)

        self.splitter_h.addWidget(self.panel_left)

        # ── Viewport (substituido pelo GCodeViewer3D em main.py) ─────────
        self.grafico = QtWidgets.QWidget(Dialog)
        self.grafico.setObjectName("grafico")
        self.grafico.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.splitter_v.addWidget(self.grafico)

        # ── Barra inferior ─────────────────────────────────────────────────
        self.panel_controls = QtWidgets.QWidget()
        self.panel_controls.setMinimumHeight(95)
        ctrl = QtWidgets.QGridLayout(self.panel_controls)
        ctrl.setContentsMargins(4, 4, 4, 4)
        ctrl.setSpacing(4)

        # Modo
        grp_mode = QtWidgets.QGroupBox("Modo")
        grp_mode.setStyleSheet(self._grp_style)
        mode_lay = QtWidgets.QVBoxLayout(grp_mode)
        mode_lay.setContentsMargins(6, 2, 6, 2)
        mode_lay.setSpacing(2)
        self.objetoRadio  = QtWidgets.QRadioButton("Objeto Completo")
        self.camadasRadio = QtWidgets.QRadioButton("Por Camadas")
        self.objetoRadio.setChecked(True)
        mode_lay.addWidget(self.objetoRadio)
        mode_lay.addWidget(self.camadasRadio)
        ctrl.addWidget(grp_mode, 0, 0, 2, 1)

        # Camadas
        grp_layer = QtWidgets.QGroupBox("Camadas")
        grp_layer.setStyleSheet(self._grp_style)
        layer_lay = QtWidgets.QVBoxLayout(grp_layer)
        layer_lay.setContentsMargins(6, 2, 6, 4)
        layer_row = QtWidgets.QHBoxLayout()
        self.camdinfBut = QtWidgets.QPushButton("◀"); self.camdinfBut.setFixedWidth(32)
        self.lbl_layer  = QtWidgets.QLabel("—")
        self.lbl_layer.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_layer.setStyleSheet("color: #2267fc; font-size: 13px; min-width: 44px;")
        self.camdsupBut = QtWidgets.QPushButton("▶"); self.camdsupBut.setFixedWidth(32)
        layer_row.addWidget(self.camdinfBut)
        layer_row.addWidget(self.lbl_layer)
        layer_row.addWidget(self.camdsupBut)
        layer_lay.addLayout(layer_row)
        self.chkIsolate = QtWidgets.QCheckBox("Isolar camada")
        self.chkIsolate.setStyleSheet("font-size: 10px;")
        layer_lay.addWidget(self.chkIsolate)
        self.chkAutoLayer = QtWidgets.QCheckBox("Auto-camada")
        self.chkAutoLayer.setStyleSheet("font-size: 10px;")
        self.chkAutoLayer.setEnabled(False)
        layer_lay.addWidget(self.chkAutoLayer)
        ctrl.addWidget(grp_layer, 0, 1, 2, 1)

        # Playback
        grp_play = QtWidgets.QGroupBox("Simulacao")
        grp_play.setStyleSheet(self._grp_style)
        play_lay = QtWidgets.QHBoxLayout(grp_play)
        play_lay.setContentsMargins(6, 2, 6, 2)
        play_lay.setSpacing(4)
        self.voltarbut    = QtWidgets.QPushButton("◀◀"); self.voltarbut.setFixedWidth(36)
        self.stopbut      = QtWidgets.QPushButton("■");  self.stopbut.setFixedWidth(36)
        self.playbut      = QtWidgets.QPushButton("▶▶");  self.playbut.setFixedWidth(36)
        self.prev_linebut = QtWidgets.QPushButton("◀");  self.prev_linebut.setFixedWidth(32)
        self.next_linebut = QtWidgets.QPushButton("▶");  self.next_linebut.setFixedWidth(32)
        _play_style = ("QPushButton { color: #2267fc; font-size: 14px; border-color: #1a3a6a; }"
                       "QPushButton:hover { border-color: #2267fc; }"
                       "QPushButton:pressed { background: #2267fc; color: #16161f; }")
        self.playbut.setStyleSheet(_play_style)
        self.voltarbut.setStyleSheet(_play_style)
        self.stopbut.setStyleSheet("QPushButton { color: #dc3c3c; font-size: 14px; border-color: #5a1a1a; }"
                                   "QPushButton:hover { border-color: #dc3c3c }"
                                   "QPushButton:pressed { background: #dc3c3c; color: #16161f; }")
        sep_v = QtWidgets.QFrame(); sep_v.setFrameShape(QtWidgets.QFrame.VLine)
        for w in (self.voltarbut, self.stopbut, self.playbut, sep_v,
                  self.prev_linebut, self.next_linebut):
            play_lay.addWidget(w)
        ctrl.addWidget(grp_play, 0, 2, 2, 1)

        # Velocidade
        grp_speed = QtWidgets.QGroupBox("Velocidade da Simulacao")
        grp_speed.setStyleSheet(self._grp_style)
        speed_lay = QtWidgets.QVBoxLayout(grp_speed)
        speed_lay.setContentsMargins(6, 2, 6, 2)
        self.velocidadebar = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.velocidadebar.setRange(1, 100)
        self.velocidadebar.setValue(50)
        self.lbl_speed = QtWidgets.QLabel("Velocidade: 50%")
        self.lbl_speed.setAlignment(QtCore.Qt.AlignCenter)
        speed_lay.addWidget(self.velocidadebar)
        speed_lay.addWidget(self.lbl_speed)
        ctrl.addWidget(grp_speed, 0, 3, 2, 1)

        # Fullscreen + linha atual
        self.fullscreembut = QtWidgets.QPushButton("⛶  Tela Cheia")
        ctrl.addWidget(self.fullscreembut, 0, 4, 1, 1)
        self.lbl_current_line = QtWidgets.QLabel("Linha: —")
        self.lbl_current_line.setStyleSheet("color: #8888a0; font-size: 10px;")
        ctrl.addWidget(self.lbl_current_line, 1, 4, 1, 1)

        self.splitter_v.addWidget(self.panel_controls)

        # Montar splitters no layout raiz
        self.splitter_h.addWidget(self.splitter_v)
        self.splitter_h.setStretchFactor(0, 0)   # painel esquerdo nao estica
        self.splitter_h.setStretchFactor(1, 1)   # area direita estica
        self.splitter_v.setStretchFactor(0, 1)   # viewer estica
        self.splitter_v.setStretchFactor(1, 0)   # controles nao esticam
        root_layout.addWidget(self.splitter_h)

        self.retranslateUi(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle("Leitor GCode — Laprosolda")


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    Dialog = QtWidgets.QDialog()
    ui = Ui_editor_grafico()
    ui.setupUi(Dialog)
    Dialog.show()
    sys.exit(app.exec_())