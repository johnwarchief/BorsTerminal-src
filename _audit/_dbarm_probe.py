# _audit/_dbarm_probe.py -- بازوِ دیتابیس با کدِ تازه: فاکتورِ روزِ سنجش و رویدادِ ۱٫۷۱
import io,json,sys,urllib.parse,urllib.request
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
BASE="http://127.0.0.1:8000"
old=json.load(open("_audit/ra365_product_bars.json",encoding="utf-8"))
after=json.load(open("_audit/ra365_product_bars_after.json",encoding="utf-8"))
for sym,d in (("لخزر","2025-08-26"),("ومعادن","2025-07-29"),("ولانا","2025-03-02")):
    j=json.loads(urllib.request.urlopen(BASE+"/api/chart-db/"+urllib.parse.quote(sym),timeout=60).read().decode("utf-8"))
    f={x["time"]:x["factor"] for x in (j.get("factors") or [])}
    fo={x["time"]:x["factor"] for x in (old[sym]["db"].get("factors") or [])}
    fa={x["time"]:x["factor"] for x in (after[sym]["db"].get("factors") or [])}
    ev={str(e["date"]):e["ratio"] for e in (j.get("adjustEvents") or [])}
    print(f"{sym:8s} روزِ {d}: پیش {fo.get(d)} | پسِ رفعِ اول {fa.get(d)} | اکنون {f.get(d)}  "
          f"| رویدادها {len(ev)} | src={j.get('adjustSource')} | ۲۰۲۶-۰۷-۲۲={ev.get('2026-07-22')}")
