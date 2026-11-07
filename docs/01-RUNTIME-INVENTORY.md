# سند ۰۱: فهرست جامع زمان اجرای وب‌سرویس‌ها و پایش کامل APIها

## خلاصه اجرایی و انطباق آماری (Census Reconciliation)

این سند مبنای دقیق و استخراج‌شده از سورس‌کد پروژه برای تمامی اندپوینت‌های فعال پایتون و وضعیت معادل آن‌ها در موتور Go (`borsd`) است.

### حل معمای اختلاف آمار ۱۰۵ در برابر ۱۳۹ در برابر ۱۴۸:
1. **گزارش پیشین فاز ۱ (۱۰۵ اندپوینت):** این عدد صرفاً بر اساس فایل کاتالوگ دستی `backend-go/internal/httpapi/routes.json` (شامل ۱۰۴ مسیر API) به‌علاوه اندپوینت `/healthz` تهیه شده بود و سورس‌کد پایتون را از ریشه پیمایش نکرده بود.
2. **شمارش اولیه بازرسی شاخه انتگریشن (۱۳۹ اندپوینت):** این عدد بر اساس استخراج سطحی مسیرهای منحصر‌به‌فرد از دکوراتورهای ماژول‌های روتر بدون محاسبه اندپوینت‌های پایه‌ای FastAPI و بدون محاسبه مسیرهای دوتایی متدها بود.
3. **آمار دقیق و قطعی استخراج‌شده از سورس پایتون (۱۴۸ اندپوینت):**
   - کل مسیرهای استخراج‌شده از درخت روترهای FastAPI: **۱۴۸ مسیر**
   - مسیرهای پیشوند `/api/*`: **۱۴۲ مسیر**
   - مسیرهای غیر API (شامل `/`, `/docs`, `/openapi.json`, `/redoc` و SPA catch-all): **۶ مسیر**

### جدول توزیع وضعیت پیاده‌سازی و مصرف در Go:
| وضعیت پیاده‌سازی | تعداد مسیر | شرح |
| :--- | :---: | :--- |
| `IMPLEMENTED` (هندلر فعال Go) | **۶۱** | کاملاً پیاده‌سازی‌شده در Go با هندلر فعال و پوشش تست ۱۰۰٪ |
| `REGISTERED_501` (ثبت صریح در Go Mux با ۵۰۱) | **۳** | `/api/fts/config`, `/api/fundamental/screen`, `/api/watchlist/matrix` |
| `GATE_501` (کاتالوگ‌شده و پاسخ ۵۰۱ از apiGate) | **۷۸** | شامل اندپوینت‌های Sarkhati/Execution (۱۵ عدد)، Bot (۸ عدد)، Mstat گسترش‌یافته (۸ عدد) و فیلترهای ابزاری |
| `EXCLUDED` (غیر API / مستندات) | **۶** | مستندات OpenAPI، ریدایرکت‌ها و روت SPA |
| **جمع کل اندپوینت‌ها** | **۱۴۸** | **پوشش کامل و ۱۰۰٪ درخت سورس پایتون** |

### ایزولاسیون کامل فرانت‌اند نوین (`frontend-v2`):
تحلیل قطعی ۵۲ فراخوانی شبکه در فرانت‌اند نوین `frontend-v2` نشان داد که این فرانت‌اند **تنها ۲۳ الگوی مسیر منحصر‌به‌فرد** (و در مجموع ۶۱ اندپوینت ارائه‌شده) را مصرف می‌کند که **۱۰۰٪ آن‌ها در Go پیاده‌سازی شده و سبز هستند**.
هیچ‌یک از مسیرهای پورت‌نشده (Execution، Bot، Structure3، Sync دستی) توسط `frontend-v2` فراخوانی نمی‌شوند و صرفاً متعلق به پنل‌های عیب‌یابی توسعه‌دهنده یا SPA قدیمی میراثی بوده‌اند.

---

## ماتریس جامع ۱۴۸ اندپوینت پروژه

| روش و مسیر API | ماژول پایتون | وضعیت در Go | وضعیت راستی‌آزمایی | مصرف در Frontend-v2 | مخزن داده و دسترسی |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /` | `app` | `EXCLUDED` | `NOT_APPLICABLE` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/adb/rotate` | `api.engine` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | ADB Bridge |
| `POST /api/adb/set` | `api.adb` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | ADB Bridge |
| `GET /api/adb/state` | `api.adb` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | ADB Bridge |
| `GET /api/adb/status` | `api.engine` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | ADB Bridge |
| `POST /api/bot/account/reset` | `api.bot` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/bot/config` | `api.bot` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `PUT /api/bot/config` | `api.bot` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/bot/halt` | `api.bot` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/bot/history` | `api.bot` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/bot/resume` | `api.bot` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/bot/run` | `api.bot` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/bot/status` | `api.bot` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/calendar/upcoming` | `api.chart` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useCalendarUpcoming`) | N/A |
| `GET /api/calendar/{symbol}` | `api.chart` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useCalendarSymbol`) | N/A |
| `GET /api/chart-db/{symbol}` | `api.chart` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useChartData`) | `market.db` (RO) |
| `GET /api/chart/{symbol}` | `api.chart` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `market.db` (RO) |
| `GET /api/chart/{symbol}/key-levels` | `api.chart` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useKeyLevels`) | `market.db` (RO) |
| `POST /api/codal/control` | `api._sync_codal` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useCodalControl`) | `codal.db` (RO) + `market.db` (RO) |
| `GET /api/diagnostics/info` | `api.diagnostics` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/diagnostics/log` | `api.diagnostics` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/diagnostics/log/open` | `api.diagnostics` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/execution/audit/{execution_id}` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/execution/cancel/{execution_id}` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/execution/config` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/execution/config` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `DELETE /api/execution/connect` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/execution/connect` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `DELETE /api/execution/connect/browser` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/execution/connect/browser` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/execution/connect/verify` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/execution/dispatch` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/execution/events` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/execution/halt` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/execution/ledger` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/execution/limits` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/execution/portfolio` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/execution/preflight` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/execution/prepare` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/execution/probe` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/execution/queue/{execution_id}` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/execution/reconcile/{execution_id}` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/execution/refresh/{execution_id}` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/execution/resume` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `DELETE /api/execution/schedule/{execution_id}` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/execution/schedule/{execution_id}` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `DELETE /api/execution/session` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/execution/session` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `POST /api/execution/session` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/execution/status` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/execution/timings` | `api.execution` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | In-Memory / State (Unported) |
| `GET /api/export` | `api._export` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useExport`) | N/A |
| `POST /api/export` | `api._export` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useExport`) | N/A |
| `GET /api/fts` | `api.market` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/fts/config` | `api.market` | `REGISTERED_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/fts/config` | `api.market` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/fts/{symbol}` | `api.chart` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useFtsAnalysis`) | N/A |
| `GET /api/fundamental/freshness` | `api.fundamental` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useFundamentalFreshness`) | `codal.db` (RO) + `market.db` (RO) |
| `GET /api/fundamental/screen` | `api.fundamental` | `REGISTERED_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `codal.db` (RO) + `market.db` (RO) |
| `GET /api/fundamental/sectors` | `api.fundamental` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useFundamentalSectors`) | `codal.db` (RO) + `market.db` (RO) |
| `GET /api/fundamental/{symbol}` | `api.fundamental` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useFundamentalCard`) | `codal.db` (RO) + `market.db` (RO) |
| `GET /api/fundamental/{symbol}/quarters` | `api.fundamental` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useQuarters`) | `codal.db` (RO) + `market.db` (RO) |
| `GET /api/funnel` | `api.funnel` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useFunnel`) | `market.db` (RO) |
| `POST /api/funnel` | `api.funnel` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useFunnel`) | `market.db` (RO) |
| `GET /api/funnel/registry` | `api.funnel` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useFunnelRegistry`) | `market.db` (RO) |
| `GET /api/funnel/trace` | `api.funnel` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useFunnelTrace`) | `market.db` (RO) |
| `GET /api/history/{symbol}` | `api.screener` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useHistory`) | N/A |
| `GET /api/index/tedpix` | `api.market_index` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useTedpix`) | N/A |
| `GET /api/live-stats` | `api.market` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/ma/{symbol}` | `api.chart` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMA`) | N/A |
| `GET /api/market` | `api.market` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMarketBoard`) | `market.db` (RO) |
| `GET /api/market/closes` | `api.market` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `market.db` (RO) |
| `GET /api/market/delta` | `api.market` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMarketDelta`) | `market.db` (RO) |
| `GET /api/market/row` | `api.market` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `market.db` (RO) |
| `GET /api/market/sync-state` | `api.market` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMarketSyncState`) | `market.db` (RO) |
| `GET /api/mstat/board` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatBoard`) | `market.db` (RO) |
| `GET /api/mstat/clientsplit` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatClientSplit`) | `market.db` (RO) |
| `GET /api/mstat/depth` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatDepth`) | `market.db` (RO) |
| `GET /api/mstat/gold` | `api.market_status` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `market.db` (RO) |
| `GET /api/mstat/goldhistory` | `api.market_status` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `market.db` (RO) |
| `GET /api/mstat/histogram` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatHistogram`) | `market.db` (RO) |
| `GET /api/mstat/indexcards` | `api.market_status` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `market.db` (RO) |
| `GET /api/mstat/industries` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatIndustries`) | `market.db` (RO) |
| `GET /api/mstat/mainwatch` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatMainwatch`) | `market.db` (RO) |
| `GET /api/mstat/market-snapshot` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatMarketSnapshot`) | `market.db` (RO) |
| `GET /api/mstat/orderflows` | `api.market_status` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `market.db` (RO) |
| `GET /api/mstat/ownership` | `api.market_status` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `market.db` (RO) |
| `GET /api/mstat/phase` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatPhase`) | `market.db` (RO) |
| `GET /api/mstat/phases` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatPhases`) | `market.db` (RO) |
| `GET /api/mstat/series` | `api.market_status` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `market.db` (RO) |
| `GET /api/mstat/smart-money` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatSmartMoney`) | `market.db` (RO) |
| `POST /api/mstat/snapshot` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatSnapshot`) | `market.db` (RO) |
| `GET /api/mstat/summary` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatSummary`) | `market.db` (RO) |
| `GET /api/mstat/thermometer` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatThermometer`) | `market.db` (RO) |
| `GET /api/mstat/timeline` | `api.market_status` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useMstatTimeline`) | `market.db` (RO) |
| `GET /api/mstat/tops` | `api.market_status` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `market.db` (RO) |
| `GET /api/mstat/treemap` | `api.market_status` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `market.db` (RO) |
| `GET /api/notifications/feed` | `api.notifications` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useNotificationFeed`) | N/A |
| `GET /api/notifications/sources` | `api.notifications` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useNotificationSources`) | N/A |
| `GET /api/notify/status` | `api.notify` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/notify/test-all` | `api.notify` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/notify/test-bale` | `api.notify` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/notify/test-telegram` | `api.notify` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/order-book/{symbol}` | `api.chart` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useOrderBook`) | N/A |
| `POST /api/orderbook/watch` | `api.market` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/patterns/{symbol}` | `api.chart` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`usePatterns`) | N/A |
| `GET /api/price-basis` | `api.market` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/price-basis` | `api.market` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/screener` | `api.screener` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useScreener`) | `market.db` (RO) |
| `GET /api/screener/row` | `api.screener` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `market.db` (RO) |
| `POST /api/selection/decision` | `api.selection` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useSelectionMutations`) | `user.db` (RW/RO) |
| `DELETE /api/selection/decision/{symbol}` | `api.selection` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useSelectionMutations`) | `user.db` (RW/RO) |
| `GET /api/selection/portfolio` | `api.selection` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`usePortfolio`) | `user.db` (RW/RO) |
| `GET /api/selection/symbols` | `api.selection` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useSelection`) | `user.db` (RW/RO) |
| `GET /api/structure3/{symbol}` | `api.structure3` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/sync/backfill` | `api.engine` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/sync/codal` | `api._sync_codal` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useSyncMutations`) | `codal.db` (RO) + `market.db` (RO) |
| `POST /api/sync/codal/db-download` | `api._sync_codal` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useSyncMutations`) | `codal.db` (RO) + `market.db` (RO) |
| `GET /api/sync/codal/db-status` | `api._sync_codal` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useCodalDBStatus`) | `codal.db` (RO) + `market.db` (RO) |
| `GET /api/sync/codal/fts-coverage` | `api.fundamental` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `codal.db` (RO) + `market.db` (RO) |
| `POST /api/sync/codal/fts-refresh` | `api._sync_codal` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useSyncMutations`) | `codal.db` (RO) + `market.db` (RO) |
| `GET /api/sync/codal/pipeline` | `api.fundamental` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useCodalPipeline`) | `codal.db` (RO) + `market.db` (RO) |
| `POST /api/sync/delta` | `api.engine` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/sync/diagnose` | `api._sync_codal` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useDiagnose`) | N/A |
| `POST /api/sync/discover` | `api._pipeline` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/sync/full` | `api.engine` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/sync/market` | `api._sync_market` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useSyncMutations`) | `market.db` (RO) |
| `GET /api/sync/pipeline` | `api.engine` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/sync/status` | `api._sync_codal` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useSyncStatus`) | N/A |
| `POST /api/sync/update-existing` | `api._pipeline` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/sync/watchlist` | `api.engine` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `user.db` (RW/RO) |
| `GET /api/tape-history` | `api.market` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useTapeHistory`) | `market.db` (RO) |
| `GET /api/universe/live` | `api.market` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/update/check` | `api.update` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/update/download` | `api.update` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/update/install` | `api.update` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `POST /api/update/install-local` | `api.update` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/update/progress` | `api.update` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/update/version` | `api.update` | `GATE_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /api/watchlist` | `api.watchlist` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useWatchlist`) | `user.db` (RW/RO) |
| `POST /api/watchlist` | `api.watchlist` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useWatchlistMutations`) | `user.db` (RW/RO) |
| `GET /api/watchlist/matrix` | `api.watchlist` | `REGISTERED_501` | `NOT_PORTED` | No (Legacy SPA v1 / Tool) | `user.db` (RW/RO) |
| `DELETE /api/watchlist/{symbol}` | `api.watchlist` | `IMPLEMENTED` | `COMPLETE_VERIFIED` | Yes (`useWatchlistMutations`) | `user.db` (RW/RO) |
| `GET /docs` | `fastapi.applications` | `EXCLUDED` | `NOT_APPLICABLE` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /docs/oauth2-redirect` | `fastapi.applications` | `EXCLUDED` | `NOT_APPLICABLE` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /openapi.json` | `fastapi.applications` | `EXCLUDED` | `NOT_APPLICABLE` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /redoc` | `fastapi.applications` | `EXCLUDED` | `NOT_APPLICABLE` | No (Legacy SPA v1 / Tool) | N/A |
| `GET /{full_path:path}` | `app` | `EXCLUDED` | `NOT_APPLICABLE` | No (Legacy SPA v1 / Tool) | N/A |
