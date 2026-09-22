# Changelog

تاریخچهٔ تغییرات BorsTerminal_Ultimate — هر نسخه یک بخش. فارسی، بدون ZWNJ (قانون پروژه).

> توجه: این فایل بین v7.4.5 تا v9.7.1 پرش دارد (بخش‌های v8/v9 هرگز نوشته نشدند).
> منبع معتبر آن بازه، جدول «بدهی فنی شناخته‌شده» در `REPO_MAP.md` و لاگ کامیت‌هاست.

## [v1.0.18] — 2026-09-22 — تراز جدول‌ها، پنجرهٔ مستقل، کارایی، ریلیزِ امضاشده

- **تراز ستون‌ها:** در ماتریس FTS و جدول تابلو، مقادیر عددی (کلاس `.num` با `direction:ltr`) با `text-end` دقیقاً زیر هدر ستون نشستند (پیش‌تر چپ‌چین می‌شدند).
- **بنیادی:** صندوق/ETF/اوراق از ماتریس حذف شدند؛ برای بانک/بیمه/هلدینگ شاخص‌های ۳ و ۴ برچسب «N/A (ماهیت مالی)» گرفتند؛ ارتفاع جدول کشسان شد (بدون فضای خالی پایین)؛ عنوانِ بالای جدول حذف و دکمهٔ تنظیمات بزرگ‌تر روی نوار جدول آمد.
- **پنجرهٔ مستقل:** اجرا در پنجرهٔ بومی WebView2 (pywebview) بدون مرورگر/تب/نوار آدرس؛ انتخاب خودکار پورتِ آزاد (پایانِ تداخل پورت)؛ fallback مرورگر.
- **نبض بازار:** حلقهٔ اسنپ‌شات هر ۵ دقیقه (فقط داخل ساعت بازار) — رفع «روند ۳-۴ روزه: بدون داده» و نمودار درون‌روز.
- **کارایی و مصرف گرافیک:** حالتِ کم‌مصرف (`data-perf="low"`) روی سیستم‌های ضعیف `backdrop-filter` و انیمیشن‌های بی‌پایان را حذف می‌کند؛ با مخفی‌شدنِ پنجره (`data-idle="1"`) همهٔ انیمیشن‌ها متوقف می‌شوند. باندل‌های هش‌دار `/assets` و `/vendor` با `Cache-Control: immutable` سرو می‌شوند (رفع دانلود دوبارهٔ ~۵۰۰KB)، پیش‌فرض پولینگ ۵s و پولینگ هنگام مخفی‌بودن پنجره خودکار متوقف می‌شود.
- **رنگ و خوانایی:** توکن `--on-accent` اضافه شد و کنتراستِ برچسب‌ها روی کارت‌ها در هر دو تمِ روشن/تاریک به سطح AA رسید (متن سفید روی رنگِ تاکیدی حذف شد).
- **کدال:** پذیرش هدر «مقدار فروش» در کنار «تعداد فروش» برای ستون حجم؛ ابزارهای `dev/backfill_prev_revenue.py` (پرکردنِ ستون‌های مقایسهٔ سالِ قبل) و `dev/db_gap_audit.py`؛ اسنپ‌شاتِ `market.db.lzma` به‌روز شد.
- **گاردها و CI:** `dev/db_housekeeping.py --selftest` اکنون پیش از سنجشِ backfill یک شکافِ مصنوعی می‌سازد (چون اسنپ‌شاتِ ارسالی از قبل پر است) و guards سبز شد. در `release.yml` فایلِ `installer/.setup_password.iss` از سکرت ساخته می‌شود، امضا با نامِ درستِ سکرت `TAURI_SIGNING_PRIVATE_KEY` انجام می‌شود، تگ از `inputs.tag || ref_name` حل می‌شود و انتشار روی ریپوی عمومی با `RELEASE_TOKEN` (PAT) انجام می‌گیرد. `#define AppVersion` در `bors_setup.iss` با `#ifndef` محافظت شد تا `ISCC /DAppVersion` واقعاً اثر کند (پیش‌تر نصابِ v1.0.17 با تگِ اشتباه ساخته می‌شد).
- **ریلیز:** `BorsTerminal_Ultimate_Setup_v1.0.18.exe` (۵۵ مگابایت) امضاشده با minisign (اعتبارسنجی‌شده با `UPDATE_PUBKEY` خودِ برنامه)، به‌همراه `.sig` و `latest.json` روی `johnwarchief/BorsTerminal` منتشر شد.
- **اسکیل‌ها:** پوشهٔ `skills/` شامل `bors-architecture`، `bors-build-release`، `bors-code-review`، `bors-frontend-ui-guard` و `bors-build-install-guard`.

## [v1.0.9] — 2026-09-20 — رفعِ دیتابیسِ ناقص + آپدیتِ خودکارِ silent

- **بحرانی — دیتابیسِ ناقص در v1.0.7/8:** `market.db.lzma`یِ ارسالی پس از استخراج فقط جداولِ پایه را داشت (`financial_statements` غایب بود) و اسکرینر با خطای ۵۰۰ («no such table: financial_statements») fail می‌شد. دو ریشه:
  1. `release.ps1` هر `market.db`ی را بی‌تفتش به `market.db.lzma` فشرده می‌کرد؛ اگر dbِ محلی ناقص بود، همان نسخهٔ ناقص شناخته و ارسال می‌شد.
  2. `ensure_market_db()` فقط `instruments`+`daily_prices` را برای پذیرشِ یک db موجود چک می‌کرد — دقیقاً همان جداولی که db ناقص داشت. نتیجه: کاربری که db ناقص را استخراج کرده بود، حتی پس از ارتقا هم دیتای ناقص را نگه می‌داشت چون فایلِ قدیمی روی دیسک محفوظ می‌ماند.
- **رفع:** `market.db.lzma` از HEAD بازیابی و یکپارچگی‌اش تأیید شد (۱۰۳.۳ مگابایت پس از استخراج: instruments=۵۱۲۹، daily_prices=۶۰۶۳۷، financial_statements=۸۰۰۹). `ensure_market_db()` اکنون `financial_statements` را هم الزامی می‌کند و dbهای ناقص را کنار گذاشته و دوباره از `market.db.lzma` استخراج می‌کند — پس ارتقا از روی v1.0.7/8 هم دیتای ناقص را اصلاح می‌کند. `release.ps1` قبل از فشرده‌سازی منبع را اعتبارسنجی می‌کند (جداول + تعدادِ ردیف)، از baselineیِ فعلی بکاپ می‌گیرد، round-tripِ lzma را تأیید می‌کند و در صورتِ ناکامی baseline را برگردانده و متوقف می‌شود. همچنین یک `market.db`یِ سرگردان در `dist/` دیگر سرازیر نصب نمی‌شود.
- **آپدیتِ خودکارِ silent:** رمزِ نصب‌کننده (`.setup_password.iss`، gitignore‌شده) اکنون داخلِ باندل در `_internal` قرار می‌گیرد، در نتیجه `_setup_password()` در `/VERYSILENT` آن را پیدا کرده و نصبِ خودکار بدونِ پرسش کار می‌کند. `api.update` و `bors_minisign` به hiddenimports اضافه شدند.
- **امضای minisign:** مسیرِ اثبات‌شدهٔ `_pysign_v108.py` به `scripts/sign_setup.py` منتقل شد (tauri-first با timeoutِ ۱۲۰ ثانیه + fallbackِ minisignِ خالصِ پایتون + تأییدِ امضا) و به `release.ps1` متصل شد؛ بدونِ امضای معتبر بیلد متوقف می‌شود.
- **هماهنگیِ نسخه‌گذاری:** `bors_config.py`، `installer/bors_setup.iss`، `frontend/src-tauri/tauri.conf.json`، `frontend/package.json` و `scripts/publish_github_release.py` به ۱.۰.۹.



## [v1.0.8] — 2026-09-20 — رفعِ خطای دیتابیس روی نصبِ all-users (بحرانی)

- **ریشهٔ باگ:** `_resolve_market_db()` در `bors_config.py` مسیرِ نصب (کنارِ EXE) را به‌عنوانِ market.db ترجیح می‌داد. در نصبِ all-users (Program Files) آن پوشه فقط‌خواندنی است: sqlite می‌تواند فایل را بخواند ولی `PRAGMA journal_mode=WAL` — که `api/_core.py:get_db()` روشن می‌کند — باید `market.db-wal` و `market.db-shm` را کنارش بسازد که ممکن نیست؛ نتیجه «unable to open database file» روی هر اتصال و خطای ۵۰۰ در همهٔ مسیرهای دیتابیس (اسکرینر، چارت/تاریخ، سینک) به‌محضِ استارت. `ensure_market_db()` پایگاه داده را درست در `WORK_DIR` استخراج می‌کرد ولی `DB_PATH` (استفاده‌شده توسط `get_db()`) همچنان به مسیرِ فقط‌خواندنی اشاره می‌کرد، یعنی استخراج بی‌فایده می‌ماند.
- **رفع:** `_resolve_market_db()` اکنون مثلِ `_work_dir()` با `_writable()` از exe_dirِ غیرنوشتنی صرف‌نظر می‌کند و فقط روی `WORK_DIR` (محلِ نوشتنیِ کاربر: `%LOCALAPPDATA%\BorsTerminal_Ultimate\data`) می‌افتد. market.dbیِ باندل‌شده کنارِ EXE در نصبِ per-user (نوشتنی) مثلِ قبل مستقیماً استفاده می‌شود، ولی در نصبِ all-users از روی `market.db.lzma`یِ همراه برنامه در مسیرِ نوشتنی استخراج می‌شود. این همان کلاسِ باگِ کشِ اسکرینرِ v1.0.7 است.
- **توضیحات:** کامنتِ `bors_entry.py` که می‌گفت `ensure_market_db` «همیشه در WORK_DIR می‌نویسد» اصلاح شد (در حالتِ per-user کنارِ EXE می‌نویسد؛ نکتهٔ تعیین‌کننده خودِ `DB_PATH` است که اکنون فقط به محلِ نوشتنی اشاره می‌کند).
- **هماهنگیِ نسخه‌گذاری:** `bors_config.py`، `frontend/src-tauri/tauri.conf.json`، `frontend/package.json` (+ lock)، `installer/bors_setup.iss` و `scripts/publish_github_release.py` به ۱.۰.۸.
- **توزیع:** push تگِ `v1.0.8` گردشِ کارِ `.github/workflows/release.yml` را راه می‌اندازد → نصابِ Inno + `latest.json`ِ امضاشده با minisign؛ نصب‌های قبلی به‌طور خودکار این نسخه را دریافت و نصب می‌کنند.

## [v1.0.3] — 2026-09-19 — ریلیز دسکتاپ: اصلاح طبقه‌بندی تابلوی بازار + اصلاح «رزولوشن»

- **اصلاح طبقه‌بندی (موتور v9.10.1):** اختیارها که TSETMC در فهرستِ `paperType=1` می‌فرستاد، به اشتباه «سهام» خوانده می‌شدند و حجمِ خردِ خود را به تابلوی «سهام و حق تقدم»، تجمیعِ حجم، و جدولِ الگوی ساعت تزریق می‌کردند. `mstat_engine.classify` حالا پیش از `paperType` و از روی نام، اختیارها را جدا می‌کند و `fetch_paper_types` دیگر `paperType` اختصاصی به آن‌ها نمی‌دهد (خود-ترمیمیِ بانک در سینکِ بعدی). تابلوی سهام از ۲۳۴۴ به ۲۳۱۵ نماد اصلاح شد. جزئیاتِ کامل در بخشِ [v9.10.1].
- **اصلاح نمایشِ حجمِ خرد (موتور v9.10.1):** سهامِ گران‌قیمت با حجمِ کم (مثلاً سپامهر: ۹٬۹۵۹ سهم در ۶۵ معامله و ~۴۸۴ میلیون ریال ارزش) حجمشان در یکای «میلیارد سهم» با ۴ رقمِ اعشار به `۰٫۰۰۰۰` گرد می‌شد — هم نمایشِ غلطِ یک سهمِ معامله‌شده، هم شکستنِ سرتیبِ حجم (همهٔ سهم‌های زیرِ ۱۰۰ هزار در ۰ قفل می‌شدند) و هم شکستِ کاذبِ گاردِ «نامزدِ بی‌معامله نداریم». دقتِ `vol_b_shares` به ۶ رقمِ اعشار رفت (حداقلِ ۱۰۰۰ سهم قابل‌نمایش) و گارد حالا روی تعدادِ معاملهٔ خام (`trades > 0`) سنجیده می‌شود — «بی‌معامله» یعنی صفرِ معامله، نه صفرِ مقدارِ گردشدهٔ نمایشی. گاردِ `dev/mstat_local_v975.py` **۱۴۰/۱۴۰ سبز**. جزئیات در بخشِ [v9.10.1].
- **اصلاح «رزولوشن» (فضای خالی روی مانیتورهای ۲K):** محتوای صفحه در نمایشگرهای ≥۱۹۲۰px به عرضِ ثابتِ ۱۶۰۰px (در ۴K: ۱۹۲۰px) محدود و وسط‌چین می‌شد، در حالی که نوارِ تبِ بالای صفحه تمام‌عرض بود؛ نتیجه، فضای خالیِ چپ/راستِ محتوا روی مانیتورهای ۲K بود. سقفِ عرضِ محتوا (`--content-max-w` در `frontend/src/shared/styles/tokens.css`) در ۲K/۴K حذف شد تا جدول‌ها و چارت‌ها مثل نوار تب، تمام‌عرض رندر شوند. مقیاسِ تایپوگرافی و gutter واکنشی دست‌نخورده باقی ماند.
- **هماهنگیِ نسخه‌گذاری:** `frontend/src-tauri/tauri.conf.json`، `frontend/package.json`، `useAppUpdater.ts` (سه fallback)، `scripts/build_installer_exe.py`، `scripts/publish_github_release.py` و `installer/bors_setup.iss` همه به ۱.۰.۳ بروز شدند.
- **اصلاح لینکِ «دانلود مستقیم Setup.exe» در `UpdateManagerModal`:** این دکمه هنوز به `BorsTerminal_Ultimate_Setup_v1.0.2.exe` اشاره می‌کرد و بلافاصله پس از ریلیزِ v1.0.3 (وقتی `releases/latest` به نسخهٔ جدید می‌چرخد) با خطای ۴۰۴ مواجه می‌شد. به `BorsTerminal_Ultimate_Setup_v1.0.3.exe` اصلاح شد — دقیقاً همان نامی که `scripts/publish_github_release.py` به‌عنوان asset آپلود می‌کند.

- **سختی‌گیری و تکمیلِ مهاجرتِ `strictGates` (تغییراتِ تجمیعی):** حدودِ ۲۵ فایلِ اصلاح‌شده در جلساتِ پیشین همراه با این ریلیز منتقل می‌شوند: رفعِ متغیرِ تعریف‌نشدهٔ `cur` در `api/fundamental.py`، کلیدِ `action`→`direction` در `signalStore`، تایپِ دقیقِ `http()` در `SymbolSearchModal`، بازنویسیِ `breakpoints.ts` برای ۲K/۴K، و حذفِ کدِ مرده. همچنین فراخوان‌های `strictGates` بروز شدند تا `warRegime`/`symbolWeightPct` را بگذرانند و مهاجرت کامل شود. این بخش شرطِ لازم برای build/tscِ سبز روی یک checkoutِ تمیز است (HEADِ قبلی `strictGates` را با امضایِ سخت می‌خواست ولی فراخوان‌ها هنوز بروز نشده بودند).
- **توزیع:** push تگِ `v1.0.3` گردشِ کارِ `.github/workflows/release.yml` را راه می‌اندازد → نصابِ NSIS/MSI + `latest.json`ِ امضاشده با minisign (كلید خصوصی در GitHub secrets)؛ نصب‌های قبلی به‌طور خودکار این نسخه را دریافت و نصب می‌کنند.

## [v9.10.1] — 2026-09-19 — جداکردنِ اختیارها از سطرهای سهام (فاز ۱)

- **ریشهٔ باگ:** TSETMC در یک تغییرِ اخیر، قراردادهای اختیار را در پاسخِ `paperType=1` (همان فهرستِ سهام) هم برمی‌گرداند. `fetch_paper_types` در `test_tsetmc.py` این فهرست را منبعِ `instruments.paper_type` می‌سازد، پس اختیارها `paper_type=1` می‌گرفتند و `mstat_engine.classify` آن‌ها را `stock` می‌خواند. روی `market.db` ۲۰۲۶-۰۹-۱۹: ۱۹۰۸ اختیار، که ۱۴۶۱ تایشان `paper_type=1` داشتند (در نسخه‌های قدیمی‌تر `NULL` بودند و درست «other» می‌شدند).
- **اثرِ مشاهده‌شده:** اختیارها با حجمِ خردِ خود (۹۱ تا ~۴۶ هزار واحد) به سطرِ «سهام و حق تقدم»، تجمیعِ حجمِ سهام، و جدولِ الگوی ساعت می‌رسیدند؛ حجمشان بعد از گردکردن به «میلیارد سهم» `0.0` نشان داده می‌شد و گاردِ فاز ۱ با شکستِ «نامزدِ بی‌معامله نداریم» (۲۹ نماد) این آلودگی را لو داد. علت واقعی داده‌ی درستِ نمایش‌اشتباه بود، نه سهمِ بی‌معامله.
- **اصلاح (دو لایه):** ۱) `mstat_engine.classify` حالا پیش از paperType و از روی نام، اختیارها را جدا می‌کند (`is_option` با کلیدهای «اختيار»/«اختیار» — سوءاثرِ صفر: هیچ نامِ غیر-اختیاری در بازار این کلیدها ندارد). ۲) `fetch_paper_types` دیگر به اختیارها paperType اختصاص نمی‌دهد تا سینکِ بعدی `paper_type` آن‌ها را `NULL` نگه دارد (خود-ترمیمیِ بانک).
- **نتیجه:** تابلوی «سهام و حق تقدم» از ۲۳۴۴ به ۲۳۱۵ نماد اصلاح شد (۲۹ اختیارِ آلوده کنار رفت). گاردِ `dev/mstat_local_v975.py` **۱۴۰/۱۴۰ سبز** (پیش از این ۱۳۹).
- **فاز دوم — همان علامت، ریشهٔ متفاوت:** بعد از سینکِ تازه‌تر، همان گاردِ «نامزدِ بی‌معامله نداریم» یک‌بار دیگر شکست خورد، ولی این بار تقصیر اختیارها نبود — یک سهمِ واقعی و گران‌قیمت (سپامهر، ۴۸٬۶۲۲ ریال) با ۶۵ معامله و ۹٬۹۵۹ سهم حجم، چون حجم در یکای «میلیارد سهم» و با ۴ رقمِ اعشار نمایش داده می‌شد، `vol_b_shares = round(9959/1e9, 4) = 0.0` می‌شد؛ یعنی یک نمادِ کاملاً معامله‌شده «بی‌معامله» جلوه می‌کرد. ریشه، یکا + دقتِ نمایش بود، نه داده.
  - **اصلاح:** ۱) دقتِ `vol_b_shares` از ۴ به ۶ رقمِ اعشار (کفِ قابل‌نمایش = ۱۰۰۰ سهم؛ سرتیبِ حجم هم دیگر در ۰ قفل نمی‌شود). ۲) `mainwatch` تعدادِ معاملهٔ خام را در کلیدِ `trades` در اختیار می‌گذارد. ۳) گاردِ مذکور حالا `trades > 0` را می‌سنجد — تعریفِ واقعیِ «بی‌معامله» — و دیگر به مقدارِ گردشدهٔ نمایشی وابسته نیست.
  - **درسِ روش‌شناختی:** این دو باگِ هم‌شکل نشان می‌دهد که یک گاردِ خوب، نقص را لو می‌دهد ولی تشخیصِ «دادهٔ آلوده» یا «نمایشِ آلوده» نیازمندِ بررسیِ دادهٔ خام است؛ وگرنه اصلاحِ اشتباه (حذفِ سهمِ سالم به جای اصلاحِ نمایش) به‌جای رفعِ نقص، داده را با نقص تطبیق می‌دهد.
- **ارقامِ واقعی (تصویرِ لحظه‌ای از market.db — با هر سینک تغییر می‌کنند، نه بخشی از قرارداد):** ۹ سطرِ جدولِ خلاصه؛ عمق برای ~۳۷۰۰ نماد؛ ~۲۰۰۰ نماد در هیستوگرام؛ درصد خرید حقیقی+حقوقی = ۱۰۰٫۰؛ تعدادِ نامزدهای الگوی ساعت و اندازهٔ تابلو به وضعیتِ روزِ بازار بستگی دارد.
- **نکتهٔ عملیاتی:** سرورِ در حال اجرا کدِ قدیمی را در حافظه دارد؛ تا restartِ uvicorn خروجیِ زندهٔ API از این اصلاح بی‌خبر است (دادهٔ تابلو همزمان با اصلاح دوباره سینک شود تا `paper_type` هم درست شود).

## [v9.10.0] — 2026-09-11 — ارزش بازار تک‌منبع (TSETMC) + دروازه‌های ریسک + پنل تنظیمات v10

- **ارزش بازار: تک‌منبعِ حقیقت شد.** `_fts_market_ctx()` در `api/fundamental.py` دیگر هیچ‌گاه `قیمت × تعداد سهام` حساب نمیکند؛ مقدارِ رسمیِ تابلوی TSETMC (`qTotCap`) از ستونِ نگه‌داشتهٔ `market_watch.market_cap` خوانده میشود و در نبودش تنها منبعِ مجازِ جایگزین، تازه‌ترین `daily_prices.market_cap`ِ معتبر است. نبودِ داده = `None` (شکافِ داده، با پیامِ «ارزش بازار نامشخص») — هرگز صفرِ جعلی، چون صفر یعنی «زیرِ کف» و سهمِ سالم را بی‌دلیل حذف میکند. پروانسِ داده در payload هست: `market_cap_rials` / `market_cap_src` / `market_cap_asof` / `market_cap_stale` / `market_cap_error` (نسخهٔ کوتاهِ `mcap_*` هم در `metrics`).
- **واحدِ همت تصحیح شد:** `HEMMAT_RIAL = 10^13` ریال. تا پیش از این، آستانه‌هایِ واردشده در پنل (کفِ ارزش بازار و نقدشوندگی) در مقیاسِ اشتباه مقایسه میشدند و عملاً یا همیشه «رد» بودند یا همیشه «قبول».
- **دروازه‌های ریسک (`risk_gates`)** در چهار لایهٔ خارج از پنج محور: ۱) ماده ۱۴۱ (زیان انباشته > نصفِ سرمایه) با `m141_hit` ۲) کفِ ارزش بازار بر حسبِ همت ۳) نقدشوندگی = حداقلِ میانگین ارزش معاملات روزانه ۴) فیلترِ دستیِ صنایع Include/Exclude (نرمال‌سازی خطِ فارسی/عربی، هر دو ویرگول `,` و `،`، trim، و تطبیقِ زیررشته‌ای با نامِ بخشِ تابلو) + حفظِ حذفِ بیمه و نمادِ معلق. `m141_map` و `liq_map` یک‌بار برای کل بازار ساخته میشوند و به `evaluate_v10` تزریق می‌گردند — همان قراردادِ ضدِ N+1 که `fts_engine.scan_symbol` دارد؛ مسیرِ دسته‌ایِ واچ‌لیست هم ارزشِ بازار را از کوئریِ دسته‌ایِ واحد میخواند.
- **پنلِ تنظیمات کدال (CODAL v10):** کلیدهایِ تازهٔ `include_industries` / `exclude_industries` / `industry_mode` (چهار مقدارِ شناخته‌شده) و آستانه‌هایِ «حکمِ جزوه» `v10_*` که عمداً از کلیدهایِ اسکرینر جدا‌اند تا تغییرِ عددِ اسکرینر بی‌صدا چکِ ۱الف یا کفِ نسبتِ فروش÷ارزش را شل نکند؛ `v10_sales_to_mcap_min = 0.33`. اعتبارسنجیِ سمتِ سرور در `set_fts_config`: هر عددِ منفی مردود، کرانِ بازه‌ها (`watchlist_max 1..500`، `eps_years/v10_eps_years 1..12`، `suspended_max_stale_sessions 1..20`)، و خطا با نامِ همان فیلد برمیگردد تا پنل همان خانه را قرمز کند (نه نوشتنِ عددِ غلط روی دیسک). همهٔ کلیدها همیشه ارسال میشوند تا state کهنهٔ `fts_thresholds.json` نگردد.
- **رفتارِ رابط:** «ذخیره و اعمال» بی‌reload صفحه کار میکند — اعتبارسنجیِ محلی، ذخیره در localStorage، POST به `/api/fts/config`، پخشِ رویدادِ `fts-settings-applied`، و تازه‌سازیِ جدولِ اسکرینر + کارتِ بنیادیِ باز. «بازیابی پیش‌فرض» کلیدِ محلی را پاک میکند و همان را روی سرور مینویسد. کارتِ بنیادی منبعِ ارزش بازار را نشان میدهد (رسمی / کهنه / بدونِ داده). handlerهایِ سراسریِ `saveFtsConfig` / `loadFtsConfig` بازنویسی شدند و مارک‌آپِ `index.html` دست‌نخورده ماند (فقط cache-buster از `9.7.7`/`9.8.1` به `9.10.0` یکدست شد — گاردِ «همهٔ ارجاع‌ها یک نسخه» در `chart_api_check_v95.py` همین را می‌سنجد؛ نسخهٔ `v=3.0.57` کتابخانهٔ vendor عمداً دست‌نخورده).
- **سقفِ واچ‌لیست:** `watchlist_max` هم سمتِ سرور (`api/watchlist.py`، کران‌شده با سقفِ مطلقِ فروشگاه) و هم سمتِ کلاینت (`static/selection.js` با toast) اعمال میشود؛ افزودنِ نمادِ تازه وقتی لیست پر است رد میشود ولی ویرایشِ نمادِ موجود آزاد می‌ماند.
- **تستها:** سوئیتِ تازهٔ `dev/test_fts_market_cap.py` (۵۲ چک: تک‌منبعِ ارزش بازار، تبدیلِ همت، هر چهار دروازه، پروانس و staleness) و `dev/test_fts_settings_ui.js` (۴۵ چک روی VMِ Node با DOM ساختگی: ذخیرهٔ نامعتبر بدونِ POST، ذخیرهٔ معتبر با payload درست‌تایپ، خطایِ سرورِ پنهان‌نشده، بازیابیِ پیش‌فرض، پارسِ اعدادِ فارسی و ویرگولِ فارسی، کران‌ها، و ساختِ idempotentِ کنترل‌ها). هر دو در `run_all_tests.py` ثبت شدند (۱۶ سوئیت — ۱۴ پایتون + ۲ Node، همه سبز) و fixture پیش از سوئیت‌های Node دوباره ساخته میشود تا clone تازه بدونِ فایلِ generated سبز بماند. گاردِ `dev/mstat_local_v975.py` از «شمردنِ placeholderهایِ موقعیتی» به «بررسیِ نامِ ستون‌ها» ارتقا یافت (۳۲ ستونِ `market_watch`) و ۱۴۰/۱۴۰ است.



## [v9.9.0] — 2026-09-11 — موتور بنیادی FTS v10 (پنج لایهٔ واقعی + سالانه‌سازی پویا)

- **لایهٔ ۱ دو شاهدی شد:** ۱الف رشد ریالی (تجمیعیِ دوره ÷ همان دورهٔ سال قبل، آستانه ۶۰٪) و ۱ب رشد فیزیکی که برای پاس‌شدنِ لایه الزامی است. قاعدهٔ جزوه رعایت شد: مخرج هرگز «ماه قبل» نیست. مخرج اول از ستون رسمیِ «مقایسه با دورهٔ مشابه سال قبل» و در نبودش از ردیف (سال−۱، همان ماه) خوانده میشود؛ نبودِ هر دو ⇒ `data_gap` با متنِ راه‌حل، نه «رد». نبودِ تناژ/تعداد فیزیکی با `price_effect_decomposition` (کاهشِ نسبتِ حاشیه) و `margin_breadth` (پهنای رشد سبد) راستی‌آزمایی میشود و حالتش در `basis` و `confidence` می‌ماند.
- **لایهٔ ۲ با نردبانِ شفافِ شاهد:** سابقهٔ EPS سه سالِ متوالی از صورت‌های سال‌پایان **و** میاندوره ساخته میشود: ۱) سال‌پایانِ حسابرسی‌شدهٔ غیرتلفیقی ۲) سال‌پایانِ غیرتلفیقیِ حسابرسی‌نشده ۳) سال‌پایانِ تلفیقی ۴) میاندوره × ۱۲÷م. هر تنزل با `evidence_tier` و پرچم‌های `consolidated_used` / `relaxed_evidence` / `low_quality_track` اعلام میشود (قاعدهٔ سختِ v8 روی این DB فقط ۱۰۸ نماد را داوری میکرد؛ با نردبان ۶۸۸ نماد). اگر تنها دلیلِ «صعودی نبودن» سالِ جاریِ فقط‑۳ماهه باشد، نتیجه `soft_gap` می‌خورد: عدد نمایش داده میشود ولی «ردِ قطعی» خوانده نمیشود.
- **سالانه‌سازی پویا در لایهٔ ۴:** «م» از خودِ گزارش ماهانه خوانده میشود (۱ تا ۱۲) و فروش سالانه = تجمیعی × (۱۲÷م)؛ نتیجه با گیتِ `fts_engine.annualized_sales` reconciled میشود و در صورت واگرایی به فروش سالانهٔ کدال تنزل می‌کند (با برچسب، نه بی‌صدا). آستانهٔ پتانسیل سود ناخالص ÷ ارزش بازار ۳۳٪ و آستانهٔ فروش÷ارزش ۱× هر دو از تنظیمات پنل خوانده میشوند.
- **`GET /api/sync/codal/fts-coverage`:** پوششِ دادهٔ هر لایه روی کل بازار در ~۰.۸ ثانیه (مرورِ تجمعی، بدون ارزیابیِ تک‌تکِ نمادها). خروجیِ امروز: ۱الف ۸۲.۴٪ (۶۰۱/۷۲۹) · ۱ب ۰٪ (هیچ ستون فیزیکی در `monthly_sales` نیست) · ۳ حاشیه ۵۹.۴٪ · ۲ سخت ۱۰.۶٪ ← ۲ پشتیبان ۶۷.۸٪. نکتهٔ مهم: تمامِ مخرج‌های ۱الف از ردیف «همان ماهِ سال قبل» می‌آید و ستونِ رسمیِ کدال (`ytd_revenue_prev`) صفر رکورد دارد.
- **حذف خودکار و گاردها:** بیمه، تعلیق، و «قیمت‌گذاری دستوری» در حالت `Exclude_Mandatory_Pricing` از غربالگری بیرون می‌مانند؛ حالت `Rank_Only` فقط رتبه‌بندی میکند. نمادهای دارای پسوند عددی و قراردادها به نماد اصلی ارجاع داده میشوند (رفتارِ حفظ‌شده از v8).
- **رابط «تحلیل کامل» (`static/fundamental_ui.js`):** بجِ نسخهٔ موتور کنار عنوان، خطِ «آستانه‌های فعال» از `methodology.thresholds`، ششِ سلولِ خلاصه (۱الف/۱ب/۲/۳/۴+پتانسیل/۵) که «داده نیست» را خاکستری و «مردود» را قرمز نشان میدهد، بنر «شکافِ داده» با `why` + `fix` برای هر لایه، و نوارِ زیرشاخص‌ها (1a/1b/2a/2b/3/4a/4b/5) با مقدار/آستانه/جزئیات داخل پنلِ فرمول‑و‑منبع. جدولِ تاریخچهٔ صورت‌های مالی دست‌نخورده ماند.
- **قاعدهٔ «سطرِ ناقص حذف نمیشود» در جدول بنیادی:** اگر لایهٔ ۲ به‌جای ۳ دوره فقط ۲ دوره (یا ۱) داشته باشد، سطر از جدول بیرون نمی‌رود — مقادیرِ موجود درج میشوند و جایِ هر دورهٔ ناموجود علامت «-» می‌نشیند؛ عنوان و همهٔ سلول‌های سطر قرمز میشوند و «تنها ۲ دوره موجود است» ذکر میگردد. `eps_series` حالا همیشه به بلندای `years_required` است (دورهٔ غایب = `None`) و `period_slots` برچسبِ سال‌ها را نگه میدارد؛ `partial` / `available_periods` / `periods_missing` و `details["۲"].period_row` (با `markdown` آماده) به payload اضافه شدند. دقتِ داوری تغییر نکرد: `data_gap` و `pass=False` سرِ جایشان می‌مانند (۳۸ نمادِ بازار در این حالت‌اند و هیچ‌کدام امتیازِ جعلی نگرفت).
- **رفعِ باگِ خروجی (CSV/XLSX/DOCX/PDF):** `GET /api/export?view=fundamental&symbol=…` روی هر نمادِ فارسی با `'latin-1' codec can't encode characters` می‌مرد، چون نامِ فایل در `Content-Disposition` خام نوشته میشد. `_disposition()` اضافه شد: `filename=` نسخهٔ ASCII و `filename*=` نسخهٔ RFC 5987 — ستونِ «EPS: - | 590 | 990» هم در همان سطرِ شاخص ۲ می‌آید.
- **قراردادِ خروجی:** `passes` دو کلیدِ جدید `1a_monetary_growth` و `1b_volume_growth` اضافه کرد (کلیدهای پنج‌محورهٔ قدیمی برای مصرف‌کننده‌های موجود دست‌نخوردهاند). `details[*].subchecks` و `data_gaps` به payload اضافه شدند؛ `fiscal_years` رشته است (عددِ صحیح باعث خطای JSON نمیشود).
- **راستی‌آزمایی:** `python dev/run_all_tests.py` = ۱۴/۱۴ سوئیت سبز · `dev/test_fts_v10_ladder.py` ۴۳/۴۳ (نردبانِ شاهد + سطرِ ناقص + هدرِ خروجی) · `dev/test_fts_v10_ui.js` ۱۷/۱۷ رندرِ هدلس با DOM ساختگی (سه سناریو: کامل / ۲-دوره / بدونِ داده) · `dev/test_fts_isolation.py` ۲۳/۲۳ · `dev/fts_m141_parity_v97.py` ۲۴/۲۴ (پاریتی `fts_engine` که عمداً تغییر نکرد) · `dev/test_calendar_v92.py` ۱۲/۱۲ · `node --check` روی UI. اسکنِ زندهٔ ۷۹۳ نماد: ۳۸ سطرِ ناقص با «-» و برچسبِ قرمز (احيا `- ← 590 ← 990`، تابان `- ← - ← 8,267`) و هیچ تغییرِ امتیازی ثبت نشد؛ کارت‌های زنده: شپنا ۳ امتیاز (۱الف +۱۵۱٪، ۱ب +۵۸.۹٪، EPS صعودی)، فولاد ۲ امتیاز با `soft_gap` و سه شکافِ گزارش‌شده.
- **بدهیِ شناخته‌شده (بدون تغییر در این نسخه):** `import app` روی پایتون ۳.۱۴ این محیط می‌شکند چون `httpx` نسخهٔ نصب‌شده `import cgi` میکند (ماژولِ حذف‌شده). موتور و API مستقیماً قابل اجرا و تست بودند؛ برای اجرای سرور، ارتقاء `httpx` (یا پایتون ۳.۱۲) لازم است.

## [v9.8.1] — 2026-09-10 — پایپلاین کدال FTS + چرخش IP روی 403/Timeout + پنجرهٔ بازار تایملاین



- **شاخص ۴ — فرمول دستور کار:** `annualized_sales` حالا اول «فروش ۳ ماههٔ متوالی × ۴» را میسازد (ماههای پرشدار/بانک ⇒ تنزل به YTD×12÷ماه قبلی). همان منطق در `bulk_scan` هم اعمال شد تا پاریتی `scan_symbol ⇄ bulk_scan` (گارد ۱۳ `confidence_engine_v973`) نشکند. روی دادهٔ زندهٔ فولاد: `basis="فروش ۳ ماهه (03–05/1405) × ۴"`
- **شاخص ۲ — سود خالص ۳ ساله:** `eps_trend_3y` علاوه بر EPS، `net_profit_series` همان پنجرهٔ ۳ ساله را برمیگرداند («ثبت سود خالص و EPS برای ۳ سال اخیر»)
- **شاخص ۵ — برچسب صنعت برتر FTS:** `sector_filter` فیلد `fts_top_industry` اضافه کرد — هر صنعتی که در فهرستهای قیمتگذاری FTS شناخته شده (فلزات/سیمان/پتروشیمی/دارو/غذا/…). برچسب ≠ قبول: دارو برچسب میخورد ولی رد میشود
- **چرخش IP روی 403:** `fetch_page` پیشتر 403 را بیصدا به `raise_for_status` میانداخت و کل صفحه دور ریخته میشد؛ حالا 403 دقیقاً همان مسیر 429 را میرود: v2ray → ADB → backoff نمایی
- **چرخش IP روی Timeout/قطع نشست:** خطای شبکهٔ متوالی (تترینگ/مودم افتاده) حالا `rotate_ip_via_adb` را صدا میزند و با IP تازه retry میکند؛ پیشتر فقط sleep جیتری میخورد. `dev/codal_fts_updater.py` هم در `api_get` روی قطع نشست چرخش فوری + `_wait_net_back` (پایش echo تا ۱۲۰s تا برقراری اینترنت) را اجرا میکند و 403 را هم مثل 429 میشمارد
- **رفع باگ تایملاین درونروزی (نقاط خارج از بازار):** دو ردیف آلوده در `mstat_snap` واقعی پیدا شد (18:00 ردیف تستی ذخیرهشده 04:21 و 20:59 ذخیرهشده 02:16 شب) که خطوط مورب/افتِ دروغین به صفر میساختند:
  - `mstat_engine`: ثابتهای `SESSION_OPEN_HM=85500`/`SESSION_CLOSE_HM=130005` + `in_trading_session()`؛ `save_mstat_snapshot` فقط درون پنجرهٔ بازار مینویسد (`when` تزریقی برای تست)؛ `_points` با `h_even BETWEEN` فقط نقاط رسمی را برمیگرداند؛ `timeline` پنجره را در `session_open/close` اعلام میکند
  - `test_tsetmc`: هر دو مسیر ذخیرهٔ اسنپشات (main و `_save_market_snapshot`) فقط در ۰۹:۰۰–۱۲:۳۵ مینویسند؛ شرط `closed` قبلی `wd<3` بعدازظهرِ شنبه/یکشنبه (روزهای کاری ایران! weekday=5/6) را همگامسازی فعال میگذاشت — به `wd in (3,4)` اصلاح شد
  - دو ردیف آلودهٔ تاریخی از market.db حذف شد؛ تست زنده: timeline فقط نقطهٔ 12:58 را میدهد، `ready=False`، بدون لیبل خارج از پنجره
- **تستها:** سوئیت جدید `dev/fts_pipeline_v981.py` (۴۸ چک: ۵ شاخص روی DB نمونه با اعداد حسابشده، فالبک ADB با ماک 403/429/Timeout، پنجرهٔ بازار)؛ `mstat_local_v975` برای گارد پنجره `when` تزریقی گرفت و به ۱۳۳ چک رسید. `run_all_tests.py` حالا ۱۳ سوئیت دارد — **همه سبز**


## [v9.7.4] — 2026-09-08 — Phase 2: رویکرد «هشدار منعطف» در موتور تایید سهگانه

- **وتوی سخت حذف شد:** `VETOED` و کلید `vetoed` از `confidence_engine.triple()` بیرون رفت؛ جایش `WATCH` آمد. دلیلش داده بود، نه سلیقه: صفحهٔ ۲ متدولوژی FTS شکارچیِ سهمهای برگشتیِ ماده ۱۴۱ است و وتوی سخت دقیقاً همانها را از دید کاربر پنهان میکرد
- **حالت چهارم `warn` به `_pillar` اضافه شد** (`pass|warn|fail|nodata`) با `PILLAR_STATES` + `ValueError` روی وضعیت ناشناخته؛ `pass` عمداً فقط `state=='pass'` است تا warn هرگز در `conf_count` شمارش نشود
- **دروازهٔ نرم هفتگی:** MA52 هفتگی (ساختهشده از کندل روزانه با کلید هفتهٔ ایزو) + RSI7 هفتگی + MA100 روزانه. نزولی/خنثی ⇒ `warn` با متن «⚠️ روند هفتگی ضعیف» — نه حذف. بیداده ⇒ `weak=None` و **بدون** هشدار (۵۲ هفته ≈ ۲۶۰ نشست؛ ۱۷۸۴ نماد از ۲۵۲۰ آن را ندارند)
- روی دادهٔ زندهٔ market.db: از ۷۳۶ نمادِ قابلارزیابی، ۱۴۲ «روند هفتگی ضعیف» و ۵۸۹ صعودی — همه در لیست میمانند
- **ستون بنیادی:** «حذف خودکار FTS (ماده ۱۴۱/زیانده)» از `fail` به `warn` تبدیل شد و متنش عیناً به `conf_reasons` میرود؛ نمادِ EXCLUDED حالا `PROBABLE` میخورد، نه وتو
- **الگوی ساعت** در تابلوخوانی: `(آخرین − پایانی)/پایانی ≥ +۱٪` + حجم مشکوک ≥ ۳× — فقط هشدار و گزارش، عمداً به `checks` اضافه نشد تا امتیاز سهگانهٔ v9.7.3 دستنخورده بماند
- **ستاپهای روزانه** (`breakout/pullback/fibonacci/CHoCH/bearish_div`) و **مراجع حد ضرر** (`ma14/rising_low/swing_stop` = ۵٪ زیر کف ماژور) در `detail` گزارش میشوند — زیرساخت Phase 3 (کارتابل پورتفوی)
- باگِ واقعیِ یافتشده حین تست: تشخیص کف ماژور با «`<=` مینیمم پنجره» روی سریِ صاف (۱۰۰،۱۰۰،…) هر ردیف را کف میشمرد ⇒ کفِ جعلیِ جلسهٔ اول؛ با شرط «باید واقعاً پایینتر باشد» اصلاح شد
- UI: `selection.js` — badge های `WATCH` (amber) و `ST.warn` (⚠) + نمایش `conf_reasons` در tooltip؛ `app.py` — داکس قرارداد جدید ماتریس
- تستها: سوئیت جدید `dev/soft_warnings_v974.py` (۷۰ چک، شامل گاردهای دیتای زنده) + `confidence_engine_v973.py` از ۱۰۲ به ۱۰۷ چک + `watchlist_matrix_v973.py` از ۴۵ به ۴۷ چک (واژگان عمومی وضعیت/verdict قفل شد)
- cache-buster: `v=9.7.2` → `v=9.7.4` (۱۶ ارجاع در `static/index.html`) + هماهنگسازی گاردهای `chart_api_check_v95.py` و `serve_check_v95.py`

## [v9.7.2] — 2026-09-07 — بدهیهای کوچک v9.7.1 + دورهٔ اندیکاتورها + تابآوری ADB

- **همگامسازی `rv.logScale`:** در `btsApplySettings` از نام واقعی محور (`btsAxis`) مشتق میشود؛ پیشتر بعد از reload محور لگاریتمی بود ولی پرچم `false` و همان مقدار نادرست در `tech_<sym>` ذخیره میشد
- **پاکسازی CSS:** ۹ کلاس یتیم حذف شد (`.tv-pop-bar/.tv-pop-btns/.tv-pop-title/.tv5-badge/.tv5-danger/.tv5-sym/.tv5-sym-name/.tv5-tfs/.tv5-tools`)؛ قوانین زندهٔ همخانواده حفظ و در گارد قفل شدند
- **دورهٔ اندیکاتور:** RSI هفتگی ۷ / روزانه ۱۴ (ماهانه دستنخورده)، EMA ‏20/50/200، BOLL ‏20/2 — با `RTV_IND_DEFAULTS` + `rvIndParams`؛ `rvIndSyncParams` بعد از هر `rvLoad` با `overrideIndicator` بازاعمال میکند
- **سلامت اورلی:** تست زنده (Playwright) — اورلی کاربر در رفتوبرگشت D→W→D بدون تکرار و بدون مفقودی
- **ADB:** حلقهٔ Retry + Re-connect برای `offline`/`unauthorized` (با `kill-server`/`start-server`)، قفل غیرهمبلوک ضد فریز ترد، و **تضمین بازگشت Wi-Fi در `finally`** (پیشتر استثنا میانِ توگل اینترنت میزبان را خاموش نگه میداشت)
- **تستها:** سوئیت جدید `dev/adb_resilience_v972.py` (۲۶ چک) به `run_all_tests.py` اضافه شد؛ گارد `chart_api_check_v95.py` از ۱۳۹ به ۱۵۶ چک رسید (بند ۱۸)
- **cache-buster:** `v=9.7.1` → `v=9.7.2` (۱۶ ارجاع) + همگامسازی گاردهای نسخه
- **MCP:** سرورهای `memory`، `sequential-thinking` و `sqlite` به کانفیگ کلاین اضافه شدند (سرور SQLite رسمی روی npm وجود ندارد؛ از `uvx mcp-server-sqlite` با پین `mcp[cli]<2` استفاده شد — بدون پین بهدلیل حذف `Server.list_resources` در `mcp` ۲.x کرش میکند)

## [v7.4.5] — 2026-09-05 — FTS دقیقتر طبق جزوه + ترمیم کیفیت داده

- **شاخص ۴ = «فروش به ارزش بازار» (P/S)** مطابق جزوه (قبلاً ارزشبازار بهعنوان ۴ بود)؛ ارزشبازار و پتانسیل سود → تکمیلی
- **شاخص ۵:** پاس = مردود نبودن صنعت؛ سهمبازار فقط اگر آستانه > 0 تنظیم شود
- **`--repair` کدال:** ترمیم ردیفهای MS/FS موجود ولی خالی (re-scrape با پارسر جدید) — ۳۷ MS بانک/خدماتی ترمیم شد
- **eps_trend:** ۷۳۶ نماد EPS سالانه دارد (۷۸۲ None = فقط فصلی/بدون گزارش — محدودیت داده کدال است نه باگ)
- **اسکن:** STRONG=2 · WATCH=63 · P/S پاس=183 (از potential=1)

## [v7.4.4] — 2026-09-05 — FTS جزوه: YoY واقعی + پنل پیششرط + بانک وبملت

- **رشد فروش YoY (جزوه):** رشد = دورهٔ اخیر ÷ همدورهٔ سال قبل (۱۴۰۵÷۱۴۰۴) — CTE جدید PrevYearFS؛ باگ فصلبهفصل (LEAD) رفع شد
- **پنل پیششرطهای ۵ شاخص** در تنظیمات کدال: growth_min/torom(streak/margin/ps/...) + تورم سالانه ۵۸٪ — ذخیره → جدول بنیادی فوری محاسبه مجدد
- **گزارش ماهانه ۱۴۰۵:** ستونهای «مقایسه با دورهٔ مشابه سال قبل» استخراج → monthly_revenue_prev/ytd_revenue_prev (migrate خودکار)
- **بانک/خدمات (وبملت):** جمع ردیفهای درآمد (تسهیلات+سپرده+اوراق+سرمایهگذاری+کارمزد) — باگ «جمع» نبود، سطر یادداشت برداشته میشد رفع شد
- **حاشیه ناخالص:** پاکسازی ۱۴۱۸ ردیف آلوده (gp≥rev)؛ مالی/کارگزاری → NULL؛ regex درآمد سفت شد
- **ADB:** چرخش IP واقعی (تست زنده ✓) + خاموشکردن Wi-Fi حین روتیشن + تأیید تغییر IP؛ run_discovery.sh → فید سراسری
- **build_exe:** fts_engine.py + fts_thresholds.json باندل میشوند (قبلاً جا میافتادند)

## [v7.2.0] — 2026-09-02 — Confluence Scoring + Patterns API + Adjustment Parity

- **Confluence Scoring (`confluence.py`):** امتیاز 0-100 قطعی = breakout_quality(40) + sr_confluence(30) + regime_alignment(PTM, 30)؛ thresholds ≥70 confirmed / 40-69 watch / <40 reject؛ FIX scale-invariant dist (شکست خرد در رنج ATR کوچک دیگر «۱ATR» حساب نمیشود)
- **`GET /api/patterns/{symbol}`:** مختصات [timestamp, value] در فضای تعدیلشده → S/R dashed + trendLine (۲ pivot آخر) + breakout zone rect؛ TTL cache؛ تست فولاد: 9 overlay بدون drift در zoom/pan
- **FIX رندر rect:** createPointFigures با `type:'rect'` بومی + styles flat (قبلاً تودرتو → رندر نمیشد)
- **Parity تعدیل:** back-adjustment factor=∏ratio (پاریتهٔ نهایتنگر) — بنچمارک خساپا/وبملت/فولاد: هیچ پرش مصنوعی؛ حالتهای raw/adjusted/adjustEvents
- **Audit ریاضی:** RSI(14) Wilder=70.46 دقیق · MACD/Ichimoku/Fib institutional · 11/11 قوانین atomic pass
- **Vault closure:** 00_Technical_MOC production-ready + operations/closed-epics/technical-engine-finalized.md — گراف 37 گره/162 یال/0 شکسته/0 یتیم

## [v7.1.0] — 2026-09-02 — Chart Engine Stabilization (Pure Mechanical)

- **Scope:** فقط پایدارسازی بوم رسم دستی؛ هیچ تشخیص الگو/قانون الگوریتمی اضافه نشد (سختگیری مأموریت)
- **Vendor:** `static/vendor/klinecharts.min.js` (KLineChart v10.0.3، آفلاین، md5 = کپی ریشه) — index.html از vendor لود میکند
- **Canvas Isolation:** همهٔ رسمها native KLineChart — هیچ اسکریپت canvas legacy برای ردیابی موس باقی نیست
- **Theme tokens:** dark `#1e222d`/`#131722` (RV_THEME + rvApplyTheme)، شمع سبز `#26A69A`/قرمز `#EF5350`، grid `#2a2e39`/`#E0E3EB`
- **Timeline گسسته:** `xAxis.createTicks` سفارشی (جلالی، فقط کندلهای واقعی) — gap تعطیلات/آخر هفته کشش نمیدهد
- **Data adapter:** `{timestamp: epoch-s, open, high, low, close, volume}` + تعدیل (factors) در rvToKLine
- **سوئیچ نماد بدون leak:** `removeOverlay()` + dataLoader یکبار (guard) + `resetData` — تست: خساپا→فملی، 0 ghost overlay، instance تک
- **مگنیت:** `crosshair.mode='strong_magnet'` — نقطهٔ رسم قفل به High/Low/Close (تأیید در بایتکد vendor)
- **حذف:** Delete/Backspace روی overlay انتخابی (`getClickOverlayInfo`) + Trash = پاک کردن همه
- **QA خودکار:** رسم segment+fibo → zoom-out 50% → pan 260 کندل → zoom-in → **drift = صفر** (نقاط دقیق) ✓ · Vision: بدون ghost/artifact ✓

## [v7.0.0] — 2026-09-01 — Tiered Memory & Autonomous Orchestration

- **L1 Fast Memory (`tools/mnemosyne.py`):** SQLite `kv_store` (session-flags/active-tasks)، `turn_counter` (5-Turn Protocol — هر ۵ ترن → `due=True` → بازبینی `00_SYSTEM_MANIFEST.md`)، `scope_locks` (write-locks برای چندworking؛ acquire/release/held با heartbeat)
- **L2 Long-Term (`00_SYSTEM_MANIFEST.md` در ریشهٔ vault):** Environment (DB/ports/proxies/ADB) + Crons + Skills/Directives + Model Routing + State Telemetry
- **Pre-Execution Hooks (SCHEMA.md):** backend/db/scraping → bors-agent + py_compile + fail-fast؛ UI/CSS → bors-agent + Visual QA (screenshot+vision+DOM)
- **Early Context Compaction:** سنتز bullet-summary در ~۵۰٪ context → push deltas به Manifest → prune
- **L2 Retrieval (`tools/vault_search.py`):** FTS5 با snippet+path+line (ibندکس 777 خط/18 فایل) — جایگزین خواندن کامل فایلها
- **تستها:** turn=1,2 ✓ · kv-set/get ✓ · lock acquire/held/release ✓ · search «نرمالسازی» → 3 hits با path:line ✓

## [v6.1.0] — 2026-09-01 — Screener Validation & API/UI Binding

### Task 1 — Screener Rerun (validation after dedupe)
- 5-index در CTE ها روی دیتابیس تمیز (8,007 FS): **1008 نماد امتیازدهی شد، صفر error تقسیمصفر** (dedupe سالم)
- **TOP 5:**
  1. **خکرمان** score 6 — رشد 44587%، حاشیه 38.8%، P/S 0.44
  2. **فن آوا** score 6 — رشد 1200%، حاشیه 100%، P/S 1.70
  3. **ماديرا** score 6 — رشد 68%، حاشیه 40.6%، P/S 0.74
  4. **سجام** score 5 — رشد 148%، حاشیه 58.1%
  5. **غچين** score 5 — رشد 58%، حاشیه 14.2%
- توزیع score: {0:234, 1:284, 2:185, 3:207, 4:59, 5:36, 6:3}

### Task 2 — API Endpoints (`app.py`)
- `POST /api/sync/update-existing?limit=N` — اجرای واقعی `--update-symbols N` در **subprocess پسزمینه** (Popen — غیرمسدود)
- `POST /api/sync/discover?limit=N` — اجرای `--discover --limit N`
- `GET /api/sync/pipeline` — poll وضعیت job (running/done)
- خروجی JSON: `{status, updated, delta, detail, log_tail}`

### Task 3 — Frontend Binding (`index.html` + `app.js`)
- دکمههای تب کدال → `syncPipeline('update'/'discover', this)`:
  - **Loading state:** disable + `opacity:0.6` + label «⏳ در حال بهروزرسانی...»
  - **Success/Error Toast** (جدید `rvToastSv`): «✓ آپدیت موفق: 5 نماد پردازش شد (3 جدید)»
  - Poll 5s بعد از شروع

### Task 4 — Visual QA (Protocol)
- DOM: `immediateDisabled:true` / `immediateText:"⏳ در حال بهروزرسانی..."` / `opacity:0.6` ✓
- Vision dark: «در حال بهروزرسانی...» واضح، بدون overlap، dark-mode هماهنگ ✓

## [v6.0.0] — 2026-09-01 — Autonomous Codal Pipeline (5-Index System Finale)

### Task 1 — Smart Discovery (tested)
- **یافتهها از پروبهای مستقیم Codal Search API:**
  - `Title` روی search API **فیلتر نمیشود** (نادیده گرفته میشود) — فیلترِ عنوان باید سمت کلاینت (`_positive_title`) باشد.
  - `LetterType=8` و `LetterCode=29` → **0 نتیجه** (top-selector بیش از حد) — **بهینه: `LetterType=-1`** (baseline) برای Category=1/3.
  - `FromDate` (شمسی با `/`) **دقیقاً کار میکند**: `FromDate=1405/04/01` → فقط ۵ گزارش از ۱۶۴ برگشت.
  - جستجوی اساسی: `Audited=true + NotAudited=true + Mains=true + Category=1/3 + LetterType=-1` — افراط در «فقط اصل» موجب حذف است.

### Task 2 — Dynamic Updater (در محصول)
- **`update_symbol_incremental(sym, sess)`** در `codal_fetcher.py`:
  1. `MAX(publish_date)` از DB → نرمالسازی ارقام فارسی → `FromDate`
  2. فقط اسناد پس از آن: `Category=1` + `Category=3`
  3. برای نماد بدون FS/MS → `_process_symbol` کامل
  4. بعد از شستشو: **`dedupe_symbol(sym)`** — فقط آخرین tracing_no در هر period_end
- **`--update-symbols N`** CLI — update افزایشی N نماد موجود.
- **باگ ماژول کشفشده:** ارقام **فارسی** در DB (`۱۴۰۵/۰۶/۰۴`) → `HTTP 400` از API — نرمالساز `translate("۰۱۲۳۴۵۶۷۸۹...")` اضافه شد.
- **بزرگترین فایده:** PK جدول `tracing_no` بود → اصلاحیهٔ جدید = **row جدید**؛ dedupe ۴۸۹۲ ردیف قدیمی حذف کرد (FS 12,899 → **8,007**، dup 0).

### Task 3 — Amendments (simulated + verified)
- شبیهسازی correction: `net_profit` 15791 → 17685 (+15%) — وارد tracing_no جدید
- dedupe2 → **۱ حذف، winner = آخرین (اصلاحیه)** ✓

### Task 4 — Cross-Verification (internal + external)
- **Internal sanity** (همه نمادها): `net_profit ≤ assets×1.05` + `margin ∈ [-0.5, 1.5]` — **همه پاس**
- **External (TSETMC public):** خساپا → TSETMC eps=-154 (ما -58) — **هر دو زیانده**؛ رمپنا → TSETMC eps=7327 (ما 365 بر ۳ماهه) — **هر دو سودده**، نسبت منطقی. **مقایسهٔ علامت/جهت — هماهنگ شد** (ارقام عددی natural بهخاطر دورهٔ ۳ماهه vs پیشبینی سالانه)

### Verification
- Dedupe: 1013 نماد / **0 dup periods** / **_FS rows 8,007** / dup MS فقط ۷ (غیرحساس)
- Sanity spot: ۱۰۰٪ پاس (حتی خساپا -7.4% در محدودهٔ مجاز)

## [v5.0.0] — 2026-08-31 — UI Nuke & Rebuild (Unified CSS Grid)

### Phase 1 — Wipe
- **حذف کامل** HTML های آشفتهٔ تب تکنیکال: `#rvDrawFloatBar` (پیل شناور)، `colorPickerMenu`، rail/DrawingToolRail قبلی، `rvTopbar` سهبخشی قدیمی، `rvBottombar`، منوهای شناور (rvChartSettingsMenu/rvPriceScaleMenu/rvIndPanel) + CSS های اسپاگتی (±۵KB)

### Phase 2 — Unified CSS Grid
- ساختار strict:
  - **Header (Top):** نماد + Badge + تایمفریمها (1D/1W/1M فعال UI) + Group یکپارچه Settings/Lock/Trash
  - **Sidebar (Left):** `#rail` — یک **ستون عمودی** ۳۸px از ۱۷ ابزار مقسم به separators (Cursor/Lines/Shapes/Annotations/Zoom/Magnet/Stay)
  - **Main (Center):** `#rvChartHead` (legend OHLC) + `#rvChartBox` (KLineChart)
- `display: grid; grid-template-rows: auto 1fr` + `grid-template-columns: 38px 1fr` — **هیچ absolute برای ساختار بعد**

### Phase 3 — Native Binding (verified)
- همهٔ ۱۷ دکمه → `rvSetTool(data-name)` → `rv.chart.createOverlay({name})`:
  - segment / straightLine / rayLine / horizontalStraightLine / verticalStraightLine — native
  - fibonacciLine / priceChannelLine / parallelStraightLine — native
  - rect / ellipse / triangle / arrow — custom `registerOverlay` (v10)
  - simpleAnnotation / simpleTag / brush — native
- تست E2E: کلیک هر ۶ نمونه → `rv.tool` برابر؛ `createOverlay` سالم (16 overlays)

### Phase 4 — Visual QA (Protocol)
- **Vision dark:** «unified application — header/sidebar/chart؛ SVGs clearly visible (strong contrast)؛ ZERO duplicate bars/broken layout» ✓ — فقط باقیماندهها sidebar اپ (خارج از techView) است
- DOM: `floatBarExists:false` · `pillExists:false` · shell/header/sidebar/main ✓

## [v4.0.0] — 2026-08-31 — Ultimate Hybrid TradingView Architecture

### UI Sourcing & Extraction (OpenCharts)
- **منبع:** `dylanpersonguy/OpenCharts` (GitHub, «Open Source TradingView Alternative», 58★) — clone و استخراج شد:
  - `DrawingToolRail.tsx` → الگوی کامل rail: **drag grip بالای rail + گروهها با flyout `left-full` + Hide (EyeOff)**
  - `global.css` → پالت dark (احساس E8 Markets)، `bg-card/90 backdrop-blur` glass
- **آیکونها:** paths واقعی **Lucide** (از `lucide-static@0.447.0` استخراج: MousePointer2, TrendingUp, MoveUpRight, Spline, Minus, MoveVertical, Equal, Layers, Layers3, Square, Circle, Triangle, Arrow*, Ruler, Type, PenTool, GripVertical, EyeOff) — نه آیکون از خود برساخته

### Hybrid Binding (KLineChart native)
- rail جدید `#rail` با **۵ گروه flyout + ۵ utility** — همهٔ دکمهها به **native API های KLineChart** بایند شدند:
  - Lines: trendline→`segment`، ray→`rayLine`، extended→`straightLine`، H/V→`horizontalStraightLine`/`verticalStraightLine`، channel→`parallelStraightLine`
  - **Fib:** `fibonacciLine` + `priceChannelLine` (Fib Extension)
  - **Shapes:** **`rect` (custom رسمی!)** + ellipse + triangle + arrow → با **`registerOverlay` + `createPointFigures`** ثبت شدند (KLineChart v10 API — ۲ نقطه)
  - Trade: `priceLine` (Long Position) + `simpleAnnotation` (Measure) · Text: `simpleAnnotation`/`simpleTag`
  - Utilities: Zoom In/Out (`zoomAtCoordinate(1.05/0.95)`)، Magnet، Stay، LockAll، Remove، ObjectTree، Hide
- **تمام ابزارها native — دیگر فقط خط نیستند؛ rect/ellipse/triangle/arrow واقعاً ثبت و رسم میشوند**

### باگ Dark Mode SVGs — رفع
- `.rail btn`/`.rail-flyout` با `color: #d1d4dc` (light در dark) + `body[data-theme=dark]` rules + fallback `.rail svg { stroke: currentColor }` — **آیکونها دیگر در پسزمینهٔ تیره محو نمیشوند** (تأیید vision: "light gray/white against dark navy — strong contrast")

### Visual QA (Protocol)
- screenshot dark + vision: «SVGs clearly visible، clean vertical rail، groups/separators، no overlap — professional like TradingView» ✓
- DOM: rail 32 SVG / 5 groups / 5 flyouts؛ `rect` custom: `getSupportedOverlays()` شامل + `createOverlay → rectFound:true`؛ flyout open ✓

## [v3.8.0] — 2026-08-31 — Fix کلیک ابزارها + Clone TV (نهایتنگر/رهاورد)

### باگ بحرانی: کلیک روی ابزارها کار نمیکرد
- **ریشه:** همهٔ دکمههای گروه فقط `rvToolMenu()` (بازکردن منو) فراخوانی میکردند — هیچ ابزار فعال نمیشد (`rv.tool` به null میماند).
- **رفع — ساختار TV دو-بخشی (mirror نهایتنگر/رهاورد):**
  - کلیک روی **main** دکمه → `rvSetTool(...)` → **ابزار بلافاصله فعال** (isDrawing:true)
  - کلیک روی **▾** (`tv-arrow`) → `rvToolMenu()` → منوی گروه باز
  - `.tv-tool { position:relative }` + `.tv-arrow` (absolute bottom) + `.tv-drop` (left:38px)
- **تست:** mainClick → `rv.tool='segment'` + drawing:true؛ ▾ → menuOpen؛ انتخاب → بسته + tool تغییر؛ zoomHit/zoomChanged true ✓
- **فاز ۰ — تثبیت رابط (interface freeze):** بخش «تحلیل بنیادی» (`fmtMcap`/`fmtBil`/`loadFundamentalData`/`switchModalTab`) و «کارتابل سبد» (کل بلوک `PF_KEY`/`pfState`/`pf*`) از `static/app.js` جدا شدند و به `static/fundamental_ui.js` و `static/portfolio_ui.js` رفتند. `app.js` از ۲۸۸۷ به ۲۳۷۰ خط رسید و فقط این توابع را صدا می‌زند (`openAnalysis` ← `loadFundamentalData`، `switchView('portfolio')` ← `initPortfolio`). هر دو فایل در `index.html` با همان cache-buster `v=9.8.1` و در `.github/workflows/guards.yml` ثبت شدند؛ گارد جداسازی در `dev/struct_check.py` قفل شد تا تعریف دوباره در `app.js` ممنوع بماند. `market.db.lzma` هم از `market.db` فعلی بازسازی شد (۱۰۰ MB ← ۱۶ MB، رفت‌و‌برگشت بایت‌یکسان)

### Clone کامل TradingView (از نهایتنگر nahayatnegar.com/tv و رهاورد)
- **نهایتنگر** = TradingView فارسی (iframe): titles فارسی واقعی استخراج شد (`خط روند`، `اصلاحی فیبوناچی`، `قلم`، `اشکال هندسی`، `متن`، `الگوXABCD`، `موقعیت خرید`، `بزرگ نمایی`، `ماندن در حالت رسم`، `قفل کردن ابزار های رسم`، `نمایش همه ابزارها و شکل ها`)
- **همهٔ emoji های topbar → SVG** (اندیکاتور/جستجو/Replay/سطوح/تم/تنظیمات/انتشار/لینک/تمام صفحه/ذخیره) — `rv-icon-btn .ic svg` CSS
- **حذف اضافیها:** دکمهٔ فونت (فقط toast بود)
- **CSS:** `.tv-tool`/`.tv-arrow` — arrow زیر آیکون مثل TV
- **باقیمانده از قابلیتهای TV:** Zoom/مغناطیس/Stay/Lock/Remove/Object Tree + ۷ گروه dropdown

### Verification (Visual QA Protocol)
- DOM: 14 btn / 6 arrow / 7 drop؛ صفر emoji (در toolbar + topbar)
- vision: «clean monochrome vector icons، absolutely no emojis، closely mimics TradingView; no overlap; professional» ✓

## [v3.7.0] — 2026-08-31 — Clone Rahavard Drawing Toolbar (گروهبندیشده TV-style)

### استخراج معکوس از رهاورد (logged-in)
- رهاورد = **TradingView embed در iframe** — ساختار ابزارها دقیق استخراج شد:
  گروهها با ▾ (Trend line tools / Gann and Fib / Patterns / Geometric shapes / Annotation tools / Icons) + Zoom In/Out + Magnet + Stay in Drawing Mode + Lock all + Hide all + Remove N + Show Object Tree + Show Drawings Toolbar

### بازسازی در `#drawToolbar` (14 دکمه + 7 گروه)
- **همه SVG (صفر emoji):** Cross/Cursor · Cursors▾ · Trend Line▾ (Trend/Straight/Ray/H/V/Parallel) · Fib▾ (Fib/PriceChannel/PriceLine) · Patterns▾ · Brush▾ · Annotation▾ · Zoom In/Out · Magnet · StayDraw · LockAll · Remove▾ · Object Tree
- Dropdown ها: `.tv-drop` (absolute، min-width 170px، shadow 0 2px 8px، border-radius 6px) — موقعیت از boundingRect، نه ثابت
- **JS جدید:** `rvToolMenu(id, btn)` toggle+بستن بقیه · `rvZoom(scale)` → `chart.zoomAtCoordinate` · `rvMagnet()` · `rvStayDraw()` · `rvObjectTree()` (خلاصهٔ رسمها)
- `rvSetTool` تمام drop ها را میبندد (مثل TV: انتخاب → بسته)

### تست (Visual QA Protocol)
- DOM: 14 btn / 7 drop / 14 SVG / صفر glyph؛ Trend menu باز: w=170، 6 item؛ انتخاب → بسته؛ zoom 10→10.5 ✓
- screenshot + vision: «TradingView-style grouped toolbar، vector icons، aligned، no broken/overlap» ✓

## [v3.5.0] — 2026-08-31 — Multi-Channel Notification Dispatcher

### جدید
- **`notifier.py`** — ماژول async (httpx) برای ارسال پیام به **Bale + Telegram**:
  - `send_telegram_msg(text, parse_mode="HTML")` — با proxy اختیاری (`TELEGRAM_PROXY`)
  - `send_bale_msg(text, parse_mode="HTML")` — مستقیم
  - `dispatch_alert(text)` — **asyncio.gather** همزمان به همهٔ کانالهای فعال
  - **Error boundary:** timeout/4xx/5xx هرگز raise نمیکنند؛ log با تگ `[notifier-telegram]`/`[notifier-bale]`
  - `send_telegram_doc()` — ارسال فایل (سند) اختیاری
  - **`.env` loader سبک** (بدون python-dotenv؛ همسایهٔ ماژول + CWD)
  - `_bot_url()` — صحافی URL: تلگرام و بله نیاز به `/bot<token>` بدون slash بعد از bot (با `/bot/<token>` → 404)
- **Env vars:** `TELEGRAM_ENABLED/BOT_TOKEN/CHAT_ID/API_BASE/PROXY` و `BALE_ENABLED/BOT_TOKEN/CHAT_ID/API_BASE` — همه با پیشفرض، `_env_bool` برای bool
- **API test endpoints:** `GET /api/notify/status` | `POST /api/notify/test-telegram` | `POST /api/notify/test-bale` | `POST /api/notify/test-all`
- Bale `getUpdates` → chat_id 1564791712 + `.env` پیکربندی شد (توکن محرمانه — .env در zip/exe نمیرود: `skip_files`)

### تست
- AST + syntax validation ✓
- `send_bale_msg` 실제 → message_id 4 (200 ok:true) ✓
- `dispatch_alert` → `{"ok":true,"sent":{"bale":true}}` ✓
- HTTP: `/api/notify/status` 200 + `/api/notify/test-all` ✓
- Error boundary: توکن فیک → 403 → `False` (بدون استثنا) ✓
- `httpx` → requirements.txt اضافه شد

## [v3.5.1] — 2026-08-31 — Whitelist Recipient Routing

### تغییرات
- **`TELEGRAM_ALLOWED_CHAT_IDS` / `BALE_ALLOWED_CHAT_IDS`** — comma-separated با strip؛ مثبت (یوزر) و منفی (گروه/سوپرگروه) هر دو پشتیبانی میشوند؛ ورودی نامعتبر فقط warning
- **Broadcast loop:** هر گیرنده در `_broadcast()` با `asyncio.gather` + **isolated try/except per-recipient** — یک ایدی باطل بقیه را متوقف نمیکند (تست: `1 موفق / 1 ناموفق` بدون کرش)
- **Empty whitelist:** `warning` واضح + skip آن کانال (تست: `TELEGRAM_ALLOWED_CHAT_IDS empty/unset — skip dispatch`)
- **خلاصهٔ ارسال:** همهٔ send ها حالا dict برمیگردانند: `{'ok', 'success': n, 'failed': m, 'summary': {id: bool}, 'detail'}`
- **اختیاری:** `BALE_CHAT_ID`/`TELEGRAM_CHAT_ID` بهعنوان fallback تک-گیرنده (اگر whitelist نبود) — backward compat
- **Endpoints:** `test-bale`/`test-telegram`/`test-all` حالا `{"success": 2, "failed": 0}` برمیگردانند

### تست (real)
- `send_bale_msg` → both IDs (1564791712, 5437294288): `success: 2, failed: 0` ✓
- `dispatch_alert` → `total: {success: 2, failed: 0}` ✓
- HTTP: `/api/notify/test-bale` success:2 | `/api/notify/test-all` ok:true ✓
- یکی از eID ها فیک (−999) → `1 موفق / 1 ناموفق` — بدون استثنا ✓
- AST/syntax: OK ✓

## [v3.6.0] — 2026-08-31 — UI/UX Refactor (Rahavard/TradingView parity)

### 1. Floating Action Pill (`#rvDrawFloatBar`)
- **ساختار جدید:** [Drag Handle ⋮⋮ | Color Picker 🎨 | Thickness 1-4 | Style Solid/Dashed | ⚙ | Lock | Delete]
- **CSS دقیق:** `border-radius: 6px`، پسزمینهٔ دینامیک (light `#ffffff` / dark `#1e222d`)، border `#e0e3eb`، shadow `0 2px 8px rgba(0,0,0,0.15)` — با کلاس `theme-dark` روی `#rvChartBox` برای تم تیره
- **کنترل زندهٔ KLineChart:** `rvDrawColor()` / `rvDrawWidth()` / `rvDrawStyle()` → `overrideOverlay({styles:{line:{color,size,style}}})` مستقیم روی آخرین رسم؛ color menu با ۶ رنگ + منوی بازشو `#rvFpColorMenu`

### 2. SVG Toolbar (بدون Unicode)
- **همهٔ یونیکد/ایموجیها حذف شدند** (`◉ 𝓕 $ 🏷 🖌 ╲ ╱ ― ⊞ ∥ ✖ 🗑 📝`)
- ۱۳ ابزار + ۲ اکشن → **۱۵ SVG inline vector** (24×24، stroke currentColor): Cursor, Trend, Straight, Ray, Horizontal, Vertical, Fib, Parallel, Price Channel, Price Line, Annotation, Tag, Brush + Delete-All

### 3. Legend OHLC (بالای چارت)
- **fix:** `{ticker}` placeholder → dynamic `بورشاجنت 365 | <symbol>`
- **قالب جدید:** نماد + تایمفریم + مقیاس + **باز/سقف/کف/پایانی/حجم** — badge های تمیز و **رنگ سبز/قرمز بر اساس صعود/نزول** (`rvUpdateLegend()` از آخرین کندل rv.data، با `_rvFmtNum` برای حجمهای K/M/B)

### تست
- E2E puppeteer: 15 SVG در toolbar (صفر glyph)، OHLC واقعی (683/703/672/696)، pill بعد از رسم ظاهر میشود، `overrideOverlay` با رنگ `#ef4444` + size 3 + style `dashed` ✓
- node --check: OK

## [v3.6.1] — 2026-08-31 — ۴ باگ بحرانی تب تکنیکال

### 1. Legend/Header HTML
- **fix:** `<b>` ها با `.textContent` رندر نمیشدند (رشتهٔ خام) → **`.innerHTML`** در `rvUpdateLegend()` + `rvChtSym`
- **fix:** `{ticker}` موجود نیست — نماد بهصورت داینامیک `بورشاجنت 365 | <sym>` رندر میشود (E2E تأیید)

### 2. Floating Action Bar
- **fix:** pill اجباری HORIZONTAL: `display:flex; flex-direction:row; align-items:center; gap:8px; padding:6px 12px; border-radius:8px; background:var(--bg-card); color:var(--text-primary)`
- **fix:** اعداد 1/2/3/4 → **۴ SVG با stroke-width 1-4** (جایگزین متن)

### 3. Auto-Charting
- **fix 1:** `rvRemoveAutoLevels(true)` **همیشه** قبل از رسم (حتی بدون force) — تغییر نماد دیگر رسم قبلی را نگه نمیدارد (E2E: خساپا 14 → رمپنا 18 → خساپا 14، نه 32)
- **fix 2:** فقط **۳ مقاومت + ۳ حمایت برتر** (kind split در `_key_levels_from_history`، با strength/idx رتبهبندی) — نه ۱۰ سطح شلوغ
- **fix 3:** `lock: true` روی همهٔ auto-overlays ✅ (تأیید E2E: 100%)

### Verification
- E2E puppeteer: legend `<b>` واقعی؛ pill flex-row/8px/var(--bg-card)؛ 4 SVG width؛ no-overlap؛ lock all ✓
- AST + node --check: OK

## [v3.6.2] — 2026-08-31 — Disable Native Tooltip + Visual QA Protocol

### Task 1: Tooltip بومی خاموش شد
- **ریشهٔ دوبلوچینی:** KLineChart tooltip پیشفرض (`showRule: "always"`) بالای legend سفارشی HTML رندر میشد و `{ticker}` خام را نشان میداد.
- **fix:** در `rvApplyStyles()` → `candle: { tooltip: { showRule: 'none', showType: 'standard' } }` + حذف `candleTooltip` مرده از setStyles.
- **تأیید:** `getStyles().candle.tooltip.showRule === 'none'`؛ `ttEls === 0` (هیچ tooltip بومی در DOM)؛ vision: یک ردیف legend واحد.

### Task 2: Mandatory Visual QA Protocol
- قانون در **SCHEMA.md** (core directives) + MEMORY ثبت شد: هر کار UI/CSS/HTML → قبل از نتیجهگیری **باید** preview/screenshot + vision_analyze + DOM-check؛ self-correct از feedback بصری.
- این task خودش با قهر قانون اجرا شد: ۲ screenshot + vision_analyze + DOM count.

### Task 3: Second Brain
- CHANGELOG v3.6.2 + log.md + SCHEMA.md + memory ✓

## [v3.6.3] — 2026-08-31 — CSS Structure Fix: Color Palette جدا از Pill

### باگ (از screenshot کاربر)
- **کاربر:** پالت رنگی داخل main toolbar رندر میشد → «giant ugly box»
- **ریشه:** `#rvFpColorMenu` دارای `style="display:none; ...; display:flex;"` — **دو نمایش تکراری**؛ `flex` آخر بر `none` غلبه → پالت همیشه داخل flex-flow نوار → بزرگ و باز

### رفع
- **`#colorPickerMenu`** — عنصر **کاملاً جدا** (فرزند `#rvChartBox`، نه `#rvDrawFloatBar` نه `.rv-float-pill`) با `display:none; position:absolute; bottom:50px; right:6px; z-index:23` + box-shadow/radius 6
- **Main Pill ثابت:** فقط `[Drag | ACTIVE Color Dot (فقط یک دات) | Width SVGs (4) | Style SVGs (2) | Lock | Delete]` — `max-height: 36px; padding 4px 10px`
- دکمهٔ ⚙ زائد حذف شد؛ پالت ۸ رنگ (2 رنگ جدید: sky/gray)
- JS: `rvDrawColorMenu()` → `colorPickerMenu`؛ بستن پالت بعد از انتخاب

### Verification (Visual QA Protocol)
- DOM: `pill h=36, w=370, flex, row` · `barChildren=1` (فقط pill) · `palette.isInsidePill=false` · `defaultDisplay=none` · بعد کلیک `block` → بعد انتخاب `none` ✓
- Screenshot + vision: «single compact horizontal row ~36px، palette completely hidden، sleek TradingView-like — not broken/giant/overlapping» ✓

## [v3.4.0] — 2026-08-31 — Feature 2: Auto-Charting

### جدید
- **Surfing خودکار در تکنیکال:** HTTP endpoint `/api/chart/{symbol}/key-levels` — از `price_history` (۲۵۰ روز آخر) سطحهای Swing High/Low (rolling extremes) و بلوکهای Demand/Supply (ساده: حجم ≥ ۱.۵× میانگین در اطراف افراطها) محاسبه میشود.
- **رندر خودکار با KLineChart:** در `tech_rtv.js` — `rvApplyAutoLevels()` بعد از لود هر نماد:
  - سطحها با `createOverlay('horizontalStraightLine')` (خط آبی برای کف / کهربایی برای سقف، dashed)
  - بلاکها با ۴ خط `segment` + `verticalSegment` (همین حالا رسمی است — نسخه باندل KLineChart overlay مستطیل `rect` ندارد؛ منشیابی: rect returns null)
- **دکمه ⚡ در بالا راست تکنیکال** — `rvToggleAutoLevels()` — ON/OFF + ایستایی: `stGet('tech_auto_levels', true)` (پیشفرض روشن).
- **پاکسازی:** `rvPersistTech` افزونههای `auto_*` را ذخیره نمیکند (هر بار دوباره fetch میشوند).

### تست
- E2E puppeteer: لوود خساپا → ۱۸ overlay خودکار (۱۰ خط + ۲ بلاک × ۴ خط)؛ toggle OFF → ۰؛ ON → ۱۸؛ `tech_auto_levels` ذخیره شد.
- `curl /api/chart/رمپنا/key-levels` → 10 levels + 3 blocks (250 روز).

### فیکس (حالا در پشت صحنه)
- `rect` در این build KLineChart وجود ندارد — مستند شد که برای zone ها از segment استفاده شود.
