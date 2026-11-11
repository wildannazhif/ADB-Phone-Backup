use std::path::Path;
use std::sync::Arc;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tauri::{AppHandle, Manager, State};
use crate::db::{AppDatabase, AppSettings, BackupSessionRecord, DashboardOverview};
use crate::python_bridge::{ActiveBackupMeta, BackendStateSnapshot, PythonSidecarManager};

#[derive(Debug, Deserialize)]
pub struct BrowseDirParams {
    pub serial: String,
    pub path: String,
    pub offset: Option<usize>,
    pub limit: Option<usize>,
    pub query: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct BackupRequestPayload {
    pub job_id: Option<String>,
    pub serial: String,
    pub dest_dir: String,
    pub auto_subfolder: Option<bool>,
    pub preserve_timestamps: Option<bool>,
    pub smart_auto_skip: Option<bool>,
    pub device_model: Option<String>,
    pub device_android_version: Option<String>,
    pub targets: Value,
}

#[derive(Debug, Serialize)]
pub struct AppInfo {
    pub name: String,
    pub version: String,
    pub identifier: String,
    pub app_data_dir: String,
    pub db_path: String,
    pub platform: String,
    pub arch: String,
}

#[tauri::command]
pub fn get_backend_state(
    bridge: State<'_, Arc<PythonSidecarManager>>,
) -> Result<BackendStateSnapshot, String> {
    Ok(bridge.get_state_snapshot(""))
}

#[tauri::command]
pub fn restart_backend(
    bridge: State<'_, Arc<PythonSidecarManager>>,
) -> Result<BackendStateSnapshot, String> {
    bridge.shutdown();
    std::thread::sleep(std::time::Duration::from_millis(200));
    bridge.start()?;
    Ok(bridge.get_state_snapshot("starting"))
}

#[tauri::command]
pub fn get_adb_status(
    bridge: State<'_, Arc<PythonSidecarManager>>,
) -> Result<Value, String> {
    bridge.send_request("get_adb_status", json!({}), 8)
}

#[tauri::command]
pub fn set_adb_path(
    path: String,
    bridge: State<'_, Arc<PythonSidecarManager>>,
    db: State<'_, AppDatabase>,
) -> Result<Value, String> {
    let clean_path = path.trim().to_string();
    let res = bridge.send_request(
        "set_adb_path",
        json!({ "custom_adb_path": clean_path }),
        8,
    )?;

    if let Ok(mut settings) = db.get_settings() {
        settings.custom_adb_path = clean_path;
        let _ = db.update_settings(&settings);
    }

    Ok(res)
}

#[tauri::command]
pub fn list_devices(
    bridge: State<'_, Arc<PythonSidecarManager>>,
) -> Result<Value, String> {
    bridge.send_request("list_devices", json!({}), 15)
}

#[tauri::command]
pub fn browse_directory(
    params: BrowseDirParams,
    bridge: State<'_, Arc<PythonSidecarManager>>,
) -> Result<Value, String> {
    let offset = params.offset.unwrap_or(0);
    let limit = params.limit.unwrap_or(200);
    let query = params.query.unwrap_or_default();

    bridge.send_request(
        "browse_directory",
        json!({
            "serial": params.serial,
            "path": params.path,
            "offset": offset,
            "limit": limit,
            "query": query,
        }),
        25,
    )
}

#[tauri::command]
pub fn resolve_whatsapp_targets(
    serial: String,
    bridge: State<'_, Arc<PythonSidecarManager>>,
) -> Result<Value, String> {
    bridge.send_request(
        "resolve_whatsapp_targets",
        json!({ "serial": serial }),
        15,
    )
}

#[tauri::command]
pub fn inspect_destination(
    path: String,
    bridge: State<'_, Arc<PythonSidecarManager>>,
) -> Result<Value, String> {
    bridge.send_request(
        "inspect_destination",
        json!({ "path": path }),
        5,
    )
}

#[tauri::command]
pub fn prescan_backup(
    payload: BackupRequestPayload,
    bridge: State<'_, Arc<PythonSidecarManager>>,
) -> Result<Value, String> {
    let job_id = payload
        .job_id
        .clone()
        .unwrap_or_else(|| format!("scan-{}", chrono::Utc::now().timestamp()));

    let req_params = json!({
        "job_id": job_id,
        "serial": payload.serial,
        "dest_dir": payload.dest_dir,
        "auto_subfolder": payload.auto_subfolder.unwrap_or(false),
        "device_model": payload.device_model.unwrap_or_else(|| "Android Device".into()),
        "targets": payload.targets,
    });

    bridge.send_request("prescan_backup", req_params, 10)
}

#[tauri::command]
pub fn start_backup(
    payload: BackupRequestPayload,
    bridge: State<'_, Arc<PythonSidecarManager>>,
) -> Result<Value, String> {
    let job_id = payload
        .job_id
        .clone()
        .unwrap_or_else(|| format!("backup-{}", chrono::Utc::now().timestamp()));

    let auto_subfolder = payload.auto_subfolder.unwrap_or(false);
    let preserve_timestamps = payload.preserve_timestamps.unwrap_or(true);
    let smart_auto_skip = payload.smart_auto_skip.unwrap_or(true);
    let model = payload.device_model.clone().unwrap_or_else(|| "Android Device".into());
    let android_ver = payload.device_android_version.clone().unwrap_or_default();
    let targets_json = serde_json::to_string(&payload.targets).unwrap_or_else(|_| "{}".into());

    bridge.set_active_backup_meta(ActiveBackupMeta {
        job_id: job_id.clone(),
        started_at: chrono::Utc::now().to_rfc3339(),
        serial: payload.serial.clone(),
        device_model: model.clone(),
        device_android_version: android_ver,
        dest_dir: payload.dest_dir.clone(),
        targets_json,
        preserve_timestamps,
        auto_subfolder,
        smart_auto_skip,
    });

    let req_params = json!({
        "job_id": job_id,
        "serial": payload.serial,
        "dest_dir": payload.dest_dir,
        "auto_subfolder": auto_subfolder,
        "preserve_timestamps": preserve_timestamps,
        "smart_auto_skip": smart_auto_skip,
        "device_model": model,
        "targets": payload.targets,
    });

    bridge.send_request("start_backup", req_params, 10)
}

#[tauri::command]
pub fn cancel_backup(
    bridge: State<'_, Arc<PythonSidecarManager>>,
) -> Result<Value, String> {
    bridge.cancel_backup()
}

#[tauri::command]
pub fn get_settings(db: State<'_, AppDatabase>) -> Result<AppSettings, String> {
    db.get_settings().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn update_settings(
    settings: AppSettings,
    db: State<'_, AppDatabase>,
    bridge: State<'_, Arc<PythonSidecarManager>>,
) -> Result<AppSettings, String> {
    let saved = db.update_settings(&settings).map_err(|e| e.to_string())?;

    // Update backend custom ADB path if changed
    let _ = bridge.send_request(
        "set_adb_path",
        json!({ "custom_adb_path": saved.custom_adb_path }),
        5,
    );

    Ok(saved)
}

#[tauri::command]
pub fn get_dashboard_overview(
    db: State<'_, AppDatabase>,
) -> Result<DashboardOverview, String> {
    let default_dir = db
        .get_settings()
        .map(|s| s.default_backup_dir)
        .unwrap_or_default();
    db.get_dashboard_overview(&default_dir)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn list_backup_history(
    limit: Option<usize>,
    offset: Option<usize>,
    db: State<'_, AppDatabase>,
) -> Result<Vec<BackupSessionRecord>, String> {
    let lim = limit.unwrap_or(50);
    let off = offset.unwrap_or(0);
    db.list_backup_sessions(lim, off).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn clear_backup_history(db: State<'_, AppDatabase>) -> Result<(), String> {
    db.clear_backup_history().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_log_info(db: State<'_, AppDatabase>) -> Result<Value, String> {
    let count = db.get_log_count().map_err(|e| e.to_string())?;
    let logs = db.list_logs(200).map_err(|e| e.to_string())?;
    Ok(json!({
        "total_count": count,
        "recent": logs,
    }))
}

#[tauri::command]
pub fn export_logs(dest_path: String, db: State<'_, AppDatabase>) -> Result<usize, String> {
    let logs = db.list_logs(10_000).map_err(|e| e.to_string())?;
    let mut out = String::new();
    for l in &logs {
        let sid = l.session_id.as_deref().unwrap_or("-");
        out.push_str(&format!("[{}] [{}] [{}] {}\n", l.timestamp, sid, l.level.to_uppercase(), l.message));
    }
    std::fs::write(&dest_path, out).map_err(|e| format!("Gagal menyimpan file log: {}", e))?;
    Ok(logs.len())
}

#[tauri::command]
pub fn clear_logs(db: State<'_, AppDatabase>) -> Result<(), String> {
    db.clear_logs().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn open_folder_in_explorer(
    path: String,
    _app: AppHandle,
) -> Result<(), String> {
    let clean = path.trim();
    if clean.is_empty() {
        return Err("Path folder kosong.".into());
    }
    let p = Path::new(clean);
    if !p.exists() {
        return Err(format!("Folder tidak ditemukan di harddisk: {}", clean));
    }

    #[cfg(target_os = "windows")]
    {
        use std::process::Command;
        let _ = Command::new("explorer.exe").arg(clean).spawn();
        Ok(())
    }
    #[cfg(not(target_os = "windows"))]
    {
        use tauri_plugin_opener::OpenerExt;
        _app.opener()
            .open_path(clean, None::<&str>)
            .map_err(|e| e.to_string())
    }
}
#[tauri::command]
pub fn get_app_info(
    app: AppHandle,
    db: State<'_, AppDatabase>,
) -> Result<AppInfo, String> {
    let app_dir = app
        .path()
        .app_data_dir()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_default();

    Ok(AppInfo {
        name: "ADB Phone Backup Pro".into(),
        version: "2.0.0".into(),
        identifier: "com.wildannazhif.adbphonebackup".into(),
        app_data_dir: app_dir,
        db_path: db.get_db_path().to_string_lossy().to_string(),
        platform: std::env::consts::OS.into(),
        arch: std::env::consts::ARCH.into(),
    })
}
