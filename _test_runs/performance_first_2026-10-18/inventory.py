# -*- coding: utf-8 -*-
"""موجودیِ پوشۀ شواهد: چه چیزی برایِ کامیت کوچک و معنادار است و چه چیزی باید محلی بماند."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LIMIT = 300 * 1024
# پوشه‌هایِ حجیمِ بازتولیدشدنی (تریس مرورگر، کپیِ بانک، اسکرین‌شات) — محلی می‌مانند و درِ گزارش
# مسیرِ و روشِ بازتولیدشان نوشته می‌شود. کپی‌هایِ کوچکِ سورس (a1-backup، f1-backup، *-after-src)
# نگه داشته می‌شوند، چون ریگ‌ها هشِ همین فایل‌ها را ملاکِ جابه‌جایی می‌گیرند.
BULK = {"p0v2-backup", "p0-backup", "b3-dryrun-rehearsal", "b3-dryrun-rehearsal-2",
        "b3-dryrun-rehearsal-3", "a2b", "f1-live", "f1-design", "__pycache__"}

keep, bulk, oversize = [], [], []
for root, dirs, files in os.walk(HERE):
    rel = os.path.relpath(root, HERE).replace("\\", "/")
    top = rel.split("/")[0] if rel != "." else ""
    if top in BULK:
        bulk.append(top)
        dirs[:] = []
        continue
    for f in files:
        p = os.path.join(root, f)
        s = os.path.getsize(p)
        r = (rel + "/" if rel != "." else "") + f
        if s > LIMIT or f.endswith(".pyc") or "market.db" in f:
            oversize.append((s, r))
        else:
            keep.append((s, r))

print("keep:", len(keep), "files,", round(sum(s for s, _ in keep) / 1024.0, 1), "KB")
print("bulk dirs skipped:", sorted(set(bulk)))
print("oversized/binary inside kept dirs:", len(oversize))
for s, r in sorted(oversize, reverse=True)[:10]:
    print("   ", round(s / 1024.0, 1), "KB", r)
by_ext = {}
for s, r in keep:
    e = os.path.splitext(r)[1] or "(noext)"
    by_ext.setdefault(e, [0, 0])
    by_ext[e][0] += 1
    by_ext[e][1] += s
for e, (n, b) in sorted(by_ext.items(), key=lambda kv: -kv[1][1]):
    print("  %-8s %3d فایل  %8.1f KB" % (e, n, b / 1024.0))
