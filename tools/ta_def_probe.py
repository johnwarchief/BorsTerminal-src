#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ta_def_probe.py — تعیینِ **تعریفِ** شاخص‌هایِ «وضعیت بازار» باِ شاهدِ چنددقیقه‌ای.

چرا این ابزار: مالک گفت برایِ پهنای بازار، جامعۀِ نمادها، فیلدِ قیمتِ مرجع،
شرایطِ حذفِ نماد و timestamp را با نمونۀِ واقعیِ TradersArena مشخص کن و «از
نزدیک‌ترین عددِ فعلی، بی‌اثباتِ تعریف، استفاده نکن». یکِ دقیقه هیچ‌وقت شاهد نیست؛
تعریفِ درست آن است که رویِ ده‌ها دقیقۀِ هم‌زمانِ خودِ مرجع بخورد.

چه می‌شمارد: درِ هر دقیقۀِ بازار، برایِ هر **جامعه** (تکرارِ `in_category` و
`classify`ِ خودِ `mstat_engine` — نه بازنویسیِ قاعده) و برایِ هر **قیمتِ مرجع**
(پایانی/آخرین/فیلدِ priceChange) و هر **قواعدِ صف** (یک‌طرفه بر پایهٔ ارزش،
یک‌طرفه بر پایهٔ حجم، قفل در کف/سقفِ مجاز، قفل∩یک‌طرفه) شمارش می‌نویسد. بعدِ نشست،
`_test_runs/ta_def_fit.py` همین ست‌ها را باِ سریِ ۶۰ثانیه‌ایِ خودِ مرجع
(`plus/minus/bq/sq`) ست می‌کند و rank می‌کند.

چه کاری **نمی‌کند**: هیچ درخواستِ شبکه به TSETMC/کدال/مرجع؛ فقط `SELECT` رویِ همان
بانکِ همگام‌شده باِ `mode=ro`؛ هیچ نوشتنِ رویِ بانک؛ هیچ سفارش/تغییرِ وضعیتِ اپ.
"""
import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import time

DB_DEFAULT = r"C:/Users/PCMOD/Desktop/v1080_verify/app/market.db"
OUT_DEFAULT = r"C:\Users\PCMOD\Desktop\_bors-ta-parity\_test_runs\ta_probe"

# جامعه‌ها: نگه‌داشتنِ همان تابعِ تولیدی، نه کپیِ قاعده
UNIVERSES = ("rows", "cat_all", "eq_all", "stock_right", "stock_only",
             "cat_all_traded", "eq_all_traded", "stock_right_traded")
REFS = ("closing", "last", "chg")
QRULES = ("q1val", "q1vol", "qlock", "qlock_one")


def f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _sign(d):
    if d is None:
        return None
    if d > 1e-12:
        return 0
    if d < -1e-12:
        return 1
    return 2


def counts(rows, mod):
    """شمارشِ همهٔ (جامعه × قاعده) رویِ یک لحظۀِ تابلو."""
    in_cat = {
        "cat_all": lambda r: mod.in_category(r, "all", None),
        "eq_all": lambda r: mod.in_category(r, "eq_all", None),
        "stock_right": lambda r: mod.in_category(r, "stock_right", None),
        "stock_only": lambda r: r["cls"] == mod.PAPER_STOCK,
    }
    sets = {"rows": list(rows)}
    for name, pred in in_cat.items():
        sets[name] = [r for r in rows if pred(r)]
        sets[name + "_traded"] = [r for r in sets[name] if f(r["_m"]["vol"]) > 0]

    out = {}
    for uname, sub in sets.items():
        rec = {"n": len(sub), "traded": sum(1 for r in sub if f(r["_m"]["vol"]) > 0)}
        for ref in REFS:
            pos = neg = zero = skip = 0
            for r in sub:
                if ref == "closing":
                    d = None
                    p = r.get("pct")
                    if p is not None:
                        d = p
                elif ref == "last":
                    py, pl = f(r.get("p_yesterday")), f(r.get("p_last"))
                    d = (pl - py) if (mod.px_near(pl, py) and pl > 0) else None
                else:
                    py, chg = f(r.get("p_yesterday")), r.get("price_change")
                    d = f(chg) if (chg is not None and py > 0) else None
                s = _sign(d)
                if s is None:
                    skip += 1
                else:
                    pos, neg, zero = (pos + (s == 0), neg + (s == 1), zero + (s == 2))
            rec["%s_pos" % ref] = pos
            rec["%s_neg" % ref] = neg
            rec["%s_zero" % ref] = zero
            rec["%s_skip" % ref] = skip
        b1 = b2 = s1 = s2 = 0
        for r in sub:
            m = r["_m"]
            bv, sv = f(m["bq_vol"]), f(m["sq_vol"])
            bvi, svi = f(m["bq_val"]), f(m["sq_val"])
            pl, amin, amax = f(r.get("p_last")), f(r.get("allowed_min")), f(r.get("allowed_max"))
            lock_b = pl > 0 and amax > 0 and abs(pl - amax) < 1e-9
            lock_s = pl > 0 and amin > 0 and abs(pl - amin) < 1e-9
            if bvi > 0 and not svi:
                b1 += 1
            if svi > 0 and not bvi:
                s1 += 1
            if bv > 0 and sv == 0:
                b2 += 1
            if sv > 0 and bv == 0:
                s2 += 1
            if lock_b and bvi > 0:
                rec["_lb"] = rec.get("_lb", 0) + 1
            if lock_s and svi > 0:
                rec["_ls"] = rec.get("_ls", 0) + 1
            if lock_b and bvi > 0 and not svi:
                rec["_lbo"] = rec.get("_lbo", 0) + 1
            if lock_s and svi > 0 and not bvi:
                rec["_lso"] = rec.get("_lso", 0) + 1
        rec["q1val_b"], rec["q1val_s"] = b1, s1
        rec["q1vol_b"], rec["q1vol_s"] = b2, s2
        rec["qlock_b"] = rec.pop("_lb", 0)
        rec["qlock_s"] = rec.pop("_ls", 0)
        rec["qlock_one_b"] = rec.pop("_lbo", 0)
        rec["qlock_one_s"] = rec.pop("_lso", 0)
        out[uname] = rec
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--minutes", type=int, default=85)
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--once", action="store_true", help="یک نمونه و خروج (سنجشِ ابزار)")
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = ap.parse_args()
    sys.path.insert(0, a.repo)
    import mstat_engine as mod
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, "our_minute_defs.jsonl")
    t_end = time.time() + a.minutes * 60.0
    n = 0
    while time.time() < t_end:
        t0 = time.perf_counter()
        try:
            con = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"),
                                  uri=True, timeout=8)
            day, h = con.execute("SELECT MAX(d_even), MAX(h_even) FROM market_watch").fetchone()
            rows, meta = mod.enrich(con)          # فقط SELECT؛ همان مسیری که پنل می‌رود
            h = meta.get("h_even")
            con.close()
        except (sqlite3.Error, OSError) as e:
            print("read failed:", type(e).__name__, str(e)[:120], flush=True)
            time.sleep(a.interval)
            continue
        rec = {"wall_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
               "day": day, "h_even": h, "universes": counts(rows, mod)}
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        n += 1
        u = rec["universes"]["cat_all"]
        e = rec["universes"]["eq_all"]
        print("%s h=%s | cat_all closing=%s/%s eq_all closing=%s/%s | q1val=%s/%s qlock=%s/%s"
              % (rec["wall_local"][11:19], h, u["closing_pos"], u["closing_neg"],
                 e["closing_pos"], e["closing_neg"],
                 u["q1val_b"], u["q1val_s"], u["qlock_b"], u["qlock_s"]), flush=True)
        if a.once:
            break
        left = a.interval - (time.perf_counter() - t0)
        if left > 0 and time.time() < t_end:
            time.sleep(left)
    print("wrote %d minute-rows to %s" % (n, path))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
