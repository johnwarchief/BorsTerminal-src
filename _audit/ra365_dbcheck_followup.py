# -*- coding: utf-8 -*-
"""ra365_dbcheck_followup.py — read-only second look (ولانا gap + installed DB)."""
import os, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"C:\Users\Johnkallnaya\Desktop\Borsterminal\BorsTerminal-src"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for label, db in (("REPO", os.path.join(ROOT, "market.db")),
                  ("INSTALLED", r"C:\Users\Johnkallnaya\AppData\Local\Programs\BorsTerminal_Ultimate\market.db")):
    if not os.path.exists(db):
        print(label, db, "MISSING"); continue
    print(f"\n===== {label} {db} size={os.path.getsize(db)} =====")
    c = ro(db)
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print("has pae/sce:", "price_adjust_events" in tables, "share_change_events" in tables)
    if "price_adjust_events" not in tables:
        c.close(); continue
    print("pae rows:", c.execute("SELECT COUNT(*) FROM price_adjust_events").fetchone()[0],
          "sce rows:", c.execute("SELECT COUNT(*) FROM share_change_events").fetchone()[0])
    print("pae d_even:", c.execute("SELECT MIN(d_even),MAX(d_even) FROM price_adjust_events").fetchone())
    print("sce d_even:", c.execute("SELECT MIN(d_even),MAX(d_even) FROM share_change_events").fetchone())
    # ولانا direct: instruments + both tables by symbol text
    for r in c.execute("SELECT ins_code,l_val18,l_val30,paper_type,c_gr_val_cot,total_shares,updated_at FROM instruments WHERE REPLACE(l_val18,'ي','ی')='ولانا'"):
        print("instruments ولانا:", r)
    if "price_history" in tables:
        print("price_history ولانا bars:", c.execute("SELECT COUNT(*),MIN(date),MAX(date) FROM price_history WHERE symbol LIKE '%ولانا%'").fetchone())
    for t in ("price_adjust_events", "share_change_events"):
        rows = c.execute(f"SELECT * FROM {t} WHERE symbol LIKE '%ولان%'").fetchall()
        print(t, "rows matching ولان:", len(rows), rows[:5])
        ins = "66830065858417081"
        print(t, "rows for ins 66830065858417081:", c.execute(f"SELECT COUNT(*) FROM {t} WHERE ins_code=?", (ins,)).fetchone()[0])
    # flow coverage: are فرابورس symbols present at all? join instruments market name
    try:
        r = c.execute("""SELECT i.paper_type, COUNT(*) FROM share_change_events s
                         JOIN instruments i ON i.ins_code=s.ins_code GROUP BY 1""").fetchall()
        print("sce by paper_type:", r)
        r = c.execute("""SELECT i.paper_type, COUNT(*) FROM price_adjust_events p
                         JOIN instruments i ON i.ins_code=p.ins_code GROUP BY 1""").fetchall()
        print("pae by paper_type:", r)
    except Exception as e:
        print("market join failed:", e)
    # oldest dates distribution (how deep history goes)
    print("pae rows before 2024:", c.execute("SELECT COUNT(*) FROM price_adjust_events WHERE d_even<20240101").fetchone()[0])
    print("sce rows by year (last 6):", c.execute("SELECT substr(d_even,1,4) y, COUNT(*) FROM share_change_events GROUP BY y ORDER BY y DESC LIMIT 6").fetchall())
    c.close()

print("\n===== DB_PATH resolution (dev import) =====")
os.chdir(ROOT)
sys.path.insert(0, ROOT)
try:
    import bors_config
    print("bors_config.DB_PATH =", bors_config.DB_PATH)
    print("bors_config.WORK_DIR =", bors_config.WORK_DIR)
except Exception as e:
    print("import failed:", type(e).__name__, e)
