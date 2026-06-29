"""PDF vector graphics extractor — converts PDF paths to DXF-like data."""

import os
import fitz  # pymupdf
import ezdxf
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np


@dataclass
class PDFEntity:
    dxftype: str
    layer: str
    geometry: Dict = field(default_factory=dict)
    closed: bool = False


@dataclass
class PDFData:
    filename: str
    layers: List[str]
    entities: Dict[str, List[PDFEntity]]
    page_count: int
    bounds: tuple  # (min_x, min_y, max_x, max_y)


class PDFImporter:
    """Extract vector paths from PDF and convert to CAD-compatible format."""

    def __init__(self):
        self._curve_steps = 32  # bezier curve approximation segments

    def extract(self, filepath: str) -> PDFData:
        doc = fitz.open(filepath)
        all_entities: Dict[str, List[PDFEntity]] = {}
        all_points = []
        layer_idx = 0

        for page in doc:
            paths = page.get_drawings()
            page_layer = f"Page{page.number + 1}"
            all_entities[page_layer] = []

            for path in paths:
                # Use PDF fill/stroke color as sub-layer
                fill = path.get("fill", (1, 1, 1))
                stroke = path.get("color", (0, 0, 0))
                layer_name = self._color_to_layer(stroke, fill)

                if layer_name not in all_entities:
                    all_entities[layer_name] = []

                entities = self._path_to_entities(path, layer_name)
                all_entities[layer_name].extend(entities)

                for e in entities:
                    pts = self._entity_points(e)
                    all_points.extend(pts)

        # compute bounds
        if all_points:
            xs = [p[0] for p in all_points]
            ys = [p[1] for p in all_points]
            bounds = (min(xs), min(ys), max(xs), max(ys))
        else:
            bounds = (0, 0, 0, 0)

        # filter empty layers
        layers = sorted([ly for ly, ents in all_entities.items() if ents])
        if not layers:
            layers = ["Page1"]

        return PDFData(
            filename=filepath,
            layers=layers,
            entities={ly: all_entities.get(ly, []) for ly in layers},
            page_count=doc.page_count,
            bounds=bounds,
        )

    def export_dxf(self, pdf_data: PDFData, output_path: str):
        """Convert extracted PDF data to a DXF file for the existing pipeline."""
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()

        # ensure layers exist
        for layer in pdf_data.layers:
            if layer not in doc.layers:
                doc.layers.add(layer)

        for layer, entities in pdf_data.entities.items():
            for e in entities:
                self._add_dxf_entity(msp, e)

        doc.saveas(output_path)
        return output_path

    def _color_to_layer(self, stroke, fill) -> str:
        """Map color to a layer name."""
        r, g, b = stroke[:3] if stroke else (0, 0, 0)
        # Map common CAD colors to meaningful layer names
        if (r + g + b) < 0.1:
            return "Outline"
        elif r > 0.8 and g < 0.2 and b < 0.2:
            return "Holes"
        elif r < 0.2 and g > 0.8 and b < 0.2:
            return "Pockets"
        elif r < 0.2 and g < 0.2 and b > 0.8:
            return "Mounts"
        elif r > 0.8 and g > 0.8 and b < 0.2:
            return "Text"
        elif r > 0.8 and g < 0.2 and b > 0.8:
            return "Dimension"
        elif abs(r - g) < 0.1 and abs(g - b) < 0.1:
            shade = (r + g + b) / 3
            if shade < 0.3:
                return "Outline"
            elif shade > 0.7:
                return "Construction"
            return "Outline"
        return "Geometry"

    def _path_to_entities(self, path: dict, layer: str) -> List[PDFEntity]:
        """Convert a PDF drawing path to CAD entities."""
        entities = []
        items = path.get("items", [])
        fill = path.get("fill")
        is_filled = fill is not None and len(fill) > 0 and fill[0] is not None

        for item in items:
            op = item[0]  # operation: 'l' line, 'c' curve, 're' rect, 'cl' close
            if op == 'l':
                p0 = (item[1].x, item[1].y)
                p1 = (item[2].x, item[2].y)
                entities.append(PDFEntity(
                    dxftype='LINE', layer=layer,
                    geometry={'start': (*p0, 0.0), 'end': (*p1, 0.0)},
                ))
            elif op == 'c':
                p0 = (item[1].x, item[1].y)
                c1 = (item[2].x, item[2].y)
                c2 = (item[3].x, item[3].y)
                p3 = (item[4].x, item[4].y)
                # approximate bezier with polyline
                points = self._bezier_points(p0, c1, c2, p3)
                entities.append(PDFEntity(
                    dxftype='LWPOLYLINE', layer=layer,
                    geometry={'points': points}, closed=is_filled,
                ))
            elif op == 're':
                # rectangle: (x, y, w, h) → closed polyline
                x, y, w, h = item[1].x, item[1].y, item[2].x, item[2].y
                pts = [
                    (x, y, 0.0), (x + w, y, 0.0),
                    (x + w, y - h, 0.0), (x, y - h, 0.0),
                ]
                entities.append(PDFEntity(
                    dxftype='LWPOLYLINE', layer=layer,
                    geometry={'points': pts}, closed=True,
                ))
            elif op == 'qu':
                # quad bezier
                p0 = (item[1].x, item[1].y)
                c1 = (item[2].x, item[2].y)
                p2 = (item[3].x, item[3].y)
                points = self._bezier_quad_points(p0, c1, p2)
                entities.append(PDFEntity(
                    dxftype='LWPOLYLINE', layer=layer,
                    geometry={'points': points}, closed=is_filled,
                ))

        # If path is filled and closed, mark the last entity
        if is_filled and entities:
            # Add closing segment if needed
            for e in entities:
                if e.dxftype == 'LWPOLYLINE':
                    e.closed = True

        return entities

    def _bezier_points(self, p0, c1, c2, p3) -> List[tuple]:
        """Approximate cubic bezier with polyline."""
        pts = []
        for i in range(self._curve_steps + 1):
            t = i / self._curve_steps
            x = ((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * c1[0]
                 + 3 * (1 - t) * t ** 2 * c2[0] + t ** 3 * p3[0])
            y = ((1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * c1[1]
                 + 3 * (1 - t) * t ** 2 * c2[1] + t ** 3 * p3[1])
            pts.append((x, y, 0.0))
        return pts

    def _bezier_quad_points(self, p0, c1, p2) -> List[tuple]:
        """Approximate quadratic bezier with polyline."""
        pts = []
        for i in range(self._curve_steps + 1):
            t = i / self._curve_steps
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c1[0] + t ** 2 * p2[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c1[1] + t ** 2 * p2[1]
            pts.append((x, y, 0.0))
        return pts

    def _entity_points(self, e: PDFEntity) -> List[tuple]:
        pts = []
        g = e.geometry
        if 'start' in g:
            pts.append((g['start'][0], g['start'][1]))
            pts.append((g['end'][0], g['end'][1]))
        if 'points' in g:
            pts.extend([(p[0], p[1]) for p in g['points']])
        return pts

    def _add_dxf_entity(self, msp, entity: PDFEntity):
        """Add a PDF entity to a DXF modelspace."""
        g = entity.geometry
        try:
            if entity.dxftype == 'LINE':
                msp.add_line(g['start'], g['end'], dxfattribs={'layer': entity.layer})
            elif entity.dxftype == 'LWPOLYLINE':
                poly = msp.add_lwpolyline(
                    [(p[0], p[1]) for p in g['points']],
                    dxfattribs={'layer': entity.layer},
                )
                poly.closed = entity.closed
        except Exception:
            pass
