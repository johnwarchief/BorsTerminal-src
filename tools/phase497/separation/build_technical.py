# tools/phase497/separation/build_technical.py
import os, json, sqlite3
from . import paths

def _init(out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    c = sqlite3.connect(out)
    c.executescript(open(os.path.join(os.path.dirname(__file__), "schema_technical.sql"), encoding="utf-8").read())
    return c

def build_candles(out, jsonl_dir=None):
    jsonl_dir = jsonl_dir or paths.JSONL_DIR
    c = _init(out)
    for fn in sorted(os.listdir(jsonl_dir)):
        if not (fn.startswith("bars_") and fn.endswith(".jsonl")): continue
        mode = fn[5:-6]; res, rest = mode.split("_", 1); basis, adj = rest.rsplit("_", 1)
        if basis == "real_close" or adj == "type5":   # redundant aliases
            continue
        with open(os.path.join(jsonl_dir, fn), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                rec = json.loads(line); aid = int(rec["asset_id"])
                seen = set()
                for b in rec["bars"]:
                    t = b["time"]
                    if t == 0: continue                 # placeholder padding
                    key = t
                    if key in seen: continue            # identical dup (source returns bar twice)
                    seen.add(key)
                    c.execute("INSERT OR IGNORE INTO candle(asset_id,res,basis,adj,t,utc,o,h,l,c,v) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                              (aid, res, basis, adj, t, b.get("utc"), b["open"], b["high"], b["low"], b["close"], b["volume"]))
        c.commit()
    c.close()