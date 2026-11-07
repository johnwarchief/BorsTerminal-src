# -*- coding: utf-8 -*-
"""Put the interpretation warning directly under the table, above §۴ب."""
import io
import os

RUN = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(RUN, "..", "..", "docs", "research",
                      "PERFORMANCE-MARKET-HOURS-2026-10-17.md")

p = REPORT
L = io.open(p, encoding="utf-8").read().split("\n")
w = next(k for k, v in enumerate(L) if v.startswith("**") and "repeat=" in v)
warn = L.pop(w)
h = next(k for k, v in enumerate(L) if v.startswith("### ") and "perf_output_equal_v1" in v)
L[h:h] = [warn, ""]
i = next(k for k, v in enumerate(L) if "exit" in v and "صفر" in v)
L[i] = L[i].replace("(exit بی‌صدا صفر)", "(exit code صفر)")
io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("warning moved to line", h + 1, "| exit phrasing fixed on", i + 1)
