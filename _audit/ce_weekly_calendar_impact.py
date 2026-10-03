# -*- coding: utf-8 -*-
"""_audit/ce_weekly_calendar_impact.py — اثرِ تقویمِ هفتگی بر رأیِ دروازۀ اطمینان

سؤالِ دقیق: اگر `_week_key`ِ confidence_engine از سطلِ ISO (دوشنبه‌محور) به سطلِ
شنبه‌محورِ خودِ همین برنامه (`api/chart.py` `_fts_resample`) عوض شود، چند تا از
رأی‌هایِ دروازه عوض می‌شوند؟ بندِ §۱-ح-۵ رویِ ۲۴ نماد «۰ از ۲۴» خوانده بود؛ این
سنجش همان کار را رویِ نمادِ بیشتر و با شمارشِ صریحِ پوشش می‌کند (چون طبقِ
`docs/parity-checks` یک مقابله بی‌حالتِ شکست، عددِ «صفر»ِ بی‌معنی می‌دهد).

سه سنجه برایِ هر نماد، رویِ یک سریِ روزانۀ یکسان:
  • bullish (بستۀ آخرِ هفتگی > MA52) — همان چیزی که weak را می‌سازد
  • oversold (RSI7 ≤ آستانه)
  • خودِ عددِ MA52 و RSI7

هیچ کدی عوض نمی‌شود؛ فقط اندازه‌گیری. اجرا:
  PYTHONIOENCODING=utf-8 py -3.14 _audit/ce_weekly_calendar_impact.py
"""
import datetime as dt
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import confidence_engine as CE  # noqa: E402

DB = os.environ.get("PROBE_DB", "market.db")
OUT = os.environ.get("PROBE_OUT", "_audit/ce_weekly_calendar_impact.json")
CAP = int(os.environ.get("PROBE_LIMIT", "0"))    # 0 = همه


def sat_key(d):
    """شنبه‌محور — همان قاعدۀ `api/chart.py` (`d - timedelta((weekday+2)%7)`)."""
    return (d - dt.timedelta(days=(d.weekday() + 2) % 7)).isoformat()


def weekly_by(rows, keyfn):
    """ردیفِ نزولی (date, close) → بستۀ هر سطل = نخستینِ ردیفِ آن کلید (قاعدۀ خودِ CE)."""
    out, seen = [], set()
    for date_s, close in rows:
        try:
            d = dt.date.fromisoformat(str(date_s)[:10])
        except ValueError:
            continue
        k = keyfn(d)
        if k in seen:
            continue
        seen.add(k)
        out.append(float(close))
    return out


def gate(closes_newest_first, cfg):
    """همان منطقِ `_weekly_gate` ولی با سریِ آماده — تا تقویم تنها متغیر باشد."""
    need = int(cfg["tech_weekly_ma"])
    res = {"bullish": None, "oversold": None, "ma52": None, "rsi": None, "bars": len(closes_newest_first)}
    if len(closes_newest_first) >= need and closes_newest_first[0] > 0:
        ma = sum(closes_newest_first[:need]) / float(need)
        res["ma52"] = ma
        res["bullish"] = bool(closes_newest_first[0] > ma)
        r = CE._rsi(closes_newest_first, int(cfg["tech_weekly_rsi"]))
        res["rsi"] = r
        if r is not None:
            res["oversold"] = bool(r <= float(cfg["tech_weekly_rsi_oversold"]))
    return res


def main():
    conn = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    cfg = CE._cfg()
    q = conn.execute(
        "SELECT symbol, date, close FROM price_history WHERE close > 0 ORDER BY symbol, date DESC")
    cur, rows, sym = None, [], None
    stats = {"symbols": 0, "qualified_both": 0, "verdict_flip": 0, "oversold_flip": 0,
             "ma52_diff_pct": [], "rsi_diff": [], "bars_diff": [], "iso_only_qual": 0,
             "sat_only_qual": 0}
    flips = []

    def flush(sym_, rows_):
        if not sym_ or len(rows_) < 200:
            return
        g_iso = gate(weekly_by(rows_, lambda d: d.isocalendar()[:2]), cfg)
        g_sat = gate(weekly_by(rows_, sat_key), cfg)
        # سطلِ شنبه‌محور با کلیدِ رشته‌ای: نخستینِ ردیفِ هر شنبه = بستۀ همان هفته
        if g_iso["bullish"] is None and g_sat["bullish"] is None:
            return
        stats["symbols"] += 1
        both = g_iso["bullish"] is not None and g_sat["bullish"] is not None
        if both:
            stats["qualified_both"] += 1
            if g_iso["bullish"] != g_sat["bullish"]:
                stats["verdict_flip"] += 1
                flips.append({"symbol": sym_, "iso": g_iso, "sat": g_sat})
            if g_iso["oversold"] != g_sat["oversold"]:
                stats["oversold_flip"] += 1
            if g_iso["ma52"] and g_sat["ma52"]:
                stats["ma52_diff_pct"].append(
                    abs(g_iso["ma52"] - g_sat["ma52"]) / g_sat["ma52"] * 100.0)
            if g_iso["rsi"] is not None and g_sat["rsi"] is not None:
                stats["rsi_diff"].append(abs(g_iso["rsi"] - g_sat["rsi"]))
            stats["bars_diff"].append(g_iso["bars"] - g_sat["bars"])
        elif g_iso["bullish"] is not None:
            stats["iso_only_qual"] += 1
        else:
            stats["sat_only_qual"] += 1

    for s, d, c in q:
        if s != cur:
            flush(cur, rows)
            cur, rows = s, []
            if CAP and stats["symbols"] >= CAP:
                break
        rows.append((d, c))
    flush(cur, rows)
    conn.close()

    def med(xs):
        xs = sorted(xs)
        return round(xs[len(xs) // 2], 3) if xs else None

    def p90(xs):
        xs = sorted(xs)
        return round(xs[min(len(xs) - 1, int(len(xs) * 0.9))], 3) if xs else None

    out = {
        "symbols_measured": stats["symbols"],
        "qualified_both": stats["qualified_both"],
        "verdict_flip_bullish": stats["verdict_flip"],
        "oversold_flip": stats["oversold_flip"],
        "iso_only_qualified": stats["iso_only_qual"],
        "sat_only_qualified": stats["sat_only_qual"],
        "ma52_diff_pct_median": med(stats["ma52_diff_pct"]),
        "ma52_diff_pct_p90": p90(stats["ma52_diff_pct"]),
        "ma52_diff_pct_max": round(max(stats["ma52_diff_pct"]), 3) if stats["ma52_diff_pct"] else None,
        "rsi_diff_median": med(stats["rsi_diff"]),
        "rsi_diff_p90": p90(stats["rsi_diff"]),
        "weekly_bars_extra_iso_median": med(stats["bars_diff"]),
        "flips": flips[:40],
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\nمنفی‌کنترل: اگر تقویم‌ها یکسان بودند verdict_flip=0 و ma52_diff=0 می‌شد؛ "
          "پس صفرِ رأیی یعنی «اثرِ واقعی ندارد»، نه «سنجش اجرا نشد» "
          f"(پوشش: {out['symbols_measured']} نماد، {out['qualified_both']} واجدِ شرط در هر دو).")


if __name__ == "__main__":
    main()
