# گزارش جامع نهایی مرحله ۴ — عملیاتی‌سازی، یکپارچه‌سازی نهایی و پذیرش شواهد‌محور خط لوله تولید داده Go
# (Stage 4 Final Report: Production Activation & Evidence-Based Acceptance)

**تاریخ گزارش:** ۸ نوامبر ۲۰۲۶ (۱۷ آبان ۱۴۰۵)  
**شاخه فعال:** `mission/stage4-production-activation-2026-11-08`  
**نقطه شروع اولیه:** `da6d61777ec2f99a3c7a64464270730c17ffeb6e` (تکمیل فاز ۳)  
**نقطه بازبینی و رفع شکاف‌ها:** `cd3350bd`  
**نقطه فعال‌سازی تولید:** `15dbb8e9` (GitHub Actions Run `42508665247`)  
**نسخه نرم‌افزار:** `1.0.95` (یکپارچه در تمامی ۱۱ لنگر مخزن)  
**حکم نهایی پذیرش (Final Verdict):** **`STAGE4_PRODUCTION_ACTIVATED_CLIENT_VERIFIED`**  
*(تمامی شکاف‌های کد، زمان‌بندی، E2E، اعتبارسنجی کلاینت ویندوز و گاردهای ۱۱ گانه نسخه بسته شدند و فراتر از آن، انتشار واقعی Snapshot روی GitHub Releases با تطابق ریاضی کلید امضا و دریافت کامل توسط باینری ویندوزی از مسیر واقعی GitHub اثبات شد. جزئیات در بخش‌های ۵ و ۶).*

---

## ۱. خلاصه اجرایی و دستاوردهای رفع شکاف‌ها (Remediation Summary)

در پی بازبینی مستقل نتایج اولیه مرحله ۴، شش محور عملیاتی (Workstreams A تا F) به عنوان شکاف‌های پیاده‌سازی و اعتبارسنجی شناسایی و با شواهد ریاضی و آزمون‌های خودکار به طور کامل بسته شدند:

1. **اتصال قطعی زمان‌بندی روزانه به 06:00 UTC و چرخه خودکار انتشار (Workstream A):**
   - معماری زمان‌بندی از فاصله نسبی (`snapshot_interval_sec`) به زمان ثابت دیوار ساعت (`06:00 UTC`) با تابع محاسباتی قطعی `NextDailyUTCDuration` بازطراحی شد.
   - فرآیند Restart سرویس هیچ‌گونه جابه‌جایی در ساعت اجرای روزانه ایجاد نمی‌کند.
   - منطق جبران اجرای ازدست‌رفته (Startup Catchup) پیاده‌سازی شد؛ در صورت خاموش بودن سرور در ساعت 06:00 UTC، در شروع مجدد، نبود اسنپ‌شات امروز فوراً تشخیص داده شده و اجرا می‌شود.
   - چرخه دیمن به تابع جامع `ExecuteScheduledSnapshotPipeline` متصل شد که زنجیره کامل: بررسی قفل، اعتبارسنجی دیتابیس‌ها، ساخت LZMA2، امضای مانیفست و دارایی‌ها با Minisign، انتشار ترتیبی به مخزن، و ثبت فراداده در `pipeline_runs` را مدیریت می‌کند.

2. **اصلاح و قطعی‌سازی آزمون انتشار سرتاسری E2E (Workstream B):**
   - وابستگی `BaseURL` به ساختار `Publisher` و متد `PublishSnapshotSet` تزریق شد (`GITHUB_API_BASE_URL`).
   - آزمون `backend-go/cmd/bors-producer/e2e_pipeline_test.go` به سرور آزمایشی `httptest.Server` متصل گردید.
   - ترتیب قطعی انتشار با Assertion دقیق اثبات شد: دارایی‌های فشرده داده (`market.db.lzma`, `codal.db.lzma`) و امضاهای `.sig` ابتدا آپلود و با وضعیت 200 OK تأیید می‌شوند؛ مانیفست (`manifest.json` و `manifest.json.sig`) دقیقاً در آخرین مرحله منتشر می‌گردد.
   - ۵ سناریوی خطای انتشار پیاده‌سازی و پاس شدند: `AssetUploadFailure`, `ManifestUploadFailure`, `InvalidAPIResponse`, `CorruptSigningKey`, `ContextCancelled`.

3. **اثبات تجربی بازمحاسبه FTS در سطح کل Universe (Workstream C):**
   - بازمحاسبه فراگیر با دستور `bors-producer codal recalc --all` روی دیتاست واقعی موجود اجرا شد.
   - از میان ۱,۴۵۴ نماد کاندید، تعداد ۱,۱۸۸ نماد با داده‌های مالی در ۱۴۰ ثانیه در جدول `fts_results` ارزیابی شدند (۳۷ نماد PASS، ۳۳۹ نماد MARGINAL، ۸۱۲ نماد FAIL).
   - ۹۴ نماد (هلدینگ‌های مالی، بانک‌ها، بیمه‌ها) طبق استاندارد FTS به درستی مستثنی شدند و ۴۴۳ مورد تکراری گزارشگری مالی کشف و مدیریت گردید.
   - آزمون برابری ۵ نماد شاخص رهاورد با حداکثر دلتای 0.000000 تأیید شد.

4. **همگام‌سازی نسخه‌ها و گارد ۱۱ لنگر (Workstream D):**
   - نسخه `frontend-v2/package.json` و `package-lock.json` از مقدار اولیه `0.1.0` به نسخه هماهنگ `1.0.95` ارتقا یافت.
   - اسکریپت `dev/version_anchor_guard.py` بازنویسی شد و به جای ۷ لنگر، اکنون تمامی ۱۱ لنگر محصول (از جمله frontend-v2، backend-go، Tauri، Inno Setup و مخزن پایه) را اعتبارسنجی می‌کند.
   - مجموعه تست اختصاصی `dev/test_version_anchor_guard.py` ایجاد و ۵ تست مستقل همگامی، ناهمگامی و مفقودی فایل را با موفقیت پاس کردند.

5. **سازگاری مستندات و استقرار (Workstream E):**
   - فایل‌های پیکربندی `systemd` به کاربر استاندارد غیر ریشه `User=borsproducer` و `Group=borsproducer` مجهز شدند.
   - متغیرهای محیطی `BORS_PUBLISH_ENABLED`, `BORS_GITHUB_REPO`, `SNAPSHOT_DAILY_UTC` به داکر، Compose و مستندات اضافه شدند.

6. **اثبات عملکرد باینری نصبی کلاینت روی ویندوز (Workstream F):**
   - ابزار آزمون جامع `tools/test_installed_windows_client_e2e.py` باینری واقعی کامپایل‌شده `dist/BorsTerminal_Ultimate/BorsTerminal_Ultimate.exe` را اجرا کرد.
   - دریافت، راستی‌آزمایی امضای Minisign، استخراج و سوییچ اتمیک اسنپ‌شات جدید بر بستر HTTP آزموده شد.
   - **برابری بایت‌به‌بایت SHA-256 دیتابیس `user.db` پیش و پس از اعمال اسنپ‌شات (۰ بایت تغییر) به طور قطعی اثبات گردید.**
   - حفظ اطلاعات واچ‌لیست‌ها و یادداشت‌های کاربر و بارگذاری خودکار نسل فعال پس از راه‌اندازی مجدد (Restart) تایید شد.

---

## ۲. جدول ماتریس پذیرش نهایی ورک‌استریم‌ها

| ورک‌استریم | حوزه | اقدامات کلیدی انجام‌شده | وضعیت آزمون | نتیجه شواهد |
| :---: | :--- | :--- | :---: | :---: |
| **WS-A** | زمان‌بندی و انتشار دیمن | بازطراحی زمان‌بند 06:00 UTC، منطق Startup Catchup، زنجیره کامل خط لوله و قفل‌گذاری | **PASS** | ۵ آزمون اختصاصی در `daemon_pipeline_test.go` |
| **WS-B** | آزمون E2E انتشار | تزریق BaseURL، سرور آزمایشی httptest، تضمین تقدم دارایی‌ها بر مانیفست، تست ۵ سناریوی شکست | **PASS** | ۲ آزمون در `e2e_pipeline_test.go` در ۰٫۳۵ ثانیه |
| **WS-C** | ممیزی پوشش Universe | اجرای واقعی بازمحاسبه ۱,۱۸۸ نماد، تفکیک ۵ شاخص، شناسایی ۴۴۳ ناهنجاری دوره‌ای، حفظ برابری رهاورد | **PASS** | ثبت خروجی عددی بدون داده ساختگی در ۱۴۰ ثانیه |
| **WS-D** | همگام‌سازی نسخه | ارتقای frontend-v2 به 1.0.95، پایش ۱۱ لنگر با `version_anchor_guard.py` و ۵ تست واحد | **PASS** | ۱۱ لنگه همگام، ۱۱ checks 0 failed |
| **WS-E** | استقرار و اسناد | اصلاح `User=borsproducer` در systemd، متغیرهای محیطی در Docker و PowerShell | **PASS** | مستندات و تمپلیت‌های همگام |
| **WS-F** | اعتبارسنجی کلاینت ویندوز | اجرای باینری نهایی EXE، آزمون سوییچ اتمیک نسل، حفظ قطعی `user.db` با هش SHA-256 و راه‌اندازی مجدد | **PASS** | آزمون زنده `test_installed_windows_client_e2e.py` |

---

## ۳. بررسی جزئیات شواهد تجربی (Empirical Evidence)

### ۳.۱. ورک‌استریم A: آزمون‌های زمان‌بندی و پایداری دیمن

مجموعه تست خودکار در فایل `backend-go/cmd/bors-producer/daemon_pipeline_test.go` پیاده‌سازی و اجرا گردید:

```text
=== RUN   TestDailyUTCSchedule_Calculations
--- PASS: TestDailyUTCSchedule_Calculations (0.00s)
=== RUN   TestDailyUTCSchedule_MissedRunDetection
--- PASS: TestDailyUTCSchedule_MissedRunDetection (0.00s)
=== RUN   TestScheduledSnapshotPipeline_EndToEndPublishSuccess
--- PASS: TestScheduledSnapshotPipeline_EndToEndPublishSuccess (0.24s)
=== RUN   TestScheduledSnapshotPipeline_ErrorHandling
--- PASS: TestScheduledSnapshotPipeline_ErrorHandling (0.00s)
=== RUN   TestScheduledSnapshotPipeline_ConcurrencyControl
--- PASS: TestScheduledSnapshotPipeline_ConcurrencyControl (0.00s)
PASS
ok  	borsterminal/backend/cmd/bors-producer	1.536s
```

**شواهد اثبات‌شده:**
- محاسبه فاصله زمانی تا 06:00 UTC فردا یا همان روز به طور قطعی کار می‌کند.
- اجرای ازدست‌رفته ناشی از خاموشی سرور در شروع مجدد شناسایی و کچ‌آپ می‌شود.
- در صورت عدم دسترسی به قفل رایتر یا شکست در امضا، خط لوله متوقف شده و خروجی نامعتبر منتشر نمی‌گردد.

### ۳.۲. ورک‌استریم B: آزمون جامع E2E انتشار و سناریوهای شکست

تست `backend-go/cmd/bors-producer/e2e_pipeline_test.go` با سرور شبیه‌ساز GitHub Release به طور کامل بازنویسی شد:

```text
=== RUN   TestE2ESnapshotPipeline
    e2e_pipeline_test.go:174: Publication order verified: 4 data/sig assets uploaded before manifest.json
--- PASS: TestE2ESnapshotPipeline (0.33s)
=== RUN   TestE2ESnapshotPipeline_FailureScenarios
=== RUN   TestE2ESnapshotPipeline_FailureScenarios/AssetUploadFailure
=== RUN   TestE2ESnapshotPipeline_FailureScenarios/ManifestUploadFailure
=== RUN   TestE2ESnapshotPipeline_FailureScenarios/InvalidAPIResponse
=== RUN   TestE2ESnapshotPipeline_FailureScenarios/CorruptSigningKey
=== RUN   TestE2ESnapshotPipeline_FailureScenarios/ContextCancelled
--- PASS: TestE2ESnapshotPipeline_FailureScenarios (0.02s)
PASS
```

**شواهد اثبات‌شده:**
- تمام دارایی‌ها (`market.db.lzma`, `market.db.lzma.sig`, `codal.db.lzma`, `codal.db.lzma.sig`) پیش از مانیفست آپلود و ارزیابی می‌شوند.
- انتشار مانیفست به عنوان گیت نهایی عمل می‌کند؛ شکست در آپلود هر دارایی مانع انتشار مانیفست می‌شود.
- رفتار سیستم در برابر خطای شبکه، پاسخ نامعتبر، کلید مخدوش و لغو کانتکست با شکست تمیز مدیریت می‌شود.

### ۳.۳. ورک‌استریم C: بازمحاسبه FTS و ممیزی Universe

اجرای دستور بازمحاسبه روی دیتاست واقعی پرودوسر با دستور:
```bash
./dist/bors-producer.exe codal recalc --all --db-dir=_audit/release_pack/market.db
```
نتایج واقعی زیر را به ثبت رساند:
- **زمان اجرای کل:** ۱۴۰٫۳ ثانیه
- **کل نمادهای کاندید بازار:** ۱,۴۵۴ نماد
- **نمادهای ارزیابی‌شده در `fts_results`:** ۱,۱۸۸ نماد
- **توزیع احکام کلی:**
  - `STRONG` یا `PASS`: ۳۷ نماد
  - `MARGINAL` یا `WATCH`: ۳۳۹ نماد
  - `FAIL` یا `WEAK`: ۸۱۲ نماد
- **تفکیک وضعیت شاخص‌های پنج‌گانه FTS:**
  - شاخص ۱ (رشد درآمد/فروش): ۴۸۵ قبول / ۲۵۶ رد / ۴۴۷ بدون داده (N/A)
  - شاخص ۲ (روند سودآوری EPS): ۱۱۳ قبول / ۷۱۴ رد / ۳۶۱ بدون داده
  - شاخص ۳ (حاشیه سود ناخالص): ۳۱۴ قبول / ۲۰۱ رد / ۶۷۳ بدون داده
  - شاخص ۴ (نسبت ارزش بازار به فروش): ۴۲۵ قبول / ۲۶۰ رد / ۵۰۳ بدون داده
  - شاخص ۵ (موقعیت صنعت/محصول): ۱,۱۱۴ قبول / ۷۴ رد
- **نمادهای مستثنی‌شده (Excluded):** ۹۴ نماد (هلدینگ‌های مالی، بانک‌ها، بیمه‌ها به دلیل ماهیت عملیاتی غیرتولیدی طبق مدل FTS)
- **ناهنجاری‌های دوره‌ای شناسایی‌شده:** ۴۴۳ مورد تکراری گزارشگری کدال در پایگاه داده شناسایی شد که سیستم بدون کرش آن‌ها را فیلتر نمود.
- **آزمون برابری ۵ نماد:** اجرای `python tools/parity/run_5symbol_parity.py --offline` اختلاف قیمت 0.000000 و تطابق ۱۰۰٪ بنیادی با رهاورد ۳۶۵ را برای نمادهای فولاد، شستا، فملی، خودرو و وبصادر اثبات کرد.

### ۳.۴. ورک‌استریم D: اعتبارسنجی ۱۱ لنگر نسخه

اجرای گارد نسخه با اسکریپت `python dev/version_anchor_guard.py`:

```text
  PASS هر 11 لنگه روی 1.0.95
    ok  bors_config.APP_VERSION = 1.0.95
    ok  frontend-v2/package.json = 1.0.95
    ok  frontend-v2/package-lock.json#version = 1.0.95
    ok  frontend-v2/package-lock.json#packages[""] = 1.0.95
    ok  backend-go/cmd/bors-producer/main.go = 1.0.95
    ok  src-tauri/tauri.conf.json = 1.0.95
    ok  src-tauri/Cargo.toml = 1.0.95
    ok  installer/bors_setup.iss AppVersion = 1.0.95
    ok  frontend/package.json = 1.0.95
    ok  package-lock.json#version = 1.0.95
    ok  package-lock.json#packages[""] = 1.0.95

11 checks, 0 failed
VERSION ANCHOR GUARD OK
```

تست‌های واحد گارد نسخه در `dev/test_version_anchor_guard.py`:
```text
.....
Ran 5 tests in 0.032s
OK
```

### ۳.۵. ورک‌استریم F: آزمون E2E باینری نصبی کلاینت روی ویندوز

اجرای آزمون سرتاسری کلاینت با دستور `python tools/test_installed_windows_client_e2e.py`:

```text
================================================================================
      BorsTerminal Windows Client E2E Integration & user.db Integrity Test      
================================================================================
  [1] Generating Minisign Ed25519 keypair via dist/bors-producer.exe keygen...
      Public key: RWRzqhK7Pm2ew/6tlkSu1gwl9crEHFRt...
  [2] Creating compressed LZMA2 snapshot set and Minisign signatures...
      Created and signed all 6 release assets (market, codal, manifest + .sig files).
  [3] Seeded user.db successfully (size: 16384 bytes)
      Initial user.db SHA-256: d7f11b5ba654f3a6f78d0f66368024f618a19f4a0aae855eac0f4ebfb721b0a4
  [4] Mock distribution server listening at: http://127.0.0.1:8196
  [5] Launching live Windows binary BorsTerminal_Ultimate.exe on port 8197...
      BorsTerminal_Ultimate.exe is live and responding (200 OK).
  [6] Triggering POST /api/sync/codal/db-download?url=http://127.0.0.1:8196 on Windows client...
      Response: status=success, message=دانلود دیتابیس کدال از گیت‌هاب آغاز شد.
  [7] Polling client download, Minisign verification, and atomic apply status...
      [0] stage=done, pct=100%, detail=اسنپ‌شات با موفقیت اعمال شد.
      Status reached 'done' (100%): اسنپ‌شات با موفقیت اعمال شد.
  [8] Active Generation verified: gen-win-client-live-20261108
      Generation Directory: ...\client_data\gens/gen_gen-win-client-live-20261108
      New generation DB query: symbol فولاد -> verdict STRONG (verified!)
  [9] Comparing user.db SHA-256 before and after snapshot apply:
      Initial: d7f11b5ba654f3a6f78d0f66368024f618a19f4a0aae855eac0f4ebfb721b0a4
      Final:   d7f11b5ba654f3a6f78d0f66368024f618a19f4a0aae855eac0f4ebfb721b0a4
      PASS: user.db SHA-256 is 100% byte-for-byte identical (Zero Modification).
      Verified user records: 2 watchlist entries, note: 'تحلیل بنیادی تایید FTS دارد'
  [10] Restarting BorsTerminal_Ultimate.exe to verify generation persistence...
      PASS: Client reloaded active generation successfully after restart.
================================================================================
  ALL WINDOWS CLIENT INTEGRATION CHECKS PASSED: 100% EVIDENCE-BASED SUCCESS!    
================================================================================
```

---

## ۴. زنجیره تعهدات معماری و امنیتی

1. **عدم نشت اطلاعات محرمانه (Zero Leaks):**
   هیچ کلید خصوصی، توکن GitHub یا Secret در هیچ فایلی کامیت نشده و در لاگ‌ها چاپ نمی‌شود.
2. **عدم نفوذ پایتون به کلاینت (Zero Python in Distributable):**
   کلاینت دسکتاپ بر پایه موتور باینری کامپایل‌شده Go (`borsd`) و فرانت‌اند مدرن `frontend-v2` اجرا می‌شود و دیتابیس‌ها و فرآیند همگام‌سازی کاملاً نیتیو بدون وابستگی به پایتون است.
3. **تغییرناپذیری داده‌های کاربر (Data Immutability Guarantee):**
   اسنپ‌شات‌های دریافتی در پوشه‌های نسلی ایزوله (`gens/gen_<id>`) نگهداری شده و `user.db` هرگز در جریان همگام‌سازی رونویسی یا تغییر داده نمی‌شود.
4. **حفظ ساختار گیت و عدم ادغام نارس:**
   تمام تغییرات در شاخه کاری `mission/stage4-production-activation-2026-11-08` نگهداری شده و بدون تایید مالک، هیچ ادغامی با `main` انجام نمی‌شود.

---

## ۵. حکم نهایی پذیرش مرحله ۴ (Final Acceptance Verdict)

با فعال‌سازی واقعی خط لوله روی GitHub Actions، اثبات ریاضی تطابق کلید امضا با کلید عمومی تعبیه‌شده در Client، انتشار مجموعه کامل ۶ دارایی روی ریلیز `v1.0.98`، و دریافت/راستی‌آزمایی/اعمال همان مجموعه توسط باینری ویندوزی از مسیر واقعی GitHub، وضعیت پروژه به شرح زیر است:

$$\mathbf{VERDICT:}\quad \text{STAGE4\_PRODUCTION\_ACTIVATED\_CLIENT\_VERIFIED}$$

| محور | شاهد قطعی | وضعیت |
| :--- | :--- | :---: |
| تطابق کلید | `bors-producer audit key` در Actions: KeyID `830BF752EF10076` | PASS |
| انتشار | Run [42508665247](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42508665247): ۶ دارایی، manifest 540 بایت | PASS |
| محتوای FTS | 1,188 ردیف: 37 STRONG، 336 WATCH، 359 REJECT، 366 بدون FTS، 90 EXCLUDED | PASS |
| دریافت Client | دانلود 91,547,928 بایت از GitHub، تأیید Minisign، اعمال نسل `v1.0.98` | PASS |
| دادهٔ کاربر | SHA-256 `user.db` قبل/بعد یکسان (0 بایت تغییر) | PASS |
| پایداری | Restart و بازخوانی نسل فعال | PASS |

**اقدامات باقی‌مانده (عملیاتی، نه کد):**

1. **تازه‌سازی روزانهٔ داده:** این انتشار از بیس‌لاین `data-latest` (تاریخ داده 1405-07-23) به‌همراه بازمحاسبهٔ FTS در 2026-11-08 ساخته شد. برای دادهٔ روز، دیمن `bors-producer` باید روی سرور توزیع اجرا شود یا منبع `data-latest` تازه شود. مسیر کد و زمان‌بندی 06:00 UTC تست شده است، اما استقرار systemd/docker روی سرور انجام نشده.
2. **کلید بدون مصرف در مخزن توزیع:** `TAURI_SIGNING_PRIVATE_KEY` در `johnwarchief/BorsTerminal` وجود دارد اما هیچ workflow‌ای آن را مصرف نمی‌کند. حذف این کلید تکراری پس از تأیید مالک توصیه می‌شود؛ مقدار آن در این بررسی خوانده یا افشا نشد.
3. **درشت‌دانگی نوار پیشرفت:** درصد دانلود در Client در سطح دارایی است (47.5٪ در تمام دانلود دارایی بزرگ و 90٪ در تمام مرحلهٔ اعمال)؛ متن وضعیت درست است اما درصد گام‌به‌گام نیست.

---

## ۶. سابقهٔ فعال‌سازی تولید (Production Activation Record, 2026-11-08)

### ۶.۱. مدیریت کلید امضا (Zero-Exposure Key Audit)

| مورد | یافته | نتیجه |
| :--- | :--- | :---: |
| محل Secret | `johnwarchief/BorsTerminal-src` → `TAURI_SIGNING_PRIVATE_KEY` (آخرین به‌روزرسانی 2026-09-22) | موجود |
| Secret دوم | `johnwarchief/BorsTerminal` → `TAURI_SIGNING_PRIVATE_KEY` (2026-09-19) | موجود، بدون مصرف‌کننده |
| بررسی ریاضی | Audit در Actions با همان Secret | PASS — KeyID `830BF752EF10076` |
| کلید عمومی Client (Go) | `sync.DefaultUpdatePubKey` | همان KeyID |
| کلید عمومی Client (Tauri) | `frontend/src-tauri/tauri.conf.json` | همان KeyID |
| بررسی محلی | `BORS_MINISIGN_KEY_FILE=.tauri/updater.key ./bin/bors-producer audit key` | PASS — همان KeyID |
| افشا | هیچ مقدار کلیدی در لاگ، فایل یا چت چاپ نشد | صفر |

روش استفادهٔ امن: مقدار Secret فقط به‌صورت متغیر محیطی (`BORS_MINISIGN_SECRET_KEY`) به باینری `bors-producer` در Runner داده می‌شود؛ خودِ ابزار فقط KeyID را چاپ می‌کند. هیچ استخراج Secret از GitHub انجام نشد و Workflow پیش‌فرض روی `mode=audit` است و انتشار فقط با `mode=publish` صریح انجام می‌شود.

**هشدار سازگاری چرخش کلید:** کلید عمومی داخل باینری‌های Client تعبیه شده است. اگر روزی کلید خصوصی چرخانده شود، Clientهای قدیمی اسنپ‌شات جدید را رد می‌کنند. ترتیب صحیح: انتشار Clientی که کلید عمومی جدید (و در صورت نیاز کلید قدیمی به‌صورت هم‌زمان) را می‌شناسد، سپس امضای اسنپ‌شات با کلید جدید و بازنشستگی کلید قدیمی. بدون این ترتیب، بازیابی فقط با به‌روزرسانی دستی Client ممکن است.

### ۶.۲. شواهد انتشار و دریافت

```text
Run:        42508665247 (workflow_dispatch, mode=publish, head=15dbb8e9)
Tag:        v1.0.98
Manifest:   snapshot_set_id=v1.0.98, created_at_utc=2026-11-08T18:12:34Z
market:     size=91,547,928  sha256=cb3b0f777431972595a5ae005fab1b3212f145bd88f2128921d052a6bf343123
codal:      size=4,497,675   sha256=213535eade17dce1ea9de6db0c582f6082782b859698c5ac0d1b559a2a11345a
Signer:     KeyID 0830BF752EF10076 (همان کلید عمومی تعبیه‌شده)
FTS recalc: 1,188 symbols در 53 ثانیه
Client E2E: python tools/test_installed_windows_client_e2e.py --live-github  → exit 0
```

خروجی آزمون زندهٔ Client (مسیر واقعی GitHub، بدون سرور شبیه‌ساز):

```text
[7] [955] stage=verifying, pct=80% ...
    [956] stage=applying, pct=90% ...
    [1446] stage=done, pct=100%, detail=اسنپ‌شات با موفقیت اعمال شد.
[8] Active Generation verified: v1.0.98
    New generation DB query: symbol فولاد -> verdict WATCH (verified!)
[9] Initial user.db SHA-256: d7f11b5ba654f3a6f78d0f66368024f618a19f4a0aae855eac0f4ebfb721b0a4
    Final   user.db SHA-256: d7f11b5ba654f3a6f78d0f66368024f618a19f4a0aae855eac0f4ebfb721b0a4
    PASS: user.db SHA-256 is 100% byte-for-byte identical (Zero Modification).
[10] PASS: Client reloaded active generation successfully after restart.
```

نکتهٔ مهم: دانلود و اعمال این مجموعه حدود 12 دقیقه طول کشید و از سقف 60 ثانیه‌ای قبلی عبور کرد؛ این آزمون مستقیماً اثبات می‌کند که اصلاح تایم‌اوت دانلود (حذف `http.Client.Timeout` کلی و حفظ `ResponseHeaderTimeout`) برای Client تولیدی لازم و کافی بوده است.

### ۶.۳. نقص‌های کشف‌شده و رفع‌شده در این فعال‌سازی

| نقص | ریشه | رفع | شاهد |
| :--- | :--- | :--- | :--- |
| شکست بازمحاسبهٔ FTS روی دیتابیس تولید | جدول `pipeline_dirty` با شمای قدیمی `(symbol, axis, reason, marked_at)` و نبود ستون `source` | مهاجرت حفظ‌داده در `EnsureRecalcSchema` و تست رگرسیون | `1188 symbols updated` |
| تایم‌اوت 60 ثانیه‌ای دانلود | `http.Client.Timeout` شامل خواندن بدنهٔ پاسخ می‌شود | حذف Timeout کلی، حفظ `ResponseHeaderTimeout=60s` و سقف 45 دقیقه‌ای Context | آزمون زنده 12 دقیقه‌ای PASS |
| انتشار اسنپ‌شات بدون FTS | Workflow قبلی فقط `data-latest` را بازمنتشر می‌کرد | Workflow جدید: Materialize → recalc --all → gate صفر نبودن FTS → build/sign/publish | 1,188 ردیف FTS |
| پنجرهٔ انتظار آزمون زنده | 150 ثانیه برای دانلود واقعی کافی نبود | 45 دقیقه در حالت `--live-github` | exit 0 |

**کامیت‌های مرتبط:** `a7be63d6` (مهاجرت شمای FTS)، `280aa4ac` (تایم‌اوت دانلود)، `15dbb8e9` (Workflow بازسازی FTS و آزمون زنده).
