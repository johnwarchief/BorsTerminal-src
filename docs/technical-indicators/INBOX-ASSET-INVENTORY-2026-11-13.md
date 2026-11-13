# فهرست اولیه دارایی‌های اندیکاتور و الگو — 2026-11-13

**شاخه مبنا:** `main`  
**مخزن:** `johnwarchief/BorsTerminal-src`  
**مسیر کانونیکال:** `docs/technical-indicators/inbox/`  
**وضعیت این سند:** `PRELIMINARY STATIC INVENTORY` — طبقه‌بندی اولیه بر اساس درخت فایل و خواندن نمونه‌های متنی؛ نه ممیزی کامل الگوریتم‌ها و نه تأیید برای ورود به محصول.

## ۱. موجودی فایل‌ها

در snapshot شاخه `main`، پوشه inbox شامل ۱۱۵ فایل است:

| نوع فایل | تعداد | تفسیر اولیه |
|---|---:|---|
| `.mq4` | ۵ | سورس MQL4؛ نوع واقعی هر فایل باید از ساختار کد تشخیص داده شود |
| `.mq5` | ۴ | سورس MQL5؛ شامل Indicator، Expert Advisor و ابزار |
| `.txt` | ۴۱ | چند فایلِ بررسی‌شده در واقع Pine Script هستند؛ پسوند فایل زبان منبع را تعیین نمی‌کند |
| `.ex4` | ۱۳ | فایل کامپایل‌شده MT4؛ منطق داخلی بدون سورس قابل ممیزی کامل نیست |
| `.ex5` | ۱۰ | فایل کامپایل‌شده MT5؛ منطق داخلی بدون سورس قابل ممیزی کامل نیست |
| `.jpg` | ۳۹ | تصویر و نمونه نمایشی؛ به‌تنهایی اثبات‌کننده فرمول یا صحت خروجی نیست |
| `.rar` | ۱ | آرشیو؛ محتوای آن در این بررسی استخراج نشده است |
| `.md` | ۲ | مستندات و راهنمای دریافت فایل |
| **جمع** | **۱۱۵** | موجودی فایل‌ها، نه تعداد الگوریتم‌های مستقل |

> چند نمونه از فایل‌های `.txt` با امضای `//@version=5/6` و اعلان `indicator(...)` شروع می‌شوند و سورس Pine Script هستند. پیش از هر پردازش باید زبان و نوع واقعی فایل تشخیص داده شود.

## ۲. نقشه اولیه قابلیت‌ها و دارایی‌های نامزد استفاده مجدد

این جدول فقط نامزدهای ممیزی را مشخص می‌کند. وجود نام یا کد در inbox به معنی صحت الگوریتم، مجوز استفاده، non-repainting بودن یا ادغام‌شدن در BorsTerminal نیست.

| قابلیت تکنیکال | دارایی‌های موجود در inbox | استفاده پیشنهادی در معماری |
|---|---|---|
| ساختار بازار، سوئینگ و HH/HL/LH/LL | `Indicator/New folder (7)/Human_Level_Structure_Engine.mq5`؛ `Indicator/New folder (6)/Indi 225.txt` (BOS/CHoCH/FVG)؛ `Indicator/New folder (8)/Indi 476.txt` (SMC/OB)؛ `Indicator/New folder (33)/Indi 607.txt` (swing exhaustion) | مقایسه با `major_swings.py`، `trend_classify.py` و `structure_engine3.py`؛ استخراج تفاوت واقعی، نه ساخت موتور موازیِ تکراری |
| کف/سقف دوقلو و شکست سطح | `Indi 516.txt` (Double Tap 3D)؛ `Indi 518.txt` (Double Breakout Failed Level)؛ `Indicator/New folder (10)/Indi 248.txt` (S/R Retest Breakout) | ساخت مجموعه الگوهای تأییدشده با نقاط پیوت، خط گردن/زون، وضعیت تأیید و زمان رخداد |
| خط روند، کانال و وج | `Indicator/New folder (17)/Indi 584.txt` (Trendlines/Breakouts/Retests)؛ `Indicator/New folder (27)/Indi 442.txt` (Pivot Channel TrendLines)؛ `Indicator/New folder (9)/Indi 407.txt` (Wedge & Channel Detector)؛ `Indi 82.txt` (3rd Wave BB TrendLines) | استخراج محاسبه خطوط، تماس‌ها، شکست و retest؛ بررسی تأخیر تأیید پیوت و repaint |
| فیبوناچی، Pitchfork و موج‌شماری | `Indicator/New folder (24)/Indi 155.txt` (Pitchfork/Fib/ZigZag)؛ `Indicator/New folder (34)/Indi 337.txt` (Golden Zone)؛ `Indicator/New folder (35)/Indi 101.txt` (Elliott Wave + Fib)؛ `Indicator/New folder (31)/Indi 609.txt` (ML Fibonacci Extensions) | استفاده به‌عنوان مرجع/کاندید برای anchor، swing و نواحی؛ آزمون مستقلِ زمان‌مندی و نگاه‌به‌آینده |
| واگرایی و مومنتوم | `Indicator/New folder (21)/Indi 472.txt` (Multi-Indicator Divergence + ADX)؛ `Indicator/New folder (23)/Indi 247.txt` (RSI Divergence Optimizer)؛ `Indicator/New folder (18)/BBRSI&MA_v2@IndicatorsforTV.mq4`؛ `Indicator/New folder (13)/BandsRSI@IndicatorsforTV.mq4` | مقایسه با RSI/سیگنال‌های موجود؛ استانداردسازی پیوت‌های قیمت و اسیلاتور و زمان رخداد واگرایی |
| رنج، فشردگی، حجم و نقدینگی | `Indicator/New folder (19)/Indi 588.txt` (Range Profile Structure)؛ `Indicator/New folder (32)/Indi 608.txt` (Quiet Range Tracker)؛ `Indi 533.txt` (Liquidity/Dealing Range/CVD) | استخراج ویژگی‌های رنج، فشردگی و حجم؛ CVD یا عمق بازار فقط در صورت وجود داده معتبر و هم‌زمان |
| روند و پولبک | `Indicator/New folder (12)/Indi 251.txt` (Supertrend Pullback)؛ `Indicator/New folder (16)/Indi 218.txt` (Pullback Sniper)؛ `Indi 84.txt` (Adaptive Ichimoku)؛ `Indicator/New folder (36)/Brooky_Rsi_Ichimoku@IndicatorsforTV.mq4` | مقایسه با trend/MAهای موجود و استخراج فیلترهای مستقل؛ عدم تبدیل مستقیم سیگنال‌های بازارهای دیگر به قانون بورس تهران |
| مدل‌های مبتنی بر ML در سورس‌های ارسالی | `Indicator/New folder (29)/Indi 268.txt` (Machine Learning Smart Money Concepts)؛ `Indicator/New folder (31)/Indi 609.txt` (ML Fibonacci Extensions)؛ `Indicator/New folder (2)/Machine Learning Regression Trend.ex5` | فقط منبع ایده و نامزد آزمایش؛ الزام ممیزی کامل label timing، look-ahead، train/test split و leakage پیش از هر استفاده پیش‌بینانه |

## ۳. فایل‌هایی که نباید به‌عنوان اندیکاتور خالص وارد شوند

| فایل | تشخیص اولیه از سورس | برخورد معماری |
|---|---|---|
| `Breakout Retest Pro EA Source Code @IndicatorsforTV.mq4` (در ریشه و کپی `Indicator/New folder (4)/`) | Expert Advisor؛ شامل تنظیمات ورود/خروج، SL/TP، مدیریت موقعیت و سفارش | فقط منطق مستقل تشخیص شکست/پولبک/کندل برگشتی پس از جداسازی و ممیزی بررسی شود؛ هیچ منطق سفارش یا اجرای بروکر منتقل نشود |
| `Gold Snap  v1.0.mq5` | EA با `CTrade`، مدیریت لات، ریسک و سفارش | اندیکاتور نیست؛ صرفاً نامزد استخراج فرضیه‌های سطح/شکست، پس از ممیزی |
| `Range Breakout With Filter.mq5` | فایل معاملاتی با payload رمز/مبهم در بخش‌هایی از سورس | اجرا یا انتقال نشود؛ تا زمان دسترسی به منطق شفاف و قابل ممیزی، قرنطینه |
| `Indi 538.txt` (Gold Breakout 15M Strategy) | اسکریپت Strategy، نه صرفاً indicator | در صورت نیاز فقط فرضیه‌های range breakout بررسی شوند؛ تنظیمات زمان/نماد طلا مستقیماً به بورس تهران تعمیم داده نشود |
| `Replay Tool.mq5` | ابزار replay و ترسیم | ابزار پژوهش/QA است، نه الگوریتم سیگنال |

## ۴. وضعیت منابع غیرقابل ممیزی مستقیم

- فایل‌های `.ex4` و `.ex5` تا زمان ارائه سورس متناظر، توضیح معتبر سازنده و مجوز، black-box باقی می‌مانند. آن‌ها نباید اجرا، decompile یا به‌عنوان الگوریتم تأییدشده معرفی شوند.
- تصاویر فقط مرجع دیداری‌اند. برای پیاده‌سازی به فرمول، رفتار عددی و نمونه خروجی timestampدار نیاز است.
- فایل RAR در این inventory استخراج نشده است.
- برخی فایل‌های Pine در توضیحات خود مجوزهایی مانند MPL-2.0 ذکر می‌کنند؛ مجوز باید برای هر فایل جداگانه و از منبع اصلی بررسی شود. وجود متن مجوز در یک فایل، مجوز سایر فایل‌ها را ثابت نمی‌کند.
- کپی تکراری احتمالیِ `Breakout Retest Pro EA` در دو مسیر با SHA یکسان در snapshot فعلی مشاهده شد؛ قبل از catalog نهایی، deduplication بر مبنای blob SHA انجام شود. پوشه قدیمی `docs/Indicator` نیز جداگانه در مخزن موجود است و باید از نظر duplicate بودن با مسیر کانونیکال مقایسه شود.

## ۵. جریان اجباری استفاده مجدد (Reuse-First Intake)

1. **Inventory و dedup:** ثبت path، blob SHA، عنوان داخل سورس، سازنده/منبع، زبان، نوع واقعی (Indicator/Strategy/EA/Script/Library)، نسخه و فایل‌های همراه.
2. **ممیزی منطق:** استخراج فرمول و پارامترها، ورودی‌ها و خروجی‌ها، حداقل تاریخچه، تایم‌فریم، کندل مورد استفاده، رفتار کندل ناقص، confirmation delay، repainting و look-ahead.
3. **ممیزی مجوز و امنیت:** بررسی license/provenance، وابستگی‌ها و هرگونه کد سفارش/شبکه/فایل؛ کد ناشناس اجرا نشود.
4. **مقایسه با موجودی BorsTerminal:** ابتدا بررسی شود آیا همان قابلیت در `api/chart.py`، `major_swings.py`، `trend_classify.py`، `structure_engine3.py` یا لایه FTS موجود است. خروجی یکسان نباید موتور یا منبع حقیقت دوم بسازد.
5. **استخراج و بازپیاده‌سازی مستقل در صورت لزوم:** سورس Pine/MQL مستقیماً runtime وابسته به TradingView/MetaTrader نمی‌شود؛ فقط منطق قابل استفاده، با رعایت مجوز و بدون وابستگی پلتفرمی، به قرارداد Python/Backend تبدیل می‌شود.
6. **آزمون و برچسب وضعیت:** واحد، fixture، prefix-stability، anti-repaint، anti-lookahead، parity عددی، کارایی و در صورت امکان مقایسه با Rahavard. وضعیت‌ها باید صریح باشند: `UNREVIEWED`، `REVIEWED`، `EXPERIMENTAL`، `VALIDATED`، `REJECTED`.
7. **ارتقای مرحله‌ای:** فقط پس از شواهد و تست، سند به `reviewed/` و سپس در صورت ادغام و تست سبز به `implemented/` منتقل شود.

## ۶. تصمیم معماری

**اصل قطعی: Reuse First, Rebuild Only on Proven Gap.**

- اولویت با استفاده از اندیکاتورها، توابع و موتورهای موجود در BorsTerminal و سپس دارایی‌های قابل ممیزی در inbox است.
- هیچ الگوریتمی صرفاً به دلیل وجود فایل، تأیید یا وارد محصول نمی‌شود.
- توسعه از صفر فقط وقتی مجاز است که ممیزی نشان دهد قابلیت وجود ندارد، منبع موجود قابل استفاده/مجوزدار نیست، با قرارداد داده ناسازگار است یا در آزمون کیفیت شکست می‌خورد.
- این snapshot هنوز ممیزی کامل ۱۱۵ فایل نیست؛ مرحله بعد، تکمیل manifest تک‌به‌تک و اجرای آزمون‌های قابلیت‌های اولویت‌دار است.
