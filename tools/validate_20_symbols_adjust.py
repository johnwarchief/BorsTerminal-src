import sys
import sqlite3
import json

sys.stdout.reconfigure(encoding='utf-8')

SYMBOLS_20 = [
    "فولاد", "فملی", "شستا", "شپنا", "شبندر",
    "شتران", "خودرو", "خساپا", "وبملت", "وتجارت",
    "وبصادر", "فارس", "تاپیکو", "کگل", "کچاد",
    "وغدیر", "ومعادن", "وامید", "رمپنا", "پارس"
]

con = sqlite3.connect("market.db")
con.row_factory = sqlite3.Row
cur = con.cursor()

import symbol_identity

for sym in SYMBOLS_20:
    p_sql, p_params = symbol_identity.pred(con, "l_val18", sym, domain="board")
    row = cur.execute(
        f"SELECT ins_code, l_val18, l_val30 FROM instruments WHERE {p_sql} ORDER BY updated_at DESC LIMIT 1",
        p_params
    ).fetchone()
    
    if not row:
        report.append({
            "symbol": sym,
            "status": "NOT_FOUND_IN_INSTRUMENTS",
            "ins_code": None,
            "candles_count": 0,
            "adjust_events_count": 0,
            "price_adjust_count": 0,
            "share_change_count": 0,
            "events_sample": []
        })
        continue
    
    ins_code = row["ins_code"]
    
    # Check candles
    candles_count = cur.execute(
        "SELECT COUNT(*) FROM daily_prices WHERE ins_code=?", (ins_code,)
    ).fetchone()[0]
    
    # Check adjust_events (canonical)
    adj_events = cur.execute(
        "SELECT date, ratio, source FROM adjust_events WHERE symbol=? ORDER BY date ASC", (sym,)
    ).fetchall()
    
    # Check price_adjust_events (dividends)
    p_adj = cur.execute(
        "SELECT d_even, p_closing, p_closing_not_adjusted, ratio, source FROM price_adjust_events WHERE ins_code=? ORDER BY d_even ASC",
        (ins_code,)
    ).fetchall()
    
    # Check share_change_events (capital increases)
    s_chg = cur.execute(
        "SELECT d_even, shares_old, shares_new, ratio, source FROM share_change_events WHERE ins_code=? ORDER BY d_even ASC",
        (ins_code,)
    ).fetchall()
    
    events_summary = []
    for ae in adj_events:
        events_summary.append({
            "date": ae["date"],
            "ratio": ae["ratio"],
            "type": "adjust_event",
            "source": ae["source"]
        })
    for pa in p_adj:
        events_summary.append({
            "date": str(pa["d_even"]),
            "ratio": pa["ratio"],
            "type": "dividend",
            "source": pa["source"],
            "p_close": pa["p_closing"],
            "p_close_raw": pa["p_closing_not_adjusted"]
        })
    for sc in s_chg:
        events_summary.append({
            "date": str(sc["d_even"]),
            "ratio": sc["ratio"],
            "type": "capital_increase",
            "source": sc["source"],
            "old_shares": sc["shares_old"],
            "new_shares": sc["shares_new"]
        })
    
    # Check date range of candles
    date_range = cur.execute(
        "SELECT MIN(d_even), MAX(d_even) FROM daily_prices WHERE ins_code=?", (ins_code,)
    ).fetchone()
    
    report.append({
        "symbol": sym,
        "name": row["l_val30"],
        "status": "OK",
        "ins_code": ins_code,
        "candles_count": candles_count,
        "date_range": [date_range[0], date_range[1]] if date_range else [None, None],
        "adjust_events_count": len(adj_events),
        "price_adjust_count": len(p_adj),
        "share_change_count": len(s_chg),
        "total_events": len(events_summary),
        "sample_events": events_summary[-5:] if events_summary else []
    })

print(f"{'نماد':<8} | {'کد ابزار':<15} | {'کندل‌ها':<8} | {'رویداد تعدیل':<12} | {'سود نقدی':<8} | {'افزایش سرمایه':<12}")
print("-" * 75)
for r in report:
    if r["status"] == "OK":
        print(f"{r['symbol']:<8} | {r['ins_code']:<15} | {r['candles_count']:<8} | {r['adjust_events_count']:<12} | {r['price_adjust_count']:<8} | {r['share_change_count']:<12}")
    else:
        print(f"{r['symbol']:<8} | NOT FOUND")

with open("_audit/20_symbols_adjust_audit.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
