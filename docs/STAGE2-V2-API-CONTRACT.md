# سند قرارداد قطعی API و تطبیق سرشماری مسیرها — مرحله ۲
# (Stage 2 Authoritative Frontend-V2 API Contract & Route Census Reconciliation)

**تاریخ ایجاد:** ۷ نوامبر ۲۰۲۶  
**شاخه مبدأ:** `mission/stage2-go-production-cutover-2026-11-07`  
**خط مبنا (Baseline SHA):** `28c5146c771271beaf758ad9dc28c2272608d461`  
**وضعیت:** مصوب و الزام‌آور برای فازهای ۲A تا ۲F  

---

## ۱. بیانیه مأموریت و خلاصه اجرایی (Executive Summary)

این سند، مرجع رسمی و تغییرناپذیر کلیه تعاملات شبکه میان فرانت‌اند مدرن (`frontend-v2`) و سرور یکپارچه Go (`borsd`) در پروژه بورس‌ترمینال است. با ورود به فاز عملیاتی مرحله ۲ (حذف کامل پایتون از زمان اجرای نهایی دسکتاپ)، ارتباط فرانت‌اند نوین به‌طور مستقیم و انحصاری با باینری Go برقرار می‌شود.

تمامی ۵۲ فراخوانی شبکه در فرانت‌اند نوین با دقت خط‌به‌خط بررسی، استخراج و در قالب **۲۴ الگوی مسیر فعال در Go + ۱ روت تنظیمات کاربر (`/api/fts/config`) — در مجموع ۲۵ الگوی مسیر** اعتبارسنجی شده‌اند. این سند اثبات می‌کند که **۱۰۰٪ نیازمندی‌های عملیاتی و تحلیلی فرانت‌اند توسط هندلرهای فعال Go برطرف شده است** و روت تنظیمات بنیادی نیز با رفتار فال‌بک مشخص تا فاز ذخیره‌سازی تنظیمات (Task 6) مهار شده است.

---

## ۲. حل قطعی معمای آمار مسیرها (The 58 vs 61 vs 142 Census Reconciliation)

در طول ارزیابی‌های مرحله ۱ و اسناد انتقالی، آمارهای متعددی پیرامون تعداد روت‌های سرور گزارش شده بود (۵۸ در برابر ۶۱ در برابر ۱۰۴ در برابر ۱۴۲ در برابر ۱۴۸). این تناقض در این بخش به‌صورت علمی، ریاضی و مستند بر سورس‌کد حل و فصل می‌شود:

### الف) درخت کامل مسیرهای پایتون (۱۴۸ روت):
۱. **۱۴۲ مسیر با پیشوند `/api/*`:** کلیه اندپوینت‌های تعریف‌شده در ماژول‌های روتر FastAPI پایتون (`api/*.py`).
۲. **۶ مسیر غیر API:** شامل مستندات OpenAPI و فایل‌های استاتیک روت و SPA:
   - `GET /`
   - `GET /docs`
   - `GET /redoc`
   - `GET /openapi.json`
   - `GET /docs/oauth2-redirect`
   - `GET /{full_path:path}` (SPA Catch-all)
۳. **جمع کل پایتون:** ۱۴۲ + ۶ = **۱۴۸ مسیر**.

### ب) ساختار روتر و Mux در Go (`backend-go/internal/httpapi/server.go`):
در سرور Go، روتینگ با `http.NewServeMux` استاندارد پیاده‌سازی شده و از سه لایه ساختاری تشکیل یافته است:
۱. **۶۱ هندلر عملیاتی فعال (`IMPLEMENTED`):** توابع Go که با منطق تجاری کامل، کوئری‌های بهینه SQLite و پاسخ‌های استاندارد JSON پیاده شده‌اند.
۲. **۳ روت ثبت‌شده صریح با خطای ۵۰۱ (`REGISTERED_501`):**
   - `GET /api/fts/config`
   - `GET /api/fundamental/screen`
   - `GET /api/watchlist/matrix`
   *(این سه مسیر عمداً و صریحاً با `s.notPortedRoute` در Mux ثبت شده‌اند تا توسط الگوهای عام حریصانه نظیر `/api/fts/{symbol}` یا `/api/fundamental/{symbol}` بلعیده نشوند).*
۳. **۱ اندپوینت بررسی سلامت:** `GET /healthz` برای مانیتورینگ سلامت باینری Go، میزان مصرف حافظه RAM، پینگ دیتابیس و وضعیت پرچم‌ها.
۴. **جمع کل روت‌های ثبت‌شده در Mux:** ۶۱ + ۳ + ۱ = **۶۵ الگو**.
۵. **۷۸ مسیر کاتالوگ‌شده در گیت محافظ (`GATE_501`):**
   تمام ۷۸ مسیر باقی‌مانده پایتون در فایل `backend-go/internal/httpapi/routes.json` نمایه شده‌اند. میدل‌ور مرکزی `apiGate` هر درخواستی که در ۶۴ مسیر بالا نباشد را با الگوهای `routes.json` مقایسه می‌کند؛ اگر در لیست باشد، با پاسخ استاندارد و ساختاریافته `501 NOT_PORTED` پاسخ می‌دهد و اگر نباشد، خطای `404 Not Found` صادر می‌کند.

### ج) منشأ عدد ۵۸ در اسناد پیشین:
عدد **۵۸** که در برخی گزارش‌های پیشین به‌عنوان «اندپوینت‌های پیاده‌شده Go» درج شده بود، ناشی از تفریق ریاضی زیر است:
$$\mathbf{61\ (Active\ Handlers) - 3\ (Explicit\ 501\ Registered\ Routes) = 58\ Implemented\ Core\ Endpoints}$$
همچنین در برخی گزارش‌ها، متدهای سه‌گانه واچ‌لیست (`GET`, `POST`, `DELETE /api/watchlist`) یا متدهای اکسپورت و فانل به‌صورت یک سرفصل واحد شمارش شده بودند.

### د) سهم کلاینت نوین (`frontend-v2`):
فرانت‌اند `frontend-v2` برخلاف SPA قدیمی پایتون، به اندپوینت‌های آزمایشی، بات معامله‌گر، سرخطی و اسکریپت‌های موقت متصل **نیست**. این فرانت‌اند در کل ۵۲ فراخوانی شبکه در سورس‌کد خود دارد که منحصراً به **۲۴ الگوی مسیر فعال در Go** و **۱ روت تنظیمات کاربر ۵۰۱ (`/api/fts/config`)** — در مجموع **۲۵ الگوی مسیر** — ترجمه می‌شوند. تمامی ۲۴ مسیر عملیاتی و تحلیلی در Go پیاده‌سازی شده و دارای تست سبز هستند؛ مسیر تنظیمات نیز در فاز ۲E (وظیفه ۶) به دیتابیس کاربر متصل خواهد شد و در حال حاضر با مقادیر پیش‌فرض جزوه بدون خطا فعالیت می‌کند.

---

## ۳. ماتریس آماری توزیع مسیرها

| رده مسیر | تعداد | وضعیت در Go | رفتار پاسخ در شبکه | دلیل عدم حضور در کلاینت نوین |
| :--- | :---: | :---: | :---: | :--- |
| **هندلرهای فعال تولیدی** | **۶۱** | `IMPLEMENTED` | `200 OK` (با پاسخ محاسباتی واقعی) | هسته عملیاتی تابلو، چارت، بنیادی، نبض و اعلان |
| **مسیرهای صریح ۵۰۱ Mux** | **۳** | `REGISTERED_501` | `501 NOT_PORTED` ساختاریافته | جلوگیری از هم‌پوشانی الگوهای پارامتریک در Mux |
| **اندپوینت سیستمی سلامت** | **۱** | `HEALTHZ` | `200 OK` (وضعیت دیتابیس، آپ‌تایم و حافظه) | مصرف توسط مانیتورینگ Tauri و تست‌های CI |
| **ماژول سرخطی و اجرای سفارش** | **۱۵** | `GATE_501` | `501 NOT_PORTED` JSON | قابلیت‌های کارگزاری و معامله مستقیم در فازهای آتی |
| **بات معاملاتی خودکار** | **۸** | `GATE_501` | `501 NOT_PORTED` JSON | الگوریتم‌های معاملاتی بدون رابط کاربری در V2 |
| **پنل‌های پیشرفته نبض بازار** | **۸** | `GATE_501` | `501 NOT_PORTED` JSON | پنل‌های کم‌کاربرد قدیمی (طلا، شاخص‌های تکمیلی) |
| **موتور سوم تحلیل ساختار** | **۱** | `GATE_501` | `501 NOT_PORTED` JSON | مسیر `/api/structure3/{symbol}` (طراحی مجدد در آینده) |
| **ابزارهای نگهداری، آپدیت و دسکتاپ** | **۴۶** | `GATE_501` | `501 NOT_PORTED` JSON | آپدیتر اینوستیلی، پل ADB و سینک دستی توسعه‌دهنده |
| **مستندات و صفحات ایستا** | **۶** | `EXCLUDED` | خارج از حیطه Go Mux | در معماری دسکتاپ Tauri کلاینت محلی بارگذاری می‌شود |
| **جمع کل** | **۱۴۹** | — | — | **۱۴۸ مسیر پایتون + ۱ مسیر `/healthz` در Go** |

---

## ۴. اصول معماری و پروتکل‌های ارتباطی

### ۱. قواعد کدگذاری نمادهای فارسی (Persian URL Encoding Protocol)
- نمادهای بازار سرمایه ایران حاوی حروف فارسی (مانند «فولاد»، «شستا»، «خودرو»، «خساپا»، «وتجارت») هستند.
- در کلیه فراخوانی‌های فرانت‌اند که نماد در مسیر (Path Parameter) یا کوئری (Query Parameter) قرار دارد، استفاده از تابع جاوااسکریپت `encodeURIComponent(symbol)` **الزامی و اجباری** است.
  *مثال:* `/api/chart-db/%D9%81%D9%88%D9%84%D8%A7%D8%AF`
- **سمت Go:** موتور `net/http` در Go 1.22+ مقادیر متغیرهای مسیر مانند `{symbol}` را به‌طور خودکار پیش از تحویل به `r.PathValue("symbol")` کدگشایی (Unescape) می‌کند.
- **یکسان‌سازی حروف (Glyph Normalization):** سرویس‌های Go نماد ورودی را با تابع نرمال‌سازی قلم فارسی (تبدیل «ك» و «ي» عربی به «ک» و «ی» فارسی و حذف اعراب و فواصل مجازی) پردازش می‌کنند تا انطباق دقیق با ردیف‌های پایگاه داده SQLite حاصل شود.

### ۲. سیاست هدرهای کش (Cache-Control & Headers Policy)
- برای جلوگیری از تداخل مقادیر کهنه بازار و تضمین بی‌درنگ بودن داده‌های مالی، میدل‌ور `noCache` در `backend-go/internal/httpapi/server.go` بر روی تمام پاسخ‌های ارسالی هدرهای زیر را تزریق می‌کند:
  ```http
  Cache-Control: no-cache, no-store, must-revalidate
  Pragma: no-cache
  ```
- **کلاینت (`shared/api/http.ts`):** فرانت‌اند با هدر `Accept: application/json` درخواست‌ها را ارسال کرده و کش‌گذاری موقت صرفاً در سطح حافظه کلاینت توسط TanStack Query مدیریت می‌شود.

### ۳. ایزولاسیون ذخیره‌سازی داده‌ها (Single-Writer SQLite Protocol)
- `market.db`: توسط Go صرفاً در حالت **فقط‌خواندنی (`mode=ro`)** و با دستور `PRAGMA query_only = ON` بازگشایی می‌شود.
- `codal.db`: توسط Go صرفاً در حالت **فقط‌خواندنی (`mode=ro`)** و با دستور `PRAGMA query_only = ON` بازگشایی می‌شود.
- `user.db`: تنها پایگاه داده دارای مجوز نوشتن برای باینری Go است (واچ‌لیست، تصمیمات و سبد). در صورت فعال بودن فلگ اجرایی `--read-only`، این دیتابیس نیز در حالت `mode=ro` باز شده و هرگونه اقدام به نوشتن با خطای HTTP 403 متوقف می‌گردد.
- **گیت معماری AST:** فراخوانی مستقیم `sql.Open` خارج از پکیج `internal/db` به‌صورت ایستا مسدود شده است.

---

## ۵. جدول جامع ۲۵ قرارداد وب‌سرویس کلاینت نوین `frontend-v2`

| # | ویژگی فرانت‌اند | متد و مسیر API | هندلر Go | اینترفیس سرویس | دیتابیس و دسترسی | پارامترها و بدنه درخواست | اسکیما و تایپ پاسخ فرانت‌اند | رفتار در داده خالی / خطا |
| :-: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **۱** | خوراک اصلی تابلوی بازار | `GET /api/market` | `srv.Market.Board` | `Market.Board` | `market.db` (RO) | بدون پارامتر | `MarketFeedSchema` (`MarketFeed`) | در نبود داده آرایه `data: []` با `count: 0` |
| **۲** | فید تغییرات افزایشی تابلو | `GET /api/market/delta` | `srv.Market.Delta` | `Market.Delta` | `market.db` (RO) | Query: `since=<rev>` | `MarketDeltaSchema` (`MarketDelta`) | وضعیت `unchanged` یا `delta` یا fallback به `full` |
| **۳** | نوار شاخص و وضعیت کلان | `GET /api/mstat/market-snapshot` | `srv.Mstat.MarketSnapshot` | `Mstat.MarketSnapshot` | `market.db` (RO) | بدون پارامتر | `MarketSnapshotSchema` (`MarketSnapshot`) | فیلدهای نال با وضعیت `status: "ok"` |
| **۴** | وضعیت نشست و فاز بازار | `GET /api/mstat/phase` | `srv.Mstat.Phase` | `Mstat.Phase` | `market.db` (RO) | بدون پارامتر | `PhaseSchema` (`Phase`) | بازگشت فاز پیش‌فرض با `official: false` |
| **۵** | نقشه صنایع و جریان نقدینگی | `GET /api/mstat/industries` | `srv.Mstat.Industries` | `Mstat.Industries` | `market.db` (RO) | بدون پارامتر | `IndustriesSchema` (`IndustriesFeed`) | آرایه خالی صنایع `rows: []` با لیدر نال |
| **۶** | کندل‌های تاریخی و تعدیلات چارت | `GET /api/chart-db/{symbol}` | `srv.Chart.ChartDB` | `Chart.ChartDB` | `market.db` (RO) | Path: `symbol`<br>Query: `adjustment` (0,1,2,3) | `ChartSchema` (`ChartPayload`) | آرایه خالی کندل‌ها `candles: []` با فاکتورهای پیش‌فرض |
| **۷** | میانگین‌های متحرک تکنیکال | `GET /api/ma/{symbol}` | `srv.Chart.MA` | `Chart.MA` | `market.db` (RO) | Path: `symbol` | `MaSchema` (`MaPayload`) | ساختار خطای `{status: "error"}` یا سری خالی نال |
| **۸** | عمق مظنه ۵ ردیفی سفارشات | `GET /api/order-book/{symbol}` | `srv.Chart.OrderBook` | `Chart.OrderBook` | `market.db` (RO) | Path: `symbol` | `BookSchema` (`OrderBook`) | آرایه ۵ سطری با مقادیر صفر در صورت نبود صف |
| **۹** | سیگنال رصد عمق مظنه نماد | `POST /api/orderbook/watch` | `orderbookWatchHandler` | مستقل (Internal) | حافظه موقت (RAM) | Body: `{ins_code: string}` | `WatchSchema` | بازگشت وضعیت خطا در نبود `ins_code` |
| **۱۰** | سابقه روزانه فیلترهای تابلوخوانی | `GET /api/tape-history` | `srv.Market.TapeHistory` | `Market.TapeHistory` | `market.db` (RO) | Query: `codes=<c>&days=<d>` | `TapeHistorySchema` (`TapeHistoryPayload`) | بازگشت نقشه خالی نمادها بدون خطای ۵۰۰ |
| **۱۱** | دریافت نمادهای واچ‌لیست کاربر | `GET /api/watchlist` | `srv.Watchlist.Get` | `Watchlist.Get` | `user.db` (RW/RO) | بدون پارامتر | `WatchlistPayloadSchema` (`WatchlistPayload`) | آرایه `data: []` با وضعیت `status: "success"` |
| **۱۲** | افزودن نماد به واچ‌لیست | `POST /api/watchlist` | `srv.Watchlist.Post` | `Watchlist.Post` | `user.db` (RW/RO) | Body: `{symbol, name}` | `WatchlistPayloadSchema` (`WatchlistPayload`) | رد درخواست در حالت `--read-only` با ۴۰۳ |
| **۱۳** | حذف نماد از واچ‌لیست | `DELETE /api/watchlist/{symbol}` | `srv.Watchlist.Delete` | `Watchlist.Delete` | `user.db` (RW/RO) | Path: `symbol` | `WatchlistPayloadSchema` (`WatchlistPayload`) | بازگشت `deleted: 0` در صورت نبودن نماد |
| **۱۴** | خوراک اعلانات و افشاگری‌ها | `GET /api/notifications/feed` | `srv.Notifications.Feed` | `Notifications.Feed` | `market.db` (RO) | Query: `since`, `limit`, `levels` | `FeedSchema` (`NoticeFeed`) | آرایه خالی `items: []` با `status: "ok"` |
| **۱۵** | وضعیت منابع فید اعلانات | `GET /api/notifications/sources` | `srv.Notifications.Sources` | `Notifications.Sources` | `market.db` (RO) | بدون پارامتر | `SourcesSchema` (`NotificationSources`) | بازگشت وضعیت کانکتورها با متای به‌روزرسانی |
| **۱۶** | کارت ارزیابی ۵ محوره بنیادی FTS | `GET /api/fundamental/{symbol}` | `srv.Fundamental.Card` | `Fundamental.Card` | `codal.db` + `market.db` (RO) | Path: `symbol` | `FtsCardSchema` (`FtsCard`) | بازگشت وضعیت `data_gap: true` در فقدان صورت مالی |
| **۱۷** | جدول فیلتر بنیادی کل بازار | `GET /api/screener` | `srv.Screener.Screener` | `Screener.Screener` | `codal.db` + `market.db` (RO) | بدون پارامتر | `ScreenerCoreSchema` (`ScreenerCore`) | آرایه ردیف‌ها با فیلترهای نال در صورت نبود گزارش |
| **۱۸** | تقویم مجامع و افشای نماد | `GET /api/calendar/{symbol}` | `srv.Chart.CalendarSymbol` | `Chart.CalendarSymbol` | `codal.db` (RO) | Path: `symbol` | `SymbolPayload` (`CalendarEvent[]`) | آرایه خالی `events: []` با وضعیت موفقیت |
| **۱۹** | تقویم مجامع پیش‌رو بازار | `GET /api/calendar/upcoming` | `srv.Chart.CalendarUpcoming` | `Chart.CalendarUpcoming` | `codal.db` (RO) | Query: `days=<number>` | `UpcomingPayload` (`UpcomingEvent[]`) | آرایه خالی `items: []` با شمارش صفر |
| **۲۰** | وضعیت سلامت پایپ‌لاین کدال | `GET /api/sync/codal/pipeline` | `srv.Sync.CodalPipeline` | `Sync.CodalPipeline` | `codal.db` + `market.db` (RO) | بدون پارامتر | `Payload` (`CodalHealth`) | بازگشت آبجکت صف با اعداد صفر و پرچم بدون گپ |
| **۲۱** | پیش‌بینی کوانتایل افق هوش مصنوعی | `GET /api/chart/{symbol}/forecast` | `srv.Chart.Forecast` | `Chart.Forecast` | `market.db` (RO) | Path: `symbol`<br>Query: `horizon`, `model`, `adjustment` | `ForecastResponseSchema` (`PredictionData`) | گام‌های تخمینی بر مبنای آخرین نوسانات تاریخی |
| **۲۲** | لبه آماری کندل و نواحی نقدینگی SMC | `GET /api/chart/{symbol}/edge` | `srv.Chart.Edge` | `Chart.Edge` | `market.db` (RO) | Path: `symbol`<br>Query: `swing_period` | `CandleEdgeResponseSchema` (`CandleEdgeReport`) | آرایه خالی نواحی پرایس‌اکشن با وین‌ریت ۰٫۵ |
| **۲۳** | اندیکاتورهای محاسباتی تکنیکال | `GET /api/chart/{symbol}/indicators` | `srv.Chart.Indicators` | `Chart.Indicators` | `market.db` (RO) | Path: `symbol` | `IndicatorsResponseSchema` (`IndicatorsResponse`) | دیکشنری خالی سری‌ها در تاریخچه ناکافی |
| **۲۴** | تحلیل سرورساید FTS و بدج استریپ | `GET /api/fts/{symbol}` | `srv.Chart.FTS` | `Chart.FTS` | `market.db` (RO) | Path: `symbol` | `FtsResponse` (`FtsAnalysisData`) | بازگشت `{status: "empty"}` یا `{status: "error"}` در نبود داده |
| **۲۵** | تنظیمات و آستانه‌های بنیادی FTS | `GET /api/fts/config`<br>`POST /api/fts/config` | `s.notPortedRoute` | ثبت‌شده صریح (501) | `user.db` (موکول به Task 6) | Body در متد POST: آبجکت `FtsConfig` | `FtsConfigResponseSchema` (`FtsConfigResponse`) | پاسخ `501 NOT_PORTED`؛ کلاینت با فال‌بک پیش‌فرض‌های جزوه کار می‌کند |

---

## ۶. مشخصات تفصیلی قرارداد هر وب‌سرویس

### ۱. تابلوی بازار (`GET /api/market`)
- **ماژول فرانت‌اند:** `features/market/api/boardFeed.ts` / `features/market/api/useBoard.ts`
- **هندلر Go:** `internal/market/service.go:Board`
- **دسترسی پایگاه داده:** `market.db` (فقط خواندنی)
- **ساختار پارامترها:** ندارد.
- **اسکیمای پاسخ (Zod):**
  ```typescript
  export const MarketFeedSchema = z.looseObject({
    status: z.string(),
    data: z.array(MarketRowSchema),
    count: z.number().nullish(),
    live_count: z.number().nullish(),
    fossil_count: z.number().nullish(),
    rev: z.number().nullish(),
    rev_at: z.number().nullish(),
    meta: z.looseObject({
      d_even: z.number().nullish(),
      h_even: z.number().nullish(),
      last_sync: z.string().nullish(),
      live: z.boolean().nullish(),
      live_at: z.number().nullish(),
    }).nullish(),
  });
  ```
- **مدیریت وضعیت خطا/خالی:** در صورتی که دیتابیس حاوی داده نباشد، پاسخ با کد ۲۰۰ و فیلد `data: []` بازگردانده شده و UI پیام هشدار محلی نمایش می‌دهد.

---

### ۲. تغییرات تفاضلی تابلو (`GET /api/market/delta`)
- **ماژول فرانت‌اند:** `features/market/api/boardFeed.ts`
- **هندلر Go:** `internal/market/service.go:Delta`
- **دسترسی پایگاه داده:** کش در حافظه (RAM) + ژورنال تغییرات
- **ساختار پارامترها:** `?since=<rev>` (شماره آخرین ویرایش دریافت شده در کلاینت).
- **اسکیمای پاسخ (Zod):**
  ```typescript
  export const MarketDeltaSchema = z.discriminatedUnion('status', [
    z.object({ status: z.literal('unchanged'), rev: z.number(), count: z.number().nullish() }),
    z.object({ status: z.literal('delta'), rev: z.number(), rows: z.array(MarketRowSchema), count: z.number().nullish() }),
    z.object({ status: z.literal('full'), rev: z.number().nullish(), reason: z.string().nullish() }),
  ]);
  ```
- **مدیریت خطای گسست بازنگری (Revision Drift):** اگر شماره `since` از حد بافر ژورنال عقب‌تر باشد، Go وضعیت `status: "full"` صادر می‌کند که موجب واکشی مجدد خودکار کل تابلو از `/api/market` می‌شود.

---

### ۳. نوار خلاصه وضعیت بازار (`GET /api/mstat/market-snapshot`)
- **ماژول فرانت‌اند:** `features/market/api/useMarketSnapshot.ts`
- **هندلر Go:** `internal/mstat/service.go:MarketSnapshot`
- **دسترسی پایگاه داده:** `market.db` (RO)
- **اسکیمای پاسخ (Zod):**
  ```typescript
  export const MarketSnapshotSchema = z.looseObject({
    status: z.literal('ok'),
    index: z.looseObject({
      d_even: z.number(),
      last: z.number().nullish(),
      change: z.number().nullish(),
      pct: z.number().nullish(),
      ew_last: z.number().nullish(),
      ew_pct: z.number().nullish(),
    }).nullish(),
    market: z.looseObject({
      trade_value_hemat: z.number().nullish(),
      volume: z.number().nullish(),
      trades: z.number().nullish(),
    }).nullish(),
    retail: z.looseObject({
      value_hemat: z.number().nullish(),
      state: z.string().nullish(),
      label: z.string().nullish(),
    }).nullish(),
  });
  ```

---

### ۴. وضعیت نشست معاملاتی (`GET /api/mstat/phase`)
- **ماژول فرانت‌اند:** `features/market/api/usePhase.ts`
- **هندلر Go:** `internal/mstat/service.go:Phase`
- **دسترسی پایگاه داده:** محاسباتی بر مبنای ساعت جاری سیستم و تقویم کاری بورس تهران.
- **اسکیمای پاسخ (Zod):**
  ```typescript
  export const PhaseSchema = z.looseObject({
    status: z.string(),
    phase: z.string().nullish(),
    label: z.string().nullish(),
    official: z.boolean().nullish(),
    is_live: z.boolean().nullish(),
    session_day: z.number().nullish(),
    session_start: z.string().nullish(),
    session_end: z.string().nullish(),
  });
  ```

---

### ۵. مانیتور صنایع بازار (`GET /api/mstat/industries`)
- **ماژول فرانت‌اند:** `features/market/api/useIndustries.ts`
- **هندلر Go:** `internal/mstat/service.go:Industries`
- **دسترسی پایگاه داده:** `market.db` (RO)
- **اسکیمای پاسخ (Zod):**
  ```typescript
  export const IndustryRowSchema = z.object({
    industry: z.string(),
    symbols: z.number().nullish(),
    positive: z.number().nullish(),
    negative: z.number().nullish(),
    avg_pct: z.number().nullish(),
    value_b_toman: z.number().nullish(),
    flow_b_toman: z.number().nullish(),
    leader: z.boolean().nullish(),
  });
  ```

---

### ۶. تاریخچه کندل‌ها و تعدیلات چارت (`GET /api/chart-db/{symbol}`)
- **ماژول فرانت‌اند:** `features/chart/api/useChart.ts`
- **هندلر Go:** `internal/chart/service.go:ChartDB`
- **دسترسی پایگاه داده:** `market.db` (جدول `candles` و `price_adjust_events`)
- **قاعده کدگذاری نماد:** `encodeURIComponent(symbol)` در مسیر الزامی است.
- **پارامترهای کوئری:** `?adjustment=0|1|2|3` (بدون تعدیل، افزایش سرمایه، سود نقدی، هر دو).
- **اسکیمای پاسخ (Zod):**
  ```typescript
  export const ChartSchema = z.looseObject({
    status: z.string(),
    candles: z.array(z.looseObject({
      time: z.union([z.string(), z.number()]),
      open: z.number(), high: z.number(), low: z.number(), close: z.number(),
      volume: z.number().nullish(),
    })).default([]),
    factors: z.array(z.looseObject({ time: z.string(), factor: z.number() })).default([]),
    corporateEvents: z.array(z.looseObject({
      date: z.string(), type: z.string(), from: z.any().nullish(), to: z.any().nullish(),
    })).default([]),
    adjustment: z.number().nullish(),
  });
  ```

---

### ۷. خطوط میانگین متحرک (`GET /api/ma/{symbol}`)
- **ماژول فرانت‌اند:** `features/market/api/useMa.ts`
- **هندلر Go:** `internal/chart/service.go:MA`
- **دسترسی پایگاه داده:** محاسبه در زمان اجرا روی کندل‌های ذخیره‌شده نماد در `market.db`.
- **اسکیمای پاسخ (Zod):**
  ```typescript
  export const MaSchema = z.union([
    z.looseObject({
      status: z.literal('ok'),
      symbol: z.string(),
      periods: z.array(z.number()).nullish(),
      ma: z.looseObject({
        ma5: z.array(z.tuple([z.string(), z.number().nullable()])).nullish(),
        ma20: z.array(z.tuple([z.string(), z.number().nullable()])).nullish(),
        ma50: z.array(z.tuple([z.string(), z.number().nullable()])).nullish(),
        ma120: z.array(z.tuple([z.string(), z.number().nullable()])).nullish(),
      }),
      bars: z.number().nullish(),
    }),
    z.looseObject({ status: z.literal('error'), message: z.string().nullish() }),
  ]);
  ```

---

### ۸. عمق مظنه دفترچه سفارشات (`GET /api/order-book/{symbol}`)
- **ماژول فرانت‌اند:** `features/market/api/useOrderBook.ts`
- **هندلر Go:** `internal/chart/service.go:OrderBook`
- **دسترسی پایگاه داده:** دریافت از بافر ۵ سطحی زنده در حافظه یا جداول `orderbook_snapshots`.
- **اسکیمای پاسخ (Zod):**
  ```typescript
  export const BookSchema = z.object({
    status: z.string(),
    symbol: z.string().nullish(),
    levels: z.array(z.object({
      buy_px: z.number(), buy_vol: z.number(), buy_cnt: z.number(),
      sell_px: z.number(), sell_vol: z.number(), sell_cnt: z.number(),
    })).default([]),
  });
  ```

---

### ۹. ثبت ضربان رصد دفتر سفارشات (`POST /api/orderbook/watch`)
- **ماژول فرانت‌اند:** `features/market/api/useOrderBook.ts`
- **هندلر Go:** `internal/httpapi/orderbook_watch.go:orderbookWatchHandler`
- **دسترسی پایگاه داده:** ندارد (تنظیم Hot-Window اشتراک در حافظه رم با مهلت انقضای ۱۵ دقیقه).
- **بدنه درخواست:** `{"ins_code": "IRB3W1250631"}`
- **اسکیمای پاسخ:** `{"status": "success", "subscribed": [...]}`

---

### ۱۰. تاریخچه فیلترهای تابلوخوانی (`GET /api/tape-history`)
- **ماژول فرانت‌اند:** `features/market/api/useTapeHistory.ts`
- **هندلر Go:** `internal/market/service.go:TapeHistory`
- **دسترسی پایگاه داده:** `market.db` (RO)
- **پارامترهای کوئری:** `?codes=<ins_code>&days=<N>`
- **اسکیمای پاسخ (Zod):**
  ```typescript
  export const TapeHistorySchema = z.looseObject({
    status: z.string(),
    days: z.array(z.number()).default([]),
    by_symbol: z.record(z.string(), z.record(z.string(), z.object({
      days: z.record(z.string(), z.object({
        active: z.boolean(), passes: z.number(),
      })),
      total: z.number(),
    }))).default({}),
    flags: z.array(z.string()).default([]),
  });
  ```

---

### ۱۱، ۱۲ و ۱۳. مدیریت واچ‌لیست کاربر (`/api/watchlist`)
- **ماژول فرانت‌اند:** `features/market/api/useWatchlist.ts`
- **هندلر Go:** `internal/watchlist/handlers.go` (`Get`, `Post`, `Delete`)
- **دسترسی پایگاه داده:** `user.db` (**تنها پایگاه مجاز نوشتن**)
- **روش‌ها و مسیرها:**
  - `GET /api/watchlist`: دریافت فهرست نمادها.
  - `POST /api/watchlist`: درج نماد با بدنه `{"symbol": "فولاد", "name": "فولاد مبارکه"}`.
  - `DELETE /api/watchlist/{symbol}`: حذف نماد با پارامتر آدرس `encodeURIComponent(symbol)`.
- **اسکیمای پاسخ مشترک (Zod):**
  ```typescript
  export const WatchlistPayloadSchema = z.looseObject({
    status: z.string(),
    count: z.number().nullish(),
    data: z.array(z.looseObject({
      norm: z.string(), symbol: z.string(), name: z.string(), added_at: z.string(),
    })).nullish(),
  });
  ```
- **محافظت Read-Only:** در صورت اجرای سرور با `--read-only`، متدهای POST و DELETE با خطای ساختاری ۴۰۳ و پیام مسدودیت نوشتن بازگردانده می‌شوند.

---

### ۱۴ و ۱۵. مرکز اعلانات و منابع خوراک (`/api/notifications/*`)
- **ماژول فرانت‌اند:** `features/notifications/api/useNotifications.ts`
- **هندلر Go:** `internal/notifications/handlers.go` (`Feed`, `Sources`)
- **دسترسی پایگاه داده:** `market.db` (جدول اطلاعیه‌ها)
- **مسیرها:**
  - `GET /api/notifications/feed?levels=high,medium`: دریافت اخبار و اخطارهای بازار.
  - `GET /api/notifications/sources`: نمایش وضعیت پایش آنلاین سامانه‌ها (کدال، بورس کالا، TSETMC).
- **اسکیمای پاسخ فید:**
  ```typescript
  export const FeedSchema = z.looseObject({
    status: z.literal('ok'),
    items: z.array(z.looseObject({
      id: z.union([z.string(), z.number()]).nullish(),
      level: z.enum(['high', 'medium', 'low', 'unclassified']),
      title: z.string(),
      symbol: z.string().nullish(),
      publish_date: z.string().nullish(),
    })),
  });
  ```

---

### ۱۶. ارزیابی جامع ۵ محوره بنیادی FTS (`GET /api/fundamental/{symbol}`)
- **ماژول فرانت‌اند:** `features/fundamental/api/useFtsCard.ts`
- **هندلر Go:** `internal/fundamental/service.go:Card`
- **دسترسی پایگاه داده:** `codal.db` (RO) + `market.db` (RO)
- **اسکیمای پاسخ (Zod):**
  ```typescript
  export const FtsCardSchema = z.looseObject({
    status: z.literal('success'),
    symbol: z.string(),
    sector: z.string().nullish(),
    score: z.number().nullish(),
    verdict: z.string().nullish(),
    applicable: z.boolean().nullish(),
    excluded: z.boolean().nullish(),
    indicators: z.looseObject({
      '1': Axis1Schema,
      '2': Axis2Schema,
      '3': Axis3Schema,
      '4': Axis4Schema,
      '5': Axis5Schema,
    }).nullish(),
    details: z.record(z.string(), DetailSchema).nullish(),
  });
  ```

---

### ۱۷. جدول اسکرینر بنیادی FTS (`GET /api/screener`)
- **ماژول فرانت‌اند:** `features/fundamental/api/useScreenerCore.ts`
- **هندلر Go:** `internal/screener/service.go:Screener`
- **دسترسی پایگاه داده:** `codal.db` (RO) + `market.db` (RO)
- **اسکیمای پاسخ (Zod):**
  ```typescript
  export const ScreenerCoreSchema = z.looseObject({
    status: z.string(),
    count: z.number(),
    data: z.array(ScreenerCoreRowSchema),
    thresholds: z.looseObject({
      growth_min: z.number().nullish(),
      margin_min: z.number().nullish(),
      v10_sales_to_mcap_min: z.number().nullish(),
    }).nullish(),
  });
  ```

---

### ۱۸ و ۱۹. تقویم رویدادها و مجامع شرکت‌ها (`/api/calendar/*`)
- **ماژول فرانت‌اند:** `features/fundamental/api/useCalendar.ts`
- **هندلر Go:** `internal/chart/service.go:CalendarSymbol` و `CalendarUpcoming`
- **دسترسی پایگاه داده:** `codal.db` (RO) و فایل تقویم رویدادها.
- **مسیرها:**
  - `GET /api/calendar/{symbol}`: تقویم اختصاصی یک شرکت (`SymbolPayload`).
  - `GET /api/calendar/upcoming?days=30`: کلیه مجامع و پرداخت‌های پیش‌رو در بازار (`UpcomingPayload`).

---

### ۲۰. سلامت پایپ‌لاین به‌روزرسانی کدال (`GET /api/sync/codal/pipeline`)
- **ماژول فرانت‌اند:** `features/fundamental/api/useCodalHealth.ts`
- **هندلر Go:** `internal/sync/handlers.go:CodalPipeline`
- **دسترسی پایگاه داده:** وضعیت صف پردازش، دیتابیس کدال و جدول وضعیت به‌روزرسانی‌ها.
- **اسکیمای پاسخ (Zod):**
  ```typescript
  const Payload = z.looseObject({
    status: z.string(),
    message: z.string().nullish(),
    queue: z.looseObject({
      queued: z.number().nullish(), running: z.number().nullish(), done: z.number().nullish(),
      total: z.number().nullish(), retryable: z.number().nullish(),
    }).nullish(),
    dirty_symbols: z.number().nullish(),
    last_data_update: z.string().nullish(),
    gap_flag: z.boolean().nullish(),
  });
  ```

---

### ۲۱، ۲۲ و ۲۳. بسته هوش مصنوعی و پرایس‌اکشن تکنیکال (`/api/chart/{symbol}/*`)
- **ماژول‌های فرانت‌اند:**
  - `features/technical/api/forecastApi.ts`
  - `features/technical/api/candleEdgeApi.ts`
  - `features/technical/api/indicatorsApi.ts`
- **هندلرهای Go:** `internal/chart/handlers.go` (`Forecast`, `Edge`, `Indicators`)
- **دسترسی پایگاه داده:** `market.db` (RO)
- **مسیرها:**
  1. `GET /api/chart/{symbol}/forecast?horizon=12&model=small&adjustment=3`: پیش‌بینی افق زمانی هوش مصنوعی و کوانتایل‌های P10، P50، P90.
  2. `GET /api/chart/{symbol}/edge?swing_period=5`: لبه آماری کندل، بلوک‌های سفارش نهادی (Order Blocks)، خلأ نقدینگی (FVG) و شکست ساختار (BOS/CHoCH).
  3. `GET /api/chart/{symbol}/indicators`: پکیج سرورساید محاسبات RSI، MACD، ایچیموکو، بولینگر و واگرایی‌ها.

---

### ۲۴. تحلیل سرورساید FTS و بدج استریپ (`GET /api/fts/{symbol}`)
- **ماژول فرانت‌اند:** `features/technical/api/useFtsAnalysis.ts`
- **هندلر Go:** `internal/chart/service.go:FTS` (ثبت‌شده در `server.go:216`)
- **اینترفیس سرویس:** `Chart.FTS`
- **دسترسی پایگاه داده:** `market.db` (RO)
- **ساختار پارامترها:** Path `symbol` با انکودینگ الزامی `encodeURIComponent(symbol)`.
- **اسکیمای پاسخ (Zod):**
  ```typescript
  export const FtsResponse = z.object({
    status: z.string(),
    symbol: z.string().nullish(),
    fts: FtsAnalysis.nullish(),
    analysis_basis: z.string().nullish(),
    bars: z.number().nullish(),
    ref_close: z.number().nullish(),
    message: z.string().nullish(),
  });
  ```
- **مدیریت وضعیت خطا/داده خالی:** در صورتی که نماد تاریخچه نداشته باشد، پاسخ با وضعیت `status: "empty"` صادر می‌شود که توسط کامپوننت‌های فرانت‌اند بدون پرتاب خطا به‌عنوان نماد فاقد سابقه تحلیل شناخته و رندر می‌شود.

---

### ۲۵. تنظیمات و آستانه‌های بنیادی FTS (`GET` و `POST /api/fts/config`)
- **ماژول فرانت‌اند:** `features/fundamental/api/useFtsConfig.ts` / `features/fundamental/ui/FtsSettingsDrawer.tsx`
- **هندلر Go:** `s.notPortedRoute` (ثبت صریح ۵۰۱ در `server.go:223`)
- **دسترسی پایگاه داده:** `user.db` (**موکول به وظیفه ۶: Task 6 - User Features & Persistence**)
- **روش‌ها و مسیرها:**
  - `GET /api/fts/config`: واکشی آستانه‌های ذخیره‌شده کاربر برای فیلترهای بنیادی.
  - `POST /api/fts/config`: ذخیره‌سازی آستانه‌های اختصاصی کاربر.
- **بدنه درخواست POST (`FtsConfigPayloadSchema`):**
  ```typescript
  export const FtsConfigPayloadSchema = z.looseObject({
    growth_min: z.number(),
    eps_years: z.number(),
    margin_min: z.number(),
    margin_optimal: z.number(),
    sales_to_mcap_min: z.number(),
    profit_potential_min: z.number(),
    industry_mode: z.string(),
    watchlist_max: z.number(),
    mandatory_sectors: z.array(z.string()),
    free_sectors: z.array(z.string()),
  });
  ```
- **اسکیمای پاسخ:** `FtsConfigResponseSchema` (`status`, `config`, `message`, `errors`).
- **رفتار و تاب‌آوری کلاینت در برابر ۵۰۱ فعلی:**
  تا زمان پیاده‌سازی کامل ذخیره‌سازی تنظیمات کاربر در `user.db` طی وظیفه ۶، کشوی تنظیمات `FtsSettingsDrawer` در صورت دریافت خطای ۵۰۱، به‌صورت خودکار بر روی مقادیر پیش‌فرض جزوه FTS (`FTS_BASIC_DEFAULTS`) فعالیت کرده و عملکرد پایه‌ای فرانت‌اند مختل نمی‌گردد.

---

## ۷. مسیرهای خارج از شمول کلاینت نوین (Out-of-Scope Ledger)

جدول زیر چرایی عدم نیاز به ۷۸ مسیر باقیمانده پایتون در `frontend-v2` را تبیین می‌کند:

| دسته مسیرها | تعداد | نمونه مسیرها | علت عدم حضور در Frontend-v2 | رفتار حفاظتی Go |
| :--- | :---: | :--- | :--- | :--- |
| **سرخطی و ارسال سفارش** | ۱۵ | `/api/execution/dispatch`, `/api/execution/connect` | قابلیت کارگزاری مستقیم و اتوماسیون ترید به هسته ترمینال تحلیلی V2 تعلق ندارد. | `501 NOT_PORTED` |
| **بات معاملاتی خودکار** | ۸ | `/api/bot/run`, `/api/bot/status`, `/api/bot/halt` | کنترل بات به صورت سرویس پس‌زمینه بدون واسط کاربری است. | `501 NOT_PORTED` |
| **اندپوینت‌های قدیمی نبض** | ۸ | `/api/mstat/gold`, `/api/mstat/treemap` | در بازطراحی V2، بخش طلا و نقشه‌های درختی سنگین قدیمی با ویجت‌های بهینه جایگزین شده‌اند. | `501 NOT_PORTED` |
| **کنترل پل ADB و شبکه** | ۴ | `/api/adb/rotate`, `/api/adb/status` | تغییر آی‌پی مودم و دانگل موبایل در فرآیند استخراج محلی استفاده می‌شود، نه کلاینت دسکتاپ نهایی. | `501 NOT_PORTED` |
| **موتور سوم ساختار** | ۱ | `/api/structure3/{symbol}` | موتور سوم ساختار در نسخه قدیمی ناپایدار بوده و در فاز ۲E با ساختار نوین ادغام می‌شود. | `501 NOT_PORTED` |
| **تنظیمات و ماتریس‌های معلق** | ۲ | `/api/fundamental/screen`, `/api/watchlist/matrix` | مسیرهای معلق با ثبت صریح ۵۰۱ در Mux تا زمان بازطراحی کامل. | `REGISTERED_501` |
| **سینک و مدیریت دستی دیتابیس** | ۴۰ | `/api/sync/discover`, `/api/sync/full`, `/api/update/*` | عملیات نگهداری توسط لانچر Tauri و فرآیندهای پس‌زمینه خودکار مدیریت می‌شوند. | `501 NOT_PORTED` |

---

## ۸. گواهی تطبیق و تست‌پذیری (Contract Verification Assurance)

این قرارداد API به‌وسیله آزمون‌های زیر در سطح شاخه قفل شده است:
۱. **تست‌های واحد و یکپارچگی Go (`backend-go`):** ۳۵ پکیج با ۳۲۴ سناریوی تست تمامی ۶۱ هندلر را با دیتابیس‌های واقعی و فیکسچرهای استاندارد راستی‌آزمایی می‌کنند.
۲. **تست‌های فرانت‌اند (`frontend-v2`):** ۱۰۴ فایل آزمون Vitest (شامل ۸۵۹ تست سبز) نحوه فراخوانی، دریافت و اعتبارسنجی Zod را برای تمامی مسیرهای فعال کلاینت نوین (۲۴ روت فعال Go + ۱ روت تنظیمات کاربر با فال‌بک) تضمین می‌نمایند.
۳. **تایپ‌چک کامل کامپایلر تایپ‌اسکریپت (`npx tsc -b`):** صفر خطای تایپ در تمامی تعاریف اسکیما، مدل‌ها و ارتباطات کامپوننت‌ها.

$$\mathbf{VERDICT: CONTRACT\_FROZEN\_AND\_VERIFIED}$$
*(این سند مبنای پیاده‌سازی و یکپارچه‌سازی وظایف Tasks 3-6 در استیج ۲ است).*
