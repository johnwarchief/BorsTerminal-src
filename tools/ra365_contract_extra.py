# -*- coding: utf-8 -*-
"""ra365_contract_extra.py — basis, history-range and missing-candle audit.

Usage:
  python tools/ra365_contract_extra.py --manifest _audit/RAHAVARD-FULL-UNIVERSE-MANIFEST-2026-10-20.csv \n    --ref _audit/ref_bars.jsonl --product _audit/product_live_final.jsonl \n    --parity _audit/out/parity_symbols.csv --out _audit/contract_extra.json
"""
import argparse, csv, json, os, sys, io, collections, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AP = argparse.ArgumentParser()
AP.add_argument("--manifest", default=os.path.join(ROOT, "_audit", "RAHAVARD-FULL-UNIVERSE-MANIFEST-2026-10-20.csv"))
AP.add_argument("--ref", default=os.path.join(ROOT, "_audit", "ref_bars.jsonl"))
AP.add_argument("--product", default=os.path.join(ROOT, "_audit", "product_live_final.jsonl"))
AP.add_argument("--parity", default=os.path.join(ROOT, "_audit", "out", "parity_symbols.csv"))
AP.add_argument("--sample", type=int, default=250)
AP.add_argument("--out", default=os.path.join(ROOT, "_audit", "contract_extra.json"))
A = AP.parse_args()
sample_n = A.sample

man = {}
for r in csv.DictReader(open(A.manifest, encoding="utf-8-sig")):
    if r.get("ra_asset_id"):
        man.setdefault(r["ra_asset_id"], []).append(r)
parity = {r["asset_id"]: r for r in csv.DictReader(open(A.parity, encoding="utf-8-sig"))}
live_assets = [a for a, p in parity.items() if p.get("product_live_available") == "True" and a in man]
random.seed(20261020)
sample = set(random.sample(live_assets, min(sample_n, len(live_assets))))
# ensure class coverage
by_class = collections.defaultdict(list)
for a in live_assets:
    by_class[man[a][0]["ra_class"]].append(a)
for c, xs in by_class.items():
    sample.update(random.sample(xs, min(20, len(xs))))

ref = {}
prod = {}
wanted_syms = set()
for a in sample:
    for r in man[a]:
        wanted_syms.add(r["symbol"])
for line in open(A.ref, encoding="utf-8"):
    r = json.loads(line); k = r["key"]
    if k.startswith("deep|"): continue
    aid, typ, res = k.split("|")
    if aid in sample and typ + res in ("type0D", "type7D", "type0W"):
        ref[(aid, typ, res)] = r.get("bars") or []
for line in open(A.product, encoding="utf-8"):
    r = json.loads(line)
    if r.get("symbol") in wanted_syms:
        prod[r["symbol"]] = r

def nb(b):
    if isinstance(b, list):
        u, o, h, l, c, v = b[:6]
    else:
        u, o, h, l, c, v = b.get("utc"), b.get("open"), b.get("high"), b.get("low"), b.get("close"), b.get("volume")
    return {"date": str(u)[:10], "open": float(o or 0), "high": float(h or 0),
            "low": float(l or 0), "close": float(c or 0), "volume": float(v or 0)}

basis = collections.Counter()
missing = collections.Counter()
missing_samples = []
missing_by_date = collections.Counter()
decimals = collections.Counter()
ranges = []
for a, rows in man.items():
    if (a, "type0", "D") not in ref:
        continue
    r0 = [nb(b) for b in ref[(a, "type0", "D")]]
    if not r0:
        continue
    ranges.append((r0[0]["date"], r0[-1]["date"], len(r0)))
    for b in r0[:200]:
        for f in ("open", "high", "low", "close"):
            s = repr(b[f])
            decimals[f + "_dec_" + (s.split(".")[1].rstrip("0") if "." in s else "0")] += 1
    if a not in sample:
        continue
    # choose the product symbol that covers the most common dates
    best = None
    for rr in rows:
        p = prod.get(rr["symbol"])
        if not p or p.get("adjustSource") == "local-db-fallback":
            continue
        candles = p.get("candles") or []
        vols = {str(v.get("time"))[:10]: float(v.get("value") or 0) for v in p.get("volumes") or []}
        pm = {}
        for c in candles:
            d = str(c.get("time"))[:10]
            pm[d] = {"last": None if c.get("last") is None else float(c.get("last")),
                     "closing": float(c.get("closing") or c.get("close") or 0),
                     "volume": float(c.get("volume") if c.get("volume") is not None else vols.get(d, 0))}
        common = set(pm) & {b["date"] for b in r0}
        if best is None or len(common) > len(best[0]):
            best = (common, pm, rr["symbol"])
    if not best:
        continue
    common, pm, sym = best
    rmap = {b["date"]: b for b in r0}
    for d in common:
        rc = rmap[d]["close"]
        last, closing = pm[d]["last"], pm[d]["closing"]
        basis["common"] += 1
        if last is not None and abs(rc - last) <= 0.5:
            basis["ref==last"] += 1
        if abs(rc - closing) <= 0.5:
            basis["ref==closing"] += 1
        if last is not None and abs(rc - last) <= 0.5 and abs(rc - closing) > 0.5:
            basis["last_only"] += 1
        if last is None:
            basis["last_missing"] += 1
    # missing reference dates inside the product range
    pmin, pmax = min(pm), max(pm)
    ref_dates = {b["date"] for b in r0}
    for d in sorted(ref_dates - set(pm)):
        if pmin <= d <= pmax:
            b = rmap[d]
            if b["volume"] == 0 or (b["high"] == 0 and b["low"] == 0):
                missing["no_trade"] += 1
            else:
                missing["true_gap"] += 1
                missing_by_date[d] += 1
                if len(missing_samples) < 15:
                    missing_samples.append({"asset": a, "symbol": sym, "date": d, "ohlc": [b["open"], b["high"], b["low"], b["close"]], "vol": b["volume"]})

start_years = collections.Counter(r[0][:4] for r in ranges)
end_years = collections.Counter(r[1][:4] for r in ranges)
out = {
    "sample_assets": len(sample), "basis": dict(basis),
    "missing_in_range": dict(missing), "missing_samples": missing_samples,
    "missing_by_date": dict(missing_by_date.most_common(30)),
    "history_first_year": dict(sorted(start_years.items())),
    "history_last_year": dict(sorted(end_years.items())),
    "history_first_min": min((r[0] for r in ranges), default=""),
    "history_first_max": max((r[0] for r in ranges), default=""),
    "decimals_sample": dict(sorted(decimals.items())),
}
json.dump(out, open(A.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
