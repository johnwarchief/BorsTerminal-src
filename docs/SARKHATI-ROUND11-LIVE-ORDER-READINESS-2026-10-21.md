# Round 11 — آمادگیِ نخستین سفارشِ واقعی EasyTrader

**تاریخ:** ۲۰۲۶-۱۰-۲۱  
**حکم نهایی:** `PAPER_READY` برایِ چرخهٔ عمرِ شبیه‌سازی؛ برایِ Live فقط
`OWNER_APPROVAL_REQUIRED` نیست — قرارداد نوشتن هنوز `UNVERIFIED` عملیاتی است و
منبعِ تعدادِ قابل‌فروش برایِ سهام اثبات نشده. `live_enabled=false` و
`live_ready=false`.

## ۱) Git

| مورد | مقدار |
| --- | --- |
| شروع | شاخهٔ `mission/sarkhati-round10-watchlist-portfolio-2026-10-21` @ `9847f76873ae6dcf396f346cc0a2c0cefbd23da7` |
| شاخهٔ راند | `mission/sarkhati-round11-live-order-readiness-2026-10-21` |
| پایان | HEAD شاخهٔ مأموریت پس از کامیتِ همین سند (کدِ اجرا: `a9946e8b`) |
| main/tag/release | تغییر نکرد |
| Issue #10 | بررسی شد؛ roadmap باز است، مجوزِ Live نیست |

## ۲) قراردادِ نوشتنِ کشف‌شده

| مورد | مقدار | شاهد |
| --- | --- | --- |
| Method/Path | `POST /core/api/v2/order` | `createOrder()` در `main-XW5OZAYT.js` (کدِ اول‌طرفی) |
| Envelope | `{"order": {…}}` | همان تابع |
| Read-back | `GET /core/api/order` | `getOrders()` |
| Modify/Cancel | `PUT /core/api/v2/order` / `DELETE /core/api/v2/delete-order` | همان کلاینت |
| سطح | `WRITE_CONTRACT_STATICALLY_RECONSTRUCTED` | نه تأییدِ عملیاتی |

فیلدها، enumها و مواردِ تأییدنشده در
[`docs/execution/EASYTRADER-WRITE-CONTRACT.md`](execution/EASYTRADER-WRITE-CONTRACT.md)
آمده‌اند. خلاصه:

- `side`: `0=خرید`, `1=فروش`.
- `orderModelType=1` (oms)، `orderFrom=34` (OrbisDesktop سهام).
- `validityType=0` (Day) برایِ مسیرِ فعلی؛ `validityDate` برایِ Day حذف.
- `symbolIsin` هویتِ ابزار است، نه `ins_code`.
- `commission` و `totalValue` فیلدهایِ client-summary با معنایِ سرورِ
  تأییدنشده‌اند؛ تا منبعِ قابل‌دفاع نداریم فرستاده نمی‌شوند.
- پاسخِ `2xx + isSuccessful + id` فقط «ثبتِ درخواست» است؛ پذیرش/اجرا از
  `GET /core/api/order` و OMS خوانده می‌شود.

## ۳) قدرت خرید و تعداد قابل‌فروش

- قدرت خرید: `buyPowerT2 - credit - avandCredit`، واحدِ `IRR`؛ منبع
  `GET /easy/api/money`. در ترافیکِ فقط‌خواندنیِ ۲۰۲۶-۱۰-۲۱ دوباره دیده شد
  (HTTP 200)؛ مقدار در گزارش/تصویر ماسک است.
- تعداد/آزاد/قابل‌فروشِ **سهام**: در `GET /assetmodule/api/performance`
  وجود ندارد؛ ترافیکِ صفحهٔ پرتفوی تنها همین منبع را برایِ سبد نشان داد.
  `positionFreeQuantity` در کدِ اول‌طرفی مربوط به استراتژی‌هایِ **آپشن** است،
  نه سهام، و تعمیم داده نشد. نتیجه: پیش‌فرودِ فروش `sellable=UNKNOWN` و مسدود
  می‌ماند.

## ۴) خرید و فروش به تفکیک

| مسیر | وضعیت |
| --- | --- |
| خرید | داده/ریسک می‌تواند جدا سبز شود؛ نوشتن به‌دلیلِ قراردادِ بازسازی‌شده و نبودِ آزمونِ عملیاتی مسدود است |
| فروش | علاوه بر همان مانع، `sellable` هم `UNKNOWN` است ⇒ مسدود |
| Paper | چرخهٔ intent → preflight → paper broker → state/reconcile آزموده شده |
| Live | `live_enabled=false`، `live_ready=false`، بدونِ مجوزِ مالک |

## ۵) تغییراتِ هسته

- `execution_write_contract.py` (تازه): تنها سازندهٔ بدنهٔ `{order: …}`،
  فیلدهایِ اجباری/اختیاری، enumها و گزارشِ منشأ؛ بدونِ network.
- `execution_easytrader.py`: payload به همین قرارداد وصل شد؛
  `request_registered` در verdict؛ ثبتِ «ثبت شد، نه پذیرفته شد».
- `execution_readiness.py` (تازه): دروازهٔ متمرکزِ ۱۲ شرطی، با تفکیکِ
  `data_risk_ready` از `live_ready`.
- `api/execution.py`: `GET /api/execution/readiness` (فقط‌خواندنی).
- `dev/execution_write_contract_v1147.py` (تازه): گاردِ قرارداد/readiness.
- Frontend: `useExecutionReadiness`، `SarkhatiReadinessCard` و نمایش در
  پنلِ اتصال؛ بدونِ بازطراحیِ گسترده.
- هیچ dependency تازه‌ای اضافه نشد.

## ۶) دروازهٔ آمادگی — وضعیتِ واقعی

| شرط | وضعیتِ endpoint | شاهد |
| --- | --- | --- |
| نشستِ فقط‌خواندنی | `BLOCKED` (در نمونهٔ dev بدونِ نشست) | `/api/execution/readiness` |
| نماد/ISIN | `NOT_RUN` تا انتخابِ نماد | endpoint |
| قدرت خرید | `BLOCKED` بدونِ نشست | endpoint |
| قیمت/مقدار | `NOT_RUN` تا preflight | endpoint |
| داده/ریسک | `NOT_RUN`/`BLOCKED` | preflight |
| قرارداد نوشتن | `UNVERIFIED` | `CONTRACT_STATE` |
| معنای پاسخ | `UNVERIFIED` | `2xx ≠ acceptance` |
| جلوگیری از تکرار | `NOT_RUN` در endpoint؛ گارد جدا `PASS` | `dev/execution_write_contract_v1147.py` |
| timeout/reconcile | `NOT_RUN` در endpoint؛ گارد جدا `PASS` | همان |
| ثبت/حفاظتِ راز | `NOT_RUN` در endpoint؛ گارد جدا `PASS` | `execution_account_sources_v1146` |
| تستِ قرارداد/چرخه | گارد `PASS` | `execution_write_contract_v1147` |
| گیتِ کامل | `143 counted / 27 silent / 2 skipped / ALL SUITES PASSED` | `dev/run_all_tests.py` |
| مجوزِ مالک | `REQUIRED` | هیچ مجوزی داده نشده |

`data_risk_ready` و `live_ready` از endpoint واقعی: `false` و `false`.

## ۷) آزمون‌ها

| آزمون | نتیجه |
| --- | --- |
| گاردِ قرارداد/readiness | ۳۳/۳۳ |
| اجرایِ مجددِ گاردهایِ execution/protocol/broker/paper | همه سبز (۵۰، ۱۶۲، ۲۴، ۳۳، ۴۷، ۳۸، ۵۴) |
| Frontend کامل | ۲۰۱ فایل، ۲۰۹۱ passed، ۵ skipped، ۰ failed |
| `npx tsc -b` | صفر خطا |
| `npm run build` | موفق |
| `dev/run_all_tests.py` | ۱۴۳ سوئیتِ شمرده، ۲۷ فقط-exit-code، ۲ SKIPِ fixture، ۰ FAIL، RC=0 |

## ۸) fingerprint دیتابیس — انحرافِ صریح

fingerprint **پیش از شروعِ راند ثبت نشد** (نقصِ رویه). در جریانِ اجرایِ یک
dev-server برایِ عکس‌ها، `market.db`/`user.db` لمس شدند. پس از توقف:

| نقطه | `market.db` | `user.db` |
| --- | --- | --- |
| پس از dev-sync، پیش از گیت | `dfbdc71ec3051482223bde8007365e5fc4a575ca1a92cfd208466c52110a18ac` | `9120a1b87b704a2b1b5951f4e6d1c1fe72aa0f0566cfe0e70580fe05b0038454` |
| پس از `run_all_tests` | `5a9117aaff1bf6c097a1618fbf1cb81ddff3868536d450003b7ad7fc9135bea3` | `381736f1d14c62e6fb57c3f7023d285fe63f4631d144dfbf427ede822c74500e` |

**هر دو fingerprint تغییر کردند.** هم dev-server و هم `run_all_tests` دیتابیسِ
عملیاتی را لمس کردند؛ این با شرطِ «fingerprint قبل/بعد یکسان» و «تستِ DB رویِ
کپیِ ایزوله» منطبق نیست و به‌عنوانِ انحرافِ جدی گزارش می‌شود. fingerprintِ
«قبل از شروعِ راند» ثبت نشده بود؛ بنابراین مقدارِ آغازینِ واقعی هم در دست
نیست. هیچ تلاشی برایِ پنهان‌کردن یا بازگردانیِ بدونِ شاهد انجام نشد.

## ۹) امنیت و عدمِ ارسالِ سفارش

- هیچ POSTِ سفارش/لغوِ واقعی در این راند اجرا نشد؛ `read-only` پیش از ترافیکِ
  نوشتن می‌ایستد و گارد با ترافیکِ بدل این را می‌سنجد.
- هیچ توکن/Cookie/رمز در گزارش، تصویر یا فایلِ خام نگه‌داری نشد؛ بدنه‌هایِ
  حساب در log نمی‌نشینند.
- `live_enabled=false` و `live_ready=false` در endpoint و UI.

## ۱۰) شواهدِ دیداری

این تصویرها از نمونهٔ dev برنامه (adapter=`mock`) گرفته شده‌اند؛ نشستِ واقعیِ
کارگزاری در آن نمونه فعال نبود. بنابراین وضعیتِ «نشست/قدرت خرید مسدود» و
«قرارداد تأییدنشده» را نشان می‌دهند، نه یک preflightِ سبزِ واقعی. شواهدِ
زندهٔ منبعِ حساب در Round 10 (۲۸ دیده‌بان، ۱۱ دارایی، قدرت خریدِ ماسک‌شده)
جدا و با برچسبِ خودش ثبت شده است. در `_audit/round11_visual/`:

- `01-readiness-blocked.png` — کارتِ آمادگی: Live بسته، داده/ریسک اجرا نشده،
  نوشتن تأییدنشده، مجوز لازم.
- `02-readiness-gates-contract.png` — دوازده دروازه + `POST /core/api/v2/order`
  و `WRITE_CONTRACT_STATICALLY_RECONSTRUCTED`.
- `03-buy-preflight-blocked.png` — پیش‌فرودِ واقعی در نمونهٔ dev (mock) با
  دلیلِ `NOT_ORDERABLE:broker_instrument` و «مسدود».
- `05-paper-bot.png` — رباتِ کاغذی، صفر موقعیت، مسیرِ Live بسته.

## ۱۱) آنچه هنوز حل نشده / اقدامِ مالک

1. **تأییدِ عملیاتیِ قرارداد نوشتن** با یک سفارشِ واقعیِ تحتِ نظارت و مجوزِ
   صریح؛ تا آن زمان `WRITE_CONTRACT_STATICALLY_RECONSTRUCTED` است.
2. **تعدادِ آزاد/قابل‌فروش سهام**: منبعِ معتبر پیدا نشد؛ فروش مسدود می‌ماند.
3. **قدرت خرید/نشستِ Live** در نمونهٔ آزمون حاضر نبود؛ با نشستِ مالک باید
   دوباره سنجیده شود.
4. **معنایِ سرور برایِ commission/totalValue/validityDate**؛ تا شاهد، حذف.
5. **fingerprint قبل/بعد**: قبل ثبت نشد و dev-sync انحراف ساخت (بندِ ۸).

## ۱۲) حکمِ نهایی

`PAPER_READY` برایِ چرخهٔ عمر و `OWNER_APPROVAL_REQUIRED` برایِ گامِ بعد؛
**همهٔ پیش‌نیازهایِ فنیِ Live هنوز گذرانده نشده‌اند** (قرارداد عملیاتی و
قابل‌فروش). هیچ ادعایِ پذیرش، اجرا یا ثبتِ سفارشِ واقعی مطرح نمی‌شود.
