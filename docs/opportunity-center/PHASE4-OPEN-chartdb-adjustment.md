# Phase 4 Open Issue — chartdb / دفترِ تعدیل (Python ↔ Go)

**وضعیت: OPEN / DEFERRED TO PHASE 4.5**
**تاریخ ثبت: 2026-11-09 · کشف در: P0.9.4 · کامیت مبنا: 768b8594**

## چرا OPEN است

`dev/test_chart_fixture_b3.py` روی شش فایلِ `s1/chartdb_*` شکست می‌خورد:
`49 passed / 1 failed`. بررسیِ «goldens == oracle تازه» (پارس‌شده، 37 فایل) نشان
می‌دهد خروجیِ `chartdb` پایتون و Go یکی نیست. گلدن‌هایِ کامیت‌شده خروجیِ Go هستند
(تستِ Go سبز است)؛ oracle خروجیِ `api/chart.py::get_chart_db` است.

اصلاحِ کامل یعنی پورتِ زنجیرۀِ canonical تعدیل (engine/chain/coverage/rejection/correction
pack) به Go؛ این فراتر از دامنۀِ P0.9 است و در Phase 4.5 مستقل انجام می‌شود.
هیچ گلدنی برایِ سبزشدنِ تست بازنویسی نشد.

## بازتولید

```bash
PYTHONIOENCODING=utf-8 python dev/test_chart_fixture_b3.py
# chart fixture guard: 49 passed, 1 failed
# FAIL goldens equal a fresh oracle run (parsed JSON, 37 files) —
#   s1/chartdb_downtrend.json; s1/chartdb_dualspell.json; s1/chartdb_fund.json;
#   s1/chartdb_nodata.json; s1/chartdb_short.json; s1/chartdb_uptrend.json
```

## اختلافِ فیلد‌به‌فیلد و علتِ ریشه‌ای

| فیلد | پایتون (oracle) | Go (گلدن) | علتِ ریشه‌ای |
|---|---|---|---|
| `adjustCapability.availability` | `_functional_state(...)` با status/covered/window | غایب | Go زنجیرۀِ `_canonical_adjustment` را ندارد؛ فقط استابِ `adjustCapability` |
| `adjustCapability.chain_complete` / `chain_incomplete_events` | از `AE.chain_factors` | غایب | همان: خروجیِ `chain` در Go محاسبه نمی‌شود |
| `adjustCapability.coverage` | `_ledger_coverage(...)` | غایب | پوششِ دفتر در Go پورت نشده |
| `adjustCapability.corrections` | `AC.capability(symbol)` | غایب | بستۀِ تصحیحِ مرجع در Go واردِ این مسیر نیست |
| `adjustCapability.functional_status` / `functional_blockers` / `functional_reason` | محاسبه‌شده از داده | استابِ ثابت (`functional_available=false`) | Go قاعدۀِ `_functional_state` را ندارد |
| `adjustCapability.ledger_sharpened` / `ledger_ambiguous` | از `_sharpen_events_with_ledger` | غایب | دفترِ مبدأ در Go پورت نشده |
| `adjustCapability.indexed_available` | **حذف شده** (ادعایِ سخت‌کدِ بی‌مصرف) | `true` | پورتِ کهنه از قراردادِ قبل؛ ادعایِ بی‌سنجش |
| `candles[].date` / `src` / `symbol` | `candle_contract.from_db_row` | غایب | سازندۀِ ردیفِ مشترک در Go پورت نشده؛ Go فقط OHLCV می‌سازد |
| `adjustEvents[].source` | `base-price-discontinuity` (و `priceAdjust` پس از تیزکردن) | غایب | `adjustEvent`ِ Go فیلدِ Source ندارد |
| `adjustEvents[].date` برای رویدادِ 2026-09-10 | `2026-09-12` | `2026-09-10` | Go گامِ `_effective_event_dates` را ندارد |
| `adjustRejected` | لیستِ ردیف‌هایِ ردشده با `factor_status` | غایب | خطِ لولهِٔ merge/reject/correction در Go نیست |
| `adjustment` | پارامتر و کلید **حذف شده** | کلیدِ عددی + `?adjustment=0..3` | محورِ legacyِ Go که پایتون به‌عنوانِ «دستۀِ تزئینیِ بی‌مسیر» حذف کرد |

## شاهدِ تاریخِ 2026-09-10 ↔ 2026-09-12

- `adjust_events` در فیکسچر: `('عادی01','2026-09-10',0.95,'base-price-discontinuity')`.
- `price_history` فیکسچر برای همان نماد: 2026-09-08, 09-09, 09-12, 09-13… —
  یعنی 09-10 و 09-11 روزِ معامله نیستند.
- `api/chart.py::_effective_event_dates` (خط ~2310): «تاریخِ هر رویداد را به اولین
  کندلِ هم‌روز یا پس از آن می‌برد» ⇒ 09-12. Go تاریخِ خام را نگه می‌دارد.
- اثرِ عددی در این فیکسچر: `factors` یکسان است (اختلاف فقط در تاریخِ اعلامیِ رویداد)؛
  در دادهٔ واقعی می‌تواند زمانِ اعمالِ ضریب را جابه‌جا کند.

## سطحِ تأثیر

- `/api/chart-db/{symbol}`، `/api/fts/{symbol}` (بدنۀِ chartdb) و هر مصرف‌کنندۀِ
  `adjustCapability`/`adjustRejected` در Go.
- `frontend/src/features/technical/nahayatnegar/lib/adjustments.ts` بلوکِ
  `adjustCapability` را «تأیید نشده» در نبودِ فیلد می‌خواند؛ نبودِ فیلدها در Go
  یعنی UI توانِ تعدیل را محافظه‌کارانه نشان می‌دهد، نه ادعایِ نادرست.
- `indexed_available: true` تنها ادعایِ نادرستِ باقی‌مانده است.

## معیارِ پذیرش (Phase 4.5)

1. `dev/test_chart_fixture_b3.py` بدونِ بازنویسیِ گلدن‌ها سبز شود (37/37).
2. `adjustCapability` با همان کلیدها و معنایِ `_functional_state` تولید شود؛
   `indexed_available` حذف شود.
3. `candles[]` همان فیلدهایِ `candle_contract.from_db_row` را داشته باشد.
4. `adjustEvents[]` شاملِ `source` و تاریخِ **effective** باشد؛ `_effective_event_dates`
   با تستِ واحد پوشش داده شود.
5. `adjustRejected` با `factor_status` تولید شود.
6. تصمیمِ مالک دربارهٔ محورِ `adjustment`: حذف (هم‌راستا با پایتون) یا حفظ به‌عنوان
   قابلیتِ صریحِ Go با قراردادِ مستند و تستِ جدا.
7. پارادایمِ گلدن: منبعِ طلایی برایِ این شش فایل باید خروجیِ پایتون باشد، نه Go
   (تستِ Go باید به‌جایِ تولیدِ گلدن، آن را مصرف کند).

## شاهدِ پیشینی‌بودن

diff گلدن‌های `HEAD~1` و `HEAD` پس از حذفِ بلوکِ `fts` در هر شش فایل صفر است؛
کامیتِ P0 فقط بلوکِ FTS را بازتولید کرد. پیش از اصلاحِ امضایِ کهنهٔ
`get_chart_db(sym, 3)` در `tools/parity/gen_chart_golden.py`، این بررسی با
`TypeError` شکست می‌خورد و مقایسۀ محتوایی هرگز اجرا نمی‌شد.
