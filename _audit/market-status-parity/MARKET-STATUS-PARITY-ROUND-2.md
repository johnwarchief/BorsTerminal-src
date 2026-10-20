# Market Status — گزارش دور ۲ (Source Parity)

**تاریخ:** ۲۰۲۶-۱۰-۲۰/۲۱ · **شاخه:** `mission/market-status-data-parity-qoder3-2026-10-20`
**شروع دور:** `3ad61a29` · **backup:** `backup/market-status-source-parity-pre-2026-10-20`
**`origin/main` شروع:** `a14375c1` · **push/merge:** در انتهای سند ثبت می‌شود.

---

## ۱) Git و حفاظت

- در شروع دور، ۱۱ commit محلی جلوتر از `origin/main` بود؛ همه بررسی و حفظ شدند.
- هیچ `reset --hard`، force push، squash یا بازنویسی تاریخچه انجام نشد.
- `main` محلی و remote دست‌نخورده ماندند تا مرحلهٔ ادغام.
- Inventory و گزارش دور ۱ حذف/بازنویسی نشدند؛ این سند ادامه‌ای است.

## ۲) Inventory

فایل: `_audit/market-status-parity/MARKET-STATUS-INVENTORY.csv`

- **۱۲۹ ردیفِ اتمی** (فیلد/سری/ستون/فیلتر)، ۹ بخش.
- توزیع: ۲۹ `MATCHED_SAMPLE`، ۴ `PARTIAL_NATIVE`، ۷ `PARTIAL_PUBLIC`، ۱۳ `INTERNAL_DERIVED`، ۳ `PRODUCT_ONLY`، ۱ `VERIFIED`، ۱ `BLOCKED_EXTERNALLY`، **۷۱ `UNVERIFIED`**.
- ردیف‌های `UNVERIFIED` حذف نشدند؛ هرکدام دلیل/گام بعدی دارند.

## ۳) یافته‌ها و اصلاحاتِ تأییدشده

### ۳-۱) کارت «قیمت وزنی ارزشی» = شاخص رسمی TSETMC

- خطای گزارش قبل: ۳٬۰۵۵٫۸۷ **تغییرِ** کارت Rahavard بود، نه مقدار.
- مقدار Rahavard: **۱٬۳۶۷٬۵۶۳٫۸۳**؛ همان `xDrNivJIdx004` شاخص رسمی
  «قیمت (وزنی-ارزشی)» با `insCode 5798407779416661`.
- Bors قبلاً `q_tot_cap/q_tot_tran` (۸٬۰۲۲٫۸۸ ریال) را زیر همان عنوان می‌گذاشت.
- اصلاح: `fetch_price_index` + `pi_last/pi_change/pi_pct` در `market_index`؛
  کارت سوم رسمی، میانگین ارزشی به کارت چهارم منتقل شد.
- نبودِ پاسخ: مقدار همان روز حفظ می‌شود؛ صفر/میانگین جایگزین نمی‌شود.
- TradersArena: کارت متناظر در سطح عمومی دیده نشد ⇒ `NOT_AVAILABLE`.

### ۳-۲) اثر رسمی بر شاخص

- `Index/GetInstEffect/0/1/500` برای نشست ۲۰۲۶-۱۰-۲۰ **۳۵۲ ردیف** داد.
- پنل‌های مثبت/منفی اکنون از `instEffectValue` رسمی با واحد **نقطهٔ شاخص**:
  - مثبت: فارس +۱۹٬۸۴۹٫۷۷، وبملت +۴٬۵۵۳٫۳۰، ومعادن +۲٬۳۶۱٫۲۶.
  - منفی: فملی −۲۳٬۳۶۴٫۰۴، فولاد −۵٬۳۴۳٫۹۰، شستا −۴٬۵۱۸٫۱۹.
- `reconciliation`: جمع ۱۹٬۱۴۶٫۵ در برابر تغییر رسمی ۱۸٬۴۴۶٫۱ → **۳٫۸٪ پسماند**
  (پوششِ ۳۵۲ نماد)؛ پنهان نشد.
- مسیر برآوردی قبلی فقط fallback با برچسب صریح است.

### ۳-۳) ارزش native حقیقی/حقوقی

- `GetClientTypeHistory` برای نشست بسته ۲۰۰ داد؛ خطای ۵۰۰ گذرا بود.
- backfill پنج‌نمادی روی کپی ایزوله: **۵/۵ native، ۰ خطا**.
- «خودرو» `value_source=native`؛ تجمیع ۱۵۰۰ نمادی `mixed` (صادقانه).
- قاعدهٔ provenance به `_value_source_of` استخراج و ۷/۷ تست شد.

### ۳-۴) طلا و حباب/ارزش ذاتی

- صفحهٔ عمومی طلا Rahavard: انس ۴٬۱۱۶ دلار (−۰٫۱۵٪) و درصد ۲۳ صندوق.
- «محاسبه‌گر ارزش ذاتی و حباب» صریحاً پشت اشتراک است
  («اشتراک خود را ارتقا دهید») ⇒ **BLOCKED_EXTERNALLY**؛ دور زده نشد.
- مقایسهٔ نمادبه‌نماد طلا هنوز انجام نشده (PARTIAL_PUBLIC).

### ۳-۵) TradersArena

- سطح عمومی: `/data/market0`، `/data/market/chart/totals0`،
  `/data/industries-csv`، `/data/mainwatch/symbols` (۲۰ نماد).
- شاخص‌های کل/هم‌وزن عمومی منطبق‌اند.
- `/homepage/<date>` (آمارهای کلیدی) به `/login` می‌رود؛ مالک حساب ندارد.
  این بخش **BLOCKED_EXTERNALLY** است و ادامهٔ کار به آن گره نخورد.
- شاخص قیمت وزنی، تفکیک مشتری و حباب طلا در سطح عمومی دیده نشد.

## ۴) معیارهای عددی (تا این نقطه)

| معیار | صورت | مخرج | وضعیت |
|---|---:|---:|---|
| فیلدهای inventory | ۱۲۹ ردیف | ۱۲۹ | ۵۸ ردیف resolved/partial، ۷۱ UNVERIFIED |
| شاخص‌های رسمی (TEDPIX/EW/قیمت) | ۳ | ۳ | مقادیر رسمی، MATCHED_SAMPLE |
| اثر رسمی شاخص | ۳۵۲ ردیف | ۳۵۲ | ذخیره و top-5 منطبق |
| اثر رسمی: تطبیق جمع با تغییر | ۱۹٬۱۴۶٫۵ | ۱۸٬۴۴۶٫۱ | ۳٫۸٪ پسماندِ مستند |
| native ارزش (نمونه) | ۵ | ۵ backfill | PASS_SAMPLE |
| native ارزش (universe) | ۵ | ۲٬۲۰۳ | ۰٫۲٪ — backfill کامل نشده |
| Rahavard price index | ۱٬۳۶۷٬۵۶۳٫۸۳ | همان | MATCHED_SAMPLE |
| TradersArena price index | — | — | NOT_AVAILABLE |

## ۵) تست‌ها و گیت

| مورد | نتیجه |
|---|---|
| `dev/market_price_index_card_v1.py` | ۱۳/۱۳ |
| `dev/mstat_value_source_semantics_v1.py` | ۷/۷ |
| `dev/market_impact_official_v1.py` | ۱۲/۱۲ |
| `dev/market_last_trade_semantics_v1.py` | ۱۱/۱۱ |
| `dev/mstat_industry_depth_semantics_v1.py` | ۸/۸ |
| Vitest هدفمند Market Status | ۳۸/۳۸ |
| `tsc -b` | rc=۰ |
| `npm run build` | rc=۰ (۴۷٫۷۷s) |
| گیت کامل backend | **NOT_COMPLETED_RUNTIME** — `confidence_engine_v973` (N+1 روی ۲۸۵MB) پس از >۲۰ دقیقه، و `fts_screener_card_parity_v10` (اسکن کل universe) پس از >۳۰ دقیقه تمام نشدند. اجرای بدون DB قبلاً ۱۹ FAIL محیطی داشت؛ ۳ سوئیت DB روی کپی ایزوله و ۷ سوئیت دیگر جداگانه PASS شدند. «سبزِ کامل» ادعا نمی‌شود. |
| QA بصری | ۱۹۲۰×۱۰۸۰، ۱۳۶۶×۱۰۸۰، ۱۲۸۰×۷۲۰: ۴ کارت شاخص، شاخص رسمی ۱٬۳۶۷٬۵۶۴، پنل‌های اثر رسمی با «نقطهٔ شاخص»، ۰ overflow، ۰ خطای کنسول |

### ۵-۱) شواهد بصری

- `_audit/market-status-parity/visual/status-1920x1080.png`
- `_audit/market-status-parity/visual/status-1366x1080.png`
- `_audit/market-status-parity/visual/status-1280x720.png`
- `_audit/market-status-parity/visual/impact-panels-1920x1080.png`

هر چهار تصویر از اجرای واقعی برنامه با DB ایزوله‌اند (نه fixture). در ۱۲۸۰
اجرای اول پیش از کامل‌شدن بارگذاری عکس گرفت و خالی بود؛ با انتظار ۱۵ ثانیه
بازاجرا شد و ۴ کارت/۰ خطا/۰ overflow ثبت شد.

## ۶) دیتابیس

- `market.db` عملیاتی در این worktree وجود ندارد.
- تمام backfillها/تست‌ها روی کپی ایزولهٔ `.q3-live-run/market.db` انجام شد.
- fingerprint اولیه: ۲۸۵٬۴۰۹٬۲۸۰ بایت.
- هیچ نوشتنی روی DB عملیاتی انجام نشد.

## ۷) موارد باز

1. backfill کامل native (۵ از ۲٬۲۰۳).
2. ۷۱ ردیف `UNVERIFIED` (طلا، سرانه/قدرت مرجع، سفارش‌های زنده، چارت مقایسه، ...).
3. حباب/ارزش ذاتی Rahavard: اشتراک.
4. آمارهای کلیدی TradersArena: پشت ورود؛ مالک حساب ندارد.
5. **انتخاب منبع سراسری/ویجتی و حالت مقایسه: پیاده نشده.** دلیل: تنها یک متریک
   (قیمت وزنی) دو نمایشِ قابل‌اثبات دارد؛ برای بقیه، تعریف مرجع یا داده عمومی
   وجود ندارد و ساختِ selector با یک گزینهٔ فعال، ظاهرسازی می‌شد. این مورد
   صریحاً باز است و در ادعای ۱۰۰٪ حساب نمی‌شود.
6. گیت کامل و QA بصری ۱۹۲۰/۱۳۶۶/۱۲۸۰: در حال تکمیل.

## ۸) وضعیت نهایی این دور

**PARTIAL / BLOCKED_EXTERNALLY — نه ۱۰۰٪.**
سه شکاف واقعی (قیمت وزنی، اثر شاخص، native sample) بسته شد و شواهد مستقل دارند؛
اما پوشش کامل فیلدها، native universe و دو سطح اشتراکی/ورودی مرجع هنوز باز است.
هیچ ادعای ۱۰۰٪ و هیچ نتیجهٔ merge/push پیش از اجرای واقعی در این سند ثبت نمی‌شود.
