from typing import Dict, List, Any
import numpy as np
import pandas as pd
from collections import Counter

from cad_parser import DXFData


class PartCounter:
    def __init__(self):
        self._connectivity_threshold = 0.1  # mm

    def count(self, dxf_data: DXFData, layer_meshes: Dict[str, Any]) -> Dict[str, Any]:
        layer_stats = self._count_by_layer(dxf_data)

        component_stats = {}
        total_components = 0
        if layer_meshes:
            component_stats, total_components = self._count_by_components(layer_meshes)

        return {
            "layer_stats": layer_stats,
            "component_stats": component_stats,
            "component_count": total_components,
            "total_layers": len(dxf_data.layers),
            "total_entities": sum(len(v) for v in dxf_data.entities.values()),
        }

    def _count_by_layer(self, dxf_data: DXFData) -> pd.DataFrame:
        rows = []
        for layer, entities in dxf_data.entities.items():
            type_counts = Counter(e.dxftype for e in entities)
            total = len(entities)
            row = {
                "图层": layer,
                "总数": total,
                "LINE": type_counts.get("LINE", 0),
                "CIRCLE": type_counts.get("CIRCLE", 0),
                "ARC": type_counts.get("ARC", 0),
                "LWPOLYLINE": type_counts.get("LWPOLYLINE", 0),
                "POLYLINE": type_counts.get("POLYLINE", 0),
                "SPLINE": type_counts.get("SPLINE", 0),
                "ELLIPSE": type_counts.get("ELLIPSE", 0),
                "TEXT/MTEXT": type_counts.get("TEXT", 0) + type_counts.get("MTEXT", 0),
                "INSERT": type_counts.get("INSERT", 0),
                "DIMENSION": type_counts.get("DIMENSION", 0),
                "闭合轮廓": sum(1 for e in entities if e.closed),
            }
            rows.append(row)
        return pd.DataFrame(rows)

    def _count_by_components(self, layer_meshes: Dict[str, Any]):
        """Connected component analysis on all meshes."""
        all_meshes = []
        mesh_labels = []

        for layer, mesh in layer_meshes.items():
            if mesh is None:
                continue
            if hasattr(mesh, 'split'):
                # multi-body mesh
                parts = mesh.split(only_watertight=False)
                for part in parts:
                    if part.vertices.shape[0] > 0:
                        all_meshes.append(part)
                        mesh_labels.append(layer)
            else:
                all_meshes.append(mesh)
                mesh_labels.append(layer)

        if not all_meshes:
            return pd.DataFrame(), 0

        # compute per-component stats
        rows = []
        for i, mesh in enumerate(all_meshes):
            verts = mesh.vertices
            if verts.shape[0] == 0:
                continue

            bbox_min = verts.min(axis=0)
            bbox_max = verts.max(axis=0)
            bbox_size = bbox_max - bbox_min
            volume = mesh.volume if hasattr(mesh, 'volume') else 0

            rows.append({
                "编号": i + 1,
                "所属图层": mesh_labels[i],
                "体积(mm³)": round(volume, 2),
                "顶点数": verts.shape[0],
                "长(mm)": round(bbox_size[0], 2),
                "宽(mm)": round(bbox_size[1], 2),
                "高(mm)": round(bbox_size[2], 2),
            })

        df = pd.DataFrame(rows)

        # group similar components
        if len(df) > 1:
            df = self._cluster_similar(df)

        return df, len(df)

    def _cluster_similar(self, df: pd.DataFrame) -> pd.DataFrame:
        """Simple clustering by volume/dimensions similarity."""
        if df.empty:
            return df

        # group by similar volume (within 5%)
        vols = df["体积(mm³)"].values
        groups = np.zeros(len(df), dtype=int)
        group_id = 1

        for i in range(len(df)):
            if groups[i] != 0:
                continue
            groups[i] = group_id
            for j in range(i + 1, len(df)):
                if groups[j] != 0:
                    continue
                if vols[i] > 0 and abs(vols[j] - vols[i]) / vols[i] < 0.05:
                    # check dimension similarity
                    d1 = df.iloc[i][["长(mm)", "宽(mm)", "高(mm)"]].values.astype(float)
                    d2 = df.iloc[j][["长(mm)", "宽(mm)", "高(mm)"]].values.astype(float)
                    if np.allclose(d1, d2, rtol=0.05):
                        groups[j] = group_id
            group_id += 1

        df["分类组"] = groups
        return df
