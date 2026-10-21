"""
Automated PyInstaller Build Script for ADB Phone Backup Tool.
Compiles the application into a standalone Windows .exe with bundled ADB binaries.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def build():
    project_root = Path(__file__).resolve().parent
    entry_script = project_root / "run.py"
    icon_ico = project_root / "assets" / "icon.ico"
    icon_png = project_root / "assets" / "icon.png"
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"

    print("=" * 60)
    print("Membangun ADB Phone Backup Tool Standalone .EXE...")
    print("=" * 60)

    # Check PyInstaller
    pyinstaller = shutil.which("pyinstaller")
    if not pyinstaller:
        print("Error: PyInstaller tidak ditemukan di PATH!")
        sys.exit(1)

    cmd = [
        pyinstaller,
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",  # No console window
        "--name", "ADB-Phone-Backup",
        "--paths", str(project_root),
        "--icon", str(icon_ico),
        "--add-data", f"{icon_ico};assets",
        "--add-data", f"{icon_png};assets",
        "--collect-submodules", "src",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "tkinter.filedialog",
        "--hidden-import", "tkinter.messagebox",
        "--hidden-import", "src",
        "--hidden-import", "src.gui",
        "--hidden-import", "src.adb_manager",
        "--hidden-import", "src.browser_dialog",
    ]

    # Include ADB binaries if available on Windows
    platform_tools = Path("C:/platform-tools")
    if platform_tools.exists():
        adb_files = ["adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll", "libwinpthread-1.dll"]
        for f in adb_files:
            fp = platform_tools / f
            if fp.exists():
                cmd.extend(["--add-binary", f"{fp};."])
                print(f"-> Menyertakan biner: {f}")

    cmd.append(str(entry_script))

    print("\nMenjalankan PyInstaller...")
    ret = subprocess.run(cmd, cwd=str(project_root))
    if ret.returncode != 0:
        print("\n[ERROR] PyInstaller gagal membuat .exe!")
        sys.exit(ret.returncode)

    output_exe = dist_dir / "ADB-Phone-Backup.exe"
    if output_exe.exists():
        size_mb = output_exe.stat().st_size / (1024 * 1024)
        print("=" * 60)
        print(f"BERHASIL! Executable siap di:")
        print(f"-> {output_exe}")
        print(f"-> Ukuran File: {size_mb:.2f} MB")
        print("=" * 60)
    else:
        print("[ERROR] File .exe tidak ditemukan di folder dist.")


if __name__ == "__main__":
    build()
