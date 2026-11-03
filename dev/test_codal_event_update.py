# -*- coding: utf-8 -*-
"""dev/test_codal_event_update.py — گارد آفلاین به‌روزرسانی رویدادمحور ۵ شاخص.

Run: PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py

`--live` (opt-in، هرگز در CI): فقط یک صفحهٔ خواندنیِ CODAL با پروفایلِ POLITE.
"""
import datetime
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

# گاردِ آفلاین همیشه برقرار است؛ `--live` فقط پروبِ صریح را مستثنا می‌کند،
# نه خودِ گاردها را.
LIVE = "--live" in sys.argv
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
import codal_periods as CP           # noqa: E402
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

# ── ۴) گیتِ ردیفی: ردیف خراب هرگز در canonical نمی‌نشیند ─────────────────
section("validation: row gate + quarantine")
from codal_row_gate import validate_extracted_row  # noqa: E402


def fs_row(tn, sym, rev=1000.0, gross=300.0, url="https://codal.ir/PDF/x",
           pe="1405/06/31", pub="1405/07/20 10:00:00"):
    row = [tn, sym, sym, "صورت‌های مالی سالانه حسابرسی‌شده", "FS", 12, pe, pub]
    row += [rev, gross, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    row += ["میلیون ریال", url, "2026-11-03 10:00:00", 1, 0, "1404", "mrl"]
    return tuple(row)


def ms_tuple(tn=10, sym="فولاد", pe="1405/06/31", monthly=1000.0, ytd=6000.0,
             pdf="https://codal.ir/PDF/m", excel=""):
    """همان ۱۵ عنصرِ `codal_fetcher.scrape_notice_row` برایِ گزارشِ ماهانه."""
    return (tn, sym, "گزارش فعالیت ماهانه", pe, 1405, 6, monthly, ytd,
            900.0, 5400.0, 10.0, 60.0, "عدد", pdf, excel)


ok, code = validate_extracted_row("fs", fs_row(1, "فولاد"))
ck(ok and code == "", "ردیفِ سالم پذیرفته می‌شود", code)
ok, code = validate_extracted_row("fs", fs_row(2, "فولاد", rev=-1))
ck(not ok and code == "negative_revenue:revenue", "درآمد منفی رد می‌شود", code)
ok, code = validate_extracted_row("fs", fs_row(3, "فولاد", rev=100, gross=101))
ck(not ok and code == "gross_gt_revenue", "سود ناخالص > درآمد رد می‌شود", code)
ok, code = validate_extracted_row("fs", fs_row(4, "فولاد", url=""))
ck(not ok and code == "missing_provenance", "بی‌منبع رد می‌شود", code)
ok, code = validate_extracted_row("fs", fs_row(5, "فولاد", pe="1406/12/29"),
                                  today=datetime.date(2026, 11, 3))
ck(not ok and code == "future_period", "دورهٔ آینده رد می‌شود", code)
ok, code = validate_extracted_row("fs", fs_row(6, "فولاد", pub=""))
ck(not ok and code == "missing_provenance",
   "FS بی publish_date هم بی‌منبع است", code)
ok, code = validate_extracted_row("fs", fs_row(7, "فولاد")[:24])
ck(not ok and code == "bad_shape", "FS بریده ⇒ bad_shape (نه IndexError)", code)

ok, code = validate_extracted_row("ms", ms_tuple()[:14])
ck(not ok and code == "bad_shape", "MS بریده ⇒ bad_shape (نه IndexError)", code)

TODAY = datetime.date(2026, 11, 3)
ok, code = validate_extracted_row("ms", ms_tuple(excel=""), today=TODAY)
ck(ok and code == "", "MS فقط pdf_url پذیرفته می‌شود", code)
ok, code = validate_extracted_row("ms", ms_tuple(pdf="", excel="https://codal.ir/X/m"),
                                  today=TODAY)
ck(ok and code == "", "MS فقط excel_url پذیرفته می‌شود", code)
ok, code = validate_extracted_row("ms", ms_tuple(pdf="", excel=""), today=TODAY)
ck(not ok and code == "missing_provenance", "MS بی هیچ پیوندی رد می‌شود", code)
ok, code = validate_extracted_row("ms", ms_tuple(ytd=-1), today=TODAY)
ck(not ok and code == "negative_revenue:ytd_revenue",
   "ytd_revenue منفی رد می‌شود", code)
ok, code = validate_extracted_row("ms", ms_tuple(pe="1406/12/29"), today=TODAY)
ck(not ok and code == "future_period", "MS با دورهٔ آینده رد می‌شود", code)

ck(CP.j2g_date("1405/06/31 12:10:00") == "2026-09-22 12:10:00",
   "تبدیلِ معتبرِ موجود تغییر نکرد", CP.j2g_date("1405/06/31 12:10:00"))
ck(CP.j2g_date("1405/07/31") is None,
   "روزِ ۳۱ در ماهِ ۳۰روزه ⇒ None", CP.j2g_date("1405/07/31"))
ck(CP.j2g_date("2026-11-03") is None,
   "سالِ بیرونِ ۱۳۰۰..۱۵۰۰ ⇒ None", CP.j2g_date("2026-11-03"))
ck(CP.j2g_date("1403/12/30") == "2025-03-20",
   "اسفندِ کبیسه هنوز تبدیل می‌شود", CP.j2g_date("1403/12/30"))
ck(CP.j2g_date("1404/12/30") is None,
   "اسفندِ غیرکبیسه ۳۰ ندارد", CP.j2g_date("1404/12/30"))

c = fresh_db()
add_notice(c, 4001, "فولاد")
PL.enqueue(c, [(4001, "fs")])
out = PL.run_cycle(
    c, "test", discover=None,
    scrape=lambda n: ("fs", fs_row(4001, "فولاد", rev=-5), "ok"),
    now="2026-11-03 20:00:00", instruments=lambda conn: {})
state = c.execute("SELECT state, last_error FROM codal_extracted WHERE tracing_no=4001").fetchone()
ck(tuple(state) == ("quarantined", "negative_revenue:revenue"),
   "ردیفِ خراب قرنطینه شد و نوشته نشد", tuple(state))
rows = c.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0]
ck(rows == 0, "هیچ ردیفِ خرابی در canonical نیست", rows)
ck(out.get("quarantined") == 1, "شمارشِ چرخه قرنطینه را گزارش می‌کند", out)

# ── ۵) قفلِ متقابل با خط شبانه ───────────────────────────────────────────
section("locks: orchestrator vs incremental worker")


def write_lock(work, age_s=30):
    p = os.path.join(work, "codal_auto.lock")
    open(p, "w", encoding="utf-8").write("1 test")
    ts = datetime.datetime.now().timestamp() - age_s
    os.utime(p, (ts, ts))


work = tempfile.mkdtemp(prefix="codal_lock_", dir=TMP)
write_lock(work, age_s=30)
b = PL.orchestrator_busy(work_dir=work)
ck(b["busy"] is True and b["reason"] == "lock-fresh",
   "قفلِ تازهٔ شبانه ⇒ مشغول", b)
os.utime(os.path.join(work, "codal_auto.lock"),
         (datetime.datetime.now().timestamp() - 7 * 3600,) * 2)
b = PL.orchestrator_busy(work_dir=work)
ck(b["busy"] is False, "قفلِ کهنه‌تر از ۶ ساعت ⇒ آزاد", b)

real_busy = PL.orchestrator_busy
PL.orchestrator_busy = lambda *a, **k: {"busy": True, "reason": "lock-fresh",
                                        "stage": "fetching"}
try:
    r = PL.worker_once(conn=fresh_db(), now="2026-11-03 10:30:00",
                       network=False, busy={"busy": False, "reason": "idle"})
finally:
    PL.orchestrator_busy = real_busy
ck(r.get("skipped") == "orchestrator-busy"
   and r.get("wakeup", {}).get("seconds") == 300,
   "worker در پنجرهٔ شبانه هیچ کاری نمی‌کند", r)

import codal_auto_update as A  # noqa: E402  (مسیرِ dev از قبل در sys.path است)
db = os.path.join(TMP, "lockprobe.db")
conn = sqlite3.connect(db)
conn.execute("CREATE TABLE pipeline_lock (key TEXT PRIMARY KEY, owner TEXT,"
             " heartbeat_at TEXT, note TEXT)")
conn.execute("INSERT INTO pipeline_lock VALUES ('codal_pipeline','x',?, '')",
             (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
conn.commit()
conn.close()
ck(A._pipeline_lock_free(db) is False, "قفلِ تازهٔ pipeline ⇒ آزاد نیست")
conn = sqlite3.connect(db)
conn.execute("UPDATE pipeline_lock SET heartbeat_at=?",
             ((datetime.datetime.now() - datetime.timedelta(seconds=600))
              .strftime("%Y-%m-%d %H:%M:%S"),))
conn.commit()
conn.close()
ck(A._pipeline_lock_free(db) is True, "قفلِ کهنه (۱۰ دقیقه) ⇒ آزاد")

# ── ۶) heartbeat چرخهٔ طولانی و مسیرِ انتظارِ run() ────────────────────────
section("locks: heartbeat refresh + run() pipeline wait")

term_work = tempfile.mkdtemp(prefix="codal_term_", dir=TMP)
with open(os.path.join(term_work, "codal_auto_status.json"), "w",
          encoding="utf-8") as fh:
    json.dump({"stage": "pipeline_busy",
               "updated_at": datetime.datetime.now().isoformat(
                   timespec="seconds")}, fh)
b = PL.orchestrator_busy(work_dir=term_work)
ck(b["busy"] is False,
   "انتظارِ ناموفق (pipeline_busy) ترمینال است، نه ۶ ساعت مشغول", b)
ck("pipeline_busy" not in A._BENIGN_SKIPS,
   "pipeline_busy عمداً benign نیست (merge/publish نشده ⇒ exit 1)")

hb_calls = []
real_hb = PL.lock_heartbeat


def counting_hb(conn, key, owner, note=""):
    hb_calls.append((key, owner))
    return real_hb(conn, key, owner, note=note)


c = fresh_db()
add_notice(c, 5001, "فولاد")
PL.enqueue(c, [(5001, "ms")])
PL.lock_heartbeat = counting_hb
try:
    out = PL.run_cycle(c, "hb-owner", discover=None,
                       scrape=lambda n: ms_row(5001, "فولاد"),
                       now="2026-11-03 10:30:00", instruments=lambda conn: {})
finally:
    PL.lock_heartbeat = real_hb
ck(len(hb_calls) >= 1
   and all(k == "codal_pipeline" and o == "hb-owner" for k, o in hb_calls),
   "چرخه پس از batch و پیش از checkpoint قفل را heartbeat می‌کند", hb_calls)
ck(out.get("error") is None and out.get("done") == 1,
   "چرخهٔ heartbeat بدونِ خطا و با یک کار انجام شد", out)

wait_dir = tempfile.mkdtemp(prefix="codal_wait_", dir=TMP)
wait_db = os.path.join(wait_dir, "market.db")
conn = sqlite3.connect(wait_db)
conn.execute("CREATE TABLE pipeline_lock (key TEXT PRIMARY KEY, owner TEXT,"
             " heartbeat_at TEXT, note TEXT)")
conn.execute("INSERT INTO pipeline_lock VALUES ('codal_pipeline','w',?, '')",
             (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
conn.commit()
conn.close()
wait_staging = os.path.join(wait_dir, "market.db.staging")
orig_paths = (A.STATUS, A.LOCK, A.PAUSE, A.CLIENT_DB_STATUS,
              A.PIPELINE_LOCK_WAIT_S)
A.STATUS = os.path.join(wait_dir, "codal_auto_status.json")
A.LOCK = os.path.join(wait_dir, "codal_auto.lock")
A.PAUSE = os.path.join(wait_dir, "codal_auto_pause")
A.CLIENT_DB_STATUS = os.path.join(wait_dir, "codal_db_status.json")
A.PIPELINE_LOCK_WAIT_S = 0
wait_status = {}
try:
    ck(A._client_download_active() is False, "دانلودِ کلاینت فعال نیست")
    ck(not os.path.exists(A.PAUSE), "فایلِ pause وجود ندارد")
    r = A.run(dry_run=True, db_path=wait_db, staging_dir=wait_staging)
    with open(A.STATUS, "r", encoding="utf-8") as fh:
        wait_status = json.load(fh)
    wait_lock = A.LOCK
finally:
    (A.STATUS, A.LOCK, A.PAUSE, A.CLIENT_DB_STATUS,
     A.PIPELINE_LOCK_WAIT_S) = orig_paths
ck(any("pipeline_busy" in e for e in r["errors"]),
   "run() با قفلِ تازهٔ pipeline ⇒ خطای pipeline_busy", r)
ck(not os.path.exists(wait_staging),
   "هیچ staging DB/backup ساخته نشد", os.listdir(wait_dir))
ck(wait_status.get("stage") == "pipeline_busy",
   "status همان stage ترمینالِ pipeline_busy را ثبت کرد", wait_status)
ck(not os.path.exists(wait_lock), "قفلِ orchestrator آزاد شد")

# ── ۶) تازگی و منشأ ───────────────────────────────────────────────────────
section("freshness: as_of / source / state")
import codal_periods as CP  # noqa: E402

ck(CP.j2g_date("1405/01/01") == "2026-03-21", "نوروز ۱۴۰۵ ⇒ 2026-03-21",
   CP.j2g_date("1405/01/01"))
ck(CP.j2g_date("1405/06/31 12:10:00") == "2026-09-22 12:10:00",
   "تاریخ+ساعت حفظ می‌شود", CP.j2g_date("1405/06/31 12:10:00"))
ck(CP.j2g_date("") is None, "تاریخ خالی ⇒ None")

import api.fundamental as AF  # noqa: E402
from api.fundamental import freshness_of  # noqa: E402

ck(AF._asof_iso("2026-11-03") == "2026-11-03",
   "as_of فقط-روز دست‌نخورده می‌ماند")
ck(AF._asof_iso("2026-09-22 09:00:00") == "2026-09-22T09:00:00+03:30",
   "as_of زمان‌دار ISO-8601 با +03:30 می‌شود")
ck(AF._asof_iso(None) is None and AF._asof_iso("") is None,
   "as_of خالی None می‌ماند (بی‌ساختنِ تاریخ)")

c = fresh_db()
c.execute("INSERT INTO instruments (ins_code, l_val18, l_val30, paper_type)"
          " VALUES ('1','فولاد','فولاد مبارکه',1)")
c.execute("CREATE TABLE market_watch (ins_code TEXT, d_even INTEGER, pcl REAL,"
          " pmn REAL, pmx REAL, py REAL, pf REAL, qtj REAL, qtc REAL, ztt REAL,"
          " pc REAL, eps REAL, pe REAL, ztd REAL, h_even INTEGER,"
          " PRIMARY KEY (ins_code, d_even))")
c.execute("INSERT INTO market_watch (ins_code, d_even) VALUES ('1', 20261103)")
c.execute("INSERT INTO codal_notices (tracing_no, symbol, title, publish_date,"
          " sent_date, fetched_at) VALUES (9100,'فولاد','گزارش فعالیت ماهانه',"
          " '1405/06/31 09:00:00','1405/06/31 09:00:00','2026-10-14 00:00:00')")
c.execute("INSERT INTO monthly_sales (tracing_no, symbol, title, period_end,"
          " year, month, monthly_revenue, ytd_revenue) VALUES"
          " (9100,'فولاد','گزارش', '1405/06/31', 1405, 6, 1000, 6000)")
c.execute("INSERT INTO codal_notices (tracing_no, symbol, title, publish_date,"
          " sent_date, fetched_at) VALUES (9200,'فولاد','صورت‌های مالی',"
          " '1405/05/10 09:00:00','1405/05/10 09:00:00','2026-10-14 00:00:00')")
c.execute("INSERT INTO financial_statements (tracing_no, symbol, title,"
          " period_months, period_end, publish_date, revenue, gross_profit,"
          " is_audited, is_consolidated)"
          " VALUES (9200,'فولاد','صورت‌ها', 12,'1404/12/29','1405/05/10 09:00:00',"
          " 1000, 300, 1, 0)")
PL.dirty_mark(c, "فولاد", "monthly_sales", reason="test")

fr = freshness_of(c, "فولاد")
ck(fr["axes"]["1_growth"]["state"] == "stale",
   "شاخص ۱ dirty ⇒ stale", fr["axes"]["1_growth"])
ck(fr["axes"]["1_growth"]["as_of"] == "2026-09-22T09:00:00+03:30",
   "as_of از publish_date شمسی به میلادیِ ISO با +03:30 تبدیل شد",
   fr["axes"]["1_growth"])
ck(fr["axes"]["1_growth"]["source"] == "monthly_sales"
   and fr["axes"]["1_growth"]["tracing_no"] == 9100,
   "منبع و tracing_no درست است", fr["axes"]["1_growth"])
ck(fr["axes"]["2_eps_trend"]["state"] == "fresh"
   and fr["axes"]["2_eps_trend"]["period_end"] == "1404/12/29",
   "شاخص ۲ از FS حسابرسی‌شده و fresh است", fr["axes"]["2_eps_trend"])
ck(fr["axes"]["5_industry"]["as_of"] == "2026-11-03",
   "شاخص ۵ از روزِ تابلو", fr["axes"]["5_industry"])
ck(fr["as_of"] == "2026-08-01T09:00:00+03:30",
   "as_of کارت = قدیمی‌ترین محورِ بنیادی (۱/۲/۳)، نه بیشینهٔ تابلو‌محور",
   fr["as_of"])
ck(fr["axes"]["2_eps_trend"]["as_of"] == "2026-08-01T09:00:00+03:30",
   "as_of شاخصِ ۲ هم ISO با +03:30 است", fr["axes"]["2_eps_trend"])
ck(fr["axes"]["1_growth"]["reason"] == "test",
   "دلیلِ stale از pipeline_dirty در محور می‌آید", fr["axes"]["1_growth"])

# ── ۶ب) اصلاحاتِ بازبینی: کلیدِ عربیِ dirty، قدمتِ قرنطینه، مرجعِ FS ────────
section("freshness: Arabic dirty key / quarantine recency / FS reference")


def add_monthly(c, tn, sym, pe="1405/06/31"):
    c.execute("INSERT INTO monthly_sales (tracing_no, symbol, title, period_end,"
              " year, month, monthly_revenue, ytd_revenue) VALUES"
              " (?,?,'گزارش',?, 1405, 6, 1000, 6000)", (tn, sym, pe))


def add_quarantine(c, tn, kind, code):
    c.execute("INSERT INTO codal_extracted (tracing_no, kind, ok, tried_at,"
              " state, last_error) VALUES (?,?,0,'2026-10-14 00:00:00',"
              " 'quarantined',?)", (tn, kind, code))


c_ar = fresh_db()
add_notice(c_ar, 9300, "كگل")            # نوشتارِ عربی (ك) در بانک
add_monthly(c_ar, 9300, "كگل")
PL.dirty_mark(c_ar, "كگل", "monthly_sales", reason="awaiting_recompute")
fr_ar = freshness_of(c_ar, "کگل")        # ورودیِ فارسی (ک)
ck(fr_ar["axes"]["1_growth"]["state"] == "stale",
   "کلیدِ عربیِ dirty با ورودیِ فارسی دیده می‌شود", fr_ar["axes"]["1_growth"])
ck(fr_ar["axes"]["1_growth"]["reason"] == "awaiting_recompute",
   "دلیلِ dirty روی محورِ stale می‌نشیند", fr_ar["axes"]["1_growth"])

c_old = fresh_db()
add_notice(c_old, 9400, "خساپا", pub="1405/06/31 09:00:00")
add_monthly(c_old, 9400, "خساپا")
add_notice(c_old, 9401, "خساپا", pub="1405/04/10 09:00:00")
add_quarantine(c_old, 9401, "ms", "negative_revenue:ytd_revenue")
fr_old = freshness_of(c_old, "خساپا")
ck(fr_old["axes"]["1_growth"]["state"] == "fresh",
   "قرنطینهٔ قدیمیِ MS شاخصِ ۱ را آلوده نمی‌کند", fr_old["axes"]["1_growth"])
ck(fr_old["axes"]["4_sales_to_mcap"]["state"] != "quarantined",
   "قرنطینهٔ قدیمیِ MS شاخصِ ۴ را آلوده نمی‌کند",
   fr_old["axes"]["4_sales_to_mcap"])

c_new = fresh_db()
add_notice(c_new, 9410, "وبملت", pub="1405/06/31 09:00:00")
add_monthly(c_new, 9410, "وبملت")
add_notice(c_new, 9411, "وبملت", pub="1405/07/15 10:00:00")
add_quarantine(c_new, 9411, "ms", "negative_revenue:ytd_revenue")
fr_new = freshness_of(c_new, "وبملت")
ck(fr_new["axes"]["1_growth"]["state"] == "quarantined"
   and fr_new["axes"]["4_sales_to_mcap"]["state"] == "quarantined"
   and fr_new["axes"]["1_growth"]["reason"] == "negative_revenue:ytd_revenue",
   "قرنطینهٔ تازه‌تر از انتشارِ canonical ⇒ quarantined",
   {k: fr_new["axes"][k] for k in ("1_growth", "4_sales_to_mcap")})

c_fs = fresh_db()
add_notice(c_fs, 9420, "فولاژ", pub="1405/06/31 09:00:00")
add_monthly(c_fs, 9420, "فولاژ")
add_notice(c_fs, 9421, "فولاژ", pub="1405/07/15 10:00:00")
add_quarantine(c_fs, 9421, "fs", "gross_gt_revenue")
fr_fsq = freshness_of(c_fs, "فولاژ")
ck(fr_fsq["axes"]["1_growth"]["state"] == "fresh"
   and fr_fsq["axes"]["4_sales_to_mcap"]["state"] != "quarantined",
   "ردِ FS شاخص‌های ۱ و ۴ را علامت نمی‌زند",
   {k: fr_fsq["axes"][k] for k in ("1_growth", "4_sales_to_mcap")})
ck(fr_fsq["axes"]["2_eps_trend"]["state"] == "quarantined",
   "FS بیِ canonical ⇒ شاخصِ ۲ قرنطینه", fr_fsq["axes"]["2_eps_trend"])

c_ua = fresh_db()
add_notice(c_ua, 9500, "کحافظ")
c_ua.execute("INSERT INTO financial_statements (tracing_no, symbol, title,"
             " period_months, period_end, publish_date, revenue, gross_profit,"
             " is_audited, is_consolidated)"
             " VALUES (9500,'کحافظ','صورت‌های مالی سالانه', 12,"
             " '1404/12/29','1405/05/10 09:00:00', 1000, 300, 0, 0)")
fr_ua = freshness_of(c_ua, "کحافظ")
ck(fr_ua["axes"]["2_eps_trend"]["state"] == "fresh"
   and fr_ua["axes"]["2_eps_trend"]["tracing_no"] == 9500,
   "FS حسابرسی‌نشدهٔ غیرتلفیقی هم مرجعِ کارت است",
   fr_ua["axes"]["2_eps_trend"])
ck(fr_ua["axes"]["3_gross_margin"]["state"] == "fresh",
   "شاخصِ ۳ هم از همان مرجعِ تنزل‌یافته fresh است", fr_ua["axes"]["3_gross_margin"])

c_fb = fresh_db()
add_monthly(c_fb, 9600, "شپنا")
fr_fb = freshness_of(c_fb, "شپنا")
ck(fr_fb["axes"]["1_growth"]["as_of"] == "2026-09-22",
   "بیِ publish_date، as_of از period_end می‌آید", fr_fb["axes"]["1_growth"])

bare = sqlite3.connect(":memory:")
bare.row_factory = sqlite3.Row
fr_bare = freshness_of(bare, "فولاد")
ck(len(fr_bare["axes"]) == 5
   and all(a["state"] == "missing" for a in fr_bare["axes"].values())
   and fr_bare["as_of"] is None,
   "بانکِ بیِ monthly_sales/FS ⇒ همه missing، بیِ استثنا", fr_bare)

from api.fundamental import router as FR  # noqa: E402
paths = [r.path for r in FR.routes]
ck(paths.index("/api/fundamental/freshness") < paths.index("/api/fundamental/{symbol}"),
   "route تازگی پیش از مسیرِ پویا ثبت شده است", paths)

# ── ۷) وضعیت، پرچم شکاف و بودجهٔ روزانه ─────────────────────────────────
section("status: gap flag / daily budget / publication")
c = fresh_db()
for i in range(240):
    add_notice(c, 5000 + i, "نماد%d" % i,
               pub="1405/07/20 %02d:10:00" % (9 + (i % 3)))
h = PL.health(c)
ck("publication" in h and "network_gap_s" in h["publication"],
   "health پنجره و gap را گزارش می‌کند", h.get("publication"))
ck("daily_requests" in h and "gap_flag" in h
   and "incomplete_streak" in h and "last_new_notice_at" in h,
   "کلیدهای تازهٔ status حاضرند", sorted(h.keys()))
ck("quarantined" in h.get("queue", {}),
   "health قرنطینه را در queue نگه می‌دارد", h.get("queue"))
ck(h.get("last_new_notice_at") == "2026-11-03 00:00:00"
   and h.get("gap_flag") is False and h.get("incomplete_streak") == 0,
   "مقدارهای تازهٔ status از خود بانک می‌آیند",
   {k: h.get(k) for k in ("last_new_notice_at", "gap_flag",
                          "incomplete_streak")})

c2 = fresh_db()
blocked = PL.discover_auto(c2, fetch=lambda *a, **k: None,
                           now="2026-11-03 20:00:00")
ck(blocked.get("complete") is False and blocked.get("blocked") is True,
   "فیدِ بی‌پاسخ ⇒ پاسِ ناقص/بلاک اعلام می‌شود", blocked)
ck(blocked.get("budget_exhausted") is False,
   "بلاکِ شبکه با «بودجهٔ صفحه» قاطی نمی‌شود",
   blocked.get("budget_exhausted"))
ck(PL.cursor_get(c2, "notice_gap_flag") == "1",
   "پاسِ ناقص ⇒ پرچم شکاف روشن")
ck(int(PL.cursor_get(c2, "notice_incomplete_streak", "0") or 0) >= 1,
   "شمارندهٔ شکافِ پیاپی افزایش یافت")
blocked2 = PL.discover_auto(c2, fetch=lambda *a, **k: None,
                            now="2026-11-03 20:10:00")
ck(int(PL.cursor_get(c2, "notice_incomplete_streak") or 0) == 2,
   "پاسِ ناقصِ دوم شمارندهٔ پیاپی را یکی بالا می‌برد", blocked2)
real_dn = CF.discover_notices
CF.discover_notices = lambda *a, **k: {"found": 0, "items": [], "floors": {},
                                       "complete": True, "blocked": False,
                                       "pages": 1, "newest": None}
try:
    PL.discover_auto(c2, fetch=lambda *a, **k: None,
                     now="2026-11-03 20:20:00")
finally:
    CF.discover_notices = real_dn
ck(PL.cursor_get(c2, "notice_gap_flag") == "0"
   and int(PL.cursor_get(c2, "notice_incomplete_streak") or 0) == 0,
   "کشفِ کامل ⇒ پرچم و شمارندهٔ شکاف صفر می‌شوند",
   (PL.cursor_get(c2, "notice_gap_flag"),
    PL.cursor_get(c2, "notice_incomplete_streak")))

c3 = fresh_db()
real_disc = PL.discover_auto
PL.discover_auto = lambda *a, **k: {"found": 0, "enqueued": 0, "items": [],
                                    "floors": {}, "complete": True,
                                    "blocked": False, "pages": 2}
try:
    out = PL.run_cycle(c3, "test", discover=PL.discover_auto,
                       scrape=lambda n: (None, None, "empty"),
                       now="2026-11-03 20:00:00", instruments=lambda conn: {})
finally:
    PL.discover_auto = real_disc
ck(out.get("pages") == 2, "run_cycle تعداد صفحه‌های فید را گزارش می‌کند", out)

# ── ۷ب) بودجهٔ روزانهٔ درخواست در worker_once ─────────────────────────────
section("worker: daily request budget")
c5 = fresh_db()
real_gate = PL.offline_gate
real_orch = PL.orchestrator_busy
real_cap = PL.DAILY_REQUEST_CAP
PL.discover_auto = lambda *a, **k: {"found": 0, "enqueued": 0, "items": [],
                                    "floors": {}, "complete": True,
                                    "blocked": False, "pages": 2}
PL.offline_gate = lambda: False
PL.orchestrator_busy = lambda *a, **k: {"busy": False, "reason": ""}
PL.DAILY_REQUEST_CAP = 4
try:
    r1 = PL.worker_once(conn=c5, now="2026-11-03 20:00:00", network=None,
                        busy={"busy": False, "reason": "idle"})
    r2 = PL.worker_once(conn=c5, now="2026-11-03 20:10:00", network=True,
                        busy={"busy": False, "reason": "idle"})
    r3 = PL.worker_once(conn=c5, now="2026-11-03 20:20:00", network=True,
                        force=True, busy={"busy": False, "reason": "idle"})
    r4 = PL.worker_once(conn=c5, now="2026-11-04 20:00:00", network=None,
                        busy={"busy": False, "reason": "idle"})
finally:
    PL.discover_auto = real_disc
    PL.offline_gate = real_gate
    PL.orchestrator_busy = real_orch
    PL.DAILY_REQUEST_CAP = real_cap
ck(r1.get("network") is True and r1.get("pages") == 2
   and (r1.get("daily_requests") or {}).get("count") == 2,
   "پاسِ شبکه صفحه‌های فید را در بودجهٔ روز می‌نویسد",
   {k: r1.get(k) for k in ("network", "pages", "daily_requests")})
ck((r2.get("daily_requests") or {}).get("count") == 4,
   "بودجهٔ روز انباشته می‌شود", r2.get("daily_requests"))
ck(r3.get("network") is False and r3.get("pages") == 0
   and (r3.get("daily_requests") or {}).get("count") == 4,
   "بودجهٔ تمام‌شده ⇒ پاسِ شبکه حتی با network=True متوقف می‌شود",
   {k: r3.get(k) for k in ("network", "pages", "daily_requests")})
ck(r4.get("network") is True
   and (r4.get("daily_requests") or {}).get("day") == "2026-11-04"
   and (r4.get("daily_requests") or {}).get("count") == 2,
   "روزِ تازه ⇒ بودجه از صفر شروع می‌شود", r4.get("daily_requests"))

# ── ۷ج) بازبینی: gapِ پویا در status_payload و فیلدهایِ lastِ worker ──────
section("status_payload: dynamic gap from health publication")
c6 = fresh_db()
PL.cursor_set(c6, PL.CURSOR_LAST_NETWORK, "2026-11-03 10:00:00")
real_gap = PL.current_network_gap
stub_pub = {"windows": [list(w) for w in CAD.DEFAULT_WINDOWS],
            "source": "default", "samples": 0,
            "labels": CAD.window_labels(CAD.DEFAULT_WINDOWS),
            "inside_window": True, "network_gap_s": 777, "enabled": True}
PL.current_network_gap = lambda conn, now=None, jitter=True, cache_write=True: (
    777, dict(stub_pub))
try:
    sp = PL.status_payload(c6, now="2026-11-03 10:00:00")
finally:
    PL.current_network_gap = real_gap
ck("network_gap_s" in sp.get("publication", {}),
   "status_payload پنجرهٔ انتشار را گزارش می‌کند", sp.get("publication"))
ck((sp.get("cadence") or {}).get("seconds") == 777
   and (sp.get("cadence") or {}).get("reason") == "discovery-gap",
   "status_payload همان gapِ پویای worker را به کار می‌برد", sp.get("cadence"))

section("worker_status: new cycle fields reach last")
real_wo = PL.worker_once
PL.worker_once = lambda **k: {"skipped": None, "touched": ["فولاد"],
                              "invalidated_symbols": 2,
                              "recalc_invalidate_only": True,
                              "wakeup": {"seconds": 60}}
PL._WORKER["last"] = None
try:
    PL.start_worker(":memory:", owner="last-fields",
                    conn_factory=lambda: None)
    for _ in range(100):
        if PL._WORKER.get("last"):
            break
        time.sleep(0.02)
finally:
    PL.stop_worker(timeout_s=2)
    PL.worker_once = real_wo
last = PL.worker_status().get("last") or {}
ck({"touched", "invalidated_symbols", "recalc_invalidate_only"} <= set(last),
   "فیلدهای تازهٔ چرخه در worker_status می‌نشینند", last)
ck(last.get("invalidated_symbols") == 2 and last.get("touched") == ["فولاد"],
   "مقدارهای last همان خروجی چرخه‌اند", last)

# ── ۷د) بازبینی: cache_invalidated باطل‌سازیِ فوری را هم می‌شمارد ──────────
section("run_cycle: cache_invalidated includes immediate invalidation")
c7 = fresh_db()
add_notice(c7, 7001, "فولاد")
PL.enqueue(c7, [(7001, "ms")])
real_inv = PL._invalidate_materialized
PL._invalidate_materialized = lambda conn, symbols: len(symbols)
try:
    out = PL.run_cycle(
        c7, "acct", discover=None,
        scrape=lambda n: ms_row(7001, "فولاد"),
        recalc=lambda conn, dirty: {"recomputed": len(dirty),
                                    "cache_invalidated": 2},
        now="2026-11-03 20:00:00", instruments=lambda conn: {})
finally:
    PL._invalidate_materialized = real_inv
ck(out.get("invalidated_symbols") == 1 and out.get("cache_invalidated") == 3,
   "cache_invalidated باطل‌سازیِ فوری و محاسبه را با هم می‌شمارد", out)
row = c7.execute("SELECT cache_invalidated FROM pipeline_runs ORDER BY id DESC"
                 " LIMIT 1").fetchone()
ck(row is not None and int(row[0] or 0) == 3,
   "pipeline_runs هم همان عددِ کامل را ثبت می‌کند",
   tuple(row) if row is not None else None)

# ── ۷هـ) بازبینی: skipِ قفل بودجه نمی‌خورد و status نوشتن ندارد ─────────────
section("worker: lock-skip does not charge daily budget")
c8 = fresh_db()
PL.cursor_set(c8, PL.DAILY_REQUEST_CURSOR,
              json.dumps({"day": "2026-11-03", "count": 3}))
real_rc8 = PL.run_cycle
real_gate8 = PL.offline_gate
real_orch8 = PL.orchestrator_busy
PL.run_cycle = lambda *a, **k: {"skipped": "locked", "run_id": None, "pages": 0}
PL.offline_gate = lambda: False
PL.orchestrator_busy = lambda *a, **k: {"busy": False, "reason": ""}
try:
    r8 = PL.worker_once(conn=c8, now="2026-11-03 20:00:00", network=True,
                        busy={"busy": False, "reason": "idle"})
finally:
    PL.run_cycle = real_rc8
    PL.offline_gate = real_gate8
    PL.orchestrator_busy = real_orch8
stored8 = json.loads(PL.cursor_get(c8, PL.DAILY_REQUEST_CURSOR) or "{}")
ck(r8.get("skipped") == "locked"
   and (r8.get("daily_requests") or {}).get("count") == 3
   and stored8.get("count") == 3,
   "skipِ قفل (بیِ run_id/صفحه) سهمِ روز را کم نمی‌کند",
   {"skipped": r8.get("skipped"), "daily_requests": r8.get("daily_requests"),
    "stored": stored8})

section("health: read-only publication cache")
c9 = fresh_db()
add_notice(c9, 7100, "فولاد")
h9 = PL.health(c9)
ck(PL.cursor_get(c9, PL.PUB_WINDOWS_CURSOR) is None,
   "health کشِ pub_windows_v1 را نمی‌نویسد",
   PL.cursor_get(c9, PL.PUB_WINDOWS_CURSOR))
ck((h9.get("publication") or {}).get("network_gap_s") is not None,
   "health بازهم network_gap_s را گزارش می‌کند", h9.get("publication"))

section("hardening: corrupt cursors never crash health/worker")
c10 = fresh_db()
PL.cursor_set(c10, "notice_incomplete_streak", "not-a-number")
PL.cursor_set(c10, PL.DAILY_REQUEST_CURSOR,
              json.dumps({"day": "2026-11-03", "count": "many"}))
h10 = PL.health(c10)
ck(h10.get("incomplete_streak") == 0
   and (h10.get("daily_requests") or {}).get("count") == 0,
   "cursorِ غیرعددی در health ایمن صفر می‌شود",
   {k: h10.get(k) for k in ("incomplete_streak", "daily_requests")})
real_orch10 = PL.orchestrator_busy
real_gate10 = PL.offline_gate
PL.offline_gate = lambda: False
PL.orchestrator_busy = lambda *a, **k: {"busy": False, "reason": ""}
try:
    r10 = PL.worker_once(conn=c10, now="2026-11-03 20:00:00", network=False,
                         busy={"busy": False, "reason": "idle"})
finally:
    PL.offline_gate = real_gate10
    PL.orchestrator_busy = real_orch10
ck(r10.get("skipped") == "nothing-to-do",
   "cursorِ خراب بودجهٔ worker را نمی‌ترکاند", r10)

section("worker: budget-exhausted skip is distinct")
c11 = fresh_db()
PL.cursor_set(c11, PL.DAILY_REQUEST_CURSOR,
              json.dumps({"day": "2026-11-03", "count": PL.DAILY_REQUEST_CAP}))
# قفلِ شبانهٔ واقعی در ریشهٔ مخزن نباید این تست را شکننده کند؛ مثلِ بقیهٔ
# تست‌هایِ worker، orchestrator_busy خنثی می‌شود.
real_orch11 = PL.orchestrator_busy
PL.orchestrator_busy = lambda *a, **k: {"busy": False, "reason": ""}
try:
    r11 = PL.worker_once(conn=c11, now="2026-11-03 20:00:00", network=None,
                         busy={"busy": False, "reason": "idle"})
finally:
    PL.orchestrator_busy = real_orch11
wk11 = r11.get("wakeup") or {}
ck(r11.get("skipped") == "budget-exhausted"
   and (r11.get("daily_requests") or {}).get("count") == PL.DAILY_REQUEST_CAP
   and wk11.get("seconds") == 4 * 3600
   and wk11.get("at") == "2026-11-04 00:00:00",
   "بودجهٔ تمام‌شده ⇒ skipِ متمایز با بیدارباش تا نیمه‌شب",
   {k: r11.get(k) for k in ("skipped", "daily_requests", "wakeup")})

# ── ۸) موجِ رفعِ بازبینیِ نهایی: بودجه/صفحه، breaker و پاسِ عمیق ─────────────
section("fix-wave: budget arithmetic / quiet+deep pages / breaker")

ck(PL.DAILY_REQUEST_CAP == 400,
   "سقفِ روزانهٔ درخواست ۴۰۰ است", PL.DAILY_REQUEST_CAP)
ck(4 * (12 * 6) + 4 * 8 <= PL.DAILY_REQUEST_CAP,
   "پنجرهٔ ۱۲ساعته با ۶۰۰ثانیه و ۴صفحه/پاس + حاشیه در سقفِ ۴۰۰ جا می‌شود",
   4 * (12 * 6) + 4 * 8)
ck(PL.PAGES_PER_CAT == 2 and PL.DEEP_PAGES_PER_CAT == 3,
   "صفحهٔ هر دسته: عادی ۲، عمیق ۳",
   (PL.PAGES_PER_CAT, PL.DEEP_PAGES_PER_CAT))


def _feed_letter(tn, sym):
    return {"TracingNo": tn, "Symbol": sym, "CompanyName": sym,
            "Title": "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۵/۰۶/۳۱",
            "LetterCode": "1", "PublishDateTime": "1405/07/20 10:00:00",
            "SentDateTime": "1405/07/20 10:00:00",
            "Url": "/L/Detail/%d" % tn, "PdfUrl": "uploads/a.pdf",
            "ExcelUrl": ""}


class _PagedFeed:
    def __init__(self, pages):
        self.pages = pages

    def __call__(self, session, page, query):
        lst = self.pages.get(str(query.get("Category"))) or []
        i = int(page) - 1
        return lst[i] if 0 <= i < len(lst) else []


def _five_pages(base):
    return [[_feed_letter(base + i, "نماد%d" % i)] for i in range(1, 6)]


feed_pages = {"1": _five_pages(20000), "3": _five_pages(21000)}
c_b = fresh_db()
r_quiet = PL.discover_auto(c_b, fetch=_PagedFeed(feed_pages),
                           now="2026-11-03 20:00:00")
ck(r_quiet["pages"] == 4,
   "پاسِ آرام ۲ صفحه/دسته = ۴ صفحه (نه ۶)", r_quiet["pages"])
ck(r_quiet.get("budget_exhausted") is True
   and r_quiet.get("blocked") is False,
   "فیدِ ۵صفحه‌ای با بودجهٔ ۲ ⇒ ناقص از نوعِ «بودجهٔ صفحه»، نه بلاک",
   {k: r_quiet.get(k) for k in ("budget_exhausted", "blocked", "complete")})
ck(PL.cursor_get(c_b, "notice_deep_pass") == "1",
   "بودجهٔ صفحه پیش از مرزِ کهنه ⇒ پرچمِ پاسِ عمیق روشن",
   PL.cursor_get(c_b, "notice_deep_pass"))
r_deep = PL.discover_auto(c_b, fetch=_PagedFeed(feed_pages),
                          now="2026-11-03 20:10:00")
ck(r_deep["pages"] == 6,
   "پاسِ عمیق ۳ صفحه/دسته = ۶ صفحه", r_deep["pages"])

real_cfd = CF.discover_notices
CF.discover_notices = lambda *a, **k: {"found": 0, "items": [], "floors": {},
                                       "complete": True, "blocked": False,
                                       "pages": 2, "newest": None}
try:
    PL.discover_auto(c_b, now="2026-11-03 20:20:00")
finally:
    CF.discover_notices = real_cfd
ck(PL.cursor_get(c_b, "notice_deep_pass") == "0",
   "پاسِ کامل پرچمِ عمیق را پاک می‌کند",
   PL.cursor_get(c_b, "notice_deep_pass"))

c_br = fresh_db()
for i in range(240):
    add_notice(c_br, 30000 + i, "ب%d" % i,
               pub="1405/07/20 %02d:10:00" % (9 + (i % 3)))
PL.cursor_set(c_br, "notice_incomplete_streak", "2")
gap2, info2 = PL.current_network_gap(c_br, now="2026-11-03 10:00:00",
                                     jitter=False)
ck(gap2 == 600 and info2.get("breaker") is False,
   "streak=۲ هنوز کادنسِ عادی ۶۰۰ثانیه", (gap2, info2.get("breaker")))
PL.cursor_set(c_br, "notice_incomplete_streak", "3")
gap3, info3 = PL.current_network_gap(c_br, now="2026-11-03 10:00:00",
                                     jitter=False)
ck(gap3 == 1800 and info3.get("breaker") is True,
   "streak=۳ ⇒ breaker: gap پایه به ۱۸۰۰ثانیه می‌رسد", gap3)
PL.cursor_set(c_br, "notice_incomplete_streak", "9")
gap9, _ = PL.current_network_gap(c_br, now="2026-11-03 10:00:00", jitter=False)
ck(gap9 == 10800, "streak بالا به سقفِ ۳ ساعت می‌رسد", gap9)
gapj, _ = PL.current_network_gap(c_br, now="2026-11-03 10:00:00", jitter=True)
ck(10740 <= gapj <= 10800,
   "jitter پس از breaker می‌نشیند و به سقف clamp می‌شود", gapj)
CF.discover_notices = lambda *a, **k: {"found": 0, "items": [], "floors": {},
                                       "complete": True, "blocked": False,
                                       "pages": 2, "newest": None}
try:
    PL.discover_auto(c_br, now="2026-11-03 10:05:00")
finally:
    CF.discover_notices = real_cfd
gap_after, _ = PL.current_network_gap(c_br, now="2026-11-03 10:00:00",
                                      jitter=False)
ck(PL.cursor_get(c_br, "notice_incomplete_streak") == "0"
   and gap_after == 600,
   "پاسِ کامل شمارنده و breaker را صفر می‌کند (بازگشت به ۶۰۰ثانیه)",
   (PL.cursor_get(c_br, "notice_incomplete_streak"), gap_after))

# بودجهٔ صفحه ≠ بلاکِ شبکه: پاسِ ناقصِ بودجه‌ای نباید شمارندهٔ breaker را
# بالا ببرد (وگرنه در بستِ آخرِ ماه gap روی ۳ ساعت latch می‌شود).
section("fix-wave: budget-exhausted pass does not latch the breaker")
c_bx = fresh_db()
real_cfx = CF.discover_notices


def _fake_discover(**over):
    base = {"found": 0, "items": [], "floors": {}, "complete": False,
            "blocked": False, "budget_exhausted": False, "pages": 4,
            "newest": None}
    base.update(over)
    return lambda *a, **k: dict(base)


try:
    CF.discover_notices = _fake_discover(complete=False, blocked=False,
                                         budget_exhausted=True)
    rb1 = PL.discover_auto(c_bx, now="2026-11-03 10:00:00")
    rb2 = PL.discover_auto(c_bx, now="2026-11-03 10:10:00")
    streak_bud = PL.cursor_get(c_bx, "notice_incomplete_streak", "0")
    flag_bud = PL.cursor_get(c_bx, "notice_gap_flag")
    deep_bud = PL.cursor_get(c_bx, "notice_deep_pass")
    gap_bud, info_bud = PL.current_network_gap(
        c_bx, now="2026-11-03 10:00:00", jitter=False)
    CF.discover_notices = _fake_discover(complete=False, blocked=True)
    PL.discover_auto(c_bx, now="2026-11-03 10:20:00")
    streak_blk = PL.cursor_get(c_bx, "notice_incomplete_streak")
    CF.discover_notices = _fake_discover(complete=True)
    PL.discover_auto(c_bx, now="2026-11-03 10:30:00")
    streak_done = PL.cursor_get(c_bx, "notice_incomplete_streak", "0")
    flag_done = PL.cursor_get(c_bx, "notice_gap_flag")
    deep_done = PL.cursor_get(c_bx, "notice_deep_pass")
finally:
    CF.discover_notices = real_cfx
ck(rb1.get("budget_exhausted") is True
   and rb2.get("budget_exhausted") is True,
   "دو پاسِ پیاپیِ ناقصِ بودجه‌ای هر دو budget_exhausted برمی‌گردانند",
   (rb1.get("budget_exhausted"), rb2.get("budget_exhausted")))
ck(streak_bud == "0",
   "پاسِ ناقصِ بودجه‌ای شمارندهٔ breaker را بالا نمی‌برد", streak_bud)
ck(flag_bud == "1" and deep_bud == "1",
   "پرچمِ شکاف و پاسِ عمیق رویِ ناقصِ بودجه‌ای روشن می‌مانند",
   (flag_bud, deep_bud))
ck(gap_bud == 600 and info_bud.get("breaker") is False,
   "gap زیرِ breaker می‌ماند (۶۰۰ثانیه) و latch نمی‌شود", gap_bud)
ck(streak_blk == "1",
   "پاسِ بلاکِ شبکه شمارندهٔ breaker را یکی بالا می‌برد", streak_blk)
ck(streak_done == "0" and flag_done == "0" and deep_done == "0",
   "پاسِ کامل هر دو شمارنده و پرچمِ عمیق را صفر می‌کند",
   (streak_done, flag_done, deep_done))

# ── ۸ب) آزادسازیِ قرنطینه (تابع + CLI، بی‌شبکه) ─────────────────────────────
section("fix-wave: quarantine release + CLI")
c_rel = fresh_db()
add_notice(c_rel, 8101, "فولاد")
c_rel.execute("INSERT INTO codal_extracted (tracing_no, kind, ok, tried_at,"
              " state, attempts, updated_at, last_error, error_kind)"
              " VALUES (8101,'fs',0,'2026-11-03 10:00:00','quarantined',1,"
              " '2026-11-03 10:00:00','negative_revenue:revenue','validation')")
n_rel = PL.release_quarantine(c_rel)
row_rel = c_rel.execute(
    "SELECT state, error_kind, next_attempt_at, claim_owner, claimed_at"
    " FROM codal_extracted WHERE tracing_no=8101").fetchone()
ck(n_rel == 1 and row_rel[0] == "queued" and row_rel[1] == "requeued",
   "آزادسازیِ قرنطینه ⇒ queued با error_kind=requeued", tuple(row_rel))
ck(row_rel[2] is None and row_rel[3] is None and row_rel[4] is None,
   "پاک‌شدنِ next_attempt_at/claim_owner/claimed_at", tuple(row_rel))
claimed_rel = PL.claim(c_rel, "rel-owner", limit=1,
                       now="2026-11-03 10:05:00")
ck([int(x[0]) for x in claimed_rel] == [8101],
   "ردیفِ آزادشده همان‌جا claim می‌شود", claimed_rel)

c_rel2 = fresh_db()
for _tn in (8201, 8202):
    c_rel2.execute("INSERT INTO codal_extracted (tracing_no, kind, ok, tried_at,"
                   " state, attempts, updated_at, last_error, error_kind)"
                   " VALUES (?, 'fs', 0, '2026-11-03 10:00:00', 'quarantined',"
                   " 1, '2026-11-03 10:00:00', 'gross_gt_revenue', 'validation')",
                   (_tn,))
ck(PL.release_quarantine(c_rel2, tracing_nos=[8202]) == 1,
   "آزادسازیِ انتخابی فقط tracing_no خواسته‌شده را برمی‌گرداند")
states_rel = dict(c_rel2.execute(
    "SELECT tracing_no, state FROM codal_extracted").fetchall())
ck(states_rel == {8201: "quarantined", 8202: "queued"},
   "بقیهٔ ردیف‌هایِ قرنطینه دست‌نخورده می‌مانند", states_rel)
ck(PL.release_quarantine(c_rel2, tracing_nos=[999999]) == 0,
   "tracing_no ناموجود صفر ردیف آزاد می‌کند")

rel_db = os.path.join(TMP, "release_cli.db")
rc = sqlite3.connect(rel_db)
rc.row_factory = sqlite3.Row
CF.create_schema(rc)
CF.migrate_schema(rc)
PL.ensure_schema(rc)
for _tn in (8301, 8302):
    rc.execute("INSERT INTO codal_extracted (tracing_no, kind, ok, tried_at,"
               " state, attempts, updated_at, last_error, error_kind)"
               " VALUES (?, 'fs', 0, '2026-11-03 10:00:00', 'quarantined',"
               " 1, '2026-11-03 10:00:00', 'gross_gt_revenue', 'validation')",
               (_tn,))
rc.commit()
rc.close()
env_cli = dict(os.environ, PYTHONIOENCODING="utf-8", BORS_CODAL_OFFLINE="1")
r_cli = subprocess.run(
    [sys.executable, os.path.join(ROOT, "codal_pipeline.py"), "--db", rel_db,
     "--json", "--release-quarantine", "--tracing-no", "8302"],
    capture_output=True, text=True, env=env_cli, timeout=180, cwd=ROOT)
lines_cli = [x for x in (r_cli.stdout or "").splitlines() if x.startswith("{")]
payload_cli = json.loads(lines_cli[-1]) if lines_cli else {}
rc2 = sqlite3.connect(rel_db)
states_cli = dict(rc2.execute(
    "SELECT tracing_no, state FROM codal_extracted").fetchall())
rc2.close()
ck(r_cli.returncode == 0 and payload_cli.get("released") == 1
   and states_cli == {8301: "quarantined", 8302: "queued"},
   "CLI --release-quarantine --tracing-no بی‌شبکه همان کار را می‌کند",
   {"rc": r_cli.returncode, "payload": payload_cli, "states": states_cli,
    "err": (r_cli.stderr or "")[-160:]})

# ── ۸ج) بازبینیِ TOCTOU قفل در run_cycle ────────────────────────────────────
section("fix-wave: run_cycle lock TOCTOU recheck")
c_m2 = fresh_db()
real_orch_m2 = PL.orchestrator_busy
PL.orchestrator_busy = lambda *a, **k: {"busy": True, "reason": "lock-fresh",
                                        "stage": "fetching"}
try:
    out_m2 = PL.run_cycle(c_m2, "m2", now="2026-11-03 10:30:00",
                          instruments=None)
finally:
    PL.orchestrator_busy = real_orch_m2
ck(out_m2.get("skipped") == "orchestrator-busy"
   and out_m2.get("run_id") is None,
   "run_cycle پس از گرفتنِ قفل، مشغول‌بودنِ خطِ شبانه را دوباره می‌بیند",
   out_m2)
ck(PL.lock_state(c_m2, "codal_pipeline")["held"] is False,
   "قفل در مسیرِ orchestrator-busy آزاد می‌شود")
ck(c_m2.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0] == 0,
   "هیچ چرخهٔ ساختگی ثبت نمی‌شود")

# ── ۸د) کشِ ۶۰ثانیه‌ایِ route تازگیِ دسته‌ای ─────────────────────────────────
section("fix-wave: freshness bulk cache (60s)")
calls_fo = []
real_fo = AF.freshness_of
AF._FRESHNESS_CACHE.clear()
AF.freshness_of = lambda conn, s, now=None: (calls_fo.append(s),
                                             {"symbol": s})[1]
try:
    p1 = AF.freshness_bulk(c_m2, ["الف", "ب"], now=1000.0)
    p2 = AF.freshness_bulk(c_m2, ["ب", "الف"], now=1030.0)
    p3 = AF.freshness_bulk(c_m2, ["الف", "ب"], now=1061.0)
finally:
    AF.freshness_of = real_fo
    AF._FRESHNESS_CACHE.clear()
ck(len(calls_fo) == 4 and p2 is p1 and p3 is not p1,
   "دو فراخوانیِ درونِ ۶۰ثانیه یک محاسبه؛ پس از TTL دوباره محاسبه",
   (calls_fo, p2 is p1, p3 is p1))
ck(p1.get("count") == 2
   and [x["symbol"] for x in p1["items"]] == ["الف", "ب"],
   "payload و ترتیبِ درخواست حفظ می‌شود", p1)

calls_fo.clear()
AF.freshness_of = lambda conn, s, now=None: (calls_fo.append(s),
                                             {"symbol": s})[1]
try:
    for _i in range(AF.FRESHNESS_CACHE_MAX + 1):
        AF.freshness_bulk(c_m2, ["نماد%d" % _i], now=2000.0 + _i)
    size_cap = len(AF._FRESHNESS_CACHE)
finally:
    AF.freshness_of = real_fo
    AF._FRESHNESS_CACHE.clear()
ck(size_cap == 1,
   "کشِ freshness پس از عبور از سقفِ ۳۲ symbol-set تخلیه می‌شود",
   size_cap)

# ── ۸هـ) debounceِ ۳۰۰ثانیه‌ایِ dropِ payload اسکرینر ───────────────────────
section("fix-wave: screener payload drop debounce (300s)")
import api.screener as SCR  # noqa: E402

c_sc = fresh_db()
for _tn, _sym in ((8401, "فولاد"), (8402, "خودرو"), (8403, "شپنا")):
    add_notice(c_sc, _tn, _sym)
PL.enqueue(c_sc, [(8401, "ms"), (8402, "ms"), (8403, "ms")])
drops_sc, inv_sc = [], []
real_si = SCR.invalidate_screener_cache
real_inv_sc = PL._invalidate_materialized
SCR.invalidate_screener_cache = lambda **kw: drops_sc.append(dict(kw))
PL._invalidate_materialized = lambda conn, symbols: (
    inv_sc.append(list(symbols)), len(symbols))[1]
try:
    for _i, _now in enumerate(("2026-11-03 20:00:00", "2026-11-03 20:03:00",
                               "2026-11-03 20:05:30")):
        PL.run_cycle(c_sc, "sc%d" % _i, discover=None,
                     scrape=lambda n: ms_row(n[0], n[1]), budget=1,
                     now=_now, instruments=None)
finally:
    SCR.invalidate_screener_cache = real_si
    PL._invalidate_materialized = real_inv_sc
ck(len(inv_sc) == 3,
   "باطل‌سازیِ fts_results هر سه چرخه بی‌تأخیر اجرا شد", inv_sc)
ck(len(drops_sc) == 2,
   "dropِ payload اسکرینر: دو چرخهٔ نخست در ۳۰۰ثانیه یک‌بار، چرخهٔ سوم دوباره",
   drops_sc[-3:])
ck(PL.cursor_get(c_sc, PL.CURSOR_SCREENER_DROP) is not None,
   "زمانِ آخرین drop در pipeline_cursor ماندگار است",
   PL.cursor_get(c_sc, PL.CURSOR_SCREENER_DROP))

# ── ۸) گیتِ زندهٔ اختیاری (فقط با --live و تأییدِ مالک؛ نه بخشی از CI) ──────
if LIVE:
    section("live: read-only CODAL page (no writes)")
    saved_polite = CF.POLITE
    saved_rotate = CF.rotate_ip_via_adb
    saved_progress = CF.write_progress
    CF.set_polite(True)                            # بدونِ ADB: فقط مکثِ امن
    # حتی مسیرِ 429/بنِ WAF هم نباید ADB را توگل یا sync_status را بنویسد؛
    # `_trigger_backoff` مستقل از POLITE چرخش می‌زند و شاخهٔ بنِ پایدار
    # write_progress را بی‌توجه به quiet صدا می‌زند.
    CF.rotate_ip_via_adb = lambda *a, **k: False
    CF.write_progress = lambda *a, **k: None
    try:
        try:
            sess = CF.make_session()
            try:
                letters = CF.fetch_page(
                    sess, 1, CF.feed_query("3", 1, "1405/01/01"), quiet=True)
            finally:
                sess.close()
        except Exception as exc:
            print("  SKIP live probe: %s" % exc)
        else:
            if letters is None:
                print("  SKIP live probe: blocked/no response")
            else:
                ck(isinstance(letters, list) and len(letters) > 0,
                   "فید کدال یک صفحهٔ غیرخالی برگرداند (بی‌نوشتن)")
    finally:
        CF.set_polite(saved_polite)
        CF.rotate_ip_via_adb = saved_rotate
        CF.write_progress = saved_progress

failed = CHECKS.count(False)
print("\n%d passed / %d failed" % (CHECKS.count(True), failed))
try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass
sys.exit(1 if failed else 0)
