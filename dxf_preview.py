from PySide6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as mpatches
import numpy as np

from cad_parser import DXFData


class DXFPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._fig = Figure(figsize=(5, 4), facecolor='#1e1e1e')
        self._canvas = FigureCanvas(self._fig)
        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor('#1e1e1e')
        self._ax.tick_params(colors='#888')
        self._ax.spines['bottom'].set_color('#555')
        self._ax.spines['left'].set_color('#555')
        self._ax.spines['top'].set_visible(False)
        self._ax.spines['right'].set_visible(False)
        self._ax.set_aspect('equal')
        self._ax.set_title("DXF 2D 预览", color='#ccc')

        layout.addWidget(self._canvas)

    def load(self, data: DXFData):
        self._data = data
        self._ax.clear()
        self._ax.set_facecolor('#1e1e1e')
        self._ax.set_title("DXF 2D 预览", color='#ccc')

        layer_colors = {}
        cmap = ['#4ecdc4', '#ff6b6b', '#ffe66d', '#a8e6cf', '#ff8b94',
                '#b8a9c9', '#f7dc6f', '#82e0aa', '#f8c471', '#85c1e9']
        for i, layer in enumerate(data.layers):
            layer_colors[layer] = cmap[i % len(cmap)]

        for layer, entities in data.entities.items():
            color = layer_colors.get(layer, '#ffffff')
            for e in entities:
                self._draw_entity(e, color)

        # legend
        patches = []
        for layer in data.layers:
            color = layer_colors.get(layer, '#ffffff')
            patches.append(mpatches.Patch(color=color, label=layer))
        if patches:
            self._ax.legend(handles=patches, loc='upper right',
                          fontsize=7, facecolor='#333', edgecolor='#555',
                          labelcolor='#ccc')

        if data.bounds != (0, 0, 0, 0):
            margin = max(data.bounds[2] - data.bounds[0], data.bounds[3] - data.bounds[1]) * 0.05
            self._ax.set_xlim(data.bounds[0] - margin, data.bounds[2] + margin)
            self._ax.set_ylim(data.bounds[1] - margin, data.bounds[3] + margin)

        self._fig.tight_layout()
        self._canvas.draw()

    def _draw_entity(self, entity, color):
        g = entity.geometry
        t = entity.dxftype

        try:
            if t == 'LINE':
                self._ax.plot(
                    [g['start'][0], g['end'][0]],
                    [g['start'][1], g['end'][1]],
                    color=color, linewidth=0.8
                )
            elif t == 'CIRCLE':
                circle = mpatches.Circle(
                    (g['center'][0], g['center'][1]),
                    g['radius'], fill=False, color=color, linewidth=0.8
                )
                self._ax.add_patch(circle)
            elif t == 'ARC':
                arc = mpatches.Arc(
                    (g['center'][0], g['center'][1]),
                    2 * g['radius'], 2 * g['radius'],
                    angle=0, theta1=g['start_angle'], theta2=g['end_angle'],
                    color=color, linewidth=0.8
                )
                self._ax.add_patch(arc)
            elif t in ('LWPOLYLINE', 'POLYLINE', 'SPLINE'):
                pts = g.get('points', [])
                if pts:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    self._ax.plot(xs, ys, color=color, linewidth=0.8)
                    if entity.closed:
                        self._ax.plot([xs[-1], xs[0]], [ys[-1], ys[0]],
                                    color=color, linewidth=0.8, linestyle='--')
            elif t == 'ELLIPSE':
                # approximate
                c = g['center']
                ratio = g.get('ratio', 1.0)
                rx = np.linalg.norm(g['major_axis'][:2])
                ry = rx * ratio
                ell = mpatches.Ellipse(
                    (c[0], c[1]), 2 * rx, 2 * ry,
                    fill=False, color=color, linewidth=0.8
                )
                self._ax.add_patch(ell)
            elif t in ('TEXT', 'MTEXT'):
                insert = g.get('insert', (0, 0, 0))
                text = g.get('text', '')[:20]
                self._ax.text(insert[0], insert[1], text,
                            color='#aaa', fontsize=5, clip_on=True)
        except Exception:
            pass

    def clear(self):
        self._ax.clear()
        self._ax.set_facecolor('#1e1e1e')
        self._canvas.draw()
