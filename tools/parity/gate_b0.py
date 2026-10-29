#!/usr/bin/env python
"""گیتِ B0: بیلد، تست، شروعِ سرد، RSS، healthz و نوشتنِ شاهد.

DB با کپیِ سادهٔ فایل به پوشهٔ موقت می‌رود؛ خودِ بانکِ عملیاتی هرگز با SQLite
باز نمی‌شود تا هیچ -wal/-shm کنارش ساخته نشود. اگر -wal با اندازهٔ مثبت وجود
داشته باشد همراهِ کپی می‌رود، ولی -shm هرگز کپی نمی‌شود. سلامتِ کپی پیش از
سنجش با PRAGMA quick_check روی همان کپیِ read-only بررسی می‌شود.

گاردِ کناربانک: وضعیتِ market.db-wal/-shm و user.db-wal/-shm پیش از اجرا ثبت
می‌شود و در finally مقایسه می‌شود؛ کناربانکِ تازه یا تغییرِ اندازه یعنی خطا
(exit 2). فقط PIDی کشته می‌شود که همین اسکریپت بالا آورده. هیچ شبکه و هیچ ADB.

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
DB_NAMES = ("market.db", "user.db")
SIDECAR_SUFFIXES = ("-wal", "-shm")


def sidecar_state():
    """اندازهٔ کناربانک‌هایِ DBِ عملیاتی؛ None یعنی فایل وجود ندارد."""
    state = {}
    for name in DB_NAMES:
        for suffix in SIDECAR_SUFFIXES:
            path = os.path.join(ROOT, name + suffix)
            state[name + suffix] = os.path.getsize(path) if os.path.exists(path) else None
    return state


def describe_sidecars(state):
    return " ".join(
        "%s=%s" % (key, "absent" if size is None else "%dB" % size)
        for key, size in state.items())


def sidecar_problem(before, after):
    """هر کناربانکِ تازه یا تغییرِ اندازه در طولِ گیت، نقضِ قید است."""
    for key in before:
        old = before[key]
        new = after[key]
        if old is None and new is not None:
            return "%s appeared (%dB)" % (key, new)
        if old is not None and new is None:
            return "%s disappeared (was %dB)" % (key, old)
        if old != new:
            return "%s changed (%dB -> %dB)" % (key, old, new)
    return None


def snapshot_db(src, dst):
    """کپیِ فایلِ DB به پوشهٔ موقت و بازکردنِ read-onlyِ همان کپی، نه منبع."""
    shutil.copy2(src, dst)
    src_wal = src + "-wal"
    if os.path.exists(src_wal) and os.path.getsize(src_wal) > 0:
        shutil.copy2(src_wal, dst + "-wal")
    # -shm کپی نمی‌شود؛ SQLite خودش در پوشهٔ موقت می‌سازد.
    con = sqlite3.connect("file:%s?mode=ro" % dst.replace("\\", "/"), uri=True)
    try:
        return [row[0] for row in con.execute("PRAGMA quick_check").fetchall()]
    finally:
        con.close()


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
    """تا مهلت صبر می‌کند تا healthz با status=ok جواب بدهد؛ degraded قبول نیست."""
    start = time.perf_counter()
    last = None
    while time.perf_counter() - start < deadline_s:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/healthz" % PORT, timeout=0.5) as r:
                if r.status == 200:
                    body = json.loads(r.read())
                    last = body
                    if body.get("status") == "ok":
                        return round((time.perf_counter() - start) * 1000.0, 1), body
        except Exception:
            pass
        time.sleep(0.02)
    return None, last


def run_gate() -> int:
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
        for name in DB_NAMES:
            src = os.path.join(ROOT, name)
            if not os.path.exists(src):
                continue
            check = snapshot_db(src, os.path.join(tmp, name))
            if check != ["ok"]:
                print("quick_check failed for %s copy: %s" % (name, check))
                return 2
            print("quick_check %s copy: ok" % name)
        proc = subprocess.Popen(
            [BIN, "--port", str(PORT), "--read-only", "--no-loops", "--db-dir", tmp],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            startup_ms, health = wait_health()
            if startup_ms is None:
                print("healthz never reached status=ok (last=%s, exit=%s)"
                      % (health, proc.poll()))
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
            dirty = bool(run(["git", "status", "--porcelain", "--untracked-files=no"],
                             ROOT)[1].strip())
            payload = {
                "commit": commit,
                "go_version": go_version,
                "startup_ms": startup_ms,
                "rss_mb": mem,
                "healthz": health,
                "tests_ok": True,
                "startup_ok": startup_ms < 500.0,
                "rss_ok": mem is not None and mem < 80.0,
                "dirty": dirty,
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


def main() -> int:
    before = sidecar_state()
    print("sidecar before: %s" % describe_sidecars(before))
    result = 2
    try:
        result = run_gate()
    finally:
        after = sidecar_state()
        print("sidecar after:  %s" % describe_sidecars(after))
        problem = sidecar_problem(before, after)
        if problem:
            print("sidecar guard failed: %s" % problem)
            result = 2
    if result == 0:
        print("sidecar guard ok")
    return result


if __name__ == "__main__":
    sys.exit(main())
