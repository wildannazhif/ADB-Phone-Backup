use adb_phone_backup_lib::db::{AppDatabase, BackupSessionRecord};
use adb_phone_backup_lib::python_bridge::BackendDeviceStatus;

#[test]
fn test_settings_roundtrip() {
    let db = AppDatabase::new_in_memory().unwrap();
    let defaults = db.get_settings().unwrap();
    assert_eq!(defaults.theme, "dark");
    assert!(defaults.smart_auto_skip);

    let mut updated = defaults;
    updated.default_backup_dir = "D:\\TestBackup".to_string();
    updated.auto_subfolder = true;
    db.update_settings(&updated).unwrap();

    let loaded = db.get_settings().unwrap();
    assert_eq!(loaded.default_backup_dir, "D:\\TestBackup");
    assert!(loaded.auto_subfolder);
}

#[test]
fn test_record_session_and_overview_aggregation() {
    let db = AppDatabase::new_in_memory().unwrap();
    let initial_overview = db.get_dashboard_overview("").unwrap();
    assert_eq!(initial_overview.total_backup_files, 0);
    assert_eq!(initial_overview.total_backup_bytes, 0);
    assert!(initial_overview.last_backup_date.is_none());

    let session1 = BackupSessionRecord {
        id: "job-1".to_string(),
        started_at: "2026-11-11T10:00:00Z".to_string(),
        finished_at: Some("2026-11-11T10:01:00Z".to_string()),
        duration_seconds: 60,
        device_serial: "SERIAL1".to_string(),
        device_model: "Phone 1".to_string(),
        device_android_version: "Android 14".to_string(),
        dest_dir: "D:\\Backup".to_string(),
        targets_json: "[]".to_string(),
        preserve_timestamps: true,
        auto_subfolder: false,
        smart_auto_skip: true,
        files_transferred: 10,
        files_skipped: 100,
        files_failed: 0,
        bytes_transferred: 50_000_000,
        status: "completed".to_string(),
        error_message: None,
    };
    db.record_backup_session(&session1).unwrap();

    let overview = db.get_dashboard_overview("").unwrap();
    assert_eq!(overview.total_backup_files, 10);
    assert_eq!(overview.total_backup_bytes, 50_000_000);
    assert_eq!(overview.last_backup_date.as_deref(), Some("2026-11-11T10:00:00Z"));
    assert_eq!(overview.recent_sessions.len(), 1);

    db.clear_backup_history().unwrap();
    let cleared = db.get_dashboard_overview("").unwrap();
    assert_eq!(cleared.total_backup_files, 0);
    assert!(cleared.recent_sessions.is_empty());
}

#[test]
fn test_logs_persistence_and_clear() {
    let db = AppDatabase::new_in_memory().unwrap();
    db.append_log(Some("job-1"), "10:00:00", "info", "Scan started").unwrap();
    db.append_log(Some("job-1"), "10:00:02", "skip", "120 files skipped").unwrap();

    assert_eq!(db.get_log_count().unwrap(), 2);
    let logs = db.list_logs(10).unwrap();
    assert_eq!(logs.len(), 2);
    assert_eq!(logs[0].message, "Scan started");
    assert_eq!(logs[1].level, "skip");

    db.clear_logs().unwrap();
    assert_eq!(db.get_log_count().unwrap(), 0);
}

#[test]
fn test_device_status_deserialization() {
    let raw = r#"{
        "adb_available": true,
        "adb_path": "C:\\platform-tools\\adb.exe",
        "adb_version": "Android Debug Bridge version 1.0.41",
        "custom_adb_path": "",
        "devices": [{
            "serial": "ABC123",
            "status": "device",
            "model": "Pixel 8",
            "product": "shiba",
            "android_version": "Android 14",
            "battery_level": 88,
            "storage_total": "110G",
            "storage_free": "42G",
            "is_ready": true,
            "display_name": "Pixel 8 (ABC123)"
        }],
        "error": null
    }"#;

    let parsed: BackendDeviceStatus = serde_json::from_str(raw).unwrap();
    assert!(parsed.adb_available);
    assert_eq!(parsed.devices.len(), 1);
    assert!(parsed.devices[0].is_ready);
    assert_eq!(parsed.devices[0].battery_level, Some(88));
}
