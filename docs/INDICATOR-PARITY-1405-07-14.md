# INDICATOR-PARITY — ممیزیِ اندیکاتورها پیش ازِ FTS (۱۴۰۵-۰۷-۱۴ / ۲۰۲۶-۱۰-۰۲)

> **Snapshot تاریخیِ parity اندیکاتورها:** این ممیزی در ۲۰۲۶-۱۰-۰۲ انجام شده و وضعیت تست یا اندیکاتورهای جدیدتر را پوشش نمی‌دهد. برای تصمیم ادغام، سورس اندیکاتور، مجوز، repaint/look-ahead، قرارداد کندل و تست‌های جاری را دوباره بررسی کنید؛ `inbox/` به‌معنی تأیید نیست.


مرحلۀ **فقط‌خواندن**: هیچ کدِ محصولی عوض نشد، هیچ وابستگیِ تازه‌ای افزوده نشد.
سوال: اندیکاتورهایِ فعلی از نظرِ فرمول، ورودی، smoothing، seed، timeframe و
خروجیِ عددی صحیح‌اند؟ سه پایۀ مقایسه:

| پایه | چیست | شاهدِ اعتبار |
|---|---|---|
| O — oracle | `_audit/indicator_audit/oracle.py` (تعریفِ کتابی: Wilder 1978، Appel، Bollinger، Lambert، Halma، Harris) + `pandas 3.0.5` به‌عنوان پیادۀ مستقلِ بیرونی | `_audit/indicator_audit/test_oracle.py` = **۳۲ سبز / ۰ قرمز** (برابریِ SMA/EMA/std با pandas،ثابت‌ماندنیِ سری‌هایِ تباهیده، هویتِ WMA−SMA=(n−1)/6) |
| P — product پایتون | `api/chart.py`، `confidence_engine.py` (توابعِ خالص import شدند) | — |
| T — product فرانت | `lib/indicators.ts` + `lib/mabnaIndicators.ts`، **اجراشده** درِ node با esbuild | `js_run.mjs` → `ts_out.json` (۴۴۴ سری) |

داده: ۱۲ نمادِ واقعی از CSVهایِ منتشرشدۀ TSETMC کش‌شده (`_audit/parity_event_csv`)،
۱٬۷۶۶ تا ۴٬۹۶۹ کندلِ روزانه درِ هر نماد، با `last` و `value`ِ واقعی؛ نگاشتِ ستون‌ها
از خودِ `candle_contract.from_csv_row` (همان مسیری که محصول می‌نویسد).
معیارها: `bad` = شمارِ نقاطِ واگرا فراترِ از گردکردنِ ۲ رقم، `max_rel` = بدترینِ خطایِ نسبی.
بازتولید: `make_dataset.py` → `js_run.mjs` → `run.py` → `cause_probe.py`.

## ۱) جدولِ نتیجه

| اندیکاتور | پیادۀ فعلی | مرجع | ورودی | بدترینِ خطا | علتِ واگرایی | وضعیت | FTS امن؟ |
|---|---|---|---|---|---|---|---|
| SMA 5/10/20/50/100/120/200 | `api/chart.py:1348 _fts_ma` | oracle ≡ `pandas.rolling.mean` | close (مبنایِ حل‌شده) | ۱٫۳e-۵ (گردکردن) | — | **درست** | بله |
| SMA (همان پنجره‌ها) | `api/chart.py:890-897 /api/ma` | oracle | close | `max_rel = 1.0` | شمارند `i+1` (میانگینِ کلِ تاریخ) نه `w` — ۴۶٬۴۰۲ از ۴۶٬۴۱۴ نقطه غلط | **غلط** | نه (ولی مصرف‌کنندۀ زنده ندارد) |
| SMA 14/20/50/100 | `lib/indicators.ts:48` | oracle | close | ۰ | — | **درست** | بله |
| EMA 9/12/14/26 | `lib/indicators.ts:21` (بذر=SMA) | oracle(seed=sma) | close | ۰ | — | **درست** | بله |
| RSI 5/7/8/14 | `lib/indicators.ts:372` (Wilder) | oracle.wilder | close | ۵e-13 | — | **درست** | بله |
| RSI 5/7/8/14 | `api/chart.py:1360 _fts_rsi` | oracle.wilder | close | `Δ=1.88` رویِ پنجرۀ ۳۵ سطری | بذر + **یکِ گامِ اضافیِ** RMA پیش ازِ نخستینِ خروجی (تغییرِ `i=period` دو‌بار شمرده می‌شود) — variantِ همان حلقه: bad=0 | **غلط (warmup)** | با احتیاط |
| RSI 14 (تک‌عدد) | `confidence_engine._rsi` | oracle.wilder | close | ۱e-15 | — | **درست** | بله |
| ATR 10/14 | `pineStd.atr = rma(trueRange)` | oracle.atr(Wilder) | H/L/C | ۰ | — | **درست** | بله |
| ATR 14 (Renko/PnF) | `chartTypes.ts:33` = SMA(TR) | oracle.atr(sma) | H/L/C | ۰ | سومینِ طعمِ ATR درِ مخزن (SMA نه Wilder) | درست درِ تعریفِ خودش | بله (سایزِ باکس) |
| Stdev/BOLL 20 | `pineStd.stdev` + klinecharts BOLL | oracle ddof=0 | close | ۳e-16 | جمعاً population (هر دو یکی) | **درست** | بله |
| VWMA 20 | `pineStd.vwma` | oracle | close+vol | ۰ | — | **درست** | بله |
| LinReg 20 | `pineStd.linreg` | oracle (LSQ) | close | ۳e-14 | — | **درست** | بله |
| Stoch raw | `pineStd.stoch` | oracle.stoch_series | series | ۰ | پنجرۀ بی‌نوسان → na (قاعدهٔ Pine) | **درست** | بله |
| DT %K(8,5,3) | `mabnaIndicators.ts` | oracle: SMA(stoch(RSI8,5),3) | close→RSI8 | ۰ | — | **درست** | بله |
| ZScore(20,2) | `mabnaIndicators.ts` | oracle (x−SMA)/σ_pop | close | ۸e-16 | — | **درست** | بله |
| SQZMOM momentum | `mabnaIndicators.ts` | oracle: linreg(close−JI,20) | H/L/C | ۲e-11 | — | **درست** | بله |
| VixFix vix | `mabnaIndicators.ts` | oracle: (HHV(close,22)−low)/HHV·100 | close+low | ۰ | — | **درست** | بله |
| WaveTrend wt/avg | `mabnaIndicators.ts` | oracle: همان زنجیر با **hlc3 واقعی** | نامشروع | `max_rel=2.3e+03` | `source('hlc3')` درِ واقع (H+L+C)/3 برمی‌گرداند؛ با همان tp واگرایی صفر می‌شود (bad=0/۴۶٬۴۶۲) | **غلط — برچسبِ ورودی** | نه (WaveTrend/Cross/FibBB) |
| HMA(9) | `mabnaIndicators.ts` (کارِ نامنسوب) | oracle: Halma (half=floor) | close | `1.1e+02` | `Math.round(9/2)=5` به‌جای `floor=4` + نرمال‌سازیِ بی‌مقدارها؛ با قرائتِ خودیِ TS: bad=0 | درست درِ تعریفِ خودش، **مغایرِ مرجع** | بله (فقط چارت) |
| VWAP | `mabnaIndicators.ts:1013` (کارِ نامنسوب) | oracle: session-anchored (Harris) | H/L/C+vol | `1.8e+01` | هیچِ ریستِ روزانه‌ای نیست؛ Σ تجمعی از اولِ سری (variantِ بی‌ریست bad=0) | **غلط** | نه |
| SuperTrend(10,3) | `mabnaIndicators.ts:1046` (کارِ نامنسوب) | oracle: ATRِ واقعیِ Wilder | H/L/C | `1.8e+00` | TR تنها از تفاضلِ closeها + قفلِ بندِ یک‌طرفه؛ هیچِ variantِ تنها علت را توضیح نداد (bad=4182 با TR-فقط) | **غلط — علتِ کامل ناشناس** | نه |
| Ichimoku | `mabnaIndicators.ts:1175` (کارِ نامنسوب) | — | — | — | درِ node با `max is not defined` می‌شکند (۱۲/۱۲ نماد)؛ `tsc` هم ۵۶ خطا درِ همین فایل می‌دهد | **اجرا نمی‌شود** | نه |
| MA_Ribbon 5..200 | `mabnaIndicators.ts:1237` (SMA) | oracle.sma | close | ۰ | پکیجِ `react-klinecharts-ui` همین نام را با **EMA** می‌سازد → دو جوابِ متفاوت | درست درِ تعریفِ خودش | بله |
| MACD histogram | klinecharts built-in = `(dif−dea)×2` در برابرِ repo/پکیج بدونِ ×۲ | oracle.Appel | close | ×۲ مقیاس | قراردادِ چینیِ histogram | روشِ متفاوت، نه غلط | بله |
| RSI درِ چارت | klinecharts built-in، پیش‌فرض `calcParams=[6,12,24]` | oracle 14 | close | دوره‌ها فرق دارد | برچسبِ منو «RSI 14 Wilder» ولی پارامترِ ثبت‌شده عوض نشده؛ MA هم «14/100» در برابرِ `[5,10,30,60]` | **برچسبِ غلط** | نه برایِ خوانشِ کاربر |
| هفتگی (سبد) | `api/chart.py:1140` =شنبه-محور | oracle bucket | close | ۰ | — | **درست** | بله |
| هفتگی (سبد) | `confidence_engine._weekly_closes` = ISO دوشنبه | سبدِ شنبه | close | `1.2e+01` | تقویمِ متفاوت: ۹٬۷۱۴ از ۱۰٬۷۰۲ سطرِ هم‌شاخص فرق دارد | روشِ متفاوت (تصمیمِ معلق) | بله ولی ناسازگار |
| ماهانهٔ (سبد) | `_fts_resample('M')` = میلادی | oracle Gregorian | close | ۰ | رهاورد جلالی است؛ داخلِ چارت میلادی | روشِ متفاوت | بله |
| سریِ ورودیِ FTS | `api/chart.py:2195 _fts_scaled` | price_basis (last ≠ closing) | last/close | ۲٫۸e-02 | `last := close×k` نوشته می‌شود ⇒ مبنایِ last درِ سریِ FTS هرگز last نیست | **نقضِ قرارداد** | نه |

## ۲) سه دسته

**الف) درست و امن برایِ FTS** — `_fts_ma`، `I.sma/ema/rsi`، `pineStd.{rma,atr,stdev,vwma,linreg,stoch,highest,lowest}`،
MabnaDT/ZScore/SQZMOM/VixFix، سبدِ شنبه‌ایِ `chart`، سبدِ میلادیِ ماهانه، هندسۀ `widen` و
`price_basis` درِ مسیرهایِ چارت. هیچ اصلاحی نمی‌خواهند.

**ب) درست ولی روشِ متفاوت** — HMA با half=round و WMA با نرمال‌سازی؛ MA_Ribbonِ repo (SMA) در
برابرِ پکیج (EMA); MACD histogramِ ×۲؛ ATRِ SMA برایِ Renko/PnF؛ Stochِ na درِ پنجرۀ بی‌نوسان؛
تقویمِ ISO درِ `confidence_engine` در برابرِ شنبه درِ `chart`؛ ماهانۀ میلادی درِ چارت در
برابرِ جلالیِ رهاورد؛ جمعِ population درِ Bollinger (سراسرِ مخزن یکدست است). این‌ها یا باید
درِ «Indicator Contract» صریحاً قفل شوند یا به یکِ قاعده برگردند — انتخابِ مالک.

**ج) واقعاً غلط** —
۱. `/api/ma`: شمارندِ غلط ⇒ MA هایِ ۵/۲۰/۵۰/۱۲۰ که این endpoint می‌دهد هیچ‌گاه MA نیستند
   (٪۹۹ خطایِ نسبی). امروز مصرف‌کنندۀ زنده ندارد (فقط `events`اش مصرف می‌شد) ولی اندپوینت
   منتشر و مستند است.
۲. `_fts_rsi`: گامِ اضافی درِ seed ⇒ تا ~۵۰ سطرِ اولِ هر پنجره خطا (بدترینِ اندازه‌گرفته‌شده
   Δ=۱٫۸۸ رویِ پنجرۀ ۳۵ سطری، Δ≤۰٫۰۵ رویِ سریِ بلند). چون آستانۀ واگراییِ لایۀ ۴ «۱٫۰ واحد»
   است، همین اندازه‌گیری می‌تواند رأیِ لایۀ ۴ را درِ پنجره‌هایِ کوتاه عوض کند.
۳. `source('hlc3')` درِ فرانت درِ واقع typical price است ⇒ WaveTrend/WaveTrendCross/FibBB رویِ
   ورودیِ دیگری نسبت بهِ تعریفِ Pine عدد می‌دهند (۳۵٬۴۸۸ از ۴۶٬۴۶۲ نقطه).
۴. VWAPِ نامنسوب: بی‌ریستِ روزانه؛ SuperTrendِ نامنسوب: TR از close تنها (علتِ کامل هنوز
   ناشناس)؛ Ichimokuِ نامنسوب: اجرا نمی‌شود و `tsc` را می‌شکند (۵۶ خطا).
۵. `_fts_scaled`: `last` را با closeِ ضرب‌شده بازنویسی می‌کند — نقضِ صریحِ قراردادِ مبنایِ قیمت
   درِ سریِ ورودیِ FTS.
۶. برچسبهایِ منو با پارامترهایِ واقعیِ klinecharts نمی‌خوانند (RSI «14» ↔ `[6,12,24]`،
   MA «14/100» ↔ `[5,10,30,60]`).

## ۳) تکرارها (یکِ اندیکاتور، چندِ پیاده)

| چیز | شمار | طعم‌ها |
|---|---|---|
| SMA | ۴ | `_fts_ma` (درست)، `/api/ma` (غلط)، `confidence_engine._sma`، SQL `AVG OVER` |
| RSI | ۴ | `_fts_rsi` (بذرِ غلط)، `confidence_engine._rsi` (درست)، `I.rsi` (درست)، klinecharts (پارامترِ ۶/۱۲/۲۴) |
| ATR | ۳ | Wilder (mabna)، SMA(TR) (chartTypes)، close-only-TR (SuperTrendِ نامنسوب) |
| هفتگی | ۲ | شنبه (`chart`) ↔ ISO (`confidence_engine`) |
| CHoCH | ۳ | دو درِ `chart` (0.3٪) + یکی درِ `confidence_engine` (بی‌حاشیه) |
| فیبو | ۲ | log-scale belts (`chart`) ↔ linear 0.5–0.68 (`confidence_engine`) |
| بنیادِ حجم | ۴ | `prior30/30` ↔ `month_avg_vol` ↔ `AVG(q_tot_cap)` ↔ میانگینِ همۀ نشست‌ها |
| ارزشِ بازار | ۲ | `market_watch.market_cap` (تک‌مرجعِ اعلام‌شده) ↔ `p_closing × total_shares` (دو جا دوباره حساب می‌شود) |

## ۴) پیشنهاد (بدونِ اجرایِ امروزی)

1. دو اصلاحِ قطعیِ پایتون: شمارندِ `/api/ma` و گامِ اضافیِ `_fts_rsi` — هر دو یک‌سطری‌اند و
   هر دو با گاردِ عددی (oracle درِ `_audit/indicator_audit/`) قابلِ قفل‌اند.
2 `source('hlc3')` یا باید (H+L+3C)/6 شود یا برچسبش به `tp` عوض شود؛ تصمیمِ «کدام ورودی را
   جزوه می‌خواهد» با مالک است (این عدد درِ سه مطالعۀ Mabna نشسته است).
3. کارِ نامنسوبِ فرانت (VWAP/SuperTrend/Ichimoku/HMA/MA_Ribbon/Stochastic/CCI/MACD/RSI_TV) یا
   تمام‌شده و ثبت می‌شود یا ازِ شاخه بیرون می‌رود؛ درِ وضعیتِ فعلی `tsc` سبز نیست.
4. برایِ «Indicator Contract» سه چیز را قفل کنید: ورودی (close بعد ازِ `price_basis`، با یا بی‌ضریبِ
   تعدیل)، قاعده‌هایِ seed/warmup (SMA-seed، na نه صفر)، و یکِ پیاده برایِ هر نام.
   هارنسِ عددیِ آماده همین است: `python _audit/indicator_audit/run.py` (۷۰۹ سطرِ مقایسه) در
   برابرِ `test_oracle.py`.

## ۵) اجرایشدۀ همین دوره (۱۴۰۵-۰۷-۱۴، پس ازِ ممیزی) — سه اصلاحِ اثبات‌شده

فقط سه موردی که با عدد اثبات شده بودند عوض شدند؛ بقیه دست‌نخورده و درِ «مرحلۀ بعد» ثبت شد.
گارد: `dev/indicator_math_v1074.py` (۲۸ سبز / ۰ قرمز، درِ `dev/run_all_tests.py` ثبت شده) —
مرجعش همان `_audit/indicator_audit/oracle.py` و fixtureِ `fixtures_ohlcv.json`
(۶ نمادِ واقعی × ۳۰۰ کندل، درِ گیت).

| مورد | قبل | بعد | شاهد |
|---|---|---|---|
| `/api/ma` شمارند `i+1` → `w` | ۴۶٬۴۰۲/۴۶٬۴۱۴ نقطه واگرا (rel ~۹۹٪) | **۰ واگرا** از ۲۲٬۶۱۸ (ma5) · ۲۲٬۴۳۸ (ma20) · ۲۱٬۹۴۸ (ma50) · ۲۱٬۲۳۸ (ma120) نقطه، هر دو مبنای last/closing | کنترلِ منفی: حلقۀ قدیمی همان fixture را قرمز می‌کند |
| `_fts_rsi` بذرِ وایلدر | ۱٬۰۸۵–۲٬۷۷۳ سطر واگرا درِ هر دوره؛ بدترینِ Δ=۱٫۸۸ رویِ پنجرۀ ۳۵ سطری | **۰ واگرا** با تلورانسِ گردکردنِ ۱ رقم (۰٫۰۶) درِ ۶ نماد × دوره‌هایِ ۵/۷/۸/۱۴ × پنجره‌هایِ period+۲ / ۳۵ / ۶۰ / ۱۲۰ / کامل؛ بدترینِ |Δ| باقی‌مانده = ۰٫۰۵ = نصفِ گامِ گردکردن | warmup مستند: index 0…period-1 → None، نخستینِ عدد در index `period`؛ کنترلِ منفی: حلقۀ معیوب درِ همان سطر قرمز می‌شود |
| `_fts_scaled` `last := close×k` | last همیشه برابرِ closeِ ضرب‌شده (۱/۱ ردیفِ قرمز) | `closing=close_raw×k`، `last=last_raw×k` (یا صریح None)، و `close` فقط از `price_basis.apply_basis` — **۰/۲** ردیفِ پروب درِ هر دو مبنایِ last و closing | fixture واقعیِ شپنا: درِ ۶۷ سطر از ۱۲۰، last ≠ closing؛ دو مبنایِ واقعی دو عددِ متفاوت به موتور می‌دهند؛ سریِ بی‌last (مثلِ شاخصِ کل) last=None می‌ماند |

قراردادها (Candle Contract، `price_basis`، `candle_contract.widen`) تغییری نکردند؛ فقط مصرف‌کننده
از آن‌ها عبور می‌کند. هیچ کتابخانۀ تازه‌ای افزوده نشد.

**دو سنجشِ ایمنی رویِ همان fixture (پاسخِ «آیا رأیِ FTS عوض می‌شود؟»):**
  • مبنایِ closing (همان چیزی که موتور عملاً می‌خواند): هیچ‌یک ازِ شش نماد درِ
    trend/fib/jet/choch/hourglass/exit_engine تکان نخورد؛ `weekly_rsi5` بیت‌به‌بیت یکی ماند
    (خطایِ بذر رویِ سریِ بلندِ هفتگی زیرِ گامِ گردکردنِ ۰٫۱ می‌میرد).
  • مبنایِ last (که تا پیش از این جعلی بود): عددها عوض می‌شوند — jet/hourglass/exit_engine
    درِ شش از شش نماد، trend درِ سه از شش — ولی **رأیِ نهایی درِ هیچ نمادی عوض نشد**
    (hold→hold، caution→caution، exit→exit).
رأیِ pilot رویِ این دوراهی (C: موتور همیشه رویِ لنگرِ پایانی بخواند) با اطمینانِ پائین
(۰٫۵۳ / confidence ۰٫۳ / risk ۰٫۵۶) بیرون آمد و چون تصمیمِ روش‌شناسیِ جداگانه‌ای است
(«FTS-on-basis» درِ #73 صریحاً معوق شد) انجام نشد؛ درِ مرحلۀ بعد ثبت است. `api/chart.py` تنها فایلِ محصولی است که
دست خورد (+ ثبتِ گارد درِ سوئیت و fixture/اسکریپت‌هایِ `_audit/`).

## ۶) مرحلۀ بعد (ثبت‌شده، انجام‌نشده)

WaveTrend/`hlc3`↔tp (در §۸ تراجع شد: کد درست بود) · VWAPِ بی‌ریست · SuperTrendِ TR-فقط (مکانیزم
کامل در §۸) · Ichimokuیِ شکسته (۵۶ خطایِ `tsc` درِ working tree) · روش‌شناسیِ HMA (half=round) و MA_Ribbon (SMA↔EMA) ·
MACD histogram ×۲ · تقویمِ ISO درِ `confidence_engine` در برابرِ شنبۀ `chart` · برچسب‌هایِ منو با پارامترهایِ
klinecharts · `price_history.last` و `src` (§۱۰) · صفِ ۹٬۱۲۸ِ مشتقهٔ کدال · رأیِ `نشار`.


1. پیاده‌هایِ klinecharts/پکیج درِ node اجرا نمی‌شوند (DOM لازم دارند)؛ فرمولشان از source
   خوانده شد، عددشان سنجیده نشد.
2. علتِ کاملِ SuperTrend ابتدا ناشناس ماند؛ درِ دورۀ تعیین‌تکلیف (§۸) بازسازیِ عینِ کد
   با bad=۷ از ۴۶٬۴۶۲ آن را کامل توضیح داد.
3. `last` درِ `price_history` هنوز یکِ ردیفِ پر هم ندارد ⇒ هر سنجشِ «مبنایِ last» رویِ بانکِ
   کاری فعلاً همان closing است (`last_missing:N/N`)؛ دادهٔ بالا از CSV گرفتم.
4. `mabnaIndicators.ts` ویرایشِ نیشدۀ یکِ نشستِ دیگر است؛ من فقط خواندم و سنجیدم.

---

# دورۀ تعیین‌تکلیف (A/B/C) — ۱۴۰۵-۰۷-۱۴

قاعدهٔ این دور: هیچ موردی صرفاً به‌خاطرِ تفاوت با یک کتابخانه «غلط» خوانده نشد؛ اول
تعریفِ مرجع و علتِ اختلاف اثبات شد. **هیچ کدِ محصولی درِ این دور عوض نشد** — چون
اثبات نشد که هیچ‌یک ازِ چهار مظنون، باگِ زنده باشد.

## ۸) Phase A — چهار مظنون، چهار حکم

| # | مورد | حکم | شاهد |
|---|---|---|---|
| ۱ | **WaveTrend / `hlc3`** | **تراجع — کدِ فعلی درست است؛ «مرجعِ» خودِ من اشتباه بود** | سندِ رسمی Pine (v6): `hlc3 = (high + low + close)/3` و `hlcc4 = (h+l+c+c)/4` — همان چیزی که `mabnaIndicators.ts:317` می‌سازد. باندلِ مرجع هم `e.Std.hlc3(n)` را صدا می‌زند (`study_WT.js:81`) و FIBB آن را defaults دارد (`in_0:200, in_1:"hlc3", in_2:3`). نسخهٔ اولِ ممیزی مرجع را (H+L+3C)/6 («weighted close» کتابِ TA) گرفته بود ⇒ همان ۳۵٬۴۸۸ واگرایی از اشتباهِ هارنس بود نه محصول. پس ازِ تصحیحِ مرجع: **۰ واگرایی از ۴۶٬۴۶۲ سطر** (۱۲ نماد). بقیۀ زنجیر هم با بدنهٔ مرجع یکی است: CI با مقسوم‌علیهِ `0.015·EMA|·|`، هر دو EMA به طولِ n1=10، `EMA(ci,21)`، و `SMA(·,4)`ِ سخت‌کدشده. (نکته: WaveTrend نسبت‌به‌مقیاس است، پس (H+L+3C)/6 و /3 همان عدد را می‌دادند؛ تفاوت فقط درِ FIBB بود.) |
| ۲ | **VWAP** | **مرجعِ بیرونی ندارد؛ کدِ مظنون مرده است؛ نسخۀ زنده درست کار می‌کند** | رجیستری مطالعاتِ مرجع (باندل، بایت ۴٬۲۰۳٬۸۹۱) ۹ مطالعه دارد و VWAP در آن‌ها نیست؛ رشتهٔ `vwap` در ۷٫۵ مگابایت باندل صفر بار می‌آید؛ تنها میانگینِ حجمیِ مرجع `Std.vwma` (پنجره‌ای، بی‌لنگر) در FIBB است. درِ محصولِ ما VWAPِ منو از پکیج `react-klinecharts-ui` می‌آید که با ریستِ روزِ UTC درست است (`chunk-QVJHXQ4A.js:2515-2519`). نسخۀ `mabnaIndicators.ts:1013` در `MABNA_TEMPLATES` هست ولی در `MABNA_INDICATORS` نیست ⇒ هرگز register نمی‌شود. رفتارِ همان نسخۀ مرده اثبات شد: بی‌ریست، Σ تجمعی از اولِ سری (variantِ بی‌ریست bad=۰، session-anchored bad=۴۶٬۱۰۲). |
| ۳ | **SuperTrend** | **مرجع ندارد؛ نسخۀ مرده غلط است (مکانیزم کامل شناخته شد)؛ نسخۀ زنده کلاسیک است** | در مرجع هیچ SuperTrend نیست (رشته صفر؛ تنها studiۀ ATR-محور HalfTrend با ATR طولِ ۱۰۰). TR/ATRِ ماژولِ غیر-Pineِ مرجع بازیابی شد: TR از high/low/**prevClose** (بایت ۲۹۵٬۸۰۵) و smootherِ Wilder (بایت ۲۹۶٬۴۵۳) ⇒ قرائتِ کتابی. مکانیزمِ نسخۀ مرده بازسازیِ بیت‌به‌بیت شد: «TR» در واقع `max(Δ,|Δ|,Δ)=|Δclose|`؛ قفلِ بند جابه‌جا (`Up=min(lower)`، `Dn=max(upper)`)؛ و خطِ رسم درِ روندِ صعودی `Dn` است ⇒ خط بالای قیمت رسم می‌شود. اعداد: عینِ کد **۷** از ۴۶٬۴۶۲ · «TR-فقط» ۴۵٬۶۵۸ · مرجعِ کتابی ۴۴٬۶۶۲ ⇒ علت، بازچینیِ سه‌قسمتی است نه فقط TR. SuperTrendِ منو از پکیج است و کلاسیک محاسبه می‌کند. |
| ۴ | **Ichimoku** | **اجرا نمی‌شود؛ خارج از دائرۀ FTS؛ فقط گزارش** | `calcIchimoku` در node با `max is not defined` می‌شکند (۱۲/۱۲ نماد) و `tsc --noEmit` رویِ همان فایل ۵۶ خطا می‌دهد ⇒commitِ آن فایل بیلد را می‌شکند. اما Ichimokuیِ که کاربر می‌بیند از پکیج است و `(slidingMax(highs)+slidingMin(lows))/2` را درست می‌زند؛ نسخۀ repo نه register می‌شود نه در catalog است. مالکِ آن block نشستِ دیگری است؛ دست نخورد. |

## ۹) Phase B — پنج روش‌شناسی؛ همه «decision pending»

تعریفِ فعلی + تعریفِ مرجع + آنچه جزوه می‌گوید ثبت شد. **جزوه در همۀ پنج مورد سکوت دارد**
(پیمایشِ `OWNER_RULINGS.md` تا رأیِ ۲۱، `jozve_FTS_handwritten_pages_1-24/25-34`، همۀ
`transcription_p*.md`، `FTS_SPEC.md`، `FTS_SYSTEM_SPECIFICATION_v2.md`،
`FTS_CHART3_extracted_text.txt`): هیچ مطابقتی برای `SMA|EMA|WMA|RMA`، `Ribbon`،
«نوار میانگین»، `MACD`، «هیستوگرام»، `ISO`/`شنبه`/`weekStart`/«مبنای هفتگی» یا `calcParams`.
نزدیک‌ترین ارجاعِ هفتگی `OWNER_RULINGS.md:126` است («هفتگی و ماهانه در `lib/timeframe.ts`
تجمیع می‌شوند») — بی‌نام‌بردن از روزِ لنگر.

| مورد | تعریفِ فعلی (ما) | تعریفِ مرجع | جزوه/contract | نتیجه |
|---|---|---|---|---|
| HMA نصفِ دوره | `Math.round(9/2)=5` + WMA با نرمال‌سازیِ بی‌مقدار (کارِ نیمه، register نشده) | مرجع هیچ HMA ندارد؛ Halma/TA-Lib و پکیج `floor(p/2)` | سکوت | **pending** |
| MA Ribbon | نسخۀ repo: شش **SMA** (مرده) · نسخۀ پکیج (زنده): **EMA** | مرجع ندارد | فقط دوره‌ها نام دارند: `FTS_SPEC.md:23-26` (MA14 حد ضرر، MA21 حجم، MA52 هفتگی، MA100) و `jozve…:760` | **pending** |
| MACD histogram | klinecharts built-in `(dif−dea)×2`؛ پکیج و repo بدونِ ×۲ | در مرجع MACD فقط در catalogِ ماژولِ غیر-Pine است؛ ×۲ اثبات‌نشده | سکوت | **pending** (کدام هیستوگرام خوانده می‌شود) |
| سبدِ هفتگی | `api/chart.py:1140` شنبه‌محور · `confidence_engine._weekly_closes` ISO-دوشنبه | رهاورد شنبه‌محور (`CANDLE-CONTRACT.md:262`: ۲٬۹۱۹ از ۳٬۳۰۸ سبد از شنبه) | سکوت؛ §۱-ح-۵ سنجید و «به‌عمد تغییر نکرد»؛ درِ `CANDLE-CONTRACT.md:724-726` باز مانده | **pending**. اثرِ عددی: ۹٬۷۱۴ از ۱۰٬۷۰۲ سطرِ هم‌شاخص فرق می‌کند؛ درِ آن سنجش هیچ رأیی عوض نشد |
| برچسبِ منو ↔ پارامتر | منو: «MA 14/100»، «EMA 50»، «RSI 14 Wilder» (`KLineChartWrapper.tsx:2496-2499`) ولی createIndicator بی‌`calcParams` صدا زده می‌شود (`:2087-2089`) و پیش‌فرضِ klinecharts 10.0.3: MA `[5,10,30,60]`، EMA `[6,12,20]`، RSI `[6,12,24]` (سنجیده از `node_modules/klinecharts/dist/index.esm.js`) | — | سکوت | **pending** — و تنها موردی که «غلطِ ساده» است نه روش‌شناسی: کاربر عددِ دیگری می‌خواند از آنچه رسم می‌شود. دو راه: صریح ست کردنِ پارامترها، یا درست کردنِ برچسب |

## ۱۰) Phase C — `price_history.last` (بی‌هیچ re-fetch)

شش پرسش با پاسخِ عددی؛ ابزار: `_audit/indicator_audit/last_provenance.py` (**۹ سبز / ۰ قرمز**).

1. **چرا هنوز صفر است؟** سه علتِ جدا، همۀ سنجیده:
   • تاریخچۀ موجود **پیش ازِ ستونِ `last`** نوشته شده: ۳۶۵٬۶۷۰ سطر، `last` پر = ۰،
     `value` پر = ۰، `src` پر = ۰.
   • مسیرِ تابلو به منبعِ خودش نمی‌رسد: `daily_prices` ۷۲٬۳۱۱ سطر و `p_last` در **همه**
     NULL (حتی نشستِ ۲۰۲۶۰۹۳۰)، در حالی که `market_watch.p_last` ۵٬۴۵۱/۵٬۴۵۱ پر است.
     علتِ مشخص درِ کد: شاخۀ «پس ازِ بستنِ بازار» (`test_tsetmc.py:1613-1618`)
     `market_watch` را با `p_last` به‌روز می‌کند ولی `UPDATE daily_prices` همان ستون را
     درِ فهرست ندارد.
   • پس ازِ افزودنِ ستون، هیچِ سینکِ کاملی اجرا نشده (بیشترینِ `price_history.date` = ۲۰۲۶-۰۹-۳۰).
2. **منبعِ واقعی `last`:** دو تا — ستونِ `<LAST>` درِ `GetClosingPriceDailyListCSV`
   (`candle_contract.from_csv_row`، index ۱۱) و `pdv` تابلو برایِ نشستِ جاری. جای دیگری
   per-day last نیست (پیمایشِ همۀ جدول‌ها).
3. **CSVها دارند؟** بله. درِ دادهٔ ممیزی (۱۲ نماد × تا ۴٬۹۶۹ سطر) `last` برایِ همهٔ سطرها
   هست و درِ ۳۰۰ سطرِ آخرِ هر نماد، ۲۱۷ تا ۲۵۴ سطر `last ≠ close` دارد ⇒ عددِ واقعی است.
4. **بی‌re-fetchِ گسترده درمی‌آید؟ برایِ تاریخچه نه.** فقط ۲۰ نشستِ محلی در `daily_prices`
   هست و آن‌ها هم `p_last` ندارند؛ پرکردنِ تاریخچه فقط از همان CSV ممکن است (per-symbol،
   ~۰٫۱۶ ثانیه، فرمانش با مالک). برایِ آینده نه: همان یکِ ستونِ `p_last` درِ
   `UPDATE daily_prices` کافی است تا نشست‌هایِ تازه پر بمانند.
5. **FTS به lastِ تاریخی نیاز دارد؟ نه.** تک‌تک توابعِ موتور فقط
   `open/high/low/close/volume/time` می‌خوانند؛ تنها جایی که `last` لمس می‌شود
   `_fts_scaled` است که آن را به `price_basis.apply_basis` می‌دهد.
   `confidence_engine._bars` هم `last` را فقط برایِ ریزالو می‌گیرد و بعد دور می‌ریزد؛
   `tape_flags`/`mstat_engine` `p_last`ِ **تابلو** را می‌خوانند (جدولِ دیگر)؛ فرانت در
   `useCandleFeed.RawCandle` اصلاً `last` نمی‌گیرد. پس پرکردنِ `last` فقط درِ این حالت
   رأی عوض می‌کند: setting = `last` **و** سریِ fallbackِ بانک — و امروز setting `closing`
   است (`price_basis.json:2`).
6. **یک نقصِ قراردادِ دیگر، سنجیده و ثبت:** `src` درِ ۳۶۵٬۶۷۰ سطر NULL است، پس قیدِ
   مالکیتِ `UPSERT_SQL` (`WHERE COALESCE(price_history.src,'') <> ? OR excluded.src = ?`)
   همیشه true می‌شود و «published > board» رویِ این بانک بی‌اثر است — آزمونِ رفتاری نشان
   داد سطرِ board یکِ ردیفِ منتشرشده را له می‌کند، و با `src` درست له نمی‌کند. هر دو
   نویسندۀ جدید (`from_csv_row`/`from_board_row`) `src` را می‌گذارند ⇒ نقصِ داده‌هایِ
   کهنه است، نه مسیرِ نوشتن.

**حکمِ این دور:** تغییرِ کد نداشت (هیچ باگِ زنده‌ای اثبات نشد). دو اصلاحِ پیشنهادیِ بعدی،
هر دو با گاردِ عددیِ آماده: (الف) افزودنِ `p_last` به `UPDATE daily_prices` درِ شاخۀ
after-hours؛ (ب) backfillِ یک‌بارۀ `price_history.src` تا قیدِ مالکیت زنده شود. پنج مورد
Phase B در انتظارِ رأیِ صریح شماست.
