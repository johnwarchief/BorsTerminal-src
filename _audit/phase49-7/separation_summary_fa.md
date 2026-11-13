# خلاصه جداسازی لایه داده فنی (Phase 4.9.7 — Task 6)

تولید خودکار از `separation_validation.json` و `technical.db`؛ همه ارقام با اسکریپت از شواهد اندازه‌گیری‌شده ساخته شده‌اند (تبدیل ارقام با `str.maketrans`). شناسه‌ها و SQL به ASCII باقی مانده‌اند.

## حکم دروازه‌های اعتبارسنجی (۵ دروازه)

| دروازه | حکم | شاهد اندازه‌گیری‌شده |
|---|---|---|
| integrity | قبول | technical.db integrity_check |
| no_placeholder | قبول | t=0 rows=0 |
| no_dup_t | قبول | dup-t groups=0 |
| alias_reproduction | قبول | real_close==last & type0==type5 on 591 (2816 bars) |
| row_reconciliation | قبول | technical=69180503 ref_distinct_no_t0=69180503 |

**all_pass = True** (همه دروازه‌ها: قبول)

## شواهد اندازه‌گیری‌شده

- شمار ردیف‌های جدول candle در technical.db: ۶۹۱۸۰۵۰۳
- شمار کلیدهای یکتای مرجع (بدون t=0 و بدون aliasهای real_close/type5): ۶۹۱۸۰۵۰۳
- کندل‌های مشترک نمونه alias (asset_id=۵۹۱، real_close==last و type0==type5): ۲۸۱۶
- ردیف‌های placeholder با t=0: ۰
- گروه‌های تکراری dup-t: ۰

## پوشش تعدیلات — محدودیت‌های کشف‌شده (Task 4)

- رویدادهای تعدیل (adjustment_event): ۸۲۸۰
- ضریب‌های تعدیل (adjustment_factor): ۶۶۲۹
- رویدادهای بدون asset_id (NULL): ۱۶۵۱
- رویدادهای بدون کلید دارایی (ins_code تهی یا غایب): ۶۴۷

این ۶۴۷ رویداد بدون کلید، از طریق symbol فارسی در pack و جدول id_crosswalk در shared_metadata.db قابل بازیابی هستند؛ schema بدون تغییر باقی مانده است.

## انطباق فقط-خواندنی (Ruling 12)

- reference_all.db پیش از ساخت: size=۱۴۶۱۲۱۲۷۷۴۴ mtime=۱۷۹۴۵۳۹۸۶۲
- reference_all.db پس از ساخت: size=۱۴۶۱۲۱۲۷۷۴۴ mtime=۱۷۹۴۵۳۹۸۶۲
- نتیجه: تأیید (بدون تغییر)
