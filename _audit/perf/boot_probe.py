"""PERF Stage 6 — boot timeline of the backend, phase by phase.

`Process Start → Port Ready → First API → Market Board Ready → Screener (FTS)
Ready` with wall-clock stamps, launched exactly the way a developer/user starts
the app (`python -u app.py`), and watching the app's OWN log lines for the
milestones so nothing is inferred from code reading.

usage: PYTHONIOENCODING=utf-8 python _audit/perf/boot_probe.py
"""
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(REPO, "_audit", "perf", "BOOT_LOG.txt")
DEADLINE_S = 420.0

MARKERS = [
    ("app startup complete", re.compile(r"Application startup complete")),
    ("codal schema migrated", re.compile(r"codal schema migrated")),
    ("market sync thread spawned", re.compile(r"\[startup\] market sync thread spawned")),
    ("market sync deferred/board fresh", re.compile(r"board is from|no network sync")),
    ("sync loops off", re.compile(r"BORS_NO_FETCH_LOOPS=1")),
    ("screener warm deferred to sync", re.compile(r"screener warm deferred")),
    ("screener loaded from disk cache", re.compile(r"\[screener\] loaded from disk cache")),
    ("screener heavy rebuild started", re.compile(r"cache miss, running heavy bulk scan")),
    ("screener fts_results live eval", re.compile(r"fts_results miss")),
    ("screener saved to disk cache", re.compile(r"screener\] saved to disk cache")),
    ("screener cache warmed", re.compile(r"\[screener\] cache warmed")),
    ("market-sync thread started", re.compile(r"\[market-sync\] thread started")),
    ("market-sync done", re.compile(r"\[market-sync\] done")),
    ("history windows rebuilt", re.compile(r"history windows rebuilt in ([\d.]+)s")),
    ("candle projection", re.compile(r"candles-from-board")),
    ("board tick loop", re.compile(r"board tick loop spawned")),
    ("pulse snapshot loop", re.compile(r"pulse snapshot loop spawned")),
    ("tape history fetch", re.compile(r"\[tape-history\]")),
    ("corporate events", re.compile(r"\[corporate-events\]")),
]


def port_open(host, port, timeout=0.4):
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def get(path, timeout=90.0):
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000" + path, timeout=timeout) as r:
            n = len(r.read())
            return (time.perf_counter() - t0) * 1000.0, r.status, n
    except urllib.error.HTTPError as e:
        return (time.perf_counter() - t0) * 1000.0, e.code, 0
    except Exception:                                         # noqa: BLE001
        return None, 0, 0


def main():
    t_start = time.time()
    fh = open(LOG, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen([sys.executable, "-u", "app.py"], cwd=REPO,
                            stdout=fh, stderr=subprocess.STDOUT, env=dict(os.environ))
    print(f"launched pid={proc.pid}")
    tl = {}

    while time.time() - t_start < 120.0:
        if port_open("127.0.0.1", 8000):
            tl["port_ready_s"] = round(time.time() - t_start, 2)
            break
        if proc.poll() is not None:
            print("process died early, rc=", proc.returncode)
            break
        time.sleep(0.25)

    while time.time() - t_start < 300.0:
        ms, code, _n = get("/api/live-stats", timeout=5.0)
        if code == 200:
            tl["first_api_ms"] = round(ms)
            tl["first_api_s"] = round(time.time() - t_start, 2)
            break
        time.sleep(0.5)

    ms, code, n = get("/api/market", timeout=180.0)
    tl["market_board_first_ms"] = round(ms or 0)
    tl["market_board_bytes"] = n
    tl["market_board_s"] = round(time.time() - t_start, 2)
    ms2, code2, n2 = get("/api/market", timeout=180.0)
    tl["market_board_second_ms"] = round(ms2 or 0)

    # markers from the app's own log, with wall-clock arrival
    seen = {}
    while time.time() - t_start < DEADLINE_S:
        with open(LOG, encoding="utf-8", errors="replace") as f:
            body = f.read()
        for name, rx in MARKERS:
            if name in seen:
                continue
            m = rx.search(body)
            if m:
                seen[name] = round(time.time() - t_start, 1)
        if all(k in seen for k, _ in MARKERS):
            break
        time.sleep(1.0)

    tl["markers"] = seen
    warm_count = body.count("[screener] cache warmed")
    heavy_count = body.count("running heavy bulk scan")
    tl["screener_cache_warmed_lines"] = warm_count
    tl["screener_heavy_rebuilds"] = heavy_count
    tl["total_s"] = round(time.time() - t_start, 1)

    import json
    print(json.dumps(tl, ensure_ascii=False, indent=1))
    with open(os.path.join(REPO, "_audit", "perf", "BOOT_TIMELINE.json"), "w", encoding="utf-8") as f:
        json.dump(tl, f, ensure_ascii=False, indent=1)
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except Exception:                                         # noqa: BLE001
        proc.kill()
    fh.close()
    print("\nwrote _audit/perf/BOOT_TIMELINE.json  (log: _audit/perf/BOOT_LOG.txt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
