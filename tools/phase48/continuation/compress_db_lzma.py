#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compress one SQLite database with LZMA/XZ and prove the round trip.

The source database is opened read-only and never modified. The compressed
file is written to a temporary sibling first and atomically renamed, so an
interrupted run cannot leave a half-written archive under the final name.

The report records raw/compressed size and sha256, and the decompressed
sha256 is compared with the raw hash before the tool exits 0.
"""
import argparse
import hashlib
import json
import lzma
import os
import sys
import time


def _read_blocks(fh, block=1 << 22):
    for chunk in iter(lambda: fh.read(block), b""):
        yield chunk


def compress_db(raw_path, out_path, preset=9, force=False):
    raw_path = os.path.abspath(raw_path)
    out_path = os.path.abspath(out_path)
    if not os.path.isfile(raw_path):
        raise SystemExit("raw database missing: " + raw_path)
    if os.path.exists(out_path) and not force:
        raise SystemExit("refusing to overwrite existing archive: " + out_path +
                         " (pass --force to replace it)")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    raw_sha = hashlib.sha256()
    comp_sha = hashlib.sha256()
    raw_size = 0
    comp_size = 0
    started = time.time()
    comp = lzma.LZMACompressor(format=lzma.FORMAT_XZ, preset=preset)
    with open(raw_path, "rb") as fin, open(tmp, "wb") as fout:
        for block in _read_blocks(fin):
            raw_sha.update(block)
            raw_size += len(block)
            packed = comp.compress(block)
            fout.write(packed)
            comp_sha.update(packed)
            comp_size += len(packed)
        packed = comp.flush()
        fout.write(packed)
        comp_sha.update(packed)
        comp_size += len(packed)
    os.replace(tmp, out_path)

    dec_sha = hashlib.sha256()
    dec_size = 0
    with lzma.open(out_path, "rb") as fin:
        for block in _read_blocks(fin):
            dec_sha.update(block)
            dec_size += len(block)
    ok = dec_sha.hexdigest() == raw_sha.hexdigest() and dec_size == raw_size
    report = {
        "raw": raw_path,
        "raw_size": raw_size,
        "raw_sha256": raw_sha.hexdigest(),
        "archived": out_path,
        "archived_size": comp_size,
        "archived_sha256": comp_sha.hexdigest(),
        "format": "xz",
        "preset": preset,
        "decompressed_size": dec_size,
        "decompressed_sha256": dec_sha.hexdigest(),
        "roundtrip_ok": ok,
        "seconds": round(time.time() - started, 1),
    }
    if not ok:
        raise SystemExit("round-trip mismatch: " + json.dumps(report, ensure_ascii=False))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="LZMA-compress a database without touching it")
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preset", type=int, default=9)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    report = compress_db(args.raw, args.out, preset=args.preset, force=args.force)
    print(json.dumps(report, ensure_ascii=False, indent=1 if args.json else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
