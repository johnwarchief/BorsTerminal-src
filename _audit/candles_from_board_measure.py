"""سنجشِ پیش‌از‌پسِ «کندل از تابلو» رویِ یک کپیِ خواندنی از بانکِ نصبی.

چرا: ادعایِ §۱۷ PLAN باید با اعدادِ خودِ بانکِ کاربر اثبات شود، نه با فیکسچرِ
گارد. این اسکریپت هیچ‌وقت رویِ `market.db` واقعی نمی‌نویسد: اول با APIِ
backup یک کپیِ متعارف می‌سازد و بعد همان projection را رویِ کپی می‌دود.
"""
import os
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_tsetmc import sync_price_history_from_daily, normalize_price_history_geometry  # noqa: E402

SRC = os.path.join(os.environ["LOCALAPPDATA"], "Programs",
                   "BorsTerminal Ultimate", "market.db")
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proj_final.db")

# همان شرطِ normalize_price_history_geometry (۱۴۰۵-۰۷-۰۸):
BAD_SQL = ("SELECT COUNT(*) FROM price_history WHERE open > 0 AND close > 0 AND ("
           "  COALESCE(high,0) < MAX(open, close) OR COALESCE(low,0) = 0"
           "  OR COALESCE(low,999999999999) > MIN(open, close) OR COALESCE(high,0) <= 0"
           ")")


def snap(conn):
    r = conn.execute("SELECT COUNT(*), MAX(date) FROM price_history").fetchone()
    bad = conn.execute(BAD_SQL).fetchone()[0]
    syms = conn.execute("SELECT COUNT(DISTINCT symbol) FROM price_history").fetchone()[0]
    last = conn.execute("SELECT MAX(d_even) FROM daily_prices").fetchone()[0]
    return {"rows": r[0], "last_date": r[1], "bad_geom": bad,
            "symbols": syms, "last_session": last}


def main():
    if not os.path.exists(SRC):
        print("بانکِ نصبی پیدا نشد:", SRC)
        return 1
    src = sqlite3.connect(SRC)
    dst = sqlite3.connect(DST)
    src.backup(dst)
    src.close()
    conn = dst
    before = snap(conn)
    print("پیش ازِ projection:", before)

    t = time.time()
    res = sync_price_history_from_daily(conn, full=True)
    conn.commit()
    catch_s = time.time() - t
    mid = snap(conn)
    print("پس ازِ catch-up:", mid, "|", res, "in %.2fs" % catch_s)

    t = time.time()
    fixed = normalize_price_history_geometry(conn)
    conn.commit()
    geom_s = time.time() - t
    after = snap(conn)
    print("سایه‌هایِ اصلاح‌شده: %s در %.2fs" % (fixed, geom_s))
    print("پس ازِ geometry:", after)

    t = time.time()
    res2 = sync_price_history_from_daily(conn, full=False)
    conn.commit()
    print("فراخوانِ دوم (latest):", res2, "در %.3fs" % (time.time() - t))
    print("دو‌بار اجرا == یک‌بار؟", snap(conn) == after)

    for sym in ("فولاد", "وبملت", "خودرو"):
        row = conn.execute(
            "SELECT date,open,high,low,close,volume FROM price_history "
            "WHERE symbol=? ORDER BY date DESC LIMIT 1", (sym,)).fetchone()
        print("آخرین کندلِ", sym, ":", row)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
