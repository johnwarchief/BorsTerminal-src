# بستنِ Engine 1 — ماتریسِ ابزارهایِ ترسیم، قراردادِ کندلِ بانک، مقایسۀِ بیرونی و گیت‌ها

- شاخه: `mission/system2-chart-parity-engine1-2026-10-18` — SHAِ این سند: `1c1d0be5`
- تاریخ: ۱۴۰۵-۰۷-۲۷ · انتشار: هیچ Push/Merge/Tag انجام نشده (شاخه بی‌upstream است: `git rev-parse --abbrev-ref @{u}` ⇒ fatal: no upstream configured).

## ۰) علتِ قطعیِ اختلافِ «گیتِ کامل» با «اجرایِ مستقل» (بندِ ۱ مأموریت)

- **اشتباهِ اول، شناساییِ بود:** سطرِ پایانیِ گیت `FAILED: <label>` را می‌دهد و برچسب‌ها انگلیسی‌اند. آن «۲ شکست» مالِ `dev/price_last_value_v1070.py` بود (برچسب «last/closing are separate columns…»)، نه `dev/price_basis_v1070.py` — همان دور که «۲ شکست» دیده می‌شد، برچسبِ `single price resolver` (= خودِ `price_basis_v1070`) درِ *همان* لاگ این سطر است: `OK   single price resolver (last|closing) + adjustment anchor invariance rc=0 | 45/45` . «۴۵ موفق درِ اجرایِ مستقل» هم مالِ همین سوئیتِ دیگر بود.
- **اشتباهِ دوم، متنِ ناخوانا:** `run_all_tests.py` دمِ خروجیِ فرزند را با `encode('ascii','replace')` چاپ می‌کرد؛ دو سطرِ FAIL درِ `gate_final3.log` «?????? ???????…» شد و علتِ واقعی سه دور پنهان ماند. ازِ این دور، هر سوئیتِ قرمزِ کاملِ stdout+stderr خود را بی‌اتلافِ متن درِ `_audit/gate_suites/NNN_<slug>.log` (UTF-8، بیرونِ گیت چون `*.log` gitignored است) می‌نویسد و مسیرش درِ کنسول چاپ می‌شود.
- **علتِ قطعی، نه نوسان و نه ترتیب:** دو سنجه درِ بندِ [۴] همین گارد **متنِ** کوئری و سازندۀِ دستیِ قدیمیِ `get_chart_db` را می‌خواستند؛ کامیتِ `6bb50cb8` آن دو را به `candle_contract.SELECT_SQL` و `from_db_row` برد و آن دو ارجاعِ متنیِ کهنه قرمز شد، بی‌آنکه هیچ عددی عوض شود. سنجشِ مستقلِ بی‌هیچ سوئیتِ دیگری: `17 passed, 2 failed` (همان شمارِ گیت) ⇒ نه وابستگیِ ترتیبی، نه فایلِ موقت، نه ساعت، نه state انباشته. دو سنجه‌ای که می‌شکستند: `last از ستونِ خودش خوانده می‌شود`; `کوئریِ خواننده هر دو ستون را می‌آورد`.
- **اصلاح، بدونِ تضعیفِ گارد:** آن دو ارجاعِ متنیِ جابه‌جاشدنی با سنجه‌هایِ قرارداد-محور بازنویسی شدند (کوئری و سازنده ازِ `candle_contract` می‌گذرند؛ `DB_COLUMNS` باید `last` و `value` را نام‌دار نگه دارد) و یکِ بندِ رفتاریِ تازه افزوده شد که با بانکِ موقت، `get_chart_db` را واقعاً صدا می‌زند: `last` باید از ستونِ خودش بیاید، `closing` لنگر بماند، `value` برسد، ردیفِ حجم‌صفر با شمارشِ علت حذف شود و بی‌`last` درِ بانک ستون `null` بماند. دو کنترلِ منفی هم راستی‌آزمایی می‌کنند سنسور کور نیست (جمله‌یِ «last := close» و حذفِ `last` از قراردادِ ستون‌ها). شمارِ سنجه‌ها ازِ ۱۹ به ۲۶ رسید و نتیجه: `26 passed, 0 failed`.

## ۱) ماتریسِ ۲۹ ابزارِ ترسیم

### ۱٫۱) چرا سنسورِ v3 بازنویسی شد (پس‌گرفتنِ ادعایِ «۲۱ ابزارِ بی‌رسم») 

- درِ اجرایِ v3 بیست‌و‌یکِ ابزار «رسم نکرد» گزارش شد. آن عدد **artifactِ سنسور** بود، نه رفتارِ محصول. سه نقصِ اندازه‌گیری سنجیده شد:
  ۱) «تمام‌شدنِ» رسم با ظهورِ هرِ اورلیِ تازه می‌شد؛ درِ klinecharts v10 یکِ کلیک هم اورلی می‌سازد (با `currentStep` مثبت)، پس رسمِ نیمه‌کاره «رسم شد» و رسمِ تمام‌شده با رسمِ باز یکی بود. قاعدۀِ درست ازِ خودِ موتور خوانده شد: `currentStep === -1` (`_scratch/live/probe_step.json`).
  ۲) بودجۀِ نقطه پنجِ ثابت بود؛ ابزارهایِ پنج‌و‌شش‌نقطه‌ای (هارمونیک، امواج) درِ همان پنجره تمام نمی‌شدند. درِ v4 تا هشت نقطه + دبل‌کلیکِ پایانی می‌رود.
  ۳) تشخیصِ رسم فقط ازِ انبارِ localStorage می‌شد و آن هم بی‌صبر. درِ v4 «رسمِ تمام‌شدۀِ تازه درِ دیدۀِ موتور» شرطِ موفقیت است و شمارۀِ ردیفِ انبار جدا ثبت می‌شود.
- کاوشِ مستقلِ «ثبتِ نام» (`createOverlay` برنامه‌ای، بی‌کلیک): ۲۳ نامِ `overlayType` سنجیده شد و ۲۳ تایِ آن‌ها درِ موتورِ جاری ثبت‌اند. کنترلِ منفیِ خودِ کاوش: نامِ ساختگیِ `zzzNoSuchOverlayXyz` `createOverlay` را بی‌`id` و بی‌اورلی برمی‌گرداند (`_scratch/live/probe_bogus.js`) ⇒ سنسورِ نام کور نیست.
- پس ادعایِ پیشینِ «۲۱ ابزارِ بی‌رسم» پس گرفته می‌شود؛ عددِ درست درِ جدولِ پایینِ همین بند است، عملیات‌به‌عملیات.

### ۱٫۲) اجرایِ v4 — کنترلِ مثبت و خطِ مبنایِ محیط

- registry از خودِ `DrawingToolbar.tsx`: ۸ شیار، ۲۹ شناسۀِ ابزار (کلیدِ گزارش `slotId:toolId:name` است، چون دو `id` با دو نامِ متفاوت تکرار شده و با دِدوپِ صرفِ id یکی از ۲۹ گم می‌شد).
- kinds: ۲۵ سازندۀِ ترسیم، ۳ حالتِ نشانگر، ۱ کنش — سه تایِ آخر عملیاتِ رسم/ویرایش/حذفِ منزوی ندارند و `NOT_APPLICABLE` ثبت می‌شوند، نه `PASS`.
- کنترلِ مثبت (`trendLine`): ✓ با ۲ کلیک — بی‌این هارنس هیچِ نتیجه‌ای گزارش نمی‌کند و exit 3 می‌دهد.
- محیطِ اجرا: `http://localhost:5173` با ۴٬۲۴۷ کندل، ۷۶ اورلیِ غیرِ خودی درِ خطِ مبنا (لایه‌هایِ موتور، بی‌دست‌خوردن)، ویژپورت ۱٬۳۶۶×۷۶۸، پروفیلِ مرورگرِ موقت ⇒ صفرِ ترسیمِ واقعیِ کاربر درِ معرضِ خطر.

### ۱٫۳) جمعِ عملیات‌ها

| عملیات | PASS | FAIL | UNMEASURABLE | NOT_RUN | NOT_APPLICABLE |
|---|---|---|---|---|---|
| دسترسی از رابط | ۲۹ | ۰ | ۰ | ۰ | ۰ |
| رسمِ تمام‌شده | ۲۵ | ۰ | ۰ | ۰ | ۴ |
| ماندگاری پس ازِ بازخوانی | ۲۵ | ۰ | ۰ | ۰ | ۰ |
| ویرایش | ۱۶ | ۹ | ۰ | ۰ | ۰ |
| مخفی‌سازی و نمایشِ مجدد | ۲۵ | ۰ | ۰ | ۰ | ۰ |
| حذفِ یکِ رسم | ۲۵ | ۰ | ۰ | ۱ | ۰ |
| حذفِ منزوی (بقیۀِ رسم‌ها سالم) | ۲۵ | ۰ | ۰ | ۰ | ۰ |
| هماهنگیِ وضعیتِ موتور با انبار | ۲۴ | ۱ | ۰ | ۰ | ۴ |
| **جمعِ ابزارهایِ سنجیده‌شده** | ۲۹ از ۲۹ | | | | |

### ۱٫۴) جدولِ کاملِ ۲۹ شناسه (هر عملیات جدا)

| کلیدِ ابزار (`slot:id:name`) | نوع | دسترسی | رسم | ماندگاری | ویرایش | مخفی | حذفِ یک | منزوی | هماهنگ |
|---|---|---|---|---|---|---|---|---|---|
| `cursor:crosshair:نشانگر صلیبی` | mode | PASS | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| `cursor:dot:نقطه` | mode | PASS | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| `cursor:arrow:پیکان انتخاب` | mode | PASS | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| `cursor:eraser:پاک‌کن` | action | PASS | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_RUN | NOT_APPLICABLE | NOT_APPLICABLE |
| `lines:trendLine:خط روند` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `lines:ray:نیم‌خط (Ray)` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `lines:infoLine:خط اطلاعاتی` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | FAIL |
| `lines:horizontalLine:خط افقی` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `lines:verticalLine:خط عمودی` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `lines:parallelChannel:کانال موازی` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `fib:fibRetracement:بازگشتی فیبوناچی` | drawing | PASS | PASS | PASS | FAIL | PASS | PASS | PASS | PASS |
| `fib:fibExtension:اکستنشن فیبوناچی` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `fib:fibFan:بادبزن فیبوناچی` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `fib:pitchfork:کانال موازی (پیشرفته)` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `shapes:rectangle:مستطیل` | drawing | PASS | PASS | PASS | FAIL | PASS | PASS | PASS | PASS |
| `shapes:brush:قلم‌مو (Brush)` | drawing | PASS | PASS | PASS | FAIL | PASS | PASS | PASS | PASS |
| `shapes:triangle:مثلث` | drawing | PASS | PASS | PASS | FAIL | PASS | PASS | PASS | PASS |
| `shapes:drawArrow:فلش` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `text:text:متن یادداشت` | drawing | PASS | PASS | PASS | FAIL | PASS | PASS | PASS | PASS |
| `text:priceLabel:برچسب قیمت` | drawing | PASS | PASS | PASS | FAIL | PASS | PASS | PASS | PASS |
| `patterns:xabcd:الگوی هارمونیک` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `patterns:xabcd:الگوی هارمونیک (XABCD)` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `patterns:elliott:امواج الیوت` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `gann:gannBox:جعبهٔ گن` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `gann:gannFan:بادبزن گن` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `prediction:longPosition:موقعیت خرید` | drawing | PASS | PASS | PASS | FAIL | PASS | PASS | PASS | PASS |
| `prediction:longPosition:موقعیت خرید (Long)` | drawing | PASS | PASS | PASS | FAIL | PASS | PASS | PASS | PASS |
| `prediction:shortPosition:موقعیت فروش (Short)` | drawing | PASS | PASS | PASS | FAIL | PASS | PASS | PASS | PASS |
| `prediction:measureRange:اندازه‌گیری (قیمت/زمان)` | drawing | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

### ۱٫۵) هرِ ابزاری که عملیاتِ غیرِ PASS دارد (۱۱ سطر) — با علتِ ثبت‌شدہ

| ابزار | عملیات | وضعیت | علتِ سنجیده‌شده |
|---|---|---|---|
| `cursor:eraser:پاک‌کن` | deleteOne | NOT_RUN | action, not a drawing: selecting it removes the whole own group (ownCount 0 -> 0) |
| `lines:infoLine:خط اطلاعاتی` | coherence | FAIL | — |
| `fib:fibRetracement:بازگشتی فیبوناچی` | edit | FAIL | drag at a visible anchor point (606,316) did not move the drawing; pts before=[{"t":1788912000000,"v":4160.12},{"t":1789516800000,"v":3423.33}] after=[{"t":1788912000000,"v":4160.12},{"t":1789516800000,"v":3423.33}] |
| `shapes:rectangle:مستطیل` | edit | FAIL | drag at a visible anchor point (606,316) did not move the drawing; pts before=[{"t":1788912000000,"v":4160.12},{"t":1789516800000,"v":3423.33}] after=[{"t":1788912000000,"v":4160.12},{"t":1789516800000,"v":3423.33}] |
| `shapes:brush:قلم‌مو (Brush)` | edit | FAIL | drag at a visible anchor point (566,316) did not move the drawing; pts before=[{"t":1788592320000,"v":4160.12}] after=[{"t":1788592320000,"v":4160.12}] |
| `shapes:triangle:مثلث` | edit | FAIL | drag at a visible anchor point (566,316) did not move the drawing; pts before=[{"t":1788566400000,"v":4160.12},{"t":1789171200000,"v":3423.33},{"t":1789776000000,"v":3969.1}] after=[{"t":1788566400000,"v":4160.12},{"t":1789171200000,"v":3423.33},{"t":1789776000000,"v":3969.1}] |
| `text:text:متن یادداشت` | edit | FAIL | drag at a visible anchor point (606,316) did not move the drawing; pts before=[{"t":1788912000000,"v":4160.12}] after=[{"t":1788912000000,"v":4160.12}] |
| `text:priceLabel:برچسب قیمت` | edit | FAIL | drag at a visible anchor point (566,316) did not move the drawing; pts before=[{"t":1788566400000,"v":4160.12}] after=[{"t":1788566400000,"v":4160.12}] |
| `prediction:longPosition:موقعیت خرید` | edit | FAIL | drag at a visible anchor point (606,316) did not move the drawing; pts before=[{"t":1788912000000,"v":4160.12},{"t":1789516800000,"v":3423.33},{"t":1790380800000,"v":3969.1}] after=[{"t":1788912000000,"v":4160.12},{"t":1789516800000,"v":3423.33},{"t":1790380800000,"v":3969.1}] |
| `prediction:longPosition:موقعیت خرید (Long)` | edit | FAIL | drag at a visible anchor point (566,316) did not move the drawing; pts before=[{"t":1788566400000,"v":4160.12},{"t":1789171200000,"v":3423.33},{"t":1789776000000,"v":3969.1}] after=[{"t":1788566400000,"v":4160.12},{"t":1789171200000,"v":3423.33},{"t":1789776000000,"v":3969.1}] |
| `prediction:shortPosition:موقعیت فروش (Short)` | edit | FAIL | drag at a visible anchor point (566,316) did not move the drawing; pts before=[{"t":1788566400000,"v":4160.12},{"t":1789171200000,"v":3423.33},{"t":1789776000000,"v":3969.1}] after=[{"t":1788566400000,"v":4160.12},{"t":1789171200000,"v":3423.33},{"t":1789776000000,"v":3969.1}] |

### ۱٫۶) «حذف تمام ترسیم‌ها» درِ هرِ دو شاخه

- هدفِ حذف پیشِ ازِ آزمون ساخته شد و راستی‌آزمایی شد: ✓ (انبار ۱ ردیف، موتور ۱ ترسیم).
- شاخۀِ **لغو** (دیالوگِ بومی رد می‌شود): هیچِ ترسیمی نمی‌میرد ✓ (۱ ردیف پس ازِ لغو).
- شاخۀِ **تأیید**: همۀِ رسم‌هایِ خودی پاک شد ✓ (انبار ۰، موتور ۰).

### ۱٫۷) نقصِ اثبات‌شده‌ای که همین ماتریس پیدا و برطرف کرد

- **ترسیمِ ابزارهایِ lazy ازِ نو نمی‌آمد و سپس پاک می‌شد.** ردیفِ انبار پس ازِ reload سرِ جایش بود، اما دیدۀِ موتور خالی می‌ماند و چند ثانیه بعد خودِ انبار هم خالی می‌شد — یعنی دادهٔ کاربر نابود می‌شد، نه فقط بازیابی‌نشدن. علت درِ کد: تمپلیت‌هایِ `tvTools` با `void import(...)` ثبت می‌شدند و effectِ ماندگاری بی‌انتظارِ آن `applySnapshot` را صدا می‌زد؛ `createOverlay` برایِ نامِ ثبت‌نشده `null` می‌دهد و بعد `tick`ِ دو‌ثانیه‌یِ وضعیتِ «چارت ترسیمی ندارد» را جایِ داده می‌نشاند. شاهدِ قبل/بعد: `_scratch/live/probe_reload_loss.json` (پیش ازِ اصلاح: پس ازِ reload `rows=0 own=0`؛ پس ازِ اصلاح: `rows=1 own=1`).
- **ترسیمِ بازگردانده‌شده ویرایش‌ناپذیر بود.** `_scratch/live/probe_fields.json` دو میدانی را نشان داد که درِ مسیرِ بازگردانی گم می‌شدند: `zLevel` (۷۵ → ۰) و callbackهایِ تعاملی که `handleSelectTool` می‌دهد. بی‌`onPressedMoveStart`، درگِ ماوس چارت را می‌لغزاند و `points` تکان نمی‌خورد. پس ازِ اصلاح، درگِ ترسیمِ بازگردانده‌شده درِ هر چهار سناریو جابه‌جا می‌شود (`_scratch/live/probe_edit2.json`، پروبِ reload).

## ۲) قراردادِ مشترکِ کندلِ بانک

- شمارشِ کلِ بانکِ همین دور (`_audit/db_row_contract_impact.py` → `_scratch/live/db_contract_impact_recheck.log`): ۴۴۱٬۶۳۵ ردیف درِ `price_history` رویِ ۶٬۱۵۰ نماد؛ ۴۳۸٬۹۴۳ ردیف کندل می‌شود؛ ۳۰۶ ردیفِ هندسه‌شکسته (`open=high=low=0` با پایانیِ معتبر) ترمیم می‌شود و ۲٬۶۹۲ ردیفِ حجم‌صفر (روزِ بی‌معامله) کندل نمی‌شود؛ ۴۴ نماد سریِ سرویس‌شده‌شان عوض می‌شود. فیلدهایِ جابه‌جا‌شده: open ۳۰۶، high ۲۹۴، low ۲۹۴ — همه از قاعدۀِ «گِشادِ سایه، بی‌کُنده‌کردنِ قیمتِ منتشرشده».
- گارد: `dev/db_candle_contract_v1.py` → `db_candle_contract_v1: 32 passed, 0 failed`
- پیاده: `get_chart_db` از `candle_contract.from_db_row` و `SELECT_SQL`/`DB_COLUMNS` می‌گذرد؛ شمارش‌ها با علت درِ پاسخ اعلام می‌شود (`dbRows`, `dbNoTradeRows`, `dbInvalidRows`) تا «کم شدنِ کندل» حذفِ خاموش نباشد.

## ۳) مقایسۀِ بیرونی با رهاورد

ماتریسِ قابل‌اجرا: `_audit/ra365_compare_matrix.py` → ۱۱۶ سطر درِ ۲۹ نماد (۲۹ سطرِ پلۀِ تعدیل + ۸۷ سطرِ عادی).

| بکه | سطرهایِ عادی | سطرهایِ پلۀِ تعدیل |
|---|---|---|
| یکسان تا دقتِ ماشین | ۸۵ | ۸ |
| ≤ ۰٫۱٪ | ۰ | ۱ |
| ≤ ۱٪ | ۰ | ۱۵ |
| ≤ ۵٪ | ۰ | ۳ |
| > ۵٪ | ۰ | ۲ |
| بی‌عدد (ردیفِ ما وجود ندارد) | ۲ | ۰ |

سطرهایِ «بی‌عدد» دو موردند و علتشان ثبت‌شدہ است: ۲۰۲۶-۱۰-۰۳ برایِ شراز و شپنا درِ منبعِ رسمی **ردیفِ روزِ بی‌معامله** است (`<VOL>=0`, `<HIGH>=<LOW>=<FIRST>=0` با پایانیِ اعلام‌شدہ)؛ قاعدۀِ محصول از آن کندل نمی‌سازد (جعلِ OHLC ممنوع) و همان ردیف برایِ زنجیرۀِ تعدیل درِ `all_rows` حفظ می‌شود. رهاورد آن روز را رویِ نمودار می‌رسمد ⇒ این تفاوتِ قراردادِ نمایشِ روزِ بی‌معامله است، نه نقصِ داده.

جایِ رویدادها درِ کلِ پنجره (`_audit/adjusted_factor_gap.py`، ۱۷٬۴۷۱ تاریخ): درِ ضریبِ رهاورد ۱۲۷ پله، درِ ما ۱۲۸ پله، ۱۲۷ مشترک، ۰ پلۀِ مرجعِ که ما نداریم، ۱ پلۀِ اضافیِ ما.
پلۀِ اضافیِ ما (مرجع درِ آن بازه پله ندارد): نماد(هایِ) ولراز 12901875871456398 — درِ `ADJUSTED-FACTOR-STEPS.csv` با تاریخِ دقیق ثبت است؛ نه رویدادِ مرجع حذف می‌شود نه ضریبِ ما با عددِ ایشان بازنویسی.

### سه اختلافِ پلۀِ تعدیل — علتِ سنجیده‌شدہ با ردیفِ رسمی

پیش ازِ این علتِ این سه «دفترِ مبدأ نرسیده» ثبت شده بود. درِ این دور ردیفِ منتشرشدۀِ خودِ TSETMC برایِ همان پنجره‌ها خوانده شد (`_audit/fetch_event_window.py` → `_audit/EVENT-WINDOW-OFFICIAL-ROWS.json`) و ردیف‌هایِ خودی ازِ بانکِ همین دور (`_audit/unresolved_events_probe.py` → `_audit/UNRESOLVED-EVENTS-PROBE.json`).

| نماد | تاریخ | نسبتِ پلۀِ مرجع | پله‌هایِ خودی درِ ±۷ روز | ردیفِ رسمیِ ±۱۴ روز | اطلاعیۀِ کدال درِ همان سال |
|---|---|---|---|---|---|
| فولاژ | 2024-07-27 | ۱٫۲۵۰۳۵۱۶۲ | 2024-07-24 1.774808 `base-price-discontinuity` / 2024-07-27 0.510394 `base-price-discontinuity` | ۱۷ ردیف منتشرشده (۳٬۸۰۷ ردیفِ کلِ سری) | ۰ |
| لخزر | 2026-07-27 | ۱٫۲۰۹۷۹۰۲۱ | 2026-07-22 1.711111 `base-price-discontinuity` / 2026-07-25 0.88868275 `priceAdjust` / 2026-07-26 0.580376 `base-price-discontinuity` | ۲۰ ردیف منتشرشده (۴٬۸۷۵ ردیفِ کلِ سری) | ۰ |
| ولراز | 2024-01-30 | ۱۸٫۹۰۵۷۸۷۰۸ | 2024-01-24 0.056225 `base-price-discontinuity` | ۲۰ ردیف منتشرشده (۳٬۴۹۱ ردیفِ کلِ سری) | ۰ |

خوانشِ این چهار ستون (بدونِ هیچِ ضریبِ حدسی):

- **فولاژ 2024-07-27**: درِ پنجرۀِ منتشرشدہ ۱۷ ردیف هست که ۶ تایِ آن‌ها `<VOL>=0` با پایانیِ بازنویسی‌شده‌اند؛ زنجیرۀِ خودی درِ همین پنجره ۲ پله می‌گذارد (2024-07-24, 2024-07-27). یعنی اختلافِ «کجا پله بگذارد» بینِ «روزِ بازنویسیِ بی‌معامله» و «نخستین روزِ معاملاتیِ بعد از آن» است، نه اختلافِ عددِ انتشاریافته.
- **لخزر 2026-07-27**: درِ پنجرۀِ منتشرشدہ ۲۰ ردیف هست که ۶ تایِ آن‌ها `<VOL>=0` با پایانیِ بازنویسی‌شده‌اند؛ زنجیرۀِ خودی درِ همین پنجره ۳ پله می‌گذارد (2026-07-22, 2026-07-25, 2026-07-26). یعنی اختلافِ «کجا پله بگذارد» بینِ «روزِ بازنویسیِ بی‌معامله» و «نخستین روزِ معاملاتیِ بعد از آن» است، نه اختلافِ عددِ انتشاریافته.
- **ولراز 2024-01-30**: درِ پنجرۀِ منتشرشدہ ۲۰ ردیف هست که ۱۰ تایِ آن‌ها `<VOL>=0` با پایانیِ بازنویسی‌شده‌اند؛ زنجیرۀِ خودی درِ همین پنجره ۱ پله می‌گذارد (2024-01-24). یعنی اختلافِ «کجا پله بگذارد» بینِ «روزِ بازنویسیِ بی‌معامله» و «نخستین روزِ معاملاتیِ بعد از آن» است، نه اختلافِ عددِ انتشاریافته.

جمعِ سه مورد: هیچ‌کدام با ضریبِ رهاورد پر نشده و هیچ عددی حدس زده نشده است. وضعیتِ بیرونیِ دیداری همچنان **NOT_OBSERVED** است (نشستِ معتبرِ مرورگر درِ دسترس نبود؛ همۀِ ارقامِ بالا ازِ CSVِ رسمیِ TSETMC و اسنپشاتِ فریزشدہ می‌آیند، نه ازِ صفحۀِ زنده).

### دستورِ آزمونِ دستیِ زنده (برایِ رفعِ NOT_OBSERVED)

```
۱. درِ مرورگریِ که به حسابِ مشترکِ رهاورد وارد است، هرِ دو طرف را رویِ این نشانی‌ها بگذار:
     رهاورد : https://www.rahavard365.com/asset/<asset_id>/chart
     خودی   : http://localhost:5173/#/technical/<symbol>
۲. پیش ازِ هرِ مقایسه درِ هرِ دو طرف: تازۀِ معاملاتی یکسان، دورۀِ «روزانہ»،
   مبنایِ «عملکردی»، و مقیاسِ «لگاریتمی» (راست‌کلیکِ محورِ عمودی → Log Scale).
   این چهارِ تنظیم بدونِ توافق، مقایسه را بی‌معنا می‌کند — قاعدۀِ دورهایِ پیشین.
۳. برایِ هرِ نماد دو تصویرِ هم‌اندازه بگیر: یکی رویِ بازۀِ کامل، یکی رویِ بازۀِ
   ±۳۰ روزِ اطرافِ تاریخِ رویداد (از جدولِ بالا).
۴. عددِ محورِ بالا/پایین و آخرینِ close را درِ هرِ دو طرف یادداشت کن؛ سپس درِ
   خودی از کنسول: window.__borsChart.getDataList().slice(-1)[0] و
   getVisibleRange() — تا سطرِ «مشاهده» با سطرِ «داده» جدا بمانند.
۵. وضعیتِ هرِ مقایسه را فقط یکی از این‌ها بگذار: MATCH / MISMATCH / NOT_COMPARABLE
   / NOT_OBSERVED. اگر نشستِ ورود نداشت یا ۴۰۱ برگشت، همان NOT_OBSERVED می‌ماند؛
   ازِ نشستِ دیگر یا استخراجِ Cookie/توکن استفاده نمی‌کنیم.
۶. ترسیم‌هایِ از‌پیش‌موجودِ نمادِ مرجع هرگز دست نمی‌خورد (حکمِ مالک).
```

## ۴) زنجیرۀِ راستی‌آزمایی رویِ یکِ SHA

- SHAِ زنجیره (ازِ سرِ لاگ‌ها، نه ازِ HEADِ امروز): `27a445b3ba7239411cf385a81ecc813d953a94ae`
  - این HEADِ سند `1c1d0be5` است و فاصلۀِ آن با SHAِ زنجیره فقط سند/مصنوعاتِ متنی است: `_audit/chart_drawing_matrix_v4.csv`, `_audit/gen_engine1_closure_doc.py`, `docs/technical-indicators/reviewed/ENGINE-1-CLOSURE-1405-07-27.md`
  - هیچ فایلِ source یا build درِ این فاصله دست نخورده و هیچ `*.md` درِ بستۀِ `dist/BorsTerminal_Ultimate` کپی نمی‌شود (`find dist -name '*.md'` ⇒ خالی)، پس هشِ بسته همان می‌ماند و زنجیرۀِ tsc/vitest/lint/build برایِ این فاصله بازتکرار نشده — فقط گیتِ پایتون، چون سندِ تازه خوراکِ گاردهایِ متنی است.
- `npx tsc -b`: TSC_EXIT=0
- `npx vitest run`: Tests  1903 passed | 5 skipped (1908)
- `npm run lint` (eslint .): ESLINT_EXIT=1
- `python dev/run_all_tests.py`: 134 suite counted, 25 silent (exit-code only) — ALL SUITES PASSED
- بازیافتِ همان گیت رویِ SHAِ اینِ سند (چون سندِ تازه خوراکِ خودِ گاردهاست): 134 suite counted, 25 silent (exit-code only) — ALL SUITES PASSED؛ سطرهایِ `  OK` = ۱۵۹، سطرهایِ `  FAIL` = ۰، سطرهایِ `  SKIP` = ۰
- `npm run build` (vite): BUILD_EXIT=0
- گاردِ کندلِ بانک: `db_candle_contract_v1: 32 passed, 0 failed`
- بستۀِ رسمی (همان زنجیرۀِ SHA): `27a445b3ba7239411cf385a81ecc813d953a94ae` ← ۸۸۹ فایل، 108.8 مگابایت
  - `PACKAGE_SHA256` (هشِ مجمّعِ relpath+sha256+size): `abcb9d3bf59027fb3c38ef21097c0da914f80506647e181ccb940a256080138f`
  - `EXE_SHA256`: `531b272bf70ea41872eb43022b93c0c422df4392db94c55a46c2c57c4d5a63eb`

## ۴-الف) کامیت‌ها و فایل‌هایِ این دور (ازِ `146b5acd` تا اینِ سند)

```
f4ace8f4|2026-10-19|test(gates): علتِ قطعیِ قرمزیِ گیت پیدا و بسته شد — دو ارجاعِ متنیِ کهنه، نه افتِ ترتیبی
7d30d3b5|2026-10-19|fix(chart): ترسیمِ بازگردانده‌شده دیگر دادهٔ کاربر را نمی‌بلعد و ماوس به آن می‌رسد
aaa9b379|2026-10-19|fix(chart): ردیفِ محافظت‌شده پس ازِ حذفِ کاربر دیگر درِ انبار نمی‌ماند
27a445b3|2026-10-19|test(audit): هارنسِ v4ِ ماتریسِ ۲۹ ابزار + کاوشِ ثبتِ نام، قابِ مختصات و ردیفِ رسمیِ رویدادها
4e811d78|2026-10-19|docs(closure): سندِ بستنِ Engine 1 با ارقامِ بازتولیدشدہ — بندِ ۰ (علتِ گیت)، ماتریسِ ۲۹×۸، قراردادِ بانک، مقایسۀِ بیرونی و زنجیرۀِ 27a445b3
1c1d0be5|2026-10-19|docs(closure): SHAِ زنجیره ازِ لاگ‌ها خوانده شد، نه ازِ HEADِ روزِ سند + بازیافتِ گیت ثبت شد
```

فایل‌هایِ دست‌خورده درِ همین بازه (`git diff --name-only 146b5acd..HEAD`):

```
_audit/ADJUSTED-FACTOR-STEPS.csv
_audit/RA365-COMPARE-MATRIX.csv
_audit/chart_drawing_matrix_v4.csv
_audit/chart_drawing_matrix_v4.js
_audit/fetch_event_window.py
_audit/gen_engine1_closure_doc.py
_audit/unresolved_events_probe.py
dev/price_last_value_v1070.py
dev/run_all_tests.py
docs/technical-indicators/reviewed/ENGINE-1-CLOSURE-1405-07-27.md
frontend/src/features/technical/lib/drawStore.ts
frontend/src/features/technical/nahayatnegar/components/KLineChartWrapper.tsx
```

## ۵) بازها: UNRESOLVED / NOT_RUN / UNMEASURABLE / NOT_OBSERVED

۱. سه پلۀِ تعدیلِ فولاژ/لخزر/ولراز — علتشان درِ §۳ با ردیفِ رسمی سنجیده شد (تکلیفِ «کجا پله بگذارد»)، اما اینکه کدامِ قراردادِ تاریخ‌گذاری مرجع است هنوز **UNRESOLVED** است؛ رفعش دفترِ رویدادِ رسمیِ همان ins_code می‌خواهد، نه ضریبِ ساخته‌شدہ.
۲. دو پلۀِ تعدیلِ فولاد درِ ۲۰۰۷ و ۲۰۰۸ — پیشِ نخستینِ ردیفِ دفتر؛ **UNRESOLVED**.
۳. مقایسۀِ دیداریِ زنده با رهاورد — **NOT_OBSERVED** (نشستِ معتبرِ مرورگرِ مالک درِ این دسترس نبود؛ دستورِ رفع درِ §۳ نوشته شده).
۴. ماتریسِ ابزارها — شمارِ عملیات‌هایِ غیرِ PASS درِ §۱٫۳ آمده است: رسم `FAIL`=۰/`NOT_RUN`=۰، ماندگاری `FAIL`=۰/`UNMEASURABLE`=۰، ویرایش `FAIL`=۹/`UNMEASURABLE`=۰، حذفِ منزوی `NOT_RUN`=۰. تک‌تکِ این‌ها با علت درِ §۱٫۵ ثبت شده و هیچ‌کدام PASS اعلام نشده‌اند.
۵. دسترسی از رابط: `UNREACHABLE`=۰ از ۲۹ شناسه.
۶. ردیف‌هایِ روزِ بی‌معامله: قراردادِ ما «کندل نمی‌سازد»، رهاورد می‌رسمد؛ تفاوتِ نمایشیِ مستند، بی‌تغییرِ داده.
۷. **پس‌گرفته‌شدہ:** علتِ «`no-official-rows-for-instrument`: هیچ ردیفِ رسمیِ ولراز درِ بانک نیست» که درِ سندِ دورِ پیش برایِ ولراز ۲۰۲۴-۰۱-۳۰ نوشته شده بود، **غلط** است: `ins_code = 12901875871456398` درِ `instruments` هست، `price_history` ۴۹۲ ردیفِ این نماد دارد و CSVِ رسمیِ همان پنجره ۳٬۴۹۱ ردیف برگرداند (`_audit/fetch_event_window.py`). علتِ درستِ اختلاف درِ §۳ ثبت شده است.
۸. ردیفِ ماندۀِ «خط اطلاعاتی» (priceLine): درِ مسیرِ «رسم ← بازخوانی ← رسمِ دوم ← حذفِ یکی»، موتور ۱ ترسیم دارد و انبار ۲ ردیف (پس ازِ ۱۲ ثانیه انتظار). درِ همان فیلد برایِ «خط عمودی» پیش‌تر همین اتفاق می‌افتاد و با پاک‌کردنِ فهرستِ محافظت‌شدہ درِ حذفِ صریح برطرف شد؛ این یکی **باز** است. سنجشِ کنترلیِ بی‌بازخوانیِ میانی (`_scratch/live/probe_delete_resurrect.json`) همین مسیر را سالم نشان می‌دهد (۲→۱ و پس ازِ reload همان ۱)، پس نقص به مسیرِ «ترسیمِ بازگردانده‌شده + حذف» مخصوص است و علتش هنوز اثبات نشده: **UNRESOLVED**.
