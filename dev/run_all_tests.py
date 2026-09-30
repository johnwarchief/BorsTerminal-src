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
    ('dev/chart_api_check_v95.py',    'KLineCharts v10 API guard'),
    ('dev/fts_m141_parity_v97.py',    'm141/liquidity parity + anti-N+1'),
    ('dev/adb_resilience_v972.py',    'ADB retry/reconnect + wifi restore'),
    ('dev/confidence_engine_v973.py', 'triple-confirmation confidence engine'),
    ('dev/soft_warnings_v974.py',     'soft pass/warn/fail/nodata — no hard vetoes'),
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
    ('dev/fts_chart_engine_v1037.py', 'chart fib belts and setup markers come from the one server engine, over the current wave'),
    ('dev/repo_hygiene_v97.py',       'repo hygiene / dead-code stays gone'),
    ('dev/test_fts_v10_ladder.py',    'FTS v10 EPS evidence ladder + partial table row'),
    ('dev/test_fts_market_cap.py',    'TSETMC market-cap source of truth + risk filters'),
    # شاخص ۴: حکمِ معافیت/N/A باید بین fts_engine (اسکرینر) و api/fundamental
    # (کارت) یکی باشد — پیش از این این سوئیت اصلاً در SUITES نبود و پاریتیِ
    # اسکرینر/کارت هم کارت را با خودش می‌سنجد (۲۳۱ نماد واگرایی بی‌صدا ماند).
    ('dev/fts_screener_card_parity_v10.py',
                                      'screener<->card parity + ind-4 exemption engine vs card'),
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
    # TA-SCOPE-1 (پرسشِ مالک ۱۴۰۵-۰۷-۰۷: «نبض را کامل با تریدرزآرنا تطبیق بده»):
    # دامنهٔ «کل بازار» = سطرهایِ market0ِ او، نشتِ صکوک/مشارکت/سلف از سطرِ سهام
    # بسته شد، و «ارزش کل بازار»ِ نصفه نه نوشته می‌شود نه خوانده.
    ('dev/pulse_ta_scope_v1063.py',
                                     'pulse scopes match tradersarena + no half-written market total'),
    # TAPE-F / JET-BREAK / HIST-SRC: پنج فیلترِ تابلو عینِ جزوه، و «نبودنِ
    # داده» هیچ‌وقت قبول نیست. پیش از این هیچ سویتی این فرمول‌ها را نمی‌پوشاند.
    ('dev/tape_filters_v1034.py',   'tape filters: five formulas match the notebook'),
    # BOARD-HIST-CACHE: دو پنجرۀ روزانه به جدولِ مادی تبدیل شده‌اند. این گارد
    # سطر‌به‌سطر ثابت می‌کند نتیجه عوض نشده و بی‌اعتباری هم درست کار می‌کند
    # (تیکِ نشستِ جاری کش را نمی‌سوزاند؛ تصحیحِ نشستِ پیشین می‌سوزاند).
    ('dev/board_hist_cache_v1056.py', 'board history windows: materialized == inline'),
    # #119 + #120 (مانیتورینگِ زندهٔ ۱۴۰۵-۰۷-۰۴): روزِ client_type باید روزِ
    # نشستِ معامله‌شده باشد، پنجرۀِ بازار یک‌جا تعریف شود، و «نبودنِ داده»
    # دماسنج را «نامساعد» نکند.
    ('dev/client_type_date_v1034.py',
                                     'board freshness: session day + abstaining market pulse'),
    # PORT-1: وزن از «قیمت × تعداد»، مایگریشنِ افزودنیِ «تعداد»، و پایانِ
    # صفرِ ساختگی در مقایسهٔ ترکیبِ سبد با هدف.
    ('dev/portfolio_weights_v1035.py',
                                     'portfolio weights: value-based + no fake zero'),
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
