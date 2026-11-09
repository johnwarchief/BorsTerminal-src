#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check the Phase 4.8 continuation artifacts against manifest.json.

Committed entries must exist and match their recorded size/sha256; a mismatch
is an error. Local-only entries (large DBs, licensed reference pack, test
binaries) are expected to be missing on a fresh clone, so a missing local
entry is reported but does not fail unless --strict is given.
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def check(manifest_path, quick=False):
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    rows = []
    failed = 0
    for entry in manifest.get("entries", []):
        rel = entry["path"]
        path = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
        exists = os.path.isfile(path)
        status = "ok"
        size = None
        digest = None
        if not exists:
            status = "missing"
        else:
            size = os.path.getsize(path)
            if entry.get("size") is not None and size != entry["size"]:
                status = "size-mismatch"
            if not quick and entry.get("sha256"):
                digest = sha256_file(path)
                if digest != entry["sha256"]:
                    status = "sha-mismatch"
        committed = entry.get("git") == "committed"
        if status != "ok" and (committed or status != "missing"):
            failed += 1
        rows.append({
            "path": rel,
            "role": entry.get("role", ""),
            "git": entry.get("git", ""),
            "status": status,
            "size": size,
            "sha256": digest or entry.get("sha256"),
        })
    return {"manifest": manifest_path, "ok": failed == 0, "failed": failed,
            "entries": rows}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Phase 4.8 continuation artifact check")
    ap.add_argument("--manifest", default=os.path.join(HERE, "manifest.json"))
    ap.add_argument("--quick", action="store_true", help="skip sha256 for existing files")
    ap.add_argument("--strict", action="store_true", help="missing local-only entries also fail")
    ap.add_argument("--json", action="store_true", help="print the full JSON report")
    args = ap.parse_args(argv)
    report = check(args.manifest, quick=args.quick)
    if args.strict:
        missing_local = [r for r in report["entries"]
                         if r["status"] == "missing" and r["git"] != "committed"]
        if missing_local:
            report["ok"] = False
            report["failed"] += len(missing_local)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        for row in report["entries"]:
            mark = "OK " if row["status"] == "ok" else "!! "
            print("%s%-8s %-12s %s" % (mark, row["status"], row["git"], row["path"]))
        print("---")
        print("ok" if report["ok"] else "FAILED (%d)" % report["failed"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
