# TSETMC Data-Layer Gap Matrix — BorsTerminal

> **هشدار وضعیت:** این ماتریس در ۲۰۲۶-۱۰-۰۵ نوشته شده و در همان snapshot تصریح می‌کند که production تغییر نکرده بود. اجرای P0ها و مصرف‌کنندگان پس از آن تاریخ در اسناد `TSETMC-P0-*` و کامیت‌های بعدی ثبت شده؛ این فایل نقشهٔ شکاف تاریخی است، نه فهرست قطعی باگ‌های امروز.


تاریخِ ممیزی: 1405-07-13 (2026-10-05). وضعیتِ کد: **بدونِ هیچ تغییرِ production** — این سند
تنها فایلِ ایجادشده است.

همۀ شمارها (شمارۀ خطِ کد، تعدادِ رکورد، آستانه‌ها) با رقمِ لاتین نوشته شده‌اند؛ دلیلش در
`docs/fts-notes/TECHNICAL-PDF-EVIDENCE-AUDIT-1405-07-13.md` آمده: رقمِ فارسیِ چندرقمی در
سندِ عدد-محور بی‌صدا ناقص ذخیره می‌شود.

**علامت‌هایِ ادعا** (طبقِ §22ِ brief — این سه با هم قاطی نمی‌شوند):

| علامت | معنا |
| --- | --- |
| LIVE-VERIFIED | درخواستِ واقعی زده شد و پاسخ دیدہ شد. این دور: ~55 درخواست، بازار بسته، 1.1s فاصله،UA/Referer/Origin |
| CODE-VERIFIED | کدِ خوانده‌شدہ (در این ریپو یا در ریپویِ مرجع) |
| README-ONLY | فقط از README/مستنداتِ مرجع فهمیده شد؛ کدش ندیده‌ام |

---

## 1. Executive Summary

**۱) مهم‌ترین gap واقعی چیست؟**
`ClientType/GetClientTypeHistory/{insCode}/{dEven}` روی CDN **ارزشِ ریالیِ حقیقی/حقوقی را
مستقیم می‌دهد** (`buy_I_Value`, `buy_N_Value`, `sell_I_Value`, `sell_N_Value`) — LIVE-VERIFIED.
BorsTerminal این چهار فیلد را نمی‌گیرد و ارزش را در `mstat_engine.py:761-765` با
`volume × vwap` بازسازی می‌کند (`vwap = val/vol or p_closing`، خطِ 747). این تنها جایی است که
یک **عددِ منتشرشدهٔ برنامه** از دادهٔ بازسازی‌شده می‌آید در حالی که دادهٔ مبدأ موجود است. ⇒ **P0**.

**۲) incremental MarketWatch داریم؟**
نه. هر دورِ ۵ ثانیه‌ای یک snapshotِ کاملِ `ClosingPrice/GetMarketWatch`
(`test_tsetmc.py:37`) گرفته می‌شود و اختلاف **سمتِ خودمان** حساب می‌شود. پروتکلِ delta واقعیِ
TSETMC زنده است: `MarketWatchInit.aspx?h=0&r=0` ⇒ 3847 سطرِ 26فیلده + cursor؛ سپس
`MarketWatchPlus.aspx?h=<heven//5*5>&r=<refID//25*25>` ⇒ **1942 سطرِ 10فیلده، فقط
تغییریافته‌ها** + cursorِ تازه. LIVE-VERIFIED. ⇒ **P1** (بهایش: ~۱۷ برابر ترافیکِ کمتر، نه رفعِ باگ).

**۳) داده‌ای که اصلاً نداریم و منبعش هست چیست؟**
شش خانواده: «علت توقف» (`webgw …/CompanyState/fa` با آرایۀ `dalils`)، پیامِ ناظر
(`Msg/GetMsgByInsCode` ⇒ 2783 پیام برایِ خودرو)، نظارت
(`Supervision/GetSupervisionListBySourceID`)، تغییرِ مالکیت (`Shareholder/{ins}/{date}` با
`change` و `changeAmount`)، رویدادِ تعدیل (`ClosingPrice/GetPriceAdjustByFlow` با `pClosing` در
برابرِ `pClosingNotAdjusted`)، و ISIN (`instrumentIdentity.cIsin` و حتی `insID` در **همان**
سطورِ `GetMarketWatch` که همین حالا می‌گیریم و دور می‌ریزیم).

**۴) چه چیزهایی که در پروژه‌هایِ خارجی هست به دردِ معماریِ ما نمی‌خورد؟**
Footprint/Delta/Imbalance/POC به معنایِ ORBO **تیک‌داده می‌خواهد**؛ تیک هست
(`Trade/GetTradeHistory` ⇒ 28943 رکورد برایِ خودرو در یک روز، 5.8MB) ولی هیچ بندِ FTSی به آن
اشاره ندارد و حجمِ ذخیره‌سازیاش برایِ اپِ دسکتاپِ onedir سنگین است. `Median Line`/`Pitchfork`/
`SAR` در هیچ‌یک از پنج پروژه نیست. `Instrument/GetInstrumentByFlow` (board مدرن با paging)
LIVE ⇒ **404**.

**۵) parityِ فعلی:** هفت فیلترِ tape در `docs/TA-PARITY-1405-07-04.md` §5–§6 و
`tools/tse_live_filter_parity.py` با درخواستِ هم‌زمانِ لحظه‌ای ثابت شده‌اند؛ **بازتولید نمی‌شود**.
تازگیِ مهم (§19): چند فیلدِ فیلترِ TSETMC (`insID`, `flow`, `pRedTran`, `buyOP`, `cGrValCot`) در
**همان پاسخِ `GetMarketWatch`** حاضرند ⇒ گپِ فیلد، گپِ «نخواندن» است نه گپِ «دریافت»، و هزینه‌اش
صفرِ درخواستِ شبکه.

جمعِ امتیاز: **24 gap** طبقه‌بندی شد ⇒ P0: 3، P1: 6، P2: 8، P3: 7. از این 24، فقط ۴ «نباید
اضافه شود» نیستند (بقیه IGNORE/DEFER).

---

## 2. BorsTerminal Current Data Inventory

### 2.1 مسیرهایی که واقعاً شبکه می‌زنند

برخلافِ فرضِ brief، دایرکتوری‌هایِ `backend/` و `src/` وجود ندارند. ساختارِ واقعی:
`test_tsetmc.py` (موتورِ واکشیِ TSETMC، 115KB، در `fts_terminal.spec:29,48` به‌عنوانِ
`hiddenimports` قفل شده)، `codal_fetcher.py` (کدال)، `api/*.py` (اندپوینت‌ها)، و
`mstat_engine.py` / `tape_flags.py` / `fts_engine.py` / `price_basis.py` / `candle_contract.py`
که **هیچ I/O شبکه‌ای ندارند** (با grepِ `requests\.|urlopen|s\.get(` در تک‌تکشان تأیید شد).

| # | اندپوینتِ واقعی | فایل:خط | داده |
| --- | --- | --- | --- |
| 1 | `cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&paperTypes[0..8]&showTraded=false&withBestLimits=true&hEven=0` | `test_tsetmc.py:37`؛ مصرف 1436 (snapshot)، 1591 (tick)، 1723 (sync) | تابلو + `blDs` |
| 2 | `…/ClientType/GetClientTypeAll` | `test_tsetmc.py:1444`, `1763` | حجم و تعدادِ حقیقی/حقوقی — **بدونِ ارزش** |
| 3 | `…/ClosingPrice/GetClosingPriceDailyListCSV/{symbol}/{from}` | `test_tsetmc.py:1226`، `api/chart.py:507` | OHLCV روزانۀ منتشرشده |
| 4 | `…/ClosingPrice/GetClosingPriceDailyAllInst` | `test_tsetmc.py:474` (`TAPE_HIST_URL`) | پنجرۀ `[ih]`: `priceMin/priceMax/qTotTran5J` روی ۶۰ نشست |
| 5 | `…/MarketData/GetMarketOverview/{0,1,2}` | `test_tsetmc.py:1453`, `1750`, `186-217` | شاخصِ کل/هم‌وزن، ارزشِ بازار، فعالیت |
| 6 | `…/StaticData/GetStaticData` | `test_tsetmc.py:1434`, `1714` | نامِ گروه‌هایِ صنعتی (`IndustrialGroup`) |
| 7 | `…/GetMarketWatch?market=1` و `market=2` | `test_tsetmc.py:1439-1440`, `1773-1774` | عضویتِ تابلوها (`boards`) |
| 8 | `…/GetMarketWatch?pt=N` (۴ درخواست) | `test_tsetmc.py:697-701` | `paper_type` |
| 9 | `…/Index/GetIndexB2History/{insCode}` (TEDPIX) | `api/market_index.py:33` | سریِ روزانۀ شاخص |
| 10 | `search.codal.ir/api/search/v2/q` + `codal.ir/Reports/Decision.aspx` | `codal_fetcher.py:33`, `1108`, `1377` | اطلاعیه/صورتهایِ مالی/فروشِ ماهانه |
| 11 | `github.com/johnwarchief/BorsTerminal` | `api/_sync_codal.py:103`, `api/update.py:65` | `codal.db.lzma`، `latest.json` |

`webgw.tse.ir`، `services.tsetmc.com`، `members.tsetmc.com`، `old.tsetmc.com`، `tsev2`،
`Loader.aspx`، `MarketWatchInit/Plus` ⇒ **صفر occurrence در کدِ production**. تنها اشاره‌ها در
`_audit/probe_*.py` و در مستنداتی است که آن‌ها را «مرده» گزارش کرده‌اند.

### 2.2 چیدمانِ بانک (market.db — 181MB، 27 جدول)

`market_watch` = `ins_code, d_even, h_even, p_closing, p_last, price_min, price_max,
allowed_min, allowed_max, price_yesterday, price_first, q_tot_tran, q_tot_cap, z_tot_tran,
price_change, eps, pe, total_shares, sector_code, fetched_at` + ۱۱ ستونِ صف (`buy_q_*`,
`sell_q_*`, `buy_q1_*`) + `market_cap, market_cap_src`. فهرستِ منبع: `MW_COLS`
(`test_tsetmc.py:97-101`). 5669 سطر.

`instruments` = `ins_code, l_val18, l_val30, sector_code, sector_name, total_shares, eps, pe,
base_vol, updated_at, paper_type` — **ISIN ندارد**.

`client_type` = `ins_code, d_even, buy_i_vol, buy_n_vol, buy_ddd_vol, buy_count_i, buy_count_n,
buy_count_ddd, sell_i_vol, sell_n_vol, sell_count_i, sell_count_n, fetched_at`
(DDL `test_tsetmc.py:936-941`) — **هیچ ستونِ ارزشی ندارد**. 77614 سطر، 33 روز، از 20260820؛
یعنی تاریخچۀ انباشتیِ خودِ ما، بدونِ backfill.

`order_book` = `ins_code PK, d_even, h_even, book_txt, updated_at` — **یک سطرِ جاری به ازایِ
نماد** (DDL `test_tsetmc.py:426-428`)؛ تاریخچۀ عمقِ صف هیچ‌جا نیست. تنها ردِّ زمانی،
aggregate در `mstat_snap(d_even, h_even, ts, agg)` است (DDL `test_tsetmc.py:963-965`، هر ۳۰۰
ثانیه).

`price_history` = `symbol, date, open, high, low, close, volume, last, value, src`
(`src ∈ published|board|index-synthetic`) — 383366 سطر.
بقیه: `daily_prices`, `tape_history`, `tape_history_state`, `market_totals`, `market_index`,
`market_liquidity`, `boards`, `adjust_events`, `adjust_verdict`, `codal_notices`,
`codal_extracted`, `financial_statements`, `monthly_sales`, `fts_results`, `symbol_sectors`,
`market_cap_snapshots`, `selection_decisions`, `user_watchlists`, `board_hist_fv`,
`board_hist_v`.

### 2.3 طبقۀ هر قابلیت

مقادیر: SOURCE-NATIVE / RECONSTRUCTED / APPROXIMATED / CACHED / DERIVED / MISSING / UNAVAILABLE.

| قابلیت | طبقه | شاهد |
| --- | --- | --- |
| تابلو: `pcl/pdv/py/pf/pmn/pmx/pMin/pMax/qtj/qtc/ztt/eps/pe/bv/csv/ztd` | SOURCE-NATIVE | `test_tsetmc.py:1391-1425` |
| `market_cap` | SOURCE-NATIVE با fallbackِ DERIVED (`marketValue`، وگرنه `pcl×ztd`) | `MW_COLS` + `market_cap_src` |
| `p_last` | SOURCE-NATIVE (`pdv`) با fallbackِ DERIVED (`py+pc`) | `test_tsetmc.py:97-101` |
| ستون‌هایِ صف (`buy_q_val` و …) | DERIVED از `blDs` (جمعِ ۵ سطح) | `queue_agg` `test_tsetmc.py:378-405` |
| `blDs` خام | CACHED (JSON در `order_book.book_txt`) | `book_lines` `test_tsetmc.py:431-451` |
| تاریخچۀ عمقِ صف | **MISSING** (منبعش هست — §13) | — |
| حجم/تعدادِ حقیقی-حقوقی | SOURCE-NATIVE | `client_type` |
| **ارزشِ حقیقی-حقوقی** | **RECONSTRUCTED** (`vol × vwap`) | `mstat_engine.py:761-765`، `vwap` خطِ 747 |
| کندلِ روزانۀ OHLCV | SOURCE-NATIVE (`published`) + DERIVED (مسیرِ تابلو، `src=board`) | `candle_contract.UPSERT_SQL` |
| `high/low` کندل | APPROXIMATED (widened با `widen()`) | `candle_contract.widen` |
| `open` کندلِ شاخص | DERIVED = closeِ روزِ قبل | `api/market_index.py:159-160` |
| رویدادِ تعدیلِ قیمت | **APPROXIMATED/INFERRED** از شکافِ `<BASE>`/`<CLOSE>` | `api/chart.py:100-158`؛ خودِ کد: «هیچ‌یک از این‌ها درِ فیدِ TSETMC نیست» `api/chart.py:173-177` — **این جمله دیگر درست نیست، §17** |
| شاخصِ کل/هم‌وزن + `idx_pct` | SOURCE-NATIVE + DERIVED (`_idx_pct`) | `test_tsetmc.py:239-272` |
| `market_liquidity.value_hemat` | DERIVED (محاسبهٔ پایتون از `mstat_engine.macro_health`) | `test_tsetmc.py:275-312` |
| پنجرۀ `[ih]` (۶۰ نشست) | SOURCE-NATIVE (`tape_history`) | `test_tsetmc.py:488-498` |
| ISIN / sub-sector / free-float | **MISSING** | §15 |
| وضعیتِ نماد (`cEtaval`, `underSupervision`) | **MISSING** | §11/§17 |
| علتِ توقف (`dalils`) | **MISSING** (فقط webgw) | §11 |
| پیامِ ناظر | **MISSING** — و عمداً حذف شده: `SAVE_USEFUL_ONLY` در `codal_fetcher.py:77-79` عنوان‌هایِ «توقف/بازگشایی» را دور می‌ریزد | §13 |
| تغییرِ مالکیت | **MISSING** | §16 |
| تیک/تراپی | **MISSING** | §18 |
| delta / POC / imbalance | **MISSING** | §18 |
| incrementalityِ تابلو | **APPROXIMATED** (snapshot کامل + diff محلی) | §14 |
| `flow`, `pRedTran`, `buyOP`, `cGrValCot`, `insID` | **MISSING** با وجودِ حضورِ در پاسخِ دریافتی | §9.1 |

---

## 3. Project 1 — BabakEslami/tse-market-data

| مورد | مقدار |
| --- | --- |
| ماهیت | **مستند، نه کتابخانه.** ۹ فایل؛ تنها کدِ قابل‌اجرا `scripts/test_active_tsetmc_endpoints.py` (342 خط) |
| branch / آخرین commit | `main` / `3d9d03b` «Add files via upload»، 2026-07-15 |
| نسخه | tag ندارد؛ `ENDPOINTS.md` خودش را `v4.1` می‌خواند |
| language / license | Python 3 / MIT |
| architecture | یک liveness-monitorِ تک‌فایل روی `requests` + مرجعِ 639خطیِ فارسی |

**ارزشِ اصلی:** کامل‌ترین فهرستِ endpointها در بینِ پنج پروژه — 55 مسیرِ CDN که **CODE-VERIFIED**
درخواست می‌شوند (خطوطِ 49–104)، + 30 مسیرِ `webgw.tse.ir` که **README-ONLY‌اند**
(`ENDPOINTS.md:410-514`، از HAR؛ هیچ کدی webgw را لمس نمی‌کند)، + Excelِ
`old.tsetmc.com/tsev2/excel/MarketWatchPlus.aspx?d=0`.

نکاتِ استخراج‌شده:
- ادعا: `ClosingPrice/GetMarketWatch` روی CDN «همیشه `marketwatch: 0` برمی‌گرداند»
  (README-ONLY، `ENDPOINTS.md:188`) — **غلط از آب درآمد**: با `paperTypes[]` و UA درست،
  3847 سطر گرفتیم (LIVE-VERIFIED، §11). تفاوت در query است نه endpoint.
- ادعا: `BestLimits` **delta است نه snapshot** (README-ONLY `ENDPOINTS.md:205`) — **تأیید شد**
  (§13، LIVE).
- `sum(trades.volume)` ≈ 36–38٪ کمتر از آمارِ رسمی؛ برایِ حجمِ رسمی باید
  `qTotTran5J/qTotCap/zTotTran` مصرف شود (README-ONLY `ENDPOINTS.md:218`). سازگار با §10.
- `GetInstValueAllInstAllParam` ≈ 24MB / 299174 رکورد (README-ONLY) — LIVE: 26.8MB / 326983.
- کلیدِ پاسخِ sectors غلطِ املاییِ سرور است: `sectorSummeries` (README-ONLY) — LIVE-VERIFIED.
- UA نبود ⇒ 403 (README-ONLY) — LIVE-VERIFIED (اولین درخواستِ بدونِ UA ما 403 گرفت).
- webgw «فقط از IP ایران» (README-ONLY) — LIVE-VERIFIED: از همین ماشین کار کرد.

**فرمول:** فقط `priceChange = pDrCotVal − priceYesterday` و
`percent = priceChange/priceYesterday×100` برایِ `GetIndexCompany` (README-ONLY
`ENDPOINTS.md:140-144`). VWAP/market-cap ندارد.

---

## 4. Project 2 — ORBO-ir/ORBO

| مورد | مقدار |
| --- | --- |
| branch / commit | `main` / `6ae501a1` 2026-07-05، نسخه `0.2.4`، 8 commit، تک‌نویسنده |
| language / deps | Python ≥3.11؛ `httpx`, `pandas`, `pyarrow`, `pydantic`, `jdatetime`. `rich` اعلام‌شده ولی **هیچ importی ندارد**؛ `numpy` مصرف می‌شود ولی اعلام نشده |
| architecture | `src/orbo/{clients,data,engines,history,index,intraday,models,option_chain,registry,search,static}`؛ ~7900 خط؛ 245 تستِ آفلاین (HTTP mock)؛ **بدونِ CI** |
| host | **فقط** `cdn.tsetmc.com/api` (`constants.py:3`)؛ webgw صفر occurrence |

**دیتا لایر (CODE-VERIFIED):** `Trade/GetTradeHistory/{ins}/{date}/{true|false}` ⇒ `tradeHistory`؛
`BestLimits/{ins}/{date}` ⇒ `bestLimitsHistory`؛ `Trade/GetTrade/{ins}` ⇒ `trade`؛
`BestLimits/{ins}` ⇒ `bestLimits`؛ `ClientType/GetClientTypeHistory/{ins}/{date}` و
`ClientType/GetClientType/{ins}/1/0`؛ `Shareholder/{ins}/{date}`؛
`ClosingPrice/GetClosingPriceHistory/{ins}/{date}`؛ `GetPriceAdjustList`؛
`GetInstrumentShareChange`؛ `Msg/GetMsgByInsCode`؛ `Index/GetIndexB1LastAll|B1LastDay|B2History`؛
`ClosingPrice/GetIndexCompany`. هشت ثابتِ `Endpoints` **فقط اعلام شده‌اند و هیچ call-site ندارند**.

**TradeSideEngine** (`engines/trade_side.py`) — Lee & Ready (1991)، DOI در `:23-25`:
```
Quote Rule : buy = (ask > 0) and (price >= ask)      # :226
             sell = (bid > 0) and (price <= bid)     # :227
             book lookup = merge_asof(direction="backward") روی level==1   # :211-218
Tick Rule  : curr>prev → buy ; curr<prev → sell ; curr==prev → carry last side   # :81-96
output     : side ∈ {buy,sell,unknown} + method ∈ {quote,tick,tick_carry,unknown}
```
**FootprintEngine** (`engines/footprint.py`):
```
delta      = buy_volume − sell_volume                                  # :216
classified = buy_volume + sell_volume                                  # :218
buy_pct    = buy/classified×100 (else 50.0)                            # :219-223
POC        = price at max(total_volume)                                # :225-227
imbalance  = buy >= 3.0×sell → demand ; sell >= 3.0×buy → supply ; tot<10 → insufficient  # :270-280
session buy% = Σbuy/classified×100 ; classified% = classified/total_all×100   # :242-243
```
**VWAP** = `Σ(price×volume)/Σ(volume)` (`intra_stats.py:164`).

**یافته‌هایِ انتقادی (CODE-VERIFIED):**
- «Footprint» در ORBO **بدونِ محورِ زمان** است: `groupby("price")` تنها (`:187-205`)، یعنی یک
  volume-profile کلِ روز، نه چارتِ footprint. README بزرگ‌نمایی می‌کند.
- `cumulative delta`، `stacked imbalance`، `absorption`، `Greeks/IV` ⇒ **هیچ‌کدام پیاده نیست**.
- کفِ «10 contracts» برایِ حجمِ سهم بی‌معناست؛ `canceled` منتقل می‌شود ولی **هرگز فیلتر نمی‌شود**
  ⇒ معاملاتِ ابطال‌شده در مخرجِ VWAP/footprint می‌مانند (باگِ واقعی در مرجع).
- `GetTrade` تاریخ را از ساعتِ **محلیِ کلاینت** می‌سازد (`instrument.py:36-39`).
- **هیچ rate-limitی ندارد**؛ 429 به `HTTP error 429` می‌رسد و دوباره retry می‌شود؛ برخلافِ
  `HTTPClient`، کلاینت‌هایِ جدید `follow_redirects` ندارند ⇒ 301 به retry-storm تبدیل می‌شود.
- **raw trades هیچ‌جا persist نمی‌شوند** — هر footprint یعنی دانلودِ دوبارهٔ آن روز.

**AdjustmentEngine** (`engines/adjustment.py`) — گران‌سارترین بخشِ ORBO، و **به تیک ربطی ندارد**:
```
factor_price = pClosing / pClosingNotAdjusted
factor_share = numberOfShareOld / numberOfShareNew
cum[i]       = factor[i] × cum[i+1]                       # backward pass
adjusted(D)  = raw(D) × ∏ factors(events with date > D)   # bisect_right
هم‌تاریخ: share_change (0) قبل از price_adjust (1)        # CRSP/Bloomberg convention
```
نقصِ مستند: فقط `_PRICE_FIELDS` تعدیل می‌شوند، **حجم مقیاس نمی‌گیرد** (`history.py:10-12,47-49`).

---

## 5. Project 3 — hemoboghosian/fima

| مورد | مقدار |
| --- | --- |
| branch / commit | `master` / `c322ef7` 2026-09-27، نسخه `0.4.0` |
| language / deps | Python ≥3.10؛ `requests`, `pandas`, `numpy`, `scipy`, `bs4`, `lxml`, `jdatetime`, `persian`, `mibian`, `truststore` |
| architecture | ۵ ماژولِ تختِ بزرگ: `TSETMC.py` 487L، `Options.py` 654L، `Funds.py` 1128L، `IFB.py` 1114L، `IME.py` 649L |
| host | **فقط** `cdn.tsetmc.com/api` (19 مسیر) + `ifb.ir` + `ime.co.ir` + `fipiran.ir` + `cfi.rbcapi.ir` |

**سؤالِ کلیدیِ brief از این پروژه — پاسخِ منفی:** fima **هیچ‌وقت** `Loader.aspx` /
`var dataInline` / `tsev2` را پارس نمی‌کند. تنها اثرش بلوکِ **کامنت‌شده** در
`TSETMC.py:294-333` است که `MarketWatchInit.aspx?h=0&r=0` را با `split('@')` → `split(';')` →
`split(',')` و انتخابِ *موقعیتیِ* ستون‌های `[0,2,3]` می‌خواند (و `timeout` دوبار دارد؛ اگر باز
شود SyntaxError). ⇒ **برایِ فیلد-دیکشنریِ inline هیچ ارزشی ندارد.**

**سه چیزِ منحصربه‌فرد:**
1. **ClientType با ارزشِ ریالی، از مسیرِ CDN.** `TSETMC.py:159-165` این ۱۴ فیلد را rename می‌کند:
   `buy_I_Volume/buy_N_Volume/buy_I_Value/buy_N_Value/buy_I_Count/buy_N_Count/
   sell_I_Volume/sell_N_Volume/sell_I_Value/sell_N_Value/sell_I_Count/sell_N_Count` + `recDate`
   + `insCode`. ⇒ **تنها مرجعی که `*_Value` را در نام دارد** — §12 با درخواستِ واقعی تأییدش
   می‌کند.
2. **`Supervision/GetSupervisionListBySourceID`** (`TSETMC.py:73`) — تنها پروژه‌ای که این مسیر را
   صدا می‌زند؛ flow را `1` hard-code کرده و `range(1,4)` ⇒ فرابورس را هرگز نمی‌بیند.
3. **`Instrument/GetInstrumentHistory/{ins}/{date}` ⇒ `zTitad`** (`TSETMC.py:180-182`) و
   `MarketCap = SharesNo × ClosePrice` (`TSETMC.py:198`) — market-cap تاریخچۀ **شناور‌نخورده**.

**Anti-patternهایی که نباید کپی شوند (CODE-VERIFIED):** هیچ `Session`، هیچ `headers`، هیچ `cache`
برایِ TSETMC؛ `_find_instrument_code()` که ۷ تابع صداش می‌زنند **هر بار** `GetInstrumentSearch`
را دوباره می‌گیرد؛ `except: return None` که 429 را به «دادهٔ کمترِ بی‌سروصدا» تبدیل می‌کند؛
`verify=False` در `Funds.py` (۱۷ بار) کنارِ `truststore.inject_into_ssl()` که در سطحِ پروسه SSL
را عوض می‌کند (برایِ اپِ PyInstaller ما خطرناک)؛ CI که همهٔ تست‌هایِ شبکه را skip می‌کند در حالی
که README (`:234`) می‌گوید انتشار با تستِ شکسته متوقف می‌شود.

**ارزشِ جانبی:** `convert_ar_characters` پیش از هر مقایسه (`TSETMC.py:274-276`) — درمانِ «ي/ی»؛
در BorsTerminal معادلش برایِ رقم هست (`toFaDigits`) ولی در مسیرِ واکشی برایِ حروف نه.

---

## 6. Project 4 — 5j9/tsetmc

| مورد | مقدار |
| --- | --- |
| branch / commit | `main` / `fdaf0e0` 2026-08-11، نسخه `5.1.1.dev1`، releases فعال (v5.0.0 2026-07-23، v5.1.0 2026-08-11) |
| language / deps | Python **≥3.14**؛ `polars` (pandas حذف)، `aiohutils`، `html-table-parse`، `lxml`؛ GPLv3 |
| architecture | `tsetmc/{market_watch,instruments,indices,general,funds,docs}.py` + `dataset/dataset.csv` (مسترِ نمادها: `ins_code,isin,cisin,l18,l30`) |
| tests | ~110 **fixtureِ ضبط‌شدۀ واقعی** در `tests/testdata/` (`.aspx` خام + JSON) — گراورِترِینِ سیمِ TSETMC |
| hosts | `old.tsetmc.com` (inline + Loader) + `members.tsetmc.com` + `cdn.tsetmc.com/api` — **هر سه** (`__init__.py:234-237`)؛ webgw صفر |

این پروژه **منبعِ مرجعِ پروتکلِ incremental** است؛ §14 بر پایهٔ کدِ اوست (و بر تأییدِ زندۀ خودِ من).

**فیلد-دیکشنریِ inline (26 ستون، `market_watch.py:40-74`، در برابرِ `market_watch_plus.js:1652-1750`):**

| idx | key | معنا | idx | key | معنا |
| --- | --- | --- | --- | --- | --- |
| 0 | `ins_code` | InsCode | 13 | `py` | قیمتِ دیروز |
| 1 | `isin` | ISIN | 14 | `eps` | EPS (می‌تواند خالی باشد) |
| 2 | `l18` | نماد | 15 | `bvol` | حجمِ مبنا |
| 3 | `l30` | نام | 16 | `visitcount` | بازدید |
| 4 | `heven` | زمانِ آخرینِ معامله HHMMSS | 17 | `flow` | کدِ بازار (`Flow` enum، `__init__.py:109-122`) |
| 5 | `pf` | اولین قیمت | 18 | `cs` | `CSecVal` صنعت |
| 6 | `pc` | قیمتِ پایانی | 19 | `tmax` | سقفِ مجازِ نوسان |
| 7 | `pl` | آخرین قیمت | 20 | `tmin` | کفِ مجازِ نوسان |
| 8 | `tno` | تعدادِ معامله | 21 | `z` | `zTitad` کلِ سهام |
| 9 | `tvol` | حجم | 22 | `yval` | کدِ نوعِ ورقه |
| 10 | `tval` | ارزش | 23 | `predtran` | NAVِ استرداد (ETF) |
| 11 | `pmin` | کمترین | 24 | `buyop` | NAVِ صدور (ETF) |
| 12 | `pmax` | بیشترین | 25 | `cgrvalcot` | گروهِ کالایی |

**سطرِ delta = 10 فیلد:** `ins_code, heven, pf, pc, pl, tno, tvol, tval, pmin, pmax`
(`market_watch.py:76`؛ تشخیصِ «سطرِ تازه» از «به‌روزرسانی» با `len(ip) != 10` در `:211,222`).
**`plc/plp/pcc/pcp/pe` سمتِ مرورگر محاسبه می‌شوند، نه سرور**
(`market_watch_plus.js:1734-1749`) و `plc/plp` وقتی `tno==0` است رویِ `"0"` قفل می‌شوند
(`:1741-1753`) — **همان چیزی که `plp_series()` ما بازتولید می‌کند** (§10).

**عمقِ صف inline:** 8 فیلد `ins_code, number, zo, zd, pd, po, qd, qo`
(`_BEST_LIMITS_SCHEMA` `market_watch.py:29-38`)؛ `d`=demand=خرید، `o`=offer=فروش؛ `p` قیمت،
`q` حجم، `z` تعدادِ سفارش.

**ClientType:** امروز `GetClientType/{ins}/1/0` ⇒ حجم+تعداد؛ تاریخ `GetClientTypeHistory` ⇒
`ClientTypeOnDate` (`instruments.py:246-261`) **ارزش هم دارد**. تعارضِ واژگانیِ مستند در
مرجع‌ها: §12.4.

**مواردِ دیگر:** `instinfodata.aspx` با 16/17 فیلدِ موقعیتی (`instruments.py:1254-1307`)؛
`InstValue.aspx` با `is51…is89` که معناشان **درِ کد decode نشده** و به
`Site.aspx?ParTree=151715` واگذار شده (README-ONLY)؛ `search.aspx` legacy با 4 کدِ معاملاتی
(`ins_code=round_lot, retail=odd_lot, compensation=buyback, wholesale=block`)؛ `docs.py` که
جدولِ معنایِ فیلدها را از صفحاتِ رسمیِ `tsetmc.com/StaticContent/WS-*` **اسکرپ می‌کند** به‌جایِ
hard-code (`WS-ClientType`, `WS-Instrument`, `WS-InstrumentsState`, `WS-BestLimitsAllIns`).

---

## 7. Project 5 — solitraderbusiness/tsetmc-mcp

| مورد | مقدار |
| --- | --- |
| branch / commit | `main` / `abf182f` 2026-07-04، نسخه `0.1.0`، 6 commit |
| language / deps | Python ≥3.11؛ `mcp[cli]`, `aiohttp`, `jdatetime`؛ extra اختیاری `tsetmc>=3.0` (کتابخانۀ 5j9) |
| architecture | `src/tsetmc_mcp/{server,service,snapshot,poller,models,normalize,shaping,calendar,jalali,config}` + `fetch/` + `filter/`؛ 15 فایلِ تستِ **کاملاً آفلاین** |
| host | **فقط** `cdn.tsetmc.com/api`؛ `legacy_base`/`members_base` در `config.py:44-45` اعلام شده‌اند ولی **هیچ fetchی از آن‌ها نمی‌کند** (CODE-VERIFIED) |

**۱۳ ابزارِ MCP** (`server.py:47-241`): `search_symbol`, `get_quote`, `get_order_book`,
`get_money_flow`, `get_market_watch`, `screen`, `get_index_overview`, `get_price_history`,
`market_status_tool`, `describe_fields`, `run_filter`, `run_saved_filter`, `filter_help`.

**گران‌سارترین خروجیِ این پروژه: DSLِ بازپیاده‌شدهٔ زبانِ فیلترِ TSETMC**
(`filter/normalize_expr.py:23-32`، `filter/variables.py:37-73`). واژگانِ پذیرفته‌شده:
```
pl, pc, py, pf, pmax, pmin, plp, pcp, plc, pcc, tvol, tval, tno, bvol, eps, pe,
symbol/l18, name/l30, flow,
ct_buy_i_vol, ct_sell_i_vol, ct_buy_count_i, ct_sell_count_i,
ct_buy_n_vol, ct_sell_n_vol, ct_buy_count_n, ct_sell_count_n,
net_individual, percap_buy, percap_sell, buyer_power,
pd1..pd5 / qd1..qd5 / zd1..zd5 , po1..po5 / qo1..qo5 / zo1..zo5
buy_queue(), sell_queue()
```
توکن‌هایِ `(ct).Buy_I_Volume` بازنویسی می‌شوند؛ `&&`/`||`/`!` → `and/or/not`؛ و **`[ih]` و `[is30]`
صریحاً رد می‌شوند** (`normalize_expr.py:46,75-79`) — یعنی این مرجع پنجرۀ تاریخچۀ ۳۰ روزه را
اصلاً پشتیبانی نمی‌کند، جایی که ما آن را با `tape_history` داریم (§19).

فرمول‌ها (CODE-VERIFIED):
```
pct_change    = round((last − yesterday)/yesterday × 100, 2)              # models.py:68
percap_buy    = ct_buy_i_vol / ct_buy_count_i                             # variables.py:107
percap_sell   = ct_sell_i_vol / ct_sell_count_i                           # variables.py:107
buyer_power   = percap_buy / percap_sell                                  # variables.py:158
net_individual= ct_buy_i_vol − ct_sell_i_vol                              # variables.py:155
buy_queue     = ((qo1 == 0 or po1 == 0) and qd1 > 0)                      # normalize_expr.py:19
sell_queue    = ((qd1 == 0 or pd1 == 0) and qo1 > 0)                      # normalize_expr.py:20
preset کد‌به‌کد  : ct_buy_i_vol > 0.5*volume and ct_sell_n_vol > 0.5*volume
                  and percap_buy > percap_sell                            # presets.py:27
preset حجمِ مشکوک: volume > 3*base_volume                                 # presets.py:35
```
**مقایسهٔ مستقیم با فیلترِ ما:** presetِ `presets.py:27` همان `f_legal` ماست **بعلاوهٔ** بندِ
`percap_buy > percap_sell`. سندِ ما
(`docs/ورود پول هوشمند و کد به کد حقوقی به حقیقی.txt`) آن بندِ سوم را **ندارد** ⇒ شاهدِ بیرونی
که دیگران نسخهٔ تغییریافته را می‌سازند و ما نسخهٔ سند را نگه می‌داریم. **آستانۀ تازه‌ای پیشنهاد
نمی‌شود** (طبقِ brief).

**طراحیِ ارزشمند:** pollerِ پس‌زمینه + snapshotِ درحافظه (ابزارها هرگز fetchِ بازارِ کامل را راه
نمی‌اندازند)، token bucketِ 1.5 req/s، و **403/429 ⇒ `TsetmcBlocked` فوراً بدونِ retry**
(`session.py:120-121`) — درست برعکسِ ORBO. تشخیصِ بن با متنِ فارسیِ «مسدود»/«دسترسی شما»
(`session.py:22-26`). circuit breaker با `min(poll×2^fail, 120)` (`poller.py:93`).

**README-vs-code (CODE-VERIFIED):** «5j9 accelerator progressively faster» درست نیست — هر متدِ
`LibrarySource` فقط به `RawSource` واگذار می‌کند (`library_source.py:43-65`؛ docstring خودش
می‌پذیرد). README می‌گوید `market_status`، ثبتِ ابزار `market_status_tool`. «paste a real TSETMC
filter and it runs as-is» فقط بدونِ `[ih]` راست است.

**غایب‌ها:** تیک/تراپی، سهامداران، نظارت، تعدیل/سرمایه، market cap/sector/ISIN، آستانه‌هایِ قیمت
(`tmax/tmin` در فهرستِ UNSUPPORTED، `variables.py:92-93`)، عمقِ صفِ تاریخی.

## 8. Endpoint Matrix

ستونِ «Bors» = وضعیتِ ما: EXACT / PARTIAL / RECONSTRUCTED / APPROXIMATED / MISSING /
SOURCE-UNAVAILABLE / NOT-USEFUL. ستونِ «L» = ✓ یعنی LIVE-VERIFIED در این دور؛ «–» یعنی فقط از
کد یا مستند.

| Source | Endpoint | Method | Params | Main fields | Hist/Live | Bors | پیاده‌سازیِ موجود | L |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tse-md, ORBO, fima, mcp | `ClosingPrice/GetMarketWatch` | GET | market, paperTypes[], showTraded, withBestLimits, hEven, RefID | `lva,lvc,pcl,pdv,pf,py,pc,pmn,pmx,pMin,pMax,qtj,qtc,ztt,pcpc,eps,pe,bv,csv,ztd,flow,insID,pRedTran,buyOP,blDs[],iClose,dEven,hEven,cGrValCot` | Live | **PARTIAL** | `test_tsetmc.py:37,1436,1591,1723` — `flow/insID/pRedTran/buyOP/cGrValCot` خوانده نمی‌شوند | ✓ |
| 5j9 | `tsev2/data/MarketWatchInit.aspx` | GET | h=0, r=0 | 5 بخشِ `@`: msg, fastview, 3847×26 states, 18244×8 bestlimits, refID | Live snapshot | **MISSING** | — | ✓ |
| 5j9 | `tsev2/data/MarketWatchPlus.aspx` | GET | `h=5*(heven//5)`, `r=25*(refID//25)` | فقط سطرهایِ تغییریافته (10 فیلد) + book delta + refIDِ تازه | **Live delta** | **MISSING** | — | ✓ |
| tse-md, ORBO, fima, mcp | `ClosingPrice/GetClosingPriceInfo/{ins}` | GET | insCode | `pClosing,pDrCotVal,zTotTran,pRedTran,qTotTran5J,qTotCap,nvt,mop,priceChange,priceMin/Max/Yesterday/First,finalLastDate,lastHEven,instrumentState` | Live | **MISSING** (per-symbol) | snapshotِ تابلو جای آن را می‌گیرد | ✓ |
| tse-md, ORBO | `ClosingPrice/GetClosingPriceDailyList/{ins}/{top}` | GET | insCode, top | `dEven,hEven,pClosing,pDrCotVal,priceChange,priceMin/Max/Yesterday/First,zTotTran,qTotTran5J,qTotCap,iClose,yClose,last` | Hist | **PARTIAL** (ما CSV می‌گیریم، نه JSON) | `test_tsetmc.py:1226`, `api/chart.py:507` | ✓ |
| Bors فقط | `ClosingPrice/GetClosingPriceDailyListCSV/{sym}/{from}` | GET | symbol, from | 12 ستونِ CSV | Hist | EXACT | `test_tsetmc.py:1226` | – |
| tse-md, ORBO, mcp | `ClosingPrice/GetClosingPriceHistory/{ins}/{date}` | GET | insCode, dEven | `dEven,hEven,pClosing,pDrCotVal,qTotTran5J,qTotCap,zTotTran,iClose,yClose` | **Intraday snapshots** | **MISSING** | — | ✓ |
| tse-md | `ClosingPrice/GetInstrmentsHistoryInDay/{date}` | GET | dEven | `insCode,lVal18AFC,priceFirst/Max/Min/Yesterday,pClosing,pDrCotVal,qTotTran5J,qTotCap,zTotTran` | Hist (کل بازار/روز) | EXACT (backfill tool) | `tools/backfill_daily_history.py:35` | – |
| Bors فقط | `ClosingPrice/GetClosingPriceDailyAllInst` | GET | – | `insCode,dEven,priceMin,priceMax,qTotTran5J` | Hist (پنجرۀ `[ih]`) | EXACT | `test_tsetmc.py:474` | – |
| tse-md, ORBO, fima, mcp | **`ClientType/GetClientTypeAll`** | GET | – | `insCode,buy_I_Volume,buy_N_Volume,buy_DDD_Volume,buy_CountI,buy_CountN,buy_CountDDD,sell_I_Volume,sell_N_Volume,sell_CountI,sell_CountN` | Live | **EXACT (حجم/تعداد)**؛ **MISSING (ارزش)** | `test_tsetmc.py:1444,1763` | ✓ 2236 سطر |
| tse-md, ORBO, fima, mcp | `ClientType/GetClientType/{ins}/1/0` | GET | insCode | همان، بدونِ `sell_CountDDD` | Live | **MISSING** (per-symbol) | — | ✓ |
| **tse-md, ORBO, fima** | **`ClientType/GetClientTypeHistory/{ins}/{date}`** | GET | insCode, dEven | **`buy_I_Value,buy_N_Value,sell_I_Value,sell_N_Value`** + `buy_I_Volume,buy_N_Volume,sell_I_Volume,sell_N_Volume,buy_I_Count,buy_N_Count,sell_I_Count,sell_N_Count,recDate,insCode` | **Hist** | **MISSING** ← ما RECONSTRUCTED کرده‌ایم | `mstat_engine.py:761-765` | ✓ |
| tse-md, ORBO, mcp | `BestLimits/{ins}` | GET | insCode | `number,pMeDem,qTitMeDem,zOrdMeDem,pMeOf,qTitMeOf,zOrdMeOf,title,insCode` | Live | **EXACT** (از `blDs` در تابلو، نه از این endpoint) | `queue_agg` `test_tsetmc.py:378-405` | ✓ |
| tse-md, ORBO | `BestLimits/{ins}/{date}` | GET | insCode, dEven | `bestLimitsHistory[]`: `refID,idn,dEven,hEven,number,pMeDem,qTitMeDem,zOrdMeDem,pMeOf,qTitMeOf,zOrdMeOf` | **Hist — delta stream** | **MISSING** | — | ✓ 21759 سطر، 4.2MB |
| tse-md, ORBO, fima, mcp | `Trade/GetTrade/{ins}` | GET | insCode | `nTran,hEven,pTran,qTitTran,canceled,qTitNgJ,iSensVarP,pPhSeaCotJ,pPbSeaCotJ,iAnuTran,xqVarPJDrPRf` | Live (کلِ نشست) | **MISSING** | — | ✓ 27653 رکورد، 5.5MB |
| tse-md, ORBO | `Trade/GetTradeHistory/{ins}/{date}/{combine}` | GET | insCode, dEven, true/false | `tradeHistory[]` همان | **Hist ticks** | **MISSING** | — | ✓ 28943 رکورد، 5.8MB |
| tse-md | `Trade/GetTradeIntraDay/{ins}` | GET | insCode | `tradeIntraDay[]`: `hEven,openPrice,closePrice,maxPrice,minPrice,volume` | Intraday bars | **MISSING** | — | ✓ 105 سطر، 11KB |
| tse-md | `Trade/GetTradeVolume/{ins}` | GET | insCode | `tradeVolume[]`: `pTran,qTitTran,firstTradeTime,lastTradeTime` | **قیمت‌به‌حجم (POC-ready)** | **MISSING** | — | ✓ 30 سطح، 3.4KB |
| tse-md, ORBO, fima, mcp | `Instrument/GetInstrumentInfo/{ins}` | GET | insCode | `eps,nav,contractSize,baseVol,zTitad,cIsin,instrumentID,sector,subSector,cgrValCot,flow,flowTitle,kAjCapValCpsIdx,minWeek/maxWeek/minYear/maxYear,qTotTran5JAvg,faraDesc,etfIssuedUnit,underSupervision,staticThreshold,yVal,cComVal,lSoc30,cValMne` | Meta | **MISSING** | — | ✓ |
| tse-md, ORBO | `Instrument/GetInstrumentIdentity/{ins}` | GET | insCode | `cIsin,instrumentID,sector{cSecVal,lSecVal},subSector{cSoSecVal,lSoSecVal},zTitad,baseVol,yVal,yMarNSC,flow,flowTitle,cgrValCot,cComVal,lVal18,lVal18AFC,lVal30,sourceID,cValMne` | Meta | **MISSING** | — | ✓ |
| 5j9, tse-md | `Instrument/GetInstrumentSearch/{query}` | GET | query | `insCode,lVal18AFC,lVal30,cIsin,flowTitle` + `insCode2/3/4` (بلوکی/جبرانی/عمده) | Meta | **MISSING** (نام→کد از بانکِ خودمان) | lookup داخلی | – |
| fima | `Instrument/GetInstrumentHistory/{ins}/{date}` | GET | insCode, dEven | `zTitad,baseVol,cIsin,instrumentID,flow,cgrValCot,lVal18AFC,lVal30,lastDate,sourceID,cComVal` | **Hist shares** | **MISSING** | — | ✓ |
| tse-md, ORBO, fima | `Instrument/GetInstrumentShareChange/{ins}` | GET | insCode | `dEven,idn,insCode,lVal18AFC,lVal30,numberOfShareOld,numberOfShareNew` | Events | **MISSING** | — | ✓ 6 رویداد |
| tse-md, fima | `Instrument/GetInstrumentShareChangeByFlow/{flow}/{days}` | GET | flow, days | همان | Events (کل بازار) | **MISSING** | — | ✓ 2395 رکورد |
| tse-md, ORBO, fima | `ClosingPrice/GetPriceAdjustList/{ins}` | GET | insCode | `dEven,insCode,pClosing,pClosingNotAdjusted,corporateTypeCode,instrument{…}` | **Events** | **MISSING** (ما infer می‌کنیم) | `api/chart.py:100-158` | ✓ 11 رویداد |
| tse-md, fima | `ClosingPrice/GetPriceAdjustByFlow/{flow}/{size}` | GET | flow, size | همان | Events (کل بازار) | **MISSING** | — | ✓ |
| tse-md, ORBO, fima, mcp | `MarketData/GetMarketOverview/{flow}` | GET | flow | `indexLastValue,indexChange,indexEqualWeightedLastValue,indexEqualWeightedChange,marketValue,marketValueBase,marketActivityDEven/HEven,marketActivityZTotTran,marketActivityQTotCap,marketActivityQTotTran,marketState,marketStateTitle,lastDataDEven,lastDataHEven` | Live | **EXACT** | `test_tsetmc.py:186-217,249-272` | ✓ |
| tse-md, ORBO | `MarketData/GetInstrumentState/{ins}/{date}` | GET | insCode, dEven | `cEtaval,cEtavalTitle,underSupervision,realHeven,idn,insCode,lVal18AFC,lVal30,dEven,hEven` | Hist+Live | **MISSING** | — | ✓ |
| tse-md | `MarketData/GetInstrumentStateTop/{top}` | GET | top | همان | Live (تغییراتِ وضعیت) | **MISSING** | — | ✓ |
| tse-md, ORBO | `MarketData/GetStaticThreshold/{ins}/{date}` | GET | insCode, dEven | `psGelStaMax,psGelStaMin,dEven,hEven,insCode` | Hist | **PARTIAL** (`pMin/pMax` تابلو همین است) | `allowed_min/allowed_max` | ✓ |
| tse-md | `MarketData/GetInstrumentStatistic/{ins}` | GET | insCode | 88 سطرِ `dataType,dataTypeDesc,dataValue,partitionCode` با توضیحِ فارسی («میانگین ارزش معاملات در 3 ماه گذشته») | Derived stats | **MISSING** | — | ✓ |
| tse-md | `MarketData/GetInstValueAllInstAllParam` | GET | – | 326983 سطرِ `insCode,dataType,dEven,dataValue` | Derived stats (کل بازار) | **MISSING** | — | ✓ 26.8MB |
| tse-md, fima, mcp | `MarketData/GetSectorsSummary` | GET | – | `sectorSummeries[]`: `cSecVal,lSecVal,c1,c2,c3,c4` | Live | **MISSING** (از `StaticData` + محاسبهٔ محلی) | `mstat_engine.industries` | ✓ 51 صنعت |
| tse-md, ORBO, fima, mcp | `StaticData/GetStaticData` | GET | – | `staticData[]`: `type,code,name` | Meta | **EXACT** | `test_tsetmc.py:1434,1714` | ✓ |
| tse-md | `StaticData/GetTime` | GET | – | متنِ `MM/DD/YYYY HH:MM:SS` | Clock | **MISSING** (ساعتِ محلی مصرف می‌شود) | — | ✓ |
| tse-md, ORBO, fima, mcp | `Shareholder/{ins}/{date}` | GET | insCode, dEven | `shareHolderName,numberOfShares,perOfShares,change,changeAmount,shareHolderID,shareHolderShareID,cIsin,dEven` | Hist | **MISSING** | — | ✓ 17 سطر |
| tse-md | `Shareholder/GetInstrumentShareHolderLast/{ins}` | GET | insCode | `shareHolder[]` همان | Live | **MISSING** | — | ✓ |
| tse-md | `Shareholder/GetShareHolderChanges/false` | GET | combine | `shareHoldersChanges[]: {insList,name}` + `dates[]` | Events (کل بازار) | **MISSING** | — | ✓ 566+5 |
| tse-md | `Shareholder/GetShareHolderCompanyList/{id}` | GET | ShareHolderShareID | – | Hist | **MISSING** | — | – آزموده نشد |
| tse-md, ORBO | `Msg/GetMsgByInsCode/{ins}` | GET | insCode | `msg[]`: `tseMsgIdn,tseTitle,tseDesc,dEven,hEven,flow` | **پیامِ ناظر** | **MISSING** | — | ✓ 2783 پیام، 2MB |
| tse-md | `Msg/GetMsgByFlow/{flow}/{top}` | GET | flow, top | همان | Announcements | **MISSING** | — | ✓ |
| fima | `Supervision/GetSupervisionListBySourceID/{src}/{idx}` | GET | sourceID, index | `supervision[]`: `reasons,underSupervision,underSupervisionTitle,insCode,instrument{…},userName,insertionDateTime,originUpdateDateTime,additionalInfo` | **وضعیتِ نظارت** | **MISSING** | — | ✓ 16 سطر |
| tse-md, ORBO, fima, mcp | `Codal/GetCodalPublisherBySymbol/{sym}` | GET | symbol | `codalPublisher`: `financialYear,auditorName,website,listedCapital,activitySubject` | Meta | **MISSING** (از codal.ir اسکرپ می‌کنیم) | `codal_fetcher.py` | – |
| tse-md, fima | `Codal/GetPreparedDataByInsCode/{n}/{ins}` | GET | n, insCode | `preparedData[]`: `symbol,name,title,tracingNo,mainTableRowID,publishDateTime_DEven/Gregorian,sentDateTime_Gregorian,hasHtml/Excel/PDF/XMLReport,attachmentID,fileName,fileExtension,contentType` | Structured Codal | **MISSING** (جایگزینِ اسکرپ) | `codal_fetcher.py:1029` | ✓ |
| tse-md, fima | `Fund/GetETFByInsCode/{ins}` | GET | insCode | `etf`: `insCode,deven,hEven,pRedTran,pSubTran,iClose` | ETF NAV | **MISSING** | — | – آزموده نشد |
| fima | `Fund/GetFundInDetail/{flow}` | GET | flow | `fund.fundProfits[], fund.stats[]: {recordDate,navSub,netAsset,…}` | Fund NAV history | **MISSING** | — | ✓ |
| tse-md, ORBO, fima, mcp | `Index/GetIndexB1LastAll/{SelectedIndexes\|All}/{flow}` | GET | scope, flow | `indexB1[]`: `insCode,lVal30,xDrNivJIdx004,xPhNivJIdx004,xPbNivJIdx004,xVarIdxJRfV,indexChange,last,dEven,hEven,c1..c4` | Live | **MISSING** (فقط `GetMarketOverview` + B2History) | `test_tsetmc.py:249-272` | ✓ 7 / 57 سطر |
| Bors, fima, ORBO | `Index/GetIndexB2History/{ins}` | GET | insCode | `indexB2[]`: `dEven,xNivInuClMresIbs,xNivInuPhMresIbs,xNivInuPbMresIbs` | Hist | **EXACT** | `api/market_index.py:33` | – |
| tse-md, fima, ORBO | `Index/GetIndexB1LastDay/{ins}` | GET | insCode | `indexB1[]` همان + `dEven/hEven` | Intraday index | **MISSING** | — | – |
| tse-md, fima, ORBO | `ClosingPrice/GetIndexCompany/{ins}` | GET | insCode | `indexCompany[]`: `instrument{lVal18AFC,lVal30},pClosing,pDrCotVal,priceYesterday,priceChange,priceMin/Max,zTotTran,qTotTran5J,qTotCap` + `relatedCompanyThirtyDayHistory` | Members | **MISSING** | — | – |
| tse-md | `Index/GetInstEffect/0/{flow}/{top}` | GET | flow, top | `instEffect[]`: `instrument{lVal30,lVal18AFC},pClosing,instEffectValue` | **اثر بر شاخص** | **MISSING** | — | README-ONLY |
| tse-md | `ClosingPrice/GetChartData/{ins}/D` | GET | insCode | `closingPriceChartData[]`: `dEven,pDrCotVal,priceFirst,priceMax,priceMin,qTotTran5J` | Hist (سبک) | **MISSING** (معادلِ CSVِ ما) | — | ✓ 5293 سطر |
| tse-md | `old.tsetmc.com/tsev2/excel/MarketWatchPlus.aspx?d=0` | GET | d | .xlsx، 3136 سطر، بدونِ InsCode | Live | **NOT-USEFUL** | — | README-ONLY |
| tse-md | `Instrument/GetInstrumentByFlow/…` | GET | 11 param | – | – | **SOURCE-UNAVAILABLE** | — | ✓ **HTTP 404** |
| **webgw** | `/InstrumentProvider/api/v1/Instrument/CompanyState/fa` | GET | – | `nam,statusCode,vaziyatdesc,lastdatechange,dalils[]` | **علتِ توقف** | **MISSING** | — | ✓ 117KB |
| **webgw** | `/InstrumentProvider/api/v1/MarketWatch/MarketWatchCash/fa` | GET | – | `Items[]`: `instrumentId(ISIN),instrumentName,companyNamePersian,tradeVolume/Value/Count{value,state},lastPrice(Change/Percent){value,state},closingPrice…,highValue,lowValue,yesterdayPrice,sellPrice,buyPrice,marketid,industryid,stateid` | Live | **MISSING** | — | ✓ 887KB |
| **webgw** | `/api/v1/PublicData/MarketDate/fa` | GET | – | `stockTypeId,stockType,openTime,closeTime,isOpen` | Clock/state | **MISSING** (تقویمِ داخلی) | `mstat_engine.in_trading_session` | ✓ |
| **webgw** | `/InstrumentProvider/api/v1/History/Archive/fa?InstrumentId={ISIN}` | GET | ISIN | `devenrlc,highvalue,lowvalue,lastprice…,marketvalue` | Hist + **daily marketvalue** | **SOURCE-UNAVAILABLE** (پاسخِ `[]`) | — | ✓ empty |
| **webgw** | `/InstrumentProvider/api/v1/Instrument/LiveInstrumentByIdQuery/fa` | GET | ISIN | `sharecount,tradeCount/Volume/Value,firstPrice,minValue/maxValue/highValue/lowValue,marketvalue,listOrderBookBuy/Sell,marketCategory` | Live L1 | **SOURCE-UNAVAILABLE** (HTTP 204) | — | ✓ 204 |
| **webgw** | `/InstrumentProvider/api/v1/Instrument/InstrumentClientType/fa` | GET | ISIN | `title,buyAmount,buyPercent,sellAmount,sellPercent` | Live | **SOURCE-UNAVAILABLE** (HTTP 204) | — | ✓ 204 |
| tse-md | `Energy/GetAuctionById`, `GetAuctionTradeById` | GET | AuctionId | – | – | **NOT-USEFUL** | — | README-ONLY |
| tse-md | `Learning/GetLearningTopics` | GET | – | `learningTopics[]` | – | **NOT-USEFUL** | — | README-ONLY |

---

## 9. Field Matrix

### 9.1 تابلو — همان پاسخ، فیلدهایِ دورریختنی

`ClosingPrice/GetMarketWatch` در درخواستِ خودِ ما (LIVE: 3847 سطر) این کلیدها را می‌دهد:

| کلیدِ خام | معنایِ نامدار | در Bors؟ |
| --- | --- | --- |
| `pcl` / `pdv` | قیمتِ پایانی / آخرین قیمت | ✓ `p_closing` / `p_last` |
| `pc` / `pcpc` | تغییرِ درصدیِ پایانی | ✗ (ما `price_change` خام را نگه می‌داریم) |
| `py` / `pf` / `pmn` / `pmx` | دیروز / اولین / کمترین / بیشترین | ✓ |
| `pMin` / `pMax` | سقف/کفِ مجازِ نوسان | ✓ `allowed_min/allowed_max` |
| `qtj` / `qtc` / `ztt` | حجم / ارزش / تعدادِ معامله | ✓ |
| `eps` / `pe` / `bv` / `ztd` / `csv` | EPS / P/E / حجمِ مبنا / کلِ سهام / صنعت | ✓ |
| `marketValue` | ارزشِ بازار | ✓ `market_cap` |
| `blDs[]` | عمقِ ۵ سطحه (`n,qmd,zmd,pmd,pmo,zmo,qmo,rid`) | ✓ (aggregate + JSON) |
| `lva` / `lvc` | نماد / نام | ✓ `instruments.l_val18/l_val30` |
| **`insID`** | **ISIN** | **✗ دور ریخته می‌شود** |
| **`flow`** | **کدِ بازار (1=بورس، 2=فرابورس، …)** | **✗** |
| **`pRedTran`** | **قیمتِ استردادِ NAV (ETF)** | **✗** |
| **`buyOP`** | **قیمتِ صدورِ ETF** | **✗** |
| **`cGrValCot`** | **گروهِ کالایی** | **✗** |
| `dEven` / `hEven` | تاریخ/زمانِ نشست | ✓ |
| `iClose` / `id` | پرچم/شناسهٔ درونی | ✗ (بی‌فایده) |

⇒ **ISIN، flow، pRedTran، buyOP و cGrValCot در همان بایتی‌اند که همین حالا دانلود می‌شود.**
هزینهٔ افزودن = صفرِ درخواستِ شبکه.

### 9.2 ClientType — مبدأ در برابرِ بازسازیِ ما

| مفهوم | SOURCE (LIVE-VERIFIED) | BorsTerminal |
| --- | --- | --- |
| حجمِ خریدِ حقیقی | `buy_I_Volume` (GetClientTypeAll) | `client_type.buy_i_vol` ✓ |
| تعدادِ خریدِ حقیقی | `buy_CountI` | `buy_count_i` ✓ |
| **ارزشِ خریدِ حقیقی** | **`buy_I_Value` — فقط در `GetClientTypeHistory`** | **`mstat_engine.py:761` = `buy_i_vol × vwap`** ✗ |
| **ارزشِ خریدِ حقوقی** | **`buy_N_Value`** | `:763` = `buy_n_vol × vwap` ✗ |
| **ارزشِ فروشِ حقیقی / حقوقی** | **`sell_I_Value` / `sell_N_Value`** | `:762` / `:764` ✗ |
| حجمِ بلوکی | `buy_DDD_Volume` (+`buy_CountDDD`) | `buy_ddd_vol` ✓ |
| `recDate` | کلیدِ تاریخ در مسیرِ History | ✗ (ما `d_even` خودمان را می‌گذاریم) |

**چرا بازسازی غلط است (نه فقط ناخوانا):** `vwap = qTotCap/qTotTran5J` میانگینِ **کلِ** نشست است،
در حالی که هر چهار جریانِ I/N رویِ **قیمت‌هایِ متفاوتی** اتفاق می‌افتند. خطایِ سیستماتیک در جهتِ
`vwap − p_last` با ضریبِ تصحیح گرفته نمی‌شود.

### 9.3 Order book

| سطح | CDN live (`BestLimits`) | inline (`blDs` در تابلو) | History (`BestLimits/{ins}/{date}`) | Bors |
| --- | --- | --- | --- | --- |
| قیمتِ خرید/فروش | `pMeDem` / `pMeOf` | `pmd` / `pmo` | همان | ✓ `buy_q1_px` / `sell_q1_px` |
| حجم | `qTitMeDem` / `qTitMeOf` | `qmd` / `qmo` | همان | ✓ `buy_q1_vol` / `sell_q1_vol` |
| تعدادِ سفارش | `zOrdMeDem` / `zOrdMeOf` | `zmd` / `zmo` | همان | ✓ `buy_q1_cnt` |
| سطح | `number` 1..5 | 5 عنصرِ `blDs[]` | `number` | ✓ aggregate |
| **تاریخچه** | ✗ | ✓ (فقط لحظۀ جاری) | **✓ `bestLimitsHistory[]` با `refID`,`hEven`** | **MISSING** |

### 9.4 واژگانِ فیلتر — raw → canonical → 7 filter → future

```
TSETMC raw fields            Canonical (market_watch ⋈ client_type ⋈ tape_history          7 filter   future
                             ⋈ instruments ⋈ daily_prices)
---------------------------  -------------------------------------------------------------  --------   -------
pl (pdv)                     p_last                                                            f_*        ok
pc (pcl)                     p_closing                                                         f_*        ok
pmax/pmin                    price_max / price_min                                             f_clock    ok
pMin/pMax                    allowed_max / allowed_min                                         f_susp     ok
tvol                         q_tot_tran                                                        f_smart    ok
tno                          z_tot_tran                                                        f_*        ok
tval                         q_tot_cap                                                         –          ok
bvol                         base_vol (instruments)                                            f_clock    ok
Buy_I_Volume / Sell_N_Volume client_type.buy_i_vol / .sell_n_vol                               f_smart    ok
Buy_CountI / Sell_CountI     client_type.buy_count_i / .sell_count_i                           f_smart    ok
Buy_I_Value / Sell_N_Value   **هیچ** → RECONSTRUCTED در mstat_engine                            –          **GAP**
[ih][0..29].QTotTran5J       tape_history.q_tot_tran5j (پنجرۀ ۶۰ نشست)                         f_smart    ok
[ih][0..29].qTotCap          **ستونش در tape_history نیست** (در پاسخِ 24MB هست)                 –          **GAP**
pRedTran / buyOP             **خوانده نمی‌شود** (در پاسخ هست)                                   –          ETF/NAV
flow                         **خوانده نمی‌شود** (در پاسخ هست)                                   –          per-market
cGrValCot                    **خوانده نمی‌شود** (در پاسخ هست)                                   –          commodity
insID (ISIN)                 **خوانده نمی‌شود** (در پاسخ هست)                                   –          webgw joins
qd1..qd5 / zd1..zd5          aggregate + order_book.book_txt خام                                f_roobi    ok
bestLimitsHistory            ✗                                                                  –          queue-dry
trade tape (pTran,qTitTran)  ✗                                                                  –          aggressive-flow
tradeVolume (per-price)      ✗                                                                  –          POC/absorption
```

---

## 10. Formula Matrix

| مفهوم | فرمولِ مبدأ | فرمولِ BorsTerminal | یکی؟ | اگر نه، چرا |
| --- | --- | --- | --- | --- |
| `plp` | `100*(pl−py)/py` سمتِ مرورگر (`market_watch_plus.js:1740`) | `plp_raw = round(100*(pl−py)/py, 2)` در `api/market.py` + `plp_series()` در `tape_flags.py` | ✓ (خام، بدونِ clampِ نمایش) | – |
| `pcp` | `100*(pc−py)/py` (js:1739) | `percent_change` با clampِ ±100 برایِ نمایش | ✓ در مسیرِ فیلتر | clamp فقط نمایشی است |
| `pe` | `pc/eps` سمتِ مرورگر (js:1749)؛ مسیرِ update از `pl/eps` | `instruments.pe` از `pe` خامِ تابلو | ✓ (مبدأ خودش می‌فرستد) | – |
| `plc/plp` وقتی `tno==0` | سمتِ مرورگر روی `"0"` قفل می‌شود (js:1741-1753) | `percent_last` display guard | ✓ (و فیلتر از `plp_raw` رد می‌شود، نه از guard) | – |
| VWAP | ORBO: `Σ(p×v)/Σv` روی تیک (`intra_stats.py:164`) | `qTotCap/qTotTran5J` (`mstat_engine.py:747`) | ✓ **برایِ کلِ نشست** | برایِ جریانِ I/N **نیست** (§9.2) |
| POC | ORBO: `argmax(total_volume)` روی تیک (`footprint.py:225`) | **هیچ** | ✗ | تیک نداریم؛ ولی `Trade/GetTradeVolume` POC را آماده می‌دهد (§18) |
| Delta | ORBO: `Σbuy_vol − Σsell_vol` (`footprint.py:216`) | **هیچ** | ✗ | به طبقه‌بندیِ aggressor نیاز دارد |
| Imbalance | ORBO: `buy ≥ 3×sell` در هر سطح (`footprint.py:276-279`) | **هیچ** | ✗ | آستانۀ 3.0 انتخابِ نویسنده است، نه مبدأ |
| Market cap | fima: `zTitad × ClosePrice` (`TSETMC.py:198`) | `marketValue` خام، وگرنه `pcl×ztd` (`market_cap_src`) | ✓ ما **بهتر** (مبدأ را ترجیح می‌دهیم) | fima شناور را نمی‌بیند |
| تعدیلِ قیمت | ORBO: `adjusted(D)=raw(D)×∏_{date>D} factor`، `factor=pClosing/pClosingNotAdjusted`، `share: old/new`، same-date: share قبل از adjust (`adjustment.py:11-24,48-50`) | infer از شکافِ `<BASE>`/`<CLOSE>` (`api/chart.py:100-158`) | ✗ | مبدأ رویداد دارد و ما نمی‌گیریم (§17) |
| حجمِ رسمیِ نشست | `qTotTran5J` (نه `Σ trade.qTitTran`) — `ENDPOINTS.md:218` | `q_tot_tran` از `qtj` | ✓ | سازگار |
| `buyer_power` (سرانه) | mcp: `(buy_i_vol/buy_count_i)/(sell_i_vol/sell_count_i)` (`variables.py:107,158`) | همان نسبت در `tape_flags`/`mstat` | ✓ | – |
| `idx_pct` | مبدأ `xVarIdxJRfV` را می‌دهد | `_idx_pct` محاسبهٔ محلی (`test_tsetmc.py:239-246`) | ✓ معادل | مبدأ را هم می‌شود گرفت؛ تغییرِ لازم نیست |

هیچ فرمولی در این سند از خودم حدس زده نشده؛ هر سطر یا نقل‌قولِ کدِ مرجع است یا پاسخِ LIVE.

---

## 11. CDN vs WEBGW

| خانواده | CDN | WEBGW | Both | یادداشتِ LIVE |
| --- | --- | --- | --- | --- |
| Board snapshot | ✓ `ClosingPrice/GetMarketWatch` | ✓ `MarketWatch/MarketWatchCash/fa` (+ `Etf/Future/Option/Debt/TradeOption/TALMarket`) | ✓ | هر دو کار کردند؛ webgw کلیدش **ISIN** است و عدد را داخلِ `{value,state}` می‌پیچد |
| **Incremental delta** | ✗ — LIVE: `GetMarketWatch?...&RefID=12000000000` همان 3847 سطرِ کامل را داد (2.5MB) ⇒ `RefID` در JSON API فیلترِ delta **نیست** | ✗ | ✓ **فقط inline** (`old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx`) | delta واقعی: 1942 سطرِ 10فیلده در برابرِ 3847 سطرِ 26فیلده؛ 142KB در برابرِ 1.38MB |
| ClientType حجم/تعداد (امروز) | ✓ `GetClientTypeAll` | ✓ `InstrumentClientType/fa` | ✓ | webgw برایِ نمادِ ما **204** داد |
| **ClientType ارزش (تاریخی)** | ✓ `GetClientTypeHistory` | ✗ (snapshot only) | CDN-only | **P0** |
| Order book امروز | ✓ `BestLimits/{ins}` و `blDs` | ✓ `LiveInstrumentByIdQuery` (L1) | ✓ | webgw 204 داد |
| **Order book تاریخچه** | ✓ `BestLimits/{ins}/{date}` (delta) | ✗ | CDN-only | 21759 سطر/نماد/روز |
| Tick/trade | ✓ `Trade/GetTrade*` | ✗ | CDN-only | – |
| تاریخچۀ روزانۀ کامل + **marketvalue روزانه** | ✓ `GetClosingPriceDailyList` (بدونِ mcap) | ✓ `History/Archive/fa` (با `marketvalue`) | ✓ | webgw برایِ `IRO1IKCO0008` `[]` داد ⇒ **UNAVAILABLE** |
| وضعیتِ نماد / تعلیق | ✓ `MarketData/GetInstrumentState` (`cEtaval`, `underSupervision`) | ✓ `Instrument/CompanyState/fa` (**`dalils[]` = علتِ توقفِ فارسی**) | ✓ | **متنِ علت فقط در webgw است** |
| شاخص | ✓ `Index/GetIndexB1*`, `B2History` | ✓ `MarketSummary/fa`, `BubbleChart/fa`, `MarketMapNew/fa`, `TradingView/history` | ✓ | – |
| تقویم/ساعتِ بازار | ✓ `StaticData/GetTime` (متن) | ✓ `PublicData/MarketDate/fa` (`isOpen`, `openTime`, `closeTime`) | ✓ | webgw ساختارمندتر |
| تابلوی ETF/اختيار/آتی/صکوک | ✓ `paperTypes[]` در همان GetMarketWatch | ✓ تب‌هایِ جدا | ✓ | ما همه را در یک درخواست می‌گیریم |
| TAL Market | ✗ | ✓ `MarketWatchTALMarket/fa` (README: فقط 12:45–13:00) | WEBGW-only | آزموده نشد |
| جست‌وجویِ صفحه‌بندی‌شده | ✓ `GetInstrumentSearch` | ✓ `InstrumentShortcut/fa` | ✓ | – |

**چهار حکمِ معماری:**
1. **webgw جای CDN را نمی‌گیرد** و بالعکس؛ هر کدام چیزهایی دارند که دیگری ندارد.
2. **تنها چیزی که فقط webgw دارد و به آن نیازِ واقعی داریم `CompanyState/fa → dalils` است**
   («علت توقف»). بقیۀ webgw یا 204/`[]` بود یا معادلِ CDN دارد.
3. **webgw با ISIN کلید می‌خورد، نه `insCode`.** ما ISIN را **همین حالا در پاسخِ تابلو داریم**
   (`insID`) و دور می‌ریزیم ⇒ پیش‌شرطِ هر کارِ webgw، ذخیرۀ `insID` است (§15).
4. **ریسک:** `ENDPOINTS.md:544` می‌گوید webgw از IPِ غیرایرانی بلاک است؛ من از همین ماشین گرفتم.
   اگر بیلد/CI رویِ GitHub Actions بدود، webgw آنجا **نمی‌آید** ⇒ هر چیزی که به webgw گره
   بخورد باید optional با fallback باشد.

---

## 12. ClientType Gap

**وضعیتِ امروز:** حجم و تعداد از `GetClientTypeAll` (SOURCE-NATIVE)؛ ارزش از `volume × vwap`
(RECONSTRUCTED) در `mstat_engine.py:761-765`. جدولِ `client_type` هیچ ستونِ ارزشی ندارد
(DDL `test_tsetmc.py:936-941`). 77614 سطر / 33 روز.

**آنچه مبدأ می‌دهد (LIVE-VERIFIED، `خودرو`، insCode 65883838195688438):**

| dEven | `buy_I_Value` | `buy_N_Value` | `sell_I_Value` | نتیجه |
| --- | --- | --- | --- | --- |
| 20261004 | 9795900492781 | 1424869091632 | 8377684161902 | 200 |
| 20261003 | 15077473490654 | 1392443680230 | 11688257414754 | 200 |
| 20260930 | 4963917011250 | 462612014276 | 2756745617188 | 200 |
| 20260922 | 1474478444900 | 3303972910895 | 3664847666393 | 200 |
| 20260901 | 6696491779469 | 3582319414306 | 8058326376259 | 200 |
| 20260701 | 3439942213720 | 864633133470 | 3229993616270 | 200 |
| **20261005 (امروز)** | — | — | — | **HTTP 500** |
| 20261002 (جمعه/تعطیل) | — | — | — | HTTP 500 |
| 20260101 | — | — | — | HTTP 500 |

**سه حکمِ عملیاتی:**
1. **امروز را نمی‌دهد.** مسیرِ History برایِ نشستِ جاری 500 می‌دهد ⇒ ارزشِ امروز باید همان
   `GetClientTypeAll` بماند و **نباید** ادعا کرد source-native است. یعنی معماریِ دوگانه:
   *امروز = reconstructed (با برچسبِ صریح)، دیروز‌به‌بعد = source*. (§22.2)
2. **retention دستِ‌کم تا `20260701` (≈ ۳ ماه) زنده است** ⇒ backfillِ ۳ ماهۀ اولیّه شدنی است.
   «عقب‌تر از این» آزموده نشد؛ 20260101 شکست ولی ممکن است تعطیل/رویداد بوده باشد.
3. **هزینه:** یک درخواست به ازایِ هر (نماد × روز). برایِ 5669 نماد × ۳۰ روز ≈ 170k درخواست ⇒
   **شدنی نیست**. الگوی شدنی: فقط نمادهایِ دارایِ حجمِ معنادار در `market_watch`، فقط T نشستِ
   اخیر (T=5..20)، با همان polite-get ladderِ `test_tsetmc.py:839-885` (429 ⇒ `Retry-After`،
   وگرنه cooldownِ 60→300→600s).

**تعارضِ واژگانیِ مستند در مرجع‌ها:**

| منبع | `I` | `N` |
| --- | --- | --- |
| fima `TSETMC.py:159-165` | Institutional = **حقوقی** | Retail = **حقیقی** |
| 5j9 `instruments.py:734-735` | natural = **حقیقی** | legal = **حقوقی** |
| tsetmc-mcp `docs/endpoints.md:30` | individual = **حقیقی** | legal = **حقوقی** |
| **BorsTerminal `mstat_engine.py:761-764`** | `buy_i_vol → retail_buy` = **حقیقی** | `buy_n_vol → inst_buy` = **حقوقی** |

⇒ **fima وارونه است**؛ نگاشتِ ما با 5j9 و tsetmc-mcp یکی است و — مهم‌تر از همه — با
**خروجیِ زندهٔ فیلترِ TSETMC** در `docs/TA-PARITY-1405-07-04.md` راستی‌آزمایی شده. پس
`Buy_I_Volume > 0.5·tvol && Sell_N_Volume > 0.5·tvol` همان «کد به کدِ حقوقی به حقیقی» است.
**تغییری نمی‌کند.**

**حکم:** `ADD` (P0).

---

## 13. BestLimits Gap

**وضعیتِ امروز:** `blDs` از همان `GetMarketWatch` (withBestLimits=true) ⇒ ۵ سطح، **snapshot**.
`order_book` کلیدش `ins_code` تنهاست (`test_tsetmc.py:426-428`) ⇒ یک سطرِ جاری به ازایِ نماد؛
هیچ تاریخچه‌ای. تنها ردِّ زمانی، aggregate در `mstat_snap(d_even,h_even,agg)` است
(DDL `test_tsetmc.py:963-965`) که هر ۳۰ ثانیه نوشته می‌شود.

**مبدأ (LIVE-VERIFIED):** `BestLimits/{insCode}/{dEven}` ⇒ `bestLimitsHistory` با **21759 سطر**
برایِ خودرو در 20261004 (4.2MB). هر سطر: `refID, idn, dEven, hEven, number, pMeDem, qTitMeDem,
zOrdMeDem, pMeOf, qTitMeOf, zOrdMeOf, title, insCode`.

**Snapshot یا delta؟ — delta.** سه شاهد:
- CODE-VERIFIED در ORBO: docstringِ `clients/intraday.py:119-123` — «This is an incremental
  UPDATE stream, not a sequence of full 5-level snapshots — most rows touch a single depth
  level only».
- LIVE-VERIFIED: در سطرهایِ نمونه، `number=3` و `number=2` با `hEven=60128` **هر دو**
  `pMeOf=0, qTitMeOf=0, zOrdMeOf=0` داشتند ⇒ سطر فقط سمتِ demand را به‌روز کرده؛ در snapshotِ
  کامل، سطحِ ۲ نمی‌تواند صفر باشد.
- LIVE: `dEven` و `insCode` در همان سطرهایِ نمونه `0/null` بود ⇒ سطر به رویدادِ کلید می‌خورد،
  نه به نماد.
- 20261001 ⇒ `list[0]` خالی (تعطیل/بی‌داده)؛ پس خالی‌بودن هم حالتِ عادی است.

**Reconstruction لازم است.** الگوریتمِ لازم (مستند، **نه پیاده‌سازی‌شده**): sort بر اساس `refID`
(ORBO `transformers.py:298` همین را می‌کند)، آنگاه per-level last-write-wins روی
`(pMeDem,qTitMeDem,zOrdMeDem)` و `(pMeOf,qTitMeOf,zOrdMeOf)`؛ هر `hEven` یک نقطۀ بازسازی.
ORBO صریحاً می‌گوید «Full point-in-time book reconstruction is left to a future engine»
(`intraday.py:122-123`) ⇒ **هیچ‌یک از پنج مرجع این را پیاده نکرده**؛ ریسکِ پیاده‌سازی رویِ دوشِ
خودمان است.

**هزینه:** 4.2MB × ~5700 نماد برایِ یک روز ⇒ صدها گیگ. پس: (الف) فقط on-demand برایِ نمادی که
کاربر باز می‌کند؛ (ب) یا فقط نمادهایِ دارایِ سیگنالِ FTS؛ (ج) یا خلاصه‌سازیِ بلافاصله پس از
ساختِ snapshot در هر `hEven` و دور ریختنِ خام.

**حکم:** `INVESTIGATE` (P1). طبقِ brief فقط مستند می‌شود؛ implementation نه.

---

## 14. MarketWatch Incremental Gap

**وضعیتِ امروز (CODE-VERIFIED):** دو حلقه، هر دو snapshotِ کامل:
- `app.py:232-246` → `api/_sync_market.py:18-47` → `test_tsetmc.main()` هر **۹۰ ثانیه**
  (gate: `mstat_engine.in_trading_session`).
- `app.py:257-284` → `test_tsetmc.tick_live()` (`test_tsetmc.py:1557-1659`) هر **۵ ثانیه**؛
  یک درخواستِ کامل، سپس diff محلی و نوشتنِ delta با `market_state.py`.

یعنی «incremental» ما **سمتِ نوشتن** است، نه سمتِ خواندن.

**پروتکلِ واقعیِ TSETMC (LIVE-VERIFIED در این دور؛ کدِ مرجع 5j9 `market_watch.py`):**

```
GET https://old.tsetmc.com/tsev2/data/MarketWatchInit.aspx?h=0&r=0
  → 5 بخشِ جدا‌شده با '@':
     [0] هدر/پیام             '277321,2062005,769133'
     [1] FastView (16 خانه)   '05/07/13 16:27:52,N,7790010.31,
                               <div class='pn'>6833.63</div> 0.09%,
                               225573311752876481.00,93962323092.00,
                               498749158935127.00,1805940,N,25592375912.00,
                               1695369383411481.00,654294,N,136116929.00,
                               21609208428000.00,395189,'
     [2] 3847 سطر × 26 فیلد   (حالتِ کاملِ هر نماد)
     [3] 18244 سطر × 8 فیلد   (عمقِ صف)
     [4] refID                '16064701076'

GET https://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx?h=<5*(heven//5)>&r=<25*(refID//25)>
     [2] 1942 سطر × **10 فیلد**  (فقط تغییریافته‌ها)
     [3] 2 سطر (deltaهایِ صف)
     [4] refIDِ تازه: '16064785236'
```

گِردکردنِ cursor (`5*floor(heven/5)` و `25*floor(refID/25)`) **عینِ JSِ خودِ سایت** است
(`market_watch_plus.js:1596-1597`) و در کدِ 5j9 بازتولید شده (`market_watch.py:241-243`).
قاعده: `heven==0` ⇒ Init، وگرنه Plus (`js:1593`). سایت هر ۱ ثانیه می‌زند و وقتی تب غیرفعال است
هر ۵ بار یک بار (`js:1583-1590`).

**آیا CDN هم delta می‌دهد؟ نه.** LIVE: `ClosingPrice/GetMarketWatch?...&RefID=12000000000` ⇒
همان 3847 سطرِ کامل (2.5MB).

**ارزشِ واقعی و صادقانه:**
- ترافیک: 2.5MB → 142KB در هر tick (LIVE). برایِ tickِ ۵ ثانیه‌ای ≈ **۱۷ برابر کمتر**.
- **ولی:** فیلدهایِ delta فقط ۱۰ تا هستند (`ins_code, heven, pf, pc, pl, tno, tvol, tval,
  pmin, pmax`). `blDs`، `pMin/pMax` مجاز، `eps/pe/bv/ztd/csv` در delta **نیستند** ⇒ باید
  snapshotِ اولیه نگه داشته شود و delta رویش سوار شود؛ یعنی یک **حالتِ در حافظه** لازم است،
  نه فقط یک endpointِ دیگر.
- `old.tsetmc.com` دامنه‌ای است که در پیامِ رسمیِ خودِ TSETMC (LIVE، `Msg/GetMsgByFlow`)
  جایگزینش اعلام شده: «در صورت عدم دسترسی به www.tsetmc.com از www.tsetmc.ir استفاده فرمایید،
  همچنین old.tsetmc.com → old.tsetmc.ir». ⇒ **آدرس باید پیکربندی‌پذیر باشد، نه hard-code.**

**حکم:** `DEFER` (P1) — ارزشِ بهینه‌سازی دارد، ولی correctnessِ فعلی را نمی‌نجات می‌دهد و
حالتِ درحافظه + وابستگیِ دامنه‌ای ریسکِ تازه وارد می‌کند. اول P0ها.

---

## 15. Instrument Gap

**وضعیتِ امروز:** `instruments` = `ins_code, l_val18, l_val30, sector_code, sector_name,
total_shares, eps, pe, base_vol, updated_at, paper_type`. پر می‌شود از `GetMarketWatch`
(`lva/lvc/csv/ztd/eps/pe/bv`) + `StaticData/GetStaticData` (نامِ صنعت) + اسکنِ `paperTypes`.

**آنچه مبدأ دربارهٔ یک نماد می‌داند و ما نداریم (LIVE-VERIFIED):**

| فیلد | مسیر | چرا مهم |
| --- | --- | --- |
| `cIsin` / `instrumentID` | `GetInstrumentIdentity` **و `insID` در همان `GetMarketWatch`** | کلیدِ webgw؛ پیوندِ بیرونی؛ پایدار در برابرِ تغییرِ نماد |
| `subSector.cSoSecVal / lSoSecVal` | `GetInstrumentIdentity` | صنعتِ دوم؛ ما فقط `IndustrialGroup` داریم |
| `kAjCapValCpsIdx` | `GetInstrumentInfo` | **free float** — بدونِ آن market-cap شناور محاسبه نمی‌شود |
| `yVal` / `cgrValCot(+Title)` | `GetInstrumentIdentity` | نوعِ ورقه و گروهِ کالایی (ETF/اختيار/آتی/صکوک را جدا می‌کند) |
| `contractSize`, `nav`, `etfIssuedUnit`, `pRedTran`, `buyOP` | `GetInstrumentInfo` / تابلو | ETF و اختيار |
| `minWeek/maxWeek/minYear/maxYear`, `qTotTran5JAvg` | `GetInstrumentInfo` | زمینهٔ حجم/قیمت |
| `faraDesc`, `sourceID`, `flowTitle` | `GetInstrumentInfo` | توضیحِ فرابورسی/منبع |
| `zTitad` **به‌تاریخِ هر روز** | `Instrument/GetInstrumentHistory/{ins}/{date}` | market-cap تاریخچۀ درست (با سهامِ آن روز) |
| `psGelStaMax/Min` به‌تاریخ | `MarketData/GetStaticThreshold/{ins}/{date}` | آستانۀ مجازِ آن روز (ما فقط مقدارِ امروزِ تابلو را داریم) |
| `cEtaval/cEtavalTitle/underSupervision/realHeven` | `MarketData/GetInstrumentState/{ins}/{date}` | وضعیتِ نماد (§17) |
| `insCode2/3/4` (بلوکی/جبرانی/عمده) | `GetInstrumentSearch` (5j9 `instruments.py:1155-1179`) | کدهایِ معاملاتیِ موازی |
| `dataType/dataTypeDesc/dataValue` (88 سطر) | `MarketData/GetInstrumentStatistic` | آمارِ آمادهٔ مبدأ، از جمله «میانگین ارزش معاملات در 3/12 ماه گذشته» |

**تطبیق با Symbol model:** نامِ کلیدِ ما در فرانت `frontend/src/shared/types/marketRow.ts` است؛
هیچ‌یک از فیلدهایِ بالا در `MarketRow` نیست. ارزان‌ترین گامِ ممکن: **`insID` را از همان پاسخِ
تابلو در `instruments.isin` بنویس** — صفرِ درخواستِ تازه.

**حکم:** `ADD` (P1 برایِ ISIN — تقریباً رایگان)، `INVESTIGATE` (P2 برایِ free-float و
`GetInstrumentInfo`).

---

## 16. Shareholder Gap

**وضعیتِ امروز:** **MISSING کامل.** grep برایِ `shareholder|سهامدار|Holder` فقط متنِ UI می‌دهد؛
نه endpoint، نه جدول.

**آنچه مبدأ می‌دهد (LIVE-VERIFIED):**

| مسیر | کلید | فیلدها | حجمِ آزموده |
| --- | --- | --- | --- |
| `Shareholder/{ins}/{date}` | `shareShareholder` | `shareHolderName, numberOfShares, perOfShares, change, changeAmount, shareHolderID, shareHolderShareID, cIsin, dEven` | 17 سطر برایِ خودرو |
| `Shareholder/GetInstrumentShareHolderLast/{ins}` | `shareHolder` | همان | 17 سطر |
| `Shareholder/GetShareHolderChanges/false` | `shareHoldersChanges` + `dates` | `insList`, `name` + 5 تاریخ | **566 دارندۀ تغییریافته + 5 روز** |
| `Shareholder/GetShareHolderCompanyList/{id}` | – | – | آزموده نشد |

**نکتۀ کلیدی:** `change` و `changeAmount` **حرکت** را می‌دهند. fima این دو را دور می‌ریزد
(`TSETMC.py:117`) و فقط سطح را نگه می‌دارد ⇒ «تغییرِ مالکیت» از fima قابلِ ساخت نیست، از مبدأ
بله. `GetShareHolderChanges` هم **بازارِ کامل را در یک درخواست** می‌دهد — یعنی سرنشۀ
«تغییرِ سهامدارِ عمده» با **یک درخواست در روز** شدنی است، نه با fan-out.

**ارزش برایِ FTS:** هیچ بندِ FTSی سهامدار را نام نمی‌برد. طبقِ brief هم «هنوز UI نساز»؛ این فقط
یک data capability است.

**حکم:** `DEFER` (P2).

---

## 17. Corporate Action Gap

**وضعیتِ امروز (CODE-VERIFIED):** رویدادِ تعدیل **استنتاج** می‌شود، از شکافِ `<BASE>` در برابرِ
`<CLOSE>` در CSV و از سطرهایِ حجم-صفر (`api/chart.py:100-158`)، و در
`adjust_events(symbol, date, ratio, source)` + `adjust_verdict(symbol, source, checked_at)`
می‌نشیند (DDL `api/chart.py:165-171`). خودِ کد صریح می‌گوید: «افزایشِ سرمایه، آورده/حق‌تقدم،
سودِ نقدی… هیچ‌یک از این‌ها درِ فیدِ TSETMC و درِ هیچ جدولِ این بانک نیست»
(`api/chart.py:173-177`).

**آن جمله دیگر درست نیست** (LIVE-VERIFIED در این دور):

| مسیر | کلید | فیلدها |
| --- | --- | --- |
| `ClosingPrice/GetPriceAdjustList/{ins}` | `priceAdjust` | `dEven, insCode, pClosing, pClosingNotAdjusted, corporateTypeCode, instrument{…}` — 11 رویداد برایِ خودرو |
| `ClosingPrice/GetPriceAdjustByFlow/{flow}/{size}` | `priceAdjust` | همان، **بازارِ کامل** (fima size=100000 می‌گیرد) |
| `Instrument/GetInstrumentShareChange/{ins}` | `instrumentShareChange` | `dEven, idn, insCode, lVal18AFC, lVal30, numberOfShareOld, numberOfShareNew` — 6 رویداد |
| `Instrument/GetInstrumentShareChangeByFlow/{flow}/{days}` | همان | **2395 رکورد در یک درخواست** |

`corporateTypeCode` هم در پاسخ هست — اما **همیشه null**. سنجشِ زنده (۱۴۰۵-۰۷-۱۳، چهار
درخواست، `_audit/corporate_type_code_probe.json`): ۴۰۱۸ ردیفِ `priceAdjust` از هر دو flow و
از `GetPriceAdjustList`، صفر ردیفِ غیرnull. مسیرِ `GetInstrumentShareChangeByFlow` اصلاً
هیچ فیلدِ نوعی ندارد. پس این «کدِ رمزگشایی‌نشده» نیست، **فیلدِ خالی** است: چیزی برایِ
decode کردن وجود ندارد، و هر نوعِ رویدادی که از آن ساخته می‌شد اختراع می‌بود.

**مقایسه با ORBO:** ORBO دقیقاً همین دو مسیر را می‌گیرد (`PRICE_ADJUST`،
`GetInstrumentShareChange`) و فرمولِ backward-cumulative می‌سازد (§4). یعنی **داده هست،
الگوریتم هم در مرجع هست، ما هیچ‌کدام را نداریم و به‌جایش از شکافِ سریِ زمانی حدس می‌زنیم.**

**چرا P0 است:** هر چیزی که رویِ کندلِ تعدیل‌شده می‌نشیند — MA52 هفتگی، MA100 روزانه، سقفِ سوم،
CHOCH، فیبوناتچی، Jet رویِ «سقفِ تاریخی» — با رویدادِ تعدیلِ اشتباه جابه‌جا می‌شود.
استنتاجِ شکاف، رویدادهایِ هم‌تاریخِ (سود + افزایشِ سرمایه) را **نمی‌تواند** جدا کند؛ ORBO با
`bisect_right` و اولویتِ same-date (share قبل از adjust) می‌تواند.

**قیدِ شکست‌پذیر:** `price_basis.py` و `candle_contract.py` فریزند. هر تغییرِ تعدیل باید **جدای
از** آن قرارداد و با گاردِ برابریِ قبل/بعد انجام شود، وگرنه parity guard سبز می‌ماند ولی
اعدادِ منتشرشده جابه‌جا شده‌اند. (این هشدارِ معماری است، نه دستورِ کارِ این دور.)

**حکم:** `ADD` (P0) — واکشیِ دو مسیرِ by-flow و ذخیره در جدولِ رویداد؛ **بدونِ تغییرِ منطقِ کندل
در این دور**.

---

## 18. Trade / Footprint Gap

**وضعیتِ امروز:** هیچ دادهٔ تکی. فقط aggregateهایِ نشست (`qtj`, `qtc`, `ztt`) + عمقِ ۵ سطحه +
ضرب‌آهنگِ snapshotِ ۵ ثانیه‌ای. `order_book` یک سطرِ جاری دارد.

**آنچه مبدأ می‌دهد (LIVE-VERIFIED، خودرو):**

| مسیر | کلید | رکورد | حجم |
| --- | --- | --- | --- |
| `Trade/GetTrade/{ins}` | `trade` | **27653** | 5.5MB |
| `Trade/GetTradeHistory/{ins}/{date}/false` | `tradeHistory` | **28943** (= `zTotTran`ِ آن روز دقیقاً) | 5.8MB |
| `Trade/GetTradeHistory/.../true` | همان | combine-same-price (معنایش در ORBO مستند نیست: `intraday.py:96-100`) | – |
| `Trade/GetTradeIntraDay/{ins}` | `tradeIntraDay` | **105** سطر `hEven,openPrice,closePrice,maxPrice,minPrice,volume` | 11KB |
| `Trade/GetTradeVolume/{ins}` | `tradeVolume` | **30** سطح `pTran,qTitTran,firstTradeTime,lastTradeTime` | 3.4KB |

فیلدهایِ سطرِ تیک: `nTran, hEven, pTran, qTitTran, canceled, qTitNgJ, iSensVarP, pPhSeaCotJ,
pPbSeaCotJ, iAnuTran, xqVarPJDrPRf, insCode, dEven`. **هیچ کدِ خریدار/فروشنده در تیک نیست** —
به همین دلیلِ تیک‌داده باید aggressor را **استنتاج** کرد (Lee-Ready در ORBO).

**سه یافته که تصمیم را عوض می‌کند:**
1. **تیک‌داده نیازی به streaming ندارد.** کلِ روز با **یک GET** می‌آید ⇒ «footprint تاریخی،
   پس‌از‌بسته‌شدنِ بازار» بدونِ زیرساختِ زنده شدنی است — چیزی که ORBO خودش persist نمی‌کند.
2. **`Trade/GetTradeVolume` یک volume-profile آماده است، 3.4KB.** POC، توزیعِ حجم‌به‌قیمت و
   «کجا صف خشک شد» **بدونِ تیک و بدونِ Lee-Ready** از این درمی‌آید. نسبتِ ارزش/هزینه‌اش از کلِ
   ORBO بهتر است.
3. **`Trade/GetTradeIntraDay` 105 مینی‌بار می‌دهد، 11KB.** VWAPِ درون‌روز و شکلِ جریانِ پول
   بدونِ 5.8MB تیک.

**طبقه‌بندیِ قابلیت‌ها (brief §9):**

| قابلیت | نیاز | وضعیتِ ما |
| --- | --- | --- |
| trade tape | تیک | **MISSING** (منبع ✓) |
| tick-level history | تیک | **MISSING** (منبع ✓) |
| trade classification | تیک + عمقِ زمان‌دار | **MISSING** (هر دو منبع ✓، reconstruction لازم) |
| aggressive buy / sell | Lee-Ready | **MISSING** — فرمولِ مبدأ هیچ‌وقت نبود؛ ORBO استنتاج می‌کند |
| delta | طبقه‌بندی | **MISSING** |
| footprint | تیک + زمان | **MISSING** — و در ORBO هم محورِ زمان ندارد (§4) |
| POC | `GetTradeVolume` | **MISSING** — ارزان‌ترین گامِ این خانواده |
| imbalance | آستانۀ دلخواه (3.0) | **MISSING** — آستانه از خودِ مرجع است، نه مبدأ |

**چرا P2 و نه P0:** هیچ‌یک از این‌ها ورودیِ FTS نیست. درختِ تکنیکالِ `FTS.CHART_3:2` رویِ
کف/سقف، MA، RSI، آستانه و عمقِ صف است، نه delta. اضافه‌کردنشان «به‌خاطرِ وجود در پروژهٔ خارجی»
می‌شد — همان چیزی که brief §21 منع می‌کند.

**قیدِ صریح:** `imbalance_ratio=3.0` و کفِ «10» در ORBO **آستانه‌هایِ اختراعیِ نویسنده** هستند
(CODE-VERIFIED: `footprint.py:132-133,270-271`). هیچ آستانۀ تازه‌ای پیشنهاد نمی‌شود.

**حکم:** `INVESTIGATE` (P2) برایِ POC از `GetTradeVolume`؛ `DEFER` (P2) برایِ تیک/footprint؛
`IGNORE` برایِ imbalance با آستانۀ 3.0.

## 19. Filter Data-Layer Gap

**زنجیرۀ هدف:** `TSETMC Raw Fields → Canonical Filter Snapshot → Existing 7 Filters → Future
Filters` (نقشۀ کامل در §9.4).

**Canonical snapshotِ فعلی** = `market_watch` (تابلو) ⋈ `client_type` ⋈ `tape_history` (پنجرۀ
`[ih]`) ⋈ `instruments` (eps/pe/base_vol/sector) ⋈ `daily_prices`. نگاشتِ متغیرها در
`tape_flags.py:16-20` مستند است (`pl=pdv`, `pc=pcl`, `tvol=qtj`, `tno=ztt`, `tmin=pMin`,
`bvol=bv`, `[ih][k]` = k-امین نشستِ منتشرشده).

**هفت فیلترِ فعلی و نیازِ داده‌ایِ هر کدام:**

| فیلتر | فرمول (از سند) | فیلدها | تأمین |
| --- | --- | --- | --- |
| clock | – | `pMin/pMax`, `bv`, `qtj` | ✓ |
| susp | – | `allowed_min/max`, `ztt` | ✓ |
| jet | `plp>0 && pl>=pc` + ladder | `plp_raw`, `p_closing`, `p_last`, `tape_history` | ✓ (`plp_series()` در `tape_flags.py`) |
| roobi | `tvol>10` + `buy_i>0.5·tvol` + خشک‌شدنِ صف | `q_tot_tran`, `buy_i_vol`, `blDs` | ✓ |
| noqteh | – | `z_tot_tran`, `q_tot_tran` | ✓ |
| **smart** | `tvol>1.5·Σ[ih][0..29]/30 && Buy_I_Volume/Buy_CountI ≥ Sell_I_Volume/Sell_CountI && pl≥pc && plp>0` | `tape_history.q_tot_tran5j`, `client_type.buy_i_vol/buy_count_i/sell_i_vol/sell_count_i`, `p_last`, `p_closing`, `plp_raw` | ✓ |
| **legal** | `Buy_I_Volume > 0.5·tvol && Sell_N_Volume > 0.5·tvol` | `client_type.buy_i_vol`, `sell_n_vol`, `q_tot_tran` | ✓ |

**parityِ این هفت با ExecFilterِ سایت در `docs/TA-PARITY-1405-07-04.md` §5–§6 و
`tools/tse_live_filter_parity.py` با درخواستِ هم‌زمانِ لحظه‌ای ثابت شده — در این دور بازتولید
نمی‌شود.** هیچ threshold تازه‌ای هم پیشنهاد نمی‌شود.

**گپ‌هایِ لایۀ دادهٔ فیلتر (نه گپِ خودِ فیلتر):**

| فیلدِ فیلترِ TSETMC | در پاسخِ ما هست؟ | در canonical هست؟ | نوعِ گپ |
| --- | --- | --- | --- |
| `Buy_I_Value`, `Sell_N_Value` (ارزش) | ✓ در `GetClientTypeHistory` | ✗ | **RECONSTRUCTED** (§12) |
| `pRedTran`, `buyOP` | ✓ در همان `GetMarketWatch` | ✗ خوانده نمی‌شود | **نخواندن** — صفرهزینه |
| `flow` | ✓ در همان `GetMarketWatch` | ✗ | **نخواندن** — صفرهزینه |
| `insID` (ISIN) | ✓ در همان `GetMarketWatch` | ✗ | **نخواندن** — صفرهزینه |
| `cGrValCot` | ✓ در همان `GetMarketWatch` | ✗ | **نخواندن** — صفرهزینه |
| `pcpc` (تغییرِ درصدیِ پایانیِ آماده) | ✓ | ✗ (محاسبهٔ محلی) | بی‌اهمیت |
| `qd1..qd5`, `zd1..zd5` (تعدادِ سفارشِ هر سطح) | ✓ در `blDs` | aggregate + JSON خام | ✓ ولی برایِ فیلترهایِ «تعدادِ سفارش» باید ستون شود |
| `bestLimitsHistory` | ✓ CDN | ✗ | §13 |
| `tradeVolume` (حجم‌به‌قیمت) | ✓ CDN | ✗ | §18 |
| `[ih]` برایِ `priceMin/priceMax/qTotTran5J` | ✓ `tape_history` | ✓ | – |
| `[ih]` برایِ **`qTotCap`** (ارزشِ پنجره) | ✓ در همان پاسخِ 24MB | **✗ فقط `q_tot_tran5j` ذخیره می‌شود** | **گپِ واقعیِ پنجره** |

**آخرین سطر مهم است:** `tape_history` تنها `price_min, price_max, q_tot_tran5j` دارد
(DDL `test_tsetmc.py:488-498`). اگر روزی فیلتری بخواهد «میانگینِ **ارزشِ** معاملاتِ ۳۰ روز» را
بگیرد، همان endpointِ `[ih]` این عدد را دارد (`qTotCap`) و ما دور ریخته‌ایم. **افزودنش یک
ستونِ NULL-able است، نه یک درخواستِ اضافه** — چون داده در همان پاسخِ 26.8MB/24MB حاضر است.

**تعارضِ نام‌گذاریِ مرجع‌ها (برایِ اینکه چه چیزی را «فیلترِ TSETMC» بنامیم):**
tsetmc-mcp `pmax/pmin` را «بیشترین/کمترینِ روز» می‌گیرد و `tmax/tmin` (آستانه) را **UNSUPPORTED**
اعلام می‌کند (`variables.py:43-44,92-93`)؛ 5j9 `pmax/pmin` را روز و `tmax/tmin` را آستانه می‌گیرد
(`market_watch.py:48-49,64-65`)؛ ما `price_min/price_max` (روز) و `allowed_min/allowed_max`
(آستانه) — **درست مثلِ 5j9**. ⇒ نگاشتِ ما صحیح و مرجعِ mcp ناقص است.

**حکم:** `ADD` (P1) برایِ ستون‌هایِ صفرهزینه (`isin`, `flow`, `p_red_tran`, `buy_op`,
`c_gr_val_cot`, `tape_history.q_tot_cap`)؛ `KEEP` برایِ هر هفت فیلتر.

---

## 20. Existing Parity Coverage — آنچه دوباره انجام **نمی‌شود**

| کارِ انجام‌شده | سند/ابزار | پوشش |
| --- | --- | --- |
| برابریِ زندهٔ ۷ فیلتر با ExecFilterِ سایت در یک لحظه | `docs/TA-PARITY-1405-07-04.md` §5–§6، `tools/tse_live_filter_parity.py`، `_audit/tse_live_parity_0713_*.json` | source→universe→timestamp→fields→formula→symbol-set→UI؛ ۵ snapshot؛ ریشۀ `plp` پیدا و رفع شد |
| برابریِ پنجرۀ `[ih]` | همان، بخشِ `tape_history` + استثنای ExecFilter برایِ <۳۰ نشست | ✓ |
| برابریِ طبقۀ روند/دروازه با تمامِ منابع | `docs/fts-notes/FTS-TREND-CLASSIFIER-AUDIT-1405-07-13.md`، `dev/fts_trend_fixtures_v1075.py` (19/19) | BULL/BEAR/RANGE + تلهٔ «روزانۀ صعودی زیرِ هفتگیِ نزولی ⇒ REJECT» |
| ممیزیِ شواهدِ PDF | `docs/fts-notes/TECHNICAL-PDF-EVIDENCE-AUDIT-1405-07-13.md` | ۱۴ فایل، صفحۀ‌به‌صفحۀ، تعارضِ FTS صفر |
| برابریِ چهارصفحۀ چارت | `docs/CHART-FOUR-PAGES-PARITY.md` | لنگرهایِ `api/chart.py` |
| برابریِ تعدیلِ صفرحجم | `docs/fts-notes/ADJUSTMENT-PHASE-A.md`، `_audit/adjust_zero_volume_probe.py` | – |
| برابریِ اندیکاتور | `docs/INDICATOR-PARITY-1405-07-14.md` | – |
| برابریِ Market/TradersArena | `docs/TA-PARITY-1405-07-04.md` §5، `dev/watchlist_matrix_v973.py` | گاردِ determinism با snapshot از sqlite backup API |
| اسنپ‌شات‌هایِ میانه/نهایه/پس‌از‌بستن | commit `92831a7`، `docs/TA-PARITY-1405-07-04.md` §6 | میزِ نهاییِ هفت‌فیلته |

**گپ‌هایِ تازهٔ این سند که آن پوشش ندارد:** ارزشِ ClientType (§12)، عمقِ صفِ تاریخی (§13)،
deltaِ تابلو (§14)، رویدادِ تعدیل (§17)، علتِ توقف/نظارت/پیامِ ناظر (§21 P0)،
ISIN/flow/pRedTran/buyOP/cGrValCot در پاسخِ موجود (§15/§19)، `tape_history.q_tot_cap` (§19).

---

## 21. P0 / P1 / P2 / P3 Recommendations

سؤالِ brief §21 برایِ هر سطر جواب داده شده: «Does BorsTerminal actually need this?» با
`KEEP / ADD / INVESTIGATE / DEFER / IGNORE`.

### P0 — مستقیماً رویِ TSETMC parity / TradersArena parity / correctness / FTS input / integrity

| # | گپ | چرا P0 | حکم |
| --- | --- | --- | --- |
| P0-1 | **ارزشِ حقیقی/حقوقی از `GetClientTypeHistory`** (§12) | تنها عددِ منتشرشده‌ای که بازسازی‌شده است در حالی که مبدأ هست؛ رویِ «نبض بازار» و هر فیلترِ ارزشی اثر دارد | **ADD** |
| P0-2 | **رویدادِ تعدیل از `GetPriceAdjustByFlow` + `GetInstrumentShareChangeByFlow`** (§17) | MA52/MA100/سقفِ سوم/CHOCH/Jet همه رویِ کندلِ تعدیل‌شدۀ همان رویداد می‌نشینند؛ استنتاجِ فعلی رویدادهایِ هم‌تاریخ را جدا نمی‌کند | **ADD** (واکشیِ داده؛ **بدونِ لمسِ `candle_contract`/`price_basis` در این دور**) |
| P0-3 | **وضعیتِ نظارت / علتِ توقف / پیامِ ناظر** (`Supervision/…`, `webgw CompanyState → dalils`, `Msg/GetMsgByInsCode`) (§11، §17) | نمادی که «ممنوع-متوقف» یا «زیرِ نظارت» است ورودیِ FTS می‌شود؛ الان برنامه هیچ نظرِ مبدأ‌ای ندارد. `codal_fetcher.py:77-79` عمداً این عنوان‌ها را دور می‌ریزد | **ADD** (داده؛ UI نه) |

### P1 — ارزشِ بسیار بالا

| # | گپ | حکم |
| --- | --- | --- |
| P1-1 | `tape_history.q_tot_cap` (ارزشِ پنجرۀ `[ih]` — در همان پاسخِ بزرگ هست) | **ADD** (یک ستونِ NULL-able) |
| P1-2 | `isin`/`flow`/`p_red_tran`/`buy_op`/`c_gr_val_cot` از همان `GetMarketWatch` | **ADD** (صفرِ درخواستِ اضافه) |
| P1-3 | ClientType تاریخچۀ انباشتی (هر روزِ بسته یک بچ، نمادهایِ دارایِ حجم) | **ADD** — هم‌مسیرِ P0-1 |
| P1-4 | `bestLimitsHistory` (عمقِ صفِ تاریخی، delta) | **INVESTIGATE** — reconstruction هیچ مرجعی نکرده؛ حجمِ سنگین (§13) |
| P1-5 | incremental `MarketWatchPlus` (۱۷× ترافیکِ کمتر) | **DEFER** — حالتِ درحافظه + وابستگیِ دامنه‌ایِ `old.tsetmc.com` (§14) |
| P1-6 | `Instrument/GetInstrumentInfo` (free-float، sub-sector، contractSize، NAV) | **INVESTIGATE** — برایِ FTS بنیادی ارزشمند |

### P2 — قابلیتِ تحلیلی

| # | گپ | حکم |
| --- | --- | --- |
| P2-1 | `Trade/GetTradeVolume` ⇒ POC و حجم‌به‌قیمت (3.4KB) | **INVESTIGATE** — کم‌هزینه‌ترین درِ این خانواده |
| P2-2 | `Trade/GetTradeIntraDay` ⇒ 105 مینی‌بار، VWAPِ درون‌روز | **INVESTIGATE** |
| P2-3 | تیک + TradeSide + Delta + Footprint (ORBO) | **DEFER** — ورودیِ FTS نیست؛ 5.8MB/نماد/روز |
| P2-4 | `Shareholder/*` و `GetShareHolderChanges` | **DEFER** — یک درخواست/روز برایِ بازار (§16) |
| P2-5 | `MarketData/GetInstrumentStatistic` (88 آمارِ آماده) | **INVESTIGATE** |
| P2-6 | `Index/GetIndexB1LastAll` (57 شاخص) + `GetInstEffect` | **INVESTIGATE** |
| P2-7 | `Codal/GetPreparedDataByInsCode` (ساختارمند، جایگزینِ اسکرپ) | **INVESTIGATE** — ولی `codal_fetcher` فعلی parity دارد |
| P2-8 | `Fund/GetFundInDetail` / `GetETFByInsCode` (NAV، صدور/استرداد) | **DEFER** |

### P3 — nice to have / نباید اضافه شود

| # | گپ | حکم |
| --- | --- | --- |
| P3-1 | `old.tsetmc.com/tsev2/excel/MarketWatchPlus.aspx` | **IGNORE** — بدونِ InsCode، 3136 سطر، معادلِ همان تابلو |
| P3-2 | `Energy/GetAuctionById*` (حراجِ انرژی) | **IGNORE** — خارجِ دامنهٔ محصول |
| P3-3 | `Learning/GetLearningTopics` | **IGNORE** |
| P3-4 | `MarketMapNew` / `BubbleChart` (webgw heatmap) | **IGNORE** — از همان داده در خانه ساخته می‌شود |
| P3-5 | `TradingView/history` (webgw datafeed) | **IGNORE** — `GetClosingPriceDailyListCSV` را داریم |
| P3-6 | `Instrument/GetInstrumentByFlow` (boardِ صفحه‌بندی‌شده) | **IGNORE** — LIVE: **404** |
| P3-7 | imbalance با آستانۀ 3.0 / SAR / Median Line / Pitchfork | **IGNORE** — آستانه‌هایِ اختراعی یا خارجِ FTS |

---

## 22. Recommended Architecture (بدونِ implementation)

### 22.1 لایۀ داده

```
                      ┌── CDN    cdn.tsetmc.com/api       (source-native، JSON — منبعِ اصلی)
                      │
Canonical Data ───────┼── INLINE old.tsetmc.com/tsev2     (تنها مسیرِ delta؛ optional)
Layer                 │
                      ├── WEBGW  webgw.tse.ir             (فقط dalils/CompanyState؛ optional)
                      │                                   ⚠ از IP غیرایرانی بلاک است
                      ├── CODAL  search.codal.ir + Reports (بنیادی؛ موجود)
                      │
                      └── GITHUB releases                  (codal.db.lzma، latest.json؛ موجود)
                                   ↓
                        Canonical Market Model
                 market.db: market_watch ⋈ client_type ⋈ tape_history
                           ⋈ instruments ⋈ order_book ⋈ adjust_events ⋈ state_events
                                   ↓
              ┌────────────────────┼────────────────────┐
              ↓                    ↓                    ↓
            Market               Chart                 FTS
              ↓                    ↓                    ↓
        Screener/7Filters   Technical (setups)     Strategy / weekly gate
```

**تصمیمِ لایه:** چهار مسیرِ CDN/INLINE/WEBGW/CODAL **هر کدام پشتِ یک adapterِ جدا** می‌نشینند و
هیچ‌کدام در دیگری حل نمی‌شود. CDN منبعِ canonical می‌ماند؛ INLINE و WEBGW **optional با
fallbackِ صریحِ «بدون داده»** هستند (نه hard dependency) — چون هر دو از بیرونِ IP ایران و
گاهی از داخل هم ناپایدارند (204/`[]`/404 دیدیم).

**قیدهایی که این معماری باید حفظ کند** (از `skills/bors-architecture`):
- هر `api/*.py` تازه باید به `hiddenimports` در `fts_terminal.spec` اضافه شود؛ وگرنه EXE در اولین
  درخواست `ModuleNotFoundError` می‌دهد. `test_tsetmc` همین حالا در `spec:29,48` هست.
- `market.db.lzma` **کنارِ EXE** می‌نشیند، نه داخلش. هر جدولِ تازه با ستون‌هایِ NULL-able و
  `ALTER` تدریجی می‌آید (الگوی `ensure_daily_tran_column`)، نه با تغییرِ اجباریِ اسکیما.
- `price_basis.py` / `candle_contract.py` / `codal_periods.py` **فریز**‌اند. لایۀ تعدیلِ تازه
  (P0-2) باید **پشتِ** این درها بنشیند و گاردِ برابریِ قبل/بعدِ اعدادِ منتشرشده داشته باشد؛
  وگرنه parity guard سبز می‌ماند ولی عدد عوض شده.
- `numpy==2.0.2` پین می‌ماند. اگر روزی `polars` (مثلِ 5j9) مطرح شود، یک وابستگیِ سنگینِ تازه
  رویِ CPUهایِ baseline x86-v2 است ⇒ **فعلاً نه**.
- فرانت: `fetch` بیرونِ `shared/api/http.ts` ممنوع؛ هیچ endpointِ خارجیِ تازه‌ای نباید مستقیم از
  مرورگر زده شود (CORS + 403). همه از بک‌اند.
- هیچ داده‌ای از ماشینِ کاربر بیرون نمی‌رود؛ چرخشِ IP/adb فقط با تأییدِ IPِ تازه (الگوی
  `codal_fetcher.rotate_ip_via_adb`).

### 22.2 دو مسیرِ ClientType — مهم‌ترین تصمیمِ این سند

```
GetClientTypeAll (امروز، بدونِ ارزش)      GetClientTypeHistory/{ins}/{dEven} (دیروز، با ارزش)
        ↓                                             ↓
  client_type (vol, count)                     client_type (vol, count, VALUE)
        ↓                                             ↓
  نشستِ جاری: ارزش = vol × vwap                نشست‌هایِ بسته: ارزش = مبدأ
        ↓                                             ↓
  برچسبِ «بازسازی‌شده» در UI                   برچسبِ «مبدأ»
```
یعنی **نه** حذفِ بازسازی (برایِ امروز چاره‌ای نیست؛ History برایِ نشستِ جاری 500 می‌دهد —
LIVE) و **نه** مخلوط‌کردنِ دو مبنا بدونِ برچسب. اگر روزی یک عددِ ارزشی در UI دیده شد،
باید از همان برچسب معلوم باشد کدام مبدأ است.

### 22.3 تحلیلِ تیک (فقط اگر P2-1/P2-3 تصمیم گرفته شود)

```
Trade/GetTradeHistory (1 GET/نماد/روز)    BestLimits/{ins}/{date} (delta)
        ↓                                            ↓
  persistِ خام (parquet/lzma per symbol-day)   sort by refID
        ↓                                            ↓  last-write-wins per level
  cancel filter   ←  ORBO این را ندارد!        book snapshot در هر hEven
        ↓                                            ↓
  TradeSide (Lee-Ready: quote rule ← book L1) ───────
        ↓
  Delta / POC / profile
```
**دو اصلاحِ لازم نسبت به ORBO** (CODE-VERIFIED که ندارندش): فیلترِ `canceled`، و persistِ خام.
**کوتاه‌راه:** اگر فقط POC و توزیعِ حجم‌به‌قیمت خواسته شود، `Trade/GetTradeVolume` (3.4KB) کلِ
این لوله را حذف می‌کند.

### 22.4 چه چیزی **نباید** اضافه شود

- حالتِ «دو منبع برایِ همه‌چیز». CDN منبعِ اصلی می‌ماند؛ webgw فقط برایِ `dalils`.
- هر وابستگیِ تازه‌ای که `truststore.inject_into_ssl()` بزند (fima) — رویِ اپِ PyInstaller ما
  رفتارِ TLS را در سطحِ پروسه عوض می‌کند.
- هر retry رویِ 403/429. الگوی tsetmc-mcp درست است (`session.py:120-121`: فوراً `TsetmcBlocked`)،
  الگوی ORBO غلط (429 را retry می‌کند).
- هیچ آستانۀ تحلیلیِ وارداتی (3.0 در ORBO، 30 درجه در PTM، 80٪ در Andrews). آستانه رأیِ صاحبِ
  جزوه است، نه ترجمۀ کتاب.

---

## 23. Evidence / Sources

**مخازن (clone به `/tmp/tsetmc_refs/`؛ هیچ‌کدام به ریپو اضافه نشد):**

| repo | branch | آخرین commit | نسخه |
| --- | --- | --- | --- |
| `BabakEslami/tse-market-data` | main | `3d9d03b` 2026-07-15 | doc v4.1 |
| `ORBO-ir/ORBO` | main | `6ae501a1` 2026-07-05 | 0.2.4 |
| `hemoboghosian/fima` | master | `c322ef7` 2026-09-27 | 0.4.0 |
| `5j9/tsetmc` | main | `fdaf0e0` 2026-08-11 | 5.1.1.dev1 |
| `solitraderbusiness/tsetmc-mcp` | main | `abf182f` 2026-07-04 | 0.1.0 |

**BorsTerminal — لنگرهایِ مصرف‌شده:**

| موضوع | فایل:خط |
| --- | --- |
| `BASE = cdn.tsetmc.com/api` | `test_tsetmc.py:20` |
| `MW_URL` (withBestLimits=true) | `test_tsetmc.py:37` |
| مصرفِ تابلو: snapshot / tick / full sync | `test_tsetmc.py:1436`, `1591`, `1723` |
| `MW_COLS` | `test_tsetmc.py:97-101` |
| DDL `client_type` (بدونِ ارزش) | `test_tsetmc.py:936-941` |
| `GetClientTypeAll` | `test_tsetmc.py:1444`, `1763` |
| `queue_agg` / `book_lines` | `test_tsetmc.py:378-405` / `431-451` |
| DDL `order_book` (PK = ins_code) | `test_tsetmc.py:426-428` |
| DDL `mstat_snap` | `test_tsetmc.py:963-965` |
| `TAPE_HIST_URL` + DDL `tape_history` | `test_tsetmc.py:474`, `488-498` |
| CSV history | `test_tsetmc.py:1226`، `api/chart.py:507-509` |
| `GetMarketOverview` + DDL `market_index` | `test_tsetmc.py:186-217`, `223-272` |
| **بازسازیِ ارزشِ حقیقی/حقوقی** | **`mstat_engine.py:761-765`** (`vwap`: `:747`) |
| استنتاجِ تعدیل + بیانِ «درِ فید نیست» | `api/chart.py:100-158`, `165-171`, `173-177` |
| TEDPIX | `api/market_index.py:31-33`, `127-137`, `159-160` |
| حلقه‌هایِ 90s / 5s / 300s | `app.py:232-246`, `257-284`, `290-318` |
| polite-get ladder (60→300→600s) | `test_tsetmc.py:839-885` |
| حذفِ عمدیِ عنوان‌هایِ «توقف/بازگشایی» | `codal_fetcher.py:77-79` |
| `test_tsetmc` در `hiddenimports` | `fts_terminal.spec:29`, `48` |
| نگاشتِ متغیرهایِ فیلتر | `tape_flags.py:16-20` |
| `plp_series()` (خام، بدونِ clamp) | `tape_flags.py` + `plp_raw` در `api/market.py` |
| parityِ ۷ فیلتر | `docs/TA-PARITY-1405-07-04.md` §5–§6، `tools/tse_live_filter_parity.py` |
| Symbol modelِ فرانت | `frontend/src/shared/types/marketRow.ts` |

**LIVE-VERIFIED در این دور** (بازار بسته، ~55 درخواست، 1.1s فاصله): نمادِ آزموده `خودرو`
(`insCode=65883838195688438`، `cIsin=IRO1IKCO0008`)؛ تاریخ‌هایِ 20261005 (امروز) / 20261004 /
20261003 / 20261002 / 20261001 / 20260930 / 20260922 / 20260901 / 20260701 / 20260101.
مسیرهایِ آزموده‌شده: 21 مسیرِ CDN (دور ۱)، 14 مسیرِ CDN رویِ تاریخِ settle‌شده (دور ۲)،
`MarketWatchInit`/`MarketWatchPlus` + `GetMarketWatch?RefID=` + `GetInstrumentByFlow` + sweep
retention + 6 مسیرِ webgw (دور ۳ و ۴). اسکریپت‌ها در `/tmp/tsetmc_probe_*/` بودند و **commit
نشدند**.

---

## 24. Unknown / Unverified Items

چیزهایی که صریحاً **نمی‌دانم** و در هیچ حکمی استفاده نشده‌اند:

1. **`corporateTypeCode`** در `priceAdjust` — کلید درِ پاسخ هست، مقدار هیچ‌وقت: ۴۰۱۸ از ۴۰۱۸
   ردیفِ زنده null (بخشِ Events همین سند و `_audit/corporate_type_code_probe.json`). پس
   «decode نشد» نیست، «خام است»؛ نوعِ رویدادِ تعدیل از **خودِ جدولِ مبدأ** خوانده می‌شود
   (قیمتِ تعدیل‌شده در برابرِ خام)، نه از این فیلد.
2. **`is51…is89`** در `InstValue.aspx` / `dataType` در `GetInstrumentStatistic` — 88 سطر با
   `dataTypeDesc` فارسی دیدم (چندتاش قابل‌خوانش بود: «میانگین ارزش معاملات در 3/12 ماه گذشته»)؛
   جدولِ کاملِ کدها فقط در `Site.aspx?ParTree=151715` است که باز نکردم.
3. **`qTitNgJ`, `iSensVarP`, `pPhSeaCotJ`, `pPbSeaCotJ`, `iAnuTran`, `xqVarPJDrPRf`** در سطرِ
   تیک — LIVE آمدند، هیچ مرجعی معناشان را نمی‌داند (5j9 صریحاً می‌گوید «the _s are unknown»).
4. **`yval`** و **`cgrvalcot`** — کدها؛ 5j9 decode را به `tsetmc.docs.instrument()` واگذار
   می‌کند که خودش اسکرپِ زنده است. من decode نکردم.
5. **retentionِ واقعیِ `Trade/GetTradeHistory` و `BestLimits/{ins}/{date}`** — یک روزِ ۳ ماهِ
   پیش برایِ ClientType تست شد؛ برایِ تیک و عمقِ صف فقط 20261004 و 20261001 (خالی) تست شد.
6. **`MarketWatchTALMarket/fa`**, `BubbleChart/fa`, `MarketMapNew/fa`, `TradingView/history`,
   `InstrumentShortcut/fa` — README-ONLY؛ زده نشدند.
7. **`Energy/*`, `Learning/*`, `Shareholder/GetShareHolderCompanyList`** — زده نشدند.
8. **`RefID` در `GetMarketWatch`:** یک مقدارِ بزرگ تست شد و «همان snapshot» گرفتیم. آیا مقادیرِ
   نزدیک‌تر به refIDِ جاری واقعاً فیلتر می‌کنند؟ **آزموده نشد** — ادعایِ قطعیِ «JSON API هیچ‌وقت
   delta نمی‌دهد» نمی‌کنم؛ می‌گویم با آن ورودی نداد.
9. **رفتارِ webgw از IPِ غیرایرانی** — فقط از همین ماشین تست شد؛ ادعایِ بلاک‌بودنِ بیرونِ ایران
   README-ONLY است.
10. **cost/عملکردِ واقعیِ delta:** 1942 سطرِ بازگشتی در ساعتِ ۱۶:29 (بازار بسته) گرفته شد، نه
    در میانهٔ نشست. نسبتِ صرفه‌جوییِ واقعی در ساعاتِ شلوغ **اندازه‌گیری نشد**؛ عددِ «۱۷ برابر»
    نسبتِ بایتِ همان دو پاسخِ after-hours است، نه تخمینِ نشست.
11. **نیم‌قراردادِ pilot jev** در این دور هم پاسخ نداد ⇒ قضاوتِ متنیِ بیرونی رویِ جدولِ §21
    **انجام نشده**.
12. **هیچ ریسکِ 429/بنی برایِ مسیرهایِ تازه اندازه گرفته نشده** — §12 هزینه را فقط «درخواست»
    شمارش کرده، نه «نرخِ مجاز».

---

## شمارشِ اختتامی

```
Reference projects reviewed (code, not README):  5
Endpoints catalogued:                            ~95 (55 CDN code-verified in tse-md,
                                                  30 webgw doc-only, 5j9 inline/legacy, + ours)
Endpoints LIVE-PROBED this pass:                 ~45 distinct URL shapes
BorsTerminal production endpoints:               11 (TSETMC 9 + Codal 2 families)
Gaps found:                                      24
  P0: 3   P1: 6   P2: 8   P3: 7
Verdicts:  ADD 6 · INVESTIGATE 6 · DEFER 4 · IGNORE 7 · KEEP (7 filters) 7
Contradictions found in reference libs:          2  (fima I/N inversion; tse-md "GetMarketWatch
                                                   always empty" claim)
Reference bugs found (do NOT copy):              5  (ORBO: canceled unfiltered, no 429 handling,
                                                   no follow_redirects, local-date stamping,
                                                   footprint has no time axis)
Existing parity work re-used (not re-run):       9 documents/tools
Code changes made:                               0
Files created:                                   1  (docs/TSETMC-DATA-GAP-MATRIX.md)
```


