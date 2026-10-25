#!/usr/bin/env python3
"""M2 packaged sidecar for the TinyJS prototype.

This is a packaging/acceptance entry point, not the production launcher. It
runs the real bors_entry preflight and app:app under uvicorn, requires an
explicit isolated WORK_DIR/DB pair, prints one machine-readable M2_READY line,
and exits when the shell closes stdin.

The installed package places market.db.lzma (and its baseline stamp) beside
this executable; bors_config discovers it there and extracts the DB into the
isolated work directory on first run.
"""
from __future__ import annotations

import json
import os
import signal
import socket
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if not getattr(sys, "frozen", False) and ROOT not in sys.path:
    sys.path.insert(0, ROOT)
APP_ROOT = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else ROOT
os.chdir(APP_ROOT)

os.environ.setdefault("BORS_SHOW_CONSOLE", "1")

import bors_entry as E  # noqa: E402
import bors_config as BC  # noqa: E402


def emit(kind: str, **fields) -> None:
    print("M2_" + kind + " " + json.dumps(fields, ensure_ascii=False), flush=True)


def pick_port(preferred: int) -> int:
    if preferred > 0 and not E.port_open(preferred):
        return preferred
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_ready(port: int, server, thread, timeout: float = 240.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if getattr(server, "started", False):
            break
        if getattr(server, "should_exit", False) or not thread.is_alive():
            return False
        time.sleep(0.1)
    return E.wait_http(port, timeout=max(5.0, deadline - time.time()))


def db_scope_ok(work: str, db: str) -> bool:
    work_abs = os.path.abspath(work)
    db_abs = os.path.abspath(db)
    try:
        return os.path.commonpath([work_abs, db_abs]) == work_abs
    except ValueError:
        return False


def main() -> int:
    work = (os.environ.get("BORS_WORK_DIR") or "").strip()
    expected_db = (os.environ.get("BORS_DB") or "").strip()
    if not work or not expected_db:
        emit("ERROR", stage="isolation-required", pid=os.getpid(),
             work=work, db=expected_db)
        print("[ERR] BORS_WORK_DIR and BORS_DB are required in the packaged sidecar", flush=True)
        return 2
    if not db_scope_ok(work, expected_db):
        emit("ERROR", stage="db-scope", pid=os.getpid(), work=work, db=expected_db)
        print("[ERR] BORS_DB must live inside BORS_WORK_DIR", flush=True)
        return 4
    if os.path.abspath(BC.DB_PATH) != os.path.abspath(expected_db):
        emit("ERROR", stage="db-isolation", db=BC.DB_PATH, expected=expected_db,
             work=work)
        print("[ERR] refusing a DB outside the explicit BORS_DB", flush=True)
        return 4

    preferred = int(os.environ.get("BORS_PORT", "0") or "0")
    port = pick_port(preferred)
    os.environ["BORS_PORT"] = str(port)
    emit("START", pid=os.getpid(), port=port, work=work, db=BC.DB_PATH,
         user_db=BC.USER_DB_PATH, frozen=bool(getattr(sys, "frozen", False)),
         seed=os.path.join(APP_ROOT, "market.db.lzma"))

    if not E._preflight():
        emit("ERROR", stage="preflight", pid=os.getpid())
        return 2

    import uvicorn
    config = uvicorn.Config(
        "app:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
        log_config=E._log_config_with_clock(),
        timeout_graceful_shutdown=5,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="m2-uvicorn", daemon=True)
    thread.start()
    E._ST.mark("uvicorn_spawn", port=port)

    if not wait_ready(port, server, thread):
        emit("ERROR", stage="http", pid=os.getpid(), port=port)
        server.should_exit = True
        thread.join(timeout=10)
        return 3

    E._ST.mark("http_ready", port=port)
    emit("READY", pid=os.getpid(), port=port, url=f"http://127.0.0.1:{port}/")

    stop = threading.Event()

    def watch_stdin() -> None:
        try:
            while True:
                chunk = sys.stdin.buffer.read(4096)
                if not chunk:
                    break
        except Exception:
            pass
        emit("STDIN_EOF", pid=os.getpid())
        stop.set()

    def on_signal(signum, _frame):
        emit("SIGNAL", pid=os.getpid(), signum=int(signum))
        stop.set()

    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        try:
            signal.signal(getattr(signal, name), on_signal)
        except (AttributeError, ValueError, OSError):
            pass

    if sys.stdin is not None:
        threading.Thread(target=watch_stdin, name="m2-stdin", daemon=True).start()

    while not stop.wait(0.25):
        if not thread.is_alive():
            emit("ERROR", stage="uvicorn-exited", pid=os.getpid(),
                 code=getattr(server, "last_exit_code", None))
            return 4

    E._ST.mark("shutdown_begin")
    server.should_exit = True
    thread.join(timeout=20)
    E._ST.mark("shutdown_end", alive=bool(thread.is_alive()))
    emit("STOPPED", pid=os.getpid(), alive=bool(thread.is_alive()))
    return 0 if not thread.is_alive() else 5


if __name__ == "__main__":
    sys.exit(main())
