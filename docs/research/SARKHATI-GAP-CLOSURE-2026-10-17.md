# بستن شکاف‌های سرخطی — سند تحویل 2026-10-17

شاخه: `mission/sarkhati-close-gaps-2026-10-17` (push شده روی `github`) · مبنی بر
`release/v1.0.91` @ `79895345cecd442424d048484ce492b00543427e` (تأییدِ وجود روی
GitHub با `git ls-remote`). `main` = `c0402614` دست‌نخورده؛ هیچ tag، Release، یا
`latest.json` تغییر نکرد. کامیت‌ها: `892d0845`، `627231e8`، `42bec762` (+ این سند).

برایِ هر بند گفته می‌شود آن بند **در کد پیاده شده**، **با Mock آزموده شده**، **در
مرورگر آزموده شده**، یا **در کارگزاری واقعی اثبات شده** است — با شاهدِ فایل/تست.
این چهار تا یکی نیستند.

## ۰) نقطۀ شروع و حفاظت از وضعیت

| بند | وضعیت | شاهد |
|---|---|---|
| SHA و شاخۀ مبدأ | VERIFIED | `git ls-remote github release/v1.0.91` = `79895345…`؛ `git status --short` = صفر سطر پیش از اولین تغییر |
| شاخۀ کاری مستقل | VERIFIED | `mission/sarkhati-close-gaps-2026-10-17`، push شده و با `ls-remote` دیده شده |
| `main`/تگ/ریلیز/نصبی ۸۰۰۱/دادۀ کاربر | VERIFIED (دست‌نخورده) | `refs/remotes/github/main` = `c0402614`؛ سرور نصبی در تمامِ مدت روی ۸۰۰۱ با `mode:"installed"` پاسخ ۲۰۰ داد؛ کپیِ آزمایشی روی ۸۱۰۲ با DBهای کپی‌شده نشست |
| کار CODAL و ۱۹ worktree دیگر | VERIFIED (دست‌نخورده) | `git show --stat` سه کامیت: فقط فایل‌های بند ۸ |
| خروجی System 2 | BLOCKED | روی این ماشین موجود نیست (جست‌وجو در ۱۹ worktree + `ls-tree` همهٔ سرهای راه دور + `gh search code` = ۰). از روی گزارش، کد بازسازی نشد |

## ۱) اتصال واقعی EasyTrader (§۲ مأموریت)

| بند | وضعیت | شاهد |
|---|---|---|
| سه مبدأ با نقشِ جدا | VERIFIED (کد + گارد) | `execution_connect.py`: `PROVEN_AUTH_HOSTS` / `PROVEN_UI_HOSTS` / `DEFAULT_LOGIN_HOSTS` + `auth_hosts()`/`ui_hosts()`/`login_hosts()`؛ بند د/ه گارد اتصال (۶۱ سنجه) و بند ۵ گارد جدید |
| مبدأها از شاهد، نه از حدس | VERIFIED (فقط‌خواندنی، صفر POST) | `d.easytrader.ir/app-version.json` ⇒ `apiPath = https://api-mts.orbis.easytrader.ir/…`؛ `account.emofid.com` ⇒ 302 ⇒ `login.emofid.com` با `/.well-known/openid-configuration` (issuer همان میزبان) و `<title>ورود - کارگزاری مفید</title>`؛ `emofid.com/easytrader/` به `d.easytrader.ir` پیوند می‌دهد |
| میزبان API هرگز پنجره باز نمی‌کند | VERIFIED (موتیشن‌شده) | `allowed_hosts() == login_hosts()`؛ چسباندنِ دوبلۀ میزبان API به این فهرست، سنجه‌های D3/E2e/E2e2 را قرمز می‌کند |
| تنظیمِ دامنة ورود، درِ API را باز نمی‌کند | VERIFIED | دو محیط جدا: `BORS_EXECUTION_CONNECT_HOSTS` (پنجره) و `BORS_EXECUTION_WIRE_HOSTS` (API در `wire_hosts()`); «ت» بند ۵ گارد جدید |
| `none` = بستنِ صریحِ پنجره | VERIFIED | E2b/E2b2 (بی‌این، پیش‌فرضِ مشاهده‌شده فعال می‌ماند و راه بستن نبود) |
| SSRF/redirect/wildcard/userinfo/بندر | VERIFIED | `validate_url`: https-only، بندر ۴۴۳ یا بی‌بندر، بک‌اسلش، userinfo، نقطۀ انتهایی، `netloc == host+port`؛ هیچ wildcard در هیچ فهرستی («ج» بند ۵)؛ `RequestsTransport(allow_redirects=False, max_retries=0, verify=True)` |
| SPA 200 ≠ ورود موفق | VERIFIED | `authenticate()` پاکتِ API می‌خواهد؛ بدنة HTML ⇒ `UNKNOWN_RESULT` و «اتصال تأیید نشد»؛ fixture `html_login_page_200` |
| ۴۰۱/۴۰۳/timeout/انقضا/JSON ناقص/بدنة خالی/origin بیرونِ فهرست | VERIFIED (Mock) | fixture با ۱۴ حالت + p0 بند ۱ و ۳/۴ + بند فِ گارد اتصال |
| نشستِ واقعیِ کارگزاری | BLOCKED | نیازمندِ ورودِ خودِ مالک (رمز/CAPTCHA/MFA دستِ خودش؛ هیچ دورزدنی ساخته نشده و هیچ credential در این ماشین نیست) |
| عبارت تأیید، انقضا، بازنشانی درِ مرورگر | VERIFIED در مرورگر | `_test_runs/ui_states_v1119.py`: ۲۸ سنجه ۰ شکست (Chromiumِ کشیده‌شده با `JEV_CHROME`)؛ حالت‌های live/expired با **پچِ پاسخِ واقعی** ساخته شدند و سرو شدنشان با شمارشِ handler اثبات شد؛ «قطع اتصال» واقعی کلیک شد: پنجره بسته و `secrets_stored:false` |
| باز کردنِ پنجره روی دامنة کارگزاری | NOT_RUN (عمداً) | درِ نشستِ معاملاتیِ مالک پنجرۀ بیرونی باز نشد؛ مسیرِ کد با transportِ بدل سنجیده شد |

## ۲) پروتکل واقعی سفارش Orbis (§۳)

| بند | وضعیت | شاهد |
|---|---|---|
| جداسازیِ قرارداد از منطقِ مرکزی | VERIFIED | ثابت‌های سیم فقط در `execution_easytrader.py`؛ `execution_service.py` هیچ مسیرِ کارگزاری نمی‌شناسد |
| فعال‌سازیِ آداپتورِ ناشناخته ممنوع | VERIFIED | `_configured_adapter()` فقط `mock|easytrader`؛ هر چیز دیگر ⇒ `mock` (fail-closed) |
| پنج معنای جدا (ارسال/پذیرش/رد/لغو/نامعلوم) | VERIFIED (Mock) | `interpret_easytrader_response()` + fixture؛ «۲۰۰ بی‌`isSuccessful` هرگز پذیرش نیست» و «رد با `id` هم رد است» در بند ۲ گارد جدید |
| retry خودکار پس از مبهم ممنوع | VERIFIED (Mock) | بند ۳ گارد جدید: دو اجرایِ همان قصد ⇒ دقیقاً یکِ POST و دومی `DUPLICATE_GUARD`؛ ۵۰۰ در `UNKNOWN_RESULT` می‌ماند نه `FAILED` (موتیشنِ «ابطال خاموش» گارد را قرمز کرد) |
| fixtureهای منشأدار | VERIFIED | `dev/fixtures/easytrader_wire_v1.json` — هر case `source` + `mock` دارد؛ `official_docs_status` داخل فایل؛ تنها ادعای «دیده‌شده» رفتارِ ۴۰۱ِ فقط‌خواندنی است |
| سند رسمی API | BLOCKED | `swagger`/`/openapi.json`/`/docs` روی میزبان API ⇒ ۴۰۳؛ هیچ درِ توسعه‌دهنده‌ای نیست ⇒ `WIRE_HYPOTHESIS` عمداً `True` و `/status` + `wire_provenance` اعلام می‌کنند |
| معنای بدنّة ۲۰۰ (id، omsError، رتبۀ صف) | NOT_PROVEN | فقط از کد شخص ثالث خوانده شده؛ دیدنِ پاسخِ واقعی درِ نشستِ مجاز لازم است |
| sandbox رسمی | NOT_FOUND | هیچ محیطِ آزمونِ مستندِ عمومی برای Orbis پیدا نشد |

## ۳) ماشین حالت و گیت‌های ریسک (§۴)

| الزام | وضعیت | شاهد |
|---|---|---|
| عبارت تأیید در بک‌اند | VERIFIED | `_confirm_gate()` + `CONFIRM_PHRASE_REQUIRED`؛ p0 بند ۲ (برابری کامل، نه پیشوند)؛ در مرورگر هم سنجیده شد |
| تغییر token/نشست، تأیید پیشین را باطل می‌کند | VERIFIED (افزودۀ همین مأموریت) | `_CONFIRM_EPOCH` + `_void_confirmations()`؛ زمان‌بندیِ منتظر ⇒ `aborted` با `cancelled_by="confirmation voided…"` و **صفر POST**؛ مسیر فوری هم پیشِ execute دوره را دوباره می‌سنجد؛ بند ۴ گارد (۵ سنجه) — خاموش‌کردنِ ابطال با موتیشن قرمز شد |
| preflight پیش از عمل حساس؛ رد احراز ⇒ صفر ارسال | VERIFIED | p0 بند ۱؛ بند ۹ گارد جدید (۴۰۱ ⇒ هیچ POST) |
| نبود پیکربندی ریسک ⇒ fail-closed | VERIFIED | `_risk_gate()` + `Limits`؛ p0 بند ۳/۴ |
| execution_id + قفل + ledger ضد تکرار | VERIFIED | `DUPLICATE_GUARD` (بند ۳) + `execution_ledger_v1108` (۴۸) |
| reconcile با پاسخ خالی ⇒ `UNKNOWN_RESULT` | VERIFIED | p0 بند ۳/۴ + fixtureهای `empty_body_200`/`truncated_json_200` |
| لغو per-id بی‌تداخل | VERIFIED | p0 بند ۸ (دو لغو هم‌زمان ⇒ حداکثر یک «لغو شد») |
| حالت‌های جدا، بی عددِ جعلی | VERIFIED | `mode_matrix`؛ **نقصِ واقعیِ همین بند:** `api/bot.py` حالت `live` را می‌پذیرفت و گیت می‌زد، ولی `PaperSession` همیشه `PaperBroker` می‌ساخت — «واقعی» در حقیقت کاغذی بود و رابط «واقعی» نشان می‌داد. اکنون `BOT_LIVE_NOT_WIRED` + ذخیره‌نشدنِ `live` + `broker_wired=paper_only` (گارد `bot_api_v1114` ۶۹/۰) |
| رتبۀ صف | VERIFIED (ادعا نه) | `queue_rank.claims_first=false`؛ `execution_queue_v1` (۲۴) «هرگز صفرِ اولِ صف نمی‌سازد» |
| ردپا با شناسه و زمان، بی راز | VERIFIED | `execution_ledger` + `execution_contract.redact()`؛ بند ۸ گارد با شش کنترل منفی |

## ۴) زمان‌بندی و تأخیر (§۵)

| بند | وضعیت | شاهد |
|---|---|---|
| ساعت کارگزاری فقط با endpoint مستند | VERIFIED (با قید) | `WIRE_PATH_SERVER_TIME` از capture عمومیِ مرجع ۲؛ سه نامزدِ فقط‌خواندنیِ دیگر با شاهدِ ۴۰۱ ثبت شدند (`WIRE_SESSION_PROBE_CANDIDATES`)؛ معنای بدنّة ۲۰۰ هنوز NOT_PROVEN |
| RTT در اندازه + monotonic برای مدت | VERIFIED | `execution_timing.percentile/estimate_one_way`؛ `_TIMINGS` روی `time.monotonic()` |
| p50/p95/p99 با نمونه‌ها | VERIFIED | `GET /api/execution/timings`؛ بند ۷ گارد: با یک نمونه `None` (کم‌نمونه)، با شش نمونهٔ واقعی عدد، و `p50 ≤ p99` |
| تفکیک فازها | VERIFIED | preflight/prepare/dispatch/response/reconcile جدا؛ `observed_ms` تا reconcile عمداً `None` |
| اندازه‌گیری بی‌بار اضافی | VERIFIED | هیچ سنجه‌ای درِ `/order` نمی‌زند؛ probe فقط‌خواندنی (p0 بند ۷) |
| رتبۀ صف رسمی | BLOCKED | دادهٔ رسمی دیده نشده؛ رابط به «زمان ارسال/پذیرش» محدود می‌ماند |

## ۵) مانیتورینگ و UI (§۶)

| بند | وضعیت | شاهد |
|---|---|---|
| collector و Task زنده و دست‌نخورده | VERIFIED | `monitor_bors.py` (PID 10988 تا ~۱۲:۴۹)؛ `Bors-Monitor-Test1091` امروز ۰۸:۴۱ شلیک کرد (`LAST_RUN=10/17/2026 08:41:00`، `RESULT=0x0`) و از فردا روزانۀ ۰۸:۴۰ است |
| نسخۀ جدید، لاگ‌های کهنه سالم | VERIFIED | `_test_runs/monitor_bors_v2.py` کنار v1؛ هیچ لاگی پاک/بازنویسی نشد؛ Task به v2 تغییر مسیر داد |
| correlation id + JSONL زمان‌دار | VERIFIED | هر رکورد `cid = <runid>-<seq>` + `ts` (v2) |
| sanitize با کنترل منفی | VERIFIED | `sensor_selftest()` در v2: نشتِ یکی از چهار رازِ کاشته‌شده یا پاک‌شدنِ متنِ بی‌راز ⇒ مانیتور روشن نمی‌شود (exit 3). همین سنجر با import از کپیِ کهنه قرمز شد و به ریشۀ نقص رساند |
| خلاصۀ خواندنی | VERIFIED | `summary.md` هر دور: سلامت، exit/crash/restart، ۴xx/۵xx، جدول p50/p95/p99 هر مسیر، ردپای prepare/dispatch/reconcile/cancel، وضعیت نشست |
| بی‌بار اضافی بر TSETMC/CODAL | VERIFIED | کپی آزمایشی `BORS_NO_FETCH_LOOPS=1`؛ collector فقط سه GET read-only به ۸۱۰۲ |
| کهنه، زنده نشان داده نشود | VERIFIED | `/api/market/sync-state` ⇒ `running:false`؛ در خلاصه صریح نوشته شده کهنه‌بودن انتخابِ ایمنی است نه نقص |
| UI در عرض‌های رایج | VERIFIED | `tools/jev_ui_check.mts` روی `#/watch` در ۱۲۸۰/۱۴۴۰/۱۹۲۰: ردیف اتصال + پنج کنترلاش، `consoleErrors` صفر، بدون ErrorBoundary؛ متنِ رابط: «دامنه‌های ورود: account.emofid.com، login.emofid.com، d.easytrader.ir» |

## ۶) گیت‌ها و بیلد (§۷) — همه با exit code

| فرمان | وضعیت | عدد |
|---|---|---|
| `dev/p0_gates_v1118.py` | VERIFIED | 33/0/0 skipped، exit 0 |
| `dev/sarkhati_connect_v1117.py` | VERIFIED | 61/0، exit 0 (۶ سنجۀ جدیدِ نقش‌ها) |
| `dev/sarkhati_protocol_v1119.py` (جدید) | VERIFIED | 47/0، exit 0؛ در `run_all_tests.py` ثبت شده |
| `dev/easytrader_adapter_v1113.py` | VERIFIED | 157/0 |
| `dev/execution_{contract,service,latency,ledger,queue,timing}.py` | VERIFIED | 20 · 50 · 21 · 48 · 24 · 32، همگی exit 0 |
| `dev/bot_api_v1114.py` / `dev/bot_paper_v1109.py` | VERIFIED | 69/0 · 54/0 |
| `npx tsc -b` | VERIFIED | exit 0 |
| `npx vitest run` | VERIFIED | 1699 passed / 5 skipped، exit 0 با `--maxWorkers=2`. اجرایِ پیش‌فرض ۲ timeout داد و همان دو پرونده در تنهایی ۱۰/۱۰ سبزند ⇒ بارِ ماشین، نه رگرسیون |
| `npm run build` | VERIFIED | exit 0 (`✓ built in 3.93s` و سپس `10.95s`) |
| `python dev/run_all_tests.py` | **VERIFIED — ALL SUITES PASSED** | exit 0 · ۱۰۹ شمارش‌شده + ۳۰ بی‌شمارش (فقط exit code) · **صفر قرمز** → `_test_runs/gatelogs/run_all_tests_isolated.out`؛ دو قرمزِ همیشگی ریشه‌دار و رفع شدند (بند ۶-الف) |
| بیلد PyInstaller | VERIFIED | onedir با **env ایزولۀ 3.12.14 + `numpy==2.0.2`** (`_test_runs/buildenv`) — نه 3.14ِ PATH که `numpy 2.4.2` دارد و pin را می‌شکند؛ زمانِ اندازه‌گیری‌شده ۰۹:۵۱:۳۰ ← ۰۹:۵۲:۰۰؛ خروجی `_test_runs/frozen/BorsTerminal_Ultimate/` (۱۶۷۷ فایل) |
| artifact + SHA‑۲۵۶ | VERIFIED | `BorsTerminal_Ultimate.exe` = `a5baced17eaf658e…`؛ manifestِ هر ۱۶۷۷ فایل: `_test_runs/frozen/frozen_manifest_sha256.json` |
| smoke روی artifact | VERIFIED | `python tools/smoke_check_portable.py …\BorsTerminal_Ultimate.exe` ⇒ `smoke: OK`: ۱.۰.۹۱ در باینری، `/api/execution/{status,connect}` زنده (hiddenimports درست)، چهار حالت نشست، صفر نشت مسیر، `dry_run/live` خاموش؛ فقط PID خودِ سنجه (32880) کشته شد |
| روش اجرای artifact | VERIFIED | `bors_portable.flag` + `market.db.lzma` کنارِ EXE ⇒ پرتابیل روی ۸۱۰۱ و پوشۀ دادۀ خودش؛ نصبیِ ۸۰۰۱ و دادۀ کاربر دست‌نخورده |
| `market.db.lzma` گم‌شده | VERIFIED (fixture محلی) | ۸۱٬۸۳۴٬۲۱۲ بایت کنارِ EXE و در ریشۀ کاری، **gitignored** (شاهد `git check-ignore -v` ⇒ `.gitignore:147:*.lzma`)؛ دادۀ کاربر commit نشد و نبودش سبز جعل نشد |
| اسکنِ credential در فایل‌ها | VERIFIED — صفرِ واقعی | ۱۵۷۱ فایل track‌شده + ۶۱ فایل `_test_runs/docs/dev/fixtures` با الگوی JWT/`Authorization:`/`set-cookie`/`password=` گشته شد: تنها JWT‌های موجود، **رازهای کاشته‌شدۀ خودِ گاردها**‌اند (`SIGNATURE_MUST_NEVER_LEAK`، `SIGNATURE_NO_LEAK`)؛ ۱۳ برازشِ دیگر نامِ تابع/برچسبِ مترجم‌اند نه مقدار |
| `npm ci` (نصبِ پاک) | **NOT_RUN** (علت دقیق) | `frontend/node_modules` این worktree **junction** به `_bors-sarkhati-connect` است؛ `npm ci` درختِ کارِ ایجنت دیگر را می‌نوشت. ریشه کشف شد (۶-الف) و تنظیم global دست‌نخورده ماند |

## ۶-الف) دو قرمزِ «محیطی» که ریشه‌دار و رفع شدند

| گارد | علتِ راستی‌آزمایی‌شده | رفع |
|---|---|---|
| `dev/npm_lock_v1040.py` | پیامِ خود npm: «`--allow-scripts` is not allowed in project‑scoped installs». علتش یک **متغیر محیطی** در همین نشست بود (`npm_config_allow_scripts=cline,protobufjs`، هم‌خوان `~/.npmrc`) که npm آن را به پرچم CLI تبدیل می‌کند؛ `frontend/package.json` خودش `allowScripts` اعلام کرده و CI آن env را ندارد | اجرای سوئیت با env پاک‌سازی‌شده ⇒ گارد **۴/۰**. `~/.npmrc` و تنظیم global تغییر نکرد |
| `dev/db_housekeeping.py --selftest` (R1/R2) | `_ROOT/market.db.lzma` می‌خواست و نبود | fixture محلی ساخته شد ⇒ exit 0 با «[selftest] PASS» و پاک‌شدنِ کپیِ temp |

## ۷) بلاکرها — دقیقاً چه شاهدی لازم است

| بلاکر | اثر بر عملکرد | تنها اقدامِ رفع |
|---|---|---|
| سند رسمی API Orbis (همه ۴۰۳) | شکل بدنه، معنای `id`/`omsError`، مسیرهای لغو/اصلاح فرضیه می‌مانند؛ دروازۀ ارسالِ واقعی عمداً بسته است | سند رسمی، یا یک ضبطِ خواندنیِ واقعی از نشست مجاز (بدنة پاسخِ `/order` و `/order-place`) |
| نبود نشست مجاز | «متصل شد» واقعی، انقضای واقعی و رتبۀ صف واقعی آزموده نمی‌شود | ورودِ خودِ مالک در پنجرۀ مرورگر — ما هیچ‌گاه این را دور نمی‌زنیم |
| رتبۀ صف رسمی | رابط نمی‌تواند «رتبه» نشان دهد؛ فقط «زمان ارسال/پذیرش» | یا دادهٔ رسمیِ رتبه، یا پذیرش همین محدودیتِ متنی |
| junctionِ `node_modules` + `~/.npmrc` | `npm ci` در این worktree امن نیست؛ گیتِ وابستگیِ تمیز باز می‌ماند | تصمیم مالک: گشودن `allow-scripts` جهانی، یا دادن `node_modules` مستقل به این worktree |
| خروجی‌های System 2 | ادغامِ کارِ آن‌ها ناممکن است | artifact یا کامیتِ واقعی |

## ۸) آنچه این شاخه لمس کرد

`api/execution.py`، `api/bot.py`، `execution_connect.py`، `execution_contract.py`،
`execution_easytrader.py`، `frontend/src/features/portfolio/components/BotPanel.tsx`،
`dev/sarkhati_connect_v1117.py`، `dev/bot_api_v1114.py`، `dev/run_all_tests.py`،
`dev/sarkhati_protocol_v1119.py` (جدید)، `dev/fixtures/easytrader_wire_v1.json`
(جدید)، و این سند.

## ۹) خروجی‌ها کجاست (هیچ‌کدام commit نشد)

`_test_runs/` درِ `.git/info/exclude` محلی ثبت شده تا کپیِ ۳۴۷مگ و داده‌ها وارد Git
نشوند (تداخلی با فایل‌های track‌شده ندارد ( = ۰)):

- `gatelogs/` — stdout و exit code هر فرمان (`p0_gates_v1118.out`, `sarkhati_connect_v1117.out`, `npm_build*.out`, `tsc.out`, `vitest*.out`, `pyinstaller.out`, `run_all_tests_*.out`, `robocopy.out`, `pipinstall.out`)
- `frozen/` — artifact + `frozen_manifest_sha256.json` + `market.db.lzma`
- `buildenv/` — env ایزولۀ ۳٫۱۲ برایِ بیلدِ pin‌شده
- `monitor_20261017_083918/` — `events.jsonl` (۱۱۵+ رویداد، cidدار) و `summary.md`
- `test_1091/` — کپیِ آزمایشیِ اجرا‌شده روی ۸۱۰۲. دو قلابِ صادقانۀ آن: (۱) یک بلوکِ
  لاگ‌گیریِ `[testreq]` در `app.py` دارد که درِ شاخه **نیست** (برایِ ستون «مدت»)
  و با هر robocopy باید دوباره افزوده شود؛ (۲) اجرایِ source است نه EXE — نسخۀ
  منجمدِ همان SHA جدا ساخته و smoke شد (بند ۶).
