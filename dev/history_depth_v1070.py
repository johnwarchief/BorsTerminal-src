#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/history_depth_v1070.py — تاریخچۀ منتشرشده هیچ‌وقت بریده نمی‌شود؛ سینک increment است.

چرا این گارد متولد شد (تصمیمِ مالک ۱۴۰۵-۰۷-۱۱، ابلاغ درِ کارِ #73):
هرسِ ۷۳۰روزه درِ `test_tsetmc.fetch_price_history` حذف شد — «Local DB باید هر مقدار
تاریخچۀ معتبرِ موجود برایِ هر نماد را نگه دارد؛ هیچ حذفِ مصنوعی بر اساسِ تعدادِ روز یا
بازۀ زمانی انجام نشود»، چون تاریخچۀ عمیق برایِ FTS، Pattern Engine و Backtesting لازم است.

حذفِ کفِ تنها یکِ نصفِ کار است؛ نصفِ دیگر خطرِ خودِ همین حذف است: اگر «از کجا
درخواست کنم» بی‌قاعده بماند، هر اجرا (هرسِ تاریخچۀ `/api/chart`، codalِ on-demand،
CLI) یکِ دانلودِ کامل می‌شود. پس چهار خواسته درِ این گارد قفل می‌شود:

  ۱) نمادِ با تاریخچۀ بلند — اولینِ تاریخِ او بعد از migration و بعد از سینک عوض نشود.
  ۲) نمادِ تازه — فقط آنچه منبع واقعاً دارد ذخیره شود؛ هیچ ردیفِ ساخته‌شده‌ای نباشد.
  ۳) اجرایِ دومِ سینک — تعدادِ ردیف‌ها عوض نشود (idempotent).
  ۴) اجرایِ دومِ نمادِ موجود — درخواست increment باشد (از روزِ بعدِ MAX(date))، نه از
     اولِ تاریخ؛ `backfill=True` تنها راهِ صریحِ عمق‌دادن است و فقط با فرمانِ مالک.

گارد بی‌شبکه است: پاسخِ CSV جعلی است و همان قاعده‌ی منبع را تقلید می‌کند (هر ردیفِ
منتشرشده از `from_` به بعد را برمی‌گرداند). اجرا:
    python dev/history_depth_v1070.py      → ۰ سبز، ۱ قرمز
"""
import datetime as dt
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import test_tsetmc as t  # noqa: E402

PASS = FAIL = 0

HEAD = ("<TICKER>,<DTYYYYMMDD>,<FIRST>,<HIGH>,<LOW>,<CLOSE>,<VALUE>,<VOL>,"
        "<OPENINT>,<PER>,<OPEN>,<LAST>")
# «منبع» جعلی: از ۱۳۹۰/۰۱/۰۱ (=2011-03-21) تا ۲۰۲۶-۰۹-۳۰، فقط شنبه تا چهارشنبه،
# و از ۲۰۲۴-۰۱-۰۲ تا ۲۰۲۴-۰۱-۰۵ معامله‌ای نبوده (تعطیلی) تا «ردیفِ نبود» هم پوشش داده شود.
START = dt.date(2011, 3, 21)
END = dt.date(2026, 9, 30)
HOLIDAY = {dt.date(2024, 1, 2), dt.date(2024, 1, 3), dt.date(2024, 1, 4), dt.date(2024, 1, 5)}


def source_days():
    d, out = START, []
    while d <= END:
        if d.weekday() < 5 and d not in HOLIDAY:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


DAYS = source_days()


def csv_for(from_yyyymmdd):
    lines = [HEAD]
    for i, d in enumerate(DAYS):
        ds = d.strftime("%Y%m%d")
        if ds < from_yyyymmdd:
            continue
        px = 1000.0 + i
        lines.append(f"<X>,{ds},{px:.0f},{px + 50:.0f},{px - 20:.0f},{px + 40:.0f},"
                     f"1e12,1e9,0,100.0,{px - 30:.0f},{px + 35:.0f}")
    return "\n".join(lines) + "\n"


class Resp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class FakeCDN:
    """یک sessionِ جعلی که URL درخواستی را ثبت می‌کند تا «از کجا خوانده شد» اندازه گرفته شود.

    `_polite` باید **صفتِ** کاذب باشد نه متد: `_rate_wait` آن را با `if not p` می‌سنجد و
    بعد `p.get(...)` می‌خواند — تابعِ بی‌پارامتر اینجا AttributeError می‌داد و اولین
    اجرای همین گارد را با صفرِ ردیف شکست داد (خطایِ خودِ فیکسچر، نه کدِ تولیدی).
    """

    def __init__(self):
        self.urls = []
        self._polite = None

    def get(self, url, headers=None, timeout=None, stream=None):
        self.urls.append(url)
        frm = url.rsplit("/", 1)[-1]
        return Resp(csv_for(frm))


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   " + what)
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  ← {detail}" if detail else ""))


def fresh_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    c = sqlite3.connect(path)
    t.create_schema(c)
    c.execute("INSERT INTO instruments (ins_code, l_val18, l_val30) VALUES (?,?,?)",
              ("111", "فولاد", "فولاد مبارکه"))
    c.execute("INSERT INTO instruments (ins_code, l_val18, l_val30) VALUES (?,?,?)",
              ("222", "نوزاد", "نمادِ تازه")
              )
    c.commit()
    return c, path


def first_and_count(c, sym):
    r = c.execute("SELECT MIN(date), MAX(date), COUNT(*) FROM price_history WHERE symbol=?",
                  (sym,)).fetchone()
    return r


def main():
    print("history_depth_v1070 | ردیف‌هایِ منبعِ جعلی:", len(DAYS))
    real_db = t.DB_PATH
    try:
        # ── ۱) نمادِ بلند: اولینِ تاریخ جابه‌جا نمی‌شود ──────────────────────
        c, p = fresh_db()
        t.DB_PATH = p
        cdn = FakeCDN()
        n1 = t.fetch_price_history("فولاد", s=cdn)
        mn, mx, cnt = first_and_count(c, "فولاد")
        ck(cnt == len(DAYS) and n1 == len(DAYS),
           "نخستینِ fetchِ نمادِ تازه = هر آنچه منبع دارد (بی‌کفِ ۷۳۰روزه)",
           f"rows={cnt} source={len(DAYS)}")
        ck(mn == START.strftime("%Y-%m-%d"),
           "اولینِ تاریخ == اولینِ روزِ منتشرشدهٔ منبع", str(mn))
        deep_before = (mn, mx, cnt)

        # ── ۲) اجرایِ دوم: increment، بی‌بازنویسی، بی‌تغییرِ شمار ─────────────
        cdn2 = FakeCDN()
        n2 = t.fetch_price_history("فولاد", s=cdn2)
        after = first_and_count(c, "فولاد")
        ck(cdn2.urls and cdn2.urls[0].rsplit("/", 1)[-1] ==
           (dt.date.fromisoformat(mx) + dt.timedelta(days=1)).strftime("%Y%m%d"),
           "درخواستِ دوم از روزِ بعدِ MAX(date) شروع می‌شود (نه از اولِ تاریخ)",
           str(cdn2.urls)[:120])
        ck(after == deep_before,
           "NEGATIVE CONTROL: اجرایِ دوم شمار/اولین/آخرینِ ردیف را عوض نکرد", str(after))
        ck(n2 == 0, "ردیفِ تازه‌ای نبود ⇒ صفرِ upsert (idempotent)", str(n2))

        # ── ۳) ردیف‌هایِ قدیمی هرگز حذف نمی‌شوند ────────────────────────────
        old_iso = (dt.date.fromisoformat(mn) + dt.timedelta(days=3)).isoformat()
        before_old = c.execute("SELECT COUNT(*) FROM price_history WHERE date < ?",
                              ((dt.date.fromisoformat(mn) + dt.timedelta(days=400)).isoformat(),)).fetchone()[0]
        ck(c.execute("SELECT 1 FROM price_history WHERE date=?", (old_iso,)).fetchone() is not None,
           "ردیفِ ۱۵سالِ پیش درِ بانک زنده است", old_iso)
        t.fetch_price_history("فولاد", s=FakeCDN())
        after_old = c.execute("SELECT COUNT(*) FROM price_history WHERE date < ?",
                             ((dt.date.fromisoformat(mn) + dt.timedelta(days=400)).isoformat(),)).fetchone()[0]
        ck(after_old == before_old,
           "سینکِ تازه ردیف‌هایِ پیشِ پنجره را نمی‌بَرَد (هرسِ بی‌بازگشت تمام شد)",
           f"{before_old} → {after_old}")

        # ── ۴) نمادِ تازه: فقط دادۀ واقعی، بی‌ساختن ─────────────────────────
        cdn3 = FakeCDN()
        n3 = t.fetch_price_history("نوزاد", s=cdn3)
        mn3, mx3, cnt3 = first_and_count(c, "نوزاد")
        ck(n3 == len(DAYS) and cnt3 == len(DAYS),
           "نمادِ نوزاد هم دقیقاً به اندازۀ منبع می‌گیرد", f"{cnt3} vs {len(DAYS)}")
        ck(mn3 == START.strftime("%Y-%m-%d") and mx3 == END.strftime("%Y-%m-%d"),
           "اولین/آخرین == اولین/آخرینِ انتشارِ منبع (چیزی قبل/بعد از آن ساخته نشده)",
           f"{mn3}..{mx3}")
        # روزهایِ تعطیلِ فیکسچر نباید کندل ساخته باشند
        hol = [d.isoformat() for d in HOLIDAY]
        got_hol = c.execute("SELECT COUNT(*) FROM price_history WHERE date IN (%s)"
                            % ",".join("?" * len(hol)), tuple(hol)).fetchone()[0]
        ck(got_hol == 0, "NEGATIVE CONTROL: روزِ بی‌معامله ردیف نمی‌گیرد (منبع آن را ندارد)",
           str(got_hol))
        weekends = c.execute("SELECT COUNT(*) FROM price_history WHERE strftime('%w', date) IN ('0','6')").fetchone()[0]
        ck(weekends == 0, "هیچ کندلِ آخرِ هفته‌ای ساخته نشده", str(weekends))

        # ── ۵) backfill صریح است، نه پیش‌فرض ────────────────────────────────
        cdn4 = FakeCDN()
        t.fetch_price_history("فولاد", s=cdn4)
        ck(cdn4.urls[0].rsplit("/", 1)[-1] != t.CSV_FLOOR,
           "حالتِ عادی هیچ‌وقت از کفِ منبع شروع نمی‌کند", str(cdn4.urls)[:120])
        cdn5 = FakeCDN()
        t.fetch_price_history("فولاد", s=cdn5, backfill=True)
        ck(cdn5.urls[0].rsplit("/", 1)[-1] == t.CSV_FLOOR,
           "فقط backfill=True از اولِ تاریخ می‌خواند (عمق دادن با فرمانِ مالک)",
           str(cdn5.urls)[:120])

        # ── ۶) عمق‌سنجیِ واقعی: اندازه‌گیریِ حجمِ ردیف‌هایِ از‌دست‌رفته ───────
        # نه حدس: چند ردیفِ منبع *الان* درِ بانکِ کاری نیست؟ (خواندنِ read-only)
        c.close()
        os.unlink(p)
        try:
            from pathlib import Path
            ro = sqlite3.connect(Path(real_db).as_uri() + "?mode=ro", uri=True, timeout=30)
            spans = ro.execute(
                "SELECT COUNT(DISTINCT symbol), MIN(date), MAX(date), COUNT(*) FROM price_history"
            ).fetchone()
            older = ro.execute("SELECT COUNT(*) FROM price_history WHERE date < ?",
                               (((dt.date.today() - dt.timedelta(days=730)).isoformat()),)).fetchone()[0]
            print(f"\n[measure] بانکِ کاری: نماد={spans[0]:,} بازه={spans[1]}..{spans[2]} "
                  f"ردیف={spans[3]:,} | ردیفِ پیشِ ۷۳۰روزِ امروز={older:,}")
            ro.close()
        except Exception as e:  # noqa: BLE001 — بانکِ کاری درِ ماشینِ تست ممکن است نباشد
            print("\n[measure] بانکِ کاری خوانده نشد:", type(e).__name__, str(e)[:90])
    finally:
        t.DB_PATH = real_db

    print(f"\nhistory_depth_v1070: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
