"""v1.0.63 — گاردِ دامنهٔ نبض بازار در برابرِ تریدرزآرنا (بدونِ شبکه).

چرا این تست متولد شد: مالک گفت «نبض بازار را کامل با تریدرزآرنا تطبیق بده».
تطبیقِ واقعی یعنی هر سطر با **ردیفِ هم‌نامِ خودش** بسزد؛ رمزگشاییِ دامنهٔ او در
`docs/TA-SCOPE-DECODE.md` است (هویتِ جبریِ خودش: `m = st + sf + nsf`، خطای
۰٫۰۰۰٪) و جدولِ سنجشِ زنده را `tools/pulse_ta_parity.py` می‌سازد. این فایل
هر دو قاعده‌ای را قفل می‌کند که آن سنجش به آن‌ها رسید، چون هیچ‌کدام از اینها
در دادهٔ تصادفیِ تستِ دیگری پیدا نمی‌شوند:

۱) دامنهٔ «کل بازار» = سهام + حق‌تقدم + ص.سهامی/مختلط/درآمدِ ثابت؛ اهرمی، طلا،
   نقره سطرِ خودشان و اوراق/اختيار سطرِ «اوراق، اختيار و سایر» را دارند.
   پیش از این «کل» هر نمادی را می‌شمرد: ۱۵۹٬۱۵۱ م.ت در برابر ۷۱٬۱۴۰ِ او (+۱۲۴٪).
۲) نشتِ طبقه: صکوک/اوراق مشارکت/سلف/گواهیِ سپرده هیچ paperType معتبری در تابلو
   نمی‌گیرند و به «سهام» می‌غلتیدند (۲۶۱ ردیف، ۲٬۰۳۳ م.ت در ۱۴۰۵-۰۷-۰۷).

سنجشِ پایانِ نشستِ ۱۴۰۵-۰۷-۰۷ (میلیارد تومان، ارزشِ معاملات): کل ۸۹٬۰۳۴ در برابر
۸۸٬۶۰۲ (+۰٫۵٪)، سهام و حق‌تقدم ۳۱٬۳۶۸ در برابر ۳۰٬۵۸۹ (+۲٫۶٪)، ص.اهرمی +۰٫۰۱٪.
سطرهایِ زیرگونهٔ صندوق (سهامی/ثابت/طلا/نقره) هنوز از **نام** حدس زده می‌شوند و
تقسیمشان ۴۰–۶۲٪ خطا دارد، ولی جمعِ سهامی+ثابت ±۰٫۶٪ و جمعِ طلا+نقره+کالا ±۲٫۷٪
می‌خواند — رأیِ pilot jev برایِ همین دور: همان ده سطر بماند و تقریب علامت
بخواند، نه اینکه سطر ادغام یا از بیرون عدد وارد شود.

اجرا:  python dev/pulse_ta_scope_v1063.py
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import mstat_engine as ME                                        # noqa: E402
import test_tsetmc as TT                                         # noqa: E402

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return cond


# ============ ۱) نشتِ طبقه — همان سه ردیفِ واقعی و دو سهامِ هم‌نام ============
LEAKS = [
    ("صفولا006", "صكوك اجاره فولاد006-بدون ضامن", "فلزات اساسي", 1051.9),
    ("صشرق512", "صكوك مرابحه ثشرق512-3ماهه18%", "سرمایه گذاريها", 0.0),
    ("مكرج712", "مشاركت ش كرج712-3ماهه23%", "خرده فروشان", 500.0),
    ("عسكه2", "سلف استاندارد سكه مركزي", "سرمایه گذاريها", 432.7),
    ("سبرق061", "سلف موازي برق گيلان061", "عرضه برق، گاز", 0.0),
    ("اراد1982", "مرابحه عام دولت198-ش.خ060524", "اوراق تامين مالي", 0.0),
]
for sym, name, sector, _v in LEAKS:
    cls, kind = ME.classify(8, name, sym, sector)
    ck(cls == "other", "«%s» (%s) سهام نمی‌شود → other" % (sym, name[:26]))
    ck(ME.is_bond(sym, name, sector), "is_bond «%s» را می‌گیرد" % sym)

# کنترلِ منفی: دو سهامِ واقعی که «آتيه» در نامشان هست — اگر اینها اوراق شوند،
# قاعدهٔ آتی بیش از حدِ لازم گشاد است (همین را در ۱۴۰۵-۰۷-۰۷ روی بانکِ نصبی
# دیدیم: «آتيه داده پرداز» و «سرمايه گذاري آتيه دماوند» نشانه می‌گرفتند).
KEEP_STOCK = [("اپرداز3", "آتيه داده پرداز", "فرآورده ها"),
              ("واتي3", "سرمايه گذاري آتيه دماوند", "سرمايه گذاريها"),
              ("ذوب", "ذوب آهن اصفهان", "فلزات اساسي"),
              ("فولاد", "فولاد مباركه اصفهان", "فلزات اساسي")]
for sym, name, sector in KEEP_STOCK:
    cls, _kind = ME.classify(1, name, sym, sector)
    ck(cls == "stock", "«%s» (%s) سهام می‌ماند — «آتيه» قرارداد آتی نیست"
       % (sym, name[:28]))
# قراردادِ آتیِ واقعی: نام با «آتي» + نمادِ عددپایان
_ati_cls, _ = ME.classify(1, "آتي شپنا-1405/10/23", "جشنا0510", "پالايش نفت")
ck(_ati_cls == "other", "«جشنا0510 — آتي شپنا» اوراق/آتی است، نه سهام")
# صندوق‌ها هرگز به این درِ باز نمی‌افتند: شش صندوقِ درآمد ثابت «اوراق/مشارکت» در
# نام دارند و باید صندوق بمانند (ترتیبِ classify: اول صندوق، بعد اوراق).
for sym, name in [("اگرد", "صندوق س. اوراق و مشارکت Agrd-د"),
                  ("پاك", "صندوق سرمايه گذاري پایداری اوراق-د")]:
    cls, kind = ME.classify(8, name, sym, "صندوق سرمايه گذاري قابل معامله")
    ck(cls == "fund", "«%s» با وجودِ «اوراق/مشارکت» در نام صندوق می‌ماند" % sym)
    ck(kind == "fixed", "و زیرگونهٔ نامش حفظ می‌شود (%s)" % kind)

# ============ ۲) دامنهٔ «کل بازار» — همان سطرهایِ market0ِ تریدرزآرنا ==========
ck([c for c, _l in ME.CATEGORY_ROWS][0] == "all" and len(ME.CATEGORY_ROWS) == 10,
   "جدولِ خلاصه ده سطری است و «کل بازار» صدرِ آن")
ck("bonds_other" in {c for c, _l in ME.CATEGORY_ROWS},
   "«اوراق، اختيار و سایر» سطرِ خودش را دارد تا پولِ پنهان نشود")
# هر نماد یا در «کل» است یا در یکی از سطرهایِ جدا — و هیچ نمادی در دو سطرِ
# تجزیه (all/bonds_other/lev/gold/silver) نمی‌نشیند.
UNIVERSE = [("stock", "stock"), ("right", "right"),
            ("fund", "equity"), ("fund", "fof"), ("fund", "etf"), ("fund", "mixed"),
            ("fund", "fixed"), ("fund", "lev"), ("fund", "gold"), ("fund", "silver"),
            ("other", "other")]
PART = ("all", "bonds_other", "lev_fund", "gold_fund", "silver_fund")
for cls, kind in UNIVERSE:
    row = {"cls": cls, "kind": kind, "ins_code": "x"}
    hits = [c for c in PART if ME.in_category(row, c, None)]
    ck(len(hits) == 1, "%s/%s دقیقاً در یک سطرِ تجزیه: %s" % (cls, kind, hits))
for cls, kind in UNIVERSE:
    row = {"cls": cls, "kind": kind, "ins_code": "x"}
    ck(ME.in_category(row, "all", None) == (
        cls in ("stock", "right") or (cls == "fund" and kind in
                                      ("equity", "fof", "etf", "mixed", "fixed"))),
       "دامنهٔ «کل» برایِ %s/%s همان است که mِ تریدرزآرنا می‌شمارد" % (cls, kind))
# «معاملات خرد» (eq_all) زیرمجموعهٔ «کل» است و اهرمی/طلا/نقره در آن نیستند
for cls, kind in UNIVERSE:
    row = {"cls": cls, "kind": kind, "ins_code": "x"}
    if ME.in_category(row, "eq_all", None):
        ck(ME.in_category(row, "all", None), "eq_all ⊂ all برایِ %s/%s" % (cls, kind))

# ==== ۲ب) برچسبِ دامنهٔ پنل باید با دامنه‌ای که می‌خواند یکی باشد =========
# سنجشِ زندهٔ ۱۴۰۵-۰۷-۱۱ (۱۰:۵۴): پنلِ «عمق/دما» hint اش «سهام، حق تقدم و
# ص.سهامی» بود ولی فرانت بی‌`group` صدا می‌زد و پیش‌فرضِ موتور `all` است —
# یعنی ۶۴٬۴۸۷ ب.تِ کلِّ بازار (درآمدثابت + اوراق + اختیار داخلش) زیرِ برچسبی
# که ۱۱٬۸۶۸ ب.تِ سهام‌ساندها را وعده می‌داد. با `eq_all`: ۱۱٬۸۶۸ در برابرِ
# ۱۱٬۲۰۳ِ تریدرزآرنا (+۵٫۹٪) و ۵٬۳۴۵ در برابرِ ۴٬۸۰۱ (+۱۱٪) و pos% ۵۳٫۱ در
# برابرِ ۵۲٪ — پیش‌تر ۵٫۷ برابر و ۲٫۹ برابر و ۵۷٪ بود.
_pul = open(os.path.join(ROOT, "frontend", "src", "features", "market", "api",
                          "useMarketPulse.ts"), encoding="utf-8").read()
for ep in ("depth", "thermometer"):
    ck(f"/api/mstat/{ep} درِ نبض بازار با group=eq_all خوانده می‌شود",
       f"/api/mstat/{ep}?group=eq_all" in _pul)
    naked = [ln.strip() for ln in _pul.splitlines()
             if f"/api/mstat/{ep}" in ln and "group=" not in ln]
    ck(not naked, "فراخوانِ بی‌دامنهٔ %s نمانده%s"
       % (ep, ("" if naked else "  ← " + " | ".join(n[:70] for n in naked))))


# ============ ۳) نوشتنِ نصفهٔ «ارزش کل بازار» + خواندنِ ردیفِ معیوب ===========
def fake_getter(replies):
    def _p(_s, url, _key):
        m = int(str(url).rsplit("/", 1)[1])
        return replies.get(m)
    return _p


FULL = {1: {"marketValue": 1.8e17, "indexLastValue": 3.2e6},
        2: {"marketValue": 7.6e16}}
PARTIAL = {1: {"marketValue": 8.0e15, "indexLastValue": 3.2e6}}
EMPTY = {}
_orig = TT.polite_get
try:
    TT.polite_get = fake_getter(FULL)
    tot, dev, ov = TT.fetch_market_total(None)
    ck(abs(tot - 2.56e17) < 1, "هر دو بازار پاسخ دهند: جمعِ کامل نوشته می‌شود")
    ck(dev == 0 and ov is not None, "شاخصِ بورس از همان پاسخِ رایگان نمی‌افتد")

    TT.polite_get = fake_getter(PARTIAL)
    tot1, _d, ov1 = TT.fetch_market_total(None)
    ck(tot1 == 0.0, "فقط بورس پاسخ دهد → عدد نوشته نمی‌شود (۸٬۰۰۹ همتِ ۱۴۰۵-۰۷-۰۶)")
    ck(ov1 is not None, "شاخص بازم می‌نشیند؛ فقط جمعِ نصفه رد می‌شود")

    TT.polite_get = fake_getter({1: dict(FULL[1]), 2: None})
    tot2, _d2, _o2 = TT.fetch_market_total(None)
    ck(tot2 == 0.0, "فرابورس بی‌پاسخ → همان ردِ جمعِ نصفه")

    TT.polite_get = fake_getter(EMPTY)
    tot3, d3, ov3 = TT.fetch_market_total(None)
    ck((tot3, d3, ov3) == (0.0, 0, None), "هیچ بازاری پاسخ نداد → (0.0, 0, None)")

    # save_market_total هم بی‌عددِ کامل نمی‌نویسد
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    TT.ensure_market_totals_schema(conn)
    # سنجهٔ باورپذیری خواننده از «جمعِ dedupedِ» خودِ تابلو است؛ رویِ بانکِ واقعی
    # این دو ۴٪ فاصله دارند (۲۴۹٬۰۷۰ در برابر ۲۶۰٬۴۶۰ همت)، پس فیشر همین‌جا
    # همان نسبت را دارد.
    conn.execute("CREATE TABLE market_watch (ins_code TEXT, d_even INTEGER,"
                 " total_shares REAL, market_cap REAL)")
    conn.execute("INSERT INTO market_watch VALUES ('i1', 20260929, 1e9, 2.55e17)")
    ck(TT.save_market_total(conn, 0.0, 20260929) is False,
       "جمعِ صفر واردِ جدول نمی‌شود")
    ck(TT.save_market_total(conn, 2.561e17, 20260927) is True,
       "عددِ کاملِ باورپذیر نوشته می‌شود")
    TT.save_market_total(conn, 8.009e15, 20260928)   # newest = نصفه
    val, src = ME.market_total_rials(conn)
    ck(abs(val - 2.561e17) < 1 and src == "tse_market_overview",
       "ردیفِ نصفه‌خوانده نمی‌شود؛ عددِ باورپذیرِ قبل می‌آید (was %s)" % val)
    # تنها ردیفِ موجود هم نصفه باشد → عددِ پشتیبانِ خودِ تابلو، نه نصفهٔ رسمی
    conn.execute("DELETE FROM market_totals")
    TT.save_market_total(conn, 8.009e15, 20260928)
    val2, src2 = ME.market_total_rials(conn)
    ck(src2 == "board_sum_deduped" and val2 == 2.55e17,
       "بی‌ردیفِ باورپذیر از market_total نمی‌خواند (منبع: %s، عدد: %s)" % (src2, val2))
    # کنترلِ منفی: اگر تابلو هم نباشد، عددِ نصفه تنها مرجع خودش است و خوانده
    # می‌شود — یعنی سنجه از «باورپذیریِ مستقل» می‌آید، نه از ردِ هر چیزِ کوچک
    conn.execute("DROP TABLE market_watch")
    val3, src3 = ME.market_total_rials(conn)
    ck(src3 == "tse_market_overview" and val3 == 8.009e15,
       "بی‌مرجعِ بیرونی هیچ ردیفی بی‌دلیل رد نمی‌شود (منبع: %s)" % src3)
    conn.close()
finally:
    TT.polite_get = _orig

print("pulse_ta_scope_v1063: %d سنجه، %d خطا"
      % (len(CHECKS), sum(1 for ok, _m in CHECKS if not ok)))
for ok, msg in CHECKS:
    print("  %s %s" % ("PASS" if ok else "FAIL", msg))
sys.exit(1 if any(not ok for ok, _m in CHECKS) else 0)
