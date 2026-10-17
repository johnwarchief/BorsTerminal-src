# ماتریسِ پوششِ سیگنال‌های Strategy FTS — داده، UNKNOWN و آزمون‌هایِ مرزی · 2026-10-18

> **گامِ ۳ از ترتیبِ مصوبِ مالک** (§۹ِ `docs/research/RAHAVARD-FILTERS-OWNER-DECISIONS-2026-10-18.md`).
> این سند **هیچ آستانه‌ای نمی‌سازد و هیچ فیلتری فعال نمی‌کند**؛ فقط ثبت می‌کند امروز چه چیزی سنجیده
> می‌شود، با کدام ستون‌های داده، چه وقتی «سنجیده نشد» می‌گوید، و کدام مرزِ عددی آزمونِ مستقیم دارد.
> هیچ فایلِ سورس درِ این دور تغییر نکرد.

| بند | مقدار |
|---|---|
| تاریخ | 2026-10-18 · 1405-07-26 |
| مرجعِ کد | `f9cea521` (= `github/main`)؛ شاخۀ `docs/rahavard-screener-technical-2026-10-18` |
| اسنادِ هم‌خانواده | `docs/research/RAHAVARD-SCREENER-TECHNICAL-FILTERS-2026-10-18.md` (گزارشِ #37) · سندِ تصمیم‌هایِ مالک · `docs/fts-notes/OWNER_RULINGS.md` (رأیِ ۲۵) |
| روش | خواندنِ ایستای `funnel_registry.py`، `tape_flags.py`، `funnel_engine.py`، `api/funnel.py`، گاردهایِ `dev/` و `tools/`، و `frontend/src/__tests__/` |
| شمارش‌ها | از `grep -rl` رویِ همین درخت؛ «۰» یعنی هیچ فایلی درِ آن مجموعه آن نشانه را ندارد |

---

## ۱. چطورِ خوانده شود

| اصطلاح درِ این سند | معنا (منبع) |
|---|---|
| `canonical` | فیلتری که درِ `FILTERS` رجیستری است و منبعش اثرِ انگشتیِ sha256 دارد |
| `availability=backend-partial` | «بعضی قیدهایِ فایل هنوز درِ بانک سنجیده نمی‌شوند» (`funnel_registry.py:75`) |
| UNAVAILABLE | «سنجیده نشد»؛ درِ `funnel_engine.py:46` صریحاً از REJECT جداست: «UNAVAILABLE ≠ REJECT» |
| PENDING | «سنجیده نشد رد نیست» (`funnel_engine.py:19`) |
| آزمونِ مرزی | آزمونی که مقدارِ آستانه را دست‌کم یکی بالا/پایین ببرد و نتیجه برعکس شود |

---

## ۲. هفت فیلترِ canonicalِ تابلویی

| فیلتر | منبع (sha-pegged) | پارامترها (configurable فقط جایی که جزوه گفته) | ستون‌هایِ داده که واقعاً می‌خواند | چه‌وقت UNAVAILABLE می‌شود | آزمون/گارِدِ موجود |
|---|---|---|---|---|---|
| `f_clock` الگوی ساعت | `docs/الگوی ساعت.txt` | `clock_delta` = 0.02 **قفل** (تعارضِ X-1: چارت ۳ و `FTS_SPEC.md:73` عددِ ۱٪ را می‌آورند؛ رأیِ ۱۸ «گد رو عین فرمول‌ها بکن») · `vol_mult` = 1.0 **دستِ کاربر** 1.0–5.0 · `min_trades` = 30 · `base_sessions` = 30 | `p_last`, `p_closing`, `tvol`, `prior30_vol`, `z_tot_tran` | `z_tot_tran` بی‌عدد ⇒ همه؛ و برایِ همین فیلتر `p_closing` بی‌عدد ⇒ UNAVAILABLE (`funnel_engine.py:260`) | `dev/tape_filters_v1034.py`، `dev/funnel_registry_v1.py`، `tools/tape_formula_parity.py`، `frontend/src/__tests__/tape-fuzz-parity.spec.ts` |
| `f_susp` حجم مشکوک | `docs/حجم مشکوک.txt` | `vol_mult` = 3.0 **دستِ کاربر** 2.5–5.0 · `min_trades` = 50 · `base_sessions` = 30 | `tvol`, `prior30_vol`, `z_tot_tran` | `z_tot_tran` بی‌عدد؛ یا `hist_sessions` < 30 | `dev/tape_filters_v1034.py`، `tools/tape_parity_fuzz.py`، `tools/tape_formula_parity.py` |
| `f_jet` فیلتر جت | `docs/فیلتر جت.txt` | `vol_mult` = 3.0 قفل · `buyer_power` = 1.5 قفل · `resistance_ladder` = 2,5,9,19,29,39,49,59 · `min_trades` (تعارضِ X-3/Q-2: «درِ قیف هنوز رأیِ صریح ندارد») | `p_last`, `p_closing`, `h*_max` (پنجره‌هایِ ladder), `z_tot_tran`, `buy_i_vol`, `sell_i_vol`, `buy_count_i`, `sell_count_i`, `tvol`, `prior30_vol` | `z_tot_tran` بی‌عدد؛ یا `hist_sessions` < 30 | `tools/jet_ladder_yield.py`، `tools/tape_formula_parity.py`، `dev/tape_filters_v1034.py` |
| `f_roobi` کف روبی صف فروش | `docs/کف روبی صف فروش.txt` | `plp_max` = −1 · `zd1_min` = 1 · `qd1_min` = 100 | `plp`/`percent_last`, `p_last`, `tmin`, `buy_q1_cnt`, `buy_q1_vol` | `tmin` بی‌عدد یا `buy_q1_cnt`/`buy_q1_vol` بی‌مقدار (`funnel_engine.py:254-257`)؛ پنجرۀ ۳۰ نشست **نمی‌خواهد** | `dev/tape_filters_v1034.py` — و تنها جایِ دیگرِ `ROOBI_QD1_MIN` درِ `tapeMath.ts` است |
| `f_noqteh` نقطه زنی | `docs/نقطه زنی.txt` | `max_dist` = 3٪ · `low_window` = 29 (تعارضِ X-4/Q-3: کرانِ `dist>=0` بی‌رأی وارد شده بود و رأیِ ۲۰ پس داد) · `vol_mult` = 1.0 · `min_trades` = 5 | `p_closing`, `min_low_29`, `tvol`, `prior30_vol`, `z_tot_tran` | `min_low_29` بی‌عدد یا `hist_sessions` < `LOW_BASE_SESSIONS` (29) | `dev/tape_filters_v1034.py` (تنها مصرف‌کنندۀ `NOQTEH_MAX_DIST`) |
| `f_smart` ورود پول هوشمند | `docs/ورود پول هوشمند.txt` | `vol_mult` = 1.5 · `buyer_power_ge` | `tvol`, `is6`, `p_closing`/`p_last`, `prior30_vol`, `buy_i_vol`, `sell_i_vol` | همان قاعدهٔ عمومیِ `z_tot_tran` / `hist_sessions` < 30 | `dev/tape_smartmoney_v1074.py`، `dev/tape_filters_v1034.py`؛ **availability = backend-partial**: دو variant با مبناءهایِ `[is5]/[is6]` سنجیده **نمی‌شوند** |
| `f_legal` کد به کد حقوقی→حقیقی | `docs/ورود پول هوشمند و کد به کد حقوقی به حقیقی.txt` | `legal_share` = 0.5 | `tvol`, `buy_i_vol`, `sell_n_vol` | همان قاعدهٔ عمومی | `dev/tape_smartmoney_v1074.py`؛ `LEGAL_SHARE_OF_TVOL` بیرونِ آن و بیرونِ `tape_flags` جای دیگری آزمونِ مستقیم ندارد |

نکتۀ ساختاری که از جدولِ بالا پیداست: **۴ فیلترِ از ۷ فقط با `z_tot_tran` و `hist_sessions` داوریِ قطعی
می‌گیرند**؛ اگر آن دو نباشد، UNAVAILABLE است نه رد. دو فیلتر (`f_roobi`, و تا حدی `f_smart`) قیدهایِ
تاریخچۀ حجمِ ۳۰-نشسته نمی‌خواهند.

## ۳. گیت‌ها و presetها

| شیء | مقدارِ فعلی | برچسب | شاهد |
|---|---|---|---|
| `TREND_GATE` | `trend_matrix` — «هفتگی داورِ جهت، روزانه داورِ ورود»؛ درِ `_fts_analyze_candles` (:2791) ساخته می‌شود (`out["trend"]["matrix"]` درِ :2840-2891) و وتو درِ :2651 خوانده می‌شود | `DOCUMENTED` | `funnel_registry.py:273-275` |
| `HOURGLASS_GATE` | `hourglass_ma52_rsi5_weekly`؛ سیگنال درِ `out["hourglass"]` (:2946) ساخته می‌شود و تنظیمش از `_fts_hourglass_settings` (:40) می‌آید؛ presetِ hourglass **زنجیره‌اش تهی** و `status="unverified"` | `OWNER_APPROVAL_REQUIRED` (نام/API) — بررسی‌اش فقط مستندسازی | `funnel_registry.py:276`, `:292-296` · رأیِ ۲۴ · رأیِ ۲۵ بندِ ۵ |
| preset `swing` | `f_clock` → `f_jet` → `f_susp` + گیتِ روند | `DOCUMENTED` | `funnel_registry.py:279-283` |
| preset `trend` | `f_roobi` → `f_noqteh` + گیتِ روند؛ حجمِ مشکوک عمداً نیست («روندگیر: به حجم مشکوک نیازی ندارد») | `DOCUMENTED` | `funnel_registry.py:285-289` |
| preset `hourglass` | زنجیره تهی؛ فقط گیتِ ساعت‌شنی | `VALIDATION_PENDING` (Q-1ِ باز) | `funnel_registry.py:291-296` |
| preset `custom` | کاربر از کلِ رجیستری می‌چیند؛ پیش‌فرضی تحمیل نمی‌شود | `DOCUMENTED` | `funnel_registry.py:298-302` |
| «خشک کردن» | عمداً درِ رجیستری نیست: «نام درِ چارت ۳ هست، فرمول هیچ‌جا نیست ⇒ NOT FOUND» | `DOCUMENTED` | `funnel_registry.py:268-269` |

## ۴. سیگنال‌هایِ جزوه‌ای که فیلترِ رجیستری **نیستند**

این‌ها درِ موتورِ خروج/ستاپ حساب می‌شوند یا نباید بشوند؛ ستونِ آخر می‌گوید آیا واردِ قیف می‌شوند یا نه.

| سیگنال | جایِ محاسبه | واردِ قیف؟ | وضعیتِ مستند |
|---|---|---|---|
| واگراییِ RSI(14) | `_fts_exit_layer4` درِ `api/chart.py:2496`؛ پرچمِ `rsi_divergence` درِ :2533 (Wilderِ اوراکل‌سنجیده) | نه — لایۀ خروج/شاهد | MATCH درِ `FTS-TREND-CLASSIFIER-AUDIT-1405-07-13.md:41` |
| MA14 «یک کندلِ کامل زیر MA» | `_fts_exit_layer1` (دو بدنهٔ متوالی) | نه | **MISMATCH منبع/کد** — همان ممیزی :39؛ نیازمندِ اصلاحِ implementation با رأیِ جدا |
| جت (ستاپِ چارت، با مهلتِ ۳ روز) | `_fts_jet_setup` درِ `api/chart.py:1899` با `entry_window_days=3`؛ نردبانِ 2/5/9/19/29/39/49/59 + کندلِ سبز | `f_jet` درِ قیف هست؛ اینکه مهلتِ ۳ روز درِ داوریِ لحظه‌ای مصرف می‌شود **درِ این دور سنجیده نشد** (گزارشِ ۱۴۰۵-۰۷-۰۷ آن را «فقط متن» خوانده بود) | `docs/CHART-FOUR-PAGES-PARITY.md:36` «متن» |
| فیبوناتچی 33–40 و 61.8–70 | `_fts_fib_zones` درِ `api/chart.py:1855` (مقیاسِ لگاریتمی) | درِ گیتِ روزانۀ نزولی | MATCH درِ همان ممیزی :35؛ «۳۰٪» فقط فرضیۀ تحقیقاتی بود و آستانه نشد |
| CHoCH · کف دوقلو · نقطه‌زنیِ ستاپ | `_fts_choch` :2043، `_fts_double_bottom` :2187، `_fts_point_hunt` :2112 | CHoCH درِ گیت؛ کف دوقلو «متن» بود و به ستونِ setup اضافه شد | `CHART-FOUR-PAGES-PARITY.md:22, :38` |
| پولبک (بازگشتی) | ساخته نشده | نه | «نیفتاده» درِ `CHART-FOUR-PAGES-PARITY.md:20` و همان ممیزی :34 |
| ساعت‌شنیِ «سهام بزرگ و بنیادی» | هیچ‌جا داوری نمی‌شود | نه | `CHART-FOUR-PAGES-PARITY.md:37` «نیفتاده» |
| بنیادی (۵ شاخص، سه تای اول بلاکر) | `fts_engine` / `api/fundamental` | بله، لایۀ جدا | `CHART-FOUR-PAGES-PARITY.md:30` اختلافِ «سه بلاکر» با جمعِ پنج‌امتیازی |

## ۵. مسیرِ UNKNOWN: چه چیزی درست کار می‌کند و کجا شک دارد

| # | رفتارِ سنجیده‌شده (کدِ موجود) | پیامد |
|---|---|---|
| 1 | درِ `tape_flags.py` هر هفت پرچم با `.fillna(False)` تمام می‌شوند (سطرهایِ 216، 222، 234، 276، 303، 349، 364) | درِ لایۀ پرچم، «نبودِ داده» و «نخوردن» یکی می‌شوند: هر دو False |
| 2 | `funnel_engine.py:235-265` `_tape_unmeasurable` همان False را با شواهدِ خودِ ردیف به UNAVAILABLE برمی‌گرداند، با آستانه‌هایِ خودِ `tape_flags` (نه عددِ تازه) | تفکیکِ درست درِ قیف انجام می‌شود |
| 3 | آن تفکیک **بسته** است، نه باز: اگر ردیف هیچ‌کدام از `hist_sessions`، `prior30_vol`، `min_low_29`، `tmin` را نداشته باشد، تابع `return False` می‌کند (`:250-252`) — یعنی پرچمِ بک‌اند تنها داوریِ صادق می‌ماند و «ساخته‌نشدن» به «سنجیده‌نشدن» ترجمه نمی‌شود | ردیف‌هایِ پنلِ قدیمی/ساختهٔ تست بی‌علامتِ UNKNOWN می‌مانند؛ این تصمیمِ خودِ کد است و درِ کامنتِ `:246-249` نوشته شده، اما هیچ آزمونِ مستقلی رویِ آن این دو مسیر را کنارِ هم مقایسه نمی‌کند (`_tape_unmeasurable` تنها درِ `tools/funnel_unmeasured_impact.py` ظاهر می‌شود) |
| 4 | `_unmeasured_why` علت را نام می‌برد («کدام ورودی کم است») و رابطِ تابلو هم نمایشِ «ارزیابی‌نشده» دارد (`frontend/src/__tests__/tape-unevaluated-display.spec.tsx`) | نمایشِ UNKNOWN درِ فرانت پوششِ آزمون دارد |

## ۶. آستانه‌ها و پوششِ مرزیِ هر کدام

| ثابت | مقدارِ فعلی | چه چیزی همان عدد را مصرف می‌کند | آزمونِ مرزیِ مستقیم (±یک واحد) |
|---|---|---|---|
| `VOL_BASE_SESSIONS` | 30 | پنجرۀ حجمِ ۴ فیلتر | درِ `dev/tape_filters_v1034.py`؛ آزمونِ 29/30 نشستِ مجزا یافت نشد |
| `LOW_BASE_SESSIONS` | 29 | کرانِ `f_noqteh` | همان گارد + `tapeAlgorithms.ts`/`tapeMath.ts`؛ مرزِ 28/29 مجزا نیست |
| `CLOCK_DELTA` | 0.02 | `f_clock` | `dev/tape_filters_v1034.py` و `tapePatterns.ts` + `tape-patterns.spec.tsx`؛ با تعارضِ ثبت‌شدهِ ۱٪ (X-1) |
| `SUSP_VOL_MULT` | 3.0 (دامنهٔ کاربری 2.5–5.0) | `f_susp` | گاردِ دامنه درِ `dev/funnel_registry_v1.py`؛ آزمونِ رفتارِ رویِ 2.5/5.0 یافت نشد |
| `SUSP_TRADES` | 50 | `f_susp` | فقط `dev/tape_filters_v1034.py` |
| `CLOCK_TRADES` | 30 | `f_clock` | بیرونِ `tape_flags.py` و `funnel_registry.py` هیچ فایلِ آزمون/گاردی آن را نام نمی‌برد (`grep -rl` = 0 درِ dev/tools/tests) |
| `JET_VOL_MULT` / `JET_BUYER_POWER` | 3.0 / 1.5 | `f_jet` | `tools/jet_ladder_yield.py` پانجرۀ ladder را می‌سنجد؛ سرانۀ خریدِ مرزی نه |
| `ROOBI_MAX_CHANGE` / `ROOBI_ZD1_MIN` / `ROOBI_QD1_MIN` | −1 / 1 / 100 | `f_roobi` (backend-partial) | `dev/tape_filters_v1034.py` + `tapeMath.ts`؛ نبودِ ستونِ `qd1` درِ دادهٔ واقعی سنجیده نشده |
| `NOQTEH_MAX_DIST` / `NOQTEH_TRADES` | 3٪ / 5 | `f_noqteh` | فقط `dev/tape_filters_v1034.py` |
| `SMART_VOL_MULT` / `SMART_BP_GE` / `LEGAL_SHARE_OF_TVOL` | 1.5 (`tape_flags.py:84`) / 1.0 با قاعدهٔ `>=` (`:85`) / 0.5 (`:90`) | `f_smart`، `f_legal` | `dev/tape_smartmoney_v1074.py` |

جمعِ بی‌رأیِ این جدول: پوششِ **درستیِ فرمول** خوب است (پاریتیِ سطر‌به‌سطر با سایت، fuzz، yield)، ولی پوششِ
**مرزِ یک‌واحدیِ آستانه‌ها** برایِ پنج ثابت عملاً صفر است. این «کمبودِ آزمون» است، نه «آستانهٔ غلط»؛
هیچ‌کدام از اعدادِ بالا درِ این سند تغییر نمی‌کند و پیشنهادِ عدد هم نمی‌شود (رأیِ ۲۵: آستانه‌ها رأیِ مالک است).

## ۷. ایرادِ تازه‌ای که همین ممیزی پیدا کرد: `test_refs` به فایلی اشاره می‌کند که هرگز وجود نداشته

| پرسش | پاسخِ شاهددار |
|---|---|
| نشانه | `funnel_registry.py:117` = `_TESTS = ("dev/test_tape_flags_v1059.py", "tools/tape_formula_parity.py")` |
| وضعیتِ فایل | درِ این ورک‌تری وجود ندارد؛ `git log --all -- dev/test_tape_flags_v1059.py` **هیچ** کامیتی برنمی‌گرداند (نه درِ `main`، نه درِ هیچ ref دیگری) — پس حذف نشده که هرگز اضافه نشده |
| دامنهٔ اثر | شش فیلتر `test_refs=_TESTS` را به‌ارث می‌برند (`f_clock` یک موردِ اضافه هم دارد)؛ `FunnelFilter.as_json` آن را درِ payload می‌گذارد و `api/funnel.py:176` همان `as_json()` را برمی‌گرداند ⇒ رشته درِ پاسخِ API است |
| آیا درِ رابط دیده می‌شود؟ | **NOT_VERIFIED** — `grep -rn "test_refs"` درِ `frontend/src` و `api/` هیچ مصرف‌کننده‌ای پیدا نکرد؛ ممکن است درِ Trace عمومی نمایش داده شود |
| چرا گارد نگرفتنش؟ | `dev/funnel_registry_v1.py` هیچ‌جا `test_refs` را چک نمی‌کند (خروجِ grep = ۰)؛ پس مسیرِ معتبر نبودنِ فایل‌هایِ اعلام‌شده را می‌پیماید |
| پوششِ واقعیِ آزمون چیست؟ | همان کاری که نامِ فایلِ phantom وعده می‌دهد درِ `dev/tape_filters_v1034.py`، `tools/tape_formula_parity.py`، `tools/tape_parity_fuzz.py` و `frontend/src/__tests__/tape-fuzz-parity.spec.ts` موجود است ⇒ ایراد از نوعِ **ارجاعِ غلط درِ زنجیرۀ اثبات** است، نه نبودِ تست |
| ریسکِ اصلاح | یک رشته درِ یک فایلِ ریشه؛ قراردادِ داده‌ای عوض نمی‌شود (مقدارِ `list[str]` همان می‌ماند). اگر مصرف‌کننده‌ای بعداً متنِ `test_refs` را نمایش دهد، متنِ مسیر درِ UI عوض می‌شود |
| وضعیتِ اقدام | **تغییری داده نشد.** اصلاحِ ارجاع = تغییرِ فایلِ `funnel_registry.py` که درِ محدودۀ §0 نیست و نیازمندِ رأی است |

## ۸. گامِ بعدیِ پیشنهادی (بدونِ اجرای این دور)

| # | کار | فایل‌ها | قراردادِ داده | آزمون | ریسکِ regression |
|---|---|---|---|---|---|
| ۱ | رأیِ صریح رویِ تعارضِ X-3 (آیا `f_jet` درِ قیف کفِ تعدادِ معامله می‌خواهد؟) | فقط `funnel_registry.py:183` (note) | بی‌اثر | بی‌آزمون | صفر تا داوری عوض نشود |
| ۲ | درست کردنِ ارجاعِ `test_refs` به فایل‌هایِ واقعی (یا حذفِ نشانهٔ phantom) | `funnel_registry.py:117` + افزودنِ بررسیِ مسیر درِ `dev/funnel_registry_v1.py` | payload فقط متن عوض می‌کند | گاردِ جدید: هر `test_refs` باید درِ دیسک موجود باشد | پایین؛ ولی درِ محدودۀ §0 است ⇒ رأی |
| ۳ | افزودنِ آزمونِ مرزیِ ±واحد برایِ پنج ثابتِ بی‌پوشش | `dev/` (گاردِ جدید) یا `tests/` | بی‌اثر | خودش آزمون است | صفر (فقط افزودنِ آزمون) |
| ۴ | ماتریسِ «مجبور به UNKNOWN» برایِ هر فیلتر با دادهٔ واقعیِ امروز | `tools/funnel_unmeasured_impact.py` موجود است؛ گسترشِ گزارش | فقط خواندنِ `market.db` با `mode=ro` | بی‌تغییرِ کد | صفر |
| ۵ | تصمیمِ تکلیفِ §۵.۳ (ردیفِ بی‌ستون: False یا UNKNOWN) | `funnel_engine.py:250-252` | تغییرِ وضعیت‌ها درِ payload ⇒ اثرِ UI | نیازمندِ آزمونِ جدید + سنجشِ جابه‌جاییِ رأی‌ها | **بالا** — همین‌جا توقف می‌کنم و رأیِ شما را می‌خواهم |

## ۹. چه چیزی راستی‌آزمایی نشد

- اینکه `test_refs` درِ رابطِ Trace نمایش داده می‌شود یا نه (NOT_VERIFIED، §۷).
- اینکه `qd1`/`buy_q1_vol` درِ دادهٔ زندهٔ امروز برایِ چند نماد وجود دارد (فقط خواندنی و انجام نشد).
- پوششِ عددیِ هر فیلتر رویِ بانکِ امروز (چه شمارِ نمادی PASS/REJECT/UNAVAILABLE می‌گیرند) — درِ این دور
  شمارشِ تازه‌ای از قیف گرفته نشد؛ §۶ فقط ارجاع‌ها را می‌شمارد.
- هر ادعایِ «برابریِ عددی با رهاورد» برایِ غیر از RSI(14) (گزارشِ #37 §۹: یک نماد، یک روز).
