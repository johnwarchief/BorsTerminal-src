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

**ورودِ واقعی در این اجرا انجام نشد.** پنجره به‌صورتِ خودکار باز نشد و هیچ
credentialای وارد نشد؛ بنابراین هیچ پاسخِ واقعیِ حساب دریافت نشده و وضعیت‌هایِ
واقعیِ auth/حساب `NOT_MEASURED`/`BLOCKED` هستند. آنچه تأیید شده، مسیرِ کد و
رفتارِ آن با mock/Playwright است.

`live_enabled=false` و `live_ready=false` در همهٔ پاسخ‌ها حفظ شدند و هیچ درخواستِ
تغییردهندهٔ وضعیت یا سفارش ساخته نشد.

## ۲) وضعیتِ نهایی

| موضوع | وضعیت | شاهد / دلیل |
|---|---|---|
| پنجرهٔ ورودِ اختصاصی Mofid | `IMPLEMENTED_AND_TESTED` | hostِ نام‌دار + API + UI؛ آزمونِ cmd و مسیر/پروفایل |
| ورودِ دستیِ واقعی | `NOT_PERFORMED` | هیچ credentialای وارد/ذخیره نشد |
| پلِ token از localStorage | `IMPLEMENTED_AND_TESTED` | Playwright/CDP روی صفحهٔ محلی؛ token در meta/log نیست |
| نشستِ واقعیِ کارگزاری | `BLOCKED` | نیاز به ورودِ دستیِ مالک |
| allowlistِ GET و منعِ POST | `IMPLEMENTED_AND_TESTED` | 25/25 گارد؛ هیچ POST در آزمون‌ها |
| detail فقط با شناسهٔ فهرست | `IMPLEMENTED_AND_TESTED` | شناسهٔ ساختگی پیش از ترافیک رد می‌شود |
| 401 ⇒ باطل‌شدن token/cache | `IMPLEMENTED_AND_TESTED` | آزمونِ توالیِ 200→401؛ دادهٔ کهنه برنمی‌گردد |
| حساب/پرتفویِ واقعی | `NOT_MEASURED` | هیچ پاسخِ واقعی دیده نشد |
| sellable | `CLIENT_DERIVED_UNVERIFIED` (بدون تغییر) | منبعِ رسمیِ قابل‌فروش تأیید نشد |
| حالت‌هایِ UI | `IMPLEMENTED_AND_TESTED` | Vitest 8/8 + مرورگرِ زنده با APIِ بدل 7/7 |
| live_enabled/live_ready | `FALSE` | در verify/session/UI صریح |
| دیتابیس عملیاتی | `UNCHANGED` | هش‌ها پیش/پس از suite یکسان |

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
| URL | فقط `customer/status`، `Portfolio/Daily`، `open-orders`، `today-order`، `state/{id}`، `detail/{id}` |
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

## ۶) آزمون‌ها

| آزمون | نتیجه | چه چیزی را ثابت می‌کند |
|---|---|---|
| `dev/mofid_session_v1165.py` | 25/25 | parse token، Playwright/CDP capture از صفحهٔ محلی، NO_SESSION/EXPIRED، allowlistِ GET، order-id provenance، 401/cache، verify states، login window/stop، جدایی host |
| `dev/mofid_adapter_v1163.py` | 38/38 | قراردادِ Round 16 + قفلِ read_only و شناسه |
| `dev/mofid_readiness_v1164.py` | 14/14 | API/readiness و صفر POST |
| `dev/broker_connect_v1120.py` | 38/38 | تنظیمِ اتصال و گاردِ نشست |
| `dev/execution_connection_v1142.py` | 39/39 | لایهٔ اتصال/نشست |
| `dev/p0_gates_v1118.py` | 33/33 | گیت‌هایِ P0 |
| `frontend/src/__tests__/autoclicker-page.spec.tsx` | 8/8 | ورود/بررسی/حساب/خطا/عدمِ live-ready |
| `_audit/round17_ui_check.py` (مرورگرِ زنده با APIِ بدل) | 7/7 | گردشِ واقعیِ UI در 1366x768؛ اسکرین‌شات |
| `npx tsc -b` | 0 خطا | تایپ‌چک |
| `npm run build` | exit 0 | بیلدِ Vite |
| `dev/run_all_tests.py` | `PASS` | 145 counted / 32 silent / 2 skipped / 0 FAIL؛ `operational_changed=none`؛ `ALL SUITES PASSED` |

اجرایِ نخستِ suite فقط به‌خاطر یک «ي» عربی در docstringِ تازهٔ
`execution_browser_host.py` گاردِ گلیف را قرمز کرد؛ متن اصلاح و اجرایِ دومِ کامل
سبز شد. هر سه گاردِ Mofid در همان اجرایِ نخست هم سبز بودند.

اسکرین‌شاتِ UIِ mockشده: `_audit/round17_ui.png` (با گام‌هایِ Probe). این
اسکرین‌شات اثباتِ چیدمان/متن با APIِ بدل است، نه ورودِ واقعی. رأیِ بصریِ نهایی با
مالک است.

## ۷) آنچه هنوز باید با ورودِ واقعی سنجیده شود

1. بازکردنِ پنجره از UI و ورودِ دستیِ مالک؛ سپس «بررسی اتصال».
2. ثبتِ پاسخِ واقعیِ `customer/status`: وجود/نوع/واحد/digitsِ `purchasingPower`.
3. `Portfolio/Daily`: `currentAsset`، `todayBoughtAsset`، `todaySoldAsset`،
   `openSellOrders` و مقایسهٔ کرانِ `sellable` با عددِ اعلامیِ کارگزار (اگر هست).
4. `open-orders`/`today-order`/`detail`/`state`: رشته‌هایِ وضعیت و قالب/منطقهٔ
   زمانیِ `orderDateTime`؛ 404 واقعی.
5. رفتارِ 401/403/timeout با نشستِ واقعی و عدمِ نمایشِ دادهٔ کهنه.
6. هنوز هیچ آزمونِ نوشتن/سفارش در این راند انجام نشده و نباید شود.

## ۸) محدودیت‌ها و یادداشت‌ها

- **ورودِ واقعی انجام نشد**؛ عمداً پنجره به‌صورتِ خودکار باز نشد تا پنجره/نشستِ
  کاربر کنترل نشود. کد و UI آماده‌اند و از مسیرِ بند ۳ باز می‌شوند.
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
| `execution_mofid.py` | `read_only`، allowlistِ GET، order-id provenance، پاک‌شدنِ کش در 401 |
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
