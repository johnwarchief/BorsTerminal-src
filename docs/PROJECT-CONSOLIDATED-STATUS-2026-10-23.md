# وضعیت تجمیعی پروژه — 2026-10-23

> **این سند audit است، نه تغییر محصول.** هیچ branchی merge نشد، هیچ commitای به `main` push نشد، هیچ دیتابیسی نوشته نشد و هیچ تغییری در منطق تولید اعمال نشد.

## ۰) فرادادهٔ audit

| مورد | مقدار |
|---|---|
| زمان audit | 2026-10-23، 15:40 به وقت تهران (12:10 UTC) |
| مرجع حقیقت | `github` = `https://github.com/johnwarchief/BorsTerminal-src.git` |
| remote `origin` | `C:/Users/PCMOD/.cline/data/workspaces/chat/BorsTerminal` — mirror محلی، نه GitHub؛ برای تعیین وضعیت استفاده نشد |
| `github/main` تأییدشده | `d580306b72a7e0ae077cd2973643b6b0b136e5b0` — 2026-10-22T23:55:37Z — «docs(perf): record the standalone confidence-engine pass» |
| روش تأیید main | GitHub API (`branches/main`)، tarball با پیشوند `johnwarchief-BorsTerminal-src-d580306`، و API مقایسه |
| branch فعال | `mission/4-axes-2026-10-10`، HEAD `d56dcb18` |

### وضعیت working tree (دست‌نخورده)

| مورد | تعداد | توضیح |
|---|---:|---|
| فایل‌های tracked تغییریافته | 2 | `_audit/FTS_TREND_COMPARE.csv` (mtime 2026-10-10) و `tools/market_state_probe.mts` (mtime 2026-10-12)؛ متعلق به کارهای قبلی، پاک/بازنشانی نشدند |
| فایل‌های untracked | 329 | 315 در `_audit/`، 9 در `docs/`، 4 در `tools/`، 1 در `Python/` |
| commitهای محلیِ unpushed | 2 | `d94d04f9` و `d56dcb18` روی branch فعال؛ upstream آن‌ها `e9db359e` است |
| فاصلهٔ branch فعال از main | 2 جلو / 297 عقب | branch فعال یک branch قدیمی است، نه main |

### محدودهٔ دسترسی و محدودیت‌ها

- GitHub API برای branchها، PRها، releaseها، CI و مقایسه‌ها در دسترس بود؛ 9 PR و 86 branch remote خوانده شد.
- `git fetch` روی HTTPS به‌صورت متناوب با خطای اتصال/`invalid index-pack output` شکست خورد؛ برای همین snapshot کامل `main@d580306b` و `branch@ca3161df` از tarball رسمی گرفته شد. بر این اساس، بررسی محتوای main روی snapshot انجام شده، نه روی working tree.
- GitHub API در چند تلاش اول ناپایدار بود؛ همهٔ اعداد مهم با فراخوانی موفق یا log CI تأیید شدند.
- هیچ دیتابیس عملیاتی در این audit نوشته، مهاجرت یا backfill نشد. فقط hash خوانده شد.
- اسناد تاریخی (`PLAN-remaining.md`، `HANDOFF-FTS-TAB-OPEN-WORK.md`، roadmap) به‌عنوان وضعیت جاری تلقی نشدند؛ `docs/README.md` خودش تصریح می‌کند این‌ها snapshot تاریخ‌دارند.

---

## ۱) خلاصهٔ مدیریتی

1. **main از نظر قابلیت جلو رفته، اما از نظر انتشار عقب است.** main در 21 کامیت اخیر، مأموریت Performance (Coder3) را merge کرده و 36 کامیت جلوتر از tag منتشرشدهٔ `v1.0.95` است؛ با این حال `APP_VERSION` هنوز `1.0.95` است. یعنی **دو کد مختلف با یک شمارهٔ نسخه** وجود دارد: نصاب منتشرشدهٔ 1.0.95 و main فعلی.
2. **CI روی main قرمز است.** آخرین اجرای `guards` در `d580306b` شکست خورده: 133 سوئیت شمارش شد، 17 سوئیت FAIL، 4 فایل PNG در گیت هستند که `.gitignore` آن‌ها را ignore می‌کند، و چند سوئیت به‌خاطر نبود `market.db` در CI نمی‌توانند اجرا شوند. همین وضعیت روی tag `v1.0.95` هم قرمز بود.
3. **اصلاح واقعی Raw H/L در main نیست.** کامیت `376d03de` («preserve raw HIGH/LOW across live candle paths») روی branch راهاورد است و main فقط یک ارجاع `high_raw` در `api/chart.py` دارد (branch سه ارجاع دارد) و `candle_contract.py` در main اصلاً `high_raw` ندارد. این یک باگ دادهٔ واقعی است که فقط روی branch رفع شده.
4. **Sarkhati در main فقط پایه است.** main ماژول‌های پایهٔ execution و UI سرخطی را دارد، اما 19 ماژول تازه (Mofid، browser host، scheduler، fast order، readiness، telemetry و…) و گسترش `api/execution.py` از 1432 به 3760 خط فقط روی branch راند ۲۱ است. سفارش واقعی هنوز ثبت نشده و `live_ready=false` است.
5. **دو blocker بیرونی، نه کمبود کد:** (الف) نشست/تأیید مالک برای سفارش واقعی کارگزاری؛ (ب) `timescale_marks` و قیمت پذیره (`S`) مرجع رهاورد برای parity کامل type7.
6. **سه اولویت بعدی:** اصلاح drift نسخه/انتشار + سبزکردن CI؛ merge اصلاح Raw H/L با طراحی schema محلی؛ تصمیم و merge/rebase راندهای Sarkhati و سپس آزمون کنترل‌شدهٔ مالک.

---

## ۲) main و آخرین commit تأییدشده

| مورد | مقدار | شاهد |
|---|---|---|
| `github/main` | `d580306b` (2026-10-22T23:55:37Z) | GitHub API `branches/main` |
| tag منتشرشدهٔ آخر | `v1.0.95` = `a14375c1` (2026-10-19T19:30Z) | `repos/.../tags` و release `v1.0.95` |
| فاصلهٔ main از tag | **36 کامیت جلو، 217 فایل تغییر** | `compare/a14375c1...d580306b` |
| `APP_VERSION` در main | `1.0.95` | `bors_config.py:865` |
| لنگرهای نسخه | هر شش لنگر `1.0.95` | `bors_config.APP_VERSION`، `frontend/package.json`، دو فیلد `package-lock.json`، `tauri.conf.json`، `installer/bors_setup.iss` |
| آخرین release | `BorsTerminal Ultimate v1.0.95`، Published 2026-10-19T19:36:51Z | GitHub Releases |
| CI روی main | **failure** (`guards`) در `d580306b` | run `39874944161` |
| CI روی tag `v1.0.95` | **failure** در `a14375c1` | run `39311565415` |

**نتیجه:** نسخهٔ منبع و نصاب منتشرشده هم‌شماره‌اند ولی هم‌محتوا نیستند. `dev/version_anchor_guard.py` فقط برابری شش لنگر را می‌سنجد، نه برابری main با tag/release را؛ بنابراین این drift را نمی‌گیرد.

---

## ۳) قابلیت‌های mergeشده و شواهد موجود

در سطح «قابلیت کامل» به‌سختی می‌توان موردی را `MERGED_AND_VERIFIED` نامید، چون CI نهایی قرمز است و suite کامل پس از آخرین اصلاحات اجرا نشده. اما این واحدهای مشخص، در main هستند و شاهد سبزِ مستقل دارند:

| کار | شاهد در main | اعتبارسنجی |
|---|---|---|
| PR #2 — source-of-truth cleanup | merge commit `da2d8c58` | merge تأیید شد؛ حضور `docs/README.md` و `docs/AGENT-INDEX.md` در main |
| PR #3 — roadmap priority clarity | merge commit `e208d028` | merge تأیید شد؛ سند roadmap و `OWNER_RULINGS.md` در main |
| PR #4 — FTS hourglass user settings | merge commit `f96ce3d3` | merge تأیید شد؛ گارد FTS در CI سبز (مثلاً `FTS filter isolation` 23/23) |
| PR #5 — hourglass cache key | merge commit `24320a92` | merge تأیید شد؛ گارد مرتبط در main؛ جزئیات DB-dependent |
| PR #6 — desktop review build | merge commit `dc99210b` | merge تأیید شد؛ اعتبارسنجی مجدد در این audit انجام نشد |
| PR #7 — speed roadmap | merge commit `cc758f11` | merge تأیید شد؛ سند roadmap در main |
| PR #8 — System 2 chart parity + major swing | merge commit `07a3576c` | merge تأیید شد؛ فایل‌های chart/technical و آزمون‌های Vitest در main |
| PR #9 — System 2 technical workspace UX | merge commit `a87575a1` | merge تأیید شد؛ `docs/CHART-FOUR-PAGES-PARITY.md` و `docs/CHART-PARITY-REFERENCE.md` در main |
| اصلاح اثر شاخص رسمی TSETMC | `ef92c89c` | گارد CI: «official TSETMC index impact; derived fallback is explicitly labelled» → **12/12 PASS** |
| مأموریت تکنیکال FTS (کد/تست) | `3527929` ancestor of main | 8 گیت اجراشده در سند `FTS-MISSION-CLOSURE-1405-07-20.md`؛ با این حال موارد باز در §۴ |
| Strategy Tree پنج‌صفحه | `b8bea222` ancestor of main | branch در main merge شده؛ سند/شواهد در main |
| Nav audit و Market tab cleanup | `85e4008c`، `36519a22` ancestor of main | branchها ancestor شده‌اند؛ شواهد زندهٔ گزارش‌شده در main |

اعتبارسنجی‌های سبزِ مستقل در آخرین CI main (حتی با قرمز بودن کل job):

- `FTS filter isolation` 23/23
- `codal FTS pipeline + ADB fallback + session window` 53/53
- `calendar py<->js categories` 24/24
- `m141/liquidity parity + anti-N+1` 21/21
- `ADB retry/reconnect + wifi restore` 26/26
- `triple-confirmation confidence engine` 39/39
- `mstat dashboard computed from local market.db` 187/187
- `official TSETMC index impact` 12/12
- `market LAST` 11/11
- `sarkhati: durable audit trail, kill switch, fail-closed risk, wired HTTP door` 48/48
- `easytrader adapter: injected transport, 2xx-is-not-acceptance, no blind resend` 162/162

این‌ها ثابت می‌کنند آن گاردها کار می‌کنند، ولی **ثابت نمی‌کنند کل main سالم است**؛ 17 سوئیت در همان اجرا FAIL شدند.

---

## ۴) قابلیت‌های موجود در main که هنوز کاملاً تأیید نشده‌اند

| کار | وضعیت | چرا کامل نیست |
|---|---|---|
| Performance Phase 1 + Phase 2 (Coder3) | `MERGED_NOT_FULLY_VERIFIED` | 21 کامیت به main fast-forward شد؛ چهار regression توسط `558f8daa` رفع شد و آزمون‌های هدفمند سبزند. اما **suite کامل Python پس از اصلاح دوباره اجرا نشد**؛ تلاش کامل قبل از اصلاح: **163 OK / 15 FAIL / 1 skipped**؛ Vitest کامل در **16/201** فایل متوقف شد. |
| FTS funnel و موتورهای تحلیل | `MERGED_NOT_FULLY_VERIFIED` | کد و گاردها در main‌اند، اما CI قرمز است و چند سوئیت DB-dependent در CI اجرا نمی‌شوند؛ suite کامل محلی نیز پس از آخرین تغییرات اجرا نشده. |
| مأموریت تکنیکال FTS | `MERGED_NOT_FULLY_VERIFIED` | 8 معیار بسته شد، اما: تطبیق دیدنی لایه‌ها با رهاورد در نشست مالک **باز**؛ موتور سوم هیچ مرجع بیرونی ندارد؛ 6 ردیف کاتالوگ سوییچ مستقل ندارند؛ چگالی بصری سنجیده نشده؛ فرمول اندیکاتورهای شخص ثالث با TradingView مقایسه نشده. |
| تب «وضعیت بازار» / TSETMC | `MERGED_NOT_FULLY_VERIFIED` | فیلدهای اصلی same-tick **100%** (11 فیلد، 3093 ردیف، صفر اختلاف)، اما حکم نهایی سند `BLOCKED` است: 6 مورد باز، از جمله ارزش native حقیقی/حقوقی (HTTP 500)، عمق جاری، universe 22 ابزار مشتقه، و وضعیت رسمی در UI. |
| UI / Strategy Tree / Market tab | `MERGED_NOT_FULLY_VERIFIED` | branchها در main هستند؛ اما verdict دیداری مالک در repo ثبت نشده و CI قرمز است. |
| Sarkhati پایه در main | `MERGED_NOT_FULLY_VERIFIED` | UI و execution پایه در main هست (تا حدود 2026-10-19)، اما `p0 gates` در CI **29/33** و `sarkhati protocol` **0/3** بود؛ نشست واقعی کارگزاری هم وجود ندارد. |
| Release v1.0.95 | `MERGED_NOT_FULLY_VERIFIED` | نصاب/Portable/پچ‌ها/`codal.db.lzma`+sig منتشر شده‌اند، اما CI همان tag قرمز بود و 36 کامیت بعدی با همان شمارهٔ نسخه در main نشسته‌اند. |

---

## ۵) کارهای تکمیل‌شده اما mergeنشده

| کار | Branch / commit | فاصله از main فعلی | اعتبارسنجی | وضعیت |
|---|---|---|---|---|
| اصلاح Raw H/L و parity رهاورد | `mission/ra365-round20-real-fixes-2026-10-23` — `376d03de` (کد) + `ca3161df` (گزارش) | **71 جلو / 21 عقب** (300 فایل) | تست‌های هدفمند 37/37، 22/22، 45/45، 9/9، 32/32؛ Full gate `VERIFIED` با 147 سوئیت؛ DB بدون تغییر | `IMPLEMENTED_UNMERGED` |
| Sarkhati راندهای ۷ تا ۲۱ | `mission/sarkhati-round21-easytrader-live-test-2026-10-22` — `74014ab5`، `585cb1f7`، `cadc54c7` | **56 جلو / 36 عقب** (234 فایل) | 146 سوئیت ALL PASSED، Vitest 202 فایل/2102 تست، tsc/build PASS، frozen smoke PASS؛ **هیچ سفارش واقعی ثبت نشد** | `IMPLEMENTED_UNMERGED` |
| نصاب آزمایشی 1.0.96 | همان branch؛ `BorsTerminal_Ultimate_Setup_v1.0.96.exe` | — | SHA-256 `0a8dbb45…`، 66,587,124 بایت؛ منتشر نشده؛ آزمون update از 1.0.95 انجام نشده | `IMPLEMENTED_UNMERGED` |
| Android 1.1.3 | `mission/android-live-market-fts-audit` / `mission/android-system2-fts-parity` — `7a79bdc3` | **99 جلو / 287 عقب** (نسبت به main فعلی) | APK 1.1.3 (21.3MB) به‌صورت Pre-release منتشر شده؛ main هیچ پوشهٔ `android/` ندارد؛ زنجیرهٔ امضا بررسی نشد | `IMPLEMENTED_UNMERGED` + بخش امضا `UNVERIFIED` |
| UIUX 2.0 | `mission/uiux-2-0-redesign-2026-10-16` — `a3984f02` | 15 جلو / 338 عقب | 202 فایل تغییر؛ بخشی ممکن است با PRهای #8/#9 جایگزین شده باشد؛ هم‌پوشانی محتوایی کامل بررسی نشد | `IMPLEMENTED_UNMERGED` / هم‌پوشانی `UNVERIFIED` |
| UI audit System 1 | `mission/ui-audit-system-1-2026-10-15` — `2efe4d27` | 1 جلو | سند + اسکرین‌شات‌ها + تغییر 4 فایل UI؛ در main نیست | `IMPLEMENTED_UNMERGED` |
| راندهای محلی Sarkhati 14/15/15.5 | `mission/sarkhati-round14…`، `round15…`، `round15-5…` | 33–37 جلو | **upstream ندارند** (local-only)؛ توسط راندهای 16+ احتمالاً جایگزین شده‌اند | `IMPLEMENTED_UNMERGED` + وضعیت superseded بودن `UNVERIFIED` |

**دربارهٔ branchهای قدیمی‌تر:** از 74 ref remote که در clone محلی موجود بود، 42 ref ancestor مستقیم main نیستند (لیست API در مجموع 86 branch دارد). اما همهٔ آن‌ها unmerged نیستند: PRهای #3/#4/#5 با squash merge وارد main شده‌اند و ancestry مستقیم ندارند؛ branchهای `strategy-tree`، `uiux-nav-audit`، `market-tab-cleanup` و `windows-stable-release` کاملاً ancestor هستند. برای هر ادعای merge، PR/commit/content بررسی شد، نه فقط SHA.

---

## ۶) کارهای ناقص، blockerها و موارد نیازمند تصمیم

### Rahavard

| مورد | وضعیت | شاهد / blocker |
|---|---|---|
| Raw H/L خام در parser و candle | رفع‌شده فقط روی branch | `376d03de`؛ main: `api/chart.py` فقط 1 ارجاع `high_raw`، `candle_contract.py` صفر ارجاع |
| Raw literal parity | 99.8104% ردیف پس از رفع (از 87.3421%) | 2260 ردیف / 3634 فیلد residual، همه سمت منبع/CSV یخ‌زده؛ 266 ردیف 2023-03-27 در parser کندل نمی‌شوند |
| type7 / performance-adjusted | 22.81% در تلورانس (fixture 29 نمادی)؛ factor exact 69.02%؛ OHLC 68.30% | `BLOCKED_REFERENCE_MARKS` و `BLOCKED_REFERENCE_EVENT_INPUT`: نبود `S` پذیره و event-set مرجع؛ هیچ فرمول production تغییر نکرد |
| Weekly volume | VERIFIED برای تعریف حجم: جمع 3970/3995 هفته | فقط روی branch اندازه‌گیری شده؛ ماهانه `NOT_MEASURED` چون fixture مرجع M ندارد |
| Local DB raw | `BLOCKED_LOCALDB_RAW_SCHEMA` | `price_history` ستون `high_raw/low_raw` ندارد؛ مهاجرت/backfill انجام نشده |
| تطبیق دیدنی لایه‌ها | باز | نیازمند نشست احراز هویت‌شدهٔ مالک؛ بخشی از مأموریت تکنیکال |

### Sarkhati

| مورد | وضعیت | شاهد / blocker |
|---|---|---|
| نشست کارگزاری | `NO_SESSION` / `LOGIN_REQUIRED` در راند ۲۰ | ورود دستی مالک لازم است؛ هیچ رازی ذخیره نشده |
| سفارش واقعی | صفر سفارش ثبت‌شده | Round 21: «هیچ سفارش واقعی ثبت نشد»؛ قرارداد نوشتن `WRITE_CONTRACT_STATICALLY_RECONSTRUCTED` و `operationally_verified=false` |
| جایگاه صف | `source_verified=false`، `queue_result_known=false` | Mofid: POST/WS فقط‌خواندنی هرگز فراخوانی نشد؛ EasyTrader: فقط mock؛ `volumeAhead` بدون واحد |
| `live_ready` | `false` | تا تأیید قرارداد عملیاتی و مجوز مالک سبز نمی‌شود |
| نوع بازار/صف | تفکیک‌شده | نوع بازار عادی و عرضهٔ اولیه یکی گرفته نمی‌شود؛ صفر «رتبهٔ اول» نیست |

### FTS / تکنیکال

- **تصمیم‌های باز مالک:** گیت رسم پولبک (ب-۹)؛ `majorResistance/Support` (ب-۵)؛ `/api/patterns` (ب-۴)؛ یکپارچه‌سازی تکرار ریاضی اندیکاتورها (ب-۶)؛ مسیر `hybrid` trend (ب-۷)؛ `JET_MARKER_OVERLAY` بدون تولیدکننده (B8).
- **سنجیده‌نشده:** تطبیق دیدنی لایه‌ها با رهاورد؛ 6 ردیف کاتالوگ بدون سوییچ مستقل؛ تفکیک دیدنی `(W)` از `(D)`؛ چگالی بصری؛ فرمول اندیکاتورهای شخص ثالث؛ divergence RSI.
- **شمارندهٔ تست:** `run_all_tests.py` برای 46 از 114 سطر «0/0» چاپ می‌کند در حالی که اجرا شده‌اند؛ این سال‌ها «سبزِ خاموش» ساخته است.

### زیرساخت

| مورد | وضعیت | شاهد |
|---|---|---|
| CI guards | قرمز | 17 سوئیت FAIL؛ غالباً `no such table`/`unable to open database file` به‌خاطر نبود DB در CI؛ 4 PNG tracked-ignored؛ `chart API guard` 10/18 (احتمالاً node_modules در CI) |
| Release drift | بحرانی | main 36 کامیت جلوتر از tag `v1.0.95` با همان `APP_VERSION` |
| Protected DB parity | `UNVERIFIED` | SHA محلی `market.db` = `7fbd9a49…` در حالی که گزارش branch عملیاتی را `7b933b05…` و promoted را `8fb85f38…` ثبت کرده؛ این دو به یک کپی اشاره نمی‌کنند |
| Working tree | نیازمند پاک‌سازی | 329 untracked + 2 modified؛ 2 commit محلی unpushed روی branch فعال |

---

## ۷) ماتریس جامع حوزه‌ها

| حوزه | کار/قابلیت | وضعیت | شواهد در main | Branch/PR و commit | تست یا اعتبارسنجی | باقی‌مانده/Blocker |
|---|---|---|---|---|---|---|
| Rahavard | حفظ Raw H/L در parser/candle | `IMPLEMENTED_UNMERGED` | main فقط 1 `high_raw` در `api/chart.py`؛ `candle_contract.py` صفر | `mission/ra365-round20-real-fixes…` — `376d03de` | 37/37 + 22/22 + 45/45 + 9/9 + 32/32 | merge + schema محلی |
| Rahavard | Raw literal parity | `PARTIALLY_IMPLEMENTED` | — | همان؛ `ca3161df` | 99.8104% ردیف؛ residual 0.1896% | 2260 ردیف سمت منبع؛ 266 ردیف session anomaly |
| Rahavard | type7 / adjusted parity | `BLOCKED` | `adjustment_engine.py` و `price_basis.py` موجود، `price_basis` بدون تغییر | branch گزارش Round 20 | 22.81% در تلورانس؛ factor 69.02%؛ OHLC 68.30% | marks کامل 2595 دارایی + S پذیره |
| Rahavard | Weekly volume rule | `INVESTIGATED_ONLY` | رفتار product از قبل «جمع» است | گزارش branch | 3970/3995 هفته با جمع | فقط سند/اندازه‌گیری؛ ماهانه NOT_MEASURED |
| Rahavard | Local DB raw schema | `BLOCKED` | `price_history` بدون `high_raw/low_raw` | گزارش branch | — | مهاجرت + backfill |
| TSETMC/بازار | same-tick parity فیلدهای اصلی | `MERGED_NOT_FULLY_VERIFIED` | `api/market.py`، `market_status.py`، docs 2026-10-20 | `ef92c89c`، `b4d83e0f` | 3093 ردیف × 11 فیلد = 100%؛ صفر اختلاف | حکم کلی BLOCKED؛ 6 مورد باز |
| TSETMC/بازار | اثر شاخص رسمی | `MERGED_AND_VERIFIED` | `api/market_index.py` | `ef92c89c` | گارد CI 12/12 | — |
| TSETMC/بازار | بستن 100% وضعیت بازار | `BLOCKED` | گزارش closure در main | — | 65/74 ردیف = 87.8% | ارزش native (HTTP 500)، عمق جاری، universe مشتقه، وضعیت رسمی UI |
| FTS | قیف، موتور، غربالگری | `MERGED_NOT_FULLY_VERIFIED` | `api/funnel.py`، `fts_engine.py`، `funnel_engine`، UI | چند PR/merge مستقیم | گاردهای متعدد سبز؛ CI نهایی قرمز؛ full suite ناتمام | اجرای کامل suite + رفع CI |
| FTS/تکنیکال | مأموریت تکنیکال | `MERGED_NOT_FULLY_VERIFIED` | `3527929` ancestor؛ docs closure | — | 8 معیار؛ 16/22 لایه سنجیده | تطبیق دیدنی رهاورد؛ موتور سوم بی‌مرجع؛ 6 ردیف بی‌سوییچ |
| FTS | parity زندهٔ فیلترها در ساعت بازار | `BLOCKED` | ابزارها در `tools/` | — | 732 حالت تفاضلی سبز | یک پاس زنده در 09:00–12:30 لازم است |
| UI/چارت | Strategy Tree، nav، market tab | `MERGED_NOT_FULLY_VERIFIED` | branchها ancestor؛ فایل‌ها در main | `b8bea222`، `85e4008c`، `36519a22` | شواهد گزارش‌شده در main | رأی دیداری مالک + CI سبز |
| Performance | Phase 1/2 بهینه‌سازی‌ها | `MERGED_NOT_FULLY_VERIFIED` | 21 کامیت، `artifacts/performance/…`، 7 سند | `2d4db99e`…`d580306b` | targeted green؛ full attempt 163/15/1؛ Vitest 16/201 | suite کامل پس از `558f8daa` |
| Performance | مسیرهای protected | `BLOCKED` | handoff در main | — | `/api/fts` first call 25–41s؛ صفحهٔ تکنیکال 1.22MB `/api/market` | تعلق به Coder2/مالک |
| Sarkhati | پایهٔ execution/UI در main | `MERGED_NOT_FULLY_VERIFIED` | `api/execution.py` 1432 خط، 9 ماژول، UI سرخطی | تا 2026-10-19 | p0 gates 29/33؛ protocol 0/3 در CI | نشست/سفارش واقعی |
| Sarkhati | راندهای ۷–۲۱ | `IMPLEMENTED_UNMERGED` | main فاقد 19 ماژول؛ API 3760 خط | `mission/sarkhati-round21…` — `74014ab5` | 146 سوئیت ALL PASSED؛ Vitest 2102؛ frozen smoke | rebase روی main + merge |
| Sarkhati | ارسال/صف زنده | `BLOCKED` | `live_ready=false` | — | صفر سفارش واقعی؛ `source_verified=false` | ورود مالک + تأیید + سفارش حداقلی |
| Sarkhati | نصاب 1.0.96 | `IMPLEMENTED_UNMERGED` | main روی 1.0.95 | `585cb1f7` | SHA `0a8dbb45…`؛ منتشرنشده | آزمون update و نصب مالک |
| Android | منبع/APK 1.1.3 | `IMPLEMENTED_UNMERGED` / امضا `UNVERIFIED` | main بدون `android/` | `7a79bdc3` | APK 21.3MB منتشرشده | منبع در main/repo جدا؛ زنجیرهٔ امضا |
| UI | UIUX 2.0 و UI audit | `IMPLEMENTED_UNMERGED` | main نسخه‌های جدیدتر دارد | `a3984f02`، `2efe4d27` | اسکرین‌شات/تست‌های branch | تصمیم merge/archive؛ هم‌پوشانی UNVERIFIED |
| انتشار | نسخه و artifact | `MERGED_NOT_FULLY_VERIFIED` | main=`1.0.95`، tag=`a14375c1` | — | release v1.0.95 با 13 asset | drift 36 کامیت؛ CI قرمز |
| تست | suite کامل در HEAD | `UNVERIFIED` | CI 133 سوئیت؛ 201 فایل Vitest | — | 163/15/1 (قبل از fix)؛ Vitest 16/201 | اجرای کامل پس از `558f8daa` |
| دیتابیس | parity عملیاتی/promoted | `UNVERIFIED` | SHAهای گزارش branch | — | محلی `7fbd9a49…` ≠ گزارش `7b933b05…` | تعیین کپی مرجع؛ بدون نوشتن |
| Git hygiene | working tree و branchهای محلی | `NOT_STARTED` | 329 untracked + 2 modified | — | 2 commit unpushed | طبقه‌بندی/commit/ignore |

---

## ۸) Backlog اولویت‌بندی‌شده و معیار پذیرش

### P0 — ریسک صحت داده، ارسال سفارش، یکپارچگی یا امنیت

| # | مسئله | مدرک باز بودن | پیش‌نیاز | معیار عینی تکمیل |
|---|---|---|---|---|
| P0-1 | **Drift نسخه/انتشار:** main 36 کامیت جلوتر از tag `v1.0.95` با همان `APP_VERSION` | `compare/a14375c1...d580306b` = 36 جلو / 217 فایل؛ `bors_config.py:865` | تصمیم مالک: bump یا retag | شش لنگر به نسخهٔ جدید؛ tag روی main؛ نصاب/پچ/`latest.json` از همان commit؛ `version_anchor_guard` سبز |
| P0-2 | **CI قرمز روی main** | run `39874944161` failure؛ 17 سوئیت FAIL؛ 4 PNG tracked-ignored | fixture DB در CI یا skip صریح DB-dependentها؛ حذف/استثنای PNGها؛ تأمین node_modules برای chart guard | `guards` روی main سبز؛ هیچ خطای `no such table`؛ `git ls-files -i -c --exclude-standard` خالی |
| P0-3 | **اصلاح Raw H/L در main نیست** | `api/chart.py` 1 vs 3 `high_raw`؛ `candle_contract.py` 0 | merge `376d03de` + گزارش؛ طراحی schema محلی | merge + تست‌های 37/37 و 22/22؛ مهاجرت `high_raw/low_raw` یا fallback مستند؛ تکرار سنجش 99.81% |
| P0-4 | **Sarkhati: ارسال واقعی تأییدنشده** | `live_ready=false`؛ صفر سفارش؛ قرارداد `operationally_verified=false` | ورود دستی مالک + مجوز صریح + سفارش حداقلی | یک سفارش کنترل‌شده با شناسهٔ کارگزاری، نتیجهٔ read-back و تأیید قرارداد؛ بدون retry کور |

### P1 — قابلیت مهم برای هدف محصول

| # | مسئله | مدرک | معیار پذیرش |
|---|---|---|---|
| P1-1 | merge/rebase راندهای Sarkhati 7–21 | 56 جلو / 36 عقب؛ 19 ماژول؛ API 3760 خط | rebase بدون حذف کار Performance؛ 146 سوئیت و Vitest کامل سبز؛ frozen build تازه |
| P1-2 | اجرای کامل suite پس از اصلاحات Performance | full attempt 163/15/1؛ Vitest 16/201 | اجرای کامل Python + Vitest در HEAD؛ ثبت pre-existing failures |
| P1-3 | مسیرهای protected پرهزینه | `/api/fts` first call 25–41s؛ 1.22MB `/api/market` در صفحهٔ تکنیکال | first-call <1s یا قرارداد progress؛ جایگزینی full feed با `/api/market/row`؛ سنجش قبل/بعد |
| P1-4 | بستن 6 مورد باز وضعیت بازار | حکم `BLOCKED`؛ 65/74 = 87.8% | هر مورد یا شاهد/تصمیم دارد یا صریحاً پذیرفته می‌شود؛ verdict نهایی با مخرج ثابت |
| P1-5 | تأمین marks و S مرجع رهاورد | `BLOCKED_REFERENCE_MARKS`؛ 22.81% در تلورانس | دسترسی/export marks؛ اجرای cohort 2595؛ هیچ فرمول بدون شاهد تغییر نکند |
| P1-6 | parity زندهٔ فیلترهای FTS | فقط 732 حالت تفاضلی؛ پاس زنده ندارد | یک اجرای زنده در ساعت بازار با شاهد زمان‌دار و مقایسهٔ same-tick |
| P1-7 | پاک‌سازی working tree | 329 untracked + 2 modified؛ 2 commit unpushed | هیچ untracked بی‌دلیل نماند؛ docs ارزشمند commit؛ آرتیفکت‌ها ignore؛ 2 فایل tracked حفظ |

### P2 — کیفیت، پوشش، قابلیت اطمینان

| # | مسئله | معیار پذیرش |
|---|---|---|
| P2-1 | Android: منبع و امضا | منبع در repo مشخص یا repo جدا مستند؛ زنجیرهٔ امضا/گواهی تأیید؛ APK قابل بازتولید |
| P2-2 | UIUX 2.0 / UI audit | تصمیم merge یا archive برای هر branch؛ هیچ شاهد دیداری tracked-ignored نماند |
| P2-3 | تصمیم‌های باز تکنیکال (ب-۹، ب-۵، ب-۴، ب-۶، ب-۷، B8) | هر مورد یک رأی مکتوب + گارد/تست متناظر |
| P2-4 | شمارندهٔ `run_all_tests` | 46 سطر «0/0» شناسایی و شمارش واقعی/برچسب «silent» صریح شود |

### P3 — بهبود اختیاری یا تصمیم آتی

| # | مسئله | معیار پذیرش |
|---|---|---|
| P3-1 | aggregations ماهانه | fixture مرجع M؛ سنجش و سند |
| P3-2 | overlay toggles / چگالی بصری | سنجش زنده و شاهد پیکسلی |
| P3-3 | اسناد تاریخی | برچسب snapshot/archived؛ حذف ادعاهای کهنه از مسیر ناوبری |

**آیا تست کافی است یا محیط واقعی لازم دارد؟** P0-1/P0-2/P1-2/P1-7 با کد و CI قابل بستن‌اند. P0-3 با تست + تکرار سنجش داده بسته می‌شود، اما schema محلی به مهاجرت و آزمون روی کپی DB نیاز دارد. P0-4 و P1-6 فقط با محیط واقعی (نشست کارگزاری/بازار باز) بسته می‌شوند. P1-5 ورودی بیرونی (marks/S) می‌خواهد و تست داخلی جای آن را نمی‌گیرد. P1-3/P1-4 با سنجش قبل/بعد و snapshot هم‌زمان بسته می‌شوند.

**کار تکراری در branch دیگر:** برای Raw H/L، Rahavard تمام کار در یک branch واحد است و تکرار شناسایی نشد. برای Sarkhati، branchهای 14/15/15.5 نسخه‌های local-only و قدیمی‌تر همان مسیرند و باید archive شوند، نه دوباره اجرا. برای UIUX 2.0 و UI audit، هم‌پوشانی با PRهای #8/#9 محتمل است اما تأیید نشده (`UNVERIFIED`)؛ پیش از merge باید diff محتوایی گرفته شود.

---

## ۹) وضعیت تست‌ها، release و دیتابیس‌های محافظت‌شده

### تست‌ها

| سطح | وضعیت | شاهد |
|---|---|---|
| CI `guards` روی main | **FAIL** | run `39874944161`؛ 133 سوئیت شمارش، 44 silent، 2 skip؛ 17 FAIL |
| CI روی tag `v1.0.95` | **FAIL** | run `39311565415` |
| Full Python suite در HEAD | `UNVERIFIED` | پس از `558f8daa` دوباره اجرا نشد؛ قبل از fix 163/15/1 |
| Full Vitest در HEAD | `UNVERIFIED` | تلاش قبلی در 16/201 متوقف شد |
| Sarkhati branch | PASS در محیط ایزوله | 146 سوئیت / ALL PASSED؛ Vitest 202 فایل/2102 تست؛ DB unchanged |
| Rahavard branch | PASS در محیط ایزوله | Full gate `VERIFIED`؛ 147 سوئیت؛ DB unchanged |
| شکست‌های pre-existing | مستند | `repo hygiene` 122/123؛ `tsetmc_p0` 164/165؛ `mstat_status_panels_contract_v1` 201/203؛ `fundamental-codal-poll` 3 failure |

**پوشش مسیرهای مهم در آخرین CI main:**

| مسیر | نتیجه | وضعیت |
|---|---|---|
| patch/update و delta | `patch/update system guard` 55/55 | سبز |
| آداپتور EasyTrader و عدم ارسال کور | 162/162 | سبز |
| گیت‌های P0 اجرای سفارش | 29/33 | **قرمز** |
| پروتکل Sarkhati | 0/3 | **قرمز** |
| chart API و klinecharts | 10/18 | **قرمز** |
| FTS filter isolation | 23/23 | سبز |
| بازار/شاخص رسمی | 11/11 و 12/12 | سبز |
| mstat dashboard | 187/187 | سبز |
| repo hygiene | 122/123 | **قرمز** |

### Release

| مورد | مقدار |
|---|---|
| آخرین release | `v1.0.95`، Published 2026-10-19T19:36:51Z |
| assets | Setup 41.1MB، Portable 138.2MB، سه patch delta + sig، Manifest، `codal.db.lzma` + `.sig`، `latest.json` |
| tag | `a14375c1` |
| drift | main 36 کامیت / 217 فایل جلوتر؛ `APP_VERSION` همان 1.0.95 |
| نصاب 1.0.96 | فقط روی branch Sarkhati؛ SHA `0a8dbb45…`؛ منتشرنشده |

### دیتابیس‌ها

| مورد | مقدار |
|---|---|
| `market.db` محلی | 275,759,104 بایت؛ mtime 2026-10-19 10:30؛ SHA-256 `7fbd9a4932dc211a80a8c528f12270a6759778dc625ca61dc126425c153e54f6` |
| `user.db` محلی | 782,336 بایت؛ mtime 2026-10-15 21:16؛ SHA-256 `9f265f4529dedce399172679ecc43906215a6a7d34ce9244ed1dc38bd4239c1e` |
| SHA عملیاتی گزارش Rahavard | `7b933b05d03b8a2f9383f901faf6b2c34f1500e70619d6cc5c8039f171b1848c` |
| SHA promoted گزارش Rahavard | `8fb85f381317634430cae429bd9775eba0a364b692e0868b4d9b17dbbcc6c17f` |
| نتیجه | hash محلی با هیچ‌کدام از دو مرجع گزارش برابر نیست؛ این audit روی همان کپی گزارش نبوده. **`UNVERIFIED`**؛ هیچ نوشتنی انجام نشد |

> `market.db` و `user.db` در گیت نیستند و در snapshot دیتابیس وارد نشدند. هیچ migration یا backfill اجرا نشد. ادعای «DB دست‌نخورده» فقط برای branchهای گزارش‌شده معتبر است، نه برای این audit.

---

## ۱۰) پیشنهاد ترتیب کارهای بعدی و وابستگی‌ها

1. **P0-1 + P0-2 — انتشار و CI:** اول باید معلوم شود کدام commit «نسخهٔ درست» است. بدون این، هر merge/release بعدی روی یک نسخهٔ مبهم می‌نشیند. وابستگی: تصمیم مالک برای bump یا retag؛ fixture DB در CI.
2. **P0-3 — Raw H/L:** مستقل از release؛ یک باگ دادهٔ واقعی است. merge `376d03de` + طراحی schema محلی. وابستگی: هیچ (به جز CI سبز برای گاردها).
3. **P1-7 — پاک‌سازی working tree:** پیش از هر merge بزرگ، تا شواهد و کارهای نیمه‌کاره گم نشوند. وابستگی: طبقه‌بندی مالک روی `_audit` و docs.
4. **P1-1 — rebase/merge Sarkhati:** بعد از CI سبز و پاک‌سازی. بزرگ‌ترین ریسک تعارض، 36 کامیت عقب‌بودن و 234 فایل تغییر است.
5. **P0-4 — آزمون زندهٔ سفارش:** فقط پس از merge/نصب 1.0.96 و با ورود دستی مالک؛ معیار، یک سفارش حداقلی و read-back است، نه ادعای آمادگی.
6. **P1-5 — marks/S رهاورد:** موازی و مستقل از کد؛ ورودی بیرونی می‌خواهد. تا آن زمان هیچ فرمول type7 تغییر نکند.
7. **P1-3/P1-4 — performance protected و وضعیت بازار:** پس از تثبیت نسخه.
8. **P2/P3 — Android، UI، تصمیم‌های تکنیکال و اسناد:** بعد از بستن P0/P1.

**بزرگ‌ترین blockerهای واقعی:**

- **نشست/تأیید مالک** برای سفارش واقعی Sarkhati و برای تطبیق دیدنی رهاورد.
- **marks/S مرجع** برای type7؛ بدون آن 100% قابل‌اثبات نیست.
- **schema محلی `price_history`** برای نگه‌داشتن `high_raw/low_raw`.
- **CI بدون DB** و **PNGهای tracked-ignored**؛ تا این‌ها حل نشوند، «سبز بودن» قابل‌اعتماد نیست.
- **واگرایی branchها:** Sarkhati 36 و Rahavard 21 کامیت عقب‌تر از main هستند؛ merge بدون rebase/آزمون کامل، ریسک regression دارد.

---

## ۱۱) محدودیت‌های audit و موارد تأییدنشده

| مورد | وضعیت |
|---|---|
| عدم اجرای suite کامل روی main در HEAD | `UNVERIFIED` — فقط log تلاش قبلی و آزمون‌های هدفمند |
| عدم اجرای CI محلی/بازتولید CI | `UNVERIFIED` — log GitHub خوانده شد، نه اجرای مجدد |
| تطبیق محتوایی UIUX 2.0 و UI audit با main | `UNVERIFIED` — branchها ancestor نیستند، اما ممکن است superseded شده باشند |
| صحت امضای APK اندروید | `UNVERIFIED` — زنجیرهٔ گواهی بررسی نشد |
| DB عملیاتی/promoted | `UNVERIFIED` — hash محلی با گزارش branch یکی نیست |
| دسترسی به PRهای Coder1/Coder3 | این کارها PR ندارند؛ push مستقیم/شاخه بودند |
| `git fetch` کامل | ناپایدار؛ snapshot رسمی tarball جای آن را گرفت |
| گزارش‌های قدیمی | فقط به‌عنوان نقطهٔ شروع؛ وضعیت جاری از main/CI/گزارش‌های 2026-10-20 به بعد |

---

## ۱۲) جمع‌بندی کوتاه

- **در main هست:** Performance Phase 1/2 (21 کامیت)، اصلاحات وضعیت بازار و شاخص رسمی، FTS funnel/موتورها، UI و Strategy Tree، Sarkhati پایه، release v1.0.95.
- **در main نیست:** اصلاح Raw H/L رهاورد (`376d03de`)، راندهای ۷–۲۱ Sarkhati (56 کامیت، 19 ماژول، نصاب 1.0.96)، Android 1.1.3، UIUX 2.0/UI audit.
- **سه اولویت بعدی:** (1) رفع drift نسخه و سبزکردن CI، (2) merge اصلاح Raw H/L + schema محلی، (3) rebase و merge Sarkhati و سپس آزمون کنترل‌شدهٔ مالک.
- **بزرگ‌ترین blockerها:** ورود/تأیید مالک برای سفارش و رهاورد، نبود marks/S، نبود `high_raw/low_raw` در DB محلی، و CI بدون DB.
