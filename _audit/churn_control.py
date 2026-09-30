# -*- coding: utf-8 -*-
"""کنترلِ منفیِ churnِ کش: نوشتنِ ردیفِ نشستِ جاری در price_history امضایِ فعلی
را عوض می‌کند، درحالی‌که امضایِ «فقط نشست‌هایِ پیشین» نباید تکان بخورد.
رویِ کپیِ بانک اجرا می‌شود، هرگز رویِ بانکِ نصبی."""
import json
import sqlite3
import sys

ISO_DATE = ("(SELECT printf('%04d-%02d-%02d', d/10000, (d/100)" + "%" + "100, d" + "%" + "100) "
            "FROM (SELECT MAX(d_even) AS d FROM market_watch))")

SIG_OLD = (
    "SELECT (SELECT MAX(d_even) FROM market_watch),"
    "       (SELECT COUNT(*) FROM price_history),"
    "       (SELECT MAX(rowid) FROM price_history),"
    "       (SELECT SUM(close)+SUM(high)+SUM(low)+SUM(volume) FROM price_history),"
    "       (SELECT COUNT(*) FROM daily_prices WHERE d_even < (SELECT MAX(d_even) FROM market_watch)),"
    "       (SELECT SUM(p_closing)+SUM(q_tot_tran) FROM daily_prices"
    "         WHERE d_even < (SELECT MAX(d_even) FROM market_watch)),"
    "       (SELECT COUNT(*) FROM tape_history),"
    "       (SELECT SUM(price_max)+SUM(price_min)+SUM(q_tot_tran5j) FROM tape_history)"
)

SIG_NEW = (
    "SELECT (SELECT MAX(d_even) FROM market_watch),"
    "       (SELECT COUNT(*) FROM price_history WHERE date < (%s)),"
    "       (SELECT MAX(rowid) FROM price_history WHERE date < (%s)),"
    "       (SELECT SUM(close)+SUM(high)+SUM(low)+SUM(volume) FROM price_history WHERE date < (%s)),"
    "       (SELECT COUNT(*) FROM daily_prices WHERE d_even < (SELECT MAX(d_even) FROM market_watch)),"
    "       (SELECT SUM(p_closing)+SUM(q_tot_tran) FROM daily_prices"
    "         WHERE d_even < (SELECT MAX(d_even) FROM market_watch)),"
    "       (SELECT COUNT(*) FROM tape_history),"
    "       (SELECT SUM(price_max)+SUM(price_min)+SUM(q_tot_tran5j) FROM tape_history)"
) % (ISO_DATE, ISO_DATE, ISO_DATE)


def sigs(conn):
    return conn.execute(SIG_OLD).fetchone(), conn.execute(SIG_NEW).fetchone()


def main(path):
    out = {"db": path}
    conn = sqlite3.connect(path)
    live = conn.execute("SELECT MAX(date) FROM price_history").fetchone()[0]
    n_live = conn.execute("SELECT COUNT(*) FROM price_history WHERE date=?", (live,)).fetchone()[0]
    out["live_date_in_price_history"] = live
    out["rows_for_live_date"] = n_live
    before_old, before_new = sigs(conn)

    # همان کاری که سینکِ کندل درِ نشستِ باز می‌کند: بازنویسیِ ردیف‌هایِ امروز.
    conn.execute("UPDATE price_history SET volume = volume * 1.001 WHERE date = ?", (live,))
    conn.commit()
    after_old, after_new = sigs(conn)

    out["old_changed"] = before_old != after_old
    out["old_changed_fields"] = [i for i in range(len(before_old)) if before_old[i] != after_old[i]]
    out["new_changed"] = before_new != after_new
    out["new_changed_fields"] = [i for i in range(len(before_new)) if before_new[i] != after_new[i]]

    # پنجرۀ نمایش: پیشِ نشستِ جاری یا شاملِ آن؟
    prev_via = conn.execute(
        "WITH iso AS (SELECT %s AS dt), "
        "spine AS (SELECT date AS dt FROM price_history "
        "           WHERE date < (SELECT dt FROM iso) "
        "           GROUP BY date ORDER BY date DESC LIMIT 60), "
        "rk AS (SELECT symbol, date, volume, ROW_NUMBER() OVER "
        "         (PARTITION BY symbol ORDER BY date DESC) rn FROM price_history "
        "         WHERE date >= (SELECT MIN(dt) FROM spine)) "
        "SELECT COUNT(DISTINCT symbol) FROM rk WHERE rn = 1 AND date = ?" % ISO_DATE,
        (live,)).fetchone()[0]
    out["symbols_whose_rn1_is_today"] = prev_via
    out["prev_day_vol_is_today_for"] = prev_via
    conn.close()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "_audit/liveprobe_copy.db"))
