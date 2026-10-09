"""trend_compare — اسکلتِ مقایسۀِ دو موتور + ستون‌هایِ پرشدنیِ مرورگری (P0-3).

برایِ هر (symbol, D/W) در یک as_ofِ کاملِ مشترک:
  • برچسبِ موتورِ قدیم (_fts_classify_trend) — همان که الان درِ production است
  • برچسبِ موتورِ ترکیبی (tools/trend_lab.classify_one)
  • confidenceِ ترکیبی + ساختارِ پیوت (شاهدِ بازبینی‌پذیر)
  • عمقِ تاریخچه (برایِ مرزِ کفایتِ داده)
  • دستۀِ انتخاب: clear-up / clear-down / clear-neutral / structure-mixed /
    engine-disagreement / short-history
  • ستون‌هایِ خالیِ مرورگری: ref_daily / ref_weekly / ref_basis / ref_notes /
    screenshot / verdict / cause — این‌ها با مراجعِ واقعی پر می‌شوند.

هیچ اختلافی خودکار به نفعِ هیچ موتوری حل نمی‌شود.
اجرا:  python tools/trend_compare.py [--as-of 2026-10-06] [--n 40]
"""
import argparse
import csv
import importlib.util
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

# بارگذاریِ trend_lab به‌عنوانِ ماژول (نه پکیج)
_spec = importlib.util.spec_from_file_location("trend_lab", os.path.join(ROOT, "tools", "trend_lab.py"))
tl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tl)

DB = os.path.join(ROOT, "market.db")
OUT = os.path.join(ROOT, "_audit", "FTS_TREND_COMPARE.csv")


def old_label(candles, tf):
    if not candles or len(candles) < (6 if tf == "D" else 4):
        return "na", {}
    series = candles if tf == "D" else (CH._fts_resample(candles, "W") if len(candles) >= 4 else [])
    if len(series) < 6:
        return "na", {}
    sw = CH._fts_swings(series, k=CH._FTS_SWING_K if tf == "D" else 2)
    d = CH._fts_classify_trend(sw, series=series)
    return (d.get("trend") if d else "na"), (d or {})


def bucket(oldD, oldW, newD, newW, bars):
    if bars < 30 or (newD in (None,) and newW in (None,)):
        return "short-history"
    if oldD != newD or oldW != newW:
        return "engine-disagreement"
    if newD == "range" or newD == "neutral":
        return "clear-neutral"
    # ساختارِ مختلط: موتورِ قدیم رویِ booleansِ خنثی ولی trendِ جهت‌دار
    return "structure-mixed" if (oldD in ("up", "down") and oldW in ("up", "down") and oldD != oldW) \
        else f"clear-{'up' if newD == 'up' else 'down'}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2026-10-06")
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT symbol, COUNT(*) n FROM price_history GROUP BY symbol ORDER BY symbol")
    all_syms = cur.fetchall()
    # سهم‌هایِ عمیقِ واقعی (چارتمقابل‌سنجی‌پذیر)؛ صندوق/اوراقِ کم‌عمق جدا برایِ مرزِ داده.
    deep = [s for s, n in all_syms if n >= 150]
    step = max(1, len(deep) // (a.n * 2))
    candidates = deep[::step][: a.n * 2]
    # چند کم‌عمقِ مرزی (برایِ تعیینِ کفِ کفایتِ داده) هم اضافه شوند
    shallow = [s for s, n in all_syms if 20 <= n < 60][: 6]
    candidates += shallow

    rows = []
    for sym in candidates:
        daily = tl.load_candles(cur, sym, a.as_of)
        if not daily:
            continue
        weekly = CH._fts_resample(daily, "W") if len(daily) >= 4 else []
        oD, od = old_label(daily, "D")
        oW, _ = old_label(daily, "W")
        nD = tl.classify_one(daily, "D", a.as_of, sym)
        nW = tl.classify_one(weekly, "W", a.as_of, sym)
        newD = nD["trend"] if nD["outcome"] == "classified" else ("insufficient_data")
        newW = nW["trend"] if nW["outcome"] == "classified" else ("insufficient_data")
        # mappingِ hybrid→واژگانِ legacy برایِ سنجشِ سیب-با-سیب: neutral→range
        nd = "range" if newD == "neutral" else newD
        nw = "range" if newW == "neutral" else newW
        rows.append({
            "symbol": sym, "as_of": a.as_of, "basis": "raw-db-close(تعدیل=ذخیره‌شده)",
            "bars_d": len(daily), "bars_w": len(weekly),
            "old_daily": oD, "old_weekly": oW,
            "new_daily": nd, "new_weekly": nw,
            "new_daily_raw": newD, "new_weekly_raw": newW,
            "conf_daily": nD.get("confidence"), "conf_weekly": nW.get("confidence"),
            "structure_d": nD.get("evidence", {}).get("structure", {}).get("structure"),
            "structure_w": nW.get("evidence", {}).get("structure", {}).get("structure"),
            "score_d": nD.get("score"), "reason_d": " ; ".join(nD.get("reason_codes", []) or [])[:200],
            "category": bucket(oD, oW, nd, nw, len(daily)),
            "ref_daily": "", "ref_weekly": "", "ref_basis": "", "ref_notes": "",
            "screenshot": "", "verdict": "UNVERIFIED", "cause": "",
        })
    conn.close()

    # انتخابِ پخش‌شده: از هر دسته چندتا
    from collections import defaultdict
    bycat = defaultdict(list)
    for r in rows:
        bycat[r["category"]].append(r)
    picked = []
    quota = max(1, a.n // max(1, len(bycat)))
    for cat, lst in bycat.items():
        picked.extend(lst[: quota])
    picked = picked[: a.n]

    cols = list(picked[0].keys()) if picked else []
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(picked)
    print(f"اسکلتِ مقایسه → {OUT} ({len(picked)} نماد؛ هرکدام D+W)")
    from collections import Counter
    print("دسته‌ها:", dict(Counter(r["category"] for r in picked)))
    dis = [r for r in picked if r["old_daily"] != r["new_daily"] or r["old_weekly"] != r["new_weekly"]]
    print(f"اختلافِ دو موتور در این {len(picked)}: {len(dis)} نماد")
    for r in picked:
        flag = "DIFF" if (r["old_daily"] != r["new_daily"] or r["old_weekly"] != r["new_weekly"]) else "same"
        print(f"  {r['symbol']:<10} D:{r['old_daily']}→{r['new_daily']} "
              f"W:{r['old_weekly']}→{r['new_weekly']}  conf(D/W)={r['conf_daily']}/{r['conf_weekly']} "
              f"bars={r['bars_d']} [{r['category']}] {flag}")


if __name__ == "__main__":
    main()
