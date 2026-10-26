#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M2 updater acceptance harness.

Drives the packaged shell's real TinyJS update API (tiny.app.update.check /
install) against a loopback manifest, then verifies the installed files, the
relaunched version, security, shutdown and rollback. It never touches the
operational database: the shell gets an isolated BORS_WORK_DIR/BORS_DB.

Modes:
  install   manifest 0.3.1 -> download, swap, relaunch, verify 0.3.1
  checksum  manifest 0.3.2 with a wrong sha256 -> install must refuse and the
            install tree must stay byte-identical
  rollback  manifest 0.3.2 with the real sha256, but a file in the install
            tree is held without FILE_SHARE_DELETE -> the Windows swap must
            fail and roll the tree back byte-identically
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import traceback
from ctypes import wintypes
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase_d_tinyjs as H  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

PROBE = Path(__file__).resolve().parent / "phase_d" / "m2_update_probe.js"
SCRATCH = Path(os.environ.get("TEMP", "")) / "bors_m2_update"

GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
CreateFileW = ctypes.windll.kernel32.CreateFileW
CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
CreateFileW.restype = wintypes.HANDLE
CloseHandle = ctypes.windll.kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_tree(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root)).replace("\\", "/")] = sha256_file(p)
    return out


def tree_pids(pid: int) -> set[int]:
    try:
        root = psutil.Process(pid)
        return {pid} | {c.pid for c in root.children(recursive=True)}
    except psutil.Error:
        return set()


def find_shell(exe: Path, exclude: set[int]) -> psutil.Process | None:
    want = os.path.normcase(str(exe.resolve()))
    for p in psutil.process_iter(["pid", "exe", "create_time"]):
        if p.pid in exclude:
            continue
        try:
            if p.info.get("exe") and os.path.normcase(p.info["exe"]) == want:
                return p
        except psutil.Error:
            pass
    return None


def sidecar_ports(pids: set[int]) -> list[int]:
    ports = set()
    for pid in pids:
        try:
            p = psutil.Process(pid)
            if p.name().lower() != "borsterminalsidecar.exe":
                continue
            for c in p.net_connections(kind="inet"):
                if c.status == psutil.CONN_LISTEN and c.laddr:
                    ports.add(c.laddr.port)
        except psutil.Error:
            pass
    return sorted(ports)


def lock_no_share(path: Path):
    h = CreateFileW(str(path), GENERIC_READ, 0, None, OPEN_EXISTING, 0, None)
    if not h or h == INVALID_HANDLE_VALUE:
        raise OSError(f"CreateFileW failed for {path}: {ctypes.get_last_error()}")
    return h


def lock_works(scratch: Path) -> bool:
    probe = scratch / "lock-probe.txt"
    probe.write_text("probe", encoding="utf-8")
    h = lock_no_share(probe)
    try:
        try:
            probe.rename(scratch / "lock-probe-renamed.txt")
            return False
        except OSError:
            return True
    finally:
        CloseHandle(h)
        for p in (probe, scratch / "lock-probe-renamed.txt"):
            try:
                p.unlink()
            except OSError:
                pass


class Serve(http.server.ThreadingHTTPServer):
    daemon_threads = True


def start_server(directory: Path, port: int, log_path: Path):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(directory), **kw)

        def log_message(self, fmt, *args):
            line = f"{time.strftime('%H:%M:%S')} {self.client_address[0]} {fmt % args}"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

    srv = Serve(("127.0.0.1", port), Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv


def close_window(hwnd: int, pid: int, timeout: float = 40.0) -> dict:
    H.USER32.PostMessageW(hwnd, H.WM_CLOSE, 0, 0)
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if not psutil.Process(pid).is_running():
                break
        except psutil.Error:
            break
        time.sleep(0.2)
    alive = True
    try:
        alive = psutil.Process(pid).is_running()
    except psutil.Error:
        alive = False
    return {"closed": not alive, "alive_after_close": alive,
            "close_ms": round((time.time() - t0) * 1000, 1)}


def collect(run_dir: Path, collector: H.Collector, seen: int, result: dict,
            log: list[dict]) -> tuple[int, list[dict]]:
    msgs, seen = collector.drained(seen)
    for m in msgs:
        log.append(m)
        with open(run_dir / "collector.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
        if m.get("kind") == "m2_update_info":
            result.setdefault("version_events", []).append(
                {"at_ms": m.get("at_ms"), "url": m.get("url"), "info": m.get("info")})
        print(f"[collector] {m.get('kind')} run={m.get('run_id')} "
              f"url={m.get('url')} {json.dumps({k: v for k, v in m.items() if k not in ('kind', 'run_id', 'url', 'at_ms')}, ensure_ascii=False)[:500]}",
              flush=True)
    result["messages"] = len(log)
    return seen, msgs


def cleanup(args, work: Path, profile: Path, root_pid: int, port: int | None) -> dict:
    ns = type("A", (), {"exe": args.exe, "installed": True})()
    observed = H.find_survivors(ns, work, profile, root_pid)
    t0 = time.time()
    remaining = observed
    while remaining and time.time() - t0 < 10.0:
        time.sleep(0.5)
        remaining = H.find_survivors(ns, work, profile, root_pid)
    natural_exit_s = round(time.time() - t0, 1) if observed and not remaining else None
    killed = []
    for s in remaining:
        try:
            psutil.Process(s["pid"]).kill()
            killed.append(s["pid"])
        except psutil.Error:
            pass
    deadline = time.time() + 5
    while time.time() < deadline and H.find_survivors(ns, work, profile, root_pid):
        time.sleep(0.25)
    return {"survivors_observed": observed,
            "natural_exit_s": natural_exit_s,
            "survivors_before": remaining,
            "killed": killed,
            "left": H.find_survivors(ns, work, profile, root_pid),
            "port_open": H.port_open(port) if port else None}


def run(args) -> dict:
    base = SCRATCH / args.mode
    shutil.rmtree(base, ignore_errors=True)
    work = base / "work"
    profile = base / "profile"
    run_dir = base / "run"
    work.mkdir(parents=True, exist_ok=True)
    profile.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    serve = base / "serve"
    shutil.rmtree(serve, ignore_errors=True)
    serve.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    zip_name = manifest["win"]["x86_64"]["url"].rsplit("/", 1)[-1]
    zip_src = Path(args.manifest).parent / zip_name
    if not zip_src.exists():
        raise SystemExit(f"missing update zip: {zip_src}")
    shutil.copy2(zip_src, serve / zip_name)
    (serve / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                         encoding="utf-8")

    before = hash_tree(args.install_dir)
    result = {
        "mode": args.mode,
        "install_dir": str(args.install_dir),
        "exe": str(args.exe),
        "manifest": manifest,
        "manifest_url": f"http://127.0.0.1:{args.port}/manifest.json",
        "install_before": before,
        "install_before_count": len(before),
        "expected_new_exe_sha256": args.expected_new_exe_sha256,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "errors": [],
        "lock": None,
    }
    print(f"[setup] mode={args.mode} install={args.install_dir} files={len(before)} "
          f"manifest={manifest.get('version')} win={manifest['win'].get('version')}", flush=True)

    lock_handle = None
    if args.mode == "rollback":
        lock_target = args.install_dir / args.lock_rel
        if not lock_target.exists():
            raise SystemExit(f"missing lock target: {lock_target}")
        works = lock_works(base)
        result["lock"] = {"path": str(lock_target), "exclusive_open_blocks_rename": works}
        print(f"[lock] {lock_target} blocks rename={works}", flush=True)
        if not works:
            raise SystemExit("could not prove an exclusive handle blocks rename")
        lock_handle = lock_no_share(lock_target)

    srv = start_server(serve, args.port, run_dir / "http.log")
    collector = H.Collector()
    collector.start()
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
        "BORS_PROBE_SCRIPT": str(PROBE),
        "BORS_COLLECTOR_PORT": str(collector.port),
        "LOCALAPPDATA": str(profile),
        "TINYJS_DEBUG": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    for key in ("BORS_PYTHON", "BORS_HEADLESS_ENTRY", "BORS_SIDECAR_EXE",
                "BORS_FAIL_TEST", "BORS_D3_CHECKS", "BORS_VISUAL"):
        env.pop(key, None)

    log = open(run_dir / "shell-stdout.log", "wb")
    t0 = time.time()
    p = subprocess.Popen([str(args.exe)], cwd=str(args.install_dir), env=env,
                         stdin=subprocess.DEVNULL, stdout=log,
                         stderr=subprocess.STDOUT, creationflags=0x08000000)
    result["root_pid"] = p.pid
    result["launched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"[launch] pid={p.pid} cwd={args.install_dir}", flush=True)

    msgs: list[dict] = []
    seen = 0
    original_msgs: list[dict] = []
    new_shell = None
    new_pid = None
    new_window = None
    sidecar_port = None
    security = None
    close_info = None
    original_exit = None

    try:
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            seen, got = collect(run_dir, collector, seen, result, msgs)
            original_msgs.extend([m for m in got if m.get("run_id")])
            if any(m.get("kind") == "m2_update_check" for m in got):
                result["check"] = next(m.get("result") for m in got
                                       if m.get("kind") == "m2_update_check")
            for m in got:
                if m.get("kind") == "m2_update_info":
                    result.setdefault("versions", []).append(m.get("info"))
                if m.get("kind") in ("m2_update_install_begin", "m2_update_install_returned",
                                     "m2_update_install_error", "m2_update_no_update",
                                     "m2_update_probe_error"):
                    result.setdefault("update_events", []).append(m)
            terminal = {"m2_update_install_error", "m2_update_install_returned",
                        "m2_update_no_update", "m2_update_probe_error"}
            if args.mode != "install" and any(
                    m.get("kind") in terminal for m in result.get("update_events") or []):
                time.sleep(1.0)
                result["original_exit_code"] = p.poll()
                break
            if args.mode == "install" and any(
                    m.get("kind") == "m2_update_install_error" for m in got):
                result["install_failed"] = True
                result["original_exit_code"] = p.poll()
                break
            if original_exit is None:
                try:
                    original_exit = p.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    pass
            if original_exit is not None:
                result["original_exit_code"] = original_exit
                if args.mode == "install":
                    new_shell = find_shell(args.exe, {p.pid})
                    if new_shell:
                        new_pid = new_shell.pid
                        break
                else:
                    break
            time.sleep(0.2)

        if args.mode == "install" and not result.get("install_failed"):
            if original_exit is None:
                raise TimeoutError("original instance did not exit")
            if new_pid is None:
                t_end = time.time() + 120
                while time.time() < t_end and new_pid is None:
                    seen, got = collect(run_dir, collector, seen, result, msgs)
                    for m in got:
                        if m.get("kind") == "m2_update_info":
                            result.setdefault("versions", []).append(m.get("info"))
                    new_shell = find_shell(args.exe, {p.pid})
                    if new_shell:
                        new_pid = new_shell.pid
                    time.sleep(0.25)
            if new_pid is None:
                raise TimeoutError("relaunched instance did not appear")
            result["new_pid"] = new_pid
            print(f"[relaunch] new pid={new_pid}", flush=True)
            t_end = time.time() + 180
            while time.time() < t_end:
                seen, got = collect(run_dir, collector, seen, result, msgs)
                for m in got:
                    if m.get("kind") == "m2_update_info":
                        result.setdefault("versions", []).append(m.get("info"))
                pids = tree_pids(new_pid)
                wins = H.app_windows(pids)
                if wins and new_window is None:
                    new_window = wins[0]
                    result["window"] = new_window
                    result["screenshot"] = H.screenshot(new_window["hwnd"],
                                                        run_dir / "relaunched.png")
                    print(f"[relaunch] window {new_window['title']!r} pid={new_window['pid']}", flush=True)
                ports = sidecar_ports(pids)
                if ports:
                    sidecar_port = ports[0]
                if new_window and sidecar_port:
                    break
                time.sleep(0.25)
            if sidecar_port is None:
                trace = H.read_jsonl(run_dir / "shell-trace.jsonl")
                ready = [r for r in trace if r.get("stage") == "sidecar_ready_line"]
                sidecar_port = ready[-1].get("port") if ready else None
            result["sidecar_port"] = sidecar_port
            if sidecar_port:
                security = H.security_checks(int(sidecar_port))
                result["security"] = security
                result["security_all_ok"] = all(v.get("ok") for v in security.values())
            # The relaunched instance runs the same probe. Give it a moment to
            # report its app.info before closing, so version_after is not just
            # the instance that was replaced.
            if new_window:
                info_end = time.time() + 4.0
                while time.time() < info_end:
                    seen, got = collect(run_dir, collector, seen, result, msgs)
                    if any((m.get("info") or {}).get("version") == manifest.get("version")
                           for m in got if m.get("kind") == "m2_update_info"):
                        break
                    time.sleep(0.2)
            if new_window:
                close_info = close_window(new_window["hwnd"], new_pid)
                result["close"] = close_info
        elif args.mode == "install":
            # The updater refused/failed and rolled back; the current instance
            # is still alive. Close it and keep the byte-level evidence.
            wins = H.app_windows(tree_pids(p.pid))
            if wins:
                result["close"] = close_window(wins[0]["hwnd"], p.pid)
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
            result["original_exit_code"] = p.poll()
        else:
            if not result.get("update_events"):
                raise TimeoutError("no updater result")
            alive = p.poll() is None
            result["app_alive_after_refusal"] = alive
            if alive:
                wins = H.app_windows(tree_pids(p.pid))
                if wins:
                    close_info = close_window(wins[0]["hwnd"], p.pid)
                    result["close"] = close_info
    finally:
        log.close()
        if p.poll() is None:
            try:
                p.kill()
            except OSError:
                pass
        if new_pid:
            try:
                psutil.Process(new_pid).kill()
            except psutil.Error:
                pass
        time.sleep(1.0)
        cleanup_info = cleanup(args, work, profile, new_pid or p.pid, sidecar_port)
        result["cleanup"] = cleanup_info
        collector.close()
        srv.shutdown()
        srv.server_close()
        if lock_handle:
            CloseHandle(lock_handle)

    after = hash_tree(args.install_dir)
    result["install_after"] = after
    result["install_after_count"] = len(after)
    changed = sorted(k for k in set(before) | set(after)
                     if before.get(k) != after.get(k))
    result["changed_files"] = changed
    result["changed_count"] = len(changed)
    result["update_old_files"] = sorted(k for k in after if k.endswith(".update-old"))
    result["exe_sha256_after"] = after.get(args.exe.name)
    result["exe_matches_expected"] = (after.get(args.exe.name) == args.expected_new_exe_sha256
                                      if args.expected_new_exe_sha256 else None)
    result["versions"] = result.get("versions") or []
    version_events = result.get("version_events") or []
    relaunched_version = next(
        (e["info"]["version"] for e in reversed(version_events)
         if (e.get("info") or {}).get("version") == manifest.get("version")), None)
    if relaunched_version:
        result["version_after"] = relaunched_version
        result["version_after_source"] = "relaunched app.info"
    elif args.mode == "install" and result.get("exe_matches_expected"):
        # Proves the installed binary came from the tested manifest build even
        # when the relaunched probe did not post its info in time.
        result["version_after"] = manifest.get("version")
        result["version_after_source"] = "exe sha256 matches manifest build"
    elif version_events:
        result["version_after"] = version_events[-1].get("info", {}).get("version")
        result["version_after_source"] = "app.info"
    else:
        result["version_after"] = None
        result["version_after_source"] = None
    result["elapsed_s"] = round(time.time() - t0, 1)
    result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    (run_dir / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(run_dir / "summary.json", out / "summary.json")
    for name in ("shell-stdout.log", "collector.jsonl", "shell-trace.jsonl",
                 "sidecar-trace.jsonl", "http.log"):
        src = run_dir / name
        if src.exists():
            shutil.copy2(src, out / name)
    for name in ("relaunched.png", "relaunched.screen.png"):
        src = run_dir / name
        if src.exists():
            shutil.copy2(src, out / name)
    print("OUT", out, flush=True)
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["install", "checksum", "rollback", "no-update"],
                    required=True)
    ap.add_argument("--install-dir", required=True)
    ap.add_argument("--exe", default="")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--port", type=int, default=8123)
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--expected-new-exe-sha256", default="")
    ap.add_argument("--lock-rel", default="resources/sidecar/market.db.baseline")
    args = ap.parse_args()
    args.install_dir = Path(args.install_dir)
    args.exe = Path(args.exe) if args.exe else args.install_dir / "BorsTerminalM2TinyJS.exe"
    if not args.exe.exists():
        raise SystemExit(f"missing shell exe: {args.exe}")
    result = run(args)
    print(json.dumps({k: result.get(k) for k in
                      ("mode", "check", "update_events", "original_exit_code",
                       "version_after", "exe_matches_expected", "changed_count",
                       "update_old_files", "security_all_ok", "close", "cleanup")},
                     ensure_ascii=False, indent=1, default=str), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
