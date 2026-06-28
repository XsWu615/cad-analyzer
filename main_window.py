from PySide6.QtWidgets import (
    QMainWindow, QMenuBar, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QWidget, QVBoxLayout,
    QHBoxLayout, QSplitter, QLabel, QDockWidget,
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction, QKeySequence

from cad_parser import CADParser
from model_builder import ModelBuilder
from part_counter import PartCounter
from exporter import Exporter
from dxf_preview import DXFPreviewWidget
from gl_widget import GLWidget
from layer_panel import LayerPanel
from stats_panel import StatsPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CAD Analyzer - 图纸分析 & 3D建模")
        self.settings = QSettings("CADTools", "CADAnalyzer")

        self._parser = CADParser()
        self._builder = ModelBuilder()
        self._counter = PartCounter()
        self._exporter = Exporter()

        self._current_dxf = None
        self._layer_meshes = {}

        self._setup_menu()
        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()

    def _setup_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("文件(&F)")
        act_open = QAction("打开DXF(&O)...", self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self._on_open)
        file_menu.addAction(act_open)

        file_menu.addSeparator()

        act_export_3d = QAction("导出3D模型(&E)...", self)
        act_export_3d.setShortcut(QKeySequence("Ctrl+E"))
        act_export_3d.triggered.connect(self._on_export_3d)
        file_menu.addAction(act_export_3d)

        act_export_stats = QAction("导出统计报表(&S)...", self)
        act_export_stats.triggered.connect(self._on_export_stats)
        file_menu.addAction(act_export_stats)

        file_menu.addSeparator()

        act_exit = QAction("退出(&X)", self)
        act_exit.setShortcut(QKeySequence.Quit)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        view_menu = mb.addMenu("视图(&V)")
        act_reset = QAction("重置3D视角(&R)", self)
        act_reset.setShortcut(QKeySequence("Ctrl+R"))
        act_reset.triggered.connect(self._on_reset_view)
        view_menu.addAction(act_reset)

        help_menu = mb.addMenu("帮助(&H)")
        act_about = QAction("关于(&A)", self)
        act_about.triggered.connect(self._on_about)
        help_menu.addAction(act_about)

    def _setup_toolbar(self):
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, tb)

        act_open = QAction("📂 打开DXF", self)
        act_open.triggered.connect(self._on_open)
        tb.addAction(act_open)

        act_build = QAction("🔧 生成3D", self)
        act_build.triggered.connect(self._on_build_3d)
        tb.addAction(act_build)

        tb.addSeparator()

        act_export_3d = QAction("💾 导出模型", self)
        act_export_3d.triggered.connect(self._on_export_3d)
        tb.addAction(act_export_3d)

        act_export_stats = QAction("📊 导出报表", self)
        act_export_stats.triggered.connect(self._on_export_stats)
        tb.addAction(act_export_stats)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Horizontal)

        # Left: 2D preview
        self._dxf_preview = DXFPreviewWidget()
        splitter.addWidget(self._dxf_preview)

        # Middle: layer panel
        self._layer_panel = LayerPanel()
        self._layer_panel.layer_changed.connect(self._on_layers_changed)
        splitter.addWidget(self._layer_panel)

        # Right: 3D view + stats (vertical split)
        right_splitter = QSplitter(Qt.Vertical)

        self._gl_widget = GLWidget()
        right_splitter.addWidget(self._gl_widget)

        self._stats_panel = StatsPanel()
        right_splitter.addWidget(self._stats_panel)

        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 1)

        splitter.addWidget(right_splitter)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 4)

        root.addWidget(splitter)

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._status_label = QLabel("就绪 - 请打开DXF文件")
        self._statusbar.addWidget(self._status_label)

    # --- slots ---

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开DXF图纸", "",
            "DXF Files (*.dxf);;All Files (*.*)"
        )
        if not path:
            return

        try:
            self._status_label.setText(f"解析中: {path}")
            self._current_dxf = self._parser.parse(path)
            self._dxf_preview.load(self._current_dxf)
            self._layer_panel.load(self._current_dxf)
            self._stats_panel.clear()
            self._gl_widget.clear()
            self._layer_meshes = {}
            self._status_label.setText(f"已加载: {path} | 图层: {len(self._current_dxf.layers)}")
        except Exception as e:
            QMessageBox.critical(self, "解析失败", str(e))
            self._status_label.setText("解析失败")

    def _on_build_3d(self):
        if self._current_dxf is None:
            QMessageBox.warning(self, "提示", "请先打开DXF文件")
            return

        try:
            self._status_label.setText("生成3D模型中...")
            layer_thicknesses = self._layer_panel.get_thicknesses()
            enabled_layers = self._layer_panel.get_enabled_layers()

            self._layer_meshes = self._builder.build(
                self._current_dxf, layer_thicknesses, enabled_layers
            )

            self._gl_widget.load(self._layer_meshes)

            stats = self._counter.count(
                self._current_dxf, self._layer_meshes
            )
            self._stats_panel.load(stats)

            total_parts = stats.get("component_count", 0)
            self._status_label.setText(
                f"3D模型已生成 | 图层: {len(self._layer_meshes)} | 零件: {total_parts}"
            )
        except Exception as e:
            QMessageBox.critical(self, "生成失败", str(e))
            self._status_label.setText("3D生成失败")

    def _on_layers_changed(self):
        if self._layer_meshes:
            self._gl_widget.update_visibility(
                self._layer_panel.get_enabled_layers()
            )

    def _on_export_3d(self):
        if not self._layer_meshes:
            QMessageBox.warning(self, "提示", "请先生成3D模型")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "导出3D模型", "model.stl",
            "STL (*.stl);;OBJ (*.obj);;GLB (*.glb)"
        )
        if not path:
            return

        try:
            self._exporter.export_3d(self._layer_meshes, path)
            self._status_label.setText(f"模型已导出: {path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _on_export_stats(self):
        if self._current_dxf is None:
            QMessageBox.warning(self, "提示", "请先打开DXF文件并生成3D")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "导出统计报表", "stats.xlsx",
            "Excel (*.xlsx);;CSV (*.csv)"
        )
        if not path:
            return

        try:
            self._exporter.export_stats(self._stats_panel.get_data(), path)
            self._status_label.setText(f"报表已导出: {path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _on_reset_view(self):
        self._gl_widget.reset_view()

    def _on_about(self):
        QMessageBox.about(
            self, "关于 CAD Analyzer",
            "CAD Analyzer v1.0\n\n"
            "CAD图纸分析 & 3D建模工具\n"
            "支持DXF格式，图层挤出生成3D\n"
            "零件自动统计与分类"
        )
