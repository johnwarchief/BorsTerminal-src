#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/proc_probe_cache_v1105.py — گاردِ شمارشِ فرایند با کشِ stale-while-revalidate.

چرا این گارد متولد شد: baselineِ زندهٔ همین نشست (۲۰ نمونه رویِ بک‌اندِ درِ ساعتِ
بازار، ۱۰:۴۲:۵۹→۱۰:۴۷:۱۵) نشان داد `GET /api/market/sync-state` با بدنۀ ۱۴۱ بایت
p50 = **573.1 ms** پاسخ می‌دهد و تنها کارش یکِ `_count_procs("test_tsetmc")` است.
رویِ ویندوز آن یکِ شمارش یعنی بالا آمدنِ `powershell.exe` و
`Get-CimInstance Win32_Process` رویِ همهٔ فرایندها. سنجشِ جایگزین‌ها:
queryِ فیلترشدهٔ CIM = ۵۷۹ms در برابرِ ۵۸۹msِ فعلی (بهتر نمی‌شود؛ هزینه از
خودِ PowerShell است)، `Get-Process python` = ۲۳۳ms ولی command line را ندارد پس
نمی‌تواند سینکرِ بازار را از خزندۀ کدال جدا کند ⇒ تنها راهِ درست، نپرسیدنِ
آن درِ هر درخواست است.

چه قفلی می‌زند (و چرا هرکدام بدونش باج می‌دهیم):
  ۱) ttl: پنج فراخوانی درِ یکِ پنجره ⇒ یکِ شمارشِ واقعی.
  ۲) SWR: پس از انقضا، پاسخِ کهنه فوراً داده می‌شود و تازه‌سازی درِ تردِ
     پس‌زمینه است — درخواستِ کاربر هیچ‌وقت ۶۰۰ms نمی‌پردازد.
  ۳) تک‌پروازگی: ۱۶۰ فراخوانیِ هشت ترد ⇒ یکِ زیرپروسه، نه هشت‌تا.
  ۴) `ttl_s=0`: تصمیمِ کشتنِ پروسه هنوز لحظه‌ای و بی‌کش است.
  ۵) نوع و معنای پاسخ عوض نشده (boolean؛ نه تعداد، نه رشته).

عددِ A/B واقعی چاپ می‌شود ولی آستانه‌اش assert نمی‌شود (زمان‌سنجیِ زیرپروسه رویِ
ماشین‌های مختلف نوسان دارد) — فقط جهتِ بهبودگی سنجیده می‌شود. بی‌شبکه،
بی‌نوشتن رویِ بانک، بی‌کشتنِ هیچ پروسه‌ای.

اجرا:  PYTHONIOENCODING=utf-8 python dev/proc_probe_cache_v1105.py
خروجی: «N passed / M failed»، exit 0 یا 1
"""
from __future__ import annotations

import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from api import _core                                            # noqa: E402

PASS = FAIL = 0


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("PASS %s" % what)
    else:
        FAIL += 1
        print("FAIL %s%s" % (what, ("   ← " + str(detail)) if detail else ""))


class Probe:
    """جایِ شمارشِ واقعی: می‌شمارد، اختصاراً می‌خوابد، و مقدارِ قابل‌کنترل می‌دهد."""

    def __init__(self, value=True, cost=0.0):
        self.calls = []
        self.value = value
        self.cost = cost
        self.lock = threading.Lock()
        self.started = threading.Event()

    def __call__(self, pattern):
        with self.lock:
            self.calls.append(pattern)
        self.started.set()
        if self.cost:
            time.sleep(self.cost)
        return self.value

    @property
    def n(self):
        with self.lock:
            return len(self.calls)


def main() -> int:
    raw_real = _core._count_procs_raw
    # ── ۱) ttl: پنج فراخوانی درِ یکِ پنجره ⇒ یکِ شمارش ────────────────────
    _core._proc_cache_clear()
    pr = Probe(value=True)
    _core._count_procs_raw = pr
    try:
        vals = [_core._count_procs("test_tsetmc", now=100.0) for _ in range(5)]
        ck(pr.n == 1, "پنج فراخوانی درِ ttl ⇒ یکِ شمارشِ واقعی", pr.n)
        ck(vals == [True] * 5, "پاسخ‌ها همان booleanِ نخست (کش مقدار را قاتی نمی‌کند)", vals)

        # ── ۲) ttl_s=0 ⇒ بی‌کش (تصمیمِ کشتن لحظه‌ای می‌ماند) ───────────────
        _core._proc_cache_clear()
        for _ in range(4):
            _core._count_procs("test_tsetmc", ttl_s=0)
        ck(pr.n == 5, "با ttl_s=0 هر فراخوانی واقعاً می‌شمارد", pr.n)

        # ── ۳) SWR: پس از انقضا پاسخِ کهنه فوراً، تازه‌سازی درِ ترد ────────
        _core._proc_cache_clear()
        _core._count_procs("test_tsetmc", now=200.0)          # cold: همین‌جا می‌سازد
        ck(pr.n == 6, "نخستین فراخوانی سرد خودش می‌سازد", pr.n)
        bg = Probe(value=True, cost=0.20)
        _core._count_procs_raw = bg
        t0 = time.perf_counter()
        v = _core._count_procs("test_tsetmc", ttl_s=1.0, now=9999.0)   # منقضی
        dt_ms = (time.perf_counter() - t0) * 1000.0
        ck(v is True and dt_ms < 5.0,
           "درخواستِ پس از انقضا کهنه را بی‌انتظارِ زیرپروسه می‌گیرد",
           (v, round(dt_ms, 2)))
        pr2 = bg
        ok_bg = pr2.started.wait(2.0)
        ck(ok_bg, "تازه‌سازی درِ تردِ پس‌زمینه شروع شد (بی‌بلوکردنِ درخواست)",
           pr2.n)
        time.sleep(0.35)
        v2 = _core._count_procs("test_tsetmc", now=99999.0)
        ck(1 <= pr2.n <= 2 and v2 is True,
           "بازسازیِ پس‌زمینه یک‌بار انجام شد و کشِ تازه جایِ کهنه را گرفت",
           (pr2.n, v2))

        # ── ۴) refresh="none" ⇒ بی‌ردیف‌کردنِ هیچ کاری (کنترلِ آزمون) ───────
        _core._proc_cache_clear()
        _core._count_procs("app.py", now=10.0)
        cn = Probe(value=False)
        _core._count_procs_raw = cn
        v3 = _core._count_procs("app.py", ttl_s=1.0, now=50.0, refresh="none")
        ck(cn.n == 0 and v3 is True,
           'با refresh="none" پاسخِ کهنه داده می‌شود و هیچ شمارشی زده نمی‌شود',
           (cn.n, v3))

        # ── ۵) تک‌پروازگی درِ تردهای هم‌زمان ────────────────────────────────
        _core._proc_cache_clear()
        many = Probe(value=True, cost=0.05)
        _core._count_procs_raw = many
        errs = []

        def _hammer():
            try:
                for _ in range(20):
                    r = _core._count_procs("test_tsetmc")
                    assert isinstance(r, bool), r
            except Exception as e:
                errs.append(repr(e))

        ts = [threading.Thread(target=_hammer) for _ in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        ck(not errs, "۱۶۰ فراخوانی درِ هشت ترد بی‌خطا", errs[:2])
        ck(many.n <= 2,
           "تک‌پروازگی: زیرپروسه‌ها شمارش‌شدنی‌اند، نه ۱۶۰تا", many.n)
    finally:
        _core._count_procs_raw = raw_real
        _core._proc_cache_clear()

    # ── ۶) مسیرِ واقعیِ endpoint ───────────────────────────────────────────
    hits = {"n": 0}

    def stub(pattern):
        hits["n"] += 1
        return False
    _core._count_procs_raw = stub
    try:
        import json
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "bors_market_status_probe.json")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"stage": "market", "ts": "2026-10-14T11:20:00"}, f)
        import api.market as MK
        MK.MARKET_STATUS_PATH = tmp
        _core._proc_cache_clear()
        r1 = MK.market_sync_state()
        r2 = MK.market_sync_state()
        r3 = MK.market_sync_state()
        ck(hits["n"] == 1,
           "سه درخواستِ پیاپیِ /api/market/sync-state ⇒ یکِ شمارشِ پروسه", hits["n"])
        ck(r1 == r2 == r3 and r1["status"] == "success" and
           r1["running"] is False and r1["last"]["stage"] == "market",
           "ساختار و مقدارِ پاسخِ endpoint دست‌نخورده است", r1)
    finally:
        _core._count_procs_raw = raw_real
        _core._proc_cache_clear()

    # ── ۷) A/B واقعی رویِ همین ماشین (جهت، نه آستانه) ─────────────────────
    if os.name == "nt":
        _core._proc_cache_clear()
        t0 = time.perf_counter()
        for _ in range(3):
            _core._count_procs_raw("test_tsetmc")
        raw_s = time.perf_counter() - t0
        _core._proc_cache_clear()
        t0 = time.perf_counter()
        for _ in range(3):
            _core._count_procs("test_tsetmc")
        warm_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        for _ in range(3):
            _core._count_procs("test_tsetmc")
        hot_s = time.perf_counter() - t0
        print("A/B: سه شمارشِ خام = %.0f ms | سرد+۲ کش = %.0f ms | سه فراخوانیِ گرم = %.1f ms"
              % (raw_s * 1000.0, warm_s * 1000.0, hot_s * 1000.0))
        ck(hot_s * 3 < raw_s / 3.0,
           "مسیرِ گرم دست‌کم ده‌ها برابر ارزان‌تر از سه شمارشِ خام است",
           (round(raw_s * 1000, 1), round(hot_s * 1000, 2)))

    print("\n%d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
