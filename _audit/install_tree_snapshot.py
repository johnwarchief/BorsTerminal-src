# -*- coding: utf-8 -*-
"""Snapshot the installed app tree so a mixed (half-updated) bundle is provable.

usage: python _audit/install_tree_snapshot.py <out.json>
"""
import hashlib
import json
import os
import sys
import time

KEY = ["user.db", ".screener_cache.json", "Version.txt", "market.db",
       "apply_update.bat", "BorsTerminal_Update.zip", "market.db.baseline",
       "codal.db", "codal_db_status.json"]
HASHED = {"user.db", ".screener_cache.json", "Version.txt", "market.db.baseline"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "install_tree.json"
    root = os.path.abspath(os.path.dirname(sys.argv[0]) or ".")
    # the install dir is passed in env so this script can live in the repo
    root = os.environ.get("BORS_INSTALL_DIR", root)
    rows = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != "logs"]
        for f in fn:
            p = os.path.join(dp, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            row = {"rel": rel, "size": st.st_size,
                   "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))}
            if rel in HASHED:
                row["sha256"] = sha(p)
            rows.append(row)
    rows.sort(key=lambda r: r["rel"])
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"root": root, "count": len(rows), "files": rows}, fh,
                  ensure_ascii=False, indent=1)
    print("install_tree_snapshot: %d files under %s -> %s" % (len(rows), root, out))
    by = {r["rel"]: r for r in rows}
    for k in KEY:
        r = by.get(k)
        if r:
            print("  %-28s %10d  %s  %s" % (k, r["size"], r["mtime"], r.get("sha256", "")[:16]))
        else:
            print("  %-28s ABSENT" % k)


if __name__ == "__main__":
    main()
