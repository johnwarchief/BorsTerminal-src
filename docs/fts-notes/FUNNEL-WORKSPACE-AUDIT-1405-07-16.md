# قیف FTS ⇒ Decision Workspace — ممیزیِ پیش از کد (۱۴۰۵-۰۷-۱۶)

> **Snapshot پیش از پیاده‌سازی:** عنوان و نتایج این سند مربوط به ممیزی پیش از کد در ۱۴۰۵-۰۷-۱۶ است. آن را فهرست قطعیِ کمبودهای فعلی فرض نکنید؛ هر مورد باید با کد، کامیت‌های بعدی و رفتار مرورگر امروز دوباره تأیید شود.


مأموریت: قیف را از «نمایشِ چند فیلتر» به قلبِ Decision Workspace استراتژی FTS
تبدیل کن. این سند **فقط ممیزی** است — هیچ کد درِ این دور عوض نشده. هر سطرِ
ادعا file:line یا فایل+سطرِ منبع دارد. هرچه منبع ندارد صریح
`UNVERIFIED`/`NOT FOUND` خورده است؛ هیچ آستانه‌ای از خودِ ما اضافه نشده.

منابعِ خوانده‌شده: `docs/*.txt` (همۀ هفت فیلتر)، `docs/fts-notes/OWNER_RULINGS.md`،
`docs/FTS_SPEC.md`، `docs/FTS_SYSTEM_SPECIFICATION_v2.md`،
`docs/fts-notes/jozve_FTS_handwritten_pages_1-24.md` و `_25-34.md`،
`docs/fts-notes/NOTEBOOK-PARITY-F1-F5.md`، `docs/fts-notes/FTS_CHART3_extracted_text.txt`،
`docs/جزوه FTS.pdf`.
کد: `tape_flags.py`، `fts_engine.py`، `api/{chart,fundamental,screener}.py`،
`frontend/src/features/master/**`، `frontend/src/features/market/lib/tapeAlgorithms.ts`،
`frontend/src/features/fundamental/**`.

> `docs/جزوه FTS.pdf` لایۀ متن ندارد (۳۴ بایتِ استخراجی؛ صفحۀ ۲–۶ تصویرِ JPX).
> متنِ جزوه از همان دو ترانویس و `FTS_CHART3_extracted_text.txt` خوانده می‌شود —
> چارت ۳ برخلافِ جزوه لایۀ متن دارد (رأی ۱۲).

---

## ۱) رجیستریِ فیلترهایِ canonical از منبع

| فیلتر | منبع (سطر) | چه می‌گیرد | آستانه‌ها، عینِ منبع | وضعیت |
|---|---|---|---|---|
| الگوی ساعت `f_clock` | `docs/الگوی ساعت.txt:1` | آخرین ≥ پایانیِ ۲٪ + حجمِ روز > میانگینِ ۳۰ نشست + تعدادِ معامله | `(pl)>=(pc)*1.02` · `(tvol)>1*(Σ[ih][0..29].QTotTran5J/30)` · `(tno)>30` | COMPLETE |
| حجم مشکوک `f_susp` | `docs/حجم مشکوک.txt:1` | حجمِ ۳ برابرِ میانگین + تعدادِ معامله | `(tvol)>3*(Σ…/30)` · `(tno)>50` | COMPLETE |
| فیلتر جت `f_jet` | `docs/فیلتر جت.txt:1` | حجم + قدرتِ خریدار + شکستنِ سقفِ ایستای ۸ پنجره | `(tvol)>3*(Σ…/30)` · `Buy_I_Volume/Buy_CountI >= 1.5 × Sell_I_Volume/Sell_CountI` · `(pl)>=(pc)` · `(plp)>0` · `(pl) > [ih][59,49,39,29,19,9,5,2].PriceMax` · `(tno)>1 && (tno)>100` | COMPLETE |
| کف‌روبیِ صف فروش `f_roobi` | `docs/کف روبی صف فروش.txt:1` | قفل رویِ کفِ صف فروش با خریدارِ سنگین | `(pl)==(tmin) && (zd1)>1 && (plp)<-1 && (qd1)>100` | COMPLETE |
| نقطه‌زنی `f_noqteh` | `docs/نقطه زنی.txt:1-24` | نزدیکِ کفِ ماه (زیرِ ۳٪) + حجم + تعداد | `round(((pc)-minimum)/(pc)*100*100)/100 < 3` · پنجرۀ `n<29` · `(tvol)>1*(Σ…/30)` · `(tno)>5` | COMPLETE |
| ورود پول هوشمند `f_smart` | `docs/ورود پول هوشمند.txt:1-3` | حجمِ ۱٫۵ برابر + قدرتِ خریدارِ حقیقی | `(tvol)>1.5*(Σ…/30)` · `Buy_I_Volume/Buy_CountI >= Sell_I_Volume/Sell_CountI` · `(pl)>=(pc)` · `(plp)>0` | COMPLETE |
| پول هوشمند + کد‌به‌کد حقوقی→حقیقی `f_legal` | `docs/ورود پول هوشمند و کد به کد حقوقی به حقیقی.txt:1-3` | دو بالا + جابه‌جاییِ کد | `(ct).Buy_I_Volume>0.5*(tvol)` · `(ct).Sell_N_Volume>0.5*(tvol)` | COMPLETE |
| «خشک کردن» | نام در `FTS_CHART3_extracted_text.txt` (بلوکِ روندگیر) | — | فرمول هیچ‌جا نیست | **NOT FOUND** |

دو فیلترِ آخر (`f_smart`, `f_legal`) درِ بک‌اند ساخته می‌شوند
(`tape_flags.py:351-352`) ولی درِ قیف جایگاه ندارند: `FILE_FILTERS`
پنج‌تاست (`frontend/src/features/master/lib/ftsFunnel.ts:44`) و هفت‌تا فقط درِ
چیپ‌هایِ تابلو هست (`tapeStore.ts:14` `QUICK_FILTERS`). **پس رجیستریِ فعلیِ
قیف، کلِ منبع را نمی‌پوشاند** — همان چیزی که مأموریت ممنوع می‌کند.

تنظیم‌هایِ قابل‌تغییرِ ثبت‌شده درِ جزوه (نه اختراعِ ما):
ضریبِ حجمِ الگوی ساعت «۱ را به ۳ یا ۵ تغییر دهیم»
(`jozve…1-24.md:610-611`، چارت ۳ سطر ۹۰) · `tno>200` به‌جایِ کف‌روبیِ سخت
(`…:616`) · حجمِ مشکوک بینِ ۲٫۵ تا ۵ (`…:615-618`).

## ۲) تعارضِ منبع‌ها و رأیِ حاکم

| # | تعارض | مرجع‌ها | حاکم |
|---|---|---|---|
| X-1 | فاصلۀ قیمتِ الگوی ساعت | TXT `1.02` (۲٪) · چارت ۳ «بیشتر از ۱٪» · `FTS_SPEC.md:73` `1.01×` · `v2:137` `plp-pcp>=1.0` | رأی ۱۸: «گد رو **عین فرمول‌ها** بکن» ⇒ TXT = ۱٫۰۲ |
| X-2 | مبنایِ حجم | TXT `Σ[ih][0..29]/30` · `FTS_SPEC.md:24,74` «Volume MA 21» | رأی ۱۸ بند ۲ صریحاً مبن را از `month_avg_vol` به همان Σ/۳۰ عوض کرده ⇒ TXT |
| X-3 | `tno>100` درِ جت | TXT دارد · رأی ۱۷ «در هیچ‌کجای جزوه و چارت ۳ عددی برای حداقلِ تعدادِ معامله درِ جت نیست» | رأی ۱۸ آن را برای **بجِ تابلو** نگه داشته؛ برایِ قیف باید صریح برچسب بخورد که از TXT آمده، نه از جزوه |
| X-4 | کرانِ `dist >= 0` درِ نقطه‌زنی | TXT فقط `(cfield2)<3` | رأی ۲۰: کرانِ `>=0` بی‌رأی واردِ کد شده بود ⇒ مردود، مگر رأیِ تازه |
| X-5 | کفِ شاخص ۴ | `v2:50` «>= 1.0» · رأی ۴ «کف قبولی **۰٫۳۳**، ایده‌آل **۱٫۰**» | رأی ۴ (سندِ متأخرِ مالک) |

## ۳) presetها از منبع

| preset | فیلترهایِ منبع، به همان ترتیب | شاهد |
|---|---|---|
| نوسان‌گیر | حجم مشکوک ← الگوی ساعت ← کف‌روبی (مهندسِ معکوس) / درِ چارت ۳: ساعت + جت + حجم مشکوک | `FTS_CHART3_extracted_text.txt` بلوکِ «فیلتر / نوسانگیر» · «مهندسی معکوس ۱-تابلو خوانی فیلتر حجم مشکوک الگوی ساعت کف روبی ۲-تکنیکال ۳-بنیادی» · `jozve…1-24.md:508` |
| روندگیر | کف‌روبی + نقطه‌زنی (ورود در کفِ سوم یا پنجم)؛ «به حجم مشکوک نیازی ندارد و رشد حجم معاملات» | چارت ۳ بلوکِ روندگیر · `jozve…1-24.md:584`، `:540`، `:508` |
| ساعت‌شنی | **هیچ فیلترِ تابلویی ندارد**؛ تعریفش تکنیکالِ هفتگی است: `MA=52` و `RSI=5` هفتگی، «درِ تایم هفتگی یا بالاتر فقط کار می‌کند»، «حداکثرِ ۱۰ تا ۲۰ سهم» | `jozve…25-34.md:74`، `:66`، `:79` · چارت ۳ سطر ۱۴۱ · `FTS_SPEC.md:94-100` (RSI ۵ یا ۷ زیرِ ۳۰ یا ۲۰، پلۀ ۲ تا ۴ برابر) |
| Custom | ساختۀ کاربر از کلِ رجیستری | خودِ مأموریت |

پیادۀ فعلی (`ftsFunnel.ts:75-84` `PRESET_ENTRY`): swing = `f_clock,f_jet,f_susp`
(= چارت ۳، درست) · trend = `f_roobi,f_noqteh` (درست) · hourglass = `f_roobi,f_clock`
(**بی‌منبع** — ساعت‌شنی فیلترِ تابلویی ندارد) · custom = پنج‌تایی.
ساعت‌شنی درِ بک‌اند واقعاً پیاده است (`api/chart.py:2767-2790`: MA52 هفتگی با
کمتر از ۵۲ کندل «نظر نمی‌دهد»، RSI5 ≤ ۳۰) ⇒ جایِ درستش **گیتِ تکنیکال** است،
نه دو فیلترِ تابلوییِ قرضی. وضعیتِ presetِ ساعت‌شنی: **UNVERIFIED تا رأیِ مالک**.

`TAPE_PRESETS` درِ `tapeAlgorithms.ts:141-205` (`scalp`/`jet_trend`/`sniper`/
`smart_money`) با اعدادِ ۱٫۵/۱٫۲/۴۰/۵/۱٫۳/۲٫۰/۲٫۵/۳٫۰ … **هیچ‌کدام درِ هیچ
منبعی نیستند** و همان‌هاست که رأی ۱۸ ممنوع می‌کند. این‌ها یا به رجیستریِ
canonical وصل می‌شوند یا حذف.

## ۴) وضعیتِ کد: چهار داورِ موازی

خواستِ مأموریت: **یک** داورِ canonical؛ فرانت فقط نمایش/ناوبری/توضیح.

| حکم | بک‌اند | فرانت | وضعیت |
|---|---|---|---|
| پرچم‌هایِ تابلو | `tape_flags.py:211-353`، درِ `/api/market` | `tapeAlgorithms.ts:281-361` همان فرمول‌ها؛ `tapeFilterVerdict` (:409-414) **اول فرمولِ فرانت**، پرچمِ بک‌اند فقط وقتی ورودیِ تاریخچه نیست | فرانت داورِ اول است |
| گیتِ روند هفتگی/روزانه | `api/chart.py:2703-2747` (`trend.matrix`: REJECT/PERMITTED/UNKNOWN) | `ftsFunnel.ts:425-468` `techMark` + `strictGates.ts:262` `weeklyVeto` + `ftsPipelineEvaluator.ts:339` | سه بازنویسی |
| امتیاز/حکمِ بنیادی | `fts_engine.py:1926-1928` + `api/screener.py:363-419` | `ftsFunnel.ts:476-503` `fundMark` · `strictGates.ts:239-253` (کفِ ۲۰ خودش) · `ftsPipelineEvaluator.ts:407-423` (۴/۳) · `fundamentalSignals.ts:118-132` (امتیازِ ۰-۱۰۰ و `direction` از P/E میانۀ صنعت) · `SymbolInspector.tsx:490` | پنج بازنویسی |
| فهرستِ نهاییِ کاندید | هیچ | `ftsFunnel.ts:801-920` `buildFunnel` | فقط فرانت |
| زنجیرۀ موازیِ دیگر | — | `masterMath.ts:82-120` (`runGatingPipeline`، مصرف‌کننده: `MasterPage.tsx:113`) | پنجمین مسیر |

`ftsPipelineEvaluator.ts:241-249` فاصلۀ ۱٪ برایِ ساعت می‌زند درحالی‌که TXT و
`tape_flags.py:62` دو درصد است — یعنی داورهایِ موازی **متفاوتند**، نه فقط تکراری.
بک‌اند هم دو حسابِ موازی دارد: `api/fundamental.py` (`evaluate_v10`) و
`fts_engine.bulk_scan`، به‌علاوه `confidence_engine.py:885-886,1010-1027`.

## ۵) معنایِ زنجیره: اشتراکِ ترتیبی؟

`buildFunnel` واقعاً ترتیبی است: جوامعِ تابلو (`:570-582`،
`entryFilters.some(tapeFilterVerdict)`) ← `techKept` (`:849-851`) ← تقسیمِ
بنیادی (`:855-859`) ← `handover` (`:871`). شمارۀ هر مرحلۀ input/matched/removed
تا حدی هست (`StageSummary` `:176-181`)، ولی درِ حالتِ «اولِ تابلو» مرحلۀ تابلو
`dropped: 0` می‌دهد (`:897`) چون ورودی‌اش از پیش فیلتر شده — یعنی **شمارۀ
مرحله درِ یکی از دو حالتِ فعلی معنا ندارد**. `GatePipeline.tsx:86` برایِ همان
نماد زنجیرۀ F→T→S می‌زند (ترتیبِ دیگر) ⇒ دو معنایِ متناقض از یک قیف.
ترتیبِ فیلترها قابلِ چیدن نیست (`STAGE_KEYS:133`، `ORDER:75`)؛
`screenOrder` (`tapeStore.ts:38-44,257,317`) ساخته شده و **هیچ مصرف‌کننده‌ای
ندارد** (کنترلِ مرده).

## ۶) سقف‌هایِ پنهان رویِ جوامع (ممنوعِ مأموریت)

| سقف | کجا | اثرِ واقعی |
|---|---|---|
| `TECH_QUERY_CAP = 60` | `useFtsTechBoard.ts:77` + `slice(0, TECH_QUERY_CAP)` (:88) و `ftsFunnel.ts:620` | حکمِ زندۀ `/api/fts` فقط برایِ ۶۰ نماد («جامعۀ ۶۰ از ۱۱۰۶» در `ROUND-M-FUNNEL-PERF.md:34-38`) |
| `watchlist_max = 50` | `bors_config.py:669` → `api/screener.py:444-448`، و غنی‌سازیِ تکنیکال/وتوی هفتگی فقط رویِ همان ردیف‌ها (`screener.py:456-458,517-519`)، `fts_engine.py:2005-2006` `[:cap]` | داورِ تکنیکالِ بک‌اند رویِ ۵۰ نماد محاسبه می‌شود، نه ۹۲۲ |
| `DEFAULT_LIMIT = 60` | `useScreener.ts:46,86` · `useWatchlist.ts:12,39` · `useStopLossBoard.ts:82` `slice(0,20)` | مسیرهایِ مجاور |
| `?limit=` بی‌مصرف | `useFtsScreen.ts:105-106` می‌فرستد، `api/screener.py:202-203` نمی‌پذیرد | امروز بی‌اثر، فردا تله |

نمایشِ مجازی‌سازی‌شده (`FtsScreenTable`، ثابت‌شده در `fts-perf-probe.spec.tsx`)
ممنوع نیست؛ **کاهشِ داده** ممنوع است.

## ۷) Decision Trace

هست: `why` (متنِ آزاد)، `status` چهارحالته (`ftsFunnel.ts:194-195`،
`StageStatus:86`)، `score`، `trendW/trendD`، `techSource` (`:210`)،
`screenRank`، `assemblyVeto/assemblyWhy`، `screenAsOf/techAsOf` (`:162-166`)،
`as_of` و `thresholds` درِ پاسخِ بک‌اند (`screener.py:533-534`).

نیست (خواستِ مأموریت): `decision_id` · `reason_codes[]` ساختاریافته (همه‌جا
نثرِ فارسی است) · `rule_id` · `source_ref` برایِ هر مرحله · `parameter_set`
مهرشده رویِ هر کاندید · `engine_version` و `ruleset_version` (APP_VERSION فقط
درِ کلیدِ کش می‌نشیند، `screener.py:235`، و هرگز درِ ردیف نمی‌آید).

## ۸) دروازۀ بنیادی: I1..I5

آستانه‌ها **ردیابی‌شدنی‌اند** و هیچ‌کدام اختراعِ ما نیست:

| شاخص | کجا | آستانه | منبع |
|---|---|---|---|
| I1 رشد فروش | `fts_engine.py:834-875`، کارت `api/fundamental.py:514-564` | کف ۴۰٪، هدف ۶۰٪ | `OWNER_RULINGS.md` رأی ۳ · `v2:18-19` |
| I2 EPS سه‌ساله | `fts_engine.py:931-1137` | سه سالِ صعودی و همۀ سودده | `v2:27-30` + جزوۀ ص ۴ |
| I3 حاشیۀ ناخالص | `fts_engine.py:1156-1194` | کف ۲۰٪، استاندارد ۳۰٪ | رأی ۲ |
| I4 فروش ۱۲ماه ÷ ارزش بازار | `fts_engine.py:1261-1358,1584-1646` | کف ۰٫۳۳، ایده‌آل ۱٫۰ | رأی ۴ |
| I5 نرخ‌گذاری | `fts_engine.py:1649-1711` | جدولِ صنایعِ ص ۶ | جزوه + `v2:54-57` (افزودۀ تأییدنشدۀ «شوینده/قند/بیمه» — `NOTEBOOK-PARITY-F1-F5.md:52`) |

سه ایرادِ ساختاری:

1. **AND-gate وجود ندارد.** `api/fundamental.py:1206-1229`:
   `score = sum(5)` و `verdict = STRONG if score>=4 and primary_score==3 else
   WATCH if score>=3 else REJECT`. یعنی یک بلاکرِ شکسته + I4 + I5 = WATCH.
   سنجشِ امروز رویِ `market.db` (۹۲۲ نماد، `bulk_scan`): **۳۰۷ نماد**
   `score>=3` با `primary_score<3` (نمونه: خار، شپديس، رمپنا، كگل، مارون).
   نقضِ صریحِ رأی ۵: «**سه آیتم اول بلاکرند**».
2. **بی‌داده ⇒ پاس یا ردِ بی‌صدا.** I1 بی‌مخرج `pass:False` (۲۶۳ ردیفِ
   `rev_growth=None`)؛ I2 سابقۀ ناقص `pass:False` (۵۴۲ ردیف)؛ I4 بی‌ارزشِ بازار
   `pass:False` (۸۴ ردیف)؛ **I5 با صنعتِ خالی پاس** (`sector_filter:1709`؛
   ۵۰۴ ردیفِ `neutral` که ۱۲۹تایش `sector_name` تهی دارد)؛ I3 تنها سه‌حالۀ
   درست است (`fts_engine.py:1876` `None`) ولی درِ کارت با `bool(...)` به صفر
   می‌نشیند (`api/fundamental.py:1197`، `screener.py:374`). `PENDING` درِ
   بک‌اند اصلاً وجود ندارد. فرانت هم `strictGates.ts:239-252` نبودِ عدد را
   «نقض» نمی‌شمارد و `fundamentalSignals.ts:118-132` بی‌امتیاز عددِ ۲۲ می‌سازد.
3. **جبرانِ بی‌داده با دادۀ یتیم:** `net_margin_proxy`
   (`api/fundamental.py:1157-1166`، `ind4_valuation:937-939`) وقتی I3 سنجیده
   نشده به I4 عدد می‌دهد و پاس می‌کند.

تازگی: کارتِ بنیادی `period`/`period_end`/`market_cap_asof/stale` دارد؛
**ردیفِ اسکرینر هیچ timestampِ هر-شاخصی ندارد**؛ `market_cap_snapshots`
(۵۳۹۱ ردیف) نوشته می‌شود و هیچ‌جا خوانده نمی‌شود.

## ۹) دروازۀ پذیرش — نگاشتِ ۲۲ بند

| بند | وضعیتِ امروز | فاصله |
|---|---|---|
| Full universe | ✗ | دو سقفِ ۶۰ و ۵۰ (بند ۶) |
| Canonical filter registry | ✗ | پنج‌تاییِ hardcoded؛ `f_smart`/`f_legal` بی‌جایگاه؛ هیچ متادیتایی نیست |
| Custom builder | ✗ | افزودن/کم‌کردن از چیپ؛ بی‌ترتیب، بی‌ذخیره/تغییرِ نام/کپی/reset |
| Sequential intersection | ~ | زنجیره ترتیبی است ولی شمارۀ مرحلۀ تابلو درِ یک حالت معنا ندارد |
| Reordering | ✗ | `screenOrder` مرده |
| Presets | ~ | سه‌تاییِ hardcoded درِ فرانت؛ ساعت‌شنی بی‌منبع |
| Swing / Trend verified | ✓ | با شاهدِ چارت ۳ و جزوه (بند ۳) |
| Hourglass verified/marked | ✗ | باید به گیتِ تکنیکالِ موجود وصل و `UNVERIFIED` برچسب بخورد تا رأیِ مالک |
| Fundamental Auto/Smart | ✗ | AND-gate نیست |
| I1/I2/I3 mandatory | ✗ | رأی ۵ نقض می‌شود (۳۰۷ نماد) |
| I4/I5 supporting | ✗ | درِ همان `score>=3` |
| Decision trace / reason codes / provenance | ✗ | بند ۷ |
| Parameters/presets | ~ | `funnelPrefsStore` + `bors_tape_filter_config_v2` + `TAPE_PRESETS` (سه منبعِ پراکندۀ آستانه) |
| TSE/TSETMC validation | ~ | `tape-fuzz-parity` و `tools/tape_parity_fuzz.py` پنج فیلتر را می‌سنجند؛ دو فیلترِ پول‌هوشمند و presetها نه |
| Browser validation | ✗ | harness هست (`tools/jev_ui_check.mts`)، سناریویِ قیف نه |
| Regression tests | ~ | سه پروندۀ قیف رفتار را قفل کرده ولی **فرمولِ فرانت** را مرجع می‌گیرد |
| Performance | ~ | عدد ثبت‌شده درِ `ROUND-M-FUNNEL-PERF.md`؛ با حذفِ سقف‌ها باید بازسنجیده شود |
| No hidden caps | ✗ | بند ۶ |
| One canonical judge | ✗ | بند ۴ |

## ۱۰) مرحلۀ اجرا (همان ترتیبِ مأموریت؛ هر مرحله یک کامیت)

1. **R — رجیستریِ canonical درِ بک‌اند:** یک واحدِ `funnel_registry.py` با
   `filter_id/name/description/source_file/source_hash/formula_version/params/
   availability/backend_impl/test_ref` از هفت فیلترِ TXT؛ `f_smart`/`f_legal`
   داخلِ زنجیره؛ `TAPE_PRESETS` یا به منبع وصل شود یا حذف.
2. **E — موتورِ قیفِ واحد:** `POST/GET /api/funnel` با زنجیرۀ ترتیبیِ
   intersection، شمارۀ input/matched/removed برایِ **هر** مرحله، گیتِ تکنیکال
   (`trend.matrix` + `hourglass`) و گیتِ بنیادیِ `I1∧I2∧I3` با چهار حالت
   PASS/REJECT/PENDING/UNAVAILABLE، و Trace با `reason_codes[]`/`rule_id`/
   `source_ref`/`parameter_set`/`data_timestamp`/`engine_version`/`ruleset_version`.
3. **C — حذفِ سقف‌ها:** `TECH_QUERY_CAP` و `watchlist_max` از راهِ محاسبه
   از‌پیش‌ساخته/دسته‌ای برداشته شود (virtualization فقط نمایش)، با بازسنجشِ
   زمانِ `/api/screener` و `/api/funnel`.
4. **U — UI:** یک Workspace با زنجیرۀ فعال، چیدنِ ترتیب، presetها، Why Panel
   دو سطحی، و بی‌داوریِ تازه؛ `tapeFilterVerdict` از مرجعِ فرانت به مصرف‌کننده
   تبدیل شود (آینۀ زنده فقط با گاردِ برابریِ موجود).
5. **T — تست:** زنجیره، ترتیب، اشتراک، جامعۀ کامل، چهار preset، هر نه حالتِ
   بنیادی، reproduceپذیری؛ بعد سنجشِ زنده درِ Chromium و ۲۰ نمادِ واقعی
   در برابرِ تابلوخوانی/TSETMC.

## ۱۱) آنچه برایِ رأیِ مالک می‌ماند (هیچ‌کدام اجرایِ بند ۱ را معطل نمی‌کند)

| # | پرسش | چرا رأی می‌خواهد |
|---|---|---|
| Q-1 | ساعت‌شنی درِ قیف: فقط گیتِ تکنیکال (MA52/RSI5 هفتگی) یا فیلترِ تابلویی هم دارد؟ | منبع فیلترِ تابلویی ندارد؛ کدِ امروز `f_roobi,f_clock` را قرض گذاشته |
| Q-2 | `tno>100` جت درِ **قیف** هم لازم است یا فقط بجِ تابلو؟ | تعارضِ X-3 (TXT در برابرِ رأی ۱۷/۱۸) |
| Q-3 | کرانِ `dist>=0` نقطه‌زنی برگردد یا نماند؟ | رأی ۲۰ آن را بی‌رأیِ ثبت‌شده می‌داند |
| Q-4 | شمارۀ ۵۰/۱۰/۵-۷ رأی ۶ (مانور اولیه/واچ‌لیست/سبد) درِ Workspace مرحلۀ **هدف** است یا سقفِ محاسبه؟ | مأموریت سقفِ پنهان ممنوع کرده؛ تبدیلش به مرحلۀ دیدنی رأی می‌خواهد |
| Q-5 | I5 با صنعتِ خالی: `UNAVAILABLE` یا `REJECT`؟ | ۵۰۴ ردیفِ امروز پاس می‌گیرند |
