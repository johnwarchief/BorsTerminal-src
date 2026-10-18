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

## ۵) آنچه بی‌تغییر ماند

`main` (محلی `92703183` / `github/main f9cea521`)، `release/1.0.91-strategy-fts`
(`0dc5d0be`)، `mission/broker-connect-ui-2026-10-18` (`ea26f1d7`)،
`mission/uiux-strategy-fts-2026-10-18` (`daf7b8f1`) و همهٔ worktreeهایِ دیگر
دست‌نخورده‌اند. تنها اهرمِ بازگشتِ ساخته‌شده: `integration/system1-2-2026-10-19`
(محلی + `github`) و باندلِ `bors-s12-refs.bundle` (۵٬۳۰۴٬۰۳۶ بایت، ۱۹ ref،
`git bundle verify` سالم).
