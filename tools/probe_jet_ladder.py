"""پrobeٔ موقت — پوشش تاریخچه و تعدادِ نامزدهای جت تحت قاعدهٔ فعلی و قاعدهٔ سخت‌گیر.

جزوه، فیلتر جت را این‌طور تعریف می‌کند:
    (pl) > [ih][k].PriceMax   برای k در {2,5,9,19,29,39,49,59}
یعنی «آخرین معامله» باید بالای سقفِ تک‌روزهٔ هر هشت نقطه باشد. پیاده‌سازی
کنونی دو انحراف دارد: (۱) فقط یک نقطه را می‌بیند، (۲) با «قیمت پایانی»
مقایسه می‌کند، و (۳) اگر سقفی موجود نبود شرط را رد می‌کند (NULL = قبول).
"""
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

DB = "market.db"
LADDER = (2, 5, 9, 19, 29, 39, 49, 59)

conn = sqlite3.connect(DB)
c = conn.cursor()

day = c.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
print("board day:", day)

rows = c.execute(
    """
    SELECT i.l_val18 AS symbol, m.p_closing, m.p_last, m.z_tot_tran, m.q_tot_tran,
           m.price_change, m.price_yesterday
    FROM market_watch m JOIN instruments i ON i.ins_code = m.ins_code
    WHERE m.d_even = ?
    """,
    (day,),
).fetchall()
print("board rows:", len(rows))

hist = {}
hvol = {}
for sym, rn, high, volume in c.execute(
    """
    SELECT symbol, rn, high, volume FROM (
        SELECT symbol, high, volume,
               ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
        FROM price_history
    ) WHERE rn <= 60
    """
):
    hist.setdefault(sym, {})[rn] = high
    hvol.setdefault(sym, {})[rn] = volume

have30 = sum(1 for s in hist.values() if len(s) >= 30)
have60 = sum(1 for s in hist.values() if len(s) >= 60)
print("symbols with >=30 sessions:", have30, "| >=60:", have60, "| total:", len(hist))


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


# وضعیتِ فعلیِ بک‌اند: سقف‌ها با p_closing و «isna => قبول»، فقط یک نقطه در UI
cur_pass, strict_pass, ladder_missing = 0, 0, 0
no_avg30 = 0
for sym, pc, pl, ztt, tvol, chg, py in rows:
    pc, pl = num(pc), num(pl)
    hs = hist.get(sym, {})
    vs = hvol.get(sym, {})
    # حجم مبنا: میانگین حجم ۳۰ جلسهٔ اخیر (تعریف جزوه: [ih][0..29].QTotTran5J)
    vols = [v for k, v in sorted(vs.items()) if k <= 30 and v is not None]
    avg30 = (sum(vols) / len(vols)) if vols else None
    if avg30 is None:
        no_avg30 += 1
    vol_ok = avg30 is not None and (num(tvol) or 0) > 3 * avg30
    other_ok = (
        pc is not None
        and pl is not None
        and pl >= pc
        and (num(chg) or 0) > 0
        and (num(ztt) or 0) > 100
    )
    # قاعدهٔ فعلی UI: فقط یک نقطه، با پایانی، NULL=قبول
    one = hs.get(59)
    if one and pc and pc > one:
        cur_pass += 1
    # قاعدهٔ جزوه: هر هشت نقطه، با آخرین، کمبود = رد
    got = [hs.get(k) for k in LADDER]
    if any(g is None for g in got):
        ladder_missing += 1
        continue
    if vol_ok and other_ok and pl and all(g and pl > g for g in got):
        strict_pass += 1

print("current single-point-vs-close matches:", cur_pass)
print("notebook ladder-vs-last matches:", strict_pass)
print("symbols missing >=1 ladder checkpoint:", ladder_missing)
print("board rows with no avg30 baseline at all:", no_avg30)

# پوشش پلکان: چند نماد لااقل h2 دارد؟
for k in LADDER:
    n = sum(1 for s in hist.values() if s.get(k))
    print(f"  h{k}_max present:", n)

conn.close()
