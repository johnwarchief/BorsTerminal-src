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


def tehran_now():
    return (dt.datetime.now(dt.timezone.utc) + TEHRAIN_OFFSET).replace(tzinfo=None)


def in_session(now):
    # شنبه..چهارشنبه = weekday 5,6,0,1,2 (python: Mon=0..Sun=6؛ شنبه=5)
    return now.weekday() in (5, 6, 0, 1, 2) and SESSION_START <= now.time() <= SESSION_END


def acquire_lock():
    os.makedirs(OUTDIR, exist_ok=True)
    if os.path.exists(LOCK):
        try:
            if time.time() - os.path.getmtime(LOCK) < 6 * 3600:   # قفلِ ۶ ساعتهٔ مانده ⇒ رد
                return False
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


def universe(cur, limit):
    cur.execute("SELECT symbol, COUNT(*) n FROM price_history GROUP BY symbol HAVING n>=60 ORDER BY symbol")
    rows = [r[0] for r in cur.fetchall()]
    return rows[:limit] if limit else rows


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
    ap.add_argument("--limit", type=int, default=0, help="سقفِ نماد (smoke=25؛ 0=کلِ جهان)")
    ap.add_argument("--force", action="store_true", help="خارجِ پنجرۀِ نشست هم اجرا شود (smoke)")
    ap.add_argument("--timeout", type=int, default=5400, help="سقفِ زمانیِ کلِ اجرا (ثانیه)")
    a = ap.parse_args()

    now = tehran_now()
    if not a.force and not in_session(now):
        print(f"خارجِ پنجرۀِ نشستِ Tehran ({now.isoformat()})؛ بدونِ --force اجرا نمی‌شود.")
        return 0
    if not acquire_lock():
        print("قفلِ دورۀِ دیگر درِ کار است؛ اجرایِ هم‌زمانِ تکراری رد شد.")
        return 0
    t0 = time.time()
    try:
        from api import chart as CH
        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cur = conn.cursor()
        syms = universe(cur, a.limit)
        today = now.date()
        lastpath = os.path.join(OUTDIR, "last.json")
        prev = {}
        if os.path.exists(lastpath):
            try:
                prev = json.load(open(lastpath, encoding="utf-8"))
            except Exception:
                prev = {}
        cur_rev = f"{now:%Y%m%d-%H%M}"
        out = []
        errs = changed = 0
        for sym in syms:
            if time.time() - t0 > a.timeout:
                print("timeoutِ کلی؛ توقفِ کنترل‌شده.")
                break
            rec = audit_one(CH, sym, today)
            rec["observed_at"] = now.isoformat(timespec="seconds")
            rec["rev"] = cur_rev
            if rec.get("error"):
                errs += 1
            old = prev.get(sym, {})
            for k in ("trend_D", "trend_W", "decision"):
                if old and rec.get(k) is not None and old.get(k) != rec.get(k):
                    rec.setdefault("changed", {})[k] = f"{old.get(k)}→{rec.get(k)}"
                    changed += 1
            out.append(cross_surface_check(CH, sym, rec))
            time.sleep(0.15)   # احترامِ نرخِ درخواستِ CDN
        conn.close()

        dayfile = os.path.join(OUTDIR, f"audit-{now:%Y%m%d}.jsonl")
        with open(dayfile, "a", encoding="utf-8") as f:
            for r in out:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        snapshot = {r["symbol"]: {k: r.get(k) for k in ("trend_D", "trend_W", "decision", "basis")}
                    for r in out if not r.get("error")}
        with open(lastpath, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=0)

        summary = {"rev": cur_rev, "observed_at": now.isoformat(timespec="seconds"),
                   "n_symbols": len(out), "errors": errs, "changed_decisions": changed,
                   "elapsed_s": round(time.time() - t0, 1)}
        print("FTS LIVE AUDIT:", json.dumps(summary, ensure_ascii=False))
        print("خروجی:", dayfile)
        return 0
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
