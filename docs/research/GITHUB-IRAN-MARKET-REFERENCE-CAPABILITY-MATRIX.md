# ماتریسِ قابلیتِ پنجِ مرجعِ GitHub — بازارِ سرمایه ایران

**مأموریت:** BorsTerminal UI/UX 2.0 — بخشِ اولِ تحقیق
**تاریخِ سنجش:** ۱۴۰۵-۰۷-۲۴ / ۲۰۲۶-۱۰-۱۶
**بیسِ کدِ مقایسه:** `.worktrees/uiux-2-0` @ `mission/uiux-2-0-redesign-2026-10-16` = `ff6b2fb41a38b8e9acc2183d6ee7fa4e07a798d0`
**روش:** هر پنج مخزن باِ `git clone --depth 1` به `_scratch/ir-refs/` (بیرونِ مخزنِ محصول) گرفته شد وِ **همۀِ فایل‌هایِ منبعیِ آن‌ها کامل خوانده شد**، نه خلاصۀِ README. بازخوانیِ سطحیِ README درِ اینِ مأموریت مجاز نیست.

> **سه واژۀِ وضعیت که درِ کلِ اینِ سند تفکیک می‌شوند:**
> `IN-CODE` = درِ کدِ آن مخزن وجود دارد (باِ شاهدِ `file:line`) · `TESTED-THERE` = درِ همان مخزن آزموده شده · `VERIFIED-HERE` = درِ BorsTerminal ما سنجیده شده.
> چیزی که فقط `IN-CODE` است، **هیچ‌وقت** درست یا قابل‌اتکا فرض نشده است. ستونِ «درجۀِ اطمینان» همان تفکیک را عددی می‌کند: **بالا** = کد خوانده شد · **متوسط** = استنتاج ازِ چندِ شاهد · **پایین** = ادعایِ سند/README بدونِ شاهد.

---

## ۰) شناسۀِ پنج مرجع (همه سنجیده ازِ git، نه ازِ حافظه)

| # | مخزن | revision بررسی‌شده | کامیتِ قابلِ مشاهده | زبان/نوع | فایل | مجوز (خوانده‌شدہ ازِ فایل) |
|---|---|---|---|---|---|---|
| A | `sajadghandehari/mofid-autotrader` | `582d57032ea463b47827b2bc924d7b8ce6021490` | ۱ (۲۰۲۵-۰۴-۱۶، پیام «.») | Python 3 + PyQt5 + Selenium، دسکتاپ GUI، EXE باینری | ۱۳ | **LICENSE ندارد** |
| B | `estakhri/Sarkhati` | `b63f55b071ed15aa43781964005d40f58ddcd744` | ۱ | Rust (edition 2024) CLI، reqwest + tokio | ۱۶ | **LICENSE ندارد** (README می‌گوید MIT) |
| C | `AFP33/TSE` | `f3285d1a58994a977cb5a5bf28ca1a08aafda14f` | ۱ (۲۰۲۳-۰۴-۰۹) | .NET Framework 4.8 class library، C#، ۷٬۸۹۱ سطر | ۱۰۸ | **GPL-2.0-only** (متنِ کامل، بدونِ «هر نسخۀِ بعد») |
| D | `BabakEslami/tse-market-data` | `3d9d03b3b9f5d74b133cdaa567858b9bfbfcb6c0` | ۱ (۲۰۲۶-۰۷-۱۵، «Add files via upload») | فقطِ سندِ فارسی + یکِ probe پایتون | ۱۰ | MIT («Copyright (c) 2026 Babak Eslami») |
| E | `solitraderbusiness/tsetmc-mcp` | `abf182f1da56169be074258e719c43969ae0cb0b` | tag `v0.1.0` (۲۰۲۶-۰۷-۰۴) | Python ≥3.11، سرورِ MCP (FastMCP/stdio) | ۵۵ | MIT + `THIRD_PARTY_LICENSES.md` |

هیچ‌یک ازِ پنج، تاریخچۀِ واقعیِ develop ندارند (شالو) — پس «تاریخچۀِ لازمِ لازم» برایِ داوریِ driftِ upstream ازِ اینها گرفته نمی‌شود وِ اینِ کمبود درِ ردیف‌هایِ زیر ثبت شده است.

---

## ۱) مرجع A — Mofid AutoTrader (سرخطیِ مفید)

| بند | yافته | درجۀِ اطمینان |
|---|---|---|
| ساختار | دو `QMainWindow` ازِ Qt Designer باِ `loadUiType`؛ هیچِ backend، هیچِ DB، هیچِ UI وبی نیست (`manage.py:3-17`) | بالا |
| گردشِ ورود | فرمِ دو فیلد → `driver.get("https://account.emofid.com/Login")` → `Keys.RETURN` → انتظارِ ۱۰s برایِ یکِ **absolute XPath** `/html/body/div[1]/div/div/div[2]/div/div/a[1]` (`manage.py:88-107`) | بالا |
| گردشِ سفارش | باز کردنِ آیکونِ جست‌وجو → تایپ درِ `#searchInputControl` → کلیکِ نخستینِ نتیجۀِ `//*[@id="0"]/…` → حلقۀِ `while True: sleep(1)` تا برابریِ رشتهٔ ساعت → `for i in range(15)` کلیکِ دکمۀِ خرید + تأیید، باِ `sleep(0.2)` (`manage.py:109-141`) | بالا |
| **حجمِ سفارش** | `self.stock_num` درِ `:83` خوانده می‌شود وِ **دیگر هیچ‌وقت استفاده نمی‌شود** — حجمِ واقعی را وب‌اپِ کارگزاری نگه می‌دارد، نه اینِ ابزار | بالا |
| CAPTCHA/OTP | README می‌گوید «کد کپچا را دستی وارد کنید» — درِ کد **صفر** خطِ مربوطِ به کپچا/OTP/تازۀِ نشست وجود ندارد؛ تنها `chrome_options` بی‌آرگومان ساخته می‌شود (`:89`) یعنی مرورگرِ دیدنی، ولی هیچِ انتظاری برایِ انسان نیست وِ `WebDriverWait`ها اول throws می‌کنند | بالا |
| پیکربندی/وضعیت | همه‌چیز درِ حافظه، بی‌محوِ پس ازِ استفاده؛ نشانی‌ها درِ متنِ کد | بالا |
| ایمنی | **هیچِ** `try/except` درِ `web_scraping` → رویِ خطا `driver.quit()` اجرا نمی‌شود وِ یکِ Chromeِ **احراز هویت‌شده** زنده می‌ماند؛ بیِ acknowledge سفارش، بیِ reconcile، بیِ idempotency، بیِ preflight، بیِ kill switch؛ کار رویِ **رشتۀِ GUI** پس پنجره درِ انتظارِ قبلِ بازشدن فریز می‌شود | بالا |
| تله‌هایِ زمان‌بندی | مقایسه باِ `"hh:mm:ss"` درِ کد (`:85`) دربرابرِ نمایشِ `"ss:mm:HH"` ویجت (`main_page.ui:304-306`)؛ برابریِ دقیقِ رشته درِ `:128` می‌تواند باِ poll یک‌ثانیه‌ای رد شود وِ ابزار تا ابد منتظر بماند | بالا |
| بیلد | `manage.spec` می‌سازد `name='manage'` ولی EXE کامیت‌شده `Autotrader.exe` است؛ `datas=[]` یعنی `.ui`ها جاسازی نشده‌اند؛ `console=False` یعنی همهٔ `print`هایِ کد درِ بیلدِ توزیع‌شده نامرئی‌اند؛ `python311.dll` درِ TOC دربرابرِ ادعایِ README «Python 3.8» | متوسط |
| تست | صفر. بیِ pytest، بیِ CI، بیِ requirements.txt | بالا |
| مجوز | **LICENSE ندارد** → پیش‌فرض «تمامیِ حقوق محفوظ است»، هیچِ اجازه‌ای؛ حتیِ ترجمۀِ یکِ ایده درِ کدِ ما باید بازنویسیِ مستقل باشد | بالا |

**قابلِ اقتباس (مفهوم، نه کد):** دروازهٔ دو مرحلۀِ «اول احرازِ نشست، بعد شلیکِ زمان‌بندی‌شده»؛ یکِ سطحِ ۶۰۰×۳۰۶ باِ فقطِ نماد/زمان/اجرا وِ `RightToLeft` رویِ سطحِ پنجره؛ نمایشِ **همان** رشته‌ای که مبنایِ مقایسۀِ زمان است (بعدِ معکوسِ باگِ بالا).
**نامناسب:** کلِ روشِ Selenium/XPathِ مطلق (شکننده، باِ صفرِ تحملِ refactor)؛ `range(15)`: همان الگویِ «ارسالِ پیوسته/موازیِ بی‌نتیجه» که قاعدۀِ سختِ ما ممنوع می‌کند؛ inheriting حجم ازِ وب‌اپ؛ بی‌تفاوتی نسبتِ به «نتیجه نامعلوم»؛ اعتبارنامۀِ plaintext درِ attribute؛ کامیتِ باینریِ درایور.

---

## ۲) مرجع B — Sarkhati (شش آداپتورِ سرخطی، Rust)

### ۲-الف) جدولِ قراردادِ سفارش (مهم‌ترین ارزشِ اینِ مخزن — فقط **فرضیۀِ** قرارداد، نه مشخصه)

| کارگزاری | path (پیش‌فرض) | احراز هویت | هدرهایِ اجباریِ غیرِ body | قراردادِ «سمت» | قراردادِ «اعتبار» | نوعِ عددیِ قیمت/حجم |
|---|---|---|---|---|---|---|
| مفید | `mofidonline.com/apigateway/api/v1/Order/send` (`mofid.rs:25`) | Cookie اگر غيرِplaceholder، وگرنه `Bearer` (`:104-114`) | `x-appname: titan`، Origin/Refererِ `titan.mofidonline` | رشتهٔ `"Buy"/"Sell"` (`:32`) | `validityType:i32` + `validityDate:null` | عدد |
| آداپتور `bmi` (`api2.bmibourse.ir/Web/V1/Order/Post` (`bmi.rs:21`) | **فقطِ Cookie، اجباری** (`:110`) | `X-Requested-With: XMLHttpRequest` | کدِ ASCII `65`/`86` (`:47`) | `orderValidity:i32`، `0` | عدد + ۱۳ فیلدِ حاشیه‌ای (صورت‌حساب، shortSell، minimumQuantity…) |
| آداپتور `danayan` (`otapi.danayan.broker/api/v1/TseOms/RegisterOrder` (`danayan.rs:22`) | Cookie (`:86`) | Origin دارد، **Referer ندارد** (`:84`) | `1`/`2` (`:39`) | `orderValidityType:i32` = `1`، `orderPaymentGateway` | عدد + `disclosedQuantity:Option` |
| اردیبهشت (`api.oibourse.ir`…/Web/V1/Order/Post` (`ordibehesht.rs:22`) | Cookie (`:110`) | `X-Requested-With`، Origin/Refererِ `online.oibourse` | مثلِ `bmi` (میدان‌ها **بایت‌به‌بایت یکسان**) | `orderValidity:i32` | عدد |
| آداپتور `alvand` (`arzeshafarin.exirbroker.com/api/v1/order` (`alvand.rs:25`) | Cookie + **`X-App-N` محاسبه‌شده ازِ ساعت** (`:166`) | `nt` اجباری، بیِ serde default | رشتهٔ `SIDE_BUY`/`…` (`:99`) | رشتهٔ `"VALIDITY_TYPE_DAY"`، `validityDate: ""` (نه null) | عدد + `insMaxLcode`, `bankAccountId`, `coreType`, `dividedOrder` |
| بیدار | `api.bidartrader.ir/trader/v1/order/buy` — **سمت درِ path است، بیِ field** (`bidar.rs:24`) | `Bearer` (پیشوندِ idempotent `:47-51`)، **بیِ Cookie** | `TE: trailers`، `x-user-trace` اختیاری | درِ path | رشتهٔ `"DAY"` | **رشته** برایِ price وِ quantity (`:31-39`) — یگانه استثنایِ عددی |

الگوریتمِ `X-App-N` (خلاصه): `seconds-of-day(now − 2s)` → جمعِ char-codeهایِ **path** → offset دو بایتِ نخستِ `nt` → برشِ ۵ کاراکتر → `"floor(v)*S.S"` (`alvand.rs:41-94`). یعنی یکِ نشانیِ ضد-رباتِ وابسته به ساعت؛ هر attemptِ دوباره باید ازِ نو امضا شود.

### ۲-ب) رفتارِ اجرا و ایمنی (اینجا باید اینِ مرجع را رد کرد)

| بند | شواهد |
|---|---|
| حلقۀِ ارسال | `loop { … for order in config.orders { tokio::spawn(send_order) } sleep(batch_delay_ms=100) }` — **بی‌انتها** (`main.rs:151-181` وِ پنج تکرارِ verbatim درِ `:212,273,334,395,457`) |
| ارسالِ موازیِ تکراری | درِ حالتِ غیرِ-test، `handles` هرگز await نمی‌شوند وِ درِ انتهایِ loop drop می‌شوند ⇒ task جدا می‌افتد؛ هر ۱۰۰ms یکِ ارسالِ **همان** سفارش درحالِ پروازِ ارسالِ قبلی. اینِ دقیقاً همانِ چیزی است که قاعدۀِ «عدم تلاشِ مجدد» ما ممنوع می‌کند |
| timeout | **هیچ**: `reqwest::Client::new()` بیِ `ClientBuilder`، بیِ `with_timeout`/`connect_timeout` (grep صفر) ⇒ یکِ سوکتِ گیرکرده آنِ task را تا ابد نگه می‌دارد |
| خواندنِ نتیجه | تنها `status.is_success()`. **هیچِ adapter بدنه را deserialize نمی‌کند** ⇒ ۲۰۰ باِ «ردِّ کارگزاری» درِ body به‌عنوانِ `✓ Sent successfully` چاپ می‌شود (دروغِ وضعیت)؛ وِ خطایِ transport به‌عنوانِ `✗ Failed` (ادعایِ ناموفقِ قطعی برایِ سفارشی که شاید پذیرفته شده) |
| «نتیجۀِ نامعلوم» | درِ مدلِ داده **وجود ندارد**؛ صفرِ GET، صفرِ استعلامِ وضعیتِ سفارش، صفرِ استخراجِ order id |
| preflight / idempotency / reconcile / cancel | **همگی غایب**. `orderId` درِ `bmi`/اردیبهشت یکِ ثابتِ config است که هر batch دوباره باِ همانِ مقدارِ تکراری می‌رود (`bmi.rs:49-50`) |
| «حالتِ تست» | README می‌گوید test فقطِ پیکربندی را می‌آزماید — **دروغِ ایمنی**: `test` تنها حلقه را یکِ بار می‌چرخاند وِ POSTِ واقعی هم زده می‌شود؛ early-return فقط زیرِ `curl_only` است (`mofid.rs:92-95` وِ پنج جایِ دیگر) |
| crash-safety | `&config.cookie[..len.min(50)]` وِ برش‌هایِ `nt[2..]` باِ index بایتی رویِ UTF-8 panik می‌کنند (`main.rs:132,199…`؛ `alvand.rs:66,83`) |
| اعتبارنامه | JSONِ plaintext درِ CWD؛ `.gitignore` درستِ configها را بیرون می‌گذارد، ولی `config_bidar.example.json:5` یکِ `x_user_trace` واقعی-نما (رمزگشایی → `2480303608:IRO1NMAD0001`) درِ مخزنِ public نگه می‌دارد؛ اعتبارنامه درِ stdout چاپ می‌شود (۳۰-۵۰ کاراکتر اول) |
| تست | صفر `#[test]`، صفرِ `tests/`، صفرِ CI |
| مجوز | README: «License: MIT» ولی **هیچِ LICENSE فایل ندارد** (۱۶ فایلِ tracked، هیچِ LICENSE/COPYING) ⇒ ادعایِ بیِ پشتوانه، استفادهٔ مجددِ کد **unverified/at-risk** |

**قابلِ اقتباس:** همینِ جدولِ ۲-الف به‌عنوانِ **شش فرضیۀِ قراردادِ جداگانه** — که ثابت می‌کند یکِ آداپتورِ عمومی برایِ کارگزاری‌هایِ TSE کافی نیست وِ لایۀِ serialisation باید per-broker باِ جدولِ قراردادِ آزمون‌پذیر باشد (سمت درِ ۴ شکلِ متفاوت، اعتبار درِ ۴ شکل، نوعِ داده درِ بیدار رشته). `curl` flag تنها primitive امنِ اینِ مخزن است (چاپِ فرمان، بیِ ارسال) وِ همانِ چیزی که ما هم برایِ «پیش‌نمایشِ بدنه» لازم داریم.
**نامناسب:** حلقۀِ ارسالِ پیوسته وِ handleهایِ رهاشده؛ success ازِ HTTP status؛ «Failed» برایِ timeout؛ `test` به‌عنوانِ آزمونِ بی‌خطر؛ ریسینگِ `X-App-N` بیِ سقفِ اعتبار؛ هیچ‌یک ازِ کدهایش (بیِ مجوزِ اثبات‌شده).

---

## ۳) مرجع C — AFP33/TSE (نقشۀِ قابلیت، C#)

### ۳-الف) قابلیت‌هایِ IN-CODE (همۀِ ردیف‌ها ازِ `StockHandler.cs`/`MarketHandler.cs`/`BourseHandler.cs` قابلِ دسترس‌اند)

| قابلیت | IN-CODE | شاهد | نکته |
|---|---|---|---|
| فهرستِ کاملِ نمادها + طبقۀِ بازار (۱۱ `BondType`) | IMPLEMENTED | `MarketHandler.cs:42-87`، `StocksDeserializer.cs:22-41` | هر فراخوانی، کلِ بازار را دوباره می‌گیرد |
| آتی/اختیار | **STUB** | `MarketHandler.cs:76-77` `case BondType.Ati: // ERRRO → return null` | |
| جست‌وجویِ نماد | IMPLEMENTED | `MarketHandler.cs:29`، `SearchStockDeserializer.cs:31` | سطرِ غیرفعال باِ `[7]=="0"` حذف می‌شود |
| فهرستِ صنایع | IMPLEMENTED | `MarketHandler.cs:93` | JSONP باِ برشِ ۱۲ کاراکتر |
| شاخص‌ها / «در یک نگاه» بازار | IMPLEMENTED | `BourseHandler.cs:20,56`, `FarabourseHandler.cs:20` | |
| پرمعامله‌ها | IMPLEMENTED | `BourseHandler.cs:44`, `FarabourseHandler.cs:44` | |
| مؤثر بر شاخص (مثبت/منفی) | IMPLEMENTED | `BourseHandler.cs:32`, `FarabourseHandler.cs:32` | فرمولش **اینجا هم** نیست؛ فقطِ خوانده ازِ upstream |
| «در یک نگاهِ» نماد (آخرین/پایانی/اولین/دیروز/عدد/حجم/ارزش/بازۀِ روز) | IMPLEMENTED | `StockHandler.cs:83` | |
| دفترِ سفارش + فیلترِ بازۀِ مجاز | IMPLEMENTED | `StockHandler.cs:98`، `StockQueueDeserializer.cs:32-96` | `QueueStatus.Full|Clean` — سطرها بیرونِ بازۀِ مجاز **هستند وِ باید دیدنی متمایز شوند** |
| حقیقی/حقوقیِ زندۀِ امروز + تاریخچۀِ روزانۀِ جابه‌جاییِ مالکیت | IMPLEMENTED | `:48-58`, `StockHandler.cs:189` | |
| تاریخچۀِ معاملات (روزهایِ معامله/همۀِ روزها) + تیک‌به‌تیکِ درون‌روزی باِ تاریخ | IMPLEMENTED | `StockHandler.cs:28,43,57,71` | |
| اطلاعیه‌ها + لینکِ پیوست | IMPLEMENTED | `StockHandler.cs:111` | |
| تغییرِ وضعیتِ نماد / پیامِ ناظر | IMPLEMENTED | `:163,269` | |
| آمارِ ۸۹ شاخصه (روزهایِ مثبت/منفی، رتبه‌ها، میانگینِ ۳/۱۲ ماهه، خریدار/فروشنده، حقیقی/حقوقی) | IMPLEMENTED | `StockHandler.cs:281`، `StatisticsDeserializer.cs:51-291` | دیکشنریِ `id→value`، نه schema ثابت |
| ترازنامه، سود/زیان، EPS، DPS، سهام‌داران، هیئت‌مدیره، اعلامیۀِ/مصوبۀِ هیئت‌مدیره، پرتفوی، هویتِ شرکت (۱۴ کد)، اطلاعاتِ شرکت (۱۴ فیلد) | IMPLEMENTED | `StockHandler.cs:124…305` | `Shareholders`/`EPSs` هرکدام **دو** درخواستِ HTTP |
| تولید و فروش | **STUB** | `Address.cs:32` بیِ مصرف‌کننده؛ README می‌پذیرد ❌ | |
| اعلان/push، نمودار/کندل، WebSocket، واچ‌لیست | README-ONLY/غایب | هیچِ ردیفی درِ کد | |

### ۳-ب) قراردادِ داده و شناسه‌ها

- سه کلیدِ **هنوز هنجارنیافته**: `TseCode` (≈ InsCode، برایِ `tsev2?i=` وِ cdn JSON) · `Stock.Symbol` (فارسی، برایِ `CodalContent.aspx?s=` وِ DPS) · `Company12DigitCode` (برایِ سهام‌داران/EPS) — سومی ازِ **یکِ scrapeِ HTMLِ اضافه درِ هر فراخوانی** (`StockHandler.cs:206,220`) درمی‌آید وِ هیچِ cache ندارد. بیِ ISIN، بیِ LEI، بیِ registryِ پایدار؛ `Stock.Id` هیچ‌وقت پر نمی‌شود.
- هاست‌ها: `www.tsetmc.com`, `cdn.tsetmc.com`, `cdn8.tsetmc.com`, `tsetmc.com` (بیِ scheme درِ `Address.cs:37`). **همۀِ آدرس‌ها `http://`، صفرِ HTTPS، صفرِ codal.ir** — بنیادی ازِ proxyهایِ کدالِ خودِ TSETMC می‌آید.
- `?c=27!` درِ یکِ درخواست، همِ snapshot وِ همِ صفِ کامل می‌دهد (`instinfodata.aspx`) — نصفِ درخواست‌ها.
- `ParTree=15` باِ indexهایِ **موضعیِ** `table1[0,2,3,4,26,29,31]` خوانده می‌شود؛ `BourseDeserializer.cs:50` متنِ وضعیتِ فارسی را باِ طولِ رشته برش می‌زند.
- نرمال‌سازیِ ارقام: `۰-۹` وِ `٠-٩` → لاتین (`StringExtensions.cs:164`)؛ `()≡منفی` (`:236`)؛ ولی `RemoveStyle` هرگزِ جداکنندۀِ هزرۀِ فارسی `،` را نمی‌زداید.

### ۳-ج) پایداری/ایمنی و مجوز

- صفرِ persistence، صفرِ cache، صفرِ retry، صفرِ thread/rate-limit، صفرِ User-Agent. هر مسیرِ خطا: `try { } catch (Exception) { throw; }` (>۱۰۰ نقطه) وِ درِ هر سطر `catch { continue; }` — سطرِ خراب **بیِ علامت** حذف می‌شود.
- تبدیلِ عددی، دادهٔ خراب را بیِ صدا به `0` تبدیل می‌کند (`StringExtensions.cs:53-157`) ⇒ خطرناک برایِ قیمت؛ دقیقاً خلافِ قاعدۀِ «بی‌داده ≠ صفر» وِ خلافِ `docs/FTS_SYSTEM_SPECIFICATION_v2.md`.
- تست: **صفر**. پروجۀِ تستی درِ `Tse.sln` نیست؛ badge AppVeyor مرده است (بیِ `appveyor.yml`).
- مجوز: **GPL-2.0-only**. بندِ ۲ (copyleft رویِ کلِ کارِ مشتق)، بندِ ۵ (عدمِ الزامِ پذیرش ⇒ بیِ پذیرش حقِ کپی نداریم)، بندِ ۶ (اعطایِ خودکارِ downstream). متنِ «یا نسخۀِ بعد» فقط درِ پیوستِ «How to Apply» است، نه grant برایِ اینِ مخزن. **نتیجه: انتقالِ هیچِ کد/ترجمه/مشتقی به BorsTerminalِ خصوصی مجاز نیست** (حتیِ لینک‌کردنِ library مشتق می‌سازد). نامِ فیلدها، URLها وِ معناهایِ protocol حقِ مؤلفی ندارند وِ به‌عنوانِ **نقشۀِ تحقیق** قابلِ استفاده‌اند؛ متنِ کامنت‌ها وِ docstringهایِ فارسی مصون‌اند.

**ارزشتِ طراحی (مفهوم، بازنویسیِ مستقل):** تقسیمِ strict «یکِ controller به‌ازایِ endpoint، یکِ deserializer به‌ازایِ payload» ⇒ ردیابیِ قابلیت؛ نمایۀِ سه‌لایه (Market / Bourse+Farabourse / نماد) که باِ IAِ «صفحۀِ بازار» دربرابرِ «صفحۀِ نماد» ما جفت می‌شود؛ نگه‌داشتنِ `OtherData` شفافِ ستون‌هایِ ناشناخته؛ تفکیکِ `QueueStatus` برایِ صف بیرونِ بازۀِ مجاز؛ آمارِ مبتنی بر دیکشنریِ id (تحملِ churnِ ستون)؛ یکِ درخواستِ `c=27!`.
**غیرقابلِ انتقال:** روشِ همگام باِ بررسیِ reason-phrase، http-only، بیِ TLS/backoff؛ scrape موضعیِ `table1[N]`؛ درآوردنِ کدِ ۱۲ رقمی باِ scrape اضافه درِ هر مسیر؛ صفرسازیِ خاموش؛ هر خطور GPL-2.

---

## ۴) مرجع D — TSE Market Data (کاتالوگِ ۹۳ endpoint)

### ۴-الف) چه‌چیزی واقعاً درِ مخزن است

فقطِ سند: `ENDPOINTS.md` ۶۳۹ سطریِ فارسی (v4.1، «تولیدِ ۱۴۰۵-۰۴-۲۴»)، چهار `ex/*.json` که خودشان درِ `_note` **ساختگی** خوانده‌اند (`insCode:"9999999999999999"`)، وِ یکِ probe زندهٔ ۳۴۲ سطری (`sc/test_active_tsetmc_endpoints.py`). **هیچِ capture خامی منتشر نشده.** یکِ کامیت، بیِ تاریخچه ⇒ نه drift قابلِ مشاهده نه تأییدِ زمانِ هر ادعا.
سند second-hand است: `EP:12-32` چهار «user upload» را نام می‌برد وِ `EP:49-53` cross-check باِ تحلیلِ ChatGPT را ثبت می‌کند. تناقضِ زنده درِ خودش: `EP:24-27` می‌گوید «ENDPOINTS.md مخزن نسخۀِ انگلیسیِ قدیمیِ بیِ بخشِ Index است» درحالی‌که همانِ فایل، نسخۀِ کاملِ فارسیِ **باِ** آنِ بخش است ⇒ قابِ provenance نامطمئن است.

### ۴-ب) سه surface، سه سطحِ تضمین (تفکیکی که دستورِ مالک خواست)

| surface | شمار | کلید | دستیابیِ اعلام‌شده | پوششِ probe |
|---|---|---|---|---|
| `cdn.tsetmc.com/api/*` | ۶۲ path | `InsCode` | UA اجباری وگرنه ۴۰۳؛ CORS/ مرورگر blocked ⇒ backend proxy لازم؛ ازِ GitHub Actions رسیدنی اعلام شده | ۵۵ ردیفِ script |
| `old.tsetmc.com/tsev2/excel/MarketWatchPlus.aspx` | ۱ | فقطِ **سمبلِ فارسی** (بیِ InsCode/ISIN) | xlsx باینری، ۳۱۳۶ سطر درِ یکِ درخواست، نیازمندِ `openpyxl` | ۱ |
| `webgw.tse.ir` | ۳۰ | **ISIN کامل** | فقط ازِ IP ایران (نقل‌شده ازِ یکِ پروژهٔ دیگر، نه آزموده‌شده اینجا) | **۰ — `grep -c webgw sc` = 0** |

و سه base pathِ ناهمگون درِ webgw (سنجیده باِ شمارشِ من): `/InstrumentProvider/api/v1` ×۲۶، `/cmssite/api/v1` ×۴، `/api/v1/PublicData` ×۱ — خودِ سند فقط ازِ استثنایِ `MarketDate` می‌گوید وِ استثنایِ دوم را کم می‌گوید ⇒ «کمکِ function باِ یکِ base pathِ عمومی» یکِ باگِ نهفته است.

### ۴-ج) قراردادِ فیلدها — چه چیزی **اثبات نمی‌شود**

- **واحدها هیچ‌جا مستند نیستند:** جست‌وجویِ «ریال/تومان/rial/toman» درِ کلِ مخزن صفرِ نتیجه. هیچِ قراردادِ fixed-point (`xsMark`، تقسیمِ ۱۰⁴)، هیچِ tick-size. تنها inference، `ex/GetClosingPriceInfo.json` است که چون ساختگی‌ست فقط self-consistency خودش را ثابت می‌کند.
- درصدِ ساده، بیِ scale (`xVarIdxJRfV:-1.9717`)؛ `GetIndexCompany` هیچِ فیلدِ درصدی ندارد ⇒ باید ازِ `priceChange/priceYesterday*100` ساخته شود.
- `DEven`/`hEven` = `YYYYMMDD`؛ فرمتِ `devenrlc`, `tarixSarresid`, `lastdatechange` هرگز نوشته نشده.
- اعدادِ webgw درِ پوستۀِ `{"value":…,"state":…}` پیچیده می‌شوند؛ `MarketMapNew` بازگشتیِ `groups[]→groups[]` است.
- `bestLimits` پنج سطح می‌دهد باِ `zOrdMeDem/pMeDem/pMeOf/zOrdMeOf` وِ **`qTitMeDem/qTitMeOf` درِ نمونه نیست** (`EP:616` خودش می‌گوید «شاید وجود داشته باشد»)، وِ feed به‌شکلِ delta است ⇒ بازسازیِ لازم.
- شناسه‌ها: `InsCode` رشتهٔ ۱۷ رقمی؛ ISIN → کلاسِ دارایی (`IRO1` سهامی، `IRO5` رشد، `IRT1` واحدهایِ صندوق، `IRO9` اختیار، `IRB3TR` درآمدثابت)؛ اما `IRO1` تابلو را متمایز نمی‌کند (فولاد وِ وسکهبو هر دو `IRO1` باِ `cgrValCot` ن1/ن2) ⇒ برایِ نامِ دقیقِ تابلو باید `cgrValCotTitle`. خانوادۀِ TradingView باِ **نامِ فارسیِ سمبل** کلید می‌شود، نه ID.
- coverage: market watch درِ cdn **همیشه خالی** (`GetMarketWatch → marketwatch:0`)، جایگزین‌ها old-excel وِ هفت تبِ webgw؛ `Trade/GetTradeHistory` ۳۶–۳۸٪ کسریِ اعلام‌شده نسبتِ به official ⇒ `sum(volume)` هرگز نباید aggregate بسازد؛ `Shareholder` ۴ ازِ ۵ خالی؛ `Fund/*` برایِ سهم ۵۰۰ می‌دهد؛ `IndexLiveById` همیشه ۲۰۴.
- غایبِ کامل: هیچِ WebSocket/stream؛ هیچِ کندلِ درون‌روزی (TV `hasIntraday:false`، فقطِ `1D`)؛ عمقِ بیشترِ ازِ ۵ سطح؛ سودِ تقسیمی/مجامع/اقداماتِ شرکتی؛ عرضه/پذیرنویسی؛ پرتفویِ صندوق‌ها؛ صورتِ مالی/KPI (کارِ codal.ir).
- هیچِ rate limit کمّی اعلام نمی‌شود؛ تنها آیینِ probe: `--delay 0.1` وِ backoff `0.6×2^attempt` رویِ ۴29/502/503/504. امضاهایِ بلاکِ قابلِ استفاده برایِ detector ما: `"request rejected"`, `"درخواست شما به دلایلی مسدود شده"`, `"access denied"`, `"cloudflare"`.
- **`SPA_DEAD` مهم‌ترین درسِ اینِ مرجع است:** pathِ ناشناخته رویِ cdn باِ fallback به HTMLِ SPA پاسخِ **۲۰۰** می‌دهد ⇒ «۲۰۰ گرفتم» اصلاً اثباتِ وجودِ endpoint نیست.

**مجوز:** MIT، نگهبانِ copyright notice؛ منهایِ این، grant فقطِ **سندِ خودش** است، نه دادهٔ TSETMC/TSE (ازِ آنِ او نیست که ببخشد) وِ نه نامِ پروژه‌هایِ ثالثِ داخلِ متنِ او. عملی: سندِ او را spec نکنید؛ به‌عنوانِ سرنخِ attribute کنید.

---

## ۵) مرجع E — TSETMC MCP (الگوهایِ داده‌گیری و تازگی)

معماریِ لایه‌ایِ تمیز: `server.py` (پوستۀِ باریکِ ۱۳ ابزار FastMCP) → `service.py` (منطقِ بیِ MCP، ۳۹۹ سطر) → `snapshot.py` (حالت) → `fetch/` (پروتکل + دو backend)؛ `models/shaping/normalize/jalali/calendar` خالص‌اند.

### ۵-الف) قراردادِ تازگی — ارزشمندترین برداشتِ اینِ پنج مرجع

`Snapshot.meta()` یکِ قراردادِ واحد است که به **همۀِ** پاسخها می‌چسبد (`snapshot.py:100-120`):

```
source:  "raw:snapshot" | "raw:live"      ← منشأ: cache یا upstream
as_of:   {gregorian, jalali "YYYY/MM/DD", deven, time "%H:%M:%S"} | null
staleness_seconds | null · market_open · upstream_reachable
instrument_count · warming_up · note
```

- «نامعلوم» یعنی **`null`، هیچ‌وقت صفر**: `staleness_seconds()` بیِ `updated_epoch` مقدارِ `None` می‌دهد (`:95-98`) وِ `as_of` بیِ `updated_dt` هم `None` است (`:103-108`).
- `warming_up` + `note` انسانی، «سرد» را ازِ «خراب» جدا می‌کند (`:116-119`).
- `stamp()` تقویمِ سه‌گانه می‌دهد (`jalali.py:75-81`) — دقیقاً چیزی که یکِ age-chipِ RTL لازم دارد.

**چهار گپِ مستندِ همینِ قرارداد (که نباید کپی شود):** (۱) فقطِ `update_prices` صداکنندۀِ `_mark_updated()` است (`:49`) ⇒ جریانِ پول وِ شاخص باِ ساعتِ قیمت مُهر می‌خورند وِ ممکن است بی‌سکوت کهنه‌تر ازِ برچسب باشند؛ (۲) `last_error` ذخیره می‌شود (`:32,66`) ولی درِ `meta()` هیچ‌وقت منتشر نمی‌شود ⇒ `upstream_reachable:false` بیِ **علت** می‌آید؛ (۳) تازگی صرفاً **توصیفی** است — هیچِ ابزاری باِ `staleness_seconds` دروازه نمی‌گذارد وِ snapshot سه‌ساعته همان‌طور سرو می‌شود که تازه؛ (۴) خطایِ pollهایِ ثانویه به logی warning تبدیل می‌شود (`poller.py:66-69`) ⇒ هیچِ degraded flag برایِ آنِ زیرسیستم.
درسِ ما: درِ یکِ دسکتاپ تازگی باید **اجرایی** باشد، نه توصیه‌ای؛ وِ per-subsystem ساعت.

### ۵-ب) poller، محدودیتِ سرعت، پارسرِ ایمن

- poller: یکِ task؛ داخلِ نشست هر ۵s (`config.py:50`)؛ بیرونِ نشست idle باِ بازبینیِ تقویم هر ۶۰s وِ نگه‌داشتنِ آخرین snapshot (`poller.py:83-84`)؛ warm-up **فقط** اگر بازار باز است (چون بیرونِ نشست `GetMarketWatch` سطرهایِ صفر می‌دهد)؛ circuit breaker `min(5·2^fail, 120)`؛ قیمت‌ها critical (خطا انتشار می‌یابد)، client-type/overview best-effort؛ shutdown باِ `_stop` Event + done-callback.
- **هیچِ single-flight/dedup وِ هیچِ cache TTL ندارد**؛ دو ابزارِ هم‌زمان برایِ یکِ نماد هر دو fetch می‌کنند (`service.py:100,139,150`)؛ `filter/store.py` بیِ سقفِ رشد است.
- کد-اجرایی: token bucket باِ حداقلِ فاصلۀِ نرم‌شدۀِ ۱٫۵ req/s (`session.py:53-70`)، `Semaphore(2)`، `ClientTimeout(total=12s)`، ۵ attempt باِ backoff `min(2^n·0.5, 8)`، وِ **۴۰۳/۴۲۹ فوراً `TsetmcBlocked` بیِ هیچِ retry** (`:120-121`)؛ ۵۰۰/۵۰۲/۵۰۳/۵۰۴ retry؛ سنجشِ نشانه‌هایِ صفحۀِ بلاکِ فارسی (`مسدود`, `دسترسی شما`, `General Error Detected`) + non-JSON؛ ترجیحِ endpoint انبوه به‌جایِ حلقۀِ per-symbol.
- README-فقطِ (هیچ‌جا درِ کد اجرایی نیست): «باید IP ایران باشد» — صفرِ منطقِ جغرافیایی. پس ادعایِ IP/markets را **هرگز** نتیجهٔ تستِ خودمان گزارش نکنید؛ واقعیتِ ما ۴۲۹/بن وِ چرخشِ IPِ خودِ ریپو (`codal_fetcher.rotate_ip_via_adb`) است.
- `enrich_limit` هیچ‌وقت clamp نمی‌شود (`service.py:342`) ⇒ یکِ فیلتر می‌تواند قانوناً ~۷۰۰ fetch صفحۀِ سفارش بزند؛ queryِ کاربر بیِ percent-encoding درِ path می‌نشیند (`raw_source.py:147`).
- پارسرِ ایمن (`filter/safe_eval.py`): AST allowlistِ دست‌نویس، بیِ `eval/exec`؛ فقطِ Expression/BoolOp/UnaryOp(Not,USub,UAdd)/BinOp/Compare/Name/Load/Constant/Call (`:19-45`)؛ constant فقطِ int/float/str/bool (`:105`)؛ call فقطِ نامِ allowlisted (`:108`)؛ **keyword argument رد** (`:110`)؛ متغیر ناشناخته رد (`:118`)؛ سقفِ ۱۰۰۰ کاراکتر (`:87`) وِ ۲۰۰ گرهٔ AST (`:96`)؛ `round` clampِ ±۱۰۰؛ ۷ تابعِ مجاز؛ بدونِ attribute/subscript ⇒ `__class__` وِ `open()` درِ زمانِ compile می‌میرند (ثابت‌شده باِ `test_filter_safe_eval.py:41-55`). نرمال‌سازیِ نحوِ TSETMC (`normalize_expr.py`): `(pl)`→`pl`، `(ct).Buy_I_Volume`→`ct_buy_i_vol`، `&&/||/!`→and/or/not باِ پرانتزِ اولویت، `buy_queue()` sugar، وِ **ردِّ صریحِ اصطلاحاتِ `[ih]`/`[is..]` باِ جایگزینِ عملیاتی**؛ rewrite فقط **بیرونِ** literalهایِ رشته‌ای ⇒ `contains(name,"a&&b")` سالم می‌ماند.
- صداقتِ «بی‌داده» بیشترِ جا درست است: `0 → None` چون رویِ TSETMC صفر یعنی «معامله‌ای نشد» (`models.py:34-38`) — قاتلِ باگِ «-۱۰۰٪ِ ساختگی»؛ `to_number` پیش‌فرض `None`؛ نمادِ کم‌معامله درِ breadth جدا bucket می‌شود (`service.py:196-212`)؛ NaN→no-match وِ عبورِ درست ازِ `not` ⇒ `not (missing != 0)` نمی‌تواند سطرِ گم‌شده را match کند؛ NaN→`None` برایِ JSON. سه **ساختگیِ واقعی** که نباید کپی شود: `shaping.py:22-25,71,73` که `None→0` برایِ sort/min-filter می‌کند (دربرابرِ `engine.py:178-182` که درست `-inf` می‌دهد — دو قرارداد درِ یکِ مخزن)، `models.py:117` `level = … or 0` که سطحِ صفر می‌سازد، وِ ناسimetrِی `_num` (صفر را نگه می‌دارد) دربرابرِ `_price` (صفر را None می‌کند) ⇒ شاخصِ صفرِ بیرونِ نشست به‌عنوانِ `0` واقعی گزارش می‌شود.
- خطا: سلسلۀِ تایپ‌شده (`TsetmcError/Blocked/Unreachable`)؛ هر مسیرِ خطا `{error, detail, meta, hint}` ساختاریافته برمی‌گرداند نه exception، باِ ۸ code؛ stdout رزروشدۀِ JSON-RPC، log درِ stderr.
- تست: ۱۳ فایل، ۱۰۱ تابع، ۱۰۷ case باِ collectِ قابلِ تطبیق، **صفرِ دسترسیِ شبکه‌ای** (grep ازِ `aiohttp|requests|socket|tsetmc.com|vcr|responses` فقطِ یکِ docstring زد)؛ fixture = `FakeSource` + `Snapshot` پیش‌گرم درِ حافظه؛ پوششِ رفتاری نه درصدی؛ regressionهایِ خصمانۀِ `test_review_fixes.py` (۰-قیمت ≠ -۱۰۰٪، برخوردِ آستانۀِ pmn/pmx، حسابِ breadth، ارقامِ فارسیِ insCode، زدودنِ bidi-isolate، سالِ جلالیِ ۲ رقمی). من suite را **اجرا نکردم** (مأموریت read-only) ⇒ «۱۰۷ سبز» سازگار باِ collect است ولی **UNVERIFIED**. CI فعال نیست (فقطِ `docs/github-actions-ci.yml`).
- مجوز: MIT؛ **دام:** `library` extra، `5j9/tsetmc` را زیرِ **GPL-3.0** می‌آورد (`pyproject.toml:22`) — pip-install بی‌اثر است، ولی vendoring درِ باندلِ PyInstaller/Inno ما آنِ باندل را کارِ ترکیبیِ GPL می‌کند ⇒ هرگزِ GPL-dependency درِ بسته نریزید.

**الگوهایِ قابلِ انتقال:** قراردادِ `meta()`ِ تازگی (باِ دو اصلاحِ بالا)؛ قاعدۀِ `0 ⇒ None`؛ پارسرِ allowlist (MIT ⇒ port مجاز، باِ attribution)؛ نظمِ poller (دروازۀِ ساعتِ بازار، backoff سقفدار، انزوایِ سیگنالِ ثانویه)؛ **۴۰۳/۴۲۹ = retry نکن، بالا بیاور**؛ سنجشِ نشانه‌هایِ بلاکِ فارسی؛ اجرایِ دو سطحیِ فیلتر (اسکنِ snapshot، آنگاهِ order-book فقط رویِ یکِ فهرستِ کوتاهِ نقدینگیِ سقفدار)؛ offloadِ CSV بالایِ سقفِ سطر.
**غیرقابلِ کاربرد:** خودِ MCP/stdio، `describe_fields`، شکل‌دادگیِ context-window (مصرف‌کنندۀِ ما React/TanStack است نه LLM)؛ singletonِ import-time؛ storeِ فایلِ صافِ `filters.json` (ما SQLite داریم — فقطِ جریانِ «اعتبارسنجیِ قبلِ ذخیره» را بردارید)؛ snapshotِ صرفاً در‌حافظه (ترمینالِ دسکتاپ نمی‌تواند cold-startِ بی‌داده بپذیرد).

---

## ۶) ماتریسِ رو‌به‌رو: کدام شکافِ BorsTerminal را هر مرجع می‌پوشاند

سنجشِ «پوششِ فعلیِ ما» ازِ همینِ بیسِ `ff6b2fb` وِ باِ `grep`/`ls` رویِ `.worktrees/uiux-2-0` انجام شده، نه ازِ حافظه.

| شکاف/نیازِ ما | شاهدِ موجود | مرجعِ مرتبط | حکم |
|---|---|---|---|
| تازگیِ **به‌ازایِ ویجت**، نه ساعتِ سراسری | `api/market_status.py` ۲۱ router؛ `useMarketPanels.ts` هفت مسیر؛ هیچِ age-chipِ per-panel | E | **بازطراحیِ UI + قراردادِ پاسخ** (داده درِ پاسخ هست: `updated_at`) |
| `/api/mstat/board` بیکار (بیِ مصرف‌کنندۀِ React) | `grep -rn "mstat/board" frontend/src` → صفر؛ فقطِ `board_cache`/`board_rows` درِ `useLiveStats.ts:60-61` | E (الگویِ snapshot) | **قبلِ اتصال، قرارداد وِ سودِ واقعی سنجیده شود** — بندِ ۸ همینِ سند |
| صفحۀِ نقشۀِ بازار (treemap) | `MarketTreemap.tsx` (۳۴۷ سطر) + `/api/mstat/treemap` | C (صنایع/فهرست‌ها) | **ازِ قبل پیاده** — بازسازی نکنیم |
| ستون‌هایِ رتبه‌بندی + سوییچِ تابلو | `RankedPanels.tsx` (۱۵۷) + `tops/orderflows/ownership` | C/D | **ازِ قبل پیاده** |
| مقایسۀِ شاخص‌ها، کارتِ شاخص | `MarketCompareSection.tsx` (۴۷۲), `indexcards` | D | **ازِ قبل پیاده** (منبعِ غیربورسی: BLOCKED) |
| بنیادیِ تجمیعیِ «گروه × دوره» | `financial_statements` + `monthly_sales`؛ aggregate ساخته‌نشده | C (۲۲ متدِ بنیادی + آمارِ ۸۹گانه) | **بک‌اندِ تازه لازم**؛ مرجعِ اعتبار کدال، نه رهاورد؛ GPL ⇒ مفهوم نه کد |
| عمقِ صف + متمایزکردنِ سطرها بیرونِ بازۀِ مجاز | `order_book.book_txt`؛ `OrderBookFive.tsx` | C (`QueueStatus.Full|Clean`), D (`bestLimits` delta) | **الگوییِ قابلِ اقتباس**؛ بازسازیِ delta وِ نشاندۀِ «بیرونِ بازه» |
| پارسرِ فیلترِ کاربرِ ایمن | `useTapeStore.query` + `applyFilters` (`MarketPage.tsx:24-65`)؛ هیچِ AST-validation درِ مسیرِ کاربر | E (MIT، کامل) | **port باِ attribution**؛ بهترینِ جوابِ آماده |
| نرخِ درخواست/۴۲۹/بن | `codal_fetcher.rotate_ip_via_adb`, `--polite`, `--extract-workers` سقفِ ۱۶ | E (bucket+semaphore), D (پیش‌نهادِ backoff) | **ما جلوتریم**؛ فقطِ «۴۰۳/۴۲۹ = بیِ retry» را صریح‌تر کن |
| تیکتِ سرخطی، preflight ۹گانه، ledger، reconcile | `orderClient.ts:147` صداکنندۀِ `/api/execution/status` که `source:'absent'` می‌گیرد؛ **`api/execution.py` درِ اینِ بیس نیست** | A (مفهومیِ ردشده), B (قراردادِ ۶ آداپتور) | **BLOCKED** — بندِ ۹ |
| ربات (paper/live، kill switch، decisions) | `BotPanel.tsx`/`botClient.ts` درِ هیچِ شاخۀِ اینِ ماشین نیستند | A/B (هیچ‌کدام ربات ندارند) | **BLOCKED** — بندِ ۹ |
| واحدها (ریال/تومان، tick، fixed-point) | `price_basis.py` تنها resolverِ ما؛ سندِ D بیِ واحد | D (هشدارِ نبودِ spec) | **هیچِ مرجعی answer نمی‌دهد**؛ فقطِ contract داخلیِ ما معتبر است |

---

## ۷) فهرستِ «نباید منتقل شود» (خطوطِ قرمزِ ایمنی)

| مرجع | رفتار | چرا باِ قاعدۀِ ما در تعارض است |
|---|---|---|
| A | `for i in range(15)` کلیکِ کور | ارسالِ مکررِ بیِ نتیجه؛ ممنوع |
| A | بیِ acknowledge/reconcile؛ نتیجه‌ای خوانده نمی‌شود | «نامعلوم» اصلاً مدل نمی‌شود |
| A | بیِ `try/except` ⇒ Chromeِ احرازشده زنده می‌ماند | نشستِ بازِ رهاشده = خطرِ امنیتی |
| A | حجمِ inherited ازِ وب‌اپ | حجم باید صریح وِ preflight شده باشد |
| B | حلقۀِ بی‌انتها + `handles` رهاشده باِ ۱۰۰ms | ارسالِ موازیِ تکراریِ همانِ سفارش؛ ممنوعِ صریح |
| B | صفرِ timeout؛ «Failed» رویِ transport error | نتیجهٔ نامعلوم را ناموفقِ قطعی نشان می‌دهد؛ ممنوع |
| B | success ازِ `is_success()` باِ بی‌توجهی به body | ادعایِ موفقیتِ ساختگی |
| B | `test` که POST واقعی می‌زند | سفارشِ واقعی به‌عنوانِ تست؛ ممنوع |
| B | idempotency/reconcile/preflight: صفر | چهار ستونِ ایمنیِ ما را تضعیف می‌کند |
| C | صفرسازیِ خاموشِ عددِ خراب؛ `catch{continue}` سطرها | «بی‌داده ≠ صفر»؛ گپِ دیدنی باید بماند |
| C | http-only، بیِ TLS، بیِ rate limit | بستهٔ ما باِ updater/signature منتشر می‌شود |
| C | GPL-2.0-only | حتیِ ترجمۀِ کد، کارِ مشتق است |
| D | پذیرفتنِ «۲۰۰» به‌عنوانِ دلیلِ وجودِ endpoint | `SPA_DEAD` همینِ استدلال را باطل می‌کند |
| E | `None→0` برایِ sort؛ `level or 0` | دو قراردادِ متضاد؛ مقدارِ مفقود را مقدارِ واقعی می‌کند |

---

## ۸) `/api/mstat/board` — قبلِ اتصال، چه می‌دانیم وِ چه نمی‌دانیم

- موجود وِ بیکار: ۲۱ router درِ `api/market_status.py`؛ `board` وِ `snapshot` (POST) درِ `:368`/`:389`. جست‌وجویِ `mstat/board` درِ `frontend/src`: **صفرِ مصرف‌کننده**.
- ادعا (ازِ سندِ رهاورد، شاهدِ آنِ سند): «هشت پنل درِ یکِ درخواست، بودجۀِ کوئری را ثابت می‌دارد». **من اینِ ادعا را درِ اینِ بیس هنوز اجرا نکردم** وِ تا سنجشِ زنده (شمارِ SQL query دربرابرِ هفت hookِ جدا، زمانِ پاسخِ واقعی رویِ `market.db` اینِ ماشین) آنِ را «سودِ اثبات‌شده» گزارش نمی‌کنم.
- شرطِ پذیرشِ اتصال: (۱) شمارِ SQLِ صفحه باِ افزایشِ شمارِ نماد ثابت بماند؛ (۲) تازگیِ **per-panel** درِ پاسخِ تکی حفظ شود (وگرنه یکِ `as_of` سراسری، گپِ ۵-الف/۱ را تولیدِ مجدد می‌کند)؛ (۳) degraded/errorِ یکِ پنل کلِ بسته را نکشد؛ (۴) `GZip` بیرونِ ۱KB بماند. اگرِ (۲) یا (۳) نشد، همانِ هفت query جدا **بهتر** است وِ اینِ بند درِ گزارشِ پیاده‌سازی به‌عنوانِ «rejected with reason» می‌ماند.

---

## ۹) مانعِ ثبت‌شده: اجرایِ سفارش وِ ربات درِ اینِ بیس وجود ندارد

سنجیده (نه ازِ سند): `git ls-tree main -- api/ | grep -E "execution|bot"` → **خالی**؛ `git ls-tree mission/windows-stable-release-2026-10-15 -- api/` → `api/bot.py`، `api/execution.py`؛ `find frontend/src -iname "*bot*"` → **خالی**. `git rev-list --left-right --count main...HEAD` = `0 54` ⇒ بیسِ ما **همۀِ `main` را دارد** وِ باِ اینِ حال آنِ دو router را ندارد؛ پس آنِ دو فقط درِ شاخۀِ مأموریتِ ویندوز (وِ درِ `refs/stash` ماشینِ PCMOD برایِ رابطِ تاریخی `5307a795`) زنده‌اند.
نتیجه: فازِ E درِ اینِ شاخه **BLOCKED** است تا مالک/سیستمِ اول تکلیفِ ادغامِ `api/execution.py` + `api/bot.py` را روشن کنند. من endpoint ساختگی نمی‌سازم وِ شاخۀِ آنِ مأموریت را هم واردِ کارِ خودم نمی‌کنم (بندِ ۲ دستورِ اصلی). هر چیزی که درِ اینِ دور ازِ مسیرِ «سرخطی/ربات» ساخته شود، فقطِ ناوبری وِ حالتِ صادقِ «سرویسِ اجرا نیست» خواهد بود — همانِ چیزی که امروز `WatchSummaryPanel.tsx` نشان می‌دهد.

---

## ۱۰) بازتولیدِ شواهد

```bash
# پنج مرجع، بدونِ آلودگیِ مخزنِ محصول
mkdir -p _scratch/ir-refs && cd _scratch/ir-refs
git clone --depth 1 https://github.com/sajadghandehari/mofid-autotrader
git clone --depth 1 https://github.com/estakhri/Sarkhati
git clone --depth 1 https://github.com/AFP33/TSE
git clone --depth 1 https://github.com/BabakEslami/tse-market-data
git clone --depth 1 https://github.com/solitraderbusiness/tsetmc-mcp
for d in */; do git -C "$d" rev-parse HEAD; done

# بی‌مصرف‌بودن board وِ نبودِ بک‌اندِ اجرا/ربات (بندِ ۸ وِ ۹)
grep -rn "mstat/board" frontend/src | head
git ls-tree --name-only main -- api/ | grep -E "execution|bot"
git ls-tree --name-only mission/windows-stable-release-2026-10-15 -- api/ | grep -E "execution|bot"
git rev-list --left-right --count main...HEAD
```

**محدودیت‌هایِ اینِ سند:** شالو ⇒ بیِ تاریخچه/درift؛ هیچِ درخواستِ آزمایشی به upstream زده نشد (هیچِ endpointِ D یا E را خودمان تأیید نکردیم)؛ کدِ هیچِ مرجعی درِ BorsTerminal اجرا نشده؛ تصمیمِ حقوقیِ نهاییِ GPL/MIT باِ من نیست وِ فقطِ متنِ فایل‌ها گزارش شده است.
