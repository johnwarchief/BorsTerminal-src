# نگاشتِ الگوریتم‌های تکنیکال → مرجع → مصرف → آزمون (مرحلۀ ۳)

تاریخ: ۱۴۰۵-۰۷-۲۰ (۲۰۲۶-۱۰-۱۲). شاخه: `mission/fts-indicator-engineering`.
این سند «موجودِ الگوریتم‌ها» و «ماتریسِ هشت‌شرطی» را ثبت می‌کند؛ قواعدِ مرجع در
`docs/FTS-RULE-ALGORITHM-MAP.md` است و ارجاع‌های آن سند را خودِ گاردِ
`dev/test_rule_map_citations.py` می‌سنجد. هر خانه‌ای که سنجیده **نشده** با همان
عنوان می‌آید (دستورِ مرحلۀ ۹: از ادعای کلیِ تطبیق برای موارد آزمون‌نشده پرهیز شود).

---

## ۱) هشت شرطِ مرحلۀ ۳ و معنای عملیِ آن‌ها در این مخزن

| # | شرط | شاهدی که پذیرفته می‌شود |
|---|---|---|
| ۱ | ورودیِ درست | سری/TF/مبنایِ واقعیِ ورودی درِ کد (نه حدس) + آزمونی که ورودیِ غلط را رد کند |
| ۲ | فرمول با تعریفِ مرجع یکی باشد | سطرِ `FTS-RULE-ALGORITHM-MAP.md` + ثابتِ عددی در آزمون |
| ۳ | دادهٔ ناکافی درست تفکیک شود | سه‌حالته (`None` ≠ `False`) + پیامِ «چرا نه» با شمار |
| ۴ | خروجی درِ همان نماد+TF مصرف شود | فایل:سطرِ مصرف‌کنندهٔ فرانت/مستر |
| ۵ | درست رسم شود | فایل:سطرِ overlay + لایۀ رجیسترشده در کاتالوگ |
| ۶ | پس از تغییرِ نماد/TF/مبنا نتیجهٔ کهنه نماند | کلیدِ کش + گاردِ «دو مبنایِ متفاوت، دو نتیجه» |
| ۷ | دادهٔ آینده نبیند | `confirm_idx`/anti-repaint + پیشوند-پایداریِ آزموده‌شده |
| ۸ | آزمونی که خطای واقعی را آشکار کند | سوئیتِ ثبت‌شده در `dev/run_all_tests.py` + کنترلِ منفی |

---

## ۲) موتورِ ۱ — `api/chart.py` (رأیِ رسمی، `/api/fts/{symbol}`)

سطرهایِ `def` درِ این دور دوباره خوانده شدند (grep)؛ جدول زیر «کجا» را می‌برد،
«چه قاعده‌ای» را از نگاشتِ قواعد می‌گیرد:

| تابع (سطر) | قاعدۀ مرجع (map) | مصرف‌کنندهٔ خروجی (فرانت) | آزمونِ مستقیم |
|---|---|---|---|
| `_fts_swings` (1719) | روند ساختاری؛ پیوت k=3/k=2 | پایهٔ همهٔ لایه‌های ساختاری | `dev/fts_antirepaint_v1086.py`، `dev/test_fts_untested_paths_v1.py`، ۱۳ فایل دیگر |
| `_fts_structure_points` (1768) | HH/HL/LH/LL (جزوه ص۷) | `patternOverlays.ts:216`، `engineFtsLayers.ts:215`، `ftsLayerEvidence.ts:118` — فقط `.D` | `dev/test_fts_untested_paths_v1.py`، `fts_antirepaint_v1086.py` |
| `_fts_classify_trend` (1854) | رأیِ روند + تلورانسِ ۰٫۵٪ | `trend.matrix` → پنل/بنر/قیف | `fts_trend_fixtures_v1075.py`، `fts_trend_staleness_v1064.py`، `test_fts_technical_tristate.py` … ۸ فایل |
| `_fts_recent_window_trend` (1814) | رأیِ بازهٔ کهنه (پایلوت گزینه B) | از همان `trend` خوانده می‌شود | ترانزیتیو (از `fts_trend_staleness_v1064.py`؛ بی‌ارجاعِ نامی) |
| `_fts_jet_setup` (2224) | جت (رأی #17) | `jet` → لایۀ `jet` + مارکرِ کندلِ آخر | `test_fts_roundj.py`، `test_fts_technical_tristate.py`، `test_trend_engine_flag.py` … ۸ فایل |
| `_fts_fib_zones`/`_fts_fib_retrace` (2178 / 2165) | کمربندها و پل‌ها (ص۹، ص۲۱) | `fib` → لایه‌های `fib-belt-*`، `fib-levels` | `fts_chart_engine_v1037.py`، `fts_engine_honesty_v1066.py`، `engine_change_impact_v1066.py` (retrace ترانزیتیو) |
| `_fts_choch*` | CHoCH (دوکندلی = اجرای فعلی، canonical نه) | `choch` → لایۀ `choch` | `test_fts_technical_tristate.py` |
| `_fts_point_hunt` | نقطه‌زنی کفِ سوم/پنجم | `point_hunt` → لایۀ `point-hunt` | `test_fts_roundj.py`، `test_fts_technical_tristate.py` … ۵ فایل |
| `_fts_double_bottom` + `range_box` | کف/سقف دوقلو؛ باکسِ رنج | `double_bottom` → لایۀ `double-bottom`؛ `range_box` → **فقط بج/پنل** (`FtsBadgeStrip.tsx:170`، `FtsTrendPanel.tsx:36`، `technicalSignals.ts:187,258`) | `test_fts_technical_tristate.py` (تنها ارجاع) |
| `_fts_pullback_setup` (2568) | پولبک (جزوه ص۸-۹) | `pullback` → لایۀ `pullback` (`ftsIndicatorCatalog.ts:126`) | **این دور اضافه شد** — `dev/test_fts_untested_paths_v1.py` (پیش‌تر صفر) |
| `_fts_exit_layer1..4` + `_fts_exit_engine` (3135) | SL نوسانگیر؛ خروج MA14؛ سقف سوم؛ واگرایی RSI | `l1` و `l3` در `engineFtsLayers.ts:173-183`؛ `verdict`/`l1` در `masterDossier.ts:180-193`، `useStopLossBoard.ts:119`؛ `l4.rsi`/`l4.rsi_divergence` در `FtsTrendPanel.tsx:202` و `technicalSignals.ts:133` | `test_fts_roundj.py`، `fts_engine_honesty_v1066.py`، `engine_change_impact_v1066.py` |
| `_fts_hourglass_settings` + مسیرِ ساعت شنی | ساعت شنی (رأی #24) | `hourglass` → لایۀ `hourglass` | `test_hourglass_settings_v1.py`، `test_roundm_freeze.py` |
| `_fts_resample` / `_fts_scaled` / `_fts_ma` / `_fts_rsi` | TFهای_mix، مبنایِ تعدیل، MA/RSI | overlayهای MA و پان RSI | `indicator_math_v1074.py`، `ce_weekly_bucket_v1073.py`، `price_basis_v1070.py`، `fts_series_basis_v1036.py` |
| `_fts_roles_table` (3026) / `_fts_status_block` | جدولِ نقش (رأی #15/#16) | `patternOverlays.ts:223,257`؛ بنرِ وضعیت | ترانزیتیو از `test_fts_roundj.py`/`test_fts_technical_tristate.py` |
| `_swing_extremes`/`_merge_levels`/`_order_blocks`/`_key_levels_from_history` (924/947/964/1001) | سطوح MA100/حمایت-مقاومت (ص۲۳، ص۳۴) | `/api/chart/{symbol}/key-levels` → `SidebarActiveLevels`/تِبِ مستر | **این دور اضافه شد** — `dev/test_fts_untested_paths_v1.py` (پیش‌تر صفر) |
| `_candles_upto_asof` (3573) / `_fts_analysis_cache_key` (3586) / `_fts_analyze_symbol` (3605) | as-of/anti-lookahead + هویتِ کش | `/api/fts/{symbol}`، `/api/structure3` (گیتِ هفتگیِ تاریخی) | `test_fts_asof_cutoff.py` (۱۷/۱۷)، `test_trend_engine_flag.py`، `fts_cache_basis_v1078.py` |
| `_fts_fa` (1990) | قاعدۀ سراسریِ رقمِ فارسی | متنِ پیام‌ها | ترانزیتیو؛ بی‌آزمونِ نامی (رشتۀ صرفِ UI) |

### یافتِ F-1 — پیوتِ «تساویِ دوطرفه» با docstringِ خودش نمی‌خواند (رفع شد)

* **اختلاف:** `_fts_swings` می‌گوید «و اکیداً بزرگ‌تر از یک طرف»، ولی کد `hi >= max(چپ) و hi >= max(راست)` را می‌پذیرفت ⇒ هر سطرِ داخلِ یک فلاتِ صاف «سقفِ تأییدشده» بود (سریِ کاملاً تخت: ۱۲ سقف + ۱۲ کف از هیچ).
* **علتِ ریشه‌ای درِ داده:** `فولاد` از ۴۲۴۲ سطر، **۱۲۷۸ سطر (۳۰٪) با `high == low`** دارد (نمونۀ واقعی: `2026-10-06` ⇒ o=h=l=c=۳۸۸۰ با حجم ۲٬۳۶۵٬۸۶۷٬۳۳۵). نقصِ خودِ TSETMC است و در `_parse_tsetmc_csv` مستند شده؛ حذفِ آن ردیف‌ها مجاز نبود، پس قاعدۀ fractal باید اکید می‌شد.
* **اندازۀ اثر رویِ داوری (۹ نمادِ واقعی، قاعدۀ اکید به‌صورت monkeypatch):** شمارِ پیوت `فولاد ۳۲۱۴→۸۴۳`، `خودرو ۵۵۶۱→۸۸۴`، `شبهرن ۳۲۹۸→۱۱۰۹`، `وبملت ۳۳۶۵→۶۳۹`، `شپنا ۱۸۷۸→۷۰۰`، `ولانا ۳۴۴→۳۱۶`، `تكنار ۴۲۶→۴۱۷`، `غکورش ۲۰۳→۲۰۱`، `زنجان ۶۳۴→۵۹۲`؛ **کلیدهای داوری (`trend.D/W`, `jet`, `choch`, `point_hunt`, `double_bottom`, `range_box`, `pullback`, `fib`, `hourglass`) در همه بایت‌به‌بایت یکسان** ⇒ این تغییر فقط لایۀ *ترسیم* (ساختار پیوت) را تمیز می‌کند.
* **اندازۀ اثر رویِ سری‌های مصنوع (این دور):** شش حالت (`saw-40/60/80/120`، `flat30+120`، `flat-120`) ⇒ بی‌تغییریِ رأی در پنج حالت؛ تنها `flat-120` (سریِ کاملاً تخت) رأی را جابه‌جا کرد، و آن هم از «رأیِ ساختگی روی ۲۲۸ پیوتِ بی‌معنا» به «بی‌ساختار» — یعنی همان چیزی که مرجع می‌خواهد. بازتولید: `PYTHONIOENCODING=utf-8 python _audit/pivot_strict_probe.py` (خروجیِ این دور: `7→7`, `9→9`, `13→13`, `24→24`, `77→27`, `228→0`).
* **قیمت‌هایِ مطلقِ شاهد:** فلاتِ سه‌کندلیِ [۱۰۰,۱۰۵,۱۱۰,۱۱۵,**۱۲۰,۱۲۰,۱۲۰**,۱۱۵,…] ⇒ پیوت‌هایِ `[4, 6]` (دو سر)، بی‌`[5]` (میانی).
* **اثرِ جانبیِ مستند:** شمارۀ قواعد `FTS_TECH_RULESET_VERSION` از `"4"` به `"5"` رسید تا هیچ کشِ rulebookِ کهنه‌ای پاسخِ فعلی را جواب ندهد؛ گاردِ `dev/test_structure3_engine.py` هم از snapshotِ عددِ ثابت به «مقایسۀ پیش/پس از دو فراخوانِ موتورِ سوم» تغییر کرد (نسخۀ قواعدِ رسمی باید توسطِ موتورِ ۳ عوض **ن**شود؛ عوض‌کردنش توسطِ مرحلۀ ۳ عمدی است و گاردِ شمارهٔ ثابت، bumpِ قانونی را «شکست» می‌گفت).

### دایرۀ ریاضِ اندیکаторها (MA/EMA/RSI/ATR/MACD که مرحلۀ ۳ نام می‌برد)

* MA/EMA/RSI: درِ موتورِ ۱ خودمان حساب می‌شوند (`_fts_ma`/`_fts_rsi`) و با `dev/indicator_math_v1074.py` سنجیده می‌شوند.
* ATR: فقط موتورِ ۳ آن را مصرف می‌کند (`structure_engine3.py:45`، رابطش `api/structure3.py:37`)؛ در payloadِ `/api/fts/{symbol}` هیچ ATRی نیست (grepِ `ATR` در `api/*.py` فقط موتورِ ۳ و متنِ مستندات را می‌دهد).
* **MACD هیچ‌جا درِ این مخزن محاسبه نمی‌شود.** تنها نامِ «MACD» درِ منوی اندیکاتورها می‌آید: `MACD` built-inِ klinecharts (`KLineChartWrapper.tsx:139`) و `MACD_TV` که تمپلیتِ پکیجِ `react-klinecharts-ui/extensions` است و بی‌واسطه از `tvIndicators.ts:19-38` ثبت می‌شود. پس شرطِ ۲ (فرمول با تعریفِ مرجع یکی باشد) برای MACD مالکیتِ خودِ پکیج است، نه کدِ این مخزن؛ آزمون‌های موجود (`technical-drawing-registry.spec.ts:58-73`، `mabna-indicators.spec.ts:491`) فقط «ثبت شدن» را می‌سنجند نه «درستیِ فرمول». (تکرارِ ریاض در پنج فایل: ب-۶.)

---

## ۳) موتورِ ۲ — رندرِ FFC (`engine/ffc/FastFinancialChartsEngine.ts`)

کاتالوگِ لایه‌ها (`ftsIndicatorCatalog.ts`) بیستِ لایه دارد: `trend-daily`,
`trend-weekly-gate`, `structure-points`, `e3-zigzag`, `e3-choch`, `fib-belt-33-40`,
`fib-belt-618-70`, `fib-levels`, `jet`, `pullback`, `choch`, `double-bottom`,
`point-hunt`, `current-trigger`, `third-peak`, `hourglass`, `ma14-exit`, `hard-stop`,
`setup-history`, `corp-actions`. هر لایه دو سمت دارد که جدا سنجیده می‌شود:
**محاسبه** (موتورِ ۱) و **رسم** (گروه overlay).

| شرط | وضعیت | شاهد / شکاف |
|---|---|---|
| ۴ مصرفِ همان نماد+TF | ✅ | `queryKey ['fts-analysis', symbol]` + AbortController (`useFtsAnalysis.ts:314-328`)؛ گاردِ ترتیبِ fetch (`KLineChartWrapper.tsx:567-575`) |
| ۵ رسمِ درست | 🟡 بخشی | گروه‌های اکتواری یکجا عوض می‌شوند (`FtsEngineChart.tsx:19,179-188`)؛ لنگرِ نسبت `dLast/aLast` (قاعدۀ لایۀ ۴). **راستی‌آزماییِ دیدنی در مرورگر = مرحلۀ ۵، سنجیده نشده.** سه لایه هم اصلاً رسم نمی‌شوند (بند ۴/ب). |
| ۶ بی‌ماندگاری پس از تغییرِ نماد/TF/مبنا | ✅ | کلیدِ کش (`chart.py:3586`) + گاردِ `dev/fts_cache_basis_v1078.py` + گاردِ تنظیمِ ساعت شنی |
| ۷ بی‌دادهٔ آینده | ✅ | `dev/fts_antirepaint_v1086.py` (مارکر در ناحیۀ تشکیل) + `dev/test_fts_asof_cutoff.py` |

## ۴) موتورِ ۳ — `api/structure_engine3.py`

ZigZag آستانه‌دار با `ATR_PERIOD=14`، `ATR_MULT=1.0`، `FLOOR_PCT=3.0`؛ رابطِ بی‌رأیِ
`/api/structure3/{symbol}?as_of=`. قراردادش با `dev/test_structure3_engine.py` (۴۷ سنجه)
می‌خواند: چهار حالتِ ورودی، آستانه فقط از خودِ موتور، پیشوند-پایداری، تفکیکِ ATR از کف،
صفر نوشتن درِ کشِ رأیِ رسمی. **تنها مانعِ مرحلۀ ۲ پابرجاست:** لینکِ مرجعِ بیرونیِ این
الگوریتم در تاریخچه/گزارش‌ها پیدا نیامد، پس `reference_status="unverified-no-external-reference"`
می‌ماند و تطبیقِ الگوریتمیِ آن با مرجع **سنجیده نشده** است (آستانۀ تازه اختراع نشد).
`_pivots` موتورِ ۳ آستانه‌دار است و از قاعدۀ اکیدِ `chart.py` متأثر **نمی‌شود** (تأییدشده با اجرایِ سوئیت).

---

## ۵) شکاف‌های مصرف/رسم (خروجیِ ممیزیِ این دور — تصمیمِ مرحلۀ ۶)

| # | یافته | شاهد | وضعیت |
|---|---|---|---|
| ب-۱ | `structure_points.W` منتشر می‌شود ولی هیچ‌جا خوانده نمی‌شود (فقط `.D`) | schema: `useFtsAnalysis.ts:284`؛ مصرف‌ها: `engineFtsLayers.ts:215`، `patternOverlays.ts:216` | باز — یا لایه می‌شود یا از payload بیرون می‌آید |
| ب-۲ | `exit_engine.l2.level/touches` و `l4.rsi_prev_peak` خوانده نمی‌شوند؛ «خطِ واگرایی RSI» که map وعده می‌داد رسم نمی‌شود (فقط تُنِ ردیفِ RSI در پنل و بجِ `bearish_div`) | `technicalSignals.ts:133`، `FtsTrendPanel.tsx:202`؛ نبودِ هر `l2.level` در فرانت | سطرِ map اصلاح شد («رسم نمی‌شود» با ذکرِ مصرف‌کننده)؛ رسم = کارِ مرحلۀ ۶ |
| ب-۳ | `range_box` باکسِ رنج را رسم نمی‌کند و لایۀ کاتالوگی ندارد | `FtsBadgeStrip.tsx:170`، `FtsTrendPanel.tsx:36`، `technicalSignals.ts:187,258` | باز (مرحلۀ ۶) |
| ب-۴ | `/api/patterns/{symbol}` صفرِ مصرف‌کننده دارد | grep در `frontend/src`، `tools/`، `dev/`: فقط سطرِ تعریف | باز؛ یا وصل می‌شود یا صریح «غیرفعال» ثبت |
| ب-۵ | `majorResistance`/`majorSupport` فقط در آزمون‌های vitest خوانده می‌شوند | `indicators.spec.ts:8-9`، `technical-weekly-wiring.spec.ts:183-184` | همان B6 (تصمیمِ مرحلۀ ۶) |
| ب-۶ | ریاضِ MA/EMA/RSI/ATR در پنج جایِ جدا تکرار شده: `chart.py::_fts_ma/_fts_rsi`، `confidence_engine.py:340/450`، `structure_engine3.py:45`، `trend_classify.py:23`، `frontend/lib/indicators.ts:21/48/207` | grepِ تعریف‌ها | ثبت؛ یک‌پارچه‌سازی بیرونِ دستورِ این دور است (ریسکِ شکستنِ سه موتور) |
| ب-۷ | `trend_classify.classify_trend` تنها با `BORS_TREND_ENGINE=hybrid` قابلِ دسترس است | `dev/test_trend_engine_flag.py` (۸/۸) | مسیرِ legacy بایت‌به‌بایت یکسان گارد شده؛ تصمیمِ حذف/نگهداشت با مالک |

## ۶) چیزی که در این دور **سنجیده نشد**

* رسمِ دیدنیِ هر لایه در مرورگر (شرطِ ۵) → مرحلۀ ۵/۶ با Playwright رویِ نشستِ احراز هویت‌شده.
* تطبیقِ عددیِ موتورِ ۳ با الگوریتمِ مرجعِ بیرونی (لینکِ مرجع در دسترس نیست).
* فرمولِ اندیکاتورهایِ بیرونی (MACD/MACD_TV/RSI_TV/CCI_TV و بقیۀ تمپلیت‌های `react-klinecharts-ui`) با تعریفِ TradingView سنجیده **نشده** — کدِ شخصِ ثالث است و درِ این مخزن فقط ثبت/رندرِ آن گارد شده.
* هیچ آستانۀ AMBIGUOUS تازه‌ای اختراع نشد؛ هیچ مقدارِ مرجعی ساخته نشد.

## ۷) دو ماژولِ همسایه که «موتورِ تکنیکال» نیستند ولی در شمارِ الگوریتم‌ها می‌آیند

| ماژول | نقش | چرا بیرونِ رأیِ FTS | آزمون (همین دور، گیتِ کامل) |
|---|---|---|---|
| `confidence_engine.py` (ریشۀ مخزن) | امتیازِ سه‌ستونه (تکنیکال/تابلو/بنیادی) برایِ تِب و مستر؛ `_sma:340`، `_rsi:450`، `_weekly_gate:477`، `_daily_setups:543` | رأیِ رسمیِ چارت را نمی‌سازد؛ فقط ستونِ «اطمینان» را می‌دهد (نسخۀ قواعدِ جدا) | `dev/confidence_engine_v973.py` (۱۰۷)، `dev/soft_warnings_v974.py` (۸۳)، `dev/ce_weekly_bucket_v1073.py` (۱۶) |
| `tape_flags.py` (ریشۀ مخزن) | پرچم‌هایِ تابلو (`JET_LADDER`، هوشِ حجم،.smart، susp)؛ `api/chart.py:10` همان `JET_LADDER` را import می‌کند تا چارت و تابلو یک جواب بدهند | ورودیِ قیف/تابلو است نه لایۀ رسمِ چارت | `dev/tape_filters_v1034.py`، `dev/tape_smartmoney_v1074.py`، `dev/test_mainwatch_flags_v1.py` (۷ بند) |

پاورقیِ صداقت: شمارِ «pass» درِ گیت از نامِ `PASS` درِ stdout خوانده می‌شود (`run_all_tests.py:418`)؛ سوئیت‌هایی که به‌جایش `ok` چاپ می‌کنند (مثلِ `test_mainwatch_flags_v1.py`) «۰ pass / ۰ fail» نشان می‌دهند، پس برایِ آن‌ها ملاکِ واقعی `rc=0` است و نبودِ سطرِ `FAIL`.
