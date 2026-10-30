#!/usr/bin/env python
"""گیتِ B1: تطبیقِ سه مسیرِ تابلو با پایتون روی دو کپیِ یخ‌زده، و کارایی.

قواعدِ سخت (همان‌هایِ B0، به‌علاوهٔ یکی):
* بانکِ عملیاتی هرگز با SQLite باز نمی‌شود؛ فقط کپیِ فایل. هر کپی با
  quick_check خوانده می‌شود و کپیِ خراب با exit 2 رد می‌شود.
* گاردِ کناربانک: (اندازه، mtime_ns) هر -wal/-shmِ کنارِ market.db/user.db در
  ریشه پیش و پس از اجرا مقایسه می‌شود. سرورِ پایتون با
  tools/parity/serve_market_copy.py بالا می‌آید تا مسیرِ migrateِ کدال هم به
  کپی بسته باشد، نه به بانکِ عملیاتی.
* فقط PIDهایی کشته می‌شوند که همین اسکریپت بالا آورده.
* پایتون در طولِ دسته پنجره‌های board_hist_v/board_hist_fv را در کپیِ خودش
  بازسازی می‌کند (نوشتنِ مشروع و مشتق). پس تغییرِ کپیِ پایتون شکست نیست؛ تغییرِ
  کپیِ Go شکست است (فازِ A فقط می‌خواند) و برابریِ شروع دو کپی الزامی است.

کدِ خروج همان معنایِ gate_b0 را دارد: 0 همه چیز سبز، 1 اندازه‌گیری انجام شد و
دست‌کم یک بررسی قرمز است، 2 نتوانستیم اندازه بگیریم (کپی/پورت/بیلد/سرور).
"""
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GO = os.path.join(ROOT, "backend-go")
BORSD = os.path.join(GO, "bin", "borsd.exe")
PARITY = os.path.join(GO, "bin", "parity.exe")
SERVE = os.path.join(ROOT, "tools", "parity", "serve_market_copy.py")
CASES = os.path.join(ROOT, "tools", "parity", "cases_b1.json")
PERF_CASES = os.path.join(ROOT, "tools", "parity", "cases_b1_perf.json")
OUT = os.path.join(ROOT, "_audit", "parity", "B1.json")
CONTRACT = os.path.join(ROOT, "_audit", "parity", "B1-contract.json")
PERF = os.path.join(ROOT, "_audit", "parity", "B1-perf.json")
# پیش‌فرض‌ها همان دو پورتِ قراردادند؛ درزِ محیطی فقط برایِ وقتی است که پورتی
# را فرآیندی گرفته که این گیت بالا نیاورده و اجازهٔ کشتنش را ندارد.
GO_PORT = int(os.environ.get("BORS_B1_GO_PORT", "8298"))
PY_PORT = int(os.environ.get("BORS_B1_PY_PORT", "8299"))
DB_NAMES = ("market.db", "user.db")
SIDECAR_SUFFIXES = ("-wal", "-shm")
HASH_CHUNK = 1 << 20
PERF_SAMPLES = 20


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(HASH_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def sidecar_state():
    state = {}
    for name in DB_NAMES:
        for suffix in SIDECAR_SUFFIXES:
            path = os.path.join(ROOT, name + suffix)
            if os.path.exists(path):
                st = os.stat(path)
                state[name + suffix] = (st.st_size, st.st_mtime_ns)
            else:
                state[name + suffix] = None
    return state


def describe(entry):
    return "absent" if entry is None else "%dB@%dns" % entry


def sidecar_problem(before, after):
    for key in before:
        old, new = before[key], after[key]
        if old is None and new is not None:
            return "%s appeared (%s)" % (key, describe(new))
        if old is not None and new is None:
            return "%s disappeared (was %s)" % (key, describe(old))
        if old != new:
            return "%s changed (%s -> %s)" % (key, describe(old), describe(new))
    return None


def snapshot_db(src, dst):
    shutil.copy2(src, dst)
    src_wal = src + "-wal"
    if os.path.exists(src_wal) and os.path.getsize(src_wal) > 0:
        shutil.copy2(src_wal, dst + "-wal")
    con = sqlite3.connect("file:%s?mode=ro" % dst.replace("\\", "/"), uri=True)
    try:
        return [row[0] for row in con.execute("PRAGMA quick_check").fetchall()]
    finally:
        con.close()


def run(cmd, cwd=None, env=None):
    p = subprocess.run(cmd, cwd=cwd or ROOT, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def wait_json(url, deadline_s, accept):
    start = time.perf_counter()
    last = None
    while time.perf_counter() - start < deadline_s:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as r:
                body = json.loads(r.read())
                last = body
                if r.status == 200 and accept(body):
                    return True
        except Exception:
            pass
        time.sleep(0.05)
    print("readiness failed for %s (last=%s)" % (url, last))
    return False


def http_get(url, headers=None):
    """(status, headers, body). هدرها عینِ HTTPMessage می‌مانند تا get بی‌حساس به حرف بزرگ/کوچک باشد؛
    304 هم از مسیرِ HTTPError برمی‌گردد."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def probe(base):
    """MISS، HIT، 304 و اندازه‌ها را از یک سرور می‌گیرد."""
    status, headers, body = http_get(base + "/api/market")
    out = {
        "status": status,
        "content_type": (headers.get("Content-Type") or "").split(";")[0].strip().lower(),
        "cache_control": (headers.get("Cache-Control") or "").strip(),
        "xcache_first": (headers.get("X-Cache") or "").strip(),
        "etag": (headers.get("ETag") or "").strip(),
        "bytes": len(body),
    }
    try:
        out["rows"] = len(json.loads(body).get("data") or [])
    except ValueError:
        out["rows"] = -1
    status2, headers2, _ = http_get(base + "/api/market")
    out["xcache_second"] = (headers2.get("X-Cache") or "").strip()
    status3, _, body3 = http_get(base + "/api/market", {"If-None-Match": out["etag"]})
    out["not_modified"] = status3 == 304 and len(body3) == 0
    _, _, all_body = http_get(base + "/api/market?fields=all")
    out["bytes_all"] = len(all_body)
    return out


def flag_rows(path):
    """ردیف‌هایِ tape_flag_day یک کپی؛ ارزش‌ها ساختاری، نه متنی."""
    if not os.path.exists(path):
        return None
    con = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
    try:
        raw = con.execute("SELECT ins_code, flag, d_even, symbol, evidence, source"
                          " FROM tape_flag_day").fetchall()
    except sqlite3.Error:
        return None
    finally:
        con.close()
    out = {}
    for code, flag, day, symbol, evidence, source in raw:
        try:
            ev = json.loads(evidence) if evidence else {}
        except ValueError:
            ev = {"!!unparsed": evidence}
        out[(str(code), str(flag), int(day))] = (symbol or "", ev, source or "")
    return out


def main() -> int:
    os.makedirs(os.path.join(GO, "bin"), exist_ok=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for target, out in (("./cmd/borsd", BORSD), ("./cmd/parity", PARITY)):
        rc, log = run(["go", "build", "-o", out, target], cwd=GO)
        if rc != 0:
            print(log)
            return 2
    rc, tests = run(["go", "test", "-count=1", "./..."], cwd=GO)
    if rc != 0:
        print(tests)
        return 2
    for port in (GO_PORT, PY_PORT):
        if not port_free(port):
            print("port %d is busy" % port)
            return 2
    commit = run(["git", "rev-parse", "--short", "HEAD"])[1].strip()
    go_version = run(["go", "version"])[1].strip()

    before_sidecars = sidecar_state()
    tmp = tempfile.mkdtemp(prefix="bors-b1-")
    go_dir = os.path.join(tmp, "go")
    py_dir = os.path.join(tmp, "py")
    os.makedirs(go_dir)
    os.makedirs(py_dir)
    procs = []
    result = 2
    try:
        for name in DB_NAMES:
            src = os.path.join(ROOT, name)
            if not os.path.exists(src):
                continue
            for dst_dir in (go_dir, py_dir):
                try:
                    check = snapshot_db(src, os.path.join(dst_dir, name))
                except (sqlite3.Error, OSError) as err:
                    print("snapshot copy unusable: %s: %s" % (name, err))
                    return 2
                if check != ["ok"]:
                    print("quick_check failed for %s copy: %s" % (name, check))
                    return 2
        go_db = os.path.join(go_dir, "market.db")
        py_db = os.path.join(py_dir, "market.db")
        db_hash = sha256_file(go_db)
        frozen_ok = db_hash == sha256_file(py_db)
        if not frozen_ok:
            print("the two copies are not identical")
            return 2

        py_env = dict(os.environ, BORS_DATA_DIR=py_dir, BORS_NO_FETCH_LOOPS="1",
                      BORS_CODAL_OFFLINE="1", BORS_CODAL_AUTO="0",
                      BORS_PARITY_PORT=str(PY_PORT), PYTHONIOENCODING="utf-8")
        py_log = open(os.path.join(tmp, "py.log"), "w", encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, SERVE], cwd=ROOT, env=py_env,
                                       stdout=py_log, stderr=subprocess.STDOUT), py_log))
        if not wait_json("http://127.0.0.1:%d/openapi.json" % PY_PORT, 60.0, lambda b: True):
            return 2
        go_proc = subprocess.Popen(
            [BORSD, "--port", str(GO_PORT), "--read-only", "--no-loops", "--db-dir", go_dir],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append((go_proc, None))
        if not wait_json("http://127.0.0.1:%d/healthz" % GO_PORT, 15.0,
                         lambda b: b.get("status") == "ok"):
            return 2
        _, _, health_body = http_get("http://127.0.0.1:%d/healthz" % GO_PORT)
        health = json.loads(health_body)
        if os.path.normcase(os.path.normpath(health.get("data_dir", ""))) != \
                os.path.normcase(os.path.normpath(go_dir)):
            print("healthz is not from this gate's server")
            return 2

        py_url = "http://127.0.0.1:%d" % PY_PORT
        go_url = "http://127.0.0.1:%d" % GO_PORT
        p_py = probe(py_url)
        p_go = probe(go_url)

        rc, log = run([PARITY, "--py", py_url, "--go", go_url, "--cases", CASES,
                       "--out", CONTRACT, "--commit", commit])
        print(log.strip())
        if rc == 2:
            print("contract batch could not run")
            return 2
        rc, log = run([PARITY, "--py", py_url, "--go", go_url, "--cases", PERF_CASES,
                       "--out", PERF, "--commit", commit])
        print(log.strip())
        if rc == 2:
            print("perf batch could not run")
            return 2
        contract = json.load(open(CONTRACT, encoding="utf-8"))
        perf = json.load(open(PERF, encoding="utf-8"))
        with open(CASES, encoding="utf-8") as f:
            case_count = len(json.load(f)["cases"])

        contract_ok = contract["failed"] == 0 and contract["passed"] == case_count
        size_ok = p_go["bytes"] <= p_py["bytes"] and p_go["bytes_all"] <= p_py["bytes_all"]
        rows_ok = p_py["rows"] == p_go["rows"] and p_py["rows"] > 0
        # Cache-Controlِ رویِ سیم در پایتون «max-age=15»ِ خودِ مسیر نیست:
        # میدل‌ورِ سراسریِ app.py (no_cache_middleware) آن را پس از هندلر به
        # no-store بازنویسی می‌کند و اندازه‌گیریِ همین گیت هم همین را دید. پس
        # مقدارِ مشاهده‌شدهٔ پایتون پین می‌شود و Go باید عیناً همان را بدهد
        # (httpapi.noCache همان میدل‌ور را پورت می‌کند). X-Cache و ETag/304 جدا
        # سنجیده می‌شوند.
        headers_ok = (p_py["content_type"] == p_go["content_type"] == "application/json"
                      and p_py["cache_control"] == "no-cache, no-store, must-revalidate"
                      and p_go["cache_control"] == p_py["cache_control"])
        cache_ok = (p_py["xcache_first"] == p_go["xcache_first"] == "MISS"
                    and p_py["xcache_second"] == p_go["xcache_second"] == "HIT")
        etag_ok = p_py["not_modified"] and p_go["not_modified"]
        ratio = perf["p95_go"] / perf["p95_py"] if perf["p95_py"] else 0.0
        perf_ok = perf["p95_py"] > 0 and perf["p95_go"] <= 0.5 * perf["p95_py"]

        # پس از خاموشی: کپی‌ها دیگر باز نیستند، پس خواندنِ آن‌ها آزاد است.
        go_rows = flag_rows(os.path.join(go_dir, "user.db"))
        py_rows = flag_rows(os.path.join(py_dir, "user.db"))
        history_ok = go_rows is not None and py_rows is not None and go_rows == py_rows
        go_db_unchanged = sha256_file(go_db) == db_hash
        py_db_changed = sha256_file(py_db) != db_hash

        payload = {
            "commit": commit,
            "go_version": go_version,
            "python": sys.version.split()[0],
            "db": {"sha256": db_hash, "frozen_ok": frozen_ok,
                   "go_copy_unchanged": go_db_unchanged,
                   "py_copy_changed": py_db_changed},
            "rows": {"py": p_py["rows"], "go": p_go["rows"], "ok": rows_ok},
            "bytes": {"default_py": p_py["bytes"], "default_go": p_go["bytes"],
                      "all_py": p_py["bytes_all"], "all_go": p_go["bytes_all"],
                      "ok": size_ok},
            "perf": {"samples": PERF_SAMPLES, "p50_py": perf["p50_py"],
                     "p95_py": perf["p95_py"], "p50_go": perf["p50_go"],
                     "p95_go": perf["p95_go"], "ratio": round(ratio, 4), "ok": perf_ok},
            "headers": {"py": p_py, "go": p_go, "ok": headers_ok,
                        "cache_ok": cache_ok, "etag_ok": etag_ok},
            "contract": {"passed": contract["passed"], "failed": contract["failed"],
                         "report": os.path.relpath(CONTRACT, ROOT), "ok": contract_ok},
            "history": {"py_rows": 0 if py_rows is None else len(py_rows),
                        "go_rows": 0 if go_rows is None else len(go_rows),
                        "ok": history_ok},
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write("\n")
        checks = {"contract": contract_ok, "rows": rows_ok, "size": size_ok,
                  "perf": perf_ok, "headers": headers_ok, "cache": cache_ok,
                  "etag": etag_ok, "history": history_ok,
                  "go_read_only": go_db_unchanged}
        print("checks: " + " ".join("%s=%s" % (k, v) for k, v in checks.items()))
        print("p50 py=%.1fms go=%.1fms | p95 py=%.1fms go=%.1fms (ratio %.3f)"
              % (perf["p50_py"], perf["p50_go"], perf["p95_py"], perf["p95_go"], ratio))
        print("bytes default %d -> %d | all %d -> %d"
              % (p_py["bytes"], p_go["bytes"], p_py["bytes_all"], p_go["bytes_all"]))
        result = 0 if all(checks.values()) else 1
    finally:
        for proc, log in reversed(procs):
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            if log is not None:
                log.close()
        after_sidecars = sidecar_state()
        problem = sidecar_problem(before_sidecars, after_sidecars)
        if problem:
            print("sidecar guard failed: %s" % problem)
            result = 2
        shutil.rmtree(tmp, ignore_errors=True)
    if result == 0:
        print("sidecar guard ok")
    return result


if __name__ == "__main__":
    sys.exit(main())
