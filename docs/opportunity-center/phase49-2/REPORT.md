# گزارش فنی Phase 4.9.2 — دیتابیس مستقل کندل Performance-Adjusted

**حکم دامنه‌دار:** `PHASE49.2_ACCEPTANCE_MET_FOR_30_SYMBOL_PILOT`

برای ۳۰ نماد Pilot، هر هفت معیار پذیرش اصلاحیۀ مالک برآورده شد: Raw و
Adjusted در بانک محلی، موتور Go مستقل، مقایسهٔ کامل با type7 ره‌آورد، اختلاف‌های
ریشه‌یابی‌شده، نمودار از بانک محلی، بی‌نیازی از ره‌آورد پس از دریافت داده، و
زنجیرۀ به‌روزرسانی قابل بازتولید. پوشش کل بازار (۶٬۱۰۳ نماد) هنوز کامل نیست و
در صف per-symbol است؛ این گزارش آن را به‌عنوان Blocker سراسری مطرح نمی‌کند.

**مبنا:** شاخهٔ `mission/phase49-full-verification-python-ci-2026-11-10`،
Commit شروع `6d63e89d`، Commit کد/دادهٔ `3dc7318a` (CI سبز: `guards`
۹/۹ job، `python-tooling`، `python-legacy`)، Seed فاز ۴.۹.۱ با SHA-256
`57118e8fc99ff69c9e9812002f1d72571f357c23287fc1880a2f00b8292bbcb5`،
Capture تازه از نشست مالک با SHA-256
`6c8999ec2401a37a1c17370be6d06f155055d8d593b99c08100d3dd42beb8834`.

---

## ۱. خلاصۀ اجرایی

| موضوع | نتیجه |
| --- | --- |
| رفتار type7 ره‌آورد | تعدیل ضربی عقب‌نگر روی OHLC، حجم دست‌نخورده، لنگر روی آخرین جلسۀ کامل |
| ریاضیات موتور فعلی | درست بود؛ `factor(t)=∏ ratio(events with date>t)` با لنگر آخر |
| نقص اصلی | مجموعهٔ Factor: ۳۶۴ رویداد مرجع بدون گامِ پک، ۱۶ گام محصولِ بی‌شاهد، ۳ نسبت غلط، ۴ رویداد مرزی غایب |
| پاریتی قبل | ۱۶ از ۳۰ نماد ≤ `1e-6`؛ بدترین ۱۲٬۱۴۱٫۸× (شنفت) |
| پاریتی بعد | **۳۰ از ۳۰ نماد ≤ `2.0e-15`**؛ ۱٬۰۲۷ از ۱٬۰۲۷ رویداد منطبق |
| دیتابیس مستقل | ۱۰۵٬۶۹۲ کندل خام + ۱۰۵٬۶۹۲ کندل Adjusted + ۱٬۰۲۷ Factor + ۱٬۲۳۲ Action |
| تأیید | ۱۰۵٬۶۹۲ از ۱۰۵٬۶۹۲ ردیف `EXACT` |
| به‌روزرسانی | Revision عوض می‌شود، زنجیره بازمحاسبه می‌شود، ساخت دوباره ایدمپوتنت است |
| Seed | تأیید مالک ثبت شد؛ گیت باز شد؛ ۱۴/۱۴ بررسی Integrity/Hash/Idempotency و ۸/۸ بررسی محصول سبز |

## ۲. آنچه از موتور فعلی قابل استفاده بود

- `canonicalPriceHistory` و قرارداد کندل (`candlecontract.Widen`) برای خواندن
  OHLC و حجم.
- `canonicalAdjustment` و `chainFactors`: زنجیرۀ ضربی معکوس و لنگر آخرین تاریخ،
  دقیقاً همان چیزی که type7 نشان می‌دهد.
- `adjustCapabilityFull` و قرارداد JSON چارت که فرانت‌اند مصرف می‌کند
  (`candles[]` + `factors[]`).
- مسیر `adjust_events`/`price_adjust_events`/`share_change_events` برای نمادهای
  بدون مرجع، به‌عنوان Fallback دست‌نخورده.

## ۳. آنچه اصلاح شد

| فایل | تغییر |
| --- | --- |
| `backend-go/internal/chart/measured.go` (جدید) | `measuredFactorEvents` (جدول `adjustment_factors`)، `referenceRawHistory` (جدول `reference_raw`)، و `ChainFactors` برای مصرف بیرونی |
| `backend-go/internal/chart/canonical.go` | اگر Factor اندازه‌گیری‌شده باشد، همان مجموعه جای پک/محصول/دفتر رسمی را می‌گیرد؛ سری خام از `reference_raw` می‌آید |
| `backend-go/internal/chart/chartdb.go` | منبع `local-measured-factors` و Revision در پاسخ |
| `backend-go/internal/chart/handlers.go` | برای نماد پوشش‌داده، تصحیح نمایشیِ پک اعمال نمی‌شود |
| `backend-go/internal/candlebuild` + `cmd/candlebuild` (جدید) | محاسبهٔ Go برای `adjusted_candles` و `adjustment_verification` با Revision و تأیید ردیف‌به‌ردیف |
| `scripts/check_seed_release.py` | رکورد تأیید مالک به‌جای فلگ دستی؛ Manifest نامعتبر همچنان مسدود |
| `scripts/test_check_seed_release.py` | ۷ سناریوی جدید تأیید/عدم‌تأیید |

## ۴. بازسازی رفتار Performance-Adjusted ره‌آورد

- `q(t) = type0.close(t) / type7.close(t)`؛ در بازۀ بین رویدادها ثابت، در آخرین
  جلسۀ کامل `q=1`.
- `factor(t) = ∏ ratio(event) برای event.date > t` و `adjusted = raw × factor`.
- سود نقدی: `(prev_close − DPS) / prev_close`.
- افزایش سرمایه: `shares_old / shares_new`.
- ترکیبی: حاصل‌ضرب، با نسبتِ دقیقِ اندازه‌گیری‌شده از مرجع (نه بازمحاسبهٔ DPS
  گردشده).
- قیمت گشایش نقش مستقل ندارد؛ O/H/L/C با یک ضریب تعدیل می‌شوند و حجم ثابت است.
- کندل روز جاری قرنطینه شد: برای طلا تغییر `0.9948` در ۲۰۲۶-۱۱-۱۱ باعث خطای
  ۰٫۵۲٪ در ۲٬۲۱۰ ردیف می‌شد؛ با حذف آن از زنجیره، همهٔ ردیف‌ها `EXACT` شدند.

جزئیات و شواهد عددی: `docs/opportunity-center/phase49-2/ENGINE-AUDIT.md`.

## ۵. نتیجهٔ مقایسهٔ ۳۰ نماد

| معیار | قبل | بعد |
| --- | --- | --- |
| نماد با `max_rel ≤ 1e-6` | ۱۶/۳۰ | **۳۰/۳۰** |
| بدترین خطا | ۱۲٬۱۴۱٫۸× (شنفت) | `2.0e-15` |
| رویداد منطبق | ۹۶۰ MATCH، ۶۷ MISSING، ۱ ENGINE_EXTRA | **۱٬۰۲۷ MATCH** |
| ردیف Adjusted تأییدشده | — | ۱۰۵٬۶۹۲/۱۰۵٬۶۹۲ `EXACT` |
| منبع چارت | پک/محصول | `local-measured-factors` برای ۳۰/۳۰ |

نمادهای واگرای قبل و ریشهٔ هرکدام:

| نماد | خطای قبل | ریشه |
| --- | ---: | --- |
| شنفت | ۱۲٬۱۴۱٫۸× | ۳۷ رویداد مرجعِ غایب از پک (۱۹۹۱–۲۰۰۹ و مرز ۱۹۹۵) |
| طلا | ۹× | رویداد ۱۰:۱ در ۲۰۲۶-۱۱-۰۲ در پک نبود |
| مارون | ۶۶۷٪ | ۹ رویداد مرجعِ غایب |
| غشان | ۲۸۳٪ | گام محصول `0.00655` در ۲۰۲۴-۰۸-۲۴ بدون تغییر مرجع |
| شصفها | ۲۲۰٪ | ۳ رویداد غایب |
| سرود | ۳۳٫۸٪ | ۲ رویداد غایب |
| كچاد | ۱۸٫۱٪ | ۱ رویداد غایب |
| چكاوه | ۷٫۶٪ | ۲ رویداد غایب |
| تپسي | ۵٫۶۹× | تقسیم ۲۰۲۶-۱۱-۱۰ در پک نبود |
| ولانا | ۶۶٫۷٪ | ۳ رویداد؛ دو نسبت غلط (۲۰۱۹، ۲۰۲۶) و یک گام اضافه |
| ارمغان | ۲٫۵۷٪ | رویداد ۲۰۲۶-۰۶-۱۳ با نسبت غلط `0.998709` در برابر `0.973551` |
| كمند/پارند | ۲٫۵۶٪ | ۱ رویداد غایب در هرکدام |
| خودرو | ۱٫۵۶٪ | ۴ رویداد پیش از ۲۰۱۰ |
| ثباغ/داسوه/ثتران/… | `≤1e-15` | فاکتورهای پک درست بودند |

## ۶. دیتابیس مستقل

مسیر ساخت (روی کپی، بدون دست‌زدن به Seed):

```bash
python _audit/phase49-2/ingest_reference.py --force
go run ./backend-go/cmd/candlebuild --db _audit/phase49-2/db/market.db
```

جدول‌ها:

| جدول | معنا | ردیف |
| --- | --- | ---: |
| `reference_raw` | OHLCV خام type0، با SHA کپچر | ۱۰۵٬۶۹۲ |
| `reference_adjusted` | Close تعدیل‌شدۀ type7 برای صحت‌سنجی | ۱۰۵٬۶۹۲ |
| `adjustment_factors` | نسبت هر رویداد + q قبل/بعد + Provenance + Revision | ۱٬۰۲۷ |
| `adjustment_factor_audit` | گام‌های پک: بی‌تغییر، جایگزین‌شده، غایب | ۳۸۴ |
| `corporate_actions` | DPS/EPS از Marks + share_change رسمی | ۱٬۲۳۲ |
| `factor_action_links` | پیوند Factor به Action با پنجرهٔ تاریخ و نسبت | — |
| `adjusted_candles` | OHLCV تعدیل‌شده + Factor + Revision | ۱۰۵٬۶۹۲ |
| `adjustment_verification` | مقایسه با type7، وضعیت `EXACT/DIFF` | ۱۰۵٬۶۹۲ |
| `candle_build_revisions` | Revision، تعداد ردیف، max rel | ۳۰ |

تعداد Factorها به تفکیک نوع: ۵۸۶ سود نقدی، ۳۷ افزایش سرمایه، ۴۰۴ رویداد با
نسبتِ اندازه‌گیری‌شده و نوعِ نامشخص (بدون حدس).

## ۷. پوشش و نمادهای آماده

`_audit/phase49-2/ledgers/COVERAGE-STATUS.csv` برای هر ۶٬۱۰۳ نماد یک ردیف دارد:

| وضعیت | تعداد | معنا |
| --- | ---: | --- |
| `READY_PILOT` | ۳۰ | خام کامل + Factor + Adjusted + تأیید EXACT |
| `QUEUE_NO_REFERENCE` | ۳٬۳۰۸ | پنجرۀ مرجع ندارند؛ مسیر پک/محصول |
| `QUEUE_NO_INSTRUMENTS` | ۱٬۴۶۸ | ردیف instruments ندارند |
| `QUEUE_REFERENCE_ONLY` | ۶۷۵ | مرجع دارند ولی Factor آن‌ها وارد DB مستقل نشده |
| `QUEUE_HALTED` | ۴۳۱ | متوقف |
| `QUEUE_UNMAPPED_ASSET_ID` | ۱۹۱ | Asset ID ندارند |

۳۰ نماد آماده (جدول کامل):

| نماد | کندل خام | اولین | آخرین | Factor | Adjusted | تأیید | max rel |
| --- | ---: | --- | --- | ---: | ---: | --- | ---: |
| ارمغان | 1685 | 2019-10-15 | 2026-11-10 | 84 | 1685 | 1685/1685 | 1.7e-15 |
| تپسي | 738 | 2022-06-14 | 2026-11-10 | 5 | 738 | 738/738 | 3.3e-16 |
| ثباغ | 3428 | 2011-05-11 | 2026-11-10 | 21 | 3428 | 3428/3428 | 6.7e-16 |
| ثتران | 3237 | 2012-01-11 | 2026-11-10 | 8 | 3237 | 3237/3237 | 2.2e-16 |
| خمهر | 4626 | 2004-03-10 | 2026-11-10 | 11 | 4626 | 4626/4626 | 4.4e-16 |
| خودرو | 6757 | 1993-08-01 | 2026-11-10 | 38 | 6757 | 6757/6757 | 7.8e-16 |
| دارا | 1689 | 2019-08-26 | 2026-11-10 | 44 | 1689 | 1689/1689 | 4.4e-16 |
| داسوه | 5342 | 1994-02-27 | 2026-11-04 | 40 | 5342 | 5342/5342 | 8.9e-16 |
| دالبر | 4798 | 1997-03-11 | 2026-11-10 | 44 | 4798 | 4798/4798 | 8.9e-16 |
| سبهان | 4088 | 2003-07-15 | 2026-11-10 | 26 | 4088 | 4088/4088 | 1.6e-15 |
| سخند | 1950 | 2015-07-04 | 2026-11-10 | 85 | 1950 | 1950/1950 | 4.4e-16 |
| سرود | 4850 | 2003-06-07 | 2026-11-10 | 28 | 4850 | 4850/4850 | 4.4e-16 |
| شصفها | 4149 | 2000-02-13 | 2026-11-10 | 17 | 4149 | 4149/4149 | 4.4e-16 |
| شنفت | 6284 | 1991-05-11 | 2026-11-10 | 50 | 6284 | 6284/6284 | 1.9e-15 |
| شپارس | 3600 | 1993-04-25 | 2026-11-10 | 31 | 3600 | 3600/3600 | 6.7e-16 |
| طلا | 2209 | 2017-06-10 | 2026-11-10 | 1 | 2209 | 2209/2209 | 2.2e-16 |
| غدشت | 3513 | 1996-03-18 | 2026-11-10 | 29 | 3513 | 3513/3513 | 4.4e-16 |
| غشان | 3719 | 2005-06-13 | 2026-11-10 | 25 | 3719 | 3719/3719 | 1e-15 |
| غگرجي | 4508 | 1991-04-22 | 2026-11-10 | 36 | 4508 | 4508/4508 | 2e-15 |
| كالا | 1673 | 2019-02-05 | 2026-11-10 | 8 | 1673 | 1673/1673 | 3.3e-16 |
| كمند | 2182 | 2017-07-29 | 2026-11-10 | 110 | 2182 | 2182/2182 | 8.9e-16 |
| كچاد | 4913 | 2003-10-19 | 2026-11-10 | 37 | 4913 | 4913/4913 | 8.9e-16 |
| لپارس | 5811 | 1991-04-06 | 2026-11-10 | 30 | 5811 | 5811/5811 | 6.7e-16 |
| مارون | 3243 | 2011-12-27 | 2026-11-10 | 16 | 3243 | 3243/3243 | 4.4e-16 |
| هجرت | 1591 | 2019-08-10 | 2026-11-10 | 9 | 1591 | 1591/1591 | 4.4e-16 |
| ولانا | 1892 | 2013-11-30 | 2026-11-10 | 11 | 1892 | 1892/1892 | 6.7e-16 |
| وپارس | 4315 | 2004-11-30 | 2026-11-10 | 23 | 4315 | 4315/4315 | 1.1e-15 |
| پارند | 2443 | 2016-07-09 | 2026-11-10 | 115 | 2443 | 2443/2443 | 8.9e-16 |
| چكاوه | 4417 | 1997-09-24 | 2026-11-02 | 27 | 4417 | 4417/4417 | 4.4e-16 |
| گكيش | 2042 | 2013-10-19 | 2026-11-10 | 18 | 2042 | 2042/2042 | 6.7e-16 |

## ۸. به‌روزرسانی و Revision

`_audit/phase49-2/update_chain_proof.py` روی کپی ایزوله با رویداد واقعی تقسیم
تپسي (۲۰۲۶-۱۱-۱۰):

| مرحله | Revision | Factor پیش از رویداد | ردیف Adjusted |
| --- | --- | ---: | ---: |
| قبل از Capture رویداد | `2e8c2318…` | `1.0` | ۱۰۵٬۶۹۱ |
| پس از افزودن رویداد | `d638ef36…` | `0.149506158…` | ۱۰۵٬۶۹۲ |
| ساخت دوباره | همان `d638ef36…` | — | همان ۱۰۵٬۶۹۲ |

همهٔ بررسی‌ها `true`: تغییر Revision، تغییر جدول Factor، Factor=1 پیش از رویداد،
Factor اندازه‌گیری‌شده پس از رویداد، Factor=1 در روز رویداد، ایدمپوتنسی ساخت
دوباره، و پایداری Revision.

## ۹. تأیید Seed و گیت انتشار

- تأیید مالک در `docs/opportunity-center/phase49-2/OWNER-APPROVAL-REFERENCE-DERIVED.json`
  و بلوک `owner_approvals` در `FINAL-SEED-MANIFEST.json` ثبت شد.
- `python scripts/check_seed_release.py --db _audit/phase49-full-verification/seed/market.db`
  → `SEED_RELEASE_OK` با ذکر رکورد تأیید و تاریخ.
- ۱۴/۱۴ بررسی Integrity/Hash/Round-trip/تعداد در `seed-recheck.json` سبز؛
  تست ایدمپوتنسی `stage09` سبز.
- تست‌های محصول Seed: `_audit/phase49-2/evidence/seed-product-check.json` —
  باینری محصول فاز ۴.۹.۱ روی کپی مستقیم Seed تأییدشده بالا آمد و API چارت
  محلی برای ۸ نماد نمونه پاسخ داد؛ هر ۸ بررسی `true` (Integrity `ok`،
  ۵۴۴٬۲۸۴ ردیف، ۶٬۱۰۳ نماد، ۱۰۵٬۳۶۷ ردیف Reference-derived،
  پاسخ `success`، `candles>0`، `factors==candles`، منبع تعدیل حاضر).

جزئیات: `docs/opportunity-center/phase49-2/SEED-APPROVAL.md`.

## ۱۰. آزمون‌ها و CI

گیت‌های محلی (venv پروژه، هاست تک‌هسته‌ای؛ رکورد کامل در
`_audit/phase49-2/evidence/local-gates.json`):

| گیت | نتیجه |
| --- | --- |
| `go test ./internal/chart ./internal/candlebuild` | PASS (شامل تست‌های جدید) |
| `go test ./...` | PASS (exit 0؛ `internal/httpapi` 30.9s) |
| `go vet ./...` | PASS |
| `dev/version_anchor_guard.py` | PASS — 11 بررسی، 0 خطا |
| `dev/suite_registry_guard.py` | PASS — 260 suite |
| `scripts/test_check_seed_release.py` | PASS (+ edge cases) |
| `_audit/phase49-2/test_phase49_2.py` | PASS — 48/48 |
| `dev/run_all_tests.py --profile data` | PASS — 20 suite، 0 خطا، ۲ SKIP به‌خاطر fixture غایب |
| `dev/run_all_tests.py --profile production` | ۱۲ از ۱۳ suite + ۱ silent؛ فقط `dev/market_universe_v1.py` در سنجهٔ زمان ۴۰۵٫۵ms در برابر سقفِ تغییرنکردهٔ ۴۰۰ms شکست خورد؛ همان suite به‌تنهایی 17/17 PASS |

سنجهٔ زمانِ بالا تحتِ بارِ کاملِ profile روی این هاست تک‌هسته‌ای مرزی است؛ هیچ
آستانه یا assertion تغییر نکرد و CI مرجعِ نهایی است. مرحلهٔ stageE با استخراج
کندِ lzma روی این هاست عملی نشد؛ به‌جایش `seed_product_check.py` روی کپی
مستقیم Seed اجرا شد و ۸/۸ بررسی سبز بود (بخش ۹).

CI نهایی روی Commit `3dc7318a` اجرا و نتیجهٔ واقعی در
`docs/opportunity-center/phase49-2/CI-FINAL-RESULTS.json` ثبت شد:

| Workflow | Run | نتیجه |
| --- | --- | --- |
| `guards` | [43016492221](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/43016492221) | success — هر ۹ job (Go vet/test/race/windows، data integrity، zero-python، frontend، repo hygiene، desktop delivery/installer) |
| `python-tooling` | [43016492177](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/43016492177) | success — seed gate self-test + data profile |
| `python-legacy` | [43016492198](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/43016492198) | success (report-only) — job قدیمی پایتون به‌صورت طراحی‌شده failure گزارش می‌شود؛ static JS سبز |

وضعیت نهایی این گزارش `CI_COMPLETE` است؛ Commitهای بعدی فقط شاهد/مستندات را
تغییر می‌دهند و Commit معتبر CI همان `3dc7318a` می‌ماند.

## ۱۱. موانع واقعی باقی‌مانده

1. **پوشش بازار:** دفتر پوشش (تعریف معتبر صف) برای ۶٬۱۰۳ نماد این وضعیت‌ها را
   ثبت می‌کند: ۳٬۳۰۸ `QUEUE_NO_REFERENCE`، ۱٬۴۶۸ `QUEUE_NO_INSTRUMENTS`،
   ۶۷۵ `QUEUE_REFERENCE_ONLY`، ۴۳۱ `QUEUE_HALTED` و ۱۹۱ `QUEUE_UNMAPPED_ASSET_ID`.
   baseline پیش از این طبقه‌بندی ۵٬۳۴۴ نماد بدون پوشش مرجع و ۳۳۹ بدون Asset ID
   شمرده بود (تعریف متفاوت)؛ عدد معتبر صف همان دفتر پوشش است. هیچ‌کدام مانع تولید
   کندل برای ۳۰ نماد آماده نیست.
2. **نوع رویداد:** از ۱٬۰۲۷ رویداد، ۴۰۴ رویداد نسبتِ اندازه‌گیری‌شده دارند ولی
   نوعِ شرکتیِ رسمی ندارند؛ نوع حدس زده نشد.
3. **روز جاری:** کندل تاریخ Capture تا جلسۀ بعد قرنطینه است.
4. **۳۰۶ ردیف OHLC نامعتبر قدیمی** در نمادهای `legacy-unknown` همچنان در Seed
   باقی است؛ برای نمادهای Pilot با سری مرجع جایگزین شده، برای بقیه per-symbol
   علامت‌گذاری شده است.
5. **تصحیح نمایشی پک** برای نمادهای بدون Factor مرجع دست‌نخورده است؛
   ۱۶ گام محصولِ بی‌شاهد در آن‌ها هنوز اعمال می‌شود. گسترش DB مستقل به آن‌ها
   همان اصلاح را می‌آورد.
6. **تست UI زنده:** مسیر چارت با API و Go تست شد؛ اسکرین‌شات مرورگر در این
   مأموریت گرفته نشد.

## ۱۲. محدودیت‌های مأموریت

`main` تغییر نکرد، Merge/Tag/Release انجام نشد، دیتابیس Production تغییر نکرد،
FTS دست‌نخورده ماند، هیچ داده/ضریب حدس زده نشد، و هیچ ردیف Reference-derived
بدون تأیید ثبت‌شده منتشر نشد. DB مستقل روی کپیِ مجزا در `_audit/phase49-2/db/`
ساخته و با همان کپی آزموده شد؛ جایگزینی آن با DB عملیاتی/توزیع، به اجازهٔ
صریح مالک نیاز دارد.

---

## پیوست: فایل‌های شاهد

| فایل | محتوا |
| --- | --- |
| `_audit/phase49-2/evidence/baseline.json` | شمارش‌های شروع مأموریت |
| `_audit/phase49-2/rahavard/pilot-capture.json` | ۶۰ سری type0/type7 + Marks (دادهٔ خام مرجع؛ عمداً خارج از Git، SHA `6c8999ec…`) |
| `_audit/phase49-2/rahavard/pilot-analysis.json` | تغییرهای q و تطبیق با پک |
| `_audit/phase49-2/rahavard/engine-parity-before.json` | پاریتی موتور قدیم |
| `_audit/phase49-2/rahavard/engine-parity-after.json` | پاریتی موتور اصلاح‌شده |
| `_audit/phase49-2/ledgers/EVENT-PARITY.csv` | یک ردیف per-event قبل/بعد |
| `_audit/phase49-2/evidence/candle-ingest.json` | ورود داده، Factor، Revision |
| `_audit/phase49-2/evidence/update-chain-proof.json` | اثبات به‌روزرسانی |
| `_audit/phase49-2/ledgers/COVERAGE-STATUS.csv` | وضعیت ۶٬۱۰۳ نماد |
| `_audit/phase49-2/evidence/seed-recheck.json` | ۱۴ بررسی Seed |
| `_audit/phase49-2/evidence/candle-ingest-conflicts` | در DB: ۱۰٬۹۸۲ فیلد ناهمخوان با Seed که بازنویسی نشد |
