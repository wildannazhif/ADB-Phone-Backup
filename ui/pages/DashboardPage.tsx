import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FolderOpen,
  FolderSearch,
  HardDrive,
  HardDriveDownload,
  Play,
  RefreshCw,
  ShieldAlert,
  Smartphone,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { formatBytes, formatCount, formatDuration, formatTimestamp } from "@/lib/utils";
import type { AppController } from "@/hooks/useAppController";
export function DashboardPage({ ctrl }: { ctrl: AppController }) {
  const {
    backendState,
    selectedDevice,
    overview,
    destDir,
    destInfo,
    setActivePage,
    openDestFolder,
    startBackup,
    refreshDevices,
    isRefreshingDevices,
  } = ctrl;

  const isDeviceReady = selectedDevice?.is_ready === true;
  const isUnauthorized = selectedDevice?.status === "unauthorized";
  const noDevices = backendState.devices.length === 0;

  return (
    <div className="space-y-5 p-6 pb-12">
      {/* 1. Unauthorized / Disconnected / Missing ADB Banner */}
      {!backendState.adb_available ? (
        <Alert variant="destructive">
          <ShieldAlert className="h-4 w-4 shrink-0 text-rose-500" />
          <div className="space-y-1">
            <div className="font-semibold">ADB executable tidak ditemukan</div>
            <p className="text-[11px] leading-relaxed text-[var(--text-secondary)]">
              {backendState.last_error ||
                "Pastikan platform-tools (adb.exe) terpasang di C:\\platform-tools atau atur path kustom di menu Settings."}
            </p>
          </div>
        </Alert>
      ) : isUnauthorized ? (
        <Alert variant="warning">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />
          <div className="space-y-1">
            <div className="font-semibold">Ponsel Terkunci — Izin USB Debugging Diperlukan</div>
            <p className="text-[11px] leading-relaxed text-[var(--text-secondary)]">
              Buka layar HP <strong>{selectedDevice?.display_name}</strong> dan ketuk{" "}
              <strong>"Izinkan USB Debugging"</strong> (centang 'Selalu izinkan dari komputer ini').
            </p>
          </div>
        </Alert>
      ) : noDevices ? (
        <Alert variant="info">
          <Smartphone className="h-4 w-4 shrink-0 text-sky-500" />
          <div className="space-y-1">
            <div className="font-semibold">Menunggu Koneksi Kabel USB Ponsel Android</div>
            <p className="text-[11px] leading-relaxed text-[var(--text-secondary)]">
              Sambungkan ponsel via kabel USB, pastikan opsi <strong>USB Debugging</strong> aktif di Opsi Pengembang (Developer Options).
            </p>
          </div>
        </Alert>
      ) : null}

      {/* 2. Top Grid: Device Connection Card & Backup Overview */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Device Connection Card */}
        <Card className="flex flex-col justify-between">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-md border border-sky-500/30 bg-sky-500/10 text-sky-500">
                  <Smartphone className="h-3.5 w-3.5" />
                </div>
                <CardTitle>Perangkat Terhubung</CardTitle>
              </div>
              {selectedDevice ? (
                <Badge
                  variant={
                    isDeviceReady
                      ? "success"
                      : isUnauthorized
                      ? "warning"
                      : "destructive"
                  }
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      isDeviceReady
                        ? "bg-emerald-500"
                        : isUnauthorized
                        ? "bg-amber-500"
                        : "bg-rose-500"
                    }`}
                  />
                  {isDeviceReady
                    ? "Terhubung & Siap"
                    : isUnauthorized
                    ? "Perlu Otorisasi"
                    : selectedDevice.status}
                </Badge>
              ) : (
                <Badge variant="secondary">Tidak Ada</Badge>
              )}
            </div>
            <CardDescription>
              Informasi perangkat Android yang aktif untuk operasi backup
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4 pt-1">
            {selectedDevice ? (
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2.5">
                  <div className="text-[11px] text-[var(--text-muted)]">Model Ponsel</div>
                  <div className="font-medium text-[var(--text-primary)] truncate">
                    {selectedDevice.model || "Unknown Model"}
                  </div>
                </div>

                <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2.5">
                  <div className="text-[11px] text-[var(--text-muted)]">Versi Android</div>
                  <div className="font-medium text-[var(--text-primary)]">
                    {selectedDevice.android_version || "Android"}
                  </div>
                </div>

                <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2.5">
                  <div className="text-[11px] text-[var(--text-muted)]">Nomor Serial USB</div>
                  <div className="font-mono text-[11px] text-[var(--text-primary)] truncate">
                    {selectedDevice.serial}
                  </div>
                </div>

                <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2.5">
                  <div className="text-[11px] text-[var(--text-muted)]">Status Baterai & Storage</div>
                  <div className="font-medium text-[var(--text-primary)] truncate">
                    {selectedDevice.battery_level !== null ? `🔋 ${selectedDevice.battery_level}%` : "—"}
                    {selectedDevice.storage_free ? ` · Sisa ${selectedDevice.storage_free}` : ""}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-6 text-center text-xs text-[var(--text-muted)]">
                <Smartphone className="mb-2 h-8 w-8 text-slate-500 opacity-60" />
                <p>Belum ada perangkat yang terdeteksi via ADB.</p>
                <p className="text-[11px] mt-1">Colok kabel USB dan ketuk "Refresh".</p>
              </div>
            )}

            <div className="flex items-center justify-between border-t border-[var(--border-subtle)] pt-3">
              <Button
                variant="outline"
                size="sm"
                onClick={refreshDevices}
                disabled={isRefreshingDevices}
              >
                <RefreshCw className={`h-3 w-3 ${isRefreshingDevices ? "animate-spin" : ""}`} />
                <span>Pindai Ulang Perangkat</span>
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setActivePage("browser")}
                disabled={!isDeviceReady}
              >
                <FolderSearch className="h-3.5 w-3.5" />
                <span>Jelajahi File HP</span>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Backup Overview Card */}
        <Card className="flex flex-col justify-between">
          <CardHeader>
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-500">
                <HardDrive className="h-3.5 w-3.5" />
              </div>
              <CardTitle>Ringkasan Backup</CardTitle>
            </div>
            <CardDescription>
              Riwayat dan kapasitas ruang penyimpanan di komputer / harddisk eksternal
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4 pt-1">
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2.5">
                <div className="text-[11px] text-[var(--text-muted)]">Terakhir Backup</div>
                <div className="font-medium text-[var(--text-primary)]">
                  {formatTimestamp(overview.last_backup_date)}
                </div>
              </div>

              <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2.5">
                <div className="text-[11px] text-[var(--text-muted)]">Total File Tersimpan</div>
                <div className="font-semibold text-emerald-600 dark:text-emerald-400">
                  {formatCount(overview.total_backup_files)} file
                </div>
              </div>

              <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2.5">
                <div className="text-[11px] text-[var(--text-muted)]">Total Ukuran Backup</div>
                <div className="font-semibold text-sky-600 dark:text-sky-400">
                  {formatBytes(overview.total_backup_bytes)}
                </div>
              </div>

              <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2.5">
                <div className="text-[11px] text-[var(--text-muted)]">Sesi Berhasil</div>
                <div className="font-medium text-[var(--text-primary)]">
                  {overview.total_sessions_count} sesi
                </div>
              </div>
            </div>

            {/* Destination folder status */}
            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-[var(--text-muted)]">Folder Tujuan Saat Ini:</span>
                {destInfo?.valid && (
                  <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                    {destInfo.free_bytes !== undefined ? `Sisa ${formatBytes(destInfo.free_bytes)}` : ""}
                  </span>
                )}
              </div>
              <div className="font-mono text-xs text-[var(--text-primary)] truncate mt-1">
                {destDir || overview.default_backup_dir || "Belum dipilih (atur di menu Backup)"}
              </div>
            </div>

            <div className="flex items-center justify-between border-t border-[var(--border-subtle)] pt-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => openDestFolder()}
                disabled={!destDir && !overview.default_backup_dir}
              >
                <FolderOpen className="h-3.5 w-3.5" />
                <span>Buka Folder Hasil</span>
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={() => setActivePage("backup")}
              >
                <HardDriveDownload className="h-3.5 w-3.5" />
                <span>Buka Halaman Backup</span>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 3. Quick Actions Banner */}
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-4 p-4">
          <div className="space-y-0.5">
            <div className="text-xs font-semibold text-[var(--text-primary)]">
              Aksi Cepat
            </div>
            <div className="text-[11px] text-[var(--text-secondary)]">
              Mulai backup otomatis dengan Smart Auto-Skip atau jelajahi file ponsel
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="default"
              onClick={() => {
                if (destDir && isDeviceReady) {
                  setActivePage("backup");
                  void startBackup();
                } else {
                  setActivePage("backup");
                }
              }}
              disabled={!isDeviceReady}
            >
              <Play className="h-3.5 w-3.5 fill-current" />
              <span>Mulai Backup Sekarang</span>
            </Button>
            <Button
              variant="outline"
              onClick={() => setActivePage("browser")}
              disabled={!isDeviceReady}
            >
              <FolderSearch className="h-3.5 w-3.5" />
              <span>Jelajahi File Android</span>
            </Button>
            <Button
              variant="outline"
              onClick={() => openDestFolder()}
              disabled={!destDir && !overview.default_backup_dir}
            >
              <FolderOpen className="h-3.5 w-3.5" />
              <span>Buka Folder Backup</span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 4. Recent Activity (Actual SQLite sessions only) */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-[var(--text-muted)]" />
              <CardTitle>Aktivitas Backup Terakhir</CardTitle>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setActivePage("history")}
            >
              Lihat Semua Riwayat
            </Button>
          </div>
          <CardDescription>
            Catatan sesi backup aktual yang tersimpan di database lokal
          </CardDescription>
        </CardHeader>

        <CardContent className="pt-0">
          {overview.recent_sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center text-xs text-[var(--text-muted)]">
              <Clock className="mb-2 h-7 w-7 text-slate-500 opacity-60" />
              <p>Belum ada riwayat backup yang tercatat.</p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Jalankan backup pertama untuk melihat catatan aktivitas di sini.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[var(--border-subtle)] text-[11px] text-[var(--text-muted)]">
                    <th className="pb-2 font-medium">Tanggal</th>
                    <th className="pb-2 font-medium">Perangkat</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">Disalin</th>
                    <th className="pb-2 font-medium">Dilewati (Skip)</th>
                    <th className="pb-2 font-medium">Ukuran</th>
                    <th className="pb-2 font-medium">Durasi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]">
                  {overview.recent_sessions.map((sess) => (
                    <tr key={sess.id} className="hover:bg-[var(--bg-elevated)]/50 transition-colors">
                      <td className="py-2.5 font-mono text-[11px] text-[var(--text-primary)]">
                        {formatTimestamp(sess.started_at)}
                      </td>
                      <td className="py-2.5">
                        <span className="font-medium text-[var(--text-primary)]">
                          {sess.device_model}
                        </span>
                      </td>
                      <td className="py-2.5">
                        <Badge
                          variant={
                            sess.status === "completed"
                              ? "success"
                              : sess.status === "completed_with_errors"
                              ? "warning"
                              : sess.status === "cancelled"
                              ? "secondary"
                              : "destructive"
                          }
                        >
                          {sess.status === "completed" ? (
                            <>
                              <CheckCircle2 className="h-3 w-3" />
                              <span>Selesai</span>
                            </>
                          ) : sess.status === "completed_with_errors" ? (
                            <span>Ada Error</span>
                          ) : sess.status === "cancelled" ? (
                            <span>Dibatalkan</span>
                          ) : (
                            <span>Gagal</span>
                          )}
                        </Badge>
                      </td>
                      <td className="py-2.5 font-semibold text-emerald-600 dark:text-emerald-400">
                        {sess.files_transferred.toLocaleString()}
                      </td>
                      <td className="py-2.5 text-violet-600 dark:text-violet-400">
                        {sess.files_skipped.toLocaleString()}
                      </td>
                      <td className="py-2.5 text-[var(--text-secondary)] font-mono text-[11px]">
                        {formatBytes(sess.bytes_transferred)}
                      </td>
                      <td className="py-2.5 text-[var(--text-muted)] font-mono text-[11px]">
                        {formatDuration(sess.duration_seconds)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
