import os
import sys
import subprocess
import tempfile
import shutil


class DWGConverter:
    """Local DWG→DXF via bundled WASM (LibreDWG). ODA as fallback."""

    ODA_PATHS = [
        "C:/Program Files/ODA/ODAFileConverter/ODAFileConverter.exe",
        "C:/Program Files (x86)/ODA/ODAFileConverter/ODAFileConverter.exe",
        "C:/Program Files/ODA/ODADrawingsExplorer/ODAFileConverter.exe",
        "C:/Program Files (x86)/ODA/ODADrawingsExplorer/ODAFileConverter.exe",
        os.path.expandvars("%LOCALAPPDATA%/ODA/ODAFileConverter/ODAFileConverter.exe"),
    ]

    DOWNLOAD_URL = "https://www.opendesign.com/guestfiles/oda_file_converter"

    def __init__(self):
        self._node_path = None
        self._checked_node = False

    def _find_node(self) -> str | None:
        if self._checked_node:
            return self._node_path
        self._checked_node = True

        # check common locations
        candidates = [
            "node",
            os.path.expandvars("%ProgramFiles%/nodejs/node.exe"),
            os.path.expandvars("%ProgramFiles(x86)%/nodejs/node.exe"),
            os.path.expandvars("%LOCALAPPDATA%/nodejs/node.exe"),
        ]
        for c in candidates:
            try:
                r = subprocess.run([c, '--version'], capture_output=True, timeout=5)
                if r.returncode == 0:
                    self._node_path = c
                    return c
            except Exception:
                continue
        return None

    def _wasm_dir(self):
        """Path to WASM files, works both in dev and PyInstaller bundle."""
        if getattr(sys, 'frozen', False):
            return sys._MEIPASS
        return os.path.dirname(os.path.abspath(__file__))

    def auto_convert(self, dwg_path: str) -> str | None:
        """Convert DWG→DXF using bundled WASM. Returns DXF path or None."""
        # Method 1: Bundled WASM via Node.js
        node = self._find_node()
        if node:
            result, error = self._convert_wasm(dwg_path, node)
            if result:
                return result
            if error:
                self._last_error = error
                return None

        # Method 2: ODA File Converter (if installed)
        oda = self._find_oda()
        if oda:
            result = self._convert_oda(dwg_path, oda)
            if result:
                return result

        return None

    @property
    def last_error(self) -> str:
        return getattr(self, '_last_error', '未知错误')

    def get_status(self) -> str:
        """Human-readable status of conversion capabilities."""
        node = self._find_node()
        oda = self._find_oda()

        if node:
            return "wasm"  # best: works without anything
        if oda:
            return "oda"   # good: ODA installed
        return "none"      # need user action

    def is_available(self) -> bool:
        return self.get_status() != "none"

    # --- internal ---

    def _convert_wasm(self, dwg_path: str, node_exe: str):
        """Returns (dxf_path, None) on success, (None, error_msg) on failure."""
        wasm_dir = self._wasm_dir()
        cli_js = os.path.join(wasm_dir, 'dwg2dxf_cli.mjs')
        wasm_file = os.path.join(wasm_dir, 'wasm_bundle', 'libredwg-web.wasm')
        js_file = os.path.join(wasm_dir, 'wasm_bundle', 'libredwg-web.js')

        missing = [f for f in [cli_js, wasm_file, js_file] if not os.path.isfile(f)]
        if missing:
            return None, f"缺少文件: {missing}"

        output_dir = tempfile.mkdtemp(prefix="cad_dwg_")
        base = os.path.splitext(os.path.basename(dwg_path))[0]
        output_path = os.path.join(output_dir, base + '.dxf')

        try:
            env = os.environ.copy()
            env['NODE_PATH'] = wasm_dir
            result = subprocess.run(
                [node_exe, cli_js, dwg_path, output_path],
                capture_output=True, timeout=120,
                cwd=wasm_dir, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            )
            if result.returncode != 0:
                err = ""
                if result.stderr:
                    err = result.stderr.decode('utf-8', errors='replace').strip()
                if not err and result.stdout:
                    err = result.stdout.decode('utf-8', errors='replace').strip()
                return None, f"Node.js返回码{result.returncode}: {err[:200]}"
            if not os.path.isfile(output_path):
                return None, f"输出文件未生成: {output_path}"
            return output_path, None
        except subprocess.TimeoutExpired:
            return None, "转换超时(120秒)"
        except FileNotFoundError:
            return None, f"找不到Node.js: {node_exe}"
        except Exception as e:
            return None, f"异常: {type(e).__name__}: {e}"

    def _find_oda(self) -> str | None:
        for path in self.ODA_PATHS:
            if os.path.isfile(path):
                return path
        return None

    def _convert_oda(self, dwg_path: str, oda_exe: str) -> str | None:
        input_dir = os.path.dirname(dwg_path)
        output_dir = tempfile.mkdtemp(prefix="cad_oda_")

        cmd = [oda_exe, "/i", input_dir, "/o", output_dir,
               "/in_version", "2018", "/out_version", "2018", "/type", "1"]
        try:
            subprocess.run(cmd, timeout=120, capture_output=True)
            base = os.path.splitext(os.path.basename(dwg_path))[0]
            expected = os.path.join(output_dir, base + ".dxf")
            if os.path.isfile(expected):
                dest = os.path.join(input_dir, base + ".dxf")
                shutil.copy2(expected, dest)
                shutil.rmtree(output_dir, ignore_errors=True)
                return dest
            shutil.rmtree(output_dir, ignore_errors=True)
        except Exception:
            shutil.rmtree(output_dir, ignore_errors=True)
        return None

    def launch_oda(self) -> bool:
        oda = self._find_oda()
        if not oda:
            return False
        try:
            subprocess.Popen([oda])
            return True
        except Exception:
            return False
