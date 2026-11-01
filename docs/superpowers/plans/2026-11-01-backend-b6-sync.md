# B6 — حلقه‌ها: سینک، اینجشن و نظارت در Go (پلنِ اجرا)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** پیاده‌سازی و پورت لایه همگام‌سازی، مانیتورینگ وضعیت سینک، کنترل خزنده‌ها و ثبت اسنپ‌شات وضعیت بازار (`POST /api/mstat/snapshot`) در بک‌اند Go با انطباق ۱۰۰٪ برابری با پایتون، رعایت قیدهای عدم اتصال زنده به شبکه در فاز A و آزمون با گیت B-G3 بر مبنای بازپخش داده‌های ضبط‌شده آفلاین.

**Architecture:** تفکیک دقیق لایه خواندن وضعیت سینک (فایل‌های `sync_ondemand.json`, `sync_status.json`, `market_sync.json`, `codal_db_status.json`)؛ پیاده‌سازی ثبت اسنپ‌شات `mstat_snap` در `market.db`؛ مدیریت فایل‌های کنترلی `codal_control.json`؛ شبیه‌سازی و هندلینگ درخواست‌های همگام‌سازی بازار و کدال؛ حفظ اصل هم‌زیستی فاز A طبق تصمیمات مصوب مالک (§۱۵.۴).

**Tech Stack:** Go 1.22+, `net/http`, `database/sql`, `modernc.org/sqlite`, Python 3.12/FastAPI (مرجع پاریتی), `tools/parity`.

**Spec:** `docs/superpowers/specs/2026-10-29-backend-go-rewrite-design.md` §۸ (B6) · §۹ (گیت B-G3) · `docs/BorsTerminal-Desktop-Migration-Decisions.md` §۱۵.۴.

## Global Constraints

- هیچ درخواست واقعی به شبکه بیرونی (TSETMC یا Codal) ارسال نمی‌شود؛ تست‌ها ۱۰۰٪ آفلاین و با فیکسچر اجرا می‌شوند.
- هیچ کنترل واقعی سخت‌افزار یا دستگاه (ADB) اجرا نمی‌شود.
- اسکیماهای موجود در دیتابیس (`mstat_snap` و سایر جداول) بدون تغییر حفظ می‌شوند.
- پایتون در فاز A همچنان تنها مجری روتین‌های واکشی پس‌زمینه در محیط زنده باقی می‌ماند.
- ارقام فارسی در اسکریپت‌ها با `chr(0x06F0+d)` و گارد `persian_glyph_guard.py` رعایت می‌شود.
- عدم استفاده از `git checkout --`؛ حفظ CRLF/LF فایل‌ها.

---

## دامنه مسیرها در فاز B6

| مسیر | متد | منبع پایتون | هدف در B6 |
| :--- | :---: | :--- | :--- |
| `/api/mstat/snapshot` | POST | `api/market_status.py:395` | ذخیره یک نقطه اسنپ‌شات بازار در جدول `mstat_snap` |
| `/api/sync/status` | GET | `api/_sync_codal.py:377` | خواندن و ادغام وضعیت زنده فرآیندهای همگام‌سازی (on-demand، global و market) |
| `/api/sync/codal/db-status` | GET | `api/_sync_codal.py:362` | وضعیت لحظه‌ای دانلود/ادغام دیتابیس کدال از گیت‌هاب |
| `/api/sync/diagnose` | GET | `api/_sync_codal.py:463` | گزارش تشخیصی فرآیندها، وضعیت ADB و اتصالات |
| `/api/sync/market` | POST | `api/_sync_market.py:69` | تریگر همگام‌سازی دیتابیس بازار TSETMC |
| `/api/sync/codal` | POST | `api/_sync_codal.py:30` | تریگر اسکن و به‌روزرسانی کدال با مدهای مختلف |
| `/api/sync/codal/fts-refresh` | POST | `api/_sync_codal.py:63` | تازه‌سازی اختصاصی ۵ شاخص بنیادی FTS |
| `/api/sync/codal/db-download` | POST | `api/_sync_codal.py:341` | شروع دانلود دیتابیس اسنپ‌شات کدال |
| `/api/codal/control` | POST | `api/_sync_codal.py:570` | ارسال فرامین کنترلی (توقف، ادامه، ریست بن) |

---

## ساختار فایل‌ها و پکیج‌ها

```text
backend-go/
  internal/
    mstat/
      snapshot.go           # متد SaveSnapshot و ساختار ذخیره در mstat_snap
      snapshot_test.go      # تست واحد ذخیره اسنپ‌شات و شرایط ساعات معاملاتی
    sync/
      status.go             # خواندن و ترکیب فایل‌های sync status با در نظر گرفتن سن و تایم‌اوت
      status_test.go        # تست خواندن و تجمیع کانال‌های on-demand, global, market
      control.go            # مدیریت فایل کنترلی codal_control.json و قفل‌های همگام‌سازی
      control_test.go       # تست صدور فرامین pause/resume/stop
      diagnose.go           # جمع‌آوری اطلاعات تشخیصی پروسه‌ها و ADB
      diagnose_test.go      # تست ماک خروجی diagnose
      handlers.go           # هندلرهای HTTP برای تمام مسیرهای /api/sync/* و /api/codal/control
      handlers_test.go      # تست‌های httptest برای کدهای وضعیت و پاسخ‌ها
    httpapi/
      server.go             # ثبت مسیرهای B6 در mux
      server_test.go        # تست روتینگ و تقدم مسیرها
tools/parity/
  cases_b6.json             # سناریوهای پاریتی B6 (وضعیت‌ها، ارورها و اکشن‌ها)
  gate_b6.py                # گیت پاریتی B6 (شامل B-G1 و B-G3)
```

---

## وظایف اجرایی (Tasks)

### Task 0: پیاده‌سازی ذخیره اسنپ‌شات بازار `POST /api/mstat/snapshot`

**Files:**
- Create: `backend-go/internal/mstat/snapshot.go`
- Create: `backend-go/internal/mstat/snapshot_test.go`
- Modify: `backend-go/internal/mstat/handlers.go`
- Modify: `backend-go/internal/httpapi/server.go`

**Interfaces:**
- `SaveSnapshot(now time.Time) (map[string]any, error)`
- هندلر `ms.SnapshotNow` روی `POST /api/mstat/snapshot`

- [ ] **Step 1: پیاده‌سازی متد `SaveSnapshot` در پکیج `mstat`**
  بررسی ساعات کاری نشست معاملاتی (`inTradingSession`)، استخراج تجمیع آخرین وضعیت بازار (`SnapshotAgg`) و درج در جدول `mstat_snap` با فرمت JSON منقبض.
- [ ] **Step 2: نوشتن تست‌های واحد `snapshot_test.go`**
  بررسی رفتار در ساعات غیرمعاملاتی (`outside_trading_session`) و درج صحیح در دیتابیس تست SQLite.
- [ ] **Step 3: ثبت روت `POST /api/mstat/snapshot` در `handlers.go` و `server.go`**
- [ ] **Step 4: اجرای `go test ./internal/mstat/...` و اطمینان از سبزی تست‌ها**
- [ ] **Step 5: کامیت تسک ۰**

---

### Task 1: پیاده‌سازی پکیج `sync` و مسیرهای خواندنی وضعیت (Status & Diagnose)

**Files:**
- Create: `backend-go/internal/sync/status.go`
- Create: `backend-go/internal/sync/status_test.go`
- Create: `backend-go/internal/sync/diagnose.go`
- Create: `backend-go/internal/sync/diagnose_test.go`

**Interfaces:**
- `StatusReader` برای خواندن فایل‌های `sync_ondemand.json`, `sync_status.json`, `market_sync.json`, `codal_db_status.json`.
- متد `GetSyncStatus() map[string]any` با قوانین اولویت on-demand، بررسی سن فایل (۶۰۰ ثانیه / ۶۰ ثانیه).
- متد `GetCodalDBStatus() map[string]any` برای نمایش درصد دانلود و مرحله فعلی.
- متد `Diagnose() map[string]any` برای برگرداندن سلامت ابزارهای فرآیند و وضعیت ADB.

- [ ] **Step 1: پیاده‌سازی خواندن امن و تجمیع وضعیت‌های سینک در `status.go`**
- [ ] **Step 2: نوشتن تست‌های جامع وضعیت با داده‌های نمونه در `status_test.go`**
- [ ] **Step 3: پیاده‌سازی `Diagnose` در `diagnose.go` و تست‌های مربوطه**
- [ ] **Step 4: اجرای تست‌های واحد و کامیت تسک ۱**

---

### Task 2: پیاده‌سازی هندلرهای کنترل و تریگرهای سینک (`POST /api/sync/*`)

**Files:**
- Create: `backend-go/internal/sync/control.go`
- Create: `backend-go/internal/sync/control_test.go`
- Create: `backend-go/internal/sync/handlers.go`
- Create: `backend-go/internal/sync/handlers_test.go`
- Modify: `backend-go/internal/httpapi/server.go`
- Modify: `backend-go/cmd/borsd/main.go`

**Interfaces:**
- متدهای `ControlCodal(cmd string)`, `TriggerMarketSync()`, `TriggerCodalSync(mode string)`
- ثبت روت‌ها در `httpapi.Server`

- [ ] **Step 1: پیاده‌سازی قفل‌های درون‌برنامه‌ای و نوشتن در `codal_control.json` در `control.go`**
- [ ] **Step 2: پیاده‌سازی هندلرهای HTTP با اعتبارسنجی دقیق پارامترهای query و body در `handlers.go`**
- [ ] **Step 3: اتصال پکیج `sync` به `httpapi.Server` و رجیستر کردن روت‌ها**
- [ ] **Step 4: تست جامع هندلرها با `httptest` و اعتبارسنجی کدهای وضعیت**
- [ ] **Step 5: کامیت تسک ۲**

---

### Task 3: پیاده‌سازی گیت برابری B6 (گیت‌های B-G1 و B-G3)

**Files:**
- Create: `tools/parity/cases_b6.json`
- Create: `tools/parity/gate_b6.py`

- [ ] **Step 1: تدوین سناریوهای آزمون در `cases_b6.json`**
  - فراخوانی روت‌های وضعیت، دیاگ، اسنپ‌شات و اکشن‌های کنترل سینک.
- [ ] **Step 2: پیاده‌سازی اسکریپت `gate_b6.py`**
  - راه‌اندازی سرور پایتون و سرور Go با دیتابیس کپی و مسیر `BORS_DATA_DIR` ایزوله.
  - تست هم‌ارزی خروجی مسیرهای خواندنی و تریگرها.
- [ ] **Step 3: اجرای زنده گیت `gate_b6.py` و اطمینان از خروج صفر (Exit 0)**
- [ ] **Step 4: اجرای گاردهای رگرسیون ریپو (`persian_glyph_guard`, `version_anchor_guard`, `repo_hygiene_v97`)**
- [ ] **Step 5: کامیت نهایی فاز B6 و به‌روزرسانی مستندات پیشرفت**
