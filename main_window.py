"""Main window with project management, multi-drawing, progress display."""

import os
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QDialog, QDialogButtonBox, QPushButton, QInputDialog,
    QTreeWidget, QTreeWidgetItem, QMenu,
)
from PySide6.QtCore import Qt, QSettings, QUrl, QTimer, QThread, Signal, QObject
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
from project_manager import ProjectManager, DrawingInfo
from progress_dialog import ProgressDialog
from settings_dialog import SettingsDialog


# ── background workers ──────────────────────────────────────────

class _ParseWorker(QObject):
    """Parse DXF in background, emit progress."""
    progress = Signal(int, str)  # percent, message
    finished = Signal(object)    # DXFData or Exception

    def __init__(self, parser, filepath):
        super().__init__()
        self._parser = parser
        self._filepath = filepath

    def run(self):
        try:
            self.progress.emit(10, "读取DXF文件...")
            data = self._parser.parse(self._filepath)
            self.progress.emit(100, f"完成: {len(data.layers)}层, {sum(len(v) for v in data.entities.values())}实体")
            self.finished.emit(data)
        except Exception as e:
            self.finished.emit(e)


class _BuildWorker(QObject):
    """Build 3D meshes in background."""
    progress = Signal(int, str)
    finished = Signal(object)  # dict layer→mesh or Exception

    def __init__(self, builder, dxf_data, thicknesses, enabled_layers):
        super().__init__()
        self._builder = builder
        self._dxf_data = dxf_data
        self._thicknesses = thicknesses
        self._enabled_layers = enabled_layers

    def run(self):
        try:
            self.progress.emit(10, "生成3D模型...")
            meshes = self._builder.build(
                self._dxf_data, self._thicknesses, self._enabled_layers
            )
            self.progress.emit(100, f"3D模型完成: {len(meshes)}层")
            self.finished.emit(meshes)
        except Exception as e:
            self.finished.emit(e)


class _DWGWorker(QObject):
    """Convert DWG in background."""
    finished = Signal(object)  # dxf_path or Exception

    def __init__(self, converter, dwg_path):
        super().__init__()
        self._converter = converter
        self._dwg_path = dwg_path

    def run(self):
        try:
            result = self._converter.auto_convert(self._dwg_path)
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit(e)


# ── main window ──────────────────────────────────────────────────

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
        self._project_mgr = ProjectManager()
        self._project_mgr.set_storage_root(SettingsDialog.get_storage_root())

        self._current_dxf = None
        self._layer_meshes = {}
        self._progress_dlg = None

        self._setup_menu()
        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()

    # ── menu ─────────────────────────────────────────────────────

    def _setup_menu(self):
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("文件(&F)")
        act_open = QAction("添加图纸(&A)...", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self._on_add_drawing)
        file_menu.addAction(act_open)
        file_menu.addSeparator()
        act_export_3d = QAction("导出3D模型(&E)...", self)
        act_export_3d.setShortcut(QKeySequence("Ctrl+E"))
        act_export_3d.triggered.connect(self._on_export_3d)
        file_menu.addAction(act_export_3d)
        act_export_stats = QAction("导出统计报表(&R)...", self)
        act_export_stats.triggered.connect(self._on_export_stats)
        file_menu.addAction(act_export_stats)
        file_menu.addSeparator()
        act_exit = QAction("退出(&X)", self)
        act_exit.setShortcut(QKeySequence.Quit)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Project
        proj_menu = mb.addMenu("项目(&P)")
        act_new_proj = QAction("新建项目(&N)...", self)
        act_new_proj.setShortcut(QKeySequence("Ctrl+N"))
        act_new_proj.triggered.connect(self._on_new_project)
        proj_menu.addAction(act_new_proj)
        act_open_proj = QAction("打开项目(&O)...", self)
        act_open_proj.triggered.connect(self._on_open_project)
        proj_menu.addAction(act_open_proj)

        # View
        view_menu = mb.addMenu("视图(&V)")
        act_reset = QAction("重置3D视角(&R)", self)
        act_reset.setShortcut(QKeySequence("Ctrl+R"))
        act_reset.triggered.connect(self._on_reset_view)
        view_menu.addAction(act_reset)

        # Settings
        set_menu = mb.addMenu("设置(&S)")
        act_settings = QAction("存储位置(&S)...", self)
        act_settings.triggered.connect(self._on_settings)
        set_menu.addAction(act_settings)

        # Help
        help_menu = mb.addMenu("帮助(&H)")
        act_about = QAction("关于(&A)", self)
        act_about.triggered.connect(self._on_about)
        help_menu.addAction(act_about)

    # ── toolbar ──────────────────────────────────────────────────

    def _setup_toolbar(self):
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, tb)

        tb.addAction("新建项目", self._on_new_project)
        tb.addAction("添加图纸", self._on_add_drawing)
        tb.addAction("生成3D", self._on_build_3d)
        tb.addSeparator()
        tb.addAction("导出模型", self._on_export_3d)
        tb.addAction("导出报表", self._on_export_stats)

    # ── ui layout ────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)

        main_splitter = QSplitter(Qt.Horizontal)

        # Left sidebar: project tree
        self._proj_tree = QTreeWidget()
        self._proj_tree.setHeaderLabel("项目浏览器")
        self._proj_tree.setMinimumWidth(180)
        self._proj_tree.setMaximumWidth(300)
        self._proj_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._proj_tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self._proj_tree.itemClicked.connect(self._on_tree_item_clicked)
        main_splitter.addWidget(self._proj_tree)

        # Center: 2D preview
        self._dxf_preview = DXFPreviewWidget()
        main_splitter.addWidget(self._dxf_preview)

        # Right: layer panel + 3D + stats
        right_splitter = QSplitter(Qt.Vertical)

        self._layer_panel = LayerPanel()
        self._layer_panel.layer_changed.connect(self._on_layers_changed)
        right_splitter.addWidget(self._layer_panel)

        self._gl_widget = GLWidget()
        right_splitter.addWidget(self._gl_widget)

        self._stats_panel = StatsPanel()
        right_splitter.addWidget(self._stats_panel)

        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 3)
        right_splitter.setStretchFactor(2, 1)

        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setStretchFactor(2, 3)

        root.addWidget(main_splitter)

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._status_label = QLabel("就绪 - 请新建项目或添加图纸 (DXF/DWG/PDF)")
        self._statusbar.addWidget(self._status_label)

    # ── project management ───────────────────────────────────────

    def _on_new_project(self):
        name, ok = QInputDialog.getText(self, "新建项目", "项目名称:")
        if not ok or not name.strip():
            return
        try:
            proj = self._project_mgr.create_project(name.strip())
            self._refresh_project_tree()
            self._status_label.setText(f"项目已创建: {proj.name} | 存储: {proj.storage_root}")
        except Exception as e:
            QMessageBox.critical(self, "创建失败", str(e))

    def _on_open_project(self):
        storage = self._project_mgr.storage_root
        path = QFileDialog.getExistingDirectory(self, "选择项目文件夹", storage)
        if not path:
            return
        try:
            self._project_mgr.open_project(path)
            self._refresh_project_tree()
            self._status_label.setText(f"已打开项目: {self._project_mgr.current_project.name}")
        except Exception as e:
            QMessageBox.critical(self, "打开失败", str(e))

    def _on_add_drawing(self):
        if not self._project_mgr.current_project:
            QMessageBox.warning(self, "提示", "请先新建或打开一个项目")
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "添加图纸", "",
            "CAD Files (*.dxf *.dwg *.pdf);;DXF (*.dxf);;DWG (*.dwg);;PDF (*.pdf);;All (*.*)"
        )
        if not path:
            return

        ext = path.lower()
        if ext.endswith('.dwg'):
            self._import_dwg(path)
        elif ext.endswith('.pdf'):
            self._import_pdf(path)
        else:
            self._import_dxf(path)

    # ── import handlers ──────────────────────────────────────────

    def _import_dxf(self, dxf_path):
        self._show_progress("解析DXF图纸", "读取文件中...")
        self._worker = _ParseWorker(self._parser, dxf_path)
        self._th = QThread()
        self._worker.moveToThread(self._th)
        self._th.started.connect(self._worker.run)
        self._worker.progress.connect(lambda p, m: (
            self._progress_dlg.set_value(p),
            self._progress_dlg.set_text(m),
        ))
        self._worker.finished.connect(lambda r: self._on_dxf_parsed(r, dxf_path))
        self._worker.finished.connect(self._th.quit)
        self._th.start()

    def _on_dxf_parsed(self, result, dxf_path):
        self._hide_progress()
        if isinstance(result, Exception):
            QMessageBox.critical(self, "解析失败", str(result))
            return

        self._current_dxf = result
        self._dxf_preview.load(result)
        self._layer_panel.load(result)
        self._stats_panel.clear()
        self._gl_widget.clear()
        self._layer_meshes = {}

        # Add to project
        di = self._project_mgr.add_drawing(
            dxf_path,
            entity_count=sum(len(v) for v in result.entities.values()),
            layer_count=len(result.layers),
        )
        self._refresh_project_tree()
        self._status_label.setText(
            f"已加载: {di.name} | 图层: {di.layer_count} | 实体: {di.entity_count}"
        )

    def _import_dwg(self, dwg_path):
        self._show_progress("DWG转换", "LibreDWG WASM 转换中...")
        self._worker2 = _DWGWorker(self._dwg_converter, dwg_path)
        self._th2 = QThread()
        self._worker2.moveToThread(self._th2)
        self._th2.started.connect(self._worker2.run)
        self._worker2.finished.connect(lambda r: self._on_dwg_done(r, dwg_path))
        self._worker2.finished.connect(self._th2.quit)
        self._th2.start()

    def _on_dwg_done(self, result, dwg_path):
        self._hide_progress()
        if isinstance(result, Exception):
            QMessageBox.warning(self, "DWG转换失败",
                f"自动转换失败: {result}\n\n"
                "请安装 ODA File Converter (免费) 或 Node.js 后重试。")
            return
        if result is None:
            self._show_dwg_help()
            return
        # result is the converted DXF path
        self._import_dxf(result)

    def _import_pdf(self, pdf_path):
        self._show_progress("PDF导入", "提取矢量图形...")
        # PDF import is fast enough to run inline
        try:
            import tempfile
            pdf_data = self._pdf_importer.extract(pdf_path)
            if not pdf_data.layers or not any(pdf_data.entities.get(ly) for ly in pdf_data.layers):
                self._hide_progress()
                QMessageBox.warning(self, "PDF无矢量数据",
                    "该PDF未检测到矢量线条，可能是扫描图片。\n请用CAD软件导出DXF后再导入。")
                return
            with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as f:
                tmp_dxf = f.name
            self._pdf_importer.export_dxf(pdf_data, tmp_dxf)
            self._hide_progress()
            self._import_dxf(tmp_dxf)
            self._translate_imported_text()
            try:
                os.unlink(tmp_dxf)
            except Exception:
                pass
        except Exception as e:
            self._hide_progress()
            QMessageBox.critical(self, "PDF导入失败", str(e))

    def _show_dwg_help(self):
        QMessageBox.information(self, "DWG转换",
            "DWG文件需要转换工具。\n\n"
            "方案1: 安装 ODA File Converter (免费, 一次安装)\n"
            "方案2: 安装 Node.js (免费, 一次安装)\n\n"
            "安装后所有DWG自动静默转换。")

    def _translate_imported_text(self):
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

    # ── 3D build ─────────────────────────────────────────────────

    def _on_build_3d(self):
        if self._current_dxf is None:
            QMessageBox.warning(self, "提示", "请先加载图纸")
            return

        self._show_progress("生成3D模型", "准备中...")
        thicknesses = self._layer_panel.get_thicknesses()
        enabled = self._layer_panel.get_enabled_layers()

        self._bw = _BuildWorker(self._builder, self._current_dxf, thicknesses, enabled)
        self._bth = QThread()
        self._bw.moveToThread(self._bth)
        self._bth.started.connect(self._bw.run)
        self._bw.progress.connect(lambda p, m: (
            self._progress_dlg.set_value(p),
            self._progress_dlg.set_text(m),
        ))
        self._bw.finished.connect(self._on_build_done)
        self._bw.finished.connect(self._bth.quit)
        self._bth.start()

    def _on_build_done(self, result):
        self._hide_progress()
        if isinstance(result, Exception):
            QMessageBox.critical(self, "3D生成失败", str(result))
            return

        self._layer_meshes = result
        self._gl_widget.load(result)

        stats = self._counter.count(self._current_dxf, result)
        self._stats_panel.load(stats)

        total = stats.get("component_count", 0)
        self._status_label.setText(f"3D模型已生成 | 图层: {len(result)} | 零件: {total}")

    # ── tree ─────────────────────────────────────────────────────

    def _refresh_project_tree(self):
        self._proj_tree.clear()
        proj = self._project_mgr.current_project
        if not proj:
            return
        root = QTreeWidgetItem([proj.name])
        root.setData(0, Qt.UserRole, "project")
        for i, d in enumerate(proj.drawings):
            child = QTreeWidgetItem([f"{d.name}  ({d.layer_count}层, {d.entity_count}实体)"])
            child.setData(0, Qt.UserRole, ("drawing", i))
            root.addChild(child)
        self._proj_tree.addTopLevelItem(root)
        root.setExpanded(True)

    def _on_tree_context_menu(self, pos):
        item = self._proj_tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.UserRole)
        if isinstance(data, tuple) and data[0] == "drawing":
            menu = QMenu()
            act_remove = menu.addAction("移除图纸")
            act = menu.exec(self._proj_tree.mapToGlobal(pos))
            if act == act_remove:
                idx = data[1]
                proj = self._project_mgr.current_project
                if proj and 0 <= idx < len(proj.drawings):
                    del proj.drawings[idx]
                    self._project_mgr._save_meta()
                    self._refresh_project_tree()

    def _on_tree_item_clicked(self, item, col):
        data = item.data(0, Qt.UserRole)
        if isinstance(data, tuple) and data[0] == "drawing":
            idx = data[1]
            proj = self._project_mgr.current_project
            if proj and 0 <= idx < len(proj.drawings):
                di = proj.drawings[idx]
                if os.path.isfile(di.dxf_path):
                    self._import_dxf(di.dxf_path)

    # ── progress ─────────────────────────────────────────────────

    def _show_progress(self, title, text):
        self._progress_dlg = ProgressDialog(self, title, cancelable=False)
        self._progress_dlg.set_text(text)
        self._progress_dlg.show()

    def _hide_progress(self):
        if self._progress_dlg:
            self._progress_dlg.accept()
            self._progress_dlg = None

    # ── slots ────────────────────────────────────────────────────

    def _on_layers_changed(self):
        if self._layer_meshes:
            self._gl_widget.update_visibility(self._layer_panel.get_enabled_layers())

    def _on_export_3d(self):
        if not self._layer_meshes:
            QMessageBox.warning(self, "提示", "请先生成3D模型")
            return
        proj = self._project_mgr.current_project
        default_dir = self._project_mgr.get_results_dir("export") if proj else ""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出3D模型", os.path.join(default_dir, "model.stl"),
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
        stats = self._stats_panel.get_data()
        if not stats:
            QMessageBox.warning(self, "提示", "请先生成3D模型")
            return
        proj = self._project_mgr.current_project
        default_dir = self._project_mgr.get_results_dir("export") if proj else ""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出统计报表", os.path.join(default_dir, "stats.xlsx"),
            "Excel (*.xlsx);;CSV (*.csv)"
        )
        if not path:
            return
        try:
            self._exporter.export_stats(stats, path)
            self._status_label.setText(f"报表已导出: {path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _on_reset_view(self):
        self._gl_widget.reset_view()

    def _on_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            new_root = SettingsDialog.get_storage_root()
            self._project_mgr.set_storage_root(new_root)
            self._status_label.setText(f"存储位置已更新: {new_root}")

    def _on_about(self):
        QMessageBox.about(self, "关于 CAD Analyzer",
            "CAD Analyzer v2.0\n\n"
            "多项目图纸分析 & 3D建模\n"
            "支持: DXF / DWG / PDF\n"
            "项目管理 · 进度显示 · 本地存储"
        )
