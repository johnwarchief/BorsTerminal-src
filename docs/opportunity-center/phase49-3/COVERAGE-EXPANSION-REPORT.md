# گزارش Phase 4.9.3 — گسترش پوشش و آمادگی Seed

**وضعیت نهایی: `PARTIAL`**

ماتریس کامل ۶٬۱۰۳ نماد ساخته و آشتی داده شد؛ گروه ۳۰ نمادی جدید به‌صورت قطعی و
بازتولیدپذیر انتخاب و منجمد شد. مالک بایت‌های licensed Capture را با Git LFS
بازگرداند؛ بازیابی **مستقلاً راستی‌آزمایی شد** (stage06 — PASS) و گروه ۳۰ سرتاسری
پردازش شد: ingest، Factor، `candlebuild` و Parity سطح کندل **PASS** (stage07)،
Revision / Update Chain / Idempotency **PASS** (stage09).

اندازه‌گیری زندهٔ Runtime روی کپی کاری مستقل **PARTIAL** است (stage08): ۲۹ نماد
مسیر اندازه‌گیری‌شده را می‌گیرند و قیمت پایانی تعدیل‌شدهٔ هر ۳۰ نماد با type7 دقیق
است، اما `پادا` — نمادِ پوشش‌دارِ بدون رویداد — برچسب پوشش را از دست می‌دهد و
**دو کندل با هندسهٔ نامعتبر** سرو می‌شوند. این نقص **اصلاح نشد**؛ رأی مالک
می‌خواهد (§۱۲). دامنهٔ آن سرشماری شد (stage10 — PASS): **۱۴ نامزد از ۷۵۹** نماد
پوشش‌دار مرجع، ۲۰٬۲۸۹ bar روزانه؛ فقط خواندنی، بدون پردازش نماد جدید (§۹.۷).

CI واقعی روی کامیت مصنوعات `a265841c` کامل شد: هر سه workflow سبز، **همهٔ jobهای
بازدارنده سبز** (guards ۹/۹، python-tooling ۱/۱ — lane داده روی CI سبز شد و
انتساب محیطیِ ۵ شکست محلی را مستقل تأیید کرد). job نگهداشت Python در lane
report-only همچنان `failure` است: ۳۰/۲۱۱ سوئیت، مجموعهٔ نام‌ها عیناً برابر کامیت
پایه، صفر شکست تازه. این به‌عنوان موفقیت همهٔ jobها گزارش نمی‌شود (§۱۰.۸).

هیچ داده‌ای ساخته نشد، هیچ Capture جعلی تولید نشد، موتور بایت‌به‌بایت دست‌نخورده
ماند و هیچ‌یک از دو دیتابیس خط‌قرمز باز یا تغییر داده نشد. Screenshot واقعی UI
گرفته نشد و `NOT_MEASURED` ماند.

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
| شاخهٔ LFS مالک | `mission/phase49-3-capture-lfs-2026-11-11` — فقط خوانده شد، merge نشد |
| کامیت مصنوعات (CI روی همین) | `a265841c709e7b91d635a43e99ae544e0b5fc584` — push شد و با `git ls-remote` روی GitHub اثبات شد |
| کامیت docs-only | پس از این کامیت می‌آید (CI + manifest بازتولیدشده)؛ SHA آن در پیام تحویل به مالک اعلام می‌شود |

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
| شواهد سطح‌رویداد گروه ۳۰ (از ledger) | **PASS_EXTRACTION_ONLY** | استخراج از اندازه‌گیری قبلی، نه اندازه‌گیری جدید؛ `candle_level_status: BLOCKED` آن زمان درست بود و اکنون با stage07/08 جانشین شده (§۱۳.۱) |
| بازیابی بایت‌های Capture (stage06) | **PASS** | هر دو ظرف + payload بازهش‌شده؛ ۷۵۹ نماد، ۵٬۲۴۰٬۹۶۴ bar |
| پوشش گروه ۳۰ در Capture بازیابی‌شده | **PASS** | ۳۰/۳۰ جفت type0/type7، ۸۴٬۴۵۲ bar روزانه برای هر type |
| پردازش سرتاسری گروه ۳۰ — سطح کندل (stage07) | **PASS** | ۶۰۶ Factor، ۸۳٬۲۵۴ کندل، صفر mismatch، close max rel ۱٫۵۵e-۱۵ |
| ناوردایی لنگر `q(last)==1` | **PASS** | ۳۰/۳۰؛ `max|q−1| = 0.0` دقیق |
| Revision / Update Chain / Idempotency (stage09) | **PASS** | ۱۲ از ۱۲ کنترل، شامل کنترل منفی |
| اندازه‌گیری زندهٔ Runtime روی کپی مستقل (stage08) | **PARTIAL** | ۲۹ PASS + ۱ PARTIAL (`پادا`)؛ API است، نه UI |
| قیمت پایانی تعدیل‌شده از مسیر HTTP | **PASS** | هر ۳۰ نماد؛ max rel ۱٫۵۵e-۱۵، صفر نماد منحرف |
| هندسهٔ کندل سروشده | **PARTIAL** | ۲ ردیف نامعتبر، هر دو در `پادا`؛ ۲/۲ منتسب، صفر بی‌انتساب |
| capability پوشش رسمی / تزریق bar زنده | **NOT_MEASURED** | جدول `instruments` در DB کاری schema-only وجود ندارد |
| آزمون محصول روی کپی Seed Candidate | **NOT_MEASURED** | Seed روی این ماشین present نیست |
| Screenshot واقعی UI | **NOT_MEASURED** | گرفته نشد؛ آزمون API هرگز UI نامیده نمی‌شود |
| موتور دست‌نخورده + سوئیت‌های Go | **PASS** | ۵۵ بسته ok، صفر شکست، `go vet` exit 0 |
| پروفایل production | **PASS** | exit 0، ALL SUITES PASSED |
| پروفایل data | **FAIL از پیش موجود** | ۵ سوئیت؛ کنترل روی کامیت پایه counts یکسان داد |
| سرشماری دامنهٔ نقص zero-event (stage10) | **PASS** | ۱۴ نامزد از ۷۵۹ نماد پوشش‌دار؛ ۲۰٬۲۸۹ bar روزانه؛ فقط خواندنی، ۱۰/۱۰ کنترل |
| CI واقعی روی `a265841c` — jobهای بازدارنده | **PASS** | guards ۹/۹ job، python-tooling ۱/۱ job (lane داده روی CI سبز) |
| CI واقعی روی `a265841c` — lane report-only | **FAIL از پیش موجود** | job نگهداشت Python: ۳۰/۲۱۱ سوئیت، مجموعهٔ نام‌ها عیناً برابر پایه، new=0 |
| CI واقعی روی `612c9658` (کامیت پیشین) | **PASS / FAIL از پیش موجود** | همان الگو؛ رکورد بایت‌یکسان کنار گذاشته شد (§۱۰.۶) |

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

### ۳.۷ نگاشت ۶۴ ستون به ابعاد خواسته‌شدهٔ مأموریت

هر بعدی که مأموریت خواست، ستون مستقل دارد. حضور Reference و وجود Capture
جفت‌شده عمداً دو ستون جدا هستند (بعد ۴ در برابر بعد ۷).

| بعد خواسته‌شده | ستون‌های ماتریس |
| --- | --- |
| هویت استاندارد / هویت معتبر | `key`, `identity_status`, `instrument_candidates` |
| instruments و وضعیت asset-id | `ins_code`, `isin`, `asset_id`, `instrument_status`, `instrument_state_date`, `asset_id_state` |
| halt و تازگی | `stale_status`, `stale_basis`, `sessions_behind`, `latest_session` |
| حضور Reference Index و نوع پوشش | `ref_coverage`, `ref_type0_bars`, `ref_first`, `ref_last` |
| حضور و شمار Factor Step | `step_rows`, `factor_steps`, `factor_verified`, `factor_reconstructed`, `factor_unverified`, `factor_conflict`, `factor_partial`, `factor_insufficient` |
| OHLCV خام معتبر | `raw_ohlc_valid`, `seed_price_rows` |
| حضور Capture جفت‌شدهٔ type0/type7 | `paired_type0_type7_evidenced` (اثبات‌شده) در برابر `local_capture_bytes` (بایت موجود) |
| کامل‌بودن بازهٔ تاریخی | `window_span_ok`, `session_completeness`, `seed_trading_sessions`, `seed_duplicate_dates`, `seed_first_date`, `seed_last_date` |
| شمار کندل قابل استفاده | `ingestable_raw_rows`, `history_gain_rows`, `adjusted_available`, `pilot_adjusted_rows` |
| OHLC نامعتبر / اختلاف Price Basis | `invalid_ohlc_legacy`, `anomalies`, `gaps`, `legacy_unknown_rows`, `price_basis_risk`, `rahavard365_rows`, `board_rows` |
| eligibility ورود به محاسبه+verify | `verification_eligible` |
| علت دقیق Block | `block_cause`, `ledger_remaining_blocker`, `recovery_class` |
| منبع لازم برای رفع Block | `required_source` |
| زمینهٔ ledger و pilot قبلی | `symbol`, `evidence_tier`, `event_coverage`, `official_o1`, `official_o1_in_range`, `ledger_final_status`, `phase49_2_status`, `phase49_2_queue_reason`, `pilot_raw_rows`, `pilot_factors`, `pilot_verified_exact`, `pilot_max_rel_error`, `pilot_revision` |

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
| halted با Reference (۵۴) | ۱۸٬۱۲۱ | ۱۵۳٬۳۶۵ | +۱۳۵٬۲۴۴ (مشروط به رأی مالک) | ۸٫۴۶× |
| گروه جدید (۳۰) | ۲۸٬۰۵۱ | ۸۴٬۴۵۲ | **+۵۶٬۴۰۱** | ۳٫۰۱× |

این اعداد در زمان نوشتن **EVIDENCED EXPECTATION** از فهرست کامیت‌شده بودند، چون
بایت‌های Capture روی این ماشین نبودند. جمع `ref_days` روی ۷۵۹ نماد `ref_full`
دقیقاً ۲٬۱۰۱٬۷۵۲ می‌شود که با `factor_days` ثبت‌شده در `capture-summary.json`
مطابقت دارد — این یک cross-check مستقل است.

**به‌روزرسانی پس از بازیابی:** ستون «bar مرجع type0» در ردیف «گروه جدید (۳۰)»
دیگر برآورد نیست — **اندازه‌گیری شد** و دقیقاً همان درآمد: ۸۴٬۴۵۲ bar روزانه
برای هر type و ۸۴٬۴۵۲ ردیف خام ingest‌شده (§۷.۳). ستون «افزایش» (+۵۶٬۴۰۱)
همچنان **مشروط** است: تفاضلِ bar مرجع از ردیف seed است و چون هیچ merge با Seed
انجام نشد، در هیچ دیتابیسی محقق نشده (§۱۲.۱). سه ردیف دیگر همچنان برآوردند و
پردازش نشدند.

هر چهار ردیف جدول بالا مستقیماً از خود ماتریس کامیت‌شده بازجمع زده شدند (نه از
JSON شواهد) و اعداد یکسان درآمدند. روش پیش‌بینی هم اعتبارسنجی شد: برای هر ۳۰ نماد
pilot قبلی `ingestable_raw_rows == ref_type0_bars` است، یعنی همان ستونی که برای
گروه جدید پیش‌بینی می‌کند، برای گروه قبلی دقیقاً برابر اندازه‌گیری واقعی بوده است.

### ۵.۲ شواهد Capture موجود

اعداد این جدول ابتدا از `capture-summary.json` نقل شده بودند؛ stage06 همه را
از خود بایت‌ها بازشمرد و **دو برچسب غلط پیدا شد** که اینجا اصلاح می‌شوند:

| مورد | مقدار | منبع |
| --- | --- | --- |
| نمادهای merge‌شده | ۷۵۹ | باز شماری stage06 ✓ |
| bar type0 (**همهٔ** resolutionها) | ۲٬۶۲۰٬۴۸۲ | `per_type/type0` |
| bar type7 (**همهٔ** resolutionها) | ۲٬۶۲۰٬۴۸۲ | `per_type/type7` |
| bar **روزانهٔ** type0 (`D`) | **۲٬۱۰۱٬۷۵۲** | `per_type_resolution/type0/D` |
| bar **روزانهٔ** type7 (`D`) | **۲٬۱۰۱٬۷۵۲** | `per_type_resolution/type7/D` |
| کل bar روزانه (`D`, هر دو type) | ۴٬۲۰۳٬۵۰۴ | `per_resolution/D` ✓ |
| bar هفتگی (`W`) | ۱٬۰۳۷٬۴۴۰ | `per_resolution/W` |
| bar ماهانه (`M`) | ۲۰ | `per_resolution/M` |
| کل bar | ۵٬۲۴۰٬۹۶۴ | `totals/merged_bars` ✓ |
| `factor_days` فهرست | ۲٬۱۰۱٬۷۵۲ | ✓ |
| `factor_changes` فهرست | ۱۳٬۹۲۱ | ✓ |
| SHA ظرف bars | `272336c036d647ed7b2090853c84c3a2d3da6126a0bfae60e987198169b3b14a` | ✓ |
| SHA payload بازفشردهٔ bars | `6aec345f817cd96a0dc8eb631cdfa206deee740afb077b5f4621dd1f821fb844` | ✓ |
| SHA فهرست مرجع | `83544012448fc19100e7b140dbcfc2e4d27eca317f667204c343f810acc92e1c` | ✓ |

**اصلاح ۱ — برچسب resolution:** نسخۀ پیشین این گزارش ۲٬۶۲۰٬۴۸۲ را «bar روزانهٔ
type0/type7» نامیده بود. این عدد **جمع همهٔ resolutionها** است
(`D` ۲٬۱۰۱٬۷۵۲ + `W` ۵۱۸٬۷۲۰ + `M` ۱۰). شمار روزانهٔ درست **۲٬۱۰۱٬۷۵۲** است.
عدد عوض نشد؛ **برچسب** اصلاح شد. هیچ محاسبه‌ای بر برچسب غلط بنا نشده بود، چون
پیش‌بینی ردیف گروه از `ref_days` می‌آمد و آن با `factor_days` می‌خواند.

**اصلاح ۲ — وضعیت کامیت:** `capture-summary.json` هنوز
`raw_capture_committed: false` دارد. این پرچم **روی شاخهٔ مالک کهنه است**:
بایت‌ها اکنون به‌صورت LFS object در کامیت `18dd46a7` کامیت شده‌اند و oid هر دو
pointer با همین SHAها می‌خواند (§۸.۱). فایل ثبت‌شدهٔ فاز قبل **بازنویسی نشد**؛
تناقض اینجا صریح گزارش می‌شود. مجوز همچنان
`owner subscription; not redistributable` است (§۱۲.۵).

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

لایه‌ها کاملاً جدا گزارش می‌شوند و هرگز با هم مخلوط نمی‌گردند:
**ledger استخراج‌شده** (§۷.۱) · **سطح کندل اندازه‌گیری‌شده** (§۷.۳) ·
**سه جمعیت رویداد از Capture** (§۷.۴) · **ناوردایی لنگر** (§۷.۵) ·
**انتساب گشادشدگی** (§۷.۶).

### ۷.۱ سطح رویداد از ledger — **PARTIAL** (استخراج‌شده، نه اندازه‌گیری جدید)

`ADJUSTMENT-EVIDENCE-LEDGER.csv` حاوی اندازه‌گیری‌ای است که
`stage03_step_ledger.py` در Phase 4.9 full-verification **قبلاً** انجام داده و
کامیت شده است. این مرحله آن را با کلید هویت استاندارد پروژه بازکلیدگذاری و
جمع می‌کند. **هیچ Parity کندلی از این لایه ادعا نمی‌شود.**

این لایه **همچنان PARTIAL است** و با اندازه‌گیری جدید stage07 جایگزین نشد:
جمعیت آن ۴۸۷ ردیف ledger است، در حالی که stage07 از خود barهای type0/type7
**۶۰۶ Factor** ساخت. این دو عدد یکی نیستند و نباید با هم جمع یا مقایسه شوند؛
هرکدام discriminator و منبع خودش را دارد (§۷.۴).

این `PARTIAL` توصیفِ خودِ لایه است، نه رشتهٔ `status` در manifest مرحله — آن
`PASS_EXTRACTION_ONLY` است و در §۱۳.۱ عیناً نقل شده.

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

### ۷.۳ سطح کندل — **PASS** (اندازه‌گیری جدید، stage07)

Block قبلی رفع شد: مالک بایت‌های licensed را بازگرداند و stage06 آن‌ها را مستقلاً
راستی‌آزمایی کرد (§۸). سپس همان معماری Phase 4.9.2 — بدون موتور دوم — روی یک
**DB کاری تازهٔ schema-only** اجرا شد.

| قلم | مقدار اندازه‌گیری‌شده |
| --- | --- |
| نماد ingest‌شده | ۳۰ |
| ردیف `reference_raw` | ۸۴٬۴۵۲ |
| ردیف `reference_adjusted` | ۸۴٬۴۵۲ |
| ردیف `adjustment_factors` | ۶۰۶ |
| پیوند Factor↔Action | ۳۳۵ |
| کندل materialize‌شده (`adjusted_candles`) | ۸۳٬۲۵۴ روی ۲۹ نماد |
| ردیف mismatch موتور | **۰** |
| ردیف EXACT موتور | ۸۳٬۲۵۴ (۱۰۰٪) |
| بیشینه خطای نسبی `close` | `1.5543122344752192e-15` |
| بیشینه خطای نسبی `open` | `1.5543122344752192e-15` |
| ردیف اختلاف حجم | **۰** (حجم در همه‌جا ثابت) |
| Revision | `4832047eecc35dd0…` |
| bar قرنطینه‌شدهٔ روز Capture | **۰** — دلیلش پایین |
| bar غیرروزانهٔ ردشده | ۴۰٬۶۷۲ (`W`) |
| ردیف اسکن‌شدهٔ گروه از NDJSON | ۲۰۹٬۵۷۶ |

**نوع رویدادها — هیچ نوعی از روی نسبت حدس زده نشد:**

| kind | تعداد |
| --- | --- |
| `dividend` | ۲۲۰ |
| `corporate_action_unclassified` | ۳۵۰ |
| `capital_increase` | ۳۶ |
| جمع | ۶۰۶ |

۳۵۰ رویداد بی‌نوع ماندند چون marks و ردیف‌های رسمی share-change روی این ماشین
غایب‌اند؛ طبقه‌بند منجمد به شواهد pack تکیه کرد و رویداد بی‌تطبیق را
`corporate_action_unclassified` گذاشت — همان رفتاری که مأموریت خواست.

**قرنطینهٔ روز Capture — عدد واقعی، نه ادعا:** قاعدهٔ پذیرفته‌شده
`date >= capture_day` است. `captured_at_max` در barهای ادغام‌شده
`2026-11-11T00:08:39Z` است، پس `capture_day = 2026-11-11`؛ آخرین bar موجود
`2026-11-10` است. بنابراین **صفر** bar قرنطینه شد. قاعده اجرا شد و خروجی‌اش
تهی بود؛ این «اجرا نشد» نیست و کندل روز جاری وارد زنجیرهٔ تعدیل نشد.

**DB کاری — خط قرمز رعایت شد:**

| مورد | مقدار |
| --- | --- |
| مسیر | `_audit/phase49-3/db/cohort.db` (gitignored) |
| SHA-256 | `99ad41262e32e0b6…` |
| اندازه | ۶۵٬۴۳۷٬۶۹۶ بایت |
| provenance | ساخته‌شده از SCHEMA منجمد Phase 4.9.2 — **نه** کپی Seed و **نه** کپی Pilot |
| Seed / Pilot روی این ماشین | غایب؛ هرگز باز یا نوشته نشدند |
| diff موتور در برابر پایه | `(empty)` |

باینری `candlebuild.exe` از `backend-go/cmd/candlebuild` در همین HEAD ساخته شد
(`ba34c90be644060d…`) و pack منجمد `aa8e13fc2d172c3e…` بدون تغییر مصرف شد.

### ۷.۴ سه جمعیت جداگانه‌ای که مأموریت خواست (§۶)

مأموریت خواست «رویدادهای مرجعِ غایب از pack»، «نسبت‌های متفاوت» و «رویدادهای
بدون تغییر مرجع» **جداگانه** ثبت شوند. هر سه از ledger کامیت‌شده قابل استخراج‌اند،
پس اندازه‌گیری شدند و به Capture موکول نشدند. جمعیت: همان ۴۸۷ ردیف معتبر
(یک assertion برابری آن را با `event_rows_valid` گیت می‌کند).

| جمعیت | تعداد | discriminator |
| --- | --- | --- |
| رویداد مرجع غایب از product **و** pack | **۱** | `provenance == 'reference'` |
| رویداد product بیرون از پوشش pack | **۱۵۶** | notes شامل `outside pack coverage` |
| نسبت‌های متفاوت (`MISMATCH`) | **۶۷** | `comparison_result == 'MISMATCH'` |
| رویداد بدون مقدار تغییر مرجع | **۱۵۱** | فیلد `ref_ratio` خالی |
| stepهای مرجع‌مشتق | **۶۲** | `method == 'reference-factor-step-v1'` |
| step pack که بر product پیروز شد | **۳** | `provenance == 'pack'` و `prod_ratio` خالی |

تفکیک‌ها:

- **۶۷ نسبت متفاوت** = `EVENT_RATIO_MISMATCH` ۳۵ + `SOURCE_MISMATCH` ۳۲؛
  `final_status = CONFLICT_RATIO` نیز ۶۷.
- **۱۵۱ بدون مقدار مرجع** = `MATCH` ۳۶ + `MISMATCH` ۴۵ + `NO_EVIDENCE` ۴۴ +
  `PARTIAL` ۲۶.
- **۶۲ مرجع‌مشتق** = `VERIFIED_REFERENCE` ۵۳ + `CONFLICT_RATIO` ۷ +
  `CONFLICT_DUPLICATE` ۱ + `PARTIAL_OFFICIAL` ۱.

آن **یک** رویداد مرجعِ کاملاً غایب از pack:

| نماد | تاریخ | نسبت | شاهد | وضعیت |
| --- | --- | --- | --- | --- |
| `وتجارت` | ۲۰۱۵-۰۷-۲۷ | `0.9893955461293765` | R1 `capture:2015-07-27` | `VERIFIED_REFERENCE` |

یادداشت خود ledger: «reference factor step missing from product/pack». این ردیف
**بازنویسی نشد**؛ نسبت، provenance و وضعیتش حفظ شد.

**دو مرزبندی صداقت که نباید رد شوند:**

1. عدد **۱** شمار رویدادهای مرجعِ غایب از pack **در جمعیت ledger** است، نه شمار
   کامل آن‌ها در فهرست مرجع. این مرزبندی برای گروه ۳۰ منجمد **برطرف شد**: stage07
   مقایسهٔ کامل فهرست-مرجع با pack را روی بایت‌های بازیابی‌شده انجام داد (جدول
   پایین). برای ۷۲۹ نماد دیگرِ Capture همچنان `NOT_MEASURED` است.
2. **۱۵۱** یعنی فیلد `ref_ratio` در ledger خالی است؛ این **غیبت فیلد** است، نه
   اثبات اینکه فهرست مرجع در آن تاریخ رویدادی ندارد.

هیچ‌کدام از این ردیف‌ها verified جدید نشدند و هیچ نسبتی از روی نوع حدس زده نشد.

#### همان سه جمعیت — این‌بار اندازه‌گیری‌شده از Capture (stage07)

مأموریت (§۶) خواست این سه جمعیت جداگانه ثبت شوند. روی گروه ۳۰ منجمد، از
`q_changes` روی barهای واقعی type0/type7 و مقایسه با pack منجمد:

| جمعیت | تعداد | discriminator |
| --- | --- | --- |
| تغییر مرجعِ غایب از pack | **۲۷۱** | `missing_pack_step` — هیچ step نزدیک با نسبت تطبیق‌پذیر |
| step pack بدون تغییر مرجع | **۱۵** | `no_reference_change` |
| step pack با نسبت متفاوت | **۱** | `superseded_ratio` — فراتر از `PACK_RATIO_TOL` |

پنجره‌ها و تلورانس‌های منجمد عیناً مصرف شدند: `PACK_WINDOW_DAYS = 7`،
`PACK_RATIO_TOL = 1e-6` برای تشخیص supersede و `1e-3` برای تطبیق step.
**هیچ تلورانس و هیچ معیار پذیرشی تغییر نکرد.** هر سه جمعیت در جدول
`adjustment_audit` با `run_id` ثبت شدند و هیچ ردیفی بازنویسی نشد.

این ۲۷۱ با آن ۶۷ ردیف `MISSING` فاز قبل **یکی نیستند**: جمعیت آن‌ها ۳۰ نماد
pilot بود و جمعیت این‌ها ۳۰ نماد جدیدِ منجمد. هیچ عددی از دیگری استنتاج نشد.

### ۷.۵ ناوردایی لنگر — کشف جدید، اندازه‌گیری‌شده روی ۳۰/۳۰

`chainFactors` (`backend-go/internal/chart/canonical.go:1463-1514`) روی **بزرگ‌ترین
تاریخ** `factor = 1.0` می‌گذارد و نسبت رویدادهای بعدی را در هم ضرب می‌کند. نسبت
ذخیره‌شده `q_after/q_before` است، پس زنجیره تلسکوپی می‌شود به `q(last)/q(t)`.
نتیجهٔ منطقی: **Parity قیمت پایانی با type7 تنها وقتی برقرار است که `q(last)==1`.**

این یک فرض نبود؛ اندازه‌گیری شد:

| قلم | مقدار |
| --- | --- |
| نماد بررسی‌شده | ۳۰ |
| نقض | **۰** |
| `max|q−1|` | `0.0` (دقیق، نه تقریبی) |
| تاریخ لنگر | ۲۹ نماد `2026-11-10`، یک نماد (`دكيمي`) `2026-11-04` |

**چطور کشف شد — صداقت دربارهٔ مسیر:** اولین اجرای کنترل‌های stage07
**۴ از ۲۵** را شکست داد، از جمله کنترل مثبت. ریشه با یک diagnostic پیدا شد، نه
حدس: fixture مصنوعی `q(last)=4` گذاشته بود در حالی که موتور روی آخرین تاریخ
لنگر می‌اندازد. سپس گروه واقعی اندازه‌گیری شد و ۳۰/۳۰ ناوردایی را برقرار یافت.
fixture به یک split واقعی ۲:۱ با type7 تخت اصلاح شد، کنترل `A_anchor_invariant`
اضافه شد و **کنترل منفی G** ثابت کرد که نقض لنگر واقعاً دیده می‌شود
(۱۲ ردیف اختلاف، وضعیت PARTIAL، پرچم mismatch موتور). اکنون ۲۹ از ۲۹ کنترل
PASS هستند و خودِ stage07 این ناوردایی را به‌عنوان یک گیت اندازه‌گیری می‌کند.
**هیچ موتور، تلورانس یا معیار پذیرشی تغییر نکرد.**

### ۷.۶ گشادشدگی سایه — هر اختلاف منتسب شد، صفر بی‌انتساب

`high` و `low` اختلاف‌های بزرگی نشان می‌دهند و **پنهان نشدند**:

| فیلد | بیشینه خطای نسبی | ردیف اختلاف |
| --- | --- | --- |
| `open` | `1.5543e-15` | ۰ |
| `close` | `1.5543e-15` | ۰ |
| `high` | `0.531609195402` | ۶۱۲ |
| `low` | `0.438234203042` | ۱٬۳۶۱ |

جمع ۶۱۲ + ۱٬۳۶۱ = **۱٬۹۷۳** و شمار ردیف‌های مبدأ که `open`شان بیرون از
`high`/`low` خودشان است نیز دقیقاً **۱٬۹۷۳** است. علت، قرارداد منجمد
`candle.Widen` (`backend-go/internal/candle/candle.go:11`) است: سایه را باز
می‌کند تا بدنه را در بر بگیرد. سری type7 مرجع اما `raw × factor` است **بدون**
گشادشدگی. پس هرجا open مبدأ بیرون از سایهٔ خودش باشد، این دو مسیر لزوماً
اختلاف پیدا می‌کنند.

| انتساب | مقدار |
| --- | --- |
| منتسب به قرارداد منجمد widen | high ۶۱۲، low ۱٬۳۶۱ |
| **بی‌انتساب** | **۰** |
| موتور = widened × factor؟ | true (بدون counterexample) |
| مرجع = raw × factor؟ | true (بدون counterexample) |
| دادهٔ خام تغییر کرد؟ | **خیر** |

بدترین نمونه‌ها ثبت شدند تا aggregate پنهانشان نکند: `پرديس` در `2000-01-31`
(high موتور `1.0236` در برابر مرجع `0.6683`) و `دكيمي` در `1997-04-14`
(low موتور `5.8870` در برابر مرجع `10.4795`).

یک اختلاف بی‌انتساب **کل مرحله را شکست می‌داد**؛ چنین چیزی رخ نداد. طبق
مأموریت، نه barهای خام اصلاح شدند و نه موتور؛ ۳۰۶ ردیف OHLC نامعتبر قدیمی و
۱۰٬۹۸۲ اختلاف فیلدی عمدی هم دست‌نخورده ماندند (§۱۱).

---

## ۸. رفع Block — بازیابی انجام شد و مستقلاً راستی‌آزمایی شد

`capture-restore-plan.json` وضعیت `BLOCKED_CAPTURE_REQUIRED` را ثبت کرده بود.
مالک بایت‌ها را با Git LFS بازگرداند و **مسیر ترجیحی (§۸.۱) محقق شد؛ هیچ Capture
جدیدی گرفته نشد و هیچ نشست authenticated تازه‌ای لازم نشد.**

### ۸.۱ راستی‌آزمایی مستقل بازیابی (stage06 — PASS)

**سند انتقال مالک به‌عنوان ورودی استفاده نشد.** هر عدد از خود بایت‌ها دوباره
استخراج شد.

| مورد | مقدار |
| --- | --- |
| شاخهٔ مالک | `mission/phase49-3-capture-lfs-2026-11-11` |
| کامیت فایل‌ها | `18dd46a71445d2e6…` |
| tip شاخه | `e887a1236f5cc4f9…` |
| روش خواندن | `git cat-file blob` — هیچ checkout و هیچ worktree از شاخهٔ مالک ساخته نشد |
| pointerها | هر دو oid با شواهد ثبت‌شدهٔ قبلی یکی‌اند (۱۳۳ و ۱۳۱ بایت) |

| ظرف | اندازه | SHA-256 | تطبیق |
| --- | --- | --- | --- |
| `bars-all.ndjson.gz` | ۱۴۵٬۸۶۴٬۴۳۰ | `272336c036d647ed…` | ✓ |
| `reference-index-all.json` | ۲٬۰۱۰٬۳۷۸ | `83544012448fc191…` | ✓ |

ظرف و payload **جداگانه** هش شدند و هیچ‌کدام به‌جای دیگری ننشست:
payload بازفشردهٔ NDJSON = `6aec345f817cd96a…`، و CRC خود gzip نیز verify شد.

**بازشمارش کامل barها (نه نمونه‌گیری):**

| قلم | مقدار |
| --- | --- |
| کل bar | ۵٬۲۴۰٬۹۶۴ |
| type0 / type7 | ۲٬۶۲۰٬۴۸۲ / ۲٬۶۲۰٬۴۸۲ |
| به تفکیک resolution | `D` ۴٬۲۰۳٬۵۰۴ · `W` ۱٬۰۳۷٬۴۴۰ · `M` ۲۰ |
| `type0/D` و `type7/D` | ۲٬۱۰۱٬۷۵۲ هرکدام |
| بازهٔ تاریخ | `1991-03-23` تا `2026-11-10` |
| نماد (کلید هویت) | ۷۵۹ |
| املای خام unmapped | **۰** |
| close تهی/غیرمتناهی | **۰** |
| volume تهی | **۰** |
| `high < low` | **۰** |
| OHLC تهی | **۰** |
| تکرار هویت مجاور | **۰** |
| ردیف هویت خارج از ترتیب | ۱۶۷ (ثبت شد، پنهان نشد) |
| bar روی آخرین تاریخ | ۱٬۴۴۰ |

**فهرست مرجع:** ۷۵۹ نماد، ۲٬۱۰۱٬۷۵۲ factor-day، **۱۳٬۹۲۱** تغییر factor،
صفر تضاد تاریخ، صفر روز raw صفر. join هویت معتبر؛ **۷۵۹ از ۷۵۹** نماد
سطح‌به‌سطح match شدند و هیچ نمادی در یکی از دو فایل غایب از دیگری نبود.

**پوشش گروه ۳۰ منجمد:** ۳۰/۳۰ در فهرست present، ۳۰/۳۰ زنجیرهٔ factor منطبق با
شمار فهرست، ۸۴٬۴۵۲ bar روزانه برای هر type، و **مجزا از ۳۰ نماد pilot قبلی**.
حضور در فهرست به‌تنهایی «پوشش» نامیده نشد: پوشش یعنی type0 **و** type7 هر دو
بازهٔ محلی را بپوشانند.

بایت‌ها سپس در مسیر gitignored `_audit/phase49-full-verification/captures/`
materialize شدند و SHA مقصد دوباره با منبع verify‌شده مقایسه شد (هر دو ✓).
**در این مرحله هیچ Factor نوشته نشد، هیچ کندلی ساخته نشد و هیچ DB خط‌قرمز باز نشد.**

### ۸.۲ مسیر جایگزین — استفاده نشد

چون بازیابی موفق بود، هیچ درخواست Capture جدیدی صادر نشد. پیش‌شرط این مسیر
همچنان پابرجاست: یک نشست **از قبل authenticated** Rahavard با مجوز مالک.
**هیچ رمز عبور یا اطلاعات ورودی درخواست یا ذخیره نشد و نمی‌شود.** اگر نشست
معتبر نبود، داده ساخته نمی‌شد و Capture جعلی تولید نمی‌شد.

| پارامتر | مقدار (برای نیاز آینده) |
| --- | --- |
| endpoint | `https://rahavard365.com` |
| types | `type0` + `type7` (جفت‌شده) |
| resolution | `D` |
| countback | ۱۰۰٬۰۰۰ |
| from | `1990-01-01T00:00:00Z` |
| کندل روز Capture | **قرنطینه** — هرگز وارد زنجیرهٔ تعدیل نمی‌شود |

هر Capture باید ثبت کند: هویت نماد (key، ins_code، asset_id)، تاریخ واکشی،
آخرین نشست کامل، نوع سری، resolution و SHA-256.

---

## ۹. قرارداد Runtime و آمادگی محصول

`product-readiness.json` (stage04، ایستا) — **۲ PASS، ۶ NOT_MEASURED**. آن مرحله
فقط سورس کامیت‌شده را probe کرد و هیچ آزمون محصولی ادعا نکرد. **stage08 اکنون
همان قرارداد را زنده اندازه‌گیری کرده است** (§۹.۳) و نتیجه PARTIAL است.

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

### ۹.۲ بستر اندازه‌گیری — چه چیزی present شد و چه چیزی همچنان غایب است

پیش از بازیابی، **۰ از ۵** ورودی لازم present بود و هیچ کپی‌ای ساخته نشد؛ ساختن
کپی بدون آن ورودی‌ها یعنی جعل داده. پس از بازیابی:

| ورودی لازم | پیش از بازیابی | اکنون |
| --- | --- | --- |
| `bars-all.ndjson.gz` | خیر | **بله** — SHA verify شد |
| `reference-index-all.json` | خیر | **بله** — SHA verify شد |
| DB کاری سازگار با Runtime | خیر | **بله** — `cohort.db` تازه از SCHEMA منجمد |
| Seed Candidate DB | خیر | **همچنان خیر** |
| Pilot DB | خیر | **همچنان خیر** |

تنها DB موجود در Worktree، `market.db` **کامیت‌شده در Git** است
(کامیت `d081d741`): ۲۶٬۳۷۸٬۲۴۰ بایت، ۲٬۲۰۹ ردیف `price_history`، ۳٬۶۸۰
instruments، و **هیچ‌یک** از شش جدول تعدیل را ندارد. این نه Seed Candidate است
(۲۸۱٬۰۸۸٬۰۰۰ بایت / ۵۴۴٬۲۸۴ ردیف) و نه Pilot (۳۶۴٬۶۷۰٬۹۷۶ بایت).
SHA آن `c0979d4e…` است و با هیچ‌یک از دو SHA خط‌قرمز یکی نیست.

این DB فقط read-only و `immutable=1` باز شد؛ `git status` آن پاک ماند.
DB نصب‌شدهٔ Production (که `-wal` و `-shm` فعال دارد) **هرگز باز، کپی یا
تغییر داده نشد**.

**تفاوت بستر با Phase 4.9.2 — صریح:** فاز قبل روی کپی Seed اندازه‌گیری کرد؛
اینجا روی یک DB تازهٔ schema-only. پذیرش سطح کندل مقایسه‌پذیر است چون موتور
فقط همان سه جدول مرجع را می‌خواند، اما هر اندازه‌گیریِ وابسته به Seed
`NOT_MEASURED` ماند (§۹.۵).

### ۹.۳ اندازه‌گیری زندهٔ Runtime (stage08) — **PARTIAL**

**این یک اندازه‌گیری HTTP API است، نه آزمون UI و نه Screenshot.**
`is_ui_test: false` و `screenshot: NOT_MEASURED` در خود payload ثبت شد.

| قلم | مقدار |
| --- | --- |
| endpoint | `GET /api/chart-db/{symbol}` |
| باینری | `borsd` ساخته‌شده از همین HEAD، موتور دست‌نخورده |
| پورت | ۱۸۰۹۳ |
| نماد پرس‌وجوشده | ۳۰ |
| بستر | کپی یک‌بارمصرف `_audit/phase49-3/db/runtime/market.db` |
| SHA کپی = SHA DB کاری | ✓ `99ad41262e32e0b6…` |
| DB اصلی | فقط read-only باز شد |
| DB خط‌قرمز باز شد؟ | **خیر** |
| فرآیند | فقط PID ۲۸۹۳۶ که خودمان بالا آوردیم terminate شد |

**مسیر خواندن — اثبات‌شده، نه استنتاج‌شده:**

| قلم | یافته |
| --- | --- |
| کندل | `chartDBBody → canonicalPriceHistory → referenceRawHistory` (`canonical.go:1972`) — **پیش از** خواندن `price_history` برمی‌گردد |
| Factor | `canonicalAdjustment → measuredFactorEvents` (`measured.go:14`) |
| آیا `adjusted_candles` مسیر Runtime است؟ | **خیر** |

این با یک کنترل اثبات شد: fixtureای که **هرگز build نشد** (جدول
`adjusted_candles` خالی) همان پاسخ کامل را از HTTP گرفت. پس سازگاری با Runtime
روی `reference_raw` + `adjustment_factors` سنجیده شد، نه روی خروجی materialize.

**نتیجهٔ قیمت — هر ۳۰ نماد:**

| قلم | مقدار |
| --- | --- |
| نماد روی مسیر `local-measured-factors` | **۲۹ از ۳۰** |
| بیشینه خطای نسبی close تعدیل‌شده (کل) | `1.5543122344752192e-15` |
| نماد با انحراف close تعدیل‌شده | **۰** |
| وضعیت‌ها | ۲۹ PASS + ۱ PARTIAL |

### ۹.۴ یافتهٔ `پادا` — نقص پوشش‌یابی، نه نقص قیمت

`پادا` تنها نماد گروه است که **صفر رویداد تعدیل** دارد: `q` آن در همهٔ روزها ۱
است، پس هیچ ردیف Factor تولید نمی‌شود. با این حال **۱٬۱۹۸ ردیف مرجع کامل** دارد
و همان‌ها سرو می‌شوند.

| قلم | مقدار اندازه‌گیری‌شدهٔ زنده |
| --- | --- |
| کندل سروشده | ۱٬۱۹۸ از ۱٬۱۹۸ |
| provenance خام | `rahavard-type0` ✓ |
| `adjustSource` | **`local-db-unseen`** ✗ |
| `adjustEvents` / `adjustRejected` | ۰ / ۰ |
| ردیف Factor در DB | ۰ |
| min/max فاکتور سروشده | ۱٫۰ / ۱٫۰ |
| اختلاف close تعدیل‌شده | **۰** (max rel `0.0`) |
| اختلاف فیلد خام | `high`: **۲** |
| منتسب به literal reset | **۲ از ۲** |
| بی‌انتساب | **۰** |
| **کندل با هندسهٔ نامعتبر** | **۲** |

**مکانیزم — با citation، و زنده تأیید شد:**

1. `measuredFactorEvents` روی مجموعهٔ Factor تهی `measured=false` برمی‌گرداند
   (`backend-go/internal/chart/measured.go:42-44`).
2. `ChartDB` هرجا `measured=false` باشد، **بعد از** price_basis و FTS،
   `literalDisplayCandles` را اعمال می‌کند
   (`backend-go/internal/chart/handlers.go:37-42`).
3. `literalDisplayCandles` بی‌قیدوشرط `high=high_raw` و `low=low_raw` می‌گذارد
   (`backend-go/internal/chart/corrections.go:747-752`) و **گشادشدگی‌ای را که
   هم `referenceRawHistory` (از `candle.Widen`) و هم `pricebasis.ApplyBasis`
   اعمال کرده بودند دور می‌ریزد**، سپس تصحیح‌های فیلد خامِ بستهٔ نسخه‌دار را
   رویش می‌نشاند.

نیت خودِ هندلر در کامنتش هست: نمادِ پوشش‌داده‌شده با فاکتورهای مرجع باید سری
type0 خودش را نگه دارد و تصحیح نمایشیِ بسته را **نگیرد**. اما پوشش از
`len(factor rows) > 0` استنتاج می‌شود، پس نماد پوشش‌دارِ بدون رویداد
«پوشش‌نداده» تلقی می‌شود و آن تصحیح را می‌گیرد.

**دو کندل نامعتبری که واقعاً سرو شدند:**

| تاریخ | open | high | low | close |
| --- | --- | --- | --- | --- |
| `2021-11-30` | ۱۰۶٬۶۱۰ | ۱۰۶٬۰۵۰ | ۱۰۵٬۰۰۰ | ۱۰۶٬۰۵۰ |
| `2022-02-12` | ۹۳٬۱۰۰ | ۹۲٬۹۰۰ | ۹۲٬۳۰۰ | ۹۲٬۸۰۱ |

در هر دو، **open بالاتر از high** است — بدنه بیرون از سایه. این یک نقص دیداری
چارت است، **نه خطای قیمت پایانی**.

**چرا اصلاح نشد:** مأموریت صریحاً بازنویسی `measured.go` و هندلر را بدون دلیل
فنی جدید ممنوع کرده و تصمیم انتخاب ردیف/محصول را به مالک سپرده است. تشخیص
«پوشش از حضور `reference_raw» به‌جای «مجموعهٔ Factor ناتهی» یک **تصمیم محصول**
است. بنابراین یافته ثبت شد، مکانیزم کامل انتساب داده شد، و **دست نخورد**.

### ۹.۵ محدودیت‌های بستر — یکنواخت روی هر ۳۰ نماد

DB کاری schema-only است، پس جدول `instruments` وجود ندارد:

| قلم | وضعیت |
| --- | --- |
| `capability.coverage.error` | `instrument-unresolved` روی **۳۰ از ۳۰** |
| `liveError` | `no such table: instruments` روی **۳۰ از ۳۰** |
| capability پوشش رسمی | **NOT_MEASURED** |
| تزریق bar زنده | **NOT_MEASURED** (`--no-loops`، بدون feed زنده) |
| شاخهٔ fallback `price_history` | **NOT_MEASURED** — Seed غایب است؛ هر ۳۰ نماد از `reference_raw` سرو شدند |
| Screenshot واقعی UI | **NOT_MEASURED** — هیچ مرورگری روی این DB رانده نشد |
| طبقه‌بندی رسمی share-change | **NOT_MEASURED** — `ins_code` و `share_change_events` غایب‌اند |
| نشانه‌های DPS/EPS | **NOT_MEASURED** — NDJSON فقط bar دارد، نه marks؛ طبقه‌بندی dividend از DPS **صفر نیست، اندازه‌گیری نشده** |
| سرشماری تضاد با Seed | **NOT_MEASURED** — ۳۰۶ ردیف نامعتبر و ۱۰٬۹۸۲ اختلاف فیلدی نه لمس شدند و نه بازقضاوت |

این محدودیت‌ها **به یک نماد خاص محدود نیستند** و به‌عنوان «سبز» گزارش نمی‌شوند.

### ۹.۶ Revision / Update Chain / Idempotency (stage09) — **PASS**

۱۲ از ۱۲ کنترل سبز، شامل یک کنترل منفی:

| کنترل | نتیجه |
| --- | --- |
| Revision در اجرای تازه پایدار | ✓ `4832047eecc35dd0…` عیناً همان |
| Revision به مرجع حساس است (کنترل منفی) | ✓ به `0bef6815bde0764f…` تغییر کرد |
| Factorها بایت‌یکسان (۱۳ ستون غیرdetails) | ✓ ۶۰۶ ردیف، `d750e79f39cf2592…` |
| `details` از نظر معنایی یکسان | ✓ |
| شمارها یکسان | ✓ |
| ردپای audit یکسان | ✓ |
| کندل‌های rebuild بایت‌یکسان | ✓ ۸۳٬۲۵۴ ردیف، `dec11147c3b17e4c…` |
| خلاصهٔ rebuild یکسان | ✓ |
| دو بار rebuild بدون رشد | ✓ همان ۸۳٬۲۵۴ |
| mismatch صفر | ✓ |
| upsert بدون انباشت | ✓ ۶۰۶ → ۶۰۶ |
| DB پین‌شده دست‌نخورده | ✓ |

Revision با `run_id` تازه و ساعت دیرتر **تغییر نکرد** — ساعت در فرمول نیست:
`sha256(capture_sha + "\n" + sorted "symbol|date|%.17g ratio")`.

**یک artifact سریال‌سازی که پیدا و شفاف ثبت شد:** مقایسهٔ بایتیِ ستون `details`
در ابتدا شکست خورد. هر ۶۰۶ ردیف diff شدند و **فقط** متن JSON تفاوت داشت در
حالی که JSON پارس‌شده برابر بود؛ نمونهٔ دقیق `آكو` / `2026-09-06`:
`"prev_close": 39290` در برابر `39290.0`. علت، بازسازی ورودی از SQLite REAL است
(int در برابر float)، **نه اختلاف موتور**. هش معنایی (float-normalized) اضافه
شد و هش متن خام هم برای شفافیت نگه داشته شد: `raw_text_identical: false`،
`semantic_content_identical: true`، `not_an_engine_difference: true`.
هیچ چکی حذف یا ضعیف نشد؛ چک بایتی روی ۱۳ ستون دیگر همچنان سخت‌گیرانه است.

### ۹.۷ دامنهٔ نقص zero-event — سرشماری فهرست مرجع (stage10) — **PASS**

رأی مالک در §۱۲.۲ نباید با «۱ نماد از ۳۰» گرفته شود. stage10 جمعیتِ در معرض را
از **همان فهرست مرجعِ راستی‌آزمایی‌شده** سرشماری کرد: فقط خواندنی، **هیچ DB باز
نشد، هیچ bar اسکن نشد، هیچ ingest و هیچ کندلی ساخته نشد**. دامنه ۷۵۹ نمادِ
پوشش‌دار مرجع است، **نه پردازش ۶٬۱۰۳ نماد**.

| جمعیت | شمار |
| --- | --- |
| نمادهای فهرست مرجع | ۷۵۹ |
| دارای جفت روزانهٔ type0/type7 | ۷۵۹ |
| دارای تغییر q | ۷۴۵ |
| **نامزدِ نقص zero-event** | **۱۴** |
| بدون جفت | ۰ |
| جمع bar روزانهٔ آن ۱۴ | **۲۰٬۲۸۹** |
| اشتراک با گروه ۳۰ | ۱ (`پادا`) |

۱۴ نامزد: `آوا`، `افقملت`، `اوج`، `اوصتا`، `بذر`، `تمشک`، `ثروتم`، `داریوش`،
`سافرون`، `صنوین`، `مدیر`، `نیکگستر`، `ویستا`، `پادا`.

**شکافِ تلورانس اندازه‌گیری شد و برای این جمعیت بسته است.** فهرست مرجع تغییرِ
کمتر از `1e-3` را «بی‌تغییر» می‌نامد، در حالی که `q_changes` منجمدِ ingest گام
`1e-9` دارد؛ پس یک نامزد می‌توانست در موتور Factor تولید کند. برای هر ۱۴ نامزد
اندازه‌گیری شد: `factor_exact == factor_days − 1` و همهٔ سطل‌های دیگر تهی — یعنی
**هر نسبت روزانه دقیقاً ۱٫۰ بوده و q بایت‌به‌بایت ثابت است**، که گام `1e-9` هم آن
را بی‌تغییر می‌خواند. تلورانس هیچ‌کدام تغییر نکرد؛ فقط اثرش سنجیده شد.

**آنچه همچنان NOT_MEASURED است:**
- **سطح مطلق q** برای نامزدهای بیرون از گروه. `q≡1` نقصِ فقط‌هندسی می‌دهد (همان
  که روی `پادا` دیده شد)؛ `q≡c≠1` parity قیمت پایانی را هم می‌شکند. تفکیک این دو
  اسکن bar می‌خواهد و انجام نشد.
- **تأیید زندهٔ HTTP** برای ۱۳ نامزد دیگر؛ فقط گروه ۳۰ از مسیر Runtime گذشت.
- **دامنه روی Seed Candidate**؛ Seed روی این ماشین غایب است.

۱۰ کنترل از ۱۰ PASS، شامل چهار کنترل منفی: تزریق یک تغییر ساختگی شمار نامزد را
۱۴ → ۱۳ می‌برد؛ شکستن جفت همان کار را می‌کند و نماد را به «بدون جفت» می‌فرستد؛
رانش زیرآستانه از سطل «ثابتِ دقیق» جدا می‌شود؛ و طبقه‌بندِ «q ثابت» با یک روز
رانش آن را از دست می‌دهد. کنترل مثبت: `پادا` که stage08 زنده با صفر Factor دید،
هم در مجموعهٔ نامزد و هم در مجموعهٔ qثابت هست — وگرنه سرشماری با اندازه‌گیری
زنده در تضاد بود و مرحله FAIL می‌شد. بازاجرا بایت‌یکسان است
(`6e57b308215a599d…`).

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

**بازاجرای تازه پیش از کامیت این گزارش:** هر سه فرمان Go و هر پنج گیت ساختاری
دوباره اجرا شدند و **همه `rc=0`** دادند؛ `go test ./...` باز **۵۵ بسته ok،
۳ بدون فایل تست، ۰ شکست** و `go vet` خروجی تهی. پروفایل production باز
`۱۳ suite counted, 1 silent, 0 skipped` + `ALL SUITES PASSED` و پروفایل data
باز `۲۰ suite counted, 14 silent, 2 skipped` با exit ۱. خط `FAILED:` پروفایل
data **بایت‌به‌بایت با مقدار ثبت‌شده در `gates.json` یکسان است** (۲۹۶ نویسه) و
هر پنج سوئیت شکست‌خورده همان‌ها هستند. پس اعداد این بخش‌ها کهنه نیستند.

`build_artifacts_manifest.py` نیز بازاجرا شد و خروجی‌اش **بایت‌یکسان** ماند
(`BYTE_IDENTICAL=True`)؛ هیچ ساعتی در payload آن نیست.

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

### ۱۰.۵ Idempotency و کنترل‌های مصنوعات جدید

| مرحله | بازاجرا |
| --- | --- |
| stage01 ماتریس پوشش | payload بایت‌یکسان ✓ |
| stage02 انتخاب گروه | payload بایت‌یکسان ✓ |
| stage03 شواهد گروه | payload بایت‌یکسان ✓ |
| stage04 آمادگی محصول | payload بایت‌یکسان ✓ |
| stage05 گیت‌ها | payload بایت‌یکسان ✓ |
| stage06 بازیابی Capture | payload بایت‌یکسان ✓ — `b9c96302b8987c1a…` در اجرای دوم عیناً همان |
| stage07 کندل گروه | بایت‌یکسانی payload **اندازه‌گیری نشد**؛ ردیف‌های DB ستون `created_at` دارند |
| stage08 مسیر Runtime | بایت‌یکسانی payload **اندازه‌گیری نشد**؛ payload خودِ PID زنده را ثبت می‌کند |
| stage09 Idempotency | **محتوای** DB بایت‌یکسان اثبات شد (§۹.۶) — این خاصیت اصلی است |
| stage10 سرشماری zero-event | payload بایت‌یکسان ✓ — `6e57b308215a599d…` در اجرای دوم عیناً همان |

ساعت فقط در manifest است، هرگز در payloadهای stage01–06 و stage10. برای
stage07/08 ادعای بایت‌یکسانی مطرح نمی‌شود؛ در عوض stage09 ثابت می‌کند که
Factorها، کندل‌ها، شمارها و ردپای audit در اجرای دوباره **محتوای** یکسان دارند و
Revision بدون ساعت پایدار می‌ماند.

**کنترل‌های منفی stage03** (`test_stage03_controls.py`, verdict PASS):

| کنترل | انتظار | نتیجه |
| --- | --- | --- |
| A — کلید هویت استاندارد | exit 0 | ۰ ✓ |
| B — حذف join alias (کلید املای خام) | exit 2 | ۲ ✓ (۶ نماد drift) |
| C — شکستن پین SHA ورودی | exit 2 | ۲ ✓ |

هر دو گیت B و C **پیش از نوشتن هیچ خروجی** abort کردند. پس این گیت‌ها واقعاً
می‌توانند شکست بخورند؛ passشان vacuous نیست.

#### کنترل‌های stage06 / stage07 / stage08 / stage10 — ۹۵ کنترل، همه PASS

اجرای تازه، همه با `rc=0`:

| سوئیت | کنترل | passed | failed |
| --- | --- | --- | --- |
| `test_stage06_controls.py` | ۳۰ | ۳۰ | ۰ |
| `test_stage07_controls.py` | ۲۹ | ۲۹ | ۰ |
| `test_stage08_controls.py` | ۲۶ | ۲۶ | ۰ |
| `stage10_zero_event_census.py --selftest-only` | ۱۰ | ۱۰ | ۰ |
| جمع | **۹۵** | **۹۵** | **۰** |

نمونهٔ کنترل‌هایی که ثابت می‌کنند گیت‌ها گاز می‌گیرند:

| سوئیت | کنترل منفی | چه چیزی را می‌گیرد |
| --- | --- | --- |
| stage06 | `B_wrong_sha_detected` / `B_wrong_size_detected` | بایت بازیابی‌شدهٔ نادرست |
| stage06 | `B_container_and_payload_differ` | هش ظرف به‌جای هش payload ننشیند |
| stage06 | `F_corrupt_gzip_detected` / `F_truncated_gzip_detected` | gzip خراب یا بریده |
| stage06 | `E_missing_type7_day_detected` | حضور type0 بدون شاهد type7 «پوشش» نامیده نشود |
| stage06 | `E_window_not_spanned_detected` | حضور در فهرست ≠ پوشش بازه |
| stage07 | `C_perturbed_close_detected` / `C_status_downgraded` | انحراف قیمت مرجع |
| stage07 | `D_perturbed_volume_detected` | نقض ثبات حجم |
| stage07 | `G_anchor_violation_detected` | نقض `q(last)==1` (§۷.۵) |
| stage07 | `E_no_witness_stays_unclassified` | نوع رویداد از روی نسبت حدس زده نشود |
| stage07 | `F_broken_pin_aborts` / `F_no_db_created` | پین SHA شکسته ⇒ abort پیش از ساخت DB |
| stage08 | `A_no_adjusted_candles_needed` | fixtureای که هرگز build نشد همان پاسخ را می‌دهد ⇒ `adjusted_candles` مسیر Runtime نیست |
| stage08 | `B_zero_event_not_called_pass` | نماد zero-event هرگز PASS نامیده نشود |
| stage08 | `D_perturbed_volume_detected` / `D_perturbed_raw_close_detected` | انحراف مقدار سروشده در برابر oracle پین‌شده |
| stage08 | `E_foreign_provenance_rejected` | دادهٔ `legacy-unknown` به‌جای مرجع پذیرفته نشود |
| stage08 | `E_truncated_history_rejected` | تاریخچهٔ بریده |
| stage09 | `revision_sensitive_to_reference` | اگر مرجع عوض شود Revision **باید** عوض شود |

**سه خطای خودِ ما که پیدا و اصلاح شدند — و هیچ‌کدام پنهان نشد:**

1. **fixture مرحلهٔ ۰۷:** اولین اجرا ۴ از ۲۵ کنترل را شکست داد. ریشه، fixture
   مصنوعی بود نه موتور (§۷.۵). اصلاح شد + کنترل منفی G اضافه شد.
2. **گیت اولیهٔ مرحلهٔ ۰۷:** انتظار داشت `adjusted_candles` برای هر ۳۰ نماد
   ردیف داشته باشد و PARTIAL داد. آن انتظار **غلط** بود: builder فقط نمادهای
   دارای Factor را materialize می‌کند (`candlebuild.go:94`). گیت به دامنهٔ
   واقعی builder اصلاح شد و اندازه‌گیری زندهٔ نماد zero-event به stage08 اضافه
   شد. **هیچ معیار پذیرش Phase 4.9.2 و هیچ تلورانسی تغییر نکرد.**
3. **کنترل توتولوژیک مرحلهٔ ۰۸:** perturbing کردن `reference_raw.volume` هم
   oracle و هم مقدار سروشده را با هم جابه‌جا می‌کرد، پس کنترل نمی‌توانست
   شکست بخورد. اصلاح شد: دو اندازه‌گیری جدا — oracle روی DB perturb‌شده برای
   target-drift، و oracle پین‌شده روی DB **اصلی** برای served-drift.

هیچ سوئیت یا گاردی حذف، skip یا ضعیف نشد. هر سه اصلاح در payloadهای
`honesty` خودِ مراحل نیز ثبت شدند.

### ۱۰.۶ CI واقعی روی کامیت مصنوعات پیشین `612c9658`

این بخش CI کامیت مصنوعات **پیشین** را ثبت می‌کند (پیش از stage06–09). CI کامیت
مصنوعات جدید در §۱۰.۸ با SHA خودش ثبت می‌شود؛ هیچ نتیجه‌ای به SHA دیگری نسبت
داده نمی‌شود.

هر سه workflow روی **همین SHA** اجرا و تمام شدند (`head_sha` هر run برابر
`612c9658d3c69f0cd64ff8fa46c7c3e1491d6c7e`). منبع:
`_audit/phase49-3/evidence/CI-612c9658.json` — همان رکوردی که پیش‌تر در
`CI-FINAL-RESULTS.json` بود و پیش از بازنویسیِ آن فایل با CI کامیت جدید،
بایت‌یکسان کنار گذاشته شد (`a2db9bcc2dcdbc1d…`) تا اعداد این بخش در درختِ
نهایی هم پشتوانهٔ فایل داشته باشند.

| workflow | run id | شمارهٔ اجرا | نتیجهٔ workflow | jobها |
| --- | --- | --- | --- | --- |
| `guards` | `43041402983` | ۱۱۲۵ | success | **۹ از ۹ success** |
| `python-tooling` | `43041402907` | ۷ | success | **۱ از ۱ success** |
| `python-legacy` | `43041402885` | ۷ | success | **۱ success + ۱ failure** |

۹ job گارد: zero-python runtime proof، go backend (vet/ast-arch/unit-tests)،
data integrity guards، frontend v2 (typecheck/vitest/build)، EOL/attributes/no
tracked junk، go backend on windows (۲۰۲۲ و latest)، go race detector،
desktop delivery.

**سه پرچم جدا، و هیچ‌کدام از دیگری استنتاج نشده:**

| پرچم | مقدار |
| --- | --- |
| `all_workflows_success` | true |
| `all_jobs_success` | **false** |
| `all_blocking_jobs_success` | true |

#### تلهٔ report-only — روی همین کامیت هم تکرار شد

`python-legacy` در YAML هر دو job خود را `continue-on-error: true` گذاشته است.
پس workflow آن `success` گزارش می‌شود در حالی که job
`legacy Python maintenance (report-only)` روی این کامیت **`failure`** است.
این دقیقاً همان الگوی فاز قبلی است و **به‌عنوان موفقیت همهٔ jobها گزارش نمی‌شود**.

#### انتساب شکست: از پیش موجود، سوئیت‌به‌سوئیت اثبات شد

job شکست‌خورده در این کامیت و در کامیت پایه با هم مقایسه شدند:

| | این کامیت `612c9658` | پایه `e09ccd95` |
| --- | --- | --- |
| job id | `130593855060` | `130514848221` |
| run id | `43041402885` | `43018306670` |
| کل سوئیت‌ها | ۲۱۱ | ۲۱۱ |
| OK | ۱۸۱ | ۱۸۱ |
| FAIL | **۳۰** | **۳۰** |

**مجموعهٔ نام‌های شکست‌خورده عیناً یکسان است: `new = ۰`، `resolved = ۰`.**
پس این شکست به این مأموریت منتسب نیست — این مأموریت هیچ کد تولیدی تغییر نداده
است. ریشهٔ غالب، drift سوئیت‌های Python قدیمی با مهاجرت Go است؛ نمونهٔ واقعی از
log: `AttributeError: module 'symbol_identity' has no attribute 'pred'` و
`AttributeError: module 'api.chart' has no attribute '_adjust_events_for'`.

**یک تلهٔ اندازه‌گیری که گرفته شد:** نام سوئیت‌ها خودشان ویرگول دارند
(مثل `EPS evidence labels: one tier label on card, row and scan_symbol`).
جداکردن خطِ خلاصهٔ `FAILED:` روی ویرگول **۴۶ قطعه** می‌دهد، نه ۳۰ سوئیت.
شمارش درست از خط‌های تک‌سوئیتی (`OK|FAIL <name> rc=N`) می‌آید و با بازساختن
همان خط خلاصه از آن‌ها اثبات می‌شود که parser همهٔ سوئیت‌ها را دیده
(`parse_complete = true` در هر دو طرف).

**چهار کنترل منفی روی همین parser** (همه رفتار درست):

| کنترل | انتظار | نتیجه |
| --- | --- | --- |
| A — log واقعی | ۳۰ FAIL، parse کامل | ۳۰، true ✓ |
| B — کاشتن یک سوئیت شکست‌خوردهٔ جدید | در `new_failures` دیده شود | `PLANTED_NEW_BROKEN_SUITE` ✓ |
| C — حذف یک خط سوئیت با نگه‌داشتن خلاصه | `parse_complete = false` | false ✓ |
| D — سبزشدن یک سوئیت | در `resolved_failures` دیده شود | نام همان سوئیت ✓ |

پس اگر این مأموریت واقعاً سوئیتی را می‌شکست، این مقایسه آن را نشان می‌داد؛
`identical = true` آن vacuous نیست. recorder در صورت `new > 0` با exit غیرصفر
و پیام FATAL متوقف می‌شود.

**ساختار دو کامیتی:** `CI-FINAL-RESULTS.json` نمی‌تواند نتیجهٔ CI روی خودش را
در خود داشته باشد. رکورد کامیت مصنوعات پیشین `612c9658` بایت‌یکسان در
`_audit/phase49-3/evidence/CI-612c9658.json` کنار گذاشته شد و فایل اصلی اکنون
CI کامیت مصنوعات جدید `a265841c` را دارد (§۱۰.۸). CI کامیت docs-only جداگانه
بررسی و در پیام تحویل به مالک با SHA دقیق گزارش می‌شود.

### ۱۰.۷ صداقت CI — قلم‌هایی که نباید بزرگ‌نمایی شوند

- **python-legacy:** این lane report-only است. هم در فاز قبلی، هم روی
  `612c9658` و هم روی `a265841c` workflow آن `success` شد در حالی که job نگهداشت
  Python آن `failure` بود. موفقیت سطح workflow هرگز به‌معنی موفقیت همهٔ jobها
  گزارش نمی‌شود.
- **CI روی `3dc7318a`** هرگز به‌جای CI روی کامیت docs `e09ccd95` ارائه نمی‌شود.
  هر نتیجه SHA خودش را نام می‌برد.
- **Stage E:** استخراج کامل LZMA در فاز قبلی هم انجام نشد؛ آزمون مستقیم محصول
  روی کپی Seed جای آن را گرفت (۸/۸ سبز). این محدودیت همچنان پابرجاست.
- **`market_universe_v1`:** ۴۰۵٫۵ms در برابر آستانهٔ **تغییرنکردهٔ** ۴۰۰ms روی
  میزبان تک‌هسته‌ای؛ سوئیت مستقل ۱۷/۱۷. آستانه تغییر نکرد و benchmark بازاجرا
  نشد، چون این مأموریت هیچ کدی تغییر نداده است.
- **`SEED_RELEASE_OK`** یک verdict گیت است، نه اجازهٔ انتشار. گیت روی Seed
  Candidate غایب بازاجرا نشد و شرایطش تغییر نکرد.

### ۱۰.۸ CI واقعی روی کامیت مصنوعات جدید `a265841c`

| مورد | مقدار |
| --- | --- |
| کامیت | `a265841c709e7b91d635a43e99ae544e0b5fc584` |
| شاخه | `mission/phase49-3-coverage-expansion-2026-11-11` |
| مخزن | `johnwarchief/BorsTerminal-src` |
| زمان واکشی | `2026-11-11T22:47:25Z` |
| منبع | `docs/opportunity-center/phase49-3/CI-FINAL-RESULTS.json` |
| `head_sha` هر سه run | برابر همین کامیت — **تأیید شد** |
| workflow غایب | هیچ (`missing_workflows = []`) |

| workflow | run id | شمارهٔ اجرا | نتیجهٔ workflow | jobها |
| --- | --- | --- | --- | --- |
| `guards` | `43113282548` | ۱۱۲۹ | success | **۹ از ۹ success** |
| `python-tooling` | `43113282504` | ۱۱ | success | **۱ از ۱ success** |
| `python-legacy` | `43113282688` | ۱۱ | success | **۱ success + ۱ failure** (report-only) |

**سه پرچم جدا، هیچ‌کدام از دیگری استنتاج نشده:**

| پرچم | مقدار |
| --- | --- |
| `all_workflows_success` | true |
| `all_jobs_success` | **false** |
| `all_blocking_jobs_success` | true |

#### lane داده روی CI سبز شد — انتساب محیطی مستقل تأیید شد

job بازدارندهٔ `data/research suites (python dev/run_all_tests.py --profile data)`
روی CI **`success`** شد، در حالی که همان پروفایل روی این میزبان ۵ سوئیت FAIL داد
(§۱۰.۴). این یک تأیید **مستقل** است که آن ۵ شکست محیطی بودند (نبود `fastapi` و
`pypdfium2` روی میزبان)، نه رگرسیونِ این مأموریت. هیچ آستانه‌ای تغییر نکرد، هیچ
سوئیتی skip نشد و کنترلِ کامیت پایه هم همان counts را داده بود.

#### تلهٔ report-only — روی کامیت جدید هم تکرار شد

`python-legacy` هر دو job خود را `continue-on-error: true` گذاشته است، پس
workflow آن `success` گزارش می‌شود در حالی که job
`legacy Python maintenance (report-only)` روی `a265841c` **`failure`** است.
این به‌عنوان موفقیت همهٔ jobها گزارش **نمی‌شود**.

انتساب سوئیت‌به‌سوئیت در برابر همان job روی کامیت پایه:

| | این کامیت `a265841c` | پایه `e09ccd95` |
| --- | --- | --- |
| job id | `130834635951` | `130514848221` |
| run id | `43113282688` | `43018306670` |
| کل سوئیت | ۲۱۱ | ۲۱۱ |
| سوئیت ok | ۱۸۱ | ۱۸۱ |
| سوئیت FAIL | **۳۰** | **۳۰** |

`failed_sets_identical = true`، `new_failures = []`، `resolved_failures = []`،
`parse_complete_both = true`، `caused_by_this_mission = 0`. نام سوئیت‌ها comma
دارند، پس خلاصهٔ `FAILED` هرگز comma-split نشد؛ خطوط هر سوئیت پارس و خلاصه از
آن‌ها بازساخته شد تا کامل‌بودن پارس اثبات شود.

**نتیجه:** هیچ شکست تازه‌ای به این مأموریت منتسب نیست، و هیچ شکستی هم پنهان نشد.

---

## ۱۱. خطوط قرمز — همه رعایت شدند

| قید | وضعیت |
| --- | --- |
| Seed Candidate تغییر نکند | ✓ غایب بود؛ هرگز باز یا نوشته نشد |
| Production DB تغییر نکند | ✓ هرگز باز، کپی یا نوشته نشد |
| هیچ‌یک از دو DB روی دیگری کپی نشود | ✓ DB کاری از SCHEMA منجمد **تازه** ساخته شد، نه کپی Seed و نه کپی Pilot |
| ردیف دارای اختلاف بدون شاهد معتبر بازنویسی نشود | ✓ ۶۷ `MISMATCH` و ۲ `CONFLICT_DUPLICATE` دست‌نخورده |
| ۴۰۴ رویداد با نوع رسمی نامشخص | ✓ `corporate_action_unclassified` ماند؛ نوع از روی نسبت حدس زده نشد |
| ۳۰۶ ردیف OHLC نامعتبر قدیمی | ✓ بدون شاهد اصلاح نشد |
| ۱۰٬۹۸۲ اختلاف فیلدی عمدی | ✓ قابل ردیابی و دست‌نخورده |
| `legacy-unknown` بدون اعتبارسنجی Price Basis | ✓ مصرف نشد؛ ریسک ۳۰/۳۰ نماد گروه صریح ثبت شد |
| رویداد بدون شاهد verified ثبت نشود | ✓ ۴۶ ردیف `NO_EVIDENCE` همان‌گونه ماند |
| کندل روز Capture قرنطینه | ✓ قاعدهٔ `date >= capture_day` اجرا شد؛ `capture_day = 2026-11-11`، آخرین bar `2026-11-10` ⇒ **۰** bar قرنطینه (عدد واقعی، نه ادعا) |
| کندل روز جاری وارد زنجیرهٔ تعدیل نشود | ✓ آخرین تاریخ لنگر ۲۹ نماد `2026-11-10` و یک نماد `2026-11-04` |
| تلورانس‌ها برای سبزشدن شل نشوند | ✓ `1e-9` موتور و پنجره‌های منجمد pack عیناً مصرف شدند |
| `measured.go` / `candlebuild` بازنویسی نشوند | ✓ `git diff e09ccd95 -- backend-go/` خالی |
| نقص `پادا` خودسرانه اصلاح نشود | ✓ ثبت و انتساب داده شد؛ **دست نخورد** — رأی مالک (§۱۲) |
| ۳۵۰ رویداد جدیدِ بی‌نوع رسمی | ✓ `corporate_action_unclassified` ماند؛ نوع از روی نسبت حدس زده نشد |
| هیچ Suite/Guard حذف، skip یا ضعیف نشد | ✓ شکست‌ها همان‌گونه گزارش شدند؛ دو گیتِ خودِ ما اصلاح شد و هر دو اصلاح افشا شد (§۷.۵، §۹.۶) |
| رمز عبور درخواست/ذخیره نشد | ✓ هرگز |
| دادهٔ ساختگی / Capture جعلی | ✓ هیچ؛ فقط بایت‌های licensed بازیابی‌شدهٔ مالک |
| پردازش خودکار کل ۶٬۱۰۳ پس از موفقیت گروه | ✓ انجام نشد؛ فقط ۳۰ نماد منجمد پردازش شد |
| `main` تغییر نکند | ✓ روی `2c3e8726` ماند |
| Rebase / Merge / Cherry-pick / Tag / Release | ✓ هیچ‌کدام انجام نشد |
| Worktreeهای موجود حفظ شوند | ✓ هیچ checkout موجودی جابه‌جا نشد؛ شاخهٔ مالک فقط با `git cat-file` خوانده شد |

نتایج پذیرفته‌شدهٔ Phase 4.9.2 **بازتولید نشدند**: فرمول تعدیل، ۳۰/۳۰ parity با
max rel ≈ 2.0e-15، ۱۰۵٬۶۹۲ کندل خام + ۱۰۵٬۶۹۲ adjusted، و idempotency
revision/rebuild همان‌گونه پذیرفته ماندند.

**ظرافت شمارش رویداد که حفظ شد:** `event-parity.json` دارای **۱٬۰۲۸ ردیف
مقایسه‌شده** است = ۹۶۰ `MATCH` پیش از fix + ۶۷ `MISSING` مرجع + ۱ `EXTRA` موتور.
بنابراین **رویدادهای مرجع = ۱٬۰۲۷** و آن ردیف اضافی فقط‌موتور است؛ پس از fix
۱٬۰۲۷ match شد و extra ناپدید گشت. ۱٬۰۲۸ ردیف هرگز ۱٬۰۲۷ رویداد نامیده نمی‌شود.

---

## ۱۲. تصمیم‌هایی که به رأی مالک نیاز دارند

### ۱۲.۱ افزایش پوشش — آنچه اندازه‌گیری شد در برابر آنچه هنوز تحویل نشده

**گروه ۳۰ منجمد — عدد واقعی، نه برآورد:**

| قلم | مقدار | کجا اندازه‌گیری شد |
| --- | --- | --- |
| ردیف خام مرجع ingest‌شده | **۸۴٬۴۵۲** | DB کاری مستقل |
| ردیف adjusted مرجع | **۸۴٬۴۵۲** | همان |
| کندل materialize‌شده | **۸۳٬۲۵۴** (۲۹ نماد) | همان |
| Factor | **۶۰۶** | همان |
| ردیف `price_history` همین ۳۰ نماد در Seed | ۲۸٬۰۵۱ | از ledger ثبت‌شده؛ خودِ Seed روی این ماشین غایب است |
| افزایشِ **مورد انتظار** در صورت merge | +۵۶٬۴۰۱ (۳٫۰۱×) | **محقق نشده — هیچ merge انجام نشد** |

آنچه از برآورد به اندازه‌گیری تبدیل شد، **شمار ردیف ingest‌شده** است: ۸۴٬۴۵۲
دقیقاً برابر پیش‌بینی منجمد. اما **+۵۶٬۴۰۱ افزایشِ تحویل‌شده نیست**؛ تفاضل دو
عدد از دو جامعهٔ متفاوت است — bar مرجع در DB کاری منهای ردیف `price_history`
همان نمادها در Seed. پیش‌نویس پیشین این بخش آن را در ستون «پیش / پس» گذاشته
بود و ۲۸٬۰۵۱ را «ردیف خام مرجعِ پیش» نامیده بود؛ هر دو غلط بودند و اصلاح شدند.

**مرزبندی حیاتی:** این افزایش در **DB کاری مستقل** (`_audit/phase49-3/db/cohort.db`)
است. **Seed Candidate تغییر نکرد و هیچ ردیفی به آن اضافه نشد.** پس این
«ظرفیت اثبات‌شده» است، نه «پوشش تحویل‌شده در Seed». هیچ انتشاری انجام نشد.

**بقیهٔ فرصت‌ها — همچنان برآورد، اندازه‌گیری‌نشده:**

- **بدون Capture جدید:** ۶۷۵ نماد `QUEUE_REFERENCE_ONLY` (+۱٬۵۶۸٬۰۶۰ ردیف،
  ۶٫۷۱ برابر) و ۵۴ نماد halted (+۱۳۵٬۲۴۴ ردیف از ۱۵۳٬۳۶۵ bar مرجع، ۸٫۴۶ برابر)
  مشروط به رأی halted. این‌ها **پردازش نشدند**.
- **با Capture جدید:** ۳٬۳۰۸ نماد دیگر.
- **نیازمند منبع/تصمیم دیگر:** ۱٬۴۶۸ حل هویت، ۱۹۱ نقشهٔ asset-id،
  ۳۷۷ رأی halted + Capture.

### ۱۲.۲ رأی یکم — نقص پوشش‌یابی `پادا` (فوری‌ترین)

پوشش اکنون از «مجموعهٔ Factor ناتهی» استنتاج می‌شود. نمادی که مرجع کامل دارد
اما هیچ رویداد تعدیل ندارد (`q≡1`)، پوشش‌نداده تلقی می‌شود و تصحیح نمایشیِ
بسته را می‌گیرد — که نتیجه‌اش **دو کندل با open بالاتر از high** است (§۹.۴).

| گزینه | اثر | هزینه |
| --- | --- | --- |
| پوشش از حضور `reference_raw` تشخیص داده شود | `پادا` و هر نماد zero-event دیگر مسیر درست را می‌گیرند؛ هندسه اصلاح می‌شود | تغییر در `measured.go` / هندلر — **مأموریت بدون رأی مالک ممنوع کرده** |
| وضعیت موجود بماند | قیمت پایانی درست می‌ماند | نقص دیداری چارت روی نمادهای zero-event باقی می‌ماند |

**این مأموریت هیچ‌کدام را انتخاب نکرد.** دامنهٔ نقص اکنون یک عدد اندازه‌گیری‌شده
دارد، نه حدس: stage10 از فهرست مرجع **۱۴ نامزد از ۷۵۹** نماد پوشش‌دار یافت
(۲۰٬۲۸۹ bar روزانه)، که یکی از آن‌ها همان `پادا` است که زنده تأیید شد (§۹.۷).
برای هر ۱۴، q بایت‌به‌بایت ثابت است، پس شکاف تلورانس `1e-3` در برابر `1e-9`
این جمعیت را مبهم نمی‌کند.

آنچه همچنان اندازه‌گیری **نشده**: سطح مطلق q آن ۱۳ نامزد دیگر (نقص فقط‌هندسی یا
شکستن parity قیمت)، تأیید زندهٔ HTTP آن‌ها، و دامنه روی **Seed Candidate** که روی
این ماشین غایب است. تعمیم به کل ۶٬۱۰۳ نماد همچنان یک **برآورد** است، نه اندازه‌گیری.

### ۱۲.۳ رأی دوم — مقیاس‌پذیری

گروه ۳۰ موفق شد. **پردازش خودکار کل ۶٬۱۰۳ انجام نشد و نخواهد شد.** تصمیم
اینکه گروه بعدی کدام باشد و آیا ۶۷۵ نماد `QUEUE_REFERENCE_ONLY` بازیابی شوند،
با مالک است.

### ۱۲.۴ رأی سوم — Seed و انتشار

`SEED_RELEASE_OK` یک verdict گیت است، **نه اجازهٔ انتشار**. Seed روی این ماشین
غایب بود، پس گیت آن بازاجرا نشد و شرایطش تغییر نکرد. هیچ ادعایی دربارهٔ
آمادگی انتشار Seed مطرح نمی‌شود.

### ۱۲.۵ دو ریسک که باید دیده شوند

1. **دادهٔ licensed در مخزن عمومی.** مجوز Capture «owner subscription; not
   redistributable» است و مخزن `BorsTerminal-src` عمومی است. بایت‌ها اکنون به‌صورت
   LFS object روی شاخهٔ مالک push شده‌اند. این مأموریت آن تصمیم را نگرفت و
   نمی‌گیرد؛ فقط ثبت می‌کند که **تعارض مجوز و دید عمومی** نیازمند رأی مالک است.
2. **تداخل `_audit/.gitignore`.** هر دو شاخه (مأموریت و مالک) این فایل را تغییر
   داده‌اند. شاخهٔ مأموریت فقط یک خط `/phase49-3/bin/` اضافه کرد. هیچ merge یا
   rebase انجام نشد؛ حل تداخل به تصمیم مالک موکول است.

---

## ۱۳. مصنوعات

| مسیر | چیست |
| --- | --- |
| `docs/opportunity-center/phase49-3/COVERAGE-EXPANSION-REPORT.md` | همین گزارش |
| `docs/opportunity-center/phase49-3/COHORT-SELECTION.json` | گروه ۳۰ منجمد با دلایل و SHA ورودی |
| `docs/opportunity-center/phase49-3/COVERAGE-EXPANSION-MAP.csv` | ماتریس ۶٬۱۰۳ × ۶۴ |
| `docs/opportunity-center/phase49-3/ARTIFACTS-SHA256.txt` | هش همهٔ گزارش‌ها، شواهد، ورودی‌ها و خروجی‌ها |
| `docs/opportunity-center/phase49-3/CI-FINAL-RESULTS.json` | CI واقعی روی `a265841c`؛ سه پرچم جدا (workflow/job/blocking) + انتساب سوئیت‌به‌سوئیت شکست report-only به کامیت پایه |
| `_audit/phase49-3/evidence/CI-612c9658.json` | رکورد CI کامیت مصنوعات پیشین، بایت‌یکسان کنار گذاشته‌شده تا اعداد §۱۰.۶ پشتوانه داشته باشند |
| `_audit/phase49-3/evidence/` | شواهد مشتق کامیت‌شده |
| `_audit/phase49-3/ledgers/` | ledgerهای مشتق کامیت‌شده |
| `_audit/phase49-3/manifests/` | manifest هر مرحله با SHA ورودی/خروجی، counts، زمان، وضعیت |
| `_audit/phase49-3/*.py` | اسکریپت‌های مرحله (قابل بازاجرا) |
| `_audit/phase49-3/{captures,db,logs,bin}/` | gitignored — دادهٔ خام، کپی DB، لاگ اجرا، باینری ساخته‌شده |

### ۱۳.۱ شواهد هر مرحله و هش payload

ستون «وضعیت» عیناً همان رشته‌ای است که manifest همان مرحله ثبت کرده است، نه
برچسبی که من از آن ساخته باشم.

| مرحله | payload | SHA-256 (کوتاه) | exit ثبت‌شده | وضعیت ثبت‌شده در manifest |
| --- | --- | --- | --- | --- |
| stage01 ماتریس پوشش | `coverage-reconciliation.json` | `55b7338c700cf3fb…` | ثبت نشده | `PASS` |
| stage02 انتخاب گروه | `COHORT-SELECTION.json` | `857573dd33676d18…` | ثبت نشده | `PASS` |
| stage03 شواهد گروه | `cohort-event-evidence.json` | `97749aaf65f3d78c…` | ثبت نشده | `PASS_EXTRACTION_ONLY` + `candle_level_status: BLOCKED` |
| stage04 آمادگی محصول | `product-readiness.json` | `f11b0a02f62517fe…` | ثبت نشده | `PASS_CONTRACT_ONLY` + `product_test_status: NOT_MEASURED` |
| stage05 گیت‌ها | `gates.json` | `603e01b903bd0c0e…` | ثبت نشده | `PASS_WITH_PROVEN_PRE_EXISTING_DATA_LANE_FAILURES` |
| stage06 بازیابی Capture | `RESTORED-CAPTURE-VERIFICATION.json` | `b9c96302b8987c1a…` | ۰ | **PASS** |
| stage07 کندل گروه | `COHORT-CANDLES.json` | `e0a58be2af0e548b…` | ۰ | **PASS** |
| stage08 مسیر Runtime | `RUNTIME-READPATH.json` | `6a50ac7b040aa297…` | **۱** | **PARTIAL** |
| stage09 Idempotency | `IDEMPOTENCY.json` | `a434f6ce4d7e5847…` | ۰ | **PASS** |
| stage10 سرشماری zero-event | `ZERO-EVENT-CENSUS.json` | `6e57b308215a599d…` | ۰ | **PASS** |

exit غیرصفر stage08 **عمدی و fail-closed** است: یک نماد PARTIAL دارد، پس مرحله
نمی‌تواند PASS گزارش کند. هیچ چکی برای سبزشدن حذف نشد.

**چرا exit مراحل ۰۱ تا ۰۵ «ثبت نشده» است:** آن پنج manifest پیش از قرارداد
`exit_code` + `payload_sha256` نوشته شدند (قراردادی که از stage06 به بعد برقرار
است). آن‌ها به‌جای exit، کلید `status` و هش خروجی‌ها را در `outputs` ثبت می‌کنند.
نوشتن «exit ۰» برای آن‌ها ادعایی بود که هیچ فیلدی پشتیبانی نمی‌کرد؛ در جدول بالا
حذف شد. هر ۸ هش خروجیِ ثبت‌شدهٔ آن پنج مرحله همین حالا دوباره از روی دیسک
اندازه‌گیری شد: **۰ ناهمخوانی**.

**تصحیحی که باید دیده شود:** پیش‌نویس پیشینِ همین جدول، stage03 را `PARTIAL` و
stage04 را `NOT_MEASURED` نامیده بود. آن دو برچسبِ استنتاجیِ من بودند، نه مقدارِ
ثبت‌شده؛ manifestها چیز دیگری می‌گویند (`PASS_EXTRACTION_ONLY` و
`PASS_CONTRACT_ONLY`، با زیروضعیت‌های بالا). جدول اصلاح شد؛ **خودِ manifestها
بازنویسی نشدند.**

**`candle_level_status: BLOCKED` در stage03 منسوخ شده، نه پاک‌شده:** آن وضعیت در
زمان نوشتنش درست بود — بایت‌های جفتِ Capture روی این ماشین غایب بودند، پس هیچ
کندلی نمی‌شد ساخت. اکنون stage07 (PASS) و stage08 (PARTIAL) جای آن را گرفته‌اند.
فایل ثبت‌شده دست‌نخورده ماند و جانشینی همین‌جا اعلام می‌شود، نه با ویرایش تاریخ.

یک ناهمسانی ظاهری هم ثبت می‌شود: manifest مرحلهٔ stage02 مسیر خروجی را با `\`
نوشته و بقیه با `/`. هش یکی است و فایل درست است؛ فقط کلید مسیر ناهمگون است.
بازنویسی نشد چون مصنوعِ منجمد است.

هش کامل همهٔ مصنوعات در `ARTIFACTS-SHA256.txt` است.

### ۱۳.۲ چه چیزی کامیت شد و چه چیزی نشد

| دسته | جایگاه |
| --- | --- |
| گزارش‌ها، CSV ماتریس، JSON گروه، هش‌ها | `docs/opportunity-center/phase49-3/` — کامیت |
| payloadهای شواهد و manifestهای مراحل | `_audit/phase49-3/{evidence,manifests}/` — کامیت |
| اسکریپت‌های مرحله و کنترل‌ها | `_audit/phase49-3/*.py` — کامیت |
| بایت‌های licensed Capture | `_audit/phase49-full-verification/captures/` — **gitignored در این شاخه** |
| DB کاری، کپی Runtime، کپی Idempotency | `_audit/phase49-3/db/` — gitignored |
| باینری‌های ساخته‌شده (`borsd`, `candlebuild`) | `_audit/phase49-3/bin/` — gitignored |
| لاگ اجرا | `_audit/phase49-3/logs/` — gitignored |

اسکریپت جدید فقط جایی نوشته شد که قابلیت موجود نبود. stage06–09 هیچ موتور
دوم یا مسیر محاسباتی موازی نساختند: ingest از `_audit/phase49-2/ingest_reference.py`
منجمد import شد، کندل‌ها را خود `candlebuild` Go ساخت و پاسخ HTTP را خود `borsd`
Go داد. سمت Python فقط خواند و مقایسه کرد.