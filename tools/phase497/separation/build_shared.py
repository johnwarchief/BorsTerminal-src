# tools/phase497/separation/build_shared.py
import os, json, sqlite3
import datetime
from . import paths

def _init(out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    c = sqlite3.connect(out)
    c.executescript(open(os.path.join(os.path.dirname(__file__), "schema_shared.sql"), encoding="utf-8").read())
    return c

def build_asset(c):
    uni = json.load(open(paths.UNIVERSE, encoding="utf-8"))["assets"]
    ref = paths.ro_conn(paths.REF_DB)
    candle = {a: (m, r) for a, m, r in ref.execute(
        "SELECT asset_id, COUNT(DISTINCT res||'/'||basis||'/'||adj), COUNT(*) FROM candles GROUP BY asset_id")}
    ins = {}
    with open(os.path.join(paths.PACK, "factors.jsonl"), encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            # Task-1 deviation (see task-1-report.md): the corrections pack contains
            # 96 symbol-keyed REFERENCE records with no "asset_id" field. They cannot
            # contribute to an asset_id-keyed crosswalk, so skip them. Without this
            # guard the brief's verbatim o["asset_id"] raises KeyError on the real pack.
            if "asset_id" not in o:
                continue
            ins.setdefault(str(o["asset_id"]), o.get("ins_code"))
    rows = []
    for a in uni:
        aid = int(a["entity_id"]); tid = a.get("type_id")
        mc, cr = candle.get(aid, (0, 0))
        rows.append((aid, a.get("trade_symbol"), a.get("name"), a.get("short_name"), a.get("exchange"),
                     tid, a.get("type"), paths.ASSET_CLASS.get(tid, "other"), ins.get(str(aid)),
                     1 if a.get("unlisted_item") else 0, 0, 1 if mc else 0, mc, cr))
    c.executemany("INSERT OR REPLACE INTO asset VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    # Task-1 deviation (see task-1-report.md): the pack also contains 1555 symbol-keyed
    # PRODUCT records with asset_id="" (empty/non-integer). They collapse to a single ""
    # key whose int() conversion raises ValueError. Keep only integer-parseable asset_id
    # keys for the crosswalk. All 806 real numeric asset_ids carry a non-null ins_code
    # (the test requires >= 800).
    c.executemany("INSERT OR REPLACE INTO id_crosswalk(asset_id, ins_code) VALUES (?,?)",
                  [(int(k), v) for k, v in ins.items() if k.lstrip("-").isdigit()])
    ref.close()

BASES = ["real_close","close","close_usd","last","last_usd","market_cap","market_cap_usd"]
ADJS = ["type0","type5","type7"]; RESS = ["D","W","M"]
def build_mode_def(c):
    rows = []
    for res in RESS:
        for b in BASES:
            for a in ADJS:
                mk = f"{res}/{b}/{a}"; alias = None
                if b == "real_close": alias = f"{res}/last/{a}"
                elif a == "type5": alias = f"{res}/{b}/type0"
                rows.append((mk, res, b, a, None, alias))
    c.executemany("INSERT OR REPLACE INTO mode_def VALUES (?,?,?,?,?,?)", rows)
def build_usd_rate(c):
    ref = paths.ro_conn(paths.REF_DB)
    rows = []
    for t, cl in ref.execute("SELECT t,c FROM candles WHERE asset_id=2 AND res='D' AND basis='close' AND adj='type0' AND t>0"):
        d = datetime.datetime.fromtimestamp(t/1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
        rows.append((d, cl, 2))
    c.executemany("INSERT OR REPLACE INTO usd_rate VALUES (?,?,?)", rows); ref.close()

def build_all(out):
    c = _init(out); build_asset(c); build_mode_def(c); build_usd_rate(c); c.commit(); c.close()