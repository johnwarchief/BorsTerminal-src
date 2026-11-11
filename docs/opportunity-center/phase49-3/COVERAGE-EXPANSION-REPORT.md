# گزارش Phase 4.9.3 — گسترش پوشش و آمادگی Seed

**وضعیت نهایی: `BLOCKED_CAPTURE_REQUIRED`**

ماتریس کامل ۶٬۱۰۳ نماد ساخته و آشتی داده شد؛ گروه ۳۰ نمادی جدید به‌صورت قطعی و
بازتولیدپذیر انتخاب و منجمد شد؛ فرصت واقعی افزایش پوشش از **Capture موجود** کمی‌سازی
شد. پردازش سرتاسری گروه ۳۰ انجام **نشد**، چون بایت‌های Capture جفت‌شدهٔ type0/type7
روی این ماشین present نیستند. هیچ داده‌ای ساخته نشد، هیچ Capture جعلی تولید نشد،
و هیچ‌یک از دو دیتابیس خط‌قرمز تغییر نکرد.

---

## ۱. مبنای Git

| مورد | مقدار |
| --- | --- |
| مخزن | `johnwarchief/BorsTerminal-src` |
| شاخهٔ مأموریت | `mission/phase49-3-coverage-expansion-2026-11-11` |
| کامیت پایه | `e09ccd95d51c94082640cda75ef3de2b2008f9d2` |
| Worktree | `E:\bors_work\phase49-3` — مستقل، روی شاخهٔ مأموریت، ساخته‌شده دقیقاً از `e09ccd95` |
| `main` | `2c3e87265ddb5ee71513c9bc28a24e73c398e6c9` — **دست‌نخورده** |
| فایل‌های مالک در `main` | `docs/Indicator/` و `docs/technical-indicators/inbox/` — حذف یا بازنویسی نشدند |
| Rebase / Merge / Cherry-pick / Tag / Release | هیچ‌کدام انجام نشد |
| Worktreeهای موجود | هر ۵۰ عدد حفظ شدند |

نکتهٔ راستی‌آزمایی: checkout اصلی روی `mission/phase48-closeout-2026-11-09` در
`9d348b64` بود، نه روی شاخهٔ پایهٔ مأموریت. شاخهٔ پایه
`mission/phase49-full-verification-python-ci-2026-11-10` فقط به‌صورت remote-tracking
موجود بود و tip آن با `git ls-remote github` دقیقاً `e09ccd95` تأیید شد؛ `main` نیز
روی `2c3e8726` تأیید شد. سپس Worktree مستقل ساخته شد؛ هیچ checkout موجودی
جابه‌جا نشد.

موتور Phase 4.9.2 **بایت‌به‌بایت تغییر نکرد**. `git diff e09ccd95 -- backend-go/`
خالی است و stage04 در صورت غیرخالی‌بودن آن abort می‌کند.

---

## ۲. چه چیزی اندازه‌گیری شد، چه چیزی نه

| قلم | وضعیت | مبنا |
| --- | --- | --- |
| ماتریس پوشش ۶٬۱۰۳ نماد | **PASS** | فقط از ledgerهای کامیت‌شده با SHA پین‌شده |
| آشتی همهٔ مخرج‌ها | **PASS** | هر اتحاد به‌صورت assertion در کد؛ drift ⇒ abort |
| انتخاب و انجماد گروه ۳۰ | **PASS** | قطعی، بدون RNG و بدون ساعت؛ بازاجرا بایت‌یکسان |
| شواهد سطح‌رویداد گروه ۳۰ | **PARTIAL** | استخراج‌شده از اندازه‌گیری قبلی، نه اندازه‌گیری جدید |
| پردازش سرتاسری گروه ۳۰ (کندل/Parity) | **BLOCKED** | بایت‌های Capture غایب‌اند |
| آزمون محصول روی کپی مستقل DB | **NOT_MEASURED** | هیچ DB سازگار با Runtime present نیست |
| Screenshot واقعی UI | **NOT_MEASURED** | گرفته نشد؛ آزمون API هرگز UI نامیده نمی‌شود |
| موتور دست‌نخورده + سوئیت‌های Go | **PASS** | ۵۵ بسته ok، صفر شکست، `go vet` exit 0 |
| پروفایل production | **PASS** | exit 0، ALL SUITES PASSED |
| پروفایل data | **FAIL از پیش موجود** | ۵ سوئیت؛ کنترل روی کامیت پایه counts یکسان داد |
| CI واقعی روی کامیت نهایی | جداگانه | `CI-FINAL-RESULTS.json` با SHA خودش |

---

## ۳. ماتریس پوشش: مخرج‌ها و آشتی

ماتریس: `COVERAGE-EXPANSION-MAP.csv` — **۶٬۱۰۳ ردیف × ۶۴ ستون**، یک ردیف به‌ازای
هر نماد `price_history`. هیچ DBای باز نشد؛ تنها ورودی‌ها دو ledger کامیت‌شده‌اند
که SHA آن‌ها با شواهد ثبت‌شده مطابقت دارد:

| ورودی | SHA-256 | نتیجه |
| --- | --- | --- |
| `HISTORY-COVERAGE-LEDGER.csv` | `c3ad3741daaa55b849fb51aca7cc066ea859d0469de2eb85d82471988a69a650` | مطابق ثبت |
| `ADJUSTMENT-EVIDENCE-LEDGER.csv` | `c0ab45bf60ba8d95fa4f4f33d60d4fa6f465a62c07271053c8ca7781f5114a28` | مطابق ثبت |

### ۳.۱ طبقه‌بندی اولویت‌دار (جمع = ۶٬۱۰۳)

این شش وضعیت **طبقه‌بندی نهایی اولویت‌دار** هستند و با علت‌های خام هم‌پوشان جمع
نمی‌شوند. نردبان عیناً از `build_coverage_ledger.py` بازتولید شد و ماتریس در صورت
هر drift نماد‌به‌نماد نسبت به `COVERAGE-STATUS.csv` شکست می‌خورد.

| وضعیت | تعداد |
| --- | --- |
| `READY_PILOT` | ۳۰ |
| `QUEUE_REFERENCE_ONLY` | ۶۷۵ |
| `QUEUE_NO_REFERENCE` | ۳٬۳۰۸ |
| `QUEUE_NO_INSTRUMENTS` | ۱٬۴۶۸ |
| `QUEUE_HALTED` | ۴۳۱ |
| `QUEUE_UNMAPPED_ASSET_ID` | ۱۹۱ |
| **جمع** | **۶٬۱۰۳** |

### ۳.۲ علت‌های خام (هم‌پوشان — با بالا جمع نکنید)

| علت خام | تعداد |
| --- | --- |
| `ref_coverage = full` | ۷۵۹ |
| `ref_coverage = none` | ۵٬۳۴۴ |
| `stale_status = halted` | ۴۴۴ |
| بدون instruments | ۱٬۴۶۸ |
| asset_id نقشه‌نشده | ۱۹۱ |
| `step_rows = 0` | ۵٬۱۸۸ |

### ۳.۳ اتحادها (همه به‌صورت assertion اثبات شدند)

| اتحاد | تفکیک |
| --- | --- |
| ۵٬۳۴۴ = ۱۹۱ + ۱٬۴۶۸ + ۳۷۷ + ۳٬۳۰۸ | `ref_none` → unmapped / no-instruments / haltedِ جذب‌شده / `QUEUE_NO_REFERENCE` |
| ۷۵۹ = ۳۰ + ۵۴ + ۶۷۵ | `ref_full` → pilot / haltedِ جذب‌شده / `QUEUE_REFERENCE_ONLY` |
| ۴۴۴ = ۱۱ + ۲ + ۴۳۱ | halted → جذب‌شده در unmapped/no-instruments / pilot (`غدشت`، `وپارس`) / `QUEUE_HALTED` |

### ۳.۴ گرهٔ `۵٬۱۸۵` در برابر `۳٬۳۰۸` — دو جمعیت متفاوت، نه تناقض

هیچ‌کدام از دو عدد حذف یا «اصلاح» نشد. تفاوت با join واقعی و منطق
`build_coverage_ledger.py` توضیح داده شد:

- **۵٬۱۸۵** = نمادهای `step_rows = 0` **و** `ref_coverage = none`، **پیش از** نردبان اولویت.
- **۳٬۳۰۸** = نمادهای بدون Reference **پس از** کناررفتن identity / asset-id / halt.

| تفکیک ۵٬۱۸۵ بر اساس وضعیت نهایی | تعداد |
| --- | --- |
| `QUEUE_NO_INSTRUMENTS` | ۱٬۴۶۷ |
| `QUEUE_NO_REFERENCE` | ۳٬۲۱۹ |
| `QUEUE_UNMAPPED_ASSET_ID` | ۱۳۵ |
| `QUEUE_HALTED` | ۳۶۴ |
| **جمع** | **۵٬۱۸۵** |

و `۳٬۳۰۸ = ۳٬۲۱۹ بدون‌step + ۸۹ دارای‌step`. همچنین ۱۵۹ نماد `ref_none` دارای
pack step هستند که این‌گونه پخش می‌شوند: ۵۶ unmapped + ۸۹ no-reference + ۱۳ halted
+ ۱ no-instruments. آن یک نماد `فيروزه2` است و این با یادداشت ثبت‌شدهٔ
`_audit/phase49-full-verification/evidence/ledger-counts.json:226`
(`no_instrument_note`) و `docs/opportunity-center/phase49/UNVERIFIED-RECONCILIATION.md:114`
می‌خواند: «1,468 history symbols have no instruments row; 1,467 of them have zero
steps … One (فيروزه2) carries a pack step».

### ۳.۵ تفکیک ۷۵۶ / ۳

۷۵۹ نماد Reference دارند؛ **۷۵۶** دارای Factor Change و **۳** بدون آن:
`طلا`، `نيك گستر`، `پادا`. این تفکیک با `factor_steps` بازتولید شد (نه `step_rows`)
— دقیقاً همان فیلدی که `stage05_symbol_ledger.py:1023-1024` استفاده می‌کند.

### ۳.۶ eligibility

| `verification_eligible` | تعداد |
| --- | --- |
| YES | ۷۵۸ |
| NO | ۵٬۳۴۵ |

۷۵۸ = ۷۵۹ منهای `آواپارس` (هویت مبهم، دو instrument candidate). شرط YES:
`ref_coverage = full` **و** `identity_status = resolved_instruments` **و**
`raw_ohlc_valid = ok`.

---

## ۴. کشف جدید: `ref_coverage = full` تضمین بازه است، نه کامل‌بودن نشست‌ها

این نکته در شواهد قبلی صریح نبود و اکنون به‌عنوان ستون مستقل ماتریس ثبت شده است.

تعریف `full` در `stage05_symbol_ledger.py:592-597` این است که **هم type0 و هم
type7** اولین و آخرین تاریخ محلی را پوشش بدهند. این تضمین **بازه** است؛ تضمین
نمی‌کند که به‌ازای هر نشست محلی یک bar مرجع وجود دارد.

| `session_completeness` | تعداد |
| --- | --- |
| `REFERENCE_SUPERSET` (بار مرجع بیشتر از نشست محلی) | ۷۴۷ |
| `REFERENCE_MISSING_n_SESSIONS` (کسری نشست) | ۱۲ |
| `NO_REFERENCE` | ۵٬۳۴۴ |
| `EQUAL` | ۰ |

۱۲ نماد با کسری نشست (بزرگ‌ترین‌ها):

| نماد | نشست محلی | bar مرجع type0 | کسری |
| --- | --- | --- | --- |
| `مبين` | ۲٬۶۴۱ | ۲٬۳۹۲ | ۲۴۹ |
| `شبندر` | ۲٬۹۰۸ | ۲٬۸۱۵ | ۹۳ |
| `شتران` | ۲٬۸۰۲ | ۲٬۷۲۷ | ۷۵ |
| `معين` | ۴۹۵ | ۴۹۰ | ۵ |
| `هانيكو` | ۱۵۷ | ۱۵۵ | ۲ |
| ۷ نماد دیگر | — | — | هرکدام ۱ |

برای هر ۱۲ نماد `duplicate_dates = 0` تأیید شد؛ پس این کسری **artifact تاریخ
تکراری نیست** و به‌عنوان نقص واقعی پوشش ثبت شد، نه هموارسازی خاموش.

**پیامد برای Parity:** حضور در Reference Index به‌تنهایی existence سری type7
adjusted OHLC را ثابت نمی‌کند. type0 بدون شاهد type7 برای اعلام Parity کافی نیست.
ماتریس این دو را در ستون‌های جدا نگه می‌دارد:
`paired_type0_type7_evidenced` در برابر `local_capture_bytes`.

---

## ۵. فرصت واقعی افزایش پوشش — بدون Capture جدید

**پاسخ به پرسش اصلی مأموریت: بله.** دادهٔ Phase 4.9 و Captureهای قبلی اجازه می‌دهند
**۶۷۵ نماد** `QUEUE_REFERENCE_ONLY` (به‌علاوهٔ ۵۴ نماد halted) بدون هیچ درخواست
شبکه‌ای جدید بازیابی شوند، چون `ref_coverage = full` وجود جفت type0/type7 را برای
بازهٔ محلی **اثبات می‌کند** و آن Capture قبلاً گرفته شده است.

| کلاس بازیابی | تعداد | منبع لازم برای رفع Block |
| --- | --- | --- |
| `RECOVERABLE_EXISTING_CAPTURE` | ۶۷۵ | فقط بازیابی بایت‌های Capture موجود |
| `RECOVERABLE_HALTED_EXISTING_CAPTURE` | ۵۴ | رأی مالک دربارهٔ halted + همان Capture |
| `NEEDS_NEW_CAPTURE` | ۳٬۳۰۸ | Capture جدید جفت‌شده |
| `NEEDS_IDENTITY_RESOLUTION` | ۱٬۴۶۸ | ردیف instruments / حل هویت |
| `NEEDS_HALT_RULING_AND_CAPTURE` | ۳۷۷ | رأی مالک + Capture جدید |
| `NEEDS_ASSET_ID_MAPPING` | ۱۹۱ | نقشهٔ asset-id |
| `ALREADY_VERIFIED` | ۳۰ | — |

### ۵.۱ کمی‌سازی افزایش ردیف

سابقهٔ pilot قبلی: `ref_days == pilot_raw_rows` برای **۳۰/۳۰** نماد، و
۳۴٬۲۴۷ ردیف seed → ۱۰۵٬۶۹۲ ردیف ingest‌شده (۳٫۰۹ برابر). پس `ref_days`
(شمار bar روزانهٔ type0 per-symbol از فهرست مرجع) پیش‌بینی معتبری است.

| جمعیت | ردیف seed | bar مرجع type0 | افزایش | ضریب |
| --- | --- | --- | --- | --- |
| pilot قبلی (۳۰) | ۳۴٬۲۴۷ | ۱۰۵٬۶۹۲ | +۷۱٬۴۴۵ | ۳٫۰۹× |
| `QUEUE_REFERENCE_ONLY` (۶۷۵) | ۲۷۴٬۶۳۵ | ۱٬۸۴۲٬۶۹۵ | **+۱٬۵۶۸٬۰۶۰** | ۶٫۷۱× |
| halted با Reference (۵۴) | — | ۱۵۳٬۳۶۵ | مشروط به رأی مالک | — |
| گروه جدید (۳۰) | ۲۸٬۰۵۱ | ۸۴٬۴۵۲ | **+۵۶٬۴۰۱** | ۳٫۰۱× |

این اعداد **EVIDENCED EXPECTATION** از فهرست کامیت‌شده‌اند، نه اندازه‌گیری محلی:
بایت‌های Capture روی این ماشین نیستند. جمع `ref_days` روی ۷۵۹ نماد `ref_full`
دقیقاً ۲٬۱۰۱٬۷۵۲ می‌شود که با `factor_days` ثبت‌شده در `capture-summary.json`
مطابقت دارد — این یک cross-check مستقل است.

### ۵.۲ شواهد Capture موجود

| مورد | مقدار |
| --- | --- |
| نمادهای merge‌شده | ۷۵۹ |
| bar روزانه type0 | ۲٬۶۲۰٬۴۸۲ |
| bar روزانه type7 | ۲٬۶۲۰٬۴۸۲ |
| کل bar روزانه (D) | ۴٬۲۰۳٬۵۰۴ |
| `factor_days` فهرست | ۲٬۱۰۱٬۷۵۲ |
| `factor_changes` فهرست | ۱۳٬۹۲۱ |
| SHA ظرف bars | `272336c036d647ed7b2090853c84c3a2d3da6126a0bfae60e987198169b3b14a` |
| SHA فهرست مرجع | `83544012448fc19100e7b140dbcfc2e4d27eca317f667204c343f810acc92e1c` |
| `raw_capture_committed` | `false` (licensed، gitignored) |

---

## ۶. گروه ۳۰ نمادی جدید

`COHORT-SELECTION.json` — منجمد، قطعی، **کاملاً مجزا از ۳۰ نماد قبلی**.

- **استخر:** ۶۷۳ نماد از ۶۷۵ `QUEUE_REFERENCE_ONLY`. دو نماد کنار گذاشته شدند:
  `آواپارس` (هویت مبهم: دو instrument candidate) و `هانيكو` (asset_id خالی).
  هیچ نماد مبهم‌الهویت / بدون instruments / بدون asset-id / halted صرفاً برای
  رسیدن به عدد ۳۰ وارد نشد.
- **روش:** ۱۲ لایه (stratum) با هدف‌های جمعاً ۳۰؛ درون هر لایه مرتب‌سازی
  «متریک نزولی، نماد صعودی» و انتخاب موقعیت‌های evenly-spread. **بدون RNG، بدون
  ساعت.** بازاجرا بایت‌یکسان است.
- **نوع رویداد** فقط از `share_change_events` / `price_adjust_events` خوانده شد؛
  هرگز از روی نسبت حدس زده نشد.

| لایه | هدف | استخر منطبق | نمادها |
| --- | --- | --- | --- |
| `LONG_HISTORY_DENSE_EVENTS` | ۳ | ۱۱ | `كگل`، `وغدير`، `دزهراوي` |
| `LONG_HISTORY_SPARSE_EVENTS` | ۳ | ۴۱ | `دكيمي`، `سصوفي`، `خمحور` |
| `SHORT_HISTORY` | ۳ | ۴۶ | `آكو`، `شمس`، `امين شهر` |
| `MID_HISTORY` | ۳ | ۴۶۶ | `بسويچ`، `ريشمك`، `نخريس` |
| `CAPITAL_INCREASE_EVIDENCED` | ۴ | ۱۷۲ | `فملي`، `نطرين`، `پرديس`، `وكغدير` |
| `PRICE_ADJUST_EVIDENCED` | ۳ | ۱۹۵ | `فولاي`، `ثغرب`، `ومپنا` |
| `CAPTURE_ONLY_MEASURED_RATIO` | ۳ | ۱۸۳ | `هماي`، `لخانه`، `گوهر` |
| `RATIO_CONFLICT_PRESENT` | ۳ | ۷۶ | `كسعدي`، `وتجارت`، `شگستر` |
| `HISTORICAL_ANOMALY` | ۲ | ۳۴ | `مبين`، `تاصيكو` |
| `REFERENCE_SESSION_DEFICIT` | ۱ | ۱۰ | `شبندر` |
| `FRESH_SERIES` | ۱ | ۲۱ | `ومعادن` |
| `REFERENCE_WITH_ZERO_STEPS` | ۱ | ۲ | `پادا` |

هر ۱۲ لایه پر شدند. املای نمادها عیناً همان املای خام داده است (مثلاً `كگل` با
ك عربی) تا joinها قابل ردیابی بمانند.

### ۶.۱ تنوع واقعی

| سنجه | مقدار |
| --- | --- |
| بازهٔ bar خام مورد انتظار | ۵۲ تا ۶٬۹۶۲ |
| جمع bar خام مورد انتظار | ۸۴٬۴۵۲ |
| جمع ردیف seed | ۲۸٬۰۵۱ |
| افزایش مورد انتظار | +۵۶٬۴۰۱ |
| سال‌های شروع متمایز | ۲۴ سال، از ۱۹۹۲ تا ۲۰۲۶ |
| `step_rows` | ۰ تا ۷۷ (جمع ۴۸۷) |
| `factor_steps` (پس از merge) | جمع ۴۶۸ |
| دارای شواهد افزایش سرمایه | ۱۷ |
| دارای شواهد price-adjust | ۲۰ |
| دارای step اندازه‌گیری‌شدهٔ فقط‌Capture | ۲۸ |
| دارای تعارض نسبت | ۱۰ |
| دارای ناهنجاری تاریخی | ۳ |
| دارای کسری نشست | ۲ (`شبندر`، `مبين`) |
| تازگی | fresh ۶، recent ۲۱، stale ۳ |
| ریسک Price Basis | **۳۰/۳۰ `LEGACY_UNKNOWN_PRESENT`** |

---

## ۷. آنچه برای گروه ۳۰ واقعاً اندازه‌گیری شد

دو چیز کاملاً جدا گزارش می‌شوند و هرگز با هم مخلوط نمی‌گردند:

### ۷.۱ سطح رویداد — **PARTIAL** (استخراج‌شده، نه اندازه‌گیری جدید)

`ADJUSTMENT-EVIDENCE-LEDGER.csv` حاوی اندازه‌گیری‌ای است که
`stage03_step_ledger.py` در Phase 4.9 full-verification **قبلاً** انجام داده و
کامیت شده است. این مرحله آن را با کلید هویت استاندارد پروژه بازکلیدگذاری و
جمع می‌کند. **هیچ Parity کندلی ادعا نمی‌شود.**

تلورانس‌های منجمد فقط نقل شدند، تغییر نکردند:
`FACTOR_EXACT = 0.001`، `FACTOR_MATERIAL = 0.01`،
`STEP_DATE_SHIFT_MAX_DAYS = 5`، `DEDUPE_RATIO_TOL = 0.01`.

**اعتبار join اثبات شد، فرض نشد:** گروه‌بندی ledger رویداد با
`dev/symbol_identity.py:key` (همان ماژولی که stage05 استفاده می‌کند) باید
`step_rows` و `factor_steps` هر نماد را بازتولید کند. نتیجه: **۳۰/۳۰ و ۳۰/۳۰**.

این join حیاتی است: ۶ نماد گروه stepهایی تحت **املای دوم** دارند. join با املای
خام ۴۸۷ ردیف را به ۳۵۷ کاهش می‌داد و ۶ نماد را silent خراب می‌کرد. کنترل منفی
این را ثابت می‌کند (بخش ۹).

| سنجه | مقدار |
| --- | --- |
| ردیف رویداد join‌شده | ۴۹۳ |
| ردیف معتبر | ۴۸۷ |
| `INVALID_DROPPED` | ۶ |
| تاریخ‌های متمایز (= `factor_steps`) | ۴۶۸ |
| `MATCH` | ۳۳۱ |
| `PARTIAL` | ۴۳ |
| `MISMATCH` | ۶۷ |
| `NO_EVIDENCE` | ۴۶ |
| شاهد O1 (رسمی) | ۱۳۹ |
| شاهد R1 (مرجع Capture) | ۴۰۸ |
| شاهد O2 (کدال) | ۰ |
| دارای `ref_ratio` | ۳۳۶ |
| دارای `prod_ratio` | ۴۸۳ |

جمع ۳۳۱ + ۴۳ + ۶۷ + ۴۶ = ۴۸۷ ✓

| وضعیت سطح‌رویداد | تعداد | نمادها |
| --- | --- | --- |
| **PASS** | ۴ | `آكو`، `امين شهر`، `هماي`، `گوهر` |
| **PARTIAL** | ۲۵ | باقی |
| **NOT_MEASURED** | ۱ | `پادا` (صفر ردیف رویداد — همان لایهٔ Reference با zero step) |

وضعیت نهایی رویدادها: `VERIFIED_REFERENCE` ۲۷۲، `CONFLICT_RATIO` ۶۷،
`INSUFFICIENT_EVIDENCE` ۴۴، `VERIFIED_MULTI_SOURCE` ۴۴، `PARTIAL_REFERENCE` ۲۶،
`PARTIAL_OFFICIAL` ۱۷، `VERIFIED_OFFICIAL` ۱۳، `RECONSTRUCTED_AUDITED` ۲،
`CONFLICT_DUPLICATE` ۲.

علت‌های اختلاف: `UNRESOLVED_SOURCE_GAP` ۴۴، `EVENT_RATIO_MISMATCH` ۳۵،
`SOURCE_MISMATCH` ۳۲، `SYMBOL_IDENTITY_MISMATCH` ۲.

۱۰ نماد دارای `MISMATCH` هستند: `تاصيكو`، `دزهراوي`، `شگستر`، `فملي`، `كسعدي`،
`كگل`، `نخريس`، `وتجارت`، `وغدير`، `ومعادن`. این‌ها **تعارض‌های ثبت‌شدهٔ قبلی**
اند، نه نقص جدید. بدون شاهد معتبر بازنویسی نشدند؛ نسبت و provenance حفظ شد.
۴۶ ردیف `NO_EVIDENCE` هرگز verified ثبت نشدند.

### ۷.۲ هویت — بررسی شد، فرض نشد

| بررسی | نتیجه |
| --- | --- |
| `ins_code` / `asset_id` هر ۳۰ نماد در برابر ledger تاریخچه | **۳۰/۳۰ CONSISTENT** |
| ردیف‌های دارای `SYMBOL_IDENTITY_MISMATCH` | ۲ |
| ردیف‌های واقعاً wrong-instrument | **۰** |

آن ۲ ردیف (`كسعدي` ۲۰۲۰-۰۵-۲۶ و `كگل` ۲۰۱۳-۰۷-۱۶) هر دو `CONFLICT_DUPLICATE`
اند و `ins_code`شان دقیقاً با ledger تاریخچه یکی است. معنای دقیق این cause در
`stage03_step_ledger.py:395-401,570-571`: **دو املای خام از یک کلید، روی یک
تاریخ، با اختلاف نسبت بیش از `DEDUPE_RATIO_TOL`**. این تعارض املای alias است،
نه هویت instrument اشتباه. صریح در شواهد فهرست شد تا aggregate پنهانش نکند.

### ۷.۳ سطح کندل — **BLOCKED** برای هر ۳۰ نماد

`BLOCKED_CAPTURE_BYTES_ABSENT`. هیچ‌کدام از این‌ها انجام نشد:
ingest خام/adjusted، محاسبهٔ نسبت type0/type7، ساخت Factor، اجرای `candlebuild`،
مقایسهٔ OHLC با مرجع، بررسی ثبات حجم، اثبات Revision / Update Chain / Idempotency.

علت دقیق Block — و این تمایز مهم است:

> Capture جفت‌شدهٔ type0/type7 **قبلاً گرفته شده و وجودش اثبات شده است**
> (۷۵۹ نماد، ۲٬۶۲۰٬۴۸۲ bar برای هر type، SHA ثبت‌شده). آنچه غایب است **بایت‌های**
> آن روی این ماشین است، چون دادهٔ licensed و gitignored است.
> این «نبود نشست معتبر» نیست و «نبود Reference» هم نیست.

---

## ۸. برنامهٔ دقیق رفع Block

`capture-restore-plan.json` — وضعیت `BLOCKED_CAPTURE_REQUIRED`.

### ۸.۱ مسیر ترجیحی: بازیابی، نه Capture جدید

`new_network_capture_needed: false`

| مصنوع | SHA-256 ثبت‌شده |
| --- | --- |
| `_audit/phase49-full-verification/captures/bars-all.ndjson.gz` | ظرف `272336c0…`، payload `6aec345f…` |
| `_audit/phase49-full-verification/captures/reference-index-all.json` | `83544012…` |

پس از بازیابی: SHA هر دو دوباره محاسبه و با مقادیر ثبت‌شده مقایسه شود؛ عدم
مطابقت ⇒ abort پیش از هر ingest. سپس یک **کپی کاری جدید** زیر
`_audit/phase49-3/db/` ساخته شود — هرگز خود Seed Candidate و هرگز کپی Pilot روی آن.

### ۸.۲ مسیر جایگزین: فقط اگر بازیابی ناممکن بود

پیش‌شرط: یک نشست **از قبل authenticated** Rahavard که مالک مجاز کرده باشد.
**هیچ رمز عبور یا اطلاعات ورودی درخواست یا ذخیره نشد و نمی‌شود.**
اگر نشست معتبر نبود: داده ساخته نمی‌شود، Capture جعلی تولید نمی‌شود، وضعیت
همان `BLOCKED_CAPTURE_REQUIRED` می‌ماند.

| پارامتر | مقدار |
| --- | --- |
| endpoint | `https://rahavard365.com` |
| types | `type0` + `type7` (جفت‌شده) |
| resolution | `D` |
| countback | ۱۰۰٬۰۰۰ |
| from | `1990-01-01T00:00:00Z` |
| نمادها | ۳۰ نماد منجمد (فهرست در JSON) |
| کندل روز Capture | **قرنطینه** — هرگز وارد زنجیرهٔ تعدیل نمی‌شود |

هر Capture باید ثبت کند: هویت نماد (key، ins_code، asset_id)، تاریخ واکشی،
آخرین نشست کامل، نوع سری، resolution و SHA-256.

---

## ۹. قرارداد Runtime و آمادگی محصول

`product-readiness.json` — **۲ PASS، ۶ NOT_MEASURED**. هیچ آزمون محصولی ادعا نشد.

### ۹.۱ آنچه از سورس کامیت‌شده استخراج و تأیید شد (۱۰ probe، همه locate شدند)

| مورد | مقدار | citation |
| --- | --- | --- |
| جدولی که Runtime می‌خواند | `adjustment_factors` | `backend-go/internal/chart/measured.go:15` |
| ستون‌ها | `date, ratio, kind, revision` | همان |
| جدول خام جدا | `reference_raw` | `backend-go/internal/chart/measured.go:53` |
| برچسب رویداد Factor | `rahavard-type7-type0` | `backend-go/internal/chart/measured.go:33` |
| برچسب ردیف خام | `rahavard-type0` | `backend-go/internal/chart/measured.go:95` |
| اثر revision | revision غیرخالی ⇒ source = `local-measured-factors` | `backend-go/internal/chart/chartdb.go:394` |
| خروجی‌های `candlebuild` | `adjusted_candles`، `adjustment_verification`، `candle_build_revisions` | `backend-go/internal/candlebuild/candlebuild.go:22,26,31` |
| محرک build | `SELECT DISTINCT symbol FROM adjustment_factors` | `backend-go/internal/candlebuild/candlebuild.go:94` |
| مسیر API | `GET /api/chart-db/{symbol}` | `backend-go/internal/httpapi/server.go:264` |

**نکتهٔ مهم برای تصمیم مالک:** Runtime مستقیماً `adjustment_factors` و
`reference_raw` را می‌خواند؛ `adjusted_candles` خروجی materialize‌شدهٔ build است،
نه مسیر خواندن Runtime. پس سازگاری کپی کاری با Runtime باید روی آن دو جدول
سنجیده شود.

### ۹.۲ چرا آزمون محصول NOT_MEASURED است

| ورودی لازم | present؟ |
| --- | --- |
| Seed Candidate DB | خیر |
| Pilot DB | خیر |
| bars-all.ndjson.gz | خیر |
| reference-index-all.json | خیر |
| pilot-capture.json | خیر |

**۰ از ۵.** تنها DB موجود در Worktree، `market.db` **کامیت‌شده در Git** است
(کامیت `d081d741`): ۲۶٬۳۷۸٬۲۴۰ بایت، ۲٬۲۰۹ ردیف `price_history`، ۳٬۶۸۰
instruments، و **هیچ‌یک** از شش جدول تعدیل را ندارد. این نه Seed Candidate است
(۲۸۱٬۰۸۸٬۰۰۰ بایت / ۵۴۴٬۲۸۴ ردیف) و نه Pilot (۳۶۴٬۶۷۰٬۹۷۶ بایت).
SHA آن `c0979d4e…` است و با هیچ‌یک از دو SHA خط‌قرمز یکی نیست.

این DB فقط read-only و `immutable=1` باز شد؛ `git status` آن پاک ماند.
DB نصب‌شدهٔ Production (که `-wal` و `-shm` فعال دارد) **هرگز باز، کپی یا
تغییر داده نشد**.

ساختن کپی کاری بدون این ورودی‌ها یعنی جعل داده، که مأموریت ممنوع کرده است.
بنابراین هیچ کپی‌ای ساخته نشد و همهٔ قلم‌های آزمون محصول `NOT_MEASURED` ماندند.

---

## ۱۰. تست‌ها و CI

ساختار کامیت: کامیت نخست همهٔ مصنوعات را می‌برد و CI روی همان SHA اجرا می‌شود؛
`CI-FINAL-RESULTS.json` و manifest بازتولیدشده در کامیت docs-only بعدی اضافه
می‌شوند، چون فایل نمی‌تواند نتیجهٔ CI روی خودش را در خود داشته باشد. هر دو SHA
در گزارش نهایی به مالک نام برده می‌شوند.

### ۱۰.۱ Go

| آزمون | نتیجه |
| --- | --- |
| `go test ./internal/chart ./internal/candlebuild -count=1` | ok، exit 0 |
| `go test ./... -count=1` | **۵۵ بسته ok**، ۳ بسته بدون فایل تست، **۰ شکست**، exit 0 |
| `go vet ./...` | exit 0 |

نسخه: Go 1.27.3 windows/amd64 (همان نسخهٔ CI).

### ۱۰.۲ گیت‌های ساختاری (همه exit 0)

| گیت | verdict |
| --- | --- |
| `dev/test_workflows_layout.py` | WORKFLOW LAYOUT TESTS OK |
| `scripts/test_check_seed_release.py` | SEED RELEASE GATE TESTS OK + EDGE CASES OK |
| `dev/suite_registry_guard.py` | SUITE REGISTRY GUARD OK: 260 suites |
| `dev/phase49_rules_guard.py` | STATUS RULES GUARD OK |
| `dev/persian_glyph_guard.py` | 4 passed / 0 failed |

### ۱۰.۳ پروفایل‌ها

| پروفایل | exit | suite counted | silent | skipped | نتیجه |
| --- | --- | --- | --- | --- | --- |
| `--profile production` | ۰ | ۱۳ | ۱ | ۰ | **ALL SUITES PASSED** |
| `--profile data` | ۱ | ۲۰ | ۱۴ | ۲ | ۵ سوئیت FAIL |

هر دو اجرا `PROTECTED_DB_UNCHANGED` دادند.

### ۱۰.۴ شکست‌های پروفایل data: از پیش موجود، با کنترل اثبات شد

**هیچ سوئیت، گارد یا آستانه‌ای تغییر، skip یا ضعیف نشد.**

۵ سوئیت شکست‌خورده و علت ریشه‌ای:

| سوئیت | passed/failed | علت |
| --- | --- | --- |
| `dev/test_board_fixture_v1120.py` | ۵ / ۱ | `No module named 'fastapi'` |
| `dev/test_chart_fixture_b3.py` | ۴۴ / ۳ | `No module named 'fastapi'` |
| `dev/test_fundamental_fixture_b4.py` | ۴۳ / ۲ | `No module named 'fastapi'` |
| `dev/test_fundamental_vectors_b4.py` | ۱ / ۱ | `No module named 'fastapi'` |
| `dev/fts_notebook_examples_v1089.py` | ۳۵ / ۱۰ | `No module named 'pypdfium2'` ⇒ ۹ PNG با `size=0` |

**کنترل قطعی:** یک Worktree detached جداگانه دقیقاً روی `e09ccd95` با **صفر
تغییر محلی** ساخته شد و همین ۵ سوئیت در آن اجرا شدند. counts **برای هر ۵ سوئیت
عیناً یکسان** بود (۵/۱، ۴۴/۳، ۴۳/۲، ۱/۱، ۳۵/۱۰). stage05 در صورت هر اختلاف
abort می‌کند. Worktree کنترل پس از اجرا حذف شد و هر ۵۰ Worktree موجود حفظ شدند.

ریشه: محیط Python محلی (۳٫۱۵٫۲) وابستگی‌های `requirements.txt` را ندارد؛ CI آن‌ها
را با `pip install -r requirements.txt` نصب می‌کند (Python 3.12). این نقص محیط
است، نه کد — و این مأموریت هیچ کدی تغییر نداده است.

### ۱۰.۵ Idempotency مصنوعات جدید

| مرحله | بازاجرا |
| --- | --- |
| stage01 ماتریس پوشش | payload بایت‌یکسان |
| stage02 انتخاب گروه | payload بایت‌یکسان |
| stage03 شواهد گروه | payload بایت‌یکسان |
| stage04 آمادگی محصول | payload بایت‌یکسان |
| stage05 گیت‌ها | payload بایت‌یکسان |

ساعت فقط در manifest است، هرگز در payload.

**کنترل‌های منفی stage03** (`test_stage03_controls.py`, verdict PASS):

| کنترل | انتظار | نتیجه |
| --- | --- | --- |
| A — کلید هویت استاندارد | exit 0 | ۰ ✓ |
| B — حذف join alias (کلید املای خام) | exit 2 | ۲ ✓ (۶ نماد drift) |
| C — شکستن پین SHA ورودی | exit 2 | ۲ ✓ |

هر دو گیت B و C **پیش از نوشتن هیچ خروجی** abort کردند. پس این گیت‌ها واقعاً
می‌توانند شکست بخورند؛ passشان vacuous نیست.

### ۱۰.۶ صداقت CI — قلم‌هایی که نباید بزرگ‌نمایی شوند

- **python-legacy:** این lane report-only است. در فاز قبلی workflow آن
  `success` شد در حالی که job نگهداشت Python آن `failure` بود. موفقیت سطح
  workflow هرگز به‌معنی موفقیت همهٔ jobها گزارش نمی‌شود.
- **CI روی `3dc7318a`** هرگز به‌جای CI روی کامیت docs `e09ccd95` ارائه نمی‌شود.
  هر نتیجه SHA خودش را نام می‌برد.
- **Stage E:** استخراج کامل LZMA در فاز قبلی هم انجام نشد؛ آزمون مستقیم محصول
  روی کپی Seed جای آن را گرفت (۸/۸ سبز). این محدودیت همچنان پابرجاست.
- **`market_universe_v1`:** ۴۰۵٫۵ms در برابر آستانهٔ **تغییرنکردهٔ** ۴۰۰ms روی
  میزبان تک‌هسته‌ای؛ سوئیت مستقل ۱۷/۱۷. آستانه تغییر نکرد و benchmark بازاجرا
  نشد، چون این مأموریت هیچ کدی تغییر نداده است.
- **`SEED_RELEASE_OK`** یک verdict گیت است، نه اجازهٔ انتشار. گیت روی Seed
  Candidate غایب بازاجرا نشد و شرایطش تغییر نکرد.

---

## ۱۱. خطوط قرمز — همه رعایت شدند

| قید | وضعیت |
| --- | --- |
| Seed Candidate تغییر نکند | ✓ غایب بود؛ هرگز باز یا نوشته نشد |
| Production DB تغییر نکند | ✓ هرگز باز، کپی یا نوشته نشد |
| هیچ‌یک از دو DB روی دیگری کپی نشود | ✓ هیچ کپی‌ای ساخته نشد |
| ردیف دارای اختلاف بدون شاهد معتبر بازنویسی نشود | ✓ ۶۷ `MISMATCH` و ۲ `CONFLICT_DUPLICATE` دست‌نخورده |
| ۴۰۴ رویداد با نوع رسمی نامشخص | ✓ `corporate_action_unclassified` ماند؛ نوع از روی نسبت حدس زده نشد |
| ۳۰۶ ردیف OHLC نامعتبر قدیمی | ✓ بدون شاهد اصلاح نشد |
| ۱۰٬۹۸۲ اختلاف فیلدی عمدی | ✓ قابل ردیابی و دست‌نخورده |
| `legacy-unknown` بدون اعتبارسنجی Price Basis | ✓ مصرف نشد؛ ریسک ۳۰/۳۰ نماد گروه صریح ثبت شد |
| رویداد بدون شاهد verified ثبت نشود | ✓ ۴۶ ردیف `NO_EVIDENCE` همان‌گونه ماند |
| کندل روز Capture قرنطینه | ✓ در برنامهٔ Capture صریح شد |
| تلورانس‌ها برای سبزشدن شل نشوند | ✓ فقط نقل شدند |
| `measured.go` / `candlebuild` بازنویسی نشوند | ✓ diff خالی |
| هیچ Suite/Guard حذف، skip یا ضعیف نشد | ✓ شکست‌ها همان‌گونه گزارش شدند |
| رمز عبور درخواست/ذخیره نشد | ✓ هرگز |
| دادهٔ ساختگی / Capture جعلی | ✓ هیچ |
| پردازش خودکار کل ۶٬۱۰۳ پس از موفقیت گروه | ✓ انجام نشد؛ شواهد برای تصمیم مالک ارائه شد |
| `main` تغییر نکند | ✓ روی `2c3e8726` ماند |

نتایج پذیرفته‌شدهٔ Phase 4.9.2 **بازتولید نشدند**: فرمول تعدیل، ۳۰/۳۰ parity با
max rel ≈ 2.0e-15، ۱۰۵٬۶۹۲ کندل خام + ۱۰۵٬۶۹۲ adjusted، و idempotency
revision/rebuild همان‌گونه پذیرفته ماندند.

**ظرافت شمارش رویداد که حفظ شد:** `event-parity.json` دارای **۱٬۰۲۸ ردیف
مقایسه‌شده** است = ۹۶۰ `MATCH` پیش از fix + ۶۷ `MISSING` مرجع + ۱ `EXTRA` موتور.
بنابراین **رویدادهای مرجع = ۱٬۰۲۷** و آن ردیف اضافی فقط‌موتور است؛ پس از fix
۱٬۰۲۷ match شد و extra ناپدید گشت. ۱٬۰۲۸ ردیف هرگز ۱٬۰۲۷ رویداد نامیده نمی‌شود.

---

## ۱۲. تصمیمی که به تأیید مالک نیاز دارد

**پوشش واقعاً چقدر می‌تواند افزایش یابد؟**

- **بدون هیچ Capture جدید:** ۶۷۵ نماد `QUEUE_REFERENCE_ONLY` قابل بازیابی‌اند
  (+۱٬۵۶۸٬۰۶۰ ردیف، ۶٫۷۱ برابر). ۵۴ نماد halted دیگر (+۱۵۳٬۳۶۵ bar) مشروط به
  رأی مالک دربارهٔ halted.
- **گروه ۳۰ منجمد:** +۵۶٬۴۰۱ ردیف مورد انتظار (۲۸٬۰۵۱ → ۸۴٬۴۵۲).
- **با Capture جدید:** ۳٬۳۰۸ نماد دیگر.
- **نیازمند منبع/تصمیم دیگر:** ۱٬۴۶۸ حل هویت، ۱۹۱ نقشهٔ asset-id،
  ۳۷۷ رأی halted + Capture.

**تصمیم لازم:** بازیابی بایت‌های licensed Capture روی این ماشین (یا مجوز
re-capture روی یک نشست authenticated موجود) تا گروه ۳۰ منجمد سرتاسری پردازش و
مستقلاً verify شود. این درخواست **هیچ تغییر Seed یا Production** را در بر ندارد.

پس از موفقیت گروه، شواهد گسترش برای **تصمیم مقیاس‌پذیری مالک** ارائه می‌شود؛
پردازش خودکار کل ۶٬۱۰۳ انجام نخواهد شد.

---

## ۱۳. مصنوعات

| مسیر | چیست |
| --- | --- |
| `docs/opportunity-center/phase49-3/COVERAGE-EXPANSION-REPORT.md` | همین گزارش |
| `docs/opportunity-center/phase49-3/COHORT-SELECTION.json` | گروه ۳۰ منجمد با دلایل و SHA ورودی |
| `docs/opportunity-center/phase49-3/COVERAGE-EXPANSION-MAP.csv` | ماتریس ۶٬۱۰۳ × ۶۴ |
| `docs/opportunity-center/phase49-3/ARTIFACTS-SHA256.txt` | هش همهٔ گزارش‌ها، شواهد، ورودی‌ها و خروجی‌ها |
| `docs/opportunity-center/phase49-3/CI-FINAL-RESULTS.json` | CI واقعی با SHA خودش |
| `_audit/phase49-3/evidence/` | شواهد مشتق کامیت‌شده |
| `_audit/phase49-3/ledgers/` | ledgerهای مشتق کامیت‌شده |
| `_audit/phase49-3/manifests/` | manifest هر مرحله با SHA ورودی/خروجی، counts، زمان، وضعیت |
| `_audit/phase49-3/*.py` | اسکریپت‌های مرحله (قابل بازاجرا) |
| `_audit/phase49-3/{captures,db,logs}/` | gitignored — دادهٔ خام، کپی DB، لاگ اجرا |

اسکریپت جدید فقط جایی نوشته شد که قابلیت موجود نبود: اسکریپت‌های قبلی
(`build_coverage_ledger.py`، `stage03`، `stage05`) به DB یا Capture غایب نیاز
دارند. هیچ موتور دوم یا مسیر محاسباتی موازی ساخته نشد.