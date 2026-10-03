# -*- coding: utf-8 -*-
"""_audit/perf_board_build_bench.py — آونگِ «بایت‌به‌بایت یکی، سریع‌تر»

هدف: بهینگیِ مسیرِ ساختنِ تابلو بی‌آنکه حتی یک بایت از بدنه عوض شود. ابزار دو
چیز می‌خواهد و همین هر دو را می‌دهد:

  • **برابری:** sha256ِ بدنۀ `/api/market` درِ هر دور ثبت می‌شود. اگر کدِ تازه
    حتی یک بایت فرق کند، خروجیِ benchmark مردود است (نه «تقریباً یکی»).
  • **زمان:** پنج دورِ گرم + میانه، و یک دورِ `cProfile` که تفکیکِ فازها
    (کپیِ قاب، overlay، ریاضیاتِ pandas، `_slim_records`، `orjson.dumps`) را
    نشان می‌دهد تا معلوم شود پول کجا سوخته است.

بانک: **کپیِ** market.dbِ نصب‌شدہ (نه خودِ فایل — `ensure_board_history` پنجره‌ها
را می‌نویسد). حالتِ داغِ RAM درِ این فرایند خالی است ⇒ `overlay_codes` تهی
می‌دهد و قابِ ایستایِ خالص سنجیده می‌شود؛ دقیقاً همان مسیری که درِ سرورِ واقعی
هر ~۶۰ ثانیه یک‌بار اجرا می‌شود.
"""
import cProfile
import hashlib
import io
import json
import os
import pstats
import shutil
import statistics
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SRC_DB = os.environ.get("BENCH_DB", "")
OUT = os.environ.get("BENCH_OUT", "")


def prep_db():
    """کپیِ read-copy از بانکِ واقعی (خودِ فایل هرگز باز نمی‌شود).

    بانکِ نصب‌شدہ درِ ساعتِ بازار هر چند ثانیه عوض می‌شود؛ اگر هر دورِ benchmark
    نمونه‌برداشتِ تازه‌ای می‌گرفت، sha256ِ «قبل» و «بعد» دو دادهٔ مختلف می‌بود و
    برابری بی‌معنی می‌شد. پس یکِ کپیِ ثابت با BENCH_TMP ساخته می‌شود و همهٔ دورها
    رویِ همان snapshot می‌خورند.
    """
    keep = os.environ.get("BENCH_TMP", "")
    if keep and os.path.exists(keep) and os.path.getsize(keep) > 1e6:
        print("reusing snapshot %s (%.0f MB)" % (keep, os.path.getsize(keep) / 1e6))
        return keep
    if not SRC_DB or not os.path.exists(SRC_DB):
        sys.exit("BENCH_DB باید به market.db واقعی اشاره کند")
    dst = keep or os.path.join(tempfile.mkdtemp(prefix="bors_bench_"), "market.db")
    t = time.time()
    shutil.copy2(SRC_DB, dst)
    print("copied %.0f MB in %.1fs" % (os.path.getsize(dst) / 1e6, time.time() - t))
    return dst


def wrap(mod, name, sink):
    """تایمرِ فاز بی‌دست‌زدنِ سورسِ محصول: نامِ سراسری را درِ ماژول می‌پوشانیم."""
    orig = getattr(mod, name)

    def inner(*a, **k):
        t = time.perf_counter()
        try:
            return orig(*a, **k)
        finally:
            sink.setdefault(name, []).append((time.perf_counter() - t) * 1000.0)
    inner.__wrapped__ = orig
    setattr(mod, name, inner)
    return orig


def main():
    dst = prep_db()
    import bors_config
    bors_config.DB_PATH = dst
    import api._core as core
    core.DB_PATH = dst
    import api.market as M
    M.get_db = lambda: __import__("sqlite3").connect(dst, timeout=30)

    ph = {}
    for fn in ("_board_frame", "_live_overlay", "_slim_records", "_encode_board",
               "apply_tape_flags", "_mirror", "_board_query_frame"):
        if hasattr(M, fn):
            wrap(M, fn, ph)

    req = M._MarketInternalRequest()
    sizes, digests, times = [], [], []
    for i in range(6):
        t0 = time.perf_counter()
        r = M._build_market_response(req)
        dt = time.perf_counter() - t0
        body = getattr(r, "body", b"") or b""
        times.append(dt * 1000.0)
        sizes.append(len(body))
        digests.append(hashlib.sha256(body).hexdigest())
        print("build %d: %7.1f ms  %9d B  sha=%s" % (i, dt * 1000.0, len(body), digests[-1][:16]))
    cold, warm = times[0], times[1:]
    if len(set(digests)) != 1:
        print("FAIL: بدنه در دو دور یکی نیست ⇒ سنجشِ بی‌رفتار ممکن نیست")
        return 1

    # حالتِ ممیزی (?fields=all) هم باید بایت‌به‌بایت ثابت بماند
    all_body = M._build_market_response(req, drop_unused=False, store_cache=False).body
    all_sha = hashlib.sha256(all_body).hexdigest()
    print("fields=all: %d B sha=%s" % (len(all_body), all_sha[:16]))

    pr = cProfile.Profile()
    pr.enable()
    M._build_market_response(req)
    pr.disable()
    buf = io.StringIO()
    pstats.Stats(pr, stream=buf).sort_stats("tottime").print_stats(18)
    top = [l for l in buf.getvalue().splitlines() if l.strip()][:30]

    out = {"builds_ms_all": [round(x, 1) for x in times],
           "first_cold_ms": round(cold, 1),
           "warm_median_ms": round(statistics.median(warm), 1),
           "warm_min_ms": round(min(warm), 1),
           "body_bytes": sizes[-1], "body_sha256": digests[-1],
           "fields_all_bytes": len(all_body), "fields_all_sha256": all_sha,
           "phases_ms": {k: round(statistics.median(v[1:]) if len(v) > 1 else v[0], 1)
                         for k, v in ph.items()},
           "profile_top": top, "db": dst}
    print(json.dumps({k: v for k, v in out.items() if k != "profile_top"},
                     ensure_ascii=False, indent=1))
    print("\n".join(top[:24]))
    if OUT:
        json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\nwrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
