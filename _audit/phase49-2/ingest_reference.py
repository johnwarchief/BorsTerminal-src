#!/usr/bin/env python3
"""Build the Phase 4.9.2 independent candle DB from the Seed + fresh capture.

The Seed's price_history is never modified. The fresh Rahavard type0 raw bars
go into ``reference_raw``; type7 goes into ``reference_adjusted``; the implied
event ratios go into ``adjustment_factors`` with full provenance. Corporate
actions come from the timescale marks (DPS/EPS) and the Seed's official
share-change rows; factor-to-action links are evidence-based (date window +
ratio), and an unmatched event stays ``corporate_action_unclassified`` rather
than being guessed.

The output DB is a copy of the Seed Candidate at _audit/phase49-2/db/market.db.
Adjusted candles and verification are materialized by the Go candlebuild
command; this script only ingests and derives factors.
"""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEED = os.path.join(ROOT, "_audit", "phase49-full-verification", "seed", "market.db")
CAPTURE = os.path.join(ROOT, "_audit", "phase49-2", "rahavard", "pilot-capture.json")
PILOT = os.path.join(ROOT, "_audit", "phase49-2", "rahavard", "pilot-symbols.json")
PACK = os.path.join(ROOT, "data", "ra365_corrections",
                    "ra365-phase49-rebuild-full-v2", "factors.jsonl")
OUT_DIR = os.path.join(ROOT, "_audit", "phase49-2", "db")
DB = os.path.join(OUT_DIR, "market.db")
SUMMARY = os.path.join(ROOT, "_audit", "phase49-2", "evidence", "candle-ingest.json")

SHARE_WINDOW_DAYS = 7
DPS_WINDOW_DAYS = 45
PACK_WINDOW_DAYS = 7
SHARE_RATIO_TOL = 1e-3
DPS_RATIO_TOL = 2e-3
PACK_RATIO_TOL = 1e-6

SCHEMA = """
CREATE TABLE IF NOT EXISTS candle_capture_runs(
  run_id TEXT PRIMARY KEY, source TEXT NOT NULL, captured_at TEXT NOT NULL,
  input_sha256 TEXT NOT NULL, types TEXT NOT NULL, resolutions TEXT NOT NULL,
  symbols INTEGER NOT NULL, bars INTEGER NOT NULL, ingested_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reference_raw(
  symbol TEXT NOT NULL, date TEXT NOT NULL, open REAL, high REAL, low REAL,
  close REAL NOT NULL, volume REAL, run_id TEXT NOT NULL,
  capture_sha256 TEXT NOT NULL, PRIMARY KEY(symbol,date));
CREATE TABLE IF NOT EXISTS reference_adjusted(
  symbol TEXT NOT NULL, date TEXT NOT NULL, close REAL NOT NULL,
  run_id TEXT NOT NULL, capture_sha256 TEXT NOT NULL, PRIMARY KEY(symbol,date));
CREATE TABLE IF NOT EXISTS adjustment_factors(
  symbol TEXT NOT NULL, date TEXT NOT NULL, ratio REAL NOT NULL,
  kind TEXT NOT NULL, source TEXT NOT NULL, method TEXT NOT NULL,
  confidence TEXT NOT NULL, status TEXT NOT NULL,
  q_before REAL NOT NULL, q_after REAL NOT NULL, prev_close REAL,
  capture_sha256 TEXT NOT NULL, run_id TEXT NOT NULL, revision TEXT NOT NULL,
  details TEXT, created_at TEXT NOT NULL, PRIMARY KEY(symbol,date,revision));
CREATE TABLE IF NOT EXISTS adjustment_factor_audit(
  symbol TEXT NOT NULL, date TEXT NOT NULL, reason TEXT NOT NULL,
  pack_ratio REAL, ref_ratio REAL, pack_event_sig TEXT,
  details TEXT, run_id TEXT NOT NULL,
  PRIMARY KEY(symbol,date,reason,run_id));
CREATE TABLE IF NOT EXISTS corporate_actions(
  symbol TEXT NOT NULL, date TEXT NOT NULL, kind TEXT NOT NULL,
  value REAL, unit TEXT, fiscal_year TEXT, source TEXT NOT NULL,
  capture_sha256 TEXT, run_id TEXT NOT NULL, details TEXT,
  PRIMARY KEY(symbol,date,kind,source,value));
CREATE TABLE IF NOT EXISTS factor_action_links(
  symbol TEXT NOT NULL, factor_date TEXT NOT NULL, action_date TEXT NOT NULL,
  action_kind TEXT NOT NULL, relation TEXT NOT NULL, delta_days INTEGER,
  evidence TEXT, PRIMARY KEY(symbol,factor_date,action_date,action_kind));
CREATE TABLE IF NOT EXISTS candle_ingest_conflicts(
  symbol TEXT, date TEXT, field TEXT, old_value REAL, new_value REAL,
  old_src TEXT, new_src TEXT, run_id TEXT,
  PRIMARY KEY(symbol,date,field));
"""


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def date10(s):
    return str(s or "")[:10]


def days(a, b):
    import datetime
    try:
        return abs((datetime.date.fromisoformat(a)
                    - datetime.date.fromisoformat(b)).days)
    except ValueError:
        return 10 ** 6


def load_capture():
    cap = json.load(open(CAPTURE, encoding="utf-8"))
    capture_day = cap["source"]["captured_at"][:10]
    raw, adj, marks = defaultdict(dict), defaultdict(dict), defaultdict(list)
    partial = 0
    for s in cap["series"]:
        if s["ticker"].endswith(":type0"):
            for b in s["bars"]:
                d = b["utc"][:10]
                if d >= capture_day:
                    partial += 1
                    continue
                raw[s["symbol"]][d] = b
            for m in (s.get("marks") or {}).get("data") or []:
                marks[s["symbol"]].append(m)
        else:
            for b in s["bars"]:
                d = b["utc"][:10]
                if d >= capture_day:
                    continue
                adj[s["symbol"]][d] = b["close"]
    cap["_partial_bars_excluded"] = partial
    cap["_capture_day"] = capture_day
    return cap, raw, adj, marks


def load_pack():
    out = defaultdict(list)
    for line in open(PACK, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("action") == "suppress_step":
            continue
        out[r["symbol"]].append({
            "date": date10(r.get("effective_date")),
            "ratio": r.get("ratio"),
            "event_sig": r.get("event_sig") or "",
            "class": r.get("class") or "",
        })
    for rows in out.values():
        rows.sort(key=lambda x: x["date"])
    return out


def q_changes(raw, adj):
    dates = sorted(set(raw) & set(adj))
    q = [(d, raw[d]["close"] / adj[d]) for d in dates if raw[d].get("close") and adj[d]]
    out, prev = [], None
    for d, v in q:
        if prev is not None and abs(v / prev - 1.0) > 1e-9:
            out.append({"date": d, "ratio": v / prev, "q_before": prev, "q_after": v})
        prev = v
    return out, dict(q)


def classify(sym, ch, raw, marks, share, pack_steps):
    """Return (kind, link) using date window + ratio evidence only."""
    d = ch["date"]
    prev_date = max((x for x in raw if x < d), default=None)
    prev_close = raw[prev_date]["close"] if prev_date else None
    share_hit = None
    for sd, ratio in share:
        if days(sd, d) <= SHARE_WINDOW_DAYS and ratio > 0 \
                and abs(ratio / ch["ratio"] - 1.0) <= SHARE_RATIO_TOL:
            share_hit = (sd, ratio)
            break
    dps_hit = None
    if prev_close:
        for md, dps in marks:
            if days(md, d) <= DPS_WINDOW_DAYS and dps:
                cand = (prev_close - dps) / prev_close
                if cand > 0 and abs(cand / ch["ratio"] - 1.0) <= DPS_RATIO_TOL:
                    dps_hit = (md, dps, cand)
                    break
    kind = "corporate_action_unclassified"
    link = {}
    if share_hit and dps_hit:
        kind = "combined"
        link = {"share": share_hit, "dps": dps_hit}
    elif share_hit:
        kind = "capital_increase"
        link = {"share": share_hit}
    elif dps_hit:
        kind = "dividend"
        link = {"dps": dps_hit}
    else:
        for st in pack_steps:
            if days(st["date"], d) <= PACK_WINDOW_DAYS and st["ratio"] \
                    and abs(st["ratio"] / ch["ratio"] - 1.0) <= 1e-3:
                sig = st["event_sig"]
                if sig == "share":
                    kind = "capital_increase"
                elif sig in ("dps", "fund_dps", "pa"):
                    kind = "dividend"
                elif sig == "base_gap":
                    kind = "dividend"
                link = {"pack": st}
                break
    return kind, link, prev_close, prev_date


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="recreate the DB copy from the Seed")
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    if args.force and os.path.exists(DB):
        os.remove(DB)
    if not os.path.exists(DB):
        shutil.copy2(SEED, DB)
    cap, raw, adj, marks = load_capture()
    pack = load_pack()
    pilot = json.load(open(PILOT, encoding="utf-8"))
    capture_sha = cap["source"]["input_sha256"]
    run_id = "phase49-2-pilot-" + capture_sha[:12]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    con.execute("DELETE FROM candle_capture_runs WHERE run_id=?", (run_id,))
    bars = sum(len(raw[s]) + len(adj[s]) for s in raw)
    con.execute("INSERT INTO candle_capture_runs VALUES(?,?,?,?,?,?,?,?,?)",
                (run_id, "rahavard365-web-api", cap["source"]["captured_at"],
                 capture_sha, ",".join(cap["source"]["types"]),
                 ",".join(cap["source"]["resolutions"]), len(pilot), bars, now))

    ins = {}
    for sym, code in con.execute("SELECT l_val18, ins_code FROM instruments"):
        if sym and code:
            ins[sym] = code
    share_all = defaultdict(list)
    for code, d_even, old, new in con.execute(
            "SELECT ins_code,d_even,shares_old,shares_new FROM share_change_events"):
        if old and new and old > 0 and new > 0:
            share_all[code].append((date10(d_even), old / new))
    for code in share_all:
        share_all[code].sort()

    conflicts = 0
    for sym in sorted(raw):
        for dt, b in sorted(raw[sym].items()):
            old = con.execute(
                "SELECT open,high,low,close,volume,src FROM price_history "
                "WHERE symbol=? AND date=?", (sym, dt)).fetchone()
            if old:
                for i, field in enumerate(("open", "high", "low", "close")):
                    a, c = old[i], b.get(field)
                    if a is None or c is None:
                        continue
                    if abs(float(a) - float(c)) > 1e-9 * max(1.0, abs(float(c))):
                        con.execute(
                            "INSERT OR REPLACE INTO candle_ingest_conflicts "
                            "VALUES(?,?,?,?,?,?,?,?)",
                            (sym, dt, field, float(a), float(c), old[5] or "",
                             "rahavard-type0", run_id))
                        conflicts += 1
            con.execute(
                "INSERT OR REPLACE INTO reference_raw VALUES(?,?,?,?,?,?,?,?,?)",
                (sym, dt, b.get("open"), b.get("high"), b.get("low"),
                 b.get("close"), b.get("volume"), run_id, capture_sha))
        for dt, close in sorted(adj[sym].items()):
            con.execute(
                "INSERT OR REPLACE INTO reference_adjusted VALUES(?,?,?,?,?)",
                (sym, dt, close, run_id, capture_sha))

    # marks -> corporate actions
    action_count = 0
    for sym in sorted(marks):
        for m in marks[sym]:
            kind = None
            value = None
            fiscal = None
            if "dps" in m:
                kind, value = "dps", m["dps"].get("pure_dps")
                fiscal = date10(m["dps"].get("fiscal_year"))
                unit = "rial_per_share"
            elif "eps" in m:
                kind, value = "eps", m["eps"].get("pure_realized_eps")
                fiscal = date10(m["eps"].get("fiscal_year"))
                unit = "rial_per_share"
            else:
                continue
            con.execute(
                "INSERT OR IGNORE INTO corporate_actions VALUES(?,?,?,?,?,?,?,?,?,?)",
                (sym, date10(m.get("date_time")), kind, value, unit, fiscal,
                 "rahavard-timescale-marks", capture_sha, run_id,
                 json.dumps(m, ensure_ascii=False, sort_keys=True)))
            action_count += 1
    for sym in sorted(raw):
        code = ins.get(sym)
        for dt, ratio in share_all.get(code, []):
            con.execute(
                "INSERT OR IGNORE INTO corporate_actions VALUES(?,?,?,?,?,?,?,?,?,?)",
                (sym, dt, "share_change", ratio, "old_over_new", None,
                 "tsetmc_share_change_by_flow", None, run_id,
                 json.dumps({"ins_code": code})))
            action_count += 1

    factors = []
    missing_pack = 0
    for sym in sorted(raw):
        steps = pack.get(sym, [])
        changes, q = q_changes(raw[sym], adj[sym])
        sym_marks = [(date10(m["date_time"]), m["dps"].get("pure_dps"))
                     for m in marks[sym] if "dps" in m]
        sym_share = share_all.get(ins.get(sym), [])
        for ch in changes:
            kind, link, prev_close, prev_date = classify(
                sym, ch, raw[sym], sym_marks, sym_share, steps)
            details = {
                "q_before": ch["q_before"], "q_after": ch["q_after"],
                "prev_close": prev_close, "prev_date": prev_date,
                "link": {k: (list(v) if isinstance(v, tuple) else v)
                         for k, v in link.items()},
                "bars": len(raw[sym]),
            }
            factors.append((sym, ch["date"], ch["ratio"], kind,
                            "rahavard-type7-type0", "implied-ratio-change",
                            "reference-exact", "MEASURED_REFERENCE",
                            ch["q_before"], ch["q_after"], prev_close,
                            capture_sha, run_id, "", json.dumps(
                                details, ensure_ascii=False, sort_keys=True), now))
            if link.get("share"):
                sd, sr = link["share"]
                con.execute(
                    "INSERT OR REPLACE INTO factor_action_links VALUES(?,?,?,?,?,?,?)",
                    (sym, ch["date"], sd, "share_change", "matched-ratio",
                     days(sd, ch["date"]), json.dumps({"ratio": sr})))
            if link.get("dps"):
                md, dps, cand = link["dps"]
                con.execute(
                    "INSERT OR REPLACE INTO factor_action_links VALUES(?,?,?,?,?,?,?)",
                    (sym, ch["date"], md, "dps", "matched-formula",
                     days(md, ch["date"]),
                     json.dumps({"dps": dps, "formula": cand})))
            if link.get("pack"):
                st = link["pack"]
                con.execute(
                    "INSERT OR REPLACE INTO factor_action_links VALUES(?,?,?,?,?,?,?)",
                    (sym, ch["date"], st["date"], "pack-step", "matched-ratio",
                     days(st["date"], ch["date"]),
                     json.dumps(st, ensure_ascii=False, sort_keys=True)))
        # pack-step audit against the reference changes
        for st in steps:
            if not st["ratio"]:
                continue
            near = [c for c in changes if days(c["date"], st["date"]) <= PACK_WINDOW_DAYS]
            if not near:
                reason = "no_reference_change"
                con.execute(
                    "INSERT OR REPLACE INTO adjustment_factor_audit VALUES(?,?,?,?,?,?,?,?)",
                    (sym, st["date"], reason, st["ratio"], None, st["event_sig"],
                     json.dumps(st, ensure_ascii=False, sort_keys=True), run_id))
                continue
            best = min(near, key=lambda c: days(c["date"], st["date"]))
            if abs(best["ratio"] / st["ratio"] - 1.0) > PACK_RATIO_TOL:
                con.execute(
                    "INSERT OR REPLACE INTO adjustment_factor_audit VALUES(?,?,?,?,?,?,?,?)",
                    (sym, st["date"], "superseded_ratio", st["ratio"],
                     best["ratio"], st["event_sig"],
                     json.dumps({"ref_date": best["date"]}, ensure_ascii=False),
                     run_id))
        for ch in changes:
            if not any(days(c["date"], ch["date"]) <= PACK_WINDOW_DAYS
                       and c["ratio"] and abs(c["ratio"] / ch["ratio"] - 1.0) <= 1e-3
                       for c in steps):
                missing_pack += 1
                con.execute(
                    "INSERT OR REPLACE INTO adjustment_factor_audit VALUES(?,?,?,?,?,?,?,?)",
                    (sym, ch["date"], "missing_pack_step", None, ch["ratio"],
                     None, None, run_id))

    revision = hashlib.sha256(
        ("%s\n" % capture_sha).encode() +
        "\n".join("%s|%s|%.17g" % (f[0], f[1], f[2])
                  for f in sorted(factors)).encode()).hexdigest()
    factors = [tuple(list(f[:13]) + [revision] + list(f[14:])) for f in factors]
    con.executemany(
        "INSERT OR REPLACE INTO adjustment_factors VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        factors)
    con.commit()
    counts = {
        "reference_raw_rows": con.execute("SELECT COUNT(*) FROM reference_raw").fetchone()[0],
        "reference_adjusted_rows":
            con.execute("SELECT COUNT(*) FROM reference_adjusted").fetchone()[0],
        "adjustment_factors": len(factors),
        "kinds": dict(con.execute(
            "SELECT kind,COUNT(*) FROM adjustment_factors GROUP BY kind").fetchall()),
        "audit": dict(con.execute(
            "SELECT reason,COUNT(*) FROM adjustment_factor_audit GROUP BY reason").fetchall()),
        "corporate_actions": action_count,
        "conflicts_with_seed_raw": conflicts,
        "missing_pack_steps": missing_pack,
    }
    con.close()
    summary = {
        "schema": "phase49-2-candle-ingest-v1",
        "seed": os.path.relpath(SEED, ROOT).replace("\\", "/"),
        "seed_sha256": sha_file(SEED),
        "db": os.path.relpath(DB, ROOT).replace("\\", "/"),
        "db_sha256": sha_file(DB),
        "capture": os.path.relpath(CAPTURE, ROOT).replace("\\", "/"),
        "capture_sha256": capture_sha,
        "run_id": run_id,
        "revision": revision,
        "pilot_symbols": len(pilot),
        "capture_day": cap["_capture_day"],
        "partial_bars_excluded": cap["_partial_bars_excluded"],
        "counts": counts,
    }
    os.makedirs(os.path.dirname(SUMMARY), exist_ok=True)
    with open(SUMMARY, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
