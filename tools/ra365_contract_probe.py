# -*- coding: utf-8 -*-
"""ra365_contract_probe.py — prove the Rahavard365 type0/type7/D/W contract.

Usage:
  python tools/ra365_contract_probe.py --ref _audit/ref_bars.jsonl --out _audit/contract_probe.json

Measures anchor, factor direction, OHLC factor consistency, volume invariance,
weekly direct-vs-aggregation, volume-sum rule, labels, no-trade rows, ranges.
"""
import argparse, datetime as dt, json, os, sys, io, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AP = argparse.ArgumentParser()
AP.add_argument("--ref", default=os.path.join(ROOT, "_audit", "ref_bars.jsonl"))
AP.add_argument("--out", default=os.path.join(ROOT, "_audit", "rahavard_contract_probe.json"))
A = AP.parse_args()

def norm(b):
    if isinstance(b, list):
        u, o, h, l, c, v = b[:6]
    else:
        u, o, h, l, c, v = b.get("utc"), b.get("open"), b.get("high"), b.get("low"), b.get("close"), b.get("volume")
    return {"date": str(u)[:10], "open": float(o or 0), "high": float(h or 0),
            "low": float(l or 0), "close": float(c or 0), "volume": float(v or 0)}

def agg_weekly(daily):
    by = collections.defaultdict(list)
    for b in daily:
        day = dt.date.fromisoformat(b["date"])
        start = day - dt.timedelta(days=(day.weekday() - 5) % 7)
        by[start.isoformat()].append(b)
    out = {}
    for k, items in by.items():
        items.sort(key=lambda x: x["date"])
        out[k] = {"open": items[0]["open"], "high": max(x["high"] for x in items),
                  "low": min(x["low"] for x in items), "close": items[-1]["close"],
                  "volume": sum(x["volume"] for x in items),
                  "first": items[0]["date"], "last": items[-1]["date"], "n": len(items)}
    return out

def pct(xs, q):
    if not xs: return None
    xs = sorted(xs); return xs[min(len(xs) - 1, int(q * (len(xs) - 1) + 0.5))]

S = collections.Counter()
range_buckets = collections.Counter()
vol_rule = collections.Counter()
label_match = collections.Counter()
field_matches = collections.Counter()
factor_dir = collections.Counter()
no_trade = []
factor_dec = collections.Counter()
examples = []
step_offsets = collections.Counter()
weekly_factor = collections.Counter()

cur_aid, cur = None, {}
def flush(aid, g):
    t0d = [norm(b) for b in g.get("type0|D", [])]
    t7d = [norm(b) for b in g.get("type7|D", [])]
    t0w = [norm(b) for b in g.get("type0|W", [])]
    t7w = [norm(b) for b in g.get("type7|W", [])]
    if not t0d or not t7d:
        return
    S["assets"] += 1
    for label, series in (("D", t0d), ("W", t0w)):
        if not series: continue
        S[f"{label}_bars"] += len(series)
        range_buckets[f"{label}:{series[0]['date'][:4]}"] += 1
    # anchor: last daily type0 vs type7
    d0 = {b["date"]: b for b in t0d}; d7 = {b["date"]: b for b in t7d}
    common = sorted(set(d0) & set(d7))
    if common:
        last = common[-1]
        if abs(d0[last]["close"] - d7[last]["close"]) < 1e-6:
            S["anchor_last_equal_D"] += 1
        else:
            examples.append({"anchor_mismatch": aid, "date": last,
                             "t0": d0[last]["close"], "t7": d7[last]["close"]})
        for d in common:
            r = d7[d]["close"] / d0[d]["close"] if d0[d]["close"] else None
            if r is None: continue
            if r > 1 + 1e-9: factor_dir["ratio>1"] += 1
            elif r < 1 - 1e-9: factor_dir["ratio<1"] += 1
            else: factor_dir["ratio=1"] += 1
            # OHLC factor consistency
            for f in ("open", "high", "low", "close"):
                a, b = d7[d][f], d0[d][f] * r
                if b and abs(a - b) / abs(b) <= 1e-6:
                    field_matches[f] += 1
                else:
                    field_matches[f + "_bad"] += 1
            if abs(d7[d]["volume"] - d0[d]["volume"]) <= 1e-6:
                field_matches["volume"] += 1
            else:
                field_matches["volume_bad"] += 1
        # steps direction
        f = [d7[d]["close"] / d0[d]["close"] for d in common if d0[d]["close"]]
        for i in range(1, len(f)):
            if f[i - 1] and abs(f[i] / f[i - 1] - 1) > 0.0005:
                ratio = f[i - 1] / f[i]   # event ratio in the product's convention
                factor_dir["step_ratio<=1" if ratio <= 1 + 1e-6 else "step_ratio>1"] += 1
    # weekly direct vs aggregation
    if t0w and t0d:
        aw = agg_weekly(t0d)
        wmap = {b["date"]: b for b in t0w}
        for k, v in aw.items():
            if k in wmap:
                label_match["matched"] += 1
                r = wmap[k]
                for f in ("open", "high", "low", "close", "volume"):
                    if abs(v[f] - r[f]) <= 1e-6:
                        field_matches["w_" + f] += 1
                    else:
                        field_matches["w_" + f + "_bad"] += 1
                vol_rule["sum" if abs(v["volume"] - r["volume"]) <= 1e-6 else "not_sum"] += 1
            else:
                label_match["missing_in_ref"] += 1
        for k in wmap:
            if k not in aw:
                label_match["only_ref"] += 1
        # functional weekly direct vs aggregation of daily type7
        if t7w:
            aw7 = agg_weekly(t7d)
            w7map = {b["date"]: b for b in t7w}
            for k in set(aw7) & set(w7map):
                for f in ("open", "high", "low", "close"):
                    a = aw7[k][f]; b = w7map[k][f]
                    if b and abs(a - b) / abs(b) <= 1e-6:
                        field_matches["w7_" + f] += 1
                    else:
                        field_matches["w7_" + f + "_bad"] += 1
                if wmap.get(k) and w7map[k].get("close") and wmap[k]["close"]:
                    wf = w7map[k]["close"] / wmap[k]["close"]
                    # daily factor at the last day of the week
                    dlast = aw[k]["last"]
                    if dlast in d0 and dlast in d7 and d0[dlast]["close"]:
                        df = d7[dlast]["close"] / d0[dlast]["close"]
                        if abs(wf - df) <= max(1e-6, 1e-4 * abs(df)):
                            weekly_factor["weekly==last_daily"] += 1
                        else:
                            weekly_factor["weekly!=last_daily"] += 1
    # no-trade rows
    for b in t0d:
        if b["volume"] == 0 or (b["high"] == 0 and b["low"] == 0):
            S["no_trade_rows"] += 1
            if len(no_trade) < 8:
                no_trade.append({"asset": aid, "date": b["date"], "ohlc": [b["open"], b["high"], b["low"], b["close"]], "vol": b["volume"]})
    # decimals
    for b in t7d[:50]:
        s = repr(b["close"])
        factor_dec[len(s.split(".")[1]) if "." in s else 0] += 1

# Two passes: keep only the LAST occurrence of each key (the pilot 118 series are
# duplicated by the full 2020+ scan). This keeps memory bounded and covers all assets.
path = A.ref
last_idx = {}
for i, line in enumerate(open(path, encoding="utf-8")):
    try:
        k = json.loads(line)["key"]
    except Exception:
        continue
    if not k.startswith("deep|"):
        last_idx[k] = i
assets = {}
for i, line in enumerate(open(path, encoding="utf-8")):
    r = json.loads(line)
    k = r["key"]
    if k.startswith("deep|") or last_idx.get(k) != i:
        continue
    aid, typ, res = k.split("|")
    assets.setdefault(aid, {})[f"{typ}|{res}"] = r.get("bars") or []
for aid, g in assets.items():
    flush(aid, g)

out = {"summary": dict(S), "factor_direction": dict(factor_dir),
       "weekly_labels": dict(label_match), "weekly_volume_rule": dict(vol_rule),
       "field_matches": dict(field_matches), "weekly_factor": dict(weekly_factor),
       "no_trade_examples": no_trade, "examples": examples[:10]}
json.dump(out, open(A.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in ("summary", "factor_direction", "weekly_labels", "weekly_volume_rule", "weekly_factor", "field_matches")}, ensure_ascii=False, indent=1))
