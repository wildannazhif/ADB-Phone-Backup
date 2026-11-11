import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowUp,
  ChevronRight,
  Folder,
  FolderPlus,
  HardDriveDownload,
  Home,
  Loader2,
  RefreshCw,
  Search,
  Smartphone,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { api } from "@/lib/tauri";
import { cn, formatBytes } from "@/lib/utils";
import type { AppController } from "@/hooks/useAppController";
import type { BrowseDirectoryResult, RemoteEntry } from "@/types/backend";

export function FileBrowserPage({ ctrl }: { ctrl: AppController }) {
  const { selectedDevice, addCustomFolderFromBrowser, setActivePage } = ctrl;

  const [currentPath, setCurrentPath] = useState<string>("/sdcard");
  const [pathInput, setPathInput] = useState<string>("/sdcard");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [browseResult, setBrowseResult] = useState<BrowseDirectoryResult | null>(null);
  const [entries, setEntries] = useState<RemoteEntry[]>([]);
  const [offset, setOffset] = useState<number>(0);
  const [isLoadingMore, setIsLoadingMore] = useState<boolean>(false);

  const isDeviceReady = selectedDevice?.is_ready === true;
  const serial = selectedDevice?.serial || "";

  const loadDirectory = useCallback(
    async (targetPath: string, append = false, currentOffset = 0, query = "") => {
      if (!serial || !isDeviceReady) return;

      if (append) {
        setIsLoadingMore(true);
      } else {
        setIsLoading(true);
      }

      try {
        const res = await api.browseDirectory({
          serial,
          path: targetPath,
          offset: currentOffset,
          limit: 150,
          query,
        });

        setBrowseResult(res);
        if (append) {
          setEntries((prev) => [...prev, ...res.entries]);
        } else {
          setEntries(res.entries);
          setCurrentPath(res.path);
          setPathInput(res.path);
        }
        setOffset(res.offset + res.entries.length);
      } catch (err) {
        setBrowseResult({
          path: targetPath,
          accessible: false,
          error: String(err),
          entries: [],
          total_dirs: 0,
          total_files: 0,
          total_count: 0,
          offset: 0,
          limit: 150,
          has_more: false,
        });
      } finally {
        setIsLoading(false);
        setIsLoadingMore(false);
      }
    },
    [serial, isDeviceReady]
  );

  useEffect(() => {
    if (isDeviceReady) {
      void loadDirectory("/sdcard", false, 0, "");
    }
  }, [isDeviceReady, loadDirectory]);

  const handleNavigate = (newPath: string) => {
    setOffset(0);
    setSearchQuery("");
    void loadDirectory(newPath, false, 0, "");
  };

  const handleGoUp = () => {
    if (currentPath === "/" || !currentPath) return;
    const parts = currentPath.replace(/\/+$/, "").split("/");
    parts.pop();
    const parent = parts.join("/") || "/";
    handleNavigate(parent);
  };

  const handleLoadMore = () => {
    if (!browseResult?.has_more || isLoadingMore) return;
    void loadDirectory(currentPath, true, offset, searchQuery);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setOffset(0);
    void loadDirectory(currentPath, false, 0, searchQuery);
  };

  const breadcrumbs = currentPath === "/" ? ["/"] : currentPath.split("/").filter(Boolean);

  if (!isDeviceReady) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 text-center">
        <Smartphone className="mb-3 h-10 w-10 text-[var(--text-muted)] opacity-60" />
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Ponsel Belum Terhubung
        </h2>
        <p className="mt-1 max-w-sm text-xs text-[var(--text-secondary)]">
          Sambungkan ponsel Android via USB dan pastikan USB debugging terotorisasi untuk menjelajahi folder perangkat.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col space-y-4 p-6 pb-8">
      {/* Navigation Toolbar */}
      <Card className="shrink-0">
        <CardContent className="space-y-3 p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2.5">
            <div className="flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                onClick={handleGoUp}
                disabled={currentPath === "/" || isLoading}
                title="Folder Atas (Up)"
              >
                <ArrowUp className="h-3.5 w-3.5" />
                <span>Atas</span>
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => handleNavigate("/sdcard")}
                disabled={isLoading}
                title="Ke /sdcard (Penyimpanan Internal)"
              >
                <Home className="h-3.5 w-3.5" />
                <span>/sdcard</span>
              </Button>

              <Button
                variant="ghost"
                size="icon"
                onClick={() => loadDirectory(currentPath, false, 0, searchQuery)}
                disabled={isLoading}
                title="Refresh Folder"
              >
                <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
              </Button>
            </div>

            {/* Select current folder for backup action */}
            <div className="flex items-center gap-2">
              <Button
                variant="default"
                size="sm"
                onClick={() => {
                  addCustomFolderFromBrowser(currentPath);
                  setActivePage("backup");
                }}
                disabled={!browseResult?.accessible}
                title="Gunakan folder ini sebagai target backup tambahan"
              >
                <HardDriveDownload className="h-3.5 w-3.5" />
                <span>Pilih Folder Ini Untuk Backup</span>
              </Button>
            </div>
          </div>

          {/* Breadcrumb + Direct path input */}
          <div className="flex items-center gap-2">
            <div className="flex flex-1 items-center gap-1.5 overflow-x-auto rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)]/60 px-3 py-1 text-xs">
              <button
                type="button"
                onClick={() => handleNavigate("/")}
                className="font-mono text-[var(--text-muted)] hover:text-sky-500 cursor-pointer"
              >
                /
              </button>
              {breadcrumbs.map((segment, idx) => {
                const subPath = "/" + breadcrumbs.slice(0, idx + 1).join("/");
                const isLast = idx === breadcrumbs.length - 1;
                return (
                  <span key={subPath} className="flex items-center gap-1">
                    <ChevronRight className="h-3 w-3 text-slate-500" />
                    <button
                      type="button"
                      onClick={() => handleNavigate(subPath)}
                      className={cn(
                        "font-mono cursor-pointer transition-colors",
                        isLast
                          ? "font-semibold text-sky-500"
                          : "text-[var(--text-secondary)] hover:text-sky-400"
                      )}
                    >
                      {segment}
                    </button>
                  </span>
                );
              })}
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleNavigate(pathInput);
              }}
              className="flex items-center gap-1.5"
            >
              <Input
                value={pathInput}
                onChange={(e) => setPathInput(e.target.value)}
                placeholder="/sdcard"
                className="w-48 font-mono text-xs sm:w-64"
              />
              <Button type="submit" variant="secondary" size="sm">
                Buka
              </Button>
            </form>

            <form onSubmit={handleSearchSubmit} className="flex items-center gap-1.5">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-[var(--text-muted)]" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Cari file..."
                  className="w-36 pl-8 text-xs sm:w-44"
                />
              </div>
            </form>
          </div>
        </CardContent>
      </Card>

      {/* Directory Contents Card */}
      <Card className="flex flex-1 flex-col overflow-hidden">
        <CardHeader className="flex-row items-center justify-between py-3">
          <div>
            <CardTitle className="text-xs">
              Isi Direktori: <span className="font-mono text-sky-500">{currentPath}</span>
            </CardTitle>
            {browseResult?.accessible && (
              <CardDescription>
                Ditemukan {browseResult.total_dirs} folder, {browseResult.total_files} file (total {browseResult.total_count} item)
              </CardDescription>
            )}
          </div>
        </CardHeader>

        <CardContent className="flex-1 overflow-y-auto p-0">
          {browseResult?.accessible === false ? (
            <div className="p-6">
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4 shrink-0 text-rose-500" />
                <div className="space-y-1">
                  <div className="font-semibold">Direktori Tidak Dapat Diakses</div>
                  <p className="text-[11px] text-[var(--text-secondary)]">
                    {browseResult.error || "Akses ditolak (Permission denied) atau folder tidak ditemukan di sistem Android."}
                  </p>
                  <div className="pt-2">
                    <Button variant="outline" size="sm" onClick={handleGoUp}>
                      Kembali ke Folder Induk
                    </Button>
                  </div>
                </div>
              </Alert>
            </div>
          ) : isLoading ? (
            <div className="flex h-64 flex-col items-center justify-center text-xs text-[var(--text-muted)]">
              <Loader2 className="mb-2 h-6 w-6 animate-spin text-sky-500" />
              <span>Memuat daftar berkas di ponsel...</span>
            </div>
          ) : entries.length === 0 ? (
            <div className="flex h-64 flex-col items-center justify-center text-xs text-[var(--text-muted)]">
              <Folder className="mb-2 h-8 w-8 text-slate-500 opacity-60" />
              <span>Folder ini kosong.</span>
            </div>
          ) : (
            <div className="divide-y divide-[var(--border-subtle)] text-xs">
              <div className="sticky top-0 z-10 flex items-center bg-[var(--bg-card)] px-4 py-2 text-[11px] font-semibold text-[var(--text-muted)] border-b border-[var(--border-subtle)]">
                <span className="flex-1">Nama Item</span>
                <span className="w-24 text-right">Ukuran</span>
                <span className="w-32 text-right hidden sm:block">Diubah</span>
                <span className="w-36 text-right">Aksi</span>
              </div>

              {entries.map((entry) => {
                const isDir = entry.type === "dir";
                const isSymlink = entry.is_symlink;
                return (
                  <div
                    key={entry.path}
                    className="flex items-center px-4 py-2 hover:bg-[var(--bg-elevated)]/60 transition-colors"
                  >
                    <div
                      onClick={() => (isDir ? handleNavigate(entry.path) : null)}
                      className={cn(
                        "flex flex-1 items-center gap-2.5 truncate",
                        isDir && "cursor-pointer hover:text-sky-500"
                      )}
                    >
                      {isDir ? (
                        <Folder className="h-4 w-4 shrink-0 text-sky-500" />
                      ) : (
                        <span className="h-4 w-4 shrink-0 text-center text-xs text-[var(--text-muted)]">
                          📄
                        </span>
                      )}
                      <span className="truncate font-mono">{entry.name}</span>
                      {isSymlink && (
                        <Badge variant="secondary" className="text-[9px] py-0">
                          link
                        </Badge>
                      )}
                    </div>

                    <div className="w-24 text-right font-mono text-[11px] text-[var(--text-secondary)]">
                      {isDir ? "—" : formatBytes(entry.size)}
                    </div>

                    <div className="w-32 text-right font-mono text-[10px] text-[var(--text-muted)] hidden sm:block truncate">
                      {entry.modified || "—"}
                    </div>

                    <div className="w-36 text-right">
                      {isDir ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            addCustomFolderFromBrowser(entry.path);
                            setActivePage("backup");
                          }}
                          className="h-7 px-2 text-[11px]"
                          title="Tambahkan folder ini ke backup"
                        >
                          <FolderPlus className="h-3 w-3 text-sky-500" />
                          <span>+ Backup</span>
                        </Button>
                      ) : (
                        <span className="text-[10px] text-[var(--text-muted)]">File</span>
                      )}
                    </div>
                  </div>
                );
              })}

              {browseResult?.has_more && (
                <div className="p-3 text-center">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleLoadMore}
                    disabled={isLoadingMore}
                  >
                    {isLoadingMore ? (
                      <>
                        <Loader2 className="h-3 w-3 animate-spin" />
                        <span>Memuat...</span>
                      </>
                    ) : (
                      <span>
                        Muat Lebih Banyak ({entries.length} dari {browseResult.total_count})
                      </span>
                    )}
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
