#!/usr/bin/env python3
"""
tools/fair_benchmark.py
سنجش و مقایسه عملکرد عادلانه و بی‌طرفانه بین بک‌اند پایتون و بک‌اند Go در شرایط کاملاً یکسان:
- سخت‌افزار یکسان (همین ماشین)
- دیتابیس یکسان (market.db موجود در ریشه)
- حالت اجرای یکسان (read-only و بدون حلقه‌های پس‌زمینه / no-loops)
- اندپوینت‌های کاملاً معادل (/api/market, /api/chart/فولاد, /api/mstat/summary)
- پارامترها: زمان شروع سرد (Cold Start)، حافظه RAM در حالت Idle و Load، تاخیر صدک ۵۰ و ۹۵
"""

import os
import sys
import time
import json
import urllib.parse
import urllib.request
import subprocess

try:
    import psutil
except ImportError:
    psutil = None

def get_process_memory_mb(pid: int) -> float:
    if psutil:
        try:
            p = psutil.Process(pid)
            # جمع حافظه با زیرپروسه‌ها
            mem = p.memory_info().rss
            for c in p.children(recursive=True):
                try:
                    mem += c.memory_info().rss
                except Exception:
                    pass
            return round(mem / (1024 * 1024), 2)
        except Exception:
            pass
    # فالبک با PowerShell در ویندوز
    try:
        cmd = f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue).WorkingSet64"
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command", cmd]).decode().strip()
        if out:
            return round(int(out) / (1024 * 1024), 2)
    except Exception:
        pass
    return 0.0

def wait_for_ready(url: str, timeout: float = 20.0) -> float:
    start = time.perf_counter()
    deadline = start + timeout
    while time.perf_counter() < deadline:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FairBenchmark/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    return (time.perf_counter() - start) * 1000.0
        except Exception:
            time.sleep(0.05)
    raise TimeoutError(f"Server at {url} did not become ready within {timeout}s")

def benchmark_endpoint(url: str, count: int = 30) -> dict:
    latencies = []
    successes = 0
    payload_len = 0
    for _ in range(count):
        req = urllib.request.Request(url, headers={"User-Agent": "FairBenchmark/1.0"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = resp.read()
                latencies.append((time.perf_counter() - t0) * 1000.0)
                successes += 1
                payload_len = len(data)
        except Exception as e:
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

def run_benchmark():
    results = {}

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
        go_cold_start = wait_for_ready(f"http://127.0.0.1:{go_port}/healthz")
        time.sleep(0.5)
        go_idle_mem = get_process_memory_mb(go_proc.pid)

        go_bench = {
            "cold_start_ms": round(go_cold_start, 2),
            "idle_rss_mb": go_idle_mem,
            "endpoints": {}
        }

        # اندپوینت‌های معادل
        symbol_enc = urllib.parse.quote("فولاد")
        test_routes = [
            ("market", f"http://127.0.0.1:{go_port}/api/market"),
            ("chart_db_foolad", f"http://127.0.0.1:{go_port}/api/chart-db/{symbol_enc}"),
            ("mstat_summary", f"http://127.0.0.1:{go_port}/api/mstat/summary"),
        ]

        for name, url in test_routes:
            print(f"  سنجش Go: {name}...")
            go_bench["endpoints"][name] = benchmark_endpoint(url, count=30)

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
        py_cold_start = wait_for_ready(f"http://127.0.0.1:{py_port}/api/market")
        time.sleep(0.5)
        py_idle_mem = get_process_memory_mb(py_proc.pid)

        py_bench = {
            "cold_start_ms": round(py_cold_start, 2),
            "idle_rss_mb": py_idle_mem,
            "endpoints": {}
        }

        test_routes = [
            ("market", f"http://127.0.0.1:{py_port}/api/market"),
            ("chart_db_foolad", f"http://127.0.0.1:{py_port}/api/chart-db/{symbol_enc}"),
            ("mstat_summary", f"http://127.0.0.1:{py_port}/api/mstat/summary"),
        ]

        for name, url in test_routes:
            print(f"  سنجش Python: {name}...")
            py_bench["endpoints"][name] = benchmark_endpoint(url, count=30)

        py_bench["load_rss_mb"] = get_process_memory_mb(py_proc.pid)
        results["python"] = py_bench
    finally:
        py_proc.terminate()
        try:
            py_proc.wait(timeout=3)
        except Exception:
            py_proc.kill()

    # خروجی JSON
    with open("tools/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n" + "="*70)
    print("جدول مقایسه عملکرد عادلانه (Go در برابر Python)")
    print("="*70)
    print(f"{'شاخص / اندپوینت':<30} | {'Go (borsd)':<18} | {'Python (FastAPI)':<18} | {'نسبت برتری Go':<12}")
    print("-" * 84)

    cs_go = results["go"]["cold_start_ms"]
    cs_py = results["python"]["cold_start_ms"]
    cs_ratio = f"{cs_py / max(cs_go, 0.001):.1f}x سریع‌تر" if cs_go > 0 else "-"
    print(f"{'زمان شروع سرد (Cold Start)':<30} | {cs_go:>14} ms | {cs_py:>14} ms | {cs_ratio:<12}")

    idle_go = results["go"]["idle_rss_mb"]
    idle_py = results["python"]["idle_rss_mb"]
    idle_ratio = f"{idle_py / max(idle_go, 0.001):.1f}x سبک‌تر" if idle_go > 0 else "-"
    print(f"{'مصرف رم در حالت بیکار (Idle RSS)':<30} | {idle_go:>14} MB | {idle_py:>14} MB | {idle_ratio:<12}")

    load_go = results["go"]["load_rss_mb"]
    load_py = results["python"]["load_rss_mb"]
    load_ratio = f"{load_py / max(load_go, 0.001):.1f}x سبک‌تر" if load_go > 0 else "-"
    print(f"{'مصرف رم زیر بار (Load RSS)':<30} | {load_go:>14} MB | {load_py:>14} MB | {load_ratio:<12}")

    for ep in ["market", "chart_db_foolad", "mstat_summary"]:
        g = results["go"]["endpoints"][ep]
        p = results["python"]["endpoints"][ep]
        if g["p50_ms"] is not None and p["p50_ms"] is not None:
            r = f"{p['p50_ms'] / max(g['p50_ms'], 0.001):.1f}x"
            print(f"{ep + ' (p50)':<30} | {g['p50_ms']:>14} ms | {p['p50_ms']:>14} ms | {r:<12}")
            r95 = f"{p['p95_ms'] / max(g['p95_ms'], 0.001):.1f}x"
            print(f"{ep + ' (p95)':<30} | {g['p95_ms']:>14} ms | {p['p95_ms']:>14} ms | {r95:<12}")

    print("="*70)

if __name__ == "__main__":
    run_benchmark()
