# BorsTerminal — Market Status & Data Parity (Qoder 3)

> **این سند گزارشِ دورِ نخست است و اکنون با سندِ بستن جایگزین/تکمیل شده است:**
> `docs/MARKET-STATUS-DATA-PARITY-CLOSURE-QODER3-2026-10-20.md`.
> مواردی که در این سند «UNVERIFIED/باز» مانده‌اند (دسترسیِ Rahavard، ۲۲ ردیفِ اضافی، ثبتِ تست در runner و UI) در سندِ بستن با شواهد تازه تعیین تکلیف شده‌اند. اعدادِ تاریخیِ همین سند پاک نشده‌اند.

**تاریخ ممیزی:** 2026-10-20 (۱۴۰۵/۰۷/۲۸) · **شاخهٔ مأموریت:** `mission/market-status-data-parity-qoder3-2026-10-20`
**مبنای کار:** `origin/main` = `a14375c14cfb8fc616fb3312c685f8a5b0f79ab3`
**دامنه:** فقط دادهٔ جاری بازار، وضعیت بازار، فیلدهای تابلو/نماد، تازگی داده و مسیر API→UI. هیچ تغییر در Sarkhati، اجرای سفارش، FTS، تعدیل، عملکرد عمومی یا طراحی کلی UI انجام نشد.

> **خلاصهٔ حکم:** دو باگِ مستقیمِ داده در `test_tsetmc.py` پیدا و اصلاح شد: (۱) `p_last` معتبر منبع با `p_last` کهنهٔ بانک بازنویسی می‌شد و در نبود LAST از `py+pc` ساخته می‌شد؛ (۲) صفرِ معتبرِ حجم/ارزش/تعداد/تغییر در حالت بسته با عددِ نشست قبل عوض می‌شد. پس از اصلاح، تطبیق same-tick روی ۱۰ فیلد اصلی **۱۰۰٪** شد. یک اختلاف باقی‌مانده مربوط به کارتِ «قیمت وزنی ارزشی» است که تعریفِ مرجعش در اسناد باز و **نیازمند رأی مالک** است؛ عمداً فرمولش تغییر نکرد.

---

## ۱) وضعیت Git و SHA پایه

| مورد | مقدار |
|---|---|
| مخزن سورس | `https://github.com/johnwarchief/BorsTerminal-src` |
| clone محلی | `C:\Users\STU\Documents\Qoder\2026-10-19\0af806b0\BorsTerminal-Qoder3` (clone قبلی، main در `33f7d16f`) |
| worktree مأموریت | `C:\Users\STU\Documents\Qoder\2026-10-19\0af806b0\BorsTerminal-market-parity-q3` |
| SHA پایه | `a14375c14cfb8fc616fb3312c685f8a5b0f79ab3` (`origin/main`) |
| شاخه | `mission/market-status-data-parity-qoder3-2026-10-20` |
| `main` | دست‌نخورده؛ هیچ push/merge/tag انجام نشد |
| DB عملیاتی | دست‌نخورده؛ فقط کپیِ موقتِ `market.db` در `.q3-live-run` استفاده شد |
| دامنهٔ تغییر | `test_tsetmc.py`، تست مستقل، `docs/` و `reports/`؛ هیچ فایل frontend/API/اجرا تغییر نکرد |

در clone محلی، `main` عمداً به‌روزرسانی نشد؛ worktree مأموریت مستقیماً از `origin/main` ساخته شد تا `main` و کار Qoder 1/2 لمس نشود.

---

## ۲) بخش‌های بازار بررسی‌شده

1. تابلوی اصلی و Market Watch (`/api/market`، `market_watch`).
2. وضعیت بازار (`/api/mstat/phase`، `market_phase.py`).
3. شاخص‌های اصلی (`/api/mstat/indexcards` و `market_index`).
4. جزئیات قیمت/وضعیت معاملاتی یک نماد (نمونه‌های فولاد، خودرو، وبملت، آسيا3، آپ3).
5. حجم، ارزش و تعداد معاملات.
6. مظنه/عمق سفارش (منبع `blDs` و ستون‌های depth).
7. آمار حقیقی/حقوقی (حجم‌های `client_type` و تفکیک ارزش).
8. صنعت/گروه (نمونهٔ فولاد).
9. زمان آخرین به‌روزرسانی/تازگی (`market_watch.fetched_at`, `meta.last_sync`, `phase.data_updated_at`).
10. مرجع‌های TradersArena و Rahavard365 و TSETMC.

---

## ۳) فیلدها و مراجع واقعی

| لایه | منبع/مسیر |
|---|---|
| تابلو | `test_tsetmc._mw_row` ← TSETMC `ClosingPrice/GetMarketWatch`؛ نوشتن در `market_watch` |
| API | `api/market.py` → `/api/market` (فیلدهای `p_last`, `p_closing`, `price_yesterday`, `p_first`, `p_max`, `p_min`, `tmin`, `tmax`, `q_tot_tran`, `q_tot_cap`, `z_tot_tran`, `price_change`, `percent_*`, `row_h`) |
| وضعیت | `market_phase.py` با `market_index.market_state`/`marketActivityHEven` از `MarketData/GetMarketOverview` |
| شاخص | `market_index` از همان `GetMarketOverview` |
| حقیقی/حقوقی | `client_type` (حجم) و `client_type_value` (ارزش native در صورت وجود) |
| مرجع ۱ | TSETMC: `GetMarketWatch`، `GetMarketOverview/1,2`، `ClientType/GetClientTypeAll` |
| مرجع ۲ | TradersArena: `/data/mainwatch/symbols`، `/data/market0`، `/data/market/chart/totals0` |
| مرجع ۳ | Rahavard365: صفحهٔ عمومی خانه (نشستِ لاگین‌شدهٔ Firefox در دسترس ابزار نبود) |

نسخهٔ قواعد مقایسه: تطبیق با `insCode` (نه نام)، و مقایسهٔ عددی فقط روی زیرمجموعهٔ **same-tick** (`row_h == hEven`) برای جداکردن تأخیر انتشار از باگ.

---

## ۴) اختلاف‌های قبل از اصلاح

### ۴-۱) پیش از اصلاح p_last

- Snapshot قبل: `2026-10-20 14:59:36` (TSETMC 14:51:49؛ Bors sync 14:53:34).
- جامعه: Bors live `3303`، TSETMC `3303`، joined `3303`؛ `only_tsetmc=0`.
- نتیجهٔ ابزار: `p_last` فقط **94.58%**، `price_change` **93.92%**، `q_tot_tran`/`z_tot_tran` **96.03%** روی same-tick؛ `p_closing`, `price_yesterday`, `p_first`, `p_max`, `p_min`, `tmin` = 100%.
- مقایسهٔ مستقیم با یک snapshot ثابت TSETMC:
  - **228 از 3302** ردیف `p_last` متفاوت بودند؛ **172** same-tick و **175** بدون معامله.
  - نمونه‌ها: `آسيا3` (Bors 4650 / TS 4750)، `آپ3` (10150 / 10060)، `اراد298` (760000 / 749800)، `آتش` (46207 / 46226).
- نمونهٔ صفر/کهنه: `آپ3` در منبع `qtj=0, qtc=0, ztt=0, pc=0` بود، ولی Bors `q_tot_tran=5000`, `q_tot_cap=50,750,000`, `z_tot_tran=1`, `price_change=170` نشان می‌داد.

### ۴-۲) وضعیت و شاخص

- `phase`: `closed`، `official_state=N`، عنوان «بسته»، `session_day=20261020`؛ با وضعیت رسمی TSETMC هم‌خوان بود. `data_updated_at` در snapshot اول 14:53:34 و منبع 15:03 بود؛ این تفاوتِ زمانِ sync/source است، نه تغییر حکم.
- `tedpix` و `equal_weight` در snapshot اول کمی با منبع فاصله داشتند (مثلاً 8,272,265.69 در برابر 8,272,265.41)؛ پس از sync نهایی دقیق شدند.
- `value_weighted_price`: Bors `7926.44`، تغییر `+50.78%`؛ Rahavard `3055.87`، `+0.22%`. این دو یک کمیت نیستند (جزئیات §۸).

---

## ۵) ریشهٔ هر اختلاف

### ۵-۱) باگ مستقیم ۱ — `p_last` از منبع جدا می‌شد

در `_mw_row` و مسیر full-sync:
```python
p_last = pdv or ((py + chg) if (pcl and py) else None)
```
دو مشکل داشت:
1. اگر `pdv` صفر/غایب بود، یک «آخرین» از `py+pc` ساخته می‌شد؛ این عدد LAST نیست.
2. در حالت بسته، بلوکِ حفاظت، `p_last`ِ **کهنهٔ بانک** را روی LASTِ معتبرِ منبع می‌نوشت (فقط با قیدِ نسبتِ 0.5–2.0). برای ردیف‌های بی‌معامله، این باعث اختلاف با `pdv` منبع می‌شد.

### ۵-۲) باگ مستقیم ۲ — صفرِ معتبر با عددِ دیروز عوض می‌شد

```python
if closed and not (vol or val or trd) and ins in prev:
    vol, val, trd, chg = _p["q_tot_tran"], _p["q_tot_cap"], ...
```
`not (vol or val or trd)` هم **صفر** و هم **غایب** را یکی می‌کرد. ردیفِ «امروز معامله‌ای نشد» صفرِ معتبر دارد؛ ولی برنامه حجم/ارزش/تعداد/تغییرِ نشستِ قبل را نشان می‌داد. مثالِ same-tick: `آپ3` (منبع 0/0/0/0؛ Bors 5000/50.75M/1/170) و `آرين سلامت06` (منبع `pc=0`؛ Bors `price_change=-11910`).

### ۵-۳) اختلافِ تعریف، نه باگِ parser

- `value_weighted_price` در Bors از `q_tot_cap/q_tot_tran` ساخته می‌شود؛ این «میانگین ارزشی قیمت معاملات» است، نه شاخصِ «قیمت وزنی ارزشی» مرجع. سند `docs/research/RAHAVARD-13-PAGES-MARKET-STATUS-RECONSTRUCTION.md` صریحاً می‌گوید تعریفِ مرجع در بانک نیست و فرمول ساخته نشود؛ سؤالِ مالک باز است.
- `percent_change` در Bors **CLOSE-based** است `(pcl-py)/py` و `percent_last` **LAST-based** است `(pdv-py)/py`. اختلافِ علامت (مثلاً خودرو: -0.43% در برابر +0.87%) طبیعی است، نه باگ.
- سطرِ `all` در `mstat.summary` جامعهٔ `m` تریدرزآرناست (1500 نماد)، نه تمام 3303 ردیفِ تابلوی زنده؛ در `docs/TA-SCOPE-DECODE.md` توضیح داده شده است.
- `blDs` بعد از بستن در منبع خالی است؛ Bors عمقِ آخرین نشست را عمداً نگه می‌دارد و `phase` می‌گوید `order_pressure` قابل‌محاسبه نیست. این یک «تفاوتِ زمان/معنا» است، نه اثبات تطبیق عمق.

---

## ۶) اصلاحات واقعی کد

### `test_tsetmc.py` — ۵۶ درج / ۱۹ حذف

1. افزودن `_source_last_price(r)`:
   - فقط `pdv` خام؛ `0`/غایب ⇒ `None`.
2. افزودن `_last_trade_price(...)`:
   - LASTِ معتبرِ منبع همیشه بر مقدارِ ذخیره‌شده مقدم است.
   - فقط در نبودِ کامل LAST، بازارِ بسته و ردیفِ بی‌معامله، LASTِ نشست پیشین (در بازهٔ 0.5–2.0 قیمت پایانی) نگه داشته می‌شود.
3. استفاده در `_mw_row` (مسیر tick و snapshot) به‌جای `pdv or py+pc`.
4. استفاده در full-sync (`main()`) به‌جای بازنویسی `p_last` با `_p["p_last"]`.
5. افزودن `_closed_values(...)`:
   - فقط وقتی هر سه `vol`, `val`, `trd` **`None`** باشند، از نشست پیشین پر می‌کند؛ صفرِ منبع دست‌نخورده می‌ماند.
   - جایگزینی بلوکِ `not (vol or val or trd)`.
6. حذف fallback استنتاجی `py+chg` از تولید `p_last`.

**فایل جدید تست:** `dev/market_last_trade_semantics_v1.py` (۱۱ سنجه؛ pure/بدون شبکه/DB عملیاتی).

**فایل‌های جدید مستندات/شواهد:**
- `docs/MARKET-STATUS-FIELD-MATRIX-QODER3-2026-10-20.csv`
- `reports/market-status-parity/snapshot-20261020-145936.json` (قبل)
- `reports/market-status-parity/snapshot-20261020-151546.json` (پس از اصلاح p_last)
- `reports/market-status-parity/snapshot-20261020-152056.json` (پس از اصلاح صفر/غایب)

**تغییر نکرد:** `api/*`، `frontend/*`، `market_phase.py`، `mstat_engine.py`، فرمول کارتِ ارزشی، تنظیمات، installer، Workflow.

---

## ۷) تست‌ها و شواهد مقایسه

### ۷-۱) تست‌های هدفمند

| فرمان | نتیجه |
|---|---|
| `python dev/market_last_trade_semantics_v1.py` | **۱۱/۱۱ passed** |
| `python dev/market_tick_v1045.py` | **۲۳ سنجه، ۰ خطا** |
| `python -m py_compile test_tsetmc.py` | OK |
| `python tools/live_parity_snapshot.py --bt http://127.0.0.1:8017` | اجرا شد؛ خروجی زیر |

محتواهای تست جدید شامل:
- LAST معتبر منبع بر مقدار کهنه مقدم است؛
- نبودِ LAST + بسته/بی‌معامله فقط از نشست قبل پر می‌شود؛
- صفر منبع در `_mw_row` به null تبدیل می‌شود؛
- صفر معتبر حجم/ارزش/تعداد/تغییر با عدد دیروز عوض نمی‌شود؛
- مسیر `daily_prices.p_last` همان قاعده را دارد.

### ۷-۲) تطبیق نهایی same-tick

Snapshot نهایی: `2026-10-20 15:20:56` · Bors sync `15:19:51` · TSETMC `15:20:54`.

| فیلد | قبل (same-tick) | بعد (same-tick) | حکم |
|---|---:|---:|---|
| `p_last` | 94.58% | **100%** | FIXED |
| `p_closing` | 100% | **100%** | MATCHED |
| `price_yesterday` | 100% | **100%** | MATCHED |
| `p_first` | 100% | **100%** | MATCHED |
| `p_max` | 100% | **100%** | MATCHED |
| `p_min` | 100% | **100%** | MATCHED |
| `tmin` | 100% | **100%** | MATCHED |
| `price_change` | 93.92% | **100%** | FIXED |
| `q_tot_tran` | 96.03% | **100%** | FIXED |
| `z_tot_tran` | 96.03% | **100%** | FIXED |

- `total_field_diffs = 0` روی فیلدهای MAPPED.
- `same-tick = 3223 / 3281`؛ ردیف‌های غیر same-tick به‌دلیل تیکِ جدیدتر منبع پس از sync هستند.
- مقایسهٔ مستقیم نهایی: `p_last` 38 اختلاف از 3281 (همه غیر same-tick)، `p_closing` 13، `q_tot_tran`/`q_tot_cap`/`z_tot_tran` 58، `price_change` 38؛ **۰ اختلاف same-tick**.
- نمونه‌های اصلاح‌شده: `آسيا3` 4650→4750، `آپ3` 10150→10060 و حجم 5000→0، `اراد298` 760000→749800.

### ۷-۳) مرجع‌های بیرونی

| مرجع | مشاهده | نتیجه |
|---|---|---|
| TradersArena `mainwatch/symbols` | 20 نماد؛ 20/20 در `p_last`, `p_closing`, `percent_change` | MATCHED |
| TradersArena حجم | 20/20 پس از اصلاح (قبل 18/20) | FIXED |
| TSETMC `GetMarketOverview` | `indexLastValue=8272267.92`، `equal=2251333.03`، `marketState=N/بسته` | با کارت‌های Bors **MATCHED** |
| TSETMC `ClientTypeAll` | حجم‌های buy/sell فولاد و خودرو | MATCHED |
| Rahavard365 home | tedpix `8,272,265.72`، equal `2,251,320.05`، value-weighted `3,055.87`، فولاد `4310`، خودرو `690` (ساعت ۱۴:۲۵) | مقایسهٔ زمانی/تعریفی؛ جزئیات §۸ و §۹ |
| TSETMC `blDs` | بعد از بستن، ۰ ردیف با عمق غیرخالی | UNVERIFIED برای عمق جاری |

---

## ۸) اختلاف‌های مورد انتظار / نیازمند تصمیم

1. **`value_weighted_price`** — Bors میانگین ارزشی معاملات (`q_tot_cap/q_tot_tran`) را نشان می‌دهد؛ Rahavard یک شاخصِ رسمیِ «قیمت وزنی ارزشی» با مقدار ۳٬۰۵۵٫۸۷ دارد. این‌ها یک کمیت نیستند. سند مرجع می‌گوید تعریف رسمی در بانک نیست و فرمول ساخته نشود. تغییر نکرد؛ نیازمند رأی مالک: تعریف/تغییر نام/حذف. تا آن زمان تطبیق با این کارت **ادعا نمی‌شود**.
2. **LAST در برابر CLOSE** — `percent_last` و `percent_change` دو تعریف جدا هستند؛ هر دو در پاسخ API حاضرند. استفاده از یکی به‌جای دیگری در UI/filters باید آگاهانه باشد.
3. **سطر `all`** — جامعهٔ ۱۵۰۰ نمادی، دامنهٔ `m` تریدرزآرناست، نه تمام ۳۳۰۳ ردیف تابلو.
4. **عمق/صف بعد از بستن** — منبع `blDs` خالی است؛ Bors صف‌های نشست آخر را نگه می‌دارد. این «آخرین نشست» است، نه عمق جاری؛ UI باید همین را نشان دهد.
5. **زمان مرجع‌ها** — Rahavard (۱۴:۲۵/۱۴:۵۱)، TradersArena (۱۵:۱۷) و TSETMC (۱۵:۲۰) هم‌لحظه نیستند؛ اختلاف‌های کوچک شاخص‌ها `TIMESTAMP_MISMATCH` هستند، نه باگ.
6. **تفکیک ارزش حقیقی/حقوقی** — `ClientTypeHistory` امروز HTTP 500 داد؛ حجم‌ها native و منطبق‌اند، اما تفکیک ارزش فعلی «محاسبه‌شده» است و با مقدار native مرجع تطبیق داده نشد. `SOURCE_GAP`.

---

## ۹) محدودیت‌ها و موارد تأییدنشده

- **Rahavard:** در مرورگر in-app، صفحهٔ Rahavard بدون نشستِ لاگین باز شد (`ورود/ثبت‌نام`). Firefox کاربر در حال اجرا بود اما endpoint remote-debugging نداشت. هیچ profile، Cookie، token یا دادهٔ حساس خوانده/کپی نشد. بنابراین فقط کارت‌های عمومی خانه Rahavard بررسی شد؛ صفحهٔ کامل نماد و عمق سفارشِ Rahavard **UNVERIFIED** است.
- هیچ تست مرورگریِ UI انجام نشد؛ ممیزی API/داده است، نه پذیرش بصری.
- تطبیق همهٔ فیلدها در یک لحظهٔ کاملاً هم‌زمان انجام نشد؛ برای فیلدهای نوسانی same-tick جدا شد و باقی اختلاف‌ها `TIMESTAMP_MISMATCH` ثبت شدند.
- عمق جاری و برخی ردیف‌های زندهٔ اضافی Bors (۲۲ ردیف) نیاز به بررسی منبع/انقضا دارند.
- `market.db` عملیاتی لمس نشد؛ فقط کپیِ موقت در `.q3-live-run` استفاده شد. 
- تست جدید در `run_all_tests.py` ثبت نشد تا فایلِ مشترکِ گاردها با مأموریت‌های موازی تداخل نکند؛ اجرای آن مستقل است و باید در گیتِ کامل ثبت شود.

---

## ۱۰) commitها و وضعیت worktree

| مورد | مقدار |
|---|---|
| branch | `mission/market-status-data-parity-qoder3-2026-10-20` |
| base | `a14375c14cfb8fc616fb3312c685f8a5b0f79ab3` |
| commit اصلی کد/تست/مستندات | `dc9896a447e161c659fd09a13b6d8be07c8d6688` |
| push/merge/tag | انجام نشد |
| شاخه‌های Qoder 1/2 | لمس نشدند |
| `main` | دست‌نخورده |

**فایل‌های تغییرکرده:**
- `test_tsetmc.py` (اصلاح دو مسیر p_last و صفر/غایب)
- `dev/market_last_trade_semantics_v1.py` (تست هدفمند)
- `docs/MARKET-STATUS-DATA-PARITY-QODER3-2026-10-20.md`
- `docs/MARKET-STATUS-FIELD-MATRIX-QODER3-2026-10-20.csv`
- `reports/market-status-parity/*.json` (شواهد before/after)

**نتیجهٔ نهایی:** شکافِ مستقیمِ `p_last` و صفر/غایب بسته شد و ۱۰ فیلد اصلی روی همان تیک ۱۰۰٪ شد. کارتِ «قیمت وزنی ارزشی» و محدودیت‌های Rahavard/عمق، صریحاً باز و `UNVERIFIED`/منتظر تصمیم مالک باقی مانده‌اند.
