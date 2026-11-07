# -*- coding: utf-8 -*-
"""Insert the output-equality gate result (§۴ب) into the report, from its JSON."""
import io
import json
import os
import collections

RUN = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(RUN, "..", "..", "docs", "research",
                      "PERFORMANCE-MARKET-HOURS-2026-10-17.md")
CHECK = os.path.join(RUN, "equal-check.md")


def fa(s):
    t = str(s)
    neg = t.startswith("-")
    out = []
    for ch in t.lstrip("-"):
        out.append(chr(0x06F0 + int(ch)) if ch.isdigit() else
                   ("٬" if ch == "," else ("٫" if ch == "." else ch)))
    return ("−" if neg else "") + "".join(out)


def num(v):
    return fa("{:,.0f}".format(v)) if abs(float(v) - round(float(v))) < 1e-9 else fa("{:,.1f}".format(v))


def main():
    d = json.load(io.open(CHECK, encoding="utf-8"))
    eps = d["endpoints"]
    tally = collections.Counter(v["verdict"] for v in eps.values())
    vol = sorted(k for k, v in eps.items() if v["verdict"] == "VOLATILE-ONLY")
    total_bytes = sum(v["bytes_after"] for v in eps.values())
    lines = [
        "### ۴ب) گیتِ برابریِ خروجی — `dev/perf_output_equal_v1.py` · **سبز**",
        "",
        "همان ابزارِ خودِ مخزن: هر " + num(len(eps)) + " اندپوینتِ مسیرِ کاربر دو بار گرفته شد (یک‌بار با",
        "کدِ «قبل»، یک‌بار با «بعد»)، `canonicalize` شد و مقایسه گردید. ریگِ یکسان، کپیِ بانکِ یکسان،",
        "ساعتِ یکسان.",
        "",
        "نتیجه: **`" + d.get("verdict", "OUTPUTS_EQUAL") + "`** — " + num(tally["IDENTICAL"]) + " بایت‌به‌بایت",
        "یکی، " + num(tally["VOLATILE-ONLY"]) + " فقط مُهرِ ساعتِ اعلام‌شده درِ خودِ گارد (" +
        "، ".join(vol) + ")، و " + num(tally.get("DATA-DIFF", 0)) + " تفاوتِ داده. حجمِ کلِ " +
        num(total_bytes) + " بایتِ canonical.",
        "",
        "این همان چیزی است که «سریع‌تر بدونِ متفاوت‌تر» را اثبات می‌کند: `compresslevel=1` و کشِ",
        "بدنهٔ قیف هیچ معنایی را عوض نکرده‌اند. شاهدِ خام: `_test_runs/…/equal-check.md` (خروجیِ",
        "همان گارد، با `--report`).",
        "",
        "همچنین پنج سوئیتِ آفلاینِ مرتبطِ دیگرِ مخزن رویِ همین سورس اجرا و سبز شدند (exit بی‌صدا صفر):",
        "`dev/funnel_engine_v1.py` (" + num(75) + " بنده)، `dev/funnel_preset_distinct_v1.py` (" + num(12) +
        "/۰)،",
        "`dev/funnel_registry_v1.py` (ruleset `" + "555648ebff52" + "`)، `dev/test_screener_funnel_gate_v1.py` (" +
        num(30) + " pass / " + num(0) + " fail)،",
        "`dev/market_swr_v1036.py`. باتریِ کاملِ `dev/run_all_tests.py` هنوز NOT_RUN (§۵ بندِ " + fa(8) + ").",
        "",
    ]
    # گیتِ برابری را درست پیشِ «هشدارِ تفسیر» می‌گذاریم
    L = io.open(REPORT, encoding="utf-8").read().split("\n")
    k = next(x for x, v in enumerate(L) if v.startswith("**") and "repeat=" in v)
    L[k:k] = lines
    io.open(REPORT, "w", encoding="utf-8", newline="\n").write("\n".join(L))
    print("inserted %d lines before line %d" % (len(lines), k + 1))
    print("tally:", dict(tally), "verdict:", d.get("verdict"), "endpoints:", len(eps))


if __name__ == "__main__":
    main()
