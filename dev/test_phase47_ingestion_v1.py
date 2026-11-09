#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_phase47_ingestion_v1.py — گاردهایِ یکپارچگیِ ingestion (فاز ۴٫۷).

سه ادعای مستقل، هر کدام با یک شاهدِ عددی و یک کنترلِ منفی:

  ۱) **provenance**: ردیفِ بدونِ `src` هرگز «published» گزارش نمی‌شود و رتبهُ
     نوشتنش صفر می‌ماند؛ ردیفِ منتشرشده با هیچ نوشتارِ رتبه‌پایین‌تر بازنویسی
     نمی‌شود (قراردادِ `candle_contract.UPSERT_SQL`).
  ۲) **daily_prices**: پاسخِ لاغر/صفرِ تابلو ردیفِ معامله‌شدهٔ همان نشست را پاک
     نمی‌کند، ولی رشدی که در همان نشست واقعاً رخ می‌دهد می‌نشیند (کنترلِ منفی:
     نبودِ گارد ⇒ پاک‌شدن).
  ۳) **idempotency**: اجرایِ دوبارهٔ همان snapshot هیچ ردیفی را عوض نمی‌کند.

اجرا: python dev/test_phase47_ingestion_v1.py
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import candle_contract as CC  # noqa: E402

FAILED = []
PASSED = []


def ck(cond, label, detail=""):
    if cond:
        print("  ok  %s" % label)
        PASSED.append(label)
    else:
        print("  FAIL %s %s" % (label, detail))
        FAILED.append(label)


def section(title):
    print("\n[%s]" % title)


def test_provenance():
    section("۱) برچسبِ منبع (provenance)")
    ck(CC.SRC_LEGACY in CC.RANK, "legacy-unknown در جدولِ رتبه هست")
    ck(CC.RANK[CC.SRC_LEGACY] == 0, "رتبهُ legacy با NULL یکی است (صفر)")
    ck(CC.RANK[CC.SRC_LEGACY] < CC.RANK[CC.SRC_BOARD] < CC.RANK[CC.SRC_PUBLISHED],
       "ترتیب: legacy < board < published")

    null_src = CC.from_db_row(("X", "2026-01-01", 10, 11, 9, 10.5, 100, None, None, None))
    empty_src = CC.from_db_row(("X", "2026-01-01", 10, 11, 9, 10.5, 100, None, None, ""))
    tree_cols = CC.from_db_row(("X", "2026-01-01", 10, 11, 9, 10.5, 100))
    for bar, label in ((null_src, "NULL"), (empty_src, "تهی"), (tree_cols, "ستون غایب")):
        ck(bar["src"] == CC.SRC_LEGACY, "src=%s ⇒ legacy-unknown" % label,
           "got %r" % bar["src"])
    board = CC.from_db_row(("X", "2026-01-01", 10, 11, 9, 10.5, 100, None, None, "board"))
    ck(board["src"] == CC.SRC_BOARD, "src موجود دست‌نخورده می‌ماند")

    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE price_history (symbol TEXT, date TEXT, open REAL, high REAL,"
                " low REAL, close REAL, volume REAL, last REAL, value REAL, src TEXT,"
                " PRIMARY KEY(symbol, date))")
    pub = CC.from_csv_row("X", "X,20260101,10,11,9,10.5,1000,900,0,0,9.8,10.4".split(","))
    ck(pub and pub["src"] == CC.SRC_PUBLISHED, "ردیفِ CSV ⇒ published")
    con.execute(CC.UPSERT_SQL, CC.upsert_row(pub))
    con.commit()
    stale = CC.candle("X", "2026-01-01", 1, 1, 1, 1, 50, None, None, CC.SRC_BOARD)
    con.execute(CC.UPSERT_SQL, CC.upsert_row(stale))
    con.commit()
    row = con.execute("SELECT open, src FROM price_history").fetchone()
    ck(row[0] == 10 and row[1] == CC.SRC_PUBLISHED,
       "نوشتارِ board ردیفِ published را بازنویسی نمی‌کند", row)
    legacy = dict(stale, src=CC.SRC_LEGACY, open=2.0)
    con.execute(CC.UPSERT_SQL, CC.upsert_row(legacy))
    con.commit()
    row = con.execute("SELECT open, src FROM price_history").fetchone()
    ck(row[0] == 10 and row[1] == CC.SRC_PUBLISHED,
       "نوشتارِ legacy ردیفِ published را بازنویسی نمی‌کند", row)
    con.close()


def _dp_schema(con, with_pk):
    pk = ", PRIMARY KEY(ins_code, d_even)" if with_pk else ""
    con.execute("CREATE TABLE daily_prices (ins_code TEXT, d_even INTEGER, p_closing REAL,"
                " price_min REAL, price_max REAL, price_yesterday REAL, price_first REAL,"
                " q_tot_tran REAL, q_tot_cap REAL, price_change REAL, fetched_at TEXT,"
                " market_cap REAL, market_cap_src TEXT, z_tot_tran REAL, p_last REAL%s)" % pk)


def test_daily_snapshot_guard():
    section("۲) daily_prices در برابرِ snapshot ناقص")
    import test_tsetmc as T

    con = sqlite3.connect(":memory:")
    _dp_schema(con, with_pk=True)
    sql = T.dp_insert_sql(con)
    ck("ON CONFLICT(ins_code, d_even)" in sql, "بانکِ با PK ⇒ UPSERTِ محافظت‌شده")
    rich = ("I", 20261011, 4180.0, 4000.0, 4220.0, 4100.0, 4220.0,
            8_380_424_275.0, 3.5e13, 80.0, "t1", None, None, 1_000_000.0, 4220.0)
    con.execute(sql, rich)
    con.commit()
    # پاسخِ لاغر: pcl/pdv هست، بقیهٔ ارقام صفر — همان الگویِ اندازه‌گیری‌شده.
    thin = ("I", 20261011, 4180.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, "t2", None, None, 0.0, 4220.0)
    con.execute(sql, thin)
    con.commit()
    got = con.execute("SELECT q_tot_tran, price_first, price_min, price_max, p_closing"
                      " FROM daily_prices").fetchone()
    ck(got == (8_380_424_275.0, 4220.0, 4000.0, 4220.0, 4180.0),
       "snapshotِ لاغر ردیفِ معامله‌شده را پاک نمی‌کند", got)

    # کنترلِ منفی: همان توالی با SQLِ قدیمی (INSERT OR REPLACE) داده را می‌بلعد.
    con2 = sqlite3.connect(":memory:")
    _dp_schema(con2, with_pk=True)
    for row in (rich, thin):
        con2.execute(T._DP_INSERT_LEGACY, row)
    con2.commit()
    legacy_got = con2.execute("SELECT q_tot_tran FROM daily_prices").fetchone()
    ck(legacy_got == (0.0,), "کنترلِ منفی: REPLACE داده را صفر می‌کند (نقص اثبات شد)",
       legacy_got)

    # رشدِ واقعیِ همان نشست باید بنشیند.
    grow = ("I", 20261011, 4190.0, 3990.0, 4230.0, 4100.0, 4220.0,
            9_000_000_000.0, 3.6e13, 90.0, "t3", None, None, 1_100_000.0, 4230.0)
    con.execute(sql, grow)
    con.commit()
    got = con.execute("SELECT q_tot_tran, p_closing, price_min, p_last FROM daily_prices"
                      ).fetchone()
    ck(got == (9_000_000_000.0, 4190.0, 3990.0, 4230.0),
       "رشدِ درون‌نشست می‌نشیند", got)

    before = con.execute("SELECT q_tot_tran, p_closing, price_min, p_last FROM daily_prices"
                         ).fetchone()
    con.execute(sql, grow)
    con.commit()
    after = con.execute("SELECT q_tot_tran, p_closing, price_min, p_last FROM daily_prices"
                        ).fetchone()
    ck(before == after, "اجرایِ دوباره بی‌اثر است (idempotent)", (before, after))
    ck(con.execute("SELECT COUNT(*) FROM daily_prices").fetchone()[0] == 1,
       "هیچ ردیفِ تازه‌ای ساخته نشد")

    con_nopk = sqlite3.connect(":memory:")
    _dp_schema(con_nopk, with_pk=False)
    ck(T.dp_insert_sql(con_nopk) == T._DP_INSERT_LEGACY,
       "بانکِ بدونِ PK به رفتارِ قبلی برمی‌گردد (بی‌خطا)")
    con.close()
    con2.close()
    con_nopk.close()


def test_no_live_fabrication():
    section("۳) بی‌ساختنِ عدد و بی‌هرسِ دادهٔ منتشرشده")
    ck(CC.candle("X", "2026-01-01", 10, 11, 9, 10.5, 0) is None,
       "روزِ بی‌معامله (حجم صفر) کندل نمی‌شود")
    bar = CC.candle("X", "2026-01-01", 10, 11, 9, 10.5, 100, None)
    ck(bar["last"] is None, "lastِ غایب None می‌ماند، نه close")
    ck(bar["close"] == 10.5 and bar["last"] is None,
       "close و last هرگز با هم عوض نمی‌شوند")
    hi, lo = CC.widen(1200, 1100, 0, 1150)
    ck(hi == 1200 and lo == 1150, "widen: کف از بدنه، نه از صفرِ «هنوز پر نشده»",
       (hi, lo))


def main():
    print("phase 4.7 ingestion guards")
    test_provenance()
    test_daily_snapshot_guard()
    test_no_live_fabrication()
    print("\n%d passed / %d failed" % (len(PASSED), len(FAILED)))
    if FAILED:
        print("FAILED: %s" % ", ".join(FAILED))
        return 1
    print("PHASE47 INGESTION GUARDS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
