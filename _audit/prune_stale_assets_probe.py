# -*- coding: utf-8 -*-
"""Prove prune_stale_frontend_assets() against two real trees.

Oracle 1 (negative control): a freshly built frontend/dist has no dead chunks,
so the prune must delete exactly nothing. If it deletes anything here the
import-closure walk is wrong and shipping it would brick the UI.

Oracle 2 (the rot it exists to fix): a copy of the patched-in-place install
tree. Everything the released file manifest names must survive, and everything
the manifest does not name must be gone.
"""
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bors_config  # noqa: E402

INSTALLED = r"C:\Users\PCMOD\AppData\Local\Programs\BorsTerminal Ultimate"
MANIFEST = os.path.join(ROOT, "_audit", "man68.json")

PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok    %s" % label)
    else:
        FAIL += 1
        print("  FAIL  %s   %s" % (label, extra))


def fresh_dist(tmp):
    src = os.path.join(ROOT, "frontend", "dist")
    if not os.path.isdir(src):
        return None
    dst = os.path.join(tmp, "fresh_dist")
    shutil.copytree(src, dst)
    return dst


def main():
    tmp = tempfile.mkdtemp(prefix="bors_prune_")
    try:
        # ── oracle 1: buildِ تازه ⇒ هیچ حذفی
        fresh = fresh_dist(tmp)
        if fresh:
            names = os.listdir(os.path.join(fresh, "assets"))
            removed = bors_config.prune_stale_frontend_assets(fresh, "1.0.68")
            ck(removed == 0, "a fresh vite build loses nothing to the prune",
               "removed=%d of %d" % (removed, len(names)))
            ck(sorted(os.listdir(os.path.join(fresh, "assets"))) == sorted(names),
               "the fresh tree is byte-for-byte the same file list")
        else:
            print("  SKIP  no frontend/dist in the repo (run npm run build)")

        # ── oracle 2: درختِ آلودهٔ نصبی
        live_dist = os.path.join(INSTALLED, "_internal", "frontend", "dist")
        if not os.path.isdir(live_dist):
            print("  SKIP  installed tree not found")
        else:
            copy = os.path.join(tmp, "installed_dist")
            shutil.copytree(live_dist, copy)
            before = set(os.listdir(os.path.join(copy, "assets")))
            doc = json.load(open(MANIFEST, encoding="utf-8-sig"))
            want_assets = sorted(os.path.basename(r) for r in doc["files"]
                                 if r.startswith("_internal/frontend/dist/assets/"))
            want_js_css = [a for a in want_assets if a.lower().endswith((".js", ".css"))]
            print("  info  installed assets=%d  manifest js/css=%d"
                  % (len(before), len(want_js_css)))

            removed = bors_config.prune_stale_frontend_assets(copy, "1.0.68")
            after = set(os.listdir(os.path.join(copy, "assets")))
            gone = before - after
            ck(removed == len(gone), "the reported count matches the files gone",
               (removed, len(gone)))
            missing = [a for a in want_js_css if a not in after]
            ck(not missing, "every asset the released manifest names survived",
               "%d missing: %s" % (len(missing), missing[:5]))
            dead_left = sorted(n for n in after if n not in set(want_assets)
                               and n != ".live_chunks_stamp")
            ck(not dead_left, "no unreferenced chunk is left behind",
               "%d left: %s" % (len(dead_left), dead_left[:5]))

            again = bors_config.prune_stale_frontend_assets(copy, "1.0.68")
            ck(again == 0, "second run in the same version is a no-op", again)
            again2 = bors_config.prune_stale_frontend_assets(copy, "1.0.69")
            ck(again2 == 0, "a new version re-runs the prune and finds nothing new",
               again2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("prune_stale_assets_probe: %d passed, %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
