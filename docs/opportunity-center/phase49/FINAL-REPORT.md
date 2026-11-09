# Phase 4.9 — گزارش نهایی: بستن زنجیرهٔ تعدیل تاریخی و آمادگی Seed تمام‌تاریخ

- تاریخ: 2026-11-10
- شاخه: `mission/phase49-adjustment-chain-closure-2026-11-10`
- مبنای ایجاد شاخه: `9d348b6456ffd7af556e299df2de9b26b3b4ca22` (HEAD شاخهٔ Phase 4.8؛ `origin/main` در `9a919e82` و بدونِ تغییر ماند)
- حکم نهایی: **PHASE49_PARTIAL**
- دلیل حکم: زنجیرهٔ تعدیل برای ۳۰ نماد بسته و پاریتیِ Python↔Go اثبات شد؛ اما دقتِ نسبت‌های پیش از ۲۰۲۰ برای ۲۹ نماد مرجعِ مستقل ندارد و گیتِ ورود به Stage 5 برآورده نشد. Seed Candidate ساخته نشد.

## ۱) خلاصهٔ اجرایی

1. **ریشهٔ نقص پیدا شد:** بستهٔ `ra365-r32b-v2` برای ۳۰ نماد **صفر** گام پیش از ۲۰۲۰ دارد، ولی ۲۵۲ رویدادِ canonical محصول در ۲۰۱۰–۲۰۱۹ وجود دارد. حالت `authoritative` همهٔ ۵۳۴ رویدادِ canonical را Suppress می‌کند و فقط ۲۷۱ گامِ ۲۰۲۰+ می‌ماند ⇒ تاریخچهٔ تعدیل‌شده پیش از ۲۰۲۰ خالی می‌شود.
2. **روش A (Rebuild) و B (Overlay) هر دو ساختار را کامل می‌کنند:** ۸۳٬۴۰۳ تاریخِ مشترک، ۷۸٬۸۸۴ برابرِ دقیق و بیشینهٔ اختلاف ۶٫۹e-۱۸ (آخرین بیتِ double)؛ اختلاف از ادغام رویدادهای هم‌تاریخ در Rebuild می‌آید.
3. **یک نقصِ واقعیِ اعمالِ دوگانه پیدا و رفع شد:** شبهرن `2026-09-28` در برابر گامِ بسته `2026-09-29` با نسبتِ یکسان؛ Dedupِ شاهددار (±۳ روز، نسبت ≤۱٪) در Python و Go اضافه شد و شاهد در `adjustRejected.dedupe` ثبت می‌شود.
4. **شکافِ Python/Go رفع شد:** `ApplyRawCandles` در Go صفر caller داشت؛ مسیر `/api/chart-db` گامِ literal H/L + تصحیح فیلد خام را اجرا نمی‌کرد. اکنون اجرا می‌شود و با fixture مشترک + پاریتیِ ۳۰-نمادی قفل شده است. یک ناسازگاریِ فقط-گزارشیِ `capability` (نبود `ins_code`) هم رفع شد.
5. **انتشار Seed همچنان BLOCKED است:** ساختار و پاریتی اثبات شد، اما دقتِ پیش از ۲۰۲۰ برای ۲۹ نماد مرجعِ مستقل ندارد و باقی‌ماندهٔ ۴٫۳٪ در فولاد هم با مرجع بسته نشده است. تاریخچهٔ خام به‌عنوان «تعدیل‌شده» منتشر نشد.

## ۲) انطباق با قیودِ ثابت

| قید | وضعیت | شاهد |
| --- | --- | --- |
| `main` تغییر نکرد | PASS | `origin/main` = `9a919e82` پیش و پس از کار؛ هیچ commit روی main |
| Merge / Tag / Release نشد | PASS | فقط commit روی شاخهٔ مأموریت |
| Visibility گیت‌هاب تغییر نکرد | PASS | هیچ تنظیم مخزنی تغییر نکرد |
| شاخهٔ Phase 4.8 و سه آرشیو DB حفظ شد | PASS | `mission/phase48-closeout-2026-11-09` روی origin = `9d348b64`؛ آرشیوها با SHA بازبینی شدند |
| DBهای اصلی/آرشیوها حذف یا بازنویسی نشدند | PASS | فقط روی کپی‌های `_audit/phase49/continuation/db/` و `api/` کار شد |
| آزمایش‌های DB فقط روی کپی مستقل | PASS | `restored-source/verify/work.db` (کپی‌های LZMA) و `api/python/market.db` |
| دادهٔ عملیاتی، نصب واقعی و Registry دست‌نخورده | PASS | هیچ DB نصب/عملیاتی باز نشد؛ بستهٔ Seed ساخته نشد |
| Credential/Token/Private Key در گیت نبود | PASS | توکنِ محلی فقط از فایل runtime خوانده شد و در هیچ artifact نوشته نشد |
| قواعد FTS، `/fts-screen` و `approval_enabled=false` دست‌نخورده | PASS | هیچ تغییر FTS/تنظیمات |
| Q1 همچنان Deferred؛ رتبه‌بندی Lexicographic؛ بدون Composite/Weight جدید | PASS | هیچ تغییر الگوریتمی خارج از تعدیل |
| Phase 5 / research اندیکاتور / بازطراحی فرانت / AutoTrader / سرخطی | PASS (وارد نشد) | خارج از دامنه |
| اگر روشی اثبات نشد، BLOCKED بماند | PASS | Seed ساخته نشد؛ دقت پیش از ۲۰۲۰ INSUFFICIENT_DATA |

## ۳) Stage 0 — ممیزی فقط-خواندنی

- محیط: Windows 10.0.19045 (Git Bash)، Go 1.26، Python 3.12.10 (venv workspace)، Node 24.22.1.
- `tools/phase48/continuation/verify_artifacts.py`: **۳۵ artifact متعهد OK، ۰ mismatch، ۱۴ artifact محلی غایب** (از جمله `_audit/phase48/parity/ref/bars.ndjson.gz` که مرجعِ type0/type7 است).
- سه آرشیو LZMA به مسیرهای جدید بازیابی و SHA آرشیو و SHA خام تأیید شد:

| آرشیو | SHA-256 آرشیو | SHA-256 خام | اندازهٔ خام |
| --- | --- | --- | ---: |
| `phase48-source-market.db.lzma` | `42cd1567da50bd4c507b0f8503d015ba44b9005b1bd8ecd077a28b03cb1eb93f` | `bb57564b2671162238f5760641e05dd5fd0fe0e44501383fb8c2f96a26efb8ca` | ۲۶۷٬۴۷۲٬۸۹۶ |
| `phase48-backfill-work-market.db.lzma` | `db214908de84f25778a7d7cabfe44bf17c37c302a79a0627526f57ef378bafca` | `2b701ea3d32dcb30c5c0bc248cd160b1aa5bc5f38598a71e6b056c355e1ed3b5` | ۲۹۴٬۷۹۳٬۲۱۶ |
| `phase48-backfill-verify-market.db.lzma` | `db214908de84f25778a7d7cabfe44bf17c37c302a79a0627526f57ef378bafca` | `2b701ea3d32dcb30c5c0bc248cd160b1aa5bc5f38598a71e6b056c355e1ed3b5` | ۲۹۴٬۷۹۳٬۲۱۶ |

- `integrity_check=ok`، `journal_mode=wal`، ۴۳ جدول؛ گزارش کامل: `_audit/phase49/continuation/stage0-restore-report.json` و `docs/opportunity-center/phase49/STAGE0-AUDIT.md`.
- محدودیت ثبت‌شده: مرجعِ مستقلِ ۳۰ نماد (`bars.ndjson.gz`) و چند artifact نصب محلی موجود نیست؛ هیچ دادهٔ جایگزین ساخته نشد.

## ۴) Stage 1 — بازتولید Baseline (PASS)

اجرا: `_audit/phase49/continuation/stage1_reproduce.py` روی کپی‌های مستقل؛ خروجی `evidence/stage1-reproduction.json`.

| سنجه | Phase 4.8 | بازتولید 4.9 | وضعیت |
| --- | ---: | ---: | --- |
| Product Events (`adjust_events`) | ۶۵۲ | ۶۵۲ | REPRODUCED |
| گام‌های Pack (`replace_step`) | ۲۷۱ | ۲۷۱ | REPRODUCED |
| ردیف‌های دفتر رسمی | ۲۸۴ | ۲۸۴ | REPRODUCED |
| ردیف‌های جدید Backfill | ۷۲٬۲۲۲ | ۷۲٬۲۲۲ | REPRODUCED |
| تغییر ردیف موجود | ۰ | ۰ از ۴۳۸٬۹۱۷ | REPRODUCED |
| ردیف ۳۰ نماد (source → work) | — | ۱۲٬۰۸۶ → ۸۴٬۳۰۸ | MEASURED |
| Reference Steps (۵۰۱) / Product منطبق (۴۴۳) / OHLC دقیق پیش از ۲۰۲۴ (۶٬۴۷۲ از ۱۱٬۱۲۱) | ثبت‌شده | — | NOT_MEASURED (مرجع غایب؛ CITED_ONLY) |

## ۵) Stage 2 — ریشه‌یابی سطح رویداد (PASS)

جزئیات کامل در `docs/opportunity-center/phase49/CHAIN-ANALYSIS.md` §۳ و جدول رویدادبه‌رویداد `EVENT-MAPPING-30.csv` (۵۶۳ ردیف).

| سنجه (۳۰ نماد) | پیش از ۲۰۲۰ | ۲۰۲۰+ | جمع |
| --- | ---: | ---: | ---: |
| گام `replace_step` بسته | **۰** | ۲۷۱ | ۲۷۱ |
| گام `suppress_step` بسته | ۰ | ۶ | ۶ |
| رویداد canonical محصول | **۲۵۲** | ۲۸۲ | ۵۳۴ |
| گام زنجیرهٔ authoritative | **۰** | ۲۷۱ | ۲۷۱ |
| گام زنجیرهٔ Overlay/Rebuild | ۲۵۲ | ۲۷۷+ | ۵۲۹+ |

- حالت authoritative برای نماد پوشش‌داده‌شده همهٔ رویدادهای ≤ `as_of` را Suppress می‌کند (۵۳۴ رویداد) و رویدادهای بعد از `as_of` را نگه می‌دارد.
- در ۳۰ نماد، هیچ رویداد near-date با نسبت سازگار نبود؛ Dedupِ دقیق‌تاریخ کافی بود. در مجموعهٔ ۴۷ نمادی **یک** مورد (شبهرن) پیدا شد که با شاهد رفع شد.
- فولاد تمام‌تاریخ: authoritative ۱۲ گام در برابر ۲۶ گام مرجع؛ خطای میانهٔ ضریب **۹۸٫۷٪** و بیشینه **۱۶۳۳٪**. Overlay/Rebuild: ۲۶/۲۶ تاریخ، میانه **۰٫۳۷٪**، بیشینه **۴٫۳٪**، صفر ردیف >۵٪.
- پاسخ پرسش‌های Stage 2 (کدام رویدادها، تکراری‌ها، کفایت Product، دادهٔ تکمیلی، Anchor/Offset) در CHAIN-ANALYSIS §۳-۵ ثبت شده است.

## ۶) Stage 3 — مقایسهٔ روش A و B (PASS)

- **A — Full Correction Pack Rebuild:** بستهٔ `ra365-phase49-rebuild-v1` با ۶۶۱ گام در ۴۷ نماد (۴۲۳ از بسته + ۲۳۸ از محصول)، حالت authoritative، بدون Suppress زمان اجرا. SHA فایل‌ها: `1fbce9eb…` (factors) و `834c6e7f…` (raw_ohlc).
- **B — Controlled Product Overlay:** بستهٔ فعلی + نگه‌داشتن رویدادهای Product بیرون از تاریخ‌های بسته + Dedupِ near-date با شاهد.
- نتیجه: روی ۳۰ نماد، زنجیرهٔ ضریب ۸۳٬۴۰۳ تاریخ مشترک؛ ۷۸٬۸۸۴ برابرِ دقیق؛ بیشینهٔ اختلاف ۶٫۹e-۱۸ مطلق / ۴٫۶e-۱۶ نسبی؛ صفر تاریخ با اختلاف >1e-15. اختلافِ باقی‌مانده از ادغام چند رویداد هم‌تاریخ در Rebuild است، نه از فرمول.
- **روش انتخاب‌شده برای معماری نهایی: A (Rebuild)** — یک منبع حقیقتِ immutable و قابل ممیزی، حذف Suppress از مسیر داغ، بازتولیدپذیری و رفتار یکسان Python/Go. **B** فقط برای دورهٔ گذار/مقایسه توصیه می‌شود. انتخاب نهاییِ معماری از اختیارِ مالک است (بند ۱۱).
- جدول کامل معیارها و نقاط قوت/ضعف: CHAIN-ANALYSIS §۴.

## ۷) Stage 4 — پاریتی Python/Go (PASS)

### ۷-۱) اصلاح‌ها

1. Go: تابع `literalDisplayCandles` (کپی نمایشی، `high=high_raw`/`low=low_raw`، سپس `ApplyRawCandles`) و فراخوانی آن در `ChartDB` بعد از `chartDBBody` — دقیقاً همان ترتیب `_literal_display_candles` پایتون (`api/chart.py:2743` و `:3575`).
2. Go: `nearPackReplace` + Dedupِ overlay با ثبت شاهد `dedupe` در `adjustRejected`.
3. Go: بازآراییِ `LoadPack` به `loadPackFromDir` برای تست‌پذیریِ fixture (بدون تغییرِ رفتار).
4. Python: همان Dedup در `adjustment_corrections.apply_factor_events` با `NEAR_DEDUPE_DAYS=3` و `NEAR_DEDUPE_RATIO_TOL=0.01`.
5. Python: `_adjust_capability` اکنون `ins_code` را resolve می‌کند تا گزارشِ `covered/replace_steps/raw_fields` با زنجیرهٔ واقعی هم‌خوان باشد (اصلاح فقط-گزارشی).

هیچ فرمول، ترتیب زنجیره، تلورانس یا assertion برای سبز شدن تست تغییر نکرد.

### ۷-۲) شواهد پاریتی

| سنجه | نتیجه |
| --- | --- |
| `dev/test_phase49_correction_parity_v1.py` | **۷۶/۷۶ PASS** |
| `backend-go/internal/chart/phase49_parity_test.go` | **PASS** |
| `test_ra365_round32b_correction_pack_v1.py` | ۱۴/۱۴ PASS |
| `test_ra365_round32c_corrections_fixes_v1.py` | ۱۲/۱۲ PASS |
| ۳۰ نماد، Overlay: Python در برابر Go | **۳۰/۳۰ PASS** (factors ۸۳٬۴۰۳ تاریخ، events/rejected/capability یکسان) |
| ۳۰ نماد، Rebuild: Python در برابر Go | **۳۰/۳۰ PASS** |
| `/api/chart-db/فولاد` (۳٬۶۸۹ کندل) | OHLC/closing/volume/raw/factors/events/rejected/capability کامل یکسان |
| `/api/chart-db/وسكاب` (۴۲۸ کندل) | کامل یکسان |

شاهد زندهٔ اصلاحِ raw display: `/api/chart-db/وسكاب` برای `2025-01-22` پس از اصلاح `open=2170, high=2171, low=2168, close=2171` می‌دهد؛ DB خام `2168/2171/2124/2124` است.

**سازگاریِ CI (EOL):** SHA-256های بستهٔ fixture روی بایت‌های LF محاسبه شده‌اند (همان بایت‌های checkout لینوکس/CI)؛ نسخه‌های کاریِ CRLF ویندوز پیش از محاسبه به LF نرمال شدند. بدون این کار، loaderِ Go/Python در CI بسته را به‌خاطرِ SHA رد می‌کرد. تست‌ها پس از نرمال‌سازی دوباره اجرا شدند: Python ۷۶/۷۶ و Go PASS.

## ۸) Stage 5 — یکپارچه‌سازی و Seed (وارد نشد / BLOCKED)

شرط ورود (اثباتِ زنجیره + پاریتی برای ۳۰ نماد با مرجعِ مستقل) برآورده نشد:

| مورد | وضعیت | دلیل |
| --- | --- | --- |
| Seed Candidate آزمایشی | **BLOCKED** | دقتِ پیش از ۲۰۲۰ برای ۲۹ نماد مرجع مستقل ندارد؛ ۴٫۳٪ باقی‌مانده در فولاد هم بسته نشده |
| Provenance / نگه‌داشتن جدول‌های وضعیت فعلی | NOT_ENTERED | پیش‌نیاز Seed |
| Seed Merge / Idempotency | NOT_MEASURED | بستهٔ Seed ساخته نشد |
| Upgrade با دادهٔ کاربر | NOT_MEASURED / BLOCKED | عمداً اجرا نشد؛ DB نصب واقعی دست‌نخورده |
| API تاریخچه/MA برای ۳۰ نماد | **PASS (محلی)** | ۳۰/۳۰ `status=ok`؛ آخرین داده ۲۰۲۶-۱۱-۰۹؛ MA طبق قرارداد تا سقف ۲۰۰۰ روز (`clampMaDays`) |
| Weekly/Monthly برای ۳۰ نماد | **PASS (محلی)** | FTS ۳۰/۳۰ success؛ `weekly` ۳۰ و `monthly` ۳۰ |
| FTS تمام‌تاریخ | **PASS (فولاد)** | `status=success`، ۳٬۶۸۹ بار |

شاهد: `evidence/api-ma-full-history.json`، `evidence/api-go-fts-30.json`، `evidence/api-go-fts-foulad.json`.

## ۹) Stage 6 — گیت‌های پذیرش

| گیت | وضعیت | شاهد/یادداشت |
| --- | --- | --- |
| بازبینیِ artifactهای Phase 4.8 | **PASS** | ۳۵ OK، ۰ mismatch، ۱۴ محلی غایب |
| بازیابی ایزوله + SHA + integrity | **PASS** | `stage0-restore-report.json` |
| بازتولید Baseline | **PASS** | `stage1-reproduction.json` |
| ریشه‌یابی سطح رویداد | **PASS** | CHAIN-ANALYSIS §۳ + `EVENT-MAPPING-30.csv` |
| مقایسهٔ A/B | **PASS** | `ab-chain-bit-identity.json` |
| پاریتی خام ۳۰ نماد با مرجع | **NOT_MEASURED / INSUFFICIENT_DATA** | مرجع `bars.ndjson.gz` غایب؛ بدون جایگزین |
| پاریتی تعدیل‌شده ۳۰ نماد با مرجع | **NOT_MEASURED / INSUFFICIENT_DATA** | همان؛ پاریتیِ زنجیره به‌تفکیک اندازه‌گیری شد |
| پاریتی خام فولاد تمام‌تاریخ | **PASS** (با آنومالی‌های جدا) | ۰ ردیف >۵٪؛ بیشینه ۲٫۹۲٪ |
| پاریتی تعدیل‌شده فولاد | **PASS ساختاری / INSUFFICIENT_DATA دقت** | ۲۶/۲۶ گام؛ بیشینه خطا ۴٫۳٪ |
| پنجرهٔ مرجع ۲۰۲۴+ | **PASS** | ۱۰۱/۱۰۲ دقیق؛ ۱۱۵/۱۲۷ ≤۵٪ پس از ۳ روز؛ ۷ outlier در همهٔ حالت‌ها |
| پاریتی Python↔Go (fixture + E2E) | **PASS** | ۷۶/۷۶؛ ۳۰/۳۰ + ۳۰/۳۰؛ دو نماد کندل‌به‌کندل |
| `go test ./...` | **PASS** | ۵۳ پکیج OK، `GO_TEST_RC=0` |
| `go vet ./...` | **PASS** | `GO_VET_RC=0` |
| Race detector | **NOT_MEASURED** | `CGO_ENABLED=0` و `gcc` محلی موجود نیست |
| مجموعهٔ کامل تست پایتون (`dev/run_all_tests.py`) | **FAIL (ازپیش‌موجود/محیطی)** | ۱۸۳ سوئیت؛ شکست‌ها مستقل از تغییرات: `chart API guard` به‌خاطر نبود `frontend/node_modules`، دو سوئیت Node به‌خاطر نبود `node`، و شکست‌های وابسته به DB کوچک/فیکسچر. مقایسهٔ Base: B1 در هر دو ۶/۶ PASS؛ B3 در هر دو ۴۹ PASS / ۱ FAIL با همان diff؛ B2 در هر دو ۲ FAIL یکسان. سوئیت Phase 4.9 در همین اجرا ثبت شده و مستقل ۷۶/۷۶ PASS است. Protected DB با اثرانگشت `04137b38…` قبل/بعد یکسان (`PROTECTED_DB_UNCHANGED`).
| Frontend / Rust | N/A | هیچ فایل فرانت/راست تغییر نکرد |
| Seed Build / Merge / Install / Upgrade | **BLOCKED / NOT_MEASURED** | Stage 5 وارد نشد |
| API تاریخچه/MA/هفتگی/ماهانه/FTS | **PASS (محلی)** | ۳۰/۳۰ + ۳۰/۳۰ |

## ۱۰) تحویل‌شدنی‌های ۱۲گانه

| # | تحویل‌شدنی | مسیر/وضعیت |
| --- | --- | --- |
| ۱ | گزارش ریشه‌یابی | `CHAIN-ANALYSIS.md` §۳ + این گزارش §۵ |
| ۲ | نقشهٔ کامل رویدادهای ۳۰ نماد | `EVENT-MAPPING-30.csv` (۵۶۳ ردیف) |
| ۳ | مقایسهٔ Rebuild در برابر Overlay | `CHAIN-ANALYSIS.md` §۴ + `evidence/ab-chain-bit-identity.json` |
| ۴ | روش انتخاب‌شده + استدلال | این گزارش §۶ (A؛ تأیید مالک لازم است) |
| ۵ | اصلاح پاریتی Go/Python + تست رگرسیون | این گزارش §۷ + `dev/test_phase49_correction_parity_v1.py` + `backend-go/internal/chart/phase49_parity_test.go` |
| ۶ | Seed Candidate | ساخته نشد — **BLOCKED** (این گزارش §۸) |
| ۷ | گزارش جداگانهٔ پاریتی خام و تعدیل‌شده | `RAW-PARITY.md` و `ADJUSTED-PARITY.md` |
| ۸ | گزارش نصب/ارتقا | اجرا نشد — **NOT_MEASURED/BLOCKED** |
| ۹ | دستورات بازتولید | این گزارش §۱۱ |
| ۱۰ | SHA-256 همهٔ artifactها/DBهای تست | `ARTIFACTS-SHA256.txt` |
| ۱۱ | گزارش نهایی با وضعیت‌های دقیق | همین فایل |
| ۱۲ | فهرست تصمیم‌های مالک | این گزارش §۱۲ |

## ۱۱) دستورات بازتولید

```bash
# 0) بازبینی artifactها و بازیابی DBها (فقط-خواندنی روی آرشیوها)
python tools/phase48/continuation/verify_artifacts.py
python _audit/phase49/continuation/restore_and_check.py

# 1) بازتولید Stage 1
python _audit/phase49/continuation/stage1_reproduce.py

# 2) سرویس Go روی DB بازیابی‌شده (برای هر حالت، پروسهٔ تازه با BORS_CORRECTIONS_DIR متفاوت)
cd backend-go && GOPROXY=https://goproxy.cn,direct go build -o ../_audit/phase49/continuation/borsd_phase49.exe ./cmd/borsd && cd ..
TOKEN_DIR=_audit/phase49/continuation/api/sandbox
BORS_CORRECTIONS_DIR="$PWD/data/ra365_corrections/ra365-r32b-v2" \
  ./_audit/phase49/continuation/borsd_phase49.exe --port 8159 \
  --db-dir $TOKEN_DIR --no-shell --no-loops --server-only

# 3) شواهد زنجیره/رویداد
python _audit/phase49/continuation/event_mapping.py
python _audit/phase49/continuation/validate_chains.py \
  --labels authoritative-base,overlay-dedup,rebuild-v1,no-corrections
python _audit/phase49/continuation/foulad_full.py

# 4) پاریتی Python↔Go
python dev/test_phase49_correction_parity_v1.py
cd backend-go && go test ./internal/chart -run TestPhase49ParityFixture -v && cd ..
python _audit/phase49/continuation/api/python_chartdb_e2e.py
python _audit/phase49/continuation/api/python_vs_go_diff.py
python _audit/phase49/continuation/api/python_go_30_parity.py --pack "$PWD/_audit/phase49/continuation/packs/overlay" --evidence api-overlay-dedup --label overlay
python _audit/phase49/continuation/api/python_go_30_parity.py --pack "$PWD/_audit/phase49/continuation/packs/rebuild-v1" --evidence api-rebuild-v1 --label rebuild

# 5) FTS/MA ۳۰ نماد
python _audit/phase49/continuation/api/fetch_fts30.py

# 6) گیت‌ها
cd backend-go && GOPROXY=https://goproxy.cn,direct go test ./... && go vet ./... && cd ..
python dev/run_all_tests.py
```

## ۱۲) تصمیم‌های مالک (خارج از اختیار این مأموریت)

1. **انتخاب معماری نهایی:** Rebuild (A) یا Overlay (B)؟ پیشنهادِ مهندسی: A.
2. **سیاست دقت پیش از ۲۰۲۰:** تأمین بستهٔ مرجع type0/type7 برای ۲۰۱۰–۲۰۱۹؛ یا پذیرش صریح ±۵٪ با برچسب «نسبت کشف‌شده»؛ یا محدودکردن Seed تعدیل‌شده به ۲۰۲۰+.
3. **مجوز ساخت/انتشار Seed تمام‌تاریخ:** فقط پس از رفع بند ۲.
4. **۷ ردیف >۵٪ در پنجرهٔ ۲۰۲۴+** (شنفت، فافق، فخاس، فولاژ، لخزر، ولانا، مارون): بررسی هویت/نسخهٔ نماد یا منبع مرجع.
5. **۹ نماد با مبنای Open قدیمی و ۷۲۹ ردیف `open=prev close`:** آیا اصلاحِ خام لازم است یا آنومالیِ دادهٔ منبع پذیرفته می‌شود؟

## ۱۳) محدودیت‌ها و ریسک‌های باقی‌مانده

- مرجعِ مستقل type0/type7 برای ۳۰ نماد روی این ماشین نیست؛ سنجه‌های خام/تعدیل‌شدهٔ ۳۰ نماد NOT_MEASURED است و هیچ ادعای پاریتی برای آن‌ها ثبت نمی‌شود.
- دقتِ نسبت‌های کشف‌شده پیش از ۲۰۲۰ (حداکثر ۴٫۳٪ در فولاد) برای انتشار به‌عنوان «تعدیل‌شدهٔ معتبر» کافی نیست.
- Race detector محلی اجرا نشد (نبود CGO/gcc)؛ باید در CI یا محیط دارای toolchain اندازه‌گیری شود.
- بستهٔ Rebuild فعلی برای ۴۷ نماد آزمایشی است، نه همهٔ نمادهای پوشش‌داده‌شده؛ سیاست نسخه‌گذاری/امضا هم هنوز تصویب نشده است.
- یک اجرای مستقیمِ تستِ `dev/test_adjustment_phasea.py` خارج از Gate Isolation، دو جدولِ **خالی** `adjust_events`/`adjust_verdict` به `market.db`ِ ریشه (seed تعهدشده) افزود. اثرِ منطقی صفر ردیف بود (اثر انگشتِ منطقی: فقط همان دو جدولِ صفر‌ردیفه)، فایل به HEAD بازگردانده شد و هیچ DB نصب/عملیاتی درگیر نشد. از این پس تست‌ها فقط با `BORS_DB` ایزوله اجرا می‌شوند.

## ۱۴) CI

CI پس از push روی همین شاخه بررسی و نتیجهٔ اجرای Actions در commit بعدیِ همین گزارش ثبت می‌شود؛ هیچ Merge/Tag/Release انجام نمی‌شود.
