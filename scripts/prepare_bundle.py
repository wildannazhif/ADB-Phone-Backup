"""
Stages the standalone Windows runtime payload inside `src-tauri/resources/`
for Tauri production builds:
1. `resources/backend/src/`: Python backup engine (`adb_manager.py`, `target_resolver.py`, `ipc_worker.py`).
2. `resources/platform-tools/`: Bundled `adb.exe` + DLLs (`AdbWinApi.dll`, `AdbWinUsbApi.dll`, `libwinpthread-1.dll`).
3. `resources/python-runtime/`: Official Windows Embeddable Python runtime (optional/recommended for standalone installer).
"""

from __future__ import annotations

import argparse
import io
import shutil
import urllib.request
import zipfile
from pathlib import Path

EMBED_PYTHON_URL = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip"
PLATFORM_TOOLS_FILES = ["adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll", "libwinpthread-1.dll"]


def stage_backend(repo_root: Path, res_dir: Path) -> None:
    backend_src_dest = res_dir / "backend" / "src"
    if backend_src_dest.exists():
        shutil.rmtree(backend_src_dest)
    backend_src_dest.mkdir(parents=True, exist_ok=True)

    for fname in ["__init__.py", "adb_manager.py", "target_resolver.py", "ipc_worker.py"]:
        src_file = repo_root / "src" / fname
        shutil.copy2(src_file, backend_src_dest / fname)
    print(f"[bundle] Staged Python backend modules -> {backend_src_dest}")


def stage_platform_tools(res_dir: Path, custom_dir: Path | None) -> None:
    candidates = [
        custom_dir,
        Path("C:/platform-tools"),
        Path("C:/Android/platform-tools"),
    ]
    source_dir = next((c for c in candidates if c and c.exists() and (c / "adb.exe").exists()), None)
    if not source_dir:
        print("[bundle] Warning: platform-tools directory not found; skipping ADB staging.")
        return

    dest = res_dir / "platform-tools"
    dest.mkdir(parents=True, exist_ok=True)
    for fname in PLATFORM_TOOLS_FILES:
        fp = source_dir / fname
        if fp.exists():
            shutil.copy2(fp, dest / fname)
            print(f"[bundle] Staged ADB binary: {fname}")


def stage_embeddable_python(res_dir: Path, download: bool) -> None:
    runtime_dir = res_dir / "python-runtime"
    if (runtime_dir / "python.exe").exists():
        print(f"[bundle] Embedded Python already present at {runtime_dir}")
        return
    if not download:
        print("[bundle] Skipping Python runtime download (--no-python).")
        return

    print(f"[bundle] Downloading Windows Embeddable Python from {EMBED_PYTHON_URL}...")
    with urllib.request.urlopen(EMBED_PYTHON_URL, timeout=60) as resp:
        data = resp.read()

    runtime_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(runtime_dir)

    # Ensure `../backend` is discoverable via python312._pth
    for pth in runtime_dir.glob("*._pth"):
        content = pth.read_text(encoding="utf-8")
        if "../backend" not in content:
            pth.write_text(content + "\n../backend\nimport site\n", encoding="utf-8")

    print(f"[bundle] Staged Windows Embeddable Python -> {runtime_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-tools", type=Path, default=None)
    parser.add_argument("--no-python", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    res_dir = repo_root / "src-tauri" / "resources"
    res_dir.mkdir(parents=True, exist_ok=True)

    stage_backend(repo_root, res_dir)
    stage_platform_tools(res_dir, args.platform_tools)
    stage_embeddable_python(res_dir, download=not args.no_python)


if __name__ == "__main__":
    main()
