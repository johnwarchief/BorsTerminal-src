# فاز تکنیکال — نقشهٔ شکاف و پلنِ اجرا (۲۰۲۶-۱۱-۰۵)

مالک پس از تأیید بصریِ پروفایل بنیادی گفت: «برو به تکنیکال». این سند وضعیتِ فعلی را با
شواهد ثبت می‌کند و اجرا را به افزایش‌های کوچک می‌شکند. **هیچ قاعده/آستانهٔ تازه‌ای ساخته
نمی‌شود؛ لایه‌ها همان چیزی است که سرور می‌فرستد.**

## وضعیتِ فعلی (شواهد)
- `frontend-v2/src/features/technical` ۵۰ فایل دارد: `KLineChartWrapper` (۷۴۹ خط)،
  `TechnicalWorkspace`، `DrawingToolbar`، `CandleEdgeCard`، `ForecastControls`،
  `PatternStoryOverlay`، `TelegramCatalogList`، `WideWorkspaceDrawer`، و
  `overlays/` شامل `ftsOverlays.ts` (۶۷۰ خط: S/R، کانالِ روند، پیوت، رنج، رگرسیون،
  پیچ‌فورک، گن، فیبوناچی extension/fan، price-range، risk/reward) + `smcOverlays`،
  `advancedTradingIndicators` (CHoCH/پولبکِ محاسبه‌شده در کلاینت)، `userIndicators`،
  `doubleTapOverlay`، `predictionOverlay`، `corporateEventsOverlay`.
- **شکافِ اصلی:** تحلیلِ سرور (`GET /api/fts/{symbol}`) در v2 مصرف نمی‌شد؛ روندِ D/W/M،
  وضعیتِ canonical، موتورِ خروج، ساعت‌شنی، جت، شکارِ نقطه، کفِ دوقلو، جعبهٔ رنج،
  فیبِ سرور و نقاطِ ساختاری هیچ‌جا رسم/نمایش نمی‌شدند. CHoCH و پولبکِ v2 محاسبهٔ
  کلاینتی‌اند، نه آینهٔ رأیِ سرور.
- اپِ قبلی این‌ها را داشت: `useFtsAnalysis`، `engineFtsLayers`، `FtsBadgeStrip`،
  `FtsDock`، `FtsEngineChart`، `FtsIndicatorPanel`، `FtsLayerLegend`، `FtsStatusCard`،
  `FtsTrendPanel`، `SidebarFtsSignals`، `SidebarActiveLevels`، `TechnicalStructureSummary`،
  `ReplayBar`، `ComparePanel`، `ChartSettingsDialog`، `PatternToggles`، `FtsDrillDown`.

## افزایش‌ها
1. **قراردادِ داده** ✅ `de63f882` — `useFtsAnalysis` + اسکیمای کامل + تستِ قرارداد
   (شکلِ پاسخ، `null ≠ false`، پاسخِ مشروعِ نمادِ بی‌تاریخچه). ۴ تست.
2. **سطحِ وضعیت** — کارتِ وضعیتِ canonical (`fts.status`: code/text/trigger/exits/
   warnings/unknown/vetoed) + نوارِ بج‌ها (روند D/W، جت، CHoCH، پولبک، ساعت‌شنی) +
   پنلِ روند (D/W/M با `basis`/`stale_bars`/`last_pivot_time`). همه از پاسخِ سرور.
3. **لایه‌های چارت از سرور** — `structure_points` (HH/HL/LH/LL با confirm_time)،
   `fib.levels`/zones، `jet.resistance`، `range_box` (با start/end)، `hourglass.ma52`
   با باندِ سرور، `point_hunt.floor`، `pullback.level`، `choch.level`، `exit_engine.l1.hard_stop`.
   هر لایه فقط وقتی رسم می‌شود که کلیدِ متناظر در پاسخ باشد؛ «سنجیده نشد» رسم نمی‌شود.
4. **لِجند و داک** — لِجندِ لایه‌ها + داکِ تحلیل (فهرستِ لایه‌هایِ فعال با نقش:
   trigger/context/warning/exit) + کنترل‌های نمایش، هم‌تراز با `status.roles`.
5. **پذیرش/پاریتی** — همان نمادهای cohort با اپِ قبلی مقایسه شود: وجود/نبودِ هر لایه،
   عددِ سطوح، و اسکرین‌شات‌ها؛ سپس نقدِ کاربریِ چارت با `fts-user-critic` (بخش chart).

## قیدها
- فقط `frontend-v2/src/features/technical/**` (+ تست‌هایش) و در صورتِ لزوم `app/styles.css`.
- بدونِ تغییرِ بک‌اند/Go/فیلترها؛ بدونِ push.
- تست‌های چارت/لایه باید «رسم شد/نشد» را از داده اثبات کنند، نه از اسنپ‌شات.
- گیتِ بصریِ مالک: ۱۳۶۶×۷۶۸ و ۱۹۲۰×۱۰۸۰، هر دو تم، با شواهدِ اندازه‌گیری‌شده.
