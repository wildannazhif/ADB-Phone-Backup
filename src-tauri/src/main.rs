#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    adb_phone_backup_lib::run();
}
