import os
import subprocess
import glob
import tempfile
import shutil


class DWGConverter:
    """Auto DWG→DXF conversion via ODA File Converter (if installed)."""

    ODA_PATHS = [
        "C:/Program Files/ODA/ODAFileConverter/ODAFileConverter.exe",
        "C:/Program Files (x86)/ODA/ODAFileConverter/ODAFileConverter.exe",
        "C:/Program Files/ODA/ODADrawingsExplorer/ODAFileConverter.exe",
        "C:/Program Files (x86)/ODA/ODADrawingsExplorer/ODAFileConverter.exe",
        "C:/Program Files/Teigha/TeighaFileConverter/TeighaFileConverter.exe",
        "C:/Program Files (x86)/Teigha/TeighaFileConverter/TeighaFileConverter.exe",
        os.path.expandvars("%LOCALAPPDATA%/ODA/ODAFileConverter/ODAFileConverter.exe"),
    ]

    DOWNLOAD_URL = "https://www.opendesign.com/guestfiles/oda_file_converter"

    def __init__(self):
        self._oda_path = None
        self._searched = False

    def find_oda_converter(self) -> str | None:
        if self._searched:
            return self._oda_path
        self._searched = True

        for path in self.ODA_PATHS:
            if os.path.isfile(path):
                self._oda_path = path
                return path

        for base in ["C:/Program Files", "C:/Program Files (x86)"]:
            pattern = f"{base}/ODA/**/ODAFileConverter.exe"
            matches = glob.glob(pattern, recursive=True)
            if matches:
                self._oda_path = matches[0]
                return self._oda_path

        return None

    def is_available(self) -> bool:
        return self.find_oda_converter() is not None

    def launch_oda(self) -> bool:
        oda = self.find_oda_converter()
        if not oda:
            return False
        try:
            subprocess.Popen([oda])
            return True
        except Exception:
            return False

    def auto_convert(self, dwg_path: str) -> str | None:
        """
        Attempt silent DWG→DXF conversion.
        Uses a temp dir to avoid cluttering the source folder.
        Returns path to DXF, or None if conversion fails.
        """
        oda = self.find_oda_converter()
        if not oda:
            return None

        input_dir = os.path.dirname(dwg_path)
        output_dir = tempfile.mkdtemp(prefix="cad_analyzer_dxf_")

        cmd = [
            oda,
            "/i", input_dir,
            "/o", output_dir,
            "/in_version", "2018",
            "/out_version", "2018",
            "/type", "1",  # DXF
        ]
        try:
            result = subprocess.run(cmd, timeout=120, capture_output=True)
            base = os.path.splitext(os.path.basename(dwg_path))[0]
            expected = os.path.join(output_dir, base + ".dxf")
            if os.path.isfile(expected):
                # Move to same dir as DWG for persistence
                dest = os.path.join(input_dir, base + ".dxf")
                shutil.copy2(expected, dest)
                shutil.rmtree(output_dir, ignore_errors=True)
                return dest

            # ODA converts ALL files in dir. Try to find ours.
            for f in os.listdir(output_dir):
                if f.lower().endswith('.dxf'):
                    src = os.path.join(output_dir, f)
                    dest = os.path.join(input_dir, f)
                    shutil.copy2(src, dest)
                    shutil.rmtree(output_dir, ignore_errors=True)
                    return dest

            shutil.rmtree(output_dir, ignore_errors=True)
        except Exception:
            shutil.rmtree(output_dir, ignore_errors=True)

        return None
