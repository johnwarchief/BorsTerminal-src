#!/usr/bin/env python3
"""Window-level benchmark for the TinyJS shell (no CDP available).

TinyJS/WebView2 does not forward WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS, so the
Puppeteer harness cannot attach. This script measures the same prototype from
the outside: process start -> window visible, TinyJS navigation log, proxy log
for API completion, Win32 PrintWindow screenshots, and process-tree RAM/CPU.
In-page metrics (JS heap, rAF frame time, console errors) are NOT_MEASURED.

usage:
  python tools/desktop-migration/bench_tinyjs.py --runs 3 \
    --exe _tools/tinyjs-site/dist/BorsTerminalM1TinyJS.exe \
    --server-log _proto-server.log
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
USER32 = ctypes.windll.user32
KERNEL32 = ctypes.windll.kernel32
WM_CLOSE = 0x0010
SW_RESTORE = 9
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def find_window(title: str) -> int:
    found: list[int] = []

    def cb(hwnd, _):
        n = USER32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            USER32.GetWindowTextW(hwnd, buf, n + 1)
            if title in buf.value:
                found.append(hwnd)
        return True

    USER32.EnumWindows(WNDENUMPROC(cb), 0)
    return found[0] if found else 0


def client_origin(hwnd: int) -> tuple[int, int]:
    pt = wintypes.POINT(0, 0)
    USER32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def client_size(hwnd: int) -> tuple[int, int]:
    r = wintypes.RECT()
    USER32.GetClientRect(hwnd, ctypes.byref(r))
    return r.right, r.bottom


def click_client(hwnd: int, x: int, y: int) -> None:
    ox, oy = client_origin(hwnd)
    USER32.SetCursorPos(ox + x, oy + y)
    time.sleep(0.12)
    USER32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    USER32.mouse_event(0x0004, 0, 0, 0, 0)


def type_text(text: str) -> None:
    for ch in text:
        vk = USER32.VkKeyScanW(ord(ch)) & 0xFF
        USER32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.03)
        USER32.keybd_event(vk, 0, 2, 0)
        time.sleep(0.03)
    USER32.keybd_event(0x0D, 0, 0, 0)
    time.sleep(0.03)
    USER32.keybd_event(0x0D, 0, 2, 0)


def screenshot(hwnd: int, path: Path) -> None:
    script = ROOT / "tools" / "desktop-migration" / "printwin.ps1"
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
         "-out", str(path.relative_to(ROOT))],
        cwd=ROOT, capture_output=True, timeout=60,
    )


def tree_processes(root_pid: int) -> list[psutil.Process]:
    try:
        root = psutil.Process(root_pid)
    except psutil.Error:
        return []
    procs = [root]
    try:
        procs.extend(root.children(recursive=True))
    except psutil.Error:
        pass
    return procs


def snapshot(root_pid: int) -> dict:
    procs = tree_processes(root_pid)
    now = time.perf_counter()
    rows = []
    for p in procs:
        try:
            rows.append({
                "pid": p.pid,
                "name": p.name(),
                "rssMB": round(p.memory_info().rss / 1048576),
                "cpuSeconds": round(sum(p.cpu_times()[:2]), 3),
            })
        except psutil.Error:
            pass
    return {
        "t": now,
        "processes": rows,
        "rssMB": sum(r["rssMB"] for r in rows),
        "cpuSeconds": round(sum(r["cpuSeconds"] for r in rows), 3),
    }


class ProxyLog:
    def __init__(self, path: Path):
        self.path = path
        self.offset = path.stat().st_size if path.exists() else 0
        self.lines: list[dict] = []
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while not self.stop.is_set():
            try:
                with open(self.path, "r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(self.offset)
                    for line in fh:
                        if not line.endswith("\n"):
                            break
                        self.offset += len(line.encode("utf-8"))
                        m = re.match(r"\[proxy\] ([\d.]+) (\S+) (\S+) -> (\d+) (\d+)ms", line)
                        if m:
                            with self.lock:
                                self.lines.append({
                                    "t": float(m.group(1)),
                                    "method": m.group(2),
                                    "path": m.group(3),
                                    "status": int(m.group(4)),
                                    "ms": int(m.group(5)),
                                })
            except FileNotFoundError:
                pass
            self.stop.wait(0.1)

    def since(self, t: float, needle: str) -> dict | None:
        with self.lock:
            for row in self.lines:
                if row["t"] >= t and needle in row["path"] and 200 <= row["status"] < 300:
                    return row
        return None

    def wait_for(self, t: float, needle: str, timeout: float) -> dict | None:
        end = time.time() + timeout
        while time.time() < end:
            row = self.since(t, needle)
            if row:
                return row
            time.sleep(0.08)
        return None

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)


def cleanup() -> None:
    subprocess.run(["taskkill.exe", "/IM", "BorsTerminalM1TinyJS.exe", "/T", "/F"],
                   capture_output=True)
    subprocess.run(["taskkill.exe", "/IM", "launcher.exe", "/T", "/F"], capture_output=True)
    time.sleep(1.5)
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if p.info["name"] and p.info["name"].lower() == "msedgewebview2.exe" and \
                    any("ip-127-0-0-1.wrap" in (a or "") for a in (p.info["cmdline"] or [])):
                p.kill()
        except psutil.Error:
            pass
    time.sleep(1.0)


def run_once(args, run: int, out_dir: Path, log: ProxyLog) -> dict:
    run_dir = out_dir / f"run-{run}"
    run_dir.mkdir(parents=True, exist_ok=True)
    cleanup()
    env = {
        **os.environ,
        "TINYJS_DEBUG": "1",
    }
    stdout_lines: list[str] = []
    nav_finish: list[float] = []

    t0 = time.perf_counter()
    t0_wall = time.time()
    child = subprocess.Popen([str(args.exe)], cwd=ROOT, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", bufsize=1)

    def reader():
        for line in child.stdout:
            stdout_lines.append(line.rstrip())
            if "[nav] finish" in line:
                nav_finish.append(time.perf_counter())

    threading.Thread(target=reader, daemon=True).start()

    hwnd = 0
    deadline = time.time() + 60
    while time.time() < deadline:
        hwnd = find_window("BorsTerminalM1TinyJS")
        if hwnd:
            break
        time.sleep(0.025)
    window_ms = round((time.perf_counter() - t0) * 1000)
    if not hwnd:
        raise RuntimeError("window did not appear within 60s")

    USER32.ShowWindow(hwnd, SW_RESTORE)
    USER32.SetForegroundWindow(hwnd)
    # the launcher clamps width to the screen work area; height can reach 768
    USER32.SetWindowPos(hwnd, 0, 0, 0, 1300, 807, SWP_NOZORDER | SWP_NOACTIVATE)
    time.sleep(0.4)
    cw, ch = client_size(hwnd)

    page_deadline = time.time() + 60
    while not nav_finish and time.time() < page_deadline:
        time.sleep(0.05)
    page_ms = round((nav_finish[0] - t0) * 1000) if nav_finish else None

    # login page: username is prefilled; password field is centered horizontally
    time.sleep(0.8)
    t_login = time.time()
    click_client(hwnd, cw // 2, 432)
    time.sleep(0.25)
    type_text("bors123")
    market = log.wait_for(t_login, "/api/market", 120)
    if not market:
        raise RuntimeError("market response not observed after login")
    login_to_market_ms = round((market["t"] - t_login) * 1000)
    market_ms = round((market["t"] - t0_wall) * 1000)
    time.sleep(2.0)
    screenshot(hwnd, run_dir / "market.png")

    # technical page: rail item below the active market item
    t_tech = time.time()
    click_client(hwnd, 1195, 163)
    chart = log.wait_for(t_tech, "/api/chart/", 120)
    if not chart:
        raise RuntimeError("chart response not observed after technical click")
    tech_ms = round((chart["t"] - t_tech) * 1000)
    time.sleep(2.5)
    screenshot(hwnd, run_dir / "technical.png")

    idle0 = snapshot(child.pid)
    time.sleep(3.0)
    idle1 = snapshot(child.pid)
    result = {
        "run": run,
        "label": "tinyjs",
        "windowMs": window_ms,
        "pageMs": page_ms,
        "client": [cw, ch],
        "loginToMarketMs": login_to_market_ms,
        "marketMs": market_ms,
        "marketRequestMs": market["ms"],
        "technicalMs": tech_ms,
        "chartRequestMs": chart["ms"],
        "rssMB": idle1["rssMB"],
        "idleCpuSeconds3s": round(idle1["cpuSeconds"] - idle0["cpuSeconds"], 3),
        "processes": idle1["processes"],
        "stdoutTail": stdout_lines[-12:],
        "consoleErrors": "NOT_MEASURED (TinyJS does not expose CDP)",
        "jsHeapMB": "NOT_MEASURED",
        "scroll": "NOT_MEASURED",
    }

    try:
        USER32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        child.wait(timeout=8)
    except Exception:
        pass
    if child.poll() is None:
        subprocess.run(["taskkill.exe", "/PID", str(child.pid), "/T", "/F"], capture_output=True)
    time.sleep(2.0)
    cleanup()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=str(ROOT / "_tools/tinyjs-site/dist/BorsTerminalM1TinyJS.exe"))
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", default=str(ROOT / "artifacts/desktop-migration"))
    ap.add_argument("--server-log", default=str(ROOT / "_proto-server.log"))
    args = ap.parse_args()
    args.exe = Path(args.exe)
    if not args.exe.exists():
        raise SystemExit(f"missing TinyJS exe: {args.exe}")

    stamp = time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    out_dir = Path(args.out) / f"{stamp}-tinyjs"
    out_dir.mkdir(parents=True, exist_ok=True)
    log = ProxyLog(Path(args.server_log))
    rows = []
    try:
        for i in range(1, args.runs + 1):
            try:
                r = run_once(args, i, out_dir, log)
            except Exception as exc:
                r = {"run": i, "label": "tinyjs", "error": str(exc)[:800]}
            (out_dir / f"run-{i}.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
            rows.append(r)
            print(json.dumps({k: r.get(k) for k in ("run", "windowMs", "pageMs", "loginToMarketMs",
                                                    "marketMs", "technicalMs", "rssMB", "error")},
                             ensure_ascii=False), flush=True)
    finally:
        log.close()
    summary = {
        "label": "tinyjs",
        "exe": str(args.exe),
        "exeBytes": args.exe.stat().st_size,
        "launcherBytes": (args.exe.parent / "launcher.exe").stat().st_size,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runs": rows,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OUT", out_dir)


if __name__ == "__main__":
    sys.exit(main())
