import sys
import os

os.environ["QT_API"] = "pyside6"

import matplotlib
matplotlib.use('QtAgg')
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from main_window import MainWindow


def _base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CAD Analyzer")
    app.setOrganizationName("CADTools")

    # Window icon (title bar + taskbar)
    icon_path = os.path.join(_base_dir(), "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    style_path = os.path.join(_base_dir(), "style.qss")
    if os.path.exists(style_path):
        with open(style_path, encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = MainWindow()
    window.resize(1400, 900)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
