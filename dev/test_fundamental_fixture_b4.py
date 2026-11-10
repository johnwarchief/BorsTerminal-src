#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""گاردِ B4 — فیکسچر، اوراکل و طلایی‌هایِ بنیادی و نوار.

۱) فیکسچر قطعی است (دو build در دو پوشۀ موقت، هشِ یکسان) و با نسخۀ کامیت‌شده در ساختار و همهٔ ردیف‌ها یکی است.
۲) هر طلایی با اجرایِ تازهٔ اوراکل برابر است (پارسِ JSON، نه رشته).
۳) هر کیس محتوایِ خودش را دارد: رأیِ پنج‌محور، سه‌حالۀ null/False، دورۀ فصلی،
   clampها، حالتِ صندوق، و روزهایِ نوار با placeholder — تا «Δ=۰ رویِ بدنهٔ تهی»
   سبز نشود.
۴) کنترلِ منفی: مرزِ «تاریخِ با خط تیره = بی‌دوره» واقعاً ردیف را از محاسبه
   بیرون می‌اندازد (سنسور باید نبود را هم ببیند).
۵) کارتِ پنج‌محور (`GET /api/fundamental/{symbol}`): بدنه‌هایِ `card_*/body.json`
   بایت‌به‌بایت با اجرایِ تازهٔ اوراکل یکی‌اند، متا و نمایه با بدنه می‌خوانند،
   و محتوایِ هر کیس (رأی، سه‌حال، خطای ارزشِ بازار) سنجیده می‌شود.

اجرا: PYTHONIOENCODING=utf-8 python dev/test_fundamental_fixture_b4.py
"""
import hashlib
import io
import json
import os
import shutil
import sqlite3
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


def logical_db(path):
    """Logical content of a SQLite file: schema text plus every row, value-exact.

    A raw sha256 also hashes the SQLite header (bytes 98-99 are
    SQLITE_VERSION_NUMBER) and the page layout, so a byte-identical *content*
    fails on any other SQLite build. The fixture's contract is its schema and
    its rows, so compare exactly those: the sqlite_master DDL plus the full row
    multiset of every table. repr keeps cell types apart (1 vs 1.0 vs '1' vs
    None), so no value can hide behind a string conversion.
    """
    con = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
    try:
        master = con.execute(
            "SELECT type, name, tbl_name, COALESCE(sql, '') FROM sqlite_master "
            "ORDER BY type, name").fetchall()
        tables = {}
        for typ, name, _tbl, ddl in master:
            if typ != "table" or name.startswith("sqlite_"):
                continue
            rows = con.execute('SELECT * FROM "%s"' % name.replace('"', '""')).fetchall()
            tables[name] = (ddl, len(rows), sorted(repr(r) for r in rows))
        return {"master": tuple(master), "tables": tables}
    finally:
        con.close()


def logical_diff(a, b):
    """First difference between two logical_db() results; '' when equal."""
    if a["master"] != b["master"]:
        return "schema objects differ"
    if set(a["tables"]) != set(b["tables"]):
        return "tables differ: %r vs %r" % (sorted(a["tables"]), sorted(b["tables"]))
    for name in sorted(a["tables"]):
        ddl_a, n_a, rows_a = a["tables"][name]
        ddl_b, n_b, rows_b = b["tables"][name]
        if ddl_a != ddl_b:
            return "%s: DDL differs" % name
        if n_a != n_b:
            return "%s: %d rows vs %d" % (name, n_a, n_b)
        if rows_a != rows_b:
            for ra, rb in zip(rows_a, rows_b):
                if ra != rb:
                    return "%s: row differs: %s vs %s" % (name, ra[:120], rb[:120])
            return "%s: row multiset differs" % name
    return ""


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

# کارتِ پنج‌محور: `GET /api/fundamental/{symbol}` ⇒ پوشهٔ `card_<CASE>/body.json`
# درِ همان درختِ طلایی. نامِ کیس ⇒ نماد (رقمِ فارسی با کدپوینت نوشته می‌شود تا
# رقم درِ متن دزدیده نشود).
CARD_GEN = os.path.join(TOOLS, "gen_fundamental_card_golden.py")
CARD_CASES = {
    "card_up": UP,
    "card_up_score5": UP,
    "card_down": DOWN,
    "card_fund": FUND,
    "card_thin": THIN,
    "card_mixed": MIXED,
    "card_mcap_missing": "نگهبان03",
    "card_no_board_row": "غایب",
    "card_holding": "سخت05",
    "card_no_sales": "کدبه‌کد09",
    "card_not_found": "نیست" + chr(0x06F0) + chr(0x06F1),
    "card_up_months6": UP,
}
ZERO_STEP = chr(0x06F0)          # «۰» — پیامِ حذفِ خودکار درِ صدرِ بینش‌ها
MCAP_KEY = "ارزش بازار"          # کلیدِ ارزشِ بازار درِ بخشِ «secondary»
# دلیلِ «نه شاخص ۴» درِ سه‌حالِ بی‌ارزش‌بازار/بی‌فروش — عینِ ثابتِ Go
# `a45ReasonNoMcap` و `fts_engine.ind4_reason_text(available=False)`؛ این‌جا
# با برابریِ کامل سنجیده می‌شود تا تغییرِ واژه بی‌صدا نماند.
NO_MCAP_REASON = "دادهٔ ارزش بازار یا فروش سالانه برای محاسبه نسبت در دسترس نیست."


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


def card_case_content(name, d):
    """محتوایِ کارت — سنجه‌هایی که از خودِ بدنه خوانده می‌شوند، نه از نامِ پرونده.

    سه‌حالِ null/False/True و شاخه‌هایِ خطایِ ارزشِ بازار محکِ اصلی‌اند: کارتِ
    درست باید «بی‌داده» را با «رد» اشتباه نگیرد.
    """
    if name == "card_not_found":
        return (d.get("__http_status__") == 404 and bool(d.get("detail"))), "404 shape kept"
    st = d.get("states") or {}
    ps = d.get("passes") or {}
    mt = d.get("metrics") or {}
    ind = d.get("indicators") or {}
    a1, a2, a3, a4 = (ind.get(k) or {} for k in ("1", "2", "3", "4"))
    sec = d.get("secondary") or {}
    steps = [i.get("step") for i in (d.get("insights") or [])]
    five = ("1_growth", "2_eps_trend", "3_gross_margin", "4_sales_to_mcap", "5_industry")
    mcap_txt = str(sec.get(MCAP_KEY) or "")
    if name == "card_up":
        ok = (d.get("verdict") == "WATCH" and d.get("score") == 4
              and d.get("applicable") is True and d.get("excluded") is False
              and st.get("1_growth") is False
              and all(st.get(k) is True for k in five[1:])
              and ps.get("1b_volume_growth") is False
              and (a1.get("monetary") or {}).get("monetary_pct") == 50.0
              and mt.get("mcap_error") is None and mt.get("mcap_source") == "official"
              and mt.get("mcap_asof") == 20261028
              and not d.get("data_gaps")
              and "موجود نیست" not in mcap_txt)
        return ok, "verdict=%r score=%r states=%r" % (d.get("verdict"), d.get("score"), st)
    if name == "card_up_score5":
        thr = (d.get("methodology") or {}).get("thresholds") or {}
        ok = (d.get("verdict") == "STRONG" and d.get("score") == 5
              and d.get("applicable") is True
              and all(st.get(k) is True for k in five)
              and ps.get("1b_volume_growth") is True
              and thr.get("inflation_basis") == 40.0
              and (d.get("thresholds") or {}).get("v10_inflation_basis") == 40.0)
        return ok, "verdict=%r score=%r inflation=%r" % (d.get("verdict"), d.get("score"),
                                                         thr.get("inflation_basis"))
    if name == "card_down":
        ok = (d.get("verdict") == "REJECT" and d.get("score") == 2
              and st.get("1_growth") is False and st.get("2_eps_trend") is False
              and st.get("3_gross_margin") is False
              and (a2.get("eps_series") or [None])[:1] == [66.56]
              and a3.get("margin_pct") == 11.0 and a3.get("na") is False
              and a3.get("pass") is False)
        return ok, "eps=%r margin=%r" % (a2.get("eps_series"), a3.get("margin_pct"))
    if name == "card_fund":
        ok = (d.get("verdict") == "FTS ندارد" and d.get("score") is None
              and d.get("applicable") is False
              and st.get("1_growth") is True
              and st.get("2_eps_trend") is None and st.get("4_sales_to_mcap") is None)
        return ok, "verdict=%r score=%r applicable=%r" % (d.get("verdict"), d.get("score"),
                                                          d.get("applicable"))
    if name == "card_thin":
        gaps = {g.get("axis") for g in (d.get("data_gaps") or [])}
        ok = (st.get("1_growth") is None and st.get("2_eps_trend") is None
              and st.get("3_gross_margin") is None
              and (a1.get("monetary") or {}).get("data_gap") is True
              and {"1a_monetary_growth", "2_eps_trend", "3_gross_margin"} <= gaps)
        return ok, "states=%r gaps=%r" % (st, sorted(gaps))
    if name == "card_mixed":
        ok = (mt.get("mcap_error") == "symbol_not_on_board"
              and mt.get("mcap_source") is None and mt.get("mcap_asof") is None
              and a4.get("na") is True and a4.get("gap_cause") == "market_cap"
              and a4.get("market_cap_error") == "symbol_not_on_board"
              and a3.get("na") is True and st.get("3_gross_margin") is None
              and "موجود نیست" in mcap_txt)
        return ok, "mcap_error=%r gap_cause=%r" % (mt.get("mcap_error"), a4.get("gap_cause"))
    if name == "card_mcap_missing":
        ok = (mt.get("mcap_error") == "market_cap_missing_value"
              and mt.get("mcap_asof") == 20261014
              and d.get("excluded") is True and d.get("verdict") == "EXCLUDED"
              and d.get("score") == 0 and d.get("pricing_mode") == "mandatory"
              and bool(d.get("exclusion_reasons"))
              and ZERO_STEP in steps
              and "موجود نیست" in mcap_txt)
        return ok, "mcap_error=%r excluded=%r steps=%r" % (mt.get("mcap_error"),
                                                           d.get("excluded"), steps)
    if name == "card_no_board_row":
        ok = (mt.get("mcap_error") == "market_cap_missing_value"
              and mt.get("mcap_asof") is None and mt.get("mcap_source") is None
              and "موجود نیست" in mcap_txt)
        return ok, "mcap_error=%r asof=%r" % (mt.get("mcap_error"), mt.get("mcap_asof"))
    if name == "card_holding":
        ok = (a4.get("na") is True and a4.get("exempt") is True
              and a4.get("available") is False and a4.get("pass") is False
              and "N/A" in str(a4.get("reason") or ""))
        return ok, "axis4=%r" % ({k: a4.get(k) for k in ("na", "exempt", "available")},)
    if name == "card_no_sales":
        # محورِ ۴ «سنجیده نشد» است نه «رد»: در این شاخه `pass` سه‌حال است
        # (None)، نه False — همان قراردادِ `api/fundamental.py` و Go.
        ok = (a4.get("na") is True and a4.get("gap_cause") == "annual_sales"
              and a4.get("available") is False and a4.get("pass") is None
              and str(a4.get("reason") or "") == NO_MCAP_REASON)
        return ok, "axis4=%r reason=%r" % (
            {k: a4.get(k) for k in ("na", "gap_cause", "available", "pass")},
            a4.get("reason"))
    if name == "card_up_months6":
        up = read_json(os.path.join(GOLD, "card_up", "body.json"))
        ok = (d == up and d.get("score") == 4 and d.get("verdict") == "WATCH")
        return ok, "months=6 body == card_up"
    return False, "no card predicate for %r" % name


def card_section():
    """داوریِ کارتِ پنج‌محور: اجرایِ تازهٔ اوراکل، مقایسهٔ بایتی، صحتِ متا و
    نمایه، و یک کنترلِ منفی.

    اوراکل درِ پروسه‌ی جدا اجرا می‌شود: `bors_config.DB_PATH` و
    `FTS_CONFIG_PATH` درِ لحظهٔ import ثابت می‌شوند، پس اگر همین پروسه پس ازِ
    اوراکلِ بنیادی کارت را اجرا کند، پروندهٔ آستانه‌های `card_up_score5` را
    نمی‌بیند و کارت را چهار از پنج محور می‌خواند.
    """
    fresh = {}
    try:
        with tempfile.TemporaryDirectory(prefix="b4-card-") as tmp:
            proc = subprocess.run([sys.executable, CARD_GEN, "--out", tmp],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace")
            check("card oracle runs clean", proc.returncode == 0,
                  "rc=%r %s" % (proc.returncode, (proc.stderr or "")[-300:]))
            if proc.returncode != 0:
                return
            have = sorted(d for d in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, d)))
            check("card oracle emits every case dir", have == sorted(CARD_CASES),
                  "got=%r want=%r" % (have, sorted(CARD_CASES)))
            mismatch, missing = [], []
            for case in sorted(CARD_CASES):
                fp = os.path.join(tmp, case, "body.json")
                gp = os.path.join(GOLD, case, "body.json")
                if not (os.path.exists(fp) and os.path.exists(gp)):
                    missing.append(case)
                    continue
                with open(fp, "rb") as f:
                    fresh[case] = f.read()
                with open(gp, "rb") as f:
                    if f.read() != fresh[case]:
                        mismatch.append(case)
            check("card goldens are byte-identical to a fresh oracle run (%d files)"
                  % len(CARD_CASES), not missing and not mismatch,
                  "missing=%r mismatch=%r" % (missing, mismatch))
    except Exception as e:                                        # noqa: BLE001
        check("card oracle section", False, repr(e))
        return

    # متا: نماد، مسیرِ مسیرِ HTTP، هش و اندازهٔ بدنه — همه باید با فایل بخوانند.
    bad = []
    for case, symbol in sorted(CARD_CASES.items()):
        mp = os.path.join(GOLD, case, "meta.json")
        bp = os.path.join(GOLD, case, "body.json")
        if not (os.path.exists(mp) and os.path.exists(bp)):
            bad.append("%s: missing" % case)
            continue
        with open(bp, "rb") as f:
            raw = f.read()
        m = read_json(mp)
        py = m.get("python") or {}
        if (m.get("case") != case or m.get("symbol") != symbol
                or m.get("body_file") != "body.json"
                or m.get("body_sha256") != hashlib.sha256(raw).hexdigest()
                or m.get("body_bytes") != len(raw)
                or py.get("module") != "api/fundamental.py"
                or py.get("function") != "get_fundamental"
                or not str(m.get("route") or "").startswith("GET /api/fundamental/")):
            bad.append(case)
    check("card meta.json matches its body (%d files)" % len(CARD_CASES), not bad,
          "; ".join(bad[:6]))

    # نمایه: هر کیس با مسیرِ نسبی، هش و اندازهٔ درست.
    bad = []
    ip = os.path.join(GOLD, "card_index.json")
    if not os.path.exists(ip):
        bad.append("card_index.json missing")
    else:
        idx = read_json(ip)
        rows = {r.get("name"): r for r in (idx.get("cases") or [])}
        if set(rows) != set(CARD_CASES):
            bad.append("cases=%r" % sorted(rows))
        if idx.get("route") != "GET /api/fundamental/{symbol}":
            bad.append("route=%r" % idx.get("route"))
        for case, symbol in sorted(CARD_CASES.items()):
            r = rows.get(case) or {}
            bp = os.path.join(GOLD, case, "body.json")
            if not os.path.exists(bp):
                bad.append("%s: body missing" % case)
                continue
            with open(bp, "rb") as f:
                raw = f.read()
            if r.get("body") != "%s/body.json" % case:
                bad.append("%s: body=%r" % (case, r.get("body")))
            if r.get("symbol") != symbol:
                bad.append("%s: symbol=%r" % (case, r.get("symbol")))
            if r.get("sha256") != hashlib.sha256(raw).hexdigest():
                bad.append("%s: sha" % case)
            if r.get("bytes") != len(raw):
                bad.append("%s: bytes" % case)
    check("card_index.json lists every case with a matching sha", not bad, "; ".join(bad[:6]))

    # کنترلِ منفی: بدنهٔ دستکاری‌شده باید هم بایتی و هم پارسی گرفته شود.
    try:
        raw = fresh.get("card_up")
        good = open(os.path.join(GOLD, "card_up", "body.json"), "rb").read()
        mutated = raw.replace(b'"score": 4', b'"score": 5', 1)
        check("negative control really mutates a card body", mutated != raw)
        check("negative control: mutated body differs byte-wise", mutated != good)
        check("negative control: mutated body differs in parsed JSON",
              json.loads(mutated.decode("utf-8")) != json.loads(good.decode("utf-8")))
    except Exception as e:                                        # noqa: BLE001
        check("negative control really mutates a card body", False, repr(e))


def main() -> int:
    names = ("market.db", "user.db")
    try:
        with tempfile.TemporaryDirectory(prefix="b4f-a-") as a, tempfile.TemporaryDirectory(prefix="b4f-b-") as b:
            rcs = (build_fixture(a), build_fixture(b))
            fresh = [{n: sha(os.path.join(r, n)) for n in names} for r in (a, b)]
            fresh_logical = [{n: logical_db(os.path.join(r, n)) for n in names} for r in (a, b)]
        committed_logical = {n: logical_db(os.path.join(FIX, n)) for n in names}
        check("fundamental fixture is deterministic", rcs == (0, 0) and fresh[0] == fresh[1], "rc=%r" % (rcs,))
        bad = {n: logical_diff(fresh_logical[0][n], committed_logical[n]) for n in names}
        bad = {n: d for n, d in bad.items() if d}
        check("committed fixture equals a fresh build (schema + every row)", not bad,
              "; ".join("%s: %s" % (n, d) for n, d in bad.items()))
    except Exception as e:                                        # noqa: BLE001
        check("fundamental fixture is deterministic", False, repr(e))
        check("committed fixture equals a fresh build (schema + every row)", False, repr(e))

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
        check("golden tree holds s1..s3 plus the card goldens",
              dirs == sorted(list(SCENARIOS) + list(CARD_CASES)) and files == ["card_index.json"],
              "dirs=%r files=%r" % (dirs, files))
    except Exception as e:                                        # noqa: BLE001
        check("golden tree holds s1..s3 plus the card goldens", False, repr(e))

    # کارتِ پنج‌محور (`GET /api/fundamental/{symbol}`): اوراکلِ تازه بایت‌به‌بایت،
    # متا و نمایه، و محتوایِ هر کیس.
    card_section()
    for case in sorted(CARD_CASES):
        p = os.path.join(GOLD, case, "body.json")
        if not os.path.exists(p):
            check("card/%s has content" % case, False, "missing")
            continue
        ok, detail = card_case_content(case, read_json(p))
        check("card/%s has content" % case, ok, detail)

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
