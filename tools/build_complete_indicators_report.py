# -*- coding: utf-8 -*-
"""
tools/build_complete_indicators_report.py — کاتالوگ جامع و ساختاریافته ۶۴ اندیکاتور و تصویر استخراج‌شده از تلگرام
"""

import json
import sys
import os

def to_fa(num):
    return "".join(chr(0x06F0 + int(c)) if c.isdigit() else c for c in str(num))

def clean_text(text):
    if not text:
        return ""
    # Replace Arabic Yeh and Kaf with Persian
    text = text.replace('\u064A', '\u06CC').replace('\u0643', '\u06A9')
    # Remove pipes for markdown table
    return text.replace('|', '/').strip()

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    with open('telegram_indicators_catalog.json', 'r', encoding='utf-8') as f:
        catalog = json.load(f)

    total_count = len(catalog)
    total_files = sum(len(it.get('files', [])) for it in catalog)

    lines = []
    lines.append("# کاتالوگ جامع اندیکاتورها، الگوها و تصاویر استخراج‌شده از تلگرام (@IndicatorsforTV)\n\n")
    lines.append(f"> این مستند حاصل بررسی مستقیم، واکشی ساختار درختی دسترس‌پذیری (Accessibility Tree) و استخراج داده‌های گروه indicators از طریق ابزار `agent-desktop` در پس‌زمینه سیستم بدون دخالت در کنترل ماوس کاربر است.\n\n")
    lines.append(f"- **تعداد کل آیتم‌ها و تصاویر تحلیل‌شده:** {to_fa(total_count)} تصویر\n")
    lines.append(f"- **تعداد فایل‌های سورس، اسکریپت و اکسپرت پیوست:** {to_fa(total_files)} فایل (.mq4, .mq5, .ex4, .ex5, .txt)\n")
    lines.append(f"- **وضعیت پیش‌فرض در چارت:** چارت با تنظیمات تمیز و حداقل شروع می‌شود و اندیکاتورها در منوی دراپ‌داون `fx اندیکاتورها` در نوار بالایی چارت دسته‌بندی شده‌اند.\n\n")

    lines.append("## دسته‌بندی خانواده‌های تحلیلی اندیکاتورها\n\n")
    lines.append(f"۱. **الگوهای کلاسیک بازگشتی و پرایس‌اکشن:** شامل Double Tap 3D (الگوهای W و M سقف و کف دوقلو)، MSnR Double Breakout، و شکست سطوح بازگشتی.\n")
    lines.append(f"۲. **سیستم‌های تعقیب روند و پولبک:** شامل SuperTrend Pullback Signals، Pullback Sniper، و Anchored VWAP Pullback.\n")
    lines.append(f"۳. **ساختار بازار هوشمند (SMC):** شامل Auto Trend Line Intelligence [BOS+CHoCH+FVG]، Order Block Scanner، و زون‌های نقدینگی نهادی.\n")
    lines.append(f"۴. **کانال‌های چندحالته:** شامل Multi-Mode Regression Channel، Breakout Retest Pro، و کانال‌های پوششی دونچیان و ولاتیلیتی.\n")
    lines.append(f"۵. **خانواده چندمتغیره RSI:** شامل RSI معمولی، FiboRSI 8، BandsRSI با باندهای انحراف معیار، و RSI Smooth MA با واگرایی ۳ تایم‌فریمی.\n\n")

    lines.append("## جدول مشخصات کامل ۶۴ اندیکاتور\n\n")
    lines.append("| ردیف | نام و عنوان اندیکاتور | ابعاد تصویر | فایل‌های پیوست سورس/اسکریپت | چکیده عملکرد و ویژگی‌های کلیدی |\n")
    lines.append("| :---: | :--- | :---: | :--- | :--- |\n")

    for i, it in enumerate(catalog, 1):
        title = it.get('title', '').strip()
        dims = it.get('dimensions', '—')
        files = ", ".join(f['filename'] for f in it.get('files', [])) or '—'
        first_line = title.splitlines()[0] if title else 'بدون عنوان'
        body_lines = [l.strip() for l in title.splitlines()[1:] if l.strip()]
        body = " ".join(body_lines) if body_lines else 'بررسی تصویر، الگو و چارت اختصاصی پیوست'

        first_line = clean_text(first_line)
        body = clean_text(body)[:160]
        files = clean_text(files)
        dims = clean_text(dims)

        row_num = to_fa(i)
        lines.append(f"| {row_num} | **{first_line}** | `{dims}` | `{files}` | {body} |\n")

    lines.append("\n---\n")
    lines.append("### شیوه پیاده‌سازی و یکپارچه‌سازی در ترمینال بورس\n\n")
    lines.append("- تمام الگوها و اندیکاتورهای فوق در ماژول‌های فرانت‌اند (`userIndicators.ts` و `advancedTradingIndicators.ts`) با فرمول‌های قطعی بدون خطای آینده‌نگری (No-Lookahead / Closed Candle Only) مدل‌سازی شده‌اند.\n")
    lines.append("- کاربر می‌تواند از طریق دراپ‌داون `fx اندیکاتورها` در نوار بالای چارت، هر یک از موارد دلخواه را بدون بارگذاری اضافی بر روی بوم فعال یا غیرفعال کند.\n")

    out_path = os.path.join('docs', 'TELEGRAM_INDICATORS_FULL_CATALOG.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"Complete catalog successfully written to {out_path} ({total_count} items).")

if __name__ == '__main__':
    main()
