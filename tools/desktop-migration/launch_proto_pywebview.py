#!/usr/bin/env python3
"""Native WebView2 (pywebview) window for the M1 prototype.

This is deliberately a thin shell launcher: it hosts the same prototype URL
that the Tauri prototype will host, so the measured difference is the desktop
shell, not the UI or the data path.

usage:
  python tools/desktop-migration/launch_proto_pywebview.py \
      --url http://127.0.0.1:8105/ --profile build/bench/proto-webview2
"""
from __future__ import annotations

import argparse
import ctypes
import inspect
import os
import sys
import time

_T0 = time.perf_counter()


def mark(label: str) -> None:
    print(f"[proto] {label} t+{time.perf_counter() - _T0:.2f}s", flush=True)


def dpi_aware():
    if sys.platform != "win32":
        return
    try:
        try:
            if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
        except AttributeError:
            pass
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except AttributeError:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8105/")
    ap.add_argument("--profile", default=os.path.join(os.environ.get("TEMP", "."), "bors-proto-webview2"))
    ap.add_argument("--title", default="BorsTerminal — M1 Prototype")
    args = ap.parse_args()

    mark('start')
    dpi_aware()
    mark('dpi')
    os.makedirs(args.profile, exist_ok=True)
    import webview
    mark('import webview')

    try:
        from webview.platforms import winforms as _wf
        renderer = getattr(_wf, "renderer", None)
        if renderer != "edgechromium":
            print(f"[proto] webview backend is {renderer!r}, not edgechromium", flush=True)
    except Exception as exc:  # still try; pywebview may fail loudly
        print(f"[proto] cannot resolve webview backend ({exc})", flush=True)

    mark('create_window')
    webview.create_window(args.title, args.url, width=1440, height=900,
                          min_size=(1024, 640), maximized=True)
    kwargs = {}
    try:
        allowed = set(inspect.signature(webview.start).parameters)
        if "private_mode" in allowed:
            kwargs["private_mode"] = False
        if "storage_path" in allowed:
            kwargs["storage_path"] = args.profile
    except (TypeError, ValueError):
        pass
    mark(f'window url={args.url} profile={args.profile}')
    webview.start(**kwargs)
    mark('start returned')
    print("[proto] window closed", flush=True)


if __name__ == "__main__":
    main()
