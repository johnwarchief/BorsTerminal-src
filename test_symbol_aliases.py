# -*- coding: utf-8 -*-
"""رگرسیونِ «پسوندِ رقمیِ خطِ تابلو» — از `symbol_aliases` به `symbol_identity`.

این فایل پیش‌تر رفتارِ `fts_engine.symbol_aliases()` را می‌آزمود (بازگشتِ
v9.10.4: یک رقمِ انتهایی کم شود تا ۳۹۶ سهم بی‌دادهٔ بنیادی نمانند). آن تابع
 حذف شد، چون **جایگشتِ نویسه** می‌ساخت: بی‌شاهد، و کرانۀ رشدِ نمایی داشت
(سنجشِ ۱۴۰۵-۰۷-۲۲: سقفِ ۹۶ ⇒ ۲۱۶ نامزد، سقفِ ۲۵۶ ⇒ ۶۴۸ نامزد). جانشینِ آن
`symbol_identity.py` است — همان قاعده، دو فرقِ مستند:

  ۱) نامزدها از **خودِ بانک** خوانده می‌شوند، نه از تولیدِ جایگشت؛
  ۲) حذفِ رقمِ انتهایی فقط با شاهدِ ISIN مجاز است، و دو صادرکننده زیرِ یک
     پایۀ نام ⇒ ردِ صریح (`isin-clash`)، نه الحاق.

پنج پروندۀ پیشین (رقمِ تک / رقمِ چندتایی / نمادِ ساده / ي↔ی / نمادِ کوتاه)
و دو پروندۀ `sym_in` اینجا حفظ شده‌اند و دو پروندۀ تازه (ردِ الحاق، و
«ردشدن اعلام می‌شود») افزوده شده است. بی‌`market.db`: بانکِ آزمون درِ حافظه
ساخته می‌شود.

اجرا:  PYTHONIOENCODING=utf-8 python test_symbol_aliases.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fts_engine as FE               # noqa: E402
import symbol_identity as SI          # noqa: E402

Z = "‌"


def make_db(rows, inst):
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE financial_statements (tracing_no INTEGER PRIMARY KEY,"
              " symbol TEXT, company_name TEXT, title TEXT, period_months INTEGER,"
              " period_end TEXT, revenue REAL, gross_profit REAL, net_profit REAL,"
              " basic_eps REAL)")
    c.executemany("INSERT INTO financial_statements (tracing_no, symbol, revenue) "
                  "VALUES (?,?,?)", rows)
    c.execute("CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, l_val18 TEXT,"
              " isin TEXT)")
    c.executemany("INSERT INTO instruments (ins_code, l_val18, isin) VALUES (?,?,?)", inst)
    c.commit()
    FE.register_sql(c)
    return c


def db():
    # مبین/مبین3 دو خطِ یکِ صادرکننده؛ صشرق512 اوراقِ مستقلی با همان پایۀ نام؛
    # کمه۴/کمه۵ دو صادرکنندهٔ متفاوت زیرِ یکِ نام.
    rows = [(1, "مبين", 10.0), (2, "مبین3", 20.0), (3, "صشرق512", 30.0),
            (4, "کمه", 40.0), (5, "فول" + Z + "اد", 50.0), (6, "داریك", 60.0)]
    inst = [("1", "مبین3", "IRO1MOBIN003"), ("2", "مبين", "IRO1MOBIN001"),
            ("3", "صشرق512", "IRB0S0000002"), ("4", "کمه4", "IRO1KAMRA004"),
            ("5", "کمه5", "IRO2KAMRB005"), ("6", "کمه", "IRO1KAMRA001"),
            ("7", "فولاد", "IRO1FOLAD001"), ("8", "داریک", "IRO1DARIK001")]
    return make_db(rows, inst)


def test_single_trailing_digit_resolves_to_base():
    """رقمِ تک با ISINِ هم‌قطار به پایه می‌رسد (همان اصلاحِ v9.10.4)."""
    c = db()
    pred, params = FE.sym_in(c, "symbol", "مبین3")
    assert "مبين" in params, params
    assert params[0] == "مبین3", "خودِ نماد باید اول بماند (ترتیبِ قطعی)"
    assert pred.startswith("symbol IN ("), pred


def test_multi_digit_tail_is_untouched():
    """۵۱۲ بخشی از نام است نه نشانۀ طبقه — هرگز رقم کم نمی‌شود."""
    c = db()
    _pred, params = FE.sym_in(c, "symbol", "صشرق512")
    assert all(a.endswith("512") for a in params), params


def test_plain_symbol_unchanged():
    """نمادِ بی‌پسوندِ رقمی: هیچ نامزدِ دیگری از جایگشت یا خردکردن نمی‌آید."""
    c = db()
    _pred, params = FE.sym_in(c, "symbol", "مبين")
    assert params == ["مبين"], params


def test_arabic_persian_variants_still_work():
    """ي/ی و ك/ک دو نوشتارِ یکِ کلیدند — نامزد از خودِ بانک برداشته می‌شود."""
    c = db()
    _pred, params = FE.sym_in(c, "symbol", "داریک")
    assert "داریك" in params, params
    _pred2, params2 = FE.sym_in(c, "symbol", "فول" + Z + "اد")
    assert "فولاد" in params2 or "فول" + Z + "اد" in params2, params2
    assert SI.key("فول" + Z + "اد") == SI.key("فولاد")


def test_too_short_symbol_does_not_strip():
    """پایۀ یک‌حرفی نماد نیست؛ الحاق نباید مطرح شود."""
    c = db()
    extra, ev = SI.line_variants(c, "آ3")
    assert not extra and ev == "exact", (extra, ev)


def test_two_issuers_under_one_base_are_never_merged():
    """کنترلِ منفی: دو ISINِ متفاوت ⇒ رد، و رد **اعلام** می‌شود."""
    c = db()
    extra, ev = SI.line_variants(c, "کمه4")
    assert not extra, extra
    assert ev == "isin-clash", ev
    assert SI.evidence(c, "کمه4") == "isin-clash", SI.evidence(c, "کمه4")
    _pred, params = FE.sym_in(c, "symbol", "کمه4")
    assert params == ["کمه4"], params


def test_sym_in_uses_the_base():
    c = db()
    pred, params = FE.sym_in(c, "symbol", "مبین3")
    assert "مبين" in params, params
    assert pred.startswith("symbol IN ("), pred


def test_empty_symbol_is_safe():
    c = db()
    pred, params = FE.sym_in(c, "symbol", "")
    assert pred == "1=0", pred
    assert params == [], params


def test_no_alias_permutation_generator_survives():
    """لایۀ جایگشت‌ساز برنگردد: کرانِ نامزد از شمارِ نوشتارهایِ بانک است."""
    assert not hasattr(FE, "symbol_aliases")
    c = db()
    _pred, params = FE.sym_in(c, "symbol", "مبین3")
    assert len(params) <= SI.MAX_VARIANTS, params


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    n_ok = 0
    for fn in fns:
        try:
            fn()
        except Exception as ex:                      # noqa: BLE001
            print("  FAIL %-52s %s" % (fn.__name__, str(ex)[:120]))
            continue
        n_ok += 1
        print("  PASS %s" % fn.__name__)
    print("\n%d/%d passed" % (n_ok, len(fns)))
    sys.exit(0 if n_ok == len(fns) else 1)
