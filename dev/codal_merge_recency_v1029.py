#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_merge_recency_v1029.py — اسنپ‌شاتِ کهنه نباید دادهٔ تازه را ببَلعد.

چرا (CODAL-MERGE-1): دکمهٔ «بروزرسانی دیتابیس کدال» `codal.db.lzma` را از
releases/latest می‌گیرد و رویِ market.dbِ کاربر ادغام می‌کند. آن فایل در CI
ساخته نمی‌شود و از ریلیزِ قبل جلو برده می‌شود، پس می‌تواند چندماهه باشد. ادغام
هم `UPDATE main.t SET <ستون‌های مشترک> FROM src.t` را بی‌هیچ شرطِ زمانی اجرا
می‌کرد — یعنی اگر کاربر همان هفته صورت‌مالیِ اصلاحیه گرفته بود، یک بار فشردنِ
دکمه عددِ اصلاحیه را با عددِ قدیمی جایگزین می‌کرد و پیام «به‌روز شد» نشان
می‌داد. خودِ دکمه داده را عقب می‌برد.

قاعده‌ای که این سوئیت قفل می‌کند:
  * محلیِ تازه‌تر  → دست‌نخورده (و شمرده در پیامِ پایان);
  * محلیِ کهنه‌تر  → از snapshot به‌سازی می‌شود;
  * محلیِ بی‌تاریخ → می‌گیرد (پرکردنِ خلأ، نه از‌دست‌رفتنِ داده);
  * snapshotِ بی‌تاریخ → محلیِ تاریخ‌دار را نمی‌بلعد;
  * برابر → به‌سازی می‌شود (idempotent: اجرایِ دوباره همان نتیجه را می‌دهد);
  * جدولِ بی‌fetched_at (monthly_sales) → رفتارِ قبلی، چون چیزی برای مقایسه نیست;
  * ستونِ فقط-مقصد (has_operating_sales) → هرگز NULL نمی‌شود.

هیچ‌کدام به market.db نیاز ندارد: همه رویِ دو دیتابیسِ موقتِ کوچک سنجیده
می‌شود، پس در CI هم اجرا می‌شود (نه SKIP).

اجرا:  python dev/codal_merge_recency_v1029.py
خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
"""
import io
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from api._sync_codal import _CODAL_TABLES, _merge_codal_snapshot  # noqa: E402

PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s %s" % (label, extra))


DDL_MAIN = {
    # snapshot این ستون را ندارد: باید دست‌نخورده بماند
    "codal_notices": """CREATE TABLE codal_notices(tracing_no INTEGER PRIMARY KEY,
                          symbol TEXT, title TEXT, fetched_at TEXT,
                          has_operating_sales INTEGER)""",
    "financial_statements": """CREATE TABLE financial_statements(
                          tracing_no INTEGER PRIMARY KEY, revenue REAL, fetched_at TEXT)""",
    "monthly_sales": """CREATE TABLE monthly_sales(tracing_no INTEGER PRIMARY KEY,
                          monthly_revenue REAL)""",
}
DDL_SNAP = {
    "codal_notices": """CREATE TABLE codal_notices(tracing_no INTEGER PRIMARY KEY,
                          symbol TEXT, title TEXT, fetched_at TEXT)""",
    "financial_statements": """CREATE TABLE financial_statements(
                          tracing_no INTEGER PRIMARY KEY, revenue REAL, fetched_at TEXT)""",
    "monthly_sales": """CREATE TABLE monthly_sales(tracing_no INTEGER PRIMARY KEY,
                          monthly_revenue REAL)""",
}

NEWER = "2026-09-25 10:00:00"
OLDER = "2026-08-01 08:00:00"


def build(path, ddl, rows):
    c = sqlite3.connect(path)
    for stmt in ddl.values():
        c.executescript(stmt)
    for table, rs in rows.items():
        c.executemany('INSERT INTO %s VALUES (%s)' % (table, ",".join("?" * len(rs[0]))), rs)
    c.commit()
    c.close()


def main():
    work = tempfile.mkdtemp(prefix="codal_merge_")
    main_db = os.path.join(work, "market.db")
    snap_db = os.path.join(work, "snapshot.db")

    build(main_db, DDL_MAIN, {
        "codal_notices": [
            (101, "فولاد", "محلی-تازه", NEWER, 1),        # محلی تازه‌تر
            (102, "فولاد", "محلی-کهنه", OLDER, 1),        # snapshot تازه‌تر
            (103, "فولاد", "محلی-بی‌تاریخ", None, 1),     # خلأ → می‌گیرد
            (104, "فولاد", "محلی-تاریخ‌دار", NEWER, 1),   # snapshot بی‌تاریخ
        ],
        "financial_statements": [
            (201, 11.0, NEWER),                            # محلی تازه‌تر
            (202, 22.0, OLDER),                            # محلی کهنه‌تر
            (203, 33.0, "2026-09-10 00:00:00"),            # برابر با snapshot
        ],
        "monthly_sales": [(301, 111.0)],                   # بدونِ fetched_at
    })
    build(snap_db, DDL_SNAP, {
        "codal_notices": [
            (101, "فولاد", "اسنپ-قدیمی", OLDER),
            (102, "فولاد", "اسنپ-تازه", NEWER),
            (103, "فولاد", "اسنپ-تازه", NEWER),
            (104, "فولاد", "اسنپ-بی‌تاریخ", None),
            (105, "ذوب", "اسنپ-ردیفِ تازه", NEWER),
        ],
        "financial_statements": [
            (201, 999.0, OLDER),
            (202, 888.0, NEWER),
            (203, 777.0, "2026-09-10 00:00:00"),
        ],
        "monthly_sales": [(301, 999.0)],
    })

    conn = sqlite3.connect(main_db, timeout=30)
    stats, stale = _merge_codal_snapshot(conn, snap_db)
    conn.commit()   # همان کاری که worker بعد از ادغام می‌کند — DETACH نباید مانعش شود

    got = dict(conn.execute("SELECT tracing_no, title FROM codal_notices").fetchall())
    rev = dict(conn.execute("SELECT tracing_no, revenue FROM financial_statements").fetchall())
    ms = dict(conn.execute("SELECT tracing_no, monthly_revenue FROM monthly_sales").fetchall())
    hos = dict(conn.execute(
        "SELECT tracing_no, has_operating_sales FROM codal_notices").fetchall())
    conn.close()

    ck(got.get(101) == "محلی-تازه", "a locally-newer notice is not downgraded", str(got.get(101)))
    ck(got.get(102) == "اسنپ-تازه", "a locally-older notice is refreshed", str(got.get(102)))
    ck(got.get(103) == "اسنپ-تازه", "an unstamped local row accepts the snapshot", str(got.get(103)))
    ck(got.get(104) == "محلی-تاریخ‌دار",
       "an unstamped snapshot row never overwrites a stamped local row", str(got.get(104)))
    ck(got.get(105) == "اسنپ-ردیفِ تازه", "a row only in the snapshot is inserted", str(got))
    ck(rev.get(201) == 11.0, "financial_statements keeps the newer local revenue", str(rev.get(201)))
    ck(rev.get(202) == 888.0, "financial_statements takes the newer snapshot revenue", str(rev.get(202)))
    ck(rev.get(203) == 777.0, "equal timestamps still update (idempotent replay)", str(rev.get(203)))
    ck(ms.get(301) == 999.0,
       "monthly_sales has no fetched_at, so it keeps the old always-write behaviour", str(ms.get(301)))
    ck(all(hos.get(k) == 1 for k in (101, 102, 103, 104)),
       "a destination-only column is never nulled on an existing row", str(hos))
    ck(hos.get(105) is None,
       "a row inserted from the snapshot has no local-only value — NULL, not a guess",
       str(hos.get(105)))

    ck(set(stats) == set(_CODAL_TABLES), "stats cover all three tables", str(list(stats)))
    upd, ins, keep = stats["codal_notices"]
    ck(keep == 2, "two locally-newer notices are reported as kept", str(stats["codal_notices"]))
    ck(ins == 1, "one inserted notice", str(stats["codal_notices"]))
    ck(stats["financial_statements"][2] == 1,
       "the kept count is per-table, not a global guess", str(stats["financial_statements"]))
    ck(stale and stale[0].startswith("codal_notices: has_operating_sales"),
       "the dropped-column warning still fires", str(stale))

    # اجرایِ دوباره نباید چیزی را عوض کند (idempotencyِ کاملِ مسیر)
    conn2 = sqlite3.connect(main_db, timeout=30)
    _merge_codal_snapshot(conn2, snap_db)
    conn2.commit()
    again = dict(conn2.execute("SELECT tracing_no, title FROM codal_notices").fetchall())
    rev2 = dict(conn2.execute("SELECT tracing_no, revenue FROM financial_statements").fetchall())
    conn2.close()
    ck(again == got and rev2 == rev, "a second merge changes nothing further")

    # worker هنوز همان ادغام را صدا می‌زند و عددِ «دست‌نخورده ماند» را گزارش می‌کند
    src = io.open(os.path.join(ROOT, "api", "_sync_codal.py"), encoding="utf-8").read()
    ck("stats, stale = _merge_codal_snapshot(main, tmp_db)" in src,
       "the worker merges through the shared function")
    ck("_CODAL_TABLES" in src and src.count("ATTACH DATABASE ? AS src") == 1,
       "no second inline merge implementation was left behind")
    ck("ردیفِ محلی تازه‌تر از snapshot بود" in src,
       "the honest end message says how many local rows were kept")

    # ── FTS-REFRESH-1: دکمهٔ «بروزرسانی» در بیلدِ فریزشده مُرده نباشد ──────────
    # بیلدِ PyInstaller پوشهٔ dev/ را ندارد (رویِ نصبِ زنده دیده شد)، پس
    # `/api/sync/codal/fts-refresh` هرگز خزنده را پیدا نمی‌کند. پیش از این
    # «یافت نشد» برمی‌گرداند و FundamentalPage پاسخ را دور می‌ریخت: اسپینر،
    # بعد هیچ. خزنده نباید به ماشینِ کاربر برود (ADB/چرخشِ IP ابزارِ ماشینِ
    # مالک است)، پس مسیرِ نبودِ خزنده کشِ محلی را پاک می‌کند و صادقانه می‌گوید
    # دادهٔ تازه از دکمهٔ «بروزرسانی دیتابیس کدال» می‌آید.
    _f = src.index("def sync_codal_fts_refresh")
    _body = src[_f:src.index("@router", _f + 10)]
    ck("from .screener import invalidate_screener_cache" in _body,
       "fts-refresh clears the local cache when the crawler is absent")
    ck('"status": "local_recompute"' in _body,
       "fts-refresh returns an honest status in a frozen build")
    ck('return {"status": "error", "message": "dev/codal_fts_updater.py' not in _body,
       "the silent dead-end «یافت نشد» is gone")
    ck("invalidate_screener_cache(drop_materialized=False)" in _body,
       "the frozen path keeps fts_results (nothing in the EXE can rebuild it)")
    ck(_body.index("invalidate_screener_cache(") < _body.index("CONTROL_PATH"),
       "no control-file write and no ADB rotate when the script is missing")

    print("codal_merge_recency_v1029: %d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
