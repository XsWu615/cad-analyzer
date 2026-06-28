from typing import Dict, Optional
import numpy as np
import pyvista as pv
from PySide6.QtWidgets import QWidget, QVBoxLayout
from pyvistaqt import QtInteractor

import trimesh


class GLWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._meshes: Dict[str, trimesh.Trimesh] = {}
        self._actors: Dict[str, any] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plotter = QtInteractor(self)
        self._plotter.set_background('#1e1e1e')
        self._plotter.show_grid(color='#444444', show_xaxis=True, show_yaxis=True)
        self._plotter.add_axes(color='#888888')
        layout.addWidget(self._plotter)

    def load(self, meshes: Dict[str, trimesh.Trimesh]):
        self._plotter.clear()
        self._actors.clear()
        self._meshes = meshes

        cmap = [
            '#4ecdc4', '#ff6b6b', '#ffe66d', '#a8e6cf', '#ff8b94',
            '#b8a9c9', '#f7dc6f', '#82e0aa', '#f8c471', '#85c1e9',
        ]

        for i, (layer, mesh) in enumerate(meshes.items()):
            if mesh is None or mesh.vertices.shape[0] == 0:
                continue
            color = cmap[i % len(cmap)]
            try:
                pv_mesh = pv.wrap(mesh)
                actor = self._plotter.add_mesh(
                    pv_mesh, color=color, show_edges=True,
                    edge_color='#333333', label=layer, opacity=0.85,
                )
                self._actors[layer] = actor
            except Exception:
                pass

        self._plotter.view_isometric()
        self._plotter.render()

    def update_visibility(self, enabled_layers: list):
        for layer, actor in self._actors.items():
            visible = layer in enabled_layers
            if hasattr(actor, 'SetVisibility'):
                actor.SetVisibility(visible)
        self._plotter.render()

    def clear(self):
        self._plotter.clear()
        self._actors.clear()
        self._meshes.clear()
        self._plotter.show_grid(color='#444444')

    def reset_view(self):
        self._plotter.view_isometric()
        self._plotter.render()
