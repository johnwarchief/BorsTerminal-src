import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')
con = sqlite3.connect("market.db")
cur = con.cursor()

print("--- adjust_events for فولاد ---")
for r in cur.execute("SELECT date, ratio, source FROM adjust_events WHERE symbol='فولاد' ORDER BY date DESC LIMIT 10").fetchall():
    print("adjust_events:", r)

ins_code = "46348559193224090"
print("\n--- price_adjust_events for فولاد ---")
for r in cur.execute("SELECT d_even, p_closing, p_closing_not_adjusted, ratio, source FROM price_adjust_events WHERE ins_code=? ORDER BY d_even DESC LIMIT 10", (ins_code,)).fetchall():
    print("price_adjust_events:", r)

print("\n--- share_change_events for فولاد ---")
for r in cur.execute("SELECT d_even, shares_old, shares_new, ratio, source FROM share_change_events WHERE ins_code=? ORDER BY d_even DESC LIMIT 10", (ins_code,)).fetchall():
    print("share_change_events:", r)
