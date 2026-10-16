"""corpusِ Ground-Truth روندِ روزانه/هفتگی (P0-3) — فقط‌خواندنی از market.db.

برایِ هر نمادِ واقعی در چند `as_of` (برشِ تاریخیِ واقعی) ثبت می‌کند:
  کندل‌هایِ ورودی، ساختارِ پیوت (HH/HL/LH/LL/Range)، رأیِ موتورِ canonical (Daily
  و Weekly از یک موتور)، evidence (پیوت‌ها + زمان‌ها)، source و as_of، و classِ
  اختلاف.

هیچ آستانه/منطقِ FTS عوض نمی‌شود — اینجا فقط مصرف‌کنندهٔ خوانش است. «رأیِ انسانی»
مطابقِ جزوه کارِ مالک است؛ ستونِ human_verdict روی PENDING می‌ماند مگر در مواردِ
روشنِ ساختاری که خودکار برچسب می‌خورند (با شاهد). مواردِ mismatch و مبهم فهرست
می‌شوند تا داوری شوند.

اجرا:  python tools/fts_trend_corpus.py [--symbols N] [--out _audit/FTS_TREND_CORPUS.csv]
"""
import argparse
import csv
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from api import chart as CH  # noqa: E402

DB = os.path.join(ROOT, "market.db")


def load_candles(cur, symbol):
    cur.execute("SELECT date,open,high,low,close,volume,src FROM price_history "
                "WHERE symbol=? ORDER BY date", (symbol,))
    out = []
    for d, o, h, l, c, v, src in cur.fetchall():
        try:
            out.append({"time": str(d)[:10], "open": float(o), "high": float(h),
                        "low": float(l), "close": float(c), "volume": float(v or 0)})
        except (TypeError, ValueError):
            continue
    return out, (src or "?")


def upto(candles, as_of):
    return [c for c in candles if c["time"] <= as_of]


def structure_label(trend_dict):
    """خوانشِ مستقلِ ساختاری از خودِ پیوت‌ها (HH/HL/LH/LL/Range) — نه بازخوانیِ trend."""
    hh, hl = trend_dict.get("hh"), trend_dict.get("hl")
    if hh and hl:
        return "HH+HL"
    if (hh is False) and (hl is False):
        return "LH+LL"
    if hh is None or hl is None:
        return "کم‌داده"
    return "mixed"


def row_for(symbol, src, candles, as_of):
    sliced = upto(candles, as_of)
    if len(sliced) < 60:
        return None
    sd = CH._fts_swings(sliced, k=CH._FTS_SWING_K)
    d = CH._fts_classify_trend(sd, series=sliced)
    w = CH._fts_resample(sliced, "W")
    ww = CH._fts_classify_trend(CH._fts_swings(w, k=2), series=w) if len(w) >= 4 else {}
    dt, wt = d.get("trend"), ww.get("trend")
    agree = "yes" if (dt == wt and dt not in (None, "na")) else ("na" if "na" in (dt, wt) else "no")
    # سازگاریِ درونی: آیا `trend` با همان hh/hl که خودِ موتور گزارش کرده می‌خواند؟
    # (flagِ داوری است، نه اصلاح — منطقِ موتور دست‌نخورده.)
    hh, hl = d.get("hh"), d.get("hl")
    implied = ("up" if (hh and hl) else "down" if (hh is False and hl is False) else "range/mixed")
    if dt in ("up", "down") and implied in ("up", "down"):
        consistency = "match" if dt == implied else ("INCONSISTENT(%s vs %s)" % (dt, implied))
    else:
        consistency = "n/a"
    # زیردستهٔ مبهم: چرا روشن نیست؟ کدام ذاتاً UNVERIFIED است و کدام با شاهد حل می‌شود.
    if structure_label(d) == "کم‌داده" or d.get("basis") == "insufficient":
        ambig = "insufficient-data (کم‌داده)"
    elif d.get("basis") == "recent-window":
        ambig = "recent-window (موتور پیوت قطعی نیافت)"
    elif dt == "na" or wt == "na":
        ambig = "na-trend"
    elif structure_label(d) == "mixed":
        ambig = "structure-mixed (یک بُعد سازگار)"
    else:
        ambig = ""
    engine_vs_struct = None
    if dt in ("up", "down") and structure_label(d) in ("HH+HL", "LH+LL"):
        engine_vs_struct = "match" if ((dt == "up") == (structure_label(d) == "HH+HL")) else "MISMATCH"
    klass = (ambig or engine_vs_struct or "NEEDS-OWNER") if ambig else (engine_vs_struct or "NEEDS-OWNER")
    return {
        "symbol": symbol, "source": src, "as_of": as_of,
        "bars_d": len(sliced), "bars_w": len(w),
        "daily_trend": dt, "daily_basis": d.get("basis"),
        "daily_hh": hh, "daily_hl": hl, "daily_struct": structure_label(d),
        "daily_last_high": d.get("last_high"), "daily_last_high_time": d.get("last_high_time"),
        "daily_last_low": d.get("last_low"), "daily_last_low_time": d.get("last_low_time"),
        "weekly_trend": wt, "weekly_hh": ww.get("hh"), "weekly_hl": ww.get("hl"),
        "weekly_last_high": ww.get("last_high"), "weekly_last_low": ww.get("last_low"),
        "daily_weekly_agree": agree, "trend_vs_own_structure": consistency,
        "ambiguous_reason": ambig, "classification": klass, "human_verdict": "",
    }


COLS = ["symbol", "source", "as_of", "bars_d", "bars_w", "daily_trend", "daily_basis",
        "daily_hh", "daily_hl", "daily_struct", "daily_last_high", "daily_last_high_time",
        "daily_last_low", "daily_last_low_time", "weekly_trend", "weekly_hh", "weekly_hl",
        "weekly_last_high", "weekly_last_low", "daily_weekly_agree", "trend_vs_own_structure",
        "ambiguous_reason", "classification", "human_verdict"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=40)
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit", "FTS_TREND_CORPUS.csv"))
    a = ap.parse_args()
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT symbol, COUNT(*) n FROM price_history GROUP BY symbol "
                "HAVING n>=300 ORDER BY symbol")
    syms = [r[0] for r in cur.fetchall()][: a.symbols]
    rows = []
    for sym in syms:
        candles, src = load_candles(cur, sym)
        if len(candles) < 60:
            continue
        last = candles[-1]["time"]
        pts = [last, candles[max(0, len(candles) - 60)]["time"],
               candles[max(0, len(candles) - 150)]["time"]]
        for as_of in sorted(set(pts)):
            r = row_for(sym, src, candles, as_of)
            if r:
                rows.append(r)
    conn.close()

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=COLS)
        wr.writeheader()
        wr.writerows(rows)

    from collections import Counter
    cls = Counter(r["classification"] for r in rows)
    ambig = Counter(r["ambiguous_reason"] for r in rows if r["ambiguous_reason"])
    incons = [r for r in rows if r["trend_vs_own_structure"].startswith("INCONSISTENT")]
    print(f"corpus: {len(rows)} rows over {len(set(r['symbol'] for r in rows))} symbols → {a.out}")
    print("classification:", dict(cls))
    print("ambiguous breakdown:", dict(ambig))
    print(f"INCONSISTENT (trend ≠ hh/hlِ خودِ موتور — پروندۀِ داوری): {len(incons)}")
    for r in incons[:25]:
        print(f"  {r['symbol']} as_of={r['as_of']} {r['trend_vs_own_structure']}"
              f" daily_basis={r['daily_basis']} weekly={r['weekly_trend']}"
              f" (lastH={r['daily_last_high']} prevH→lastLow={r['daily_last_low']})")
    mism = [r for r in rows if r["classification"] == "MISMATCH"]
    print(f"\nMISMATCH (موتور ≠ خوانشِ ساختاریِ دوبعدی): {len(mism)}")
    for r in mism[:25]:
        print(f"  {r['symbol']} as_of={r['as_of']} daily={r['daily_trend']}"
              f" struct={r['daily_struct']} weekly={r['weekly_trend']}")


if __name__ == "__main__":
    main()
