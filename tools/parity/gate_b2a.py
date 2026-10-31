#!/usr/bin/env python
"""گیتِ B2: مسیرهایِ GETِ /api/mstat/* رویِ دو کپیِ یخ‌زده.

پیش‌فرض: B2a با یازده مسیر. `gate_b2b.py` همین بدنه را با فهرستِ سیزده‌مسیره
و شاهدِ جدا اجرا می‌کند (BORS_B2_CASES/BORS_B2_OUT/BORS_B2_CONTRACT).

همان قواعدِ gate_b1 را از خودش قرض می‌گیرد: بانکِ عملیاتی با SQLite باز
نمی‌شود، هر کپی quick_check می‌خورد، گاردِ کناربانک پیش/پس مقایسه می‌شود، و
فقط PIDهایی کشته می‌شوند که همین اسکریپت بالا آورده. به شرطِ وظیفه، دو چیز
تازه هم هست: اثرانگشتِ (sha256، mtime) هر دو بانکِ ریشه پیش/پس گرفته و
مقایسه می‌شود، و پیش از بالا آمدنِ سرورِ پایتون ثابت می‌شود که
`bors_config.DB_PATH`/`USER_DB_PATH` داخلِ کپی افتاده‌اند (نه در ریشه).

سه سنجهٔ اصلی:
* صفر اختلاف رویِ همهٔ مسیرهایِ فهرست (قرارداد) — کیس‌هایِ ‎-422 و یک صنعتِ
  برگرفته از دادهٔ همان کپی هم در دسته‌اند. بیشینهٔ دلتای عددی جدا ثبت می‌شود.
* POST /api/mstat/snapshot در Go هنوز 501 و در پایتون 200 است — تفاوتِ
  اعلام‌شده تا B6؛ اندازه‌گیری می‌شود، فرض نمی‌شود.
* clock_now بیرونِ مقایسه است ولی هر دو باید timestampِ معتبر بدهند.

کدِ خروج: 0 سبز، 1 اندازه‌گیری شد و قرمز، 2 نتوانستیم اندازه بگیریم.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import gate_b1 as base  # noqa: E402

ROOT = base.ROOT
GO = base.GO
# پیش‌فرض‌ها همان کیس/شاهدِ B2a (یازده مسیر) است؛ gate_b2b.py با متغیرهایِ
# محیطی فهرستِ سیزده‌مسیره و شاهدِ جدا می‌دهد — یک بدنه و دو ورودی، نه دو نسخه.
CASES = os.environ.get("BORS_B2_CASES") or os.path.join(HERE, "cases_b2a.json")
OUT = os.environ.get("BORS_B2_OUT") or os.path.join(ROOT, "_audit", "parity", "B2a.json")
CONTRACT = (os.environ.get("BORS_B2_CONTRACT")
            or os.path.join(ROOT, "_audit", "parity", "B2a-contract.json"))
# پیش‌فرض‌ها همان دو پورتِ قراردادند؛ اگر فرآیندی که این گیت بالا نیاورده
# پورتی را گرفته باشد، پورتِ آزادِ بعدی انتخاب و در شاهد ثبت می‌شود — هرگز
# فرآیندِ غریبه کشته نمی‌شود.
GO_PORT = int(os.environ.get("BORS_B2A_GO_PORT", "8296"))
PY_PORT = int(os.environ.get("BORS_B2A_PY_PORT", "8297"))
# بانک‌هایِ ریشه که اثرانگشت می‌شوند. codal.db هم اضافه است: گیت هیچ‌کدام را با
# SQLite باز نمی‌کند و فقط می‌خواند، پس هزینه‌اش چند ثانیه هش است در برابرِ
# «ادعایِ دست‌نخورده بودنِ کلِ دادِ ریشه».
ROOT_DBS = ("market.db", "user.db", "codal.db")
PORT_SCAN = 60
LOG_TAIL_LINES = 60


def post_json(url):
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read() or b"{}")
        except ValueError:
            body = {}
        return e.code, body
    except Exception as err:  # noqa: BLE001 — سرورِ مرده = سنجهٔ قرمز، نه کرشِ گیت
        return 0, {"error": str(err)}


def get_json(url):
    """بدنهٔ JSON با خطای مهارشده؛ سرورِ مرده سنجه را قرمز می‌کند."""
    try:
        status, _, body = base.http_get(url)
        return status, json.loads(body)
    except Exception as err:  # noqa: BLE001
        return None, {"error": str(err)}


def industry_case(py_url):
    """نامِ نخستین صنعتِ دارایِ نماد از خودِ پایتون.

    صنعت‌ها در بانک با حرف‌هایِ عربی/فارسی ذخیره می‌شوند و نوشتنشان در فایلِ
    کیس شکننده است؛ از پاسخِ خودِ سرور برداشته و percent-encode می‌شود تا فیلتر
    رویِ دادهٔ واقعی بیفتد، نه رویِ صنعتِ ناموجود.
    """
    status, _, body = base.http_get(py_url + "/api/mstat/industries")
    if status != 200:
        return None
    try:
        rows = json.loads(body).get("rows") or []
    except ValueError:
        return None
    try:
        for row in rows:
            name = (row.get("industry") or "").strip()
            if name and (row.get("symbols") or 0) > 0:
                return name
    except (AttributeError, TypeError):
        return None
    return None


def valid_clock(value):
    try:
        time.strptime(value, "%Y-%m-%d %H:%M:%S")
        return True
    except (TypeError, ValueError):
        return False


def root_fingerprint():
    """(sha256، اندازه، mtime_ns) هر بانکِ ریشه — فقط خواندنِ بایت‌ها.

    این فایل‌ها هرگز با SQLite باز نمی‌شوند؛ هشِ جریانی هم فقط می‌خواند.
    """
    out = {}
    for name in ROOT_DBS:
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            out[name] = None
            continue
        st = os.stat(path)
        out[name] = {"sha256": base.sha256_file(path), "bytes": st.st_size,
                     "mtime_ns": st.st_mtime_ns}
    return out


def pick_port(preferred, taken):
    """پورتِ آزاد از preferred به بعد؛ پورتِ گرفته‌شده هرگز کشته/آزاد نمی‌شود."""
    for port in range(preferred, preferred + PORT_SCAN):
        if port in taken:
            continue
        if base.port_free(port):
            return port
    raise RuntimeError("no free port in [%d, %d)" % (preferred, preferred + PORT_SCAN))


def python_redirect_ok(py_dir, env):
    """پیش از هر importِ app: ببین بک‌اند کدام بانک را باز می‌کند.

    `bors_config` تنها ماژولی است که این‌جا import می‌شود (بدونِ app)؛ ادعا
    همان چیزی است که gate_b1 در عمل به آن تکیه می‌کند، ولی صریح نشده بود.
    """
    probe = ("import json, bors_config;"
             "print(json.dumps({'market': bors_config.DB_PATH,"
             " 'user': bors_config.USER_DB_PATH}))")
    rc, log = base.run([sys.executable, "-c", probe], cwd=ROOT, env=env)
    if rc != 0:
        print("bors_config probe failed: %s" % log.strip())
        return False, None
    try:
        paths = json.loads(log.strip().splitlines()[-1])
    except (ValueError, IndexError):
        print("bors_config probe printed no JSON: %r" % log[-400:])
        return False, None
    want = {"market": os.path.join(py_dir, "market.db"),
            "user": os.path.join(py_dir, "user.db")}
    labels = {"market": "DB_PATH", "user": "USER_DB_PATH"}
    for key in want:
        got = os.path.normcase(os.path.normpath(paths.get(key) or ""))
        exp = os.path.normcase(os.path.normpath(want[key]))
        if got != exp:
            print("bors_config.%s is outside the frozen copy: %s != %s"
                  % (labels[key], paths.get(key), want[key]))
            return False, paths
    return True, paths


def dump_logs(tmp):
    """آخرین خطوطِ هر دو سرور — فقط وقتی اندازه‌گیری قرمز/ناممکن شده."""
    for name in ("py.log", "go.log"):
        path = os.path.join(tmp, name)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        tail = lines[-LOG_TAIL_LINES:]
        print("---- %s (last %d of %d lines) ----" % (name, len(tail), len(lines)))
        for line in tail:
            print(line)


def main() -> int:
    os.makedirs(os.path.join(GO, "bin"), exist_ok=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    root_before = root_fingerprint()
    if root_before["market.db"] is None:
        print("operational market.db is missing; nothing to freeze")
        return 2

    for target, out in (("./cmd/borsd", base.BORSD), ("./cmd/parity", base.PARITY)):
        rc, log = base.run(["go", "build", "-o", out, target], cwd=GO)
        if rc != 0:
            print(log)
            return 2
    rc, tests = base.run(["go", "test", "-count=1", "./..."], cwd=GO)
    if rc != 0:
        print(tests)
        return 2

    taken = set()
    go_port = pick_port(GO_PORT, taken)
    taken.add(go_port)
    py_port = pick_port(PY_PORT, taken)
    fell_back = (go_port, py_port) != (GO_PORT, PY_PORT)
    if fell_back:
        print("ports busy: using go=%d py=%d (requested %d/%d)"
              % (go_port, py_port, GO_PORT, PY_PORT))
    commit = base.run(["git", "rev-parse", "--short", "HEAD"])[1].strip()

    before_sidecars = base.sidecar_state()
    tmp = tempfile.mkdtemp(prefix="bors-b2a-")
    go_dir = os.path.join(tmp, "go")
    py_dir = os.path.join(tmp, "py")
    os.makedirs(go_dir)
    os.makedirs(py_dir)
    procs = []
    result = 2
    # frozen_ok در عمل با «رسیدن به مرحلهٔ سرورها» ثابت می‌شود؛ اما در شاهد باید
    # نتیجهٔ سنجه باشد، نه یک حرفِ ثابتِ True که هیچ‌وقت دروغ نمی‌گوید.
    frozen_ok = False
    try:
        for name in base.DB_NAMES:
            src = os.path.join(ROOT, name)
            if not os.path.exists(src):
                continue
            for dst_dir in (go_dir, py_dir):
                try:
                    check = base.snapshot_db(src, os.path.join(dst_dir, name))
                except Exception as err:  # noqa: BLE001 — کپیِ ناخوانا = اندازه‌گیری ناممکن
                    print("snapshot copy unusable: %s: %s" % (name, err))
                    return 2
                if check != ["ok"]:
                    print("quick_check failed for %s copy: %s" % (name, check))
                    return 2
        go_db = os.path.join(go_dir, "market.db")
        py_db = os.path.join(py_dir, "market.db")
        db_prints = base.db_fingerprint(go_db)
        if db_prints != base.db_fingerprint(py_db):
            print("the two copies are not identical")
            return 2
        frozen_ok = True

        py_env = dict(os.environ, BORS_DATA_DIR=py_dir, BORS_NO_FETCH_LOOPS="1",
                      BORS_CODAL_OFFLINE="1", BORS_CODAL_AUTO="0",
                      BORS_PARITY_PORT=str(py_port), PYTHONIOENCODING="utf-8")
        redirect_ok, redirect_paths = python_redirect_ok(py_dir, py_env)
        if not redirect_ok:
            return 2

        py_log = open(os.path.join(tmp, "py.log"), "w", encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, base.SERVE], cwd=ROOT, env=py_env,
                                       stdout=py_log, stderr=subprocess.STDOUT), py_log))
        if not base.wait_json("http://127.0.0.1:%d/openapi.json" % py_port, 60.0,
                              lambda b: True):
            print("python server did not become ready")
            return 2

        go_log = open(os.path.join(tmp, "go.log"), "w", encoding="utf-8")
        go_proc = subprocess.Popen(
            [base.BORSD, "--port", str(go_port), "--read-only", "--no-loops",
             "--db-dir", go_dir],
            cwd=ROOT, stdout=go_log, stderr=subprocess.STDOUT)
        procs.append((go_proc, go_log))
        if not base.wait_json("http://127.0.0.1:%d/healthz" % go_port, 15.0,
                              lambda b: b.get("status") == "ok"):
            print("go server did not become ready")
            return 2
        _, _, health_body = base.http_get("http://127.0.0.1:%d/healthz" % go_port)
        health = json.loads(health_body)
        if os.path.normcase(os.path.normpath(health.get("data_dir", ""))) != \
                os.path.normcase(os.path.normpath(go_dir)):
            print("healthz is not from this gate's server")
            return 2

        py_url = "http://127.0.0.1:%d" % py_port
        go_url = "http://127.0.0.1:%d" % go_port

        with open(CASES, encoding="utf-8") as f:
            cases = json.load(f)
        # هشِ کپیِ یخ‌زده در فایلِ اجرا نوشته می‌شود و به parity داده می‌شود تا
        # ابزار خودش ببیند کیس‌ها و بانک یکی‌اند و بانک در دسته عوض نشده است.
        cases["db_sha256"] = db_prints["market.db"]
        picked = industry_case(py_url)
        if picked:
            cases["cases"].append({
                "name": "mainwatch-industry-live", "method": "GET",
                "path": "/api/mstat/mainwatch?industry=%s&limit=5"
                        % urllib.parse.quote(picked, safe=""),
                "exclude": []})
        dynamic_cases = os.path.join(tmp, "cases_b2a_run.json")
        with open(dynamic_cases, "w", encoding="utf-8") as f:
            json.dump(cases, f, ensure_ascii=False)
        case_count = len(cases["cases"])

        rc, log = base.run([base.PARITY, "--py", py_url, "--go", go_url,
                            "--cases", dynamic_cases, "--db", go_db,
                            "--out", CONTRACT, "--commit", commit])
        print(log.strip())
        if rc == 2:
            print("contract batch could not run")
            return 2
        with open(CONTRACT, encoding="utf-8") as f:
            contract = json.load(f)
        contract_ok = contract["failed"] == 0 and contract["passed"] == case_count
        max_delta = max([case.get("max_delta") or 0.0
                         for case in contract["cases"]] or [0.0])
        delta_zero = max_delta == 0.0
        # هیچ کیسی نباید با ۴۰۴ِ «دو طرف یکی» رد شود: بدنهٔ NotFoundِ Go عمداً مثلِ
        # FastAPI ساخته شده، پس یک مسیرِ غلط‌نویسی‌شده یا کم‌شده دو ۴۰۴ برابر می‌دهد و
        # بی‌صدا از مقایسهٔ بدنه بیرون می‌ماند. دامنهٔ مجاز: (200,200) و (422,422)،
        # و مجموعهٔ ۴۲۲ها باید مو‌به‌مو همان کیس‌هایِ ‎-422 باشد — شمارشِ ثابت یک
        # ۴۲۲ِ جاافتاده/اضافه را نمی‌دید و با آمدنِ board باید دستی عوض می‌شد.
        pairs = [(case.get("status_py"), case.get("status_go"))
                 for case in contract["cases"]]
        allowed = {(200, 200), (422, 422)}
        expect_422 = {c["name"] for c in cases["cases"] if c["name"].endswith("-422")}
        got_422 = {c["name"] for c in contract["cases"]
                   if (c.get("status_py"), c.get("status_go")) == (422, 422)}
        statuses_ok = (bool(pairs) and all(p in allowed for p in pairs)
                       and got_422 == expect_422
                       and sum(1 for p in pairs if p == (422, 422)) == len(expect_422))
        # و هیچ کیسی نباید از دسته غایب باشد: نام‌هایِ اجراشده باید مو‌به‌مو با
        # کیس‌هایِ ارسالی (به‌علاوهٔ کیسِ پویای صنعت) یکی باشد.
        wanted = sorted(case["name"] for case in cases["cases"])
        ran = sorted(case["name"] for case in contract["cases"])
        coverage_ok = wanted == ran
        failed_cases = [{"name": case["name"], "diffs": case.get("diffs") or []}
                        for case in contract["cases"] if not case.get("pass")]

        # تایم‌لاین پیش از POST سنجیده می‌شود: نوشتنِ پایتون در POST ممکن است
        # نقطهٔ تازه‌ای در mstat_snap بسازد و دو طرف دیگر هم‌حالت نباشند.
        _, tl_py_j = get_json(py_url + "/api/mstat/timeline")
        _, tl_go_j = get_json(go_url + "/api/mstat/timeline")
        points_py, points_go = tl_py_j.get("points"), tl_go_j.get("points")
        timeline_ok = (points_py == points_go
                       and tl_py_j.get("ready") == tl_go_j.get("ready")
                       and points_py is not None)
        timeline_exercised = (points_py or 0) >= 2

        # POST پس از سنجه‌هایِ فقط-خواندنی: نوشتنِ پایتون رویِ کپیِ خودش.
        py_post, py_post_body = post_json(py_url + "/api/mstat/snapshot")
        go_post, go_post_body = post_json(go_url + "/api/mstat/snapshot")
        post_ok = (go_post == 501 and go_post_body.get("code") == "NOT_PORTED"
                   and py_post == 200 and py_post_body.get("status") == "ok")

        _, ph_py_j = get_json(py_url + "/api/mstat/phase")
        _, ph_go_j = get_json(go_url + "/api/mstat/phase")
        clock_py = ph_py_j.get("clock_now")
        clock_go = ph_go_j.get("clock_now")
        clock_ok = valid_clock(clock_py) and valid_clock(clock_go)

        base.stop(procs)
        go_db_unchanged = base.db_fingerprint(go_db) == db_prints
        root_after = root_fingerprint()
        root_untouched = root_before == root_after
        # گاردِ کناربانک هم در شاهد می‌آید تا «exit=0 و گارد ok» فقط از stdoutِ
        # همان اجرا قابلِ بازخوانی نباشد؛ finally دوباره همان را سنجید و در صورتِ
        # نقض، کدِ خروج را به ۲ می‌برد.
        sidecar_problem = base.sidecar_problem(before_sidecars, base.sidecar_state())

        checks = {"contract": contract_ok, "delta_zero": delta_zero,
                  "statuses_200_422": statuses_ok, "case_coverage": coverage_ok,
                  "post_501": post_ok, "timeline": timeline_ok,
                  "timeline_exercised": timeline_exercised,
                  "industry_case_ran": bool(picked), "clock": clock_ok,
                  "go_read_only": go_db_unchanged, "root_untouched": root_untouched,
                  "frozen_copies": frozen_ok,
                  "sidecar_untouched": not sidecar_problem}
        payload = {
            "commit": commit,
            "python": sys.version.split()[0],
            "ports": {"py": py_port, "go": go_port,
                      "preferred_py": PY_PORT, "preferred_go": GO_PORT,
                      "fell_back": fell_back},
            "db": {"sha256": db_prints["market.db"],
                   "wal_sha256": db_prints.get("market.db-wal"),
                   "frozen_ok": frozen_ok, "go_copy_unchanged": go_db_unchanged,
                   "root_before": root_before, "root_after": root_after,
                   "root_untouched": root_untouched},
            "sidecar": {"ok": not sidecar_problem,
                        "problem": sidecar_problem or ""},
            "statuses": {"pairs": sorted("%s/%s" % p for p in set(pairs)),
                         "count_422": sum(1 for p in pairs if p == (422, 422)),
                         "ok": statuses_ok},
            "python_redirect": redirect_paths,
            "contract": {"passed": contract["passed"], "failed": contract["failed"],
                         "cases": case_count, "max_delta": max_delta,
                         "report": os.path.relpath(CONTRACT, ROOT), "ok": contract_ok,
                         "failed_cases": failed_cases},
            "post": {"py": py_post, "go": go_post,
                     "go_code": go_post_body.get("code"),
                     "py_status": py_post_body.get("status"),
                     "py_saved": py_post_body.get("saved"), "ok": post_ok},
            "timeline": {"py_points": points_py, "go_points": points_go,
                         "py_ready": tl_py_j.get("ready"),
                         "go_ready": tl_go_j.get("ready"),
                         "exercised": timeline_exercised,
                         "industry_case": picked, "ok": timeline_ok},
            "phase": {"py_clock": clock_py, "go_clock": clock_go, "ok": clock_ok},
            "checks": checks,
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("checks: " + " ".join("%s=%s" % kv for kv in checks.items()))
        print("contract %d/%d | max_delta=%s | timeline points py=%s go=%s (exercised=%s)"
              % (contract["passed"], case_count, max_delta, points_py, points_go,
                 timeline_exercised))
        for row in failed_cases:
            print("FAILED %s: %s" % (row["name"], "; ".join(row["diffs"][:4])))
        result = 0 if all(checks.values()) else 1
    finally:
        base.stop(procs)
        after_sidecars = base.sidecar_state()
        problem = base.sidecar_problem(before_sidecars, after_sidecars)
        if problem:
            print("sidecar guard failed: %s" % problem)
            result = 2
        if result != 0:
            dump_logs(tmp)
        shutil.rmtree(tmp, ignore_errors=True)
    if result == 0:
        print("sidecar guard ok")
    return result


if __name__ == "__main__":
    sys.exit(main())
