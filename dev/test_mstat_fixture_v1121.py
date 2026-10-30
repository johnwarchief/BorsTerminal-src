#!/usr/bin/env python
"""گاردِ فیکسچر/طلاییِ B2 — پنج بررسی، بی‌شبکه.

۱) فیکسچر قطعی است: دو ساختِ مستقل در دو پوشۀ موقت، همان sha256، و همان
   فیکسچرِ کامیت‌شده. گارد هرگز فیکسچرِ ردیابی‌شده را بازنویسی نمی‌کند؛
   وگرنه یک سازندۀ ناقطعی با یک بازنویسی «سبز» می‌شد.
۲) طلایی‌ها با اجرایِ تازۀ اوراکل یکی‌اند.
۳) هر پنلِ سند در s1 حاضر است، خالی نیست (هر مسیر شرطِ محتوای خودش را دارد)
   و mainwatch دقیقاً جفت‌هایِ پرچمِ موردانتظار را True می‌دهد.
۴) شمارشِ سناریوها همان چهار صحنه است و درختِ طلایی فقط همان‌ها را دارد.
۵) رفتارِ صحنه‌ها با مقدارِ دقیق سنجیده می‌شود (نه «هر مقدارِ متفاوت»).

هرگز `market.db`/`user.db`ِ عملیاتیِ ریشه باز نمی‌شود: فیکسچر از نو ساخته
می‌شود و اوراکل در پوشۀ موقت می‌نویسد (همان الگویِ گاردِ B1).
"""
import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARITY = os.path.join(ROOT, "tools", "parity")
FIX = os.path.join(ROOT, "backend-go", "internal", "mstat", "testdata", "fixture")
GOLD = os.path.join(ROOT, "backend-go", "internal", "mstat", "testdata", "golden")
ROUTES = ["summary", "histogram_all", "histogram_eq_all", "thermometer_all",
          "thermometer_eq_all", "depth_all", "depth_eq_all", "clientsplit_all",
          "clientsplit_fixed", "market_snapshot", "phase", "industries",
          "timeline_cum", "timeline_inst", "phases", "mainwatch_default",
          "mainwatch_val"]
# همان چیزی که تسک می‌خواهد: s1 هفده پنل، s2 دو فایل، s3 و s4 هرکدام یکی.
SCENARIOS = {"s1": set(ROUTES),
             "s2": {"timeline_cum", "phases"},
             "s3": {"phase"},
             "s4": {"phase"}}
PIN_CLOCK = "2026-10-28 10:30:00"
# جفت‌هایِ (ins_code، نامِ پرچم) که طلاییِ s1 باید True بدهد. دو پرچمِ متفاوت
# عمدی‌اند تا پورتِ Go با «همه False» یا با سخت‌کدِ یک پرچم سبز نشود.
EXPECTED_FLAGS = {("m1", "f_noqteh"), ("m1", "f_susp")}
PREV_MARKET_DAY = 20261013
ENV_KEYS = ("BORS_DATA_DIR", "BORS_NO_FETCH_LOOPS", "BORS_CODAL_OFFLINE",
            "BORS_CODAL_AUTO")

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


def build_fixture(dest):
    """فیکسچر را در `dest` می‌سازد؛ فیکسچرِ ردیابی‌شده دست نمی‌خورد."""
    mod = load("mstat_fixture_build", "make_mstat_fixture.py")
    mod.OUT = dest
    os.makedirs(dest, exist_ok=True)
    with redirect_stdout(io.StringIO()):
        return mod.main()


def panel_content(name, d):
    """شرطِ «خالی نبودن»ِ همان مسیر — نه فقط `status == ok`.

    بدنه‌ای با `status: ok` و هیستوگرام/عمق/تقسیمِ مشتریانِ تهی، یا خلاصه‌ای
    که فقط ردیفِ `bonds_other` عدد دارد، نباید سبز شود. هر شرط از خودِ همان
    شمارنده/آرایه‌ای می‌آید که پنل باید پر کند.
    """
    if name.startswith("histogram_"):
        n = d.get("known") or 0
        return n > 0, "known=%r" % d.get("known")
    if name.startswith("thermometer_"):
        n = sum(d.get(k) or 0 for k in ("positive", "negative", "zero"))
        return n > 0, "positive+negative+zero=%d" % n
    if name.startswith("depth_"):
        n = d.get("symbols_with_depth") or 0
        return n > 0, "symbols_with_depth=%r" % d.get("symbols_with_depth")
    if name.startswith("clientsplit_"):
        n = d.get("symbols") or 0
        return n > 0, "symbols=%r" % d.get("symbols")
    if name == "market_snapshot":
        has_index = d.get("index") is not None
        has_prev = d.get("prev") is not None
        return has_index and has_prev, "index_present=%s prev_present=%s" % (
            has_index, has_prev)
    if name == "phase":
        return bool(d.get("phase")), "phase=%r" % d.get("phase")
    if name == "industries":
        n = len(d.get("rows") or [])
        return n > 0, "rows=%d" % n
    if name.startswith("timeline_"):
        n = d.get("points") or 0
        return n > 0, "points=%r" % d.get("points")
    if name == "phases":
        red = len(d.get("red") or [])
        green = len(d.get("green") or [])
        return red > 0 and green > 0, "red=%d green=%d" % (red, green)
    if name.startswith("mainwatch_"):
        n = len(d.get("rows") or [])
        return n > 0, "rows=%d" % n
    if name == "summary":
        n = len(d.get("rows") or [])
        return n > 0, "rows=%d" % n
    return False, "no content predicate for %r" % name


def main() -> int:
    # ۱) قطعیتِ فیکسچر — دو ساختِ مستقل در دو پوشۀ موقت؛ هیچ نوشتنی رویِ
    #    فیکسچرِ ردیابی‌شده، و مقایسه با همان فایلِ کامیت‌شده.
    try:
        with tempfile.TemporaryDirectory(prefix="b2-fix-a-") as a, \
                tempfile.TemporaryDirectory(prefix="b2-fix-b-") as b:
            rcs = (build_fixture(a), build_fixture(b))
            fresh = [{n: sha(os.path.join(root, n))
                      for n in ("market.db", "user.db")} for root in (a, b)]
        committed = {n: sha(os.path.join(FIX, n))
                     for n in ("market.db", "user.db")}
        check("fixture build is deterministic (two temp builds, same sha256)",
              rcs == (0, 0) and fresh[0] == fresh[1],
              "rc=%r a=%s b=%s" % (rcs, fresh[0], fresh[1]))
        check("committed fixture equals a fresh build", fresh[0] == committed,
              "fresh=%s committed=%s" % (fresh[0], committed))
        check("user.db is the empty B1 database",
              os.path.getsize(os.path.join(FIX, "user.db")) == 0,
              "size=%d" % os.path.getsize(os.path.join(FIX, "user.db")))
    except Exception as e:                                        # noqa: BLE001
        for label in ("fixture build is deterministic (two temp builds, same sha256)",
                      "committed fixture equals a fresh build",
                      "user.db is the empty B1 database"):
            check(label, False, repr(e))

    # ۲) طلایی‌ها — اوراکل در پوشۀ موقت اجرا می‌شود و خروجیِ کامیت‌شده با آن
    #    مقایسه می‌شود (پارس‌شده؛ ترتیبِ کلید داور نیست). پوشۀ کامیت‌شده
    #    دست‌نخورده می‌ماند تا «طلاییِ دست‌ویرایش‌شده» لو برود.
    saved = {k: os.environ.get(k) for k in ENV_KEYS}
    try:
        gg = load("mstat_golden_gen", "gen_mstat_golden.py")
        with tempfile.TemporaryDirectory(prefix="b2-golden-check-") as tmp:
            gg.OUT = tmp
            with redirect_stdout(io.StringIO()):
                gg.main()
            mismatches, checked = [], 0
            for scen, stems in sorted(SCENARIOS.items()):
                fresh_dir = os.path.join(tmp, scen)
                have = sorted(n[:-5] for n in os.listdir(fresh_dir)) if os.path.isdir(fresh_dir) else []
                if set(have) != stems:
                    mismatches.append("%s: files %s" % (scen, have))
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

    # ۳) هر پنلِ سند در s1 حاضر است، status دارد و بدنه‌اش خالی نیست.
    for name in ROUTES:
        p = os.path.join(GOLD, "s1", name + ".json")
        if not os.path.exists(p):
            check("s1/" + name + " status ok", False, "missing")
            check("s1/" + name + " has content", False, "missing")
            continue
        d = read_json(p)
        ok = isinstance(d, dict) and d.get("status") == "ok"
        check("s1/" + name + " status ok", ok,
              "status=%r" % (d.get("status") if isinstance(d, dict) else None))
        if isinstance(d, dict):
            filled, detail = panel_content(name, d)
        else:
            filled, detail = False, "body is not an object"
        check("s1/" + name + " has content", filled, detail)
    try:
        s = read_json(os.path.join(GOLD, "s1", "summary.json"))
        check("summary has the ten category rows", len(s.get("rows") or []) == 10,
              "count=%d" % len(s.get("rows") or []))
        rows = s.get("rows") or []
        eq_all = next((r for r in rows if r.get("key") == "eq_all"), None)
        check("summary eq_all row has symbols > 0",
              bool(eq_all) and (eq_all.get("symbols") or 0) > 0,
              "eq_all=%r" % (eq_all,))
        check("phase clock is the pinned instant",
              (s.get("phase") or {}).get("clock_now") == PIN_CLOCK,
              "clock_now=%r" % (s.get("phase") or {}).get("clock_now"))
        snap = read_json(os.path.join(GOLD, "s1", "market_snapshot.json"))
        prev = snap.get("prev")
        check("market_snapshot previous session is a real object",
              isinstance(prev, dict) and prev.get("d_even") == PREV_MARKET_DAY,
              "prev=%r" % (prev,))
        mw = read_json(os.path.join(GOLD, "s1", "mainwatch_default.json"))
        check("mainwatch tape flags came from api/market",
              mw.get("tape_flags_source") == "api/market",
              "source=%r" % mw.get("tape_flags_source"))
        # پوششِ پرچم: مجموعهٔ دقیقِ (نماد، پرچم) قفل می‌شود تا اگر روزی یکی گم
        # شود، FAIL نامِ همان جفت را بگوید — نه «همه False» یا «یک True کافی است».
        heat = set()
        for stem in ("mainwatch_default", "mainwatch_val"):
            body = read_json(os.path.join(GOLD, "s1", stem + ".json"))
            for r in body.get("rows") or []:
                for k, v in (r.get("tape_flags") or {}).items():
                    if v is True:
                        heat.add((r.get("ins_code"), k))
        print("  INFO tape flag coverage: " + (
            ", ".join("%s@%s" % (flag, ic) for ic, flag in sorted(heat))
            if heat else "none"))
        missing = sorted(EXPECTED_FLAGS - heat)
        unexpected = sorted(heat - EXPECTED_FLAGS)
        check("mainwatch TRUE tape flags are exactly the expected pairs",
              heat == EXPECTED_FLAGS,
              "missing=%s unexpected=%s" % (missing, unexpected))
        tl = read_json(os.path.join(GOLD, "s1", "timeline_cum.json"))
        check("timeline has every point", (tl.get("points") or 0) == 3,
              "points=%r" % tl.get("points"))
    except Exception as e:                                        # noqa: BLE001
        check("s1 panel bodies are readable", False, repr(e))

    # ۴) شمارشِ سناریوها — همان چهار صحنه، با همان فهرستِ فایل، و رفتارشان.
    try:
        for scen, stems in sorted(SCENARIOS.items()):
            d = os.path.join(GOLD, scen)
            have = set(os.listdir(d)) if os.path.isdir(d) else set()
            want = {stem + ".json" for stem in stems}
            check("%s holds exactly %d golden(s)" % (scen, len(stems)), have == want,
                  "have=%s" % sorted(have))
        entries = set(os.listdir(GOLD))
        check("golden tree holds only s1..s4 (files and dirs)",
              entries == set(SCENARIOS), "have=%s" % sorted(entries))
        s2 = read_json(os.path.join(GOLD, "s2", "timeline_cum.json"))
        check("s2 timeline is marked stale", s2.get("stale") is True,
              "stale=%r" % s2.get("stale"))
        check("s2 timeline day is the previous session",
              s2.get("board_day") == 20261014
              and s2.get("day") == (s2.get("board_day") or 0) - 1,
              "day=%r board_day=%r" % (s2.get("day"), s2.get("board_day")))
        s3 = read_json(os.path.join(GOLD, "s3", "phase.json"))
        check("s3 phase is unknown from the calendar",
              s3.get("phase") == "unknown" and s3.get("phase_source") == "none",
              "phase=%r source=%r" % (s3.get("phase"), s3.get("phase_source")))
        s4 = read_json(os.path.join(GOLD, "s4", "phase.json"))
        check("s4 phase is holiday from the official state",
              s4.get("phase") == "holiday"
              and s4.get("phase_source") == "tsetmc_marketState"
              and s4.get("official") is True,
              "phase=%r source=%r official=%r" % (
                  s4.get("phase"), s4.get("phase_source"), s4.get("official")))
    except Exception as e:                                        # noqa: BLE001
        check("scenario count", False, repr(e))

    print("mstat_fixture_v1121: %d failed" % FAIL)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
