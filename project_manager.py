"""Project management — create/open projects, manage drawings, persist results."""

import os
import json
import shutil
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict


@dataclass
class DrawingInfo:
    name: str
    dxf_path: str = ""
    layer_count: int = 0
    entity_count: int = 0
    component_count: int = 0
    import_time: str = ""


@dataclass
class ProjectInfo:
    name: str
    created: str = ""
    modified: str = ""
    drawings: List[DrawingInfo] = field(default_factory=list)
    storage_root: str = ""

    def to_dict(self):
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d):
        d["drawings"] = [DrawingInfo(**di) for di in d.get("drawings", [])]
        return cls(**d)


class ProjectManager:
    def __init__(self):
        self._current_project: Optional[ProjectInfo] = None
        self._project_dir: str = ""
        self._storage_root: str = ""

    @property
    def current_project(self) -> Optional[ProjectInfo]:
        return self._current_project

    @property
    def storage_root(self) -> str:
        return self._storage_root

    def set_storage_root(self, path: str):
        self._storage_root = path
        os.makedirs(path, exist_ok=True)

    def create_project(self, name: str) -> ProjectInfo:
        if not self._storage_root:
            raise ValueError("请先设置存储位置")

        self._project_dir = os.path.join(self._storage_root, name)
        os.makedirs(self._project_dir, exist_ok=True)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        proj = ProjectInfo(
            name=name,
            created=now,
            modified=now,
            storage_root=self._storage_root,
        )
        self._current_project = proj
        self._save_meta()
        return proj

    def open_project(self, project_path: str):
        """Open existing project from its directory."""
        meta_path = os.path.join(project_path, "project.json")
        if not os.path.isfile(meta_path):
            raise FileNotFoundError(f"项目文件不存在: {meta_path}")

        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._project_dir = project_path
        self._current_project = ProjectInfo.from_dict(data)
        # fix storage_root if project moved
        parent = os.path.dirname(project_path)
        self._storage_root = parent
        self._current_project.storage_root = parent

    def add_drawing(self, dxf_path: str, entity_count: int = 0,
                    layer_count: int = 0) -> DrawingInfo:
        if not self._current_project:
            raise ValueError("请先创建或打开项目")

        name = os.path.splitext(os.path.basename(dxf_path))[0]
        # copy DXF to project drawings folder
        drawings_dir = os.path.join(self._project_dir, "drawings")
        os.makedirs(drawings_dir, exist_ok=True)

        # use unique name if duplicate
        dest = os.path.join(drawings_dir, os.path.basename(dxf_path))
        if os.path.isfile(dest):
            base, ext = os.path.splitext(os.path.basename(dxf_path))
            dest = os.path.join(drawings_dir, f"{base}_{len(self._current_project.drawings)}{ext}")

        shutil.copy2(dxf_path, dest)

        di = DrawingInfo(
            name=name,
            dxf_path=dest,
            layer_count=layer_count,
            entity_count=entity_count,
            import_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._current_project.drawings.append(di)
        self._current_project.modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_meta()
        return di

    def update_drawing_stats(self, index: int, layer_count: int = 0,
                             entity_count: int = 0, component_count: int = 0):
        if self._current_project and 0 <= index < len(self._current_project.drawings):
            d = self._current_project.drawings[index]
            if layer_count:
                d.layer_count = layer_count
            if entity_count:
                d.entity_count = entity_count
            if component_count:
                d.component_count = component_count
            self._save_meta()

    def get_results_dir(self, drawing_name: str) -> str:
        if not self._project_dir:
            return ""
        results_dir = os.path.join(self._project_dir, "results", drawing_name)
        os.makedirs(results_dir, exist_ok=True)
        return results_dir

    def list_projects(self) -> List[str]:
        """List all project names in storage root."""
        if not self._storage_root or not os.path.isdir(self._storage_root):
            return []
        projects = []
        for name in os.listdir(self._storage_root):
            proj_dir = os.path.join(self._storage_root, name)
            meta = os.path.join(proj_dir, "project.json")
            if os.path.isfile(meta):
                projects.append(name)
        return sorted(projects)

    def _save_meta(self):
        if not self._current_project or not self._project_dir:
            return
        meta_path = os.path.join(self._project_dir, "project.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self._current_project.to_dict(), f, ensure_ascii=False, indent=2)
