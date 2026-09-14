# گزارش ممیزی کد مرده — پاک‌سازی v9.7.1

مبنای هر ادعای «مرده» در این جدول، **شمارش occurrences در کل مخزن track‌شده**
(شامل `index.html` و handlerهای inline) است، نه حدس. ابزار: یک نمایهٔ توکن
تک‌گذر روی ۱۰۴ فایل + تحلیل AST برای پایتون.

> نکتهٔ روش‌شناسی: یک تابع تنها در صورتی مرده شمرده شد که **کل occurrences
> برابر ۱** باشد (همان خط تعریف). ارجاع درون‌فایلی هم «زنده» حساب می‌شود؛
> و توابع دارای decorator (route/middleware فریم‌ورک) از دامنهٔ حذف خارج‌اند
> چون با نام صدا زده نمی‌شوند.

---

## ۱. فایل‌های حذف‌شده (۳۲ فایل)

### ریشه
| فایل | دلیل |
|---|---|
| `_test_fts.txt` (19KB) | خروجی تولیدی `dev/test_fts_v8.py` که اشتباهاً track شده بود |
| `fts_v8_test_report.txt` (19KB) | گزارش تولیدی تکراری (هم‌حجم مورد بالا) |
| `syn3.txt` · `.phase1_backup_dir.txt` | اسکرچ |
| `ex_test.xlsx` | بدون هیچ ارجاع |
| `confluence.py` | ماژول کاملاً غیرقابل‌دسترس (بخش ۳) |
| `rahavard_intrinsic.json` (52KB) | **صفر ارجاع** در کل مخزن |
| `sb_config.json` | **صفر ارجاع** در کل مخزن |
| `static/klinecharts.min.js` (229KB) | بایت‌به‌بایت مشابه `static/vendor/klinecharts.min.js`؛ تنها ارجاع موجود یک کامنت است، HTML فقط نسخهٔ vendor را بارگذاری می‌کند |

### `dev/` — تست‌های منسوخ و پروب‌های یک‌بارمصرف
`camo_test.png` (220KB باینری) · `task1.log` · `dom_test.js` · `dom_test_v91.js` ·
`serve_check_v91.py` (جانشین: `serve_check_v95.py`) · `validate_v9.py` ·
`validate_v91.py` · `validate_cache.py` · `task1_discovery.py` ·
`task3_amendment.py` · `task4_finalize.py` · `probe_http.py` · `probe_http2.py` ·
`probe_endpoints.py` · `probe_codal_params.py` · `probe_tsetmc_rate.py` ·
`klc_slice.py` · `db_probe.py` · `audit.py` · `make_release.py` ·
`rebuild_rail.py` · `mine_and_test.py` · `health_v91.py` · `test_fts_v8.py`

`test_fts_v8.py` به‌طور خاص: **اجراشدنی نبود** — فیکسچر in-memory آن ستون
`capital` را نداشت و با `sqlite3.OperationalError` می‌افتاد؛ مسیر مطلق
hardcode‌شده داشت؛ و `_test_fts.txt` را در ریشهٔ مخزن می‌نوشت.

### untrack (بدون حذف از دیسک)
`sync_summary.json` — وضعیت زمان اجرا که توسط `codal_fetcher.py` و
`test_tsetmc.py` نوشته می‌شود.

---

## ۲. توابع مردهٔ JS (۳۰ تابع)

| فایل | توابع |
|---|---|
| `static/app.js` (8) | `onFontSlider` `faDigits` `confirmCodalStart` `setAutoRefreshInterval` `clearAllFilters` `missingReason` `openCodalSettings` `closeCodalSettings` |
| `static/tech_rtv.js` (21) | `rvRenderChart` `rvTogglePriceScaleMenu` `rvSetScaleType` `rvResetPriceScale` `rvToggleScaleSide` `rvToggleAutoScale` `rvFibExtStart` `rvFibRecalc` `rvRailHide` `rvLockAll` `rvToggleMagnet` `rvZoomFit` `rvFocusSearch` `rvReplay` `rvFullscreen` `rvShareChart` `rvPublishChart` `rvToolFa` `rvAutoSaveStatus` `rvFontMenu` `rvToggleItvMenu` |
| `static/tech_tools.js` (1) | `FIBS_EXT` |

یافته‌های جالب:

- **`rvRenderChart`** همان «نسخهٔ قدیمی» مورد انتظار بود: `rvRerender()` جای
  آن را گرفته و از سه نقطه زنده صدا زده می‌شود.
- **خوشهٔ مقیاس قیمت**: `rvTogglePriceScaleMenu` مرده بود و چهار تابع
  `rvSetScaleType` / `rvResetPriceScale` / `rvToggleScaleSide` /
  `rvToggleAutoScale` را صدا می‌زد؛ یعنی آن چهار تا فقط از مسیر یک تابع مرده
  قابل‌دسترس بودند. حذف مورد اول آن‌ها را یتیم کرد و در ممیزی دوم آشکار شدند.
  هر سه‌تای اول روی المنت `rvPriceScaleMenu` `.style.display` می‌زدند، ولی آن
  المنت در `index.html` **وجود ندارد** — یعنی حتی اگر صدا زده می‌شدند
  `TypeError` می‌دادند. بقایای منوی حذف‌شده.
- **هیچ‌کدام پشت dispatch پویا پنهان نبودند**: تنها wrap پویا در پروژه
  `btsHook('rvApplyStyles')` در `tech_365.js` است و آن تابع ارجاع زنده دارد.

راستی‌آزمایی: مجموعهٔ تعاریف `HEAD` با مجموعهٔ فعلی مقایسه شد →
`removed=30, added=0` و لیست حذف‌شده مو‌به‌مو با جدول بالا یکی بود.
`node --check` روی هر سه فایل سبز است.

---

## ۳. کد مردهٔ پایتون

| فایل | تابع | دلیل |
|---|---|---|
| `app.py` | `_fmt_bil` | فرمت مبلغ به JS منتقل شده |
| `app.py` | `_invalidate_market_cache` | کمکی تک‌خطی، هرگز صدا زده نشد |
| `app.py` | `_fs_count` | شمارش FS، جایگزین‌شده |
| `codal_fetcher.py` | `_safe_get` | مسیر backoff قدیمی |
| `codal_fetcher.py` | `_process_one` | جانشین: `_deep_extract` |
| `confluence.py` | کل ماژول | تنها نقطهٔ ورودش `confluence_score` بود که صفر فراخوان داشت؛ توابع کمکی‌اش فقط توسط خودِ همان تابع استفاده می‌شدند |
| `tests/auto_ui_stress_test.py` | `probe_endpoints` | پیش‌نویس اولیهٔ `endpoint_checks`؛ بدنه‌اش `results.extend([_() for _ in ()] or [...])` بود که عمداً لیست خالی می‌داد |

**باگ ساختاری کشف‌شده — route دوتایی:** `/api/market/sync-state` دو بار با دو
تابع هم‌نام `market_sync_state` ثبت شده بود (خط ۲۰۲ و ۱۸۲۷). با تست عملی
ثابت شد Starlette اولین match را برمی‌گرداند، پس نسخهٔ خط ۱۸۲۷ **هرگز اجرا
نمی‌شد**. نسخهٔ غیرقابل‌دسترس حذف شد و رفتار سرو‌شده دست‌نخورده ماند.

**ایمپورت‌های بلااستفاده حذف‌شده (۲۸ مورد در ۱۵ فایل).**
`from __future__ import annotations` عمداً **حذف نشد**: دستور کامپایلر است نه
نام، و ممیز آن را false-positive علامت می‌زند.
