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

# ── ۲) پنجره از دادهٔ واقعیِ codal_notices ────────────────────────────────
section("pipeline: publication windows from DB")


def fresh_db():
    c = sqlite3.connect(":memory:", timeout=60, isolation_level=None)
    c.row_factory = sqlite3.Row
    CF.create_schema(c)
    CF.migrate_schema(c)
    PL.ensure_schema(c)
    c.execute("CREATE TABLE IF NOT EXISTS instruments (ins_code TEXT PRIMARY KEY,"
              " l_val18 TEXT, l_val30 TEXT, paper_type INTEGER)")
    return c


def add_notice(c, tn, sym, pub="1405/07/20 10:00:00",
               title="گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۵/۰۷/۳۰"):
    c.execute("INSERT OR REPLACE INTO codal_notices (tracing_no, symbol,"
              " company_name, title, letter_code, publish_date, sent_date, url,"
              " fetched_at, pdf_url, excel_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (tn, sym, sym, title, "1", pub, pub,
               "https://codal.ir/L/Detail/%d" % tn, "2026-11-03 00:00:00", "", ""))


c = fresh_db()
for i in range(240):
    add_notice(c, 1000 + i, "نماد%d" % i,
               pub="1405/07/20 %02d:10:00" % (9 + (i % 3)))
pub = PL.publication_windows(c, now="2026-11-03 10:00:00")
ck(pub["source"] == "learned" and pub["samples"] >= 200,
   "نمونهٔ کافی ⇒ پنجره از داده یاد گرفته می‌شود", pub)
ck(any(a <= 9 and b >= 12 for a, b in pub["windows"]),
   "پنجرهٔ صبح درست ساخته شد", pub["windows"])
cache = PL.publication_windows(c, now="2026-11-03 18:00:00")
ck(cache.get("day") == pub.get("day") and cache["windows"] == pub["windows"],
   "کشِ روزانه دوباره SQL نمی‌زند")

c2 = fresh_db()
for i in range(3):
    add_notice(c2, 2000 + i, "کم%d" % i, pub="1405/07/20 10:00:00")
low = PL.publication_windows(c2, now="2026-11-03 10:00:00")
ck(low["source"] == "default"
   and low["windows"] == [list(x) for x in CAD.DEFAULT_WINDOWS],
   "نمونهٔ کم ⇒ پیش‌فرضِ ۸ تا ۲۰", low)

gap_in, pub_in = PL.current_network_gap(c, now="2026-11-03 10:00:00", jitter=False)
gap_out, _ = PL.current_network_gap(c, now="2026-11-03 14:00:00", jitter=False)
ck(gap_in == 600, "داخلِ پنجرهٔ یادگرفته ⇒ ۶۰۰ ثانیه", gap_in)
ck(gap_out == 10800, "بیرون ⇒ ۳ ساعت", gap_out)
ck("windows" in pub_in and "samples" in pub_in,
   "خروجیِ publication برای status کامل است", pub_in)

# ── ۳) نوشتنِ تازه ⇒ باطل‌سازیِ فوری، حتی در بازارِ باز ──────────────────
section("pipeline: immediate invalidation")


def ms_row(tn, sym, pe="1405/06/31", pub="1405/07/20 10:00:00"):
    return ("ms", (tn, sym, "گزارش فعالیت ماهانه", pe, 1405, 6,
                   1000.0, 6000.0, 900.0, 5400.0, 10.0, 60.0, "عدد",
                   "https://codal.ir/PDF/%d" % tn, ""), "ok")


c = fresh_db()
add_notice(c, 3001, "فولاد")
PL.enqueue(c, [(3001, "ms")])
calls = []
real_invalidate = PL._invalidate_materialized
PL._invalidate_materialized = lambda conn, symbols: (calls.append(list(symbols)),
                                                     len(symbols))[1]
try:
    out = PL.run_cycle(c, "test", discover=None,
                       scrape=lambda n: ms_row(3001, "فولاد"),
                       recalc="invalidate", now="2026-11-03 10:30:00",
                       instruments=lambda conn: {})
finally:
    PL._invalidate_materialized = real_invalidate
ck(out.get("touched") == ["فولاد"], "نمادِ نوشته‌شده در touched ثبت شد", out)
ck(calls == [["فولاد"]], "باطل‌سازیِ فوری با همان نماد صدا زده شد", calls)
ck(PL.dirty_count(c) == 1, "نماد در pipeline_dirty می‌ماند برای محاسبهٔ بعدی")
ck(out.get("recalc_invalidate_only") is True,
   "حالتِ invalidate-only اعلام شد", out)
