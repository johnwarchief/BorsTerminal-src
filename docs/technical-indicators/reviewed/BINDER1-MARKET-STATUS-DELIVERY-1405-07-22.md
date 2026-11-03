# Binder1 — گزارشِ تحویلِ تب «وضعیت بازار» (مراحل ۱ تا ۷)

تاریخِ اجرا: ۱۴۰۵-07-۲۲ (۲۰۲۶-۱۰-۱۴) · شاخه: `mission/fts-indicator-engineering`
ماتریسِ مرحلۀ ۰: `BINDER1-MARKET-STATUS-CAPABILITY-MATRIX-1405-07-23.md`
مرجعِ تصویری: `Binder1.pdf` → `_audit/binder1_pages/p01.jpg … p13.jpg`

همۀ اعدادِ این گزارش از سه منبعِ *اجراشده* می‌آیند، نه از قرائتِ کد:

| منبعِ شواهد | فایل | نتیجه |
|---|---|---|
| قراردادِ داده رویِ HTTPِ واقعی | `dev/mstat_status_panels_contract_v1.py` | **۲۰۱ بررسی، ۲۰۱ سبز، ۰ سرخ** |
| مرورگرِ واقعی (Edge + Playwright، سه viewport) | `_audit/ms_binder_ui_check.js` → `_audit/MS-BINDER-UI.json` | **۴۷ بررسی، ۴۷ سبز، ۲۶ اسکرین‌شات، ۰ خطای کنسول، ۰ خطای شبکه** |
| تستِ کامپوننت (jsdom) | `frontend` → `npx vitest run` | **۱۷۱۰ سبز، ۳ skip، ۰ سرخ** (۱۶۶ فایل) |

واژۀِ حکم: `DONE_VERIFIED` پیاده + درِ مرورگر دیده شد · `UI_DONE_DATA_BLOCKED` رابط هست،
منبعِ داده نیست · `PARTIAL` بخشی سنجیده شده · `OUT_OF_SCOPE_BY_OWNER_ORDER` به دستورِ مالک.

---

## ۱) ماتریسِ تحویلِ ۱۳ صفحه

هر ۱۳ صفحه ردیابی می‌شود. شباهتِ ۱↔۳ و ۶↔۷ اجازهٔ حذف نبود: کامپوننتِ مشترک
است ولی هر دو مرجع جدا ثبت و جدا سنجیده شده‌اند.

| صفحۀ مرجع | بخش درِ تب | کامپوننت | اندپوینت | حکم | شاهدِ اجرا |
|---|---|---|---|---|---|
| ۱ داشبوردِ بازارِ طلا (نمای اول) | طلا، سکه… | `GoldMarketSection/GoldOverview` | `/api/mstat/gold` | `DONE_VERIFIED` | ۲۴ کارتِ ابزارِ طلا در ۳ viewport؛ حلقه + پوشش «۳ از ۳»؛ هشت موردِ بی‌منبع/محدودیتِ دسترسی با علت |
| ۲ نقشۀ بازار | نقشۀ بازار | `MarketTreemap` | `/api/mstat/treemap` | `DONE_VERIFIED` | ۲۲۰ خانه از ۱۳۶۰ نماد، ۸۴ بی‌معامله درِ چیدامن نمی‌نشیند؛ سطحِ بزرگ‌ترین خانه با عوض‌شدنِ معیار ۳۸٬۴۶۳ → ۲۹٬۳۳۸ px²؛ tooltip = API (`تاصيكو ۸۹٬۶۰۹ عدد` — همان `size` ردیف)؛ کلیک → `/technical/…` |
| ۳ داشبوردِ طلا (نمای دوم، مشابه ۱) | طلا، سکه… | `GoldFunds` (donut + نقشه) | `/api/mstat/gold` + `/api/mstat/treemap?group=gold_fund` | `DONE_VERIFIED` | تبِ «صندوق‌های طلا» هر دو نمایِ مستقل را باز می‌کند؛ درخواستِ `group=gold_fund` دیده شد |
| ۴ گزارش‌های بنیادی | — | — | — | `OUT_OF_SCOPE_BY_OWNER_ORDER` | دستورِ صریحِ مالک: «بنیادی رو نمی‌خواد». درِ ماتریسِ مرحلۀ ۰ ثبت است، بی‌حذفِ بی‌سروصدا |
| ۵ نمودارِ پیشرفته | نمودارِ پیشرفته | `MarketChartSection` → `KLineChartWrapper` (همان موتور) | `/api/chart/<sym>` (خودِ موتور) | `DONE_VERIFIED` (یک کنترل: `PARTIAL`) | ۱۰ canvas درِ کادر؛ انتخابِ نماد از «پرتراکنشِ تابلو» → `GET /api/chart/فزر`؛ تایم‌فریم/تعدیل/ابزارها از خودِ موتور. کلیکِ ردیفِ دیدۀ‌بان فقط درِ jsdom سنجیده شد (دیدۀ‌بانِ پروفایلِ تست خالی بود — برایِ نوشتن درِ دادهٔ کاربر اقدام نشد) |
| ۶ نمایِ کلی | نمایِ کلی | `MarketGlanceCards` + `IndexCards` + بلوک‌هایِ موجود | `/api/mstat/summary`,`/smart-money`,`/depth`,`/thermometer`,`/indexcards` | `DONE_VERIFIED` | سه کارتِ شاخص با یکا/فرمول؛ فقط `tedpix` لینکِ نمودار می‌گیرد، بقیه «بی‌کندل» |
| ۷ نمودارِ وضعیتِ بازار (مشابه ۶) | نمایِ کلی | `BreadthHistogram` + `TimelineCharts` + `SessionPhasesPanel` | `/api/mstat/histogram`,`/timeline`,`/phases` | `DONE_VERIFIED` | توزیعِ درصد با افسانۀ چهارحالتی؛ نمودارهایِ درون‌روزِ همین نشست |
| ۸ برترین‌های بازارِ سهام | برترین‌ها… | `TopListsGrid` (۴ پنل) | `/api/mstat/tops` | `DONE_VERIFIED` | ۴ پنلِ جدا درِ هر viewport؛ پسماندِ اعلام‌شده: جمعِ اثرها −۴۳٬۵۷۶.۸ در برابرِ −۳۴٬۷۷۱.۲ ⇒ ۲۵.۳۲٪ (عمداً برازش نشده) |
| ۹ سفارش‌ها و تغییرِ مالکیت | سفارش‌ها و مالکیت | `OrdersPanel` + `OwnershipPanel` | `/api/mstat/orderflows`,`/ownership` | `DONE_VERIFIED` | سفارش ۳۲٬۶۹۴.۴ ≠ معامله ۱۱۸٬۳۴۹.۹ م.سهم؛ مالکیت −۶۸۰.۶ م.سهم با یکایِ سهم + تراشهٔ تأخیرِ تفکیکِ مشتری |
| ۱۰ داشبوردِ جامعِ طلا | طلا، سکه… | `GoldOverview` (کارت‌ها + روندِ تجمعی) | `/api/mstat/gold` | `DONE_VERIFIED` | روندِ تجمعی با <۲ نقطه خط نمی‌کشد (`ms-gold-trend-nodata`) |
| ۱۱ جدول‌های طلا/سکه/ابزارها | طلا، سکه… | `GoldTables` (سه جدولِ جدا) | `/api/mstat/gold` | `DONE_VERIFIED` | سه جدول درِ همان نشست؛ دانلودِ CSV درِ مرورگر: `طلا-صندوق-2026-10-14_22-50.csv` |
| ۱۲ نقشه و ترکیبِ صندوق‌های طلا | طلا، سکه… | `MarketTreemap(fixedGroup=gold_fund)` + `DonutChart` | `/api/mstat/treemap?group=gold_fund` | `DONE_VERIFIED` | همان کامپوننتِ صفحۀ ۲ با دامنهٔ قفل‌شده؛ بی‌کرکرۀ دامنه؛ «دو نمایِ مستقل» اعلام می‌شود |
| ۱۳ نمودارِ مقایسه‌ای | نمودارِ مقایسه‌ای | `MarketCompareSection` | `/api/mstat/series` + `/api/index/tedpix` | `DONE_VERIFIED` | ۳ خطِ نرمال‌شده رویِ پایۀ ۱۰۰؛ یک درخواستِ batched (بی‌fan-out)؛ `days=182` با تغییرِ بازه؛ مقیاسِ log هندسه را عوض می‌کند |

---

## ۲) قراردادِ داده درِ هر بلوک (مرحلۀ ۳)

قاعدۀ کلی که گارد می‌سنجد: هیچ عددی درِ رابط ساخته نمی‌شود؛ یکا/مبنا/فرمول از
خودِ پاسخ می‌آیند؛ «بی‌داده» ≠ صفر؛ منبعِ نرسیده با علت می‌آید.

| بلوک | یکا | مبنا | فرمولِ اعلام‌شده درِ پاسخ | تازگی |
|---|---|---|---|---|
| treemap | از `metric_unit` (میلیارد تومان / میلیون سهم / عدد) | همان اسکنِ `enrich()` | `formula.pct = p_closing ÷ price_yesterday × 100`؛ `share_pct = size ÷ total_size` (گارد تا ۵e-۴) | `asof.d_even = 20261014` = MAX(d_even) بانک (گارد مستقیم از SQLite می‌سنجد) |
| tops | میلیارد تومان / میلیون سهم / عدد | اثرِ شاخص از وزنِ سهامِ کل | `impact_i = (p_closing − p_yesterday) × total_shares × idx_last ÷ total_market_value` + `delta_cap_b_toman`ِ سنجیده | همان |
| orderflows | میلیون سهم | `buy_q_vol`/`sell_q_vol` (ماندهٔ دفتر) | `buy_order = Σ buy_q_vol`، `executed = q_tot_tran` — دو فیلدِ جدا | همان |
| ownership | میلیون سهم | `buy_n_vol − sell_n_vol` ÷ `total_shares` | `formula.not_to_be_confused` + `pct_of_capital`؛ قرینهٔ دو گروه (گارد: \|legal+real\| < 1e-6) | `client_data_lags_session` اعلام می‌شود |
| indexcards | واحدِ شاخص / ریال | ردیفِ رسمیِ `market_index` | `قیمتِ وزنیِ ارزشی = q_tot_cap ÷ q_tot_tran`؛ `history_points` اعلام می‌شود | `asof_d_even` درِ هر کارت |
| gold | ریال / میلیارد تومان | ردیف‌هایِ واقعیِ تابلو (`cls=fund`, `kind∈{gold,silver}`) | `history_source = price_history (بستۀِ روزانۀِ همین بانک)` | همان + `computed_at` |
| series | ریال | `price_history.close` | مبدأ «پایانیِ خام» صریح اعلام می‌شود (نه «بازدهیِ تعدیل‌شده») | `first_date`/`last_date` به‌ازای نماد |

### جداسازیِ مفهوم‌هایِ نزدیک (سه خطِ قرمزِ مأموریت)
گاردِ `mstat_status_panels_contract_v1.py` این سه را *عدد به عدد* می‌بندد:

1. **حجمِ سفارش ≠ حجمِ معامله** — `buy_order_m_share (۳۲٬۶۹۴.۴) != executed_m_share (۱۱۸٬۳۴۹.۹)`؛
   اگر روزی یکی شدند، گارد می‌ایستد.
2. **اثر بر شاخص ≠ ٪ رشدِ قیمت** — هر ردیفِ `impact_*` هم `impact_points` دارد هم
   `delta_cap_b_toman`، و `impact_points != pct`.
3. **تغییرِ مالکیت ≠ خالصِ ورودِ پول ≠ سرانه** — یکا «میلیون سهم» است و
   `not_to_be_confused` درِ پاسخ اجباری است.

### چیزهایی که عمداً ساخته نشد
- پسماندِ ۲۵.۳۲٪ اثرِ شاخص **اعلام** می‌شود؛ نسخۀ قبلی که با ضریبِ `(pcl/py)`
  به ۰.۷٪ می‌رسید رد شد، چون همان برازش بود (ضریب، کاهنده‌ها را کوچک‌تر نشان
  می‌داد). بلوکرِ `free_float` با `official_attribution_available: false` ثبت است.
- هشت قلمِ بی‌منبعِ طلا (اونسِ جهانی، دلار/تتر، تورم، مسکن، سکهٔ فیزیکی، قیمتِ
  آینده، ارزشِ ذاتی، یک‌گرمِ سکه) فقط **اعلام** می‌شوند؛ هیچ عددی برایشان نیست.
  `forward_price`: «تعریفِ مرجع نامعلوم است»؛ `intrinsic_value`: «پشتِ ورود/عضویت
  قفل است» — به‌عنوانِ محدودیتِ دسترسی ثبت، بدونِ دورزدن.
- نمادهایِ بی‌ردیفِ مرجع (BTCUSD / XAUTBHR / USDTBHR) جعل نمی‌شوند؛ گارد درِ کلِ
  پاسخِ طلا دنبالشان می‌گردد و نبودشان سبز است.
- «۵ سال» بی‌پنج‌سالِ واقعی وعده داده نمی‌شود: `ms-compare-span` روزِ دیدنی را
  می‌نویسد و اگر کمتر از بازۀِ درخواستی بود صریح می‌گوید ««۱ سال»ِ درخواستی
  واقعی نیست».

---

## ۳) تعامل‌ها (مرحلۀ ۴) — آنچه درِ مرورگر کلیک شد

| کنترل | شواهدِ واقعی |
|---|---|
| «اعمال فیلتر» نقشه | پیش از کلیک: درخواستِ تازه‌ای با `metric=trades` **نیست** + تراشۀ «هنوز اعمال نشده»؛ پس از کلیک: `?group=eq_all&industry=&metric=trades` و سطحِ بزرگ‌ترین خانه عوض شد |
| hoverِ خانهٔ نقشه | tooltip «تاصيكو … ۸۹٬۶۰۹ عدد ۲.۷٪» = `{"size":89609,"unit":"عدد","pct":2.74}` همان ردیفِ API |
| کلیکِ خانه | `navigate('/technical/<sym>')` |
| بازه‌هایِ مقایسه (۵سال…۵روز) | `days=182` درِ درخواستِ تازه دیده شد |
| سوییچِ ٪/log | `d`ِ مسیرِ SVG عوض شد |
| تب‌هایِ طلا (۳ تا) | جدول‌ها/نقشه عوض می‌شوند؛ `ms-gold-tbl-{fund,paper}-scroller` و `ms-gold-treemap` |
| دانلودِ CSV | رویدادِ دانلود با نامِ `طلا-صندوق-2026-10-14_22-50.csv` |
| انتخابِ نماد درِ چارت | از «پرتراکنشِ تابلو» → `GET /api/chart/فزر` |
| ناوبریِ بخش‌ها | کلیک → `scrollIntoView` + `aria-current`؛ هایلایت با IntersectionObserver (درِ jsdom با شبیه‌سازِ ثبت‌شده سنجیده شد) |

---

## ۴) بازبینیِ بصری (مرحلۀ ۵)

۲۶ اسکرین‌شات درِ `_audit/MS-BINDER-SHOTS/` — ۸ بخش × ۳ viewport + تصویرِ تمام‌صفحه +
نمایِ پس از انتخابِ نماد.

| سنجه | 1366×768 | 1920×1080 | 390×844 |
|---|---|---|---|
| سرریزِ افقیِ صفحه | ۰ px | ۰ px | ۰ px |
| هر هشت بخش | ✓ | ✓ | ✓ |
| متنِ بریدۀ بی‌جایگزین (بدونِ `title`) | ۰ | ۰ | ۰ |
| حذفِ اختصاریِ با `title` (الگویِ پذیرفتۀ خودِ برنامه) | ۱۶ | ۱۹ | ۴۲ |
| خانه‌هایِ نقشه / خط‌هایِ مقایسه / کارتِ طلا | ۲۲۰ / ۳ / ۲۴ | ۲۲۰ / ۳ / ۲۴ | ۲۲۰ / ۳ / ۲۴ |
| canvasِ موتورِ چارت | ۱۰ | ۱۰ | ۱۰ |
| بلوکِ «بی‌داده» / بلوکِ خطا | ۰ / ۰ | ۰ / ۰ | ۰ / ۰ |

دو نقصِ واقعی که همین بازبینیِ بصری گرفت (نه jsdom):
1. `MarketPulseBar` و برچسبِ انتخابگرِ مقایسه، متنِ بریدۀ **بی‌`title`** داشتند →
   `title` افزوده شد؛ شمارشِ بی‌جایگزین از ۶/۸/۱ به ۰ رسید.
2. `/api/index/tedpix` کندل را با `time` رشته‌ای می‌دهد؛ قراردادِ دست‌سازِ من
   `time: number` بود ⇒ سریِ شاخص بی‌سروصدا حذف می‌شد (۲ خط به‌جای ۳). اکنون
   `toKLine`ِ خودِ فیچرِ تکنیکال مصرف می‌شود و خطای تبدیلِ دوم نمی‌ماند.

---

## ۵) گیت‌ها (مرحلۀ ۶)

| گیت | خروجی |
|---|---|
| `npx tsc -b` | rc=0 |
| `npx vite build` | rc=0 (chunkِ `MarketStatusPage` = ۱۳۱.۳۶ kB، جدا بارگذاری می‌شود) |
| `npx vitest run` | ۱۷۱۰ سبز / ۳ skip / ۰ سرخ — از این شمار ۴۹ بررسیِ تازه درِ ۴ فایلِ تازه است (۲۱ + ۱۶ + ۹ + ۳) |
| `dev/mstat_status_panels_contract_v1.py` | ۲۰۱/۲۰۱ |
| `_audit/ms_binder_ui_check.js` (Edge) | ۴۷/۴۷، ۲۶ شات، ۰ خطای کنسول، ۰ ۴xx/۵xx |
| `dev/persian_glyph_guard.py` | ۴/۴ (نقصِ CJK درِ `design-token-guard.spec.ts` پیدا و درست شد) |
| `dev/mstat_local_v975.py` | ۲۰۷ بررسی، **۱ سرخِ از پیش موجود**: «روزِ ناقص … (20261004)» — کژتابیِ پنجرۀ `market_liquidity`/`daily_prices`، بی‌ربطِ مسیرِ این مأموریت (دیفِ `mstat_engine` فقط `has_mcap_col`/`_row_keys`/`load_snapshot`/`money()` را لمس کرده). هیچ assertion برایِ سبزشدن حذف نشد |
| `npx eslint .` | ۳ خطا، هر سه درِ فایل‌هایِ تستِ **دست‌نخورده** (`engine-klinecharts-adapter.spec.ts` prefer-const، `funnel-preset-switch.spec.tsx` ts-nocheck، `technical-settings-effectiveness.spec.tsx` no-explicit-any) — مالِ این مأموریت نیست و تغییر داده نشد |

### نقصِ سیستمیِ گرفته‌شده درِ همین مسیر
۳۳ بار کلاسِ `accent-amber` درِ ۸ فایل نوشته شده بود وقتی `--color-accent-amber`
تعریف نداشت؛ Tailwind v4 برایِ نامِ تعریف‌نشده **هیچ قاعدهٔ CSS نمی‌سازد** — tsc،
build و حتی مرورگر سبز می‌مانند و فقط رنگ غیب می‌شود. به `accent-yellow` تغییر کرد و
`design-token-guard.spec.ts` نگهبانش شد (خودِ نگهبان هم با نمونۀِ مصنوعی تست
می‌کند که نقص را می‌گیرد، و با `files.length > 80` که بی‌محتوا سبز نشود).

---

## ۶) بازاستفاده (مرحلۀ ۶ مأموریت)

- بنیادی و FTS دوباره پیاده نشدند؛ چارتِ صفحۀ ۵ **همان** `KLineChartWrapper` است
  (lazy) و تنظیمِ تعدیل/تایم‌فریم از `fts.chart.settings.v1` خودش می‌آید.
- `alignCompare` و `toKLine` از `features/technical` بازاستفاده شدند — فرمولِ دومِ
  مقایسه درِ این تب ساخته نشد.
- همۀ پنل‌ها از **یک** اسکنِ `mstat_engine.enrich()` می‌آیند (`mstat_panels.py`) و
  هر کدام درِ `api/market_status.py` پشتِ `_mstat_call` با کشِ ۴۵ ثانیه‌ای keyed روی
  `(fn, args, revision, static_rev, session_day, snap)` نشسته‌اند؛ `/api/mstat/board`
  هم پنل‌هایِ تازه را درِ همان یک سفر می‌دهد.
- هیچ فایلِ بزرگِ یکی‌شده‌ای ساخته نشد: ۱۲ کامپوننت + ۱ لایه + ۱ الگوریتم + ۱ واژۀِ تون.

## ۷) محدودیت‌ها و کارهایِ نمانده

1. **تطابقِ عددی با رهاورد** (مرحلۀ ۵ِ فازهایِ پیشین) برایِ این تب انجام نشد:
   نشستِ مالک درِ Edge درِ دسترسِ این پروفایل نیست و احراز هویت دور زده نمی‌شود.
   تطابقِ این تب فعلاً «ساختار + قراردادِ داده + تعامل» است، نه «برابریِ پیکسلی».
2. کلیکِ ردیفِ **دیدۀ‌بان** درِ مرورگر سنجیده نشد (دیدۀ‌بانِ پروفایل خالی است؛ برایِ
   نوشتن درِ دادهٔ کاربر اقدام نشد). رفتار درِ jsdom با همان قراردادِ API سنجیده شده.
3. `market_cap` درِ بانکِ فعلی هست و معیارِ «ارزشِ بازار» کار می‌کند؛ اگر درِ
   نصبی این ستون را نداشته باشد، گارد ثابت می‌کند که پنل **علت** می‌نویسد و صفر
   نمی‌سازد (سنجیده شد).
4. پسماندِ اثرِ شاخص تا زمانی که «وزنِ سهامِ شناورِ رسمی» منبع ندارد، باقی می‌ماند
   و اعلام می‌شود — این یک محدودیتِ داده است، نه نقصِ رابط.
5. صفحۀ ۴ (بنیادی) به دستورِ مالک بیرونِ دامنه است.

## ۸) فایل‌ها

**تازۀ بک‌اند:** `mstat_panels.py` (۷۸۲ سطر)، `dev/mstat_status_panels_contract_v1.py` (۲۹۹)
**تازۀ فرانت:** `features/market/api/useMarketPanels.ts` (۴۰۵)، `lib/treemapLayout.ts` (۱۲۵)،
`lib/tones.ts` (۷۰)، `components/{StatusShell,MarketSectionNav,MarketTreemap,RankedPanels,OrderOwnershipSection,GoldMarketSection,MarketCompareSection,MarketChartSection,IndexCards,MarketGlanceCards,DonutChart,Sparkline}.tsx` (۲۷۴۰ مجموع)،
`__tests__/{design-token-guard,market-treemap-layout,market-status-sections,market-gold-compare-chart}` (۸۷۶)
**تغییر:** `mstat_engine.py` (عبورِ `market_cap` + چهار حجمِ خامِ خرید/فروش)،
`api/market_status.py` (هفت مسیرِ تازه + پخشِ `board`)،
`routes/MarketStatusPage.tsx` (هشت بخش)، `MarketPulseBar.tsx` و `__tests__/setup.ts`
(شبیه‌سازِ `IntersectionObserver`)، ۳۳ رنگِ `accent-amber` → `accent-yellow`.

**دست‌نخورده:** `market.db` (فقط read-only)، `user.db`، هیچ فایل/کامیت/شاخۀ عاملِ دیگر،
هیچ secret/token/کوکی ثبت یا commit نشد، push/merge/tag انجام نشد.
