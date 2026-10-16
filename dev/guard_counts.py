# -*- coding: utf-8 -*-
"""dev/guard_counts.py — تنها ترجمانِ «چند تا بررسی شد» برایِ گزارشگرِ گیت‌ها.

چرا این فایل جداست (مأموریتِ ۱۴۰۵-۰۷-۲۳، بندِ ۱-۱۴ و ۷): `dev/run_all_tests.py`
سه الگو را می‌شناخت و هر چیزِ دیگر را با شمارشِ کلمه‌های PASS/FAIL پر می‌کرد.
نتیجه: گاردهایی که «۱۲ سنجه، ۰ خطا» یا «۹ سبز، ۲ قرمز» چاپ می‌کردند درِ خلاصه
«۰ pass / ۰ fail» می‌شدند — یعنی *سکوت* درِ لباسِ موفقیت. این ماژول همان
الگوها را یک‌جا و قابلِ آزمون نگه می‌دارد؛ `dev/guard_counts_v1110.py` می‌سنجدش.

قاعدۀ خروجی: یا شمارشِ واقعی (`countable=True`)، یا صریح «بی‌شمارش»
(`countable=False`) — هر دو بهتر از عددِ ساختگیِ صفر.
"""
from __future__ import annotations

import re
from typing import Optional

#: (نامِ الگو، regex، سازگارکننده) — به ترتیبِ اولویت؛ اولین تطبیق برنده است.
PATTERNS = (
    # `execution_contract_v1: 20 passed / 0 failed` و `20/24 passed`
    ("X/Y passed", re.compile(r"(\d+)\s*/\s*(\d+)\s+passed")),
    ("N passed, M failed", re.compile(r"(\d+)\spassed[ ,/]+(\d+)\s*failed")),
    # `۱۲ بررسی سبز، ۰ شکست`
    ("N سبز، M شکست", re.compile(r"(\d+)\s*\u0628\u0631\u0631\u0633\u06cc\s*\u0633\u0628\u0632\u060c\s*(\d+)\s*\u0634\u06a9\u0633\u062a")),
    # `۱۲ سنجه، ۰ خطا` (dev/market_tick_v1045)
    ("N سنجه، M خطا", re.compile(r"(\d+)\s*\u0633\u0646\u062c\u0647\u060c\s*(\d+)\s*\u062e\u0637\u0627")),
    # `۱۲ سبز، ۰ قرمز` (dev/fts_engine_paths_parity_v1076)
    ("N سبز، M قرمز", re.compile(r"(\d+)\s*\u0633\u0628\u0632\u060c\s*(\d+)\s*\u0642\u0631\u0645\u0632")),
    # `OK — 12/12` و `%d/%d` تنها درِ خطِ پایانی
    ("OK — N/M", re.compile(r"OK\s*\u2014\s*(\d+)\s*/\s*(\d+)")),
    # `۲۹ سرخ` (candle_integrity) — فقط شمارِ خطا؛ کلِ بررسی‌ها از PASS/FAIL می‌آید
    ("N سرخ", re.compile(r"(\d+)\s*\u0633\u0631\u062e")),
)

#: خروجی‌هایی که «هیچ شمارشی» ندارند — اینها باید صریح بی‌شمارش گزارش شوند.
SILENT = re.compile(r"^\s*(ok|OK|done|PASS|)\s*$")


def parse_counts(txt: str) -> Optional[dict]:
    """`{'passed', 'total', 'pattern'}` یا None اگر هیچِ شمارشِ واقعی نبود.

    هر الگو *خود* معنا را دارد: «۱۲/۲۴ passed» کل را می‌دهد، «۱۲ سنجه، ۲ خطا»
    کل و خطا را، «۲۹ سرخ» فقط خطا را. یکِ سازگارکنندهٔ عمومی برایِ همه، همان
    اشتباهی است که شمارش‌ها را عوضی می‌کند.
    """
    for name, rx in PATTERNS:
        m = rx.search(txt)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        if name == "X/Y passed":
            return {"passed": g[0], "total": g[1], "pattern": name}
        if name == "OK — N/M":
            # `OK — 12/12`: مخرج *کل* است، نه خطا
            return {"passed": g[0], "total": g[1], "pattern": name,
                    "failed": max(0, g[1] - g[0])}
        if name in ("N سبز، M قرمز", "N سنجه، M خطا"):
            # a = کلِ سنجه‌ها، b = خطا
            failed = g[1]
            return {"passed": max(0, g[0] - failed), "total": g[0],
                    "pattern": name, "failed": failed}
        if name in ("N بررسی سبز، M شکست", "N سبز، M شکست"):
            return {"passed": g[0], "total": g[0] + g[1], "pattern": name,
                    "failed": g[1]}
        if name == "N passed, M failed":
            return {"passed": g[0], "total": g[0] + g[1], "pattern": name,
                    "failed": g[1]}
        if name == "N سرخ":
            # فقط شمارِ خطا؛ کل از tokenهای PASS/FAILِ همان خروجی می‌آید
            n_pass = len(re.findall(r"\bPASS\b", txt))
            return {"passed": n_pass, "total": n_pass + g[0], "pattern": name,
                    "failed": g[0]}
    return None


def summarize(txt: str, rc: int) -> dict:
    """تصمیرِ نهاییِ گزارشگر برایِ یکِ suite: شمارش‌دار یا بی‌شمارش."""
    got = parse_counts(txt)
    if got is not None:
        ok = rc == 0 and got.get("failed", 0) == 0
        return {"countable": True, "ok": ok, "detail": "%d/%d" % (got["passed"], got["total"]),
                "pattern": got["pattern"]}
    n_pass = len(re.findall(r"\bPASS\b", txt))
    n_fail = len(re.findall(r"\bFAIL\b", txt))
    if n_pass or n_fail:
        # tokenهای PASS/FAIL شمارش‌اند، ولی «X/Y» نیستند؛ نامِ الگو روشن می‌ماند
        return {"countable": True, "ok": rc == 0 and n_fail == 0,
                "detail": "%d pass / %d fail" % (n_pass, n_fail), "pattern": "PASS/FAIL tokens"}
    return {"countable": False, "ok": rc == 0,
            "detail": "\u0628\u06cc\u200c\u0634\u0645\u0627\u0631\u0634 (\u0641\u0642\u0637 exit code)",
            "pattern": "silent"}
