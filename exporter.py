import os
from typing import Dict, Any
import trimesh
import numpy as np
import pandas as pd


class Exporter:
    def export_3d(self, meshes: Dict[str, Any], filepath: str):
        """Export 3D meshes to STL/OBJ/GLB."""
        all_meshes = []
        for layer, mesh_dict in meshes.items():
            mesh = mesh_dict if not isinstance(mesh_dict, dict) else mesh_dict.get('mesh')
            if mesh is None:
                continue
            if isinstance(mesh, trimesh.Trimesh):
                # assign color per layer
                all_meshes.append(mesh)

        if not all_meshes:
            raise ValueError("没有可导出的模型")

        combined = trimesh.util.concatenate(all_meshes)

        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.stl':
            combined.export(filepath)
        elif ext == '.obj':
            combined.export(filepath)
        elif ext == '.glb':
            combined.export(filepath, file_type='glb')
        else:
            raise ValueError(f"不支持的格式: {ext}")

    def export_stats(self, data: Dict[str, Any], filepath: str):
        """Export statistics to Excel or CSV."""
        layer_df = data.get("layer_stats")
        component_df = data.get("component_stats")

        ext = os.path.splitext(filepath)[1].lower()

        if ext == '.csv':
            if layer_df is not None:
                path = filepath.replace('.csv', '_图层统计.csv')
                layer_df.to_csv(path, index=False, encoding='utf-8-sig')
            if component_df is not None:
                path = filepath.replace('.csv', '_零件统计.csv')
                component_df.to_csv(path, index=False, encoding='utf-8-sig')
        elif ext == '.xlsx':
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                if layer_df is not None:
                    layer_df.to_excel(writer, sheet_name='图层统计', index=False)
                if component_df is not None:
                    component_df.to_excel(writer, sheet_name='零件统计', index=False)
        else:
            raise ValueError(f"不支持的格式: {ext}")
