# HANDOFF.md — وضعیت تحویل و کارهای باقی‌مانده

> این فایل وضعیت پروژه را در لحظهٔ تحویل ثبت می‌کند تا ادامهٔ کار در سیستم جدید بی‌دردسر باشد.

## وضعیت فعلی (لحظهٔ تحویل)
- **برنچ مرجع:** `master` = `6d9aaa7` · درخت **تمیز** · همهٔ برنچ‌های ایجنت (`agent/tape|fundamental|technical|master-portfolio`) **مرج‌شده**.
- **تست‌ها:** فرانت **۷۷۲/۷۷۲** (سکوئنشال، ۷۳ فایل) سبز · eslint صفر خطا (۳ warning ظاهری) · `vite build` سالم.
- **بک‌اند:** تست‌های فرمول FTS **۷۲/۷۲** سبز (`dev/fts_formula_tests_v2.py`) · خط لولهٔ زنده کار می‌کند (`dev/live_pipeline_check.py`).
- **راه‌اندازی روی سیستم جدید:** طبق `MIGRATION.md` + `setup-agents.ps1`.

## کارهای باقی‌مانده (سه مورد)

### ۱) تکنیکال — ترسیم واقعی الگوها روی چارت (کوچک، آماده برای اتصال)
- **محل:** `frontend/src/features/technical/nahayatnegar/components/KLineChartWrapper.tsx`
- **وضعیت آماده:** موتور `lib/ftsPatterns.ts` (۹ الگو) + سوییچ‌های مستقل (استور + پنل UI) آماده‌اند؛ فقط یک **effect کوتاه `createOverlay`** مانده که خروجی موتور را به اورلی‌های موتور چارت نگاشت کند (فیبو دو باکس، خط جت + هایلایت ۳کندلی، CHoCH، نقطه‌زنی، کف/سقف دوقلو + خط گردن، سر و شانه، سقف سوم، ضربدر MA14).
- **معیار:** `tsc -b` + `vite build` + vitest سکوئنشال سبز؛ الگوی خاموش = بدون overlay؛ بدون افت ۶۰fps.

### ۲) بازار — حذف دو فایل بی‌استفاده (تمیزکاری)
- `frontend/src/features/market/components/VolumeFlow.tsx`
- `frontend/src/__tests__/market-volume-sheet.spec.tsx`
- **وضعیت:** رندرشان از تب برداشته شده و بی‌اثرند؛ حذف با گارد ایمنی سیستم قبلی رد شد. روی سیستم جدید آزادانه حذف شوند.

### ۳) بک‌اند — سه مورد
۱. **ناسازگاری امتیاز/پرچم اسکرینر با کارت جزئیات:** منبع واحد حقیقت مسیر جزئیات است (`api/fundamental._eps_track_blended` / `evaluate_v10`؛ اسکنر در `api/screener.py` + `fts_engine.bulk_scan`). نردبان EPS همراستا شده، ولی برای بقیهٔ شاخص‌ها هم باید یکسان‌سازی شود.
۲. **`exclude_base_market` (رفتار):** کلید در `bors_config.FTS_DEFAULTS` هست ولی رفتارش اعمال نشده — دادهٔ تفکیک «بازار پایهٔ فرابورس» در دیتابیس نیست (جدول `boards` فقط ۱/۲ = بورس/فرابورس). نیازمند منبع داده یا تصمیم به معادل‌گیری `board=2`.
۳. **پرچم تعلیق «A»:** در دادهٔ ما موجود نیست (تنها heuristic «نشست‌های عقب‌مانده» در `fts_engine.is_suspended`). نیازمند منبع وضعیت نماد از کدال/TSETMC.

## دستورهای تأیید (روی سیستم جدید)
```powershell
python dev\fts_formula_tests_v2.py
python dev\live_pipeline_check.py
cd frontend; npm run test -- --run --no-file-parallelism ; npm run build
```

## نکته
بستهٔ نصبی/portable/بیس‌کد را با `.\release.ps1 all` روی سیستم جدید از نو بساز (اول سه متغیر مسیر بالای فایل را تنظیم کن).
