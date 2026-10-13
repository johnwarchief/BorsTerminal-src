# -*- coding: utf-8 -*-
"""چرا حاشیۀ سودِ این نمادها از «عدد» به «بی‌داده» افتاد؟ — تک‌تک، با شاهد.

بندِ ۳ مأموریت، هفت پرسش برای هر نماد. سه نقصِ نسخۀ پیشین این ابزار رفع شد:

۱) «پیش» ساختگی بود: با خاموش‌کردنِ `title_entity_suffix` درِ کدِ امروز ساخته
   می‌شد، پس توصیفِ «گزارشِ منتخبِ پیشین» از کدی می‌آمد که نردبانِ P-2 و لایۀ
   هویت را هم داشت. حالا چهار dumpِ واقعی خوانده می‌شود
   (`codal_bulk_dump.py` و `codal_ref_dump.py` روی `5c97b5c` و رویِ امروز).
۲) مرجعِ توصیف‌شده با ردیفی که `bulk_scan` واقعاً مصرف کرده یکی نبود، پس
   چاپِ «حاشیۀ پیشین = None» برایِ نمادهایی تولید می‌شد که عدد داشتند
   (تاديكو/وفيروزه).
۳) علت‌ها تا «نبودِ داده» خلاصه می‌شد؛ حالا دفترچۀ `codal_extracted` (ok=0 یعنی
   استخراجِ *موفق* نبود) و ستونِ واحد و صنعت هم خوانده می‌شوند تا «بی‌دادهٔ
   درست» از «بی‌دادهٔ ناشی از نقصِ استخراج» جدا شود.

usage: PYTHONIOENCODING=utf-8 python tools/codal_margin_loss_diagnosis.py
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import codal_periods as CP                    # noqa: E402
import codal_units as CU                      # noqa: E402
import fts_engine as FE                       # noqa: E402
import symbol_identity as SI                  # noqa: E402

_real_suffix = FE.title_entity_suffix
CAUSES = ("policy_other_entity", "genuine_absence_no_gp_line", "not_applicable_sector",
          "extraction_failed", "unit_missing", "period_undetermined",
          "selection_bug", "no_own_annual_row", "other")


def load_rows(path):
    if not os.path.exists(path):
        raise SystemExit("BLOCKED: baseline نیست — «پیش» را از کدِ امروز نساز: %s" % path)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["rows"]


def own_annual_rows(conn, sym):
    """همهٔ ردیف‌هایِ سالانۀ خودِ شرکت (خانوادۀ نوشتاری، بی‌عنوانِ شرکتِ دیگر)."""
    pred, params = FE.sym_in(conn, "symbol", sym)
    out = []
    for tn, pe, pm, title, gp, rev, op, unit, cname in conn.execute(
            "SELECT tracing_no, period_end, period_months, title, gross_profit, revenue, "
            "operating_profit, unit, company_name FROM financial_statements WHERE "
            + pred + " ORDER BY period_end DESC", params).fetchall():
        months, src = CP.effective_months(pe, pm, title)
        t = str(title or "")
        out.append({"tracing_no": tn, "period_end": CP.canonicalize(pe),
                    "months": months, "months_source": src,
                    "is_annual": bool(months and months >= 12),
                    "other_entity": _real_suffix(t),
                    "gross_profit": gp, "revenue": rev, "operating_profit": op,
                    "unit": unit, "unit_known": CU.classify(unit) is not None,
                    "company_name": cname,
                    "audited": FE._is_audited(t), "consolidated": FE._is_consolidated(t)})
    return out


def extraction_state(conn, tn):
    r = conn.execute("SELECT ok, tried_at FROM codal_extracted WHERE tracing_no=? AND kind='fs'",
                     (tn,)).fetchone()
    if not r:
        return {"tried": False, "ok": None, "tried_at": None}
    return {"tried": True, "ok": int(r[0]), "tried_at": r[1]}


def identify_row(conn, ref):
    """ردیفِ انتخابیِ کدِ HEAD را از **عددش** درِ بانک پیدا می‌کند.

    چرا لازم است: `reference_annual` درِ `5c97b5c` ردیف را بی‌`tracing_no` و
    بی‌`company_name` برمی‌گرداند (آن دو ستون درِ provenance نبودند — دقیقاً همان
    چیزی که بندِ ۱/۶ مأموریت می‌خواهد). پس هویتِ «گزارشِ منتخبِ پیشین» را از
    (revenue, gross_profit, period_end) بازمی‌خوانیم و می‌گوییم آن عدد درِ bank
    مالِ کدامِ نماد/عنوان بوده. تطبیقِ چندردیفی خودشان فهرست می‌شوند، نه یکی.
    """
    if not ref or ref.get("revenue") is None:
        return []
    out = []
    for r in conn.execute(
            "SELECT tracing_no, symbol, company_name, title FROM financial_statements "
            "WHERE revenue IS ? AND gross_profit IS ? ORDER BY tracing_no LIMIT 6",
            (ref.get("revenue"), ref.get("gross_profit"))).fetchall():
        out.append({"tracing_no": r[0], "symbol": r[1], "company_name": r[2],
                    "title": str(r[3] or "")[:110]})
    return out


def margin_of(row):
    if not row:
        return None
    gp, rev = row.get("gross_profit"), row.get("revenue")
    if gp is None or not rev:
        return None
    try:
        return round(100.0 * float(gp) / float(rev), 1)
    except (TypeError, ValueError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--bulk-old", default="_audit/bulk_old_5c97b5c_2026-10-13.json")
    ap.add_argument("--bulk-new", default="_audit/bulk_new_2026-10-13.json")
    ap.add_argument("--ref-old", default="_audit/ref_old_5c97b5c_2026-10-13.json")
    ap.add_argument("--ref-new", default="_audit/ref_new_2026-10-13.json")
    ap.add_argument("--out", default="_audit/codal_margin_loss_diagnosis.json")
    a = ap.parse_args()
    bulk_old, bulk_new = load_rows(a.bulk_old), load_rows(a.bulk_new)
    ref_old, ref_new = load_rows(a.ref_old), load_rows(a.ref_new)

    conn = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True)
    conn.row_factory = sqlite3.Row
    FE.register_sql(conn)

    lost = sorted(s for s, o in bulk_old.items()
                  if o.get("gross_margin") is not None
                  and (bulk_new.get(s) or {}).get("gross_margin") is None)
    gained = sorted(s for s, o in bulk_old.items()
                    if o.get("gross_margin") is None
                    and (bulk_new.get(s) or {}).get("gross_margin") is not None)

    cases = []
    for sym in lost:
        ore = (ref_old.get(sym) or {}).get("ref") or {}
        nre = (ref_new.get(sym) or {}).get("ref") or {}
        nmre = (ref_new.get(sym) or {}).get("margin_ref") or nre
        rows = own_annual_rows(conn, sym)
        annual_own = [r for r in rows if r["is_annual"] and not r["other_entity"]]
        with_gp = [r for r in annual_own if r["gross_profit"] is not None and r["revenue"]]
        pred, params = FE.sym_in(conn, "i.l_val18", sym, SI.BOARD)
        sector = conn.execute(
            "SELECT COALESCE(sector_name,'') FROM instruments i WHERE " + pred,
            params).fetchone()
        sec = str((sector[0] if sector else "") or "")
        old_names_other = bool(_real_suffix(ore.get("title") or ""))
        ex = extraction_state(conn, (nmre or {}).get("tracing_no"))
        ex_old = extraction_state(conn, ore.get("tracing_no"))
        if with_gp:
            cause = "selection_bug"
            why = ("ردیفِ خودیِ دارایِ سودِ ناخالص هست (%s) ولی انتخاب نشده"
                   % "،".join(str(r["tracing_no"]) for r in with_gp[:3]))
        elif not annual_own:
            cause = "no_own_annual_row"
            why = "هیچ ردیفِ سالانۀ خودی (بی‌عنوانِ شرکتِ دیگر) درِ بانک نیست"
        elif FE.fund_class_match(sec, "") or FE.is_insurance_sector(sec):
            cause = "not_applicable_sector"
            why = "صنعت «%s» خطِ سودِ ناخالص ندارد — جزوه این را not_applicable می‌گیرد" % sec
        elif any(r["operating_profit"] is not None and not r["unit_known"] for r in annual_own):
            cause = "unit_missing"
            why = "ردیفِ خودی عدد دارد ولی ستونِ واحدِش شناخته‌شده نیست"
        elif ex["tried"] and not ex["ok"]:
            cause = "extraction_failed"
            why = "برداشتِ این ردیف درِ دفترچۀ `codal_extracted` با ok=0 ثبت شده"
        else:
            cause = "genuine_absence_no_gp_line"
            why = ("%d ردیفِ سالانۀ خودی درِ بانک هست ولی هیچ‌بار خطِ «سود ناخالص» برایش "
                   "ثبت نشده (برداشت موفق بوده، خط وجود ندارد)" % len(annual_own))
        cases.append({
            "symbol": sym,
            "q1_old_selected_reference": {
                "tracing_no": ore.get("tracing_no"), "title": (ore.get("title") or "")[:110],
                "company_name": ore.get("company_name"),
                "period_end": CP.canonicalize(ore.get("period_end")),
                "margin_pct_old_bulk": bulk_old[sym].get("gross_margin"),
                "margin_pct_of_that_row": margin_of(ore),
                "extraction_ok": ex_old.get("ok"),
                "row_identity_from_db": identify_row(conn, ore)},
            "q2_new_selected_reference": {
                "general_tracing_no": nre.get("tracing_no"),
                "margin_tracing_no": nmre.get("tracing_no"),
                "margin_title": (nmre.get("title") or "")[:110],
                "margin_period_end": CP.canonicalize(nmre.get("period_end"))},
            "q3_old_row_named_another_company": {
                "suffix": _real_suffix(ore.get("title") or "") or None,
                "old_company": ore.get("company_name"),
                "own_companies": sorted({str(r["company_name"] or "") for r in rows
                                         if r["company_name"]})[:3],
                "different_entity": old_names_other},
            "q4_valid_own_report_exists": {"annual_own_rows": len(annual_own),
                                           "with_gross_profit": len(with_gp)},
            "q5_gp_or_op_extracted": {
                "own_rows_detail": [{"tn": r["tracing_no"], "pe": r["period_end"],
                                     "gp": r["gross_profit"], "rev": r["revenue"],
                                     "op": r["operating_profit"], "unit": r["unit"],
                                     "unit_known": r["unit_known"],
                                     "audited": r["audited"], "consolidated": r["consolidated"]}
                                    for r in annual_own[:5]],
                "selected_row_extraction": ex},
            "q6_why_none": why,
            "q7_root_cause": cause,
            "sector": sec,
            "today_axes_score": bulk_new.get(sym, {}).get("score"),
            "head_score": bulk_old.get(sym, {}).get("score"),
        })

    by_cause = {c: sum(1 for x in cases if x["q7_root_cause"] == c) for c in CAUSES}
    by_cause = {k: v for k, v in by_cause.items() if v}
    selection_bugs = [x["symbol"] for x in cases if x["q7_root_cause"] == "selection_bug"]
    rep = {"db": a.db, "baseline": {"bulk_old": a.bulk_old, "ref_old": a.ref_old},
           "lost_margin_symbols": len(lost), "by_cause": by_cause,
           "gained_margin_symbols": len(gained), "gained": gained,
           "selection_bugs": selection_bugs, "cases": cases}
    d = os.path.dirname(a.out)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print("حاشیه‌هایِ رفته:", len(lost), "| تفکیک:", by_cause)
    print("حاشیه‌هایِ برگشتی (P-2):", len(gained), gained[:12])
    for x in cases:
        o = x["q1_old_selected_reference"]
        print("  %-11s tn=%s حاشیه=%s %s ← حالا tn=%s | خودیِ سالانه=%d با عدد=%d | %s"
              % (x["symbol"], o["tracing_no"], o["margin_pct_old_bulk"],
                 ("(شرکت دیگر)" if x["q3_old_row_named_another_company"]["different_entity"]
                  else ""), x["q2_new_selected_reference"]["margin_tracing_no"],
                 x["q4_valid_own_report_exists"]["annual_own_rows"],
                 x["q4_valid_own_report_exists"]["with_gross_profit"], x["q7_root_cause"]))
    if selection_bugs:
        print("SELECTION BUG (رفع لازم):", selection_bugs)
    print("out=%s" % a.out)
    return 1 if selection_bugs else 0


if __name__ == "__main__":
    raise SystemExit(main())
