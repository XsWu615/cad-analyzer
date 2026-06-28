import os
import subprocess
import glob


class DWGConverter:
    """Detects ODA File Converter and provides DWG→DXF conversion guidance."""

    ODA_PATHS = [
        # ODA File Converter common install locations
        "C:/Program Files/ODA/ODAFileConverter/ODAFileConverter.exe",
        "C:/Program Files (x86)/ODA/ODAFileConverter/ODAFileConverter.exe",
        # ODA Drawings Explorer (includes converter)
        "C:/Program Files/ODA/ODADrawingsExplorer/ODAFileConverter.exe",
        "C:/Program Files (x86)/ODA/ODADrawingsExplorer/ODAFileConverter.exe",
        # Teigha File Converter (older name)
        "C:/Program Files/Teigha/TeighaFileConverter/TeighaFileConverter.exe",
        "C:/Program Files (x86)/Teigha/TeighaFileConverter/TeighaFileConverter.exe",
        # User-local
        os.path.expandvars("%LOCALAPPDATA%/ODA/ODAFileConverter/ODAFileConverter.exe"),
    ]

    def find_oda_converter(self) -> str | None:
        """Find installed ODA File Converter. Returns path or None."""
        for path in self.ODA_PATHS:
            if os.path.isfile(path):
                return path

        # fuzzy search in Program Files
        for base in ["C:/Program Files", "C:/Program Files (x86)"]:
            pattern = f"{base}/ODA/**/ODAFileConverter.exe"
            matches = glob.glob(pattern, recursive=True)
            if matches:
                return matches[0]

        return None

    def launch_oda(self, oda_path: str) -> bool:
        """Launch ODA File Converter. Returns True if launched."""
        try:
            subprocess.Popen([oda_path])
            return True
        except Exception:
            return False

    def convert_dwg_to_dxf(self, dwg_path: str, oda_path: str, output_dir: str) -> str | None:
        """
        Attempt CLI conversion via ODAFileConverter.
        ODAFileConverter.exe /i <input_dir> /o <output_dir> /in_version <ver> /out_version <ver>
        Returns: path to converted DXF, or None.
        """
        input_dir = os.path.dirname(dwg_path)
        output_dir = output_dir or input_dir

        cmd = [
            oda_path,
            "/i", input_dir,
            "/o", output_dir,
            "/in_version", "2018",
            "/out_version", "2018",
            "/type", "1",  # 1 = DXF
        ]
        try:
            subprocess.run(cmd, timeout=60, capture_output=True)
            base = os.path.splitext(os.path.basename(dwg_path))[0]
            expected = os.path.join(output_dir, base + ".dxf")
            if os.path.isfile(expected):
                return expected
        except Exception:
            pass
        return None
