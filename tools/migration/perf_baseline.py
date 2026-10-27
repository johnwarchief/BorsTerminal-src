#!/usr/bin/env python
"""A — installed-app performance baseline for the desktop migration.

Measures the frozen v1.0.95 build on an isolated portable copy:
  * cold start -> port -> first API -> first usable market data
  * warm start (same data, second launch)
  * RSS / CPU of the whole app process tree (idle, boot, UI work)
  * install size (binaries vs copied DBs)
  * UI route timings at 1366x768 / 1920x1080 / 2560x1440 via tools/migration/fe_probe.js
  * data freshness and offline-safety evidence (no public connections)

Safety rules baked in:
  * refuses to launch during Tehran market hours (08:50-12:35) unless --force
  * copies DBs with sqlite3 backup (source is opened read-only, never written)
  * portable mode + BORS_PORTABLE + BORS_NO_FETCH_LOOPS + BORS_CODAL_OFFLINE
  * LOCALAPPDATA is redirected so the owner's WebView2/Edge profile is untouched
  * stops only the process tree it started

Usage:
  python tools/migration/perf_baseline.py --prepare-only
  python tools/migration/perf_baseline.py --label installed-1.0.95
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sqlite3
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import psutil
except ImportError:  # pragma: no cover - the machine has psutil; fail loudly if not
    print("[ERR] psutil is required: python -m pip install psutil", file=sys.stderr)
    raise

REPO = Path(__file__).resolve().parents[2]
SRC_APP = Path(r"C:\Users\PCMOD\Desktop\v1080_verify\app")
ROOT = Path(os.environ.get("BORS_PERF_ROOT", r"C:\Users\PCMOD\AppData\Local\Temp\bors_perf_baseline_2026-10-27"))
APP = ROOT / "app"
DATA = APP / "data"
LOCALAPPDATA = ROOT / "localappdata"
OUT_JSON = ROOT / "baseline.json"
TOOL_UI = REPO / "tools" / "migration" / "fe_probe.js"
EXE = "BorsTerminal_Ultimate.exe"

IGNORE = shutil.ignore_patterns(
    "data", "logs", "*.log", "*.db", "*.db-wal", "*.db-shm", "*.db.baseline", "*.part-*"
)

# Resolve the market-data hosts once. PTR lookup is unreliable here (it returned
# no name for tsetmc.com in the 2026-10-27 run), so match the numeric IPs too.
MARKET_IPS = {"46.102.143.218", "94.182.113.115"}  # tsetmc.com, cdn.tsetmc.com
for _h in ("tsetmc.com", "www.tsetmc.com", "cdn.tsetmc.com", "codal.ir", "www.codal.ir"):
    try:
        MARKET_IPS.update(socket.gethostbyname_ex(_h)[2])
    except OSError:
        pass


def now_tehran() -> datetime:
    return datetime.now(ZoneInfo("Asia/Tehran"))


def in_market_hours(now: datetime | None = None) -> bool:
    now = now or now_tehran()
    minutes = now.hour * 60 + now.minute
    return 8 * 60 + 50 <= minutes <= 12 * 60 + 35


def free_port(start: int = 8140) -> int:
    for port in range(start, start + 60):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("no free loopback port found")


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0
    for f in path.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass
    return round(total / 1e6, 1)


def backup_db(src: Path, dst: Path) -> None:
    if dst.exists():
        dst.unlink()
    con = sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)
    try:
        out = sqlite3.connect(str(dst))
        try:
            con.backup(out)
        finally:
            out.close()
    finally:
        con.close()


def prepare(source: Path, reuse: bool) -> dict:
    if not (source / EXE).is_file():
        raise SystemExit(f"[ERR] installed EXE not found: {source / EXE}")
    if APP.exists() and not reuse:
        shutil.rmtree(APP)
    if LOCALAPPDATA.exists() and not reuse:
        shutil.rmtree(LOCALAPPDATA, ignore_errors=True)
    APP.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, APP, ignore=IGNORE, dirs_exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    LOCALAPPDATA.mkdir(parents=True, exist_ok=True)

    # The portable marker is explicit; without it the frozen app binds 8001.
    (APP / "bors_portable.flag").write_text("", encoding="ascii")

    for name in ("market.db", "user.db"):
        src = source / name
        if src.is_file():
            backup_db(src, DATA / name)

    version = ""
    vf = source / "Version.txt"
    if vf.is_file():
        version = vf.read_text(encoding="utf-8", errors="replace").strip()

    return {
        "source": str(source),
        "copy": str(APP),
        "version_txt": version,
        "source_total_mb": dir_size_mb(source),
        "copy_binaries_mb": round(dir_size_mb(APP) - dir_size_mb(DATA), 1),
        "market_db_mb": round((DATA / "market.db").stat().st_size / 1e6, 1) if (DATA / "market.db").exists() else 0,
        "user_db_mb": round((DATA / "user.db").stat().st_size / 1e6, 1) if (DATA / "user.db").exists() else 0,
    }


class Sampler(threading.Thread):
    def __init__(self, pid: int, interval: float = 0.5):
        super().__init__(daemon=True)
        self.pid = pid
        self.interval = interval
        self.stop_evt = threading.Event()
        self.samples: list[dict] = []
        self.phase = "boot"
        self.remote: list[dict] = []
        self.market_hit: list[dict] = []
        self._host_cache: dict[str, str] = {}
        self._proc_cpu: dict[int, float] = {}
        self.last_cpu: float | None = None
        self.last_wall: float | None = None

    def _hostname(self, ip: str) -> str:
        if ip not in self._host_cache:
            try:
                self._host_cache[ip] = socket.gethostbyaddr(ip)[0]
            except OSError:
                self._host_cache[ip] = ""
        return self._host_cache[ip]

    def _tree(self) -> list[psutil.Process]:
        try:
            root = psutil.Process(self.pid)
            return [root] + root.children(recursive=True)
        except psutil.Error:
            return []

    def run(self) -> None:
        while not self.stop_evt.is_set():
            procs = self._tree()
            if not procs:
                break
            rss = 0
            cpu = 0.0
            ct_map: dict[int, tuple[str, float]] = {}
            for p in procs:
                try:
                    rss += p.memory_info().rss
                    times = p.cpu_times()
                    ct = times.user + times.system
                    cpu += ct
                    ct_map[p.pid] = (p.name(), ct)
                    for c in p.net_connections(kind="inet"):
                        ip = c.raddr.ip if c.raddr else ""
                        if ip and ip not in ("127.0.0.1", "::1") and not ip.startswith("::ffff:127."):
                            host = self._hostname(ip)
                            row = {
                                "pid": p.pid,
                                "name": p.name(),
                                "ip": ip,
                                "port": c.raddr.port,
                                "host": host,
                            }
                            if not any(r["pid"] == row["pid"] and r["ip"] == ip and r["port"] == row["port"]
                                       for r in self.remote):
                                self.remote.append(row)
                            if ip in MARKET_IPS or "tsetmc" in host.lower() or "codal" in host.lower():
                                self.market_hit.append(row)
                except (psutil.Error, OSError):
                    pass
            wall = time.perf_counter()
            cores = None
            top_cpu = []
            if self.last_cpu is not None and self.last_wall is not None and wall > self.last_wall:
                dw = wall - self.last_wall
                cores = round((cpu - self.last_cpu) / dw, 2)
                for pid, (name, ct) in ct_map.items():
                    prev = self._proc_cpu.get(pid)
                    if prev is not None:
                        top_cpu.append({"name": name, "cores": round(max(0.0, ct - prev) / dw, 2)})
                top_cpu.sort(key=lambda x: x["cores"], reverse=True)
                top_cpu = top_cpu[:3]
            self._proc_cpu.update({pid: ct for pid, (_, ct) in ct_map.items()})
            self.last_cpu, self.last_wall = cpu, wall
            self.samples.append({
                "t": round(time.perf_counter() - T0, 2),
                "phase": self.phase,
                "rss_mb": round(rss / 1e6, 1),
                "cores": cores,
                "top_cpu": top_cpu,
                "procs": len(procs),
            })
            self.stop_evt.wait(self.interval)


def phase_summary(samples: list[dict]) -> dict:
    out = {}
    for phase in sorted({s["phase"] for s in samples}):
        rows = [s for s in samples if s["phase"] == phase]
        rss = [s["rss_mb"] for s in rows]
        cores = [s["cores"] for s in rows if s["cores"] is not None]
        if not rss:
            continue
        out[phase] = {
            "n": len(rows),
            "rss_mb_median": round(statistics.median(rss), 1),
            "rss_mb_max": round(max(rss), 1),
            "cores_median": round(statistics.median(cores), 2) if cores else None,
            "cores_max": round(max(cores), 2) if cores else None,
        }
    return out


def http_probe(url: str, timeout: float = 180.0) -> dict:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read()
            return {
                "url": url,
                "status": resp.status,
                "ms": round((time.perf_counter() - started) * 1000),
                "bytes": len(body),
            }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "url": url,
            "status": None,
            "ms": round((time.perf_counter() - started) * 1000),
            "error": str(exc)[:300],
        }


T0 = time.perf_counter()


def launch_and_boot(port: int, label: str, sampler_holder: list, boot_seconds: float = 240.0) -> dict:
    env = os.environ.copy()
    env.update({
        "BORS_PORTABLE": "1",
        "BORS_PORT": str(port),
        "BORS_NO_FETCH_LOOPS": "1",
        "BORS_CODAL_OFFLINE": "1",
        "BORS_CODAL_AUTO": "0",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "LOCALAPPDATA": str(LOCALAPPDATA),
        # Hard network block for the app's own HTTP clients (requests/urllib honor
        # these). Loopback stays direct. A dead proxy fails external calls fast and
        # makes the benchmark reproducible; the 2026-10-27 run showed that
        # BORS_NO_FETCH_LOOPS alone still let /api/market fetch tsetmc.com.
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
        "NO_PROXY": "127.0.0.1,localhost,::1",
        "no_proxy": "127.0.0.1,localhost,::1",
        # Keep WebView2 from doing background component/telemetry traffic; the
        # only network we abort on is a TSETMC/Codal connection.
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": (
            "--disable-background-networking --disable-component-update --disable-sync "
            "--no-first-run --disable-features=Translate,OptimizationHints,MediaRouter"
        ),
    })
    log_path = ROOT / f"{label}.log"
    log = open(log_path, "wb")
    proc = subprocess.Popen(
        [str(APP / EXE)],
        cwd=str(APP),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    sampler = Sampler(proc.pid)
    sampler.start()
    sampler_holder.append(sampler)

    t0 = time.perf_counter()
    result = {"pid": proc.pid, "log": str(log_path), "port": port}
    result["port_ms"] = None
    result["version"] = None
    result["market"] = None
    result["ready_ms"] = None
    try:
        while time.perf_counter() - t0 < boot_seconds:
            if proc.poll() is not None:
                result["exited"] = proc.returncode
                break
            if sampler.market_hit:
                result["remote_connections"] = list(sampler.remote)
                result["market_connections"] = list(sampler.market_hit)
                result["blocked_market"] = True
                break
            if port_open(port):
                result["port_ms"] = round((time.perf_counter() - t0) * 1000)
                break
            time.sleep(0.05)
        if result.get("blocked_market"):
            return {"proc": proc, "result": result}
        if result["port_ms"] is not None:
            result["version"] = http_probe(f"http://127.0.0.1:{port}/api/update/version", timeout=60)
            result["market"] = http_probe(f"http://127.0.0.1:{port}/api/market", timeout=180)
            if result["market"].get("status") == 200:
                result["ready_ms"] = round((time.perf_counter() - t0) * 1000)
            result["sync_state"] = http_probe(f"http://127.0.0.1:{port}/api/market/sync-state", timeout=60)
            result["live_stats"] = http_probe(f"http://127.0.0.1:{port}/api/live-stats", timeout=60)
        return {"proc": proc, "result": result}
    except Exception:
        stop_tree(proc)
        raise
    finally:
        log.close()


def stop_tree(proc: subprocess.Popen) -> dict:
    out = {"graceful": False, "killed": []}
    try:
        root = psutil.Process(proc.pid)
        tree = root.children(recursive=True) + [root]
    except psutil.Error:
        out["already_gone"] = True
        return out
    # WM_CLOSE first (taskkill without /F); only the PID we launched.
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid)], capture_output=True, timeout=15)
        proc.wait(timeout=12)
        out["graceful"] = True
    except (subprocess.TimeoutExpired, OSError):
        pass
    except subprocess.CalledProcessError:
        pass
    for p in tree:
        try:
            if p.is_running():
                p.kill()
                out["killed"].append(p.pid)
        except psutil.Error:
            pass
    time.sleep(0.5)
    return out


def run_ui(port: int, viewports: list[str], runs: int, label: str) -> dict:
    node = shutil.which("node")
    if not node:
        return {"error": "node not found on PATH"}
    if not TOOL_UI.is_file():
        return {"error": f"missing {TOOL_UI}"}
    out = {}
    for vp in viewports:
        name = f"MIG_BASE_{label}_{vp}.json"
        log_path = ROOT / f"ui_{vp}.log"
        env = os.environ.copy()
        env.update({
            "BORS_UI_BASE": f"http://127.0.0.1:{port}",
            "BORS_LABEL": f"{label}-{vp}",
            "BORS_VIEWPORT": vp,
            "BORS_RUNS": str(runs),
            "BORS_DEADLINE_MS": os.environ.get("BORS_UI_DEADLINE_MS", "240000"),
        })
        with open(log_path, "wb") as log:
            try:
                cp = subprocess.run(
                    [node, str(TOOL_UI), "--out", name],
                    cwd=str(REPO), env=env, stdout=log, stderr=subprocess.STDOUT,
                    timeout=2400,
                )
                rc = cp.returncode
            except subprocess.TimeoutExpired:
                rc = "timeout"
        out[vp] = {
            "exit": rc,
            "json": str(REPO / "_audit" / "perf" / name),
            "log": str(log_path),
        }
    return out


def read_freshness() -> dict:
    db = DATA / "market.db"
    out = {"market_db_mtime": None, "max_price_date": None, "sync_json_mtime": None}
    if db.exists():
        out["market_db_mtime"] = datetime.fromtimestamp(db.stat().st_mtime).isoformat(timespec="seconds")
    sync = APP / "market_sync.json"
    if sync.exists():
        out["sync_json_mtime"] = datetime.fromtimestamp(sync.stat().st_mtime).isoformat(timespec="seconds")
    if db.exists():
        try:
            con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
            try:
                row = con.execute("select max(date) from price_history").fetchone()
                out["max_price_date"] = row[0] if row else None
            finally:
                con.close()
        except sqlite3.Error as exc:
            out["max_price_date"] = f"error: {exc}"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(SRC_APP))
    ap.add_argument("--label", default="installed-1.0.95")
    ap.add_argument("--viewports", default="1366x768,1920x1080,2560x1440")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--prepare-only", action="store_true")
    ap.add_argument("--skip-ui", action="store_true")
    ap.add_argument("--reuse-copy", action="store_true")
    ap.add_argument("--force", action="store_true", help="allow launching during market hours")
    ap.add_argument("--out", default=str(OUT_JSON))
    args = ap.parse_args()

    if in_market_hours() and not args.force:
        print("[REFUSED] Tehran market hours (08:50-12:35). Run after the close or use --force.")
        return 3

    ROOT.mkdir(parents=True, exist_ok=True)
    install = prepare(Path(args.source), args.reuse_copy)
    print(f"[OK] copy ready: {APP} (binaries {install['copy_binaries_mb']} MB, "
          f"market.db {install['market_db_mb']} MB)")
    if args.prepare_only:
        print(json.dumps(install, ensure_ascii=False, indent=2))
        return 0

    port = free_port(8140)
    report: dict = {
        "meta": {
            "label": args.label,
            "started_at": now_tehran().isoformat(timespec="seconds"),
            "source_app": args.source,
            "copy": str(APP),
            "port": port,
            "viewports": args.viewports.split(","),
            "runs": args.runs,
            "force": args.force,
        },
        "install": install,
        "cold": {},
        "warm": {},
        "ui": {},
        "freshness": {},
        "safety": {},
        "process": {},
    }

    holders: list[Sampler] = []
    proc = None
    try:
        launched = launch_and_boot(port, f"{args.label}-cold", holders)
        proc = launched["proc"]
        report["cold"] = launched["result"]
        sampler = holders[-1]
        ready = bool(report["cold"].get("ready_ms")) and not report["cold"].get("blocked_market")
        if ready:
            sampler.phase = "idle"
            time.sleep(20)
            sampler.phase = "ui"
            print(f"[OK] boot: port={report['cold']['port_ms']} ms, ready={report['cold']['ready_ms']} ms")
            if not args.skip_ui:
                report["ui"] = run_ui(port, args.viewports.split(","), args.runs, args.label)
        else:
            print(f"[WARN] cold launch not ready: {json.dumps(report['cold'], ensure_ascii=False)[:400]}")
        sampler.phase = "stop"
        stop_tree(proc)
        proc = None
        log_path = Path(report["cold"]["log"])
        log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        report["safety"] = {
            "remote_connections": list(sampler.remote),
            "market_connections": list(sampler.market_hit),
            # The windowed frozen build usually writes no stdout, so an absent
            # line here is NOT evidence that the flag was ignored.
            "log_bytes": len(log_text),
            "flag_in_log": "BORS_NO_FETCH_LOOPS=1" in log_text,
        }
        report["process"] = phase_summary(sampler.samples)
        report["raw_samples"] = {"cold": sampler.samples}

        # Warm start: same prepared data, second launch.
        if ready:
            for _ in range(50):
                if not port_open(port):
                    break
                time.sleep(0.2)
            warm_holders: list[Sampler] = []
            warm = launch_and_boot(port, f"{args.label}-warm", warm_holders)
            report["warm"] = warm["result"]
            warm_sampler = warm_holders[-1]
            warm_sampler.phase = "warm_idle"
            time.sleep(10)
            stop_tree(warm["proc"])
            warm_sampler.stop_evt.set()
            report["process"].update({
                f"warm_{k}": v for k, v in phase_summary(warm_sampler.samples).items()
            })
            report["safety"]["warm_remote_connections"] = list(warm_sampler.remote)
            report["safety"]["warm_market_connections"] = list(warm_sampler.market_hit)
            report["raw_samples"]["warm"] = warm_sampler.samples
        else:
            report["warm"] = {"skipped": "cold launch was not ready"}
        report["freshness"] = read_freshness()
    finally:
        if proc is not None:
            stop_tree(proc)
        for s in holders:
            s.stop_evt.set()

    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] wrote {args.out}")
    if report["safety"].get("market_connections"):
        print("[WARN] a TSETMC/Codal connection was observed; inspect safety.market_connections")
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
