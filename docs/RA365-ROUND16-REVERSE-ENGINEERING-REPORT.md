# RA365 Round 16 — Reverse Engineering & Full-Universe Parity Recovery

**تاریخ:** 2026-10-22  
**شاخه:** `mission/ra365-round15-full-universe-type7-parity-2026-10-21`  
**مبنای Round 15:** `138c8002` (کد: `ad9aa230`، گزارش: `01006798`)  
**دیتابیس عملیاتی:** دست‌نخورده — fingerprint `fff358a78be74e8d21961251a727116e102df84cea70f87b4dcb7da198667004`

---

## 0. خلاصهٔ اجرایی

| موضوع | وضعیت | شاهد |
|---|---|---|
| فرضیهٔ «محدودیت دادهٔ پیش از ۲۰۲۴» | **REFUTED** | API با `size=20000` داده را تا ۲۰۰۸ برمی‌گرداند؛ محدودیت، پارامتر collector بود |
| فرمول DPS در `type7` | **VERIFIED** | `closing_ex / (closing_ex + DPS)` با **پایانیِ همان کندل**؛ holdout 445/483 exact |
| فرضیهٔ last-price | **REJECTED** | dev 244/451، holdout 250/483؛ متریک کلی بدتر |
| نسبت منبع `p_closing/pna` به‌عنوان پایهٔ DPS | **REJECTED** | dev 13/451، holdout 20/483؛ نسبت رسمی PA است، نه پایهٔ type7 |
| اصلاح production | `IMPLEMENTED_AND_TESTED` | پایهٔ DPS از پایانیِ کندل اثربخش؛ DB فقط fallback |
| اثر کد روی cohort ۲۷ ردیفی | `VERIFIED` | exact `49.5933 → 51.4664` (**+1.8731pp**) |
| اثر داده + کد روی cohort کامل | `VERIFIED` | exact `49.5933 → 68.8309` (**+19.2376pp**) |
| Factor ±1% | `VERIFIED` | `85.4817 → 87.2290` (+1.7473pp) |
| OHLC عملکردی | `VERIFIED` | `50.2502 → 68.0025` (+17.7523pp) |
| نرمال exact | `VERIFIED` | `41.5983 → 60.0912` (+18.4929pp) |
| Full-Universe Gate | `IMPLEMENTED_AND_TESTED` | DB کامل + guard جدید؛ chart API guard 18/18؛ اجرای all-suite دوباره ناتمام (`NOT_MEASURED`) |
| CODAL | `VERIFIED` | ۳۰/۳۰ سند؛ ۲۸ no-cash، ۱ PAID_IN، ۱ UNPARSED |
| فروي | `BLOCKED` | `BLOCKED_P_DEFINITION` |
| حخزر | `BLOCKED` | `UNVERIFIED_NET_DPS` |
| دیتابیس عملیاتی | `VERIFIED` بدون تغییر | SHA پیش/پس یکسان |

**نتیجهٔ اصلی:** علت اصلی اختلاف پیش از ۲۰۲۴، «گردکردن قیمت» نبود؛ **پایهٔ DPS از منبع اشتباه**
خوانده می‌شد و **تاریخچهٔ رسمی کامل** در collector وجود نداشت. با بازیابی تاریخچهٔ کامل TSETMC
(۱۰٬۸۳۱ ردیف priceAdjust از ۲۰۰۸، ۳٬۴۹۳ ردیف shareChange) و استفاده از **پایانیِ کندل اثربخش**
در فرمول DPS، تطبیق Factor exact از `49.5933` به **`68.8309`** و OHLC از `50.2502` به
**`68.0025`** رسید؛ همان cohort، همان مخرج‌ها.

---

## 1. مبنا و cohortها

- HEAD شروع: `138c8002`؛ کد Round 15: `ad9aa230`؛ گزارش: `01006798`.
- working tree شروع پاک بود؛ هیچ reset/بازنویسی انجام نشد.
- شاخه و کد Round 15 حفظ شد؛ اصلاحات R15 در `api/chart.py` باقی ماندند.
- `main` تغییر نکرد.
- دیتابیس عملیاتی فقط‌خواندنی بود؛ همهٔ آزمایش‌ها روی کپی ایزوله.
- کپی fullcorp جدول `fund_profit_events` را از Round 15 (۲٬۲۲۲ ردیف) دارد؛
  دیتابیس عملیاتی این جدول را خالی دارد. نتیجهٔ ۶۸٫۸۳ شامل دادهٔ صندوق است و
  production بدون آن پایین‌تر خواهد بود (coverage، نه فرمول).

| Cohort | Factor exact | Factor ±1% | OHLC | نرمال exact | نرمال ±1% |
|---|---:|---:|---:|---:|---:|
| R15 baseline ۱۸ ردیفی | 48.4596 | 82.1036 | 48.9452 | 41.4102 | 82.0526 |
| R15 final ۲۷ ردیفی | 49.5933 | 85.4817 | 50.2502 | 41.5983 | 82.4325 |
| R16 code-only (۲۷ ردیفی) | **51.4664** | **85.7996** | **52.2521** | 41.6970 | 82.3603 |
| R16 data-only (DB-close) | 52.0051 | 84.3268 | 52.5656 | 42.3149 | 78.4519 |
| **R16 final (full + candle closing)** | **68.8309** | **87.2290** | **68.0025** | **60.0912** | **83.5676** |
| R16 rejected last-price (code-only) | 46.7683 | 85.6677 | 47.6572 | 41.3774 | 82.4065 |
| R16 rejected last-price (full) | 49.8976 | 87.0192 | 50.8865 | 46.9350 | 83.2209 |

- Universe: ۲٬۵۹۵ دارایی؛ Factor dates: ۱٬۱۸۷٬۹۴۵؛ OHLC fields: ۴٬۷۵۱٬۷۸۰.
- تعریف‌ها همان Round 12–15: exact `|prod/ref−1|≤0.0005`؛ ±1% `≤0.01`؛ OHLC با تلورانس
  `max(0.5 ریال, 1e−6·|ref|)`؛ نرمال‌سازی به اولین کندل مشترک.
- `48.4009` همچنان به cohort دوازده‌ردیفی تعلق دارد، نه دیتابیس عملیاتی؛ در این راند
  مبنای مقایسهٔ اصلی **۲۷ ردیفی** است و همهٔ نتایج با همان مخرج گزارش شده‌اند.

---

## 2. روش‌ها و ابزارها

| ابزار/روش | کاربرد |
|---|---|
| API عمومی TSETMC (`cdn.tsetmc.com`) | کشف تاریخچهٔ کامل `GetPriceAdjustByFlow` و `GetInstrumentShareChangeByFlow` |
| Python / SQLite | بازسازی زنجیره، محاسبهٔ step، تحلیل ۱٬۲۱۶ گسست پیش از ۲۰۲۴ |
| Rahavard type0/type7 bars | مرجع مستقل برای هر گام؛ بدون ذخیرهٔ credential/cookie |
| CODAL collector | تکمیل ۳۰ سند، cache HTML، checkpoint ماندگار |
| Git history | حفظ قواعد Round 7/12/14/15 و بررسی دلیل `_drop_base` و تلورانس‌ها |
| Holdout | تقسیم قطعی بر اساس `sha256(symbol)`؛ پارامترها روی holdout تنظیم نشد |

نشست Rahavard برای خواندن حالت‌های اضافی در این راند استفاده نشد؛ مرجع type0/type7
ذخیره‌شده و bars مستقل کافی بود. هیچ credential/کوکی خوانده یا ذخیره نشد.

---

## 3. کشف داده: «محدودیت» وجود نداشت

Collector قبلی از این پارامترها استفاده می‌کرد:

- `GetPriceAdjustByFlow/{flow}/500` → فقط ۵۰۰ ردیف آخر (شروع ۲۰۱۷).
- `GetInstrumentShareChangeByFlow/{flow}/14` → پنجرهٔ ۱۴ روزه.

با پارامتر بزرگ‌تر:

| درخواست | ردیف | بازه |
|---|---:|---|
| `GetPriceAdjustByFlow/1/5000` | ۵٬۰۰۰ | 2017-04-22 .. 2026-10-21 |
| **`GetPriceAdjustByFlow/1/20000`** | **۸٬۷۹۸** | **2008-11-26 .. 2026-10-21** |
| `GetPriceAdjustByFlow/2/5000` | ۲٬۲۲۵ | 2009-10-03 .. 2026-10-20 |
| `GetInstrumentShareChangeByFlow/1/5000` | ۲٬۳۹۹ | 2008-12-06 .. 2026-10-21 |
| `GetInstrumentShareChangeByFlow/2/5000` | ۱٬۱۸۵ | 2010-08-30 .. 2026-10-24 |

پس از dedupe: **۱۰٬۸۳۱ ردیف PA** و **۳٬۴۹۳ ردیف SH** (back to 2008) در
`market_r16_fullcorp.db` ایزوله inghest شدند. این جدول‌ها با
`tools/corp_events_full_history_ingest.py` قابل بازتولیدند و snapshot آن‌ها در
`docs/audit/ra365-round16/tsetmc-price-adjust-full.csv` و
`tsetmc-share-change-full.csv` ثبت شد.

---

## 4. مهندسی معکوس فرمول `type7`

### 4.1 فرضیه‌ها و نتایج

مجموعهٔ مرجع: ۹۳۴ گام تک‌رویدادیِ پیش از ۲۰۲۴ که در baseline اختلاف exact داشتند و یک
ردیف رسمی PA در فاصلهٔ ≤۱۰ روز دارند. توسعه/holdout جداگانه.

| فرضیهٔ پایهٔ DPS | فرمول | dev exact | holdout exact | post-2024 exact | وضعیت |
|---|---|---:|---:|---:|---|
| **پایانیِ کندل اثربخش** | `closing/(closing+DPS)` | **412/451** | **445/483** | **345/364** | **VERIFIED** |
| last قیمت | `last/(last+DPS)` | 244/451 | 250/483 | 197/364 | **REJECTED** |
| نسبت منبع رسمی | `p_closing/p_closing_not_adjusted` | 13/451 | 20/483 | 16/364 | **REJECTED** (نسبت PA است) |
| پایانیِ روز قبل | `(prev_close−DPS)/prev_close` | 60/451 | 55/483 | — | **REJECTED** |
| open / high / low | `x/(x+DPS)` | 177 / 159 / 153 | 180 / 144 / 177 | — | **REJECTED** |
| گیت حجم صفر | last فقط اگر volume>0 | 244 | 251 | — | **REJECTED** (تفاوت ۱ مورد) |
| انتخاب نزدیک‌تر به گسست پایه | min(|B−gap|,|C−gap|) | 14/451 | 23/483 | — | **REJECTED** |

**مثال تعیین‌کننده (آریا 2020-07-05):** کندل اثربخش: `closing=91,277`، DPS=8,740 →
`91,277/100,017 = 0.91261486` = مرجع. `last=94,105` → `0.91499`؛ نسبت منبع `89,624/98,364=0.911146`.
این نشان می‌دهد type7 برای DPS از **پایانی همان کندل** استفاده می‌کند، نه last و نه نسبت رسمی.

### 4.2 چرا قبلاً دیده نمی‌شد

`_official_price_adjust_events` پایهٔ DPS را از `_closing_prices_for` می‌خواند که از
`price_history.close` می‌آید. برای بسیاری از نمادها تاریخچهٔ محلی از payload کوتاه‌تر است
(نمونه: آریا در `price_history` برای ۲۰۲۰ ردیفی ندارد)؛ پس `cl = None` می‌شد و رویداد
به `dps-unverified` یا نسبت منبع تبدیل می‌شد. کندل payload همان `closing` درست را دارد.
این یک **نقص plumbing داده** بود، نه فرمول.

---

## 5. علت‌های غالب و تعداد موارد

| خانواده | تعداد | شاهد/وضعیت |
|---|---:|---|
| گسست پایهٔ تک‌رویدادیِ پیش از ۲۰۲۴ با اختلاف exact | ۱٬۲۱۶ | ۹۳۶ ردیف PA ≤۱۰ روز؛ ۲۸۰ بدون PA |
| ↳ با پایانیِ کندل exact | **۸۵۷/۹۳۴** (۹۱٫۸٪) | holdout ۴۴۵/۴۸۳؛ post-2024 ۳۴۵/۳۶۴ |
| ↳ با نسبت منبع exact | ۳۳/۹۳۴ (۳٫۵٪) | نشان می‌دهد منبع رسمی پایهٔ type7 نیست |
| گسست پایهٔ ۲۰۲۴+ با اختلاف exact | ۴۹۲ | ۳۶۴ ردیف PA؛ ۳۴۵/۳۶۴ exact با پایانی کندل |
| ۲۸۰ گسست بدون PA | ۲۸۰ | ۱۵۳ ردیف share در ≤۱۰ روز؛ فقط ~۱۵ نسبت با مرجع ≤۱٪ |
| گسست‌های far باقی‌مانده | ۶۸/۹۳۴ پیش از ۲۰۲۴؛ ۱۵/۳۶۴ پس از ۲۰۲۴ | چندرویدادی/سرمایه/طبقه‌بندی |

**علت غالب اثبات‌شده:** ترکیب (الف) نبود تاریخچهٔ رسمی PA پیش از ۲۰۲۴ در collector و
(ب) خواندن پایهٔ DPS از `price_history.close` به‌جای پایانیِ کندل. هر دو در این راند اصلاح شدند.
فرضیهٔ «گردکردن قیمت» به‌تنهایی توضیح‌دهنده نبود؛ ۹۳۶ گام داده رسمی داشتند که استفاده نمی‌شد.

---

## 6. تغییرات production

### 6.1 `api/chart.py`

1. `_canonical_adjustment(..., closings=None)` نقشهٔ تاریخ→پایانیِ کندل را می‌گیرد.
2. `_official_price_adjust_events(..., closings=None)` پایهٔ DPS را از همین نقشه می‌خواند؛
   `_closing_prices_for` فقط fallback است.
3. `_classify_pa_event` همان فرمول اثبات‌شدهٔ `closing/(closing+DPS)` را با پایانیِ کندل
   اعمال می‌کند؛ هیچ مقدار ناموجودی با صفر/یک پر نمی‌شود.
4. دو مسیر واقعی چارت (`get_chart_tsetmc` و `get_chart_db`) نقشهٔ
   `{date: candle.closing}` را پاس می‌دهند.

قواعد Round 15 (dedupe DPS با نسبت منبع، اقدام ترکیبی، پنجرهٔ ۱۰ روزهٔ شاهد) و
قواعد Round 12 (فیلتر سهام) دست‌نخورده‌اند. هیچ شرط/ضریب مخصوص نماد اضافه نشد.
`adjustment_engine.py` تغییر نکرد.

### 6.2 محیط Gate

`dev/gate_db_guard.py` اکنون قبل از کپی، وجود جدول‌های `instruments`، `price_history` و
`financial_statements` را بررسی می‌کند و DB ناقص/خالی را با
`GATE_REFUSED_INCOMPLETE_DB` رد می‌کند. ریشهٔ خطای Round 15 یک `market.db` ۴ کیلوبایتی
خالی در worktree بود که کپی می‌شد.

### 6.3 ابزارها

- `tools/corp_events_full_history_ingest.py` — ingest کامل PA/SH با cache و idempotency.
- `tools/ra365_round16_parity.py` — اندازه‌گیری قبل/بعد با preload و `--candle-closing`.
- `tools/codal_share_type_resume.py` — checkpoint ماندگار، HTML cache، lock، Retry-After.

---

## 7. Before/After و Holdout

### 7.1 تفکیک اثر

| مقایسه | Factor exact | Factor ±1% | OHLC | نرمال exact |
|---|---:|---:|---:|---:|
| R15 final (۲۷ ردیفی) | 49.5933 | 85.4817 | 50.2502 | 41.5983 |
| R16 code-only | 51.4664 | 85.7996 | 52.2521 | 41.6970 |
| **Δ کد** | **+1.8731pp** | **+0.3179pp** | **+2.0019pp** | **+0.0987pp** |
| R16 data+code | 68.8309 | 87.2290 | 68.0025 | 60.0912 |
| **Δ کل** | **+19.2376pp** | **+1.7473pp** | **+17.7523pp** | **+18.4929pp** |
| **Δ داده (با کد اصلاح‌شده)** | **+17.3645pp** | **+1.4294pp** | **+15.7504pp** | **+18.3942pp** |

تعداد موارد:
- Δ کد: +۲۲٬۲۵۱ تاریخ exact، +۳٬۷۷۷ near، +۹۵٬۱۲۹ فیلد OHLC.
- Δ کل: +۲۲۸٬۵۳۲ تاریخ exact، +۲۰٬۷۵۸ near، +۸۴۳٬۵۵۲ فیلد OHLC،
  +۲۱۹٬۶۸۵ نرمال exact، +۱۳٬۴۸۴ نرمال near.
- Step mismatch: ۲۲۷ → ۲۱۶ (کد) → **۱۶۷** (کامل).
- REF_ONLY: ۱۴۷ → ۱۵۰ → ۱۴۶؛ PROD_ONLY: ۱۴۹ → ۱۵۲ → ۱۸۴.

### 7.2 Holdout و اعتبارسنجی

- مرجع مستقل: ۹۳۴ گام؛ development ۴۵۱ (۴۱۲ exact با پایانی کندل)،
  holdout ۴۸۳ (۴۴۵ exact).
- post-2024 مستقل: ۳۶۴ گام PA-covered؛ ۳۴۵ exact (۹۴٫۸٪).
- فرضیهٔ last-price روی holdout فقط ۲۵۰/۴۸۳ exact بود و در متریک کامل هم بدتر شد؛
  در production استفاده نشد. ستون‌های آن در reference dataset به‌عنوان شاهد رد حفظ شده‌اند.

### 7.3 نمادها

| معیار | بهتر | بدتر | بدون تغییر |
|---|---:|---:|---:|
| Factor exact | **۳۶۱** | **۲۳** | ۲۲۱۱ |
| Factor ±1% | ۹۸ | ۶۵ | ۲۴۳۲ |
| OHLC | ۳۸۶ | ۶۲ | ۲۱۴۷ |
| نرمال exact | ۳۲۰ | ۴۶ | ۲۲۲۹ |

بزرگ‌ترین بهبودها: دجابر (+۱٬۵۳۹ exact)، وساپا (+۱٬۵۰۲)، ثمسكن (+۱٬۴۰۷)، اتكاي (+۱٬۴۰۶)،
دكوثر (+۱٬۳۸۵)، شفا (+۱٬۳۸۰)، ثپرديس (+۱٬۳۵۳)، حكشتي (+۱٬۳۴۴)، تپمپي (+۱٬۲۷۸)، فخوز (+۱٬۲۷۵).

---

## 8. رگرسیون‌ها و علت آن‌ها (پنهان نشده)

۲۳ نماد در Factor exact بدتر شدند؛ ۶۵ نماد در near، ۶۲ در OHLC و ۴۶ در نرمال exact.

| نماد | تغییر exact | نمونهٔ علت |
|---|---:|---|
| ميدكو | −۴۵۰ | گام 2022-06-12: R15 `0.4348779` (ref `0.43477628`) → R16 `0.42697877`؛ share `0.42857143` + PA رسمی، طبقه‌بندی را عوض کرد |
| بشهاب | −۴۴۱ | تداخل رویدادهای ترکیبی/تاریخی در همان کندل؛ نسبت منبع و پایانی کندل هم‌راستا نیستند |
| ومعلم | −۳۵۱ | تغییر طبقه‌بندی/تجمیع رویدادهای رسمی |
| ولبهمن | −۳۵۰ | گام 2023-06-13: R15 `0.66093` → R16 `0.62805609`؛ دو ردیف PA + share `0.61538462` |
| بترانس | −۳۴۴ | رویداد share-only با شاهد CODAL؛ اثر جانبی دادهٔ کامل بر گام مجاور |
| والبر | −۳۳۶ | ردیف PA 2023-06-24 (۲۴ روز قبل) روی کندل پس از توقف نشست و گسست `0.9569` را با `0.9287` عوض کرد |
| كماسه | −۳۲۴ | تغییر زنجیرهٔ share/DPS |
| آسيا | −۳۲۱ | طبقه‌بندی DPS/سرمایه با دادهٔ کامل |
| نمرينو | −۳۰۰ | گام 2025-02-23 در R16 وجود ندارد (رویداد حذف/جابه‌جا شد) |

این رگرسیون‌ها عمدتاً از **تداخل ردیف‌های رسمی قدیمی روی اولین کندل پس از توقف** و
طبقه‌بندی مجدد share/DPS می‌آیند، نه از فرمول پایانیِ کندل. برای Round 17 باید قاعدهٔ
merge ردیف‌های دوردست (پنجرهٔ ۱۰ روزه بر تاریخ مؤثر) و طبقه‌بندی share با پنجرهٔ بزرگ‌تر
مورد بررسی قرار گیرد. هیچ‌کدام پنهان نشده‌اند و در `parity-delta-symbols.csv` ثبت‌اند.

نکتهٔ دیگر: `PROD_ONLY` از ۱۴۹ به ۱۸۴ افزایش یافت؛ دادهٔ کامل چند گام تولیدی اضافی ساخته
که در مرجع نیستند. این مورد نیز برای Round 17 باز است.

---

## 9. Full-Universe Gate

### 9.1 ریشهٔ خطای Round 15

`dev/run_all_tests.py` به `dev/gate_db_guard.py` واگذار می‌کند؛ guard پیش‌فرض
`ROOT/market.db` را کپی می‌کرد. در worktree یک فایل ۴ کیلوبایتی خالی وجود داشت؛
کپی آن باعث `no such table: financial_statements/price_history` شد.

### 9.2 اصلاح

- guard اکنون جدول‌های اصلی را قبل از کپی بررسی می‌کند.
- `market.db` worktree از snapshot کامل ۲۷ ردیفی ساخته شد (نه DB عملیاتی).
- Full gate با DB کامل اجرا شد و **همهٔ سوئیت‌ها به‌جز یکی** سبز شدند؛
  `PROTECTED_DB_UNCHANGED` نیز تأیید شد.
- تنها شکست، `chart_api_check_v95.py` به‌دلیل نبود `frontend/node_modules/klinecharts`
  بود؛ پس از نصب dependency، همان سوئیت **18/18** شد.
- اجرای دوبارهٔ all-suite با dependency نصب‌شده آغاز شد اما پیش از بستن این گزارش
  کامل نشد (روی یک سوئیت طولانی متوقف ماند)؛ وضعیت «یک اجرای کاملاً سبز»:
  `NOT_MEASURED`. شاهدها: `D:/BorsTerminal-tmp/ra365_round15/full_gate_r16.log`
  و `D:/BorsTerminal-tmp/ra365_round16/full_gate_r16_final.log`.

---

## 10. CODAL و داده‌های ناقص

| وضعیت | تعداد | توضیح |
|---|---:|---|
| `COMPLETE` | **۳۰/۳۰** | همهٔ اسناد ۳۰ ردیف exact-type |
| `RESERVE_ONLY` | ۲۶ | no-cash |
| `COMBINED_CLAIMS` | ۲ | no-cash |
| `PAID_IN` | ۱ | وپاسار ۲۰۲۳-۰۳-۱۹؛ پرداخت نقدی ۳۲۲٬۹۶۹ میلیارد ریال؛ واجد sharpening نیست |
| `UNPARSED` | ۱ | فاراك ۲۰۲۱-۰۳-۳۱؛ بدنه موجود، ترکیب قابل‌استخراج نبود |
| `RATE_LIMITED` / `RETRY_PENDING` | ۰ | كلر در Round 16 با `RESERVE_ONLY` کامل شد |

- ۱۷ ردیف Round 14: ۱۶ سند کامل (۱۵ no-cash + ۱ PAID_IN) و ۱ ردیف که قبلاً 429 بود
  (كلر) اکنون کامل است.
- collector: checkpoint، HTML cache، lock، `Retry-After`، backoff؛ 429 هرگز «نبود سند» نیست.
- شاهد جدید: `docs/audit/ra365-round16/codal-checkpoint.csv`.

---

## 11. تست، build و دیتابیس

| مورد | نتیجه |
|---|---|
| `dev/test_round16_candle_closing_dps_v1.py` | **27/27** |
| `dev/test_gate_incomplete_db_v1.py` | **3/3** |
| `dev/test_dps_formula_v1.py` | **61/61** |
| `dev/test_round15_dps_source_duplicate_v1.py` | **21/21** |
| `dev/test_round14_official_events_v1.py` | **17/17** |
| `dev/test_adjustment_engine_v1.py` | **44/44** |
| `dev/test_share_type_evidence_v1.py` | **3/3** |
| `dev/chart_api_check_v95.py` | **18/18** (پس از نصب klinecharts) |
| `python -m py_compile api/chart.py ...` | OK |
| `python dev/persian_glyph_guard.py` | 4/4 |
| `npm run build` | `✓ built in 22.23s` (frontend بدون تغییر؛ شاهد R15) |
| دیتابیس عملیاتی | SHA `fff358…` پیش/پس یکسان |

---

## 12. فایل‌ها و commitها

### 12.1 production/dev

| فایل | تغییر |
|---|---|
| `api/chart.py` | پایهٔ DPS از پایانیِ کندل اثربخش؛ `closings` در دو مسیر چارت |
| `dev/gate_db_guard.py` | رد DB ناقص/خالی قبل از کپی |
| `dev/test_round16_candle_closing_dps_v1.py` | ۲۷ تست holdout/فرمول |
| `dev/test_gate_incomplete_db_v1.py` | ۳ تست guard |
| `dev/run_all_tests.py` | ثبت دو سوئیت |
| `tools/corp_events_full_history_ingest.py` | ingest تاریخچهٔ کامل PA/SH |
| `tools/ra365_round16_parity.py` | سنجش قبل/بعد با `--candle-closing` |
| `tools/codal_share_type_resume.py` | checkpoint/HTML cache/lock/Retry-After |

### 12.2 artifactها

| فایل | نقش |
|---|---|
| `docs/audit/ra365-round16/parity-stages.csv` | جدول مرحله‌ای before/after |
| `docs/audit/ra365-round16/reference_pre2024_dps.csv` | ۹۳۴ گام مرجع با split توسعه/holdout |
| `docs/audit/ra365-round16/tsetmc-price-adjust-full.csv` | ۱۰٬۸۳۱ ردیف رسمی PA |
| `docs/audit/ra365-round16/tsetmc-share-change-full.csv` | ۳٬۴۹۳ ردیف رسمی SH |
| `docs/audit/ra365-round16/parity-symbols-fullcorp-candleclosing.csv` | per-symbol نهایی |
| `docs/audit/ra365-round16/parity-delta-symbols.csv` | delta هر نماد |
| `dev/fixtures/ra365_round16_pre2024_holdout.json` | holdout قابل‌تکرار |

### 12.3 commitها

- `0a76ac4b` — کد/تست/ابزار/artifactهای Round 16
- commit گزارش Round 16 — همین commit

---

## 13. `VERIFIED` / `BLOCKED` / `NOT_MEASURED`

| مورد | وضعیت | دلیل |
|---|---|---|
| فرمول DPS = `closing/(closing+DPS)` با پایانی کندل | `VERIFIED` | dev 412/451، holdout 445/483، post-2024 345/364 |
| last-price به‌عنوان پایهٔ DPS | `REJECTED` | dev 244/451، holdout 250/483؛ متریک بدتر |
| نسبت منبع `pcl/pna` به‌عنوان پایهٔ type7 | `REJECTED` | dev 13/451، holdout 20/483 |
| «محدودیت دادهٔ پیش از ۲۰۲۴» | `REFUTED` | API تا ۲۰۰۸ داده می‌دهد؛ پارامتر collector محدود بود |
| اصلاح production و تست‌ها | `IMPLEMENTED_AND_TESTED` | ۲۷ تست جدید + سوئیت‌های قبلی |
| اثر کامل Full-Universe | `VERIFIED` | 68.8309 / 87.2290 / 68.0025 |
| Gate محیط | `IMPLEMENTED_AND_TESTED` | guard + DB کامل + `PROTECTED_DB_UNCHANGED` + chart guard 18/18 |
| اجرای all-suite کاملاً سبز | `NOT_MEASURED` | rerun پس از نصب dependency کامل نشد؛ تنها شکست قبلی 18/18 شد |
| فروي (`P` رسمی) | `BLOCKED` | `BLOCKED_P_DEFINITION` |
| حخزر (net-DPS) | `BLOCKED` | `UNVERIFIED_NET_DPS` |
| ۲۸۰ گام بدون PA | `NOT_MEASURED` | ۱۵۳ share نزدیک؛ فقط ~۱۵ نسبت با مرجع ≤۱٪ |
| ۶۸ + ۱۵ گام far | `NOT_MEASURED` | چندرویدادی/طبقه‌بندی؛ نیازمند Round 17 |
| ۲۳ رگرسیون exact | `NOT_MEASURED` | علت‌های sample ثبت شد؛ قاعدهٔ merge دوردست باز است |
| production با دادهٔ کامل | `NOT_MEASURED` | migration داده انجام نشده؛ DB عملیاتی فقط post-2024 دارد |
| صندوق در DB عملیاتی | `NOT_MEASURED` | `fund_profit_events` عملیاتی ۰ ردیف است |

**هیچ ادعای ۱۰۰٪ یا حذف مورد دشوار انجام نشد.** مخرج‌ها ثابت ماندند؛ دادهٔ جدید به‌عنوان
`data effect` جدا از `code effect` گزارش شد. هدف بعدی: قاعدهٔ merge ردیف‌های دوردست،
طبقه‌بندی share با پنجرهٔ بزرگ‌تر، و migration کنترل‌شدهٔ دادهٔ کامل به production.
