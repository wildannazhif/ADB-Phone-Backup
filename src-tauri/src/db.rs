use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use chrono::Utc;
use rusqlite::{params, Connection, OptionalExtension, Result};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppSettings {
    pub theme: String,
    pub default_backup_dir: String,
    pub custom_adb_path: String,
    pub auto_subfolder: bool,
    pub preserve_timestamps: bool,
    pub smart_auto_skip: bool,
    pub default_dcim: bool,
    pub default_documents: bool,
    pub default_pictures: bool,
    pub default_whatsapp: bool,
    pub custom_folders: Vec<String>,
    pub max_log_lines: u32,
    pub auto_open_destination: bool,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            theme: "dark".to_string(),
            default_backup_dir: String::new(),
            custom_adb_path: String::new(),
            auto_subfolder: false,
            preserve_timestamps: true,
            smart_auto_skip: true,
            default_dcim: true,
            default_documents: true,
            default_pictures: true,
            default_whatsapp: true,
            custom_folders: Vec::new(),
            max_log_lines: 2000,
            auto_open_destination: false,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackupSessionRecord {
    pub id: String,
    pub started_at: String,
    pub finished_at: Option<String>,
    pub duration_seconds: i64,
    pub device_serial: String,
    pub device_model: String,
    pub device_android_version: String,
    pub dest_dir: String,
    pub targets_json: String,
    pub preserve_timestamps: bool,
    pub auto_subfolder: bool,
    pub smart_auto_skip: bool,
    pub files_transferred: i64,
    pub files_skipped: i64,
    pub files_failed: i64,
    pub bytes_transferred: i64,
    pub status: String,
    pub error_message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DashboardOverview {
    pub last_backup_date: Option<String>,
    pub total_backup_files: i64,
    pub total_backup_bytes: i64,
    pub default_backup_dir: String,
    pub recent_sessions: Vec<BackupSessionRecord>,
    pub total_sessions_count: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEntry {
    pub id: i64,
    pub session_id: Option<String>,
    pub timestamp: String,
    pub level: String,
    pub message: String,
}

#[derive(Clone)]
pub struct AppDatabase {
    conn: Arc<Mutex<Connection>>,
    db_path: PathBuf,
}

impl AppDatabase {
    pub fn new(db_path: &Path) -> Result<Self> {
        if let Some(parent) = db_path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        let conn = Connection::open(db_path)?;
        let db = Self {
            conn: Arc::new(Mutex::new(conn)),
            db_path: db_path.to_path_buf(),
        };
        db.init_schema()?;
        Ok(db)
    }

    pub fn new_in_memory() -> Result<Self> {
        let conn = Connection::open_in_memory()?;
        let db = Self {
            conn: Arc::new(Mutex::new(conn)),
            db_path: PathBuf::from(":memory:"),
        };
        db.init_schema()?;
        Ok(db)
    }

    pub fn get_db_path(&self) -> PathBuf {
        self.db_path.clone()
    }

    fn init_schema(&self) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute_batch(
            "
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous = NORMAL;
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS backup_sessions (
                id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds INTEGER NOT NULL,
                device_serial TEXT NOT NULL,
                device_model TEXT NOT NULL,
                device_android_version TEXT NOT NULL,
                dest_dir TEXT NOT NULL,
                targets_json TEXT NOT NULL,
                preserve_timestamps INTEGER NOT NULL,
                auto_subfolder INTEGER NOT NULL,
                smart_auto_skip INTEGER NOT NULL,
                files_transferred INTEGER NOT NULL,
                files_skipped INTEGER NOT NULL,
                files_failed INTEGER NOT NULL,
                bytes_transferred INTEGER NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS app_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON backup_sessions(started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON app_logs(id DESC);
            ",
        )?;
        Ok(())
    }

    pub fn get_settings(&self) -> Result<AppSettings> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare("SELECT value FROM settings WHERE key = 'app_settings'")?;
        let json_str: Option<String> = stmt.query_row([], |row| row.get(0)).optional()?;

        match json_str {
            Some(raw) => Ok(serde_json::from_str::<AppSettings>(&raw).unwrap_or_default()),
            None => Ok(AppSettings::default()),
        }
    }

    pub fn update_settings(&self, settings: &AppSettings) -> Result<AppSettings> {
        let conn = self.conn.lock().unwrap();
        let json_str = serde_json::to_string(settings).unwrap_or_else(|_| "{}".to_string());
        let now = Utc::now().to_rfc3339();

        conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES ('app_settings', ?1, ?2)
             ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            params![json_str, now],
        )?;

        Ok(settings.clone())
    }

    pub fn record_backup_session(&self, s: &BackupSessionRecord) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO backup_sessions (
                id, started_at, finished_at, duration_seconds, device_serial,
                device_model, device_android_version, dest_dir, targets_json,
                preserve_timestamps, auto_subfolder, smart_auto_skip,
                files_transferred, files_skipped, files_failed, bytes_transferred,
                status, error_message
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18)
            ON CONFLICT(id) DO UPDATE SET
                finished_at = excluded.finished_at,
                duration_seconds = excluded.duration_seconds,
                files_transferred = excluded.files_transferred,
                files_skipped = excluded.files_skipped,
                files_failed = excluded.files_failed,
                bytes_transferred = excluded.bytes_transferred,
                status = excluded.status,
                error_message = excluded.error_message",
            params![
                s.id,
                s.started_at,
                s.finished_at,
                s.duration_seconds,
                s.device_serial,
                s.device_model,
                s.device_android_version,
                s.dest_dir,
                s.targets_json,
                if s.preserve_timestamps { 1 } else { 0 },
                if s.auto_subfolder { 1 } else { 0 },
                if s.smart_auto_skip { 1 } else { 0 },
                s.files_transferred,
                s.files_skipped,
                s.files_failed,
                s.bytes_transferred,
                s.status,
                s.error_message,
            ],
        )?;
        Ok(())
    }

    pub fn list_backup_sessions(&self, limit: usize, offset: usize) -> Result<Vec<BackupSessionRecord>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT id, started_at, finished_at, duration_seconds, device_serial,
                    device_model, device_android_version, dest_dir, targets_json,
                    preserve_timestamps, auto_subfolder, smart_auto_skip,
                    files_transferred, files_skipped, files_failed, bytes_transferred,
                    status, error_message
             FROM backup_sessions
             ORDER BY started_at DESC
             LIMIT ?1 OFFSET ?2",
        )?;

        let rows = stmt.query_map(params![limit as i64, offset as i64], |row| {
            Ok(BackupSessionRecord {
                id: row.get(0)?,
                started_at: row.get(1)?,
                finished_at: row.get(2)?,
                duration_seconds: row.get(3)?,
                device_serial: row.get(4)?,
                device_model: row.get(5)?,
                device_android_version: row.get(6)?,
                dest_dir: row.get(7)?,
                targets_json: row.get(8)?,
                preserve_timestamps: row.get::<_, i64>(9)? != 0,
                auto_subfolder: row.get::<_, i64>(10)? != 0,
                smart_auto_skip: row.get::<_, i64>(11)? != 0,
                files_transferred: row.get(12)?,
                files_skipped: row.get(13)?,
                files_failed: row.get(14)?,
                bytes_transferred: row.get(15)?,
                status: row.get(16)?,
                error_message: row.get(17)?,
            })
        })?;

        let mut list = Vec::new();
        for r in rows {
            list.push(r?);
        }
        Ok(list)
    }

    pub fn get_dashboard_overview(&self, settings_dest: &str) -> Result<DashboardOverview> {
        let conn = self.conn.lock().unwrap();

        let (total_files, total_bytes, count): (i64, i64, i64) = conn.query_row(
            "SELECT COALESCE(SUM(files_transferred), 0), COALESCE(SUM(bytes_transferred), 0), COUNT(*)
             FROM backup_sessions
             WHERE status IN ('completed', 'completed_with_errors')",
            [],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
        )?;

        let last_session: Option<(String, String)> = conn
            .query_row(
                "SELECT started_at, dest_dir FROM backup_sessions ORDER BY started_at DESC LIMIT 1",
                [],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()?;

        drop(conn);

        let recent = self.list_backup_sessions(5, 0)?;

        let (last_date, effective_dest) = match last_session {
            Some((dt, d)) => {
                let dest = if !settings_dest.is_empty() {
                    settings_dest.to_string()
                } else {
                    d
                };
                (Some(dt), dest)
            }
            None => (None, settings_dest.to_string()),
        };

        Ok(DashboardOverview {
            last_backup_date: last_date,
            total_backup_files: total_files,
            total_backup_bytes: total_bytes,
            default_backup_dir: effective_dest,
            recent_sessions: recent,
            total_sessions_count: count,
        })
    }

    pub fn clear_backup_history(&self) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute("DELETE FROM backup_sessions", [])?;
        conn.execute("DELETE FROM app_logs", [])?;
        Ok(())
    }

    pub fn append_log(&self, session_id: Option<&str>, timestamp: &str, level: &str, message: &str) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO app_logs (session_id, timestamp, level, message) VALUES (?1, ?2, ?3, ?4)",
            params![session_id, timestamp, level, message],
        )?;
        Ok(())
    }

    pub fn list_logs(&self, limit: usize) -> Result<Vec<LogEntry>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT id, session_id, timestamp, level, message FROM app_logs ORDER BY id DESC LIMIT ?1",
        )?;
        let rows = stmt.query_map(params![limit as i64], |row| {
            Ok(LogEntry {
                id: row.get(0)?,
                session_id: row.get(1)?,
                timestamp: row.get(2)?,
                level: row.get(3)?,
                message: row.get(4)?,
            })
        })?;

        let mut list = Vec::new();
        for r in rows {
            list.push(r?);
        }
        list.reverse();
        Ok(list)
    }

    pub fn clear_logs(&self) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute("DELETE FROM app_logs", [])?;
        Ok(())
    }

    pub fn get_log_count(&self) -> Result<i64> {
        let conn = self.conn.lock().unwrap();
        conn.query_row("SELECT COUNT(*) FROM app_logs", [], |row| row.get(0))
    }
}

