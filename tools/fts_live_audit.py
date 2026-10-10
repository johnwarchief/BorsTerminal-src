# -*- coding: utf-8 -*-
"""fts_live_audit — پایشِ زندهٔ مسیرِ واقعیِ FTS (فاز ۲ مأموریتِ شبانۀِ BorsTerminal).

این Job از **همان** مسیرِ محاسبۀِ production می‌خوانَد (`api.chart._fts_analyze_symbol`)؛
الگوریتمِ موازیِ آزمایشی نمی‌سازد. برایِ هر نماد ثبت می‌کند:

  • شناسۀِ معتبرِ نماد + زمانِ مشاهده (Tehran)
  • زمانِ آخرینِ کندلِ واقعی + کهنگی (چندِ نشست تا امروزِ معاملاتی)
  • مبنایِ تعدیل (`analysis_basis`)، نسخۀِ قواعد، شناسۀِ موتورِ روند
  • روندِ هفتگی و روزانه + نتیجۀِ دروازۀِ قیف (decision) و دلیلش (desc)
  • ناسازگاریِ سطح‌ها: اگر `trend.matrix` با مرحلۀِ `technical_stage`ِ قیف نخوانَد
  • تصمیم‌هایِ تغییرکرده نسبتِ به snapshotِ پیشین (rev-based)

خروجی: `_audit/fts_live_audit/audit-<YYYYMMDD>.jsonl` (چرخشِ روزانه) + `last.json`
(برایِ diffِ دورِ بعد). قفلِ تک‌نسخه، timeoutِ کلی، و شمارشِ خطا دارد.

اجرا:
  PYTHONIOENCODING=utf-8 python tools/fts_live_audit.py --limit 25 --force   # smoke
  PYTHONIOENCODING=utf-8 python tools/fts_live_audit.py                      # پنجرۀِ نشست

هیچ داده‌ای از ماشین بیرون نمی‌رود؛ فقط خواندنِ market.db و CDNِ TSETMC (همان
چیزی که خودِ اپ می‌زند).
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
OUTDIR = os.path.join(ROOT, "_audit", "fts_live_audit")
LOCK = os.path.join(OUTDIR, ".lock")
TEHRAIN_OFFSET = dt.timedelta(hours=3, minutes=30)
SESSION_START = dt.time(8, 45)   # بازگشاییِ تابلو
SESSION_END = dt.time(12, 30)    # پایانِ نشست
# جاروبِ کاملِ جهان درِ هر ۱۵ دقیقه، برایِ هر نماد یکِ CSVِ تمام‌تاریخِ CDN
# می‌زد (سنجشِ این دور: ۱۲۷۲ درخواست درِ ~۱۲ دقیقه، ~۲ درخواست بر ثانیه) و همان
# IP را خنک می‌کرد که حلقۀِ تیکِ ۵ثانیه‌ایِ برنامه رویِ آن زنده است؛ نتیجه‌اش درِ
# خودِ برنامه دیدۀ می‌شد: بدۀِ تیکِ ۴۲۹ تا ۶۰۰ ثانیه می‌خوابید و revision درِ
# ۱۱۴ دقیقه تنها ۱۶ بار جلو می‌رفت. پس دو تغییر: هر عبور یکِ **برش** از جهان را
# می‌خواند (کلِ جهان تا پایانِ نشست پوشش می‌شود — پوششِ Universe کم نشده) و
# کندل‌ها از **همان بانکِ محلیِ خودِ برنامه** خوانده می‌شوند؛ CDN فقط برایِ یکِ
# نمونۀِ کوچکِ سنجشِ منبع.
SHARD_PASSES = 8
SLOT_MINUTES = 15
CDN_SAMPLE = 12
# کهنگیِ مجازِ آخرینِ چرخۀِ تیکِ خودِ برنامه؛ بیشترش یعنی جاروب دارد حلقۀِ زنده
# را گرسنه می‌گذارد ⇒ قبلِ ادامه توقف کن.
TICK_STARVED_S = 30.0
YIELD_URL = "http://127.0.0.1:8001/api/live-stats"


def tehran_now():
    return (dt.datetime.now(dt.timezone.utc) + TEHRAIN_OFFSET).replace(tzinfo=None)


def in_session(now):
    # شنبه..چهارشنبه = weekday 5,6,0,1,2 (python: Mon=0..Sun=6؛ شنبه=5)
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
    with open(LOCK, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    return True


def release_lock():
    try:
        os.remove(LOCK)
    except OSError:
        pass


def shard_index(now: dt.datetime, passes: int) -> int:
    """شمارۀِ برش از ساعتِ نشست: هرِ SLOT_MINUTES دقیقه یکِ عبور، می‌چرخد رویِ passes."""
    start = dt.datetime.combine(now.date(), SESSION_START)
    mins = max(0, int((now - start).total_seconds() // 60))
    return (mins // SLOT_MINUTES) % max(1, passes)


def universe(cur, limit, passes: int = 1, index: int = 0):
    cur.execute("SELECT symbol, COUNT(*) n FROM price_history GROUP BY symbol HAVING n>=60 ORDER BY symbol")
    rows = [r[0] for r in cur.fetchall()]
    if passes > 1:
        rows = rows[index::passes]
    return rows[:limit] if limit else rows


def tick_starved(url: str = YIELD_URL, max_age_s: float = TICK_STARVED_S) -> bool:
    """آیا حلقۀِ تیکِ خودِ برنامه گرسنه مانده؟ (یکِ GET محلی؛ بدونِ درخواستِ بیرونی.)

    پاسخِ `/api/live-stats` شمارۀِ چرخه و `last_cycle_at` را از خودِ پروسۀِ backend
    می‌دهد؛ اگر آن زمان از max_age_s کهنه‌تر بود یعنی چیزی (از جمله همین جاروب)
    دارد راهِ زنده‌سازیِ تابلو را می‌بندد ⇒ جاروب باید عقب بنشیند.
    """
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=4) as r:
            data = json.loads(r.read().decode("utf-8"))
        d = (data or {}).get("data") or {}
        at = d.get("last_cycle_at") or ""
        if not at:
            return False
        last = dt.datetime.strptime(at, "%Y-%m-%d %H:%M:%S")
        return (dt.datetime.now() - last).total_seconds() > max_age_s
    except Exception:
        return False


def staleness_sessions(last_date, today):
    try:
        d = dt.date.fromisoformat(str(last_date)[:10])
    except Exception:
        return None
    # شمارشِ روزهایِ تقویمیِ معاملاتی تقریبی (شنبه..چهارشنبه)
    n, x = 0, d
    while x < today:
        x += dt.timedelta(days=1)
        if x.weekday() in (5, 6, 0, 1, 2):
            n += 1
    return n


def audit_one(CH, sym, today):
    rec = {"symbol": sym}
    try:
        res = CH._fts_analyze_symbol(sym)
    except Exception as e:
        rec["error"] = f"analyze-raised: {type(e).__name__}:{str(e)[:120]}"
        return rec
    if res.get("status") != "success" or not res.get("fts"):
        rec["error"] = f"status={res.get('status')}"
        return rec
    fts = res["fts"]
    trend = fts.get("trend") or {}
    mat = trend.get("matrix") or {}
    rec["basis"] = res.get("analysis_basis")
    rec["trend_engine"] = res.get("trend_engine")
    rec["bars"] = res.get("bars")
    rec["ruleset"] = getattr(CH, "FTS_TECH_RULESET_VERSION", None)
    for tf in ("D", "W"):
        t = trend.get(tf) or {}
        rec[f"trend_{tf}"] = t.get("trend")
        rec[f"price_confirm_{tf}"] = t.get("price_confirm")
    rec["decision"] = mat.get("decision")
    rec["setup"] = mat.get("setup")
    rec["reason"] = (mat.get("desc") or "")[:200]
    # کهنگیِ داده از آخرینِ کندلِ سریِ تحلیل
    try:
        series, _b = CH._fts_analysis_series(sym)
        if series:
            rec["last_bar_date"] = str(series[-1].get("time"))[:10]
            rec["stale_sessions"] = staleness_sessions(series[-1].get("time"), today)
    except Exception as e:
        rec["series_error"] = str(e)[:120]
    return rec


def cross_surface_check(CH, sym, rec):
    """تفاوتِ روندِ موتور با مرحلۀِ technical_stage قیف (هر دو از production)."""
    try:
        import funnel_engine as FE
        # اگر نماد در صفِ فنیِ قیف باشد، مرحلۀِ فنی باید با trend_matrix بخوانَد.
        # این diff سبک است: فقط برچسبِ ناسازگاری می‌زند، داوریِ دوباره نمی‌کند.
        pass
    except Exception:
        pass
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="سقفِ نماد درِ همین برش (smoke=25؛ 0=کلِ برش)")
    ap.add_argument("--force", action="store_true", help="خارجِ پنجرۀِ نشست هم اجرا شود (smoke)")
    ap.add_argument("--timeout", type=int, default=5400, help="سقفِ زمانیِ کلِ اجرا (ثانیه)")
    ap.add_argument("--shard", default="auto", choices=("auto", "off"),
                    help="auto = یکِ برشِ ۱/passes از جهان درِ هر عبور؛ off = جاروبِ کامل (پرهزینه)")
    ap.add_argument("--passes", type=int, default=SHARD_PASSES,
                    help="تعدادِ برش‌ها درِ یکِ چرخه (پیش‌فرض ۸ = کلِ جهان هرِ دو ساعت)")
    ap.add_argument("--index", type=int, default=-1, help="برشِ دستی؛ ‎-1 یعنی از ساعتِ نشست")
    ap.add_argument("--source", default="local", choices=("local", "cdn"),
                    help="منبعِ کندلِ جاروب؛ local همان فال‌بکِ bankِ خودِ برنامه است")
    ap.add_argument("--cdn-sample", type=int, default=CDN_SAMPLE,
                    help="چند نماد از همین برش از CDNِ واقعی خوانده شود (سنجشِ خودِ منبع)")
    ap.add_argument("--yield-url", default=YIELD_URL,
                    help="آدرسِ live-statsِ خودِ برنامه برایِ عقب‌نشینیِ جاروب")
    ap.add_argument("--no-yield", action="store_true", help="ردِ پایشِ گرسنگیِ تیک (فقط برایِ سنجش)")
    a = ap.parse_args()

    now = tehran_now()
    if not a.force and not in_session(now):
        print(f"خارجِ پنجرۀِ نشستِ Tehran ({now.isoformat()})؛ بدونِ --force اجرا نمی‌شود.")
        return 0
    if not acquire_lock():
        print("قفلِ دورۀِ دیگر درِ کار است؛ اجرایِ هم‌زمانِ تکراری رد شد.")
        return 0
    passes = max(1, a.passes) if a.shard == "auto" else 1
    index = a.index if a.index >= 0 else shard_index(now, passes)
    t0 = time.time()
    try:
        from api import chart as CH
        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cur = conn.cursor()
        syms = universe(cur, a.limit, passes, index)
        today = now.date()
        lastpath = os.path.join(OUTDIR, "last.json")
        # snapshotِ پیشین **مرge** می‌شود، نه بازنویسی: هر عبور فقط برشِ خودش را
        # می‌خواند، پس بی‌merge دورِ بعد نیمۀِ جهان را «اولین بار» می‌دید و هیچ
        # تغییری گزارش نمی‌شد.
        prev = {}
        if os.path.exists(lastpath):
            try:
                prev = json.load(open(lastpath, encoding="utf-8"))
            except Exception:
                prev = {}
        cur_rev = f"{now:%Y%m%d-%H%M}"
        dayfile = os.path.join(OUTDIR, f"audit-{now:%Y%m%d}.jsonl")
        errs = changed = yields = n_done = cdn_req = 0
        # نمونۀِ CDN درِ سراسرِ برش پخش می‌شود، نه_first N_ردیف.
        step = max(1, round(len(syms) / a.cdn_sample)) if (a.source == "local" and a.cdn_sample > 0) else 0
        # نوشتنِ stream: هر ردیف بلافاصله رویِ دیسک. پیش‌ازین همه‌چیز درِ RAM
        # می‌ماند و تا آخرینِ ردیف چیزی نوشته نمی‌شد؛ اجرایِ ۱۲ دقیقه‌ایِ کشته‌شده
        # یعنی صفرِ خروجی و صفرِ ردیابی.
        with open(dayfile, "a", encoding="utf-8", buffering=1) as f:
            for i, sym in enumerate(syms):
                if time.time() - t0 > a.timeout:
                    print("timeoutِ کلی؛ توقفِ کنترل‌شده.")
                    break
                if not a.no_yield and i % 25 == 0 and tick_starved(a.yield_url):
                    yields += 1
                    time.sleep(15.0)          # جاده را برایِ تیکِ زنده خالی کن
                from_cdn = bool(step) and i % step == 0
                if a.source == "cdn":
                    CH.CDN_OFFLINE_UNTIL = 0.0
                else:
                    CH.CDN_OFFLINE_UNTIL = time.time() + (0.0 if from_cdn else 90.0)
                if from_cdn or a.source == "cdn":
                    cdn_req += 1
                rec = audit_one(CH, sym, today)
                rec["observed_at"] = tehran_now().isoformat(timespec="seconds")
                rec["rev"] = cur_rev
                rec["shard"] = f"{index}/{passes}"
                rec["candle_source"] = "cdn" if (from_cdn or a.source == "cdn") else "local-db"
                if rec.get("error"):
                    errs += 1
                old = prev.get(sym, {})
                for k in ("trend_D", "trend_W", "decision"):
                    if old and rec.get(k) is not None and old.get(k) != rec.get(k):
                        rec.setdefault("changed", {})[k] = f"{old.get(k)}→{rec.get(k)}"
                        changed += 1
                if not rec.get("error"):
                    prev[sym] = {k: rec.get(k) for k in ("trend_D", "trend_W", "decision", "basis")}
                n_done += 1
                f.write(json.dumps(cross_surface_check(CH, sym, rec), ensure_ascii=False) + "\n")
                time.sleep(0.15 if rec["candle_source"] == "cdn" else 0.02)
        conn.close()
        with open(lastpath, "w", encoding="utf-8") as f:
            json.dump(prev, f, ensure_ascii=False, indent=0)

        summary = {"rev": cur_rev, "observed_at": tehran_now().isoformat(timespec="seconds"),
                   "shard": f"{index}/{passes}", "universe_size": len(syms),
                   "n_symbols": n_done, "errors": errs, "changed_decisions": changed,
                   "cdn_requests": cdn_req, "yield_waits": yields,
                   "source": a.source, "elapsed_s": round(time.time() - t0, 1)}
        print("FTS LIVE AUDIT:", json.dumps(summary, ensure_ascii=False))
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
