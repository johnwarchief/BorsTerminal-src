# B7 — تکمیل سطح نسخه ۱ در Go (پلنِ اجرا)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** تکمیل سطح نسخه ۱ و پورت تمام مسیرهای باقی‌مانده در بک‌اند Go با پوشش ۱۰۰٪ روی مسیرهای زنده شامل پورتفولیو/تصمیمات سبد (`/api/selection/*`)، شاخص کل TEDPIX (`/api/index/tedpix`)، خروجی داده‌ها (`/api/export`)، تاریخچه قیمت و اسکرینر بنیادی FTS (`/api/screener`, `/api/history/{symbol}`)، قیف FTS (`/api/funnel/*`)، تعیین تکلیف مسیرهای بازنشسته بدون مصرف‌کننده در UI، و اجرای موفق گیت برابری B7.

**Architecture:** تفکیک ماژولار پکیج‌های دامنه در `backend-go/internal/`: پکیج `selection` برای مدیریت دارایی‌ها در `user.db` و نگاشت طبقه‌بندی ابزارها؛ پکیج `marketindex` برای کندل‌های شاخص کل؛ پکیج `export` برای فرمت‌دهی CSV/داده‌ها با Content-Disposition امن فارسی؛ پکیج `screener` و `funnel` برای زنجیره غربالگری و قیف FTS؛ حفظ اصل هم‌زیستی با پایتون تا زمان تصمیم‌گیری نهایی G5.

**Tech Stack:** Go 1.22+, `net/http`, `database/sql`, `modernc.org/sqlite`, Python 3.12/FastAPI (مرجع پاریتی), `tools/parity`.

**Spec:** `docs/superpowers/specs/2026-10-29-backend-go-rewrite-design.md` §۸ (B7) · §۹ (گیت‌ها) · §۱۵ و §۱۶ · `docs/BorsTerminal-Desktop-Migration-Decisions.md` §۱۵.

## Global Constraints

- هیچ درخواست واقعی به اینترنت در آزمون‌های گیت زده نمی‌شود؛ تست‌ها آفلاین و مبتنی بر فیکسچر هستند.
- اسکیماهای موجود در دیتابیس‌ها بدون تغییر باقی می‌مانند.
- ارقام فارسی در اسکریپت‌ها با `chr(0x06F0+d)` و گارد `persian_glyph_guard.py` رعایت می‌شوند.
- عدم استفاده از `git checkout --`؛ حفظ CRLF/LF فایل‌ها.
- مسیرهای بدون مصرف‌کننده در UI با کد ۵۰۱ و پیام `NOT_PORTED` پاسخ صادقانه می‌دهند.

---

## دامنه مسیرها در فاز B7

| مسیر | متد | منبع پایتون | هدف در B7 |
| :--- | :---: | :--- | :--- |
| `/api/selection/symbols` | GET | `api/selection.py:52` | جستجوی نمادهای سهام و صندوق برای افزودن به سبد |
| `/api/selection/portfolio` | GET | `api/selection.py:167` | گزارش سبد دارایی، وزن‌ها، ارزش ریالی و ترکیب طبقات |
| `/api/selection/decision` | POST | `api/selection.py:230` | ثبت یا به‌روزرسانی تصمیم روی نماد در `selection_decisions` |
| `/api/selection/decision/{symbol}` | DELETE | `api/selection.py:319` | حذف تصمیم و بازگشت نماد به حالت بررسی‌نشده |
| `/api/index/tedpix` | GET | `api/market_index.py:207` | سری کندل‌های شاخص کل TEDPIX با اعمال مبنای قیمت |
| `/api/export` | GET & POST | `api/_export.py:150,178` | دانلود داده‌های جدولی در قالب CSV/XLSX با انکودینگ UTF-8 BOM |
| `/api/history/{symbol}` | GET | `api/screener.py:96` | تاریخچه کندل و حجم معاملات نماد با اعمال `price_basis` |
| `/api/screener` | GET | `api/screener.py:311` | جدول غربالگری ۵ شاخص FTS و فیلترهای منتخب |
| `/api/funnel/registry` | GET | `api/funnel.py:173` | رجیستری متادیتا و تنظیمات زنجیره‌های قیف FTS |
| `/api/funnel` | GET & POST | `api/funnel.py:212,219` | ارزیابی قیف FTS و جدول وضعیت |
| `/api/funnel/trace` | GET | `api/funnel.py:179` | خط زمانی تصمیمات قیف برای یک نماد مشخص |
| `/api/adb/*`, `/api/sync/delta`, … | * | `api/engine.py`, `api/adb.py` | مسیرهای بازنشسته بدون UI (پاسخ ۵۰۱ NOT_PORTED) |

---

## وظایف اجرایی (Tasks)

### Task 0: پیاده‌سازی پکیج `internal/selection` (سبد دارایی و تصمیمات پورتفولیو)

**Files:**
- Create: `backend-go/internal/selection/symbols.go`
- Create: `backend-go/internal/selection/portfolio.go`
- Create: `backend-go/internal/selection/decision.go`
- Create: `backend-go/internal/selection/handlers.go`
- Create: `backend-go/internal/selection/selection_test.go`
- Modify: `backend-go/internal/httpapi/server.go`

- [x] **Step 1: پیاده‌سازی جستجوی نمادها و طبقه‌بندی دارایی‌ها در `symbols.go`**
- [x] **Step 2: پیاده‌سازی محاسبه وزن‌ها و تجمیع سبد در `portfolio.go`**
- [x] **Step 3: پیاده‌سازی ثبت، ویرایش و حذف در `selection_decisions` در `decision.go`**
- [x] **Step 4: پیاده‌سازی هندلرهای HTTP و تست‌های واحد در `selection_test.go`**
- [x] **Step 5: سیم‌کشی روت‌ها در `httpapi.Server` و کامیت تسک ۰**

---

### Task 1: پیاده‌سازی پکیج `internal/marketindex` (شاخص کل بورس TEDPIX)

**Files:**
- Create: `backend-go/internal/marketindex/tedpix.go`
- Create: `backend-go/internal/marketindex/handlers.go`
- Create: `backend-go/internal/marketindex/tedpix_test.go`
- Modify: `backend-go/internal/httpapi/server.go`

- [x] **Step 1: پیاده‌سازی مدل کندل‌های شاخص، تبدیل تاریخ و نگاشت فیلدها**
- [x] **Step 2: اعمال هندسه کندل (`candlecontract.Widen`) و مبنای قیمت (`pricebasis.Resolve`)**
- [x] **Step 3: مدیریت کش و خطای صادقانه ۵۰۲ در غیاب شبکه**
- [x] **Step 4: تست‌های واحد و کامیت تسک ۱**

---

### Task 2: پیاده‌سازی پکیج `internal/export` (خروجی داده‌ها)

**Files:**
- Create: `backend-go/internal/export/export.go`
- Create: `backend-go/internal/export/handlers.go`
- Create: `backend-go/internal/export/export_test.go`
- Modify: `backend-go/internal/httpapi/server.go`

- [x] **Step 1: پیاده‌سازی تولید خروجی CSV با هدر UTF-8 BOM (`\ufeff`) و خطوط متادیتا**
- [x] **Step 2: تولید هدر Content-Disposition امن مطابق RFC 5987**
- [x] **Step 3: هندلر `POST /api/export` با سقف ردیف/ستون و هندلر `GET /api/export`**
- [x] **Step 4: تست‌های واحد و کامیت تسک ۲**

---

### Task 3: پیاده‌سازی تاریخچه نماد و اسکرینر بنیادی (`/api/history/{symbol}`, `/api/screener`)

**Files:**
- Create: `backend-go/internal/screener/history.go`
- Create: `backend-go/internal/screener/screener.go`
- Create: `backend-go/internal/screener/handlers.go`
- Create: `backend-go/internal/screener/screener_test.go`
- Modify: `backend-go/internal/httpapi/server.go`

- [x] **Step 1: پیاده‌سازی `GET /api/history/{symbol}` از جدول `daily_prices` با `pricebasis.Resolve`**
- [x] **Step 2: پیاده‌سازی خواندن کش دیسک/رم اسکرینر و نتایج مادی‌شده FTS**
- [x] **Step 3: اعمال وتوی مجمع و فیلتر نمادها**
- [x] **Step 4: تست‌های واحد و کامیت تسک ۳**

---

### Task 4: پیاده‌سازی قیف FTS و تعیین تکلیف مسیرهای بازنشسته (`/api/funnel/*`, 501 NOT_PORTED)

**Files:**
- Create: `backend-go/internal/funnel/registry.go`
- Create: `backend-go/internal/funnel/evaluator.go`
- Create: `backend-go/internal/funnel/handlers.go`
- Create: `backend-go/internal/funnel/funnel_test.go`
- Modify: `backend-go/internal/httpapi/server.go`
- Modify: `backend-go/cmd/borsd/main.go`

- [x] **Step 1: پیاده‌سازی رجیستری زنجیره‌های قیف در `registry.go`**
- [x] **Step 2: هندلرهای `GET /api/funnel`, `POST /api/funnel`, `GET /api/funnel/trace`**
- [x] **Step 3: ثبت صریح مسیرهای بازنشسته بدون UI با کد ۵۰۱ NOT_PORTED**
- [x] **Step 4: تست‌های واحد، اتصال به `borsd` و کامیت تسک ۴**

---

### Task 5: پیاده‌سازی و اجرای گیت برابری B7

**Files:**
- Create: `tools/parity/cases_b7.json`
- Create: `tools/parity/gate_b7.py`

- [x] **Step 1: تدوین سناریوهای آزمون در `cases_b7.json` شامل تمام روت‌های فعال و بازنشسته**
- [x] **Step 2: پیاده‌سازی اسکریپت `gate_b7.py` (سنجش برابری خواندن B-G1 و نوشتن B-G2)**
- [x] **Step 3: اجرای زنده گیت B7 و اعتبارسنجی خروج صفر و $\Delta = 0.0$**
- [x] **Step 4: اجرای گاردهای ریپو (`persian_glyph_guard`, `version_anchor_guard`, `repo_hygiene_v97`)**
- [x] **Step 5: کامیت نهایی فاز B7 و ذخیره کارنامه `_audit/parity/B7.json`**
