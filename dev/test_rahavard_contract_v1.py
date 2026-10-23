# -*- coding: utf-8 -*-
"""Rahavard data-contract fixture: type0/type7, OHLC factor, weekly aggregation, basis.

The fixture is a small, committed extract of the live reference capture
(dev/fixtures/rahavard_contract_sample.json) around one event per asset.
"""
import datetime as dt, io, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
FIX = os.path.join(ROOT, "dev", "fixtures", "rahavard_contract_sample.json")
D = json.load(open(FIX, encoding="utf-8"))

checks = fails = 0
def ck(name, cond, detail=""):
    global checks, fails
    checks += 1
    if cond: print(f"  OK   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}  {detail}")

def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))

def weekly(daily):
    by = {}
    for b in daily:
        day = dt.date.fromisoformat(b[0])
        start = day - dt.timedelta(days=(day.weekday() - 5) % 7)
        by.setdefault(start.isoformat(), []).append(b)
    out = {}
    for k, items in by.items():
        items.sort(key=lambda x: x[0])
        out[k] = {
            "open": items[0][1], "high": max(x[2] for x in items),
            "low": min(x[3] for x in items), "close": items[-1][4],
            "volume": sum(x[5] for x in items),
            "first": items[0][0], "last": items[-1][0],
        }
    return out

ck("fixture version 1.0", D.get("version") == "1.0", D.get("version"))
for aid, e in D["assets"].items():
    d0, d7 = e["type0D"], e["type7D"]
    ck(f"{aid} D series aligned", len(d0) == len(d7) and [x[0] for x in d0] == [x[0] for x in d7])
    ck(f"{aid} type0 prices are integer rial", all(float(x[1]).is_integer() and float(x[4]).is_integer() for x in d0))
    anc = e.get("anchor") or {}
    ck(f"{aid} full-series anchor: type7 == type0 at last date",
       anc.get("type0") is not None and close(anc["type0"], anc["type7"]),
       (anc.get("type0"), anc.get("type7")))
    ok = 0; bad = []
    for a, b in zip(d0, d7):
        if not a[4]: continue
        f = b[4] / a[4]
        if all(close(b[i], a[i] * f) for i in (1, 2, 3, 4)) and close(a[5], b[5]):
            ok += 1
        else:
            bad.append((a[0], a[1:5], b[1:5], f))
    ck(f"{aid} type7 OHLC = type0 × factor, volume unchanged", not bad, bad[:2])
    factors = [b[4] / a[4] for a, b in zip(d0, d7) if a[4]]
    if e["symbol"] == "اعتماد":
        ck(f"{aid} no-event control: factor is exactly 1", all(abs(f - 1) < 1e-9 for f in factors))
    else:
        ck(f"{aid} factor moves down before the event", any(f < 1 - 1e-9 for f in factors))
    # weekly direct vs daily aggregation (only full weeks)
    aw = weekly(d0)
    w0 = {x[0]: x for x in e["type0W"]}
    w7 = {x[0]: x for x in e["type7W"]}
    checked = 0; wbad = []
    for k, v in aw.items():
        if k not in w0: continue
        checked += 1
        w = w0[k]
        if not all(close(v[f], w[i]) for f, i in (("open",1),("high",2),("low",3),("close",4),("volume",5))):
            wbad.append((k, v, w))
        if k in w7 and w[4]:
            wf = w7[k][4] / w[4]
            dlast = v["last"]
            fl = {x[0]: x[4] for x in d7}[dlast]
            fr = {x[0]: x[4] for x in d0}[dlast]
            if fr and not close(wf, fl / fr):
                wbad.append((k, "weekly_factor", wf, fl / fr))
    ck(f"{aid} weekly = Saturday open/high/low/close/volume-sum", checked > 0 and not wbad, (checked, wbad[:2]))
    ck(f"{aid} weekly factor == daily factor at week end", checked > 0 and not any(len(x) == 4 for x in wbad))
    # basis: reference type0 close == product last (not closing)
    hits = 0
    for row in e.get("product_basis") or []:
        ref = {x[0]: x[4] for x in d0}.get(row["date"])
        if ref is None: continue
        if abs(ref - row["last"]) <= 0.5: hits += 1
    ck(f"{aid} basis: type0 close == product LAST", hits == len(e.get("product_basis") or []) and hits > 0, (hits, len(e.get("product_basis") or [])))

print(f"\n{checks - fails}/{checks} checks passed")
sys.exit(0 if fails == 0 else 1)
