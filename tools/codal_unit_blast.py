"""tools/codal_unit_blast.py — سرشماریِ «چند رأیِ امروز رویِ ردیفِ بی‌واحد سوار است».

مرحلۀ ۶ مأموریت (واحد و دورۀ مالی) قبلِ هر کد باید بداند هزینهٔ واقعیِ «بی‌واحد
نامعتبر است» چقدر است. سه چیز را می‌شمارد و هیچ‌کدام را حدس نمی‌زند:

  ۱) هر نوشتارِ `unit` در بانک + طبقۀ آن از `codal_units.classify` + ادعایِ
     مقیاسِ آن نوشتار (میلیون/میلیارد/هیچ). اگر روزی ردیفی «میلیارد تومان» بیاید
     و موتور هنوز ×۱e۶ بزند، این‌جا دیده می‌شود، نه درِ کارتِ کاربر.
  ۲) ردیف‌های بی‌واحد: `unit_norm IS NULL` (هیچِ منبعی واحد را نگفته) و
     ردیف‌های «واحد از خودِ شیت» (`unit` خالی، `unit_norm` پر) — دو حالتِ متفاوت
     که درِ شمارشِ خام یکی می‌شوند.
  ۳) دامنۀِ انفجار: از路径ِ حقیقیِ اسکرینر (`bulk_scan`) می‌پرسد کدامِ نمادهای
     رأیِ عدددارِ شاخص ۴/پتانسیل‌شان از ردیفی می‌آید که واحدش نامعلوم است، و
     چند نماد خودِ موتور «واحد مشکوک» گفته (`reconciled=False`).

فقط خواندنی. بانکِ عملیاتیِ مشترک هرگز نوشته نمی‌شود (حکمِ مأموریت و
`market.db` در `bors_config` از `market.db.lzma` بازسازی می‌شود).

usage:  PYTHONIOENCODING=utf-8 python tools/codal_unit_blast.py [--db market.db]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import codal_units as CU            # noqa: E402
import fts_engine as FE             # noqa: E402

_AR = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _norm(text: str) -> str:
    """مقایسهٔ مقیاس: ی/ك عربی ← فارسی، حذفِ فاصله و نیم‌فاصله، رقمِ فارسی ← لاتین."""
    s = (text or "").translate(_AR)
    for a, b in (("ي", "ی"), ("ك", "ک"), ("ة", "ه")):
        s = s.replace(a, b)
    return s.replace(" ", "").replace("\u200c", "")


_MILIARD = re.compile(r"ميليارد|میلیارد|بيليون|بیليون")
_TOMAN = re.compile(r"تومان|تومان")
_MILION = re.compile(r"ميليون|میلیون|مليون")
_RIAL = re.compile(r"ريال|ریال")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--out", default="_audit/codal_unit_blast.json")
    a = ap.parse_args()

    conn = sqlite3.connect("file:%s?mode=ro" % a.db, uri=True)
    conn.row_factory = sqlite3.Row
    out = {"db": a.db, "fs_rows": conn.execute(
        "SELECT COUNT(*) FROM financial_statements").fetchone()[0]}

    # ── ۱) هر نوشتارِ unit، طبقه‌بندی، و ادعایِ مقیاس ────────────────────────
    spell = collections.Counter()
    for r in conn.execute("SELECT unit, unit_norm, COUNT(*) n FROM financial_statements "
                          "GROUP BY 1,2"):
        spell[(r["unit"], r["unit_norm"])] += r["n"]
    scale_rows = collections.Counter()
    claims = []
    for (unit, un), n in spell.items():
        t = _norm(unit or "")
        claim = ("milliard" if _MILIARD.search(t) else
                 "million" if _MILION.search(t) else "none")
        toman = bool(_TOMAN.search(t))
        rial = bool(_RIAL.search(t))
        scale_rows["%s|%s" % (claim, "toman" if toman else "rial" if rial else "-")] += n
        got = CU.classify(unit)
        claims.append({"unit": unit, "rows": n, "stored_norm": un,
                       "recomputed": got, "text_scale": claim,
                       "currency": "toman" if toman else "rial" if rial else None,
                       "agree": got == un})
    out["unit_spellings"] = sorted(claims, key=lambda c: -c["rows"])
    out["scale_claims"] = dict(scale_rows)
    out["spelling_disagreements"] = [c for c in claims if not c["agree"]]

    # ── ۲) سه حالتِ «شواهدِ واحد» ────────────────────────────────────────────
    ev = {}
    for key, pred in (
            ("no_evidence", CU.MISSING_SQL),
            ("notice_empty_norm_set", "(unit IS NULL OR trim(unit)='') AND %s"
             % CU.PRESENT_SQL),
            ("both_present", "%s AND unit IS NOT NULL AND trim(unit)<>''" % CU.PRESENT_SQL)):
        ev[key] = conn.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) "
                               "FROM financial_statements WHERE " + pred).fetchone()[0:2]
    out["evidence"] = {"no_evidence_rows": ev["no_evidence"][0],
                       "no_evidence_symbols": ev["no_evidence"][1],
                       "from_sheet_only_rows": ev["notice_empty_norm_set"][0],
                       "from_sheet_only_symbols": ev["notice_empty_norm_set"][1],
                       "notice_and_norm_rows": ev["both_present"][0]}
    out["unit_counts"] = CU.unit_counts(conn)

    # ── ۳) دامنۀِ انفجار رویِ مسیرِ واقعیِ اسکرینر ───────────────────────────
    # ردیفِ مرجعِ سالانۀ هر نماد + واحدِ همان ردیف (از tracing_no، نه از حدس).
    ref_unit = {}
    syms = [r[0] for r in conn.execute(
        "SELECT DISTINCT symbol FROM financial_statements")]
    for s in syms:
        ref = FE.reference_annual(conn, s)
        if not ref:
            continue
        tn = ref.get("tracing_no")
        row = conn.execute("SELECT unit_norm, unit FROM financial_statements "
                           "WHERE tracing_no=?", (tn,)).fetchone()
        ref_unit[s] = (tn, row["unit_norm"] if row else None)
    out["symbols_with_reference_annual"] = len(ref_unit)
    out["reference_annual_unitless"] = sum(
        1 for s, (_tn, un) in ref_unit.items() if un is None)

    rows = FE.bulk_scan(conn)
    by_symbol = {r.get("symbol"): r for r in rows}
    moved = []
    for s, (tn, un) in ref_unit.items():
        r = by_symbol.get(s)
        if r is None:
            continue
        s2m = r.get("sales_to_mcap")
        pot = r.get("profit_potential_pct")
        if un is None and (s2m is not None or pot is not None):
            moved.append({"symbol": s, "tracing_no": tn,
                          "sales_to_mcap": s2m, "potential_pct": pot,
                          "basis": r.get("annualize_basis") or "",
                          "in_funnel": bool(r.get("passes") or r.get("score"))})
    out["bulk_rows"] = len(rows)
    out["suspect_unit_gate_rows"] = sum(
        1 for r in rows if r.get("annualize_reconciled") is False)
    out["verdicts_on_unitless_reference"] = len(moved)
    out["moved_examples"] = moved[:25]

    # چه مقدار از «فروش سالانه» از ردیفِ بی‌واحد می‌آید (مبنایِ صورتِ مالی)؟
    fs_basis = [r for r in rows if "صورت مالی" in (r.get("annualize_basis") or "")]
    out["funnel_rows_on_fs_basis"] = len(fs_basis)
    out["funnel_rows_on_fs_basis_unitless"] = sum(
        1 for r in fs_basis if ref_unit.get(r.get("symbol"), (None, "x"))[1] is None)

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    # گزارشِ خلاصه رویِ stdout
    print("fs_rows=%d  spellings=%d  scale_claims=%s"
          % (out["fs_rows"], len(claims), out["scale_claims"]))
    print("spelling_disagreements=%d" % len(out["spelling_disagreements"]))
    print("unit_counts=%s" % (out["unit_counts"],))
    print("evidence=%s" % (out["evidence"],))
    print("reference_annual: %d نماد، %d تایشان ردیفِ مرجعِ بی‌واحد"
          % (out["symbols_with_reference_annual"], out["reference_annual_unitless"]))
    print("bulk_rows=%d  suspect_unit_gate=%d  verdicts_on_unitless_reference=%d"
          % (out["bulk_rows"], out["suspect_unit_gate_rows"],
             out["verdicts_on_unitless_reference"]))
    print("funnel rows on FS basis=%d (unitless=%d)"
          % (out["funnel_rows_on_fs_basis"], out["funnel_rows_on_fs_basis_unitless"]))
    print("out=%s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
