# EasyTrader Live-Session Reference Audit — Round 11A

**زمانِ بررسی:** ۲۰۲۶-۱۰-۲۱، نشستِ موجودِ مالک در `https://d.easytrader.ir/`  
**روش:** مرورگرِ مجازِ موجود + درخواست‌هایِ **GET فقط‌خواندنی** + بررسیِ ایستایِ
bundle اول‌طرفی. هیچ POST، لغو، تغییر فرم یا ورودِ تازه انجام نشد.  
**محرمانگی:** هیچ token/Cookie/Authorization یا مقدارِ مالیِ حساب در این
سند، log یا خروجیِ ابزار نوشته نشد؛ فقط status، کلیدها، نوع‌ها و شمارش.

## ۰) وضعیتِ نشست

| مورد | نتیجه |
| --- | --- |
| URL | `https://d.easytrader.ir/` |
| OIDC در sessionStorage | موجود (`has_oidc=true`)؛ مقدار خوانده/ثبت نشد |
| CAPTCHA/MFA | هیچ تلاشی برایِ دورزدن انجام نشد |
| حسابِ دیگر/پروفایلِ دیگر | استفاده نشد |

سطح: **READ_ONLY_BEHAVIOR_VERIFIED** برایِ درخواست‌هایِ زیر.

## ۱) شواهدِ شبکه (فقط schema)

| منبع | Status | شکل | شمارش | نتیجه |
| --- | --- | --- | --- | --- |
| `GET /core/api/order` | ۲۰۰ | `{orders, algoSuffixCharacters}` | ۰ سفارش | هیچ سفارشِ موجودی برایِ آزمونِ صف نیست |
| `GET /easy/api/MarketWatch` | ۲۰۰ | array از دسته‌ها | ۲ دسته | کلیدهایِ دسته شاملِ `customerIsin` است؛ آداپتور آن را حذف می‌کند |
| `GET /assetmodule/api/performance` | ۲۰۰ | `{items}` | ۱۱ دارایی | هیچ `quantity/free_quantity/sellable_quantity` ندارد |
| `GET /easy/api/money` | ۲۰۰ | object | — | `blockT2` هم در schema هست؛ قبلاً در parser نبود |
| `GET /ms/api/MarketSheet/order-place` | اجرا نشد | — | — | بی سفارشِ موجود، `order-id` معتبری برایِ آزمون نبود |

**اثر:** `blockT2` به `get_money`/`get_balances` اضافه شد. شاهدِ تازه‌ای برایِ
تعدادِ قابل‌فروشِ سهام پیدا نشد؛ فروش همچنان `sellable=UNKNOWN` و مسدود است.

## ۲) سفارش‌هایِ موجود

پاسخ `GET /core/api/order` در این نشست خالی بود (۰ سفارش). بنابراین:
- فیلدهایِ واقعیِ یک ردیفِ سفارش در این نشست دیده نشد؛ نوع‌ها از کدِ
  اول‌طرفی/مرجعِ Reza (`orderStateStr`, `executedQuantity`, `symbolIsin`, ...)
  می‌آیند و در سطحِ **static reference** می‌مانند.
- آزمونِ عملیِ `orderPlace/volumeAhead` ممکن نبود؛ این مسیر **UNVERIFIED** است.
- `reconcile` فعلی با فهرستِ خالی باید UNKNOWN بماند، نه «ردشده»؛ گاردها این را
  می‌سنجند.

## ۳) فرمِ ثبت سفارش (کدِ اول‌طرفی + مشاهدهٔ ایستا)

از `main-XW5OZAYT.js` (کدِ اول‌طرفی، ۲۰۲۶-۱۰-۲۱):

- فیلدهایِ فرم: `isin`, `side`, `quantity`, `price`, `validity`.
- اعتبارسنجی: `quantity ≥ 1`, `price ≥ 0.01`, سمت فقط Buy/Sell.
- `generateOrderForSubmission`:
  `price`, `quantity`, `side`, `validityType`, `createDateTime`, `commission`,
  `symbolIsin`, `symbolName`, `validityDate`, `orderModelType`, `totalValue`.
- `prepareSendingOrder` سپس `orderFrom=34` (سهام، دسکتاپ) و برایِ Week/Month
  `validityType` را به `ValidToDate` تبدیل می‌کند.
- خطایِ ۴۲۹ در کلاینت به «۱۰۰۰ سفارش در ساعت» اشاره دارد (پیامِ کلاینت؛
  آزمونِ سرور نیست).
- `symbolIsin` شناسهٔ سفارش است؛ `symbolName` فقط برچسب.

سطح: **FIRST_PARTY_CLIENT_CODE_OBSERVED**؛
**WRITE_CONTRACT_STATICALLY_RECONSTRUCTED**.  
**WRITE_PAYLOAD_OBSERVED_PRE_DISPATCH** انجام نشد، چون مکانیزمِ abortِ
قابل‌اعتماد پیش از dispatch در این بررسی فراهم نشد؛ دکمهٔ ثبت زده نشد.

## ۴) دیده‌بان و پرتفوی

- دیده‌بان: دو دسته، ساختارِ `watchCategorySymbols`؛ کلیدِ `customerIsin` در
  پاسخ هست، ولی `get_watchlist` عمداً آن را در خروجی نمی‌گذارد.
- پرتفوی: ۱۱ ردیف؛ فیلدهایِ `asset`, میانگین‌ها، DPS/سود و حجم‌هایِ خرید/فروش.
  **هیچ فیلدِ تعداد/آزاد/قابل‌فروش ندارد.** وجودِ `bonusShareVolume` یا
  `totalBoughtVolume` دلیلِ تعدادِ آزاد نیست و به‌عنوانِ sellable استفاده نشد.
- قدرت خرید: schema شاملِ `t0/t1/t2`, `buyPowerT0/T1/T2`, `block`, `blockT2`,
  `credit`, `avandCredit`, …؛ فرمولِ Round 10 حفظ شد.

## ۵) مقایسه با شش مرجع

| یافته | منبع | سطح | اثر |
| --- | --- | --- | --- |
| `POST /core/api/v2/order` + `{order}` | m-fazel + Reza + اول‌طرفی | FIRST_PARTY_CLIENT_CODE_OBSERVED | تأییدِ قراردادِ ایستا |
| minimal ۷ فیلد | m-fazel | static reference | فیلدهایِ ما شاملِ آن‌هاست؛ گارد ۳۶/۳۶ |
| `commission:0.0012` ثابت | Reza | static reference؛ ارزش/معنا تأییدنشده | عمداً حذف؛ مقدارِ ساختگی ساخته نشد |
| `totalValue` | اول‌طرفی | static reference | تا شاهدِ commission حذف |
| `GET /core/api/order` fields | Reza + اول‌طرفی | static reference | parser فعلی؛ live empty |
| queue path `/ms/.../order-place` | Reza | third-party hypothesis | مسیر حفظ، اما fallback حذف شد |
| `orderPlace<=1 = first` | Reza | third-party hypothesis | تفسیر نشد؛ `known` فقط با عدد |
| token cache on disk | Reza | security anti-pattern | کپی نشد؛ نشست فقط در حافظه |
| HEAD probe for latency | m-fazel | third-party assumption | ادعایِ latency POST نشد |
| Selenium/xpath + CAPTCHA | Hossein/Sajad | UI automation | Reject؛ هیچ کد/روش ورود کپی نشد |

## ۶) تغییراتِ واقعیِ BorsTerminal (نه صرفاً گزارش)

| تغییر | فایل | تست |
| --- | --- | --- |
| `blockT2` در raw/balances | `execution_easytrader.py` | `execution_account_sources_v1146` ۲۵/۲۵ |
| حذفِ fallbackِ ردیفِ اولِ صف | `execution_easytrader.py` | `easytrader_adapter_v1113` ۱۶۳/۱۶۳ |
| گاردِ تطبیق با فیلدهایِ m-fazel/Reza | `dev/execution_write_contract_v1147.py` | ۳۶/۳۶ |
| گزارش‌هایِ audit | `docs/…` | — |

## ۷) آنچه هنوز تأییدنشده / آزمونِ لازم

1. **queue semantics** با یک سفارشِ واقعی: فقط GET با `order-id`؛ تا آن زمان
   `orderPlace/volumeAhead` خام و `UNVERIFIED`.
2. **ترتیبِ فهرستِ سفارش‌ها** و رفتارِ اجرایِ جزئی/رد در یک نشستِ واقعی.
3. **قرارداد نوشتنِ عملیاتی**: نیاز به یک POSTِ واقعی با مجوزِ صریحِ مالک و
   مکانیزمِ توقف/مشاهدهٔ ایمن؛ در این راند انجام نشد.
4. **منبعِ sellable سهام**: هیچ مسیرِ معتبری دیده نشد؛ فروش مسدود می‌ماند.
5. **commission/totalValue**: معنایِ سرور و مقدارِ معتبر؛ تا شاهد حذف.
6. **idempotency**: کلیدِ رسمیِ سرور دیده نشد؛ قفلِ فعلی محلی/دفتری است.

## ۸) دیتابیس و خط قرمزها

fingerprintِ عملیاتی در ابتدا و پس از probeهایِ فقط‌خواندنیِ این راند یکسان بود:
`market.db` = `5a9117aa…135bea3` و `user.db` = `381736f1…c74500e`.
گیتِ کاملِ Round 11A از یک **کپیِ موقت** از repo و `market.db` اجرا شد:
۱۴۳ counted، ۲۷ فقط-exit-code، ۲ SKIP، ۰ FAIL. fingerprintِ عملیاتی پس از
گیت هم همان دو hash بالا ماند.

- هیچ POST سفارش/لغو/تغییر انجام نشد.
- هیچ token/Cookie/پاسخِ خام حاویِ حساب ذخیره یا چاپ نشد.
- هیچ CAPTCHA/MFA دور زده نشد.
- هیچ دادهٔ حساب به fixture تبدیل نشد.

## ۹) IPO — مشاهدهٔ نشست و آزمون فرم (Round 12)

در نشستِ مجازِ ۲۰۲۶-۱۰-۲۱، `GET /ipo/api/ipo` پاسخِ ۲۰۰ با یک عرضهٔ عمومی
داد: نماد **سیمکات**، ISIN `IRO3SIMC0001`، بازهٔ `2026-10-21 12:15–14:15`،
قیمتِ ثابت `45,840` و حداکثرِ تعداد `130`؛ `isOfflineOrderAvailable=false` و
`ipoStatus=4` (معنای enum تأییدنشده). این داده از API اول‌طرفیِ کارگزاری است،
نه اعلان رسمی بورس؛ برای تاریخِ شنبه `2026-10-24` عرضه‌ای در این منبع دیده نشد.

در رابطِ واقعی، صفحهٔ عرضه باز و فرمِ خرید باز شد؛ `#price` و `#quantity`
موجودند و دکمهٔ نهایی «ارسال خرید» است. مقدارهای `45,840` و `10` در فرم
نشستند و دکمه فعال ماند؛ مقدارهای `0` و `131` هم دکمه را غیرفعال نکردند.
**دکمهٔ نهایی کلیک نشد**، چون abortِ قابل‌اثبات پیش از dispatch فراهم نشد.
پس اعتبارسنجیِ نهایی، payload و نتیجهٔ سفارش در سطحِ UI **مشاهده نشده**اند.

| مورد | نتیجه |
| --- | --- |
| فرم باز و فیلدها | PASS |
| پرکردن مقدارهایِ معتبر بدون ارسال | PASS |
| اعتبارسنجیِ مقدارِ صفر/بیش از سقف در دکمه | NOT_RUN (دکمه فعال بود؛ کلیک نشد) |
| preflight خرید IPO | BLOCKED_CONFIGURATION: mapping محلی و بودجه/مجوز صریحِ IPO نیست |
| ارسال/شناسه/صف/اجرا | NOT_RUN / UNVERIFIED — هیچ سفارشی ارسال نشد |
