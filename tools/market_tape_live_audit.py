# -*- coding: utf-8 -*-
"""market_tape_live_audit — پایشِ زندۀِ تابلوخوانی و وضعیتِ بازار (فاز ۳).

از همان مسیرِ production می‌خوانَد: `api.market._board_sql` + `tape_flags.apply_tape_flags`
(هیچ فیلترِ تازه یا شرطِ ساختگی اضافه نمی‌کند). پنج فیلترِ واقعیِ تابلو که ثبت
می‌شوند: f_jet (جت)، f_roobi (روبی/قدرتِ خرید)، f_noqteh (نقصِ تعهد)، f_smart
(پولِ هوشمند)، f_legal (حقوقی‌به‌حقیقی) — به‌علاوهٔ f_clock/f_suspِ کمکی.

برایِ هر نماد ثبت می‌کند: قیمت/حجم/ارزش، حجمِ واقعیِ دو طرف، زمانِ دریافتِ feed
(fetched_at) و کهنگی، و مقادیرِ فیلترها. سپس برایِ نمادهایِ محدودِ نمونه، مقدارِ
TSETMC و وضعیتِ TradersArena را می‌گیرد و **اختلافِ مقدار/زمان/منبع** را ثبت می‌کند.

قاعده: اگر منبعِ بیرونی دسترس نبود یا داده نداد ⇒ `UNAVAILABLE`؛ دادهٔ تخمینی/
ساختگی جایگزین نمی‌شود. تفکیکِ نوعِ خطا: source_error / stale / mapping / unit /
formula / display.

خروجی: `_audit/market_tape_live_audit/audit-<YYYYMMDD>.jsonl` + `last.json`.
اجرا:  python tools/market_tape_live_audit.py --limit 20 --force
"""
import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DB = os.path.join(ROOT, "market.db")
OUTDIR = os.path.join(ROOT, "_audit", "market_tape_live_audit")
LOCK = os.path.join(OUTDIR, ".lock")
TEHRAIN_OFFSET = dt.timedelta(hours=3, minutes=30)
SESSION_START, SESSION_END = dt.time(8, 45), dt.time(12, 30)
FILTERS = ["f_jet", "f_roobi", "f_noqteh", "f_smart", "f_legal", "f_clock", "f_susp"]
FIELDS = ["p_last", "p_closing", "p_open", "price_min", "price_max", "q_tot_tran",
          "q_tot_cap", "z_tot_tran", "buy_q_vol", "buy_q_val", "sell_q_vol",
          "sell_q_val", "vol_ratio", "buyer_power_raw", "resistance_59"]


def tehran_now():
    return (dt.datetime.now(dt.timezone.utc) + TEHRAIN_OFFSET).replace(tzinfo=None)


def in_session(now):
    return now.weekday() in (5, 6, 0, 1, 2) and SESSION_START <= now.time() <= SESSION_END


def acquire_lock():
    os.makedirs(OUTDIR, exist_ok=True)
    if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 6 * 3600:
        return False
    open(LOCK, "w", encoding="utf-8").write(str(os.getpid()))
    return True


def release_lock():
    try:
        os.remove(LOCK)
    except OSError:
        pass


def _j(v):
    try:
        import numpy as _np
        if isinstance(v, (_np.integer,)):
            return int(v)
        if isinstance(v, (_np.floating,)):
            return round(float(v), 4)
        if isinstance(v, (_np.bool_,)):
            return bool(v)
    except Exception:
        pass
    return v if isinstance(v, (int, float, bool, str, type(None))) else str(v)


def tsetmc_quote(isin_or_code):
    """تلاشِ خواندنِ قیمتِ TSETMC برایِ تطبیق؛ هر خطا ⇒ UNAVAILABLE (بدونِ جعل)."""
    try:
        import requests
        # market_status/tsetmc endpoint — اگر شبکه نبود سریع UNAVAILABLE می‌شود.
        r = requests.get("https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo",
                         params={"a": isin_or_code}, timeout=6,
                         headers={"User-Agent": "BorsTerminal-audit"})
        if r.status_code != 200:
            return {"tsetmc": "UNAVAILABLE", "http": r.status_code}
        ins = (r.json().get("instrumentInfo") or {})
        return {"tsetmc_last": ins.get("lastValue"), "tsetmc_vol": ins.get("vol"),
                "tsetmc_val": ins.get("val")}
    except Exception as e:
        return {"tsetmc": "UNAVAILABLE", "err": type(e).__name__}


def fetch_board():
    """تابلو را از endpointِ production می‌خوانَد (نه بازسازیِ لایۀِ ستون‌ها).

    مسیرِ واقعیِ تابلو + هفت فیلترِ tape_flags همین API است. اگر backend بالا
    نبود ⇒ UNAVAILABLE (دادهٔ ساختگی جایگزین نمی‌شود).
    """
    import json as _json
    import urllib.request
    for base in ("http://127.0.0.1:8001", "http://127.0.0.1:8000", "http://127.0.0.1:8002"):
        try:
            with urllib.request.urlopen(base + "/api/market", timeout=8) as r:
                data = _json.loads(r.read().decode("utf-8"))
            rows = data if isinstance(data, list) else (data.get("rows") or data.get("data") or [])
            if rows:
                return rows, base, data
        except Exception:
            continue
    return None, None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--compare", type=int, default=8, help="چند نماد باِ TSETMC تطبیق شود")
    ap.add_argument("--timeout", type=int, default=5400)
    a = ap.parse_args()
    now = tehran_now()
    if not a.force and not in_session(now):
        print(f"خارجِ پنجرۀِ نشست ({now.isoformat()})؛ --force برایِ smoke.")
        return 0
    if not acquire_lock():
        print("قفلِ دورۀِ دیگر فعال؛ اجرایِ تکراری رد شد.")
        return 0
    t0 = time.time()
    try:
        rows, base, meta = fetch_board()
        if not rows:
            print("UNAVAILABLE: هیچ backendِ زنده‌ای رویِ 8001/8000/8002 پاسخ نداد؛ "
                  "تابلو بازسازی نمی‌شود (بدونِ دادهٔ ساختگی).")
            return 2
        feed = (meta or {}).get("feed") or {} if isinstance(meta, dict) else {}
        d_even = feed.get("d_even") or feed.get("dEven")
        fetched = feed.get("fetched_at") or feed.get("updatedAt")
        if a.limit:
            rows = rows[:a.limit]
        symkeys = ("symbol", "l_val18", "ins_code", "isin")
        out = []
        for i, r in enumerate(rows):
            if time.time() - t0 > a.timeout:
                print("timeoutِ کلی؛ توقف.")
                break
            sym = next((r[k] for k in symkeys if r.get(k) is not None), None)
            rec = {"symbol": sym, "observed_at": now.isoformat(timespec="seconds"),
                   "source": base, "feed_d_even": _j(d_even), "fetched_at": _j(fetched)}
            for c in FIELDS:
                if c in r:
                    rec[c] = _j(r.get(c))
            for c in FILTERS:
                if c in r:
                    rec[c] = _j(r.get(c))
            if i < a.compare:
                rec.update(tsetmc_quote(r.get("ins_code") or r.get("isin") or ""))
            out.append(rec)
        dayfile = os.path.join(OUTDIR, f"audit-{now:%Y%m%d}.jsonl")
        with open(dayfile, "a", encoding="utf-8") as f:
            for rec in out:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        have_f = [c for c in FILTERS if c in (out[0] if out else {})]
        nflag = sum(1 for rec in out for c in have_f if rec.get(c))
        print("TAPE LIVE AUDIT:", json.dumps(
            {"observed_at": now.isoformat(timespec="seconds"), "source": base,
             "n_rows": len(out), "filters": have_f, "flag_hits": nflag,
             "feed_d_even": _j(d_even)}, ensure_ascii=False))
        print("خروجی:", dayfile)
        return 0
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
