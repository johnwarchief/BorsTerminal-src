# _audit/_ghost_probe.py -- ردیف‌هایِ کشی که دیگر درِ کشفِ زنده نیستند (spiritِ upsert)
import io,json,sys,sqlite3
sys.path.insert(0,".")
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
from api._core import DB_PATH
new=json.load(open("_audit/ra365_product_bars_new.json",encoding="utf-8"))
conn=sqlite3.connect(DB_PATH)
tot=0
for sym,rec in new.items():
    live={str(e["date"]) for e in (rec["live"].get("adjustEvents") or [])}
    try:
        cache=conn.execute("SELECT date,ratio FROM adjust_events WHERE symbol=?",(sym,)).fetchall()
    except sqlite3.OperationalError:
        print("   بدونِ ستونِ ratio؟",sym); continue
    ghosts=[(d,round(float(r),6)) for d,r in cache if d not in live]
    if ghosts:
        prod=1.0
        for _,r in ghosts: prod*=r
        tot+=len(ghosts)
        print(f"{sym:8s} کش {len(cache)} ردیف، زندہ {len(live)}، شبح {len(ghosts)} → {ghosts[:6]} "
              f"حاصل‌ضربِ شبح‌ها {prod:.6f}")
print("جمعِ ردیف‌هایِ شبح درِ کش:",tot)
