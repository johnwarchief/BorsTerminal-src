#!/usr/bin/env python3
"""Stage 00 - baseline snapshot for the Phase 4.9.1 verification ledgers.

Records what the ledgers are built *from*: the git HEAD, the pack manifest
counts and file SHA-256s, the Seed DB SHA-256/size/row counts, the capture
file SHA-256s (when a capture directory is given) and the tool versions.

The Seed DB is always opened read-only (``mode=ro``); nothing here writes to
the seed or to the pack. Stdlib only. The baseline JSON is deterministic:
UTF-8, LF, ``indent=1``, one trailing newline, repo-relative POSIX paths -
so the same tree produces the same bytes.

CLI:
    python _audit/phase49-full-verification/stage00_baseline.py \\
        --db _audit/phase49-finalization/seed/market.db \\
        --pack data/ra365_corrections/ra365-phase49-rebuild-full-v2 \\
        [--captures _audit/phase49-full-verification/captures] \\
        --out _audit/phase49-full-verification/evidence/baseline.json
"""
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEV = os.path.join(ROOT, "dev")
if DEV not in sys.path:
    sys.path.insert(0, DEV)

import phase49_manifest as PM  # noqa: E402

CHUNK = 1 << 22
# ``head`` records the checkout the snapshot ran on, not the commit that later
# carries this file (the snapshot is committed afterwards, so HEAD moves).
HEAD_NOTE = ("head is the git HEAD at snapshot time, not the commit that "
             "contains this baseline (the file is committed afterwards)")
DEFAULT_MANIFEST = os.path.join(HERE, "evidence", "stage00_baseline.manifest.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _abs(path):
    """Resolve a repo-relative path against ROOT; leave absolute paths alone."""
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def _rel(path):
    """Repo-relative POSIX path (portable in evidence; no machine paths)."""
    try:
        rel = os.path.relpath(_abs(path), ROOT)
    except ValueError:  # different drive on Windows
        rel = _abs(path)
    return rel.replace("\\", "/")


def git_head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip()


def _git_version():
    try:
        return subprocess.check_output(["git", "--version"], cwd=ROOT,
                                       text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _db_uri(path):
    """Read-only SQLite URI; the Seed DB is never opened writable."""
    return "file:%s?mode=ro" % quote(_abs(path).replace("\\", "/"), safe="/:")


def capture_shas(captures):
    """SHA-256 of every file under a capture directory, keyed by POSIX relpath."""
    if not captures:
        return {}
    base = _abs(captures)
    if not os.path.isdir(base):
        raise FileNotFoundError("capture directory not found: %s" % base)
    out = {}
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            out[os.path.relpath(full, base).replace(os.sep, "/")] = sha256(full)
    return out


def snapshot(pack, db, captures=None):
    pack = _abs(pack)
    db = _abs(db)
    manifest_path = os.path.join(pack, "manifest.json")
    factors_path = os.path.join(pack, "factors.jsonl")
    raw_path = os.path.join(pack, "raw_ohlc.jsonl")
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)

    con = sqlite3.connect(_db_uri(db), uri=True)
    try:
        rows = con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        syms = con.execute(
            "SELECT COUNT(DISTINCT symbol) FROM price_history").fetchone()[0]
        validity = dict(con.execute(
            "SELECT status,COUNT(*) FROM history_validity GROUP BY status"))
    finally:
        con.close()

    capture_files = capture_shas(captures)
    return {
        "head": git_head(),
        "head_note": HEAD_NOTE,
        "pack": {"path": _rel(pack),
                 "version": manifest.get("version"),
                 "counts": manifest.get("counts"),
                 "factors_sha256": sha256(factors_path),
                 "raw_ohlc_sha256": sha256(raw_path),
                 "manifest_sha256": sha256(manifest_path),
                 "declared_sha256": {
                     "factors": manifest.get("factors_sha256"),
                     "raw_ohlc": manifest.get("raw_ohlc_sha256")}},
        "db": {"path": _rel(db), "sha256": sha256(db),
               "size": os.path.getsize(db),
               "price_history_rows": rows, "symbols_with_history": syms,
               "validity": validity},
        "captures": {"dir": _rel(captures) if captures else None,
                     "count": len(capture_files),
                     "files": capture_files},
        "python": sys.version,
        "tools": {"git": _git_version(), "sqlite": sqlite3.sqlite_version},
    }


def write_report(rep, out):
    parent = os.path.dirname(os.path.abspath(out))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    return out


def write_manifest(rep, args):
    """Stage manifest (see dev/phase49_manifest.py) - inputs, outputs, counts."""
    counts = {
        "pack_steps": (rep["pack"]["counts"] or {}).get("steps"),
        "pack_symbols": (rep["pack"]["counts"] or {}).get("symbols"),
        "db_price_history_rows": rep["db"]["price_history_rows"],
        "symbols_with_history": rep["db"]["symbols_with_history"],
        "capture_files": rep["captures"]["count"],
    }
    inputs = [_rel(args.db),
              _rel(os.path.join(args.pack, "manifest.json")),
              _rel(os.path.join(args.pack, "factors.jsonl")),
              _rel(os.path.join(args.pack, "raw_ohlc.jsonl"))]
    return PM.write_manifest("stage00_baseline", inputs, [_rel(args.out)],
                             counts, args.manifest)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="Seed market.db (opened read-only)")
    ap.add_argument("--pack", required=True, help="correction pack directory")
    ap.add_argument("--captures", default=None,
                    help="capture directory to hash (optional; empty baseline)")
    ap.add_argument("--out", required=True, help="baseline JSON to write")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST,
                    help="stage manifest path ('' disables)")
    a = ap.parse_args(argv)

    # Every CLI path is repo-relative; the manifest hashes repo-relative keys.
    os.chdir(ROOT)
    try:
        rep = snapshot(a.pack, a.db, a.captures)
    except (OSError, sqlite3.Error) as exc:
        print("BASELINE FAIL: %s" % exc, file=sys.stderr)
        return 2
    write_report(rep, a.out)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    if a.manifest:
        write_manifest(rep, a)
        print("BASELINE MANIFEST: %s" % _rel(a.manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
