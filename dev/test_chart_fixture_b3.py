#!/usr/bin/env python
"""گاردِ فیکسچر/طلاییِ B3 — بی‌شبکه، بی‌دست‌زدن به بانکِ عملیاتیِ ریشه.

شش بررسی:
۱) فیکسچر قطعی است: دو ساختِ مستقل در دو پوشۀ موقت همان sha256 را می‌دهند و
   همان فایلِ کامیت‌شده است. گارد فیکسچرِ ردیابی‌شده را بازنویسی نمی‌کند.
۲) طلایی‌ها با اجرایِ تازهٔ اوراکل یکی‌اند (پارس‌شده؛ ترتیبِ کلید داور نیست).
۳) هر مسیرِ پورت‌شده در s1 بدنهٔ غیرخالی با شرطِ همان مسیر دارد: ۵ سطحِ سفارش،
   هندسهٔ کندلِ نمادِ تعدیل‌دار/صندوق/کوتاه‌تاریخ/بی‌داده، سه‌حالتیِ مبنا، برشِ
   `as_of` و سطح‌هایِ کلیدی.
۴) درختِ طلایی فقط صحنه‌هایِ s1..s4 را دارد.
۵) کنترلِ منفیِ درزها: بی `BORS_CHART_CDN` درخواستِ شبکه واقعاً صدا زده می‌شود؛
   با `off` هرگز؛ و `_schedule_history_repair` با درزِ بسته `False` می‌دهد.
۶) `BORS_CALENDAR_PATH` در نبودِ متغیر همان مسیرِ APP_DIR است.

هرگز `market.db`/`user.db`ِ عملیاتیِ ریشه باز نمی‌شود: فیکسچر از نو ساخته
می‌شود و اوراکل در پوشۀ موقت می‌نویسد (همان الگویِ گاردِ B1/B2).
"""
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARITY = os.path.join(ROOT, "tools", "parity")
FIX = os.path.join(ROOT, "backend-go", "internal", "chart", "testdata", "fixture")
GOLD = os.path.join(ROOT, "backend-go", "internal", "chart", "testdata", "golden")
ENV_KEYS = ("BORS_DATA_DIR", "BORS_CALENDAR_PATH", "BORS_CHART_CDN",
            "BORS_NO_FETCH_LOOPS", "BORS_CODAL_OFFLINE", "BORS_CODAL_AUTO")
SCENARIOS = {
    "s1": {"chartdb_uptrend", "chartdb_downtrend", "chartdb_fund",
           "chartdb_short", "chartdb_nodata", "chartdb_dualspell",
           "keylevels_uptrend", "keylevels_short", "keylevels_nodata",
           "ma_uptrend", "ma_downtrend", "ma_short",
           "patterns_uptrend", "patterns_short",
           "orderbook_five", "orderbook_null", "orderbook_missing",
           "calendar_symbol", "calendar_upcoming",
           "fts_uptrend", "fts_downtrend", "fts_short", "fts_nodata", "fts_asof"},
    "s2": {"orderbook_five", "orderbook_null"},
    "s3": {"fts_uptrend", "chartdb_uptrend"},
    "s4": {"keylevels_uptrend", "ma_uptrend", "patterns_uptrend",
           "chartdb_uptrend", "fts_uptrend"},
}
UP, DOWN, FUND, SHORT, NODATA = "عادی01", "پایین02", "اهرم‌ب", "کم‌سابقه11", "بی‌معامله04"

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + (" — " + detail if detail else ""))


def load(name, filename):
    path = os.path.join(PARITY, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_fixture(tmp):
    mf = load("chart_fixture_builder", "make_chart_fixture.py")
    with redirect_stdout(io.StringIO()):
        mf.build(tmp)
    return 0


def seam_probe(tmp_db):
    """در یک فرایندِ تازه: درزِ CDN و ترمیمِ تاریخچه را با کنترلِ منفی می‌سنجد."""
    code = r'''
import json, os, sys, types
sys.path.insert(0, sys.argv[1])
import bors_config as bc
import api.chart as ch
out = {"cal": bc._CAL_CACHE_PATH}
calls = {"get": 0}
class _Sess:
    def mount(self, *a, **k):
        pass
    def get(self, *a, **k):
        calls["get"] += 1
        raise RuntimeError("NETWORK BLOCKED")
fake = types.ModuleType("requests")
fake.Session = lambda: _Sess()
fake.adapters = types.SimpleNamespace(HTTPAdapter=lambda **k: None)
sys.modules["requests"] = fake
os.environ.pop("BORS_CHART_CDN", None)
out["enabled_default"] = ch._cdn_enabled()
r0 = ch.get_chart_tsetmc("بی‌معامله04")   # بی‌داده ⇒ فال‌بک نیست، همان خطایِ بیرونی
out["default_status"] = r0.get("status")
out["default_calls"] = calls["get"]
os.environ["BORS_CHART_CDN"] = "off"
ch.CHART_CACHE.clear()
calls["get"] = 0
out["enabled_off"] = ch._cdn_enabled()
r = ch.get_chart_tsetmc("پایین02")
out["off_calls"] = calls["get"]
out["off_status"] = r.get("status")
out["off_degraded"] = r.get("degraded")
out["repair_off"] = ch._schedule_history_repair("X", "2026-01-01", "2026-10-28")
print(json.dumps(out, ensure_ascii=False))
'''
    env = dict(os.environ, BORS_DATA_DIR=tmp_db,
               BORS_CALENDAR_PATH=os.path.join(tmp_db, "calendar", "cache.json"),
               BORS_CHART_CDN="", BORS_NO_FETCH_LOOPS="1",
               BORS_CODAL_OFFLINE="1", PYTHONIOENCODING="utf-8")
    env.pop("BORS_CHART_CDN", None)
    proc = subprocess.run([sys.executable, "-c", code, ROOT], env=env,
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout)[-800:]
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
    if not lines:
        return None, "probe printed no JSON: %r" % proc.stdout[-400:]
    return json.loads(lines[-1]), ""


def case_content(scen, name, d):
    """شرطِ محتوایِ هر کیس — «بدنه هست» کافی نیست؛ شاخهٔ نام‌دار باید دیده شود."""
    if not isinstance(d, dict):
        return False, "not an object"
    st = d.get("status")
    if name.startswith("chartdb_"):
        if st != "success":
            return False, "status=%r" % st
        want = {"chartdb_uptrend": 321, "chartdb_downtrend": 321, "chartdb_fund": 321,
                "chartdb_short": 41, "chartdb_nodata": 0, "chartdb_dualspell": 321}[name]
        if d.get("count") != want or len(d.get("candles") or []) != want:
            return False, "count=%r candles=%d want=%d" % (
                d.get("count"), len(d.get("candles") or []), want)
        if name == "chartdb_dualspell" and d.get("symbol") != "عادی 01":
            return False, "symbol=%r" % d.get("symbol")
        if name == "chartdb_uptrend":
            if not d.get("liveInjected") or d.get("liveError"):
                return False, "live bar not injected"
            if len(d.get("corporateEvents") or []) != 2:
                return False, "corporateEvents=%d" % len(d.get("corporateEvents") or [])
            if d.get("adjustSource") != "local-cache":
                return False, "adjustSource=%r" % d.get("adjustSource")
            if scen == "s4":
                if d.get("priceBasisRequested") != "closing" or d.get("priceBasisReason"):
                    return False, "s4 basis=%r/%r" % (
                        d.get("priceBasisRequested"), d.get("priceBasisReason"))
            elif d.get("priceBasisReason") != "last_missing:30/321":
                return False, "priceBasisReason=%r" % d.get("priceBasisReason")
            if not isinstance(d.get("fts"), dict) or d["fts"]["trend"]["D"]["trend"] != "up":
                return False, "fts/trend missing"
        if name == "chartdb_downtrend" and d.get("priceBasis") != "last":
            return False, "priceBasis=%r (last must apply)" % d.get("priceBasis")
        if name == "chartdb_fund" and not d.get("liveInjected"):
            return False, "live bar not injected"
        if name == "chartdb_nodata":
            if (d.get("fts") or {}).get("status", {}).get("code") != "insufficient":
                return False, "fts status=%r" % ((d.get("fts") or {}).get("status"),)
        return True, "count=%d" % d.get("count")
    if name.startswith("keylevels_"):
        if st != "ok":
            return False, "status=%r" % st
        want = 6 if name.endswith("uptrend") else 0
        if len(d.get("levels") or []) != want:
            return False, "levels=%d want=%d" % (len(d.get("levels") or []), want)
        return True, "levels=%d" % len(d.get("levels") or [])
    if name.startswith("ma_"):
        if st != "ok":
            return False, "status=%r" % st
        if sorted(d.get("ma") or {}) != ["ma120", "ma20", "ma5", "ma50"]:
            return False, "ma keys=%r" % sorted(d.get("ma") or {})
        if name == "ma_downtrend" and d["ma"]["ma120"][-1][1] is None:
            return False, "ma120 last is None"
        if name == "ma_short" and d["ma"]["ma120"][-1][1] is not None:
            return False, "ma120 last must stay None under 120 bars"
        return True, "bars=%d" % d.get("bars")
    if name.startswith("patterns_"):
        if st != "ok":
            return False, "status=%r" % st
        want = 9 if name.endswith("uptrend") else 0
        if len(d.get("overlays") or []) != want:
            return False, "overlays=%d want=%d" % (len(d.get("overlays") or []), want)
        if want:
            kinds = {o.get("kind") for o in d["overlays"]}
            if not {"trend-high", "trend-low", "breakout-zone"} <= kinds:
                return False, "kinds=%r" % sorted(kinds)
        return True, "overlays=%d" % len(d.get("overlays") or [])
    if name.startswith("orderbook_"):
        if name == "orderbook_five":
            if scen == "s2":
                return st == "no_data" and not (d.get("levels") or []), \
                    "s2 status=%r (table dropped)" % st
            if st != "ok" or len(d.get("levels") or []) != 5:
                return False, "status=%r levels=%d" % (st, len(d.get("levels") or []))
            if (d.get("session") or {}).get("d_even") != 20261028:
                return False, "session=%r" % (d.get("session"),)
            return True, "5 levels"
        ok = st == "no_data" and not (d.get("levels") or [])
        return ok, "status=%r" % st
    if name == "calendar_symbol":
        if st != "ok" or d.get("count") != 5:
            return False, "status=%r count=%r" % (st, d.get("count"))
        dates = [e.get("date") for e in d.get("events") or []]
        if dates != sorted(dates) or "2027-01-15" not in dates:
            return False, "dates=%r" % dates
        return True, "5 events (duplicate collapsed, horizon irrelevant here)"
    if name == "calendar_upcoming":
        if st != "ok" or d.get("count") != 3 or d.get("capital_count") != 2:
            return False, "count=%r capital=%r" % (d.get("count"), d.get("capital_count"))
        if not any(i.get("date_source") == "title" for i in d.get("items") or []):
            return False, "no title-dated item"
        if not any(i.get("cat") == "assemblyChange" for i in d.get("items") or []):
            return False, "cancelled assembly did not win the tie"
        return True, "3 assemblies + 2 capital increases"
    if name.startswith("fts_"):
        if name == "fts_nodata":
            return st == "empty" and d.get("fts") is None, "status=%r" % st
        if st != "success":
            return False, "status=%r" % st
        fts = d.get("fts") or {}
        if name == "fts_uptrend":
            t = (fts.get("trend") or {})
            if [t.get("D", {}).get("trend"), t.get("W", {}).get("trend"),
                    t.get("M", {}).get("trend")] != ["up", "up", "up"]:
                return False, "trends=%r" % (t,)
            if t.get("matrix", {}).get("decision") != "PERMITTED":
                return False, "matrix=%r" % (t.get("matrix"),)
            ex = fts.get("exit_engine") or {}
            if ex.get("verdict") != "hold" or ex.get("signals") != []:
                return False, "verdict=%r signals=%r" % (ex.get("verdict"), ex.get("signals"))
            if (ex.get("l1") or {}).get("stop_basis") != "swing_low" \
                    or (ex.get("l1") or {}).get("hard_stop") is None:
                return False, "l1=%r" % (ex.get("l1"),)
            if (fts.get("status") or {}).get("code") != "no_signal":
                return False, "status=%r" % (fts.get("status"),)
            if d.get("analysis_basis") != "local-db-adjusted":
                return False, "basis=%r" % d.get("analysis_basis")
            hg = fts.get("hourglass") or {}
            if scen == "s3":
                if (hg.get("rsi_period"), hg.get("rsi_oversold"),
                        hg.get("ma52_position_mode")) != (5, 40.0, "above"):
                    return False, "s3 hourglass=%r" % (hg,)
            elif hg.get("rsi_period") != 7:
                return False, "rsi_period=%r" % hg.get("rsi_period")
        if name == "fts_asof":
            if d.get("as_of") != "2026-09-01" or not 60 < (d.get("bars") or 0) < 321:
                return False, "as_of=%r bars=%r" % (d.get("as_of"), d.get("bars"))
        if name == "fts_short":
            if (fts.get("jet") or {}).get("active") is not None:
                return False, "jet must stay unmeasured"
            if (fts.get("hourglass") or {}).get("action") != "UNKNOWN":
                return False, "hourglass=%r" % (fts.get("hourglass"),)
        if name == "fts_downtrend":
            if (fts.get("trend") or {}).get("D", {}).get("trend") != "down":
                return False, "trend D=%r" % (fts.get("trend") or {}).get("D")
        return True, "bars=%r" % d.get("bars")
    return False, "no content predicate for %r" % name


def main() -> int:
    # ۱) قطعیتِ فیکسچر
    try:
        with tempfile.TemporaryDirectory(prefix="b3-fix-a-") as a, \
                tempfile.TemporaryDirectory(prefix="b3-fix-b-") as b:
            rcs = (build_fixture(a), build_fixture(b))
            names = ("market.db", "user.db", os.path.join("calendar", "cache.json"))
            fresh = [{n: sha(os.path.join(root, n)) for n in names} for root in (a, b)]
        committed = {n: sha(os.path.join(FIX, n)) for n in names}
        check("fixture build is deterministic (two temp builds, same sha256)",
              rcs == (0, 0) and fresh[0] == fresh[1], "rc=%r" % (rcs,))
        check("committed fixture equals a fresh build", fresh[0] == committed,
              "fresh=%s committed=%s" % (fresh[0], committed))
    except Exception as e:                                        # noqa: BLE001
        check("fixture build is deterministic (two temp builds, same sha256)", False, repr(e))
        check("committed fixture equals a fresh build", False, repr(e))

    # ۲) طلایی‌ها — اوراکل در پوشۀ موقت اجرا می‌شود، پوشۀ کامیت‌شده دست‌نخورده می‌ماند.
    saved = {k: os.environ.get(k) for k in ENV_KEYS}
    try:
        gg = load("chart_golden_gen", "gen_chart_golden.py")
        with tempfile.TemporaryDirectory(prefix="b3-golden-check-") as tmp:
            gg.OUT = tmp
            with redirect_stdout(io.StringIO()):
                gg.main()
            mismatches, checked = [], 0
            for scen, stems in sorted(SCENARIOS.items()):
                fresh_dir = os.path.join(tmp, scen)
                have = sorted(n[:-5] for n in os.listdir(fresh_dir)) \
                    if os.path.isdir(fresh_dir) else []
                if set(have) != stems:
                    mismatches.append("%s: files %s" % (scen, sorted(set(have) ^ stems)))
                    continue
                for stem in sorted(stems):
                    name = stem + ".json"
                    checked += 1
                    got = read_json(os.path.join(GOLD, scen, name)) \
                        if os.path.exists(os.path.join(GOLD, scen, name)) else None
                    want = read_json(os.path.join(fresh_dir, name))
                    if got != want:
                        mismatches.append("%s/%s" % (scen, name))
        check("goldens equal a fresh oracle run (parsed JSON, %d files)" % checked,
              not mismatches, "; ".join(mismatches[:6]))
    except Exception as e:                                        # noqa: BLE001
        check("goldens equal a fresh oracle run (parsed JSON)", False, repr(e))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # ۳) محتوایِ هر کیس
    for scen, stems in sorted(SCENARIOS.items()):
        for stem in sorted(stems):
            p = os.path.join(GOLD, scen, stem + ".json")
            if not os.path.exists(p):
                check("%s/%s has content" % (scen, stem), False, "missing")
                continue
            ok, detail = case_content(scen, stem, read_json(p))
            check("%s/%s has content" % (scen, stem), ok, detail)

    # ۴) درختِ طلایی فقط همین صحنه‌ها است
    try:
        dirs = sorted(d for d in os.listdir(GOLD)
                      if os.path.isdir(os.path.join(GOLD, d)))
        files = sorted(f for f in os.listdir(GOLD)
                       if os.path.isfile(os.path.join(GOLD, f)))
        check("golden tree holds only s1..s4 (files and dirs)",
              not files and set(dirs) == set(SCENARIOS), "dirs=%r files=%r" % (dirs, files))
    except Exception as e:                                        # noqa: BLE001
        check("golden tree holds only s1..s4 (files and dirs)", False, repr(e))

    # ۵) کنترلِ منفیِ درزها — در فرایندِ تازه تا ترتیبِ import واقعی باشد.
    try:
        with tempfile.TemporaryDirectory(prefix="b3-seam-") as tmp:
            build_fixture(tmp)
            probe, err = seam_probe(tmp)
        if probe is None:
            check("CDN seam negative control", False, err)
        else:
            check("default: requests is really called (negative control)",
                  probe["enabled_default"] is True and probe["default_calls"] == 1
                  and probe["default_status"] == "error", repr(probe))
            check("BORS_CHART_CDN=off: zero network calls, local fallback",
                  probe["enabled_off"] is False and probe["off_calls"] == 0
                  and probe["off_status"] == "success" and probe["off_degraded"] is True,
                  repr(probe))
            check("history repair is off behind the seam", probe["repair_off"] is False,
                  repr(probe.get("repair_off")))
            check("BORS_CALENDAR_PATH is honoured",
                  probe["cal"].replace("\\", "/").endswith("/calendar/cache.json"),
                  probe["cal"])
    except Exception as e:                                        # noqa: BLE001
        for label in ("CDN seam negative control",):
            check(label, False, repr(e))

    # ۶) مسیرِ پیش‌فرضِ تقویم بدونِ متغیر
    try:
        env = {k: v for k, v in os.environ.items() if k != "BORS_CALENDAR_PATH"}
        proc = subprocess.run(
            [sys.executable, "-c",
             "import sys,json;sys.path.insert(0,sys.argv[1]);"
             "import bors_config as b;print(json.dumps(b._CAL_CACHE_PATH))", ROOT],
            env=dict(env, PYTHONIOENCODING="utf-8"),
            capture_output=True, text=True, timeout=60)
        line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
        want = os.path.join(ROOT, "static", "calendar", "cache.json")
        check("without BORS_CALENDAR_PATH the APP_DIR path is used",
              proc.returncode == 0
              and json.loads(line).replace("\\", "/").endswith("/static/calendar/cache.json"),
              "%r want=%r" % (line, want))
    except Exception as e:                                        # noqa: BLE001
        check("without BORS_CALENDAR_PATH the APP_DIR path is used", False, repr(e))

    print("chart fixture guard: %d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
