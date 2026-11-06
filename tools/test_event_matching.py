import sys
import sqlite3
from datetime import datetime
sys.path.insert(0, ".")
import symbol_identity

sys.stdout.reconfigure(encoding='utf-8')
con = sqlite3.connect("market.db")
cur = con.cursor()

def date_diff_days(d1, d2):
    try:
        t1 = datetime.strptime(d1[:10], "%Y-%m-%d")
        t2 = datetime.strptime(d2[:10], "%Y-%m-%d")
        return abs((t1 - t2).days)
    except:
        return 999

SYMBOLS_20 = [
    "فولاد", "فملی", "شستا", "شپنا", "شبندر",
    "شتران", "خودرو", "خساپا", "وبملت", "وتجارت",
    "وبصادر", "فارس", "تاپیکو", "کگل", "کچاد",
    "وغدیر", "ومعادن", "وامید", "رمپنا", "پارس"
]

for sym in SYMBOLS_20:
    p_sql, p_params = symbol_identity.pred(con, "l_val18", sym, domain="board")
    inst = cur.execute(f"SELECT ins_code FROM instruments WHERE {p_sql} LIMIT 1", p_params).fetchone()
    if not inst:
        continue
    ins_code = inst[0]
    
    adj_evs = cur.execute("SELECT date, ratio FROM adjust_events WHERE symbol=? ORDER BY date DESC", (sym,)).fetchall()
    p_adj = cur.execute("SELECT d_even, ratio FROM price_adjust_events WHERE ins_code=? ORDER BY d_even DESC", (ins_code,)).fetchall()
    s_chg = cur.execute("SELECT d_even, ratio FROM share_change_events WHERE ins_code=? ORDER BY d_even DESC", (ins_code,)).fetchall()
    
    # Format dates
    dividends = [(f"{str(d[0])[:4]}-{str(d[0])[4:6]}-{str(d[0])[6:8]}", d[1]) for d in p_adj]
    cap_inc = [(f"{str(d[0])[:4]}-{str(d[0])[4:6]}-{str(d[0])[6:8]}", d[1]) for d in s_chg]
    
    # Check matching
    matched_div = 0
    matched_cap = 0
    unmatched_adj = 0
    for a_date, a_ratio in adj_evs:
        is_div = any(date_diff_days(a_date, d_date) <= 4 for d_date, _ in dividends)
        is_cap = any(date_diff_days(a_date, c_date) <= 4 for c_date, _ in cap_inc)
        if is_div:
            matched_div += 1
        elif is_cap:
            matched_cap += 1
        else:
            unmatched_adj += 1
            
    print(f"{sym:<8}: Total adjust_events={len(adj_evs)} | Matched Div={matched_div} | Matched Cap={matched_cap} | Older Historical={unmatched_adj}")
