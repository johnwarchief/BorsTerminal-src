import sqlite3

con = sqlite3.connect("market.db")
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
adjust_tables = [t for t in tables if any(k in t.lower() for k in ['adjust', 'factor', 'event', 'share', 'corporate'])]
print("Matching tables:", adjust_tables)
for t in adjust_tables:
    cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})").fetchall()]
    print(f"{t}: {cnt} rows, cols: {cols}")

print("\nSample adjust_events for فولاد:")
rows = cur.execute("SELECT date, ratio FROM adjust_events WHERE symbol='فولاد' ORDER BY date DESC LIMIT 5").fetchall()
for r in rows:
    print(r)
