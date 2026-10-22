# -*- coding: utf-8 -*-
"""Round 18 general repair: replace fallback price_history rows with published rows.

Evidence: the chart's local fallback served 220 raw-contract mismatches on 101
fallback assets.  Most price_history rows are src NULL or 'board'; 10,448 rows
carry the base <OPEN> column as open.  This tool re-parses the already fetched
TSETMC CSV for each measured asset with candle_contract.from_csv_row (open=FIRST,
close=CLOSE, last=LAST) and upserts rows with src=published inside the existing
per-symbol date range.  It is keyed, idempotent and only writes to a copy.

It never touches the operational database and never expands a symbol's range.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get("RA365_R18_CACHE", "D:/BorsTerminal-tmp/ra365_round18")
ART = os.path.join(ROOT, "artifacts", "ra365", "r18")
SRC_DB = "D:/BorsTerminal-tmp/ra365_round17/market_r17_migrated.db"
OPERATIONAL = os.path.abspath(os.path.join(ROOT, "market.db"))
CACHE_CSV = os.path.join(CACHE, "cache", "tsetmc_csv")

sys.path.insert(0, ROOT)
import candle_contract as CC  # noqa: E402


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def copy_db(src, dst):
    if os.path.exists(dst):
        raise SystemExit("destination exists: %s (remove it explicitly)" % dst)
    con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    out = sqlite3.connect(dst)
    with out:
        con.backup(out)
    out.close(); con.close()


def repair(dst, cohort_path, report_path):
    con = sqlite3.connect(dst)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    rows = []
    total = {"symbols": 0, "csv_rows_in_range": 0, "upserted": 0,
             "added": 0, "replaced": 0, "skipped_no_db": 0}
    for line in open(cohort_path, encoding="utf-8"):
        j = json.loads(line)
        sym = j["symbol"]; ins = j["ins_code"]
        rng = con.execute("SELECT MIN(date),MAX(date) FROM price_history WHERE symbol=?",
                          (sym,)).fetchone()
        if not rng or not rng[0]:
            total["skipped_no_db"] += 1
            continue
        lo, hi = rng
        p = os.path.join(CACHE_CSV, ins + ".csv")
        if not os.path.exists(p):
            continue
        existing = {r[0] for r in con.execute(
            "SELECT date FROM price_history WHERE symbol=? AND date BETWEEN ? AND ?",
            (sym, lo, hi))}
        n_in = n_up = n_add = n_rep = 0
        text = open(p, encoding="utf-8", errors="replace").read()
        head = True
        for ln in text.splitlines():
            if not ln.strip():
                continue
            if head and ln.lstrip().startswith("<"):
                head = False
                continue
            fields = [x.strip() for x in ln.split(",")]
            dt = CC.iso_from_csv(fields)
            if not dt or dt < lo or dt > hi:
                continue
            bar = CC.from_csv_row(sym, fields, src=CC.SRC_PUBLISHED)
            if not bar:
                continue
            n_in += 1
            con.execute(CC.UPSERT_SQL, CC.upsert_row(bar))
            n_up += 1
            if dt in existing:
                n_rep += 1
            else:
                n_add += 1
        con.commit()
        total["symbols"] += 1
        total["csv_rows_in_range"] += n_in
        total["upserted"] += n_up
        total["added"] += n_add
        total["replaced"] += n_rep
        rows.append({"symbol": sym, "ins_code": ins, "range_start": lo, "range_end": hi,
                     "csv_in_range": n_in, "upserted": n_up,
                     "added": n_add, "replaced": n_rep})
        if total["symbols"] % 250 == 0:
            print("  repaired %d symbols, %d rows" % (total["symbols"], total["upserted"]),
                  flush=True)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    src_counts = dict(con.execute(
        "SELECT src,COUNT(*) FROM price_history GROUP BY src").fetchall())
    con.close()
    total["src_counts"] = {str(k): v for k, v in src_counts.items()}
    total["integrity_check"] = integrity
    total["db_sha256"] = sha(dst)
    total["db_bytes"] = os.path.getsize(dst)
    with open(report_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    return total


def parity(dbpath, cohort_path, out_path):
    """Direct price_history vs TSETMC contract, before/after."""
    ref = sqlite3.connect(f"file:{os.path.join(CACHE, 'reference.db')}?mode=ro", uri=True)
    db = sqlite3.connect(f"file:{dbpath}?mode=ro", uri=True)
    sys.path.insert(0, ROOT)
    import importlib
    R = importlib.import_module("tools.ra365_round18_raw") if False else None
    # local helpers (same contract as the raw runner)
    import candle_contract as CC2
    def eff_open(first, base, high, low, close):
        if first > 0:
            return first
        if base > 0:
            return min(max(base, low), high)
        return close
    def status(refv, prod):
        if refv is None or prod is None:
            return "NULL"
        if abs(refv - prod) <= 0.5:
            return "EXACT" if refv == prod else "TOL"
        if refv and abs(refv - prod) / abs(refv) <= 0.0005:
            return "ROUNDING"
        return "DIFF"
    out = []
    for line in open(cohort_path, encoding="utf-8"):
        j = json.loads(line)
        if not str(j.get("adjust_source") or "").startswith("local-db"):
            continue
        sym = j["symbol"]; ins = j["ins_code"]
        T = {r[0]: r for r in ref.execute(
            "SELECT date,first,high,low,close,volume,base,last FROM tsetmc WHERE ins_code=?",
            (ins,))}
        rows = db.execute("SELECT date,open,high,low,close,volume,last,src FROM price_history "
                          "WHERE symbol=?", (sym,)).fetchall()
        cnt = {"rows": 0, "ok": 0, "diff": 0, "last_null": 0, "open_base": 0}
        for d, o, h, l, c, v, last, src in rows:
            t = T.get(d)
            if not t or t[2] <= 0 or t[3] <= 0 or t[4] <= 0:
                continue
            o_eff = eff_open(t[1], t[6], t[2], t[3], t[4])
            hp, lp = CC2.widen(o_eff, t[2], t[3], t[4])
            vals = [status(o_eff, o), status(hp, h), status(lp, l),
                    status(t[4], c), status(t[5], v), status(t[7], last)]
            cnt["rows"] += 1
            if all(x in ("EXACT", "TOL", "NULL") for x in vals):
                cnt["ok"] += 1
            else:
                cnt["diff"] += 1
            if last is None and t[7] > 0:
                cnt["last_null"] += 1
            if t[1] > 0 and o is not None and abs(o - t[6]) <= 0.5 and abs(o - t[1]) > 0.5:
                cnt["open_base"] += 1
        out.append({"symbol": sym, "adjust_source": j.get("adjust_source"),
                    "rows": cnt["rows"], "ok": cnt["ok"], "diff": cnt["diff"],
                    "ok_pct": round(100.0 * cnt["ok"] / cnt["rows"], 4) if cnt["rows"] else "",
                    "last_null": cnt["last_null"], "open_base": cnt["open_base"]})
    db.close(); ref.close()
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader(); w.writerows(out)
    n = sum(r["rows"] for r in out); ok = sum(r["ok"] for r in out)
    print(json.dumps({"assets": len(out), "rows": n, "ok": ok,
                      "ok_pct": round(100.0 * ok / max(1, n), 4),
                      "last_null": sum(r["last_null"] for r in out),
                      "open_base": sum(r["open_base"] for r in out)}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC_DB)
    ap.add_argument("--dst", default=os.path.join(CACHE, "market_r18_repaired.db"))
    ap.add_argument("--cohort", default=os.path.join(CACHE, "cohort.jsonl"))
    ap.add_argument("--copy-only", action="store_true")
    ap.add_argument("--measure", default="")
    a = ap.parse_args()
    if os.path.abspath(a.src) == OPERATIONAL or os.path.abspath(a.dst) == OPERATIONAL:
        raise SystemExit("refusing to touch the operational database")
    if not os.path.exists(a.dst):
        print("copying", a.src, "->", a.dst)
        copy_db(a.src, a.dst)
    if a.copy_only:
        print("sha", sha(a.dst), "bytes", os.path.getsize(a.dst))
        return
    report = os.path.join(ART, "price-history-repair.csv")
    t0 = time.time()
    result = repair(a.dst, a.cohort, report)
    result["elapsed_s"] = round(time.time() - t0, 1)
    with open(os.path.join(ART, "price-history-repair-manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
