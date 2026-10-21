# Round 17 — نشستِ ورودِ دستیِ Mofid و اعتبارسنجیِ فقط‌خواندنی

- تاریخ: 2026-10-22 (شروع در 2026-10-21)
- شاخه: `mission/sarkhati-round17-mofid-manual-session-2026-10-22`
- پایه: `3a854faf` (Round 16)
- دامنه: پنجرهٔ ورودِ دستیِ Mofid، پلِ نشست، گاردِ فقط‌خواندنی و Probeِ حساب.

## ۱) خلاصهٔ اجرایی

یک پنجرهٔ مرورگرِ **اختصاصی و نام‌دار** برای ورودِ رسمیِ Mofid اضافه شد
(`bors_browser_host_mofid.json` و `browser_host_profile_mofid`). این پنجره از
hostِ EasyTrader و از پنجره‌هایِ Rahavard/مرورگرِ کاربر جدا است و هیچ صفحه‌ای را
هدایت/بازنشانی نمی‌کند. پس از ورودِ دستی، دکمهٔ «ورود انجام شد؛ بررسی اتصال» با
همان CDPِ محلی، کلیدِ `token` را از localStorage صفحهٔ `tg.mofidonline.com`
می‌خواند و **فقط در حافظه** به آداپتور می‌دهد؛ برنامه هیچ token/cookie را در log،
پاسخ، دیتابیس، `.env` یا گزارش نمی‌نویسد. پروفایلِ اختصاصیِ مرورگر، مثلِ هر ورودِ
مرورگری، نشست را رویِ خودِ پروفایل نگه می‌دارد و برنامه آن را export نمی‌کند.

گاردِ `read_only` در خودِ `MofidAdapter` enforce شد: فقط GET و فقط مسیرهایِ
allowlist، ارسالِ سفارش ممنوع، و `detail/{id}` فقط برایِ شناسه‌هایی که از فهرستِ
واقعیِ سفارش‌هایِ باز/امروز آمده‌اند. 401 شاهدِ نشست و کش را باطل می‌کند.

**ورودِ دستیِ واقعی انجام شد** و Probeِ فقط‌خواندنی در 2026-10-22 به
`READ_ONLY_PROBE_OK` رسید: نشست با `/Order/customer/status` (200) تأیید شد،
`Accounting/Remain` قدرت خرید را داد، `Portfolio/Daily` دوازده دارایی برگرداند و
فهرست‌هایِ سفارشِ باز/امروز خالی بودند. مقدارِ قدرت خرید عددیِ صحیح بود؛ در این
گزارش ماسک شده و فقط در پاسخِ محلی/گفت‌وگویِ مالک دیده می‌شود.

یک divergence واقعی هم پیدا و اصلاح شد: `customer/status` این حساب
`purchasingPower` نداشت؛ منبعِ مبلغ به `/Accounting/Remain` (web V4) رفت (همان
مسیری که بستهٔ اول‌طرف برایِ این فیلد دارد). اگر هر دو مسیر فیلد را نداشته باشند،
آداپتور فقط **نامِ کلیدها** را برایِ تشخیص برمی‌گرداند، نه مقدار.

`live_enabled=false` و `live_ready=false` در همهٔ پاسخ‌ها حفظ شدند و هیچ درخواستِ
تغییردهندهٔ وضعیت یا سفارش ساخته نشد.

## ۲) وضعیتِ نهایی

| موضوع | وضعیت | شاهد / دلیل |
|---|---|---|
| پنجرهٔ ورودِ اختصاصی Mofid | `OPENED_LIVE` | Edgeِ جدا رویِ `login.emofid.com` (client_id=mofidTitan) |
| ورودِ دستیِ واقعی | `PERFORMED_BY_OWNER` | مالک خودش وارد شد؛ صفحه به `tg.mofidonline.com` رسید |
| پلِ token از localStorage | `VERIFIED_LIVE` | token به آداپتور رسید؛ meta فقط طول/نوع/exp |
| نشستِ واقعیِ کارگزاری | `VERIFIED_LIVE` | `/Order/customer/status` 200 و `session_proven=true` |
| allowlistِ GET و منعِ POST | `ENFORCED_LIVE` | همهٔ گام‌ها GET؛ هیچ POST/سفارش |
| detail فقط با شناسهٔ فهرست | `IMPLEMENTED_AND_TESTED` | در این نشست سفارشی نبود؛ هیچ ID حدسی فرستاده نشد |
| 401 ⇒ باطل‌شدن token/cache | `IMPLEMENTED_AND_TESTED` | آزمونِ توالیِ 200→401؛ در نشستِ واقعی 401 رخ نداد |
| حساب/پرتفویِ واقعی | `VERIFIED_LIVE` | 12 ردیف؛ فهرست‌های سفارش 0/0 |
| purchasingPower | `VERIFIED_NUMERIC` | عددیِ صحیح؛ منبع `/Accounting/Remain`؛ مقدار ماسک‌شده |
| sellable | `CLIENT_DERIVED_UNVERIFIED` | فرمول در 12/12 ردیفِ واقعی سازگار؛ برچسب تغییر نکرد |
| سفارش‌ها/read-back | `LISTS_READ_EMPTY` | open=0، today=0؛ read-back موضوعیت نداشت |
| حالت‌هایِ UI | `VERIFIED_LIVE` | حالت `خواندن تأیید شد` و حساب واقعی در UI |
| live_enabled/live_ready | `FALSE` | در verify/session/UI صریح |
| دیتابیس عملیاتی | `UNCHANGED` | `market.db=fd688edb...` و `user.db=fbffd6ef...` |

### ۲-۱) جدولِ نتیجهٔ اجرایِ واقعی (2026-10-22)

| مورد | نتیجهٔ واقعی |
|---|---|
| نسخهٔ اجراشده | Round 17، شاخهٔ `mission/sarkhati-round17-...`، commit `5bc44540` + اصلاحِ حداقلیِ fallback |
| پنجرهٔ ورود | باز شد (Edgeِ اختصاصی، صفحهٔ رسمیِ ورود) |
| ورود دستی | انجام شد (توسطِ مالک) |
| احراز هویت واقعی | موفق؛ `/Order/customer/status` 200، `READ_ONLY_PROBE_OK` |
| پاسخ حساب | دریافت شد؛ منبع مبلغ `/Accounting/Remain` |
| قدرت خرید | عددیِ صحیح تأیید شد؛ مقدار در گزارش ماسک شده · واحد `IRR` |
| تعداد قابل‌فروش | فرمول ۱۲/۱۲ ردیف سازگار؛ همچنان `CLIENT_DERIVED_UNVERIFIED` |
| سفارش‌ها و read-back | open=0، today=0؛ هیچ detail/read-backی برایِ شناسهٔ ناموجود فرستاده نشد |
| درخواست تغییردهندهٔ وضعیت | صفر (همه GET) |
| وضعیت اجرای زنده | `live_enabled=false` · `live_ready=false` |

## ۳) پنجرهٔ ورود از کجا باز می‌شود

1. در `/autoclicker` مسیر **API** را انتخاب کنید.
2. در «تنظیم اتصال» آداپتور **مفید آنلاین (Titan)** و **فقط‌خواندنی** را انتخاب
   و برنامه را یک‌بار restart کنید (پیش‌نیازِ فعال‌شدن `MofidAdapter`).
3. دکمهٔ **«ورود به حساب مفید»** در بخشِ «حساب مفید (ورود دستی، فقط‌خواندنی)».
4. پنجرهٔ اختصاصی روی `https://tg.mofidonline.com/` باز می‌ماند؛ نام کاربری/رمز/
   OTP/CAPTCHA را **خودِ مالک** در همان صفحهٔ رسمی وارد می‌کند.
5. پس از ورود، دکمهٔ **«ورود انجام شد؛ بررسی اتصال»**.

آدرس از originِ اول‌طرفِ Round 16 (`WIRE_ORIGIN`) گرفته شده است؛ در buildManifest
همان بسته مسیرِ `/login` هم دیده شد، ولی ریشهٔ origin باز می‌شود تا خودِ کلاینت
مسیرِ ورود را انتخاب کند. هیچ URL حدسی ساخته نشد.

### امنیتِ پنجره و نشست

- پروفایل و statusِ جدا: `browser_host_profile_mofid` / `bors_browser_host_mofid.json`.
- `BH.start_host(name="mofid")` بدونِ URL عمداً `URL_REQUIRED` می‌دهد تا پروفایلِ
  Mofid اشتباهاً صفحهٔ EasyTrader را باز نکند.
- بستنِ پنجره فقط PID/پروفایلِ همان hostِ نام‌دار را هدف می‌گیرد
  (`_pid_matches` + `stop_host(name="mofid")`).
- پنجره پس از ورود خودکار بسته نمی‌شود؛ بستن فقط با دکمهٔ «بستن پنجرهٔ ورود».
- نشست در localStorageِ همان پروفایلِ مرورگر می‌ماند (رفتارِ خودِ مرورگر)؛
  برنامه آن را export نمی‌کند. token فقط با اقدامِ صریحِ «بررسی اتصال» خوانده
  و در حافظهٔ پروسه به آداپتور داده می‌شود.

## ۴) پلِ نشست و گاردِ فقط‌خواندنی

### ۴-۱) `execution_mofid_capture.py`

- فقط hostِ `tg.mofidonline.com` (allowlist)؛ صفحهٔ ورودِ سایر سرویس‌ها خوانده نمی‌شود.
- کلیدِ `token` از localStorage؛ token خالی/کوتاه/بزرگ/دارایِ فاصله رد می‌شود.
- JWT در صورت وجود، فقط `exp/iat` برایِ بررسیِ انقضا؛ `sub`/نام/مقدار در meta نیست.
- meta فقط `token_present/length/type/expires_at/page_host/page_path/captured_at`.
- 401/403 و timeout در آداپتور به `SESSION_EXPIRED`/`AUTH_FAILED`/`UNKNOWN` نگاشت می‌شوند.
- `capture_from_host` صفحه را نمی‌بندد/navigate نمی‌کند؛ فقط اتصالِ Playwright را می‌بندد.

### ۴-۲) `MofidAdapter` در حالتِ `read_only`

| قفل | رفتار |
|---|---|
| method | فقط `GET`؛ هر `POST/PUT/DELETE` پیش از ترافیک رد می‌شود |
| URL | فقط `customer/status`، `Accounting/Remain`، `Portfolio/Daily`، `open-orders`، `today-order`، `state/{id}`، `detail/{id}` |
| fallbackِ مبلغ | اگر `customer/status` فیلد `purchasingPower` نداشت، `/Accounting/Remain` (web V4) با همان GET خوانده می‌شود؛ اگر هیچ‌کدام نبود، فقط نامِ کلیدها گزارش می‌شود |
| order detail | فقط اگر شناسه از `open-orders`/`today-order`یِ همان نشست آمده باشد |
| شناسهٔ نامعتبر/ساختگی | پیش از هر درخواست `UNSUPPORTED`؛ هیچ شناسهٔ حدسی |
| submit_order | حتی با `writes_allowed`، در `read_only` ممنوع |
| 401/403 | token، `session_proof` و کشِ `customer/status` باطل می‌شوند |
| 5xx/timeout | `UNKNOWN_RESULT`؛ بدونِ retry؛ کش پاک می‌شود |

`_adapter()` در API، `MofidAdapter` را با `read_only=not LIVE_REQUESTED` می‌سازد؛
حالتِ عادیِ این راند read_only است. `capabilities().place` هم در این حالت `False` است.

### ۴-۳) API

| مسیر | کار |
|---|---|
| `GET /api/execution/mofid/session` | فقط metadata/شمارش؛ بدونِ حساب/token |
| `POST /api/execution/mofid/login-window` | بازکردنِ hostِ نام‌دارِ mofid؛ بدونِ ورود |
| `DELETE /api/execution/mofid/login-window` | بستنِ همان host؛ بدونِ بستنِ hostِ دیگر |
| `POST /api/execution/mofid/verify-session` | capture + authenticate + money/positions/orders/detailsِ مجاز |

`verify-session` فقط اگر `adapter=mofid`، `read_only=true` و ترافیکِ خواندن مجاز
باشد اجرا می‌شود. در غیرِ این صورت `NEEDS_LOGIN` با دلیلِ `ADAPTER_NOT_READY`/
`NOT_READ_ONLY` برمی‌گردد. در خطا `account=None` است و هیچ دادهٔ قبلی برگردانده
نمی‌شود.

### ۴-۴) وضعیت‌ها

| وضعیت | معنا |
|---|---|
| `NEEDS_LOGIN` | پنجره باز است ولی نشست تأیید نشده / پیش‌نیاز آداپتور نیست |
| `AUTHENTICATING` | درخواستِ واقعیِ capture/authenticate در جریان است |
| `AUTHENTICATED_UNVERIFIED` | token در حافظه است ولی Probeِ کامل اجرا نشده |
| `READ_ONLY_PROBE_OK` | همهٔ GETهایِ مجاز موفق؛ حساب خوانده شد |
| `SESSION_EXPIRED` | 401/403؛ token و کش باطل |
| `READ_ONLY_PROBE_FAILED` | timeout/5xx/پاسخِ ناقص؛ بدونِ حسابِ کهنه |

موفقیتِ `READ_ONLY_PROBE_OK` به‌معنای آمادگیِ ارسال نیست؛ `live_enabled` و
`live_ready` در همان پاسخ `False` می‌مانند.

## ۵) UI

- بخشِ «حساب مفید (ورود دستی، فقط‌خواندنی)» با سه اقدام: ورود، بررسی اتصال،
  بستنِ پنجره؛ برچسبِ وضعیت و علتِ هر حالت.
- فقط پس از پاسخِ `READ_ONLY_PROBE_OK` حساب نمایش داده می‌شود؛ در خطا دادهٔ قبلی
  فوراً با `setMofidProbe(null)` پاک می‌شود.
- `sellable` با `CLIENT_DERIVED_UNVERIFIED` باقی می‌ماند.
- خطِ ثابت: `ارسال سفارش بسته است: live_enabled=false · live_ready=false`.
- هیچ مسیرِ خودکارِ «متصل شد» یا «آماده برای ارسال» وجود ندارد.
- در اجرایِ واقعیِ 2026-10-22، UI پس از Probe حسابِ 12 ردیفی را نشان داد و
  `sellable` را با برچسبِ `CLIENT_DERIVED_UNVERIFIED` نگه داشت؛ اسکرین‌شاتِ
  حسابِ واقعی عمداً commit نشد.

## ۶) آزمون‌ها

| آزمون | نتیجه | چه چیزی را ثابت می‌کند |
|---|---|---|
| `dev/mofid_session_v1165.py` | 25/25 | parse token، Playwright/CDP capture از صفحهٔ محلی، NO_SESSION/EXPIRED، allowlistِ GET، order-id provenance، 401/cache، verify states، login window/stop، جدایی host |
| `dev/mofid_adapter_v1163.py` | 39/39 | قراردادِ Round 16 + قفلِ read_only/شناسه + fallbackِ `Accounting/Remain` |
| اجرایِ واقعی 2026-10-22 | `READ_ONLY_PROBE_OK` | session 200، 12 دارایی، 0 سفارش، مبلغ عددی، همهٔ گام‌ها GET |
| `dev/mofid_readiness_v1164.py` | 14/14 | API/readiness و صفر POST |
| `dev/broker_connect_v1120.py` | 38/38 | تنظیمِ اتصال و گاردِ نشست |
| `dev/execution_connection_v1142.py` | 39/39 | لایهٔ اتصال/نشست |
| `dev/p0_gates_v1118.py` | 33/33 | گیت‌هایِ P0 |
| `frontend/src/__tests__/autoclicker-page.spec.tsx` | 8/8 | ورود/بررسی/حساب/خطا/عدمِ live-ready |
| `_audit/round17_ui_check.py` (مرورگرِ زنده با APIِ بدل) | 7/7 | گردشِ واقعیِ UI در 1366x768؛ اسکرین‌شات |
| `npx tsc -b` | 0 خطا | تایپ‌چک |
| `npm run build` | exit 0 | بیلدِ Vite |
| `dev/run_all_tests.py` | `PASS` (پیش از fallback) | 145 counted / 32 silent / 2 skipped / 0 FAIL؛ `operational_changed=none`؛ `ALL SUITES PASSED` |

اجرایِ نخستِ suite فقط به‌خاطر یک حرفِ عربیِ `U+064A` در docstringِ تازهٔ
`execution_browser_host.py` گاردِ گلیف را قرمز کرد؛ متن اصلاح و اجرایِ دومِ کامل
سبز شد. هر سه گاردِ Mofid در همان اجرایِ نخست هم سبز بودند. fallbackِ
`Accounting/Remain` پس از اجرایِ واقعی اضافه شد و با گاردِ آداپتور (39/39) و
گاردهایِ API/نشست آزموده شد؛ suite کامل پس از این تغییرِ کوچک دوباره اجرا نشد.

اسکرین‌شاتِ UIِ mockشده: `_audit/round17_ui.png` (با گام‌هایِ Probe). این
اسکرین‌شات اثباتِ چیدمان/متن با APIِ بدل است، نه ورودِ واقعی. رأیِ بصریِ نهایی با
مالک است.

## ۷) آنچه هنوز سنجیده نشده

1. **قابل‌فروشِ رسمی:** فرمولِ ما با 12/12 ردیفِ واقعی سازگار است، ولی کارگزار
   عددِ رسمیِ «قابل‌فروش» نداده؛ برچسب `CLIENT_DERIVED_UNVERIFIED` می‌ماند.
2. **read-back/وضعیتِ سفارش:** در این نشست هیچ سفارشِ باز/امروزی نبود؛ detail/state
   واقعی آزموده نشد و هیچ شناسهٔ حدسی ساخته نشد.
3. **401/403/timeout واقعی:** در این نشست رخ نداد؛ رفتارِ آن فقط با mock آزموده شده.
4. **واحدِ سرور:** پاسخِ واقعی فیلدِ `unit` نداشت؛ `IRR` برچسبِ شواهد (کاتالوگِ
   ریالیِ خطاها و فیلدهایِ قیمت) است، نه ادعایِ فیلدِ صریحِ سرور.
5. **نوشتن/سفارش:** هیچ آزمونِ ثبت/اصلاح/لغو در این راند انجام نشد و نباید شود.

## ۸) محدودیت‌ها و یادداشت‌ها

- **ورودِ دستیِ واقعی انجام شد**؛ پنجرهٔ اختصاصی پس از restartِ backend با همان
  پروفایل بازگشایی شد و نشست حفظ شد. پس از ورود/بررسی، هیچ صفحه‌ای به
  `about:blank` نرفت و پنجرهٔ EasyTrader/Rahavard لمس نشد.
- دادهٔ خامِ حساب فقط در فایلِ موقتِ محلی و برایِ بررسیِ همین اجرا بود؛ در گزارش
  ماسک شده و اسکرین‌شاتِ حسابِ واقعی commit نشد.
- این قابلیت در **شاخه** است؛ اپِ نصب‌شدهٔ فعلی (Round 16) دکمه/endpointهایِ تازه
  را ندارد. برای استفاده باید از این شاخه بیلد/نصب شود (یا dev backendِ همین
  شاخه با Vite اجرا شود).
- پروفایلِ مرورگر نشست را روی دیسکِ همان پروفایل نگه می‌دارد (رفتارِ مرورگر)؛
  برنامه هیچ token/cookie را در دیتابیس/log/گزارش نمی‌نویسد.
- برایِ اجرایِ dev، `changeOrigin` پروکسیِ Vite به `false` تغییر کرد تا Origin/Hostِ
  محلی با گاردِ same-origin هم‌خوان باشند؛ اجرایِ نصب‌شده (همان origin) دست‌نخورده است.
- `execution_mofid_capture` در هر دو spec (`fts_terminal.spec` و `bors_setup.spec`)
  به hiddenimports اضافه شد.
- هیچ دادهٔ حساسِ حساب در گزارشِ عمومی نوشته نشده است؛ مقادیرِ mock فقط در آزمون‌اند.

## ۹) تغییراتِ فایل

| فایل | تغییر |
|---|---|
| `execution_browser_host.py` | hostِ نام‌دار/پروفایلِ جدا؛ `--name`؛ `URL_REQUIRED` برایِ hostِ نام‌دارِ بی‌نشانی |
| `execution_mofid_capture.py` | پلِ CDP، allowlist، parse/expiry، بدونِ افشایِ token |
| `execution_mofid.py` | `read_only`، allowlistِ GET، order-id provenance، پاک‌شدنِ کش در 401، fallbackِ `Accounting/Remain` و تشخیصِ کلیدها |
| `api/execution.py` | endpointهایِ login-window/verify/session، stateها، پاسخِ ماسک‌شده |
| `frontend/.../AutoClickerPage.tsx` | گردشِ ورود/بررسی/حساب، حالت‌ها، پاک‌شدنِ دادهٔ کهنه |
| `frontend/.../orderClient.ts` | انواع/متدهایِ Mofid و `useMofidSession` |
| `frontend/vite.config.ts` | `changeOrigin:false` برایِ هم‌خوانیِ same-origin در dev |
| `dev/mofid_session_v1165.py` | گاردِ ۲۵سنجه‌ایِ Round 17 |
| `dev/run_all_tests.py` | ثبتِ گاردِ تازه |
| `fts_terminal.spec`, `bors_setup.spec` | hiddenimportِ `execution_mofid_capture` |
| `_audit/round17_ui_check.py`, `_audit/round17_ui.png` | آزمون/اسکرین‌شاتِ مرورگری با APIِ بدل |

## ۱۰) شاخه و commitها

- شاخه: `mission/sarkhati-round17-mofid-manual-session-2026-10-22`
- پایه: `3a854faf`
- کامیتِ پیاده‌سازی: `2b8f2e44`
- نتیجهٔ نهاییِ suite: 145 counted / 32 silent / 2 skipped / 0 FAIL؛
  `operational_changed=none`؛ `_audit/round17_run_all_final.txt`.
- گاردِ گلیفِ فارسی: 4/4.
