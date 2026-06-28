from typing import Dict, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QDoubleSpinBox, QCheckBox, QLabel, QHBoxLayout, QPushButton,
    QGroupBox,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

from cad_parser import DXFData


class LayerPanel(QWidget):
    layer_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: DXFData = None
        self._spinners: Dict[str, QDoubleSpinBox] = {}
        self._checks: Dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("图层面板")
        title.setStyleSheet("font-weight: bold; font-size: 13px; padding: 4px;")
        layout.addWidget(title)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        btn_all = QPushButton("全选")
        btn_all.clicked.connect(self._on_select_all)
        btn_none = QPushButton("全不选")
        btn_none.clicked.connect(self._on_select_none)
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_none)
        layout.addLayout(btn_layout)

    def load(self, data: DXFData):
        self._data = data
        self._list.clear()
        self._spinners.clear()
        self._checks.clear()

        for layer in data.layers:
            item = QListWidgetItem()
            widget = self._make_layer_row(layer, data)
            item.setSizeHint(widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

    def _make_layer_row(self, layer: str, data: DXFData) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 2, 4, 2)

        cb = QCheckBox()
        cb.setChecked(True)
        cb.stateChanged.connect(lambda: self.layer_changed.emit())
        self._checks[layer] = cb
        layout.addWidget(cb)

        # color indicator
        color_label = QLabel("  ")
        color_label.setFixedWidth(16)
        color_label.setStyleSheet("background-color: #4ecdc4; border-radius: 3px;")
        layout.addWidget(color_label)

        # entity count
        count = len(data.entities.get(layer, []))
        name_label = QLabel(f"{layer} ({count})")
        name_label.setMinimumWidth(80)
        layout.addWidget(name_label)

        # thickness spinner
        spin = QDoubleSpinBox()
        spin.setRange(0.1, 1000.0)
        spin.setValue(10.0)
        spin.setSuffix(" mm")
        spin.setDecimals(1)
        spin.setMaximumWidth(100)
        spin.valueChanged.connect(lambda: self.layer_changed.emit())
        self._spinners[layer] = spin
        layout.addWidget(spin)

        layout.addStretch()
        return w

    def get_thicknesses(self) -> Dict[str, float]:
        return {ly: s.value() for ly, s in self._spinners.items()}

    def get_enabled_layers(self) -> List[str]:
        return [ly for ly, cb in self._checks.items() if cb.isChecked()]

    def _on_select_all(self):
        for cb in self._checks.values():
            cb.setChecked(True)
        self.layer_changed.emit()

    def _on_select_none(self):
        for cb in self._checks.values():
            cb.setChecked(False)
        self.layer_changed.emit()
