# -*- coding: utf-8 -*-
"""گاردِ شمارِ ردیفِ --pack (تسک ۶۴).

reason: `PACK_REFUSED` فقط «تاریخِ آخرین نشست» را با بیس‌لاین مقایسه می‌کرد.
رویِ ماشینِ ۱۴۰۵-۰۷-۰۹ بانکِ مخزن با آخرینِ نشستِ *همان روز* ۱۴٬۸۶۶ ردیفِ
daily_prices کم‌تر از فایلِ منتشرشده داشت، و بانکِ اپِ نصبی tape_history را
از دست داده بود — یعنی --pack بی‌استثنا قبول می‌کرد و بیس‌لاینِ ریلیز را
کوتاه می‌کرد. این سوئیت هر دو حالت را با بانکِ کوچکِ مصنوعی می‌سنجد: بی‌بانک،
بی‌شبکه، بی‌دست‌زدنِ market.db واقعی.
"""
import io
import lzma
import os
import sqlite3
import sys
import tempfile
import contextlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scripts.check_release_db as M  # noqa: E402

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))


def make_db(path, rows, last_day=20260930, with_tape=True):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE daily_prices (ins_code TEXT, d_even INT, fetched_at TEXT)")
    conn.execute("CREATE TABLE market_totals (updated_at TEXT)")
    conn.execute("CREATE TABLE financial_statements (symbol TEXT)")
    conn.execute("CREATE TABLE codal_notices (report_id TEXT, fetched_at TEXT)")
    if with_tape:
        conn.execute("CREATE TABLE tape_history (symbol TEXT)")
    stamp = "2026-09-30 12:00:00"
    conn.executemany("INSERT INTO daily_prices VALUES (?,?,?)",
                     [("s%d" % i, last_day, stamp) for i in range(rows["daily_prices"])])
    conn.execute("INSERT INTO market_totals VALUES (?)", (stamp,))
    conn.executemany("INSERT INTO financial_statements VALUES (?)",
                     [("s%d" % i,) for i in range(rows["financial_statements"])])
    conn.executemany("INSERT INTO codal_notices VALUES (?,?)",
                     [("r%d" % i, stamp) for i in range(rows["codal_notices"])])
    if with_tape:
        conn.executemany("INSERT INTO tape_history VALUES (?)",
                         [("s%d" % i,) for i in range(rows["tape_history"])])
    conn.commit()
    conn.close()


def write_baseline(dst, path):
    with open(path, "rb") as f:
        raw = f.read()
    with open(dst, "wb") as f:
        f.write(lzma.compress(raw, preset=1))


def run_pack(src_db, dst_lzma, **kw):
    out = io.StringIO()
    old_src, old_dst = M.SRC, M.DST
    M.SRC, M.DST = src_db, dst_lzma
    try:
        with contextlib.redirect_stdout(out):
            rc = M.pack(**kw)
    finally:
        M.SRC, M.DST = old_src, old_dst
    return rc, out.getvalue()


def scenario(tag, base_rows, src_rows, src_day=20260930, src_tape=True, **kw):
    # هر سناریو پوشۀ خودش: دو سناریو روی یک base.db «table already exists»
    # می‌گیرد، و روی ویندوزِ قفل‌شده پاک‌کردنِ پوشۀ مشترک هم ممکن نیست.
    dirname = tempfile.mkdtemp(prefix="prc_" + tag + "_")
    base_db = os.path.join(dirname, "base.db")
    src_db = os.path.join(dirname, "src.db")
    dst = os.path.join(dirname, "market.db.lzma")
    make_db(base_db, base_rows)
    make_db(src_db, src_rows, last_day=src_day, with_tape=src_tape)
    write_baseline(dst, base_db)
    before = open(dst, "rb").read()
    rc, log = run_pack(src_db, dst, **kw)
    after = open(dst, "rb").read()
    return rc, log, before == after, os.path.exists(dst + ".bak")


FULL = {"daily_prices": 100, "financial_statements": 40, "codal_notices": 60, "tape_history": 200}

# ۱) کاستیِ ردیف با آخرینِ نشستِ تازه → رد، فایل دست‌نخورده
rc, log, untouched, bak = scenario("refuse", FULL, dict(FULL, daily_prices=85))
ck(rc == 1, "کاهشِ daily_prices با نشستِ تازه رد می‌شود (rc=1)")
ck("PACK_SHRINK table=daily_prices source=85 baseline=100 lost=15" in log,
   "خطِ PACK_SHRINK هر سه عدد را می‌نویسد")
ck("PACK_REFUSED rows" in log, "پیامِ ردِ صریحِ --pack چاپ می‌شود")
ck(untouched, "بیس‌لاین در حالتِ رد بی‌تغییر می‌ماند")
ck(not bak, "رد پیش از پشتیبان‌گیریِ .bak می‌ایستد (هیچ چیزی جابه‌جا نشد)")

# ۲) همان کاهش با --allow-shrink → قبول، بیس‌لاین عوض می‌شود
rc2, log2, untouched2, bak2 = scenario("shrink", FULL, dict(FULL, daily_prices=85),
                                       allow_shrink=True)
ck(rc2 == 0, "--allow-shrink همان کاهش را می‌پذیرد")
ck("PACK_ALLOWED_SHRINK" in log2, "پذیرشِ عمدی علامت می‌خورد")
ck(not untouched2, "با پذیرش، بیس‌لاین واقعاً بازنویسی می‌شود")
ck(bak2, "مسیرِ پذیرش از .bakِ همیشگی می‌گذرد")

# ۳) ردیفِ برابر یا بیشتر → بدونِ پرچم قبول
rc3, log3, _, _ = scenario("grow", FULL, dict(FULL, tape_history=250))
ck(rc3 == 0, "افزایشِ ردیف بی‌پرچم قبول می‌شود")
ck("PACK_SHRINK" not in log3, "هیچ کاستی‌ای گزارش نمی‌شود")

# ۴) جدولِ غایب = ناشناخته، نه صفر
rc4, log4, untouched4, _ = scenario("no Tape", FULL, dict(FULL), src_tape=False)
ck(rc4 == 0, "نبودِ tape_history در منبع رد نمی‌کند (ناشناخته ≠ صفر)")
ck("PACK_SHRINK table=tape_history" not in log4, "جدولِ ناشناخته در فهرستِ کاستی نمی‌آید")

# ۵) رفتارِ کهنه‌تر (منطقِ قبلی) باید دست‌نخورده بماند
rc5, log5, untouched5, _ = scenario("old", FULL, dict(FULL), src_day=20260929)
ck(rc5 == 1 and "PACK_REFUSED source is older" in log5,
   "گاردِ تاریخِ قدیمی همچنان کار می‌کند")
ck(untouched5, "ردِ تاریخی هم بیس‌لاین را دست نمی‌زند")

# ۶) بیس‌لاینِ ناخوانا → نه ردِ کاذب، نه کرش
d2 = tempfile.mkdtemp(prefix="prc_garbage_")
src_db = os.path.join(d2, "src.db")
dst = os.path.join(d2, "market.db.lzma")
make_db(src_db, FULL)
with open(dst, "wb") as f:
    f.write(b"not-lzma-at-all")
rc6, log6 = run_pack(src_db, dst)
ck(rc6 == 0, "بیس‌لاینِ ناخوانا ریلیز را نمی‌بندد (راه‌درمانِ همیشگی)")
ck("no row-count comparison" in log6, "بی‌مقایسه بودنِ شمارِ ردیف اعلام می‌شود")

# ۷) توابعِ خالص
ck(M.shrinking({"daily_prices": 5, "tape_history": None},
               {"daily_prices": 9, "tape_history": 9}) == [("daily_prices", 5, 9)],
   "shrinking فقط کاستیِ قطعی را برمی‌گرداند")
ck(M.shrinking({"daily_prices": 9}, {"daily_prices": 9}) == [], "برابر کاستی نیست")
ck(set(M.COUNT_TABLES) == {"daily_prices", "financial_statements",
                           "codal_notices", "tape_history"},
   "چهار جدولِ نگهبان ثابت مانده‌اند")
conn = sqlite3.connect(src_db)
counts = M.row_counts(conn)
conn.close()
ck(counts["daily_prices"] == FULL["daily_prices"], "row_counts شمارِ واقعی را می‌دهد")
conn2 = sqlite3.connect(":memory:")
ck(M.row_counts(conn2)["tape_history"] is None, "جدولِ نبود → None نه صفر")
conn2.close()

bad = [m for ok, m in CHECKS if not ok]
for ok, m in CHECKS:
    print(("  ok  " if ok else "  FAIL ") + m)
print("PACK-ROWCOUNT GUARD %s — %d/%d" % ("OK" if not bad else "FAILED",
                                          len(CHECKS) - len(bad), len(CHECKS)))
sys.exit(1 if bad else 0)
