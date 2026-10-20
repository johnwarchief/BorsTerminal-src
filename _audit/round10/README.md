# Round 10 — منابعِ حسابِ EasyTrader و انتخابِ سرخطی

این پرونده شواهدِ فشردهٔ Round 10 است. داده‌هایِ خامِ حساب اینجا نیستند؛ فقط
شمارش، وضعیت و فهرستِ مسیرها. تصویرهایِ `visual/` یا از دادهٔ خامِ واقعی با
مقدارِ مالیِ ماسک‌شده‌اند یا fixtureِ صریحاً با برچسبِ «دادهٔ آزمایشی».

## مبنا و دامنه

- مبنا: `mission/sarkhati-round9-interactive-debug-2026-10-20` @
  `2b2448b3d0d8e4fe8215981e7dafa577884324a3`
- شاخهٔ کار: `mission/sarkhati-round10-watchlist-portfolio-2026-10-21`
- تغییر در `main`، تگ یا انتشار: هیچ.

## سه منبعِ مستقل (فقط‌خواندنی)

| منبع | مسیرِ مشاهده‌شده در وب‌اپِ رسمی | شاهد | وضعیت |
| --- | --- | --- | --- |
| دیده‌بانِ شخصی | `GET /easy/api/MarketWatch` | پاسخ ۲۰۰ JSON در نشستِ ۲۰۲۶-۱۰-۲۱ | `WATCHLIST_VERIFIED` |
| پرتفوی/عملکرد | `GET /assetmodule/api/performance` | پاسخ ۲۰۰ JSON، `items[]` | `PORTFOLIO_VERIFIED` / `PORTFOLIO_PARTIALLY_VERIFIED` |
| قدرت خرید/مانده | `GET /easy/api/money` | پاسخ ۲۰۰ JSON؛ فرمول از خودِ وب‌اپ | `BUYING_POWER_VERIFIED` |

منشأ: `first-party-web-app (observed 2026-10-21)`. هیچ مسیری حدس زده نشد و
هیچ‌کدام مجوزِ نوشتن نیست. `order_write_state` همچنان
`ORDER_WRITE_UNVERIFIED` است.

### شمارشِ سنجشِ زنده

| سنجه | دیده‌بان | پرتفوی |
| --- | ---: | ---: |
| ردیفِ خام | ۲۹ | ۱۱ |
| ISINِ یکتا | ۲۸ | ۱۱ |
| تکراری | ۱ | ۰ |
| نگاشت‌نشده | ۰ | ۰ |
| مبهم | ۰ | ۰ |

هم‌پوشانیِ نمادی دو منبع: ۳؛ اجتماع: ۳۶ نماد.

### قدرت خرید

- فرمولِ وب‌اپ: `buyPowerT2 - credit - avandCredit`
- واحد: ریال (`IRR`)، با مقایسهٔ مقدارِ API و «قدرت خرید»ِ نمایش‌داده‌شده
  (نسبت ۱) و علامتِ ریال در همان صفحه.
- واحدِ `asset`/`totalBuyAveragePrice` پرتفوی مستقل تأیید نشد؛ رابط آن‌ها را
  «عدد خام» و بدونِ ادعای ریال نشان می‌دهد.

## وضعیت‌هایِ API

`WATCHLIST_VERIFIED`، `WATCHLIST_UNAVAILABLE`، `PORTFOLIO_VERIFIED`،
`PORTFOLIO_PARTIALLY_VERIFIED`، `PORTFOLIO_UNAVAILABLE`،
`BUYING_POWER_VERIFIED`، `BUYING_POWER_UNAVAILABLE`،
`ACCOUNT_SOURCE_BLOCKED`، `ORDER_WRITE_UNVERIFIED`.

خطایِ هر منبع مستقل است: شکستِ دیده‌بان پرتفوی را متوقف نمی‌کند و برعکس.

## پیش‌فرود

- خرید: فقط با `buying_power` (یا `cash` در نبودش) و به‌صورتِ blocking.
- فروش: فقط با `get_sellable_quantity`؛ منبعِ فعلی این عدد را نمی‌دهد، پس
  همهٔ فروش‌هایِ واقعی `UNKNOWN` و مسدود می‌مانند. `PaperBroker` عددِ آزاد را
  از حسابِ شبیه‌سازیِ خودش می‌دهد و مسیرِ فروشِ paper را زنده نگه می‌دارد.
- هر خطایِ خواندن یا مقدارِ غیرعددی ⇒ `UNKNOWN` مسدود، نه ۵۰۰ و نه PASS.

## امنیت

- بدنهٔ سه منبع در `redacted_log` نمی‌نشیند (`log_body=False`).
- `Authorization` از مسیرِ `redact()` می‌گذرد؛ توکن در پاسخ‌های API نیست.
- هیچ `POST` سفارش، لغو یا تغییرِ دیده‌بان/پرتفوی اجرا نشد.
- فهرستِ ذخیره‌شدهٔ سرخطی فقط نماد/ISIN/منبع/هدف/اولویت/بودجهٔ خودِ کاربر و
  زمان‌هایِ منابع را در پروفایلِ محلی نگه می‌دارد؛ قدرت خرید، توکن یا ردیفِ
  خامِ حساب در آن نیست.

## آزمون‌ها

| آزمون | نتیجه |
| --- | --- |
| `dev/run_all_tests.py` | ۱۴۲ سوئیتِ شمرده، ۲۷ فقط-exit-code، ۲ SKIPِ fixture، ۰ FAIL |
| `npx vitest run` | ۲۰۸۹ passed، ۵ skipped، ۰ failed (۲۰۹۴؛ ۲۰۰ فایل) |
| `npx tsc -b` | صفر خطا |
| `npm run build` | موفق |
| `dev/execution_account_sources_v1146.py` | ۲۴/۲۴ |
| `dev/p0_gates_v1118.py` | ۳۳/۳۳ |
| `dev/sarkhati_protocol_v1119.py` | ۴۷/۴۷ |
| `dev/broker_connect_v1120.py` | ۳۸/۳۸ |
| `dev/bot_paper_v1109.py` | ۵۴/۵۴ |

## شواهدِ دیداری

تصویرها از خودِ برنامهٔ منجمد (WebView2، پروفایلِ محلی) گرفته شده‌اند. مقدارِ
قدرت خرید و عددهایِ سفارشِ واقعی با ماسکِ تصویری پوشانده شده‌اند؛ ردیف‌هایِ
شخصیِ دیده‌بان در تصویرِ تمام‌صفحه ماسک شده‌اند. تصویرهایِ fixture با نوارِ
«دادهٔ آزمایشی — فقط برای تصویر» برچسب خورده‌اند.

| فایل | چیست |
| --- | --- |
| `visual/01-sources-live-summary.png` | خلاصهٔ زنده: ۲۸ نمادِ دیده‌بان، ۱۱ دارایی، قدرت خریدِ ماسک‌شده |
| `visual/01b-sarkhati-live-page.png` | همان صفحه با ردیف‌هایِ دیده‌بانِ ماسک‌شده |
| `visual/02-watchlist-fixture.png` | دیده‌بانِ آزمایشی، دو نماد و تکراری/نگاشت‌نشده |
| `visual/03-portfolio-fixture.png` | پرتفویِ آزمایشی، نمادِ مشترک با دیده‌بان |
| `visual/04-multiselect-fixture.png` | انتخابِ سه‌نمادی از دو منبع |
| `visual/05-goals-priority-fixture.png` | هدفِ خرید/فروش/نامشخص و جابه‌جاییِ اولویت |
| `visual/06-buying-power-fixture.png` | جزئیاتِ خامِ قدرت خرید (آزمایشی) |
| `visual/07-review-saved-fixture.png` | ذخیرهٔ فهرست و زمانِ ذخیره |
| `visual/08-source-error-simulated.png` | شکستِ مستقلِ دیده‌بان: پیامِ خطا، بدونِ دادهٔ کهنه |
| `visual/08b-empty-fixture.png` | دیده‌بان/پرتفویِ خالی با شمارشِ صفرِ صادق |
| `visual/09-preflight-real-values-masked.png` | پیش‌فرودِ واقعی: ۷ سبز، ۱ رد، ۲ نامعلوم — «مسدود» |

پیش‌فرودِ فروش در همان مسیر با `sellable=UNKNOWN` مسدود می‌شود (سنجهٔ
`dev/execution_account_sources_v1146.py`)؛ چون منبعِ تعدادِ آزاد وجود ندارد،
تصویرِ جداگانه‌ای از «فروشِ آماده» ساخته نشد.

