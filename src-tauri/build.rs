fn main() {
    tauri_build::build();

    // Ensure Windows test executables also receive the generated resource manifest
    // (required for comctl32 v6 symbols such as TaskDialogIndirect pulled in by rfd).
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        if let Ok(out_dir) = std::env::var("OUT_DIR") {
            for candidate in ["libresource.a", "resource.lib"] {
                let res_path = std::path::Path::new(&out_dir).join(candidate);
                if res_path.exists() {
                    println!("cargo:rustc-link-arg-tests={}", res_path.display());
                    break;
                }
            }
        }
    }
}
