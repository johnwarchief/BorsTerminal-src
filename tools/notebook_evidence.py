#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/notebook_evidence.py — برش‌هایِ گویا از خودِ تصویرِ جزوۀ FTS

چرا این ابزار هست: `docs/جزوه FTS.pdf` سی‌وچهار تصویرِ اسکن‌شدۀ دست‌نویس است
(بی‌لایۀ متن)، و دورهایِ پیشین از همان صفحه دو نقلِ ناهمخوان کرده‌اند
(`NOTEBOOK-PARITY-F1-F5.md` بند ۷ جدولِ EPS را «۱۴۵» خوانده، ممیزیِ دور اول
«۷۷۴»، و فهرستِ همان صفحه «۷۴»). پس مرجع، خودِ تصویر است — و ادعایِ این
ممیزی باید با همان برشِ قابلِ بازتولیدِ تصویر دفاع شود، نه با حافظۀ مدل.

جعبه‌ها **نسبتِ** عرض/ارتفاعِ صفحۀ رندرشده‌اند (نه پیکسل)، تا تغییرِ `scale`
شواهد را جابه‌جا نکند. `--page` شمارهٔ صفحۀ PDF (یک‌مبنا) است؛ هر صفحۀ PDF
یکِ بازِ دوصفحهای از دفتر است.

    python tools/notebook_evidence.py                 # همهٔ برش‌ها
    python tools/notebook_evidence.py --list          # نامِ برش‌ها + جعبه
    python tools/notebook_evidence.py --only margin_fraction --scale 4
"""
import argparse
import os
import sys

import pypdfium2 as pdfium

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "docs", "جزوه FTS.pdf")
OUT = os.path.join(ROOT, "_audit", "notebook_evidence")

# name → (صفحۀ PDF, چپ, بالا, راست, پایین) — همه به‌صورتِ کسرِ ابعادِ صفحه
CROPS = {
    # شاخص ۱: «… نسبت به سال قبل +۴۰٪ افزایش است» (ص ۳، صفحۀ راستِ اسکن)
    "growth_40pct":       (3, 0.50, 0.30, 1.00, 0.44),
    # شاخص ۲: جدولِ سه‌سالۀ EPS (۱۴۰۲ | ۱۴۰۳ | ۱۴۰۴) — ص ۴
    "eps_table":          (4, 0.50, 0.33, 1.00, 0.49),
    # شاخص ۲: فهرستِ سه «سود (زیان) خالص هر سهم» به تفکیکِ ۱۲/۲۹ — ص ۴
    "eps_list":           (4, 0.60, 0.56, 1.00, 0.74),
    # شاخص ۳: نثرِ «درآمد عملیاتی ۳۹۲۱ میلیارد ریال» — ص ۴ (صفحۀ چپ)
    "margin_prose":       (4, 0.20, 0.46, 0.40, 0.55),
    # شاخص ۳: کسرِ «۲۱۲ ÷ ۳۶۲۱ × ۱۰۰ = ۵۸٪» — ص ۴ (صفحۀ چپ)
    "margin_fraction":    (4, 0.02, 0.56, 0.50, 0.71),
    # شاخص ۳: تکرارِ همان کسر در صفحۀ بعد — ص ۵ (صفحۀ راست)
    "margin_fraction_p5": (5, 0.52, 0.52, 1.00, 0.63),
    # شاخص ۴: سالانه‌سازیِ «× ۴» رویِ دورۀ سه‌ماهه + حاشیۀ مثالِ دوم — ص ۵ (چپ)
    "annualize_x4":       (5, 0.00, 0.30, 0.50, 0.52),
    # شاخص ۵: جدولِ ✓/✗ صنایع (سرِ فهرست تا «کاشی و سرامیک») — ص ۶ (چپ)
    "industry_table":     (6, 0.00, 0.20, 0.50, 0.52),
    # شاخص ۵: جمع‌بندیِ چهار شاخصِ اول + سرِ صفحۀ «۵/ چهار بُعد بازار» — ص ۶ (راست)
    "four_dimensions":    (6, 0.50, 0.20, 1.00, 0.56),
}


def render(page_no: int, scale: float):
    pdf = pdfium.PdfDocument(PDF)
    if not 1 <= page_no <= len(pdf):
        raise SystemExit("صفحۀ %d وجود ندارد (کل: %d)" % (page_no, len(pdf)))
    return pdf[page_no - 1].render(scale=scale).to_pil()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--scale", type=float, default=3.0)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for k, v in sorted(CROPS.items()):
            print("%-20s page=%d box=%s" % (k, v[0], v[1:]))
        return 0
    os.makedirs(OUT, exist_ok=True)
    cache = {}
    for name, (page, l, t, r, b) in sorted(CROPS.items()):
        if a.only and a.only != name:
            continue
        if page not in cache:
            cache[page] = render(page, a.scale)
        im = cache[page]
        box = (int(l * im.width), int(t * im.height),
               int(r * im.width), int(b * im.height))
        crop = im.crop(box)
        path = os.path.join(OUT, "%s_p%02d.png" % (name, page))
        crop.save(path)
        print("wrote %-34s %5dx%-5d (منبع: صفحۀ %d، جعبه %s)"
              % (os.path.relpath(path, ROOT).replace("\\", "/"),
                 crop.width, crop.height, page, box))
    return 0


if __name__ == "__main__":
    sys.exit(main())
