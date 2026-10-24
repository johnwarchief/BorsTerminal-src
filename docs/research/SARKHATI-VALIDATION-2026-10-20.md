# اعتبارسنجی سرخطی — 2026-10-20 (Mission 2)

مبنای رسمی: `a14375c14cfb8fc616fb3312c685f8a5b0f79ab3` (v1.0.95)
Checkpoint: `735e4d63097a8d2645fdcb0c06bb393bf33367d3`
شاخه: `mission/multi-strategy-2026-10-20`
HEAD پیش از این مرحله: `7d16d888f0af3b115524926bb0671c6db218fa7b`

این سند فقط شواهدِ قابل‌بازتولید را ثبت می‌کند. هیچ سفارش واقعی در هیچ مرحله‌ای
ارسال نشد؛ هیچ endpointِ ثبت/لغو/تغییر سفارش فراخوانی نشد.

## A. Git

| مورد | مقدار |
| --- | --- |
| شاخه | `mission/multi-strategy-2026-10-20` |
| HEAD پیش از مرحله | `7d16d888f0af3b115524926bb0671c6db218fa7b` |
| وضعیت پیش از تغییر | clean؛ DB/node_modules/dist فقط ignored |
| فایل‌های تغییرکرده | `execution_browser.py`، `execution_strategy_engine.py`، `dev/strategy_guard_v1123.py`، `scripts/check_build_env.py`، همین سند (جدید) |
| کامیت این مرحله | یک کامیتِ مستقل روی همین شاخه؛ SHA در گزارشِ نهایی |
| secret/DB/HAR در diff | ندارد (بخش B-۴) |

دلیلِ هر تغییر:

- `execution_browser.py` — Probe فقط‌خواندنی غنی شد: ورودی‌ها/دکمه‌ها با
  tag/type/name/id/testid/aria/متنِ کوتاه، visible/enabled/readonly، تطابقِ
  selectorها، و `login_candidates`. هیچ `value` خوانده نمی‌شود. برای SPAِ
  EasyTrader که پس از load به SSO ریدایرکت می‌کند، انتظارِ network-idle و
  تلاشِ دوباره روی `Execution context was destroyed` اضافه شد تا Probe نتیجهٔ
  صفحهٔ نیمه‌بارگذاری‌شده را گزارش نکند. ارقام در متنِ برگشتی (عنوان/دکمه‌ها)
  با `•` پوشانده می‌شوند تا موجودی/شمارهٔ حساب امکانِ نشت نداشته باشد.
  شمارشِ شبکه (متد/میزبان، بدونِ مسیر) هم گزارش می‌شود تا صفر بودنِ POST به
  مسیرِ سفارش شاهدِ عددی داشته باشد.
- `execution_strategy_engine.py` — Probe دیگر دیدنِ صفحهٔ ورود را استثنا
  نمی‌کند؛ `login`/`login_source`، `host`، `origin_ok`، منبع/پیکربندیِ
  profile و `elapsed_ms` را گزارش می‌کند. `LOGIN_REQUIRED` فقط با دو شاهد:
  selectorِ ورودِ پیکربندی‌شده، یا فیلدِ رمزِ نمایان (شاهدِ ساختاری، نه
  selectorِ حدسی). مسیرِ trigger همچنان `_check_origin` و `_check_login`
  سخت‌گیرانه را دارد (خطوط ۴۴۷–۴۴۸).
- `dev/strategy_guard_v1123.py` — از ۴۴ به ۴۶ بررسی رسید: مقصد/origin_ok در
  Probe، و `LOGIN_REQUIRED` با فیلدِ رمز؛ به‌همراه بررسی‌های قبلیِ Stop،
  ۲۰۰-HTML، seamِ loopback، پیش‌فرض‌های production و sensorِ مرورگر.
- `scripts/check_build_env.py` — Playwright به فهرستِ پیش‌نیازهای بیلدِ رسمی
  اضافه شد تا نبودش در `.venv` پیش از بیلد دیده شود.
- این سند — ثبتِ شواهد و تفکیکِ اثبات‌شده/آزمایشی/مسدود.

## B. تست‌ها

### B-۱. Backend — `python dev/run_all_tests.py`

- دستور: `PYTHONIOENCODING=utf-8 python -u dev/run_all_tests.py`
- لاگ: `%TEMP%\run_all_final2.log` (UTF-16LE)؛ exit code در `run_all_final2.exit`
- خروجی نهایی: `ALL SUITES PASSED`، exit code **0**

| شمارش | واحد | مقدار |
| --- | --- | --- |
| suiteهای شروع‌شده | suite | **166** |
| suiteهای موفق | suite | **164** (137 شمارش‌دار + 27 silent) |
| suiteهای failed | suite | **0** |
| suiteهای skip (fixture missing) | suite | **2** |
| suiteهای silent (فقط exit code) | suite | **27** |
| بررسی‌های pass/fail در ۱۳۷ سوئیتِ شمارش‌دار | check | **4922 / 4922 pass، 0 fail** |

خروجی نهایی: `ALL SUITES PASSED`، exit code **0**.

دو skip فقط به‌خاطرِ نبودِ fixture محلی است و اجرا نشدند:
`Phase4 engine ... (_audit/ra365_ref_bars.json)` و
`R1/R2 housekeeping ... (market.db.lzma)`. هیچ‌کدام به‌عنوان «سبز» شمرده نشده‌اند.

**واحدِ شمارش:** `run_all_tests.py` در سطحِ **suite** می‌شمارد. برخی سوئیت‌ها
فقط exit code می‌دهند (silent) و شمارشِ check داخلی ندارند. عددِ suite و عددِ
check دو واحدِ متفاوت‌اند و بی‌توضیح جمع نمی‌شوند؛ مجموعِ checks فقط از
سوئیت‌های شمارش‌دار است، نه از silentها.

یک اجرای اولیه پیش از آخرین تغییرِ Probe آغاز شده بود و عمداً متوقف شد.
پس از آن، یک اجرای کاملِ دیگر پیش از افزودنِ شمارشِ شبکه سبز شد، ولی چون
کد بعد از آن تغییر کرد، مجموعه از ابتدا دوباره اجرا شد. اعدادِ بالا از
اجرای نهاییِ روی کدِ نهایی است؛ اعدادِ اجراهای قبلی گزارش نمی‌شوند.

علتِ شکستِ قبلیِ `npm_lock_v1040`: متغیرِ `npm_config_allow_scripts` تزریقیِ
محیطِ ایجنت باعث می‌شد npm 12 در نصبِ project-scoped خطای `EALLOWSCRIPTS`
بدهد. گارد فقط envِ همان subprocess را از `npm_config_*`/`npm_lifecycle_*`/
`npm_package_json`/`npm_command`/`npm_execpath`/`npm_node_execpath` پاک می‌کند؛
هیچ پیکربندیِ امنیتیِ npm و هیچ pin فروشگاه تغییر نکرد. گارد مستقل 4/4 سبز است.

### B-۲. Frontend

- `cd frontend && npx --no-install vitest run --maxWorkers=2` → exit 0
  (اسکریپتِ `package.json`: `vitest run`)
- `Test Files  197 passed | 2 skipped (199)`
- `Tests  2065 passed | 5 skipped (2070)`
- `Duration 208.28s`
- `cd frontend && npx --no-install tsc -b` → exit 0 (بدون خطا)

### B-۳. Sarkhati / security guards (اجرای مستقل در این مرحله)

- `dev/strategy_guard_v1123.py` → **47 checks, 0 failed, 0 skipped**؛ شاملِ:
  ردِ تنظیماتِ رازآلود، metrics فقط از نمونهٔ واقعی، arbiterِ یک‌submit،
  dry-run بدونِ transport/POST در همهٔ strategyها، عدمِ fallback پس از
  UNKNOWN، ۴۰۱/۲۰۰-HTML به‌عنوان عدمِ پذیرش، نبودِ مرورگر/selector/profile/
  مرورگرِ بسته به‌صورتِ خطای قابل‌تشخیص، Probe بدونِ value/token/cookie،
  `LOGIN_REQUIRED` با شاهدِ ساختاری، شمارشِ شبکه با `order_posts: 0`،
  پیش‌فرض‌های production، seamِ loopback فقط برای bench، و Stop پیش/پس از
  نتیجه.
- بقیهٔ گاردهای Sarkhati در همان `run_all_tests.py` بالا اجرا شدند؛ اعداد
  به‌تفکیک در لاگِ اجرای نهایی است.

### B-۴. secret/DB/HAR

- در diffِ این مرحله هیچ فایلِ `market.db`/`user.db`/`*.har`/`*.log`/`.env`/
  `*.pem`/`*.key` نیست. پنج فایلِ staged فقط کد و سند هستند.
- اسکنِ الگوهای JWT (`eyJ…`)، `Bearer <token>`، مقدارِ `authorization`/`cookie`
  و انتسابِ `token/secret/password` به رشتهٔ بلند روی diffِ staged: **بدونِ
  هیچ تطابق**.
- `python dev/persian_glyph_guard.py` (پس از stage، تا فایلِ جدید را هم
  ببیند): **4 passed / 0 failed**.

## C. Frozen Build

- مفسرِ رسمی: `.venv` با Python **3.12.14** (قراردادِ `requirements.txt`).
- `scripts/check_build_env.py` → exit 0، «14 importable modules» شاملِ
  `PyInstaller, fastapi, httpx, numpy, pandas, playwright, pythonnet,
  requests, uvicorn, webview` (و docx/openpyxl/orjson/reportlab).
- Build: `.venv/Scripts/python.exe scripts/build_all.py` → **exit 0**؛
  خروجی `dist/BorsTerminal_Ultimate`؛ اندازهٔ گزارش‌شده **230.2 MB**.
- `dev/onedir_contract_v11.py --dist dist` → **PASS**؛ 22 router module در
  22/23 hiddenimport؛ `webview`، `pythonnet` و `clr_loader` در بسته.
- نمایش: مسیرِ رسمی **native** است (pywebview + WebView2). لاگِ اجرای واقعی:
  `[native] persistent webview profile: ...\data\BorsTerminal_Ultimate\webview2`.
  Edge fallback مسیرِ رسمی نیست؛ اگر pywebview/WebView2 نباشد،
  `bors_entry` به مرورگر fallback می‌کند و آن مسیر در `_hold_open()` حلقهٔ
  بی‌پایان دارد و خروجِ UI ندارد.
- Playwright: بستهٔ Python 1.62.0 + driver/node.exe در بسته است، اما
  executable مرورگر عمداً در بسته نیست؛ از Edge/Chrome/Brave سیستم یا
  cacheِ `%LOCALAPPDATA%\ms-playwright` استفاده می‌شود. نبودِ مرورگر در
  گارد صادقانه `UNAVAILABLE` می‌شود؛ بستهٔ کاملِ مرورگر لازم نیست.
- Startup: سنجشِ زمان‌دار روی بیلدِ نهایی (اجرای سردِ اول پس از build):
  **۳۵۴۶٫۷ میلی‌ثانیه** از `Popen` تا اولین پاسخِ 200 از
  `GET /api/execution/strategies` (دقتِ poll: 50ms). در لاگ، `Uvicorn running`
  و اولین GET در همان ثانیه‌اند.
- Shutdown زمان‌دار: `WM_CLOSE` تا خروجِ process **۳۷۲۲٫۳ میلی‌ثانیه**؛
  exit code **0**؛ هیچ فرزندی در process tree نماند.
- Smoke (final build):
  - `startup_ok: true`، `GET /api/execution/strategies` → 200
  - `status: adapter=mock, dry_run=true, live_enabled=false`
  - prepare → success؛ triggerِ dry-run → `dry_run` با `transport_calls=0`
  - Probeِ Mock → 200، `has_structure: true`، `login: UNKNOWN`، `read_only: true`
  - صفحهٔ Mock: **GET 2 / POST 0**
  - پنجرهٔ native پیدا شد؛ `WM_CLOSE` → خروج **0**، `graceful: true`
  - فرزندِ مرورگر پس از خروج: `msedgewebview2.exe=0`, `msedge.exe=0`
  - هیچ processِ test app باقی نماند؛ اپِ نصب‌شدهٔ مالک (PID 32888) دست‌نخورده
- Shutdown: مسیرِ رسمی native، بستنِ پنجره است؛ لاگ:
  `[app] native window closed (boot worker: serving)` و
  `[app] [exit] process ending pid=... reason=window-closed`؛ exit code صفر.
  خطِ «Shutting down»ِ uvicorn دیده نمی‌شود چون process پس از برگشتنِ
  `webview.start()` پایان می‌یابد؛ نبودِ process/فرزندِ باقی‌مانده بررسی شد.

## D. Probe

- نوع عملیات: فقط خواندنی. Probe فقط `goto` (GET)، انتظارِ load و خواندنِ
  attributeهای DOM را انجام می‌دهد؛ هیچ click/submit/keyboard/JS-fetch به
  endpointِ سفارش ندارد. هیچ `value`، token، cookie یا Authorization خوانده
  یا برگردانده نمی‌شود. ارقامِ متنِ UI پیش از بازگشت پوشانده می‌شوند.
- خروجی: `url` (path)، `host`، `origin_ok`، `title`، `login`/`login_source`،
  `browser` (driver/headless/profile_source/profile_configured/alive)،
  `network` (requests/by_host/order_posts/truncated)، `selectors`
  (count/first_visible/first_enabled)، `structure`
  (inputs/buttons/login_candidates)، `elapsed_ms`، `read_only`.

### D-۱. Mock

- Probe روی صفحهٔ Mock محلی: 200، `read_only: true`، `login: UNKNOWN`
  (بدون selectorِ ورود و بدون فیلدِ رمز)، ساختار برگشت.
- شمارشِ سرورِ Mock در همان پنجره: **GET 2 / POST 0**.

### D-۲. EasyTrader واقعی (final frozen build)

- پروفایل: تازه/خالی (`data/real_probe_profile`، headless=true)؛ هیچ نشستِ
  جعلی ساخته نشد. اجرا دو بار تکرار شد و هر دو یک نتیجه دادند.
- `probe_http: 200`، `startup_ok: true`، `app_exit_code: 0`.
- مقصدِ نهایی: `url=/Login`، `host=login.emofid.com`، `origin_ok: false`
  (میزبانِ SSO بیرونِ allowlistِ d.easytrader.ir است؛ فقط گزارش شد).
- `title`: «ورود - کارگزاری مفید»؛ `login: LOGIN_REQUIRED`،
  `login_source: password-input-visible`؛ `read_only: true`؛
  `elapsed_ms≈6700`.
- ساختار (بدونِ مقدار): inputهای `Username` (text، visible)، `Password`
  (password، visible)، `__RequestVerificationToken` (hidden؛ فقط نام)؛
  دکمه‌ها: «ورود» (button، visible)، «فراموشی کلمه عبور»، «ثبت نام»،
  «رویه ارائه خدمات و انجام معاملات برخط».
- selectorهای سفارش: هر چهار selector (symbol/price/quantity/submit) روی
  صفحهٔ ورود `count: 0` — این دربارهٔ صفحهٔ سفارش چیزی اثبات نمی‌کند.
- شمارشِ شبکه از رویدادهای requestِ خودِ مرورگر (فقط میزبان و متد؛ مسیرها
  برنمی‌گردند): **80 درخواست**، `order_posts: 0` با
  `order_path_matched: true`، `truncated: false`. به تفکیک مقصد:
  `d.easytrader.ir` 54 GET؛ `login.emofid.com` 17 GET؛
  `api-mts.orbis.easytrader.ir` 1 GET؛ `www.googletagmanager.com` 6 GET؛
  `sapi.emofid.com` 1 POST؛ `www.google-analytics.com` 1 POST.
  دو POST را خودِ صفحه/تحلیل‌گرِ EasyTrader می‌زند، نه Probe؛ کدِ Probe فقط
  یک ناوبریِ GET و خواندنِ DOM انجام می‌دهد و هیچ POSTی به مسیرِ سفارش نرفت.
- هیچ کلیکِ ثبت یا درخواست به endpointِ تغییرِ سفارش انجام نشد؛
  `order_submitted: false`. بستنِ پنجرهٔ native با `WM_CLOSE` → exit 0.
- نتیجه: **VERIFIED_READ_ONLY برای صفحهٔ ورود/وضعیتِ ورود**؛ Probeِ صفحهٔ
  سفارش و selectorهای واقعی **BLOCKED** تا ورودِ دستیِ مالک.

### D-۳. اقدامِ حداقلیِ مالک (برای Probeِ صفحهٔ سفارش)

1. در پروفایلِ strategy (همان `profile_dir`، با `headless=false`) پنجرهٔ
   ورود را باز کنید و **خودتان** وارد شوید؛ هیچ رمزی در چت یا فیلدِ برنامه
   وارد نکنید. مسیرِ رسمی: «تنظیمِ اتصال» در تبِ سرخطی (پنجرهٔ اختصاصیِ
   دامنهٔ ورود).
2. پس از ورود، Probe را دوباره اجرا کنید تا `login` از `LOGIN_REQUIRED`
   به حالتِ صفحهٔ سفارش تغییر کند و ساختارِ فرم برگردد.
3. selectorهای واقعی (symbol/price/quantity/submit) را فقط از شواهدِ همان
   Probe پیکربندی کنید؛ هیچ selectorای حدس زده نمی‌شود.
4. اگر می‌خواهید Probe مقصدِ SSO را `origin_ok` نشان دهد،
   `https://login.emofid.com` را در allowlistِ ورود قرار دهید (این کار
   فقط گزارش را تغییر می‌دهد، نه مجوزِ ارسال).

## E. وضعیت قابلیت‌ها

| قابلیت | وضعیت | دلیل |
| --- | --- | --- |
| Direct API read-only | VERIFIED_LIVE (در همین مأموریت، پیش از این مرحله) | با نشستِ واقعی، فقط GET؛ پاسخِ خواندنی. در این مرحله دوباره اجرا نشد. |
| Direct API order submission | UNVERIFIED_LIVE / WIRE_HYPOTHESIS | هیچ سفارش واقعی ارسال نشد؛ قراردادِ ثبت اثبات نشده. |
| JavaScript | MOCK_VERIFIED / UNVERIFIED_LIVE | POST به Mockِ محلی و تفسیرِ پاسخ؛ کارگزاری واقعی نه. |
| Keyboard | MOCK_VERIFIED / UNVERIFIED_LIVE | همان؛ یک ارسالِ کلید حداکثر. |
| Playwright/DOM | MOCK_VERIFIED / UNVERIFIED_LIVE | همان؛ Probeِ واقعی فقط خواندنی و روی صفحهٔ ورود. |
| AutoClicker | MOCK_VERIFIED / UNVERIFIED_LIVE | همان؛ یک کلیک، بدون تکرار. |
| Selenium | UNAVAILABLE | بسته نصب نیست. |
| Browser readiness | AVAILABLE (سیستم) / NOT_CONFIGURED (سفارش) | مرورگر و Probe کار می‌کنند؛ selector/profileِ سفارش پیکربندی نشده. |
| Balance/purchasing power | UNKNOWN / BLOCKED | منبعِ معتبر در دسترس نیست؛ هیچ عددی ساخته نشد. «قدرت خرید: ...» صفحه هم مقدار نیست. |
| Frozen build (native + shutdown) | VERIFIED (smoke) | startup/API/dry-run/Probe/shutdown؛ بدونِ سفارش. |
| WIRE_HYPOTHESIS | UNRESOLVED | قراردادِ ثبت/پاسخ با کارگزاری واقعی اثبات نشده. |

## F. موانع باقی‌مانده

- Probeِ صفحهٔ سفارش: ورودِ دستیِ مالک در پروفایلِ strategy (BLOCKED).
- selectorهای واقعی سفارش: هیچ‌کدام تأیید نشده (UNKNOWN).
- ارسالِ زنده: هیچ مجوز/آزمونِ واقعی وجود ندارد (UNVERIFIED_LIVE).
- قدرت خرید: منبعِ عددیِ معتبر ندارد (UNKNOWN).
- Edge fallback: مسیرِ رسمی نیست و خروجِ UI ندارد؛ فقط در نبودِ
  pywebview/WebView2 رخ می‌دهد و باید همین‌طور مستند بماند.

## G. بازتولید

```bash
# tests (backend)
PYTHONIOENCODING=utf-8 python -u dev/run_all_tests.py

# tests (frontend)
cd frontend && npx --no-install vitest run --maxWorkers=2
cd frontend && npx --no-install tsc -b

# guards
PYTHONIOENCODING=utf-8 python dev/strategy_guard_v1123.py
PYTHONIOENCODING=utf-8 python dev/persian_glyph_guard.py

# frozen build (official interpreter)
.venv/Scripts/python.exe scripts/check_build_env.py
.venv/Scripts/python.exe scripts/build_all.py
.venv/Scripts/python.exe dev/onedir_contract_v11.py --dist dist
```

## H. تفکیکِ ادعا

- **اثبات‌شده در این مرحله:** بیلدِ native، startup/API (۳۵۴۷ms)، dry-run
  بدونِ transport، Probe فقط‌خواندنی روی Mock و روی صفحهٔ ورودِ واقعی،
  خروجِ سالمِ native (۳۷۲۲ms، exit 0)، نبودِ فرزندِ باقی‌مانده، 166 suite
  (164 pass، 0 fail، 2 skip؛ 4922/4922 check در ۱۳۷ سوئیتِ شمارش‌دار)،
  47/47 گاردِ strategy، 197/199 فایل و 2065/2070 تستِ فرانت، exit 0 برای tsc.
- **آزمایشی/محلی:** همهٔ strategyهای مرورگری روی Mock؛ تفسیرِ پاسخ و
  زمان‌بندی، بدونِ کارگزاری واقعی.
- **مسدود:** Probeِ صفحهٔ سفارش، selectorهای واقعی، ارسالِ زنده،
  قدرت خرید، و اثباتِ WIRE.
