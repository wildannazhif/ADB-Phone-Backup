"""
Structured NDJSON stdin/stdout IPC worker wrapping the existing AdbManager engine.
Managed by the Rust/Tauri host process.

Protocol invariants:
- Real stdout is strictly reserved for one-JSON-object-per-line protocol frames.
- sys.stdout is redirected to sys.stderr so stray prints/warnings never corrupt IPC.
- Device status updates use event-driven `adb track-devices` instead of tight polling.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from typing import Any, Optional

# Ensure repo/bundle root is importable when invoked as `python src/ipc_worker.py`
if __package__ is None or __package__ == "":
    _pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _pkg_parent not in sys.path:
        sys.path.insert(0, _pkg_parent)

from src.adb_manager import AdbManager, DeviceInfo
from src.target_resolver import build_active_targets, compute_backup_root_dest

# Protect stdout exclusively for JSON IPC frames
_REAL_STDOUT = sys.stdout
sys.stdout = sys.stderr

_LS_LONG_RE = re.compile(
    r"^([dlcbps-])[-a-zA-Z0-9@.+?]{9,12}\s+\d+\s+\S+\s+\S+\s+(\d+(?:,\s*\d+)?)\s+"
    r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?|[A-Za-z]{3}\s+\d+\s+(?:\d{2}:\d{2}|\d{4}))\s+(.+)$"
)


def _device_to_dict(dev: DeviceInfo) -> dict[str, Any]:
    data = asdict(dev)
    data["is_ready"] = dev.is_ready
    data["display_name"] = dev.display_name
    return data


def _parse_ls_long_entries(stdout_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    """
    Parses `ls -lpa` output into structured directory and file records with sizes.
    Returns (dirs, files, matched_any_long_format).
    """
    dirs: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    matched_long = False

    for raw_line in stdout_text.splitlines():
        line = raw_line.rstrip("\r\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("total "):
            continue

        m = _LS_LONG_RE.match(stripped)
        if not m:
            continue

        matched_long = True
        mode_char, size_str, modified, raw_name = m.groups()
        name = raw_name
        link_target: Optional[str] = None
        is_symlink = mode_char == "l"

        if is_symlink and " -> " in raw_name:
            name, link_target = raw_name.split(" -> ", 1)

        is_dir = mode_char == "d" or name.endswith("/")
        if name.endswith("/"):
            name = name[:-1]

        if not name or name in (".", ".."):
            continue

        try:
            size_bytes = int(size_str.replace(",", "").strip()) if not is_dir else 0
        except ValueError:
            size_bytes = 0

        item = {
            "name": name,
            "type": "dir" if is_dir else ("symlink" if is_symlink else "file"),
            "size": size_bytes,
            "modified": modified,
            "is_symlink": is_symlink,
            "link_target": link_target,
        }
        if is_dir:
            dirs.append(item)
        else:
            files.append(item)

    dirs.sort(key=lambda x: x["name"].lower())
    files.sort(key=lambda x: x["name"].lower())
    return dirs, files, matched_long


class IpcWorker:
    def __init__(self) -> None:
        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._job_lock = threading.Lock()

        self.adb = AdbManager()
        self._active_job_id: Optional[str] = None
        self._active_job_kind: Optional[str] = None
        self._stop_event = threading.Event()

        self._track_proc: Optional[subprocess.Popen] = None
        self._track_restart_event = threading.Event()
        self._tracker_thread: Optional[threading.Thread] = None

    # ==================== IPC IO ====================

    def _emit(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False)
        with self._write_lock:
            _REAL_STDOUT.write(line + "\n")
            _REAL_STDOUT.flush()

    def emit_event(self, event: str, payload: dict[str, Any]) -> None:
        self._emit({"type": "event", "event": event, "payload": payload})

    def emit_response(self, req_id: str, ok: bool, result: Any = None, error_code: str = "", error_msg: str = "") -> None:
        msg: dict[str, Any] = {"type": "response", "id": req_id, "ok": ok}
        if ok:
            msg["result"] = result
        else:
            msg["error"] = {"code": error_code or "INTERNAL_ERROR", "message": error_msg or "Unknown error"}
        self._emit(msg)

    # ==================== ADB HELPERS ====================

    def get_adb_status_payload(self) -> dict[str, Any]:
        try:
            adb_path = self.adb.find_adb()
            adb_version = self.adb.get_adb_version()
            return {
                "adb_available": True,
                "adb_path": adb_path,
                "adb_version": adb_version,
                "custom_adb_path": self.adb.custom_adb_path or "",
                "error": None,
            }
        except FileNotFoundError as exc:
            return {
                "adb_available": False,
                "adb_path": None,
                "adb_version": None,
                "custom_adb_path": self.adb.custom_adb_path or "",
                "error": str(exc),
            }
        except Exception as exc:
            return {
                "adb_available": False,
                "adb_path": None,
                "adb_version": None,
                "custom_adb_path": self.adb.custom_adb_path or "",
                "error": str(exc),
            }

    def fetch_devices_payload(self) -> dict[str, Any]:
        status = self.get_adb_status_payload()
        if not status["adb_available"]:
            return {**status, "devices": []}

        devices = [_device_to_dict(d) for d in self.adb.list_devices()]
        return {**status, "devices": devices}

    # ==================== EVENT-DRIVEN DEVICE TRACKER ====================

    def start_device_tracker(self) -> None:
        if self._tracker_thread and self._tracker_thread.is_alive():
            return
        self._tracker_thread = threading.Thread(target=self._device_tracker_loop, daemon=True)
        self._tracker_thread.start()

    def _kill_tracker_process(self) -> None:
        proc = self._track_proc
        self._track_proc = None
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=0.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _device_tracker_loop(self) -> None:
        last_snapshot: Optional[str] = None

        while not self._stop_event.is_set():
            self._track_restart_event.clear()
            try:
                adb_exe = self.adb.find_adb()
            except FileNotFoundError as exc:
                snap = json.dumps({"adb_available": False, "error": str(exc)})
                if snap != last_snapshot:
                    last_snapshot = snap
                    self.emit_event("device_status", {
                        "adb_available": False,
                        "adb_path": None,
                        "adb_version": None,
                        "custom_adb_path": self.adb.custom_adb_path or "",
                        "devices": [],
                        "error": str(exc),
                    })
                # Wait until settings change or shutdown (checked every 5s max, no tight polling)
                self._track_restart_event.wait(timeout=5.0)
                continue

            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            try:
                proc = subprocess.Popen(
                    [adb_exe, "track-devices"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=creationflags,
                )
                self._track_proc = proc

                while not self._stop_event.is_set() and not self._track_restart_event.is_set():
                    if proc.stdout is None:
                        break
                    len_bytes = proc.stdout.read(4)
                    if len(len_bytes) < 4:
                        break
                    try:
                        payload_len = int(len_bytes.decode("ascii"), 16)
                    except ValueError:
                        break
                    if payload_len > 0:
                        _ = proc.stdout.read(payload_len)

                    payload = self.fetch_devices_payload()
                    snap = json.dumps(payload, sort_keys=True)
                    if snap != last_snapshot:
                        last_snapshot = snap
                        self.emit_event("device_status", payload)

                self._kill_tracker_process()
            except Exception as exc:
                self._kill_tracker_process()
                payload = {
                    "adb_available": False,
                    "adb_path": None,
                    "adb_version": None,
                    "custom_adb_path": self.adb.custom_adb_path or "",
                    "devices": [],
                    "error": str(exc),
                }
                snap = json.dumps(payload, sort_keys=True)
                if snap != last_snapshot:
                    last_snapshot = snap
                    self.emit_event("device_status", payload)

            if not self._stop_event.is_set() and not self._track_restart_event.is_set():
                self._track_restart_event.wait(timeout=3.0)

    # ==================== DIRECTORY BROWSING ====================

    def browse_directory(
        self,
        serial: str,
        path: str,
        offset: int = 0,
        limit: int = 200,
        query: str = "",
    ) -> dict[str, Any]:
        clean_path = (path or "/sdcard").strip()
        if clean_path != "/":
            clean_path = clean_path.rstrip("/") or "/"

        target_for_ls = "/" if clean_path == "/" else f"{clean_path}/"
        quoted = shlex.quote(target_for_ls)

        try:
            res = self.adb._run_cmd(
                ["-s", serial, "shell", f"ls -lpa {quoted} 2>&1"],
                timeout=15,
                check_returncode=False,
            )
        except FileNotFoundError as exc:
            return {
                "path": clean_path,
                "accessible": False,
                "error": str(exc),
                "entries": [],
                "total_dirs": 0,
                "total_files": 0,
                "total_count": 0,
                "offset": offset,
                "limit": limit,
                "has_more": False,
            }

        out_text = res.stdout or ""
        err_text = res.stderr or ""
        combined = f"{out_text}\n{err_text}".strip()

        dirs, files, matched_long = _parse_ls_long_entries(out_text)

        if not matched_long:
            lowered = combined.lower()
            if (
                "permission denied" in lowered
                or "no such file" in lowered
                or "not a directory" in lowered
                or "cannot access" in lowered
                or "opendir failed" in lowered
            ):
                return {
                    "path": clean_path,
                    "accessible": False,
                    "error": combined.splitlines()[0] if combined else "Direktori tidak dapat diakses.",
                    "entries": [],
                    "total_dirs": 0,
                    "total_files": 0,
                    "total_count": 0,
                    "offset": offset,
                    "limit": limit,
                    "has_more": False,
                }

            # Fallback to original AdbManager.list_remote_directory if `ls -lpa` format differed
            fb_dirs, fb_files = self.adb.list_remote_directory(serial, clean_path)
            if res.returncode != 0 and not fb_dirs and not fb_files:
                return {
                    "path": clean_path,
                    "accessible": False,
                    "error": combined.splitlines()[0] if combined else f"Gagal membuka direktori (exit {res.returncode})",
                    "entries": [],
                    "total_dirs": 0,
                    "total_files": 0,
                    "total_count": 0,
                    "offset": offset,
                    "limit": limit,
                    "has_more": False,
                }
            dirs = [{"name": d, "type": "dir", "size": 0, "modified": "", "is_symlink": False, "link_target": None} for d in fb_dirs]
            files = [{"name": f["name"], "type": "file", "size": None, "modified": "", "is_symlink": False, "link_target": None} for f in fb_files]

        q_lower = query.strip().lower()
        if q_lower:
            dirs = [d for d in dirs if q_lower in d["name"].lower()]
            files = [f for f in files if q_lower in f["name"].lower()]

        all_entries = []
        for item in dirs + files:
            child_path = f"/{item['name']}" if clean_path == "/" else f"{clean_path}/{item['name']}"
            all_entries.append({**item, "path": child_path})

        safe_offset = max(0, int(offset))
        safe_limit = max(1, min(1000, int(limit)))
        sliced = all_entries[safe_offset : safe_offset + safe_limit]

        return {
            "path": clean_path,
            "accessible": True,
            "error": None,
            "entries": sliced,
            "total_dirs": len(dirs),
            "total_files": len(files),
            "total_count": len(all_entries),
            "offset": safe_offset,
            "limit": safe_limit,
            "has_more": (safe_offset + safe_limit) < len(all_entries),
        }

    # ==================== DESTINATION & STORAGE ====================

    def inspect_destination(self, path: str) -> dict[str, Any]:
        clean = os.path.normpath(path.strip()) if path and path.strip() else ""
        if not clean:
            return {"valid": False, "exists": False, "error": "Folder tujuan belum dipilih."}

        probe = clean
        while probe and not os.path.exists(probe):
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent

        if not probe or not os.path.exists(probe):
            return {"valid": False, "exists": False, "path": clean, "error": "Drive atau path tujuan tidak ditemukan."}

        try:
            usage = shutil.disk_usage(probe)
            drive = os.path.splitdrive(clean)[0] or probe
            used = usage.total - usage.free
            used_pct = (used / usage.total) * 100.0 if usage.total > 0 else 0.0
            return {
                "valid": True,
                "exists": os.path.exists(clean),
                "path": clean,
                "drive": drive,
                "total_bytes": usage.total,
                "free_bytes": usage.free,
                "used_bytes": used,
                "used_percent": round(used_pct, 1),
                "error": None,
            }
        except OSError as exc:
            return {"valid": False, "exists": os.path.exists(clean), "path": clean, "error": str(exc)}

    # ==================== PRE-SCAN & BACKUP EXECUTION ====================

    def _run_prescan(self, params: dict[str, Any]) -> None:
        job_id = params.get("job_id") or f"scan-{int(time.time())}"
        serial = params["serial"]
        dest_dir = params["dest_dir"]
        auto_subfolder = bool(params.get("auto_subfolder", False))
        device_model = params.get("device_model", "Android Device")
        t_cfg = params.get("targets") or {}

        try:
            root_dest = compute_backup_root_dest(dest_dir, auto_subfolder, device_model)
            targets = build_active_targets(
                self.adb,
                root_dest,
                serial,
                include_dcim=bool(t_cfg.get("dcim", True)),
                include_documents=bool(t_cfg.get("documents", True)),
                include_pictures=bool(t_cfg.get("pictures", True)),
                include_whatsapp=bool(t_cfg.get("whatsapp", True)),
                custom_enabled=bool(t_cfg.get("custom_enabled", False)),
                custom_path=str(t_cfg.get("custom_path", "")),
                custom_paths=t_cfg.get("custom_paths"),
            )

            report = []
            total_on_phone = 0
            total_already_on_disk = 0
            total_new = 0
            total_new_bytes = 0

            for idx, target in enumerate(targets, start=1):
                if self.adb.is_cancelled():
                    break
                self.emit_event("prescan_progress", {
                    "job_id": job_id,
                    "target_index": idx,
                    "total_targets": len(targets),
                    "target_label": target.label,
                    "remote_path": target.remote_path,
                })

                phone_files = self.adb.scan_remote_files(
                    serial,
                    target.remote_path,
                    log_callback=lambda m, lvl: self.emit_event("backup_log", {
                        "job_id": job_id,
                        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                        "level": lvl,
                        "message": m,
                    }),
                )
                p_count = len(phone_files)
                total_on_phone += p_count

                local_index: dict[str, int] = {}
                if os.path.exists(target.local_path):
                    for r, _, fns in os.walk(target.local_path):
                        for fn in fns:
                            fp = os.path.join(r, fn)
                            try:
                                sz = os.path.getsize(fp)
                                rel = os.path.relpath(fp, target.local_path).replace("\\", "/").strip("/").lower()
                                local_index[rel] = sz
                            except OSError:
                                pass

                skipped = 0
                new_bytes = 0
                for rel_p, rem_sz in phone_files:
                    rel_norm = rel_p.replace("\\", "/").strip("/").lower()
                    if rel_norm in local_index and local_index[rel_norm] == rem_sz:
                        skipped += 1
                    else:
                        new_bytes += max(0, rem_sz)

                new_count = p_count - skipped
                total_already_on_disk += skipped
                total_new += new_count
                total_new_bytes += new_bytes

                report.append({
                    "label": target.label,
                    "remote_path": target.remote_path,
                    "local_path": target.local_path,
                    "on_phone": p_count,
                    "already_on_disk": skipped,
                    "new_files": new_count,
                    "new_bytes": new_bytes,
                })

            self.emit_event("prescan_completed", {
                "job_id": job_id,
                "cancelled": self.adb.is_cancelled(),
                "root_dest": root_dest,
                "targets": report,
                "total_on_phone": total_on_phone,
                "total_already_on_disk": total_already_on_disk,
                "total_new": total_new,
                "total_new_bytes": total_new_bytes,
                "error": None,
            })
        except Exception as exc:
            self.emit_event("prescan_completed", {
                "job_id": job_id,
                "cancelled": self.adb.is_cancelled(),
                "root_dest": dest_dir,
                "targets": [],
                "total_on_phone": 0,
                "total_already_on_disk": 0,
                "total_new": 0,
                "total_new_bytes": 0,
                "error": str(exc),
            })
        finally:
            with self._job_lock:
                if self._active_job_id == job_id:
                    self._active_job_id = None
                    self._active_job_kind = None

    def _run_backup(self, params: dict[str, Any]) -> None:
        job_id = params.get("job_id") or f"backup-{int(time.time())}"
        serial = params["serial"]
        dest_dir = params["dest_dir"]
        auto_subfolder = bool(params.get("auto_subfolder", False))
        preserve_timestamps = bool(params.get("preserve_timestamps", True))
        smart_auto_skip = bool(params.get("smart_auto_skip", True))
        device_model = params.get("device_model", "Android Device")
        t_cfg = params.get("targets") or {}

        start_time = time.time()
        transfer_start_time: Optional[float] = None
        total_transferred = 0
        total_skipped = 0
        total_errors = 0
        total_bytes_transferred = 0
        targets_summary: list[dict[str, Any]] = []
        root_dest = dest_dir

        def emit_log(message: str, level: str = "info") -> None:
            self.emit_event("backup_log", {
                "job_id": job_id,
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                "level": level,
                "message": message,
            })

        try:
            self.adb._is_cancelled = False
            root_dest = compute_backup_root_dest(dest_dir, auto_subfolder, device_model)
            os.makedirs(root_dest, exist_ok=True)

            targets = build_active_targets(
                self.adb,
                root_dest,
                serial,
                include_dcim=bool(t_cfg.get("dcim", True)),
                include_documents=bool(t_cfg.get("documents", True)),
                include_pictures=bool(t_cfg.get("pictures", True)),
                include_whatsapp=bool(t_cfg.get("whatsapp", True)),
                custom_enabled=bool(t_cfg.get("custom_enabled", False)),
                custom_path=str(t_cfg.get("custom_path", "")),
                custom_paths=t_cfg.get("custom_paths"),
            )

            if not targets:
                raise ValueError("Tidak ada folder target backup yang dipilih.")

            total_targets = len(targets)
            emit_log(f"Memulai backup ke: {root_dest}", "info")
            if smart_auto_skip:
                emit_log("Smart Auto-Skip aktif: relative path & ukuran file dicocokkan persis.", "skip")
            else:
                emit_log("Smart Auto-Skip dimatikan: seluruh file hasil scan akan disalin.", "warning")

            for idx, target in enumerate(targets, start=1):
                if self.adb.is_cancelled():
                    break

                os.makedirs(target.local_path, exist_ok=True)
                emit_log(f"[{idx}/{total_targets}] Memeriksa: {target.remote_path} -> {target.local_path}", "info")

                self.emit_event("backup_progress", {
                    "job_id": job_id,
                    "phase": "scanning",
                    "target_index": idx,
                    "total_targets": total_targets,
                    "target_label": target.label,
                    "overall_percent": round(((idx - 1) / total_targets) * 100.0, 2),
                    "target_percent": 0.0,
                    "current_file": "",
                    "current_file_rel": "",
                    "files_completed": total_transferred,
                    "files_skipped": total_skipped,
                    "files_failed": total_errors,
                    "files_total_to_pull": 0,
                    "files_scanned": 0,
                    "bytes_transferred": total_bytes_transferred,
                    "bytes_total_to_pull": 0,
                    "speed_bps": None,
                    "eta_seconds": None,
                    "elapsed_seconds": int(time.time() - start_time),
                })

                target_bytes_done = 0

                def _telemetry_cb(t: dict[str, Any]) -> None:
                    nonlocal transfer_start_time, target_bytes_done
                    target_bytes_done = int(t.get("bytes_transferred", 0) or 0)
                    phase = t.get("phase", "transferring")
                    if phase == "pulling" and transfer_start_time is None:
                        transfer_start_time = time.time()

                    now = time.time()
                    elapsed_total = int(now - start_time)
                    cum_bytes = total_bytes_transferred + target_bytes_done
                    bytes_total_target = int(t.get("bytes_total_to_pull", 0) or 0)

                    speed_bps: Optional[float] = None
                    eta_seconds: Optional[float] = None
                    if transfer_start_time is not None:
                        pull_elapsed = now - transfer_start_time
                        if pull_elapsed >= 0.5 and cum_bytes > 0:
                            speed_bps = cum_bytes / pull_elapsed
                            remaining_in_target = max(0, bytes_total_target - target_bytes_done)
                            if bytes_total_target > 0 and speed_bps > 0:
                                eta_seconds = remaining_in_target / speed_bps

                    target_pct = float(t.get("pct", 0.0) or 0.0)
                    overall_pct = ((idx - 1) + (target_pct / 100.0)) / total_targets * 100.0

                    self.emit_event("backup_progress", {
                        "job_id": job_id,
                        "phase": "transferring" if phase == "pulling" else phase,
                        "target_index": idx,
                        "total_targets": total_targets,
                        "target_label": target.label,
                        "overall_percent": round(overall_pct, 2),
                        "target_percent": round(target_pct, 2),
                        "current_file": t.get("current_file", ""),
                        "current_file_rel": t.get("current_file_rel", ""),
                        "files_completed": total_transferred + int(t.get("transferred", 0) or 0),
                        "files_skipped": total_skipped + int(t.get("skipped", 0) or 0),
                        "files_failed": total_errors + int(t.get("errors", 0) or 0),
                        "files_total_to_pull": int(t.get("total_to_pull", 0) or 0),
                        "files_scanned": int(t.get("total_scanned", 0) or 0),
                        "bytes_transferred": cum_bytes,
                        "bytes_total_to_pull": bytes_total_target,
                        "speed_bps": round(speed_bps, 1) if speed_bps is not None else None,
                        "eta_seconds": round(eta_seconds, 1) if eta_seconds is not None else None,
                        "elapsed_seconds": elapsed_total,
                    })

                try:
                    transferred, skipped, errors = self.adb.smart_sync(
                        serial=serial,
                        remote_dir=target.remote_path,
                        local_dest=target.local_path,
                        preserve_timestamps=preserve_timestamps,
                        log_callback=emit_log,
                        auto_skip=smart_auto_skip,
                        telemetry_callback=_telemetry_cb,
                    )
                    total_transferred += transferred
                    total_skipped += skipped
                    total_errors += errors
                    total_bytes_transferred += target_bytes_done
                    targets_summary.append({
                        "label": target.label,
                        "remote_path": target.remote_path,
                        "local_path": target.local_path,
                        "transferred": transferred,
                        "skipped": skipped,
                        "errors": errors,
                    })
                except Exception as exc:
                    total_errors += 1
                    emit_log(f"Error memproses {target.remote_path}: {exc}", "error")
                    targets_summary.append({
                        "label": target.label,
                        "remote_path": target.remote_path,
                        "local_path": target.local_path,
                        "transferred": 0,
                        "skipped": 0,
                        "errors": 1,
                        "error": str(exc),
                    })

            duration_secs = int(time.time() - start_time)
            was_cancelled = self.adb.is_cancelled()
            if was_cancelled:
                status = "cancelled"
                emit_log("Operasi backup dibatalkan oleh pengguna.", "warning")
            elif total_errors > 0:
                status = "completed_with_errors"
                emit_log(
                    f"Backup selesai dengan {total_errors} kegagalan ({total_transferred:,} disalin, {total_skipped:,} dilewati).",
                    "warning",
                )
            else:
                status = "completed"
                emit_log(
                    f"BACKUP SELESAI dalam {duration_secs} detik! ({total_transferred:,} disalin, {total_skipped:,} dilewati).",
                    "success",
                )

            self.emit_event("backup_completed", {
                "job_id": job_id,
                "status": status,
                "serial": serial,
                "device_model": device_model,
                "dest_dir": root_dest,
                "files_transferred": total_transferred,
                "files_skipped": total_skipped,
                "files_failed": total_errors,
                "bytes_transferred": total_bytes_transferred,
                "duration_seconds": duration_secs,
                "targets_summary": targets_summary,
                "error": None,
            })
        except Exception as exc:
            duration_secs = int(time.time() - start_time)
            emit_log(f"Backup gagal: {exc}", "error")
            self.emit_event("backup_completed", {
                "job_id": job_id,
                "status": "failed",
                "serial": serial,
                "device_model": device_model,
                "dest_dir": root_dest,
                "files_transferred": total_transferred,
                "files_skipped": total_skipped,
                "files_failed": total_errors + 1,
                "bytes_transferred": total_bytes_transferred,
                "duration_seconds": duration_secs,
                "targets_summary": targets_summary,
                "error": str(exc),
            })
        finally:
            with self._job_lock:
                if self._active_job_id == job_id:
                    self._active_job_id = None
                    self._active_job_kind = None

    # ==================== COMMAND DISPATCH ====================

    def handle_request(self, req: dict[str, Any]) -> None:
        req_id = str(req.get("id", ""))
        method = str(req.get("method", ""))
        params = req.get("params") or {}

        if method == "ping":
            self.emit_response(req_id, True, {"pong": True, "pid": os.getpid()})
            return

        if method == "shutdown":
            self._stop_event.set()
            self.adb.cancel_operation()
            self._kill_tracker_process()
            self._track_restart_event.set()
            self.emit_response(req_id, True, {"shutting_down": True})
            return

        if method == "cancel_backup":
            with self._job_lock:
                active_id = self._active_job_id
            self.adb.cancel_operation()
            self.emit_response(req_id, True, {"cancelled": True, "active_job_id": active_id})
            return

        if method == "set_adb_path":
            custom_path = (params.get("custom_adb_path") or "").strip() or None
            self.adb.custom_adb_path = custom_path
            self._kill_tracker_process()
            self._track_restart_event.set()
            status = self.get_adb_status_payload()
            self.emit_response(req_id, True, status)
            return

        if method == "get_adb_status":
            self.emit_response(req_id, True, self.get_adb_status_payload())
            return

        if method == "inspect_destination":
            self.emit_response(req_id, True, self.inspect_destination(str(params.get("path", ""))))
            return

        if method == "list_devices":
            def _list_worker() -> None:
                try:
                    payload = self.fetch_devices_payload()
                    self.emit_response(req_id, True, payload)
                    self.emit_event("device_status", payload)
                except Exception as exc:
                    self.emit_response(req_id, False, error_code="ADB_LIST_ERROR", error_msg=str(exc))

            threading.Thread(target=_list_worker, daemon=True).start()
            return

        if method == "resolve_whatsapp_targets":
            serial = str(params.get("serial", ""))
            def _wa_worker() -> None:
                try:
                    targets = self.adb.resolve_whatsapp_targets(serial)
                    self.emit_response(req_id, True, {
                        "targets": [{"remote_path": r, "subfolder": s} for r, s in targets]
                    })
                except Exception as exc:
                    self.emit_response(req_id, False, error_code="WA_RESOLVE_ERROR", error_msg=str(exc))

            threading.Thread(target=_wa_worker, daemon=True).start()
            return

        if method == "browse_directory":
            serial = str(params.get("serial", ""))
            path = str(params.get("path", "/sdcard"))
            offset = int(params.get("offset", 0))
            limit = int(params.get("limit", 200))
            query = str(params.get("query", ""))

            def _browse_worker() -> None:
                try:
                    res = self.browse_directory(serial, path, offset=offset, limit=limit, query=query)
                    self.emit_response(req_id, True, res)
                except Exception as exc:
                    self.emit_response(req_id, False, error_code="BROWSE_ERROR", error_msg=str(exc))

            threading.Thread(target=_browse_worker, daemon=True).start()
            return

        if method == "prescan_backup":
            job_id = str(params.get("job_id") or f"scan-{int(time.time())}")
            with self._job_lock:
                if self._active_job_id is not None:
                    self.emit_response(req_id, False, error_code="JOB_BUSY", error_msg=f"Operasi lain ({self._active_job_kind}) sedang berjalan.")
                    return
                self._active_job_id = job_id
                self._active_job_kind = "prescan"
                self.adb._is_cancelled = False

            params["job_id"] = job_id
            threading.Thread(target=self._run_prescan, args=(params,), daemon=True).start()
            self.emit_response(req_id, True, {"job_id": job_id, "started": True})
            return

        if method == "start_backup":
            job_id = str(params.get("job_id") or f"backup-{int(time.time())}")
            with self._job_lock:
                if self._active_job_id is not None:
                    self.emit_response(req_id, False, error_code="JOB_BUSY", error_msg=f"Backup lain sedang berjalan ({self._active_job_id}).")
                    return
                self._active_job_id = job_id
                self._active_job_kind = "backup"
                self.adb._is_cancelled = False

            params["job_id"] = job_id
            threading.Thread(target=self._run_backup, args=(params,), daemon=True).start()
            self.emit_response(req_id, True, {"job_id": job_id, "started": True})
            return

        self.emit_response(req_id, False, error_code="UNKNOWN_METHOD", error_msg=f"Unknown method: {method}")

    def run(self) -> int:
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(_REAL_STDOUT, "reconfigure"):
            _REAL_STDOUT.reconfigure(encoding="utf-8", errors="replace")

        status = self.get_adb_status_payload()
        self.emit_event("backend_ready", {
            "pid": os.getpid(),
            "python_version": sys.version.split()[0],
            **status,
        })
        self.start_device_tracker()

        for raw_line in sys.stdin:
            if self._stop_event.is_set():
                break
            line = raw_line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as exc:
                self.emit_response("", False, error_code="INVALID_JSON", error_msg=str(exc))
                continue

            if not isinstance(req, dict):
                self.emit_response("", False, error_code="INVALID_REQUEST", error_msg="Request must be a JSON object")
                continue

            self.handle_request(req)
            if self._stop_event.is_set():
                break

        self._stop_event.set()
        self.adb.cancel_operation()
        self._kill_tracker_process()
        return 0


def main() -> None:
    worker = IpcWorker()
    raise SystemExit(worker.run())


if __name__ == "__main__":
    main()
