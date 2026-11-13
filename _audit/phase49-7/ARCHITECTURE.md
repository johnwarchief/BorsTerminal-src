# معماری جداسازی دیتابیس تکنیکال از سایر داده‌های بازار — Phase 4.9.7

طراحی بر پایهٔ **محتوای واقعی** کشف‌شده (نه حدس). این یک **پیشنهاد** است؛ اجرا منوط به تصمیم مالک. هیچ DB/موتوری در این مأموریت تغییر نکرده.

## اصل حاکم (یافتهٔ کلیدی)
آرشیو رهاورد **فقط کندل + متادیتای عمومی دارایی** است (تأییدشده از کد استخراج). دادهٔ بنیادی/جریان پول/دفتر سفارش/شاخص استخراج نشده. پس جداسازی در عمل یعنی:
۱. جدا کردن **انبار مرجع سرد** (faithful) از **انبار تکنیکال گرم** (عملیاتی، پاک‌سازی‌شده).
۲. تعریف لایهٔ **Shared Metadata** به‌عنوان تنها منبع حقیقت شناسه‌ها.
۳. تعریف **Other Market Data DB** که از CODAL/TSETMC (منابع موجود BorsTerminal) + استخراج آیندهٔ top-lists رهاورد تغذیه می‌شود — نه از آرشیو فعلی رهاورد.

## نمای چهارلایه
```
Reference Archive (سرد، immutable، ۳۴٫۴ GB)  ← منبع حقیقت parity + بازتولید
        │ مشتق (خواندن، بدون تغییر مبدأ)
        ▼
Shared Metadata (asset/mode/fx/crosswalk)  ← کلید مشترک asset_id
        │ FK                         │ FK
        ▼                            ▼
A. Technical Market DB (گرم)     B. Other Market Data DB
   کندل/تعدیل/تقویم/منشأ            بنیادی/جریان پول/دفتر سفارش/شاخص
   ~۵.۲۰ GB (پاک‌سازی‌شده)        از CODAL/TSETMC + top-lists آینده
```

## A. Technical Market Database
**هدف**: تغذیهٔ موتورهای قیمت‌محور (Technical، FTS لایهٔ setup، Forecasting، Regime، Volatility، قیمت Portfolio).
**محتوا**: OHLCV (D/W/M)، پایه‌های قیمت، خام + عملکردی، رویدادها/ضرایب تعدیل، تقویم معاملاتی (در صورت وجود)، نگاشت asset_id (FK به Shared)، متادیتا/منشأ تکنیکال، ویژگی‌های مشتق (اختیاری).

### Schema پیشنهادی (کلیدها و ارتباطات)
- `candle(candle_id PK, asset_id FK, res, basis, adj, t, utc, o, h, l, c, v, is_placeholder)` — پس از پاک‌سازی: حذف t=0 و dedup identical → UNIQUE(asset_id,res,basis,adj,t).
- `adjustment_event(event_id PK, asset_id FK, ins_code, effective_date, kind, ratio, cum_factor_after, source, confidence, event_sig, correction_version)` — از pack تعدیل.
- `adjustment_factor(asset_id FK, date, factor, revision, PK(asset_id,date,revision))` — ضریب تجمعی per-bar (مطابق market43).
- `trading_calendar(date PK, is_trading_day, session_phase)` — **شکاف**: در آرشیو رهاورد نیست؛ از BorsTerminal marketphase یا تقویم TSE تأمین شود.
- `tech_capture_run(run_id PK, source, captured_at, input_sha256, types, resolutions, symbols, bars)` + `candle_build(asset_id FK, revision, raw_rows, adjusted_rows, max_rel_error, built_at)` — منشأ/lineage.
- `derived_feature(asset_id FK, date, feature_key, value, model_revision)` — اختیاری، برای آموزش.

### پاک‌سازی و نرمال‌سازی (با حفظ parity در Archive)
- **حذف افزونگی**: real_close≡last و type0≡type5 → به‌جای ۶۳ mode، **۳۶ mode متمایز** نگه داشته می‌شود؛ نگاشت alias در Shared.mode_def. صرفه‌جویی: ۶۶,۶۹۰,۴۱۰ ردیف (۴۳.۱۰٪).
- **حذف placeholder**: کندل‌های t=0 (≈۳۲,۸۸۵,۲۵۰ در W/M) از انبار عملیاتی حذف/علامت‌گذاری می‌شوند (در Archive faithful می‌مانند).
- **dedup identical**: ۱۱ دارایی D با bar تکراری identical → یک نمونه نگه داشته می‌شود (در Archive هر دو می‌مانند).
- **حفظ utc**: فیلد utc/offset که DB مرجع حذف کرده بود، در Technical DB نگه داشته می‌شود.

### حجم
- فعلی (مرجع ۶۳ mode): ۱۴.۶۱ GB، ۱۵۴,۶۳۲,۹۳۳ ردیف.
- پس از تفکیک (متمایز، بدون padding): ≈۵.۲۰ GB، ≈۵۵,۰۵۷,۲۷۳ ردیف (برآورد).
- میانی (متمایز با padding): ≈۸.۳۱ GB، ۸۷,۹۴۲,۵۲۳ ردیف.

### به‌روزرسانی/ورود داده
- ingest افزایشی از `/api/v2/chart/bars` (login مالک) + بازسازی pack تعدیل؛ upsert idempotent بر اساس (asset_id,res,basis,adj,t)؛ log تعارض (مطابق candle_ingest_conflicts).
- هر run با input_sha256 + revision ثبت می‌شود (lineage خام→پردازش‌شده).

### استفاده توسط Go Backend
- نمای `price_history(date, close, volume, last)` از candle (basis=close/last، adj=functional) سرو می‌شود — همان که `backend-go/internal/chart/chartdb.go` می‌خواند.
- `adjust_events`/`adjustment_factor` → موتور تعدیل (بدون تغییر منطق؛ فقط منبع داده).

### آماده‌سازی آموزش AI
- corpus خام از Reference Archive (faithful)؛ ویژگی‌ها از Technical DB؛ برچسب‌ها با revision/provenance به کندل مبدأ متصل می‌مانند (lineage خام→ویژگی→خروجی مدل).
- dataset_split (آموزش/اعتبار/آزمون) تصمیم مالک؛ پیشنهاد: split زمانی (بدون نشت آینده) + حذف placeholder + نمادهای دارای پوشش کافی.

## B. Other Market Data Database
**هدف**: موتورهای بنیادی/جریان (Fundamental، Market Intelligence/mstat، Adaptive Signal/confidence، گیت‌های بنیادی FTS، sector در Portfolio).
**محتوای واقعی از رهاورد**: **هیچ** (فقط متادیتای دارایی که به Shared می‌رود). این DB از منابع دیگر تغذیه می‌شود:
| دسته | منبع | وضعیت در BorsTerminal |
|---|---|---|
| صورت مالی / monthly_sales / EPS / codal_notices | CODAL | موجود (api/fundamental.py، backend-go/internal/fundamental) |
| instruments (sector/total_shares/asset_class) | TSETMC | موجود |
| market_watch / client_type (حقیقی/حقوقی) / دفتر سفارش blDs | TSETMC | موجود (mstat_engine) |
| instrument_state / ask-bid / value / اثر شاخص | Rahavard top-lists | **استخراج نشده** (probe شد) — استخراج آینده |
| مقادیر شاخص / صنایع/گروه‌ها | TSETMC/Rahavard | نیازمند تأمین |

### Schema پیشنهادی
- `instrument(asset_id FK, ins_code, sector, total_shares, asset_class, …)`
- `financial_statement(asset_id FK, fiscal_year, period, field, value, source, publish_date)`
- `monthly_sales(asset_id FK, month, value, …)` ، `codal_notice(asset_id FK, publish_date, kind, …)`
- `market_watch(asset_id FK, date, p_closing, …)` ، `client_type(asset_id FK, date, real_buy, real_sell, legal_buy, legal_sell, …)`
- `order_book_depth(asset_id FK, ts, level, ask_price, ask_count, bid_price, bid_count)`
- `index_value(index_id, date, value)` ، `industry(industry_id, name)` ، `top_list_snapshot(list_id, exchange_id, ts, asset_id FK, rank, metrics_json)`
- کلید: asset_id FK به Shared؛ اتصال بیرونی با ins_code/symbol/codal_id.

### حجم/به‌روزرسانی/استفاده
- حجم: وابسته به CODAL/TSETMC (سهم رهاورد = ۰ فراتر از متادیتا). به‌روزرسانی: fetch CODAL + فید زندهٔ TSETMC (موجود) + top-lists آینده.
- Go: `internal/fundamental`، `internal/mstat`، `confidence_engine` این جداول را می‌خوانند (بدون تغییر منطق).
- آموزش AI: ویژگی‌های بنیادی برای FTS/fundamental؛ lineage با publish_date (بدون نشت lookahead).

## C. Shared Metadata
**هدف**: اتصال A و B بدون تکرار متادیتا؛ تنها منبع حقیقت شناسه‌ها.
- `asset(asset_id PK, trade_symbol, name, short_name, exchange, type_id, type_name, asset_class, ins_code, unlisted, encoding_corrupt, has_candles, modes_count, candle_rows)` — از universe + assets + pack.
- `asset_alias(asset_id FK, alias_symbol, kind)` — گونه‌های نماد.
- `mode_def(mode_key PK, res, basis, adj, meaning, alias_of)` — ۶۳ mode + نگاشت افزونگی (real_close→last، type5→type0).
- `usd_rate(date PK, rate_rial, source_asset_id=2)` — نرخ دلار برای تبدیل USD (از دارایی id=2).
- `id_crosswalk(asset_id FK, ins_code, codal_id, tsetmc_id)` — پل به منابع بیرونی.
- `provenance(key PK, value)` — منشأ/نسخه/SHA.
- حجم: کوچک (≈۴۵٬۱۵۷ دارایی، ~۵۰ MB). به‌روزرسانی: refresh universe + نگهداری crosswalk.

## آنچه در Reference Archive می‌ماند vs منتقل می‌شود
| قلم | جایگاه | دلیل |
|---|---|---|
| ۶۳ JSONL + reference_all.db (faithful، padding/dup حفظ) | Archive (سرد) | منبع parity + بازتولید؛ immutable |
| .orig / errors.jsonl / probeها | Archive | provenance/کیفیت استخراج |
| کندل متمایز پاک‌سازی‌شده + utc | Technical DB (گرم) | مصرف عملیاتی موتورهای قیمت‌محور |
| رویداد/ضریب تعدیل + منشأ ساخت | Technical DB | بازتولید عملکردی |
| asset master + mode_def + usd_rate + crosswalk | Shared Metadata | کلید مشترک، بی‌تکرار |
| بنیادی/جریان/دفتر سفارش/شاخص | Other Market Data DB | از CODAL/TSETMC/top-lists آینده |

## وابستگی‌ها و اطلاعات مشترک
- هر دو DB عملیاتی به Shared.asset با FK asset_id متصل‌اند؛ متادیتا یک‌بار نگه داشته می‌شود.
- Technical به usd_rate (Shared) برای بازتولید *_usd نیاز دارد؛ Other به id_crosswalk برای اتصال CODAL/TSETMC.
- Archive منبع lineage است: هر رکورد عملیاتی با revision/input_sha256 به کندل خام Archive قابل‌ردیابی است.