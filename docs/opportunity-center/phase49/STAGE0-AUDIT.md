# Stage 0 — ممیزیِ فقط‌خواندنیِ مبنا (Phase 4.9)

- تاریخ: 2026-11-10
- شاخه: `mission/phase49-adjustment-chain-closure-2026-11-10`
- مبنا: `9d348b6456ffd7af556e299df2de9b26b3b4ca22` (HEAD شاخهٔ `mission/phase48-closeout-2026-11-09`)
- worktree: تنها یک worktree تازه در `C:/Users/STU/Desktop/borsterminal`؛ هیچ worktree دیگرِ مأموریت‌ها روی این ماشین نبود.
- در این مرحله هیچ داده‌ای تغییر نکرد؛ همهٔ DBها در مسیرهای ایزولهٔ تازه بازیابی شدند.

## ۱) وضعیت محیط و ابزار

| قلم | مقدار |
| --- | --- |
| Git | 2.53.0.windows.1 |
| Python | 3.12.10 |
| Go | 1.26.0 windows/amd64 (CI فاز ۴٫۸ با 1.27.3 اجرا شده) |
| Node | v24.22.1 (frontend build در این مأموریت لازم نیست) |
| Remote base | `9d348b64…` تأییدشده؛ `main` روی Remote همان `9a919e82…` و دست‌نخورده |
| Worktreeهای دیگر | هیچ؛ `git worktree list` فقط این worktree را نشان می‌دهد |

## ۲) اعتبارسنجیِ آرتیفکت‌ها (manifest فاز ۴٫۸)

`python tools/phase48/continuation/verify_artifacts.py`:

- **۳۵ ورودیِ `committed`: همگی OK** (اندازه و SHA-256 دقیقاً منطبق؛ شامل سه آرشیو LZMA و پک اصلاح `ra365-r32b-v2`).
- **۱۴ ورودیِ `local`: همگی روی این ماشین غایب‌اند.** این ورودی‌ها از ابتدا در گیت نبودند؛ طبق سیاستِ پروژه فقط خلاصه/دادهٔ مشتق در مخزن است.

### آرتیفکتِ حیاتیِ غایب: بستهٔ مرجع مالک

| مسیر | sha256 ثبت‌شده | وضعیت در این محیط | اثر |
| --- | --- | --- | --- |
| `_audit/phase48/parity/ref/bars.ndjson.gz` | `68a1c803…36fc171b` | **غایب**؛ روی هیچ مسیر این ماشین پیدا نشد | هر سنجه‌ای که به سری type0/type7 مرجع نیاز دارد، مستقل بازتولیدپذیر نیست |
| `_audit/phase48/parity/ref/symbols.json` | `d1b62739…` | **غایب** | فهرست ۳۰ نماد از `evidence/verify-api.json` بازیابی شد (تطبیق کامل با شواهد) |
| `_audit/phase48/parity/ref/coverage.json` | `3333e660…` | **غایب** | پوشش مرجع قابل بازسنجی نیست |

سایر آرتیفکت‌های `local` (DBهای خام، باینری تست، باندل Repair) نیز غایب‌اند؛ اما DBهای خام از آرشیوهای گیت بازیابی شدند و باینری‌ها از کد قابل ساخت‌اند.

**تصمیم مطابق مأموریت:** هیچ دادهٔ تخمینی جای آرتیفکتِ غایب گذاشته نشد. سنجه‌های وابسته به مرجع با وضعیت `NOT_MEASURED` / `INSUFFICIENT_DATA` علامت می‌خورند، نه PASS.

## ۳) بازیابیِ سه دیتابیس (مسیرهای ایزولهٔ تازه)

مسیر بازیابی: `_audit/phase49/continuation/db/` (gitignored؛ هیچ DB موجودی overwrite نشد).
گزارش ماشینی: `_audit/phase49/continuation/stage0-restore-report.json`.

| DB | آرشیو | SHA آرشیو | SHA خام | integrity | جدول‌ها | price_history |
| --- | --- | --- | --- | --- | ---: | ---: |
| Source | `phase48-source-market.db.lzma` | `42cd1567…` ✔ | `bb57564b…` ✔ | `ok` | 41 | 438,917 |
| Work | `phase48-backfill-work-market.db.lzma` | `db214908…` ✔ | `2b701ea3…` ✔ | `ok` | 43 | 511,139 |
| Verify | `phase48-backfill-verify-market.db.lzma` | `db214908…` ✔ | `2b701ea3…` ✔ | `ok` | 43 | 511,139 |

- Work و Verify خام بایت‌یکسان‌اند؛ آرشیوهایشان هم یکسان است (مطابق manifest).
- بازهٔ کامل `price_history`: **2010-01-02 تا 2026-11-09**.
- `backfill_runs`: یک اجرا با `status=applied`، `run_id=rahavard-backfill-2026-11-09`، `ref_rows=83,364`، `ref_only=72,243`، `inserted=72,222`، `skipped_existing=0`، `invalid=21`، `duplicate_conflicts=0`.
- `backfill_rows`: ۷۲٬۲۲۲ ردیف با `src=rahavard365` و provenance کامل.
- توزیع `src` در ۳۰ نماد: `rahavard365=72,222`، `legacy-unknown=11,217`، `board=869` (جمع ۸۴٬۳۰۸) — دقیقاً مطابق گزارش فاز ۴٫۸.

## ۴) بازتولیدِ بخشِ زنجیره‌ایِ Baseline

محاسبهٔ مستقل از DBهای بازیابی‌شده و پک گیت‌شده:

| سنجه | مقدار فاز ۴٫۸ | بازتولید Phase 4.9 | وضعیت |
| --- | ---: | ---: | --- |
| نمادها | ۳۰ | ۳۰ (از `evidence/verify-api.json`) | REPRODUCED |
| Product Events (`adjust_events`، ratio>0) | ۶۵۲ | **۶۵۲** (تطبیق per-symbol: ۳۰/۳۰) | REPRODUCED |
| Authoritative Pack Steps (replace) | ۲۷۱ | **۲۷۱** (تطبیق per-symbol: ۳۰/۳۰) | REPRODUCED |
| ردیف‌های دفتر رسمی | ۲۸۴ | **۲۸۴** | REPRODUCED |
| Backfill خام جدید | ۷۲٬۲۲۲ | **۷۲٬۲۲۲** | REPRODUCED |
| تغییر ردیف‌های موجود | صفر | **۰ از ۴۳۸٬۹۱۷ ردیف مشترک** (مقایسهٔ ستون‌به‌ستون) | REPRODUCED |
| ردیف گم‌شده | ۰ | **۰** | REPRODUCED |
| Reference Steps | ۵۰۱ | — | NOT_MEASURED (مرجع غایب) |
| Product Steps منطبق با مرجع که Suppress شده‌اند | ۴۴۳ | — | CITED_ONLY (شاهد ثبت‌شده؛ بازسنجی مستقل ممکن نیست) |
| OHLC دقیق پیش از ۲۰۲۴ | ۶٬۴۷۲ / ۱۱٬۱۲۱ (۵۸٫۲٪) | — | NOT_MEASURED (مرجع غایب) |
| پاریتی خام/تعدیل‌شده و طبقه‌بندی close | جدول §۴ گزارش فاز ۴٫۸ | — | NOT_MEASURED (مرجع غایب) |

**تفکیک عمدی:** «پاریتی خام»، «پاریتی زنجیرهٔ ضریب» و «پاریتی OHLC تعدیل‌شده» سه سنجهٔ جدا هستند. فقط سنجهٔ دوم (سمت Product/Pack) کامل بازتولید شد؛ دو سنجهٔ اول و سوم به بستهٔ مرجع نیاز دارند.

## ۵) مسیر واقعیِ کد — Python در برابر Go

### Python (`api/chart.py`)

1. ساخت کندل از CSV/DB با `candle_contract` (هندسهٔ widened + `high_raw`/`low_raw`).
2. کشف رویداد از گسستِ قیمت پایه، تیزکردن با دفتر رسمی، فیلتر رویدادهای بی‌شاهد، split موقت.
3. `AC.apply_factor_events` در `api/chart.py:2365` (حالت `authoritative`/`overlay`) سپس `AE.chain_factors` در `:2379`.
4. محاسبهٔ `factors` = ∏ ratio برای رویدادهای `date > t` و ساخت پاسخ.
5. در لایهٔ route: `_literal_display_candles` در `api/chart.py:2743` روی **کپیِ نمایشی**:
   - `high = high_raw` و `low = low_raw`،
   - سپس `AC.apply_raw_candles` (`api/chart.py:2764`) برای تصحیح‌های فیلد خام از پک.
6. این مرحله در `/api/chart/{symbol}` (`:2774`) و `/api/chart-db/{symbol}` (`:3575`) اجرا می‌شود؛ ضریب‌ها و محاسبات داخلی FTS دست‌نخورده می‌مانند.

### Go (`backend-go`)

1. `canonicalPriceHistory` → `canonicalAdjustment` → `ApplyFactorEvents` (`canonical.go:961`) → `chainFactors` (`canonical.go:1444`) — معادل مراحل ۲–۴ پایتون.
2. `ApplyRawCandles` در `internal/chart/corrections.go:663` تعریف شده است، اما **هیچ caller ندارد** (`grep` در کل `backend-go` فقط تعریف را نشان می‌دهد).
3. `ChartDB` handler (`internal/chart/handlers.go:28`) خروجی `chartDBBody` را مستقیم برمی‌گرداند؛ نه literal display (high/low خام) و نه تصحیح فیلد خام پک اعمال می‌شود.

**نتیجهٔ Stage 0:** شکافِ پاریتیِ گزارش‌شده تأیید شد. Go مرحلهٔ نمایشیِ Python را ندارد؛ بنابراین حتی بدون پک، کندل‌های دیدنی Go (سایهٔ widened) با Python (سایهٔ literal) یکی نیستند و تصحیح‌های فیلد خام پک هم در Go اعمال نمی‌شوند.

## ۶) Baselineِ CI (بدون تغییر)

اجرای `guards` روی HEAD مبنا (`9d348b64…`، run `42703163925`):

| Job | نتیجه |
| --- | --- |
| go race detector / go backend / windows 2022 / windows-latest | success |
| data integrity guards | success |
| frontend v2 / js syntax / desktop delivery / repo hygiene | success |
| offline guard suites (python `dev/run_all_tests.py`) | **failure** |

این همان شکستِ ازپیش‌موجودِ `python-guards` است (نبودِ `frontend/node_modules` در CI) و در این مأموریت Regression جدید حساب نمی‌شود.

## ۷) محدودیت‌های این محیط (صادقانه)

1. **بستهٔ مرجع مالک غایب است**؛ هیچ بازتولید مستقلی از پاریتیِ وابسته به type0/type7 ممکن نیست. تمام داوری‌های نهاییِ تعدیل باید با این محدودیت علامت بخورند.
2. `frontend/node_modules` نصب نیست؛ در صورت نیاز به گیت frontline باید `npm ci` اجرا شود (خارج از دامنهٔ این مأموریت مگر تغییر Frontend).
3. دسترسیِ پیش‌فرض `proxy.golang.org` برای بعضی ماژول‌ها 403 می‌دهد؛ ماژول‌ها با mirror جایگزین دریافت می‌شوند و این موضوع در گزارش نهایی ثبت می‌شود.
