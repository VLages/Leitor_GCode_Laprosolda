from PyQt5.QtWidgets import QApplication, QWidget, QPushButton
from PyQt5.Qt import Qt
from PyQt5.QtCore import pyqtSlot
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtPrintSupport import *
import os, sys

from editor_grafico import Ui_editor_grafico

class editor_grafico(QDialog):
    def __init__(self,*args,**argvs):
        super(editor_grafico,self).__init__(*args,**argvs)
        self.ui = Ui_editor_grafico()
        self.ui.setupUi(self)
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)


app = QApplication(sys.argv)
if (QDialog.Accepted == True):
    window = editor_grafico()
    window.show()
sys.exit(app.exec_())