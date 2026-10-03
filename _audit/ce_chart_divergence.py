# -*- coding: utf-8 -*-
"""_audit/ce_chart_divergence.py — سنجشِ عددیِ واگراییِ confidence_engine با موتورِ FTSِ chart.py

کارِ دورِ E، اولویتِ ۲: دو موتور از یک سریِ کندلِ روزانهٔ *یکسان* (از `price_history`،
صعودی، بدونِ شبکه) رأی می‌گیرند و اختلافِ عددیِ سه محورِ ادعاشده اندازه گرفته می‌شود:

  ۱) ترازِ هفتگی   : شمارشِ سطل، بستۀ آخر، MA52، RSI هفتگی (دورۀ ۷ در اطمینان در
                     برابر ۵ در ساعت شنی) و رأیِ صعودی/ضعیف در برابر trendW.
                     **پس از ۱۴۰۵-۰۷-۱۲** که `_week_key` به سطلِ شنبه‌محورِ
                     `_fts_resample` هم‌سان شد، شمارِ سطل و MA52 در ۴۰/۴۰ نماد برابر
                     است؛ آنچه می‌ماند دورۀ متفاوتِ RSI و تعریفِ متفاوتِ رأی
                     (MA-محور در برابرِ پیوت-محور) است — جدولِ §۱-ح-۵.
  ۲) مبنایِ فیبو   : CE خطی رویِ پنجرۀ ۶۰ نشستی با باند [۰.۵، ۰.۶۸]؛
                     chart لگاریتمی رویِ پایۀ ساختاری با کمربندهای ۳۳-۴۰ و ۶۱.۸-۷۰.
  ۳) حاشیۀ CHoCH  : CE بی‌حاشیه (بسته > پیوتِ k=۱، فقط شکستِ صعودی)؛
                     chart حاشیۀ ۰.۳٪ با پیوتِ k=۳ و هر دو جهت.

هیچ چیزی اینجا «درست» اعلام نمی‌شود؛ فقط عددِ اختلاف ثبت می‌شود تا تصمیمِ معماری
(رأیِ دومِ مستقل در برابرِ هم‌راستایی با موتورِ کاننیکال) با مدرک گرفته شود.
هیچ آستانه یا فرمولِ تازه‌ای درِ این اسکریپت ساخته نمی‌شود — هر دو موتور
دعوتِ مستقیمِ خودشان‌اند با پیش‌فرضِ خودشان.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.chart as CH              # noqa: E402
import confidence_engine as CE      # noqa: E402

DB = os.environ.get("PROBE_DB", "market.db")
LIMIT = int(os.environ.get("PROBE_LIMIT", "14"))
OUT = os.environ.get("PROBE_OUT", "_audit/ce_chart_divergence.json")


def symbols(conn):
    """نمونۀ لایه‌ای، نه «عمیق‌ترین‌ها»: برداشت از همۀ جدول با گامِ ثابت تا
    رژیم‌هایِ متفاوت (صعودی/نزولی/رنج) هم دیده شوند — با `n DESC` تنها ۱۴ نمادِ
    پرعمقِ هم‌رژیم انتخاب می‌شدند و شمارِ واگراییِ رأی صفرِ گمراه‌کننده می‌داد."""
    rows = conn.execute(
        "SELECT symbol, COUNT(*) n FROM price_history GROUP BY symbol "
        "HAVING n >= 200 ORDER BY symbol").fetchall()
    seen, uniq = set(), []
    for sym, _n in rows:
        s = (sym or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    if len(uniq) <= LIMIT:
        return uniq
    step = max(1, len(uniq) // LIMIT)
    return [uniq[i] for i in range(0, len(uniq), step)][:LIMIT]


def daily(conn, sym):
    """سریِ صعودیِ یکسان؛ تکراریِ روز با همان قاعدۀ تولید (پرحجم‌تر می‌ماند)."""
    raw = conn.execute(
        "SELECT date, open, high, low, close, volume FROM price_history "
        "WHERE symbol = ? ORDER BY date DESC, volume DESC", (sym,)).fetchall()
    seen, rows = set(), []
    for r in raw:
        if r[0] in seen:
            continue
        seen.add(r[0])
        rows.append(r)
    rows.reverse()
    out = []
    for d, o, h, l, c, v in rows:
        try:
            o, h, l, c = float(o or 0), float(h or 0), float(l or 0), float(c or 0)
        except (TypeError, ValueError):
            continue
        if c <= 0 or h <= 0 or l <= 0:
            continue
        out.append({"time": d, "open": o or c, "high": h, "low": l, "close": c,
                    "volume": float(v or 0)})
    return out


def desc_tuples(candles):
    """همان ردیف‌ها با قراردادِ CE: تازه‌ترین اول، پنج‌تاییِ (date, close, high, low, volume)."""
    return [(c["time"], c["close"], c["high"], c["low"], c["volume"]) for c in reversed(candles)]


def pct(a, b):
    """اختلافِ نسبیِ a به b، با درصدِ گردِ سه‌رقمی؛ None بی‌مخرجِ معتبر."""
    if a is None or b is None:
        return None
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    if b == 0:
        return None
    return round(abs(a - b) / abs(b) * 100.0, 3)


def one(conn, sym, cfg):
    candles = daily(conn, sym)
    if len(candles) < 200:
        return None
    fts = CH._fts_analyze_candles(sym, [dict(c) for c in candles])
    rows_d = desc_tuples(candles)
    gates = CE._weekly_gate(rows_d, cfg)
    closes = [c["close"] for c in reversed(candles)]
    highs = [c["high"] for c in reversed(candles)]
    lows = [c["low"] for c in reversed(candles)]
    vols = [c["volume"] for c in reversed(candles)]
    setups = CE._daily_setups(closes, highs, lows, vols, cfg)

    hg = fts.get("hourglass") or {}
    tw = (fts.get("trend") or {}).get("W") or {}
    mx = (fts.get("trend") or {}).get("matrix") or {}
    fib = fts.get("fib") or {}
    z1 = fib.get("zone_33_40") or {}
    z2 = fib.get("zone_618_70") or {}
    chart_fib_in = bool(z1.get("in_zone") or z2.get("in_zone"))
    ch = fts.get("choch") or {}
    chart_choch = bool(ch.get("bullish")) or bool(ch.get("bearish"))

    return {
        "symbol": sym,
        "bars": len(candles),
        "weekly": {
            "bars_ce": gates.get("w_bars"), "bars_chart": hg.get("weekly_bars"),
            "close_ce": round(closes[0], 2) if closes else None,
            "close_chart": hg.get("weekly_close"),
            "ma52_ce": None if gates.get("ma52") is None else round(gates["ma52"], 2),
            "ma52_chart": hg.get("ma52"),
            "ma52_pct": pct(gates.get("ma52"), hg.get("ma52")),
            "rsi_ce7": None if gates.get("rsi7") is None else round(gates["rsi7"], 1),
            "rsi_chart5": hg.get("weekly_rsi5"),
            "ce_bullish": gates.get("bullish"), "ce_weak": gates.get("weak"),
            "chart_trendW": tw.get("trend"), "chart_basis": tw.get("basis"),
            "chart_decision": mx.get("decision"),
        },
        "fib": {
            "ce_flag": setups.get("fibonacci"),
            "ce_basis": "linear/60-bar band 0.50-0.68",
            "chart_in_zone": chart_fib_in,
            "chart_basis": "log/structural-leg belts 33-40 & 61.8-70",
            "chart_base_high": fib.get("retrace_base_high"),
            "chart_base_low": fib.get("retrace_base_low"),
            "chart_zone_33_40": [z1.get("lo"), z1.get("hi")] if z1 else None,
            "chart_zone_618_70": [z2.get("lo"), z2.get("hi")] if z2 else None,
        },
        "choch": {
            "ce_flag": setups.get("choch"),
            "ce_basis": "margin=0 / k=1 pivot / up-break only",
            "chart_bullish": ch.get("bullish"), "chart_bearish": ch.get("bearish"),
            "chart_level": ch.get("level"),
            "chart_margin": 0.003,
            "chart_basis": "margin=0.003 / k=3 pivot / both directions",
        },
    }


def verdict_flip(r):
    """رأیِ هفتگی: CE «ضعیف» می‌گوید (بسته زیر MA52) یا chart «REJECT» — آیا یکی دیگر را تأیید می‌کند؟"""
    ce_down = bool(r["weekly"]["ce_weak"])
    chart_reject = r["weekly"]["chart_decision"] == "REJECT"
    return ce_down != chart_reject


def main():
    conn = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    cfg = CE._cfg()
    rows = [r for r in (one(conn, s, cfg) for s in symbols(conn)) if r]
    conn.close()

    agg = {
        "symbols": len(rows),
        "weekly_bar_count_diff": sum(1 for r in rows if r["weekly"]["bars_ce"] != r["weekly"]["bars_chart"]),
        "ma52_diff_over_0p1pct": sum(1 for r in rows if (r["weekly"]["ma52_pct"] or 0) > 0.1),
        "weekly_verdict_flip": sum(1 for r in rows if verdict_flip(r)),
        "fib_flag_diff": sum(1 for r in rows if bool(r["fib"]["ce_flag"]) != r["fib"]["chart_in_zone"]),
        "choch_diff": sum(1 for r in rows if bool(r["choch"]["ce_flag"]) != r["choch"]["chart_bullish"]
                          and (bool(r["choch"]["ce_flag"]) or r["choch"]["chart_bearish"]
                               or r["choch"]["chart_bullish"] is not None)),
        "rsi_gap_median": None,
    }
    gaps = [abs((r["weekly"]["rsi_ce7"] or 0) - (r["weekly"]["rsi_chart5"] or 0))
            for r in rows if r["weekly"]["rsi_ce7"] is not None and r["weekly"]["rsi_chart5"] is not None]
    if gaps:
        gaps.sort()
        agg["rsi_gap_median"] = round(gaps[len(gaps) // 2], 1)
        agg["rsi_gap_max"] = round(gaps[-1], 1)

    hdr = ("نماد | کندل | هفته CE/chart | MA52 CE | MA52 chart | diff% | RSI 7/5 "
           "| weakCE | trendW | decision | fib CE/chart | CHoCH CE/chart")
    print(f"دیتاست: {agg['symbols']} نماد، یک سریِ صعودیِ یکسان به هر دو موتور (بی‌شبکه)\n")
    print(hdr)
    print("-" * max(len(hdr), 110))
    for r in rows:
        w, f, c = r["weekly"], r["fib"], r["choch"]
        print(f"{r['symbol']:>9} | {r['bars']:>4} | {w['bars_ce']}/{w['bars_chart']} | "
              f"{w['ma52_ce']} | {w['ma52_chart']} | {w['ma52_pct']} | "
              f"{w['rsi_ce7']}/{w['rsi_chart5']} | {w['ce_weak']} | {w['chart_trendW']} | "
              f"{w['chart_decision']} | {f['ce_flag']}/{f['chart_in_zone']} | "
              f"{c['ce_flag']}/{c['chart_bullish'] or c['chart_bearish']}")

    print("\nجدولِ واگرایی (تعدادِ نماد در " + str(agg["symbols"]) + "):")
    for k, v in agg.items():
        if k != "symbols":
            print(f"  {k}: {v}")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"dataset": "price_history · یک سریِ صعودیِ یکسان به هر دو موتور",
                   "aggregates": agg, "rows": rows}, fh, ensure_ascii=False, indent=1)
    print("\nجزئیات:", OUT)


if __name__ == "__main__":
    main()
