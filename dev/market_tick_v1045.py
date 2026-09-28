"""dev/market_tick_v1045.py — تیکِ زندۀ تابلو: پنج‌ثانیه، یکِ درخواست، بی‌سوختنِ صف‌ها

چرا: مالک تابلو را رویِ سایت ثانیه‌به‌ثانیه تکان می‌خورد دید، ولی برنامه تا
سینکِ کاملِ ۹۰ ثانیه‌ایِ بعدی هیچ عددی را در بانک عوض نمی‌کرد — پولینگِ
پنج‌ثانیه‌ایِ فرانت درست همان بدنه را ۳۰۴ می‌گرفت. درمان: حلقۀ تیکِ ۵
ثانیه‌ای در app.py که test_tsetmc.tick_live را صدا می‌زند.

این گارد بدونِ شبکه و بدونِ market.dbِ واقعی می‌دود (CI بی‌بانک) و چهار چیز
را ثابت می‌کند که یک ویرایشِ بی‌دقت می‌شکند:

  • تیک داخلِ پنجره فقط market_watch/daily_prices را می‌نویسد — نه
    instruments/boards/client_type؛ و ارقامش عینِ همان _mw_row است که سینک
    کامل می‌نویسد (یکِ نگاشت، نه دو تا).
  • بیرونِ پنجره (پنجشنبه/جمعه یا ۱۲:۳۰ به بعد) هیچ درخواستی زده نمی‌شود و
    هیچ سطر عوض نمی‌شود — صف‌هایِ حفظ‌شدۀ بستۀ بازار سوختنی نیستند.
  • پاسخِ خالی (۴۲۹/قطعی) یعنی «این تیک رد» — بانک دست‌نخورده می‌ماند و
    تیکِ بعدی صفرِ جعلی نمی‌سازد.
  • _save_market_snapshot دیگر بدوزشِ مستقیمِ ردیف ندارد و از _mw_row
    می‌خواند (منبعِ واحدِ فرمول).
"""
import datetime as _real_dt
import os
import sqlite3
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import test_tsetmc as T  # noqa: E402

FAILS = []


def ck(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


class _Day:
    def __init__(self, wd, ymd):
        self._wd, self._ymd = wd, ymd

    def weekday(self):
        return self._wd

    def strftime(self, fmt):
        return self._ymd if fmt == "%Y%m%d" else self._ymd


class _Now:
    def __init__(self, hm, stamp):
        self._hm, self._stamp = hm, stamp

    def strftime(self, fmt):
        return self._hm if fmt == "%H%M" else self._stamp


class _DateMod:
    today_val = _Day(0, "20260928")

    @classmethod
    def today(cls):
        return cls.today_val


class _DateTimeMod:
    now_val = _Now("1030", "2026-09-28 10:30:00")

    @classmethod
    def now(cls):
        return cls.now_val


def set_clock(wd=0, hhmm="1030", ymd="20260928"):
    _DateMod.today_val = _Day(wd, ymd)
    _DateTimeMod.now_val = _Now(hhmm, "2026-09-28 %s:%s:00" % (hhmm[:2], hhmm[2:]))
    T.datetime = types.SimpleNamespace(date=_DateMod, datetime=_DateTimeMod)


def mw_row(ins="X1", pcl=100.0, qtj=500.0, pc=2.0, ztt=7.0, h=103000, d=20260928):
    return {"insCode": ins, "lva": "نام", "lvc": "شرکت", "csv": "S1", "dEven": d,
            "hEven": h, "pcl": pcl, "pdv": 90.0, "py": 98.0, "pf": 99.0,
            "pmn": 95.0, "pmx": 105.0, "pMin": 92.0, "pMax": 110.0,
            "qtj": qtj, "qtc": pcl * qtj, "ztt": ztt, "pc": pc, "eps": 5.0,
            "pe": 10.0, "ztd": 1000.0, "bv": 50.0}


FETCHES = []


def fake_fetch_ok(s, url, key=None, timeout=90):
    FETCHES.append(url)
    return fake_fetch_ok.rows


def fake_fetch_empty(s, url, key=None, timeout=90):
    FETCHES.append(url)
    return []


def fresh_db():
    conn = sqlite3.connect(":memory:")
    T.create_schema(conn)
    T.ensure_daily_tran_column(conn)
    import mstat_engine
    mstat_engine.ensure_schema(conn)
    conn.commit()
    return conn


def run():
    set_clock()
    orig_pg = T.polite_get
    try:
        # ── ۱) تیکِ سالم: فقط تابلو و قیمت‌هایِ همان روز ────────────────────
        conn = fresh_db()
        FETCHES.clear()
        fake_fetch_ok.rows = [mw_row(pcl=100.0, qtj=500.0, pc=2.0),
                              mw_row(ins="X2", pcl=200.0, qtj=60.0, pc=-1.0)]
        T.polite_get = fake_fetch_ok
        n = T.tick_live(conn)
        ck("تیکِ داخلِ پنجره ردیف‌ها را می‌نویسد", n == 2)
        ck("یکِ درخواستِ تابلو (نه شش‌تاییِ سینک)", len(FETCHES) == 1 and "GetMarketWatch?market=0" in FETCHES[0])
        r = conn.execute("SELECT p_closing, q_tot_tran, price_change, fetched_at FROM market_watch WHERE ins_code='X1'").fetchone()
        ck("market_watchِ آخرین/حجم/تغییر٪ نوشته شد", r == (100.0, 500.0, 2.0, "2026-09-28 10:30:00"))
        r2 = conn.execute("SELECT p_closing, q_tot_tran FROM daily_prices WHERE ins_code='X2' AND d_even=20260928").fetchone()
        ck("daily_pricesِ همان نشست هم هم‌خط شد", r2 == (200.0, 60.0))
        ck("instruments دست‌نخورده (کارِ سینکِ کامل است)",
           conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0] == 0)
        ck("client_type دست‌نخورده (کارِ سینکِ کامل است)",
           conn.execute("SELECT COUNT(*) FROM client_type").fetchone()[0] == 0)

        # ── ۲) تیکِ دوم با عددِ تازه‌تر: بازنویسیِ زنده ────────────────────
        set_clock(hhmm="1035")
        fake_fetch_ok.rows = [mw_row(pcl=101.0, qtj=550.0, pc=3.0)]
        n = T.tick_live(conn)
        r = conn.execute("SELECT p_closing, q_tot_tran FROM market_watch WHERE ins_code='X1'").fetchone()
        ck("تیکِ بعدی همان سطر را تازه می‌کند (نه ردیفِ دوتایی)", n == 1 and r == (101.0, 550.0))
        ck("یکِ کلیدِ PrimaryKey: مجموعِ سطرهایِ market_watch ثابت",
           conn.execute("SELECT COUNT(*) FROM market_watch").fetchone()[0] == 2)

        # ── ۳) درب‌هایِ زمانی: هیچِ درخواستی بیرونِ پنجره ──────────────────
        for wd, tag in ((3, "پنجشنبه"), (4, "جمعه")):
            set_clock(wd=wd)
            FETCHES.clear()
            ck("تعطیلیِ %s: صفرِ درخواست، صفرِ نوشتن" % tag,
               T.tick_live(conn) == 0 and not FETCHES)
        set_clock(hhmm="1230")
        FETCHES.clear()
        ck("۱۲:۳۰ به بعد: درخواست نمی‌زنیم (صف‌هایِ حفظیِ main نسوزد)",
           T.tick_live(conn) == 0 and not FETCHES)
        v = conn.execute("SELECT p_closing FROM market_watch WHERE ins_code='X1'").fetchone()[0]
        ck("بعدازظهر عددِ تابلو همانِ بستۀ بازار ماند", v == 101.0)

        # ── ۴) پاسخِ خالی (۴۲۹/قطعی): رد، نه صفرِ جعلی ────────────────────
        set_clock(hhmm="1040")
        T.polite_get = fake_fetch_empty
        FETCHES.clear()
        ck("پاسخِ خالی ⇒ تیک رد می‌شود", T.tick_live(conn) == 0)
        v = conn.execute("SELECT p_closing FROM market_watch WHERE ins_code='X1'").fetchone()[0]
        ck("عددِ بانک با پاسخِ خالی پاک نشد", v == 101.0)

        # ── ۵) یکِ نگاشت: بدنۀ سینک هم دیگر دوختِ مستقیم ندارد ─────────────
        src_txt = open(os.path.join(os.path.dirname(T.__file__), "test_tsetmc.py"),
                       encoding="utf-8").read()
        ck("_save_market_snapshot از _mw_row می‌خواند (منبعِ واحدِ فرمول)",
           "_mw_row(r, last_d_even, today, now, sectors, ptypes)" in src_txt
           and "watch.append((ins, d, num(r.get(\"hEven\"))" not in src_txt)

        # ── ۶) تیک بدونِ conn: مسیرِ DB_PATH کرش نمی‌کند (اورقِ sqlite نه) ──
        # در CI بانکِ واقعی نیست؛ نبودِ فایل باید استثنا بدهد و حلقه بلعَد —
        # این را حلقۀ app.py تضمین می‌کند، نه tick_live. اینجا فقط مطمئن می‌شویم
        # tick_live خودش هیچ‌وقت سطرِ نصفه نمی‌گذارد:
        conn2 = fresh_db()
        T.polite_get = fake_fetch_ok
        fake_fetch_ok.rows = [mw_row(), {"insCode": None}]
        n = T.tick_live(conn2)
        ck("ردیفِ بی‌insCode نادیده می‌گذرد، نوشتنِ نصفه نداریم", n == 1)

        conn.close()
        conn2.close()
    finally:
        T.polite_get = orig_pg
    passed = 16 - len(FAILS)
    print("\nmarket_tick_v1045: %d passed / %d failed" % (passed, len(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
