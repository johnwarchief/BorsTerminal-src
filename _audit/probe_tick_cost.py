# یک‌بارمصرف — هزینهٔ واقعیِ یک تیک: transfers، gzip، JSON-parse، و استخراج ردیف‌ها.
# هیچ نوشتنی ندارد؛ فقط GET + زمان‌سنجیِ pure-python.
import gzip
import json
import sys
import time
import zlib

sys.path.insert(0, r"C:\Users\PCMOD\Desktop\BorsTerminal")
import test_tsetmc as T   # noqa: E402

s = T.make_session()
url = ("https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0"
       "&paperTypes[0]=1&showTraded=false&withBestLimits=true&hEven=0")
t0 = time.time()
r = s.get(url, headers=T.HEADERS, timeout=60)
t1 = time.time()
raw = r.content
enc = r.headers.get("Content-Encoding") or "-"
ctype = r.headers.get("Content-Type", "")[:28]
print("transfer: " + str(len(raw)) + " B | content-encoding=" + enc + " | " + ctype
      + " | wall " + str(round(t1 - t0, 2)) + "s")
print("headers: ", {k: v for k, v in r.headers.items()
                    if k.lower() in ("content-length", "content-encoding", "server", "cache-control")})
t0 = time.time()
text = raw.decode("utf-8", "replace")
t1 = time.time()
print("decode: " + str(round(t1 - t0, 3)) + "s | " + str(len(text)) + " chars")
t0 = time.time()
d = json.loads(text)
t1 = time.time()
rows = d.get("marketwatch") or []
print("json.loads: " + str(round(t1 - t0, 3)) + "s | rows=" + str(len(rows)))
if rows:
    print("per-row keys: " + str(sorted(rows[0].keys())))
t0 = time.time()
m = {}
for x in rows:
    ic = x.get("insCode")
    if not ic:
        continue
    m[ic] = (x.get("pcl"), x.get("pdv"), x.get("qtj"), x.get("qtc"), x.get("ztt"),
             x.get("eps"), x.get("pe"), x.get("ztd"), x.get("hEven"), x.get("dEven"),
             (x.get("blDs") or {}).get("qmd") if isinstance(x.get("blDs"), dict) else None)
t1 = time.time()
print("row-map build: " + str(round(t1 - t0, 3)) + "s | keys=" + str(len(m)))
t0 = time.time()
blob = json.dumps({"data": [[None if v is None else v for v in t] for t in m.values()]})
t1 = time.time()
g = gzip.compress(blob.encode("utf-8"), 6)
t2 = time.time()
print("re-serialize: " + str(round(t1 - t0, 3)) + "s | " + str(len(blob)) + " B"
      + " | gzip: " + str(round(t2 - t1, 3)) + "s | " + str(len(g)) + " B")
try:
    import orjson
    t0 = time.time()
    b2 = orjson.dumps({"data": list(m.values())})
    t1 = time.time()
    print("orjson: " + str(round(t1 - t0, 4)) + "s | " + str(len(b2)) + " B")
except Exception as e:
    print("orjson: unavailable (" + str(e)[:40] + ")")
