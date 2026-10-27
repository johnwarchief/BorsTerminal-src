#!/usr/bin/env python
"""C — shell-only spike probe: TinyJS vs Tauri, same backend, same UI.

Both shells load http://127.0.0.1:8140 served by the v1.0.98 backend. This
script measures the SHELL, not the product:
  * spawn -> first `GET /` seen in the backend access log (shell startup cost)
  * spawn -> last initial asset -> /api/market response (page bootstrap)
  * RSS / CPU of the shell process tree (idle + UI phases)
  * TinyJS in-window probe results, POSTed by the injected script to the local
    collector started here (its launcher ignores WebView2 flags by design, so
    CDP is impossible on a built .exe)
  * Tauri UI phases via fe_probe.js over CDP (the shell window exposes it)

Safety: starts only the EXE it was given, kills only that PID tree, never
touches the operational databases or the network (the backend is the caller's
responsibility and must already be the offline-gated copy).

usage:
  python tools/migration/shell_probe.py --exe <path> --label tinyjs \
      --backend-log <uvicorn.log> --launches 2 --idle 20 \
      --out _audit/perf/MIG_SHELL_tinyjs.json
  python tools/migration/shell_probe.py --exe <path> --label tauri \
      --backend-log <uvicorn.log> --cdp-port 9334 --viewports 1366x768,1920x1080 \
      --out _audit/perf/MIG_SHELL_tauri.json
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import shutil
import statistics
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import psutil

REPO = Path(__file__).resolve().parents[2]
SPIKE = Path(r"C:\Users\PCMOD\AppData\Local\Temp\bors_shell_spike_2026-10-27")


class Collector(http.server.BaseHTTPRequestHandler):
    posts: list[dict] = []

    def do_POST(self):  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8", "replace")
        try:
            self.posts.append({"t": time.time(), "body": json.loads(body)})
        except json.JSONDecodeError:
            self.posts.append({"t": time.time(), "raw": body[:2000]})
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, *args):  # silence
        pass


def window_titles(pids: set[int]) -> dict[int, str]:
    """Visible top-level window titles for the given PIDs (Win32, no network)."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    out: dict[int, str] = {}

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids:
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                out[int(hwnd)] = buf.value
        return True

    user32.EnumWindows(cb, 0)
    return out


class TitleWatcher(threading.Thread):
    """Records window-title changes — the TinyJS probe's out-of-band channel."""

    def __init__(self, pid: int, interval: float = 0.4):
        super().__init__(daemon=True)
        self.pid = pid
        self.interval = interval
        self.stop_evt = threading.Event()
        self.timeline: list[dict] = []

    def run(self) -> None:
        last = ""
        while not self.stop_evt.is_set():
            try:
                titles = list(window_titles(set(tree_pids(self.pid))).values())
            except OSError:
                titles = []
            joined = " || ".join(t for t in titles if t)
            if joined and joined != last:
                self.timeline.append({"t": round(time.time(), 2), "title": joined[:300]})
                last = joined
            self.stop_evt.wait(self.interval)


def start_collector(port: int) -> http.server.ThreadingHTTPServer:
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Collector)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class LogWatcher(threading.Thread):
    """Follows the backend access log from a byte offset and timestamps lines."""

    def __init__(self, path: Path, offset: int):
        super().__init__(daemon=True)
        self.path = path
        self.offset = offset
        self.stop_evt = threading.Event()
        self.lines: list[dict] = []

    def run(self) -> None:
        while not self.stop_evt.is_set():
            try:
                with open(self.path, "rb") as f:
                    f.seek(self.offset)
                    data = f.read()
                    self.offset = f.tell()
                for raw in data.splitlines():
                    line = raw.decode("utf-8", "replace").strip()
                    if line:
                        self.lines.append({"t": time.time(), "line": line})
            except OSError:
                pass
            self.stop_evt.wait(0.025)

    def find(self, needle: str, start: int = 0) -> float | None:
        for row in self.lines[start:]:
            if needle in row["line"]:
                return row["t"]
        return None


class Sampler(threading.Thread):
    def __init__(self, pid: int, profile_root: str, interval: float = 0.5):
        super().__init__(daemon=True)
        self.pid = pid
        self.profile_root = profile_root.lower()
        self.interval = interval
        self.stop_evt = threading.Event()
        self.samples: list[dict] = []
        self.phase = "boot"
        self._last_cpu: float | None = None
        self._last_wall: float | None = None

    def _tree(self) -> list[psutil.Process]:
        procs: dict[int, psutil.Process] = {}
        try:
            root = psutil.Process(self.pid)
            for p in [root] + root.children(recursive=True):
                procs[p.pid] = p
        except psutil.Error:
            pass
        # WebView2 children can be re-parented; attribute them by the isolated
        # profile path, never by image name alone.
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if p.pid in procs:
                    continue
                cmd = " ".join(p.cmdline())
                if self.profile_root in cmd.lower():
                    procs[p.pid] = p
            except psutil.Error:
                pass
        return list(procs.values())

    def run(self) -> None:
        while not self.stop_evt.is_set():
            procs = self._tree()
            rss = 0
            cpu = 0.0
            for p in procs:
                try:
                    rss += p.memory_info().rss
                    times = p.cpu_times()
                    cpu += times.user + times.system
                except psutil.Error:
                    pass
            wall = time.perf_counter()
            cores = None
            if self._last_cpu is not None and self._last_wall is not None and wall > self._last_wall:
                cores = round((cpu - self._last_cpu) / (wall - self._last_wall), 2)
            self._last_cpu, self._last_wall = cpu, wall
            self.samples.append({
                "t": round(time.time(), 2),
                "phase": self.phase,
                "rss_mb": round(rss / 1e6, 1),
                "cores": cores,
                "procs": len(procs),
            })
            self.stop_evt.wait(self.interval)

    def summary(self) -> dict:
        out = {}
        for phase in sorted({s["phase"] for s in self.samples}):
            rows = [s for s in self.samples if s["phase"] == phase]
            if not rows:
                continue
            rss = [s["rss_mb"] for s in rows]
            cores = [s["cores"] for s in rows if s["cores"] is not None]
            out[phase] = {
                "n": len(rows),
                "rss_mb_median": round(statistics.median(rss), 1),
                "rss_mb_max": round(max(rss), 1),
                "cores_median": round(statistics.median(cores), 2) if cores else None,
                "cores_max": round(max(cores), 2) if cores else None,
                "procs_max": max(s["procs"] for s in rows),
            }
        return out


def stop_tree(pid: int, profile_root: str = "") -> list[int]:
    killed = []
    procs: dict[int, psutil.Process] = {}
    try:
        root = psutil.Process(pid)
        for p in root.children(recursive=True) + [root]:
            procs[p.pid] = p
    except psutil.Error:
        pass
    # Re-parented launcher/WebView2 children are attributed by the isolated
    # profile path so we never kill a browser process we did not start.
    for p in psutil.process_iter(["pid"]):
        try:
            cmd = " ".join(p.cmdline()).lower()
            if profile_root and profile_root.lower() in cmd:
                procs[p.pid] = p
        except psutil.Error:
            pass
    for p in procs.values():
        try:
            if p.is_running():
                p.kill()
                killed.append(p.pid)
        except psutil.Error:
            pass
    return killed


def tree_pids(pid: int, profile_root: str = "") -> list[int]:
    pids = [pid]
    try:
        pids += [c.pid for c in psutil.Process(pid).children(recursive=True)]
    except psutil.Error:
        pass
    for p in psutil.process_iter(["pid"]):
        try:
            if profile_root and profile_root.lower() in " ".join(p.cmdline()).lower():
                pids.append(p.pid)
        except psutil.Error:
            pass
    return sorted(set(pids))


def wait_until(fn, timeout: float, step: float = 0.02):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout:
        val = fn()
        if val:
            return val
        time.sleep(step)
    return None


def cdp_ready(port: int) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=0.5) as r:
            return r.status == 200
    except Exception:
        return False


def launch(args, launch_no: int, profile: Path, log_path: Path, watcher: LogWatcher, sampler_out: list, title_out: list) -> dict:
    env = os.environ.copy()
    env.update({
        "LOCALAPPDATA": str(profile),
        "PYTHONIOENCODING": "utf-8",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
        "NO_PROXY": "127.0.0.1,localhost,::1",
        "no_proxy": "127.0.0.1,localhost,::1",
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": (
            f"--remote-debugging-port={args.cdp_port} " if args.cdp_port else ""
        ) + "--disable-background-networking --disable-component-update --no-first-run "
            "--disable-features=Translate,OptimizationHints,MediaRouter",
    })
    log = open(log_path, "wb")
    t0 = time.perf_counter()
    t0_wall = time.time()   # the log watcher timestamps with time.time()
    base_idx = len(watcher.lines)   # only this launch's requests count
    proc = subprocess.Popen([str(args.exe)], cwd=str(Path(args.exe).parent), env=env,
                            stdout=log, stderr=subprocess.STDOUT)
    sampler = Sampler(proc.pid, str(profile))
    sampler.start()
    sampler_out.append(sampler)
    titles = TitleWatcher(proc.pid)
    titles.start()
    title_out.append(titles)
    out = {"pid": proc.pid, "log": str(log_path), "launch": launch_no}
    try:
        first = wait_until(lambda: watcher.find("GET / HTTP/1.1", base_idx), 120)
        out["first_http_ms"] = round((first - t0_wall) * 1000) if first else None
        if first:
            # The landing route is /master, so /api/market is NOT the first API
            # call (the app only asks for it on the board tab). The first /api/*
            # response is the shell-independent "UI is alive and talking" signal;
            # uvicorn logs a line only after the response completes.
            api = wait_until(lambda: next(
                (r for r in watcher.lines[base_idx:] if "GET /api/" in r["line"]), None), 180)
            if api:
                out["first_api_ms"] = round((api["t"] - t0_wall) * 1000)
                out["first_api"] = api["line"].split('"')[1] if '"' in api["line"] else api["line"]
            cutoff = (api or {}).get("t") or time.time()
            assets = [r["t"] for r in watcher.lines[base_idx:] if r["t"] <= cutoff
                      and ("GET /assets/" in r["line"] or "GET /vendor/" in r["line"])]
            out["assets_last_ms"] = round((max(assets) - t0_wall) * 1000) if assets else None
        if args.cdp_port:
            out["cdp_ms"] = round((time.perf_counter() - t0) * 1000) if wait_until(lambda: cdp_ready(args.cdp_port), 90) else None
        if out.get("first_api_ms"):
            sampler.phase = "idle"
            time.sleep(args.idle)
        out["alive"] = proc.poll() is None
        return out
    finally:
        log.close()


def run_ui(args, label: str, ui_out: list) -> None:
    node = shutil.which("node")
    if not node:
        ui_out.append({"error": "node not on PATH"})
        return
    probe = REPO / "tools" / "migration" / "fe_probe.js"
    for vp in args.viewports.split(","):
        name = f"MIG_SHELL_{label}_{vp}.json"
        env = os.environ.copy()
        env.update({
            "BORS_CDP": f"http://127.0.0.1:{args.cdp_port}",
            "BORS_UI_BASE": args.ui_base,
            "BORS_VIEWPORT": vp,
            "BORS_LABEL": f"{label}-{vp}",
            "BORS_RUNS": str(args.runs),
            "BORS_DEADLINE_MS": "180000",
            "BORS_SHOT": f"MIG_SHELL_{label}_{vp}.png",
        })
        log_path = args.out.parent / f"ui_{label}_{vp}.log"
        with open(log_path, "wb") as log:
            cp = subprocess.run([node, str(probe), "--out", name], cwd=str(REPO), env=env,
                                stdout=log, stderr=subprocess.STDOUT, timeout=2400)
        ui_out.append({"viewport": vp, "exit": cp.returncode,
                       "json": str(REPO / "_audit" / "perf" / name), "log": str(log_path)})


def screenshot_window(pids: list[int], out: Path) -> bool:
    ps = f"""
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class W {{
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  public struct RECT {{ public int L, T, R, B; }}
}}
'@
$p = $null
foreach ($id in @({','.join(str(p) for p in pids)})) {{
  $c = Get-Process -Id $id -ErrorAction SilentlyContinue
  if ($c -and $c.MainWindowHandle -ne 0) {{ $p = $c; break }}
}}
if (-not $p -or $p.MainWindowHandle -eq 0) {{ exit 2 }}
[W]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 700
$r = New-Object W+RECT
[W]::GetWindowRect($p.MainWindowHandle, [ref]$r) | Out-Null
$w = $r.R - $r.L; $h = $r.B - $r.T
if ($w -le 0 -or $h -le 0) {{ exit 3 }}
$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
$bmp.Save('{out.as_posix()}', [System.Drawing.Imaging.ImageFormat]::Png)
exit 0
"""
    try:
        cp = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                            capture_output=True, timeout=30)
        return cp.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--backend-log", required=True)
    ap.add_argument("--ui-base", default="http://127.0.0.1:8140")
    ap.add_argument("--collector-port", type=int, default=8151)
    ap.add_argument("--cdp-port", type=int, default=0)
    ap.add_argument("--viewports", default="1366x768")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--launches", type=int, default=1)
    ap.add_argument("--idle", type=float, default=20)
    ap.add_argument("--probe-wait", type=float, default=300,
                    help="how long to wait for the injected probe; 0 skips it")
    ap.add_argument("--profile", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    args.exe = Path(args.exe)
    args.out = Path(args.out)

    profile = Path(args.profile) if args.profile else SPIKE / f"profile_{args.label}"
    profile.mkdir(parents=True, exist_ok=True)
    srv = start_collector(args.collector_port)

    watcher = LogWatcher(Path(args.backend_log), Path(args.backend_log).stat().st_size)
    watcher.start()

    report = {
        "label": args.label,
        "exe": str(args.exe),
        "exe_mb": round(args.exe.stat().st_size / 1e6, 2) if args.exe.exists() else None,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "profile": str(profile),
        "launches": [],
        "ui": [],
        "shots": [],
        "collector_posts": [],
    }
    samplers: list[Sampler] = []
    title_watchers: list[TitleWatcher] = []
    try:
        for i in range(1, args.launches + 1):
            info = launch(args, i, profile, args.out.parent / f"shell_{args.label}_L{i}.log", watcher, samplers, title_watchers)
            report["launches"].append(info)
            sampler = samplers[-1]
            print(f"[{args.label}] launch {i}: first GET /={info.get('first_http_ms')}ms "
                  f"first_api={info.get('first_api_ms')}ms cdp={info.get('cdp_ms')}ms", flush=True)
            if args.cdp_port and i == args.launches:
                sampler.phase = "ui"
                run_ui(args, args.label, report["ui"])
            if not args.cdp_port:
                sampler.phase = "probe"
                # The wrapped TinyJS page could not POST to the collector in
                # either fetch mode; the injected probe also writes milestones
                # into the window title, so a finished title ends the wait too.
                def probe_done():
                    if Collector.posts:
                        return True
                    return any("BSP|done" in row["title"]
                               for tw in title_watchers for row in tw.timeline)
                got = wait_until(probe_done, args.probe_wait) if args.probe_wait > 0 else None
                if got:
                    report["collector_posts"] = Collector.posts
                    print(f"[{args.label}] collector received a report "
                          f"({len(Collector.posts)} post(s))", flush=True)
                else:
                    print(f"[{args.label}] no collector report arrived", flush=True)
                shot = args.out.parent / f"MIG_SHELL_{args.label}_window.png"
                if screenshot_window(tree_pids(info["pid"], str(profile)), shot):
                    report["shots"].append(str(shot))
            sampler.phase = "stop"
            report["launches"][-1]["killed"] = stop_tree(info["pid"], str(profile))
            title_watchers[-1].stop_evt.set()
            report[f"launch_titles_{i}"] = title_watchers[-1].timeline
            time.sleep(2)
            report["process_" + str(i)] = sampler.summary()
    finally:
        for s in samplers:
            s.stop_evt.set()
        for tw in title_watchers:
            tw.stop_evt.set()
        watcher.stop_evt.set()
        srv.shutdown()

    report["backend_lines"] = len(watcher.lines)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
