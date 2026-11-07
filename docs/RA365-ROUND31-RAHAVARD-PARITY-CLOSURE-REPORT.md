# RA365 Round 31 — تطبیق کندل‌های قابل‌مشاهده با رهاورد

**تاریخ:** 2026-10-25  
**شاخه:** `mission/ra365-round31-rahavard-parity-closure-2026-10-25`، از HEAD تأییدشدهٔ R30 `3e397c527e6aac36b383c7172809034dd36b2f84`  
**Code/tests head:** `1d5e8a56` (نمایش literal + تست‌ها + refresh ارجاع‌های NAME:LINE؛ gate نهایی روی همین درخت)  
**وضعیت:** **PARTIAL — EXPLICIT REMAINING MISMATCHES** (هدف ۱۰۰٪ حاصل نشد؛ هیچ اختلافی حذف یا پنهان نشد)

## ۱. تغییر واقعی محصول: OHLC قابل‌مشاهده literal شد

شاهد رهاورد: type7 رهاورد سایه‌ها را widen نمی‌کند و همان extremeهای literal type0 را نگه می‌دارد. نمونهٔ اندازه‌گیری‌شده در corpus منجمد (asset 6، 1996-09-16):

```
type0: O=4022 H=4020 L=4020 C=4020      (H < O — هندسهٔ «ناممکن»)
type7: O=7.48072 H=7.47699 L=7.47699 C=7.47699
factor = 0.00185995؛ H_type7 = H_type0 × factor
```

محصول قبلاً با `widen()` سایه را باز می‌کرد تا بدنه داخل آن بنشیند؛ بنابراین candle قابل‌مشاهده با رهاورد فرق داشت. در R31:

- `_literal_display_candles()` اضافه شد: `high/low` نمایشی از `high_raw/low_raw` می‌آید؛ `open/close` و فیلدهای خام دست‌نخورده می‌مانند.
- `/api/chart/{symbol}` به wrapper `get_chart_visible` وصل شد.
- `/api/chart-db/{symbol}` (مسیر صفحهٔ تکنیکال) به wrapper `get_chart_db_visible` وصل شد.
- capture tool و live-capture tool هم از همان قاعده استفاده می‌کنند تا اندازه‌گیری، مسیر واقعی نمایش را بازتاب دهد.

این تغییر **تعریف معیار نیست**؛ خود دادهٔ نمایشی محصول تغییر کرده است. `widen()` برای تشخیص‌های هندسی و قرارداد TSETMC حفظ شده، ولی دیگر روی candle نمایشی اعمال نمی‌شود.

## ۲. نتیجهٔ سراسری (مرجع منجمد R26، D/W/M)

| معیار | R30 (نمایش widen) | R31 (نمایش literal، code-only) | R31 + دادهٔ session anomaly |
|---|---:|---:|---:|
| D adjusted tolerance | 58.8564 | **64.5905** | **65.3927** |
| W adjusted tolerance | 59.7507 | **63.8787** | **64.6503** |
| M adjusted tolerance | 58.7457 | **62.0936** | **62.8039** |
| D raw literal | 99.8482 | 99.8482 | 99.8482 |
| W raw literal | 98.9789 | 98.9789 | 98.9789 |
| M raw literal | 96.3259 | 96.3259 | 96.3259 |

- دامنه: ۱٬۱۹۴٬۴۴۶ ردیف D، ۲۷۵٬۷۷۶ W، ۶۹٬۲۶۸ M؛ ۱٬۹۸۹ دارایی paired.
- D adjusted exact OHLC (هر چهار فیلد، ۱e-9): **306,955 / 1,194,446 = 25.6985%**.
- D adjusted tolerance: **781,081** ردیف منطبق، **413,365** نامنطبق.
- W: 178,290 منطبق / 97,486 نامنطبق؛ M: 43,503 / 25,765.
- raw literal D: 1,192,633 exact / 1,194,446؛ H/L/O/C exact هر کدام حدود 99.9% (جدول کامل در `visible-metrics.txt`).
- دادهٔ session anomaly فقط روی کپی ایزوله (`D:/BorsTerminal-tmp/r30_data/market.db`) اعمال شده است؛ DB عملیاتی/promoted تغییر نکرد. therefore code-only قابل‌تحویل 64.5905 است و 65.3927 فقط code+data است.

## ۳. مسیر واقعی /api/chart (۳۰ نماد)

- ۳۰/۳۰ پاسخ `success`؛ در همهٔ candles دارای تاریخ مشترک، `high == high_raw` و `low == low_raw` است (wrapper literal).
- مقایسه با corpus منجمد: raw H/L exact **4,183 / 4,845** و tolerance **4,471 / 4,845**؛ اختلاف باقی‌مانده عمدتاً revision فید زندهٔ TSETMC (۲۰۲۶-۱۰-۲۵) در برابر snapshot منجمد (۲۰۲۶-۱۰-۲۰) است، نه widen.
- factor chain: ۲۷/۳۰ همان replay؛ ساراب/وتوسم/پكوير فقط revision دارند (گزارش R30).
- adjusted این ۳۰ نماد ۷.۷۴٪ است؛ این مجموعه عمداً از سخت‌ترین نمادها انتخاب شده، نه میانگین بازار. اعداد سراسری در §۲ است.

## ۴. اختلاف‌های باقی‌مانده و مانع دقیق

۴۱۳٬۳۶۵ ردیف D هنوز از tolerance عبور نمی‌کند. علت‌ها همان طبقه‌بندی R30 است:

- **base-gap / unproven-gap precision بدون ردیف رسمی:** ۵۴۳ step / ۱۹,۱۶۶ ردیف یک‌مرحله‌ای قابل‌بازیابی. نسبت مشاهده‌شدهٔ gap با نسبت مرجع ۰.۱–۱٪ فرق دارد؛ بدون `S`/نسبت رسمی، تغییر آن حدس است.
- **reference-only:** ۳۷۸ step / ۱۰,۵۶۴ ردیف؛ هیچ ردیف رسمی share/PA/fund نزدیک ندارند. import رویداد مرجع ممنوع است.
- **DPS/fund precision:** حدود ۴.۵k ردیف؛ مبلغ DPS مرجع با پورتال ۰.۵–۲.۶٪ فرق دارد و قاعدهٔ عمومی مالیات/گردکردن وجود ندارد.
- **base gap + DPS/share و رویدادهای ترکیبی:** حدود ۵k ردیف؛ بدون سند رسمی برای leg حذف‌شده قابل انتخاب نیست.
- **raw source divergence/revision:** ۱٬۸۱۳ ردیف D raw literal؛ product از TSETMC و مرجع از Rahavard می‌آید؛ بدون تغییر مجاز منبع خام، ۱۰۰٪ literal ممکن نیست.
- attempted fixes in R30 (share-in-halt و mapped-DPS) به‌دلیل پسرفت سراسری revert شدند و در R31 دوباره اعمال نشدند.

**هیچ اختلافی از مخرج حذف نشد؛ هیچ ردیف reference-only/ product-only حذف نشد؛ هیچ نسبت مرجعی کپی نشد.**

## ۵. تست‌ها و gate

- `dev/test_ra365_round31_visible_hl_v1.py`: **7/7** (literal display، `high_raw` preservation، open/close immutability، wrapper هر دو مسیر).
- `dev/test_ra365_round30_chart_route_v1.py`: **3/3**.
- رگرسیون‌های هدفمند: R29 6/6، R15 21/21، R25 9/9 و 6/6، unproven-base 10/10، R18 raw 37/37، candle_contract 22/22.
- Full gate نهایی روی `1d5e8a56` و DB ایزوله `D:/BorsTerminal-tmp/r31_gate3` (TMP/SQLITE_TMPDIR روی D): **215 OK / 0 FAIL / 2 skip**، 157 suite + 58 silent، **`ALL SUITES PASSED`**، exit 0، **`PROTECTED_DB_UNCHANGED`** (`logical_total=1d9bc9b4…`). skipها: fixtureهای مستند `ra365_ref_bars.json` و `market.db.lzma`.
- تلاش ۱ با `No space left on device` روی temp درایو C شکست خورد؛ تلاش ۲ فقط ارجاع‌های `NAME:LINE` را پس از +۳۷ خط قدیمی دید. هر دو در `full-gate-attempt1-diskfull.log` و `full-gate-attempt2-citation.log` حفظ شده‌اند؛ citation با `_audit/fix_rule_map_lines.py` به 11/11 اصلاح شد.
- DB محافظت‌شده `e08d8062…`؛ promoted `8fb85f38…`؛ DB تست session `d9da8671…`؛ هر دو DB محافظت‌شده byte-identical ماندند.

## ۶. بازتولید

```bash
# سنجش دیداری سراسری (پس از capture با capture tool فعلی)
python tools/ra365_round30_audit_literal_hl.py \
  --ref D:/BorsTerminal-tmp/r26_bench/frozen/ref_bars_v2.jsonl \
  --product D:/BorsTerminal-tmp/r30_data_cluster,D:/BorsTerminal-tmp/r29_bench/full_shard0,...,D:/BorsTerminal-tmp/r29_bench/full_shard5 \
  --cohort D:/BorsTerminal-tmp/ra365_round18/cohort.jsonl \
  --out artifacts/ra365/r31/visible-data-audit

# مسیر زنده (DB ایزوله)
BORS_DB=D:/BorsTerminal-tmp/r31_live/market.db \
python tools/ra365_round30_live_capture.py --symbols "..." --out D:/BorsTerminal-tmp/r31_live/payloads
```

- `artifacts/ra365/r31/visible-metrics.txt`: جدول کامل فیلدها/دقت.
- `artifacts/ra365/r31/exact-visible.json`: exact OHLC.
- `artifacts/ra365/r31/live-visible-check.json`: ۳۰ نماد.
- `artifacts/ra365/r31/full-gate.log`: gate.

## ۷. حکم

**PARTIAL — EXPLICIT REMAINING MISMATCHES.** تغییر واقعی و قابل‌مشاهدهٔ محصول انجام شد: OHLC نمایشی از widen به literal رهاورد تغییر کرد و adjusted tolerance از 58.8564 به 64.5905 (code-only) و 65.3927 (با دادهٔ session روی کپی) رسید؛ raw literal 99.8482 است. اما ۴۱۳٬۳۶۵ ردیف D هنوز منطبق نیست و علت‌های آن (precision بدون سند رسمی، reference-only، DPS، source divergence) با شواهد موجود قابل‌رفع بدون کپی مرجع یا حدس نیستند. بنابراین `PARITY_100_PERCENT_VERIFIED` اعلام نمی‌شود.

**گام بعدی لازم:** تأمین نسبت‌های رسمی/`S` یا CODAL برای خانواده‌های precision، تصمیم مالک دربارهٔ منبع خام (TSETMC در برابر Rahavard)، و سپس بازسازی زنجیرهٔ رویدادها با شواهد مستقل. مرحلهٔ آیندهٔ موتور آینده‌نگر نیز پس از تثبیت همین مبنا اجرا می‌شود.
