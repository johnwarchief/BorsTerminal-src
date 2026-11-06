# E0 — audit اندیکاتورهای الگو/ساختار تلگرام (@IndicatorsforTV)

- تاریخ: 2026-11-06
- دامنه: همهٔ ردیف‌های کاتالوگ ۶۴تایی که به الگو، ساختار، کانال، پولبک/شکست یا واگرایی مربوط‌اند + پست‌های تازهٔ کانال در 2026-11-06.
- قاعدهٔ پذیرش: فقط سورس متنی (`Indi *.txt`/`.mq4`) + عدم repaint + نقش مشخص در سیگنال؛ باینری‌های `.ex4/.ex5` پورت نمی‌شوند.
- وضعیت موتور فعلی: موتور الگوی فاز A–D (۲۶ نوع، ClassicPatterns) + موتور رویداد فاز C (کانال/واگرایی/پولبک/شکست) از ۹ اورلی قدیمی جداست؛ این audit آن‌ها را نیز حساب می‌کند.

## ۱. جدول ردیف‌های مرتبط

| ردیف | عنوان | نوع پیوست | دسته | پیاده‌سازی فعلی | قابلیت پورت | تصمیم |
|---|---|---|---|---|---|---|
| p12 | Double Tap 3D | `.txt` Pine v6 (629 خط) | W/M، گردن، تارگت | `DoubleTap3D` + `PatternStoryOverlay` | سورس متنی | **fix** (وفادارسازی) |
| p14/p42 | Auto Trendline Intelligence (BOS+CHoCH+FVG) | `.txt` | ساختار | `AutoTrendlineCHoCH` | سورس | fix (FVG در رسم نیست) |
| p22/p28 | Super Trend Pullback | `.txt` | پولبک | `SuperTrendPullback` | سورس | keep |
| p06 | Breakout Retest Pro | `.mq4`+`.ex4` | شکست/ریتست | `BreakoutRetestPro` | سورس | keep |
| p05 | RSI MA Smooth (MTF+div) | `.ex4` | واگرایی | `RsiMaSmooth` (فقط عادی) | باینری | fix داخلی: افزودن واگرایی مخفی از موتور RSI خودمان؛ پورت p05 نه |
| p11 | MSnR Double Breakout Failed Level | `.txt` بدون مجوز | شکست ناموفق | — | سورس، مجوز نامشخص | reference |
| p16 | Human Level Structure Engine | `.mq5` | ساختار/CHoCH | — | سورس | port candidate (بعدی) |
| p17 | SMC Order Block Scorer | `.txt` | OB/نمره | `smcZones` بدون نمره | سورس | port candidate (بعد از E2) |
| p19 | Automatic Wedge & Channel | `.txt` (407/228) | کانال/گُوه | `MultiModeChannel` (رگرسیون/دانچیان) | سورس | **port (E2)** |
| p21 | S/R Retest Breakout | `.txt` (248) | S/R + ریتست | `ftsSupportResistance` + `BreakoutRetestPro` جزئی | سورس | **port (E2)** |
| p26 | Raff Channel MT4 | `.ex4` | کانال | — | باینری | reject |
| p27/p31 | Anchored VWAP Pullback | `.txt` | پولبک/تارگت | — | سورس | port candidate (بعدی) |
| p29 | Pullback Sniper | `.txt` | پولبک | `SuperTrendPullback` جزئی | سورس | reference |
| p30/p35 | Trendlines w/ Breakouts/Hold Rate | `.txt` بدون مجوز | خط روند/آمار | `AutoTrendlineCHoCH` بدون hold-rate | سورس، مجوز نامشخص | reference |
| p33 | Range Profile Structure | `.txt` بدون مجوز | رنج/تارگت | `ClassicPatterns` RECTANGLE | سورس، مجوز نامشخص | reference |
| p36/p55 | Historical Pattern Projection | بدون فایل | پروجکشن | — | فقط تصویر | reference/reject |
| p39 | EQH/EQL Levels Likely to Break | `.txt` | نقدینگی | — | سورس | port candidate (بعدی) |
| p40 | Breakout & Retest Scanner | `.ex4` | شکست | — | باینری | reject |
| p43 | Ranked S/R Zones | `.txt` | S/R | `ftsSupportResistance` بدون رتبه | سورس | port candidate (بعدی) |
| p45 | Divergence for Multiple Indicators v4 | `.txt` Pine v4 | واگرایی | `RsiMaSmooth` + `ChartEvents` (فقط RSI) | سورس | reference (v4) |
| p46 | Divergence Tool (trial) | `.ex4` | واگرایی | — | باینری | reject |
| p47/p57 | RSI Divergence Out-of-Sample Optimizer | `.txt` | واگرایی پژوهشی | — | سورس | reference (پژوهشی) |
| p48 | Auto Fibo Zig Zag | `.txt` | پیوت/فیبو | `pivots.ts` | سورس | reference |
| p51/p60 | Pivot Channel TrendLines | `.txt` | کانال | `ftsTrendChannel` | سورس | reference |
| p52/p61 | Strong Pressure Zones / SMC Volume Profile | `.txt` | زون | `smcZones` | سورس | reference |
| p54 | ML Smart Money Concepts | `.txt` CC BY-NC-SA | SMC | `smcZones` | مجوز مانع | reject |
| p62 | Wave Structure PRO v2 | `.txt` | الیوت | — | سورس | reference |
| p63 | Professional Market Structure | `.txt` | ساختار | `AutoTrendlineCHoCH` جزئی | سورس | port candidate (بعدی) |
| p01 | FB_OBwin | `.ex4` | OB | — | باینری | reject |

## ۲. پست‌های تازهٔ کانال (2026-11-06)

| پست | پیوست | دسته | تصمیم |
|---|---|---|---|
| MW Pattern MT4 | ZIP + ویدئو | W/M | مرجع فقط؛ باینری/آرشیو، پورت نمی‌شود |
| Pattern Recognition | `.ex5` (32KB) + چارت | الگو | reject (باینری) |
| Pattern_Recognition_Master_v3 | `.MT4` + `.ex4` (48.9KB) | الگو | reject (باینری) |
| Pattern Recognition Hammer & Shooting Star v1.0 MT5 | `.ex5` | الگو | reject (باینری) |
| Concept PNG Patterns for TradingView | تصویر | مرجع ۹ الگو | reference only |

## ۳. یافته‌های کلیدی

- **W/M از قبل وجود دارد و سورس دارد**: p12 = `Indi 516.txt`؛ پیاده‌سازی فعلی نازک‌تر است. کار E2 = وفادارسازی (grade/score، اسلب ۳D، BREAK/LONG/SHORT، TP1/TP2/SL، چرخه) نه ساخت از صفر.
- **p19/p21 سورس متنی دارند** و گپ واقعی «کانال/گُوه» و «S/R + ریتست/شکست» را پر می‌کنند؛ در E2 داخل موتور موجود ادغام می‌شوند.
- **باینری‌های تازه** (MW Pattern، Pattern Recognition و…) قابل پورت نیستند؛ فقط مرجع بصری/منطقی‌اند.
- **پوشش فعلی**: ۲۶ نوع الگوی فاز A–D + کانال رگرسیون + واگرایی RSI ۴نوعه + پولبک/شکست؛ p19/p21 این پوشش را کامل‌تر می‌کنند.
- **ریسک مجوز**: p19/p21 MPL-2.0 + برند کانال؛ p12 بدون خط مجوز. attribution در `evidence.source` و مستندات، بدون کپی واترمارک. p54 به‌خاطر CC BY-NC-SA رد شد.

## ۴. نقشهٔ پورت (خلاصه)

- p19: `patterns/detectChannelPivot.ts` + `events/channel.ts` (نوع `PIVOT_CHANNEL`)؛ امتیاز جزء‌به‌جزء Pine، طبقه‌بندی موازی/همگرا/واگرا، چرخهٔ شکست/ریکلیم/انقضا، late-stage.
- p21: `events/zone.ts` (نوع `SR_RETEST`)؛ زون دو سوئینگی با `stdev(40)`، ضخامت o/h/l/c، ماشین حالت ۰→±1→±2→±3، پروکسی حجم با برچسب نبود LTF.
- ACهای اولین برش در §۲.۳ سند طراحی (`docs/superpowers/specs/2026-11-06-workspace2-telegram-pattern-spotlight-kronos-design.md`).
