# -*- coding: utf-8 -*-
"""grep.py — جستجوی مطمئن و چندخطی (جایگزین Select-String که جدول می‌شکند).

usage: python dev/grep.py <pattern> [path ...]
"""
import io, os, re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# v9.8.1: the route handlers live in api/*.py now; app.py is only the shim.
DEFAULT = ["app.py", "bors_config.py", "bors_flags.py", "archive/legacy_static/app.js",
           "archive/legacy_static/index.html", "fts_engine.py", "api",
           "static/calendar/calendar.js", "static/calendar/calendarService.js",
           "archive/legacy_static/tech_tools.js", "dev/calendar_fetcher.py"]


def expand(paths):
    """A directory entry expands to the .py files inside it (api/ -> api/*.py)."""
    out = []
    for q in paths:
        fq = q if os.path.isabs(q) else os.path.join(BASE, q)
        if os.path.isdir(fq):
            out += [os.path.join(q, f) for f in sorted(os.listdir(fq))
                    if f.endswith(".py")]
        else:
            out.append(q)          # let the report loop show MISSING
    return out

pat = sys.argv[1]
args = sys.argv[2:]
out_path = None
if args and args[0] == "--out":
    out_path = args[1]
    args = args[2:]
paths = expand(args or DEFAULT)
rx = re.compile(pat, re.I)

buf = []
def emit(s=""):
    buf.append(s)

for p in paths:
    fp = p if os.path.isabs(p) else os.path.join(BASE, p)
    if not os.path.isfile(fp):
        emit("MISSING: %s" % p)
        continue
    try:
        lines = io.open(fp, encoding="utf-8", errors="replace").read().split("\n")
    except Exception as e:
        emit("ERR %s: %s" % (p, e))
        continue
    hits = [(i + 1, l.strip()[:170]) for i, l in enumerate(lines) if rx.search(l)]
    emit("=== %s  (%d hits / %d lines) ===" % (p, len(hits), len(lines)))
    for n, l in hits[:200]:
        emit("  %6d | %s" % (n, l))
    if len(hits) > 200:
        emit("  ... %d more" % (len(hits) - 200))

text = "\n".join(buf)
if out_path:
    io.open(out_path if os.path.isabs(out_path) else os.path.join(BASE, out_path),
            "w", encoding="utf-8").write(text + "\n")
    print("wrote %d lines -> %s" % (len(buf), out_path))
else:
    print(text)

