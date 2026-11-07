# لاگِ خودِ برنامۀ بسته‌شده درِ دورِ smoke

خطِ `_encode_funnel_body` ثابت می‌کند همان کوئریِ این شاخه درِ فریز اجرا شده، و `304 Not Modified`ها مسیرِ مشروط را.

```
[OK] portable mode: data=C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\dist\BorsTerminal_Ultimate\data port=8123
==================================================================
  BorsTerminal_Ultimate - smart preflight
==================================================================
  data root: C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\dist\BorsTerminal_Ultimate
  [OK]  market.db: 6,023 instruments (TSETMC + Codal data inside)
[native] persistent webview profile: C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\dist\BorsTerminal_Ultimate\data\BorsTerminal_Ultimate\webview2
  [OK]  bundled libraries: pandas/numpy/fastapi/uvicorn/requests (self-contained)
  [OK]  everything ready - starting ...
==================================================================
2026-10-17 17:33:03 INFO:     Started server process [12644]
2026-10-17 17:33:03 INFO:     Waiting for application startup.
[startup] codal schema migrated (additive, idempotent)
[startup] BORS_NO_FETCH_LOOPS=1 — حلقه‌هایِ شبکه‌ایِ تابلو خاموش (دست‌نخورده خواندنِ بانکِ مشترک؛ برایِ سنجشِ dev کنارِ نسخۀِ نصبی)
[startup] screener warm thread spawned
[startup] candle projection spawned (local-only, one pass)
2026-10-17 17:33:03 INFO:     Application startup complete.
2026-10-17 17:33:03 INFO:     Uvicorn running on http://127.0.0.1:8123 (Press CTRL+C to quit)
2026-10-17 17:33:04 INFO:     127.0.0.1:3305 - "GET / HTTP/1.1" 200 OK
[OK] http://127.0.0.1:8123
[screener] loaded from disk cache
2026-10-17 17:33:04 INFO:     127.0.0.1:6625 - "GET / HTTP/1.1" 200 OK
  [candles-from-board] latest: 2318 کندل از 1 نشست برایِ 2٬318 نماد (نوشتۀ تازه/بازنشانی‌شده: 0)
2026-10-17 17:33:05 INFO:     127.0.0.1:10695 - "GET /favicon.ico HTTP/1.1" 200 OK
2026-10-17 17:33:14 WARNING:  fastapi\routing.py:144: FastAPIDeprecationWarning: ORJSONResponse is deprecated, FastAPI now serializes data directly to JSON bytes via Pydantic when a return type or response model is set, which is faster and doesn't need a custom response class. Read more in the FastAPI docs: https://fastapi.tiangolo.com/advanced/custom-response/#orjson-or-response-model and https://fastapi.tiangolo.com/tutorial/response-model/

2026-10-17 17:33:14 INFO:     127.0.0.1:2436 - "GET /api/update/version HTTP/1.1" 200 OK
2026-10-17 17:33:15 [market] history windows rebuilt in 10.27s (sig=(20261014, 443878, 18743513417152.64, 126231, 3542579310460.0, 220333, 6781594126587.0, 20261014))
[screener] cache warmed
2026-10-17 17:33:27 WARNING:  api\funnel.py:152: FastAPIDeprecationWarning: ORJSONResponse is deprecated, FastAPI now serializes data directly to JSON bytes via Pydantic when a return type or response model is set, which is faster and doesn't need a custom response class. Read more in the FastAPI docs: https://fastapi.tiangolo.com/advanced/custom-response/#orjson-or-response-model and https://fastapi.tiangolo.com/tutorial/response-model/
  body, etag = _encode_funnel_body(payload if full else _strip(payload))

2026-10-17 17:33:27 WARNING:  fastapi\routing.py:144: FastAPIDeprecationWarning: ORJSONResponse is deprecated, FastAPI now serializes data directly to JSON bytes via Pydantic when a return type or response model is set, which is faster and doesn't need a custom response class. Read more in the FastAPI docs: https://fastapi.tiangolo.com/advanced/custom-response/#orjson-or-response-model and https://fastapi.tiangolo.com/tutorial/response-model/

2026-10-17 17:33:27 INFO:     127.0.0.1:4479 - "GET /api/notifications/feed?limit=60 HTTP/1.1" 200 OK
2026-10-17 17:33:27 INFO:     127.0.0.1:5401 - "GET /api/selection/portfolio HTTP/1.1" 200 OK
2026-10-17 17:33:27 INFO:     127.0.0.1:13989 - "GET /api/screener HTTP/1.1" 200 OK
2026-10-17 17:33:27 INFO:     127.0.0.1:14050 - "POST /api/funnel HTTP/1.1" 200 OK
2026-10-17 17:33:27 INFO:     127.0.0.1:4479 - "GET /api/live-stats HTTP/1.1" 200 OK
2026-10-17 17:33:27 INFO:     127.0.0.1:2436 - "GET /favicon.ico HTTP/1.1" 200 OK
2026-10-17 17:33:27 INFO:     127.0.0.1:2924 - "GET /api/market HTTP/1.1" 200 OK
2026-10-17 17:33:27 INFO:     127.0.0.1:4479 - "GET /api/mstat/timeline?mode=cum HTTP/1.1" 200 OK
2026-10-17 17:33:28 INFO:     127.0.0.1:4479 - "GET /api/mstat/series?symbols=%D8%B9%D9%8A%D8%A7%D8%B1%2C%D9%81%D9%88%D9%84%D8%A7%D8%AF&days=365 HTTP/1.1" 200 OK
2026-10-17 17:33:28 INFO:     127.0.0.1:4479 - "GET /api/watchlist HTTP/1.1" 200 OK
2026-10-17 17:33:29 INFO:     127.0.0.1:14050 - "GET /api/index/tedpix?limit=0 HTTP/1.1" 200 OK
2026-10-17 17:33:30 INFO:     127.0.0.1:13989 - "GET /api/mstat/treemap?group=eq_all&industry=&metric=value HTTP/1.1" 200 OK
2026-10-17 17:33:30 INFO:     127.0.0.1:13989 - "GET /api/mstat/summary HTTP/1.1" 200 OK
2026-10-17 17:33:30 INFO:     127.0.0.1:13989 - "GET /api/mstat/depth?group=eq_all HTTP/1.1" 200 OK
2026-10-17 17:33:30 INFO:     127.0.0.1:2436 - "GET /api/mstat/gold?history_days=60 HTTP/1.1" 200 OK
2026-10-17 17:33:30 INFO:     127.0.0.1:13989 - "GET /api/mstat/thermometer?group=eq_all HTTP/1.1" 200 OK
2026-10-17 17:33:30 INFO:     127.0.0.1:2436 - "GET /api/mstat/histogram?group=all HTTP/1.1" 200 OK
2026-10-17 17:33:30 INFO:     127.0.0.1:13989 - "GET /api/mstat/clientsplit?tab=all HTTP/1.1" 200 OK
2026-10-17 17:33:30 INFO:     127.0.0.1:13989 - "GET /api/mstat/indexcards?days=30 HTTP/1.1" 200 OK
2026-10-17 17:33:31 INFO:     127.0.0.1:13989 - "GET /api/mstat/tops?group=eq_all HTTP/1.1" 200 OK
2026-10-17 17:33:31 INFO:     127.0.0.1:13989 - "GET /api/mstat/orderflows?group=all HTTP/1.1" 200 OK
2026-10-17 17:33:31 INFO:     127.0.0.1:13989 - "GET /api/mstat/ownership?group=all HTTP/1.1" 200 OK
2026-10-17 17:33:31 INFO:     127.0.0.1:2436 - "GET /api/mstat/phases HTTP/1.1" 200 OK
2026-10-17 17:33:31 INFO:     127.0.0.1:2436 - "GET /favicon.ico HTTP/1.1" 200 OK
2026-10-17 17:33:31 INFO:     127.0.0.1:2436 - "GET /favicon.ico HTTP/1.1" 200 OK
2026-10-17 17:33:32 INFO:     127.0.0.1:5401 - "GET /api/mstat/mainwatch?group=eq_all&industry= HTTP/1.1" 200 OK
2026-10-17 17:33:33 INFO:     127.0.0.1:4479 - "GET /api/mstat/mainwatch?group=all&industry= HTTP/1.1" 200 OK
2026-10-17 17:33:33 INFO:     127.0.0.1:2924 - "GET /api/mstat/industries HTTP/1.1" 200 OK
2026-10-17 17:33:33 INFO:     127.0.0.1:14050 - "GET /api/mstat/smart-money HTTP/1.1" 200 OK
2026-10-17 17:33:34 INFO:     127.0.0.1:13989 - "GET /api/chart/%D9%81%D9%88%D9%84%D8%A7%D8%AF HTTP/1.1" 200 OK
2026-10-17 17:33:42 INFO:     127.0.0.1:7427 - "GET /api/live-stats HTTP/1.1" 200 OK
2026-10-17 17:33:54 INFO:     127.0.0.1:2687 - "GET /api/mstat/series?symbols=%D8%B9%D9%8A%D8%A7%D8%B1%2C%D9%81%D9%88%D9%84%D8%A7%D8%AF%2C%D8%B7%D9%84%D8%A7&days=365 HTTP/1.1" 200 OK
2026-10-17 17:33:58 INFO:     127.0.0.1:2687 - "GET /api/live-stats HTTP/1.1" 200 OK
[OK] portable mode: data=C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\dist\BorsTerminal_Ultimate\data port=8123
==================================================================
  BorsTerminal_Ultimate - smart preflight
==================================================================
  data root: C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\dist\BorsTerminal_Ultimate
  [OK]  market.db: 6,023 instruments (TSETMC + Codal data inside)
[native] persistent webview profile: C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\dist\BorsTerminal_Ultimate\data\BorsTerminal_Ultimate\webview2
  [OK]  bundled libraries: pandas/numpy/fastapi/uvicorn/requests (self-contained)
  [OK]  everything ready - starting ...
==================================================================
2026-10-17 17:34:19 INFO:     Started server process [4832]
2026-10-17 17:34:19 INFO:     Waiting for application startup.
[startup] codal schema migrated (additive, idempotent)
[startup] BORS_NO_FETCH_LOOPS=1 — حلقه‌هایِ شبکه‌ایِ تابلو خاموش (دست‌نخورده خواندنِ بانکِ مشترک؛ برایِ سنجشِ dev کنارِ نسخۀِ نصبی)
[startup] screener warm thread spawned
[startup] candle projection spawned (local-only, one pass)
2026-10-17 17:34:19 INFO:     Application startup complete.
2026-10-17 17:34:19 INFO:     Uvicorn running on http://127.0.0.1:8123 (Press CTRL+C to quit)
2026-10-17 17:34:19 INFO:     127.0.0.1:1237 - "GET / HTTP/1.1" 200 OK
[OK] http://127.0.0.1:8123
2026-10-17 17:34:19 INFO:     127.0.0.1:12541 - "GET / HTTP/1.1" 200 OK
[screener] loaded from disk cache
2026-10-17 17:34:20 INFO:     127.0.0.1:12541 - "GET /favicon.ico HTTP/1.1" 200 OK
2026-10-17 17:34:21 INFO:     127.0.0.1:8599 - "GET /api/health HTTP/1.1" 200 OK
2026-10-17 17:34:21 INFO:     127.0.0.1:8601 - "GET /api/health HTTP/1.1" 200 OK
2026-10-17 17:34:21 INFO:     127.0.0.1:8602 - "GET / HTTP/1.1" 200 OK
  [candles-from-board] latest: 2318 کندل از 1 نشست برایِ 2٬318 نماد (نوشتۀ تازه/بازنشانی‌شده: 0)
2026-10-17 17:34:29 [market] history windows rebuilt in 8.47s (sig=(20261014, 443878, 18743513417152.64, 126231, 3542579310460.0, 220333, 6781594126587.0, 20261014))
2026-10-17 17:34:32 INFO:     127.0.0.1:8603 - "GET /api/market HTTP/1.1" 200 OK
2026-10-17 17:34:32 INFO:     127.0.0.1:8615 - "GET /api/market HTTP/1.1" 304 Not Modified
2026-10-17 17:34:35 WARNING:  api\funnel.py:152: FastAPIDeprecationWarning: ORJSONResponse is deprecated, FastAPI now serializes data directly to JSON bytes via Pydantic when a return type or response model is set, which is faster and doesn't need a custom response class. Read more in the FastAPI docs: https://fastapi.tiangolo.com/advanced/custom-response/#orjson-or-response-model and https://fastapi.tiangolo.com/tutorial/response-model/
  body, etag = _encode_funnel_body(payload if full else _strip(payload))

2026-10-17 17:34:36 WARNING:  fastapi\routing.py:144: FastAPIDeprecationWarning: ORJSONResponse is deprecated, FastAPI now serializes data directly to JSON bytes via Pydantic when a return type or response model is set, which is faster and doesn't need a custom response class. Read more in the FastAPI docs: https://fastapi.tiangolo.com/advanced/custom-response/#orjson-or-response-model and https://fastapi.tiangolo.com/tutorial/response-model/

2026-10-17 17:34:36 INFO:     127.0.0.1:8616 - "POST /api/funnel HTTP/1.1" 200 OK
2026-10-17 17:34:36 INFO:     127.0.0.1:7736 - "GET /api/update/version HTTP/1.1" 200 OK
2026-10-17 17:34:36 INFO:     127.0.0.1:11703 - "GET /api/selection/portfolio HTTP/1.1" 200 OK
2026-10-17 17:34:36 INFO:     127.0.0.1:7736 - "GET /favicon.ico HTTP/1.1" 200 OK
2026-10-17 17:34:36 INFO:     127.0.0.1:4573 - "POST /api/funnel HTTP/1.1" 200 OK
2026-10-17 17:34:36 INFO:     127.0.0.1:6745 - "GET /api/market HTTP/1.1" 200 OK
2026-10-17 17:34:36 INFO:     127.0.0.1:9497 - "POST /api/funnel HTTP/1.1" 200 OK
2026-10-17 17:34:36 INFO:     127.0.0.1:9496 - "GET /api/screener HTTP/1.1" 200 OK
2026-10-17 17:34:36 INFO:     127.0.0.1:13563 - "GET /api/notifications/feed?limit=60 HTTP/1.1" 200 OK
2026-10-17 17:34:36 INFO:     127.0.0.1:9499 - "POST /api/funnel HTTP/1.1" 304 Not Modified
2026-10-17 17:34:36 INFO:     127.0.0.1:9500 - "GET /api/market HTTP/1.1" 200 OK
[screener] cache warmed
[OK] portable mode: data=C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\dist\BorsTerminal_Ultimate\data port=8123
==================================================================
  BorsTerminal_Ultimate - smart preflight
==================================================================
  data root: C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\dist\BorsTerminal_Ultimate
  [OK]  market.db: 6,023 instruments (TSETMC + Codal data inside)
[native] persistent webview profile: C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\dist\BorsTerminal_Ultimate\data\BorsTerminal_Ultimate\webview2
  [OK]  bundled libraries: pandas/numpy/fastapi/uvicorn/requests (self-contained)
  [OK]  everything ready - starting ...
==================================================================
2026-10-17 17:35:32 INFO:     Started server process [11556]
2026-10-17 17:35:32 INFO:     Waiting for application startup.
[startup] codal schema migrated (additive, idempotent)
[startup] BORS_NO_FETCH_LOOPS=1 — حلقه‌هایِ شبکه‌ایِ تابلو خاموش (دست‌نخورده خواندنِ بانکِ مشترک؛ برایِ سنجشِ dev کنارِ نسخۀِ نصبی)
[startup] screener warm thread spawned
[startup] candle projection spawned (local-only, one pass)
2026-10-17 17:35:32 INFO:     Application startup complete.
2026-10-17 17:35:32 INFO:     Uvicorn running on http://127.0.0.1:8123 (Press CTRL+C to quit)
2026-10-17 17:35:32 INFO:     127.0.0.1:5656 - "GET / HTTP/1.1" 200 OK
[OK] http://127.0.0.1:8123
2026-10-17 17:35:33 INFO:     127.0.0.1:10592 - "GET / HTTP/1.1" 200 OK
[screener] loaded from disk cache
2026-10-17 17:35:33 INFO:     127.0.0.1:10592 - "GET /favicon.ico HTTP/1.1" 200 OK
  [candles-from-board] latest: 2318 کندل از 1 نشست برایِ 2٬318 نماد (نوشتۀ تازه/بازنشانی‌شده: 0)
2026-10-17 17:35:34 INFO:     127.0.0.1:2519 - "GET /api/health HTTP/1.1" 200 OK
2026-10-17 17:35:34 INFO:     127.0.0.1:2520 - "GET /api/health HTTP/1.1" 200 OK
2026-10-17 17:35:34 INFO:     127.0.0.1:2521 - "GET / HTTP/1.1" 200 OK
2026-10-17 17:35:40 [market] history windows rebuilt in 6.38s (sig=(20261014, 443878, 18743513417152.64, 126231, 3542579310460.0, 220333, 6781594126587.0, 20261014))
2026-10-17 17:35:44 INFO:     127.0.0.1:2522 - "GET /api/market HTTP/1.1" 200 OK
2026-10-17 17:35:44 INFO:     127.0.0.1:2530 - "GET /api/market HTTP/1.1" 304 Not Modified
[screener] cache warmed
2026-10-17 17:35:47 WARNING:  api\funnel.py:152: FastAPIDeprecationWarning: ORJSONResponse is deprecated, FastAPI now serializes data directly to JSON bytes via Pydantic when a return type or response model is set, which is faster and doesn't need a custom response class. Read more in the FastAPI docs: https://fastapi.tiangolo.com/advanced/custom-response/#orjson-or-response-model and https://fastapi.tiangolo.com/tutorial/response-model/
  body, etag = _encode_funnel_body(payload if full else _strip(payload))

2026-10-17 17:35:47 INFO:     127.0.0.1:2531 - "POST /api/funnel HTTP/1.1" 200 OK
2026-10-17 17:35:47 INFO:     127.0.0.1:2532 - "POST /api/funnel HTTP/1.1" 200 OK
2026-10-17 17:35:47 INFO:     127.0.0.1:2533 - "POST /api/funnel HTTP/1.1" 304 Not Modified
2026-10-17 17:35:47 INFO:     127.0.0.1:2534 - "GET /api/market HTTP/1.1" 200 OK
```
