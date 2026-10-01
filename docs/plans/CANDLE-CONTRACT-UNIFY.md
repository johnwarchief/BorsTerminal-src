# Change: قراردادِ واحدِ کندل — یکِ هندسه، یکِ مالکیتِ سطر، یکِ منبعِ نام‌دار (Step 4، کارِ #73)

## Scope

پیش از هر کد، واگرایی **اندازه** گرفته شد (نه از روی کاغذ):

| سند | چه می‌گوید |
|---|---|
| `_audit/candle_builder_divergence.py` | از ۱٬۱۹۵ روزِ مشترکِ «کندلِ RAMِ `/api/chart`» ⇄ «`/api/chart-db`»: open در ۳۰۴ روز، high در ۷۶، low در ۱۰۹، close در ۳ روز فرق دارد. مصرف‌کننده‌ها (screener/confidence) رویِ OHLC هیچ واگرایی ندارند (۰/۱٬۲۰۱ و ۰/۷۵۰) — واگرایی درِ **ساخت**، نه خواندن است. |
| `_audit/candle_source_priority_probe.py` | ۷۲ نشستِ مشترکِ تابلو/CSV: تنها **۴** واگرایی، و هر چهار رویِ یکِ روز (۲۰۲۶-۰۹-۰۱) ⇒ `INSERT OR REPLACE` بی‌اولویت: مسیرِ ۲ snapshotِ میانه/پیش‌بستُُن را رویِ ردیفِ **منتشرشده** می‌کُوبَد. + **۸ روزِ شبح** درِ `price_history` که درِ فهرستِ منتشرشده هیچ‌وقت نبوده. + `p_last` درِ همهٔ ۷۲ ردیفِ تابلویِ قدیمی NULL است. |
| `_audit/legacy_open_basis.json` | ۱٬۲۷۲ ردیفِ بانک: open==FIRST در ۷۹۹ (۶۲٫۸٪) ولی open==پایه در **۴۷۰ (۳۷٪)** — و همه درِ یکِ نماد (شبندر ۴۷۰/۴۸۱، فولاد ۰/۳۷۲، خگستر ۰/۴۱۹). یعنی مبنایِ open **نماد‌به‌نماد** بر حسبِ «کدام نویسندۀ آخر نوشت» فرق می‌کند — همان چیزی که inventory §۲-الف هشدار داد و هیچ تستی نگهش نمی‌داشت. `last` درِ ۱٬۲۷۲/۱٬۲۷۲ ردیف NULL است (قدمِ ۲ تازه ستون را ساخت). |

فایل‌ها:

1. **`candle_contract.py` (تازہ، ریشۀ ریپو)** — سه چیز، همه درِ یکِ جا:
   - `widen(o, h, l, c) → (h, l)` — **تنها** قاعدۀ هندسه (سایه گِشاد می‌شود، بدنه/پایانی خُرد
     نمی‌شود). امروز سه پیادهٔ هم‌سان دارد: `api/chart.py:86`، `test_tsetmc.candle_from_row`
     (`:1041-1042`)، `normalize_price_history_geometry` (`:1123`) + یک پیادهٔ **مخالف**
     (clampِ open درِ `api/market_index.py:157`).
   - `SRC_*` + `write_sql()` — مالکیتِ سطر با ستونِ `price_history.src`:
     `published` (CSV/`GetInstrmentsHistoryInDay`) بر `board` (snapshotِ تابلو) اولویت دارد،
     و `board` هرگز ردیفِ `published` را بازنویسی نمی‌کند.
   - `from_db_row` / `from_csv_row` / `from_board_row` — یکِ شکلِ خروجی برایِ هر سه منبع.
2. `mstat_engine.MIGRATIONS`: `price_history += (src TEXT)` (additive، nullable).
3. هر چهار نویسندۀ `price_history` ستونِ `src` را می‌نویسند و از `widen()` می‌گذرند:
   `fetch_price_history` (published) · `candle_from_row`+`sync_price_history_from_daily`
   (board) · `tools/backfill_daily_history.py` (published) · `normalize_price_history_geometry`
   (بازنویسندۀ هندسه — هندسه را از همان یک تابع می‌گیرد).
4. `api/market_index.py`: clampِ open جایش به `widen()` می‌رود (شاخص openِ ساختگی دارد؛
   سایه باید گِشاد شود نه بدنه خُرد) و `src:"index-synthetic-open"` درِ payload ثبت می‌شود.
5. `_watch_live_bar` و `_parse_tsetmc_csv` از `widen()` عبور می‌کنند (سریِ RAM).

## Invariants touched
- **منبعِ یکتای DDL** (`MIGRATIONS`) — حفظ: ستونِ `src` همان‌جا اضافه می‌شود.
- **هر سازندۀ کندل باید هر دو مبنای نام‌دار بدهد** (§۱-ث) — حفظ؛ `src` اضافه می‌شود تا
  «چه کسی این سطر را نوشت» قابلِ گزارش باشد (پیش‌نیازِ رفعِ ۴۷۰ ردیفِ legacy و ۸ ردیفِ شبح).
- **لنگرِ تعدیل = CLOSING** — دست‌نخورده؛ `widen()` هرگز `close` را عوض نمی‌کند و
  `_adjust_events_from_rows` از `all_rows` خام می‌خواند.
- **market.db.lzma کنارِ EXE / onedir / numpy==2.0.2** — `src` additive و nullable است؛
  baselineِ قدیمی با اولینِ اتصال ALTER می‌خورد. هیچ وابستگیِ تازه‌ای اضافه نمی‌شود ⇒ spec
  فقط `price_basis`-طور: `candle_contract` هم به hiddenimports اضافه می‌شود.
- **هیچ git checkout/reset/stash؛ کار رویِ کپیِ بانک** —migration و هر دو سنجشِ جدید رویِ
  کپی (`sqlite3.backup`) اجرا می‌شوند؛ app نصبی (۸۰۰۱) و dev (۸۰۰۲) دست‌نخورده.

## Lockstep updates (spec / eslint / guards)
- `fts_terminal.spec` hiddenimports += `candle_contract` (ایمپورتش سطح-بال است اما مثل
  `tape_flags` صریح فهرست می‌شود).
- `dev/candles_from_board_v1062.py` — فیکسچرها `src` را ندارند ⇒ `executemany` با ستون‌هایِ
  نام‌دار و فیکسچرِ ۱۰-ستونی هم‌خوان می‌شود.
- `dev/price_last_value_v1070.py`، `dev/history_depth_v1070.py`، `dev/board_hist_cache_v1056.py`،
  `dev/market_db_union_v1069.py`، `dev/incremental_sync_resilience.py` — فیکسچرهایِ CREATE
  باید ستونِ `src` را داشته باشند.
- frontend/eslint — بی‌کاربرد (تغییرِ سمتِ سرور).

## Guard that proves it
`dev/candle_contract_v1071.py` (تازہ، آفلاین):
1. یکِ ردیفِ ورودیِ یکسان از `from_csv_row`، `from_board_row` و `from_db_row` می‌گذرد ⇒
   **سه خروجیِ عددیِ یکسان** (بدنه، سایه، last، value) — این خودِ «حذفِ divergence» است.
2. `widen()` رویِ پنج حالتِ لبه (h<payani، l=0، o بیرونِ بازه، last بیرونِ بازه، روزِ بی‌معامله).
3. **مالکیتِ سطر**: مسیرِ board رویِ ردیفِ `published` نمی‌نویسد؛ مسیرِ published رویِ
   ردیفِ board می‌نویسد؛ ردیفِ شبح (منبعِ غیرمنتشر) ساخته نمی‌شود.
4. **NEGATIVE CONTROL**: اگر روزی `widen()` حذف/تکراری شود، گارد قرمز می‌شود (تک‌پیاده).
5. legacy repair: ردیفِ `src=NULL` با re-publish اصلاح می‌شود و `close`ش تکان نمی‌خورد.

## Rollback
کامیت‌ها درِ گیت؛ `src` additive/nullable است ⇒ rollbackِ کد بی‌DROP COLUMN ممکن است
(کدِ قدیمی ستون را نمی‌بیند). اولویتِ نوشتن با حذفِ شرطِ `WHERE` به رفتارِ امروز برمی‌گردد.
