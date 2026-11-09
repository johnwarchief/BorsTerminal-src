#!/usr/bin/env python3
"""Create the fast-boot seed (market.db.gz) from the canonical market.db.lzma.

Why this exists: the canonical seed is an XZ stream produced by Python. The Go
runtime can read it, but the pure-Go XZ decoder takes ~3 minutes for the real
280 MB database, which would block the first launch behind an invisible server
start. gzip is decoded by Go's stdlib in ~2 seconds and costs ~35 MB more in the
installer. The canonical artifact stays market.db.lzma; this file is derived.

Usage:
    python scripts/make_fast_seed.py market.db.lzma dist/market.db.gz
    python scripts/make_fast_seed.py --verify dist/market.db.gz

The output is written atomically. An unchanged input mtime/size skips the work.
"""
from __future__ import annotations

import argparse
import gzip
import lzma
import os
import sys
import tempfile

CHUNK = 1 << 20


def _mtime(path: str) -> float:
    return os.path.getmtime(path)


def build(src: str, dst: str, force: bool = False) -> int:
    if not os.path.isfile(src):
        print(f"[seed] source missing: {src}", file=sys.stderr)
        return 2
    if (not force and os.path.isfile(dst)
            and os.path.getsize(dst) > 0
            and _mtime(dst) >= _mtime(src)):
        print(f"[seed] up to date: {dst} ({os.path.getsize(dst)} B)")
        return 0

    os.makedirs(os.path.dirname(os.path.abspath(dst)) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".market-db-", suffix=".gz", dir=os.path.dirname(os.path.abspath(dst)))
    os.close(fd)
    try:
        with lzma.open(src, "rb") as fin, gzip.open(tmp, "wb", compresslevel=6) as fout:
            while True:
                block = fin.read(CHUNK)
                if not block:
                    break
                fout.write(block)
        os.replace(tmp, dst)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    print(f"[seed] {src} -> {dst} ({os.path.getsize(dst)} B)")
    return 0


def verify(path: str) -> int:
    """Prove the gzip really contains a healthy SQLite database."""
    import sqlite3
    if not os.path.isfile(path):
        print(f"[seed] missing: {path}", file=sys.stderr)
        return 2
    fd, tmp = tempfile.mkstemp(prefix=".seed-verify-", suffix=".db")
    os.close(fd)
    try:
        with gzip.open(path, "rb") as fin, open(tmp, "wb") as fout:
            while True:
                block = fin.read(CHUNK)
                if not block:
                    break
                fout.write(block)
        con = sqlite3.connect("file:" + tmp.replace("\\", "/") + "?mode=ro", uri=True)
        try:
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            rows, first, last = con.execute(
                "SELECT count(*), min(date), max(date) FROM price_history").fetchone()
        finally:
            con.close()
        if integrity != "ok" or not rows:
            print(f"[seed] invalid: integrity={integrity} rows={rows}", file=sys.stderr)
            return 1
        print(f"[seed] verified: rows={rows} first={first} last={last} integrity={integrity}")
        return 0
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--verify", metavar="GZ")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    if args.verify:
        return verify(args.verify)
    if not args.src or not args.dst:
        ap.error("src and dst are required unless --verify is used")
    return build(args.src, args.dst, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
