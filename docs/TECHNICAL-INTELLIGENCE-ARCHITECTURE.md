# معماری هوشمندی تکنیکال BorsTerminal
## Technical Intelligence, Adaptive Indicators & Kronos Forecasting

- تاریخ: 2026-11-10
- وضعیت: معماری پایه برای بررسی و اجرای مرحله‌ای؛ جهت کلی با مالک پروژه توافق شده است.
- دامنه: زیرساخت‌های تکنیکال و یادگیری که باید پیش از Opportunity Lab آماده شوند.
- وضعیت پیاده‌سازی: این سند به‌تنهایی به معنی شروع پیاده‌سازی، تغییر قواعد FTS، فعال‌سازی مدل‌ها یا انتشار قابلیت نیست.

---

## 1. هدف و جایگاه این معماری

هدف، ساخت یک لایه هوشمندی تکنیکال تخصصی برای بازار سرمایه ایران است که بر داده‌های تاریخی و جاری خود BorsTerminal تکیه کند و اجزای قابل‌استفاده مجدد برای Opportunity Lab فراهم کند.

این لایه باید چهار مسئله متفاوت را از یکدیگر جدا نگه دارد:

1. **قواعد canonical استراتژی FTS:** همان منطق مصوب جزوه، چارت و رأی‌های مالک؛ بدون بازنویسی یا تغییر ضمنی.
2. **تشخیص ساختار و الگوها:** محاسبه و شناسایی رویدادهایی مانند Jet، Pullback، CHoCH، کانال و الگوهای کلاسیک.
3. **یادگیری تطبیقی کیفیت الگوها:** یادگیری اینکه هر الگو در چه شرایطی و با چه احتمال و ریسکی به نتیجه می‌رسد.
4. **پیش‌بینی سری زمانی با Kronos:** پیش‌بینی توزیعی و چندافقی کندل‌ها و روند احتمالی آینده، با آموزش و ارزیابی اختصاصی بورس ایران.

این چهار خروجی می‌توانند در آینده در Opportunity Lab کنار هم مصرف شوند، اما نباید به یک مدل واحد، یک امتیاز مبهم یا یک مرجع تصمیم‌گیری غیرقابل‌توضیح تبدیل شوند.

## 2. اصول معماری و محدودیت‌های غیرقابل‌مذاکره

### 2.1 استقلال FTS

- منبع روش‌شناسی FTS، جزوه اصلی، چارت چهارصفحه‌ای و رأی‌های صریح مالک است.
- FTS canonical باید مستقل باقی بماند. هیچ مدل ML، Kronos، اندیکاتور خارجی یا الگوی کلاسیک حق بازنویسی یا تفسیر مجدد قواعد آن را ندارد.
- اندیکاتورهای جدید می‌توانند کنار FTS ثبت و اجرا شوند، اما باید صریحاً مشخص باشد که «قاعده رسمی FTS» هستند یا «تحلیل مستقل/پژوهشی».
- فیبوناچی در FTS نقش Context دارد و به‌تنهایی تریگر ورود نیست.
- جت در Production فقط روی آخرین کندل محاسبه و منتشر می‌شود. ساخت مارکر جت تاریخی فقط در محیط پژوهشی مجاز است.
- رأی‌های مالک و وضعیت‌های فعلی مانند approval_enabled=false حفظ می‌شوند. هیچ مدل یا فرآیند یادگیری خودکاری مجاز به تأیید، Stable کردن یا فعال‌سازی استراتژی نیست.

### 2.2 صداقت داده و محاسبه

- داده خام و تعدیل‌شده باید صریحاً از هم جدا باشند؛ هیچ سری ترکیبی یا مبنای مبهمی مجاز نیست.
- تمام محاسبات باید زمان مبنای داده، منبع، نسخه الگوریتم، تایم‌فریم و وضعیت تازگی را نگه دارند.
- اطلاعات آینده، اصلاحات بعدی تاریخچه، داده بنیادی منتشرنشده در زمان تصمیم و هر ویژگی مبتنی بر آینده نباید به ورودی گذشته نشت کند.
- نقطه وقوع Pivot از زمان تأیید آن جداست.
- وضعیت‌های forming، confirmed، invalid، unknown و insufficient_data باید از هم متمایز باشند.
- نبود داده هرگز به صفر، false، موفقیت یا شکست تبدیل نمی‌شود.
- هیچ الگوی repaint‌شونده‌ای نباید در UI به‌عنوان سیگنال قطعی تاریخی نمایش داده شود.

### 2.3 مرز اجرا و تکنولوژی محصول

- Runtime محصول: Tauri v2 + React/Vite + Go backend + SQLite.
- Python مجاز برای پژوهش، آماده‌سازی داده، آموزش، ارزیابی و ابزارهای توسعه است؛ اما نباید به وابستگی الزامی نصب و اجرای Production تبدیل شود.
- اجرای Production مدل‌های ML باید با یک مسیر native و قابل‌بسته‌بندی اثبات شود. نوع Runtime مدل، از جمله ONNX یا موتور native جداگانه، تا انجام آزمون امکان‌سنجی قطعی نیست.
- CPU-first اصل پیش‌فرض Runtime است. GPU برای آموزش یا محاسبات سنگین می‌تواند اختیاری و با انتخاب صریح مالک باشد.
- افزودن سرویس خارجی، Cloud inference، دیتابیس جدید یا زیرساخت پرهزینه بدون شواهد و تصمیم جداگانه مجاز نیست.

---

## 3. نمای کلان معماری

جریان منطقی پیشنهادی:

**Market Data & Corporate Events**
→ **Canonical Data / Price-Basis Layer**
→ **Feature & Structure Layer**
→ چند موتور مستقل:
- **Canonical FTS Engine**
- **Deterministic Pattern & Indicator Engine**
- **Adaptive Signal Intelligence**
- **Kronos Forecasting Engine**

سپس خروجی هر موتور با قرارداد مشخص در **Technical Intelligence Registry / Result Store** ثبت می‌شود و در چارت، پنل تکنیکال، اسکرینر و در آینده Opportunity Lab قابل‌مصرف خواهد بود.

اصل مهم: لایه نمایش فقط نتیجه و شواهد محاسبه‌شده را نمایش می‌دهد؛ مرجع محاسبه در چند محل موازی تکرار نمی‌شود.

## 4. لایه داده و ویژگی‌های بازار ایران

### 4.1 داده‌های ورودی

منابع اصلی از دیتابیس و Pipeline خود BorsTerminal هستند:

- کندل‌های OHLCV و ارزش معاملات؛
- حجم و تعداد معاملات؛
- اطلاعات نماد، نوع ابزار، صنعت و وضعیت معاملاتی؛
- رویدادهای شرکتی و زنجیره تعدیل؛
- قیمت خام و قیمت تعدیل‌شده با basis صریح؛
- داده‌های بازار و شاخص‌های breadth؛
- جریان حقیقی/حقوقی و اطلاعات تابلو در صورت وجود و معتبر بودن؛
- تقویم معاملاتی، توقف و بازگشایی، محدودیت دامنه قیمت، اندازه tick و ویژگی‌های نقدشوندگی.

داده‌های صف، عمق بازار و درون‌روزی فقط زمانی استفاده می‌شوند که پوشش تاریخی و کیفیت آن‌ها واقعاً موجود باشد. نبود داده تاریخی نباید با شبیه‌سازی جعلی پنهان شود.

### 4.2 Market Data Contract

هر ورودی تحلیلی باید حداقل این فراداده را داشته باشد:

- شناسه پایدار نماد و نوع ابزار؛
- تایم‌فریم و زمان کندل؛
- timestamp دریافت و timestamp مؤثر بازار؛
- منبع داده و وضعیت اعتبار؛
- مبنای قیمت: raw یا adjusted به‌همراه نسخه زنجیره تعدیل؛
- وضعیت جلسه، توقف، بازگشایی و محدودیت قیمت در صورت دسترسی؛
- شناسه نسخه Dataset/Snapshot برای بازتولید آزمایش.

### 4.3 ویژگی‌های مشتق‌شده

Feature Layer می‌تواند ویژگی‌هایی مانند موارد زیر را محاسبه کند:

- بازده و تغییرات لگاریتمی قیمت؛
- ATR و نوسان تحقق‌یافته؛
- نسبت بدنه و سایه کندل؛
- فاصله نرمال‌شده تا Pivot، مقاومت، حمایت و خط روند؛
- شیب و کیفیت کانال؛
- حجم نسبی، ارزش معاملات و تعداد معاملات؛
- دامنه نوسان و فاصله تا حد مجاز روزانه؛
- وضعیت روند در تایم‌فریم‌های روزانه و هفتگی؛
- شاخص‌های breadth و صنعت، فقط با داده معتبر و as-of.

ویژگی‌ها باید نسخه‌دار، قابل بازتولید و دارای زمان برش باشند. محاسبه یک Feature در دو مسیر متفاوت، بدون قرارداد و تست برابری، مجاز نیست.

---

## 5. موتور canonical FTS

FTS یک مصرف‌کننده مستقل و صاحب قواعد خودش باقی می‌ماند. این معماری فقط نیازهای آن را به موتورهای تکنیکال استاندارد وصل می‌کند؛ منطق FTS را به مدل یادگیری منتقل نمی‌کند.

### 5.1 ساختار و گیت روند

- تشخیص روند ساختاری از توالی Pivotها و HH/HL/LH/LL، نه جایگزین‌کردن آن با MA.
- طبقه‌بندی مجزای Daily و Weekly.
- روند هفتگی نزولی یا خنثی، طبق قواعد FTS، گیت ورود را رد می‌کند.
- روند روزانه مسیر Setup را مشخص می‌کند:
  - صعودی: Jet و Pullback؛
  - نزولی: Fibonacci Context و CHoCH؛
  - خنثی: منطق منبع‌محور کف/حمایت، کف دوقلو و محدوده بین Pivotهای معتبر.
- مقدارهای unknown و insufficient_data باید قابل انتشار باشند و به verdict ساختگی تبدیل نشوند.

### 5.2 کاتالوگ قابلیت‌های FTS موردنیاز

| شناسه / خانواده | وظیفه و مرز |
|---|---|
| Structural Trend | HH/HL، LH/LL و روند خنثی در روزانه و هفتگی |
| Weekly Gate | وتوی هفتگی طبق FTS |
| Jet | شکست مقاومت استاتیک/سقف تاریخی و کندل تثبیت؛ مارکر Production فقط روی آخرین کندل |
| Pullback | بازگشت به سقف شکسته‌شده یا مقاومت استاتیک و تشخیص نقطه تماس |
| Fibonacci | محاسبه لگاریتمی موج و باندهای 33–40٪ و 61.8–70٪؛ Context، نه تریگر مستقل |
| CHoCH | تغییر ساختار با شکست Pivot مخالف و تفکیک forming/confirmed/invalid |
| Point Hunt | خط روند نزولی، شمارش کف‌ها و تشخیص نقاط سوم و پنجم |
| Double Bottom | دو کف و Neckline؛ ورود پس از شکست Neckline |
| Double Top | سقف‌های دوقلو، شکست Neckline و رویداد خروج |
| Head & Shoulders | لایه خروج/هشدار متناظر با قواعد CHoCH در FTS |
| Third Peak | ناتوانی از ساخت سقف بالاتر و فاصله از خط مقاومت |
| Range Box / Breakout | باکس رنج، طول دوره و شکست همراه با شواهد حجم/جریان پول |
| MA14 Exit | قاعده کندل کامل زیر MA14 مطابق منبع و رأی‌های مالک |
| MA52 Weekly / Hourglass | لایه هفتگی ساعت‌شنی با تنظیمات مصوب |
| MA100 Daily | مرجع روزانه طبق جزوه |
| RSI Divergence | واگرایی منفی با RSI(14)، مستقل از RSI ساعت‌شنی |
| Volume MA | نمایش Volume MA(21)؛ قواعد حجم مشکوک مبنای مستقل خود را حفظ می‌کنند |
| Market/Tape Context | الگوی ساعت، حجم مشکوک، ورود پول و کف‌روبی صف در لایه تابلو، نه محاسبه صرفاً قیمت‌محور |

جزئیات فرمول، آستانه و رفتار هر ردیف باید از اسناد canonical استخراج شود. این جدول فهرست قابلیت‌هاست، نه مجوز تغییر فرمول‌ها.

### 5.3 یکپارچگی محاسبات

- تنها یک مرجع محاسباتی برای هر رأی FTS وجود دارد.
- خروجی canonical از Backend می‌آید؛ Frontend و موتورهای نمودار آن را دوباره تفسیر نمی‌کنند.
- دو موتور رندر موجود باید از همان payload و همان نقش‌ها استفاده کنند.
- نمایش لایه، رنگ و سوییچ آن حق تغییر رأی تحلیلی را ندارد.
- ناسازگاری‌های فعلی Catalog، API، محاسبه و renderer ابتدا ممیزی و سپس با تست parity اصلاح می‌شوند.

---

## 6. Deterministic Indicator & Pattern Engine

### 6.1 هدف

این موتور ساختار و الگو را با الگوریتم‌های شفاف تشخیص می‌دهد. وظیفه آن «تشخیص اینکه چه چیزی روی نمودار شکل گرفته» است، نه پیش‌بینی قطعی سودآوری آن.

هر Detector مستقل، نسخه‌دار و قابل‌آزمون است؛ اما همه از قرارداد خروجی مشترک پیروی می‌کنند.

### 6.2 خانواده اول: ساختار بازار و هندسه قیمت

- Swing / Pivot Detector
- Market Structure: HH, HL, LH, LL
- Support & Resistance Zones
- Static Resistance / Historical High
- Trendline Detector
- Parallel Channel Detector
- Range / Rectangle Detector
- Breakout & Retest Detector
- Volatility / ATR Context

Swing Detector باید زمان وقوع Pivot را از زمان تأیید جدا کند و تأیید آینده‌محور را به گذشته نسبت ندهد.

### 6.3 خانواده دوم: Setupها و الگوهای اختصاصی FTS

Jet، Pullback، Fibonacci، CHoCH، Point Hunt، Double Bottom، Double Top، Head & Shoulders، Third Peak، Range Box و Hourglass در کاتالوگ اختصاصی FTS حفظ می‌شوند.

برای قابلیت‌هایی که از قبل در پروژه وجود دارند، پیاده‌سازی مجدد از صفر پیش‌فرض نیست. ابتدا وضعیت واقعی کد، تست، parity، repaint، خروجی API و نمایش در هر دو موتور نمودار ممیزی می‌شود.

### 6.4 خانواده سوم: الگوهای کلاسیک مستقل

الگوهای زیر به‌عنوان کتابخانه مستقل و پژوهشی در نظر گرفته می‌شوند:

**ادامه‌دهنده:**
- Ascending Triangle
- Descending Triangle
- Symmetrical Triangle
- Bull Flag / Bear Flag
- Pennant
- Rectangle Continuation
- Rising Channel / Falling Channel

**بازگشتی:**
- Head & Shoulders / Inverse Head & Shoulders
- Double Top / Double Bottom
- Triple Top / Triple Bottom
- Rising Wedge / Falling Wedge
- Rounding Bottom / Cup & Handle، در صورت توجیه داده‌ای

هر الگو باید Detector، تعریف هندسی، شرایط تشکیل و ابطال، نقطه شکست، تایم‌فریم، محدودیت داده و مجموعه تست مستقل داشته باشد.

این خانواده به‌صورت پیش‌فرض خارج از قواعد رسمی FTS است. حتی اگر نام یک الگو در FTS نیز وجود داشته باشد، شناسه و رابطه آن با FTS باید صریح باشد؛ نسخه کلاسیک نباید قواعد FTS را جایگزین کند.

### 6.5 قرارداد استاندارد Detector

هر Detector حداقل این مشخصات را ثبت می‌کند:

- شناسه پایدار، نام، خانواده و نسخه؛
- وضعیت canonical: FTS یا مستقل/پژوهشی؛
- تایم‌فریم و ورودی‌های لازم؛
- حداقل تاریخچه موردنیاز و warm-up؛
- پارامترها و منبع هر پارامتر؛
- وضعیت repaint و سیاست تأیید؛
- محدوده هندسی یا سطوح کلیدی؛
- زمان وقوع و زمان تأیید؛
- وضعیت forming / confirmed / invalid / unknown؛
- نقش خروجی: entry، context، warning یا exit، در صورت انطباق با قرارداد مصرف‌کننده؛
- شواهد و توضیح قابل نمایش؛
- نسخه Feature، مدل و Dataset در صورت استفاده از ML.

Detector نباید بدون دلیل، یک سیگنال خرید/فروش یا احتمال موفقیت تولید کند. تشخیص الگو و ارزیابی کیفیت آن دو مرحله مجزا هستند.

---

## 7. Adaptive Signal Intelligence

### 7.1 هدف

این موتور می‌آموزد هر Detector در چه شرایطی عملکرد بهتری یا بدتری دارد.

برای مثال:
- Jet پس از شکست مقاومت، با چه وضعیت روند هفتگی و چه حجم نسبی موفق‌تر بوده است؟
- Pullback با چه عمق اصلاح، نوسان و فاصله از حمایت نتیجه بهتری داشته است؟
- شکست Range Box در چه شرایطی شکست کاذب بیشتری داشته است؟
- الگوهای مثلث یا سر و شانه در کدام صنایع و رژیم‌های بازار قابل‌اتکاتر بوده‌اند؟

این مدل‌ها تشخیص هندسی را حذف نمی‌کنند؛ کیفیت و Outcome تاریخی آن را تخمین می‌زنند.

### 7.2 روش شروع

به‌جای ساخت یک شبکه عصبی بزرگ برای همه الگوها، ابتدا روش‌های کم‌هزینه و قابل‌توضیح ارزیابی می‌شوند:

- KNN / Pattern Memory برای بازیابی نمونه‌های تاریخی مشابه؛
- LightGBM یا CatBoost برای تخمین احتمال و ریسک؛
- Logistic Regression به‌عنوان baseline ساده و قابل‌تفسیر؛
- کالیبراسیون احتمال و بررسی پایداری آن در زمان.

مدل و روش مناسب می‌تواند برای هر خانواده متفاوت باشد. انتخاب نهایی براساس Walk-forward و عملکرد روی داده خارج از آموزش انجام می‌شود، نه براساس پیچیدگی یا شهرت الگوریتم.

### 7.3 Outcome Ledger

تمام رویدادهای تشخیص‌داده‌شده باید ثبت شوند، نه فقط نمونه‌های موفق:

- سیگنال و نسخه Detector؛
- وضعیت روند، صنعت و رژیم بازار در لحظه تشخیص؛
- ویژگی‌های ورودی در همان زمان؛
- زمان و قیمت فرضی اجرای قابل‌دفاع؛
- هدف، حد ابطال و افق ارزیابی؛
- لمس هدف، لمس حد، انقضا یا نامشخص‌ماندن؛
- امکان واقعی اجرا با توجه به صف، محدودیت قیمت، توقف و نقدشوندگی؛
- هزینه‌های معامله و اثر عدم انجام سفارش، هرجا داده کافی باشد.

Outcome باید delayed-label باشد. کندل جدید به‌تنهایی موفقیت یا شکست پیش‌بینی قبلی را معلوم نمی‌کند. یک رویداد تا پایان افق یا وقوع شرایط برچسب‌گذاری، pending باقی می‌ماند.

نمونه‌های failed، stopped، expired، invalid و no-fill باید نگه داشته شوند. حذف آن‌ها باعث Selection Bias و برآورد بیش‌ازحد موفقیت می‌شود.

### 7.4 یادگیری تطبیقی و کنترل نسخه

چرخه پیشنهادی:

1. داده جدید دریافت و اعتبارسنجی می‌شود.
2. Featureهای جدید محاسبه می‌شوند.
3. Outcomeهای بالغ‌شده برچسب می‌خورند.
4. آمار drift و کیفیت مدل پایش می‌شود.
5. در صورت کفایت نمونه، نسخه Challenger به‌صورت کنترل‌شده آموزش می‌بیند.
6. Challenger در آزمون زمانی و Holdout قفل‌شده مقایسه می‌شود.
7. فقط با عبور از گیت‌های پذیرش می‌تواند جای Champion را بگیرد.
8. مدل قبلی و امکان Rollback حفظ می‌شوند.

یادگیری روزانه به معنی تغییر خودکار و بی‌قید مدل فعال نیست. جمع‌آوری و تکمیل برچسب‌ها می‌تواند روزانه باشد؛ آموزش مجدد و ارتقای مدل باید versioned، reproducible و gate-controlled باشد.

### 7.5 خروجی

خروجی باید شامل احتمال کالیبره‌شده، تعداد نمونه، افق، نرخ پایه، محدوده عدم‌قطعیت، ویژگی‌های مهم، نسخه مدل و تاریخ آموزش باشد. احتمال بدون حجم نمونه یا بدون کالیبراسیون نباید به‌عنوان اطمینان معتبر نمایش داده شود.

---

## 8. Kronos Forecasting Engine

### 8.1 جایگاه و هدف

Kronos یک مسیر مستقل برای پیش‌بینی سری زمانی مالی است. در BorsTerminal هدف، استفاده پژوهشی و سپس آموزش تکمیلی آن با داده‌های خود بورس ایران است تا در صورت عبور از معیارها بتواند:

- توالی احتمالی کندل‌های آینده را پیش‌بینی کند؛
- سناریوهای چندکندلی و چندافقی تولید کند؛
- مسیر احتمالی روند و دامنه نوسان را تخمین بزند؛
- عدم‌قطعیت و چند سناریوی ممکن را نشان دهد.

خروجی pretrained روی بازارهای دیگر، بدون Fine-tuning و آزمون ایرانی معتبر فرض نمی‌شود.

### 8.2 مسیر آموزش

1. ثبت نسخه دقیق کد، معماری، tokenizer، checkpoint و مجوز Kronos.
2. ساخت Dataset Snapshot نسخه‌دار از دیتابیس BorsTerminal.
3. جداسازی صریح نمادها، تایم‌فریم‌ها، بازارها و price basis.
4. بررسی پوشش و کیفیت تاریخچه، corporate actions، توقف‌ها، داده‌های ناقص و اصلاح‌شده.
5. ساخت baseline از نسخه pretrained بدون تغییر.
6. ساخت baselineهای ساده و ارزان برای مقایسه.
7. Fine-tune روی داده ایران با split زمانی و جلوگیری از نشت اطلاعات.
8. ارزیابی چندافقی و Walk-forward.
9. ثبت خطاها، calibration، drift و عملکرد به تفکیک صنعت، نوع نماد و رژیم بازار.
10. تنها پس از پذیرش، ساخت نسخه قابل‌استقرار و آزمون Runtime.

### 8.3 طراحی داده و هدف پیش‌بینی

- ورودی اصلی، توالی تاریخی OHLCVA از دیتابیس خود پروژه است.
- مدل نباید raw و adjusted را بدون برچسب و قرارداد در یک سری ادغام کند.
- مدل می‌تواند با چند نماد به‌صورت pooled آموزش ببیند؛ در شروع، آموزش مستقل برای هر نماد به‌دلیل کوتاهی یا کمبود تاریخچه پیش‌فرض نیست.
- ویژگی‌های بازار ایران مانند محدودیت دامنه قیمت، وضعیت توقف، نقدشوندگی، روزهای معاملاتی و صنعت می‌توانند به‌عنوان context بررسی شوند، مشروط به وجود تاریخی و قابل‌اعتماد بودن آن‌ها.
- افق‌های پیش‌بینی و تایم‌فریم‌ها باید صریح باشند. ارزیابی روزانه و هفتگی با هم ادغام نمی‌شود.
- پیش‌بینی باید به شکل چند سناریو یا توزیع/بازه همراه با عدم‌قطعیت باشد، نه یک قیمت قطعی و ظاهراً دقیق.

### 8.4 Baseline و معیارهای ارزیابی

Kronos باید با این گروه‌ها مقایسه شود:

- Last-value / persistence و baselineهای naive؛
- میانگین تاریخی و baselineهای آماری؛
- مدل‌های tabular مانند LightGBM/CatBoost با Featureهای سری زمانی؛
- یک یا چند مدل sequence کوچک، فقط در صورت توجیه.

معیارهای ارزیابی:

- خطای OHLC یا بازده نرمال‌شده با نوسان؛
- خطای دامنه High-Low و تخمین Volatility؛
- Directional Accuracy و معیارهای مربوط به تغییر جهت؛
- Quantile Loss و پوشش واقعی Prediction Interval؛
- Calibration و پایداری افق‌های مختلف؛
- مقایسه با baseline در Walk-forward و Holdout قفل‌شده؛
- تحلیل جداگانه در بازار صعودی، نزولی، خنثی، پرنوسان، صف و توقف.

دقت پیش‌بینی به‌تنهایی اثبات سودآوری نیست. هر ارزیابی اقتصادی باید هزینه‌ها، محدودیت‌های بازار ایران و امکان واقعی اجرا را جداگانه لحاظ کند.

### 8.5 چرخه به‌روزرسانی

- روزانه داده جدید به Dataset و صف ارزیابی اضافه می‌شود.
- برچسب‌های هر افق زمانی در موعد مناسب بالغ می‌شوند.
- drift و افت عملکرد پایش می‌شود.
- Fine-tuning مجدد فقط با Dataset و Manifest نسخه‌دار انجام می‌شود.
- نسخه جدید ابتدا Challenger است و نسخه فعال تا عبور از Gate ثابت می‌ماند.
- ارتقای مدل، rollback و انتشار مدل نیازمند فرآیند کنترل نسخه و پذیرش است.

### 8.6 Runtime مدل

Fine-tuning می‌تواند در محیط Python/PyTorch انجام شود، ولی Production نباید به نصب Python یا اجرای یک Python server وابسته باشد.

مسیرهای inference مانند ONNX، runtime native یا sidecar باینری باید به‌صورت امکان‌سنجی مقایسه شوند. تا زمانی که خروجی برابر، سرعت، مصرف RAM/CPU، بسته‌بندی، آپدیت، rollback و پایداری روی ماشین هدف اثبات نشده، روش Runtime Kronos تصمیم قطعی نیست.

مدل و tokenizer باید همراه manifest، checksum، نسخه Feature Contract و نسخه Dataset/Training ثبت شوند. مدل بزرگ نباید بدون سنجش footprint به بسته اصلی تحمیل شود؛ امکان نصب اختیاری یا دریافت کنترل‌شده بعداً بررسی می‌شود.

---

## 9. قرارداد مشترک خروجی و Registry

تمام موتورهای تکنیکال باید از قراردادهای نسخه‌دار و قابل‌ردیابی استفاده کنند. Registry محل کشف، معرفی، نسخه‌بندی و کنترل قابلیت‌هاست؛ نه محل اجرای کد دلخواه.

برای هر Indicator/Detector/Model حداقل این موارد ثبت می‌شود:

- شناسه یکتا و نسخه؛
- نام فارسی و انگلیسی؛
- نوع: canonical FTS، deterministic pattern، adaptive model یا forecasting model؛
- خانواده و تایم‌فریم؛
- ورودی‌های لازم و minimum history؛
- price basis و Feature Contract؛
- منبع روش‌شناسی یا پیوند پژوهشی؛
- نسخه الگوریتم/مدل؛
- وضعیت اجرا و تازگی؛
- نقش و نوع خروجی؛
- محدودیت‌ها و وضعیت داده؛
- شواهد قابل مشاهده و شناسه آزمایش.

هر نتیجه باید بتواند این اطلاعات را حمل کند:

- symbol و timeframe؛
- as-of timestamp؛
- observed_at و confirmed_at، در صورت کاربرد؛
- data basis؛
- detector/model ID و version؛
- state و validity؛
- values، levels، zones یا forecast scenarios؛
- confidence/probability و calibration metadata، فقط برای مدل‌هایی که آن را معتبر تولید می‌کنند؛
- explanation/evidence؛
- Dataset/Feature/Ruleset identifiers.

خروجی مدل Forecast با خروجی Pattern Detector و Verdict رسمی FTS نوع یکسان ندارد و نباید در یک فیلد مبهم ادغام شود.

## 10. ارزیابی، ضدنشت و پذیرش

### 10.1 پروتکل عمومی

- تقسیم داده کاملاً زمانی باشد؛ random shuffle بین گذشته و آینده ممنوع است.
- از Walk-forward، Purging و Embargo متناسب با افق برچسب استفاده شود.
- Holdout نهایی قبل از انتخاب پارامترها قفل شود.
- تست generalization بین نمادها و صنایع به‌صورت جدا ثبت شود.
- اصلاحات تاریخی داده و Corporate Actionها در بازسازی point-in-time لحاظ شوند.
- تعداد آزمایش‌ها و انتخاب‌های تکراری ثبت شوند تا Multiple Testing و Overfitting پنهان نماند.
- هر ادعا باید نتیجه، dataset، کد، seed، تنظیمات و artifact قابل بازتولید داشته باشد.

### 10.2 پذیرش Detector

- تطبیق با تعریف هندسی و منبع؛
- تست مثبت، منفی، مرزی، داده ناقص و warm-up؛
- تست repaint و زمان تأیید؛
- تست تایم‌فریم و تغییر symbol؛
- تست ثبات خروجی بین API و دو موتور نمودار؛
- تست عملکرد روی مجموعه واقعی نمادها.

### 10.3 پذیرش Adaptive Model و Kronos

- عملکرد خارج از نمونه و در چند پنجره زمانی؛
- مقایسه با baseline؛
- کالیبراسیون و اندازه نمونه؛
- حساسیت به رژیم‌های متفاوت بازار؛
- آزمون drift و افت کیفیت؛
- CPU/RAM و زمان اجرا؛
- بازتولید آموزش و rollback؛
- تفکیک Forecast Quality از Economic/Trading Utility.

وضعیت هر معیار باید صریح باشد: PASS، FAIL، BLOCKED، NOT_MEASURED یا INSUFFICIENT_DATA.

---

## 11. تجربه کاربری و نمایش

- چارت قیمت باید کندل را عنصر اصلی نگه دارد.
- الگوها و لایه‌ها باید قابل روشن/خاموش کردن و دارای legend قابل فهم باشند.
- FTS، Pattern Library، Adaptive Assessment و Kronos Forecast در UI باید نام و نقش متمایز داشته باشند.
- نتیجه پیش‌بینی با داده واقعی کندل اشتباه گرفته نشود؛ کندل پیش‌بینی‌شده باید ظاهر و برچسب مجزا داشته باشد.
- احتمال موفقیت، محدوده عدم‌قطعیت و تعداد نمونه نمایش داده شود؛ درصد بدون توضیح مبنای آن مجاز نیست.
- timestamp، منبع، price basis، نسخه الگوریتم و stale/unknown بودن داده قابل مشاهده باشد.
- هیچ سیگنال یا نتیجه قدیمی پس از تغییر نماد، تایم‌فریم یا مبنای قیمت نباید به نماد جدید نشت کند.
- نمایشگر حق اصلاح یا بازتولید رأی Backend را ندارد.

---

## 12. ترتیب اجرای پیشنهادی

این معماری پیش‌نیاز Opportunity Lab است. اجرای آن باید بعد از بستن کارهای داده و Performance فعلی پروژه آغاز شود.

### Gate A — تکمیل داده و Performance

1. تکمیل Phase 4.9 و تصمیم‌های باقی‌مانده Adjustment Chain.
2. تکمیل Seed و اعتبارسنجی دیتابیس تاریخی قابل استفاده.
3. اجرای Phase 4.10 برای Benchmark و بهینه‌سازی SQLite و Go Backend.
4. تثبیت benchmark و data contracts برای تحلیل تکنیکال.

### TI-1 — Technical Intelligence Audit

- ممیزی Catalog و پیاده‌سازی‌های موجود؛
- تعیین EXISTS & VERIFIED، EXISTS BUT NEEDS FIX و MISSING؛
- تطبیق با جزوه، چارت، OWNER_RULINGS و اسناد parity؛
- جلوگیری از بازنویسی قابلیت‌هایی که از قبل سالم و canonical هستند؛
- ثبت Gapها و معیار پذیرش.

### TI-2 — FTS & Structural Foundation

- تأیید Data/Feature Contract؛
- تکمیل و آزمون Pivot، Structure، Daily/Weekly Trend و Weekly Gate؛
- بستن parity لایه‌های FTS موجود؛
- بررسی Jet، Pullback، Fibonacci، CHoCH، Point Hunt، الگوهای دوقلو، Third Peak، Range Box و Exitها؛
- اثبات API و دو موتور رندر با خروجی canonical یکسان.

### TI-3 — Classical Pattern Library

- تعریف قرارداد مشترک Detector؛
- اولویت‌بندی و پیاده‌سازی الگوهای کلاسیک؛
- تست هندسه، تشکیل/ابطال و زمان تأیید؛
- نگه‌داشتن همه موارد خارج از FTS canonical مگر رأی صریح مالک.

### TI-4 — Outcome Ledger & Adaptive Learning

- ثبت همه نمونه‌های مثبت و منفی؛
- delayed labeling و no-fill semantics؛
- ساخت baselineها؛
- ارزیابی KNN/Pattern Memory و مدل‌های tabular؛
- Champion/Challenger و پایش drift.

### TI-5 — Kronos Iran Adaptation

- تثبیت Dataset و baseline؛
- ارزیابی pretrained؛
- Fine-tuning روی دیتابیس بورس ایران؛
- ارزیابی Walk-forward و Holdout؛
- آزمون Runtime native و بسته‌بندی بدون Python؛
- فعال‌سازی فقط پس از عبور از Gate.

### TI-6 — Integration & Stability

- اتصال نتایج به چارت و پنل تکنیکال؛
- تست سراسری تغییر نماد، تایم‌فریم، مبنا و داده stale؛
- benchmark واقعی CPU/RAM و Startup؛
- versioning، rollback و observability؛
- تثبیت API قابل‌مصرف برای Opportunity Lab.

### بعد از TI-6 — Opportunity Lab

Opportunity Lab مصرف‌کننده این زیرساخت‌ها خواهد بود. وظایف آن شامل ترکیب ساختاریافته Strategy، تولید فرضیه، Backtest، Validation، مقایسه و Registry است؛ نه بازسازی Detectorها، آموزش Kronos یا محاسبه مجدد FTS.

ترتیب و جزئیات Opportunity Lab باید در بازبینی مستقل اسناد Phase 5 و با توجه به وضعیت واقعی TI-1 تا TI-6 تعیین شود.

---

## 13. خارج از دامنه فعلی

موارد زیر در این سند به‌عنوان کار فعلی مجاز نشده‌اند:

- ساخت یا فعال‌سازی Opportunity Lab؛
- تغییر قواعد FTS یا thresholdهای منبع؛
- ارتقای خودکار مدل به Approved/Stable؛
- ارسال سفارش واقعی یا اجرای خودکار معامله؛
- اتصال اجباری به سرویس Cloud یا GPU خارجی؛
- افزودن Python به نصب Production؛
- انتقال داده کاربر به خارج از سیستم؛
- جایگزینی دیتابیس یا Backend فعلی بدون شواهد و تصمیم معماری جداگانه؛
- استفاده از پیش‌بینی مدل به‌عنوان سیگنال قطعی خرید یا فروش.

AutoTrader و اجرای سفارش، در صورت تصمیم مالک، مأموریت مستقل و نیازمند زیرساخت و کنترل‌های جداگانه خواهند بود.

## 14. تصمیم‌های باز که باید با شواهد بسته شوند

1. نسخه دقیق Kronos، checkpoint، tokenizer، license و روش Fine-tuning.
2. Datasetهای قابل استفاده، پوشش تاریخی و مرز raw/adjusted.
3. افق‌های اولیه Forecast و تایم‌فریم‌های پشتیبانی‌شده.
4. Runtime native مناسب Kronos و footprint واقعی آن.
5. مجموعه اولیه الگوهای کلاسیک برای TI-3.
6. Label horizon، تعریف دقیق success/failure و فرض اجرای قابل‌معامله برای هر الگو.
7. معیارهای Gate برای ارتقای Champion به Challenger.
8. سیاست نگهداری نسخه‌های مدل و Dataset.
9. حداقل تعداد نمونه برای نمایش احتمال/اطمینان هر خانواده.
10. اولویت‌بندی نهایی بر اساس نتیجه Audit مرحله TI-1، نه صرفاً تعداد قابلیت‌ها.

هیچ‌یک از این موارد با حدس یا انتخاب خودکار بسته نمی‌شوند؛ شواهد و گزینه‌های تصمیم به مالک ارائه می‌شوند.

---

## 15. منابع پروژه و تقدم آن‌ها

منابع زیر باید هنگام هر مأموریت دوباره با کد و شاخه جاری تطبیق داده شوند:

- [جزوه رسمی FTS](جزوه%20FTS.pdf)
- [چارت چهارصفحه‌ای FTS](FTS.CHART_3.pdf)
- [FTS Specification](FTS_SPEC.md)
- [FTS Rule-to-Algorithm Map](FTS-RULE-ALGORITHM-MAP.md)
- [FTS Indicator Mission Plan](FTS-INDICATOR-MISSION-PLAN.md)
- [FTS Indicator Catalog](../frontend/src/features/technical/lib/ftsIndicatorCatalog.ts)
- [Owner Rulings](fts-notes/OWNER_RULINGS.md)
- [Technical Engine Signal Lab](fts-notes/TECHNICAL-ENGINE-SIGNAL-LAB.md)
- [Technical PDF Evidence Audit](fts-notes/TECHNICAL-PDF-EVIDENCE-AUDIT-1405-07-13.md)
- [FTS Algorithm Verification](technical-indicators/reviewed/FTS-ALGORITHM-VERIFICATION-1405-07-20.md)

تقدم روش‌شناسی در صورت تعارض:
1. رأی صریح و جاری مالک؛
2. جزوه و چارت اصلی FTS؛
3. اسناد فنی استخراج‌شده؛
4. parity/audit و کد جاری.

این سند معماری، مرجع جدید قواعد FTS نیست؛ فقط معماری ساخت و اتصال موتورهای تکنیکال و یادگیری را تعریف می‌کند.

---

## 16. Financial ML Research Methodology, Labeling & Validation

**Status:** This section adds research-method requirements to the two independent learning tracks. It does not replace the four-engine architecture, change canonical FTS rules, select a final model, or authorize Production activation.

### 16.1 Hypothesis-first research

Every experiment must start with a falsifiable research question, not with searching for a parameter set that produces an attractive historical result.

Record for each hypothesis:

- The market phenomenon or mechanism being investigated.
- The eligible instruments, universe, timeframe and market regimes.
- The decision timestamp and information available at that time.
- The features and their economic or technical rationale.
- The target, label horizon and executable-entry assumption.
- What observations would support the hypothesis and what observations would contradict it.
- Dataset snapshot, code revision, feature contract, model configuration and all prior trials.

Machine learning can discover candidate variables, nonlinear relationships, peer groups and interactions. Predictive association or feature importance does not establish causation. State the proposed mechanism separately and test implications beyond the backtest used to discover it.

A backtest is a historical simulation, not a controlled experiment and not proof of a causal market mechanism. A poor result is evidence to examine the hypothesis, data and assumptions; it is not permission to repeatedly tune the same Holdout until the result looks good.

**FTS boundary:** canonical FTS rules remain defined by their existing source documents and owner rulings. ML may assess historical context or outcome quality, but cannot rewrite, approve, stabilize or silently modify a canonical FTS rule.

### 16.2 Point-in-time data and information availability

Every training row must be reconstructible as of its historical decision time.

Distinguish where applicable:

- event_time: when the market event or source fact applies;
- published_at: when information became publicly available;
- observed_at: when BorsTerminal received or captured it;
- effective_at: when it became effective in the market or issuer data;
- decision_at: when the model is assumed to make its prediction;
- execution_at: the earliest defensible time a hypothetical action could be executed.

A feature is eligible only if it was available by decision_at. Do not apply an unconditional one-bar shift as a substitute for this contract. A post-close model may use the completed close once it is available, but execution must occur at the next feasible opportunity. An intraday model cannot use the final close of a still-forming session.

Historical fundamental data must use the publication/as-of version available at decision time, not the latest restated value. Corporate actions, adjustment factors, symbol identity changes, suspensions, listings/delistings and universe membership must be reconstructed point-in-time where source history permits. Survivorship and backfill limitations must be measured and reported.

Raw and adjusted price bases remain separate, explicit and versioned. A Dataset must never silently combine them.

For multi-symbol panels, a date belongs to one temporal split across the universe. Do not place one symbol's observation from a date in training while another symbol's observation from the same date is in testing when the purpose is future-time generalization. Cross-sectional ranks and industry-relative features must use the historically eligible universe at that timestamp, not today's surviving universe.

### 16.3 Financial data structures and sampling

Time-based daily and weekly bars are the initial canonical basis because they align with the available OHLCV history and current product semantics.

Alternative sampling methods such as tick, volume, dollar/value, imbalance or run bars may be evaluated only when the corresponding historical transaction or trade-flow data exists with adequate coverage and quality. Daily OHLCV candles cannot be used to fabricate intraday bars or microstructure history.

Every sampling method must declare its source fields, sampling rule, timestamp convention, minimum history, warm-up, missing-session and halted-symbol behavior, price basis, adjustment revision, Dataset snapshot and overlap with other observations.

A sampling change creates a new Dataset and Feature Contract version and requires a fresh baseline comparison. It cannot silently replace the canonical daily/weekly series.

### 16.4 Feature engineering and selection

The Feature Layer remains shared infrastructure, but each research track owns its own Dataset schema and target.

1. Fit learned preprocessing only on the training partition of each fold. This includes scaling, imputation, dimensionality reduction, feature selection, denoising and clustering.
2. Preserve point-in-time availability and explicit warm-up or insufficient-data states.
3. Use price, volatility, volume, liquidity, market-regime, industry and event-context features only when historical availability and coverage are demonstrated.
4. Do not treat missing values as zero or as a negative market signal.
5. Version feature definitions, parameters, units, lookback, timeframe and source.

Candidate feature families include returns and momentum, realized volatility and ATR, candle geometry, volume/value ratios, market breadth, relative industry behavior, structural pivots and trend, distances to levels and market-state context. Inclusion is experimental, not automatic.

Evaluate feature relevance out-of-sample. Permutation or Mean Decrease Accuracy can estimate how much held-out predictive performance changes when a feature is disrupted. Correlated or substitutable features may require grouped analysis. In-sample tree impurity importance alone is insufficient for acceptance. Feature importance indicates predictive information under a particular experiment; it does not prove a causal mechanism.

Fractional differentiation, covariance denoising/detoning, information-theoretic distances, PCA and clustering are optional research techniques, not mandatory preprocessing. Compare each with an untransformed baseline and examine information loss, stability, leakage and actual benefit. Do not apply fractional differentiation to Kronos sequences without proving compatibility with the model's expected representation.

### 16.5 Adaptive Signal Intelligence: event labels and Outcome Ledger

Adaptive Signal Intelligence is an event/outcome problem, not a generic row-wise price-direction classifier.

For every confirmed Detector event, preserve:

- Detector ID/version and canonical-versus-independent status;
- symbol, timeframe, event/observed/confirmed timestamps;
- side or direction, if supplied by the Detector;
- feature snapshot strictly as of decision time;
- reference entry assumption and earliest executable time;
- profit/target barrier, stop/invalidation barrier and vertical/time barrier;
- outcome interval from event start through outcome end;
- realized outcome, fill feasibility and data-quality status;
- Dataset, Feature Contract, label-method and ruleset versions.

Fixed-horizon labels are a baseline. Event-driven labels may use Triple Barrier design: an upper profit/target barrier, a lower stop/invalidation barrier and a vertical time barrier. Volatility-scaled thresholds may be tested where meaningful. Barrier sizes, side and horizon must be specified per Setup family and reflect plausible execution assumptions; they are not universal constants.

Where a canonical FTS or deterministic Detector already supplies a side, an Adaptive model may act as a separate quality/meta-labeling layer that estimates conditional outcome or adds caution. It does not alter the FTS rule or Detector verdict. Where no defensible side exists, define a separate prediction problem rather than inventing one.

The Outcome Ledger must support at least:

- PENDING: the outcome interval has not matured;
- TARGET_FIRST;
- STOP_FIRST;
- VERTICAL_HORIZON;
- NO_FILL;
- HALTED_OR_UNTRADEABLE;
- INVALIDATED;
- INSUFFICIENT_DATA.

A label remains pending until its full outcome interval is observable. Do not label an event successful merely because a target was touched in an incomplete path. Where target and stop are both crossed inside one OHLC bar and intrabar order is unavailable, use an explicit conservative or unknown policy; never invent event order from OHLC alone.

Keep all eligible events, including failures, expired events, stopped events, no-fill and untradeable cases. Filtering the ledger to successful or executable-looking examples creates selection bias.

### 16.6 Overlapping outcomes and sample uniqueness

Event labels frequently overlap in calendar time. If two labels depend on common future returns or market bars, they are not independent observations.

For event-based training:

- record each label's information interval, from decision/start time through outcome end;
- compute concurrent-label counts and average uniqueness where appropriate;
- report overlap and effective sample information, not only raw row count;
- evaluate uniqueness-based sample weights against an unweighted baseline;
- test time-decay and class weights as separate, versioned experiments.

Sample weighting must not make the effective sample size appear larger than it is. Reports must include raw event count, matured label count, class distribution, concurrency/uniqueness statistics and weighted effective contribution.

### 16.7 Financial validation protocol

The validation design must reflect the intended use of the model. Randomly shuffled K-Fold or Stratified K-Fold is not an acceptable primary evaluation method for financial time series.

**A. Chronological Walk-Forward**

- Train only on information preceding each test window.
- Use rolling or expanding training windows with explicit dates.
- Refit preprocessing and model selection inside each training window.
- Evaluate each future window once according to a predeclared schedule.
- Aggregate results by period, symbol, industry and market regime.

**B. Purging and Embargo for overlapping labels**

For event labels with outcome intervals, remove training observations whose label-information intervals overlap test-label intervals. Apply an embargo after test intervals where residual serial dependence or feature construction can still transmit information. Purge and embargo widths must derive from actual label and feature information horizons, not arbitrary fixed day counts.

**C. Cross-sectional and generalization tests**

Report separately:

- future-time generalization on instruments represented during training;
- unseen-symbol or held-out-instrument generalization;
- industry transfer where sufficient data exists;
- performance by market regime and liquidity tier.

Do not merge these into one score.

**D. CPCV as a complementary research diagnostic**

Combinatorial Purged Cross-Validation may estimate dispersion across multiple backtest paths and diagnose sensitivity to sample selection, provided label-overlap purging and embargo are correct. CPCV is not a replacement for realistic chronological Walk-Forward simulation or a final locked future Holdout. Some CPCV training partitions may contain observations later than a particular test partition; those paths must not be presented as literal historical deployment simulations.

**E. Locked final Holdout**

Reserve a final chronological period before model, feature or threshold selection begins. Do not use it for feature selection, tuning, threshold design, repeated hypothesis debugging or model ranking. If the Holdout is inspected and then used to change the research, it is no longer untouched; a new future period is required.

The evaluation harness must include negative controls that prove it detects date leakage, label-interval overlap, cross-symbol date splitting, preprocessing fitted outside the fold and accidental Holdout reuse.

### 16.8 Model selection, multiple testing and research ledger

Use a model ladder rather than assuming a complex method is superior:

- naive/persistence and simple statistical baselines;
- regularized linear/logistic models;
- nearest-neighbor and simple distance baselines;
- tree/ensemble methods such as Random Forest, Gradient Boosting, LightGBM or CatBoost;
- sequence/deep models only when data structure and baseline evidence justify them.

All hyperparameter tuning, feature selection, threshold search, Detector parameter variations, label alternatives, model families and repeated experiments count as trials. Record them in an experiment ledger with code/data/configuration hashes and outcomes, including discarded experiments.

The same Holdout must not become an iterative tuning surface. Where many strategies or models are selected from multiple trials, assess selection bias using suitable methods such as family-wise error controls, Deflated Sharpe Ratio or Probability of Backtest Overfitting where their assumptions fit the question. These statistics are not universal pass/fail constants; document assumptions, number of trials, dependence structure and interpretation. Never report only the best-performing trial while omitting the search process.

### 16.9 Separate evaluation contracts for the two model tracks

The tracks share validated data and eligible Feature infrastructure, but keep independent targets, experiments, model registries, metrics and release gates.

**Kronos Forecasting Track**

- Target: future OHLCV sequence/distribution for explicitly declared horizons and timeframes.
- Keep raw and adjusted experiments separate.
- Evaluate pretrained models before fine-tuning.
- Compare with persistence/last-value, statistical and lightweight tabular/sequence baselines.
- Report normalized OHLC error, volatility/range error, directional measures, quantile loss and prediction-interval coverage/calibration by horizon.
- Do not turn a point forecast or one predicted candle into a deterministic trade signal.
- Forecast quality and economic/trading utility are separate evaluation questions.

**Adaptive Signal Intelligence Track**

- Target: outcome probability/quality for a specific Detector or Setup under an explicit label and execution contract.
- Compare Logistic/regularized baselines, tree ensembles and pattern-memory approaches.
- Report class balance, sample count, PR-AUC where useful, Log Loss, Brier Score, calibration, base rates and performance by Setup, regime, symbol/industry and time window.
- Probability output must include calibration metadata, matured sample count and horizon. Do not display a confidence percentage when the model is uncalibrated or sample support is insufficient.
- Outcome probabilities must not be silently merged into Kronos forecasts or canonical FTS verdicts.

### 16.10 Economic and execution realism

Forecast or classification metrics do not establish a tradable edge.

Any economic evaluation must state:

- decision time and executable entry time/price;
- whether assumed entry is next open, next executable quote/trade or another defensible convention;
- commissions, taxes, exchange/broker fees and spread where applicable;
- slippage, market impact, partial fills and no-fill conditions;
- price limits, queues, suspensions, reopening and local execution constraints;
- turnover, liquidity capacity and concentration;
- long/short assumptions only where the instrument and market rules actually permit them.

A close-to-close forecast made after the close cannot be backtested as if the order had been filled at that same close. US-market examples, short-selling assumptions and generic basis-point cost values must not be copied into the Iranian market without local validation.

Keep Forecast Quality, Detector/Label Quality and Economic Utility as three separate result layers.

### 16.11 Synthetic experiments and rare-regime stress tests

Synthetic or Monte Carlo data may test statistical procedures, stress assumptions and explore underrepresented scenarios. Each synthetic Dataset must record its data-generating process, fitted parameters, random seed and limits of representativeness.

Synthetic data must be marked as synthetic. It must never count as observed Iranian market history, claim historical coverage, or replace the locked real-data Holdout. Rare-event stress results are conditional on the realism of the assumed process.

### 16.12 Model lifecycle and controlled deployment

After research acceptance, a model follows:

Research → Candidate → Shadow → Champion/Challenger → Accepted Runtime → Retired

- A Candidate first runs in shadow against live or replayed data without changing canonical FTS or generating orders.
- Monitor prediction quality, calibration, data drift, regime drift, feature availability, stale inputs, latency, CPU/RAM and failure states.
- Champion/Challenger comparisons use a declared observation window and independent acceptance metrics.
- Keep prior accepted models and Dataset/Feature contracts for rollback.
- Retraining does not automatically promote a model.
- This methodology does not authorize automatic strategy approval, auto-trading or order submission.

### 16.13 Mandatory research artifacts

Every experiment must produce a reproducible record containing at least:

- hypothesis ID/version;
- repository, commit SHA and working-tree status;
- Dataset snapshot ID, manifest and checksums;
- point-in-time, universe and price-basis contract;
- feature schema/version and preprocessing fit scope;
- label definition, side, information interval and execution assumptions;
- train/validation/test dates and symbol-group policy;
- purge/embargo/CPCV configuration where applicable;
- model/library/checkpoint/tokenizer versions and hyperparameters;
- random seeds and hardware/runtime details;
- all trial identifiers, not only the selected trial;
- per-fold, per-period, per-symbol and per-regime metrics;
- baseline comparisons, calibration and uncertainty;
- failed/negative controls and known limitations;
- final verdict: PASS, FAIL, BLOCKED, NOT_MEASURED or INSUFFICIENT_DATA.

A result without its Dataset, code, configuration and split definitions is not an accepted research result.

### 16.14 Methodological implementation order

Apply these foundations before large-scale model training:

1. Research Hypothesis and Experiment Registry.
2. Point-in-time Market Data/Feature Contract and reproducible Dataset Snapshots.
3. Timestamp-aware panel split engine with Walk-Forward and held-out-symbol tests.
4. Event information-interval schema, delayed labels, purging and embargo.
5. Outcome Ledger with execution and no-fill semantics.
6. Baselines and metrics for Kronos and Adaptive separately.
7. Feature-importance, trial-count and multiple-testing controls.
8. Training, tuning and model-lifecycle automation only after the previous contracts are testable.

This order is a methodology prerequisite, not a commitment to implement every advanced AFML technique immediately. Optional methods must demonstrate value on BorsTerminal data and remain separately versioned.

### 16.15 Source basis and reading map

This methodology adapts relevant ideas from the following sources to BorsTerminal's two research tracks. It does not adopt every method or market assumption wholesale.

- Quantt, Machine Learning for Trading Tutorial (2026): practical workflow from target definition and features to validation, backtesting and monitoring. https://www.quantt.co.uk/resources/machine-learning-for-trading-tutorial
- Marcos M. López de Prado, Advances in Financial Machine Learning (Wiley, 2018): especially Chapters 2–9 and 11–15 for financial data structures, labeling, sample uniqueness/weights, ensembles, Purged K-Fold/Embargo, feature importance, tuning, backtest risk, CPCV and backtest statistics. Official publisher: https://www.wiley.com/en-us/advances-in-financial-machine-learning-p-9781119482086 . Public chapter map/previews: https://www.oreilly.com/library/view/advances-in-financial/9781119482086/p00.xhtml
- Marcos M. López de Prado, Machine Learning for Asset Managers (Cambridge University Press, 2020): theory-first research, variable-search/specification-search separation, train/test overfitting, feature importance, denoising, distance metrics, clustering, financial labels and testing-set overfitting. Publisher: https://www.cambridge.org/core/elements/abs/machine-learning-for-asset-managers/6D9211305EA2E425D33A9F38D0AE3545 . Publisher excerpt: https://assets.cambridge.org/97811087/92899/excerpt/9781108792899_excerpt.pdf
- Trevor Hastie, Robert Tibshirani and Jerome Friedman, The Elements of Statistical Learning, 2nd ed. (Springer, 2009): Chapters 2–5, 7–10, 12–16 and 18 for supervised learning, regression/classification, regularization, model assessment, trees/boosting, nearest neighbors, unsupervised learning, random forests, ensembles and high-dimensional issues. Publisher: https://link.springer.com/book/10.1007/978-0-387-84858-7
- Marcos López de Prado, The 10 Reasons Most Machine Learning Funds Fail (2018): supplementary discussion of common financial-ML failure modes. https://ssrn.com/abstract=3104816
- Hudson & Thames MLFinLab documentation: implementation reference for Purged/Embargo CV and CPCV; use as an implementation aid, not as a replacement for verifying the mathematics and adapting multi-symbol date grouping. https://random-docs.readthedocs.io/en/latest/implementations/cross_validation.html

The original architecture Sections 1–15, FTS source precedence, model/runtime boundaries and independent Kronos/Adaptive split remain in force. This section adds research-method discipline; it does not change canonical FTS methodology.
