# -*- coding: utf-8 -*-
"""dump.py — چاپ محدودهٔ خطی یک فایل در خروجی UTF-8 (دورزدن کش ابزار read).

usage: python dev/dump.py <file> <start> <end> [out]
"""
import io, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
f, s, e = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
out = sys.argv[4] if len(sys.argv) > 4 else None
fp = f if os.path.isabs(f) else os.path.join(BASE, f)
lines = io.open(fp, encoding="utf-8", errors="replace").read().split("\n")
buf = ["### %s  lines %d-%d of %d" % (f, s, e, len(lines))]
for i in range(max(1, s) - 1, min(len(lines), e)):
    buf.append("%5d | %s" % (i + 1, lines[i]))
text = "\n".join(buf)
if out:
    op = out if os.path.isabs(out) else os.path.join(BASE, out)
    io.open(op, "w", encoding="utf-8").write(text + "\n")
    print("wrote %s (%d lines)" % (out, e - s + 1))
else:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(text)
