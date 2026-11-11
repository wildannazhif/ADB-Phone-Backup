"""
Comprehensive unit and IPC integration tests for the preserved Python backend.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.adb_manager import AdbManager, DeviceInfo
from src.ipc_worker import IpcWorker, _parse_ls_long_entries
from src.target_resolver import build_active_targets, compute_backup_root_dest, resolve_target_dir


class TestAdbManagerPreservedBehavior:
    def test_smart_sync_auto_skip_preserves_nomedia_and_skips_matching_files(self, tmp_path: Path):
        dest = tmp_path / "DCIM"
        (dest / "Camera").mkdir(parents=True)
        (dest / "Camera" / "IMG_1.jpg").write_bytes(b"abcde")  # 5 bytes -> should skip
        (dest / "Camera" / "IMG_2.jpg").write_bytes(b"old")    # 3 bytes != 7 -> should pull
        (dest / "Camera" / ".nomedia").write_bytes(b"")        # 0 bytes -> should skip
        (dest / "Screenshots").mkdir(parents=True)             # missing .nomedia here -> should pull

        adb = AdbManager(custom_adb_path="adb.exe")
        adb.find_adb = lambda: "adb.exe"  # type: ignore[method-assign]
        adb.scan_remote_files = lambda serial, remote_dir, log_callback=None: [  # type: ignore[method-assign]
            ("Camera/IMG_1.jpg", 5),
            ("Camera/IMG_2.jpg", 7),
            ("Camera/.nomedia", 0),
            ("Screenshots/.nomedia", 0),
            ("Screenshots/shot 1.png", 12),
        ]

        pulled_cmds: list[list[str]] = []
        telemetry_events: list[dict] = []

        def fake_popen(args, **kwargs):
            pulled_cmds.append(args)
            local_target = Path(args[-1])
            local_target.parent.mkdir(parents=True, exist_ok=True)
            if local_target.name == "IMG_2.jpg":
                local_target.write_bytes(b"1234567")
            elif local_target.name == "shot 1.png":
                local_target.write_bytes(b"0123456789ab")
            else:
                local_target.write_bytes(b"")
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate.return_value = ("", "")
            return proc

        with patch("src.adb_manager.subprocess.Popen", side_effect=fake_popen):
            transferred, skipped, errors = adb.smart_sync(
                serial="TEST123",
                remote_dir="/sdcard/DCIM",
                local_dest=str(dest),
                preserve_timestamps=True,
                telemetry_callback=telemetry_events.append,
            )

        assert (transferred, skipped, errors) == (3, 2, 0)
        assert all("-a" in cmd for cmd in pulled_cmds)
        pulled_remotes = [cmd[-2] for cmd in pulled_cmds]
        assert pulled_remotes == [
            "/sdcard/DCIM/Camera/IMG_2.jpg",
            "/sdcard/DCIM/Screenshots/.nomedia",
            "/sdcard/DCIM/Screenshots/shot 1.png",
        ]
        assert telemetry_events[-1]["phase"] == "target_done"
        assert telemetry_events[-1]["bytes_transferred"] == 7 + 0 + 12
        assert telemetry_events[-1]["bytes_total_to_pull"] == 7 + 0 + 12

    def test_smart_sync_auto_skip_disabled_re_pulls_all(self, tmp_path: Path):
        dest = tmp_path / "Docs"
        dest.mkdir()
        (dest / "file.pdf").write_bytes(b"1234")

        adb = AdbManager()
        adb.find_adb = lambda: "adb.exe"  # type: ignore[method-assign]
        adb.scan_remote_files = lambda serial, remote_dir, log_callback=None: [  # type: ignore[method-assign]
            ("file.pdf", 4),
        ]

        pulled_cmds: list[list[str]] = []

        def fake_popen(args, **kwargs):
            pulled_cmds.append(args)
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate.return_value = ("", "")
            return proc

        with patch("src.adb_manager.subprocess.Popen", side_effect=fake_popen):
            transferred, skipped, errors = adb.smart_sync(
                serial="TEST123",
                remote_dir="/sdcard/Documents",
                local_dest=str(dest),
                preserve_timestamps=False,
                auto_skip=False,
            )

        assert (transferred, skipped, errors) == (1, 0, 0)
        assert "-a" not in pulled_cmds[0]

    def test_smart_sync_cancellation_stops_remaining_pulls(self, tmp_path: Path):
        dest = tmp_path / "DCIM"
        adb = AdbManager()
        adb.find_adb = lambda: "adb.exe"  # type: ignore[method-assign]
        adb.scan_remote_files = lambda serial, remote_dir, log_callback=None: [  # type: ignore[method-assign]
            ("a.jpg", 10),
            ("b.jpg", 10),
            ("c.jpg", 10),
        ]

        call_count = 0

        def fake_popen(args, **kwargs):
            nonlocal call_count
            call_count += 1
            adb._is_cancelled = True
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate.return_value = ("", "")
            return proc

        with patch("src.adb_manager.subprocess.Popen", side_effect=fake_popen):
            transferred, skipped, errors = adb.smart_sync(
                serial="TEST123",
                remote_dir="/sdcard/DCIM",
                local_dest=str(dest),
            )

        assert call_count == 1
        assert transferred == 1
        assert adb.is_cancelled() is True

    def test_scan_remote_files_printf_and_fallbacks(self):
        adb = AdbManager()
        adb.find_adb = lambda: "adb.exe"  # type: ignore[method-assign]

        # Tier 1: find -printf
        res_printf = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1024 /sdcard/DCIM/Camera/my photo.jpg\n0 /sdcard/DCIM/.nomedia\n", stderr=""
        )
        with patch.object(adb, "_run_cmd", return_value=res_printf):
            files = adb.scan_remote_files("SER", "/sdcard/DCIM/")
        assert files == [("Camera/my photo.jpg", 1024), (".nomedia", 0)]

        # Tier 2 fallback when printf fails
        res_empty = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="bad option")
        res_stat = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="512 /sdcard/Documents/report.pdf\n", stderr=""
        )
        with patch.object(adb, "_run_cmd", side_effect=[res_empty, res_stat]):
            files = adb.scan_remote_files("SER", "/sdcard/Documents")
        assert files == [("report.pdf", 512)]

    def test_resolve_whatsapp_targets_excludes_audio_and_stickers(self):
        adb = AdbManager()

        def fake_run(args, **kwargs):
            cmd_str = " ".join(args)
            if "/sdcard/Android/media/com.whatsapp/WhatsApp/Media'" in cmd_str:
                return subprocess.CompletedProcess(args, 0, "FOUND\n", "")
            if "WhatsApp Images" in cmd_str or "WhatsApp Video" in cmd_str or "WhatsApp Documents" in cmd_str:
                return subprocess.CompletedProcess(args, 0, "FOUND\n", "")
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch.object(adb, "_run_cmd", side_effect=fake_run):
            targets = adb.resolve_whatsapp_targets("SER")

        assert targets == [
            ("/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Images", "WhatsApp Images"),
            ("/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Video", "WhatsApp Video"),
            ("/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Documents", "WhatsApp Documents"),
        ]

    def test_find_adb_missing_raises_file_not_found(self, tmp_path: Path):
        adb = AdbManager(custom_adb_path=str(tmp_path / "missing_adb.exe"))
        with (
            patch("src.adb_manager.shutil.which", return_value=None),
            patch("src.adb_manager.Path.exists", return_value=False),
        ):
            with pytest.raises(FileNotFoundError):
                adb.find_adb()


class TestTargetResolver:
    def test_preserves_existing_localized_folder_names(self, tmp_path: Path):
        (tmp_path / "Camera").mkdir()
        (tmp_path / "Dokumen").mkdir()
        (tmp_path / "Gambar").mkdir()
        (tmp_path / "WhatsApp Media" / "WhatsApp Images").mkdir(parents=True)

        assert resolve_target_dir(str(tmp_path), "DCIM") == str(tmp_path / "Camera")
        assert resolve_target_dir(str(tmp_path), "Documents") == str(tmp_path / "Dokumen")
        assert resolve_target_dir(str(tmp_path), "Pictures") == str(tmp_path / "Gambar")
        assert resolve_target_dir(str(tmp_path), "WhatsApp", "WhatsApp Images") == str(
            tmp_path / "WhatsApp Media" / "WhatsApp Images"
        )

    def test_compute_backup_root_dest_with_subfolder(self, tmp_path: Path):
        import datetime
        now = datetime.datetime(2026, 11, 11, 10, 0, 0)
        res = compute_backup_root_dest(str(tmp_path), auto_subfolder=True, device_model="Pixel 8/Pro", now=now)
        assert res == str(tmp_path / "Backup_Pixel_8_Pro_2026-11-11")


class TestIpcWorkerAndBrowser:
    def test_parse_ls_long_entries_with_spaces_and_sizes(self):
        sample = "\n".join([
            "total 64",
            "drwxrwx--- 4 u0_a12 media_rw 4096 2026-10-20 14:22 DCIM/",
            "drwxrwx--- 2 u0_a12 media_rw 4096 2026-10-20 14:22 .",
            "-rw-rw---- 1 u0_a12 media_rw 2048576 2026-10-21 09:15 holiday photo.jpg",
            "lrwxrwxrwx 1 root root 21 2024-01-01 00:00 sdcard -> /storage/self/primary",
        ])
        dirs, files, matched = _parse_ls_long_entries(sample)
        assert matched is True
        assert [d["name"] for d in dirs] == ["DCIM"]
        assert len(files) == 2
        assert files[0]["name"] == "holiday photo.jpg"
        assert files[0]["size"] == 2048576
        assert files[1]["is_symlink"] is True

    def test_browse_directory_handles_inaccessible_and_pagination(self):
        worker = IpcWorker()
        worker.adb.find_adb = lambda: "adb.exe"  # type: ignore[method-assign]

        # Permission denied
        with patch.object(
            worker.adb,
            "_run_cmd",
            return_value=subprocess.CompletedProcess([], 1, "ls: /sdcard/Android/data: Permission denied\n", ""),
        ):
            res = worker.browse_directory("SER", "/sdcard/Android/data")
        assert res["accessible"] is False
        assert "Permission denied" in (res["error"] or "")

        # Pagination on large folder
        lines = ["total 100"] + [
            f"-rw-rw---- 1 u0_a1 media_rw {i * 100} 2026-10-21 10:00 img_{i:03d}.jpg"
            for i in range(1, 26)
        ]
        with patch.object(
            worker.adb,
            "_run_cmd",
            return_value=subprocess.CompletedProcess([], 0, "\n".join(lines), ""),
        ):
            page1 = worker.browse_directory("SER", "/sdcard/DCIM", offset=0, limit=10)
            page2 = worker.browse_directory("SER", "/sdcard/DCIM", offset=20, limit=10)
        assert page1["accessible"] is True
        assert len(page1["entries"]) == 10
        assert page1["has_more"] is True
        assert page1["total_files"] == 25
        assert len(page2["entries"]) == 5
        assert page2["has_more"] is False

    def test_ipc_subprocess_stdio_protocol_and_clean_stdout(self, tmp_path: Path):
        proc = subprocess.Popen(
            [sys.executable, "-u", str(REPO_ROOT / "src" / "ipc_worker.py")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=str(REPO_ROOT),
        )
        assert proc.stdin is not None and proc.stdout is not None

        try:
            ready_line = proc.stdout.readline()
            ready = json.loads(ready_line)
            assert ready["type"] == "event"
            assert ready["event"] == "backend_ready"

            commands = [
                {"id": "1", "method": "ping", "params": {}},
                {"id": "2", "method": "inspect_destination", "params": {"path": str(tmp_path)}},
                {"id": "3", "method": "unknown_op", "params": {}},
                {"id": "4", "method": "shutdown", "params": {}},
            ]
            for cmd in commands:
                proc.stdin.write(json.dumps(cmd) + "\n")
            proc.stdin.flush()

            responses: dict[str, dict] = {}
            while len(responses) < 4:
                line = proc.stdout.readline()
                if not line:
                    break
                frame = json.loads(line)
                if frame.get("type") == "response":
                    responses[frame["id"]] = frame

            assert responses["1"]["ok"] is True
            assert responses["1"]["result"]["pong"] is True
            assert responses["2"]["ok"] is True
            assert responses["2"]["result"]["valid"] is True
            assert responses["3"]["ok"] is False
            assert responses["3"]["error"]["code"] == "UNKNOWN_METHOD"
            assert responses["4"]["ok"] is True
        finally:
            proc.wait(timeout=5)
            assert proc.returncode == 0

    def test_ipc_worker_prescan_and_backup_events(self, tmp_path: Path):
        worker = IpcWorker()
        worker.adb.find_adb = lambda: "adb.exe"  # type: ignore[method-assign]
        worker.adb.scan_remote_files = lambda serial, remote_dir, log_callback=None: [  # type: ignore[method-assign]
            ("IMG_001.jpg", 100),
            (".nomedia", 0),
        ]

        emitted: list[dict] = []
        worker.emit_event = lambda event, payload: emitted.append({"event": event, "payload": payload})  # type: ignore[method-assign]

        # Pre-seed one matching file so Auto-Skip skips 1 and pulls 1
        (tmp_path / "DCIM").mkdir()
        (tmp_path / "DCIM" / ".nomedia").write_bytes(b"")

        worker._run_prescan({
            "job_id": "scan-1",
            "serial": "SER123",
            "dest_dir": str(tmp_path),
            "targets": {"dcim": True, "documents": False, "pictures": False, "whatsapp": False},
        })
        prescan_done = [e for e in emitted if e["event"] == "prescan_completed"][-1]["payload"]
        assert prescan_done["total_on_phone"] == 2
        assert prescan_done["total_already_on_disk"] == 1
        assert prescan_done["total_new"] == 1
        assert prescan_done["total_new_bytes"] == 100

        emitted.clear()

        def fake_popen(args, **kwargs):
            local_target = Path(args[-1])
            local_target.parent.mkdir(parents=True, exist_ok=True)
            local_target.write_bytes(b"x" * 100)
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate.return_value = ("", "")
            return proc

        with patch("src.adb_manager.subprocess.Popen", side_effect=fake_popen):
            worker._run_backup({
                "job_id": "job-1",
                "serial": "SER123",
                "dest_dir": str(tmp_path),
                "device_model": "Pixel 8",
                "targets": {"dcim": True, "documents": False, "pictures": False, "whatsapp": False},
            })

        completed = [e for e in emitted if e["event"] == "backup_completed"][-1]["payload"]
        assert completed["status"] == "completed"
        assert completed["files_transferred"] == 1
        assert completed["files_skipped"] == 1
        assert completed["files_failed"] == 0
        assert completed["bytes_transferred"] == 100

    def test_legacy_gui_imports_remain_compatible(self):
        import src.gui  # noqa: F401
        import src.browser_dialog  # noqa: F401
        assert hasattr(src.gui, "launch_gui")
