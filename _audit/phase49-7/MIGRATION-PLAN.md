# برنامهٔ انتقال به معماری جدید + اعتبارسنجی — Phase 4.9.7

**این فقط برنامه است؛ اجرا منوط به تصمیم مالک.** در همهٔ مراحل: Reference Archive فقط‌خواندنی می‌ماند؛ منطق موتور تعدیل/FTS/Runtime تغییر نمی‌کند؛ هیچ merge/release بدون مجوز مالک.

## ترتیب مراحل (وابستگی‌ها)
```
P0 تثبیت Archive → P1 Shared Metadata → P2 Technical candles → P3 adjustment events
                                   → P4 Go wiring → P5 Other Market Data → P6 AI prep
```

## P0 — تثبیت Reference Archive (پیش‌نیاز، انجام‌شده)
- manifest SHA-256 برای ۶۳ JSONL + DB (موجود: api_all_provenance.json). Archive immutable.
- اعتبارسنجی: تطابق SHA + شمارش ردیف ۱۵۴,۶۳۲,۹۳۳ ✓ (انجام شده در 4.9.5/4.9.6).

## P1 — ساخت Shared Metadata
- ورودی: universe.json + assets + pack تعدیل (ins_code) + taxonomy.
- خروجی: asset/۴۵,۱۵۷، mode_def/۶۳ + alias، usd_rate (از id=2)، id_crosswalk، provenance.
- اعتبارسنجی: شمارش دارایی = ۴۵,۱۵۷؛ یکگانگی asset_id؛ پوشش ins_code برای ۸۰۸ دارایی pack؛ FK integrity؛ نرخ دلار مطابق نمونه‌های اندازه‌گیری‌شده.
- بازگشت‌پذیر: DB جدید جداگانه؛ Archive دست‌نخورده.

## P2 — ساخت Technical candles (متمایز، پاک‌سازی‌شده)
- ورودی: reference_all.db (خواندن) یا JSONL (برای utc).
- تبدیل: حذف modeهای افزونه (real_close→last، type5→type0) طبق mode_def؛ حذف/علامت t=0؛ dedup identical؛ حفظ utc.
- خروجی: ≈۵۵,۰۵۷,۲۷۳ ردیف، ≈۵.۲۰ GB (برآورد).
- اعتبارسنجی (حیاتی):
  - reconciliation: ردیف متمایز = ۸۷,۹۴۲,۵۲۳ منهای padding؛ تطابق با مبدأ per-mode.
  - parity: روی cohort، close تعدیل‌شدهٔ Technical با reference type7 در تلورانس (معیار موجود 13-runtime).
  - پاک‌سازی: هیچ t=0 در عملیاتی؛ هیچ dup-t identical؛ utc حفظ شده.
  - alias: بازتولید real_close از last و type5 از type0 بیت‌به‌بیت.

## P3 — رویدادها/ضرایب تعدیل
- ورودی: pack تعدیل (factors.jsonl ۸,۲۸۰ step) + raw_ohlc.
- خروجی: adjustment_event + adjustment_factor + candle_build/tech_capture_run.
- اعتبارسنجی: زنجیرهٔ factor، type7 را بازتولید کند (rel_error≈0 روی ۶۲۲ verified step)؛ ۱,۳۵۸ unverified علامت‌دار (بی‌جعل)؛ lineage هر factor به ref_bars_sha256.

## P4 — اتصال Go Backend به Technical DB
- نمای price_history + adjust_events از Technical DB سرو شود (بدون تغییر منطق موتور).
- اعتبارسنجی: harness موجود 13-runtime parity + شواهد مرورگر ۳۰ نماد؛ مقایسهٔ خروجی چارت قبل/بعد (بیت‌به‌بیت در تلورانس).
- **گیت مالک**: پیش از جایگزینی منبع دادهٔ عملیاتی.

## P5 — Other Market Data DB (CODAL/TSETMC + top-lists آینده)
- اتصال منابع موجود CODAL/TSETMC به schema پیشنهادی؛ استخراج آیندهٔ top-lists رهاورد (اختیاری، با login مالک).
- اعتبارسنجی: خروجی موتورهای fundamental/mstat/confidence بدون تغییر؛ lineage با publish_date (بدون lookahead).

## P6 — آماده‌سازی آموزش AI
- corpus خام از Archive؛ ویژگی از Technical/Other؛ dataset_split (تصمیم مالک: split زمانی، حذف placeholder، پوشش کافی).
- اعتبارسنجی: lineage خام→ویژگی→برچسب→خروجی مدل با revision/provenance؛ بدون نشت زمانی.

## اصول اعتبارسنجی عمومی
- هر مرحله read-only روی Archive؛ خروجی در DB جداگانه؛ قابل‌بازگشت.
- هیچ PASS بدون شواهد واقعی (شمارش/parity/hash).
- اعداد از artifacts خام تولید می‌شوند (نه دست‌نویس).
- تصمیم اجرا/merge/release با مالک است.