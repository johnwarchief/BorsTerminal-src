# -*- coding: utf-8 -*-
"""Rank symbols by how much adjustment work they carry.

An adjustment event is what the backend calls base-price discontinuity: the
next day's «قیمت پایه» (price_yesterday) is not the previous day's closing
price. Symbols with the most such events are the worst case for the three
adjustment modes, so they are the right sample for a live parity check.
"""
import os
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else (
    r"C:\Users\PCMOD\AppData\Local\Programs\BorsTerminal Ultimate\market.db")
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 15

SQL = """
with s as (
  select ins_code, d_even, p_closing, price_yesterday,
         lag(p_closing) over (partition by ins_code order by d_even) prev_close,
         lead(price_yesterday) over (partition by ins_code order by d_even) next_base
  from daily_prices
)
select i.l_val18, i.ins_code,
       sum(case when next_base is not null and prev_close is not null
                 and abs(next_base/prev_close - 1) > 0.005 then 1 else 0 end) events,
       min(d_even), max(d_even), count(*) rows
from s join instruments i on i.ins_code = s.ins_code
group by s.ins_code
having rows > 200 and events > 0
order by events desc
limit ?
"""

con = sqlite3.connect("file:%s?mode=ro" % DB.replace(os.sep, "/"), uri=True)
rows = con.execute(SQL, (LIMIT,)).fetchall()
con.close()
print("%-12s %-16s %7s %10s %10s %8s" % ("symbol", "ins_code", "events", "first", "last", "rows"))
for sym, code, ev, lo, hi, n in rows:
    print("%-12s %-16s %7d %10s %10s %8d" % ((sym or "").strip(), code, ev, lo, hi, n))
