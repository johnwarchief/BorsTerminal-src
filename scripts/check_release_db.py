#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اعتبارسنجی، تازگی‌سنجی و فشرده‌سازیِ market.db به‌عنوانِ baseline ریلیز.

قرارداد: اگر این اسکریپت با کدِ غیرِ صفر خارج شود، release.ps1 باید
متوقف شود و market.db.lzmaیِ commit‌شده دست‌نخورده بماند.

چرا یک فایلِ جدا: release.ps1 این منطق را به‌صورتِ اسکریپتِ درون‌خطی با
کوتیشنِ دوتایی اجرا می‌کرد، و PowerShell 5.1 کوتیشنهایِ جاسازی‌شده را
هنگامِ فراخوانیِ EXE بومی می‌بلعد:
    d=open(market.db.lzma,rb).read()   ← NameError: name 'market' is not defined
    print(                              ← SyntaxError: '(' was never closed
یعنی هر سه مرحلهٔ اعتبارسنجی/فشرده‌سازی/round-trip در عمل هرگز کار
نمی‌کردند و فقط بهخاطرِ همان خطایِ نحوی، ریلیز با یک پیامِ گمراه‌کننده
متوقف می‌شد. انتقال به فایل، این طبقهٔ باگ را کلاً حذف می‌کند.

چرا سن (DATA-AGE-1): baseline هرگز در CI ساخته نمی‌شود — release.ps1 آن را
از market.dbِ محلیِ همین ماشین می‌گیرد و codal.db.lzma هم از تازه‌ترین
ریلیزِ دارایِ فایل جلو برده می‌شود. پس یک ریلیزِ صرفاً UI می‌تواند تابلو را
رویِ دادهٔ دو ماهِ قبل بفرستد و هیچ مرحله‌ای متوجه نشود. از این رو:
  • سنِ هر چهار چسبِ میلادی گزارش می‌شود (پیش‌فرض هشدار، نه خطا);
  • فشرده‌سازی وقتی رد می‌شود که منبع از baseline کهنه‌تر باشد — این تنها
    حالتی است که استثنا ندارد (یعنی تاریخِ معاملاتیِ از دست رفته).

سن از رویِ چسب‌های میلادی حساب می‌شود و از هیچ فیلدِ جلالی استفاده نمی‌شود
(period_end، publish_date، monthly_sales.year): تبدیلِ جلالیِ موردِاعتمادی
در ریپو نیست، و تبدیلِ دست‌سازی که یک‌بار خطا کند عددِ «روز» را
گمراه‌کننده می‌کند. ساعتِ محلیِ ماشینِ سازنده و stampهایِ fetcher یکسان
اند؛ در رانرِ CI اختلافِ ۳:۳۰ ساعت نسبت به تهران در آستانه‌ای که با «روز»
سنجیده می‌شود بی‌اثر است.

حالت‌ها:
    python scripts/check_release_db.py             # فقط اعتبارسنجی + سن
    python scripts/check_release_db.py --pack      # + فشرده‌سازی
    python scripts/check_release_db.py --baseline  # سنِ market.db.lzmaیِ commit‌شده
    python scripts/check_release_db.py --strict    # کهنه = کدِ خروجِ غیرِ صفر
"""
import argparse
import lzma
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime

# market_totals = کلِ ارزشِ بازارِ رسمیِ TSETMC. بدون آن، نصبِ تازه تا نخستین
# سینکِ موفق روی جمعِ تابلو می‌نشیند که ۲.۸ برابرِ عددِ واقعی است.
REQUIRED = {"instruments", "daily_prices", "financial_statements", "market_totals"}
MIN_FS = 1000

# (کلید، کوئری، نوعِ مقدار، سقفِ روز). codal سقفش بالاتر است چون
# اسنپ‌شاتش با scripts/build_codal_snapshot.py جدا ساخته می‌شود، نه در هر
# ریلیز. None یعنی «داده نیست» و هرگز صفر یا رد نمی‌شود.
STAMPS = (
    ("last_trading_day", "SELECT MAX(d_even) FROM daily_prices", "dayint", 7),
    ("market_synced_at", "SELECT MAX(fetched_at) FROM daily_prices", "stamp", 7),
    ("market_totals_at", "SELECT MAX(updated_at) FROM market_totals", "stamp", 7),
    ("codal_synced_at", "SELECT MAX(fetched_at) FROM codal_notices", "stamp", 21),
)

_EPOCH = datetime(1970, 1, 1)
# نصفِ روز، نه صفر: تهران ۳:۳۰+ است و رانرِ CI صفرِ UTC؛ تازگیِ داده نباید
# به‌خاطرِ ساعتِ ماشین «آینده» خوانده شود.
FUTURE_TOLERANCE = 0.5
SRC = "market.db"
DST = "market.db.lzma"

# شمارِ ردیفِ این جدول‌ها «دادهٔ روز» است، نه آرایهٔ جانبی. بیس‌لاین با هر
# نشستِ تازه بزرگ‌تر می‌شود، پس کم‌شدنِ هر کدام یعنی روزها/گزارش‌هایی که در
# فایلِ commit‌شده هست از بیس‌لاینِ نو بیرون می‌افتد — دقیقاً همان چیزی که
# PACK_REFUSED برایِ تاریخِ آخرین نشست نگهبانی‌اش می‌کند، ولی تاریخِ تنها
# نشستِ آخر این را نمی‌بیند. سنجشِ ۱۴۰۵-۰۷-۰۹: daily_prices این ماشین ۷۲٬۲۸۰ در
# برابر ۸۷٬۱۴۶ِ فایلِ منتشرشده، و tape_historyِ بانکِ نصبی ۱۵۱٬۳۵۶ در برابر
# ۱۸۳٬۹۷۳ — هر دو «تازه» بودند و --pack بی‌استثنا قبول می‌کرد.
COUNT_TABLES = ("daily_prices", "financial_statements", "codal_notices", "tape_history")


def row_counts(conn, tables=COUNT_TABLES):
    """نامِ جدول -> شمارِ ردیف؛ None یعنی جدول نیست یا خوانده نمی‌شود.

    None با صفر یکی نیست: بانکِ بی‌`tape_history` «خالی» نیست، «ناشناخته» است و
    بی‌دلیل نمی‌تواند ریلیز را ببندد.
    """
    out = {}
    for t in tables:
        try:
            out[t] = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        except sqlite3.Error:
            out[t] = None
    return out


def shrinking(src_counts, base_counts, tables=COUNT_TABLES):
    """فقط جدول‌هایی که عددشان قطعیِ کمتر است؛ خروجیِ ناشناخته رد نمی‌شود."""
    bad = []
    for t in tables:
        a, b = src_counts.get(t), base_counts.get(t)
        if isinstance(a, int) and isinstance(b, int) and a < b:
            bad.append((t, a, b))
    return bad


def _ro(path):
    return sqlite3.connect("file:%s?mode=ro" % path.replace(os.sep, "/"), uri=True)


def _as_dt(kind, raw):
    """چسبِ میلادی -> datetime؛ هر مقدارِ نامعتبر None (نه صفر)."""
    if raw is None:
        return None
    if kind == "dayint":
        try:
            return datetime.strptime("%08d" % int(raw), "%Y%m%d")
        except (TypeError, ValueError):
            return None
    s = str(raw).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def ages(conn, now=None):
    """کلید -> تعدادِ روز (float) یا None برایِ «دادهٔ قابلِ استفاده نیست»."""
    now = now or datetime.now()
    out = {}
    for key, sql, kind, _lim in STAMPS:
        try:
            raw = conn.execute(sql).fetchone()[0]
        except sqlite3.Error:
            raw = None
        dt = _as_dt(kind, raw)
        out[key] = None if dt is None else (now - dt).total_seconds() / 86400.0
    return out


def report(conn, now=None, tag="src"):
    """چاپِ سن و برگرداندنِ کلیدهایی که از سقفِ خود رد شده‌اند.

    کلیدِ نامعلوم به فهرستِ ردشده اضافه نمی‌شود: نبودِ داده، پیر بودن نیست.
    سنِ منفی تا اندازهٔ یک اختلافِ منطقهٔ زمانی (FUTURE_TOLERANCE) خطا نیست:
    ساعتِ رانرِ CI برابر UTC است و stampها محلیِ تهران (+۳:۳۰)، پس baselineای
    که همین چند دقیقه پیش بسته شده «−۰٫۱ روز» می‌شود. بدونِ این تلورانس،
    دقیقاً تازه‌ترین — و بهترین — داده «خراب» گزارش می‌شد و دروازه به نویز
    تبدیل می‌گشت. چیزی که بیشتر از تلورانس در آینده باشد واقعاً غلط است.
    """
    a = ages(conn, now)
    over = []
    for key, _sql, _kind, lim in STAMPS:
        d = a.get(key)
        if d is None:
            print("AGE_UNKNOWN %s.%s (no usable Gregorian stamp)" % (tag, key))
        elif d < -FUTURE_TOLERANCE:
            print("AGE_FUTURE %s.%s days=%.1f (clock or stamp is wrong)" % (tag, key, d))
            over.append(key)
        else:
            d = max(d, 0.0)
            print("AGE_%s %s.%s days=%.1f limit=%d" %
                  ("STALE" if d > lim else "OK", tag, key, d, lim))
            if d > lim:
                over.append(key)
    return over


def freshness_key(conn):
    """کلیدِ مقایسهٔ نسبیِ دو دیتابیس: (آخرین روزِ معاملاتی، لحظهٔ سینک).

    برایِ «منبع کهنه‌تر از baseline» به‌کار می‌رود؛ این مقایسه به ساعتِ درستِ
    ماشین نیاز ندارد، پس در CI هم معنا دارد. None یعنی چیزی برایِ مقایسه
    نیست — و در آن حالت رد نمی‌کنیم.
    """
    try:
        day = conn.execute("SELECT MAX(d_even) FROM daily_prices").fetchone()[0]
        ts = conn.execute("SELECT MAX(fetched_at) FROM daily_prices").fetchone()[0]
    except sqlite3.Error:
        return None
    day_i = int(day) if day else 0
    dt = _as_dt("stamp", ts)
    if day_i == 0 and dt is None:
        return None
    return (day_i, dt or _EPOCH)


def _fmt_key(k):
    return "none" if k is None else "%d@%s" % (k[0], (k[1] or _EPOCH).isoformat(" "))


def check_structure(conn, tag):
    """جدول‌هایِ لازم + حداقلِ رکوردِ صورتِ مالی. rc=0 یعنی قابلِ انتشار."""
    try:
        have = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        fs = conn.execute(
            "SELECT COUNT(*) FROM financial_statements").fetchone()[0] \
            if "financial_statements" in have else 0
    except sqlite3.Error as e:
        print("SRC_BAD: %r" % e)
        return 1
    miss = sorted(REQUIRED - have)
    if miss:
        print("%s_INCOMPLETE missing=%s" % (tag.upper(), ",".join(miss)))
        return 1
    if fs < MIN_FS:
        print("%s_TOO_SMALL financial_statements rows=%d" % (tag.upper(), fs))
        return 1
    print("%s_OK financial_statements rows=%d" % (tag.upper(), fs))
    return 0


def _open_src():
    try:
        return _ro(SRC)
    except Exception as e:
        print("SRC_BAD: %r" % e)
        return None


def validate():
    """(rcِ ساختار، کلیدهایِ کهنه). rcِ ساختار هیچ‌وقت با «کهنه» یکی نمی‌شود.

    تفکیکِ عمدی است: اگر هر دو یک کدِ خروج بدهند، main برایِ بخشودنِ دادهٔ
    کهنه، دیتابیسِ بی‌جدول را هم می‌بخشد و ریلیزِ خراب رد می‌شود.
    """
    conn = _open_src()
    if conn is None:
        return 1, []
    try:
        rc = check_structure(conn, "src")
        if rc:
            return rc, []
        over = report(conn, tag="src")
        print("STALE_COUNT=%d stale=%s" % (len(over), ",".join(over) or "-"))
        return 0, over
    finally:
        conn.close()


@contextmanager
def open_lzma(path):
    """baselineیِ فشرده را رویِ فایلِ موقت می‌گشاید و می‌بندد."""
    with open(path, "rb") as f:
        raw = lzma.decompress(f.read())
    fd, tmp = tempfile.mkstemp(suffix=".db", prefix="chk_baseline_")
    os.close(fd)
    try:
        with open(tmp, "wb") as f:
            f.write(raw)
        conn = _ro(tmp)
        try:
            yield conn
        finally:
            conn.close()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def baseline():
    """سنجشِ خودِ market.db.lzma — تنها راهی که CI بدونِ سینک دارد."""
    if not os.path.exists(DST):
        print("BASELINE_MISSING %s not in this tree" % DST)
        return 0
    conn = _open_src() if os.path.exists(SRC) else None
    try:
        with open_lzma(DST) as b:
            rc = check_structure(b, "baseline")
            over = report(b, tag="baseline")
            bk = freshness_key(b)
        print("BASELINE_KEY %s" % _fmt_key(bk))
        if conn is not None:
            sk = freshness_key(conn)
            print("SOURCE_KEY %s" % _fmt_key(sk))
            if sk and bk and sk < bk:
                print("BASELINE_NEWER source would lose market days — repack first")
                rc = rc or 1
        print("STALE_COUNT=%d stale=%s" % (len(over), ",".join(over) or "-"))
        return rc
    except Exception as e:
        print("BASELINE_BAD: %r" % e)
        return 1
    finally:
        if conn is not None:
            conn.close()


def pack(allow_shrink=False):
    """فشرده‌سازی + round-trip verification. baseline قبلی حفظ می‌شود."""
    src, dst = SRC, DST
    if not os.path.exists(src):
        print("[pack] market.db not found (skip)")
        return 0

    # منبع از baseline کهنه‌تر = روزهایِ معاملاتی از دست می‌رود. این تنها
    # حالتی است که بی‌استثنا رد می‌کنیم، چون عددِ مطلقِ «۸ روز کهنه» می‌تواند
    # تعطیلاتِ رسمی باشد ولی «کهنه‌تر ازِ فایلِ commit‌شده» هیچ توجیهی ندارد.
    conn = _open_src()
    if conn is not None:
        try:
            sk = freshness_key(conn)
        finally:
            conn.close()
        if os.path.exists(dst):
            try:
                with open_lzma(dst) as b:
                    bk = freshness_key(b)
            except Exception as e:
                print("[pack] baseline unreadable (%r) — no age comparison" % e)
                bk = None
            print("[pack] freshness src=%s baseline=%s" % (_fmt_key(sk), _fmt_key(bk)))
            if sk and bk and sk < bk:
                print("PACK_REFUSED source is older than the committed baseline; "
                      "market.db.lzma left untouched. Sync market.db first.")
                return 1

    # سنِ «آخرین نشست» تنها نشانه نیست: بانکِ همین ماشین با آخرینِ نشستِ دیروز
    # هم می‌تواند ۱۴٬۰۰۰ ردیفِ کم‌تر از فایلِ منتشرشده داشته باشد و بیس‌لاینِ
    # کاربرها را کوتاه کند. بی‌--allow-shrink رد می‌کنیم و فایل را دست نمی‌زنیم.
    if os.path.exists(dst):
        c_src = _open_src()
        try:
            sc = row_counts(c_src) if c_src is not None else {}
        finally:
            if c_src is not None:
                c_src.close()
        try:
            with open_lzma(dst) as b:
                bc = row_counts(b)
        except Exception as e:
            print("[pack] baseline unreadable (%r) — no row-count comparison" % e)
            bc = {}
        if sc and bc:
            print("[pack] rows " + " ".join(
                "%s=%s/%s" % (t, sc.get(t), bc.get(t)) for t in COUNT_TABLES))
            bad = shrinking(sc, bc)
            if bad:
                for t, a, b_ in bad:
                    print("PACK_SHRINK table=%s source=%d baseline=%d lost=%d"
                          % (t, a, b_, b_ - a))
                if not allow_shrink:
                    print("PACK_REFUSED rows: market.db has fewer rows than the "
                          "committed baseline; market.db.lzma left untouched. "
                          "Sync first, or pass --allow-shrink for an intentional dedupe.")
                    return 1
                print("PACK_ALLOWED_SHRINK --allow-shrink: کاستیِ ردیف‌ها عمدی است")

    if os.path.exists(dst):
        shutil.copy2(dst, dst + ".bak")
        print("[pack] backed up previous market.db.lzma -> market.db.lzma.bak")

    raw = open(src, "rb").read()
    # اتمی: رویِ .new فشرده می‌کنیم، round-trip را همان‌جا می‌سنجیم و فقط بعد
    # جای baseline می‌گذاریم. پیش از این، باز کردنِ dst با "wb" فایلِ
    # commit‌شده را همان اولِ کار صفر بایت می‌کرد؛ یک Ctrl+C (یا کرش) وسطِ
    # فشرده‌سازی، بیس‌لاینِ ریلیز را نابود می‌کرد — و در run بعدی همان فایلِ
    # صفر‌بایتی رویِ .bakِ سالم کپی می‌شد، یعنی مسیرِ از‌دست‌رفتنِ کامل.
    tmp = dst + ".new"
    with open(tmp, "wb") as f:
        f.write(lzma.compress(raw, preset=9))
    print("  lzma MB %.1f" % (os.path.getsize(tmp) / 1048576.0))

    # round-trip: باید دقیقاً همانیِ منبع را برگرداند؛ وگرنه baselineیِ
    # قبلی دست‌نخورده می‌ماند.
    ok = lzma.decompress(open(tmp, "rb").read()) == raw
    if not ok:
        os.remove(tmp)
        print("[pack] round-trip mismatch — baseline left untouched")
        return 1
    os.replace(tmp, dst)
    print("  round-trip OK")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", action="store_true",
                    help="also compress market.db -> market.db.lzma")
    ap.add_argument("--baseline", action="store_true",
                    help="validate + age the committed market.db.lzma (no market.db needed)")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero when any stamp is past its age limit")
    ap.add_argument("--allow-shrink", action="store_true",
                    help="with --pack: accept fewer rows than the committed baseline "
                         "(intentional dedupe/housekeeping only)")
    args = ap.parse_args()

    if args.baseline:
        return baseline()

    hard, stale = validate()
    if hard:
        return hard
    # کهنه‌بودن به‌تنهایی ریلیز را نمی‌بندد: تعطیلاتِ نوروزی و ریلیزِ صرفاً UI
    # هر دو مشروع‌اند. خطِ STALE_COUNT را CI به ::warning:: تبدیل می‌کند و
    # --strict همان هشدار را برایِ کاری که باید داده تازه کند خطا می‌کند.
    if stale and args.strict:
        print("STRICT: stale stamps=%s" % ",".join(stale))
        return 1
    return pack(allow_shrink=args.allow_shrink) if args.pack else 0


if __name__ == "__main__":
    sys.exit(main())
