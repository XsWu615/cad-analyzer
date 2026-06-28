from typing import Dict, Any
import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTableView, QLabel,
    QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor


class PandasModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self._df = df

    def rowCount(self, parent=QModelIndex()):
        return self._df.shape[0]

    def columnCount(self, parent=QModelIndex()):
        return self._df.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            val = self._df.iloc[index.row(), index.column()]
            if isinstance(val, float):
                return f"{val:.2f}"
            return str(val)
        if role == Qt.BackgroundRole and index.row() % 2 == 0:
            return QColor("#2a2a2a")
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            else:
                return str(self._df.index[section])
        return None


class StatsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: Dict[str, Any] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("统计面板")
        title.setStyleSheet("font-weight: bold; font-size: 13px; padding: 4px;")
        layout.addWidget(title)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._layer_table = QTableView()
        self._layer_table.setAlternatingRowColors(True)
        self._layer_table.horizontalHeader().setStretchLastSection(True)
        self._layer_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        self._component_table = QTableView()
        self._component_table.setAlternatingRowColors(True)
        self._component_table.horizontalHeader().setStretchLastSection(True)
        self._component_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        self._tabs.addTab(self._layer_table, "按图层")
        self._tabs.addTab(self._component_table, "按零件")

    def load(self, data: Dict[str, Any]):
        self._data = data

        layer_df = data.get("layer_stats")
        if layer_df is not None and not layer_df.empty:
            model = PandasModel(layer_df)
            self._layer_table.setModel(model)
            self._layer_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        comp_df = data.get("component_stats")
        if comp_df is not None and not comp_df.empty:
            model = PandasModel(comp_df)
            self._component_table.setModel(model)
            self._component_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    def get_data(self) -> Dict[str, Any]:
        return self._data

    def clear(self):
        self._data = {}
        self._layer_table.setModel(None)
        self._component_table.setModel(None)
