import { Suspense, lazy } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useAppController } from "@/hooks/useAppController";
import { DashboardPage } from "@/pages/DashboardPage";
import { BackupPage } from "@/pages/BackupPage";

// Lazy load secondary tabs for fast initial startup
const FileBrowserPage = lazy(() =>
  import("@/pages/FileBrowserPage").then((m) => ({ default: m.FileBrowserPage }))
);
const HistoryPage = lazy(() =>
  import("@/pages/HistoryPage").then((m) => ({ default: m.HistoryPage }))
);
const SettingsPage = lazy(() =>
  import("@/pages/SettingsPage").then((m) => ({ default: m.SettingsPage }))
);

export function App() {
  const ctrl = useAppController();
  const {
    activePage,
    setActivePage,
    backendState,
    selectedDevice,
    selectedSerial,
    setSelectedSerial,
    refreshDevices,
    isRefreshingDevices,
    restartPythonBackend,
    isBackingUp,
    appInfo,
  } = ctrl;

  const isBackendCrashed =
    backendState.state === "crashed" || backendState.state === "stopped";

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        backendState={backendState}
        isBackingUp={isBackingUp}
        version={appInfo?.version || "2.0.0"}
      />

      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <TopBar
          activePage={activePage}
          backendState={backendState}
          selectedDevice={selectedDevice}
          selectedSerial={selectedSerial}
          onSelectSerial={setSelectedSerial}
          onRefreshDevices={refreshDevices}
          isRefreshing={isRefreshingDevices}
        />

        {isBackendCrashed && (
          <div className="px-6 pt-4 shrink-0">
            <Alert variant="destructive" className="items-center justify-between">
              <div className="flex items-start gap-2.5">
                <AlertTriangle className="h-4 w-4 shrink-0 text-rose-500 mt-0.5" />
                <div className="space-y-0.5">
                  <div className="font-semibold">
                    Backend Engine Python Terhenti Secara Tidak Terduga
                  </div>
                  <p className="text-[11px] opacity-90">
                    {backendState.stderr_tail.length > 0
                      ? backendState.stderr_tail[backendState.stderr_tail.length - 1]
                      : "Proses backend tidak aktif."}
                  </p>
                </div>
              </div>
              <Button variant="destructive" size="sm" onClick={restartPythonBackend}>
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Restart Backend</span>
              </Button>
            </Alert>
          </div>
        )}

        <main className="flex-1 overflow-y-auto">
          {activePage === "dashboard" && <DashboardPage ctrl={ctrl} />}
          {activePage === "backup" && <BackupPage ctrl={ctrl} />}
          {activePage !== "dashboard" && activePage !== "backup" && (
            <Suspense
              fallback={
                <div className="flex h-full items-center justify-center text-xs text-[var(--text-muted)]">
                  Memuat halaman...
                </div>
              }
            >
              {activePage === "browser" && <FileBrowserPage ctrl={ctrl} />}
              {activePage === "history" && <HistoryPage ctrl={ctrl} />}
              {activePage === "settings" && <SettingsPage ctrl={ctrl} />}
            </Suspense>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
