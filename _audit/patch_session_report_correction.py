# _audit/patch_session_report_correction.py -- افزودنِ بخشِ «تصحیحِ دامنه» به گزارشِ نشستِ پیشین
# رقم‌ها ASCII نوشته می‌شوند و پیش از نوشتن به فارسی برگردانده می‌شوند (به‌جز داخلِ backtick) تا
# هیچ رقمی جا نیفتد — همان نقصی که dev/persian_glyph_guard.py دنبالِ آن است.
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "SESSION-REPORT-1405-07-19-FTS-INDICATORS.md")
MARK = "تصحیحِ دامنه (1405-07-20)"

FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(s):
    return "`".join(p if i % 2 else p.translate(FA) for i, p in enumerate(s.split("`")))


SECTION = """
## تصحیحِ دامنه ({DATE}) — «رهاورد» در گزارشِ پیشین دو چیزِ متفاوت بود

مالک این تفکیک را خواست و ما آن را از کد و از مرورگرِ واقعی دوباره سنجیدیم:

- **دادۀِ کندلِ مقابله‌شده از `tradersarena.ir` آمده، نه از `rahavard365.com`.**
  `tools/ra_fts_parity.py` کندل را از `tradersarena.ir/data/{{ins_code}}/prices` می‌گیرد؛ تریدرز آرنا
  محصولِ دیگری است. پس ۵۴ سطرِ `PARITY-2026-10-11.csv` فقط پاریتیِ داده با تریدرز آرنا را ثابت می‌کند و
  «تطبیق با رهاورد» درِ آن‌ها اثبات‌نشده می‌ماند.
- **ادعای «رهاورد هیچ اندیکاتوری منتشر نمی‌کند» از همین JSONِ تریدرز آرنا نتیجه شده بود و غلط است.**
  رابطِ واقعیِ ره‌آورد ویجتِ TradingView است: هشت گروهِ ابزارِ ترسیم
  (`linetool-group-trend-line`, `linetool-group-gann-and-fibonacci`, `linetool-group-patterns`,
  `linetool-group-prediction-and-measurement`, `linetool-group-geometric-shapes`,
  `linetool-group-annotation`, `linetool-group-font-icons`, `linetool-group-cursors`)،
  `open-indicators-dialog`، مقیاسِ سه‌حالته (`percentage` / `logarithm` / `auto`) و تعدیلِ سه‌حالته
  («بدون تعدیل» / «عملکردی» / «آخرین قیمت»). شاهد: `_audit/ra365_tools.json` و
  `_audit/ra365_folad_chart.png` (گرفتۀِ نشستِ لاگین‌شده).
- **برچسب‌هایِ انسانیِ `REFERENCE.csv` واقعاً از رابطِ ره‌آورد خوانده شده بودند** — `asset id`هایِ آن
  (453 فولاد، 462 وبملت، 599 ولانا، 149 فنوال، 167 خودرو، 484 شپنا) رویِ `rahavard365.com` به همان
  نمادها می‌رسند. اما مبنایِ بصریِ برچسب‌ها «محورِ خطی» بوده و دورِ جدید باید «عملکردی + لگاریتمی»
  بسنجد؛ پس آن ۱۲ سطر درِ دورِ جدید بازتأیید می‌شوند.
- **نخستین واگراییِ اندازه‌گیری‌شده درِ دورِ جدید (دادۀِ مرجع، نه حدس):** کندلِ هفتۀِ جاریِ فولاد درِ
  ره‌آورد `O 4,100 H 4,220 L 4,000 C 4,220` است؛ `price_history` ما درِ همان هفته فقط یکِ نشست
  (یکشنبه 2026-10-11) با `open 4,220` دارد و شنبه 2026-10-10 برایِ تقریباً هیچِ نمادی ثبت نشده
  (2391 نماد سطرِ 10-11 دارند، فقط 2 نماد سطرِ 10-10). اختلافِ بازِ کندل: 120 واحد (2.9٪) درِ O.
  علتِ ریشه‌ای درِ مرحلۀِ ۳ همین دور پیگیری می‌شود؛ تا پیش از آن، هیچ رأیِ روندی بر پایهٔ این
  سری «تطبیق‌یافته» اعلام نمی‌شود.
""".format(DATE=fa("1405-07-20"))


def main():
    with io.open(DOC, "r", encoding="utf-8") as f:
        text = f.read()
    if fa(MARK) in text:
        print("SKIP: بخشِ تصحیح از پیش موجود است")
        return 0
    block = fa(SECTION).strip("\n") + "\n"
    out = text.rstrip("\n") + "\n\n" + block
    with io.open(DOC, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    glued = re.findall(r"[۰-۹][0-9]|[0-9][۰-۹]", out)
    print("WROTE %s | glued-digit pairs: %d" % (DOC, len(glued)))
    return 1 if glued else 0


if __name__ == "__main__":
    sys.exit(main())
