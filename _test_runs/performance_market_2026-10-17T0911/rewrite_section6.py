# -*- coding: utf-8 -*-
"""Rewrite §۶ with the commands that were actually used, and record the
commits/artifact hashes the mission asks for (Phase 6, بندِ ۵)."""
import io
import os

RUN = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(RUN, "..", "..", "docs", "research",
                      "PERFORMANCE-MARKET-HOURS-2026-10-17.md")

COMMITS = [
    ("a43b137", "perf(funnel)", "سورسِ رفع: `app.py` + `api/funnel.py` + گارد + ابزارِ سنجش"),
    ("77d5a93", "docs(perf)", "گزارشِ کامل + خروجیِ خامِ `_test_runs/`"),
    ("08e572d", "docs(perf)", "پنجرۀ شنودِ زنده تا ۷۱ دقیقه + تصحیحِ ادعایِ §۰"),
]


def fa(s):
    return "".join(chr(0x06F0 + int(ch)) if ch.isdigit() else ch for ch in str(s))


def main():
    L = io.open(REPORT, encoding="utf-8").read().split("\n")
    s = next(k for k, v in enumerate(L) if v.startswith("## ") and "فرمانِ" in v)
    tail = [
        "## ۶) فرمانِ اجرایِ دوباره",
        "",
        "```bash",
        "# ۱) ریگِ کنترلی — کپیِ بانک، بی‌هیچ fetchِ بیرونی",
        "cd .worktrees/system2-perf",
        "cp <BorsTerminal-src>/market.db .        # یا sqlite3 market.db \".backup\" 227MB",
        "BORS_NO_FETCH_LOOPS=1 PYTHONIOENCODING=utf-8 \\",
        "  python -m uvicorn app:app --host 127.0.0.1 --port 8020 --log-level warning",
        "",
        "# ۲) باتریِ سنجش — یک دور قبل، یک دور بعد (فایل‌ها را عوض کن، ریگ را restart کن)",
        "python tools/perf_market_hours_bench.py --port 8020 --label before --out …/bench-before.json",
        "python dev/funnel_body_cache_v1.py --port 8020                      # ۱۱ سنجه",
        "python tools/perf_market_concurrency_probe.py --port 8020 --n 6",
        "",
        "# ۳) گیتِ برابریِ خروجی (همان ابزارِ مخزن) — قبل و بعد ازِ تغییر",
        "python dev/perf_output_equal_v1.py save  --base http://127.0.0.1:8020 --tag before-mylift",
        "python dev/perf_output_equal_v1.py save  --base http://127.0.0.1:8020 --tag after-mylift",
        "python dev/perf_output_equal_v1.py check --before before-mylift --after after-mylift \\",
        "       --report equal-check-2026-10-17.md      # اسمِ مسیرِ نسبی بده؛ گیت خودش را به _audit/perf/ می‌چسباند",
        "",
        "# ۴) پنجرۀ مرورگر (playwright-core را از node_modulesِ ورک‌تریِ خواهر قرض می‌گیرد)",
        "MSYS_NO_PATHCONV=1 node --experimental-strip-types \\",
        "  tools/perf_market_hours_browser_probe.mts --url http://127.0.0.1:8020 \\",
        "  --window 90 --out _test_runs/…/browser-after",
        "",
        "# ۵) شنودِ پیوستۀ نشست (به بک‌اندِ واقعی، بدونِ Accept-Encoding)",
        "python _test_runs/…/perf_tick_sampler.py 8000 …/live.jsonl 95",
        "",
        "# ۶) اعدادِ گزارش را از همان فایل‌ها بازسازی می‌کند (نه از حافظه)",
        "python _test_runs/…/repair_report_numbers.py && python _test_runs/…/finalize_report.py",
        "python _test_runs/…/add_equal_section.py && python _test_runs/…/refresh_live.py",
        "```",
        "",
        "مقایسهٔ gzip با سطحِ پیشین: `BORS_GZIP_LEVEL=5` رویِ ریگ و دوباره باتری.",
        "",
        "## ۷) کامیت‌ها و اثرِ انگشتِ فایل‌ها",
        "",
        "شاخه: `mission/system2-perf-market-hours-2026-10-17` (پایه `ff6b2fb`) — push شده به",
        "`origin`؛ `main`/" + "c0402614" + "، تگ‌ها و ریلیز دست‌نخورده. PR ساخته نشد (به رأیِ مالک).",
        "",
        "| کامیت | چی | ",
        "|---|---|",
    ]
    for h, kind, what in COMMITS:
        tail.append("| `" + h + "` | " + kind + " | " + what + " |")
    tail += [
        "",
        "sha256 (اول ۱۶ کاراکتر) درِ لحظۀ نوشتن: `app.py` " + "bcdc793e1f377378" + " · `api/funnel.py` " +
        "0867f8814f578a24 ·",
        "این فایل " + "581a941fc9e655c6" + ". بیلدِ دسکتاپِ آزمایشی ساخته نشد ⇒ SHA آرتیفکتی وجود ندارد",
        "(§۵ بندِ " + fa(9) + ").",
        "",
    ]
    L[s:] = tail
    io.open(REPORT, "w", encoding="utf-8", newline="\n").write("\n".join(L))
    print("§۶ rewritten from line", s + 1, "| new total", len(L))


if __name__ == "__main__":
    main()
