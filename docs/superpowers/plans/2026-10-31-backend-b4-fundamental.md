# B4 — بنیادی و نوار رویِ Go (پلنِ اجرا)

Spec: `docs/superpowers/specs/2026-10-29-backend-go-rewrite-design.md` §۸ (مرحلۀ B4) و §۹ (گیت‌ها)
Decisions: `docs/BorsTerminal-Desktop-Migration-Decisions.md` §۱۴ و §۱۵
Branch: `mission/4-axes-2026-10-10` · پیش‌نیاز: B3 بسته شد (گیت ۳۷ کیس Δ=۰، `b3a5abf5`)

## دامنه

| مسیر | مرجعِ پایتون | حکم |
| --- | --- | --- |
| `GET /api/fundamental/sectors` | `api/fundamental.py:1964` | درِ B4 — یک SELECTِ ساده |
| `GET /api/fundamental/{symbol}` | `api/fundamental.py:1978` | درِ B4 — هستۀ پنج‌محور `evaluate_v10` |
| `GET /api/fundamental/{symbol}/quarters` | `api/fundamental.py:2190` | درِ B4 — `quarter_reference_rows` + clampِ limit |
| `GET /api/tape-history` | `api/market.py:1450` | درِ B4 — خواندنِ `tape_flag_day`/`tape_flag_day_meta` از **user.db** |
| `indicators['1'].monetary.series` | وجود ندارد | **اول پایتون** (§۱۵ بند ۵)، بعد Go |
| `GET /api/fundamental/screen` | `api/fundamental.py:1896` | **نیست → B7**: بدنه‌اش خروجیِ `api/screener.py` است (`_screener_cached` + `fts_engine.bulk_scan` روی ۶۰۱۸ نماد، کشِ RAM/دیسک با TTL ۱۲ ساعت و کلید `cfg_hash#APP_VERSION`)؛ پورتِ آن بدونِ پورتِ screener معنی ندارد |
| `GET /api/sync/codal/fts-coverage`, `/pipeline` | `api/fundamental.py:2505,2517` | **نیست → B6**: وضعیتِ حلقه‌ها را گزارش می‌دهند و حلقه‌ها تا G5 در پایتون می‌مانند (§۱۵ بند ۴) |

درِ پذیرشِ §۸ برایِ B4 «۶ مسیر api/fundamental.py» است؛ سه مسیرِ باقی‌مانده با دلیلِ بالا تعویق می‌افتند و گیتِ B4 همان تعویق را **اندازه** می‌کند (Go ۵۰۱ / پایتون ۲۰۰)، نه اینکه فرض کند.

## تصمیم‌های پیش از اجرا

- **R1 — پنج‌محور دست‌نخورده.** هیچ آستانه‌ای در Go عوض نمی‌شود؛ `v10_thresholds` با همان ترتیبِ پراب (`v10_<k>` → نامِ پنل → کلیدِ مشترک، به‌جزِ `monetary_growth_min` که پرابِ v10 ندارد) و همان `FTS_DEFAULTS` خوانده می‌شود. آستانه‌ها رأیِ مالک‌اند، نه پیشنهادِ من.
- **R2 — `null` با `0.0` و با `false` یکی نیست.** سه تبدیلِ متفاوت درِ یک فایل وجود دارد (`_f` که NaN را ۰.۰ می‌کند، `_num_or_none`، `_rials_or_none`)؛ هر کدام درِ همان جای خودشان پورت می‌شوند، نه یک تبدیلِ مشترک. `states` بی‌نظر ⇒ `null` در حالی که `passes` bool می‌ماند.
- **R3 — ترتیبِ رشته‌ها در SQL.** برگزیدنِ ردیفِ مرجع به `ORDER BY` متنیِ `publish_date`/`symbol` و به `CP.desc_sort_key` پایتون وابسته است؛ Go همان SQLite را صدا می‌زند، پس همین که **ترتیبِ کوئری‌ها و کلیدهایِ مقایسه عیناً** پورت شوند کفایت می‌کند — و با کیسِ «دو نوشتارِ متفاوتِ یک تاریخ» در فیکسچر اثبات می‌شود، نه با استدلال.
- **R4 — گردکردنِ نیم‌به‌زوج رویِ عددِ خام.** مقایسه‌ها رویِ مقدارِ گردنشده (`pot_raw`) و نمایش رویِ گردنشده است؛ هر دو درِ پیلود می‌آیند.
- **R5 — ارقام قاطی نمی‌شوند.** دوره‌هایِ `"%02d/%d"` انگلیسی، تاریخ‌هایِ جلالیِ کاننیکال فارسی، هزارگانِ `_n` و برچسب‌هایِ فارسیِ مصوّبِ جزوه هر کدام همان شکلِ خودشان؛ هیچ نرمال‌سازی‌ای در Go اضافه نمی‌شود.
- **R6 — `months: int = 0` بی‌مصرف است.** درِ `get_fundamental` پارس و ۴۲۲ می‌شود ولی درِ رأی نقشی ندارد؛ Go هم دقیقاً همین کار را می‌کند (اعتبارسنجی می‌شود، ولی اثری درِ رأی ندارد).
- **R7 — فقط‌خواندنی.** مسیرهایِ B4 شبکه نمی‌زنند؛ نوشتن‌هایِ پایتون درِ همین مسیرها ساختِ ایندکس/اسکیما (`api/_core.py:96-144`، `ensure_market_cap_schema`) و کشِ اسکرینر رویِ دیسک است. Go رویِ market.db `mode=ro` می‌ماند و تفاوت را اعلام می‌کند؛ هیچ `journal_mode` یا اسکیمایی عوض نمی‌شود.
- **R8 — `write_error` وضعیتِ پروسه است، نه داده.** درِ پایتون از متغیرِ ماژول‌سازِ `_last_err` می‌آید؛ Go آن را با فیلدِ معادلِ همان-پروسه پیاده می‌کند و درِ گیت (که هر دو سرویس تازه‌اند) دو طرف `null` می‌دهند — این درِ گزارشِ اعلام‌شده می‌آید، نه پنهان.
- **R9 — ترتیبِ ثبتِ مسیرها.** درسِ `fts/config` درِ B3: هر مسیرِ صریحِ هم‌خانواده (`sectors`, `screen`) **پیش از** `{symbol}` ثبت می‌شود و یک آزمونِ رگرسیون ثابت می‌کند `{symbol}` آن‌ها را نمی‌بلعد.

## وظیفه‌ها

**Task 0 — فیلدِ افزودنی در پایتون (پیش از هر پورت).** `indicators['1'].monetary.series` از `fts_engine.monthly_series:1133` (ردیف‌هایِ ماهانۀ کاننیکال‌شده، با همان `_dedupe_ym`) درِ `evaluate_v10` منتشر شود؛ تستِ پایتون (`dev/fund_monetary_series_b4.py`) ردیف‌ها، ترتیب، و حالتِ «سری نیست ⇒ این کلید نباشد» را بزند؛ `series_months` دست‌نخورده بماند. فقط افزودنِ فیلد، بدونِ هیچ تغییرِ UI.

**Task 1 — فیکسچر + اوراکل + طلایی‌ها + گارد.**
`tools/parity/make_fundamental_fixture.py` رویِ `backend-go/internal/fundamental/testdata/fixture/`: `financial_statements` (چند دورۀ ۱۲/۳/۶ ماهه، `tracing_no` نامرتب، `publish_date` تهی/متنی/تهیِ سال، `gross_profit` NULL، تکراریِ همان دوره)، `monthly_sales` (دورۀ ۱۲/۹/۶ ماهه، دِدوپِ همان `YYYY/MM`، یک ردیفِ بی‌دوره)، `codal_notices` (زنجیرۀ datasource ← عنوان)، `instruments`/`market_watch`/`daily_prices` برایِ mcap، سه نماد: صعودیِ پنج‌محور قبول، صندوقِ «هیچ‌جا مردود نمی‌شود»، نمادِ داده‌گپ‌دار؛ درِ user.db: `tape_flag_day` + `tape_flag_day_meta` با هفت فیلتر، روزهایِ بی‌فیلتر (placeholder `active:false`)، و `reliable_from`. اوراکل `gen_fundamental_golden.py` با envهایِ آفلاینِ B3 (بی‌شبکه، مسیرِ دادهٔ موقت) و «امروز»ِ میخ‌کوبی‌شده. گاردِ `dev/test_fundamental_fixture_b4.py` درِ `dev/run_all_tests.py` ثبت می‌شود: قطعیتِ فیکسچر، برابریِ طلایی‌ها با اجرایِ تازه، هر کیس پیلود دارد، کنترلِ منفیِ درزها.

**Task 2 — گسترشِ `internal/period`.** ثابت‌ها و عبارت‌هایِ SQLِ `codal_periods.py` (`DATED_SQL`، `UNDATED_SQL`، `order_expr`، `pub_order_expr`، `latest_order_sql`، `pub_canon_sql`) و `undated_counts`؛ با وکتورهایِ طلایی از خودِ پایتون.

**Task 3 — هستۀ پنج‌محور.** `internal/fundamental`: `mcap`، `sector`، `annual_statements`، `eps_assessment/eps_ladder`، `gross_margin`، `annualized_sales`، `ind4_exempt`، `sector_filter`، `axis1_pass`، `v10_axis_states`، `v10_data_gaps`، `evaluate_v10` و رشته‌هایِ کارت. هر شاخه یک وکتورِ نام‌دار با عددِ خودِ پایتون.

**Task 4 — سه مسیرِ بنیادی.** `sectors`، `{symbol}` (با `months` بی‌مصرف)، `{symbol}/quarters` (clampِ `max(1,min(limit,40))` و انتخابِ مرجع بی‌`ORDER BY` در SQL)؛ هندلرها + 422ها + ثبتِ مسیرها به ترتیبِ R9.

**Task 5 — `tape-history`.** خواندنی‌هایِ `internal/tapehistory` (`TradingDays`، `ReliableFrom`، `HistoryFor` با placeholderها و کلیدهایِ روزِ رشته‌ای، `Summary`) + `codes[:400]` و clampِ روزها + `write_error` + هندلر و مسیر.

**Task 6 — گیتِ B4.** `tools/parity/cases_b4.json` + `gate_b4.py` رویِ کپیِ یخ‌زده با نمادهایِ پویا از همان کپی (نمادِ پنج‌محورقبول، صندوق، داده‌گپ، بی‌داده، نمادِ دارایِ تاریخچۀ نوار)؛ چک‌هایِ اعلام‌شده: `screen` و `sync/codal/*` در Go ۵۰۱ و در پایتون ۲۰۰ **اندازه‌گیری** می‌شود؛ پنج محور با حالت‌هایِ بی‌نظر/داده‌گپ؛ هفت فیلترِ نوار؛ سریِ ماهانه ردیف‌به‌ردیف. گزارشِ فارسی + بازبینیِ مستقل + دورِ اصلاح با کنترلِ منفی + لجر + پوش.

## قالبِ چهارگانهٔ گاردِ معماری

**What changes.** دو پکیجِ تازه درِ `backend-go/internal` (`fundamental`، خواندن‌هایِ `tapehistory`)، گسترشِ `period`، یک فیکسچر/اوراکل/گارد، و یک افزودۀ کوچک درِ `api/fundamental.py` + `fts_engine.py` (Task 0). هیچ فایلِ موجودی جابه‌جا یا حذف نمی‌شود.

**Invariants touched.** (۱) ترتیبِ ثبتِ مسیرها — R9 و آزمونِ رگرسیون؛ (۲) قراردادِ HTTP یخ‌زده (§۱۵ بند ۳) — فقط افزودنِ فیلد، بدونِ تغییرِ فیلدهایِ موجود؛ (۳) فاز A: Go رویِ market.db فقط‌خواندنی است و `user.db` را درِ B4 **نمی‌نویسد** (نوار فقط خواندنی است؛ نوشتنِ user.db درِ B5/B-G2 می‌آید)؛ (۴) اسکیما و `journal_mode` دست‌نخورده؛ (۵) `numpy==2.0.2` و هیچ وابستگیِ تازه‌ای نه در پایتون نه در Go (فقط `modernc.org/sqlite` موجود).

**Lockstep updates.** `fts_terminal.spec/hiddenimports`: **هیچ** — هیچ ماژولِ `api/*.py` تازه‌ای اضافه نمی‌شود (Task 0 داخلِ فایل‌های موجود است). ESLint/frانت: **هیچ** (B4 رابط را دست نمی‌زند؛ مصرفِ `monetary.series` در UI کارِ همان مسیرِ بنیادیِ UI است و رأیِ بصری G1 را می‌خواهد). گاردها: `dev/run_all_tests.py` با گاردِ تازه؛ `dev/struct_check.py` و `dev/undef_name_guard.py` باید سبز بمانند (سابقۀ دو نامِ تعریف‌نشده در همین فایل درِ ریلیز ۱.۰.۴۱ زنده بود). `dev/persian_glyph_guard.py` هم برایِ متن‌هایِ تازه.

**Guard that proves it.** `dev/test_fundamental_fixture_b4.py` (قطعیت + تازگیِ اوراکل + محتوایِ هر کیس + کنترلِ منفی) و گیتِ `_audit/parity/B4.json` با Δ=۰ و جدولِ پوشش؛ به‌علاوۀ `go test ./...` و آزمونِ ترتیبِ مسیرها درِ `internal/httpapi`.

**Rollback.** هر تسک یک کامیت؛ بازگشت = `git revert` همان کامیت‌ها (هیچ مهاجرتِ دیتابیسی نیست). برنامهٔ نصبی هنوز پایتون اجرا می‌کند؛ پروکسیِ dev با یک ردیف به پایتون برمی‌گردد (§۱۵ بند ۸).

## آنچه راستی‌آزمایی نخواهد شد (صریح)

- حالت‌هایی که فقط با نوشتنِ user.db ساخته می‌شوند (B-G2 درِ B5).
- `write_error` درِ حالتِ واقعیِ نوشتن (درِ گیت دو طرف `null` است).
- پاسخِ کاملِ `/api/fundamental/screen` و `/api/sync/codal/*` (تعویقِ اعلام‌شده، فقط اندازه‌گیریِ ۵۰۱).
- مصرفِ UIِ فیلدِ تازه (کارِ UI و رأیِ G1).
