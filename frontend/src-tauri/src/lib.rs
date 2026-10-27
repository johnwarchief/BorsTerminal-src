use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::menu::{CheckMenuItemBuilder, MenuBuilder, MenuItemBuilder};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder, WindowEvent};

#[derive(serde::Serialize, serde::Deserialize, Default)]
struct ShellSettings {
    version: u32,
    close_action: String,
}

struct ShellState {
    close_to_tray: AtomicBool,
    settings_path: Option<PathBuf>,
}

impl ShellState {
    fn from_settings(path: &Option<PathBuf>) -> Self {
        let mut close_to_tray = false;
        if let Some(p) = path {
            if let Ok(txt) = std::fs::read_to_string(p) {
                if let Ok(s) = serde_json::from_str::<ShellSettings>(&txt) {
                    close_to_tray = s.close_action == "tray";
                }
            }
        }
        Self {
            close_to_tray: AtomicBool::new(close_to_tray),
            settings_path: path.clone(),
        }
    }

    fn write(&self, close_to_tray: bool) {
        let Some(p) = &self.settings_path else { return };
        let s = ShellSettings {
            version: 1,
            close_action: if close_to_tray { "tray".into() } else { "exit".into() },
        };
        if let Ok(txt) = serde_json::to_string_pretty(&s) {
            let _ = std::fs::write(p, txt);
        }
    }
}

#[derive(Default)]
struct Args {
    url: Option<String>,
    profile: Option<PathBuf>,
    settings: Option<PathBuf>,
    ready: Option<PathBuf>,
    parent_pid: Option<u32>,
}

impl Args {
    fn from_iter<I: Iterator<Item = String>>(iter: I) -> Self {
        let mut a = Args::default();
        let mut it = iter;
        while let Some(k) = it.next() {
            let Some(v) = it.next() else { break };
            match k.as_str() {
                "--url" => a.url = Some(v),
                "--profile" => a.profile = Some(PathBuf::from(v)),
                "--settings" => a.settings = Some(PathBuf::from(v)),
                "--ready" => a.ready = Some(PathBuf::from(v)),
                "--parent-pid" => a.parent_pid = v.parse().ok(),
                _ => {}
            }
        }
        a
    }

    fn parse() -> Self {
        Self::from_iter(std::env::args().skip(1))
    }
}

fn write_ready(path: &Option<PathBuf>, url: Option<&str>) {
    let Some(p) = path else { return };
    let url_json = serde_json::to_string(&url.unwrap_or("")).unwrap_or_else(|_| "\"\"".into());
    let body = format!("{{\"pid\":{},\"url\":{}}}", std::process::id(), url_json);
    let _ = std::fs::write(p, body);
}

#[cfg(windows)]
fn watch_parent(pid: u32, app: tauri::AppHandle) {
    use windows_sys::Win32::Foundation::CloseHandle;
    use windows_sys::Win32::System::Threading::{OpenProcess, WaitForSingleObject, INFINITE};
    const SYNCHRONIZE: u32 = 0x0010_0000;

    std::thread::spawn(move || unsafe {
        let h = OpenProcess(SYNCHRONIZE, 0, pid);
        if h.is_null() {
            return;
        }
        WaitForSingleObject(h, INFINITE);
        CloseHandle(h);
        app.exit(0);
    });
}

#[cfg(not(windows))]
fn watch_parent(_pid: u32, _app: tauri::AppHandle) {}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let args = Args::parse();
            let state = ShellState::from_settings(&args.settings);
            let close_to_tray = state.close_to_tray.load(Ordering::Relaxed);
            app.manage(state);

            let builder = match args.url.as_deref() {
                Some(u) => {
                    let url: tauri::Url = u.parse()?;
                    WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                }
                None => {
                    WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                }
            };
            let mut builder = builder
                .title("بورس‌ترمینال — BorsTerminal")
                .inner_size(1440.0, 900.0)
                .min_inner_size(1024.0, 640.0)
                .maximized(true)
                .visible(false);
            if let Some(p) = &args.profile {
                builder = builder.data_directory(p.clone());
            }
            let win = builder.build()?;

            let app_handle = app.handle().clone();
            let win_for_close = win.clone();
            win.on_window_event(move |event| {
                if let WindowEvent::CloseRequested { api, .. } = event {
                    let state = app_handle.state::<ShellState>();
                    if state.close_to_tray.load(Ordering::Relaxed) {
                        api.prevent_close();
                        let _ = win_for_close.hide();
                    }
                }
            });

            let show_item = MenuItemBuilder::with_id("show", "نمایشِ پنجره").build(app)?;
            let close_item =
                CheckMenuItemBuilder::with_id("close_tray", "بستنِ پنجره → System Tray")
                    .checked(close_to_tray)
                    .build(app)?;
            let quit_item = MenuItemBuilder::with_id("quit", "خروج").build(app)?;
            let menu = MenuBuilder::new(app)
                .items(&[&show_item, &close_item, &quit_item])
                .build()?;

            let mut tray_builder = TrayIconBuilder::with_id("main")
                .tooltip("بورس‌ترمینال")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(move |app, event| match event.id().as_ref() {
                    "show" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "close_tray" => {
                        let state = app.state::<ShellState>();
                        let new_value = !state.close_to_tray.load(Ordering::Relaxed);
                        state.close_to_tray.store(new_value, Ordering::Relaxed);
                        state.write(new_value);
                        let _ = close_item.set_checked(new_value);
                    }
                    "quit" => app.exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                });
            if let Some(icon) = app.handle().default_window_icon() {
                tray_builder = tray_builder.icon(icon.clone());
            }
            let tray = tray_builder.build(app)?;
            app.manage(tray);

            win.show()?;
            write_ready(&args.ready, args.url.as_deref());
            if let Some(pid) = args.parent_pid {
                watch_parent(pid, app.handle().clone());
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn args_parse_all() {
        let a = Args::from_iter(
            [
                "--url",
                "http://127.0.0.1:8001/",
                "--profile",
                "C:\\p",
                "--settings",
                "C:\\s.json",
                "--ready",
                "C:\\r.json",
                "--parent-pid",
                "123",
            ]
            .iter()
            .map(|s| s.to_string()),
        );
        assert_eq!(a.url.as_deref(), Some("http://127.0.0.1:8001/"));
        assert_eq!(a.parent_pid, Some(123));
        assert!(a.profile.is_some());
        assert!(a.settings.is_some());
        assert!(a.ready.is_some());
    }

    #[test]
    fn settings_default_to_exit_when_missing() {
        let st = ShellState::from_settings(&Some(PathBuf::from("Z:\\no\\such.json")));
        assert!(!st.close_to_tray.load(Ordering::Relaxed));
    }

    #[test]
    fn settings_roundtrip_tray_and_exit() {
        let dir = std::env::temp_dir().join(format!("bors_shell_test_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let p = dir.join("shell_settings.json");
        let st = ShellState {
            close_to_tray: AtomicBool::new(false),
            settings_path: Some(p.clone()),
        };
        st.write(true);
        assert!(ShellState::from_settings(&Some(p.clone()))
            .close_to_tray
            .load(Ordering::Relaxed));
        st.write(false);
        assert!(!ShellState::from_settings(&Some(p.clone()))
            .close_to_tray
            .load(Ordering::Relaxed));
        let _ = std::fs::remove_dir_all(&dir);
    }
}
