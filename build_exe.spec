# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CAD Analyzer."""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# collect VTK modules
vtk_hidden = collect_submodules('vtk')
vtk_datas = collect_data_files('vtk')

# collect PyVista
pv_datas = collect_data_files('pyvista')

# collect matplotlib
mpl_datas = collect_data_files('matplotlib', subdir='mpl-data')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        *vtk_datas,
        *pv_datas,
        *mpl_datas,
        ('style.qss', '.'),
        ('icon.ico', '.'),
    ],
    hiddenimports=[
        *vtk_hidden,
        'vtkmodules.all',
        'vtkmodules.util.vtkConstants',
        'vtkmodules.qt.QVTKRenderWindowInteractor',
        'pyvistaqt',
        'QtPy',
        'matplotlib.backends.backend_qtagg',
        'matplotlib.backends.backend_svg',
        'mpl_toolkits',
        'shapely',
        'shapely.geometry',
        'triangle',
        'trimesh',
        'ezdxf',
        'ezdxf.addons',
        'ezdxf.entities',
        'pandas',
        'openpyxl',
        'numpy.core._methods',
        'numpy.lib.format',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'IPython',
        'jupyter',
        'notebook',
        'sphinx',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CAD-Analyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
