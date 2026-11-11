#!/usr/bin/env python3
"""Select the 30-symbol Rahavard pilot deterministically.

Mandatory coverage: the four unadjustable rows (شنفت, طلا, تپسي, غشان) and the
three-step Volana symbol (ولانا). The rest is stratified over the pack event
signatures (share-only, dps-only, combined, base_gap, product/unproven,
no_event), history length, event count, and recency so the pilot exercises
different adjustment shapes rather than 30 look-alikes.

Output: _audit/phase49-2/rahavard/pilot-symbols.json + pilot-selection.json
"""
import json
import os
import random
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACK = os.path.join(ROOT, "data", "ra365_corrections",
                    "ra365-phase49-rebuild-full-v2", "factors.jsonl")
SYMBOLS = os.path.join(ROOT, "_audit", "phase49-full-verification",
                       "capture-plan", "symbols.json")
OUT_DIR = os.path.join(ROOT, "_audit", "phase49-2", "rahavard")
MANDATORY = ["شنفت", "طلا", "تپسي", "غشان", "ولانا"]


def sig_class(sigs):
    s = set(sigs) - {""}
    has_share = "share" in s
    has_dps = bool(s & {"dps", "fund_dps", "pa"})
    has_gap = "base_gap" in s
    if has_share and has_dps:
        return "combined"
    if has_share:
        return "share_only"
    if has_dps:
        return "dps_only"
    if has_gap:
        return "base_gap"
    if s & {"product", "unproven_gap"}:
        return "product_or_unproven"
    return "no_event"


def main():
    symbols = {x["symbol"]: x for x in json.load(
        open(SYMBOLS, encoding="utf-8"))}
    stats = collections.defaultdict(lambda: {
        "count": 0, "sigs": set(), "first": None, "last": None})
    for line in open(PACK, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        s = stats[r["symbol"]]
        s["count"] += 1
        s["sigs"].add(r.get("event_sig") or "")
        d = r.get("effective_date") or ""
        if s["first"] is None or d < s["first"]:
            s["first"] = d
        if s["last"] is None or d > s["last"]:
            s["last"] = d

    pool = []
    seen_pool = set()
    for sym, s in stats.items():
        if sym not in symbols:
            continue
        pool.append({
            "symbol": sym,
            "asset_id": symbols[sym]["asset_id"],
            "ins_code": symbols[sym].get("ins_code"),
            "basis": symbols[sym].get("basis") or "real_close",
            "events": s["count"],
            "first": s["first"],
            "last": s["last"],
            "signatures": sorted(s["sigs"]),
            "class": sig_class(s["sigs"]),
        })
        seen_pool.add(sym)
    # A mandatory symbol may carry no pack steps at all (طلا), yet it must be
    # in the pilot: it is one of the four named unadjustable rows.
    for sym, info in symbols.items():
        if sym in seen_pool:
            continue
        pool.append({
            "symbol": sym,
            "asset_id": info["asset_id"],
            "ins_code": info.get("ins_code"),
            "basis": info.get("basis") or "real_close",
            "events": 0, "first": None, "last": None,
            "signatures": [], "class": "no_pack_steps",
        })
    by_name = {p["symbol"]: p for p in pool}

    chosen = []
    reasons = {}
    for sym in MANDATORY:
        if sym in by_name:
            chosen.append(by_name[sym])
            reasons[sym] = "mandatory: named blocker/concentration case"
    chosen_names = {p["symbol"] for p in chosen}

    def take(predicate, label, limit):
        n = 0
        for p in sorted(pool, key=lambda x: (x["first"] or "", x["symbol"])):
            if p["symbol"] in chosen_names or not predicate(p):
                continue
            chosen.append(p)
            chosen_names.add(p["symbol"])
            reasons[p["symbol"]] = label
            n += 1
            if n >= limit:
                break

    take(lambda p: p["first"] and p["first"] <= "2009-12-31",
         "long history (first step <= 2009)", 5)
    take(lambda p: p["events"] >= 40, "high event count (>=40 steps)", 5)
    take(lambda p: p["class"] == "share_only", "signature class: share_only", 3)
    take(lambda p: p["class"] == "dps_only", "signature class: dps_only", 3)
    take(lambda p: p["class"] == "combined", "signature class: combined", 4)
    take(lambda p: p["class"] == "base_gap", "signature class: base_gap", 2)
    take(lambda p: p["class"] == "product_or_unproven",
         "signature class: product/unproven", 2)
    take(lambda p: p["first"] and p["first"] >= "2020-01-01",
         "recent listing (first step >= 2020)", 2)

    rng = random.Random(49_2)
    rest = [p for p in pool if p["symbol"] not in chosen_names]
    rng.shuffle(rest)
    for p in rest:
        if len(chosen) >= 30:
            break
        chosen.append(p)
        chosen_names.add(p["symbol"])
        reasons[p["symbol"]] = "seeded random fill (diversity tail)"
    # Adding mandatory symbols can overshoot the 30 budget; trim random fills,
    # never a stratified or mandatory pick.
    while len(chosen) > 30:
        for i in range(len(chosen) - 1, -1, -1):
            if reasons[chosen[i]["symbol"]].startswith("seeded random fill"):
                del chosen[i]
                break
        else:
            raise SystemExit("cannot trim the pilot to 30")
    if len(chosen) != 30:
        raise SystemExit("pilot pool too small: %d" % len(chosen))

    chosen.sort(key=lambda p: p["symbol"])
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "pilot-symbols.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump([{k: p[k] for k in ("symbol", "asset_id", "ins_code", "basis")}
                   for p in chosen], fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    report = {
        "schema": "phase49-2-pilot-selection-v1",
        "pool": len(pool),
        "chosen": len(chosen),
        "classes": dict(collections.Counter(p["class"] for p in chosen)),
        "events_total": sum(p["events"] for p in chosen),
        "history_min": min(p["first"] for p in chosen if p["first"]),
        "history_max": max(p["last"] for p in chosen if p["last"]),
        "symbols": [{**p, "reason": reasons[p["symbol"]]} for p in chosen],
    }
    with open(os.path.join(OUT_DIR, "pilot-selection.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(json.dumps({k: report[k] for k in
                      ("pool", "chosen", "classes", "events_total")},
                     ensure_ascii=False, indent=1))
    for p in chosen:
        print("%-12s asset=%-6s %-18s events=%-3d %s..%s  %s"
              % (p["symbol"], p["asset_id"], p["class"], p["events"],
                 p["first"], p["last"], reasons[p["symbol"]]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
