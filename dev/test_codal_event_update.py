# -*- coding: utf-8 -*-
"""dev/test_codal_event_update.py — گارد آفلاین به‌روزرسانی رویدادمحور ۵ شاخص.

Run: PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
"""
import datetime
import json
import os
import shutil
import sqlite3
import sys
import tempfile

os.environ["BORS_CODAL_OFFLINE"] = "1"
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dev"))

import codal_cadence as CAD          # noqa: E402
import codal_fetcher as CF           # noqa: E402
import codal_pipeline as PL          # noqa: E402

CHECKS = []


def ck(cond, msg, detail=""):
    CHECKS.append(bool(cond))
    print("  %s %s%s" % ("PASS" if cond else "FAIL", msg,
                         ("   ← " + str(detail)) if (detail and not cond) else ""))
    return bool(cond)


TMP = tempfile.mkdtemp(prefix="codal_event_update_")


def section(name):
    print("\n== %s ==" % name)


# ── ۱) ماژول خالصِ کادنس ──────────────────────────────────────────────────
section("cadence: windows / gap")
counts = {h: 0 for h in range(24)}
for h, n in ((8, 10), (9, 100), (10, 100), (11, 90),
             (16, 100), (17, 100), (18, 80)):
    counts[h] = n
w = CAD.windows_from_hour_counts(counts, min_samples=200, share=0.25)
ck(len(w) == 2 and w[0][0] <= 9 and w[0][1] >= 12 and w[1][0] <= 16 and w[1][1] >= 19,
   "دو قلهٔ انتشار ⇒ دو پنجرهٔ جدا", w)
ck(CAD.windows_from_hour_counts({h: 1 for h in range(24)}, min_samples=200)
   == list(CAD.DEFAULT_WINDOWS),
   "نمونهٔ کم ⇒ پیش‌فرضِ محافظه‌کارانه 08:00–20:00")
ck(CAD.inside_window(9.5, w) and not CAD.inside_window(14.0, w),
   "inside_window مرزها را درست می‌فهمد", (w,))
ck(CAD.gap_seconds(9.5, w, enabled=True) == 600,
   "داخلِ پنجره ⇒ ۶۰۰ ثانیه")
ck(CAD.gap_seconds(14.0, w, enabled=True) == 10800,
   "بیرونِ پنجره ⇒ ۳ ساعت")
ck(CAD.gap_seconds(9.5, w, enabled=False) == 10800,
   "خاموش ⇒ همیشه ۳ ساعت")
ck(CAD.gap_seconds(9.5, w, enabled=True, jitter_s=-100000) == 60,
   "jitter هرگز زیرِ کفِ ۶۰ ثانیه نمی‌رود")
ck(CAD.window_labels(w)[0] == "08:30-12:30",
   "برچسبِ پنجره برای status", CAD.window_labels(w))
