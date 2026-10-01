# موجودیِ کاملِ جریانِ دادهٔ کندلِ روزانۀ تهران — Rahavard Parity Inventory

این فایل inventoryِ §۲-۴ سند `docs/CANDLE-CONTRACT.md` است («یکِ مسیرِ تولیدِ کندل — شمارشِ
نویسدگانِ price_history و خوانندگانِ آن»). هیچ چیزی در این فایل «احتمالاً» نیست: هر ادعا
شمارۀ خط دارد، و هر جایی که چیزی پیدا نشد صریحاً نوشته شده «یافت نشد» با ذکرِ آنچه جست‌وجو شد.
مبنایِ داوری: قراردادِ نهاییِ §۱-ت همان فایل — **Display Close = LAST؛ محاسباتِ تکنیکال بر
همان مبنایِ نمایشی؛ لنگرِ زنجیرِ تعدیل = CLOSING؛ این دو هرگز قاطی نمی‌شوند.**

نتیجهٔ سنجشِ ۸۰۰نمادی (`_audit/last_close_blast_radius.py`، `_audit/last_blast_radius/report.json`):
در حالتِ B1 (تعدیل هم به LAST) لنگرِ **۷۳۹ از ۸۰۰ نماد (۹۲٪)** می‌شکند
(`4_adjustment_drift_naive.symbols_anchor_lost_naive = 739`، `max_oldest_factor_shift ≈ ×۲۷۰٬۴۷۵`)؛
در حالتِ B2 (نمایش LAST، تعدیل CLOSE-محور) رأی‌هایِ کلیدیِ `matrix.decision`/فیبو/hard_stop صفر
جابه‌جا می‌شوند. پس تفکیکِ زیرِ کلِ این موجودی بارِ ساختاری دارد.

---

## ۰) نمایِ کلیِ زنجیر

```
TSETMC (5 endpoint خام)
  ├─ GetMarketWatch (تابلو)            → market_watch / daily_prices / instruments / order_book
  ├─ GetClosingPriceDailyListCSV       → price_history (مسیرِ ۱) و کندلِ RAMِ /api/chart (مسیرِ ۵)
  ├─ GetInstrmentsHistoryInDay         → price_history (مسیرِ ۳، دستی)
  ├─ GetClosingPriceDailyAllInst [ih]  → tape_history (کندل نمی‌سازد؛ پنجرۀ فیلتر)
  └─ Index/GetIndexB2History           → کندلِ ساختگیِ شاخص کل (مسیرِ ۸)
price_history ──► /api/chart-db، /api/history، /api/ma، key-levels، patterns، پنجرۀ تابلو، confidence
/api/chart (CDN) ──► فرانت (KLineChartWrapper + TechnicalPage/FFC) ──► تجمیع هفتگی/ماهانه ──► چارت/اندیکاتور/سیگنال
```

---

## ۱) مرحلۀ «دیتای خامِ TSETMC» (raw)

| منبع | کجا خوانده می‌شود | فیلدهایِ مصرفی |
|---|---|---|
| `ClosingPrice/GetMarketWatch` (تابلو) | `test_tsetmc.py:36` (MW_URL)، `_mw_row` `test_tsetmc.py:1295-1324`، `tick_live` `test_tsetmc.py:1451` | `pcl`=پایانی، `pdv`=? (خوانده ولی ذخیره نمی‌شود، خطِ 1309)، `py`=پایۀ دیروز، `pf`=اولین، `pmn/pmx`=کم/بیِ نشست، `pc`=تغییر، `qtj`=حجم، `qtc`=ارزش، `ztt`=تعداد؛ «آخرین» خام **نیست** — `p_last = py + chg` مشتق‌شده (خطوطِ 1313 و 1682) |
| `ClosingPrice/GetClosingPriceDailyListCSV/<ins>/<from>` | `test_tsetmc.fetch_price_history` `test_tsetmc.py:1165`؛ `api/chart.get_chart_tsetmc` `api/chart.py:377` | هدرِ رسمی (`api/chart.py:38-39`): 0=TICKER، 1=DTYYYYMMDD، 2=FIRST، 3=HIGH، 4=LOW، 5=CLOSE(پایانی)، 6=VALUE، 7=VOL، 8=OPENINT، 9=PER، 10=OPEN(قیمت پایه)، 11=LAST(آخرین) |
| `ClosingPrice/GetInstrmentsHistoryInDay/<dEven>` | `tools/backfill_daily_history.py:60` | `priceFirst، priceMax، priceMin، pClosing، qTotTran5J` — **pLast در این پاسخ خوانده نمی‌شود** |
| `ClosingPrice/GetClosingPriceDailyAllInst` ([ih]) | `test_tsetmc.refresh_tape_history` `test_tsetmc.py:459-659` | فقط `priceMin/priceMax/qTotTran5J` → جدولِ `tape_history`؛ بدنهٔ کندل ندارد |
| `Index/GetIndexB2History` | `api/market_index.py:31`، `fetch_tedpix_series` `:64` | `xNivInuClMresIbs/Ph/Pb` → close/high/lowِ شاخص |
| `MarketData/GetMarketOverview`، `ClientType/GetClientTypeAll`، `StaticData` | `test_tsetmc.py:171/1343/1333` | شاخص/تابلو/صنعت — بی‌کندل |

**باید اینجا ساخته شود:** FIRST/«پایانی»/«آخرین» هر سه از همان ردیفِ CSV باید واردِ زنجیر شوند —
`<FIRST>` برایِ open، `<CLOSE>` فقط برایِ لنگرِ تعدیل، `<LAST>` به‌عنوانِ closeِ نمایشی. تنها جایی
که `<LAST>` امروز خوانده می‌شود `_parse_tsetmc_csv` است (`api/chart.py:46,61`); هیچ fetcherِ
ذخیره‌کننده‌ای (مسیرهایِ ۱ و ۳) آن را نمی‌خواند. تابلو (`GetMarketWatch`) «آخرینِ» خام ندارد و
`p_last` را مشتق می‌سازد (`test_tsetmc.py:1313`) — برایِ parity باید یا از endpointِ زندهٔ
`LastPrice` گرفته شود یا صریحاً «تقریبِ py+pc» برچسب بخورد.

---

## ۲) مرحلۀ «ذخیره‌سازی» (storage)

اسکیمایِ `price_history` — `test_tsetmc.py:926-928` و تأییدِ read-only رویِ بانکِ نصبیِ
`market.db` (PRAGMA table_info، ۱۴۰۵-۰۷-۱۰): ستون‌ها **فقط**
`symbol, date, open, high, low, close, volume` — یعنی:
- **ستونِ `last` وجود ندارد** (همان که قراردادِ §۱-پ گفت؛ اینجا تأییدِ schema شد).
- **ستونِ `value` (گردشِ ریالی) وجود ندارد**؛ VALUE فقط در `daily_prices.q_tot_cap` می‌نشیند
  (`_DP_INSERT` `test_tsetmc.py:90-94`). درِ CSV هم `_parse_tsetmc_csv` ستونِ ۶ (VALUE) را
  نادیده می‌گیرد (`api/chart.py:59` فقط p[7]=VOL).
- `close` درِ این جدول **همیشه «قیمت پایانی» است** (هر پنج مسیرِ نوشتن پایین).
- ایندکسِ خوانندگان: `ix_ph_sym_date2` (`api/_core.py:105`).

جداولِ هم‌خانواد: `market_watch` (پایانی+آخرینِ مشتق+اولین، `test_tsetmc.py:900-907`)،
`daily_prices` (۲۴ نشستِ آخر، `test_tsetmc.py:908-917`)، `tape_history` ([ih] شصت‌نشسته،
`test_tsetmc.py:476-482`)، `boards/instruments/client_type/order_book/mstat_snap`.

**باید اینجا ساخته شود:** مهاجرتِ `price_history` به `(…, last REAL, value REAL)` یا
جایگزینی‌اش با یکِ جدولِ کندلِ واحد که **هر دو** `closing` (لنگرِ تعدیل) و `last` (نمایش) را
نگه می‌دارد. تا این ستون نیست، هیچ‌یک از مسیرهایِ local-db/تاریخچه‌محلی نمی‌توانند سریِ LAST
بدهند و قراردادِ مالک فقط رویِ مسیرِ CDN-executable است.

## ۲-الف) شمارشِ کاملِ نویسندگانِ `price_history` ( INSERT/REPLACE )

| # | مسیر | file:line | نگاشتِ امروز (فیلدِ CSV/تابلو → ستون) | last؟ |
|---|---|---|---|---|
| ۱ | `test_tsetmc.fetch_price_history` (CSV دلتا، هر نماد) | تابع `test_tsetmc.py:1138`؛ نوشتن `:1188`؛ **open از `fields[10]`** `:1181`؛ هرسِ ۷۳۰روزه `:1197-1200` | open=**OPEN(قیمت‌پایه!)** high=HIGH low=LOW close=**CLOSE(پایانی)** vol=VOL | ندارد |
| ۲ | `test_tsetmc.sync_price_history_from_daily` + `candle_from_row` (کندل از خودِ تابلو) | `test_tsetmc.py:1002-1027` (تبدیل)، `:1030-1100` (کوئری/نوشتن `:1090`)؛ فراخوان: انتهایِ `main()` `:1777-1780` و تردِ بوتِ `app.py:306-323` | open=`price_first`(اولین) high=`price_max` low=`price_min` close=`p_closing`(پایانی) vol=`q_tot_tran`؛ هندسه: `h=max(h,o,c)` `:1025` | ندارد |
| ۳ | `tools/backfill_daily_history.py` (GetInstrmentsHistoryInDay، دستی/۶۰نشست) | کوئری `:107-119`، نوشتن `:121` | open=`priceFirst` high/low=max/min close=`pClosing` vol=`qTotTran5J` | ندارد |
| ۴ | بازنویسِ هندسه (تولیدِ کندل نیست ولی ستون‌ها را عوض می‌کند): `normalize_price_history_geometry` | `test_tsetmc.py:1103-1135`؛ فراخوان `main():1781-1784` و `app.py:314` | فقط `high/low` را گِشاد می‌کند؛ closeِ پایانی دست‌نخورده (`:1111` comment) | — |
| ۵ | بانکِ baselineِ بسته‌شده درِ نصب‌کن (`market.db.lzma`) | `scripts/make_release_3.py:58` (price_history در فهرستِ جدول‌هایِ pack) | هرچه درِ baseline بوده (نتیجۀ ۱-۴ درِ زمانِ pack) | ندارد |

فراخوان‌دهنده‌هایِ مسیرِ ۱ (چهارTrigger): `update_existing` Phase B (`test_tsetmc.py:1267`)،
کدالِ on-demand (`codal_fetcher.py:3261-3262`)، ترمیمِ تاریخچهٔ چارت (`api/chart.py:242-249`
`_schedule_history_repair`→`fetch_price_history`)، و دستیِ CLI. مسیرِ ۳ هم دستی است.

نکتهٔ «چه کسی برنده می‌شود» (همان که قراردادِ §۰ گفت): درِ ردیف‌هایِ تازه، مسیرِ ۲ هر ۹۰ ثانیه
(حلقۀ `app.py:232-246` → `main():1778`) و درِ بوت مسیرِ app.py:313 ردیفِ همان نشست را با
open=FIRST بازنویسی می‌کند؛ مسیرِ ۱ اگر بعداً بدود (repair/on-demand/CLI) همان ردیف را با
open=پایه خراب می‌کند و سپس مسیرِ ۴ بی‌صدا جبران می‌کند — **هیچ تستی مالکیتِ ترتیب را نگه
نمی‌دارد** و قرارداد صریح نیست.

## ۲-ب) شمارشِ کاملِ خوانندگانِ `price_history`

| خواننده | file:line | فیلدها | مبنایِ فعلی |
|---|---|---|---|
| `/api/chart-db/{symbol}` `get_chart_db` | `api/chart.py:877`؛ SELECT `:890-892`؛ **`last := close` جعلی `:907`** | OHLCV | خامِ پایانی، بی‌تعدیل (`adjustSource:"local-db"` `:936`) |
| `/api/history/{symbol}` `get_history` | `api/screener.py:93`؛ SELECT `:101-104` | OHLCV | خامِ پایانی، بی‌adjustEvents |
| `/api/ma/{symbol}` `get_ma_events` | `api/chart.py:823`؛ SELECT `:836-839`؛ پنجره‌ها `MA_WINDOWS=[5,20,50,120]` `bors_config.py:641` | date,close,volume | خامِ پایانی (مصرفِ زنده فقط events — `frontend/.../useCalendarEvents.ts:6`) |
| `/api/chart/{symbol}/key-levels` | `api/chart.py:544`؛ SELECT `:555-558` | OHLCV | خامِ پایانی **بی‌تعدیل** |
| `/api/patterns/{symbol}` | `api/chart.py:944`؛ SELECT `:559-561`→`:959-962`؛ اعمالِ ضرایب `:976-982` | OHLCV × adjustEventsِ CDN | **مخلوط**: بدنه از DB، رویداد از CDN |
| پنجرۀ تابلو `board_hist_v` | `api/market.py:244-305` (اتحادِ price_history و daily_prices، `:256,:270`)؛ بازسازی `:408-430`؛_signature_ `:363-405` | فقط high/low/volume | خام؛ نمایشِ «میانگین ماه/حجمِ دیروز/کم/بی ۳۰روزه» |
| `confidence_engine._bars` (ستونِ تکنیکالِ واچ‌لیست/اطمینان) | `confidence_engine.py:322-359` (SELECT `:351`)؛ مصرف‌کننده `watchlist_store.py:24` | date,close,high,low,volume | خامِ پایانی **بی‌تعدیل**؛ هفتگی ISO-دوشنبه `:367-372` |
| انتخابِ دلتا در `update_existing` | `test_tsetmc.py:1226-1236` | symbol,date | — |
| نرمال‌سازِ نوشتار | `scripts/migrate_symbol_norm.py:88` | symbol | — |
| نامِ گمراه‌کننده: `mstat_engine._liquidity_from_price_history` | `mstat_engine.py:1163` | **از daily_prices می‌خواند** (`:1181`)، نه price_history — سازندهٔ کندل نیست |

**باید اینجا ساخته شود:** (الف) ستونِ `last` (+`value`) درِ `price_history` با backfill از CSV؛
(ب) یکِ مسیرِ نوشتنِ واحد (fetcherِ مرجع) که همهٔ ستون‌ها را از همانِ یکِ ردیفِ CSV بیاورد و
LV-last را بنویسد؛ (ج) حذفِ جعلِ `last:=close` در `api/chart.py:907` و جانشین‌کردنش با
NULLِ صادقانه یا backfill.

---

## ۳) مرحلۀ «نرمال‌سازی» (normalization)

- **نرمال‌سازیِ نماد:** `fts_engine.norm_fa` (`fts_engine.py:44`)، `fts_engine.sym_in`/`api/_core.sym_pred`
  (`api/_core.py:284-295`) — تطبیقِ چند-نویشتاریِ ك/ي عربی↔فارسی رویِ `symbol IN (?,?)`؛
  قیدِ کلید: `price_history.symbol == instruments.l_val18` (`confidence_engine.py:24`؛
  `test_tsetmc.py:1317` درِ `_mw_row`). مهاجرتِ یک‌بار: `scripts/migrate_symbol_norm.py`.
- **نرمال‌سازیِ تاریخ:** `dEven(int) → 'YYYY-MM-DD'` سه پیادهٔ هم‌سان دارد که باید یکی بمانند:
  `_iso_from_deven` (`test_tsetmc.py:994`)، `_d_even_to_date` (`api/chart.py:137`)،
  `printf('%04d-%02d-%02d')` داخلِ SQL (`api/market.py:257,277-284`)؛ plus `_d_even_to_iso`
  درِ `api/market_index.py:52`.
- **نرمال‌سازیِ هندسۀ کندل:** گِشاد‌کردنِ سایه سه‌جا: `_parse_tsetmc_csv` (`api/chart.py:85`)،
  `candle_from_row` (`test_tsetmc.py:1025-1026`)، `normalize_price_history_geometry`
  (`test_tsetmc.py:1103`). clampِ `last` داخلِ [low,high]: `api/chart.py:92`. clampِ openِ
  پایه بیرونِ بازه: `api/chart.py:72` (v8.7 FIX-1b).
- **حذفِ تکراریِ دو-املا:** سه پیادهٔ جدا با سه قاعده: `ORDER BY date DESC, volume DESC` +
  seen-set درِ chart.py (`:896-900`, `:964-970`, `:842-846`)، pandas `drop_duplicates` درِ
  screener (`api/screener.py:113-116`)، seen-set درِ confidence (`confidence_engine.py:353-358`).

**باید اینجا ساخته شود:** نرمال‌سازیِ «قیمت» هم اینجا اضافه می‌شود: یکِ تابعِ مرجع که از یکِ
ردیفِ CSV/تابلو جفتِ `(closing, last)` را با همانِ هندسۀ یک‌بار‌تعریف‌شده بیرون می‌دهد؛ امروز
هندسه سه پیاده دارد و «مبنای قیمت» صفر.

---

## ۴) مرحلۀ «تولیدِ کندل» — مسیرهایِ زنده/رم/ساختگی (علاوه بر نویسندگانِ DBِ §۲-الف)

| # | سازندۀ کندل | file:line | close امروز | last امروز | open امروز |
|---|---|---|---|---|---|
| ۵ | `_parse_tsetmc_csv` — کندلِ RAMِ `/api/chart` (CDN، کامل‌ترین مسیر) | `api/chart.py:28-96`؛ fetch `:377` | **CLOSE (پایانی)** `:57` | **LAST** `:61` با fallback به close `:87` و clamp `:92` | FIRST `:56,72` (v8.7 FIX-1) |
| ۶ | `_watch_live_bar` — کندلِ نشستِ جاری از market_watch (تزریقی، ذخیره نمی‌شود) | `api/chart.py:145-201`؛ تزریق در `get_chart_db:916` و `_attach_live_bar:253-283` | `p_closing` `:199` | `p_last` (مشتقِ py+pc) `:201` | `price_first` `:195` |
| ۷ | `get_chart_db` — تاریخچهٔ محلی + تزریقِ زنده؛ `last:=close` (`:907`) | `api/chart.py:877-942` | close (پایانی) | جعلی=close | DB (FIRST یا پایه، §۲-الف) |
| ۸ | `build_tedpix_payload` — کندلِ «شاخص کل» از Index/GetIndexB2History؛ open=closeِ دیروز clamp‌شده؛ `open_basis` درِ payload صریح است | `api/market_index.py:91-165`؛ route `:189` | پایانیِ شاخص | =close `:158` | ساختگی (prev-close) |
| — | مسیرِ تزریقِ fallback: `_fallback_local` (`api/chart.py:297-331`) با `degraded:True` و `adjustSource:"local-db-fallback"` — همان ۷ را صدا می‌زند | `api/chart.py:286-444` | | | |

کندلِ «امروز» درِ UI امروز از **مسیرِ ۶** می‌آید، نه DB؛ مسیرِ ۲ هم همان نشست را درِ DB
می‌نویسد (`sync_price_history_from_daily` حالتِ latest)، یعنی **دو سازندهٔ هم‌زمان برایِ یکِ
نشست** با دو قاعدهٔ پنهان‌سازیِ بی‌معامله (۶: vol≤0 ⇒ رد `:192`؛ ۲: `q_tot_tran>0 AND
p_closing>0` `:1054`).

**باید اینجا ساخته شود:** همهٔ هشت سازنده باید جفتِ `(close_display=LAST,
closing_anchor=CLOSING)` بدهند؛ امروز فقط ۵ هر دو عدد را از منبعِ درست می‌گیرد ولی ۵ هم
close‌اش پایانی است. مسیرهایِ ۶/۷/۸ که منبعشان تابلو/DB/ایندکس است اصلاً LASTِ معتبر ندارند
(۶ «آخرینِ مشتق»، ۷ جعل، ۸ بی‌معنا برایِ شاخص) و باید یا از CSVِ پرکنندهٔ ۱ با ستونِ تازه
تغذیه شوند یا صادقاً NULL بدهند.

---

## ۵) مرحلۀ «تعدیل» (adjustment) — لنگر: ممنوعِ دست‌زدن

- **تشخیصِ رویداد:** `_adjust_events_from_rows` `api/chart.py:99-134` — از جفتِ
  `(base=<OPEN> قیمت‌پایه, close=<CLOSE>)` درِ همان CSV (همین دو، `all_rows` `:73-74`،
  فقط ردیف‌های «پایه و پایانیِ معتبر» `:109`). **درِ لنگر:** اگر ≥۲۰ جفت باشد و کسرِ
  `base(t)==close(t-1)` زیرِ `ANCHOR_MIN=0.9` برود ⇒ بی‌رویداد (`:120-122`)؛ آستانهٔ
  دوتایی `ADJ_TOL=0.001` + ≥۱ریال `:130`. این دقیقاً همان لنگری است که سنجشِ ۸۰۰نمادی گفت با
  LAST در ۹۲٪ می‌شکند — **CLOSE-محور می‌ماند و به Last هیچ ربطی نمی‌دهد.**
- **ساختِ فاکتور:** back-adjustment معکوسِ O(n+m) درِ `get_chart_tsetmc:405-418`
  (`factor(t)=∏ ratio برایِ رویدادهایِ date>t`، آخرین کندل factor=1).
- **اعمالِ سمتِ فرانت:** `applyAdjustmentToCandles` (`nahayatnegar/lib/adjustments.ts:70-108`)
  — ضربِ OHLC در factorِ تجمعی، تقسیمِ volume، گردِ صحیح؛ سه حالتِ `none|combined|performance`
  `:29`؛ حالتِ performance = شاخصِ بازدهیِ «نخستین کندل=۱۰۰» (`toPerformanceSeries:50-60`).
  نگاشتِ رویدادهایِ خام: `mapBackendAdjustEvents:117-131` (فیلترِ ratio∈(0.02,50)).
- **اعمالِ سمتِ سرور برایِ تحلیل:** `_fts_scaled` `api/chart.py:2136-2165` — آرایۀ
  candles×factors×volumes را به همان شکلِ فرانت می‌زند (گردِ floor(x+0.5) `:2150`)؛
  **⚠️ خطِ `:2163` مقدارِ `last` را رویِ `close*k` می‌گذارد** — یعنی LASTِ واقعیِ CSV پیش از
  ورود به موتورِ FTS دور ریخته می‌شود.
- **تعدیلِ گِِتره‌ای/پراکندگی:** سنجشِ قبلی `tools/nn_adjust_parity.py` (قرارداد §۲-۳: میانۀ
  نسبت≈۱٫۰۰، ردیف‌به‌ردیف ۹-۹۹٪ هم‌تا۱٪ — علت: closeِ متفاوت؛ باید بعد از B2 دوباره سنجیده شود).

**باید اینجا ساخته شود:** خودِ زنجیرِ تعدیل نباید اینجا ساخته شود — لنگرِ تعدیل باید CLOSING بماند (§۱-ت «ممنوع»). عددِ «تعدیل‌نمایِ رهاورد» (قیمتِ تعدیل‌شدهٔ نمایشی) فقط درِ نقطۀ اعمالِ ضریب ساخته می‌شود: `_fts_scaled` سمتِ سرور (`api/chart.py:2136`) و `applyAdjustmentToCandles` سمتِ فرانت (`adjustments.ts:70`) — هر دو باید `last×factor` را جدا از `closing×factor` خارج کنند. تنها تغییرِ لازم
درِ همین مرحله: `_fts_scaled` نباید `last` را بمُکَد — فاکتور رویِ LASTِ نمایشی هم اعمال
می‌شود (`last*k`) و زنجیرِ کشف از همان `base/close` خامِ CSV می‌آید؛ و `_parse_tsetmc_csv`
باید `all_rows` را بی‌تغییرِ واقعی حفظ کند (base=OPENِ تاپلی = پایانیِ تعدیل‌نشدهٔ دیروز).

---

## ۶) مرحلۀ «تجمیعِ تایم‌فریم» (روزانه→هفتگی/ماهانه)

سه قاعدۀ **شنبه‌محورِ ماهانهٔ میلادیِ** هم‌شکل، و دو قاعدۀ **دوشنبه‌محورِ** جداافتاده:

| سازنده | فایل:خط | کلیدِ هفته | کلیدِ ماه | closeِ تجمیعی |
|---|---|---|---|---|
| فرانت (کلیۀ هر دو چارت) | `nahayatnegar/lib/timeframe.ts:37-77`؛ bucketKey `:25-30`: هفته `floor((day-2)/7)` = **شنبه**؛ ماه `getUTCFullYear*12+getUTCMonth` = **میلادی** | شنبه | میلادی | آخرینِ سطل `:65` |
| سرور FTS (رأیِ هفتگی/ماهانه) | `api/chart.py:_fts_resample:1081-1121`؛ `:1107` `(weekday()+2)%7` = **شنبه**؛ `:1109` `'YYYY-MM'` = **میلادی**؛ کامنت `:1087-1093` صریحاً ردِ ISO-دوشنبه را توضیح می‌دهد | شنبه | میلادی | آخرین روزِ سطل، `time` هم آخرین روز `:1119` |
| آزمایشگاهِ موتور (engine-lab فقط) | `lib/resample.ts:10-19`؛ `:14` `dow=(getUTCDay+6)%7` = **دوشنبه**؛ ماه `:12` میلادی | دوشنبه | میلادی | آخرین | مصرفِ تولیدی ندارد (`engine-lab/EngineLabPage.tsx:10`) |
| دروازۀ هفتگیِ واچ‌لیست/اطمینان | `confidence_engine.py:_week_key:367-372` (`date.isocalendar()` = **ISO دوشنبه**)، `_weekly_closes:375-388` close=اولینِ نزولی=آخرینِ روزِ هفته | دوشنبه(ISO) | — | — |
| پشتیبانِ صریحِ قرارداد: «یافت نشد» | تجمیعِ **جلالی** (ماهانه بر سطلِ فروردین…) — جست‌وجو: `gregorianToJalaali|jalaliMonth|فروردین|ماهانه` درِ `frontend/src` و `api/` — **هیچ bucket‌کنندۀ جلالی وجود ندارد**؛ جلالی فقط برایِ نمایشِ محور (`jalaliDate.ts:epochToJalali:95`) و YTD (`timeframe.ts:98-100`) و برچسبِ مجمع (`assemblyEvent.ts:jalaliOf:56`) مصرف می‌شود | — | — | — |

یادداشتِ سازگاری: کندلِ تجمیعیِ هر دو صفحۀ شنبه‌محور، stamp را رویِ آخرین روزِ سطل می‌گذارد
(`timeframe.ts:36,64` و `_fts_resample:1119` — کامنتِ `:1092` می‌گوید «هم‌قرارداد rvAggregate
سمتِ فرانت»)؛ پس امروز W/M ما با W/M رهاورد فقط در «سطلِ ماه» (میلادی vs جلالی) و در «مبنای
close» (پایانی vs آخرین) فرق دارد، نه در محورِ هفته.

**باید اینجا ساخته شود:** سطلِ ماهِ آن‌ها **جلالی** است (سنجیده شد: گامِ ماهِ جلالی ۷۷۷/۷۹۶ = ۱ و
هیچ‌وقت ۰، درحالی‌که گامِ میلادی درِ ۲۸ جفت صفر شده — `_audit/ra_monthly_bucket.py`؛ قراردادِ
§۱-ج ب) و closeِ تجمیعیِ هر دو صفحۀ ما باید از `last`ِ آخرینِ روزِ سطل ساخته شود (قانونِ تجمیعِ
خودِ رهاورد: open=openِ روزِ اول، close=closeِ روزِ آخر، high=max، low=min — ۸۰۱/۸۰۱ و
۳٬۳۰۸/۳٬۳۰۸ در `_audit/ra_aggregation_rules.py`). دو نکتهٔ باز که درِ این inventory تصمیمِ مالک
می‌خواهند: (۱) حجمِ تجمیعیِ رهاورد **جمع نیست، حجمِ روزِ اولِ سطل است** (۷۶۸/۸۰۱ ماهانه،
۳٬۳۰۱/۳٬۳۰۸ هفتگی) — هم‌سازی با آن یعنی له‌کردنِ جمعِ حجمِ ما؛ رأیِ مالک درِ قراردادِ §۱-ج پ
ثبت می‌شود. (۲) سطلِ ماهِ فرانت و سرورِ ما میلادی است (§۶ بالا) ⇒ تغییرِ کلیدِ سطل به جلالی،
مهاجرتِ §۵-۶ است نه اصلاحِ یک‌سطری.

---

## 7) مرحلۀ «APIِ بک‌اند» — شمارندۀ endpointهایی که کندل/سریِ قیمت می‌دهند

| endpoint | file:line | منبع | close | last | adjustEvents |
|---|---|---|---|---|---|
| `GET /api/chart/{symbol}` | `api/chart.py:286` | CDN CSV (مسیرِ ۵) + تزریقِ ۶ + fallbackِ ۷ | پایانی | **LAST واقعی** (`:94`) | دارد (`:395`) |
| `GET /api/chart-db/{symbol}` | `api/chart.py:877` | DB (مسیرِ ۷) | پایانی | **جعل: =close `:907`** | `[]` (`:936`) + `fts` (`:924-928`) |
| `GET /api/history/{symbol}` | `api/screener.py:93` | DB | پایانی | ندارد (schema `:127`) | ندارد |
| `GET /api/fts/{symbol}` | `api/chart.py:2231`→`_fts_analyze_symbol:2196` | `_fts_analysis_series:2168`: CDN-adjusted یا local-db | تعدیل‌شدۀ پایانی | بلعیده‌شده `:2163` | مبنای تحلیل؛ `analysis_basis` `:2224` |
| `GET /api/ma/{symbol}` | `api/chart.py:823` | DBِ خام | پایانی | ندارد | ندارد؛ امروز فقط events مصرف می‌شود (بالا) |
| `GET /api/chart/{symbol}/key-levels` | `api/chart.py:544` | DBِ خام **بی‌تعدیل** | — | — | سطوح رویِ خام (`:556`) |
| `GET /api/patterns/{symbol}` | `api/chart.py:944` | DB × رویدادهایِ CDN (`:976-982`) | — | — | سطوح رویِ تعدیل‌شده |
| `GET /api/market` | `api/market.py:110/461` | تابلو + پنجره‌های `board_hist_v/fv` | p_closing/p_lastِ board | p_lastِ مشتق | — |
| `GET /api/screener` (tech_*ها) | `api/screener.py:406-448`؛ importِ موتور `:10` | همان FTS سرور | — | — | رأیِ سبد |
| `GET /api/index/tedpix` | `api/market_index.py:189` | مسیرِ ۸ | شاخص | =close | — |
| `GET /api/order-book/{symbol}` | `api/chart.py:580` | order_book | بی‌کندل | — | — |
| `POST /api/sync/market` | `api/_sync_market.py:55` | راه‌اندازِ `test_tsetmc.main()` (مسیرهایِ ۲/۴) | — | — | — |

**باید اینجا ساخته شود:** هر سری‌دهنده باید دو مبنایِ نام‌دار بدهد و نه یکیِ مبهم:
`candles[].close` := LAST (نمایش) و `candles[].closing` := پایانی (لنگر)، با `value` (VALUE) و
`last` واقعی درِ مسیرهایِ DB. امروز فقط `/api/chart` «آخرین» دارد، آن هم در فیلدی که فرانت
دور می‌ریزد (§۸)، و `/api/chart-db` دروغِ `last=close` می‌فروشد.

---

## ۸) مرحلۀ «لایۀ دادهٔ فرانت»

- **`useCandleFeed`** (`api/useCandleFeed.ts`): `ChartSchema/RawCandle:12-38` **فیلدِ `last` را
  ندارد** — یعنی LASTِ `/api/chart` همین‌جا دور می‌ریزد. زنجیرۀ منبع: `/api/chart` →
  `/api/history` (`:79-108`). `toKLineData:60-73` stamp را `Date.parse(time+'T00:00:00Z')`
  می‌گذارد (نیمه‌شبِ UTC، نه ظهر).
- **`useNnData`** (`nahayatnegar/lib/useNnData.ts`): همان schema بی‌`last` `:12-18`؛
  `toKLine:41-50`؛ منبعِ `/api/index/tedpix` `:72-87`.
- **`KLineChartWrapper.fetchCandleData`** (`nahayatnegar/components/KLineChartWrapper.tsx:498-630`):
  لایۀ ۱ `/api/chart` (`:504`)، لایۀ ۲ `/api/history` (`:527`)، لایۀ ۳ `/api/chart-db`
  (`:546-548`؛ برایِ شاخص کل هاردکد `/api/chart-db/فولاد` `:547`)؛ نگاشتِ خامِ تدافعی
  `:582-604` — **`c.last` هرگز خوانده نمی‌شود (`:586-595` فقط o/h/l/c/v/turnover)**؛ `turnover`
  هرگز از سرور نمی‌آید ⇒ همیشه undefined (§۲؛ جست‌وجو: `grep turnover api/*.py` — تنها
  مصرف‌کننده‌ها درِ TS‌اند). برچسبِ منبعِ جایگزین `:614-619`.
- **`TechnicalPage`** (`routes/TechnicalPage.tsx`): یکِ سریِ دومِ موازی می‌سازد —
  `applyAdjustmentToCandles(..., 'combined')` `:97-101` → `aggregateCandles` `:112-123` →
  `engineBars` برایِ موتورِ دوم (FFC) → `series` برایِ `technicalSignal` `:137-154` →
  `activeLevels` (ma100 رویِ تعدیل‌شده `:182-197`). یعنی درِ یکِ صفحه **دو مبنایِ نمایش**:
  کلاین‌چارت با `activeAdjustment` (پیش‌فرض `performance` — پایین) و FFC همیشه `combined`.

**باید اینجا ساخته شود:** سه schema (useCandleFeed/useNnData/loader تدافعی) باید `last` (و
آینده `closing`) را نگه دارند و لایۀ نمایش closeِ نمایشی را از `last` بسازد؛ و «یک سریِ مرجع» —
همین حالا `TechnicalPage.candles` (combined) و `KLineChartWrapper.adjustedCandles` (پیش‌فرض
performance) دو سریِ جدا‌اند که سیگنال و رندر از دو سریِ جدا تغذیه می‌شوند.

---

## ۹) مرحلۀ «موتورهایِ چارت» (دو موتور + آزمایشگاه)

| موتور | فایل | داده از کجا | تاریخِ محور | ملاحظاتِ parity |
|---|---|---|---|---|
| **KLineCharts v10** (پیش‌فرضِ تولید، `ftsConfigStore.ts:181 chartEngine:'klinecharts'`) | `nahayatnegar/components/KLineChartWrapper.tsx`؛ `setDataLoader:886`؛ `setPeriod:899`؛ تزریق `renderCandles` (`:459-463`) | `displayCandles` = aggregate(adjust(raw)) `:450` | جلالی (`epochToJalali` درِ formatter `:229`+`jalaliDate.ts`)؛ `axisScaleLock` | **حالتِ پیش‌فرضِ تعدیل = `performance`** (`:328` `useState<AdjustmentMode>('performance')`) — یعنی امروزِ نمایشِ ما شاخصِ «نخستین کندل=۱۰۰» است، نه ریال؛ رهاورد ریالِ تعدیل‌شده می‌دهد. VOL/MA/RSI/MACD/BOLLِ داخلی رویِ همین سریِ رندرشده می‌دونند (`:2082-2089`) |
| **FFC (FastFinancialCharts)** — موتورِ دوم | `engine/ffc/FastFinancialChartsEngine.ts:1-40` (اعلانی، WebGL2)؛ `setBars:251`؛ `jalaliAxis:false` `:119` | `engineBars` از `TechnicalPage:112-123` (combined، تجمیع‌شده) | **میلادی**؛ بنرِ هشدارِ خودش `FtsEngineChart.tsx:158` | `chartType:'heikinAshi'` را خودِ بسته حساب می‌کند (`:44-45`) ⇒ اندیکاتورهایِ FFC رویِ HA تبدیل‌شده می‌دونند؛ `ts/1000` `:34` |
| آداپتورِ KLineCharts (نقۀ مشترکِ engine-lab و FtsEngineChart) | `engine/klinecharts/KLineChartsEngine.ts`؛ `setBars:301-310` (`turnover: b.turnover ?? null` `:309`) | همان engineBars | `jalaliAxis:true` `:209` | نوعِ `EngineBar` فیلدِ `last` ندارد (`engine/types.ts:19`) |
| آزمایشگاه | `engine-lab/EngineLabPage.tsx:10` (`resample` دوشنبه‌محور) | دادهٔ lab | — | خارجِ مسیرِ تولید |

اورلی‌ها/مارکرها: `KLineChartWrapper:1313-1400` — زون‌ها/سطوحِ فیبو و مارکرهایِ ستاپ از
payloadِ **سرور** می‌آیند و با نسبتِ `toDisp = dLast/aLast` به فضایِ نمایش نگاشت می‌شوند
(`:1326-1334`)؛ اگر سریِ نمایش (performance/combined/Heikin) با سریِ تحلیل (سرور combinedِ
پایانی) یکی نباشد، **کلِ مارکرها بی‌صدا جابه‌جا می‌شوند** — «rendering transformation»ِ قرارداد.

**باید اینجا ساخته شود:** موتورِ مرجع باید سریِ «ریالِ تعدیل‌شده با close=LAST» بگیرد؛ حالتِ
`performance` اگر بماند فقط می‌تواند «نمایِ دوم» باشد نه پیش‌فرض؛ و `EngineBar` باید `last`
بگیرد تا دو موتور یکِ عدد نشان دهند.

---

## ۱۰) مرحلۀ «اندیکاتور / الگو / سیگنال» — نقشۀ مبنایِ قیمت

میانگین‌ها و نوسان‌نماها:

| اندیکاتور | کجا حساب می‌شود | سریِ ورودی | مبنایِ امروز | ذیلِ قرارداد باید |
|---|---|---|---|---|
| MA/EMA/RSI/MACD/BOLL (پنل‌هایِ چارت) | کتابخانۀ klinecharts، ساختِ `chart.createIndicator` `KLineChartWrapper:2082-2089` + registerIndicatorsِ TV/mabna `:815-876` | `renderCandles` (adjust→aggregate→heikin) | تعدیل‌شدهٔ پایانی؛ پیش‌فرضِ نرمال‌شده به ۱۰۰؛ با Heikin-Ashi رویِ HA | همان سریِ نمایشیِ جدید (LAST×factor؛ بدونِ نرمال‌سازیِ پیش‌فرض) |
| MA14 تریلینگ + MA52 ساعت‌شنی + MA100 مرجع | سرور: `_fts_ma:1289` درِ `_fts_exit_layer1:1734-1746` (MA14 رویِ closesِ تعدیل‌شده)؛ `_fts_analyze_candles:2061-2098` (MA52/RSI5 هفتگی از `closes_w`)؛ فرانت: `indicators.ts:ftsMAs:85 (14/21/52/100)`، `ma14TrailingExit:115`؛ `TechnicalPage:184-188` MA100 | سریِ تعدیل‌شده (سرور `_fts_scaled` / فرانت combined) | تعدیل‌شدهٔ پایانی؛ **سنگین‌ترین مصرف‌کنندهٔ لنگر**: سنجشِ B2 عددِ MAها را <۰٫۵٪ جابه‌جا می‌کند (`matrix MA14/MA52: 739/715` در report) | LAST-based adjusted |
| RSI وایلدر (لایۀ ۴ خروج + اشباع) | سرور: `_fts_rsi:1301` (رویِ `closes` تعدیل‌شده)؛ `confidence_engine._rsi:391` (رویِ **خامِ DB**!)؛ فرانت `indicators.ts:372` | سه پیاده | **مخلوط**: سرور تعدیل‌شده / confidence خام | یکی؛ تعدیل‌شدهٔ LAST |
| Bollinger / MACD | فقط کتابخانۀ چارت (جدول بالا) | سریِ نمایش | تعدیل‌شدهٔ نمایشی | LAST-based |
| فیبوناچی | سرور: `_fts_fib_leg:1321-1390` (موجِ اخیر رویِ high/low/closeِ تعدیل‌شده)، `_fts_fib_zones:1417-1458` (مقیاس لگاریتمی، کمربندهای ۳۳-۴۰/۶۱.۸-۷۰، `in_zone` با `candles[-1].close` `:1446`)؛ رسم: `KLineChartWrapper:1343-1380` با `toDisp`؛ ابزارِ کاربریِ fib: `:1930-1965` | سریِ تعدیل‌شده | **سیستمِ رأیِ فیبو درِ B2 صفر جابه‌جا شد (report `3_engine_flips_B2`)** — چون با close نمایشیِ جدید هم موج و هم in_zone عوض می‌شود، موتورِ واقعی درِ سنجش همان B2 را اجرا کرد؛ درِ کد هنوز پایانی | LAST-based + لنگرِ تعدیل CLOSE |
| تشخیصِ روند | سرور: `_fts_swings:1123` (fractal k=3) + `_fts_classify_trend:1189-1253` (HH/HL رویِ high/low) + `_fts_recent_window_trend:1149` (شیبِ رگرسیونِ closes + MA52)؛ بازنمونهٔ W/M: `_fts_resample`؛ فرانتِ mappingِ رأی: `weeklyFromFts.ts` (فقط خواندنِ payload)؛ confidence: `conf_tech:521-627` (MA خام) | تعدیل‌شده (سرور) / خام (confidence) | **دو روندِ موازی**: رأیِ چارت/اسکرینر از سریِ تعدیل‌شدهٔ CDN، ستونِ تکنیکالِ واچ‌لیست از سریِ خامِ DB | همه از یکِ سریِ مرجع |
| حمایت/مقاومت | `_swing_extremes:446` + `_merge_levels:469` (از high/low)؛ `/key-levels:544` رویِ **خامِ DB**؛ `/patterns:944` رویِ **تعدیل‌شده** (`:976-982`)؛ `indicators.ts: majorSupport/majorResistance` (فرانت، سریِ combined) | سه مصرف، سه مبنایِ متفاوت | **پرچمِ «مخلوط»**: دو عددِ سطوحِ متفاوت برایِ یکِ نماد از دو endpoint می‌آید | یکی: LAST-adjusted |
| الگوها (سقف‌سوم/دوتاپ/H&S/کف‌دوقلو/باکس‌رنج/CHoCH/شکارنقطه/جت) | سرور: `_fts_exit_layer3:1780-1844`، `_fts_double_bottom:1576-1608`، `_fts_choch:1497-1529`، `_fts_point_hunt:1532-1573`، `_fts_jet_setup:1461-1494` (همه رویِ close/high/lowِ سریِ تحلیل)، مارکرهایِ تاریخچۀ `_fts_setup_history:1614-1692`؛ رسمِ اورلیِ الگو: `KLineChartWrapper` group `fts_pattern_overlays` `:166-167` + `lib/patternOverlays*`/`engineFtsLayers.ts` (مصرفِ payload) | تعدیل‌شدهٔ پایانی | همه درِ B2 تقریباً پایدار ماندند (report: چوچ ۱/دبل‌باتم ۱/ساعت‌شنی ۰ نماد) | LAST-based |
| سیگنال/داوری | فرانتِ `technicalSignals.ts` (رویِ `series`ِ combinedِ `TechnicalPage:137-154`؛ Jet/Choch/fib/gates) → `signalBus` → تبِ مستر؛ سرورِ matrix/hourglass: `_fts_analyze_candles:1998-2098`؛ رأیِ نهاییِ غربگر: `api/screener.py:406-466`؛ وتوی مجمع: `_apply_assembly_veto:151-179` (تقویمی، بی‌قیمت) | combined/سریِ تحلیل | درِ B2 `matrix.decision` صفر تغییر؛ درِ B1 ۸۴ نماد — این عددِ بیدارکننده | B2 همان است؛ فقط ورودیِ نمایش |
| هشدارِ قیمتی | `priceAlerts.ts:19` — `p_last` با fallback به `p_closing` از ردیفِ تابلو (نه کندل) | board | **تنها مصرفِ LAST-محورِ زنجیر**؛ اما `p_last`ِ خودِ board مشتقِ py+pc است (§۱) | LASTِ واقعی از همان منبعِ کندل |

پرچم‌هایِ «مخلوط‌کردنِ دو مبنی» (خلاصه):
1. `api/chart.py:907` — `last := close` درِ `/api/chart-db`: مصرف‌کننده اگر روزی last بخواند، پایانی می‌گیرد.
2. `api/chart.py:2163` — `_fts_scaled` last را می‌مُکَد؛ تحلیلِ «سریِ مرجعِ تعدیل‌شده» عملاً بی‌LAST است.
3. `api/chart.py:976-982` — `/patterns` بدنه را از DB (محلی/خام) می‌گیرد و ضریب را از رویدادهایِ CDN؛ اگر DBِ محلی با مسیرِ ۲ (تابلو) پر شده باشد و CSV با مسیرِ ۱ (پایانیِ قدیمی) رویداد بسازد، تاریخ/عدد تراز نمی‌شوند.
4. `key-levels` (خام) در برابرِ `patterns` (تعدیل‌شده) — دو سطحِ متفاوت برایِ یکِ نماد.
5. `confidence_engine` (خام + ISO-week) در برابرِ موتورِ FTS (تعدیل‌شده + Saturday) — ستونِ تکنیکالِ واچ‌لیست با رأیِ چارت نمی‌خواند.
6. `TechnicalPage` combined در برابرِ `KLineChartWrapper` performance — دو موتورِ چارت دو سریِ جدا می‌بینند.
7. `/api/ma` MAها را رویِ خامِ DB می‌سازد (`:836-857`) و فرانت امروز فقط `events` را مصرف می‌کند؛ اگر روزی سریِ ma مصرف شود، مبنایش با چارت فرق دارد.

**باید اینجا ساخته شود:** یکِ «سریِ مرجع» (reference series) درِ بک‌اند — `tsetmc-adjusted-last`
که تنها ورودیِ همهٔ موتورهایِ بالا باشد — و حذفِ همهٔ مسیرهایِ خام/جایگزین‌ساخته. هیچ اندیکاتوری حقِ
ساختنِ سریِ خودش را ندارد.

---

## ۱۱) نقاطِ تبدیلِ تاریخ/منطقۀ زمانی (کاندیداهایِ «session boundary / timezone-date conversion»)

1. مهرِ نشستِ کندلِ زنده: `_watch_live_bar` تاریخ را از `d_even` می‌خواند نه `today()`
   (`api/chart.py:146-156,180-182`) — گاردِ `dev/live_bar_session_date_v1059.py` (چک `:261`)
   جلویِ هر «امروزِ سیستم» درِ chart.py را می‌گیرد. سندِ شاهدِ خودِ قرارداد: فولاد بامداد
   ۱۴۰۵-۷-۸ کندلِ شبح گرفت.
2. `datetime.date.today()` (ساعتِ سیستم، بدونِ TZ) درِ: cutoffِ fetch `test_tsetmc.py:1158`،
   hرسِ `:1198`، `main():1542-1553` (دربِ بازار با `%H%M` محلی)، `tick_live:1472-1475`
   (۰۸:۵۵–۲۰:۰۰)، `_upcoming_by:731`، `refresh_tape_history:553`. ماشینِ خارجِ Asia/Tehran این
   درب‌ها را جابه‌جا می‌کند — **هیچ تبدیلِ TZ صریحی درِ بک‌اند نیست (یافت نشد؛ جست‌وجو:
   `ZoneInfo|Asia/Tehran|pytz` درِ ریشه)**.
3. فرانت: `parseCandleTimestamp` (`jalaliDate.ts:108-145`) — رشته/عددِ ۸رقمی با سالِ ۱۳۰۰-۱۵۰۰
   را **جلالی** تفسیر می‌کند و `Date.UTC` می‌دهد؛ `toKLineData` و `toKLine` اما
   `Date.parse(time+'T00:00:00Z')` (نیمه‌شب) می‌سازند (`useCandleFeed.ts:67`،
   `useNnData.ts:44`)، درحالی‌که سرور برایِ اورلی‌ها/تقویم **ظهر UTC** می‌فرستد
   (`api/chart.py:684` `_cal_events_for` و `:988` `ts_of=+43200`) — سه stampِ متفاوت
   (۰۰، ۱۲ UTC، جلالی-تفسیرشده) رویِ یکِ روز. تجمیعِ هفتگی چون با epoch-day کار می‌کند
   (`timeframe.ts:26`) نسبتاً stamp-مقاوم است، ولی `rangeVisibleBars` (YTD) با جلالیِ خودِ
   آخرین کندل می‌شمارد (`:96-100`).
4. محور/نمایش: `epochToJalali` فقط getUTC() می‌خواند (`jalaliDate.ts:95-102`) — اگر stamp به
   ظهرِ UTC باشد همان روز؛ اگر محلیِ منفی‌ساعت باشد یک روز عقب می‌افتد (منبعِ همان اشتباهِ
   «۱۳۹۹-۰۵-۰۱ vs ۱۳۹۹-۰۴-۳۱» درِ یادداشتِ صحتِ دادهٔ §۰ِ قرارداد).
5. `board_hist_v` امروزِ تقویمی را `printf` از d_even می‌سازد و «امروز» را از پنجره بیرون
   می‌گذارد (`api/market.py:244-305,359-360`) — قیدِ «نشستِ باز خوانده نشود».
6. درِ نوشتنِ تیک/سینک (۱۲:۳۰/۱۵:۳۰، پنجشنبه-جمعه): `test_tsetmc.py:1400-1404,1472-1477,1551-1553`
   — ساعتِ محلیِ سیستم.

**باید اینجا ساخته شود:** تبدیلِ «میلادی↔جلالیِ واحدِ پروژه» که همۀ تست‌هایِ parity از همان
بگذرند (قرارداد §۰ یادداشتِ آخر: صریحاً باید از تستِ §۲-۵ بیاید) — یعنی یکِ `TehranDate`
مرکزی (stamp=ظهر UTC یا epoch-day + jalaliDate) که بک‌اند و فرانت هر دو مصرف کنند؛ امروز دو
`toJalaali` مستقل هستند (`jalaliDate.ts` و `Intl fa-IR-u-ca-persian` درِ
`assemblyEvent.ts:44`).

---

## ۱۲) گاردهایِ موجود (شبکهٔ تستیِ فعلی — برایِ اینکه بدانیم چه چیزی نمی‌شکند)

- `dev/candle_source_fidelity_v1033.py` — پاریتیِ `_parse_tsetmc_csv` و چکِ «route از همین helper
  رد می‌شود» (`:170`).
- `dev/candles_from_board_v1062.py` — گاردِ مسیرِ ۲ (کندل از تابلو).
- `dev/live_bar_session_date_v1059.py:261` — گاردِ مسیرِ ۶ (تزریقِ زنده) و ممنوعیتِ `today()`.
- `dev/board_hist_cache_v1056.py` — گاردِ پنجره‌هایِ `board_hist_v/fv` (سطر‌به‌سطر تک‌پیسّه).
- `dev/market_db_union_v1069.py` — گاردِ اتحادِ DB (INSERTهایِ `:87/:120` فقط فیکسچرِ temp‌اند،
  نه مسیرِ تولید).
- `dev/incremental_sync_resilience.py:81-83` — فیکسچرهایِ سناریوی سینک (نویسندۀ تولیدی نیست).
- `dev/weekly_veto_guard.py`، `frontend/__tests__/technical-weekly-wiring.spec.ts`،
  `technical-timeframe.spec.ts`، `technical-nn-adjust.spec.ts`، `technical-jalali.spec.ts`،
  `percent-change-sentinel.spec.tsx`.
- **نداشتنی‌ها (صریح):** هیچ گاردی مالکیتِ ترتیبِ نویسندگانِ `price_history` را نمی‌گیرد؛ هیچ
  گاردی نبودِ `last` را؛ هیچ تستی parity بیرونی با رهاورد/نهایات‌نگار ندارد (§۲-۵ قرارداد هنوز
  نوشته نشده — خارجِ دامنۀ این inventory).

---

## ۱۳) جمع‌بندی — «باید کجا ساخته شود» یک‌جا

1. **Schema (§۲):** ستون‌هایِ `closing`(لنگر)/`last`(نمایش)/`value` درِ جدولِ کندلِ واحد.
2. **Fetcherِ مرجع (§۱/§۴ مسیرِ ۱):** هر سه ستون از همان ردیفِ CSV؛ open=FIRST (اصلاحِ
   `test_tsetmc.py:1181` که امروز پایه می‌نویسد)؛ لغوِ هرسِ بی‌قاعدهٔ ۷۳۰روزه یا جایگزینی‌اش
   با پنجرۀ صریح.
3. **کشفِ تعدیل (§۵):** دست‌نخورده — فقط `_fts_scaled:2163` دیگر نباید last را ببلعد و
   فاکتور باید رویِ LASTِ نمایشی هم اعمال شود (بدون تغییرِ زنجیر).
4. **APIها (§۷):** همهٔ سری‌دهنده‌ها دو-مبنایی؛ حذفِ `last:=close` (`chart.py:907`)؛
   یکسان‌کردنِ key-levels/patterns/ma با سریِ مرجع.
5. **تجمیع (§۶):** closeِ تجمیعی := LAST؛ سطلِ ماه := جلالی (پس از سنجشِ APIِ رهاورد)؛
   حذفِ قاعدۀ ISO-دوشنبه از confidence یا هم‌سان‌سازی‌اش با شنبه.
6. **لایۀ نمایش (§۸-۹):** سه schema باید `last` را پاس‌دارند؛ یکِ سریِ مرجع برایِ هر دو موتور؛
   حذفِ `performance` از پیش‌فرض (`KLineChartWrapper:328`) اگر رهاورد ریال است.
7. **اندیکاتورها (§۱۰):** هیچ‌کس سریِ خودش را نمی‌سازد؛ همه از سریِ مرجعِ `price_basis()`
   (قراردادِ §۱-ث — «B2» دیگر نامِ حالتِ محصول نیست، فقط برچسبِ سنجشِ §۱-پ است).
8. **تاریخ/TZ (§۱۱):** یکِ تبدیلِ جلالیِ مرکزی؛ stampِ واحد؛ درب‌هایِ ساعتِ بازار رویِ
   Asia/Tehran نه ساعتِ سیستم.

## ۱۴) آنچه تعیین نشد (حدس نمی‌زنم)

- ~~کدامِ ستونِ FIRST/OPENِ CSV openِ کندلِ رهاورد است~~ — **سنجیده شد: FIRST**
  (۱۴٬۲۱۰/۱۴٬۷۰۶ = ۹۶٫۶٪، OPEN صفرِ مطلق؛ قراردادِ §۱-ج الف).
- ~~جلالی‌بودنِ سطلِ ماهانۀ رهاورد~~ — **سنجیده شد: جلالی** (قراردادِ §۱-ج ب؛
  `_audit/ra_monthly_bucket.py`). کدِ timeframe هم از markupِ خودشان خوانده شد:
  0=D ۱=W ۲=M، و باندلِ `technicalChart.1.1.2.min.js` همان را درِ `'/prices?timeframe='`
  می‌گذارد (`_audit/ra_ta_strings.txt` سطرهایِ ۴۴۱/۱۵۶۳).
- نگاشتِ VALUE/VOL درِ رهاورد/نهایات‌نگار — هیچ‌یک از دو مرجع هنوز استخراج نشده (قرارداد §۲-۲).
  آنچه سنجیده شد: قانونِ *تجمیعِ* حجمِ آن‌ها (جمع نیست؛ §۶) و اینکه ستون‌های ۷/۸ پاسخِ
  `/prices` درِ ۱٬۳۷۳/۱٬۳۷۳ روزِ مشترکِ پنج نماد یکسان‌اند ⇒ بازار-محور، نه گردشِ نماد.
- اینکه کدامِ نویسنده درِ بانکِ نصبیِ امروز «آخرین‌نویس» است (۱ در برابر ۲) — ترتیبِ runtime به
  ساعتِ بوت/سینک و repairها بستگی دارد؛ ادعایِ قطعیِ «همیشه ۲ برنده است» درِ هیچ شواهدِ
  اندازه‌گیری‌شده‌ای نیست؛ آنچه هست: دادهٔ موجود با FIRST می‌خورد (§۰ِ قرارداد، ۹۹٫۷٪).
- حلقۀ دادۀ خودِ مرجع (۱۴۰۴-۱۲-۰۶ تا ۲۰۲۶-۰۵/۰۶/۰۸ بسته به نماد) — «علتش» از داده‌هایِ ما
  قابلِ تشخیص نیست؛ فقط ثبت می‌شود که درِ پنجره‌هایِ خالی، مقایسه ممکن نیست
  (قراردادِ §۱-ج ت).
