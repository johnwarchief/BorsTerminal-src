#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase C startup harness for the current pywebview shell.

Measures the real launch path from process start to a usable board/chart:
process tree RSS/CPU, boot/preflight/uvicorn stage marks, WebView2 CDP page
stages (login, board, technical, fundamental), and API resource timings.

It runs against an isolated WORK_DIR + WebView2 profile, with network loops and
the Codal worker off, so no second TSETMC fetcher competes with an installed
app. Cold = fresh work dir + fresh profile per run. Warm = one seeded work dir
and profile reused (one unrecorded warmup). A separate --mode cold-data run can
measure first-run DB extraction from market.db.lzma.

Example:
  .venv/Scripts/python.exe tools/desktop-migration/phase_c_startup.py \
    --label source-cold --mode cold --runs 5 \
    --template %TEMP%/bors_phasec/template \
    --out-dir artifacts/desktop-migration/phase-c/source-cold
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
NODE = ROOT / "_tools" / "node" / "node.exe"
PROBE = ROOT / "frontend" / "tools" / "desktop-migration" / "phase_c_probe.mjs"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
CREATE_NO_WINDOW = 0x08000000


def now_ms() -> float:
    return time.time() * 1000.0


def free_port() -> int:
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


def http_ok(url: str, timeout: float = 0.6) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


def http_json(url: str, timeout: float = 1.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


class TreeSampler:
    """Samples the app process tree at 100 ms.

    With extra_match (e.g. an Edge --user-data-dir), browser processes that
    detach from the launcher are included too.
    """

    def __init__(self, root_pid: int, launch_epoch_ms: float, extra_match: str | None = None):
        self.root_pid = root_pid
        self.launch = launch_epoch_ms
        self.extra_match = extra_match
        self.samples: list[dict] = []
        self.peak = {"rss_mb": 0.0, "epoch_ms": None, "procs": 0, "names": []}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

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

    def _loop(self):
        last_cpu = None
        last_wall = None
        while not self._stop.is_set():
            procs = self._tree()
            rss = cpu = 0
            names = []
            for p in procs:
                try:
                    rss += p.memory_info().rss
                    t = p.cpu_times()
                    cpu += t.user + t.system
                    names.append(p.name())
                except psutil.Error:
                    pass
            e = now_ms()
            wall = time.perf_counter()
            cpu_pct = None
            if last_cpu is not None and wall > last_wall:
                cpu_pct = round((cpu - last_cpu) / (wall - last_wall) * 100.0, 1)
            last_cpu, last_wall = cpu, wall
            s = {
                "epoch_ms": round(e, 1),
                "rel_ms": round(e - self.launch, 1),
                "rss_mb": round(rss / 1048576.0, 1),
                "cpu_s": round(cpu, 2),
                "cpu_pct_one_core": cpu_pct,
                "procs": len(procs),
                "names": sorted(set(names)),
            }
            self.samples.append(s)
            if s["rss_mb"] > self.peak["rss_mb"]:
                self.peak = {"rss_mb": s["rss_mb"], "epoch_ms": s["epoch_ms"],
                             "procs": s["procs"], "names": s["names"]}
            self._stop.wait(0.1)


class Run:
    def __init__(self, idx: int, args, out_dir: Path, scratch_root: Path):
        self.idx = idx
        self.args = args
        self.out_dir = out_dir
        self.scratch_root = scratch_root
        self.tag = f"run-{idx:02d}"
        # Profiles and DB copies live in %TEMP%, not under the repo: WebView2
        # creation under Documents took ~75 s on this host (Defender/sync scan),
        # which swamped every page stage and was not representative.
        self.work = scratch_root / self.tag / "work"
        self.localappdata = scratch_root / self.tag / "localappdata"
        self.trace_path = out_dir / self.tag / "startup-trace.jsonl"
        self.log_path = out_dir / self.tag / "app.log"
        self.probe_out = out_dir / self.tag / "probe.json"
        self.probe_log = out_dir / self.tag / "probe.log"
        self.lines: list[dict] = []
        self.launch_epoch_ms = None
        self.launch_perf = None
        self.proc = None
        self.sampler = None
        self.events = {}
        self.log_marks = {}
        self._focus_stop = threading.Event()

    # ---- environment -----------------------------------------------------
    def _prepare(self, reuse: bool):
        self.out_dir.joinpath(self.tag).mkdir(parents=True, exist_ok=True)
        if not reuse:
            if self.work.exists():
                shutil.rmtree(self.work, ignore_errors=True)
            if self.localappdata.exists():
                shutil.rmtree(self.localappdata, ignore_errors=True)
            self.work.mkdir(parents=True)
            self.localappdata.mkdir(parents=True)
            tpl = Path(self.args.template)
            if not tpl.is_dir():
                raise SystemExit(f"template not found: {tpl}")
            lzma_only = self.args.mode == "cold-data"
            for src in tpl.iterdir():
                if src.is_file():
                    if lzma_only and src.name not in ("market.db.lzma",):
                        continue
                    shutil.copy2(src, self.work / src.name)
            if self.args.mode == "cold-data":
                for junk in ("market.db.baseline", "market.db", "user.db"):
                    try:
                        (self.work / junk).unlink()
                    except OSError:
                        pass
        else:
            self.work.mkdir(parents=True, exist_ok=True)
            self.localappdata.mkdir(parents=True, exist_ok=True)
            if self.args.mode != "cold-data" and not (self.work / "market.db").exists():
                tpl = Path(self.args.template)
                if not tpl.is_dir():
                    raise SystemExit(f"template not found: {tpl}")
                for src in tpl.iterdir():
                    if src.is_file() and not (self.work / src.name).exists():
                        shutil.copy2(src, self.work / src.name)
        for p in (self.trace_path, self.probe_out, self.probe_log, self.log_path):
            try:
                p.unlink()
            except OSError:
                pass

    def _env(self, port: int, cdp_port: int) -> dict:
        env = dict(os.environ)
        env.update({
            "BORS_WORK_DIR": str(self.work),
            "BORS_PORT": str(port),
            "BORS_NO_FETCH_LOOPS": "1",
            "BORS_CODAL_AUTO": "0",
            "BORS_SHOW_CONSOLE": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "BORS_STARTUP_TRACE": "1",
            "BORS_STARTUP_TRACE_FILE": str(self.trace_path),
            "LOCALAPPDATA": str(self.localappdata),
            # The harness window is not the foreground window in this agent
            # session; Chromium then occludes it and throttles the boot page's
            # 500 ms poll to ~1/min, which inflated time-to-board to ~140 s.
            # Disable only that measurement artifact; no app behavior changes.
            "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS":
                f"--remote-debugging-port={cdp_port} --remote-allow-origins=* "
                "--disable-background-timer-throttling "
                "--disable-backgrounding-occluded-windows "
                "--disable-renderer-backgrounding "
                "--disable-features=CalculateNativeWinOcclusion,IntensiveWakeUpThrottling",
        })
        for k in ("BORS_DB", "BORS_NATIVE_WINDOW", "BORS_BROWSER_DEBUG_PORT"):
            env.pop(k, None)
        if self.args.browser_fallback:
            env["BORS_NATIVE_WINDOW"] = "0"
            env["BORS_BROWSER_DEBUG_PORT"] = str(cdp_port)
        else:
            env["BORS_NATIVE_WINDOW"] = "1"
        return env

    # ---- launch ----------------------------------------------------------
    def start(self, reuse: bool):
        self._prepare(reuse)
        port, cdp_port = free_port(), free_port()
        while cdp_port == port:
            cdp_port = free_port()
        self.port, self.cdp_port = port, cdp_port
        env = self._env(port, cdp_port)
        cmd = ([str(self.args.executable)] if self.args.executable
               else [str(PY), "bors_entry.py"])
        self.launch_epoch_ms = now_ms()
        self.launch_perf = time.perf_counter()
        self.events["launch"] = {"epoch_ms": self.launch_epoch_ms}

        def reader():
            f = open(self.log_path, "w", encoding="utf-8", errors="replace")
            try:
                for line in self.proc.stdout:
                    e = now_ms()
                    rec = {"epoch_ms": round(e, 1), "rel_ms": round(e - self.launch_epoch_ms, 1),
                           "line": line.rstrip("\r\n")}
                    self.lines.append(rec)
                    f.write(f"{rec['rel_ms']:9.1f}ms {rec['line']}\n")
                    f.flush()
                    self._scan_log(rec)
            finally:
                f.close()

        self.proc = subprocess.Popen(
            cmd, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=CREATE_NO_WINDOW,
        )
        threading.Thread(target=reader, daemon=True).start()
        extra = (str(self.localappdata / "BorsTerminal_Ultimate" / "app_profile")
                 if self.args.browser_fallback else None)
        self.sampler = TreeSampler(self.proc.pid, self.launch_epoch_ms, extra_match=extra)
        self.sampler.start()
        if not self.args.no_focus and not self.args.browser_fallback:
            threading.Thread(target=self._focus_loop, daemon=True).start()

    def _focus_loop(self):
        """Bring the native window to the foreground while measuring.

        The agent session leaves it behind another window; Chromium then treats
        it as occluded and can defer the first navigation by tens of seconds.
        Find the window by owning process (the title is localized, so a title
        match is not reliable). Harness-only; no app code changes.
        """
        user32 = ctypes.windll.user32
        user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
        user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
        user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
        user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
        user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        user32.BringWindowToTop.argtypes = [ctypes.c_void_p]
        user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        found = False
        for _ in range(240):
            if self._focus_stop.is_set():
                return
            try:
                root = psutil.Process(self.proc.pid)
                pids = {root.pid} | {c.pid for c in root.children(recursive=True)}
            except psutil.Error:
                pids = {self.proc.pid}
            hits = []

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def cb(hwnd, _lp):
                pid = ctypes.c_ulong()
                h = ctypes.c_void_p(hwnd)
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                if pid.value in pids and user32.IsWindowVisible(h):
                    n = user32.GetWindowTextLengthW(h)
                    if n:
                        b = ctypes.create_unicode_buffer(n + 1)
                        user32.GetWindowTextW(h, b, n + 1)
                        hits.append((h, b.value))
                return True

            try:
                user32.EnumWindows(cb, 0)
            except Exception:
                pass
            for hwnd, _title in hits:
                try:
                    user32.ShowWindow(hwnd, 3)          # SW_MAXIMIZE
                    # HWND_TOPMOST + NOSIZE|NOMOVE is allowed without the
                    # foreground lock that can reject SetForegroundWindow.
                    user32.SetWindowPos(hwnd, ctypes.c_void_p(-1), 0, 0, 0, 0,
                                        0x0001 | 0x0002)
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass
            if hits and not found:
                found = True
                self.events["native_window_found"] = {
                    "epoch_ms": now_ms(), "hwnd": int(hits[0][0].value or 0),
                    "title": hits[0][1][:120],
                }
            self._focus_stop.wait(0.5)

    def _scan_log(self, rec):
        line = rec["line"]
        table = {
            "smart preflight": "preflight_start_log",
            "everything ready - starting": "preflight_end_log",
            "Application startup complete": "api_startup_complete_log",
            "Uvicorn running on": "uvicorn_running_log",
            "[native] persistent webview profile": "webview_profile_log",
            "[startup] screener warm": "screener_log",
            "[startup] mstat panel cache warmed": "mstat_warm_log",
            "[startup] candle projection spawned": "projection_spawn_log",
            "[boot]": "boot_log",
        }
        for needle, name in table.items():
            if needle in line and name not in self.log_marks:
                self.log_marks[name] = rec

    # ---- waits -----------------------------------------------------------
    def wait_cdp(self, timeout=90.0):
        t0 = time.time()
        url = f"http://127.0.0.1:{self.cdp_port}/json/version"
        while time.time() - t0 < timeout:
            try:
                http_json(url)
                self.events["cdp_available"] = {"epoch_ms": now_ms()}
                return True
            except Exception:
                time.sleep(0.2)
        return False

    def wait_app_http(self, timeout=120.0):
        t0 = time.time()
        url = f"http://127.0.0.1:{self.port}/"
        while time.time() - t0 < timeout:
            if http_ok(url):
                self.events["app_http_ready"] = {"epoch_ms": now_ms()}
                return True
            time.sleep(0.2)
        return False

    # ---- probe -----------------------------------------------------------
    def probe(self, symbol: str, timeout: float):
        env = dict(os.environ)
        env.update({
            "CDP_URL": f"http://127.0.0.1:{self.cdp_port}",
            "APP_URL": f"http://127.0.0.1:{self.port}",
            "SYMBOL": symbol,
            "OUT_JSON": str(self.probe_out),
        })
        with open(self.probe_log, "w", encoding="utf-8", errors="replace") as plog:
            p = subprocess.run(
                [str(NODE), str(PROBE)], cwd=str(ROOT / "frontend"), env=env,
                stdin=subprocess.DEVNULL, stdout=plog, stderr=subprocess.STDOUT,
                timeout=timeout, creationflags=CREATE_NO_WINDOW,
            )
        return p.returncode

    # ---- teardown --------------------------------------------------------
    def stop(self):
        mode = "already-exited"
        if self.proc.poll() is None:
            mode = "forced"
            try:
                targets = http_json(f"http://127.0.0.1:{self.cdp_port}/json/list", timeout=2)
                for t in targets:
                    if t.get("type") == "page":
                        urllib.request.urlopen(
                            f"http://127.0.0.1:{self.cdp_port}/json/close/{t['id']}",
                            timeout=2).read()
                        break
                try:
                    self.proc.wait(timeout=8)
                    mode = "page-close"
                except subprocess.TimeoutExpired:
                    pass
            except Exception:
                pass
            if self.proc.poll() is None:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)],
                               capture_output=True, creationflags=CREATE_NO_WINDOW)
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
        self._focus_stop.set()
        if self.sampler:
            self.sampler.stop()
        port_free = not http_ok(f"http://127.0.0.1:{self.port}/", timeout=0.3)
        return {"mode": mode, "exit_code": self.proc.returncode,
                "port_released": port_free}

    # ---- result ----------------------------------------------------------
    def collect(self, probe_rc, shutdown):
        probe = {}
        if self.probe_out.exists():
            try:
                probe = json.loads(self.probe_out.read_text(encoding="utf-8"))
            except Exception as e:
                probe = {"fatal": f"probe json unreadable: {e}"}
        trace = []
        if self.trace_path.exists():
            for line in self.trace_path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    trace.append(json.loads(line))
                except Exception:
                    pass
        ev = {}
        for rec in trace:
            stage = rec.get("stage")
            if stage and stage not in ev:
                ev[stage] = {"epoch_ms": rec["t"] * 1000.0, "dt": rec.get("dt"),
                             **{k: v for k, v in rec.items()
                                if k not in ("stage", "t", "dt", "pid")}}
        for name, rec in self.log_marks.items():
            ev.setdefault(name, {"epoch_ms": rec["epoch_ms"]})
        for name, rec in (probe.get("events") or {}).items():
            ev.setdefault(name, rec)

        def rel(name):
            r = ev.get(name)
            if not r or not r.get("epoch_ms"):
                return None
            return round(r["epoch_ms"] - self.launch_epoch_ms, 1)

        stages = {k: rel(k) for k in (
            "entry_import", "streams_ready", "serve_start", "boot_server_ready",
            "boot_page_served", "boot_status_poll", "boot_status_ready_seen",
            "window_request", "preflight_start", "db_prepared",
            "library_import_begin", "library_import_end", "native_import_begin",
            "native_import_end", "preflight_end", "uvicorn_spawn", "api_startup_begin", "api_startup_end",
            "http_ready", "app_http_ready", "cdp_available", "native_window_found",
            "boot_ready", "window_start", "app_document_ready", "login_ready", "login_submit",
            "master_ready", "market_rows_visible", "technical_ready",
            "fundamental_ready", "market_publish",
            "screener_warm_done", "screener_low_priority", "screener_wait_board",
            "screener_wait_board_done", "mstat_warm_done", "candle_projection_done",
        )}
        stages = {k: v for k, v in stages.items() if v is not None}

        samples = self.sampler.samples if self.sampler else []
        peak = self.sampler.peak if self.sampler else {}
        rss_at = {}
        cpu_at = {}
        for name, t in stages.items():
            best = min(samples, key=lambda s: abs(s["epoch_ms"] - (self.launch_epoch_ms + t)),
                       default=None)
            if best and abs(best["epoch_ms"] - (self.launch_epoch_ms + t)) < 700:
                rss_at[name] = best["rss_mb"]
                cpu_at[name] = best["cpu_s"]
        idle = None
        idle_stage = "fundamental_ready"
        if idle_stage in stages and samples:
            target = self.launch_epoch_ms + stages[idle_stage] + 2000
            s = min(samples, key=lambda x: abs(x["epoch_ms"] - target), default=None)
            if s:
                idle = {"rss_mb": s["rss_mb"], "cpu_s": s["cpu_s"],
                        "cpu_pct_one_core": s["cpu_pct_one_core"]}
        cpu_stages = {}
        names = list(stages.items())
        for (n1, t1), (n2, t2) in zip(names, names[1:]):
            if t2 <= t1:
                continue
            if n1 in cpu_at and n2 in cpu_at:
                cpu_stages[f"{n1}->{n2}"] = {
                    "wall_s": round((t2 - t1) / 1000.0, 2),
                    "cpu_s": round(cpu_at[n2] - cpu_at[n1], 2),
                }

        resources = probe.get("resources") or []
        api = {}
        for key, match in (
            ("market", lambda n: n == "/api/market" or n.startswith("/api/market?")),
            ("chart", lambda n: n.startswith("/api/chart/")),
            ("fts", lambda n: n.startswith("/api/fts/")),
            ("fundamental", lambda n: n.startswith("/api/fundamental")),
        ):
            hits = [r for r in resources if match(r.get("name", ""))]
            if hits:
                api[key] = {
                    "count": len(hits),
                    "first_duration_ms": hits[0]["duration_ms"],
                    "first_transfer": hits[0].get("transfer_size"),
                    "first_encoded": hits[0].get("encoded_body_size"),
                    "status": hits[0].get("response_status"),
                }
        time_origin = ((probe.get("events") or {}).get("app_document_ready") or {}).get("time_origin")
        if time_origin:
            for key in ("market", "chart", "fts", "fundamental"):
                if key in api:
                    hits = [r for r in resources if (
                        r.get("name") == "/api/market" or r.get("name", "").startswith(
                            {"market": "/api/market?", "chart": "/api/chart/",
                             "fts": "/api/fts/", "fundamental": "/api/fundamental"}[key]))]
                    if hits:
                        api[key]["first_start_rel_ms"] = round(
                            hits[0]["start_ms"] + (time_origin - self.launch_epoch_ms), 1)

        ok = (probe_rc == 0 and not probe.get("fatal")
              and "technical_ready" in stages and "fundamental_ready" in stages
              and (probe.get("states", {}).get("market_rows_after_1s") or 0) > 0)
        return {
            "run": self.idx,
            "ok": bool(ok),
            "ports": {"app": self.port, "cdp": self.cdp_port},
            "stages_rel_ms": stages,
            "rss_mb_at_stage": rss_at,
            "cpu_s_at_stage": cpu_at,
            "cpu_between_stages": cpu_stages,
            "peak_rss_mb": peak.get("rss_mb"),
            "peak_procs": peak.get("procs"),
            "peak_names": peak.get("names"),
            "idle": idle,
            "api": api,
            "probe_states": probe.get("states") or {},
            "probe_metrics": probe.get("metrics") or {},
            "probe_errors": (probe.get("errors") or [])[:20],
            "probe_fatal": probe.get("fatal"),
            "probe_targets": probe.get("target_count"),
            "shutdown": shutdown,
            "log_markers": {k: v["rel_ms"] for k, v in self.log_marks.items()},
            "samples": len(samples),
        }


def aggregate(runs: list[dict], stages: list[str]) -> dict:
    out = {}
    for s in stages:
        vals = [r["stages_rel_ms"][s] for r in runs if s in r.get("stages_rel_ms", {})]
        if not vals:
            continue
        out[s] = {
            "n": len(vals),
            "median_ms": round(statistics.median(vals), 1),
            "min_ms": round(min(vals), 1),
            "max_ms": round(max(vals), 1),
            "p95_ms": round(statistics.quantiles(vals, n=20)[18], 1)
            if len(vals) >= 20 else None,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--mode", choices=("cold", "warm", "cold-data"), default="cold")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--warmup", action="store_true",
                    help="run one unrecorded warmup first (warm mode)")
    ap.add_argument("--template", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--symbol", default="فولاد")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--executable", default=None,
                    help="launch this shell/exe instead of python bors_entry.py")
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--no-focus", action="store_true",
                    help="do not force the native window foreground")
    ap.add_argument("--browser-fallback", action="store_true",
                    help="use the app's supported Edge app-window path with CDP")
    ap.add_argument("--scratch-dir", default=None,
                    help="work/profile root (default: %%TEMP%%/bors_phasec/scratch-<label>)")
    args = ap.parse_args()
    # Warm needs a seeded profile/work dir; without it the first "warm" run would
    # silently measure a cold start. Force one unrecorded warmup.
    if args.mode == "warm":
        args.warmup = True

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch_root = Path(args.scratch_dir).resolve() if args.scratch_dir else (
        Path(tempfile.gettempdir()) / "bors_phasec" / f"scratch-{args.label}")
    if scratch_root.exists():
        shutil.rmtree(scratch_root, ignore_errors=True)
    scratch_root.mkdir(parents=True, exist_ok=True)
    shared = scratch_root / "_warm" / "work"
    shared_profile = scratch_root / "_warm" / "localappdata"
    results = []
    warm_seed = args.mode == "warm"

    if args.warmup:
        w = Run(0, args, out_dir, scratch_root)
        w.tag = "warmup"
        w.work, w.localappdata = shared, shared_profile
        w.trace_path = out_dir / "warmup-trace.jsonl"
        w.log_path = out_dir / "warmup.log"
        w.probe_out = out_dir / "warmup-probe.json"
        w.probe_log = out_dir / "warmup-probe.log"
        print(f"[{args.label}] warmup ...", flush=True)
        w.start(reuse=warm_seed)
        if not w.wait_cdp(timeout=120.0):
            print("  WARN cdp did not come up", flush=True)
        w.wait_app_http()
        rc = w.probe(args.symbol, args.timeout)
        sh = w.stop()
        print(f"  warmup probe_rc={rc} shutdown={sh['mode']}", flush=True)
        if not args.keep_work:
            pass

    for i in range(1, args.runs + 1):
        r = Run(i, args, out_dir, scratch_root)
        reuse = args.mode == "warm"
        if reuse:
            r.work, r.localappdata = shared, shared_profile
        print(f"[{args.label}] run {i}/{args.runs} ({args.mode}) ...", flush=True)
        r.start(reuse=reuse)
        cdp_ok = r.wait_cdp(timeout=120.0)
        http_ok_ = r.wait_app_http()
        if not cdp_ok:
            print("  ERROR cdp timeout", flush=True)
            rc = -1
            probe = None
        else:
            try:
                rc = r.probe(args.symbol, args.timeout)
            except subprocess.TimeoutExpired:
                rc = -2
                print("  ERROR probe timeout", flush=True)
        sh = r.stop()
        res = r.collect(rc, sh)
        res["cdp_ok"] = cdp_ok
        res["app_http_ok"] = http_ok_
        results.append(res)
        print(f"  ok={res['ok']} board={res['stages_rel_ms'].get('market_rows_visible')}ms "
              f"chart={res['stages_rel_ms'].get('technical_ready')}ms "
              f"fund={res['stages_rel_ms'].get('fundamental_ready')}ms "
              f"peakRSS={res['peak_rss_mb']}MB shutdown={sh['mode']}", flush=True)
        if args.mode in ("cold", "cold-data") and not args.keep_work:
            shutil.rmtree(r.work, ignore_errors=True)
            shutil.rmtree(r.localappdata, ignore_errors=True)

    stage_names = [
        "entry_import", "streams_ready", "serve_start", "boot_server_ready",
        "boot_page_served", "boot_status_poll", "boot_status_ready_seen",
        "window_request", "preflight_start", "db_prepared",
        "library_import_begin", "library_import_end", "native_import_begin",
        "native_import_end", "preflight_end", "uvicorn_spawn", "api_startup_begin", "api_startup_end", "http_ready",
        "app_http_ready", "cdp_available", "native_window_found", "boot_ready", "window_start",
        "app_document_ready", "login_ready", "login_submit", "master_ready",
        "market_rows_visible", "technical_ready", "fundamental_ready",
        "market_publish", "screener_warm_done", "screener_low_priority",
        "screener_wait_board", "screener_wait_board_done", "mstat_warm_done",
        "candle_projection_done",
    ]
    summary = {
        "harness": "phase_c_startup/1",
        "label": args.label,
        "mode": args.mode,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "host": {
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "cpu_logical": psutil.cpu_count(logical=True),
            "cpu_physical": psutil.cpu_count(logical=False),
            "total_ram_gb": round(psutil.virtual_memory().total / 1073741824, 1),
        },
        "definitions": {
            "cold": "fresh WORK_DIR copy and fresh WebView2 profile every run",
            "warm": "one seeded WORK_DIR + profile reused (unrecorded warmup)",
            "cold_data": "WORK_DIR contains only market.db.lzma; first-run extraction",
            "os_file_cache": "not purged; cold/warm differ in app/profile state only",
            "network_loops": "BORS_NO_FETCH_LOOPS=1, BORS_CODAL_AUTO=0; chart still fetched on demand",
            "window_throttling": "harness sets the native window foreground and disables Chromium occlusion/timer throttling",
            "browser_fallback": "BORS_NATIVE_WINDOW=0 + BORS_BROWSER_DEBUG_PORT; app opens its supported Edge app window",
            "time_origin": "process launch (Popen) in the harness",
            "board_ready": "first [data-testid=tape-row] rendered (virtualized)",
            "chart_ready": "canvas in chart-area AND FTS freshness line with آخرین کندل",
            "fundamental_ready": "fts-strategy-summary or holding-pnav-panel visible",
            "p95": "computed only when n>=20; null otherwise",
        },
        "template": str(Path(args.template).resolve()),
        "scratch_root": str(scratch_root),
        "runs": results,
        "aggregate": aggregate(results, stage_names),
        "browser_fallback": bool(args.browser_fallback),
        "failures": [r["run"] for r in results if not r["ok"]],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{args.label}] wrote {out_dir / 'summary.json'}", flush=True)
    sys.exit(0 if not summary["failures"] else 1)


if __name__ == "__main__":
    main()
