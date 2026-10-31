#!/usr/bin/env python
"""گیتِ B3: هشت مسیرِ محلیِ api/chart.py رویِ دو کپیِ یخ‌زده.

همان قواعدِ B1/B2: بانکِ عملیاتی با SQLite باز نمی‌شود، هر کپی quick_check
می‌خورد، فقط PIDهایِ همین اسکریپت کشته می‌شوند، و اثرانگشتِ (sha256، اندازه،
mtime_ns) هر سه بانکِ ریشه پیش/پس مقایسه می‌شود.

سه چیز مخصوصِ B3:

* پایتون با `BORS_CHART_CDN=off` بالا می‌آید — درزِ پاریتیِ Task 1. بی‌این،
  `/api/fts` و `chart-db` سریِ CDN را داوری می‌کردند و Go (که تا B6 فقط
  محلی است) با همان کیس مقایسه‌ناپذیر می‌شد. خاموش بودنِ درز هم ثابت می‌شود:
  درخواستِ شبکه درِ گیت صفر است، چون serve_market_copy بی‌CDN بالا می‌آید و
  هر مسیرِ محلی از همان کپی می‌خواند.
* تنظیمات (`price_basis.json`، `fts_thresholds.json`) و تقویم
  (`BORS_CALENDAR_PATH`) عیناً به هر دو طرف داده می‌شوند؛ وگرنه یک طرف
  «closing» و طرف دیگر «last» می‌خواند و اختلافِ ساختگی می‌شد.
* نمادها درِ زمانِ اجرا از همان کپی برگزیده می‌شوند (پرس‌وجوهایِ cases_b3.json)
  تا کیس‌ها رویِ دادهٔ واقعی بیفتند، نه رویِ نامِ نمادِ دست‌نویس.

`GET /api/chart/{symbol}` درِ مقایسه نیست: Go تا B6 ۵۰۱ می‌دهد. گیت آن را
اندازه می‌گیرد و درِ شاهد می‌نویسد (py ۲۰۰ / go ۵۰۱) — نه فرضِ سبز، نه سبزِ بی‌آزمون.

کدِ خروج: 0 سبز، 1 اندازه‌گیری شد و قرمز، 2 نتوانستیم اندازه بگیریم.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import gate_b1 as base                                        # noqa: E402
import gate_b2a as engine                                     # noqa: E402

ROOT = base.ROOT
CASES = os.path.join(HERE, "cases_b3.json")
OUT = os.path.join(ROOT, "_audit", "parity", "B3.json")
CONTRACT = os.path.join(ROOT, "_audit", "parity", "B3-contract.json")
GO_PORT = int(os.environ.get("BORS_B3_GO_PORT", "8298"))
PY_PORT = int(os.environ.get("BORS_B3_PY_PORT", "8299"))
SETTINGS = ("price_basis.json", "fts_thresholds.json")
CALENDAR = os.path.join(ROOT, "static", "calendar", "cache.json")
ROOT_DBS = engine.ROOT_DBS
LOG_TAIL_LINES = 60


def pick_port(preferred, taken):
    for port in range(preferred, preferred + engine.PORT_SCAN):
        if port in taken:
            continue
        if base.port_free(port):
            return port
    raise RuntimeError("no free port near %d" % preferred)


def read_roles(db_path, roles_sql):
    """نخستین نمادِ هر نقش از همان کپیِ یخ‌زده (فقط mode=ro)."""
    con = sqlite3.connect("file:%s?mode=ro" % db_path.replace("\\", "/"), uri=True)
    out = {}
    try:
        for role, sql in roles_sql.items():
            try:
                row = con.execute(sql).fetchone()
            except sqlite3.Error:
                row = None
            out[role] = str(row[0]) if row and row[0] is not None else None
        deep = out.get("deep")
        out["past"] = None
        if deep:
            row = con.execute("SELECT date FROM price_history WHERE symbol = ? "
                              "ORDER BY date DESC LIMIT 1 OFFSET 120", (deep,)).fetchone()
            if not row:
                row = con.execute("SELECT MIN(date) FROM price_history WHERE symbol = ?",
                                  (deep,)).fetchone()
            out["past"] = str(row[0]) if row and row[0] else None
    finally:
        con.close()
    return out


def calendar_symbol(cal_path, roles):
    """نمادی که درِ تقویمِ واقعی رویداد دارد — برایِ `/api/calendar/{symbol}`."""
    try:
        with open(cal_path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    known = {v for v in roles.values() if v}

    def sym_of(ev):
        return (ev.get("asset_symbol_trade") or ev.get("instTitle")
                or ev.get("symbol") or "").strip()

    events = doc.get("events") or []
    for ev in events:
        name = sym_of(ev)
        if name and name in known:
            return name
    for ev in events:
        name = sym_of(ev)
        if name:
            return name
    return None


def build_cases(spec, roles):
    """جایگزینیِ {role}؛ نقشی که نبود ⇒ کیسش حذف می‌شود و ثبت می‌گردد."""
    kept, dropped = [], []
    for case in spec["cases"]:
        path, missing = case["path"], None
        for ph in ("deep", "watch", "adjust", "events", "verdict", "corporate",
                   "short", "thin", "absent", "book", "past", "cal"):
            if "{%s}" % ph in path and not roles.get(ph):
                missing = ph
                break
        if missing:
            dropped.append("%s (role %s has no data)" % (case["name"], missing))
            continue
        for key, val in roles.items():
            if val:
                path = path.replace("{%s}" % key, urllib.parse.quote(val, safe=""))
        kept.append({"name": case["name"], "method": case.get("method", "GET"),
                     "path": path, "exclude": case.get("exclude") or []})
    return kept, dropped


B3_ROUTES = {"/api/chart/{symbol}", "/api/chart/{symbol}/key-levels",
             "/api/chart-db/{symbol}", "/api/fts/{symbol}", "/api/order-book/{symbol}",
             "/api/calendar/upcoming", "/api/calendar/{symbol}", "/api/ma/{symbol}",
             "/api/patterns/{symbol}"}


def template_of(path):
    """مسیرِ اجرا را به الگویِ فهرستِ پایتون برمی‌گرداند (نماد ⇒ {symbol}).

    نماد percent-encode شده یک قطعهٔ path است (quote(safe="") اسلش را هم می‌بندد)،
    پس قطعهٔ پس از نامِ مسیر همیشه همان نماد است، جز `calendar/upcoming`.
    """
    pure = path.split("?", 1)[0]
    segs = [x for x in pure.split("/") if x]
    if len(segs) >= 3 and segs[0] == "api":
        head, tail = "/api/" + segs[1], segs[2:]
        if head == "/api/calendar" and tail[0] == "upcoming":
            return "/api/calendar/upcoming"
        if head == "/api/chart" and len(tail) == 2 and tail[1] == "key-levels":
            return "/api/chart/{symbol}/key-levels"
        if len(tail) == 1:
            return head + "/{symbol}"
    return pure


def basket_check(py_url, cases, basket):
    """قیمتِ سبد باید از کلیدِ کش بیرون بیاید و درِ موتورِ خروج بنشیند."""
    if not basket.get("ok"):
        return ["basket seed: %s" % basket.get("why")]
    path = {c["name"]: c["path"] for c in cases}.get("fts-deep")
    if not path:
        return ["no fts-deep case to carry the basket hint"]
    body = engine.get_json(py_url + path)[1]
    l1 = ((body.get("fts") or {}).get("exit_engine") or {}).get("l1") or {}
    if l1.get("stop_basis") != "entry" or l1.get("hard_stop") != basket["hard_stop_expected"]:
        return ["fts-deep hint did not reach the engine: l1=%r" % (l1,)]
    return []


def content_checks(py_url, cases):
    """هیچ کیسی نباید با بدنهٔ تهی سبز شده باشد؛ سنسور باید رأی را ببیند."""
    by_name = {c["name"]: c["path"] for c in cases}
    problems = []

    def want(name):
        return by_name.get(name)

    path = want("chart-db-deep")
    if path:
        body = engine.get_json(py_url + path)[1]
        if body.get("status") != "success" or (body.get("count") or 0) < 100:
            problems.append("chart-db-deep count=%r" % body.get("count"))
        if body.get("priceBasis") not in ("last", "closing"):
            problems.append("chart-db-deep priceBasis=%r" % body.get("priceBasis"))
        fts = body.get("fts") or {}
        if (fts.get("status") or {}).get("code") is None:
            problems.append("chart-db-deep has no fts.status")
    path = want("chart-db-watch")
    if path:
        body = engine.get_json(py_url + path)[1]
        # درِ این کپی market_watch از price_history قدیمی‌تر است ⇒ هیچ نشستی
        # «جدیدتر از آخرینِ تاریخچه» نیست و شاخهٔ تزریق نمی‌تواند روشن شود.
        # اثباتِ آن شاخه درِ فیکسچر است (گاردِ B3 liveInjected=True را می‌خواند)؛
        # این‌جا فقط سنجیده می‌شود که دو طرف یک رأی می‌دهند.
        if body.get("liveInjected") is not False or body.get("liveError") is not None:
            problems.append("chart-db-watch liveInjected=%r liveError=%r"
                            % (body.get("liveInjected"), body.get("liveError")))
    path = want("chart-db-events")
    if path:
        body = engine.get_json(py_url + path)[1]
        if not body.get("adjustEvents"):
            problems.append("chart-db-events adjustEvents empty")
    path = want("fts-deep")
    if path:
        body = engine.get_json(py_url + path)[1]
        if body.get("status") != "success" or not body.get("bars"):
            problems.append("fts-deep status=%r bars=%r" % (body.get("status"), body.get("bars")))
        if body.get("trend_engine") != "legacy":
            problems.append("fts-deep trend_engine=%r" % body.get("trend_engine"))
    path = want("fts-asof")
    if path:
        body = engine.get_json(py_url + path)[1]
        live = engine.get_json(py_url + by_name["fts-deep"])[1] if want("fts-deep") else {}
        want_date = urllib.parse.unquote(path.split("as_of=")[1])
        if body.get("as_of") != want_date:
            problems.append("fts-asof echo=%r want=%r" % (body.get("as_of"), want_date))
        elif live and not (0 < (body.get("bars") or 0) < (live.get("bars") or 0)):
            problems.append("fts-asof bars=%r vs live=%r (cutoff did not cut)"
                            % (body.get("bars"), live.get("bars")))
    path = want("order-book-book")
    if path:
        body = engine.get_json(py_url + path)[1]
        if body.get("status") != "ok":
            problems.append("order-book-book status=%r" % body.get("status"))
    path = want("calendar-symbol")
    if path:
        body = engine.get_json(py_url + path)[1]
        if not body.get("events"):
            problems.append("calendar-symbol events empty")
    # تقویمِ ماشین درِ ۲۰۶-۰۹-۲۷ واکشی شده و افقِ ۶۰ روزهٔ امروز خالی است؛
    # کیسِ upcoming پس با «تهی بودنِ هر دو طرف» سبز می‌شود، پس شکلِ پاسخ را
    # می‌سنجیم (daysِ اکو‌شده و هر دو فهرست) تا مسیرِ خالی با مسیرِ شکسته یکی
    # نشود؛ شمارشِ رویداد درِ فیکسچر (calendar_upcoming count=3) اثبات شده است.
    # _clamp_days افق را در [۱، ۹۰] نگه می‌دارد: days=0 درِ پاسخ ۱ می‌شود.
    for name, days in (("calendar-upcoming-14", 14), ("calendar-upcoming-60", 60),
                       ("calendar-upcoming-zero", 1)):
        path = want(name)
        if not path:
            continue
        body = engine.get_json(py_url + path)[1]
        if body.get("days") != days or "items" not in body or "capital" not in body:
            problems.append("%s shape=%r" % (name, list(body)[:8]))
    return problems


def fts_config_declared(py_url, go_url):
    """`GET /api/fts/config` مال api/market.py است و در B7 می‌ماند؛ پایتون ۲۰۰
    می‌دهد و Go ۵۰۱. مسیرهایِ عامِ Go نباید این را «نمادِ config» بخوانند."""
    py_status, py_body = engine.get_json(py_url + "/api/fts/config")
    go_status, go_body = engine.get_json(go_url + "/api/fts/config")
    ok = (go_status == 501 and go_body.get("code") == "NOT_PORTED"
          and go_body.get("route") == "GET /api/fts/config" and py_status == 200)
    return ok, {"py": py_status, "go": go_status, "go_code": go_body.get("code"),
                "go_route": go_body.get("route"),
                "py_keys": sorted(py_body)[:6] if isinstance(py_body, dict) else []}


def chart_declared(py_url, go_url, symbol):
    """پایتون ۲۰۰ (یا بدنهٔ خطای محلی) و Go ۵۰۱ — اندازه‌گیری، نه فرض."""
    py_status, py_body = engine.get_json(py_url + "/api/chart/" +
                                         urllib.parse.quote(symbol, safe=""))
    go_status, go_body = engine.get_json(go_url + "/api/chart/" +
                                         urllib.parse.quote(symbol, safe=""))
    # دو مدرکِ داخلِ همان پاسخ ثابت می‌کنند پایتون از CDN نیامده: پرچمِ
    # «منبعِ جایگزین» و خاموش بودنِ ترمیمِ پس‌زمینه — هر دو فقط درِ فال‌بکِ محلی
    # (و با BORS_CHART_CDN=off) نوشته می‌شوند.
    seam = (py_body.get("degraded") is True
            and py_body.get("historyRepairScheduled") is False)
    ok = (go_status == 501 and go_body.get("code") == "NOT_PORTED"
          and py_status == 200 and py_body.get("status") == "success" and seam)
    return ok, {"py": py_status, "go": go_status, "go_code": go_body.get("code"),
                "py_status_field": py_body.get("status"),
                "py_degraded": py_body.get("degraded"),
                "py_history_repair_scheduled": py_body.get("historyRepairScheduled"),
                "cdn_seam_proven": seam, "symbol": symbol}


def seed_basket(go_dir, py_dir, roles_holder):
    """یک ردیفِ accept درِ user.dbِ هر دو کپی، با قیمتی که از کفِ ساختاریِ همان
    نماد بالاتر است. بی‌این، گیتِ زنده هرگز entry_hint را به موتور نمی‌داد."""
    roles = roles_holder[0] if roles_holder else {}
    symbol = (roles.get("deep") or "").strip()
    if not symbol:
        return {"ok": False, "why": "no deep symbol"}
    ph = os.path.join(go_dir, "market.db")
    con = sqlite3.connect("file:%s?mode=ro" % ph.replace("\\", "/"), uri=True)
    try:
        row = con.execute("SELECT MAX(close) FROM price_history WHERE symbol = ?",
                          (symbol,)).fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        return {"ok": False, "why": "no close history for %s" % symbol}
    price = round(float(row[0]) * 1.4, 2)
    for d in (go_dir, py_dir):
        c = sqlite3.connect(os.path.join(d, "user.db"))
        try:
            c.execute("INSERT OR REPLACE INTO selection_decisions(symbol, status, price) "
                      "VALUES (?, 'accept', ?)", (symbol, price))
            c.commit()
        finally:
            c.close()
    return {"ok": True, "symbol": symbol, "price": price,
            "hard_stop_expected": round(price * 0.95, 2)}


def dump_logs(tmp):
    engine.dump_logs(tmp)


def main() -> int:
    os.makedirs(os.path.join(base.GO, "bin"), exist_ok=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    root_before = engine.root_fingerprint()
    if root_before["market.db"] is None:
        print("operational market.db is missing; nothing to freeze")
        return 2

    for target, out in (("./cmd/borsd", base.BORSD), ("./cmd/parity", base.PARITY)):
        rc, log = base.run(["go", "build", "-o", out, target], cwd=base.GO)
        if rc != 0:
            print(log)
            return 2
    rc, tests = base.run(["go", "test", "-count=1", "./..."], cwd=base.GO)
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
    tmp = tempfile.mkdtemp(prefix="bors-b3-")
    go_dir, py_dir = os.path.join(tmp, "go"), os.path.join(tmp, "py")
    os.makedirs(go_dir)
    os.makedirs(py_dir)
    procs = []
    roles_holder = [{}]
    result, frozen_ok = 2, False
    try:
        for name in base.DB_NAMES:
            src = os.path.join(ROOT, name)
            if not os.path.exists(src):
                continue
            for dst_dir in (go_dir, py_dir):
                try:
                    check = base.snapshot_db(src, os.path.join(dst_dir, name))
                except Exception as err:                                    # noqa: BLE001
                    print("snapshot copy unusable: %s: %s" % (name, err))
                    return 2
                if check != ["ok"]:
                    print("quick_check failed for %s copy: %s" % (name, check))
                    return 2
        go_db = os.path.join(go_dir, "market.db")
        db_prints = base.db_fingerprint(go_db)
        if db_prints != base.db_fingerprint(os.path.join(py_dir, "market.db")):
            print("the two copies are not identical")
            return 2
        # تنظیماتِ واقعیِ اپ به هر دو کپی؛ بی‌این یک طرف closing و طرف دیگر last
        # می‌خواند و اختلافِ ساختگی از همان کیسِ چارت‌دب بلند می‌شد.
        settings_copied = []
        for name in SETTINGS:
            src = os.path.join(ROOT, name)
            if not os.path.exists(src):
                continue
            for dst_dir in (go_dir, py_dir):
                shutil.copy2(src, os.path.join(dst_dir, name))
            settings_copied.append(name)
        calendar_shared = os.path.exists(CALENDAR)
        frozen_ok = True

        # seed_basket: کاربرِ این ماشین هنوز هیچ ردیفی درِ سبد ندارد (سنجیده شد:
        # selection_decisions خالی است)، پس شاخهٔ entry_hint درِ گیت زنده هیچ‌وقت
        # صدا نمی‌زد — همان‌جا که بازبینی بلوکر را گرفت. یک ردیفِ accept با قیمتی
        # بالای کفِ ساختاری درِ **هر دو** کپی می‌نشینیم تا ورودی یکی باشد.
        with open(CASES, encoding="utf-8") as f:
            spec = json.load(f)
        roles = read_roles(go_db, spec["roles"])
        roles["cal"] = calendar_symbol(CALENDAR, roles) if calendar_shared else None
        calendar_meta = None
        try:
            with open(CALENDAR, encoding="utf-8") as f:
                calendar_meta = ((json.load(f).get("meta") or {}).get("fetchedAt"))
        except (OSError, ValueError, AttributeError):
            calendar_meta = None
        roles_holder[:] = [roles]
        basket = seed_basket(go_dir, py_dir, roles_holder)

        env_common = {"BORS_CALENDAR_PATH": CALENDAR if calendar_shared else "",
                      "BORS_CHART_CDN": "off", "PYTHONIOENCODING": "utf-8"}
        py_env = dict(os.environ, BORS_DATA_DIR=py_dir, BORS_NO_FETCH_LOOPS="1",
                      BORS_CODAL_OFFLINE="1", BORS_CODAL_AUTO="0",
                      BORS_PARITY_PORT=str(py_port), **{k: v for k, v in env_common.items() if v})
        ok_redirect, redirect_paths = engine.python_redirect_ok(py_dir, py_env)
        if not ok_redirect:
            return 2

        py_log = open(os.path.join(tmp, "py.log"), "w", encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, base.SERVE], cwd=ROOT, env=py_env,
                                       stdout=py_log, stderr=subprocess.STDOUT), py_log))
        if not base.wait_json("http://127.0.0.1:%d/openapi.json" % py_port, 60.0, lambda b: True):
            print("python server did not become ready")
            return 2

        go_env = dict(os.environ, **{k: v for k, v in env_common.items() if v})
        go_log = open(os.path.join(tmp, "go.log"), "w", encoding="utf-8")
        go_proc = subprocess.Popen(
            [base.BORSD, "--port", str(go_port), "--read-only", "--no-loops",
             "--db-dir", go_dir], cwd=ROOT, env=go_env,
            stdout=go_log, stderr=subprocess.STDOUT)
        procs.append((go_proc, go_log))
        if not base.wait_json("http://127.0.0.1:%d/healthz" % go_port, 15.0,
                              lambda b: b.get("status") == "ok"):
            print("go server did not become ready")
            return 2
        _, _, health_body = base.http_get("http://127.0.0.1:%d/healthz" % go_port)
        if os.path.normcase(os.path.normpath(json.loads(health_body).get("data_dir", ""))) \
                != os.path.normcase(os.path.normpath(go_dir)):
            print("healthz is not from this gate's server")
            return 2

        py_url = "http://127.0.0.1:%d" % py_port
        go_url = "http://127.0.0.1:%d" % go_port

        cases, dropped = build_cases(spec, roles)
        if not cases:
            print("no case could be built from %s" % CASES)
            return 2

        # db_sha256 از همان کپیِ یخ‌زده تزریق می‌شود (پینِ دستی نیست): شاهدِ این
        # فایل لاگِ اجراست، نه مدرکِ بازسازی‌شدنی — bank هر روز عوض می‌شود.
        payload_cases = {"db_sha256": db_prints["market.db"], "cases": cases}
        dynamic = os.path.join(tmp, "cases_b3_run.json")
        with open(dynamic, "w", encoding="utf-8") as f:
            json.dump(payload_cases, f, ensure_ascii=False)

        rc, log = base.run([base.PARITY, "--py", py_url, "--go", go_url,
                            "--cases", dynamic, "--db", go_db,
                            "--out", CONTRACT, "--commit", commit])
        print(log.strip())
        if rc == 2:
            print("contract batch could not run")
            return 2
        with open(CONTRACT, encoding="utf-8") as f:
            contract = json.load(f)
        case_count = len(cases)
        contract_ok = contract["failed"] == 0 and contract["passed"] == case_count
        max_delta = max([c.get("max_delta") or 0.0 for c in contract["cases"]] or [0.0])
        pairs = [(c.get("status_py"), c.get("status_go")) for c in contract["cases"]]
        allowed = {(200, 200), (422, 422)}
        expect_422 = {c["name"] for c in cases if c["name"].endswith("-422")}
        got_422 = {c["name"] for c in contract["cases"]
                   if (c.get("status_py"), c.get("status_go")) == (422, 422)}
        statuses_ok = (bool(pairs) and all(p in allowed for p in pairs)
                       and got_422 == expect_422)
        wanted = sorted(c["name"] for c in cases)
        ran = sorted(c["name"] for c in contract["cases"])
        coverage_ok = wanted == ran
        failed_cases = [{"name": c["name"], "diffs": c.get("diffs") or []}
                        for c in contract["cases"] if not c.get("pass")]

        vacuous = content_checks(py_url, cases) + basket_check(py_url, cases, basket)
        chart_ok, chart_meas = (False, {})
        if roles.get("deep"):
            chart_ok, chart_meas = chart_declared(py_url, go_url, roles["deep"])
        cfg_ok, cfg_meas = fts_config_declared(py_url, go_url)

        base.stop(procs)
        go_db_unchanged = base.db_fingerprint(go_db) == db_prints
        root_after = engine.root_fingerprint()
        root_untouched = root_before == root_after
        sidecar_problem = base.sidecar_problem(before_sidecars, base.sidecar_state())

        routes = sorted({(c["path"].split("?")[0].split("/api/")[1].split("/")[0])
                         for c in cases})
        covered = {template_of(c["path"]) for c in cases}
        if chart_ok:
            covered.add("/api/chart/{symbol}")
        missing_routes = sorted(B3_ROUTES - covered)
        checks = {
            "contract": contract_ok, "delta_zero": max_delta == 0.0,
            "statuses_200_422": statuses_ok, "case_coverage": coverage_ok,
            "cases_not_vacuous": not vacuous,
            "nine_routes_covered": not missing_routes,
            "chart_501_declared": chart_ok, "fts_config_501_declared": cfg_ok,
            "cdn_seam_proven": chart_meas.get("cdn_seam_proven", False),
            "go_read_only": go_db_unchanged, "root_untouched": root_untouched,
            "frozen_copies": frozen_ok,
            "sidecar_untouched": not sidecar_problem,
            "settings_shared": sorted(settings_copied) == sorted(SETTINGS),
            "calendar_shared": calendar_shared,
            "roles_resolved": all(roles.get(k) for k in ("deep", "short", "absent")),
        }
        payload = {
            "commit": commit, "python": sys.version.split()[0],
            "ports": {"py": py_port, "go": go_port, "preferred_py": PY_PORT,
                      "preferred_go": GO_PORT, "fell_back": fell_back},
            "chart_cdn": "off (forced on the child process; proven by cdn_seam_proven)",
            "routes": routes,
            "notes": {
                "watch_injection": "market_watch of this copy is older than price_history, "
                                   "so the live-bar branch is proven by the fixture oracle "
                                   "(chartdb_* liveInjected=true), not by this copy",
                "calendar_horizon": "calendar cache fetched %s; the 14/60-day windows are "
                                    "empty on both sides"
                                    % (calendar_meta or "unknown"),
            },
            "roles": roles, "dropped_cases": dropped, "basket_seed": basket,
            "routes_covered": sorted(covered), "routes_missing": missing_routes,
            "db": {"sha256": db_prints["market.db"], "wal_sha256": db_prints.get("market.db-wal"),
                   "frozen_ok": frozen_ok, "go_copy_unchanged": go_db_unchanged,
                   "root_before": root_before, "root_after": root_after,
                   "root_untouched": root_untouched},
            "sidecar": {"ok": not sidecar_problem, "problem": sidecar_problem or ""},
            "settings": {"copied": settings_copied, "calendar": CALENDAR,
                         "calendar_shared": calendar_shared},
            "python_redirect": redirect_paths,
            "contract": {"passed": contract["passed"], "failed": contract["failed"],
                         "cases": case_count, "max_delta": max_delta,
                         "report": os.path.relpath(CONTRACT, ROOT), "ok": contract_ok,
                         "failed_cases": failed_cases},
            "statuses": {"pairs": sorted("%s/%s" % p for p in set(pairs)),
                         "count_422": sum(1 for p in pairs if p == (422, 422)),
                         "ok": statuses_ok},
            "vacuous": vacuous, "chart_endpoint": chart_meas,
            "fts_config_endpoint": cfg_meas,
            "checks": checks,
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("checks: " + " ".join("%s=%s" % kv for kv in checks.items()))
        print("contract %d/%d | max_delta=%s | routes=%s | covered=%d/9 | roles=%s | dropped=%d"
              % (contract["passed"], case_count, max_delta, ",".join(routes),
                 len(covered), ",".join(sorted(k for k, v in roles.items() if v)),
                 len(dropped)))
        if missing_routes:
            print("MISSING ROUTE COVERAGE: %s" % missing_routes)
        for row in failed_cases:
            print("FAILED %s: %s" % (row["name"], "; ".join(row["diffs"][:4])))
        for v in vacuous:
            print("VACUOUS %s" % v)
        result = 0 if all(checks.values()) else 1
    finally:
        base.stop(procs)
        problem = base.sidecar_problem(before_sidecars, base.sidecar_state())
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
