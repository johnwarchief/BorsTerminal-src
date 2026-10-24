# Tauri v2 shell prototype (M1)

This is a deliberately minimal Tauri v2 project used only to measure the shell.
It loads the same loopback URL as the pywebview prototype:

```
http://127.0.0.1:8105/
```

There is **no IPC** and **no sidecar wiring** in this prototype. The production
repo's existing `frontend/src-tauri` has no backend sidecar either (the release
workflow says so explicitly), so this prototype isolates the window/WebView2
cost while keeping the real Python backend and the origin guard unchanged.

## Build prerequisites (upstream requirements)

- Rust stable (`x86_64-pc-windows-msvc`) — the officially supported Windows target.
- Visual Studio C++ Build Tools with the Windows SDK.
- WebView2 runtime (already present on this machine: 155.0.4283.62).

```bash
cargo build --release --manifest-path prototypes/tauri-m1/src-tauri/Cargo.toml
```

The binary is `prototypes/tauri-m1/src-tauri/target/release/bors-m1-shell.exe`.
Start the prototype server first; the window is blank-by-design until
`127.0.0.1:8105` is up.

On this machine no MSVC build tools/admin were available, so the measured binary
was built with the **unofficial GNU target** after installing a local Rust
toolchain (`x86_64-pc-windows-gnu`) and MinGW:

```bash
export PATH="$PWD/_tools/rust/cargo/bin:$PWD/_tools/mingw/mingw64/bin:$PATH"
export CARGO_HOME="$PWD/_tools/rust/cargo" RUSTUP_HOME="$PWD/_tools/rust/rustup"
cargo build --release --manifest-path prototypes/tauri-m1/src-tauri/Cargo.toml
```

The build finished in 41m31s and produced a working 21.5 MB binary (CDP and both
pages verified), but it emitted `linker stderr: .rsrc merge failure: multiple
non-default manifests`. The MSVC build, installer, updater, tray, sidecar and code
signing are **not** implemented or measured. See the M0/M1 report for the full
limitations.

## Why the window URL is external

The production guard accepts only `127.0.0.1` / `localhost` / `::1` origins.
Tauri's bundled frontend on Windows is served from `http://tauri.localhost`,
which the guard rejects with 403. Loading the loopback URL (or adding a native
proxy/IPC bridge) preserves the guard. Weakening `Origin: null` is not an option.
