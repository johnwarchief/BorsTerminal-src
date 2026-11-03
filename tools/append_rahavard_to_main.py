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
    if n is None or n == "":
        return "—"
    if isinstance(n, str):
        try:
            n = float(n)
        except ValueError:
            return n
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
def row_count(cause):
    for r in rows:
        if r["cause"] == cause:
            return int(r["rows"])
    return 0


addendum = f"""

---

## ۱۳. ضمیمه — ممیزی کامل Rahavard type0

این بخش، سؤال «آیا OHLC خام BorsTerminal با Rahavard یکسان است؟» را در سطح ردیف و فیلد پاسخ می‌دهد. گزارش تفصیلی: `docs/RA365-ROUND18-RAHAVARD-RAW-OHLC-PARITY-REPORT.md`؛ داوری نهایی اختلاف‌ها: `docs/RA365-ROUND19-MISMATCH-CLOSURE-REPORT.md`.

- **تمام ۲٬۵۹۵ دارایی** نوع `type0` در snapshot منجمد بررسی شدند؛ **{fa(S['row_pairs'])}** ردیف قابل‌مقایسه از **۱٬۱۹۲٬۰۷۱** تاریخ مشترک.
- **تطبیق قراردادی Raw:** **{fa(S['contract_ok_pct'], 4, True)}** فیلد و **{fa(S['row_exact_pct'], 4, True)}** ردیف.
- **تطبیق تحت‌اللفظی OHLC:** high {fa(S['literal_high_exact_pct'], 4, True)}، low {fa(S['literal_low_exact_pct'], 4, True)}، ردیف کامل {fa(S['literal_row_exact_pct'], 4, True)}؛ اختلاف عمدتاً `widen()` مستند است.
- **معنای type0:** close = LAST ({fa(S['type0_vs_tsetmc']['close_last_exact_pct'], 4, True)}) نه official CLOSE ({fa(S['type0_vs_tsetmc']['close_official_exact_pct'], 4, True)})؛ open = FIRST ({fa(S['type0_vs_tsetmc']['open_first_exact_pct'], 4, True)}) نه base OPEN ({fa(S['type0_vs_tsetmc']['open_base_exact_pct'], 4, True)}).
- **علت‌های نهایی (Round 19):** SOURCE_DATA_DIVERGENCE {fa(row_count('SOURCE_DATA_DIVERGENCE'))} ردیف؛ HISTORICAL_REVISION {fa(row_count('HISTORICAL_REVISION'))}؛ PRECISION {fa(row_count('PRECISION_OR_ROUNDING'))}؛ CANDLE_GEOMETRY {fa(row_count('CANDLE_GEOMETRY'))}؛ PARSING {fa(row_count('PARSING_OR_TRANSFORM'))}؛ UNCLASSIFIED {fa(row_count('UNCLASSIFIED'))}.
- **تعیین تکلیف P0:** از ۶ ردیف PARSING اولیه، ۵ ردیف volume در واقع type0-only بودند و به SOURCE منتقل شدند؛ ۱ ردیف volume صفر snapshot با TSETMC مثبت ماند. ۵۵ ردیف UNCLASSIFIED قبلی، open با `FIRST=0` و fallback مستند product بودند و PARSING شدند؛ ۳۱ ردیف دیگر به سه‌منبعی SOURCE رفتند. UNCLASSIFIED صفر شد.
- **هیچ اصلاح production** موجه اثبات نشد؛ gapهای ۴۹۹تایی snapshot در pipeline زنده وجود دارند و flat/geometry از منبع Rahavard است. تنها قرارداد مقایسه (widen با official CLOSE) اصلاح شد.
- **پوشش:** type0 فقط حدود **{fa(100.0*S['row_pairs']/2125330, 2, True)}** از کندل‌های محصول را می‌پوشاند؛ Full-Universe برای ردیف‌های Rahavard قابل‌دسترسی است، نه تمام تاریخ محصول.
"""
marker = "## ۱۳. ضمیمه"
if marker in text:
    text = text[:text.index(marker)].rstrip() + "\n" + addendum
else:
    text += addendum
open(MAIN, "w", encoding="utf-8").write(text)
print("updated", MAIN, len(text))
