# Change: افزودنِ `last`/`value` به `price_history` و پایانِ جعلِ `last := close` (کارِ #73، قدمِ ۲)

## Scope
تنها لایۀِ داده (bank + fetcherها + یک خوانندۀ `/api/chart-db`). هیچ رأیِ تکنیکالی، هیچ
اندیکاتوری و هیچ کامپوننتِ فرانتی دست نمی‌خورد؛ `price_basis()` و مهاجرتِ هشت سازنده
قدم‌های ۳-۵ همین فایل‌اند. عددِ مبنایِ تصمیم: `docs/CANDLE-CONTRACT.md` §۱-پ و §۱-ج.

فایل‌ها:
1. `mstat_engine.py:190` — `MIGRATIONS`: `price_history += (last REAL, value REAL)`،
   `daily_prices += (p_last REAL)` (منبعِ یکتای DDL؛ همان‌جا که `market_watch` و
   `paper_type` اضافه شده‌اند).
2. `test_tsetmc.py:926` و `codal_fetcher.py:589` — دو تعریفِ هم‌سانِ `CREATE TABLE
   price_history`؛ هر دو با دو ستونِ تازه یکی می‌شوند (اگر یکی بماند، بانکِ تازه با
   بانکِ مهاجرت‌شده_diff می‌شود و `_DP_INSERT`-وار خطایِ عددِ ستون می‌دهد).
3. نویسندگانِ `price_history` (inventory §۲-الف):
   - مسیرِ ۱ `fetch_price_history` `test_tsetmc.py:1171-1201`: `INSERT` بی‌نامِ
     ۷-مقداری → `INSERT` با ستون‌هایِ نام‌دار؛ `open` از `fields[2]` (= FIRST) نه
     `fields[10]` (= OPEN/پایه) — سنجشِ §۱-ج الف: FIRST ۱۴٬۲۱۰/۱۴٬۷۰۶، OPEN صفرِ مطلق؛
     `last` از `fields[11]` (LAST)، `value` از `fields[6]` (VALUE).
   - مسیرِ ۲ `candle_from_row` + `sync_price_history_from_daily` `test_tsetmc.py:1002-1097`:
     دو آرگومانِ تازه (`last`, `value`) از `daily_prices.p_last`/`q_tot_cap`؛ کوئریِ منبع
     و `executemany` نام‌دار.
   - `_mw_row` `test_tsetmc.py:1309-1322`: `p_last` از کلیدِ خامِ `pdv` (سنجیده‌شده:
     `pdv == CSV LAST` درِ ۶/۶ نماد، `pmd` هم ۶/۶ — `_audit/mw_key_to_csv_column.json`)،
     با fallback به `py + pc` وقتی `pdv` صفر است (ردیفِ پیش از بازگشایی). امروز `pcl`
     (== CLOSE، ۶/۶) به‌عنوانِ `p_closing` درست است و می‌ماند.
   - `_DP_INSERT` `test_tsetmc.py:90-94`: ستونِ ۱۵ام (`p_last`)؛ placeholderها با شمارِ
     ستون‌ها قفل می‌شوند ⇒ درِ همان سطر.
   - مسیرِ ۳ `tools/backfill_daily_history.py:107-121`: `INSERT` نام‌دار؛ این endpoint
     («GetInstrmentsHistoryInDay») هیچ کلیدِ «آخرین» ندارد (همۀ کلیدهایِ یکِ ردیفِ واقعی
     dumped: priceMin/Max/Yesterday/First/Change, pClosing, pDrCotVal, zTotTran,
     qTotTran5J, qTotCap) ⇒ `last` عمداً `NULL` و `value` از `qTotCap`.
4. خوانندۀ `/api/chart-db` `api/chart.py:890-908`: `last` و `value` از بانک خوانده
   می‌شوند؛ جعلِ `last := close` حذف و جایش `NULL`ِ صادقانه می‌نشیند (قرارداد §۱-ث شرطِ ۳).
   تا قدمِ ۵ هیچ مصرف‌کننده‌ای `last` را نمی‌خواند (inventory §۸: `c.last` هرگز خوانده
   نمی‌شود)، پس حذفِ جعل همین حالا فقط «دروغِ payload» را کم می‌کند و عددِ نمایشی را عوض
   نمی‌کند.

## Invariants touched
- **منبعِ یکتای DDL** (`mstat_engine.MIGRATIONS`) — حفظ: ستون‌ها همان‌جا اضافه می‌شوند، نه
  با `ALTER` پراکنده.
- **ترتیبِ ثبتِ route و عمرِ startup** — دست‌نخورده.
- **market.db.lzma کنارِ EXE** — ستون‌هایِ تازه additive و nullable‌اند؛ بانکِ baselineِ
  قدیمی درِ اولینِ اتصال با `ensure_schema` (`api/_core.py:125`) ALTER می‌خورد، پس baseline
  جدید لازم نیست (و درِ این قدم باز‌بسته نمی‌شود).
- **numpy==2.0.2 / onedir / hiddenimports** — هیچ ماژولِ تازه‌ای اضافه نمی‌شود ⇒
  `fts_terminal.spec` دست‌نخورده (تازۀ `dev/` گارد است، نه importِ تولیدی).
- **هیچ‌وقت git checkout/reset/stash** — مهاجرت رویِ **کپیِ** بانک آزموده می‌شود؛
  `market.db` واقعیِ ریپو و بانکِ app نصبی (۸۰۰۱) و dev (۸۰۰۲) دست‌نخورده.

## Lockstep updates (spec / eslint / guards)
- `dev/candles_from_board_v1062.py:71,163` — فیکسچرش `CREATE TABLE price_history` هفت‌ستونی
  و `INSERT INTO price_history VALUES (?,?,?,?,?,?,?)` دارد؛ با امضایِ جدیدِ
  `candle_from_row` و ستون‌هایِ نام‌دار هم‌خوان می‌شود (وگرنه گارد سبزِ ساختگی می‌دهد).
- `dev/board_hist_cache_v1056.py:338` — همان فیکسچرِ هفت‌ستونی.
- `dev/incremental_sync_resilience.py:81-83` — ستون‌هایِ نام‌دار، بی‌تغییرِ رفتار.
- `frontend/eslint` و `package.json` — بی‌کاربرد (تغییرِ سمتِ سرور).

## Guard that proves it
`dev/price_last_value_v1070.py` (تازةِ این قدم)، چک‌ها رویِ کپیِ بانک:
1. `PRAGMA table_info(price_history)` هر دو ستون را دارد و `daily_prices.p_last` هم هست.
2. هیچ `INSERT ... VALUES` بی‌نامی درِ نویسندگانِ `price_history` نمانده (grepِ استاتیک).
3. `open == FIRST` درِ مسیرِ ۱ با فیکسچرِ ردیفِ CSV که FIRST ≠ OPEN دارد (تضمینِ رگرسیون).
4. `last` از `pdv` می‌آید و `p_closing` از `pcl` — فیکسچرِ ردیفِ تابلو با دو عددِ متفاوت.
5. `/api/chart-db` برایِ ردیفِ فاقدِ last مقدارِ `None` می‌دهد نه close.
6. **لنگرِ تعدیل بی‌تغییر:** `_adjust_events_from_rows` رویِ همان `base=OPEN`/`close=CLOSE`
   می‌ماند و تعدادِ رویدادها با presenceِ ستونِ `last` عوض نمی‌شود (قدمِ ۴ کاملش می‌کند).

## Rollback
تغییرات همه درِ گیت؛ ستون‌های SQLite additive و nullable‌اند ⇒ rollbackِ کد بی‌نیازِ
`DROP COLUMN` است (کدِ قدیمی ستون‌هایِ اضافه را نمی‌بیند و INSERTهایش دوباره هفت‌تایی
می‌شوند — همان چیزی که برایِ سازگاریِ بانکِ قدیمی لازم است). اگر لازم شد، بانکِ آزموده‌شده
یک کپی است و `market.db` اصلی از ابتدا دست‌نخورده مانده.
