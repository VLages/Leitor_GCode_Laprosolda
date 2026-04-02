from PyQt5.QtWidgets import QApplication, QWidget, QPushButton
from PyQt5.Qt import Qt
from PyQt5.QtCore import pyqtSlot
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtPrintSupport import *
import os, sys

from ui.editor_grafico import Ui_editor_grafico
from motor_3d.gcode_parser import GCodeParser
from motor_3d.render.viewer import GCodeViewer3D

class editor_grafico(QDialog):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.ui = Ui_editor_grafico()
        self.ui.setupUi(self)
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.ui.fullscreembut.clicked.connect(self.tela_cheia)
        self.ui.grafico
        self.parser = GCodeParser()
        self.model = None
        self.viewer = GCodeViewer3D(self)
        self.ui.gridLayout_2.replaceWidget(self.ui.grafico, self.viewer)
        self.ui.grafico.hide()
        self.ui.importbut.clicked.connect(self.importar_gcode)
        #self.ui.playbut.clicked.connect(self.iniciar_simulacao)
        #self.ui.camdinfBut.clicked.connect(self.layer_anterior)
        #self.ui.camdsupBut.clicked.connect(self.layer_seguinte)
        #self.ui.camadasRadio.toggled.connect(self.modo_camadas)
        #self.ui.objetoRadio.toggled.connect(self.modo_objeto)
        #self.ui.velocidadebar.valueChanged.connect(self.ajustar_velocidade)

    def importar_gcode(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Abrir GCode', '', '*.gcode *.nc *.txt')
        if path:
            self.model = self.parser.parse(path)
            self.ui.codigo.setPlainText(open(path).read())
            self.viewer.set_model(self.model)

    def tela_cheia(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            window.showFullScreen()

app = QApplication(sys.argv)
if (QDialog.Accepted == True):
    window = editor_grafico()
    window.show()
sys.exit(app.exec_())