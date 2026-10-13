# -*- coding: utf-8 -*-
"""خودآزمونِ سنسورِ گاردِ هویت — نقص‌هایِ تاریخی را دوباره می‌کارد، نه این‌که گارد را اجرا می‌کند.

دستورِ Stage ۱ مأموریت: «گارد هویت را فقط اجرا نکن؛ بررسی کن که توان تشخیص
واقعی نقص‌هایی را که قبلاً وجود داشته‌اند دارد.» سبزبودنِ `dev/symbol_identity_v1090.py`
به‌خودی‌خود هیچ چیز را ثابت نمی‌کند: ممکن است سنسور کور باشد و داده درست باشد،
یا برعکس. پس هر نقصِ اثبات‌شدهٔ این پرونده درِ **حافظه** برگردانده می‌شود
(هیچ فایلی عوض نمی‌شود، هیچ نوشتی رویِ هیچ بانکی نیست) و باید همان چک‌ها قرمز
شوند. اگر نقصی برگردانده شد و گارد قرمز نشد، این ابزار غیرموفق است.

شش نقصِ برگردانده‌شده، همه از تاریخِ همین پرونده:

  ۱) `key`ِ بی‌حذفِ نیم‌فاصله — همان باگِ «شهر فرش» (کارت ۱ ردیف، قیف ۷ ردیف)
  ۲) پلکانی که پرچمِ «شرکتِ دیگر» را نمی‌بیند — مرجعِ ۲۰٪ از «شرکت داتیس…»
  ۳) سبدِ سالِ بی‌پرچم — ردیفِ فرعی جای صورتِ مالیِ خودِ نماد را درِ ۱۴۰۴ می‌گیرد
  ۴) نردبانِ EPSِ بی‌قاعده — EPS 109ِ شرکتِ دیگر به‌جای 382ِ خودِ نماد
  ۵) گیتِ ISINِ خاموش — الحاقِ پسوندِ رقمی بی‌شاهد (`كم ر ۱` ⇄ `كم ر ۵`)
  ۶) `row_conflicts`ِ تهی — تناقضِ عنوان⇄ستون بی‌اعلام می‌ماند

اجرا:  PYTHONIOENCODING=utf-8 python tools/codal_identity_sensor_selftest.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io as _io
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import fts_engine as FE                      # noqa: E402
import symbol_identity as SI                 # noqa: E402

GUARD_PATH = os.path.join(ROOT, "dev", "symbol_identity_v1090.py")
_spec = importlib.util.spec_from_file_location("symid_guard_selftest_subject", GUARD_PATH)
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)

_ORIG = {
    "SI.key": SI.key,
    "SI.line_variants": SI.line_variants,
    "FE.pick_reference": FE.pick_reference,
    "FE.statement_rank": FE.statement_rank,
    "FE.title_entity_suffix": FE.title_entity_suffix,
    "FE.row_conflicts": FE.row_conflicts,
}


def reds_for(conn):
    G.CHECKS.clear()
    G.section_layer(conn)
    G.section_paths(conn)
    G.section_regressions(conn)
    return {msg for ok, msg in G.CHECKS if not ok}


_SUFFIXES = ("", "ب", "پ", "ت", "ج")


def prefix_hits(reds, prefixes):
    """آیا برای هر پیشوندِ موردانتظار، حداقلِ یک چک با همان شناسه قرمز شده؟

    تطبیق «شروعِ رشته» کافی نیست: «T1» با «T12…» هم شروع می‌شود و سنسورِ کور
    خودش را سبز نشان می‌دهد. پس شناسه (توکنِ اولِ برچسب) باید دقیقاً یکی از
    شکل‌هایِ پیشوند + پسوندِ فارسی باشد.
    """
    hit, miss = [], []
    for p in prefixes:
        want = {p + s for s in _SUFFIXES}
        got = [m for m in reds if m.split(" ", 1)[0] in want]
        (hit if got else miss).append(p)
    return hit, miss


def run_case(name, mutate, expect_prefixes):
    """نقص را می‌کارد، گارد را اجرا می‌گیرد، و می‌گوید کدام چک‌ها قرمز شدند."""
    conn, path = G.make_db()
    saved = dict(_ORIG)
    try:
        mutate()
        SI.reset_cache(conn)
        with contextlib.redirect_stdout(_io.StringIO()):
            reds = reds_for(conn)
    finally:
        if hasattr(SI, "_SLOT_BACKUP"):
            SI._slot = SI._SLOT_BACKUP
            del SI._SLOT_BACKUP
        for k, v in saved.items():
            if k.startswith("SI."):
                setattr(SI, k.split(".")[1], v)
            else:
                setattr(FE, k.split(".")[1], v)
        SI.reset_cache(conn)
        conn.close()
        try:
            os.unlink(path)
        except OSError:
            pass
    _hit, miss = prefix_hits(reds, expect_prefixes)
    ok = not miss
    print("  %s %-44s قرمز: %2d   انتظار: %-18s %s"
          % ("✓" if ok else "✗", name, len(reds), " ".join(expect_prefixes),
             "" if ok else ("هیچ‌کدام قرمز نشد: " + ",".join(miss))))
    for m in sorted(reds)[:2]:
        print("        · " + m[:112])
    return ok


# ── شش نقصِ تاریخی، هرکدام درِ یک تابع ─────────────────────────────────────
def m_key_zwnj():
    """`key`ِ پیش ازِ Stage 1.2: فقط عربی←فارسی، بی‌حذفِ نیم‌فاصله."""
    SI.key = lambda s: str(s if s is not None else "").translate(
        str.maketrans({"\u064a": "\u06cc", "\u0643": "\u06a9", "\u0649": "\u06cc"})).replace(
        " ", "").lower()


def m_ladder_blind():
    """HEAD: لایۀ پلکان و لایۀ سبد، با هم، پرچمِ «شرکتِ دیگر» را نمی‌بینند.

    تک‌لایه‌ای کافی نیست: با سبدِ سالم، ردیفِ فرعی هرگز برندۀ سبدِ سال نمی‌شود و
    پلکانِ بی‌پرچم هم چیزی را عوض نمی‌کند (دفاعِ چندلایه). نقصِ تاریخیِ واقعی
    «خاموش‌بودنِ هر دو» بود، پس کارز هم هر دو را خاموش می‌کند.
    """
    def blind(rows, need=None):
        by_year = {}
        for r in rows or []:
            if int(FE._f(r.get("period_months"))) < 12:
                continue
            yr = str(r.get("fiscal_year") or "")
            if not yr:
                continue
            rank = FE.statement_rank(FE.FS_NUMBER_KEYS, bool(r.get("consolidated")),
                                     FE.row_completeness(FE.FS_NUMBER_KEYS, r),
                                     r.get("tracing_no") or 0)
            cur = by_year.get(yr)
            if cur is None or rank < cur[0]:
                by_year[yr] = (rank, r)
        cand = sorted(by_year.values(), key=lambda t: str(t[1].get("fiscal_year") or ""),
                      reverse=True)
        for want in (lambda a, c, o: a and not c, lambda a, c, o: not c, lambda a, c, o: True):
            for _rank, r in cand:
                if want(bool(r.get("audited")), bool(r.get("consolidated")),
                        bool(r.get("other_entity"))):
                    return r
        return None
    FE.pick_reference = blind
    FE.statement_rank = (lambda keys, consolidated, completeness, tracing_no,
                         other_entity=False: (0, 1 if consolidated else 0,
                                              -completeness, -int(tracing_no or 0)))


def m_bucket_blind():
    FE.statement_rank = (lambda keys, consolidated, completeness, tracing_no,
                         other_entity=False: (0, 1 if consolidated else 0,
                                              -completeness, -int(tracing_no or 0)))


def m_eps_blind():
    FE.title_entity_suffix = lambda title: ""


def m_isin_off():
    real = _ORIG["SI.line_variants"]

    def no_gate(conn, symbol, domain=SI.CODAL):
        slot = SI._slot(conn)
        k = SI.key(symbol)
        base = re.sub(r"(?<=\D)\d$", "", k)
        if base and base != k:
            raws = tuple(r for r in slot["by_key"].get(base, ()) if SI.key(r) == base)
            if raws:
                return raws, "isin-agree"
        return real(conn, symbol, domain)
    SI.line_variants = no_gate


def m_conflicts_off():
    FE.row_conflicts = lambda period_end, title, period_months: []


def m_cache_same_conn_off():
    """بی‌اعتباریِ نوشتِ *خودِ اتصال* خاموش — دقیقاً همان نقصِ واقعیِ این دور."""
    real = SI._slot

    def stale(conn, *a, **kw):
        slot = SI._CACHE.get(id(conn))
        if slot and slot["conn"] is conn:
            slot["tc"] = conn.total_changes      # سیگنالِ دوم خنثی
        return real(conn, *a, **kw)
    SI._slot = stale
    SI._SLOT_BACKUP = real


def run_case7_vacuous_ast():
    """چکِ AST نباید با جابه‌جاییِ فایلِ مصرف‌کننده بی‌صدا سبز شود.

    حلقه‌هایِ `section_ast` فایلِ نبود را `continue` می‌کنند؛ اگر روزی
    `api/fundamental.py` rename شود، «هیچ زنجیرۀ REPLACE نمانده» بی‌مصرف سبز
    می‌ماند. T18 همان سوراخ را می‌بندد — پس با PRODِ افزوده‌شده باید قرمز شود.
    """
    saved = G.PROD
    G.PROD = tuple(saved) + ("api/این‌فایلنیست.py",)
    try:
        G.CHECKS.clear()
        with contextlib.redirect_stdout(_io.StringIO()):
            G.section_ast()
        reds = {msg for ok, msg in G.CHECKS if not ok}
    finally:
        G.PROD = saved
    ok = any(m.split(" ", 1)[0] == "T18" for m in reds)
    print("  %s %-44s قرمز: %2d   انتظار: T18              %s"
          % ("✓" if ok else "✗", "۷) AST بی‌فایلِ مصرف‌کننده (سبزِ بی‌مصرف)", len(reds),
             "" if ok else "هیچ‌کدام قرمز نشد: T18"))
    return ok


CASES = [
    ("۱) keyِ بی‌نیم‌فاصله (باگِ شهر فرش)", m_key_zwnj, ("T1", "R1", "R11", "T2")),
    ("۲) پلکان+sبدِ بی‌پرچم (سرشتِ HEAD)", m_ladder_blind, ("R2", "R5ب", "R10", "T12ب")),
    ("۳) سبدِ سالِ بی‌پرچم", m_bucket_blind, ("T12ب",)),
    ("۴) نردبانِ EPSِ بی‌قاعده", m_eps_blind, ("R13", "R2")),
    ("۵) گیتِ ISINِ خاموش", m_isin_off, ("T6", "T9")),
    ("۶) row_conflictsِ تهی", m_conflicts_off, ("R12",)),
    ("۸) کشِ بی‌اعتبارنشدنِ نوشتِ خودِ اتصال", m_cache_same_conn_off, ("T21",)),
]


def main() -> int:
    print("سنسورِ گاردِ هویت — هفت نقصِ تاریخی برگردانده می‌شود:")
    n_ok = 0
    for name, mutate, expect in CASES:
        n_ok += 1 if run_case(name, mutate, expect) else 0
    n_ok += 1 if run_case7_vacuous_ast() else 0
    n_all = len(CASES) + 1
    # کنترلِ مثبت: بی‌هیچِ کارزاری گارد باید سبز باشد (وگرنه قرمزها بی‌معنااند)
    conn, path = G.make_db()
    try:
        G.CHECKS.clear()
        with contextlib.redirect_stdout(_io.StringIO()):
            G.section_layer(conn)
            G.section_paths(conn)
            G.section_regressions(conn)
        clean = sum(1 for ok, _ in G.CHECKS if not ok)
    finally:
        conn.close()
        try:
            os.unlink(path)
        except OSError:
            pass
    print("  %s کنترلِ مثبت: بی‌هیچِ کارزاری %d چک قرمز است (باید ۰)"
          % ("✓" if clean == 0 else "✗", clean))
    # شمارشگرِ قابل‌پارسِ dev/run_all_tests.py (`N passed / M failed`)
    passed = n_ok + (1 if clean == 0 else 0)
    print("\nsensor_selftest: %d passed / %d failed  (%d نقصِ تاریخی + کنترلِ مثبت)"
          % (passed, n_all + 1 - passed, n_all))
    return 0 if (n_ok == n_all and clean == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
