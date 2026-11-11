import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { open, save } from "@tauri-apps/plugin-dialog";
import type {
  AppInfo,
  AppSettings,
  BackendStateSnapshot,
  BackupSessionRecord,
  BrowseDirectoryResult,
  DashboardOverview,
  DestinationInspectResult,
  DeviceStatusPayload,
  LogInfoResult,
} from "@/types/backend";

export interface BackupInvokeRequest {
  job_id?: string;
  serial: string;
  dest_dir: string;
  auto_subfolder: boolean;
  preserve_timestamps: boolean;
  smart_auto_skip: boolean;
  device_model: string;
  device_android_version: string;
  targets: BackupRequestPayloadTargets;
}

export interface BackupRequestPayloadTargets {
  dcim: boolean;
  documents: boolean;
  pictures: boolean;
  whatsapp: boolean;
  custom_enabled: boolean;
  custom_path: string;
  custom_paths: string[];
}

export const isTauriRuntime = (): boolean =>
  typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

export const api = {
  getBackendState: () => invoke<BackendStateSnapshot>("get_backend_state"),
  restartBackend: () => invoke<BackendStateSnapshot>("restart_backend"),
  getAdbStatus: () => invoke<Record<string, unknown>>("get_adb_status"),
  setAdbPath: (path: string) => invoke<Record<string, unknown>>("set_adb_path", { path }),
  listDevices: () => invoke<DeviceStatusPayload>("list_devices"),
  browseDirectory: (params: {
    serial: string;
    path: string;
    offset?: number;
    limit?: number;
    query?: string;
  }) => invoke<BrowseDirectoryResult>("browse_directory", { params }),
  resolveWhatsappTargets: (serial: string) =>
    invoke<{ targets: Array<{ remote_path: string; subfolder: string }> }>(
      "resolve_whatsapp_targets",
      { serial }
    ),
  inspectDestination: (path: string) =>
    invoke<DestinationInspectResult>("inspect_destination", { path }),
  prescanBackup: (payload: BackupInvokeRequest) =>
    invoke<{ job_id: string; started: boolean }>("prescan_backup", { payload }),
  startBackup: (payload: BackupInvokeRequest) =>
    invoke<{ job_id: string; started: boolean }>("start_backup", { payload }),
  cancelBackup: () => invoke<{ cancelled: boolean }>("cancel_backup"),
  getSettings: () => invoke<AppSettings>("get_settings"),
  updateSettings: (settings: AppSettings) =>
    invoke<AppSettings>("update_settings", { settings }),
  getDashboardOverview: () => invoke<DashboardOverview>("get_dashboard_overview"),
  listBackupHistory: (limit = 50, offset = 0) =>
    invoke<BackupSessionRecord[]>("list_backup_history", { limit, offset }),
  clearBackupHistory: () => invoke<void>("clear_backup_history"),
  getLogInfo: () => invoke<LogInfoResult>("get_log_info"),
  exportLogs: (destPath: string) => invoke<number>("export_logs", { destPath }),
  clearLogs: () => invoke<void>("clear_logs"),
  openFolderInExplorer: (path: string) =>
    invoke<void>("open_folder_in_explorer", { path }),
  getAppInfo: () => invoke<AppInfo>("get_app_info"),

  pickFolder: async (defaultPath?: string, title = "Select Backup Folder"): Promise<string | null> => {
    const selected = await open({
      directory: true,
      multiple: false,
      defaultPath: defaultPath || undefined,
      title,
    });
    return typeof selected === "string" ? selected : null;
  },

  pickAdbExecutable: async (defaultPath?: string): Promise<string | null> => {
    const selected = await open({
      directory: false,
      multiple: false,
      defaultPath: defaultPath || undefined,
      title: "Select ADB Executable (adb.exe)",
      filters: [{ name: "Executable", extensions: ["exe"] }],
    });
    return typeof selected === "string" ? selected : null;
  },

  pickLogSavePath: async (): Promise<string | null> => {
    const selected = await save({
      title: "Export Activity Logs",
      defaultPath: `adb-backup-logs-${new Date().toISOString().slice(0, 10)}.log`,
      filters: [{ name: "Log Files", extensions: ["log", "txt"] }],
    });
    return typeof selected === "string" ? selected : null;
  },

  onEvent: <T>(channel: string, handler: (payload: T) => void): Promise<UnlistenFn> =>
    listen<T>(channel, (ev) => handler(ev.payload)),
};

