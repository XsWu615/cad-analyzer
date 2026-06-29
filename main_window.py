"""Main window with project management, multi-drawing, progress display."""

import os, tempfile
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QTreeWidget, QTreeWidgetItem, QMenu, QApplication, QInputDialog,
    QProgressBar, QDialog,
)
from PySide6.QtCore import Qt, QSettings, QTimer, QThread, Signal, QObject
from PySide6.QtGui import QAction, QKeySequence

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
from settings_dialog import SettingsDialog


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
        self._pending_dwg = ""

        self._setup_menu()
        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()

    # ── menu ─────────────────────────────────────────────────────

    def _setup_menu(self):
        mb = self.menuBar()
        f = mb.addMenu("文件(&F)")
        f.addAction("添加图纸(&A)...", self._on_add_drawing, "Ctrl+O")
        f.addSeparator()
        f.addAction("导出3D模型(&E)...", self._on_export_3d, "Ctrl+E")
        f.addAction("导出统计报表(&R)...", self._on_export_stats)
        f.addSeparator()
        f.addAction("退出(&X)", self.close, "Ctrl+Q")

        p = mb.addMenu("项目(&P)")
        p.addAction("新建项目(&N)...", self._on_new_project, "Ctrl+N")
        p.addAction("打开项目(&O)...", self._on_open_project)

        v = mb.addMenu("视图(&V)")
        v.addAction("重置3D视角(&R)", self._on_reset_view, "Ctrl+R")

        s = mb.addMenu("设置(&S)")
        s.addAction("存储位置(&S)...", self._on_settings)

        h = mb.addMenu("帮助(&H)")
        h.addAction("关于(&A)", self._on_about)

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

    # ── ui ───────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)

        ms = QSplitter(Qt.Horizontal)

        self._proj_tree = QTreeWidget()
        self._proj_tree.setHeaderLabel("项目浏览器")
        self._proj_tree.setMinimumWidth(150)
        self._proj_tree.setMaximumWidth(280)
        self._proj_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._proj_tree.customContextMenuRequested.connect(self._on_tree_menu)
        self._proj_tree.itemDoubleClicked.connect(self._on_tree_dblclick)
        ms.addWidget(self._proj_tree)

        self._dxf_preview = DXFPreviewWidget()
        ms.addWidget(self._dxf_preview)

        rs = QSplitter(Qt.Vertical)
        self._layer_panel = LayerPanel()
        self._layer_panel.layer_changed.connect(self._on_layers_changed)
        rs.addWidget(self._layer_panel)
        self._gl_widget = GLWidget()
        rs.addWidget(self._gl_widget)
        self._stats_panel = StatsPanel()
        rs.addWidget(self._stats_panel)
        rs.setStretchFactor(0, 1)
        rs.setStretchFactor(1, 3)
        rs.setStretchFactor(2, 1)

        ms.addWidget(rs)
        ms.setStretchFactor(0, 1)
        ms.setStretchFactor(1, 3)
        ms.setStretchFactor(2, 3)
        root.addWidget(ms)

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setVisible(False)
        self._status_label = QLabel("就绪")
        self._statusbar.addWidget(self._status_label)
        self._statusbar.addPermanentWidget(self._progress_bar)

    # ── status helper ────────────────────────────────────────────

    def _status(self, msg, progress=-1):
        self._status_label.setText(msg)
        if progress >= 0:
            self._progress_bar.setVisible(True)
            self._progress_bar.setValue(progress)
        else:
            self._progress_bar.setVisible(False)
        QApplication.processEvents()

    # ── project ──────────────────────────────────────────────────

    def _on_new_project(self):
        name, ok = QInputDialog.getText(self, "新建项目", "项目名称:")
        if not ok or not name.strip():
            return
        try:
            proj = self._project_mgr.create_project(name.strip())
            self._refresh_tree()
            self._status(f"项目已创建: {proj.name}")
        except Exception as e:
            QMessageBox.critical(self, "创建失败", str(e))

    def _on_open_project(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择项目文件夹", self._project_mgr.storage_root)
        if not path:
            return
        try:
            self._project_mgr.open_project(path)
            self._refresh_tree()
            self._status(f"已打开: {self._project_mgr.current_project.name}")
        except Exception as e:
            QMessageBox.critical(self, "打开失败", str(e))

    # ── add drawing ──────────────────────────────────────────────

    def _on_add_drawing(self):
        if not self._project_mgr.current_project:
            QMessageBox.warning(self, "提示", "请先新建或打开一个项目")
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "添加图纸", "",
            "CAD Files (*.dxf *.dwg *.pdf);;DXF (*.dxf);;DWG (*.dwg);;PDF (*.pdf);;All (*.*)")
        if not path:
            return

        ext = path.lower()
        if ext.endswith('.dwg'):
            self._import_dwg(path)
        elif ext.endswith('.pdf'):
            self._import_pdf(path)
        else:
            self._import_dxf(path)

    # ── DXF import ───────────────────────────────────────────────

    def _import_dxf(self, dxf_path):
        self._status("解析DXF中...", 0)
        try:
            data = self._parser.parse(dxf_path)
            self._status("解析完成", -1)

            self._current_dxf = data
            self._dxf_preview.load(data)
            self._layer_panel.load(data)
            self._stats_panel.clear()
            self._gl_widget.clear()
            self._layer_meshes = {}

            di = self._project_mgr.add_drawing(
                dxf_path,
                entity_count=sum(len(v) for v in data.entities.values()),
                layer_count=len(data.layers),
            )
            self._refresh_tree()
            self._status(f"已加载: {di.name} | {di.layer_count}层, {di.entity_count}实体")
        except Exception as e:
            QMessageBox.critical(self, "解析失败", str(e))
            self._status("解析失败")

    # ── DWG import (background) ──────────────────────────────────

    def _import_dwg(self, dwg_path):
        self._pending_dwg = dwg_path
        self._status("DWG转换中...", 0)

        self._worker = _DWGWorker(self._dwg_converter, dwg_path)
        self._th = QThread()
        self._worker.moveToThread(self._th)
        self._th.started.connect(self._worker.run)
        self._worker.done.connect(self._on_dwg_done)
        self._worker.done.connect(self._th.quit)
        self._th.finished.connect(self._th.deleteLater)
        self._th.start()

    def _on_dwg_done(self, result):
        self._status("转换完成", -1)
        if result is None or isinstance(result, Exception):
            QMessageBox.warning(self, "DWG转换失败",
                f"自动转换未成功。\n\n请确保已安装 Node.js。\n错误: {result}")
            self._status("DWG转换失败")
            return
        # result is DXF path
        self._import_dxf(result)

    # ── PDF import ───────────────────────────────────────────────

    def _import_pdf(self, pdf_path):
        self._status("导入PDF矢量...", 0)
        try:
            pdf_data = self._pdf_importer.extract(pdf_path)
            if not pdf_data.layers or not any(
                pdf_data.entities.get(ly) for ly in pdf_data.layers):
                self._status("PDF无矢量数据")
                QMessageBox.warning(self, "PDF无矢量数据",
                    "该PDF未检测到矢量线条，可能是扫描图片。")
                return

            with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as f:
                tmp_dxf = f.name
            self._pdf_importer.export_dxf(pdf_data, tmp_dxf)
            self._status("PDF导入完成", -1)
            self._import_dxf(tmp_dxf)
            self._translate_imported_text()
            try:
                os.unlink(tmp_dxf)
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, "PDF导入失败", str(e))
            self._status("PDF导入失败")

    # ── 3D build ─────────────────────────────────────────────────

    def _on_build_3d(self):
        if self._current_dxf is None:
            QMessageBox.warning(self, "提示", "请先加载图纸")
            return

        self._status("生成3D模型...", 0)
        thicknesses = self._layer_panel.get_thicknesses()
        enabled = self._layer_panel.get_enabled_layers()

        try:
            meshes = self._builder.build(self._current_dxf, thicknesses, enabled)
            self._layer_meshes = meshes
            self._gl_widget.load(meshes)

            stats = self._counter.count(self._current_dxf, meshes)
            self._stats_panel.load(stats)
            total = stats.get("component_count", 0)
            self._status(f"3D完成 | {len(meshes)}层, {total}个零件")
        except Exception as e:
            QMessageBox.critical(self, "3D生成失败", str(e))
            self._status("3D生成失败")

    # ── tree ─────────────────────────────────────────────────────

    def _refresh_tree(self):
        self._proj_tree.clear()
        proj = self._project_mgr.current_project
        if not proj:
            return
        root = QTreeWidgetItem([proj.name])
        for i, d in enumerate(proj.drawings):
            child = QTreeWidgetItem([f"{d.name}  ({d.layer_count}层)"])
            child.setData(0, Qt.UserRole, i)
            root.addChild(child)
        self._proj_tree.addTopLevelItem(root)
        root.setExpanded(True)

    def _on_tree_menu(self, pos):
        item = self._proj_tree.itemAt(pos)
        if not item or item.data(0, Qt.UserRole) is None:
            return
        menu = QMenu()
        act = menu.addAction("移除")
        if menu.exec(self._proj_tree.mapToGlobal(pos)) == act:
            idx = item.data(0, Qt.UserRole)
            proj = self._project_mgr.current_project
            if proj and 0 <= idx < len(proj.drawings):
                del proj.drawings[idx]
                self._project_mgr._save_meta()
                self._refresh_tree()

    def _on_tree_dblclick(self, item, col):
        idx = item.data(0, Qt.UserRole)
        if idx is None:
            return
        proj = self._project_mgr.current_project
        if proj and 0 <= idx < len(proj.drawings):
            di = proj.drawings[idx]
            if os.path.isfile(di.dxf_path):
                self._import_dxf(di.dxf_path)

    # ── translate ────────────────────────────────────────────────

    def _translate_imported_text(self):
        if self._current_dxf is None:
            return
        translated = 0
        for entities in self._current_dxf.entities.values():
            for e in entities:
                if e.dxftype in ('TEXT', 'MTEXT'):
                    orig = e.geometry.get('text', '')
                    if orig:
                        new = self._translator.translate(orig)
                        if new != orig:
                            e.geometry['text'] = new
                            translated += 1
        if translated > 0:
            self._dxf_preview.load(self._current_dxf)
            self._status(f"已翻译 {translated} 处文本")

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
            "STL (*.stl);;OBJ (*.obj);;GLB (*.glb)")
        if not path:
            return
        try:
            self._exporter.export_3d(self._layer_meshes, path)
            self._status(f"已导出: {path}")
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
            "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return
        try:
            self._exporter.export_stats(stats, path)
            self._status(f"已导出: {path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _on_reset_view(self):
        self._gl_widget.reset_view()

    def _on_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._project_mgr.set_storage_root(SettingsDialog.get_storage_root())
            self._status("存储位置已更新")

    def _on_about(self):
        QMessageBox.about(self, "关于 CAD Analyzer",
            "CAD Analyzer v2.0\n\n"
            "多项目图纸分析 & 3D建模\n"
            "支持: DXF / DWG / PDF\n"
            "项目管理 · 进度显示 · 本地存储")


# ── DWG worker ───────────────────────────────────────────────────

class _DWGWorker(QObject):
    done = Signal(object)

    def __init__(self, converter, dwg_path):
        super().__init__()
        self._c = converter
        self._p = dwg_path

    def run(self):
        try:
            r = self._c.auto_convert(self._p)
            self.done.emit(r)
        except Exception as e:
            self.done.emit(e)
