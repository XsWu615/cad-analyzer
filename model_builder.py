from typing import Dict, List, Optional
import numpy as np
import trimesh
from shapely.geometry import Polygon, LineString, Point as SPoint
from shapely.ops import unary_union, polygonize
from shapely import affinity
import triangle as tr

from cad_parser import DXFData, DXFEntity


class ModelBuilder:
    def __init__(self):
        self._circle_segments = 64

    def build(
        self,
        dxf_data: DXFData,
        layer_thicknesses: Dict[str, float],
        enabled_layers: List[str],
    ) -> Dict[str, trimesh.Trimesh]:
        meshes = {}
        for layer in enabled_layers:
            if layer not in dxf_data.entities:
                continue
            thickness = layer_thicknesses.get(layer, 1.0)
            if thickness <= 0:
                continue

            mesh = self._build_layer(dxf_data.entities[layer], thickness)
            if mesh is not None:
                meshes[layer] = mesh

        return meshes

    def _build_layer(self, entities: List[DXFEntity], thickness: float) -> Optional[trimesh.Trimesh]:
        layer_meshes = []

        # collect closed contours
        contours = self._find_closed_contours(entities)

        for contour in contours:
            poly = self._polygon_from_contour(contour)
            if poly is None or poly.is_empty:
                continue
            if not poly.is_valid:
                poly = poly.buffer(0)

            mesh = self._extrude_polygon(poly, thickness)
            if mesh is not None:
                layer_meshes.append(mesh)

        # circles → cylinders
        for e in entities:
            if e.dxftype == 'CIRCLE':
                c = e.geometry['center']
                r = e.geometry['radius']
                cyl = trimesh.creation.cylinder(
                    radius=r,
                    height=thickness,
                    sections=self._circle_segments,
                )
                cyl.apply_translation([c[0], c[1], thickness / 2])
                layer_meshes.append(cyl)

            elif e.dxftype == 'ELLIPSE':
                mesh = self._extrude_ellipse(e, thickness)
                if mesh is not None:
                    layer_meshes.append(mesh)

        if not layer_meshes:
            return None

        if len(layer_meshes) == 1:
            return layer_meshes[0]

        return trimesh.util.concatenate(layer_meshes)

    def _find_closed_contours(self, entities: List[DXFEntity]) -> List[List[DXFEntity]]:
        """Find closed polyline contours and closed line loops."""
        contours = []

        for e in entities:
            if e.dxftype in ('LWPOLYLINE', 'POLYLINE') and e.closed:
                contours.append([e])

        # try to find closed loops from individual LINE entities
        lines = [e for e in entities if e.dxftype == 'LINE']
        if len(lines) >= 3:
            contours.extend(self._find_line_loops(lines))

        return contours

    def _find_line_loops(self, lines: List[DXFEntity]) -> List[List[DXFEntity]]:
        """Build a graph of connected line endpoints and find closed loops."""
        loops = []
        used = set()

        # adjacency: endpoint → list of (line, other_endpoint)
        from collections import defaultdict
        TOL = 0.01

        def pt_key(p):
            return (round(p[0] / TOL) * TOL, round(p[1] / TOL) * TOL)

        adj = defaultdict(list)
        for line in lines:
            s = pt_key(line.geometry['start'])
            e_pt = pt_key(line.geometry['end'])
            adj[s].append((line, e_pt))
            adj[e_pt].append((line, s))

        # simple loop detection: for each connected component, try to walk
        remaining = set(id(l) for l in lines)
        while remaining:
            start_id = remaining.pop()
            start_line = next(l for l in lines if id(l) == start_id)
            # walk
            path = [start_line]
            s = pt_key(start_line.geometry['start'])
            e = pt_key(start_line.geometry['end'])
            current_pt = e
            start_pt = s
            found = False

            for _ in range(len(lines)):
                neighbors = [n for n in adj[current_pt] if id(n[0]) in remaining]
                if not neighbors:
                    break
                next_line, next_pt = neighbors[0]
                remaining.discard(id(next_line))
                path.append(next_line)
                if pt_key(next_pt) == start_pt:
                    found = True
                    break
                current_pt = next_pt

            if found and len(path) >= 3:
                loops.append(path)

        return loops

    def _polygon_from_contour(self, entities: List[DXFEntity]) -> Optional[Polygon]:
        """Convert contour entities to a Shapely Polygon."""
        all_points = []
        for e in entities:
            if e.dxftype in ('LWPOLYLINE', 'POLYLINE'):
                pts = e.geometry.get('points', [])
                all_points.extend([(p[0], p[1]) for p in pts])
            elif e.dxftype == 'LINE':
                all_points.append((e.geometry['start'][0], e.geometry['start'][1]))
            elif e.dxftype == 'ARC':
                # approximate arc with line segments
                c = e.geometry['center']
                r = e.geometry['radius']
                sa = np.radians(e.geometry['start_angle'])
                ea = np.radians(e.geometry['end_angle'])
                if ea < sa:
                    ea += 2 * np.pi
                angles = np.linspace(sa, ea, 32)
                pts = [(c[0] + r * np.cos(a), c[1] + r * np.sin(a)) for a in angles]
                all_points.extend(pts)

        if len(all_points) < 3:
            return None

        # deduplicate consecutive points
        clean = [all_points[0]]
        for p in all_points[1:]:
            if not np.allclose(p, clean[-1], atol=1e-6):
                clean.append(p)

        if len(clean) < 3:
            return None

        try:
            if not np.allclose(clean[0], clean[-1], atol=1e-6):
                clean.append(clean[0])
            return Polygon(clean)
        except Exception:
            return None

    def _extrude_polygon(self, poly: Polygon, thickness: float) -> Optional[trimesh.Trimesh]:
        """Extrude a 2D polygon into a 3D mesh."""
        if poly.is_empty or poly.area < 1e-9:
            return None

        # triangulate the polygon
        exterior = np.array(poly.exterior.coords[:-1])  # remove duplicate last point
        if len(exterior) < 3:
            return None

        try:
            tri = self._triangulate(exterior, poly)
            if tri is None:
                return None

            vertices_2d, faces = tri
            # Bottom face (z=0, reversed winding)
            bottom = np.column_stack([vertices_2d, np.zeros(len(vertices_2d))])
            # Top face (z=thickness)
            top = np.column_stack([vertices_2d, np.full(len(vertices_2d), thickness)])

            all_verts = np.vstack([bottom, top])
            n_verts = len(vertices_2d)

            # top faces with offset
            top_faces = faces[:, ::-1] + n_verts

            # side walls from exterior edges
            n_ext = len(exterior)
            side_faces = []
            for i in range(n_ext):
                j = (i + 1) % n_ext
                # two triangles per quad
                side_faces.append([i, j, j + n_verts])
                side_faces.append([i, j + n_verts, i + n_verts])

            all_faces = np.vstack([faces, top_faces, np.array(side_faces)])

            return trimesh.Trimesh(vertices=all_verts, faces=all_faces)
        except Exception:
            return None

    def _triangulate(self, exterior_points, poly):
        """Triangulate polygon with holes using triangle library."""
        # build hole points
        holes = []
        hole_points = []
        for interior in poly.interiors:
            coords = np.array(interior.coords[:-1])
            hole_points.append(coords)
            centroid = coords.mean(axis=0)
            holes.append(centroid)

        all_points = [exterior_points]
        if hole_points:
            all_points.extend(hole_points)

        segments = []
        offset = 0
        for pts in all_points:
            n = len(pts)
            for i in range(n):
                segments.append([offset + i, offset + (i + 1) % n])
            offset += n

        vertices = np.vstack(all_points)

        tri_input = {
            'vertices': vertices,
            'segments': np.array(segments),
        }
        if holes:
            tri_input['holes'] = np.array(holes)

        try:
            result = tr.triangulate(tri_input, 'p')
            return result['vertices'], result['triangles']
        except Exception:
            # fallback: use trimesh's built-in triangulation
            try:
                mesh2d = trimesh.creation.triangulate(
                    poly, engine='triangle'
                )
                v2d = mesh2d.vertices[:, :2]
                f = mesh2d.faces
                return v2d, f
            except Exception:
                return None

    def _extrude_ellipse(self, entity: DXFEntity, thickness: float) -> Optional[trimesh.Trimesh]:
        """Approximate ellipse as polygon, then extrude."""
        g = entity.geometry
        c = g['center']
        ratio = g.get('ratio', 1.0)

        angles = np.linspace(0, 2 * np.pi, self._circle_segments, endpoint=False)
        rx = np.linalg.norm(g['major_axis'][:2])
        ry = rx * ratio
        pts = np.column_stack([
            c[0] + rx * np.cos(angles),
            c[1] + ry * np.sin(angles),
        ])
        poly = Polygon(pts)
        return self._extrude_polygon(poly, thickness)
