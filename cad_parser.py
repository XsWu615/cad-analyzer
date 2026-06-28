from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import ezdxf


@dataclass
class DXFEntity:
    """Parsed DXF entity wrapper."""
    handle: str
    dxftype: str
    layer: str
    geometry: Dict[str, Any] = field(default_factory=dict)
    closed: bool = False


@dataclass
class DXFData:
    """Parsed DXF document."""
    filename: str
    layers: List[str]
    entities: Dict[str, List[DXFEntity]] = field(default_factory=dict)
    blocks: Dict[str, List[DXFEntity]] = field(default_factory=dict)
    bounds: tuple = (0, 0, 0, 0)  # min_x, min_y, max_x, max_y


class CADParser:
    def parse(self, filepath: str) -> DXFData:
        doc = ezdxf.readfile(filepath)
        msp = doc.modelspace()
        layers = [layer.dxf.name for layer in doc.layers]

        entities: Dict[str, List[DXFEntity]] = {ly: [] for ly in layers}
        all_points = []

        for e in msp:
            layer = e.dxf.layer
            if layer not in entities:
                entities[layer] = []

            parsed = self._parse_entity(e)
            if parsed:
                entities[layer].append(parsed)
                pts = self._entity_points(parsed)
                all_points.extend(pts)

        # compute bounds
        if all_points:
            xs = [p[0] for p in all_points]
            ys = [p[1] for p in all_points]
            bounds = (min(xs), min(ys), max(xs), max(ys))
        else:
            bounds = (0, 0, 0, 0)

        # extract blocks
        blocks = {}
        for block in doc.blocks:
            if block.name.startswith('*'):
                continue
            block_entities = []
            for e in block:
                parsed = self._parse_entity(e)
                if parsed:
                    block_entities.append(parsed)
            if block_entities:
                blocks[block.name] = block_entities

        return DXFData(
            filename=filepath,
            layers=layers,
            entities=entities,
            blocks=blocks,
            bounds=bounds,
        )

    def _parse_entity(self, e) -> Optional[DXFEntity]:
        t = e.dxftype()
        geom = {}
        closed = False

        try:
            if t == 'LINE':
                geom = {
                    'start': (e.dxf.start.x, e.dxf.start.y, e.dxf.start.z),
                    'end': (e.dxf.end.x, e.dxf.end.y, e.dxf.end.z),
                }
            elif t == 'CIRCLE':
                geom = {
                    'center': (e.dxf.center.x, e.dxf.center.y, e.dxf.center.z),
                    'radius': e.dxf.radius,
                }
                closed = True
            elif t == 'ARC':
                geom = {
                    'center': (e.dxf.center.x, e.dxf.center.y, e.dxf.center.z),
                    'radius': e.dxf.radius,
                    'start_angle': e.dxf.start_angle,
                    'end_angle': e.dxf.end_angle,
                }
            elif t == 'LWPOLYLINE':
                points = [(p[0], p[1], 0.0) for p in e.get_points()]
                geom = {
                    'points': points,
                    'elevation': e.dxf.elevation,
                }
                closed = e.closed
            elif t == 'POLYLINE':
                points = [(p[0], p[1], p[2]) for p in e.points()]
                geom = {'points': points}
                closed = e.is_closed
            elif t == 'SPLINE':
                try:
                    points = [(p[0], p[1], p[2]) for p in e.control_points]
                except Exception:
                    points = [(p[0], p[1], 0.0) for p in e.control_points]
                geom = {'points': points}
                closed = e.closed
            elif t == 'ELLIPSE':
                geom = {
                    'center': (e.dxf.center.x, e.dxf.center.y, e.dxf.center.z),
                    'major_axis': (e.dxf.major_axis.x, e.dxf.major_axis.y, e.dxf.major_axis.z),
                    'ratio': e.dxf.ratio,
                    'start_param': e.dxf.start_param,
                    'end_param': e.dxf.end_param,
                }
                closed = True
            elif t == 'TEXT':
                geom = {
                    'insert': (e.dxf.insert.x, e.dxf.insert.y, e.dxf.insert.z),
                    'text': e.dxf.text,
                    'height': e.dxf.height,
                }
            elif t == 'MTEXT':
                geom = {
                    'insert': (e.dxf.insert.x, e.dxf.insert.y, e.dxf.insert.z),
                    'text': e.text,
                    'height': e.dxf.char_height,
                }
            elif t == 'DIMENSION':
                geom = {'type': 'dimension'}
            elif t == 'INSERT':
                geom = {
                    'name': e.dxf.name,
                    'insert': (e.dxf.insert.x, e.dxf.insert.y, e.dxf.insert.z),
                    'scale': (e.dxf.xscale, e.dxf.yscale, e.dxf.zscale),
                    'rotation': e.dxf.rotation,
                }
            elif t == 'POINT':
                geom = {
                    'location': (e.dxf.location.x, e.dxf.location.y, e.dxf.location.z),
                }
            else:
                return None

            return DXFEntity(
                handle=e.dxf.handle,
                dxftype=t,
                layer=e.dxf.layer,
                geometry=geom,
                closed=closed,
            )
        except Exception:
            return None

    def _entity_points(self, e: DXFEntity) -> List[tuple]:
        pts = []
        g = e.geometry
        if e.dxftype in ('LINE',):
            pts.append(g['start'])
            pts.append(g['end'])
        elif e.dxftype in ('CIRCLE', 'ARC'):
            c = g['center']
            pts.append((c[0] - g['radius'], c[1] - g['radius']))
            pts.append((c[0] + g['radius'], c[1] + g['radius']))
        elif e.dxftype in ('LWPOLYLINE', 'POLYLINE', 'SPLINE'):
            pts.extend(g.get('points', []))
        elif e.dxftype == 'ELLIPSE':
            c = g['center']
            pts.append(c)
        elif e.dxftype in ('TEXT', 'MTEXT', 'INSERT'):
            pts.append(g.get('insert', (0, 0, 0)))
        return [(p[0], p[1]) for p in pts]
