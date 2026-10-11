# -*- coding: utf-8 -*-
"""tools/ra_fts_parity.py — پاریتیِ لایه‌های FTS با مرجعِ رهاورد (مرحلۀ ۹)

چرا این فایل جدا از `tools/ra_parity.py` است: آن هارنس «کندل⇄کندل» را می‌سنجد، ولی
مأموریتِ لایه‌های FTS سؤالِ دیگری دارد — آیا *تشخیصِ ساختار و روند* رویِ دادهٔ ما
با همان چیزی می‌خواند که رویِ نمودارِ رهاورد دیده می‌شود؟ رهاورد هیچ مقدارِ
اندیکاتوری منتشر نمی‌کند (پاسخِ `…/prices?timeframe=` فقط کندل است؛ درِ اجرای
۲۰۲۶-۱۰-۱۱ مشاهده شد)، پس پاریتیِ لایه سه‌پایه است:

  ۱) داده: سریِ نمایشیِ ما (کندل × ضریبِ تعدیلِ خودِ برنامه) ⇄ سریِ مرجع، رویِ
     تقاطعِ تاریخ‌ها — خطایِ نسبیِ میانه/p95 بسته بهاندازهٔ خودِ داده، نه آستانهٔ ابداعی.
  ۲) حساسیتِ منطق: **همان الگوریتمِ ما** رویِ هر دو سری اجرا می‌شود
     (`_fts_swings` → `_fts_classify_trend` → `_fts_structure_points`). اگر رأیِ
     روند عوض شود، علت مستند «واگراییِ داده» است (نه منطق) و فاصلۀ واقعیِ پیوت‌ها
     چاپ می‌شود؛ اگر رأی‌ها یکی بودند و با برچسبِ انسانی نمی‌خواندند، شکافِ منطق است.
  ۳) برچسبِ انسانی: rowsِ `docs/validation/rahavard-trend-parity/REFERENCE.csv`
     (برچسب‌هایی که فقط از نمودارِ خوانده‌شدۀ رهاورد گرفته شده‌اند، نه از خروجیِ
     هیچ الگوریتمی) درِ نمادهایِ پوشش‌داده‌شده مقابله می‌خورند.

انتخابِ نماد برایِ حذفِ «گلچینِ به‌نفعِ الگوریتم» مکانیکی است: بیست‌وچهارِ نخستِ
بازارِ ایران بر پایهٔ آخرین market_cap با دست‌کم ۳۰۰ کندلِ روزانه درِ بانک، به‌علاوهٔ
نمادهایِ برچسب‌انسانی‌شدۀ بیرونِ آن فهرست. هر نمادِ بی‌ins_code یا بی‌مرجع با وضعیتِ
صریح رد می‌شود و درِ گزارش می‌آید.

شبکه لازم است (مرجع از tradersarena.ir می‌آید، با کشِ `_audit/ra_probe_cache` مثلِ
`ra_parity.py`)؛ بی‌شبکه این فایل «گزارشِ ناقص + UNVERIFIED» چاپ می‌کند و درِ
`dev/run_all_tests.py` ثبت **نشده** است، چون سوئیت‌هایِ آن باید آفلاین بدوند.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sqlite3
import sys
import tempfile
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import ra_parity as RP  # noqa: E402

REF_CSV = os.path.join(ROOT, "docs", "validation", "rahavard-trend-parity", "REFERENCE.csv")

# فهرستِ پیش‌فرض = همان قاعدۀ مکانیکیِ بالایِ فایل (نتیجۀ اجرایِ ۲۰۲۶-۱۰-۱۱) + برچسب‌انسانی‌ها
DEFAULT_SYMBOLS = ("فارس,شپنا,فولاد,شبندر,شستا,وبملت,پارسان,شتران,وپاسار,ومعادن,"
                  "مارون,فزر,پارس,وتجارت,طلا,سامان,جم,شسپا,صبا,وپارس,وصندوق,شراز,"
                  "شبهرن,همراه,فنوال,ولانا,خودرو")

LABEL_MAP = {"up": "up", "down": "down", "range": "range", "na": "na",
             "contradictory": "contradictory", "n/a": "na"}


def pick_auto(limit, min_bars):
    """انتخابِ مکانیکی از بانک (بی‌دستِ انسان) — همان قاعدۀ مستندشده."""
    con = sqlite3.connect(os.path.join(ROOT, "market.db"))
    rows = con.execute(
        """SELECT i.l_val18,
                  (SELECT COUNT(*) FROM price_history p WHERE p.symbol=i.l_val18) bars,
                  (SELECT market_cap FROM market_cap_snapshots m
                    WHERE m.symbol=i.l_val18 ORDER BY m.date DESC LIMIT 1) cap
           FROM instruments i WHERE i.ins_code IS NOT NULL AND TRIM(i.ins_code)<>''""").fetchall()
    con.close()
    cand = [r for r in rows if r[1] >= min_bars and r[2]]
    cand.sort(key=lambda r: (-r[2], r[0]))
    return [r[0] for r in cand[:limit]]


def human_labels():
    out = {}
    if not os.path.isfile(REF_CSV):
        return out
    for line in open(REF_CSV, encoding="utf-8").read().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = next(csv.reader([line]))
        if parts[0] == "symbol":
            continue
        out[(parts[0], parts[4])] = LABEL_MAP.get(parts[7].strip().lower(), parts[7].strip())
    return out


def to_series(candles_by_date, window):
    out = []
    for d in sorted(candles_by_date)[-window:]:
        c = candles_by_date[d]
        if not isinstance(c.get("close"), (int, float)) or c["close"] <= 0:
            continue
        out.append({"time": d, "open": float(c.get("open") or c["close"]),
                    "high": float(c.get("high") or c["close"]),
                    "low": float(c.get("low") or c["close"]),
                    "close": float(c["close"]), "volume": c.get("volume")})
    return out


def rel_err(our, ref):
    errs = []
    for d in set(our) & set(ref):
        a, b = our[d]["close"], ref[d]["close"]
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a > 0 and b > 0:
            errs.append(abs(a - b) / ((a + b) / 2.0))
    if not errs:
        return {"n": 0, "median": None, "p95": None}
    errs.sort()
    return {"n": len(errs), "median": round(errs[len(errs) // 2], 6),
            "p95": round(errs[min(len(errs) - 1, int(0.95 * len(errs)))], 6)}


def pivot_agreement(a, b, tol_bars=3):
    """چند پیوتِ a درِ پنجرۀ ±tol_bars کندلِ b هم‌جنس پیدا می‌شود (نسبت به len(a))."""
    if not a:
        return {"a": 0, "b": len(b), "matched": 0, "rate": None}
    matched = 0
    idx_b = {p["idx"]: p for p in b}
    for p in a:
        hit = None
        for off in range(0, tol_bars + 1):
            for cand in (idx_b.get(p["idx"] + off), idx_b.get(p["idx"] - off)):
                if cand and cand["kind"] == p["kind"]:
                    hit = cand
                    break
            if hit:
                break
        if hit:
            matched += 1
    return {"a": len(a), "b": len(b), "matched": matched, "rate": round(matched / len(a), 3)}


def layers(series):
    import api.chart as CH
    piv = CH._fts_swings(series, k=CH._FTS_SWING_K)
    pts = CH._fts_structure_points(piv)
    trend = CH._fts_classify_trend(piv, series=series)
    return {"pivots": piv, "points": pts, "trend": str(trend.get("trend") or "na"),
            "basis": str(trend.get("basis") or ""),
            "last_labels": [p["label"] for p in pts][-4:],
            "last_pivot_time": (pts[-1]["time"] if pts else None)}


def audit_symbol(sym, ins, tfs, window, cache_only):
    row = {"symbol": sym, "ins_code": ins}
    try:
        our_daily, meta = RP.bors_series_display(sym, "last")
    except Exception as e:                                   # noqa: BLE001
        return {**row, "status": f"bors_error:{type(e).__name__}"}
    if not our_daily:
        return {**row, "status": f"bors_empty:{meta.get('error')}"}
    for tf, name in zip(tfs, ("D", "W")):
        try:
            ref = RP.ra_rows(ins, tf) if not cache_only else _cache_only(ins, tf)
        except (urllib.error.URLError, OSError) as e:
            row[f"{name}_status"] = f"reference_unreachable:{type(e).__name__}"
            continue
        if not ref:
            row[f"{name}_status"] = "reference_missing"
            continue
        our = our_daily if tf == 0 else RP.aggregate(our_daily, 1, "last")
        shared = sorted(set(ref) & set(our))[-window[tf]:]
        if len(shared) < 20:
            row[f"{name}_status"] = f"shared_bars_{len(shared)}"
            continue
        cut_ref = {d: ref[d] for d in shared}
        cut_our = {d: our[d] for d in shared}
        s_our, s_ref = to_series(cut_our, len(shared)), to_series(cut_ref, len(shared))
        L, Lr = layers(s_our), layers(s_ref)
        row[f"{name}_shared_bars"] = len(shared)
        row[f"{name}_rel_err"] = rel_err(cut_our, cut_ref)
        row[f"{name}_trend_bors"] = L["trend"]
        row[f"{name}_trend_on_ref"] = Lr["trend"]
        row[f"{name}_basis_bors"] = L["basis"]
        row[f"{name}_pivots"] = pivot_agreement(L["pivots"], Lr["pivots"])
        row[f"{name}_labels_bors"] = L["last_labels"]
        row[f"{name}_labels_on_ref"] = Lr["last_labels"]
        row[f"{name}_last_pivot_time"] = L["last_pivot_time"]
        flip = L["trend"] != Lr["trend"]
        hum = HUMAN.get((sym, name))
        row[f"{name}_human"] = hum
        if flip:
            row[f"{name}_verdict"] = "data_divergence_flips_label"
        elif hum and hum not in ("na", "contradictory") and hum != L["trend"]:
            row[f"{name}_verdict"] = "logic_gap_vs_human_label"
        elif hum:
            row[f"{name}_verdict"] = "match_human" if hum == L["trend"] else f"human_{hum}"
        else:
            row[f"{name}_verdict"] = "label_stable_under_ref"
    return row


def _cache_only(ins, tf):
    key = os.path.join(RP.CACHE, "httpstradersarenairdata%spricestimeframe%d.json" % (ins, tf))
    if not os.path.isfile(key):
        raise OSError("no cached reference")
    return RP.ra_rows(ins, tf)


HUMAN = {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=DEFAULT_SYMBOLS)
    ap.add_argument("--auto", type=int, default=0, help="N نمادِ نخستِ بازار (انتخابِ مکانیکی)")
    ap.add_argument("--min-bars", type=int, default=300)
    ap.add_argument("--timeframes", default="0,1")
    ap.add_argument("--window", type=int, default=0, help="کندلِ سنجش (پیش‌فرض: 420 روزانه / 120 هفتگی)")
    ap.add_argument("--cache-only", action="store_true", help="بی‌شبکه؛ فقط کشِ موجود")
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit", "ra_fts_parity.json"))
    a = ap.parse_args()

    global HUMAN
    HUMAN = human_labels()

    syms = ([s.strip() for s in a.symbols.split(",") if s.strip()] if not a.auto
            else pick_auto(a.auto, a.min_bars))
    tfs = [int(x) for x in a.timeframes.split(",") if x.strip()]
    window = {0: a.window or 420, 1: a.window or 120}

    src = os.path.join(ROOT, "market.db")
    import bors_config
    import price_basis
    DB_COPY = os.path.join(tempfile.mkdtemp(prefix="ftsp_"), "copy.db")
    x = sqlite3.connect(src, timeout=60)
    y = sqlite3.connect(DB_COPY)
    with y:
        x.backup(y)
    x.close()
    y.close()
    con = sqlite3.connect(DB_COPY)
    ins_map = {n: i for n, i in con.execute("SELECT l_val18, ins_code FROM instruments")}
    con.close()
    bors_config.DB_PATH = DB_COPY
    bors_config.PRICE_BASIS_PATH = os.path.join(os.path.dirname(DB_COPY), "price_basis.json")
    price_basis.set_basis("last")
    for m in ("api._core", "api.chart", "api.market", "api.screener", "api.fundamental"):
        mod = sys.modules.get(m)
        if mod is not None:
            mod.DB_PATH = DB_COPY
    print(f"[copy] market.db دست‌نخورده · سنجش رویِ {DB_COPY} · مرجع: "
          f"{'کشِ محلی' if a.cache_only else 'tradersarena.ir'} · {len(syms)} نماد")

    rows = []
    for sym in syms:
        ins = str(ins_map.get(sym) or "")
        if not ins:
            rows.append({"symbol": sym, "status": "no_ins_code"})
            print(f"  {sym}: بی‌ins_code — رد")
            continue
        r = audit_symbol(sym, ins, tfs, window, a.cache_only)
        rows.append(r)
        d = r.get("D_verdict") or r.get("D_status") or r.get("status") or "-"
        w = r.get("W_verdict") or r.get("W_status") or "-"
        e = (r.get("D_rel_err") or {}).get("median")
        pa = (r.get("D_pivots") or {}).get("rate")
        print(f"  {sym:<10} D={d:<28} W={w:<24} rel_err={e} pivot±3={pa}")

    tally = {}
    for r in rows:
        for k, v in r.items():
            if k.endswith("_verdict") or k.endswith("_status"):
                tally[v] = tally.get(v, 0) + 1
    body = {"generated": dt.datetime.now().isoformat(timespec="seconds"),
            "mode": "cache-only" if a.cache_only else "live-reference",
            "symbols": len(syms), "timeframes": tfs, "window": window,
            "selection_rule": "top-N by latest market_cap with >= %d daily bars, "
                              "plus previously human-labelled symbols" % a.min_bars,
            "human_label_rows": len(HUMAN),
            "note": "مرجع رهاورد هیچ مقدار اندیکاتوری منتشر نمی‌کند؛ لایه‌ها با اجرای "
                    "همان الگوریتم روی سری مرجع سنجیده می‌شوند و برچسب انسانی فقط از "
                    "REFERENCE.csv می‌آید",
            "verdict_tally": tally, "rows": rows}
    json.dump(body, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n── خلاصه ──")
    for k, v in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"  {v:>3}  {k}")
    print(f"گزارش: {a.out}")
    if not any(str(r.get("D_verdict", "")).startswith(("match", "label_stable")) for r in rows):
        print("UNVERIFIED: هیچ سطرِ موفقِ مقابله‌ای ثبت نشد (شبکه/مرجع در دسترس نبود؟)")


if __name__ == "__main__":
    sys.exit(main())
