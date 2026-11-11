export type ThemeMode = "dark" | "light" | "system";

export type NavPage = "dashboard" | "backup" | "browser" | "history" | "settings";

export interface DeviceInfo {
  serial: string;
  status: string;
  model: string;
  product: string;
  android_version: string;
  battery_level: number | null;
  storage_total: string;
  storage_free: string;
  is_ready: boolean;
  display_name: string;
}

export interface DeviceStatusPayload {
  adb_available: boolean;
  adb_path: string | null;
  adb_version: string | null;
  custom_adb_path: string;
  devices: DeviceInfo[];
  error: string | null;
}

export interface BackendStateSnapshot {
  state: "starting" | "ready" | "crashed" | "stopped";
  pid: number | null;
  python_version: string | null;
  python_path: string | null;
  backend_script: string | null;
  adb_available: boolean;
  adb_path: string | null;
  adb_version: string | null;
  custom_adb_path: string;
  devices: DeviceInfo[];
  active_job_id: string | null;
  last_error: string | null;
  stderr_tail: string[];
}

export interface AppSettings {
  theme: ThemeMode;
  default_backup_dir: string;
  custom_adb_path: string;
  auto_subfolder: boolean;
  preserve_timestamps: boolean;
  smart_auto_skip: boolean;
  default_dcim: boolean;
  default_documents: boolean;
  default_pictures: boolean;
  default_whatsapp: boolean;
  custom_folders: string[];
  max_log_lines: number;
  auto_open_destination: boolean;
}

export interface BackupTargetsConfig {
  dcim: boolean;
  documents: boolean;
  pictures: boolean;
  whatsapp: boolean;
  custom_enabled: boolean;
  custom_path: string;
  custom_paths: string[];
}

export interface DestinationInspectResult {
  valid: boolean;
  exists: boolean;
  path?: string;
  drive?: string;
  total_bytes?: number;
  free_bytes?: number;
  used_bytes?: number;
  used_percent?: number;
  error?: string | null;
}

export interface BackupProgressEvent {
  job_id: string;
  phase: "scanning" | "transferring" | "target_done" | "completed" | "cancelled";
  target_index: number;
  total_targets: number;
  target_label: string;
  overall_percent: number;
  target_percent: number;
  current_file: string;
  current_file_rel: string;
  files_completed: number;
  files_skipped: number;
  files_failed: number;
  files_total_to_pull: number;
  files_scanned: number;
  bytes_transferred: number;
  bytes_total_to_pull: number;
  speed_bps: number | null;
  eta_seconds: number | null;
  elapsed_seconds: number;
}

export interface BackupLogEvent {
  job_id: string;
  timestamp: string;
  level: "info" | "skip" | "success" | "warning" | "error" | "detail";
  message: string;
}

export interface TargetSummaryItem {
  label: string;
  remote_path: string;
  local_path: string;
  transferred: number;
  skipped: number;
  errors: number;
  error?: string;
}

export interface BackupCompletedEvent {
  job_id: string;
  status: "completed" | "completed_with_errors" | "cancelled" | "failed";
  serial: string;
  device_model: string;
  dest_dir: string;
  files_transferred: number;
  files_skipped: number;
  files_failed: number;
  bytes_transferred: number;
  duration_seconds: number;
  targets_summary: TargetSummaryItem[];
  error: string | null;
}

export interface PrescanTargetItem {
  label: string;
  remote_path: string;
  local_path: string;
  on_phone: number;
  already_on_disk: number;
  new_files: number;
  new_bytes: number;
}

export interface PrescanCompletedEvent {
  job_id: string;
  cancelled: boolean;
  root_dest: string;
  targets: PrescanTargetItem[];
  total_on_phone: number;
  total_already_on_disk: number;
  total_new: number;
  total_new_bytes: number;
  error: string | null;
}

export interface RemoteEntry {
  name: string;
  path: string;
  type: "dir" | "file" | "symlink";
  size: number | null;
  modified: string;
  is_symlink: boolean;
  link_target: string | null;
}

export interface BrowseDirectoryResult {
  path: string;
  accessible: boolean;
  error: string | null;
  entries: RemoteEntry[];
  total_dirs: number;
  total_files: number;
  total_count: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export interface BackupSessionRecord {
  id: string;
  started_at: string;
  finished_at: string | null;
  duration_seconds: number;
  device_serial: string;
  device_model: string;
  device_android_version: string;
  dest_dir: string;
  targets_json: string;
  preserve_timestamps: boolean;
  auto_subfolder: boolean;
  smart_auto_skip: boolean;
  files_transferred: number;
  files_skipped: number;
  files_failed: number;
  bytes_transferred: number;
  status: string;
  error_message: string | null;
}

export interface DashboardOverview {
  last_backup_date: string | null;
  total_backup_files: number;
  total_backup_bytes: number;
  default_backup_dir: string;
  recent_sessions: BackupSessionRecord[];
  total_sessions_count: number;
}

export interface LogInfoResult {
  total_count: number;
  recent: Array<{
    id: number;
    session_id: string | null;
    timestamp: string;
    level: string;
    message: string;
  }>;
}

export interface AppInfo {
  name: string;
  version: string;
  identifier: string;
  app_data_dir: string;
  db_path: string;
  platform: string;
  arch: string;
}
