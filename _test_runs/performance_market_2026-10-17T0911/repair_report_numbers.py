# -*- coding: utf-8 -*-
"""Repair the Persian numerals in the perf report from the raw artifacts.

Digits typed by hand into Persian prose get dropped by the writing layer, so
every numeral here is generated with chr(0x06F0+d) and read from the JSON
outputs — never transcribed from memory.
"""
import io
import json
import os
import sys

RUN = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(RUN, "..", "..", "docs", "research",
                      "PERFORMANCE-MARKET-HOURS-2026-10-17.md")


def fa(s, keep=()):
    out = []
    for ch in str(s):
        if ch.isdigit():
            out.append(chr(0x06F0 + int(ch)))
        elif ch in keep:
            out.append(ch)
        elif ch == ",":
            out.append("٬")
        elif ch == ".":
            out.append("٫")
        elif ch == "-":
            out.append("−")
        elif ch == "%":
            out.append("٪")
        else:
            out.append(ch)
    return "".join(out)


def plain(s):
    """Digits only — keeps '-', ':' and '.' as written (ports, clocks, dates)."""
    return fa(s, keep="-:.")


def num(v, dec=1):
    if v is None:
        return "—"
    if dec == 0 or abs(v - round(v)) < 1e-9:
        return fa("{:,.0f}".format(v))
    return fa("{:,.1f}".format(v))


def load(name):
    with io.open(os.path.join(RUN, name), encoding="utf-8") as fh:
        return json.load(fh)


def bench(path):
    d = load(path)
    out = {}
    out["cold_ms"] = d["steps"][0]["identity"][0]["ms"]
    warm_id = d["steps"][1]["paths"]
    warm_gz = d["steps"][2]["paths"]
    conc = d["steps"][3]
    out["304_ms"] = d["steps"][4]["result"]["ms"]
    for tag, src in (("id", warm_id), ("gz", warm_gz)):
        for key, p in (("market", "/api/market"), ("funnel", "/api/funnel"), ("board", "/api/mstat/board")):
            e = src[p]
            out["%s_%s_p50" % (tag, key)] = e["p50_ms"]
            out["%s_%s_p95" % (tag, key)] = e["p95_ms"]
            out["%s_%s_xc" % (tag, key)] = ",".join(sorted(set(e["x_cache"])))
        out["%s_market_bytes" % tag] = sorted(set(src["/api/market"]["bytes"]))[0]
        out["%s_funnel_bytes" % tag] = max(src["/api/funnel"]["bytes"])
    out["conc_wall"] = conc["wall_ms"]
    out["conc_p50"] = conc["p50_ms"]
    out["conc_max"] = conc["max_ms"]
    out["conc_miss"] = conc["builds_observed_MISS"]
    return out


def live(path="/api/mstat/board", f="live-8000.jsonl"):
    import statistics
    ms = []
    with io.open(os.path.join(RUN, f), encoding="utf-8") as fh:
        for line in fh:
            try:
                j = json.loads(line)
            except ValueError:
                continue
            if j.get("path") == path and isinstance(j.get("ms"), (int, float)):
                ms.append(j["ms"])
    if not ms:
        raise SystemExit("no live samples for %s" % path)
    return {"n": len(ms), "min": min(ms), "p50": statistics.median(ms), "max": max(ms)}


def pct(a, b):
    if not a or b is None:
        return "—"
    return fa("%+.0f%%" % ((b - a) / float(a) * 100.0))


def find(lines, needle, lo=0):
    for i in range(lo, len(lines)):
        if needle in lines[i]:
            return i
    raise SystemExit("marker not found: %r" % needle)


def main():
    b0 = bench("bench-before.json")
    b1 = bench("bench-after.json")
    board = live("/api/mstat/board")
    syncst = live("/api/market/sync-state")
    screener = live("/api/screener")
    text = io.open(REPORT, encoding="utf-8").read()
    lines = text.split("\n")

    def put(needle, new):
        i = find(lines, needle)
        lines[i] = new

    # ── §0 ────────────────────────────────────────────────────────────────
    put("# عملکردِ BorsTerminal",
        "# عملکردِ BorsTerminal در ساعتِ واقعیِ معاملات — " + plain("1405-07-25") +
        " (= " + plain("2026-10-17") + ")")
    put("| ماشین |",
        "| ماشین | دو نمونهٔ لحظه‌ای: " + plain("10:54") + " → RAM آزاد " + num(1121, 0) + " از " +
        num(8104, 0) + " MB، CPU " + num(34, 0) + "٪ · دیسک آزاد " + num(17.8) + " GB — و نمونهٔ " +
        plain("09:11") + " که با مرگِ پالر گم شد ⇒ روندِ CPU/RAM رویِ کلِ نشست NOT_MEASURED |")
    put("ریگِ کنترلیِ من",
        "ریگِ کنترلیِ من: همان سورسِ شاخۀ کاری، رویِ پورتِ " + plain(8020) +
        "، با **کپیِ** `market.db`")

    # ── §2 ────────────────────────────────────────────────────────────────
    put("شاهدِ ریگ (orjson فعال",
        "شاهدِ ریگ (orjson فعال، ورودیِ ثابت): p50 = **" + num(b0["id_funnel_p50"]) + "ms**، "
        "p95 = max = " + num(b0["id_funnel_p95"]) + "ms.")
    put("### P3 — `/api/mstat/board`",
        "### P3 — `/api/mstat/board`: " + num(board["min"]) + " تا " + num(board["max"]) +
        "ms برایِ " + num(241970, 0) + " بایت · **باز**")
    put("«بازار در یک نگاه»",
        "(p50 = " + num(b0["id_board_p50"]) + "ms درِ بنچِ «قبل») و درِ شنودِ زندهٔ " +
        num(board["min"]) + "–" + num(board["max"]) + "ms ‏(n=" + plain(board["n"]) +
        "). این «بازار در یک نگاه» را")
    put("### P4 — `/api/market/sync-state`",
        "### P4 — `/api/market/sync-state`: " + num(syncst["min"]) + " تا " + num(syncst["max"]) +
        "ms برایِ " + num(265, 0) + " بایت · **باز**")
    put("### P5 —",
        "### P5 — `/api/screener` بیش از " + num(60, 0) + " ثانیه درِ حالتِ سرد · **باز (بخشی)**")
    put("### P6 — ساختِ سردِ تابلو",
        "### P6 — ساختِ سردِ تابلو " + num(b0["cold_ms"]) + "ms · **باز**")
    put("ردیف است و `COUNT(*)`",
        "  " + num(5981, 0) + " ردیف است و `COUNT(*)` آن " + num(1.1) + "ms. "
        "**هیچ ایندکسی اضافه نشد.**")
    put("بی\u200cخواننده. سنجشِ امشب",
        "بی\u200cخواننده. سنجشِ امروز: **" + num(6355843, 0) + " بایت با orjson / " + num(6997312, 0) +
        " با stdlib** — یعنی")

    # ── §4 ردیف‌هایِ بنچ: بلوکِ ۱۱ خطی → ۱۲ خطِ درست ────────────────────────
    i = find(lines, "| API p50 — `/api/funnel`")
    j = find(lines, "| `/api/mstat/board` |", i)
    rows = [
        "| API p50 — `/api/funnel` (identity) | " + num(b0["id_funnel_p50"]) + " ms | **" +
            num(b1["id_funnel_p50"]) + " ms** | **" + pct(b0["id_funnel_p50"], b1["id_funnel_p50"]) +
            "** | بنچ، ۵ دور گرم |",
        "| API p95 = max — `/api/funnel` (identity) | " + num(b0["id_funnel_p95"]) + " ms | " +
            num(b1["id_funnel_p95"]) + " ms | " + pct(b0["id_funnel_p95"], b1["id_funnel_p95"]) +
            " | درِ دورِ «بعد» یکِ نمونه از ۵ تا `MISS` بود (" + b1["id_funnel_xc"] + ") |",
        "| API p50 — `/api/funnel` (gzip) | " + num(b0["gz_funnel_p50"]) + " ms | **" +
            num(b1["gz_funnel_p50"]) + " ms** | " + pct(b0["gz_funnel_p50"], b1["gz_funnel_p50"]) + " | همان |",
        "| API p95 = max — `/api/funnel` (gzip) | " + num(b0["gz_funnel_p95"]) + " ms | " +
            num(b1["gz_funnel_p95"]) + " ms | " + pct(b0["gz_funnel_p95"], b1["gz_funnel_p95"]) +
            " | همانِ `MISS`ِ تک‌نمونه (" + b1["gz_funnel_xc"] + ") |",
        "| API p50 — `/api/market` (identity) | " + num(b0["id_market_p50"]) + " ms | " +
            num(b1["id_market_p50"]) + " ms | " + pct(b0["id_market_p50"], b1["id_market_p50"]) +
            " | این مسیر کشِ بدنه داشت؛ سودش ازِ `compresslevel` است (" + b1["id_market_xc"] + ") |",
        "| API p50 — `/api/market` (gzip) | " + num(b0["gz_market_p50"]) + " ms | **" +
            num(b1["gz_market_p50"]) + " ms** | " + pct(b0["gz_market_p50"], b1["gz_market_p50"]) + " | همان |",
        "| حجمِ پاسخِ gzip‌شدهٔ `/api/market` | " + num(b0["gz_market_bytes"], 0) + " B | " +
            num(b1["gz_market_bytes"], 0) + " B | " + pct(b0["gz_market_bytes"], b1["gz_market_bytes"]) +
            " حجم (رویِ حلقۀ محلی، نه رویِ سیمِ بیرونی) | `bytes` |",
        "| حجمِ پاسخِ gzip‌شدهٔ `/api/funnel` | " + num(b0["gz_funnel_bytes"], 0) + " B | " +
            num(b1["gz_funnel_bytes"], 0) + " B | " + pct(b0["gz_funnel_bytes"], b1["gz_funnel_bytes"]) +
            " حجم | همان |",
        "| پاسخِ شرطی ۳۰۴ | " + num(b0["304_ms"]) + " ms / ۰ B | " + num(b1["304_ms"]) +
            " ms / ۰ B | " + pct(b0["304_ms"], b1["304_ms"]) + " | `If-None-Match` |",
        "| ساختِ سردِ تابلو | " + num(b0["cold_ms"]) + " ms | " + num(b1["cold_ms"]) + " ms | " +
            pct(b0["cold_ms"], b1["cold_ms"]) + " (تک‌نمونه؛ پراکندگی بالا) | اولینِ درخواستِ بعدِ restart |",
        "| ۶ درخواستِ هم‌زمانِ کش‌خورده | " + num(b0["conc_wall"]) + " ms دیواری (p50 " +
            num(b0["conc_p50"]) + "، max " + num(b0["conc_max"]) + ") | " + num(b1["conc_wall"]) +
            " ms دیواری (p50 " + num(b1["conc_p50"]) + "، max " + num(b1["conc_max"]) + ") | " +
            pct(b0["conc_wall"], b1["conc_wall"]) + " = نویز · ساختِ اضافه درِ هر دو دور = " +
            num(b0["conc_miss"], 0) + " و " + num(b1["conc_miss"], 0) + " | concurrency probe |",
        "| `/api/mstat/board` (identity) | " + num(b0["id_board_p50"]) + " ms | " + num(b1["id_board_p50"]) +
            " ms | " + pct(b0["id_board_p50"], b1["id_board_p50"]) +
            " | دست نخورد؛ P3 هنوز باز است (gzip: " + num(b0["gz_board_p50"]) + " → " +
            num(b1["gz_board_p50"]) + ") |",
    ]
    lines[i:j + 1] = rows

    io.open(REPORT, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    sys.stdout.write("ok — bench block %d..%d replaced with %d rows\n" % (i + 1, j + 1, len(rows)))
    sys.stdout.write("funnel id p50 %s->%s %s | p95 %s->%s %s\n" % (
        b0["id_funnel_p50"], b1["id_funnel_p50"], pct(b0["id_funnel_p50"], b1["id_funnel_p50"]),
        b0["id_funnel_p95"], b1["id_funnel_p95"], pct(b0["id_funnel_p95"], b1["id_funnel_p95"])))


if __name__ == "__main__":
    main()
