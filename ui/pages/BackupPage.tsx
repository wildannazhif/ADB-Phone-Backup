import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  FileText,
  Folder,
  FolderOpen,
  FolderSearch,
  HardDrive,
  Image as ImageIcon,
  MessageSquare,
  Play,
  Plus,
  ScanSearch,
  Square,
  Terminal,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import { Alert } from "@/components/ui/alert";
import type { AppController } from "@/hooks/useAppController";
import {
  cn,
  formatBytes,
  formatCount,
  formatDuration,
  formatEta,
  formatSpeed,
} from "@/lib/utils";

export function BackupPage({ ctrl }: { ctrl: AppController }) {
  const {
    selectedDevice,
    destDir,
    setDestDir,
    destInfo,
    chooseDestDirectory,
    openDestFolder,
    targets,
    setTargets,
    autoSubfolder,
    setAutoSubfolder,
    preserveTimestamps,
    setPreserveTimestamps,
    smartAutoSkip,
    setSmartAutoSkip,
    isBackingUp,
    isCancelling,
    backupProgress,
    backupCompleted,
    backupError,
    logs,
    clearLiveLogs,
    prescan,
    runPrescan,
    startBackup,
    cancelBackup,
    setActivePage,
  } = ctrl;

  const [autoScrollLogs, setAutoScrollLogs] = useState(true);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [newCustomInput, setNewCustomInput] = useState("");
  const logEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (autoScrollLogs && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "auto" });
    }
  }, [logs, autoScrollLogs]);

  useEffect(() => {
    if (!isBackingUp) {
      setConfirmCancel(false);
    }
  }, [isBackingUp]);

  const isDeviceReady = selectedDevice?.is_ready === true;
  const hasAnyTarget =
    targets.dcim ||
    targets.documents ||
    targets.pictures ||
    targets.whatsapp ||
    (targets.custom_enabled &&
      (targets.custom_path.trim().length > 0 || targets.custom_paths.length > 0));

  const canRun = isDeviceReady && destDir.trim().length > 0 && hasAnyTarget && !isBackingUp && !prescan.running;

  const addCustomFolder = () => {
    const clean = newCustomInput.trim();
    if (!clean) return;
    setTargets((prev) => ({
      ...prev,
      custom_enabled: true,
      custom_path: prev.custom_path || clean,
      custom_paths: prev.custom_paths.includes(clean)
        ? prev.custom_paths
        : [...prev.custom_paths, clean],
    }));
    setNewCustomInput("");
  };

  const removeCustomFolder = (pathToRemove: string) => {
    setTargets((prev) => {
      const nextPaths = prev.custom_paths.filter((p) => p !== pathToRemove);
      return {
        ...prev,
        custom_paths: nextPaths,
        custom_path: prev.custom_path === pathToRemove ? (nextPaths[0] ?? "") : prev.custom_path,
      };
    });
  };

  const coreCards = [
    {
      key: "dcim" as const,
      title: "DCIM",
      subtitle: "Camera & Videos",
      path: "/sdcard/DCIM",
      icon: Camera,
      accent: "text-sky-500 border-sky-500/40 bg-sky-500/8",
    },
    {
      key: "documents" as const,
      title: "Dokumen",
      subtitle: "PDF, Office & Files",
      path: "/sdcard/Documents",
      icon: FileText,
      accent: "text-teal-500 border-teal-500/40 bg-teal-500/8",
    },
    {
      key: "pictures" as const,
      title: "Pictures",
      subtitle: "Screenshots & Gallery",
      path: "/sdcard/Pictures",
      icon: ImageIcon,
      accent: "text-violet-500 border-violet-500/40 bg-violet-500/8",
    },
    {
      key: "whatsapp" as const,
      title: "WhatsApp",
      subtitle: "Images, Video & Docs",
      path: "Auto-detect media",
      icon: MessageSquare,
      accent: "text-emerald-500 border-emerald-500/40 bg-emerald-500/8",
    },
  ];

  const overallPercent = isBackingUp
    ? backupProgress?.overall_percent ?? 0
    : backupCompleted?.status === "completed" || backupCompleted?.status === "completed_with_errors"
    ? 100
    : 0;

  return (
    <div className="space-y-5 p-6 pb-12">
      {/* Errors or Completion Alerts */}
      {backupError && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4 shrink-0 text-rose-500" />
          <div className="text-xs">
            <span className="font-semibold">Error Backup: </span>
            {backupError}
          </div>
        </Alert>
      )}

      {backupCompleted && !isBackingUp && (
        <Alert
          variant={
            backupCompleted.status === "completed"
              ? "success"
              : backupCompleted.status === "cancelled"
              ? "warning"
              : "destructive"
          }
        >
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <div className="flex flex-1 flex-wrap items-center justify-between gap-3">
            <div className="space-y-0.5">
              <div className="font-semibold">
                {backupCompleted.status === "completed"
                  ? `Backup Selesai dalam ${formatDuration(backupCompleted.duration_seconds)}`
                  : backupCompleted.status === "completed_with_errors"
                  ? `Backup Selesai dengan ${backupCompleted.files_failed} kegagalan`
                  : backupCompleted.status === "cancelled"
                  ? "Backup Dibatalkan Pengguna"
                  : "Backup Gagal"}
              </div>
              <div className="text-[11px] opacity-90">
                {formatCount(backupCompleted.files_transferred)} disalin baru ·{" "}
                {formatCount(backupCompleted.files_skipped)} dilewati (Auto-Skip) ·{" "}
                {formatBytes(backupCompleted.bytes_transferred)}
              </div>
            </div>
            {backupCompleted.dest_dir && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => openDestFolder(backupCompleted.dest_dir)}
              >
                <FolderOpen className="h-3.5 w-3.5" />
                <span>Buka Folder Hasil</span>
              </Button>
            )}
          </div>
        </Alert>
      )}

      {/* 1. Source Folder Selection */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Folder Sumber di HP Android</CardTitle>
              <CardDescription>
                Pilih kategori folder utama atau tambahkan folder kustom dari ponsel
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setActivePage("browser")}
              disabled={!isDeviceReady || isBackingUp}
            >
              <FolderSearch className="h-3.5 w-3.5" />
              <span>Jelajahi HP...</span>
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {coreCards.map((c) => {
              const Icon = c.icon;
              const checked = targets[c.key];
              return (
                <button
                  key={c.key}
                  type="button"
                  disabled={isBackingUp}
                  onClick={() =>
                    setTargets((prev) => ({ ...prev, [c.key]: !prev[c.key] }))
                  }
                  className={cn(
                    "flex flex-col items-start gap-2 rounded-xl border p-3.5 text-left transition-colors duration-150 cursor-pointer disabled:opacity-60",
                    checked
                      ? "border-sky-500/45 bg-sky-500/6"
                      : "border-[var(--border-subtle)] bg-[var(--bg-elevated)]/50 hover:border-[var(--border-strong)]"
                  )}
                >
                  <div className="flex w-full items-center justify-between">
                    <div
                      className={cn(
                        "flex h-7 w-7 items-center justify-center rounded-lg border",
                        checked
                          ? c.accent
                          : "border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-muted)]"
                      )}
                    >
                      <Icon className="h-3.5 w-3.5" />
                    </div>
                    <input
                      type="checkbox"
                      checked={checked}
                      readOnly
                      className="h-3.5 w-3.5 accent-sky-500 pointer-events-none"
                    />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-[var(--text-primary)]">
                      {c.title}
                    </div>
                    <div className="text-[11px] text-[var(--text-secondary)]">
                      {c.subtitle}
                    </div>
                    <div className="mt-1 font-mono text-[10px] text-[var(--text-muted)]">
                      {c.path}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Custom Folder Row */}
          <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)]/40 p-3 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Switch
                  checked={targets.custom_enabled}
                  onCheckedChange={(v) =>
                    setTargets((prev) => ({ ...prev, custom_enabled: v }))
                  }
                  disabled={isBackingUp}
                  aria-label="Enable custom Android folder"
                />
                <span className="text-xs font-medium text-[var(--text-primary)]">
                  Folder Kustom Tambahan
                </span>
              </div>
              <span className="text-[11px] text-[var(--text-muted)]">
                Contoh: /sdcard/Download
              </span>
            </div>

            {targets.custom_enabled && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Input
                    value={targets.custom_path}
                    disabled={isBackingUp}
                    onChange={(e) =>
                      setTargets((prev) => ({ ...prev, custom_path: e.target.value }))
                    }
                    placeholder="/sdcard/Download"
                    className="font-mono"
                  />
                  <Input
                    value={newCustomInput}
                    disabled={isBackingUp}
                    onChange={(e) => setNewCustomInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") addCustomFolder();
                    }}
                    placeholder="Tambah path lain lalu tekan +"
                    className="font-mono max-w-60"
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={addCustomFolder}
                    disabled={isBackingUp || !newCustomInput.trim()}
                    title="Tambah folder kustom"
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                </div>

                {targets.custom_paths.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {targets.custom_paths.map((cp) => (
                      <Badge key={cp} variant="secondary" className="gap-1.5 py-0.5 font-mono text-[10px]">
                        <Folder className="h-3 w-3 text-sky-500" />
                        <span>{cp}</span>
                        {!isBackingUp && (
                          <button
                            type="button"
                            onClick={() => removeCustomFolder(cp)}
                            className="hover:text-rose-500 cursor-pointer"
                            aria-label={`Remove ${cp}`}
                          >
                            <X className="h-3 w-3" />
                          </button>
                        )}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 2. Destination & Options */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <Card className="lg:col-span-7">
          <CardHeader className="pb-3">
            <CardTitle>Folder / Harddisk Tujuan</CardTitle>
            <CardDescription>
              Pilih lokasi penyimpanan di PC atau harddisk eksternal
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <Input
                value={destDir}
                disabled={isBackingUp}
                onChange={(e) => setDestDir(e.target.value)}
                placeholder="Contoh: D:\Backup_HP"
                className="font-mono"
              />
              <Button
                variant="secondary"
                onClick={chooseDestDirectory}
                disabled={isBackingUp}
              >
                <FolderOpen className="h-3.5 w-3.5" />
                <span>Pilih Folder</span>
              </Button>
              <Button
                variant="outline"
                size="icon"
                onClick={() => openDestFolder()}
                disabled={!destDir.trim()}
                title="Buka di Windows Explorer"
              >
                <Folder className="h-3.5 w-3.5" />
              </Button>
            </div>

            {destInfo?.valid ? (
              <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)]/60 p-3 space-y-2">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="flex items-center gap-1.5 font-medium text-[var(--text-primary)]">
                    <HardDrive className="h-3.5 w-3.5 text-emerald-500" />
                    <span>Drive {destInfo.drive}</span>
                  </span>
                  <span className="text-[var(--text-secondary)]">
                    <strong className="text-emerald-600 dark:text-emerald-400">
                      {formatBytes(destInfo.free_bytes)} bebas
                    </strong>{" "}
                    dari {formatBytes(destInfo.total_bytes)} ({destInfo.used_percent}% terpakai)
                  </span>
                </div>
                <Progress
                  value={destInfo.used_percent ?? 0}
                  indicatorClassName={
                    (destInfo.used_percent ?? 0) > 90
                      ? "bg-rose-500"
                      : (destInfo.used_percent ?? 0) > 75
                      ? "bg-amber-500"
                      : "bg-emerald-500"
                  }
                />
              </div>
            ) : destDir.trim() ? (
              <div className="text-[11px] text-rose-500">
                {destInfo?.error || "Path tujuan belum valid"}
              </div>
            ) : (
              <div className="text-[11px] text-[var(--text-muted)]">
                Pilih folder harddisk tujuan untuk memeriksa ruang penyimpanan tersedia.
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-5">
          <CardHeader className="pb-3">
            <CardTitle>Opsi Backup</CardTitle>
            <CardDescription>
              Pengaturan kompatibilitas dan sinkronisasi presisi
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-1.5 text-xs font-medium text-[var(--text-primary)]">
                  <Zap className="h-3.5 w-3.5 text-violet-500" />
                  <span>Smart Auto-Skip</span>
                </div>
                <p className="text-[11px] text-[var(--text-muted)]">
                  Lewati file identik (relative path & ukuran sama, termasuk .nomedia)
                </p>
              </div>
              <Switch
                checked={smartAutoSkip}
                onCheckedChange={setSmartAutoSkip}
                disabled={isBackingUp}
              />
            </div>

            <div className="flex items-center justify-between gap-3 border-t border-[var(--border-subtle)] pt-2.5">
              <div>
                <div className="text-xs font-medium text-[var(--text-primary)]">
                  Pertahankan Tanggal Asli Foto (-a)
                </div>
                <p className="text-[11px] text-[var(--text-muted)]">
                  Gunakan adb pull -a agar timestamp file asli terjaga
                </p>
              </div>
              <Switch
                checked={preserveTimestamps}
                onCheckedChange={setPreserveTimestamps}
                disabled={isBackingUp}
              />
            </div>

            <div className="flex items-center justify-between gap-3 border-t border-[var(--border-subtle)] pt-2.5">
              <div>
                <div className="text-xs font-medium text-[var(--text-primary)]">
                  Buat Subfolder Tanggal
                </div>
                <p className="text-[11px] text-[var(--text-muted)]">
                  Nonaktifkan agar file backup lama otomatis dilewati
                </p>
              </div>
              <Switch
                checked={autoSubfolder}
                onCheckedChange={setAutoSubfolder}
                disabled={isBackingUp}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 3. Action Bar & Pre-Scan Report */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            size="lg"
            onClick={startBackup}
            disabled={!canRun}
          >
            <Play className="h-4 w-4 fill-current" />
            <span>{isBackingUp ? "Backup Berjalan..." : "Mulai Backup"}</span>
          </Button>

          <Button
            variant="secondary"
            size="lg"
            onClick={runPrescan}
            disabled={!canRun}
          >
            <ScanSearch className="h-4 w-4" />
            <span>
              {prescan.running
                ? `Scanning (${prescan.progressIndex}/${prescan.progressTotal})...`
                : "Cek Status File (Pre-Scan)"}
            </span>
          </Button>

          {isBackingUp && (
            confirmCancel ? (
              <div className="flex items-center gap-2 rounded-lg border border-rose-500/40 bg-rose-500/10 px-2.5 py-1">
                <span className="text-xs font-medium text-rose-500">Hentikan backup?</span>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={cancelBackup}
                  disabled={isCancelling}
                >
                  {isCancelling ? "Menghentikan..." : "Ya, Batalkan"}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setConfirmCancel(false)}
                >
                  Lanjutkan
                </Button>
              </div>
            ) : (
              <Button
                variant="destructive"
                size="lg"
                onClick={() => setConfirmCancel(true)}
                disabled={isCancelling}
              >
                <Square className="h-3.5 w-3.5 fill-current" />
                <span>Batalkan Backup</span>
              </Button>
            )
          )}
        </div>

        {!isDeviceReady && (
          <span className="text-xs text-amber-500">
            Hubungkan ponsel Android yang terotorisasi untuk memulai backup.
          </span>
        )}
      </div>

      {/* Pre-Scan Result Breakdown */}
      {prescan.result && !prescan.running && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle>Hasil Pemeriksaan File (Pre-Scan)</CardTitle>
              <Badge variant="default">
                {formatCount(prescan.result.total_new)} file baru ({formatBytes(prescan.result.total_new_bytes)})
              </Badge>
            </div>
            <CardDescription>
              Total di HP: {formatCount(prescan.result.total_on_phone)} · Sudah ada di disk:{" "}
              {formatCount(prescan.result.total_already_on_disk)} (Auto-Skip)
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-1">
            {prescan.result.error ? (
              <div className="text-xs text-rose-500">{prescan.result.error}</div>
            ) : (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {prescan.result.targets.map((t) => (
                  <div
                    key={t.remote_path}
                    className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)]/60 p-2.5 text-xs"
                  >
                    <div className="font-medium text-[var(--text-primary)]">{t.label}</div>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
                      <span>Di HP: {t.on_phone.toLocaleString()}</span>
                      <span className="text-violet-500">Skip: {t.already_on_disk.toLocaleString()}</span>
                      <span className="font-semibold text-emerald-500">
                        Baru: {t.new_files.toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* 4. Live Progress Telemetry */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CardTitle>Progres & Telemetri Transfer</CardTitle>
              {isBackingUp && (
                <Badge variant="default">
                  {backupProgress?.phase === "scanning"
                    ? "Memindai HP"
                    : "Menyalin File"}
                </Badge>
              )}
            </div>
            <span className="font-mono text-xs font-semibold text-sky-500">
              {overallPercent.toFixed(1)}%
            </span>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Progress value={overallPercent} />
            <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
              <span className="truncate font-mono">
                {backupProgress?.current_file
                  ? `[${backupProgress.target_index}/${backupProgress.total_targets}] ${backupProgress.target_label}: ${backupProgress.current_file}`
                  : isBackingUp
                  ? `Memeriksa ${backupProgress?.target_label || "folder target"}...`
                  : backupCompleted
                  ? `Status akhir: ${backupCompleted.status}`
                  : "Siap untuk memulai backup."}
              </span>
              {backupProgress && backupProgress.bytes_total_to_pull > 0 && (
                <span className="shrink-0 font-mono">
                  {formatBytes(backupProgress.bytes_transferred)} / {formatBytes(backupProgress.bytes_total_to_pull)}
                </span>
              )}
            </div>
          </div>

          {/* Real Measured Counters */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)]/60 p-2.5">
              <div className="text-[10px] text-[var(--text-muted)]">Disalin Baru</div>
              <div className="text-sm font-semibold text-emerald-500">
                {formatCount(
                  isBackingUp
                    ? backupProgress?.files_completed ?? 0
                    : backupCompleted?.files_transferred ?? 0
                )}
              </div>
            </div>

            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)]/60 p-2.5">
              <div className="text-[10px] text-[var(--text-muted)]">Dilewati (Skip)</div>
              <div className="text-sm font-semibold text-violet-500">
                {formatCount(
                  isBackingUp
                    ? backupProgress?.files_skipped ?? 0
                    : backupCompleted?.files_skipped ?? 0
                )}
              </div>
            </div>

            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)]/60 p-2.5">
              <div className="text-[10px] text-[var(--text-muted)]">Gagal</div>
              <div className="text-sm font-semibold text-rose-500">
                {formatCount(
                  isBackingUp
                    ? backupProgress?.files_failed ?? 0
                    : backupCompleted?.files_failed ?? 0
                )}
              </div>
            </div>

            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)]/60 p-2.5">
              <div className="text-[10px] text-[var(--text-muted)]">Kecepatan</div>
              <div className="text-sm font-semibold text-sky-500 font-mono">
                {isBackingUp ? formatSpeed(backupProgress?.speed_bps) : "—"}
              </div>
            </div>

            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)]/60 p-2.5">
              <div className="text-[10px] text-[var(--text-muted)]">Estimasi Sisa</div>
              <div className="text-sm font-semibold text-[var(--text-primary)] font-mono">
                {isBackingUp ? formatEta(backupProgress?.eta_seconds) : "—"}
              </div>
            </div>

            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)]/60 p-2.5">
              <div className="text-[10px] text-[var(--text-muted)]">Waktu Berjalan</div>
              <div className="text-sm font-semibold text-amber-500 font-mono">
                {formatDuration(
                  isBackingUp
                    ? backupProgress?.elapsed_seconds ?? 0
                    : backupCompleted?.duration_seconds ?? 0
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 5. Live Activity Logs */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-[var(--text-muted)]" />
              <CardTitle>Log Aktivitas Langsung</CardTitle>
              <span className="text-[11px] text-[var(--text-muted)]">
                ({logs.length} baris)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1.5 text-[11px] text-[var(--text-secondary)] cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoScrollLogs}
                  onChange={(e) => setAutoScrollLogs(e.target.checked)}
                  className="accent-sky-500"
                />
                Auto-scroll
              </label>
              <Button variant="ghost" size="sm" onClick={clearLiveLogs}>
                <Trash2 className="h-3.5 w-3.5" />
                <span>Bersihkan</span>
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-56 overflow-y-auto rounded-lg border border-[var(--border-subtle)] bg-[#06080d] p-3 font-mono text-[11px] leading-relaxed selectable">
            {logs.length === 0 ? (
              <div className="text-slate-500">
                Menunggu aktivitas backup atau pre-scan...
              </div>
            ) : (
              logs.map((entry, idx) => (
                <div key={idx} className="flex gap-2">
                  <span className="shrink-0 text-slate-500">{entry.timestamp}</span>
                  <span
                    className={cn(
                      "shrink-0 uppercase font-semibold",
                      entry.level === "skip"
                        ? "text-violet-400"
                        : entry.level === "success"
                        ? "text-emerald-400"
                        : entry.level === "warning"
                        ? "text-amber-400"
                        : entry.level === "error"
                        ? "text-rose-400"
                        : entry.level === "detail"
                        ? "text-slate-400"
                        : "text-sky-400"
                    )}
                  >
                    [{entry.level}]
                  </span>
                  <span className="text-slate-200 break-all">{entry.message}</span>
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
