"""Settings dialog for storage location and preferences."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QDialogButtonBox, QGroupBox,
)
from PySide6.QtCore import QSettings


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)

        self._settings = QSettings("CADTools", "CADAnalyzer")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Storage group
        storage_group = QGroupBox("项目存储位置")
        storage_layout = QVBoxLayout(storage_group)

        hint = QLabel("新建项目和分析结果将保存在此目录下。")
        hint.setStyleSheet("color: #888;")
        storage_layout.addWidget(hint)

        path_layout = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("默认为软件所在文件夹下的 projects 目录")
        current = self._settings.value("storage_root", "")
        if current:
            self._path_edit.setText(current)
        path_layout.addWidget(self._path_edit)

        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self._on_browse)
        path_layout.addWidget(btn_browse)

        storage_layout.addLayout(path_layout)

        btn_default = QPushButton("恢复默认")
        btn_default.clicked.connect(self._on_default)
        storage_layout.addWidget(btn_default)

        layout.addWidget(storage_group)

        layout.addStretch()

        # OK / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_browse(self):
        path = QFileDialog.getExistingDirectory(self, "选择存储位置")
        if path:
            self._path_edit.setText(path)

    def _on_default(self):
        self._path_edit.clear()

    def _on_accept(self):
        path = self._path_edit.text().strip()
        if path:
            self._settings.setValue("storage_root", path)
        else:
            self._settings.remove("storage_root")
        self.accept()

    @staticmethod
    def get_storage_root() -> str:
        """Get configured storage root, or default."""
        settings = QSettings("CADTools", "CADAnalyzer")
        configured = settings.value("storage_root", "")
        if configured:
            return configured
        import os, sys
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "projects")
