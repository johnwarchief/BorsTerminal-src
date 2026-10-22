# -*- coding: utf-8 -*-
"""Correct the operational-DB sensor and append the Rahavard addendum to the main R18 report."""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "artifacts", "ra365", "r18-rahavard")
MAIN = os.path.join(ROOT, "docs", "RA365-ROUND18-RAW-OHLC-PARITY-REPORT.md")
FA = "۰۱۲۳۴۵۶۷۸۹"


def fa(n, dec=0, pct=False):
    s = f"{float(n):,.{dec}f}" if dec else f"{int(round(float(n))):,}"
    s = s.replace(",", "٬").replace(".", "٫")
    s = "".join(FA[int(ch)] if ch.isdigit() else ch for ch in s)
    return s + ("٪" if pct else "")


S = json.load(open(os.path.join(ART, "rahavard-raw-ohlc-summary.json"), encoding="utf-8"))
rows = list(csv.DictReader(open(os.path.join(ART, "rahavard-raw-ohlc-row-taxonomy.csv"),
                                encoding="utf-8-sig")))
text = open(MAIN, encoding="utf-8").read()
text = text.replace(
    "**دیتابیس عملیاتی:** SHA `17e93bf6c88fa09956efa5cc234620c5d84d85a1b4301436f8a44c536416f070` (mtime: 2026-10-22 04:14)",
    "**دیتابیس عملیاتی:** SHA `7b933b05d03b8a2f9383f901faf6b2c34f1500e70619d6cc5c8039f171b1848c` (mtime: 2026-10-15 03:31)")
text = text.replace(
    "SHA واقعی دیتابیس سورس در شروع و پایان این راند `17e93bf6c88fa09956efa5cc234620c5d84d85a1b4301436f8a44c536416f070` است؛ mtime فایل اصلی 2026-10-22 04:14 و `market.db-wal` صفر بایت است.",
    "SHA واقعی دیتابیس سورس در شروع و پایان این راند `7b933b05d03b8a2f9383f901faf6b2c34f1500e70619d6cc5c8039f171b1848c` است؛ mtime فایل اصلی 2026-10-15 03:31 و `market.db-wal` صفر بایت است. فایل `market.db` داخل worktree یک fixture تست است و با دیتابیس عملیاتی یکی نیست؛ SHA گزارش قبلی (`17e93…`) به همان fixture اشاره داشت و اکنون تصحیح شده است.")
text = text.replace(
    "- دیتابیس عملیاتی: SHA `17e93bf6c88fa09956efa5cc234620c5d84d85a1b4301436f8a44c536416f070` پیش/پس یکسان.",
    "- دیتابیس عملیاتی: SHA `7b933b05d03b8a2f9383f901faf6b2c34f1500e70619d6cc5c8039f171b1848c` پیش/پس یکسان.")
if "## ۱۳. ضمیمه" not in text:
    text += f"""

---

## ۱۳. ضمیمه — ممیزی کامل Rahavard type0

این بخش، سؤال «آیا OHLC خام BorsTerminal با Rahavard یکسان است؟» را در سطح ردیف و فیلد پاسخ می‌دهد. گزارش تفصیلی: `docs/RA365-ROUND18-RAHAVARD-RAW-OHLC-PARITY-REPORT.md`.

- **تمام ۲٬۵۹۵ دارایی** نوع `type0` در snapshot منجمد بررسی شدند؛ **{fa(S['row_pairs'])}** ردیف قابل‌مقایسه از **۱٬۱۹۲٬۰۷۱** تاریخ مشترک.
- **تطبیق قراردادی Raw:** **{fa(S['contract_ok_pct'], 4, True)}** فیلد و **{fa(S['row_exact_pct'], 4, True)}** ردیف.
- **تطبیق تحت‌اللفظی OHLC:** high {fa(S['literal_high_exact_pct'], 4, True)}، low {fa(S['literal_low_exact_pct'], 4, True)}، ردیف کامل {fa(S['literal_row_exact_pct'], 4, True)}؛ اختلاف عمدتاً `widen()` مستند است.
- **معنای type0:** close = LAST ({fa(S['type0_vs_tsetmc']['close_last_exact_pct'], 4, True)}) نه official CLOSE ({fa(S['type0_vs_tsetmc']['close_official_exact_pct'], 4, True)})؛ open = FIRST ({fa(S['type0_vs_tsetmc']['open_first_exact_pct'], 4, True)}) نه base OPEN ({fa(S['type0_vs_tsetmc']['open_base_exact_pct'], 4, True)}).
- **علت‌های باقی‌مانده:** SOURCE_DATA_DIVERGENCE {fa([r for r in rows if r['cause']=='SOURCE_DATA_DIVERGENCE'][0]['rows'])} ردیف؛ HISTORICAL_REVISION {fa([r for r in rows if r['cause']=='HISTORICAL_REVISION'][0]['rows'])}؛ PRECISION {fa([r for r in rows if r['cause']=='PRECISION_OR_ROUNDING'][0]['rows'])}؛ CANDLE_GEOMETRY {fa([r for r in rows if r['cause']=='CANDLE_GEOMETRY'][0]['rows'])}؛ UNCLASSIFIED {fa([r for r in rows if r['cause']=='UNCLASSIFIED'][0]['rows'])}؛ PARSING {fa([r for r in rows if r['cause']=='PARSING_OR_TRANSFORM'][0]['rows'])}.
- **هیچ اصلاح production** موجه اثبات نشد؛ gapهای ۴۹۹تایی snapshot در pipeline زنده وجود دارند و flat/geometry از منبع Rahavard است. تنها قرارداد مقایسه (widen با official CLOSE) اصلاح شد.
- **پوشش:** type0 فقط حدود **{fa(100.0*S['row_pairs']/2125330, 2, True)}** از کندل‌های محصول را می‌پوشاند؛ Full-Universe برای ردیف‌های Rahavard قابل‌دسترسی است، نه تمام تاریخ محصول.
"""
open(MAIN, "w", encoding="utf-8").write(text)
print("updated", MAIN, len(text))
