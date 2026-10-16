# FTS — گزارش ممیزی منطق (Logic Audit Report)

> **Audit snapshot، نه وضعیت جاری:** نتایج و شمارش‌های این گزارش به کد و تاریخ سنجش خود تعلق دارند. پیش از استفاده برای تصمیم یا تغییر امروز، کد جاری، تست‌ها و هر رأی بعدی مالک را بررسی کنید.

> خروجیِ دستورالعملِ بخش پنجمِ سند: **Complete Logic Audit & Implementation Amendment (نسخهٔ ۳.۰)**
> دامنه: هستهٔ بنیادی و کدال (بخش اول سند: F-01 … F-05 + ضوابط پایهٔ دریافت داده)
> روش: هر سطر با سورس‌کد زندهٔ `BorsTerminal/` تطبیق داده شده؛ اعداد و آستانه‌ها عیناً از کد استخراج شده‌اند.
> **توجه:** طبق بند ۲ دستورالعمل، این گزارش **فقط ممیزی** است؛ هیچ آستانه‌ای تغییر نیافته و قانونی اختراع نشده است.

---

## خلاصهٔ مدیریتی

| وضعیت | تعداد | توضیح |
| :---: | :---: | :--- |
| `VALID_RULE` | ۱۶ | منطبق بر جزوه و چارت FTS |
| `ENGINEERING_STANDARD` | ۲ | فرمول‌سازی صریحِ معادلِ منطق جزوه (طبق بند ۳، خطا نیست) |
| `PARTIAL` | ۲ | پیاده‌سازی ناقص یا ناتراز با سند |
| `MISSING` | ۱ | پیاده‌سازی‌نشده |
| `CRITICAL_LOGIC_ERROR` | ۰ | در دامنهٔ بنیادی/کدال مشاهده نشد |
| `DUAL_PROFILE_LOGIC` | ۰ | در لایهٔ بنیادی نیست (مربوط به بخش T/P است) |

**سه مورد نیازمند تصمیمِ صریحِ شماست** (طبق بند ۲، من حق تغییرشان را ندارم):
۱. **F-01 امتیاز کامل:** سند می‌گوید ≥۶۰٪، کد از `۵۸.۰` استفاده می‌کند + کلید `full_score_percent` در JSON مرده است.
۲. **F-01 تعدیل ناترازی فصلی انرژی:** کلاً `MISSING` — هیچ منطق فصلی‌ای وجود ندارد.
۳. **F-04 شرط پایه:** سند می‌گوید ≥۰.۳۳، کد `۱.۰` است و تستِ `dev/test_fts_market_cap.py` همین تضاد را **FAIL** می‌زند (۵۱/۵۲).

---

## بخش اول: جدول ممیزی — هستهٔ بنیادی و کدال (F)

ستون‌ها طبق فرمتِ بخش پنجم سند: `کد شاخص | لایه/ماژول | شرح قانون | وضعیت در کد | آدرس فایل/تابع | اقدام اصلاحی پیشنهادی`

### ۱. ضوابط پایهٔ دریافت داده از کدال

| کد شاخص | لایه / ماژول | شرح قانون | وضعیت در کد | آدرس فایل / تابع | اقدام اصلاحی پیشنهادی |
| :---: | :---: | :--- | :---: | :--- | :--- |
| **F-01** | Fundamental / کدال | فیلتر شرکت اصلی — صورت‌های تلفیقی مبنای محاسبه نباشند | `VALID_RULE` | [`_is_consolidated()`](BorsTerminal/fts_engine.py:458)، [`_is_audited()`](BorsTerminal/fts_engine.py:452)، [`annual_statements(exclude_consolidated=True)`](BorsTerminal/fts_engine.py:491)، [`_is_consolidated_title()`](BorsTerminal/api/fundamental.py:552) (مصرف‌کننده در :۶۷۸، :۸۲۹، :۲۳۰۵) | نیازی نیست — فیلتر در سه لایه (عنوان، پرچم، کوئری) اعمال می‌شود |
| **F-01** | Fundamental / کدال | مقیاس و واحد پولی — خام به میلیون ریال؛ ÷۱۰٬۰۰۰ → میلیارد تومان | `ENGINEERING_STANDARD` | [`MRL_TO_RIAL = 1e6`](BorsTerminal/api/fundamental.py:71)، [`BT_FACTOR = 1e-4`](BorsTerminal/api/fundamental.py:72)، `_bt()` | نیازی نیست — ثابت‌ها دقیقاً همان ضرایب سندند |
| **F-01** | Fundamental / کدال | سال مالی شناور — لزوماً ۲۹ اسفند نیست | `VALID_RULE` | [`_fiscal_year_rows()`](BorsTerminal/api/fundamental.py:1027) + تشخیص سالِ مالیِ جاری در [`dynamic_annualized_sales()`](BorsTerminal/api/fundamental.py:1026) | نیازی نیست — آخرین سالِ مالیِ معتبر از خود سری استخراج می‌شود |
| **F-01** | Fundamental / کدال | نمادهای تعلیق (نشان A) → `REJECT` قطعی | `VALID_RULE` | [`"suspended_max_stale_sessions": 3`](BorsTerminal/bors_config.py:187) + `vetoes.reject_suspended` در `fts_thresholds.json` | نیازی نیست |

### ۲. شاخص‌های پنج‌گانه

#### F-01 — رشد فروش و درآمد عملیاتی

| کد شاخص | لایه / ماژول | شرح قانون | وضعیت در کد | آدرس فایل / تابع | اقدام اصلاحی پیشنهادی |
| :---: | :---: | :--- | :---: | :--- | :--- |
| **F-01** | Fundamental | کف شرط مرزی: `Sales_Growth ≥ ۴۰٪` → کمتر `REJECT` | `VALID_RULE` | [`"growth_min": 40.0`](BorsTerminal/bors_config.py:164) → [`revenue_growth_yoy(min_growth=40.0)`](BorsTerminal/fts_engine.py:579) → مصرف در [`scan_symbol()`](BorsTerminal/fts_engine.py:1060) و [`bulk_scan()`](BorsTerminal/fts_engine.py:1203) | نیازی نیست — ۴۰٪ در سه لایه یکسان است |
| **F-01** | Fundamental | امتیاز کامل FTS (پوشش تورم): `Sales_Growth ≥ ۶۰٪` | `PARTIAL` ⚠ | سند: ≥۶۰٪ ↔ کد: [`"inflation_min": 58.0`](BorsTerminal/bors_config.py:165) → [`revenue_growth_yoy(inflation_min=58.0)`](BorsTerminal/fts_engine.py:580) و [`beats_inflation = growth >= inflation_min`](BorsTerminal/fts_engine.py:632)؛ fallbackِ [`_INFLATION_FALLBACK = 58.0`](BorsTerminal/api/fundamental.py:76)؛ کلیدِ `f01.full_score_percent: 60.0` در `fts_thresholds.json` **هیچ خواننده‌ای در پایتون ندارد (کلید مرده)** | **نیازمند تصمیم شما:** یا `inflation_min` → `۶۰.۰` شود یا `full_score_percent` به کد وصل شود. طبق بند ۲، بدون اجازه تغییر نمی‌دهم |
| **F-01** | Fundamental | تولیدی — رشد ریالی باید با تناژ همراه باشد | `VALID_RULE` | [`"volume_growth_min": 0.0`](BorsTerminal/bors_config.py:199) + [`"volume_breadth_min": 0.60`](BorsTerminal/bors_config.py:200) + شاخص ۱ب در `ind1b` + `require_volume_growth_for_manufacturing: true` | نیازی نیست — درگاه تناژ برای تولیدی فعال است |
| **F-01** | Fundamental | بانکی — تجمیع درآمدهای عملیاتی؛ تناژ `N/A` | `VALID_RULE` | [`company_profile()`](BorsTerminal/api/fundamental.py:342) (طبقهٔ financial) → `operational_revenue_basis` در [`dynamic_annualized_sales()`](BorsTerminal/api/fundamental.py:1019) | نیازی نیست |
| **F-01** | Fundamental | هلدینگ/سرمایه‌گذاری — `N/A`، وتوی منفی ندارد | `VALID_RULE` | [`"holdings_sales_na": True`](BorsTerminal/bors_config.py:183) + [`ind4_valuation(kind="holding")`](BorsTerminal/api/fundamental.py:1068) | نیازی نیست |
| **F-01** | Fundamental | **تعدیل ناترازی فصلی انرژی** — افت ۱ماههٔ سیمان/فلزات (تابستان، برق) و پتروشیمی (زمستان، گاز) مجاز | `MISSING` ❌ | جستجو برای `فصلی`/`تابستان`/`زمستان`/`season` در کل `BorsTerminal/*.py` → **هیچ منطق فصلی‌ای یافت نشد**. تنها مرجعِ «فصل»، [`ANNUALIZATION_SCALE`](BorsTerminal/api/fundamental.py:1055) (جدول ضرایب ۱۲÷n) است که چیز دیگری است | **نیازمند تصمیم شما:** آیا این قانون پیاده‌سازی شود؟ نیازمند دادهٔ ماهانهٔ ≥۱۲ماهه + برچسب صنعتِ ریز (سیمان/فلز/پتروشیمی) است. فعلاً در هیچ مسیری اثر ندارد |
| **F-01** | Fundamental | صنعت بیمه — وتوی مطلق (`REJECT`) | `VALID_RULE` | [`"mandatory_sectors"` شامل «بیمه»](BorsTerminal/bors_config.py:176) + `vetoes.reject_insurance` + [`ind5_industry()`](BorsTerminal/api/fundamental.py:1127) | نیازی نیست |

#### F-02 — سابقه سودآوری سه ساله

| کد شاخص | لایه / ماژول | شرح قانون | وضعیت در کد | آدرس فایل / تابع | اقدام اصلاحی پیشنهادی |
| :---: | :---: | :--- | :---: | :--- | :--- |
| **F-02** | Fundamental | روند EPS طی ۳ سال صعودی + سود خالص سال آخر مثبت | `VALID_RULE` | [`"eps_years": 3`](BorsTerminal/bors_config.py:167) + `strict_growth: true` / `require_positive_latest: true` در `fts_thresholds.json` + [`ind2_eps_track()`](BorsTerminal/api/fundamental.py:866) | نیازی نیست |
| **F-02** | Fundamental | افت جزئی میان‌دوره‌ای → وتوی خودکار نیست | `VALID_RULE` | `interim_confirms` در [`ind2_eps_track()`](BorsTerminal/api/fundamental.py:866) یک **سیگنال نرم** است، نه وتو | نیازی نیست — تطبیق دقیق |

#### F-03 — حاشیه سود ناخالص

| کد شاخص | لایه / ماژول | شرح قانون | وضعیت در کد | آدرس فایل / تابع | اقدام اصلاحی پیشنهادی |
| :---: | :---: | :--- | :---: | :--- | :--- |
| **F-03** | Fundamental | ایده‌آل ≥۳۰٪، کف ۲۰٪، زیر ۲۰٪ `REJECT` | `VALID_RULE` | [`"margin_optimal": 30.0`](BorsTerminal/bors_config.py:170)، [`"margin_min": 20.0`](BorsTerminal/bors_config.py:169)، [`"margin_ideal": 30.0`](BorsTerminal/api/fundamental.py:66) / [`"margin_min": 20.0`](BorsTerminal/api/fundamental.py:65) | نیازی نیست |
| **F-03** | Fundamental | استثنای دارویی: `GPM ≥ ۵۰٪` | `VALID_RULE` | [`"pharma_margin_exempt_min": 50.0`](BorsTerminal/bors_config.py:184) + `f05.pharma_min_gpm: 50` در `fts_thresholds.json` | نیازی نیست |

#### F-04 — نسبت فروش سالانه به ارزش بازار

| کد شاخص | لایه / ماژول | شرح قانون | وضعیت در کد | آدرس فایل / تابع | اقدام اصلاحی پیشنهادی |
| :---: | :---: | :--- | :---: | :--- | :--- |
| **F-04** | Fundamental | سالانه‌سازی داینامیک: `Sales_n × (۱۲ ÷ n)` | `ENGINEERING_STANDARD` | [`factor = 12.0 / months`](BorsTerminal/api/fundamental.py:1031) در [`dynamic_annualized_sales()`](BorsTerminal/api/fundamental.py:990) + [`ANNUALIZATION_SCALE`](BorsTerminal/api/fundamental.py:1055) | نیازی نیست — طبق بند ۳ سند، این فرمول‌سازی صریحِ معادل است، نه خطا |
| **F-04** | Fundamental | **شرط پایه: `Sales_to_Cap ≥ ۰.۳۳`** | `PARTIAL` ⚠ | سند: ≥۰.۳۳ ↔ کد: [`"sales_to_mcap_min": 1.0`](BorsTerminal/bors_config.py:172)، [`"sales_to_mcap_min": 1.0`](BorsTerminal/api/fundamental.py:67)، [`"v10_sales_to_mcap_min": 1.0`](BorsTerminal/bors_config.py:204). کلیدِ `f04.min_sales_to_cap_ratio` در JSON از طریق [`v10_thresholds()`](BorsTerminal/api/fundamental.py:79) خوانده نمی‌شود (فقط `sales_to_mcap_min`/`v10_sales_to_mcap_min` خوانده می‌شوند). **تستِ [`dev/test_fts_market_cap.py:295`](BorsTerminal/dev/test_fts_market_cap.py:295) که ۰.۳۳ را ادعا می‌کند، الان FAIL است (۵۱/۵۲)** | **نیازمند تصمیم شما:** کدام مرجع درست است — ۰.۳۳ِ سند یا ۱.۰ِ کد؟ پیشنهاد: یا پیش‌فرض → ۰.۳۳ و `۱.۰` به‌عنوان مرزِ ایده‌آل ثبت شود، یا سطرِ تست اصلاح شود. فعلاً تضاد دست‌نخورده باقی مانده |
| **F-04** | Fundamental | ایده‌آل: `Sales_to_Cap ≥ ۱.۰` **یا** `GP_to_Cap ≥ ۰.۴۰` | `VALID_RULE` | [`pot_pass = pot_pct >= th["potential_min"]`](BorsTerminal/api/fundamental.py:1091) با [`"potential_min": 40.0`](BorsTerminal/bors_config.py:173) (= ۰.۴۰) و [`"gate": "OR"`](BorsTerminal/api/fundamental.py:1104) + [`pass = sales_pass or pot_pass`](BorsTerminal/api/fundamental.py:1105) | نیازی نیست — درگاه OR دقیقاً سند است |
| **F-04** | Fundamental | هلدینگ‌ها `N/A` | `VALID_RULE` | همان سطرِ هلدینگِ F-01: [`ind4_valuation(kind="holding")`](BorsTerminal/api/fundamental.py:1068) | نیازی نیست |

#### F-05 — چشم‌انداز صنعت و نوع نرخ‌گذاری

| کد شاخص | لایه / ماژول | شرح قانون | وضعیت در کد | آدرس فایل / تابع | اقدام اصلاحی پیشنهادی |
| :---: | :---: | :--- | :---: | :--- | :--- |
| **F-05** | Fundamental | صنایع آزاد (سیمان/فلزات/پتروشیمی/کاشی/شیشه/…) در برابر دستوری (خودرو/نیروگاهی/شوینده/لاستیک/غذایی) | `VALID_RULE` | [`"free_sectors"`](BorsTerminal/bors_config.py:177) و [`"mandatory_sectors"`](BorsTerminal/bors_config.py:176) + [`"industry_mode": "Exclude_Mandatory_Pricing"`](BorsTerminal/bors_config.py:175) + [`ind5_industry()`](BorsTerminal/api/fundamental.py:1127) که [`fts_engine.sector_filter()`](BorsTerminal/fts_engine.py:1128) را می‌پوشاند | نیازی نیست |
| **F-05** | Fundamental | استثنائاتِ صنایع دستوری (دزاگرس با GPM>۵۰٪، وبملت با تراز ارزی) | `PARTIAL` | استثنای دارویی پوشش داده شده: [`pharma_margin_exempt_min: 50.0`](BorsTerminal/bors_config.py:184). اما **استثنای بانکیِ وبملت (تراز ارزی + درآمد تسهیلات) مکانیزمی ندارد** — هیچ کلید استثنایی per-symbol وجود ندارد | پیشنهاد (فقط با اجازه): یک فهرست `sector_exceptions` نماد-محور؛ فعلاً وبملت فقط از طریق `mandatory_sectors`/بانکی مدیریت می‌شود |

---

## بخش دوم: تطبیق برنامهٔ جاری با این سند (Reconciliation)

این بخش پاسخِ مستقیم به درخواستِ شما — «برنامه را باهاش تطبیق بده» — است.

### الف) تسک ۱۹ (مادی‌سازیِ `fts_results`) با سند **منطبق** است ✅

تسک ۱۹ در حال حاضر: کش کردنِ خروجیِ [`evaluate_v10()`](BorsTerminal/api/fundamental.py:1272) در جدولِ `fts_results` تا حلقهٔ per-row در [`get_screener()`](BorsTerminal/api/screener.py:198) (~۲۵۰۰ نماد × ۵–۸ کوئری) تبدیل به یک `SELECT` شود.

تطبیق با دستورالعمل‌های سند:
- **بند ۱ (توقف تغییرات خودسرانه):** این کار منطق را تغییر نمی‌دهد، فقط نتیجهٔ محاسبهٔ موجود را ذخیره می‌کند. خروجیِ `evaluate_v10()` قبل و بعد یکسان است.
- **بند ۲ (عدم اختراع قانون):** هیچ آستانه‌ای لمس نشده. جدول فقط ستون‌های خروجیِ موجود (`score`، `passes`، `excluded`، …) را نگه می‌دارد.
- **بند ۳ (تفکیک خطا از استاندارد مهندسی):** همین کار، تعریفِ «استاندارد مهندسی» است — کشِ نتیجه برای رفعِ N+1.

**نتیجه:** تسک ۱۹ بدون تغییر در مسیر ادامه می‌یابد.

### ب) بخش‌های T / S / P سند — خارج از فاز فعلی

سند در بخش‌های ۲ تا ۴ به موتور تکنیکال، تابلوخوانی و پورتفوی می‌پردازد. چند مورد علامت‌دار شده:
- **T-02 (`CRITICAL_LOGIC_ERROR`):** تعریف `MA(100)` در تایم‌فریم **هفتگی** به‌جای روزانه — باید در `frontend` بررسی شود.
- **T-03:** فلگ لگاریتمیِ فیبوناچی روی چارت.
- **T-04:** تفکیک حد ضررِ نوسان‌گیر (۵٪) از روندگیر (بنیادی) — `DUAL_PROFILE_LOGIC`.
- **S-02:** تطبیق موقعیتی حجم مشکوک (`tvol ≥ ۳ × bvol`).
- **P-02:** شتاب‌دهندهٔ ساعت شنی (ضریب ۲–۴ برابر در کفِ هفتگی زیر `MA52` با `RSI ≤ 30`).

این موارد در دامنهٔ پروژهٔ فعلی (FTS/Codal/DB) **نیستند** و نباید با آن مخلوط شوند. به‌عنوان فاز بعدی ثبت می‌شوند.

### ج) سه مورد نیازمند تصمیم مالک محصول

طبق بند ۲، این سه مورد را بدون اجازه تغییر نمی‌دهم:

| # | مورد | سند می‌گوید | کد می‌گوید | پیشنهاد من |
| :---: | :--- | :--- | :--- | :--- |
| ۱ | F-01 امتیاز کامل | `≥ ۶۰٪` | `inflation_min = ۵۸.۰` + کلیدِ مردهٔ `full_score_percent: ۶۰.۰` | یا `inflation_min` → `۶۰.۰`، یا اتصالِ `full_score_percent` به کد. تا زمان تصمیم، ۵۸ باقی می‌ماند |
| ۲ | F-01 ناترازی فصلی انرژی | افت ۱ماههٔ فصلی مجاز است | `MISSING` | اگر قرار باشد پیاده شود، نیاز به دادهٔ ماهانهٔ ≥۱۲ماهه + برچسب صنعتِ ریز دارد. فعلاً اولویتِ پایین |
| ۳ | F-04 شرط پایه | `Sales_to_Cap ≥ ۰.۳۳` | `sales_to_mcap_min = ۱.۰` + تستِ FAIL | مشخص کنید کدام مرجع رسمی است؛ سپس یا پیش‌فرض یا تست اصلاح می‌شود |

---

## بخش سوم: وضعیت تست‌ها

- [`dev/test_fts_market_cap.py`](BorsTerminal/dev/test_fts_market_cap.py:1): **۵۱/۵۲ PASS** — تنها FAIL، ادعای ۰.۳۳ در سطر ۲۹۵ است که خودِ تضادِ F-04 را اثبات می‌کند.
- بقیهٔ گاردهای `dev/` (که قرارداد تست هستند) دست‌نخورده‌اند.

---

## نتیجه

هستهٔ بنیادی/کدالِ FTS در ۱۶ مورد `VALID_RULE`، ۲ مورد `ENGINEERING_STANDARD` و **صفر `CRITICAL_LOGIC_ERROR`** است. سه مورد ناترازی (۲ تا `PARTIAL` + ۱ تا `MISSING`) همگی در **مقادیر آستانه/پوشش** هستند، نه در جهتِ شرط یا منطق — یعنی خطرِ تحریفِ استراتژی ندارند، اما تا تصمیم شما، دست‌نخورده می‌مانند.

تسک ۱۹ (مادی‌سازیِ `fts_results`) مطابق با سند ادامه می‌یابد و بخش‌های T/S/P به فاز بعدی موکول می‌شوند.
