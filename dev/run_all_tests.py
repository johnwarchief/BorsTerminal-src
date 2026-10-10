"""
v9.5 — اجرای همهٔ تست‌های آفلاین (بدون نیاز به سرور)
اجرا:  python dev/run_all_tests.py
تست نیازمند سرور جدا است:  python dev/serve_check_v95.py
"""
import os, re, subprocess, sys

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

SUITES = [
    ('dev/struct_check.py',           'structure / undefined-names'),
    ('dev/test_fts_isolation.py',     'FTS filter isolation'),
    ('dev/fts_pipeline_v981.py',      'codal FTS pipeline + ADB fallback + session window'),
    ('dev/test_calendar_v92.py',      'calendar py<->js categories'),
    ('dev/chart_api_check_v95.py',    'chart API guard: installed klinecharts v10 exports, no dead legacy path'),
    ('dev/fts_m141_parity_v97.py',    'm141/liquidity parity + anti-N+1'),
    ('dev/adb_resilience_v972.py',    'ADB retry/reconnect + wifi restore'),
    ('dev/confidence_engine_v973.py', 'triple-confirmation confidence engine'),
    ('dev/soft_warnings_v974.py',     'soft pass/warn/fail/nodata — no hard vetoes'),
    # بستۀ هفتگیِ موتورِ اطمینان باید همان سبدِ شنبه‌محورِ خودِ چارت باشد؛ سنجشِ
    # ۷۴۸ نمادی (§۱-ح-۵ و _audit/ce_weekly_calendar_impact.py) MA52 را تا ۱۲٪ و
    # شمارِ سطل را در ۲۹ از ۴۰ نماد جدا می‌دید. گارد با منفی‌کنترلِ ISO.
    ('dev/ce_weekly_bucket_v1073.py', 'confidence_engine weekly bucket == chart Saturday bucket'),
    ('dev/mstat_local_v975.py',       'mstat dashboard computed from local market.db'),
    ('dev/watchlist_matrix_v973.py',  'watchlist store + triple matrix + parity'),
    ('dev/patch_check_v10.py',        'patch/update system guard'),
    ('dev/test_arg_parse_v10.py',     'make_patch --from arg parsing'),
    ('dev/test_delta_update.py',      'delta patch select/apply + fallback'),
    ('dev/test_fund_revenue_v1027.py', 'fund sheet: سود سهام هرگز «فروش» نمی‌شود'),
    ('dev/loopback_guard_v1029.py',   'API فقط از حلقهٔ محلی / نشانیِ نصاب از مانیفست'),
    ('dev/fund_not_applicable_v1028.py', 'صندوق هیچ‌جا مردود نمی‌شود (کارت/اسکرینر/تابلو/مستر)'),
    ('dev/typography_guard.py',        'هیچ کلاس اندازهٔ مرده‌ای در فرانت نماند (نردبان 3xs/2xs)'),
    # NPM-LOCK: ریلیزِ ۱٫۰٫۳۹ درِ CI مُرد چون قفلِ npm با package.json نمی‌خواند
    # (npm ci → ERESOLVE). این گارد همان داوریِ npm را پیش ازِ تگ می‌زند؛ بی‌شبکه
    # هم تا حدِ ساختاری روشن می‌ماند و خطایِ شبکه را به حسابِ قفل نمی‌گذارد.
    ('dev/npm_lock_v1040.py',           'قفلِ npm درِ CI هم نصب می‌شود (npm ci، نه فقط node_modules محلی)'),
    # UNDEF-NAME: دو نامِ تعریف‌نشده درِ api/fundamental.py از اولین ریلیز تا
    # ۱٫۰٫۴۱ زنده بودند و هر کارتِ بنیادیِ یک قراردادِ اختیار (۱٬۰۴۹ نماد) ۵۰۰
    # می‌داد؛ struct_check با عنوان «undefined-names» بی‌صدا ok می‌گفت.
    ('dev/undef_name_guard.py',         'هیچ نامِ تعریف‌نشده‌ای در کدِ منتشرشده (NameError درِ شرطِ نایاب)'),
    # DATA-AGE-1: سنِ market.db.lzma/codal.db.lzmaیِ منتشرشده. رفتاری است با
    # دیتابیسِ ساختگی، پس به bank نیاز ندارد و در CI هم سبز می‌ماند.
    ('dev/data_age_release_guard.py',  'سنِ دادهٔ ریلیز سنجیده می‌شود: کهنه=هشدار، کهنه‌تر از baseline=رد'),
    # CODAL-MERGE-1: دکمهٔ «بروزرسانی دیتابیس کدال» رویِ اسنپ‌شاتِ کهنه نباید
    # ردیفِ تازهٔ محلی را با عددِ قدیمی جایگزین کند. رویِ DBهایِ موقتِ کوچک
    # اجرا می‌شود، پس در CI هم واقعاً می‌دود (بی‌SKIP).
    ('dev/codal_merge_recency_v1029.py', 'ادغامِ کدال: محلیِ تازه‌تر هرگز بازنویسی نمی‌شود'),
    # UPDATE-ROLLBACK-1: همان اصلِ کدال برایِ market.db. «نصبِ کامل» (سهمِ
    # کاربرِ نسخهٔ گذشته‌مانده، چون دلتا پچ فقط from==نسخهٔ فعلی را می‌پذیرد)
    # کل market.db را با baselineِ نصاب عوض می‌کرد و کندل‌هایِ سینک‌شده می‌مردند.
    ('dev/market_db_union_v1069.py',    'ادغامِ market.db: دادهٔ بازارِ کاربر با ارتقا له نمی‌شود'),
    # UPDATE-ROT-1: پچِ دلتا حذف نمی‌کند و Vite هر build نامِ chunk را عوض می‌کند
    # ⇒ ۷۴۶ فایلِ js/css درِ نصب در برابرِ ۲۷ فایلِ manifestِ همان نسخه.
    ('dev/stale_chunk_prune_v1069.py',  'پاک‌سازیِ chunkهایِ مردهٔ frontend، با درختِ ساختگی'),
    # دو باندلِ KLineCharts (public/vendor روی window و پکیجِ npm) دو API دارند؛
    # getCrosshair فقط در یکی روی Chart است. بی‌این گارد، خط‌کشِ نهایات‌نگر کرش کرد.
    ('dev/chart_single_bundle_v1038.py', 'چارتِ یکتا: هر متدِ Chart باید در باندلِ خودش باشد و باندلِ دومی نباشد'),
    # #176: تابلو پایِ بازسازیِ ۱.۴ ثانیه‌ایِ کش نمی‌ایستد (کهنه فوراً،
    # بازسازیِ تک‌نفره در پس‌زمینه، و سقفِ کهنگی که خطا را پنهان نکند).
    # #177: سطرِ «جمع»ِ خالی/صفرِ کدال نباید برچسبِ «فروش» را به یک سطرِ جزء
# واگذار کند — رویِ datasourceِ ساخته‌شود، بی‌شبکه.
    ('dev/codal_blank_total_v1036.py', 'blank published total refuses a component line for فروش'),
    ('dev/market_swr_v1036.py',      'board cache is stale-while-revalidate, single-flight, honest on failure'),
    # #120 ریشۀ باگِ تازهنشدنِ تابلو: تیکِ زندۀ پنج‌ثانیه‌ای — یکِ درخواست، یکِ
    # نگاشتِ مشترک با سینک، و دربِ ۱۲:۳۰ که صف‌هایِ بستۀ بازار را نسوزاند.
    ('dev/market_tick_v1045.py',     'live 5s board tick: one request, shared row map, closed-window refuses to write'),
    # #187: تحلیل FTSِ سرور باید همان سریِ تمام‌تاریخِ تعدیل‌شده‌ای را ببیند که
    # چارت می‌رسمد — بی‌شبکه و بی‌market.db (هر دو منبع جعل می‌شوند).
    ('dev/fts_series_basis_v1036.py', 'server FTS reads the full adjusted series the chart draws, not the starved raw table'),
    # کشِ تحلیل FTS بدونِ مبنایِ قیمت درِ کلید، عوض‌کردنِ «آخرین ↔ پایانی» را تا
    # ۹۰۰ ثانیه بی‌پاسخ می‌گذاشت (برایِ نمادی که آخرینِ close == closing است).
    ('dev/fts_cache_basis_v1078.py', 'FTS analysis cache key carries the price basis (with a negative control)'),
    # Round K / PHASE A: چهار مفهومِ تعدیل جدا از هم، یک سریِ کاننیکال برایِ همهٔ
    # مصرف‌کننده‌ها، و فال‌بکی که «داوریِ تعدیل در دسترس نیست» را اعلام می‌کند،
    # نه اینکه سریِ خام را «تعدیل‌شده» جا بزند.
    # Round M §۱۹: گیتِ هفتگی و ساعتِ شنیِ هفتگی فریزِ مالک‌اند — این گارد
    # قاعده را رویِ ۴۰ نمادِ واقعیِ بانک می‌سنجد و بی‌بانک SKIP می‌شود، نه شکست.
    ('dev/test_roundm_freeze.py',
     'weekly gate + weekly hourglass stay frozen (measured on real bank rows)'),
    ('dev/test_adjustment_phasea.py',
     'canonical adjustment: mode semantics split, single scaled series, honest fallback'),
    ('dev/fts_chart_engine_v1037.py', 'chart fib belts and setup markers come from the one server engine, over the current wave'),
    ('dev/repo_hygiene_v97.py',       'repo hygiene / dead-code stays gone'),
    ('dev/test_fts_v10_ladder.py',    'FTS v10 EPS evidence ladder + partial table row'),
    ('dev/test_fts_technical_tristate.py',
     'technical setups stay three-state (null != false) and each rule matches the notebook'),
    ('dev/test_fts_roundj.py',
     'Round J: jet is last-candle-only, point-hunt trigger ≠ anchor, exit tri-state, roles + status priority'),
    ('dev/test_fts_asof_cutoff.py',
     'FTS analysis as_of is a real input cutoff; the cache key carries as_of + ruleset so cutoffs never leak'),
    ('dev/test_trend_engine_flag.py',
     'trend engine flag: legacy is byte-identical, hybrid is a drop-in, jet unchanged, cache isolated by engine, weekly gate rule preserved'),
    ('_audit/candle_integrity_roundj.py',
     'candle integrity + published-TSETMC parity along feed → engine → chart'),
    ('dev/test_fts_market_cap.py',    'TSETMC market-cap source of truth + risk filters'),
    # شاخص ۴: حکمِ معافیت/N/A باید بین fts_engine (اسکرینر) و api/fundamental
    # (کارت) یکی باشد — پیش از این این سوئیت اصلاً در SUITES نبود و پاریتیِ
    # اسکرینر/کارت هم کارت را با خودش می‌سنجد (۲۳۱ نماد واگرایی بی‌صدا ماند).
    ('dev/fts_screener_card_parity_v10.py',
                                      'screener<->card parity + ind-4 exemption engine vs card'),
    # پاریتیِ **تمام‌سطحی**ِ دو مسیرِ موتور (sample-based بودنِ گاردِ بالا سه
    # واگراییِ مرزی را ندید): آستانه باید با عددِ خام سنجیده شود، نه با
    # مقدارِ گردشدۀ منتشرشده. ~۲ دقیقه (۹۲۱ فراخوان scan_symbol).
    ('dev/fts_engine_paths_parity_v1076.py',
                                      'scan_symbol == bulk_scan on every symbol + raw-threshold boundary'),
    # جدولِ مادی‌شدهٔ fts_results باید فیلد‌به‌فیلد با evaluate_v10ِ زنده یکی باشد.
    # این گارد در SUITES نبود — و همان‌جا سه ناهم‌خوانیِ `3_gross_margin` (None در
    # جدول ⇄ False در کارت) یکِ دورِ کامل پنهان ماند؛ علتِ واقعی‌اش هم فیکچری بود
    # که `period_end` را با خطِ تیره می‌نوشت و زیرِ قراردادِ canonical بی‌دوره شد.
    ('dev/test_fts_results_materialize.py',
                                      "materialized fts_results == live evaluate_v10, field by field"),
    # قیف/جدول نباید «بی‌داده» را «رد» بنویسد: شاخص ۳ (حاشیۀ ناخالص) در اسکرینرِ
    # زنده bool می‌ماند و ۲۹۷ نماد بی‌سطرِ سود ناخالص سرخ می‌شدند (۱۴۰۵-۰۷-۰۹).
    ('dev/fts_ind3_na_guard_v1065.py',
                                      "indicator-3 no-data is 'not measured', never 'rejected' (both cache paths)"),
    ('dev/codal_logic_guard.py',      'codal logic contract F-01..F-05 (amendment)'),
    ('dev/db_contract_v11.py',        'FTS v2.2 db contract: writer/reader/schema agree'),
    ('dev/version_anchor_guard.py',   'all six version anchors state the same release'),
    ('dev/fts_defaults_parity_guard.py', 'FTS guide defaults: FE drawer mirrors the server'),
    ('dev/weekly_veto_guard.py',      'weekly downtrend/neutral is a hard veto; no-data is not'),
    # وتوی مجمع (رأیِ مالک، نه چارت): برچسبِ جدول و وتوی اسکرینر باید یک افق و یک
    # پنجرۀ تقویم داشته باشند، و وتو بیرونِ کشِ ۱۲ ساعته حساب شود. بی‌شبکه —
    # هم تقویم و هم کشِ اسکرینر جعل می‌شوند.
    ('dev/assembly_veto_v1064.py',    'assembly veto: fresh outside the cache, no-data is not a veto'),
    # سیمِ مرگِ وتوی هفتگی: هیچ تولیدکننده‌ای رأیِ هفتگی را منتشر نمی‌کرد، پس
    # گیت برای هر نمادی «در انتظار» می‌ماند. پیوتِ کهنه ⇒ سنجشِ بازۀ اخیر.
    ('dev/fts_trend_staleness_v1064.py', 'weekly trend verdict from live pivots or the recent window, never a stale pivot'),
    # موتورِ FTS چهار جا عددِ جا‌زده منتشر می‌کرد: هفتۀ ISO روی بازارِ شنبه‌محور،
    # کمربندِ فیبوِ موجِ نزولی از سقف، حدِ ضرر روی کندلِ نیمه‌کار، MA52 با کمتر از
    # ۵۲ کندل، و روزانۀ na در آغالتِ «خنثیِ مجاز». بی‌شبکه و بی‌market.db.
    ('dev/fts_engine_honesty_v1066.py',
                                     'FTS engine publishes no made-up numbers (week, fib, stop, MA52, na)'),
    ('dev/test_cumulative_db_v1020.py', 'market.db re-extracts on a new bundled baseline'),
    # --pack تنها تاریخِ آخرین نشست را می‌دید؛ روی این ماشین بانکِ مخزن با
    # نشستِ همان روز ۱۴٬۸۶۶ ردیف daily_prices کم‌تر از بیس‌لاینِ منتشرشده داشت.
    # با بانکِ کوچکِ مصنوعی: رد، پذیرشِ --allow-shrink، و «ناشناخته ≠ صفر».
    ('dev/pack_rowcount_guard_v1065.py',
                                      'pack refuses a baseline with fewer rows than the committed one'),
    # Data-Lifecycle (گام ۳۴/۳۵): ستون‌های مشتقِ خودکار + تاب‌آوریِ سینکِ افزایشی.
    # نکته: run() مسیر را با os.sep می‌سازد و سپس split می‌کند، پس آرگومانِ
    # اضافی باید در همان رشته باشد (درست مثل test_arg_parse_v10).
    ('dev/db_backfill_derived.py --selftest',
                                      'derived columns at insert (backfill selftest)'),
    ('dev/incremental_sync_resilience.py',
                                       'incremental sync: new symbol + new monthly report'),
    # R1/R2 housekeeping (plans/codal-final-audit.md): dedupe اصلاحیه‌ها +
    # backfill ستون‌های «سال قبل». یدم‌پذیر و روی کپیِ تازه اجرا می‌شود.
    ('dev/db_housekeeping.py --selftest',
                                       'R1/R2 housekeeping: dedupe + prev-year backfill'),
    # Phase B (plans/production-packaging-and-unpark-plan.md): onedir build.
    # api_router() ماژول‌ها را داخلِ بدنهٔ تابع import می‌کند → اسکنِ استاتیکِ
    # PyInstaller آن‌ها را نمی‌بیند. این چک جلویِ مرگِ سایلنت را می‌گیرد.
    ('dev/onedir_contract_v11.py',  'onedir build contract: hiddenimports + shape'),
    # گام ۲ (ممیزی زندهٔ تابلو): حالتِ آفلاین فقط حالاتِ مرزی را می‌سنجد —
    # حجم/تعدادِ صفر، نبودِ ClientType، معاملهٔ بلوکی. حالتِ کاملِ زنده
    # (--symbols ...) به شبکه نیاز دارد و در CI سبز نمی‌ماند، پس جداست.
    ('dev/live_market_board_audit.py --offline',
                                    'live board audit: zero-volume / no-CT edge cases'),
    # v1.0.12: گاردِ سازگاریِ ویندوز + رندرِ نرم‌افزاری. رویِ سیستم‌های بدونِ
    # GPU اختصاصی کرومیوم صفحهٔ سفید می‌زد؛ حالا SwiftShader می‌زند.
    ('dev/test_compat_guard_v1012.py', 'Windows + GPU/software-render guard'),
    # LOG-CLOCK: لاگِ بی‌ساعت + بافرِ بلوکی، «مرگِ بی‌صدای» برنامه را غیرقابلِ
    # داوری کرده بود. گارد با دو کنترلِ منفی ثابت می‌کند خودش را می‌گیرد.
    ('dev/log_clock_guard_v1055.py',  'log has a clock and survives a hard death'),
    # CANDLE-1: کندل باید همان باشد که TSETMC منتشر می‌کند (ترمیمِ هندسه +
    # رِفتنِ تعدیلِ جعلی). نه شبکه می‌خواهد نه market.db.
    ('dev/candle_source_fidelity_v1033.py',
                                     'candle fidelity: geometry repair + anchored adjustment'),
    # LIVE-BAR-1 (گزارشِ مالک رویِ فولاد ۱۴۰۵-۰۷-۰۷): کندلِ زنده با تاریخِ
    # خودِ نشست تزریق می‌شود، در هر دو اندپوینت، و کش را آلوده نمی‌کند.
    ('dev/live_bar_session_date_v1059.py',
                                     'live candle: session date, both chart endpoints, cache untouched'),
    # CANDLES-STALE-1 (پرسشِ مالک ۱۴۰۵-۰۷-۰۷): هیچ حلقه‌ای price_history را
    # نمی‌نوشت؛ حالا کندل از خودِ daily_prices ساخته می‌شود و سایه‌هایِ
    # بی‌هندسهٔ کهنه اصلاح می‌شوند. بی‌شبکه، رویِ جدول‌هایِ موقتِ کوچک.
    ('dev/candles_from_board_v1062.py',
                                     'candles from the board table + geometry repair + no prune-before-fetch'),
    # کارِ #73 قدمِ ۲ (docs/CANDLE-CONTRACT.md §۱-ث): «آخرین» و «پایانی» دو ستونِ جدا درِ
    # price_history‌اند، open از FIRST است، و `/api/chart-db` دیگر last := close نمی‌سازد؛
    # لنگرِ تعدیل هرگز last را نمی‌خواند. بی‌شبکه — CSV و تابلو فیکسچرند.
    ('dev/price_last_value_v1070.py',
                                     'last/closing are separate columns; no fabricated last, anchor untouched'),
    # کارِ #73 قدمِ ۳: price_basis تنها نقطۀ انتخابِ ستونِ قیمت است (last|closing،
    # پیش‌فرض last، سمتِ سرور) و لنگرِ تعدیل تحتِ هر دو مبنای بیت‌به‌بیت یکی می‌ماند.
    ('dev/price_basis_v1070.py',
                                     'single price resolver (last|closing) + adjustment anchor invariance'),
    # تصمیمِ مالک ۱۴۰۵-۰۷-۱۱: هرسِ ۷۳۰روزه حذف شد — بانک هر تاریخچۀ منتشرشده را نگه
    # می‌دارد (FTS/الگو/بک‌تست به عمق نیاز دارند) و سینک increment می‌ماند، پس نه
    # دانلودِ کاملِ هر اجرا و نه بازنویسیِ ردیفِ موجود. بی‌شبکه: CDN فیکسچر است.
    ('dev/history_depth_v1070.py',
                                     'no history pruning, incremental sync, idempotent second run'),
    # Step 4: هشت سازندۀ کندل یک قرارداد دارند — یک هندسه (widen)، یک مالکیتِ سطر
    # (published > board)، یک شکلِ خروجی. واگراییِ پیش از این اندازه گرفته شد.
    ('dev/candle_contract_v1071.py',
                                     'one candle contract: shared geometry, writer priority, same numbers from every source'),
    # Step 6 (ریشۀ اختلافِ تعدیل با رهاورد): TSETMC بعضی تعدیل‌ها را درِ <CLOSE> یکِ
    # سطرِ بی‌معامله (VOL=0) می‌گذارد و «قیمت پایه» را نمی‌چرخاند، پس قاعدۀ
    # «گسستِ پایه = تعدیل» آن‌ها را کامل از دست می‌داد (وبملت: شش تعدیلِ ۱۳۹۰–۱۳۹۳،
    # مقیاسِ آن دوره تا ۳٫۸ برابر با رهاورد). پوششِ گام‌هایِ مرجع: ۷۰٫۴٪ → ۷۶٫۱٪.
    ('dev/adjust_zero_volume_v1072.py',
                                     'adjustment also from restated close on zero-volume rows; four negative controls'),
    # هدفِ ۱ دورۀ بنیادی: `feed_sync` دوره را **سراسری** dedupe می‌کرد — به‌محضِ این‌که
    # یکِ نماد دورۀ ۱۴۰۵-۰۶-۳۱ را ثبت می‌کرد، گزارشِ بقیۀ بازار برایِ همان دوره برایِ
    # همیشه بی‌ردیف می‌ماند (۳٬۵۱۶ از ۳٬۵۳۷ فروشِ ماهانه و ۶٬۰۷۸ از ۶٬۱۷۱ صورتِ مالی
    # درِ بانکِ امروز). کلیدِ درست `tracing_no` است + دفترِ `codal_extracted`؛ شکستِ
    # شبکه ثبت نمی‌شود تا دوباره تلاش شود، و قاعدۀ ترجیح (مستقل بر تلفیقی) یک‌جا.
    ('dev/codal_derived_ledger_v1073.py',
                                     'one notice = one extraction; shared period never blocks another symbol'),
    # «دورۀ گزارش» پنج تفسیر داشت (`period_end IS NOT NULL` سه جا، `str(pe)[:4]`
    # دو جا، سه regex استخراج، چهار کپیِ «latest by period_end» برایِ نامِ شرکت).
    # حالا یکِ تعریف درِ `codal_periods.py` است و این گارد ثابت می‌کند شرطِ SQL و
    # شرطِ پایتون یکی‌اند، ردیفِ بی‌دوره حذف/برنده نمی‌شود، و همهٔ consumerها
    # (fts_engine / api.fundamental / api.screener / db_housekeeping) یکِ عدد
    # «بی‌دوره» می‌بینند. بی‌شبکه؛ خواندنِ market.db فقط read-only است.
    ('dev/codal_period_canonical_v1075.py',
                                     'one canonical period rule; SQL and Python agree; every consumer sees one count'),
    # هدفِ ۲ دورۀ audit پیش از FTS: چهار مسیرِ «داده تازه شد ولی برنامه کهنه جواب
    # داد» — کشِ اسکرینر پس ازِ سینکِ بازار/کدال، تولدِ زیرپروسۀ خزنده درِ EXE
    # (sys.executable خودِ EXE است)، کلیدِ سه کشِ چارت بی‌مبنایِ قیمت، و سریِ
    # برش‌خورده/حل‌نشده درِ INDEX_CACHE. بی‌شبکه و بی‌market.dbِ واقعی.
    ('dev/stale_wiring_v1073.py',
                                     'fresh data invalidates the dependent caches; no crawler child in the frozen build'),
    # ممیزیِ اندیکاتورها (۱۴۰۵-۰۷-۱۴، docs/INDICATOR-PARITY-1405-07-14.md): سه خطایِ
    # عددیِ اثبات‌شده قفل می‌شوند — شمارندِ `/api/ma` (باید عرضِ پنجره باشد)، گامِ
    # اضافیِ بذر درِ `_fts_rsi` (وایلدرِ خالص؛ بدترینِ انحرافِ پیشین Δ=۱٫۸۸ رویِ پنجرۀ
    # ۳۵ سطری در برابرِ آستانۀ واگراییِ ۱٫۰)، و `last := close×k` درِ `_fts_scaled`.
    # مرجع = همان oracleِ `_audit/indicator_audit/` (خودش ۳۲/۰ سبز) رویِ fixtureِ
    # ۶ نماد × ۳۰۰ کندلِ واقعیِ درِ گیت. بی‌شبکه.
    ('dev/indicator_math_v1074.py',
                                     'indicator math: MA divisor, Wilder RSI seed, and FTS last/closing are oracle-exact'),
    # TA-SCOPE-1 (پرسشِ مالک ۱۴۰۵-۰۷-۰۷: «نبض را کامل با تریدرزآرنا تطبیق بده»):
    # دامنهٔ «کل بازار» = سطرهایِ market0ِ او، نشتِ صکوک/مشارکت/سلف از سطرِ سهام
    # بسته شد، و «ارزش کل بازار»ِ نصفه نه نوشته می‌شود نه خوانده.
    ('dev/pulse_ta_scope_v1063.py',
                                     'pulse scopes match tradersarena + no half-written market total'),
    # TAPE-F / JET-BREAK / HIST-SRC: پنج فیلترِ تابلو عینِ جزوه، و «نبودنِ
    # داده» هیچ‌وقت قبول نیست. پیش از این هیچ سویتی این فرمول‌ها را نمی‌پوشاند.
    ('dev/tape_filters_v1034.py',   'tape filters: five formulas match the notebook'),
    # SMART-MONEY: «ورود پول هوشمند» و «کد به کد» عینِ دو فایلِ تازهٔ جزوه،
    # درِ همان tape_flags؛ ماتریسِ حدی/بی‌داده + سیم‌کشیِ رابطِ بی‌آینه.
    ('dev/tape_smartmoney_v1074.py', 'tape smart-money: two new file filters, one canonical judge'),
    # TREND-FIXTURES: سه جامعۀ ساختگی (HH/HL، LH/LL، برابر) ⇒ رأیِ چارت ص ۲؛
    # ادعای محوری: روزانۀ صعودی وتوی هفتگی را نمی‌شکند؛ na ⇒ UNKNOWN نه REJECT.
    ('dev/fts_trend_fixtures_v1075.py', 'fts trend fixtures: weekly gate beats daily setup'),
    # TSETMC-P0: سه P0ِ لایۀ داده — ارزشِ مبدأ‌محورِ حقیقی/حقوقی با اولویتِ
    # مبدأ و fallbackِ سالم، رویدادهایِ شرکتیِ منتشرشده، و وضعیت/تعلیق/نظارت/
    # پیام. چکِ ضدِ نشت: هیچ‌کدام به فیلتر/گیت/طبقۀ روند وصل نشوند.
    ('dev/tsetmc_p0_v1076.py', 'tsetmc p0: native client values, corporate events, state'),
    # SINGLE-WRITER: دورِ P0 دو بک‌اند هم‌زمان رویِ یک market.db داشت (نسخۀ
    # ماندۀ 1.0.73 ستون‌هایِ تازه را با هر سینک NULL می‌کرد). این گارد همان
    # حالت را می‌گیرد؛ رویِ ماشینِ بدونِ PowerShell بی‌صدا skip می‌شود.
    ('dev/single_writer_guard.py', 'single writer: one backend per market.db'),
    # FUNNEL REGISTRY: هفت فیلترِ docs/*.txt باید همه درِ رجیستریِ قیف باشند،
    # sha256ِ هر منبع با فایلِ رویِ دیسک بخواند، هر backend_impl زنده باشد، و
    # هر عددِ پارامتر درِ متنِ منبعش پیدا شود (کنترلِ منفی: تکانِ یک آستانه
    # ruleset_version را عوض می‌کند). ساعت‌شنی عمداً زنجیرۀ تهی دارد تا هیچ
    # فیلترِ بی‌منبعی برایش اختراع نشود.
    ('dev/funnel_registry_v1.py', 'funnel registry: every txt filter pinned to its source'),
    # FUNNEL ENGINE: داورِ canonical — اشتراکِ ترتیبی، وتوی هفتگی، سه
    # حالتِ بنیادی، استثنایِ برچسب‌دار و رتبۀ تحویل. ۲۲ بندِ مأموریت، همگی
    # با انتظارِ نوشته‌شدۀ بیرونِ موتور.
    ('dev/funnel_engine_v1.py', 'funnel engine: ordered intersection, weekly gate, fund modes'),
    # FUNNEL PRESET DISTINCT: هر Preset باید **خروجِ موتور** را عوض کند، نه فقط
    # عنوانِ دکمه. این گارد تا پیش از این درِ `run_all_tests` ثبت نبود (باگِ P0:
    # «تغییر Preset جدول را عوض نمی‌کند» سبز می‌ماند) و فقط رجیستری را می‌خواند؛
    # حالا خروجیِ واقعیِ `FE.evaluate` رویِ fixture هم مقابله می‌شود، پس هیچ
    # presetی نمی‌تواند بی‌صدا کپیِ دیگری شود.
    ('dev/funnel_preset_distinct_v1.py', 'funnel presets: distinct chains, gates AND distinct engine output'),
    # UNIVERSE LIVE: طبقه‌بندیِ وضعیتِ معاملاتی (معاملۀ انجام‌شده ≠ تغییرِ دفتر)،
    # یکی‌کردنِ ردیفِ تکراریِ هم‌نام و کهنگی از سنِ خودِ بدنهٔ تابلو. ثبت نشدنی
    # بود و درِ `run_all_tests` نبود؛ endpointِ `/api/universe/live` هم از
    # `api/funnel.py` به `api/market.py` رفت (یکِ ردیاب، یکِ راننده).
    ('dev/market_universe_v1.py', 'live trading-status universe: executed vs quoted, dedupe, staleness'),
    ('dev/user_watchlist_v1.py', 'user watchlist CRUD: get() on a missing row, upsert identity, cap layering'),
    ('dev/fts_trend_pit_v1.py', 'trend point-in-time: Saturday week bucket, closed-week immutability, no cache-key lookahead'),
    # SARKHATI Stage D: قراردادِ BrokerAdapter. هیچ کارگزاریِ واقعی صدا زده
    # نمی‌شود؛ بدلِ ما هم timeout را «پذیرفته‌شده درِ سرور، گم‌شده درِ کلاینت»
    # می‌سازد تا مسیرِ UNKNOWN_RESULT → RECONCILE و تله‌یِ retryِ کور قابلِ اثبات
    # باشند. کنترلِ منفی: SloppyAdapter (retry + fallback به ISINِ «زر» + صفرِ
    # جعلیِ صف) باید درِ همین سوئیت بیفتد، وگرنه سوئیت کور است.
    ('dev/execution_contract_v1.py', 'sarkhati: broker contract on mock, no blind retry'),
    # SARKHATI Stage H: موتورِ زمان. آفستِ NTP چندنمونه‌ای با *حالتِ* کیفیت
    # (TRUSTED/DEGRADED/UNTRUSTED/UNAVAILABLE) و fail-safe بی‌صدا رد نمی‌شود؛
    # مهلت رویِ monotonic است پس پرشِ ساعتِ دیواری dispatch را جابه‌جا نمی‌کند؛
    # یک‌طرفه = نصفِ RTT نه کلِ آن (اشتباهِ مرجعِ Rust، §۷-ج). سرورِ SNTP بدل
    # رویِ 127.0.0.1 است — هیچ درخواستِ واقعی به بیرون نمی‌رود.
    ('dev/execution_timing_v1.py', 'sarkhati: monotonic-anchored scheduler + clock quality'),
    # SARKHATI Stage I (ابزار): سنجشِ تأخیر فاز‌به‌فاز رویِ 127.0.0.1 — نه یک
    # HEAD به ریشۀِ میزبان (§۷-ج). warmup و پرت حذف می‌شوند و نامشان ثبت
    # می‌شود؛ بی‌نمونۀِ کافی برآوردِ یک‌طرفه None است نه صفر؛ و ریاضِ صدک از
    # execution_timing وارد می‌شود تا دو منبعِ حقیقت نداشته باشیم.
    ('dev/execution_latency_v1.py', 'sarkhati: phased latency probe, no fabricated estimate'),
    # SARKHATI Stage J: ارکستراسیونِ اجرا. dry-run پیش‌فرض است و درِ آن هیچ
    # submit_order صدا زده نمی‌شود؛ بعدِ timeout تنها مسیرِ مجاز reconcile است
    # (ارسالِ دوبل از لایۀِ adapter هم DUPLICATE_GUARD می‌خورد و وضعیتِ
    # UNKNOWN_RESULT را بازنویسی نمی‌کند)؛ ULTRA بی‌prepare() رد می‌شود و
    # تکرار بی‌تأییدِ صریح یا بی‌سقفِ ارزش/تعداد اجرا نمی‌شود.
    ('dev/execution_service_v1.py', 'sarkhati: dry-run default, reconcile-only after unknown, limits'),
    # گاردِ متنِ فارسی (بیرونِ سرخطی هم لازم است): سه خانۀِ خطا که درِ همین
    # ریپو واقعی دیده شده — نویسهٔ CJK جاافتاده وسطِ واژۀِ فارسی، رقمِ
    # شمارۀِ بخش که بی‌صدا می‌افتد، و ك/ي عربی درِ فایل‌هایِ سرخطی. هر سه
    # سنسور با سمِ --selftest راستی‌آزمایی می‌شوند؛ بیرونِ سرخطی ك/ي عربی
    # فقط شمارشِ اطلاعیه (۳۵۰ سطر، اکثراً املایِ خودِ نمادهایِ تابلو).
    ('dev/persian_glyph_guard.py', 'persian text: no stray CJK, no eaten section digit'),
    # SARKHATI Stage G: خواندنِ وضعیتِ سفارش و جایِ صف. سه معنایِ متفاوتِ
    # «نمی‌دانیم» (بی‌capability / پاسخِ خالی / ردیفِ بی‌مقدار) را از صفر
    # جدا می‌گذارد، و ثابت می‌کند هیچ refresh یا پایشی سفارشِ تازه
    # نمی‌سازد.
    ('dev/execution_queue_v1.py', 'sarkhati: order state + queue position, never a fabricated zero'),
    # BOARD-HIST-CACHE: دو پنجرۀ روزانه به جدولِ مادی تبدیل شده‌اند. این گارد
    # سطر‌به‌سطر ثابت می‌کند نتیجه عوض نشده و بی‌اعتباری هم درست کار می‌کند
    # (تیکِ نشستِ جاری کش را نمی‌سوزاند؛ تصحیحِ نشستِ پیشین می‌سوزاند).
    ('dev/board_hist_cache_v1056.py', 'board history windows: materialized == inline'),
    # HOT-STATE (کار #73): حالتِ داغِ تابلو در RAM. سه چیز را می‌بندد که یک
    # ویرایشِ بی‌دقت می‌شکند: امضا فقط ستون‌هایِ *نوشته‌شدنیِ همان نوبت* را
    # می‌بیند، بدنۀ RAM-overlay سطر‌به‌سطر همان بدنۀ SQLite است، و
    # /api/market/delta یا exact است یا صریح `full` — هیچ‌وقت نصفه.
    ('dev/market_hot_state_v1077.py', 'hot state: field-aware diff, RAM==SQL board, honest delta'),
    # Stage-2 «در یک نگاه»: سه قیمتِ روزانه از ستونِ واقعی، بی‌نشتِ عمق درِ تابلو،
    # و تطابقِ نماد درِ /api/order-book (نبودِ مقدار ⇒ حذفِ کلید، نه صفر/جایگزین).
    ('dev/sidebar_market_fields_v1082.py', 'sidebar Stage-2: p_first/p_max/p_min from real cols, lazy order-book binding'),
    # #119 + #120 (مانیتورینگِ زندهٔ ۱۴۰۵-۰۷-۰۴): روزِ client_type باید روزِ
    # نشستِ معامله‌شده باشد، پنجرۀِ بازار یک‌جا تعریف شود، و «نبودنِ داده»
    # دماسنج را «نامساعد» نکند.
    ('dev/client_type_date_v1034.py',
                                     'board freshness: session day + abstaining market pulse'),
    # PORT-1: وزن از «قیمت × تعداد»، مایگریشنِ افزودنیِ «تعداد»، و پایانِ
    # صفرِ ساختگی در مقایسهٔ ترکیبِ سبد با هدف.
    ('dev/portfolio_weights_v1035.py',
                                     'portfolio weights: value-based + no fake zero'),
    # BOOT-1 (۱۴۰۵-۰۷-۱۷): اولین اجرا باید پیشرفت نشان دهد. دو مسیرِ ساختِ
    # market.db (دریافت از Release، استخراجِ lzma) عددِ واقعی می‌دهند و صفحۀ
    # بوتِ فارسی همان‌ها را سرو می‌کند؛ بی‌این گارد «صفحه سفیدِ بی‌خبر» دوباره
    # برمی‌گردد.
    ('dev/boot_page_v1081.py',
                                     'boot page: real download/extract progress, RTL page, handoff + error'),
]

# تست‌هایِ Node (رابطِ جدول بنیادی با DOMِ ساختگی) — اگر node نصب نباشد رد میشوند
JS_SUITES = [
    ('dev/test_fts_v10_ui.js',        'FTS v10 fundamental table UI render (headless)'),
    ('dev/test_fts_settings_ui.js',   'FTS CODAL settings panel: validate + storage + apply'),
]

# پیش از اجرای سوئیتِ Node، fixture ساخته میشود — تا clone تازه (یا CI) بدون
# فایلِ generated هم سبز بماند و «تست به‌خاطر نبودِ داده شکست» رخ ندهد.
FIXTURE_GEN = 'dev/make_fts_ui_fixture.py'


env = dict(os.environ, PYTHONIOENCODING='utf-8')
bad = []


def run(argv, label):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=600, env=env, shell=False)
    except FileNotFoundError:
        print('  SKIP %-40s (%s not found)' % (label, argv[0]))
        return
    except Exception as ex:
        print('  FAIL %-40s (%s)' % (label, str(ex)[:60]))
        bad.append(label)
        return
    txt = (r.stdout or '') + (r.stderr or '')
    n = len(re.findall(r'\bPASS\b', txt))
    f = len(re.findall(r'\bFAIL\b', txt))
    m = re.search(r'(\d+)/(\d+) passed', txt)
    # گاردهای فارسیِ تازه (v1.0.33+) خطۀ «N بررسی سبز، M شکست» می‌دهند؛ بدونِ
    # این، گزارشِ مجموعه «0 pass / 0 fail» چاپ می‌شد و هیچ‌کس نمی‌فهمید چه چیزی
    # واقعاً سبز شده است.
    mf = re.search(r'(\d+) \u0628\u0631\u0631\u0633\u06cc \u0633\u0628\u0632\u060c (\d+) \u0634\u06a9\u0633\u062a', txt)
    mp = re.search(r'(\d+) passed[ ,/]+(\d+) failed', txt)
    if m:
        detail = '%s/%s' % (m.group(1), m.group(2))
    elif mf:
        detail = '%s/%s' % (mf.group(1), int(mf.group(1)) + int(mf.group(2)))
    elif mp:
        detail = '%s/%s' % (mp.group(1), int(mp.group(1)) + int(mp.group(2)))
    else:
        detail = '%d pass / %d fail' % (n, f)
    ok = (r.returncode == 0)
    print('  %s %-40s rc=%s | %s' % ('OK  ' if ok else 'FAIL', label, r.returncode, detail))
    if not ok:
        bad.append(label)
        print('\n'.join('       ' + l for l in txt.strip().split('\n')[-12:])
              .encode('ascii', 'replace').decode('ascii'))


# Data-Lifecycle: برخی سوئیت‌ها آرگومان می‌گیرند (مثلاً --selftest)؛
# script.split() مسیر و آرگومان‌ها را از هم جدا می‌کند.
for script, label in SUITES:
    run([sys.executable] + [a.replace('/', os.sep) for a in script.split()], label)
if os.path.exists(FIXTURE_GEN):
    run([sys.executable, FIXTURE_GEN.replace('/', os.sep)], 'fixture: fts_v10 payloads')
for script, label in JS_SUITES:
    run(['node', script.replace('/', os.sep)], label)

print('\n%s' % ('ALL SUITES PASSED' if not bad else 'FAILED: ' + ', '.join(bad)))
sys.exit(1 if bad else 0)
