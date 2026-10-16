# -*- coding: utf-8 -*-
"""منشأیِ هر جابه‌جاییِ رأی: کدامِ قاعده، کدامِ ردیف، چه عددی.

تغییرِ امتیاز به‌خودی‌خود باگ نیست؛ اما باید معلوم باشد از کجاست. سه نقصِ این
سنجش در دورِ پیشین اصلاح شد:

۱) منطقِ وارونه: «خاموش‌کردنِ قاعدۀ X چیزی را نسبتِ امروز تغییر نداد» یعنی X
   بی‌اثر است، اما ابزار آن را به‌عنوان منشأ ثبت می‌کرد — پس ۲۸ جابه‌جایی همه
   `period_resolution` می‌شدند و `other_entity` هرگز دیده نمی‌شد.
۲) «پیش» ساختگی: HEAD با خاموش‌کردنِ دو قاعده درِ کدِ امروز ساخته می‌شد، پس
   لایۀ هویت و نردبانِ P-2 و خوانندۀ EPS هر سه درِ «پیش» می‌ماندند و هیچ
   جابه‌جاییِ آن‌ها ثبت نمی‌شد. حالا `--old` خروجیِ واقعیِ `5c97b5c` است
   (`tools/codal_bulk_dump.py --root <worktreeِ 5c97b5c>`).
۳) بی‌هیچِ پرچمِ قرمزی: اگر جابه‌جایی را هیچ قاعدۀ قابل‌خاموش‌کردنی توضیح
   نمی‌داد، ابزار باز هم یک برچسب می‌داد. حالا چنین موردی `UNEXPLAINED`
   می‌شود و خروجِ ۱ است — چون یعنی نقصِ تازه.

قاعده‌ای منشأ شمرده می‌شود که خاموش‌کردنشِ *تنها* رأی‌های جابه‌شده را به
مقادیرِ HEAD برگرداند. قاعده‌ای که اثر دارد ولی بازگردانی نمی‌کند، بخشی از
تعامُل است و جدا گزارش می‌شود.

usage: PYTHONIOENCODING=utf-8 python tools/codal_verdict_move_causes.py \
         --old _audit/bulk_old_5c97b5c_2026-10-13.json
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

import codal_periods as CP                  # noqa: E402
import fts_engine as FE                     # noqa: E402
import symbol_identity as SI                # noqa: E402

_real_suffix = FE.title_entity_suffix
_real_months = CP.effective_months
_real_key = SI.key
_real_pred = SI.pred
AXES = {"1_growth": "i1_pass", "2_eps_trend": "i2_pass", "3_gross_margin": "i3_pass",
        "4_sales_to_mcap": "i4_pass", "5_industry": "i5_pass"}
NUMS = ("gross_margin", "rev_growth", "sales_to_mcap", "eps_last", "annual_sales_bt")


def _off_entity():
    FE.title_entity_suffix = lambda title: ""


def _off_months():
    def raw(period_end, period_months, title):
        try:
            n = int(period_months) if period_months is not None and str(period_months).strip() else None
        except (TypeError, ValueError):
            n = None
        return n, ("column" if n is not None else None)
    CP.effective_months = raw


def _off_identity(conn):
    """لایۀ هویت را به «نوشتارِ خام، بی‌گروه‌بندی» برمی‌گرداند (همان v9.10).

    `SI.reset_cache()` فراموش‌نشدنی است: نقشۀ `_CACHE` نوشتارها را با `key()`
    پیشین بسته شده، پس بی‌پاک‌کردنشِ بعدِ patch، خاموش‌کردنِ هویت بی‌صدا هیچ
    اثری نمی‌کرد و آمارِ منشأ دوباره گم می‌شد (همین نقصِ «سنسور کور»).
    """
    SI.key = lambda s: str(s or "").strip()
    SI.pred = lambda conn, col, symbol, domain=None: (col + " = ?", (str(symbol or ""),))
    SI.reset_cache()
    FE.register_sql(conn)          # `sym_key` درِ SQL دوباره باید patch شود


def _restore(conn=None):
    FE.title_entity_suffix = _real_suffix
    CP.effective_months = _real_months
    SI.key = _real_key
    SI.pred = _real_pred
    SI.reset_cache()
    if conn is not None:
        FE.register_sql(conn)


def _off_margin_ladder():
    """نردبانِ P-2 را خاموش می‌کند: مرجعِ شاخص ۳ = همان مرجعِ عمومی، بی‌تنزلِ need."""
    FE.MARGIN_NEED = ()


def _restore_ml():
    FE.MARGIN_NEED = ("gross_profit", "revenue")


def run_bulk(conn):
    return {r["symbol"]: r for r in FE.bulk_scan(conn, cfg=None)}


def reach(conn) -> dict:
    """چند ردیفِ واقعی زیرِ هر خاموش‌سازی تغییر می‌کند (صرف‌نظر از رأی)."""
    ent = per = 0
    for (title, pm, pe) in conn.execute(
            "SELECT title, period_months, period_end FROM financial_statements"):
        t = str(title or "")
        if _real_suffix(t):
            ent += 1
        try:
            raw = int(pm) if pm is not None and str(pm).strip() else None
        except (TypeError, ValueError):
            raw = None
        eff, _src = _real_months(pe, pm, t)
        if eff != raw:
            per += 1
    ms_ent = sum(1 for (t,) in conn.execute("SELECT title FROM monthly_sales")
                 if t and _real_suffix(str(t)))
    ladder = conn.execute(
        "SELECT COUNT(*) FROM financial_statements WHERE period_months >= 12 AND "
        "(gross_profit IS NULL OR revenue IS NULL OR CAST(revenue AS REAL) <= 0)"
        "").fetchone()[0]
    syms = set()
    for tbl in ("financial_statements", "monthly_sales", "codal_notices"):
        try:
            syms |= {str(r[0]) for r in conn.execute(
                "SELECT DISTINCT symbol FROM " + tbl) if r[0]}
        except sqlite3.OperationalError:
            pass
    fam = sum(1 for s in sorted(syms) if len(SI.variants(conn, s)) > 1)
    # دست‌یابیِ نردبانِ P-2: چند نماد که مرجعِ حاشیه‌شان واقعاً با مرجعِ عمومی فرق
    # می‌کند (یعنی تنزل occurrence دارد، نه فقط یک قاعدۀ رویِ کاغذ).
    descent = 0
    for s in sorted(syms):
        try:
            g = FE.reference_annual(conn, s)
            m = FE.margin_reference(conn, s, g)
        except Exception:
            continue
        if g and m and (g.get("tracing_no") != m.get("tracing_no")):
            descent += 1
    return {"other_entity": ent + ms_ent, "period_resolution": per,
            "identity_family": fam, "margin_basis_p2": descent}


def axes_of(row):
    return tuple((row or {}).get(col) for col in AXES.values())


def axes_diff(o, n):
    o = o or {}
    n = n or {}
    return {k: (o.get(col), n.get(col)) for k, col in AXES.items() if o.get(col) != n.get(col)}


def nums_diff(o, n):
    o = o or {}
    n = n or {}
    return {k: (o.get(k), n.get(k)) for k in NUMS if o.get(k) != n.get(k)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--old", required=True, help="خروجیِ real HEAD از codal_bulk_dump.py")
    ap.add_argument("--out", default="_audit/codal_verdict_move_causes.json")
    a = ap.parse_args()
    if not os.path.exists(a.old):
        print("BLOCKED: baseline نیست — «پیش» را از کدِ امروز نساز:", a.old)
        return 2
    with open(a.old, encoding="utf-8") as fh:
        blob = json.load(fh)
    old = blob["rows"]
    print("baseline: root=%s rows=%d" % (blob.get("root"), len(old)))

    conn = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True)
    conn.row_factory = sqlite3.Row
    FE.register_sql(conn)

    today = run_bulk(conn)
    ab = {}
    for name, apply_ in (("other_entity", _off_entity),
                         ("period_resolution", _off_months),
                         ("margin_basis_p2", _off_margin_ladder)):
        apply_()
        try:
            ab[name] = run_bulk(conn)
        finally:
            _restore_ml()
            _restore(conn)
    _off_identity(conn)
    try:
        ab["identity_family"] = run_bulk(conn)
    finally:
        _restore(conn)

    # کنترلِ سنسور دو لایه است. **دست‌یابی** (reach): خاموش‌سازی باید دستِ‌کم یک
    # ردیفِ واقعی را ببیند، وگرنه patch به path نرسیده و هر «UNEXPLAINED» بعدی
    # بی‌معناست. **اثرِ رأی**: صفر بودنش خبر است، نه نقصِ ابزار — سنجشِ دورِ
    # قبل دقیقاً همین را برایِ تعیینِ دوره نشان داد (هیچ رأیی با آن جابه‌جا نمی‌
    # شود، فقط پنجره از خوانشِ نادرستِ ردیف‌هایِ متناقض در امان می‌ماند).
    reach_ = reach(conn)
    vote_effect = {k: sum(1 for s, t in today.items()
                          if axes_of(ab[k].get(s)) != axes_of(t)
                          or (ab[k].get(s) or {}).get("score") != t.get("score")) for k in ab}
    blind = [k for k in ab if reach_.get(k, 0) == 0]
    if blind:
        print("BLOCKED: خاموش‌سازیِ کور (هیچ ردیفی را نمی‌بیند) —", blind)
        return 2
    print("سنسور:", {k: "دست‌یابی=%d اثرِرأی=%d" % (reach_[k], vote_effect[k]) for k in ab})

    causes, rows, unexplained = {}, [], []
    for s, t in today.items():
        h = old.get(s) or {}
        moved = axes_diff(h, t)
        if not moved:
            continue
        # کدامِ قاعده تنها کافی بود؟ خاموش‌کردنش باید رأی را به HEAD برگرداند.
        restores = [k for k, out in ab.items()
                    if axes_of(out.get(s)) == axes_of(h) and axes_of(out.get(s)) != axes_of(t)]
        affects = [k for k, out in ab.items() if axes_of(out.get(s)) != axes_of(t)]
        if len(restores) == 1:
            why = restores
        elif restores:
            why = restores                      # بیش از یک قاعده، هر دو بازگرداننده
        elif len(affects) == 1:
            why = [affects[0] + "+interaction"]
        elif not affects:
            why = ["UNEXPLAINED"]
        else:
            why = ["interaction"]
        key = "+".join(sorted(why))
        causes[key] = causes.get(key, 0) + 1
        rec = {"symbol": s, "axes": moved, "cause": key,
               "head_axes": list(axes_of(h)), "today_axes": list(axes_of(t)),
               "head_score": h.get("score"), "today_score": t.get("score"),
               "numbers": nums_diff(h, t)}
        rows.append(rec)
        if key == "UNEXPLAINED":
            unexplained.append(rec)

    score_moves = [r for r in rows if (r["head_score"] or 0) != (r["today_score"] or 0)]
    num_moves = [r for r in rows if r["numbers"]]
    # نمادهایی که رأی‌شان جابه‌جا نشد ولی عددِ منتشرشده‌شان تغییر کرد
    quiet_num = [s for s, t in today.items() if not axes_diff(old.get(s) or {}, t)
                 and nums_diff(old.get(s) or {}, t)]
    fam = sum(1 for r in rows if len(SI.variants(conn, r["symbol"])) > 1)

    rep = {"db": a.db, "baseline": a.old, "universe_old": len(old), "universe_today": len(today),
           "moved_verdict_rows": len(rows), "by_cause": causes,
           "score_moves": len(score_moves), "rows_with_number_moves": len(num_moves),
           "rows_with_number_moves_only": len(quiet_num),
           "rows_in_two_spelling_family": fam,
           "axis_tally": {k: sum(1 for x in rows if k in x["axes"]) for k in AXES},
           "unexplained": unexplained, "examples": rows[:60]}
    d = os.path.dirname(a.out)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print("جابه‌جاییِ رأی:", len(rows), "| منشأ:", causes)
    print("تغییرِ امتیاز:", len(score_moves), "| تغییرِ عدد:", len(num_moves),
          "| فقط عدد (بی‌تغییرِ رأی):", len(quiet_num), "| در خانوادۀ دو-نوشتاری:", fam)
    print("محور:", rep["axis_tally"])
    for x in rows[:10]:
        print("   %-10s %-30s %-14s %s → %s" % (x["symbol"],
              json.dumps(x["axes"], ensure_ascii=False)[:30], x["cause"],
              x["head_score"], x["today_score"]))
    if unexplained:
        print("UNEXPLAINED (باید رفع شود):", [x["symbol"] for x in unexplained][:20])
    print("out=%s" % a.out)
    return 1 if unexplained else 0


if __name__ == "__main__":
    raise SystemExit(main())
