"""list_patch.py — محتوای پچِ دلتا را فهرست می‌کند (ابزارِ تحلیلِ موقت)

اجرا:  python dev/list_patch.py [patch.zip]
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
default = os.path.join(ROOT, "dist", "BorsTerminal_Patch_1.0.9_to_1.0.10.zip")
path = sys.argv[1] if len(sys.argv) > 1 else default
if not os.path.isfile(path):
    print("missing:", path); sys.exit(1)

total = 0
rows = []
with zipfile.ZipFile(path) as zf:
    for i in zf.infolist():
        total += i.compress_size
        rows.append((i.compress_size, i.file_size, i.filename))

rows.sort(reverse=True)
print("== patch contents (%d entries, %.1f MB compressed)" % (len(rows), total / 1048576))
for c, u, name in rows[:25]:
    print("  %8.1f MB  %s" % (c / 1048576, name))
print("  ---")
for c, u, name in rows[25:]:
    print("  %8.1f KB  %s" % (c / 1024.0, name))
