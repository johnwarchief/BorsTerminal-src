# گیتِ B4a — بنیادی (دو مسیر) و تاریخچۀ نوار رویِ Go

شاهد: `_audit/parity/B4.json` · گزارشِ کیس‌ها: `_audit/parity/B4-contract.json`
کامیتِ اندازه‌گیری: `97313538` · شاخه: `mission/4-axes-2026-10-10`
محوّلِ اجرا: ۱۴۰۵-۰۸-۰۹ (۲۰۲۶-۱۰-۳۱، ۱۸:۳۴ محلی) — بازار بسته بود، ولی همه‌چیز آفلاین است.

## نتیجه

| | |
| --- | --- |
| کیس‌هایِ قرارداد | **۱۸ از ۱۸** سبز |
| بیشینهٔ دلتای عددی | **۰٫۰** (هیچ عددی حتی در حدِ راندینگ واگرا نبود) |
| جفت‌هایِ وضعیت | فقط `200/200` و `422/422` — دو کیسِ ۴۲۲، مو‌به‌مو همان `quarters-422` و `tape-422` |
| پوششِ مسیر | **۳ از ۳** مسیرِ پورت‌شده درِ این تسک پاسخ Go دید |
| سنجه‌ها | ۱۳ از ۱۳ سبز |
| بانک‌هایِ ریشه | دست‌نخورده: `market.db 4a85b22c…`، `user.db 29ad7b39…` (پیش و پس یکسان) |
| گاردِ کناربانک | ok (هیچ PID غریبه‌ای کشته نشد؛ فقط PIDهایِ همین اسکریپت) |
| کدِ خروجِ گیت | ۰ |

`checks: contract=True delta_zero=True statuses_200_422=True case_coverage=True
routes_3_of_3=True content=True declared_measured=True tape_roles=True
quarters_roles=True go_read_only=True root_untouched=True frozen_copies=True
sidecar_untouched=True`

## چه مسیرهایی سنجیده شد

| مسیر | کیس‌ها | نکته |
| --- | --- | --- |
| `GET /api/fundamental/sectors` | ۱ | فهرستِ صنایع از `instruments`، با همان ترتیبِ واژگانیِ SQLite |
| `GET /api/fundamental/{symbol}/quarters` | ۸ | نمادِ پُررودیف، `limit` ۱ / ۰ / ‎-۵ / ۹۹۹ / `abc`، نمادِ بی‌صورت‌مالی، نمادِ ناشناخته |
| `GET /api/tape-history` | ۹ | دو ins_code، بی‌کد، `days` ۱ / ۰ / ۹۹۹ / `abc`، کدِ ناشناخته، کدِ تکراری، کدِ مخلوطِ فاصله‌دار |

نقش‌ها درِ زمانِ اجرا از همان کپیِ یخ‌زده انتخاب شدند (نه نامِ دست‌نویس):
`fs_rich = دعبید` (چهار دورۀ دوره‌دار با دوِ طولِ متفاوت)، `fs_empty = طفزر816`
(درِ `instruments` هست، هیچ صورتِ مالی ندارد)، `tape_a/tape_b` دو ins_code که
واقعاً درِ `tape_flag_day` ردیف دارند (اولِ پُربارترین، دومِ کم‌بارترین).

## تعویق‌هایِ اعلام‌شده — اندازه‌گیری شد، نه فرض

| کیس | پایتون | Go | حکم |
| --- | --- | --- | --- |
| `GET /api/fundamental/{symbol}` (کارتِ پنج‌محور) | ۲۰۰ | ۵۰۱ `NOT_PORTED` | تسکِ 3b |
| `GET /api/fundamental/{symbol}?months=abc` | **۴۲۲** | ۵۰۱ | اعتبارسنجیِ `months` بی‌مصرف هم درِ Go باید ۴۲۲ بدهد، نه ۵۰۱ |
| `GET /api/fundamental/screen?limit=5` | ۲۰۰ | ۵۰۱ | خروجیِ `api/screener.py` → B7 |
| `GET /api/sync/codal/fts-coverage` | ۲۰۰ | ۵۰۱ | وضعیتِ حلقه‌ها → B6 |
| `GET /api/sync/codal/pipeline` | ۲۰۰ | ۵۰۱ | وضعیتِ حلقه‌ها → B6 |

سنجهٔ `declared_measured` همین پنج ردیف را می‌پاید و **تاریخ‌انقضا** دارد: اگر روزی
کارت پورت شود و کیسش به مقایسه برنگردد، همین سنجه قرمز می‌شود.

## سرعت (همان اجرایِ گیت، هر دو طرف درِ یکِ لحظه)

| کیس | پایتون (ms) | Go (ms) |
| --- | --- | --- |
| `quarters-clamp-high` | ۳۲۹٫۴ | ۱٫۰ |
| `quarters-negative` | ۲۰۵٫۸ | ۰٫۵ |
| `quarters-limit1` | ۱۹۹٫۸ | ۱٫۰ |
| `quarters-rich` | ۱۵۸٫۳ | ۴۹٫۶ |
| `quarters-unknown-symbol` | ۸۸٫۴ | ۰٫۵ |
| `sectors` | ۲۲٫۰ | ۶٫۴ |
| `tape-no-codes` | ۲۹٫۴ | ۰٫۵ |
| `tape-two-codes` | ۸٫۰ | ۱٫۰ |
| میانهٔ همهٔ کیس‌ها | **۱۵٫۰** | **۱٫۰** |

عددِ ۴۹٫۶ برایِ `quarters-rich` تنها کیسی است که Go در آن کندتر از یکِ میلی‌ثانیه
بود. با ترتیبِ اجرایِ کیس‌ها می‌خواند (سازندۀ نقشۀ هویت درِ نخستینِ جست‌وجو کلِ
ستون‌هایِ `symbol` را از بانک می‌خواند) — **این توضیح حدسِ من است و اندازه‌گیری نشده**؛
اثرِ آن رویِ رأیِ پاریتی صفر است، چون بدنه‌ها مو‌به‌مو یکسان شدند.

## چه چیزی پورت شد

- `internal/period`: `ValidGlob`، `DatedSQL`، `UndatedSQL`، `OrderExpr`، `LatestOrderSQL`،
  و `Trim` (`.strip()`ِ پایتون — `strings.TrimSpace` بی‌U+001C تا U+001F است).
  دو طبقه پین شد: متنِ رشته‌ها از خودِ پایتون، و نتیجهٔ همان رشته رویِ SQLite هم از
  خودِ SQLite (۱۷ ردیفِ شاهد).
- `internal/fundamental`: `norm_fa`، `title_entity_suffix`، `_entity_span`،
  `row_completeness`، `statement_rank`، `quarter_reference_rows` + دو مسیر.
- `internal/tapehistory/read.go`: `TradingDays`، `ReliableFrom`، `HistoryFor`
  (دو فهرستِ placeholderِ جدا، کلیدِ روزِ رشته‌ای، placeholderِ «غیرفعال» بدونِ
  بازنویسیِ ردیفِ فعال) + `ParseCodes`/`ClampDays` + هندلر درِ `internal/market`.

## تفاوت‌هایِ اعلام‌شده

۱) `ensure()` درِ پایتون پیش از خواندن، جدولِ نبودِ `tape_flag_day` را **می‌سازد**
(نوشتن درِ user.db). Go درِ فازِ A نمی‌نویسد و همان بدنهٔ خالی را بی‌ساختن می‌دهد؛
بدنه یکی است، اثرِ جانبی نه (فیکسچرِ تسکِ ۱ کیسِ `s3/tape_missing_tables` همین را
می‌پاید).

۲) `write_error` حالتِ پروسه است، نه داده؛ درِ گیت هر دو طرف تازه بالا آمده بودند و
هر دو `null` دادند. حالتِ واقعیِ خطایِ نوشتن راستی‌آزمایی نشده (B5/B-G2).

۳) رشتهٔ خطایِ SQLite درِ `write_error` بینِ دو زبان یکی نیست (`sqlite3.Error` در
برابرِ `err.Error`)؛ مسیرِ Reachable آن درِ دادهٔ واقعی عملاً هیچ‌وقت اجرا نمی‌شود
(تقویم تهی → خروجِ زودهنگام، بی‌کوئری).

## کنترل‌هایِ منفیِ این دور

| چه چیزی دست‌کاری شد | چه دیدی |
| --- | --- |
| حذفِ `trim(` از `DatedSQL` | `TestSQLTextGolden` قرمز (چهار مستعار) |
| `pyTrim` → `strings.TrimSpace` | ردیفِ شاهدِ U+001C قرمز شد |
| خاموش‌کردنِ لایۀ «دامنۀ شرکت» | **ابتدا همه سبز** → آزمون‌ها آن لایه را نمی‌دیدند؛ یکِ کیسِ تازه اضافه شد و سپس همان کیس قرمز شد |
| «درست‌کردنِ» `int(passes or 1)` | چهار طلایی قرمز شد ⇒ رفتارِ باگ-به‌باگ پین است |
| `selected[:limit]` بدونِ محافظ | panic واقعیِ slice bounds — بسته شد |
| اجرایِ گاردِ پایتون هم‌زمان با گیت | گاردِ کناربانک mtime درِ `market.db-shm` را دید و گیت exit 2 داد؛ مقصر اجرایِ هم‌زمان بود، نه پورت |

## راستی‌آزمایی نشده

- کارتِ پنج‌محور و `screen` (تعویقِ اعلام‌شده؛ فقط ۵۰۱ سنجیده شد).
- `pub_canon_sql`/`pub_order_expr`/`undated_counts` پورت نشدند (مصرف‌کننده‌شان درِ
  `m141_map` و حلقه‌هاست؛ `m141_map` با کارتِ پنج‌محور لازم می‌شود و آن‌جا می‌آید).
- نوشتنِ user.db و `ensure()` درِ Go (B5/B-G2).
- رابطِ کاربر: هیچ UI درِ این دور دست‌نخورده؛ مصرفِ `monetary.series` درِ کارت رأیِ
  بصریِ G1 را می‌خواهد.
- `go test -race` (بی‌cgo رویِ این ماشین).
- `dev/run_all_tests.py` کامل درِ این دور اجرا نشد — پیش از ریلیزِ جامع اجرا می‌شود.

## گامِ بعد

**Task 3b** — کارتِ پنج‌محور (`GET /api/fundamental/{symbol}`): `load_fts_config`،
`mstat_engine.market_total_rials`، سالیۀ `fts_engine`
(`company_profile`/`monthly_series`/`ytd_denominator`/`annual_statements`/
`reference_annual`/`eps_assessment`/`eps_ladder`/`gross_margin`/`annualized_sales`/
`ind4_exempt`/`sector_filter`/`m141_map`/`is_suspended`/`avg_trade_value_hmt`)،
`evaluate_v10`، `build_insights` و `v10_data_gaps`؛ سپس پنج کیسِ `declared` به
مقایسه برمی‌گردند. نقشۀ وابستگی با شمارهٔ خط درِ لجرِ B4 ثبت شده است.
