# برنامه اجرایی مرحله اول: ممیزی کامل، تثبیت زیرساخت و رفع ریسک‌های پایه

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** تثبیت کامل زیرساخت، ممیزی جامع، رفع ریسک‌های همزمانی داده و چرخهٔ حیات Go، ارتقای CI و آماده‌سازی پایدار برای ورود به مرحله دوم مهاجرت به Go.

**Architecture:** استقرار انحصاری فرانت‌اند روی `frontend-v2`، اعمال ساختاری و متقارن Single Writer برای `market.db` و `codal.db` با `mode=ro`، مسدودسازی ساختاری هرگونه bypass روی `sql.Open`، مهار سخت‌افزاری/نرم‌افزاری تمام حلقه‌ها با `--no-loops`، اثبات تجربی Zero Disk Writes برای `--read-only`، مدیریت جامع Shutdown در شرایط انقضای تایم‌اوت، و افزودن پایپ‌لاین Go و Frontend V2 به CI.

**Tech Stack:** Go (1.26.3 محلی / 1.27.x پایدار CI), SQLite (`modernc.org/sqlite`), React 18, TypeScript, Tailwind CSS v4, Vitest, KLineCharts v10, Python 3.12 (جهت ممیزی و پاریتی).

**Spec:** [`docs/superpowers/specs/2026-11-07-python-elimination-stage-1-design.md`](file:///c:/Users/PCMOD/Desktop/BorsTerminal/docs/superpowers/specs/2026-11-07-python-elimination-stage-1-design.md)

## Global Constraints

- هیچ قابلیت، الگوریتم، دقت داده یا ویژگی بصری نباید تضعیف یا حذف شود.
- `market.db` و `codal.db` در Go همیشه و منحصراً با `mode=ro` باز می‌شوند.
- هیچ فراخوانی مستقیمی به `sql.Open` خارج از `internal/db` مجاز نیست (با گارد AST در CI).
- پرچم `--read-only` باید Zero Disk Writes واقعی (عدم لمس wal/shm، عدم ساخت دیتابیس غایب، لاگ به stdout) را اثبات کند.
- پرچم `--no-loops` باید تمام تیکرها، ورکرها و فید زنده را به صورت ۱۰۰٪ مهار کند.
- فرآیند Shutdown در صورت انقضای ۵ ثانیه باید کانکشن‌ها را قطع، ثبت کارهای جدید را مسدود، کارهای فعال را لغو و دیتابیس را فقط پس از توقف هندلرها ببندد.
- هیچ تستی نباید با حذف یا تضعیف Assertionها سبز شود؛ تثبیت تست‌های پایتون فقط از طریق Fixtureهای پایدار انجام می‌شود.
- بهداشت مخزن با بررسی تک‌به‌تک فایل‌ها انجام می‌شود و نادیده‌گیری کورکورانه ممنوع است.
- بنچمارک Go و Python باید روی سخت‌افزار، دیتابیس و اندپوینت‌های معادل انجام شود.

---

### Task 1: تدوین اسناد ممیزی ۱ و ۲ (موجودی سیستم و مالکیت API و دیتابیس)

**Files:**
- Create: `docs/migration/python-elimination/01-runtime-inventory.md`
- Create: `docs/migration/python-elimination/02-api-and-data-ownership.md`
- Test: `tools/verify_audit_docs.py`

**Interfaces:**
- Consumes: `backend-go/internal/httpapi/routes.json`, کدهای `app.py`, `tape_flags.py`, `fts_engine.py`, `mstat_engine.py`, `codal_fetcher.py`.
- Produces: ماتریس ۱۰۵ اندپوینت با برچسب‌های `COMPLETE_VERIFIED`, `PARTIAL_OR_DEGRADED`, `STUB_501`, `MISSING` و جدول مالکیت جداول SQLite.

- [ ] **Step 1: ایجاد پوشه مستندات مهاجرت**
  ایجاد مسیر `docs/migration/python-elimination/`.

- [ ] **Step 2: نوشتن اسکریپت اعتبارسنجی اسناد ممیزی (`tools/verify_audit_docs.py`)**
  اسکریپتی که بررسی می‌کند اسناد ۱ و ۲ ایجاد شده‌اند، فاقد TODO یا TBD هستند، جدول ۱۰۵ اندپوینت را کامل پوشش داده‌اند و تمام جداول پایگاه داده در ماتریس مالکیت فهرست شده‌اند.

- [ ] **Step 3: تدوین `01-runtime-inventory.md`**
  ممیزی جامع هر ماژول پایتون و پیاده‌سازی متناظر در Go، وضعیت وابستگی ران‌تایم، وضعیت پاریتی و آمادگی مهاجرت.

- [ ] **Step 4: تدوین `02-api-and-data-ownership.md`**
  ماتریس کامل ۱۰۵ اندپوینت طبق تعریف جدید `COMPLETE_VERIFIED`، مصرف‌کنندگان در `frontend-v2`، نگاشت جداول `market.db`, `codal.db`, `user.db` و قیدهای تک‌نویسنده.

- [ ] **Step 5: اجرای اعتبارسنجی اسناد**
  اجرای `python tools/verify_audit_docs.py` و اطمینان از خروجی PASS.

- [ ] **Step 6: کامیت**
  ```bash
  git add docs/migration/python-elimination/ tools/verify_audit_docs.py
  git commit -m "docs(migration): نگارش اسناد ممیزی موجودی و مالکیت API و دیتابیس"
  ```

---

### Task 2: گیت معماری آزمون AST ضد دورزدن `sql.Open` و دسترسی مستقیم دیسک

**Files:**
- Create: `backend-go/internal/db/arch_test.go`
- Test: `backend-go/internal/db/arch_test.go`

**Interfaces:**
- Consumes: کل فایل‌های منبع Go در `backend-go/**/*.go`.
- Produces: تست معماری که هرگونه فراخوانی مستقیم `sql.Open` یا دسترسی نوشتن مستقیم به فایلهای `.db` خارج از `internal/db` را رد می‌کند.

- [ ] **Step 1: نوشتن تست معماری AST در `backend-go/internal/db/arch_test.go`**
  استفاده از پکیج‌های `go/parser`, `go/token`, `go/ast` برای پیمایش درخت نحو تمام فایل‌های `backend-go` و بررسی موارد زیر:
  - هیچ فراخوانی به `sql.Open` یا `sql.OpenDB` خارج از پکیج `db` وجود ندارد.
  - هیچ فراخوانی به توابع ساخت/نوشتن فایل (`os.Create`, `os.OpenFile`, `os.WriteFile`) با نام یا الگوی فایلهای دیتابیس (`.db`, `.db-wal`, `.db-shm`) خارج از پکیج `db` وجود ندارد.

- [ ] **Step 2: اجرای تست برای بررسی پاس بودن آن در وضعیت فعلی**
  ```bash
  cd backend-go && go test -v ./internal/db -run TestArchitectureNoDirectSQLOpen
  ```
  انتظار: PASS بدون خطا.

- [ ] **Step 3: کامیت**
  ```bash
  git add backend-go/internal/db/arch_test.go
  git commit -m "test(arch): افزودن گیت معماری AST ضد فراخوانی مستقیم sql.Open"
  ```

---

### Task 3: اعمال ساختاری و متقارن Single Writer برای `market.db` و `codal.db` (`db.go`)

**Files:**
- Modify: `backend-go/internal/db/db.go`
- Modify: `backend-go/internal/db/db_test.go`

**Interfaces:**
- Consumes: مسیر `dataDir` و پرچم `readOnly`.
- Produces: `Handles` با اتصالات `Market` (`mode=ro`), `Codal` (`mode=ro`) و `User` (`mode=rwc` یا `mode=ro`).

- [ ] **Step 1: افزودن تست‌های رد نوشتن در `market.db` و `codal.db` در `backend-go/internal/db/db_test.go`**
  تست‌هایی که اثبات می‌کنند تلاش برای اجرای `CREATE TABLE`, `INSERT`, `UPDATE` روی اتصالات `Market` و `Codal` در هر شرایطی با خطای `attempt to write a readonly database` رد می‌شود؛ و در حالت `readOnly=true`، نوشتن روی `User` نیز رد شده و اگر `user.db` وجود نداشته باشد، فایلی ساخته نمی‌شود.

- [ ] **Step 2: اصلاح پیاده‌سازی `backend-go/internal/db/db.go`**
  - تنظیم قطعی `mode=ro` برای `market.db` همیشه.
  - باز کردن `codal.db` در `Open` با `mode=ro` همیشه.
  - تنظیم `mode=ro` برای `user.db` هنگام `readOnly=true`؛ و افزودن `_pragma=query_only=ON` در حالت Read-only.
  - جلوگیری از ساخت فایل صفر-بایتی در صورت غیاب `user.db` در حالت Read-only (بررسی با `os.Stat` قبل از باز کردن با `mode=ro`).

- [ ] **Step 3: اجرای تست‌های پکیج db**
  ```bash
  cd backend-go && go test -v ./internal/db
  ```
  انتظار: PASS.

- [ ] **Step 4: کامیت**
  ```bash
  git add backend-go/internal/db/db.go backend-go/internal/db/db_test.go
  git commit -m "fix(db): اعمال ساختاری Single Writer و تقارن ro برای market.db و codal.db"
  ```

---

### Task 4: پیاده‌سازی و آزمون واقعی Zero Disk Writes برای `--read-only`

**Files:**
- Modify: `backend-go/internal/market/service.go`
- Create: `backend-go/internal/market/lifecycle_test.go`
- Modify: `backend-go/cmd/borsd/main.go`

**Interfaces:**
- Consumes: تنظیمات `config.Config` با `ReadOnly: true`.
- Produces: رفتار تضمین‌شدهٔ عدم تغییر حتی یک بایت روی دیسک (RAM-only Cache و Stdout Logging).

- [ ] **Step 1: نوشتن تست جامع Zero Disk Writes در `lifecycle_test.go`**
  تستی که یک محیط موقت شامل کپی `market.db` ایجاد می‌کند، درخت فایل‌ها و هش‌ها و mtimeهای تمام فایل‌ها را قبل از شروع ثبت می‌کند، سرویس را با `ReadOnly: true` بالا می‌آورد، درخواست‌های تابلو و چارت ارسال می‌کند، سرویس را متوقف می‌کند، و تطابق ۱۰۰٪ هش و اندازهٔ تمام فایل‌ها و عدم تولید هیچ فایل جدیدی (از جمله `-wal`, `-shm`, کش یا لاگ) را اثبات می‌کند.

- [ ] **Step 2: اصلاح متدهای ذخیره‌سازی کش در `market/service.go`**
  در صورت `s.cfg.ReadOnly == true`، متد `storeCache` بلافاصله بدون نوشتن دیسک بازمی‌گردد و کش فقط در حافظهٔ موقت RAM نگهداری می‌شود.

- [ ] **Step 3: اصلاح هدایت لاگ‌ها در `cmd/borsd/main.go`**
  در حالت `ReadOnly: true`، لاگر به صورت انحصاری روی `os.Stdout` یا `os.Stderr` می‌نویسد و هیچ فایل لاگی روی دیسک ایجاد نمی‌شود.

- [ ] **Step 4: اجرای تست Zero Disk Writes**
  ```bash
  cd backend-go && go test -v ./internal/market -run TestReadOnlyZeroDiskWrites
  ```
  انتظار: PASS.

- [ ] **Step 5: کامیت**
  ```bash
  git add backend-go/internal/market/service.go backend-go/internal/market/lifecycle_test.go backend-go/cmd/borsd/main.go
  git commit -m "feat(lifecycle): تضمین و آزمون واقعی Zero Disk Writes در حالت read-only"
  ```

---

### Task 5: مهار سخت‌افزاری/نرم‌افزاری تمام حلقه‌ها با `--no-loops`

**Files:**
- Modify: `backend-go/internal/market/service.go`
- Modify: `backend-go/internal/mstat/service.go`
- Modify: `backend-go/internal/market/lifecycle_test.go`

**Interfaces:**
- Consumes: تنظیمات `config.Config` با `NoLoops: true`.
- Produces: مهار کامل هرگونه Goroutine آزاد، بازسازی ناهمگام، و حلقه‌های واکشی زنده.

- [ ] **Step 1: نوشتن تست اثبات عدم اجرای کار پس‌زمینه با `--no-loops` در `lifecycle_test.go`**
  تستی که بررسی می‌کند با `NoLoops: true`، هیچ بازسازی ناهمگام یا تسک پس‌زمینه‌ای اجرا نمی‌شود و شمارش کارهای فعال صفر می‌ماند.

- [ ] **Step 2: اعمال شرط بازدارنده در `rebuildAsync` و تسک‌های پس‌زمینه**
  در `market/service.go`:
  ```go
  if s.cfg.NoLoops {
      return
  }
  ```
  همین بررسی برای سرویس‌های `mstat` و Live Feed نیز اعمال می‌شود.

- [ ] **Step 3: اجرای تست‌های پکیج market**
  ```bash
  cd backend-go && go test -v ./internal/market -run TestNoLoopsSuppressesAsyncWork
  ```
  انتظار: PASS.

- [ ] **Step 4: کامیت**
  ```bash
  git add backend-go/internal/market/service.go backend-go/internal/mstat/service.go backend-go/internal/market/lifecycle_test.go
  git commit -m "fix(lifecycle): اعمال بازدارندگی قطعی --no-loops بر تمام کارهای پس‌زمینه"
  ```

---

### Task 6: مدیریت جامع Graceful Shutdown در شرایط انقضای مهلت و خروج پاکیزه

**Files:**
- Modify: `backend-go/cmd/borsd/main.go`
- Modify: `backend-go/internal/httpapi/server.go`
- Create: `backend-go/cmd/borsd/main_test.go`

**Interfaces:**
- Consumes: سیگنال‌های `SIGINT`/`SIGTERM` و تایم‌اوت ۵ ثانیه‌ای.
- Produces: رویهٔ خاموش شدن ترتیبی، قطع ارتباطات در انقضا، لغو کارهای فعال و بستن دیتابیس پس از توقف هندلرها.

- [ ] **Step 1: نوشتن تست‌های Shutdown و Startup Error در `cmd/borsd/main_test.go`**
  تست اعتبارسنجی خروج تمیز در دریافت سیگنال و آزمون خروج با کد ۱ در صورت اشغال پورت یا عدم دسترسی به دیتابیس.

- [ ] **Step 2: بازنویسی منطق خاموشی در `cmd/borsd/main.go`**
  پیاده‌سازی دقیق سناریوی انقضای مهلت:
  1. شروع `srv.Shutdown(shutdownCtx)`.
  2. در صورت انقضای مهلت ۵ ثانیه (`shutdownCtx.Err() != nil`)، فراخوانی `srv.Close()` برای بستن اجباری اتصالات باز و اتصالات Hijacked.
  3. اعمال فلگ اتمیک `shuttingDown = true` تا از ثبت هرگونه `wg.Add()` جدید جلوگیری شود.
  4. لغو سراسری Contextهای فعال هندلرها و کارها.
  5. انتظار برای تکمیل یا لغو تمام ورکرها.
  6. بستن قطعی دیتابیس‌ها (`handles.Close()`).
  7. مدیریت خطاهای Startup با خروج سریع (کد ۱) و پیام ساختاریافته.

- [ ] **Step 3: اجرای تست‌های borsd**
  ```bash
  cd backend-go && go test -v ./cmd/borsd
  ```
  انتظار: PASS.

- [ ] **Step 4: کامیت**
  ```bash
  git add backend-go/cmd/borsd/main.go backend-go/internal/httpapi/server.go backend-go/cmd/borsd/main_test.go
  git commit -m "feat(shutdown): پیاده‌سازی مدیریت جامع Graceful Shutdown در شرایط انقضای مهلت"
  ```

---

### Task 7: تثبیت داده‌ای تست‌های ناموفق پایتون و پاکسازی هوشمند بهداشت مخزن

**Files:**
- Create: `dev/fixtures/mstat_baseline_fixture.py`
- Modify: `dev/mstat_local_v975.py`
- Modify: `dev/board_hist_cache_v1056.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: دیتابیس محلی و فایل‌های Untracked.
- Produces: اجرای ۱۰۰٪ سبز تمام تست‌های پایتون در `run_all_tests.py` بدون تضعیف هیچ شرطی، و پاکیزگی کامل مخزن در `git ls-files --others`.

- [ ] **Step 1: تثبیت داده‌ای `dev/mstat_local_v975.py`**
  تأمین شرایط داده‌ای منجمدشده برای دو سنجهٔ مربوط به ارزش بازار و برچسب سلامت بدون تغییر در Assertionها.

- [ ] **Step 2: تثبیت داده‌ای `dev/board_hist_cache_v1056.py`**
  تأمین ردیف‌های تاریخی ثابت برای فیلترهای روبیک و نقطه بدون دستکاری در شروط آزمون.

- [ ] **Step 3: بازبینی تک‌به‌تک فایل‌های Untracked و به‌روزرسانی هوشمند `.gitignore`**
  - افزودن فایل‌های موقت کاری، PIDها، فایل‌های dump و لاگ‌های تست به `.gitignore`.
  - افزودن فایل‌های مفید و مهارت‌ها (`.agents/skills/agent-desktop/` و اسکریپت‌های تحلیلی) به مرحلهٔ Stage گیت.
  - اطمینان از اینکه `git ls-files --others --exclude-standard` خروجی کاملاً خالی برمی‌گرداند.

- [ ] **Step 4: اجرای کل تست‌های آفلاین پایتون**
  ```bash
  $env:PYTHONIOENCODING="utf-8"; python dev/run_all_tests.py
  ```
  انتظار: ۱۰۰٪ تست‌ها سبز و خروجی `ALL TESTS PASSED`.

- [ ] **Step 5: کامیت**
  ```bash
  git add dev/ .gitignore .agents/skills/
  git commit -m "fix(guards): تثبیت داده‌ای تست‌های پایتون با فیچر پایدار و بهداشت کامل مخزن"
  ```

---

### Task 8: ارتقای خط لولهٔ CI (`.github/workflows/guards.yml`)

**Files:**
- Modify: `.github/workflows/guards.yml`

**Interfaces:**
- Consumes: GitHub Actions runner.
- Produces: جاب‌های خودکار Go (Go پایدار), Frontend V2 (Node 22), Python Guards و Repo Hygiene.

- [ ] **Step 1: افزودن جاب Go به `.github/workflows/guards.yml`**
  - نصب Go با اکشن `actions/setup-go@v5` روی نسخهٔ پایدار (`1.27.x` یا `stable`).
  - اجرای تست‌ها: `cd backend-go && go test -v ./...`
  - اجرای وِت: `cd backend-go && go vet ./...`

- [ ] **Step 2: افزودن جاب Frontend V2 به `.github/workflows/guards.yml`**
  - نصب Node 22 با `actions/setup-node@v4`.
  - اجرای `cd frontend-v2 && npm ci`.
  - اجرای `cd frontend-v2 && npm run typecheck`.
  - اجرای `cd frontend-v2 && npx vitest run`.
  - اجرای `cd frontend-v2 && npm run build`.

- [ ] **Step 3: حفظ جاب‌های پایتون و بهداشت مخزن با تست‌های تثبیت‌شده**

- [ ] **Step 4: اعتبارسنجی سینتکس ورک‌فلو با ابزارهای بررسی محلی**

- [ ] **Step 5: کامیت**
  ```bash
  git add .github/workflows/guards.yml
  git commit -m "ci: افزودن ارزیابی خودکار Go، Frontend V2 و گیت‌های معماری به CI"
  ```

---

### Task 9: اجرای بنچمارک منصفانه و تدوین سند خطوط مبنا (Document 03)

**Files:**
- Create: `tools/fair_benchmark.py`
- Create: `docs/migration/python-elimination/03-baseline-and-acceptance-gates.md`

**Interfaces:**
- Consumes: دیتابیس‌های ثابت و سرورهای Go و Python روی پورت‌های مستقل.
- Produces: گزارش عددی Cold Start, RAM, CPU و p50/p95 تأخیر برای اندپوینت‌های معادل، و ثبت رسمی گیت‌های مرحله اول با برچسب‌های PASS/FAIL/NOT_MEASURED.

- [ ] **Step 1: ایجاد ابزار بنچمارک منصفانه (`tools/fair_benchmark.py`)**
  اسکریپتی که در شرایط کاملاً یکسان سخت‌افزاری و دیتابیسی، سه اندپوینت معادل (`/api/market`, `/api/chart/فولاد`, `/api/mstat/summary`) را روی هر دو سرور تست کرده و نتایج را با انحراف معیار ثبت می‌کند.

- [ ] **Step 2: اجرای بنچمارک و ثبت نتایج عددی واقعی**
  اجرای بنچمارک و استخراج ارقام دقیق شروع سرد، مصرف رم و تأخیر.

- [ ] **Step 3: نگارش سند `03-baseline-and-acceptance-gates.md`**
  ثبت جداول نتایج بنچمارک، ثبت کارنامهٔ ارزیابی گیت‌های مرحله اول، و وضعیت نهایی تمامی معیارها.

- [ ] **Step 4: کامیت**
  ```bash
  git add tools/fair_benchmark.py docs/migration/python-elimination/03-baseline-and-acceptance-gates.md
  git commit -m "docs(migration): ثبت بنچمارک منصفانه و سند خطوط مبنا و گیت‌های پذیرش مرحله اول"
  ```
