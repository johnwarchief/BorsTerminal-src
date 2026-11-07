# -*- coding: utf-8 -*-
"""tools/phase5f_official_ratios_audit.py — Stage 3ِ دورِ بستۀ Phase 5

هر نسبتِ **رسمی** را از ستون‌هایِ خودِ مبدأ دوباره می‌سازد و با `ratio`ِ ذخیره‌شده مقابله
می‌کند؛ بعد همان ردیف‌ها را از دو دریچۀِ ورودِ زنجیرۀِ تعدیلِ فعلیِ محصول می‌گذراند:

  • `adjustment_engine.event_factor(KIND_SOURCE_RATIO)`  → کرانِ [_RATIO_MIN=1e-4, _RATIO_MAX=1e4]
  • `api/chart.py::_ledger_events_for`                   → فقط `r > 0` و `|r−1| > ADJ_TOL`

چرا این دو کنارِ هم: موتورِ canonical می‌گوید «خارجازکران = نامعتبر، واردِ زنجیره نشود»،
و مسیرِ تولیدیِ چارت همین ردیف را **بی‌علامت** می‌پذیرد. اگر تفاوتِ این دو رویِ دادهٔ واقعی
صفر باشد، بحثِ نظری است؛ اگر نباشد، یکِ نقصِ عددیِ واقعی درِ ضریبِ کاربر است. حدس نمی‌زنیم —
می‌سنجیم (قیدِ مأموریت: «ردیف‌های نامعتبر نباید وارد زنجیره شوند»).

فقط‌خواندنی: `mode=ro`. هیچِ نوشتنی برِ `market.db` انجام نمی‌شود.
"""
import csv
import io
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import adjustment_engine as AE                      # noqa: E402
import bors_config as BC                            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("BORS_DB", BC.DB_PATH)
OUT = os.path.join(ROOT, "_audit", "RA365-PHASE5F-RATIO-BOUNDARIES.csv")
REL_TOL = 1e-9      # تفاوتِ گردکردنِ ۸ رقمیِ مبدأ با نسبتِ بی‌گرد


def rel(a, b):
    """نسبتِ واگرایی؛ None یعنی «قابلِ محاسبه نیست» (نه صفر)."""
    if a is None or b is None:
        return None
    if b == 0:
        return None
    return abs(a / b - 1.0)


def exact_match(stored, recomputed):
    d = rel(stored, recomputed)
    return d is not None and d <= REL_TOL


def main():
    con = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    # ADJ_TOLِ خودِ چارت را ازِ همان ماژول می‌خوانیم، نه ازِ عددِ تایپ‌شده
    import api.chart as CH
    adj_tol = float(getattr(CH, "ADJ_TOL", 0.0))
    print(f"دریچۀِ چارت: ADJ_TOL={adj_tol} | دریچۀِ موتور: [{AE._RATIO_MIN}, {AE._RATIO_MAX}]")

    rows_out = []
    stats = {
        "pa_rows": 0, "pa_recompute_exact": 0, "pa_recompute_off": 0,
        "pa_engine_reject": 0, "pa_chart_accepts_engine_rejects": 0,
        "sc_rows": 0, "sc_recompute_exact": 0, "sc_recompute_off": 0,
        "sc_engine_reject": 0, "sc_chart_accepts_engine_rejects": 0,
        "worst_chart_only_ratio": None, "worst_chart_only_symbol": None,
    }

    for r in con.execute("SELECT ins_code, symbol, d_even, ratio, p_closing, p_closing_not_adjusted,"
                         " source FROM price_adjust_events ORDER BY ins_code, d_even"):
        stats["pa_rows"] += 1
        recomputed = None
        try:
            recomputed = round(float(r["p_closing"]) / float(r["p_closing_not_adjusted"]), 8)
        except (TypeError, ValueError, ZeroDivisionError):
            recomputed = None
        stored = float(r["ratio"]) if r["ratio"] is not None else None
        exact = exact_match(stored, recomputed)
        stats["pa_recompute_exact" if exact else "pa_recompute_off"] += 1
        _ratio_of, status = AE.event_factor({"kind": AE.KIND_SOURCE_RATIO, "date": r["d_even"],
                                         "ratio": stored})
        accepted_by_chart = stored is not None and stored > 0 and abs(stored - 1.0) > adj_tol
        rejected = status != AE.OK
        if rejected:
            stats["pa_engine_reject"] += 1
        if rejected and accepted_by_chart:
            stats["pa_chart_accepts_engine_rejects"] += 1
            worst = abs(stored - 1.0)
            if stats["worst_chart_only_ratio"] is None or worst > stats["worst_chart_only_ratio"]:
                stats["worst_chart_only_ratio"] = round(worst, 6)
                stats["worst_chart_only_symbol"] = f"{r['symbol']}@{r['d_even']} ratio={stored}"
            rows_out.append({"table": "price_adjust_events", "ins_code": r["ins_code"],
                             "symbol": r["symbol"], "d_even": r["d_even"], "stored_ratio": stored,
                             "recomputed": recomputed, "engine_status": status,
                             "chart_accepts": accepted_by_chart, "divergence": "ENGINE_REJECT_CHART_ACCEPTS"})

    for r in con.execute("SELECT ins_code, symbol, d_even, ratio, shares_old, shares_new, source"
                         " FROM share_change_events ORDER BY ins_code, d_even"):
        stats["sc_rows"] += 1
        recomputed = None
        try:
            recomputed = round(float(r["shares_old"]) / float(r["shares_new"]), 8)
        except (TypeError, ValueError, ZeroDivisionError):
            recomputed = None
        stored = float(r["ratio"]) if r["ratio"] is not None else None
        exact = exact_match(stored, recomputed)
        stats["sc_recompute_exact" if exact else "sc_recompute_off"] += 1
        _ratio_of, status = AE.event_factor({"kind": AE.KIND_SOURCE_RATIO, "date": r["d_even"],
                                         "ratio": stored})
        accepted_by_chart = stored is not None and stored > 0 and abs(stored - 1.0) > adj_tol
        rejected = status != AE.OK
        if rejected:
            stats["sc_engine_reject"] += 1
        if rejected and accepted_by_chart:
            stats["sc_chart_accepts_engine_rejects"] += 1
            worst = abs(stored - 1.0)
            if stats["worst_chart_only_ratio"] is None or worst > stats["worst_chart_only_ratio"]:
                stats["worst_chart_only_ratio"] = round(worst, 6)
                stats["worst_chart_only_symbol"] = f"{r['symbol']}@{r['d_even']} ratio={stored}"
            rows_out.append({"table": "share_change_events", "ins_code": r["ins_code"],
                             "symbol": r["symbol"], "d_even": r["d_even"], "stored_ratio": stored,
                             "recomputed": recomputed, "engine_status": status,
                             "chart_accepts": accepted_by_chart,
                             "divergence": "ENGINE_REJECT_CHART_ACCEPTS"})

    con.close()

    with io.open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        if rows_out:
            w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
            w.writeheader()
            w.writerows(rows_out)

    print("\n== نسبتِ رسمی، دوباره‌سازی‌شده ازِ ستون‌هایِ خودِ مبدأ ==")
    print(f" price_adjust_events : ردیف={stats['pa_rows']}  "
          f"بازسازیِ دقیق (±{REL_TOL:g})={stats['pa_recompute_exact']}  واگرایی={stats['pa_recompute_off']}")
    print(f" share_change_events : ردیف={stats['sc_rows']}  "
          f"بازسازیِ دقیق={stats['sc_recompute_exact']}  واگرایی={stats['sc_recompute_off']}")
    print("\n== ردیف‌هایی که موتورِ canonical رد می‌کند اما چارت می‌پذیرد ==")
    print(f" price_adjust_events : engine_reject={stats['pa_engine_reject']}  "
          f"و چارت‌پذیرفت={stats['pa_chart_accepts_engine_rejects']}")
    print(f" share_change_events : engine_reject={stats['sc_engine_reject']}  "
          f"و چارت‌پذیرفت={stats['sc_chart_accepts_engine_rejects']}")
    print(f" بدترینِ واگراییِ چارت‌پذیرفته: {stats['worst_chart_only_ratio']}  "
          f"({stats['worst_chart_only_symbol']})")
    print(f" ردیف‌هایِ واگاییِ کاملِ دو دریچه: {len(rows_out)} → {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
