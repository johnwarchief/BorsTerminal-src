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

def build_adjustments(out, pack_dir=None):
    pack_dir = pack_dir or paths.PACK
    c = _init(out)
    with open(os.path.join(pack_dir, "factors.jsonl"), encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            raw = o.get("asset_id")
            aid = int(raw) if raw not in (None, "") and str(raw).lstrip("-").isdigit() else None
            c.execute("INSERT INTO adjustment_event(asset_id,ins_code,effective_date,kind,event_sig,ratio,cum_factor_after,source,confidence,correction_version,ref_bars_sha256) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (aid, o.get("ins_code"), o.get("effective_date"), o.get("class"),
                       o.get("event_sig"), o.get("ratio"), o.get("cum_factor_after"), o.get("source"),
                       o.get("confidence"), o.get("correction_version"), o.get("ref_bars_sha256")))
            if aid is not None:
                c.execute("INSERT OR REPLACE INTO adjustment_factor VALUES (?,?,?,?)",
                          (aid, o.get("effective_date"), o.get("cum_factor_after"), o.get("correction_version")))
    c.commit(); c.close()