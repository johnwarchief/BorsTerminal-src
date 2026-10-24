# Round 8 — تشخیص اتصال EasyTrader و بازطراحی UX سرخطی

شاخه: `mission/sarkhati-round8-connection-ux-2026-10-20`
پایه: `acc5a74dc5bd5dcd5bf1af5cec4010f8968ce92f` (Round 7)
وضعیت: **`live_ready=false`**؛ هیچ سفارش واقعی، هیچ POST سفارش به کارگزاری و
هیچ release/tag انجام نشد. `main` و نسخهٔ `1.0.95` دست‌نخورده‌اند.

## A. تشخیص اتصال

### یافته‌های واقعی

| # | یافته | شاهد/مسیر | اثر |
| --- | --- | --- | --- |
| ۱ | اپ پیش‌فرض روی آداپتور `mock` می‌ماند | اجرای کامل Portable: `/api/execution/status` → `adapter=mock` و `traffic=blocked`؛ تنظیم آداپتور فقط با ذخیره + restart مؤثر می‌شود (`SarkhatiConnectionSettings`، `api/execution.py`) | کاربر «اتصال» را نمی‌بیند، هرچند Backend پاسخ می‌دهد |
| ۲ | مسیر «باز کردن پنجره»‌ی قدیمی یک پروفایل موقت جدا باز می‌کرد، نه browser host پایدار | `execution_connect.open_login_window` / `execution_connect.py:285`؛ `ConnectBrokerRow` | ورود مالک در یک context بود و runtime بعدی به همان context/CDP دسترسی نداشت؛ نشست API در backend نمی‌نشست |
| ۳ | `verify` قدیمی پیش از «نبودِ نشست»، `adapter.live` (ترافیک + token) را می‌سنجید | `execution_connect.py:386` | با ترافیک روشن و token غایب، پیام «ترافیک خاموش» می‌داد، نه «نشست نیست»؛ تشخیص گمراه‌کننده |
| ۴ | بازبودن صفحه/پنجره با نشست احرازشده یکی گرفته می‌شد | `SarkhatiConnectionCard` قدیمی؛ `execution_connect.verify` | خطر ادعای متصل‌بودن بدون پاسخ واقعی کارگزاری |
| ۵ | قرارداد write هنوز `WIRE_HYPOTHESIS=True` است | `/api/execution/status` → `wire_hypothesis=true` | هیچ CONNECTED کامل/ارسال مجاز نیست |
| ۶ | منبع حساب/پرتفوی و قدرت خرید وجود ندارد | `/api/execution/portfolio` → `no_source`؛ `capabilities.balances=false` | Preflight زنده و تخصیص بودجهٔ واقعی مسدود |
| ۷ | پنل اتصال قدیمی URLها، نقش میزبان‌ها، فرم نشست و تنظیمات را هم‌زمان نشان می‌داد | `SarkhatiConnectionCard` پیش از این تغییر | کاربر نمی‌دانست آخرین مرحلهٔ موفق کدام است |

### اصلاحات انجام‌شده

- `execution_connection.py`: state machine ده‌مرحله‌ای مستقل:
  Backend → host → CDP → صفحه → ورود → نشست API → قرارداد → read-only →
  حساب/پرتفوی → قابلیت‌ها. هر مرحله `PASS/FAIL/BLOCKED/UNVERIFIED/NOT_RUN`،
  شاهد، دلیل، اقدام و زمان دارد.
- صفحه‌ها فقط از `/json/list` محلی (`url/title/host`) خوانده می‌شوند؛ هیچ
  token/cookie/input/حساب خوانده نمی‌شود.
- APIهای جدید: `GET /api/execution/connection/diagnose`،
  `POST /connection/verify`، `GET /connection/report`.
- `verify` قدیمی اکنون ابتدا `transport.is_live` را می‌سنجد و بعد `has_token`؛
  «ترافیک خاموش» و «نشست غایب» دو پیام جدا شدند.
- تشخیص، پیام صریح «مرورگر آماده است؛ اتصال API کارگزاری هنوز تأیید نشده است»
  را برای صفحهٔ UI باز و قرارداد تأییدنشده برمی‌گرداند؛ هرگز آن را CONNECTED
  نمی‌خواند.
- تست: `dev/execution_connection_v1142.py` (۲۱ بررسی) و
  `frontend/src/__tests__/sarkhati-connection-guide.spec.tsx` (۶ تست).

### آنچه هنوز اثبات نشده

- ورود مالک و نشست API واقعی: ورود دستی انجام نشد؛ `LOGIN_REQUIRED` ماند.
- قرارداد write و پذیرش سفارش: `UNVERIFIED`؛ هیچ POST ثبت سفارش انجام نشد.
- منبع حساب/پرتفوی و قدرت خرید: `BLOCKED_EXTERNALLY`.
- آداپتور در اپ تست `mock` بود؛ تغییر به `easytrader` نیازمند ذخیرهٔ تنظیم و
  restart است و پس از آن هم بدون نشست، اتصال کامل نیست.

## B. UX جدید

### معماری اطلاعات

مسیر اصلی: **اتصال ← نماد ← آماده‌سازی/بررسی سفارش ← نتیجه و پیگیری**.
ابزارهای حرفه‌ای (زمان‌بندی، ریسک، آمادگی/پایش، عرضه/بودجه، Timeline و
گزارش) از مسیر اصلی جدا مانده‌اند.

### اتصال

- یک پیام وضعیت کلی و یک اقدام بعدی در بالای پنل.
- شش قدم اصلی با شماره، وضعیت، شاهد، دلیل و اقدام؛ مراحل API/حساب در
  جزئیات بازشونده.
- دکمه‌های واقعی: «باز کردن پنجرهٔ اتصال» (browser host)، «بررسی وضعیت»،
  «بستن host»، «گزارش تشخیصی».
- پیام‌های `LOGIN_REQUIRED`، `HOST_DOWN`، `CDP_DOWN`، `PAGE_MISSING` و
  `BROWSER_READY_API_UNVERIFIED` جدا و قابل‌فهم.
- URLها، نقش میزبان‌ها، تنظیم آداپتور و فرم نشست قدیمی به «جزئیات فنی» منتقل
  شدند؛ قابلیت حفظ شد، ولی مسیر اصلی شلوغ نیست.
- هیچ توکن/کوکی در سطح اصلی نمایش داده نمی‌شود.

### نماد

- منبع «تابلو همین نشست»، زمان دریافت، و وضعیت `UNVERIFIED`/زنده/آخرین داده
  کنار نام و شناسهٔ نماد.
- جست‌وجو و انتخاب نماد همچنان از فید معتبر انجام می‌شود؛ دادهٔ ساختگی جای
  دادهٔ زنده نمی‌نشیند.

### سفارش و پیگیری

- فرم خرید/فروش، قیمت، تعداد، ارزش و خلاصهٔ پیش از ارسال حفظ شد.
- تفکیک Mock/Dry-run/Live در همان فرم دیده می‌شود؛ هیچ ارسال زنده‌ای از
  این صفحه انجام نشد.
- پیگیری یک خلاصهٔ «نامعلوم/تأییدشده/UNKNOWN_HOLD» دارد و صریح می‌گوید
  HTTP 200 پذیرش نیست.

## C. وضعیت اتصال (آخرین مرحلهٔ اثبات‌شده)

در اجرای کامل Round 8:

- Backend: `PASS`؛ نسخه `1.0.95`، آداپتور `mock`.
- Browser host: با دکمهٔ برنامه باز شد؛ `PASS`.
- CDP: `PASS` (یک صفحه).
- صفحه: `login.emofid.com` با عنوان «ورود - کارگزاری مفید»؛ `PASS` از نظر
  وجود صفحهٔ مجاز، ولی ورود `BLOCKED`.
- نشست API: `BLOCKED`؛ چون آداپتور mock/بدون نشست است.
- قرارداد API: `UNVERIFIED`؛ `WIRE_HYPOTHESIS=true`.
- حساب/پرتفوی: `BLOCKED`؛ منبع معتبر نیست.
- نتیجهٔ کلی: **`LOGIN_REQUIRED` / `BROWSER_READY_API_UNVERIFIED`**، نه
  `CONNECTED`.

سه چیز جدا: بازبودن پنجره، ورود کاربر، تأیید API. فقط مورد سوم می‌تواند
اتصال کامل باشد و در این دور به‌دست نیامد.

## D. تست‌ها

| آزمون | نتیجه |
| --- | --- |
| `dev/execution_connection_v1142.py` | **23/23** |
| Connection UI tests | **31/31** در فایل‌های اتصال (۶ تست جدید) |
| Backend کامل | **141 suite شمارش‌شده + 27 خاموش + 2 skip؛ 5160/5160 بررسی؛ ALL SUITES PASSED** |
| Vitest کامل | **199 فایل موفق / 2 اسکیپ؛ 2077 تست موفق / 5 اسکیپ** |
| TypeScript | **0 خطا** (`npx tsc -b`) |
| Frozen/onedir | **230.5 MB**؛ build exit 0؛ `onedir_contract PASS`؛ API smoke: 10 مرحله، `HOST_DOWN`، cockpit `PASS`؛ daemon `--once` exit 0 |

## E. QA تصویری

شواهد کامل: [`_audit/round8/visual/index.md`](../../_audit/round8/visual/index.md)

- ۱۵ تصویر از اپ کامل Portable؛ viewportهای 1366×768، 1920×1080 و 1280×720.
- host خاموش/ورود دستی: واقعی؛ `03`/`04` با fixture صریحاً `simulated`.
- نماد/سفارش/پیگیری: اپ واقعی با فید fixture برچسب‌دار «فولاد».
- Cockpit/عرضه/Timeline: اپ واقعی با fixture عرضه.
- تصویر API تأییدشده ساخته نشد؛ چون شاهد واقعی وجود ندارد.
- قبل/بعد: برای صفحهٔ اتصال تصویر قبلِ معتبر نبود و جعل نشد؛ برای پایش،
  تصویر Round 7 با Round 8 قابل مقایسه است.
- داوری زیبایی‌شناختی نهایی مالک: **UNVERIFIED**.

## F. تست مالک

```bash
cd C:\Users\PCMOD\Desktop\_bors-sarkhati-minfix
.venv\Scripts\python.exe scripts\build_all.py
dist\BorsTerminal_Ultimate\BorsTerminal_Ultimate.exe
```

1. «سرخطی» ← «اتصال».
2. اگر آداپتور `mock` است، «جزئیات فنی» ← تنظیم آداپتور، `EasyTrader` و
   «فقط‌خواندنی» را ذخیره کنید و برنامه را یک‌بار ببندید/باز کنید.
3. «باز کردن پنجرهٔ اتصال» را بزنید.
4. خودتان در همان پنجره وارد EasyTrader شوید؛ رمز/CAPTCHA/MFA را با برنامه
   به اشتراک نگذارید.
5. «بررسی وضعیت» را بزنید. انتظار:
   - اگر ورود نشده‌اید: `LOGIN_REQUIRED`.
   - اگر صفحه باز است ولی API تأیید نشده: «مرورگر آماده است؛ API تأیید نشده».
   - اگر نشست read-only تأیید شود، مرحله‌های بعدی جدا نمایش داده می‌شوند.
6. «گزارش تشخیصی» را بگیرید؛ باید بدون token/cookie باشد.
7. هیچ سفارش واقعی ارسال نکنید؛ `live_ready=false` است.

اگر خطا دیدید، نام مرحلهٔ قرمز، شاهد آن و گزارش JSON را بفرستید؛ پیام کلی
«اتصال برقرار نشد» کافی نیست.

## G. GitHub

- شاخه: `mission/sarkhati-round8-connection-ux-2026-10-20`
- کامیت کد/تست: `fd5456e1`
- گزارش: https://github.com/johnwarchief/BorsTerminal-src/blob/mission/sarkhati-round8-connection-ux-2026-10-20/docs/SARKHATI-ROUND8-CONNECTION-UX-2026-10-20.md
- شواهد بصری: https://github.com/johnwarchief/BorsTerminal-src/blob/mission/sarkhati-round8-connection-ux-2026-10-20/_audit/round8/visual/index.md
- تصویر اتصال (ورود دستی): https://raw.githubusercontent.com/johnwarchief/BorsTerminal-src/mission/sarkhati-round8-connection-ux-2026-10-20/_audit/round8/visual/02-connection-login-required-1366.png
- فقط همین شاخه push می‌شود؛ `main`، tag و release دست‌نخورده‌اند.

## H. موانع نهایی

- ورود دستی مالک و نشست API واقعی: بدون این، مرحله ۶ و بالاتر مسدود است.
- آداپتور واقعی `easytrader` + read-only و restart.
- قرارداد write/پاسخ واقعی کارگزاری: `UNVERIFIED`.
- منبع حساب/پرتفوی و قدرت خرید.
- پذیرش، جایگاه صف و زمان واقعی پذیرش.
- داوری بصری نهایی مالک.

هیچ ادعای اتصال کامل، پذیرش سفارش، سود، تخصیص یا اول‌شدن در صف مطرح نیست.
