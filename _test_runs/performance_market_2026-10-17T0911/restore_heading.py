# -*- coding: utf-8 -*-
"""Restore the §۲ heading that the block swap consumed, and teach
refresh_live.py to re-emit it so the next refresh cannot lose it again."""
import io
import os

RUN = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(RUN, "..", "..", "docs", "research",
                      "PERFORMANCE-MARKET-HOURS-2026-10-17.md")
HEADING = "## " + chr(0x06F2) + ") " + "مشکلاتِ اثبات‌شده (با عدد و با محلِ کد)"


def main():
    L = io.open(REPORT, encoding="utf-8").read().split("\n")
    if not any(v.startswith("## ") and "مشکلاتِ اثبات" in v for v in L):
        p = next(k for k, v in enumerate(L) if v.startswith("### P1 —"))
        # '---' , '' , [heading] , '' , '### P1'
        L[p - 1:p - 1] = [HEADING, ""]
        io.open(REPORT, "w", encoding="utf-8", newline="\n").write("\n".join(L))
        print("heading re-inserted before line", p)
    else:
        print("heading already present")

    # teach refresh_live.py to keep the heading in its own block
    q = os.path.join(RUN, "refresh_live.py")
    s = io.open(q, encoding="utf-8").read()
    old = '    L[a:b - 1] = sec'
    new = '    L[a:b - 1] = sec + [HEADING]\n    # (HEADING is defined below in this file)'
    if old in s and "HEADING]" not in s:
        s = s.replace(old, new)
        s = s.replace("F = importlib.util.module_from_spec(spec)",
                      'F = importlib.util.module_from_spec(spec)')
        s = s.replace("def main():", "HEADING = \"## \" + chr(0x06F2) + \") \" + " +
                      '"مشکلاتِ اثبات‌شده (با عدد و با محلِ کد)"\n\n\ndef main():', 1)
        io.open(q, "w", encoding="utf-8", newline="\n").write(s)
        import ast
        ast.parse(s)
        print("refresh_live.py taught to re-emit the heading")


if __name__ == "__main__":
    main()
