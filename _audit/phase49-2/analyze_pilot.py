#!/usr/bin/env python3
"""Analyze the 30-symbol Rahavard raw/type7 capture.

Establishes, per symbol:
  * how type7 is anchored (q = raw_close / adjusted_close; q_last expected 1.0);
  * the change points of q (implied event dates) and their implied ratios;
  * whether each change point matches a pack step (date within 7 days, ratio);
  * whether type7 equals raw * piecewise cumulative factor on every bar and
    every OHLC field, and whether volume is untouched;
  * the pack steps with no type7 change (extra/future/no-op).

Writes _audit/phase49-2/rahavard/pilot-analysis.json. Read-only.
"""
import json
import os
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAPTURE = os.path.join(ROOT, "_audit", "phase49-2", "rahavard", "pilot-capture.json")
PACK = os.path.join(ROOT, "data", "ra365_corrections",
                    "ra365-phase49-rebuild-full-v2", "factors.jsonl")
OUT = os.path.join(ROOT, "_audit", "phase49-2", "rahavard", "pilot-analysis.json")
MATCH_DAYS = 7
RATIO_TOL = 1e-6
PRICE_TOL = 1e-6


def date10(s):
    return str(s or "")[:10]


def days(a, b):
    import datetime
    try:
        return abs((datetime.date.fromisoformat(a) - datetime.date.fromisoformat(b)).days)
    except ValueError:
        return 10 ** 6


def load_pack():
    out = collections.defaultdict(list)
    for line in open(PACK, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        out[r["symbol"]].append({
            "date": date10(r.get("effective_date")),
            "ratio": r.get("ratio"),
            "event_sig": r.get("event_sig"),
            "action": r.get("action"),
        })
    for rows in out.values():
        rows.sort(key=lambda x: x["date"])
    return out


def main():
    cap = json.load(open(CAPTURE, encoding="utf-8"))
    capture_day = cap["source"]["captured_at"][:10]
    by_symbol = collections.defaultdict(dict)
    for s in cap["series"]:
        typ = "raw" if s["ticker"].endswith(":type0") else "type7"
        by_symbol[s["symbol"]][typ] = {
            b["utc"][:10]: b for b in s["bars"]
            if b.get("close") and b["utc"][:10] < capture_day}
    pack = load_pack()

    symbols = []
    for sym in sorted(by_symbol):
        series = by_symbol[sym]
        if "raw" not in series or "type7" not in series:
            continue
        raw, adj = series["raw"], series["type7"]
        common = sorted(set(raw) & set(adj))
        qs = []
        for dt in common:
            c0, c7 = raw[dt]["close"], adj[dt]["close"]
            if c0 and c7:
                qs.append((dt, c0 / c7))
        changes = []
        prev = None
        for dt, q in qs:
            if prev is not None and abs(q / prev - 1.0) > 1e-9:
                changes.append({"date": dt, "implied_ratio": q / prev,
                                "q_before": prev, "q_after": q})
            prev = q
        # match changes to pack steps
        steps = [s for s in pack.get(sym, []) if s.get("action") != "suppress_step"]
        used = set()
        for ch in changes:
            best = None
            for i, st in enumerate(steps):
                dd = days(ch["date"], st["date"])
                if dd <= MATCH_DAYS and i not in used:
                    if best is None or dd < best[0]:
                        best = (dd, i, st)
            if best is None:
                ch["pack_match"] = None
                ch["status"] = "NO_PACK_STEP"
            else:
                used.add(best[1])
                st = best[2]
                ch["pack_match"] = {**st, "delta_days": best[0]}
                if st["ratio"] and abs(ch["implied_ratio"] / st["ratio"] - 1) <= RATIO_TOL:
                    ch["status"] = "MATCH"
                else:
                    ch["status"] = "RATIO_DIFF"
        extra = [st for i, st in enumerate(steps) if i not in used]

        # OHLC parity: the same q = raw_close/adj_close must map every field.
        q_by_date = dict(qs)
        max_dev = {"open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0}
        worst = {}
        for dt in common:
            q = q_by_date.get(dt)
            if not q:
                continue
            for field in ("open", "high", "low", "close"):
                a, b = raw[dt].get(field), adj[dt].get(field)
                if not a or not b:
                    continue
                dev = abs(a / q / b - 1.0)
                if dev > max_dev[field]:
                    max_dev[field] = dev
                    worst[field] = dt
        vol_equal = sum(1 for dt in common
                        if raw[dt].get("volume") == adj[dt].get("volume"))
        vol_total = sum(1 for dt in common if raw[dt].get("volume") is not None)

        symbols.append({
            "symbol": sym,
            "bars": len(common),
            "q_first": qs[0][1] if qs else None,
            "q_last": qs[-1][1] if qs else None,
            "changes": changes,
            "change_status": dict(collections.Counter(c["status"] for c in changes)),
            "pack_steps": len(steps),
            "pack_steps_without_change": len(extra),
            "extra_steps": extra,
            "max_factor_dev": max_dev,
            "worst_factor_date": worst,
            "volume_equal": vol_equal,
            "volume_total": vol_total,
            "anchored_at_last_bar": bool(qs and abs(qs[-1][1] - 1.0) < 1e-9),
        })

    totals = collections.Counter()
    for s in symbols:
        for k, v in s["change_status"].items():
            totals[k] += v
        totals["pack_steps_without_change"] += s["pack_steps_without_change"]
        totals["symbols"] += 1
    out = {
        "schema": "phase49-2-rahavard-pilot-analysis-v1",
        "capture_sha256": cap["source"].get("input_sha256"),
        "captured_at": cap["source"].get("captured_at"),
        "match_days": MATCH_DAYS,
        "ratio_tol": RATIO_TOL,
        "price_tol": PRICE_TOL,
        "totals": dict(totals),
        "symbols": symbols,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(json.dumps(out["totals"], ensure_ascii=False, indent=1))
    bad = []
    for s in symbols:
        dev = max(s["max_factor_dev"].values())
        if s["change_status"].get("RATIO_DIFF") or s["change_status"].get("NO_PACK_STEP") \
                or dev > PRICE_TOL:
            bad.append((s["symbol"], s["change_status"], round(dev, 9),
                        s["pack_steps_without_change"]))
    print("symbols needing attention:", len(bad))
    for b in bad[:15]:
        print(" ", b)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
