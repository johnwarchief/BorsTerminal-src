# خطِ دریافت خودکار کدال — قرارداد، وضعیت و مرزهای عملیاتی

تاریخ: ۱۴۰۵-۰۷-۲۷ (۲۰۲۶-۱۰-۱۴) · branch: `mission/4-axes-2026-10-10`
مأموریت: «Fundamental Auto-Update Pipeline» — دریافت خودکار کدال، کشف نماد جدید،
پردازش افزایشی، و تازه‌سازی بنیادی بی‌وابستگی به ایجنت.

این فایل همانِ جاریِ همان مأموریت است: قراردادِ حالت، آنچه ساخته شده، آنچه با
عدد سنجیده شده، و مرزهایِ اجرایِ عملیاتی. بخش‌های ۷ تا ۱۲ (محاسبۀ افزایشی،
cache/UI، مشاهده‌پذیری، آزمونِ سرتاسری، گیت‌ها، تحویل) پس از بسته‌شدن به همین
فایل افزوده می‌شوند — چیزی که درِ این فایل نوشته نشده «انجام شده» نیست.

---

## ۰) قراردادِ واحدِ خط (Stage 1)

```
Source (Codal/TSETMC)
  → Discovery        (حرف‌هایِ تازه + ابزارهایِ تازه)
  → Raw Notice       (codal_notices، بی‌لمسِ ستون‌هایِ ثبت‌شده)
  → Identity         (symbol_identity + طبقۀ mstat_engine)
  → Extraction       (codal_fetcher.scrape_notice_row)
  → Validation       (codal_periods / codal_units / row_conflicts)
  → Canonical Record (financial_statements / monthly_sales + codal_extracted)
  → Fundamental Recalculation (پنج شاخص، فقط نمادهایِ علامت‌خورده)
  → Cache/API        (screener / funnel / card)
  → UI               (کارت بنیادی، قیف FTS، غربالگری، پنل سلامت)
```

حالت‌هایِ هر کار (رویِ همان سطرِ `codal_extracted`، نه جدولِ موازی):

| حالت | معنا | پایان‌یافته؟ |
| --- | --- | --- |
| `queued` | کشف شده، در صف است | نه |
| `running` | یکِ worker آن را claim کرده | نه |
| `done` | ردیفِ canonical نوشته شد | بله (`ok=1`) |
| `empty` | گزارش باز شد و عددِ قابل‌استخراج نداشت | بله (`ok=0`) |
| `failed` | خطای شبکه/استخراج، بودجۀ تلاش باقی است | نه |
| `unresolved` | بودجۀ تلاش تمام شد؛ علت درِ رکورد است | بله، ولی «موفق» نیست |

`error_kind` علت را از هم جدا نگه می‌دارد: `network` (خطای منبع)، `extract`
(پارس/ساختار)، `missing_input` (ورودیِ ضروری غایب)، `identity` (هویت نامطمئن).
تنها تعریفِ «این اطلاعیه تمام شد» `codal_fetcher.ledger_terminal_sql()` است؛
`derived_state`، `pending_notices`، صف و گاردها همه همان را می‌خوانند.

جدول‌هایِ افزودنی (همه `IF NOT EXISTS`، مهاجرتِ PRAGMA-gated):
`pipeline_cursor` (checkpoint) · `pipeline_runs` (گزارشِ هر چرخه) ·
`pipeline_dirty` (نماد × شاخصِ منتظرِ محاسبه) · `pipeline_lock` (قفلِ worker با
heartbeat) · `pipeline_instrument` (دفترِ عضویتِ ابزار).

---

## ۱) کشفِ خودکارِ اطلاعیه (Stage 2)

**مشکلِ پیشین:** پنجرۀ increment از `MAX(publish_date)`ِ خودِ داده می‌آمد؛ SQLite
رشته‌ها را لغت‌شناختی مقایسه می‌کند و نیمی از سطرهایِ بانک تاریخِ فارسی دارند،
پنجره می‌افتاد رویِ یکِ تاریخِ قدیمی و روزهایِ دیدۀ‌قبل دوباره خوانده می‌شدند —
و اطلاعیه‌ای که استخراجش شکست می‌خورد از پنجرۀ بعدی بیرون می‌افتاد.

**حالا:** نشانک، شناسۀ منبع است، نه تاریخ:
`pipeline_cursor['notice_scan_tn_cat<1|3>']` = کوچک‌ترین `tracing_no` رویِ آخرین
صفحۀ **کامل‌خوانده‌شده** (`CF.discover_notices` → `PL.discover_auto`).

| بندِ مأموریت | رفتارِ پیاده‌سازی‌شده | گواه |
| --- | --- | --- |
| ۲-۱ مسیرِ موجود تکمیل شود | `feed_sync` و کشفِ صفی از یکِ `feed_query` و یکِ `letter_to_notice` می‌گذرند | ۴ بررسیِ «یکِ منبعِ حقیقت» |
| ۲-۲ checkpoint پایدار | `pipeline_cursor` با `previous` و `updated_at` و `note` | ۲ بررسی |
| ۲-۳ بی‌تکیه بر `MAX(publish_date)` | دریبِ کشف `newest_publish_date` نمی‌خواند؛ canonical با `CP.pub_date_only` | ۲ بررسی (بدنه، بی‌docstring) |
| ۲-۴ دیررس/اصلاحیه | نشانک بر شناسه؛ اصلاحیه شناسۀ خودش را نگه می‌دارد و نشانه‌اش را `fts_engine._is_amendment` می‌شناسد | ۳ بررسی |
| ۲-۵ افزایشی | چرخۀ پایدار ≤ ۲ صفحه به‌ازایِ دسته | شمارشِ درخواست‌ها |
| ۲-۶ شناسه + نسخه | `tracing_no`، `letter_code`، `url`، `pdf_url`/`excel_url`ِ مطلق | ۲ بررسی |
| ۲-۷ انتشار ≠ دوره | ستونِ اطلاعیه فقط تاریخِ انتشار؛ دوره از `CP.derive` درِ لایۀ استخراج | ۳ بررسی |
| ۲-۸ دریافتِ مجدد بی‌تکراری | `INSERT ... ON CONFLICT DO NOTHING` رویِ کار + UPSERTِ نام‌ستونِ ردیفِ مالی | ۴ بررسی |
| ۲-۹ ناقص ⇒ ثبت + retry | رکوردِ بی‌تاریخِ انتشار ثبت می‌شود (تاریخ ساخته نمی‌شود) و درِ `pending_notices` می‌ماند | ۲ بررسی |
| ۲-۱۰ خطای منبع ⇒ نشانک ثابت | `blocked`/`complete=False` ⇒ هیچ `floors` نوشته نمی‌شود | ۴ بررسی + دامِ سنسور |

گارد: `dev/codal_discovery_v1101.py` — **۴۵ بررسی، ۰ شکست** (exit ۰)، بی‌شبکه
(فیدِ تزریقی)، بی‌`market.db`.

---

## ۲) کشفِ خودکارِ ابزار (Stage 3)

`PL.discover_instruments` Universe را از خودِ بانک می‌خواند (`instruments` +
حضور در `market_watch` + `instrument_state.c_etaval_title`) و با دفترِ
`pipeline_instrument` مقایسه می‌کند. پنج حالت جدا می‌مانند:

| رویداد | شرط | نتیجه |
| --- | --- | --- |
| `new` | `ins_code` درِ دفتر نبود | سطرِ تازه با `first_seen_at` |
| `renamed` | همان `ins_code`، نامِ متفاوت | `prev_name` می‌ماند، ابزارِ تازه **نمی‌شود** |
| `symbol_changed` | همان `ins_code`، نمادِ متفاوت | پرچم جدا |
| `id_changed` | یکِ نماد → بیش از یکِ `ins_code` | `identity='ambiguous'`، بی‌ادغامِ خودکار |
| `deactivated` | درِ `instruments` هست، درِ تابلو نیست | `membership='present'` + پرچم |
| `absent` → `removed` | دو چرخۀ پی‌درپی غیبت | `membership='removed'`، سطر پاک نمی‌شود |

* طبقه از `mstat_engine.classify` می‌آید: `stock` مشمولِ پنج شاخص، `fund` /
  `right` / `other` ⇒ `not_eligible`. هیچِ صندوقی مثلِ شرکتِ عملیاتی رفتار نمی‌کند.
* هویت فقط با کلیدِ `symbol_identity` (و گیتِ ISIN برایِ پسوندها)؛ نه حذفِ رقمِ
  انتهایی، نه شباهتِ نام، رأیِ اتصالِ خودکار نمی‌سازد.
* پوشش: `fs+ms` / `fs` / `ms` / `none` / `unknown`؛ ابزارِ بی‌داده هیچ ردیفِ
  مالیِ ساختگی نمی‌گیرد و درِ سلامت به‌صورت `no_fundamental` شمرده می‌شود.
* نبودِ ستون ⇒ NULL (با گزینشِ PRAGMA)، نبودِ `market_watch` ⇒ «سنسور نیست» —
  صفرِ ادعا از صفرِ مدرک.

**سرشماریِ واقعی رویِ کپیِ ایزولۀ `market.db` (۱۴۰۵-۰۷-۲۷، فقط رویِ کپی):**

```
instr_scanned   5992      class: other 3609 / stock 1722 / fund 621 / right 40
identity  linked 1592 · not_eligible 4270 · no_publisher 126 · ambiguous 4
coverage  fs+ms 1489 · ms 74 · fs 33 · none 126 · unknown 4270
چرخۀ دوم: instr_new=0, instr_renamed=0, instr_removed=0 (یدم‌پذیر در مقیاسِ واقعی)
```

سه نمادِ دارایِ دو `ins_code` درِ بانکِ امروز: `آواپارس`، `حيان072`، `كيمازي` —
همان‌ها که فازی‌مچ نباید وصلشان کند؛ دو تایِ اول درِ دفتر `ambiguous` ثبت شدند
(سوم غیرمشمولِ طبقه بود).

**کارایی:** پاسِ Universe أول ۷۷ ثانیه طول می‌کشید؛ علت اندازه‌گیری‌شده این بود
که `symbol_identity` با هر نوشتنِ همین اتصال کشش را می‌اندازد (۱۰۰ جستارِ هویت
بی‌نوشتن ۰٫۰۸s، با یکِ نوشتنِ میانِ هر جستار ۴٫۲۹s). هویت/پوشش حالا **پیش از**
اولین نوشتن محاسبه می‌شود و شمارشِ پوشش از دو `GROUP BY` می‌آید:
**۷۷٫۰s → ۳٫۷s** رویِ همان ۵٬۹۹۲ ابزار.

گارد: `dev/codal_instrument_discovery_v1102.py` — **۳۹ بررسی، ۰ شکست** (exit ۰).

---

## ۳) زمان‌بندی مستقل از رابط و بازیابی (Stage 6)

`app.py` درِ هوکِ استارت (کنارِ حلقه‌هایِ تابلو) یکِ رشتۀ daemon می‌سازد:
`codal_pipeline.start_worker(DB_PATH, owner="app-<pid>")`. تبِ بنیادی نقشی درِ
شروعِ دریافت ندارد؛ فراخوانیِ دومِ استارت رشتۀ دوم نمی‌سازد
(`reason="already-running"`).

**چراغِ بیدارباش از خودِ وضعیت است** (`PL.next_wakeup`)، نه تایمرِ ثابت:

| علتِ بیدارباش | شرط |
| --- | --- |
| `retry-at` | یکِ کارِ `failed` وقتِ تلاشِ دوباره دارد (`next_attempt_at`) |
| `backlog` | کارِ بازیابی‌شدنی هست (≤ `CADENCE_BACKLOG_S` = ۳۰۰s) |
| `discovery-due` | پاسِ شبکه از `DISCOVERY_MIN_GAP_S` (۳ ساعت) گذشته است |
| `discovery-gap` | پاسِ شبکه تازه بوده ⇒ بیدارباش موکول می‌شود (بی‌انباشتِ درخواست) |
| `idle` | صف تهی ⇒ `CADENCE_IDLE_S` (۶ ساعت) |

**دو worker رویِ یکِ کار:** `run_cycle` قفلِ `pipeline_lock` را با
`BEGIN IMMEDIATE` + heartbeat می‌گیرد؛ اگر از بیرون (دکمۀ دستی، Task Scheduler،
یا instanceِ دوم) چیزی در کار باشد، `skipped="locked"` برگردانده می‌شود. علاوه
بر آن، `crawler_busy()` همان `sync_status.json` را می‌خواند که خودِ خزندۀ دستی
می‌نویسد و پاسِ شبکه را موکول می‌کند — چون دو مسیرِ Codal رویِ یکِ IP یعنی ۴۲۹.

**ساعتِ بازار:** محاسبۀ سنگینِ پنج شاخص درِ پنجرۀ معاملاتی (قاعدۀ یگانۀ
`mstat_engine.in_trading_session`، همان که `app.py` مصرف می‌کند) **موکول**
می‌شود و نمادها درِ `pipeline_dirty` می‌مانند؛ بیرونِ نشست انجام می‌شود.
دریافتِ کدال موکولِ ساعتِ بازار نیست (میزبانِ دیگری است) ولی به `crawler_busy`
و بودجۀ صفحه مقید است.

**صداقت دربارهٔ تعطیلات:** درِ این مخزن تقویمِ تعطیلیِ رسمیِ جایگزین وجود ندارد
(سنجش: هیچ `jalali`/`shamsi` درِ کد)؛ «تعطیل» فقط پنجشنبه/جمعه است و وضعیتِ
رسمی از جدولِ `market_index` خوانده می‌شود. ادعایِ «در روزِ تعطیل چیزی نمی‌خوانیم»
نمی‌کنیم.

**وقتی برنامه باز نیست:** رشتۀ زمان‌بند داخلِ backend است، پس با backendِ خاموش
اجرا نمی‌شود. گزینهٔ پشتیبانی‌شده: `scripts/schedule_codal_worker.ps1` که
`python codal_pipeline.py --once --budget 8 --json` را زمان‌بندی می‌کند —
**همان قفل، همان checkpoint، همان صف**. اسکریپت به‌طورِ پیش‌فرض dry-run است و
بدونِ `-Install` هیچ چیزی ثبت نمی‌کند؛ `-Install` نیازمندِ مجوزِ صریحِ مالک است
و ایجنت آن را اجرا نمی‌کند. اگر سیستم خاموش یا شبکه قطع باشد، در آن بازه هیچ
داده‌ای دریافت **نمی‌شود**؛ پس از بازگشت، `-StartWhenAvailable` یکِ اجرا جبران
می‌کند و چرخه از نشانکِ `tracing_no` عقب‌ماندگی را برمی‌دارد.

گارد: `dev/codal_scheduler_v1103.py` — **۴۰ بررسی، ۰ شکست** (exit ۰).

---

## ۴) نقص‌هایِ قابلِ اعتمادِ این جلسه و رفعش

1. **پاسِ شبکه‌ایِ تصادفی درِ گارد:** اجرایِ اولِ `codal_scheduler_v1103.py` با
   `network=None`، چون زمان‌بند خودش «کشف واجب است» را تصمیم گرفت، درخواستِ
   واقعی به `search.codal.ir` زد و `rotate_ip_via_adb` خواست IP گوشی بچرخاند
   (بی‌دستگاهِ متصل، پس به sleep backoff افتاد). این نقضِ قراردادِ مخزن است
   («هیچ کنترلِ واقعیِ دستگاه برایِ تستِ یکِ گارد اجرا نمی‌شود»).
   **رفع:** دربه‌دیوارِ `BORS_CODAL_OFFLINE=1` درِ خودِ `worker_once` (نه فقط درِ
   گارد — از راهِ subprocess هم رد نمی‌شود) + tripwire رویِ `CF.fetch_page` /
   `CF.make_session` که با هر تماسِ بیرونی می‌ترکد. دو بررسیِ تازه ثابت می‌کنند
   `network=True` و `force` هم از این درب رد نمی‌شوند.
2. **`crawler_busy` همیشه «آزاد» می‌گفت:** `write_progress` زمان را با
   `isoformat()` («T» جداکننده) می‌نویسد و `_to_dt` فقط فاصله می‌پذیرفت ⇒ فازِ
   تازهٔ خزندۀ دستی دیده نمی‌شد. رفع: پذیرفتنِ هر دو قالب + بررسیِ تازه.
3. **کارِ محاسباتیِ موکول‌شده گم می‌شد:** `worker_once` با صفِ تهی زودتر از محاسبه
   بیرون می‌رفت، حتی وقتی `pipeline_dirty` پر بود. رفع: «کاری هست؟» حالا
   `dirty_count` را هم می‌شمارد.
4. **دو کدِ اشتباهِ متنیِ خودم:** پنج بنرِ بی‌شماره و رقمِ گم‌شدهٔ `۱۴۵` جای
   `۱۴۰۵` درِ فیکچرِ `codal_pipeline_v1100.py` — `persian_glyph_guard` حالا
   **۴ سبز، ۰ قرمز** است و رقمِ تازه از کدِ نقطه ساخته می‌شود.

---

## ۵) چک‌پوینتِ نشست (برایِ ادامۀ کار در نشستِ بعد)

کامیت‌هایِ این خط، به‌ترتیب:

| کامیت | چیست | گارد |
| --- | --- | --- |
| `c9d68f8` | Stage 1+5 — صفِ پایدار رویِ همان `codal_extracted` + checkpoint + قفل | 42/0 |
| `5fd24c6` | یکِ `letter_to_notice` به‌جای پنج نگاشتِ دست‌نویس | 42/0 + 11 گاردِ codal |
| `a5694fe` | Stage 2 — کشفِ خودکار با نشانکِ `tracing_no` | 45/0 |
| `e8deef9` | Stage 3 — دفترِ عضویتِ ابزار (پنج حالت جدا) | 39/0 |
| `15741d6` | کاراییِ پاسِ Universe: 77.0s → 3.7s | 39/42/45/0 |
| `1aabef2` | Stage 6 — زمان‌بند، بازیابی، CLI، مرزِ «برنامه بسته» | 40/0 |
| `83b89af` | Stage 7 — محاسبۀ افزایشیِ همان نمادها | 25/0 |

گیت‌هایِ اجراشدۀ این نشست (exit ۰ همه): `dev/codal_pipeline_v1100.py` 42/0 ·
`dev/codal_discovery_v1101.py` 45/0 · `dev/codal_instrument_discovery_v1102.py`
39/0 · `dev/codal_scheduler_v1103.py` 40/0 · `dev/codal_incremental_recalc_v1104.py`
25/0 · `dev/codal_derived_ledger_v1073.py` 75/0 · `dev/codal_period_canonical_v1075.py`
51/0 · `dev/codal_ingest_identity_v1088.py` 13/0 · `dev/codal_unit_scale_v1090.py`
34/0 · `dev/codal_reference_select_v1088.py` 50/0 · `dev/codal_publish_date_v1089.py`
24/0 · `dev/codal_merge_recency_v1029.py` 30/0 · `dev/codal_logic_guard.py` 24/0 ·
`dev/test_notifications_v1.py` 30/0 · `dev/persian_glyph_guard.py` 4/0.

**اجرا نشد:** `dev/run_all_tests.py`ِ کامل، `npx vitest run`، `npx tsc -b`،
`npx vite build`، آزمونِ مرورگرِ Stage 10 — هیچ‌کدام درِ این نشست اجرا نشدند.

گامِ بعد (Stage 8+9، به‌همین ترتیب):
۱) `GET /api/fundamental/pipeline` که `PL.health()` را می‌دهد (queue، instruments،
   cursor، last_successful_sync، last_attempt، worker، data_epoch)؛
۲) شکستنِ cache با همان `data_epoch`: درِ `frontend/src/features/fundamental/api/`
   کلیدِ `['fts-card', symbol]` را به epoch ببند، و درِ سمتِ سرور پس از هر چرخۀ
   موفق `invalidate_screener_cache(drop_materialized=False)` (فقط اگر `dirty`
   مصرف شده باشد) — با مستندکردنِ اینکه باطل‌کنندۀ تک‌نمادیِ payload وجود ندارد؛
۳) پنلِ سلامتِ کوچک درِ Same‌جا (الگوی `SymbolInspector`: ارتفاعِ محدود، اسکرولِ
   مستقل، بدونِ پنلِ بزرگ) با هشت شمارشِ الزامی؛
۴) Stage 10 رویِ کپیِ ایزوله (`_audit/codal_census_20261014/copy.db`) + گردشِ
   واقعیِ مرورگر؛ ۵) Stage 11 گیت‌ها با exit code؛ ۶) Stage 12 هماهنگ‌سازی
   `docs/MASTER-EXECUTION-ROADMAP.md` و حذفِ کپیِ موقت.

---

## ۶) آنچه مانده (Stage 8 → 12)

## ۷) آنچه مانده (Stage 7 → 12)

* **۷** محاسبۀ افزایشی با نقشۀ وابستگی (`AXES_BY_SOURCE` ساخته شده؛ مصرف‌کنندۀ
  واقعیِ `bulk_scan`/`evaluate_v10` هنوز به صف وصل نشده).
* **۸** شکستِ cache و نمایشِ تازگی: `invalidate_screener_cache()` و
  `fts_engine.invalidate_fts_results()` تنها باطل‌سازهایِ موجودند و برایِ
  **کلِ** بازار، نه نماد؛ کارت بنیادی هر درخواست را دوباره محاسبه می‌کند
  (pullِ کدنویس) ⇒ تازگیِ سمتِ UI یعنی شکستنِ `['fts-card', symbol]` با
  `data_epoch`.
* **۸/۹** پنلِ سلامت و مشاهده‌پذیریِ کامل.
* **۱۰** پانزده سناریویِ سرتاسری رویِ کپی + گردشِ واقعیِ مرورگر.
* **۱۱** گیت‌هایِ نهایی با exit code و شمارشِ واقعی.
* **۱۲** گزارشِ پایانی و هماهنگ‌سازی `docs/MASTER-EXECUTION-ROADMAP.md`.

**داوریِ مالک لازم (بدونِ تغییرِ من):** چرخشِ علامتِ ~۱۸۵ ردیفِ دفتر و
واکشیِ مجددشان، تناقض‌هایِ عددیِ جزوه، حاشیۀ سودِ تلفیقی، backfillِ
`period_months`/`unit_norm`، شکستِ cacheِ دیسکیِ اسکرینر با تغییرِ کد.

**آزمایش‌هایِ تغییردهنده هیچ‌وقت رویِ `market.db`ِ عملیاتی اجرا نشدند؛** کپیِ
سرشماری درِ `_audit/codal_census_20261014/` است (untracked، پاک‌شدنی).
