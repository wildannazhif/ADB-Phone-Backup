"""
Target directory resolution and backup target planning for ADB Phone Backup.
Preserves exact folder compatibility rules from the original application so
previously backed-up files are accurately matched and auto-skipped.
"""

from __future__ import annotations

import datetime
import os
import re
from dataclasses import dataclass
from typing import Optional

from .adb_manager import AdbManager


@dataclass(frozen=True)
class BackupTarget:
    remote_path: str
    local_path: str
    label: str
    category: str


def resolve_target_dir(base_dest: str, category: str, sub_name: str = "") -> str:
    """
    Resolves the exact local destination directory for a given target category.
    Detects existing folder structures (e.g. Documents vs Dokumen, flat WhatsApp vs nested)
    so that previously backed-up files are correctly located and skipped!
    """
    base = os.path.normpath(base_dest)
    base_lower = os.path.basename(base).lower()

    if category == "DCIM":
        if base_lower in ("dcim", "camera"):
            return base
        for candidate in ["DCIM", "dcim", "Camera", "camera"]:
            p = os.path.join(base, candidate)
            if os.path.exists(p) and os.path.isdir(p):
                return p
        return os.path.join(base, "DCIM")

    elif category == "Documents":
        if base_lower in ("documents", "dokumen", "docs"):
            return base
        for candidate in ["Documents", "documents", "Dokumen", "dokumen"]:
            p = os.path.join(base, candidate)
            if os.path.exists(p) and os.path.isdir(p):
                return p
        return os.path.join(base, "Documents")

    elif category == "Pictures":
        if base_lower in ("pictures", "gambar", "screenshots"):
            return base
        for candidate in ["Pictures", "pictures", "Gambar", "gambar"]:
            p = os.path.join(base, candidate)
            if os.path.exists(p) and os.path.isdir(p):
                return p
        return os.path.join(base, "Pictures")

    elif category == "WhatsApp":
        clean_sub = os.path.basename(sub_name)
        candidates = [
            os.path.join(base, "WhatsApp", clean_sub),
            os.path.join(base, clean_sub),
            os.path.join(base, "WhatsApp Media", clean_sub),
            os.path.join(base, "Media", clean_sub),
            os.path.join(base, "WhatsApp", clean_sub.replace("WhatsApp ", "")),
            os.path.join(base, clean_sub.replace("WhatsApp ", "")),
        ]
        for c in candidates:
            if os.path.exists(c) and os.path.isdir(c):
                return c
        return os.path.join(base, "WhatsApp", clean_sub)

    return os.path.join(base, sub_name or category)


def compute_backup_root_dest(
    dest_dir: str,
    auto_subfolder: bool,
    device_model: str = "Android Device",
    now: Optional[datetime.datetime] = None,
) -> str:
    """Computes final local backup root matching original subfolder naming."""
    clean_dest = os.path.normpath(dest_dir.strip())
    if not auto_subfolder:
        return clean_dest

    raw_name = (device_model or "Android_Device").replace(" ", "_").replace("/", "_")
    device_clean_name = re.sub(r'[<>:"\\|?*]', "_", raw_name)
    stamp = (now or datetime.datetime.now()).strftime("%Y-%m-%d")
    return os.path.join(clean_dest, f"Backup_{device_clean_name}_{stamp}")


def build_active_targets(
    adb: AdbManager,
    final_root_dest: str,
    serial: str,
    *,
    include_dcim: bool = True,
    include_documents: bool = True,
    include_pictures: bool = True,
    include_whatsapp: bool = True,
    custom_enabled: bool = False,
    custom_path: str = "",
    custom_paths: Optional[list[str]] = None,
) -> list[BackupTarget]:
    """Builds the ordered list of backup targets preserving original naming & mapping."""
    targets: list[BackupTarget] = []

    if include_dcim:
        loc = resolve_target_dir(final_root_dest, "DCIM")
        targets.append(BackupTarget("/sdcard/DCIM", loc, "DCIM", "DCIM"))

    if include_documents:
        loc = resolve_target_dir(final_root_dest, "Documents")
        targets.append(BackupTarget("/sdcard/Documents", loc, "Dokumen", "Documents"))

    if include_pictures:
        loc = resolve_target_dir(final_root_dest, "Pictures")
        targets.append(BackupTarget("/sdcard/Pictures", loc, "Pictures", "Pictures"))

    if include_whatsapp:
        wa_targets = adb.resolve_whatsapp_targets(serial)
        for remote_p, local_sub in wa_targets:
            loc = resolve_target_dir(final_root_dest, "WhatsApp", local_sub)
            targets.append(BackupTarget(remote_p, loc, f"WhatsApp ({local_sub})", "WhatsApp"))

    resolved_custom_paths: list[str] = []
    if custom_enabled and custom_path and custom_path.strip():
        resolved_custom_paths.append(custom_path.strip())
    if custom_paths:
        for p in custom_paths:
            clean = p.strip()
            if clean and clean not in resolved_custom_paths:
                resolved_custom_paths.append(clean)

    seen_remote = {t.remote_path.rstrip("/") for t in targets}
    for c_path in resolved_custom_paths:
        norm_remote = c_path.rstrip("/") or "/"
        if norm_remote in seen_remote:
            continue
        seen_remote.add(norm_remote)
        c_name = os.path.basename(norm_remote) or "Custom_Folder"
        loc = os.path.join(final_root_dest, c_name)
        targets.append(BackupTarget(c_path, loc, f"Kustom ({c_name})", "Custom"))

    return targets
