# Deep Research: الگوهای AutoClicker در شش مرجع سرخطی

> تولید ۲۰۲۶-۱۰-۲۱ | عمق: deep | منابع: ۵۴ | قاعده: فقط شاهد و الگو، بدون کپی کد، بدون سفارش واقعی

## TL;DR

هیچ‌یک از شش مرجع، یک الگویِ اثبات‌شدهٔ «کلیکِ ایمن» ندارد: تنها مرجعِ زمان‌دار (`m-fazel/Sarkhati`) یک نمونهٔ NTP در شروع و یک RTT کامل از `HEAD` دارد و آن را هم دوباره همگام نمی‌کند؛ سه مرجع دیگر یا بازگشتی/۱۵باره کلیک می‌کنند یا کلاً زمان‌بند ندارند. برای راند ۱۴، پیش از هر قابلیت تازه، باید نشتیِ dry-run، تکرارِ سراسری، انتخابگرِ خرید/فروش و دروازهٔ ریسکِ مسیر مرورگر بسته شود و زمانِ هدف از تهران و تأخیرِ اندازه‌گیری‌شده بیاید. ادعای «بهترین زمان» و مجوزِ رباتِ خرد پشتوانهٔ رسمی ندارد؛ چهار مخزن بدون مجوز و دو مخزن فقط ادعای MIT در README دارند، پس هیچ کدی کپی نمی‌شود.

## Executive Summary

شش مخزن با سه معماری متفاوت بررسی شدند: دو کلاینتِ Rust با API مستقیم (`m-fazel`, `estakhri`)، دو ابزارِ Selenium/PyQt با کلیک روی DOM (`HosseinSayyedMousavi`, `sajadghandehari`) و دو ابزارِ TypeScript/Qt (`RezaMahdaviiDev`, `amirali110`). هیچ‌کدام به‌طور مستقل «امنیتِ یک کلیک» را حل نکرده‌اند. `m-fazel` تنها کسی است که برای لحظهٔ ارسال محاسبه دارد، اما محاسبه‌اش سه نقصِ بنیادی دارد: یک نمونهٔ NTP بدون همگام‌سازیِ دوره‌ای، کالیبراسیون با `HEAD` روی ریشهٔ دامنه به‌جای مسیر سفارش، و کم‌کردنِ یک RTT کامل به‌عنوان تأخیرِ یک‌طرفه. `HosseinSayyedMousavi` با timeoutِ یک‌ثانیه‌ای به‌صورت بازگشتی دوباره کلیک می‌کند و موفقیت را از toastِ بدون انتظار می‌خواند؛ این ترکیب، دقیقاً مولدِ سفارشِ تکراری است. `sajadghandehari` پانزده کلیک پشت‌سرهم می‌زند و ساعتِ ۱۲ساعته را با ساعتِ ۲۴ساعته مقایسه می‌کند، پس هدفِ بعد از ۱۲:۵۹ هرگز تطبیق نمی‌دهد. `RezaMahdaviiDev` نزدیک‌ترین مرجع از نظر UI است، ولی در `catch`ِ مسیر API به DOM برمی‌گردد و می‌تواند سفارشِ دوم بسازد؛ تأییدِ فرم و سفارشش هم فقط هشدار می‌دهد و ارسال را متوقف نمی‌کند. `amirali110` یک تایمرِ ۱ms دارد که تایمرِ دومش هرگز `start()` نمی‌شود و آدرس‌هایش ناقص‌اند.

در سمتِ خودمان، صفحهٔ `/autoclicker` راند ۱۳ یک کلیک، بررسیِ دوبارهٔ فرم و dry-runِ مبتنی بر intercept دارد؛ اما dry-run فقط وقتی امن است که الگویِ intercept با درخواستِ واقعی بخورد، قفلِ سراسریِ تکرار ندارد، انتخابگرهایش خریدمحورند، دروازهٔ ریسکِ مسیر مرورگر سطحی است، `status:"scheduled"` را در UI خطا می‌خواند و زمانِ هدف را با منطقهٔ زمانیِ مرورگر می‌سازد. هیچ اندازه‌گیریِ زندهٔ «کلیک تا POST» هم نداریم. پیشنهادِ راند ۱۴ در بخش ۴ به همین ترتیب اولویت‌بندی شده است.

## ۱. وضعیتِ موجود [Confidence: High]

### ۱.۱ جدولِ مقایسهٔ شش مرجع

| مخزن | انتقال | کلیک/DOM | زمان | نرخ/تکرار | تأییدِ سفارش | مجوز |
| --- | --- | --- | --- | --- | --- | --- |
| `m-fazel/Sarkhati` | API مستقیم EasyTrader | ندارد | NTP یک‌بار + `HEAD` | batch موازی، بدون قفلِ تکرار | فقط HTTP 2xx | فایل ندارد؛ README ادعای MIT |
| `estakhri/Sarkhati` | API مستقیم مفید | ندارد | ندارد | spawnِ دسته‌ای، بدون انتظار | فقط HTTP 2xx | فایل ندارد؛ README ادعای MIT |
| `HosseinSayyedMousavi/Sarkhati` | Selenium | XPath مطلق | حلقهٔ `QTime` بدون خوابِ اولیه | تکرار تا موفقیت، بازگشتی | toast + جدول، بدون order-id | ندارد |
| `sajadghandehari/mofid-autotrader` | Selenium | XPath | مقایسهٔ رشتهٔ ساعت، هر ۱s | ۱۵ کلیک | ندارد | ندارد |
| `RezaMahdaviiDev/mofid` | Playwright + API | `data-cy` | ندارد | ۱۰۰ms rate limiter، مانیتور ۵s×۶۰ | لیست سفارش، ولی غیرمسدودکننده | فایل ندارد؛ `package.json` ادعای ISC |
| `amirali110/Sarkhati-Bourse` | Qt/HTTP ناقص | QTimer | ۱ms، تایمرِ هدف `start()` نمی‌شود | فیلد repeat بی‌استفاده | ندارد | ندارد |

اصلِ مشترکِ هر شش مخزن: «کلیک» یا `POST` یک عملِ یک‌طرفه است و هیچ‌کدام یک قفلِ پایدارِ «یک سفارش برای یک قصد» ندارند. این نه یک نقصِ جزئی، بلکه شکافِ اصلیِ طراحی است [1]–[27].

### ۱.۲ شرحِ مرجع‌به‌مرجع

**m-fazel/Sarkhati — تنها زمان‌بندِ واقعی، با سه خطای محاسباتی.** این مخزن Rust برای EasyTrader یک لایهٔ زمان دارد: `time_reference.rs` یک نمونهٔ NTP در شروع می‌گیرد و در صورتِ خطا offset را صفر می‌گذارد [4]؛ `calibration.rs` با `HEAD` روی `scheme://host` چند نمونهٔ RTT می‌گیرد و p50/p75/p90/EWMA می‌سازد [3]؛ `main.rs` لحظهٔ ارسال را `target − (RTT + margin)` می‌گذارد [2]. سه اشکال: NTP با `OnceLock` فقط یک‌بار تنظیم می‌شود و هیچ بازهمگام‌سازی ندارد؛ `HEAD` روی ریشهٔ دامنه وضعیتِ HTTP را نمی‌سنجد و مسیرِ سفارش را لمس نمی‌کند؛ و کم‌کردنِ کلِ RTT به‌جای تأخیرِ یک‌طرفه، ارسال را زودتر از لازم می‌فرستد. بدتر: `batch_repeat` چند futureِ موازی با فاصلهٔ ثابت می‌سازد و `join_all` آن‌ها را هم‌زمان اجرا می‌کند [2]؛ هیچ کلیدِ idempotency، read-backِ order-id یا توقفِ تکرار وجود ندارد. موفقیت فقط `2xx` است و بدنهٔ خطا هم «موفق» ثبت می‌شود [1]. `test_mode` در عمل سفارش می‌فرستد و فقط حالتِ `curl` ارسال را متوقف می‌کند؛ توکن و هدرِ Authorization در لاگ چاپ می‌شوند [1][2][6].

**estakhri/Sarkhati — پروتکلِ متفاوت، بدون زمان.** این مخزن برای مفید/Titan است، نه EasyTrader: `POST /apigateway/api/v1/Order/send` با فیلدهایِ رشته‌ای `orderSide` و `orderFrom` [8]. هیچ NTP، کالیبراسیون یا زمانِ هدفی ندارد؛ تنها استفادهٔ ساعت، ساختنِ هدرِ `X-App-N` از UTC منهای دو ثانیه است [9]. دسته‌ها با `tokio::spawn` موازی می‌شوند و `sleep(batch_delay)` بدونِ await کردنِ درخواست‌ها اجرا می‌شود [7]. نتیجه: هم‌پوشانیِ دسته‌ها و بی‌نظمیِ نرخ. تأییدِ سفارش فقط status است و پاسخِ خام چاپ می‌شود [8].

**HosseinSayyedMousavi/Sarkhati — کلیک با XPathِ شکننده و بازگشتِ بازگشتی.** این ابزار PyQt + Selenium فرمِ کارگزاری را با XPathهایِ مطلق مثل `/html/body/.../send-order/...` می‌زند [11]. قبل از کلیک فقط ۱ ثانیه `visibility_of_element_located` صبر می‌کند و در timeout، تابعِ `Transaction()` را بازگشتی صدا می‌زند [11]. بعد از کلیک، toastِ موفقیت را بدونِ هیچ انتظاری با `find_element` می‌خواند؛ اگر toast هنوز رندر نشده باشد، «ناموفق» ثبت می‌کند و حلقه دوباره کلیک می‌کند [11]. جدولِ سفارش را با تطبیقِ زیررشتهٔ نماد، سمت، قیمت و تعداد می‌خواند و اولین ردیف را می‌پذیرد؛ order-id ندارد [11]. CAPTCHA کاملاً دستی است [13] و رمز در UI می‌ماند. این مخزن همچنین یک شمارهٔ موبایل را در ثابتِ عنوانِ پنجره دارد که در این گزارش بازنشر نمی‌شود.

**sajadghandehari/mofid-autotrader — پانزده کلیک و ساعتِ ناسازگار.** `manage.py` هر ۱ ثانیه `datetime.now().strftime("%H:%M:%S")` را با رشته‌ای مقایسه می‌کند که با `toString("hh:mm:ss")` ساخته شده است؛ `hh` در Qt ساعتِ ۱۲ساعته است، پس هر هدفِ بعد از ۱۲:۵۹ هرگز برابر نمی‌شود [14]. در لحظهٔ تطبیق، `range(15)` کلیکِ خرید و ارسال می‌زند [14]. تعداد را کاربر از قبل در حسابِ مفید تنظیم می‌کند و فیلدِ تعدادِ Qt بی‌استفاده می‌ماند [14][16]. CAPTCHA دستی است و هیچ reconcile یا order-id وجود ندارد.

**RezaMahdaviiDev/mofid — نزدیک‌ترین مرجع، با خطرِ دوبار ارسال.** این مخزن دو مسیر دارد: DOM با Playwright و API مستقیم؛ مدلِ `all` هر دو را پشتِ سرِ هم امتحان می‌کند [17][19]. انتخابگرها `data-cy` هستند (`order-form-input-price`, `oms-order-form-submit-button-buy`, `order-buy-btn`) و برای پیدا کردنِ دکمه ۵ بار با فاصلهٔ ۸۰۰ms تلاش می‌شود [17]. اما کلیک با `force:true` است و وضعیتِ enabled/stable را در لحظهٔ کلیک نمی‌سنجد [17]. مهم‌تر: مسیر API در `catch` به `executeFastBuy` روی DOM برمی‌گردد؛ اگر پاسخِ API گم شود ولی سفارش ثبت شده باشد، این fallback سفارشِ دوم می‌سازد [19]. تأییدِ قیمت/تعداد فقط `console.warn` می‌کند و ارسال ادامه می‌یابد؛ تطبیقِ نماد حتی به ISINِ هاردکدشدهٔ یک نمادِ دیگر برمی‌گردد [17][18]. rate limiter یک صفِ FIFO با فاصلهٔ ۱۰۰ms (۱۰ درخواست بر ثانیه) است [22]، مانیتور صف هر ۵ ثانیه تا ۶۰ بار [21]، و توکن در `token-cache.json` روی دیسک با TTLِ دو ساعت ذخیره می‌شود [23]. داشبورد یک صفحهٔ ساده با فرم، وضعیتِ ثابتِ «آماده برای خرید»، جدولِ نتیجه و لاگ است [24]؛ نه زمان‌بند دارد و نه دروازهٔ آمادگیِ واقعی.

**amirali110/Sarkhati-Bourse — تایمرِ بی‌اثر.** `mainwindow.cpp` یک `QTimer` با فاصلهٔ ۱ms دارد که ساعت را با زمانِ کاربر مقایسه می‌کند؛ وقتی هدف می‌گذرد، تایمر را متوقف و یک `QTimer` تازه برای ارسال می‌سازد، ولی آن را هرگز `start()` نمی‌کند [26]. آدرس‌ها ناقص‌اند (`https://com/Web/V1/Order/Post`) و هیچ احرازِ واقعی دیده نمی‌شود [26]. این مخزن بیشتر «درسِ منفی» است: تایمرِ ۱ms روی ویندوز با tickِ پیش‌فرضِ ۱۵٫۶۲۵ms عملاً دقتِ میلی‌ثانیه ندارد [44][45].

### ۱.۳ وضعیتِ خودمان پس از راند ۱۳

صفحهٔ `/autoclicker` یک کلیک و بررسیِ دوبارهٔ فرم دارد، اما تضمین‌هایش از آنچه UI نشان می‌دهد کمتر است:

- **Probe ناقص است.** `probe` ساختار صفحه را می‌خواند ولی `form_symbol_selector` و `open_form_selector` را اصلاً بررسی نمی‌کند (`execution_strategy_engine.py:284-289`، `:291-364`) و صفحه هم `structure.buttons/inputs` را نمایش نمی‌دهد (`AutoClickerPage.tsx:299-303`).
- **Prepare فرم را باز می‌کند، ولی هیچ تایمری مسلح نمی‌کند.** `open_form_selector` کلیک می‌شود، `_verify_form` اجرا می‌شود و ساعتِ کارگزار snapshot می‌شود؛ `require_prefilled` فقط ثبت می‌شود و اجرا نمی‌شود (`execution_strategy_engine.py:457-492`). از طریق API می‌توان `autofill=true` فرستاد و فرم را پر کرد؛ صفحه این کار را نمی‌کند ولی سرویس جلوی آن را هم نمی‌گیرد.
- **Trigger در dry-run همیشه `live=False` است** (`api/execution.py:1115-1151`). اگر هدف بیش از ۲۵۰ms دور باشد، `scheduled` برمی‌گردد و یک threadِ daemon تا لحظهٔ هدف می‌خوابد (`api/execution.py:1129-1142`).
- **زمان‌بند، `one_way_ms` و `margin_ms` را صفر می‌گیرد** (`execution_strategy_engine.py:1121-1130`؛ `execution_timing.py:300-351`). یعنی حتی وقتی زمان‌بند درست کار کند، کلیک پس از چند round-tripِ Playwright (بررسیِ فرم، intercept، preclick) انجام می‌شود و POST بعد از T0 می‌رسد، نه در T0.
- **یک کلیک واقعی وجود دارد** (`execution_strategy_engine.py:710-719`) و تستِ async-change نشان می‌دهد تغییرِ قیمت/تعداد/نماد پیش از کلیک گرفته می‌شود (`dev/strategy_guard_v1123.py:537-552`). اما تستی وجود ندارد که تعدادِ کلیک را بشمارد؛ MockDriver همیشه `wait_for=True` و `is_enabled=True` برمی‌گرداند (`execution_browser.py:160-179`)، پس کنترل‌جریان اثبات می‌شود، نه رفتارِ واقعیِ دکمه.
- **قفلِ تکرار فقط در سطحِ intent است.** `IntentArbiter` هر `execution_id` را یک‌بار می‌پذیرد (`execution_strategy_core.py:384-401`)، ولی UI برای هر بار `ac-${Date.now()}` می‌سازد (`AutoClickerPage.tsx:138-143`)؛ دو prepare روی یک فرم، دو intent است و قفلِ سراسری وجود ندارد.
- **دروازهٔ ریسک روی مسیر مرورگر سطحی است.** `post_strategy_dispatch` فقط چک می‌کند که «یک» سقف تنظیم شده باشد و بعد مستقیم موتور را صدا می‌زند؛ `ExecutionService.preflight/execute` صدا زده نمی‌شود (`api/execution.py:335-352`). یعنی سقفِ ارزش و سقفِ هر نماد روی کلیکِ AutoClicker اعمال نمی‌شود.
- **dry-run به الگویِ intercept وابسته است.** کلیک واقعی است و فقط درخواستِ منطبق با `intercept_pattern` abort می‌شود (`execution_strategy_engine.py:556-563`, `:655-660`). اگر URLِ واقعیِ سفارش با الگو نخورد، POST می‌تواند از dry-run بیرون بزند و موتور `failed/NO_ORDER_REQUEST` گزارش کند.
- **`status:"scheduled"` در UI خطا خوانده می‌شود.** صفحه هر پاسخِ غیر از `success` را ناموفق می‌داند (`AutoClickerPage.tsx:160-164`)، در حالی که مسیر برای هدفِ آینده `scheduled` برمی‌گرداند (`api/execution.py:1140-1142`).
- **زمانِ هدف منطقه‌محور نیست.** `Date.parse(datetime-local)` از منطقهٔ زمانیِ مرورگر استفاده می‌کند (`sarkhatiFormStore.ts:88-92`)؛ `TimeSource.to_target_wall_ms` تهران‌آگاه وجود دارد ولی در مسیر استراتژی استفاده نمی‌شود (`execution_timing.py:100-115`).
- **دروازهٔ آمادگیِ سرور به صفحه وصل نیست.** `/api/execution/readiness` با ورودی‌هایِ ثابت `contract_operational=False` و `owner_approved=False` ساخته می‌شود (`api/execution.py:2090-2101`)؛ چیپ‌های صفحه هفت شرطِ محلی‌اند (`AutoClickerPage.tsx:82-97`)، نه خروجیِ آن endpoint.
- **پشتیبانی از دیالوگ نیست.** `execution_browser.py` فقط listenerهایِ request/response دارد؛ هندلرِ `dialog` ندارد. یک confirm مرورگری با رفتارِ پیش‌فرض Playwright ممکن است رد شود.

## ۲. الگوهایِ تکرارشونده [Confidence: Medium]

**۲.۱ شناختِ دکمه: از XPathِ مطلق به actionability.** دو مرجعِ Selenium با XPathهایِ مطلق کار می‌کنند و هیچ‌کدام وضعیتِ «قابلِ کلیک بودن» را کامل نمی‌سنجند [11][14]. Reza با `data-cy` جلوتر است، ولی `force:true` بخشی از بررسی‌ها را دور می‌زند [17]. تنها الگویِ مستند و قابلِ دفاع، actionabilityِ Playwright است: یک عنصرِ یگانه، visible، stable، receives-events و enabled [30]. `force:true` این‌ها را «غیرضروری» می‌کند و به‌طور مشخص بررسیِ دریافتِ رویداد را دور می‌زند [30]. برای فرمِ EasyTrader که SPA است و ممکن است دوباره رندر شود، بررسیِ state-based بهتر از `sleep` است؛ چون locator دوباره resolve می‌شود، نه اینکه handleِ کهنه کلیک شود [30].

**۲.۲ زمان: هیچ مرجعی «بهترین زمان» را اثبات نکرده است.** `m-fazel` تنها کسی است که تلاشِ جدی دارد [2][3][4]، ولی کالیبراسیونش یک RTT کامل را کم می‌کند، `HEAD` را به ریشهٔ دامنه می‌زند و NTP را بازهمگام نمی‌کند. سه مرجع دیگر یا حلقهٔ مقایسهٔ ساعت دارند [11][14][26] یا هیچ [7][17]. در سمتِ منابعِ معتبر، NTPِ اینترنت فقط «چند میلی‌ثانیه» دقت دارد و LAN «ده‌ها میکروثانیه» [33]؛ `performance.now()` یکنواست و در زمینهٔ غیرایزوله دقتش حدودِ ۱۰۰ میکروثانیه است [32]. تایمرهایِ تبِ پنهان به حدودِ یک بار در ثانیه محدود می‌شوند و از Chrome 88 تایمرهایِ زنجیره‌ای پس از پنج دقیقهٔ پنهان‌شدن به حدودِ یک بار در دقیقه می‌رسند [34][35][36]. پس «کلیکِ میلی‌ثانیه‌ای» با `setTimeout` در تبِ پس‌زمینه ادعایِ نادرستی است.

**۲.۳ نرخ و تکرار: rate limiter مسئلهٔ تکرار را حل نمی‌کند.** Reza یک صفِ FIFO با فاصلهٔ ۱۰۰ms دارد [22]، `m-fazel` یک mutex با حداقلِ فاصله [5]، و Sarkhati یک خوابِ پس از تلاش با بازهٔ ۱۰۰ تا ۱۰۰٬۰۰۰ms [12]. هیچ‌کدام کلیدِ idempotency یا قفلِ «یک سفارش برای یک قصد» ندارند. الگویِ بالغِ بیرونی، کلیدِ idempotencyِ Stripe است: کلید برای دست‌کم ۲۴ ساعت نگه داشته می‌شود و تلاشِ دوباره با همان کلید پاسخِ ذخیره‌شده را برمی‌گرداند، نه شیءِ دوم [37]. فرمِ EasyTrader هیچ مکانیزمِ مستندی برایِ چنین کلیدی ندارد؛ پس at-most-once فقط با قفلِ پایدارِ محلی و read-backِ بعد از ارسال قابلِ ادعاست، و اگر بین ارسال و ثبت کرش شود، وضعیت UNKNOWN است و نباید کورکورانه تکرار شود.

**۲.۴ صفحهٔ تنظیمات و آمادگی: مرجع، «آمادگیِ نمایشی» دارد.** داشبوردِ Reza یک صفحهٔ ساده با فرم، وضعیتِ ثابتِ «آماده برای خرید»، جدولِ نتیجه و لاگ است [24]. «آماده برای خرید» متنِ هاردکد است و تنها حالت‌های زنده، idle/loading/success/errorِ fetch هستند [24]. صفحهٔ ما از آن جلوتر است (هفت دروازه، Probe، dry-run با تأییدِ صریح)، ولی دروازه‌هایش محلی‌اند و به readinessِ سرور وصل نیستند (`api/execution.py:2090-2101`؛ `AutoClickerPage.tsx:82-97`). الگویِ درست، circuit breaker است: هر شکستِ preflight مدار را باز کند و «مسلح‌نشدن» را صریح نشان دهد، نه اینکه کلیک را تکرار کند [38].

**۲.۵ ایمنی: کنترلِ پیش از معامله و kill switch، نه امید به سرعت.** SEC Rule 15c3-5 و متنِ FINRA چارچوبِ رسمیِ کنترلِ پیش از معامله و امکانِ قطعِ دسترسیِ خودکار را توصیف می‌کنند [39][40]؛ این قاعده بر کارگزار حاکم است، نه بر ابزارِ خرد، ولی منطقش قابلِ اقتباس است: سقفِ ارزش، سقفِ تعداد، امکانِ توقف، و ثبتِ تصمیم. در سمتِ لاگ، هیچ‌یک از مراجع نباید الگو باشد: `m-fazel` توکن و Authorization را چاپ می‌کند [1][2]، `estakhri` کوکی و بدنه را [7][8]، و Reza توکن را روی دیسک می‌نویسد [23].

## ۳. ارزیابیِ انتقادی [Confidence: High]

### ۳.۱ جدولِ الگوهایِ شکست

| الگو | شاهد | پیامد | وضعیتِ ما |
| --- | --- | --- | --- |
| timeoutِ کوتاه + بازگشتِ بازگشتی | `Sarkhati.py:386-391` [11] | کلیکِ دوم روی فرمِ کند | نداریم؛ بررسی دوباره پیش از کلیک داریم |
| toastِ بدون انتظار | `Sarkhati.py:419` [11] | «ناموفق» کاذب و تکرار | نداریم؛ نتیجه از request/response می‌آید |
| ۱۵ کلیکِ پشت‌سرهم | `manage.py:129-140` [14] | سفارشِ تکراریِ عمدی | یک کلیک داریم، ولی قفلِ سراسری نداریم |
| ساعتِ ۱۲ساعته در برابر ۲۴ساعته | `manage.py:85,125` [14] | هدفِ بعد از ۱۲:۵۹ هرگز اجرا نمی‌شود | منطقهٔ زمانیِ مرورگر و نبودِ اعتبارسنجیِ آینده |
| fallback از API به DOM | `buyActionAPI.ts:231-234` [19] | سفارشِ دوم وقتی پاسخ گم شود | مسیر API/مرورگر جدا است؛ ولی UNKNOWN باید قفل کند |
| force click | `buyActionUltra.ts:523` [17] | کلیک روی دکمهٔ غیرفعال/پوشیده | `.first` و انتخابگرِ صفحه‌ای داریم |
| انتخابگرِ خرید برای فروش | `execution_strategy_core.py:67-70` | کلیکِ اشتباه یا بلاک | انتخابگرِ side-aware نداریم |
| dry-run وابسته به الگو | `execution_strategy_engine.py:556-563` | نشتیِ POST در صورتِ عدمِ تطبیق | همین ریسک را داریم |
| دروازهٔ ریسکِ سطحی | `api/execution.py:335-352` | عبور از سقفِ ارزش/نماد | همین شکاف را داریم |
| توکن/هدر در لاگ یا دیسک | [1][2][7][8][23] | نشتِ نشست | الگو را تکرار نمی‌کنیم |
| تایمرِ ۱ms بدون `start` | `mainwindow.cpp:116-121` [26] | هدف هرگز اجرا نمی‌شود | تایمرِ واقعی داریم، ولی compensation نداریم |
| threadِ مشترک روی WebDriver | `Sarkhati.py:403-414` [11] | رفتارِ نامعین | تک‌threadیم |

### ۳.۲ مجوز: تصحیحِ مهم نسبت به راند ۱۱A

ممیزیِ راند ۱۱A گفته بود «هیچ‌یک از شش مخزن مجوز ندارد». بررسیِ عمیق‌تر نشان می‌دهد این جمله برای همهٔ شش مخزن دقیق نیست: `m-fazel/Sarkhati` و `estakhri/Sarkhati` در README ادعایِ «MIT» دارند [6][10]، ولی هیچ فایلِ `LICENSE`/`COPYING` در درختِ commitِ pin‌شده نیست و endpointِ مجوزِ GitHub هم ۴۰۴ می‌دهد [28]. چهار مخزنِ دیگر هیچ ادعایِ مجوزی هم ندارند [28]. طبقِ مستندِ GitHub، نبودِ مجوز یعنی حقوقِ پیش‌فرض و ممنوعیتِ بازتوزیع/اثرِ مشتق [29]. ادعایِ یک‌کلمه‌ایِ MIT در README هم متنِ مجوز را همراه ندارد؛ بنابراین آن را «مجوزِ قطعی» نمی‌دانیم. نتیجهٔ عملی برای راند ۱۴ تغییر نمی‌کند: **همهٔ شش مخزن فقط مرجعِ رفتاری‌اند و هیچ کد، کامنت یا شِمای‌شان کپی نمی‌شود.**

### ۳.۳ مجوزِ فعالیت و زمانِ بازار: ادعاهایِ تأییدنشده

هیچ سندِ اولیه‌ای از TSETMC/TSE/SEO برایِ زمان‌بندیِ معاملات در بودجهٔ این تحقیق به‌دست نیامد. ساعتِ ۸:۴۵ تا ۹:۰۰ به‌عنوانِ «پیش‌گشایش» در صفحهٔ آموزشیِ کارگزاری مفید و چند رسانهٔ مالی تکرار شده است [47][48]، ولی سندِ رسمیِ آن دیده نشد و زمان‌بندی به نوعِ ابزار بستگی دارد (مثلاً یک کلاسِ صندوق تا ۱۵:۰۰ معامله می‌شود) [48]. هیچ منبعی «بهترین لحظه» را تعریف نکرده است؛ ۸:۴۵ فقط شروعِ پنجرهٔ ثبتِ سفارش است و دربارهٔ اولویتِ میلی‌ثانیه‌ای در حراجِ پیش‌گشایش سندی نداریم.

در سمتِ قانونی، خبرِ مهر از اطلاعیهٔ ۱۲۲۴۰۹/۱۲۱ و بندِ ۱۰ صورت‌جلسهٔ ۶۱۹ می‌گوید ارائهٔ خدماتِ معاملاتِ الگوریتمی برای **مؤسساتِ دارای مجوز** با هشت شرط مجاز است [49]. این چارچوب به کارگزار/مؤسسه خطاب دارد، نه به مشتریِ خرد که فرمِ وبِ کارگزار را کلیک می‌کند. پورتالِ رسمیِ SEO هم فقط زمینهٔ نظارتی را نشان می‌دهد [50]. سندِ «الزاماتِ معاملاتِ الگوریتمی» در یک میزبانِ کارگزاری پیدا شد، ولی PDFِ اسکن‌شده قابلِ استخراج نبود و متنش را نقل نمی‌کنیم [51]. **بنابراین مجوز یا ممنوعیتِ AutoClicker برای مشتریِ خرد UNVERIFIED است**؛ و هیچ کارگزارِ خاصی را نمی‌توان «مجازکننده» یا «ممنوع‌کننده» توصیف کرد. تبلیغاتِ فروشِ رباتِ سرخطی [52][53] وجودِ بازارِ خاکستری را نشان می‌دهد، نه مجوز را.

### ۳.۴ اندازه‌گیری: چیزی که هیچ مرجعی ندارد

هیچ‌کدام از شش مخزن، تأخیرِ «کلیک تا رسیدنِ POST به کارگزار» را اندازه نمی‌گیرند. `m-fazel` یک RTTِ `HEAD` را کم می‌کند [2][3]، ولی این عدد نه یک‌طرفه است، نه مسیرِ سفارش را می‌سنجد و نه توزیعِ p95 را در لحظهٔ ارسال نگه می‌دارد. Reza زمان‌ها را با `Date.now()` می‌گیرد [17] که یکنوا نیست. ما هم `one_way_ms` را صفر می‌دهیم (`execution_strategy_engine.py:1121-1130`). تا وقتی این عدد در محیطِ خودِ کاربر اندازه‌گیری نشود، هر ادعایی دربارهٔ «بهترین زمان» یا «دقتِ میلی‌ثانیه» بی‌پشتوانه است.

### ۳.۵ نقدِ رقیب: چرا اصلاً کلیک؟

منتقدِ سخت‌گیر می‌گوید: اگر مسیرِ API با order-id و reconcile وجود دارد [19][21]، ساختنِ AutoClicker رویِ DOM یک ریسکِ ساختاری است، نه یک قابلیت. در کلیک، بینِ «تأییدِ فرم» و «کلیک» همیشه یک پنجرهٔ TOCTOU هست؛ فرمِ SPA می‌تواند در همان چند میلی‌ثانیه دوباره رندر شود، قیمت/تعداد عوض شود یا دکمه غیرفعال گردد. هیچ مرجعی این پنجره را نبسته است و Playwright هم فقط actionability را در لحظهٔ عمل بررسی می‌کند، نه اتمیک‌بودنِ تصمیم و ارسال [30]. علاوه بر این، کلیک به DOMِ کارگزار وابسته است؛ یک تغییرِ `data-cy` کلِ زنجیره را می‌شکند، در حالی که قراردادِ API با یک نسخهٔ مستند پایدارتر است. از نظرِ حقوقی هم نمی‌توان «مجاز بودن» را ادعا کرد [49][50]، و از نظرِ زمان‌بندی، دقتِ واقعیِ ارسال در محیطِ کاربر هنوز اندازه‌گیری نشده است.

پاسخِ این نقد هم روشن است: برایِ کارگزارانی که APIِ نوشتنِ مستند ندارند، کلیک تنها راهِ باقی‌مانده است؛ و مالک صریحاً خواسته که قیمت/تعداد را خودش در فرمِ کارگزاری بزند. اما این پاسخ، AutoClicker را «مسیرِ اصلی» نمی‌کند. نتیجهٔ طراحی این است که کلیک باید fallbackِ محدود و قابلِ خاموش‌شدن باشد، نه جایگزینِ API؛ هر دو مسیر باید preflight و قفلِ تکرارِ مشترک داشته باشند؛ و تا وقتی مالک دربارهٔ مجوز، آستانه‌هایِ امنیتی و زمانِ هدف حکم نداده، صفحه در حالتِ shadow/dry-run بماند. این نقد در برنامهٔ عمل به‌صورتِ P2-5 (اولویتِ API) و P0-1 تا P0-4 (بستنِ شکاف‌هایِ کلیک) بازتاب دارد.

## ۴. برنامهٔ عمل برای راند ۱۴

اولویت‌ها بر اساسِ «چه چیزی می‌تواند سفارشِ ناخواسته بسازد» مرتب شده‌اند، نه بر اساسِ جذابیتِ قابلیت. هیچ آیتمی مجوزِ سفارشِ واقعی نیست و `live_enabled`/`live_ready` باید بسته بماند.

### P0 — بستنِ شکاف‌هایِ ایمنی (پیش از هر قابلیتِ تازه)

- [ ] **P0-1: dry-run را قطعی و قابلِ اثبات کن.** به‌جای globِ قابلِ‌تنظیم، predicateِ متد+میزبان+مسیر (`POST` و `/core/api/v2/order`) را در intercept بگذار؛ بعد از کلیک، اگر درخواستی دیده نشد ولی شاهدِ شبکه‌ایِ خروجی وجود داشت، نتیجه را `ESCAPED_REQUEST` بکن و فوراً متوقف شو. یک تستِ محلی با URLِ طعمه اضافه کن که ثابت کند POSTِ غیرمنطبق بیرون نمی‌زند. مرجع: `execution_strategy_engine.py:556-563`, `:642-660`؛ [30].
- [ ] **P0-2: قفلِ سراسریِ «یک قصد، یک سفارش».** یک latchِ پایدار در `user.db` با کلیدِ هشِ (نماد/ISIN، سمت، قیمت، تعداد، زمانِ هدف، اثرِ انگشتِ فرم) بساز؛ هر prepare یا triggerِ دوم با همان کلید رد شود؛ وضعیتِ UNKNOWN تا reconcileِ موفق، هر ارسالِ بعدی را مسدود کند. قفلِ فعلی فقط در سطحِ `execution_id` است و دو `ac-${Date.now()}` را نمی‌بیند (`execution_strategy_core.py:384-401`؛ `AutoClickerPage.tsx:138-143`). الگویِ idempotency [37].
- [ ] **P0-3: انتخابگرهایِ side-aware و یگانه.** انتخابگرهایِ بازکردن و ارسال برای خرید و فروش جدا شوند؛ دکمه باید داخلِ کانتینرِ فرم و دقیقاً یک عنصر باشد؛ `.first`ِ صفحه‌ای حذف شود. الان پیش‌فرض‌ها خریدمحورند (`execution_strategy_core.py:67-70`) و `_verify_form` سمت را مقایسه نمی‌کند (`execution_strategy_engine.py:399-426`). بررسیِ نهایی باید visible+stable+enabled باشد، نه `force` [30].
- [ ] **P0-4: دروازهٔ ریسک رویِ مسیرِ مرورگر.** پیش از هر کلیکِ live، `ExecutionService.preflight` (قدرتِ خرید/فروشِ قابلِ فروش، سقفِ ارزش، سقفِ هر نماد) صدا زده شود و نتیجهٔ `blocking` کلیک را متوقف کند. الان `_risk_gate` فقط وجودِ «یک» سقف را چک می‌کند و `preflight/execute` را صدا نمی‌زند (`api/execution.py:335-352`). readinessِ سرور هم باید ورودیِ واقعی بگیرد، نه `contract_operational=False`ِ ثابت (`api/execution.py:2090-2101`؛ `execution_readiness.py:151-163`).
- [ ] **P0-5: معناشناسیِ `scheduled` و abort.** UI باید `status:"scheduled"` را «زمان‌بندی شد» نشان دهد، نه خطا؛ abort باید تایمرِ خوابیده را بیدار کند و نتیجهٔ صریح `aborted` ثبت شود؛ مسیرِ liveِ زمان‌بندی‌شده نباید در صورتِ شکستِ تأیید، بی‌صدا برگردد (`AutoClickerPage.tsx:160-164`؛ `api/execution.py:1129-1193`).
- [ ] **P0-6: زمانِ هدف از تهران.** `datetime-local` مرورگر را به یک timestampِ تهران‌آگاه تبدیل کن (سرور)، هدفِ گذشته را با تلورانسِ مشخص رد کن، و منطقهٔ زمانی را در پاسخ برگردان. الان `Date.parse` از منطقهٔ مرورگر می‌آید (`sarkhatiFormStore.ts:88-92`) و `to_target_wall_ms`ِ تهران‌آگاه بی‌استفاده است (`execution_timing.py:100-115`).

### P1 — اندازه‌گیری و شناختِ درست (پیش از ادعای «بهترین زمان»)

- [ ] **P1-1: تأخیرِ «کلیک تا POST» را اندازه بگیر.** با رویدادهایِ request/responseِ Playwright یا `performance`، برای هر اجرا t_click، t_request_start و t_response را ثبت کن و p50/p95 را در گزارشِ همان نشست نگه دار. `one_way_ms` را از همین عدد به `Scheduler.plan` بده. الان زمان‌بند `one_way=0` و `margin=0` می‌گیرد و کلیک بعد از چند round-trip می‌افتد (`execution_strategy_engine.py:1121-1130`؛ `execution_timing.py:300-351`). تا اندازه‌گیری نشود، هیچ عددِ میلی‌ثانیه‌ای در UI نوشته نشود [32][43].
- [ ] **P1-2: آفستِ ساعتِ کارگزار را چندنمونه‌ای کن.** snapshotِ فعلی در prepare فقط یک مقدار است و گیتِ زندهٔ ۱۵۰۰ms دارد (`execution_strategy_engine.py:366-394`, `:523-544`). پیش از مسلح‌شدن، چند نمونه با میانه/حداقل بگیر، drift را ثبت کن و در نتیجه نشان بده. به NTPِ سیستم به‌عنوانِ منبعِ حقیقت تکیه نکن؛ دقتِ اینترنت چند میلی‌ثانیه است [33][32].
- [ ] **P1-3: تأییدِ پس از کلیک.** پاسخِ همان POST را بگیر و `id`/`orderState` را ثبت کن؛ اگر پاسخ نرسید، `UNKNOWN` بمان و هیچ fallback یا کلیکِ دوباره‌ای نزن. reconcile فقط با ISIN/سمت/قیمت/تعدادِ یگانه انجام شود (`execution_strategy_engine.py:642-692`, `:1194-1252`). الگویِ «2xx ≠ پذیرش» را در UI صریح نگه دار.
- [ ] **P1-4: Probe را کامل کن.** `form_symbol_selector` و `open_form_selector` را هم بسنج؛ تعدادِ تطبیقِ هر انتخابگر را برگردان؛ ساختارِ دکمه‌ها/ورودی‌ها را بدونِ مقدار نمایش بده. الان Probe این دو را نمی‌بیند (`execution_strategy_engine.py:284-289`) و صفحه ساختار را پنهان می‌کند (`AutoClickerPage.tsx:299-303`).
- [ ] **P1-5: سیاستِ فاصله و سقف را با مالک تعیین کن.** برای طراحیِ «یک کلیک»، فاصلهٔ بین کلیک‌ها بی‌معناست؛ آنچه لازم است cooldownِ بینِ intentهایِ جداگانه و سقفِ ساعتی/روزانه است. هیچ عددی را خودسرانه در کد نگذار؛ عددِ پیشنهادی را از اندازه‌گیری بگیر و برایِ حکمِ مالک ارائه کن [37][38]. سقفِ فعلی `BORS_EXECUTION_MAX_ORDERS_TOTAL` اختیاری و تنها در مسیرِ live است (`execution_strategy_engine.py:853-855`, `:1110-1119`).
- [ ] **P1-6: تستِ واقعیِ مرورگر با EasyTraderِ تقلبیِ محلی.** یک صفحهٔ محلی با همان `data-cy`ها بساز و این‌ها را بشمار: تعدادِ کلیک (باید ۱)، انتخابگرِ خرید/فروش، فرمِ کهنه، دکمهٔ غیرفعال، `scheduled`، abort، و URLِ طعمه در dry-run. تست‌هایِ فعلی MockDriver دارند که همیشه `wait_for=True` برمی‌گرداند (`execution_browser.py:160-179`)؛ برایِ همین رفتارِ دکمه را اثبات نمی‌کنند [41][42].
- [ ] **P1-7: نمایشِ یک وضعیت، یک اقدام.** نتیجهٔ Probe/آمادگی را پشتِ یک expander بگذار و بالای صفحه فقط یک وضعیت و یک اقدامِ بعدی نشان بده؛ اعدادِ اندازه‌گیری (offset، p95، drift) در همان expander. این با الگویِ UI خودمان و بازخوردِ مالک هم‌راستاست.

### P2 — تصمیم‌هایِ مالک و مستندسازی

- [ ] **P2-1: تصحیحِ سندِ مجوز و ثبتِ قاعده.** در `docs/SARKHATI-GITHUB-REFERENCE-AUDIT.md` جملهٔ «هیچ‌یک مجوز ندارد» به «چهار مخزن بدون مجوز؛ دو مخزن ادعایِ MIT در README بدون فایلِ مجوز» اصلاح شود. تصمیمِ کپی همچنان «هیچ» است. [28][29]
- [ ] **P2-2: سیاستِ «بهترین زمان» بدونِ ادعایِ بی‌شاهد.** ۸:۴۵ را در کد هاردکد نکن؛ پنجرهٔ پیش‌گشایش را به‌عنوانِ دادهٔ دارایِ منبع و وابسته به نوعِ ابزار نمایش بده و برچسبِ UNVERIFIED بزن تا سندِ رسمی پیدا شود [47][48]. اگر مالک زمانی را حکم کند، همان در تنظیمات بیاید، نه در منطقِ پنهان.
- [ ] **P2-3: ثبتِ وضعیتِ حقوقی.** هیچ سندِ رسمی برایِ مجوز/ممنوعیتِ AutoClickerِ مشتریِ خرد پیدا نشد [49][50]. پیش از هر live، مالک باید تصمیمِ خود را با آگاهی از «UNVERIFIED» و شرایطِ کارگزار ثبت کند؛ ابزار نباید خود را «مجاز» معرفی کند.
- [ ] **P2-4: circuit breakerِ آمادگی.** هر شکستِ preflight (نشست، انتخابگر، فرم، آفست، ریسک) مدار را باز کند و «مسلح‌نشدن» را نشان دهد؛ بازگشت فقط با preflightِ کامل. الگویِ closed/open/half-open [38].
- [ ] **P2-5: مسیرِ API در برابر کلیک.** قبل از سرمایه‌گذاریِ بیشتر روی کلیک، مالک تصمیم بگیرد که مسیرِ اصلی همان APIِ مستندشده باشد و کلیک فقط fallbackِ کارگزارهایی باشد که API ندارند؛ چون API قابلِ order-id و reconcile است و کلیک نیست [19][21].

## ۵. پرسش‌هایِ باز و هشدارها

1. **مجوزِ رباتِ خرد:** هیچ سندِ رسمیِ SEO/TSETMC/کارگزار پیدا نشد که AutoClickerِ مشتریِ خرد را مجاز یا ممنوع کند. این پرسش با شواهدِ موجود قابلِ پاسخ نیست و باید UNVERIFIED بماند [49][50].
2. **«بهترین زمان»:** ۸:۴۵ شروعِ پنجرهٔ پیش‌گشایش است (به گزارشِ کارگزار/رسانه)، ولی هیچ سندی دربارهٔ اولویتِ میلی‌ثانیه‌ای یا مزیتِ ارسال در ۸:۴۵:۰۰٫۰۰۰ نداریم [47][48]. هر ادعایی در این باره فرضیه است.
3. **idempotency در EasyTrader:** هیچ مستندِ عمومی برایِ کلیدِ idempotency یا رفتارِ ثبتِ دوباره در فرم/APIِ EasyTrader پیدا نشد؛ نبودش یک استنتاج است، نه واقعیتِ مستند [37].
4. **تأخیرِ محیطِ مالک:** عددِ «کلیک تا POST» در سیستمِ مالک اندازه‌گیری نشده است. تا اندازه‌گیریِ P1-1، هیچ هدفِ زمانیِ میلی‌ثانیه‌ای قابلِ تنظیم نیست.
5. **پایداریِ زمان‌بندی:** triggerِ زمان‌بندی‌شده یک threadِ درون‌حافظه‌ای است (`api/execution.py:1129-1142`)؛ با restart از دست می‌رود. مسیرِ durableِ `ScheduleRunner` وجود دارد ولی به AutoClicker وصل نیست و dry-run است (`execution_schedule.py:1147-1166`). اگر مالک زمان‌بندیِ پایدار می‌خواهد، این اتصال کارِ مستقل است.
6. **مجوزِ دو مخزن:** ادعایِ MIT در READMEی `m-fazel` و `estakhri` بدونِ متنِ مجوز است؛ تفسیرِ حقوقیِ آن روشن نیست. تصمیمِ محافظه‌کارانه: همچنان مرجع، بدونِ کپی [6][10][28][29].
7. **معنایِ `blockT2` در قدرتِ خرید:** از راند ۱۱A باز مانده و در این تحقیق لمس نشد؛ تا اثباتِ معناشناسی، در فرمولِ BP وارد نشود.
8. **آستانه‌هایِ امنیتی:** cooldown، سقفِ ساعتی و تلورانسِ هدف، حکمِ مالک می‌خواهند؛ این تحقیق فقط روشِ اندازه‌گیری و ریسکِ نبودشان را نشان می‌دهد.

## روش‌شناسی

این گزارش در عمقِ deep و با شش عامل تولید شد: چهار عاملِ بازیابی (دو مخزنِ Rust، دو مخزنِ Selenium/PyQt، دو مخزنِ Playwright/Qt، و منابعِ بیرونی)، یک عاملِ بازبینیِ کدِ خودمان، یک عاملِ شکاف‌پرکن برای منابعِ رسمیِ ایران، و یک عاملِ راستی‌آزماییِ استناد. مخازن از کلون‌هایِ pin‌شدهٔ راند ۱۱A خوانده شدند و HEADِ هر شش کلون با SHAِ سندِ راند ۱۱A تطبیق داده شد. یک موجِ بازیابی و یک موجِ شکاف‌پرکن اجرا شد؛ ۵۴ منبع در کتاب‌نامه ثبت شد. راستی‌آزمایی، چهار تصحیحِ مهم داد: (۱) مجوزِ دو مخزن ادعایِ MIT در README دارند و جملهٔ «هیچ‌یک مجوز ندارد» باید اصلاح شود؛ (۲) `force:true` در Playwright همهٔ بررسی‌ها را دور نمی‌زند، بلکه بررسی‌هایِ غیرضروری مثلِ receives-events را دور می‌زند؛ (۳) throttleِ تبِ پنهان حدودِ ۱ بار در ثانیه است و تایمرهایِ زنجیره‌ای پس از پنج دقیقه به ۱ بار در دقیقه می‌رسند؛ (۴) بخشِ EasyTrader از ادعایِ idempotency یک استنتاج است، نه سند. هیچ اتصالِ زنده به کارگزاری، هیچ سفارشِ واقعی، هیچ credential و هیچ کپیِ کد انجام نشد. گزارش در شاخهٔ راند ۱۳ نوشته شد و هنوز commit نشده است. محدودیت‌ها: سندِ اولیهٔ زمان‌بندیِ بورس و شرایطِ کارگزار به‌دست نیامد؛ PDFِ الزاماتِ الگوریتمی قابلِ استخراج نبود؛ و هیچ‌کدام از مخازن تست یا دادهٔ عملیاتیِ قابلِ اتکا نداشتند.

## کتاب‌نامه

[1] m-fazel — `src/easy_trader.rs` @ `c7c94879e3d8b303202348e66ce95fc468b1bb1c` — https://github.com/m-fazel/Sarkhati/blob/c7c94879e3d8b303202348e66ce95fc468b1bb1c/src/easy_trader.rs — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[2] m-fazel — `src/main.rs` @ همان SHA — https://github.com/m-fazel/Sarkhati/blob/c7c94879e3d8b303202348e66ce95fc468b1bb1c/src/main.rs — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[3] m-fazel — `src/calibration.rs` @ همان SHA — https://github.com/m-fazel/Sarkhati/blob/c7c94879e3d8b303202348e66ce95fc468b1bb1c/src/calibration.rs — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[4] m-fazel — `src/time_reference.rs` @ همان SHA — https://github.com/m-fazel/Sarkhati/blob/c7c94879e3d8b303202348e66ce95fc468b1bb1c/src/time_reference.rs — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[5] m-fazel — `src/rate_limiter.rs` @ همان SHA — https://github.com/m-fazel/Sarkhati/blob/c7c94879e3d8b303202348e66ce95fc468b1bb1c/src/rate_limiter.rs — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[6] m-fazel — `README.md` @ همان SHA — https://github.com/m-fazel/Sarkhati/blob/c7c94879e3d8b303202348e66ce95fc468b1bb1c/README.md — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 3.
[7] estakhri — `src/main.rs` @ `b63f55b071ed15aa43781964005d40f58ddcd744` — https://github.com/estakhri/Sarkhati/blob/b63f55b071ed15aa43781964005d40f58ddcd744/src/main.rs — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[8] estakhri — `src/mofid.rs` @ همان SHA — https://github.com/estakhri/Sarkhati/blob/b63f55b071ed15aa43781964005d40f58ddcd744/src/mofid.rs — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[9] estakhri — `src/alvand.rs` @ همان SHA — https://github.com/estakhri/Sarkhati/blob/b63f55b071ed15aa43781964005d40f58ddcd744/src/alvand.rs — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[10] estakhri — `README.md` @ همان SHA — https://github.com/estakhri/Sarkhati/blob/b63f55b071ed15aa43781964005d40f58ddcd744/README.md — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 3.
[11] HosseinSayyedMousavi — `Sarkhati.py` @ `fd4b3731765fef1aec42e8a0829244538867fbcb` — https://github.com/HosseinSayyedMousavi/Sarkhati/blob/fd4b3731765fef1aec42e8a0829244538867fbcb/Sarkhati.py — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[12] HosseinSayyedMousavi — `Main.py` @ همان SHA — https://github.com/HosseinSayyedMousavi/Sarkhati/blob/fd4b3731765fef1aec42e8a0829244538867fbcb/Main.py — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[13] HosseinSayyedMousavi — `Captcha.py` @ همان SHA — https://github.com/HosseinSayyedMousavi/Sarkhati/blob/fd4b3731765fef1aec42e8a0829244538867fbcb/Captcha.py — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[14] sajadghandehari — `manage.py` @ `582d57032ea463b47827b2bc924d7b8ce6021490` — https://github.com/sajadghandehari/mofid-autotrader/blob/582d57032ea463b47827b2bc924d7b8ce6021490/manage.py — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[15] sajadghandehari — `front/main_page.ui` @ همان SHA — https://github.com/sajadghandehari/mofid-autotrader/blob/582d57032ea463b47827b2bc924d7b8ce6021490/front/main_page.ui — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[16] sajadghandehari — `README.md` @ همان SHA — https://github.com/sajadghandehari/mofid-autotrader/blob/582d57032ea463b47827b2bc924d7b8ce6021490/README.md — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 3.
[17] RezaMahdaviiDev — `src/brokerages/easy/buyActionUltra.ts` @ `72a2e8cbd58aba4841dc0e98a10d77571505d862` — https://github.com/RezaMahdaviiDev/mofid/blob/72a2e8cbd58aba4841dc0e98a10d77571505d862/src/brokerages/easy/buyActionUltra.ts — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[18] RezaMahdaviiDev — `src/brokerages/easy/buyAction.ts` @ همان SHA — https://github.com/RezaMahdaviiDev/mofid/blob/72a2e8cbd58aba4841dc0e98a10d77571505d862/src/brokerages/easy/buyAction.ts — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[19] RezaMahdaviiDev — `src/brokerages/easy/buyActionAPI.ts` @ همان SHA — https://github.com/RezaMahdaviiDev/mofid/blob/72a2e8cbd58aba4841dc0e98a10d77571505d862/src/brokerages/easy/buyActionAPI.ts — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[20] RezaMahdaviiDev — `src/brokerages/easy/api/client.ts` @ همان SHA — https://github.com/RezaMahdaviiDev/mofid/blob/72a2e8cbd58aba4841dc0e98a10d77571505d862/src/brokerages/easy/api/client.ts — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[21] RezaMahdaviiDev — `src/brokerages/easy/api/order.ts` @ همان SHA — https://github.com/RezaMahdaviiDev/mofid/blob/72a2e8cbd58aba4841dc0e98a10d77571505d862/src/brokerages/easy/api/order.ts — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[22] RezaMahdaviiDev — `src/brokerages/easy/api/rateLimiter.ts` @ همان SHA — https://github.com/RezaMahdaviiDev/mofid/blob/72a2e8cbd58aba4841dc0e98a10d77571505d862/src/brokerages/easy/api/rateLimiter.ts — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[23] RezaMahdaviiDev — `src/brokerages/easy/api/tokenCache.ts` @ همان SHA — https://github.com/RezaMahdaviiDev/mofid/blob/72a2e8cbd58aba4841dc0e98a10d77571505d862/src/brokerages/easy/api/tokenCache.ts — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[24] RezaMahdaviiDev — داشبورد (`index.html`, `app.js`, `routes/buy.ts`, `server.ts`) @ همان SHA — https://github.com/RezaMahdaviiDev/mofid/tree/72a2e8cbd58aba4841dc0e98a10d77571505d862/src/dashboard — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[25] RezaMahdaviiDev — `src/core/browser.ts` و `routes/login.ts` @ همان SHA — https://github.com/RezaMahdaviiDev/mofid/blob/72a2e8cbd58aba4841dc0e98a10d77571505d862/src/core/browser.ts — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[26] amirali110 — `mainwindow.cpp` @ `2fb5b604fe4bd2b04d95dd3423f5a0acf68fc9b9` — https://github.com/amirali110/Sarkhati-Bourse/blob/2fb5b604fe4bd2b04d95dd3423f5a0acf68fc9b9/mainwindow.cpp — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[27] amirali110 — `mainwindow.ui` @ همان SHA — https://github.com/amirali110/Sarkhati-Bourse/blob/2fb5b604fe4bd2b04d95dd3423f5a0acf68fc9b9/mainwindow.ui — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[28] GitHub REST API — metadata و license endpoint برای هر شش مخزن (همه ۴۰۴/`license:null`؛ SHAها: `c7c9487`, `b63f55b`, `fd4b373`, `582d570`, `72a2e8c`, `2fb5b60`) — https://api.github.com/repos/m-fazel/Sarkhati — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[29] GitHub Docs — Licensing a repository — https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[30] Playwright — Auto-waiting / actionability — https://playwright.dev/docs/actionability — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[31] Playwright — Clock — https://playwright.dev/docs/clock — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[32] MDN — `Performance.now()` — https://developer.mozilla.org/en-US/docs/Web/API/Performance/now — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[33] chrony — Introduction — https://chrony-project.org/ — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[34] Chromium Blog — Reducing power consumption for background tabs — https://blog.chromium.org/2017/03/reducing-power-consumption-for.html — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[35] Chrome for Developers — Heavy throttling of chained JS timers beginning in Chrome 88 — https://developer.chrome.com/blog/timer-throttling-in-chrome-88 — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[36] chromestatus — Throttle chained timers — https://chromestatus.com/feature/4718288976216064 — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[37] Stripe — Idempotent requests — https://docs.stripe.com/api/idempotent_requests — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[38] Microsoft Azure Architecture Center — Circuit Breaker Pattern — https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[39] U.S. SEC — Trading and Markets FAQ (Rule 15c3-5) — https://www.sec.gov/rules-regulations/staff-guidance/trading-markets-frequently-asked-questions/divisionsmarketregfaq-0 — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[40] FINRA — Market Access Rule — https://www.finra.org/rules-guidance/guidance/reports/2022-finras-examination-and-risk-monitoring-program/market-access-rule — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[41] Selenium — Waiting Strategies — https://www.selenium.dev/documentation/webdriver/waits/ — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[42] Selenium — ThreadGuard — https://www.selenium.dev/documentation/webdriver/support_features/thread_guard/ — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[43] Node.js — `perf_hooks` / `performance.now()` — https://nodejs.org/api/perf_hooks.html — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[44] Qt — QTimer Class — https://doc.qt.io/qt-6/qtimer.html — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1.
[45] Bruce Dawson (RandomASCII) — Windows Timer Resolution — https://randomascii.wordpress.com/2020/10/04/windows-timer-resolution-the-great-rule-change/ — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[46] cf-natali — `ntplib.py` — https://raw.githubusercontent.com/cf-natali/ntplib/master/ntplib.py — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2.
[47] کارگزاری مفید — «ساعت معاملات در بورس به چه صورت است؟» — https://learning.emofid.com/trading-hours/ — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 3.
[48] دنیای اقتصاد — «زمان‌بندی معاملات بورس اعلام شد» — https://donya-e-eqtesad.com/بخش-سایت-خوان-62/4271386 — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 3.
[49] خبرگزاری مهر — «معاملات الگوریتمی آزاد شد / ۸ شرط سازمان بورس برای کارگزاران» — https://www.mehrnews.com/news/5192979 — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 3 (رسانه؛ نقل از اطلاعیهٔ رسمی).
[50] پورتال خدمت سازمان بورس — گزارش‌های نظارتی معاملات الگوریتمی — https://service.seo.ir/news/80293 — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 2 (پورتال رسمی؛ متن کامل قابلِ استخراج نبود).
[51] کارگزاری بهگزین — «الزامات معاملات الگوریتمی» (PDF) — https://behgozinbroker.ir/Assets/143/1397-12-29-الزامات%20معاملات%20الگوریتمی-1.pdf — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 1 (میزبانِ رسمی؛ متن قابلِ استخراج نبود).
[52] Jetboors — تبلیغِ رباتِ سرخطی — https://jetboors.ir/Page/2/News/129/ربات-فروش-چخزر — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 3 (تبلیغاتِ فروشنده).
[53] Bourse Robot — صفحهٔ فروشنده — https://bourse-robot.ir/ — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 3 (تبلیغاتِ فروشنده).
[54] رهاورد۳۶۵ — «سودجویی از طریق سرخطی زدن» — https://rahavard365.com/feed/items/122922/ — دسترسی ۲۰۲۶-۱۰-۲۱ — Tier 3 (رسانه).

## استخراجِ منابع

جدولِ زیر شواهدِ کلیدیِ مخازن را برایِ پیگیریِ آینده نگه می‌دارد. نقل‌قول‌ها کوتاه‌اند و کدِ کامل بازنشر نمی‌شود.

| # | خلاصه | شاهدِ کلیدی | نوع/Tier |
| --- | --- | --- | --- |
| [1] | کلاینتِ EasyTrader؛ ساختِ payload و ارسال؛ تأیید فقط 2xx | `if !status.is_success() { bail!(...) }`؛ چاپِ Authorization در test/curl | CODE_OBSERVED / 2 |
| [2] | زمان‌بند، `batch_repeat` موازی، drift فقط لاگ | `final_send = target − effective_delay`؛ `join_all` روی repeatها | CODE_OBSERVED / 2 |
| [3] | کالیبراسیونِ RTT با HEAD روی ریشه؛ شکست ⇒ صفر | `max_probes = usize::MAX` با deadline؛ `using zero delay estimate` | CODE_OBSERVED / 2 |
| [4] | NTP یک‌باره با offset صفر در خطا | `OnceLock`؛ `CLOCK_OFFSET_MS.set(0)` | CODE_OBSERVED / 2 |
| [5] | حداقلِ فاصلهٔ ساده با mutex | `sleep(rate_limit − elapsed)` | CODE_OBSERVED / 2 |
| [6] | README: delay، plaintext، ادعای MIT | «Batch delay: 100ms…»؛ «MIT» بدون فایل | README_CLAIM / 3 |
| [7] | شش حلقهٔ کارگزار، spawn بدون await | `tokio::spawn(...)` سپس `sleep(batch_delay)` | CODE_OBSERVED / 2 |
| [8] | کلاینتِ مفید، کوکی/Bearer، چاپِ پاسخ | `Cookie:` و `Authorization:` در curl؛ چاپِ body | CODE_OBSERVED / 2 |
| [9] | هدرِ `X-App-N` از UTC منهای ۲s | `Utc::now() − 2s` | CODE_OBSERVED / 2 |
| [10] | README: loop بی‌پایان، plaintext، ادعای MIT | «continuously send orders in a loop» | README_CLAIM / 3 |
| [11] | XPath مطلق؛ بازگشتِ بازگشتی؛ toast بدون انتظار | `except: Transaction()`؛ `find_element` روی toast | CODE_OBSERVED / 2 |
| [12] | کنترل‌های UI: فاصله ۱۰۰–۱۰۰٬۰۰۰ms، سقف تعداد | `Req_Distance` min/max/default؛ `Quantity_Field` max | CODE_OBSERVED / 2 |
| [13] | CAPTCHA دستی، بدون OCR | فیلد و دکمه تا رسیدنِ تصویر غیرفعال | CODE_OBSERVED / 2 |
| [14] | polling هر ۱s؛ `hh` در برابر `%H`؛ ۱۵ کلیک | `toString("hh:mm:ss")` و `strftime("%H:%M:%S")`؛ `range(15)` | CODE_OBSERVED / 2 |
| [15] | نمایشِ زمان `ss:mm:HH`؛ تعداد بی‌استفاده | `displayFormat`؛ فیلد «تعداد سهم» | CODE_OBSERVED / 2 |
| [16] | README: تعداد از قبل در حساب؛ «۵ ثانیه قبل» | ادعای تجربی، بدون سند | README_CLAIM / 3 |
| [17] | DOM با `data-cy`؛ `force:true`؛ تأییدِ غیرمسدودکننده | `click({ force: true })`؛ `console.warn` و ادامه | CODE_OBSERVED / 2 |
| [18] | بررسیِ هدر با نامِ نمادِ دیگر؛ refill یک‌باره | `includes('اطلس')`؛ سپس ارسال | CODE_OBSERVED / 2 |
| [19] | API و fallback به DOM در catch | `executeFastBuy(page, order)` در catch | CODE_OBSERVED / 2 |
| [20] | retry و backoff؛ ۴۰۰/۴۰۱ بدون retry | `retries=2`؛ `100·2^(n−1)` تا ۵۰۰۰ms | CODE_OBSERVED / 2 |
| [21] | قرارداد و مانیتورِ صف | `interval=5000`, `maxChecks=60`؛ `orderPlace <= 1` | CODE_OBSERVED / 2 |
| [22] | صفِ FIFO با ۱۰۰ms | `minInterval = 1000 / maxRps`؛ `new RateLimiter(10)` | CODE_OBSERVED / 2 |
| [23] | توکن روی دیسک با TTL دو ساعت | `fs.writeFileSync(cacheFile, ...)` | CODE_OBSERVED / 2 |
| [24] | داشبوردِ تک‌صفحه‌ای؛ وضعیتِ ثابت | متنِ «آماده برای خرید» در HTML | CODE_OBSERVED / 2 |
| [25] | `storageState` و loginِ ۳۰ثانیه‌ای بدونِ assert | `waitForTimeout(30000)` سپس ذخیره | CODE_OBSERVED / 2 |
| [26] | QTimer ۱ms؛ تایمرِ دوم `start()` نمی‌شود | `new_timer` بدونِ `start()`؛ URLهایِ ناقص | CODE_OBSERVED / 2 |
| [27] | فیلدهای TOKEN/interval/repeat که استفاده نمی‌شوند | UIِ بدونِ منطقِ متناظر | CODE_OBSERVED / 2 |
| [28] | همهٔ شش مخزن `license:null`/۴۰۴ | پاسخِ API و SHAهایِ pin‌شده | EXTERNAL / 1 |
| [29] | نبودِ مجوز ⇒ حقوقِ پیش‌فرض | «no one may reproduce, distribute, or create derivative works» | OFFICIAL_DOC / 1 |
| [30] | actionabilityِ کلیک و معنایِ force | visible/stable/receives-events/enabled | OFFICIAL_DOC / 1 |

منابعِ ۳۱ تا ۵۴ اسنادِ رسمی/رسانه‌ایِ بیرونی‌اند و در کتاب‌نامه با URL کامل آمده‌اند. مهم‌ترین نقل‌ها: دقتِ NTPِ اینترنت «چند میلی‌ثانیه» [33]؛ یکنواییِ `performance.now()` [32]؛ throttleِ تبِ پنهان «یک بار در ثانیه» [34] و سخت‌ترشدنِ تایمرهایِ زنجیره‌ای پس از Chrome 88 [35][36]؛ نگه‌داریِ کلیدِ idempotencyِ Stripe برایِ دست‌کم ۲۴ ساعت [37]؛ مدارِ closed/open/half-open [38]؛ ساعتِ پیش‌گشایش ۸:۴۵–۹:۰۰ در صفحهٔ کارگزاری مفید [47] و وابستگیِ پنجره به نوعِ ابزار [48]؛ و چارچوبِ هشت‌شرطیِ معاملاتِ الگوریتمیِ مؤسسات [49] که به مشتریِ خرد تعمیم داده نمی‌شود.

---

**وضعیتِ نهایی:** `live_enabled=false`، `live_ready=false`، هیچ سفارشِ واقعی، هیچ credential و هیچ کدِ کپی‌شده. این سند پیشنهادِ تحقیق است، نه مجوزِ اجرا؛ تصمیم‌هایِ آستانه و مجوز با مالک است.

