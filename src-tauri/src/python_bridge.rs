use std::collections::{HashMap, VecDeque};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::time::Duration;
use chrono::Utc;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager};
use uuid::Uuid;

use crate::db::{AppDatabase, BackupSessionRecord};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackendDeviceInfo {
    pub serial: String,
    pub status: String,
    pub model: String,
    pub product: String,
    pub android_version: String,
    pub battery_level: Option<i64>,
    pub storage_total: String,
    pub storage_free: String,
    pub is_ready: bool,
    pub display_name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackendDeviceStatus {
    pub adb_available: bool,
    pub adb_path: Option<String>,
    pub adb_version: Option<String>,
    pub custom_adb_path: String,
    pub devices: Vec<BackendDeviceInfo>,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackendStateSnapshot {
    pub state: String, // "starting" | "ready" | "crashed" | "stopped"
    pub pid: Option<u32>,
    pub python_version: Option<String>,
    pub python_path: Option<String>,
    pub backend_script: Option<String>,
    pub adb_available: bool,
    pub adb_path: Option<String>,
    pub adb_version: Option<String>,
    pub custom_adb_path: String,
    pub devices: Vec<BackendDeviceInfo>,
    pub active_job_id: Option<String>,
    pub last_error: Option<String>,
    pub stderr_tail: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct ActiveBackupMeta {
    pub job_id: String,
    pub started_at: String,
    pub serial: String,
    pub device_model: String,
    pub device_android_version: String,
    pub dest_dir: String,
    pub targets_json: String,
    pub preserve_timestamps: bool,
    pub auto_subfolder: bool,
    pub smart_auto_skip: bool,
}

struct ChildProcessState {
    child: Child,
    stdin: Box<dyn Write + Send>,
    pid: u32,
    python_path: String,
    script_path: String,
}

pub struct PythonSidecarManager {
    app_handle: AppHandle,
    db: AppDatabase,
    child_state: Mutex<Option<ChildProcessState>>,
    pending_requests: Mutex<HashMap<String, mpsc::Sender<Result<Value, String>>>>,
    cached_status: Mutex<BackendDeviceStatus>,
    cached_ready: Mutex<Option<Value>>,
    active_backup_meta: Mutex<Option<ActiveBackupMeta>>,
    active_job_id: Mutex<Option<String>>,
    stderr_tail: Mutex<VecDeque<String>>,
    is_shutting_down: AtomicBool,
    is_spawning: Mutex<()>,
}

impl PythonSidecarManager {
    pub fn new(app_handle: AppHandle, db: AppDatabase) -> Arc<Self> {
        let default_status = BackendDeviceStatus {
            adb_available: false,
            adb_path: None,
            adb_version: None,
            custom_adb_path: String::new(),
            devices: Vec::new(),
            error: None,
        };

        Arc::new(Self {
            app_handle,
            db,
            child_state: Mutex::new(None),
            pending_requests: Mutex::new(HashMap::new()),
            cached_status: Mutex::new(default_status),
            cached_ready: Mutex::new(None),
            active_backup_meta: Mutex::new(None),
            active_job_id: Mutex::new(None),
            stderr_tail: Mutex::new(VecDeque::with_capacity(60)),
            is_shutting_down: AtomicBool::new(false),
            is_spawning: Mutex::new(()),
        })
    }

    pub fn start(&self) -> Result<(), String> {
        let _guard = self.is_spawning.lock().unwrap();

        if self.child_state.lock().unwrap().is_some() {
            return Ok(());
        }

        self.is_shutting_down.store(false, Ordering::SeqCst);

        let (python_exe, backend_script, python_path_env) = self.resolve_runtime_paths()?;

        let mut cmd = Command::new(&python_exe);
        cmd.arg("-u")
            .arg(&backend_script)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .env("PYTHONUTF8", "1")
            .env("PYTHONIOENCODING", "utf-8");

        if let Some(py_path) = &python_path_env {
            cmd.env("PYTHONPATH", py_path);
        }

        if let Some(pt_dir) = self.resolve_bundled_platform_tools_dir() {
            let existing_path = std::env::var("PATH").unwrap_or_default();
            cmd.env("PATH", format!("{};{}", pt_dir.display(), existing_path));
        }
        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("Gagal menjalankan proses backend Python ({}): {}", python_exe.display(), e))?;

        let pid = child.id();
        let stdout = child.stdout.take().ok_or("Gagal membuka stdout pipa backend")?;
        let stderr = child.stderr.take().ok_or("Gagal membuka stderr pipa backend")?;
        let stdin = child.stdin.take().ok_or("Gagal membuka stdin pipa backend")?;

        *self.child_state.lock().unwrap() = Some(ChildProcessState {
            child,
            stdin: Box::new(stdin),
            pid,
            python_path: python_exe.to_string_lossy().to_string(),
            script_path: backend_script.to_string_lossy().to_string(),
        });

        // Spawn stdout line parser thread
        let self_clone = self.get_arc();
        std::thread::Builder::new()
            .name("python-ipc-stdout".into())
            .spawn(move || self_clone.read_stdout_loop(stdout))
            .map_err(|e| format!("Gagal membuat thread pembaca stdout: {}", e))?;

        // Spawn stderr monitor thread
        let self_clone2 = self.get_arc();
        std::thread::Builder::new()
            .name("python-ipc-stderr".into())
            .spawn(move || self_clone2.read_stderr_loop(stderr))
            .map_err(|e| format!("Gagal membuat thread pembaca stderr: {}", e))?;

        // Synchronize initial custom ADB path from DB settings if present
        if let Ok(settings) = self.db.get_settings() {
            if !settings.custom_adb_path.is_empty() {
                let _ = self.send_request(
                    "set_adb_path",
                    json!({ "custom_adb_path": settings.custom_adb_path }),
                    5,
                );
            }
        }

        self.emit_state_change("starting");
        Ok(())
    }

    fn resolve_runtime_paths(&self) -> Result<(PathBuf, PathBuf, Option<String>), String> {
        // 1. Check bundled resource directory (standalone production distribution)
        if let Ok(res_dir) = self.app_handle.path().resource_dir() {
            // Check nested resources/ layout (typical Tauri bundle)
            let nested_py = res_dir.join("resources").join("python-runtime").join("python.exe");
            let nested_script = res_dir.join("resources").join("backend").join("src").join("ipc_worker.py");
            if nested_py.exists() && nested_script.exists() {
                let py_path = res_dir.join("resources").join("backend");
                return Ok((nested_py, nested_script, Some(py_path.to_string_lossy().to_string())));
            }

            // Check flat layout directly inside resource_dir
            let flat_py = res_dir.join("python-runtime").join("python.exe");
            let flat_script = res_dir.join("backend").join("src").join("ipc_worker.py");
            if flat_py.exists() && flat_script.exists() {
                let py_path = res_dir.join("backend");
                return Ok((flat_py, flat_script, Some(py_path.to_string_lossy().to_string())));
            }

            let direct_script = res_dir.join("src").join("ipc_worker.py");
            if nested_py.exists() && direct_script.exists() {
                return Ok((nested_py, direct_script, Some(res_dir.to_string_lossy().to_string())));
            }
            if flat_py.exists() && direct_script.exists() {
                return Ok((flat_py, direct_script, Some(res_dir.to_string_lossy().to_string())));
            }
        }

        // 2. Check relative to current executable parent
        if let Ok(exe_path) = std::env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                // Nested resources/ check
                let nested_py = exe_dir.join("resources").join("python-runtime").join("python.exe");
                let nested_script = exe_dir.join("resources").join("backend").join("src").join("ipc_worker.py");
                if nested_py.exists() && nested_script.exists() {
                    let py_path = exe_dir.join("resources").join("backend");
                    return Ok((nested_py, nested_script, Some(py_path.to_string_lossy().to_string())));
                }

                // Flat layout check
                let local_py = exe_dir.join("python-runtime").join("python.exe");
                let local_script = exe_dir.join("backend").join("src").join("ipc_worker.py");
                if local_py.exists() && local_script.exists() {
                    let py_path = exe_dir.join("backend");
                    return Ok((local_py, local_script, Some(py_path.to_string_lossy().to_string())));
                }
            }
        }

        // 3. Development workspace fallback: locate repository root
        let repo_root = self.find_dev_repo_root();
        let dev_script = repo_root.join("src").join("ipc_worker.py");

        if !dev_script.exists() {
            return Err(format!(
                "File backend Python tidak ditemukan di: {}",
                dev_script.display()
            ));
        }

        // Locate Python on system
        let python_candidates = [
            PathBuf::from("python"),
            PathBuf::from("python3"),
            PathBuf::from("py"),
            PathBuf::from("C:\\Users\\USER\\AppData\\Local\\Programs\\Python\\Python313\\python.exe"),
            PathBuf::from("C:\\Users\\USER\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"),
        ];

        for c in &python_candidates {
            if c.is_absolute() && c.exists() {
                return Ok((c.clone(), dev_script, Some(repo_root.to_string_lossy().to_string())));
            }
        }

        // Use standard "python" from PATH
        Ok((PathBuf::from("python"), dev_script, Some(repo_root.to_string_lossy().to_string())))
    }

    fn resolve_bundled_platform_tools_dir(&self) -> Option<PathBuf> {
        if let Ok(res_dir) = self.app_handle.path().resource_dir() {
            let pt_nested = res_dir.join("resources").join("platform-tools");
            if pt_nested.join("adb.exe").exists() {
                return Some(pt_nested);
            }
            let pt_flat = res_dir.join("platform-tools");
            if pt_flat.join("adb.exe").exists() {
                return Some(pt_flat);
            }
        }
        if let Ok(exe_path) = std::env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                let pt_nested = exe_dir.join("resources").join("platform-tools");
                if pt_nested.join("adb.exe").exists() {
                    return Some(pt_nested);
                }
                let pt_flat = exe_dir.join("platform-tools");
                if pt_flat.join("adb.exe").exists() {
                    return Some(pt_flat);
                }
            }
        }
        None
    }

    fn find_dev_repo_root(&self) -> PathBuf {
        if let Ok(cwd) = std::env::current_dir() {
            if cwd.join("src").join("ipc_worker.py").exists() {
                return cwd;
            }
            if cwd.join("adb-backup-tool").join("src").join("ipc_worker.py").exists() {
                return cwd.join("adb-backup-tool");
            }
            if let Some(parent) = cwd.parent() {
                if parent.join("src").join("ipc_worker.py").exists() {
                    return parent.to_path_buf();
                }
            }
        }
        PathBuf::from(".")
    }

    fn get_arc(&self) -> Arc<Self> {
        self.app_handle.state::<Arc<PythonSidecarManager>>().inner().clone()
    }

    fn read_stdout_loop(&self, stdout: impl std::io::Read) {
        let reader = BufReader::new(stdout);
        for line_res in reader.lines() {
            let line = match line_res {
                Ok(l) => l,
                Err(_) => break,
            };
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }

            let frame: Value = match serde_json::from_str(trimmed) {
                Ok(v) => v,
                Err(_) => continue,
            };

            let f_type = frame.get("type").and_then(|v| v.as_str()).unwrap_or("");

            if f_type == "response" {
                if let Some(id) = frame.get("id").and_then(|v| v.as_str()) {
                    let sender = self.pending_requests.lock().unwrap().remove(id);
                    if let Some(tx) = sender {
                        let ok = frame.get("ok").and_then(|v| v.as_bool()).unwrap_or(false);
                        if ok {
                            let res = frame.get("result").cloned().unwrap_or(Value::Null);
                            let _ = tx.send(Ok(res));
                        } else {
                            let err_msg = frame
                                .get("error")
                                .and_then(|e| e.get("message"))
                                .and_then(|m| m.as_str())
                                .unwrap_or("Unknown backend error")
                                .to_string();
                            let _ = tx.send(Err(err_msg));
                        }
                    }
                }
            } else if f_type == "event" {
                if let Some(event_name) = frame.get("event").and_then(|v| v.as_str()) {
                    let payload = frame.get("payload").cloned().unwrap_or(Value::Null);
                    self.handle_event(event_name, &payload);
                }
            }
        }

        self.handle_child_termination();
    }

    fn read_stderr_loop(&self, stderr: impl std::io::Read) {
        let reader = BufReader::new(stderr);
        for line_res in reader.lines() {
            let line = match line_res {
                Ok(l) => l,
                Err(_) => break,
            };
            let trimmed = line.trim();
            if !trimmed.is_empty() {
                let mut tail = self.stderr_tail.lock().unwrap();
                if tail.len() >= 50 {
                    tail.pop_front();
                }
                tail.push_back(trimmed.to_string());
            }
        }
    }

    fn handle_event(&self, event_name: &str, payload: &Value) {
        match event_name {
            "backend_ready" => {
                *self.cached_ready.lock().unwrap() = Some(payload.clone());
                if let Ok(st) = serde_json::from_value::<BackendDeviceStatus>(payload.clone()) {
                    *self.cached_status.lock().unwrap() = st;
                }
                self.emit_state_change("ready");
            }
            "device_status" => {
                if let Ok(st) = serde_json::from_value::<BackendDeviceStatus>(payload.clone()) {
                    *self.cached_status.lock().unwrap() = st;
                }
            }
            "prescan_progress" | "backup_progress" => {
                if let Some(job_id) = payload.get("job_id").and_then(|v| v.as_str()) {
                    *self.active_job_id.lock().unwrap() = Some(job_id.to_string());
                }
            }
            "backup_log" => {
                if let (Some(msg), Some(lvl), Some(ts)) = (
                    payload.get("message").and_then(|v| v.as_str()),
                    payload.get("level").and_then(|v| v.as_str()),
                    payload.get("timestamp").and_then(|v| v.as_str()),
                ) {
                    let session_id = payload.get("job_id").and_then(|v| v.as_str());
                    let _ = self.db.append_log(session_id, ts, lvl, msg);
                }
            }
            "backup_completed" => {
                *self.active_job_id.lock().unwrap() = None;
                self.persist_completed_backup(payload);
            }
            "prescan_completed" => {
                *self.active_job_id.lock().unwrap() = None;
            }
            _ => {}
        }

        // Forward event directly to React frontend
        let event_channel = format!("backend://{}", event_name);
        let _ = self.app_handle.emit(&event_channel, payload);
    }

    fn persist_completed_backup(&self, payload: &Value) {
        let meta = self.active_backup_meta.lock().unwrap().take();
        let job_id = payload
            .get("job_id")
            .and_then(|v| v.as_str())
            .unwrap_or_else(|| meta.as_ref().map(|m| m.job_id.as_str()).unwrap_or("unknown"));

        let status = payload.get("status").and_then(|v| v.as_str()).unwrap_or("completed");
        let files_transferred = payload.get("files_transferred").and_then(|v| v.as_i64()).unwrap_or(0);
        let files_skipped = payload.get("files_skipped").and_then(|v| v.as_i64()).unwrap_or(0);
        let files_failed = payload.get("files_failed").and_then(|v| v.as_i64()).unwrap_or(0);
        let bytes_transferred = payload.get("bytes_transferred").and_then(|v| v.as_i64()).unwrap_or(0);
        let duration = payload.get("duration_seconds").and_then(|v| v.as_i64()).unwrap_or(0);
        let error_msg = payload.get("error").and_then(|v| v.as_str()).map(|s| s.to_string());

        let finished_at = Utc::now().to_rfc3339();
        let started_at = meta
            .as_ref()
            .map(|m| m.started_at.clone())
            .unwrap_or_else(|| Utc::now().to_rfc3339());

        let record = BackupSessionRecord {
            id: job_id.to_string(),
            started_at,
            finished_at: Some(finished_at),
            duration_seconds: duration,
            device_serial: meta.as_ref().map(|m| m.serial.clone()).unwrap_or_default(),
            device_model: meta.as_ref().map(|m| m.device_model.clone()).unwrap_or_else(|| "Android Device".into()),
            device_android_version: meta.as_ref().map(|m| m.device_android_version.clone()).unwrap_or_default(),
            dest_dir: meta.as_ref().map(|m| m.dest_dir.clone()).unwrap_or_default(),
            targets_json: meta.as_ref().map(|m| m.targets_json.clone()).unwrap_or_else(|| "[]".into()),
            preserve_timestamps: meta.as_ref().map(|m| m.preserve_timestamps).unwrap_or(true),
            auto_subfolder: meta.as_ref().map(|m| m.auto_subfolder).unwrap_or(false),
            smart_auto_skip: meta.as_ref().map(|m| m.smart_auto_skip).unwrap_or(true),
            files_transferred,
            files_skipped,
            files_failed,
            bytes_transferred,
            status: status.to_string(),
            error_message: error_msg,
        };

        let _ = self.db.record_backup_session(&record);
    }

    fn handle_child_termination(&self) {
        let was_shutting_down = self.is_shutting_down.load(Ordering::SeqCst);

        {
            let mut state = self.child_state.lock().unwrap();
            *state = None;
        }

        // Cancel and fail any remaining pending request channels
        {
            let mut pending = self.pending_requests.lock().unwrap();
            for (_, tx) in pending.drain() {
                let _ = tx.send(Err("Proses backend Python terhenti secara tidak terduga.".into()));
            }
        }

        *self.active_job_id.lock().unwrap() = None;

        if !was_shutting_down {
            self.emit_state_change("crashed");
        } else {
            self.emit_state_change("stopped");
        }
    }

    fn emit_state_change(&self, state: &str) {
        let snap = self.get_state_snapshot(state);
        let _ = self.app_handle.emit("backend://status", &snap);
    }

    pub fn get_state_snapshot(&self, forced_state: &str) -> BackendStateSnapshot {
        let child_guard = self.child_state.lock().unwrap();
        let st_guard = self.cached_status.lock().unwrap();
        let ready_guard = self.cached_ready.lock().unwrap();
        let stderr_guard = self.stderr_tail.lock().unwrap();
        let job_guard = self.active_job_id.lock().unwrap();

        let state_str = if !forced_state.is_empty() {
            forced_state.to_string()
        } else if child_guard.is_some() {
            if ready_guard.is_some() {
                "ready".into()
            } else {
                "starting".into()
            }
        } else {
            "stopped".into()
        };

        let (pid, py_path, script_path) = match &*child_guard {
            Some(c) => (Some(c.pid), Some(c.python_path.clone()), Some(c.script_path.clone())),
            None => (None, None, None),
        };

        let py_ver = ready_guard
            .as_ref()
            .and_then(|v| v.get("python_version"))
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());

        BackendStateSnapshot {
            state: state_str,
            pid,
            python_version: py_ver,
            python_path: py_path,
            backend_script: script_path,
            adb_available: st_guard.adb_available,
            adb_path: st_guard.adb_path.clone(),
            adb_version: st_guard.adb_version.clone(),
            custom_adb_path: st_guard.custom_adb_path.clone(),
            devices: st_guard.devices.clone(),
            active_job_id: job_guard.clone(),
            last_error: st_guard.error.clone(),
            stderr_tail: stderr_guard.iter().cloned().collect(),
        }
    }

    pub fn send_request(&self, method: &str, params: Value, timeout_secs: u64) -> Result<Value, String> {
        let req_id = Uuid::new_v4().to_string();
        let (tx, rx) = mpsc::channel();

        {
            let mut pending = self.pending_requests.lock().unwrap();
            pending.insert(req_id.clone(), tx);
        }

        let msg = json!({
            "id": req_id,
            "method": method,
            "params": params,
        });
        let line = format!("{}\n", serde_json::to_string(&msg).map_err(|e| e.to_string())?);

        {
            let mut state_guard = self.child_state.lock().unwrap();
            let state = state_guard
                .as_mut()
                .ok_or("Backend Python belum aktif atau sedang berhenti.")?;

            state
                .stdin
                .write_all(line.as_bytes())
                .map_err(|e| format!("Gagal menulis ke stdin backend: {}", e))?;
            state
                .stdin
                .flush()
                .map_err(|e| format!("Gagal flush stdin backend: {}", e))?;
        }

        let timeout = Duration::from_secs(timeout_secs);
        match rx.recv_timeout(timeout) {
            Ok(result) => result,
            Err(mpsc::RecvTimeoutError::Timeout) => {
                self.pending_requests.lock().unwrap().remove(&req_id);
                Err(format!("Permintaan backend '{}' melebihi batas waktu ({}s)", method, timeout_secs))
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                self.pending_requests.lock().unwrap().remove(&req_id);
                Err("Saluran komunikasi backend terputus.".into())
            }
        }
    }

    pub fn set_active_backup_meta(&self, meta: ActiveBackupMeta) {
        *self.active_backup_meta.lock().unwrap() = Some(meta);
    }

    pub fn cancel_backup(&self) -> Result<Value, String> {
        self.send_request("cancel_backup", json!({}), 5)
    }

    pub fn shutdown(&self) {
        self.is_shutting_down.store(true, Ordering::SeqCst);

        // Send graceful shutdown command
        let _ = self.send_request("shutdown", json!({}), 2);

        // Terminate child process if still active
        let mut child_guard = self.child_state.lock().unwrap();
        if let Some(mut state) = child_guard.take() {
            let _ = state.child.kill();
            let _ = state.child.wait();
        }
    }
}

