"""پrobeٔ موقت — بازدهِ فیلتر جت به ازای هر انتخابِ «تایم‌فریم شکست سقف».

مدلِ پیشنهادی: پلکانِ جزوه {2,5,9,19,29,39,49,59} و «هر نقطه‌ای که از
تایم‌فریمِ انتخابی کوتاه‌تر است هم باید شکسته شود». اگر این مدل در
تایم‌فریم‌های کوتاه بازدهِ معناداری ندهد، کنترلِ تک‌تایم‌فریم بی‌فایده است
و باید چیز دیگری پیشنهاد شود.
"""
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

LADDER = (2, 5, 9, 19, 29, 39, 49, 59)
conn = sqlite3.connect("market.db")
c = conn.cursor()
day = c.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]

rows = c.execute(
    """SELECT i.l_val18, m.p_closing, m.p_last, m.z_tot_tran, m.q_tot_tran,
              m.price_change, ct.buy_i_vol, ct.buy_count_i, ct.sell_i_vol, ct.sell_count_i
       FROM market_watch m
       JOIN instruments i ON i.ins_code=m.ins_code
       LEFT JOIN (SELECT ins_code, MAX(d_even) d FROM client_type
                  WHERE d_even <= (SELECT MAX(d_even) FROM market_watch)
                  GROUP BY ins_code) x ON x.ins_code = m.ins_code
       LEFT JOIN client_type ct ON ct.ins_code = m.ins_code AND ct.d_even = x.d
       WHERE m.d_even=?""", (day,)).fetchall()

hist, hvol = {}, {}
for sym, rn, high, volume in c.execute(
    """SELECT symbol, rn, high, volume FROM (
         SELECT symbol, high, volume,
                ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
         FROM price_history) WHERE rn <= 60"""):
    hist.setdefault(sym, {})[rn] = high
    hvol.setdefault(sym, {})[rn] = volume


def f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if x == x else 0.0


for lb in LADDER:
    pts = [k for k in LADDER if k <= lb]
    n_strict = n_lennient = 0
    for sym, pc, pl, ztt, tvol, chg, biv, bci, siv, sci in rows:
        hs = hist.get(sym, {})
        vs = hvol.get(sym, {})
        vols = [v for k, v in vs.items() if k <= 30 and v]
        avg30 = (sum(vols) / len(vols)) if vols else 0.0
        bp = f(biv) / max(f(bci), 1.0)
        sp = f(siv) / max(f(sci), 1.0)
        base_ok = (f(tvol) > 3 * avg30 and avg30 > 0 and f(pl) >= f(pc) and f(pc) > 0
                   and f(chg) > 0 and bp >= 1.5 * sp and f(ztt) > 100)
        if not base_ok:
            continue
        got = [hs.get(k) for k in pts]
        if all(g and f(pl) > g for g in got):
            n_strict += 1
        if any(g and f(pl) > g for g in got):
            n_lennient += 1
    print(f"lookback {lb:>2} (points {pts}) -> همهٔ نقاط: {n_strict:>4} | حداقل یک نقطه: {n_lennient:>4}")

conn.close()
