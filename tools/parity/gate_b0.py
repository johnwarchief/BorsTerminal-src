#!/usr/bin/env python
"""گیتِ B0: بیلد، تست، شروعِ سرد، RSS، healthz و نوشتنِ شاهد.

DB با backup API به یک پوشهٔ موقت کپی می‌شود تا هیچ فایلِ WAL کنارِ بانکِ
عملیاتی ساخته نشود. فقط PIDی کشته می‌شود که همین اسکریپت بالا آورده.
هیچ شبکه و هیچ ADB.

RSSِ واقعی با tasklist خوانده می‌شود و خروجیِ CSV با ماژولِ csv تجزیه می‌شود؛
ستونِ حافظه خودش ویرگول دارد (مثلِ «330,576 K») و تقسیمِ سادهٔ خط بر ویرگول
عدد را می‌شکند. عددِ کمتر از ۲ مگابایت یعنی شکستِ سنجش، نه قبولیِ سقفِ ۸۰ مگابایت.
"""
import csv
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GO = os.path.join(ROOT, "backend-go")
BIN = os.path.join(GO, "bin", "borsd.exe")
OUT = os.path.join(ROOT, "_audit", "parity", "B0.json")
PORT = 8298
RSS_FLOOR_MB = 2.0


def snapshot_db(src, dst):
    s = sqlite3.connect("file:%s?mode=ro" % src.replace("\\", "/"), uri=True)
    try:
        d = sqlite3.connect(dst)
        try:
            s.backup(d)
        finally:
            d.close()
    finally:
        s.close()


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def parse_rss_csv(text):
    """آخرین ستونِ خروجیِ CSVِ tasklist را به مگابایت تبدیل می‌کند؛ None یعنی نامعتبر."""
    line = (text or "").strip()
    if not line:
        return None
    try:
        rows = list(csv.reader([line]))
    except csv.Error:
        return None
    if not rows or not rows[0]:
        return None
    cell = rows[0][-1].strip().strip('"').strip()
    if not cell.endswith(" K"):
        return None
    try:
        kb = int(cell[:-2].replace(",", "").strip())
    except ValueError:
        return None
    return round(kb / 1024.0, 1)


def rss_mb(pid):
    rc, out = run(["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"], ROOT)
    if rc != 0:
        return None
    return parse_rss_csv(out)


def port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def wait_health(deadline_s=10.0):
    start = time.perf_counter()
    while time.perf_counter() - start < deadline_s:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/healthz" % PORT, timeout=0.5) as r:
                if r.status == 200:
                    return round((time.perf_counter() - start) * 1000.0, 1), json.loads(r.read())
        except Exception:
            time.sleep(0.02)
    return None, None


def main() -> int:
    os.makedirs(os.path.join(GO, "bin"), exist_ok=True)
    rc, log = run(["go", "build", "-o", BIN, "./cmd/borsd"], GO)
    if rc != 0:
        print(log)
        return 2
    rc, tests = run(["go", "test", "./..."], GO)
    if rc != 0:
        print(tests)
        return 2
    if not port_free(PORT):
        print("port %d is busy" % PORT)
        return 2
    commit = run(["git", "rev-parse", "--short", "HEAD"], ROOT)[1].strip()
    go_version = run(["go", "version"], ROOT)[1].strip()
    tmp = tempfile.mkdtemp(prefix="bors-b0-")
    try:
        for name in ("market.db", "user.db"):
            src = os.path.join(ROOT, name)
            if os.path.exists(src):
                snapshot_db(src, os.path.join(tmp, name))
        proc = subprocess.Popen(
            [BIN, "--port", str(PORT), "--read-only", "--no-loops", "--db-dir", tmp],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            startup_ms, health = wait_health()
            if startup_ms is None:
                print("healthz never came up (exit=%s)" % proc.poll())
                return 2
            # پاسخ باید از همین نمونه با همین پوشهٔ موقت باشد، نه از سرورِ دیگری
            # که ممکن است همان موقع پورت را گرفته باشد.
            got_dir = os.path.normcase(os.path.normpath(str(health.get("data_dir", ""))))
            want_dir = os.path.normcase(os.path.normpath(tmp))
            if got_dir != want_dir or proc.poll() is not None:
                print("healthz is not from this gate's server")
                return 2
            time.sleep(1.0)
            if proc.poll() is not None:
                print("server exited before RSS measurement")
                return 2
            mem = rss_mb(proc.pid)
            if mem is None or mem < RSS_FLOOR_MB:
                print("rss measurement failed: %s" % mem)
                return 2
            payload = {
                "commit": commit,
                "go_version": go_version,
                "startup_ms": startup_ms,
                "rss_mb": mem,
                "healthz": health,
                "tests_ok": True,
                "startup_ok": startup_ms < 500.0,
                "rss_ok": mem is not None and mem < 80.0,
                "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            os.makedirs(os.path.dirname(OUT), exist_ok=True)
            with open(OUT, "w", encoding="utf-8", newline="\n") as f:
                json.dump(payload, f, ensure_ascii=False, indent=1)
                f.write("\n")
            print("startup_ms=%.1f rss_mb=%s tests_ok=True" % (startup_ms, mem))
            return 0 if (payload["startup_ok"] and payload["rss_ok"]) else 1
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
