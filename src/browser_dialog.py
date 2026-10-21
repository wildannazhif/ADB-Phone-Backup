"""
Remote Folder Browser dialog for browsing Android phone directories via ADB.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional
from .adb_manager import AdbManager


class AndroidBrowserDialog(tk.Toplevel):
    """Modal dialog allowing the user to browse folders directly on their Android phone."""

    def __init__(
        self,
        parent: tk.Tk,
        adb_manager: AdbManager,
        serial: str,
        initial_path: str = "/sdcard",
        on_select: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)
        self.adb = adb_manager
        self.serial = serial
        self.current_path = initial_path.rstrip("/") if initial_path else "/sdcard"
        if not self.current_path:
            self.current_path = "/sdcard"
        self.on_select = on_select

        self.title("Jelajahi Folder di HP Android")
        self.geometry("640x520")
        self.minsize(500, 400)
        self.configure(bg="#0f172a")

        # Make modal
        self.transient(parent)
        self.grab_set()

        self._setup_ui()
        self._load_current_directory()

    def _setup_ui(self) -> None:
        # Header / Navigation bar
        nav_frame = tk.Frame(self, bg="#1e293b", padx=12, pady=10)
        nav_frame.pack(fill=tk.X, side=tk.TOP)

        btn_up = tk.Button(
            nav_frame,
            text="⬆️ Folder Atas",
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._go_up,
        )
        btn_up.pack(side=tk.LEFT, padx=(0, 8))

        btn_sdcard = tk.Button(
            nav_frame,
            text="🏠 /sdcard",
            font=("Segoe UI", 9),
            bg="#334155",
            fg="#94a3b8",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=4,
            cursor="hand2",
            command=lambda: self._navigate_to("/sdcard"),
        )
        btn_sdcard.pack(side=tk.LEFT, padx=(0, 8))

        self.path_entry_var = tk.StringVar(value=self.current_path)
        self.path_entry = tk.Entry(
            nav_frame,
            textvariable=self.path_entry_var,
            font=("Segoe UI", 10),
            bg="#0f172a",
            fg="#38bdf8",
            insertbackground="#38bdf8",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#475569",
            highlightcolor="#38bdf8",
        )
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.path_entry.bind("<Return>", lambda e: self._navigate_to(self.path_entry_var.get()))

        btn_go = tk.Button(
            nav_frame,
            text="Buka",
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            cursor="hand2",
            command=lambda: self._navigate_to(self.path_entry_var.get()),
        )
        btn_go.pack(side=tk.LEFT)

        # List frame
        list_frame = tk.Frame(self, bg="#0f172a", padx=12, pady=10)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.tree = ttk.Treeview(
            list_frame,
            columns=("type", "name"),
            show="headings",
            yscrollcommand=scrollbar.set,
            selectmode="browse",
        )
        scrollbar.config(command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.heading("type", text="Tipe", anchor=tk.W)
        self.tree.heading("name", text="Nama Item (Dobel-klik folder untuk membuka)", anchor=tk.W)

        self.tree.column("type", width=80, stretch=False)
        self.tree.column("name", width=460, stretch=True)

        self.tree.bind("<Double-1>", self._on_double_click)

        # Footer Action Bar
        footer = tk.Frame(self, bg="#1e293b", padx=12, pady=12)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_status = tk.Label(
            footer,
            text="Pilih folder di atas, lalu klik 'Pilih Folder Ini'.",
            font=("Segoe UI", 9),
            bg="#1e293b",
            fg="#94a3b8",
        )
        self.lbl_status.pack(side=tk.LEFT)

        btn_select = tk.Button(
            footer,
            text="✅ Pilih Folder Ini",
            font=("Segoe UI", 10, "bold"),
            bg="#22c55e",
            fg="#ffffff",
            activebackground="#16a34a",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._commit_selection,
        )
        btn_select.pack(side=tk.RIGHT, padx=(8, 0))

        btn_cancel = tk.Button(
            footer,
            text="Batal",
            font=("Segoe UI", 9),
            bg="#475569",
            fg="#f8fafc",
            activebackground="#64748b",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.destroy,
        )
        btn_cancel.pack(side=tk.RIGHT)

    def _load_current_directory(self) -> None:
        self.lbl_status.config(text=f"Memuat {self.current_path}...", fg="#38bdf8")
        self.update_idletasks()

        for item in self.tree.get_children():
            self.tree.delete(item)

        dirs, files = self.adb.list_remote_directory(self.serial, self.current_path)

        for d in dirs:
            self.tree.insert("", tk.END, values=("📁 Folder", d), tags=("dir",))

        for f in files:
            self.tree.insert("", tk.END, values=("📄 File", f["name"]), tags=("file",))

        self.path_entry_var.set(self.current_path)
        self.lbl_status.config(
            text=f"Ditemukan {len(dirs)} folder, {len(files)} file di '{self.current_path}'",
            fg="#94a3b8",
        )

    def _navigate_to(self, new_path: str) -> None:
        clean = new_path.strip().rstrip("/")
        if not clean:
            clean = "/"
        self.current_path = clean
        self._load_current_directory()

    def _go_up(self) -> None:
        if self.current_path in ("/", ""):
            return
        parts = self.current_path.rstrip("/").rsplit("/", 1)
        parent = parts[0] if parts[0] else "/"
        self._navigate_to(parent)

    def _on_double_click(self, event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        itype, name = item["values"]
        if "Folder" in itype:
            new_path = f"{self.current_path}/{name}".replace("//", "/")
            self._navigate_to(new_path)

    def _commit_selection(self) -> None:
        sel = self.tree.selection()
        selected_path = self.current_path
        if sel:
            item = self.tree.item(sel[0])
            itype, name = item["values"]
            if "Folder" in itype:
                selected_path = f"{self.current_path}/{name}".replace("//", "/")

        if self.on_select:
            self.on_select(selected_path)
        self.destroy()
