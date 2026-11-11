# dev/test_phase48_backfill_history_v1.py — S4: backfillِ تاریخیِ مرجع رویِ کپیِ آزمایشگاهی
#
# هیچ‌مسیری به market.dbِ عملیاتی ندارد (tempfile.mkdtemp)؛ بی‌شبکه. ثابت می‌کند:
#   • فقط تاریخ‌هایِ «در مرجع هست، در بانک نیست» نوشته می‌شوند؛ ردیفِ موجود هرگز عوض نمی‌شود.
#   • هندسهٔ نامعتبر/حجمِ صفر/قیمتِ صفر کندل نمی‌شود؛ ردیفِ تکراریِ مرجع دوبار نوشته نمی‌شود.
#   • سایهٔ بیرونِ بدنه (h<o / l>o) با قراردادِ کندل (widen) پذیرفته و اصلاحش ثبت می‌شود؛
#     سایهٔ وارونه (high<low) و ردیفِ غیرمتناهی/بی‌قیمت/بی‌حجم با نام رد می‌شوند.
#   • هر ردیفِ نوشته‌شده provenanceِ اجرا/مرجع دارد (backfill_runs/backfill_rows).
#   • اجرایِ دوم idempotent است (صفر نوشتن) و rollback فقط ردیف‌هایِ همان اجرا را برمی‌دارد.
#   • مقایسهٔ خام، مبناهایِ close (last/closing/other) و low=حراج را جدا می‌شمارد.
import gzip
import io
import json
import os
import sqlite3
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "phase48"))

import backfill_reference as B  # noqa: E402

P = F = 0


def check(name, got, want):
    global P, F
    if got == want:
        P += 1
        print(f"  ✓ {name}")
    else:
        F += 1
        print(f"  ✗ {name}: got={got!r} want={want!r}")


SCHEMA = (
    "CREATE TABLE price_history (symbol TEXT, date TEXT, open REAL, high REAL, low REAL,"
    " close REAL, volume REAL, last REAL, value REAL, src TEXT, PRIMARY KEY (symbol, date))"
)


def temp_db(path, rows):
    con = sqlite3.connect(path)
    con.execute(SCHEMA)
    con.executemany(
        "INSERT INTO price_history (symbol,date,open,high,low,close,volume,last,value,src)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()


def ref_row(sym, date, o, h, l, c, v, adjust="raw", res="D", typ="type0", asset=1):
    return {"symbol": sym, "date": date, "open": o, "high": h, "low": l, "close": c,
            "volume": v, "adjust": adjust, "resolution": res, "type": typ,
            "basis": "real_close", "asset_id": asset}


def write_ref(path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    tmp = tempfile.mkdtemp(prefix="p48backfill_")
    src = os.path.join(tmp, "market.db")
    work = os.path.join(tmp, "work")
    ref = os.path.join(tmp, "bars.ndjson.gz")
    local = [
        ("فولاد", "2024-01-01", 100.0, 110.0, 90.0, 105.0, 1000.0, 107.0, 5000.0, "legacy-unknown"),
        ("فولاد", "2024-01-02", 101.0, 111.0, 91.0, 106.0, 0.0, None, None, "legacy-unknown"),
        ("خودرو", "2024-01-01", 200.0, 210.0, 190.0, 205.0, 2000.0, 207.0, None, "board"),
    ]
    temp_db(src, local)
    rows = [
        ref_row("فولاد", "2023-12-30", 90, 95, 80, 85, 900),          # تنها ردیفِ تازه
        ref_row("فولاد", "2024-01-01", 999, 999, 999, 999, 9),        # مشترک: باید دست‌نخورده بماند
        ref_row("فولاد", "2023-12-31", 90, 95, 80, 85, 0),            # حجمِ صفر ⇒ نامعتبر
        ref_row("فولاد", "2023-12-29", 90, 95, 80, 0, 900),           # close صفر ⇒ نامعتبر
        ref_row("فولاد", "2023-12-28", 90, 70, 95, 85, 900),          # سایهٔ وارونه: high<low
        ref_row("فولاد", "2023-12-27", 80, 88, 75, 85, 800),          # تکراری: اولی می‌ماند
        ref_row("فولاد", "2023-12-27", 81, 89, 76, 86, 801),
        ref_row("فولاد", "2023-12-26", 80, 88, 75, 85, 800, adjust="adjusted"),
        ref_row("فولاد", "2023-12-25", 80, 88, 75, 85, 800, res="W"),
        ref_row("خودرو", "2023-12-30", 200, 210, 190, 205, 3000),     # بیرونِ فهرستِ نمادها
    ]
    write_ref(ref, rows)

    dry = B.apply_backfill(src, work, ref, ["فولاد"], "run-dry", dry_run=True)
    check("۰ dry-run چیزی نمی‌نویسد", (dry["inserted"], dry["would_insert"]), (0, 2))
    rep = B.apply_backfill(src, work, ref, ["فولاد"], "run-test-1", dry_run=False)
    check("۱ ردیف‌هایِ تازه (۲ تا) نوشته شد", rep["inserted"], 2)
    check("۱ ردیفِ مشترک دست‌نخورده", rep["changed_existing"], 0)
    check("۱ هشِ فایلِ کاری پس از بستن", rep["work_db_sha256_after"],
          B.sha256_file(os.path.join(work, "market.db")))
    check("۱ ردیفِ نامعتبر ۳ + تکراری ۱", (rep["invalid"], rep["duplicate_conflicts"]), (3, 1))
    check("۱ نامعتبر با نام: high<low/close<=0/volume<=0",
          rep["totals"]["invalid_reasons"],
          {"high<low": 1, "close<=0": 1, "volume<=0": 1})
    con = sqlite3.connect(os.path.join(work, "market.db"))
    got = con.execute("SELECT date,open,close,last,src FROM price_history"
                      " WHERE symbol='فولاد' ORDER BY date").fetchall()
    check("۱ تاریخ‌هایِ نهایی", [r[0] for r in got],
          ["2023-12-27", "2023-12-30", "2024-01-01", "2024-01-02"])
    check("۱ ردیفِ موجود بازنویسی نشد", got[2][1:], (100.0, 105.0, 107.0, "legacy-unknown"))
    check("۱ src و lastِ ردیفِ تازه", got[1][3:], (85.0, "rahavard365"))
    check("۱ provenanceِ دو ردیف", con.execute(
        "SELECT COUNT(*) FROM backfill_rows WHERE run_id='run-test-1'").fetchone()[0], 2)
    check("۱ اجرا ثبت شد", con.execute(
        "SELECT inserted,status FROM backfill_runs WHERE run_id='run-test-1'").fetchone(),
        (2, "applied"))
    con.close()

    # idempotent: همان کار با شناسهٔ دوم هیچ نمی‌نویسد
    rep2 = B.apply_backfill(src, work, ref, ["فولاد"], "run-test-2", reuse_work=True)
    check("۲ اجرایِ دوم صفر نوشتن", rep2["inserted"], 0)
    check("۲ ردیف‌هایِ تازه به‌عنوانِ موجود شمرده شد", rep2["skipped_existing"], 2)
    con = sqlite3.connect(os.path.join(work, "market.db"))
    check("۲ تعدادِ نهایی بی‌تغییر", con.execute(
        "SELECT COUNT(*) FROM price_history WHERE symbol='فولاد'").fetchone()[0], 4)
    con.close()

    rb = B.rollback_backfill(os.path.join(work, "market.db"), "run-test-1")
    check("۳ rollback فقط ردیف‌هایِ همان اجرا", rb["deleted"], 2)
    con = sqlite3.connect(os.path.join(work, "market.db"))
    check("۳ ردیفِ محلی ماند", con.execute(
        "SELECT COUNT(*) FROM price_history WHERE src='legacy-unknown'").fetchone()[0], 2)
    check("۳ ردیفِ مرجع رفت", con.execute(
        "SELECT COUNT(*) FROM price_history WHERE src='rahavard365'").fetchone()[0], 0)
    check("۳ وضعیتِ اجرا", con.execute(
        "SELECT status FROM backfill_runs WHERE run_id='run-test-1'").fetchone()[0], "rolled_back")
    con.close()
    check("۳ rollback دوم صفر", B.rollback_backfill(
        os.path.join(work, "market.db"), "run-test-1")["deleted"], 0)

    # مقایسهٔ خام: close با last، وگرنه closing؛ low==last ⇒ حراج
    loc = [
        {"date": "d1", "open": 10, "high": 12, "low": 9, "close": 11, "last": 11.5, "volume": 100},
        {"date": "d2", "open": 10, "high": 12, "low": 9, "close": 11, "last": None, "volume": 100},
        {"date": "d3", "open": 10, "high": 12, "low": 11, "close": 11, "last": 11, "volume": 100},
    ]
    rr = [
        {"date": "d1", "open": 10, "high": 12, "low": 9, "close": 11.5, "volume": 100},
        {"date": "d2", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100},
        {"date": "d3", "open": 10, "high": 12, "low": 9, "close": 9, "volume": 100},
    ]
    st = B.compare_raw_rows(loc, rr)
    check("۴ close: last / closing / other", (st["close_by_last"], st["close_by_closing"],
                                              st["close_other"]), (1, 1, 1))
    check("۴ last_missing", st["last_missing"], 1)
    check("۴ low=حراج", st["low_auction"], 1)
    check("۴ open/high/volume برابر", (st["open_mismatch"], st["high_mismatch"],
                                        st["volume_mismatch"]), (0, 0, 0))

    # قراردادِ کندل: هندسه از `widen` می‌آید نه از قضاوتِ محلی. ردیفی که فقط
    # سایه‌اش بیرونِ بدنه است پذیرفته می‌شود و اصلاحش در گزارش می‌آید؛ ردیفِ
    # وارونه/غیرمتناهی/بی‌قیمت با نام رد می‌شود.
    tmp2 = tempfile.mkdtemp(prefix="p48contract_")
    src2 = os.path.join(tmp2, "market.db")
    work2 = os.path.join(tmp2, "work")
    ref2 = os.path.join(tmp2, "bars.ndjson.gz")
    temp_db(src2, [])
    rows2 = [
        ref_row("گواه", "2024-02-01", 90, 70, 60, 85, 100),        # h<o: widen
        ref_row("گواه", "2024-02-02", 10, 5, 20, 8, 100),          # high<low
        ref_row("گواه", "2024-02-03", "10", "12", "9", "nan", 100),  # غیرمتناهی
        ref_row("گواه", "2024-02-04", 10, 12, 9, 0, 100),          # close<=0
        ref_row("گواه", "2024-02-05", 10, 12, 9, 8, 0),            # volume<=0
        ref_row("گواه", "2024-02-06", 10, 14, 13, 12, 100),        # l>o: widen
    ]
    write_ref(ref2, rows2)
    rep_c = B.apply_backfill(src2, work2, ref2, ["گواه"], "run-contract")
    check("۵ h<o و l>o با widen پذیرفته شدند", rep_c["inserted"], 2)
    check("۵ نامعتبر با نام", rep_c["totals"]["invalid_reasons"],
          {"high<low": 1, "not-finite": 1, "close<=0": 1, "volume<=0": 1})
    check("۵ اصلاح ثبت شد", (rep_c["corrections"]["rows_corrected"],
                             rep_c["corrections"]["high_widened"],
                             rep_c["corrections"]["low_widened"]), (2, 1, 1))
    con = sqlite3.connect(os.path.join(work2, "market.db"))
    check("۵ سایه گشاد شد، بدنه دست‌نخورده",
          con.execute("SELECT open,high,low,close,last FROM price_history"
                      " WHERE symbol='گواه' AND date='2024-02-01'").fetchone(),
          (90.0, 90.0, 60.0, 85.0, 85.0))
    check("۵ کف به بدنه گشاد شد",
          con.execute("SELECT open,high,low,close,last FROM price_history"
                      " WHERE symbol='گواه' AND date='2024-02-06'").fetchone(),
          (10.0, 14.0, 10.0, 12.0, 12.0))
    con.close()
    sample = rep_c["corrections"]["samples"][0]
    check("۵ اصلاح دیدنی: خام/نهایی",
          (sample["date"], sample["raw_high"], sample["high"], sample["reason"]),
          ("2024-02-01", 70.0, 90.0, "high-widened"))

    print(f"\n{P} passed / {F} failed")
    return 0 if F == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
