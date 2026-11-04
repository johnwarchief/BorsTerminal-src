# مشخصات: S4b — بستن دیدنی بنیادی (تنظیمات آستانه، P/NAV، تفکیک N/A)

- **تاریخ:** ۲۰۲۶-۱۱-۰۴
- **شاخه:** `integration/4axes-main-2026-11-03`
- **وضعیت:** دامنه و معماری پیشنهادی توسط مالک در ۲۰۲۶-۱۱-۰۴ تأیید شد؛ این سند مشخصات اجرایی همان تصمیم است.
- **مبنا:** `docs/BorsTerminal-Desktop-Migration-Decisions.md` (کل سند، به‌ویژه §۴، §۹، §۱۲.۴، §۱۲.۱۹، §۱۲.۲۴، §۱۲.۲۶، §۱۲.۳۰، §۱۲.۳۸.۱ بند ۱۵، §۱۲.۳۹.۱ بند ۱ و ۸)، `docs/superpowers/specs/2026-11-04-fundamental-core-migration-design.md` (S4a)، و `docs/MIGRATION-REBUILD-PLAN-2026-10-27.md` (S4).
- **تصمیم مالک در همین نشست:** بعد از تکمیل S4b، برگردیم به **تکنیکال** و بعد **بازار**.
- **یادداشت شواهد:** نسخهٔ فایل تصمیمات در این checkout در §۱۲.۳۹.۲ تمام می‌شود و بخش §۱۳ در آن وجود ندارد؛ ارجاع پلن ری‌بیلد به §۱۳ در این checkout کهنه است. تأییدهای این برش، پیام‌های مالک در ۲۰۲۶-۱۱-۰۴ هستند.

---

## ۱. هدف

بستن قابل‌دیدن بخش بنیادی در `frontend-v2` بدون تغییر فرمول‌ها یا قواعد FTS:

1. **تنظیمات آستانه‌های بنیادی** در همان صفحه (جدول و نمای نماد): خواندن، ویرایش، ذخیره، بازگردانی، و اعمال قابل‌سنجش روی جدول و کارت.
2. **پنل P/NAV** برای هلدینگ/سرمایه‌گذاری و بانک: به‌جای عدد ساختگی، وضعیت صریح N/A و علت طبقه.
3. **تثبیت تفکیک N/A از رد** در جدول غربالگری و فیلتر «حذف بر اساس شاخص» مطابق رفتار اپ قدیم.
4. **حفظ مالکیت نوشتن و منبع حقیقت:** تنظیمات فقط از مسیر موجود `/api/fts/config` نوشته می‌شود؛ جدول و کارت هر دو از همان فایل/آستانه می‌خوانند.

## ۲. شواهد وضعیت فعلی

| ادعا | جا |
|---|---|
| v2 جدول و کارت بنیادی دارد؛ تنظیمات و P/NAV ندارد | `frontend-v2/src/features/fundamental/**` |
| اپ قدیم دراور تنظیمات FTS و پنل `holding-pnav-panel` دارد | `frontend/src/features/fundamental/ui/FtsSettingsDrawer.tsx`، `frontend/src/features/fundamental/routes/FundamentalPage.tsx:337` |
| تنظیمات در پایتون نوشته می‌شود و Go فقط می‌خواند | `api/market.py:1760,1788`، `backend-go/internal/fundamental/config.go:145` |
| کش اسکرینر پایتون کلید آستانه‌ها را اعتبارسنجی می‌کند | `api/screener.py:424-472` |
| کش فعلی نمونه ۹۲۲ ردیف و `i*_na` کامل دارد | `D:/BorsTerminal-tmp/4axes-data/.screener_cache.json` |
| کارت Go `profile.kind`، `profile.margin_class` و `indicators.4.na/exempt` را برمی‌گرداند | `backend-go/internal/fundamental/testdata/golden/card_holding/body.json` |
| جدول v2 chipهای pass/fail/na/unknown را دارد ولی فیلتر حذف ندارد | `frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx` |

## ۳. معماری و مسیر داده

### ۳.۱. جدول: پایتون به‌صورت موقت

- `/api/screener` در `frontend-v2/vite.config.ts` از `goProxy` خارج می‌شود و به بک‌اند پایتون می‌رود.
- دلیل: کش پایتون `payload_key = cfg_hash#vAPP_VERSION` را اعتبارسنجی می‌کند؛ پس بعد از تغییر آستانه، جدول با آستانهٔ تازه و `i*_na` کامل ساخته می‌شود. Go فعلی کلید کش را اعتبارسنجی نمی‌کند و می‌تواند ۱۲ ساعت دادهٔ کهنه بدهد.
- این یک **مرز سازگاری موقتِ صریح** است (§۱۲.۳۰): در UI ادعای Go-native نمی‌شود، `as_of` نمایش داده می‌شود، و S4c با materializer جدول را به Go برمی‌گرداند.
- هیچ fallback خاموشی ساخته نمی‌شود؛ منبع جدول در این برش پایتون است.

### ۳.۲. کارت: Go

- `/api/fundamental/{symbol}` همان مسیر Go می‌ماند.
- `LoadFtsConfig` در هر درخواست فایل `fts_thresholds.json` را می‌خواند؛ بنابراین آستانهٔ تازه بلافاصله روی کارت اثر می‌گذارد، به‌شرط آنکه Go و پایتون به یک پوشهٔ داده اشاره کنند.
- آزمون پذیرش باید همین اشتراک پوشه را اثبات کند؛ اگر دو پوشه جدا باشند، تنظیمات نباید موفق گزارش شود.

### ۳.۳. تنظیمات: پایتون، یک نویسنده

- `GET/POST /api/fts/config` بدون تغییر در پایتون استفاده می‌شود.
- تنها نویسندهٔ `fts_thresholds.json` همان endpoint است؛ Go فقط می‌خواند (§۱۲.۳۹.۱ بند ۸).
- ذخیره **پیکربندی کامل** است: GET فعلی + تغییرات بنیادی. کلیدهای ساعت‌شنی (`hourglass_rsi_period`، `hourglass_rsi_oversold`، `hourglass_ma52_position`) دست‌نخورده می‌مانند.
- بازگردانی فقط آستانه‌های بنیادی را به پیش‌فرض FTS برمی‌گرداند؛ ساعت‌شنی عمداً دست نمی‌خورد (در فاز تکنیکال تنظیم می‌شود).

### ۳.۴. هم‌ارزی جدول و کارت پس از ذخیره

پذیرش این برش شامل یک آزمون سازگاری است (§۱۲.۳۹.۱ بند ۱):

1. `growth_min` را از ۴۰ به ۶۰ تغییر بده.
2. `GET /api/screener` پایتون و `GET /api/fundamental/{symbol}` Go را برای ۵ نماد نمونه بخوان.
3. آستانه/پرچم/امتیازها باید با هم سازگار باشند؛ اختلاف فقط اگر در S4a به‌عنوان تفاوت تعریف‌شده ثبت شده باشد.

## ۴. قراردادها و UI

### ۴.۱. `useFtsConfig`

- `GET /api/fts/config` با اسکیمای کامل (کپی قرارداد اپ قدیم) و `POST` با `requestJson`.
- خطای GET: پیام «تنظیمات خوانده نشد» + تلاش دوباره؛ پیش‌فرض‌ها به‌عنوان مقدار ذخیره‌شده نمایش داده نمی‌شوند.
- خطای POST: نمایش `message` و `errors` سرور؛ پیام موفقیت فقط با `status === 'success'`.
- بعد از موفقیت: باطل‌کردن `screener-core`، `fts-card` و `fts-config`.

### ۴.۲. دراور تنظیمات

- دکمهٔ «تنظیمات» در نوار جدول و سربرگ نمای نماد.
- پنل از نوع dialog با backdrop، Escape، تلهٔ فوکوس، بازگردانی فوکوس و `aria-modal`؛ در RTL از سمت راست.
- سه بخش:
  1. **آستانه‌های پنج شاخص:** رشد ریالی (`growth_min`)، هدف رشد (`v10_monetary_growth_min`)، مبنای تورم (`v10_inflation_basis`)، الزام رشد تولیدی (`v10_volume_breadth_min` روشن/خاموش)، الزام EPS سه‌ساله (`v10_eps_years` ۳/۱)، کف حاشیهٔ ناخالص (`margin_min`)، کف فروش/ارزش بازار (`v10_sales_to_mcap_min`)، پوشش سود ناخالص (`profit_potential_min`).
  2. **دروازه‌های سخت:** حالت نرخ‌گذاری (`industry_mode`)، حذف تعلیق (`suspended_max_stale_sessions`)، وتوی بیمه (`reject_insurance`)، N/A هلدینگ (`holdings_sales_na`)، استثنای دارو (`pharma_margin_exempt_min`)، حذف بازار پایه (`exclude_base_market`).
  3. **فیلتر حذف بر اساس شاخص:** `1a`، `1b`، `2`، `3`، `4`، `5`؛ `1b` صادقانه هیچ ردیفی را حذف نمی‌کند و متن علت را نشان می‌دهد.
- پیش‌فرض‌ها و حدود از قرارداد موجود: `growth_min=40`، `v10_monetary_growth_min=60`، `v10_inflation_basis=60`، `v10_volume_breadth_min=0.6`، `v10_eps_years=3`، `margin_min=20`، `margin_optimal=max(margin_min,30)`، `v10_sales_to_mcap_min=0.33`، `profit_potential_min=40`، `industry_mode='Exclude_Mandatory_Pricing'`، `mandatory_sectors=['خودرو','نیروگاه','لاستیک']`، `reject_insurance=true`، `suspended_max_stale_sessions=3`، `holdings_sales_na=true`، `pharma_margin_exempt_min=0`، `exclude_base_market=true`.
- هیچ آستانه یا فرمول تازه‌ای ساخته نمی‌شود؛ فقط همان کلیدهای موجود (§۱۲.۳۸.۱ بند ۱۵).

### ۴.۳. P/NAV و N/A

- `isHolding` از `card.profile.kind === 'holding'` یا `indicators.4.na/exempt`؛ fallback نام/صنعت برای کارت بدون profile.
- `isBankLike` از `profile.margin_class === 'bank'` یا برچسب/صنعت بانک.
- برای هلدینگ/بانک، پنل «P/E صنعت» جای خود را به `holding-pnav-panel` می‌دهد:
  - هلدینگ: «N/A — قابل ارزیابی نیست؛ در کدال ارزش خالص دارایی (NAV) منتشر نشده؛ P/NAV محاسبه نمی‌شود و جای آن عددی گذاشته نمی‌شود.»
  - بانک: «N/A — قابل ارزیابی نیست؛ P/NAV برای این طبقه تعریف نشده است.»
  - هیچ نسبت جانشینی (مثل EPS) ساخته نمی‌شود.
- برای صندوق/`applicable === false`: پیام «FTS ندارد» نه پنل P/NAV.
- برای نماد عادی: پنل P/E صنعت بدون تغییر.
- نشان طبقه در سربرگ: «هلدینگ / سرمایه‌گذاری» یا «بانک / مؤسسهٔ اعتباری».

### ۴.۴. جدول و فیلتر حذف

- `ScreenerCoreRow` فیلدهای لازم فیلتر را تایپ می‌کند: `rev_growth`، `eps_series`، `eps_years_required`، `eps_years_available`، `gross_margin`، `profit_potential_pct`، `sales_to_mcap`، `pricing_mode`، `i1a_pass`، `i1b_applicable`، `i1b_data_gap`.
- `rejectedFor(row, axis)`:
  - `1a`: `i1_pass === false` یا (`i1_pass == null && rev_growth == null`) → حذف.
  - `1b`: همیشه `null` (ستون در پاسخ نیست).
  - `2`: `i2_na === true` → `null`؛ `i2_pass === false` → حذف؛ تاریخچهٔ ناقص → حذف.
  - `3`: `i3_pass === false` یا (`i3_pass == null && gross_margin == null`) → حذف.
  - `4`: `i4_pass === false` یا (`i4_pass == null && profit_potential_pct == null && sales_to_mcap == null`) → حذف.
  - `5`: `i5_pass === false` یا `pricing_mode == null` → حذف.
- فیلترها در `localStorage` با کلید `fts:exclude-rejected-axes` نگه داشته می‌شوند؛ کلید `exclude_rejected_indicators` هم در payload ذخیره فرستاده می‌شود (اگر سرور آن را پذیرفت، ماندگاری سرور جایگزین می‌شود).
- جدول chip «حذف‌شده‌ها: N» و نام محورهای فعال را نشان می‌دهد؛ ردیف حذف‌شده هیچ حکم جعلی نمی‌سازد.
- chipهای pass/fail/na/unknown حفظ می‌شوند؛ `null` بدون `na=true` «نامشخص» است، نه «رد» (§۱۲.۲۴).

## ۵. فایل‌ها

| فایل | مسئولیت |
|---|---|
| `frontend-v2/src/features/fundamental/api/useFtsConfig.ts` | GET/POST، اسکیما، پیش‌فرض‌های بنیادی |
| `frontend-v2/src/features/fundamental/ui/FtsSettingsDrawer.tsx` | دراور + دکمه |
| `frontend-v2/src/features/fundamental/lib/exclusionFilter.ts` | پورت فیلتر حذف |
| `frontend-v2/src/features/fundamental/lib/assetScope.ts` | تشخیص هلدینگ/بانک |
| `frontend-v2/src/features/fundamental/ui/HoldingNavPanel.tsx` | پنل N/A |
| `frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx` | دکمه، نشان، پنل، پیام صندوق |
| `frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx` | دکمه، فیلتر حذف، شمار |
| `frontend-v2/src/features/fundamental/api/useFtsCard.ts` | تایپ `profile` و `na/exempt` |
| `frontend-v2/src/features/fundamental/api/useScreenerCore.ts` | تایپ فیلدهای فیلتر |
| `frontend-v2/vite.config.ts` | خارج‌کردن `/api/screener` از `goProxy` |
| `frontend-v2/src/__tests__/fundamental-settings.spec.tsx` | تست تنظیمات |
| `frontend-v2/src/__tests__/fundamental-holding.spec.tsx` | تست P/NAV |
| `frontend-v2/src/__tests__/fundamental-table-na.spec.tsx` | تست N/A و فیلتر |

## ۶. حالت‌ها و خطاها

- **بارگذاری تنظیمات:** دکمه/دراور غیرفعال با متن «در حال خواندن تنظیمات…».
- **خطای خواندن:** پیام روشن + تلاش دوباره؛ هیچ پیش‌فرضی به‌جای مقدار ذخیره‌شده نمایش داده نمی‌شود.
- **خطای ذخیره:** `message` و `errors` سرور؛ مقدار روی فرم می‌ماند تا کاربر اصلاح کند.
- **موفقیت:** فقط بعد از پاسخ `status: success`؛ پیام «تنظیمات ذخیره شد» + باطل‌شدن کش‌ها.
- **جدول در حال بازسازی:** اگر اولین درخواست پس از تغییر آستانه طول کشید، همان حالت بارگذاری موجود با متن «جدول با آستانه‌های تازه در حال بازسازی…» نمایش داده می‌شود؛ دادهٔ قدیمی به‌عنوان تازه جا زده نمی‌شود.
- **نماد بدون کارت:** همان پیام موجود؛ پنل P/NAV ساخته نمی‌شود.
- **هلدینگ/بانک:** N/A صریح؛ هیچ عددی جای NAV گذاشته نمی‌شود.
- **صندوق:** «FTS ندارد»؛ نه N/A هلدینگ.

## ۷. پذیرش و آزمون

1. `npm run typecheck` و `npm test` در `frontend-v2` سبز؛ تست‌های جدید سه فایل بالا.
2. **تنظیمات:** بازکردن از جدول و نمای نماد؛ خواندن مقدار فعلی؛ تغییر `growth_min` و ذخیره؛ payload کامل و حفظ کلیدهای ساعت‌شنی؛ خطای سرور؛ بازگردانی بنیادی بدون تغییر ساعت‌شنی.
3. **اثر واقعی:** پس از ذخیره، جدول پایتون و کارت Go برای ۵ نماد نمونه با آستانهٔ تازه سازگار باشند؛ اگر Go و پایتون پوشهٔ دادهٔ یکسان نداشتند، آزمون باید شکست بخورد و موفقیت گزارش نشود.
4. **P/NAV:** هلدینگ (نماد نمونه ویسا)، بانک (وبملت)، صندوق و نماد عادی؛ وجود/نبود `holding-pnav-panel`؛ نبود هر عدد P/NAV؛ متن درست هر طبقه.
5. **N/A:** ردیف‌های pass/fail/na/unknown؛ `null` بدون `na` هرگز «رد» نشود؛ فیلتر حذف فقط ردیف‌های مردود/ناقص را حذف کند؛ `1b` هیچ ردیفی را حذف نکند.
6. **زنده:** وضوح ۱۳۶۶×۷۶۸ و ۱۹۲۰×۱۰۸۰؛ اسکرین‌شات جدول، دراور، نمای هلدینگ و بانک؛ بدون خطای کنسول؛ دسترس‌پذیری Escape/فوکوس/backdrop.
7. **قیدها:** هیچ تغییر فرمول/آستانهٔ FTS، هیچ جدول تازه، هیچ نوشتن در `market.db`، فقط یک حلقهٔ زندهٔ TSETMC؛ آزمون‌ها روی دادهٔ جدا/`BORS_NO_FETCH_LOOPS=1`.
8. **سازگاری:** `as_of` جدول و `freshness` کارت نمایش داده شوند؛ دادهٔ کهنه زنده معرفی نشود.

## ۸. ریسک‌ها

| ریسک | کاهش |
|---|---|
| کندی اولین اسکرینر پس از تغییر آستانه | حالت بارگذاری صریح؛ گرم‌کردن کش در آزمون؛ عدم نمایش دادهٔ کهنه به‌عنوان تازه |
| اختلاف پوشهٔ داده Go و پایتون | آزمون مشترک؛ شکست صریح اگر کارت آستانهٔ تازه را نبیند |
| پست ناقص و بازنشانی کلیدهای ساعت‌شنی | ارسال پیکربندی کامل + تست |
| دو منبع حقیقت جدول/کارت | هر دو از یک `fts_thresholds.json`؛ آزمون سازگاری ۵ نماد |
| برگشت موقت جدول به پایتون | ثبت صریح در سند/پذیرش؛ S4c با materializer؛ بدون fallback خاموش |
| فیلتر حذف بیش از حد | `1b` بدون حذف؛ `null` بدون `na` نامشخص؛ تست‌های مرزی |
| دسترسی‌پذیری دراور | Escape/فوکوس/backdrop/aria؛ تست زنده |

## ۹. خارج از دامنه (S4c)

- materializer مستقل Go برای `fts_results` (۲۷ ستون + `i*_na`/دلایل).
- پورت `GET/POST /api/fts/config` به Go با پاریتی اعتبارسنجی.
- برگرداندن جدول به Go با اعتبارسنجی کلید کش و مالکیت نوشتن واحد.
- تنظیمات ساعت‌شنی در صفحهٔ تکنیکال؛ این در فاز بعدی (تکنیکال) انجام می‌شود.
- مبلغ DPS تا وقتی `stock_dividend_events` داده دارد.

## ۱۰. بعد از S4b

طبق تصمیم مالک (۲۰۲۶-۱۱-۰۴): بازگشت به **تکنیکال** و بعد **بازار**. جزئیات آن در اسپک/پلن جداگانه همان فاز نوشته می‌شود.
