from PySide6.QtWidgets import (
    QMainWindow, QMenuBar, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QWidget, QVBoxLayout,
    QHBoxLayout, QSplitter, QLabel, QDockWidget,
    QDialog, QDialogButtonBox, QPushButton,
)
from PySide6.QtCore import Qt, QSettings, QUrl
from PySide6.QtGui import QAction, QKeySequence, QDesktopServices

from cad_parser import CADParser
from model_builder import ModelBuilder
from part_counter import PartCounter
from exporter import Exporter
from dxf_preview import DXFPreviewWidget
from gl_widget import GLWidget
from layer_panel import LayerPanel
from stats_panel import StatsPanel
from dwg_converter import DWGConverter


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CAD Analyzer - 图纸分析 & 3D建模")
        self.settings = QSettings("CADTools", "CADAnalyzer")

        self._parser = CADParser()
        self._builder = ModelBuilder()
        self._counter = PartCounter()
        self._exporter = Exporter()
        self._dwg_converter = DWGConverter()

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
            self, "打开CAD图纸", "",
            "CAD Files (*.dxf *.dwg);;DXF Files (*.dxf);;DWG Files (*.dwg);;All Files (*.*)"
        )
        if not path:
            return

        # DWG detection → guide user to convert first
        if path.lower().endswith('.dwg'):
            self._handle_dwg(path)
            return

        self._load_dxf(path)

    def _handle_dwg(self, dwg_path):
        """Show DWG guidance dialog with conversion options."""
        dlg = QDialog(self)
        dlg.setWindowTitle("DWG文件检测")
        dlg.setMinimumWidth(520)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        info = QLabel(
            f"<h3>检测到 DWG 格式文件</h3>"
            f"<p><b>文件:</b> {dwg_path}</p>"
            f"<p>DWG 是 AutoCAD 私有二进制格式，本软件无法直接解析。</p>"
            f"<p><b>解决方案：</b>使用 Autodesk 官方免费的 "
            f"<a href='https://www.opendesign.com/guestfiles/oda_file_converter'>ODA File Converter</a> "
            f"将 DWG 转换为 DXF，再导入本软件。</p>"
            f"<p style='color:#888;'>一次转换所有 DWG 文件，后续直接打开 DXF 即可。</p>"
        )
        info.setWordWrap(True)
        info.setOpenExternalLinks(True)
        layout.addWidget(info)

        # ODAFileConverter detection
        oda_path = self._dwg_converter.find_oda_converter()
        oda_label = QLabel()
        if oda_path:
            oda_label.setText(f"ODAFileConverter 已检测到:<br><code>{oda_path}</code>")
            oda_label.setStyleSheet("color: #4ecdc4;")
        else:
            oda_label.setText("未检测到 ODA File Converter 安装。\n请下载后安装，或将 DWG 文件用其他工具转为 DXF。")
            oda_label.setStyleSheet("color: #ff6b6b;")
        oda_label.setWordWrap(True)
        layout.addWidget(oda_label)

        # buttons
        btn_layout = QHBoxLayout()

        if oda_path:
            btn_run = QPushButton("启动 ODA File Converter")
            btn_run.clicked.connect(lambda: self._dwg_converter.launch_oda(oda_path))
            btn_layout.addWidget(btn_run)

        btn_download = QPushButton("下载 ODA File Converter")
        btn_download.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://www.opendesign.com/guestfiles/oda_file_converter")
        ))
        btn_layout.addWidget(btn_download)

        btn_layout.addStretch()

        dlg_buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        dlg_buttons.accepted.connect(dlg.accept)
        btn_layout.addWidget(dlg_buttons)

        layout.addLayout(btn_layout)
        dlg.exec()

    def _load_dxf(self, path):
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
