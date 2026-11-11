#!/usr/bin/env python3
"""Re-verify the Phase 4.9.1 Seed Candidate after the owner approval.

Read-only over the Seed artifacts. Checks:
  * FINAL-SEED-MANIFEST.json exists, parses, and matches the DB seed_manifest
    on the counts and reference hashes that matter for release;
  * marketed SHA-256 for market.db, market.db.lzma and market.db.gz match the
    files on disk, and both compressed streams decompress to the DB hash;
  * PRAGMA integrity_check, duplicate (symbol,date) pairs, and the core table
    counts;
  * the recorded owner approval matches the DB manifest (count + hashes).

Product/API tests are run separately (stageE) because they start borsd against
an isolated copy; this script never writes to the Seed.
"""
import hashlib
import json
import lzma
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEED = os.path.join(ROOT, "_audit", "phase49-full-verification", "seed")
DB = os.path.join(SEED, "market.db")
LZMA = DB + ".lzma"
GZ = DB + ".gz"
MANIFEST = os.path.join(SEED, "FINAL-SEED-MANIFEST.json")
APPROVAL = os.path.join(ROOT, "docs", "opportunity-center", "phase49-2",
                        "OWNER-APPROVAL-REFERENCE-DERIVED.json")
OUT = os.path.join(ROOT, "_audit", "phase49-2", "evidence", "seed-recheck.json")


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha_stream(fh):
    h = hashlib.sha256()
    for block in iter(lambda: fh.read(1 << 20), b""):
        h.update(block)
    return h.hexdigest()


def main():
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    approval = json.load(open(APPROVAL, encoding="utf-8"))
    con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    db_manifest = {k: v for k, v in con.execute("SELECT key,value FROM seed_manifest")}
    counts = {}
    for table in ("price_history", "history_validity", "instruments",
                  "instrument_state", "daily_prices", "adjust_events"):
        counts[table] = con.execute('SELECT COUNT(*) FROM "%s"' % table).fetchone()[0]
    integrity = [r[0] for r in con.execute("PRAGMA integrity_check")]
    duplicates = con.execute(
        "SELECT COUNT(*) FROM (SELECT symbol,date FROM price_history "
        "GROUP BY symbol,date HAVING COUNT(*)>1)").fetchone()[0]
    ref_rows = con.execute(
        "SELECT COUNT(*) FROM price_history WHERE src='rahavard365'").fetchone()[0]
    symbols = con.execute("SELECT COUNT(DISTINCT symbol) FROM price_history").fetchone()[0]
    con.close()

    db_sha = sha_file(DB)
    lz_sha = sha_file(LZMA)
    gz_sha = sha_file(GZ)
    with lzma.open(LZMA, "rb") as fh:
        lz_round = sha_stream(fh)
    import gzip
    with gzip.open(GZ, "rb") as fh:
        gz_round = sha_stream(fh)

    checks = {
        "db_sha_matches_manifest": db_sha == manifest["seed_db"]["sha256"],
        "lzma_sha_matches_manifest": lz_sha == manifest["seed_lzma"]["sha256"],
        "gzip_sha_matches_manifest": gz_sha == manifest["seed_gzip"]["sha256"],
        "lzma_roundtrip_matches_db": lz_round == db_sha,
        "gzip_roundtrip_matches_db": gz_round == db_sha,
        "db_size_matches_manifest": os.path.getsize(DB) == manifest["seed_db"]["size"],
        "integrity_ok": integrity == ["ok"],
        "duplicates_zero": duplicates == 0,
        "reference_rows_manifest_match":
            ref_rows == manifest["counts"]["reference_derived_rows"]
            == int(db_manifest["reference_derived_rows"]),
        "symbols_manifest_match":
            symbols == manifest["counts"]["symbols_with_history"]
            == int(db_manifest["symbols_with_history"]),
        "db_capture_sha_matches_approval":
            db_manifest.get("reference_capture_sha256")
            == approval["reference_capture_sha256"]
            == manifest["inputs"]["reference_summary"]["capture_sha256"],
        "db_index_sha_matches_approval":
            db_manifest.get("reference_index_sha256")
            == approval["reference_index_sha256"]
            == manifest["inputs"]["reference_summary"]["reference_index_sha256"],
        "approval_covers_db_sha": approval["seed_db_sha256"] == db_sha,
        "approval_count_matches": approval["expected_reference_derived_rows"] == ref_rows,
    }
    out = {
        "schema": "phase49-2-seed-recheck-v1",
        "seed": {
            "db": os.path.relpath(DB, ROOT).replace("\\", "/"),
            "db_sha256": db_sha,
            "db_size": os.path.getsize(DB),
            "lzma_sha256": lz_sha,
            "gzip_sha256": gz_sha,
            "lzma_roundtrip_sha256": lz_round,
            "gzip_roundtrip_sha256": gz_round,
        },
        "counts": counts,
        "reference_derived_rows": ref_rows,
        "symbols_with_history": symbols,
        "duplicate_pairs": duplicates,
        "integrity_check": integrity,
        "owner_approval": approval["approval_record"] if "approval_record" in approval
        else os.path.relpath(APPROVAL, ROOT).replace("\\", "/"),
        "checks": checks,
        "ok": all(checks.values()),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(json.dumps({"ok": out["ok"], "counts": counts,
                      "reference_derived_rows": ref_rows,
                      "symbols_with_history": symbols,
                      "checks": checks}, ensure_ascii=False, indent=1))
    print("wrote", OUT)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
