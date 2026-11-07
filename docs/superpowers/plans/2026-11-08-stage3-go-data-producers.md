# برنامهٔ اجرایی Stage 3 — موتورهای تولید داده، خط لولهٔ کدال و همگام‌سازی پس‌زمینه در Go
# (Stage 3 Implementation Plan: Go Data Producers, CODAL Pipeline & Background Ingestion)

> **برای ایجنت‌های اجرایی:** مهارت الزامی: از `superpowers:subagent-driven-development` یا `superpowers:executing-plans` برای اجرای تسک‌به‌تسک این پلن استفاده کنید. گام‌ها از نگارش چک‌باکس (`- [ ]`) برای پایش بهره می‌برند.

**هدف:** استقرار کامل باینری مستقل `bors-producer` و ماژول‌های تولید، استخراج، اعتبارسنجی داده‌های کدال، دریافت بازار TSETMC، بازمحاسبه ۵ شاخص FTS، ساخت و امضای مانیفست و اسنپ‌شات منسجم، و اعمال اتمیک در کلاینت دسکتاپ `borsd`، به گونه‌ای که هیچ فرآیند عملیاتی به پایتون وابسته نباشد.

**معماری:** تفکیک قطعی دو باینری (`borsd` کلاینت دسکتاپ فقط‌خواندنی، و `bors-producer` ابزار و دیمن مرکزی خط لوله داده) بر پایه پکیج‌های مشترک داخلی در `backend-go/internal/`؛ پروتکل تعویض اتمیک پایگاه داده در ویندوز مبتنی بر نسل‌های تغییرناپذیر (`gens/gen_<snapshot_set_id>/`) با درایو مبدأ/مقصد یکسان و تخلیه اتصالات؛ حفظ ۱۰۰٪ فرمول‌های پنج شاخص FTS و چهار حالت تعدیل رهاورد ۳۶۵ با خطای صفر مطلق.

**تک‌استک:** Go 1.22+, `modernc.org/sqlite`, `aead/minisign`, `ulikunitz/xz` (LZMA2), `net/http`, Windows API (`ReplaceFileW` / write-rename).

**سند طراحی مرجع (Spec):** [`docs/superpowers/specs/2026-11-08-stage3-go-data-producers-design.md`](file:///c:/Users/PCMOD/Desktop/BorsTerminal/docs/superpowers/specs/2026-11-08-stage3-go-data-producers-design.md)

## الزامات سراسری (Global Constraints)

- **Single Writer:** در کلاینت `borsd`، دیتابیس‌های `market.db` و `codal.db` منحصراً با `mode=ro` باز می‌شوند. در Producer، فقط یک نویسنده با قفل پایدار فایلی مجاز به نوشتن است.
- **Snapshot Consistency:** انتشار اسنپ‌شات با شناسه یکتای مشترک `snapshot_set_id` و مانیفست امضاشده `manifest.json` انجام می‌شود. مانیفست تنها پس از تایید دسترسی‌پذیری کامل فایل‌های دیتابیس منتشر می‌گردد. Rollback به صورت مجموعه‌ای است.
- **FTS Parity:** فرمول‌ها، نسبت‌ها، آستانه‌ها و شروط تفکیک صنعت پنج شاخص بنیادی FTS دقیقاً منطبق بر `docs/جزوه FTS.pdf` و موتور Go موجود در `backend-go/internal/fundamental/` باقی مانده و هیچ ساده‌سازی مجاز نیست.
- **Rahavard Parity:** برابری ۴ حالت تعدیل با خطای صفر قیمت (`0.000000`) و لودر بسته تصحیحات مرجع رهاورد حفظ می‌شود.
- **Security:** توکن گیت‌هاب و کلید خصوصی امضا منحصراً از متغیرهای محیطی (`GITHUB_TOKEN`, `BORS_MINISIGN_SECRET_KEY`) خوانده می‌شوند؛ هرگز در آرگومان‌های CLI پاس داده نمی‌شوند.
- **Resilience:** سرفصل `Retry-After` منبع خارجی اولویت قطعی بر سقف‌های بک‌آف محلی دارد.
- **Zero Python in Production:** هیچ اسکریپت یا پروسه پایتونی در زنجیره تولید، واکشی، استخراج یا انتشار محصول نباید اجرا شود. پایتون فقط به عنوان اوراکل مقایسه در ابزارهای تست توسعه باقی می‌ماند.

---

## ساختار فایل‌ها و پکیج‌ها (File Structure)

```text
backend-go/
  cmd/
    bors-producer/
      main.go                     # نقطه ورود باینری خط لوله داده
    borsd/
      main.go                     # کلاینت دسکتاپ موجود
  internal/
    codal/
      discovery.go                # فید سراسری search.codal.ir، نشانک و حذف تکراری
      discovery_test.go
      fetcher.go                  # کلاینت HTTP مودب با احترام به Retry-After
      fetcher_test.go
      extractor.go                # استخراج HTML گزارش ماهانه و صورت مالی
      extractor_test.go
      validator.go                # اعتبارسنجی نماد/ناشر، قرنطینه و دوره‌های مالی
      validator_test.go
      recalc.go                   # علامت‌گذاری dirty و فراخوانی موتور ۵ شاخص FTS
      recalc_test.go
    tsetmc/
      fetcher.go                  # کلاینت CDN رسمی TSETMC
      fetcher_test.go
      marketwatch.go              # تابلوی زنده و صنایع
      marketwatch_test.go
      clienttype.go               # داده زنده و تاریخچه ClientTypeHistory
      clienttype_test.go
      history.go                  # بازیابی گپ کندل‌ها
      history_test.go
      adjust_events.go            # GetPriceAdjustByFlow و GetInstrumentShareChange
      adjust_events_test.go
      lock.go                     # قفل تک‌نویسنده پایدار فایلی
      lock_test.go
    snapshot/
      manifest.go                 # مدل داده مانیفست و snapshot_set_id
      builder.go                  # VACUUM INTO و فشرده‌سازی LZMA2
      builder_test.go
      signer.go                   # امضای دیجیتال و تایید Minisign ed25519
      signer_test.go
      publisher.go                # آپلود دارایی‌ها به تگ‌های گیت‌هاب
      publisher_test.go
      applier.go                  # پروتکل ویندوز: نسل‌های تغییرناپذیر، تخلیه و سوئیچ اتمیک
      applier_test.go
    worker/
      ratelimit.go                # توکن‌باکت و مدارشکن
      ratelimit_test.go
      cadence.go                  # یادگیری پنجره‌های انتشار کدال و زمان‌بند تطبیقی
      cadence_test.go
      orchestrator.go             # مدیریت Jobها، وضعیت و توقف آرام
      orchestrator_test.go
```

---

## فاز ۱: خط لولهٔ دریافت، استخراج و اعتبارسنجی کدال (Workstream A)

### Task 1: ماژول کشف فید و کلاینت HTTP مؤدب کدال

**Files:**
- Create: `backend-go/internal/codal/fetcher.go`
- Create: `backend-go/internal/codal/fetcher_test.go`
- Create: `backend-go/internal/codal/discovery.go`
- Create: `backend-go/internal/codal/discovery_test.go`

**Interfaces:**
- `type PoliteClient struct`: کلاینت HTTP با پشتیبانی از `Retry-After`، سقف Concurrency=2، و بک‌آف نمایی.
- `func (c *PoliteClient) Get(ctx context.Context, url string) ([]byte, int, error)`
- `type NoticeSummary struct { TracingNo int64; Symbol, Title, LetterCode, PublishDate, SentDate, URL string }`
- `func DiscoverFeed(ctx context.Context, client *PoliteClient, db *sql.DB, category int) ([]NoticeSummary, error)`

- [ ] **Step 1: نوشتن تست ناموفق کلاینت مؤدب (`fetcher_test.go`)**
  تست احترام به سرفصل `Retry-After` با سرور آزمایشی `httptest` که پاسخ ۴۲۹ همراه با `Retry-After: 3` می‌دهد و اثبات اینکه کلاینت حداقل ۳ ثانیه صبر می‌کند.
- [ ] **Step 2: پیاده‌سازی `fetcher.go`**
  پیاده‌سازی کلاینت، تجزیه هدرهای زمان انتظار و بک‌آف با Jitter.
- [ ] **Step 3: اجرای تست و سبزشکنی**
  اجرای `go test -v ./internal/codal -run TestPoliteClient`.
- [ ] **Step 4: نوشتن تست کشف اطلاعیه‌ها (`discovery_test.go`)**
  ارسال پاسخ ماک JSON فید جستجوی کدال (Category 1 و 3)، بررسی صفحه‌بندی، نشانک `pipeline_cursor` و عدم بازگشت ردیف‌های تکراری.
- [ ] **Step 5: پیاده‌سازی `discovery.go`**
  پیاده‌سازی متد `DiscoverFeed` و درج در جدول `codal_notices`.
- [ ] **Step 6: کامیت Task 1**
  `git commit -m "feat(codal): implement polite http fetcher and feed discovery"`

---

### Task 2: استخراج ساختاریافته HTML گزارش‌های کدال (Extractor)

**Files:**
- Create: `backend-go/internal/codal/extractor.go`
- Create: `backend-go/internal/codal/extractor_test.go`

**Interfaces:**
- `type MonthlyReportData struct { TracingNo int64; Symbol, PeriodEnd string; Year, Month int; Revenue, YTDRevenue, PrevRevenue, PrevYTD float64; Volume, YTDVolume float64; Unit string }`
- `type FinancialStatementData struct { TracingNo int64; Symbol, PeriodEnd string; Months int; Revenue, GrossProfit, OperatingProfit, NetProfit, Assets, Liabilities, Equity, Capital, RetainedEarnings, EPS float64; IsAudited, IsConsolidated bool; UnitNorm float64 }`
- `func ExtractMonthlySales(htmlContent []byte, notice NoticeSummary) (*MonthlyReportData, error)`
- `func ExtractFinancialStatements(sheets map[string][]byte, notice NoticeSummary) (*FinancialStatementData, error)`

- [ ] **Step 1: ایجاد فیکسچرهای HTML واقعی کدال در `internal/codal/testdata/`**
  ذخیره نمونه HTML واقعی گزارش فعالیت ۱ ماهه فولاد و صورت مالی ۶ ماهه فملی.
- [ ] **Step 2: نوشتن تست ناموفق استخراج (`extractor_test.go`)**
  تست استخراج مقادیر کلیدی ترازنامه، سود و زیان و فروش ماهانه از روی فیکسچرها.
- [ ] **Step 3: پیاده‌سازی متدهای استخراج در `extractor.go`**
  استفاده از پارسر HTML (`golang.org/x/net/html`) جهت پیمایش جداول استاندارد کدال و استخراج مقادیر عددی.
- [ ] **Step 4: اجرای تست و تطبیق با مقادیر مورد انتظار**
  اجرای `go test -v ./internal/codal -run TestExtract`.
- [ ] **Step 5: کامیت Task 2**
  `git commit -m "feat(codal): implement html table extraction for sales and statements"`

---

### Task 3: اعتبارسنجی، قرارداد دوره‌ها و قرنطینه داده معیوب

**Files:**
- Create: `backend-go/internal/codal/validator.go`
- Create: `backend-go/internal/codal/validator_test.go`
- Create: `backend-go/internal/codal/units.go`
- Create: `backend-go/internal/codal/units_test.go`

**Interfaces:**
- `func NormalizeUnit(unitStr string) float64`: تبدیل ریال، هزار ریال، میلیون ریال به ضریب ۱٫۰، ۱۰۰۰، و ۱,۰۰۰,۰۰۰.
- `func ValidateAndIngest(ctx context.Context, db *sql.DB, st *FinancialStatementData) error`: تطبیق نماد با `instruments`، اعتبارسنجی تاریخ پایان دوره با `internal/period` و ثبت در `financial_statements` یا `codal_quarantine`.

- [ ] **Step 1: نوشتن تست‌های واحد تبدیل واحد و اعتبارسنجی دوره (`units_test.go` و `validator_test.go`)**
- [ ] **Step 2: پیاده‌سازی نرمال‌سازی واحدها در `units.go` و گیت‌های کنترل در `validator.go`**
- [ ] **Step 3: مدیریت ردیف‌های نامعتبر و درج در `codal_quarantine`**
- [ ] **Step 4: اجرای تست‌ها و تایید سبزی**
- [ ] **Step 5: کامیت Task 3**
  `git commit -m "feat(codal): implement validation, units normalization, and quarantine handling"`

---

### Task 4: خط لوله بازمحاسبه پنج شاخص بنیادی FTS با موتور Go

**Files:**
- Create: `backend-go/internal/codal/recalc.go`
- Create: `backend-go/internal/codal/recalc_test.go`

**Interfaces:**
- `func MarkDirty(ctx context.Context, db *sql.DB, symbol string, source string) error`
- `func RecalculateDirtyFTS(ctx context.Context, marketDB *sql.DB, symbols []string) (int, error)`: فراخوانی ارزیابی ۵ شاخص از `backend-go/internal/fundamental` و بروزرسانی جدول `fts_results`.

- [ ] **Step 1: نوشتن تست مقایسه‌ای FTS (`recalc_test.go`)**
  تزریق یک صورت مالی جدید برای نماد فولاد در پایگاه داده تست و بررسی تغییر احکام و خروجی در `fts_results`.
- [ ] **Step 2: پیاده‌سازی متد `RecalculateDirtyFTS` با استفاده مستقیم از توابع `internal/fundamental`**
- [ ] **Step 3: راستی‌آزمایی انطباق ۱۰۰٪ خروجی با احکام قبلی جزوه FTS**
- [ ] **Step 4: کامیت Task 4**
  `git commit -m "feat(codal): implement targeted incremental FTS recalculation in Go"`

---

## فاز ۲: زیرسیستم اسنپ‌شات، امضا، انتشار و پروتکل تعویض اتمیک (Workstream B)

### Task 5: سازنده اسنپ‌شات و مانیفست منسجم مجموعه‌ای

**Files:**
- Create: `backend-go/internal/snapshot/manifest.go`
- Create: `backend-go/internal/snapshot/builder.go`
- Create: `backend-go/internal/snapshot/builder_test.go`

**Interfaces:**
- `type Manifest struct { SnapshotSetID string; CreatedAtUTC string; SchemaVersion int; Assets map[string]AssetMeta }`
- `func BuildSnapshot(sourceDB, outDir, name string) (string, string, int64, error)`: اجرای `VACUUM INTO`، فشرده‌سازی LZMA2 و تولید هش SHA-256.

- [ ] **Step 1: نوشتن تست ساخت اسنپ‌شات LZMA2 و مانیفست (`builder_test.go`)**
- [ ] **Step 2: پیاده‌سازی `VACUUM INTO`، استریمینگ فشرده‌ساز LZMA2 و محاسبه SHA-256 در `builder.go`**
- [ ] **Step 3: تولید فایل‌های `codal.db.lzma`، `market.db.lzma` و سند `manifest.json` با `snapshot_set_id` یکسان**
- [ ] **Step 4: اجرای تست و سبزشکنی**
- [ ] **Step 5: کامیت Task 5**
  `git commit -m "feat(snapshot): implement snapshot builder and unified manifest"`

---

### Task 6: امضای دیجیتال Minisign و ناشر دارایی‌های داده

**Files:**
- Create: `backend-go/internal/snapshot/signer.go`
- Create: `backend-go/internal/snapshot/signer_test.go`
- Create: `backend-go/internal/snapshot/publisher.go`
- Create: `backend-go/internal/snapshot/publisher_test.go`

**Interfaces:**
- `func SignAsset(filePath string, privKeyStr string) (string, error)`
- `func VerifyAsset(filePath string, sigPath string, pubKeyStr string) error`
- `func PublishSnapshotSet(ctx context.Context, client *http.Client, token string, tag string, manifest *Manifest, files []string) error`

- [ ] **Step 1: نوشتن تست امضا و تایید Minisign ed25519 (`signer_test.go`)**
  تولید جفت‌کلید تستی Minisign، امضای فایل و تایید صحت امضا و پس زدن امضای دستکاری‌شده.
- [ ] **Step 2: پیاده‌سازی توابع امضا و راستی‌آزمایی در `signer.go`**
- [ ] **Step 3: پیاده‌سازی ناشر گیت‌هاب در `publisher.go` با خواندن `GITHUB_TOKEN` منحصراً از متغیر محیطی**
  رعایت توالی انتشار: ابتدا آپلود فایل‌های فشرده، تست در دسترس بودن (HTTP 200)، و سپس آپلود `manifest.json` و `manifest.json.sig`.
- [ ] **Step 4: اجرای تست‌ها و تایید کامل**
- [ ] **Step 5: کامیت Task 6**
  `git commit -m "feat(snapshot): implement minisign signing and release publisher"`

---

### Task 7: پروتکل قطعی تعویض اتمیک در ویندوز بر پایه نسل‌های تغییرناپذیر

**Files:**
- Create: `backend-go/internal/snapshot/applier.go`
- Create: `backend-go/internal/snapshot/applier_test.go`

**Interfaces:**
- `type Applier struct { dataDir string; pubKey string }`
- `func (a *Applier) ApplySnapshotSet(stagingDir string, manifest *Manifest) error`:
  - ایجاد پوشه `gens/gen_<snapshot_set_id>/` روی همان Volume.
  - اعتبارسنجی امضا، هش SHA-256 و `PRAGMA integrity_check`.
  - جابه‌جایی فایل‌ها به پوشه نسل.
  - به‌روزرسانی اتمیک `active_generation.json`.
  - حفظ نسل قبلی (`gen_N-1`) برای امکان Rollback بدون وقفه.

- [ ] **Step 1: نوشتن تست شبیه‌سازی قفل باز و سوئیچ اتمیک (`applier_test.go`)**
  باز نگه داشتن کانکشن خواندن بر روی دیتابیس نسل قدیم، اعمال اسنپ‌شات نسل جدید، تایید موفقیت سوئیچ بدون ارور قفل و هدایت خواننده‌های جدید به نسل تازه.
- [ ] **Step 2: پیاده‌سازی ساختار دایرکتوری‌های نسل‌ها و سوئیچ اشاره‌گر اتمیک در `applier.go`**
- [ ] **Step 3: پیاده‌سازی مکانیزم Rollback مجموعه‌ای به نسل قبلی**
- [ ] **Step 4: اجرای تست و سبزشکنی**
- [ ] **Step 5: کامیت Task 7**
  `git commit -m "feat(snapshot): implement windows atomic ingestion via immutable generations"`

---

## فاز ۳: خط لوله بازار TSETMC و حفظ تعدیل رهاورد (Workstream C)

### Task 8: دریافت زنده بازار، گروه‌های صنعت و تاریخچه حقیقی/حقوقی

**Files:**
- Create: `backend-go/internal/tsetmc/fetcher.go`
- Create: `backend-go/internal/tsetmc/fetcher_test.go`
- Create: `backend-go/internal/tsetmc/marketwatch.go`
- Create: `backend-go/internal/tsetmc/clienttype.go`

**Interfaces:**
- `func FetchMarketWatch(ctx context.Context, client *http.Client) ([]MarketWatchRow, error)`
- `func FetchClientTypeHistory(ctx context.Context, client *http.Client, insCode string) ([]ClientTypePoint, error)`
- `func IngestMarketSnapshot(ctx context.Context, db *sql.DB, rows []MarketWatchRow) error`

- [ ] **Step 1: نوشتن تست واکشی تابلوی بازار و تاریخچه حقیقی/حقوقی از روی فیکسچرهای JSON تستی**
- [ ] **Step 2: پیاده‌سازی کلاینت CDN رسمی TSETMC در `fetcher.go` با پین کردن IP بهینه**
- [ ] **Step 3: درج و بروزرسانی دسته‌ای در جداول `market_watch`, `client_type`, `instruments` دیتابیس `market.db`**
- [ ] **Step 4: کامیت Task 8**
  `git commit -m "feat(tsetmc): implement live market watch and client type history ingestion"`

---

### Task 9: رویدادهای شرکتی و حفظ برابری تعدیل رهاورد ۳۶۵

**Files:**
- Create: `backend-go/internal/tsetmc/adjust_events.go`
- Create: `backend-go/internal/tsetmc/adjust_events_test.go`

**Interfaces:**
- `func SyncCorporateEvents(ctx context.Context, client *http.Client, db *sql.DB, insCode string) error`:
  واکشی رویدادها از `GetPriceAdjustByFlow` و `GetInstrumentShareChange` و درج در `share_change_events` و `price_adjust_events`.

- [ ] **Step 1: نوشتن تست انطباق رویدادهای شرکتی با ماتریس شکاف داده (`TSETMC-DATA-GAP-MATRIX`)**
- [ ] **Step 2: پیاده‌سازی واکشی جریان رویدادها و تفکیک تاریخ مجمع از تاریخ مؤثر بازگشایی**
- [ ] **Step 3: اجرای تست برابری تعدیل ۴ گانه رهاورد با `TestRahavardCorrectionPackParity_ShastaFemeli` و اثبات عدم رگرسیون (Price Delta = 0.000000)**
- [ ] **Step 4: کامیت Task 9**
  `git commit -m "feat(tsetmc): implement corporate actions ingestion with strict Rahavard parity"`

---

### Task 10: پروتکل قفل تک‌نویسنده پایدار دیتابیس مارکت

**Files:**
- Create: `backend-go/internal/tsetmc/lock.go`
- Create: `backend-go/internal/tsetmc/lock_test.go`

**Interfaces:**
- `type WriterLock struct { lockFilePath string; file *os.File }`
- `func AcquireWriterLock(dataDir string) (*WriterLock, error)`
- `func (l *WriterLock) Release() error`

- [ ] **Step 1: نوشتن تست رقابت دو پروسه نویسنده (`lock_test.go`)**
  تلاش پروسه دوم برای اخذ قفل و پس‌زدن فوری با خطای `writer lock already held`.
- [ ] **Step 2: پیاده‌سازی قفل فایلی سیستم‌عامل (`LockFileEx` در ویندوز و `flock` در لینوکس)**
- [ ] **Step 3: کامیت Task 10**
  `git commit -m "feat(tsetmc): implement robust single-writer lock protocol"`

---

## فاز ۴: پایداری، کادنس تطبیقی و باینری مرکزی `bors-producer` (Workstreams D & E)

### Task 11: مدارشکن (Circuit Breaker) و کنترل نرخ درخواست

**Files:**
- Create: `backend-go/internal/worker/ratelimit.go`
- Create: `backend-go/internal/worker/ratelimit_test.go`

- [ ] **Step 1: نوشتن تست مدارشکن در مواجهه با خطای شبیه‌سازی‌شده ۴۲۹ و ۵xx**
- [ ] **Step 2: پیاده‌سازی Rate Limiter با توکن‌باکت و Circuit Breaker با سه وضعیت Closed, Open, Half-Open**
- [ ] **Step 3: اولویت‌دهی به سرفصل `Retry-After` سرور بر زمان استراحت محلی**
- [ ] **Step 4: کامیت Task 11**
  `git commit -m "feat(worker): implement circuit breaker and token bucket rate limiter"`

---

### Task 12: کادنس تطبیقی و زمان‌بند هماهنگ‌کننده Workerها

**Files:**
- Create: `backend-go/internal/worker/cadence.go`
- Create: `backend-go/internal/worker/cadence_test.go`
- Create: `backend-go/internal/worker/orchestrator.go`
- Create: `backend-go/internal/worker/orchestrator_test.go`

- [ ] **Step 1: پیاده‌سازی استخراج پنجره‌های اوج انتشار کدال از روی تاریخچه `codal_notices`**
- [ ] **Step 2: زمان‌بندی چرخه‌ها (۱۰ دقیقه در ساعات اوج، ۲ ساعت در سایر مواقع)**
- [ ] **Step 3: پیاده‌سازی مدیریت چرخه‌ها (Start, Stop, Pause, Resume, Drain) و سلامت Workerها**
- [ ] **Step 4: کامیت Task 12**
  `git commit -m "feat(worker): implement adaptive cadence and worker orchestrator"`

---

### Task 13: باینری مستقل خط فرمان `bors-producer`

**Files:**
- Create: `backend-go/cmd/bors-producer/main.go`
- Create: `backend-go/cmd/bors-producer/main_test.go`

- [ ] **Step 1: پیاده‌سازی زیرفرمان‌های خط فرمان:**
  - `bors-producer codal run --mode=update`
  - `bors-producer codal backfill --limit=N`
  - `bors-producer codal snapshot --out=dist/snapshots`
  - `bors-producer codal publish --tag=data-codal`
  - `bors-producer market run --history=true`
  - `bors-producer daemon --config=config.json`
- [ ] **Step 2: خواندن امن توکن گیت‌هاب و کلید امضا از Environment و ممانعت از دریافت آرگومان حساس CLI**
- [ ] **Step 3: تست کامپایل و اجرای هلپ تمام فرامین**
- [ ] **Step 4: کامیت Task 13**
  `git commit -m "feat(producer): create standalone bors-producer CLI binary"`

---

## فاز ۵: ممیزی پایتون، بازنشستگی اسکریپت‌ها و گزارش نهایی (Workstream F)

### Task 14: حذف فراخوانی‌های پایتون در کلاینت دسکتاپ `borsd`

**Files:**
- Modify: `backend-go/internal/sync/handlers.go`
- Modify: `backend-go/internal/sync/status.go`

- [ ] **Step 1: قطع کامل هرگونه اجرای پایتون (subprocess spawn) در اندپوینت‌های `/api/sync/codal` و `/api/sync/market`**
- [ ] **Step 2: اتصال اندپوینت‌های دانلود و اعمال اسنپ‌شات به پکیج بومی `internal/snapshot/applier.go`**
- [ ] **Step 3: کامیت Task 14**
  `git commit -m "refactor(sync): eliminate python subprocess spawns in desktop client"`

---

### Task 15: ممیزی پاریتی جامع، تست‌های تزریق خطا و تدوین گزارش نهایی

**Files:**
- Modify: `tools/parity/run_5symbol_parity.py`
- Create: `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md`

- [ ] **Step 1: اجرای تست‌های تزریق خطا (Fault-Injection):**
  - شبیه‌سازی پاسخ ۴۲۹ همراه و بدون `Retry-After`.
  - تزریق فایل اسنپ‌شات با امضای نامعتبر و اطمینان از رد شدن توسط کلاینت.
  - شبیه‌سازی کرش پروسه در حین اعمال اسنپ‌شات و تایید سلامت پایگاه داده و امکان Rollback.
- [ ] **Step 2: اجرای تست برابری ۵ نماد شاخص بازار و اطمینان از حفظ اختلاف قیمت صفر (`0.000000`)**
- [ ] **Step 3: ممیزی وابستگی پایتون (Python Dependency Audit) و تایید صفر بودن فرآیندهای عملیاتی پایتون**
- [ ] **Step 4: تدوین و ذخیره سند جامع `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md`**
- [ ] **Step 5: اجرای کلیه گاردهای ریپو (گاردهای نسخه، رسم‌الخط، ساختار Onedir و تست‌های Go)**
- [ ] **Step 6: کامیت و پوش نهایی Stage 3**
