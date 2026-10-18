# موجودیِ مرحلۀ A — چارت، ابزارهایِ رسم، اندیکاتورها و موتورِ تکنیکال ۱

تاریخ: ۱۴۰۵-۰۷-۲۶ (۲۰۲۶-۱۰-۱۸) · branch: `mission/system2-chart-parity-engine1-2026-10-18` · HEADِ این سند: `18fa3f89`
مبنایِ کد: `ff6b2fb` (موتورِ تعدیل + زنجیرۀ پاریتی) ⊕ `1d3ff6fe` (محصول ۱٫۰٫۹۱ + polishِ UI/UX) ⊕ کاغذِ `origin/main`.
روش: خواندنِ کدِ واقعی با `file:line`. هر آنچه پیدا نشد صریح **absent** نوشته شده، نه حدس.

---

## ۱. مسیرِ دادهٔ چارت (Backend)

| چیز | کجا |
|---|---|
| route اصلیِ چارت | `api/chart.py:1043` `GET /api/chart/{symbol}` → `get_chart_tsetmc` |
| سایرِ routeها | `:1331` key-levels · `:1384` order-book · `:1492`/`:1649` calendar · `:1681` `/api/ma/{symbol}` · `:1748` `/api/chart-db/{symbol}` (محلی، تمامِ عمق) · `:1840` patterns · `:4037` `/api/fts/{symbol}` |
| ترتیبِ منبع | کش (`:1048-1051`) ← `CDN_OFFLINE_UNTIL` (`:1106`) ← `ins_code` (`:1122`) ← CSVِ `GetClosingPriceDailyListCSV/{ins_code}/19900101` (`:1148-1151`) ← `_parse_tsetmc_csv` (`:1164`) |
| افتادن به محلی | فقط داخلِ `_fallback_local()` `:1055-1103`؛ صدا زده می‌شود در `:1107`, `:1138`, `:1154` (با `CDN_OFFLINE_UNTIL=now+120` در `:1153`), `:1160`, `:1199` (صفر کندل), `:1228` (هر استثنا) |
| `degraded` | **تنها** در `:1079` (مسیرِ محلی). درِ مسیرِ CDN اصلاً کلید نمی‌شود |
| `historyRepairScheduled` | بازگشتِ `_schedule_history_repair(...)` در `:1096-1097`؛ `True` فقط با شکاف + `HISTORY_REPAIR_MIN_GAP = 900.0` (`:929`) |
| منشأِ تعدیل | `adjust_source` `:1179-1182` با مقادیر `ledger+base-price-discontinuity` / `base-price-discontinuity` / `base-not-anchored` / `no-adjustment-event`؛ مسیرِ محلی `:1073` صریح `local-db-fallback` |
| زنجیرۀ canonicalِ تعدیل | `_canonical_adjustment:758`، `_adjust_capability:770`، `_ledger_coverage:624`، `_functional_state:722`، `_collapse_zero_volume_runs:223`، `_attach_live_bar:995`، `_stamp_data_time:978` |
| اتصالِ موتورهایِ canonical | `AE.event_factor` `:615/:659`، `AE.chain_factors` `:766/:810`، `CL.build_typed_events` `:655`، `candle_contract.widen` `:147/:920`، `price_basis.resolve_payload` `:1005/:1010/:1040/:1826` |
| قراردادِ وضعیتِ موتورِ تعدیل | `OK:47`، `unknown_type:64/128`، `incomplete:<فیلد>`، `invalid:<علت>` → درِ API به‌شکلِ `factor_status` روی `adjustRejected` (`:620`) |
| تایم‌فریم | بک‌اند **فقط روزانه**؛ هیچِ پارامترِ interval رویِ routeها نیست. هفتگی/ماهانه با `_fts_resample(...,"W"|"M")` `:2033-2073` (باکتِ شنبه `:2059`) و مصرف `:3622-3623` |
| کشِ چارت | `CHART_CACHE:1938`، کلید `_chart_cache_key:1941-1955` = `symbol|price_basis.current()`، `TTL=3600` `:1965`، `FALLBACK_TTL=20` `:1974` |
| `BORS_NO_FETCH_LOOPS` | پیش از این دور **تنها** `app.py:177` (حلقه‌های `:209/:269/:308`). ترمیمِ تاریخچۀ چارت ازِ این درب رد می‌شد → اصلاح شد (بندِ ۴) |

## ۲. چارتِ Frontend

| چیز | کجا |
|---|---|
| موتورهایِ ثبت‌شده | `features/technical/engine/registry.ts` (klinecharts + ffc، هر دو `production:true`)؛ `DEFAULT_ENGINE='klinecharts'` `:45` |
| انتخابِ موتور | `routes/TechnicalPage.tsx:136` از `useFtsConfigStore.chartEngine`؛ `chartEngine==='ffc'` ⇒ `FtsEngineChart` درغیراینصورت `NnChart` (`:269-320`) |
| چارتِ زنده | `nahayatnegar/components/KLineChartWrapper.tsx` (مستقیم `klinecharts.init` در `:955`، بی‌گذر از آداپتورِ رجیستری) |
| کندل/محور/مقیاس | رنگ‌ها و شبح `:1114-1137`, `:1237-1249` · محورها `:1196-1219`, `:1332-1353` · log/percent `:1366-1379` · دقتِ قیمت `:1410-1422` · `applyAdjustmentToCandles:540` |
| ابزارهایِ رسمِ واقعی | `DrawingToolbar.tsx:61-145` → `handleSelectTool` `:2235` → `chart.createOverlay` `:2275`؛ بازنقش‌ها `fibonacciLine→tvFibLog` `:2258`، `ruler→ftsMeasure` `:2260-2263` |
| `lib/drawingTools.ts` | **مرده**: `DRAWING_CATALOG`/`buildDrawingGroups`/`defaultFor`/`saveToolDefault` فقط توسطِ سه specِ تست مصرف می‌شوند؛ ذخیرۀِ `fts.tool.defaults.v1` بی‌اثر است |
| ماندگاریِ رسم‌ها | `lib/drawStore.ts` — نقاط **زمان/قیمت** (نه پیکسل) `:5`، کلیدِ per-symbol `:22` و per-symbol+timeframe `:27`؛ چرخۀِ پاک/بازیابی `KLineChartWrapper.tsx:779-907`، autosave هر ۲s `:859` |
| تنظیماتِ هر عنصر | `FloatingPropertiesBar.tsx` (mounted `:2525`) → `handleColor/Width/Style/ToggleLock` `:2332-2377` → `overrideOverlay` **متصل و کار می‌کند** |
| تنظیماتِ سراسریِ چارت | `components/ChartSettingsDialog.tsx:433-533` → `ftsConfigStore.setView` → effectِ `:1104-1395` |
| کاتالوگِ اندیکاتور/لایه | `lib/ftsIndicatorCatalog.ts:59` (۲۴ شناسه: trend، choch، jet، double-bottom، range-box، fib-beltها، corp-actions، …)؛ مقادیر ازِ payloadِ `/api/fts` می‌آیند (`source:42`) |
| رندرِ لایه‌ها | klinecharts: `lib/ftsOverlays.ts` + `lib/patternOverlays.ts` (`toChartOverlay:189`) + `lib/structure3Layers.ts`؛ ffc: `lib/engineFtsLayers.ts:15` |
| DPI | `devicePixelRatio` درِ کدِ اپ **absent** (فقط `FastFinancialChartsEngine.ts:187/229` canvas می‌سازد)؛ ResizeObserver `:1067-1082` + re-resize ۲۲۰ms |
| ریسکِ باقی‌ماندنِ شیءِ نمادِ قبلی | effectِ استراتژی FTS با `!ftsAnalysis` زودِ return می‌کند `:1462` و فقط به cleanupِ دورِ پیشین تکیه دارد؛ `handleTimeframeChange:1987` هم گروه‌ها را هم‌زمان پاک نمی‌کند |

## ۳. قواعدِ رسمیِ FTS ⇄ کد ⇄ API ⇄ UI ⇄ آزمون

| سیگنال | منبعِ قاعده | Backend | UI | آزمون | حکم |
|---|---|---|---|---|---|
| روند + گیتِ هفتگی | `docs/fts-notes/FTS_CHART3_extracted_text.txt:31-33`؛ `jozve…:179-186` | `api/chart.py:2210 _fts_classify_trend`، پیوت `:2075`، گیتِ هفتگی `:3655-3707` | `useSymbolVeto.ts:72`, `FtsTrendPanel.tsx`, `SymbolInspector.tsx:273`, `FtsFunnelAllStages.tsx:69` | `dev/fts_trend_fixtures_v1075.py:79-139`, `dev/weekly_veto_guard.py`, `technical-weekly-wiring.spec.ts` | **VERIFIED** (هفتگی ازِ روزانه تجمیع می‌شود، نه فیدِ مستقل) |
| CHoCH صعودی/نزولی | CHART3:39؛ `jozve…:241-243`, `:729` | `:2728 _fts_choch`، شعبه `:2790-2795`/`:2784-2787`، `_settled:2772-2779` با `_FTS_CHOCH_DAYS=2` `:2018` و `_FTS_CHOCH_MARGIN=0.01` `:2019` | `FtsBadgeStrip.tsx:147/150`, `useScreener.ts:68/69`, `patternOverlays.ts:345` | `test_fts_technical_tristate.py:114-122`, `fts_antirepaint_v1086.py`, `technicalSignals.spec.ts:135` | **VERIFIED** — دو بستۀِ روزانۀ تأییدی و حاشیۀِ ۱٪ واقعاً درِ کد هست |
| جت | CHART3:142؛ `OWNER_RULINGS.md:259-262` | `:2584 _fts_jet_setup` (سقفِ استاتیک ۲۵۰جلسه‌ای `:2633-2646`، کندلِ تثبیت `:2664`، پنجرۀِ ۳روزه `:2672`) | تنها به‌شکلِ presetِ جدول (`FtsScreenTable.tsx:760,775`)؛ `tech_jet` درِ قیف evidence-only | `test_fts_technical_tristate.py:59-104`, `jet-candidate-preset.spec.tsx:48,64` | **MISMATCH** — شروطِ بنیادی/روند بیرونِ تابع‌اند و رجیستری `f_jet`ِ جدا (tape) است |
| کفِ دوقلو | CHART3:42؛ `jozve…_25-34.md:158,161` | `:2885` با تلورانسِ **۱٫۵٪** (`:2896-2908`) | `useScreener.ts:70`, `patternOverlays.ts`, `ftsPipelineEvaluator.ts:331,359` | `technical-pattern-wiring.spec.tsx:49,67` | **MISMATCH** — تلورانسِ ۱٫۵٪ درِ جزوه نیست (اختراعِ پیاده‌سازی) |
| خروج از باکس رنج | CHART3:84؛ `jozve…:579` | `:2909-2924` (باکس = ۲۰ کندل، شکستِ سقفِ باکس باِ یکِ کندل) | `useScreener.ts:71`, `patternOverlays.ts:541` | `ffc-engine-v1066.spec.ts:84-142` | **MISMATCH** — رشدِ حجم/پولِ هوشمند/الگویِ ساعت و قاعدۀ «باکسِ بلندتر، حرکتِ بزرگ‌تر» modelled نشده |
| فیبوناچی | CHART3:38؛ `jozve…:249-252` (رویِ log)؛ `FTS-RULE-ALGORITHM-MAP.md` «فیبو به‌تنهایی ورود نیست» | `:2533 _fts_fib_zones` + `_fts_fib_retrace:2520` (log)؛ سیگنالِ ورود تولید نمی‌کند | `FtsBadgeStrip.tsx:133-138` («زمینه، نه سیگنال»), `SidebarActiveLevels.tsx:177-186`, `useScreener.ts:72` `role:'context'` | `fts_chart_engine_v1037.py:64-104`, `fts_antirepaint_v1086.py:194-207` | **VERIFIED** (نقشِ زمینه‌ای تا endpoint حفظ شده) |
| فیلترهایِ تکنیکالِ قیف | CHART3:31-41؛ `FTS-RULE-ALGORITHM-MAP.md` | `funnel_engine.py:757 technical_stage` (فقط خواندنِ ستون‌ها)، سه‌حالته `:786-812` | `FtsFunnelStageView.tsx:15`؛ `FtsCustomChainBuilder.tsx:22,36` **فقط فیلترهای tape** را می‌شمارد | `funnel_engine_v1.py:189,270,370`, `test_screener_funnel_gate_v1.py:72,208` | **MISMATCH** — `tech_points` در `:836/:951/:1003/:1031` مرتب می‌کند ولی هیچِ تولیدکننده‌ای هرگز آن را پر نمی‌کند (absent در DDLِ `funnel_tech_scan.py` و `api/screener.py`)؛ `tech_choch_bear`/`tech_double_bottom`/`tech_range_break`/`tech_fib_zone`/`tech_exit_verdict` درِ API هست ولی هیچِ انتخابگرِ UI ندارد |

وضعیتِ `UNKNOWN`/`NOT_EVALUATED` حفظ شده است: `TECH_NO_HISTORY ⇒ UNAVAILABLE`، `TECH_SCAN_PENDING ⇒ PENDING`، `TECH_UNMEASURED ⇒ UNAVAILABLE` (`funnel_engine.py:786-812`)، و رابطِ چارت `pending` را از `insufficient` جدا می‌دارد (`FtsStatusCard.tsx:28-30`، کارِ دورِ P0§۳ در `5408fba`).

## ۴. آنچه درِ این دور اصلاح/ثب‌ت شد

1. **دربِ `BORS_NO_FETCH_LOOPS` ترمیمِ تاریخچه را نمی‌بست** — اندازه‌گیری: باِ دربِ بسته هم `hist-repair` زاده می‌شد، ازِ TSETMC می‌گرفت و می‌نوشت (فولاد ۳۹۱→۳۹۲). داوری به `bors_flags.fetch_loops_enabled()` منتقل شد (یکِ منبع)؛ `dev/history_repair_env_gate_v1.py` (۲۴ سنجه) به SUITES اضافه شد: بی‌درب ۱۹/۵ قرمز، باِ درب ۲۴/۰.
2. **کندل‌هایِ تخت باگ نیستند**: ۱۳۱/۴۲۴۷ کندلِ فولاد O=H=L=C است و مرجع (۴۳ روزِ مشترک درِ `_audit/ra365_ref_bars.json`) رویِ **همان ۴۳ روز** تخت است ⇒ «رفتارِ منبع».
3. **`volumes` کامل است** (۴۲۴۷/۴۲۴۷ غیرصفر، باِ `color`)؛ درِ آرایۀِ `candles` حجم نیست و این قراردادِ payload است، نه گم‌شدنِ داده.
4. **مقیاسِ محور سالم است** درِ 1366×768 و 1600×900 (`_audit/chart_parity_measure.js`؛ درگِ کوتاه `scaleHeld=true`، درگِ بلند `scaleRechosen=true`، `idleRepeat stable=true`).
5. **D-1/D-2 درِ ماتریسِ Stage 0 کهنه‌اند**: پنج کنترلِ «بی‌رفتار» درِ `22e45e06` به موتور رسیدند و `technical-settings-effectiveness.spec.tsx` (۱۱ سنجه) سبز است. مرده‌هایِ واقعی فقط `showXAxis`/`showYAxis`/`splitLayout` (بی‌UI) — سازۀِ دو اول `size:0`+`show:false` است (vendor `show` را تنها درِ شاخۀِ auto-size می‌خواند).
6. **مبنایِ قیمت درِ مسیرِ جایگزین عوض می‌شود**: CDN ⇒ `priceBasis=last`، محلی ⇒ `closing` با `priceBasisReason=last_missing:382/391`. تطبیقِ بصری باید باِ مبنایِ یکسان خوانده شود.
7. **تعدیلِ عملکردی برایِ فولاد «available» نیست** (`functional_available:false` به‌سببِ نامعلوم‌بودنِ `corporateTypeCode`) — چارت ما درِ پیش‌فرضِ `closing` باِ `adjustSource=ledger+base-price-discontinuity` سرو می‌شود؛ مقابلهٔ رسمیِ type7 میانۀِ خطا ۰٫۳۲۲۵٪ (فولاد) و ۰٫۴۴۵۰٪ (میانهٔ ۲۹ نماد).

## ۵. بازها

- **دسترسیِ زندهٔ رهاورد**: مرورگرِ connector لاگین نیست (`ورود / ثبتنام`)؛ طبقِ قاعده واردِ حساب نمی‌شوم. تاِ ورودِ خودِ مالک، تطبیقِ بصریِ زنده `NOT_RUN` است و سنجش‌ها آفلاین (ازِ fixtureها) گزارش می‌شود.
- `splitLayout` سازۀِ تک‌نهادی درِ klinecharts ندارد (N نشست + `subscribeAction`) — نیازمندِ تصمیمِ مالک.
- `ffc` ازِ انتخابِ کاربر بیرون می‌رود (رأیِ مالک)، ولی کد/لایه‌هایش می‌ماند.
- `tech_points` بی‌تولیدکننده (بندِ ۳) و پنج ستونِ تکنیکالِ بی‌انتخابگرِ UI.
- `tools/notebook_evidence.py` dep اعلام‌نشده داشت (پینِ `pypdfium2==5.14.0` اضافه شد).
