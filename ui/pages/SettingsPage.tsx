import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Cpu,
  Download,
  FolderOpen,
  Palette,
  RefreshCw,
  Save,
  Search,
  Settings,
  ShieldCheck,
  Terminal,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Alert } from "@/components/ui/alert";
import { api } from "@/lib/tauri";
import type { AppController } from "@/hooks/useAppController";
import type { AppSettings, ThemeMode } from "@/types/backend";

export function SettingsPage({ ctrl }: { ctrl: AppController }) {
  const {
    settings,
    saveSettings,
    backendState,
    appInfo,
    restartPythonBackend,
  } = ctrl;

  const [form, setForm] = useState<AppSettings>(settings);
  const [logCount, setLogCount] = useState<number>(0);
  const [isSaved, setIsSaved] = useState<boolean>(false);
  const [adbTestResult, setAdbTestResult] = useState<string | null>(null);
  const [isTestingAdb, setIsTestingAdb] = useState<boolean>(false);
  const [isRestarting, setIsRestarting] = useState<boolean>(false);

  useEffect(() => {
    setForm(settings);
  }, [settings]);

  useEffect(() => {
    void api.getLogInfo().then((res) => setLogCount(res.total_count)).catch(() => {});
  }, []);

  const handleSave = async () => {
    await saveSettings(form);
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2000);
  };

  const handlePickDefaultDir = async () => {
    const chosen = await api.pickFolder(form.default_backup_dir || undefined);
    if (chosen) {
      setForm((prev) => ({ ...prev, default_backup_dir: chosen }));
    }
  };

  const handlePickCustomAdb = async () => {
    const chosen = await api.pickAdbExecutable(form.custom_adb_path || undefined);
    if (chosen) {
      setForm((prev) => ({ ...prev, custom_adb_path: chosen }));
      await api.setAdbPath(chosen);
    }
  };

  const handleTestAdb = async () => {
    setIsTestingAdb(true);
    setAdbTestResult(null);
    try {
      const res = await api.getAdbStatus();
      if (res.adb_available) {
        setAdbTestResult(`ADB OK: ${res.adb_version || "Tersedia"} (${res.adb_path})`);
      } else {
        setAdbTestResult(`Gagal: ${res.error || "adb.exe tidak ditemukan"}`);
      }
    } catch (err) {
      setAdbTestResult(`Error: ${String(err)}`);
    } finally {
      setIsTestingAdb(false);
    }
  };

  const handleExportLogs = async () => {
    const targetFile = await api.pickLogSavePath();
    if (!targetFile) return;
    try {
      const count = await api.exportLogs(targetFile);
      alert(`Berhasil mengekspor ${count} catatan log ke:\n${targetFile}`);
    } catch (err) {
      alert(`Gagal mengekspor log: ${err}`);
    }
  };

  const handleClearLogs = async () => {
    if (confirm("Hapus semua catatan log yang tersimpan di database lokal?")) {
      await api.clearLogs();
      setLogCount(0);
    }
  };

  const handleRestartBackend = async () => {
    setIsRestarting(true);
    try {
      await restartPythonBackend();
    } finally {
      setIsRestarting(false);
    }
  };

  return (
    <div className="space-y-5 p-6 pb-12 max-w-4xl">
      {isSaved && (
        <Alert variant="success">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>Pengaturan berhasil disimpan ke database SQLite lokal.</span>
        </Alert>
      )}

      {/* 1. Appearance */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Palette className="h-4 w-4 text-sky-500" />
            <CardTitle>Tampilan & Tema</CardTitle>
          </div>
          <CardDescription>
            Pilih preferensi tema visual antarmuka desktop
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            {(["dark", "light", "system"] as ThemeMode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setForm((p) => ({ ...p, theme: m }))}
                className={`rounded-xl border p-3 text-left transition-colors cursor-pointer ${
                  form.theme === m
                    ? "border-sky-500/60 bg-sky-500/10"
                    : "border-[var(--border-subtle)] bg-[var(--bg-elevated)]/50 hover:border-[var(--border-strong)]"
                }`}
              >
                <div className="text-xs font-semibold capitalize text-[var(--text-primary)]">
                  {m === "dark" ? "Dark Mode" : m === "light" ? "Light Mode" : "Ikuti Sistem"}
                </div>
                <div className="text-[10px] text-[var(--text-muted)] mt-0.5">
                  {m === "dark"
                    ? "Obsidian / Slate dark"
                    : m === "light"
                    ? "Clean light slate"
                    : "Otomatis Windows"}
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 2. Paths & ADB Configuration */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
            <CardTitle>Folder Default & Eksekutor ADB</CardTitle>
          </div>
          <CardDescription>
            Konfigurasi lokasi penyimpanan default dan executable adb.exe
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[var(--text-primary)]">
              Folder Harddisk Tujuan Default
            </label>
            <div className="flex items-center gap-2">
              <Input
                value={form.default_backup_dir}
                onChange={(e) =>
                  setForm((p) => ({ ...p, default_backup_dir: e.target.value }))
                }
                placeholder="Contoh: D:\Backup_HP"
                className="font-mono text-xs"
              />
              <Button variant="secondary" onClick={handlePickDefaultDir}>
                <FolderOpen className="h-3.5 w-3.5" />
                <span>Pilih</span>
              </Button>
            </div>
            <p className="text-[11px] text-[var(--text-muted)]">
              Folder ini akan otomatis terpilih setiap aplikasi dibuka.
            </p>
          </div>

          <div className="space-y-1.5 border-t border-[var(--border-subtle)] pt-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-[var(--text-primary)]">
                Biner ADB (Android Debug Bridge)
              </label>
              <Button
                variant="outline"
                size="sm"
                onClick={handleTestAdb}
                disabled={isTestingAdb}
              >
                <Search className="h-3 w-3" />
                <span>{isTestingAdb ? "Menguji..." : "Uji Koneksi ADB"}</span>
              </Button>
            </div>

            <div className="flex items-center gap-2">
              <Input
                value={form.custom_adb_path}
                onChange={(e) =>
                  setForm((p) => ({ ...p, custom_adb_path: e.target.value }))
                }
                placeholder="Kosongkan untuk auto-detect (C:\platform-tools\adb.exe)"
                className="font-mono text-xs"
              />
              <Button variant="secondary" onClick={handlePickCustomAdb}>
                Pilih adb.exe
              </Button>
            </div>

            <div className="flex items-center gap-2 text-[11px] text-[var(--text-secondary)] font-mono">
              <span>Aktif saat ini:</span>
              <span className="text-sky-500 font-semibold">
                {backendState.adb_path || "Belum ditemukan"}
              </span>
            </div>

            {adbTestResult && (
              <div
                className={`rounded-lg border p-2 text-xs font-mono ${
                  adbTestResult.startsWith("ADB OK")
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                    : "border-rose-500/30 bg-rose-500/10 text-rose-400"
                }`}
              >
                {adbTestResult}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 3. Default Backup Options */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Settings className="h-4 w-4 text-violet-500" />
            <CardTitle>Preferensi Default Operasi Backup</CardTitle>
          </div>
          <CardDescription>
            Nilai awal yang digunakan saat aplikasi dibuka
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs font-medium text-[var(--text-primary)]">
                Smart Auto-Skip Default Aktif
              </div>
              <div className="text-[11px] text-[var(--text-muted)]">
                Mencocokkan relative path dan ukuran file identik secara otomatis
              </div>
            </div>
            <Switch
              checked={form.smart_auto_skip}
              onCheckedChange={(v) => setForm((p) => ({ ...p, smart_auto_skip: v }))}
            />
          </div>

          <div className="flex items-center justify-between border-t border-[var(--border-subtle)] pt-2.5">
            <div>
              <div className="text-xs font-medium text-[var(--text-primary)]">
                Pertahankan Tanggal Asli Foto (-a)
              </div>
              <div className="text-[11px] text-[var(--text-muted)]">
                Menyimpan tanggal pengambilan foto asli komputer
              </div>
            </div>
            <Switch
              checked={form.preserve_timestamps}
              onCheckedChange={(v) => setForm((p) => ({ ...p, preserve_timestamps: v }))}
            />
          </div>

          <div className="flex items-center justify-between border-t border-[var(--border-subtle)] pt-2.5">
            <div>
              <div className="text-xs font-medium text-[var(--text-primary)]">
                Buka Folder Otomatis Setelah Selesai
              </div>
              <div className="text-[11px] text-[var(--text-muted)]">
                Membuka Windows Explorer langsung saat backup selesai 100%
              </div>
            </div>
            <Switch
              checked={form.auto_open_destination}
              onCheckedChange={(v) => setForm((p) => ({ ...p, auto_open_destination: v }))}
            />
          </div>
        </CardContent>
      </Card>

      {/* 4. Log Management */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-amber-500" />
            <CardTitle>Manajemen Log Aktivitas</CardTitle>
          </div>
          <CardDescription>
            Pengelolaan berkas catatan aktivitas backup yang tersimpan di PC
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs font-semibold text-[var(--text-primary)]">
              {logCount.toLocaleString()} Catatan Log di Database
            </div>
            <p className="text-[11px] text-[var(--text-muted)]">
              Ekspor catatan aktivitas ke berkas teks atau bersihkan basis data
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleExportLogs}>
              <Download className="h-3.5 w-3.5" />
              <span>Ekspor Log (.log)</span>
            </Button>
            <Button variant="outline" size="sm" onClick={handleClearLogs}>
              <Trash2 className="h-3.5 w-3.5" />
              <span>Bersihkan Log</span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 5. Diagnostic & App Info */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-sky-500" />
            <CardTitle>Informasi Sistem & Diagnostik</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-xs">
          <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
            <div className="rounded border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2">
              <span className="text-[var(--text-muted)]">Versi Aplikasi: </span>
              <span className="text-[var(--text-primary)]">v{appInfo?.version || "2.0.0"}</span>
            </div>
            <div className="rounded border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2">
              <span className="text-[var(--text-muted)]">Platform: </span>
              <span className="text-[var(--text-primary)]">{appInfo?.platform} ({appInfo?.arch})</span>
            </div>
            <div className="rounded border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2">
              <span className="text-[var(--text-muted)]">Backend Python: </span>
              <span className="text-[var(--text-primary)]">
                {backendState.python_version ? `Python ${backendState.python_version}` : "—"} (PID {backendState.pid || "—"})
              </span>
            </div>
            <div className="rounded border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2">
              <span className="text-[var(--text-muted)]">Status Bridge: </span>
              <span className={backendState.state === "ready" ? "text-emerald-500 font-semibold" : "text-amber-500"}>
                {backendState.state.toUpperCase()}
              </span>
            </div>
          </div>

          <div className="rounded border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2 font-mono text-[10px] text-[var(--text-muted)] truncate">
            Database: {appInfo?.db_path || "adb_backup.sqlite"}
          </div>

          <div className="flex items-center justify-between border-t border-[var(--border-subtle)] pt-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRestartBackend}
              disabled={isRestarting}
            >
              <RefreshCw className={`h-3 w-3 ${isRestarting ? "animate-spin" : ""}`} />
              <span>{isRestarting ? "Memulai Ulang..." : "Restart Backend Python"}</span>
            </Button>
            <Button size="default" onClick={handleSave}>
              <Save className="h-3.5 w-3.5" />
              <span>Simpan Perubahan</span>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
