#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase D TinyJS integrated harness.

Launches the built TinyJS shell, which owns the real FastAPI sidecar, waits for
HTTP readiness, opens the loopback app window, runs an in-page probe through the
shell's own eval bridge (TinyJS has no CDP), screenshots the window, closes it,
and checks that the shell, sidecar, and port went away cleanly.

Cold = fresh work dir + profile per run (seeded from a market.db template).
Warm = one work dir/profile, one unrecorded warmup, then recorded runs.

All data stays in %TEMP%/bors_phased/<label>; only compact summary JSON and
selected screenshots are written to --out-dir.
"""
from __future__ import annotations

import argparse
import ctypes
import http.client
import http.server
import json
import os
import platform
import shutil
import signal
import socket
import socketserver
import statistics
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from ctypes import wintypes
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
DEFAULT_EXE = ROOT / "prototypes" / "tinyjs-m2" / "dist" / "BorsTerminalM2TinyJS.exe"
HEADLESS = ROOT / "tools" / "desktop-migration" / "phase_d" / "headless_server.py"
PROBE = ROOT / "tools" / "desktop-migration" / "phase_d" / "tinyjs_probe.js"
DEFAULT_TEMPLATE = Path(os.environ.get("TEMP", "")) / "bors_phasec" / "template"
SCRATCH_ROOT = Path(os.environ.get("TEMP", "")) / "bors_phased"

USER32 = ctypes.windll.user32
GDI32 = ctypes.windll.gdi32
WM_CLOSE = 0x0010
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
# Full 64-bit HWNDs overflow the default c_int marshalling; pin every signature.
USER32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
USER32.GetWindowTextLengthW.restype = ctypes.c_int
USER32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
USER32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
USER32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
USER32.IsWindowVisible.argtypes = [wintypes.HWND]
USER32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
USER32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
USER32.SetForegroundWindow.argtypes = [wintypes.HWND]
USER32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
USER32.GetForegroundWindow.restype = wintypes.HWND
USER32.GetWindowDC.argtypes = [wintypes.HWND]
USER32.GetWindowDC.restype = ctypes.c_void_p
USER32.ReleaseDC.argtypes = [wintypes.HWND, ctypes.c_void_p]
USER32.PrintWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.UINT]
GDI32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
GDI32.CreateCompatibleDC.restype = ctypes.c_void_p
GDI32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
GDI32.CreateCompatibleBitmap.restype = ctypes.c_void_p
GDI32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
GDI32.SelectObject.restype = ctypes.c_void_p
GDI32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT, wintypes.UINT,
                            ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
GDI32.DeleteObject.argtypes = [ctypes.c_void_p]
GDI32.DeleteDC.argtypes = [ctypes.c_void_p]
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        USER32.SetProcessDPIAware()
    except Exception:
        pass


def now_ms() -> float:
    return time.time() * 1000.0


def free_port() -> int:
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


def port_open(port: int) -> bool:
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def security_checks(port: int) -> dict:
    """Live guard check against the sidecar the shell actually launched."""
    base = {"Host": f"127.0.0.1:{port}"}
    cases = {
        "local_host": (base, 200),
        "foreign_host": ({"Host": "evil.example"}, 403),
        "origin_null": ({**base, "Origin": "null"}, 403),
        "origin_foreign": ({**base, "Origin": "http://evil.example"}, 403),
        "origin_local": ({**base, "Origin": f"http://127.0.0.1:{port}"}, 200),
    }
    out = {}
    for name, (headers, expected) in cases.items():
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            c.putrequest("GET", "/api/update/version", skip_host=True)
            for k, v in headers.items():
                c.putheader(k, v)
            c.endheaders()
            resp = c.getresponse()
            status = resp.status
            resp.read()
            c.close()
            out[name] = {"status": status, "expected": expected,
                         "ok": status == expected, "headers": headers}
        except Exception as e:
            out[name] = {"error": str(e)[:200], "expected": expected, "ok": False,
                         "headers": headers}
    return out


def read_jsonl(path: Path) -> list[dict]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError):
        return []


_PROGRESS_LOCK = threading.Lock()


def progress(run_dir: Path, message: str, tag: str = "info") -> None:
    line = f"{time.strftime('%H:%M:%S')} [{tag}] {message}"
    with _PROGRESS_LOCK:
        print(line, flush=True)
        try:
            with open(run_dir / "progress.log", "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def snapshot_result(run_dir: Path, result: dict) -> None:
    """Write the in-progress run atomically so an external kill leaves evidence."""
    path = run_dir / "partial-result.json"
    tmp = run_dir / "partial-result.json.tmp"
    try:
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str),
                       encoding="utf-8")
        tmp.replace(path)
    except (OSError, TypeError, ValueError):
        pass


def cleanup_survivors(args, work: Path, profile: Path, root_pid: int,
                      port: int | None) -> dict:
    before = find_survivors(args, work, profile, root_pid)
    killed = []
    for s in before:
        try:
            proc = psutil.Process(s["pid"])
            proc.kill()
            killed.append(s["pid"])
        except psutil.Error:
            pass
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if not find_survivors(args, work, profile, root_pid):
            break
        time.sleep(0.25)
    after = find_survivors(args, work, profile, root_pid)
    return {
        "survivors_before": before,
        "killed": killed,
        "survivors_after": after,
        "port_open_after_cleanup": port_open(port) if port else None,
    }


# ── Win32 windows / screenshots ──────────────────────────────────────────────


def enum_windows() -> list[dict]:
    out: list[dict] = []

    def cb(hwnd, _):
        n = USER32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        USER32.GetWindowTextW(hwnd, buf, n + 1)
        pid = wintypes.DWORD()
        USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        r = wintypes.RECT()
        USER32.GetWindowRect(hwnd, ctypes.byref(r))
        out.append({
            "hwnd": hwnd,
            "title": buf.value,
            "pid": pid.value,
            "visible": bool(USER32.IsWindowVisible(hwnd)),
            "rect": [r.left, r.top, r.right, r.bottom],
            "w": r.right - r.left,
            "h": r.bottom - r.top,
        })
        return True

    USER32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def app_windows(pids: set[int]) -> list[dict]:
    out = []
    for w in enum_windows():
        title = w["title"]
        low = title.lower()
        if not w["visible"] or w["w"] <= 500 or w["pid"] not in pids:
            continue
        if "borsterminal" not in low:
            continue
        # A console child (python.exe path as title) is not the app window.
        if "python.exe" in low or "pythonw.exe" in low or low.startswith(("c:\\", "\\\\")):
            continue
        out.append(w)
    return out


def firewall_windows() -> list[dict]:
    return [w for w in enum_windows() if w["visible"] and "Security Alert" in w["title"]]


def screenshot(hwnd: int, path: Path) -> dict:
    """PrintWindow(PW_RENDERFULLCONTENT): WebView2 content is not in a GDI
    screen grab here, and the probe waits for an ack after this returns."""
    from PIL import Image, ImageGrab
    t0 = time.perf_counter()
    r = wintypes.RECT()
    USER32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return {"ok": False, "error": "empty window rect", "w": w, "h": h}
    screen_path = path.with_name(path.stem + ".screen.png")
    screen = {"ok": False}
    try:
        USER32.ShowWindow(hwnd, 5)  # SW_SHOW
        USER32.SetForegroundWindow(hwnd)
        try:
            ctypes.windll.dwmapi.DwmFlush()
        except Exception:
            pass
        time.sleep(0.6)
        fg = USER32.GetForegroundWindow()
        img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom), all_screens=True)
        img.convert("RGB").save(screen_path)
        screen = {"ok": True, "method": "ImageGrab", "foreground": fg == hwnd,
                  "path": str(screen_path),
                  "duration_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as e:
        screen = {"ok": False, "error": str(e)[:200]}
    hdc = USER32.GetWindowDC(hwnd)
    mdc = GDI32.CreateCompatibleDC(hdc)
    bmp = GDI32.CreateCompatibleBitmap(hdc, w, h)
    GDI32.SelectObject(mdc, bmp)
    ok = USER32.PrintWindow(hwnd, mdc, 2)

    class BIH(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    bi = BIH()
    bi.biSize = ctypes.sizeof(bi)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    got = GDI32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    GDI32.DeleteObject(bmp)
    GDI32.DeleteDC(mdc)
    USER32.ReleaseDC(hwnd, hdc)
    if not got:
        return {"ok": False, "error": "GetDIBits failed", "w": w, "h": h,
                "duration_ms": round((time.perf_counter() - t0) * 1000, 1)}
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB").save(path)
    return {"ok": bool(ok), "method": "PrintWindow", "w": w, "h": h,
            "path": str(path), "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            "screen": screen}


# ── process tree ─────────────────────────────────────────────────────────────


class TreeSampler:
    def __init__(self, root_pid: int, extra_match: str):
        self.root_pid = root_pid
        self.extra_match = extra_match
        self.samples: list[dict] = []
        self.stages: dict[str, dict] = {}
        self.peak = {"rss_mb": 0.0, "epoch_ms": None, "procs": 0}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._lock = threading.Lock()

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=3)

    def _tree(self):
        try:
            root = psutil.Process(self.root_pid)
        except psutil.NoSuchProcess:
            return []
        procs = [root]
        try:
            procs += root.children(recursive=True)
        except psutil.Error:
            pass
        if self.extra_match:
            for p in psutil.process_iter(["pid", "cmdline"]):
                try:
                    cmd = " ".join(p.info.get("cmdline") or [])
                    if self.extra_match in cmd:
                        procs.append(p)
                        procs += p.children(recursive=True)
                except psutil.Error:
                    pass
        seen, out = set(), []
        for p in procs:
            if p.pid in seen:
                continue
            seen.add(p.pid)
            try:
                if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                    out.append(p)
            except psutil.Error:
                pass
        return out

    def snapshot(self) -> dict:
        procs = self._tree()
        rows = []
        rss = 0
        cpu = 0.0
        for p in procs:
            try:
                mi = p.memory_info()
                ct = p.cpu_times()
                ppid = p.ppid()
                rss += mi.rss
                cpu += ct.user + ct.system
                rows.append({
                    "pid": p.pid,
                    "ppid": ppid,
                    "name": p.name(),
                    "rss_mb": round(mi.rss / 1048576, 1),
                    "cpu_s": round(ct.user + ct.system, 3),
                })
            except psutil.Error:
                pass
        rec = {
            "epoch_ms": now_ms(),
            "rss_mb": round(rss / 1048576, 1),
            "cpu_s": round(cpu, 3),
            "procs": len(rows),
            "rows": rows,
        }
        if rec["rss_mb"] > self.peak["rss_mb"]:
            self.peak = {"rss_mb": rec["rss_mb"], "epoch_ms": rec["epoch_ms"], "procs": len(rows)}
        return rec

    def stage(self, name: str) -> dict:
        rec = self.snapshot()
        self.stages[name] = rec
        return rec

    def _loop(self):
        while not self._stop.is_set():
            self.samples.append(self.snapshot())
            self._stop.wait(0.1)

    def tree_pids(self) -> set[int]:
        return {p.pid for p in self._tree()}

    def cpu_between(self, a: dict, b: dict) -> dict:
        return {
            "seconds": round(b["cpu_s"] - a["cpu_s"], 3),
            "wall_s": round((b["epoch_ms"] - a["epoch_ms"]) / 1000.0, 3),
            "pct_one_core": round(((b["cpu_s"] - a["cpu_s"]) /
                                   max(0.001, (b["epoch_ms"] - a["epoch_ms"]) / 1000.0)) * 100, 1),
        }


# ── probe collector ──────────────────────────────────────────────────────────


class Collector:
    def __init__(self):
        self.messages: list[dict] = []
        self.acks: set[str] = set()
        self.lock = threading.Lock()
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def do_GET(self):
                from urllib.parse import urlparse, parse_qs
                stage = (parse_qs(urlparse(self.path).query).get("stage") or [None])[0]
                with outer.lock:
                    ok = bool(stage) and stage in outer.acks
                body = json.dumps({"stage": stage if ok else None}).encode()
                self.send_response(200 if ok else 204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if ok:
                    self.wfile.write(body)

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n).decode("utf-8", "replace")
                try:
                    msg = json.loads(body)
                except Exception:
                    msg = {"kind": "raw", "body": body[:2000]}
                msg["_recv_epoch_ms"] = now_ms()
                with outer.lock:
                    outer.messages.append(msg)
                self.send_response(204)
                self.end_headers()

        self.httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def ack(self, stage: str):
        with self.lock:
            self.acks.add(stage)

    def close(self):
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception:
            pass

    def drained(self, seen: int) -> tuple[list[dict], int]:
        with self.lock:
            new = self.messages[seen:]
            return new, len(self.messages)


# ── scratch / env ────────────────────────────────────────────────────────────


def copy_template(template: Path, work: Path) -> list[str]:
    work.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in template.iterdir():
        if not src.is_file() or src.name.endswith(".lzma"):
            continue
        shutil.copy2(src, work / src.name)
        copied.append(src.name)
    return sorted(copied)


def prepare_work(label: str, mode: str, run_i: int, template: Path,
                 seed: bool = True) -> tuple[Path, Path, Path]:
    base = SCRATCH_ROOT / label
    if mode == "warm":
        work = base / "warm-work"
        profile = base / "warm-profile"
        run_dir = base / "runs" / f"run-{run_i}"
        if seed and not work.exists():
            copy_template(template, work)
        profile.mkdir(parents=True, exist_ok=True)
    else:
        run_dir = base / "runs" / f"run-{run_i}"
        work = run_dir / "work"
        profile = run_dir / "profile"
        if seed:
            copy_template(template, work)
        profile.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    return work, profile, run_dir


def build_env(args, work: Path, profile: Path, run_dir: Path, collector_port: int,
              stop_file: Path) -> dict:
    env = {
        **os.environ,
        "BORS_PYTHON": str(PY),
        "BORS_HEADLESS_ENTRY": str(HEADLESS),
        "BORS_WORK_DIR": str(work),
        # _resolve_market_db() prefers the dev repo market.db over WORK_DIR;
        # BORS_DB is the explicit isolation door, so the benchmark never opens
        # the operational database even when a repo market.db exists.
        "BORS_DB": str(work / "market.db"),
        "BORS_PORT": "0",
        "BORS_REUSE_SERVER": "0",
        "BORS_NO_FETCH_LOOPS": "1",
        "BORS_CODAL_AUTO": "0",
        "BORS_SHOW_CONSOLE": "1",
        "BORS_STARTUP_TRACE": "1",
        "BORS_STARTUP_TRACE_FILE": str(run_dir / "sidecar-trace.jsonl"),
        "BORS_SHELL_TRACE": str(run_dir / "shell-trace.jsonl"),
        "BORS_PROBE_SCRIPT": str(PROBE),
        "BORS_PROBE_STOP_FILE": str(stop_file),
        "BORS_COLLECTOR_PORT": str(collector_port),
        "BORS_SYMBOL": args.symbol,
        "BORS_SYMBOL2": args.symbol2,
        "LOCALAPPDATA": str(profile),
        "TINYJS_DEBUG": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    if args.d3:
        env["BORS_D3_CHECKS"] = "1"
    if args.visual:
        env["BORS_VISUAL"] = "1"
    if args.scenario == "fail":
        env["BORS_FAIL_TEST"] = "1"
    return env


def sidecar_log_path(work: Path) -> Path:
    return work / "logs" / "sidecar.log"


def tail(path: Path, n: int = 30) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except FileNotFoundError:
        return []


# ── one run ──────────────────────────────────────────────────────────────────


def run_once(args, mode: str, run_i: int, template: Path) -> dict:
    work, profile, run_dir = prepare_work(args.label, mode, run_i, template,
                                          seed=args.scenario != "fail")
    stop_file = run_dir / "probe-stop.flag"
    if stop_file.exists():
        stop_file.unlink()
    collector = Collector()
    collector.start()

    env = build_env(args, work, profile, run_dir, collector.port, stop_file)
    log_path = run_dir / "tinyjs-stdout.log"
    log = open(log_path, "wb")
    t0 = time.perf_counter()
    t_launch = now_ms()
    p = subprocess.Popen(
        [str(args.exe)], cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
        stdout=log, stderr=subprocess.STDOUT,
        creationflags=0x08000000,
    )
    sampler = TreeSampler(p.pid, extra_match=str(profile))
    sampler.start()

    result = {
        "label": args.label,
        "mode": mode,
        "scenario": args.scenario,
        "run": run_i,
        "launch_epoch_ms": round(t_launch, 1),
        "exe": str(args.exe),
        "work_dir": str(work),
        "profile_dir": str(profile),
        "screenshots": {},
        "errors": [],
        "probe_instances": [],
        "crash": bool(args.crash),
    }
    snapshot_result(run_dir, result)
    progress(run_dir, f"launched pid={p.pid} exe={args.exe.name} work={work} "
                     f"profile={profile} scenario={args.scenario} crash={args.crash}")
    hb_stop = threading.Event()

    def _heartbeat():
        started = time.perf_counter()
        while not hb_stop.wait(15.0):
            progress(run_dir, f"run {run_i} alive={p.poll() is None} "
                             f"elapsed={time.perf_counter() - started:.0f}s "
                             f"final={bool(result.get('final'))}", tag="heartbeat")
            snapshot_result(run_dir, result)

    hb = threading.Thread(target=_heartbeat, daemon=True)
    hb.start()
    seen_msgs = 0
    handled_events: set[str] = set()
    logged_events: set[str] = set()
    board_seen = False
    final_payload = None
    final_run_ids: list[str] = []
    app_hwnd = None
    error_hwnd = None
    window_visible_ms = None
    firewall_seen = 0
    firewall_hwnds: set[int] = set()
    closed_at_ms = None
    shutdown = {}

    try:
        deadline = t0 + args.timeout
        last_ss = 0.0
        while time.perf_counter() < deadline:
            msgs, seen_msgs = collector.drained(seen_msgs)
            for m in msgs:
                kind = m.get("kind")
                if kind == "started":
                    result["probe_instances"].append({
                        "run_id": m.get("run_id"), "at_ms": round(m.get("_recv_epoch_ms", 0) - t_launch, 1),
                        "url": m.get("url"),
                    })
                if kind == "event":
                    name = m.get("name") or ""
                    ev = m.get("event") or {}
                    rel = round(ev.get("epoch_ms", 0) - t_launch, 1) if ev.get("epoch_ms") else None
                    if name == "market_rows_visible":
                        board_seen = True
                        try:
                            stop_file.write_text("stop", encoding="utf-8")
                        except OSError:
                            pass
                    if name not in logged_events:
                        logged_events.add(name)
                        progress(run_dir, f"probe_event {name} rel_ms={rel} url={ev.get('url')}")
                        snapshot_result(run_dir, result)
                    if name not in handled_events and app_hwnd:
                        handled_events.add(name)
                        if args.visual and name in ("market_rows_visible", "technical_ready",
                                                    "fundamental_ready", "market_status_ready", "d3_symbol2_ready",
                                                    "login_ready", "d3_checks_done", "d3_raw_mode"):
                            time.sleep(1.2 if name == "fundamental_ready"
                                       else (0.25 if name != "login_ready" else 0.1))
                            path = run_dir / f"{name}.png"
                            shot = screenshot(app_hwnd, path)
                            result["screenshots"][name] = shot
                            sampler.stage(name)
                            if name in ("market_rows_visible", "technical_ready",
                                        "fundamental_ready", "market_status_ready", "d3_raw_mode", "d3_symbol2_ready"):
                                collector.ack(name)
                    result.setdefault("probe_event_ms", {})[name] = rel
                elif kind == "final":
                    rid = m.get("run_id")
                    payload = m.get("payload") or {}
                    if payload.get("events", {}).get("technical_ready") or payload.get("events", {}).get("market_rows_visible"):
                        final_payload = payload
                        final_run_ids.append(rid)
                        sampler.stage("probe_final")

            wins = app_windows(sampler_tree_pids(sampler))
            if wins and app_hwnd is None:
                app_hwnd = wins[0]["hwnd"]
                window_visible_ms = round(now_ms() - t_launch, 1)
                result["window"] = wins[0]
                result["window_visible_ms"] = window_visible_ms
                sampler.stage("window_visible")
                if args.visual:
                    result["screenshots"]["window_first"] = screenshot(
                        app_hwnd, run_dir / "window_first.png")

            err_wins = [w for w in enum_windows()
                        if w["visible"] and "startup failed" in w["title"]
                        and w["pid"] in sampler_tree_pids(sampler)]
            if err_wins and error_hwnd is None:
                error_hwnd = err_wins[0]["hwnd"]
                result["error_window"] = err_wins[0]
                time.sleep(0.3)
                if args.visual or args.scenario == "fail":
                    result["screenshots"]["error"] = screenshot(error_hwnd, run_dir / "error.png")

            for fw in firewall_windows():
                if fw["hwnd"] not in firewall_hwnds:
                    firewall_hwnds.add(fw["hwnd"])
                    firewall_seen += 1
                    USER32.PostMessageW(fw["hwnd"], WM_CLOSE, 0, 0)
            result["firewall_prompts"] = firewall_seen

            if args.crash and board_seen and "crash_kill" not in result:
                time.sleep(1.0)
                result["crash_kill"] = {"epoch_ms": now_ms(), "root_pid": p.pid,
                                        "reason": "TerminateProcess on the shell root only"}
                result["errors"].append("crash_kill: root terminated without window close")
                progress(run_dir, f"crash_kill root_pid={p.pid} (children are not killed)")
                try:
                    p.kill()
                    p.wait(timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                snapshot_result(run_dir, result)
                break

            if final_payload is not None and time.perf_counter() - last_ss > 2.0:
                last_ss = time.perf_counter()
                if args.scenario != "fail":
                    break
            if args.scenario == "fail" and error_hwnd:
                break
            if p.poll() is not None:
                break
            time.sleep(0.15)

        if final_payload is None and args.scenario == "fail" and error_hwnd:
            time.sleep(1.0)

        live_trace = read_jsonl(run_dir / "shell-trace.jsonl")
        live_ready = next((r for r in live_trace if r.get("stage") == "sidecar_ready_line"), None)
        live_port = (live_ready or {}).get("port")
        if live_port and port_open(int(live_port)):
            result["security"] = security_checks(int(live_port))
            progress(run_dir, "security_checks " + json.dumps(
                {k: v.get("status") for k, v in result["security"].items()},
                ensure_ascii=False))
            snapshot_result(run_dir, result)

        # idle sample before shutdown
        if p.poll() is None:
            a = sampler.snapshot()
            time.sleep(3.0)
            b = sampler.snapshot()
            result["idle"] = {
                "rss_mb": b["rss_mb"],
                "cpu": sampler.cpu_between(a, b),
                "procs": b["procs"],
                "rows": b["rows"],
            }
            sampler.stage("idle")

        hwnd_to_close = app_hwnd or error_hwnd
        if hwnd_to_close and p.poll() is None:
            closed_at_ms = now_ms()
            USER32.PostMessageW(hwnd_to_close, WM_CLOSE, 0, 0)
            t_close = time.perf_counter()
            while p.poll() is None and time.perf_counter() - t_close < 40:
                time.sleep(0.2)
        t_exit = now_ms()
        if p.poll() is None:
            shutdown["forced_kill"] = True
            subprocess.run(["taskkill.exe", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            p.wait(timeout=15)
        else:
            shutdown["forced_kill"] = False
        t_exit = now_ms()

        shell_trace = read_jsonl(run_dir / "shell-trace.jsonl")
        sidecar_trace = read_jsonl(run_dir / "sidecar-trace.jsonl")
        ready = next((r for r in shell_trace if r.get("stage") == "sidecar_ready_line"), None)
        port = (ready or {}).get("port")
        time.sleep(1.0)
        shutdown.update({
            "window_close_ms": round(closed_at_ms - t_launch, 1) if closed_at_ms else None,
            "root_exit_ms": round(t_exit - t_launch, 1),
            "exit_code": p.returncode,
            "port": port,
            "port_open_after_exit": port_open(port) if port else None,
            "sidecar_shutdown": [r for r in sidecar_trace if r.get("stage") in ("shutdown_begin", "shutdown_end")],
            "shell_tail": shell_trace[-8:],
            "crash_kill": result.get("crash_kill"),
        })

        cleanup = cleanup_survivors(args, work, profile, p.pid, port)
        shutdown["survivors"] = cleanup["survivors_before"]
        shutdown["cleanup"] = cleanup
        if cleanup["survivors_before"]:
            result["errors"].append(
                f"survivors_after_shell_exit={len(cleanup['survivors_before'])}")
            progress(run_dir, "survivors " + json.dumps(
                cleanup["survivors_before"], ensure_ascii=False), tag="warn")
        progress(run_dir, f"shutdown exit={p.returncode} forced_kill="
                         f"{shutdown['forced_kill']} port_open={shutdown['port_open_after_exit']} "
                         f"survivors_after_cleanup={len(cleanup['survivors_after'])}")
        snapshot_result(run_dir, result)

        result.update({
            "final": final_payload,
            "final_run_ids": final_run_ids,
            "shell_trace": shell_trace,
            "sidecar_trace": sidecar_trace,
            "process": {
                "peak": sampler.peak,
                "stages": sampler.stages,
                "samples": len(sampler.samples),
            },
            "shutdown": shutdown,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        })
        result["timings_ms"] = derive_timings(result)
        if result.get("final"):
            result["errors"].extend(result["final"].get("errors") or [])
    finally:
        hb_stop.set()
        hb.join(timeout=2.0)
        sampler.stop()
        collector.close()
        log.close()
        if p.poll() is None:
            subprocess.run(["taskkill.exe", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        live_ready = next((r for r in read_jsonl(run_dir / "shell-trace.jsonl")
                           if r.get("stage") == "sidecar_ready_line"), None)
        cleanup = cleanup_survivors(args, work, profile, p.pid,
                                    (live_ready or {}).get("port"))
        result.setdefault("shutdown", {})["cleanup_final"] = cleanup
        result.setdefault("shutdown", {})["shell_exit_code"] = p.returncode
        result["harness_finished_at"] = round(now_ms(), 1)
        result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        snapshot_result(run_dir, result)
        progress(run_dir, f"harness_finished exit={p.returncode} "
                         f"leftovers={len(cleanup['survivors_after'])}")
    return result


def sampler_tree_pids(sampler: TreeSampler) -> set[int]:
    return sampler.tree_pids()


def ancestor_pids(pid: int) -> set[int]:
    out: set[int] = set()
    try:
        for p in psutil.Process(pid).parents():
            out.add(p.pid)
    except psutil.Error:
        pass
    return out


def find_survivors(args, work: Path, profile: Path, root_pid: int) -> list[dict]:
    out = []
    own = {os.getpid()} | ancestor_pids(os.getpid())
    exe = os.path.normcase(str(args.exe.resolve()))
    launcher = os.path.normcase(str((args.exe.parent / "launcher.exe").resolve()))
    work_s = str(work)
    profile_s = str(profile)
    for p in psutil.process_iter(["pid", "name", "cmdline", "exe"]):
        try:
            if p.pid in own or p.pid == root_pid:
                continue
            name = (p.info.get("name") or "").lower()
            argv = [str(a) for a in (p.info.get("cmdline") or [])]
            exe_path = os.path.normcase(p.info.get("exe") or "")
            is_shell = bool(exe_path) and (exe_path == exe or exe_path == launcher)
            is_sidecar = any(os.path.basename(a).lower() == "headless_server.py"
                             for a in argv)
            is_webview = name == "msedgewebview2.exe"
            if not (is_shell or is_sidecar or is_webview):
                continue
            # A shell name inside the invoking Bash command string is not a
            # survivor. Read the isolated env for children instead of matching
            # arbitrary command-line text.
            try:
                env = p.environ()
            except psutil.Error:
                env = {}
            ours = (env.get("BORS_WORK_DIR") == work_s
                    or env.get("LOCALAPPDATA") == profile_s
                    or env.get("BORS_PROFILE_DIR") == profile_s)
            if not (is_shell or ours):
                continue
            out.append({"pid": p.pid, "name": p.info.get("name"), "exe": exe_path,
                        "cmd": " ".join(argv)[:300],
                        "env_work": env.get("BORS_WORK_DIR"),
                        "env_localappdata": env.get("LOCALAPPDATA")})
        except psutil.Error:
            pass
    return out


def derive_timings(result: dict) -> dict:
    launch = result["launch_epoch_ms"]
    out = {}
    for r in result.get("shell_trace") or []:
        stage = r.get("stage")
        if stage in ("sidecar_spawned", "sidecar_ready_line", "http_verified",
                     "window_open_begin", "window_open", "window_closed", "quit_requested",
                     "error_window", "ready_timeout"):
            out[stage] = round(r.get("t", 0) * 1000 - launch, 1)
    if result.get("window_visible_ms") is not None:
        out["window_visible"] = result["window_visible_ms"]
    for name, rel in (result.get("probe_event_ms") or {}).items():
        out[name] = rel
    for r in result.get("sidecar_trace") or []:
        st = r.get("stage")
        if st in ("preflight_start", "preflight_end", "http_ready", "shutdown_begin", "shutdown_end"):
            out["sidecar_" + st] = round(r.get("t", 0) * 1000 - launch, 1)
    sh = result.get("shutdown") or {}
    for k in ("window_close_ms", "root_exit_ms"):
        if sh.get(k) is not None:
            out[k] = sh[k]
    if result.get("final"):
        ev = (result["final"].get("events") or {})
        for k in ("app_document_ready", "login_ready", "master_ready", "market_rows_visible",
                  "technical_ready", "fundamental_ready", "d3_checks_done"):
            if k in ev and ev[k].get("epoch_ms"):
                out[k] = round(ev[k]["epoch_ms"] - launch, 1)
    return out


# ── summary ──────────────────────────────────────────────────────────────────


def summarize(runs: list[dict], args) -> dict:
    ok_runs = [r for r in runs if r.get("final") and not r.get("errors")]
    def vals(key):
        return [r["timings_ms"][key] for r in runs
                if key in (r.get("timings_ms") or {}) and r["timings_ms"][key] is not None]
    def stat(key):
        v = vals(key)
        if not v:
            return {"n": 0, "median": None, "min": None, "max": None, "p95": None,
                    "p95_note": "not reported: n<20"}
        return {
            "n": len(v),
            "median": round(statistics.median(v), 1),
            "min": min(v),
            "max": max(v),
            "values": v,
            "p95": None,
            "p95_note": "not reported: n<20",
        }
    keys = ["sidecar_ready_line", "window_visible", "http_verified", "app_document_ready",
            "login_ready", "master_ready", "market_rows_visible", "technical_ready",
            "fundamental_ready", "market_status_ready", "window_close_ms", "root_exit_ms"]
    peak = [r.get("process", {}).get("peak", {}).get("rss_mb") for r in runs if r.get("process")]
    idle = [r.get("idle", {}).get("rss_mb") for r in runs if r.get("idle")]
    idle_cpu = [r.get("idle", {}).get("cpu", {}).get("pct_one_core") for r in runs if r.get("idle")]
    return {
        "label": args.label,
        "mode": args.mode,
        "scenario": args.scenario,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": {
            "platform": platform.platform(),
            "cpu_logical": psutil.cpu_count(logical=True),
            "cpu_physical": psutil.cpu_count(logical=False),
            "ram_gb": round(psutil.virtual_memory().total / 1073741824, 2),
            "python": sys.version.split()[0],
            "exe": str(args.exe),
            "exe_bytes": args.exe.stat().st_size if args.exe.exists() else None,
            "launcher_bytes": (args.exe.parent / "launcher.exe").stat().st_size
            if (args.exe.parent / "launcher.exe").exists() else None,
            "dist_bytes": sum(f.stat().st_size for f in args.exe.parent.glob("*") if f.is_file())
            if (args.exe.parent.exists() and "TinyJS" in args.exe.stem) else None,
            "dist_bytes_note": "TinyJS portable dist only; Tauri target/release is not an install footprint",
        },
        "protocol": {
            "shell": args.shell_label or f"{args.exe.name} + Python sidecar",
            "window_gate": "shell opens the loopback window only after GET /api/update/version succeeds",
            "isolation": "fresh WORK_DIR/profile in cold; shared seeded one in warm",
            "network_loops": "BORS_NO_FETCH_LOOPS=1, BORS_CODAL_AUTO=0",
            "instrumentation": f"external process tree + Win32 PrintWindow + {args.exe.name} WebView2 eval probe (no CDP)",
            "cold_definition": "fresh work dir and profile per run, DB seeded from the Phase C template",
            "warm_definition": "one unrecorded warmup, then same work dir/profile reused",
            "crash": "with --crash the shell root is terminated after the first board paint; "
                     "orphans are recorded and then killed by the harness",
        },
        "timings_ms": {k: stat(k) for k in keys},
        "rss_mb": {
            "peak": {"n": len(peak), "median": round(statistics.median(peak), 1) if peak else None,
                     "values": peak},
            "idle": {"n": len(idle), "median": round(statistics.median(idle), 1) if idle else None,
                     "values": idle},
        },
        "idle_cpu_pct_one_core": {
            "n": len(idle_cpu),
            "median": round(statistics.median(idle_cpu), 1) if idle_cpu else None,
            "values": idle_cpu,
        },
        "runs_ok": len(ok_runs),
        "runs_total": len(runs),
        "security": [r.get("security") for r in runs if r.get("security")],
        "security_all_ok": (all(v.get("ok") for r in runs
                               for v in (r.get("security") or {}).values())
                            if any(r.get("security") for r in runs) else None),
        "exit_codes": [((r.get("shutdown") or {}).get("exit_code")) for r in runs],
        "cleanup": [((r.get("shutdown") or {}).get("cleanup_final")) for r in runs],
        "crash_runs": [r.get("run") for r in runs if r.get("crash_kill")],
        "crash_orphans": sum(len(((r.get("shutdown") or {}).get("cleanup") or {})
                               .get("survivors_before") or [])
                             for r in runs if r.get("crash_kill")),
        "runs": runs,
    }


def compact(summary: dict) -> dict:
    keep = ["label", "mode", "scenario", "generated_at", "host", "protocol",
            "timings_ms", "rss_mb", "idle_cpu_pct_one_core", "security",
            "security_all_ok", "exit_codes", "cleanup", "crash_runs", "crash_orphans", "partial",
            "runs_ok", "runs_total"]
    out = {k: summary[k] for k in keep if k in summary}
    runs = []
    for r in summary.get("runs", []):
        final = r.get("final") or {}
        runs.append({
            "run": r.get("run"),
            "mode": r.get("mode"),
            "timings_ms": r.get("timings_ms"),
            "window": r.get("window"),
            "process": {
                "peak": (r.get("process") or {}).get("peak"),
                "stages": {
                    k: {"rss_mb": v.get("rss_mb"), "cpu_s": v.get("cpu_s"),
                        "procs": v.get("procs"), "names": sorted({x["name"] for x in v.get("rows", [])})}
                    for k, v in ((r.get("process") or {}).get("stages") or {}).items()
                },
            },
            "idle": r.get("idle"),
            "shutdown": r.get("shutdown"),
            "probe_instances": r.get("probe_instances"),
            "screenshots": {k: {"ok": v.get("ok"), "w": v.get("w"), "h": v.get("h")}
                            for k, v in (r.get("screenshots") or {}).items()},
            "final": {
                "ok": final.get("ok"),
                "states": final.get("states"),
                "events": {k: {"epoch_ms": v.get("epoch_ms"), "perf_ms": v.get("perf_ms"),
                               "url": v.get("url")} for k, v in (final.get("events") or {}).items()},
                "technical_ready": (final.get("events") or {}).get("technical_ready"),
                "resources": final.get("resources"),
                "errors": final.get("errors"),
            },
            "errors": r.get("errors"),
            "firewall_prompts": r.get("firewall_prompts"),
            "error_window": r.get("error_window"),
            "final_run_ids": r.get("final_run_ids"),
        })
    out["runs"] = runs
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--mode", choices=["cold", "warm"], default="cold")
    ap.add_argument("--scenario", choices=["normal", "fail"], default="normal")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--shell-label", default="")
    ap.add_argument("--symbol", default="فولاد")
    ap.add_argument("--symbol2", default="آباد")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--d3", action="store_true")
    ap.add_argument("--visual", action="store_true",
                    help="pause the page at each milestone for PrintWindow captures")
    ap.add_argument("--crash", action="store_true",
                    help="kill the shell root after the first board paint and record orphans")
    ap.add_argument("--keep-work", action="store_true")
    args = ap.parse_args()
    args.exe = Path(args.exe)
    template = Path(args.template)
    if not args.exe.exists():
        raise SystemExit(f"missing shell exe: {args.exe}")
    if not template.exists():
        raise SystemExit(f"missing template dir: {template}")
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "artifacts/desktop-migration/phase-d" / args.label
    out_dir.mkdir(parents=True, exist_ok=True)

    base = SCRATCH_ROOT / args.label
    if base.exists() and (args.mode == "cold" or not args.keep_work):
        # only our own scratch tree; never touch user data
        shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True, exist_ok=True)

    runs: list[dict] = []

    def persist(partial: bool) -> dict:
        summary = summarize(runs, args)
        summary["partial"] = partial
        (out_dir / "summary.json").write_text(
            json.dumps(compact(summary), ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "summary-full.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        rep = next((r for r in runs if r.get("final")), runs[0] if runs else None)
        if rep:
            wanted = ("market_rows_visible", "technical_ready", "fundamental_ready",
                      "market_status_ready", "error", "window_first", "d3_raw_mode",
                      "d3_symbol2_ready")
            for name, shot in (rep.get("screenshots") or {}).items():
                if not shot.get("path"):
                    continue
                src = Path(shot["path"])
                if src.exists() and name in wanted:
                    shutil.copy2(src, out_dir / f"{name}.png")
                alt = (shot.get("screen") or {}).get("path")
                if alt and Path(alt).exists() and name in (
                        "market_rows_visible", "technical_ready", "fundamental_ready",
                        "market_status_ready", "d3_symbol2_ready"):
                    shutil.copy2(alt, out_dir / f"{name}.screen.png")
        print(f"[summary] partial={partial} runs={len(runs)} "
              f"ok={summary['runs_ok']} out={out_dir}", flush=True)
        return summary

    def _sigterm(_signum, _frame):
        raise KeyboardInterrupt("SIGTERM")

    try:
        signal.signal(signal.SIGTERM, _sigterm)
    except (ValueError, OSError):
        pass

    interrupted = False
    summary = None
    try:
        if args.mode == "warm" and args.warmup > 0:
            for i in range(args.warmup):
                print(f"[warmup {i+1}/{args.warmup}] ...", flush=True)
                try:
                    w = run_once(args, args.mode, 0, template)
                    print(f"[warmup] ok={bool(w.get('final'))} "
                          f"err={len(w.get('errors') or [])} "
                          f"elapsed={w.get('elapsed_ms')}ms", flush=True)
                except Exception:
                    print("[warmup] EXCEPTION\n" + traceback.format_exc(), flush=True)
        for i in range(1, args.runs + 1):
            print(f"[run {i}/{args.runs}] {args.label} {args.mode} ...", flush=True)
            try:
                r = run_once(args, args.mode, i, template)
            except KeyboardInterrupt:
                raise
            except Exception:
                r = {"label": args.label, "mode": args.mode,
                     "scenario": args.scenario, "run": i, "final": None,
                     "errors": [traceback.format_exc()], "fatal": True}
                print(f"[run {i}] EXCEPTION\n{r['errors'][0]}", flush=True)
            runs.append(r)
            t = r.get("timings_ms") or {}
            print(f"[run {i}] ok={bool(r.get('final'))} "
                  f"errors={len(r.get('errors') or [])} "
                  f"ready={t.get('sidecar_ready_line')} window={t.get('window_visible')} "
                  f"board={t.get('market_rows_visible')} chart={t.get('technical_ready')} "
                  f"fund={t.get('fundamental_ready')} "
                  f"peak={((r.get('process') or {}).get('peak') or {}).get('rss_mb')}MB "
                  f"exit={((r.get('shutdown') or {}).get('exit_code'))}", flush=True)
            if args.scenario == "fail":
                print(f"[run {i}] error_window={bool(r.get('error_window'))} "
                      f"shell={((r.get('shutdown') or {}).get('shell_tail') or [])[-2:]}",
                      flush=True)
            persist(partial=(i < args.runs))
    except KeyboardInterrupt:
        interrupted = True
        print("[interrupted] external stop; writing partial summary", flush=True)
    finally:
        summary = persist(partial=interrupted or len(runs) < args.runs)
        print("OUT", out_dir, flush=True)

    if summary is None:
        return 1
    if args.scenario == "fail":
        return 1
    if args.crash:
        return 0 if runs and all(r.get("crash_kill") for r in runs) else 1
    return 0 if runs and summary["runs_ok"] == len(runs) else 1


if __name__ == "__main__":
    sys.exit(main())
