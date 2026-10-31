# B3 — چارت، سطوح، تقویم و موتورِ FTS

**Spec:** `docs/superpowers/specs/2026-10-29-backend-go-rewrite-design.md` (§۶ و §۸، مرحلهٔ B3)
**پیش‌نیاز:** B2 کامل و سبز (`docs/superpowers/reports/2026-10-31-b2b-13-route-parity.md`، ۳۸ کیس، Δ=۰)
**Branch:** `mission/4-axes-2026-10-10`

## دامنه

۹ مسیرِ GETِ `api/chart.py` (۳۲۱۶ خط؛ موتورِ FTS هم داخلِ همین فایل است، نه در `fts_engine.py`):

| مسیر | تابع | منبعِ داده | در B3 |
| --- | --- | --- | --- |
| `GET /api/chart-db/{symbol}` | `get_chart_db` (1185) | `price_history` + `market_watch` + `adjust_events` + `price_adjust_events`/`share_change_events` + موتورِ FTS | پورت |
| `GET /api/chart/{symbol}/key-levels` | `get_key_levels` (802) | `price_history` (۲۵۰ روز) + `price_basis` | پورت |
| `GET /api/order-book/{symbol}` | `get_order_book` (846) | `order_book.book_txt` + `market_watch` | پورت |
| `GET /api/calendar/upcoming` | `get_calendar_upcoming` (1092) | `static/calendar/cache.json` + «امروز» | پورت |
| `GET /api/calendar/{symbol}` | `get_calendar_events` (1111) | همان کشِ تقویم | پورت |
| `GET /api/ma/{symbol}` | `get_ma_events` (1123) | `price_history` + تقویم + `price_basis` | پورت |
| `GET /api/patterns/{symbol}` | `get_patterns` (1272) | `price_history` + `adjust_events` + `price_basis` | پورت |
| `GET /api/fts/{symbol}` | `get_fts` (3200) | `price_history` + `adjust_events` + `user.db` + موتورِ FTS | پورت |
| `GET /api/chart/{symbol}` | `get_chart_tsetmc` (531) | CDN + فال‌بکِ محلی + **نوشتنِ** `adjust_events` | **نه — B6** |

سه چیز بیرون از دامنه:

- `GET /api/chart/{symbol}`: شاخهٔ CDN به `cdn.tsetmc.com` وصل می‌شود و رویِ شاخهٔ موفق
  `_store_adjust_events` در `market.db` **می‌نویسد** (۲۴۸) و `_schedule_history_repair`
  یک رشتهٔ پس‌زمینهٔ شبکه‌ای باز می‌کند (۴۶۷). در فازِ A، Go رویِ `market.db` فقط‌خواندنی
  است (spec §۵) و هارنسِ پخشِ ضبط‌شده (G3) هم مالِ B6 است. پس این مسیر تا B6 در Go
  همان `501 NOT_PORTED` را می‌دهد و گیت آن را **اندازه می‌گیرد**، فرض نمی‌کند.
- `POST /api/orderbook/watch` و `GET/POST /api/fts/config` در `api/market.py` هستند
  (اشتراکِ زنده/تنظیمات)، نه `api/chart.py`؛ تا B6/B7 `501` می‌مانند.
- نوشتنِ `price_basis.json`/`fts_thresholds.json` (مسیرهایِ تنظیمات) بیرون از B3 است؛
  B3 فقط **می‌خواند** (با همان اعتبارسنجی و همان fallback).

## تصمیم‌های پیش از اجرا

- **R1 — Go در B3 نه شبکه می‌زند نه در `market.db` می‌نویسد.** همهٔ مسیرهایِ پورت‌شده از
  `price_history`/`order_book`/`instruments`/تقویم می‌خوانند؛ `adjust_events` و
  `adjust_verdict` اگر نبودند، مثلِ پایتون «تهی» خوانده می‌شوند، ولی Go جدول نمی‌سازد
  (پایتون `CREATE TABLE IF NOT EXISTS` می‌زند — اثرِ جانبیِ سنجیده و اعلام‌شده).
- **R2 — درزِ `BORS_CHART_CDN=off` در پایتون.** با این متغیر، `get_chart_tsetmc` پیش از
  هر درخواستِ شبکه به `_fallback_local` می‌رود و `_schedule_history_repair` دست‌کم
  `False` می‌دهد. پیش‌فرض دست‌نخورده است؛ گارد با کنترلِ منفی ثابت می‌کند بی این متغیر
  `requests` واقعاً صدا زده می‌شود. مصرف: فقط پاریتی/CI (همان الگویِ `BORS_CODAL_OFFLINE`).
  بی این درز، `/api/fts` و `/api/patterns` در گیت به CDNِ واقعی می‌زنند — که ممنوع است.
- **R3 — درزِ `BORS_CALENDAR_PATH` در `bors_config.py`.** `_CAL_CACHE_PATH` پیش‌فرض همان
  `APP_DIR/static/calendar/cache.json` می‌ماند؛ پاریتی هر دو سرور را به **یک** فایلِ
  تقویمِ فیکسچر (با رویدادهایِ نزدیک به «امروزِ» ثابت) اشاره می‌دهد تا `calendar/upcoming`
  به تقویمِ واقعیِ ماشین وابسته نباشد. همان‌جا مسیرِ `fts_thresholds.json` و
  `price_basis.json` هم از `BORS_DATA_DIR` می‌آید (پایتون: `WORK_DIR`).
- **R4 — «امروز» تزریق‌شدنی است.** تنها مصرفِ تاریخِ دیواری در این ۸ مسیر
  `_upcoming_by` است (`datetime.date.today()`). اوراکل `chart.datetime` را قفل می‌کند و
  سرویسِ Go یک `Clock func() time.Time` می‌گیرد؛ در گیت هر دو طرف ساعتِ واقعیِ یک روز را
  می‌بینند، در طلایی‌ها ۲۰۲۶-۱۰-۲۸ قفل است.
- **R5 — موتورِ FTS کامل می‌آید.** `_fts_*` (۱۴۰۹–۲۷۴۰) + `trend_classify.py` (۱۴۹ خط) با
  هر دو حالتِ `BORS_TREND_ENGINE=legacy|hybrid`؛ پیش‌فرض `legacy`. `JET_LADDER` از پکیجِ
  موجودِ `internal/tapeflags` خوانده می‌شود (بازتعریف نمی‌شود).
- **R6 — کش‌ها مثلِ پایتون، درونِ سرویس.** `KEY_LEVELS_CACHE`/`MA_CACHE`/`PATTERNS_CACHE`
  با TTLِ ۳۰۰/۹۰۰ ثانیه و کلیدِ `symbol|...|basis`، و `FTS_ANALYSIS_CACHE` با TTLِ ۹۰۰،
  سقفِ ۳۰۰۰ و کلیدِ `symbol|last_close|entry_hint|as_of|ruleset|engine|hg|basis`. خواندنِ
  `price_basis.json`/`fts_thresholds.json` با امضایِ `(mtime,size)` تا تغییرِ فایل فوراً
  اثر کند. کندلِ زنده رویِ نسخه می‌نشیند، نه در کش (مثلِ `_attach_live_bar`).
- **R7 — فیکسچرِ نو، جدا از mstat.** `backend-go/internal/chart/testdata/fixture/`:
  همان نُه نمادِ m1..m9 (پیوستگیِ نام) ولی با `price_history`ِ ده‌ستونی و تاریخچهٔ عمیق
  (۳۲۰ نشست برای پنج نمادِ کانونی، ۴۰ نشست برای کوتاه‌تاریخ، بی‌ردیف برای بی‌داده)،
  `adjust_events`/`adjust_verdict`، `price_adjust_events`/`share_change_events`،
  `order_book` (۵ سطح)، `market_watch` با نشستِ زنده، تقویمِ کوچک، `fts_thresholds.json`،
  `price_basis.json`، و `user.db` با `selection_decisions` (accept/price>0، accept/0، reject).
  داده‌ها قطعی‌اند (فرمولِ بی‌تصادف) و گارد دو ساختِ مستقل را sha256 می‌کند.
- **R8 — گیت رویِ کپیِ یخ‌زدهٔ بانکِ عملیاتی، با کیس‌هایِ پویا.** مثلِ B1/B2: کپیِ
  snapshot از `market.db`/`user.db` ریشه، پورت‌هایِ 8296/8297، اثرانگشتِ ریشه، گاردِ
  کناربانک، و کشتنِ فقط PIDِ خودِ اسکریپت. نمادِ هر کیس از خودِ کپی انتخاب می‌شود
  (عمیق‌ترین تاریخچه، دارایِ `price_adjust_events`، دارایِ `order_book.book_txt`،
  کوتاه‌تاریخ، ناموجود) تا وابسته به یک نامِ ثابت نباشد.
- **R9 — اختلاف‌هایِ اعلامی، اندازه‌گیری‌شده.** (۱) `/api/chart` در Go 501 و در پایتون 200؛
  (۲) `liveError` متنِ درایورِ SQLite است، پس از مقایسه مستثنا و فقط «null یا رشتهٔ
  ناتهی» سنجیده می‌شود؛ (۳) در پایتونِ بدونِ درز، `/api/fts` سریِ CDN را تحلیل می‌کند و
  Go تا B6 سریِ محلی را — در گیت هر دو محلی‌اند و همین صریح در گزارش می‌آید؛ (۴) پایتون
  رویِ کپی دو جدولِ `adjust_*` را می‌سازد، Go نمی‌سازد (پاسخ یکی است)؛ (۵) کلیدِ کش
  داخلی است و رویِ سیم دیده نمی‌شود.

## Task 1 — درزها، فیکسچر، اوراکل، طلایی‌ها، گارد

- `api/chart.py`: `_cdn_enabled()` + شرطِ فال‌بک در `get_chart_tsetmc` و
  `_schedule_history_repair`؛ `bors_config.py`: `BORS_CALENDAR_PATH`.
- `tools/parity/make_chart_fixture.py` → `backend-go/internal/chart/testdata/fixture/`.
- `tools/parity/gen_chart_golden.py`: ساعت ۲۰۲۶-۱۰-۲۸ ۱۰:۳۰، «امروز» ۲۰۲۶-۱۰-۲۸،
  `BORS_CHART_CDN=off`، تقویمِ فیکسچر. صحنه‌ها:
  - `s1` پیش‌فرض (مبنای `last`): `chartdb_*` برایِ پنج نمادِ کانونی + کوتاه‌تاریخ + بی‌داده +
    دو-املا، `keylevels_*`، `ma_*`، `patterns_*`، `orderbook_*`، `calendar_symbol_*`،
    `calendar_upcoming`، `fts_*` (شاملِ `as_of` و نمادِ سبددار).
  - `s2` بدونِ جدولِ `order_book` (شاخهٔ `no_data`).
  - `s3` تنظیماتِ سفارشیِ ساعتِ شنی (`fts_thresholds.json`).
  - `s4` مبنای `closing` و سریِ دارایِ `last`ِ گمشده (سه‌حالتیِ MA + `priceBasis*`).
- `dev/test_chart_fixture_b3.py`: قطعیتِ فیکسچر (دو ساخت + فایلِ کامیت‌شده)، برابریِ
  طلایی‌ها با اجرایِ تازه، شرطِ محتوا برایِ هر مسیر (۵ سطحِ سفارش، ۵-نمادِ هندسه،
  `priceBasisApplied/Reason`، `as_of`)، شمارشِ صحنه‌ها، و **کنترلِ منفیِ درزها**:
  بی `BORS_CHART_CDN` → `requests.get` صدا زده می‌شود؛ با `off` → هرگز؛ بی
  `BORS_CALENDAR_PATH` → مسیرِ APP_DIR. ثبت در `dev/run_all_tests.py`.

## Task 2 — کتابخانه‌هایِ مشترک

- `internal/symbolid` (پورتِ `symbol_identity.py`، ۳۸۸ خط): `key/norm/variants/line_variants/
  class_siblings/pred/evidence/sources` با کشِ مبتنی بر `PRAGMA data_version` رویِ یک
  `*sql.Conn` اختصاصی (Go رویِ `market.db` نمی‌نویسد، پس همان دو سیگنالِ پایتون کافی است).
- `internal/pricebasis`: `current/describe/closingOf/lastOf/closeOf/basisOfRow/applyBasis/
  resolvePayload/stamp` (قراردادِ `docs/CANDLE-CONTRACT.md`؛ `copy` همیشه).
- `internal/candle`: فقط `widen` (+ ثابت‌هایِ `SRC_*`/`RANK` اگر لازم شد).
- تست: وکتورهایِ طلایی از خودِ پایتون (`libcases.json` در همان اوراکل) + تستِ
  control-منفی برایِ `line_variants` (پسوندِ رقمی) و `apply_basis` (گِشاد/`last_missing`).

## Task 3 — مسیرهایِ ساده (۶ مسیر)

- `internal/chart`: `orderbook.go` (JSONِ `book_txt`، `no_data`)، `calendar.go` (کشِ mtime،
  `_cal_classify`، `event_date_source`، `upcoming_*` با مرتب‌سازیِ پایدار)، `levels.go`
  (`_swing_extremes`/`_merge_levels`/`_order_blocks`/`_key_levels_from_history`)، `ma.go`،
  `patterns.go` (tsِ ظهرِ UTC، ضریبِ تعدیل، overlays).
- `handlers.go`: اعتبارسنجیِ FastAPI (`days`/`adjustment` غیرعدد → ۴۲۲ `int_parsing`)،
  پوششِ `status:error` با پیامِ همان مسیر، و `httpapi` routes.
- تست: طلایی‌هایِ s1/s2 + وکتورهایِ `_merge_levels`/`_order_blocks`/`days` clamp.

## Task 4 — موتورِ FTS، هستهٔ روند و ساختار

- `fts_swings.go` (`_fts_resample`، `_fts_swings`)، `fts_trend.go` (`_fts_recent_window_trend`،
  `_fts_classify_trend`، `_fts_trend_reason`)، `trendclassify.go` (پورتِ `trend_classify.py`)،
  `fts_fib.go` (`_fts_fib_leg/zones/price/retrace`)، `fts_jet.go` (`_fts_jet_setup` با
  `tapeflags.JET_LADDER`)، `fts_choch.go`، `fts_pointhunt.go`، `fts_doublebottom.go`،
  `fts_setups.go` (`_fts_setup_history`، برچسب‌ها).
- تست: وکتورهایِ swing/trend (up/down/range/na + `recent-window` + کهنگی)، فیبو، جت،
  CHoCH، دابل‌باتم — هر شاخه دست‌کم یک وکتورِ نام‌دار با عددِ دقیق.

## Task 5 — موتورِ FTS، خروج و وضعیت

- `fts_exit.go`: `_fts_ma`، `_fts_rsi` (warmupِ بذرِ دقیق)، `_fts_exit_layer1..4`،
  `_fts_exit_engine`.
- `fts_status.go`: `_fts_status_block`، `_fts_roles_table`، `FTS_STATUS_PRIORITY/TEXT`،
  برچسب‌هایِ ستاپ/تریگر؛ همهٔ رشته‌ها زیررشتهٔ `api/chart.py` سنجیده می‌شوند.
- تست: RSI (طولِ کوتاه، صعودیِ مطلق، واگرایی)، چهار لایه با `entry_hint`، ترتیبِ وضعیت.

## Task 6 — تحلیل، chart-db و `/api/fts`

- `fts_analyze.go`: `_fts_clean_candles`، `_fts_analyze_candles` (ماتریسِ روند، ساعتِ شنی،
  `trend_engine`)، `_fts_hourglass_settings` (امضایِ فایل)، `_fts_fa`.
- `chartdb.go`: `get_chart_db` کامل (`_watch_live_bar`، `_stored_adjust_*`،
  `_adjust_capability`، `_factors_from_events`، `_corporate_events`، `_fts_scaled`،
  `resolve_payload`) + `_basket_entry` + `_fts_analysis_series` + `_candles_upto_asof` +
  کشِ ۹۰۰ ثانیه‌ای.
- `handlers.go`: `ChartDB`، `FTS`؛ `httpapi` دو GET + تستِ مسیرها (۹ مسیر، `chart` هنوز ۵۰۱).
- تست: طلایی‌هایِ s1/s3/s4 برایِ `chartdb_*`/`fts_*`، کنترلِ منفیِ `as_of` (کندلِ بعد از
  برش نباید اثر بگذارد)، `entry_hint` (سبددار/بی‌سبد)، و `last_missing` در `chartdb`.

## Task 7 — گیتِ B3 و گزارش

- `tools/parity/cases_b3.json` + `gate_b3.py` (همان بدنهٔ `gate_b1`/`gate_b2a`): ۸ مسیر ×
  کیس‌هایِ پویا از کپی + کیس‌هایِ ۴۲۲؛ `GET /api/chart/{symbol}` همچنان ۵۰۱ در Go و ۲۰۰
  در پایتون **اندازه‌گیری** می‌شود؛ پوششِ هر ۹ مسیر اجباری است.
- شاهد: `_audit/parity/B3.json` و `B3-contract.json` (Δ=۰، بیشینهٔ دلتا، اثرانگشتِ ریشه،
  کپیِ Go دست‌نخورده، کناربانک، ۵ ردیفِ سفارش، سه‌حالتیِ MA، دو نمادِ تعدیل/صندوق).
- گزارشِ فارسی `docs/superpowers/reports/2026-10-31-b3-chart-parity.md` + بازبینیِ مستقل +
  دورِ اصلاح + لجر + پوش.

## چه چیزی در B3 نیست

- `GET /api/chart/{symbol}`، CDN، `_store_adjust_events`، و ترمیمِ پس‌زمینهٔ تاریخچه (B6).
- `POST /api/orderbook/watch` و `GET/POST /api/fts/config` (B6/B7).
- نوشتنِ تنظیمات (`price_basis.json`/`fts_thresholds.json`) — B3 فقط می‌خواند.
- هیچ کاربرِ ریلیز/نصب در این مرحله دیده نمی‌شود؛ برنامهٔ نصب‌شده هنوز پایتون اجرا می‌کند.
