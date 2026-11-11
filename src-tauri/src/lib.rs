mod commands;
pub mod db;
pub mod python_bridge;

use std::sync::Arc;
use tauri::{Manager, RunEvent};

use db::AppDatabase;
use python_bridge::PythonSidecarManager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let app_data = app
                .path()
                .app_data_dir()
                .expect("Failed to resolve Tauri app data directory");

            let db_path = app_data.join("adb_backup.sqlite");
            let db = AppDatabase::new(&db_path).expect("Failed to initialize SQLite database");

            let bridge = PythonSidecarManager::new(app.handle().clone(), db.clone());

            app.manage(db);
            app.manage(bridge.clone());

            // Spawn managed Python backend child process
            if let Err(err) = bridge.start() {
                eprintln!("[Tauri Setup] Warning starting Python backend: {}", err);
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::get_backend_state,
            commands::restart_backend,
            commands::get_adb_status,
            commands::set_adb_path,
            commands::list_devices,
            commands::browse_directory,
            commands::resolve_whatsapp_targets,
            commands::inspect_destination,
            commands::prescan_backup,
            commands::start_backup,
            commands::cancel_backup,
            commands::get_settings,
            commands::update_settings,
            commands::get_dashboard_overview,
            commands::list_backup_history,
            commands::clear_backup_history,
            commands::get_log_info,
            commands::export_logs,
            commands::clear_logs,
            commands::open_folder_in_explorer,
            commands::get_app_info,
        ]);

    let app = builder
        .build(tauri::generate_context!())
        .expect("Error while building ADB Phone Backup application");

    app.run(|app_handle, event| {
        if let RunEvent::Exit = event {
            if let Some(bridge) = app_handle.try_state::<Arc<PythonSidecarManager>>() {
                bridge.shutdown();
            }
        }
    });
}
