# -*- coding: utf-8 -*-
"""ra365_dbcheck_coverage.py — READ-ONLY coverage probe for the canonical
TSETMC event tables in market.db. Touches nothing (mode=ro URI)."""
import os, sqlite3, sys, csv, json

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"C:\Users\Johnkallnaya\Desktop\Borsterminal\BorsTerminal-src"
DB = os.path.join(ROOT, "market.db")

def ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)

conn = ro(DB)
print("== 1) DB ==")
print("path:", DB, "size:", os.path.getsize(DB))
for t, in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    pass
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("has price_history:", "price_history" in tables)
if "price_history" in tables:
    print("price_history max date:", conn.execute("SELECT MAX(date) FROM price_history").fetchone()[0])
    print("price_history rows:", conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0])

print("\n== 2) schema ==")
for t in ("price_adjust_events", "share_change_events"):
    if t in tables:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
        print(t, "cols:", cols)
    else:
        print(t, "MISSING")

print("\n== 3) coverage ==")
for t in ("price_adjust_events", "share_change_events"):
    n, ni = conn.execute(f"SELECT COUNT(*), COUNT(DISTINCT ins_code) FROM {t}").fetchone()
    dmin, dmax = conn.execute(f"SELECT MIN(d_even), MAX(d_even) FROM {t}").fetchone()
    print(f"{t}: rows={n} distinct_ins={ni} d_even {dmin}..{dmax}")

symbols = []
with open(os.path.join(ROOT, "_audit", "RA365-CORPUS-2026-10-12.csv"), encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        symbols.append(row["symbol"])
print("corpus size:", len(symbols))

def ins_for(sym):
    # same fold as api/chart.py:608 (Arabic->Persian ي/ك/ى)
    pred = "REPLACE(REPLACE(REPLACE(l_val18,'ك','ک'),'ي','ی'),'ى','ی')=? "
    r = conn.execute(f"SELECT ins_code FROM instruments WHERE {pred} ORDER BY updated_at DESC LIMIT 1",
                     (sym.replace("ي", "ی").replace("ك", "ک"),)).fetchone()
    return r[0] if r else None

print("symbol | ins_code | price_adjust_events | share_change_events")
cov_adj = cov_shr = 0
ins_map = {}
for s in symbols:
    ins = ins_for(s)
    ins_map[s] = ins
    if ins:
        a = conn.execute("SELECT COUNT(*) FROM price_adjust_events WHERE ins_code=?", (ins,)).fetchone()[0]
        sh = conn.execute("SELECT COUNT(*) FROM share_change_events WHERE ins_code=?", (ins,)).fetchone()[0]
    else:
        a = sh = -1
    cov_adj += 1 if a > 0 else 0
    cov_shr += 1 if sh > 0 else 0
    print(f"{s} | {ins} | {a} | {sh}")
print(f"corpus with >=1 price_adjust row: {cov_adj}/{len(symbols)}; >=1 share_change: {cov_shr}/{len(symbols)}")

print("\n== 4) rows for شبهرن / ولانا / وبملت ==")
hdr = ["d_even", "symbol", "p_closing", "p_closingNotAdj", "corpTypeCode", "ratio", "source", "fetched_at"]
for s in ("شبهرن", "ولانا", "وبملت"):
    ins = ins_map.get(s) or ins_for(s)
    print(f"\n--- {s} (ins_code={ins}) ---")
    if not ins:
        print("  no instruments row")
        continue
    print(" price_adjust_events:")
    for r in conn.execute("SELECT d_even,symbol,p_closing,p_closing_not_adjusted,corporate_type_code,ratio,source,fetched_at FROM price_adjust_events WHERE ins_code=? ORDER BY d_even", (ins,)):
        print("  ", r)
    print(" share_change_events:")
    for r in conn.execute("SELECT d_even,symbol,shares_old,shares_new,ratio,source,fetched_at FROM share_change_events WHERE ins_code=? ORDER BY d_even", (ins,)):
        print("  ", r)

print("\n== 5) ratios vs reference steps ==")
for s in ("شبهرن", "ولانا", "وبملت"):
    ins = ins_map.get(s)
    if not ins:
        continue
    for r in conn.execute("SELECT d_even,p_closing,p_closing_not_adjusted,ratio FROM price_adjust_events WHERE ins_code=? ORDER BY d_even", (ins,)):
        d, adj, raw, ratio = r
        derived = (raw / adj) if (adj and raw) else None
        print(f"{s} {d}: pClosing={adj} raw={raw} stored_ratio(adj/raw)={ratio} raw/adj={derived}")
    for r in conn.execute("SELECT d_even,shares_old,shares_new,ratio FROM share_change_events WHERE ins_code=? ORDER BY d_even", (ins,)):
        d, old, new, ratio = r
        print(f"{s} {d}: shares {old}->{new} stored_ratio(old/new)={ratio} new/old={(new/old) if old and new else None}")

print("\n== 6) corporateTypeCode ==")
tot, nonnull = conn.execute("SELECT COUNT(*), COUNT(corporate_type_code) FROM price_adjust_events").fetchone()
print(f"price_adjust_events rows={tot} corporate_type_code non-null={nonnull}")
for v, c in conn.execute("SELECT corporate_type_code, COUNT(*) FROM price_adjust_events WHERE corporate_type_code IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 20"):
    print("  value:", v, "count:", c)

print("\n== 7) _corporate_events replication (query path of api/chart.py:339-383) ==")
for s in ("شبهرن", "ولانا"):
    ins = ins_map.get(s)
    out = []
    if ins:
        for d, raw, adj, src in conn.execute("SELECT d_even,p_closing_not_adjusted,p_closing,source FROM price_adjust_events WHERE ins_code=? ORDER BY d_even", (ins,)):
            ds = str(d)
            if len(ds) == 8:
                out.append({"date": f"{ds[:4]}-{ds[4:6]}-{ds[6:]}", "type": "priceAdjust", "from": raw, "to": adj, "source": src or "tsetmc"})
        for d, old, new, src in conn.execute("SELECT d_even,shares_old,shares_new,source FROM share_change_events WHERE ins_code=? ORDER BY d_even", (ins,)):
            ds = str(d)
            if len(ds) == 8:
                out.append({"date": f"{ds[:4]}-{ds[4:6]}-{ds[6:]}", "type": "shareChange", "from": old, "to": new, "source": src or "tsetmc"})
        out.sort(key=lambda e: e["date"])
    print(s, "n_events:", len(out))
    for e in out[-12:]:
        print("  ", json.dumps(e, ensure_ascii=False))
conn.close()
