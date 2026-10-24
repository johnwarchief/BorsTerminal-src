# TinyJS shell prototype (M1)

Minimal TinyJS wrapper around the same loopback prototype URL as the Tauri and
pywebview shells:

```
http://127.0.0.1:8105/
```

TinyJS loads the URL directly, so the production `loopback_guard` sees a
loopback origin and keeps working. The wrapper exposes only window controls
(`win.close`, `win.minimize`, `win.zoom`, `win.startDrag`); every other native
API is disabled in `tinyjs.json`.

## Build

```bash
# TinyJS 0.65.0 toolchain, not vendored
cd prototypes/tinyjs-m1
../../_tools/tinyjs/tinyjs.cmd build
# output: dist/BorsTerminalM1TinyJS.exe (+ launcher.exe)
```

This directory keeps only the wrapper source/config. The generated binary is a
measurement artifact and is not committed.

## Measurement limitation

The TinyJS launcher does not forward
`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`, so WebView2 CDP is unavailable.
`tools/desktop-migration/bench_tinyjs.py` measures window appearance, TinyJS
navigation log, API completion through the proxy log, Win32 PrintWindow
screenshots and process-tree RAM instead. In-page JS heap, console errors and
rAF frame times are NOT_MEASURED for this shell.
