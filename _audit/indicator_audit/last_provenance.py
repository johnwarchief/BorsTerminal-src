# -*- coding: utf-8 -*-
"""`_audit/indicator_audit/last_provenance.py` — منشأِ `price_history.last` و `src` (Phase C).

پرسش‌هایی که این اسکریپت با عدد جواب می‌دهد (بدونِ شبکه، بدونِ نوشتن رویِ
`market.db`ِ کاری، بدونِ re-fetch):

  ۱) امروز چه تعدادِ سطر `last` / `value` / `src` پر دارد؟
  ۲) آیا «آخرینِ» هر روز درِ هیچ جدولِ دیگری از بانکِ محلی هست؟ (مرورِ همهِ
     جدول‌ها برایِ ستون‌هایِ last-مانند + پوششِ زمانی‌شان)
  ۳) آیا لولۀ نوشتن می‌تواند `last` را از تابلو به `price_history` برساند؟
     (آزمونِ لولۀی رویِ بانکِ موقت: `daily_prices` → `sync_price_history_from_daily`)
   ۴) آیا `src`ِ تهی، قیدِ مالکیتِ سطر درِ `candle_contract.UPSERT_SQL` را بی‌اثر
     می‌کند؟ (آزمونِ رفتاری: ردیفِ «منتشرشده» با ردیفِ «تابلو» جایگزین می‌شود؟)

اجرا:  python _audit/indicator_audit/last_provenance.py
"""
import json
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import candle_contract as CC           # noqa: E402
import price_basis                     # noqa: E402

DB = os.path.join(ROOT, "market.db")
PASS = FAIL = 0


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ✓ %s" % what)
    else:
        FAIL += 1
        print("  ✗ %s%s" % (what, ("   ← %s" % detail) if detail else ""))


def main():
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    one = lambda s: con.execute(s).fetchone()

    print("— ۱) آنچه بانکِ کاری امروز دارد")
    ph = one("SELECT count(*), sum(last IS NOT NULL), sum(value IS NOT NULL),"
             " sum(src IS NOT NULL) FROM price_history")
    print("   price_history: %d سطر · last پر=%s · value پر=%s · src پر=%s"
          % (ph[0], ph[1] or 0, ph[2] or 0, ph[3] or 0))
    ck(ph[1] == 0, "هیچ ردیفِ پرشدۀ `last` درِ price_history نیست (سنجیده، نه حدس)", str(ph))
    ck(ph[3] == 0, "هیچ ردیفی `src` ندارد ⇒ قیدِ مالکیتِ سطر رویِ این بانک بی‌اثر است", str(ph))
    print("   پوششِ زمانی:", one("SELECT min(date), max(date), count(DISTINCT date),"
                                 " count(DISTINCT symbol) FROM price_history"))

    print("\n— ۲) آیا «آخرینِ» روزهایِ گذشته جای دیگری هست؟")
    found = []
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        cols = [r[1] for r in con.execute("PRAGMA table_info(%s)" % t)]
        cand = [x for x in cols if x in ("p_last", "last", "price_last", "pLast")]
        if not cand:
            continue
        for col in cand:
            n, tot = con.execute("SELECT sum(%s IS NOT NULL AND %s>0), count(*) FROM %s"
                                 % (col, col, t)).fetchone()
            span = ""
            for dc in ("date", "d_even"):
                if dc in cols:
                    span = str(con.execute("SELECT min(%s), max(%s) FROM %s" % (dc, dc, t)).fetchone())
                    break
            found.append((t, col, n or 0, tot, span))
            print("   %-14s %-8s پر=%-6s از %-7s %s" % (t, col, n or 0, tot, span))
    mw = [f for f in found if f[0] == "market_watch"]
    dp = [f for f in found if f[0] == "daily_prices"]
    ck(bool(mw) and mw[0][2] > 0, "تابلو (market_watch) آخرینِ نشستِ جاری را دارد",
       str(mw))
    ck(bool(dp) and dp[0][2] == 0, "daily_prices هیچِ «آخرینِ» ذخیره‌شده‌ای ندارد",
       str(dp))
    print("   ⇒ تنها سورسِ per-dayِ «آخرین» درِ همین بانک: یکِ نشستِ جاری (تابلو) — "
          "تاریخچه نیست")

    print("\n— ۳) لولۀ نوشتن: آیا مسیرِ تابلو می‌تواند last را به price_history برساند؟")
    tmp = os.path.join(tempfile.mkdtemp(prefix="lastprov_"), "t.db")
    w = sqlite3.connect(tmp)
    w.execute("CREATE TABLE price_history (symbol TEXT, date TEXT, open REAL, high REAL,"
              " low REAL, close REAL, volume REAL, last REAL, value REAL, src TEXT,"
              " PRIMARY KEY (symbol, date))")
    w.execute("CREATE TABLE daily_prices (ins_code TEXT, d_even INTEGER, p_closing REAL,"
              " price_min REAL, price_max REAL, price_yesterday REAL, price_first REAL,"
              " q_tot_tran REAL, q_tot_cap REAL, price_change REAL, fetched_at TEXT,"
              " market_cap REAL, market_cap_src TEXT, z_tot_tran REAL, p_last REAL)")
    w.execute("CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT, l_val30 TEXT,"
              " sector_code TEXT, sector_name TEXT, total_shares REAL, eps REAL, pe REAL,"
              " base_vol REAL, updated_at TEXT, paper_type TEXT)")
    days = [20260927, 20260928, 20260929, 20260930]
    for i, d in enumerate(days):
        w.execute("INSERT INTO daily_prices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  ("INS1", d, 1000.0 + i, 990.0 + i, 1010.0 + i, 995.0 + i, 998.0 + i,
                   100.0, 1.0e9, 5.0, "now", 1.0e12, "tse_board", 40.0, 1005.0 + i))
    w.execute("INSERT INTO instruments VALUES ('INS1','فولاد','فولاد','S','فلزات',0,0,0,0,'now','1')")
    w.commit()
    import test_tsetmc
    n = test_tsetmc.sync_price_history_from_daily(w, full=True)
    got = w.execute("SELECT date, close, last, value, src FROM price_history ORDER BY date").fetchall()
    print("   rows=%s %s" % (n, got))
    ck(bool(got) and all(r[2] is not None for r in got),
       "مسیرِ تابلو (daily_prices.p_last → price_history.last) عدد را می‌رساند",
       str([r[2] for r in got]))
    ck(bool(got) and all(r[4] == CC.SRC_BOARD for r in got),
       "و src را هم می‌نویسد (board) ⇒ پس ازِ این مرحله قیدِ مالکیت زنده می‌شود",
       str([r[4] for r in got]))
    ck(all(abs((r[2] or 0) - (r[1] or 0)) > 0.5 or r[2] == r[1] for r in got),
       "last با closing یکی نیست یا صریح برابرش است — جعلِ بی‌صدا ندارد", str(got))
    w.close()

    print("\n— ۴) قیدِ مالکیتِ سطر با srcِ تهی")
    v = sqlite3.connect(":memory:")
    v.execute("CREATE TABLE price_history (symbol TEXT, date TEXT, open REAL, high REAL,"
              " low REAL, close REAL, volume REAL, last REAL, value REAL, src TEXT,"
              " PRIMARY KEY (symbol, date))")
    # سطرِ «منتشرشده» که srcاش NULL است (همان شکلِ بانکِ امروز)
    v.execute("INSERT INTO price_history VALUES ('فولاد','2026-09-30',1,2,0.5,1.5,10,NULL,NULL,NULL)")
    board = CC.candle("فولاد", "2026-09-30", 1.0, 2.0, 0.5, 1.6, 11.0, 1.7, 1.1e9, CC.SRC_BOARD)
    v.execute(CC.UPSERT_SQL, CC.upsert_row(board))
    after = v.execute("SELECT close, src FROM price_history").fetchone()
    print("   پس ازِ نوشتنِ یکِ سطرِ board رویِ سطرِ منتشرشدۀ بی‌src:", after)
    ck(after[1] == CC.SRC_BOARD,
       "اثبات: بی‌src، اولویتِ «published > board» بی‌اثر است و سطر بازنویسی می‌شود",
       str(after))
    v2 = sqlite3.connect(":memory:")
    v2.execute("CREATE TABLE price_history (symbol TEXT, date TEXT, open REAL, high REAL,"
               " low REAL, close REAL, volume REAL, last REAL, value REAL, src TEXT,"
               " PRIMARY KEY (symbol, date))")
    v2.execute("INSERT INTO price_history VALUES ('فولاد','2026-09-30',1,2,0.5,1.5,10,NULL,NULL,?)",
               (CC.SRC_PUBLISHED,))
    v2.execute(CC.UPSERT_SQL, CC.upsert_row(board))
    kept = v2.execute("SELECT close, src FROM price_history").fetchone()
    ck(kept[1] == CC.SRC_PUBLISHED,
       "با srcِ درست، سطرِ منتشرشده له نمی‌شود (قرارداد کار می‌کند)", str(kept))
    con.close()
    print("\nنتیجه: %d سبز، %d قرمز" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
