# پروندۀ ادغامِ System 2 — چرا ادغامِ خطِ اصلیِ System 2 «حلِّ تعارض» نیست

مرحۀ ۴ مأموریتِ ادغام. هیچ‌چیز درِ این سند حدس نیست: هر سطر ازِ `git merge-tree`،
`git show` و `git cat-file` رویِ SHAهایِ ثبت‌شده درِ §۴ آمده.

مبنایِ ادغام: `integration/system1-2-2026-10-19` = `2a9f3f0f`
(پیش ازِ آن `f6fbfd77`؛ System 1 کامل + سه خطِ پاکِ همسایه ادغام شده و درِ
`github` منتشر شده‌اند).

## ۱) سه خطِ System 2، سه سرنوشتِ متفاوت

| ref | tip | کامیتِ منحصربه‌فرد نسبت باِ `github/main` (`f9cea521`) | ادغام باِ `2a9f3f0f` | نتیجه |
| --- | --- | --- | --- | --- |
| `mission/technical-algorithm-engine` | `60888acc` | ۳ | — | **CLEAN — ادغام شد** (`478aa069`) |
| `mission/qa-full-uiux-perf-2026-10-16` | `402acbfe` | ۳ | — | **CLEAN — ادغام شد** (`c81cadad`) |
| `mission/ui-workstation-redesign-2026-10-15` | `e5570a81` | ۱ | — | **CLEAN — ادغام شد** (`f6fbfd77`) |
| `github/mission/market-status-parity-tradersarena-2026-10-17` | `7d9d0e4f` | ۵ | ۱ تعارض | فقط `docs/AGENT-INDEX.md` (تولیدشدنی) — **حل‌ناشده، بی‌ریسک** |
| `github/mission/system2-perf-market-hours-2026-10-17` | `9594c7ff` | ۶۱ | ۱۸ تعارض / ۳۲ هانک | **مسدود — تصمیمِ مهندسی می‌خواهد (§۲)** |
| `github/mission/ui-audit-system-2-2026-10-15` | `3feb5257` | ۶۶ | ۲۴ تعارض | همان خانواده، پرحاشیه‌تر |
| `github/handoff/system-2/inventory-2026-10-15` | `5f3b0a74` | ۶۱ | ۱۷ تعارض | زیرمجموعۀِ `fts-indicator-engineering` را دارد |
| `github/fix/system-2-reproducible-fixtures-2026-10-15` | `c68dbc0a` | ۵۶ | ۱۷ تعارض | « |
| `github/mission/fts-indicator-engineering` | `ff6b2fb4` | ۵۱ | ۱۷ تعارض | درونِ سه شاخۀِ بالا هست (containment سنجیده شد) |
| `mission/uiux-2-0-redesign-2026-10-16` | `a3984f02` | ۶۶ | ۴۸ تعارض | `api/execution.py` و دو گاردِ execution را **موازیِ** System 1 ساخته (add/add) |
| `integration/uiux-2-0-review-2026-10-16` | `65080701` | ۳ |  تعارض | `TapeTable.tsx` + `AGENT-INDEX.md` — کارِ نمایِ کارتیِ تابلو |

`git merge-base --is-ancestor` برایِ جدولِ بالا اجرا شد؛ نتیجه: زنجیرهٔ System 2
خطی نیست — `system2-perf-market-hours` و `handoff/inventory` و
`fix/reproducible-fixtures` هر سه `fts-indicator-engineering` را دارند، ولی
`ui-audit-system-2` هیچ‌کدام را ندارد و هیچ‌کدام هم او را. پس «یکی ادغام کن،
تمام می‌شود» صادق نیست.

## ۲) چهار تعارضِ واقعی (نه مکانیکی)

### الف) `api/funnel.py` — دو بازسازیِ هم‌زمان رویِ یکِ تابع

| تابع | `github/main` | مبنایِ مشترک (`f5a10166`) | System 1 (خطِ انتشار) | System 2 |
| --- | --- | --- | --- | --- |
| `_run_entry` | ندارد | ندارد | ندارد | **دارد** |
| `_shape` | ندارد | ندارد | ندارد | **دارد** |
| `_funnel_http` | ندارد | ندارد | ندارد | **دارد** |
| `_cache_key` | ندارد | ندارد | ندارد | **دارد** |
| `_run` (بازگشتی) | دارد | دارد | دارد، باِ `tech_chain` + `settings` | **شکسته به سه تابع**؛ `_run` برمی‌گرداند `(payload, ts, built)` |

System 1 پارامترهایِ «تکنیکال‌اول» و «تنظیمِ مستقلِ استراتژی» را به همان `_run`ِ
قدیم افزود (`weekly_mode`، `daily_mode`، `clock_delta_pct`، `tech_chain` +
اعتبارسنجیِ `REG.TECH_BY_ID` و `REG.validate_settings`). System 2 لایۀ
کش/شکلِ پاسخ را جدا کرد (`_shape` برایِ پاسخِ کامل/کاسته + `cached_for_ms`).
**هیچ‌کدام باِ «هر دو طرف را نگه دار» درست نمی‌شود**: امضایِ `_run` و نوعِ
بازگشتش فرق کرده. حلِّ درست = بردنِ پارامترهایِ System 1 درونِ ساختارِ تازهٔ
System 2، و بعد **اثباتِ بی‌جابه‌جاییِ رأی‌ها** (تطبیقِ بدنهٔ `/api/funnel` برایِ
هر preset، پیش و پس) — نه یکِ resolve سه‌خطی.

### ب) `api/market_status.py` — دو طرحِ کارایی برایِ یکِ لایۀِ کش

- System 1: `_mstat_state()` — یکِ پویشِ «حالتِ بانک» درِ هر درخواست، چون ده پنل
  آن را تکرار می‌کردند (سنجشِ درِ کامنت: ~۸–۱۰ms به‌ازای پنل، ترکیبِ بی‌کش ~۱۰۳ms؛
  و پاسخِ ۲٬۵۰ms وقتی ttlِ تب ده پنل را درون‌خطی می‌ساخت).
- System 2: `_mstat_call()` با PERF-S3 — حذفِ اتصالِ دوم (هر `get_db()` ≈ ۴ms؛
  شاهدِ `_audit/perf/SQLITE_CONN_BASELINE.json`) و کشِ نتیجه به‌ازای حالتِ بانک.

این دو **یکِ مشکل را ازِ دو سو** حل می‌کنند و بدنه‌هایِ مشترک را بازنویسی کرده‌اند.
ادغامِ صحیح یعنی اجرایِ دوبارهٔ هر دو سنجش رویِ کدِ واحد؛ وگرنه یکی ازِ دو
بهبودِ اندازه‌گیری‌شده بی‌صدا می‌رود.

### پ) `api/chart.py` — دو **معنایِ متفاوت** برایِ جهتِ موج

```
System 1:  direction = "up" if lo_idx <= hi_idx else "down"      # جایِ نسبیِ دو Extreme
System 2:  direction = "up" if hi_i >= lo_i else "down"          # + provisional: True
```

System 2 پرچمِ `provisional` را افزوده (رأیِ P0 #4 و باگِ «فولاد» #161: موجِ
min/max بی‌پیوتِ فراکتالی «در حالِ تشکیل» است، نه ساختارِ تأییدشده). System 1 هم
دلیلِ خودش را درِ کامنت دارد (پیش از این همین شاخه همیشه `up` می‌داد). این
تصمیمِ **روش‌شناسی** است، نه فنی: رأیِ روند، کمربندهایِ فیبو و سیگنالِ رابط ازِ
همین خوانده می‌شوند. مطابقِ قاعدۀِ مخزن (آستانه و دروازۀ روش رأیِ مالک است) این
را من انتخاب نمی‌کنم.

### ت) `frontend/src/__tests__/design-token-guard.spec.ts` (add/add) و `tones.ts`

هر دو خط یکِ گاردِ «کلاسِ رنگِ بی‌توکن» نوشته‌اند. یکِ نسخه باید بماند وگرنه گارد
دو بار اجرا می‌شود یا بدتر، ضعیف‌ترینِ دو نسخه حاکم می‌شود.

## ۳) چیزهایی که باید حفظ شوند و درِ هیچ ادغامی نیستند

| مورد | کجا | وضعیت | تصمیم |
| --- | --- | --- | --- |
| `TapeCards.tsx` و `tapeColumns.ts` | `integration/uiux-2-0-review-2026-10-16` (کامیت‌شده) + **نسخۀِ تغییرکردهٔ کامیت‌نشده درِ worktree `_bors-uiux-integration`** | کارِ کامیت‌شده قابلِ انتقال است؛ نسخۀِ کامیت‌نشده کارِ نشستِ دیگری است | درِ §۷ سندِ ممیزیِ تابلو به‌صورتِ بسته‌هایِ T‑۱/T‑۲ برنامه‌ریزی شده؛ به‌عنوانِ «ادغامِ فوری» انجام نشد چون باِ `TapeTable`ِ خطِ انتشار (که `MicroBadge`/`tapeRowTone` را جدا کرده) درگیر می‌شود |
| `api/fundamental.py`، `api/screener.py`، `fts_engine.py` (تغییرِ کامیت‌نشده) | worktree `_bors-fund-browser` (detached `e08dc567`) | دست‌نخورده باقی ماند | کارِ نشستِ دیگری است؛ فقط ثبت شد تا گم نشود |
| `tools/ta_def_probe.py` (تغییرِ کامیت‌نشده) | worktree `_bors-ta-parity` | دست‌نخورده | همان |
| `mstat_panels.py` (۷۳۷ سطرِ تازه) + `StatusShell`/`MarketTreemap`/`MarketGlanceCards`/`RankedPanels`/`OrderOwnershipSection`/`Sparkline` | فقط درِ `github/mission/system2-perf-market-hours-2026-10-17` | درِ `github/main` و درِ `2a9f3f0f` **نیست** | باِ همان خط ادغام می‌شود؛ مشکل فقط چهار فایلِ مشترکِ §۲ است، نه این فایل‌ها |
| `mission/system2-chart-parity-engine1-2026-10-18` | **وجود ندارد** | `git ls-remote --heads github` تنها `mission/system2-perf-market-hours-2026-10-17` را نشان می‌دهد؛ درِ `git for-each-ref` محلی هم هیچ refِ هم‌نامِ «chart-parity/engine1» نیست | نامِ شاخه درِ دستورِ مأموریت باِ مخزن نمی‌خواند؛ کارِ پاریتیِ چارت درِ `mission/technical-algorithm-engine` و `mission/market-status-parity-tradersarena-2026-10-17` دیده شد و آن اولی ادغام شد |

## ۴) مسیرِ رفعِ مانع (به ترتیبِ وابستگی)

1. **دو رأیِ مالک** لازم است: (الف) جهتِ موج و `provisional` (§۲‑پ) کدام باشد؛
   (ب) لایۀِ کشِ `market_status` کدام طرح را نگه دارد (§۲‑ب). بدونِ این دو، هر
   انتخابی یکِ بهبودِ اندازه‌گیری‌شده را بی‌صدا می‌سوزاند.
2. `api/funnel.py`: پارامترهایِ System 1 (`tech_chain`، `weekly_mode`،
   `daily_mode`، `clock_delta_pct`) به ساختارِ `_run_entry`/`_shape` منتقل شوند؛
   سپس **تطبیقِ بدنهٔ `/api/funnel`** برایِ هر پنج preset و هر دو منطقِ
   اشتراک/اجتماع، پیش و پس ازِ تغییر (این همان چیزی است که مالک «عددِ رأی باید
   ثابت بماند» می‌خواند).
3. `design-token-guard.spec.ts`: یکی ازِ دو نسخه بماند (نسخۀِ System 2 کامل‌تر
   به‌نظر می‌رسد چون گارد را درِ `run_all_tests` ثبت کرده) — باِ شاهدِ diff.
4. سپس ادغامِ `9594c7ff` (کلِ System 2: وضعیتِ بازار + موتورِ تعدیل + کاتالوگِ
   اندیکاتور) و بعد `7d9d0e4f` (پاریتیِ TradersArena) و درِ آخر `65080701`
   (نمایِ کارتیِ تابلو).
5. هر مرحله باِ `git merge-tree --write-tree` پیش‌سنجیده شود و تعارض‌ها باِ نامِ
   فایل و تصمیم درِ همین سند افزوده شوند.

## ۴-الف) رأی‌های مالک (۲۰۲۶-۱۰-۱۹) — تصمیمِ هر ۱۸ فایل

**رأیِ ۱ — `api/chart.py`:** جهتِ موجِ System 1 می‌ماند
(`direction = "up" if lo_idx <= hi_idx else "down"`) و `provisional: True` ازِ
System 2 افزوده می‌شود. هیچ رأیِ FTS یا کمربندِ فیبو بی‌اجازه جابه‌جا نمی‌شود.
تست‌هایِ لازم: موجِ موقت (بی‌پیوتِ فراکتالی)، موجِ تأییدشده، دادهٔ ناکافی،
نقطۀِ مرزیِ `hi == lo`، و یکِ آزمونِ برابریِ رأیِ FTS پیش/پس ازِ افزودنِ پرچم.

**رأیِ ۲ — `api/market_status.py`:** گزینهٔ C. «یکِ پویشِ حالتِ بانک درِ هر
درخواست»ِ System 1 حفظ می‌شود (ده پنل ازِ تکرارِ پویش نجات می‌یابد) و
«یکِ اتصال برایِ نشانک + پنل»ِ System 2 (PERF-S3) رویش سوار می‌شود. مبنایِ
تصمیم، اعدادِ خودِ System 2 است: سه حالت (S1 / S2 / ترکیب) باِ ورودیِ یکسان
باِ p50/p95/p99، شمارِ اتصال‌ها، محاسبۀِ تکراری، همزمانی، invalidation، تازگی و
برابریِ بدنهٔ پاسخ سنجیده می‌شوند. اگر ترکیب برتریِ S2 را نگه ندارد، اصلاح و
دوباره سنجیده می‌شود — بی‌عدد، برتری ادعا نمی‌شود.

| فایل | تصمیم |
| --- | --- |
| `api/__init__.py` | اتحادِ فهرست: `market_index, diagnostics, execution, bot, structure3` + هر دو کامنتِ توضیحی |
| `dev/run_all_tests.py` | ours (شمارش ازِ `dev/guard_counts.summarize`) و **انتقالِ چهار الگویِ شمارشِ System 2 بهِ خودِ `guard_counts.py`** (`N/M passed`، «N بررسی سبز، M شکست»، «N سبز، M قرمز»، `N_pass / M_fail`) — وگرنه گاردِ «شمارشِ واقعی» دوباره سکوت را سبز می‌خواند |
| `docs/README.md` | اتحادِ سه سطرِ جدولِ research (TECH-FIRST، RAHAVARD-CANDLE-ADJUSTMENT-PARITY، TECHNICAL-RAHAVARD-PARITY-AUDIT) |
| `fts_terminal.spec` | اتحادِ `hiddenimports` (جاافتادن = `ModuleNotFoundError` درِ EXE) |
| `design-token-guard.spec.ts` | **گارد حفظ می‌شود** (نسخۀ کامل‌تر + ثبتِ درِ `run_all_tests`). حذفِ گارد مجاز نیست |
| `market/lib/tones.ts` | ترکیب باِ **بازگشت بهِ توکن** (`text-tone-pos` …)؛ اگر کلاسِ System 2 گارد را می‌شکند، کلاس اصلاح می‌شود نه گارد |
| `api/funnel.py` | ساختارِ theirs (`_run_entry`/`_shape`/`_funnel_http`/`_cache_key`) + پارامترهایِ ours (`tech_chain`، `weekly_mode`، `daily_mode`، `clock_delta_pct`، `REG.TECH_BY_ID`، `REG.validate_settings`). **کلیدِ کش باید `tech_chain`/`settings` را هم ببرد.** معیارِ پذیرش: تطبیقِ بدنهٔ `/api/funnel` برایِ پنج preset × دو منطقِ اشتراک/اجتماع پیش و پس، باِ ثبتِ اعداد |
| `api/market_status.py` / `api/chart.py` | §۴-الف بالا |
| `technical-feed.spec.tsx`، `technical-pattern-wiring.spec.tsx` | theirs، سپس Vitestِ کامل؛ اگر باِ `provisional` درافتادند، **تست اصلاح می‌شود، نه حذف** |
| `MarketStatusPage.tsx`، `FtsStatusCard.tsx`، `useFtsAnalysis.ts`، `patternOverlays.ts`، `SymbolInspector.tsx`، `FtsFunnelAllStages.tsx`، `FtsCustomChainBuilder.tsx` | theirs برایِ ویژگی‌هایِ تازه، باِ حفظِ هر سطرِ رابطیِ System 1؛ دو قید: هیچ کلاسِ رنگِ تازه بی‌توکنِ موجود درِ `tokens.css`، و پلکانِ چهارسطریِ اتصالِ سرخطی دست‌نخورده |

**ترتیبِ اجرا:** (۰) این سند کامیت و push شود — **پیش ازِ هر تلاشِ ادغام**، چون
`git merge --abort` تغییراتِ حل‌نشدهٔ همین فایل را هم برگرداند (تجربۀِ همین
جلسه). (۱) `git merge --no-ff github/mission/system2-perf-market-hours-2026-10-17`
(۲) چهار فایلِ اتحادِ ساده (۳) `chart.py` + تست (۴) `funnel.py` + تطبیقِ پنج
preset × دو منطق (۵) `market_status.py` + بنچمارکِ سه‌حالته (۶) `tones.ts` +
گاردِ توکن (۷) هفت فایلِ فرانت → `tsc -b` + `eslint src` +
`vitest run --maxWorkers=2` (۸) `dev/run_all_tests.py` باِ
`npm_config_allow_scripts` پاک‌شده + `dev/version_anchor_guard.py`
(۹) ادغامِ `7d9d0e4f` و `65080701` (تعارضشان فقط `AGENT-INDEX.md` تولیدشدنی و
`TapeTable.tsx` است) (۱۰) bumpِ ششِ لنگرۀِ نسخه → fast-forwardِ `main` (بی‌force)
→ تگ → بیلدِ CI ازِ همان تگ → تستِ خودِ بسته → انتشار درِ کانالِ پایدار.

**یادآوریِ محیط (تا قرمزِ جعلی تکرار نشود):** درِ worktree تازه `npm ci` باید باِ
`npm_config_allow_scripts= npm ci` اجرا شود و وجودِ `node_modules/vitest`
بررسی شود؛ و گاردهایِ نماد→کارگزاری به `market.db` **هم‌سازی‌شده** نیاز دارند
(۶٬۰۱۸ نماد، نه ۵٬۲۹۶ِ baseline) وگرنه `p0_gates` چهار `NOT_ORDERABLE`ِ دروغین
می‌دهد.

## ۵) آنچه بی‌تغییر ماند

`main` (محلی `92703183` / `github/main f9cea521`)، `release/1.0.91-strategy-fts`
(`0dc5d0be`)، `mission/broker-connect-ui-2026-10-18` (`ea26f1d7`)،
`mission/uiux-strategy-fts-2026-10-18` (`daf7b8f1`) و همهٔ worktreeهایِ دیگر
دست‌نخورده‌اند. تنها اهرمِ بازگشتِ ساخته‌شده: `integration/system1-2-2026-10-19`
(محلی + `github`) و باندلِ `bors-s12-refs.bundle` (۵٬۳۰۴٬۰۳۶ بایت، ۱۹ ref،
`git bundle verify` سالم).


## ۵-الف) مبنایِ رأیِ قیف — ثبت‌شده پیش ازِ هر تلاشِ ادغام (۲۰۲۶-۰۱:۰۱)

`tools/funnel_verdict_baseline.py` (تازۀِ همین مرحلۀِ ادغام) چهلِ حالت را درون‌فرآیندی
ازِ `api.funnel._run` می‌خواند: پنج preset × دو منطقِ اشتراک/اجتماع، سه زنجیرۀ
دستیِ تابلو، چهار زنجیرۀ فیلترِ تکنیکال، چهار تنظیمِ مستقلِ «تکنیکال اول»، سه
حالتِ بنیادی، دو حالتِ `drop_suffix`، یکِ `params`+`exceptions`، و شش خطایِ
اعتبارسنجی. `as_of`/`cached_for_ms`/`timeline` ازِ هش بیرون‌اند؛ `start_refresh`
رشتهٔ پس‌زمینه خاموش می‌ماند تا دو اجرا رویِ یکِ داده مقایسه شوند (شمارۀ
`pending_symbols` همچنان ثبت می‌شود).

**خودِ سنجش قبل ازِ استفاده سنجیده شد** (بی‌این، «صفر جابه‌جایی» بی‌معیار است):

| CONTROL | نتیجه |
| --- | --- |
| دو اجرایِ پیاپی درِ یکِ کد (`pre` ↔ `pre2`) | ۴۰/۴۰ هشِ یکسان → قطعی |
| آستانۀ کذایی: `logic` درِ `api/funnel.py` به «and» قفل شد (`ruleset_version` دست‌نخورده) | ۶ حالت جابه‌جا، دقیقاً شش `__or`؛ ۳۴ حالتِ دیگر یکسان → حساس درِ سطحِ رأی، نه فقط درِ مهرِ نسخه |
| بازگردانی ازِ copy و اجرایِ سوم | دوباره ۴۰/۴۰ یکسان باِ `pre` |

مبنایِ زمینه: `instruments=6018`، `tape_history=145516`، نشستِ `20261014`. هر
مقایسۀِ پیش/پس که این دو عدد را نبیند، بی‌اعتبار است (`--compare` خودش هشدار
می‌دهد).

| حالت | digest | status |
| --- | --- | --- |
| `swing__and` | `086873426362d5b2` | success |
| `swing__or` | `acd20ca1753be42d` | success |
| `trend__and` | `2eb9c4f6e46f5063` | success |
| `trend__or` | `340d07623cb7dc9d` | success |
| `hourglass__and` | `f0bf811aac266230` | success |
| `hourglass__or` | `f0bf811aac266230` | success |
| `tech_first__and` | `eac186c5f56fb3c2` | success |
| `tech_first__or` | `eac186c5f56fb3c2` | success |
| `custom__and` | `b270b8c92c40fcd7` | success |
| `custom__or` | `b270b8c92c40fcd7` | success |
| `custom_chain0__and` | `985506f04f091ab3` | success |
| `custom_chain0__or` | `0f0224e4957d5255` | success |
| `custom_chain1__and` | `4c2d495f00d8fa0c` | success |
| `custom_chain1__or` | `cd1910eb5f75c3a6` | success |
| `custom_chain2__and` | `da42ebf1460eb07e` | success |
| `custom_chain2__or` | `a1d632d9c3d2c233` | success |
| `tech_weekly_up__and` | `22135ee77051d78b` | success |
| `tech_weekly_up__or` | `22135ee77051d78b` | success |
| `tech_weekly_up_daily_up__and` | `c23f583792995831` | success |
| `tech_weekly_up_daily_up__or` | `c23f583792995831` | success |
| `tech_setup_jet_risk_divergence__and` | `a1f5b00baeb942c0` | success |
| `tech_setup_jet_risk_divergence__or` | `a1f5b00baeb942c0` | success |
| `tech_hourglass_accelerate__and` | `0acaa8cf1230781a` | success |
| `tech_hourglass_accelerate__or` | `0acaa8cf1230781a` | success |
| `set_weekly_mode=require_up` | `d662a69006a1f2fe` | success |
| `set_daily_mode=require_up_weekly_mode=reject_down` | `cc8bd37b64abbe9d` | success |
| `set_clock_delta_pct=2_daily_mode=require_up` | `60afc3c71cbdcd92` | success |
| `set_clock_delta_pct=2` | `8dd04e22f29f69ca` | success |
| `fund_hard__trend` | `db9e34c6a2d20892` | success |
| `fund_standard__trend` | `2eb9c4f6e46f5063` | success |
| `fund_exception__trend` | `54bd04d4263db5e9` | success |
| `keep_suffix__swing` | `a6baf99709a347b2` | success |
| `keep_suffix__trend` | `2df67e74fe26e194` | success |
| `params__custom` | `7e35355a8fd253fe` | success |
| `err_unknown_preset` | `1b028d43d4ce8264` | error |
| `err_unknown_logic` | `ce7d059ed95f4ff0` | error |
| `err_unknown_tech` | `ebda5d5bb4b0cb2f` | error |
| `err_unknown_setting_key` | `6eb414a48fc1a44c` | error |
| `err_unknown_setting_value` | `d48d7cbeaec2b0cf` | error |
| `err_unknown_fund_mode` | `ff6f378dec848be7` | error |

sha: 245eea4768f5e7502348649db70b9f36d3532220 | context: {"instruments": 6018, "tape_history": 145516}

معيارِ پذیرشِ حلِّ `api/funnel.py`: `--compare pre post` باید صفرِ جابه‌جایی بدهد، یا هر جابه‌جاییِ باقی‌مانده توضیحِ طرح‌دار درِ همین سند داشته باشد.
