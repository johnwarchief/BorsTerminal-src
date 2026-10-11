# _audit/ra365_product_pull.py -- گرفتنِ کندل‌هایِ خودِ محصول (BorsTerminal) برایِ گنجینە
# دو مسیرِ محصول: /api/chart/{sym} (CSV زنده از TSETMC) و /api/chart-db/{sym} (همان چیزی که دیتابیس محلی می‌دهد)
# خروجی: _audit/ra365_product_bars.json  (کندل + فاکتورهایِ تعدیل + منبعِ تعدیل)
# فقط خواندنی؛ سرورِ محلی رویِ 127.0.0.1:8000 باید بالا باشد.
import json
import sys
import io
import time
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = "http://127.0.0.1:8000"
OUT = "_audit/ra365_product_bars.json"

corpus = json.load(open("_audit/ra365_corpus.json", encoding="utf-8"))
out = {}
for c in corpus:
    sym = c["sym"]
    rec = {}
    for path_name, tmpl in (("live", "/api/chart/{}"), ("db", "/api/chart-db/{}")):
        url = BASE + tmpl.format(urllib.parse.quote(sym))
        t0 = time.time()
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                j = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            j = {"status": "error", "message": str(e)[:200]}
        rec[path_name] = {
            "status": j.get("status"),
            "count": j.get("count"),
            "adjustSource": j.get("adjustSource"),
            "priceBasis": j.get("priceBasis"),
            "priceBasisRequested": j.get("priceBasisRequested"),
            "seconds": round(time.time() - t0, 2),
            "keys": sorted(j.keys())[:20],
            "candles": j.get("candles"),
            # درِ مسیرِ زنده حجم درِ آرایۀِ جداگانه‌ای است؛ اینجا همان را کنارِ هم می‌گذاریم
            "volumes": {v.get("time"): v.get("value") for v in (j.get("volumes") or []) if isinstance(v, dict)},
            "factors": j.get("factors"),
            "adjustEvents": j.get("adjustEvents"),
            "message": j.get("message"),
        }
        st = rec[path_name]
        print(f"{sym:9s} {path_name:4s} status={st['status']} candles={len(st['candles'] or [])} "
              f"adjustSource={st['adjustSource']} {st['seconds']}s" + (f" msg={st['message']}" if st['message'] else ""))
    out[sym] = rec

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("WROTE", OUT, "symbols", len(out))
