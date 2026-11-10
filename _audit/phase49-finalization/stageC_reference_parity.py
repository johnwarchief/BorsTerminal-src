#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage C: reference parity (Raw / Factor chain / Adjusted OHLC) for captured
Rahavard type0/type7 bars against the product DB and a Rebuild pack.

Read-only. Produces a JSON detail file and a per-symbol CSV/Markdown summary.
"""
import argparse
import collections
import csv
import gzip
import json
import os
import sqlite3
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "_audit", "phase49-finalization", "db", "restored-work.db")
EVID = os.path.join(ROOT, "_audit", "phase49-finalization", "evidence")
CH_KEYS = ("open", "high", "low", "close", "volume")


def skeleton(s):
    return str(s).translate(str.maketrans({"ي": "ی", "ك": "ک", "ى": "ی"}))


def rel(a, b):
    if a is None or b is None:
        return None
    try:
        a = float(a)
        b = float(b)
    except (TypeError, ValueError):
        return None
    d = max(abs(b), 1e-12)
    return abs(a - b) / d


def pct(rows, p):
    if not rows:
        return None
    rows = sorted(rows)
    k = min(len(rows) - 1, max(0, int(round((len(rows) - 1) * p))))
    return rows[k]


def load_ref(path):
    raw, adj = collections.defaultdict(dict), collections.defaultdict(dict)
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if str(r.get("resolution")) != "D":
                continue
            typ = str(r.get("type"))
            # normalizer type is raw/adjusted; accept type0/type7 too
            if typ in ("type0", "raw"):
                raw[r["symbol"]][str(r["date"])] = r
            elif typ in ("type7", "adjusted"):
                adj[r["symbol"]][str(r["date"])] = r
    return raw, adj


def load_db(symbols):
    con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    names = {r[0]: r[0] for r in con.execute(
        "SELECT DISTINCT symbol FROM price_history")}
    by_skel = collections.defaultdict(list)
    for n in names:
        by_skel[skeleton(n)].append(n)
    out = {}
    for sym in symbols:
        real = sym if sym in names else None
        if real is None:
            cand = by_skel.get(skeleton(sym)) or []
            real = cand[0] if len(cand) == 1 else None
        if real is None:
            out[sym] = {}
            continue
        rows = con.execute(
            "SELECT date,open,high,low,close,volume,last,src FROM price_history "
            "WHERE symbol=? ORDER BY date", (real,)).fetchall()
        out[sym] = {str(r[0]): {"open": r[1], "high": r[2], "low": r[3],
                                "close": r[4], "volume": r[5], "last": r[6],
                                "src": r[7]} for r in rows}
    con.close()
    return out


def load_pack(path):
    by = collections.defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("action", "replace_step") != "replace_step":
                continue
            try:
                ratio = float(r["ratio"])
            except (KeyError, TypeError, ValueError):
                continue
            if ratio > 0:
                by[r["symbol"]].append({
                    "date": str(r["effective_date"])[:10], "ratio": ratio,
                    "prov": r.get("prov_kind") or r.get("method") or "",
                    "source": r.get("source") or ""})
    for v in by.values():
        v.sort(key=lambda x: x["date"])
    return by


def factor_series(times, steps):
    """factor(t) = prod(ratio for step.date > t), two-pointer from the end."""
    out = {}
    cum, i = 1.0, len(steps) - 1
    for t in sorted(times, reverse=True):
        while i >= 0 and steps[i]["date"] > t:
            cum *= steps[i]["ratio"]
            i -= 1
        out[t] = cum
    return out


def ref_regimes(dates, raw, adj):
    """Segment the reference factor q=adj.close/raw.close into constant levels."""
    q = {}
    for d in dates:
        a, b = raw.get(d), adj.get(d)
        if not a or not b:
            continue
        try:
            ac, bc = float(a.get("close")), float(b.get("close"))
        except (TypeError, ValueError):
            continue
        if ac > 0 and bc > 0:
            q[d] = bc / ac
    seq = sorted(q)
    if len(seq) < 4:
        return [], {}
    # 5-day centered median smooths integer-rounding noise
    sm = {}
    for i, d in enumerate(seq):
        win = [q[x] for x in seq[max(0, i - 2):i + 3]]
        sm[d] = statistics.median(win)
    segments = []
    start = 0
    for i in range(1, len(seq)):
        a, b = sm[seq[i - 1]], sm[seq[i]]
        if abs(b / a - 1.0) > 0.001:
            segments.append((start, i - 1))
            start = i
    segments.append((start, len(seq) - 1))
    # absorb segments shorter than 3 days into the previous one
    merged = []
    for seg in segments:
        if merged and seg[1] - seg[0] + 1 < 3:
            merged[-1] = (merged[-1][0], seg[1])
        else:
            merged.append(seg)
    levels, reg = [], {}
    for k, (i, j) in enumerate(merged):
        # skip the boundary day (may be a stale print) when estimating the level
        vals = [q[seq[x]] for x in range(i + (1 if k else 0), j + 1)]
        lvl = statistics.median(vals) if vals else None
        levels.append({"start": seq[i], "end": seq[j], "level": lvl})
        for x in range(i, j + 1):
            reg[seq[x]] = lvl
    steps = []
    for k in range(1, len(levels)):
        if levels[k]["level"] and levels[k - 1]["level"]:
            steps.append({"date": levels[k]["start"],
                          "ratio": levels[k]["level"] / levels[k - 1]["level"],
                          "level_before": levels[k - 1]["level"],
                          "level_after": levels[k]["level"]})
    return steps, reg


def analyze(sym, ref_raw, ref_adj, db, steps):
    dates_all = sorted(set(ref_raw) | set(ref_adj) | set(db))
    common = sorted(set(ref_raw) & set(db))
    raw_stats = {}
    for f in CH_KEYS:
        diffs = []
        for d in common:
            rv = ref_raw[d].get(f)
            dv = db[d].get(f)
            if rv is None or dv is None:
                continue
            diffs.append(abs(float(rv) - float(dv)) / max(abs(float(rv)), 1e-9))
        raw_stats[f] = {
            "n": len(diffs),
            "exact_1e9": sum(1 for x in diffs if x <= 1e-9),
            "within_0.1pct": sum(1 for x in diffs if x <= 1e-3),
            "within_1pct": sum(1 for x in diffs if x <= 1e-2),
            "over_5pct": sum(1 for x in diffs if x > 5e-2),
            "median": pct(diffs, 0.5), "max": max(diffs) if diffs else None,
        }
    # price-basis: which local column matches reference close?
    basis = {}
    for col in ("close", "last"):
        diffs = [rel(ref_raw[d].get("close"), db[d].get(col)) for d in common
                 if ref_raw[d].get("close") is not None and db[d].get(col) is not None]
        diffs = [x for x in diffs if x is not None]
        basis[col] = {"n": len(diffs), "within_0.1pct": sum(1 for x in diffs if x <= 1e-3),
                      "median": pct(diffs, 0.5)}
    # open audit
    db_dates = sorted(db)
    prev_close = {}
    for i, d in enumerate(db_dates):
        if i:
            prev_close[d] = db[db_dates[i - 1]].get("close")
    open_eq_prev = sum(1 for d in common if db[d].get("open") and
                       prev_close.get(d) and db[d]["open"] == prev_close[d])
    refopen_eq_dbprev = sum(1 for d in common if ref_raw[d].get("open") and
                            prev_close.get(d) and
                            abs(float(ref_raw[d]["open"]) - float(prev_close[d])) < 1e-9)
    open_ref_match = [rel(ref_raw[d].get("open"), db[d].get("open")) for d in common
                      if ref_raw[d].get("open") is not None and db[d].get("open") is not None]
    open_ref_match = [x for x in open_ref_match if x is not None]
    # factor chain
    ref_steps, ref_level = ref_regimes(sorted(set(ref_raw) & set(ref_adj)), ref_raw, ref_adj)
    times = sorted(set(ref_raw) | set(ref_adj))
    our_f = factor_series(times, steps)
    fdates = [d for d in times if d in ref_level and ref_level[d] is not None]
    fdiffs = [rel(our_f.get(d), ref_level[d]) for d in fdates]
    fdiffs = [x for x in fdiffs if x is not None]
    factor_stats = {
        "dates": len(fdiffs),
        "equal_1e9": sum(1 for x in fdiffs if x <= 1e-9),
        "within_0.1pct": sum(1 for x in fdiffs if x <= 1e-3),
        "within_1pct": sum(1 for x in fdiffs if x <= 1e-2),
        "over_5pct": sum(1 for x in fdiffs if x > 5e-2),
        "median": pct(fdiffs, 0.5), "max": max(fdiffs) if fdiffs else None,
    }
    # step matching (+-5 days, greedy nearest)
    used = set()
    matched = []
    for rs in ref_steps:
        best = None
        for i, os_ in enumerate(steps):
            if i in used:
                continue
            delta = abs((__import__("datetime").date.fromisoformat(os_["date"]) -
                         __import__("datetime").date.fromisoformat(rs["date"])).days)
            if delta <= 5 and (best is None or delta < best[0]):
                best = (delta, i)
        if best is None:
            matched.append({"ref_date": rs["date"], "status": "missing",
                            "ref_ratio": rs["ratio"]})
        else:
            used.add(best[1])
            os_ = steps[best[1]]
            # q=adjusted/raw falls at a step date: level_after/level_before is
            # the inverse of the price ratio used by our chain.
            ref_ours = 1.0 / rs["ratio"]
            matched.append({
                "ref_date": rs["date"], "our_date": os_["date"],
                "delta_days": best[0],
                "status": "exact" if best[0] == 0 else "shifted",
                "ref_ratio": rs["ratio"], "ref_ratio_our_direction": ref_ours,
                "our_ratio": os_["ratio"],
                "ratio_rel": rel(os_["ratio"], ref_ours),
                "prov": os_["prov"]})
    extras = [{"our_date": s["date"], "our_ratio": s["ratio"], "prov": s["prov"],
               "delta": abs(float(s["ratio"]) - 1.0)}
              for i, s in enumerate(steps) if i not in used]
    step_stats = {
        "ref_steps": len(ref_steps), "our_steps": len(steps),
        "exact": sum(1 for m in matched if m["status"] == "exact"),
        "shifted_1_3": sum(1 for m in matched if m["status"] == "shifted" and m["delta_days"] <= 3),
        "shifted_4_5": sum(1 for m in matched if m["status"] == "shifted" and m["delta_days"] > 3),
        "missing": sum(1 for m in matched if m["status"] == "missing"),
        "extra": len(extras),
        "extra_material": sum(1 for e in extras if e["delta"] > 0.01),
        "extra_max_delta": max([e["delta"] for e in extras] or [0.0]),
        "ratio_over_5pct": sum(1 for m in matched if (m.get("ratio_rel") or 0) > 0.05),
        "ratio_over_1pct": sum(1 for m in matched if (m.get("ratio_rel") or 0) > 0.01),
        "max_ratio_rel": max([m["ratio_rel"] for m in matched
                              if m.get("ratio_rel") is not None] or [None],
                             key=lambda x: -1 if x is None else x),
    }
    # adjusted OHLC: isolate method (ref raw * our factor) and product (db raw * our factor)
    adj_stats = {}
    for label, src in (("method", ref_raw), ("product", db)):
        acc = {f: [] for f in ("open", "high", "low", "close")}
        for d in sorted(set(src) & set(ref_adj)):
            fct = our_f.get(d)
            if fct is None or ref_adj[d].get("close") is None:
                continue
            for f in acc:
                rv = ref_adj[d].get(f)
                sv = src[d].get(f)
                if rv is None or sv is None:
                    continue
                acc[f].append(abs(float(sv) * fct - float(rv)))
        adj_stats[label] = {
            f: {"n": len(v), "within_0.5rial": sum(1 for x in v if x <= 0.5),
                "within_1pct": None, "median_abs": pct(v, 0.5),
                "max_abs": max(v) if v else None}
            for f, v in acc.items()}
    # coverage
    ref_dates = set(ref_raw) | set(ref_adj)
    ref_only = sorted(ref_dates - set(db))
    db_only = sorted(set(db) - ref_dates)
    return {
        "symbol": sym,
        "ref_days": len(ref_dates), "db_days": len(db),
        "ref_first": min(ref_dates) if ref_dates else None,
        "ref_last": max(ref_dates) if ref_dates else None,
        "db_first": min(db) if db else None, "db_last": max(db) if db else None,
        "common_days": len(common),
        "ref_only_days": len(ref_only), "db_only_days": len(db_only),
        "ref_only_2010_2019": sum(1 for d in ref_only if d < "2020-01-01"),
        "ref_only_2020_2024": sum(1 for d in ref_only if "2020-01-01" <= d < "2025-01-01"),
        "raw": raw_stats, "basis": basis,
        "open_audit": {"n": len(common), "db_open_eq_prev_close": open_eq_prev,
                       "ref_open_eq_db_prev_close": refopen_eq_dbprev,
                       "ref_open_match_n": len(open_ref_match),
                       "ref_open_match_within_0.1pct": sum(1 for x in open_ref_match if x <= 1e-3),
                       "ref_open_match_median": pct(open_ref_match, 0.5)},
        "factor": factor_stats, "steps": step_stats,
        "step_detail": matched, "extra_steps": extras,
        "adjusted": adj_stats,
        "verdict": verdict(raw_stats, factor_stats, step_stats, adj_stats),
    }


def verdict(raw, factor, steps, adj):
    if factor["dates"] == 0:
        return "INSUFFICIENT_DATA"
    if factor["max"] is not None and factor["max"] > 0.05:
        return "FAIL_FACTOR"
    if steps["missing"] or steps["extra_material"] or steps["ratio_over_5pct"]:
        return "FAIL_STEPS"
    if factor["max"] is not None and factor["max"] > 0.001:
        return "PARTIAL_FACTOR"
    return "PASS_FACTOR"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="normalized dir (bars.ndjson.gz)")
    ap.add_argument("--pack", required=True, help="rebuild factors.jsonl")
    ap.add_argument("--label", required=True)
    args = ap.parse_args()
    raw, adj = load_ref(os.path.join(args.ref, "bars.ndjson.gz"))
    symbols = sorted(set(raw) | set(adj))
    db = load_db(symbols)
    pack = load_pack(args.pack)
    out = {}
    rows = []
    for sym in symbols:
        rec = analyze(sym, raw.get(sym, {}), adj.get(sym, {}), db.get(sym, {}),
                      pack.get(sym, []))
        out[sym] = rec
        r = {
            "symbol": sym, "ref_days": rec["ref_days"], "db_days": rec["db_days"],
            "common_days": rec["common_days"],
            "ref_only": rec["ref_only_days"], "db_only": rec["db_only_days"],
            "raw_open_match_pct": (100.0 * rec["raw"]["open"]["within_0.1pct"] /
                                   rec["raw"]["open"]["n"]) if rec["raw"]["open"]["n"] else None,
            "raw_close_match_pct": (100.0 * rec["raw"]["close"]["within_0.1pct"] /
                                    rec["raw"]["close"]["n"]) if rec["raw"]["close"]["n"] else None,
            "factor_dates": rec["factor"]["dates"],
            "factor_within_0.1pct": rec["factor"]["within_0.1pct"],
            "factor_max_rel": rec["factor"]["max"],
            "ref_steps": rec["steps"]["ref_steps"], "our_steps": rec["steps"]["our_steps"],
            "exact": rec["steps"]["exact"], "shifted": rec["steps"]["shifted_1_3"] + rec["steps"]["shifted_4_5"],
            "missing": rec["steps"]["missing"], "extra": rec["steps"]["extra"],
            "ratio_over_5pct": rec["steps"]["ratio_over_5pct"],
            "open_eq_prev": rec["open_audit"]["db_open_eq_prev_close"],
            "verdict": rec["verdict"],
        }
        rows.append(r)
    os.makedirs(EVID, exist_ok=True)
    with open(os.path.join(EVID, "reference-parity-%s.json" % args.label),
              "w", encoding="utf-8") as fh:
        json.dump({"label": args.label, "ref": args.ref, "pack": args.pack,
                   "per_symbol": out}, fh, ensure_ascii=False, indent=1)
    csv_path = os.path.join(ROOT, "_audit", "phase49-finalization",
                            "reference-parity-%s.csv" % args.label)
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    counts = collections.Counter(r["verdict"] for r in rows)
    print(json.dumps({"label": args.label, "symbols": len(rows),
                      "verdicts": dict(counts)}, ensure_ascii=False, indent=1))
    for r in rows:
        if r["verdict"] in ("FAIL_FACTOR", "FAIL_STEPS"):
            print("  %s verdict=%s factor_max=%s steps(ref/our/miss/extra)=%s/%s/%s/%s" % (
                r["symbol"], r["verdict"],
                "%.4g" % r["factor_max_rel"] if r["factor_max_rel"] is not None else None,
                r["ref_steps"], r["our_steps"], r["missing"], r["extra"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
