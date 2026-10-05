# TSETMC P0 Implementation — canonical data layer

دور: 1405-07-13. پیش از این دور: ممیزیِ `docs/TSETMC-DATA-GAP-MATRIX.md` (commit `f204749`).
قیدِ شکست‌پذیرِ این دور: **FTS، طبقۀ روند، دروازۀ هفتگی، فرمولِ هفت فیلتر و هیچ آستانه‌ای
تغییر نکردند** — و گاردِ ضدنشت (§7) همین را چک می‌کند، نه ادعای من.

همۀ شماره‌ها (خطِ کد، تعدادِ رکورد، تاریخ) با رقمِ لاتین.

---

## 1. P0-1 — ارزشِ ریالیِ حقیقی/حقوقی از مبدأ

### منبع
`GET https://cdn.tsetmc.com/api/ClientType/GetClientTypeHistory/{InsCode}/{dEven}`
⇒ کلیدِ `clientType` که **شیء** است نه آرایه.

فیلدهایِ مصرفی (LIVE-VERIFIED، خودرو/20261004):

| کلیدِ خام | ستون | مقدارِ آزموده |
| --- | --- | --- |
| `buy_I_Value` | `client_type_value.buy_i_val` | 9795900492781 |
| `buy_N_Value` | `buy_n_val` | 1424869091632 |
| `sell_I_Value` | `sell_i_val` | 8377684161902 |
| `sell_N_Value` | `sell_n_val` | 2000000000000 (نمونۀ ساختگیِ تست) |
| `buy_DDD_Value` | `buy_ddd_val` | 0.0 |
| `recDate` | `d_even` (برچسبِ روز، نه «امروز») | 20261004 |

حجم/تعداد کماکان از `ClientType/GetClientTypeAll` می‌آید (`client_type`) — آن endpoint
ارزش **ندارد** (LIVE: 2236 ردیف، فقط `*_Volume` و `*_Count`).

### جدول
`client_type_value(ins_code, d_even, buy_i_val, buy_n_val, sell_i_val, sell_n_val,
buy_ddd_val, fetched_at, source)` با کلیدِ `(ins_code, d_even)` +
`client_type_value_state(id=1, last_attempt, last_ok, newest_d_even, note)`.

### اولویت و fallback
`mstat_engine.money()` (تنها جایی که ارزشِ ریالی ساخته می‌شد — `mstat_engine.py:761-765`
پیش از این):

```
_VALUE_SLOTS = ((retail_buy,  buy_i_val,  buy_i_vol),
                (retail_sell, sell_i_val, sell_i_vol),
                (inst_buy,    buy_n_val,  buy_n_vol),
                (inst_sell,   sell_n_val, sell_n_vol))
→ هر خانۀ مبدأ اگر باشد از مبدأ، وگرنه همان حجم × VWAPِ پیشین
```

* **fallback حذف نشده** — بی‌ردیفِ مبدأ رفتارِ بیتغییر می‌ماند.
* **صفرِ جعلی ساخته نمی‌شود**: اگر هیچ‌کدام از چهار ارزش عدد نبود، `parse_client_type_value`
  `None` می‌دهد و **هیچ ردیفی نوشته نمی‌شود**. صفرِ واقعی (`buy_I_Value: 0.0`) ولی
  «صفر» خوانده می‌شود، نه «نبودِ داده» (چکِ جدا درِ گارد).
* `value_source` ∈ {`native`, `mixed`, `reconstructed`} — **mixed** یعنی مثلاً خرید از مبدأ
  و فروش از بازسازی؛ آن‌وقت آن دو عدد مبنایِ متفاوت دارند و باید این‌طور خوانده شوند.

### Provenance کجا دیده می‌شود
فقط درِ لایۀ mstat/audit. `value_source` درِ `api/market.py` نیست (چکِ گارد)، پس بدنۀ
`/api/market` بایت‌به‌بایت یکی می‌ماند و UI با برچسب شلوغ نمی‌شود.

### بودجه و throttle
`refresh_client_type_values(conn, day=None, limit=600, force=False, fetch=None)`:

* **یک درخواست به ازایِ (نماد × نشست)** — هیچ endpoint دسته‌جمعی برایِ ارزش وجود ندارد.
* دامنه از `client_type`ِ همان روز می‌آید (نمادهایی که مبدأ برایشان جریان گزارش کرده)،
  مرتب‌شده بر اساسِ مجموعِ حجم، با سقفِ `CTV_BUDGET = 600`. این انتخابِ **بودجه** است،
  نه دست‌کاریِ دامنۀ فیلتر: نمادی که بیرونِ بودجه می‌ماند ردیفی ندارد و مصرف‌کننده
  همان بازسازی را با `reconstructed` می‌خواند.
* `CTV_RETRY_S = 6h` + بررسیِ پوشش ⇒ درِ حلقۀ ۹۰ ثانیه‌ای چیزی تکرار نمی‌شود.
* `fetch` تزریق‌پذیر است تا گارد آفلاین بماند.

### رفتاری که سنجش تعیین کرد، نه فرضِ من
| نشست | پاسخ |
| --- | --- |
| 20261004 (دیروز، بسته) | 200 با چهار ارزش |
| 20261003 | 200 |
| 20260930 / 20260922 / 20260901 / **20260701** | 200 |
| **20261005 (امروز)** | **HTTP 500** |
| 20261002 (جمعه/تعطیل) | HTTP 500 |
| 20260101 | HTTP 500 |

⇒ مسیرِ History برایِ **نشستِ جاری** داده ندارد؛ پس «امروز» ناگزیر بازسازی می‌ماند و
دوگانهٔ مبدأ/بازسازی قاعدۀ این معماری است، نه کمبودِ پیاده‌سازی. retentionِ آزموده‌شده
تا `20260701` (≈ سه ماه) زنده است.

### اندازه‌گیریِ واگرایی (چون «P0» بودنِ این بند را کمّی می‌کند)
مبدأ در برابرِ `volume × vwap` رویِ ۱۲ نمادِ پرگردش در 20261004 (۲۴ سنجش):

```
median |err| = 0.13%      max |err| = 3.12%   (اهرم −3.12%، فولاد +1.91..2.19%)
```

و یک نتیجۀ جانبی که درِ کامنت هم نوشته شده: **نسبت‌ها از این انتخاب مستقل‌اند.**
`power = (buy_val/count) ÷ (sell_val/count)` است و VWAP در صورت و مخرج ساده می‌شود؛ پس
«قدرت خریدار» بی‌تغییر می‌ماند. آنچه مبدأ‌ای می‌شود **ارقامِ ریالیِ مطلق** است:
خرید/فروشِ هر گروه و `flow` خالص (`mstat_engine.py:818`) که درِ جمعِ صنعت/کلِ بازار
(`:1810`) و گیتِ «جهتِ پولِ حقیقی» (`:1434`) می‌نشیند.

**هشدارِ صادقانه:** چون پوشش بودجه‌دار است، جمعِ بازار **مخلوط** می‌شود (بعضی نمادها
مبدأ، بعضی بازسازی). با خطایِ میانیِ ۰٫۱۳٪ این مخلوط‌بودن زیرِ دقتِ داوریِ گیت است، ولی
«صفر نیست» و باید دانسته شود.

---

## 2. P0-2 — رویدادهایِ شرکتی

### منابع (LIVE-VERIFIED)
| endpoint | کلید | فیلدها |
| --- | --- | --- |
| `ClosingPrice/GetPriceAdjustByFlow/{flow}/{size}` | `priceAdjust` | `dEven, insCode, pClosing, pClosingNotAdjusted, corporateTypeCode, instrument{lVal18AFC,lVal30,insCode}` |
| `Instrument/GetInstrumentShareChangeByFlow/{flow}/{days}` | `instrumentShareChange` | `dEven, idn, insCode, lVal18AFC, lVal30, numberOfShareOld, numberOfShareNew` |

### مدلِ canonical
```
price_adjust_events(ins_code, d_even, symbol, p_closing, p_closing_not_adjusted,
                    corporate_type_code, ratio, source, fetched_at)
                    PK (ins_code, d_even)
share_change_events(ins_code, d_even, symbol, shares_old, shares_new, ratio,
                    source, fetched_at)  PK (ins_code, d_even)
```
تفکیکِ خواستۀ brief حفظ شده: **پایانیِ تعدیل‌شده** و **پایانیِ خام** دو ستون‌اند،
**سهامِ قبل** و **سهامِ بعد** دو ستون‌اند، و **تاریخِ رویداد** کلید است.

دو عددِ مشتق، با فرمولِ آشکار (نه آستانه):
```
ratio(price)  = pClosing / pClosingNotAdjusted
ratio(share)  = numberOfShareOld / numberOfShareNew     # قاعدۀ ضریبِ سهام
```
`corporateTypeCode` **خام ذخیره می‌شود و decode نمی‌شود** — هیچ‌یک از پنج مرجع معنای
کدهایش را نگفته و حدس زدنِ نوعِ رویداد همان «آستانه/معنای اختراعی» است که ممنوع است.

### یکپارچگیِ مسیرِ نوشتن
`fetch_corporate_events(s, conn)` = **۴ درخواست** (flow=1 بورس، flow=2 فرابورس، برایِ هر
دو خانواده). dedupe بر `(ins_code, d_even)` پیش از نوشتن، تا شمارشِ لاگ با ردیفِ بانک یکی
بماند. خطای هر flow جدا می‌شمارد و **هیچ ردیفی نمی‌نویسد** — «رویدادی نبود» فقط وقتی
ثبت می‌شود که مبدأ واقعاً جواب داده باشد.

### چارت: اصلاحِ ادعا، بدونِ بازنویسیِ منطق
`api/chart.py` (`_ADJ_FUNCTIONAL_REASON`) می‌گفت «افزایشِ سرمایه، آورده/حق‌تقدم، سودِ
نقدی… هیچ‌یک درِ فیدِ TSETMC نیست». این جمله **با سنجشِ زنده رد شد** و کامنت حالا همان را
می‌نویسد + دو endpoint را نام می‌برد + می‌گوید چه چیزی هنوز مبدأ ندارد: **نوعِ رویداد**.

منطقِ تعدیل (`_adjust_events_from_rows`) درِ این دور **از مبدأ نمی‌خواند** — چکِ گارد:
`"FROM price_adjust_events" not in api/chart.py`. دلیلش خواستۀ خودِ brief است
(«ابتدا مشخص کن کدام بخش را می‌توان دقیق‌تر کرد»): سنجشِ واگرایی باید قبل از عوض‌کردنِ
اعدادِ منتشرشده انجام شود، چون `price_basis.py` و `candle_contract.py` فریزند و هر
تغییرِ فاکتورِ تجمعی کلِ تاریخِ گذشته را مقیاس می‌کند.

**بخش‌هایی که با رویدادِ مبدأ دقیق‌تر می‌شوند (ثبت، نه اجرا):**
1. رویدادهایِ **هم‌تاریخ** (سود + افزایشِ سرمایه) — استنتاجِ شکاف نمی‌تواند جدا کند؛
   ORBO با `bisect_right` و اولویتِ same-date (share قبل از adjust) می‌تواند.
2. نمادهایی که تعدیل را **درِ ستونِ پایانیِ سطرِ بی‌معامله** می‌گذارند (الگوی «ب» درِ
   `api/chart.py:100-158`) — الان با نسبتِ `close/base` گرفته می‌شوند؛ `pClosing` در برابرِ
   `pClosingNotAdjusted` همان رویداد را مستقیم می‌دهد.
3. صندوق‌هایی که لنگر ندارند (`ANCHOR_MIN`) و امروز برایشان **هیچ** رویدادی نمی‌دهیم —
   با رویدادِ مبدأ، بی‌نیاز از حدسِ لنگر می‌شوند.

---

## 3. P0-3 — وضعیتِ نماد / علتِ توقف / نظارت / پیامِ ناظر

### منابع و جدول‌ها (همه LIVE-VERIFIED)
| مفهوم | endpoint | کلید | جدول |
| --- | --- | --- | --- |
| تغییرِ وضعیتِ نماد | `MarketData/GetInstrumentStateTop/{top}` | `instrumentState` | `instrument_state` |
| وضعیتِ یک نماد در یک روز | `MarketData/GetInstrumentState/{ins}/{date}` | `instrumentState` | (همان) |
| **علتِ توقف** | `webgw …/Instrument/CompanyState/fa` | آرایۀ `dalils` | `stop_reasons` |
| نظارت | `Supervision/GetSupervisionListBySourceID/{src}/{idx}` | `supervision` | `supervision_state` |
| پیامِ ناظر / اطلاعیه | `Msg/GetMsgByFlow/{flow}/{top}` | `msg` | `tsetmc_messages` |

تمایزهایی که خواسته شده بود، همه جدا می‌مانند:
`instrument_state` (c_etaval + c_etaval_title) · `last_h_even` (زمانِ تغییر) ·
`stop_reasons.dalils` (متنِ علت) · `supervision_state.under_supervision(_title)` +
`reasons` + `reason_count` · `tsetmc_messages(title, descr, d_even, h_even, flow)`.

### سه چیزی که سنجشِ زنده اصلاح کرد
1. **`supervision` تاریخچه نیست.** `id=0`، `userName=null`،
   `insertionDateTime=0001-01-01T00:00:00` درِ همۀ ردیف‌ها ⇒ جدول **snapshot** است و هر
   اجرا کلش جایگزین می‌شود؛ هیچ کلیدِ زمانی‌ای از آن ساخته نشد (چکِ گارد که آن صفرِ
   تاریخ جایی ننشیند).
2. **`GetInstrumentStateTop` لاگِ تغییر است، نه وضعیتِ روزانه.** با کلیدِ دوتایی
   `(ins_code, d_even)` از 500 رکورد فقط 225 ردیف می‌ماند ⇒ کلید به
   `(ins_code, d_even, last_h_even)` عوض شد و ۴۹۲ ردیف می‌ماند (۸ تایِ واقعاً تکراری).
3. **`webgw` با ISIN کلید نمی‌خورد، با `nam` می‌خورد** و `nam` رشتهٔ
   «نماد(نامِ کامل)» است (`kodenamaddarsamane` همیشه null). پس پیشوندِ قبل از «(» =
   `l_val18`.

### تله‌ای که فقط سنجشِ زنده نشان داد (مهم‌ترین یافتهٔ این بخش)
پیوندِ `nam → instruments.l_val18` اول **۱۵ از ۵۲** ردیف را می‌گرفت. علت: بانک بعضی
نمادها را با **ي/ک عربی** نگه می‌دارد (`حكشتي`، `واميد`) و webgw همان‌ها را با **ی/ک
فارسی** می‌فرستد (`حکشتی`، `وامید`). با `fold_persian()` رویِ هر دو طرف ⇒ **۲۵ از ۵۲**.
همان درسی که fima با `convert_ar_characters` گرفته بود و ما درِ مسیرِ واکشی نداشتیم.

۲۷ ردیفِ باقی‌مانده درِ `instruments` نیستند (صندوق‌ها/اوراق/اختیارهایی که تابلویِ سهام
نمی‌آوردشان) ⇒ **نمی‌سازیمشان**: بی‌کلیدِ پایدار، اتصالِ بعدی حدسی می‌شد.

### وب‌گی اختیاری است
`fetch_state_and_notices(..., webgw=None)` مسیر را بی‌خطا رد می‌کند؛ `webgw` یک **تابعِ
تزریق‌شدنی** است نه یک وابستگی. دلیلش: `ENDPOINTS.md:544` می‌گوید از IP غیرایرانی بلاک
است (من از همین ماشین گرفتم؛ GitHub Actions نه). خطای webgw فقط `failed` را بالا می‌برد
و بقیه از CDN می‌آیند.

### کدال: یک مفهوم، یک منبع
`codal_fetcher.py:77-79` (`SAVE_USEFUL_ONLY = True`) عنوان‌هایِ «توقف/بازگشایی» را دور
می‌ریزد و **همان‌طور ماند**. از این به بعد منبعِ canonicalِ این مفهوم TSETMC است
(`stop_reasons` / `instrument_state` / `supervision_state`)، نه دو مسیرِ متناقض. چکِ گارد
که این پرچم عوض نشود.

---

## 4. فیلدهایِ رایگانِ P1

همۀ این‌ها درِ **همان پاسخ‌هایی** بودند که همین حالا دانلود می‌شود؛ هیچ درخواستِ تازه‌ای
هزینه نکردند.

| فیلد | source | type | unit | meaning | consumer |
| --- | --- | --- | --- | --- | --- |
| `instruments.isin` | `GetMarketWatch.insID` | TEXT | — | ISINِ نماد | هنوز هیچ؛ تنها پلِ به webgw (که با ISIN کلید می‌خورد) |
| `instruments.c_gr_val_cot` | `GetMarketWatch.cGrValCot` | TEXT | — | گروهِ کالایی | هنوز هیچ |
| `market_watch.flow` | `GetMarketWatch.flow` | INTEGER | کد | بازار (۱ بورس / ۲ فرابورس / …) | هنوز هیچ؛ امروز از `boards` جدا می‌شد |
| `market_watch.p_red_tran` | `GetMarketWatch.pRedTran` | REAL | ریال | قیمتِ استردادِ NAV | هنوز هیچ (ETF/صندوق) |
| `market_watch.buy_op` | `GetMarketWatch.buyOP` | REAL | ریال | قیمتِ صدورِ NAV | هنوز هیچ (ETF/صندوق) |
| `tape_history.q_tot_cap` | `GetClosingPriceDailyAllInst.qTotCap` | REAL | ریال | گردشِ ریالیِ همان نشستِ پنجرۀ `[ih]` | هنوز هیچ؛ هر فیلترِ «میانگینِ ارزشِ ۳۰ روز» |

**decode حدسی ننوشتم**: معنای `pRedTran`/`buyOP` از نامِ کلید و از 5j9
(`predtran` = «NAVِ استرداد»، `buyop` = «NAVِ صدور»، `market_watch.py:70-74`) است؛ `flow`
از `Flow` enum همان مرجع. `qTotCap` درِ پاسخِ واقعی دیدہ شد (184911 ردیف، کلیدش درِ
ردیفِ نمونه).

**هیچ‌کدام به بدنهٔ `/api/market` اضافه نشد** (چکِ گارد): مصرف‌کنندۀ نمایشی ندارند، و
سازندۀ تابلو باید بایت‌به‌بایت یکی بماند.

### دو باگی که همین بخشِ «رایگان» بیرون داد
1. **`INSERT OR REPLACE INTO instruments VALUES (۱۱ جایگاهی)`** با افزودنِ دو ستون
   می‌شکست — و بدتر: `paper_type` را `mstat_engine.MIGRATIONS` با `ALTER` می‌افزاید، پس
   **ترتیبِ ستون‌ها درِ بانکِ تازه با بانکِ ارتقایافته فرق می‌کند** و نوشتنِ جایگاهی رویِ
   یکی از دو مسیر ستون‌ها را بی‌صدا جابه‌جا می‌نشاند. ⇒ نوشتنِ `instruments` و هر پنج
   نوشتنِ `market_watch` درِ گاردِ mstat به **نام‌دار** تبدیل شد (`_INST_INSERT` /
   `TS._MW_INSERT`).
2. `dev/mstat_local_v975.py` اسکیما و شمارۀ ستون را **دستی کپی** کرده بود
   (`MW_COLS = 33` و یک `DDL` جدا). یعنی هر ستونِ تازه‌ای آن گارد را می‌شکست و تا آن
   لحظه «کهنۀ من vs کهنۀ خودم» را چک می‌کرد. ⇒ حالا `new_db()` همان
   `test_tsetmc.create_schema()` را اجرا می‌کند و شمارش از `len(TS.MW_COLS)` می‌آید؛
   چک‌هایِ شمارۀ ثابت (`== 11`) به **قیدِ مجموعه‌ای** تبدیل شدند (بی‌عددِ جادویی).

---

## 5. گارد و تست‌ها

`dev/tsetmc_p0_v1076.py` — **۹۵ بررسی، همه سبز**، کاملاً آفلاین (پاسخ‌ها تزریق می‌شوند؛
شکلشان از سنجشِ زندهٔ همین دور). درِ `dev/run_all_tests.py` ثبت شده.

| خواستۀ brief | چک |
| --- | --- |
| native value exact | `buy_I_Value`/`sell_I_Value` عینِ مبدأ؛ ردیفِ بانک == مبدأ |
| native > reconstruction | مبدأ می‌نشیند و با بازسازی فرق دارد (چکِ بی‌معنا نمی‌شود) |
| fallback still works | بی‌ردیفِ مبدأ ⇒ همان `vol × vwap`، `value_source='reconstructed'` |
| I/N mapping unchanged | `retail ← I` و `inst ← N` هم درِ عدد و هم درِ ترتیبِ slotها |
| zero/null behavior | `0.0` مبدأ = صفرِ واقعی؛ پاسخِ بی‌ارزش ⇒ هیچ ردیفی |
| adjusted vs non-adjusted | `p_closing` و `p_closing_not_adjusted` دو ستونِ جدا |
| share count old/new + event date | `shares_old/new`، `d_even` کلید |
| multiple events / no-event symbol | دو رویدادِ دو روزه می‌مانند؛ بی‌رویداد ⇒ صفر ردیف |
| state / reason / supervision / messages | هر چهار جدول با ردیفِ واقعی |
| empty response / upstream error | `failed` می‌شمارد، بی‌نوشتن، بی‌سقوط |
| regression | `dev/run_all_tests.py` ⇒ **ALL SUITES PASSED** |

چک‌هایِ ضدنشت (§«Do NOT»): `tape_flags` هرگز `client_type_value` را نمی‌خواند؛
`confidence_engine` همان حجم‌مبنا می‌ماند؛ `value_source` درِ `api/market.py` نیست؛
`api/chart.py` از `price_adjust_events` نمی‌خواند؛ هیچ `api/*.py` تازه‌ای ساخته نشده
(پس `fts_terminal.spec` دست‌نخورده)؛ `SAVE_USEFUL_ONLY` عوض نشده.

### چیزی که گارد درِ همین دور سه باگ واقعی گرفت
`share_change_events` هشت‌ستونه بود با هفت placeholder · `Msg/GetMsgByFlow` یک پیام را از
هر دو flow دو بار می‌شمرد · `priceAdjust` هم همین (dedupe بر کلیدِ اصلی اضافه شد).

---

## 6. راستی‌آزماییِ زنده

بانک: کپیِ `market.db` (۱۸۱MB) درِ temp — **خودِ بانکِ کاری دست‌نخورده**. بازار بسته بود.

```
migration رویِ بانکِ واقعی:
  market_watch: flow / p_red_tran / buy_op        ✓
  instruments : isin / c_gr_val_cot               ✓
  tape_history: q_tot_cap                         ✓
  جدول‌های تازه: client_type_value, price_adjust_events, share_change_events,
                instrument_state, stop_reasons, supervision_state, tsetmc_messages  ✓

P0-2  fetch_corporate_events → {'adjust': 1000, 'share': 3478, 'failed': 0}
      price_adjust_events: 1000 ردیف | 609 نماد | 20240721 … 20261004
      share_change_events: 3478 ردیف | 20081206 … 20261005
      نمونه: كماسه 20261004  pClosing=5710  pClosingNotAdjusted=5730  ratio=0.9965096
             دتهران 20261004  600 / 1000 → ratio=0.6      corporateTypeCode=None (بی‌decode)

P0-3  fetch_state_and_notices → {'state': 500, 'messages': 600, 'supervision': 69,
                                 'stops': 25, 'failed': 0}
      instrument_state 492 (225 نمادِ متمایز) · supervision_state 69 ·
      tsetmc_messages 600 · stop_reasons 25
      نمونه: اپال (3, مشمول فرایند تعلیق) · دانا (2, تعلیق شده) · واميد (3, …)

P0-1  refresh_client_type_values(day=20261004, limit=20)
      → {'written': 20, 'total': 20, 'errors': 0, 'attempted': 20}
      خودرو  buy_i_val=9795900492781  buy_n_val=1424869091632  sell_i_val=8377684161902
      ذوب    buy_i_val=4194125069951  buy_n_val=600902282850   sell_i_val=4054579448474
      (هر دو عدد با سنجشِ مستقیمِ همان endpoint درِ §12 سندِ ممیزی یکی است)
```

نمادِ **بی‌رویداد** هم پوشش داده شد: 609 نمادِ دارایِ تعدیل از ~۵۷۰۰ نماد ⇒ بقیه هیچ
ردیفی درِ `price_adjust_events` ندارند و چارت برایشان همان مسیرِ استنتاج می‌رود.

---

## 7. محدودیت‌هایِ شناخته‌شده

1. **پوششِ P0-1 بودجه‌دار است** (۶۰۰ نماد در هر اجرا، یک نشست). جمعِ بازار/صنعت
   **مخلوطِ مبدأ و بازسازی** می‌شود؛ با خطایِ میانیِ ۰٫۱۳٪ زیرِ دقتِ گیت است ولی صفر نیست.
2. **امروز هیچ‌وقت مبدأ ندارد** (500) ⇒ `value_source` برایِ نشستِ جاری همیشه
   `reconstructed` است. این رفتارِ مبدأ است، نه کمبودِ کد.
3. **`corporateTypeCode` decode نشده** ⇒ نوعِ رویداد نامعلوم؛ فقط خام ذخیره می‌شود.
4. **منطقِ تعدیلِ چارت هنوز از مبدأ نمی‌خواند** — سه بخشِ دقیق‌ترشدنی درِ §2 ثبت شد،
   سنجشِ واگرایی و تصمیمِ مالک قبل از عوض‌کردنِ اعدادِ منتشرشده لازم است.
5. **۲۷ از ۵۲ ردیفِ «علت توقف» بی‌پیوند ماندند** (درِ `instruments` نیستند) — عمداً
   ساخته نشدند.
6. **`instrument_state` تنها «تغییراتِ اخیر» را دارد** (سقفِ ۵۰۰ رکورد)؛ وضعیتِ فعلیِ
   هر ۵۷۰۰ نماد نیازمندِ `GetInstrumentState` به‌ازایِ نماد است که انجام نشده.
7. **P1-هایِ رایگان مصرف‌کننده ندارند** — فقط ذخیره می‌شوند. هیچ ستونی به بدنهٔ تابلو
   اضافه نشد.
8. **پروتکلِ delta (§14 سندِ ممیزی) عمداً پیاده نشد** — `DEFER/P1` بود.
9. **pilot jev باز هم پاسخ نداد** ⇒ قضاوتِ متنیِ بیرونی رویِ همین دور انجام **نشده**.
10. هیچ درخواستِ تازه‌ای به TSETMC درِ حلقۀ ۹۰ ثانیه‌ای اضافه نشده؛ هر سه P0 پشت
    `tsetmc_p0_state` با throttle روزانه/۶ساعته‌اند.

---

## 8. فایل‌هایِ تغییرکرده

```
test_tsetmc.py            جدول‌هایِ تازه + سه fetcher + throttle + fold_persian
                          + سه ستونِ market_watch و دو ستونِ instruments
                          + q_tot_cap درِ tape_history + نوشتنِ نام‌دارِ instruments
mstat_engine.py           اولویتِ مبدأ در money() + value_source
                          + MIGRATIONS (flow/p_red_tran/buy_op، isin/c_gr_val_cot،
                            tape_history.q_tot_cap) + TAPE_HIST_DDL هم‌نام
api/chart.py              اصلاحِ کامنتِ «درِ فید نیست» (منطقِ تعدیل دست‌نخورده)
dev/tsetmc_p0_v1076.py    گاردِ تازه (۹۵ بررسی)                       [جدید]
dev/run_all_tests.py      ثبتِ سوئیت
dev/mstat_local_v975.py   اسکیما از create_schema می‌آید، نه از کپیِ دستی؛
                          نوشتن‌ها نام‌دار؛ چک‌هایِ شمارۀ ثابت → قیدِ مجموعه‌ای
dev/tape_filters_v1034.py نوشتنِ نام‌دارِ tape_history

هیچ فایلی در api/ ساخته یا حذف نشد ⇒ fts_terminal.spec دست‌نخورده.
هیچ فایلِ frontend/ تغییر نکرد ⇒ UI و بدنهٔ تابلو یکی مانده.
```
