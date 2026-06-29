"""Startup: project selection or creation."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QInputDialog, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt
from project_manager import ProjectManager
from settings_dialog import SettingsDialog


class WelcomeDialog(QDialog):
    def __init__(self, project_mgr: ProjectManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CAD Analyzer - 欢迎")
        self.setMinimumSize(500, 400)
        self._mgr = project_mgr
        self._result_project_path = None

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("<h2>CAD Analyzer</h2><p>图纸分析 & 3D建模</p>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Recent / existing projects
        layout.addWidget(QLabel("<b>打开已有项目:</b>"))
        self._list = QListWidget()
        self._refresh_list()
        self._list.itemDoubleClicked.connect(self._on_open_selected)
        layout.addWidget(self._list)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_new = QPushButton("新建项目")
        btn_new.setStyleSheet("QPushButton { background-color: #0078d4; padding: 10px 24px; font-size: 14px; }")
        btn_new.clicked.connect(self._on_new)
        btn_layout.addWidget(btn_new)

        btn_open = QPushButton("打开项目文件夹...")
        btn_open.clicked.connect(self._on_browse)
        btn_layout.addWidget(btn_open)

        layout.addLayout(btn_layout)

        btn_exit = QPushButton("退出")
        btn_exit.clicked.connect(self.reject)
        layout.addWidget(btn_exit)

    def _refresh_list(self):
        self._list.clear()
        projects = self._mgr.list_projects()
        if not projects:
            self._list.addItem("（暂无项目）")
        for p in projects:
            self._list.addItem(p)

    def _on_open_selected(self):
        item = self._list.currentItem()
        if not item or item.text().startswith("（"):
            return
        name = item.text()
        path = self._mgr.storage_root + "/" + name
        try:
            self._mgr.open_project(path)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "打开失败", str(e))

    def _on_new(self):
        name, ok = QInputDialog.getText(self, "新建项目", "项目名称:")
        if not ok or not name.strip():
            return
        try:
            self._mgr.create_project(name.strip())
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "创建失败", str(e))

    def _on_browse(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择项目文件夹", self._mgr.storage_root)
        if not path:
            return
        try:
            self._mgr.open_project(path)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "打开失败", str(e))
