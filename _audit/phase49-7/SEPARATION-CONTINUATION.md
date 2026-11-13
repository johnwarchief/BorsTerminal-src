# ادامهٔ کار جداسازی لایهٔ داده — Phase 4.9.7 (برای سیستم قوی‌تر)

شاخه: `mission/phase49-7-discovery` — پوش‌شده تا `b9925ee8` روی origin (مخزن خصوصی BorsTerminal-src).

## وضعیت انجام‌شده
- Task 1–5 کامل + review (spec ✅ + quality Approved). کامیت‌ها:
```
b9925ee8 feat(separation): full build orchestration + validation evidence
ac1cb86a fix(separation): non-vacuous alias + reconciliation gates
1c3a157b feat(separation): validation gates (integrity/placeholder/dup/alias/reconciliation)
565dc08d feat(separation): adjustment events + factors from corrections pack
36573472 feat(separation): cleaned distinct-mode technical candles from JSONL
82f3db24 fix(separation): timezone-aware usd_rate date, drop deprecation warnings
d21d2f50 feat(separation): mode_def aliases + usd_rate from dollar asset
446f9e15 feat(separation): shared metadata asset + crosswalk
```
- Task 6 فاز A (کد orchestrator `run_separation.py` + بهینه‌سازی build_candles: batching executemany + PRAGMA bulk + progress logging) کامیت شده.
- build کامل تا مرحلهٔ candles + adjustments اجرا شد: `technical.db` ≈ ۱۱.۹۰ GB و `shared_metadata.db` ≈ ۹.۰ MB در `D:/BorsTerminal-data/separation`. مرحلهٔ validate/evidence در زمان پوش هنوز نهایی نشده بود (separation_validation.json تولید نشده).

## ادامه روی سیستم قوی‌تر
۱. آرشیو مبدأ (≈ ۳۴.۳۸ GB، زیر) را کپی کنید و مسیرها را در `tools/phase497/separation/paths.py` تنظیم کنید: `REF_DB`, `JSONL_DIR`, `UNIVERSE`, `PACK`, `OUT_DIR`.
۲. اجرا: `PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 python -m tools.phase497.separation.run_separation`
   - shared_metadata.db + technical.db را می‌سازد، ۵ گیت validate را روی مرجع read-only اجرا می‌کند، `separation_validation.json` + خلاصهٔ فارسی می‌نویسد و `ALL_PASS` چاپ می‌کند.
۳. اگر گیتی fail شد، STOP و بررسی با شواهد اندازه‌گیری‌شده (بدون fudge). گیت row_reconciliation باید tech_rows == ref_distinct (deduped, بدون t=0 و alias) بدهد.
۴. مرجع باید دست‌نخورده بماند: size.reference_all.db = ۱۴۶۱۲۱۲۷۷۴۴ (قبل/بعد stat مقایسه شود).

## مسیرهای آرشیو مبدأ برای کپی روی فلش USB
- پوشهٔ اصلی (≈ ۳۴.۳۸ GB): `D:/BorsTerminal-worktrees/phase49-5-resume/_audit/phase49-5/api-all`
  - `reference_all.db` = ۱۴۶۱۲۱۲۷۷۴۴ بایت (≈ ۱۴.۶۱ GB) — کندل‌ها + متادیتای دارایی
  - ۶۳ فایل `bars_*.jsonl` = ≈ ۱۹.۷۷ GB — کندل خام با فیلد utc
  - `universe.json` (۴۵۱۵۷ دارایی) + `errors.jsonl` + اسکریپت‌های provenance
- پک تصحیحات (≈ ۱۰.۰ MB): `D:/BorsTerminal-worktrees/phase49-5-resume/data/ra365_corrections/ra365-phase49-rebuild-full-v2`
  - `factors.jsonl` (۸۲۸۰ رویداد تعدیل) + `manifest.json` + `raw_ohlc.jsonl`

## نکات معوق (برای review نهایی / گزارش مالک)
- ۶۴۷ رویداد تعدیل بدون کلید دارایی (۹۶ REFERENCE بدون ins_code + ۵۵۱ PRODUCT با ins_code='')؛ از ۱۶۵۱ رویداد symbol-keyed فقط ۱۰۰۴ ins_code دارند. قابل بازیابی از symbol پک + id_crosswalk. پوشش: ۷۶۳۳ keyed / ۶۴۷ keyless.
- adjustment_factor فقط برای ۶۶۲۹ رکورد numeric ساخته می‌شود (۸۰۶ دارایی متمایز).
- minorهای plan-verbatim: try/finally اتصالات؛ shared.db بدون گیت اختصاصی؛ newline انتهایی فایل‌ها.
- Rulingهای 11/12/13 در run_separation.py پیاده شده‌اند (batching/PRAGMA/progress؛ stat قبل/بعد مرجع؛ خلاصهٔ فارسی با ارقام اسکریپتی).

## محدودیت‌های مأموریت (بدون تغییر)
- مرجع read-only (mode=ro&immutable=1)؛ بدون تغییر engine/FTS/Runtime/backend-go؛ بدون push فایل‌های حجیم آرشیو به GitHub؛ بدون merge/release بدون تصمیم مالک.
