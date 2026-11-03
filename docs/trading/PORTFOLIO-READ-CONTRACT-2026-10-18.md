# قراردادِ خواندنیِ پرتفوی — شواهدِ ۲۰۲۶‑۱۰‑۱۸

این سند فقط یک کار می‌کند: ثبتِ **آنچه واقعاً دیده شد** درِ مسیرهایِ پرتفوی و
تنظیمِ اتصال، و تفکیکِ آن از آنچه **دیده نشده**. هیچ عددِ مالی، هیچ ردیفِ دارایی
و هیچ «مانده» ای اینجا ساخته نشده است؛ هر جا شاهدی نبود، وضعیت
`NOT_OBSERVED` یا `NO_SOURCE` نوشته شده است.

- پایۀ سنجش: worktree `_bors-fts-technical`، شاخۀ `mission/broker-connect-ui-2026-10-18`
  (پایۀ `0dc5d0be` + رابطِ نشانیِ همین مرحلۀ)، بیلدِ منبعی باِ
  `python -m uvicorn app:app --port 8106` و `BORS_NO_FETCH_LOOPS=1 BORS_CODAL_OFFLINE=1`.
- آداپتورِ فعالِ آن پروسه: `mock`، `traffic_allowed=false`، `live_enabled=false`.
  یعنی هیچ‌یک ازِ این پرسش‌ها ازِ ماشین بیرون نرفت.
- ابزارِ سنجش: `tools/portfolio_contract_capture.py` (فقط شکلِ فیلد را ثبت می‌کند، نه
  مقدار). خروجیِ خامِ همین اجرا درِ `docs/trading/PORTFOLIO-CONTRACT-CAPTURE-2026-10-18.json`
  بایگانی شده و باِ `python tools/portfolio_contract_capture.py 8106` دوباره تولید می‌شود.

## ۱) مسیرها، آن‌طور که پاسخ دادند

| مسیر | متد | وضعیت HTTP | `content-type` | شکلِ بدنۀ پاسخ | رأی |
| --- | --- | --- | --- | --- | --- |
| `/api/execution/status` | GET | ۲۰۰ | `application/json` | ۳۲ کلید؛ `session{state,account_label,checked_at,origin,proven,verified_by}`، `capabilities{place,list_orders,order_state,queue_position,cancel,best_bid_ask,balances}`، `connection_config{adapter,adapter_source,applies_on_restart,read_only,secrets_stored,writes_gate}`، `mode_matrix{mock,paper,live,backtest,dry_run}`، `limits{۱۲ کلید}`، `blocked_on[]`، `session_live=false`، `traffic_allowed=false` | VERIFIED (همین پروسه) |
| `/api/execution/config` | GET | ۲۰۰ | `application/json` | `{status, stored{adapter,read_only,source,updated_at}, effective{adapter,traffic_allowed,read_only,live_requested,session_live,writes_gate}, applies_on_restart, secrets_stored, detail}` | VERIFIED |
| `/api/execution/config` | POST | ۲۰۰ | `application/json` | فقط دو کلیدِ `adapter` و `read_only` پذیرفته می‌شود؛ `secrets_stored=false` و `applies_on_restart=true` ثابت‌اند | VERIFIED درِ کد و گارد (برایِ این سند نوشتهٔ دیسک زده نشد) |
| `/api/execution/portfolio` | GET | ۲۰۰ | `application/json` | `{status, adapter, live, session_proven, as_of, source, rows, cached_at, error}` — درِ این حالت: `status="blocked"`, `rows=null`, `as_of=null`, `source="none"`, `error=<علت>` | VERIFIED |
| `/api/execution/connect` | GET | ۲۰۰ | `application/json` | ۱۲ کلید: `{status, traffic_mode:"blocked", session_proven:false, secrets_stored:false, detail, browser{open,pid,url,profile_kept}, last_verify:{}` (پرسشی انجام نشده ⇒ بدنهٔ خالی، نه ادعا)`, host_roles{auth,ui,api,evidence}, allowed_hosts[۳], login_hosts_configured[۳], login_host_blocked_reason:"", states_supported[۴]}` | VERIFIED |
| `/api/execution/session` | POST | ۲۰۰ | `application/json` | ردِ بک‌اند باِ آداپتورِ بدل: `{status:"error", code:"UNSUPPORTED", detail:"آداپتورِ فعال token نمی‌پذیرد (adapter=mock)", session{…}}` — نشانی هیچ‌جا ذخیره نشد | VERIFIED |
| `/api/execution/session` | DELETE | ۲۰۰ | `application/json` | `{status:"success", live:false, confirmations_voided:<number>, session{state:"disconnected", proven:false, …}}` | VERIFIED |

## ۲) سه حالتِ «هیچ ردیفی نیست» باِ هم یکی نیستند

| `status` | `rows` | معنایِ دقیق | چه‌وقت می‌افتَد |
| --- | --- | --- | --- |
| `blocked` | `null` | ترافیک ازِ این پروسه بیرون نمی‌رود | آداپتور غیرِ easytrader، یا تنظیمِ مؤثر ترافیک را نبسته |
| `unverified_session` | `null` | ترافیک باز است ولی نشستی درِ حافظه نیست (یا تأیید نشده) | بی‌`has_token` یا بی‌`session_proven` |
| `no_source` | `null` | نشست تأیید شده، ولی *هیچِ مسیرِ مستندِ خواندنی* برایِ دارایی‌ها نداریم | `capabilities.balances=false` |
| `error` | `null` | پرسش انجام شد و پاسخِ معنادار نداد | استثنایِ آداپتور |
| `success` / `cached` | `[]` یا ردیف‌ها | «خالی» یعنی کارگزاری ردیفی نداد — تنها حالتی که عدد معنا دارد | `get_balances()` مقدارِ واقعی بدهد |

`rows=null` هرگز «صفر ردیف» نیست؛ رابط (`SarkhatiConnectionCard`) عدد را فقط وقتی
می‌نویسد که `Array.isArray(rows)` باشد. گاردِ `dev/broker_connect_v1120.py` بندِ ۷
و ۹ همین را می‌سنجد («پرتفوی بی‌منبع ردیفِ خالی یا صفر نمی‌سازد»).

## ۳) سمتِ کارگزاری: آنچه دیده نشده

| پرسش | رأی | شاهد / نبودِ شاهد |
| --- | --- | --- |
| نشانیِ واقعیِ دارایی‌ها/موجودی درِ EasyTrader | **NO_SOURCE** | swagger و openapi → ۴۰۳؛ درِ پنج مخزنِ بررسی‌شده هیچ مسیرِ مستندِ «balances» نیست؛ `execution_easytrader.get_balances()` عمداً `None` برمی‌گرداند (`execution_easytrader.py:1292`) و `capabilities.balances=false` درِ هر سه جدولِ `NO_CAPS` / `PROTOCOL_CAPS` / `_READ_ONLY_CAPS` (`execution_easytrader.py:571-582`) |
| پاسخِ `portfolio` باِ نشستِ تأییدشده | **NOT_OBSERVED** | تا امروز هیچ نشستِ واقعیِ مفید درِ این ماشین ثبت نشده (احراز هویت فقط دستی و باِ خودِ مالک) |
| آیا `portfolio` درِ حالتِ `unverified_session` یا `no_source` پرسشی به کارگزاری می‌فرستَد؟ | **نه — VERIFIED** | `api/execution.py:904-957` پیشِ هر فراخوانی برمی‌گردد؛ سه GETِ پی‌درپی درِ همین سنجش بدنه‌هایِ عیناً یکسان داد (`docs/trading/PORTFOLIO-CONTRACT-CAPTURE-2026-10-18.json`)؛ و آزمونِ رابط «بازکردنِ فرم فقط GETهایِ خودیِ برنامه است» درِ `sarkhati-session-form.spec.tsx` |
| تازگیِ داده (`as_of`) | **NOT_OBSERVED** | تا `status` غیرِ `success` باشد `as_of=null` است؛ یعنی هیچ برچسبِ زمانی جعل نمی‌شود |

## ۴) پاک‌سازی

خروجیِ بایگانی‌شده فقط این‌ها را دارد: متد، آدرس، وضعیت HTTP، `content-type`، نامِ
کلیدها و *نوع* مقدارها (`string(len=…)`, `null`, `bool(…)`, `number`, `object{…}`,
`array(n x …)`). هیچ کوکی، هیچ توکن، هیچ نشانیِ شناساییِ شخصی و هیچ مقدارِ مالیِ
خامی درِ آن نیست. نشانیِ آزمونیِ این سنجش (`BORS-CONTRACT-PROBE-NOT-A-REAL-SESSION`)
درِ هیچ پاسخِ `/session`، `/portfolio` یا `/config` بازنگشت — پاسخ‌ها یا `rows:null`
و یا علّتِ رد می‌دهند، هرگز نشانی. اگر بعداً HARِ پاک‌شده‌ای برسد، همان جدولِ §۱
باِ ستونِ «مشاهده شد / مشاهده نشد» تازه می‌شود — نه باِ عددِ تازه.

## ۵) بازمانده‌ها (رأیِ مالک لازم ندارد، فقط ثبتِ واقع)

1. تا نشستِ واقعی گرفته نشود، `/portfolio` هیچ‌وقت ازِ این سه حالتِ بیرون نمی‌آید.
2. `no_source` یک انتخابِ عمدیِ مهندسی است، نه باگ: عددِ ساخته‌شده ازِ رتبه‌بندیِ
   کارگزاری بدتر از «نداریم» است.
3. تنها راهِ عوض‌کردنِ رأیِ §۳، یکِ شاهدِ بیرونی است: سندِ منتشرشدۀ خودِ کارگزاری،
   یا یکِ HARِ پاک‌شده ازِ نشستِ واقعیِ مالک.
