"""
Modern, Stunning & Ultra-Lightweight GUI for ADB Phone Backup Pro.
Crafted with an Obsidian / Cyber-Slate dark aesthetic, interactive cards,
live storage capacity meter, smooth hover transitions, and bulletproof Auto-Skip.
"""

from __future__ import annotations

import datetime
import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from .adb_manager import AdbManager, DeviceInfo
from .browser_dialog import AndroidBrowserDialog


class ModernBackupApp(tk.Tk):
    """Modern, high-performance GUI for ADB Phone Backup."""

    def __init__(self):
        super().__init__()

        self._enable_dpi_awareness()

        self.title("ADB Phone Backup Pro — DCIM · Dokumen · Pictures · WhatsApp")
        self.geometry("1020x800")
        self.minsize(920, 700)
        self.configure(bg="#070b14")

        self._set_app_icon()

        self.adb = AdbManager()
        self.devices: list[DeviceInfo] = []
        self.selected_device: Optional[DeviceInfo] = None

        self.is_backing_up = False
        self.worker_thread: Optional[threading.Thread] = None

        # State Variables
        self.device_var = tk.StringVar(value="Memindai perangkat...")
        self.dest_path_var = tk.StringVar(value="")
        self.free_space_var = tk.StringVar(value="Pilih folder harddisk tujuan di bawah")
        self.auto_subfolder_var = tk.BooleanVar(value=False)
        self.preserve_time_var = tk.BooleanVar(value=True)
        self.status_detail_var = tk.StringVar(value="Siap untuk backup. Hubungkan HP via USB.")
        self.progress_val = tk.DoubleVar(value=0.0)

        # Primary Backup Targets (All 4 ON by default)
        self.target_dcim_var = tk.BooleanVar(value=True)
        self.target_doc_var = tk.BooleanVar(value=True)
        self.target_pics_var = tk.BooleanVar(value=True)
        self.target_wa_var = tk.BooleanVar(value=True)

        # Optional Custom Path
        self.custom_enabled_var = tk.BooleanVar(value=False)
        self.custom_path_var = tk.StringVar(value="/sdcard/Download")

        # Telemetry counters
        self.stat_copied_var = tk.StringVar(value="0")
        self.stat_skipped_var = tk.StringVar(value="0")
        self.stat_target_var = tk.StringVar(value="Menunggu...")
        self.stat_time_var = tk.StringVar(value="00:00")

        # Card container references for dynamic styling
        self.card_widgets: dict[str, dict] = {}

        self._configure_styles()
        self._build_ui()

        self.after(300, self.refresh_devices)

    def _enable_dpi_awareness(self) -> None:
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                try:
                    import ctypes
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass

    def _set_app_icon(self) -> None:
        candidates = []
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "assets", "icon.ico"))
            candidates.append(os.path.join(sys._MEIPASS, "icon.ico"))
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates.append(os.path.join(base_dir, "assets", "icon.ico"))

        for p in candidates:
            if os.path.exists(p):
                try:
                    self.iconbitmap(p)
                    break
                except Exception:
                    pass

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        # Combobox modern style
        style.configure(
            "TCombobox",
            fieldbackground="#0f172a",
            background="#1e293b",
            foreground="#f8fafc",
            darkcolor="#0f172a",
            lightcolor="#334155",
            bordercolor="#2a3b5c",
            arrowcolor="#38bdf8",
            padding=6,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#0f172a")],
            foreground=[("readonly", "#f8fafc")],
        )

        # Progressbar modern neon style
        style.configure(
            "Neon.Horizontal.TProgressbar",
            troughcolor="#0a0f1d",
            background="#0284c7",
            bordercolor="#1e293b",
            lightcolor="#38bdf8",
            darkcolor="#0369a1",
        )

        # Storage capacity meter
        style.configure(
            "DriveGauge.Horizontal.TProgressbar",
            troughcolor="#0f172a",
            background="#10b981",
            bordercolor="#1e293b",
            lightcolor="#34d399",
            darkcolor="#059669",
        )

    def _build_ui(self) -> None:
        # ==================== 1. TOP NAVBAR / HEADER ====================
        header = tk.Frame(self, bg="#0d1424", padx=24, pady=16, highlightthickness=1, highlightbackground="#1b253b")
        header.pack(fill=tk.X, side=tk.TOP)

        title_box = tk.Frame(header, bg="#0d1424")
        title_box.pack(side=tk.LEFT, fill=tk.Y)

        title_row = tk.Frame(title_box, bg="#0d1424")
        title_row.pack(anchor=tk.W)

        lbl_logo = tk.Label(
            title_row,
            text="⚡ ADB PHONE BACKUP",
            font=("Segoe UI", 16, "bold"),
            bg="#0d1424",
            fg="#f8fafc",
        )
        lbl_logo.pack(side=tk.LEFT)

        lbl_badge = tk.Label(
            title_row,
            text="PRO EDITION",
            font=("Segoe UI", 8, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            padx=8,
            pady=2,
            relief=tk.FLAT,
        )
        lbl_badge.pack(side=tk.LEFT, padx=(10, 0))

        lbl_sub = tk.Label(
            title_box,
            text="DCIM · Dokumen · Pictures · WhatsApp (Images/Video/Docs) dengan Smart Auto-Skip Presisi",
            font=("Segoe UI", 9),
            bg="#0d1424",
            fg="#94a3b8",
        )
        lbl_sub.pack(anchor=tk.W, pady=(3, 0))

        # Device selection area on top right
        dev_box = tk.Frame(header, bg="#0d1424")
        dev_box.pack(side=tk.RIGHT, fill=tk.Y)

        dev_row = tk.Frame(dev_box, bg="#0d1424")
        dev_row.pack(anchor=tk.E)

        self.cb_devices = ttk.Combobox(
            dev_row,
            textvariable=self.device_var,
            state="readonly",
            width=32,
            font=("Segoe UI", 9),
        )
        self.cb_devices.pack(side=tk.LEFT, padx=(0, 8))
        self.cb_devices.bind("<<ComboboxSelected>>", self._on_device_selected)

        btn_refresh = tk.Button(
            dev_row,
            text="🔄 Segarkan",
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg="#f8fafc",
            activebackground="#334155",
            activeforeground="#38bdf8",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.refresh_devices,
        )
        btn_refresh.pack(side=tk.LEFT)
        self._add_hover(btn_refresh, "#1e293b", "#334155")

        self.lbl_device_status = tk.Label(
            dev_box,
            text="Mendeteksi koneksi kabel USB...",
            font=("Segoe UI", 8),
            bg="#0d1424",
            fg="#94a3b8",
        )
        self.lbl_device_status.pack(anchor=tk.E, pady=(4, 0))

        # ==================== MAIN BODY SCROLLABLE / STACK ====================
        main_body = tk.Frame(self, bg="#070b14", padx=22, pady=14)
        main_body.pack(fill=tk.BOTH, expand=True)

        # ==================== 2. HERO CARDS: 4 FOLDER PRIORITAS ====================
        sec_targets = tk.Frame(main_body, bg="#070b14")
        sec_targets.pack(fill=tk.X, pady=(0, 12))

        sec1_header = tk.Frame(sec_targets, bg="#070b14")
        sec1_header.pack(fill=tk.X, pady=(0, 8))

        lbl_sec1 = tk.Label(
            sec1_header,
            text="📁 FOLDER SUMBER DI HP (PILIH YANG INGIN DI-BACKUP)",
            font=("Segoe UI", 9, "bold"),
            bg="#070b14",
            fg="#38bdf8",
        )
        lbl_sec1.pack(side=tk.LEFT)

        lbl_sec1_hint = tk.Label(
            sec1_header,
            text="Klik pada kartu untuk mengaktifkan / menonaktifkan",
            font=("Segoe UI", 8, "italic"),
            bg="#070b14",
            fg="#64748b",
        )
        lbl_sec1_hint.pack(side=tk.RIGHT)

        # 4 Interactive Grid Cards
        grid_cards = tk.Frame(sec_targets, bg="#070b14")
        grid_cards.pack(fill=tk.X)
        grid_cards.columnconfigure(0, weight=1)
        grid_cards.columnconfigure(1, weight=1)
        grid_cards.columnconfigure(2, weight=1)
        grid_cards.columnconfigure(3, weight=1)

        self._build_interactive_card(
            parent=grid_cards,
            key="dcim",
            col=0,
            icon="📸",
            title="DCIM",
            subtitle="Kamera & Foto Utama",
            detail="Foto & video kamera (/sdcard/DCIM)",
            var=self.target_dcim_var,
            accent_color="#0284c7",
            badge_text="KAMERA",
        )

        self._build_interactive_card(
            parent=grid_cards,
            key="doc",
            col=1,
            icon="📄",
            title="Dokumen",
            subtitle="Folder Dokumen",
            detail="Berkas PDF, Word, Excel, kerjaan",
            var=self.target_doc_var,
            accent_color="#0d9488",
            badge_text="DOKUMEN",
        )

        self._build_interactive_card(
            parent=grid_cards,
            key="pics",
            col=2,
            icon="🖼️",
            title="Pictures",
            subtitle="Screenshots & Galeri",
            detail="Tangkapan layar & gambar aplikasi",
            var=self.target_pics_var,
            accent_color="#7c3aed",
            badge_text="GALERI",
        )

        self._build_interactive_card(
            parent=grid_cards,
            key="wa",
            col=3,
            icon="💬",
            title="WhatsApp",
            subtitle="Media Pilihan Saja",
            detail="Images, Video & Documents (Voice note skip)",
            var=self.target_wa_var,
            accent_color="#10b981",
            badge_text="WHATSAPP MEDIA",
        )

        # Custom Folder Accordion Box
        custom_box = tk.Frame(sec_targets, bg="#0d1424", padx=14, pady=10, highlightthickness=1, highlightbackground="#1b253b")
        custom_box.pack(fill=tk.X, pady=(10, 0))

        cb_custom = tk.Checkbutton(
            custom_box,
            text="+ Tambah Folder Kustom Lainnya:",
            variable=self.custom_enabled_var,
            bg="#0d1424",
            fg="#f8fafc",
            activebackground="#0d1424",
            activeforeground="#38bdf8",
            selectcolor="#070b14",
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        cb_custom.pack(side=tk.LEFT, padx=(0, 10))

        self.entry_custom = tk.Entry(
            custom_box,
            textvariable=self.custom_path_var,
            font=("Segoe UI", 10),
            bg="#070b14",
            fg="#38bdf8",
            insertbackground="#38bdf8",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#2a3b5c",
            highlightcolor="#38bdf8",
        )
        self.entry_custom.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=4)

        btn_browse_phone = tk.Button(
            custom_box,
            text="📱 Jelajahi HP...",
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg="#38bdf8",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._open_android_browser,
        )
        btn_browse_phone.pack(side=tk.LEFT)
        self._add_hover(btn_browse_phone, "#1e293b", "#334155")

        # ==================== 3. HARDDISK & AUTO-SKIP BANNER ====================
        sec_dest = tk.Frame(main_body, bg="#0d1424", padx=18, pady=14, highlightthickness=1, highlightbackground="#1b253b")
        sec_dest.pack(fill=tk.X, pady=(0, 12))

        dest_header_row = tk.Frame(sec_dest, bg="#0d1424")
        dest_header_row.pack(fill=tk.X, pady=(0, 8))

        lbl_sec2 = tk.Label(
            dest_header_row,
            text="💾 FOLDER / HARDDISK TUJUAN",
            font=("Segoe UI", 9, "bold"),
            bg="#0d1424",
            fg="#38bdf8",
        )
        lbl_sec2.pack(side=tk.LEFT)

        tag_autoskip = tk.Label(
            dest_header_row,
            text="⚡ SMART AUTO-SKIP AKTIF (Relative Path & Ukuran File Presisi)",
            font=("Segoe UI", 8, "bold"),
            bg="#1e1b4b",
            fg="#a78bfa",
            padx=10,
            pady=3,
            highlightthickness=1,
            highlightbackground="#4338ca",
        )
        tag_autoskip.pack(side=tk.RIGHT)

        dest_input_row = tk.Frame(sec_dest, bg="#0d1424")
        dest_input_row.pack(fill=tk.X, pady=(0, 8))

        self.entry_dest = tk.Entry(
            dest_input_row,
            textvariable=self.dest_path_var,
            font=("Segoe UI", 10),
            bg="#070b14",
            fg="#f8fafc",
            insertbackground="#38bdf8",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#2a3b5c",
            highlightcolor="#38bdf8",
        )
        self.entry_dest.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12), ipady=6)

        btn_browse_dest = tk.Button(
            dest_input_row,
            text="📂 Pilih Folder Harddisk...",
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._choose_dest_directory,
        )
        btn_browse_dest.pack(side=tk.LEFT)
        self._add_hover(btn_browse_dest, "#0284c7", "#0369a1")

        # Drive Space & Checkbox Options
        dest_options_row = tk.Frame(sec_dest, bg="#0d1424")
        dest_options_row.pack(fill=tk.X)

        self.lbl_free_space = tk.Label(
            dest_options_row,
            textvariable=self.free_space_var,
            font=("Segoe UI", 8, "bold"),
            bg="#0d1424",
            fg="#10b981",
        )
        self.lbl_free_space.pack(side=tk.LEFT, padx=(0, 24))

        cb_subfolder = tk.Checkbutton(
            dest_options_row,
            text="Buat subfolder tanggal baru (Jangan centang agar file lama otomatis dilewati)",
            variable=self.auto_subfolder_var,
            bg="#0d1424",
            fg="#94a3b8",
            activebackground="#0d1424",
            activeforeground="#38bdf8",
            selectcolor="#070b14",
            font=("Segoe UI", 8),
            cursor="hand2",
        )
        cb_subfolder.pack(side=tk.LEFT, padx=(0, 16))

        cb_time = tk.Checkbutton(
            dest_options_row,
            text="Pertahankan Tanggal Asli Foto (-a)",
            variable=self.preserve_time_var,
            bg="#0d1424",
            fg="#94a3b8",
            activebackground="#0d1424",
            activeforeground="#38bdf8",
            selectcolor="#070b14",
            font=("Segoe UI", 8),
            cursor="hand2",
        )
        cb_time.pack(side=tk.LEFT)

        # ==================== 4. LIVE TELEMETRY HUD ====================
        hud_frame = tk.Frame(main_body, bg="#070b14")
        hud_frame.pack(fill=tk.X, pady=(0, 10))
        hud_frame.columnconfigure(0, weight=1)
        hud_frame.columnconfigure(1, weight=1)
        hud_frame.columnconfigure(2, weight=2)
        hud_frame.columnconfigure(3, weight=1)

        self._build_hud_chip(hud_frame, 0, "📥 Disalin Baru", self.stat_copied_var, "#10b981", "#064e3b")
        self._build_hud_chip(hud_frame, 1, "⏭️ Dilewati (Auto-skip)", self.stat_skipped_var, "#c084fc", "#4c1d95")
        self._build_hud_chip(hud_frame, 2, "📂 Target Berjalan", self.stat_target_var, "#38bdf8", "#0c4a6e")
        self._build_hud_chip(hud_frame, 3, "⏱️ Waktu Berjalan", self.stat_time_var, "#fbbf24", "#78350f")

        # ==================== 5. ACTION CENTER & PROGRESS ====================
        sec_exec = tk.Frame(main_body, bg="#070b14")
        sec_exec.pack(fill=tk.X, pady=(0, 10))

        btn_row = tk.Frame(sec_exec, bg="#070b14")
        btn_row.pack(fill=tk.X, pady=(0, 8))

        self.btn_start = tk.Button(
            btn_row,
            text="🚀 MULAI BACKUP KE HARDDISK",
            font=("Segoe UI", 11, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=24,
            pady=11,
            cursor="hand2",
            command=self.start_backup,
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 10))
        self._add_hover(self.btn_start, "#0284c7", "#0ea5e9")

        self.btn_scan = tk.Button(
            btn_row,
            text="🔍 Cek Status File (Scan Dulu)",
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg="#38bdf8",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=16,
            pady=11,
            cursor="hand2",
            command=self.check_files_status,
        )
        self.btn_scan.pack(side=tk.LEFT, padx=(0, 10))
        self._add_hover(self.btn_scan, "#1e293b", "#334155")

        self.btn_cancel = tk.Button(
            btn_row,
            text="⏹️ Batalkan",
            font=("Segoe UI", 10, "bold"),
            bg="#ef4444",
            fg="#ffffff",
            activebackground="#dc2626",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=16,
            pady=11,
            cursor="hand2",
            state=tk.DISABLED,
            command=self.cancel_backup,
        )
        self.btn_cancel.pack(side=tk.LEFT, padx=(0, 10))
        self._add_hover(self.btn_cancel, "#ef4444", "#dc2626")

        self.btn_open_dest = tk.Button(
            btn_row,
            text="📁 Buka Folder Hasil",
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg="#94a3b8",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=16,
            pady=11,
            cursor="hand2",
            command=self._open_destination_in_explorer,
        )
        self.btn_open_dest.pack(side=tk.RIGHT)
        self._add_hover(self.btn_open_dest, "#1e293b", "#334155")

        self.progress_bar = ttk.Progressbar(
            sec_exec,
            orient="horizontal",
            mode="determinate",
            variable=self.progress_val,
            style="Neon.Horizontal.TProgressbar",
            length=100,
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 4))

        self.lbl_progress_detail = tk.Label(
            sec_exec,
            textvariable=self.status_detail_var,
            font=("Segoe UI", 8),
            bg="#070b14",
            fg="#94a3b8",
            anchor=tk.W,
        )
        self.lbl_progress_detail.pack(fill=tk.X)

        # ==================== 6. TERMINAL LOG CONSOLE ====================
        sec_log = tk.Frame(main_body, bg="#0d1424", padx=12, pady=10, highlightthickness=1, highlightbackground="#1b253b")
        sec_log.pack(fill=tk.BOTH, expand=True)

        log_header = tk.Frame(sec_log, bg="#0d1424")
        log_header.pack(fill=tk.X, pady=(0, 6))

        lbl_log_title = tk.Label(
            log_header,
            text="📋 LOG AKTIVITAS ADB & AUTO-SKIP",
            font=("Segoe UI", 8, "bold"),
            bg="#0d1424",
            fg="#64748b",
        )
        lbl_log_title.pack(side=tk.LEFT)

        btn_clear_log = tk.Button(
            log_header,
            text="Bersihkan Log",
            font=("Segoe UI", 8),
            bg="#1e293b",
            fg="#94a3b8",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._clear_log,
        )
        btn_clear_log.pack(side=tk.RIGHT)
        self._add_hover(btn_clear_log, "#1e293b", "#334155")

        log_scroll = tk.Scrollbar(sec_log, orient=tk.VERTICAL)
        self.txt_log = tk.Text(
            sec_log,
            bg="#070b14",
            fg="#f8fafc",
            font=("Consolas", 8),
            relief=tk.FLAT,
            yscrollcommand=log_scroll.set,
            padx=10,
            pady=8,
            wrap=tk.WORD,
        )
        log_scroll.config(command=self.txt_log.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.txt_log.tag_config("info", foreground="#38bdf8")
        self.txt_log.tag_config("skip", foreground="#c084fc")
        self.txt_log.tag_config("success", foreground="#34d399")
        self.txt_log.tag_config("warning", foreground="#fbbf24")
        self.txt_log.tag_config("error", foreground="#f87171")
        self.txt_log.tag_config("detail", foreground="#94a3b8")

        self.log(f"Aplikasi siap. {self.adb.get_adb_version()}", "info")
        self.log("Auto-Skip presisi aktif: mencocokkan relative path dan ukuran file.", "skip")

    # ==================== INTERACTIVE CARD BUILDER ====================

    def _build_interactive_card(
        self,
        parent: tk.Frame,
        key: str,
        col: int,
        icon: str,
        title: str,
        subtitle: str,
        detail: str,
        var: tk.BooleanVar,
        accent_color: str,
        badge_text: str,
    ) -> None:
        """Constructs a responsive card with toggleable state and hover glow."""
        card = tk.Frame(
            parent,
            bg="#0d1424",
            padx=12,
            pady=12,
            highlightthickness=1,
            highlightbackground="#1b253b",
            cursor="hand2",
        )
        card.grid(row=0, column=col, sticky="nsew", padx=4)

        top_row = tk.Frame(card, bg="#0d1424")
        top_row.pack(fill=tk.X)

        # Icon chip
        icon_chip = tk.Label(
            top_row,
            text=icon,
            font=("Segoe UI", 12),
            bg="#1e293b",
            fg="#f8fafc",
            padx=6,
            pady=2,
        )
        icon_chip.pack(side=tk.LEFT, padx=(0, 6))

        # Checkbutton
        cb = tk.Checkbutton(
            top_row,
            text=title,
            variable=var,
            bg="#0d1424",
            fg="#f8fafc",
            activebackground="#0d1424",
            activeforeground="#38bdf8",
            selectcolor="#070b14",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            command=lambda: self._update_card_appearance(key, var.get(), card, badge_lbl, accent_color),
        )
        cb.pack(side=tk.LEFT)

        # Category badge
        badge_lbl = tk.Label(
            top_row,
            text=badge_text,
            font=("Segoe UI", 7, "bold"),
            bg=accent_color,
            fg="#ffffff",
            padx=6,
            pady=1,
        )
        badge_lbl.pack(side=tk.RIGHT)

        lbl_sub = tk.Label(
            card,
            text=subtitle,
            font=("Segoe UI", 8, "bold"),
            bg="#0d1424",
            fg="#94a3b8",
            anchor=tk.W,
        )
        lbl_sub.pack(fill=tk.X, pady=(4, 0))

        lbl_det = tk.Label(
            card,
            text=detail,
            font=("Segoe UI", 7),
            bg="#0d1424",
            fg="#64748b",
            anchor=tk.W,
        )
        lbl_det.pack(fill=tk.X)

        # Save references for styling
        self.card_widgets[key] = {
            "card": card,
            "badge": badge_lbl,
            "accent": accent_color,
            "var": var,
        }

        # Make clicking anywhere on the card toggle the variable!
        def _toggle_card(event=None):
            var.set(not var.get())
            self._update_card_appearance(key, var.get(), card, badge_lbl, accent_color)

        for w in (card, top_row, icon_chip, lbl_sub, lbl_det):
            w.bind("<Button-1>", _toggle_card)

        # Apply initial appearance
        self._update_card_appearance(key, var.get(), card, badge_lbl, accent_color)

    def _update_card_appearance(self, key: str, is_active: bool, card: tk.Frame, badge: tk.Label, accent: str) -> None:
        if is_active:
            card.config(highlightbackground=accent, bg="#111c35")
            badge.config(bg=accent, fg="#ffffff")
        else:
            card.config(highlightbackground="#1b253b", bg="#0d1424")
            badge.config(bg="#334155", fg="#94a3b8")

    def _build_hud_chip(self, parent: tk.Frame, col: int, label: str, var: tk.StringVar, text_color: str, bg_tint: str) -> None:
        chip = tk.Frame(parent, bg="#0d1424", padx=12, pady=8, highlightthickness=1, highlightbackground="#1b253b")
        chip.grid(row=0, column=col, sticky="nsew", padx=4)

        lbl_title = tk.Label(chip, text=label, font=("Segoe UI", 7, "bold"), bg="#0d1424", fg="#94a3b8")
        lbl_title.pack(anchor=tk.W)

        lbl_val = tk.Label(chip, textvariable=var, font=("Segoe UI", 11, "bold"), bg="#0d1424", fg=text_color)
        lbl_val.pack(anchor=tk.W)

    def _add_hover(self, widget, normal_bg: str, hover_bg: str) -> None:
        widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
        widget.bind("<Leave>", lambda e: widget.config(bg=normal_bg))

    # ==================== EVENT HANDLERS & ACTIONS ====================

    def _choose_dest_directory(self) -> None:
        selected = filedialog.askdirectory(
            title="Pilih Folder Harddisk / Tempat Penyimpanan Hasil Backup",
            initialdir=self.dest_path_var.get() or os.path.expanduser("~"),
        )
        if selected:
            norm = os.path.normpath(selected)
            self.dest_path_var.set(norm)
            self._update_free_space(norm)

    def _update_free_space(self, path: str) -> None:
        try:
            usage = shutil.disk_usage(path)
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            used_pct = ((usage.total - usage.free) / usage.total) * 100.0
            drive_letter = os.path.splitdrive(path)[0] or path

            self.free_space_var.set(
                f"💾 Drive {drive_letter} [{used_pct:.0f}% Terpakai] — {free_gb:.1f} GB Bebas dari {total_gb:.1f} GB"
            )
        except Exception:
            self.free_space_var.set("Folder siap digunakan.")

    def _open_android_browser(self) -> None:
        if not self.selected_device or not self.selected_device.is_ready:
            messagebox.showwarning(
                "HP Belum Terhubung",
                "Silakan sambungkan HP Android via kabel USB dan pilih perangkat yang aktif terlebih dahulu.",
            )
            return

        AndroidBrowserDialog(
            parent=self,
            adb_manager=self.adb,
            serial=self.selected_device.serial,
            initial_path=self.custom_path_var.get() or "/sdcard",
            on_select=lambda p: (self.custom_path_var.set(p), self.custom_enabled_var.set(True)),
        )

    def refresh_devices(self) -> None:
        self.device_var.set("Mencari perangkat USB...")
        self.cb_devices.config(values=[])
        self.lbl_device_status.config(text="Memeriksa koneksi ADB...", fg="#94a3b8")

        def _worker():
            try:
                devs = self.adb.list_devices()
            except Exception as e:
                devs = []
                self.after(0, lambda: self.log(f"Gagal memindai perangkat: {e}", "error"))

            self.after(0, lambda: self._on_devices_refreshed(devs))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_devices_refreshed(self, devs: list[DeviceInfo]) -> None:
        self.devices = devs
        if not devs:
            self.device_var.set("Tidak ada HP terdeteksi")
            self.cb_devices.config(values=["Tidak ada HP terdeteksi"])
            self.selected_device = None
            self.lbl_device_status.config(
                text="⚠️ Tidak ada perangkat. Hubungkan USB & aktifkan USB Debugging.",
                fg="#f59e0b",
            )
            return

        display_names = [d.display_name for d in devs]
        self.cb_devices.config(values=display_names)

        ready_devs = [d for d in devs if d.is_ready]
        chosen = ready_devs[0] if ready_devs else devs[0]
        self.selected_device = chosen
        self.device_var.set(chosen.display_name)
        self._update_device_status_label(chosen)

    def _on_device_selected(self, event=None) -> None:
        idx = self.cb_devices.current()
        if 0 <= idx < len(self.devices):
            self.selected_device = self.devices[idx]
            self._update_device_status_label(self.selected_device)

    def _update_device_status_label(self, dev: DeviceInfo) -> None:
        if not dev.is_ready:
            if dev.status == "unauthorized":
                self.lbl_device_status.config(
                    text="🔒 HP Terkunci: Ketuk 'Izinkan USB Debugging' di layar HP Anda!",
                    fg="#f59e0b",
                )
            else:
                self.lbl_device_status.config(
                    text=f"⚠️ Status: {dev.status}. Cek kabel USB.",
                    fg="#f43f5e",
                )
            return

        details = ["🟢 Terhubung"]
        if dev.model:
            details.append(dev.model)
        if dev.android_version:
            details.append(dev.android_version)
        if dev.battery_level is not None:
            details.append(f"🔋 {dev.battery_level}%")
        if dev.storage_free:
            details.append(f"Sisa HP: {dev.storage_free}")

        self.lbl_device_status.config(
            text=" | ".join(details),
            fg="#10b981",
        )

    def log(self, message: str, level: str = "info") -> None:
        now = datetime.datetime.now().strftime("%H:%M:%S")
        prefix = {
            "info": "[INFO]",
            "skip": "[AUTO-SKIP]",
            "success": "[SUKSES]",
            "warning": "[PERINGATAN]",
            "error": "[ERROR]",
            "detail": "[FILE]",
        }.get(level, "[INFO]")

        text_to_insert = f"{now} {prefix} {message}\n"
        self.txt_log.insert(tk.END, text_to_insert, (level,))
        self.txt_log.see(tk.END)

    def _clear_log(self) -> None:
        self.txt_log.delete("1.0", tk.END)

    def _open_destination_in_explorer(self) -> None:
        dest = self.dest_path_var.get().strip()
        if dest and os.path.exists(dest):
            if sys.platform == "win32":
                os.startfile(dest)
            else:
                subprocess.run(["xdg-open", dest])
        else:
            messagebox.showinfo("Folder Belum Dipilih", "Pilih folder tujuan terlebih dahulu.")

    # ---------------- SMART DESTINATION PATH RESOLVER ----------------

    def _resolve_target_dir(self, base_dest: str, category: str, sub_name: str = "") -> str:
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

    # ---------------- PRE-SCAN FILE STATUS CHECK ----------------

    def check_files_status(self) -> None:
        """Quickly scans phone folders and harddisk destination to display skip/copy status."""
        if not self.selected_device or not self.selected_device.is_ready:
            messagebox.showwarning("HP Belum Siap", "Hubungkan HP via USB dan pastikan status '🟢 Terhubung'.")
            return

        dest_dir = self.dest_path_var.get().strip()
        if not dest_dir:
            messagebox.showwarning("Tujuan Belum Dipilih", "Pilih folder tujuan di harddisk terlebih dahulu.")
            self._choose_dest_directory()
            return

        self.btn_scan.config(state=tk.DISABLED)
        self.status_detail_var.set("Memeriksa status file di HP & Harddisk...")
        self.log("=" * 60, "info")
        self.log("Memulai pemeriksaan status file (Pre-Scan)...", "info")

        serial = self.selected_device.serial

        def _scan_worker():
            targets = self._get_active_targets(dest_dir, serial)
            report_lines = []
            total_on_phone = 0
            total_already_on_disk = 0
            total_new = 0

            for remote_p, local_p, label in targets:
                phone_files = self.adb.scan_remote_files(serial, remote_p)
                p_count = len(phone_files)
                total_on_phone += p_count

                # Index local folder
                local_index = {}
                if os.path.exists(local_p):
                    for r, _, fns in os.walk(local_p):
                        for fn in fns:
                            fp = os.path.join(r, fn)
                            try:
                                sz = os.path.getsize(fp)
                                rel = os.path.relpath(fp, local_p).replace("\\", "/").strip("/").lower()
                                local_index[rel] = sz
                            except OSError:
                                pass

                skipped = 0
                for rel_p, rem_sz in phone_files:
                    rel_norm = rel_p.replace("\\", "/").strip("/").lower()
                    if rel_norm in local_index and local_index[rel_norm] == rem_sz:
                        skipped += 1

                new_count = p_count - skipped
                total_already_on_disk += skipped
                total_new += new_count

                msg = f"{label}: {p_count:,} di HP -> {skipped:,} sudah ada di harddisk, {new_count:,} baru"
                report_lines.append(msg)
                self.after(0, lambda m=msg: self.log(f"  • {m}", "skip" if "0 baru" in m else "info"))

            summary = f"Total: {total_on_phone:,} file di HP | {total_already_on_disk:,} sudah ada (Auto-Skip) | {total_new:,} file baru"
            self.after(0, lambda: self.log(summary, "success"))
            self.after(0, lambda: self.status_detail_var.set(summary))
            self.after(0, lambda: self.btn_scan.config(state=tk.NORMAL))
            self.after(0, lambda: messagebox.showinfo(
                "Hasil Pemeriksaan Status File",
                "\n".join(report_lines) + f"\n\n{summary}"
            ))

        threading.Thread(target=_scan_worker, daemon=True).start()

    def _get_active_targets(self, final_root_dest: str, serial: str) -> list[tuple[str, str, str]]:
        targets: list[tuple[str, str, str]] = []

        if self.target_dcim_var.get():
            loc = self._resolve_target_dir(final_root_dest, "DCIM")
            targets.append(("/sdcard/DCIM", loc, "📸 DCIM"))

        if self.target_doc_var.get():
            loc = self._resolve_target_dir(final_root_dest, "Documents")
            targets.append(("/sdcard/Documents", loc, "📄 Dokumen"))

        if self.target_pics_var.get():
            loc = self._resolve_target_dir(final_root_dest, "Pictures")
            targets.append(("/sdcard/Pictures", loc, "🖼️ Pictures"))

        if self.target_wa_var.get():
            wa_targets = self.adb.resolve_whatsapp_targets(serial)
            for remote_p, local_sub in wa_targets:
                loc = self._resolve_target_dir(final_root_dest, "WhatsApp", local_sub)
                targets.append((remote_p, loc, f"💬 WhatsApp ({local_sub})"))

        if self.custom_enabled_var.get():
            c_path = self.custom_path_var.get().strip()
            if c_path:
                c_name = os.path.basename(c_path.rstrip("/")) or "Custom_Folder"
                loc = os.path.join(final_root_dest, c_name)
                targets.append((c_path, loc, f"📁 Kustom ({c_name})"))

        return targets

    # ---------------- BACKUP ENGINE EXECUTION ----------------

    def start_backup(self) -> None:
        if self.is_backing_up:
            return

        if not self.selected_device or not self.selected_device.is_ready:
            messagebox.showerror(
                "Perangkat Belum Siap",
                "Pastikan HP Android terhubung via USB dan statusnya '🟢 Terhubung' (bukan unauthorized/offline).",
            )
            return

        dest_dir = self.dest_path_var.get().strip()
        if not dest_dir:
            messagebox.showwarning(
                "Tujuan Belum Dipilih",
                "Silakan pilih folder tujuan di harddisk / PC terlebih dahulu pada Bagian 2.",
            )
            self._choose_dest_directory()
            return

        if self.auto_subfolder_var.get():
            device_clean_name = self.selected_device.model.replace(" ", "_").replace("/", "_")
            date_stamp = datetime.datetime.now().strftime("%Y-%m-%d")
            final_root_dest = os.path.join(dest_dir, f"Backup_{device_clean_name}_{date_stamp}")
        else:
            final_root_dest = dest_dir

        try:
            os.makedirs(final_root_dest, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Gagal Membuat Folder", f"Tidak dapat membuat folder:\n{e}")
            return

        serial = self.selected_device.serial
        targets = self._get_active_targets(final_root_dest, serial)

        if not targets:
            messagebox.showwarning(
                "Tidak Ada Folder Dipilih",
                "Silakan centang minimal satu folder di atas (DCIM, Dokumen, Pictures, atau WhatsApp).",
            )
            return

        self.is_backing_up = True
        self.btn_start.config(state=tk.DISABLED, bg="#334155")
        self.btn_scan.config(state=tk.DISABLED)
        self.btn_cancel.config(state=tk.NORMAL)
        self.progress_val.set(0.0)
        self.status_detail_var.set("Menyiapkan sinkronisasi Auto-Skip...")

        self.stat_copied_var.set("0")
        self.stat_skipped_var.set("0")
        self.stat_target_var.set("Memulai...")

        self.log("=" * 60, "info")
        self.log(f"Memulai backup untuk: {self.selected_device.display_name}", "info")
        self.log(f"Folder tujuan: {final_root_dest}", "info")
        self.log("⚡ Fitur Smart Auto-Skip aktif: file identik (relative path & ukuran sama) akan otomatis dilewati.", "skip")

        self.worker_thread = threading.Thread(
            target=self._backup_worker,
            args=(serial, targets, final_root_dest),
            daemon=True,
        )
        self.worker_thread.start()

    def _backup_worker(self, serial: str, targets: list[tuple[str, str, str]], root_dest: str) -> None:
        start_time = time.time()
        preserve_timestamps = self.preserve_time_var.get()
        total_targets = len(targets)

        total_transferred = 0
        total_skipped = 0
        total_errors = 0

        stop_timer = threading.Event()

        def _timer_loop():
            while not stop_timer.is_set():
                elapsed = int(time.time() - start_time)
                m, s = divmod(elapsed, 60)
                self.after(0, lambda t=f"{m:02d}:{s:02d}": self.stat_time_var.set(t))
                time.sleep(1)

        threading.Thread(target=_timer_loop, daemon=True).start()

        for idx, (remote_p, local_target_dir, display_label) in enumerate(targets, start=1):
            if self.adb.is_cancelled():
                break

            os.makedirs(local_target_dir, exist_ok=True)

            self.after(0, lambda d=display_label: self.stat_target_var.set(d))
            self.after(0, lambda i=idx, t=total_targets, p=remote_p, d=local_target_dir: self.log(
                f"[{i}/{t}] Memeriksa: {p} -> {d}",
                "info",
            ))

            def _log_cb(msg: str, lvl: str):
                self.after(0, lambda m=msg, l=lvl: self.log(m, l))

            def _prog_cb(pct: float, detail: str, item_transferred: int, item_skipped: int):
                self.after(0, lambda: self._on_progress_update(
                    idx, total_targets, pct, detail,
                    total_transferred + item_transferred,
                    total_skipped + item_skipped
                ))

            try:
                transferred, skipped, errors = self.adb.smart_sync(
                    serial=serial,
                    remote_dir=remote_p,
                    local_dest=local_target_dir,
                    preserve_timestamps=preserve_timestamps,
                    log_callback=_log_cb,
                    progress_callback=_prog_cb,
                )
                total_transferred += transferred
                total_skipped += skipped
                total_errors += errors

                self.after(0, lambda c=total_transferred: self.stat_copied_var.set(f"{c:,}"))
                self.after(0, lambda s=total_skipped: self.stat_skipped_var.set(f"{s:,}"))

            except Exception as e:
                total_errors += 1
                _log_cb(f"Error memproses {remote_p}: {e}", "error")

        stop_timer.set()
        elapsed = time.time() - start_time
        m, s = divmod(int(elapsed), 60)
        time_str = f"{m} menit {s} detik" if m > 0 else f"{s} detik"

        self.after(0, lambda: self._on_backup_finished(
            total_transferred, total_skipped, total_errors, time_str, root_dest
        ))

    def _on_progress_update(
        self,
        target_idx: int,
        total_targets: int,
        item_pct: float,
        detail: str,
        current_copied: int,
        current_skipped: int,
    ) -> None:
        overall = ((target_idx - 1) + (item_pct / 100.0)) / total_targets * 100.0
        self.progress_val.set(overall)
        self.status_detail_var.set(f"[{overall:.1f}%] {detail}")
        self.stat_copied_var.set(f"{current_copied:,}")
        self.stat_skipped_var.set(f"{current_skipped:,}")

    def _on_backup_finished(
        self,
        transferred: int,
        skipped: int,
        errors: int,
        elapsed_str: str,
        dest_dir: str,
    ) -> None:
        self.is_backing_up = False
        self.btn_start.config(state=tk.NORMAL, bg="#0284c7")
        self.btn_scan.config(state=tk.NORMAL)
        self.btn_cancel.config(state=tk.DISABLED)
        self.stat_target_var.set("Selesai")

        was_cancelled = self.adb.is_cancelled()
        if was_cancelled:
            self.progress_val.set(0.0)
            self.status_detail_var.set("Backup dihentikan oleh pengguna.")
            self.log("Operasi backup telah dihentikan.", "warning")
            messagebox.showwarning("Backup Dibatalkan", "Proses backup telah dihentikan sebelum selesai.")
        else:
            self.progress_val.set(100.0)
            self.status_detail_var.set(f"Selesai! {transferred:,} disalin, {skipped:,} dilewati (identik).")

            self.log("=" * 60, "success")
            self.log(f"BACKUP SELESAI DALAM {elapsed_str}!", "success")
            self.log(f"Disalin baru: {transferred:,} file", "success")
            self.log(f"Dilewati otomatis (Auto-skip): {skipped:,} file", "skip")
            self.log(f"Folder hasil: {dest_dir}", "success")

            res = messagebox.askyesno(
                "Backup Selesai!",
                f"Proses backup telah selesai dalam {elapsed_str}!\n\n"
                f"• File baru disalin: {transferred:,}\n"
                f"• File identik dilewati (Auto-skip): {skipped:,}\n\n"
                f"Lokasi Harddisk:\n{dest_dir}\n\n"
                "Apakah Anda ingin membuka folder hasil backup sekarang?",
            )
            if res:
                self._open_destination_in_explorer()

    def cancel_backup(self) -> None:
        if not self.is_backing_up:
            return

        res = messagebox.askyesno(
            "Konfirmasi Pembatalan",
            "Apakah Anda yakin ingin menghentikan proses backup yang sedang berjalan?",
        )
        if res:
            self.status_detail_var.set("Menghentikan proses ADB...")
            self.log("Mengirim sinyal pembatalan...", "warning")
            self.adb.cancel_operation()


def launch_gui() -> None:
    app = ModernBackupApp()
    app.mainloop()
