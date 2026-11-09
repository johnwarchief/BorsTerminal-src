#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_history_api.py — S4: سنجشِ زندهٔ تاریخچهٔ backfill‌شده از APIِ Go.

سه اندازه‌گیریِ جدا:
  ۱) خامِ موجود (پیش از backfill): ردیف‌هایِ `price_history` که از مرجع نیستند؛
     هندسه/حجم/close در برابرِ `type0` مرجع. مبنایِ close (last/closing) و
     openِ «قیمتِ پایه» (برابرِ closeِ روزِ قبل) جدا شمرده می‌شود.
  ۲) خامِ backfill‌شده: ردیف‌هایِ `src=rahavard365`؛ این‌ها از همان مرجع نوشته
     شده‌اند، پس «انطباقِ مشتق از منبع» است، نه پاریتیِ مستقل.
  ۳) تعدیل‌شده: OHLCِ خام × ضریبِ زنجیرهٔ محلی در برابرِ `type7` مرجع. زنجیرهٔ
     این ۳۰ نماد از بستهٔ تصحیحِ `rahavard-reference-correction` می‌آید که خودش
     از یک snapshotِ مرجع ساخته شده است؛ پس این سنجش «سازگاری» است، نه مرجعِ
     مستقل. نسخه/هشِ بسته و هشِ مرجع در خروجی ثبت می‌شوند.

هیچ نوشتنی در بانک ندارد؛ فقط GET. توکن از فایل خوانده می‌شود و چاپ نمی‌شود.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import json
import math
import os
import pathlib
import sqlite3
import statistics
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "phase48"))
sys.path.insert(0, ROOT)
import backfill_reference as BF  # noqa: E402

try:
    import wm_calendar as WMC  # noqa: E402
except Exception:  # pragma: no cover - calendar pack optional in this tool
    WMC = None


def d10(v):
    return str(v)[:10]


def round_pos(v):
    if v >= 0:
        return float(math.floor(v + 0.5))
    return float(v)


def week_key(date_str):
    d = dt.date.fromisoformat(d10(date_str))
    return (d - dt.timedelta(days=(d.weekday() + 2) % 7)).isoformat()


def month_key(date_str):
    d = dt.date.fromisoformat(d10(date_str))
    if WMC is not None:
        jy, jm, _ = WMC.g2j(d.year, d.month, d.day)
        return f"{jy:04d}-{jm:02d}"
    return d.strftime("%Y-%m")


def load_pack_rows(path):
    out = collections.defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            sym = r.get("symbol")
            if sym and r.get("effective_date") and r.get("ratio") is not None:
                out[sym].append((str(r["effective_date"])[:10], float(r["ratio"])))
    return out


def ref_steps(ref_raw_sym, ref_adj_sym):
    """گام‌هایِ ضریبِ مرجع: ratio بینِ دو تاریخِ متوالی (فقط تغییرِ >۰٫۲٪)."""
    dates = sorted(set(ref_raw_sym) & set(ref_adj_sym))
    out, prev = [], None
    for d in dates:
        rc = float(ref_raw_sym[d]["close"])
        ac = float(ref_adj_sym[d]["close"])
        if rc <= 0 or ac <= 0:
            continue
        f = ac / rc
        if prev and abs(f / prev[1] - 1.0) > 0.002:
            out.append((d, prev[1] / f))
        prev = (d, f)
    return out


def _near_steps(ref, candidates):
    hit = 0
    for rd, rr in ref:
        if not rr:
            continue
        try:
            rdate = dt.date.fromisoformat(d10(rd))
        except ValueError:
            continue
        for cd, cr in candidates:
            if not cr:
                continue
            try:
                cdate = dt.date.fromisoformat(d10(cd))
            except ValueError:
                continue
            if abs((rdate - cdate).days) <= 45 and abs(float(cr) / float(rr) - 1.0) <= 0.05:
                hit += 1
                break
    return hit


def load_ref(path, adjust):
    out = collections.defaultdict(dict)
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("adjust") == adjust and r.get("resolution") == "D":
                out[r["symbol"]][r["date"]] = r
    return out


def api_get(base, path, token, timeout=180):
    req = urllib.request.Request(base.rstrip("/") + path,
                                 headers={"Authorization": "Bearer " + token,
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _close(c):
    v = c.get("last")
    if v is None or float(v) == 0:
        return c.get("close")
    return v


def _bucket(src):
    return "new" if (src or "") == BF.SRC_RAHAVARD else "pre"


def _empty_raw():
    return collections.Counter({
        "common": 0, "open_mismatch": 0, "high_mismatch": 0, "low_mismatch": 0,
        "volume_mismatch": 0, "close_by_last": 0, "close_by_closing": 0,
        "close_other": 0, "last_missing": 0, "low_auction": 0,
        "ref_degenerate": 0, "open_eq_prev_close": 0})


def _empty_adj():
    return collections.Counter({
        "common": 0, "factor_bad": 0, "factor_strict_bad": 0, "factor_missing": 0,
        "ohlc_ok_closing": 0, "ohlc_ok_last": 0,
        "ohlc3_ok": 0, "ohlc4_ok": 0, "shape_ohlc3_ok": 0, "shape_ohlc4_ok": 0,
        "close_ok": 0, "open_mismatch": 0, "high_mismatch": 0, "low_mismatch": 0,
        "close_mismatch": 0, "close_by_last": 0, "close_by_closing": 0,
        "close_other": 0, "last_missing": 0, "factor_ratio_constant": 0})


def compare_symbol(sym, payload, ref_raw, ref_adj):
    candles = [c for c in (payload.get("candles") or [])
               if not c.get("live_forming") and c.get("time")]
    candles.sort(key=lambda c: d10(c["time"]))
    api = {d10(c["time"]): c for c in candles}
    factors = {d10(f["time"]): float(f["factor"])
               for f in (payload.get("factors") or []) if f.get("time")}
    src_counts = collections.Counter((c.get("src") or "legacy-unknown")
                                     for c in candles)
    out = {
        "symbol": sym, "api_count": len(candles),
        "api_first": d10(candles[0]["time"]) if candles else None,
        "api_last": d10(candles[-1]["time"]) if candles else None,
        "dbRows": payload.get("dbRows"), "dbNoTradeRows": payload.get("dbNoTradeRows"),
        "dbInvalidRows": payload.get("dbInvalidRows"),
        "liveInjected": bool(payload.get("liveInjected")),
        "src": dict(src_counts), "raw": {}, "adj": {}, "shift": {},
        "capability": {}, "wm": {},
    }
    raw = {"pre": _empty_raw(), "new": _empty_raw()}
    ref_dates = sorted(ref_raw)
    ref_idx = {d: i for i, d in enumerate(ref_dates)}
    for d in ref_dates:
        rr = ref_raw[d]
        c = api.get(d)
        if c is None:
            raw.setdefault("ref_missing", collections.Counter())["ref_missing"] += 1
            if not BF.valid_ref_row(rr)[0]:
                raw["ref_missing"]["ref_invalid"] += 1
            continue
        b = _bucket(c.get("src"))
        st = raw[b]
        st["common"] += 1
        o = float(c["open"])
        hi = float(c.get("high_raw") if c.get("high_raw") is not None else c["high"])
        lo = float(c.get("low_raw") if c.get("low_raw") is not None else c["low"])
        cl = float(c["close"])
        vol = float(c.get("volume") or 0)
        last = c.get("last")
        if float(o) != float(rr["open"]):
            st["open_mismatch"] += 1
            i = ref_idx[d]
            if i > 0:
                prev_close = float(ref_raw[ref_dates[i - 1]]["close"])
                if float(o) == prev_close:
                    st["open_eq_prev_close"] += 1
        if hi != float(rr["high"]):
            st["high_mismatch"] += 1
        if lo != float(rr["low"]):
            st["low_mismatch"] += 1
        if vol != float(rr["volume"]):
            st["volume_mismatch"] += 1
        if last is None:
            st["last_missing"] += 1
        rc = float(rr["close"])
        if last is not None and float(last) == rc:
            st["close_by_last"] += 1
        elif cl == rc:
            st["close_by_closing"] += 1
        else:
            st["close_other"] += 1
        if last is not None and lo != float(rr["low"]) and lo == float(last):
            st["low_auction"] += 1
        if float(rr["open"]) == float(rr["high"]) == float(rr["low"]) == float(rr["close"]):
            st["ref_degenerate"] += 1
    raw.setdefault("ref_missing", collections.Counter())
    raw["api_only"] = len(set(api) - set(ref_raw))
    raw["ref_missing"]["ref_total"] = len(ref_raw)
    out["raw"] = {k: (dict(v) if isinstance(v, collections.Counter) else v)
                  for k, v in raw.items()}

    # جابه‌جاییِ روز: ردیفِ محلیِ موجود، عیناً همان ردیفِ مرجعِ روزِ بعد/قبل است.
    def tuple_of(c):
        return (float(c["open"]),
                float(c.get("high_raw") if c.get("high_raw") is not None else c["high"]),
                float(c.get("low_raw") if c.get("low_raw") is not None else c["low"]),
                float(c.get("volume") or 0), float(_close(c)))
    ref_tuple = {d: (float(r["open"]), float(r["high"]), float(r["low"]),
                     float(r["volume"]), float(r["close"])) for d, r in ref_raw.items()}
    shift = {"next": 0, "prev": 0, "examples": []}
    for d, c in api.items():
        if _bucket(c.get("src")) != "pre" or d not in ref_idx:
            continue
        i = ref_idx[d]
        t = tuple_of(c)
        if i + 1 < len(ref_dates) and t == ref_tuple[ref_dates[i + 1]]:
            shift["next"] += 1
            if len(shift["examples"]) < 6:
                shift["examples"].append({"symbol": sym, "local": d,
                                          "ref": ref_dates[i + 1], "dir": "next"})
        elif i > 0 and t == ref_tuple[ref_dates[i - 1]]:
            shift["prev"] += 1
            if len(shift["examples"]) < 6:
                shift["examples"].append({"symbol": sym, "local": d,
                                          "ref": ref_dates[i - 1], "dir": "prev"})
    out["shift"] = shift

    adj = {"pre": _empty_adj(), "new": _empty_adj()}
    factor_max = {"pre": 0.0, "new": 0.0}
    recs = {"pre": [], "new": []}
    for d, ar in ref_adj.items():
        c = api.get(d)
        rr = ref_raw.get(d)
        if c is None or rr is None:
            continue
        b = _bucket(c.get("src"))
        k = factors.get(d)
        if k is None:
            adj[b]["factor_missing"] += 1
            continue
        rc = float(rr["close"])
        ac = float(ar["close"])
        ref_f = (ac / rc) if (rc > 0 and ac > 0) else None
        recs[b].append((d, c, ar, k, ref_f))
    for b, rows in recs.items():
        st = adj[b]
        ratios = [k / rf for (_d, _c, _a, k, rf) in rows if rf and rf > 0]
        med = statistics.median(ratios) if ratios else 1.0
        variation = (max(ratios) / min(ratios) - 1.0) if ratios and min(ratios) > 0 else None
        st["factor_ratio_median"] = med
        st["factor_ratio_min"] = min(ratios) if ratios else None
        st["factor_ratio_max"] = max(ratios) if ratios else None
        st["factor_ratio_variation"] = variation
        if variation is not None and variation <= 0.002 and len(ratios) >= 5:
            st["factor_ratio_constant"] = 1
        for (_d, c, ar, k, ref_f) in rows:
            st["common"] += 1
            if ref_f:
                rel = abs(k / ref_f - 1.0)
                factor_max[b] = max(factor_max[b], rel)
                if rel > 0.001:
                    st["factor_bad"] += 1
                if rel > 1e-6:
                    st["factor_strict_bad"] += 1
            o_raw = float(c["open"])
            hi_raw = float(c.get("high_raw") if c.get("high_raw") is not None else c["high"])
            lo_raw = float(c.get("low_raw") if c.get("low_raw") is not None else c["low"])
            cl_raw = float(c["close"])
            last = c.get("last")
            o = round_pos(o_raw * k)
            hi = round_pos(hi_raw * k)
            lo = round_pos(lo_raw * k)
            cl = round_pos(cl_raw * k)
            alast = round_pos(float(last) * k) if last is not None else None
            ao, ah, al, ac = (float(ar["open"]), float(ar["high"]),
                              float(ar["low"]), float(ar["close"]))
            if abs(o - ao) > 0.5:
                st["open_mismatch"] += 1
            if abs(hi - ah) > 0.5:
                st["high_mismatch"] += 1
            if abs(lo - al) > 0.5:
                st["low_mismatch"] += 1
            if abs(cl - ac) > 0.5:
                st["close_mismatch"] += 1
            if o == ao and hi == ah and lo == al and cl == ac:
                st["ohlc_ok_closing"] += 1
            if abs(o - ao) <= 0.5 and abs(hi - ah) <= 0.5 and abs(lo - al) <= 0.5:
                st["ohlc3_ok"] += 1
                if abs(cl - ac) <= 0.5:
                    st["ohlc4_ok"] += 1
            if last is None:
                st["last_missing"] += 1
            elif o == ao and hi == ah and lo == al and alast == ac:
                st["ohlc_ok_last"] += 1
            kk = (k / med) if med else k
            so, shi = round_pos(o_raw * kk), round_pos(hi_raw * kk)
            slo, scl = round_pos(lo_raw * kk), round_pos(cl_raw * kk)
            if abs(so - ao) <= 0.5 and abs(shi - ah) <= 0.5 and abs(slo - al) <= 0.5:
                st["shape_ohlc3_ok"] += 1
                if abs(scl - ac) <= 0.5:
                    st["shape_ohlc4_ok"] += 1
            if last is not None and abs(round_pos(float(last) * kk) - ac) <= 0.5:
                st["shape_close_ok"] += 1
            if alast is not None and abs(alast - ac) <= 0.5:
                st["close_by_last"] += 1
            elif abs(cl - ac) <= 0.5:
                st["close_by_closing"] += 1
            else:
                st["close_other"] += 1
            if alast is not None and abs(alast - ac) <= 0.5:
                st["close_ok"] += 1
            elif last is None and abs(cl - ac) <= 0.5:
                st["close_ok"] += 1
    out["adj"] = {k: dict(v) for k, v in adj.items()}
    out["adj"]["factor_max_rel"] = factor_max

    cap = payload.get("adjustCapability") or {}
    av = cap.get("availability") or {}
    cov = cap.get("coverage") or {}
    corr = cap.get("corrections") or {}
    out["capability"] = {
        "functional_status": cap.get("functional_status"),
        "functional_available": cap.get("functional_available"),
        "combined_available": cap.get("combined_available"),
        "availability_status": av.get("status"),
        "window_start": av.get("window_start"), "window_end": av.get("window_end"),
        "window_available": av.get("window_available"),
        "coverage_start": cov.get("coverage_start"),
        "coverage_end": cov.get("coverage_end"),
        "pre_coverage_candles": cov.get("pre_coverage_candles"),
        "chain_complete": cap.get("chain_complete"),
        "event_count": cap.get("event_count"),
        "correction_covered": corr.get("covered"),
        "correction_mode": corr.get("mode"),
        "correction_version": corr.get("version"),
        "correction_ref_sha256": corr.get("reference_sha256"),
        "adjust_source": payload.get("adjustSource"),
    }

    dates = sorted(api)
    months = {month_key(d) for d in dates}
    weeks = {week_key(d) for d in dates}
    out["wm"] = {"days": len(dates), "weeks": len(weeks), "months": len(months),
                 "first_month": min(months) if months else None,
                 "last_month": max(months) if months else None}
    return out


def chain_audit(db_path, pack_rows, sym, ref_raw_sym, ref_adj_sym):
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db_path)).as_uri() + "?mode=ro",
                          uri=True)
    try:
        product = [tuple(r) for r in con.execute(
            "SELECT date, ratio FROM adjust_events WHERE symbol=? AND ratio>0",
            (sym,))]
        ins = con.execute("SELECT ins_code FROM instruments WHERE l_val18=? "
                          "ORDER BY updated_at DESC LIMIT 1", (sym,)).fetchone()
        official = 0
        if ins and ins[0]:
            official = con.execute(
                "SELECT (SELECT COUNT(*) FROM price_adjust_events WHERE ins_code=?) + "
                "(SELECT COUNT(*) FROM share_change_events WHERE ins_code=?)",
                (ins[0], ins[0])).fetchone()[0]
    finally:
        con.close()
    ref = ref_steps(ref_raw_sym, ref_adj_sym)
    pack = pack_rows.get(sym, [])
    return {
        "product_events": len(product),
        "pack_steps": len(pack),
        "ref_steps": len(ref),
        "product_matches_ref": _near_steps(ref, product),
        "pack_matches_ref": _near_steps(ref, pack),
        "official_rows": official,
    }


def aggregate(per_symbol):
    tot = {"raw_pre": _empty_raw(), "raw_new": _empty_raw(),
           "adj_pre": _empty_adj(), "adj_new": _empty_adj(),
           "shift_next": 0, "shift_prev": 0, "api_only": 0,
           "ref_missing": 0, "ref_invalid_missing": 0}
    for s in per_symbol:
        for bucket in ("pre", "new"):
            for k, v in s["raw"][bucket].items():
                if isinstance(v, int):
                    tot["raw_" + bucket][k] += v
            for k, v in s["adj"][bucket].items():
                if isinstance(v, int):
                    tot["adj_" + bucket][k] += v
        tot["shift_next"] += s["shift"]["next"]
        tot["shift_prev"] += s["shift"]["prev"]
        tot["api_only"] += s["raw"].get("api_only", 0)
        tot["ref_missing"] += s["raw"]["ref_missing"].get("ref_missing", 0)
        tot["ref_invalid_missing"] += s["raw"]["ref_missing"].get("ref_invalid", 0)
    return {k: (dict(v) if isinstance(v, collections.Counter) else v)
            for k, v in tot.items()}


def write_json(obj, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def write_markdown(rep, path):
    t = rep["totals"]
    rp, rn = t["raw_pre"], t["raw_new"]
    ap, an = t["adj_pre"], t["adj_new"]
    lines = [
        "# سنجشِ زندهٔ تاریخچهٔ backfill‌شده",
        "",
        f"- API: `{rep['api']}` — نمادها: {len(rep['per_symbol'])}",
        f"- مرجع: `{rep['ref_path']}` — sha256: `{rep['ref_sha256']}`",
        f"- خامِ موجود (پیش از backfill): {rp.get('common',0)} روزِ مشترک؛ "
        f"open نابرابر {rp.get('open_mismatch',0)} (از این‌ها open=closeِ روزِ قبل: "
        f"{rp.get('open_eq_prev_close',0)})؛ high {rp.get('high_mismatch',0)}؛ "
        f"low {rp.get('low_mismatch',0)}؛ حجم {rp.get('volume_mismatch',0)}",
        f"- close: last {rp.get('close_by_last',0)} / closing {rp.get('close_by_closing',0)} / "
        f"دیگر {rp.get('close_other',0)}؛ last غایب {rp.get('last_missing',0)}؛ "
        f"low=حراج {rp.get('low_auction',0)}",
        f"- خامِ backfill‌شده: {rn.get('common',0)} روز (مشتق از همان مرجع؛ "
        f"نابرابری‌ها: open {rn.get('open_mismatch',0)}، high {rn.get('high_mismatch',0)}، "
        f"low {rn.get('low_mismatch',0)}، حجم {rn.get('volume_mismatch',0)})",
        f"- تعدیل‌شدهٔ موجود: {ap.get('common',0)} روز؛ O/H/L (تحمل ۰٫۵) "
        f"{ap.get('ohlc3_ok',0)}؛ O/H/L/C {ap.get('ohlc4_ok',0)}؛ شکل پس از حذفِ "
        f"لنگر {ap.get('shape_ohlc3_ok',0)}؛ close {ap.get('close_ok',0)}؛ "
        f"factor_bad {ap.get('factor_bad',0)} (strict "
        f"{ap.get('factor_strict_bad',0)}؛ بیشینهٔ انحراف "
        f"{rep['factor_max_rel']['pre']:.6g})",
        f"- تعدیل‌شدهٔ backfill: {an.get('common',0)} روز؛ O/H/L (تحمل ۰٫۵) "
        f"{an.get('ohlc3_ok',0)}؛ O/H/L/C {an.get('ohlc4_ok',0)}؛ شکل پس از حذفِ "
        f"لنگر {an.get('shape_ohlc3_ok',0)}؛ close {an.get('close_ok',0)}؛ "
        f"factor_bad {an.get('factor_bad',0)} (strict "
        f"{an.get('factor_strict_bad',0)}؛ بیشینه "
        f"{rep['factor_max_rel']['new']:.6g})",
        f"- لنگرهایِ ثابتِ ضریب (ratio≠۱ با تغییرِ ≤۰٫۲٪): "
        f"{len(rep.get('constant_offsets') or [])} نماد/بازه",
        f"- جابه‌جاییِ روز (احتمالی): بعد {t['shift_next']}، قبل {t['shift_prev']}؛ "
        f"مرجعِ غایب از API {t['ref_missing']} (نامعتبر {t['ref_invalid_missing']})",
        "",
        "> تعدیل‌شده «سازگاری» است نه مرجعِ مستقل: زنجیرهٔ این نمادها از بستهٔ "
        "`rahavard-reference-correction` می‌آید که از snapshotِ مرجع ساخته شده است.",
        "",
        "## نمادها",
        "",
        "| نماد | API | اولین | آخرین | خامِ موجود | open بد | open=close قبل | "
        "close=closing | close دیگر | تعدیل موجود O/H/L | شکل | تعدیل backfill O/H/L | "
        "شکل | factor بد | ratio | var | وضعیت |",
        "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for s in rep["per_symbol"]:
        r = s["raw"]["pre"]
        ap = s["adj"]["pre"]
        an = s["adj"]["new"]
        lines.append(
            f"| {s['symbol']} | {s['api_count']} | {s['api_first']} | {s['api_last']} | "
            f"{r.get('common',0)} | {r.get('open_mismatch',0)} | "
            f"{r.get('open_eq_prev_close',0)} | {r.get('close_by_closing',0)} | "
            f"{r.get('close_other',0)} | {ap.get('ohlc3_ok',0)}/{ap.get('common',0)} | "
            f"{ap.get('shape_ohlc3_ok',0)}/{ap.get('common',0)} | "
            f"{an.get('ohlc3_ok',0)}/{an.get('common',0)} | "
            f"{an.get('shape_ohlc3_ok',0)}/{an.get('common',0)} | "
            f"{ap.get('factor_bad',0)+an.get('factor_bad',0)} | "
            f"{(ap.get('factor_ratio_median') or 1.0):.4f}/"
            f"{(an.get('factor_ratio_median') or 1.0):.4f} | "
            f"{(ap.get('factor_ratio_variation') or 0.0):.3%}/"
            f"{(an.get('factor_ratio_variation') or 0.0):.3%} | "
            f"{s['capability'].get('functional_status')} |")
    if rep.get("chain_totals"):
        c = rep["chain_totals"]
        lines += ["", "## زنجیرهٔ تعدیل (ریشهٔ اختلافِ پیش از ۲۰۲۴)", "",
                  "| قلم | تعداد |", "| --- | ---: |",
                  f"| گام‌هایِ مرجع | {c['ref_steps']} |",
                  f"| ردیف‌هایِ محصول (adjust_events) | {c['product_events']} |",
                  f"| گام‌هایِ پکِ تصحیح | {c['pack_steps']} |",
                  f"| گام‌هایِ مرجع که محصول پوشش می‌دهد | {c['product_matches_ref']} |",
                  f"| گام‌هایِ مرجع که پک پوشش می‌دهد | {c['pack_matches_ref']} |",
                  f"| ردیف‌هایِ دفترِ رسمی | {c['official_rows']} |", "",
                  "حالتِ authoritative همهٔ ردیف‌هایِ محصول را کنار می‌گذارد و فقط "
                  "گام‌هایِ پک (تصحیح‌ها) را نگه می‌دارد؛ اگر پک زنجیرهٔ کامل نباشد، "
                  "گام‌هایِ درستِ محصول هم حذف می‌شوند."]
    if rep.get("acceptance"):
        a = rep["acceptance"]
        lines += ["", "## پذیرش (نماد نمونه)", "",
                  f"- `{a['symbol']}`: کندل {a['chart_count']} از {a['chart_first']} تا "
                  f"{a['chart_last']}",
                  f"- MA: {a['ma_bars']} میله؛ اولین ma5 غیرتهی "
                  f"{a['ma5_first']}؛ آخرین {a['ma5_last']}"]
    lines += ["", "## بازیابی‌ناپذیر / محدودیت‌ها", ""]
    for item in rep.get("unrecoverable", []):
        lines.append(f"- {item}")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="S4: سنجشِ APIِ تاریخچهٔ backfill‌شده")
    ap.add_argument("--api", default="http://127.0.0.1:8157")
    ap.add_argument("--token-file", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", default="")
    ap.add_argument("--acceptance-symbol", default="فولاد")
    ap.add_argument("--ma-days", type=int, default=2000)
    ap.add_argument("--db", default="", help="optional market.db for the chain audit")
    ap.add_argument("--pack", default="", help="optional factors.jsonl for the chain audit")
    args = ap.parse_args(argv)
    token = open(args.token_file, encoding="ascii").read().strip()
    symbols = BF.load_symbols(args.symbols)
    ref_raw = load_ref(args.ref, "raw")
    ref_adj = load_ref(args.ref, "adjusted")
    pack_rows = load_pack_rows(args.pack) if args.pack else {}
    per_symbol = []
    for i, sym in enumerate(symbols, 1):
        payload = api_get(args.api, "/api/chart-db/" + urllib.parse.quote(sym, safe=""),
                          token)
        entry = compare_symbol(sym, payload, ref_raw.get(sym, {}),
                               ref_adj.get(sym, {}))
        if args.db:
            entry["chain"] = chain_audit(args.db, pack_rows, sym,
                                         ref_raw.get(sym, {}), ref_adj.get(sym, {}))
        per_symbol.append(entry)
        print(f"[{i}/{len(symbols)}] {sym}", flush=True)
    totals = aggregate(per_symbol)
    factor_max = {"pre": 0.0, "new": 0.0}
    for s in per_symbol:
        for b in ("pre", "new"):
            factor_max[b] = max(factor_max[b], s["adj"]["factor_max_rel"][b])
    acceptance = None
    acc_payload = next((s for s in per_symbol if s["symbol"] == args.acceptance_symbol),
                       None)
    if acc_payload:
        ma = api_get(args.api, "/api/ma/" + urllib.parse.quote(args.acceptance_symbol,
                                                               safe="") +
                     f"?days={args.ma_days}", token)
        ma5 = (ma.get("ma") or {}).get("ma5") or []
        first = next((x for x in ma5 if x and x[1] is not None), None)
        acceptance = {
            "symbol": args.acceptance_symbol, "chart_count": acc_payload["api_count"],
            "chart_first": acc_payload["api_first"], "chart_last": acc_payload["api_last"],
            "ma_bars": ma.get("bars"), "ma_status": ma.get("status"),
            "ma5_first": first, "ma5_last": ma5[-1] if ma5 else None,
        }
    constant_offsets = []
    for s in per_symbol:
        for b in ("pre", "new"):
            a = s["adj"][b]
            if a.get("factor_ratio_constant") and a.get("common", 0) >= 5:
                med = a.get("factor_ratio_median") or 1.0
                if abs(med - 1.0) > 0.002:
                    constant_offsets.append({
                        "symbol": s["symbol"], "bucket": b, "ratio": med,
                        "variation": a.get("factor_ratio_variation"),
                        "common": a["common"]})
    capability_status = collections.Counter(
        s["capability"].get("functional_status") for s in per_symbol)
    corrections = sorted({(s["capability"].get("correction_version"),
                           s["capability"].get("correction_ref_sha256"))
                          for s in per_symbol if s["capability"].get("correction_covered")})
    unrecoverable = [
        "نمادهای بیرون از ۳۰ نماد: مرجعِ ۲۰۱۰–۲۰۲۴ در مخزن نیست؛ پوششِ پیش از ۲۰۲۴ "
        "برایِ آن‌ها بازیابی نشد.",
        "سریِ تعدیل‌شدهٔ پیش از ۲۰۲۴ مستقل از مرجع نیست: زنجیرهٔ این نمادها از بستهٔ "
        "rahavard-reference-correction می‌آید؛ سنجشِ تعدیل، سازگاری است نه شاهدِ مستقل.",
        "ردیف‌هایِ ۲۱گانهٔ مرجع با هندسهٔ ناسازگار (high<close یا مشابه) نوشته نشدند و "
        "در گزارشِ backfill به‌عنوانِ invalid ثبت شده‌اند.",
        "close محلی در ردیف‌هایِ legacy همان «قیمتِ پایانیِ حراج» است و مرجع فقط "
        "«آخرین معامله» را دارد؛ برایِ ردیف‌هایِ بی last، اختلافِ close قابلِ داوری "
        "با این مرجع نیست (INSUFFICIENT_DATA).",
    ]
    rep = {
        "api": args.api, "ref_path": os.path.abspath(args.ref),
        "ref_sha256": BF.sha256_file(args.ref),
        "symbols": len(symbols), "per_symbol": per_symbol,
        "totals": totals, "factor_max_rel": factor_max,
        "capability_status": dict(capability_status), "corrections": corrections,
        "chain_totals": ({k: sum(s["chain"].get(k, 0) for s in per_symbol
                                 if "chain" in s)
                          for k in ("product_events", "pack_steps", "ref_steps",
                                    "product_matches_ref", "pack_matches_ref",
                                    "official_rows")} if args.db else None),
        "constant_offsets": constant_offsets,
        "acceptance": acceptance, "unrecoverable": unrecoverable,
    }
    write_json(rep, args.out)
    if args.md:
        write_markdown(rep, args.md)
    print(json.dumps({"symbols": len(symbols), "api_first": min(
        (s["api_first"] for s in per_symbol if s["api_first"]), default=None),
        "api_last": max((s["api_last"] for s in per_symbol if s["api_last"]),
                        default=None),
        "raw_pre": {k: totals["raw_pre"].get(k, 0) for k in
                    ("common", "open_mismatch", "high_mismatch", "low_mismatch",
                     "volume_mismatch", "close_by_last", "close_by_closing",
                     "close_other", "last_missing", "low_auction")},
        "raw_new": {k: totals["raw_new"].get(k, 0) for k in
                    ("common", "open_mismatch", "high_mismatch", "low_mismatch",
                     "volume_mismatch")},
        "adj_pre": {k: totals["adj_pre"].get(k, 0) for k in
                    ("common", "ohlc3_ok", "ohlc4_ok", "shape_ohlc3_ok",
                     "close_ok", "factor_bad", "factor_strict_bad")},
        "adj_new": {k: totals["adj_new"].get(k, 0) for k in
                    ("common", "ohlc3_ok", "ohlc4_ok", "shape_ohlc3_ok",
                     "close_ok", "factor_bad", "factor_strict_bad")},
        "shifts": [totals["shift_next"], totals["shift_prev"]],
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
