# -*- coding: utf-8 -*-
"""RA365 Round 18 - independent raw OHLC parity before any adjustment.

Layers:
  A  BorsTerminal raw (chart candles as produced by the live pipeline)
  B  TSETMC raw daily payload (CSV, cross-checked on a sample with JSON)
  C  Rahavard type0 daily bars (reference only; semantics measured, not assumed)

The tool never applies a factor, never edits a DB and never fills a missing
bar.  Missing bars are counted as coverage, not as numeric differences.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import hashlib
import json
import os
import sqlite3
import sys
import threading
import time
from collections import Counter, defaultdict

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.dirname(os.path.dirname(ROOT))
REF_FILE = os.path.join(BASE, "_scratch", "ra_fup_2026_10_20", "ref_bars_v2.jsonl")
PROD_FILE = os.path.join(BASE, "_scratch", "ra_round3", "product_live_final_v4.jsonl")
MANIFEST = os.path.join(ROOT, "_audit", "RAHAVARD-FULL-UNIVERSE-MANIFEST-v2-2026-10-20.csv")
CACHE = os.environ.get("RA365_R18_CACHE", "D:/BorsTerminal-tmp/ra365_round18")
ART = os.path.join(ROOT, "artifacts", "ra365", "r18")
CSV_URL = "https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyListCSV/{ins}/19900101"
JSON_URL = "https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/{ins}/{top}"
HDR = {"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/csv"}

sys.path.insert(0, ROOT)
import candle_contract as CC  # noqa: E402

PRICE_ABS = 0.5          # display tolerance already used by the parity protocol
PRICE_REL_ROUND = 0.0005  # 0.05%: rounding-only, never called exact
MISS_SAMPLE_CAP = 40000
DIFF_SAMPLE_CAP = 60000


def iso8(d):
    s = str(d)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(a, b):
    if b in (None, 0):
        return None
    return abs(a - b) / abs(b)


def pctile(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    i = min(len(xs) - 1, max(0, int(q * (len(xs) - 1) + 0.5)))
    return xs[i]


def load_manifest():
    rows = list(csv.DictReader(open(MANIFEST, encoding="utf-8-sig")))
    by_symbol = defaultdict(list)
    for r in rows:
        if r.get("ra_asset_id"):
            by_symbol[r["symbol"]].append(r)
    return rows, by_symbol


def cmd_cohort(args):
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(ART, exist_ok=True)
    rows, by_symbol = load_manifest()
    best = {}
    product_symbols = set()
    status = Counter()
    for line in open(PROD_FILE, encoding="utf-8"):
        j = json.loads(line)
        sym = j.get("symbol")
        cands = j.get("candles") or []
        product_symbols.add(sym)
        status[j.get("status")] += 1
        for r in by_symbol.get(sym) or []:
            aid = r["ra_asset_id"]
            if aid not in best or len(cands) > len(best[aid]["candles"]):
                best[aid] = {"row": r, "record": j, "candles": cands}

    vols = {}
    out_path = os.path.join(CACHE, "cohort.jsonl")
    dup_total = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for aid in sorted(best, key=lambda x: int(x) if x.isdigit() else x):
            b = best[aid]
            j = b["record"]
            r = b["row"]
            vols.clear()
            for v in j.get("volumes") or []:
                vols[str(v.get("time"))[:10]] = v.get("value")
            seen = {}
            dups = 0
            rows_out = []
            for c in b["candles"]:
                d = str(c.get("time"))[:10]
                if d in seen:
                    dups += 1
                seen[d] = 1
                rows_out.append([
                    d, c.get("open"), c.get("high"), c.get("low"), c.get("close"),
                    c.get("closing"), c.get("last"), c.get("high_raw"), c.get("low_raw"),
                    vols.get(d), c.get("basis"),
                ])
            rows_out.sort(key=lambda x: x[0])
            dup_total += dups
            rec = {
                "ra_asset_id": aid, "symbol": j.get("symbol"), "ins_code": r.get("ins_code"),
                "ra_class": r.get("ra_class"), "paper_type": r.get("paper_type"),
                "basis": j.get("priceBasis"), "adjust_source": j.get("adjustSource"),
                "product_source": j.get("_round3_source"),
                "count": len(rows_out), "duplicate_dates": dups,
                "first_date": rows_out[0][0] if rows_out else None,
                "last_date": rows_out[-1][0] if rows_out else None,
                "candles": rows_out,
                "factors": [[str(x.get("time"))[:10], x.get("factor")]
                            for x in j.get("factors") or []],
                "adjust_events": j.get("adjustEvents") or [],
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    all_assets = set(r["ra_asset_id"] for r in rows if r.get("ra_asset_id"))
    measured = set(best)
    manifest = {
        "round": "ra365-r18",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "layer_a": {
            "name": "BorsTerminal raw chart candles",
            "file": PROD_FILE, "sha256": sha256_file(PROD_FILE),
            "records": sum(status.values()), "status": dict(status),
            "note": "candles are pre-factor; `close` is basis-selected, `closing` is official",
        },
        "manifest": {"file": MANIFEST, "sha256": sha256_file(MANIFEST),
                     "rows": len(rows), "symbols_with_asset": len(by_symbol)},
        "universe": {
            "assets_in_manifest": len(all_assets),
            "assets_with_product": len(measured),
            "assets_missing_product": len(all_assets - measured),
            "product_symbols_without_manifest_asset": len(product_symbols - set(by_symbol)),
            "duplicate_candle_dates": dup_total,
        },
        "cohort_file": out_path,
        "cohort_sha256": sha256_file(out_path),
        "layers": ["A=BorsTerminal raw", "B=TSETMC raw", "C=Rahavard type0"],
    }
    with open(os.path.join(ART, "raw-ohlc-cohort-manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(json.dumps(manifest["universe"], ensure_ascii=False))


def _valid_csv(path):
    try:
        if os.path.getsize(path) < 80:
            return False
        with open(path, encoding="utf-8", errors="replace") as f:
            head = f.readline()
            second = f.readline()
        return head.strip().startswith("<TICKER>") and second.strip() != ""
    except OSError:
        return False


def _fetch_one(ins, cache_dir, retries, timeout, json_top):
    p = os.path.join(cache_dir, ins + ".csv")
    if _valid_csv(p):
        return {"ins_code": ins, "status": "CACHED", "bytes": os.path.getsize(p),
                "sha256": sha256_file(p), "http": "", "error": ""}
    last = ""
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(CSV_URL.format(ins=ins), headers=HDR, timeout=timeout)
            if r.status_code == 200 and r.text.startswith("<TICKER>") and len(r.text) > 80:
                tmp = p + ".tmp"
                with open(tmp, "w", encoding="utf-8", newline="") as f:
                    f.write(r.text)
                os.replace(tmp, p)
                res = {"ins_code": ins, "status": "OK", "bytes": os.path.getsize(p),
                       "sha256": sha256_file(p), "http": 200, "error": ""}
                if json_top:
                    jp = os.path.join(cache_dir, ins + ".json")
                    try:
                        jr = requests.get(JSON_URL.format(ins=ins, top=json_top),
                                          headers=HDR, timeout=timeout)
                        if jr.status_code == 200 and jr.text.startswith("{"):
                            with open(jp + ".tmp", "w", encoding="utf-8") as f:
                                f.write(jr.text)
                            os.replace(jp + ".tmp", jp)
                            res["json"] = True
                    except Exception as e:
                        res["json_error"] = str(e)[:80]
                return res
            last = f"HTTP {r.status_code}"
            if r.status_code == 429:
                wait = r.headers.get("Retry-After")
                try:
                    wait = float(wait) if wait else min(30, 2 ** attempt)
                except ValueError:
                    wait = min(30, 2 ** attempt)
                time.sleep(wait)
            elif r.status_code >= 500:
                time.sleep(min(20, 2 ** attempt) + 0.25 * attempt)
        except Exception as e:
            last = str(e)[:120]
            time.sleep(min(20, 2 ** attempt) + 0.25 * attempt)
    return {"ins_code": ins, "status": "FAILED", "bytes": 0, "sha256": "",
            "http": "", "error": last}


def cmd_fetch(args):
    cache = os.path.join(CACHE, "cache", "tsetmc_csv")
    os.makedirs(cache, exist_ok=True)
    ins = []
    for line in open(os.path.join(CACHE, "cohort.jsonl"), encoding="utf-8"):
        j = json.loads(line)
        if j.get("ins_code"):
            ins.append(j["ins_code"])
    ins = sorted(set(ins))
    if args.limit:
        ins = ins[:args.limit]
    status_path = os.path.join(CACHE, "fetch-status.csv")
    done = {}
    if os.path.exists(status_path):
        for r in csv.DictReader(open(status_path, encoding="utf-8-sig")):
            done[r["ins_code"]] = r
    todo = [x for x in ins if not _valid_csv(os.path.join(cache, x + ".csv"))]
    print(f"fetch: {len(ins)} instruments, {len(todo)} missing cache, workers={args.workers}")
    lock = threading.Lock()
    out = open(status_path, "a", encoding="utf-8-sig", newline="")
    w = csv.writer(out)
    if out.tell() == 0:
        w.writerow(["ins_code", "status", "bytes", "sha256", "http", "error", "fetched_at"])
    ok = fail = 0
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_fetch_one, x, cache, args.retries, args.timeout,
                          args.json_top if args.json else 0): x for x in todo}
        for i, fut in enumerate(cf.as_completed(futs), 1):
            r = fut.result()
            r["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            with lock:
                w.writerow([r["ins_code"], r["status"], r["bytes"], r["sha256"],
                            r["http"], r["error"], r["fetched_at"]])
                if i % 50 == 0:
                    out.flush()
            if r["status"] in ("OK", "CACHED"):
                ok += 1
            else:
                fail += 1
            if i % 100 == 0:
                print(f"  {i}/{len(todo)} ok={ok} fail={fail} "
                      f"({time.time()-t0:.0f}s)", flush=True)
    out.close()
    print(f"fetch done: ok={ok} fail={fail} in {time.time()-t0:.0f}s")


def _parse_csv_rows(text):
    rows = []
    head = None
    for ln in text.splitlines():
        if not ln.strip():
            continue
        if ln.strip().startswith("<"):
            head = ln
            continue
        p = [x.strip() for x in ln.split(",")]
        if len(p) < 12:
            continue
        d = iso8(p[1])
        if not d:
            continue
        try:
            rows.append((d, float(p[2] or 0), float(p[3]), float(p[4]), float(p[5]),
                         float(p[6] or 0), float(p[7] or 0), float(p[10] or 0),
                         float(p[11] or 0)))
        except ValueError:
            continue
    return head, rows



def cmd_fetch_variants(args):
    """Fetch every InsCode variant of the measured assets (renames/capital changes)."""
    cache = os.path.join(CACHE, "cache", "tsetmc_csv")
    os.makedirs(cache, exist_ok=True)
    rows, _ = load_manifest()
    cohort = set()
    for line in open(os.path.join(CACHE, "cohort.jsonl"), encoding="utf-8"):
        cohort.add(json.loads(line)["ra_asset_id"])
    ins = sorted({r["ins_code"] for r in rows
                  if r.get("ra_asset_id") in cohort and r.get("ins_code")})
    todo = [x for x in ins if not _valid_csv(os.path.join(cache, x + ".csv"))]
    print(f"variants: {len(ins)} instruments, {len(todo)} missing")
    if not todo:
        return
    status_path = os.path.join(CACHE, "fetch-variants-status.csv")
    out = open(status_path, "a", encoding="utf-8-sig", newline="")
    w = csv.writer(out)
    if out.tell() == 0:
        w.writerow(["ins_code", "status", "bytes", "sha256", "http", "error", "fetched_at"])
    ok = fail = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_fetch_one, x, cache, args.retries, args.timeout, 0): x
                for x in todo}
        for i, fut in enumerate(cf.as_completed(futs), 1):
            r = fut.result(); r["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            w.writerow([r["ins_code"], r["status"], r["bytes"], r["sha256"],
                        r["http"], r["error"], r["fetched_at"]])
            ok += r["status"] in ("OK", "CACHED"); fail += r["status"] not in ("OK", "CACHED")
            if i % 100 == 0:
                print(f"  {i}/{len(todo)} ok={ok} fail={fail}", flush=True)
    out.close()
    print(f"variants done: ok={ok} fail={fail}")


def cmd_reference(args):
    db_path = os.path.join(CACHE, "reference.db")
    if os.path.exists(db_path) and not args.force:
        print("reference.db exists; use --force to rebuild")
        return
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("""CREATE TABLE tsetmc(
        ins_code TEXT, date TEXT, first REAL, high REAL, low REAL, close REAL,
        value REAL, volume REAL, base REAL, last REAL, PRIMARY KEY(ins_code,date))""")
    con.execute("""CREATE TABLE tsetmc_meta(
        ins_code TEXT PRIMARY KEY, rows INTEGER, first_date TEXT, last_date TEXT,
        duplicate_dates INTEGER, header TEXT, sha256 TEXT)""")
    con.execute("""CREATE TABLE type0(
        ra_asset_id TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
        volume REAL, PRIMARY KEY(ra_asset_id,date))""")
    con.execute("""CREATE TABLE type7(
        ra_asset_id TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
        volume REAL, PRIMARY KEY(ra_asset_id,date))""")
    cache = os.path.join(CACHE, "cache", "tsetmc_csv")
    n_rows = n_bad = 0
    for line in open(os.path.join(CACHE, "cohort.jsonl"), encoding="utf-8"):
        j = json.loads(line)
        ins = j.get("ins_code")
        if not ins:
            continue
        p = os.path.join(cache, ins + ".csv")
        if not os.path.exists(p):
            con.execute("INSERT OR REPLACE INTO tsetmc_meta VALUES(?,?,?,?,?,?,?)",
                        (ins, 0, "", "", 0, "MISSING", ""))
            n_bad += 1
            continue
        text = open(p, encoding="utf-8", errors="replace").read()
        head, rows = _parse_csv_rows(text)
        by_date = {}
        dups = 0
        for r in rows:
            d = r[0]
            if d in by_date:
                dups += 1
                if (r[5] or 0) >= (by_date[d][5] or 0):
                    by_date[d] = r
            else:
                by_date[d] = r
        vals = [(ins, d, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8])
                for d, r in sorted(by_date.items())]
        con.executemany("INSERT OR REPLACE INTO tsetmc VALUES(?,?,?,?,?,?,?,?,?,?)", vals)
        n_rows += len(vals)
        ds = sorted(by_date)
        con.execute("INSERT OR REPLACE INTO tsetmc_meta VALUES(?,?,?,?,?,?,?)",
                    (ins, len(vals), ds[0] if ds else "", ds[-1] if ds else "",
                     dups, (head or "")[:200], hashlib.sha256(text.encode()).hexdigest()))

    asset_ids = set()
    for line in open(os.path.join(CACHE, "cohort.jsonl"), encoding="utf-8"):
        asset_ids.add(json.loads(line)["ra_asset_id"])
    n0 = n7 = 0
    for line in open(REF_FILE, encoding="utf-8"):
        j = json.loads(line)
        aid = str(j.get("asset_id") or "")
        typ = j.get("type")
        if aid not in asset_ids or typ not in ("type0", "type7") or j.get("res") != "D":
            continue
        vals = []
        for b in j.get("bars") or []:
            if isinstance(b, list):
                u, o, h, l, c, v = (list(b) + [None] * 6)[:6]
            else:
                u, o, h, l, c, v = (b.get("utc"), b.get("open"), b.get("high"),
                                    b.get("low"), b.get("close"), b.get("volume"))
            d = str(u)[:10]
            try:
                vals.append((aid, d, float(o), float(h), float(l), float(c), float(v or 0)))
            except (TypeError, ValueError):
                continue
        table = "type0" if typ == "type0" else "type7"
        con.executemany(f"INSERT OR REPLACE INTO {table} VALUES(?,?,?,?,?,?,?)", vals)
        if typ == "type0":
            n0 += len(vals)
        else:
            n7 += len(vals)
    con.commit()
    con.execute("CREATE INDEX idx_t0_date ON type0(ra_asset_id,date)")
    con.commit()
    con.close()
    print(f"reference: tsetmc rows={n_rows} missing={n_bad} type0={n0} type7={n7}")


def _widen(open_, high, low, close):
    return CC.widen(open_, high, low, close)


def _eff_open(t_first, t_base, t_high, t_low, t_close):
    if t_first > 0:
        return t_first
    if t_base > 0:
        return min(max(t_base, t_low), t_high)
    return t_close


def _status(ref, prod):
    if prod is None or ref is None:
        return "NULL"
    try:
        ref = float(ref); prod = float(prod)
    except (TypeError, ValueError):
        return "NULL"
    if ref == prod:
        return "EXACT"
    d = abs(ref - prod)
    if d <= PRICE_ABS:
        return "TOL"
    if ref and d / abs(ref) <= PRICE_REL_ROUND:
        return "ROUNDING"
    return "DIFF"


def cmd_measure(args):
    db_path = os.path.join(CACHE, "reference.db")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    fields = ["open_first", "open_eff", "high_parser", "low_parser",
              "high_contract", "low_contract", "high_literal", "low_literal",
              "close_official", "close_last", "close_display", "volume"]
    parity_path = os.path.join(ART, "raw-ohlc-parity.csv")
    t0_path = os.path.join(ART, "raw-ohlc-type0-parity.csv")
    sample_path = os.path.join(ART, "raw-ohlc-mismatch-samples.csv")
    missing_path = os.path.join(ART, "raw-ohlc-missing.csv")
    pf = open(parity_path, "w", encoding="utf-8-sig", newline="")
    wf = csv.writer(pf)
    wf.writerow(["ra_asset_id", "symbol", "ins_code", "basis", "product_count",
                 "tsetmc_rows", "tsetmc_tradable", "type0_rows", "common_b", "common_c",
                 "b_cmp", "b_ok", "b_ok_pct", "contract_cmp", "contract_ok",
                 "contract_ok_pct", "b_diff", "b_null",
                 "row_pairs", "row_contract_exact", "row_contract_tol",
                 "row_contract_exact_pct", "row_contract_tol_pct",
                 "row_display_exact", "row_ohlcv_exact",
                 "missing_p_no_trade", "missing_p_product",
                 "missing_r_ref", "p_before_t", "p_after_t", "p_start", "p_end",
                 "t_start", "t_end", "t0_flat", "status"] +
                [f"{f}_{s}" for f in fields for s in ("cmp", "exact", "tol", "diff", "null")] +
                [f"{f}_{s}" for f in fields for s in ("p50_abs", "p95_abs", "max_abs")])
    tf = open(t0_path, "w", encoding="utf-8-sig", newline="")
    wt = csv.writer(tf)
    wt.writerow(["ra_asset_id", "symbol", "type0_rows", "common", "flat_bars",
                 "close_last_cmp", "close_last_exact", "close_last_tol",
                 "close_closing_cmp", "close_closing_exact",
                 "open_cmp", "open_exact", "high_cmp", "high_exact",
                 "low_cmp", "low_exact", "volume_cmp", "volume_exact",
                 "row_exact", "row_tol", "status"])
    sf = open(sample_path, "w", encoding="utf-8-sig", newline="")
    ws = csv.writer(sf)
    ws.writerow(["ra_asset_id", "symbol", "date", "field", "ref", "prod", "abs_diff",
                 "rel_diff", "basis", "kind", "cause", "confidence", "note"])
    mf = open(missing_path, "w", encoding="utf-8-sig", newline="")
    wm = csv.writer(mf)
    wm.writerow(["ra_asset_id", "symbol", "date", "kind", "t_high", "t_low",
                 "t_close", "t_volume", "source"])
    n_samples = n_missing = 0
    tax = defaultdict(lambda: {"assets": set(), "dates": 0, "fields": 0,
                               "samples": [], "note": ""})
    cov = defaultdict(lambda: {"assets": set(), "dates": 0})
    totals = Counter()
    asset_rows = []
    n_assets = 0
    for line in open(os.path.join(CACHE, "cohort.jsonl"), encoding="utf-8"):
        if args.limit and n_assets >= args.limit:
            break
        n_assets += 1
        j = json.loads(line)
        aid = j["ra_asset_id"]; ins = j["ins_code"]; sym = j["symbol"]
        basis = j.get("basis") or "last"
        P = {r[0]: r for r in j["candles"]}
        T = {r[0]: r for r in con.execute(
            "SELECT date,first,high,low,close,volume,base,last FROM tsetmc WHERE ins_code=?",
            (ins,))}
        C = {r[0]: r for r in con.execute(
            "SELECT date,open,high,low,close,volume FROM type0 WHERE ra_asset_id=?",
            (aid,))}
        counts = Counter()
        absd = defaultdict(list)
        rels = defaultdict(list)
        samples = []
        row_exact = row_tol = row_disp = row_ohlcv = row_pairs = 0
        t0flat = 0
        t0_counts = Counter()
        common_c = 0
        p_dates = sorted(P); t_dates = sorted(T)
        tset = set(T); pset = set(P)
        tmin = t_dates[0] if t_dates else None
        tmax = t_dates[-1] if t_dates else None
        # coverage of product range
        for d in t_dates:
            if d in pset:
                continue
            if tmin and tmax and p_dates and p_dates[0] <= d <= p_dates[-1]:
                r = T[d]
                if (r[1] <= 0 or r[2] <= 0 or r[3] <= 0 or r[5] == 0):
                    counts["missing_p_no_trade"] += 1
                    kind = "NO_TRADE"
                else:
                    counts["missing_p_product"] += 1
                    kind = "PRODUCT_OMISSION"
                if n_missing < MISS_SAMPLE_CAP:
                    wm.writerow([aid, sym, d, kind, r[2], r[3], r[4], r[5], "TSETMC"])
                    n_missing += 1
                cov[kind]["assets"].add(aid); cov[kind]["dates"] += 1
        for d in p_dates:
            if d in tset:
                continue
            if tmin and tmax and d < tmin:
                counts["p_before_t"] += 1
                cov["PRODUCT_BEFORE_REFERENCE_RANGE"]["assets"].add(aid)
                cov["PRODUCT_BEFORE_REFERENCE_RANGE"]["dates"] += 1
            elif tmin and tmax and d > tmax:
                counts["p_after_t"] += 1
                cov["PRODUCT_AFTER_REFERENCE_RANGE"]["assets"].add(aid)
                cov["PRODUCT_AFTER_REFERENCE_RANGE"]["dates"] += 1
            else:
                counts["missing_r_ref"] += 1
                if n_missing < MISS_SAMPLE_CAP:
                    wm.writerow([aid, sym, d, "REFERENCE_OMISSION", "", "", "", "", "TSETMC"])
                    n_missing += 1
                cov["REFERENCE_OMISSION"]["assets"].add(aid)
                cov["REFERENCE_OMISSION"]["dates"] += 1
        for d in sorted(pset & tset):
            c = P[d]; r = T[d]
            if r[2] <= 0 or r[3] <= 0 or r[4] <= 0:
                counts["common_no_trade_t"] += 1
                continue
            t_first, t_base, t_close = r[1], r[6], r[4]
            t_last, t_vol, t_high, t_low = r[7], r[5], r[2], r[3]
            o_eff = _eff_open(t_first, t_base, t_high, t_low, t_close)
            hi_p, lo_p = _widen(o_eff, t_high, t_low, t_close)
            chosen = t_last if (basis == "last" and t_last > 0) else t_close
            hi_c, lo_c = max(hi_p, chosen), min(lo_p, chosen)
            p_disp = c[4]
            p_hi_raw = c[7] if c[7] is not None else c[2]
            p_lo_raw = c[8] if c[8] is not None else c[3]
            checks = {
                "open_first": (t_first if t_first > 0 else None, c[1]),
                "open_eff": (o_eff, c[1]),
                "high_parser": (hi_p, p_hi_raw),
                "low_parser": (lo_p, p_lo_raw),
                "high_contract": (hi_c, c[2]),
                "low_contract": (lo_c, c[3]),
                "high_literal": (t_high, c[2]),
                "low_literal": (t_low, c[3]),
                "close_official": (t_close, c[5]),
                "close_last": (t_last if t_last > 0 else None, c[6]),
                "close_display": (chosen, p_disp),
                "volume": (t_vol, c[9]),
            }
            row_ok = True; row_tol_ok = True; row_disp_ok = True; row_vol_ok = True
            for f, (ref, pv) in checks.items():
                st = _status(ref, pv)
                counts[(f, st.lower())] += 1
                if st != "NULL":
                    counts[(f, "cmp")] += 1
                    absd[f].append(abs(float(ref) - float(pv)))
                    rv = rel(float(pv), float(ref))
                    if rv is not None:
                        rels[f].append(rv)
                if st in ("EXACT", "TOL"):
                    counts[(f, "ok")] += 1
                if f in ("open_eff", "high_contract", "low_contract", "close_official"):
                    if st != "EXACT": row_ok = False
                    if st not in ("EXACT", "TOL"): row_tol_ok = False
                if f in ("open_eff", "high_contract", "low_contract", "close_display"):
                    if st not in ("EXACT", "TOL"):
                        row_disp_ok = False
                if f == "volume" and st not in ("EXACT", "TOL", "NULL"):
                    row_vol_ok = False
                if st not in ("EXACT", "TOL", "NULL") and len(samples) < args.samples_per_asset:
                    cause, conf, note = classify_diff(f, ref, pv, r, c, basis, C.get(d))
                    samples.append([d, f, ref, pv, abs(float(ref) - float(pv)),
                                    rel(float(pv), float(ref)), basis, "B",
                                    cause, conf, note])
                    k = cause
                    tax[k]["assets"].add(aid); tax[k]["dates"] += 1
                    tax[k]["fields"] += 1
                    if len(tax[k]["samples"]) < 6:
                        tax[k]["samples"].append([sym, d, f, ref, pv, note])
            row_pairs += 1
            if row_ok: row_exact += 1
            if row_tol_ok: row_tol += 1
            if row_vol_ok: row_ohlcv += 1
            if row_disp_ok: row_disp += 1
        # C: Rahavard type0
        for d in sorted(pset & set(C)):
            c = P[d]; r = C[d]
            o0, h0, l0, c0, v0 = r[1], r[2], r[3], r[4], r[5]
            flat = (o0 == h0 == l0 == c0)
            t0flat += 1 if flat else 0
            common_c += 1
            if flat and (c[2] > c[3] or c[1] != c[4]):
                t0_counts["flat_bar"] += 1
            cnt = {
                "open": (o0, c[1]), "high": (h0, c[2]), "low": (l0, c[3]),
                "close_last": (c0, c[6]), "close_closing": (c0, c[5]),
                "volume": (v0, c[9]),
            }
            for f, (ref, pv) in cnt.items():
                st = _status(ref, pv)
                t0_counts[(f, st.lower())] += 1
                if st != "NULL": t0_counts[(f, "cmp")] += 1
            if all(_status(ref, pv) == "EXACT" for f, (ref, pv) in
                   [(k, v) for k, v in cnt.items() if k != "volume"]):
                t0_counts["row_exact"] += 1
            if all(_status(ref, pv) in ("EXACT", "TOL") for f, (ref, pv) in
                   [(k, v) for k, v in cnt.items() if k != "volume"]):
                t0_counts["row_tol"] += 1
        b_cmp = sum(v for k, v in counts.items()
                    if isinstance(k, tuple) and len(k) == 2 and k[1] == "cmp")
        b_ok = sum(v for k, v in counts.items()
                   if isinstance(k, tuple) and len(k) == 2 and k[1] == "ok")
        contract_fields = ("open_eff", "high_contract", "low_contract",
                           "close_official", "close_last", "close_display", "volume")
        contract_cmp = sum(counts[(f, "cmp")] for f in contract_fields)
        contract_ok = sum(counts[(f, "ok")] for f in contract_fields)
        row_exact_pct = round(100.0 * row_exact / row_pairs, 4) if row_pairs else ""
        row_tol_pct = round(100.0 * row_tol / row_pairs, 4) if row_pairs else ""
        # "ok" includes exact+tol for each field; row_contract is the strict OHLC view
        wf.writerow([aid, sym, ins, basis, len(P), len(T),
                     len([d for d in t_dates if T[d][2] > 0 and T[d][3] > 0 and T[d][4] > 0]),
                     len(C), len(pset & tset), common_c, b_cmp, b_ok,
                     round(100.0 * b_ok / b_cmp, 4) if b_cmp else "",
                     contract_cmp, contract_ok,
                     round(100.0 * contract_ok / contract_cmp, 4) if contract_cmp else "",
                     sum(counts[(f, "diff")] for f in fields),
                     sum(counts[(f, "null")] for f in fields),
                     row_pairs, row_exact, row_tol, row_exact_pct, row_tol_pct,
                     row_disp, row_ohlcv,
                     counts["missing_p_no_trade"], counts["missing_p_product"],
                     counts["missing_r_ref"], counts["p_before_t"], counts["p_after_t"],
                     p_dates[0] if p_dates else "",
                     p_dates[-1] if p_dates else "", tmin or "", tmax or "", t0flat,
                     "ok" if contract_cmp and contract_ok / contract_cmp >= 0.999
                     else "attention"] +
                    [x for f in fields for x in
                     (counts[(f, "cmp")], counts[(f, "exact")], counts[(f, "tol")],
                      counts[(f, "diff")], counts[(f, "null")])] +
                    [x for f in fields for x in
                     (pctile(absd[f], 0.5), pctile(absd[f], 0.95),
                      max(absd[f]) if absd[f] else None)])
        for s in samples:
            ws.writerow([aid, sym] + s)
            n_samples += 1
        def c(x):
            return t0_counts[(x, "cmp")]
        def e(x):
            return t0_counts[(x, "exact")]
        wt.writerow([aid, sym, len(C), common_c, t0flat,
                     c("close_last"), e("close_last"),
                     t0_counts[("close_last", "tol")],
                     c("close_closing"), e("close_closing"),
                     c("open"), e("open"), c("high"), e("high"),
                     c("low"), e("low"), c("volume"), e("volume"),
                     t0_counts["row_exact"], t0_counts["row_tol"],
                     "ok" if common_c and t0_counts["row_tol"] / common_c >= 0.99 else "attention"])
        totals["assets"] += 1
        totals["b_cmp"] += b_cmp; totals["b_ok"] += b_ok
        totals["contract_cmp"] += contract_cmp; totals["contract_ok"] += contract_ok
        totals["row_pairs"] += row_pairs
        totals["row_exact"] += row_exact; totals["row_tol"] += row_tol
        totals["common_b"] += len(pset & tset); totals["common_c"] += common_c
        totals["missing_p_no_trade"] += counts["missing_p_no_trade"]
        totals["missing_p_product"] += counts["missing_p_product"]
        totals["missing_r_ref"] += counts["missing_r_ref"]
        totals["p_before_t"] += counts["p_before_t"]; totals["p_after_t"] += counts["p_after_t"]
        if totals["assets"] % 250 == 0:
            print(f"  measured {totals['assets']} assets", flush=True)
    pf.close(); tf.close(); sf.close(); mf.close()
    summary = {
        "assets": totals["assets"], "b_compared_fields": totals["b_cmp"],
        "b_ok_fields": totals["b_ok"],
        "b_ok_pct_all_fields": round(100.0 * totals["b_ok"] / max(1, totals["b_cmp"]), 4),
        "contract_compared": totals["contract_cmp"],
        "contract_ok": totals["contract_ok"],
        "contract_ok_pct": round(100.0 * totals["contract_ok"] / max(1, totals["contract_cmp"]), 4),
        "row_pairs": totals["row_pairs"],
        "row_contract_exact": totals["row_exact"], "row_contract_tol": totals["row_tol"],
        "row_contract_exact_pct": round(100.0 * totals["row_exact"] / max(1, totals["row_pairs"]), 4),
        "row_contract_tol_pct": round(100.0 * totals["row_tol"] / max(1, totals["row_pairs"]), 4),
        "common_b": totals["common_b"], "common_c": totals["common_c"],
        "missing_p_no_trade": totals["missing_p_no_trade"],
        "missing_p_product": totals["missing_p_product"],
        "missing_r_ref": totals["missing_r_ref"],
        "samples": n_samples, "missing_rows": n_missing,
    }
    with open(os.path.join(ART, "raw-ohlc-summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    with open(os.path.join(ART, "raw-ohlc-coverage.csv"), "w", encoding="utf-8-sig",
              newline="") as f:
        w = csv.writer(f)
        w.writerow(["category", "assets", "dates", "note"])
        for k in sorted(cov, key=lambda x: -cov[x]["dates"]):
            w.writerow([k, len(cov[k]["assets"]), cov[k]["dates"],
                        "coverage only; never counted as a numeric mismatch"])
    with open(os.path.join(ART, "raw-ohlc-taxonomy.csv"), "w", encoding="utf-8-sig",
              newline="") as f:
        w = csv.writer(f)
        w.writerow(["cause", "assets", "asset_date_fields", "share_pct", "samples", "note"])
        total = sum(v["fields"] for v in tax.values()) or 1
        for k in sorted(tax, key=lambda x: -tax[x]["fields"]):
            v = tax[k]
            w.writerow([k, len(v["assets"]), v["fields"],
                        round(100.0 * v["fields"] / total, 4),
                        json.dumps(v["samples"][:3], ensure_ascii=False), v["note"]])
    print(json.dumps(summary, ensure_ascii=False))


def classify_diff(field, ref, prod, t, c, basis, c0):
    """Best-effort single cause; evidence is kept in the note, never guessed."""
    try:
        ref = float(ref); prod = float(prod)
    except (TypeError, ValueError):
        return ("UNCLASSIFIED", "LOW", "non-numeric")
    d = abs(ref - prod); r = rel(prod, ref)
    if ref and any(abs(prod / ref - k) <= 0.001 for k in (10, 100, 1000, 0.1, 0.01, 0.001)):
        return ("PRICE_SCALE_OR_UNIT", "HIGH", f"ratio={prod/ref:.6f}")
    if r is not None and r <= PRICE_REL_ROUND:
        return ("PRECISION_OR_ROUNDING", "HIGH", f"rel={r:.6f}")
    if field == "open_first" and ref == 0:
        return ("PARSING_OR_TRANSFORM", "MEDIUM", "TSETMC FIRST is zero; product fallback")
    if field in ("high_literal", "low_literal", "high_parser", "low_parser"):
        hi, lo = _widen(_eff_open(t[1], t[6], t[2], t[3], t[4]), t[2], t[3], t[4])
        chosen = t[7] if (basis == "last" and t[7] > 0) else t[4]
        hi_f, lo_f = max(hi, chosen), min(lo, chosen)
        if field in ("high_literal", "high_parser") and prod in (hi, hi_f) and prod != ref:
            return ("PARSING_OR_TRANSFORM", "HIGH",
                    "widen()/basis raised high to contain body or displayed last")
        if field in ("low_literal", "low_parser") and prod in (lo, lo_f) and prod != ref:
            return ("PARSING_OR_TRANSFORM", "HIGH",
                    "widen()/basis lowered low to contain body or displayed last")
    if field == "close_display" and basis == "closing":
        return ("FIELD_MAPPING", "HIGH", "closing basis displayed against last")
    if c0 is not None:
        if field in ("close_official", "close_last", "close_display"):
            cval = c0[3]
        elif field in ("open_eff", "open_first"):
            cval = c0[0]
        elif "high" in field:
            cval = c0[1]
        elif "low" in field:
            cval = c0[2]
        elif field == "volume":
            cval = c0[4]
        else:
            cval = None
        try:
            cval = float(cval) if cval is not None else None
        except (TypeError, ValueError):
            cval = None
        if cval is not None and abs(cval - prod) <= max(PRICE_ABS, 1e-9 * abs(cval)):
            return ("SOURCE_DATA_DIVERGENCE", "HIGH",
                    f"product matches Rahavard type0 {cval}, TSETMC={ref}")
    if field in ("close_official", "close_last", "close_display") and c and c[6] is not None             and abs(float(c[6]) - ref) <= 1.0:
        return ("HISTORICAL_REVISION", "MEDIUM",
                f"product snapshot last={c[6]} matches neither side; current TSETMC={ref}")
    return ("UNCLASSIFIED", "LOW", f"abs={d:.4f} rel={r}")



def cmd_pipeline(args):
    """Parser-level check: production parser vs the literal CSV it just read.

    Same payload on both sides, so every difference is mapping/transform or a
    dropped/duplicated row - never a source revision or a snapshot age effect.
    """
    import importlib
    CH = importlib.import_module("api.chart")
    db = sqlite3.connect(f"file:{os.path.join(CACHE, 'reference.db')}?mode=ro", uri=True)
    out_path = os.path.join(ART, "pipeline-parser-parity.csv")
    f = open(out_path, "w", encoding="utf-8-sig", newline="")
    w = csv.writer(f)
    w.writerow(["ra_asset_id", "symbol", "ins_code", "t_rows", "t_tradable",
                 "candles", "no_trade_dropped", "first_zero_fallback",
                 "open_cmp", "open_exact", "high_cmp", "high_exact",
                 "low_cmp", "low_exact", "close_cmp", "close_exact",
                 "last_cmp", "last_exact", "volume_cmp", "volume_exact",
                 "row_cmp", "row_exact", "status"])
    cache = os.path.join(CACHE, "cache", "tsetmc_csv")
    totals = Counter()
    n_assets = 0
    for line in open(os.path.join(CACHE, "cohort.jsonl"), encoding="utf-8"):
        if args.limit and n_assets >= args.limit:
            break
        n_assets += 1
        j = json.loads(line); ins = j["ins_code"]; aid = j["ra_asset_id"]
        p = os.path.join(cache, ins + ".csv")
        if not os.path.exists(p):
            continue
        text = open(p, encoding="utf-8", errors="replace").read()
        candles, volumes, _ = CH._parse_tsetmc_csv(text)
        vols = {v["time"]: v["value"] for v in volumes}
        T = {r[0]: r for r in db.execute(
            "SELECT date,first,high,low,close,volume,base,last FROM tsetmc WHERE ins_code=?",
            (ins,))}
        counts = Counter(); no_trade = 0; first_zero = 0
        cdates = {c["time"] for c in candles}
        for d, r in T.items():
            if d not in cdates:
                if r[2] <= 0 or r[3] <= 0 or r[5] == 0:
                    no_trade += 1
        rp = 0; rex = 0
        for c in candles:
            d = c["time"]; r = T.get(d)
            if not r:
                continue
            o_eff = _eff_open(r[1], r[6], r[2], r[3], r[4])
            hi, lo = _widen(o_eff, r[2], r[3], r[4])
            if r[1] == 0:
                first_zero += 1
            checks = {"open": (o_eff, c["open"]), "high": (hi, c["high"]),
                      "low": (lo, c["low"]), "close": (r[4], c["close"]),
                      "last": (r[7] if r[7] > 0 else None, c.get("last")),
                      "volume": (r[5], vols.get(d))}
            ok = True
            for k, (ref, prod) in checks.items():
                st = _status(ref, prod)
                if st != "NULL":
                    counts[(k, "cmp")] += 1
                    if st == "EXACT":
                        counts[(k, "exact")] += 1
                    else:
                        ok = False
            rp += 1
            if ok:
                rex += 1
        w.writerow([aid, j["symbol"], ins, len(T),
                    sum(1 for r in T.values() if r[2] > 0 and r[3] > 0 and r[4] > 0),
                    len(candles), no_trade, first_zero] +
                   [x for k in ("open", "high", "low", "close", "last", "volume")
                    for x in (counts[(k, "cmp")], counts[(k, "exact")])] +
                   [rp, rex, "ok" if rp and rex == rp else "attention"])
        totals["assets"] += 1; totals["t_rows"] += len(T); totals["candles"] += len(candles)
        totals["no_trade_dropped"] += no_trade; totals["first_zero"] += first_zero
        totals["row_cmp"] += rp; totals["row_exact"] += rex
        for k in ("open", "high", "low", "close", "last", "volume"):
            totals[(k, "cmp")] += counts[(k, "cmp")]
            totals[(k, "exact")] += counts[(k, "exact")]
        if totals["assets"] % 250 == 0:
            print(f"  pipeline {totals['assets']} assets", flush=True)
    f.close(); db.close()
    summary = {"assets": totals["assets"], "tsetmc_rows": totals["t_rows"],
               "candles": totals["candles"],
               "no_trade_dropped": totals["no_trade_dropped"],
               "first_zero_fallback": totals["first_zero"],
               "row_compared": totals["row_cmp"], "row_exact": totals["row_exact"],
               "row_exact_pct": round(100.0 * totals["row_exact"] / max(1, totals["row_cmp"]), 6)}
    for k in ("open", "high", "low", "close", "last", "volume"):
        c = totals[(k, "cmp")]; e = totals[(k, "exact")]
        summary[k + "_cmp"] = c
        summary[k + "_exact_pct"] = round(100.0 * e / max(1, c), 6)
    with open(os.path.join(ART, "pipeline-parser-summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))


def cmd_layers(args):
    """Factor and adjusted-OHLC layer on the same cohort, for linkage only."""
    db = sqlite3.connect(f"file:{os.path.join(CACHE, 'reference.db')}?mode=ro", uri=True)
    rows = []
    for line in open(os.path.join(CACHE, "cohort.jsonl"), encoding="utf-8"):
        j = json.loads(line)
        aid = j["ra_asset_id"]
        C0 = {r[0]: r for r in db.execute(
            "SELECT date,open,high,low,close,volume FROM type0 WHERE ra_asset_id=?", (aid,))}
        C7 = {r[0]: r for r in db.execute(
            "SELECT date,open,high,low,close,volume FROM type7 WHERE ra_asset_id=?", (aid,))}
        F = {r[0]: r[1] for r in j.get("factors") or []}
        P = {r[0]: r for r in j["candles"]}
        common = sorted(set(P) & set(C0) & set(C7) & set(F))
        fc = fo = fn = 0
        ac = ao = 0
        al = []
        for d in common:
            p = P[d]; f = F.get(d); c0 = C0[d]; c7 = C7[d]
            if f is None or not c0[4]:
                continue
            rf = c7[4] / c0[4]
            fd = rel(f, rf)
            if fd is not None:
                fc += 1; al.append(fd)
                if fd <= 0.0005: fo += 1
                if fd <= 0.01: fn += 1
            for idx, fld in ((1, "open"), (2, "high"), (3, "low"), (4, "close")):
                a = p[idx] * f if p[idx] is not None else None
                b = c7[idx]
                if a is None or b is None: continue
                ac += 1
                if _status(b, a) in ("EXACT", "TOL"): ao += 1
        rows.append({"ra_asset_id": aid, "symbol": j["symbol"], "common": len(common),
                     "factor_cmp": fc, "factor_exact": fo, "factor_near": fn,
                     "adj_cmp": ac, "adj_ok": ao,
                     "factor_ok_pct": round(100.0 * fo / fc, 4) if fc else "",
                     "adj_ok_pct": round(100.0 * ao / ac, 4) if ac else ""})
    with open(os.path.join(ART, "layer-decomposition.csv"), "w", encoding="utf-8-sig",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    tot_fc = sum(r["factor_cmp"] for r in rows); tot_fo = sum(r["factor_exact"] for r in rows)
    tot_ac = sum(r["adj_cmp"] for r in rows); tot_ao = sum(r["adj_ok"] for r in rows)
    print(json.dumps({"assets": len(rows), "factor_cmp": tot_fc, "factor_exact": tot_fo,
                      "factor_exact_pct": round(100.0 * tot_fo / max(1, tot_fc), 4),
                      "adj_cmp": tot_ac, "adj_ok": tot_ao,
                      "adj_ok_pct": round(100.0 * tot_ao / max(1, tot_ac), 4)},
                     ensure_ascii=False))


def cmd_link(args):
    """Join raw parity to the Round 17 regression list (per metric, not per symbol)."""
    par = {}
    for r in csv.DictReader(open(os.path.join(ART, "raw-ohlc-parity.csv"), encoding="utf-8-sig")):
        par[r["symbol"]] = r
    out = []
    seen = set()
    for name in ("regression-status.csv", "regression-status-ohlc.csv"):
        path = os.path.join(ROOT, "docs", "audit", "ra365-round17", name)
        for r in csv.DictReader(open(path, encoding="utf-8-sig")):
            sym = r.get("symbol")
            metric = r.get("metric") or ""
            key = (sym, metric)
            if not sym or key in seen:
                continue
            seen.add(key)
            p = par.get(sym, {})
            out.append({
                "symbol": sym,
                "metric": metric,
                "r15": r.get("r15", ""),
                "r16": r.get("r16", ""),
                "r17": r.get("r17", ""),
                "delta_r17": r.get("delta_r17", ""),
                "r17_status": r.get("status", ""),
                "r17_note": r.get("note", ""),
                "raw_contract_ok_pct": p.get("contract_ok_pct", ""),
                "raw_row_exact_pct": p.get("row_contract_exact_pct", ""),
                "raw_row_pairs": p.get("row_pairs", ""),
                "raw_status": p.get("status", "NOT_MEASURED"),
                "missing_p_no_trade": p.get("missing_p_no_trade", ""),
                "missing_p_product": p.get("missing_p_product", ""),
                "raw_class": ("RAW_HEALTHY" if p.get("row_contract_tol_pct") not in ("", None)
                              and float(p.get("row_contract_tol_pct") or 0) >= 99.9
                              else "RAW_ATTENTION"),
            })
    if not out:
        print("no regression rows")
        return
    with open(os.path.join(ART, "regression-raw-link.csv"), "w", encoding="utf-8-sig",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader(); w.writerows(out)
    print(f"linked {len(out)} regression metric rows")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cohort"); c.set_defaults(func=cmd_cohort)
    f = sub.add_parser("fetch")
    f.add_argument("--workers", type=int, default=6)
    f.add_argument("--retries", type=int, default=3)
    f.add_argument("--timeout", type=float, default=20)
    f.add_argument("--limit", type=int, default=0)
    f.add_argument("--json", action="store_true")
    f.add_argument("--json-top", type=int, default=2000)
    f.set_defaults(func=cmd_fetch)
    v = sub.add_parser("fetch-variants")
    v.add_argument("--workers", type=int, default=6)
    v.add_argument("--retries", type=int, default=3)
    v.add_argument("--timeout", type=float, default=20)
    v.set_defaults(func=cmd_fetch_variants)
    r = sub.add_parser("reference")
    r.add_argument("--force", action="store_true")
    r.set_defaults(func=cmd_reference)
    m = sub.add_parser("measure")
    m.add_argument("--samples-per-asset", type=int, default=8)
    m.add_argument("--limit", type=int, default=0)
    m.set_defaults(func=cmd_measure)
    p = sub.add_parser("pipeline")
    p.add_argument("--limit", type=int, default=0)
    p.set_defaults(func=cmd_pipeline)
    l = sub.add_parser("layers"); l.set_defaults(func=cmd_layers)
    k = sub.add_parser("link"); k.set_defaults(func=cmd_link)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
