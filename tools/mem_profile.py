#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مصرفِ RAMِ خودِ بک‌اند، مرحله‌به‌مرحله — نه «برنامه سنگین است».

چرا این ابزار: سنجشِ ۱۴۰۵-۰۷-۰۷ رویِ اپِ نصبیِ ۱.۰.۵۴، پروسۀ پایتونِ تنها
۸۲۶ مگابایت Private Bytes داشت و ۳۹۶ مگابایت Resident؛ بیست‌وچهار بار ساختنِ
کلِ بدنهٔ /api/market آن را فقط ۲۴ مگابایت بالا برد، پس آن عددِ اولیه از
«ساختنِ مکرر» نمی‌آید؛ چیزی درِ warm-up بزرگ نگه داشته می‌شود. این اسکریپت
همان warm-up را مرحله‌به‌مرحله می‌زند و در هر مرحله RSS + بالاترین محل‌هایِ
اختصاصِ پایتون (tracemalloc) را چاپ می‌کند، تا معلوم شود کدام کش نگهش داشته.

    PYTHONIOENCODING=utf-8 python tools/mem_profile.py
    PYTHONIOENCODING=utf-8 python tools/mem_profile.py --polls 20

--json مسیرِ خروجیِ JSON (برایِ ضمیمه شدن در _audit).
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import tracemalloc
from collections import OrderedDict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def rss_mb() -> float:
    """Resident set از ویندوز. psapi.dll حلقهٔ call را export می‌کند؛ kernel32
    فقط K32GetProcessMemoryInfo را دارد. اگر نشد، استثناء می‌دهد — عددِ -1 در
    این ابزار یعنی «سنجیده نشد»، و گزارش با آن گمراه‌کننده است."""
    import ctypes

    class CTR(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_uint32),
            ("PageFaultCount", ctypes.c_uint32),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    ctr = CTR()
    ctr.cb = ctypes.sizeof(CTR)
    last_err = None
    for lib in ("psapi", "kernel32"):
        try:
            fn = getattr(ctypes.windll, lib)
            get = getattr(fn, "GetProcessMemoryInfo", None) or getattr(fn, "K32GetProcessMemoryInfo", None)
            if get is None:
                continue
            get.argtypes = [ctypes.c_void_p, ctypes.POINTER(CTR), ctypes.c_uint32]
            get.restype = ctypes.c_int
            h = ctypes.windll.kernel32.GetCurrentProcess()
            if get(h, ctypes.byref(ctr), ctr.cb):
                return ctr.WorkingSetSize / 1e6
        except AttributeError as e:
            last_err = e
    raise RuntimeError(f"GetProcessMemoryInfo in hand نشد: {last_err}")


def top_sites(n=10):
    gc.collect()
    snap = tracemalloc.take_snapshot()
    out = []
    for st in snap.statistics("lineno")[:n]:
        f = str(st.traceback[0].filename).replace(_ROOT + os.sep, "")
        out.append({"site": f"{f}:{st.traceback[0].lineno}", "mb": round(st.size / 1e6, 2)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--polls", type=int, default=0, help="چند بار بدنهٔ کاملِ /api/market بسازد")
    ap.add_argument("--sample-every", type=int, default=0,
                    help="در هر چند بازسازی یک نمونهٔ RSS بگیرد (سلسله‌مراتبِ نشتی)")
    ap.add_argument("--json", default="", help="مسیرِ نوشتن JSON")
    a = ap.parse_args()

    steps = OrderedDict()
    series = []
    tracemalloc.start()
    steps["baseline(importشده، چیزی warm نشده)"] = {"rss_mb": round(rss_mb(), 1)}

    import bors_config  # noqa: F401  (path helpers)
    steps["import bors_config"] = {"rss_mb": round(rss_mb(), 1)}

    from api import market as M
    steps["import api.market"] = {"rss_mb": round(rss_mb(), 1), "top": top_sites(6)}

    class _R:
        headers: dict = {}

    before = rss_mb()
    resp = M._build_market_response(_R())
    steps["یک بار ساختنِ کاملِ /api/market"] = {
        "rss_mb": round(rss_mb(), 1),
        "delta_mb": round(rss_mb() - before, 1),
        "body_bytes": len(getattr(resp, "body", b"") or b""),
        "top": top_sites(10),
    }

    for i in range(a.polls):
        M._build_market_response(_R())
        if a.sample_every and (i + 1) % a.sample_every == 0:
            series.append({"builds": i + 1, "rss_mb": round(rss_mb(), 1)})
    if a.polls:
        steps["series"] = series
        steps[f"{a.polls} بار ساختنِ دوباره"] = {
            "rss_mb": round(rss_mb(), 1),
            "cache_keys": sorted(M.MARKET_CACHE.keys()),
            "top": top_sites(10),
        }
        if len(series) >= 3:
            # شیبِ خطِ آخر: اگر حافظه بیایستد، گرم‌شدنِ arena است؛ اگر خطی برود،
            # نشتیِ هر بازسازی است و درِ نشستِ ۳٫۵ ساعته (تیکِ ۵ ثانیه ≈ ۲۵۰۰
            # بازسازی) معنايش عددِ گیگابایتی است.
            tail = series[-3:]
            dx = tail[-1]["builds"] - tail[0]["builds"]
            dy = tail[-1]["rss_mb"] - tail[0]["rss_mb"]
            steps["mb_per_build_over_last_%d" % tail[-1]["builds"]] = round(dy / dx, 3) if dx else None
            first = series[1] if len(series) > 1 else series[0]
            dx2 = tail[-1]["builds"] - first["builds"]
            steps["mb_per_build_whole_run"] = round((tail[-1]["rss_mb"] - first["rss_mb"]) / dx2, 3) if dx2 else None

    try:
        from api.screener import warm_screener_cache
        before = rss_mb()
        warm_screener_cache()
        steps["warm_screener_cache()"] = {"rss_mb": round(rss_mb(), 1),
                                          "delta_mb": round(rss_mb() - before, 1),
                                          "top": top_sites(10)}
    except Exception as e:  # گرم‌کردنِ اسکنر در این نشست ممکن است ناموفق باشد
        steps["warm_screener_cache()"] = {"error": f"{type(e).__name__}: {e}"}

    print(json.dumps(steps, ensure_ascii=False, indent=1))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(steps, f, ensure_ascii=False, indent=1)
        print(f"\nJSON -> {a.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
