# گزارش بازچینی و پالایش Technical Indicator Inbox

- **تاریخ:** 2026-11-10
- **شاخه:** `mission/technical-indicator-inbox-curation-2026-11-10`
- **مبنای بررسی:** `main` در commit `9a919e82f5b836cc7ec4be5ba04a39ec2f74b4e2`
- **نوع بررسی:** static source review و inventory؛ هیچ فایل باینری اجرا یا decompile نشد.
- **دامنه:** `docs/technical-indicators/inbox/`، فایل‌های README و template، سورس‌های قابل‌خواندن و گزارش بررسی قبلی.

## خلاصهٔ تصمیم

پیش از بازچینی، ۲۶ ورودی در Inbox وجود داشت. ساختار جدید، دو سورس را به‌عنوان نامزد تحقیق نگه می‌دارد و به پوشهٔ مستقل منتقل می‌کند؛ دو سند راهنما نیز حفظ/به‌روزرسانی می‌شوند. ۲۲ ورودی دیگر از Inbox حذف می‌شوند. حذف از Inbox به معنی ادعای بی‌ارزش‌بودن همهٔ ایده‌ها نیست؛ به معنی نداشتن جایگاه به‌عنوان ورودی فعال این مرحله است.

| پرونده | تصمیم | جایگاه |
|---|---|---|
| `Indi 533.txt` | نگه‌داری و انتقال بدون تغییر محتوای سورس | Research candidate — اولویت بالا |
| `Indi 84.txt` | نگه‌داری و انتقال بدون تغییر محتوای سورس | Research candidate — اختیاری |
| `README.md` | حفظ و به‌روزرسانی | راهنمای Inbox |
| `INDICATOR_INTAKE_TEMPLATE.md` | حفظ و گسترش | قالب دریافت ورودی |
| سایر ۲۲ ورودی | حذف از Inbox | دلایل زیر |

هیچ موردی با این بازچینی به `implemented/` ارتقا پیدا نمی‌کند. هیچ اندیکاتوری در Runtime پیاده‌سازی نمی‌شود.

## ۱) نامزدهای نگه‌داری‌شده

### A. `liquidity-structure/indicator.pine` — از `Indi 533.txt`

**اولویت تحقیق: بالا.** سورس Pine v6 شامل ماژول‌های Swing Liquidity (BSL/SSL)، sweep، PDH/PDL و PWH/PWL، FVG/iFVG، supply/demand zones و premium/discount range است.

دلایل نگه‌داری: چند مفهوم مجزا و تست‌پذیر دارد که می‌توانند در کتابخانهٔ مستقل Pattern/Indicator بررسی شوند. لازم نیست بستهٔ بزرگ اسکریپت یکجا پذیرفته شود.

ریسک‌ها و محدودیت‌های کشف‌شده:
- pivot right-bars تأخیر تأیید دارد؛ زمان pivot و زمان تأیید باید جدا باشند.
- بسیاری از منطق‌های روی کندل جاری گارد سراسری close-confirm ندارند؛ repaint/intrabar باید دقیقاً تست شود.
- «CVD» عمدتاً از جهت کندل برای تقسیم حجم مثبت/منفی proxy می‌سازد؛ این order flow یا bid/ask delta واقعی نیست.
- تعریف OB heuristic است و نهادی بودن سفارش را اثبات نمی‌کند.
- توابع روز/هفتهٔ قبلی باید با timezone و تقویم بورس ایران تطبیق یابند.
- سربرگ MPL 2.0 دارد؛ اصالت مجوز و تعهدات لازم پیش از اقتباس/بازنشر باید بررسی شود.

اولویت بررسی ماژول‌ها: BSL/SSL و sweep؛ سپس FVG/iFVG؛ سپس OB heuristic؛ سپس premium/discount به‌عنوان context. CVD proxy تا اثبات اعتبار جداگانه نباید به‌عنوان CVD واقعی معرفی شود.

### B. `adaptive-ichimoku/indicator.pine` — از `Indi 84.txt`

**اولویت تحقیق: اختیاری.** سورس Pine v6 شامل Ichimoku کلاسیک/تطبیقی مبتنی بر volatility، Kumo، Tenkan/Kijun، Chikou، breakout/retest، MTF و momentum/confluence است.

دلایل نگه‌داری: یک گزینهٔ context/trend مستقل است و نسخهٔ سورس‌دار آن از فایل‌های کامپایل‌شدهٔ Ichimoku قابل ارزیابی‌تر است.

ریسک‌ها و محدودیت‌های کشف‌شده:
- سیگنال‌های اصلی با barstate.isconfirmed گیت شده‌اند؛ MTF از state تایم‌فریم قبلی استفاده می‌کند، اما باید روی مرزهای تایم‌فریم تست شود.
- محاسبهٔ MTF کلاسیک است، حتی وقتی تنظیم اصلی در حالت Adaptive قرار دارد؛ این ناهمخوانی باید حل/مستند شود.
- وزن‌های امتیاز ۰–۱۰۰ سلیقهٔ نویسنده‌اند، نه پارامترهای اعتبارسنجی‌شده.
- fallbackهای `nz(..., close)` ممکن است کمبود داده را مخفی کنند.
- مناسب‌بودن volume filter و دوره‌های تطبیقی برای بازار ایران نامعلوم است.
- سربرگ MPL 2.0 دارد؛ اصالت مجوز و تعهدات استفاده باید بررسی شود.

مسیر تحقیق: baseline کلاسیک، سپس آزمون جداگانهٔ adaptive و MTF؛ score وزنی تا ارزیابی out-of-sample وارد محصول نشود.

## ۲) ورودی‌های حذف‌شده و دلیل

### سورس‌های Pine / TradingView

| ورودی | تشخیص و دلیل خروج از Inbox |
|---|---|
| `Indi 516.txt` | Double Tap 3D؛ الگوی سقف/کف دوقلو با pivot، ATR و RSI. منطق کندل جاری گارد سراسری close-confirm ندارد؛ با ساختارهای موجود هم‌پوشانی دارد و تعریف/کیفیت سیگنال با نمونهٔ مرجع تثبیت نشده است. |
| `Indi 518.txt` | MSnR Double Breakout Failed Level؛ close-confirm دارد، اما تعریف شکست ناموفق/سطح با ساختار مرجع FTS یکی نیست و ارزش افزودهٔ روشن نسبت به level/structure موجود اثبات نشده است. در این مرحله نامزد فعال نمی‌ماند. |
| `Indi 534.txt` | StormCore SMC/Div/SuperTrend composite؛ ترکیبی از ماژول‌های هم‌پوشان با Indi533، CHoCH/RSI و ابزارهای تکنیکال موجود. منطق custom SuperTrend و score مستقل باید جداگانه از صفر سنجیده شوند؛ نگه‌داشتن کل بسته در Inbox باعث تکرار و ابهام می‌شود. |
| `Indi 538.txt` | Gold Breakout 15M یک Pine **Strategy** است؛ سفارش‌های stop، entry/exit، position sizing و equity guard دارد. اندیکاتور نیست و استراتژی خاص XAUUSD است. |
| `Indi 82.txt` | 3rd Wave BB TrendLines؛ به کتابخانهٔ خارجی ZigZag وابسته است و هم‌زمان Elliott 3rd wave، Bollinger، RSI و trendline دارد. تعریف و وابستگی بیرونی/ریسک hindsight برای این مرحله شفاف نیست؛ ارزش نگه‌داری کل اسکریپت پایین است. |

### Expert Advisor و ابزار غیراندیکاتوری

| ورودی | تشخیص و دلیل خروج |
|---|---|
| `Breakout Retest Pro EA Source Code @IndicatorsforTV.mq4` | Expert Advisor؛ منطق معاملاتی و فراخوان‌های باز/بستن سفارش دارد. |
| `Breakout Retest Pro EA Source Code @IndicatorsforTV.ex4` | فایل کامپایل‌شدهٔ همراه همان EA؛ نه اندیکاتور و نه قابل ممیزی مستقل. |
| `Gold Snap  v1.0.mq5` | Expert Advisor با `CTrade`، محاسبهٔ حجم/ریسک و ثبت سفارش؛ یک استراتژی اجرایی طلاست. |
| `Range Breakout With Filter.mq5` | Expert Advisor با `OnTick`، `CTrade`، مدیریت ریسک و prop-firm guard؛ اندیکاتور نیست. |
| `Range Breakout With Filter.ex5` | باینری همراه همان Expert Advisor؛ برای بررسی منطق به‌تنهایی کافی نیست. |
| `Replay Tool.mq5` | ابزار Market Replay و ترسیم Long/Short روی نمودار است؛ محاسبه‌گر اندیکاتوری نیست و در مسیر جداگانهٔ ابزار تحقیق/تست قرار می‌گیرد. |

### باینری‌های کامپایل‌شدهٔ غیرقابل‌ممیزی

این فایل‌ها سورس قابل‌خواندن در Inbox ندارند. نام فایل یا توضیح احتمالی سازنده برای تأیید الگوریتم، repainting، پارامترها و مجوز کافی نیست؛ بنابراین از ورودی فعال حذف شدند، نه اینکه فرمولشان تأیید یا رد شده باشد.

| فایل | دلیل خروج |
|---|---|
| `AI RSI BB SCALPER.ex5` | باینری؛ منطق و ماهیت «AI» قابل تأیید نیست؛ نام scalper نیز نشان‌دهندهٔ تمرکز معاملاتی کوتاه‌مدت است. |
| `FB_OBwin.ex4` | باینری بدون سورس و مستندات قابل‌ممیزی. |
| `Fibo.ex4` | باینری بدون سورس؛ ابزار فیبو در FTS نیز context canonical تعریف شده و نیاز به duplicate سیاه‌جعبه‌ای نیست. |
| `FiboRSI8_SingleShot_v122 @IndicatorsforTV.ex5` | باینری بدون سورس؛ فرمول/سیگنال و انطباق RSI/Fibonacci قابل تأیید نیست. |
| `Machine Learning Regression Trend.ex5` | باینری بدون سورس؛ دادهٔ آموزش، target، leakage، روش اعتبارسنجی و مدل مشخص نیست. ادعای ML به‌تنهایی ارزش فنی اثبات نمی‌کند. |
| `SuperTrend(wHA) @IndicatorsforTV.ex4` | باینری بدون سورس؛ فرمول و حتی تعریف دقیق variant از نام قابل استنتاج نیست. |
| `fox_UP_DOWN_ARROW.ex5` | باینری سیگنال‌نما بدون سورس؛ منطق، repaint و مجوز نامعلوم. |
| `ichimoku-cloud-indicator.ex5` | باینری بدون سورس؛ برای بررسی Ichimoku، نامزد سورس‌دار Indi84 قابل ممیزی‌تر است. |
| `ichimoku-signals-cloud.ex4` | باینری بدون سورس؛ هم‌پوشانی با نامزد Ichimoku سورس‌دار. |
| `indi sbnr2+save2_alert(1).ex4` | باینری بدون سورس؛ منطق و خروجی قابل تأیید نیست. |
| `rsi ma - smooth (mtf + alerts + divergence) @IndicatorsforTV.ex4` | باینری بدون سورس؛ MTF/RSI divergence را نمی‌توان بدون الگوریتم و تست مرجع تأیید کرد و مفاهیم RSI/واگرایی در مسیرهای موجود نیز حضور دارند. |

## ۳) ساختار نهایی Inbox

```text
docs/technical-indicators/inbox/
├── README.md
├── INDICATOR_INTAKE_TEMPLATE.md
├── liquidity-structure/
│   ├── indicator.pine
│   └── notes.md
└── adaptive-ichimoku/
    ├── indicator.pine
    └── notes.md
```

سورس‌های دو نامزد به‌صورت متنی و بدون تغییر الگوریتم/محتوا منتقل می‌شوند؛ فقط مسیر و نام فایل برای نظم پوشه تغییر می‌کند. ۲۲ ورودی دیگر از Inbox حذف می‌شوند. این گزارش، نام تمام موارد و علت تصمیم را حفظ می‌کند.

## ۴) تصویر لازم است؟

برای طبقه‌بندی اولیه و static review سورس، تصویر لازم نبود؛ بنابراین این مرحله بدون تصویر قابل انجام بود.

برای پذیرش بصری هر نامزد، این دو تصویر مفیدند:
1. `reference.png`: چارت با خروجی اندیکاتور و سیگنال/ناحیهٔ مشخص؛
2. `settings.png`: پنجرهٔ تنظیمات همان اجرا.

همراه تصاویر باید نماد، بازار، تایم‌فریم، زمان سیگنال و مبنای قیمت خام/تعدیل‌شده معلوم باشد. اگر تصویر در دسترس نیست، فقط مرحلهٔ visual-parity در وضعیت NOT_MEASURED می‌ماند؛ بررسی سورس متوقف نمی‌شود.

## ۵) قیود معماری و پذیرش

- هیچ فایل یا ایده‌ای در این گزارش به `implemented/` منتقل نمی‌شود.
- هیچ کد Runtime یا منطق Go/React/SQLite تغییر نمی‌کند.
- قواعد canonical FTS، veto هفتگی، Jet، CHoCH، Fibonacci، RSI/Hourglass و exit rules دست‌نخورده‌اند.
- هیچ امتیاز ترکیبی، وزن، trigger یا threshold جدیدی به FTS اضافه نمی‌شود.
- هر الگوریتم پذیرفته‌شده باید مستقل، deterministic، دارای semantics روشن برای unknown/insufficient/stale، ضد-repaint و قابل‌آزمون روی دادهٔ ایران باشد.
- وجود header مجوز در Pine به‌تنهایی جایگزین بررسی اصالت منبع و تعهدات مجوز نیست.
- حذف این ورودی‌ها از Inbox، حکم حقوقی یا ادعای بی‌ارزش‌بودن همهٔ ایده‌هایشان نیست؛ فقط تصمیم پالایش مخزن برای این مرحله است.

## ۶) نتیجهٔ قابل‌تأیید

این commit فقط تغییر مستندات و ساختار Inbox است. هیچ فایل کامپایل‌شده اجرا نشده، هیچ backtest یا benchmark بازار ایران انجام نشده و هیچ اندیکاتوری به‌عنوان VERIFIED اعلام نمی‌شود. وضعیت هر دو نامزد: **RESEARCH / UNVERIFIED**.
