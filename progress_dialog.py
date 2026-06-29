"""Non-modal progress dialog with cancel support."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout,
)
from PySide6.QtCore import Qt, Signal, QObject


class ProgressSignal(QObject):
    """Thread-safe progress emitter."""
    value = Signal(int)
    text = Signal(str)
    finished = Signal()
    error = Signal(str)


class ProgressDialog(QDialog):
    def __init__(self, parent=None, title="处理中", cancelable=True):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleLabel)
        self._cancelled = False

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._label = QLabel("正在加载...")
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

        self._bar = QProgressBar()
        self._bar.setMinimum(0)
        self._bar.setMaximum(0)  # indeterminate by default
        layout.addWidget(self._bar)

        if cancelable:
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            self._cancel_btn = QPushButton("取消")
            self._cancel_btn.clicked.connect(self._on_cancel)
            btn_layout.addWidget(self._cancel_btn)
            layout.addLayout(btn_layout)

        self._signal = ProgressSignal()
        self._signal.value.connect(self._bar.setValue)
        self._signal.text.connect(self._label.setText)

    def _on_cancel(self):
        self._cancelled = True
        self._label.setText("正在取消...")
        self._cancel_btn.setEnabled(False)

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @property
    def signal(self) -> ProgressSignal:
        return self._signal

    def set_range(self, min_val: int, max_val: int):
        self._bar.setMinimum(min_val)
        self._bar.setMaximum(max_val)

    def set_value(self, val: int):
        self._bar.setValue(val)

    def set_text(self, text: str):
        self._label.setText(text)
