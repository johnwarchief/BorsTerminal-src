# نقشهٔ ارتباطی داده‌ها و شناسه‌ها — Phase 4.9.7

## کلید مرکزی: `asset_id`
`asset_id` رهاورد (= `entity_id` در universe = `asset_id` در JSONL/DB) کلید جهانی اتصال همهٔ داده‌هاست.

## نگاشت شناسه‌ها
| از | به | کاردینالیتی | منبع |
|---|---|---|---|
| asset_id | trade_symbol | ۱:۱ (۳٬۷۲۸ فاقد نماد) | universe/assets |
| asset_id | type_id → type → asset_class | ۱:۱ (۱۷ نوع) | universe + taxonomy |
| asset_id | exchange (بازار) | ۱:۱ | universe |
| asset_id | ins_code (TSETMC) | ۱:۱ در pack تعدیل | factors.jsonl |
| symbol | asset_id | چند:۱ در pack (۹۵۱ symbol → ۸۰۸ asset_id) | corrections manifest |
| asset_id | mode_key (res/basis/adj) | ۱:چند (تا ۶۳) | series |

## زنجیرهٔ lineage (خام → مشتق)
```
Rahavard API (/api/v2/chart/bars)
  → bars_{res}_{basis}_{adj}.jsonl  {asset_id, trade_symbol, name, n, bars[time,utc,OHLCV]}
  → reference_all.db.candles        {asset_id, res, basis, adj, t, o,h,l,c, v}  (utc حذف)
  → metadata.db.series              {asset_id, mode_key, rows, first_t, last_t}
universe.json → reference_all.db.assets → metadata.db.asset
corrections pack (factors/raw_ohlc) → market43.db.adjustment_factors/adjusted_candles
```

## گره‌های ویژه
- **دارایی دلار id=2**: کلید تبدیل USD. `close_usd = close / close(id=2)`. باید در Shared Metadata به‌عنوان series نرخ ارز نگه داشته شود.
- **mode_key**: ترکیب `{res}/{basis}/{adj}` (مثال D/close/type7). ۶۳ mode = ۷×۳×۳؛ اما real_close≡last و type0≡type5 → سری‌های متمایز کمتر از ۶۳.
- **ins_code**: کد ابزار TSETMC در pack تعدیل (نمونهٔ ۱۷ رقمی)؛ پل بین symbol بورسی و asset_id رهاورد.

## کاردینالیتی‌های کلیدی
- universe: ۴۵,۱۵۷ دارایی | دارای کندل: ۱۰,۷۱۵ | series: ۴۵۷,۷۱۲ | کندل: ۱۵۴,۶۳۲,۹۳۳.
- pack تعدیل v2: ۹۵۱ symbol، ۸۰۸ asset_id، ۹۱۷ ins_code، ۸,۲۸۰ step (dps=۳,۰۴۵، product=۱,۵۵۵، fund_dps=۱,۱۲۲، share=۹۲۱، base_gap=۵۴۸).
- market43.db (نمونهٔ عملیاتی): ۴۳ symbol، ۱۲۲,۹۴۴ کندل تعدیل‌شده، ۹۱۰ factor.

## اتصال دو دیتابیس پیشنهادی (Shared Metadata)
`asset_id` کلید مشترک Technical DB و Other Market Data DB است. جدول `asset` (شناسه/نماد/نوع/بازار) یک‌بار در Shared Metadata نگه داشته می‌شود و هر دو DB با FK به آن ارجاع می‌دهند؛ از تکرار متادیتا جلوگیری می‌شود. `ins_code` و `trade_symbol` به‌عنوان کلیدهای جایگزین برای اتصال به منابع بیرونی (TSETMC/CODAL) نگه داشته می‌شوند.