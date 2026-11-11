import { useCallback, useEffect, useState } from "react";
import {
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FolderOpen,
  History,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/tauri";
import { formatBytes, formatCount, formatDuration, formatTimestamp } from "@/lib/utils";
import type { AppController } from "@/hooks/useAppController";
import type { BackupSessionRecord, TargetSummaryItem } from "@/types/backend";

export function HistoryPage({ ctrl }: { ctrl: AppController }) {
  const { openDestFolder, refreshOverview } = ctrl;
  const [sessions, setSessions] = useState<BackupSessionRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  const loadHistory = useCallback(async () => {
    setIsLoading(true);
    try {
      const records = await api.listBackupHistory(100, 0);
      setSessions(records);
    } catch (err) {
      console.error("Failed to load backup history:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const handleClear = async () => {
    await api.clearBackupHistory();
    setConfirmClear(false);
    await loadHistory();
    await refreshOverview();
  };

  const totalTransferred = sessions.reduce((acc, s) => acc + s.files_transferred, 0);
  const totalSkipped = sessions.reduce((acc, s) => acc + s.files_skipped, 0);
  const totalBytes = sessions.reduce((acc, s) => acc + s.bytes_transferred, 0);

  return (
    <div className="space-y-5 p-6 pb-12">
      {/* Top summary strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
          <div className="text-[11px] text-[var(--text-muted)]">Total Sesi Tercatat</div>
          <div className="mt-1 text-base font-semibold text-[var(--text-primary)]">
            {sessions.length} sesi
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
          <div className="text-[11px] text-[var(--text-muted)]">Total File Disalin Baru</div>
          <div className="mt-1 text-base font-semibold text-emerald-500">
            {formatCount(totalTransferred)} file
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
          <div className="text-[11px] text-[var(--text-muted)]">Total File Dilewati (Auto-Skip)</div>
          <div className="mt-1 text-base font-semibold text-violet-500">
            {formatCount(totalSkipped)} file
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
          <div className="text-[11px] text-[var(--text-muted)]">Volume Data Tersimpan</div>
          <div className="mt-1 font-mono text-base font-semibold text-sky-500">
            {formatBytes(totalBytes)}
          </div>
        </div>
      </div>

      {/* Main Table Card */}
      <Card>
        <CardHeader className="flex-row items-center justify-between pb-3">
          <div>
            <CardTitle>Riwayat Sesi Backup</CardTitle>
            <CardDescription>
              Semua catatan riwayat diambil langsung dari database SQLite lokal
            </CardDescription>
          </div>
          {sessions.length > 0 && (
            confirmClear ? (
              <div className="flex items-center gap-2 rounded-lg border border-rose-500/40 bg-rose-500/10 px-2 py-1">
                <span className="text-xs text-rose-500">Hapus riwayat?</span>
                <Button variant="destructive" size="sm" onClick={handleClear}>
                  Ya, Bersihkan
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setConfirmClear(false)}>
                  Batal
                </Button>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmClear(true)}
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Bersihkan Riwayat</span>
              </Button>
            )
          )}
        </CardHeader>

        <CardContent className="pt-0">
          {isLoading ? (
            <div className="py-12 text-center text-xs text-[var(--text-muted)]">
              Memuat data riwayat...
            </div>
          ) : sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-xs text-[var(--text-muted)]">
              <History className="mb-2.5 h-8 w-8 text-slate-500 opacity-60" />
              <p>Belum ada riwayat backup yang tercatat di database lokal.</p>
              <p className="mt-1 text-[11px]">
                Jalankan backup untuk melihat log sesi otomatis tersimpan di sini.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-[var(--border-subtle)]">
              {sessions.map((sess) => {
                const isExpanded = expandedId === sess.id;
                let targetsSummary: TargetSummaryItem[] = [];
                try {
                  const parsed = JSON.parse(sess.targets_json);
                  if (Array.isArray(parsed)) targetsSummary = parsed;
                } catch {
                  // ignore JSON parse
                }

                return (
                  <div key={sess.id} className="py-3 space-y-2">
                    <div
                      onClick={() => setExpandedId(isExpanded ? null : sess.id)}
                      className="flex flex-wrap items-center justify-between gap-3 cursor-pointer hover:bg-[var(--bg-elevated)]/40 p-2 rounded-lg transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          className="text-[var(--text-muted)]"
                          aria-label="Toggle details"
                        >
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </button>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-xs text-[var(--text-primary)]">
                              {sess.device_model || "Android Device"}
                            </span>
                            <span className="font-mono text-[10px] text-[var(--text-muted)]">
                              ({sess.device_serial})
                            </span>
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
                                <span className="flex items-center gap-1">
                                  <CheckCircle2 className="h-3 w-3" /> Selesai
                                </span>
                              ) : sess.status === "completed_with_errors" ? (
                                "Ada Error"
                              ) : sess.status === "cancelled" ? (
                                "Dibatalkan"
                              ) : (
                                "Gagal"
                              )}
                            </Badge>
                          </div>
                          <div className="mt-0.5 flex items-center gap-3 text-[11px] text-[var(--text-muted)]">
                            <span className="flex items-center gap-1">
                              <Calendar className="h-3 w-3" />
                              {formatTimestamp(sess.started_at)}
                            </span>
                            <span>Durasi: {formatDuration(sess.duration_seconds)}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 text-xs font-mono">
                        <span className="text-emerald-500 font-medium">
                          +{sess.files_transferred.toLocaleString()} baru
                        </span>
                        <span className="text-violet-400">
                          {sess.files_skipped.toLocaleString()} skip
                        </span>
                        <span className="text-slate-400">
                          {formatBytes(sess.bytes_transferred)}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            void openDestFolder(sess.dest_dir);
                          }}
                          title="Buka Folder di Windows Explorer"
                        >
                          <FolderOpen className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>

                    {/* Expanded details */}
                    {isExpanded && (
                      <div className="ml-7 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs space-y-2">
                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 text-[11px]">
                          <div>
                            <span className="text-[var(--text-muted)]">Lokasi Tujuan: </span>
                            <span className="font-mono text-[var(--text-primary)]">
                              {sess.dest_dir}
                            </span>
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {sess.smart_auto_skip && (
                              <Badge variant="secondary">Smart Auto-Skip</Badge>
                            )}
                            {sess.preserve_timestamps && (
                              <Badge variant="secondary">Preserve Timestamps (-a)</Badge>
                            )}
                            {sess.auto_subfolder && (
                              <Badge variant="secondary">Subfolder Tanggal</Badge>
                            )}
                          </div>
                        </div>

                        {sess.error_message && (
                          <div className="text-[11px] text-rose-500 font-mono">
                            Error: {sess.error_message}
                          </div>
                        )}

                        {targetsSummary.length > 0 && (
                          <div className="border-t border-[var(--border-subtle)] pt-2 space-y-1">
                            <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">
                              Rincian Target Folder:
                            </div>
                            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                              {targetsSummary.map((ts, i) => (
                                <div
                                  key={i}
                                  className="flex items-center justify-between rounded bg-[var(--bg-card)] px-2.5 py-1 text-[11px]"
                                >
                                  <span className="font-medium text-[var(--text-primary)]">
                                    {ts.label}
                                  </span>
                                  <span className="font-mono text-[10px] text-[var(--text-muted)]">
                                    {ts.transferred} disalin · {ts.skipped} skip
                                    {ts.errors > 0 ? ` · ${ts.errors} gagal` : ""}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
