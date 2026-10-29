#!/usr/bin/env python
"""فیکسچرِ تابلو برایِ تستِ Go — ۳۰ نماد، هر ردیف یک قاعده را قفل می‌کند.

خروجی: backend-go/internal/board/testdata/fixture/{market.db,user.db}
هیچ دادهٔ واقعی در آن نیست؛ همهٔ اعداد ساختگی و عمداً لبه‌ای‌اند.
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "backend-go", "internal", "board", "testdata", "fixture")

DDL = """
CREATE TABLE market_watch (
  ins_code TEXT PRIMARY KEY, p_closing REAL, p_last REAL, q_tot_tran REAL,
  z_tot_tran REAL, price_yesterday REAL, q_tot_cap REAL, price_change REAL,
  d_even INTEGER, h_even INTEGER, pe REAL, eps REAL, price_max REAL,
  price_min REAL, price_first REAL, buy_q_vol REAL, buy_q_val REAL,
  buy_q_cnt REAL, sell_q_vol REAL, sell_q_val REAL, sell_q_cnt REAL,
  buy_q1_vol REAL, buy_q1_px REAL, sell_q1_vol REAL, sell_q1_px REAL,
  buy_q1_cnt REAL, allowed_min REAL, allowed_max REAL, fetched_at TEXT,
  market_cap REAL, market_cap_src TEXT);
CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT, sector_name TEXT);
CREATE TABLE boards (ins_code TEXT PRIMARY KEY, board TEXT);
CREATE TABLE client_type (ins_code TEXT, d_even INTEGER, buy_i_vol REAL, buy_n_vol REAL,
  sell_i_vol REAL, sell_n_vol REAL, buy_count_i REAL, sell_count_i REAL);
CREATE TABLE client_type_value (ins_code TEXT, d_even INTEGER, kind TEXT,
  buy_i_val REAL, buy_n_val REAL, sell_i_val REAL, sell_n_val REAL);
CREATE TABLE instrument_state (ins_code TEXT, c_etaval TEXT, c_etaval_title TEXT,
  d_even INTEGER, last_h_even INTEGER);
CREATE TABLE supervision_state (ins_code TEXT PRIMARY KEY, under_supervision_title TEXT,
  reason_count INTEGER, reasons TEXT);
CREATE TABLE stop_reasons (symbol TEXT PRIMARY KEY, vaziyat_desc TEXT,
  last_date_change TEXT, dalils TEXT);
CREATE TABLE tse_inst_stat (ins_code TEXT PRIMARY KEY, is5 REAL, is6 REAL);
CREATE TABLE price_history (symbol TEXT, date TEXT, high REAL, low REAL, close REAL, volume REAL);
CREATE TABLE daily_prices (ins_code TEXT, d_even INTEGER, price_max REAL, price_min REAL,
  q_tot_tran REAL, market_cap REAL, p_closing REAL);
CREATE TABLE tape_history (ins_code TEXT, d_even INTEGER, price_min REAL, price_max REAL,
  q_tot_tran5j REAL);
CREATE TABLE tape_ih_slot (ins_code TEXT, slot INTEGER, d_even INTEGER, price_min REAL,
  price_max REAL, q_tot_tran5j REAL);
CREATE TABLE tape_history_state (id INTEGER PRIMARY KEY, newest_d_even INTEGER);
"""

DAY = 20261014


def hist_dates(n=60):
    # ۶۰ تاریخِ کاریِ ساختگی، نزولی‌ناپذیر لازم نیست؛ فقط یکتا و کوچک‌تر از DAY.
    import datetime as dt
    base = dt.date(2026, 7, 1)
    out = []
    for i in range(n):
        d = base + dt.timedelta(days=i)
        out.append(d.strftime("%Y-%m-%d"))
    return out


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    db = os.path.join(OUT, "market.db")
    if os.path.exists(db):
        os.remove(db)
    con = sqlite3.connect(db)
    con.executescript(DDL)
    dates = hist_dates(60)
    rows = []
    # (symbol, name, sector, close, last, qty, trades, py, chg, d_even, h_even,
    #  pmin, pmax, pfirst, tmin, tmax, buy_i, sell_i, bcnt, scnt, is5, is6,
    #  ctv(bi,bn,si,sn), mcap, mcap_src, board, st_title, stop, sup)
    rows.append(("عادی01", "عادی یک", "فلزات", 1000.0, 1100.0, 500000, 120, 1000.0, 100.0, DAY, 123000,
                 990.0, 1150.0, 1000.0, 900.0, 1150.0, 300000, 200000, 60, 40, None, 1.0e9,
                 (10e6, 5e6, 8e6, 6e6), 5.0e12, "mw", "بازار", None, None, None))
    rows.append(("پایین02", "پایین دو", "فلزات", 500.0, 495.0, 100000, 30, 500.0, -5.0, DAY, 121500,
                 480.0, 520.0, 500.0, 450.0, 520.0, 50000, 60000, 10, 12, None, 2.0e8,
                 (1e6, 2e6, 3e6, 1e6), 1.0e12, "mw", "بازار", None, None, None))
    rows.append(("نگهبان03", "نگهبان سه", "خودرو", 2000.0, 2100.0, 80000, 55, 1.0, 100.0, DAY, 122000,
                 1900.0, 2200.0, 2000.0, 1800.0, 2200.0, 30000, 20000, 7, 8, None, None,
                 (None, None, None, None), None, None, "بازار", None, None, None))
    rows.append(("بی‌معامله04", "بی معامله", "خودرو", 1500.0, 1500.0, 0, 0, 1500.0, 0.0, DAY, 120000,
                 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0, None, 0.0,
                 (0.0, 0.0, 0.0, 0.0), 0.0, "mw", "بازار", None, None, None))
    rows.append(("سخت05", "سخت پنج", "بانک", 3000.0, 3300.0, 900000, 400, 2000.0, 1000.0, DAY - 1, 122500,
                 2900.0, 3400.0, 3000.0, 2800.0, 3400.0, 400000, 100000, 90, 20, 5.0e8, 1.0e9,
                 (5e6, 1e6, 2e6, 8e6), 9.0e12, "mw", "بازار", "مجاز", None, None))
    rows.append(("پول‌هوشمند06", "پول هوشمند", "بانک", 4000.0, 4100.0, 2000000, 250, 3800.0, 200.0, DAY, 123500,
                 3900.0, 4200.0, 4000.0, 3700.0, 4200.0, 1200000, 900000, 200, 150, None, 3.0e8,
                 (9e6, 1e6, 5e6, 4e6), 2.0e13, "mw", "بازار", "مجاز-متوقف", None, None))
    rows.append(("متوقف07", "متوقف هفت", "بانک", 1000.0, 1000.0, 1000, 3, 1000.0, 0.0, DAY, 110000,
                 990.0, 1010.0, 1000.0, 900.0, 1100.0, 10, 20, 1, 2, None, None,
                 (None, None, None, None), 1.0e11, "mw", "بازار", None, "متوقف", None))
    rows.append(("ممنوع08", "ممنوع هشت", "بانک", 1200.0, 1200.0, 2000, 4, 1200.0, 0.0, DAY, 100000,
                 1190.0, 1210.0, 1200.0, 1100.0, 1300.0, 15, 25, 2, 3, None, None,
                 (None, None, None, None), 2.0e11, "mw", "بازار", "ممنوع", None, None))
    rows.append(("کدبه‌کد09", "کد به کد", "سیمان", 800.0, 810.0, 3000000, 500, 700.0, 100.0, DAY, 123900,
                 780.0, 830.0, 800.0, 700.0, 850.0, 2500000, 2400000, 300, 280, None, 4.0e8,
                 (12e6, 2e6, 10e6, 8e6), 3.0e12, "mw", "بازار", None, None, None))
    rows.append(("کف‌روبی10", "کف روبی", "سیمان", 600.0, 450.0, 200000, 80, 600.0, -150.0, DAY, 124000,
                 450.0, 700.0, 600.0, 450.0, 700.0, 90000, 50000, 40, 30, None, None,
                 (2e6, 1e6, 3e6, 2e6), 6.0e11, "mw", "بازار", None, None, None))
    rows.append(("کم‌سابقه11", "کم سابقه", "سیمان", 900.0, 950.0, 150000, 40, 900.0, 50.0, DAY, 121000,
                 880.0, 960.0, 900.0, 850.0, 980.0, 70000, 65000, 12, 11, None, None,
                 (3e6, 1e6, 2e6, 2e6), 9.0e11, "mw", "بازار", None, None, None))
    # ردیف‌هایِ سادهٔ دیگر تا «ترتیب/حذف/تکرار» هم پوشش بگیرد.
    for i in range(12, 31):
        code = "ساده%02d" % i
        rows.append((code, "ساده %d" % i, "سایر", 100.0 + i, 100.5 + i, 10000 + i, 10 + i,
                     100.0 + i, 0.5, DAY, 120000 + i, 99.0 + i, 102.0 + i, 100.0 + i,
                     90.0 + i, 110.0 + i, 6000, 5000, 5, 4, None, None,
                     (1e6, 1e6, 1e6, 1e6), 1.0e11 + i, "mw", "بازار", None, None, None))

    for r in rows:
        (sym, name, sector, pc, pl, qty, tno, py, chg, d_even, h_even, pmin, pmax, pfirst,
         tmin, tmax, bi, si, bc, sc, is5, is6, ctv, mcap, msrc, board, st_title, stop, sup) = r
        code = "INS-" + sym
        con.execute(
            "INSERT INTO market_watch(ins_code,p_closing,p_last,q_tot_tran,z_tot_tran,"
            "price_yesterday,q_tot_cap,price_change,d_even,h_even,pe,eps,price_max,price_min,"
            "price_first,buy_q_vol,buy_q_val,buy_q_cnt,sell_q_vol,sell_q_val,sell_q_cnt,"
            "buy_q1_vol,buy_q1_px,sell_q1_vol,sell_q1_px,buy_q1_cnt,allowed_min,allowed_max,"
            "fetched_at,market_cap,market_cap_src) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (code, pc, pl, qty, tno, py, pc * qty, chg, d_even, h_even, 7.5, 100.0,
             pmax, pmin, pfirst, 1000.0, 1.0e7, 10.0, 900.0, 9.0e6, 9.0,
             500.0, pl, 400.0, pl - 10.0, 2.0, tmin, tmax, "2026-10-14 12:00:00", mcap, msrc))
        con.execute("INSERT INTO instruments VALUES(?,?,?,?)", (code, sym, name, sector))
        con.execute("INSERT INTO boards VALUES(?,?)", (code, board))
        con.execute("INSERT INTO client_type VALUES(?,?,?,?,?,?,?,?)",
                    (code, DAY - 1, bi, 0.0, si, 0.0, bc, sc))
        if ctv is not None:
            con.execute("INSERT INTO client_type_value VALUES(?,?,?,?,?,?,?)",
                        (code, DAY - 1, "native", *ctv))
        con.execute("INSERT INTO tse_inst_stat VALUES(?,?,?)", (code, is5, is6))
        if st_title is not None:
            con.execute("INSERT INTO instrument_state VALUES(?,?,?,?,?)",
                        (code, "A", st_title, DAY - 1, 90000))
        if sup is not None:
            con.execute("INSERT INTO supervision_state VALUES(?,?,?,?)",
                        (code, sup, 1, "[]"))
        if stop is not None:
            con.execute("INSERT INTO stop_reasons VALUES(?,?,?,?)",
                        (sym, stop, "2026-10-13", "[]"))
        for k, dt in enumerate(dates):
            con.execute("INSERT INTO price_history VALUES(?,?,?,?,?,?)",
                        (sym, dt, pmax, pmin, pc, float(k + 1) * 1000.0))
        for k in range(60):
            con.execute("INSERT INTO tape_history VALUES(?,?,?,?,?)",
                        (code, DAY - k, pmin, pmax, 1000.0 + k))
            con.execute("INSERT INTO tape_ih_slot VALUES(?,?,?,?,?,?)",
                        (code, k, DAY - k, pmin, pmax, 1000.0 + k))
    # نمادی که در market_watch نیست ولی در instruments هست ⇒ هرگز نباید در تابلو بیاید.
    con.execute("INSERT INTO instruments VALUES(?,?,?,?)", ("INS-غایب", "غایب", "غایب", "سایر"))
    con.execute("INSERT INTO tape_history_state VALUES(1, ?)", (DAY - 60,))
    con.commit()
    con.close()

    user = os.path.join(OUT, "user.db")
    if os.path.exists(user):
        os.remove(user)
    sqlite3.connect(user).close()

    print("fixture rows: %d -> %s" % (len(rows), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
