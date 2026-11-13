# گزارش مستقل محتوای هر ۶۳ فایل JSONL — Phase 4.9.7

اسکن read-only کامل (شمارش خط + مجموع n + بررسی schema). نتیجه: **۶۳ فایل، schema یکسان (۱ variant)، بدون رکورد asset تکراری در هیچ فایل**.
- مجموع رکوردها (asset-mode): ۴۵۷,۷۱۲ | مجموع کندل‌ها: ۱۵۴,۶۳۲,۹۳۳ | حجم: ۱۹,۷۷۱,۹۲۵,۵۳۷ بایت.
- تطابق با DB: مجموع کندل JSONL == ردیف candles DB == ۱۵۴,۶۳۲,۹۳۳ ✓ (استخراج faithful).

ساختار هر رکورد: `{asset_id, trade_symbol, name, n, bars[{time, utc, open, high, low, close, volume}]}`.

| # | فایل | mode | رکورد | کندل | حجم | اولین asset | schema |
|---|---|---|---|---|---|---|---|
| ۱ | bars_D_close_type0.jsonl | D_close_type0 | ۷,۴۳۶ | ۴,۶۹۶,۴۵۹ | ۵۷۶,۱۱۴,۴۷۵ | 19692 (آفاق) | یکسان |
| ۲ | bars_D_close_type5.jsonl | D_close_type5 | ۷,۴۳۶ | ۴,۶۹۶,۴۶۱ | ۵۷۶,۱۱۴,۶۸۷ | 19692 (آفاق) | یکسان |
| ۳ | bars_D_close_type7.jsonl | D_close_type7 | ۷,۴۳۶ | ۴,۶۹۶,۴۶۱ | ۶۹۶,۸۹۷,۲۷۴ | 19692 (آفاق) | یکسان |
| ۴ | bars_D_close_usd_type0.jsonl | D_close_usd_type0 | ۷,۴۲۵ | ۴,۶۹۵,۸۶۳ | ۷۰۳,۶۶۳,۱۹۴ | 19692 (آفاق) | یکسان |
| ۵ | bars_D_close_usd_type5.jsonl | D_close_usd_type5 | ۷,۴۳۶ | ۴,۶۹۶,۱۱۷ | ۷۰۳,۶۹۳,۵۲۰ | 1654 (آتیه ملت) | یکسان |
| ۶ | bars_D_close_usd_type7.jsonl | D_close_usd_type7 | ۷,۴۳۶ | ۴,۶۹۶,۱۱۷ | ۷۱۹,۹۳۶,۶۳۵ | 1654 (آتیه ملت) | یکسان |
| ۷ | bars_D_last_type0.jsonl | D_last_type0 | ۷,۴۳۶ | ۴,۶۹۶,۱۱۷ | ۵۷۶,۰۷۰,۴۰۵ | 1654 (آتیه ملت) | یکسان |
| ۸ | bars_D_last_type5.jsonl | D_last_type5 | ۷,۴۳۶ | ۴,۶۹۶,۱۱۷ | ۵۷۶,۰۷۰,۴۱۶ | 36208 (پاسارگاد) | یکسان |
| ۹ | bars_D_last_type7.jsonl | D_last_type7 | ۷,۴۳۶ | ۴,۶۹۶,۲۲۹ | ۶۹۶,۸۳۱,۳۱۵ | 19692 (آفاق) | یکسان |
| ۱۰ | bars_D_last_usd_type0.jsonl | D_last_usd_type0 | ۷,۴۳۶ | ۴,۶۹۶,۴۴۲ | ۵۷۶,۱۰۹,۶۹۳ | 19692 (آفاق) | یکسان |
| ۱۱ | bars_D_last_usd_type5.jsonl | D_last_usd_type5 | ۷,۴۳۶ | ۴,۶۹۶,۴۴۲ | ۵۷۶,۱۰۹,۷۵۶ | 1654 (آتیه ملت) | یکسان |
| ۱۲ | bars_D_last_usd_type7.jsonl | D_last_usd_type7 | ۷,۴۳۶ | ۴,۶۹۶,۴۴۴ | ۶۹۶,۸۵۷,۴۳۴ | 33197 (ارکیده) | یکسان |
| ۱۳ | bars_D_market_cap_type0.jsonl | D_market_cap_type0 | ۷,۴۲۰ | ۴,۶۹۵,۹۵۹ | ۶۳۲,۸۷۸,۴۶۹ | 461 (وتجارت) | یکسان |
| ۱۴ | bars_D_market_cap_type5.jsonl | D_market_cap_type5 | ۷,۴۲۰ | ۴,۶۹۵,۹۷۳ | ۶۳۲,۸۸۰,۰۷۶ | 461 (وتجارت) | یکسان |
| ۱۵ | bars_D_market_cap_type7.jsonl | D_market_cap_type7 | ۷,۴۲۰ | ۴,۶۹۵,۹۷۳ | ۶۳۲,۸۸۰,۱۰۵ | 461 (وتجارت) | یکسان |
| ۱۶ | bars_D_market_cap_usd_type0.jsonl | D_market_cap_usd_type0 | ۷,۴۲۰ | ۴,۶۹۵,۹۷۳ | ۷۳۲,۶۸۱,۰۰۴ | 461 (وتجارت) | یکسان |
| ۱۷ | bars_D_market_cap_usd_type5.jsonl | D_market_cap_usd_type5 | ۷,۴۲۰ | ۴,۶۹۵,۹۷۳ | ۷۳۲,۶۸۱,۰۳۵ | 461 (وتجارت) | یکسان |
| ۱۸ | bars_D_market_cap_usd_type7.jsonl | D_market_cap_usd_type7 | ۷,۴۲۰ | ۴,۶۹۵,۹۷۳ | ۷۳۲,۶۸۱,۰۵۴ | 461 (وتجارت) | یکسان |
| ۱۹ | bars_D_real_close_type0.jsonl | D_real_close_type0 | ۱۰,۷۱۵ | ۴,۹۳۹,۳۴۴ | ۶۰۵,۴۱۶,۷۹۳ | 600 (انفورماتیک) | یکسان |
| ۲۰ | bars_D_real_close_type5.jsonl | D_real_close_type5 | ۷,۴۳۲ | ۴,۶۹۲,۱۷۷ | ۵۷۵,۵۶۹,۸۴۴ | 1654 (آتیه ملت) | یکسان |
| ۲۱ | bars_D_real_close_type7.jsonl | D_real_close_type7 | ۷,۴۳۶ | ۴,۶۹۶,۱۱۷ | ۶۹۶,۸۱۷,۸۰۸ | 19692 (آفاق) | یکسان |
| ۲۲ | bars_M_close_type0.jsonl | M_close_type0 | ۷,۴۳۵ | ۱,۰۸۳,۱۳۶ | ۱۰۴,۹۰۱,۵۰۹ | 19692 (آفاق) | یکسان |
| ۲۳ | bars_M_close_type5.jsonl | M_close_type5 | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۰۴,۹۱۲,۳۴۸ | 19692 (آفاق) | یکسان |
| ۲۴ | bars_M_close_type7.jsonl | M_close_type7 | ۷,۴۳۵ | ۱,۰۸۳,۲۲۱ | ۱۱۲,۰۵۸,۷۸۲ | 19692 (آفاق) | یکسان |
| ۲۵ | bars_M_close_usd_type0.jsonl | M_close_usd_type0 | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۱۲,۸۹۶,۰۵۴ | 1654 (آتیه ملت) | یکسان |
| ۲۶ | bars_M_close_usd_type5.jsonl | M_close_usd_type5 | ۷,۴۳۵ | ۱,۰۸۳,۲۱۷ | ۱۱۲,۸۹۵,۲۶۰ | 1654 (آتیه ملت) | یکسان |
| ۲۷ | bars_M_close_usd_type7.jsonl | M_close_usd_type7 | ۷,۴۳۵ | ۱,۰۸۳,۲۱۸ | ۱۱۳,۴۵۷,۵۲۲ | 19692 (آفاق) | یکسان |
| ۲۸ | bars_M_last_type0.jsonl | M_last_type0 | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۰۴,۹۱۲,۱۵۳ | 1654 (آتیه ملت) | یکسان |
| ۲۹ | bars_M_last_type5.jsonl | M_last_type5 | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۰۴,۹۱۲,۱۵۳ | 33197 (ارکیده) | یکسان |
| ۳۰ | bars_M_last_type7.jsonl | M_last_type7 | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۱۲,۰۵۷,۳۰۸ | 19692 (آفاق) | یکسان |
| ۳۱ | bars_M_last_usd_type0.jsonl | M_last_usd_type0 | ۷,۴۳۵ | ۱,۰۸۳,۰۶۸ | ۱۰۴,۸۹۲,۵۱۴ | 19692 (آفاق) | یکسان |
| ۳۲ | bars_M_last_usd_type5.jsonl | M_last_usd_type5 | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۰۴,۹۱۲,۱۵۳ | 19692 (آفاق) | یکسان |
| ۳۳ | bars_M_last_usd_type7.jsonl | M_last_usd_type7 | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۱۲,۰۵۷,۳۰۸ | 1654 (آتیه ملت) | یکسان |
| ۳۴ | bars_M_market_cap_type0.jsonl | M_market_cap_type0 | ۶,۱۷۵ | ۹۳۴,۲۰۱ | ۸۷,۰۸۶,۶۹۸ | 50125 (فرویح) | یکسان |
| ۳۵ | bars_M_market_cap_type5.jsonl | M_market_cap_type5 | ۶,۱۷۵ | ۹۳۴,۲۰۱ | ۸۷,۰۸۶,۶۹۷ | 50125 (فرویح) | یکسان |
| ۳۶ | bars_M_market_cap_type7.jsonl | M_market_cap_type7 | ۶,۱۷۵ | ۹۳۴,۲۰۱ | ۸۷,۰۸۶,۶۹۷ | 50125 (فرویح) | یکسان |
| ۳۷ | bars_M_market_cap_usd_type0.jsonl | M_market_cap_usd_type0 | ۶,۱۷۵ | ۹۳۴,۲۰۱ | ۸۷,۵۱۳,۸۵۷ | 50125 (فرویح) | یکسان |
| ۳۸ | bars_M_market_cap_usd_type5.jsonl | M_market_cap_usd_type5 | ۶,۱۷۵ | ۹۳۴,۲۰۱ | ۸۷,۵۱۳,۸۵۹ | 50125 (فرویح) | یکسان |
| ۳۹ | bars_M_market_cap_usd_type7.jsonl | M_market_cap_usd_type7 | ۶,۱۷۵ | ۹۳۴,۲۰۱ | ۸۷,۵۱۳,۸۵۹ | 50125 (فرویح) | یکسان |
| ۴۰ | bars_M_real_close_type0.jsonl | M_real_close_type0 | ۷,۴۳۵ | ۱,۰۸۳,۲۲۰ | ۱۰۴,۹۱۱,۶۶۳ | 33197 (ارکیده) | یکسان |
| ۴۱ | bars_M_real_close_type5.jsonl | M_real_close_type5 | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۰۴,۹۱۲,۱۵۳ | 33197 (ارکیده) | یکسان |
| ۴۲ | bars_M_real_close_type7.jsonl | M_real_close_type7 | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۱۲,۰۵۷,۳۰۷ | 1654 (آتیه ملت) | یکسان |
| ۴۳ | bars_W_close_type0.jsonl | W_close_type0 | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۱۸۸,۰۹۱,۸۴۹ | 461 (وتجارت) | یکسان |
| ۴۴ | bars_W_close_type5.jsonl | W_close_type5 | ۷,۴۳۵ | ۱,۷۱۳,۷۲۳ | ۱۸۸,۰۹۰,۶۹۰ | 1654 (آتیه ملت) | یکسان |
| ۴۵ | bars_W_close_type7.jsonl | W_close_type7 | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۲۱۶,۲۹۵,۱۷۱ | 19692 (آفاق) | یکسان |
| ۴۶ | bars_W_close_usd_type0.jsonl | W_close_usd_type0 | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۲۱۹,۱۳۰,۳۰۷ | 461 (وتجارت) | یکسان |
| ۴۷ | bars_W_close_usd_type5.jsonl | W_close_usd_type5 | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۲۱۹,۱۳۰,۳۲۰ | 19692 (آفاق) | یکسان |
| ۴۸ | bars_W_close_usd_type7.jsonl | W_close_usd_type7 | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۲۲۱,۷۱۳,۰۸۲ | 33197 (ارکیده) | یکسان |
| ۴۹ | bars_W_last_type0.jsonl | W_last_type0 | ۷,۴۳۵ | ۱,۷۱۳,۷۱۹ | ۱۸۸,۰۸۹,۸۴۱ | 19692 (آفاق) | یکسان |
| ۵۰ | bars_W_last_type5.jsonl | W_last_type5 | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۱۸۸,۰۹۱,۴۲۱ | 19692 (آفاق) | یکسان |
| ۵۱ | bars_W_last_type7.jsonl | W_last_type7 | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۲۱۶,۲۸۶,۲۹۶ | 33197 (ارکیده) | یکسان |
| ۵۲ | bars_W_last_usd_type0.jsonl | W_last_usd_type0 | ۷,۴۳۵ | ۱,۷۱۳,۷۳۰ | ۱۸۸,۰۹۱,۰۱۸ | 19692 (آفاق) | یکسان |
| ۵۳ | bars_W_last_usd_type5.jsonl | W_last_usd_type5 | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۱۸۸,۰۹۱,۴۲۱ | 33197 (ارکیده) | یکسان |
| ۵۴ | bars_W_last_usd_type7.jsonl | W_last_usd_type7 | ۷,۴۳۵ | ۱,۷۱۲,۸۲۵ | ۲۱۶,۱۲۶,۹۹۶ | 33197 (ارکیده) | یکسان |
| ۵۵ | bars_W_market_cap_type0.jsonl | W_market_cap_type0 | ۶,۳۷۸ | ۱,۳۶۹,۳۱۰ | ۱۵۱,۷۸۰,۹۰۳ | 172 (خساپا) | یکسان |
| ۵۶ | bars_W_market_cap_type5.jsonl | W_market_cap_type5 | ۶,۳۷۸ | ۱,۳۶۹,۳۱۰ | ۱۵۱,۷۸۰,۹۰۳ | 167 (خودرو) | یکسان |
| ۵۷ | bars_W_market_cap_type7.jsonl | W_market_cap_type7 | ۶,۳۷۸ | ۱,۳۶۹,۳۱۰ | ۱۵۱,۷۸۰,۹۰۱ | 172 (خساپا) | یکسان |
| ۵۸ | bars_W_market_cap_usd_type0.jsonl | W_market_cap_usd_type0 | ۶,۳۷۸ | ۱,۳۶۹,۳۱۰ | ۱۶۲,۴۶۰,۸۳۰ | 167 (خودرو) | یکسان |
| ۵۹ | bars_W_market_cap_usd_type5.jsonl | W_market_cap_usd_type5 | ۶,۳۷۸ | ۱,۳۶۹,۳۱۰ | ۱۶۲,۴۶۰,۸۳۰ | 172 (خساپا) | یکسان |
| ۶۰ | bars_W_market_cap_usd_type7.jsonl | W_market_cap_usd_type7 | ۶,۳۷۸ | ۱,۳۶۹,۳۱۰ | ۱۶۲,۴۶۰,۸۳۰ | 167 (خودرو) | یکسان |
| ۶۱ | bars_W_real_close_type0.jsonl | W_real_close_type0 | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۱۸۸,۰۹۱,۴۰۰ | 19692 (آفاق) | یکسان |
| ۶۲ | bars_W_real_close_type5.jsonl | W_real_close_type5 | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۱۸۸,۰۹۱,۴۰۲ | 19692 (آفاق) | یکسان |
| ۶۳ | bars_W_real_close_type7.jsonl | W_real_close_type7 | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۲۱۶,۲۸۶,۲۸۰ | 19692 (آفاق) | یکسان |

## تفکیک per-resolution
- D: ۲۱ فایل، ۱۵۹,۳۲۴ رکورد، ۹۸,۸۵۸,۷۳۱ کندل.
- W: ۲۱ فایل، ۱۴۹,۸۰۴ رکورد، ۳۳,۹۲۰,۹۰۹ کندل.
- M: ۲۱ فایل، ۱۴۸,۵۸۴ رکورد، ۲۱,۸۵۳,۲۹۳ کندل.

## نکات محتوایی (از نمونه‌های واقعی)
- کندل‌های D دارای `utc` با زمان درون‌روز (مثلاً 14:54:05Z)؛ M دارای offset تهران (+04:30). فیلد utc در DB حذف شده.
- در W/M صندوق‌ها، هزاران کندل placeholder با `time=0` و همهٔ فیلدها صفر وجود دارد (padding مبدأ).
- market_cap*: فیلدهای OHLC حاملِ ارزش بازارند نه قیمت (معناشناسی متفاوت).