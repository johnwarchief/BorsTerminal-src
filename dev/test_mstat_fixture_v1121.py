#!/usr/bin/env python
"""گاردِ فیکسچر/طلاییِ B2 — چهار بررسی، بی‌شبکه.

۱) فیکسچر قطعی است (دو ساخت، همان sha256).
۲) طلایی‌ها با اجرایِ تازۀ اوراکل یکی‌اند.
۳) هر پنلِ سند در s1 حاضر است و ردیف‌هایش خالی نیست — و `mainwatch` حداقل
   یک پرچمِ True دارد (طلاییِ همه‌False شاخهٔ زنده را از مرده جدا نمی‌کند).
۴) شمارشِ سناریوها همان چهار صحنه است.

هرگز `market.db`/`user.db`ِ عملیاتیِ ریشه باز نمی‌شود: فیکسچر از نو ساخته
می‌شود و اوراکل در پوشۀ موقت می‌نویسد (همان الگویِ گاردِ B1).
"""
import hashlib
import importlib.util
import io
import json
import os
import subprocess
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


def main() -> int:
    # ۱) قطعیتِ فیکسچر — دو ساختِ مستقل، همان بایت‌ها.
    try:
        before = {n: sha(os.path.join(FIX, n)) for n in ("market.db", "user.db")}
        subprocess.run([sys.executable, os.path.join(PARITY, "make_mstat_fixture.py")],
                       check=True, capture_output=True,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        after = {n: sha(os.path.join(FIX, n)) for n in ("market.db", "user.db")}
        check("fixture build is deterministic (same sha256)", before == after,
              "%s vs %s" % (before, after))
        check("user.db is the empty B1 database",
              os.path.getsize(os.path.join(FIX, "user.db")) == 0,
              "size=%d" % os.path.getsize(os.path.join(FIX, "user.db")))
    except Exception as e:                                        # noqa: BLE001
        check("fixture build is deterministic (same sha256)", False, repr(e))
        check("user.db is the empty B1 database", False, repr(e))

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

    # ۳) هر پنلِ سند در s1 حاضر است و ردیف‌هایش خالی نیست.
    for name in ROUTES:
        p = os.path.join(GOLD, "s1", name + ".json")
        if not os.path.exists(p):
            check("s1/" + name, False, "missing")
            continue
        d = read_json(p)
        ok = isinstance(d, dict) and d.get("status") == "ok"
        check("s1/" + name + " status ok", ok,
              "status=%r" % (d.get("status") if isinstance(d, dict) else None))
    try:
        s = read_json(os.path.join(GOLD, "s1", "summary.json"))
        check("summary has the ten category rows", len(s.get("rows") or []) == 10,
              "count=%d" % len(s.get("rows") or []))
        rows = s.get("rows") or []
        check("summary rows are not all empty",
              any((r.get("symbols") or 0) > 0 for r in rows))
        check("phase clock is the pinned instant",
              (s.get("phase") or {}).get("clock_now") == PIN_CLOCK,
              "clock_now=%r" % (s.get("phase") or {}).get("clock_now"))
        ind = read_json(os.path.join(GOLD, "s1", "industries.json"))
        check("industries is not empty", bool(ind.get("rows")))
        mw = read_json(os.path.join(GOLD, "s1", "mainwatch_default.json"))
        check("mainwatch rows are not empty", bool(mw.get("rows")),
              "rows=%d" % len(mw.get("rows") or []))
        check("mainwatch tape flags came from api/market",
              mw.get("tape_flags_source") == "api/market",
              "source=%r" % mw.get("tape_flags_source"))
        # پوششِ پرچم: طلایی‌ای که هر هفت پرچمش رویِ هر ردیف False باشد، شاخهٔ
        # زنده را از شاخهٔ مرده جدا نمی‌کند — پورتِ Go می‌تواند «همه False»
        # بدهد و همان طلایی را سبز کند. پس حداقل یک True واجب است، و نامِ
        # جفتِ پوشش‌داده هم قفل می‌شود تا اگر روزی گم شود، همین بررسی آن را
        # به نام صدا کند.
        heat = sorted((r.get("ins_code"), k)
                      for r in (mw.get("rows") or [])
                      for k, v in (r.get("tape_flags") or {}).items() if v is True)
        print("  INFO tape flag coverage: " + (
            ", ".join("%s@%s" % (k, ic) for ic, k in heat) if heat else "none"))
        check("mainwatch has a row with a TRUE tape flag", bool(heat),
              "all seven flags are false on all %d rows"
              % len(mw.get("rows") or []))
        check("tape flag f_susp is exercised on m1 (suspicious volume)",
              ("m1", "f_susp") in heat, "exercised=%r" % (heat,))
        tl = read_json(os.path.join(GOLD, "s1", "timeline_cum.json"))
        check("timeline has every point", (tl.get("points") or 0) == 3,
              "points=%r" % tl.get("points"))
    except Exception as e:                                        # noqa: BLE001
        check("s1 panel bodies are readable", False, repr(e))

    # ۴) شمارشِ سناریوها — همان چهار صحنه، با همان فهرستِ فایل، و رفتارشان.
    try:
        for scen, stems in sorted(SCENARIOS.items()):
            d = os.path.join(GOLD, scen)
            have = {n[:-5] for n in os.listdir(d) if n.endswith(".json")} \
                if os.path.isdir(d) else set()
            check("%s holds exactly %d golden(s)" % (scen, len(stems)), have == stems,
                  "have=%s" % sorted(have))
        extra = {n for n in os.listdir(GOLD) if os.path.isdir(os.path.join(GOLD, n))}
        check("golden tree holds only s1..s4", set(SCENARIOS) == extra,
              "have=%s" % sorted(extra))
        s2 = read_json(os.path.join(GOLD, "s2", "timeline_cum.json"))
        check("s2 timeline is marked stale", s2.get("stale") is True,
              "stale=%r" % s2.get("stale"))
        check("s2 timeline day is the previous session",
              s2.get("day") != s2.get("board_day"),
              "day=%r board_day=%r" % (s2.get("day"), s2.get("board_day")))
        check("s3 phase is unknown from the calendar",
              read_json(os.path.join(GOLD, "s3", "phase.json")).get("phase") == "unknown")
        check("s4 phase is holiday",
              read_json(os.path.join(GOLD, "s4", "phase.json")).get("phase") == "holiday")
    except Exception as e:                                        # noqa: BLE001
        check("scenario count", False, repr(e))

    print("mstat_fixture_v1121: %d failed" % FAIL)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
