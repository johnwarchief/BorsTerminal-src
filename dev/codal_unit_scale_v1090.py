#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_unit_scale_v1090.py — گاردِ «واحدِ پول»: یکِ تعریف، مقیاسِ هر ردیف از خودِ ردیف.

چرا (مرحلۀ ۴ مأموریت بنیادی، ۱۴۰۵-۰۷-۲۳): ادعایِ «این عدد میلیون ریال است» چهار
جا مستقل نوشته شده بود و **هیچ‌کدام به خودِ ردیف نگاه نمی‌کرد**:
`fts_engine.MRL_TO_RIAL = 1e6` (دو مصرف)، `api/fundamental.MRL_TO_RIAL = 1e6`
(مصرفِ سوم)، `normalize_mrl_to_btom` (`÷ 10_000`)، و `_classify_unit`ِ جدا درِ
واکشی. ستونِ `unit_norm` درِ بانک پر می‌شد ولی درِ هیچ کوئریِ خوانده نمی‌شد —
یعنی ۲۸۳ ردیفِ بی‌واحد (۱۲۶ نماد) با همان ضریبِ 1e6 به ریال می‌رفتند و بر ارزشِ
بازار تقسیم می‌شدند. سنجشِ همین بانک (`tools/codal_unit_blast.py`): ۲۵ ردیفِ
مرجعِ بی‌واحد، و ۵ نماد که عددِ شاخص ۴‌شان فقط از آن فرضِ بی‌شاهد می‌آمد.

قاعده‌ای که این گارد می‌کارد:
  ۱ مقیاس از `codal_units.SCALES` و از `unit_norm`ِ **همان ردیف** خوانده می‌شود.
  ۲ «بی‌واحد» جایگزینِ صفر یا حدسِ 1e6 نمی‌شود: رأیِ وابسته به مقیاس **داده
    نمی‌شود** و درِ رابط اعلام می‌شود (`unit_unverified`).
  ۳ نسبت‌های بی‌مقیاس (رشد، حاشیۀ سود) از این قاعده متأثر نمی‌شوند.
  ۴ «میلیون تومان» عمداً شناخته نمی‌شود (fail-closed) — نه 1e5، نه 1e6.
  ۵ نوشتن از `classify` می‌گذرد و خواندن از `PRESENT_SQL`/`is_valid` — یکِ مجموعه.

هر بند با کنترلِ منفی ثابت می‌شود (سنسور کور نباشد): یا واگردِ آن بند، یا
همان داده با واحدِ اعلام‌شده در برابرِ بی‌واحد.

اجرا:  python dev/codal_unit_scale_v1090.py     (خروج ۰ = سبز)
"""
import io
import os
import re
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import codal_fetcher as CF                     # noqa: E402
import codal_units as CU                       # noqa: E402
import fts_engine as FE                        # noqa: E402

PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s   %s" % (label, extra))


def fs_row(tracing_no, symbol, unit_norm, revenue=1000.0, gross=400.0, eps=2.0,
           title=None, period_end="1404/12/29", pm=12):
    """ردیفِ موقعیتی از رویِ **نامِ ستون** (همان الگوی گاردِ CA-2)."""
    t = title or ("صورت‌های مالی  سال مالی منتهی به %s (حسابرسی شده)" % period_end)
    vals = {"tracing_no": tracing_no, "symbol": symbol, "company_name": "شرکت آزمون " + symbol,
            "title": t, "report_kind": "Financial Statements", "period_months": pm,
            "period_end": period_end, "publish_date": "1405/01/10", "revenue": revenue,
            "gross_profit": gross, "operating_profit": gross, "net_profit": 300.0,
            "total_assets": 9000.0, "total_liabilities": None, "total_equity": 5000.0,
            "capital": 4000.0, "retained_earnings": None, "basic_eps": eps,
            "unit": None, "url": "https://codal.ir/%d" % tracing_no,
            "fetched_at": "2026-10-13T00:00:00",
            "is_audited": 1, "is_consolidated": 0,
            "fiscal_year": period_end[:4], "unit_norm": unit_norm}
    return [vals.get(c) for c in CF.FS_COLS]


class Bank:
    def __init__(self, rows):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        c = sqlite3.connect(self.path)
        CF.create_schema(c)
        CF.migrate_schema(c)
        c.executemany(CF.FS_UPSERT, rows)
        # `instruments` لازم نیست: مسیرهایِ واحد (fs_amount_mrl / annualize_rows /
        # annualized_sales) از `financial_statements` و `monthly_sales` می‌خوانند.
        c.executemany("INSERT OR REPLACE INTO monthly_sales (tracing_no, symbol, title, "
                      "period_end, year, month, monthly_revenue, ytd_revenue) "
                      "VALUES (?,?,?,?,?,?,?,?)", [
                          (7001, "واحدآزمون", "گزارش فعالیت ماهانه",
                           "1405/06/31", 1405, 6, 100.0, 600.0),
                          # نمادِ بی‌واحد هم گزارشِ ماهانه دارد: آن‌وقت مسیرِ کارت
                          # عدد می‌سازد و پرچمِ «راستی‌آزمایی‌نشده» درِ همان dict دیده
                          # می‌شود. بی‌این annualize_rows به {} می‌افتاد و چکِ U8ب
                          # بی‌معنا سبز می‌شد (کنترلِ کورنبودنِ خودِ چک).
                          (7002, "بی‌واحدآزمون", "گزارش فعالیت ماهانه",
                           "1405/06/31", 1405, 6, 100.0, 600.0),
                      ])
        c.commit()
        c.row_factory = sqlite3.Row
        FE.register_sql(c)
        self.conn = c

    def close(self):
        self.conn.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass


def main() -> int:
    # ── ۱) fail-closed بودنِ تشخیص ─────────────────────────────────────────
    ck(CU.classify("کليه مبالغ به ميليون ريال است") == "mrl", "U1 نوشتارِ عربیِ میلیون ریال")
    ck(CU.classify("کلیه‌ی مبالغ به میلیون ریال است") == "mrl", "U1ب نیم‌فاصله مقیاس را نمی‌شکند")
    ck(CU.classify("مبالغ به میلیارد تومان می‌باشد") == "btl", "U1پ میلیارد تومان = btl")
    ck(CU.classify("مبالغ به میلیون تومان") is None,
       "U1ت «میلیون تومان» عمداً شناخته نمی‌شود (fail-closed)", CU.classify("میلیون تومان"))
    ck(CU.classify(None) is None and CU.classify("") is None, "U1ث هیچ → بی‌واحد")

    # ── ۲) مقیاس از خودِ ردیف، و «بی‌واحد» هیچ‌وقت صفر نیست ────────────────
    ck(CU.to_rial(2.0, "mrl") == 2_000_000.0, "U2 میلیون ریال → ×1e6")
    ck(CU.to_rial(2.0, "btl") == 20_000_000_000.0, "U2ب میلیارد تومان → ×1e10")
    ck(CU.to_rial(2.0, None) is None, "U2پ بی‌واحد → None (نه صفر، نه ×1e6)")
    ck(CU.to_mrl(1.0, "btl") == 10_000.0, "U2ت مبناىِ داخلی: میلیارد تومان → 1e4 میلیون ریال")

    # ── ۳) تنها یکِ تعریفِ ضریب درِ کلِ مخزن ───────────────────────────────
    ck(FE.MRL_TO_RIAL == CU.SCALES["mrl"], "U3 fts_engine دیگر ضریبِ خودش را ندارد")
    ck(abs(FE.MRL_TO_BTM_FACTOR - CU.SCALES["mrl"] / CU.RIAL_PER_BTM) < 1e-18,
       "U3ب ضریبِ میلیارد تومان از همان جدول می‌آید")
    ck(FE.normalize_mrl_to_btom(10_000.0) == 1.0, "U3پ قاعدۀ جزوه (حذفِ ۴ رقم) برقرار است")
    src_fe = io.open(os.path.join(ROOT, "fts_engine.py"), encoding="utf-8").read()
    src_api = io.open(os.path.join(ROOT, "api", "fundamental.py"), encoding="utf-8").read()
    lit_fe = re.findall(r"MRL_TO_RIAL\s*=\s*[\d_.eE+-]+", src_fe)
    lit_api = re.findall(r"(?:MRL_TO_RIAL|BT_FACTOR)\s*=\s*[\d_.eE+-]+", src_api)
    ck(not lit_fe and not lit_api,
       "U3ت هیچ ثابتِ مقیاسِ عددیِ دیگری ننشسته (هر دو از codal_units)",
       "fts=%s api=%s" % (lit_fe, lit_api))
    # کنترلِ منفی: اگر روزی ضریبِ محلی برگردد، همین چک قرمز می‌شود
    fake = src_fe.replace("MRL_TO_RIAL = CU.SCALES[\"mrl\"]", "MRL_TO_RIAL = 1e6", 1)
    ck(fake != src_fe and re.findall(r"MRL_TO_RIAL\s*=\s*[\d_.eE+-]+", fake),
       "U3ر سنسورِ ثابتِ مقیاس کور نیست (بازگشتِ 1e6 را می‌بیند)")

    # ── ۴) نوشتن و خواندن یکِ مجموعه ──────────────────────────────────────
    ck(CF._classify_unit("مبالغ به میلیارد تومان") == "btl"
       and CF._classify_unit("مبالغ به میلیون تومان") is None,
       "U4 نویسنده از همان `classify` می‌گذرد")
    body = io.open(os.path.join(ROOT, "codal_fetcher.py"), encoding="utf-8").read()
    fn = body[body.index("def _classify_unit"):]
    fn = fn[:fn.index("\ndef ")]
    ck("CU.classify" in fn and "میلیارد" not in fn,
       "U4ب `_classify_unit` دیگر شرطِ دومِ خودش را ندارد", fn[:60])

    # ── ۵) شرطِ SQL و شرطِ پایتون قرینۀ هم ────────────────────────────────
    b = Bank([fs_row(9001, "واحدآزمون", "mrl"), fs_row(9002, "بی‌واحدآزمون", None),
              fs_row(9003, "تلفیقیآزمون", "btl", revenue=5.0, gross=2.0),
              # بی‌واحد **و** بی‌گزارشِ ماهانه: تنها مسیرِ باقی‌مانده، فروشِ صورتِ
              # مالی است و آن هم مقیاسش را از هیچ منبعی نگرفته → شاخص ۴ باید
              # «قابل محاسبه نبود» بدهد، نه عددِ ×1e6ِ حدسی.
              fs_row(9004, "تهیآزمون", None)])
    try:
        rows = b.conn.execute("SELECT symbol, unit_norm FROM financial_statements").fetchall()
        py_missing = {r["symbol"] for r in rows if CU.is_missing(r["unit_norm"])}
        sql_missing = {r[0] for r in b.conn.execute(
            "SELECT symbol FROM financial_statements WHERE " + CU.MISSING_SQL)}
        nil_set = {"بی‌واحدآزمون", "تهیآزمون"}
        ck(py_missing == sql_missing == nil_set,
           "U5 MISSING_SQL و is_missing یکِ مجموعه را می‌دهند", (py_missing, sql_missing))
        present = {r[0] for r in b.conn.execute(
            "SELECT symbol FROM financial_statements WHERE " + CU.PRESENT_SQL)}
        ck(present == {"واحدآزمون", "تلفیقیآزمون"}, "U5ب PRESENT_SQL نقیضِ دقیق است")
        counts = CU.unit_counts(b.conn)
        ck(counts["financial_statements"] == 2 and counts["symbols_financial_statements"] == 2,
           "U5پ شمارشِ یگانۀ بی‌واحد (یکِ کوئری، نه دو تا)", counts)

        # ── ۶) fs_amount_mrl: مقیاسِ ردیف، نه فرضِ ماژول ──────────────────
        ref_mrl = FE.reference_annual(b.conn, "واحدآزمون")
        ref_nil = FE.reference_annual(b.conn, "بی‌واحدآزمون")
        ref_btl = FE.reference_annual(b.conn, "تلفیقیآزمون")
        ck(ref_mrl.get("unit_valid") is True and FE.fs_amount_mrl(ref_mrl) == 1000.0,
           "U6 ردیفِ mrl بدونِ تغییرِ مقیاس به مبنایِ داخلی می‌رسد")
        ck(FE.fs_amount_mrl(ref_nil) is None, "U6ب ردیفِ بی‌واحد → None (بی‌ضریبِ حدسی)")
        ck(FE.fs_amount_mrl(ref_btl) == 50_000.0,
           "U6پ ردیفِ میلیارد‌تومانی ×1e4 می‌شود (نه ×1)", FE.fs_amount_mrl(ref_btl))

        # ── ۷) رأیِ وابسته به مقیاس بی‌شاهد داده نمی‌شود ──────────────────
        core_known = FE.annualize_rows([], 1000.0, op_basis=True, fs_unit_known=True)
        core_nil = FE.annualize_rows([], 1000.0, op_basis=True, fs_unit_known=False)
        ck(core_known.get("annual_sales_mrl") == 1000.0 and not core_known.get("unit_unverified"),
           "U7 با شاهدِ واحد، منطقۀ درآمدِ عملیاتی کار می‌کند")
        ck(core_nil == {}, "U7ب بی‌شاهد، همان عدد رأی نمی‌سازد (هیچ‌وقت صفرِ ساختگی)", core_nil)
        monthly = [[1405, 6, 100.0, 600.0]]
        g_nil = FE.annualize_rows(monthly, 1000.0, fs_unit_known=False)
        g_known = FE.annualize_rows(monthly, 1000.0, fs_unit_known=True)
        ck(g_nil.get("unit_unverified") is True and g_nil.get("reconciled") is False,
           "U7پ گیتِ واحد بی‌شاهد «اجرا نشد» اعلام می‌شود", g_nil)
        ck(g_known.get("unit_unverified") is False and g_known.get("reconciled") is True,
           "U7ت با شاهد، همان ردیف راستی‌آزمایی‌شده می‌ماند (کنترلِ کورنبودنِ سنسور)")

        # ── ۸) شاخص ۴ رویِ ردیفِ بی‌واحد: نه عدد، نه PASS ─────────────────
        # «تهیآزمون» نه واحد دارد نه گزارشِ ماهانه؛ تنها عددِ ممکن از فرضِ
        # مقیاس می‌آمد. قراردادِ بندِ ۲: آن فرض نوشته نمی‌شود.
        ref_nil2 = FE.reference_annual(b.conn, "تهیآزمون")
        s_nil = FE.sales_to_marketcap(b.conn, "تهیآزمون", 1_000_000_000_000.0,
                                      annual=FE.annualized_sales(b.conn, "تهیآزمون",
                                                                 ref=ref_nil2))
        ck(s_nil is None, "U8 شاخص ۴ بی‌شاهد هیچ عددی تولید نمی‌کند", s_nil)
        s_mrl = FE.sales_to_marketcap(b.conn, "تهیآزمون", 1_000_000_000_000.0,
                                      annual={"annual_sales_mrl": 1000.0,
                                              "annual_sales_bt": 0.1, "basis": "mrl",
                                              "months_used": 12})
        ck(isinstance(s_mrl, dict) and s_mrl.get("sales_to_mcap") is not None,
           "U8أ کنترلِ همان چک: با مبنایِ اعلام‌شده عدد ساخته می‌شود (سنسور کور نیست)", s_mrl)
        a_nil = FE.annualized_sales(b.conn, "بی‌واحدآزمون", ref=ref_nil)
        a_mrl = FE.annualized_sales(b.conn, "واحدآزمون", ref=ref_mrl)
        ck((a_nil or {}).get("unit_unverified") is True
           and (a_mrl or {}).get("unit_unverified") is False,
           "U8ب پرچمِ راستی‌آزمایی‌نشدن درِ همان دیکشنریِ کارت است",
           "nil=%s mrl=%s" % ((a_nil or {}).get("unit_unverified"),
                              (a_mrl or {}).get("unit_unverified")))
        ck((a_nil or {}).get("fs_unit") is None and (a_mrl or {}).get("fs_unit") == "mrl",
           "U8ث خودِ واحد هم درِ ردپا می‌آید (منبع، نه حدس)")
    finally:
        b.close()

    # ── ۹) سرشماریِ واقعی رویِ بانکِ کاری، با قرینِ بی‌واحد ────────────────
    prod = os.path.join(ROOT, "market.db")
    if os.path.exists(prod):
        c = sqlite3.connect("file:%s?mode=ro" % prod.replace("\\", "/"), uri=True)
        c.row_factory = sqlite3.Row
        FE.register_sql(c)
        n_rows, n_syms = c.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM "
                                   "financial_statements WHERE " + CU.MISSING_SQL).fetchone()
        ck(n_rows > 0, "U9 بانکِ کاری ردیفِ بی‌واحد دارد (سنسور رویِ دادهٔ real هم دو پا دارد)",
           (n_rows, n_syms))
        # نوشتارهایِ خامِ واحد درِ بانک ده‌تا بیشتر نیستند؛ مقایسه با خودِ
        # `classify` درِ پایتون می‌شود. LIKEِ SQL «ي» عربی و نیم‌فاصله را نمی‌
        # شناسد و ۲۸۱۵ دعوایِ جعلی می‌ساخت — قرینۀ همین چک، بندهایِ U1 است.
        pairs = c.execute("SELECT unit, unit_norm, COUNT(*) n FROM financial_"
                          "statements GROUP BY 1,2").fetchall()
        bad = [(str(r["unit"])[:26], r["unit_norm"], r["n"]) for r in pairs
               if r["unit"] is not None and str(r["unit"]).strip()
               and CU.classify(r["unit"]) != r["unit_norm"]]
        ck(not bad, "U9ب نوشتارِ خامِ واحد با unit_normِ همان ردیف می‌خواند", bad[:3])
        sheet_only = c.execute("SELECT COUNT(*) FROM financial_statements WHERE "
                               "(unit IS NULL OR trim(unit)='') AND " + CU.PRESENT_SQL).fetchone()[0]
        ck(CU.provenance(None, "mrl") == "sheet" and CU.provenance("x", "mrl") == "notice",
           "U9پ منشأِ واحد (نامه در برابرِ شیت) تفکیک می‌شود", sheet_only)
        # کنترلِ واقعیِ «بی‌شاهد رأی نمی‌دهد»: یکِ نمادِ مرجعِ بی‌واحد پیدا کن
        nil = [r["symbol"] for r in c.execute(
            "SELECT symbol FROM financial_statements WHERE unit_norm IS NULL "
            "GROUP BY symbol ORDER BY MAX(CAST(COALESCE(revenue,0) AS REAL)) DESC LIMIT 6")]
        moved = []
        for s in nil:
            ref = FE.reference_annual(c, s)
            if not ref or CU.is_valid(ref.get("unit_norm")):
                continue
            if FE.annualize_rows([], FE.fs_amount_mrl(ref), op_basis=True,
                                 fs_unit_known=False):
                moved.append(s)
        ck(not moved, "U9ت رویِ دادهٔ real هم هیچ مرجعِ بی‌واحدی مبنایِ عدد نمی‌شود", moved[:4])
        c.close()
    else:
        print("  info  market.db نیست — بندهایِ ۹ رویِ این ماشین اجرا نشد")

    print("\ncodal_unit_scale_v1090: %d passed / %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
