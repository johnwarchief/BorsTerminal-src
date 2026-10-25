#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Installed-package close/lifecycle test.

Launches the packaged shell with an isolated work/profile, waits for the
sidecar and the app window, closes the window, then watches every shell,
sidecar and WebView2 process (without killing them) until it exits or a grace
period expires. This separates a real orphan from normal WebView2 teardown,
which takes longer than the one-second check used by the phase-D harness.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase_d_tinyjs as H  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def prepare(base: Path, run_i: int) -> tuple[Path, Path, Path]:
    run_dir = base / "runs" / f"run-{run_i}"
    work = run_dir / "work"
    profile = run_dir / "profile"
    work.mkdir(parents=True, exist_ok=True)
    profile.mkdir(parents=True, exist_ok=True)
    return work, profile, run_dir


def build_env(work: Path, profile: Path, run_dir: Path) -> dict:
    env = {
        **os.environ,
        "BORS_WORK_DIR": str(work),
        "BORS_DB": str(work / "market.db"),
        "BORS_PORT": "0",
        "BORS_REUSE_SERVER": "0",
        "BORS_NO_FETCH_LOOPS": "1",
        "BORS_CODAL_AUTO": "0",
        "BORS_SHOW_CONSOLE": "1",
        "BORS_STARTUP_TRACE": "1",
        "BORS_STARTUP_TRACE_FILE": str(run_dir / "sidecar-trace.jsonl"),
        "BORS_SHELL_TRACE": str(run_dir / "shell-trace.jsonl"),
        "LOCALAPPDATA": str(profile),
        "TINYJS_DEBUG": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    for key in ("BORS_PYTHON", "BORS_HEADLESS_ENTRY", "BORS_SIDECAR_EXE",
                "BORS_PROBE_SCRIPT", "BORS_PROBE_STOP_FILE", "BORS_COLLECTOR_PORT",
                "BORS_D3_CHECKS", "BORS_VISUAL", "BORS_FAIL_TEST"):
        env.pop(key, None)
    return env


def run_once(args, run_i: int) -> dict:
    base = Path(os.environ.get("TEMP", "")) / "bors_m2_close" / args.label
    shutil.rmtree(base / "runs" / f"run-{run_i}", ignore_errors=True)
    work, profile, run_dir = prepare(base, run_i)
    env = build_env(work, profile, run_dir)
    log = open(run_dir / "shell-stdout.log", "wb")
    t0 = time.time()
    launch_ms = t0 * 1000
    p = subprocess.Popen([str(args.exe)], cwd=str(args.exe.parent), env=env,
                         stdin=subprocess.DEVNULL, stdout=log,
                         stderr=subprocess.STDOUT, creationflags=0x08000000)
    result = {"run": run_i, "root_pid": p.pid, "work": str(work),
              "profile": str(profile), "launch_ms": launch_ms, "errors": []}
    print(f"[run {run_i}] launched pid={p.pid}", flush=True)
    window = None
    try:
        deadline = time.time() + args.timeout
        while time.time() < deadline and window is None:
            try:
                root = psutil.Process(p.pid)
                pids = {p.pid} | {c.pid for c in root.children(recursive=True)}
            except psutil.Error:
                pids = set()
            wins = H.app_windows(pids)
            if wins:
                window = wins[0]
                result["window"] = window
                break
            if p.poll() is not None:
                break
            time.sleep(0.2)
        if window is None:
            result["errors"].append("window_not_found")
            raise SystemExit(1)
        trace = H.read_jsonl(run_dir / "shell-trace.jsonl")
        ready = next((r for r in trace if r.get("stage") == "sidecar_ready_line"), None)
        port = (ready or {}).get("port")
        result["sidecar_port"] = port
        result["window_found_s"] = round(time.time() - t0, 1)
        result["ready_s"] = (round(ready.get("t", 0) * 1000 - launch_ms, 1)
                             if ready else None)
        if port:
            security = H.security_checks(int(port))
            result["security"] = security
            result["security_all_ok"] = all(v.get("ok") for v in security.values())
        print(f"[run {run_i}] window={window['title']!r} port={port} "
              f"security={result.get('security_all_ok')} hold={args.hold}s", flush=True)
        hwnd_to_close = window["hwnd"]
        if args.kill_sidecar:
            spawned = next((r for r in reversed(trace)
                            if r.get("stage") == "sidecar_spawned"), None)
            victim = (spawned or {}).get("pid")
            if not victim:
                raise RuntimeError("sidecar pid not found in trace")
            result["sidecar_kill"] = {"pid": victim}
            psutil.Process(victim).kill()
            error = None
            end = time.time() + 60
            while time.time() < end:
                for w in H.enum_windows():
                    if not w["visible"] or w["w"] <= 300:
                        continue
                    title = w["title"].lower()
                    if "startup failed" in title or "backend stopped" in title:
                        error = w
                        break
                if error:
                    break
                time.sleep(0.3)
            result["error_window"] = error
            if error:
                result["error_screenshot"] = H.screenshot(error["hwnd"], run_dir / "error.png")
                hwnd_to_close = error["hwnd"]
            else:
                result["errors"].append("error_window_not_found")
        else:
            time.sleep(args.hold)
        t_close = time.time()
        H.USER32.PostMessageW(hwnd_to_close, H.WM_CLOSE, 0, 0)
        while p.poll() is None and time.time() - t_close < 40:
            time.sleep(0.2)
        result["shell_exit_code"] = p.poll()
        result["shell_exit_s"] = round(time.time() - t_close, 1)
        result["port_open_after_exit"] = H.port_open(int(port)) if port else None
        # Natural teardown: observe, never kill, for the grace period.
        ns = type("A", (), {"exe": args.exe, "installed": True})()
        observed = H.find_survivors(ns, work, profile, p.pid)
        result["survivors_observed"] = observed
        t_obs = time.time()
        remaining = observed
        while remaining and time.time() - t_obs < args.grace:
            time.sleep(0.5)
            remaining = H.find_survivors(ns, work, profile, p.pid)
        result["survivor_natural_exit_s"] = (round(time.time() - t_obs, 1)
                                             if observed and not remaining else None)
        result["survivors_after_grace"] = remaining
        killed = []
        for s in remaining:
            try:
                psutil.Process(s["pid"]).kill()
                killed.append(s["pid"])
            except psutil.Error:
                pass
        time.sleep(1.0)
        result["killed"] = killed
        result["left_after_kill"] = H.find_survivors(ns, work, profile, p.pid)
        result["port_open_final"] = H.port_open(int(port)) if port else None
        result["errors"] = [e for e in result["errors"] if e != "window_not_found"]
        if result["shell_exit_code"] != 0:
            result["errors"].append(f"shell_exit={result['shell_exit_code']}")
        if remaining:
            result["errors"].append(f"survivors_after_{args.grace}s={len(remaining)}")
        print(f"[run {run_i}] exit={result['shell_exit_code']} "
              f"natural={result['survivor_natural_exit_s']}s "
              f"observed={len(observed)} left={len(remaining)}", flush=True)
    finally:
        log.close()
        if p.poll() is None:
            try:
                p.kill()
            except OSError:
                pass
        ns = type("A", (), {"exe": args.exe, "installed": True})()
        for s in H.find_survivors(ns, work, profile, p.pid):
            try:
                psutil.Process(s["pid"]).kill()
            except psutil.Error:
                pass
        result["finished_s"] = round(time.time() - t0, 1)
        (run_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(f"[run {run_i}] result={run_dir / 'result.json'}", flush=True)
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--exe", default=str(H.DEFAULT_EXE))
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--hold", type=float, default=20.0)
    ap.add_argument("--grace", type=float, default=30.0)
    ap.add_argument("--kill-sidecar", action="store_true",
                    help="kill the sidecar after the window opens; expect the shell error window")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    args.exe = Path(args.exe)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runs = []
    for i in range(1, args.runs + 1):
        try:
            runs.append(run_once(args, i))
        except SystemExit:
            break
        except Exception as e:
            runs.append({"run": i, "errors": [str(e)]})
            print(f"[run {i}] error {e}", flush=True)
    summary = {"label": args.label, "exe": str(args.exe), "runs": runs,
               "runs_total": len(runs),
               "all_ok": bool(runs) and all(not r.get("errors") for r in runs)}
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for r in runs:
        rd = Path(os.environ.get("TEMP", "")) / "bors_m2_close" / args.label / "runs" / f"run-{r['run']}"
        for name in ("shell-stdout.log", "shell-trace.jsonl", "sidecar-trace.jsonl",
                     "error.png", "error.screen.png"):
            src = rd / name
            if src.exists():
                shutil.copy2(src, out / f"run-{r['run']}-{name}")
    print("OUT", out, flush=True)
    return 0 if summary["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
