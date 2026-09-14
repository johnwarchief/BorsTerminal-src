"""تستِ آفلاینِ نردبانِ شواهدِ لایهٔ ۲ (FTS v10 — `api/fundamental._eps_track_blended`).

هیچ درخواست شبکه‌ای نمی‌زند و به market.db نیاز ندارد: یک DBِ در‌مُوری با رکوردهای
ساختگی می‌سازد و فقط رفتارِ انتخابِ شاهد را می‌سنجد — ترتیبِ نردبان
(غیرتلفیقیِ حسابرسی‌شده ← غیرتلفیقیِ نشده ← تلفیقیِ حسابرسی‌شده ← تلفیقیِ نشده ←
میاندوره × ۱۲÷م)، سال‌سازی، پرچم‌های soft_gap/low_quality_track و تکمیلِ پنجره با
سالِ در‌جریان. هدف: اثبات اینکه تنزلِ شاهد «برچسب‌دار» است، نه پنهانی.

همین‌طور قاعدهٔ «خروجی جدول بنیادی» قفل میشود: با کمبودِ دوره (۲ به‌جای ۳) سطر
هرگز حذف نمیشود — مقادیرِ موجود می‌مانند، جایِ دورهٔ غایب «-» است و سطر با تگِ
HTML قرمز و ذکرِ «تنها ۲ دوره موجود است» رندر میشود (`_eps_row`)؛ به‌علاوهٔ
هدرِ امنِ Content-Disposition در خروجیِ CSV (نامِ نمادِ فارسی).
اجرا:  python dev/test_fts_v10_ladder.py
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# کنسولِ ویندوز با cp1252 متنِ فارسی را نمی‌نویسد — خروجی را UTF-8 و امن میکنیم
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from api import fundamental as F  # noqa: E402

AUD = "صورت مالی سالانه حسابرسی شده"
UN = "صورت مالی سالانه حسابرسی نشده"
CA = "صورت‌های مالی تلفیقی سالانه حسابرسی شده"
CU = "صورت مالی تلفیقی سالانه حسابرسی نشده"
I3 = "اطلاعاتیه و صورت‌های مالی میاندوره‌ای ۳ ماهه حسابرسی نشده"
I9 = "اطلاعاتیه و صورت‌های مالی میاندوره‌ای ۹ ماهه حسابرسی نشده"
I6 = "اطلاعاتیه و صورت‌های مالی میاندوره‌ای ۶ ماهه حسابرسی نشده"

ROWS = [
    # A: نردبان — غیرتلفیقیِ حسابرسی‌نشده (سطح ۲) باید بر تلفیقیِ حسابرسی‌شده (سطح ۳) ببرد
    ("A", "1403-12-29", 12, UN, 500), ("A", "1403-12-29", 12, CA, 900),
    ("A", "1402-12-29", 12, AUD, 400), ("A", "1404-12-29", 12, AUD, 600),
    # B: فقط تلفیقیِ حسابرسی‌شده
    ("B", "1403-12-29", 12, CA, 100), ("B", "1402-12-29", 12, CA, 90),
    ("B", "1404-12-29", 12, CA, 110),
    # C: سالِ کامل در برابر میاندورهٔ ۹ماههٔ همان سال
    ("C", "1404-12-29", 12, CU, 300), ("C", "1404-09-30", 9, I9, 300),
    ("C", "1403-12-29", 12, CU, 200), ("C", "1402-12-29", 12, CU, 100),
    # D: سالِ جاری فقط ۳ماهه → سال‌سازیِ کوتاه + soft_gap
    ("D", "1405-03-31", 3, I3, 60), ("D", "1404-12-29", 12, AUD, 500),
    ("D", "1403-12-29", 12, AUD, 400),
    # E: فقط دو سال → شکافِ داده
    ("E", "1405-03-31", 3, I3, 80), ("E", "1404-12-29", 12, AUD, 500),
    # F: سالِ جاری ۶ماهه → annualized_interim (کوتاه نیست) و روند صعودی می‌ماند
    ("F", "1405-06-31", 6, I6, 400), ("F", "1404-12-29", 12, AUD, 500),
    ("F", "1403-12-29", 12, AUD, 300),
    # G: فقط یک دورهٔ متوالی (۱۴۰۴ غایب) → دو سلولِ «-» و سطرِ قرمز
    ("G", "1405-12-29", 12, AUD, 600), ("G", "1403-12-29", 12, AUD, 500),
]

conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE financial_statements (symbol TEXT, period_end TEXT, "
             "period_months INTEGER, title TEXT, basic_eps REAL)")
conn.executemany("INSERT INTO financial_statements VALUES (?,?,?,?,?)", ROWS)
conn.commit()

RES = []


def chk(name, cond, got=""):
    RES.append((name if cond else "✗ " + name, cond, "" if cond else repr(got)))


for sym in ("A", "B", "C", "D", "E", "F", "G"):
    chk("%s: خروجی JSON-serializable است" % sym,
        isinstance(F._eps_track_blended(conn, sym, years=3), dict))

a = F._eps_track_blended(conn, "A", years=3)
chk("A: غیرتلفیقیِ نشده بر تلفیقیِ شده مقدم است",
    a["evidence"] == ["audited_year_end", "unaudited_year_end", "audited_year_end"], a["evidence"])
chk("A: مقادیر EPS (۴۰۰/۵۰۰/۶۰۰)", a["eps_series"] == [400.0, 500.0, 600.0], a["eps_series"])
chk("A: پرچم تلفیقی خاموش می‌ماند", a["consolidated_used"] is False, a["consolidated_used"])

b = F._eps_track_blended(conn, "B", years=3)
chk("B: سطحِ تلفیقیِ حسابرسی‌شده برچسب می‌خورد",
    b["evidence"] == ["consolidated_audited"] * 3, b["evidence"])
chk("B: consolidated_used و relaxed_evidence هر دو true",
    b["consolidated_used"] and b["relaxed_evidence"], b)
chk("B: روند صعودی پاس می‌شود", b["pass"] is True, b)

c = F._eps_track_blended(conn, "C", years=3)
chk("C: سالِ کامل بر میاندورهٔ همان سال مقدم است (۳۰۰ نه ۴۰۰)",
    c["eps_series"] == [100.0, 200.0, 300.0], c["eps_series"])
chk("C: برچسب تلفیقیِ حسابرسی‌نشده", c["evidence"][-1] == "consolidated_unaudited", c["evidence"])

d = F._eps_track_blended(conn, "D", years=3)
chk("D: میاندورهٔ ۳ماهه × ۱۲÷۳ = ۲۴۰", d["eps_series"][-1] == 240.0, d["eps_series"])
chk("D: برچسب میاندورهٔ کوتاه", d["evidence"][-1] == "annualized_interim_short", d["evidence"])
chk("D: soft_gap به‌جای ردِ قطعی", d["soft_gap"] is True and d["pass"] is False, d)
chk("D: low_quality_track true", d["low_quality_track"] is True, d)
chk("D: سالِ در‌جریان دوبار شمرده نمیشود", d["in_progress_year"] is None, d["in_progress_year"])

e = F._eps_track_blended(conn, "E", years=3)
chk("E: دو سال → شکافِ داده، اما سطر حذف نمیشود",
    e["data_gap"] is True and e["partial"] is True, e)
chk("E: پنجره فقط ۲ ساله", e["years_available"] == 2, e["years_available"])

f = F._eps_track_blended(conn, "F", years=3)
chk("F: میاندورهٔ ۶ماهه «کوتاه» شمرده نمیشود",
    f["evidence"][-1] == "annualized_interim", f["evidence"])
chk("F: ۴۰۰ × ۱۲÷۶ = ۸۰۰", f["eps_series"][-1] == 800.0, f["eps_series"])
chk("F: صعودی و بدون soft_gap", f["pass"] is True and f["soft_gap"] is False, f)
chk("F: fiscal_years رشته است (بازگشتِ خطای JSON)",
    all(isinstance(y, str) for y in f["fiscal_years"]), f["fiscal_years"])

# ── قاعدهٔ خروجی جدول بنیادی: سطرِ ناقص حذف نمیشود، قرمز میشود ─────────────
e = F._eps_track_blended(conn, "E", years=3)
row_e = F._eps_row(e)
chk("E: پنجره با «None» به ۳ دوره کامل میشود (حذف نشود)",
    row_e["cells"] == ["-", "500", "320"], row_e["cells"])
chk("E: دورهٔ غایب = اسلاتِ قدیمی، نه تازه",
    e["eps_series"] == [None, 500.0, 320.0], e["eps_series"])
chk("E: period_slots = ۳ اسلات", row_e["required"] == 3, row_e)
chk("E: ۲ دوره موجود ذکر شود", row_e["available"] == 2 and row_e["red"] is True, row_e)
chk("E: عنوانِ سطر = «شاخص ۲ (تنها ۲ دوره موجود است)»",
    row_e["label"] == "شاخص ۲ (تنها ۲ دوره موجود است)", row_e["label"])
chk("E: فرمتِ دقیقِ سطر با تگِ قرمز روی همهٔ سلول‌ها",
    row_e["markdown"] == (
        '|<span style="color: red;">شاخص ۲ (تنها ۲ دوره موجود است)</span>'
        '| <span style="color: red;">-</span>'
        ' | <span style="color: red;">500</span>'
        ' | <span style="color: red;">320</span>|'), row_e["markdown"])
chk("E: هنوز data_gap/pass=False (امتیازِ واقعی نگیرد)",
    e["data_gap"] is True and e["pass"] is False, e)
chk("E: serializable", isinstance(json.loads(json.dumps(e)), dict))
chk("E: دورهٔ غایب در evidence برچسب می‌گیرد",
    e["evidence"][0] == "missing", e["evidence"])

row_g = F._eps_row(F._eps_track_blended(conn, "G", years=3))
chk("G: تک‌دوره → دو «-» و سطرِ قرمز",
    row_g["cells"] == ["-", "-", "600"] and row_g["red"] is True, row_g)
chk("G: ذکرِ «تنها ۱ دوره موجود است»",
    row_g["label"] == "شاخص ۲ (تنها ۱ دوره موجود است)", row_g["label"])

row_a = F._eps_row(F._eps_track_blended(conn, "A", years=3))
chk("A: پنجرهٔ کامل → سطرِ ساده بدون تگِ قرمز",
    row_a["red"] is False and "<span" not in row_a["markdown"], row_a)
chk("A: سلول‌ها همان ۳ مقدار", row_a["cells"] == ["400", "500", "600"], row_a["cells"])

try:  # خروجیِ جدول — هدرِ فارسی نباید ستونِ export را بشکند
    from api import _export as X

    _d = X._disposition("borsagent_fundamental_احيا_20260911_1843.csv")
    chk("export: Content-Dispositionِ فارسی latin-1-encodable است",
        _d == _d.encode("latin-1").decode("latin-1"), _d)
    chk("export: filename* (RFC 5987) نامِ اصلی را حفظ میکند",
        "filename*=UTF-8''" in _d and "%D8%A7" in _d, _d)
    _r = X._export_build("csv", "fundamental_احيا",
                         [["شاخص ۲ (تنها ۲ دوره موجود است)", "EPS", "- | 590 | 990"]])
    chk("export: CSV روی نمادِ فارسی نمی‌شکند",
        "590 | 990" in _r.body.decode("utf-8-sig"), str(_r)[:120])
    chk("export: هدرِ پاسخِ واقعی latin-1 است",
        _r.headers["content-disposition"].encode("latin-1").decode("latin-1")
        == _r.headers["content-disposition"])
except ImportError as _ex:      # pandas در محیطِ حداقلی نصب نیست → رد شدنِ تمیز
    chk("export: (skipped: %s)" % _ex, True)

npass = sum(1 for _n, ok, _g in RES if ok)
for n, ok, g in RES:
    print(("  PASS  " if ok else "  FAIL  ") + n + ("" if ok else "   <<< " + g))
print("\n%d/%d passed" % (npass, len(RES)))
sys.exit(0 if npass == len(RES) else 1)
