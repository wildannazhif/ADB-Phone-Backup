# 📱 ADB Phone Backup Pro

[![Windows](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=flat&logo=windows)](https://github.com/wildannazhif/ADB-Phone-Backup)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776AB?style=flat&logo=python)](https://github.com/wildannazhif/ADB-Phone-Backup)
[![Build Status](https://img.shields.io/badge/Build-Standalone%20.EXE-10B981?style=flat&logo=githubactions)](https://github.com/wildannazhif/ADB-Phone-Backup)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Aplikasi desktop Windows portabel, modern, dan ultra-ringan untuk backup otomatis foto, video, dokumen, dan media WhatsApp dari HP Android langsung ke Harddisk eksternal atau PC via USB ADB.

Aplikasi ini sudah dikompilasi menjadi **file tunggal `.exe` mandiri (standalone)** lengkap dengan biner ADB terintegrasi. **Tidak perlu install Python atau download platform-tools secara manual.**

---

```
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ ⚡ ADB PHONE BACKUP  [PRO EDITION]               [ 2412DPC0AG (Android 14) · 🔋 85% · 💾 45GB ] │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ 📁 FOLDER SUMBER DI HP (PILIH YANG INGIN DI-BACKUP)                                           │
│ ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐ ┌─────────────────────────┐ │
│ │ 📸 [v] DCIM       │ │ 📄 [v] Dokumen    │ │ 🖼️ [v] Pictures   │ │ 💬 [v] WhatsApp         │ │
│ │ Kamera & Foto     │ │ Berkas & PDF      │ │ Galeri & SS       │ │ Media Pilihan Saja      │ │
│ │ [KAMERA]          │ │ [DOKUMEN]         │ │ [GALERI]          │ │ [WHATSAPP MEDIA]        │ │
│ └───────────────────┘ └───────────────────┘ └───────────────────┘ └─────────────────────────┘ │
│                                                                                               │
│ 💾 FOLDER / HARDDISK TUJUAN                 [⚡ SMART AUTO-SKIP: PATH & UKURAN PRESISI]      │
│ [ D:\Backup_HP                                             ] [ 📂 Pilih Folder Harddisk...  ] │
│ 💾 Drive D:\ [45% Terpakai] — 420.5 GB Bebas dari 1.0 TB                                      │
│                                                                                               │
│ ┌───────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ 📥 Disalin Baru: 0  │  ⏭️ Dilewati: 23,449  │  📂 Target: Menunggu...  │  ⏱️ Waktu: 00:00   │ │
│ └───────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                               │
│ [ 🚀 MULAI BACKUP KE HARDDISK ]   [ 🔍 Cek Status File (Scan Dulu) ]   [ 📁 Buka Folder ]     │
│ [==================================== 100% =================================================] │
│                                                                                               │
│ 📋 LOG AKTIVITAS ADB & AUTO-SKIP                                                              │
│ > [AUTO-SKIP] 23,449 file WhatsApp di HP sudah lengkap di harddisk (Dilewati otomatis!)       │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 4 Target Utama Backup (Otomatis Tercentang)

1. 📸 **DCIM** (`/sdcard/DCIM`)
   - Semua foto dan rekaman video kamera utama.
2. 📄 **Dokumen** (`/sdcard/Documents`)
   - File dokumen PDF, Word, Excel, e-book, dan berkas kerja.
3. 🖼️ **Pictures** (`/sdcard/Pictures`)
   - Tangkapan layar (screenshots), foto unduhan aplikasi, dan galeri non-kamera.
4. 💬 **WhatsApp (Khusus Media Pilihan Saja)**:
   - ✅ **WhatsApp Documents**
   - ✅ **WhatsApp Images**
   - ✅ **WhatsApp Video**
   - 🚫 *Voice notes, audio sampah, stiker, dan wallpaper otomatis dilewati agar backup bersih dan hemat ruang.*

*(Tersedia opsi tambahan jika ingin menambah folder kustom lain melalui tombol **"Jelajahi HP..."**).*

---

## ⚡ Fitur Unggulan

- 🔄 **Smart Auto-Skip (Presisi Relative Path & Ukuran File)**:
  - Sebelum menyalin, sistem memindai file di HP dengan `find -printf '%s %p\n'` (mampu memindai 25.000+ file dalam 5 detik tanpa batas buffer).
  - File yang **sudah ada di harddisk dengan relative path dan ukuran identik langsung dilewati (0 detik)**.
  - File `.nomedia` tetap dicadangkan secara normal dan dicocokkan sesuai subfoldernya masing-masing tanpa tabrakan.
- 🎨 **UI Modern, Menarik & Ringan**:
  - Desain Dark Obsidian / Cyber-Slate modern dengan kartu interaktif dan hover glow.
  - Memori RAM < 35 MB, waktu buka seketika (*instant startup*).
- 🕒 **Preserve Timestamps (`adb pull -a`)**:
  - Tanggal asli foto dan video dipertahankan sama persis di komputer (tidak berubah menjadi tanggal hari ini).
- 💾 **Drive Free Space & Capacity Gauge**:
  - Menampilkan bar visual sisa kapasitas harddisk tujuan secara langsung.
- 🔍 **Tombol Pre-Scan "Cek Status File"**:
  - Periksa berapa ribu file yang sudah ada dan berapa file baru sebelum proses backup dimulai.
- 📊 **Live HUD Telemetry**:
  - Menampilkan jumlah file disalin baru, file yang dilewati (*auto-skip*), folder aktif, durasi waktu, dan log aktivitas real-time.

---

## 🚀 Cara Pakai

1. **Aktifkan USB Debugging di HP**:
   - Buka **Pengaturan** > **Tentang Ponsel** > Ketuk **Nomor Bentukan** 7 kali.
   - Buka **Opsi Pengembang** > Aktifkan **Debugging USB**.
   - Colok kabel USB ke komputer dan ketuk **"Izinkan USB Debugging"** di layar HP.
2. **Buka Aplikasi**:
   - Dobel-klik file:
     ```text
     dist/ADB-Phone-Backup.exe
     ```
3. **Pilih Harddisk Tujuan**:
   - Klik **"📂 Pilih Folder Harddisk..."** dan arahkan ke folder di harddisk eksternal Anda.
4. **Klik "🚀 MULAI BACKUP KE HARDDISK"**:
   - Aplikasi akan langsung berjalan. File yang sudah pernah di-backup otomatis dilewati kilat!

---

## 🛠️ Struktur Repository

```text
ADB-Phone-Backup/
├── .github/
│   └── workflows/
│       └── build.yml        # CI/CD otomatis kompilasi .exe Windows
├── assets/
│   ├── icon.ico             # Ikon resolusi tinggi Windows
│   └── icon.png             # Ikon aplikasi PNG
├── dist/
│   └── ADB-Phone-Backup.exe # Binary standalone siap pakai (~12.8 MB)
├── src/
│   ├── __init__.py
│   ├── adb_manager.py       # Engine ADB, fast scanner, auto-skip logic
│   ├── browser_dialog.py    # Dialog jelajah folder HP Android
│   ├── gui.py               # Modern UI Tkinter & threading
│   └── main.py              # Entry point package
├── build_exe.py             # Script build otomatis PyInstaller
├── run.py                   # Root launcher
├── requirements.txt         # Dependensi Python
├── LICENSE                  # Lisensi MIT
└── README.md                # Dokumentasi lengkap
```

---

## 🔨 Cara Build dari Source Code

Jika ingin memodifikasi kode sumber dan membangun ulang file `.exe`:

```bash
# 1. Clone repository
git clone https://github.com/wildannazhif/ADB-Phone-Backup.git
cd ADB-Phone-Backup

# 2. Install dependensi
pip install -r requirements.txt

# 3. Jalankan build PyInstaller
python build_exe.py
```

File `.exe` baru akan otomatis dihasilkan di `dist/ADB-Phone-Backup.exe`.

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah [MIT License](LICENSE) - © 2026 Wildan Nazhif.
