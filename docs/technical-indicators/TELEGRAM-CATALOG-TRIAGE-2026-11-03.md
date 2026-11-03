# تریاژ کاتالوگ ۶۴ اندیکاتور تلگرام (@IndicatorsforTV)

- **تاریخ:** ۲۰۲۶-۱۱-۰۳
- **منبع داده:** `frontend-v2/src/features/technical/data/telegram-indicators.json` (۶۴ ردیف exportشده؛ عنوان‌ها و پیوست‌ها)
- **وضعیت پیاده‌سازی فعلی:** ۹ اورلی در `ADVANCED_INDICATORS_REGISTRY` و `USER_INDICATORS_REGISTRY`
- **هدف:** فقط چیزی بماند که به **سیگنال خرید/فروش** یا **ریسک/تارگت** کمک کند؛ نه هر اندیکاتوری که در کانال منتشر شده.

## ۱. جمع‌بندی شمارشی

| دسته | تعداد (تقریبی) | حکم |
|---|---:|---|
| پیاده‌شده و هم‌راستا با جزوه | ۹ اورلی (از ۱۲ ردیف) | نگه دار |
| TradingView قابل‌بررسی برای مرحلهٔ بعد | ۱۲–۱۵ ردیف | اولویت‌بندی شود |
| فقط MT4/MT5 (ex4/ex5) یا EA | ۲۱ ردیف | پورت نشود |
| تکراری / کپشن / بدون فایل | ۱۰+ ردیف | بی‌اعتنا |
| بیربط به سیگنال (تم چارت، طلا، اسکالپر) | ۵–۶ ردیف | حذف از دامنه |

## ۲. نگه دار — همان ۹ اورلی موجود

| ردیف | عنوان | نقش در سیگنال | پیاده‌سازی |
|---:|---|---|---|
| ۱۲ | Double Tap 3D | الگوی W/M، خط گردن، تارگت | `DoubleTap3D` |
| ۱۴، ۴۲ | Auto Trendline Intelligence (BOS+CHoCH+FVG) | ساختار و شکست | `AutoTrendlineCHoCH` |
| ۲۲، ۲۸ | Super Trend Pullback | ورود در پولبک | `SuperTrendPullback` |
| ۰۶، ۴۰ | Breakout Retest Pro | شکست و بازآزمایی | `BreakoutRetestPro` |
| ۰۵ | RSI MA Smooth (MTF + Divergence) | مومنتوم/واگرایی | `RsiMaSmooth` |
| ۰۲ | Fibo RSI8 SingleShot | مومنتوم/فیبو | `FiboRSI8` |
| ۲۴، ۳۲ | Bands RSI / BB RSI MA | مومنتوم | `MultiVariantRSI` (حالت BB) |
| ۰۳ | SuperTrend (wHA) | روند | `SuperTrendHeikinAshi` |
| ۱۹، ۲۶، ۵۱، ۵۹ | کانال/رگرسیون/دانچیان | زمینهٔ روند | `MultiModeChannel` |

این ۹ مورد، ستون فقرات «روند → ساختار → ورود → حد ضرر» را پوشش می‌دهند و با زبان جزوه (پولبک، CHoCH، خط گردن، فیبو، RSI) هم‌خوان‌اند.

## ۳. مرحلهٔ بعد — سه اولویت واقعی

| اولویت | ردیف | عنوان | چرا | چه چیزی اضافه می‌کند |
|---:|---:|---|---|---|
| ۱ | ۲۱ | Support and Resistance Retest Breakout | سقف/کف عمومی، نه فقط دوقلو؛ همان نیاز «سقف و کف» | ناحیهٔ S/R + بازآزمایی + سیگنال شکست |
| ۲ | ۱۹ | Automatic Wedge & Channel Detector | مثلث/گُوه/کانال همگرا در کد فعلی نیست | فشرده‌شدن، شکست ساختاری، عمر الگو |
| ۳ | ۱۷، ۲۳ | SMC Order Block Scorer / Volume-Trend OB | اردربلاک داریم، اما درجه‌بندی/حجم ندارد | نمرهٔ A+/A/B/C و کیفیت زون |

**گزینه‌های ذخیره برای بعد:** ردیف ۴۳ (Ranked S/R Zones)، ۶۱ (Institutional SMC Volume Profile)، ۳۰/۳۵ (Trendlines with Hold Rate)، ۳۹ (Levels Likely to Break)، ۲۷/۳۱ (Anchored VWAP). این‌ها وقتی ارزش دارند که داده/منبعشان قابل‌اعتبارسنجی باشد.

## ۴. پورت نکن — چون در ترمینال وب قابل اجرا یا قابل اعتماد نیستند

- **فقط باینری MT4/MT5:** ۰۱ (FB_OBwin)، ۰۳ (SuperTrend MT4)، ۰۴ (ML Regression MT5)، ۱۵ (CHoCH Detector MT4)، ۱۶ (Human Level Structure MT5)، ۱۸ (ChartThemeManager)، ۲۴/۲۵/۳۲/۳۴/۴۶ (خانواده RSI/SMA MT4/MT5)، ۳۷ (YUVI FX)، ۴۱ (Barkat)، ۴۴ (Ultimate Breakout)، ۴۹ (AI RSI BB Scalper)، ۵۳ (Obsidian Pivot)، ۵۹ (Regression Channel Scanner).
- **EA/اسکالپر طلا یا بازار خاص:** ۷، ۱۰ (Gold Snap)، ۱۳/۳۸ (Range Breakout EA)، ۴۰ (Breakout Retest Scanner EA).
- **بدون فایل/کپشن تکراری:** ۰۷–۰۹ (Key Features)، ۳۶/۵۵ (Historical Pattern Projection بدون پیوست)، ۳۱ و ۳۵ و ۴۲ و ۵۷ و ۶۰ (تکرار ردیف‌های قبلی).
- **خارج از هدف سیگنال:** ۱۸ (تم چارت)، ۵۶ (Magic Trading Tool)، ۵۸ (GG SHOT Ai V2) — بدون سورس/شفافیت کافی، ریسک repaint و ادعای بازاریابی.

> قاعده: یک اندیکاتور فقط وقتی وارد ترمینال می‌شود که **سورس متنی** (`.txt`/`.mq4/.mq5`) داشته باشد، **بدون repaint** باشد، و خروجی‌اش به یکی از این پنج نقش بچسبد: روند، ساختار، تریگر ورود، ریسک/تارگت، تأیید حجم/مومنتوم.

## ۵. نقشهٔ نیاز FTS ← اندیکاتور

| نیاز | الان چه داریم | کمبود | کاندید بعدی |
|---|---|---|---|
| روند هفتگی/روزانه | `trend.matrix`, SuperTrend | — | — |
| ساختار (CHoCH/BOS) | AutoTrendlineCHoCH | چنددرجه‌ای | ۱۶/۶۳ (فقط اگر سورس باشد) |
| ورود در پولبک | SuperTrendPullback, BreakoutRetest | — | — |
| شکست/جت | FTS jet, الگوی سایت | — | — |
| الگوی برگشتی | Double Tap W/M | سقف سوم/سر و شانهٔ مستقل | ۱۲ (توسعهٔ همان) |
| سقف/کف عمومی | Key Levels فعلی | ناحیهٔ تأییدشده + retest | **۲۱ / ۴۳** |
| فشرده‌سازی/کانال | MultiModeChannel | مثلث/گُوه | **۱۹** |
| حد ضرر/تارگت | ATR، فیبو، measured move | — | — |
| تأیید حجم/پول | Tape filters, FTS | حجم پروفایل/OB score | **۱۷ / ۲۳ / ۶۱** |
| واگرایی | RSI divergence | — | ۴۵/۴۷ (فقط پژوهشی) |

## ۶. حکم نهایی

- **نگه دار:** ۹ اورلی فعلی.
- **بعدی:** ۲۱ (S/R Retest)، ۱۹ (Wedge/Channel)، ۱۷/۲۳ (OB Scorer) — هر سه به «سقف و کف» و «کیفیت ناحیه» که دغدغهٔ اصلی شماست وصل‌اند.
- **پورت نکن:** ۲۱ باینری MT4/MT5، EAها، تم چارت، و ردیف‌های تکراری/بدون فایل.
- **معیار ورود:** سورس متنی + عدم repaint + نقش مشخص در سیگنال + تست قابل‌تکرار. بدون این چهار، اندیکاتور فقط شلوغی چارت است.
