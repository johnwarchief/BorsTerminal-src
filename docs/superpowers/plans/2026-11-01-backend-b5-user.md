# B5 — کاربر: واچ‌لیست و مرکز اعلان‌ها رویِ Go (پلنِ اجرا)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** پیاده‌سازی و پورت کامل لایه کاربر (واچ‌لیست پایدار در `user.db` و مرکز اعلان‌های کدال از `market.db`) در بک‌اند Go با انطباق ۱۰۰٪ برابری با پایتون، رعایت گیت B-G2 (نوشتن ردیف‌به‌ردیف) و فیلتر افزودنی `?symbol=` روی فید اعلان‌ها.

**Architecture:** تفکیک روشن خواندن و نوشتن؛ نوشتن روی `user.db` با کلید نرمال‌شده `symbol_norm` (`fts_engine.norm_fa`)، کنترل ظرفیت و هم‌زمانی SQLite؛ خواندن اعلان‌ها از `codal_notices` در `market.db` با طبقه‌بندی نه ۹گانه و تجمیع موارد تکراری بدون سرویس بیرونی؛ ثبت هندلرها در `httpapi.Server`.

**Tech Stack:** Go 1.22+, `database/sql`, `modernc.org/sqlite`, Python 3.12/FastAPI (مرجع پاریتی), `tools/parity`.

**Spec:** `docs/superpowers/specs/2026-10-29-backend-go-rewrite-design.md` §۸ (B5) · §۹ (گیت‌های B-G1 و B-G2) · §۱۱ (قرارداد داده‌های UI)

## Global Constraints

- هیچ داده ساختگی یا حدسی اختراع نمی‌شود؛ مفقود بودن مقدار یعنی `null` یا تهی.
- هیچ تغییری در ساختار جداول موجود داده نمی‌شود؛ اسکیماهای `user_watchlists` و `codal_notices` کاملاً منجمدند.
- فیلد افزودنی `?symbol=` ابتدا در پایتون (§۸ و §۱۱) تست و اثبات می‌شود، سپس در Go پورت می‌گردد.
- تبدیل نوشتار فارسی/عربی با `norm_fa` دقیقاً معادل `fts_engine.norm_fa` (تبدیل ي/ك/ى و حذف نیم‌فاصله) انجام می‌شود.
- سقف پیش‌فرض واچ‌لیست ۵۰ است (قابل پیکربندی در `fts_config.json`، مقید به بازه ۱ تا ۶۰).
- ارقام فارسی در اسکریپت‌ها با `chr(0x06F0+d)` و گارد `persian_glyph_guard.py` رعایت می‌شود.
- عدم استفاده از `git checkout --`؛ حفظ CRLF/LF فایل‌ها.

---

## دامنه مسیرها در فاز B5

| مسیر | متد | منبع پایتون | هدف در B5 |
| :--- | :---: | :--- | :--- |
| `/api/watchlist` | GET | `api/watchlist.py:18` | خواندن فهرست واچ‌لیست کاربر (`added_at DESC, symbol_norm ASC`) |
| `/api/watchlist` | POST | `api/watchlist.py:33` | افزودن/ویرایش نماد با کلید `symbol_norm` و بررسی سقف ۵۰ تایی |
| `/api/watchlist/{symbol}` | DELETE | `api/watchlist.py:77` | حذف نماد بر اساس کلید نرمال |
| `/api/notifications/sources` | GET | `api/notifications.py:23` | گزارش سلامت منبع اطلاعیه‌های کدال از `codal_notices` |
| `/api/notifications/feed` | GET | `api/notifications.py:33` | دریافت زنده اطلاعیه‌ها با فیلترهای `since`, `levels`, `limit` و فیلتر جدید `symbol` |
| `/api/watchlist/matrix` | GET | `api/watchlist.py:92` | **تعویق به B7 (۵۰۱ NOT_PORTED)** — نیازمند `confidence_engine` است |

---

## ساختار فایل‌ها و پکیج‌ها

```text
backend-go/
  internal/
    watchlist/
      store.go              # مدیریت CRUD و ذخیره‌سازی در user.db با کلید نرمال
      store_test.go         # تست‌های واحد CRUD، سقف ۵۰ و نرمال‌سازی
      handlers.go           # هندلرهای HTTP (GET, POST, DELETE)
      handlers_test.go      # تست‌های هندلر با httptest و کدهای وضعیت
    notifications/
      classify.go           # طبقه‌بندی ۹گانه نوع و ۴ سطحی اهمیت اطلاعیه‌ها
      classify_test.go      # تست وکتورهای طبقه‌بندی
      feed.go               # کوئری‌های Sources و Feed از codal_notices
      feed_test.go          # تست‌های فیلتر، ادغام تکراری‌ها و منذ
      handlers.go           # هندلرهای HTTP برای sources و feed
      handlers_test.go      # تست‌های هندلرهای اعلان‌ها
    httpapi/
      server.go             # رجیستر کردن روت‌های B5 در mux
      server_test.go        # تست روتینگ و تقدم مسیرها
tools/parity/
  cases_b5.json             # سناریوهای پاریتی B5 (خواندن و نوشتن)
  gate_b5.py                # گیت پاریتی B5 شامل B-G1 و B-G2
dev/
  test_watchlist_fixture_b5.py # گارد فیکسچر و تست‌های رگرسیون B5
```

---

## وظایف اجرایی (Tasks)

### Task 0: پیاده‌سازی و تست فیلتر افزودنی `?symbol=` در پایتون

**Files:**
- Modify: `api/notifications.py:33-49`
- Modify: `notifications.py:106-158`
- Create: `dev/test_notifications_symbol_b5.py`

**Interfaces:**
- `N.feed(conn, since=None, levels=None, limit=120, symbol=None) -> dict`

- [ ] **Step 1: ایجاد تست پایتون برای فیلتر symbol**
  نوشتن `dev/test_notifications_symbol_b5.py` که واکشی فید با `symbol` مشخص را تست کرده و اطمینان حاصل می‌کند که فقط اطلاعیه‌های همان نماد (یا نماد نرمال‌شده) بازگردانده می‌شوند.
- [ ] **Step 2: اجرای تست برای دیدن fail اولیه**
- [ ] **Step 3: اعمال تغییر در `notifications.py` و `api/notifications.py`**
  افزودن پارامتر `symbol: str = Query("")` به روت و اعمال فیلتر بر اساس `fts_engine.norm_fa` در حلقه فید.
- [ ] **Step 4: اجرای تست و اطمینان از پاس شدن آن**
- [ ] **Step 5: کامیت تسک ۰**

---

### Task 1: پکیج `internal/watchlist` در Go (لایۀ Store و CRUD)

**Files:**
- Create: `backend-go/internal/watchlist/store.go`
- Create: `backend-go/internal/watchlist/store_test.go`

**Interfaces:**
- `New(db *sql.DB, dataDir string) *Store`
- `(s *Store) List(ctx context.Context) ([]Row, int, error)`
- `(s *Store) Add(ctx context.Context, symbol, name, note string) (*Row, int, int, bool, error)`
- `(s *Store) Remove(ctx context.Context, symbol string) (int, error)`

- [ ] **Step 1: پیاده‌سازی ساختار داده `Row` و اسکیما**
  تعریف مدل‌های منطبق با پاسخ‌های `watchlist_store.py`:
  `{"symbol": ..., "name": ..., "note": ..., "added_at": ..., "norm": ...}`
- [ ] **Step 2: نوشتن تست‌های جامع `store_test.go` روی DB موقت**
  تست افزودن نماد جدید، ویرایش یادداشت/نام نماد قبلی (`existed = true`)، اعتبارسنجی سقف ظرفیت، حذف با نوشتار عربی/فارسی و سورت بر اساس `added_at DESC`.
- [ ] **Step 3: پیاده‌سازی توابع CRUD در `store.go`**
  شامل `ON CONFLICT(symbol_norm) DO UPDATE`، خواندن سقف از کانفیگ، و نرمال‌سازی با `normFa`.
- [ ] **Step 4: اجرای تست‌ها و تایید پاس شدن ۱۰۰٪**
- [ ] **Step 5: کامیت تسک ۱**

---

### Task 2: پکیج `internal/notifications` در Go (طبقه‌بندی و فید)

**Files:**
- Create: `backend-go/internal/notifications/classify.go`
- Create: `backend-go/internal/notifications/classify_test.go`
- Create: `backend-go/internal/notifications/feed.go`
- Create: `backend-go/internal/notifications/feed_test.go`

**Interfaces:**
- `Classify(title, letterCode string) Classification`
- `(s *Service) Sources(ctx context.Context) (map[string]any, error)`
- `(s *Service) Feed(ctx context.Context, since string, levels []string, limit int, symbol string) (map[string]any, error)`

- [ ] **Step 1: پیاده‌سازی ماتریس عبارات منظم و طبقه‌بندی ۹گانه در `classify.go`**
  انطباق کامل با `_KINDS` و `LEVEL_*` در `notifications.py` (از جمله سطوح `high`, `medium`, `low`, `unclassified`).
- [ ] **Step 2: نوشتن تست‌های وکتور در `classify_test.go`**
  بررسی تطبیق عناوین گوناگون مجمع، افزایش سرمایه، صورت‌های مالی، تولید، هیئت مدیره و عناوین نشناخته.
- [ ] **Step 3: پیاده‌سازی کوئری‌های `Sources` و `Feed` در `feed.go`**
  استفاده از `pub_order_expr` و `pub_canon_sql` از پکیج `period`، الگوریتم ادغام تکراری‌ها (`symbol|norm_title|publish_date[:10]`) و فیلترهای `since`, `levels`, `symbol`.
- [ ] **Step 4: تست‌های واحد `feed_test.go` روی فیکسچر کدال**
- [ ] **Step 5: اجرای تست‌ها و تایید پاس شدن**
- [ ] **Step 6: کامیت تسک ۲**

---

### Task 3: هندلرهای HTTP و اتصال به `httpapi.Server`

**Files:**
- Create: `backend-go/internal/watchlist/handlers.go`
- Create: `backend-go/internal/watchlist/handlers_test.go`
- Create: `backend-go/internal/notifications/handlers.go`
- Create: `backend-go/internal/notifications/handlers_test.go`
- Modify: `backend-go/internal/httpapi/server.go`
- Modify: `backend-go/cmd/borsd/main.go`

**Interfaces:**
- اینترفیس `Watchlist` و `Notifications` در `httpapi`
- رجیستری روت‌ها در `httpapi.New`

- [ ] **Step 1: نوشتن هندلرهای `Watchlist`**
  پشتیبانی از `GET /api/watchlist`، `POST /api/watchlist` (با پارس بادی JSON)، `DELETE /api/watchlist/{symbol}`.
- [ ] **Step 2: نوشتن هندلرهای `Notifications`**
  پشتیبانی از `GET /api/notifications/sources` و `GET /api/notifications/feed`.
- [ ] **Step 3: ثبت روت‌ها در `httpapi/server.go` و سیم‌کشی در `borsd/main.go`**
  حفظ روت `/api/watchlist/matrix` روی ۵۰۱ `notPortedRoute` تا فاز B7.
- [ ] **Step 4: اجرای تست‌های روتینگ و هندلرها**
- [ ] **Step 5: کامیت تسک ۳**

---

### Task 4: پیاده‌سازی گیت برابری B5 و اعتبارسنجی B-G1 / B-G2

**Files:**
- Create: `tools/parity/cases_b5.json`
- Create: `tools/parity/gate_b5.py`

- [ ] **Step 1: تدوین سناریوهای تست در `cases_b5.json`**
  - خواندن واچ‌لیست و فید اعلان‌ها (حالت‌های گوناگون levels, since, limit, symbol).
  - تست‌های وضعیت اعلان‌ها و خطاهای ورودی.
- [ ] **Step 2: پیاده‌سازی گیت B5 شامل آزمون‌های رونویسی B-G2**
  - اجرای سناریوهای متوالی: افزودن نمادها، ویرایش، حذف، تست سقف.
  - مقایسه متناظر جداول `user_watchlists` در دیتابیس کپی موقت بین پایتون و Go ردیف‌به‌ردیف.
- [ ] **Step 3: اجرای زنده گیت `gate_b5.py` و اطمینان از خروج صفر (Exit 0)**
- [ ] **Step 4: اجرای تمام گاردهای رگرسیون پروژه**
- [ ] **Step 5: کامیت نهایی فاز B5 و به‌روزرسانی مستندات پیشرفت**
