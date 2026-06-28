import sys
import os

os.environ["QT_API"] = "pyside6"

import matplotlib
matplotlib.use('QtAgg')
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CAD Analyzer")
    app.setOrganizationName("CADTools")

    with open(os.path.join(os.path.dirname(__file__), "style.qss"), encoding="utf-8") as f:
        app.setStyleSheet(f.read())

    window = MainWindow()
    window.resize(1400, 900)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
