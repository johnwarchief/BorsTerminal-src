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

from api.fundamental import freshness_of  # noqa: E402

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
c.execute("INSERT INTO financial_statements (tracing_no, symbol, title, period_end,"
          " publish_date, revenue, gross_profit, is_audited, is_consolidated)"
          " VALUES (9200,'فولاد','صورت‌ها','1404/12/29','1405/05/10 09:00:00',"
          " 1000, 300, 1, 0)")
PL.dirty_mark(c, "فولاد", "monthly_sales", reason="test")

fr = freshness_of(c, "فولاد")
ck(fr["axes"]["1_growth"]["state"] == "stale",
   "شاخص ۱ dirty ⇒ stale", fr["axes"]["1_growth"])
ck(fr["axes"]["1_growth"]["as_of"] == "2026-09-22 09:00:00",
   "as_of از publish_date شمسی به میلادی تبدیل شد", fr["axes"]["1_growth"])
ck(fr["axes"]["1_growth"]["source"] == "monthly_sales"
   and fr["axes"]["1_growth"]["tracing_no"] == 9100,
   "منبع و tracing_no درست است", fr["axes"]["1_growth"])
ck(fr["axes"]["2_eps_trend"]["state"] == "fresh"
   and fr["axes"]["2_eps_trend"]["period_end"] == "1404/12/29",
   "شاخص ۲ از FS حسابرسی‌شده و fresh است", fr["axes"]["2_eps_trend"])
ck(fr["axes"]["5_industry"]["as_of"] == "2026-11-03",
   "شاخص ۵ از روزِ تابلو", fr["axes"]["5_industry"])
ck(fr["as_of"] == "2026-11-03", "as_of کارت بیشینهٔ محورهاست", fr["as_of"])

from api.fundamental import router as FR  # noqa: E402
paths = [r.path for r in FR.routes]
ck(paths.index("/api/fundamental/freshness") < paths.index("/api/fundamental/{symbol}"),
   "route تازگی پیش از مسیرِ پویا ثبت شده است", paths)
