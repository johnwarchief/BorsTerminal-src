#!/usr/bin/env python
"""گیتِ B2b: هر سیزده مسیرِ GETِ /api/mstat/* رویِ دو کپیِ یخ‌زده.

همان ابزارِ gate_b2a است — همان دو کپی، همان گاردِ ریشه/کناربانک، همان سیزده
بررسی، همان POSTِ ۵۰۱ — با فهرستی که همهٔ کیس‌هایِ B2a را دارد به‌علاوهٔ چهار
کیسِ دو مسیرِ آخر (smart-money و board). فهرست در زمانِ اجرا از دو فایل ساخته
می‌شود تا یک نسخهٔ دستیِ سی‌وهفت‌کیسی نداشته باشیم: هر اصلاحِ کیسِ B2a
خودبه‌خود در گیتِ نهایی هم می‌آید و دو فهرست نمی‌توانند از هم جدا بیفتند.

شاهد: `_audit/parity/B2b.json` و قرارداد: `_audit/parity/B2b-contract.json`.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BASE = os.path.join(HERE, "cases_b2a.json")
EXTRA = os.path.join(HERE, "cases_b2b_extra.json")

# خانوادهٔ کاملِ مسیرها و کیس‌هایِ الزامیِ B2-2. بی‌این، یک فایلِ خالیِ
# cases_b2b_extra.json هنوز «B2b»ِ سبز با ۳۳ کیس می‌ساخت و ادعایِ سیزده مسیر
# فقط به عرف تکیه می‌کرد.
MSTAT_ROUTES = {"summary", "histogram", "thermometer", "depth", "clientsplit",
                "market-snapshot", "phase", "mainwatch", "industries", "timeline",
                "phases", "smart-money", "board"}
EXTRA_CASES = {"smart-money", "board-default", "board-stock-3", "board-limit-422"}


def route_tails(cases):
    """دنبالهٔ مسیرهایِ GETِ mstat که در فهرست پوشش دارند (بی‌query)."""
    out = set()
    for case in cases:
        path = (case.get("path") or "").split("?", 1)[0]
        if case.get("method") == "GET" and path.startswith("/api/mstat/"):
            out.add(path.rsplit("/", 1)[-1])
    return out


def merged_cases(dest):
    """B2a + کیس‌هایِ B2-2 در یک فایل؛ نامِ تکراری یعنی دو تعریفِ یک کیس."""
    with open(BASE, encoding="utf-8") as f:
        cases = json.load(f)
    with open(EXTRA, encoding="utf-8") as f:
        extra = json.load(f)
    names = {c["name"] for c in cases["cases"]}
    for case in extra["cases"]:
        if case["name"] in names:
            raise SystemExit("duplicate case name: %s" % case["name"])
        names.add(case["name"])
    cases["cases"].extend(extra["cases"])
    missing_routes = MSTAT_ROUTES - route_tails(cases["cases"])
    if missing_routes:
        raise SystemExit("merged cases miss mstat routes: %s" % sorted(missing_routes))
    missing_extra = EXTRA_CASES - names
    if missing_extra:
        raise SystemExit("B2-2 cases missing: %s" % sorted(missing_extra))
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False)
    return len(cases["cases"]), len(extra["cases"])


def main():
    fd, path = tempfile.mkstemp(prefix="b2b-cases-", suffix=".json")
    os.close(fd)
    try:
        count, extra = merged_cases(path)
        os.environ["BORS_B2_CASES"] = path
        os.environ["BORS_B2_OUT"] = os.path.join(ROOT, "_audit", "parity", "B2b.json")
        os.environ["BORS_B2_CONTRACT"] = os.path.join(
            ROOT, "_audit", "parity", "B2b-contract.json")
        sys.path.insert(0, HERE)
        import gate_b2a
        print("B2b: %d cases (%d from B2a + %d B2-2)" % (count, count - extra, extra))
        return gate_b2a.main()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
