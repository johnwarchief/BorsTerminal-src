# STATE — اسنپ‌شات سیستم (به‌روز: 2026-09-14 ۱۶:۰۰ محلی)

## Repo / سرور
- **master HEAD:** `26b125f` (شامل همهٔ کارها + بستهٔ agent-system؛ سرِ آن `4f180ac` فیکس دراور بنیادی است)
- **خط پایهٔ تست:** 730/730 (با fixِ uncommittedِ هد) · eslint صفر · build سالم
- **سرور:** `python start_dashboard.py --port 8012` از ریشه (پایدار در این ماشین، PID متغیر)
- **دیتابیس:** market.db (≈۱۰۴MB، sync خودکار صبحگاهی) + codal.db در ریشه

## برنچ‌ها / ورک‌تری‌ها / سشن‌ها (ماشین مبدأ — روی ماشین جدید session id معنا ندارد)
| برنچ | ورک‌تری | HEAD | وضعیت | Session ID |
|---|---|---|---|---|
| agent/tape | silky-arch | da5268b | clean، مرج‌شده | e5f55980-77fb-4c98-9557-05099566f2ce |
| agent/fundamental | serene-mountain | 4f180ac | مرج‌شده | 7750c3e9-694a-477c-9eb9-7c127d81e56b |
| agent/technical | neat-plateau | 6d2c036 (+1 dirty) | **در حال کار** | 3f5fa69b-626f-4820-879c-3b31aaa419be |
| agent/master-portfolio | mellow-brook | 4177e24 | clean، مرج‌شده | ac6ab3ac-ae87-4507-a70d-d321e6034ccf |

## مأموریت باز (اگر迁移 وسط کار کردید، همین را re-dispatch کنید)
**T-01 · Technical · RightDock:**
```
۱) Read TechnicalPage.tsx
۲) components/RightDock.tsx جدید: سه تب (شاخص‌ها: macro.value_hemat + متریک ۲۰ همت + صادقانه «سری شاخص کل نیست»؛
   FTS: top-scored /api/screener با p_last/percent؛ تحرکات: f_susp/f_clock) + Radar (passes از /api/fundamental/{sym} + fib_zones/ستاپ /api/chart/{sym})
۳) symbol خالی ⇒ fallback اولین screener؛ چیدمان چارت + RightDock
۴) curl /api/chart/کانسار: بک‌اند سالم ⇒ فیکس feed؛ بک‌اند flat ⇒ گزارش
۵) vitest سبز (ریدایرکت) → eslint → build → commit "feat(technical): right dock watchlist + radar with default symbol fallback"
```

## گره‌های حل‌شدهٔ امروز (برای حفظ در refactors بعدی)
- Market menu → `createPortal` (بدون پکیج جدید) — Radix اضافه نکنید
- FtsSettingsDrawer → پنل `fixed inset-y-0 right-0` + backdrop (anchor-math حذف شد)
- `macro.value_hemat_all_market` از همان /api/mstat/smart-money
- Axis چارت: ایزوله LTR؛ سورت صعودی `a.time-b.time` قبل از feed
- طلا در targetAllocation: فیزیکی ۲۵ + صندوق/گواهی ۲۰ (جمع ۱۰۰٪)

## ریسک‌های محیط free-model
این ماشین چند بار zombie/quota دید (_pattern در PLAYBOOK). روی Hermes با مدل‌های پایدارتر این‌ها کمترند، ولی PLAYBOOK-ORCHESTRATOR را نگه دارید.


## به‌روزرسانی (ایجنتهد main — 2026-09-14 ~19:00)
- **agent/fundamental (F-01)** مرج شد: `git merge agent/fundamental` → `b261abe` (کارت خالی FTS + جای پنل تنظیمات). vitest ۴۰۸/۳۸ سبز، eslint صفر، build سالم.
- **فیکس سیستمیک `frontend/src/index.css`** (خارج قلمرو ایجنت‌ها، اعمال هد): کلاس‌های `.glass-panel/.glass-strip/.num/.panel-in/.scale-in/.conflict-pulse/.flash-up/.flash-down/.hud-beam/.neon-edge-cyan` داخل `@layer components` رفتند تا utilities تیلویند (`fixed/sticky/rounded-*`) دیگر باطل نشوند → Sidebar (sticky) و widgets/SymbolInspector (fixed) و کارت‌های rounded-* هم اصلاح شدند. کامیت `2a4e4c2`.
- ⚠️ **سرور 8012 الان از ریپوی `Desktop\BorsTerminal_Ultimate` (دیست قدیمی، 3:08PM) سرو می‌کند، نه از `_Base`.** برای دیدن فیکس‌ها یا سرور را از ریشهٔ `_Base` بالا بیاورید یا `frontend/dist` همان ریپو را rebuild کنید.


## به‌روزرسانی ۲ (ایجنتهد main - 2026-09-14 ~19:20)
- **agent/technical (T-01)** مرج شد: fast-forward به `2a4e4c2` (فاز 1-2 کامل + شروع فاز 3). نمای «کل بورس» بدون نماد + سایدبار راست ۴تب (دیده‌بان/سیگنال FTS/ترازها/نبض کلان). vitest 437/41 سبز · eslint صفر · build سالم.
- باقیمانده‌ی فاز 3: ابزارهای رسم + دیالوگ تنظیمات (طبق docs/CHART-PARITY-REFERENCE.md). نیاز خارج‌قلمرو: اندپوینت OHLC «شاخص کل» (اختیاری/جایگزین نمای کلان).


## به‌روزرسانی ۳ (ایجنتهد main, 2026-09-14 ~19:40)
- **agent/technical (ادامه‌ی فاز 3)** مرج شد (`efef9c3` + merge commit `2a4e4c2`). ریل ابزار ترسیم (خطوط/کانال/فیبوناچی/حاشیه‌نویسی + واگرد/ازنو/پاک/پنهان)، مقیاس قیمت/شبکه/کراس‌هیر، اصلاح candle.type به مقادیر معتبر vendor، DrawingToolbar + lib/drawingTools. vitest 444/41 سبز · eslint صفر · build سالم.
- باقیمانده‌ی فاز 3 (آگاهانه): مقایسه نماد، هشدار، بازپخش، انتشار، چیدمان‌ها، دیالوگ کامل Settings، Properties هر ابزار، میان‌برها، magnet/stay-in-draw، Heikin-Ashi/Renko/Kagi/PnF، تایم‌فریم‌های درون‌روزی.


## به‌روزرسانی ۴ (ایجنتهد main, 2026-09-14 ~20:00)
- **agent/technical (ادامه‌ی فاز 1)** مرج شد: `986f082` + merge commit `fef5d51`. (feed: ترجیح /api/chart با fallback به /api/history + نشانهٔ منبع؛ لایهٔ دادهٔ واحد useMarketSeries؛ رادار سلامت کلان؛ fallback اولین نماد screener). vitest 455/43 سبز · eslint صفر · build سالم.
- سوییچ نمای «کل‌بورس» به `/api/index/tedpix` **هنوز اعمال نشده** (منبع فعلی `local:mstat-timeline`)؛ اما useMarketSeries/buildMarketSeries دقیقاً همان seam جای‌گزینی است (یک تابع).
- باگ بک‌اند (خارج‌قلمرو): `/api/history` و `/api/fts` تطبیق نماد را دقیق (WHERE symbol=?) می‌زنند و DB بعضی نمادها را با «ك/ي» عربی ذخیره کرده (344 نماد KAF عربی، 554 YEH) ⇒ تاریخچه/FTS این نمادها خالی می‌ماند. /api/chart سالم است (CDN + نرمال‌سازی). نیازمند نرمال‌سازی سمت پایتون.


## به‌روزرسانی ۵ (ایجنتهد main, 2026-09-14 ~20:15)
- **agent/fundamental (F-02)** مرج شد: `a092417` + merge commit `0e16fb8`. (جدول شاخص 2 چهار‌دحالته؛ lib/epsHistory.ts منبع واحد؛ برچسب یکسان جدول/نردبان/drill-down.) اعتبارسنجی روی درخت تمیز `0e16fb8`: vitest 468/44 سبز · eslint صفر · build سالم.
- نیاز خارج‌قلمرو (پایتون = قلمرو هد): در `fts_engine.py::bulk_scan` وقتی `len(solo)<eps_years`، `eps_series` None می‌شود و دو سال از پیلود اسکنر حذف می‌شود (۷۳۲ ردیف اسکنر با eps_series=null). پچ پیشنهادی ایجنت ابلاغ شد.
- یافته برای تصمیم هد: ناهمخوانی مسیر اسکنر/جزئیات (۱۵۷ از ۱۶۰ نمونه‌ی gap در جزئیات ۳ سال دارند) و اختلاف امتیاز اسکنر/جزئیات.
- توجه: چک‌اوت Base از ~20:10 کار uncommitted هد (ری‌فکتور پوسته/دیزاین + api/*.py) دارد؛ مرج‌ها با آن تداخل نکردند و اعتبارسنجی در ورکتری تمیز انجام شد.


## به‌روزرسانی ۶ (ایجنتهد main, 2026-09-14 ~20:20)
- **agent/technical (T-02 / باقیماندهٔ فاز 3)** مرج شد: `1a89d54` + merge commit `007b9d2`. (نمای «کل‌بورس» به سری واقعی `/api/index/tedpix?limit=0` → 4284 کندل + fallback؛ ابزارهای ترسیم vendor + سفارشی FTS؛ دیالوگ تنظیمات چارت + پنل تنظیمات ابزار.) اعتبارسنجی روی درخت تمیز `007b9d2`: vitest 482/45 سبز · eslint صفر · build سالم.
- باقیماندهٔ شناخته‌شده: ویرایش مختصات، تب هشدار (هشدار سرور).
- ⚠️ ورکتریِ تمیزِ موقتِ اعتبارسنجی در به‌روزرسانی ۷ امن حذف شد: `BorsTerminal_Ultimate_Base_worktrees\_verify-head` (detached @007b9d2) که داخل `frontend/node_modules` یک junction به node_modules اصلی دارد. برای حذف امن: اول `cmd /c rmdir "...\_verify-head\frontend\node_modules"` و بعد `git worktree remove --force`. حذف با PowerShell `-Recurse` روی junction خطرناک است (محتوای node_modules اصلی را پاک می‌کند).


## به‌روزرسانی ۷ (ایجنتهد main, 2026-09-14 ~20:30)
- هولد-مرجِ مالک مأموریت برداشته شد (رفکتور UI `f077d6f` + فیکس نماد `c831b6e` لند شدند). مرج‌های ایجنتی از سر گرفته شد.
- ورکتریِ موقتِ `_verify-head` **به‌صورت امن حذف شد** (junction با `cmd rmdir` سپس `git worktree remove --force`؛ node_modules اصلی سالم).
- master HEAD = `f077d6f` — اعتبارسنجی: vitest 482/482 (45 فایل) · eslint صفر · build سالم. هیچ برنچ ایجنتی الان جلوتر از master نیست (همه مرج‌شده؛ tape/master-portfolio هنوز روی snapshot پایه).


## به‌روزرسانی ۸ (ایجنتهد main, 2026-09-14 ~20:40)
- **agent/technical (T-02)** مرج شد: `157fd7f` + merge commit `fe784aa`. منطق انتخاب سری در `useMarketMacro` متمرکز شد (اول `/api/index/tedpix` با status==success و کندل معتبر → چارت شاخص کل؛ وگرنه fallback صادقانه به `/api/mstat/timeline`)؛ `useMarketSeries` به re‌export تبدیل شد (import پایدار)؛ `MarketOverview` ادعای «شاخص کل نیست» را حذف و منبع TEDPIX را نشان می‌دهد. اعتبارسنجی روی master: vitest 484/484 (45 فایل) · eslint صفر · build سالم.


## به‌روزرسانی ۹ (ایجنتهد main, 2026-09-14 ~20:55)
- هد پچ `fts_engine.py::bulk_scan` را لند کرد (`ea1b7d7`: نگه‌داشتن سری ۲ساله + eps_years_available/required).
- **agent/technical (T-03 بخش 1)** مرج شد: `20c947a` + merge commit `b28a2fd`. (MA14 = کندل کامل زیر خط؛ آستانهٔ CHoCH 0.3%؛ RSI(14) وایلدر + واگرایی؛ ستاپ fibonacci لوگ؛ حد ضرر سوینگ؛ تست technical-fts-spec.) اعتبارسنجی: vitest 496/496 (46 فایل)، eslint صفر، build سالم.
- ⚠️ نکته: `app-shell.spec` زیر بار موازی کامل گاهی فلیک می‌کند (یک‌بار قرمز شد؛ رانِ تنها و ران مجدد سبز).
- T-03 بخش 2 (شکاف‌سنجی TradingView) اطلاعاتی است؛ نیازمند تصمیم کاربر دربارهٔ موتور چارت (نبود onOverlaySelected در klinecharts v10، نبود دادهٔ درون‌روزی، و Alerts/Trade نیازمند بک‌اند).


## به‌روزرسانی ۱۰ (ایجنتهد main, 2026-09-14 ~21:05)
- **agent/fundamental (F-03)** مرج شد: `2767a5a` + merge commit `fe592d5`. (`lib/gapReason.ts` منبع واحد «علت + راه‌حل»؛ جایگزینی برچسب‌های عمومی «شکاف داده»/«بدون داده» با متن علت‌محور + tooltip در جدول/کارت/drill-down/نردبان EPS/بنر.) اعتبارسنجی: vitest 496/496 (46 فایل)، eslint صفر، build سالم.
- شفافیت داده: برای «صفر سال» شاخص 2 متن «صورت مالی سالانه نیست» عمداً گذاشته نشد (یافتهٔ F-02: اسکنر ممکن است سری ۲ساله را کنار گذاشته باشد)؛ متن به وضعیت پیلود وفادار است.


## به‌روزرسانی ۱۱ (ایجنتهد main, 2026-09-14 ~21:20)
- هد `lightweight-charts@5.2.1` را افزود (`1782687`) و T-04 را داد (مهاجرت موتور چارت).
- **agent/technical (T-04 فاز 1)** مرج شد (fast-forward): `214fa70`. رندرر `lightweight-charts` + datafeed پشت سوییچ موتور (`ftsConfigStore.chartEngine`، پیش‌فرض klinecharts؛ LW با React.lazy در چانک جدای 179KB). از همان هوک‌های موجود (useCandleFeed / هوک کلان / دیده‌بان) بدون اندپوینت جدید. اعتبارسنجی: vitest 504/504 (47 فایل)، eslint صفر، build سالم.
- `npm install` لازم نشد (lightweight-charts از قبل در node_modules بود). ورکتری‌ها frontend/node_modules را با junction به Base به اشتراک می‌گذارند ⇒ ایجنت‌ها نباید npm install بزنند.
- فاز 2 T-04 (ابزار ترسیم/دیالوگ ابزار روی LW) هنوز شروع نشده.


## به‌روزرسانی ۱۲ (ایجنتهد main, 2026-09-14 ~22:40)
- **agent/technical (T-06)** مرج شد (fast-forward): `7a7f338`. پولیش ظاهری شل چارت به سمت TV (پالت پس‌زمینه/گرید hairline، محورها و کراس‌هیر، افسانهٔ شیشه‌ای با اعداد فارسی و چیدمان LTR، ریل ترسیم با آیکون‌های SVG یکدست و flyout فشرده با شمارنده) — فقط استایل/markup؛ مسیر داده و رندر دست‌نخورده. اعتبارسنجی: vitest 504/504 (47 فایل)، eslint صفر، build سالم.


## به‌روزرسانی ۱۳ (ایجنتهد main, 2026-09-14 ~23:00)
- **agent/fundamental (F-04)** مرج شد: `af04d56` + merge commit `2f6eb81`. بج «مجمع نزدیک» از رویدادهای تقویم؛ منبع واقعی: فیلد `events` در `/api/ma/{symbol}` (نه `/api/chart` که فقط adjustEvents دارد)؛ منطق انتخاب خالص در `lib/assemblyEvent.ts`؛ برچسب صادقانه برای لغو/تعویق/تغییر زمان؛ بدون رویداد/خطا ⇒ بدون بج. اعتبارسنجی: vitest 518/518 (48 فایل)، eslint صفر، build سالم.
- نیاز بک‌اند (پیشنهاد ایجنت): اندپوینت سبک `GET /api/calendar/{symbol}` که فقط `_cal_events_for(symbol)` را بدهد — الان بج ناچار سری MA را هم می‌کشد. فرانت یک‌خطی url عوض می‌کند.
- نکته node_modules: ورکتری serene-mountain (بنیادی) node_modules **خصوصی** دارد؛ neat-plateau (تکنیکال) با junction به Base مشترک است. قاعده: فقط در ورکتریِ با junction هرگز npm install نزن (چک: ReparsePoint).


## به‌روزرسانی ۱۴ (ایجنتهد main, 2026-09-14 ~23:30)
- هد اندپوینت سبک تقویم را لند کرد (`a36f954`: `GET /api/calendar/{symbol}` + اسکریپت نرمال‌سازی نماد) — دقیقاً نیازِ F-04.
- **agent/technical (T-07)** مرج شد: `4ccb7de` + merge commit `f302825`. کاتالوگ ابزار ترسیم TV-style: فیبوی بازگشتی FTS خطی/لگاریتمی با builder مشترک (log: p(t)=exp(ln p1 + t·(ln p0 − ln p1)))، اندازه‌گیری، پوزیشن لانگ/شورت، toolDefaults برای هر ابزار، تزریق پیش‌فرض در createOverlay. اعتبارسنجی: vitest 530/530 (49 فایل)، eslint صفر، build سالم.
- باقی‌مانده: سوییچ `useCalendarEvents` به `/api/calendar/{symbol}` (یک خط، سمت بنیادی)؛ ویرایش ترسیم‌های قدیمی نیازمند `onOverlaySelected` (خارج d.ts ما).


## به‌روزرسانی ۱۵ (ایجنتهد main, 2026-09-14 ~23:45)
- **agent/fundamental (ادامهٔ F-04)** مرج شد: `5bb2b0f` + merge commit `1ed4180`. بج «مجمع نزدیک» حالا از اندپوینت سبک `GET /api/calendar/{symbol}` می‌خواند و دیگر سری MA را نمی‌کشد (فقط url/کامنت/تست به‌روز شد). اعتبارسنجی: vitest 530/530 (49 فایل)، eslint صفر، build سالم. حلقهٔ تقویم بسته شد: اندپوینت هد (`a36f954`) + فرانت (`5bb2b0f`).


## به‌روزرسانی ۱۶ (ایجنتهد main, 2026-09-15 ~00:05)
- هد دو وابستگی چارت اضافه کرد (`d766150` react-klinecharts-ui، `8a1980f` @klinecharts/extension).
- **agent/technical (T-08)** مرج شد: `37ee8dd` + `60d1695` + merge commit `c7d54d6`. انواع چارت HA/Renko/Kagi/PnF در لایهٔ داده (چون klinecharts v10 ندارد)؛ دیالوگ تنظیمات تب‌دار TV-style با کنترل‌های واقعی موتور؛ پنل ابزار با تب‌ها + ذخیرهٔ پیش‌فرض در localStorage. صادقانه: تب نماد فقط خواندنی (setPriceVolumePrecision حذف شده)، رویدادها خالی با دلیل، هشدار placeholder، مختصات فقط نمایش. اعتبارسنجی: vitest 547/547 (50 فایل)، eslint صفر، build سالم.
- دو ویرایش آینده (نیازمند قابلیت موتور، خارج قلمرو): ویرایش نقاط ترسیم (onOverlaySelected) و نمایش مشروط به تایم‌فریم.


## به‌روزرسانی ۱۷ (ایجنتهد main, 2026-09-15 ~00:30)
- **agent/technical (T-09)** مرج شد: `8b6d13f` + merge commit `2bc9928`. پروب `react-klinecharts-ui@2.2.0` = سازگار (در dist هیچ API حذف‌شدهٔ v9 نیست؛ فقط registerOverlay/Indicator/Hotkey). ادغام جزئی: به‌جای تعویض پوسته/provider، ۱۴ ابزار منتخب TV در گروه «پرفته (TV)» کاتالوگ ثبت شد؛ ثبت lazy (چانک `tvTools` جدا ~176KB). اعتبارسنجی: vitest 554/554 (51 فایل)، eslint صفر، build سالم — TechnicalPage از ~292KB به ~116KB آمد (dist تأیید شد).


## به‌روزرسانی ۱۸ (ایجنتهد main, 2026-09-15 ~01:00)
- **agent/fundamental (F-05)** مرج شد: `3c1d5d5` + merge commit `64bccba`. اصلاحات صفحهٔ بنیادی بر مبنای گزارش کاربر: (1) شاخص 4 = همان فیلدهای بک‌اند (م=12، ضریب ×1، نسبت 0.31)؛ (2) هلدینگ: حذف جانشینی EPS/عدد ساختگی → «نیازمند ارزیابی پرتفوی هلدینگ (N/A)»، رشد فیزیکی برای هلدینگ/مالی/بانکی/بیمه مخفی، کادر تناژ غیر‌تولیدی حذف؛ (3) دلیل رد شاخص 2 از خود داده (`epsFailReason`) به‌جای بنر عمومی؛ (4) بصری: سلول 5 = وضعیت صنعت هم‌رنگ دروازه‌ها (`lib/industryGate`)، واحد فصلی «میلیارد تومان/همت». اعتبارسنجی: vitest 563/563 (52 فایل)، eslint صفر، build سالم.
- نیازهای بک‌اند/تصمیم (هد): (الف) مسیر سالانه‌سازی پویا برای ویسا مردود شده در حالی که months=12/scale=1؛ (ب) قاعدهٔ کاربر «نسبت ≥1 ⇒ ارزنده» vs آستانهٔ `v10_sales_to_mcap_min: 0.33`؛ (ج) `kind='holding'`/`volume_applicable=false` برای صنعت سرمايه‌گذاري‌ها + NAV پرتفوی برای P/NAV واقعی؛ (د) متن `reason` شاخص 2 از trend شکست ساخته شود (به‌جای soft-gap).


## به‌روزرسانی ۱۹ (ایجنتهد main, 2026-09-15 ~01:30)
- **agent/technical (T-10)** مرج شد: `9f87c56` + `0840609` + `82c94cb` + merge commit `328791e`. سه قابلیت:
  - Bar Replay (`lib/replay` + `stores/replayStore` + `ReplayBar`): اسلایدر/پخش/سرعت؛ کندل‌های بعد از مکان‌نما در لایهٔ داده بریده می‌شوند.
  - Split View 1/2/4 + همگام‌سازی کراس‌هیر و زوم/بازهٔ بین پنل‌های هم‌گروه (`lib/chartSync` + `SplitChartView`)؛ اورلی‌های FTS فقط پنل اول.
  - مقایسهٔ چند نماد با نرمال‌سازی base=100 (`lib/compare` + `ComparePanel`)؛ دادهٔ ناکافی ⇒ «بدون داده».
  بستهٔ `@klinecharts/extension` استفاده نشد (منطق اختصاصی). اعتبارسنجی: vitest 585/585 (55 فایل)، eslint صفر، build سالم (TechnicalPage ~127KB).


## به‌روزرسانی ۲۰ (ایجنتهد main, 2026-09-15 ~02:00)
- **agent/technical (T-12)** مرج شد (fast-forward): `e94b534`. چهار شکاف ابزار ترسیم:
  1) قفل حالت ترسیم — با property واقعی `lock` در klinecharts v10 (`overrideOverlay {groupId, lock}`).
  2) کپی ترسیم — جابه‌جایی افقی 5 روز + حفظ styles/extendData.
  3) گروه/پوشه — تگ `groupId`، فهرست/پنهان/حذف/گروه هدف (صادقانه در UI: گروه = برچسب است نه پوشهٔ واقعی).
  4) تغییر اندازهٔ همه — ⚠️ فقط ضخامت خط (`styles.size`، 1→2→3)؛ resize هندسی اشکال در API موتور پشتیبانی نمی‌شود ⇒ پیاده نشد (بدون ادعای کاذب).
  اعتبارسنجی: vitest 593/593 (56 فایل)، eslint صفر، build سالم (TechnicalPage ~132KB).


## به‌روزرسانی ۲۱ (ایجنتهد main, 2026-09-15 ~02:30)
- (میان این و قبلی، هد کامیت‌های زیادی لند کرد: `104f854` portfolio basket، `e150dce` responsive shell فاز 2، `3b0141b` UI فاز 3 (type floor مشترک + کنتراست تم روشن)، و `1d4f963` که هر ۴ موردِ F-05 را پیاده کرد: آستانهٔ sales/mcap=1.0، هلدینگ + مخفی‌کردن رشد حجم، reason شاخص 2 مبتنی بر trend، گارد سالانه‌سازی 12ماهه.)
- **agent/fundamental (UI-1)** مرج شد (fast-forward): `3e5ff33`. ۵۸ مورد `text-[9/10/11px]` در ۱۰ فایل features/fundamental به `text-2xs` (کف 12px). اعتبارسنجی: vitest 605/605 (57 فایل)، eslint صفر، build سالم. تأیید شد در fundamental صفر مورد باقی است.
- ⚠️ باقی‌مانده: ۲۰۹ مورد `text-[9-11px]` در سایر تب‌ها (market/technical/master/portfolio/app) هنوز هست — type floor فقط fundamental + shared اعمال شده.


## به‌روزرسانی ۲۲ (ایجنتهد main, 2026-09-15 ~03:00)
- **agent/technical (T-13)**: جایگزینی drop-in پکیج «جمینای» ممکن نیست — برای klinecharts v9 نوشته شده و روی v10 کامپایل نمی‌شود (≌13 خطا: applyNewData/setOverlayOptions نبود، امضای createIndicator v9، LineType تم). هیچ کامیتی نزده شد (درست).
- ⚠️ حادثه و پاک‌سازی: ایجنت پوشهٔ untracked `frontend/src/features/technical/nahayatnegar/` را در ورکتری neat-plateau جا گذاشته بود که `tsc -b`/build را قرمز می‌کرد؛ حذفِ او با گارد ایمنی رد شد. من پوشه را حذف کردم و `npx tsc -b` ورکتری الان exit=0 (سبز). چک‌اوت اصلی Base از اول تمیز بود (فقط `dev/eval/` untracked).
- پورت پیشنهادی (مرحلهٔ بعد، ~۱ پاس، تصمیم با هد): applyNewData→setDataLoader؛ امضای createIndicator؛ setOverlayOptions→overrideOverlay/styles؛ اصلاح شکل تم به LineType؛ افزودن corporateActions + اتصال lib/adjustments به adjustEvents؛ اتصال دوبارهٔ اورلی‌های FTS.


## به‌روزرسانی ۲۳ (ایجنتهد main, 2026-09-15 ~03:30)
- **agent/technical (T-14)** مرج شد (fast-forward): `754277d`. جایگزینی کامل چارت تب تکنیکال با نسخهٔ NahayatNegar-سبکِ ساختهٔ جمینای + پورت ۶ نقطه‌ای به v10 (applyNewData→setDataLoader/resetData؛ createIndicator شیئی v10؛ setOverlayOptions→overrideOverlay؛ yAxis log با setStyles؛ setFormatter جلالی؛ corporateActions از adjustEvents + lib/adjustments). اعتبارسنجی: vitest 607/607 (58 فایل)، eslint صفر، build سالم.
- ⚠️ رگرسیون‌های موقت (خود‌گزارش): اورلی‌های FTS روی چارت جدید **وصل نشدند**؛ Split View موقتاً **غیرفعال** شد. اندازهٔ چانک `TechnicalPage` ~367KB (klinecharts داخلش؛ قابل lazy در مرحلهٔ بعد).
- حفظ‌شده: سایدبار راست، بازپخش، مقایسه، پنل‌های تحلیل FTS. هیچ فایل موقتِ untracked نمانده (اسکرچ فقط در .openclaw/tmp).


## به‌روزرسانی ۲۴ (ایجنتهد main, 2026-09-15 ~03:50)
- **agent/technical (T-15)** مرج شد: `51b8fc8` + merge commit `b98a139`. رفع دو رگرسیون T-14 + lazy:
  1) اورلی‌های FTS دوباره وصل شدند (`registerFtsOverlays`: کمربندهای فیبوی لوگ 0.33-0.40/0.618-0.70 + تراز 1.0، مارکرهای ستاپ جت/پولبک/کف‌دوقلو/شکارِ نقطه، خط جت؛ اندیکاتورها MA14/21/52/100 روی قیمت، MA21 حجم، RSI(14) وایلدر در پنل جدا).
  2) Split View دوباره فعال (چیدمان 1/2/4 + sync کراس‌هیر/زوم با `chartSync`؛ پنل‌ها با رپر v10 خودمان).
  3) Lazy: چارت جمینای با React.lazy/Suspense جدا ⇒ `TechnicalPage` از ~367KB به **106.7KB** (gzip 33KB).
  اعتبارسنجی: vitest 607/607 (58 فایل)، eslint صفر، build سالم (اندازه‌ها در dist تأیید شد).


## به‌روزرسانی ۲۵ (ایجنتهد main, 2026-09-15 ~04:15)
- **agent/technical (T-16)**: ادغام پکیج `gem13_003154` انجام نشد — هنوز کامل پورت نشده؛ با v10.0.3 پنج خطا می‌دهد (`createIndicator` 3‌آرگومانی، `{type:string}` به‌جای boolean، `IconCheck` بی‌استفاده، `body` بی‌استفاده). ایجنت تغییرات را با `git checkout` برگرداند و درخت سبز ماند؛ master دست‌نخورده (`072c14a`). هیچ کامیتی نزده شد (درست).
- ⚠️ پاک‌سازی: یک فایل یتیمِ untracked `frontend/src/features/technical/nahayatnegar/lib/ftsOverlays.ts` در ورکتری neat-plateau مانده بود (حذفِ ایجنت با گارد ایمنی رد شد). من حذفش کردم و `npx tsc -b` ورکتری الان exit=0 (سبز).
- مرحلهٔ بعد (با dispatch، ~۱ پاس): همان ۵ خطا در nahayatnegar فیکس؛ صفحه به `KLineChartWrapper` جدید (default export) وصل؛ تست `technical-nn-chart` به نام جدید به‌روز. سایدبار/Replay/مقایسه/Split دست‌نخورده می‌مانند.


## به‌روزرسانی ۲۶ (ایجنتهد main, 2026-09-15 ~04:45)
- **agent/technical (T-17)** مرج شد (fast-forward): `01a5e54`. تکمیل پورت چارت جمینای به v10: رفع ۵ خطا (createIndicator شیئی v10 + setPaneOptions؛ getConvertPictureUrl(true)؛ حذف IconCheck/body بی‌استفاده؛ as never؛ هدر eslint-disable برای کد vendored)، وصل صفحه به default export جدید `KLineChartWrapper` + حذف پراپ‌های قدیمی، به‌روزرسانی تست `technical-nn-chart`. سایدبار/Replay/Compare/Split دست‌نخورده.
- اعتبارسنجی روی master: vitest 607/58 سبز (کامیت‌شده؛ رانِ محلی با probe سرگردانِ هد = 609/59)، build سالم (TechnicalPage 106.6KB، چارت در چانک جدا 49.9KB)، eslint **0 error / 3 warning** (disableهای بلااستفاده در کد vendored — فقط cosmetic).
- ⚠️ درخت Base فعلاً WIP هد دارد: `fts_engine.py` تغییر و `frontend/src/__tests__/zzuiprobe.spec.tsx` untracked — دست نزدم.


## به‌روزرسانی ۲۷ (ایجنتهد main, 2026-09-15 ~05:15)
- (میان این و قبلی، هد کامیت‌های FTS Spec v2 را لند کرد: `220b3e5`/`c60f402` docs، `34fad1b` تست‌های فرمول — **Python**: `dev/fts_formula_tests_v2.py` (۷۲ تست، نه vitest)، `dcbc3fc` فیکس FTS spec v2.1.)
- **agent/technical (T-18)** مرج شد: `d3a7562` + `7724bab` + merge commit `80d9c14`. چیدمان full-bleed (بدون اسکرول صفحه؛ داک کشویی `FtsDock` برای کارت‌های حجیم؛ واچ‌لیست ۳ستونی) + پالت تیرهٔ TV در دامنهٔ `.tv-workbench` (`styles/tvTheme.css`). اعتبارسنجی: vitest 607/607 (58 فایل — `app-shell` و `technical-feed` هم سبز بودند؛ فلِیک بار‌محور در این ران نیامد)، eslint 0 error / 3 warning، build سالم (TechnicalPage ~106KB).


## به‌روزرسانی ۲۸ (ایجنتهد main, 2026-09-15 ~05:40)
- **agent/technical (T-19)** مرج شد: `74bee6c` + merge commit `a21c0c9`. چارت‌محور: هدر تک‌خطی 32px (نماد/کندل/جهت + خلاصهٔ FTS + تنظیمات)، داک پایین (حالت جمع = استاتوس‌بار 28px)، سایدبار راست جمع‌شو (ریل 32px)، حذف کادر مردهٔ چارت + `ResizeObserver`، اورلی‌های فیبو ظریف‌تر (alpha 0.16→0.07). اعتبارسنجی نهایی: vitest 607/607 (58 فایل)، eslint 0 error / 3 warning، build سالم (TechnicalPage ~107KB، چارت چانک جدا 50KB).
- ⚠️ مشاهدۀ عملیاتی: در یک رانِ کاملِ **کند** (62s، environment 395s) **۶ تست** قرمز شد (app-shell / market-filters / market-timeline / portfolio-page / technical-tool-settings / technical-toolbar)؛ همه در رانِ تکی سبز بودند و ران کاملِ مجدد 607/607 در 19.5s سبز شد ⇒ فلِیکِ بار‌محور (گسترده‌تر از فقط app-shell). توصیه: تست کامل را هم‌زمان با پروسه‌های سنگین اجرا نکنید؛ اگر ran قرمزِ پراکنده دیدید، اول با رانِ مجدد/تکی تأیید کنید.


## به‌روزرسانی ۲۹ (ایجنتهد main, 2026-09-15 ~06:10)
- **agent/fundamental (F-06)** مرج شد: `f66863c` + merge commit `3d3e47c`. `AuditBadge` + `AuditReasonCard` + `auditDeviation` + `lib/auditEvidence`؛ بازشوی explainability با `createPortal`/`fixed` (بدون Radix؛ بسته با Esc/بیرون‌کلیک/اسکرول؛ stopPropagation). نصب روی ۶ سلول کارت + ۵ ستون جدول غربالگری؛ target‌ها از `thresholds` پاسخ `/api/screener`. رفتار دفاعی: فیلدهای نبوده فقط موجودها نمایش، بدون عدد ساختگی. `widgets/SymbolInspector` دست‌نخورده. اعتبارسنجی: vitest 622/622 (59 فایل)، eslint صفر، build سالم.
- ⚠️ فلِیکِ بار‌محور تشدید شد: در دو رانِ کندِ متوالی (62s و 78.7s) به‌ترتیب ۶ و **۱۲** تست قرمز شد (پراکنده در همهٔ تب‌ها)؛ همه در رانِ تکی سبز و رانِ کاملِ مجدد 622/622 در 20.3s سبز ⇒ قطعاً محیطی. توصیه: قبل از باور به قرمزِ پراکنده، ران مجدد/تکی بگیرید (سیستم زیر بار سنگین — احتمالاً فرآیندهای موازی).


## به‌روزرسانی ۳۰ (ایجنتهد main, 2026-09-15 ~06:40)
- **agent/fundamental (F-07)** مرج شد: `a8ade67` + merge commit `7a666a8`. کنترل‌های v2.1 در FtsSettingsDrawer: توگل ۱ب «فقط تولیدی» (بانک/بیمه/خدمات/هلدینگ N/A)؛ **رفع باگ واقعی**: خاموش‌کردن توگل قبلاً `v10_volume_growth_min=-1` می‌فرستاد و بک‌اند (`api/market.py`) رد می‌کرد ⇒ حالا `0` + `v10_volume_breadth_min=0` می‌فرستد؛ شاخص 4 با OR + `potential_min=40` (نوشتن هر دو کلید `profit_potential_min` و `v10_potential_min`)؛ دروازه‌های سخت (حذف بیمه، N/A نسبت فروش هلدینگ، استثنای دارویی >50%، حذف بازار پایه). اعتبارسنجی: vitest 627/627 (59 فایل)، eslint 0 error/3 warning، build سالم.
- نیاز بک‌اند (کلیدهای ناشناخته در POST دور ریخته می‌شوند ⇒ باید به `FTS_DEFAULTS` اضافه شوند تا ماندگار شوند): `holdings_sales_na` (bool, true)، `pharma_margin_exempt_min` (float, 0/50)، `exclude_base_market` (bool, true). بیمه فعلاً از مسیر `mandatory_sectors` کار می‌کند.


## به‌روزرسانی ۳۱ (ایجنتهد main, 2026-09-15 ~07:05)
- (هد `AuditBadge` را داخل `SymbolInspector` نصب کرد: `ad21945`.)
- **agent/technical (T-20)** مرج شد: `e13ada7` + merge commit `b3e2144`. پاس QA بصری (autoglm روی :8012): رفع فضای مردهٔ عمودی چارت، سرریز افقی واچ‌لیست (`min-width:0` + `minmax(0,1fr)` + ستون درصد w-16)، رنگ میله‌های حجم سبز/قرمز، مهار اسکرول/ارتفاع. رفع‌نشده (صادقانه): تراز RTL و بریدگی‌های داخل کامپوننت vendoredِ چارت جمینای + کیفیت رندر مارکر «T» (نیازمند پاس جداگانه). اعتبارسنجی: vitest 627/627 (59 فایل)، eslint 0/3، build سالم.


## به‌روزرسانی ۳۲ (ایجنتهد main, 2026-09-15 ~07:35)
- (هد کامیت‌های FTS متعددی لند کرد: `64da1c7` هم‌ترازی screener با نردبان جزئیات (gap 730→181، series 367→692)، `aed28ab` اسکریپت تأیید لایو، `21b1939` rule_ref روی F-01/F-01b/F-02/F-03.)
- **agent/technical (T-21)** مرج شد: `84255c2` + merge commit `654b746`. RTL/بریدگی داخل چارت vendored با CSS اسکوپ‌شده (`direction:rtl` روی کانتینر، **canvas عمداً LTR**، `min-width:0`+`nowrap`، z-index منوها 60) + مارکرهای ظریف‌تر (شعاع مثلث 5-9→4-7، برچسب size 10/bold→9/normal). اعتبارسنجی: vitest 627/627 (59 فایل)، eslint 0/3، build سالم. (ران کند بود: 42.8s/env 531s ولی بدون فلِیک.)


## به‌روزرسانی ۳۳ (ایجنتهد main, 2026-09-15 ~08:00)
- (هد خودش `agent/master-portfolio` (`6b93f1e`) و `agent/tape` (`9d4a763`) را مرج کرد ⇒ شمارش تست به 634/60 رسید.)
- **agent/fundamental (UI-2)** مرج شد: `d726f18` + merge commit `5314e1f`. RTL: فیزیکی→منطقی (`text-start/end`، `ms-`، دراور `start-0`/`border-e`)، ایزولاسیون LTR (`num`) روی اعداد/درصد/تاریخ، آینه‌سازی فلش‌های جهت‌دار (→⇒ به ←⇐)، و رفع هش «button داخل button» (`AuditBadge` trigger → `span` role=button). اعتبارسنجی: vitest 634/634 (60 فایل)، eslint 0/3، build سالم.


## به‌روزرسانی ۳۴ (ایجنتهد main, 2026-09-15 ~08:25)
- **agent/technical (T-22)** مرج شد: `1b2aa35` + merge commit `6077622`. هدر تک‌خطی چارت [نماد|تعداد کندل|جهت | بازپخش|پاپاور متراکم FTS|تنظیمات] (پاپاور = بج‌های وضعیت + جهت/امتیاز/دلیل سیگنال، z-50)؛ پولیش اورلی‌های فیبو/مارکر دوباره تأیید شد. فقط `routes/TechnicalPage.tsx`. صادقانه: نوار ترسیم/جستجو/تایم‌فریم/نوع کندل/اندیکاتورها داخل کامپوننت vendored جمینای هستند و دوباره پیاده نشدند. اعتبارسنجی: vitest 634/634 (60 فایل)، eslint 0/3، build سالم.


## به‌روزرسانی ۳۵ (ایجنتهد main, 2026-09-15 ~08:50)
- **agent/technical (T-23، تحویل جزئی و صادقانه)** مرج شد (fast-forward): `ca27ba3`. فقط **لایهٔ موتور** فاز 3: `lib/drawStore.ts` (persistence با کلید `fts-draw:<symbol>:<timeframe>` + پاک‌سازی نماد، undo/redo پشتهٔ خالص snapshot، `snapToOhlc` با آستانهٔ درصدی) + تست ۱۱تایی. ⚠️ **اتصال به چارت انجام نشد** (بازیابی خودکار در تعویض نماد/رفرش، Delete و Ctrl+Z/Y، سوییچ مگنت) — نقطهٔ اتصال داخل کامپوننت vendored جمینای است و بودجهٔ نوبت تمام شد. اعتبارسنجی: vitest 645/645 (61 فایل)، eslint 0/3، build سالم.
- قدم بعدی پیشنهادی: نوبت مخصوص «wiring» روی `nahayatnegar/components/KLineChartWrapper.tsx`.


## به‌روزرسانی ۳۶ (ایجنتهد main, 2026-09-15 ~09:30)
- **agent/technical (T-24)** مرج شد (fast-forward): `3b0a904`. wiring فاز 3 روی `nahayatnegar/components/KLineChartWrapper.tsx`: بازیابی/ذخیره‌ی ترسیم‌ها با تغییر نماد/تایم‌فریم (اسنپ‌شات دوره‌ای 2s، فیلتر اندیکاتورها)، Delete/Backspace + Ctrl+Z/Y، مگنت واقعی (`snapToOhlc` آستانهٔ 0.4% روی آخرین ترسیم)، `onClearDrawings` + `clearSymbolDrawings`. اعتبارسنجی نهایی: vitest 645/645 (61 فایل).
- ⚠️ فلِیک شدید: ران‌های **موازیِ** من زیر بار سنگین ماشین به‌ترتیب ۹، ۴ و ۱۳ تست قرمزِ **پراکنده** دادند (مثل همیشه در همهٔ تب‌ها)؛ رانِ **سکوئنشال** (`npx vitest run --no-file-parallelism`) **645/645 سبز** شد ⇒ قطعاً contention موازی/بار، نه رگرسیون. توصیه: تحت بار سنگین، تست کامل را سکوئنشال بگیرید (`--no-file-parallelism`).


## به‌روزرسانی ۳۷ (ایجنتهد main, 2026-09-15 ~10:15)
- **agent/fundamental (F-08)** مرج شد: `a427993` + merge commit `cca107e`. مجازی‌سازی جدول غربالگری با `@tanstack/react-virtual` (ردیف ثابت 46px، overscan 8، کانتینر max-h-70vh + هدر چسبان؛ `ScreenerRow` memo؛ `AuditBadge` با memo + evidence تنبل). قبل/بعد (865 ردیف، jsdom): ردیف DOM 865→12-24، گره 32031→<1200، رندر ~867ms→~50ms؛ حالت بسته = صفر محاسبه. + تست نگهبان بودجهٔ کارایی `fts-perf-probe.spec`. اعتبارسنجی: vitest 651/651 (62 فایل، ران سکوئنشال)، eslint 0/3، build سالم.
- ⚠️ محیط به‌شدت زیر بار بود: ران‌های موازی ۳ تا ۱۳ تست قرمزِ پراکنده دادند و یک رانِ سکوئنشال هم ۳ فلیک داد؛ رانِ سکوئنشالِ بعدی 651/651 سبز شد. (احتمالاً سایر سشن‌های ایجنت هم‌زمان vitest اجرا می‌کنند.)
- پاک‌سازی: فایل یتیمِ untracked `fts-perf-probe2.spec.tsx` در ورکتری serene-mountain حذف شد.


## به‌روزرسانی ۳۸ (ایجنتهد main, 2026-09-15 ~10:50)
- (مسیر master: هد `agent/master-portfolio` را مرج کرد → `1537216`؛ شمارش 651→704.)
- **agent/technical (T-25، فاز 4، تحویل جزئی و صادقانه)** مرج شد (fast-forward): `861066a`. موتور شناساگرِ ۹ الگوی FTS در `lib/ftsPatterns.ts` (جت، فیبوی لوگ، CHoCH، نقطه‌زنی، کف‌دوقلو، سر و شانه، سقف سوم، خروج زیر MA14، ساعت شنی) + anti-clutter (`PATTERN_STALE_BARS`) + تست ۱۱تایی. ⚠️ سوییچ‌های مستقل UI + ترسیم واقعی روی چارت ماند برای نوبت بعد (لایهٔ موتور آمادهٔ اتصال). تست‌های پیوت‌محور به «smoke + contract» کاهش یافته (fixture شکننده). اعتبارسنجی: vitest 704/704 (67 فایل، سکوئنشال)، eslint 0/3، build سالم.


## به‌روزرسانی ۳۹ (ایجنتهد main, 2026-09-15 ~11:30)
- **agent/technical (T-26، فاز 4 wiring — تلاش مجدد موفق)** مرج شد: `d45bb52` + merge commit `fcfb867`. سوییچ‌های ۹ الگو (چک‌باکس + رنگ + شفافیت، localStorage `fts-pattern-prefs`) + `buildPatternOverlays` (خاموش ⇒ صفر اورلی؛ anti-clutter) + تست‌های تقویت‌شده. ⚠️ `createOverlay` واقعی داخل کامپوننت vendored هنوز وصل نشده (یک effect کوتاه مانده).
- ⚠️ **master قرمز (پیش از T-26، از `ebae21f` هد):** `symbol-inspector.spec` حالا `getByText('شپنا')` را دوگانه می‌بیند چون VolumeFlowMini برچسب نماد (`span.num.text-2xs`) اضافه کرده و تست قدیمی به‌روز نشده. T-26 بی‌تقصیر است (فقط features/technical). اصلاح ساده: `getAllByText('شپنا')` یا scope دقیق‌تر. (به هد گزارش شد.)


## به‌روزرسانی ۴۰ (ایجنتهد main, 2026-09-15 ~12:00)
- **agent/fundamental (F-09)** مرج شد: `5f1ab6f` + merge commit `26b125f`. فیلتر حذف بر اساس شاخص (۶ سوئیچ + بازنشانی + نوار «X نماد با فیلتر شاخصی حذف شد»)؛ `lib/exclusionFilter.ts`. صداقت: شاخص 1ب بدون دادهٔ ستون/پرچم در غربالگری ⇒ دامنهٔ «بدون داده» و حذف صفر. کلید `exclude_rejected_indicators` در payload ارسال می‌شود. اعتبارسنجی: vitest 730/730 (70 فایل، سکوئنشال — شامل fixِ uncommittedِ هد روی `symbol-inspector.spec`)، eslint 0/3، build سالم.
- نیاز بک‌اند (هد): افزودن `exclude_rejected_indicators` به `FTS_DEFAULTS`/`FTS_LIST_KEYS` برای ماندگاری سمت سرور.
- نکته: تست `symbol-inspector` که از `ebae21f` قرمز بود، با ویرایشِ **uncommittedِ** هد (موجود در درخت) سبز شده؛ با کامیت‌شدنِ آن، baseline کامیت‌شده هم سبز می‌شود.
