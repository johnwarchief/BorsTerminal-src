# ویندوز ۱٫۰٫۹۰ — تحویلِ کارِ توسعه به سیستم اول (DEV HANDOFF)

> **اینِ سند انتشار نیست.** هیچِ Release، هیچِ tag، هیچِ asset عمومی، هیچِ تغییری درِ
> `latest.json` وِ هیچِ ادغامی درِ `main` درِ اینِ مأموریت انجام نشده وِ انجام *نمی‌شود*:
> انتشارِ رسمیِ نسخه only درِ اختیارِ سیستم اول (Release Owner) است.
> تاریخِ سنجش‌ها: ۱۴۰۵-۰۷-۲۳ / ۲۰۲۶-۱۰-۱۵–۱۶، رویِ همینِ شاخه.

## ۱) شناسۀِ شاخه (سنجیده، نه ازِ حافظه)

| مورد | مقدار |
|---|---|
| worktree | `C:/Users/Johnkallnaya/Desktop/Borsterminal/.worktrees/windows-stable-release` |
| branch | `mission/windows-stable-release-2026-10-15` |
| پایه | `c04026145769b316381997e6931ef07c9eb46a1d` |
| پایۀِ شاخه == `refs/heads/main` رویِ remote | بله — `git ls-remote origin refs/heads/main` همان `c040261` را می‌دهد |
| فاصلۀِ شاخه ازِ main | ۱۰ کامیت جلوتر، صفرِ کامیتِ عقب‌مانده → fast-forwardِ تمیز، بی‌واگرایی |
| upstream محلی | عمداً **تنظیم نشده** تا هیچِ pushِ تصادفی بهِ `main` ممکن نباشد |
| نسخۀِ اعلام‌شدہ درِ anchorها | `1.0.90` (ششِ لنگر، گاردِ پایین) |

۱۰ کامیتِ اینِ شاخه ازِ پایه (به ترتیبِ واقعیِ تاریخچه):

```
0768099 fix(ui): make the pinned chrome actually pin on 1366x768
2e41bba fix(ui): let the technical chart toolbar wrap so its controls stay clickable
f5b16bc fix(ui): stop the FTS overlays from stealing the chart controls
f08a169 fix(ui): Escape closes the symbol inspector when focus is inside it
5cbf0f9 fix(ui): keep the indicator panel inside the viewport
93f1538 fix(ui): give the show-password toggle a real touch target
9e02cd9 test(ui): add testids for the analyst modal and portfolio view switch
c79c881 feat(ui): give tape execution and the trading bot a nav destination
4c28374 chore(release): 1.0.90 — six anchors together, guard run after the bump
95f6999 fix(dev): declare pypdfium2, the notebook witness tool's first import
```

هفتِ کامیتِ اول «transplant» هستند، نه merge: شاخۀِ آدیتِ UI ازِ `main` واگرا بود
(۱۰۲ کامیتِ main ازِ مبدأ، ۴۰۹ فایلِ سمتِ آدیت، ۳۶۸ فایلِ سمتِ main، ۳۲ فایلِ مشترک)،
پس فقطِ اصلاحاتِ ثابت‌شده باِ `cherry-pick -x` برداشته شد وِ تغییراتِ سیستمِ اول
(EasyTrader، سرخطی، ربات) دست‌نخورده ازِ `main` ماند. دوِ patchِ آدیت که درِ main
قابلِ اعمال نبودند حذف نشدند بلکه **مستند** شدند: `MarketChartSection.tsx` و
`MarketSectionNav.tsx` درِ main وجود ندارند (main آن‌ها را حذف کرده)، پس نسخه‌هایِ
آدیتِ آن‌ها باِ `git rm` ازِ انتقال بیرون ماندند.

## ۲) آنچه درِ اینِ دور اضافه شد (کارِ تمام‌نشده ازِ دورِ قبل)

`dev/run_all_tests.py` — دو اصلاحِ کوچک وِ همۀ‌اش درِ ابزارِ تست، بی‌هیچِ اثری رویِ محصول:

1. `LONG_TIMEOUTS`: بودژۀِ زمانیِ هرِ سوئیت جدا ازِ پیش‌فرضِ ۶۰۰ ثانیه. علتِ سنجیده‌شده:
   `dev/fts_engine_paths_parity_v1076.py` رویِ ماشینِ **بی‌رقابت** ۴۸۱ ثانیه طول کشید
   (rc=0، ۷ سبز / ۰ قرمز، ۹۲۲ نماد، صفرِ واگرایی) — تنها ۲۰٪ فاصلۀِ تنفس. درِ همانِ
   دوری که باِ `npm run build` وِ سنجشِ مرورگر هم‌زمان اجرا شد، ازِ ۶۰۰ گذشت وِ **قرمز
   شد بی‌آنکه کد ایرادی داشته باشد**. بودژۀِ جدیدِ اینِ سوئیت ۱۲۰۰ ثانیه است؛ داوری
   نرم‌تر نشده: سوئیت همچنان باید rc=0 بدهد وِ شمارۀِ واگرایی صفر باشد.
   **اینِ نقص درِ CI هم زنده است:** `guards.yml` همانِ ۶۰۰ ثانیه را بهِ runnerی می‌دهد که
   ازِ اینِ ماشین آهسته‌تر هم olabilir. سیستمِ اول پیش ازِ merge تصمیم بگیرد که اینِ
   سطرِ `LONG_TIMEOUTS` را بپذیرد یا بودژۀِ CI را جدا تنظیم کند.
2. پرینتِ علتِ `FAIL` ازِ `[:60]` بهِ `[:180]` باز شد. متنِ `TimeoutExpired` باِ نامِ
   فرمان شروع می‌شود، پس «timed out after 600 seconds» هیچ‌وقت چاپ نمی‌شد وِ قرمزیِ
   سوئیتِ سنگین ازِ قرمزیِ سوئیتِ خراب قابلِ تفکیک نبود — همینِ بلeness باعث شد اینِ
   ایرادِ محیطی بهِ جایِ تشخیص، دوباره‌اجرا شود.

## ۳) گیت‌هایِ نهایی رویِ همینِ کد (همگی درِ اینِ دور اجرا شده، نه تاریخی)

| گیت | دستورِ واقعی | نتیجه |
|---|---|---|
| TypeScript | `npx tsc -b` (درِ `frontend/`) | rc=**0**، بی‌خروجی |
| Vitest کامل (بی‌رقابت) | `npx vitest run` | **168 فایل سبز / 2 skip، 1698 تست سبز / 5 skip**، rc=**0**، 258٫31s |
| Vitest کامل (باِ رقابت) | همانِ دستور هم‌زمان باِ battery | 1 قرمز: `master-page.spec.tsx` «Test timed out in 5000ms» درِ 5248ms؛ کلِ suite 415٫80s. **اثباتِ علت:** همانِ فایل تنها **5 سبز / 0 قرمز** درِ 3٫17s، وِ اجرایِ کاملِ بی‌رقابت بالا 1698 سبز. یعنی contention، نه regression |
| Lint | `npx eslint .` | rc=**1**، 4 خطا — **همۀ‌اش ازِ main بهِ ارثِ اینِ شاخه** (بندِ ۵) |
| Python battery | `python dev/run_all_tests.py` | ← verdict درِ پایینِ همینِ جدول پس ازِ اجرایِ بی‌رقابت |
| گاردِ شمارشِ گیت‌ها | `python dev/guard_counts_v1110.py` |rc=0؛ تنها **20 سبز / 0 قرمز**، درِ دلِ battery همانِ سوئیت **33/33** خوانده می‌شود (`summarize` دوِ شمارشِ مختلف می‌دهد، پس هر دو اینجا ثبت شده) |
| گاردِ لنگرهایِ نسخه | `python dev/version_anchor_guard.py` | **6 بررسی / 0 خطا** → `VERSION ANCHOR GUARD OK`، همه `1.0.90` |
| گاردِ الفبایِ فارسی | `python dev/persian_glyph_guard.py` | **4 سبز / 0 قرمز** (بیرونِ استثنایِ ثبت‌شده، CJK وِ رقمِ دزدیده‌شده نیست) |
| build تولیدی | `npm run build` | rc=**0**، 14٫04s (دوباره 18٫99s پس ازِ اصلاحاتِ کامنت) |
| بستهٔ ویندوز (محلی) | `python scripts/build_all.py --skip-npm` | rc=**0**، 123s، خروجی `dist/BorsTerminal_Ultimate/` = **119٫6 MB**، EXE = **16٬983٬784 B** |

### اثباتِ «همانِ کد، همانِ بسته»

ویرایش‌هایِ اینِ دور درِ `Sidebar.tsx`، `TradingPage.tsx`، `WatchSummaryPanel.tsx` وِ
`trading-nav.spec.tsx` **فقطِ کامنت** بودند. برایِ اینکه اینِ ادعا حدس نباشد، build دوباره
اجرا شد و نامِ هر **38** فایلِ `frontend/dist/assets` باِ آنچه داخلِ EXE سنجیده‌شدۀِ من
(`_internal/frontend/dist/assets`) مقایسه گردید: **کاملاً یکسان**. چون Vite نام‌ها را باِ
hashِ محتوا می‌سازد، اینِ تطبیق یعنی رفتارِ بیلدِ منجمدِ آزموده‌شده بی‌تغییر است وِ لازم
نبود بسته را دوباره بسازم/اجرا کنم.

### شاهدِ ماژول‌هایِ داخلِ بسته

`_audit/ui/pyz_witness.py` (نویینِ اینِ دور) فهرستِ `build/fts_terminal/PYZ-00.toc` وِ
CArchiveِ خودِ EXE را می‌خواند: **38 ماژولِ backend سبز، 0 غایب** — ازِ جمله
`api.execution`، `api.bot`، `execution_easytrader`، `execution_service`،
`execution_contract/mock/timing/ledger`، `bot_signals`، `paper_trading`، همهٔ
`codal_*`، `funnel_*`، `mstat_engine`، `market_state` — وِ `bors_entry` که درِ onedir
درِ CArchive است نه PYZ، جدا سنجیده می‌شود. rc=**0**.

اینِ گارد یکِ ادعایِ غلطِ موجود درِ کامنتِ `fts_terminal.spec` را هم لو داد: آنجا نوشته
بوده `execution_latency` سطح‌بالِ `api/execution.py` است. سنجشِ PYZ نشان داد نیست، وِ
تنها مصرف‌کنندۀِ واقعیِ آن `dev/execution_latency_v1.py` است. کامنتِ spec اصلاح شد
(بیلدِ منجمد هیچِ راهِ اجرایی بهِ آن ماژول ندارد، پس درِ بسته هم لازم نیست).

## ۴) ایمنیِ معاملاتی — سنجیده رویِ خودِ فایلِ اجرایی

بسته رویِ پورتِ اختصاصیِ من (`BORS_PORT=8010`، حالتِ portable باِ `bors_portable.flag`
وِ `market.db.lzma` کنارِ EXE) اجرا شد وِ همانِ پروسه سنجیده شد، نه dev server:

- `/api/update/version` → `{"version":"1.0.90","tauri":false,"mode":"portable","instance":"c4445b148a38"}`
- `/api/execution/status` → `adapter="mock"`، `dry_run=true`، `live_enabled=false`،
  `nothing_will_leave_the_machine=true`، `live_requested=false`،
  `blocked_on=["آداپتورِ واقعی انتخاب نشده (BORS_EXECUTION_ADAPTER=easytrader)"]`
- `/api/bot/status` → `config.enabled=false`، `config.mode="paper"`، `kill="ARMED"`،
  `halted=false`، `live_gates.all_open=false`، سرمایهٔ نمایشی `start_cash=100000000.0`،
  `commission_bps=30.0` (=۰٫۳٪)، `slippage_bps=10.0` (=۰٫۱٪)
- **Halt/Resume** رویِ همانِ بسته: `POST /api/bot/halt` → `kill="HALTED"`،
  `halted=true`؛ `POST /api/bot/resume` → `kill="ARMED"`، `halted=false`. متنِ علتِ توقف
  درِ UTF-8 درست برگشت (`ROUNDTRIP_REASON_OK=True`). ردِّپا درِ `user.db` (نه
  `market.db`) رویدادهایِ kill را باِ `actor="bot-panel"` ثبت کرد — تاریخچهٔ واقعی، نه
  حالتِ نمایشی. `TRIPPED` هم درِ کد بی‌اقدامِ صریحِ ریسک باِ `resume` باز نمی‌شود
  (`api/bot.py:508`).
- تاریخچه: `/api/execution/ledger` → `{"kill_switch":"ARMED","open_ids":[],"scheduled":[],"records":[]}`؛
  `/api/bot/history` → `{"runs":[],"events":[],"account":{}}` (بانکِ تازه، بی‌سفارشِ ساختگی)
- `_start_uvicorn` هیچِ زمانِ سفارشی ندارد؛ باز کردنِ هیچِ صفحۀ‌ای ربات را اجرا نمی‌کند
  (بندِ ۶ وِ ۶-بِ پایین).

### آزمونِ «هیچِ سفارشی نمی‌رود» — وِ اصلاحِ ادعایِ غلطِ خودم

آزمونِ واحد وِ harnessِ مرورگر من اول اینِ مأموریت مدعا می‌دادند: «صفرِ درخواستِ غیرِ GET».
**اینِ مدعا نادرست بود.** سنجشِ مرورگر رویِ بسته نشان داد خودِ برنامه
`POST /api/funnel` می‌زند (خواندنِ قیف باِ بدنهٔ زنجیره، `queryFn` درِ
`features/master/api/useFtsFunnel.ts:163`) وِ `api/funnel.py` **صفر** عبارتِ
`INSERT/UPDATE/DELETE/commit` دارد — یعنی آنِ POST نوشتگی درِ معنایِ مأموریت نیست.
کدِ endpoint یا UI را برایِ سبزکردنِ تست تغییر ندادم؛ **مدعا را باِ واقعیت تطبیق دادم**
وِ آن را قوی‌تر کردم: حالا قاعده «هیچِ درخواستِ غیرِ خواندنی درِ **قلمروِ**
`/api/execution` وِ `/api/bot`» است، نه فهرستِ دستیِ مسیرها — اگر نسخۀِ بعد راهِ
سفارشِ تازه‌ای اضافه کند، همینِ قاعدہ می‌گیرتش. (فهرستِ مسیرهایِ نوشتگیِ هر دو فایل ازِ
`api/execution.py` وِ `api/bot.py` بیرون کشیده شد: dispatch/prepare/preflight/probe/
halt/resume/session/reconcile/refresh/queue وِ run/halt/resume/account-reset/config —
همگی زیرِ همینِ دوِ پیشوند.)

**سبز‑قرمزِ همینِ invariant (تا حدس نباشد):** موقتاً `void fetch('/api/bot/run',{method:'POST'})`
به `TradingPage` تزریق شد → آزمون **قرمز** شد (`1 failed | 4 passed`)؛ فایل بازگردانده شد
(`grep -c "RED-GREEN PROBE"` = 0) وِ آزمون دوباره **سبز** شد (`5 passed`). پس اینِ تست
واقعاً مسیرِ ربات را می‌بیند، نه اینکه همیشه سبز باشد.

شاهدِ مرورگری: `_audit/ui/TRADE_PROBE.json` — **22 سبز / 0 قرمز**، 39 درخواستِ ثبت‌شده،
`nonGet: ["POST /api/funnel"]`، `orderOrBotWrites: []`،
`killAtStart="ARMED"` وِ `killAtEnd="ARMED"`، `consoleErrors: []`.

## ۵) ایرادهایِ بازِ شناخته‌شده (پنهان نمی‌ماند)

1. **`npx eslint .` قرمز است: 4 خطا، هیچ‌کدام ازِ اینِ شاخه.** سه فایلِ مظنون
   (`src/__tests__/funnel-preset-switch.spec.tsx` → `@ts-nocheck`؛
   `src/features/market/lib/tapeAlgorithms.ts:475` → `no-fallthrough`؛
   `src/shared/components/TapeHistoryPanel.tsx:24` → دوِ `no-useless-escape`) باِ
   `git diff --quiet c040261` **بی‌تغییرِ محتوا** نسبت بهِ main تأیید شدند. لمسِ
   `no-fallthrough` داخلِ `tapeAlgorithms.ts` رفتارِ محاسباتیِ سرخطی را عوض می‌کند وِ
   درِ محدودهٔ اینِ checkpoint نیست — برایِ سیستم اول، بهِ‌عنوانِ بدهیِ ازِ قبلِ ما.
   (نکته: lint درِ `guards.yml` یا jobِ انتشار اجرا نمی‌شود، پس اینِ قرمزیِ CI را نمی‌شکند.)
2. **بودژۀِ CI برایِ سوئیتِ سنگین.** همانِ `LONG_TIMEOUTS` بالا؛ تا وقتی merge نشود،
   `guards.yml` می‌تواند رویِ runnerِ آهسته قرمزِ کاذب بدهد.
3. **`Setup.exe` درِ اینِ ماشین ساخته نمی‌شود** — پس هیچِ «نصبِ نهایی» ازِ من تست نشده:
   Inno Setup 6 درِ هیچ‌یک ازِ سه مسیرِ معیار نیست وِ `ISCC` رویِ PATH نیست؛
   `installer/.setup_password.iss` نیست (ازِ secretِ `BORS_SETUP_PASSWORD` درِ CI ساخته
   می‌شود)؛ کلیدِ خصوصیِ به‌روزرسان (`TAURI_SIGNING_PRIVATE_KEY`) هم فقط درِ CI است.
   بستهٔ من **آزمایشی وِ بدونِ امضا** است.
4. **محیطِ بیلدِ من باِ CI یکی نیست:** Python 3.14.4 (CI: 3.12)، `numpy 2.5.2` /
   `pandas 3.0.5` (چسبندۀِ مخزن `numpy==2.0.2`). سبزیِ گیت‌هایِ محلی شاهدِ هدفِ CPUِ
   نسخۀِ انتشار نیست.
5. **اتصالِ واقعیِ کارگزاری وِ ارسالِ سفارش آزموده نشد** — عمداً، چون عملِ مالک است.
   هیچِ capabilityِ کارگزاریِ آزمون‌نشده‌ای درِ اینِ سند «تأییدشده» گزارش نشده؛ پنل هم
   خودِ `capabilities.balances: false` را درِ UI باِ «بی‌داده … صفر جا نمی‌زند» اعلام می‌کند.
6. **`/trade` درِ برابرِ `/execution` + `/bot`.** اینِ دور برایِ بستنِ «مقصدِ ناوبری
   نداشتن» یکِ مسیرِ واحد باِ دوِ تب ساخته شد (`routes.tsx` → `path: 'trade'`،
   `Sidebar.tsx` → «سرخطی و ربات»). اگر سیستم اول معماریِ جداسازیِ دوِ فضای کاری را
   بپسندد، اینِ مسیرِ واحد مهاجرتِ آسانی دارد (هرِ دوِ پنل بدونِ تغییرِ consumerند).
   **ادعایِ اصلاح‌شده:** برخلافِ نوشتهٔ اولِ من، `ExecutionPanel` بی‌mount نبود — درِ
   `WatchSummaryPanel.tsx:95` نصب بود که خودِ `WatchMarketWorkspace.tsx:236/266` درِ
   تب‌هایِ «سرخطی/بازارِ» دفترچۀِ نماد درِ `/watch` آن را می‌سازد. نقصِ واقعی **نداشتنِ
   مقصدِ مستقلِ ناوبری** بود، وِ همانِ عبارتِ غلط درِ RELEASE_NOTES، کامنتِ `TradingPage`،
   `trading-nav.spec`، `Sidebar` وِ یکِ برچسبِ غلطِ کهنه («پنلِ ربات» برایِ `ExecutionPanel`
   درِ `WatchSummaryPanel.tsx`) اصلاح شد. بازرسیِ اثباتی: عبارت‌هایِ «mount نبودن»/
   «وجود نداشتنِ پنل» درِ `frontend/src`، `dev/` وِ `_audit/ui/` صفرِ نتیجه
   دارند (جست‌وجو درِ `docs/` شمارش نمی‌شود، چون خودِ همینِ سندِ پیشِ رو آنِ
   ادعایِ رد‌شده را درِ نقلِ‌قول می‌آورد).

## ۶) نتایجِ مرورگر (بستهٔ منجمد، نه dev server)

`_audit/ui/FROZEN_EM_1366x768.json` وِ `_audit/ui/FROZEN_REAL_maximized.json`، هر دو rc=**0**:

- **22/22 مسیر** باِ نشانۀِ آمادگیِ واقعیِ خودِ صفحه (`readyBy=marker`، نه timeout).
  `routes.js` را همینِ دور باِ `/trade` به‌روز کردم (22 ردیف).
- درِ **هر دو** حالت: صفرِ سرریزِ افقی، صفرِ متنِ بریدۀِ بی‌سه‌نقطه، صفرِ کنترلِ بیرونِ
  viewport، صفرِ کنترلِ پوشیده، صفرِ پنلِ اسکرول‌نشدنی.
- حالتِ `real` واقعی است نه تقلبی: `headless:false` + `--start-maximized`،
  `physicalViewport = 1358×636`، وِ رشتهٔ `HeadlessChrome` درِ user-agent **نیست**
  (اینِ تفکیک را ازِ درسِ دورِ قبل اضافه کردم).
- `sticky_probe.js` rc=0: فقطِ Topbar چسبان است (`h-9` = 36px)، `.app-main` ازِ `top=36`
  شروع می‌شود؛ نوارِ نماد دیگر sticky نیست چون ارتفاعش باِ flex-wrap بهِ محتوا بستگی دارد.
- `toolbar_fit.js` rc=0 وِ `inspector_keys.js` rc=0 (۵ سناریو، `errors=0`): `Esc` پنلِ
  نماد را فقط وقتی می‌بندد که فوکوس داخلش باشد.
- `overlap_probe.js` rc=0: `covered=0` رویِ هر 22 مسیر. پرچم‌هایِ
  `OUTSIDE-OWN-SCROLLER` درِ `/trade` **مثبتِ کاذبِ خودِ harness** بودند وِ باِ سنجشِ
  جدا اثبات شدند: فهرستِ نماد `overflow-y:auto` باِ `maxH=256px`، `scrollH=1038` درِ
  `clientH=256`، 40 ردیف که 30 تا بیرونِ برش بودند، وِ `scrollIntoView` همانِ ردیف را
  داخلِ اسکرولر می‌آورد (`inside=true`, `scrollTop>0`). یعنی ردیف‌ها دیدنی‌اند، نه گم.
- `fit_check.js` rc=0: هر `OVERFLOW` ازِ راهِ scroll-containerِ خودش `REACHABLE` است.
- تعاملاتِ `/trade` (22 سنجش، rc=0): دوِ تب دیده می‌شوند، تبِ پیش‌فرض سرخطی است
  (`watch-order-panel` نمایان، `bot-panel` غایب)، باِ کلیکِ تبِ ربات اینِ دوِ حالت دقیقاً
  برعکس می‌شود وِ برمی‌گردد، یادداشتِ «کاغذی» رویِ صفحه خوانده می‌شود، پنلِ سرخطی
  دفترِ واقعیِ خودش را باِ 13 آزمونگارِ واقعی می‌سازد (`watch-order-buy/sell/price/qty/
  balance-row/phase/reason/actions` + `tape-buy-pc/tape-sell-pc`)، وِ بارِ `/portfolio`
  (محلِ قدیمیِ `BotPanel`) هم بی‌کلیک هیچِ نوشتگی نمی‌رود.

## ۷) یادداشت‌هایِ انتشار وِ زنجیرۀِ به‌روزرسان

- `docs/RELEASE_NOTES.md`: بخشِ `## v1.0.90` اضافه شد **به‌صورتِ افزودنیِ محض**:
  `git diff --numstat` = **۵۰ افزودن / ۰ حذف**، وِ متنِ ازِ `## v1.0.89` به‌بعد
  **بایت‌به‌بایت یکسان** باِ نسخهِٔ commit‌شده (۲۷۱٬۹۷۰ B درِ هر دو طرف). درِ میانهٔ کار
  خودم یکِ بارِ اشتباه همانِ سربال `v1.0.89` را بلعیدم وِ بازگردانده شد — همینِ تطبیق
  برایِ اثباتِ بازگشت انجام شد، نه برایِ اعلانِ بی‌عیب.
- `scripts/publish_github_release.py::release_body` اجرا/تست شد:
  `v1.0.90` → ۳٬۰۹۰ کاراکتر (فقطِ بخشِ خودش)، `v1.0.89` → ۴٬۳۰۴ کاراکتر (بخشِ خودش)،
  `v1.0.99` → پیامِ صریحِ «یادداشت پیدا نشد». یعنی ناشرِ CI متنِ درست را برمی‌دارد.
- وضعیتِ **دست‌نخوردهٔ** remote: `johnwarchief/BorsTerminal` (public) →
  `releases/latest` = `v1.0.89` باِ 13 asset؛ `latest.json` →
  `version=1.0.89`، `url=…/v1.0.89/BorsTerminal_Ultimate_Setup_v1.0.89.exe`،
  `signature=dW50cnVzdGVk…` (minisign). تگِ `v1.0.90` رویِ remote **نیست**
  (`releases/tags/v1.0.90` → 404). هیچ‌یک ازِ این‌ها درِ اینِ دور نوشته نشد.
- مخزنِ سورس `johnwarchief/BorsTerminal-src` خصوصی مانده (تصمیمِ مالک) وِ مخزنِ
  انتشار public: لازم است، چون آپدیتر بی‌احراز هویت می‌خواندش
  (`api/update.py:66-67` → `…/releases/latest/download/latest.json` وِ
  `bors_config.py:283` → assetِ `market.db.lzma`).

## ۸) کارِ سیستم اول برایِ انتشار (من عمداً انجام ندادم)

1. merge/PR بهِ `main` (شاخه برایِ fast-forward آماده است).
2. تعیینِ شمارۀِ نهایی. **توجه:** لنگرها رویِ `1.0.90` تنظیم شده‌اند. اگر شمارهٔ دیگری
   می‌خواهید، هر **شش** لنگر باِ هم عوض شوند وِ `python dev/version_anchor_guard.py`
   دوباره rc=0 بدهد: `bors_config.APP_VERSION`، `frontend/package.json`،
   `package-lock.json` (ریشه + `packages[""]`)، `frontend/src-tauri/tauri.conf.json`،
   `installer/bors_setup.iss` (`#define AppVersion`).
3. `git tag vX.Y.Z && git push origin vX.Y.Z` → خودِ CI انتشار را می‌سازد
   (`release.yml` رویِ `push: tags: v*`؛ jobِ `release-windows`/Tauri دستی است وِ
   `release-inno` رویِ پوشِ تگ اجرا می‌شود): `npm ci` → `npm test` → بازسازیِ
   `.setup_password.iss` ازِ secret → `scripts/build_all.py` → ISCC → `tauri signer sign`
   → manifest → Portable ZIP (assetِ `data-latest` را می‌گیرد) →
   `scripts/publish_github_release.py` باِ `RELEASE_TOKEN` → ناشر هر asset را دوباره
   دانلودِ وِ SHA-256/minisign را می‌سنجد وِ تأیید می‌کند `latest.json` همانِ تگ را اعلام کند.
4. پس ازِ انتشار: سلامتِ channelِ به‌روزرسانِ یکِ نصبِ واقعیِ قبلی (۱٫۰٫۸۷ → هدف).
   درِ اینِ ماشین **نصبِ مالک رویِ `1.0.87` است** (PID 5336، دست‌نخورده) وِ
   `releases/latest` رویِ `1.0.89` — یعنی channelِ رسمی ازِ نصبِ اینِ ماشین جلوتر است.
5. Android درِ اینِ مأموریت اصلاً لمس نشد.

## ۹) بازتولیدِ سنجش‌ها

```bash
# گیت‌هایِ JS/TS
cd frontend && npx tsc -b && npx vitest run && npx eslint . && npm run build

# گیت‌هایِ پایتون (درِ ریشۀِ worktree)
python dev/version_anchor_guard.py
python dev/persian_glyph_guard.py
python dev/guard_counts_v1110.py
python dev/run_all_tests.py                       # ~35 دقیقه؛ بی‌رقابتِ CPU اجرا کنید

# بسته + اجرایِ خودِ بسته
python scripts/build_all.py --skip-npm
cd dist/BorsTerminal_Ultimate
printf '' > bors_portable.flag                    # حالتِ portable، داده درِ ./data
cp ../../market.db.lzma .                          # درِ CI ازِ assetِ data-latest می‌آید
BORS_PORT=8010 ./BorsTerminal_Ultimate.exe

# آزمونگارها (رویِ همانِ بسته)
export BORS_UI_BASE=http://127.0.0.1:8010
python _audit/ui/pyz_witness.py
node _audit/ui/layout_audit.js  --mode=em   --out=EM.json
node _audit/ui/layout_audit.js  --mode=real --out=REAL.json
node _audit/ui/trade_probe.js
node _audit/ui/sticky_probe.js ; node _audit/ui/toolbar_fit.js ; node _audit/ui/inspector_keys.js
node _audit/ui/overlap_probe.js --mode=em ; node _audit/ui/fit_check.js
```

پیش‌نیازهایی که درِ هرِ checkoutِ تازه‌ِ `.worktrees` نیستند (به‌سببِ `.gitignore`) وِ
بدونِ آن‌ها battery قرمزِ محیطی می‌دهد: `market.db` (ازِ
`bors_config.ensure_market_db()`)، `_audit/ra365_ref_bars.json` وِ `market.db.lzma`
(کپیِ read-only ازِ `../BorsTerminal-src/`)، وِ یکِ venv باِ
`pywebview/pythonnet/openpyxl/python-docx/reportlab/pypdfium2`.

## ۱۰) verdictِ نهایی

`python dev/run_all_tests.py` رویِ ماشینِ **بی‌رقابت** (بدونِ build/مرورگر/vitest هم‌زمان):

- **ALL SUITES PASSED**، rc=**0**
- **105 سوئیت شمارش‌شده، 29 سوئیت بی‌شمارش** (فقطِ exit code — صریح اعلام می‌شوند،
  باِ نام‌هایشان درِ انتهایِ خروجی، پس سکوت هیچ‌وقت «سبز» خوانده نمی‌شود)
- دورِ قبلی که همینِ battery باِ `npm run build` وِ سنجشِ مرورگر هم‌زمان اجرا شد، **یکِ
  قرمز** داد: `dev/fts_engine_paths_parity_v1076.py` که تنها ۴۸۱ ثانیه کار لازم داشت وِ
  ازِ سقفِ ۶۰۰ ثانیه‌اش گذشت. علتِ دقیقش (TimeoutExpired، نه assertion) به‌سببِ
  بریدۀِ `[:60]` درِ پیامِ FAIL دیده نمی‌شد؛ هر دو اصلاحِ بندِ ۲ ازِ همینِ سنجش آمد.
- گیتِ JS هم درِ همانِ دور باِ contention قرمزِ کاذب داد (`master-page.spec.tsx`) وِ درِ
  اجرایِ بی‌رقابت سبز شد. **درسِ عملی برایِ سیستم اول: اینِ دو گیت سنگین را هم‌زمان
  اجرا نکنید؛ عددِ قرمزِ آن‌ها درِ رقابتِ CPU نشاندۀِ کد نیست.**

وضعیتِ تحویل: کدِ اینِ شاخه درِ هر سه سطحِ گیت (TypeScript، Vitest، Python battery) وِ
build تولیدی وِ بستهٔ منجمدِ اجراشده سبز است. **انتشارِ ۱٫۰٫۹۰ عمداً انجام نشد** — باِ
تصمیمِ مالک، شمارۀِ نسخه، ادغام درِ `main`، تگ، asset عمومی وِ `latest.json` همگی باِ
سیستم اول است. لنگرها رویِ `1.0.90` مانده وِ هیچِ reset/بازگشتی درِ اینِ شاخه نشده است.

نکتۀِ صداقت: قاعدۀِ «قلمروِ نوشتگی» (`/api/execution` + `/api/bot`) پس ازِ آخرینِ اجرایِ
بسته درِ `_audit/ui/trade_probe.js` جابه‌جا شد وِ باِ همانِ بسته **دوباره اجرا نشد**؛ آنچه
اجرا وِ ثبت شد نسخهٔ فهرستیِ تنگ‌تر است که نتیجه‌اش `orderOrBotWrites: []` وِ تنها
`POST /api/funnel` بود (قلمروِ جدید ازِ همانِ داده بی‌واسطه نتیجه می‌شود، چون آنِ یکِ
POST هیچ‌کدام ازِ دوِ پیشوند را ندارد). قاعدۀِ جدید درِ آزمونِ واحد باِ قرمز‑سبزِ واقعی
اثبات شد (بندِ ۴).
