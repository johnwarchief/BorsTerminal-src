# -*- coding: utf-8 -*-
"""Final pass on the report: correct the §۰ `main` claim and refresh §۱ب from
the completed sampler window. Reuses live_section() from finalize_report.py so
the numbers in §۱ب always come from one generator."""
import datetime
import importlib.util
import io
import json
import os
import statistics
import sys

RUN = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(RUN, "..", "..", "docs", "research",
                      "PERFORMANCE-MARKET-HOURS-2026-10-17.md")

spec = importlib.util.spec_from_file_location("finalize_report",
                                              os.path.join(RUN, "finalize_report.py"))
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)


def fa(s):
    t = str(s)
    out = []
    for ch in t.lstrip("-"):
        out.append(chr(0x06F0 + int(ch)) if ch.isdigit() else
                   ("٬" if ch == "," else ("٫" if ch == "." else ch)))
    return ("−" if t.startswith("-") else "") + "".join(out)


def num(v):
    v = float(v)
    return fa("{:,.0f}".format(v)) if abs(v - round(v)) < 1e-9 else fa("{:,.1f}".format(v))


HEADING = "## " + chr(0x06F2) + ") " + "مشکلاتِ اثبات‌شده (با عدد و با محلِ کد)"


def main():
    tk = F.tick_stats()
    P = tk["paths"]
    ORJ, STD = 6355843, 6997312
    gap = (STD - ORJ) / float(STD) * 100.0

    L = io.open(REPORT, encoding="utf-8").read().split("\n")

    # 1) the §۰ row about main must state what was actually verified
    i = next(k for k, v in enumerate(L) if v.startswith("| `main`"))
    L[i] = ("| `main` | ریموت همچنان " + "c0402614" + " (`git ls-remote origin refs/heads/main`)؛ " +
            "دستیابیِ من به‌تنهایی " + "ff6b2fb..HEAD" + " است (" + num(29) + " فایل، که " + num(2) +
            " سورس). diff با `origin/main` شاملِ کارِ شاخۀ میزبان (" + "mission/fts-indicator-engineering" +
            ") است، پس سنجشِ «دست‌نخورده» با آن انجام نشده. |")

    # 2) refresh §۱ب from the completed window
    sec = F.live_section(tk, P, "/api/market", "/api/mstat/board", "/api/market/sync-state",
                         "/api/market/delta", ORJ, STD, gap)
    a = next(k for k, v in enumerate(L) if v.startswith("## ") and "پنجرۀ نشستِ زنده" in v)
    b = next(k for k, v in enumerate(L) if v.startswith("### P1 —"))
    L[a:b - 1] = sec + [HEADING]
    # (HEADING is defined below in this file)

    # 3) item 1 of §۵ must agree with the refreshed window
    import io as _io
    tms = [x for x in (json.loads(l) for l in io.open(F.TICK, encoding="utf-8") if l.strip())
           if x.get("path") == "/api/mstat/board"]
    ms = [x["ms"] for x in tms]
    bt = json.load(io.open(os.path.join(RUN, "bench-before.json"), encoding="utf-8"))
    bp = bt["steps"][1]["paths"]["/api/mstat/board"]["p50_ms"]
    m = next(k for k, v in enumerate(L) if v.startswith("1. `") and "mstat" in v)
    L[m] = ("1. `/api/mstat/board` (بنچِ قبل p50 " + num(bp / 1000.0) + "s؛ شنودِ زنده میانه " +
            num(statistics.median(ms) / 1000.0) + "s، بدترین " + num(max(ms) / 1000.0) +
            "s) و `/api/screener`ِ سرد: هیچ‌کدام کشِ کلیددار ندارند.")

    io.open(REPORT, "w", encoding="utf-8", newline="\n").write("\n".join(L))
    print("main row corrected at", i + 1)
    print("live section refreshed:", F.hhmm(tk["t0"]), "->", F.hhmm(tk["t1"]),
          "| samples", tk["n"], "| span_min", round(tk["span"], 1), "| errors", tk["errors"])
    print("board live p50/max ms:", round(statistics.median(ms), 1), round(max(ms), 1))


if __name__ == "__main__":
    main()
