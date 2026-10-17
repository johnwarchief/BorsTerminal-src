# موجودیِ تحویل — system-1 · ۲۰۲۶-۱۰-۱۵

مخزن: <https://github.com/johnwarchief/BorsTerminal-src> (remote `github`) ·
سیستم: `system-1` · شاخۀ کاری: `mission/4-axes-2026-10-10` ·
HEAD هنگامِ بازرسی: `b9a60fc` · تازۀترین برچسبِ منتشرشده: `v1.0.88`.

این سند فقط چیزهایی را می‌گوید که درِ **همین سیستم** دیدم و بررسی کردم. هیچ ادعایی دربارهٔ
کارِ سیستمِ دوم یا شاخه‌هایی که درِ این ماشین نیستند، نشده است.

## ۱) وضعیت اولیهٔ Git (پیش ازِ هر کاری)

| مورد | مشاهده |
|---|---|
| remoteها | `github` = BorsTerminal-src (HTTPS) · `origin` = مسیرِ کاریِ Clineِ محلی (`C:/Users/PCMOD/.cline/data/workspaces/chat/BorsTerminal`) — بی‌استفاده درِ این تحویل |
| worktreeها | ۷ تا: این پوشه + `_bors-fund-browser` + `_bors-pre5c97b5c` + `BorsTerminal-android` + `BorsTerminal-baseline` + `BorsTerminal-desktop` + `BorsTerminal-roadmap` |
| کامیتِ محلیِ pushنشده | ۲ تا، هر دو سندِ من درِ `mission/4-axes-2026-10-10` (`9cf9308` ماتریس پنج مخزن، `b9a60fc` نقشۀ سرخطی) · **۱** کامیت محلیِ ایجنت نقشۀراه (`41c00a9` نسبتِ `github/roadmap-main`) |
| شاخه بی‌upstreamِ محتوایِ تازه | `arena/fts-mobile-uiux-20261007` بی‌upstream بود ولی ریموتِ هم‌نامش محتوا را داشت (۰/۰) ⇒ منتشرشده |
| detachedها | `e08dc56`، `5c97b5c`، `73b1c00` همگی ازِ `github/main` قابلِ دسترسی ⇒ منتشرشده، بی‌کارِ گم‌شده |
| تغییراتِ ثبت‌نشده | سه worktree کثیف + این worktree (جزئیات درِ بند ۵) |

## ۲) وضعیتِ هر حوزه

| حوزه | وضعیت | Branch | HEAD | Remote | تغییرات | تست‌ها | شواهد | باقی‌مانده | بلاکر | وابستگی |
|---|---|---|---|---|---|---|---|---|---|---|
| سرخطی / EasyTrader | `PARTIAL` | `mission/4-axes-2026-10-10` | `b9a60fc` | `handoff/system-1/easytrader-2026-10-15` | دو سندِ تازه: `docs/trading/EASYTRADER-OSS-RESEARCH-MATRIX.md`، `docs/trading/EASYTRADER-ADAPTER-HANDOFF.md`. هیچ کدِ آداپتوری نوشته نشد | گاردهایِ موجودِ سرخطی: ۱۸۶ سبز / ۰ سرخ (تاریخِ ۱۴۰۵-۰۷-۲۳، همان چیزی که درِ v1.0.88 منتشر شد) | دو سندِ بالا با file:line و SHA هر پنج مخزن | آداپتور `execution_easytrader.py`، تفسیرِ پاکتِ پاسخ، UI، تستِ mockِ گاردماند، frozen/Windows | D8 (کدام سکو) + D1 (مجوزِ PoC) + نشستِ مجازِ خودِ مالک | `execution_contract/service/ledger` (درِ main) |
| اتصالِ واقعی به کارگزاری | `BLOCKED` | — | — | — | هیچ | هیچ سنجشِ زنده‌ای ممکن نبود | نبودِ `adb_config.json`، نبودِ هیچ فایل/متغیرِ کارگزاری درِ این ماشین | هر گونه `LIVE_READ_ONLY_VERIFIED` / `LIVE_ORDER_VERIFIED` | دسترسیِ حساب + ورودِ تعاملی توسطِ مالک | — |
| بهینۀ کارایی (mstat + delta) | `DONE_VERIFIED` برایِ واحدِ سنجیده‌شده | `github/main` | `a412697` (کدِ رفع: `7196c61`) | رویِ `github/main` منتشر است | `api/market_status.py` (SWR + تک‌پروازگی + سقفِ کهنه + یک‌سطحِ کش + `stale_ok=False`)، `api/market.py` (برچسبِ `no-cache`)، `dev/mstat_swr_v1111.py` + ثبتش درِ `run_all_tests.py`، `dev/market_hot_state_v1077.py` (+۲ بررسی) | گاردهایِ اجراشده پس ازِ رفع: mstat_swr ۱۶/۰ · market_hot_state ۵۱/۰ · mstat_local ۲۰۸/۰ · proc_probe ۱۳/۰ · glyph ۴/۰. **`run_all_tests.py` کامل پس ازِ رفع اجرا نشد** (آخرین اجرا `ALL SUITES PASSED` exit ۰ رویِ `edbe6e6`، یعنی پیش ازِ رفع ⇒ این تست **قدیمی** است) | `_audit/perf_live/loops_on_22h_*` (پیش) و `loops_on_final_*` (پس): board p95 = 2570.4 → 104.1 ms · delta با `since` واقعی = 158 B در برابرِ 872,141 B | اجرایِ کاملِ گیت‌ها رویِ `7196c61+`؛ سنجشِ delta زیرِ بارِ بازارِ باز؛ عددِ سازگاریِ `count` با افزودن/حذفِ نماد | بازار باید باز باشد (۰۸:۵۰ به بعد) | — |
| نسخۀ دارایِ این رفع | **نیست** | — | — | — | `git tag --contains 7196c61` خالی است ⇒ رفعِ کارایی درِ هیچ برچسبِ منتشرشده‌ای نیست (درِ `main` هست، درِ v1.0.88 **نیست**) | — | همان دستورِ بالا | انتشارِ ۱٫۰٫۸۹ (عمداً انجام نشد: دستورِ این مأموریت ساختِ tag/release را ممنوع کرده) | تصمیمِ مالک برایِ انتشار | گیتِ کاملِ فرانت |
| Fundamental/CODAL | `PARTIAL` | `mission/4-axes-2026-10-10` | `b9a60fc` | پنل/خطِ دریافت درِ v1.0.88 منتشر شده | کارِ منتشرشده: `useCodalHealth.ts`، `CodalHealthStrip.tsx`، صف/زمان‌بند/invalidation | ۱۲ تستِ vitestِ پنل؛ گاردِ کدال درِ `run_all_tests` | `docs/SAME-DAY-CLOSURE-2026-10-14.md` §۷ | چرخۀ واقعیِ کدال (هرگز درِ این بانک ثبت نشده)، مرحلۀ ۱۰-۱۲ِ آن مأموریت، ۱۸۵ نشانکِ باز | واکشیِ زنده + رأی‌هایِ مالک | — |
| کارِ ثبت‌نشندۀ ایجنت بنیادی/مرورگر | `UNVERIFIED` (WIPِ ایجنت دیگر) | `_bors-fund-browser` @ `e08dc56` | `b54f575` (اسنپ‌شات) | `handoff/system-1/fundamental-browser-wip-2026-10-15` | `api/fundamental.py` (+۷۰/-۷)، `api/screener.py` (+۳۲/-۹)، `fts_engine.py` (+۱۶) — فقط ۹۸ خطِ افزوده، بی‌آزمونِ ثبت‌شده | هیچ تستی برایِ این diff اجرا **نشد** (کارِ من نبود) | خودِ شاخهٔ اسنپ‌شات | بازنگریِ خودِ ایجنت؛ مشخص نیست کامل است یا خیر | مالکیتِ کار با ایجنتِ بنیادی است | — |
| تطبیقِ TradersArena (۲۷ کلید) | `IN_PROGRESS` | `mission/4-axes-2026-10-10` | `b9a60fc` | درِ `github/main` (سند) | `docs/CONTINUATION-2026-10-14.md`؛ ابزار `tools/pulse_ta_parity.py` (سخت‌سازی‌شده درِ `7ccbdc6`) | ماتریسِ ۱۱ از ۲۷ سطرِ ارزش/جریان + کنترلِ منفیِ fallback (۱۱/۱۱ NOT_COMPARABLE) | `_audit/perf_live/ta_parity_matrix_20261014_1110.json`، `ta_parity_fallback_control.json` | ۱۶ کلیدِ باقیِ‌مانده؛ تعريفِ `pos`/`xyz` ازِ UI/مستندِ مرجع؛ `sf` (صندوق) ریشه‌یابی‌شده به‌عنوانِ تفاوتِ تعریف | نشستِ بازِ بازار برایِ مرجعِ تازه | — |
| ربات معامله‌گر کاغذی | `DONE_VERIFIED` (کاغذی) | `github/main` | `a412697` | درِ v1.0.88 | `trade_sim.py`، `backtest_engine.py`، `paper_trading.py`، `bot_signals.py`، `tools/bot_backtest_run.py` | `dev/bot_paper_v1109.py` ۵۴/۵۴ · بک‌تستِ واقعی ۴۰ نماد/۵۱۷ نشست | `_audit/bot_backtest/run_*.json`، §۶ سندِ پیش | مصرفِ رأیِ canonical درِ replay تاریخی (نیازمند signal journal) | — | هیچ‌کدام ازِ این پنج ماژول درِ بیلدِ منجمد **نیست** (بی‌واردکنندۀ منتشرشده؛ عمدی) |
| تکنیکال / موتور تعدیل / چارت | `UNVERIFIED` ازِ دیدِ من — **دامنۀ ایجنتِ دیگر** | `github/mission/fts-indicator-engineering` | `09e8d64` | منتشرشده، ۱۲ کامیت جلوتر ازِ main | دست‌نخورده؛ فقط شاهدشم | من اجرایش نکردم | `_audit/adjustment_parity_phasea.md` | تطبیقِ ≥۳۰ نماد (بیشینه‌ای که ثبت شده ۲۷ است، رویِ همین شاخه) | رأیِ مالک (مبنایِ تعدیل) | — |
| اندروید/موبایل | `PARTIAL` | `arena/fts-mobile-uiux-20261007` | `8af64a1` | منتشرشده (۰/۰ با ریموتِ هم‌نام) | ۳۷ کامیت جلوتر ازِ main؛ محلی‌اش فقط تعویضِ CRLFِ `dev/fixtures/fts_v10_payloads.json` بود (بی‌کارِ واقعی) | آزمونِ WebView/APK **عمداً** اجرا نشده | `docs/plan-android.md` (untracked، مالِ ایجنت موبایل) | امضایِ APK/مراسمِ کلید + WebView | مراسمِ کلید = فقط مالک | — |
| اسناد/ابزارِ نشست‌هایِ این سیستم | `DONE_VERIFIED` (منتشر) | `github/main` | `a412697` | منتشرشده | `SAME-DAY-CLOSURE-2026-10-14.md`، `MARKET-ACCURACY-AND-WATCH-EXPORT-2026-10-14.md`، `LIVE-PERF-AND-TA-PARITY-2026-10-14.md`، `CONTINUATION-2026-10-14.md`، `tools/*` | — | خودِ فایل‌ها رویِ main | — | — | — |

## ۳) تفکیکِ «کد منتشرشده» ازِ «درِ نسخۀ نصبی»

| چیز | درِ `github/main` | درِ برچسبِ released (v1.0.88) | درِ نسخۀ نصبیِ این ماشین |
|---|---|---|---|
| پنلِ سلامتِ کدال، دروازۀ اجرا، قفلِ توقف، ردِّپا، رباتِ کاغذی | بله | **بله** (رویِ بیلدِ منجمد هم آزموده شد) | بله (1.0.87 نبود؛ کاربر هنوز ارتقا نداده — نسخۀ نصبی ۱٫۰٫۸۷ گزارش شده است) |
| `7ccbdc6` (کاراییِ دورِ قبل: ttl شمارشِ پروسه + کشِ board) | بله | **بله** (ancestorِ برچسب) | — |
| `7196c61` (رفعِ p95 = 2570→104 ms) | بله | **خیر** | خیر |
| `a412697`/`b9a60fc` (سندها) | `a412697` بله؛ `b9a60fc` فقط رویِ شاخۀ مأموریت | خیر | خیر |

## ۴) کارهایِ محلیِ باقی‌مانده و علتِ منتشرنشدن

| مورد | علت |
|---|---|
| `_audit/` (۴٫۶ گیگابایت، ۳۱۳ فایلِ untracked درِ این worktree) | شاهد/خروجیِ موقت/artifactِ حجیم؛ مأموریت نشرِ این‌ها را ممنوع کرده |
| `Python/` (۹۸ مگابایت، نسخۀ مفسر با `.deleteme`) | نصبِ ابزارِ رویِ ماشین، نه محتوایِ مخزن |
| `docs/Technical_Pashootan.pdf` (۵٫۳ مگابایت)، `docs/plan-android.md` | مالکیتِ روشن نیست (اسنادِ ایجنتِ دیگر/مالک) ⇒ فقط ثبت شد |
| `tools/replace_classify_trend.py`، `tools/test_kline_methods.{js,mts}`، `tools/test_mobile_layout.mts` | اسکریپت‌هایِ دامنهٔ تکنیکال/موبایل؛ کارِ من نیست و بازنگری نشده |
| `_audit/FTS_TREND_COMPARE.csv` و `tools/market_state_probe.mts` (دست‌خورده درِ این worktree) | تغییراتِ **نشستِ موازی**؛ استیج نشد و دست‌نخورده ماند |
| `market.db.baseline*`، `market.db.meta.json` درِ `BorsTerminal-roadmap` | کپیِ بانکِ عملیاتی (داده + حجم) ⇒ هرگز منتشر نمی‌شود |
| نسخۀ ۹٬۸۶۸ بایتیِ `api/execution.py` درِ همان worktree | منتشر شد، ولی به‌عنوانِ **اسنپ‌شاتِ موازی** با برچسبِ تعارض (`handoff/system-1/funnel-wip-execution-copy-2026-10-15`)، نه به‌عنوانِ کدِ درست |

## ۵) همپوشانی و احتمالِ تعارض

- `handoff/system-1/funnel-wip-execution-copy-*` (9,868 B) با `api/execution.py`ِ خطِ اصلی (15,703 B، دروازۀ halt/resume/audit) **تعارضِ متنیِ مستقیم** دارد؛ هرگز merge نشود تا کسی diff نگیرد.
- `github/mission/fts-indicator-engineering` (۱۲ کامیت) با `main` درِ فایل‌هایِ چارت/تعدیل همپوشانی دارد؛ مالکیتش با ایجنتِ تکنیکال است.
- `handoff/system-1/fundamental-browser-wip-*` رویِ `e08dc56` نشسته که خودش ازِ `main` قابلِ دسترسی است؛ diff‌اش (`fts_engine.py` +۱۶) با کارِ تکنیکال همپوشانیِ بالقوه دارد.
- `roadmap-main` (۴۱c00a9) فقط سند است و تعارضی ندارد.

## ۶) صحت‌سنجیِ تحویل

```
git ls-remote --heads github refs/heads/handoff/*
b9a60fc37651…  handoff/system-1/easytrader-2026-10-15
b54f57557acd…  handoff/system-1/fundamental-browser-wip-2026-10-15
41c00a9ed0a7…  handoff/system-1/funnel-roadmap-2026-10-15
b7cbebd03e8a…  handoff/system-1/funnel-wip-execution-copy-2026-10-15
```
- `mission/4-axes-2026-10-10` رویِ ریموت = `b9a60fc37651…` = SHA محلی (برابر، تأییدشده).
- HEAD و dirty-countِ دو worktree دیگر **پیش و پسِ ساختِ اسنپ‌شات‌ها یکی است** (`e08dc56`/۵ مورد، `4540f01`/۱۴ مورد)؛ اسنپ‌شات‌ها با indexِ موقتِ بیرونِ آن worktreeها ساخته شدند.
- `PUSH_BLOCKED`: هیچ. همهٔ pushها موفق بودند.
- این سند رویِ `handoff/system-1/inventory-2026-10-15` هم منتشر می‌شود.

## ۷) گزارشِ امنیت Secret

- الگویِ `(authorization|bearer|api_key|password|cookie|token) = <۸+ نویسه>` رویِ **کلِ diffهایِ نامزدِ انتشار** اجرا شد: **صفر خط**.
- نام‌هایِ پرخطر (`adb_config.json`، `*tauri_updater_key*`، `.setup_password.iss`، `*.pem/.key/.p12`، `*.env`، `credential*`) درِ هیچ worktree کثیفی پیدا نشد.
- مقدارِ هیچ رازی درِ خروجیِ این نشست چاپ نشد (بررسیِ وجودِ متغیرها با `-n` و چاپِ `set/unset`).
- `market.db` و `codal.db` درِ `.gitignore`‌اند؛ کپی‌هایِ بانکِ roadmap عمداً منتشر نشدند.
- سابقهٔ هشدار: درِ نشستِ پیشین یکِ `${TYPESAFE_API_KEY:-no}` مقدارِ کلید را درِ **خروجیِ ابزار** چاپ کرد (نه درِ Git، نه درِ فایل). برایِ پاکسازیِ واقعی لازم است آن کلید درِ سمتِ سرویس rotate شود — این تصمیمِ مالک است و من آن را انجام ندادم.
- درِ تاریخچۀ مخازنِ بررسی‌شدهٔ بیرونی، رمزهایِ صریحِ کامیت‌شده یافت شد (`sajadghandehari/mofid-autotrader` @ `b3f8eab`؛ درِ HEAD حذفش کرده‌اند) — درِ سندِ ماتریس ثبت شده، ربطی به مخزنِ ما ندارد.

## ۸) آزمون‌ها و تاریخِ آخرین اعتبارسنجی

| آزمون | آخرین اجرا | رویِ کدام SHA | نتیجه |
|---|---|---|---|
| `python dev/run_all_tests.py` | ۱۴۰۵-۰۷-۲۳ ~۲۲:۰۴ | `3752ae1`/`edbe6e6` (فقط فرقِ سندی با برچسب) | `ALL SUITES PASSED` exit ۰، «۱۰۲ شمارش‌دار / ۲۹ بی‌شمارش»، صفر FAIL |
| گاردهایِ پس ازِ رفعِ کارایی | ۱۴۰۵-۰۷-۲۴ ~۲۳:۴۰ | `7196c61`+ | mstat_swr ۱۶/۰ · market_hot_state ۵۱/۰ · mstat_local ۲۰۸/۰ · proc_probe ۱۳/۰ · glyph ۴/۰ · pulse_ta_scope سبز |
| `npx tsc -b` / `npx vitest run` / `npm run build` | ۱۴۰۵-۰۷-۲۳ | پیش ازِ رفعِ کارایی | ۰ خطا / ۱٬۶۶۹ سبز، ۵ skip / build ✓ — **برایِ کدِ `7196c61+` تکرار نشده** |
| گیتِ کامل رویِ `7196c61` یا `b9a60fc` | — | — | **انجام نشد** |
| آزمونِ Frozen/Portable برایِ مسیرِ سرخطی | — | — | انجام نشد (آداپتور وجود ندارد) |
| WebView/APK، چرخۀ واقعی کدال، delta زیرِ بارِ بازارِ باز، اتصالِ واقعی EasyTrader | — | — | باقی‌مانده (علت‌ها درِ جدولِ بند ۲) |

## ۹) رأیِ نهاییِ تحویل

`HANDOFF_COMPLETE` برایِ هدفِ این مأموریت: هر کامیتِ منتشرنشده‌ای که درِ این سیستم بود
انتشار یافت (خودیم مستقیم بر شاخهٔ خودی؛ کارِ دیگران فقط به‌عنوانِ ارجاع/اسنپ‌شاتِ مستقل
بدونِ دست‌زدن به HEAD یا indexشان)، هر کارِ نیمه‌تمامی با وضعیتش ثبت شد، و هر چیزی که
عمداً منتشر نشد با علت ثبت شد.

توسعهٔ تازه درِ این مأموریت شروع **نشد**. `main` تغییر نکرد، هیچ merge/cherry-pick ای انجام
نشد، هیچ tag/release ساخته نشد، و هیچ force-push/reset/clean.
