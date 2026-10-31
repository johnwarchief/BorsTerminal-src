#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""گاردِ B4 — فیکسچر، اوراکل و طلایی‌هایِ بنیادی و نوار.

۱) فیکسچر قطعی است (دو build در دو پوشۀ موقت، هشِ یکسان) و با نسخۀ کامیت‌شده یکی است.
۲) هر طلایی با اجرایِ تازهٔ اوراکل برابر است (پارسِ JSON، نه رشته).
۳) هر کیس محتوایِ خودش را دارد: رأیِ پنج‌محور، سه‌حالۀ null/False، دورۀ فصلی،
   clampها، حالتِ صندوق، و روزهایِ نوار با placeholder — تا «Δ=۰ رویِ بدنهٔ تهی»
   سبز نشود.
۴) کنترلِ منفی: مرزِ «تاریخِ با خط تیره = بی‌دوره» واقعاً ردیف را از محاسبه
   بیرون می‌اندازد (سنسور باید نبود را هم ببیند).

اجرا: PYTHONIOENCODING=utf-8 python dev/test_fundamental_fixture_b4.py
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TOOLS = os.path.join(ROOT, "tools", "parity")
FIX = os.path.join(ROOT, "backend-go", "internal", "fundamental", "testdata", "fixture")
GOLD = os.path.join(ROOT, "backend-go", "internal", "fundamental", "testdata", "golden")
UP, DOWN, FUND, THIN, MIXED = "عادی01", "پایین02", "اهرم‌ب", "کم‌سابقه11", "متنوع01"

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS %s%s" % (name, (" — " + str(detail)) if detail else ""))
    else:
        FAIL += 1
        print("  FAIL %s%s" % (name, (" — " + str(detail)) if detail else ""))


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load(modname, filename):
    import importlib.util
    spec = importlib.util.spec_from_file_location(modname, os.path.join(TOOLS, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SCENARIOS = {
    "s1": {"fund_up", "fund_down", "fund_fund", "fund_thin", "fund_mixed",
           "fund_up_months6", "fund_unknown",
           "quarters_up", "quarters_mixed", "quarters_thin", "quarters_clamp_high",
           "quarters_clamp_zero", "quarters_negative", "quarters_missing", "sectors",
           "tape_four", "tape_all", "tape_one_day", "tape_clamp_days", "tape_zero_days",
           "tape_unknown_code", "tape_cap_codes"},
    "s2": {"fund_up", "fund_down", "fund_thin"},
    "s3": {"tape_missing_tables", "tape_empty_meta"},
}


def build_fixture(tmp):
    return subprocess.run([sys.executable, os.path.join(TOOLS, "make_fundamental_fixture.py"), tmp],
                          capture_output=True, text=True).returncode


def case_content(scen, name, d):
    def axis(f, key=None):
        ind = (d.get("indicators") or {}).get(f) or {}
        return ind if key is None else ind.get(key)

    if scen == "s3":
        return (d.get("status") == "success" and not (d.get("days") or [])
                and d.get("reliable_from") is None), "no tape tables ⇒ empty, not an error"
    if name == "sectors":
        rows = d.get("sectors") or []
        return (len(rows) >= 5 and rows == sorted(rows) and UP not in rows), "n=%d sorted" % len(rows)
    if name.startswith("quarters"):
        q = d.get("quarters") or []
        if name in ("quarters_up", "quarters_clamp_high"):
            # تاریخِ دوره درِ بانک با «/» است (CP.DATED_SQL همان را GLOB می‌کند)؛
            # خروجیِ ترمینال / را شبیهِ - نشان می‌دهد، پس این literal عمداً با
            # کدپوینت نوشته می‌شود تا دوباره از نمایشِ غلط کپی نشود.
            slash = chr(0x2F)
            want = "1405" + slash + "09" + slash + "30"
            return (d.get("count") == 7 and len(q) == 7
                    and q[0]["period_end"] == want and q[1]["period_months"] == 12), \
                "count=%r first=%r" % (d.get("count"), q[0]["period_end"])
        if name in ("quarters_clamp_zero", "quarters_negative"):
            return len(q) == 1, "clamp to 1 row: %d" % len(q)
        if name in ("quarters_mixed", "quarters_thin", "quarters_missing"):
            return q == [], "expected no dated quarter rows"
        return False, "no predicate"
    if name.startswith("tape"):
        if d.get("status") != "success":
            return False, "status=%r" % d.get("status")
        days = d.get("days") or []
        bs = d.get("by_symbol") or {}
        if name == "tape_all":
            return (len(days) == 4 and bs == {}), "codes='' ⇒ no symbols, days still listed"
        if name == "tape_one_day":
            return days == [20261028] and len(bs) == 1, "days=%r" % days
        if name in ("tape_clamp_days", "tape_zero_days"):
            return len(days) == 4 and bs, "clamp keeps the four watched days"
        if name == "tape_unknown_code":
            # کدِ ناشناخته هم هفت فیلتر را با چهار روزِ میخ‌کوبی برمی‌گرداند، همه
            # active:false — «ثبت نشد» با «غیرفعال» یکی نیست، و با نبودِ کلید هم نه.
            row = next(iter(bs.values()), {}) or {}
            return (len(row) == 7
                    and all(len((f or {}).get("days") or {}) == 4 for f in row.values())
                    and all(cell["active"] is False for f in row.values()
                            for cell in (f.get("days") or {}).values())), "symbols=%d flags=%d" % (len(bs), len(row))
        if name == "tape_cap_codes":
            return len(bs) == 1, "500 codes must collapse to the distinct set"
        if name == "tape_four":
            thin = bs.get(next((k for k in bs if "کم‌سابقه" in str(k)), "")) or {}
            four = len(bs) >= 3 and len(days) == 4
            gap_ok = True
            for sym, flags in bs.items():
                for flag, cell in (flags or {}).items():
                    if not cell.get("active") and not (cell.get("days") or {}):
                        gap_ok = gap_ok and flag in ("f_smart", "f_legal", "f_noqteh", "f_roobi", "f_susp")
            return four and gap_ok, "symbols=%d days=%d" % (len(bs), len(days))
        return False, "no predicate"
    if "__http_status__" in d:
        return (d.get("__http_status__") == 404 and "detail" in d), "404 shape kept"
    if d.get("status") != "success":
        return False, "status=%r" % d.get("status")
    st = d.get("states") or {}
    a1 = axis("1", "monetary")
    if scen == "s2":
        # سه قاعدۀ پرابِ آستانه، همه اندازه‌گرفته (نه از روی نام‌ها):
        #  ۱) `monetary_growth_min` درِ `no_v10_probe` است ⇒ کف از `growth_minِ`
        #     مشترک می‌آید (۷۰) و `v10_monetary_growth_min` به
        #     `monetary_growth_target` نگاشت می‌شود (۱۰)؛
        #  ۲) `cfg = dict(FTS_DEFAULTS)` آغاز می‌شود، پس هر `v10_*` که در
        #     پیش‌فرض‌ها هست، کلیدِ مشترکِ خودش را می‌پوشاند: نوشتنِ تنها
        #     `margin_min` رأیِ محور ۳ را تکان نمی‌دهد و باید `v10_margin_min`
        #     هم نوشته شود. این quirk همین‌جا پین می‌شود، نه در Go.
        thr = d.get("methodology", {}).get("thresholds", {})
        e3 = axis("3")
        base = (a1.get("threshold") == 70.0 and thr.get("monetary_growth_min") == 70.0
                and thr.get("monetary_growth_target") == 10.0
                and thr.get("margin_min") == 40.0 and e3.get("threshold") == 40.0)
        if name == "fund_up":
            # مرزِ رأی: حاشیۀ ۲۵٪ با کفِ ۲۰ می‌گرفت (s1) و با ۴۰ رد می‌شود
            return base and e3.get("pass") is False and st.get("3_gross_margin") is False, \
                "thr=%r e3pass=%r st3=%r" % (thr.get("margin_min"), e3.get("pass"),
                                             st.get("3_gross_margin"))
        return base, "thr=%r margin_min=%r" % (a1.get("threshold"), thr.get("margin_min"))
    if name == "fund_up" or name == "fund_up_months6":
        ok = (d.get("verdict") == "WATCH" and d.get("score") == 4 and d.get("applicable") is True
              and st.get("2_eps_trend") is True and st.get("3_gross_margin") is True
              and st.get("1_growth") is False and a1.get("pass") is True
              and a1.get("monetary_pct") == 50.0)
        return ok, "verdict=%r score=%r states=%r" % (d.get("verdict"), d.get("score"), st)
    if name == "fund_down":
        e2, e3 = axis("2"), axis("3")
        # EPS سه سالِ اخیر نزولی است و حاشیه ۱۱٪ (زیرِ کفِ ۲۰) — دو «رد»ِ واقعی،
        # نه None. کلیدِ حاشیه `margin_pct` است.
        return (d.get("verdict") == "REJECT" and st.get("2_eps_trend") is False
                and (e2.get("eps_series") or [None])[:1] == [66.56]
                and e3.get("margin_pct") == 11.0 and e3.get("na") is False
                and e3.get("pass") is False), \
            "eps=%r margin=%r" % (e2.get("eps_series"), e3.get("margin_pct"))
    if name == "fund_fund":
        return (d.get("verdict") == "FTS ندارد" and d.get("score") is None
                and d.get("applicable") is False and st.get("1_growth") is True), \
            "verdict=%r score=%r" % (d.get("verdict"), d.get("score"))
    if name == "fund_thin":
        return (st.get("1_growth") is None and a1.get("data_gap") is True
                and axis("4").get("data_gap") is not False), "all gaps, no fabricated zero"
    if name == "fund_mixed":
        # ردیف‌هایِ «1404-12-30» (خط تیره) و رقمِ فارسی بی‌دوره‌اند ⇒ محور ۳ na
        return (st.get("3_gross_margin") is None and axis("3").get("na") is True
                and a1.get("monetary_pct") == 33.3 and len(a1.get("series") or []) == 4), \
            "pct=%r series=%d" % (a1.get("monetary_pct"), len(a1.get("series") or []))
    return False, "no content predicate for %r" % name


def main() -> int:
    names = ("market.db", "user.db")
    try:
        with tempfile.TemporaryDirectory(prefix="b4f-a-") as a, tempfile.TemporaryDirectory(prefix="b4f-b-") as b:
            rcs = (build_fixture(a), build_fixture(b))
            fresh = [{n: sha(os.path.join(r, n)) for n in names} for r in (a, b)]
        committed = {n: sha(os.path.join(FIX, n)) for n in names}
        check("fundamental fixture is deterministic", rcs == (0, 0) and fresh[0] == fresh[1], "rc=%r" % (rcs,))
        check("committed fixture equals a fresh build", fresh[0] == committed,
              "fresh=%s committed=%s" % (fresh[0], committed))
    except Exception as e:                                        # noqa: BLE001
        check("fundamental fixture is deterministic", False, repr(e))
        check("committed fixture equals a fresh build", False, repr(e))

    saved = {k: os.environ.get(k) for k in
             ("BORS_DATA_DIR", "BORS_CHART_CDN", "BORS_CODAL_OFFLINE", "BORS_NO_FETCH_LOOPS")}
    gg = None
    try:
        gg = load("fund_golden_gen", "gen_fundamental_golden.py")
        with tempfile.TemporaryDirectory(prefix="b4-golden-") as tmp:
            gg.OUT = tmp
            with redirect_stdout(io.StringIO()):
                gg.main()
            mismatches, checked = [], 0
            for scen, stems in sorted(SCENARIOS.items()):
                have = sorted(n[:-5] for n in os.listdir(os.path.join(tmp, scen))) \
                    if os.path.isdir(os.path.join(tmp, scen)) else []
                if set(have) != stems:
                    mismatches.append("%s: files %s" % (scen, sorted(set(have) ^ stems)))
                    continue
                for stem in sorted(stems):
                    checked += 1
                    got = read_json(os.path.join(GOLD, scen, stem + ".json"))
                    want = read_json(os.path.join(tmp, scen, stem + ".json"))
                    if got != want:
                        mismatches.append("%s/%s" % (scen, stem))
            check("fundamental goldens equal a fresh oracle run (%d files)" % checked,
                  not mismatches, "; ".join(mismatches[:6]))
    except Exception as e:                                        # noqa: BLE001
        check("fundamental goldens equal a fresh oracle run", False, repr(e))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    checked = 0
    for scen, stems in sorted(SCENARIOS.items()):
        for stem in sorted(stems):
            p = os.path.join(GOLD, scen, stem + ".json")
            if not os.path.exists(p):
                check("%s/%s has content" % (scen, stem), False, "missing")
                continue
            checked += 1
            ok, detail = case_content(scen, stem, read_json(p))
            check("%s/%s has content" % (scen, stem), ok, detail)
    try:
        dirs = sorted(d for d in os.listdir(GOLD) if os.path.isdir(os.path.join(GOLD, d)))
        files = [f for f in os.listdir(GOLD) if os.path.isfile(os.path.join(GOLD, f))]
        check("golden tree holds only s1..s3", not files and dirs == ["s1", "s2", "s3"],
              "dirs=%r files=%r" % (dirs, files))
    except Exception as e:                                        # noqa: BLE001
        check("golden tree holds only s1..s3", False, repr(e))

    # کنترلِ منفی: مرزِ «خط تیره = بی‌دوره» را خودِ SQLite با همان GLOB می‌زند
    try:
        tmp = tempfile.mkdtemp(prefix="b4-neg-")
        db = os.path.join(tmp, "m.db")
        shutil.copyfile(os.path.join(FIX, "market.db"), db)
        import sqlite3
        import codal_periods as CP
        con = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
        slash = con.execute("SELECT COUNT(*) FROM financial_statements WHERE symbol=? AND " + CP.DATED_SQL,
                            (UP,)).fetchone()[0]
        dash = con.execute("SELECT COUNT(*) FROM financial_statements WHERE symbol=?", (MIXED,)).fetchone()[0]
        dash_ok = con.execute("SELECT COUNT(*) FROM financial_statements WHERE symbol=? AND " + CP.DATED_SQL,
                              (MIXED,)).fetchone()[0]
        con.close()
        shutil.rmtree(tmp, ignore_errors=True)
        check("dated/undated boundary is really enforced by the same GLOB",
              slash >= 6 and dash > dash_ok, "up=%d mixed=%d mixed_dated=%d" % (slash, dash, dash_ok))
    except Exception as e:                                        # noqa: BLE001
        check("dated/undated boundary is really enforced by the same GLOB", False, repr(e))

    print("fundamental fixture guard: %d passed / %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
