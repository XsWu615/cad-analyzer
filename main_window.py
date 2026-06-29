from PySide6.QtWidgets import (
    QMainWindow, QMenuBar, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QWidget, QVBoxLayout,
    QHBoxLayout, QSplitter, QLabel, QDockWidget,
    QDialog, QDialogButtonBox, QPushButton,
)
from PySide6.QtCore import Qt, QSettings, QUrl, QTimer
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
from pdf_importer import PDFImporter
from translator_util import TextTranslator


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
        self._pdf_importer = PDFImporter()
        self._translator = TextTranslator()

        self._current_dxf = None
        self._layer_meshes = {}

        self._setup_menu()
        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()

    def _setup_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("文件(&F)")

        act_open = QAction("打开CAD/PDF(&O)...", self)
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

        act_open = QAction("打开CAD/PDF", self)
        act_open.triggered.connect(self._on_open)
        tb.addAction(act_open)

        act_build = QAction("生成3D", self)
        act_build.triggered.connect(self._on_build_3d)
        tb.addAction(act_build)

        tb.addSeparator()

        act_export_3d = QAction("导出模型", self)
        act_export_3d.triggered.connect(self._on_export_3d)
        tb.addAction(act_export_3d)

        act_export_stats = QAction("导出报表", self)
        act_export_stats.triggered.connect(self._on_export_stats)
        tb.addAction(act_export_stats)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Horizontal)

        self._dxf_preview = DXFPreviewWidget()
        splitter.addWidget(self._dxf_preview)

        self._layer_panel = LayerPanel()
        self._layer_panel.layer_changed.connect(self._on_layers_changed)
        splitter.addWidget(self._layer_panel)

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
        self._status_label = QLabel("就绪 - 支持 DXF / DWG / PDF")
        self._statusbar.addWidget(self._status_label)

    # --- slots ---

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开CAD图纸或PDF", "",
            "支持格式 (*.dxf *.dwg *.pdf);;DXF Files (*.dxf);;DWG Files (*.dwg);;PDF Files (*.pdf);;All Files (*.*)"
        )
        if not path:
            return

        ext = path.lower()

        if ext.endswith('.pdf'):
            self._open_pdf(path)
            return

        if ext.endswith('.dwg'):
            self._open_dwg(path)
            return

        if ext.endswith('.dxf'):
            self._load_dxf(path)
            return

    def _open_pdf(self, pdf_path):
        """Import PDF, translate text, convert to DXF for pipeline."""
        try:
            self._status_label.setText(f"导入PDF矢量图形: {pdf_path}")
            QTimer.singleShot(50, lambda: self._do_pdf_import(pdf_path))
        except Exception as e:
            QMessageBox.critical(self, "PDF导入失败", str(e))

    def _do_pdf_import(self, pdf_path):
        try:
            pdf_data = self._pdf_importer.extract(pdf_path)
            if not pdf_data.layers or not any(
                pdf_data.entities.get(ly) for ly in pdf_data.layers
            ):
                QMessageBox.warning(
                    self, "PDF无矢量数据",
                    "该PDF未检测到矢量线条。\n"
                    "可能原因：\n"
                    "  - PDF是扫描图片（非CAD导出）\n"
                    "  - 矢量内容被栅格化\n\n"
                    "请用CAD软件导出为DXF后再导入。"
                )
                self._status_label.setText("PDF无矢量数据")
                return

            # Export to temp DXF
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as f:
                tmp_dxf = f.name
            self._pdf_importer.export_dxf(pdf_data, tmp_dxf)

            self._status_label.setText(
                f"PDF已导入: {pdf_data.page_count}页, {len(pdf_data.layers)}层 - 翻译中..."
            )

            # Load into pipeline
            self._load_dxf(tmp_dxf)

            # Translate text annotations
            self._translate_imported_text()

            # cleanup temp
            import os
            try:
                os.unlink(tmp_dxf)
            except Exception:
                pass

            self._status_label.setText(
                f"PDF已导入: {pdf_path} | 图层: {len(self._current_dxf.layers) if self._current_dxf else 0}"
            )
        except Exception as e:
            QMessageBox.critical(self, "PDF导入失败", str(e))
            self._status_label.setText("PDF导入失败")

    def _open_dwg(self, dwg_path):
        """Try silent ODA conversion, fall back to guidance dialog."""
        self._status_label.setText("检测DWG，尝试自动转换...")
        QTimer.singleShot(50, lambda: self._do_dwg_convert(dwg_path))

    def _do_dwg_convert(self, dwg_path):
        # Try auto-convert via ODA
        dxf_path = self._dwg_converter.auto_convert(dwg_path)
        if dxf_path:
            self._status_label.setText(f"DWG已自动转换为DXF: {dxf_path}")
            self._load_dxf(dxf_path)
            self._translate_imported_text()
            return

        # ODA not found — show guidance dialog
        self._show_dwg_dialog(dwg_path)

    def _show_dwg_dialog(self, dwg_path):
        dlg = QDialog(self)
        dlg.setWindowTitle("DWG转换 - 需要ODA File Converter")
        dlg.setMinimumWidth(520)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        info = QLabel(
            f"<h3>DWG 自动转换失败</h3>"
            f"<p><b>文件:</b> {dwg_path}</p>"
            f"<p>DWG 是 AutoCAD 私有格式。需要安装 ODA File Converter（免费）才能自动转换。</p>"
            f"<p>这是一次性安装，之后所有 DWG 都会自动转换。</p>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        oda_path = self._dwg_converter.find_oda_converter()
        if oda_path:
            oda_label = QLabel(f"已检测到: <code>{oda_path}</code>")
            oda_label.setStyleSheet("color: #4ecdc4;")
            layout.addWidget(oda_label)

        btn_layout = QHBoxLayout()

        if oda_path:
            btn_try = QPushButton("重试转换")
            btn_try.clicked.connect(lambda: (
                dlg.accept(),
                QTimer.singleShot(100, lambda: self._do_dwg_convert(dwg_path)),
            ))
            btn_layout.addWidget(btn_try)

        btn_download = QPushButton("下载 ODA File Converter (免费)")
        btn_download.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl(DWGConverter.DOWNLOAD_URL)
        ))
        btn_layout.addWidget(btn_download)

        btn_layout.addStretch()

        dlg_buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        dlg_buttons.accepted.connect(dlg.accept)
        btn_layout.addWidget(dlg_buttons)

        layout.addLayout(btn_layout)
        dlg.exec()
        self._status_label.setText("DWG转换：请安装ODA File Converter后重试")

    def _load_dxf(self, path):
        try:
            self._status_label.setText(f"解析中: {path}")
            self._current_dxf = self._parser.parse(path)
            self._dxf_preview.load(self._current_dxf)
            self._layer_panel.load(self._current_dxf)
            self._stats_panel.clear()
            self._gl_widget.clear()
            self._layer_meshes = {}
            self._status_label.setText(
                f"已加载: {path} | 图层: {len(self._current_dxf.layers)}"
            )
        except Exception as e:
            QMessageBox.critical(self, "解析失败", str(e))
            self._status_label.setText("解析失败")

    def _translate_imported_text(self):
        """Translate non-Chinese TEXT/MTEXT entities in loaded DXF data."""
        if self._current_dxf is None:
            return

        translated = 0
        for layer, entities in self._current_dxf.entities.items():
            for e in entities:
                if e.dxftype in ('TEXT', 'MTEXT'):
                    original = e.geometry.get('text', '')
                    if original:
                        new_text = self._translator.translate(original)
                        if new_text != original:
                            e.geometry['text'] = new_text
                            translated += 1

        if translated > 0:
            self._dxf_preview.load(self._current_dxf)
            self._status_label.setText(
                f"{self._status_label.text()} | 已翻译 {translated} 处文本"
            )

    def _on_build_3d(self):
        if self._current_dxf is None:
            QMessageBox.warning(self, "提示", "请先打开DXF/PDF/DWG文件")
            return

        try:
            self._status_label.setText("生成3D模型中...")
            layer_thicknesses = self._layer_panel.get_thicknesses()
            enabled_layers = self._layer_panel.get_enabled_layers()

            self._layer_meshes = self._builder.build(
                self._current_dxf, layer_thicknesses, enabled_layers
            )

            self._gl_widget.load(self._layer_meshes)

            stats = self._counter.count(self._current_dxf, self._layer_meshes)
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
            QMessageBox.warning(self, "提示", "请先打开文件并生成3D")
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
            "CAD Analyzer v1.1\n\n"
            "CAD图纸分析 & 3D建模工具\n"
            "支持: DXF / DWG(自动转换) / PDF(矢量导入)\n"
            "图层挤出生成3D · 零件自动统计\n"
            "非中文标注自动翻译"
        )
