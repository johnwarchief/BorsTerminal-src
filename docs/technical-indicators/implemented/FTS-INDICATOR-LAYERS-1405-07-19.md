# لایه‌های FTS در محصول — رکوردِ پیاده‌سازی (۱۴۰۵-۰۷-۱۹ / ۲۰۲۶-۱۰-۱۱)

مرحلۀ ۳ تا ۷ مأموریتِ «مهندسی اندیکاتورهای FTS». این فایل فقط آنچه **واقعاً در مخزن و درِ گیت‌ها
اجرا می‌شود** را ثبت می‌کند؛ هر چیزِ آزمایش‌نشده با برچسبِ UNVERIFIED یا «اجرا نشده» می‌آید.
مرجعِ قاعده: `docs/FTS-RULE-ALGORITHM-MAP.md` (نگاشتِ قاعدهٔ جزوه → الگوریتم → ترسیم).
مرجعِ قواعد: جزوۀ `FTS.pdf` و `FTS.CHART_3.pdf`. هیچ آستانه‌ای که جزوه عددش را نگفته اختراع نشده است.

## ۱) کاتالوگ لایه‌ها — ۱۸ لایه، هر یک با توسلِ مستقل

منبع: `frontend/src/features/technical/lib/ftsIndicatorCatalog.ts`. هر سطرِ این جدول همان `id` است که
پنل، افسانۀ چارت (legend)، شواهدِ کلیک و سوییچِ localStorage از همان استفاده می‌کنند؛ «دهانۀ payload»
کلیدِ واقعی در `FtsAnalysis` پاسخِ `/api/fts/{symbol}` است — یعنی هیچ لایه‌ای در فرانت محاسبه نمی‌شود.

| id | نام فارسی | گروه | نوع نمایش | دهانۀ payload | توسل |
|---|---|---|---|---|---|
| `trend-daily` | روند ساختاری روزانه | trend | panel | `trend.D` | با موتور (null) |
| `trend-weekly-gate` | وتوی روند هفتگی | trend | panel | `trend.matrix` | با موتور (null) |
| `structure-points` | نقاط ساختار (HH/HL/LH/LL) | structure | marker | `structure_points.D` | `structure` |
| `fib-belt-33-40` | پل اول فیبو ۳۳–۴۰٪ | fibonacci | band | `fib.zone_33_40` | با موتور (null) |
| `fib-belt-618-70` | کمربند طلایی ۶۱.۸–۷۰٪ | fibonacci | band | `fib.zone_618_70` | با موتور (null) |
| `fib-levels` | سطوح کامل فیبو (۰ تا ۱) | fibonacci | level | `fib.levels` | `showFibLevels` |
| `jet` | جت — شکست مقاومت استاتیک | entry-setup | segment + level | `jet.resistance` | `jet` |
| `pullback` | پولبک به آخرین سقف | entry-setup | level + marker | `pullback` | `pullback` |
| `choch` | تغییر ساختار (CHoCH) | entry-setup | level | `choch.level` | `choch` |
| `double-bottom` | خط گردن کف دوقلو | entry-setup | level | `double_bottom.neckline` | `double` |
| `point-hunt` | تریگر نقطه‌زنی کف‌ها | entry-setup | marker | `point_hunt` | `pointhunt` |
| `current-trigger` | تریگرِ فعلیِ موتور | entry-setup | marker | `status.trigger` | با موتور (null) |
| `third-peak` | منطقه پرریسک سقف سوم | exit-risk | band + level | `exit_engine.l3` | `thirdpeak` |
| `hourglass` | ساعت شنی (MA52 هفتگی) | exit-risk | band + level | `hourglass` | `hourglass` |
| `ma14-exit` | خروج زیر MA14 | exit-risk | level + marker | `exit_engine.l1` | `ma14exit` |
| `hard-stop` | حد ضرر (آخرین کف) | exit-risk | level | `exit_engine.l1.hard_stop` | با موتور (null) |
| `setup-history` | رویدادهای تاریخی ستاپ‌ها | history-events | marker | `setups` | `showHistoryEvents` |
| `corp-actions` | رویدادهای شرکتی (تعدیل) | history-events | marker | خوراکِ `adjustEvents` (نه `/api/fts`) | `showCorporateActions` |

نام‌هایِ دوگان، گروه‌ها (`trend` / `structure` / `fibonacci` / `entry-setup` / `exit-risk` /
`history-events`) و پنج نوعِ نمایش (`level` `band` `segment` `marker` `panel`) از همان فایل می‌آیند؛
`corp-actions` تنها سطری است که قاعدۀ جزوه ندارد و منبعش خوراکِ TSETMC است — درِ کاتالوگ هم با
`rule: '— خارج از قواعد جزوه…'` همین طور علامت خورده است.

## ۲) جداسازی محاسبه از رندر

- **محاسبه:** `api/chart.py` (توابعِ `_fts_*`) پشتِ `/api/fts/{symbol}`؛ تنها مالکِ رأی.
- **نگاشت (یک سورس، دو رندر):** `lib/patternOverlays.ts` برای موتورِ اول (klinecharts) و
  `lib/engineFtsLayers.ts` + `engine/ffc/FtsEngineChart.tsx` برای موتورِ دوم (FFC/WebGL2).
- **UX:** `FtsIndicatorPanel.tsx` (تست‌ها با `data-testid="fts-layer-panel"` پیدا می‌کنند)، افسانۀ چارت
  (`fts-legend-host`) و کارتِ شواهد (`lib/ftsLayerEvidence.ts` → قاعده، دهانۀ payload، زمانِ رخداد/تأیید،
  یا «بی‌واکهِ قابل‌استناد» وقتی عددی منتشر نشده).
- **مقیاسِ لگ و تعدیل:** `toDisp` در FFC پیش از رسم، ضریبِ تعدیلِ عملکردی را اعمال می‌کند (پدیدۀ B5 برطرف شد) و
  `fibLogarithmic` در `useFtsConfigStore.view` (`fts.chart.settings.v1`) نشسته است.

## ۳) موتور سوم: `structure_engine3.py` (تحلیلی، آفلاین، بی‌لایه)

**چیست:** ZigZagِ آستانه‌دار بر بسترِ ATR٪. پیوت از «فاصلۀ برگشتِ کافی» می‌آید نه از مقایسهٔ همسایه؛
تأیید زمانی‌اش `confirm_idx` همان کندلِ برگشت است نه `idx + k`.
**پارامترهایِ پیش‌فرض (همان‌ها که harness اجرا می‌کند):** `ATR_PERIOD = 14`، `ATR_MULT = 1.0`،
`FLOOR_PCT = 3.0` — سه پارامترِ **اجرایِ موتورِ مقایسه**، نه قاعدۀ جزوه؛ جزوه برای ZigZagِ آستانه‌دار
عددی نمی‌دهد و در `FTS-RULE-ALGORITHM-MAP.md` به‌عنوانِ AMBIGUOUS باقی مانده است.
**خروجی:** فهرستِ پیوت با `idx/time` + `confirm_idx/confirm_time` + `label_structure(pivots)` برای
HH/HL/LH/LL.

**تفاوتِ الگوریتمی — اندازه‌گیری‌شده (خروجیِ `dev/structure_engine3_compare_v1.py`، همین مخزن):**

| سری | پیوتِ موتورِ اول | پیوتِ موتورِ سوم | تطابقِ ±۳ کندل |
|---|---|---|---|
| `tri-amp18` (مصنوعی) | ۴۳ | ۴ | ۱۴٪ |
| `walk-42` (seed ثابت) | ۲۵ | ۸ | ۵۶٪ |
| `walk-7` (seed ثابت) | ۲۱ | ۱۱ | ۹۰٪ |
| سبهان (بانکِ محلی) | ۲۸۹۴ | ۴۹۷ | ۳۴٪ |
| سخاش | ۲۳۵۰ | ۴۸۱ | ۴۱٪ |
| سرود | ۲۸۴۸ | ۶۸۴ | ۴۸٪ |
| سشمال | ۱۴۹۴ | ۵۳۷ | ۵۴٪ |
| سفار | ۴۶۱ | ۲۷۶ | ۶۱٪ |
| شاملا | ۲۰۷۸ | ۵۴۳ | ۴۴٪ |

گاردِ «بازمصرف نیست» رویِ هر دو دسته (مصنوعی و واقعی) پاس می‌شود: دست‌کم یک سری با فهرستِ پیوتِ جدا.
anti-repaint و prefix-stability هم برای هر پنج سریِ مصنوعی/واقعیِ بررسی‌شده سبزاند.

**تصمیمِ مستند (چرا در چارت نیست):** موتورِ سوم به کاتالوگِ §۱ و به `FtsLayerPanel` **وصل نشده** و
رأیِ `/api/fts` را عوض نمی‌کند. دلیل: (الف) اگر دو موتورِ ساختارِ متفاوت رویِ یک چارتِ واحد برچسب
بزنند، «منبع حقیقت» دو تا می‌شود و قراردادِ مأموریت (`/api/fts` مرجع می‌ماند) نقض می‌شود؛
(ب) آستانه‌هایش (ATR×۱٫۰ و کفِ ۳٪) رأیِ جزوه ندارند، پس نمی‌توانند در قیفِ رسمی وارد شوند؛
(ج) مصرفِ تأییدشده‌اش همین حالا harnessِ مقایسه و گاردِ ضدِ repaint است. برای لایه شدنش لازم است:
یک endpointِ جدا (مثلاً `/api/structure3/{symbol}`)، یک سطرِ کاتالوگِ با `rule: '— خارج از قواعد جزوه'`،
و آستانه‌هایی که مالک عددشان را تأیید کند — هیچ‌یک از این سه امروز وجود ندارد. ⇒ **UNVERIFIED در مرجع
بیرونی:** تطابقِ این موتور با رهاورد سنجیده نشده (سنجشِ رهاورد فقط موتورِ اول را پوشش می‌دهد؛
ببین `docs/TECHNICAL-RAHAVARD-PARITY-AUDIT.md`).

**چرا در `hiddenimports` نیست:** import‌کننده‌هایش فقط `dev/structure_engine3_compare_v1.py` و
`dev/fts_antirepaint_v1086.py` و `dev/run_all_tests.py`اند (تأیید با grep)؛ هیچ `api/*.py` آن را وارد
نمی‌کند، پس فهرستِ `hiddenimports`ِ بسته‌بندیِ PyInstaller تغییر نمی‌کند.

## ۴) تست‌ها و درگاه‌ها

| سنجه | کجا | وضعیت |
|---|---|---|
| یکتاییِ `id`ها، زنده‌بودنِ دهانه‌ها، پوششِ هر دو رندر | `frontend/src/__tests__/fts-indicator-catalog.spec.ts` | vitest |
| پنل/توسل‌ها/افسانه/کارتِ شواهد | `frontend/src/__tests__/technical-indicator-panel.spec.tsx` | vitest |
| تفاوتِ الگوریتمی + anti-repaint موتورِ سوم | `dev/structure_engine3_compare_v1.py` | در `dev/run_all_tests.py` (آفلاین) |
| دو-زمانیِ پیوت‌ها، prefix-stability، بی‌نگاه‌به‌آینده بودنِ payload | `dev/fts_antirepaint_v1086.py` | در `dev/run_all_tests.py` (آفلاین) |
| پاریتیِ رهاورد رویِ ۲۷ نماد / ۵۴ سطر | `tools/ra_fts_parity.py` | **خارج از گیتِ آفلاین** — شبکه لازم دارد؛ خروجیِ اجراشده: `docs/validation/rahavard-trend-parity/PARITY-2026-10-11.csv` |
| مرورگرِ زنده (هر دو موتور، تبِ «لایه‌های FTS»، افسانه، توسل، شواهد) | `dev/fts_layers_e2e_v1.js` | نیازمندِ سرورِ بالا؛ **در این دور اجرا و PASS شد** — جزئیات در §۶ همین فایل |

## ۵) آنچه از inbox آمد: هیچ

`docs/technical-indicators/reviewed/FTS-MISSION-INBOX-REVIEW-1405-07-19.md` — ۱۱ موردِ بررسی‌شده،
صفر ادغام. هیچ خطِ کدی از فایل‌های MQL/Pine به این مخزن منتقل نشده و هیچ `.ex4/.ex5` اجرا نشده است.

## ۶) نتیجۀ سنجشِ مرورگری — اجرا شد (۱۴۰۵-۰۷-۱۹، ۲۲:۲۷)

دستگاه: `dev/fts_layers_e2e_v1.js` رویِ Chromiumِ واقعی، `BASE=http://localhost:5173` (vite این ماشین
رویِ `::1` می‌نشیند؛ با `127.0.0.1` اتصال رد می‌شود)، نمادِ `فولاد`، هر دو موتور در دو context مستقل.
صفحۀ ورودِ محلی با همان فرمِ واقعی و مقدارهایِ shipped (`admin` / `bors123`) رانده می‌شود؛ با
`--user/--pass` قابلِ تغییر است. پس از اجرایِ نهایی، هر دو سرورِ dev بسته شد (قاعدۀ گیت).

**حکمِ نهایی: PASS — ۳۰ سطرِ `ok` (۱۵ سنجه × ۲ موتور)، `fails: []`، سطرِ پایانی
«FTS LAYERS E2E OK».**

| سنجه (هر موتور جدا) | نتیجۀ اندازه‌گیری‌شده |
|---|---|
| میزبانِ چارت + بوم رویِ دادهٔ زنده | `nn-chart-host` / `ffc-chart-host` هر دو با canvas؛ رسیدنِ feed: ۳۶ ms (klinecharts) و ۲۸ ms (ffc) از لحظۀ پروب |
| تبِ داکِ «لایه‌های FTS» | باز شد (`fts-dock-tab-layers` → `fts-dock-body`) |
| سطرهایِ کاتالوگ | ۱۸ سطر در هر دو موتور |
| لایه‌های «فعال» رویِ دادهٔ زنده | ۹ لایه: `trend-daily`، `trend-weekly-gate`، `structure-points`، `fib-belt-33-40`، `fib-belt-618-70`، `fib-levels`، `hard-stop`، `setup-history`، `corp-actions` |
| لایه‌های «فعال نیست» | `jet`، `pullback`، `choch`، `double-bottom`، `point-hunt`، `third-peak`، `hourglass`، `ma14-exit` — و `current-trigger` با برچسبِ «منتشر نشده». هیچ‌کدام صفرِ ساختگی نیست؛ همین‌ها یعنی payload در این دور این سیگنال‌ها را اعلام نکرده. |
| خطِ تازگی | `مبنا: tsetmc-adjusted · ۴۲۴۳ کندلِ تحلیل · آخرین کندل: 1405/07/19 · دریافت: ۲۲:۲۷` — شمارِ کندل واقعی است، نه متنِ ثابت؛ سنجه، «اعلام نشده» بودن را FAIL می‌گیرد. |
| سوییچِ دوطرفه | `structure-points`: خاموش → `false` درِ `localStorage` (`fts-pattern-prefs`) → روشن و بازگشت به وضعیتِ پیش از آزمایش |
| کارتِ شواهد | ارجاع به `docs/FTS-RULE-ALGORITHM-MAP.md`؛ دهانۀ payload: `structure_points.D`، ترسیم: `marker`؛ دو زمان جدا: `کِی رخ داد: 2026-10-05` / `کِی فهمیدیم: 2026-10-10` (در DOM کنارِ هم می‌چسبند، ولی دو `span` مستقل‌اند — `fts-evidence-times` با `flex flex-wrap gap-3`) |
| افسانۀ چارت | klinecharts: `structure-points, fib-belt-33-40, fib-belt-618-70, corp-actions`؛ ffc: همان چهار + `hard-stop`. اختلافِ این دو **عمدی و ثبت‌شده** است: رجیستری `engines: { klinecharts: false, ffc: true }` برایِ `hard-stop` می‌گوید (`ftsIndicatorCatalog.ts:143-149`) و پنل همان را با نشانِ `K ✓/✗`، `F ✓/✗` (`FtsIndicatorPanel.tsx:166-170`) نشان می‌دهد. افسانه چیزی را که موتور رسم نمی‌کند وعده نمی‌دهد. |
| console / pageerror | صفر خطا در هر دو موتور |

شواهدِ تصویری و ماشینیِ این اجرا: `_audit/e2e_layers_klinecharts.png`، `_audit/e2e_layers_ffc.png`
(موتورِ اوّلی: کندل‌ها با نشانگرهایِ HH/HL/LH/LL، بلت‌های فیبو، بجِ تعدیل، داکِ باز رویِ «لایه‌های FTS»
با برچسب‌هایِ «فعال»، خطِ افسانه بالایِ چارت) و `_audit/fts_layers_e2e.json` (همان جدولِ بالا به‌صورتِ
داده). **عمداً محلی‌اند:** `_audit/.gitignore` فایل‌های `*.png` و `_audit/*.json` را از مخزن بیرون
می‌گذارد، پس درِ commit فقط harness و این رکورد می‌آید؛ تصاویر رویِ همین ماشین‌اند و برایِ دیدنِ
جدید باید `node dev/fts_layers_e2e_v1.js --symbol فولاد` دوباره اجرا شود.

سه ایرادی که این دور رفع کرد (و پیش از رفع، E2E را red می‌کرد): (۱) `BASE` رویِ `127.0.0.1` رد می‌شد؛
(۲) میزبانِ چارت هرگز ظاهر نمی‌شد چون صفحۀ ورودِ محلی جلویِ مسیر را می‌گرفت؛ (۳) پروب پیش از رسیدنِ
feed اجرا می‌شد و بوم/افسانه/تازگی را تهی می‌دید — `waitForFeed` اضافه شد. ورودی‌هایِ ERR_ABORTEDِ
پیش‌ازِ ورود، لغوِ unmount بی‌خطرند و خطا شمرده نشدند.
