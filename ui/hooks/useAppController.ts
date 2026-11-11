import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, isTauriRuntime } from "@/lib/tauri";
import type {
  AppInfo,
  AppSettings,
  BackendStateSnapshot,
  BackupCompletedEvent,
  BackupLogEvent,
  BackupProgressEvent,
  BackupTargetsConfig,
  DashboardOverview,
  DestinationInspectResult,
  DeviceInfo,
  DeviceStatusPayload,
  NavPage,
  PrescanCompletedEvent,
  PrescanTargetItem,
} from "@/types/backend";

const DEFAULT_SETTINGS: AppSettings = {
  theme: "dark",
  default_backup_dir: "",
  custom_adb_path: "",
  auto_subfolder: false,
  preserve_timestamps: true,
  smart_auto_skip: true,
  default_dcim: true,
  default_documents: true,
  default_pictures: true,
  default_whatsapp: true,
  custom_folders: [],
  max_log_lines: 2000,
  auto_open_destination: false,
};

export interface PrescanState {
  running: boolean;
  progressLabel: string;
  progressIndex: number;
  progressTotal: number;
  result: PrescanCompletedEvent | null;
}

export interface AppController {
  activePage: NavPage;
  setActivePage: (page: NavPage) => void;
  backendState: BackendStateSnapshot;
  settings: AppSettings;
  saveSettings: (next: AppSettings) => Promise<AppSettings>;
  appInfo: AppInfo | null;
  overview: DashboardOverview;
  refreshOverview: () => Promise<void>;
  selectedDevice: DeviceInfo | null;
  selectedSerial: string;
  setSelectedSerial: React.Dispatch<React.SetStateAction<string>>;
  isRefreshingDevices: boolean;
  refreshDevices: () => Promise<void>;
  restartPythonBackend: () => Promise<void>;
  destDir: string;
  setDestDir: React.Dispatch<React.SetStateAction<string>>;
  destInfo: DestinationInspectResult | null;
  chooseDestDirectory: () => Promise<string | null>;
  openDestFolder: (overridePath?: string) => Promise<void>;
  targets: BackupTargetsConfig;
  setTargets: React.Dispatch<React.SetStateAction<BackupTargetsConfig>>;
  autoSubfolder: boolean;
  setAutoSubfolder: React.Dispatch<React.SetStateAction<boolean>>;
  preserveTimestamps: boolean;
  setPreserveTimestamps: React.Dispatch<React.SetStateAction<boolean>>;
  smartAutoSkip: boolean;
  setSmartAutoSkip: React.Dispatch<React.SetStateAction<boolean>>;
  isBackingUp: boolean;
  isCancelling: boolean;
  backupProgress: BackupProgressEvent | null;
  backupCompleted: BackupCompletedEvent | null;
  backupError: string | null;
  setBackupError: React.Dispatch<React.SetStateAction<string | null>>;
  logs: BackupLogEvent[];
  clearLiveLogs: () => void;
  prescan: PrescanState;
  prescanSummary: PrescanTargetItem[];
  runPrescan: () => Promise<void>;
  startBackup: () => Promise<void>;
  cancelBackup: () => Promise<void>;
  addCustomFolderFromBrowser: (remotePath: string) => void;
}

export function useAppController(): AppController {
  const [activePage, setActivePage] = useState<NavPage>("dashboard");
  const [backendState, setBackendState] = useState<BackendStateSnapshot>({
    state: "starting",
    pid: null,
    python_version: null,
    python_path: null,
    backend_script: null,
    adb_available: false,
    adb_path: null,
    adb_version: null,
    custom_adb_path: "",
    devices: [],
    active_job_id: null,
    last_error: null,
    stderr_tail: [],
  });

  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null);
  const [overview, setOverview] = useState<DashboardOverview>({
    last_backup_date: null,
    total_backup_files: 0,
    total_backup_bytes: 0,
    default_backup_dir: "",
    recent_sessions: [],
    total_sessions_count: 0,
  });

  const [selectedSerial, setSelectedSerial] = useState<string>("");
  const [isRefreshingDevices, setIsRefreshingDevices] = useState(false);

  // Backup configuration state (persisted across tab navigation)
  const [destDir, setDestDir] = useState<string>("");
  const [destInfo, setDestInfo] = useState<DestinationInspectResult | null>(null);
  const [targets, setTargets] = useState<BackupTargetsConfig>({
    dcim: true,
    documents: true,
    pictures: true,
    whatsapp: true,
    custom_enabled: false,
    custom_path: "/sdcard/Download",
    custom_paths: [],
  });
  const [autoSubfolder, setAutoSubfolder] = useState<boolean>(false);
  const [preserveTimestamps, setPreserveTimestamps] = useState<boolean>(true);
  const [smartAutoSkip, setSmartAutoSkip] = useState<boolean>(true);

  // Live backup execution state
  const [isBackingUp, setIsBackingUp] = useState<boolean>(false);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);
  const [backupProgress, setBackupProgress] = useState<BackupProgressEvent | null>(null);
  const [backupCompleted, setBackupCompleted] = useState<BackupCompletedEvent | null>(null);
  const [backupError, setBackupError] = useState<string | null>(null);
  const [logs, setLogs] = useState<BackupLogEvent[]>([]);
  const [prescan, setPrescan] = useState<PrescanState>({
    running: false,
    progressLabel: "",
    progressIndex: 0,
    progressTotal: 0,
    result: null,
  });

  const maxLogLinesRef = useRef<number>(2000);
  maxLogLinesRef.current = settings.max_log_lines || 2000;

  const autoOpenOnCompleteRef = useRef<boolean>(false);
  autoOpenOnCompleteRef.current = settings.auto_open_destination;

  // Theme application
  useEffect(() => {
    const root = document.documentElement;
    const apply = (dark: boolean) => {
      if (dark) {
        root.classList.add("dark");
      } else {
        root.classList.remove("dark");
      }
    };

    if (settings.theme === "dark") {
      apply(true);
      return;
    }
    if (settings.theme === "light") {
      apply(false);
      return;
    }

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    apply(mq.matches);
    const handler = (ev: MediaQueryListEvent) => apply(ev.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [settings.theme]);

  const selectedDevice: DeviceInfo | null = useMemo(() => {
    if (!backendState.devices.length) return null;
    const found = backendState.devices.find((d) => d.serial === selectedSerial);
    if (found) return found;
    return backendState.devices.find((d) => d.is_ready) ?? backendState.devices[0];
  }, [backendState.devices, selectedSerial]);

  const refreshOverview = useCallback(async () => {
    if (!isTauriRuntime()) return;
    try {
      const ov = await api.getDashboardOverview();
      setOverview(ov);
    } catch {
      // ignore initial race
    }
  }, []);

  const inspectDest = useCallback(async (path: string) => {
    if (!isTauriRuntime()) return;
    if (!path.trim()) {
      setDestInfo(null);
      return;
    }
    try {
      const res = await api.inspectDestination(path);
      setDestInfo(res);
    } catch (err) {
      setDestInfo({ valid: false, exists: false, error: String(err) });
    }
  }, []);

  // Inspect destination whenever destDir changes
  useEffect(() => {
    const timer = window.setTimeout(() => {
      void inspectDest(destDir);
    }, 150);
    return () => window.clearTimeout(timer);
  }, [destDir, inspectDest]);

  // Initial load + Tauri event subscriptions
  useEffect(() => {
    if (!isTauriRuntime()) return;

    let unlisteners: Array<() => void> = [];
    let cancelled = false;

    const init = async () => {
      try {
        const [st, cfg, ov, info] = await Promise.all([
          api.getBackendState(),
          api.getSettings(),
          api.getDashboardOverview(),
          api.getAppInfo(),
        ]);

        if (cancelled) return;
        setBackendState(st);
        setSettings(cfg);
        setOverview(ov);
        setAppInfo(info);

        // Apply saved defaults into backup session state
        if (cfg.default_backup_dir) {
          setDestDir(cfg.default_backup_dir);
        } else if (ov.default_backup_dir) {
          setDestDir(ov.default_backup_dir);
        }
        setAutoSubfolder(cfg.auto_subfolder);
        setPreserveTimestamps(cfg.preserve_timestamps);
        setSmartAutoSkip(cfg.smart_auto_skip);
        setTargets({
          dcim: cfg.default_dcim,
          documents: cfg.default_documents,
          pictures: cfg.default_pictures,
          whatsapp: cfg.default_whatsapp,
          custom_enabled: cfg.custom_folders.length > 0,
          custom_path: cfg.custom_folders[0] || "/sdcard/Download",
          custom_paths: cfg.custom_folders,
        });

        if (st.devices.length > 0) {
          const ready = st.devices.find((d) => d.is_ready) ?? st.devices[0];
          setSelectedSerial(ready.serial);
        }
      } catch (err) {
        console.error("Failed initial load:", err);
      }

      const u1 = await api.onEvent<BackendStateSnapshot>("backend://status", (snap) => {
        setBackendState(snap);
        if (snap.state === "crashed") {
          setIsBackingUp(false);
          setIsCancelling(false);
          setPrescan((p) => ({ ...p, running: false }));
        }
      });

      const u2 = await api.onEvent<DeviceStatusPayload>("backend://device_status", (payload) => {
        setBackendState((prev) => ({
          ...prev,
          state: "ready",
          adb_available: payload.adb_available,
          adb_path: payload.adb_path,
          adb_version: payload.adb_version,
          custom_adb_path: payload.custom_adb_path,
          devices: payload.devices,
          last_error: payload.error,
        }));
        setSelectedSerial((prevSerial) => {
          if (prevSerial && payload.devices.some((d) => d.serial === prevSerial)) {
            return prevSerial;
          }
          const ready = payload.devices.find((d) => d.is_ready) ?? payload.devices[0];
          return ready ? ready.serial : "";
        });
      });

      const u3 = await api.onEvent<BackupProgressEvent>("backend://backup_progress", (ev) => {
        setBackupProgress(ev);
      });

      const u4 = await api.onEvent<BackupLogEvent>("backend://backup_log", (entry) => {
        setLogs((prev) => {
          const limit = maxLogLinesRef.current;
          const next = prev.length >= limit ? prev.slice(prev.length - limit + 1) : prev.slice();
          next.push(entry);
          return next;
        });
      });

      const u5 = await api.onEvent<BackupCompletedEvent>("backend://backup_completed", (ev) => {
        setIsBackingUp(false);
        setIsCancelling(false);
        setBackupCompleted(ev);
        if (ev.error) {
          setBackupError(ev.error);
        }
        void refreshOverview();
        if (
          autoOpenOnCompleteRef.current &&
          (ev.status === "completed" || ev.status === "completed_with_errors") &&
          ev.dest_dir
        ) {
          void api.openFolderInExplorer(ev.dest_dir);
        }
      });

      const u6 = await api.onEvent<{
        job_id: string;
        target_index: number;
        total_targets: number;
        target_label: string;
      }>("backend://prescan_progress", (ev) => {
        setPrescan((p) => ({
          ...p,
          running: true,
          progressLabel: ev.target_label,
          progressIndex: ev.target_index,
          progressTotal: ev.total_targets,
        }));
      });

      const u7 = await api.onEvent<PrescanCompletedEvent>("backend://prescan_completed", (ev) => {
        setPrescan({
          running: false,
          progressLabel: "",
          progressIndex: 0,
          progressTotal: 0,
          result: ev,
        });
      });

      unlisteners = [u1, u2, u3, u4, u5, u6, u7];
    };

    void init();

    return () => {
      cancelled = true;
      for (const fn of unlisteners) fn();
    };
  }, [refreshOverview]);

  const refreshDevices = useCallback(async () => {
    if (!isTauriRuntime()) return;
    setIsRefreshingDevices(true);
    try {
      const payload = await api.listDevices();
      setBackendState((prev) => ({
        ...prev,
        adb_available: payload.adb_available,
        adb_path: payload.adb_path,
        adb_version: payload.adb_version,
        custom_adb_path: payload.custom_adb_path,
        devices: payload.devices,
        last_error: payload.error,
      }));
      if (payload.devices.length > 0 && !payload.devices.some((d) => d.serial === selectedSerial)) {
        const ready = payload.devices.find((d) => d.is_ready) ?? payload.devices[0];
        setSelectedSerial(ready.serial);
      }
    } catch (err) {
      setBackendState((prev) => ({ ...prev, last_error: String(err) }));
    } finally {
      setIsRefreshingDevices(false);
    }
  }, [selectedSerial]);

  const restartPythonBackend = useCallback(async () => {
    if (!isTauriRuntime()) return;
    const snap = await api.restartBackend();
    setBackendState(snap);
  }, []);

  const chooseDestDirectory = useCallback(async () => {
    if (!isTauriRuntime()) return null;
    const chosen = await api.pickFolder(destDir || settings.default_backup_dir || undefined);
    if (chosen) {
      setDestDir(chosen);
    }
    return chosen;
  }, [destDir, settings.default_backup_dir]);

  const openDestFolder = useCallback(
    async (overridePath?: string) => {
      const path = (overridePath ?? destDir) || overview.default_backup_dir;
      if (!path) return;
      await api.openFolderInExplorer(path);
    },
    [destDir, overview.default_backup_dir]
  );

  const runPrescan = useCallback(async () => {
    if (!selectedDevice || !selectedDevice.is_ready || !destDir.trim()) return;
    setBackupError(null);
    setPrescan({
      running: true,
      progressLabel: "Initializing scan...",
      progressIndex: 0,
      progressTotal: 0,
      result: null,
    });
    try {
      await api.prescanBackup({
        serial: selectedDevice.serial,
        dest_dir: destDir.trim(),
        auto_subfolder: autoSubfolder,
        preserve_timestamps: preserveTimestamps,
        smart_auto_skip: smartAutoSkip,
        device_model: selectedDevice.model,
        device_android_version: selectedDevice.android_version,
        targets,
      });
    } catch (err) {
      setPrescan((p) => ({ ...p, running: false }));
      setBackupError(String(err));
    }
  }, [selectedDevice, destDir, autoSubfolder, preserveTimestamps, smartAutoSkip, targets]);

  const startBackup = useCallback(async () => {
    if (!selectedDevice || !selectedDevice.is_ready || !destDir.trim() || isBackingUp) return;
    setBackupError(null);
    setBackupCompleted(null);
    setBackupProgress(null);
    setIsBackingUp(true);
    setIsCancelling(false);
    setLogs([]);

    try {
      await api.startBackup({
        serial: selectedDevice.serial,
        dest_dir: destDir.trim(),
        auto_subfolder: autoSubfolder,
        preserve_timestamps: preserveTimestamps,
        smart_auto_skip: smartAutoSkip,
        device_model: selectedDevice.model,
        device_android_version: selectedDevice.android_version,
        targets,
      });
    } catch (err) {
      setIsBackingUp(false);
      setBackupError(String(err));
    }
  }, [
    selectedDevice,
    destDir,
    isBackingUp,
    autoSubfolder,
    preserveTimestamps,
    smartAutoSkip,
    targets,
  ]);

  const cancelBackup = useCallback(async () => {
    if (!isBackingUp || isCancelling) return;
    setIsCancelling(true);
    try {
      await api.cancelBackup();
    } catch (err) {
      setBackupError(String(err));
      setIsCancelling(false);
    }
  }, [isBackingUp, isCancelling]);

  const saveSettings = useCallback(async (next: AppSettings) => {
    setSettings(next);
    if (!isTauriRuntime()) return next;
    const saved = await api.updateSettings(next);
    setSettings(saved);
    return saved;
  }, []);

  const addCustomFolderFromBrowser = useCallback((remotePath: string) => {
    const clean = remotePath.trim();
    if (!clean) return;
    setTargets((prev) => {
      const existing = prev.custom_paths.includes(clean)
        ? prev.custom_paths
        : [...prev.custom_paths, clean];
      return {
        ...prev,
        custom_enabled: true,
        custom_path: clean,
        custom_paths: existing,
      };
    });
    setActivePage("backup");
  }, []);

  const clearLiveLogs = useCallback(() => {
    setLogs([]);
  }, []);

  const prescanSummary: PrescanTargetItem[] = prescan.result?.targets ?? [];

  return {
    activePage,
    setActivePage,
    backendState,
    settings,
    saveSettings,
    appInfo,
    overview,
    refreshOverview,
    selectedDevice,
    selectedSerial,
    setSelectedSerial,
    isRefreshingDevices,
    refreshDevices,
    restartPythonBackend,
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
    setBackupError,
    logs,
    clearLiveLogs,
    prescan,
    prescanSummary,
    runPrescan,
    startBackup,
    cancelBackup,
    addCustomFolderFromBrowser,
  };
}
