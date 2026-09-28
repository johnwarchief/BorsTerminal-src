# tools/tape_parity_fuzz.py — ریزشِ تفاضلیِ پنج فیلتر: پایتونِ مرجع در برابرِ فرانت
#
# پرسشِ مالک: «وقتی بازار باز شود و اعداد هی عوض شوند، نتیجهٔ فیلترهای ما با
# TSE یکی است؟» برابری رویِ یک اسنپ‌شاتِ زنده ثابت شده (۱۴۰۵-۰۷-۰۷)؛ ولی «اعداد
# عوض می‌شوند» یعنی هزاران حالتِ میانی که هیچ‌کدام درِ تابلو دیده نمی‌شوند.
# اینجا همان ردیف‌هایِ واقعیِ /api/market را با ضریب‌هایِ تعیین‌شده (seeded)
# به‌هم می‌ریزیم — قیمت، حجم، تعدادِ معاملات، پنجرهٔ تاریخچه، زنده/متوقف — و
# پنج پرچم را دو بار می‌خوانیم: یک‌بار با tape_flags.py (مرجعِ سایت) و یک‌بار با
# tapeFilterVerdict() درِ فرانت. هر اختلافی این‌جا می‌افتد، نه درِ بازارِ باز.
#
#   python -X utf8 tools/tape_parity_fuzz.py --rows 140 --out _audit/tape_parity_fuzz.json
import argparse
import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402
from tape_flags import apply_tape_flags  # noqa: E402

FLAGS = ("f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh")

# ضریب‌ها عمداً دورِ آستانه‌ها می‌چرخند: ۲٪ ساعت، ۳× مشکوک، نردبانِ جت (۲/۵/۹/…)
PRICE_X = (0.97, 1.0, 1.021, 1.03, 1.06)
VOL_X = (0.2, 1.0, 2.9, 3.2, 6.0, 12.0)
TRAN_X = (0.002, 0.01, 1.0, 12.0, 90.0)
HIST = (0, 12, 28, 29, 30, 60)


def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def mutate(row, rng):
    """یک نسخۀِ به‌هم‌ریخته از ردیفِ واقعی، با همان ستون‌هایِ لازم."""
    m = dict(row)
    base = _num(row.get("p_last")) or _num(row.get("p_closing")) or 1000.0
    m["p_last"] = round(base * rng.choice(PRICE_X), 4)
    m["p_closing"] = round((_num(row.get("p_closing")) or base) * rng.choice((1.0, 1.005, 1.02)), 4)
    m["price_yesterday"] = round((_num(row.get("price_yesterday")) or base) * rng.choice((0.98, 1.0, 1.03)), 4)
    m["tvol"] = (_num(row.get("tvol")) or 1e6) * rng.choice(VOL_X)
    m["q_tot_tran"] = (_num(row.get("q_tot_tran")) or 100) * rng.choice(TRAN_X)
    m["z_tot_tran"] = (_num(row.get("z_tot_tran")) or 100) * rng.choice(TRAN_X)
    m["prior30_vol"] = (_num(row.get("prior30_vol")) or 3e8) * rng.choice((0.25, 1.0, 3.0))
    m["hist_sessions"] = rng.choice(HIST)
    m["min_low_29"] = (_num(row.get("min_low_29")) or base * 0.9) * rng.choice((0.9, 1.0, 1.15))
    m["min30_low"] = (_num(row.get("min30_low")) or base * 0.9) * rng.choice((0.9, 1.0, 1.15))
    for k in ("h2_max", "h5_max", "h9_max", "h19_max", "h29_max", "h39_max", "h49_max", "h59_max", "max30_high"):
        if k in row:
            m[k] = (_num(row[k]) or base) * rng.choice((0.85, 1.0, 1.02, 1.2))
    m["buy_q1_vol"] = (_num(row.get("buy_q1_vol")) or 0.0) * rng.choice((0.0, 1.0, 4.0))
    m["buy_q1_cnt"] = (_num(row.get("buy_q1_cnt")) or 0.0) * rng.choice((0.0, 1.0, 6.0))
    m["tmin"] = (_num(row.get("tmin")) or base * 0.95) * rng.choice((0.9, 1.0, 1.01))
    m["tmax"] = (_num(row.get("tmax")) or base) * rng.choice((0.95, 1.0, 1.1))
    m["is_live"] = rng.random() > 0.15
    return m


def scenarios(base):
    """قالب‌هایِ هدفمند، چون ضریب‌هایِ تصادفیِ خام هرگز آستانه‌هایِ «جت» و
    «کف‌روبی» را با هم نمی‌آورند (جت هفت قیدِ هم‌زمان می‌خواهد، کف‌روبی چهار
    قیدِ صفی). برایِ هر پرچم یک «باید قبول شود» و دو «یک قیدش کم است» می‌سازیم؛
    همان near-miss ها جایی‌اند که دو پیاده‌سازی از هم جدا می‌شوند."""
    b = dict(base)
    pc, pl, py = 1000.0, 1030.0, 1000.0

    def shape(**kw):
        r = dict(b)
        r.update(
            p_closing=pc, p_last=pl, price_yesterday=py, percent_last=round((pl / py - 1) * 100, 2),
            tvol=3.5e6, prior30_vol=1e6 * 30, z_tot_tran=400.0, q_tot_tran=400.0,
            hist_sessions=60.0, min_low_29=990.0, min30_low=980.0,
            h2_max=900.0, h5_max=900.0, h9_max=900.0, h19_max=900.0, h29_max=900.0,
            h39_max=900.0, h49_max=900.0, h59_max=900.0, max30_high=900.0,
            buy_q1_cnt=0.0, buy_q1_vol=0.0, tmin=900.0, tmax=1040.0,
            buy_q_cnt=10.0, sell_q_cnt=2.0, buy_q_vol=2e6, sell_q_vol=1e6,
            is_live=True,
        )
        r.update(kw)
        return r

    jet = shape()
    jet_near_vol = shape(tvol=2.0e6)                 # نسبتِ حجم زیرِ سه
    jet_near_res = shape(h59_max=1100.0)             # آخرین زیرِ پلکان
    jet_near_trades = shape(z_tot_tran=50.0)         # tno <= 100
    roobi = shape(p_last=900.0, tmin=900.0, buy_q1_cnt=3.0, buy_q1_vol=500.0)
    roobi_near_queue = shape(p_last=900.0, tmin=900.0, buy_q1_cnt=1.0, buy_q1_vol=500.0)
    roobi_near_price = shape(p_last=901.0, tmin=900.0, buy_q1_cnt=3.0, buy_q1_vol=500.0)
    roobi_near_depth = shape(p_last=900.0, tmin=900.0, buy_q1_cnt=3.0, buy_q1_vol=50.0)
    clock = shape(p_last=1030.0)
    clock_near_delta = shape(p_last=1015.0)
    susp = shape(p_last=1030.0, z_tot_tran=400.0)
    susp_near_trades = shape(p_last=1030.0, z_tot_tran=40.0)
    noqteh = shape(p_last=1000.0, min_low_29=995.0)
    noqteh_far = shape(p_last=1000.0, min_low_29=900.0)
    noqteh_short_window = shape(p_last=1000.0, min_low_29=995.0, hist_sessions=20.0)
    dead = shape(p_last=1030.0, is_live=False)
    rows = [
        jet, jet_near_vol, jet_near_res, jet_near_trades,
        roobi, roobi_near_queue, roobi_near_price, roobi_near_depth,
        clock, clock_near_delta, susp, susp_near_trades,
        noqteh, noqteh_far, noqteh_short_window, dead,
    ]
    # درصدِ آخرین باید از خودِ آخرینِ همان قالب بیاید، وگرنه «کف‌روبی» که
    # زیرِ یکِ درصدِ منفی می‌خواهد هیچ‌وقت شرطش را نمی‌بیند.
    for r in rows:
        py = float(r.get("price_yesterday") or 0) or 1.0
        r["percent_last"] = round((float(r["p_last"]) / py - 1) * 100, 2)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "_audit", "mk_fund_overlap.json"))
    ap.add_argument("--rows", type=int, default=140)
    ap.add_argument("--per", type=int, default=8)
    ap.add_argument("--seed", type=int, default=14050707)
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit", "tape_parity_fuzz.json"))
    a = ap.parse_args()

    raw = json.load(open(a.src, encoding="utf-8"))
    rows = raw["data"] if isinstance(raw, dict) else raw
    rng = random.Random(a.seed)
    picked = [r for r in rows if r.get("p_closing") or r.get("p_last")]
    rng.shuffle(picked)
    picked = picked[: a.rows]

    cases = []
    for r in picked:
        for _ in range(a.per):
            cases.append(mutate(r, rng))
    # قالب‌هایِ هدفمند: چند بار با نویزِ کم تکرار می‌شوند تا ستون‌هایِ اختیاریِ
    # ردیفِ واقعی هم درِ آزمون دیده شوند.
    for r in picked[:12]:
        for s in scenarios(r):
            cases.append(s)

    df = pd.DataFrame(cases)
    flagged = apply_tape_flags(df)
    # ستون‌هایِ آماده‌ای که فرانت می‌خواند باید از همان مرجعِ پایتون بازسازی
    # شوند: فرانت نسبتِ حجم را دوباره حساب نمی‌کند، `vol_ratio_file`ِ گردِ
    # بک‌اند را می‌خواند. بی‌این، ردیف‌هایِ به‌هم‌ریخته درِ فرانت بی‌داده
    # می‌شدند و اختلافِ جعلی (فرانت=false) بالا می‌آمد.
    for col in ("vol_ratio", "vol_ratio_file", "buyer_power_raw", "resistance_59", "dist_min30_pct"):
        df[col] = flagged[col]
    df["buyer_power"] = df["buyer_power_raw"].round(2).clip(upper=10.0)

    keep = (
        "symbol", "p_last", "p_closing", "price_yesterday", "percent_last", "tvol",
        "z_tot_tran", "q_tot_tran", "prior30_vol", "hist_sessions", "min_low_29",
        "min30_low", "tmin", "tmax", "buy_q1_cnt", "buy_q1_vol",
        "vol_ratio", "vol_ratio_file", "buyer_power", "buyer_power_raw",
        "resistance_59", "dist_min30_pct", "month_avg_vol", "vol_dod", "is_live",
        "h2_max", "h5_max", "h9_max", "h19_max", "h29_max", "h39_max", "h49_max", "h59_max",
        "max30_high", "buy_count_i", "sell_count_i", "buy_i_vol", "sell_i_vol",
    )
    out_rows, expect = [], {f: [] for f in FLAGS}
    # از df خوانده می‌شود نه cases: ستون‌هایِ ساخته‌شده فقط رویِ DataFrame
    # می‌نشینند و تکرارِ cases، vol_ratio_fileِ ردیفِ اصلیِ نشستِ پیشین را با
    # خودِ حالتِ به‌هم‌ریخته قاطی می‌کرد (پنجرۀِ زیرِ ۳۰ نشست ⇒ باید null).
    for i, c in enumerate(df.to_dict("records")):
        clean = {}
        for k in keep:
            v = c.get(k)
            if k == "is_live":
                clean[k] = bool(v)
            elif isinstance(v, str) or v is None:
                clean[k] = v
            else:
                n = _num(v)
                clean[k] = None if n is None else round(n, 4)
        out_rows.append(clean)
        for f in FLAGS:
            expect[f].append(bool(flagged[f].iloc[i]))

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"seed": a.seed, "count": len(out_rows), "rows": out_rows, "expected": expect}, fh,
                  allow_nan=False, separators=(",", ":"))

    pos = {f: sum(expect[f]) for f in FLAGS}
    print(f"cases={len(out_rows)} seed={a.seed} positives={pos}")
    print("all-zero guard:", "FAIL" if sum(pos.values()) == 0 else "ok")


if __name__ == "__main__":
    main()
