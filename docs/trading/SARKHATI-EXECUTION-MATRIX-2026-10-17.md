# ماتریس اجراییِ سرخطی — از پنج مرجع عمومی به یک سامانه

تاریخ: ۲۰۲۶-۱۰-۱۷ · branch: `mission/sarkhati-connect-flow-2026-10-17` · base: `github/main` = `c0402614` (v1.0.89)

مبنا: `EASYTRADER-OSS-RESEARCH-MATRIX.md` (ممیزیِ پنج مخزن، کارِ System 2) دوباره از صفر
ننوشته نشده است. این سند فقط یک چیز را اضافه می‌کند: **برای هر قابلیت، حالا در کدِ ما
چه خبر است.** شاهدِ هر ردیف یا `path:line` است یا «نیست».

| # | قابلیت (منبع در ماتریس مرجع) | وضعیت | شاهد / علت |
| --- | --- | --- | --- |
| ۱ | نشانه‌گذاریِ نشست: `authorization`/`cookie` صفحه‌اختیاری کاربر | **PARTIAL** | `execution_easytrader.py:686-697` نشانی را به `Authorization` می‌گذارد (نرمال‌سازی `Bearer`)؛ ولی **منبعِ نشانی** هنوز «کاربر خودش در API می‌خواند و اینجا می‌چسباند» است. تحویلِ خودکارِ نشست از پنجرۀ مرورگر: **REJECTED WITH REASON** تا پروتکلِ واقعی مشاهده نشود (§۶) |
| ۲ | بازِ کردنِ پنجرۀ ورودِ کاربر در دامنهٔ واقعی | **IMPLEMENTED** | `execution_connect.py:open_login_window` + `POST /api/execution/connect/browser`؛ پروفایلِ موقت، بدونِ هیچ ورودِ خودکار؛ `dev/sarkhati_connect_v1117.py` E1–E3 |
| ۳ | حالتِ صریحِ نشست (CONNECTED / DISCONNECTED / EXPIRED / UNKNOWN) | **IMPLEMENTED** | `execution_connect.py:verify`؛ ۴۰۱⇒EXPIRED، احرازِ ناموفق⇒EXPIRED، timeout/شبکه⇒UNKNOWN، بی‌ترافیکِ مجاز⇒UNKNOWN+`blocked_reason`. F1–F6، و **G1**: پنجرۀ باز به‌تنهایی «متصل» نیست |
| ۴ | بررسیِ اتصال / قطعِ اتصال / مشاهدهٔ وضعیت در رابط | **IMPLEMENTED** | `ConnectBrokerRow.tsx` (چیپِ حالت + سه کنش + جزئیات درِ `<details>`) روی `ExecutionPanel`؛ `connect-broker-row.spec.tsx` ۴ سنجه |
| ۵ | محدودیتِ دامنه + ردِّ پاسخِ HTML به‌عنوانِ «اتصال موفق» | **IMPLEMENTED** | `validate_url` (فقط https + میزبانِ مجاز)؛ `login_hosts()` عمداً از `allowed_hosts()` جداست و بی‌`BORS_EXECUTION_CONNECT_HOSTS` خروج `NO_LOGIN_HOST` است (E1–E2) |
| ۶ | عدمِ ذخیرهٔ رمز/کوکی/توکن روی دیسک | **IMPLEMENTED** | توکن فقط درِ حافظه (`api/execution.py:post_session`)؛ پروفایلِ مرورگر هنگام بستن پاک می‌شود (`close_login_window`)؛ H1–H4: نه در پاسخ، نه در وضعیتِ پنجره |
| ۷ | حلِ ISIN/شناسه پیش ازِ هر چیز؛ بی‌نگاشتِ مبهم | **IMPLEMENTED** | `_resolve_instrument` از `instruments` می‌خواند؛ بی‌ISIN ⇒ `NOT_ORDERABLE`. I2 (`resolution=exact`) و I10 |
| ۸ | کنترلِ قیمت/حجم/محدودیت/تازگی (preflight) | **IMPLEMENTED** | `/api/execution/preflight` + `checks` در پاسخ؛ I2–I3 |
| ۹ | زمان‌بندی + منبعِ ساعت + خطایِ زمان‌بندی دیدنی | **PARTIAL** | `schedule/{id}`، `timings` در پاسخِ dispatch، و `execution_timing` درِ مرجعِ مخزن؛ **کالیبراسیون RTT/HEAD** (مرجع ۱) و «چند میلی‌ثانیه مانده» درِ این شاخه سنجیده نشده — NOT_IMPLEMENTED |
| ۱۰ | دروازۀ پیش از ارسال + توقفِ اضطراری + لغوِ زمان‌بندی | **IMPLEMENTED** | I4–I6: halt ⇒ dispatch رد؛ resume با `confirm` ⇒ ارسال می‌رود؛ `aborted_schedules` در پاسخِ halt |
| ۱۱ | یک قصد = یک ارسال (بی‌تکرارِ کور) | **IMPLEMENTED** | I8: dispatchِ دوبارهٔ همان `execution_id` ⇒ `DUPLICATE_GUARD`؛ در contract هم `submit_order` بی‌retry است |
| ۱۲ | timeout ⇒ اول reconcile، نه ارسالِ دوباره | **IMPLEMENTED** | `UNKNOWN_RESULT` + مسیرِ reconcile؛ I7/I9/I10 |
| ۱۳ | معانیِ جدا: پذیرفته / مشاهده‌شده / صف / معامله | **PARTIAL** | `OrderState` در `execution_contract.py` این حالت‌ها را جدا دارد و `map_order_state` خاموش «معامله» نمی‌سازد؛ **جایِ صف** از کارگزاری واقعی هرگز دیده نشده (`queue_position = None` ⇒ UNKNOWN) |
| ۱۴ | چند روشِ اجرا (API مستقیم / آماده‌سازیِ فرم / اجرایِ مرورگری) زیرِ یک کنترل‌کننده | **NOT IMPLEMENTED** | فقط یک مسیر (API) پشتِ `BrokerAdapter` است. **عمداً** فعال نشده: برایِ یکِ قصد، دو ارسالِ رقابتیِ API و کلیک، قفلِ «جلوگیری از تکرار» را بی‌معنا می‌کند. تا اثباتِ «یک مالکِ ارسال» ⇒ REJECTED WITH REASON |
| ۱۵ | آماده‌سازی/راستی‌آزماییِ فرمِ مرورگری (مرجع ۳/۴) | **NOT IMPLEMENTED** | هیچ کلیک/تایپِ خودکاری درِ کارگزاری نیست (قاعدهٔ مأموریت) |
| ۱۶ | کالیبراسیونِ زمان و rate-limitِ هر نمونه | **NOT_IMPLEMENTED** | مرجع ۱؛ درِ ما فقط `polite_pause` برایِ *کدال* هست، نه برایِ کارگزاری |

## ۶) آنچه پیش ازِ «اتصالِ واقعی» باید دیده شود (BLOCKED)

سه چیز درِ این مخزن **مشاهده نشده** و با حدس ساخته نمی‌شوند؛ تا نیامدنشان ارسالِ زنده
خاموش می‌ماند (`BORS_EXECUTION_LIVE` + توکنِ کاربر):

1. **نشانی و شکلِ ورودِ Orbis/MTS** (صفحه، CSRF، گام‌های MFA) — مرجع ۱ آن را از
   «کوکیِ صفحه‌اختیِ کاربر» می‌داند، نه از یکِ قراردادِ مستند.
2. **اینکه نشانیِ API چگونه ازِ نشستِ مرورگر به دست می‌آید** — اگر کاربر خودش
   می‌تواند آن را کپی کند، مسیرِ امروز کار می‌کند؛ اگر نه، یکِ پلِ مرورگری لازم است
   که باید با شواهدِ واقعیِ System 2 طراحی شود.
3. **قالبِ بدنهٔ `orderPlace` و معنای `volumeAhead`/`from`** — در ماتریس مرجع با
   پرچمِ UNVERIFIED آمده؛ ما هم همان‌جا `WIRE_ORDER_FROM` و `WIRE_COMMISSION` را
   UNVERIFIED نگه داشته‌ایم (`execution_easytrader.py:77-78`).

## ۷) مرزهایِ این خروجی

- هیچ سفارشِ واقعی ارسال نشد؛ همه‌چیز `dry_run`/mock است (`I7` با `dry_run: true`).
- پیکربندیِ نصاب/بسته‌بندیِ ویندوز درِ این مرحله ساخته **نشده** — فقط `npm run build`
  (خروجۀ SPA) و اجرایِ بک‌اندِ محلی. انتشار/تگ/merge به `main` انجام نشده است.
- اعدادِ «اول صف» یا «ارسالِ زندهٔ تأییدشده» درِ هیچ کجای این شاخه ادعا نمی‌شود.
