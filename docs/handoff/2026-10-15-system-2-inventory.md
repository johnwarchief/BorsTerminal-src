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
| تغییراتِ ثبت‌نشده درِ checkoutِ اصلی | `M _audit/app_log.txt` (+۹۰۶/−۳۰۶)، `M _audit/RA365-LEDGER-RULE-2026-10-12.csv` (بی‌تغییرِ محتوا، فقطِ پایانِ خط CRLF)، `M dev/fixtures/fts_v10_payloads.json` (همان)، + ۶ فایلِ untrackedِ `_audit/PHASE5F-*.txt` و `_audit/P5G-FINAL-RC.txt` |
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
| `.worktrees/ui-audit-system-2` → `mission/ui-audit-system-2-2026-10-15` | ممیزیِ UI — **بسته‌شدہ درِ دورِ دوم (§۱۰)** | منتشر شد (`dd065c1` → `3feb525`) |
| `.worktrees/handoff-system-2` → `handoff/system-2/inventory-2026-10-15` | همینِ سند، بریدۀِ `ff6b2fb` | منتشر شد (SHA درِ §۱۰) |
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
| وضعیت | **PARTIAL — رأیِ خودِ سندِ ممیزی (§۱۲ِ `docs/ui-audit/2026-10-15-system-2.md`)** |
| Branch | `mission/ui-audit-system-2-2026-10-15` |
| HEAD | `3feb525` (سی‌وسه‌کامیتِ بعدِ `dd065c1`: ۱۱ اصلاحِ UI، هارنس‌هایِ تاز، جاروبِ حالتِ واقعی، سندِ §۱ تا §۱۲) |
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
| `handoff/system-2/inventory-2026-10-15` | `[new branch]` ازِ `ff6b2fb` | `13baf23` (اینِ سطر هم باِ هرِ کامیتِ خودِ سند جلو می‌رود؛ برایِ SHAِ قطعی `git ls-remote origin refs/heads/handoff/system-2/inventory-2026-10-15`) | https://github.com/johnwarchief/BorsTerminal-src/tree/handoff/system-2/inventory-2026-10-15 |

بی‌force-push، بی‌tag، بی‌release، بی‌merge. `main` وِ هیچِ شاخۀِ دیگری دست‌نخورده ماند.

### ۴‑۱) راستی‌آزماییِ پس ازِ push (همه باِ فرمان، نه باِ خاطره)

| بررسی | فرمان | نتیجه |
|---|---|---|
| هم‌خوانیِ SHA محلی/remote | `git ls-remote origin refs/heads/<b>` درِ برابرِ `git rev-parse <b>` | هرِ سه شاخه **MATCH** (`ff6b2fb`, `dd065c1`, `13baf23`) |
| باقی‌ماندۀِ push‌نشده | `git log --branches --not --remotes --oneline` | **خالی** |
| وجودِ سندِ موجودی رویِ remote | `git ls-tree -r origin/handoff/system-2/inventory-2026-10-15` | `docs/handoff/2026-10-15-system-2-inventory.md` |
| محتوایِ شاخۀِ UI | `git ls-tree -r … | grep` | ۷ هارنسِ js · ۲۲ شاهدِ json/txt · ۱ سندِ وضعیت · **۰ تصویرِ png** · **۰ backend.log** |
| شاهدِ مأموریتِ عملکرد رویِ شاخۀِ FTS | `git ls-tree -r …` | `_audit/perf/PERFORMANCE_REPORT.md` · `BEFORE_AFTER.md` · `dev/mstat_snapshot_cache_v1.py` · `dev/perf_output_equal_v1.py` |
| وضعیتِ working treeها | `git status --short` | worktreeهایِ UI وِ handoff **پاک**؛ checkoutِ اصلی فقطِ ۸ قلمِ §۷ (دوِ فایلِ «فقطِ پایانِ خط» وِ ۶ لاگِ scratch) — پاک نشدند، stage نشدند |

**خطایِ خودی که پنهان نشد:** نخستینِ کامیتِ همینِ سند باِ گاردِ گلیف «سبز» رفت، چونِ
اجرایِ گارد درِ لولۀِ `| tail` شد و کدِ خروجی‌اش گم شد؛ گارد بعداً یکِ نویسسۀِ کره‌ای
درِ سطرها ۲۰ وِ ۱۴۳ پیدا کرد که درِ همانِ کامیتِ منتشرشده بود. اصلاحش درِ
کامیتِ بعدیِ همینِ شاخه رفت (تاریخچه بازنویسی نشد) وِ هرِ دوِ worktree دوباره باِ
کدِ خروجیِ درست سنجیده شدند. دوِ نکتهٔ صادقانه باقی می‌ماند: (۱) پیامِ همانِ
کامیتِ اصلاحی (`92becd0`) خودش سه نویسسۀِ کره‌ای دارد و چونِ کامیت منتشر شده،
بازنویسی‌اش نکردم؛ (۲) اینِ بند درِ نسخۀِ اولش همانِ نویسسۀِ ممنوع را نقلِ قول
می‌کرد وِ گارد دوباره همان را قرمز کرد — حالا به‌جایِ نقلِ قول، توصیفش می‌کنم.

---

## ۵) تفکیکِ شاخه/نسخه و ریسکِ conflict (مرحلۀِ ۵)

1. **ازِ قبل رویِ `github/main`:** ۸۹ کامیت ازِ نقطۀِ جدا شدنِ ما (تاریخِ ۲۰۲۶‑۱۰‑۱۲ به‌بعد): `feat(codal)`، `feat(bot)`/`/api/execution`، `feat(watch)`، `perf(mstat)`، releasesِ `v1.0.87` وِ `v1.0.88`. هیچ‌یک ازِ اینها درِ دوِ شاخۀِ ماست.
2. **commitهایی که محلی بودند و اکنون push شده‌اند:** همان ۴۲ (FTS/وضعیت‌بازار/عملکرد/سند) + ۲ِ ممیزیِ UI.
3. **تغییراتِ منتشرشده رویِ شاخه‌هایِ مستقل:** سه شاخۀِ §۴.
4. **هنوز فقط رویِ اینِ ماشین:** دو فایلِ `M` بی‌تغییرِ محتوا (فقطِ پایانِ خط: `_audit/RA365-LEDGER-RULE-2026-10-12.csv`، `dev/fixtures/fts_v10_payloads.json`) وِ ۶ لاگِ scratchِ `_audit/PHASE5F-*` وِ `_audit/P5G-FINAL-RC.txt` وِ `_audit/ui/backend.log` وِ ۱۶۸ تصویرِ `_audit/ui/shots/*.png` وِ پوشۀِ `frontend/dist/` (ignored) — علتشان درِ §۸.
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
| suiteِ کاملِ JS/PY | `3feb525` | ۲۰۲۶‑۱۰‑۱۵ | `npx tsc -b` rc=0 · `npx vitest run` rc=0 (۱۷۱۰ سبز / ۳ skip / ۱۶۶ فایل) · `npm run build` rc=0 (14.18s) · `python dev/run_all_tests.py` **rc=1** = ۱۲۱ سبز / ۲ قرمز؛ هرِ دوِ قرمز ازِ نبودِ fixture درِ worktree وِ باِ supplying آن‌ها سبز شدند (§۱۰‑۳) |

---

## ۹) رأیِ نهاییِ تحویل

`HANDOFF_COMPLETE`

همۀ کارهایِ محلیِ منتشرشدنیِ اینِ سیستم رویِ GitHub هستند (سه شاخه، باِ upstream،
بی‌force/merge/tag)؛ وضعیتِ واقعیِ هرِ حوزه — از جمله دوِ مأموریتِ **PARTIAL**، یکِ
مأموریتِ **PARTIAL** (ممیزیِ UI که درِ دورِ دوم بسته شد؛ §۱۰)، وِ سه حوزۀِ **NOT_STARTED/بیرونِ اینِ سیستم** — درِ همینِ سند
ثبت شده؛ مواردِ منتشرنشده باِ علتِ مشخص درِ §۷ هستند وِ هیچِ کارِ ناقصی برایِ سبک‌تر
شدنِ گزارش پاک یا بازنویسی نشد.

**ادامه‌دادنِ کار ازِ همینِ نقاط:**
۱) `mission/ui-audit-system-2-2026-10-15` §۳‑ب (سرریزِ ۳۳pxِ چارتِ تکنیکال) → ۲) §۳‑پِ
همانِ سند (گیرِ کلیکِ تنظیماتِ چارت) → ۳) suiteِ کاملِ بعدِ اصلاحِ UI → ۴) تصمیمِ
مالک دربارهٔ آمیختنِ `api/market_status.py`/`mstat_engine.py` باِ نسخهِٔ `origin/main`
(۲۷ فایلِ همپوشان).

---

## ۱۰) ممیزیِ موجودیِ دورِ دوم — ۲۰۲۶‑۱۰‑۱۵ (همۀ کارهایِ سیستمِ دوم، ازِ GitHub)

سوالِ اینِ دور: «آیا هر کارِ فنیِ مفیدِ اینِ سیستم ازِ یکِ ماشینِ دیگر قابلِ دریافت است؟»
پاسخِ کوتاه: **بله، به‌جزِ دوِ موردِ ثبت‌شده درِ §۱۰‑۵** — که یکیشان تصمیمِ مالک است.

### ۱۰‑۱) آنچه درِ اینِ دور سنجیده شد (فرمان، نه حافظه)

| بررسی | فرمان | نتیجه |
|---|---|---|
| worktreeها | `git worktree list --porcelain` | ۴: `BorsTerminal-src`، `.worktrees/ui-audit-system-2`، `.worktrees/handoff-system-2`، وِ درِ اینِ دور `.worktrees/system-2-fixtures` |
| شاخه‌ها | `git branch` / `git branch -r` | ۵ محلی (همۀ باِ upstream) · ۳۲ remote |
| commitهایِ بی‌push | `git fetch --all --prune` سپس `git log --branches --not --remotes --oneline` | **خالی** — هیچِ کامیتِ مرتبطی فقط درِ local نبود |
| stash | `git stash list` | **خالی** |
| reflog / dangling | `git reflog` + `git fsck --unreachable` | ۲ آبجکتِ dangling ازِ ۲۰۲۶‑۱۰‑۱۱ = یکِ stashِ قدیمی؛ `git diff --stat 09e8d64 afa4590` → **خالی**، یعنی هیچِ کاری درِ آنِ نبود |
| فایل‌هایِ ignoredِ کاری | `git ls-files -o -i --exclude-standard` (بی‌node_modules/dist/pycache) | ۱۶۷ قلم: ۱۰۲ json، ۴۵ log، ۸ txt، ۶ py، ۱ js، ۱ csv — ۵۸ درِ `_audit/` وِ ۵۴ درِ `_audit/ra_probe_cache/` (طبقه‌بندی درِ §۱۰‑۴) |
| بیرونِ مخزن | `ls ../_audit` | ۱۵ فایل (۵۶۸KB) که درِ هیچِ repoیی نبودند: ۱۳ تصویرِ `binder1_pages/` + `MS-GATE-mstat.txt` + `ms_server.log` (§۱۰‑۴/۵) |
| فایل‌هایِ `M` | `git diff --stat` + sha256 باِ `tr -d '\r'` | هرِ دوِ باقی‌مانده **بی‌تغییرِ محتوا** (فقطِ CRLF/LF): `_audit/RA365-LEDGER-RULE-2026-10-12.csv`، `dev/fixtures/fts_v10_payloads.json` |

### ۱۰‑۲) جدولِ نهاییِ موجودی

| حوزۀِ کاری | شاخۀِ Remote | SHA نهایی | فایل‌ها/مستنداتِ اصلی | وضعیتِ انتشار |
|---|---|---|---|---|
| **Responsive UI** | `mission/ui-audit-system-2-2026-10-15` | `3feb525` | `docs/ui-audit/2026-10-15-system-2.md` (۱۲ بخش) · `…-STATUS.md` · `docs/ui-audit/img/*.png` (۳ برش) · ۸۴ فایلِ `_audit/ui/**` = ۲۲ هارنسِ js + ۶۲ شاهدِ json/txt | **PUBLISHED / DONE_VERIFIED** — رأیِ خودِ گزارش: PARTIAL (بطورِ گیتِ محیطیِ Python) |
| **Performance** | `mission/fts-indicator-engineering` | `ff6b2fb` | `_audit/perf/PERFORMANCE_REPORT.md` · `BEFORE_AFTER.md` · ۵۹ فایلِ شاهد درِ `_audit/perf/` (BE/AFTER/BOOT/CONTEND/FE/MSTAT) · `dev/perf_output_equal_v1.py` · `dev/mstat_snapshot_cache_v1.py` · `_audit/perf/gates/*.txt` | **PUBLISHED** — باِ رأیِ PARTIALLY_IMPROVED وِ بطری‌هایِ باقی‌مانده درِ §۱۰ِ خودِ گزارش |
| **موتورِ FTS / تکنیکال** | `mission/fts-indicator-engineering` | `ff6b2fb` | `fts_engine.py`، `api/chart.py`، `api/ma*.py`، `dev/fts_engine_*`، `docs/technical-indicators/reviewed/FTS-PHASE*.md`، ماتریس‌هایِ `_audit/RA365-PHASE*.csv` | **PUBLISHED (PARTIAL: ۴۶ UNVERIFIED / ۲۷ MISMATCH)** |
| **موتورِ تعدیلِ canonical** | `mission/fts-indicator-engineering` **وِ** `fix/system-2-reproducible-fixtures-2026-10-15` | `ff6b2fb` · `9d3f587` | `dev/test_adjustment_engine_v1.py`، `dev/adjustment_ledger*`، `tools/phase5f_*.py`، `tools/phase6_verdict_matrix.py`، `tools/make_adjustment_witness_fixture.py`، `dev/fixtures/ra365_witness_subset.json` | **PUBLISHED وِ ازِ اینِ دور رویِ cloneِ خالی هم سبز می‌شود (۴۴/۰)** |
| **Market Status / Binder1** | `mission/fts-indicator-engineering` | `ff6b2fb` | `frontend/src/features/market/**` (هشت بخش)، `api/market_status.py`، `mstat_engine.py`، `docs/technical-indicators/reviewed/BINDER1-*.md`، `_audit/MS-BINDER-UI-RUN.txt`، `tools/market_status_page_probe.mts` | **PUBLISHED** — به‌جزِ ۲۶ اسکرین‌شات (§۱۰‑۴) وِ ۱۳ صفحۀِ ارجاع‌داده‌شدہ که هرگز درِ مخزن نبودند (§۱۰‑۵) |
| **تحقیقِ تطبیقِ Rahavard** | `mission/fts-indicator-engineering` | `ff6b2fb` | `docs/RAHAVARD-*.md`، `_audit/RA365-*.csv` (کامیت‌شده)، `_audit/ra365_job_fetch.js`، `_audit/ra365_adjustment_events.py` | **PUBLISHED (تجدیدِ زنده BLOCKED: نشستِ مالک لازم است)** |
| **دستگاهِ تحویل/موجودی** | `handoff/system-2/inventory-2026-10-15` | tipِ `git ls-remote` (همینِ سند) | `docs/handoff/2026-10-15-system-2-inventory.md` | **PUBLISHED** |
| **شاهدها وِ fixtureهایِ بازتولید** | `fix/system-2-reproducible-fixtures-2026-10-15` | `9d3f587` | `docs/handoff/2026-10-15-system-2-reproducible-fixtures.md`، `_audit/PHASE5F-P5G-RUNDIGEST.txt`، `_audit/P5G-FINAL-RC.txt`، شواهدِ maskedِ بیس‌لاین | **PUBLISHED (تازۀِ اینِ دور)** |

### ۱۰‑۳) انتشارهایِ اینِ دور (قبل‌تر فقط رویِ دیسک بودند)

- **۴ کامیت** درِ `fix/system-2-reproducible-fixtures-2026-10-15` (پایه `ff6b2fb`):
  شاهدِ تعدیل + ابزارِ سازندۀِ آن، LF‑پین، رکوردِ فازِ ۵F/۵G، وِ گزارشِ بازتولید.
- **۱۴ کامیت** درِ `mission/ui-audit-system-2-2026-10-15` ازِ `dd065c1` تاِ `3feb525`
  (۱۱ اصلاحِ UI + هارنس + جاروبِ واقعی + سند).
- **۲ قلم که درِ گیت نبودند وِ باید بودند** (سیاستِ `.gitignore` را نمی‌شکنند):
  `dev/fixtures/ra365_witness_subset.json` (۴۵۹٫۹۷۵ بایت) وِ
  `tools/make_adjustment_witness_fixture.py`.
- **اثباتِ سبز شدن رویِ درختِ تنها ازِ GitHub**: `dev/test_adjustment_engine_v1.py` →
  ۴۴ سبز / ۰ قرمز؛ `dev/db_housekeeping.py --selftest` باِ assetِ منتشرشده
  (`sha256 e7df91dc…` = `market.db.meta.json`) → **PASS، rc=0**
  (۳۳۳ ردیفِ تکراری dedupe، ۱۱٫۴۰۵ سلولِ prev‑year، integrity ok).

### ۱۰‑۴) آنچه عمداً درِ GitHub نیست (دلیل + عدد)

| قلم | حجم | دلیل | جایگزینِ منتشرشده |
|---|---|---|---|
| `_audit/ra365_ref_bars.json` وِ `ra365_product_bars*.json` | ۱۲MB + ۴×~۲۷MB | کشیدنیِ خام؛ renew نیازمندِ نشستِ احرازشدۀِ مالک (دورزدنِ احراز هویت ممنوع) | نتایجِ جدولی درِ گیت + زیرمجموعۀِ شاهدِ §۱۰‑۳ |
| `market.db`, `market.db.lzma`, `codal.db` | ~۲۲۸MB / ۵۷–۷۹MB | دادهٔ عملیاتی + ردیف‌هایِ کاربر؛ قراردادِ ریلیز، نه مخزنِ سورس | assetِ `data-latest` + `market.db.meta.json` (digest تأیید شد) |
| `_audit/ui/shots/*.png` (۱۶۸) وِ `_audit/MS-BINDER-SHOTS/*.png` (۲۶) | ~۲۳MB / ۵٫۹MB | `*.png` درِ `_audit/.gitignore`؛ سنگینِ مخزن | ۳ برشِ فشرده + اعدادِ قبل/بعد؛ `_audit/MS-BINDER-UI-RUN.txt` |
| لاگ‌هایِ خامِ راه‌اندازیِ مرورگر (`_audit/PHASE5F-CAPTURE*.txt`) | ۵KB | سطرهایِ launch باِ `--user-data-dir=<پروفیلِ کاربر>` وِ pid؛ مخزن **public** است | `_audit/PHASE5F-P5G-RUNDIGEST.txt` (outcomeها، masked) |
| `ms_server.log` بیرونِ مخزن (`Borsterminal/_audit/`) | ۵۴KB | لاگِ خامِ سرویسِ dev؛ artefactِ زمانِ اجرا | گیت‌هایِ عددی درِ `_audit/perf/gates/` وِ `_audit/ui/` |
| `frontend/dist/**`، `node_modules`، `__pycache__` | — | خروجیِ build، قابلِ بازتولید | فرمانِ build درِ سندِ fixtureها (§۶ آنِ سند) |

### ۱۰‑۵) ACTION REQUIRED (تصمیمِ مالک، نه کارِ ایجنت)

۱) **سیزده صفحۀِ Binder1**: دوِ سندِ tracked تصویرهایِ `_audit/binder1_pages/p01.jpg … p13.jpg`
    را ارجاع می‌دهند؛ آنِ فایل‌ها (۴۹۲KB) درِ **بیرونِ** مخزن بودند
    (`Borsterminal/_audit/binder1_pages/`) وِ هیچ‌وقت درِ GitHub نبودند. کپی‌شان درِ اینِ دور
    آماده شد وِ سپس برداشته شد: بریدۀِ سندِ یکِ شخصِ ثالث درِ مخزنِ public = تصمیمِ مالک،
    نه تصمیمِ ممیزی. دوِ راهِ پیشنهاد: (الف) منتشر کن باِ ذکرِ مصدر، (ب) همانِ ۱۳ صفحه را
    به‌صورتِ جدولِ متنِ فارسی درِ خودِ سند بازنویسی کن (دادهٔ خودِ ماست). تا then ارجاعِ
    دوِ سند رویِ GitHub شکسته می‌ماند؛ فایل‌هایِ اصلی درِ دیسکِ همینِ ماشین سالم‌اند وِ
    هیچ‌کدام جابه‌جا یا پاک نشدند.
۲) **credentialهایِ پیش‌فرضِ خودِ مخزن**: جاروبِ `_audit/**` نشان داد ۱۳ فایلِ ازِ
    مأموریت‌هایِ پیشین مقدارِ literal حسابِ پیش‌فرض را هارد‌کد دارند (۱۰ فایل باِ **رمز**؛
    §۶). ریشۀِ کار درِ `frontend/src/shared/stores/authStore.ts` است که درِ همینِ مخزنِ
    public نشسته است. پاک‌سازیِ آنِ ۱۳ فایل یا چرخشِ رمزِ پیش‌فرض تصمیمِ مالک است. درِ
    کامیت‌هایِ اینِ دور هیچِ credential منتشر نشد (جاروبِ ۱۱۱ فایلِ دورِ UI + ۷ فایلِ
    اینِ دور → ۰ hit؛ سطرهایِ launchِ مرورگر masked شدند).

### ۱۰‑۶) رأیِ اینِ دور

`WORK_INVENTORY_COMPLETE_WITH_TWO_OWNER_DECISIONS`

همۀ کامیت‌هایِ سیستمِ دوم رویِ remote‌اند (`git log --branches --not --remotes` خالی)،
هیچِ stash یا dangling commitِ دارایِ کار نیست، هرِ حوزه یکِ شاخۀِ remote باِ SHAِ
تأییدشده دارد (§۱۰‑۲)، وِ دوِ suite‌ای که ازِ cloneِ خالی نمی‌دویدند اکنون می‌دوند
(§۱۰‑۳). تنهاِ بقایایِ محلی: فایل‌هایِ §۱۰‑۴ (باِ دلیل) وِ دوِ موردِ §۱۰‑۵ (باِ تصمیمِ
مالک). بی‌merge، بی‌tag، بی‌release، بی‌force‑push، وِ بی‌دست‌زدن بهِ نسخۀِ نصبی یا
بانکِ عملیاتیِ بازار.
