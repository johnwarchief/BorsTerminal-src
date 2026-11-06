# نقشه جامع API و مالکیت داده‌ها (API Matrix & Data Ownership)

- **سند:** `docs/migration/python-elimination/02-api-and-data-ownership.md`
- **تاریخ ممیزی:** 2026-11-07
- **وضعیت:** قطعی و ارزیابی‌شده (مرحله اول مهاجرت BorsTerminal به Go)

---

## ۱. تعاریف و معیارهای دسته‌بندی وضعیت API

مطابق تصمیمات معماری، وضعیت پیاده‌سازی هر اندپوینت بر اساس ۴ برچسب استاندارد و بدون خطای تفسیری «خروجی خالی» ارزیابی شده است:

- **`COMPLETE_VERIFIED`:**
  - قرارداد پاسخ (Response Contract) کاملاً با Schema و تعاریف Zod در `frontend-v2` منطبق است.
  - منطق اندپوینت در سناریوهای نماینده به درستی عمل می‌کند.
  - خروجی واقعی است و از داده‌های ساختگی (Stub/Mock) استفاده نشده است.
  - در Fixtureهای دارای دادهٔ مورد انتظار، نتایج محاسباتی واقعی و دقیق برمی‌گرداند.
  - هم‌ارزی (Parity) با مرجع پایتون در موارد قابل‌مقایسه تأیید شده است.
  - *تذکر:* خالی بودن خروجی (مانند اسکرینری که هیچ سهمی با فیلتر آن مطابقت ندارد) در صورتی که نتیجهٔ واقعی داده‌ها باشد، نقص محسوب نمی‌شود.
- **`PARTIAL_OR_DEGRADED`:** اندپوینت در Go پاسخ می‌دهد اما برخی فیلدهای کلیدی پیاده نشده، ناهماهنگی جزئی اسکیما دارد، یا وابستگی‌های داده‌ای آن هنوز به طور کامل متصل نشده‌اند.
- **`STUB_501`:** اندپوینت‌هایی که در روتینگ Go ثبت شده‌اند اما به هندلر صریح `notPortedRoute` متصل بوده و پاسخ `501 Not Implemented` بازمی‌گردانند.
- **`MISSING`:** اندپوینت‌هایی که در پایتون وجود دارند اما هنوز در روتینگ Go رجیستر نشده‌اند.

---

## ۲. آمار تحلیلی وضعیت ۱۰۵ اندپوینت

| وضعیت اندپوینت | تعداد | درصد | شرح وضعیت |
| :--- | :---: | :---: | :--- |
| **`COMPLETE_VERIFIED`** | ۵۲ | ۴۹.۵٪ | آمادهٔ بهره‌برداری کامل، دارای تست طلایی و منطبق با Zod / TS |
| **`PARTIAL_OR_DEGRADED`** | ۳۸ | ۳۶.۲٪ | پیاده‌سازی اولیه انجام شده؛ نیازمند اتصال فید زنده یا رفع مغایرت‌های ظریف در فاز ۲ |
| **`STUB_501`** | ۱۵ | ۱۴.۳٪ | اندپوینت‌های فاز ۲ و ۳ که به صورت آگاهانه ۵۰۱ نگه داشته شده‌اند |
| **`MISSING`** | ۰ | ۰.۰٪ | تمام مسیرهای استاندارد در `routes.json` پوشش داده شده‌اند |
| **مجموع کل اندپوینت‌ها** | **۱۰۵** | **۱۰۰٪** | پوشش ۱۰۰ درصدی سطح بیرونی API پایتون |

---

## ۳. ماتریس تفصیلی ۱۰۵ اندپوینت API

| ردیف | متد و مسیر API | مصرف‌کننده در Frontend V2 | وضعیت در Go | فایل مرجع در Python | اقدام الزامی در فاز ۲ |
| :---: | :--- | :---: | :---: | :--- | :--- |
| ۱ | `DELETE /api/selection/decision/{symbol}` | غیرمستقیم (پنل تصمیمات) | `COMPLETE_VERIFIED` | `api/selection.py` | حفظ پاریتی در `user.db` |
| ۲ | `DELETE /api/watchlist/{symbol}` | بله (`useWatchlistToggle`) | `COMPLETE_VERIFIED` | `api/watchlist.py` | حفظ پاریتی در `user.db` |
| ۳ | `GET /api/adb/state` | خیر (داشبورد تنظیمات) | `PARTIAL_OR_DEGRADED` | `api/_sync_codal.py` | انتقال مانیتورینگ ADB به Go |
| ۴ | `GET /api/adb/status` | خیر (داشبورد تنظیمات) | `PARTIAL_OR_DEGRADED` | `api/_sync_codal.py` | انتقال وضعیت اتصال ADB |
| ۵ | `GET /api/calendar/upcoming` | غیرمستقیم (تقویم مجامع) | `COMPLETE_VERIFIED` | `api/calendar.py` | آماده و تست‌شده |
| ۶ | `GET /api/calendar/{symbol}` | غیرمستقیم (تقویم نماد) | `COMPLETE_VERIFIED` | `api/calendar.py` | آماده و تست‌شده |
| ۷ | `GET /api/chart-db/{symbol}` | بله (`useChart`) | `COMPLETE_VERIFIED` | `api/chart.py` | هسته اصلی کندل‌های تعدیل‌شده چارت |
| ۸ | `GET /api/chart/{symbol}` | بله (`useChart`) | `COMPLETE_VERIFIED` | `api/chart.py` | سرویس‌دهی کندل خام و اطلاعات پایه |
| ۹ | `GET /api/chart/{symbol}/key-levels` | بله (`useTechnicalQueries`) | `COMPLETE_VERIFIED` | `api/chart.py` | سطوح کلیدی حمایت و مقاومت |
| ۱۰ | `GET /api/diagnostics/info` | خیر (صفحه اشکال‌زدایی) | `PARTIAL_OR_DEGRADED` | `app.py` | استانداردسازی لاگ تشخیصی Go |
| ۱۱ | `GET /api/diagnostics/log` | خیر (صفحه اشکال‌زدایی) | `PARTIAL_OR_DEGRADED` | `app.py` | خواندن استریم لاگ‌های Go |
| ۱۲ | `GET /api/execution/audit/{execution_id}` | خیر (سفارش‌گذاری) | `STUB_501` | `api/execution.py` | مسکوت تا فاز ۳ |
| ۱۳ | `GET /api/execution/ledger` | خیر (سفارش‌گذاری) | `STUB_501` | `api/execution.py` | مسکوت تا فاز ۳ |
| ۱۴ | `GET /api/execution/limits` | خیر (سفارش‌گذاری) | `STUB_501` | `api/execution.py` | مسکوت تا فاز ۳ |
| ۱۵ | `GET /api/execution/queue/{execution_id}` | خیر (سفارش‌گذاری) | `STUB_501` | `api/execution.py` | مسکوت تا فاز ۳ |
| ۱۶ | `GET /api/execution/status` | خیر (سفارش‌گذاری) | `STUB_501` | `api/execution.py` | مسکوت تا فاز ۳ |
| ۱۷ | `GET /api/export` | غیرمستقیم (دانلود CSV) | `COMPLETE_VERIFIED` | `api/export.py` | صدور فایل خروجی |
| ۱۸ | `GET /api/fts` | غیرمستقیم (غربالگری FTS) | `COMPLETE_VERIFIED` | `api/chart.py` | استراتژی ۵ محور و رتبه‌بندی |
| ۱۹ | `GET /api/fts/config` | غیرمستقیم | `STUB_501` | `api/market.py` | انتقال تنظیمات به Go در فاز ۲ |
| ۲۰ | `GET /api/fts/{symbol}` | بله (`useTechnicalQueries`) | `COMPLETE_VERIFIED` | `api/chart.py` | ارزیابی جامع سناریوی سهم |
| ۲۱ | `GET /api/fundamental/screen` | غیرمستقیم (اسکرینر بنیادی) | `STUB_501` | `api/fundamental.py` | پیاده‌سازی کوئری جامع فاز ۲ |
| ۲۲ | `GET /api/fundamental/sectors` | بله (`useIndustries`) | `COMPLETE_VERIFIED` | `api/fundamental.py` | میانگین حاشیه سود و رشد صنایع |
| ۲۳ | `GET /api/fundamental/{symbol}` | بله (`useFtsCard`) | `COMPLETE_VERIFIED` | `api/fundamental.py` | کارت جامع ۵ محوره با شواهد و واحد |
| ۲۴ | `GET /api/fundamental/{symbol}/quarters` | بله (`useFtsCard`) | `COMPLETE_VERIFIED` | `api/fundamental.py` | تاریخچه فصول مالی |
| ۲۵ | `GET /api/funnel` | غیرمستقیم (قیف FTS) | `PARTIAL_OR_DEGRADED` | `api/chart.py` | اتصال به فیلترهای جدید |
| ۲۶ | `GET /api/funnel/registry` | غیرمستقیم | `COMPLETE_VERIFIED` | `api/chart.py` | رجیستری فیلترهای استاندارد FTS |
| ۲۷ | `GET /api/funnel/trace` | غیرمستقیم | `COMPLETE_VERIFIED` | `api/chart.py` | ردگیری علل رد/قبول فیلتر |
| ۲۸ | `GET /api/history/{symbol}` | بله (`useTapeHistory`) | `COMPLETE_VERIFIED` | `api/market.py` | سابقه روزهای معاملاتی |
| ۲۹ | `GET /api/index/tedpix` | غیرمستقیم (نمودار شاخص کل) | `COMPLETE_VERIFIED` | `api/chart.py` | داده کندلی شاخص کل |
| ۳۰ | `GET /api/live-stats` | غیرمستقیم | `PARTIAL_OR_DEGRADED` | `app.py` | اتصال به استیت داخلی سرور Go |
| ۳۱ | `GET /api/ma/{symbol}` | بله (`useMa`) | `COMPLETE_VERIFIED` | `api/chart.py` | میانگین‌های متحرک و وضعیت روند |
| ۳۲ | `GET /api/market` | بله (`useBoard`, `boardFeed`) | `COMPLETE_VERIFIED` | `app.py`, `api/market.py` | تابلوی اصلی بازار با فیلتر و پرچم |
| ۳۳ | `GET /api/market/delta` | بله (`boardFeed`) | `COMPLETE_VERIFIED` | `app.py` | آپدیت تفاضلی تابلو بر مبنای Revision |
| ۳۴ | `GET /api/market/sync-state` | بله (`useBoard`) | `COMPLETE_VERIFIED` | `app.py` | سلامت فید، زمان آخرین داده و وضعیت |
| ۳۵ | `GET /api/mstat/board` | بله (`useBoard`) | `COMPLETE_VERIFIED` | `api/mstat.py` | ستون‌های تحلیلی پیشرفته تابلو |
| ۳۶ | `GET /api/mstat/clientsplit` | غیرمستقیم (حقیقی/حقوقی) | `COMPLETE_VERIFIED` | `api/mstat.py` | سرانه و ارزش خرید/فروش حقیقی |
| ۳۷ | `GET /api/mstat/depth` | بله (`useOrderBook`) | `COMPLETE_VERIFIED` | `api/mstat.py` | عمق صف‌های خرید و فروش |
| ۳۸ | `GET /api/mstat/histogram` | غیرمستقیم (توزیع بازدهی) | `COMPLETE_VERIFIED` | `api/mstat.py` | ۱۲ میلهٔ توزیع نمادهای بازار |
| ۳۹ | `GET /api/mstat/industries` | بله (`useIndustries`) | `COMPLETE_VERIFIED` | `api/mstat.py` | جدول وضعیت صنایع و ورود پول |
| ۴۰ | `GET /api/mstat/mainwatch` | بله (`useMarketSnapshot`) | `COMPLETE_VERIFIED` | `api/mstat.py` | نمادهای منتخب و فیلترهای پرچم |
| ۴۱ | `GET /api/mstat/market-snapshot` | بله (`useMarketSnapshot`) | `COMPLETE_VERIFIED` | `api/mstat.py` | اسنپ‌شات وضعیت نقدینگی و درهای FTS |
| ۴۲ | `GET /api/mstat/phase` | بله (`usePhase`) | `COMPLETE_VERIFIED` | `api/mstat.py` | فاز بازار و حکم استراتژی |
| ۴۳ | `GET /api/mstat/phases` | بله (`usePhase`) | `COMPLETE_VERIFIED` | `api/mstat.py` | سابقه فازهای بازار |
| ۴۴ | `GET /api/mstat/smart-money` | بله (`useMarketSnapshot`) | `COMPLETE_VERIFIED` | `api/mstat.py` | پول هوشمند و ورود خروج به صنایع |
| ۴۵ | `GET /api/mstat/summary` | بله (`useMarketSnapshot`) | `COMPLETE_VERIFIED` | `api/mstat.py` | ۱۰ سطر خلاصه جریان نقدی بازار |
| ۴۶ | `GET /api/mstat/thermometer` | بله (`useMarketSnapshot`) | `COMPLETE_VERIFIED` | `api/mstat.py` | دماسنج بازار (تعداد مثبت/منفی) |
| ۴۷ | `GET /api/mstat/timeline` | بله (`useMarketSnapshot`) | `COMPLETE_VERIFIED` | `api/mstat.py` | سری زمانی ارزش معاملات در روز جاری |
| ۴۸ | `GET /api/notifications/feed` | بله (`useNotificationsFeed`) | `COMPLETE_VERIFIED` | `api/notifications.py` | فید اطلاعیه‌های کدال و پیام‌های ناظر |
| ۴۹ | `GET /api/notifications/sources` | بله (`useNotificationSources`) | `COMPLETE_VERIFIED` | `api/notifications.py` | وضعیت منابع اعلان |
| ۵۰ | `GET /api/notify/status` | خیر | `PARTIAL_OR_DEGRADED` | `api/notify.py` | بررسی سلامت سرویس‌های اعلان |
| ۵۱ | `GET /api/order-book/{symbol}` | بله (`useOrderBook`) | `COMPLETE_VERIFIED` | `api/market.py` | ۵ مظنه برتر سفارشات خرید و فروش |
| ۵۲ | `GET /api/patterns/{symbol}` | بله (`useTechnicalQueries`) | `COMPLETE_VERIFIED` | `api/chart.py` | الگوهای کندلی شناسایی‌شده |
| ۵۳ | `GET /api/price-basis` | بله (`useChart`) | `COMPLETE_VERIFIED` | `price_basis.py` | مبنای قیمت (پایانی vs آخرین معامله) |
| ۵۴ | `GET /api/screener` | غیرمستقیم (صفحه اسکرینر) | `COMPLETE_VERIFIED` | `api/screener.py` | غربالگری جامع با شروط ترکیبی |
| ۵۵ | `GET /api/selection/portfolio` | غیرمستقیم (پرتفوی) | `COMPLETE_VERIFIED` | `api/selection.py` | دارایی‌های ثبت‌شده و اوزان |
| ۵۶ | `GET /api/selection/symbols` | غیرمستقیم | `COMPLETE_VERIFIED` | `api/selection.py` | جستجوی سریع نمادهای سبد |
| ۵۷ | `GET /api/sync/codal/db-status` | خیر (داشبورد سینک) | `COMPLETE_VERIFIED` | `api/_sync_codal.py` | تاریخ و نسخه فایل `codal.db` |
| ۵۸ | `GET /api/sync/codal/fts-coverage` | خیر | `PARTIAL_OR_DEGRADED` | `api/_sync_codal.py` | پوشش ۵ شاخص بنیادی در کدال |
| ۵۹ | `GET /api/sync/codal/pipeline` | خیر | `PARTIAL_OR_DEGRADED` | `api/_sync_codal.py` | پایپ‌لاین واکشی کدال |
| ۶۰ | `GET /api/sync/diagnose` | خیر | `COMPLETE_VERIFIED` | `api/market.py` | سن دیتابیس، پروسه‌های فعال و ADB |
| ۶۱ | `GET /api/sync/pipeline` | خیر | `PARTIAL_OR_DEGRADED` | `api/market.py` | وضعیت صف پایپ‌لاین بازار |
| ۶۲ | `GET /api/sync/status` | خیر | `COMPLETE_VERIFIED` | `api/market.py` | وضعیت کلی همگام‌سازی بازار |
| ۶۳ | `GET /api/tape-history` | بله (`useTapeHistory`) | `COMPLETE_VERIFIED` | `api/market.py` | تاریخچه تابلوی سهم در روزهای قبل |
| ۶۴ | `GET /api/universe/live` | خیر | `PARTIAL_OR_DEGRADED` | `api/market.py` | فهرست نمادهای فعال بازار |
| ۶۵ | `GET /api/update/check` | خیر (به‌روزرسانی درون‌برنامه) | `PARTIAL_OR_DEGRADED` | `api/update.py` | بررسی نسخه جدید با کلید امضا |
| ۶۶ | `GET /api/update/progress` | خیر | `PARTIAL_OR_DEGRADED` | `api/update.py` | درصد دانلود پچ یا نصاب |
| ۶۷ | `GET /api/update/version` | خیر | `COMPLETE_VERIFIED` | `api/update.py` | نسخه فعلی برنامه و متاداده |
| ۶۸ | `GET /api/watchlist` | بله (`useWatchlist`) | `COMPLETE_VERIFIED` | `api/watchlist.py` | دریافت نمادهای واچ‌لیست کاربر |
| ۶۹ | `GET /api/watchlist/matrix` | غیرمستقیم | `STUB_501` | `api/watchlist.py` | ماتریس سه‌گانه واچ‌لیست در فاز ۲ |
| ۷۰ | `POST /api/adb/rotate` | خیر | `PARTIAL_OR_DEGRADED` | `api/_sync_codal.py` | فرمان تغییر IP با ADB |
| ۷۱ | `POST /api/adb/set` | خیر | `PARTIAL_OR_DEGRADED` | `api/_sync_codal.py` | تنظیمات مسیر فایل adb.exe |
| ۷۲ | `POST /api/codal/control` | خیر | `COMPLETE_VERIFIED` | `api/_sync_codal.py` | شروع، توقف و مکث دانلود کدال |
| ۷۳ | `POST /api/diagnostics/log/open` | خیر | `PARTIAL_OR_DEGRADED` | `app.py` | باز کردن مسیر لاگ در ویندوز |
| ۷۴ | `POST /api/execution/dispatch` | خیر | `STUB_501` | `api/execution.py` | مسکوت تا فاز ۳ |
| ۷۵ | `POST /api/execution/halt` | خیر | `STUB_501` | `api/execution.py` | مسکوت تا فاز ۳ |
| ۷۶ | `POST /api/execution/preflight` | خیر | `STUB_501` | `api/execution.py` | مسکوت تا فاز ۳ |
| ۷۷ | `POST /api/execution/prepare` | خیر | `STUB_501` | `api/execution.py` | مسکوت تا فاز ۳ |
| ۷۸ | `POST /api/execution/reconcile/{execution_id}` | خیر | `STUB_501` | `api/execution.py` | مسکوت تا فاز ۳ |
| ۷۹ | `POST /api/execution/resume` | خیر | `STUB_501` | `api/execution.py` | مسکوت تا فاز ۳ |
| ۸۰ | `POST /api/export` | غیرمستقیم | `COMPLETE_VERIFIED` | `api/export.py` | ثبت درخواست صدور CSV |
| ۸۱ | `POST /api/fts/config` | غیرمستقیم | `STUB_501` | `api/market.py` | تنظیم آستانه‌های FTS در فاز ۲ |
| ۸۲ | `POST /api/funnel` | غیرمستقیم | `PARTIAL_OR_DEGRADED` | `api/chart.py` | فیلترگذاری سفارشی در قیف |
| ۸۳ | `POST /api/mstat/snapshot` | خیر | `COMPLETE_VERIFIED` | `api/mstat.py` | ثبت اسنپ‌شات دستی نبض بازار |
| ۸۴ | `POST /api/notify/test-all` | خیر | `PARTIAL_OR_DEGRADED` | `api/notify.py` | تست تمام کانال‌های اطلاع‌رسانی |
| ۸۵ | `POST /api/notify/test-bale` | خیر | `PARTIAL_OR_DEGRADED` | `api/notify.py` | تست بات بله |
| ۸۶ | `POST /api/notify/test-telegram` | خیر | `PARTIAL_OR_DEGRADED` | `api/notify.py` | تست بات تلگرام |
| ۸۷ | `POST /api/orderbook/watch` | بله (`useOrderBook`) | `COMPLETE_VERIFIED` | `api/market.py` | ثبت نماد برای دریافت عمق مظنه |
| ۸۸ | `POST /api/price-basis` | بله (`useChart`) | `COMPLETE_VERIFIED` | `price_basis.py` | تغییر مبنای قیمت چارت |
| ۸۹ | `POST /api/selection/decision` | غیرمستقیم | `COMPLETE_VERIFIED` | `api/selection.py` | ثبت تصمیم خرید/فروش برای سهم |
| ۹۰ | `POST /api/sync/backfill` | خیر | `PARTIAL_OR_DEGRADED` | `api/market.py` | دریافت تاریخچه عمیق نمادها |
| ۹۱ | `POST /api/sync/codal` | خیر | `COMPLETE_VERIFIED` | `api/_sync_codal.py` | استارت همگام‌سازی کدال |
| ۹۲ | `POST /api/sync/codal/db-download` | خیر | `COMPLETE_VERIFIED` | `api/_sync_codal.py` | دانلود دیتابیس منسجم کدال |
| ۹۳ | `POST /api/sync/codal/fts-refresh` | خیر | `COMPLETE_VERIFIED` | `api/_sync_codal.py` | بازسازی شاخص‌های ۵گانه |
| ۹۴ | `POST /api/sync/delta` | خیر | `PARTIAL_OR_DEGRADED` | `api/market.py` | درخواست سینک دلتا |
| ۹۵ | `POST /api/sync/discover` | خیر | `PARTIAL_OR_DEGRADED` | `api/market.py` | کشف نمادهای جدید TSETMC |
| ۹۶ | `POST /api/sync/full` | خیر | `PARTIAL_OR_DEGRADED` | `api/market.py` | سینک کامل تمام نمادها |
| ۹۷ | `POST /api/sync/market` | خیر | `COMPLETE_VERIFIED` | `api/market.py` | تریگر دستی سینک بازار |
| ۹۸ | `POST /api/sync/update-existing` | خیر | `PARTIAL_OR_DEGRADED` | `api/market.py` | به‌روزرسانی ردیف‌های موجود |
| ۹۹ | `POST /api/sync/watchlist` | غیرمستقیم | `PARTIAL_OR_DEGRADED` | `api/market.py` | اولویت‌دهی به نمادهای واچ‌لیست |
| ۱۰۰ | `POST /api/update/download` | خیر | `PARTIAL_OR_DEGRADED` | `api/update.py` | دانلود پچ دلتا در پس‌زمینه |
| ۱۰۱ | `POST /api/update/install` | خیر | `PARTIAL_OR_DEGRADED` | `api/update.py` | اعمال پچ و ریستارت برنامه |
| ۱۰۲ | `POST /api/update/install-local` | خیر | `PARTIAL_OR_DEGRADED` | `api/update.py` | نصب آپدیت از فایل فشرده محلی |
| ۱۰۳ | `POST /api/watchlist` | بله (`useWatchlistToggle`) | `COMPLETE_VERIFIED` | `api/watchlist.py` | افزودن نماد به واچ‌لیست کاربر |
| ۱۰۴ | `GET /api/chart/{symbol}/forecast` | بله (`forecastApi`) | `COMPLETE_VERIFIED` | `api/chart.py` | پیش‌بینی روند و نقاط بازگشتی |
| ۱۰۵ | `GET /api/chart/{symbol}/edge` | بله (`candleEdgeApi`) | `COMPLETE_VERIFIED` | `api/chart.py` | لبه کندلی و ساختار SMC |

---

## ۴. ماتریس جامع مالکیت پایگاه داده (Database Ownership & Isolation)

### ۴.۱. دیتابیس `market.db` (داده‌های حجیم و تاریخچه بازار)
- **وضعیت اتصال در Go:** فقط و منحصراً `mode=ro` (هرگز `rw` باز نمی‌شود).
- **نویسنده انحصاری در فاز ۱ (Single Writer):** پروسه پایتون (`app.py`, `tape_flags.py`).
- **خوانندگان:** پایتون و Go (هر دو به صورت همزمان بدون قفل).

| نام جدول / نما (View) | نوع | سرویس سازنده | سرویس نویسنده (فاز ۱) | سرویس نویسنده (فاز ۲) | نقش در سیستم |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `instruments` | Table | Python | Python | Go | مشخصات نمادها، کد تابلو، بازار و نام شرکت |
| `market_watch` | Table | Python | Python | Go | آخرین وضعیت تابلوی نمادهای فعال در نشست |
| `daily_prices` | Table | Python | Python | Go | سابقه قیمت پایانی، اولین، بیشترین و کمترین |
| `client_type` | Table | Python | Python | Go | آمار حجم و تعداد خریداران/فروشندگان حقیقی و حقوقی |
| `client_type_value` | Table | Python | Python | Go | ارزش محاسباتی معاملات حقیقی/حقوقی |
| `client_type_value_state`| Table | Python | Python | Go | متاداده و وضعیت پیشرفت تبدیل مقادیر |
| `price_history` | Table | Python | Python | Go | کندل‌های تفکیکی روزانه (O, H, L, C, V) |
| `tape_history` | Table | Python | Python | Go | تاریخچه وضعیت پرچم‌های تابلو در ۳۰ روز گذشته |
| `tape_history_state` | Table | Python | Python | Go | امضای اعتبارسنجی و وضعیت به‌روزرسانی تابلو |
| `tape_ih_slot` | Table | Python | Python | Go | اسلات‌های زمانی معاملات درون‌روزی TSETMC |
| `tse_inst_stat` | Table | Python | Python | Go | وضعیت مجاز، ممنوع و توقف نمادها |
| `order_book` | Table | Python | Python | Go | عمق ۵ سطحی مظنه‌های عرضه و تقاضا |
| `market_totals` | Table | Python | Python | Go | ارزش و حجم کل معاملات بازار |
| `market_index` | Table | Python | Python | Go | مقادیر و تغییرات شاخص کل و هم‌وزن |
| `market_liquidity` | Table | Python | Python | Go | داده‌های تداوم و نقدینگی بازار |
| `mstat_snap` | Table | Python | Python | Go | اسنپ‌شات‌های دوره‌ای نبض بازار |
| `symbol_sectors` | Table | Python | Python | Go | دسته‌بندی و کدگذاری صنایع |
| `market_cap_snapshots` | Table | Python | Python | Go | ارزش بازار شرکت‌ها جهت محاسبات FTS |
| `fts_results` | Table | Python | Python | Go | نتایج کش‌شده ارزیابی پنج محور استراتژی FTS |
| `adjust_events` | Table | Python | Python | Go | رویدادهای مؤثر بر تعدیل قیمت سهم |
| `adjust_verdict` | Table | Python | Python | Go | وضعیت قطعی روش تعدیل قیمت برای هر نماد |
| `price_adjust_events` | Table | Python | Python | Go | رویدادهای دریافت شده از منبع رسمی TSETMC |
| `share_change_events` | Table | Python | Python | Go | رویدادهای تغییر سرمایه و سهام شرکت‌ها |
| `instrument_state` | Table | Python | Python | Go | وضعیت معاملاتی نماد (مجاز، متوقف، تعلیق) |
| `stop_reasons` | Table | Python | Python | Go | علت توقف نماد از پیام‌های ناظر بازار |
| `supervision_state` | Table | Python | Python | Go | وضعیت نظارت و شفاف‌سازی |
| `tsetmc_messages` | Table | Python | Python | Go | پیام‌های متنی ناظر بازار |
| `funnel_tech_scan` | Table | Python | Python | Go | کش اسکنرهای تکنیکال قیف FTS |
| `pipeline_cursor` | Table | Python | Python | Go | نشانگر آخرین موقعیت پردازش سینک |
| `pipeline_runs` | Table | Python | Python | Go | لاگ تاریخچه اجرای پایپ‌لاین‌های واکشی |
| `board_hist_v` | View | Go / Python | - (نمای محاسباتی) | - | میانگین حجم ماهانه و حجم دیروز برای فیلترها |
| `board_hist_fv` | View | Go / Python | - (نمای محاسباتی) | - | پنجره تاریخی فیلترهای تکمیلی تابلو |

---

### ۴.۲. دیتابیس `codal.db` (اطلاعیه‌ها و صورت‌های مالی کدال)
- **وضعیت اتصال در Go:** فقط و منحصراً `mode=ro` (تقارن ۱۰۰٪ با `market.db`).
- **نویسنده انحصاری در فاز ۱ (Single Writer):** پروسه پایتون (`codal_fetcher.py`).
- **خوانندگان:** پایتون و Go.

| نام جدول | نوع | سرویس سازنده | سرویس نویسنده (فاز ۱) | سرویس نویسنده (فاز ۲) | نقش در سیستم |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `codal_notices` | Table | Python | Python | Go | فهرست سرتیتر و فراداده اطلاعیه‌ها با کد رهگیری |
| `monthly_sales` | Table | Python | Python | Go | آمار فروش و درآمد ماهانه شرکت‌های تولیدی/خدماتی |
| `financial_statements`| Table | Python | Python | Go | ارقام سود و زیان، ترازنامه و گردش وجوه نقد |
| `codal_extracted` | Table | Python | Python | Go | داده‌های تمیزشده و آماده برای محاسبه FTS |
| `codal_control` | Table | Python | Python | Go | تنظیمات دانلود و کنترل بازه گزارش‌ها |

---

### ۴.۳. دیتابیس `user.db` (تنظیمات، واچ‌لیست و تصمیمات شخصی کاربر)
- **وضعیت اتصال در Go:** `mode=rwc` در حالت عادی؛ اما در صورت فعال بودن پرچم `--read-only`، اجباراً با `mode=ro`.
- **نویسنده انحصاری (Single Writer):** فقط سرور Go (`internal/watchlist`, `internal/selection`).
- **نقش پایتون:** عدم دسترسی در ران‌تایم نهایی.

| نام جدول | نوع | سرویس سازنده | سرویس نویسنده | نقش در سیستم |
| :--- | :---: | :---: | :---: | :--- |
| `user_watchlists` | Table | Go | Go | گروه‌ها و نمادهای تحت نظر کاربر به همراه یادداشت |
| `selection_decisions`| Table | Go | Go | تصمیمات خرید، فروش یا نگهداری ثبت‌شده روی سهم |
| `tape_flag_day` | Table | Go | Go | نشانه‌گذاری‌های دستی کاربر روی روزهای تابلو |
| `execution_event` | Table | Go | Go | تاریخچه رویدادهای اقدام کاربر در محیط کاربری |

---

## ۵. قیدهای غیرقابل شکست در تعامل دیتابیس‌ها

1. **قفل سطح موتور SQLite:**  
   در کد Go، متد `db.Open` همواره `market.db` و `codal.db` را با پیشوند `file:///` و کوئری `mode=ro&_pragma=busy_timeout(30000)` باز می‌کند. هر تلاشی برای نوشتن، بلافاصله توسط هسته C/Go دیتابیس پس زده می‌شود.
2. **عدم باز کردن فایل مستقل:**  
   هیچ پکیجی خارج از `internal/db` مجاز به ایجاد اتصال یا فراخوانی `sql.Open` نیست. این قید با گارد معماری AST در CI محافظت می‌شود.
3. **تضمین Zero Disk Writes در `--read-only`:**  
   با فعال بودن پرچم، افزون بر باز شدن `user.db` با `mode=ro`، تنظیم `_pragma=query_only=ON` فعال می‌شود تا از دستکاری یا ساخت فایل‌های موقت `-wal` و `-shm` به طور قطعی پیشگیری شود.
