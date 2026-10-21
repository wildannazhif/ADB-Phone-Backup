"""
Root launcher for ADB Phone Backup Tool.
Properly handles sys.path for both development and PyInstaller frozen executables.
"""

import sys
import os

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    base_dir = getattr(sys, "_MEIPASS")
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from src.gui import launch_gui

if __name__ == "__main__":
    launch_gui()
