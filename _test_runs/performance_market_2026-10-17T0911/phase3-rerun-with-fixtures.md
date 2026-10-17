# بازاجرای همان دو سوئیت با فیکسچرهایِ gitignore‌شده

`market.db.lzma` و `_audit/ra365_ref_bars.json` کپی شدند (ساخته نشدند) — هر دو سبز.

```
### dev/db_housekeeping.py --selftest (با فیکسچرِ واقعی)
  [ok] dedupe idempotent
  [setup] artificial prev-year gap: 11405 cells nulled
  [ok] backfill filled 11405 cells
  [ok] backfill idempotent
  [ok] شارپيلن canonical (1 row per period)
  [ok] integrity=ok, fk_violations=0
[selftest] PASS
[selftest] copy removed: C:\Users\JOHNKA~1\AppData\Local\Temp\bors_housekeep__z2x1gj0\copy.db
### dev/test_adjustment_engine_v1.py (با شاهدِ مرجع)
  ✓ ج۴ [وبصادر] میانۀِ خطا < ۰٫۱٪ در برابرِ type7/type0 (واقعی، بدونِ تنظیم)
     ↳ [وبصادر] نقاط=601 میانۀِ خطا=0.0370٪ رویدادها=9
  ✓ ج۵ [طلا] بی‌رویداد، موتور complete
  ✓ ج۵-ب [طلا] همه فاکتورها ۱ (بدونِ جابه‌جاییِ مصنوعی)

نتیجه: 44 سبز، 0 قرمز
```
