#!/usr/bin/env python3
"""Headless sidecar for the Phase D TinyJS/Tauri prototypes.

Runs the real bors_entry preflight and app:app through uvicorn without opening
pywebview or a browser. It prints one machine-readable READY line, then keeps
running until its stdin pipe closes (the shell died) or SIGTERM/SIGINT arrives.

This is a benchmark wrapper, not the production launcher. Production still
starts bors_entry.py, which owns the native window.
"""
from __future__ import annotations

import json
import os
import signal
import socket
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# app.py mounts 'static' and imports sibling modules by relative cwd; the shell
# may start this sidecar from an arbitrary cwd, so pin it to the app root.
APP_ROOT = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else ROOT
os.chdir(APP_ROOT)

os.environ.setdefault("BORS_SHOW_CONSOLE", "1")

import bors_entry as E  # noqa: E402  (sets up UTF-8 streams and startup_trace)
import bors_config as BC  # noqa: E402


def _emit(kind: str, **fields) -> None:
    print("PHASE_D_" + kind + " " + json.dumps(fields, ensure_ascii=False), flush=True)


def _pick_port(preferred: int) -> int:
    if preferred > 0 and not E.port_open(preferred):
        return preferred
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_ready(port: int, server, thread, timeout: float = 180.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if getattr(server, "started", False):
            break
        if getattr(server, "should_exit", False) or not thread.is_alive():
            return False
        time.sleep(0.1)
    return E.wait_http(port, timeout=max(5.0, deadline - time.time()))


def main() -> int:
    if os.environ.get("BORS_FAIL_TEST") == "1":
        _emit("ERROR", stage="fail-test", pid=os.getpid())
        print("[ERR] deliberate Phase D failure fixture", flush=True)
        return 42

    preferred = int(os.environ.get("BORS_PORT", "0") or "0")
    port = _pick_port(preferred)
    os.environ["BORS_PORT"] = str(port)

    expected_db = os.environ.get("BORS_DB", "")
    if expected_db and os.path.abspath(BC.DB_PATH) != os.path.abspath(expected_db):
        _emit("ERROR", stage="db-isolation", db=BC.DB_PATH, expected=expected_db,
              work=BC.WORK_DIR)
        print("[ERR] refusing to use a DB outside the isolated BORS_DB", flush=True)
        return 4

    _emit("START", pid=os.getpid(), port=port,
          work=os.environ.get("BORS_WORK_DIR", ""), db=BC.DB_PATH,
          user_db=BC.USER_DB_PATH)
    if not E._preflight():
        _emit("ERROR", stage="preflight", pid=os.getpid())
        return 2

    import uvicorn
    config = uvicorn.Config(
        "app:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
        log_config=E._log_config_with_clock(),
        # A closed shell should not wait on keep-alive sockets or background
        # warm threads forever; 5s is enough to finish the normal shutdown.
        timeout_graceful_shutdown=5,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="phase-d-uvicorn", daemon=True)
    thread.start()
    E._ST.mark("uvicorn_spawn", port=port)

    if not _wait_ready(port, server, thread):
        _emit("ERROR", stage="http", pid=os.getpid(), port=port)
        server.should_exit = True
        thread.join(timeout=10)
        return 3

    E._ST.mark("http_ready", port=port)
    _emit("READY", pid=os.getpid(), port=port, url=f"http://127.0.0.1:{port}/")

    stop = threading.Event()

    def _watch_stdin() -> None:
        try:
            while True:
                chunk = sys.stdin.buffer.read(4096)
                if not chunk:
                    break
        except Exception:
            pass
        _emit("STDIN_EOF", pid=os.getpid())
        stop.set()

    def _on_signal(signum, _frame):
        _emit("SIGNAL", pid=os.getpid(), signum=int(signum))
        stop.set()

    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        try:
            signal.signal(getattr(signal, name), _on_signal)
        except (AttributeError, ValueError, OSError):
            pass

    if sys.stdin is not None:
        threading.Thread(target=_watch_stdin, name="phase-d-stdin", daemon=True).start()

    while not stop.wait(0.25):
        if not thread.is_alive():
            _emit("ERROR", stage="uvicorn-exited", pid=os.getpid(),
                  code=getattr(server, "last_exit_code", None))
            return 4

    E._ST.mark("shutdown_begin")
    server.should_exit = True
    thread.join(timeout=20)
    E._ST.mark("shutdown_end", alive=bool(thread.is_alive()))
    _emit("STOPPED", pid=os.getpid(), alive=bool(thread.is_alive()))
    return 0 if not thread.is_alive() else 5


if __name__ == "__main__":
    sys.exit(main())
