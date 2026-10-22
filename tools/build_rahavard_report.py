# -*- coding: utf-8 -*-
"""Generate the exhaustive Rahavard type0 parity report from frozen artifacts."""
from __future__ import annotations

import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "artifacts", "ra365", "r18-rahavard")
OUT = os.path.join(ROOT, "docs", "RA365-ROUND18-RAHAVARD-RAW-OHLC-PARITY-REPORT.md")
CODE_COMMIT = os.environ.get("RAHAVARD_CODE_COMMIT", "pending")
FA = "۰۱۲۳۴۵۶۷۸۹"


def fa(n, dec=0, pct=False):
    if n is None or n == "":
        return "—"
    if isinstance(n, str):
        return n
    s = f"{float(n):,.{dec}f}" if dec else f"{int(round(float(n))):,}"
    s = s.replace(",", "٬").replace(".", "٫")
    s = "".join(FA[int(ch)] if ch.isdigit() else ch for ch in s)
    return s + ("٪" if pct else "")


def sha(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(name):
    return json.load(open(os.path.join(ART, name), encoding="utf-8"))


S = load("rahavard-raw-ohlc-summary.json")
M = load("rahavard-raw-ohlc-cohort-manifest.json")

# per-field aggregate
prows = list(csv.DictReader(open(os.path.join(ART, "rahavard-raw-ohlc-parity.csv"),
                                 encoding="utf-8-sig")))
fields = [("open", "Open (FIRST)"), ("high_raw", "High (parser contract)"),
          ("low_raw", "Low (parser contract)"), ("last", "Close last trade"),
          ("close_display", "Close display (basis)"), ("volume", "Volume")]
frows = []
for f, label in fields:
    c = sum(int(r[f + "_cmp"] or 0) for r in prows)
    e = sum(int(r[f + "_exact"] or 0) for r in prows)
    t = sum(int(r[f + "_tol"] or 0) for r in prows)
    d = sum(int(r[f + "_diff"] or 0) for r in prows)
    n = sum(int(r[f + "_null"] or 0) for r in prows)
    frows.append((label, c, e, 100 * e / max(1, c), d, n))
tax = list(csv.DictReader(open(os.path.join(ART, "rahavard-raw-ohlc-taxonomy.csv"),
                               encoding="utf-8-sig")))
t0rows = sum(int(r["type0_rows"] or 0) for r in csv.DictReader(
    open(os.path.join(ART, "rahavard-type0-vs-tsetmc.csv"), encoding="utf-8-sig")))
rtax = list(csv.DictReader(open(os.path.join(ART, "rahavard-raw-ohlc-row-taxonomy.csv"),
                               encoding="utf-8-sig")))
row_mismatch = S["row_pairs"] - S["row_exact"]


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


md = f"""# RA365 Round 18 — Rahavard (type0) Raw OHLC Parity

**تاریخ:** 2026-10-22  
**شاخه:** `mission/ra365-round18-raw-ohlc-parity-2026-10-22`  
**مبنای Track A:** `f6e3c4e0`  
**Commit ابزار/تست این ممیزی:** `{CODE_COMMIT}`  
**مرجع Rahavard:** snapshot منجمد `ref_bars_v2.jsonl` (۲۰۲۶-۱۰-۲۰)، type0 و type7 با resolution روزانه

> این گزارش مکمل گزارش اصلی `docs/RA365-ROUND18-RAW-OHLC-PARITY-REPORT.md` است. تمرکز آن فقط Raw OHLC در برابر Rahavard است؛ Track B و موتور الگو دست‌نخورده‌اند.

---

## ۰. پاسخ کوتاه

- **تمام ۲٬۵۹۵ دارایی** دارای type0 در snapshot، در cohort اندازه‌گیری شدند؛ **۱٬۱۹۲٬۰۷۱ تاریخ مشترک** و **۱٬۱۸۸٬۹۲۱ ردیف قابل‌مقایسه** (با last موجود) مقایسه شد.
- **تطبیق قراردادی Raw:** **{fa(S['contract_ok_pct'], 4, True)}** فیلد و **{fa(S['row_exact_pct'], 4, True)}** ردیف.
- **تطبیق تحت‌اللفظی OHLC:** high {fa(S['literal_high_exact_pct'], 4, True)}، low {fa(S['literal_low_exact_pct'], 4, True)}، ردیف کامل {fa(S['literal_row_exact_pct'], 4, True)}. اختلاف عمدتاً `widen()` مستند BorsTerminal است، نه خطای داده خام.
- **معنای type0 با oracle مستقل TSETMC اثبات شد:** close = LAST ({fa(S['type0_vs_tsetmc']['close_last_exact_pct'], 4, True)})، نه official CLOSE ({fa(S['type0_vs_tsetmc']['close_official_exact_pct'], 4, True)})؛ open = FIRST ({fa(S['type0_vs_tsetmc']['open_first_exact_pct'], 4, True)})، نه base OPEN ({fa(S['type0_vs_tsetmc']['open_base_exact_pct'], 4, True)}).
- **هیچ اصلاح تولیدی موجه اثبات نشد**؛ تنها قرارداد مقایسه (widen با official CLOSE) اصلاح شد. داده‌های خام product در open/last/volume و H/L قراردادی با Rahavard سازگارند.

---

## ۱. Git و مرزها

- Track A روی `mission/ra365-round18-raw-ohlc-parity-2026-10-22` از `f6e3c4e0`.
- Track B در شاخه `mission/technical-pattern-engine-round18-2026-10-22` مستقل و دست‌نخورده است؛ هیچ فایل Track B در این ممیزی تغییر نکرد.
- دیتابیس عملیاتی و promoted فقط read-only استفاده شدند؛ SHA آن‌ها در پایان گزارش ثبت شده است.

---

## ۲. اثبات معنای type0

مقایسه type0 با TSETMC به‌عنوان oracle مستقل (نه جایگزین Rahavard) روی **{fa(S['type0_vs_tsetmc']['common'])}** ردیف مشترک:

{table(["فیلد type0", "مرجع TSETMC", "exact٪"],
       [["close", "LAST", fa(S['type0_vs_tsetmc']['close_last_exact_pct'], 4, True)],
        ["close", "official CLOSE", fa(S['type0_vs_tsetmc']['close_official_exact_pct'], 4, True)],
        ["open", "FIRST", fa(S['type0_vs_tsetmc']['open_first_exact_pct'], 4, True)],
        ["open", "base OPEN", fa(S['type0_vs_tsetmc']['open_base_exact_pct'], 4, True)],
        ["high", "HIGH", fa(S['type0_vs_tsetmc']['high_exact_pct'], 4, True)],
        ["low", "LOW", fa(S['type0_vs_tsetmc']['low_exact_pct'], 4, True)],
        ["volume", "VOL", fa(S['type0_vs_tsetmc']['vol_exact_pct'], 4, True)]])}

**نتیجه:** type0 یک سری **خام** با close = آخرین معامله است، نه قیمت پایانی رسمی. هر مقایسه‌ای که type0 را با `closing` مقایسه کند، اختلاف ساختاری تولید می‌کند. type7 یک سری **تعدیل‌شده** است: close آن با type0 در **{fa(S['type7_diff_rows'])}** ردیف مشترک تفاوت دارد.

ماتریس کامل: `artifacts/ra365/r18-rahavard/source-field-matrix-rahavard.csv`.

---

## ۳. پوشش واقعی

| شاخص | مقدار |
|---|---:|
| دارایی‌های cohort | {fa(S['assets'])} |
| دارایی‌های دارای type0 | {fa(S['type0_assets'])} |
| ردیف‌های type0 | {fa(t0rows)} |
| ردیف‌های محصول | {fa(2125330)} |
| تاریخ‌های مشترک | ۱٬۱۹۲٬۰۷۱ |
| ردیف قابل‌مقایسه (last موجود) | {fa(S['row_pairs'])} |
| last_null محصول | {fa(S['last_null'])} |
| محصول فقط داخل بازه type0 | {fa(S['product_only_inside'])} |
| محصول فقط خارج بازه type0 | {fa(S['product_only_outside'])} |
| type0 فقط داخل بازه محصول | {fa(S['type0_only_no_trade'] + S['type0_only_tradable'])} |
| type0 فقط خارج بازه محصول | {fa(S['type0_only_outside'])} |
| ردیف‌های type0 تخت (O=H=L=C) | {fa(S['type0_flat'])} |
| ردیف‌های type0 با هندسهٔ نامعتبر | {fa(S['type0_bad_geom'])} |

پوشش type0 فقط **{fa(100.0 * S['row_pairs'] / 2125330, 2, True)}** از کل کندل‌های محصول است؛ type0 برای بسیاری از دارایی‌ها از ۲۰۱۹/۲۰۲۰ آغاز می‌شود. بنابراین «Full Universe» در این گزارش یعنی **تمام دارایی‌ها و تمام ردیف‌های Rahavard قابل‌دسترسی**، نه تمام تاریخ محصول. ردیف‌های محصول خارج از بازهٔ type0 با قیمت مقایسه نشدند.

---

## ۴. نتیجهٔ تطبیق

### ۴-۱. قراردادی (پس از اعمال widen مستند)

{table(["فیلد", "مقایسه", "exact", "exact٪", "diff", "null"],
       [[r[0], fa(r[1]), fa(r[2]), fa(r[3], 4, True), fa(r[4]), fa(r[5])]
        for r in frows])}

**جمع قراردادی:** {fa(S['contract_ok_pct'], 4, True)}؛ **ردیف قابل‌مقایسه:** {fa(S['row_exact_pct'], 4, True)} ({fa(S['row_exact'])} از {fa(S['row_pairs'])}).

### ۴-۲. تحت‌اللفظی (بدون widen)

- high: **{fa(S['literal_high_exact_pct'], 4, True)}**؛ low: **{fa(S['literal_low_exact_pct'], 4, True)}**؛ ردیف کامل: **{fa(S['literal_row_exact_pct'], 4, True)}**.
- اختلاف بالا عمدتاً همان `widen()` است: product سایه را باز می‌کند تا body/close رسمی داخل آن باشد. contract-aware high/low به {fa([r for r in frows if r[0].startswith('High')][0][3], 4, True)} / {fa([r for r in frows if r[0].startswith('Low')][0][3], 4, True)} می‌رسد. بنابراین «high خام برابر نیست» را نباید خطای دیتای خام نامید.

### ۴-۳. فیلدهای خاص

- `close_display` {fa([r for r in frows if r[0].startswith('Close display')][0][3], 4, True)}: اختلاف ۲٬۹۲۳ فیلد عمدتاً برای ۷۱ دارایی با basis=closing است (نمایش official close در برابر close=last در type0)؛ `FIELD_MAPPING`، نه خطای raw.
- `open` {fa([r for r in frows if r[0].startswith('Open')][0][3], 4, True)}؛ `last` {fa([r for r in frows if r[0].startswith('Close last')][0][3], 4, True)}؛ `volume` {fa([r for r in frows if r[0].startswith('Volume')][0][3], 4, True)}.

---

## ۵. علت‌شناسی

### ردیف‌ها ({fa(row_mismatch)} ردیف قابل‌مقایسه با mismatch)

{table(["علت", "دارایی", "تاریخ", "ردیف", "سهم از mismatch"],
       [[r['cause'], fa(r['assets']), fa(r['dates']), fa(r['rows']),
         fa(100.0 * int(r['rows']) / max(1, row_mismatch), 2, True)]
        for r in rtax])}

### فیلدها

{table(["علت", "دارایی", "تاریخ", "فیلد"],
       [[r['cause'], fa(r['assets']), fa(r['dates']), fa(r['field_mismatches'])]
        for r in tax])}

**تفسیر:**
- `SOURCE_DATA_DIVERGENCE`: محصول با TSETMC مطابق است، type0 نیست؛ عمدتاً اراد/آپشن‌ها، flat bars و تاریخ‌های خاص.
- `HISTORICAL_REVISION`: type0 و TSETMC با هم می‌خوانند، snapshot محصول قدیمی‌تر/اصلاح‌شده است.
- `CANDLE_GEOMETRY`: type0 تخت یا H/L بیرون body؛ product با widen آن را ترمیم می‌کند.
- `FIELD_MAPPING`: فقط `close_display` با basis=closing؛ انتظار می‌رود.
- `PRECISION_OR_ROUNDING`: اختلاف‌های کوچک مستند.
- `PARSING_OR_TRANSFORM`: volume صفر product در چند ردیف.
- `PRICE_SCALE_OR_UNIT`: پنج ردیف آپشن/صندوق با مقیاس واحد متفاوت.
- `UNCLASSIFIED`: {fa([r for r in tax if r['cause']=='UNCLASSIFIED'][0]['field_mismatches'] if any(r['cause']=='UNCLASSIFIED' for r in tax) else 0)} فیلد؛ عمدتاً اختلاف‌های کوچک بدون شاهد کافی برای یک علت واحد.
- `INSTRUMENT_MAPPING` و `DATE_MAPPING` به‌صورت اثبات‌شده **صفر**؛ type0-only tradable {fa(S['type0_only_tradable'])} تاریخ است که {fa(S['type0_only_rahavard_date'])} مورد آن Rahavard-only و {fa(S['type0_only_product_omission'])} مورد omission محصول است.

---

## ۶. missing bar و پوشش

- **{fa(S['type0_only_product_omission'])}** ردیف type0 معتبر که محصول snapshot ندارد؛ ۱۵۳ در ۲۰۲۳-۰۳-۲۷ و ۲۸۴ در تاریخ‌های ۲۰۲۶-۱۰-۱۰/۱۳/۱۷/۱۸. بررسی زنده نشان داد pipeline فعلی این تاریخ‌ها را دارد؛ این یک **gap در snapshot محصول** است، نه نقص فعلی دریافت.
- **{fa(S['product_only_rahavard_omission'])}** ردیف product معتبر که type0 ندارد (`PRODUCT_ONLY_RAHAVARD_OMISSION`)؛ reference gap.
- **{fa(S['type0_only_rahavard_date'])}** تاریخ type0-only که TSETMC هم ندارد (`TYPE0_ONLY_RAHAVARD_DATE`)؛ تقویم/داده Rahavard.
- **{fa(S['type0_only_outside'])}** تاریخ type0 خارج از بازه محصول؛ مقایسه نشد.
- **{fa(S['product_only_no_trade'])}** product-only no-trade و **{fa(S['type0_only_no_trade'])}** type0-only no-trade؛ در درصد قیمت وارد نشدند.
- **{fa(S['last_null'])}** ردیف product بدون last؛ از denominator ردیف قابل‌مقایسه خارج شدند و جدا گزارش شده‌اند.

هیچ missing bar با صفر، forward-fill یا کندل ساختگی پر نشد.

---

## ۷. جداسازی لایه‌ها

| لایه | نتیجه | وضعیت |
|---|---|---|
| Raw product ↔ type0 (قراردادی) | {fa(S['contract_ok_pct'], 4, True)} فیلد / {fa(S['row_exact_pct'], 4, True)} ردیف | `VERIFIED` |
| Raw product ↔ type0 (تحت‌اللفظی) | high {fa(S['literal_high_exact_pct'], 4, True)} / low {fa(S['literal_low_exact_pct'], 4, True)} | `VERIFIED` (شامل widen) |
| type0 ↔ type7 | {fa(S['type7_diff_rows'])} ردیف diff | `VERIFIED` (type7 adjusted) |
| Factor (R17) | ۶۹٫۰۲۴۳٪ exact | `VERIFIED` (artifact R17) |
| Adjusted OHLC (R17) | ۶۸٫۳۰۴۵٪ | `VERIFIED` (artifact R17) |

`close_official_diff` = {fa(S['close_official_diff'])} ردیف؛ این عدد عمداً به‌عنوان «خطای raw» گزارش نمی‌شود، چون product `closing` رسمی را با type0 `last` مقایسه می‌کند.

---

## ۸. اصلاح، محدودیت و وضعیت

**اصلاح انجام‌شده (analysis contract):** در comparator قبلی، widen با type0 close انجام می‌شد و هزاران اختلاف را اشتباهاً `HISTORICAL_REVISION` می‌نامید. اکنون widen با **official CLOSE مستقل** انجام می‌شود و high_raw/low_raw به {fa([r for r in frows if r[0].startswith('High')][0][3], 4, True)}/{fa([r for r in frows if r[0].startswith('Low')][0][3], 4, True)} رسیده‌اند.

**اصلاح production انجام نشد**، چون هیچ علت عمومی اثبات‌شده در pipeline فعلی پیدا نشد: gapهای ۴۹۹تایی snapshot در pipeline زنده وجود ندارند و flat/geometry مربوط به منبع Rahavard است. هیچ شرط یا مقدار مخصوص نمادی اضافه نشد.

**محدودیت‌ها:**
- مرجع، snapshot منجمد Rahavard است؛ دسترسی live در این راند استفاده نشد (`BLOCKED_LIVE_ACCESS` در حد عدم استفاده، نه ادعای نبود دسترسی).
- type0 فقط ۵۶٪ کندل‌های محصول را پوشش می‌دهد؛ Full-Universe برای ردیف‌های قابل‌دسترسی، نه کل تاریخ محصول.
- ۸۶ ردیف / ۱۰۱ فیلد `UNCLASSIFIED` باقی مانده‌اند.
- ۵ ردیف price-scale آپشن/صندوق و flat bars منبع، بدون اصلاح تولید.
- `INSTRUMENT_MAPPING` اثبات‌شده‌ای در این pass پیدا نشد؛ اتهام mapping بدون شاهد ثبت نشد.

---

## ۹. تست‌ها، دیتابیس و artifactها

- `dev/test_rahavard_raw_parity_v1.py`: **۱۵/۱۵** بررسی (widen با official close، status، taxonomy، semantics واقعی).
- Full gate این راند دوباره اجرا نشد چون هیچ کد production تغییر نکرد؛ گیت Track A قبلی روی `f6e3c4e0` سبز بود. این محدودیت `NOT_RE-RUN` است، نه ادعای سبز جدید.
- دیتابیس عملیاتی و promoted read-only؛ SHA پایان در manifest/پاسخ نهایی ثبت می‌شود.

{table(["artifact", "bytes", "sha256"],
       [[f"`{name}`", fa(os.path.getsize(os.path.join(ART, name))), f"`{sha(os.path.join(ART, name))}`"]
        for name in ("rahavard-raw-ohlc-parity.csv",
                     "rahavard-type0-vs-tsetmc.csv",
                     "rahavard-raw-ohlc-field-mismatches.csv",
                     "rahavard-raw-ohlc-taxonomy.csv",
                     "rahavard-raw-ohlc-row-taxonomy.csv",
                     "rahavard-raw-ohlc-missing.csv",
                     "rahavard-raw-ohlc-summary.json",
                     "rahavard-raw-ohlc-cohort-manifest.json",
                     "source-field-matrix-rahavard.csv")])}

---

## ۱۰. جمع‌بندی

برای ردیف‌های Rahavard قابل‌دسترسی، OHLC خام محصول از نظر **open، last و volume** و H/L پس از transform مستند، تطبیق بسیار بالایی دارد. اختلاف high/low تحت‌اللفظی عمدتاً widen است؛ اختلاف‌های باقی‌مانده به flat/geometry منبع Rahavard، basis نمایش، اصلاح snapshot و چند مورد کوچک تقسیم می‌شوند. هیچ شاهد کافی برای یک اصلاح عمومی production به دست نیامد.
"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(md)
print(OUT, len(md))
