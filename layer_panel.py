from typing import Dict, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QDoubleSpinBox, QCheckBox, QLabel, QHBoxLayout, QPushButton,
    QGroupBox, QScrollArea,
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
        self._z_spinners: Dict[str, QDoubleSpinBox] = {}
        self._checks: Dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Header with column labels
        header = QHBoxLayout()
        header.addWidget(QLabel(""))
        header.addWidget(QLabel("图层"))
        header.addWidget(QLabel("厚"))
        header.addWidget(QLabel("Z"))
        header.addStretch()
        layout.addLayout(header)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self._list)

        # Selection buttons
        btn_layout = QHBoxLayout()
        btn_all = QPushButton("全选")
        btn_all.clicked.connect(self._on_select_all)
        btn_none = QPushButton("全不选")
        btn_none.clicked.connect(self._on_select_none)
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_none)
        layout.addLayout(btn_layout)

        # Z presets for building layers
        z_group = QGroupBox("Z偏移快捷设置")
        z_layout = QHBoxLayout(z_group)
        for label, z in [("0m", 0), ("3m", 3000), ("6m", 6000),
                          ("9m", 9000), ("12m", 12000), ("-3m", -3000)]:
            btn = QPushButton(label)
            btn.setMaximumWidth(45)
            btn.clicked.connect(lambda checked, z=z: self._set_all_z(z))
            z_layout.addWidget(btn)
        layout.addWidget(z_group)

    def load(self, data: DXFData):
        self._data = data
        self._list.clear()
        self._spinners.clear()
        self._z_spinners.clear()
        self._checks.clear()

        # Only show layers with entities
        active = [(ly, len(ents)) for ly, ents in data.entities.items() if ents]
        active.sort(key=lambda x: x[0])

        for layer, count in active:
            item = QListWidgetItem()
            widget = self._make_layer_row(layer, count)
            item.setSizeHint(widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

    def _make_layer_row(self, layer: str, count: int) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(4)

        # Checkbox
        cb = QCheckBox()
        cb.setChecked(True)
        cb.stateChanged.connect(lambda: self.layer_changed.emit())
        self._checks[layer] = cb
        layout.addWidget(cb)

        # Layer name
        short = layer if len(layer) <= 12 else layer[:11] + "…"
        name_label = QLabel(f"{short} ({count})")
        name_label.setMinimumWidth(90)
        name_label.setToolTip(f"{layer} — {count} entities")
        layout.addWidget(name_label)

        # Thickness
        spin_t = QDoubleSpinBox()
        spin_t.setRange(1, 50000)
        spin_t.setValue(300)
        spin_t.setSuffix("")
        spin_t.setDecimals(0)
        spin_t.setMaximumWidth(56)
        spin_t.valueChanged.connect(lambda: self.layer_changed.emit())
        self._spinners[layer] = spin_t
        layout.addWidget(spin_t)

        # Z offset
        spin_z = QDoubleSpinBox()
        spin_z.setRange(-100000, 1000000)
        spin_z.setValue(0)
        spin_z.setSuffix("")
        spin_z.setDecimals(0)
        spin_z.setMaximumWidth(64)
        spin_z.valueChanged.connect(lambda: self.layer_changed.emit())
        self._z_spinners[layer] = spin_z
        layout.addWidget(spin_z)

        layout.addStretch()
        return w

    def get_thicknesses(self) -> Dict[str, float]:
        return {ly: s.value() for ly, s in self._spinners.items()}

    def get_z_offsets(self) -> Dict[str, float]:
        return {ly: s.value() for ly, s in self._z_spinners.items()}

    def get_enabled_layers(self) -> List[str]:
        return [ly for ly, cb in self._checks.items() if cb.isChecked()]

    def _set_all_z(self, z: float):
        for sp in self._z_spinners.values():
            sp.setValue(z)
        self.layer_changed.emit()

    def _on_select_all(self):
        for cb in self._checks.values():
            cb.setChecked(True)
        self.layer_changed.emit()

    def _on_select_none(self):
        for cb in self._checks.values():
            cb.setChecked(False)
        self.layer_changed.emit()
