# -*- coding: utf-8 -*-
"""Last two prose fixes in the report, both generated from raw artifacts."""
import io
import json
import os

RUN = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(RUN, "..", "..", "docs", "research",
                      "PERFORMANCE-MARKET-HOURS-2026-10-17.md")


def fa(s):
    t = str(s)
    neg = t.startswith("-")
    out = []
    for ch in t.lstrip("-"):
        out.append(chr(0x06F0 + int(ch)) if ch.isdigit() else
                   ("٬" if ch == "," else ("٫" if ch == "." else ch)))
    return ("−" if neg else "") + "".join(out)


def num(v):
    v = float(v)
    s = "{:,.1f}".format(v) if abs(v - round(v)) > 1e-9 else "{:,.0f}".format(v)
    return fa(s)


def main():
    d = json.load(io.open(os.path.join(RUN, "browser-before-paired", "browser-perf.json"),
                          encoding="utf-8"))
    mk = next(r for r in d["results"] if r["label"] == "market-1366x768")
    by = {x["path"]: x for x in mk["by_path"]}
    dn, mn, win = by["/api/market/delta"]["n"], by["/api/market"]["n"], mk["window_s"]

    p = REPORT
    L = io.open(p, encoding="utf-8").read().split("\n")

    dbl = [x for x, v in enumerate(L) if "  " in v and "امروز" in v]
    k = dbl[0] if dbl else 0
    if dbl:
        L[k] = L[k].replace("  ", " ")

    i = next(x for x, v in enumerate(L) if v.startswith("- ") and "`since`" in v)
    head = "  نفرستاده بودم و "
    tail = " طبقِ قرارداد `full/stale-client` برمی‌گرداند. شواهدِ"
    L[i:i + 3] = [
        "- **«مسیرِ delta مرده است»:** خوانشِ اولِ من غلطِ ابزارِ خودم بود — من `since`",
        head + "`since=" + fa(-1) + "`" + tail,
        "  مرورگر (پنجرۀ " + num(win) + "s، view تابلو): " + num(mn) + " بار `/api/market` کامل در برابرِ " +
        num(dn) + " بار `delta` — یعنی رابط دارد delta را مصرف می‌کند. delta سالم است.",
    ]

    import statistics
    tms = []
    with io.open(os.path.join(RUN, "live-8000-tick-sampler.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("path") == "/api/mstat/board":
                tms.append(r["ms"])
    bt = json.load(io.open(os.path.join(RUN, "bench-before.json"), encoding="utf-8"))
    bp = bt["steps"][1]["paths"]["/api/mstat/board"]["p50_ms"]
    m = next(x for x, v in enumerate(L) if v.startswith("1. `") and "mstat" in v)
    L[m] = ("1. `/api/mstat/board` (" + "بنچِ قبل p50 " + num(bp / 1000.0) +        "s؛ شنودِ زنده میانه " + num(statistics.median(tms) / 1000.0) +        "s، بدترین " + num(max(tms) / 1000.0) +
        "s) و `/api/screener`ِ سرد: هیچ‌کدام کشِ کلیددار ندارند.")

    io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
    print("prose double-space lines fixed:", len(dbl))
    print("bullet:", L[i + 1][:100])
    print("bullet2:", L[i + 2][:130])


if __name__ == "__main__":
    main()
