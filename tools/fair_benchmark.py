#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/fair_benchmark.py
سنجش و مقایسه عملکرد عادلانه و بی‌طرفانه بین بک‌اند پایتون و بک‌اند Go در شرایط کاملاً یکسان:
- سخت‌افزار یکسان (همین ماشین)
- دیتابیس یکسان (market.db موجود در ریشه)
- حالت اجرای یکسان (read-only و بدون حلقه‌های پس‌زمینه / no-loops)
- سنجش کاملاً متقارن آمادگی پروسه (Process Readiness) روی اندپوینت یکسان /healthz
- سنجش تاخیر اولین درخواست سرد (Cold Start Request) روی /api/market
- اندپوینت‌های ۴گانه معادل:
    1. /api/market
    2. /api/chart-db/فولاد
    3. /api/fundamental/فولاد
    4. /api/screener
- ۳۰ تکرار پس از ۱ درخواست گرم‌کردن، به همراه p50، p95، میانگین، کمینه، بیشینه
- حافظه RAM در حالت بیکار (Idle RSS) و زیر بار (Load RSS)
"""

import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError, OSError):
    pass

try:
    import psutil
except ImportError:
    psutil = None


def get_process_memory_mb(pid: int) -> float:
    if psutil:
        try:
            p = psutil.Process(pid)
            mem = p.memory_info().rss
            for c in p.children(recursive=True):
                try:
                    mem += c.memory_info().rss
                except Exception:
                    pass
            return round(mem / (1024 * 1024), 2)
        except Exception:
            pass
    try:
        cmd = f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue).WorkingSet64"
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command", cmd]).decode().strip()
        if out:
            return round(int(out) / (1024 * 1024), 2)
    except Exception:
        pass
    return 0.0


def wait_for_ready(url: str, timeout: float = 25.0) -> float:
    start = time.perf_counter()
    deadline = start + timeout
    while time.perf_counter() < deadline:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FairBenchmark/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    return (time.perf_counter() - start) * 1000.0
        except Exception:
            time.sleep(0.02)
    raise TimeoutError(f"Server at {url} did not become ready within {timeout}s")


def measure_single_request(url: str, timeout: float = 30.0) -> tuple[float, int, int]:
    req = urllib.request.Request(url, headers={"User-Agent": "FairBenchmark/1.0"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return latency_ms, resp.status, len(data)


def benchmark_endpoint(url: str, count: int = 30, warmup: bool = True) -> dict:
    # ۱ درخواست گرم‌کردن برای پر شدن کش پلن کوئری و استخر اتصال
    if warmup:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FairBenchmark/1.0"})
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                _ = resp.read()
        except Exception:
            pass
        time.sleep(0.05)

    latencies = []
    successes = 0
    payload_len = 0
    for _ in range(count):
        req = urllib.request.Request(url, headers={"User-Agent": "FairBenchmark/1.0"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                data = resp.read()
                latencies.append((time.perf_counter() - t0) * 1000.0)
                successes += 1
                payload_len = len(data)
        except Exception:
            pass
        time.sleep(0.01)

    if not latencies:
        return {"count": count, "success": 0, "p50_ms": None, "p95_ms": None, "avg_ms": None}

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    avg = sum(latencies) / len(latencies)

    return {
        "count": count,
        "success": successes,
        "bytes": payload_len,
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "avg_ms": round(avg, 2),
        "min_ms": round(latencies[0], 2),
        "max_ms": round(latencies[-1], 2),
    }


def collect_environment_metadata() -> dict:
    total_ram_gb = 0.0
    if psutil:
        try:
            total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
        except Exception:
            pass

    db_path = "market.db"
    db_size_mb = 0.0
    db_sha256 = ""
    if os.path.exists(db_path):
        db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2)
        try:
            h = hashlib.sha256()
            with open(db_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    h.update(chunk)
            db_sha256 = h.hexdigest()
        except Exception:
            pass

    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "cpu_cores": os.cpu_count(),
        "total_ram_gb": total_ram_gb,
        "python_version": sys.version.split()[0],
        "database": {
            "path": db_path,
            "size_mb": db_size_mb,
            "sha256": db_sha256,
        },
        "benchmark_timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "repetitions_per_endpoint": 30,
    }


def run_benchmark():
    meta = collect_environment_metadata()
    results = {
        "environment": meta,
        "go": {},
        "python": {},
    }

    foolad_enc = urllib.parse.quote("فولاد")

    test_routes = [
        ("market", "/api/market"),
        ("chart_db_foolad", f"/api/chart-db/{foolad_enc}"),
        ("fundamental_foolad", f"/api/fundamental/{foolad_enc}"),
        ("screener", "/api/screener"),
    ]

    # 1. سنجش بک‌اند Go
    print("=== [1/2] در حال سنجش بک‌اند Go (borsd) ===")
    go_exe = os.path.abspath("backend-go/borsd.exe")
    if not os.path.exists(go_exe):
        print("کامپایل borsd.exe...")
        subprocess.check_call(["go", "build", "-o", "borsd.exe", "./cmd/borsd"], cwd="backend-go")

    go_port = 8082
    go_proc = subprocess.Popen(
        [go_exe, "-port", str(go_port), "-db-dir", ".", "-read-only", "-no-loops"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # متدولوژی متقارن: پروب /healthz برای اندازه‌گیری زمان باز شدن پورت و آمادگی پردازه
        go_readiness = wait_for_ready(f"http://127.0.0.1:{go_port}/healthz")
        time.sleep(0.5)
        go_idle_mem = get_process_memory_mb(go_proc.pid)

        # اولین درخواست سرد روی /api/market
        cold_lat, cold_st, cold_bytes = measure_single_request(f"http://127.0.0.1:{go_port}/api/market")

        go_bench = {
            "process_readiness_ms": round(go_readiness, 2),
            "cold_start_request_ms": round(cold_lat, 2),
            "idle_rss_mb": go_idle_mem,
            "endpoints": {},
        }

        for name, route in test_routes:
            url = f"http://127.0.0.1:{go_port}{route}"
            print(f"  سنجش Go: {name}...")
            go_bench["endpoints"][name] = benchmark_endpoint(url, count=30, warmup=True)

        go_bench["load_rss_mb"] = get_process_memory_mb(go_proc.pid)
        results["go"] = go_bench
    finally:
        go_proc.terminate()
        try:
            go_proc.wait(timeout=3)
        except Exception:
            go_proc.kill()

    time.sleep(1.0)

    # 2. سنجش بک‌اند Python
    print("\n=== [2/2] در حال سنجش بک‌اند Python (uvicorn app:app) ===")
    py_port = 8081
    py_env = dict(os.environ, BORS_NO_FETCH_LOOPS="1", PYTHONIOENCODING="utf-8")
    py_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--port", str(py_port), "--host", "127.0.0.1"],
        env=py_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # متدولوژی متقارن: پروب /healthz برای اندازه‌گیری زمان باز شدن پورت و آمادگی پردازه
        py_readiness = wait_for_ready(f"http://127.0.0.1:{py_port}/healthz")
        time.sleep(0.5)
        py_idle_mem = get_process_memory_mb(py_proc.pid)

        # اولین درخواست سرد روی /api/market
        cold_lat, cold_st, cold_bytes = measure_single_request(f"http://127.0.0.1:{py_port}/api/market")

        py_bench = {
            "process_readiness_ms": round(py_readiness, 2),
            "cold_start_request_ms": round(cold_lat, 2),
            "idle_rss_mb": py_idle_mem,
            "endpoints": {},
        }

        for name, route in test_routes:
            url = f"http://127.0.0.1:{py_port}{route}"
            print(f"  سنجش Python: {name}...")
            py_bench["endpoints"][name] = benchmark_endpoint(url, count=30, warmup=True)

        py_bench["load_rss_mb"] = get_process_memory_mb(py_proc.pid)
        results["python"] = py_bench
    finally:
        py_proc.terminate()
        try:
            py_proc.wait(timeout=3)
        except Exception:
            py_proc.kill()

    # خروجی JSON
    out_path = "tools/benchmark_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("جدول مقایسه عملکرد عادلانه و علمی (Go در برابر Python)")
    print("=" * 80)
    print(f"{'شاخص / اندپوینت':<35} | {'Go (borsd)':<18} | {'Python (FastAPI)':<18} | {'نسبت برتری':<14}")
    print("-" * 92)

    rd_go = results["go"]["process_readiness_ms"]
    rd_py = results["python"]["process_readiness_ms"]
    rd_ratio = f"{rd_py / max(rd_go, 0.001):.1f}x سریع‌تر" if rd_go > 0 else "-"
    print(f"{'آمادگی پروسه (Process Readiness)':<35} | {rd_go:>14} ms | {rd_py:>14} ms | {rd_ratio:<14}")

    cs_go = results["go"]["cold_start_request_ms"]
    cs_py = results["python"]["cold_start_request_ms"]
    cs_ratio = f"{cs_py / max(cs_go, 0.001):.1f}x سریع‌تر" if cs_go > 0 else "-"
    print(f"{'اولین درخواست سرد (/api/market)':<35} | {cs_go:>14} ms | {cs_py:>14} ms | {cs_ratio:<14}")

    idle_go = results["go"]["idle_rss_mb"]
    idle_py = results["python"]["idle_rss_mb"]
    idle_ratio = f"{idle_py / max(idle_go, 0.001):.1f}x سبک‌تر" if idle_go > 0 else "-"
    print(f"{'مصرف رم بیکار (Idle RSS)':<35} | {idle_go:>14} MB | {idle_py:>14} MB | {idle_ratio:<14}")

    load_go = results["go"]["load_rss_mb"]
    load_py = results["python"]["load_rss_mb"]
    load_ratio = f"{load_py / max(load_go, 0.001):.1f}x سبک‌تر" if load_go > 0 else "-"
    print(f"{'مصرف رم زیر بار (Load RSS)':<35} | {load_go:>14} MB | {load_py:>14} MB | {load_ratio:<14}")

    print("-" * 92)
    for name, _ in test_routes:
        g = results["go"]["endpoints"][name]
        p = results["python"]["endpoints"][name]
        if g["p50_ms"] is not None and p["p50_ms"] is not None:
            r50 = f"{p['p50_ms'] / max(g['p50_ms'], 0.001):.1f}x سریع‌تر"
            print(f"{name + ' (p50)':<35} | {g['p50_ms']:>14} ms | {p['p50_ms']:>14} ms | {r50:<14}")
            r95 = f"{p['p95_ms'] / max(g['p95_ms'], 0.001):.1f}x سریع‌تر"
            print(f"{name + ' (p95)':<35} | {g['p95_ms']:>14} ms | {p['p95_ms']:>14} ms | {r95:<14}")

    print("=" * 80)
    print(f"گزارش ساختاریافته در {out_path} ذخیره شد.")


if __name__ == "__main__":
    run_benchmark()
