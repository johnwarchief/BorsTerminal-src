# مشخصات: S4a — هستهٔ بنیادی در برنامهٔ مهاجرت

- **تاریخ:** ۲۰۲۶-۱۱-۰۴
- **شاخه:** `integration/4axes-main-2026-11-03`
- **وضعیت:** دامنه و cutover توسط مالک تأیید شد (۲۰۲۶-۱۱-۰۴): هستهٔ صفحه، و cutover افزایشی فقط مسیرهای بنیادی به Go.
- **مبنا:** `docs/BorsTerminal-Desktop-Migration-Decisions.md` (§۳، §۴، §۶، §۱۲.۳۸ بند ۱۵، §۱۲.۳۹)، `docs/MIGRATION-REBUILD-PLAN-2026-10-27.md` (S4)، و طلایی‌های `backend-go/internal/fundamental/testdata/golden`.
- **خارج از دامنه:** S4b (تنظیمات آستانه، تقویم/مجمع، DPS، خروجی، P/NAV/هلدینگ، سلول‌های ریز جدول) و materializer مستقل Go برای `fts_results`.

---

## ۱. هدف

صفحهٔ `/fundamental` در `frontend-v2` را به یک صفحهٔ قابل‌استفادهٔ «هسته» برسانیم و مسیر دادهٔ آن را تا حد امکان روی بک‌اند Go ببریم:

1. `/fundamental` — جدول غربالگری همهٔ نمادها با ۵ محور، امتیاز، صنعت و جستجو/مرتب‌سازی.
2. `/fundamental/:symbol` — نمای نماد: خلاصهٔ ۵ محور، کارت‌های تفصیلی، Drill-Down هر محور، روند فصلی، P/E صنعت، نوار تازگی و سلامت کدال.
3. پاریتی کارت بنیادی Go با اوراکل پایتون (شامل `freshness`) و سبزکردن `go test ./...`.
4. مسیر `GET /api/fundamental/freshness` در Go، پیش از `/{symbol}`.

## ۲. شواهد وضعیت فعلی

| ادعا | جا |
|---|---|
| v2 فقط کارت/خلاصه دارد؛ مسیر `/fundamental` نیست | `frontend-v2/src/app/App.tsx`، `frontend-v2/src/app/shell/Sidebar.tsx` |
| صفحهٔ قدیم: جدول + کارت + Drill-Down + فصلی + P/E + سلامت/آپدیت | `frontend/src/features/fundamental/routes/FundamentalPage.tsx` |
| Go فقط `sectors`، `{symbol}/quarters` و `{symbol}` را پورت کرده | `backend-go/internal/httpapi/server.go:224-229` |
| `GET /api/fundamental/screen` در Go `notPortedRoute` است | `server.go:227` |
| `/api/screener` Go فقط زیرمجموعهٔ هسته را برمی‌گرداند و از `fts_results` می‌خواند | `backend-go/internal/screener/screener.go:166-215` |
| `as_of` اسکرینر Go = `time.Now()` (نه روز نشست) | `screener.go:216` |
| ۳ گروه تست `internal/fundamental` قرمز است | `go test ./internal/fundamental` — `TestAx1Ind1aMatchesOracle`، `TestAx1NoSeriesNodataShape`، `TestCardGoldens` |
| `freshness` در کارت/مسیر Go نیست | `routes.json` و `fundamental/handlers.go` |
| نویسندهٔ فعلی `fts_results` updater پایتون است | `dev/codal_fts_updater.py` |

## ۳. معماری و cutover

### ۳.۱. Proxy مسیرمحور (v2)

`frontend-v2/vite.config.ts` یک هدف دوم می‌گیرد:

```
BORS_BACKEND      = پایتون (پیش‌فرض فعلی، 8101)
BORS_BACKEND_GO   = Go (اختیاری؛ مثلاً 8103)
```

اگر `BORS_BACKEND_GO` تنظیم شود، این مسیرها به Go می‌روند و بقیه به پایتون:

- `/api/fundamental`
- `/api/screener`
- `/api/market` (برای P/E صنعت)
- `/api/sync/codal`

قاعدهٔ ترتیب: مسیرهای خاص **پیش از** `/api` عمومی ثبت می‌شوند؛ وگرنه proxy عمومی آن‌ها را می‌بلعد. `/vendor` دست‌نخورده به پایتون می‌ماند.

### ۳.۲. جریان دادهٔ صفحه

```
/fundamental
  جدول:      GET /api/screener            → Go (زیرمجموعهٔ هسته)
  نمای نماد: GET /api/fundamental/{s}     → Go (شامل freshness)
             GET /api/fundamental/{s}/quarters → Go
             GET /api/fundamental/freshness    → Go (برای قرارداد عمومی)
             GET /api/market              → Go (P/E و میانهٔ صنعت)
             GET /api/sync/codal/pipeline → Go (نوار سلامت)
```

**قید صادقانه:** جدول هسته از `fts_results` می‌خواند که فعلاً updater پایتون آن را می‌نویسد. این مرحله «Go-served، Python-fed» است؛ materializer مستقل Go در S4b/S4c. نوار تازگی/سند این وابستگی را پنهان نمی‌کند.

## ۴. قراردادهای Go

### ۴.۱. کارت بنیادی

هدف: `go test ./internal/fundamental` سبز؛ طلایی‌ها اوراکل پایتون‌اند. فهرست شکاف فعلی (از `card_up`/`card_fund`/`card_thin`):

- `indicators.1.monetary.series` در Go اضافه است؛ `indicators.1.reason` غایب.
- `indicators.2.evidence_label` غایب.
- `indicators.3.margin_tier`، `na_kind`، `margin_class`، `net_margin_pct`، `net_margin_period`، `data_gap`، `ideal`، `na`، `reason`، `remediation` غایب؛ چند فیلد اضافی Go (`basis`، `fiscal_year`، `formula`، …) باید حذف/هم‌تراز شوند.
- `indicators.4.acceptance_path`، `annualize_label`، `annualize_months` غایب؛ متن `reason` باید عیناً از اوراکل بیاید.
- `profile.margin_class` غایب.
- `thresholds.mandatory_sectors` باید ۶ عضو باشد؛ `thresholds.reject_insurance` غایب.
- `data_gaps` در `card_fund` باید ۱ عضو باشد (نه ۲).
- `details.۳` در `card_fund` باید calc/source/subchecks اوراکل را داشته باشد.
- `card_thin`: `indicators.1.pass` باید `null` بماند و `reason` بیاید.
- `TestAx1Ind1aMatchesOracle` و `TestAx1NoSeriesNodataShape` باید سبز شوند.

**قاعده:** هیچ فیلد یا فرمولی از خودمان اضافه نمی‌شود؛ منبع، تابع پایتون و طلایی است. تغییرات قبلیِ uncommitted (`axis1.go`، طلایی‌های بازتولیدشده، `prediction_test.go`) بخشی از همین کارند و نباید دور ریخته شوند.

### ۴.۲. Freshness

- `fundamental.Service.Freshness(ctx, symbols)` با همان قرارداد پایتون:
  - `{"symbol","as_of","axes":{"1_growth","2_eps_trend","3_gross_margin","4_sales_to_mcap","5_industry"}}`
  - هر محور: `as_of` (ISO+03:30 یا date-only)، `source`، `tracing_no`، `period_end`، `state` (`fresh/stale/missing/quarantined`)، `reason`.
  - `state` precedence: quarantined > stale > missing > fresh.
  - `as_of` کلی = قدیمی‌ترین محور بنیادی ۱/۲/۳.
- کارت `GET /api/fundamental/{symbol}` کلید `freshness` را برمی‌گرداند.
- مسیر `GET /api/fundamental/freshness` با `symbols` اختیاری؛ پیش‌فرض ۲۰۰ سهم؛ **پیش از** `/{symbol}`.
- تست: fixture با monthly/FS/board/quarantine؛ ترتیب route؛ goldens کارت شامل freshness.

### ۴.۳. اسکرینر هسته

- `GET /api/screener` همان زیرمجموعهٔ فعلی Go کافی است: `symbol`، `symbol_norm`، `name`، `sector_name`، `score`، `verdict`، `excluded`، `i1_pass`..`i5_pass`.
- **محدودیت صادقانه:** این زیرمجموعه `i*_na` ندارد؛ پس جدول هسته فقط می‌تواند «قبول» را سبز نشان دهد و برای غیرقبول «—» بگذارد. تفکیک «رد» از «بی‌نظر» فقط در کارت نماد است. برای نمادهای `excluded` یک نشان «خارج از پنج‌شاخص» نمایش داده می‌شود. سلول‌های ریز و تفکیک NA در S4b.
- `as_of` از `MAX(d_even)` تابلو خوانده شود، نه `time.Now()`.
- تست: `as_of` = روز نشست؛ قرارداد فیلدها ثابت بماند.
- `/api/fundamental/screen` همچنان `notPortedRoute` می‌ماند؛ صفحهٔ هسته از آن استفاده نمی‌کند.

## ۵. صفحهٔ v2

### ۵.۱. مسیرها و ناوبری

- `/fundamental` و `/fundamental/:symbol` در `App.tsx`.
- آیتم «بنیادی» در `Sidebar.tsx` از حالت غیرفعال به `live` تبدیل می‌شود.
- کلیک ردیف جدول → `/fundamental/:symbol`؛ بازگشت به جدول با لینک/دکمه.

### ۵.۲. جدول هسته

ستون‌ها: نماد، صنعت، ۵ نشان «قبول»/«—»، امتیاز ۰–۵. جستجو بر نماد/نام، فیلتر صنعت، مرتب‌سازی امتیاز. ردیف‌ها مجازی‌شده. تفکیک «رد» از «بی‌نظر» و سلول‌های ریز (تاریخچهٔ EPS، دلیل هر محور، نشان تازگی سلولی) در S4b؛ در این مرحله کارت نماد مرجع دقیق وضعیت است و جدول هیچ حکمِ ردِ جعلی نمی‌سازد. نمادهای `excluded` نشان «خارج از پنج‌شاخص» می‌گیرند.

### ۵.۳. نمای نماد

- سربرگ: نماد، صنعت، نشان تازگی (از کارت)، لینک بازگشت.
- خلاصهٔ «X از ۵ محور» با `FundamentalSummary`.
- کارت‌های ۵ محور با `FundamentalCards`.
- Drill-Down هر محور از `details` واقعی کارت: عنوان، فرمول، منبع، calc، what، subchecks؛ کلیک روی محور باز/بسته می‌شود. هیچ متن یا عدد ساختگی.
- روند فصلی از `/quarters`؛ P/E نماد و میانهٔ صنعت از `/api/market`.
- نوار سلامت کدال از `/api/sync/codal/pipeline`: آخرین موفقیت، صف، quarantined، gap flag.
- حالت‌ها: loading، empty، خطای Go، نماد بی‌کارت، `data_gap`، صندوق/N/A، quarantined/stale؛ همه با متن صریح.

### ۵.۴. فایل‌های پیشنهادی

| فایل | مسئولیت |
|---|---|
| `frontend-v2/src/features/fundamental/routes/FundamentalPage.tsx` | مسیر و حالت جدول/نماد |
| `frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx` | جدول هسته |
| `frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx` | نمای نماد |
| `frontend-v2/src/features/fundamental/ui/AxisDrilldown.tsx` | پنل هر محور |
| `frontend-v2/src/features/fundamental/ui/QuarterlyTrend.tsx` | روند فصلی |
| `frontend-v2/src/features/fundamental/ui/CodalHealthStrip.tsx` | سلامت کدال |
| `frontend-v2/src/features/fundamental/api/useScreenerCore.ts` | اسکرینر هسته |
| `frontend-v2/src/features/fundamental/api/useQuarters.ts` | quarters |
| `frontend-v2/src/features/fundamental/api/useSectorPe.ts` | P/E و میانه |
| `frontend-v2/src/features/fundamental/api/useCodalHealth.ts` | سلامت |
| `frontend-v2/vite.config.ts` | proxy مسیرمحور |
| `frontend-v2/src/app/App.tsx`، `Sidebar.tsx` | مسیر/ناوبری |

## ۶. پذیرش و آزمون

1. `go build ./...` و `go test ./...` سبز؛ `internal/fundamental` صفر FAIL.
2. پاریتی ۱۰ نماد (کارت شامل freshness + quarters) بین پایتون و Go روی همان DB؛ تفاوت فقط فیلدهای غیرقطعیِ تعریف‌شده، وگرنه شکست.
3. `GET /api/fundamental/freshness` در Go با قرارداد بالا؛ route order تست شود.
4. `as_of` اسکرینر = روز نشست؛ تست.
5. v2 روی Go (پورت آزمایشی + proxy): جدول تعداد/امتیاز/پاس‌ها = Go؛ ۱۰ نماد نمونه = کارت Go؛ Drill-Down باز می‌شود؛ فصلی/P/E/سلامت رندر می‌شوند؛ اسکرین‌شات ۱۳۶۶×۷۶۸ و ۱۹۲۰×۱۰۸۰؛ بدون خطای کنسول.
6. بدون تغییر فرمول/آستانهٔ FTS یا `codal_periods`؛ بدون جدول تازه در `market.db`.

## ۷. ریسک‌ها

- **پاریتی کارت Go بزرگ است:** فقط با اوراکل و طلایی؛ هیچ فیلد بی‌شاهد.
- **وابستگی جدول به `fts_results` پایتون:** صریح در سند/نوار؛ materializer در S4b.
- **proxy مسیرمحور:** ترتیب و آزمون شبکه؛ اگر Go پاسخ نداد، خطای صریح، نه fallback خاموش.
- **freshness در کارت:** طلایی‌ها بازتولید می‌شوند؛ کارت Go باید کلید را دقیقاً بسازد.

## ۸. تصمیم‌های اجرایی

- جدول هستهٔ compact؛ سلول‌های ریز S4b.
- `GET /api/fundamental/screen` فعلاً پورت نمی‌شود؛ صفحه از `/api/screener` هسته استفاده می‌کند.
- `fts_results` فعلاً Python-fed است؛ این یک قید موقت اعلام‌شده است، نه ادعای استقلال Go.
- تنظیمات/تقویم/DPS/خروجی/P/NAV در S4b.
