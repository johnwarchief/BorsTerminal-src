# STATE — اسنپ‌شات سیستم (به‌روز: 2026-09-14 ۱۶:۰۰ محلی)

## Repo / سرور
- **master HEAD:** `fe784aa` (شامل همهٔ کارها + بستهٔ agent-system؛ سرِ آن `4f180ac` فیکس دراور بنیادی است)
- **خط پایهٔ تست:** ۴۸۴ سبز (۴۵ فایل) · eslint صفر · build سالم
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
