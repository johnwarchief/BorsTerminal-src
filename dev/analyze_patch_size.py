"""analyze_patch_size.py — چرا پچِ دلتا هنوز بزرگ است؟ (ابزارِ تحلیلِ موقت)

هدف: پیدا کردنِ اینکه حجمِ پچ از کجا می‌آید. یک پچِ overlayِ «همهٔ فایلها»
تقریباً به اندازهٔ نصبِ کامل است؛ این اسکریپت نشان می‌دهد کدام لایه‌ها
بیشترین سهم را دارند و آیا اصلاً فایلهایی هست که بینِ دو نسخه تغییر نکرده‌اند.

اجرا:  python dev/analyze_patch_size.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate")
PATCH = os.path.join(ROOT, "dist", "BorsTerminal_Patch_1.0.9_to_1.0.10.zip")
SETUP = None
out = os.path.join(ROOT, "installer", "out")
if os.path.isdir(out):
    for f in sorted(os.listdir(out)):
        if f.lower().endswith(".exe") and f.lower().startswith("borsterminal"):
            SETUP = os.path.join(out, f)

if not os.path.isdir(DIST):
    print("dist missing: %s" % DIST); sys.exit(1)

# لایهٔ اول: اندازهٔ روی دیسکِ هر شاخه
groups = {}
total = 0
for dirpath, dirnames, filenames in os.walk(DIST):
    for fn in filenames:
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, DIST)
        top = rel.split(os.sep)[0] if os.sep in rel else "(root)"
        if top == "_internal":
            parts = rel.split(os.sep)
            top = "_internal/" + (parts[1] if len(parts) > 2 else "(top)")
        size = os.path.getsize(full)
        groups[top] = groups.get(top, 0) + size
        total += size

print("== on-disk size by layer (uncompressed)")
for k, v in sorted(groups.items(), key=lambda kv: -kv[1])[:14]:
    print("  %-34s %8.1f MB  (%4.1f%%)" % (k, v / 1048576, 100.0 * v / total))
print("  %-34s %8.1f MB" % ("TOTAL", total / 1048576))

print("\n== artifacts")
if os.path.isfile(PATCH):
    print("  patch  %8.1f MB" % (os.path.getsize(PATCH) / 1048576))
if SETUP and os.path.isfile(SETUP):
    print("  setup  %8.1f MB" % (os.path.getsize(SETUP) / 1048576))
    if os.path.isfile(PATCH):
        ratio = 100.0 * os.path.getsize(PATCH) / os.path.getsize(SETUP)
        print("  patch/setup ratio = %.1f%%" % ratio)

# بزرگ‌ترین فایلهای منفرد — معمولاً چند فایلِ باینریِ بزرگ (pyd/dll) کلِ حجم را
# می‌بلعند و آن‌ها بینِ نسخه‌ها به‌ندرت تغییر می‌کنند.
print("\n== largest single files")
files = []
for dirpath, dirnames, filenames in os.walk(DIST):
    for fn in filenames:
        full = os.path.join(dirpath, fn)
        files.append((os.path.getsize(full), os.path.relpath(full, DIST)))
files.sort(reverse=True)
for size, rel in files[:12]:
    print("  %8.1f MB  %s" % (size / 1048576, rel))
