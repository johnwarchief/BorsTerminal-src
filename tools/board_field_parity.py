#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/board_field_parity.py — ماتریس تطبیق فیلد‌به‌فیلد، در یکِ لحظه.

سه طرف که در چند ثانیه می‌خوانده می‌شوند (نه در دو ساعتِ متفاوت):
  • تابلوی خودِ منبع        cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch  (+ ClientType/GetClientTypeAll)
  • اندپوینت برنامۀ نصبی    GET /api/market
  • (لایۀ دوم، --ctv)        ClientType/GetClientTypeHistory برای نمادهای نمونه

نگاشتِ فیلدها از کدِ دریافتِ خودِ برنامه برداشته شده (test_tsetmc._mw_row /
queue_agg / board_market_cap) — چیزی از حافظه اضافه نشده است. تکلیفِ هر جفت:

  MATCH              اختلافِ سنجیده زیرِ تلورانس
  MISMATCH           بالاتر از تلورانس (خطای فرمول/نگاشت کاندید)
  STALE              شمارنده‌هایِ انباشتیِ ما **کمتر** از منبع، درحالی‌که ساعتِ
                     ردیفِ منبع تازه‌تر است ⇒ اختلاف از زمانِ snapshot است، نه فرمول
  MISSING_SOURCE     خانۀ منبع نیامده (سنسور ندارد)
  MISSING_MAPPING    منبع عدد دارد، ما کلیدِ معتبر نداریم
  NOT_COMPARABLE     یکِ طرف null است (بی‌داده با صفر یکی نمی‌شود)

فقط‌خواندنی: هیچ نوشتن رویِ بانک، هیچ restart، هیچ تغییرِ polling/cache.

اجرا:  PYTHONIOENCODING=utf-8 python tools/board_field_parity.py \
          [--base http://127.0.0.1:8001] [--ctv 30] [--out _audit/market_parity_20261014]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import test_tsetmc as TT                       # noqa: E402
import client_split                            # noqa: E402

MW_URL = TT.MW_URL
CT_URL = f"{TT.BASE}/ClientType/GetClientTypeAll"
CTH_URL = f"{TT.BASE}/ClientType/GetClientTypeHistory"
HDRS = dict(TT.HEADERS)

PORTS = (8001, 8012, 8002, 8021, 8000, 5173)


def discover_backend(explicit=None):
    """پورت را به‌خاطر نمی‌سپارم — هر ششِ آشنا را می‌کاوم."""
    cands = [explicit] if explicit else [f"http://127.0.0.1:{p}" for p in PORTS]
    for base in cands:
        if not base:
            continue
        try:
            j = get_json(base.rstrip("/") + "/api/update/version", timeout=4)
            if j.get("version"):
                return base.rstrip("/"), j
        except Exception:                                       # noqa: BLE001
            continue
    return None, None


def get_json(url, timeout=60):
    # سرِ خودِ برنامه روی Origin/Refererِ بیگانه ۴۰۳ می‌دهد؛ هدرهایِ TSETMC را
    # فقط به همان میزبان بده، وگرنه کاوشگرِ خودش را کور می‌کند.
    hdrs = HDRS if "tsetmc.com" in url else {"User-Agent": "bors-parity"}
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def hms(ts=None):
    return (ts if ts is not None else time.time())


def clock(t):
    return dt.datetime.fromtimestamp(t).strftime("%H:%M:%S")


# ── تعریفِ فیلدها ────────────────────────────────────────────────────────────
# kind: exact=هر تلورانسِ بیش از tol خطاست · mono=شمارندۀ انباشتی (کمبود ⇒ STALE)
# ref/ours: callable رویِ (ردیفِ خامِ تابلو، ردیفِ clientType) یا (ردیفِ ما، ردیفِ منبع)
def _q_first(row, key):
    lines = row.get("blDs")
    if not isinstance(lines, list) or not lines or not isinstance(lines[0], dict):
        return None
    return num(lines[0].get(key))


def _mcap(row, _c=None):
    v, _src = TT.board_market_cap(row)
    return v


def _implied_shares(our_row, src_row):
    """ارزشِ بازارِ ذخیرۀ ما ÷ قیمتِ پایانیِ منبع = تعدادِ سهامی که ما نگه داشته‌ایم.

   Stage 3 بند ۱ و ۲: اگر این عدد با ztdِ خودِ منبع یکی باشد، اختلافِ ارزشِ بازار
    از قیمت/زمانِ snapshot است نه از تعدادِ سهام.
    """
    m, p = num(our_row.get("mcap")), num(src_row.get("pcl"))
    if not m or not p or p <= 0:
        return None
    return m / p


def _per_capita(row, vol_k, cnt_k):
    v, c = num(row.get(vol_k)), num(row.get(cnt_k))
    if v is None or c is None or c <= 0:
        return None
    return v / c


FIELDS = [
    # (fid, عنوانِ فارسی, خواندنِ از ما, خواندنِ از منبع, واحد, kind, tol)
    ("p_last", "آخرین معامله", lambda o, r, c: num(o.get("p_last")),
     lambda r, c: num(r.get("pdv")), "ریال", "exact", 1.0),
    ("p_closing", "قیمت پایانی", lambda o, r, c: num(o.get("p_closing")),
     lambda r, c: num(r.get("pcl")), "ریال", "exact", 1.0),
    ("p_first", "اولین قیمت", lambda o, r, c: num(o.get("p_first")),
     lambda r, c: num(r.get("pf")), "ریال", "exact", 1.0),
    # pMax/pMin درِ این پاسخ **سقف/کفِ مجاز** قیمت است نه بیشترین/کمترینِ
    # معامله‌شده — سنجشِ tools/tse_price_range_semantics.py رویِ ۳٬۱۰۸ ردیف:
    # price_max ما == pmx در ۳٬۰۵۶ ردیف، ولی == pMax فقط در ۴۷۴؛ و pMax در
    # ۱٬۳۱۰ ردیف بیش از سه‌برابرِ قیمتِ آخرین است. مقایسۀ پیشین با pMax،
    # نگاشتِ خودِ ابزار را اشتباه گرفته بود (نه خطایِ برنامه).
    ("p_max", "بیشترین قیمتِ معامله‌شده", lambda o, r, c: num(o.get("p_max")),
     lambda r, c: num(r.get("pmx")), "ریال", "exact", 1.0),
    ("p_min", "کمترین قیمتِ معامله‌شده", lambda o, r, c: num(o.get("p_min")),
     lambda r, c: num(r.get("pmn")), "ریال", "exact", 1.0),
    ("allowed_min", "کفِ مجاز (tminِ ما ← pMinِ منبع)", lambda o, r, c: num(o.get("tmin")),
     lambda r, c: num(r.get("pMin")), "ریال", "exact", 1.0),
    ("price_yesterday", "قیمت دیروز", lambda o, r, c: num(o.get("price_yesterday")),
     lambda r, c: num(r.get("py")), "ریال", "exact", 1.0),
    ("price_change", "تغییر عددی", lambda o, r, c: num(o.get("price_change")),
     lambda r, c: num(r.get("pc")), "ریال", "exact", 1.0),
    ("volume", "حجم", lambda o, r, c: num(o.get("q_tot_tran")),
     lambda r, c: num(r.get("qtj")), "سهم", "mono", 0.02),
    ("traded_value", "ارزش معاملات", lambda o, r, c: num(o.get("q_tot_cap")),
     lambda r, c: num(r.get("qtc")), "ریال", "mono", 0.02),
    ("trade_count", "تعداد معاملات", lambda o, r, c: num(o.get("z_tot_tran")),
     lambda r, c: num(r.get("ztt")), "عدد", "mono", 0.02),
    ("mcap", "ارزش بازار (در برابر pcl×ztd منبع)", lambda o, r, c: num(o.get("mcap")),
     lambda r, c: _mcap(r), "ریال", "exact", 1.0),
    ("implied_shares", "تعداد سهامِ ضمنیِ ما (mcap÷pcl)", _implied_shares,
     lambda r, c: num(r.get("ztd")), "سهم", "exact", 1.0),
    ("stored_shares", "تعداد سهامِ ذخیرۀ ما (market_watch)",
     lambda o, r, c: num(o.get("_store_total_shares")),
     lambda r, c: num(r.get("ztd")), "سهم", "exact", 1.0),
    ("buy_q1_px", "قیمت صف اول خرید", lambda o, r, c: num(o.get("buy_q1_px")),
     lambda r, c: _q_first(r, "pmd"), "ریال", "exact", 1.0),
    ("buy_q1_vol", "حجم صف اول خرید", lambda o, r, c: num(o.get("buy_q1_vol")),
     lambda r, c: _q_first(r, "qmd"), "سهم", "mono", 0.05),
    ("buy_q1_cnt", "تعداد سفارش صف اول خرید", lambda o, r, c: num(o.get("buy_q1_cnt")),
     lambda r, c: _q_first(r, "zmd"), "سفارش", "mono", 0.05),
    ("sell_q1_px", "قیمت صف اول فروش", lambda o, r, c: num(o.get("sell_q1_px")),
     lambda r, c: _q_first(r, "pmo"), "ریال", "exact", 1.0),
    ("sell_q1_vol", "حجم صف اول فروش", lambda o, r, c: num(o.get("sell_q1_vol")),
     lambda r, c: _q_first(r, "qmo"), "سهم", "mono", 0.05),
    ("buy_i_vol", "حجم خرید حقیقی", lambda o, r, c: num(o.get("buy_i_vol")),
     lambda r, c: num(c.get("buy_I_Volume")), "سهم", "mono", 0.02),
    ("sell_i_vol", "حجم فروش حقیقی", lambda o, r, c: num(o.get("sell_i_vol")),
     lambda r, c: num(c.get("sell_I_Volume")), "سهم", "mono", 0.02),
    ("buy_count_i", "تعداد خریدار حقیقی", lambda o, r, c: num(o.get("buy_count_i")),
     lambda r, c: num(c.get("buy_CountI")), "نفر", "mono", 0.02),
    ("sell_count_i", "تعداد فروشنده حقیقی", lambda o, r, c: num(o.get("sell_count_i")),
     lambda r, c: num(c.get("sell_CountI")), "نفر", "mono", 0.02),
    # سرانه از خودِ منبع: حجم ÷ تعداد — همان تعریفی که buy_power_i ما می‌سازد
    ("buy_per_capita_shares", "سرانه خرید (سهم/نفر)", lambda o, r, c: num(o.get("buy_power_i")),
     lambda r, c: _per_capita(c, "buy_I_Volume", "buy_CountI"), "سهم/نفر", "exact", 1.0),
    ("sell_per_capita_shares", "سرانه فروش (سهم/نفر)", lambda o, r, c: num(o.get("sell_power_i")),
     lambda r, c: _per_capita(c, "sell_I_Volume", "sell_CountI"), "سهم/نفر", "exact", 1.0),
]


def classify(ours, ref, kind, tol):
    """داوریِ جفت‌مقداری.

    `mono` (شمارندۀ انباشتی): تلورانسِ **نسبی** — چون حجمِ امروز درِ ساعتِ بازار
    بزرگ و بزرگ‌تر می‌شود، و کمبودِ ما یعنی snapshotِ ما قدیمی‌تر است (STALE)،
    نه فرمولِ غلط.
    `exact` (قیمت، سرانه، ارزشِ بازار): تلورانسِ **قدرِ مطلق** (یکِ تیکِ قیمت).
    تلورانسِ نسبیِ درشت اینجا خطا را می‌پوشاند: رویِ عددِ ۸e15، rel≤1 یعنی
    «هرچه تا صدِ برابر، درست» — که دقیقاً همان دروغی است که این ابزار نباید
    بگوید.
    """
    if ref is None:
        return "MISSING_SOURCE", None
    if ours is None:
        return "MISSING_MAPPING", None
    d = abs(ours - ref)
    rel = (d / abs(ref)) if ref else d
    if kind == "mono":
        if rel <= tol:
            return "MATCH", rel
        return ("STALE", rel) if ours < ref else ("MISMATCH", rel)
    if d <= tol:
        return "MATCH", rel
    return "MISMATCH", rel


def load_store_shares(db_path, day):
    """تعدادِ سهامِ ذخیره‌شدۀ ما (mode=ro، بی‌هیچ نوشتن).

    چرا ازِ بانکِ نه ازِ API: ردیفِ /api/market بی‌ستونِ total_shares است، و
    بندِ ۱ و ۳ مرحلۀ ۳ دقیقاً همان «تعدادِ سهامِ موردِ استفادۀ محاسبه» را می‌پرسند.
    """
    import sqlite3
    try:
        c = sqlite3.connect("file:" + os.path.abspath(db_path).replace(chr(92), "/")
                            + "?mode=ro", uri=True)
    except Exception:                                            # noqa: BLE001
        return {}
    try:
        cols = {r[1] for r in c.execute("PRAGMA table_info(market_watch)")}
        if "total_shares" not in cols:
            return {}
        return {str(r[0]): r[1] for r in c.execute(
            "SELECT ins_code, total_shares FROM market_watch WHERE d_even=?", (day,))}
    except Exception:                                            # noqa: BLE001
        return {}
    finally:
        c.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None)
    ap.add_argument("--ctv", type=int, default=0, help="نمونۀ GetClientTypeHistory")
    ap.add_argument("--db", default=None, help="برایِ شمارشِ تعدادِ سهامِ ذخیره‌شده (فقط‌خواندنی)")
    ap.add_argument("--same-instant", action="store_true",
                    help="فقط ردیف‌هایی که ساعتِ خودِ ردیفِ ما == hEvenِ منبع‌اند")
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit", "market_parity_20261014"))
    ap.add_argument("--tag", default="", help="برچسبِ نامِ فایلِ خروجی (live/sameinstant/…)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    base, ver = discover_backend(a.base)
    if not base:
        print("هیچ بک‌اندِ در حالِ اجرا پیدا نشد — مقایسه با API ممکن نیست.")
        return 2
    print(f"بک‌اند: {base}  نسخۀ {ver.get('version')}  حالت {ver.get('mode')}")

    t = {}
    t["ours"] = hms()
    our_api = get_json(base + "/api/market", timeout=60)
    t["mw"] = hms()
    mw = get_json(MW_URL, timeout=90)
    mw_rows = mw.get("marketwatch") if isinstance(mw, dict) else mw
    t["ct"] = hms()
    ct = get_json(CT_URL, timeout=90)
    ct_rows = ct.get("clientTypeAllDto") if isinstance(ct, dict) else ct

    ours = {str(r.get("ins_code")): r for r in (our_api.get("data") or []) if r.get("ins_code")}
    src = {str(r.get("insCode")): r for r in (mw_rows or []) if r.get("insCode")}
    cts = {str(r.get("insCode")): r for r in (ct_rows or []) if r.get("insCode")}
    day = int((our_api.get("meta") or {}).get("d_even") or 0)
    store = load_store_shares(a.db or os.path.join(ROOT, "market.db"), day)
    for code, sh in store.items():
        if code in ours:
            ours[code]["_store_total_shares"] = sh
    print("تعدادِ سهامِ ذخیره‌شدۀ ما (read-only): %d ردیف در نشست %s" % (len(store), day))
    common = sorted(set(ours) & set(src))
    if a.same_instant:
        common = [c for c in common
                  if num(ours[c].get("row_h")) == num(src[c].get("hEven"))]
        print("پس از گیتِ «هم‌نفس» (ساعتِ ردیفِ ما == hEven منبع): %d ردیف" % len(common))
    print("ردیف: ما %d | تابلوی منبع %d | clientType منبع %d | مشترکِ ما∩منبع %d"
          % (len(ours), len(src), len(cts), len(common)))

    # واچ‌لیستِ منبعِ زنده (برایِ شمارشِ ردیفِ جاافتاده در دامانۀ بازارِ باز)
    live_src = {k for k, r in src.items() if num(r.get("hEven"))}
    we_have_live = {k for k in common if num(ours[k].get("row_h"))}
    missing_rows = sorted(live_src - set(ours))
    extra_rows = sorted(set(ours) - live_src)

    summary = {}
    detail = []
    for fid, label, ours_getter, ref_getter, unit, kind, tol in FIELDS:
        cnt = {}
        rels = []
        for code in common:
            o = ours[code]
            r = src[code]
            c = cts.get(code, {})
            try:
                ref = ref_getter(r, c)
                ov = ours_getter(o, r, c)
            except Exception:                                    # noqa: BLE001
                ref = ov = None
            st, rel = classify(ov, ref, kind, tol)
            cnt[st] = cnt.get(st, 0) + 1
            if rel is not None:
                rels.append(rel)
            if st == "MISMATCH":
                detail.append({"ins_code": code, "symbol": o.get("symbol"), "field": fid,
                               "ours": ov, "ref": ref, "rel": round(rel, 6),
                               "unit": unit, "our_hEven": o.get("row_h"),
                               "src_hEven": num(r.get("hEven")),
                               "is_live": o.get("is_live")})
        summary[fid] = {
            "label": label, "unit": unit, "kind": kind, "tol": tol,
            "counts": cnt, "compared": sum(v for k, v in cnt.items() if k != "MISSING_SOURCE"),
            "median_rel": (sorted(rels)[len(rels) // 2] if rels else None),
            "p95_rel": (sorted(rels)[int(len(rels) * 0.95) - 1] if rels else None),
        }

    # ── لایۀ دوم: درصدِ ارزشِ حقیقی/حقوقی ─────────────────────────────────────
    ctv_rows = []
    if a.ctv:
        sample = pick_sample(common, ours, a.ctv)
        day = int(our_api.get("meta", {}).get("d_even") or 0)
        for code in sample:
            rec = {"ins_code": code, "symbol": ours[code].get("symbol")}
            try:
                payload = get_json(f"{CTH_URL}/{code}/{day}", timeout=25)
                row = (payload or {}).get("clientType") or {}
            except Exception as e:                               # noqa: BLE001
                rec["source_status"] = "REFERENCE_UNAVAILABLE:%s" % type(e).__name__
                ctv_rows.append(rec)
                time.sleep(0.4)
                continue
            vals = [num(row.get(k)) for k in ("buy_I_Value", "buy_N_Value",
                                              "sell_I_Value", "sell_N_Value")]
            # دو املا دیدم؛ اینجا حدس نمی‌زنم — هر دو نام خوانده می‌شود و
            # کلِ کلیدهایِ پاسخ درِ CSV ثبت می‌شود تا بازآزمون ممکن باشد.
            counts = [num(row.get(k)) for k in ("buy_I_Volume", "buy_CountI",
                                                "sell_I_Volume", "sell_CountI")]
            rec["src_keys"] = "|".join(sorted(row.keys()))
            ref_pct = client_split.shares(*vals) if all(v is not None for v in vals) else None
            mine = {k: num(ours[code].get(k)) for k in
                    ("retail_buy_pct", "legal_buy_pct", "retail_sell_pct", "legal_sell_pct")}
            rec.update({
                "src_buy_i_val": vals[0], "src_buy_n_val": vals[1],
                "src_sell_i_val": vals[2], "src_sell_n_val": vals[3],
                "src_recDate": num(row.get("recDate")),
                "ref_retail_buy_pct": (None if ref_pct is None else ref_pct["retail_buy_pct"]),
                "ref_retail_sell_pct": (None if ref_pct is None else ref_pct["retail_sell_pct"]),
                "our_retail_buy_pct": mine["retail_buy_pct"],
                "our_retail_sell_pct": mine["retail_sell_pct"],
                "our_pct_basis": ours[code].get("pct_basis"),
                "our_ctv_d": num(ours[code].get("ctv_d")),
                "our_pct_is_current": num(ours[code].get("pct_is_current")),
                "src_buy_i_vol": counts[0], "src_buy_count_i": counts[1],
                "our_buy_power_i": num(ours[code].get("buy_power_i")),
                "per_capita_value_rial": (None if not (counts[1] and vals[0])
                                          else vals[0] / counts[1]),
            })
            ctv_rows.append(rec)
            time.sleep(0.35)

    stamp = ((a.tag + "_") if a.tag else "") + dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(a.out, "parity_summary_%s.csv" % stamp), "w",
              newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["field_id", "برچسب", "واحد", "kind", "tol", "مقایسه‌شده",
                    "MATCH", "STALE", "MISMATCH", "MISSING_SOURCE", "MISSING_MAPPING",
                    "NOT_COMPARABLE", "mid_rel", "p95_rel"])
        for fid, s in summary.items():
            c = s["counts"]
            w.writerow([fid, s["label"], s["unit"], s["kind"], s["tol"],
                        s["compared"],
                        c.get("MATCH", 0), c.get("STALE", 0), c.get("MISMATCH", 0),
                        c.get("MISSING_SOURCE", 0), c.get("MISSING_MAPPING", 0),
                        c.get("NOT_COMPARABLE", 0),
                        s["median_rel"], s["p95_rel"]])
    with open(os.path.join(a.out, "parity_mismatches_%s.csv" % stamp), "w",
              newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(detail[0].keys()) if detail else ["ins_code"],
                           delimiter=";")
        w.writeheader()
        w.writerows(detail[:400])
    if ctv_rows:
        with open(os.path.join(a.out, "parity_value_split_%s.csv" % stamp), "w",
                  newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(ctv_rows[0].keys()), delimiter=";")
            w.writeheader()
            w.writerows(ctv_rows)
    json.dump({
        "backend": base, "backend_version": ver,
        "clock": {k: clock(v) for k, v in t.items()},
        "meta": our_api.get("meta"), "count": our_api.get("count"),
        "live_count": our_api.get("live_count"), "fossil_count": our_api.get("fossil_count"),
        "rows_ours": len(ours), "rows_source": len(src), "rows_ct": len(cts),
        "rows_source_with_hEven": len(live_src),
        "rows_missing_in_ours": len(missing_rows),
        "rows_only_in_ours": len(extra_rows),
        "sample_missing": missing_rows[:20], "summary": summary,
        "ctv": ctv_rows,
    }, open(os.path.join(a.out, "parity_%s.json" % stamp), "w", encoding="utf-8"),
        ensure_ascii=False, indent=1)

    # چاپِ خلاصه (RTL فارسی)
    print("\n" + "=" * 100)
    print(f"{'فیلد':28} {'مقایسه':>7} {'MATCH':>7} {'STALE':>7} {'MISMATCH':>9} "
          f"{'بی‌منبع':>7} {'mid_rel':>9}")
    print("-" * 100)
    for fid, s in summary.items():
        c = s["counts"]
        print(f"{s['label'][:26]:28} {s['compared']:>7} {c.get('MATCH', 0):>7} "
              f"{c.get('STALE', 0):>7} {c.get('MISMATCH', 0):>9} {c.get('MISSING_SOURCE', 0):>7} "
              f"{('%.4f' % s['median_rel']) if s['median_rel'] is not None else '—':>9}")
    print("-" * 100)
    print("ردیفِ بازارِ بازِ منبع که ما نداریم: %d | ردیفِ ما که منبع امروز ندارد: %d"
          % (len(missing_rows), len(extra_rows)))
    print("خروجی: %s" % a.out)
    return 0


def pick_sample(codes, ours, n):
    """نمونۀ متنوع: بزرگ/کم‌حجم/صندوق/حق‌تقدم/متوقف/بدونِ صف — از خودِ ردیف‌ها."""
    def key(c):
        r = ours[c]
        return num(r.get("q_tot_cap")) or 0.0
    by_val = sorted(codes, key=key, reverse=True)
    big = by_val[:12]
    small = [c for c in by_val if 0 < key(c)][:8]
    funds = [c for c in codes if "صندوق" in str(ours[c].get("name") or "")][:6]
    rights = [c for c in codes if str(ours[c].get("symbol") or "").startswith("ض")][:6]
    dead = [c for c in codes if ours[c].get("is_live") is False][:4]
    noq = [c for c in codes if not num(ours[c].get("buy_q1_px"))][:4]
    out, seen = [], set()
    for c in big + rights + funds + small[-8:] + dead + noq:
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
        if len(out) >= n:
            break
    return out


if __name__ == "__main__":
    sys.exit(main())
