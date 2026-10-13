# -*- coding: utf-8 -*-
"""tools/codal_ledger_repair.py — آزادکردنِ «پایۀ گم‌شده درِ پاک‌سازیِ قدیم».

چرا این ابزار متولد شد (بندِ ۸ مأموریت، 1405-07-24). `tools/codal_coverage_audit.py`
رویِ `market.db` نشان داد ۷۳۵ اطلاعیه هست که

  * صورتِ مالیِ **غیرتلفیقی** بوده‌اند (عنوانِ خودِ اطلاعیه، نه ستون)،
  * ردیفشان درِ دورۀ پاک‌سازیِ قدیم (حذفِ فیزیکیِ «بازندۀ هم‌دوره») رفته،
  * تنها بازماندۀ همان (نماد، دوره) **تلفیقی** است،
  * و `codal_extracted.ok` برایِ آن اطلاعیه هنوز ۱ است ⇒ هیچ اجرایِ تازهای
    هرگز دوباره سراغشان نمی‌رود. یعنی آن دوره برایِ همیشه با مبنایِ تلفیقی
    قفل شده — درحالی‌که بندِ P-2 جزوه، محدودیتِ «غیرتلفیقی» را دقیقاً رویِ همان
    شاخصِ سه‌سالۀ EPS (و مرجعِ حاشیه) می‌گذارد.

تفکیکِ شمارش (سنجیده رویِ همین بانک، `market.db` فقط‌خواندنی، 1405-07-24):

  * **۱۸۵** اطلاعیه دوره‌شان «سالانۀ سالِ مالی» است (از خودِ عنوان)، رویِ **۱۱۵**
    نماد — و `FT.reference_annual` امروز برایِ **۷۷** از آن ۱۱۵ نماد ردیفِ
    تلفیقی را برمی‌دارد (۳۸ نماد از راهِ دورۀ دیگری هنوز ردیفِ غیرتلفیقی پیدا
    می‌کنند).
  * **۵۵۰** اطلاعیه میاندورهای‌اند (۶ یا ۹ ماهه، یا «نصفِ دومِ سال» که تاریخش
    درِ اسفند می‌نشیند). پنج شاخص جزوه صورتهایِ میاندورهای را مرجعِ سالانه
    نمی‌گیرند، پس پیش‌فرضِ این ابزار آن‌ها را **نمی‌دارد**؛ با `--all-periods`
    دیده می‌شوند.

کارِ این ابزار فقط و فقط **برگرداندنِ همان نشانک** است (`ok → 0`) تا اجرایِ
تازۀ `--mode full` دقیقاً همان گزارش‌ها را دوباره بکارد. هیچ ردیفی حذف نمی‌شود،
هیچ عددی نوشته نمی‌شود، هیچ درخواستِ شبکه‌ای درِ این فایل نیست. (پیش‌نیاش همین
امروز برآورده شد: `dev/codal_fts_updater.save_annual` از ۲۰۲۶-۰۹-۲۱ هر سالانه را
با `OperationalError` رد می‌کرد و خطا را «استخراج ناموفق» چاپ می‌کرد؛ تا آن
مسیر درست نشود، هر دوبارۀ بکاردی بی‌نتیجه است.)

    usage: PYTHONIOENCODING=utf-8 python tools/codal_ledger_repair.py [--db market.db]
                          [--apply] [--all-periods] [--selftest]

پیش‌فرض **dry-run** است و دیتابیس را `mode=ro` باز می‌کند؛ `--apply` تنها رویِ
مسیری می‌نویسد که صریح داده‌اید — و آن باید اول کپیِ آزمون باشد.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import codal_periods as CP                    # noqa: E402
import fts_engine as FE                       # noqa: E402
import symbol_identity as SI                  # noqa: E402


def fs_title_sql(alias=""):
    """پرانتز الزامی است: `AND` درِ SQLite بر `OR` تقدم دارد، پس بی‌پرانتز یکِ
    LIKE از فیلترِ کناری فرار می‌کند (سنجیده شد: ۹۸۵ در برابرِ ۹۸۰)."""
    col = (alias + "." if alias else "") + "title"
    return ("(%s LIKE '%%صورتهای مالی%%' OR %s LIKE '%%صورت‌های مالی%%')" % (col, col))


def is_annual_title(title):
    """آیا این عنوان «سالانۀ سالِ مالی» است؟ — از خودِ عنوان، نه از تقویم.

    چرا ماهِ تاریخ کافی نیست: «دورۀ ۶ ماهه منتهی به ۱۴۰۱/۱۲/۲۹» (نصفِ دومِ
    سالِ مالی ۳۰ تیر) هم درِ ماهِ ۱۲ می‌نشیند و با معیارِ تاریخ «سالانه» خوانده
    می‌شد (سنجیده: ۲۰۴ نامزد با معیارِ تاریخ در برابرِ ۱۸۵ با معیارِ عنوان).
    قاعده: `months_from_title` رقمِ «X ماهه» را می‌خواند ⇒ فقط ۱۲ سالانه است؛
    بی‌رقم، واژۀ «سال مالی» به‌شرطِ نبودِ «میاندوره» سالانه است.
    """
    mo = CP.months_from_title(title)
    if mo is not None:
        return mo == 12
    t = str(title or "")
    return ("سال مالی" in t) and ("میاندوره" not in t)


def candidates(conn, annual_only=True):
    """[(tracing_no, نماد، دوره، عنوانِ بازمانده] — غیرتلفیقیِ گم‌شده، مرجعِ قفل‌شده.

    «هیچ ردیفی درِ آن دوره نمانده» عمداً نامزد **نیست**: آن شکاف کارِ واکشی است
    (دوبارۀ بکاردی بی‌needِ نشانک)، نه قفلِ مرجع.
    """
    led = {r["tracing_no"]: r["ok"] for r in conn.execute(
        "SELECT tracing_no, ok FROM codal_extracted WHERE kind='fs'")}
    rows = conn.execute(
        "SELECT n.tracing_no tn, n.symbol sym, n.title title"
        " FROM codal_notices n LEFT JOIN financial_statements f"
        " ON f.tracing_no = n.tracing_no WHERE %s AND f.tracing_no IS NULL"
        % fs_title_sql("n")).fetchall()
    survivors = {}
    for sym, pe, title in conn.execute(
            "SELECT symbol, period_end, title FROM financial_statements"):
        k = SI.key(sym)
        if k:
            survivors.setdefault((k, str(pe or "").strip()), []).append(title or "")
    out = []
    for r in rows:
        try:
            tn = int(r["tn"])
        except (TypeError, ValueError):
            continue
        if led.get(tn) != 1 or FE._is_consolidated(r["title"]):
            continue
        pe, _src = CP.derive(None, r["title"])
        if annual_only and not is_annual_title(r["title"]):
            continue
        left = survivors.get((SI.key(r["sym"]), str(pe or "").strip())) or []
        if left and not any(not FE._is_consolidated(t) for t in left):
            out.append((tn, r["sym"], pe, max(left)))
    return sorted(out)


def consolidated_reference_count(conn, cands):
    """چند نماد از این‌ها امروز واقعاً مرجعِ سالانش به ردیفِ تلفیقی رأی می‌دهد."""
    FE.register_sql(conn)
    syms = sorted({SI.key(x[1]) for x in cands})
    cons = solo = none = 0
    for k in syms:
        ref = FE.reference_annual(conn, k, need="margin")
        if not ref:
            none += 1
            continue
        if FE._is_consolidated(str((ref or {}).get("title") or "")):
            cons += 1
        else:
            solo += 1
    return {"symbols_affected": len(syms), "reference_now_consolidated": cons,
            "reference_now_standalone": solo, "no_annual_reference": none}


def apply_repair(conn, tns):
    """فقط `ok=0` رویِ همان ردیفهایِ ledger؛ بقیۀ ستون‌ها دست‌نخورده."""
    conn.executemany("UPDATE codal_extracted SET ok=0"
                     " WHERE tracing_no=? AND kind='fs'", [(t,) for t in tns])
    conn.commit()
    return sum(1 for t in tns if conn.execute(
        "SELECT ok FROM codal_extracted WHERE tracing_no=? AND kind='fs'",
        (t,)).fetchone()[0] == 0)


def _fixture():
    mem = sqlite3.connect(":memory:")
    mem.row_factory = sqlite3.Row
    mem.execute("CREATE TABLE codal_notices (tracing_no TEXT, symbol TEXT, title TEXT)")
    mem.execute("CREATE TABLE financial_statements (tracing_no INTEGER, symbol TEXT,"
                " period_end TEXT, title TEXT)")
    mem.execute("CREATE TABLE codal_extracted (tracing_no INTEGER, kind TEXT,"
                " ok INTEGER, tried_at TEXT)")
    ANN_S = "صورت\u200cهای مالی سال مالی منتهی به ۱۴۰۰/۱۲/۲۹ (حسابرسی نشده)"
    ANN_C = "صورت\u200cهای مالی تلفیقی سال مالی منتهی به ۱۴۰۰/۱۲/۲۹ (حسابرسی شده)"
    MID_S = "اطلاعات و صورت\u200cهای مالی میاندوره\u200cای دوره ۶ ماهه منتهی به ۱۴۰۱/۰۶/۳۱"
    MID_C = "اطلاعات و صورت\u200cهای مالی میاندوره\u200cای تلفیقی دوره ۶ ماهه منتهی به ۱۴۰۱/۰۶/۳۱"
    OK_S = "صورت\u200cهای مالی سال مالی منتهی به ۱۴۰۲/۱۲/۲۹ (حسابرسی نشده)"
    # ۱) کاشته: سالانۀ غیرتلفیقیِ بی‌ردیف + بازماندۀ تلفیقی + نشانکِ ok=۱
    mem.execute("INSERT INTO codal_notices VALUES ('101','واحدآزمون',?)", (ANN_S,))
    mem.execute("INSERT INTO financial_statements VALUES (202,'واحدآزمون',"
                " '1400/12/29',?)", (ANN_C,))
    mem.execute("INSERT INTO codal_extracted VALUES (101,'fs',1,'t')")
    mem.execute("INSERT INTO codal_extracted VALUES (202,'fs',1,'t')")
    # ۲) کنترلِ منفیِ مقیاس: همان قفل، ولی میاندورهای ⇒ پیش‌فرض نباید بگیردش
    mem.execute("INSERT INTO codal_notices VALUES ('103','میاندوره',?)", (MID_S,))
    mem.execute("INSERT INTO financial_statements VALUES (204,'میاندوره',"
                " '1401/06/31',?)", (MID_C,))
    mem.execute("INSERT INTO codal_extracted VALUES (103,'fs',1,'t')")
    # ۲ب) کنترلِ «تاریخ گول‌زن»: نصفِ دومِ سالِ مالی، تاریخش درِ اسفند می‌نشیند
    # ولی عنوان «دوره ۶ ماهه» می‌گوید ⇒ با معیارِ عنوان سالانه **نیست** (با
    # معیارِ ماهِ تاریخ، ۱۹ موردِ این‌چنینی اشتباه نامزد می‌شدند).
    H2_S = MID_S.replace("۱۴۰۱/۰۶/۳۱", "۱۴۰۲/۱۲/۲۹")
    H2_C = MID_C.replace("۱۴۰۱/۰۶/۳۱", "۱۴۰۲/۱۲/۲۹")
    mem.execute("INSERT INTO codal_notices VALUES ('110','نصفدوم',?)", (H2_S,))
    mem.execute("INSERT INTO financial_statements VALUES (111,'نصفدوم',"
                " '1402/12/29',?)", (H2_C,))
    mem.execute("INSERT INTO codal_extracted VALUES (110,'fs',1,'t')")
    # ۳) کنترلِ منفی: بازمانده **غیرتلفیقی** است ⇒ چیزی گم نشده
    mem.execute("INSERT INTO codal_notices VALUES ('105','سالم',?)", (OK_S,))
    mem.execute("INSERT INTO financial_statements VALUES (106,'سالم',"
                " '1402/12/29',?)", (OK_S,))
    mem.execute("INSERT INTO codal_extracted VALUES (105,'fs',1,'t')")
    # ۴) کنترلِ منفی: خودِ اطلاعیه تلفیقی بوده ⇒ مرجعِ تلفیقی اشکال ندارد
    mem.execute("INSERT INTO codal_notices VALUES ('107','تلفیقی',?)", (ANN_C,))
    mem.execute("INSERT INTO financial_statements VALUES (108,'تلفیقی',"
                " '1400/12/29',?)", (ANN_C,))
    mem.execute("INSERT INTO codal_extracted VALUES (107,'fs',1,'t')")
    # ۵) کنترلِ منفی: ردیفِ خودش هست ⇒ اصلاً «گم‌شده» نیست
    mem.execute("INSERT INTO codal_notices VALUES ('109','دارد',?)", (ANN_S,))
    mem.execute("INSERT INTO financial_statements VALUES (109,'دارد',"
                " '1400/12/29',?)", (ANN_S,))
    mem.execute("INSERT INTO codal_extracted VALUES (109,'fs',1,'t')")
    return mem


def selftest() -> int:
    mem = _fixture()
    got = [t for (t, _s, _p, _l) in candidates(mem)]
    allp = [t for (t, _s, _p, _l) in candidates(mem, annual_only=False)]
    print("  candidates(annual) =", got, " candidates(all) =", allp)
    if got != [101] or allp != [101, 103, 110]:
        print("  SELFTEST FAIL — سنسور کور است، بیش از حد گیر می‌کند، یا تاریخ را "
              "به‌جای عنوان می‌خواند")
        return 1
    n = apply_repair(mem, got)
    again = [t for (t, _s, _p, _l) in candidates(mem)]
    ok101 = mem.execute("SELECT ok FROM codal_extracted WHERE tracing_no=101").fetchone()[0]
    untouched = mem.execute("SELECT ok FROM codal_extracted WHERE tracing_no=103").fetchone()[0]
    rows_left = mem.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0]
    print("  after apply: flipped=%s ok(101)=%s ok(103)=%s re-detected=%s fs_rows=%s"
          % (n, ok101, untouched, again, rows_left))
    if ok101 != 0 or again or untouched != 1 or rows_left != 6:
        print("  SELFTEST FAIL — تعمیر بی‌اثر است، بیش از حد نوشته، یا ردیفی را کم کرده")
        return 1
    print("  SELFTEST OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all-periods", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    path = os.path.abspath(a.db)
    conn = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
    conn.row_factory = sqlite3.Row
    cands = candidates(conn, annual_only=not a.all_periods)
    report = consolidated_reference_count(conn, cands)
    conn.close()
    print("نامزدِ تعمیر: %d اطلاعیه  |  %s"
          % (len(cands), " ".join("%s=%s" % kv for kv in report.items())))
    for tn, sym, pe, left in cands:
        print("  tn=%s  %s  %s  بازمانده: %s" % (tn, sym, pe, str(left)[:52]))
    if not cands or not a.apply:
        return 0
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    n = apply_repair(conn, [t for (t, _s, _p, _l) in cands])
    left = candidates(conn, annual_only=not a.all_periods)
    conn.close()
    print("اعمال شد: %d نشانک ← ok=0، بازمعرفی‌شده پس از تعمیر: %d" % (n, len(left)))
    return 0 if n == len(cands) and not left else 1


if __name__ == "__main__":
    raise SystemExit(main())
