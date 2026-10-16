#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/mstat_swr_v1111.py — گاردِ stale-while-revalidate و تک‌پروازگیِ پنل‌هایِ mstat.

چرا این گارد متولد شد: سنجشِ همین شب رویِ بک‌اندِ HEAD با حلقه‌هایِ دریافتِ روشن
(`_audit/perf_live/loops_on_22h_20261014-224612.jsonl`، ۲۰ نمونه، فاصلۀ ۱۰s، خارج
ازِ ساعاتِ معاملۀ ۱۴۰۵-۰۷-۲۳) نشان داد ttlِ تنها کافی نبود:

    /api/mstat/board    p50 = 18.0 ms   p95 = 2570.4 ms   max = 2970.9 ms
    /api/mstat/summary  p50 =  8.7 ms   p95 =  289.1 ms
    نمونه‌هایِ سرخورده: i=0 (22:46:12) · i=4 (22:47:09) · i=8 (22:48:04) ·
    i=12 (22:49:00) · i=16 (22:49:56) — هر ~۵۶ ثانیه یک‌بار.

یعنی هر بار که کشِ هر-حالت می‌سوخت، همان یکِ درخواستِ کاربر *ده* پنل را درون‌خطی
می‌ساخت و دو و نیم ثانیه بلاک می‌ماند. راه‌حلِ `api/_core.py` برایِ شمارشِ فرایند
(SWR + تک‌پروازگی) اینجا نبود؛ این گارد همان دو قفل را رویِ `_mstat_call` می‌زند.

چه قفلی می‌زند:
  ۱) ttl: پنج فراخوانی درِ یکِ پنجره ⇒ یکِ ساختِ واقعی.
  ۲) SWR: پس از انقضا پاسخِ کهنه فوراً می‌رود و بازسازی درِ پس‌زمینه است.
  ۳) سقفِ امانت: کهنه فقط تا `_MSTAT_STALE_MAX_S`؛ بعد از آن درون‌خطی می‌سازد
     (پاسخِ کهنه بی‌سقف نمی‌شود).
  ۴) تک‌پروازگی cold miss: هشت ترد ⇒ یکِ ساخت، نه هشت‌تا.
  ۵) جابه‌جاییِ نشانۀ بانک ⇒ کلیدِ تازه ⇒ هیچ کهنه‌ای از حالتِ پیشین سرو نمی‌شود.
  ۶) `ttl_s=0` و `refresh="inline"` ⇒ رفتارِ بی‌کشِ لحظه‌ایِ قدیم دست‌نخورده.
  ۷) خطا هرگز کش نمی‌شود و جایِ دادهٔ سالم را نمی‌گیرد.
  ۸) بدنهٔ پاسخ با مسیرِ بی‌کش یکی است (هیچ محاسبۀ موازی نساخته شده).
  ۹) بی‌نشتی: `_MSTAT_WAIT` و `_MSTAT_BG` پس از هر دور خالی می‌مانند.

چهار کنترلِ منفی (سنسور باید قرمز شود): بی‌اثرکردنِ سقفِ امانت، بی‌اثرکردنِ
تک‌پروازگی، کش‌کردنِ پاسخِ خطا، و بی‌اثرکردنِ `stale_ok=False`. بی‌شبکه، بی‌نوشتن رویِ هیچ بانکی.

اجرا:  PYTHONIOENCODING=utf-8 python dev/mstat_swr_v1111.py
خروجی: «N passed / M failed»، exit 0 یا 1
"""
from __future__ import annotations

import os
import sys
import threading
import time
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from api import market_status as ms                              # noqa: E402

CAP0 = ms._MSTAT_STALE_MAX_S   # گامِ زمانِ آزمون‌ها به این مرجعِ ثابت بند است

PASS = FAIL = 0


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("PASS %s" % what)
    else:
        FAIL += 1
        print("FAIL %s%s" % (what, ("   ← " + str(detail)) if detail else ""))
    return ok


# ── محیطِ آزمایش: نه بانک، نه شبکه، فقط شمارشِ ساخت ──────────────────────────
class _Clock:
    """ساعتِ یکنواختِ قابل‌جل‌بردن — جایِ `time.monotonic` درِ ماژولِ هدف."""
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t

    def advance(self, s):
        self.t += float(s)


class _Conn:
    def close(self):
        pass


class Probe:
    """جایِ موتورِ پنل: می‌شمارد، می‌تواند بخوابد/بیسازد/ارور بدهد.

    `tag` نامِ یکتای هر بررسی است. بی‌آن، کلیدِ کش (از `fn.__name__` ساخته
    می‌شود) میانِ بررسی‌ها یکی می‌ماند و تردِ پس‌زونۀ بررسیِ پیشین می‌تواند
    *پس ازِ* `_reset()` درِ کشِ بررسیِ تازه بنشیند — یعنی قرمزیِ نادرست.
    """

    def __init__(self, delay=0.0, value="panel", tag="x"):
        self.__name__ = "probe_" + tag
        self.calls = 0
        self.delay = delay
        self.value = value
        self.fails = False
        self.raises = False
        self.lock = threading.Lock()
        self.started = threading.Event()

    def __call__(self, conn, *args, **kw):
        self.started.set()
        if self.delay:
            time.sleep(self.delay)
        if self.raises:
            raise RuntimeError("engine exploded")
        with self.lock:
            self.calls += 1
            n = self.calls
        if self.fails:
            return {"status": "error", "message": "engine said no"}
        return {"status": "ok", "value": self.value, "gen": n}


STATE = {"marker": (20261014, 183235), "rev": 7, "static": 3, "day": "20261014"}
CLOCK = _Clock()
_REAL_TIME = ms.time


def _install():
    ms.get_db = lambda: _Conn()
    ms._mstat_marker = lambda conn: STATE["marker"]
    ms._MS = SimpleNamespace(revision=lambda: STATE["rev"],
                             static_rev=lambda: STATE["static"],
                             session_day=lambda: STATE["day"])
    ms.time = CLOCK


def _reset():
    ms._MSTAT_CACHE.clear()
    ms._MSTAT_WAIT.clear()
    ms._MSTAT_BG.clear()
    STATE["marker"] = (20261014, 183235)   # هر بررسی ازِ همان حالتِ بانک شروع کند
    STATE["rev"], STATE["static"], STATE["day"] = 7, 3, "20261014"
    CLOCK.t = 1000.0


def _settle(timeout=3.0):
    """صبر تا بازسازیِ پس‌زمینه تمام شود (ساعتِ ماژول مصنوعی است، پس تردِ واقعی
    باید با ساعتِ واقعی پایش شود)."""
    t0 = time.monotonic()
    while ms._MSTAT_BG and time.monotonic() - t0 < timeout:
        time.sleep(0.01)
    return not ms._MSTAT_BG


def _join_cache(new_ts, timeout=3.0):
    """صبر تا نشانیِ کش جلوتر برود (بازسازی تمام شد)."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        vals = [v[0] for v in ms._MSTAT_CACHE.values()]
        if any(v > new_ts for v in vals):
            return True
        time.sleep(0.01)
    return False


# ── بررسی‌ها ─────────────────────────────────────────────────────────────────
def c1_ttl():
    _reset()
    p = Probe(tag="c1")
    outs = [ms._mstat_call(p) for _ in range(5)]
    ok = p.calls == 1 and all(o["gen"] == 1 for o in outs)
    return ok, "calls=%d" % p.calls


def c2_swr_serves_stale_immediately():
    _reset()
    p = Probe(delay=0.08, tag="c2")     # تردِ پس‌زونه باید هنگامِ داوری زنده باشد
    ms._mstat_call(p)                       # gen 1
    ts0 = list(ms._MSTAT_CACHE.values())[0][0]
    CLOCK.advance(ms._MSTAT_TTL_S + 1)      # سوختۀ ttl
    out = ms._mstat_call(p)                 # باید کهنه بدهد و پس‌زمینه بسازد
    served_stale = out["gen"] == 1 and p.calls == 1 and bool(ms._MSTAT_BG)
    done = _settle() and _join_cache(ts0)
    after = ms._mstat_call(p)
    return served_stale and done and after["gen"] == 2 and p.calls == 2, \
        "stale=%s calls_at_serve=%d bg=%d settled=%s after_gen=%s" % (
            served_stale, 1, len(ms._MSTAT_BG), done, after["gen"])


def c3_stale_is_capped():
    """کهنۀ بیش‌ازحدِ سقف ⇒ همان درخواست می‌سازد، نه سروِ کهنه با بازسازیِ پس‌زمینه.

    داوری **پیش ازِ هر settle()** و با تردِ کُند: اگر سقف بی‌اثر شده باشد، فراخوان
    پاسخِ کهنه می‌دهد و تردِ پس‌زمینه شمارش را بالا می‌برد؛ اگر بی‌درنگ بسنجیم،
    آزمون‌نامه خودش را گول می‌زند (سنجشِ واقعیِ همین گارد: calls=2 expected=2).
    """
    _reset()
    p = Probe(delay=0.08, tag="c3")
    ms._mstat_call(p)
    CLOCK.advance(CAP0 + 10)                    # کهنه‌تر ازِ سقفِ امانت
    before = p.calls
    ms._mstat_call(p)
    inline_now = p.calls == before + 1 and not ms._MSTAT_BG
    _settle()
    return inline_now, "calls=%d expected=%d bg=%d" % (p.calls, before + 1, len(ms._MSTAT_BG))


def c4_single_flight_cold():
    _reset()
    p = Probe(delay=0.05, tag="c4")
    res = []
    lk = threading.Lock()

    def worker():
        o = ms._mstat_call(p)
        with lk:
            res.append(o)
    ths = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in ths]
    [t.join(timeout=5) for t in ths]
    gens = {o.get("gen") for o in res}
    return p.calls == 1 and len(res) == 8 and gens == {1}, "calls=%d gens=%s" % (p.calls, gens)


def c5_no_cache_when_ttl_zero():
    _reset()
    p = Probe(tag="c5")
    outs = [ms._mstat_call(p, ttl_s=0) for _ in range(3)]
    return p.calls == 3 and not ms._MSTAT_CACHE, "calls=%d cache=%d" % (p.calls, len(ms._MSTAT_CACHE))


def c6_inline_refresh_is_uncached():
    _reset()
    p = Probe(tag="c6")
    ms._mstat_call(p, refresh="inline")
    ms._mstat_call(p, refresh="inline")
    return p.calls == 2 and not ms._MSTAT_CACHE, "calls=%d cache=%d" % (p.calls, len(ms._MSTAT_CACHE))


def c7_marker_change_makes_new_key():
    _reset()
    p = Probe(tag="c7")
    ms._mstat_call(p)
    STATE["marker"] = (20261014, 183900)     # نقطۀ نبض جلوتر رفت
    out = ms._mstat_call(p)
    return p.calls == 2 and out["gen"] == 2 and len(ms._MSTAT_CACHE) == 2, \
        "calls=%d gen=%s keys=%d" % (p.calls, out["gen"], len(ms._MSTAT_CACHE))


def c8_error_never_cached():
    """سه حکمِ جدا، چون سه موقعیتِ واقعاً متفاوت‌اند.

    الف) موتور از اول خراب است ⇒ خطا برگردد و **هیچ** چیزی کش نشود.
    ب) دادهٔ سالم درِ پنجرۀ امانت است و موتور خراب شد ⇒ کهنۀ سالم سرو می‌شود و
       خطا جایِ آن را نمی‌گیرد (کاربرِ تب وضعیت بازار بی‌دلیل صفر نمی‌شود).
    پ) کهنه از سقف گذشته و موتور خراب است ⇒ خطا **بیرون می‌زند**، بی‌پنهان‌کاری؛
       و درِ همین حالِ بد، آن رکوردِ سالمِ کهنه هم رویِ کش نمی‌سوزد.
    """
    _reset()
    p = Probe(tag="c8")
    p.fails = True
    e1 = ms._mstat_call(p)
    e2 = ms._mstat_call(p)
    no_cache = not ms._MSTAT_CACHE
    cold_err = e1.get("status") == "error" and e2.get("status") == "error" and no_cache

    _reset()
    p2 = Probe(tag="c8b")
    good = ms._mstat_call(p2)
    p2.fails = True
    CLOCK.advance(ms._MSTAT_TTL_S + 1)              # درِ پنجرۀ امانت
    within = ms._mstat_call(p2)
    _settle()
    kept_within = list(ms._MSTAT_CACHE.values())[0][1].get("gen")

    _reset()
    p3 = Probe(tag="c8c")
    ms._mstat_call(p3)
    p3.fails = True
    CLOCK.advance(CAP0 + 10)                         # بیرون ازِ پنجرۀ امانت
    beyond = ms._mstat_call(p3)
    _settle()
    entry = list(ms._MSTAT_CACHE.values())[0][1]
    return (cold_err and within.get("status") == "ok" and within.get("gen") == 1
            and kept_within == 1 and beyond.get("status") == "error"
            and entry.get("gen") == 1 and good["gen"] == 1), \
        ("cold_err=%s within=%s/%s beyond=%s cache_gen=%s" % (
            cold_err, within.get("status"), within.get("gen"),
            beyond.get("status"), entry.get("gen")))


def c9_body_equals_uncached_path():
    """بدنۀ پاسخِ کش‌شده با بدنۀ همان fn درِ مسیرِ بی‌کش یکی است.

    `gen` شمارندۀ خودِ Probe است و عمداً بیرون گذاشته می‌شود: دو ساختِ جدا، دو
    شماره می‌دهند و این تفاوتِ kد نیست. مقایسه رویِ همان فیلدهایِ موتور است.
    """
    _reset()
    p = Probe(tag="c9")
    cached = ms._mstat_call(p)
    _reset()
    direct = ms._mstat_call(p, ttl_s=0)
    strip = lambda d: {k: v for k, v in d.items() if k != "gen"}
    same = strip(cached) == strip(direct)
    return same and cached.get("source") == "local:market.db", "cached=%s direct=%s" % (
        strip(cached), strip(direct))


def c10_bg_exception_does_not_poison():
    _reset()
    p = Probe(tag="c10")
    ms._mstat_call(p)
    CLOCK.advance(ms._MSTAT_TTL_S + 1)
    p.raises = True
    out = ms._mstat_call(p)                 # کهنه سرو می‌شود، پس‌زمینه منفجر می‌شود
    settled = _settle()
    kept = list(ms._MSTAT_CACHE.values())[0][1]["gen"] == 1
    p.raises = False
    CLOCK.advance(ms._MSTAT_TTL_S + 1)      # ttlِ جدید ⇒ تلاشِ دوباره
    ms._mstat_call(p)                       # کهنه می‌دهد و بازسازیِ تازه را می‌فرستد
    retried = _settle()
    final = ms._mstat_call(p)
    return settled and out["gen"] == 1 and kept and not ms._MSTAT_BG and retried \
        and final["gen"] == 2, \
        "settled=%s kept=%s bg=%d retried=%s final=%s" % (
            settled, kept, len(ms._MSTAT_BG), retried, final["gen"])


def c11_no_bookkeeping_leak():
    _reset()
    p = Probe(tag="c11")
    ms._mstat_call(p)
    CLOCK.advance(ms._MSTAT_TTL_S + 1)
    ms._mstat_call(p)
    _settle()
    CLOCK.advance(CAP0 + 10)
    ms._mstat_call(p)
    _settle()
    return not ms._MSTAT_WAIT and not ms._MSTAT_BG, "wait=%d bg=%d" % (
        len(ms._MSTAT_WAIT), len(ms._MSTAT_BG))


def c12_stale_ok_false_never_serves_stale():
    """`stale_ok=False` ⇒ درِ انقضا همان درخواست می‌سازد، نه کهنه.

    چرا لازم است: سنجشِ B-2 نشان داد تنها فیلدی که میانِ دو ساختِ یکسانِ حالتِ
    بانک فرق می‌کند `phase.clock_now` است — یعنی رأیِ مرحلۀ جلسه از ساعتِ دیوار
    می‌آید. این پنل بی‌سقفِ ۹۰ ثانیه باید تازه بماند.
    """
    _reset()
    p = Probe(tag="c12")
    ms._mstat_call(p, stale_ok=False)          # ساختِ اول و ذخیره در کش
    first = p.calls
    warm = ms._mstat_call(p, stale_ok=False)   # درِ ttl ⇒ اصابتِ کش
    CLOCK.advance(ms._MSTAT_TTL_S + 1)         # انقضا
    after = ms._mstat_call(p, stale_ok=False)  # ⇒ باید بسازد، نه کهنه بدهد
    _settle()
    no_bg = not ms._MSTAT_BG
    return (first == 1 and p.calls == 2 and warm.get("gen") == 1
            and after.get("gen") == 2 and no_bg), \
        "first=%d calls=%d warm_gen=%s after_gen=%s bg=%d" % (
            first, p.calls, warm.get("gen"), after.get("gen"), len(ms._MSTAT_BG))


CHECKS = [
    ("۱ ttl: پنج فراخوانی ⇒ یکِ ساخت", c1_ttl),
    ("۲ SWR: پس ازِ انقضا کهنه فوراً، بازسازی درِ پس‌زمینه", c2_swr_serves_stale_immediately),
    ("۳ سقفِ امانت: کهنۀ بیش‌ازحد ⇒ ساختِ درون‌خطی", c3_stale_is_capped),
    ("۴ تک‌پروازگی cold miss: هشت ترد ⇒ یکِ ساخت", c4_single_flight_cold),
    ("۵ ttl_s=0 ⇒ بی‌کش، لحظه‌ای", c5_no_cache_when_ttl_zero),
    ("۶ refresh=inline ⇒ رفتارِ قدیم، بی‌کش", c6_inline_refresh_is_uncached),
    ("۷ جابه‌جاییِ نشانه ⇒ کلیدِ تازه، بی‌کهنۀِ حالتِ پیشین", c7_marker_change_makes_new_key),
    ("۸ خطا هرگز کش نمی‌شود و جایِ دادهٔ سالم را نمی‌گیرد", c8_error_never_cached),
    ("۹ بدنهٔ پاسخ با مسیرِ بی‌کش یکی است", c9_body_equals_uncached_path),
    ("۱۰ انفجارِ تردِ پس‌زمینه کش را مسموم نمی‌کند", c10_bg_exception_does_not_poison),
    ("۱۱ بی‌نشتیِ `_MSTAT_WAIT` و `_MSTAT_BG`", c11_no_bookkeeping_leak),
    ("۱۲ `stale_ok=False` (رأیِ مرحلۀ جلسه) هرگز کهنه نمی‌دهد",
     c12_stale_ok_false_never_serves_stale),
]


def run(fn):
    try:
        ok, detail = fn()
    except Exception as e:
        return False, "EXCEPTION " + repr(e)[:120]
    return ok, detail


def main():
    _install()
    print("== گاردِ mstat SWR (۱۲ بررسی + ۴ کنترلِ منفی) ==")
    for what, fn in CHECKS:
        ok, detail = run(fn)
        ck(ok, what, detail)

    # ── کنترلِ منفی ۱: سقفِ امانت را بی‌اثر کن ⇒ بررسیِ ۳ باید قرمز شود
    saved_cap = ms._MSTAT_STALE_MAX_S
    ms._MSTAT_STALE_MAX_S = 10 ** 9
    ok3, d3 = run(c3_stale_is_capped)
    ms._MSTAT_STALE_MAX_S = saved_cap
    _reset()
    ck(not ok3, "کنترلِ منفیِ ۱: بی‌اثرکردنِ سقفِ امانت، سنسورِ ۳ را قرمز کرد", d3)

    # ── کنترلِ منفیِ ۲: تک‌پروازگی را بردار ⇒ بررسیِ ۴ باید قرمز شود
    saved_wait = ms._MSTAT_WAIT
    ms._MSTAT_WAIT = {}
    class _NoWait(dict):
        def get(self, k, default=None):
            return None            # هیچ‌وقت «سازندهٔ جاری» را نمی‌بیند
        def setdefault(self, k, v):
            dict.__setitem__(self, k, v)
            return None
    ms._MSTAT_WAIT = _NoWait()
    ok4, d4 = run(c4_single_flight_cold)
    ms._MSTAT_WAIT = saved_wait
    _reset()
    ck(not ok4, "کنترلِ منفیِ ۲: بی‌اثرکردنِ تک‌پروازگی، سنسورِ ۴ را قرمز کرد", d4)

    # ── کنترلِ منفیِ ۳: خطا را کش کن ⇒ بررسیِ ۸ باید قرمز شود
    saved_store = ms._mstat_store

    def _store_errors(full_key, now, out):
        with ms._MSTAT_LOCK:
            ms._MSTAT_CACHE[full_key] = (now, out)
        return True
    ms._mstat_store = _store_errors
    ok8, d8 = run(c8_error_never_cached)
    ms._mstat_store = saved_store
    _reset()
    ck(not ok8, "کنترلِ منفیِ ۳: کش‌کردنِ پاسخِ خطا، سنسورِ ۸ را قرمز کرد", d8)

    # ── کنترلِ منفیِ ۴: `stale_ok=False` را بی‌اثر کن ⇒ بررسیِ ۱۲ باید قرمز شود
    saved_call = ms._mstat_call

    def _ignore_stale_ok(fn, *a, **k):
        k.pop("stale_ok", None)          # رأیِ جلسه دگر دیگر کهنه سرو می‌کند
        return saved_call(fn, *a, **k)
    ms._mstat_call = _ignore_stale_ok
    ok12, d12 = run(c12_stale_ok_false_never_serves_stale)
    ms._mstat_call = saved_call
    _reset()
    ck(not ok12, "کنترلِ منفیِ ۴: بی‌اثرکردنِ `stale_ok`، سنسورِ ۱۲ را قرمز کرد", d12)

    ms.time = _REAL_TIME
    print("\n%d passed / %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
