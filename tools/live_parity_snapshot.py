#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""live_parity_snapshot.py — یکِ اسنپ‌شاتِ هم‌زمان از سهِ لایه، باِ حکمِ هر فیلد.

مأموریت (۲۰۶-۱۰-۱۸، فوری): تطبیقِ زندۀ TSETMC × TradersArena × BorsTerminal.
این فایل **فقط می‌خواند و می‌نویسد**: هیچ نوشتنی درِ بانک، هیچ فراخوانِ POST،
هیچ تغییرِ تنظیمات درِ منابع بیرونی.

چرا ابزارِ تازه، با وجودِ `market_tape_live_audit.py` و `ta_ref_capture.py`؟
آن دو یک لایه را می‌گیرند (تابلوخوانی از TSETMC / صفحۀ مرجع از TA). چیزی که
نبود، **یکِ لحظۀ مشترک** با **حکمِ هر فیلد** بود — وگرنه دو خوانش از دو زمان،
همان «اختلافِ تأخیر» را با «باگِ محاسبه» اشتباه می‌کند (بندِ ۱ مأموریت).

سه قیدِ روش:
  ۱) هویت با `insCode` است، نه نام. join رویِ نام، «آتيه06» را به «فولاد»
     می‌چسباند. نمادهایِ بی‌insCode شمرده می‌شوند، حذفِ بی‌شمارش نه.
  ۲) تطبیقِ نامِ فیلد حدس نیست: برایِ هر ستونِ BorsTerminal، کاندیداهایِ خامِ
     TSETMC سنجیده می‌شوند و **نرخِ توافقِ عددی** گزارش می‌شود؛ نگاشتِ برنده
     همان چیزی است که داده می‌گوید، و اگر هیچ کاندیدا زیرِ سقفِ توافق نرود
     فیلد `NOT_VERIFIED` می‌ماند (نه «صفر اختلاف»).
  ۳) زمانِ هر منبع ثبت می‌شود (`d_even`/`hEven`/`time[]`). اگر دو طرف هم‌پنجره
     نباشند، اختلاف `STALE` است نه `MISMATCH`.

خروجی: `_audit/live_parity/snapshot-<ts>.json` (همه‌چیز) + همان‌جا
`snapshot-<ts>.md` (ماتریسِ خوانا). اجرا:
    python tools/live_parity_snapshot.py                 # یکِ اسنپ‌شات
    python tools/live_parity_snapshot.py --bt http://127.0.0.1:8101
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import ssl
import sys
import urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

TSETMC_MW = ("https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&"
             + "&".join(f"paperTypes[{i}]={i+1}" for i in range(9))
             + "&showTraded=false&withBestLimits=true&hEven=0")
TA_URLS = {
    "totals0": "https://tradersarena.ir/data/market/chart/totals0",
    "industries": "https://tradersarena.ir/data/industries-csv",
    "symbols": "https://tradersarena.ir/data/mainwatch/symbols",
}
MSTAT = ("summary", "phase", "thermometer", "clientsplit", "industries", "board")

# نگاشتِ ارجاع: ستونِ BorsTerminal → کاندیداهایِ خامِ TSETMC. این فهرست «حدسِ
# قابل‌آزمون» است، نه حکم: برایِ هر جفت، نرخِ توافق رویِ کلِ جامعه سنجیده و
# برنده گزارش می‌شود.
FIELD_CANDIDATES = {
    # این نگاشت ازِ نه نمادِ زنده درِ ۱۱:۲۵ (آ س پ، آباد، آبادا، آبنوس، آبي،
    # آتيه ملت، آذرين، آرام، آرامش) سطر‌به‌سطر درج‌بند شد؛ هر خانۀِ خامی که درِ
    # هر نه نماد باِ ستونِ برنامه برابر نبود حذف شده است.
    #
    # دو تله که ابزارِ همین فایل را اول اشتباه انداخت (و نام‌هایِ TSETMC مقصرند،
    # نه نگاشتِ برنامه):
    #   • `pcl` = قیمت **پایانی** است و `pdv` = قیمت **آخرین** — نه برعکس.
    #   • `pMax`/`pMin` = **حدِّ مجازِ** نوسانِ امروزند (دیروز × ۱٫۰۳ و × ۰٫۹۷)
    #     و `pmx`/`pmn` = بیشترین/کمترینِ **واقعیِ** امروز.
    # پس `tminِ` برنامه همان `pMin` است و `p_minِ` برنامه همان `pmn`.
    "p_last": ["pdv"],
    "p_closing": ["pcl"],
    "price_yesterday": ["py"],
    "p_first": ["pf"],
    "p_max": ["pmx"],
    "p_min": ["pmn"],
    "tmin": ["pMin"],
    "price_change": ["pc", "pcpc"],
    "q_tot_tran": ["qtj"],
    "z_tot_tran": ["ztt"],
}

# فیلدهایی که «باید» دقیقاً برابر باشند (قیمت): بی‌تلورانس، و بی‌مقدار ⇒ MISSING
PRICE_FIELDS = ("p_last", "p_closing", "price_yesterday", "p_first", "p_max", "p_min")


def _get(url: str, headers: dict | None = None, timeout: float = 45.0):
    req = urllib.request.Request(url, headers=headers or {})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.status, r.read()


def _json(url: str, headers: dict | None = None, timeout: float = 45.0):
    t0 = dt.datetime.now()
    try:
        code, body = _get(url, headers, timeout)
        return {"ok": True, "code": code, "ms": int((dt.datetime.now() - t0).total_seconds() * 1000),
                "fetched_at": t0.isoformat(timespec="seconds"), "data": json.loads(body)}
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "err": type(e).__name__ + ": " + str(e)[:160],
                "fetched_at": t0.isoformat(timespec="seconds")}


def fetch_tsetmc() -> dict:
    h = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
         "Accept": "application/json, text/plain, */*",
         "Referer": "https://tsetmc.com/", "Origin": "https://tsetmc.com"}
    out = _json(TSETMC_MW, h)
    if out.get("ok"):
        rows = (out["data"] or {}).get("marketwatch") or []
        flat = []
        for r in rows:
            row = {k: v for k, v in r.items() if k != "blDs"}
            row["_depth"] = r.get("blDs") or []
            flat.append(row)
        out["rows"] = flat
        del out["data"]
    return out


def fetch_ta() -> dict:
    h = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
         "Accept": "application/json, text/plain, */*", "Referer": "https://tradersarena.ir/"}
    return {k: _json(v, h) for k, v in TA_URLS.items()}


def fetch_bt(bt: str) -> dict:
    out = {"market": _json(bt + "/api/market")}
    for name in MSTAT:
        out["mstat_" + name] = _json(bt + f"/api/mstat/{name}", timeout=25.0)
    return out


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


def _key_of(row: dict, *names) -> str:
    for n in names:
        v = row.get(n)
        if v:
            return str(v).strip()
    return ""


def compare_universe(ts_rows, bt_rows, ta_rows) -> dict:
    """تطبیقِ هویت، نه نام: insCode کلیدِ اصلی، ISIN پشتیبان."""
    ts = {_key_of(r, "insCode"): r for r in ts_rows if _key_of(r, "insCode")}
    bt = {_key_of(r, "ins_code"): r for r in bt_rows if _key_of(r, "ins_code")}
    # صفحۀ مرجع ردیف را آرایۀِ وضعی می‌دهد (سرستون ندارد): [insCode, isin,
    # symbol, ...اعداد]. پس هویت ازِ خانۀِ صفر می‌آید و معنیِ بقیه خان‌ها را
    # باز هم *داده* می‌گوید، نه حدسِ جایِ ستون (`ta_probe`).
    ta = {}
    for r in ta_rows:
        if isinstance(r, list) and r and r[0]:
            ta[str(r[0])] = {"insCode": str(r[0]), "isin": str(r[1]) if len(r) > 1 else "",
                             "symbol": r[2] if len(r) > 2 else "", "nums": r[3:]}
        elif isinstance(r, dict) and _key_of(r, "insCode", "ins_code", "isn"):
            ta[_key_of(r, "insCode", "ins_code", "isn")] = r
    both = sorted(set(ts) & set(bt))
    return {
        "counts": {"tsetmc": len(ts), "bors_all": len(bt),
                   "bors_live": sum(1 for r in bt_rows if r.get("is_live")),
                   "tradersarena": len(ta)},
        "joined_tsetmc_bors": len(both),
        "only_tsetmc": len(set(ts) - set(bt)),
        "only_bors": len(set(bt) - set(ts)),
        "only_bors_live": sum(1 for k in (set(bt) - set(ts)) if bt[k].get("is_live")),
        "joined_ta": len(set(bt) & set(ta)) if ta else 0,
        "only_ta": len(set(ta) - set(bt)) if ta else 0,
        "samples_only_tsetmc": [ts[k].get("lva") for k in list(set(ts) - set(bt))[:12]],
        "samples_only_bors": [bt[k].get("symbol") for k in list(set(bt) - set(ts))[:12]],
        "_keys": both, "_bt_by_key": bt, "_ts_by_key": ts,
    }


def compare_fields(bt_by_key, ts_by_key, keys) -> dict:
    """نگاشتِ ارجاع از خودِ داده: نرخِ توافقِ هر کاندیدا، بعد حکمِ فیلدِ برنده."""
    out = {}
    for field, cands in FIELD_CANDIDATES.items():
        stats = {}
        for c in cands:
            same = diff = both_missing = 0
            worst = 0.0
            for k in keys:
                a = _num(bt_by_key[k].get(field))
                b = _num(ts_by_key[k].get(c))
                if a is None and b is None:
                    both_missing += 1
                    continue
                if a is None or b is None:
                    continue
                if a == b or (max(abs(a), abs(b)) > 0 and abs(a - b) / max(abs(a), abs(b)) <= 1e-9):
                    same += 1
                else:
                    diff += 1
                    rel = abs(a - b) / max(abs(a), abs(b))
                    worst = max(worst, rel)
            n = same + diff
            stats[c] = {"agree": same, "differ": diff, "compared": n,
                        "rate": round(same / n, 4) if n else None,
                        "both_missing": both_missing, "max_rel_diff": round(worst, 6)}
        best = max(stats.items(), key=lambda kv: (kv[1]["rate"] or -1)) if stats else (None, None)
        out[field] = {"candidates": stats, "best": best[0],
                      "best_rate": (best[1] or {}).get("rate"),
                      "verdict": ("MAPPED" if ((best[1] or {}).get("rate") or -1) >= 0.98
                                  else ("NOT_VERIFIED" if best[1] else "NO_CANDIDATE"))}
    return out


def same_tick_keys(bt_by_key, ts_by_key, keys) -> list:
    """زیرمجموعۀِ «همان تیک»: برنامه و منبع هر دو زمانِ ردیفشان را می‌گویند
    (`row_h` در برابرِ `hEven`). مقایسه فقط رویِ این زیرمجموعه، تأخیرِ انتشار را
    از باگِ محاسبه جدا می‌کند — چیزی که مقایسۀِ دقیقِ عددی رویِ کلِ جامعه
    نمی‌تواند (حجمِ یکِ نماد درِ ده ثانیه سه بار عوض می‌شود)."""
    out = []
    for k in keys:
        a = _num(bt_by_key[k].get("row_h"))
        b = _num(ts_by_key[k].get("hEven"))
        if a is not None and a == b:
            out.append(k)
    return out


def field_mismatches(bt_by_key, ts_by_key, keys, mapping) -> dict:
    """برایِ هر فیلدِ نگاشت‌شده، خودِ اختلاف‌ها: چند تا، کدام‌ها، با چقدر."""
    rows = []
    for field, info in mapping.items():
        c = info.get("best")
        if not c or info["verdict"] != "MAPPED":
            continue
        bad = []
        stale = 0
        for k in keys:
            a = _num(bt_by_key[k].get(field))
            b = _num(ts_by_key[k].get(c))
            if a is None or b is None:
                if (a is None) != (b is None):
                    bad.append({"key": k, "symbol": bt_by_key[k].get("symbol"),
                                "bors": a, "tsetmc": b, "verdict": "MISSING"})
                continue
            if a != b:
                # اختلافِ تأخیر؟ TSETMC همین حالا pcl را عوض کرده و BT هنوز نه
                he_bt = _num(bt_by_key[k].get("row_h")) or 0
                he_ts = _num(ts_by_key[k].get("hEven")) or 0
                bad.append({"key": k, "symbol": bt_by_key[k].get("symbol"),
                            "bors": a, "tsetmc": b,
                            "rel_pct": round(100.0 * (a - b) / b, 4) if b else None,
                            "bt_row_h": he_bt, "ts_hEven": he_ts,
                            "verdict": "STALE" if he_ts > he_bt else "MISMATCH"})
        rows.append({"field": field, "source_column": c, "compared": len(keys),
                     "diffs": len(bad),
                     "stale": sum(1 for x in bad if x["verdict"] == "STALE"),
                     "missing": sum(1 for x in bad if x["verdict"] == "MISSING"),
                     "examples": bad[:10]})
    return {"rows": rows, "total_diffs": sum(r["diffs"] for r in rows)}


def ta_probe(bt_by_key, ts_by_key, ta_by_key, keys) -> dict:
    """معنیِ خان‌هایِ وضعیِ مرجع ازِ نرخِ توافق، نه ازِ ترتیبِ ستون.

    برایِ هر خانۀ عددیِ `mainwatch/symbols`، توافقش با سه ستونِ شناخته‌شدۀ
    BorsTerminal سنجیده می‌شود. خانۀ‌ای که با `p_last` می‌خورد = آخرینِ همان
    روز، و خانه‌ای که با `percent_change` می‌خورد = درصدِ تغییر. هیچ حکمی بی‌این
    توافق نمی‌شود؛ بی‌کاندیدایِ ≥۹۸٪ خانۀ `NOT_VERIFIED` می‌ماند.
    """
    out = {}
    idx = [k for k in keys if k in ta_by_key][:1200]
    if not idx:
        return {"verdict": "NOT_RUN", "why": "هیچ خانۀِ مشترکی بینِ مرجع و برنامه نیست"}
    width = max(len(ta_by_key[k].get("nums") or []) for k in idx)
    for pos in range(min(width, 14)):
        row = {}
        for field in ("p_last", "p_closing", "percent_change", "q_tot_tran"):
            same = diff = 0
            for k in idx:
                nums = ta_by_key[k].get("nums") or []
                if pos >= len(nums):
                    continue
                a = _num(bt_by_key[k].get(field))
                b = _num(nums[pos])
                if a is None or b is None:
                    continue
                if a == b:
                    same += 1
                else:
                    diff += 1
            n = same + diff
            row[field] = {"agree": same, "differ": diff,
                          "rate": round(same / n, 4) if n else None}
        best = max(row.items(), key=lambda kv: kv[1]["rate"] or -1)
        out[pos] = {"against": row, "matches": best[0] if (best[1]["rate"] or 0) >= 0.98 else None}
    return {"compared_symbols": len(idx), "columns": out}


def aggregates(bt_market, ts_rows, ta) -> dict:
    """لایۀ تجمعی: ارزشِ معاملات ≠ ارزشِ بازار (بندِ ۲-الف مأموریت)."""
    def s(rows, key):
        tot = 0.0
        n = 0
        for r in rows:
            v = _num(r.get(key))
            if v:
                tot += v
                n += 1
        return {"sum": round(tot, 2), "rows_with_value": n}

    ts_live = [r for r in ts_rows if (_num(r.get("ztt")) or 0) > 0 or (_num(r.get("pcl")) or 0) > 0]
    bt_rows = ((bt_market.get("data") or {}).get("data") or []) if bt_market.get("ok") else []
    bt_live = [r for r in bt_rows if r.get("is_live")]
    out = {
        # qtj=حجم، qtc=ارزش، ztt=تعدادِ معامله. پیش از این ztt/ztd/vc به‌جایِ این‌ها
        # خوانده می‌شد و «حجم» در گزارش، تعدادِ معامله بود؛ mcap هم در این اندپوینت
        # همیشه null است، پس عددِ جایگزین ساخته نمی‌شود.
        "tsetmc": {"volume": s(ts_rows, "qtj"), "value": s(ts_rows, "qtc"),
                   "count": s(ts_rows, "ztt"),
                   "mcap": s(ts_rows, "mcap") if any(r.get("mcap") is not None for r in ts_rows) else None,
                   "rows_with_trade": len(ts_live)},
        "bors": {"volume": s(bt_live, "q_tot_tran"),
                 # ارزشِ معاملات ازِ همان ستونی که واقعاً پر است؛ اگر `tval`
                 # نبود، `z_tot_tran` جایش را نمی‌گیرد (آن تعدادِ معاملۀ ماست،
                 # نه ارزش) — بی‌ستونِ ارزش صریح null می‌ماند.
                 "value": s(bt_live, "tval") if any(r.get("tval") for r in bt_live) else None,
                 "count": s(bt_live, "z_tot_tran"), "mcap": s(bt_live, "mcap"),
                 "q_tot_cap": s(bt_live, "q_tot_cap"), "rows_live": len(bt_live)},
        "timing": {"bors_meta": ((bt_market.get("data") or {}).get("meta") if bt_market.get("ok") else None),
                   "tsetmc_hEven": sorted({int(_num(r.get("hEven")) or 0) for r in ts_rows})[-3:]},
    }
    if ta.get("totals0", {}).get("ok"):
        t = (ta["totals0"].get("data") or {})
        out["tradersarena"] = {"series_keys": sorted(t.keys())[:24],
                               "last_time": (t.get("time") or [None])[-1],
                               "n_points": len(t.get("time") or [])}
    else:
        out["tradersarena"] = {"verdict": "BLOCKED", "err": ta.get("totals0", {}).get("err")}
    return out


def latency_probe(bt: str, eps=("market", "mstat/summary", "mstat/phase",
                                "mstat/thermometer"), n: int = 5) -> dict:
    """تأخیرِ هر اندپوینت درِ چندِ نمونهٔ پشت‌سرهم.

    چرا: یکِ نمونه نمی‌گوید چیزی — گلوگاهِ این برنامه «دوره‌ای» است (میانی
    ۰٫۰۱s و یکِ مکثِ چندده‌ثانیه‌ای درِ همان نشست). پس p50/p95/bیشینه و
    شمارۀِ timeoutها ثبت می‌شود، نه میانگین."""
    out = {}
    for ep in eps:
        ts = []
        for _ in range(n):
            t0 = dt.datetime.now()
            try:
                _get(bt + "/api/" + ep, timeout=60.0)
                ts.append(round((dt.datetime.now() - t0).total_seconds(), 2))
            except Exception:                              # noqa: BLE001
                ts.append(None)
        good = sorted(x for x in ts if x is not None)
        out[ep] = {"samples": ts, "n_ok": len(good),
                   "p50": (good[len(good) // 2] if good else None),
                   "p95": (good[max(0, int(round(0.95 * (len(good) - 1))))] if good else None),
                   "max": (good[-1] if good else None),
                   "timeouts": len(ts) - len(good)}
    return out



def market_level(bt_rows, bt_summary, ta_totals) -> dict:
    """لایۀ تجمعیِ بازار: شمارشِ مثبت/منفی و ارزشِ معاملات، درِ نزدیک‌ترین تیک.

    سه چیز اینجا می‌سنجد نه یکی: «ارزشِ معاملات» با «ارزشِ بازار» قاطی نشود
    (بندِ ۲-الف)؛ شمارشِ کلی ازِ یکِ snapshot باشد نه جمعِ دو زمانِ متفاوت؛ و
    skewِ ساعتِ مرجع (سریِ ۶۰ثانیه‌ایِ TA) گزارش شود، نه پنهان.
    """
    if not bt_rows:
        # جمعیتِ خالی = سنجشِ انجام‌نشده. بی‌این، یکِ timeoutِ ساده رویِ
        # `/api/market` همه‌چیز را «MISMATCH با صفر» نشان می‌داد — خطایِ
        # ابزار، نه خطایِ برنامه.
        return {"verdict": "NOT_RUN", "why": "پاسخی ازِ برنامه نرسید (timeout/خطا)"}
    live = [r for r in bt_rows if r.get("is_live")]
    traded = [r for r in live if (_num(r.get("q_tot_tran")) or 0) > 0]
    bt = {
        "traded_symbols": len(traded),
        "plus": sum(1 for r in traded if (_num(r.get("percent_change")) or 0) > 0),
        "minus": sum(1 for r in traded if (_num(r.get("percent_change")) or 0) < 0),
        "equal": sum(1 for r in traded if (_num(r.get("percent_change")) or 0) == 0),
        "volume_shares": round(sum(_num(r.get("q_tot_tran")) or 0 for r in traded), 0),
        "value_rial": round(sum(_num(r.get("q_tot_cap")) or 0 for r in traded), 0),
        "tick": None,
    }
    if isinstance(bt_summary, dict) and bt_summary.get("ok"):
        d = (bt_summary.get("data") or {}).get("asof") or {}
        bt["tick"] = d.get("h_even")
        rows = ((bt_summary.get("data") or {}).get("rows") or [])
        allrow = next((x for x in rows if x.get("key") == "all"), {})
        bt["mstat_all_row"] = {"symbols": allrow.get("symbols"), "traded": allrow.get("traded"),
                               "value_b_toman": allrow.get("value_b_toman"),
                               "volume_b_shares": allrow.get("volume_b_shares")}
    ta = {}
    if isinstance(ta_totals, dict) and ta_totals.get("ok"):
        t = ta_totals.get("data") or {}
        times = t.get("time") or []
        if times:
            import datetime as _dt
            def _ep2h(e):
                # ساعتِ مرجع: `time[]`ِ TradersArena دیوانگیِ ظریفی دارد — اگر
                # باِ منطقۀِ محلیِ همین ماشین (تهران) خوانده شود، اولین خانۀ
                # سریِ امروز ۱۲:۳۵ می‌شود، یعنی بعدِ بسته‌شدنِ بازار. باِ UTC
                # همان خانۀ اول ۰۹:۰۵ می‌شود = آغازِ نشست. پس مرجع، ساعتِ
                # تهران را درِ قالبِ epochِ UTC می‌فرستد؛ همان‌طور می‌خوانیم.
                return int(_dt.datetime.fromtimestamp(
                    e, tz=_dt.timezone.utc).strftime("%H%M%S"))
            near = min(range(len(times)), key=lambda i: abs(_ep2h(times[i]) - (bt["tick"] or 0)))
            ta = {"n_points": len(times), "picked_epoch": times[near],
                  "picked_hEven": _ep2h(times[near]), "bors_tick": bt["tick"],
                  "skew_ticks": _ep2h(times[near]) - (bt["tick"] or 0)}
            for k in ("plus", "minus", "equal", "mval", "bq", "sq", "green", "red",
                      "close", "lower", "transfer", "stockTransfer"):
                arr = t.get(k)
                if isinstance(arr, list) and len(arr) == len(times):
                    ta[k] = arr[near]
        else:
            ta = {"verdict": "NOT_RUN", "why": "سریِ time ندارد"}
    else:
        ta = {"verdict": "BLOCKED"}
    out = {"bors": bt, "tradersarena": ta, "rows": []}
    # شمارشِ مرجع با شمارشِ ما رویِ یکِ جامعۀ یکسان نیست: مجموعِ plus+minusِ
    # مرجع تقریباً نصفِ نمادهایِ معامله‌شدهٔ ماست ⇒ دو «تعریف» را مقایسه کرده‌ایم،
    # نه دو «عددِ اشتباه». تا وقتی جامعۀِ خودِ شمارنده ثابت نشود حکم NOT_COMPARABLE
    # است (بندِ ۶: برایِ بالا بردنِ درصد، موردی حذف نمی‌شود — فقط حکم درست می‌خورد).
    ta_total = (ta.get("plus") or 0) + (ta.get("minus") or 0)
    bt_total = bt.get("plus", 0) + bt.get("minus", 0)
    pop_gap = (abs(ta_total - bt_total) / bt_total) if bt_total else None
    for k in ("plus", "minus", "equal"):
        a, b = bt.get(k), ta.get(k)
        if not isinstance(a, int) or not isinstance(b, (int, float)):
            out["rows"].append({"metric": k, "verdict": "NOT_COMPARABLE", "bors": a, "ta": b})
            continue
        d = a - int(b)
        out["rows"].append({"metric": k, "bors": a, "ta": int(b), "delta": d,
                            "verdict": ("MATCH" if d == 0 else
                                        ("NOT_COMPARABLE" if (pop_gap or 0) > 0.05 else
                                         ("STALE" if abs(d) <= 12 else "MISMATCH"))),
                            "pop_gap_pct": (round(100 * pop_gap, 2) if pop_gap is not None else None),
                            "why": ("" if d == 0 else
                                    ("جامعۀ شمارندهٔ مرجع با جامعۀ ما یکی نیست "
                                     "(مرجع %d، برنامه %d)" % (ta_total, bt_total)
                                     if (pop_gap or 0) > 0.05 else
                                     "تیکِ مرجع با تیکِ برنامه یکی نیست"))})
    if isinstance(ta.get("mval"), (int, float)) and bt.get("value_rial"):
        rel = (bt["value_rial"] - ta["mval"]) / ta["mval"]
        out["rows"].append({"metric": "traded_value", "bors_rial": bt["value_rial"],
                            "ta_raw": ta["mval"], "rel_pct": round(100 * rel, 3),
                            "verdict": "NOT_COMPARABLE",
                            "why": "واحدِ mvalِ مرجع (تومان/ریال/میلیارد) اثبات نشده ⇒ "
                                   "نسبتِ عددی ثبت می‌شود، حکمِ تطبیق نه"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bt", default="http://127.0.0.1:8101")
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit", "live_parity"))
    ap.add_argument("--no-ta", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    ts = dt.datetime.now()
    stamp = ts.strftime("%Y%m%d-%H%M%S")

    t = fetch_tsetmc()
    b = fetch_bt(args.bt)
    a = {"skipped": True} if args.no_ta else fetch_ta()

    ts_rows = t.get("rows") or []
    bt_rows = ((b["market"].get("data") or {}).get("data") or []) if b["market"].get("ok") else []
    ta_rows = ((a.get("symbols") or {}).get("data") or []) if not args.no_ta else []
    if isinstance(ta_rows, dict):
        ta_rows = ta_rows.get("data") or []

    uni = compare_universe(ts_rows, bt_rows, ta_rows)
    keys = uni["_keys"]
    bt_by_key = uni.pop("_bt_by_key")
    ts_by_key = uni.pop("_ts_by_key")
    mapping = compare_fields(bt_by_key, ts_by_key, keys)
    same = same_tick_keys(bt_by_key, ts_by_key, keys)
    # نگاشت هم باید رویِ همین زیرمجموعه سنجیده شود: بی‌این، خانۀ «آخرین» که درِ
    # پنجاه ثانیه سه بار عوض می‌شود زیرِ سقفِ ۹۸٪ می‌ماند و NOT_VERIFIED
    # می‌خورد — یعنی ابزارِ من خودش را قرمز می‌کرد، نه برنامه را.
    mapping = compare_fields(bt_by_key, ts_by_key, same)
    mism = field_mismatches(bt_by_key, ts_by_key, same, mapping)
    mism["population"] = {"joined": len(keys), "same_tick": len(same),
                          "excluded_as_stale": len(keys) - len(same)}
    ta_by_key = {str(r[0]): {"insCode": str(r[0]), "isin": str(r[1]) if len(r) > 1 else "",
                             "symbol": r[2] if len(r) > 2 else "", "nums": r[3:]}
                 for r in ta_rows if isinstance(r, list) and r and r[0]}
    tap = ta_probe({k: v for k, v in ((_key_of(r, "ins_code"), r) for r in bt_rows)},
                   ts_by_key, ta_by_key, keys)
    # کفِ نویز: خودِ TSETMC بینِ دو خوانشِ چندثانیه‌ای عوض می‌شود. بی‌این،
    # هر اختلافِ ناشیِ تأخیرِ انتشار «باگِ محاسبه» گزارش می‌شد (بندِ ۱ مأموریت).
    t2 = fetch_tsetmc()
    ts2 = {str(r.get("insCode")): r for r in (t2.get("rows") or []) if r.get("insCode")}
    noise = {}
    for fld, info in mapping.items():
        c = info.get("best")
        if not c:
            continue
        same = diff = 0
        for k in keys:
            if k not in ts2:
                continue
            x = _num(ts_by_key[k].get(c))
            y = _num(ts2[k].get(c))
            if x is None or y is None:
                continue
            if x == y:
                same += 1
            else:
                diff += 1
        n = same + diff
        noise[fld] = {"column": c, "compared": n,
                      "source_churn_rate": round(diff / n, 4) if n else None}
    agg = aggregates(b["market"], ts_rows, a)
    lvl = market_level(bt_rows, b.get("mstat_summary"), a.get("totals0") or {})
    lat = latency_probe(args.bt)

    report = {"stamp": stamp, "observed_at": ts.isoformat(timespec="seconds"),
              "sources": {"tsetmc": {k: v for k, v in t.items() if k != "rows"},
                          "bors": {k: {kk: vv for kk, vv in v.items() if kk != "data"}
                                   for k, v in b.items()},
                          "tradersarena": {k: {kk: vv for kk, vv in (v or {}).items() if kk != "data"}
                                           for k, v in (a or {}).items() if isinstance(v, dict)}},
              "universe": uni, "field_mapping": mapping, "field_diffs": mism,
              "tradersarena_columns": tap, "source_noise_floor": noise,
              "second_fetch": {"ok": t2.get("ok"), "at": t2.get("fetched_at"),
                               "rows": len(ts2)},
              "market_level": lvl, "latency": lat, "aggregates": agg}
    jpath = os.path.join(args.out, f"snapshot-{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(jpath)
    print(json.dumps({"universe": uni["counts"], "joined": uni["joined_tsetmc_bors"],
                      "only_tsetmc": uni["only_tsetmc"], "only_bors": uni["only_bors"],
                      "total_field_diffs": mism["total_diffs"]}, ensure_ascii=False))
    print("  سطحِ بازار:", json.dumps([{"m": r["metric"], "v": r["verdict"],
          "b": r.get("bors"), "t": r.get("ta"), "d": r.get("delta")} for r in lvl["rows"]],
          ensure_ascii=False))
    print("  tick:", lvl["tradersarena"].get("picked_hEven"), "vs", lvl["bors"].get("tick"))
    print("  تأخیر:", json.dumps(lat, ensure_ascii=False))
    print("  same-tick:", mism["population"]["same_tick"], "/",
          mism["population"]["joined"])
    print("  TA joined:", tap.get("compared_symbols"),
          "| ستون‌هایِ شناسایی‌شده:", {k: v["matches"] for k, v in (tap.get("columns") or {}).items()
                                     if v.get("matches")})
    for fld, info in mapping.items():
        nz = (noise.get(fld) or {}).get("source_churn_rate")
        print("  %-16s best=%-12s agree=%-7s churn=%-7s %s"
              % (fld, info["best"], info["best_rate"], nz, info["verdict"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
