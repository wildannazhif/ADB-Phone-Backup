"""
ADB Manager for ADB Phone Backup Tool.
Robust Auto-Skip engine comparing exact relative paths and file sizes,
preserving .nomedia and all files on the phone without modification.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass
class DeviceInfo:
    serial: str
    status: str
    model: str = "Unknown"
    product: str = ""
    android_version: str = ""
    battery_level: Optional[int] = None
    storage_total: str = ""
    storage_free: str = ""

    @property
    def is_ready(self) -> bool:
        return self.status == "device"

    @property
    def display_name(self) -> str:
        name = self.model if self.model and self.model != "Unknown" else self.serial
        if not self.is_ready:
            return f"[{self.status.upper()}] {name} ({self.serial})"
        return f"{name} ({self.serial})"


class AdbManager:
    """High-level ADB interactions with exact relative path & size Auto-Skip."""

    def __init__(self, custom_adb_path: Optional[str] = None):
        self.custom_adb_path = custom_adb_path
        self._active_process: Optional[subprocess.Popen] = None
        self._is_cancelled: bool = False

    def find_adb(self) -> str:
        candidates = []
        if self.custom_adb_path and os.path.exists(self.custom_adb_path):
            return self.custom_adb_path

        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "adb.exe")

        exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        candidates.append(exe_dir / "adb.exe")
        candidates.append(exe_dir / "platform-tools" / "adb.exe")

        which_adb = shutil.which("adb")
        if which_adb:
            candidates.append(Path(which_adb))

        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            candidates.append(Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / "adb.exe")

        candidates.extend([
            Path("C:/platform-tools/adb.exe"),
            Path("C:/Android/platform-tools/adb.exe"),
            Path("C:/Program Files/Android/platform-tools/adb.exe"),
        ])

        for c in candidates:
            if c and c.exists():
                return str(c)

        raise FileNotFoundError("adb.exe tidak ditemukan di PATH atau folder standar.")

    def _run_cmd(
        self,
        args: list[str],
        timeout: int = 30,
        check_returncode: bool = True,
    ) -> subprocess.CompletedProcess:
        adb = self.find_adb()
        cmd = [adb] + args
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=creationflags,
        )
        if check_returncode and res.returncode != 0:
            raise RuntimeError(f"ADB Error ({res.returncode}): {res.stderr.strip() or res.stdout.strip()}")
        return res

    def get_adb_version(self) -> str:
        try:
            res = self._run_cmd(["version"], timeout=5)
            first_line = res.stdout.strip().splitlines()[0] if res.stdout else "ADB Available"
            return first_line
        except Exception as e:
            return f"Error: {e}"

    def list_devices(self) -> list[DeviceInfo]:
        try:
            res = self._run_cmd(["devices", "-l"], timeout=10)
        except Exception:
            return []

        devices = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue

            parts = line.split()
            if not parts:
                continue

            serial = parts[0]
            status = parts[1] if len(parts) > 1 else "unknown"

            model = "Android Device"
            product = ""

            for part in parts[2:]:
                if part.startswith("model:"):
                    model = part.split(":", 1)[1].replace("_", " ")
                elif part.startswith("product:"):
                    product = part.split(":", 1)[1]

            dev = DeviceInfo(serial=serial, status=status, model=model, product=product)

            if status == "device":
                self._enrich_device_info(dev)

            devices.append(dev)

        return devices

    def _enrich_device_info(self, dev: DeviceInfo) -> None:
        try:
            res = self._run_cmd(["-s", dev.serial, "shell", "getprop", "ro.build.version.release"], timeout=5, check_returncode=False)
            if res.returncode == 0 and res.stdout.strip():
                dev.android_version = f"Android {res.stdout.strip()}"

            df_res = self._run_cmd(["-s", dev.serial, "shell", "df -h /sdcard 2>/dev/null || df -h /storage/emulated/0"], timeout=5, check_returncode=False)
            if df_res.returncode == 0:
                lines = df_res.stdout.strip().splitlines()
                if len(lines) >= 2:
                    cols = lines[-1].split()
                    if len(cols) >= 4:
                        dev.storage_total = cols[1]
                        dev.storage_free = cols[3]

            bat_res = self._run_cmd(["-s", dev.serial, "shell", "dumpsys battery"], timeout=5, check_returncode=False)
            if bat_res.returncode == 0:
                match = re.search(r"level:\s*(\d+)", bat_res.stdout)
                if match:
                    dev.battery_level = int(match.group(1))
        except Exception:
            pass

    def list_remote_directory(self, serial: str, remote_path: str) -> tuple[list[str], list[dict]]:
        clean_path = remote_path.rstrip("/")
        if not clean_path:
            clean_path = "/"

        quoted = shlex.quote(clean_path)
        cmd = ["-s", serial, "shell", f"ls -1pa {quoted}"]
        res = self._run_cmd(cmd, timeout=15, check_returncode=False)

        dirs: list[str] = []
        files: list[dict] = []

        if res.returncode != 0:
            return dirs, files

        for line in res.stdout.splitlines():
            line = line.strip()
            if not line or line in (".", "..", "./", "../"):
                continue

            if line.endswith("/"):
                dirs.append(line[:-1])
            else:
                files.append({"name": line, "type": "file"})

        dirs.sort(key=str.lower)
        files.sort(key=lambda x: x["name"].lower())
        return dirs, files

    def resolve_whatsapp_targets(self, serial: str) -> list[tuple[str, str]]:
        """
        Locates WhatsApp media folders on the device specifically for:
        - WhatsApp Documents
        - WhatsApp Images
        - WhatsApp Video
        Ignores audio, voice notes, stickers, wallpapers, etc.
        Returns: list of (remote_path, subfolder_identifier)
        """
        base_candidates = [
            "/sdcard/Android/media/com.whatsapp/WhatsApp/Media",
            "/sdcard/WhatsApp/Media",
            "/sdcard/Android/media/com.whatsapp.w4b/WhatsApp Business/Media",
            "/sdcard/WhatsApp Business/Media",
        ]

        found_targets = []
        checked_subfolders = [
            ("WhatsApp Images", "WhatsApp Images"),
            ("WhatsApp Video", "WhatsApp Video"),
            ("WhatsApp Documents", "WhatsApp Documents"),
            ("WhatsApp Document", "WhatsApp Documents"),
        ]

        for base in base_candidates:
            check_base_cmd = ["-s", serial, "shell", f"[ -d '{base}' ] && echo 'FOUND' || echo ''"]
            try:
                res = self._run_cmd(check_base_cmd, timeout=5, check_returncode=False)
                if "FOUND" not in res.stdout:
                    continue
            except Exception:
                continue

            for sub_name, local_sub in checked_subfolders:
                remote_sub = f"{base}/{sub_name}"
                check_cmd = ["-s", serial, "shell", f"[ -d '{remote_sub}' ] && echo 'FOUND' || echo ''"]
                try:
                    res = self._run_cmd(check_cmd, timeout=5, check_returncode=False)
                    if "FOUND" in res.stdout:
                        if not any(t[1] == local_sub for t in found_targets):
                            found_targets.append((remote_sub, local_sub))
                except Exception:
                    pass

            if found_targets:
                break

        if not found_targets:
            def_base = "/sdcard/Android/media/com.whatsapp/WhatsApp/Media"
            found_targets = [
                (f"{def_base}/WhatsApp Images", "WhatsApp Images"),
                (f"{def_base}/WhatsApp Video", "WhatsApp Video"),
                (f"{def_base}/WhatsApp Documents", "WhatsApp Documents"),
            ]

        return found_targets

    def cancel_operation(self) -> None:
        self._is_cancelled = True
        proc = self._active_process
        if proc:
            try:
                proc.terminate()
                time.sleep(0.3)
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def scan_remote_files(
        self,
        serial: str,
        remote_dir: str,
        log_callback: Optional[Callable[[str, str], None]] = None,
    ) -> list[tuple[str, int]]:
        """
        Recursively queries files on the phone using find + stat.
        Returns: list of (relative_path, size_in_bytes)
        All files including .nomedia are included exactly as they exist on the phone.
        """
        clean_dir = remote_dir.rstrip("/")
        if log_callback:
            log_callback(f"Memindai file di HP: {clean_dir}...", "info")

        quoted = shlex.quote(clean_dir)
        # 1. Primary method: find with -printf '%s %p\n' (blazing fast, built-in, handles 20,000+ files without ARG_MAX)
        cmd_printf = ["-s", serial, "shell", f"find {quoted} -type f -printf '%s %p\\n' 2>/dev/null"]
        res = self._run_cmd(cmd_printf, timeout=120, check_returncode=False)
        files: list[tuple[str, int]] = []

        if res.returncode == 0 and res.stdout.strip():
            clean_prefix = clean_dir + "/"
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" ", 1)
                if len(parts) == 2 and parts[0].isdigit():
                    size = int(parts[0])
                    full_p = parts[1]
                    if full_p.startswith(clean_prefix):
                        rel_p = full_p[len(clean_prefix):]
                    elif full_p.startswith(clean_dir):
                        rel_p = full_p[len(clean_dir):].lstrip("/")
                    else:
                        rel_p = os.path.basename(full_p)
                    files.append((rel_p, size))
            if files:
                return files

        # 2. Secondary method: find with stat (for smaller directories)
        cmd_stat = ["-s", serial, "shell", f"find {quoted} -type f -exec stat -c '%s %n' {{}} + 2>/dev/null"]
        res_stat = self._run_cmd(cmd_stat, timeout=90, check_returncode=False)
        if res_stat.returncode == 0 and res_stat.stdout.strip():
            for line in res_stat.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" ", 1)
                if len(parts) == 2 and parts[0].isdigit():
                    size = int(parts[0])
                    full_p = parts[1]
                    if full_p.startswith(clean_dir):
                        rel_p = full_p[len(clean_dir):].lstrip("/")
                    else:
                        rel_p = os.path.basename(full_p)
                    files.append((rel_p, size))
            if files:
                return files

        # 3. Fallback method: bare find (if size queries fail)
        fallback_cmd = ["-s", serial, "shell", f"find {quoted} -type f 2>/dev/null"]
        res2 = self._run_cmd(fallback_cmd, timeout=90, check_returncode=False)
        if res2.returncode == 0:
            for line in res2.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith(clean_dir):
                    rel_p = line[len(clean_dir):].lstrip("/")
                else:
                    rel_p = os.path.basename(line)
                files.append((rel_p, 0))

        return files

    def smart_sync(
        self,
        serial: str,
        remote_dir: str,
        local_dest: str,
        preserve_timestamps: bool = True,
        log_callback: Optional[Callable[[str, str], None]] = None,
        progress_callback: Optional[Callable[[float, str, int, int], None]] = None,
        auto_skip: bool = True,
        telemetry_callback: Optional[Callable[[dict], None]] = None,
    ) -> tuple[int, int, int]:
        """
        Synchronizes remote_dir to local_dest.
        Accurately skips files that already exist at local_dest with the exact same
        relative path and file size (including 0-byte files like .nomedia).
        """
        self._is_cancelled = False
        clean_remote = remote_dir.rstrip("/")
        os.makedirs(local_dest, exist_ok=True)

        # 1. Scan remote files from phone
        remote_files = self.scan_remote_files(serial, clean_remote, log_callback=log_callback)
        total_files = len(remote_files)

        if self._is_cancelled:
            if log_callback:
                log_callback("Backup dibatalkan oleh pengguna.", "warning")
            return (0, 0, 0)

        if total_files == 0:
            if log_callback:
                log_callback(f"Tidak ada file di folder HP: {clean_remote}", "warning")
            return (0, 0, 0)

        # 2. Build local index of existing files in local_dest:
        # Map: relative_path_normalized_lower -> file_size
        local_index: dict[str, int] = {}
        if auto_skip and os.path.exists(local_dest):
            for root, _, filenames in os.walk(local_dest):
                for fn in filenames:
                    full_lp = os.path.join(root, fn)
                    try:
                        sz = os.path.getsize(full_lp)
                        rel = os.path.relpath(full_lp, local_dest).replace("\\", "/").strip("/").lower()
                        local_index[rel] = sz
                    except OSError:
                        pass

        # 3. Determine which files are already backed up vs need pulling
        need_pull: list[tuple[str, int]] = []
        skipped = 0

        for rel_path, remote_size in remote_files:
            rel_norm = rel_path.replace("\\", "/").strip("/").lower()

            # Exact relative path match & matching size (including 0-byte files like .nomedia)
            if auto_skip and rel_norm in local_index and local_index[rel_norm] == remote_size:
                skipped += 1
            else:
                need_pull.append((rel_path, remote_size))

        if skipped > 0 and log_callback:
            log_callback(f"⚡ AUTO-SKIP: {skipped:,} file sudah ada di tujuan (relative path & ukuran sama), dilewati otomatis!", "skip")
        elif not auto_skip and log_callback:
            log_callback("Smart Auto-Skip dinonaktifkan: semua file hasil scan akan disalin ulang.", "info")

        if not need_pull:
            if log_callback:
                log_callback(f"✅ Semua {total_files:,} file sudah lengkap di tujuan! (0 disalin, {skipped:,} dilewati).", "success")
            if progress_callback:
                progress_callback(100.0, f"Selesai! {skipped:,} file identik dilewati.", 0, skipped)
            if telemetry_callback:
                telemetry_callback({
                    "phase": "target_done",
                    "total_scanned": total_files,
                    "total_to_pull": 0,
                    "file_index": 0,
                    "current_file": "",
                    "current_file_rel": "",
                    "current_file_bytes": 0,
                    "transferred": 0,
                    "skipped": skipped,
                    "errors": 0,
                    "bytes_transferred": 0,
                    "bytes_total_to_pull": 0,
                    "pct": 100.0,
                })
            return (0, skipped, 0)

        # 4. Pull only the missing or modified files
        total_pull = len(need_pull)
        bytes_total_to_pull = sum(max(0, sz) for _, sz in need_pull)
        bytes_transferred = 0
        if log_callback:
            log_callback(f"📥 Menyalin {total_pull:,} file baru/berubah ke: {local_dest}", "info")

        transferred = 0
        errors = 0
        adb = self.find_adb()
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        for idx, (rel_path, remote_size) in enumerate(need_pull, start=1):
            if self._is_cancelled:
                if log_callback:
                    log_callback("Backup dibatalkan oleh pengguna.", "warning")
                break

            filename = os.path.basename(rel_path)
            local_file_path = os.path.join(local_dest, rel_path.replace("/", os.sep))
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            remote_full = f"{clean_remote}/{rel_path}"

            pct = (idx / total_pull) * 100.0
            if progress_callback:
                progress_callback(pct, f"[{idx}/{total_pull}] Menyalin: {filename}", transferred, skipped)
            if telemetry_callback:
                telemetry_callback({
                    "phase": "pulling",
                    "total_scanned": total_files,
                    "total_to_pull": total_pull,
                    "file_index": idx,
                    "current_file": filename,
                    "current_file_rel": rel_path,
                    "current_file_bytes": remote_size,
                    "transferred": transferred,
                    "skipped": skipped,
                    "errors": errors,
                    "bytes_transferred": bytes_transferred,
                    "bytes_total_to_pull": bytes_total_to_pull,
                    "pct": pct,
                })

            pull_args = [adb, "-s", serial, "pull"]
            if preserve_timestamps:
                pull_args.append("-a")
            pull_args.extend([remote_full, local_file_path])

            try:
                self._active_process = subprocess.Popen(
                    pull_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=creationflags,
                )
                _, stderr = self._active_process.communicate()
                ret = self._active_process.returncode
                self._active_process = None

                if ret == 0:
                    transferred += 1
                    local_index[rel_path.replace("\\", "/").strip("/").lower()] = remote_size
                    if remote_size > 0:
                        bytes_transferred += remote_size
                    elif os.path.exists(local_file_path):
                        try:
                            bytes_transferred += os.path.getsize(local_file_path)
                        except OSError:
                            pass
                    if log_callback and (transferred % 25 == 0 or transferred <= 5):
                        log_callback(f"✓ Disalin ({transferred}/{total_pull}): {filename}", "detail")
                else:
                    errors += 1
                    if log_callback:
                        log_callback(f"✗ Gagal ({filename}): {stderr.strip()}", "error")
            except Exception as e:
                errors += 1
                if log_callback:
                    log_callback(f"✗ Error ({filename}): {e}", "error")

        if progress_callback:
            progress_callback(100.0, f"Selesai! {transferred:,} disalin, {skipped:,} dilewati.", transferred, skipped)

        if telemetry_callback:
            telemetry_callback({
                "phase": "target_done",
                "total_scanned": total_files,
                "total_to_pull": total_pull,
                "file_index": total_pull,
                "current_file": "",
                "current_file_rel": "",
                "current_file_bytes": 0,
                "transferred": transferred,
                "skipped": skipped,
                "errors": errors,
                "bytes_transferred": bytes_transferred,
                "bytes_total_to_pull": bytes_total_to_pull,
                "pct": 100.0,
            })

        if log_callback:
            log_callback(
                f"Selesai: {transferred:,} file baru disalin, {skipped:,} file lama dilewati (Auto-skip), {errors} gagal.",
                "success" if errors == 0 else "warning",
            )

        return (transferred, skipped, errors)
