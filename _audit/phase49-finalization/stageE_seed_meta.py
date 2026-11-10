#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage E: add seed metadata (pack state, per-symbol validity, manifest),
vacuum, and compress the Seed candidate with a round-trip proof.
"""
import collections
import gzip
import hashlib
import json
import lzma
import os
import sqlite3
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEED = os.path.join(ROOT, "_audit", "phase49-finalization", "seed", "market.db")
PACK = os.path.join(ROOT, "_audit", "phase49-finalization", "packs", "rebuild-full-v2")
EVID = os.path.join(ROOT, "_audit", "phase49-finalization", "evidence")
NORM30 = os.path.join(ROOT, "_audit", "phase49-finalization", "rahavard", "normalized30")
NORM7 = os.path.join(ROOT, "_audit", "phase49-finalization", "rahavard", "normalized7")
OUT_LZMA = SEED + ".lzma"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def load_ref(symbols):
    out = collections.defaultdict(dict)
    for d in (NORM30, NORM7):
        with gzip.open(os.path.join(d, "bars.ndjson.gz"), "rt", encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if str(r.get("resolution")) == "D" and str(r.get("type")) in ("type0", "raw"):
                    if r["symbol"] in symbols:
                        out[r["symbol"]][str(r["date"])] = r
    return out


def main():
    manifest = json.load(open(os.path.join(PACK, "manifest.json"), encoding="utf-8"))
    parity = {}
    for label in ("30-final", "7-final"):
        p = json.load(open(os.path.join(EVID, "reference-parity-%s.json" % label),
                           encoding="utf-8"))["per_symbol"]
        parity.update(p)
    captured = set(parity)
    ref = load_ref(captured)
    con = sqlite3.connect(SEED)
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("DROP TABLE IF EXISTS adjust_pack_state")
    con.execute("DROP TABLE IF EXISTS history_validity")
    con.execute("DROP TABLE IF EXISTS seed_manifest")
    con.execute("""CREATE TABLE adjust_pack_state(
        version TEXT PRIMARY KEY, mode TEXT, as_of TEXT, factors_sha256 TEXT,
        raw_ohlc_sha256 TEXT, reference_sha256 TEXT, applied_at TEXT,
        steps INTEGER, symbols INTEGER, verified_steps INTEGER,
        reconstructed_verified_steps INTEGER, unverified_steps INTEGER,
        invalid_dropped_steps INTEGER)""")
    con.execute("""CREATE TABLE history_validity(
        symbol TEXT PRIMARY KEY, rows INTEGER, first_date TEXT, last_date TEXT,
        reference_coverage TEXT, ref_days INTEGER, ref_first TEXT, ref_last TEXT,
        factor_steps INTEGER, factor_verified INTEGER,
        factor_reconstructed INTEGER, factor_unverified INTEGER,
        raw_open_verified INTEGER, raw_open_corrected INTEGER,
        factor_parity TEXT, adjusted_max_abs REAL, status TEXT, notes TEXT)""")
    c = manifest["counts"]
    con.execute("""INSERT INTO adjust_pack_state VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (manifest["version"], manifest["mode"], manifest.get("as_of", ""),
                 manifest.get("file_sha256", {}).get("factors", ""),
                 manifest.get("file_sha256", {}).get("raw_ohlc", ""),
                 manifest.get("reference_sha256", ""),
                 time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 c["steps"], c["symbols"], c["verified_steps"],
                 c["reconstructed_verified_steps"], c["unverified_steps"],
                 c["invalid_dropped_steps"]))
    ph = con.execute(
        "SELECT symbol, COUNT(*), MIN(date), MAX(date) FROM price_history GROUP BY symbol"
    ).fetchall()
    corr = dict(con.execute(
        "SELECT symbol, COUNT(*) FROM raw_history_corrections GROUP BY symbol"))
    per = manifest.get("per_symbol", {})
    status_counts = collections.Counter()
    for sym, n, first, last in ph:
        rec = parity.get(sym)
        p = per.get(sym) or {}
        if rec:
            ref_days = rec["ref_days"]
            ref_first, ref_last = rec["ref_first"], rec["ref_last"]
            dbc = {r[0] for r in con.execute(
                "SELECT date FROM price_history WHERE symbol=?", (sym,))}
            matched = 0
            for d, rr in (ref.get(sym) or {}).items():
                if d not in dbc:
                    continue
                row = con.execute(
                    "SELECT open FROM price_history WHERE symbol=? AND date=?",
                    (sym, d)).fetchone()
                if row and row[0] is not None and rr.get("open") is not None and \
                        abs(float(row[0]) - float(rr["open"])) <= 1.0:
                    matched += 1
            status = ("verified" if rec["verdict"].startswith("PASS")
                      else "reconstructed_verified")
            notes = ("reference 2010-2026 capture; factor verdict %s" % rec["verdict"])
        else:
            ref_days = ref_first = ref_last = None
            matched = None
            if p:
                status = "reconstructed_verified"
                notes = "pack step derived from reference; no independent 2026-11-10 capture"
            else:
                status = "unverified"
                notes = "no independent reference evidence for this symbol"
        status_counts[status] += 1
        con.execute("""INSERT INTO history_validity VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (sym, n, first, last,
                     "rahavard-type0-type7-2026-11-10" if rec else "none",
                     ref_days, ref_first, ref_last,
                     p.get("steps", 0), p.get("verified", 0),
                     p.get("reconstructed_verified", 0), p.get("unverified", 0),
                     matched, corr.get(sym, 0),
                     rec["verdict"] if rec else None,
                     (rec["adjusted"]["product"]["close"]["max_abs"] if rec else None),
                     status, notes))
    con.execute("""CREATE TABLE seed_manifest(
        key TEXT PRIMARY KEY, value TEXT)""")
    rows = {
        "schema": "phase49-seed-candidate-v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pack_version": manifest["version"],
        "pack_reference_sha256": manifest.get("reference_sha256", ""),
        "price_history_rows": sum(r[1] for r in ph),
        "symbols_with_history": len(ph),
        "open_corrections": sum(corr.values()),
        "open_corrections_symbols": len(corr),
        "validity_status_counts": json.dumps(dict(status_counts), ensure_ascii=False),
        "provenance": "phase48 backfill (rahavard365) + phase49 reference-verified rebuild",
    }
    for k, v in rows.items():
        con.execute("INSERT INTO seed_manifest VALUES (?,?)", (k, str(v)))
    con.commit()
    integrity = [r[0] for r in con.execute("PRAGMA integrity_check")]
    con.execute("VACUUM")
    con.commit()
    con.close()
    raw_sha = sha256(SEED)
    if os.path.exists(OUT_LZMA):
        os.remove(OUT_LZMA)
    with open(SEED, "rb") as src, lzma.open(OUT_LZMA, "wb",
                                           format=lzma.FORMAT_XZ,
                                           preset=9 | lzma.PRESET_EXTREME) as dst:
        for chunk in iter(lambda: src.read(1 << 22), b""):
            dst.write(chunk)
    # round-trip proof
    h = hashlib.sha256()
    with lzma.open(OUT_LZMA, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    report = {"seed_db": os.path.relpath(SEED, ROOT).replace("\\", "/"),
              "seed_db_sha256": raw_sha, "seed_db_size": os.path.getsize(SEED),
              "seed_lzma": os.path.relpath(OUT_LZMA, ROOT).replace("\\", "/"),
              "seed_lzma_sha256": sha256(OUT_LZMA),
              "seed_lzma_size": os.path.getsize(OUT_LZMA),
              "roundtrip_sha256": h.hexdigest(),
              "roundtrip_ok": h.hexdigest() == raw_sha,
              "integrity": integrity,
              "price_history_rows": rows["price_history_rows"],
              "symbols": rows["symbols_with_history"],
              "validity_status_counts": dict(status_counts),
              "open_corrections": rows["open_corrections"]}
    with open(os.path.join(ROOT, "_audit", "phase49-finalization",
                           "seed-build-report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
