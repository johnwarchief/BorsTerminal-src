# -*- coding: utf-8 -*-
"""market_tape_live_audit — پایشِ زندۀِ تابلوخوانی و وضعیتِ بازار (فاز ۳).

از همان مسیرِ production می‌خوانَد: `api.market._board_sql` + `tape_flags.apply_tape_flags`
(هیچ فیلترِ تازه یا شرطِ ساختگی اضافه نمی‌کند). پنج فیلترِ واقعیِ تابلو که ثبت
می‌شوند: f_jet (جت)، f_roobi (روبی/قدرتِ خرید)، f_noqteh (نقصِ تعهد)، f_smart
(پولِ هوشمند)، f_legal (حقوقی‌به‌حقیقی) — به‌علاوهٔ f_clock/f_suspِ کمکی.

برایِ هر نماد ثبت می‌شود: قیمت/حجم/ارزش، حجمِ واقعیِ دو طرف، زمانِ دریافتِ feed
(`meta.last_sync`) و کهنگی، و مقادیرِ فیلترها. سپس برایِ نمادهایِ محدودِ نمونه،
`GetInstrumentInfo`ِ خودِ TSETMC گرفته می‌شود و اختلافِ عددیِ خام ثبت می‌شود
(سقف/کفِ مجاز، میانگینِ تعدادِ معاملۀِ پنجِ نشست، شمارۀِ نشست).

دامنۀِ صادقانۀِ این Job: مقایسه با **TSETMC**. TradersArena اینجا هرگز گرفته
نمی‌شود (منبعِ جدا، نشستِ جدا) ⇒ درِ گزارشِ تطبیق `UNAVAILABLE` می‌ماند، نه این‌که
جایش عددِ TSETMC گذاشته شود. تفکیکِ نوعِ خطا (source/stale/mapping/unit/formula/
display) کارِ تحلیلِ پس ازِ جمع‌آوری است، نه حدسِ همین Tool.

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
# ستون‌هایی که مستقیم با ارقامِ رسمیِ TSETMC سنجیده می‌شوند (سقف/کفِ مجازِ قیمت درِ
# هر گروه، میانگینِ حجم، وضعیتِ نماد). پیش‌ازین درِ خروجیِ Job نبودند، پس هیچ
# اختلافی قابلِ نسبت‌دادن نبود.
LIMIT_FIELDS = ["h2_max", "h5_max", "h9_max", "h19_max", "h29_max", "h39_max",
                "h49_max", "h59_max", "month_avg_vol", "prior30_vol",
                "st_code", "st_title", "stop_state", "stop_reason"]


def tehran_now():
    return (dt.datetime.now(dt.timezone.utc) + TEHRAIN_OFFSET).replace(tzinfo=None)


def in_session(now):
    return now.weekday() in (5, 6, 0, 1, 2) and SESSION_START <= now.time() <= SESSION_END


def _pid_alive(pid) -> bool:
    """آیا این PID هنوز زنده است؟ (قفلِ بی‌صاحب نباید جاروب را شش ساعت بخواباند.)"""
    try:
        pid = int(str(pid).strip())
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259                        # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def acquire_lock():
    os.makedirs(OUTDIR, exist_ok=True)
    if os.path.exists(LOCK):
        try:
            with open(LOCK, encoding="utf-8") as f:
                holder = f.read().strip()
        except OSError:
            return False
        if _pid_alive(holder):
            return False
        try:
            os.remove(LOCK)
        except OSError:
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


def tsetmc_instrument_info(ins_code):
    """اطلاعاتِ رسمیِ نماد از TSETMC، برایِ تطبیقِ مقدارِ خودمان.

    دو نکته که پیش‌ازین این مقایسه را همیشه `UNAVAILABLE` می‌کرد:
      • قالبِ آدرس: `GetInstrumentInfo` شناسۀِ عددیِ نماد را درِ **مسیر** می‌خواهد
        (`…/GetInstrumentInfo/<insCode>`)؛ قالبِ پرسش‌واری (`?a=`) که قبلاً زده
        می‌شد برایِ هر دوازده نماد ۴۰۴ می‌داد، پس مقایسه هیچ‌وقت اجرا نشده بود.
      • فیلدهایِ lastValue/vol/val درِ این پاسخ نیست؛ آنچه هست سقف/کفِ مجازِ
        قیمت، میانگینِ تعدادِ معاملۀِ پنجِ نشست، شمارۀِ نشست، نظارت و بازار است
        — و دقیقاً همین‌ها با ستون‌هایِ خودمان (h*_max، month_avg_vol، d_even،
        st_code، board) سنجیده می‌شوند.
    هر خطا ⇒ `UNAVAILABLE`؛ عددِ جایگزین ساخته نمی‌شود.
    """
    try:
        import requests
        if not ins_code:
            return {"tsetmc": "UNAVAILABLE", "err": "no-ins-code"}
        r = requests.get(f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/{ins_code}",
                         timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return {"tsetmc": "UNAVAILABLE", "http": r.status_code}
        ii = (r.json() or {}).get("instrumentInfo") or {}
        if not ii:
            return {"tsetmc": "UNAVAILABLE", "err": "empty-instrumentInfo"}
        st = ii.get("staticThreshold") or {}
        return {
            "tsetmc_d_even": ii.get("dEven"),
            "tsetmc_static_max": st.get("psGelStaMax"),
            "tsetmc_static_min": st.get("psGelStaMin"),
            "tsetmc_q_tot_tran_5j_avg": ii.get("qTotTran5JAvg"),
            "tsetmc_z_titad": ii.get("zTitad"),
            "tsetmc_under_supervision": ii.get("underSupervision"),
            "tsetmc_flow_title": ii.get("flowTitle"),
            "tsetmc_l_val18": ii.get("lVal18"),
            "tsetmc_c_isin": ii.get("cIsin"),
        }
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
        rows, base, payload = fetch_board()
        if not rows:
            print("UNAVAILABLE: هیچ backendِ زنده‌ای رویِ 8001/8000/8002 پاسخ نداد؛ "
                  "تابلو بازسازی نمی‌شود (بدونِ دادهٔ ساختگی).")
            return 2
        # `d_even`/`last_sync` درِ `meta`ِ خودِ پاسخ‌اند (api/market.py:709-722)، نه
        # درِ کلیدِ `feed`؛ پیش‌ازین از آنجا خوانده می‌شد و همیشه None می‌شد، پس
        # «زمانِ تابلو» درِ لاگ هرگز نوشته نمی‌شد.
        meta = (payload or {}).get("meta") or {} if isinstance(payload, dict) else {}
        d_even = meta.get("d_even")
        h_even = meta.get("h_even")
        last_sync = meta.get("last_sync")
        rev = (payload or {}).get("rev") if isinstance(payload, dict) else None
        if a.limit:
            rows = rows[:a.limit]
        symkeys = ("symbol", "l_val18", "ins_code", "isin")
        step = max(1, round(len(rows) / a.compare)) if a.compare > 0 else 0
        compared = 0
        dayfile = os.path.join(OUTDIR, f"audit-{now:%Y%m%d}.jsonl")
        # stream + flush: اجرایِ طولانی باید از بیرون قابلِ دید باشد؛ اگر کشته
        # شود، آنچه نوشته شده از دست نمی‌رود.
        with open(dayfile, "a", encoding="utf-8", buffering=1) as f:
            for i, r in enumerate(rows):
                if time.time() - t0 > a.timeout:
                    print("timeoutِ کلی؛ توقف.")
                    break
                sym = next((r[k] for k in symkeys if r.get(k) is not None), None)
                rec = {"symbol": sym, "observed_at": tehran_now().isoformat(timespec="seconds"),
                       "source": base, "rev": rev, "board_d_even": _j(d_even),
                       "board_h_even": _j(h_even), "board_last_sync": _j(last_sync)}
                for c in FIELDS:
                    if c in r:
                        rec[c] = _j(r.get(c))
                for c in FILTERS:
                    if c in r:
                        rec[c] = _j(r.get(c))
                for c in LIMIT_FIELDS:
                    if c in r:
                        rec[c] = _j(r.get(c))
                if step and i % step == 0 and compared < a.compare:
                    compared += 1
                    ours = {"h19_max": rec.get("h19_max"), "h29_max": rec.get("h29_max"),
                            "h39_max": rec.get("h39_max"), "h49_max": rec.get("h49_max"),
                            "h59_max": rec.get("h59_max"), "h9_max": rec.get("h9_max"),
                            "h5_max": rec.get("h5_max"), "h2_max": rec.get("h2_max"),
                            "month_avg_vol": rec.get("month_avg_vol"),
                            "z_tot_tran": rec.get("z_tot_tran")}
                    them = tsetmc_instrument_info(r.get("ins_code"))
                    rec["tsetmc"] = them
                    rec["ours_for_compare"] = ours
                    # اختلافِ عددی، همان‌جا و بدونِ تفسیر: تحلیلِ «کدام خانۀِ خطا»
                    # کارِ مالک/گزارش است، نه حدسِ این Tool.
                    if them.get("tsetmc_static_max") is not None:
                        rec["delta_static_max_minus_h19"] = round(
                            float(them["tsetmc_static_max"]) - float(rec.get("h19_max") or 0), 4)
                        rec["delta_static_min_plus_h19"] = round(
                            float(rec.get("h19_max") or 0) - float(them.get("tsetmc_static_min") or 0), 4)
                    if them.get("tsetmc_d_even") is not None and d_even is not None:
                        rec["delta_d_even"] = int(them["tsetmc_d_even"]) - int(d_even)
                    if them.get("tsetmc_q_tot_tran_5j_avg") is not None:
                        rec["delta_5j_avg_minus_month_avg"] = round(
                            float(them["tsetmc_q_tot_tran_5j_avg"])
                            - float(rec.get("month_avg_vol") or 0), 2)
                    time.sleep(0.2)      # احترامِ نرخِ درخواستِ بیرونی
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        have_f = [c for c in FILTERS if c in (rows[0] if rows else {})]
        nflag = sum(1 for r in rows for c in have_f if r.get(c))
        summary = {"observed_at": tehran_now().isoformat(timespec="seconds"), "source": base,
                   "rev": rev, "n_rows": len(rows), "filters": have_f, "flag_hits": nflag,
                   "board_d_even": _j(d_even), "board_h_even": _j(h_even),
                   "compared": compared, "elapsed_s": round(time.time() - t0, 1)}
        print("TAPE LIVE AUDIT:", json.dumps(summary, ensure_ascii=False))
        print("خروجی:", dayfile)
        return 0
    finally:
        release_lock()


if __name__ == "__main__":
    import audit_runlog as AUD
    _runlog = AUD.attach(OUTDIR)
    try:
        _code = main()
    except BaseException:            # traceback درِ run.log؛ کدِ شکستِ واقعی بماند
        import traceback
        traceback.print_exc()
        _code = 1
    AUD.mark_end(_runlog, _code)
    sys.exit(_code)
