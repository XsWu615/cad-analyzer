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
from welcome_dialog import WelcomeDialog
from project_manager import ProjectManager
from settings_dialog import SettingsDialog


def _base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CAD Analyzer")
    app.setOrganizationName("CADTools")

    icon_path = os.path.join(_base_dir(), "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    style_path = os.path.join(_base_dir(), "style.qss")
    if os.path.exists(style_path):
        with open(style_path, encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    # Welcome: project selection / create
    pm = ProjectManager()
    pm.set_storage_root(SettingsDialog.get_storage_root())
    welcome = WelcomeDialog(pm)
    if not welcome.exec():
        sys.exit(0)  # user clicked exit

    window = MainWindow()
    window._project_mgr = pm  # inject the already-opened project manager
    window._refresh_tree()
    window.resize(1400, 900)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
