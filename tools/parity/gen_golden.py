#!/usr/bin/env python
"""وکتورهایِ طلاییِ codal_periods از خودِ پایتون → backend-go/internal/period/testdata/cases.json

رقمِ فارسی/عربی با chr ساخته می‌شود (قیدِ AGENTS.md) تا ویرایشِ دستی رقم را ندزدد.

سه طبقه درِ این فایل سنجیده می‌شود، نه یکی:
  * رشته‌هایِ تابعی (`canonicalize` و هم‌خانواده‌ها) — پایتون ↔ Go؛
  * رشته‌هایِ SQL (`dated_sql` و هم‌خانواده‌ها) — هر دو زبان باید **همان رشته** را
    به SQLite بدهند، پس خودِ رشته طلایی است؛
  * رفتارِ آن رشته رویِ SQLite — ردیف‌هایِ نام‌گذشته در یکِ بانکِ حافظه‌ای
    می‌نشینند و «کدام ردیف دوره دارد» و «ترتیبِ آخرین» از خودِ SQLite خوانده
    می‌شود. هیچ‌کدام از این دو فهرست دست‌نویس نیست.

هم‌سنجیِ شرطِ پایتون و شرطِ SQL اینجا **ادعا نمی‌شود**: `is_canonical` با
`.strip()` هر جای خالی را برمی‌دارد و `trim()` در SQLite فقط فاصله (U+0020).
ردیف‌هایِ شاهدِ همین شکاف درِ `sql.seam_ids` ثبت می‌شوند تا Go هم همان شکاف را
بازتولید کند، نه اینکه آن را «درست» کند.

--out مسیرِ جایگزین می‌نویسد (گاردِ تازگیِ طلایی از آن استفاده می‌کند).
"""
import argparse
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import codal_periods as CP  # noqa: E402

OUT = os.path.join(ROOT, "backend-go", "internal", "period", "testdata", "cases.json")


def digits(text, base):
    table = str.maketrans("0123456789", "".join(chr(base + d) for d in range(10)))
    return text.translate(table)


SQL_CALLS = ("dated_sql", "undated_sql", "order_expr", "latest_order_sql")
SQL_ALIASES = (None, "", "fs", "ms")


def sql_vectors(fa, ar):
    """هم متنِ SQL و هم رفتارِ همان متن رویِ SQLite — هر دو از خودِ پایتون.

    ردیف‌ها سه چیزِ جدا را می‌آزمایند: شکلِ درست، شکلِ غلط، و سه ردیفِ
    «شکلِ درست با جای خالیِ غیرفاصله» که شرطِ پایتون آن را canonical می‌شمارد و
    شرطِ SQL نه (`trim` در SQLite فقط U+0020 را برمی‌دارد؛ تب، nbsp و U+001C را
    نه). آن‌ها درِ `seam_ids` ثبت می‌شوند تا Go همان شکاف را بازتولید کند، نه
    اینکه آن را «درست» کند.
    """
    text = [{"call": c, "alias": a, "out": getattr(CP, c)(a)}
            for c in SQL_CALLS for a in SQL_ALIASES]
    text.append({"call": "DATED_SQL", "alias": None, "out": CP.DATED_SQL})
    text.append({"call": "UNDATED_SQL", "alias": None, "out": CP.UNDATED_SQL})
    text.append({"call": "VALID_GLOB", "alias": None, "out": CP.VALID_GLOB})

    rows = [
        (1, None),                          # بی‌دورهٔ واقعی: NULL
        (2, ""),                            # رشتهٔ خالی
        (3, "   "),                         # فقط فاصله — trim خالی می‌کند
        (4, "1405-06-31"),                  # خط تیره: بندِ ۱ صریحاً بی‌دوره می‌گوید
        (5, "1405/06/31"),                  # canonical
        (6, "1404/01/01"),                  # canonicalِ کهنه
        (7, fa("1405/06/30")),              # رقمِ فارسی: SQL و پایتون هر دو رد
        (8, "1405/13/45"),                  # شکل‌درست، تقویم‌غلط: شرطِ خواندن فقط شکل
        (9, "1405/06/31 "),                 # فاصلهٔ انتهایی: هر دو شرط می‌پذیرند
        (10, "\t1405/06/31"),               # شکافِ trim (فاصله نه تب)
        (11, "1405/06/301"),                # lookaround: تاریخ نیست
        (12, ar("1405/06/30")),             # رقمِ عربی
        (13, "1405/6/31"),                  # پهنایِ رقم کم
        (14, "1405/06/31" + chr(0x00A0)),   # شکافِ trim دوم (nbsp)
        (15, "1403/12/29"),                 # canonicalِ کهنه‌تر
        (16, "0000/01/01"),                 # canonicalِ صفرها: درِ ترتیب آخر می‌نشیند
        (17, chr(0x001C) + "1405/06/31"),   # شکافِ سوم: .strip()ِ پایتون U+001C را هم
                                            # جای خالی می‌شمارد، Goِ پیش‌فرض نه
    ]
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE financial_statements "
                "(tracing_no INTEGER PRIMARY KEY, period_end TEXT)")
    con.executemany("INSERT INTO financial_statements (tracing_no, period_end) VALUES (?, ?)",
                    rows)

    def ids(sql, *params):
        return [r[0] for r in con.execute(sql, params)]

    dated = ids("SELECT tracing_no FROM financial_statements WHERE " + CP.DATED_SQL
                + " ORDER BY tracing_no")
    undated = ids("SELECT tracing_no FROM financial_statements WHERE " + CP.UNDATED_SQL
                  + " ORDER BY tracing_no")
    ordered = ids("SELECT tracing_no FROM financial_statements ORDER BY "
                  + CP.order_expr() + ", tracing_no DESC")
    latest_dated = ids("SELECT tracing_no FROM financial_statements WHERE " + CP.DATED_SQL
                       + " " + CP.latest_order_sql() + " LIMIT 1")
    latest_any = ids("SELECT tracing_no FROM financial_statements "
                     + CP.latest_order_sql() + " LIMIT 1")
    canon_ids = [n for n, v in rows if CP.is_canonical(v)]
    con.close()
    return {
        "text": text,
        "rows": [{"tracing_no": n, "period_end": v} for n, v in rows],
        "py_canonical_ids": canon_ids,
        "dated_ids": dated,
        "undated_ids": undated,
        "order_ids": ordered,
        "latest_dated_id": latest_dated[0] if latest_dated else None,
        "latest_any_id": latest_any[0] if latest_any else None,
        "seam_ids": sorted(set(canon_ids) - set(dated)),
    }


def main(argv=None) -> int:
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
        "sql": sql_vectors(fa, ar),
    }
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT, help="مسیرِ نوشتن (گاردِ تازگیِ طلایی)")
    args = ap.parse_args(argv)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    total = sum(len(v) for k, v in out.items() if k != "sql")
    total += sum(len(v) for v in out["sql"].values() if isinstance(v, list))
    print("golden cases:", total, "->", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
