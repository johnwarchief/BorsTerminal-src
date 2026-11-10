# گزارش اصلاح‌شدهٔ بررسی و پالایش Technical Indicator Inbox

- **تاریخ:** 2026-11-10
- **شاخه:** `mission/technical-indicator-inbox-curation-2026-11-10`
- **مبنای اصلی:** `main` در `9a919e82f5b836cc7ec4be5ba04a39ec2f74b4e2`
- **وضعیت:** نسخهٔ اصلاح‌شده؛ این سند تصمیم اولیهٔ شتاب‌زده را supersede می‌کند.
- **دامنه:** فقط اسناد و فایل‌های زیر `docs/technical-indicators/`؛ هیچ Runtime code تغییر نکرده است.

## ۱) اصلاح تصمیم قبلی

در بازبینی اولیه، `Indi 516.txt` (Double Tap) و چند فایل Ichimoku و سایر باینری‌ها به‌دلیل نداشتن سورس خوانا یا هم‌پوشانی احتمالی، زودهنگام از Inbox خارج شدند. این استدلال کافی نبود. «قابل‌خواندن نبودن فرمول باینری» یا «وجود مفهوم مشابه در محصول» دلیل حذف یک نامزد پژوهشی نیست.

در این نسخه:
- **Double Tap** با اولویت بالا حفظ شده است.
- سورس **Adaptive Ichimoku** و هر دو باینری Ichimoku حفظ شده‌اند.
- تمام باینری‌های احتمالی اندیکاتور در `binary-review-pending/` نگه داشته شده‌اند؛ صرفاً به‌دلیل عدم دسترسی به سورس حذف نمی‌شوند.
- سه سورس Pine دیگر (Failed Breakout Level، Third Wave BB، StormCore composite) در صف بررسی باقی مانده‌اند.
- فقط مواردی از Inbox خارج می‌شوند که ساختار سورس‌شان به‌وضوح EA، Strategy یا ابزار Replay باشد؛ این خروج از Inbox اندیکاتور به معنی حذف از کل پژوهش پروژه نیست.

## ۲) دسته‌بندی فعلی

### اولویت بالا

| مورد | قابلیت | چرا نگه داشته می‌شود؟ |
|---|---|---|
| Double Tap 3D | Double Top/Bottom، neckline، score، RSI/volume divergence، stop/targets | یک Pattern Detection کامل با lifecycle است؛ ارزش آزمون و مقایسه دارد. |
| Adaptive Ichimoku Nexus | خطوط کلاسیک/تطبیقی، Kumo، TK، Chikou، MTF، breakout/retest و momentum | می‌تواند لایهٔ روند/زمینه و چندسیگنال پیشرفته بسازد؛ ارزش آن به چند خط سنتی محدود نیست. |
| Ichimoku Cloud EX5 | باینری MT5 | به‌عنوان variant مستقل حفظ شده؛ رفتار هنوز تأیید نشده. |
| Ichimoku Signals Cloud EX4 | باینری MT4 | variant سیگنال‌محور حفظ شده؛ رفتار هنوز تأیید نشده. |
| Liquidity & Structure | BSL/SSL، sweep، FVG/iFVG، supply/demand | چند ماژول مستقل با ارزش بررسی؛ بخش CVD فعلاً proxy مبتنی بر جهت کندل است، نه order flow واقعی. |

### اولویت متوسط / اکتشافی

| مورد | موضوع | وضعیت |
|---|---|---|
| MSnR Double Breakout Failed Level | شکست ناموفق سطح | close-confirm در بخش رویدادها دارد؛ باید با ساختار swing و سطح‌های خودمان مقایسه شود. |
| 3rd Wave BB TrendLines | موج سوم، ZigZag، BB، RSI، trendline | وابستگی خارجی ZigZag و ریسک hindsight/repaint باید بررسی شود. |
| StormCore SMC/Div/ST+ | SuperTrend، HTF FVG/OB/CHoCH، divergence | بستهٔ ترکیبی باید ماژول‌به‌ماژول ارزیابی شود، نه یکجا پذیرفته شود. |
| سایر EX4/EX5ها | نامزدهای نامشخص | تا زمان مشاهدهٔ خروجی و/یا دریافت سورس در وضعیت BINARY_REVIEW_PENDING باقی می‌مانند. |

## ۳) Double Tap — یافته‌های فنی واقعی

سورس `Indi 516.txt` یک Pine v6 indicator است، نه صرفاً یک overlay تزئینی:
- پیوت high/low را با `pivLeft=8` و `pivRight=5` تأیید می‌کند؛ مختصات پیوت به `bar_index-pivRight` برمی‌گردد، پس تأخیر تأیید باید در خروجی ما جداگانه ثبت شود.
- دو سقف/کف را با فاصلهٔ min/max bars و tolerance مبتنی بر ATR تطبیق می‌دهد.
- neckline از extreme بین دو پیوت ساخته می‌شود و شرط پاکیزگی هندسی دارد.
- ارتفاع الگو باید حداقل `1.5 × ATR` باشد.
- score از peak match، RSI divergence، volume divergence، height، symmetry و prior trend ساخته می‌شود.
- سیگنال شکست با close نسبت به neckline ساخته می‌شود و EMA/volume filter اختیاری دارد.
- TP1/TP2 با ضریب ارتفاع الگو، حد ابطال با buffer ATR و انتقال stop به break price پس از TP1 دارد.
- state machine برای forming، active، success، failed و timeout دارد؛ برخورد stop و target در یک کندل را stop فرض می‌کند.

مواردی که باید تست شوند:
- گارد نداشتن سراسری `barstate.isconfirmed`: pivot تأییدشده است، ولی state/رسم روی کندل باز می‌تواند intrabar تغییر کند. `alert.freq_once_per_bar_close` برای alert وجود دارد، اما برای اثبات anti-repaint کافی نیست.
- ATR زمان تأیید پیوت دوم در score و matching مصرف می‌شود؛ با ATR زمان وقوع pivot مقایسه شود.
- score و Grade وزن‌های hand-crafted هستند و probability یا edge اثبات‌شده نیستند.
- win-rate داشبورد ظاهراً timeoutها را در denominator کامل لحاظ نمی‌کند و نباید معیار عملکرد معتبر تلقی شود.
- رفتار روی قیمت خام/تعدیل‌شده، کندل‌های کم‌حجم و دادهٔ دارای گپ باید بررسی شود.

نتیجه: **RETAIN — HIGH PRIORITY / NOT YET VERIFIED**. هیچ‌یک از این caveatها دلیل حذف نیست؛ موارد آزمون و بهبودند.

## ۴) Ichimoku — دامنهٔ واقعی تحقیق

سورس `Indi 84.txt` چند مسیر دارد:
- محاسبهٔ کلاسیک Tenkan/Kijun/Senkou و حالت تطبیقی بر اساس volatility؛
- وضعیت قیمت نسبت به Kumo، TK cross/alignment و Chikou؛
- flat Kijun به‌عنوان support/resistance context؛
- Kumo breakout و retest؛
- momentum pulse و confluence؛
- state چندتایم‌فریمی.

دو نکتهٔ فنی برای ممیزی:
1. سیگنال‌های اصلی با `barstate.isconfirmed` کنترل شده‌اند؛ MTF با state تایم‌فریم قبلی و `lookahead_on` الگوی رایج confirmed HTF را به‌کار می‌گیرد، ولی باید روی مرز timeframe و دادهٔ واقعی آزمون شود.
2. تابع MTF در همین سورس از خطوط کلاسیک استفاده می‌کند حتی وقتی main mode روی Adaptive باشد؛ ممکن است خروجی MTF و چارت از دو definition متفاوت استفاده کنند.

امتیاز ۰–۱۰۰ و وزن‌های آن هنوز فقط heuristic سازنده‌اند. این مسئله مانع نگه‌داری نیست؛ ابتدا باید خطوط/شرط‌های مستقل بررسی و سپس calibration انجام شود.

دو باینری دیگر نیز با نام Ichimoku در همان پوشه نگه داشته شده‌اند تا خروجی‌شان با نسخهٔ Pine مقایسه شود. برای باینری‌ها screenshot و settings لازم است؛ فرمول آن‌ها از سورس Pine قابل استنتاج نیست.

## ۵) استاتیک تریاژ EX4 / EX5

برای هر ۱۱ باینری در این مرحله از GitHub contents با encoding=base64 استفاده و header و رشته‌های printable بررسی شد. نتیجهٔ این روش محدود است:
- headerهای خانوادهٔ EX4/EX5 شناسایی شدند.
- در `Fibo.ex4` رشته‌های قابل‌خواندن `Don Perry`، `lookback`، `lastbar` و `Fibo` وجود دارد.
- در بیشتر باینری‌های دیگر رشته‌های معنی‌دار برای بازسازی الگوریتم دیده نشد.
- این کار decompilation، اجرای MetaTrader، یا تأیید فرمول محسوب نمی‌شود.

پس تصمیم صحیح برای آن‌ها `BINARY_REVIEW_PENDING` است، نه `REJECT`. برای پیشبرد بررسی نیاز به screenshot واقعی از خروجی و Inputs/Settings در MetaTrader سازگار داریم؛ دریافت سورس اصلی/لینک سازنده بهتر است.

## ۶) مواردی که با اطمینان از Inbox اندیکاتورها خارج می‌شوند

| فایل | تشخیص از روی سورس | مقصد/دلیل |
|---|---|---|
| `Breakout Retest Pro EA Source Code @IndicatorsforTV.mq4` | Expert Advisor؛ حساب/سفارش/OrderClose | اندیکاتور نیست؛ خارج از این Inbox |
| `Breakout Retest Pro EA Source Code @IndicatorsforTV.ex4` | باینری همراه همان EA سورس‌دار | خارج از این Inbox |
| `Gold Snap  v1.0.mq5` | Expert Advisor با `CTrade` و سفارش واقعی | استراتژی اجرایی طلا، نه اندیکاتور |
| `Range Breakout With Filter.mq5` | Expert Advisor با `CTrade` و مدیریت ریسک | ربات معاملاتی |
| `Range Breakout With Filter.ex5` | باینری همراه همان EA سورس‌دار | خارج از این Inbox |
| `Replay Tool.mq5` | ابزار Market Replay و drawing | ابزار تحقیق/بازپخش، نه اندیکاتور |
| `Indi 538.txt` | Pine Strategy با `strategy.entry/exit/cancel` | استراتژی بک‌تست طلا، نه indicator |

## ۷) تصاویر مورد نیاز از مالک

برای نهایی‌کردن اولویت‌ها و مقایسهٔ بصری، این تصاویر بیشترین ارزش را دارند:
1. **Double Tap:** چارت با دو سقف/کف، neckline، شکست و TP/SL + پنجرهٔ تنظیمات.
2. **Ichimokuها:** هر نسخه جداگانه روی یک نماد و تایم‌فریم مشخص + Inputs/Settings؛ به‌خصوص هر دو EX4/EX5 و Adaptive Ichimoku.
3. **باینری‌های دیگر:** هرکدام که در گذشته روی نمودار سیگنال جالبی نشان داده‌اند، همراه settings و source link.

تصویر باید تاریخ/ساعت، نماد و timeframe را نشان دهد. برای بازار ایران، بعداً نمونهٔ همان نماد در چارت تعدیل‌شده و خام مفید است. تصویر بدون تنظیمات و نماد برای بازتولید دقیق کافی نیست.

## ۸) قیدهای معماری و پذیرش

- هیچ‌یک از موارد این گزارش وارد `implemented/` نمی‌شوند.
- هیچ Runtime code تغییر نمی‌کند.
- FTS canonical مستقل می‌ماند و هیچ آستانه یا رأی FTS از این منابع استخراج نمی‌شود.
- هر نامزد پذیرفته‌شده باید deterministic، قابل‌آزمون، دارای تعریف دقیق timestamp/confirmation، ضد-look-ahead، و سازگار با raw/adjusted basis باشد.
- مواردی با مجوز نامعلوم فقط از نظر رفتار/ایده بررسی می‌شوند؛ اقتباس یا بازنشر مستقیم کد تا روشن‌شدن مجوز انجام نمی‌شود.
- فایل‌های کامپایل‌شده ناشناس روی حساب واقعی اجرا نمی‌شوند.

## ۹) وضعیت نهایی

- **Double Tap:** RETAIN / HIGH PRIORITY / NOT YET VERIFIED
- **Ichimoku source + two binaries:** RETAIN / HIGH PRIORITY / NOT YET VERIFIED
- **Liquidity/SMC:** RETAIN / HIGH PRIORITY / MODULE-LEVEL REVIEW REQUIRED
- **Failed breakout / Third Wave / StormCore:** RETAIN / EXPLORATORY
- **EX4/EX5 not paired with known EA source:** RETAIN / BINARY_REVIEW_PENDING
- **Known EAs, Strategy and Replay Tool:** EXCLUDE FROM INDICATOR INBOX

این مرحله فقط طبقه‌بندی، مستندسازی و نظم‌دهی مخزن است. هیچ اندیکاتوری VERIFIED یا Production-ready اعلام نشده است.
