# سند طراحی معماری: موتورهای تولید داده، خط لولهٔ کدال و همگام‌سازی پس‌زمینه در Go (مرحله ۳)
# (Stage 3 Design: Go Data Producers, CODAL Pipeline & Background Ingestion)

- **تاریخ:** ۲۰۲۶-۱۱-۰۸ (۱۷ آبان ۱۴۰۵)
- **شاخه:** `mission/stage3-go-data-producers-2026-11-07`
- **خط مبنا (Baseline):** `aca7c465df207d9e55fccfecf23b3759b110bea7`
- **وضعیت:** طراحی مصوب با تفکیک دو باینری (`borsd` برای کلاینت دسکتاپ و `bors-producer` برای خط لوله مرکزی داده).

---

## ۱. بیانیهٔ مأموریت و اهداف معماری

مرحلهٔ ۲ با موفقیت زمان اجرای کلاینت دسکتاپ را به ترکیب سه‌گانهٔ Go + Frontend-V2 + Tauri منتقل نمود و پایتون را به طور کامل از بسته نصبی حذف کرد. هدف مرحلهٔ ۳، **حذف کامل و قطعی وابستگی‌های عملیاتی پایتون در زنجیرهٔ تأمین، واکشی، استخراج، اعتبارسنجی و انتشار داده‌ها** است.

### اصول بنیادین معماری:
۱. **تفکیک کامل Producer و Client:**
   - باینری `borsd`: کلاینت دسکتاپ کاربران که دیتابیس‌های `market.db` و `codal.db` را منحصراً در حالت فقط‌خواندنی (`mode=ro`) باز می‌کند و فاقد هرگونه اسکرپر یا خزندهٔ تهاجمی به سمت کدال است. کلاینت فقط اسنپ‌شات‌های امضاشده را دریافت و به صورت اتمیک اعمال می‌نماید.
   - باینری `bors-producer`: ابزار مستقل خط فرمان و سرویس دیمن مخصوص سرور/ادمین مرکزی که وظیفهٔ کشف اطلاعیه‌ها، استخراج داده‌ها، اعتبارسنجی، محاسبهٔ مجدد FTS، دریافت داده‌های TSETMC، ساخت اسنپ‌شات‌های فشرده LZMA، امضای دیجیتال با کلید خصوصی minisign و انتشار به مخزن داده را بر عهده دارد.
۲. **کدبیس مشترک در یک مخزن (Monorepo Shared Go Packages):**
   هر دو باینری در پوشه `backend-go/cmd/` قرار داشته و از بسته‌های داخلی مشترک در `backend-go/internal/` (شامل لایه‌های دیتابیس، تحلیل بنیادی FTS، محاسبات دوره‌ای، قرارداد کندل‌ها و توابع رمزنگاری) بهره می‌برند.
۳. **تک‌نویسنده بودن دیتابیس‌ها (Single-Writer Invariant):**
   هیچ دو فرآیندی اجازهٔ نوشتن هم‌زمان بر روی یک دیتابیس را ندارند. اعمال اسنپ‌شات در کلاینت بدون آسیب به خواننده‌های فعال انجام می‌پذیرد.
۴. **حذف ترفندهای ناپایدار (ADB / CAPTCHA Bypass):**
   فرآیند کشف داده‌ها بر پایهٔ کادنس تطبیقی، احترام به سرفصل `Retry-After`، الگوریتم Exponential Backoff با Jitter و Circuit Breaker پایدار پیاده‌سازی می‌شود.

---

## ۲. نمای کلی معماری و توپولوژی سیستم

```mermaid
flowchart TD
    subgraph ExternalSources ["منابع خارجی داده"]
        CodalSearch["سامانه جستجوی کدال (search.codal.ir)"]
        CodalReports["صفحات گزارش کدال (codal.ir/Reports)"]
        TSETMC["سرورهای داده TSETMC (cdn.tsetmc.ir)"]
    end

    subgraph CentralProducer ["محیط مرکزی: باینری bors-producer"]
        WorkerOrch["هماهنگ‌کننده Workerها و زمان‌بند تطبیقی"]
        CodalPipeline["پایپ‌لاین کدال (کشف، واکشی، استخراج، اعتبارسنجی)"]
        MarketPipeline["پایپ‌لاین بازار (تابلو، حقیقی/حقوقی، تاریخچه، تعدیل)"]
        FTSEngine["موتور باز‌محاسبه پنج شاخص بنیادی FTS"]
        SnapshotBuilder["سازنده اسنپ‌شات LZMA و متادیتا"]
        Signer["امضاکننده دیجیتال Minisign (Private Key)"]
        Publisher["ناشر دارایی‌ها در تگ داده گیت‌هاب (data-codal / data-latest)"]
    end

    subgraph DistributionLayer ["لایه توزیع مستقل داده"]
        DataCodalTag["GitHub Release Tag: data-codal\n(codal.db.lzma + sig + meta.json)"]
        DataMarketTag["GitHub Release Tag: data-latest\n(market.db.lzma + sig + meta.json)"]
    end

    subgraph DesktopClient ["دسکتاپ کاربر: باینری borsd + Tauri"]
        ClientSyncWorker["Worker درون‌برنامه‌ای دریافت اسنپ‌شات"]
        SignatureVerifier["اعتبارسنجی امضای دیجیتال Minisign (Public Key)"]
        AtomicApplier["تعویض اتمیک دیتابیس (Atomic File Swap)"]
        LocalCodalRO[("codal.db (mode=ro)")]
        LocalMarketRO[("market.db (mode=ro)")]
        LocalUserRW[("user.db (mode=rwc)")]
        GoAPI["Go HTTP API (:8198)"]
        FrontendV2["React TypeScript (UI)"]
    end

    %% اتصالات
    CodalSearch --> CodalPipeline
    CodalReports --> CodalPipeline
    TSETMC --> MarketPipeline
    WorkerOrch --> CodalPipeline
    WorkerOrch --> MarketPipeline
    CodalPipeline --> FTSEngine
    FTSEngine --> SnapshotBuilder
    MarketPipeline --> SnapshotBuilder
    SnapshotBuilder --> Signer
    Signer --> Publisher
    Publisher --> DataCodalTag
    Publisher --> DataMarketTag

    DataCodalTag --> ClientSyncWorker
    DataMarketTag --> ClientSyncWorker
    ClientSyncWorker --> SignatureVerifier
    SignatureVerifier --> AtomicApplier
    AtomicApplier --> LocalCodalRO
    AtomicApplier --> LocalMarketRO
    LocalCodalRO --> GoAPI
    LocalMarketRO --> GoAPI
    LocalUserRW --> GoAPI
    GoAPI --> FrontendV2
```

---

## ۳. طراحی تفصیلی زیرسیستم‌ها (Workstreams)

### بخش ۱: زیرسیستم خط لولهٔ کدال و بازمحاسبهٔ FTS (Workstream A)

این زیرسیستم مسئولیت کامل واکشی، پردازش و اعتبارسنجی اطلاعات کدال را در قالب پکیج `backend-go/internal/codal/` بر عهده دارد:

#### ۱. کشف اطلاعیه‌ها (Discovery Engine):
- **فراخوانی فید سراسری:** درخواست به `https://search.codal.ir/api/search/v2/q` با پارامترهای:
  - `Category=1` (صورت‌های مالی)
  - `Category=3` (گزارش فعالیت ماهانه)
  - `Publisher=false`، `TracingNo=-1`
- **مدیریت نشانک (Incremental Cursor):** نشانک در جدول `pipeline_cursor` نگهداری می‌شود. نشانک تنها پس از تکمیل موفق و کامل یک صفحه جلو می‌رود تا در صورت کرش یا قطعی اینترنت، هیچ اطلاعیه‌ای از قلم نیفتد.
- **حذف تکراری (Deduplication):** کلید `tracing_no` به عنوان شناسهٔ یکتا در جدول `codal_notices` درج می‌گردد (`INSERT OR IGNORE`).

#### ۲. دریافت محتوا و استخراج (Content Fetcher & Extractor):
- **واکشی صفحات:** دریافت مستقیم صفحات HTML از `codal.ir/Reports/Decision.aspx` (عدم نیاز به دانلود PDF یا Excel).
- **استخراج تولید و فروش ماهانه (`monthly_sales`):**
  - استخراج درآمد ماه جاری (`monthly_revenue`)، درآمد تجمعی از ابتدای سال مالی (`ytd_revenue`)، درآمد ماه مشابه سال قبل، حجم فروش و واحد فروش.
- **استخراج صورت‌های مالی (`financial_statements`):**
  - استخراج ارقام ترازنامه و سود و زیان: درآمد عملیاتی (`revenue`)، سود ناخالص (`gross_profit`)، سود عملیاتی (`operating_profit`)، سود خالص (`net_profit`)، جمع دارایی‌ها، بدهی‌ها، حقوق صاحبان سهام، سرمایه ثبت‌شده، سود انباشته و سود هر سهم (`basic_eps`).
  - تشخیص وضعیت حسابرسی‌شده (`is_audited`)، تلفیقی (`is_consolidated`) و طول دوره مالی (`period_months`).

#### ۳. اعتبارسنجی داده‌ها و قوانین دوره‌ها (Validation & Periods Gate):
- **انطباق هویت نماد و ناشر:** اعتبارسنجی با جدول `instruments` دیتابیس مارکت جهت جلوگیری از اتصال گزارش یک نماد به شرکت دیگر.
- **اعمال قرارداد دوره‌های کدال (`codal_periods`):** تاریخ‌های پایان دوره به صورت استاندارد شمسی `YYYY/MM/DD` اعتبارسنجی و نرمال‌سازی می‌شوند.
- **قرنطینه داده‌های معیوب:** در صورت بروز خطای ساختاری یا اعتبارسنجی، ردیف در جدول `codal_quarantine` ذخیره می‌شود و چرخه متوقف نمی‌گردد.

#### ۴. بازمحاسبهٔ هدفمند پنج شاخص بنیادی FTS (تطبیق ۱۰۰٪ با جزوه FTS):
- **اصل عدم تغییر و عدم ساده‌سازی فرمول‌ها:** محاسبات پنج شاخص بنیادی دقیقاً و عیناً مطابق با فرمول‌ها، نسبت‌ها، آستانه‌ها و شروط تفکیک صنعت جزوه رسمی FTS (`docs/جزوه FTS.pdf`) و موتور Go موجود در `backend-go/internal/fundamental/` انجام می‌شود. هیچ فرمول، آستانه یا شرط اعتباری به بهانه مهاجرت ساده‌سازی نخواهد شد.
- **نشانه‌گذاری Dirty:** با ورود دادهٔ جدید، تنها نمادهای متأثر در جدول `pipeline_dirty` درج می‌شوند.
- **محاسبه مجدد با موتور Go (`backend-go/internal/fundamental/`):**
  - محور ۱: نرخ رشد فروش ماهانه و فروش تجمیعی ۳ ماهه.
  - محور ۲: پایداری و روند سودآوری EPS (حداقل ۴ تا ۸ دوره گذشته).
  - محور ۳: حاشیه سود ناخالص و پایداری آن.
  - محور ۴: نسبت ارزش بازار به فروش (P/S) و اهرم مالی.
  - محور ۵: داوری صنعت و شروط اختصاصی بانکی/دارویی/بیمه‌ای.
- نتایج در جدول `fts_results` در دیتابیس مارکت به‌روزرسانی می‌شوند.

---

### بخش ۲: زیرسیستم اسنپ‌شات، امضا و پروتکل تعویض اتمیک ویندوز (Workstream B)

این زیرسیستم ارتباط میان Producer مرکزی و کلاینت‌های دسکتاپ را مدیریت می‌نماید (`backend-go/internal/snapshot/`):

#### ۱. سازگاری مجموعه‌ای اسنپ‌شات (Snapshot Consistency & Manifest):
- **شناسه مجموعه مشترک (`snapshot_set_id`):** هر بیلد اسنپ‌شات یک شناسه یکتا (نظیر `set_20261108_01`) تولید می‌کند که به طور مشترک متعلق به نسخه متناظر `market.db` و `codal.db` است.
- **سند مانیفست امضاشده (`manifest.json`):**
  ```json
  {
    "snapshot_set_id": "set_20261108_01",
    "created_at_utc": "2026-11-08T03:00:00Z",
    "schema_version": 2,
    "assets": {
      "codal": {
        "filename": "codal.db.lzma",
        "sha256": "3a8c5f...4b",
        "size": 3116840
      },
      "market": {
        "filename": "market.db.lzma",
        "sha256": "e7df91...1a",
        "size": 78667800
      }
    }
  }
  ```
- **ترتیب انتشار امن (Publish Sequence):**
  1. ابتدا فایل‌های حجیم دیتابیس (`codal.db.lzma` و `market.db.lzma`) و متادیتای هریک آپلود می‌شوند.
  2. دسترسی‌پذیری و صحت هش آن‌ها با درخواست آزمایشی به مخزن تایید می‌شود.
  3. در پایان و تنها پس از اطمینان از استقرار موفق تمامی Assetها، فایل `manifest.json` به همراه امضای دیجیتال `manifest.json.sig` منتشر می‌گردد. کلاینت تا قبل از دریافت مانیفست کامل هیچ اقدامی انجام نمی‌دهد.

#### ۲. امضای دیجیتال و امنیت کلیدها:
- فایل مانیفست و اسنپ‌شات‌ها توسط کلید خصوصی minisign امضا می‌شوند.
- **عدم افشای توکن و کلید:** توکن GitHub و کلید خصوصی امضا منحصراً از متغیرهای محیطی (`GITHUB_TOKEN` و `BORS_MINISIGN_SECRET_KEY`) یا مخزن امن سیستم خوانده می‌شوند و هرگز در پارامترهای خط فرمان (CLI Arguments) پاس داده نمی‌شوند تا در تاریخچه شل یا فهرست پردازه‌ها افشا نگردند.
- کلاینت دسکتاپ با کلید عمومی تعبیه‌شده (`UPDATE_PUBKEY`) اصالت امضا را بررسی می‌کند.

#### ۳. پروتکل قطعی تعویض اتمیک در ویندوز (Windows Atomic Ingestion via Generations):
به دلیل محدودیت‌های قفل فایل در ویندوز و جلوگیری از برخورد با خواننده‌های فعال:
1. **مسیر Staging روی همان Volume مقصد:** دانلود، اکسترکت و بررسی سلامت فایل‌ها در دایرکتوری موقت روی همان درایو مقصد (`%LOCALAPPDATA%/BorsTerminal/data/staging/`) انجام می‌شود تا جابه‌جایی نهایی بدون کپی فیزیکی و به صورت اتمیک انجام گیرد.
2. **پوشه‌های نسل تغییرناپذیر (Immutable Generations):** دیتابیس‌های استخراج‌شده در مسیر مستقل `gens/gen_<snapshot_set_id>/` قرار می‌گیرند.
3. **اعتبارسنجی کامل پیش از سوئیچ:** بررسی SHA-256، تایید امضای دیجیتال و اجرای `PRAGMA integrity_check` روی هر دو دیتابیس قبل از هرگونه تغییر اعمال می‌شود.
4. **سوئیچ اتمیک اشاره‌گر فعال (Active Pointer Swap):** اشاره‌گر فعال در فایل `active_generation.json` از طریق نوشتن در فایل موقت و تعویض اتمیک (`ReplaceFileW` / write-rename) تغییر می‌کند.
5. **تخلیه آرام اتصالات (Connection Drain):** اتصالات قبلی اجازه دارند کوئری‌های در حال اجرای خود را از نسل قدیم به پایان برسانند و درخواست‌های جدید به نسل جدید هدایت می‌شوند.
6. **نگهداری نسل قبلی برای Rollback فوری:** نسل قبلی (`gen_N-1`) روی دیسک حفظ می‌شود تا در صورت بروز هرگونه خطای منطقی یا ساختاری، بازگشت به نسل قبلی بدون قطعی و در کسری از ثانیه امکان‌پذیر باشد.

---

### بخش ۳: زیرسیستم دریافت بازار، رویدادهای شرکتی و حفظ تعدیل رهاورد (Workstream C)

این زیرسیستم در پکیج `backend-go/internal/tsetmc/` پیاده‌سازی می‌شود و تمامی نیازهای مصرف‌کنندگان فعلی را پوشش می‌دهد:

- **کامل‌بودن داده‌های بازار و تاریخچه:**
  - دریافت تابلوی زنده: `/ClosingPrice/GetMarketWatch`
  - گروه‌های صنعت و اطلاعات نمادها: `/StaticData/GetStaticData`
  - داده‌های لحظه‌ای حقیقی/حقوقی: `/ClientType/GetClientTypeAll`
  - **تاریخچه سری زمانی حقیقی/حقوقی:** افزودن صریح اندپوینت `/ClientType/GetClientTypeHistory` جهت حفظ تحلیل جریان نقدینگی و قدرت خریدار در تاریخچه.
  - تاریخچه کندل‌های روزانه از CDN با تطبیق قرارداد سه‌گانه (`candle_contract`).
- **رویدادهای شرکتی و حفظ برابری تعدیل رهاورد:**
  - واکشی و بروزرسانی رویدادهای جریان نقدینگی و افزایش سرمایه از طریق `GetPriceAdjustByFlow` و `GetInstrumentShareChange`.
  - تفکیک قطعی تاریخ مجمع از تاریخ مؤثر بازگشایی (Ex-Date).
  - حفظ ۱۰۰٪ چهار حالت تعدیل Stage 2 (خام، افزایش سرمایه، سود نقدی، عملکردی) و بارگذاری پیوسته بسته تصحیحات مرجع رهاورد ۳۶۵ برای نمادهای شاخص با خطای صفر مطلق (`0.000000`).
  - انطباق کامل با ماتریس شکاف داده (`TSETMC-DATA-GAP-MATRIX`) پیش از حذف کدهای پایتون.
- **قفل پایدار تک‌نویسنده (Single Writer Lock):**
  استفاده از فایل قفل پایدار `market_writer.lock` و قفل فایلی انحصاری سیستم‌عامل (`flock` / `LockFileEx`) تا از اجرای هم‌زمان دو Producer یا آسیب به دیتابیس جلوگیری شود.

---

### بخش ۴: پایداری در برابر ۴۲۹، مدیریت خط لوله و زمان‌بند (Workstreams D & E)

- **اولویت قطعی سرفصل Retry-After بر سقف محلی:**
  در صورت دریافت خطای ۴۲۹، مقدار ارائه‌شده در هدر HTTP `Retry-After` **اولویت مطلق** بر سقف‌های بک‌آف محلی دارد؛ اگر منبع خارجی زمان ۳۰۰ ثانیه اعلام کند، Worker دقیقاً ۳۰۰ ثانیه در خواب می‌ماند و هیچ درخواستی زودهنگام ارسال نخواهد شد.
- **الگوریتم Exponential Backoff با Jitter:**
  در غیاب هدر اختصاصی، زمان انتظار به صورت نمایی ($T = \min(T_{max}, T_{base} \cdot 2^n) + \text{jitter}$) افزایش می‌یابد.
- **کنترل نرخ و مدار شکن (Rate Limiter & Circuit Breaker):**
  - کنترل نرخ درخواست با سقف حداکثر ۲ درخواست در ثانیه به کدال.
  - در صورت دریافت ۳ خطای متوالی یا ورود به وضعیت Block، مدارشکن فعال شده و عملیات برای مدت بازگشایی متوقف می‌شود.
- **کادنس تطبیقی بر اساس ساعات انتشار کدال (Adaptive Cadence):**
  - ساعات کاری و اوج انتشار اطلاعیه‌ها (۰۹:۰۰ الی ۱۳:۳۰ و ۱۵:۰۰ الی ۱۹:۳۰): بررسی فید هر ۱۰ دقیقه.
  - ساعات شب و روزهای تعطیل: بررسی هر ۲ ساعت.

---

### بخش ۵: ممیزی و حذف کامل ردپای پایتون در عملیات (Workstream F)

| اسکریپت قدیمی پایتون | جایگزین در معماری جدید Go | وضعیت نهایی |
| :--- | :--- | :--- |
| `codal_fetcher.py` | `backend-go/internal/codal/` + `bors-producer codal run` | حذف کامل از عملیات |
| `codal_pipeline.py` | `backend-go/internal/codal/pipeline.go` | حذف کامل از عملیات |
| `codal_periods.py` | `backend-go/internal/period/` | جایگزین شده با پکیج Go |
| `codal_units.py` | `backend-go/internal/codal/units.go` | حذف کامل از عملیات |
| `codal_dividends.py` | `backend-go/internal/codal/dividends.go` | حذف کامل از عملیات |
| `dev/codal_fts_updater.py` | فرمان `bors-producer codal backfill` | حذف کامل از عملیات |
| `scripts/build_codal_snapshot.py` | فرمان `bors-producer codal snapshot` | حذف کامل از عملیات |
| `scripts/publish_codal_snapshot.py` | فرمان `bors-producer codal publish` | حذف کامل از عملیات |
| `test_tsetmc.py` | `backend-go/internal/tsetmc/` + `bors-producer market run` | حذف کامل از عملیات |
| `api/_sync_codal.py` | پکیج Go `internal/sync/` در `borsd` | حذف کامل از عملیات |
| `api/_sync_market.py` | پکیج Go `internal/sync/` در `borsd` | حذف کامل از عملیات |

پایتون پس از پایان این مرحله صرفاً به عنوان **اوراکل مقایسهٔ داده‌ها در ابزارهای تست توسعه (`tools/parity/`)** باقی می‌ماند و هیچ نقشی در تولید یا توزیع داده نخواهد داشت.

---

## ۴. ساختار باینری‌ها، پکیج‌ها و خط فرمان

### ساختار پوشه‌ها در مخزن:
```text
backend-go/
  cmd/
    borsd/                  # باینری اصلی کلاینت دسکتاپ
      main.go
    bors-producer/          # باینری خط لوله و تولیدکننده مرکزی داده
      main.go
  internal/
    codal/                  # خط لوله کدال (کشف، واکشی، استخراج، قرنطینه)
      discovery.go
      fetcher.go
      extractor.go
      units.go
      dividends.go
      validator.go
      pipeline.go
    tsetmc/                 # دریافت داده‌های بازار TSETMC
      fetcher.go
      marketwatch.go
      clienttype.go
      history.go
      adjust_events.go
    snapshot/               # بسته‌بندی، امضا، انتشار و اعمال دیتابیس
      builder.go
      signer.go
      publisher.go
      applier.go
    worker/                 # زمان‌بند، کادنس، ریت‌لیمیتر و مدارشکن
      orchestrator.go
      cadence.go
      ratelimit.go
      breaker.go
    fundamental/            # موتور محاسباتی ۵ شاخص بنیادی FTS (از قبل موجود)
    period/                 # منطق دوره‌های مالی و تقویم جلالی (از قبل موجود)
    chart/                  # موتور چارت و تعدیل رهاورد (تثبیت‌شده در Stage 2)
    sync/                   # هندلرهای وضعیت سینک و مانیتورینگ کلاینت
```

### فرامین باینری `bors-producer`:
```bash
# اجرای یک دور اسکن و دریافت فید افزایشی کدال
bors-producer codal run --mode=update

# استخراج و پر کردن اطلاعیه‌های قدیمی (Backfill)
bors-producer codal backfill --limit=100

# ساخت اسنپ‌شات و امضای دیجیتال
bors-producer codal snapshot --db=codal.db --out=dist/snapshots/

# انتشار اسنپ‌شات در مخزن
bors-producer codal publish --tag=data-codal --token=$GITHUB_TOKEN

# دریافت داده‌های زنده و رویدادهای بازار TSETMC
bors-producer market run --history=true

# اجرای دائم به صورت Daemon هماهنگ با کادنس و زمان‌بند
bors-producer daemon --config=producer_config.json
```

---

## ۵. ماتریس آزمون‌ها و معیارهای پذیرش (Acceptance Gates)

۱. **Gate 3.1 (CODAL Extraction & FTS Parity):**
   انطباق ۱۰۰٪ خروجی داده‌های استخراج‌شده صورت‌های مالی و فروش ماهانه در Go با نسخه پایتون، و تطابق کامل احکام ۵ شاخص FTS روی نمادهای نمونه.
۲. **Gate 3.2 (Snapshot Integrity & Minisign):**
   تولید صحیح فایل `codal.db.lzma`، امضا با کلید آزمایشی، و تایید موفق امضا توسط کلاینت دسکتاپ.
۳. **Gate 3.3 (Atomic Swap):**
   تست تزریق اسنپ‌شات تازه در حالتی که کلاینت در حال خواندن چارت یا تابلوی بازار است، بدون ارور `database is locked` یا کرش پروسه.
۴. **Gate 3.4 (429 Fault-Injection):**
   شبیه‌سازی خطای ۴۲۹ با سرور تست محلی و اثبات فعال‌شدن Circuit Breaker و احترام به زمان بک‌آف.
۵. **Gate 3.5 (Zero Operational Python):**
   اجرای فرآیند تولید داده، محاسبه و انتشار بدون اجرای حتی یک خط کد پایتون.
