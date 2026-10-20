# زمان‌بندی ماندگار سرخطی داروند — ۲۰۲۶-۱۰-۲۰

شاخه: `mission/multi-strategy-2026-10-20`
مبنا: `55e8ce79`
وضعیت: ذخیره/زمان‌بندی/اجرای dry-run **پیاده و اثبات‌شده**؛ ارسال زنده **عمداً وصل نشده** و اثبات نشده است.

## ۱) دامنه

این مرحله یک لایهٔ زمان‌بندیِ ماندگار برای سفارشِ آماده‌شده ساخت تا سفارشِ داروند
شب ذخیره شود و در زمان مقرر، بدون Qoder و بدون وابستگی به پنجرهٔ UI، بررسی و
اجرا شود. اجرای واقعیِ سفارش در این مرحله انجام نمی‌شود.

## ۲) معماری

### ذخیره‌سازی
- `execution_schedule.py` — SQLite جدا: `execution_schedules.db` در `WORK_DIR`؛
  **نه** `market.db` و **نه** `user.db`.
- WAL + `synchronous=FULL` + `BEGIN IMMEDIATE`؛ هر تغییرِ وضعیت با `UPDATE ... WHERE state=...`
  و بررسیِ `rowcount` انجام می‌شود.
- هر رکورد: شناسه، `execution_id` یکتا، نماد/ISIN/نام، سمت، قیمت، تعداد، نوع/اعتبار،
  `target_ms` + `target_local` + `Asia/Tehran`، وضعیت، نسخهٔ تنظیمات، زمان‌ها،
  `claim_token`، آخرین اعتبارسنجی و نتیجه.
- کلیدِ dedupe در دقتِ دقیقه (`symbol|side|minute|mode`) و ایندکسِ یکتای جزئی روی
  وضعیت‌های فعالِ خطرناک؛ UNKNOWN و ACKNOWLEDGED هم کلید را قفل نگه می‌دارند.

### ماشین وضعیت
`PREPARED → ARMED → RUNNING → (SUBMITTING) → ACKNOWLEDGED/REJECTED/UNKNOWN/DRY_RUN`
و حالت‌های `CANCELLED`، `EXPIRED`، `MISSED_TARGET`، `NEEDS_REVIEW`.

- claim فقط از `ARMED` و با شرطِ `target_ms<=now`؛ دو claim هم‌زمان: یکی برنده.
- submit فقط با `claim_token` همان اجرا؛ ارسال دوم ممکن نیست.
- UNKNOWN ترمینال است؛ نه claim دوباره، نه ساختِ سفارشِ هم‌کلید.
- `cancel` فقط `PREPARED/ARMED`؛ پس از claim رد می‌شود.
- `recover` پس از restart: `PREPARED/ARMED/RUNNING/SUBMITTING → NEEDS_REVIEW`؛
  هیچ چیز خودکار اجرا نمی‌شود. ARMEDِ دیرشده `MISSED_TARGET` می‌شود.
- `halt` زمان‌بندی‌های ARMED را `NEEDS_REVIEW` می‌کند و runner پیش/پس از claim
  توقف را می‌سنجد.

### زمان‌بند
- `ScheduleRunner` برای dry-run: بدون شبکه/مرورگر؛ فقط زمان‌بندی، claim،
  اعتبارسنجی و ثبت نتیجه.
- دیرکرد بیش از سقف → `MISSED_TARGET`؛ اجرای فوریِ جبرانی وجود ندارد.
- اجرای live در runner فقط با `live_enabled`، `contract_verified`، اعتبارسنجی کامل،
  ساعتِ معتبر و تقویمِ باز ممکن است؛ هیچ‌کدام در محصول فعال نیست.
- `execution_daemon.py` + `BorsTerminal_Ultimate.exe --schedule-daemon` — اجرای
  محلی بدون UI و بدون Qoder؛ فقط dry-run.

### اعتبارسنجی داروند
- `validate_darvand` با شکستِ بسته: هویت مستقل (نماد/ISIN/نام در `market.db`)،
  هدر فرم، بازشدن مجدد فرم، دامنهٔ قیمت، گام، سقف تعداد، قدرت خرید، کارمزد،
  نشست، تقویم و تازگی داده.
- static checks در Mock/Frozen سبز؛ کنترل‌های زنده (فرم/دامنه/نشست/موجودی/تقویم)
  در محصولِ امروز `UNKNOWN` هستند و live را مسدود می‌کنند.
- هویت محلی داروند: `IRO1DRVN0001` / «زیست اروند فارمد» (مقایسه با نرمال‌سازی
  عربی/فارسی).

### فرم
- `open_form_selector` و `form_symbol_selector` به Strategy اضافه شد: پس از
  navigation، فرم برای نماد فعال دوباره باز می‌شود و هدرش با قصد مقایسه می‌شود.
- Mock `open_form` کلیکِ بازکردن را از کلیکِ ارسال جدا می‌کند؛ تست‌ها:
  یک بار بازشدن، تطبیق هدر، و `SYMBOL_MISMATCH` در هدر ناهماهنگ.

### API و رابط
- `/api/execution/schedules` (GET/POST)، `/{id}/arm`، `/{id}/cancel`، `/{id}/reset`،
  `/{id}`، `/readiness`، `/instrument?symbol=`.
- کارت «زمان‌بندیِ ماندگار (dry-run)» در تب سرخطی: ذخیره، مسلح‌کردن، لغو، بازبینی،
  وضعیت و موانعِ live. قیمت/تعداد پیش‌فرض ندارد؛ ISIN از دادهٔ محلی استعلام می‌شود.
- توقف اضطراری همان halt موجود است و زمان‌بندی‌های ماندگار را هم متوقف می‌کند.

## ۳) شواهد و تست‌ها

| مورد | نتیجه |
| --- | --- |
| `dev/execution_schedule_v1130.py` | **45/45** |
| `dev/strategy_guard_v1123.py` | **50/50** (شاملِ ۳ تستِ بازکردن فرم/هدر) |
| `dev/run_all_tests.py` | **138 شمارش‌دار + 27 silent + 2 skip = 167**؛ 4967/4967 check؛ `ALL SUITES PASSED`؛ exit 0 |
| Vitest | 197/199 فایل، 2065/2070 تست، 5 skip؛ exit 0 |
| `npx tsc -b` | صفر خطا |
| Frozen build | exit 0؛ **230.3 MB**؛ `onedir_contract --dist` **PASS** |
| Frozen smoke | create/arm موفق؛ حالت نهایی **DRY_RUN**؛ رویدادها `created,validation,armed,claimed,finished`؛ خروج native **0**؛ بدون فرزند |
| Frozen daemon | `--schedule-daemon --once` → exit 0؛ تنها dry-run؛ بدون پنجره/فرایند باقی‌مانده |

سناریوهای گارد: ذخیره/بازیابی، claim هم‌زمان، dispatch تکراری، اعتبارسنجی نماد/ISIN/نام،
قیمت/تعداد، UNKNOWN، timeout/restart، MISSED_TARGET، cancel، halt، تقویمِ بسته/نامعلوم،
ساعت نامعتبر، live gate، dedupe و reset.

## ۴) آنچه اثبات نشد / مسدود

1. **ارسال زنده** — هیچ POSTِ ثبت و هیچ پاسخِ کارگزاری مشاهده نشد؛ `WIRE_HYPOTHESIS=True`.
2. **نشستِ پایدار** — EasyTrader توکن را در `sessionStorage` نگه می‌دارد؛
   بستن/restart نشست را از بین می‌برد و هیچ session providerِ مجاز وصل نیست.
3. **قدرت خرید** — منبع معتبر در دسترس نیست؛ validator live را مسدود می‌کند.
4. **دامنه/گام/سقف زنده** — فقط از فرمِ واقعی همان لحظه، که به نشست زنده وابسته است.
5. **تقویم آینده** — فقط تاریخ‌های `price_history` محلی باز شناخته می‌شوند؛ آینده
   `UNKNOWN` است و runner live را متوقف می‌کند.
6. **selector پایدار هدر فرم** — هدر در UI شناسهٔ پایدار ندارد؛ `form_symbol_selector`
   باید از شواهد همان صفحه پیکربندی و تست شود.
7. **بازیابی پس از restart** — رکوردها می‌مانند ولی به `NEEDS_REVIEW` می‌روند؛
   اجرای خودکارِ بعد از restart عمداً وجود ندارد (قاعدهٔ ایمنی).
8. **صف/اول‌شدن** — هیچ تضمینی نیست.

## ۵) مقادیر لازم از مالک

- قیمت نهایی (ریال) و تعداد نهایی (سهم) — فردا و داخل دامنهٔ همان لحظه.
- تأیید سمت (خرید)، نوع (عادی) و اعتبار (روز).
- تأیید قدرت خرید/موجودی و وضعیت نشست پیش از اجرای زنده.
- تصمیم دربارهٔ session provider/ورود دستی و مجوز یک تست زندهٔ تحت نظارت.

## ۶) بازتولید

```bash
python dev/execution_schedule_v1130.py
python dev/strategy_guard_v1123.py
PYTHONIOENCODING=utf-8 python -u dev/run_all_tests.py
cd frontend && npx --no-install vitest run --maxWorkers=2 && npx --no-install tsc -b
.venv/Scripts/python.exe scripts/build_all.py
.venv/Scripts/python.exe dev/onedir_contract_v11.py --dist dist
python execution_daemon.py --once --db <temp>/schedule.db
BorsTerminal_Ultimate.exe --schedule-daemon --once --db <temp>/schedule.db
```
