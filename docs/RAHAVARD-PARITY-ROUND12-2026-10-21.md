# Round 12 — Rahavard Visual + Numerical Convergence

**تاریخ:** ۲۰۲۶-۱۰-۲۱ · **شاخه:** `mission/ra365-round12-visual-numerical-2026-10-21`
**مبنا:** `a4dced2c` (Round 11) · **main ادغام‌شده:** `784d9d8a` (Market Status) · **merge:** `c27744ab`
**وضعیت نهایی این دور: `BLOCKED_WITH_EVIDENCE` / `NO_IMPROVEMENT` در معیارِ عددی · `SESSION_NOT_ACCESSIBLE` در مسیر بصری.**
هیچ ادعای ۱۰۰٪، هیچ تغییر در `main` و هیچ tag/release انجام نشد.

---

## ۱) Git و حفاظت

- Round 11 با tip `a4dced2c` و ۳۷ commit بررسی و حفظ شد.
- `origin/main` (شامل انتشار Market Status `784d9d8a`) با یک merge تمیز وارد شاخه شد: `c27744ab`.
- هیچ تعارضی رخ نداد؛ هیچ reset/force/squash انجام نشد.
- `main`، tagها و releaseها تغییر نکردند.
- worktree مستقل: `BorsTerminal-ra365-round12`.

## ۲) این دور چه چیزی را واقعاً ثابت کرد؟

### ۲-۱) Baseline عددی Round 11 قابل بازتولید نبود

Baseline گزارش‌شده (Factor exact 48.3147%، near 81.5943%، OHLC 48.7637%،
normalized 41.2898/82.0320، REF_ONLY 154، PROD_ONLY 157، mismatch 263)
روی corpus اصلی قابل بازتولید **نبود**، چون:

- فایل‌های خام `ref_bars.jsonl` و `product_live_final.jsonl` در مخزن نیستند
  (فقط ماتریس‌های خلاصهٔ symbol/step کامیت شده‌اند).
- ماتریس نمادها **۷٬۷۹۴ unresolved event** روی ۶۷۶ نماد دارد؛ عدد ۲۸۴
  از هیچ‌یک از ماتریس‌های کامیت‌شده قابل استخراج نبود.
- توزیع ۳٬۴۸۸ ردیف `share_change_events` بازسازی شد: ۱٬۰۶۵ ردیف با یک
  reference step هم‌راستا هستند و هنوز PA تایپ‌شده ندارند؛ این superset است،
  نه ۲۸۴ گزارش‌شده.

**نتیجه:** `BASELINE_NOT_REPRODUCIBLE_NO_REFERENCE_BARS`. هیچ مخرج جدیدی
ساخته نشد و اعداد Round 11 جعل/بازنویسی نشدند.

### ۲-۲) باگ واقعی در فیلتر share-change

`_filter_share_changes` فقط نسبت و فاصلهٔ ۱۸۰ روز را می‌دید و هر نسبتِ
تکراری را «همان رویداد بازنویسی‌شده» می‌گرفت. audit روی ۳٬۴۸۸ ردیف نشان داد
**۵ زنجیرهٔ واقعی** قربانی این قاعده می‌شوند:

| نماد | زنجیرهٔ سرمایه | تاریخ‌ها |
|---|---|---|
| آسال | ۵۰۰M → ۱B → ۲B | 2026-06-22 / 2026-09-02 |
| بلد | ۵۰۰M → ۱B → ۲B | 2026-06-16 / 2026-08-05 |
| شميم | ۵۰۰M → ۱B → ۲B → ۳B → ۶B | 2024-07-22 … 2025-07-28 |
| پاكشو | ۱B → ۲B → ۴B | 2020-02-22 / 2020-03-16 |
| فاخر | ۱٫۵B → ۲B → ۳B → ۴B | 2024-08-07 / 2024-10-13 / 2025-01-18 |

در مقابل، ۱۸۷ ردیفِ restatement دقیق و ۴ ردیفِ near-restatement (مثل
دانا/سشمال/خاهن) باید حذف بمانند.

**اصلاح:** dedup بر اساس **هویت شمار سهام** شد:
- شروع و پایانِ یکسان ⇒ همان رویداد بازنویسی‌شده (drop)؛
- شروعِ ردیفِ بعد = پایانِ ردیفِ قبل ⇒ رویدادِ متوالیِ واقعی (keep)؛
- شروعِ متفاوت ⇒ رویدادِ متمایز (keep).
نسبت تنها دیگر کلید هویت نیست.

**تست‌ها:** ۵۵/۵۵ DPS (شامل ۴ تست جدید)، ۷/۷ ledger، ۱۰/۱۰ fund،
۴۸/۴۸ phase-A، ۲۰/۲۰ fund/backfill.

**اندازه‌گیری:** برای پنج نماد، `_canonical_adjustment` قبل/بعد فراخوانی شد؛
چون برای رویداد دوم هیچ ردیف PA رسمی در بانک نیست، factor تغییر نکرد.
بنابراین این یک **اصلاح صحت داده/نوع‌دهی** است، نه بهبود اندازه‌گیری‌شدهٔ
Full-Universe. وضعیت عددی: **`NO_IMPROVEMENT`** (با شاهد) و برای خوشهٔ
۲۸۴: **`BLOCKED_WITH_EVIDENCE`**.

## ۳) مسیر بصری — `SESSION_NOT_ACCESSIBLE`

- managed browser روی `/asset/48315/chart`: صفحه با modal ورود
  (`input[type=password]`، متن ~۲۰۰ نویسه) باز شد؛ asset عمومی بدون login
  داده داشت، اما chart محافظت‌شده بود.
- Firefox مالک (PID 1892) روی `rahavard365.com` احراز هویت‌شده بود (صفحهٔ
  خانه بدون دکمهٔ ورود و با آیکن حساب)، اما:
  - navigation مصنوعی با SendKeys/کلیک، آدرس را عوض نکرد؛
  - UI Automation/PrintWindow فقط خانه را دید و ورود به متن/چارت ممکن نشد
    (`Win32Exception`).
- هیچ کوکی/token/رمز/هویت حسابی خوانده، ذخیره یا در repo ثبت نشد.
- برای شش نماد، `charts_opened=0`; وضعیت همه: `SESSION_NOT_ACCESSIBLE`.
- شاهد: `docs/audit/ra365-round12-visual-comparison.csv`.

## ۴) خروجی‌های الزامی

| فایل | محتوا |
|---|---|
| `docs/audit/ra365-round12-share-only-evidence.csv` | ۳٬۴۲۵ ردیف share با PA-match، filter action و `BLOCKED_TYPE_EVIDENCE` |
| `docs/audit/ra365-round12-filter-audit.csv` | ۵ ردیفِ تازه‌نگه‌داشته‌شده + ۵۳۶ ردیفِ reverse/restatement حذف‌شده |
| `docs/audit/ra365-round12-visual-comparison.csv` | ۶ نماد، `SESSION_NOT_ACCESSIBLE` |
| `docs/audit/ra365-round12-loop-history.jsonl` | ۶ iteration واقعی |

## ۵) تست و گیت

| مورد | نتیجه |
|---|---|
| `dev/test_dps_formula_v1.py` | 55/55 |
| `dev/test_official_ledger_dedupe_v1.py` | 7/7 |
| `dev/test_fund_events_v1.py` | 10/10 |
| `dev/test_adjustment_phasea.py` | 48 pass / 0 fail / 1 skip |
| `dev/test_fund_profit_and_backfill_v1.py` | 20/20 |
| `python -m py_compile api/chart.py` | OK |
| Full gate | اجرا نشد؛ به‌دلیل دو suite تمام‌universe کند در دور قبل، «سبز» ادعا نمی‌شود |

## ۶) دیتابیس

- DB عملیاتی دست‌نخورده؛ همهٔ بررسی‌ها روی کپی read-only
  `../.q3-live-data/market.db` انجام شد.
- هیچ backfill/INSERT/UPDATE روی DB عملیاتی انجام نشد.

## ۷) محدودیت‌ها و گام بعدی

1. بازسازی corpus خام Rahavard (ref bars) یا یافتن آرشیو Round 11 برای
   بازتولید ۲۸۴ و معیارهای Full-Universe.
2. نوع‌دهی رسمی ۲۸۴/۱٬۰۶۵ ردیف با notice ID؛ CODAL در دسترس محلی قدیمی/
   rate-limited است ⇒ `BLOCKED_TYPE_EVIDENCE`.
3. مشاهدهٔ چارت با یک نشست قابل‌کنترل (Playwright/CDP/Firefox remote) و
   ثبت tooltip/OHLC؛ فعلاً `SESSION_NOT_ACCESSIBLE`.
4. اجرای گیت کامل روی شاخه پس از رفع کندی suiteهای تمام‌universe.

**جمع‌بندی:** این دور یک باگ واقعیِ حذف رویداد را اصلاح کرد و مرزهای
بازتولیدپذیری/بصری را صادقانه ثبت کرد؛ اما هیچ بهبود عددیِ Full-Universe
اندازه‌گیری نشد و ۱۰۰٪ ادعا نمی‌شود.
