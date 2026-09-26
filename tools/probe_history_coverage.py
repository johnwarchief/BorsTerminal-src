"""پrobeٔ موقت — چرا فقط ۱۰۸۹ نماد ۳۰ جلسه تاریخچه دارند؟

اگر سهامِ شناورِ قدیمی ردیفِ کم دارد، مشکل از «جمع‌آوری تاریخچه» است نه از
فیلتر؛ در این حالتِ سخت‌گیر کردنِ فیلتر، نامزدِ واقعی را پنهان می‌کند.
پس اول باید معلوم شود نمادهای کم‌تاریخچه چه جنسیتی‌اند.
"""
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect("market.db")
c = conn.cursor()

day = c.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
print("board day:", day)

print("\n-- price_history global --")
n, sym, dmin, dmax = c.execute(
    "SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(date), MAX(date) FROM price_history"
).fetchone()
print(f"rows={n} symbols={sym} date {dmin}..{dmax}")

print("\n-- توزیع تعدادِ جلسه به ازای هر نماد --")
for lo, hi in ((0, 1), (2, 9), (10, 29), (30, 59), (60, 10_000)):
    q = f"""SELECT COUNT(*) FROM (
        SELECT symbol, COUNT(*) k FROM price_history GROUP BY symbol
    ) WHERE k BETWEEN {lo} AND {hi}"""
    print(f"  sessions {lo}..{hi}:", c.execute(q).fetchone()[0])

print("\n-- ۲۰ نمادِ پر حجمِ تابلو که <۳۰ جلسه تاریخچه دارند --")
rows = c.execute(
    """
    SELECT i.l_val18 sym, i.l_val30 nm, i.paper_type, m.q_tot_cap val,
           (SELECT COUNT(*) FROM price_history h WHERE h.symbol = i.l_val18) k
    FROM market_watch m
    JOIN instruments i ON i.ins_code = m.ins_code
    WHERE m.d_even = ? AND m.q_tot_cap > 0
      AND (SELECT COUNT(*) FROM price_history h WHERE h.symbol = i.l_val18) < 30
    ORDER BY m.q_tot_cap DESC LIMIT 20
    """,
    (day,),
).fetchall()
for r in rows:
    print("  ", r)

print("\n-- تفکیک بر اساس پیشوندِ نماد (اختیار/صندوق/نماد عادی) --")
print("paper_type مقادیر موجود:",
      c.execute("SELECT DISTINCT paper_type FROM instruments LIMIT 20").fetchall())

tot = c.execute(
    """SELECT COUNT(*) FROM market_watch m JOIN instruments i ON i.ins_code=m.ins_code
       WHERE m.d_even=?""", (day,)).fetchone()[0]
thin = c.execute(
    """SELECT COUNT(*) FROM market_watch m JOIN instruments i ON i.ins_code=m.ins_code
       WHERE m.d_even=? AND
       (SELECT COUNT(*) FROM price_history h WHERE h.symbol=i.l_val18) < 30""",
    (day,)).fetchone()[0]
none_ = c.execute(
    """SELECT COUNT(*) FROM market_watch m JOIN instruments i ON i.ins_code=m.ins_code
       WHERE m.d_even=? AND NOT EXISTS
       (SELECT 1 FROM price_history h WHERE h.symbol=i.l_val18)""",
    (day,)).fetchone()[0]
print(f"\nboard={tot} thin(<30)={thin} no-history={none_}")

# ارزش معاملاتِ نمادهای کم‌تاریخچه — اگر بخش بزرگی از نقدشوندگی باشد،
# یعنی جمع‌آوری تاریخچه حفره دارد و فیلتر سخت‌گیر نامزد از دست می‌دهد.
v_thin = c.execute(
    """SELECT COALESCE(SUM(m.q_tot_cap),0) FROM market_watch m
       JOIN instruments i ON i.ins_code=m.ins_code WHERE m.d_even=? AND
       (SELECT COUNT(*) FROM price_history h WHERE h.symbol=i.l_val18) < 30""",
    (day,)).fetchone()[0]
v_all = c.execute(
    "SELECT COALESCE(SUM(q_tot_cap),0) FROM market_watch WHERE d_even=?", (day,)
).fetchone()[0]
print(f"ارزش معاملات نمادهای کم‌تاریخچه: {v_thin/1e9:,.0f} میلیارد از {v_all/1e9:,.0f} "
      f"({(v_thin/v_all*100 if v_all else 0):.1f}%)")

conn.close()
