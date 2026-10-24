#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

// Phase E Tauri v2 shell. It owns the Python sidecar, verifies the loopback
// backend before showing the window, injects the same in-page probe through
// WebView2 eval, and lets the sidecar finish uvicorn's shutdown before exit.
// The window loads the loopback origin directly: no IPC, no proxy, no CORS
// bypass, no Origin rewriting.

use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::process::{Child, Command, Stdio};
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tauri::{Manager, WebviewWindow, WindowEvent};

#[derive(Clone)]
struct SidecarState {
    child: Arc<Mutex<Option<Child>>>,
    closing: Arc<AtomicBool>,
}

fn env_or(name: &str, fallback: &str) -> String {
    std::env::var(name).unwrap_or_else(|_| fallback.to_string())
}

fn now_secs() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn trace(stage: &str, port: Option<u16>, detail: Option<&str>) {
    let path = env_or("BORS_SHELL_TRACE", "");
    if path.is_empty() {
        return;
    }
    let rec = serde_json::json!({
        "stage": stage,
        "t": now_secs(),
        "dt": 0.0,
        "pid": std::process::id(),
        "port": port,
        "detail": detail,
    });
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(f, "{}", rec);
    }
}

fn append_log(path: &str, line: &str) {
    if path.is_empty() {
        return;
    }
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(f, "{}", line);
    }
}

fn log_path() -> String {
    let root = env_or("BORS_WORK_DIR", "");
    if root.is_empty() {
        return String::new();
    }
    let dir = std::path::Path::new(&root).join("logs");
    let _ = fs::create_dir_all(&dir);
    dir.join("sidecar.log").to_string_lossy().to_string()
}

fn http_ok(port: u16) -> bool {
    let mut stream = match TcpStream::connect(("127.0.0.1", port)) {
        Ok(s) => s,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(5)));
    let req = format!(
        "GET /api/update/version HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n",
        port
    );
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }
    let mut buf = [0u8; 64];
    match stream.read(&mut buf) {
        Ok(n) if n > 0 => {
            let head = String::from_utf8_lossy(&buf[..n]);
            head.starts_with("HTTP/1.1 200") || head.starts_with("HTTP/1.0 200")
        }
        _ => false,
    }
}

fn spawn_and_verify() -> Result<(Child, u16), String> {
    let py = env_or("BORS_PYTHON", "");
    let entry = env_or("BORS_HEADLESS_ENTRY", "");
    if py.is_empty() || entry.is_empty() {
        return Err("BORS_PYTHON/BORS_HEADLESS_ENTRY are not set".to_string());
    }
    trace("sidecar_spawn_begin", None, None);
    let mut cmd = Command::new(&py);
    cmd.arg(&entry)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env("BORS_SHOW_CONSOLE", "1");
    #[cfg(windows)]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW: no stray console beside the app
    let mut child = cmd
        .spawn()
        .map_err(|e| format!("spawn {}: {}", py, e))?;
    trace("sidecar_spawned", None, None);

    let stdout = child.stdout.take().ok_or("no sidecar stdout")?;
    let log = log_path();
    if let Some(mut stderr) = child.stderr.take() {
        let log2 = log.clone();
        thread::spawn(move || {
            let mut reader = BufReader::new(&mut stderr);
            let mut line = String::new();
            loop {
                line.clear();
                match reader.read_line(&mut line) {
                    Ok(0) | Err(_) => break,
                    Ok(_) => append_log(&log2, line.trim_end()),
                }
            }
        });
    }

    let (tx, rx) = mpsc::channel::<String>();
    let log2 = log.clone();
    thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines().flatten() {
            append_log(&log2, &line);
            let _ = tx.send(line);
        }
    });

    let start = Instant::now();
    let mut last: Vec<String> = Vec::new();
    let mut port: Option<u16> = None;
    while start.elapsed() < Duration::from_secs(240) {
        match rx.recv_timeout(Duration::from_millis(250)) {
            Ok(line) => {
                last.push(line.clone());
                if last.len() > 24 {
                    last.remove(0);
                }
                if let Some(rest) = line.strip_prefix("PHASE_D_READY ") {
                    let v: serde_json::Value = serde_json::from_str(rest)
                        .map_err(|e| format!("READY json: {}", e))?;
                    let p = v.get("port").and_then(|x| x.as_u64())
                        .ok_or("READY has no port")? as u16;
                    port = Some(p);
                    break;
                }
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {
                if let Ok(Some(st)) = child.try_wait() {
                    return Err(format!("sidecar exited before ready ({:?})\n{}",
                                       st.code(), last.join("\n")));
                }
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                let _ = child.kill();
                return Err(format!("sidecar stdout closed before ready\n{}", last.join("\n")));
            }
        }
    }
    let port = match port {
        Some(p) => p,
        None => {
            let _ = child.kill();
            return Err(format!("sidecar READY timeout\n{}", last.join("\n")));
        }
    };
    trace("sidecar_ready_line", Some(port), None);
    for _ in 0..40 {
        if http_ok(port) {
            trace("http_verified", Some(port), None);
            return Ok((child, port));
        }
        if let Ok(Some(st)) = child.try_wait() {
            return Err(format!("sidecar exited after READY ({:?})", st.code()));
        }
        thread::sleep(Duration::from_millis(250));
    }
    let _ = child.kill();
    Err(format!("HTTP verification failed on port {}", port))
}

fn show_error(win: &WebviewWindow, message: &str) {
    let _ = win.set_title("BorsTerminal — startup failed");
    let html = format!(
        "<!doctype html><html lang=\"fa\" dir=\"rtl\"><meta charset=\"utf-8\">\
         <style>html,body{{height:100%;margin:0;background:#0b0f17;color:#e6edf7;\
         font:14px/1.9 Tahoma,'Segoe UI',sans-serif}}.w{{min-height:100%;display:flex;\
         align-items:center;justify-content:center;padding:24px}}.c{{width:min(680px,100%);\
         background:#111827;border:1px solid #1f2a3a;border-radius:16px;padding:26px}}\
         h1{{font-size:17px;margin:0 0 10px;color:#fca5a5}}pre{{white-space:pre-wrap;\
         font-size:12px;color:#cfe3ff;background:#0b1220;padding:12px;border-radius:8px}}\
         </style><div class=\"w\"><div class=\"c\"><h1>Backend could not start</h1>\
         <pre id=\"m\"></pre></div></div><script>document.getElementById('m').textContent={};\
         </script></html>",
        serde_json::to_string(message).unwrap_or_else(|_| "\"error\"".to_string())
    );
    let js = format!(
        "document.open();document.write({});document.close();",
        serde_json::to_string(&html).unwrap_or_else(|_| "\"\"".to_string())
    );
    let _ = win.eval(js);
    let _ = win.show();
    let _ = win.maximize();
    trace("error_window", None, Some(message));
}

fn start_probe(win: WebviewWindow) {
    let path = env_or("BORS_PROBE_SCRIPT", "");
    let collector = env_or("BORS_COLLECTOR_PORT", "");
    if path.is_empty() || collector.is_empty() {
        return;
    }
    let mut source = match fs::read_to_string(&path) {
        Ok(s) => s.replace("__BORS_COLLECTOR__", &collector),
        Err(e) => {
            trace("probe_read_failed", None, Some(&e.to_string()));
            return;
        }
    };
    if env_or("BORS_VISUAL", "0") == "1" {
        source = format!("window.__BORS_VISUAL__=true;{}", source);
    }
    if env_or("BORS_D3_CHECKS", "0") == "1" {
        let sym = env_or("BORS_SYMBOL2", "");
        source = format!(
            "window.__BORS_D3_CHECKS__=true;window.__BORS_SYMBOL2__={};{}",
            serde_json::to_string(&sym).unwrap_or_else(|_| "\"\"".to_string()),
            source
        );
    }
    let stop = env_or("BORS_PROBE_STOP_FILE", "");
    thread::spawn(move || {
        // Re-inject: the first eval may land on about:blank before the loopback
        // document commits. The probe is idempotent via window.__borsPhaseDProbe.
        let mut injected = false;
        for i in 0..40 {
            if !stop.is_empty() && std::path::Path::new(&stop).exists() {
                trace("probe_stop_file", None, None);
                break;
            }
            if win.eval(source.clone()).is_ok() {
                if !injected {
                    injected = true;
                    trace("probe_eval", None, None);
                }
            } else if !injected {
                trace("probe_eval_failed", None, None);
            }
            if i == 39 {
                break;
            }
            thread::sleep(Duration::from_millis(900));
        }
    });
}

fn monitor_sidecar(win: WebviewWindow, slot: Arc<Mutex<Option<Child>>>, closing: Arc<AtomicBool>) {
    loop {
        thread::sleep(Duration::from_millis(1000));
        if closing.load(Ordering::SeqCst) {
            return;
        }
        let status = {
            let mut guard = slot.lock().unwrap();
            match guard.as_mut() {
                Some(child) => match child.try_wait() {
                    Ok(v) => v,
                    Err(_) => None,
                },
                None => return,
            }
        };
        if let Some(st) = status {
            trace("sidecar_exit", None, Some(&format!("{:?}", st.code())));
            if !closing.load(Ordering::SeqCst) {
                show_error(&win, &format!("Backend stopped unexpectedly (exit {:?}).", st.code()));
            }
            return;
        }
    }
}

fn main() {
    tauri::Builder::default()
        .manage(SidecarState {
            child: Arc::new(Mutex::new(None)),
            closing: Arc::new(AtomicBool::new(false)),
        })
        .setup(|app| {
            let window = app
                .get_webview_window("main")
                .ok_or_else(|| "main window missing".to_string())?;
            let state = app.state::<SidecarState>();
            let slot = state.child.clone();
            let closing = state.closing.clone();
            let win = window.clone();
            thread::spawn(move || {
                trace("backend_init", None, None);
                match spawn_and_verify() {
                    Ok((child, port)) => {
                        *slot.lock().unwrap() = Some(child);
                        let url = match tauri::Url::parse(&format!("http://127.0.0.1:{}/", port)) {
                            Ok(u) => u,
                            Err(e) => {
                                show_error(&win, &format!("invalid loopback URL: {}", e));
                                return;
                            }
                        };
                        trace("window_open_begin", Some(port), None);
                        if let Err(e) = win.navigate(url) {
                            show_error(&win, &format!("window navigation failed: {}", e));
                            return;
                        }
                        let _ = win.maximize();
                        let _ = win.show();
                        trace("window_open", Some(port), None);
                        start_probe(win.clone());
                        monitor_sidecar(win.clone(), slot.clone(), closing.clone());
                    }
                    Err(e) => show_error(&win, &e),
                }
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let state = window.app_handle().state::<SidecarState>().inner().clone();
                if state.closing.swap(true, Ordering::SeqCst) {
                    return;
                }
                trace("window_closed", None, None);
                trace("shutdown_wait_begin", None, None);
                let slot = state.child.clone();
                let handle = window.app_handle().clone();
                thread::spawn(move || {
                    let mut graceful = false;
                    if let Some(mut child) = slot.lock().unwrap().take() {
                        drop(child.stdin.take());
                        let start = Instant::now();
                        loop {
                            match child.try_wait() {
                                Ok(Some(st)) => {
                                    graceful = true;
                                    trace("sidecar_exit", None, Some(&format!("{:?}", st.code())));
                                    break;
                                }
                                Ok(None) => {
                                    if start.elapsed() > Duration::from_secs(15) {
                                        let _ = child.kill();
                                        break;
                                    }
                                    thread::sleep(Duration::from_millis(100));
                                }
                                Err(_) => break,
                            }
                        }
                    }
                    trace("shutdown_wait_done", None, Some(if graceful { "graceful" } else { "timeout" }));
                    trace("quit_requested", None, None);
                    handle.exit(0);
                });
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running BorsTerminal Tauri shell");
}
