# یکپارچگی دیتابیس عملیاتی — Round 5

- **تاریخ:** ۲۰۲۶-۱۰-۲۰
- **فایل:** `market.db` (worktree مأموریت)
- **حکم:** `LOGICAL_CONTENT_DIFFERENCE_FOUND` — سلامت فایل تأیید شد، اما ۱۴ ردیف `price_history` در گیت نوشته شد.

## ۱. وضعیت فایل

| سنجه | مقدار |
|---|---|
| sha256 شروع Round 5 | `ce74f80cf8ebb721239ff5114f8baa8db573fdc2b3f6c38a4adccb910ef22237` |
| sha256 پایان بررسی | `fff358a78be74e8d21961251a727116e102df84cea70f87b4dcb7da198667004` |
| اندازه | ۲۴۴٬۲۸۵٬۴۴۰ بایت |
| `market.db-wal` | ۰ بایت (خالی) |
| `market.db-shm` | ۳۲٬۷۶۸ بایت |
| `PRAGMA integrity_check` | `ok` |
| تعداد جدول | ۴۷ |
| جدول‌های `fund_profit_events` / `session_backfill` / `session_anomalies` | ۰ / ۰ / ۰ ردیف |
| `price_history` قبل/پس از گیت | ۴۴۳٬۷۳۸ / ۴۴۳٬۷۵۲ (+۱۴) |

## ۲. نامزدهای baseline و چرا معتبر نیستند

| نامزد | زمان | مشکل |
|---|---|---|
| `_scratch/ra_round3/market_copy.db` | ۱۴:۵۶ | کپیِ کاریِ Round 3 است و خودِ ما در آن fund/backfill/anomaly نوشتیم: `fund_profit_events=1332`، `session_backfill=105`، `session_anomalies=1`، `adjust_events=5034` در برابر ۴۹۵۵ عملیاتی. baseline عملیاتی نیست. |
| `_scratch/ra_fup_2026_10_20/market_copy_v2.db` | ۰۶:۳۴ | بسیار قدیمی‌تر از گیت Round 3/4 است و با sync عادی بازار واگرا شده (مثلاً `instruments` ۵۹۸۱ در برابر ۶۱۰۸). برای انتساب تغییر به گیت معتبر نیست. |
| هیچ snapshot منطقیِ پیش از گیت ۱۵:۱۷ | — | وجود ندارد؛ checksum شروع فقط بایت‌ها را ثبت کرده بود، نه یک کپی. |

## ۳. مقایسهٔ schema و محتوا

- **Schema:** مجموعهٔ ۴۷ جدول در `market_copy.db` و `operational_after.db` یکسان است؛ هیچ اختلاف DDL در جدول‌های مشترک دیده نشد.
- **جدول‌های جدید:** فقط `fund_profit_events`، `session_backfill`، `session_anomalies` اضافه شده‌اند و هر سه ۰ ردیف دارند.
- **محتوا:** مقایسهٔ hash منطقی روی `instruments`، `price_history`، `daily_prices`، `price_adjust_events`، `share_change_events`، `codal_notices`، `financial_statements`، `monthly_sales`، `market_watch` و `boards` با کپی کاری، تفاوت نشان می‌دهد؛ اما کپی کاری توسط pullهای خودمان نوشته شده و `market_copy_v2` هم قدیمی‌تر است. بنابراین این تفاوت‌ها به گیت منتسب نمی‌شوند.
- **جدول‌های کش چارت:** `adjust_events` و `adjust_verdict` در مسیر تست‌های چارت ممکن است نوشته شوند؛ `adjust_verdict` ۵۲ ردیف با `checked_at=2026-10-20` دارد. زمان دقیق نوشتن ثبت نشده و قابل انتساب قطعی به گیت نیست.

## ۴. نتیجه

`LOGICAL_CONTENT_DIFFERENCE_FOUND`: در گیت ۱۴ ردیف `price_history` با `src='published'` و تاریخ ۲۰۲۶-۱۰-۲۰ اضافه شد (۴۴۳٬۷۳۸→۴۴۳٬۷۵۲). این ردیف‌ها از یک سوئیت تست نوشته شده‌اند؛ شمارهٔ سوئیت به‌طور قطعی جداسازی نشد. هیچ migration/ترمیم/حذف روی `market.db` انجام نشد. برابری بایتی نیز به‌دلیل checkpoint تغییر کرد، اما این توضیح به‌تنهایی کافی نیست و تفاوت منطقی ۱۴ ردیف ثبت شده است.

**اقدام بعدی:** پیش از هر گیت نوشتنی، یک snapshot منطقی (`.dump` یا کپی + sha256) از `market.db` گرفته شود و تست‌ها با `BORS_DB` روی کپی اجرا شوند؛ سپس همین مقایسه schema/row-count/hash تکرار شود.
