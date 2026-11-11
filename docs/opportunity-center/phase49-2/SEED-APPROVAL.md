# تأیید مالک برای ردیف‌های Reference-derived و بازکردن گیت Seed

**تاریخ ثبت:** ۲۰۲۶-۱۱-۱۱
**دامنۀ تأیید:** `reference_derived_rows` در Seed Candidate فاز ۴.۹.۱
**تعداد ردیف‌های تأییدشده:** ۱۰۵٬۳۶۷
**Seed تأییدشده:** `_audit/phase49-full-verification/seed/market.db` با SHA-256
`57118e8fc99ff69c9e9812002f1d72571f357c23287fc1880a2f00b8292bbcb5`

## ۱. متن تأیید مالک

> «تأیید مالک پروژه برای استفاده از ۱۰۵٬۳۶۷ ردیف Reference-derived در Seed صادر است.»
>
> «این تأیید را در مستندات و Manifest پروژه ثبت کن.»
> «گیت check_seed_release.py را مطابق تأیید مالک اصلاح کن تا صرفاً به دلیل وجود این ردیف‌ها، انتشار Seed را مسدود نکند.»
> «منشأ، Provenance و قابلیت ردیابی این داده‌ها حفظ شود.»
> «این تأیید به معنی Verified شدن خودکار داده‌ها یا Adjustmentهای تأییدنشده نیست؛ کنترل‌های صحت فنی، هویت نماد و زنجیرهٔ تعدیل همچنان برقرار باشند.»
> «Seed جدید را از نظر Integrity، Hash، Idempotency و تست‌های محصول مجدداً بررسی کن.»
> «این تغییر به معنی اجازهٔ انتشار فوری نیست؛ پس از اجرای تست‌ها، گزارش نهایی Seed Candidate را برای بررسی من ارائه بده.»
> «main، Release و Tag همچنان خارج از محدودهٔ مأموریت هستند.»

## ۲. ثبت در Manifest و مستندات

- رکورد ماشین‌خوان:
  `docs/opportunity-center/phase49-2/OWNER-APPROVAL-REFERENCE-DERIVED.json`
  (schema `phase49-2-owner-approval-reference-derived-v1`، `approved=true`،
  `scope=reference_derived_rows`، تعداد مورد انتظار، SHA کپچر و ایندکس مرجع،
  شرایط، و نقل مستقیم تصمیم مالک).
- بلوک `owner_approvals` در
  `docs/opportunity-center/phase49/FINAL-SEED-MANIFEST.json` با همان
  `seed_db_sha256`، تعداد، تاریخ و شرایط.
- منشأ داده در `seed_manifest` بانک دست‌نخورده ماند:
  `reference_capture_sha256=83544012…`،
  `reference_index_sha256=83544012…`،
  `reference_derived_rows=105367`،
  `provenance=rahavard365 licensed footprint (phase48 + phase49 backfill) + phase49 reference-verified adjustment pack`.

## ۳. تغییر گیت `scripts/check_seed_release.py`

قرارداد جدید:

| ورودی | نتیجه |
| --- | --- |
| `reference_derived_rows=0` | `SEED_RELEASE_OK` |
| `>0` + رکورد تأیید معتبر و منطبق (schema، approved، scope، approver، تعداد، SHA کپچر/ایندکس، conditions) | `SEED_RELEASE_OK` |
| `>0` + رکورد غایب/ناقص/ناهمخوان | `SEED_RELEASE_BLOCKED` |
| `seed_manifest` غایب/تهی، کلید غایب، عدد غیرصحیح یا منفی | `SEED_RELEASE_BLOCKED` حتی با تأیید یا فلگ دستی |
| فلگ صریح `--owner-approved-reference-redistribution` | `SEED_RELEASE_OK` (مسیر دستیِ قدیمی) |

تأیید، «داده» را مجاز می‌کند نه «Manifest ناشناخته» را؛ به همین دلیل بررسی
صحّت Manifest همیشه اول اجرا می‌شود. تأیید هیچ ردیفی را Verified نمی‌کند.

تست‌ها: `python scripts/test_check_seed_release.py` →
`SEED RELEASE GATE TESTS OK` و `SEED RELEASE GATE EDGE CASES OK` (شامل
رکورد معتبر، رکورد غایب، approved=false، عدم تطابق تعداد، عدم تطابق SHA کپچر،
عدم تطابق SHA ایندکس، JSON خراب، و DB بدون Manifest).

اجرای گیت روی Seed Candidate:

```
SEED_RELEASE_OK: reference_derived_rows=105367; owner approval recorded in
docs/opportunity-center/phase49-2/OWNER-APPROVAL-REFERENCE-DERIVED.json
(approved_at=2026-11-11)
```

## ۴. بازبینی مجدد Seed

`_audit/phase49-2/seed_recheck.py` (۱۴ بررسی، همه `true`):

| بررسی | نتیجه |
| --- | --- |
| SHA-256 خود `market.db` با Manifest | ✅ |
| SHA-256 `market.db.lzma` و `market.db.gz` با Manifest | ✅ |
| Round-trip هر دو فشرده‌سازی به همان SHA بانک | ✅ |
| اندازهٔ بانک | ✅ |
| `PRAGMA integrity_check` | `ok` |
| جفت‌های تکراری `(symbol,date)` | ۰ |
| تعداد ردیف Reference-derived (DB/Manifest/تأیید) | ۱۰۵٬۳۶۷ در هر سه |
| تعداد نمادهای دارای تاریخچه | ۶٬۱۰۳ در DB و Manifest |
| SHA کپچر/ایندکس مرجع (DB/Manifest/تأیید) | یکسان |
| `seed_db_sha256` رکورد تأیید | منطبق |

تست ایدمپوتنسی سازندهٔ Seed:
`python _audit/phase49-full-verification/test_stage09_seed_build.py` →
`SEED BUILD TESTS OK` (ساخت دوباره همان شمارش/وضعیت‌ها، بدون ردیف تکراری).

تست‌های محصول: مسیر کاملِ stageE (استخراج ۲۸۱ مگابایتی lzma روی این هاست) عملی
نشد؛ به‌جای آن `_audit/phase49-2/seed_product_check.py` همان Seed تأییدشده را
مستقیماً کپی می‌کند و باینریِ محصولِ فاز ۴.۹.۱ (`borsd.exe`) را روی آن بالا
می‌آورد و API محلی چارت را برای ۸ نماد نمونه اجرا می‌کند. نتیجه
(`_audit/phase49-2/evidence/seed-product-check.json`): هر ۸ بررسی `true` —
Integrity `ok`، ۵۴۴٬۲۸۴ ردیف `price_history`، ۶٬۱۰۳ نماد، ۱۰۵٬۳۶۷ ردیف
Reference-derived، پاسخ `success` برای همهٔ ۸ نماد، `candles>0`،
`factors==candles`، و منبع تعدیل حاضر. Round-trip فشرده‌سازی مستقل از این مسیر
در `seed_recheck.py` پوشش داده شده است.

## ۵. آنچه این تأیید تغییر نمی‌دهد

- هیچ Adjustment تأییدنشده‌ای Verified نمی‌شود.
- کنترل‌های هویت نماد، صحت فنی، و زنجیرۀ تعدیل سرجای خود هستند.
- ۳۰۶ ردیف OHLC نامعتبر، ۵٬۱۸۵ نماد بدون Reference Window و ۱٬۱۷۹ گام
  تأییدنشده همچنان به‌صورت per-symbol در `COVERAGE-STATUS.csv` علامت‌گذاری
  شده‌اند و مانع انتشار سراسری نیستند، ولی در گزارش پوشش شفاف افشا می‌شوند.
- انتشار تجاری Seed همچنان منتظر بررسی گزارش نهایی Seed Candidate توسط مالک
  است؛ این مأموریت Release/Tag/Merge انجام نداد.
