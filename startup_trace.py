# -*- coding: utf-8 -*-
"""Opt-in startup stage trace (BORS_STARTUP_TRACE=1).

Writes one JSON line per stage with wall time and process-relative monotonic
time. Off by default and inert when disabled; the harness sets
BORS_STARTUP_TRACE_FILE so runs never share a file. Why a file instead of a
log line: uvicorn and the boot worker run in threads, and the launcher replaces
sys.stdout early, so parsing printed text loses ordering and sub-second detail.
"""
import json
import os
import threading
import time

_LOCK = threading.Lock()
_T0 = time.perf_counter()
_ENABLED = (os.environ.get("BORS_STARTUP_TRACE") or "").strip() == "1"
_PATH = (os.environ.get("BORS_STARTUP_TRACE_FILE") or "").strip()


def mark(stage, **fields):
    if not _ENABLED:
        return
    rec = {
        "stage": stage,
        "t": round(time.time(), 6),
        "dt": round(time.perf_counter() - _T0, 6),
        "pid": os.getpid(),
    }
    rec.update(fields)
    try:
        line = json.dumps(rec, ensure_ascii=False) + "\n"
    except (TypeError, ValueError):
        return
    with _LOCK:
        path = _PATH
        if not path:
            try:
                import bors_config
                path = os.path.join(bors_config.WORK_DIR, "logs", "startup-trace.jsonl")
            except Exception:
                return
        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass
