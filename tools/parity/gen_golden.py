#!/usr/bin/env python
"""وکتورهایِ طلاییِ codal_periods از خودِ پایتون → backend-go/internal/period/testdata/cases.json

رقمِ فارسی/عربی با chr ساخته می‌شود (قیدِ AGENTS.md) تا ویرایشِ دستی رقم را ندزدد.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import codal_periods as CP  # noqa: E402

OUT = os.path.join(ROOT, "backend-go", "internal", "period", "testdata", "cases.json")


def digits(text, base):
    table = str.maketrans("0123456789", "".join(chr(base + d) for d in range(10)))
    return text.translate(table)


def main() -> int:
    fa = lambda s: digits(s, 0x06F0)  # noqa: E731
    ar = lambda s: digits(s, 0x0660)  # noqa: E731
    raw = [
        None, "", "1405/06/31", "1405-6-31", "1405/06/31 18:10:30",
        "1405/02/301", "1405/13/45", "1405/02/30", "زمان نامعلوم",
        fa("1405/06/31"), ar("1405/06/31"), fa("1405-6-3"),
        14050631.0, 1405, " 1405/06/31 ",
        "1405/13/45 1404/01/01", "01405/06/31", "1405/02/301 1404/01/01",
        "1405\u00a0/\u00a006/\u00a031",
    ]
    titles = [
        "", "دوره ۶ ماهه", "صورت مالی 3 ماهه منتهی به 1404/12/29",
        "مجمع از 1403/01/01 تا 1403/12/29", "بدون دوره",
        fa("دوره ۱۲ ماهه منتهی به ۱۴۰۴/۱۲/۲۹"),
        "مجمع از 1403/01/01 تا 1403/12/29 منتهی\u00a0به 1404/12/29",
        "دوره ۶\u00a0ماهه",
    ]
    months = [None, "", "6", "6.0", "0", "13", "abc", 6, 6.0]
    ends = [None, "1404/12/29", "1404/12/29 18:00:00", "1404-12-29", "1405/13/45", "1403/12/29"]

    out = {
        "canonicalize": [{"in": c, "out": CP.canonicalize(c)} for c in raw],
        "from_title": [{"in": t, "out": CP.from_title(t)} for t in titles],
        "months_from_title": [{"in": t, "out": CP.months_from_title(t)} for t in titles],
        "derive": [{"end": e, "title": t, "out": list(CP.derive(e, t))}
                   for e in ends for t in titles],
        "effective_months": [{"end": e, "months": m, "title": t, "out": list(CP.effective_months(e, m, t))}
                             for e in ends for m in months for t in titles],
        "is_canonical": [{"in": c, "out": CP.is_canonical(c)} for c in raw],
        "is_undated": [{"in": c, "out": CP.is_undated(c)} for c in raw],
        "ym": [{"in": c, "out": list(CP.ym(c))} for c in raw],
        "fiscal_year": [{"in": c, "out": CP.fiscal_year(c)} for c in raw],
        "desc_sort_key": [{"in": c, "out": CP.desc_sort_key(c)} for c in raw],
        "latest": [{"in": xs, "out": CP.latest(xs)} for xs in
                   ([], ["1404/01/01"], ["1404/01/01", "1405/02/02"], [None, "1405/13/45"], ["1405/02/02", None])],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    total = sum(len(v) for v in out.values())
    print("golden cases:", total, "->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
