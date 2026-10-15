# موجودیِ تحویل — system‑2 — ۲۰۲۶‑۱۰‑۱۵

مخزن: `https://github.com/johnwarchief/BorsTerminal-src`
اینِ سند **فقط** کارهایی را می‌شمرد که درِ همینِ سیستم (ماشینِ `Johnkallnaya`،
مسیرِ `C:/Users/Johnkallnaya/Desktop/Borsterminal`) دیده یا اجرا شده‌اند.
رأیِ تحویل درِ §۹ است.

---

## ۱) وضعیتِ اولیهٔ Git (پیش ازِ هرِ اقدام — مرحلۀِ ۰)

| قلم | مقدارِ سنجیده‌شده |
|---|---|
| remote | `origin → https://github.com/johnwarchief/BorsTerminal-src.git` (تکِ remote) |
| شاخۀِ checkoutِ اصلی | `mission/fts-indicator-engineering` @ `165bdca` |
| upstream آنِ شاخه | `origin/mission/fts-indicator-engineering` — **ahead 41** (هیچ‌کدام ازِ آنِ ۴۱ کامیت رویِ GitHub نبود) |
| `main` محلی | `1e651b1` — **behind 3** نسبت بهِ `origin/main`؛ دست‌نخورده گذاشته شد |
| worktreeها (شروعِ مأموریت) | `BorsTerminal-src` (checkoutِ اصلی) + `.worktrees/ui-audit-system-2` |
| شاخۀِ UI | `mission/ui-audit-system-2-2026-10-15` @ `165bdca` — **بی‌upstream** (رویِ remote اصلاً وجود نداشت) |
| تغییراتِ ثبت‌نشده درِ checkoutِ اصلی | `M _audit/app_log.txt` (+۹۰۶/−۳۰۶)، `M _audit/RA365-LEDGER-RULE-2026-10-12.csv` (بی‌تغییرِ محتوا، فقطِ خطوطِ 끝 CRLF)، `M dev/fixtures/fts_v10_payloads.json` (همان)، + ۶ فایلِ untrackedِ `_audit/PHASE5F-*.txt` و `_audit/P5G-FINAL-RC.txt` |
| تغییراتِ ثبت‌نشده درِ worktreeِ UI | ۶ فایلِ `frontend/src/**` + `_audit/ui/` (۷ هارنسِ js + JSON/TXT) + `_audit/ui-gates/` |
| هویتِ commit | بی‌تنظیمِ سراسری (`git config user.name` خالی) ⇒ هرِ کامیت باِ `-c user.name/user.email` درِ خودِ فرمان، همانِ رawardِ همیشگیِ اینِ سیستم |

مالکیتِ تغییرات: هرِ ۴۲ کامیتِ شاخۀِ FTS نویسنده‌ای به‌اسمِ `johnwarchief` دارند
و تاریخشان ۲۰۲۶‑۱۰‑۱۱ تاِ ۱۵ است (همانِ سه مأموریتِ اینِ سیستم: فازهایِ تعدیل/FTS،
بازسازیِ «وضعیت بازار»، مأموریتِ عملکرد). کارِ ایجنتِ دیگری درِ اینِ دوِ checkout
ندیدم؛ تنهاِ همپوشانیِ واقعی باِ دیگرِ سیستم‌ها درِ `origin/main` است (§۵).

---

## ۲) شاخه‌ها و worktreeهایِ بررسی‌شده

| مسیر / شاخه | نقش | وضعیتِ انتشار |
|---|---|---|
| `BorsTerminal-src` → `mission/fts-indicator-engineering` | FTS + تعدیل + market-status + perf | منتشر شد (`ff6b2fb`) |
| `.worktrees/ui-audit-system-2` → `mission/ui-audit-system-2-2026-10-15` | ممیزیِ UI (درِ میانه) | منتشر شد (`dd065c1`) |
| `.worktrees/handoff-system-2` → `handoff/system-2/inventory-2026-10-15` | همینِ سند، بریدۀِ `ff6b2fb` | منتشر شد |
| `main` (محلی) | — | **دست‌نخورده**؛ باِ `origin/main` هم‌سنج نیست (§۵) |
| `origin/mission/easytrader-adapter-2026-10-15`, `origin/handoff/system-1/*`, `origin/mission/ui-audit-system-1-2026-10-15`, `origin/feat/android` | کارِ سیستم/ایجنتِ دیگر | فقط *دیدہ* شد؛ واردش نشدم |

---

## ۳) موجودیِ مأموریت‌ها (فیلدهایِ مرحلۀِ ۴)

### ۳‑۱) موتورِ تعدیلِ canonical و فازهایِ FTS (۱ ← ۵F)

| فیلد | محتوا |
|---|---|
| وضعیت | **PARTIAL** (ریاضیِ استخراج‌شده و وصل‌شده؛ پوششِ سنجشِ زنده نه) |
| Branch | `mission/fts-indicator-engineering` |
| HEAD | `ff6b2fb` (پیش ازِ اینِ مأموریت: `165bdca`) |
| Remote | `origin/mission/fts-indicator-engineering` — `09e8d64..ff6b2fb` |
| تغییرات | `adjustment_ledger*`، فازهایِ ۲/۳/۴/۵/۵F درِ `api/chart.py`، `api/ma*`، موتورِ canonicalِ نوع‌محور، `dev/*` گیت‌ها، ۶ سندِ `docs/technical-indicators/reviewed/FTS-PHASE*` |
| تست‌ها | `npx tsc -b` rc=0 · `npx vitest run` ۱۷۱۰ سبز / ۳ skip / ۱۶۶ فایل · `python dev/run_all_tests.py` ۱۲۶ سطرِ `rc=0` (همۀ اینها درِ `165bdca` وِ تاریخ‌هایِ ۱۴۰۵‑۰۷‑۲۱…۲۳ = ۲۰۲۶‑۱۰‑۱۳/۱۴ ثبت شده‌اند) |
| شواهد | `docs/technical-indicators/reviewed/FTS-PHASE4-CANONICAL-ADJUSTMENT-ENGINE-1405-07-21.md` · `FTS-PHASE5-CANONICAL-ADJUSTMENT-LEDGER-LIVE-PARITY-1405-07-22.md` · `FTS-PHASE5F-CLOSURE-ADJUSTMENT-CHART-INTEGRATION-1405-07-23.md` · ماتریسِ حکم: `UNVERIFIED 46 · MISMATCH 27 · PARTIAL_COVERAGE 2` (سطرِ ۶۳ همانِ سند) · `_audit/RA365-PHASE3-DERIVE-2026-10-13.csv` (اکنون tracked) |
| باقی‌مانده | ۴۶ نمادِ sample بی‌مرجع؛ ۲۷ MISMATCH که باید تک‌تک ریشه‌یابی شوند؛ captureِ **تازةِ** مرجع |
| بلاکر | **BLOCKED (خارجی)** — نشستنِ مجازِ مالک درِ rahavard365 لازم است (پروفیلِ رابطِ مرورگر لاگ‌اوت است؛ احراز هویت دور زده نشد) |
| وابستگی | شاخۀِ دیگری لازم ندارد؛ ادامه درِ همینِ شاخه |

### ۳‑۲) بازسازیِ تبِ «وضعیت بازار» (۱۳ صفحۀِ Binder1)

| فیلد | محتوا |
|---|---|
| وضعیت | **DONE_VERIFIED برایِ ۱۳ صفحه، PARTIAL ۲، BLOCKED/بی‌منبع ۱** (همانِ شمارشِ سندِ تحویل) |
| Branch | `mission/fts-indicator-engineering` (کامیت‌هایِ `3e8b917…7752065`) |
| Remote | درِ همانِ push بالا |
| تغییرات | `MarketStatusPage.tsx` (هشت بخش)، `MarketSectionNav`، `MarketTreemap`، `GoldMarketSection`، `MarketChartSection`، `api/market_status.py`، `mstat_engine.py`، `tools/market_status_page_probe.mts` |
| تست‌ها | tsc rc=0 · vitest ۱۷۱۰/۳ (۴۹ بررسیِ تازه درِ ۴ فایل) · `dev/mstat_status_panels_contract_v1.py` · `_audit/ms_binder_ui_check.js` (مرورگرِ واقعی) |
| شواهد | `docs/technical-indicators/reviewed/BINDER1-MARKET-STATUS-DELIVERY-1405-07-22.md` · `BINDER1-MARKET-STATUS-CAPABILITY-MATRIX-1405-07-23.md` (ماتریسِ ۱۲ سطری: ۱۲ PARTIAL) |
| باقی‌مانده | ۲ ردیفِ PARTIALِ سندِ تحویل؛ منبعِ `tedpix` بیرونِ کنترلِ ماست (CDN) |
| بلاکر | برایِ ۸ کارتِ «بی‌منبع» دادهٔ منبع نیست، نه کد |
| وابستگی | — |

### ۳‑۳) مأموریتِ عملکردِ کم‌توان

| فیلد | محتوا |
|---|---|
| وضعیت | **PARTIALLY_IMPROVED — EXPLICIT_REMAINING_BOTTLENECKS** (رأیِ خودِ گزارش، سطرِ ۲۰۲) |
| Branch | `mission/fts-indicator-engineering` (`0d0b76f`, `b9681e2`, `165bdca`) |
| Remote | درِ همانِ push بالا |
| تغییرات | `mstat_engine.py` (کشِ سطحِ پروسه + حافظۀِ decode)، `api/market_status.py` (یکِ اتصال)، `api/_sync_market.py` (تصمیمِ همگام‌سازی)، `app.py` (تأخیرِ warm)، `dev/mstat_snapshot_cache_v1.py`، `dev/perf_output_equal_v1.py` |
| تست‌ها | درِ `165bdca`: tsc PASS · vitest ۱۷۱۰ سبز/۳ skip (۲۹۰ ثانیه) · `dev/run_all_tests.py` ۱۲۶ سطرِ `rc=0` · `dev/mstat_snapshot_cache_v1.py` ۱۰/۱۰ · `perf_output_equal_v1.py` باِ کنترلِ جبری |
| شواهد | `_audit/perf/PERFORMANCE_REPORT.md` · `_audit/perf/BEFORE_AFTER.md` · `BOOT_TIMELINE.json` · `OUTPUT_EQUALITY_*.json` |
| باقی‌مانده (همانِ گزارش) | پرکردنِ `fts_results` توسطِ `dev/codal_fts_updater.py` (حذفِ ۴۶–۱۳۸ ثانیهٔ تبِ بنیادی)؛ کش‌شکنِ `fts_engine` ازِ `id(conn)` بهِ کلیدِ حالتِ بانک؛ تصمیمِ مالک دربارهٔ تکه‌تکه‌کردنِ اولینِ `/api/market` |
| بلاکر | «حذفِ داده برایِ کمِ‌کردنِ payload» درِ Stage 4 مأموریت ممنوع بود ⇒ نیازمندِ رأیِ صریحِ مالک |
| تست‌هایِ **NOT RUN** (مستند درِ §۱۰ِ همانِ گزارش) | سنجشِ مرورگریِ نسخۀِ نصبی (:8001، کدِ فریزشده، restart اجازه نداشت) · گیتِ ماشینیِ زمان‌بندیِ بوت · طرفِ «قبل» درِ `/master` باِ نشانۀِ درست |

### ۳‑۴) ممیزیِ سراسریِ UI (system‑2) — **نیمه‌تمام، درِ همینِ سیستم**

| فیلد | محتوا |
|---|---|
| وضعیت | **IN_PROGRESS** |
| Branch | `mission/ui-audit-system-2-2026-10-15` |
| HEAD | `dd065c1` (کامیت‌ها: `9811104` اصلاحِ پوسته، `dd065c1` هارنس‌ها + شواهد) |
| Remote | `origin/mission/ui-audit-system-2-2026-10-15` (تازةِ منتشرشده، upstream بند شد) |
| تغییرات | `AppShell.tsx` (`h-dvh`)، `Topbar.tsx`/`SymbolContextStrip.tsx` (`shrink-0`، خارج ازِ چسبان)، `MarketSectionNav.tsx` (`--chrome-h` + تک‌ردیفه + scroll‑margin)، `MarketChartSection.tsx` (میزبانِ ۵۲۰px)، `index.css` (توکن) |
| تست‌ها | **رویِ همینِ ۶ فایلِ تغییریافته**: glyph guard ۴/۴ · `npx tsc -b` exit 0 · `npx vitest run` رویِ ۵ فایلِ مرتبط = **۵ فایل / ۵۵ آزمون سبز** · `npm run build` موفق. `npx vitest run`ِ کامل وِ `dev/run_all_tests.py` **بعدِ اینِ تغییرات اجرا نشده‌اند** ⇒ هرِ ادعایِ سبزِ کامل بهِ `165bdca` برمی‌گردد و **STALE** است |
| شواهد | `docs/ui-audit/2026-10-15-system-2-STATUS.md` + `_audit/ui/*.json|txt` + ۷ هارنسِ `_audit/ui/*.js` (دستورهایِ بازتولید درِ §۵ آنِ سند) |
| باقی‌مانده | ۸ یافتهٔ باز درِ §۳ آنِ سند (سرریزِ ۳۳pxِ چارتِ تکنیکال، گیرِ کلیکِ `open-chart-settings`، Escape نبودنِ داور، ۱۳ قدمِ سنجیده‌نشده، `--mode=real`، مرحلۀِ ۴ِ ابزارهایِ رسم، سندِ مرحلۀِ ۷، گیت‌هایِ کامل) |
| بلاکر | هیچِ دسترسی لازم نیست؛ فقطِ ادامهِٔ کارِ خودی (هارنس باید منتظرِ خودِ دستگیره بنشیند نه زمانِ ثابت) |
| وابستگی | شاخه ازِ `165bdca` می‌آید؛ اگرِ FTS/perf برود رویِ `origin/main`، اینِ دوِ شاخه هم باید rebase شوند (§۵) |

### ۳‑۵) حوزه‌هایی که درِ اینِ سیستم **وجود ندارند**

| حوزه | سنجشِ من درِ اینِ ماشین | رأی |
|---|---|---|
| EasyTrader / سرخطی | `git ls-files` رویِ HEAD: ۰ فایلِ هم‌نام؛ هیچِ branch محلی‌ای باِ اینِ نام نیست (رویِ remote: `origin/mission/easytrader-adapter-2026-10-15`) | **NOT_STARTED (درِ اینِ سیستم — کارِ سیستمِ دیگر)** |
| رباتِ معامله‌گرِ کاغذی / `/api/execution` | ۰ فایلِ `paper.?trad|execution` درِ HEAD؛ رویِ `origin/main` کامیت‌هایِ `feat(bot)`/`feat(execution)` ازِ نشستِ دیگر هست | **NOT_STARTED (اینجا)** |
| اندروید | ۰ فایل/پوشه درِ HEAD؛ `origin/feat/android` متعلق بهِ جایِ دیگر است | **NOT_STARTED (اینجا)** |
| صفِ CODAL / پنلِ سلامتِ خطِ کدال | درِ HEAD ما فقط `dev/codal_fts_updater.py` وِ بخشِ بنیادیِ کهنه هست؛ صدها کامیتِ `feat(codal)` درِ `origin/main` است که ما آن را نداریم | **UNVERIFIED (وابسته بهِ merge باِ main)** |
| تست/ابزار/سندِ مشترک | `dev/*.py` گیت‌ها وِ `docs/technical-indicators/**` درِ شاخۀِ ما منتشر شده‌اند | DONE_VERIFIED (همانِ §۳‑۱…۳) |

---

## ۴) انتشارها (مرحلۀِ ۳) — SHA و URLِ تأییدشده

| شاخه | بازۀِ push | HEAD remote | URL |
|---|---|---|---|
| `mission/fts-indicator-engineering` | `09e8d64..ff6b2fb` (fast‑forward، ۴۲ کامیت) | `ff6b2fb` | https://github.com/johnwarchief/BorsTerminal-src/tree/mission/fts-indicator-engineering |
| `mission/ui-audit-system-2-2026-10-15` | `[new branch]` | `dd065c1` | https://github.com/johnwarchief/BorsTerminal-src/tree/mission/ui-audit-system-2-2026-10-15 |
| `handoff/system-2/inventory-2026-10-15` | `[new branch]` ازِ `ff6b2fb` | `8fc44b7` (+ همینِ تصحیح) | https://github.com/johnwarchief/BorsTerminal-src/tree/handoff/system-2/inventory-2026-10-15 |

بی‌force-push، بی‌tag، بی‌release، بی‌merge. `main` وِ هیچِ شاخۀِ دیگری دست‌نخورده ماند.

### ۴‑۱) راستی‌آزماییِ پس ازِ push (همه باِ فرمان، نه باِ خاطره)

| بررسی | فرمان | نتیجه |
|---|---|---|
| هم‌خوانیِ SHA محلی/remote | `git ls-remote origin refs/heads/<b>` درِ برابرِ `git rev-parse <b>` | هرِ سه شاخه **MATCH** (`ff6b2fb`, `dd065c1`, `8fc44b7`) |
| باقی‌ماندۀِ push‌نشده | `git log --branches --not --remotes --oneline` | **خالی** |
| وجودِ سندِ موجودی رویِ remote | `git ls-tree -r origin/handoff/system-2/inventory-2026-10-15` | `docs/handoff/2026-10-15-system-2-inventory.md` |
| محتوایِ شاخۀِ UI | `git ls-tree -r … | grep` | ۷ هارنسِ js · ۲۲ شاهدِ json/txt · ۱ سندِ وضعیت · **۰ تصویرِ png** · **۰ backend.log** |
| شاهدِ مأموریتِ عملکرد رویِ شاخۀِ FTS | `git ls-tree -r …` | `_audit/perf/PERFORMANCE_REPORT.md` · `BEFORE_AFTER.md` · `dev/mstat_snapshot_cache_v1.py` · `dev/perf_output_equal_v1.py` |
| وضعیتِ working treeها | `git status --short` | worktreeهایِ UI وِ handoff **پاک**؛ checkoutِ اصلی فقطِ ۸ قلمِ §۷ (دوِ فایلِ CRLF‑only وِ ۶ لاگِ scratch) — پاک نشدند، stage نشدند |

---

## ۵) تفکیکِ شاخه/نسخه و ریسکِ conflict (مرحلۀِ ۵)

1. **ازِ قبل رویِ `github/main`:** ۸۹ کامیت ازِ نقطۀِ جدا شدنِ ما (تاریخِ ۲۰۲۶‑۱۰‑۱۲ به‌بعد): `feat(codal)`، `feat(bot)`/`/api/execution`، `feat(watch)`، `perf(mstat)`، releasesِ `v1.0.87` وِ `v1.0.88`. هیچ‌یک ازِ اینها درِ دوِ شاخۀِ ماست.
2. **commitهایی که محلی بودند و اکنون push شده‌اند:** همان ۴۲ (FTS/وضعیت‌بازار/عملکرد/سند) + ۲ِ ممیزیِ UI.
3. **تغییراتِ منتشرشده رویِ شاخه‌هایِ مستقل:** سه شاخۀِ §۴.
4. **هنوز فقط رویِ اینِ ماشین:** دو فایلِ `M` بی‌تغییرِ محتوا (فقطِ خطوطِ 끝: `_audit/RA365-LEDGER-RULE-2026-10-12.csv`، `dev/fixtures/fts_v10_payloads.json`) وِ ۶ لاگِ scratchِ `_audit/PHASE5F-*` وِ `_audit/P5G-FINAL-RC.txt` وِ `_audit/ui/backend.log` وِ ۱۶۸ تصویرِ `_audit/ui/shots/*.png` وِ پوشۀِ `frontend/dist/` (ignored) — علتشان درِ §۸.
5. **همپوشانی:** `api/market_status.py` وِ `mstat_engine.py` درِ **هر دو** سو ازِ `f5a1016` عوض شده‌اند (اختلافِ موجود: ۳۴۰ وِ ۵۸۲ سطر). یعنی سیستمِ دیگر رویِ main همانِ اندپوینت/موتور را دوباره کار کرده است.
6. **ریسکِ conflict (عددِ دقیق):** نقطۀِ مشترکِ جدایی `f5a10166` (۲۰۲۶‑۱۰‑۱۱). ما ۵۱ کامیت وِ ۳۱۰ فایل؛ `origin/main` ۸۹ کامیت وِ ۳۳۳ فایل؛ **۲۷ فایل درِ هر دو سو تغییده شده‌اند** — پرخطرترینها: `api/market_status.py`، `api/chart.py`، `app.py`، `frontend/src/app/components/Topbar.tsx`، `frontend/src/features/market/routes/MarketStatusPage.tsx`، `MarketStatusTables.tsx`، `MarketPulseBar.tsx`، `FtsFunnelAllStages.tsx`، `MasterFtsDetails.tsx`، `SymbolInspector.tsx`، `dev/run_all_tests.py`، `.gitignore`، `fts_terminal.spec`. هیچِ merge‌ای انجام نشد (ممنوعِ مأموریت).
7. **چه چیزی درِ نسخۀِ نصبی/Frozen/Portable نیست:** نسخۀِ نصبیِ درِ حالِ اجرا `v1.0.86` رویِ `127.0.0.1:8001` (PID 5336) است وِ `BorsTerminal_Portable_v1.0.86.zip` رویِ دسکتاپ؛ `APP_VERSION` شاخۀِ ما ۱.۰.۸۶ وِ `origin/main` ۱.۰.۸۸. `git tag --contains HEAD` خالی است ⇒ **هیچ‌یک ازِ کارهایِ اینِ سه شاخه درِ هیچِ tag یا بیلدِ منتشرشده نیست** (نه تبِ وضعیتِ بازارِ بازسازی‌شده، نه اصلاحاتِ عملکرد، نه اصلاحِ پوستهٔ UI).
8. **تست/آزمونِ اجرا‌نشده:** §۳‑۳ (سنجشِ مرورگریِ نسخۀِ نصبی، گیتِ زمان‌بندیِ بوت)، §۳‑۴ (۱۳ قدمِ تعاملی، جاروبِ حالتِ واقعی، suiteِ کامل)، §۳‑۱ (captureِ تازةِ مرجع به‌خاطرِ نشستِ مالک). هیچِ سفارشِ واقعی هیچ‌وقت ارسال نشد وِ بانکِ عملیاتی تغییر داده نشد.

---

## ۶) امنیت و Secretها (مرحلۀِ ۲)

- diffِ tracked (`_audit/app_log.txt`) وِ ۳۳ فایلِ artefact باِ الگویِ `password|passwd|secret|token|authorization|cookie|api[_-]?key|bearer` جاروب شد → **۰ باندۀِ credential** درِ آنچه منتشر شد. مقدارِ هیچِ Secretی درِ خروجیِ ابزار چاپ نشد (بازبینی باِ ماسک/طبقه‌بندیِ PATH|HEX|BLOB انجام شد).
- نمادهایِ ورودِ harness ازِ `frontend/src/shared/stores/authStore.ts` درِ زمانِ اجازه خوانده می‌شوند و درِ هیچِ فایلِ `_audit/ui/**` نوشته نمی‌شوند (بررسیِ مستقیمِ حضورِ مقدار: ۰).
- **به مالک هشدار داده می‌شود (وضعیتِ ازِ قبل موجود، نه ساختۀِ اینِ مأموریت):** `authStore.ts` دوِ ثابتِ «ورودِ پیش‌فرضِ توسعه» دارد (طولِ کاربر ۸، طولِ رمز ۷) که درِ مخزنِ tracked نشسته است. اگر اینها رویِ حسابِ واقعی/کاری استفاده می‌شوند، باید چرخانده شوند و ازِ کدِ مخزن بیرون بروند. من نه پاکشان کردم نه بازنویسیِ تاریخچه.
- ۴ لاگِ scratchِ راه‌اندازیِ مرورگر (`_audit/PHASE5F-CAPTURE*.txt`) که سطرهایشان کلماتِ `نشست/token/password` وِ آرگومانهایِ خطِ فرمانِ Edge دارد **عمداً منتشر نشدند** (احتمالِ شناسۀِ نشستِ مرورگر). پاک نشدند؛ رویِ دیسکِ همینِ ماشین ماندند.
- بانکِ عملیاتی/`*.db`/dump منتشر نشد (`_audit/.gitignore` مانعِ `*.db` است) وِ برایِ اینِ مأموریت هیچِ دادهٔ تولیدی تغییر نکرد.

---

## ۷) آنچه عمداً منتشر نشد وِ چرا (مرحلۀِ ۶)

| قلم | علت |
|---|---|
| ۱۶۸ فایلِ `PNG` درِ `_audit/ui/shots/**` (≈۲۰ مگابایت) | `*.png` درِ `_audit/.gitignore`؛ سنگینِ مخزن. گزینۀِ فشرده باید بهِ `docs/ui-audit/` برود (کارِ مرحلۀِ ۷ِ مأموریتِ UI، هنوز انجام نشده) |
| `_audit/ui/backend.log` (۱۸۶KB) | لاگِ خامِ سرویسِ dev؛ artefactِ زمانِ اجرا، نه شاهدِ قابلِ بازبینی |
| `_audit/PHASE5F-CAPTURE*.txt`، `_audit/PHASE5F-SELECTION-RUN.txt`، `_audit/PHASE5F-SHAPE.txt`، `_audit/P5G-FINAL-RC.txt` | scratchِ لاگِ راه‌اندازیِ مرورگر باِ کلماتِ نشست/رمز (§۶)؛ P5G فقطِ یکِ شمارۀِ بازگشتِ ۳۲ بایتی است |
| دوِ فایلِ CRLF‑onlyِ `M` | بی‌تغییرِ محتوا؛ کامیتِ بی‌محتوا تاریخچه را شلوغ می‌کرد. **هنوز درِ working tree هستند و پاک/بازگردانی نشدند** |
| `frontend/dist/**` | ignored؛ بیلدِ محلی برایِ سنجشِ مرورگری ساخته می‌شود |

---

## ۸) آخرینِ اعتبارسنجیِ معتبر (باِ تاریخ وِ SHA)

| گیت | SHAِ مرجع | تاریخ | نتیجه |
|---|---|---|---|
| `npx tsc -b` | `165bdca` | ۲۰۲۶‑۱۰‑۱۵ | PASS (exit 0) |
| `npx vitest run` (کل) | `165bdca` | ۲۰۲۶‑۱۰‑۱۵ | ۱۷۱۰ سبز / ۳ skip / ۱۶۶ فایل |
| `python dev/run_all_tests.py` | `165bdca` | ۲۰۲۶‑۱۰‑۱۵ | ۱۲۶ سطرِ `rc=0`، ALL SUITES PASSED |
| `npx eslint .` | `165bdca` | ۲۰۲۶‑۱۰‑۱۵ | **FAIL ازِ پیشِ اینِ مأموریت** — ۳ خطا: `engine-klinecharts-adapter.spec.ts:21` (prefer‑const)، `funnel-preset-switch.spec.tsx:1` (ban‑ts‑comment)، `technical-settings-effectiveness.spec.tsx:114` (no‑explicit‑any)؛ درِ §۸ِ گزارشِ عملکرد مستند |
| glyph + tsc + ۵۵ آزمونِ هدفمند + build | `dd065c1` | ۲۰۲۶‑۱۰‑۱۵ | همۀ سبز (این تنهاِ گیتِ معتبرِ **بعدِ** اصلاحِ پوسته است) |
| suiteِ کاملِ JS/PY | `dd065c1` | — | **NOT RUN** — وِ چونِ ۶ فایلِ frontend ازِ `165bdca` عوض شده، شمارشِ بالا برایِ اینِ کد **STALE** خوانده می‌شود، نه سبز |

---

## ۹) رأیِ نهاییِ تحویل

`HANDOFF_COMPLETE`

همۀ کارهایِ محلیِ منتشرشدنیِ اینِ سیستم رویِ GitHub هستند (سه شاخه، باِ upstream،
بی‌force/merge/tag)؛ وضعیتِ واقعیِ هرِ حوزه — از جمله دوِ مأموریتِ **PARTIAL**، یکِ
مأموریتِ **IN_PROGRESS**، وِ سه حوزۀِ **NOT_STARTED/بیرونِ اینِ سیستم** — درِ همینِ سند
ثبت شده؛ مواردِ منتشرنشده باِ علتِ مشخص درِ §۷ هستند وِ هیچِ کارِ ناقصی برایِ سبک‌تر
شدنِ گزارش پاک یا بازنویسی نشد.

**ادامه‌دادنِ کار ازِ همینِ نقاط:**
۱) `mission/ui-audit-system-2-2026-10-15` §۳‑ب (سرریزِ ۳۳pxِ چارتِ تکنیکال) → ۲) §۳‑پِ
همانِ سند (گیرِ کلیکِ تنظیماتِ چارت) → ۳) suiteِ کاملِ بعدِ اصلاحِ UI → ۴) تصمیمِ
مالک دربارهٔ آمیختنِ `api/market_status.py`/`mstat_engine.py` باِ نسخهِٔ `origin/main`
(۲۷ فایلِ همپوشان).
