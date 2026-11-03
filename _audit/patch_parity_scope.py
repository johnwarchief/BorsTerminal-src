# _audit/patch_parity_scope.py -- درجِ کادرِ «تصحیحِ دامنه» در گزارشِ پاریتی (بدونِ تایپِ عددِ فارسی)
# چرا اسکریپت: درِ نوشتنِ مستقیمِ متنِ فارسی، رقم‌هایِ فارسی جا می‌افتند (همان نقصِ «banner digit
# loss» که dev/persian_glyph_guard.py دنبالِ آن است). اینجا همهٔ اعداد ASCII نوشته می‌شوند و
# پیش از نوشتنِ فایل به فارسی تبدیل می‌شوند — به‌جز هرچه داخلِ backtick است (نامِ فایل/URL)،
# پس نه رقمی گم می‌شود و نه هیچ نشانیِ واقعی خراب می‌شود.
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "TECHNICAL-RAHAVARD-PARITY-AUDIT.md")
MARK = "تصحیحِ دامنه"

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(s):
    """تبدیلِ رقم‌هایِ ASCII به فارسی، بی‌دست‌زدنِ هرچه داخل `backtick` است."""
    return "`".join(p if i % 2 else p.translate(FA_DIGITS) for i, p in enumerate(s.split("`")))


BLOCK = """
> ## تصحیحِ دامنه (1405-07-20 / 2026-10-12) — پیش از خواندنِ هر ادعایی در این فایل
>
> به‌خواستِ مالک، نامِ «رهاورد» در این فایل دو چیزِ متفاوت را کنارِ هم گذاشته بود. تفکیکِ درست:
>
> 1. **دادۀِ مقایسه درِ این ممیزی از `tradersarena.ir` آمده، نه از ره‌آورد 365.**
>    `tools/ra_fts_parity.py` کندل را از `https://tradersarena.ir/data/{ins_code}/prices?timeframe=N`
>    می‌گیرد (کش: `_audit/ra_probe_cache`) و تریدرز آرنا محصولِ دیگری است (کتابخانۀ `lightweight-charts`).
>    پس 54 سطرِ `PARITY-2026-10-11.csv` فقط «پاریتیِ دادۀِ کندل با تریدرز آرنا» را ثابت می‌کند و
>    **هیچ‌وقت اثباتِ تطبیق با نمودارِ ره‌آورد نبوده است.**
> 2. **ادعایِ §0 («رهاورد هیچ اندیکاتوری منتشر نمی‌کند») از همین JSONِ تریدرز آرنا نتیجه شده و غلط است.**
>    رابطِ واقعیِ ره‌آورد 365 (`rahavard365.com/asset/<id>/chart`، ویجتِ TradingView) هم اندیکاتور
>    دارد، هم ابزارهایِ ترسیم، هم انتخابِ تعدیل «عملکردی» و هم نشانگرهایِ رویدادِ شرکتی.
>    شاهدِ این بند: `_audit/ra365_folad_chart.png` (گرفتۀ 1405-07-19 شب، نشستِ لاگین‌شده).
> 3. **برچسب‌هایِ انسانیِ `REFERENCE.csv` واقعاً از رابطِ ره‌آورد خوانده شده‌اند** — این امشب
>    اندازه‌گیری و تأیید شد: `asset id`هایِ همان فایل رویِ `rahavard365.com` به همان نمادها
>    می‌رسند (453 فولاد، 462 وبملت، 599 ولانا، 149 فنوال، 167 خودرو، 484 شپنا).
>    اما مبنایِ بصری‌شان «محورِ خطی» بوده (§تنظیماتِ `PROTOCOL.md`) درحالی‌که دورِ جدید باید
>    «عملکردی + لگاریتمی» بسنجد؛ پس آن 12 سطر درِ دورِ جدید بازتأیید می‌شوند، نه تقلیل.
>
> نتیجه: آنچه در این فایل «پاریتیِ دادۀِ کندل» و «پاریتیِ منطق» نام گرفته، اعتبارش تا مرزِ
> «تریدرز آرنا» است. سنجشِ دوباره با رابطِ ره‌آورد درِ برنامۀ «تطبیقِ عددی و بصریِ جامع»
> (مراحلِ 3 تا 6) در جریان است و نتیجه در `docs/technical-indicators/implemented/` گزارش می‌شود.
"""

SEC0_OLD_HEAD = "## ۰) پیش‌شرطِ روش‌شناختی: رهاورد هیچ اندیکاتوری منتشر نمی‌کند"
SEC0_NEW_HEAD = (
    "## {0}) پیش‌شرطِ روش‌شناختی: رهاورد هیچ اندیکاتوری منتشر نمی‌کند "
    "— (تصحیحِ {1}: این بند از JSONِ تریدرز آرنا نتیجه شد؛ رابطِ واقعیِ ره‌آورد {2} "
    "اندیکاتور و ابزارِ ترسیم دارد. کادرِ بالایِ فایل را ببین.)"
).format(fa("0"), fa("1405-07-20"), fa("365"))


def main():
    with io.open(DOC, "r", encoding="utf-8") as f:
        text = f.read()
    if ("> ## " + MARK) in text:
        print("SKIP: کادرِ تصحیح از پیش موجود است")
        return 0
    lines = text.split("\n")
    assert lines[0].startswith("# "), "تیترِ فایل عوض شده: " + lines[0][:40]
    block = fa(BLOCK).strip("\n") + "\n"
    out = "\n".join(lines[0:2] + [block] + lines[2:])
    if SEC0_OLD_HEAD in out and SEC0_NEW_HEAD not in out:
        out = out.replace(SEC0_OLD_HEAD, SEC0_NEW_HEAD, 1)
    with io.open(DOC, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    # خودآزمایی ۱: هیچ رقمِ ASCII بیرونِ backtick نماند (مگر درِ نامِ فایلِ لاتین)
    leaks = []
    for ln in out.split("\n"):
        outside = re.sub(r"`[^`]*`", "", ln)
        for m in re.finditer(r"[0-9]", outside):
            ctx = outside[max(0, m.start() - 18):m.start() + 18]
            if not re.search(r"[A-Za-z]{3}", ctx):
                leaks.append(ctx.strip())
    # خودآزمایی ۲: هیچ رقمِ فارسی+لاتین چسبیده‌ای نسازد
    glued = [x[:60] for x in re.findall(r"[۰-۹][0-9]|[0-9][۰-۹]", out)]
    print("WROTE " + DOC)
    print("ascii-digit leaks: %d | glued digits: %d" % (len(leaks), len(glued)))
    for x in (leaks + glued)[:6]:
        print("  " + x)
    return 1 if (leaks or glued) else 0


if __name__ == "__main__":
    sys.exit(main())
