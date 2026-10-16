# P0 — فهرستِ مسیرهای «بدون داده / ناکافی / سنجیده نشده» — ممیزیِ ۱۴۰۵-۰۷-۱۹

مأموریت: ریشه‌یابیِ سیستماتیکِ وضعیت‌های مبهم در کلِ برنامه (پیوستِ مالک، ۱۲ بخش).
این سند نتیجۀ گامِ ۱ (فهرستِ کاملِ مسیرها) است؛ گامِ ۲ (خطِ پایهٔ کمی) در
`_audit/p0_nodata_baseline.json` و گامِ ۳ (ریشه‌یابی و اصلاح) پس از آن می‌آید.
هر سه فهرست‌سازی با ایجنت‌های فقط‌خواندنی انجام شد؛ هیچ کدی اینجا تغییر نکرده است.
ارقام لاتین عمدی است (قراردادِ گزارش‌های نشست).

## قراردادِ ۸ حالت (از بریفِ مالک)

| حالت | معنا |
|---|---|
| available | داده معتبر است و محاسبه موفق |
| not_evaluated | محاسبه واقعاً اجرا نشده — علت باید معلوم شود |
| missing_data | ورودیِ موردنیاز وجود ندارد |
| insufficient_history | تاریخچه هست ولی برای محاسبهٔ معتبر کافی نیست |
| source_error | دریافت از منبع شکست خورده یا پاسخ نامعتبر |
| stale_data | داده هست ولی برای ادعای فعلی کهنه است |
| invalid_data | داده هست ولی ساختاراً/اعتباری قابل‌استفاده نیست |
| not_applicable | آن محاسبه برای این مورد طبق تعریف کاربرد ندارد |

قاعدۀ طلایی بریف: این سه با هم یکی نیستند — `not_evaluated` ≠ `missing_data` ≠
`insufficient_history`. و هیچ‌وقت مقدار ساختگی/صفر جایِ «نامعلوم» گذاشته نمی‌شود.

## ۱) بک‌اند — ~۹۰ مسیر

### خوشه‌های با تفکیکِ خوب (الگوی مثبت)

| ناحیه | مسیر | تفکیک |
|---|---|---|
| بنیادی | `ind1a` ۳ علت + remediation | available / insufficient / missing جدا |
| بنیادی | `gap_report` | علت‌مند |
| بنیادی | mcap ۴ دلیل | علت‌مند |
| تکنیکال موتور ۳ | `TECH_NO_HISTORY` / `TECH_SCAN_PENDING` / `TECH_UNMEASURED` | جدا |

### خوشه‌های بدونِ تفکیک (بدترین‌ها)

| مسیر | وضعیتِ تولیدی | اشکال |
|---|---|---|
| `mstat_engine.py:1088` | یک پیام برای ۳ علت | منبع/بازه/پوشش قاطی |
| `mstat_engine.py:1218` `_liq_side` | «بدون داده» تخت | — |
| `mstat_engine.py:1470` `day_verdict` | «بدون داده» تخت | — |
| `mstat_engine.py:1576` `_clock_window` | «بدون داده» تخت | — |
| `api/market.py:1478, :43, :234` | `{"status":"error","message":"بدون داده"}` عمومی | علت در پیام نیست |
| `api/chart.py` FTS status | `insufficient` تک‌حالته | not_evaluated هم همان می‌شود |

### ۸ مسیرِ مشکوک «داده هست ولی ریزش می‌کند» — نامزدِ ریشه‌یابیِ عمیق

| # | مسیر | ظن |
|---|---|---|
| B1 | `tape_flags.py:107-116` `plp_series` | گارد روی `percent_last`ِ NaN مقدارِ واقعی را هم می‌اندازد → فیلتر بی‌داده؛ شاهد: طملت8068/طتاص9019 |
| B2 | `api/market.py:980-994` | ستونِ `market_cap`/`allowed_min` نیست → `CAST(NULL AS REAL)` مخرجِ mcap+I4 را می‌کشد |
| B3 | `api/market.py:986` | گاندِ `(1=0)` برای unknown-band — no-opِ نامرئی |
| B4 | `api/chart.py:818-824` | dedupِ حجم ردیف می‌اندازد |
| B5 | `fts_engine.py:433-471` | وقتی `fts_results` None است fallbackِ زندهٔ بی‌صدا |
| B6 | `mstat_engine.py:1088` | ۳ علت یک پیام |
| B7 | `client_type` پوشش | `f_smart`/`f_legal` سقفشان پوششِ client_type است (۱۵۹۳ در نشستِ ۲۰۲۶۱۰۱۰) — not_applicable در برابر missing باید جدا شود |
| B8 | `test_tsetmc.py` پنجرۀ بودجهٔ CTV | **رفع‌شده امروز** (`ebddaf0`) — نسخۀ نصبی هنوز ۱٫۰٫۸۶ است و پنجرهٔ منجمد را دارد |

## ۲) فرانت‌اند — ~۱۵۰ جا

### خوشه‌ها

| خوشه | اعضا | وضعیت |
|---|---|---|
| سلولِ «—» | FtsFunnelAllStages, FtsScreenTable, StrategyStageCandidateTable, MasterDossier/MasterFtsDetails, WatchTable/WatchSummaryPanel, MarketPulseBar, MarketStatusTables/Ticker, SymbolInspector | مقدارِ null/undefined → «—» بدونِ علت |
| «بدون داده» | TwinDonuts, DeltaBar, useStopLossBoard NO_STOP, TradePlanCard/Blueprint, MasterVerdictCard, AgentMatrix | همین |
| enum `nodata` | — | همین |
| «نامعلوم» وضعیت بازار | — | همین |

### نگاشت‌های مشکوک (falsy به‌جای null، صفرِ ساختگی)

| # | مسیر | ظن |
|---|---|---|
| F1 | `SymbolInspector.tsx:480,487,494` | `p_first/p_max/p_min`ِ صفرِ معتبر → «—»؛ صفرِ واقعی با مفقود قاطی |
| F2 | `SymbolInspector.tsx:545` | mcap صفر → «بی‌داده» |
| F3 | `FtsFunnelAllStages.tsx:945` | falsy به‌جای null |
| F4 | `MasterDossier.tsx:161` | jetAth undefined → «خیر» (ساختگی) |
| F5 | `useNnData.ts:47`, `adjustments.ts:73`, `targetAllocation.ts:59`, `MarketStatusPanel.tsx:203` | `??0` — صفرِ ساختگی |
| F6 | `MarketStatusPanel.tsx:116` | حدسِ محلی `market_open ?? isMarketOpen(now)` |
| F7 | `tapeAlgorithms.ts:388,411`, `MarketPage.tsx:45` | truthiness روی کلیدِ داینامیک |
| F8 | `funnelView.ts:154,166` | `as unknown as` — ساختنِ سطرِ ساختگی |
| F9 | `normalizeFa` | identity-join جا می‌اندازد |

## ۳) موتورهای تکنیکال — حدِ کندلِ هر اندیکاتور

| اندیکاتور | حدِ کندل (کد) | حد (frontend) | نکته |
|---|---|---|---|
| RSI14 | ۱۶ chart / ۱۵ CE / ۱۵ frontend | — | **ناهماهنگ** — باید یکی شود |
| key-levels / patterns | ۶۰ | ۶۰ | — |
| jet | ۶۰ | ۶۰ | رأیِ مالک: کفِ ۶۰ |
| hourglass MA52 | ۵۲ weekly | ۵۲ | — |
| exit L3 / L4 | ۱۵ / ۳۰ | — | — |
| conf_tech | ۴۰ + پیامِ «%d < %d» با تعداد | — | **الگوی مثبت** — همان را همه جا تعمیم بده |
| fib zones | <۸ کندل | — | **بی‌صدا به min/max degrade می‌شود** — از موجِ بالغ قابل‌تمایز نیست |
| exit L1 | ۳ کندل «swing_low» | — | **با اقتدارِ کامل منتشر می‌شود** — باید «در حال تشکیل» باشد |
| `_daily_setups` | کلیدها بی‌صدا ناپدید می‌شوند | — | — |
| `MIN_WEEKLY=8` | ثابتِ مرده | — | — |
| `_fts_setup_history` | `[]`ِ بی‌صدا | — | — |
| frontend FtsStatusCard | — | PENDING با INSUFFICIENT قاطی | — |

## قاعدۀ FTS مالک (از بریف)

تأخیرِ تأیید سقف/کف ≠ کمبود داده. الگوی «در حال تشکیل» وضعیتِ متمایز است و
باید در UI هم متمایز دیده شود (FtsStatusCard الان قاطی می‌کند).

## گامِ بعد

`_audit/p0_nodata_baseline.json` — سنجشِ خطِ پایه به تفکیکِ پنج ناحیه
(تابلو/فیلترها، قیف، بنیادی، تکنیکال، وضعیت بازار) + CTV که امروز بسته شد
(۶۰۰→۱۷۲۴ = ۷۲٫۰۱٪، سقفِ منبع ≈۷۵٪).
