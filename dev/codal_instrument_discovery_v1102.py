#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_instrument_discovery_v1102.py — گاردِ بندِ ۳: کشفِ ابزارِ تازه.

مأموریت می‌گوید «Universe داخلی را با منبع واقعی و معتبر TSETMC مقایسه کن» و
پنج چیز را از هم تشخیص بده: ابزارِ تازه، تغییرِ شناسه، نمادِ تغییرنام‌یافته،
ابزارِ غیرفعال، ابزارِ حذف‌شده. این گارد همان پنج را رویِ فیکچر می‌سنجد — و
چهار قیدی را که مأموریت گذاشته است:

  * هویت = `ins_code`ِ پایدار + نگاشتِ معتبرِ ناشر؛ نامِ نمایشی تنها مرجع نیست
  * حذفِ رقمِ انتهایی/فازی‌مچ/شباهتِ نام ⇒ اتصالِ خودکارِ قطعی ممنوع
  * صندوق/حقِ تقدم/اوراق مثلِ شرکتِ عملیاتی رفتار نمی‌کنند
  * هویتِ مبهم ثبت و **نگه داشته** می‌شود، نه متصل به شرکتِ مشابه

هیچ رأیِ بنیادی ساختگی ساخته نمی‌شود: ابزارِ بی‌صورتِ مالی `coverage='none'`
می‌گیرد و هیچ ردیفی درِ `financial_statements` نمی‌سازد.

بی‌شبکه و بی‌market.db — همه رویِ `:memory:`.

اجرا:  PYTHONIOENCODING=utf-8 python dev/codal_instrument_discovery_v1102.py
خروجی: «N passed / M failed»، exit 0 یا 1
"""
from __future__ import annotations

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import codal_fetcher as CF                    # noqa: E402
import codal_pipeline as PL                   # noqa: E402
import mstat_engine as M                      # noqa: E402
import symbol_identity as SI                  # noqa: E402

PASS = FAIL = 0
FS_TITLE = "صورت‌های مالی  سال مالی منتهی به ۱۴۰۵/۰۳/۳۱ (حسابرسی شده)"


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("PASS %s" % what)
    else:
        FAIL += 1
        print("FAIL %s%s" % (what, ("   ← " + str(detail)) if detail else ""))


def fresh_db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    CF.create_schema(c)
    CF.migrate_schema(c)
    # همان سیزده ستونِ `instruments`ِ کاری (`test_tsetmc._INST_COLS`)
    c.execute("CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, l_val18 TEXT,"
              " l_val30 TEXT, sector_code TEXT, sector_name TEXT, total_shares REAL,"
              " eps REAL, pe REAL, base_vol REAL, updated_at TEXT, paper_type INTEGER,"
              " isin TEXT, c_gr_val_cot REAL)")
    c.execute("CREATE TABLE market_watch (ins_code TEXT PRIMARY KEY, d_even TEXT)")
    c.execute("CREATE TABLE instrument_state (ins_code TEXT PRIMARY KEY,"
              " c_etaval TEXT, c_etaval_title TEXT)")
    return c


def add_inst(c, code, sym, name, paper=1, sector="فلزات", isin=None):
    c.execute("INSERT OR REPLACE INTO instruments (ins_code, l_val18, l_val30,"
              " sector_name, paper_type, isin) VALUES (?,?,?,?,?,?)",
              (code, sym, name, sector, paper, isin or ("C" + code)))


def on_board(c, code, d_even="1405/07/21"):
    c.execute("INSERT OR REPLACE INTO market_watch (ins_code, d_even) VALUES (?,?)",
              (code, d_even))


def ledger_row(c, code):
    r = c.execute("SELECT * FROM pipeline_instrument WHERE ins_code=?",
                  (code,)).fetchone()
    return dict(r) if r else None


def n_fs(c, sym):
    return int(c.execute("SELECT COUNT(*) FROM financial_statements WHERE symbol=?",
                         (sym,)).fetchone()[0])


def main() -> int:
    # ── ۱) ابزارِ تازه: شناسه + اطلاعاتِ رسمی + طبقه + پوشش ثبت می‌شود ──────
    c = fresh_db()
    add_inst(c, "1234", "فولاد", "فولاد مبارکه اصفهان", paper=1)
    on_board(c, "1234")
    t = PL.discover_instruments(c)
    ck(t["instr_scanned"] == 1 and t["instr_new"] == 1,
       "یکِ ابزارِ تازه درِ Universe دیده و «تازه» شمرده می‌شود", t)
    row = ledger_row(c, "1234")
    ck(row is not None and row["symbol"] == "فولاد"
       and row["name"] == "فولاد مبارکه اصفهان" and row["isin"] == "C1234",
       "شناسۀ پایدار + نامِ رسمی + ISIN درِ دفتر می‌مانند", row)
    ck(row["class"] == M.classify(1, "فولاد مبارکه اصفهان", "فولاد", "فلزات")[0]
       == "stock",
       "طبقه‌بندی از خودِ mstat_engine.classify است (نه پیشوندِ نام)", row["class"])
    ck(row["membership"] == PL.MEMBERSHIP_PRESENT and row["cycles_absent"] == 0,
       "عضویتِ فعال ثبت می‌شود", (row["membership"], row["cycles_absent"]))
    ck(row["coverage"] == "none" and row["identity"] == "no_publisher",
       "ابزارِ بی‌ردیفِ کدال: پوشش = none، هویت = بی‌ناشر (نه اتصالِ حدسی)",
       (row["coverage"], row["identity"]))
    ck(n_fs(c, "فولاد") == 0,
       "هیچ ردیفِ صورتِ مالیِ ساختگی برایِ ابزارِ تازه نوشته نمی‌شود",
       n_fs(c, "فولاد"))
    d = list(c.execute("SELECT symbol, axis FROM pipeline_dirty"))
    ck(any(r[0] == "فولاد" and r[1] == "5_industry" for r in d),
       "فیلترِ صنعت برایِ ابزارِ تازه علامتِ دوباره‌محاسبه می‌گیرد",
       [tuple(r) for r in d])

    # ── ۲) یدم‌پذیری: اجرایِ دوباره «تازه» نمی‌سازد و دفتر رشد نمی‌کند ──────
    SI.reset_cache(c)
    c.execute("DELETE FROM pipeline_dirty")
    t2 = PL.discover_instruments(c)
    ck(t2["instr_new"] == 0 and t2["ledger"] == 1,
       "چرخۀ دوم همان ابزار را تازه نمی‌شمارد (دفتر = یکِ سطر)", t2)
    row2 = ledger_row(c, "1234")
    ck(row2["first_seen_at"] == row["first_seen_at"],
       "first_seen_at با اجرایِ دوباره بازنویسی نمی‌شود (تاریخچۀ عضویت)",
       (row["first_seen_at"], row2["first_seen_at"]))
    ck(row2["flags"] == "",
       "پرچم‌هایِ رویداد فقط درِ چرخۀ واقعی می‌مانند (لاگِ بی‌رشد)", row2["flags"])
    ck(not list(c.execute("SELECT 1 FROM pipeline_dirty")),
       "و علامتِ تکراری برایِ نمادِ بی‌تغییری نوشته نمی‌شود")

    # ── ۳) تغییرِ نام: همان ابزار است، نه ابزارِ تازه ───────────────────────
    SI.reset_cache(c)
    c.execute("UPDATE instruments SET l_val30=? WHERE ins_code=?",
              ("فولاد مبارکۀ اصفهان (حجمِ تازه)", "1234"))
    t3 = PL.discover_instruments(c)
    row3 = ledger_row(c, "1234")
    ck(t3["instr_renamed"] == 1 and t3["instr_new"] == 0 and t3["ledger"] == 1,
       "تغییرِ نامِ نمایشی «تازه» نمی‌شمارد؛ رویداد renamed می‌گیرد", t3)
    ck(row3["prev_name"] == "فولاد مبارکه اصفهان" and
       row3["name"] == "فولاد مبارکۀ اصفهان (حجمِ تازه)",
       "نامِ پیشین برایِ ردیابی حفظ می‌شود", (row3["prev_name"], row3["name"]))

    # ── ۴) تغییرِ شناسه: دو ins_code زیرِ یکِ نماد ⇒ مبهم، بی‌اتصال خودکار ──
    SI.reset_cache(c)
    add_inst(c, "5678", "خودرو", "خودرو سازان (سالِ تازه)", paper=1)
    add_inst(c, "9012", "خودرو", "خودروسازان", paper=1)
    on_board(c, "5678")
    on_board(c, "9012")
    t4 = PL.discover_instruments(c)
    r_a, r_b = ledger_row(c, "5678"), ledger_row(c, "9012")
    ck(t4["instr_id_changed"] == 2,
       "هر دو سطرِ هم‌نماد پرچمِ تغییرِ شناسه می‌گیرند", t4)
    ck(r_a["identity"] == "ambiguous" and r_b["identity"] == "ambiguous"
       and r_a["identity_note"] == "more_than_one_ins_code",
       "هویتِ مبهم **ثبت** می‌شود و برایِ تصمیم معتبر نگه داشته می‌شود",
       (r_a["identity"], r_a["identity_note"]))
    ck(r_a["ins_code"] != r_b["ins_code"] and t4["ledger"] == 3,
       "هیچ‌کدام درِ دیگری ادغام نمی‌شود (بی‌اتصالِ خودکارِ قطعی)",
       (r_a["ins_code"], r_b["ins_code"], t4["ledger"]))

    # ── ۵) ابزارِ غیرفعال در برابر حذف‌شده از Universe ──────────────────────
    SI.reset_cache(c)
    c.execute("DELETE FROM market_watch WHERE ins_code='1234'")
    t5 = PL.discover_instruments(c)
    r5 = ledger_row(c, "1234")
    ck(t5["instr_deactivated"] == 1 and r5["membership"] == PL.MEMBERSHIP_PRESENT,
       "از تابلو بیرون‌رفتن ولی هنوز درِ `instruments`: غیرفعال، نه حذف‌شده",
       (t5, r5["membership"], r5["flags"]))
    ck("deactivated" in (r5["flags"] or ""), "رویدادِ غیرفعال‌شدن برچسب می‌خورد",
       r5["flags"])
    # حذفِ واقعی: سطر از خودِ Universe بیرون می‌رود
    SI.reset_cache(c)
    c.execute("DELETE FROM instruments WHERE ins_code='1234'")
    t6 = PL.discover_instruments(c)
    r6 = ledger_row(c, "1234")
    ck(t6["instr_absent"] == 1 and t6["instr_removed"] == 0 and
       r6["membership"] == PL.MEMBERSHIP_ABSENT and r6["cycles_absent"] == 1,
       "غیبتِ یکِ چرخه «حذف» اعلام نمی‌شود (سنسور ممکن است یک‌بار ننویسد)",
       (t6, r6["membership"], r6["cycles_absent"]))
    SI.reset_cache(c)
    t7 = PL.discover_instruments(c)
    r7 = ledger_row(c, "1234")
    ck(t7["instr_removed"] == 1 and r7["membership"] == PL.MEMBERSHIP_REMOVED,
       "غیبتِ دو چرخۀ پی‌درپی = حذف‌شده از Universe",
       (t7["instr_removed"], r7["membership"]))
    ck(t7["ledger"] == 3,
       "سطرِ حذف‌شده پاک نمی‌شود (ردیابی می‌ماند) و دفتر بی‌رشد نمی‌شود",
       t7["ledger"])
    # بازگشت
    SI.reset_cache(c)
    add_inst(c, "1234", "فولاد", "فولاد مبارکه اصفهان", paper=1)
    on_board(c, "1234")
    t8 = PL.discover_instruments(c)
    r8 = ledger_row(c, "1234")
    ck(r8["membership"] == PL.MEMBERSHIP_PRESENT and r8["cycles_absent"] == 0 and
       "reactivated" in (r8["flags"] or ""),
       "بازگشتِ ابزارِ غایب دوباره فعال شمرده و شمارندۀ غیبت صفر می‌شود",
       (r8["membership"], r8["cycles_absent"], r8["flags"]))
    ck(t8["instr_new"] == 0 and r8["first_seen_at"] == row["first_seen_at"],
       "بازگشت «تازه‌شدن» نیست و تاریخچۀ عضویت از اول نمی‌شود", t8)

    # ── ۶) صندوق/حقِ تقدم/اوراق مثلِ شرکتِ عملیاتی نیستند ──────────────────
    c2 = fresh_db()
    add_inst(c2, "7001", "داریا", "صندوق سرمایه گذاری قابل معامله (ETF)", paper=8)
    add_inst(c2, "7002", "حقا", "حق تقدم شرکت فولاد", paper=2)
    add_inst(c2, "7003", "اختیار", "اختیار خرید خودرو", paper=4)
    add_inst(c2, "7004", "ولنز", "اوراق مشارکت", paper=4)
    for k in ("7001", "7002", "7003", "7004"):
        on_board(c2, k)
    t9 = PL.discover_instruments(c2)
    ck(t9["instr_not_eligible"] >= 3,
       "غیرِسهامی درِ مسیرِ پنج شاخص مشمول نمی‌شوند (not_eligible)", t9)
    for k, sym in (("7001", "داریا"), ("7002", "حقا")):
        r = ledger_row(c2, k)
        ck(r["identity"] == "not_eligible" and r["class"] != "stock",
           "طبقۀ «%s» از خودِ classify می‌آید، نه از شباهتِ نام" % sym,
           (r["class"], r["kind"], r["identity"]))
    ck(not list(c2.execute("SELECT 1 FROM pipeline_dirty WHERE symbol IN"
                          " ('داریا','حقا')")),
       "و برایِ آن‌ها علامتِ محاسبۀ بنیادی نوشته نمی‌شود")
    # سهامِ مجاز باید مشمول شود (کنترلِ مثبتِ همان شرط)
    add_inst(c2, "7005", "شهاب", "صنایع شهاب (سهامی عام)", paper=1)
    on_board(c2, "7005")
    SI.reset_cache(c2)
    t9b = PL.discover_instruments(c2)
    ck(ledger_row(c2, "7005")["class"] == "stock",
       "سهامی عام درِ همان قاعده مشمول است", ledger_row(c2, "7005")["class"])

    # ── ۷) نبودِ سنسور ⇒ ادعایِ غیرفعالیت ساخته نمی‌شود (کنترلِ کوری) ───────
    c3 = sqlite3.connect(":memory:")
    c3.row_factory = sqlite3.Row
    CF.create_schema(c3)
    CF.migrate_schema(c3)
    c3.execute("CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, l_val18 TEXT,"
               " l_val30 TEXT, sector_name TEXT, paper_type INTEGER, isin TEXT)")
    c3.execute("INSERT INTO instruments (ins_code, l_val18, l_val30, sector_name,"
               " paper_type, isin) VALUES ('8001','آوا','آواپارس','شیمی',1,'C8001')")
    snap = PL.instrument_snapshot(c3)
    ck(len(snap) == 1 and snap[0]["on_board"] is None and
       snap[0]["state"] is None,
       "بانکِ بی‌`market_watch`: حضور نامعلوم است، نه «غیرفعال»", snap)
    t10 = PL.discover_instruments(c3, snapshot=snap)
    ck(t10["instr_deactivated"] == 0 and t10["instr_new"] == 1,
       "هیچِ سنسور ⇒ هیچِ ادعایِ غیرفعالی (دامِ کوریِ سنسور)", t10)
    ck(PL.instrument_snapshot(c3)[0]["isin"] == "C8001",
       "ستون‌هایِ موجود خوانده می‌شوند (گزینش با PRAGMA، نه حدس)")
    c4 = sqlite3.connect(":memory:")
    c4.row_factory = sqlite3.Row
    CF.create_schema(c4)
    CF.migrate_schema(c4)
    c4.execute("CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, l_val18 TEXT,"
               " l_val30 TEXT, paper_type INTEGER)")
    c4.execute("INSERT INTO instruments (ins_code, l_val18, l_val30, paper_type)"
               " VALUES ('8002','بهناز','بهناز',1)")
    s4 = PL.instrument_snapshot(c4)
    ck(s4 and s4[0]["isin"] is None and s4[0]["sector"] is None,
       "ستونِ نبود ⇒ مقدارِ ساختگی نمی‌گیرد (NULL می‌ماند)", s4)

    # ── ۸) گزارش‌هایِ موجودِ ابزارِ تازه کشف و پردازش می‌شوند ───────────────
    c5 = fresh_db()
    add_inst(c5, "9100", "نوپا", "کاغذ و سلولوز نوپا", paper=1)
    on_board(c5, "9100")
    c5.execute("INSERT INTO codal_notices (tracing_no, symbol, company_name, title,"
               " letter_code, publish_date, sent_date, url, fetched_at, pdf_url,"
               " excel_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (12345, "نوپا", "نوپا", FS_TITLE, "1", "1405/07/22 10:00:00", "",
                "https://codal.ir/L/Detail/12345", "2026-10-14 00:00:00", "", ""))
    SI.reset_cache(c5)

    def fs_scrape(n):
        vals = {k: None for k in CF.FS_KEYS}
        vals.update({"revenue": 500.0, "gross_profit": 200.0, "net_profit": 90.0,
                     "basic_eps": 12.0})
        pe, _src = CP_derive(n[3])
        unit = "کليه مبالغ به ميليون ريال است"
        row = ((n[0], n[1], n[2], n[3], "Financial Statements", 12, pe, n[5])
               + tuple(vals.get(k) for k in CF.FS_KEYS)
               + (unit, n[7], PL.now_s()) + CF.fs_derived(n[3], pe, unit, 0))
        return "fs", row, "ok"

    res = PL.run_cycle(c5, "w-inst", scrape=fs_scrape, budget=4,
                       instruments=None)
    ck(res["enqueued"] == 1 and res["done"] == 1,
       "اطلاعیهٔ موجودِ ابزارِ تازه درِ همان چرخه پردازش می‌شود", res)
    ck(n_fs(c5, "نوپا") == 1, "یکِ ردیفِ صورتِ مالیِ واقعی (نه ساختگی) نوشته شد",
       n_fs(c5, "نوپا"))
    SI.reset_cache(c5)
    t11 = PL.discover_instruments(c5)
    r11 = ledger_row(c5, "9100")
    ck(r11["coverage"] == "fs" and r11["identity"] == "linked",
       "وضعیتِ پوششِ بنیادی پس از استخراج تازه می‌شود", (r11["coverage"],
                                                         r11["identity"]))
    # و چرخۀ کاملِ پیش‌فرض هم همین ابزار را درِ شمارنده‌ها می‌آورد
    SI.reset_cache(c5)
    res2 = PL.run_cycle(c5, "w-auto", scrape=fs_scrape, budget=4)
    ck(res2["instruments"].get("instr_scanned") == 1,
       "چرخۀ پیش‌فرض هم Universe را می‌سنجد (زمان‌بندیِ دستی لازم نیست)",
       res2["instruments"])

    # ── ۹) شمارنده‌ها و سلامت: رویدادها درِ گزارشِ چرخه و UI خوانده می‌شوند ──
    cur = c5.execute("SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    cols = [d[0] for d in cur.description]
    runs = dict(zip(cols, tuple(row)))
    ck(runs.get("instr_scanned") == 1,
       "شمارندۀ Universe درِ `pipeline_runs` می‌نشیند (از جدول، نه حافظه)",
       runs.get("instr_scanned"))
    h = PL.health(c5)
    ck({"ledger", "present", "absent", "removed", "ambiguous", "no_publisher",
        "no_fundamental"} <= set(h.get("instruments") or {}),
       "گزارشِ سلامت شمارشِ ابزار را با همان تفکیک می‌دهد", h.get("instruments"))
    ck(h["instruments"]["no_fundamental"] == 0,
       "ابزارِ دارایِ پوشش درِ شمارشِ «بی‌داده» نمی‌نشیند", h["instruments"])

    print("\n%d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


def CP_derive(title):
    """دورۀ canonical از خودِ عنوان (`codal_periods.derive` بی‌datasource)."""
    import codal_periods as _CP
    return _CP.derive(None, title)


if __name__ == "__main__":
    sys.exit(main())
