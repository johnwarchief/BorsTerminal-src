#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/stale_chunk_prune_v1069.py — پاک‌سازیِ chunkهایِ مرده، با درختِ ساختگی.

چرا: پچِ دلتا فایلِ هیچ حذف نمی‌کند و Vite هر build نامِ hash‌شده را عوض
می‌کند، پس هر آپدیتِ درجا چندصدِ chunkِ مرده درِ نصب می‌گذارد (شمارشِ واقعی روی
نصبیِ ۱٫۰٫۶۸: ۷۴۶ فایلِ js/css درِ assets در برابرِ ۲۷ فایلِ همان manifest).
رفعش در `bors_config.prune_stale_frontend_assets` است و این گارد همان را با
درختِ کوچکِ ساختگی می‌سنجد — بی‌نیازِ npm build، پس درِ CI هم واقعاً می‌دود.

سه چیز که قفل می‌شوند و بی‌آن‌ها آتش‌بزنند:
  ۱) chunkی که فقط `vendor/` (بیرونِ assets) آن را صدا می‌زند نباید پاک شود؛
  ۲)_closure_ باید ازِ chunkِ زنده به chunkِ زنده برود، نه فقط ازِ index.html؛
  ۳) اگرِ فهمیدنِ ارجاع‌ها شکست بخورد (closure کوچک) هیچ فایلِ نباید برود.

خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
اجرا:  python dev/stale_chunk_prune_v1069.py
"""
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bors_config  # noqa: E402

PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s   %s" % (label, extra))


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build_dist(root):
    """درختِ SPAِ ساختگی: ۳ chunkِ زنده (یکیِ غیرمستقیم) + ۳ مرده + vendor."""
    assets = os.path.join(root, "assets")
    write(os.path.join(root, "index.html"),
          '<script src="/assets/index-NEW.js"></script>'
          '<link href="/assets/index-NEW.css">')
    write(os.path.join(assets, "index-NEW.js"),
          'import("./Entry-AAA.js"); import("./Vendor-CCC.js");')
    write(os.path.join(assets, "Entry-AAA.js"), "console.log(1);")
    # فقط vendor آن را می‌خواهد، نه index.html و نه chunkِ زنده
    write(os.path.join(assets, "Vendor-CCC.js"), "console.log(3);")
    write(os.path.join(root, "vendor", "klinecharts.js"),
          'load("/assets/Vendor-CCC.js");')
    # سه مرده: نامشان درِ هیچ فایلِ زنده‌ای نیست
    write(os.path.join(assets, "Old-111.js"), "console.log('old');")
    write(os.path.join(assets, "Old-222.js"), "console.log('old');")
    write(os.path.join(assets, "index-OLD.css"), "/* old */")


def names(assets):
    return sorted(n for n in os.listdir(assets) if not n.startswith("."))


def main():
    tmp = tempfile.mkdtemp(prefix="bors_prune_guard_")
    try:
        root = os.path.join(tmp, "dist")
        build_dist(root)
        assets = os.path.join(root, "assets")
        before = names(assets)
        ck(len(before) == 6, "fixture has 3 live + 3 dead chunks", before)

        removed = bors_config.prune_stale_frontend_assets(root, "9.9.9", verbose=False)
        after = names(assets)
        ck(removed == 3, "the three unreferenced chunks are pruned", removed)
        ck("Old-111.js" not in after and "index-OLD.css" not in after,
           "dead files are actually gone", after)
        ck({"index-NEW.js", "Entry-AAA.js", "Vendor-CCC.js"} <= set(after),
           "the closure keeps index -> entry -> vendor-only chunk", after)

        ck(bors_config.prune_stale_frontend_assets(root, "9.9.9") == 0,
           "same version never re-scans (stamp)")
        ck(bors_config.prune_stale_frontend_assets(root, "9.9.10") == 0,
           "a new version re-runs it and finds nothing left")

        # نگهبانِ شکستِ فهمیدنِ ارجاع: index.html خالی ⇒ هیچ حذفی
        root2 = os.path.join(tmp, "dist2")
        build_dist(root2)
        write(os.path.join(root2, "index.html"), "<html></html>")
        write(os.path.join(root2, "vendor", "klinecharts.js"), "")
        before2 = names(os.path.join(root2, "assets"))
        removed2 = bors_config.prune_stale_frontend_assets(root2, "9.9.9")
        ck(removed2 == 0 and names(os.path.join(root2, "assets")) == before2,
           "an unreadable entry point prunes nothing at all", removed2)

        # مسیرِ نبودِ dist: بی‌صدا و بی‌خطا
        ck(bors_config.prune_stale_frontend_assets(os.path.join(tmp, "nope"), "1") == 0,
           "a missing dist is not an error")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("stale_chunk_prune_v1069: %d passed, %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
