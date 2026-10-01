# -*- coding: utf-8 -*-
"""Verify an install tree against a released file manifest.

A delta patch only overlays the changed files, so an interrupted or locked
extraction leaves a MIXED bundle: some files at the new version, some at the
old one, and Version.txt still stamped new. This tool makes that visible:
every manifest entry is hashed from disk and classified.

usage:  BORS_INSTALL_DIR=<dir> python _audit/verify_installed_tree.py <manifest.json>
"""
import hashlib
import json
import os
import sys
import time

USER_STATE = ("market.db", "user.db", ".screener_cache.json", "adb_config.json",
              "codal_control.json", "codal_state.json", "market_sync.json",
              "sync_status.json", "sync_ondemand.json", "sync_summary.json",
              "fts_update_state.json", "market.db.baseline", "market.db.lzma",
              "codal.db", "BorsTerminal_Update.zip")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    manifest_path = sys.argv[1]
    root = os.environ.get("BORS_INSTALL_DIR", os.getcwd())
    with open(manifest_path, encoding="utf-8-sig") as fh:
        doc = json.load(fh)
    files = doc.get("files") or {}
    print("verify_installed_tree: manifest version=%s files=%d" % (doc.get("version"), len(files)))
    print("                       install root=%s" % root)

    mismatch, missing = [], []
    for rel, want in sorted(files.items()):
        p = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            missing.append(rel)
            continue
        got = sha256(p)
        if got != want:
            mismatch.append((rel, want, got))

    have = set(files)
    on_disk = set()
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != "logs"]
        for f in fn:
            on_disk.add(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/"))
    extra = sorted(on_disk - have)
    extra_real = [r for r in extra if os.path.basename(r) not in USER_STATE
                  and not r.endswith((".db", ".db-wal", ".db-shm", ".log"))]

    print("  exact matches : %d" % (len(files) - len(mismatch) - len(missing)))
    print("  MISMATCH      : %d" % len(mismatch))
    for rel, want, got in mismatch[:20]:
        print("     %s  want=%s got=%s" % (rel, want[:12], got[:12]))
    print("  MISSING       : %d" % len(missing))
    for rel in missing[:20]:
        print("     %s" % rel)
    print("  on-disk files not in manifest: %d (user-state excluded: %d)"
          % (len(extra), len(extra) - len(extra_real)))
    for rel in extra_real[:40]:
        print("     %s" % rel)

    vp = os.path.join(root, "Version.txt")
    if os.path.isfile(vp):
        print("  Version.txt: " + open(vp, encoding="utf-8", errors="replace").read().replace("\n", " | "))

    ok = not mismatch and not missing
    print("verify_installed_tree: %s" % ("TREE CLEAN" if ok else "TREE MIXED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
