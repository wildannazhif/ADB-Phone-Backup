# 📱 ADB Phone Backup Pro — Modern Desktop Edition

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=flat&logo=windows)](https://github.com/wildannazhif/ADB-Phone-Backup)
[![Framework](https://img.shields.io/badge/Framework-Tauri%202-24C8DB?style=flat&logo=tauri)](https://v2.tauri.app/)
[![Frontend](https://img.shields.io/badge/Frontend-React%2019%20%7C%20TypeScript%20%7C%20Tailwind%20CSS-38BDF8?style=flat&logo=react)](https://react.dev/)
[![Core Engine](https://img.shields.io/badge/Core%20Engine-Python%203%20AdbManager-3776AB?style=flat&logo=python)](https://python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Aplikasi desktop Windows modern, ultra-ringan, dan berkinerja tinggi untuk mencadangkan foto, video, dokumen, dan media WhatsApp dari ponsel Android langsung ke PC atau Harddisk eksternal via USB ADB.

Antarmuka desktop dibangun menggunakan **Tauri 2 + Rust + React + TypeScript + Tailwind CSS**, sementara **seluruh mesin dan logika backup Python asli (`AdbManager`) dipertahankan 100% tanpa mengubah algoritma sinkronisasi.**

---

## 🏗️ Arsitektur Sistem

```
┌────────────────────────────────────────────────────────────────────────┐
│                        REACT FRONTEND (Vite + TS)                      │
│   Dashboard · Backup · File Browser · Backup History · Settings Pages  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Tauri Commands & Events
┌───────────────────────────────────▼────────────────────────────────────┐
│                        RUST APPLICATION LAYER                          │
│   Process Lifecycle · Window Mgmt · SQLite DB · Stdio NDJSON Router    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Managed stdin/stdout JSON-RPC
┌───────────────────────────────────▼────────────────────────────────────┐
│                        PYTHON BACKEND WORKER                           │
│   src/ipc_worker.py · adb track-devices · Telemetry & Log Dispatch     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ AdbManager (Preserved Core)
┌───────────────────────────────────▼────────────────────────────────────┐
│                        ADB EXECUTABLE & DAEMON                         │
│   find -printf fast scan · smart_sync Auto-Skip · adb pull -a          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ USB Debugging Cable
┌───────────────────────────────────▼────────────────────────────────────┐
│                        ANDROID MOBILE DEVICE                           │
│   /sdcard/DCIM · Documents · Pictures · WhatsApp Media · Custom Folders│
└────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Fitur Utama & Keunggulan

### 1. Mesin Backup Python Terpercaya (Preserved 100%)
- 🔄 **Smart Auto-Skip Presisi**: Membandingkan **relative path dan ukuran file identik secara eksak** sebelum menyalin. File yang sudah lengkap di harddisk langsung dilewati (0 detik).
- 📁 **Dukungan Penuh `.nomedia`**: File `.nomedia` tetap dicadangkan dan dicocokkan sesuai subfoldernya masing-masing tanpa konflik.
- 🕒 **Preserve Timestamps (`adb pull -a`)**: Tanggal asli pemotretan foto dan video kamera tetap utuh sesuai waktu aslinya.
- 💬 **Target WhatsApp Media Bersih**: Khusus mengambil *WhatsApp Images*, *WhatsApp Video*, dan *WhatsApp Documents*, otomatis mengabaikan audio/voice notes/stiker sampah.
- 🔍 **Pre-Scan Status Cek File**: Memindai berapa ribu file yang sudah ada di harddisk dan berapa file baru sebelum proses backup dieksekusi.

### 2. Antarmuka Desktop Modern (Tauri 2 + React + Tailwind)
- 🎨 **Desain Obsidian / Slate Dark-First**: Estetika minimalis terinspirasi Linear & Raycast dengan kartu berdensitas informasi tinggi dan mode gelap/terang.
- 🚀 **Performa Tinggi & RAM Sangat Rendah**: Menggunakan WebView2 Windows bawaan tanpa overhead Electron, konsumsi memori hemat (< 45 MB).
- 🔌 **Deteksi Ponsel Event-Driven**: Memanfaatkan protokol streaming `adb track-devices` langsung ke ADB daemon, mendeteksi koneksi/diskoneksi USB secara instan **tanpa polling berulang yang membebani CPU**.
- 📂 **Android File Browser Interaktif**: Menjelajahi folder ponsel dengan breadcrumb, indikator ukuran file, penanganan direktori tak terakses (*Permission Denied*), paginasi dinamis, dan tombol langsung *"Pilih Folder Ini Untuk Backup"*.
- 💾 **Gauge Kapasitas Harddisk Real-Time**: Bar visual persentase dan sisa ruang bebas harddisk tujuan.
- 📊 **Telemetri & Log Langsung**: Indikator file disalin, file dilewati, file gagal, kecepatan transfer terukur (*MB/s*), estimasi waktu sisa (*ETA*), dan konsol log aktivitas real-time.
- 📜 **Riwayat Backup SQLite Terverifikasi**: Menyimpan catatan riwayat sesi backup secara lokal dan akurat tanpa fabrikasi data.

---

## 📁 Struktur Direktori Repository

```text
ADB-Phone-Backup/
├── .github/
│   └── workflows/
│       └── build.yml               # CI/CD pengujian Python & kompilasi installer Windows
├── assets/
│   ├── icon.ico                    # Windows icon multi-resolusi
│   └── icon.png                    # Ikon aplikasi PNG master
├── dist/
│   └── ADB-Phone-Backup.exe        # Binary standalone PyInstaller legacy
├── scripts/
│   └── prepare_bundle.py           # Skrip staging runtime Python embeddable & ADB platform-tools
├── src/                            # Mesin Python (Source of Truth)
│   ├── __init__.py
│   ├── adb_manager.py              # Engine ADB, fast scanner, auto-skip logic
│   ├── browser_dialog.py           # Dialog jelajah folder legacy Tkinter
│   ├── gui.py                      # UI Tkinter legacy (tetap dapat dijalankan)
│   ├── ipc_worker.py               # Worker stdin/stdout NDJSON IPC untuk Tauri
│   ├── main.py                     # Entry point package
│   └── target_resolver.py          # Resolver folder target & subfolder tanggal
├── src-tauri/                      # Backend Tauri 2 (Rust)
│   ├── Cargo.toml                  # Dependensi Rust (Tauri 2, SQLite bundled, plugins)
│   ├── build.rs                    # Skrip build Tauri
│   ├── tauri.conf.json             # Konfigurasi aplikasi desktop Tauri 2
│   ├── capabilities/
│   │   └── default.json            # Desktop permissions & capabilities
│   ├── icons/                      # Ikon aplikasi desktop multi-ukuran
│   └── src/
│       ├── commands.rs             # Tauri command invocations untuk frontend
│       ├── db.rs                   # Database SQLite lokal (settings, history, logs)
│       ├── lib.rs                  # Lifecycle app & plugin registration
│       ├── main.rs                 # Windows entrypoint
│       └── python_bridge.rs        # Managed child process supervisor & IPC channel
├── tests/
│   └── test_backend.py             # Unit & integration test suite Python/IPC
├── ui/                             # Frontend Desktop (React + TypeScript)
│   ├── components/                 # Komponen UI (Sidebar, TopBar, shadcn/ui primitives)
│   ├── hooks/                      # useAppController hook sentral & state management
│   ├── lib/                        # Tauri API client & format utilities
│   ├── pages/
│   │   ├── DashboardPage.tsx       # Status perangkat, ringkasan, quick action, riwayat singkat
│   │   ├── BackupPage.tsx          # Target folder, opsi Auto-Skip, telemetri, log langsung
│   │   ├── FileBrowserPage.tsx     # Penjelajah file Android, breadcrumbs, paginasi
│   │   ├── HistoryPage.tsx         # Riwayat sesi backup SQLite terperinci
│   │   └── SettingsPage.tsx        # Tema, path ADB kustom, manajemen log, diagnostik
│   ├── styles/                     # Tailwind CSS v4 styling & color tokens
│   ├── types/                      # TypeScript definitions untuk IPC & DB
│   ├── App.tsx                     # Layout utama
│   └── main.tsx                    # React DOM root
├── index.html                      # Entry HTML Vite
├── package.json                    # Dependensi frontend & scripts
├── tsconfig.json                   # Konfigurasi TypeScript
├── vite.config.ts                  # Konfigurasi Vite bundler
├── requirements.txt                # Dependensi Python
├── build_exe.py                    # Builder PyInstaller legacy
├── run.py                          # Launcher legacy Tkinter
└── README.md                       # Dokumentasi
```

---

## 🛠️ Panduan Pengembangan Lokal

### Prasyarat
1. **Node.js** 20+ & **npm**
2. **Rust** (stable toolchain)
3. **Python** 3.10+
4. **Android Platform Tools (ADB)** (misal di `C:\platform-tools`)

### 1. Menjalankan Frontend & Backend Python dalam Mode Dev
```bash
# 1. Masuk ke folder proyek
cd ADB-Phone-Backup

# 2. Pasang dependensi frontend
npm install

# 3. Jalankan pengujian Python untuk memastikan backend sehat
python -m pytest tests/test_backend.py -v

# 4. Jalankan aplikasi desktop dalam mode development
npm run tauri dev
```

---

## 📦 Membangun Installer Standalone Windows

Aplikasi dapat dikompilasi menjadi installer mandiri (`.exe` NSIS / `.msi`) yang mengemas runtime Python embeddable dan biner ADB sehingga **pengguna akhir tidak perlu memasang Python atau Node.js**.

```bash
# 1. Siapkan aset dan stage runtime mandiri
python scripts/prepare_bundle.py --platform-tools C:\platform-tools

# 2. Bangun frontend production
npm run build

# 3. Kompilasi Tauri installer
npx tauri build
```

Installer mandiri yang siap didistribusikan akan otomatis dihasilkan di folder:
`src-tauri/target/release/bundle/nsis/`

---

## 📱 Panduan Penggunaan Singkat

1. **Aktifkan USB Debugging di HP Android**:
   - Buka **Pengaturan** > **Tentang Ponsel** > Ketuk **Nomor Bentukan** 7 kali.
   - Buka **Opsi Pengembang** > Aktifkan **Debugging USB**.
   - Colokkan kabel USB ke PC dan ketuk **"Izinkan USB Debugging"** pada layar HP.
2. **Buka Aplikasi ADB Phone Backup**:
   - Status ponsel akan langsung terdeteksi hijau pada bagian atas.
3. **Tentukan Folder Harddisk Tujuan**:
   - Pada halaman **Backup**, pilih folder di harddisk eksternal atau PC Anda.
4. **Pilih Folder & Mulai Backup**:
   - Pilih folder (DCIM, Dokumen, Pictures, WhatsApp) atau tambah folder kustom.
   - Klik **"Cek Status File"** untuk melihat perbandingan file sebelum menyalin.
   - Klik **"Mulai Backup"**. File yang identik otomatis dilewati secara kilat via **Smart Auto-Skip**!

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah [MIT License](LICENSE) - © 2026 Wildan Nazhif.
