# -*- mode: python ; coding: utf-8 -*-
# fts_terminal.spec -- فاز 7: بسته دسکتاپ FTS Terminal (onedir تمیز)
#
# ساختار خروجی (dist/BorsTerminal_Ultimate/):
#   BorsTerminal_Ultimate.exe          ← لانچر (bors_entry.py): preflight + uvicorn + browser
#   _internal/                         ← پایتون + کتابخانه‌ها + datas
#       frontend/dist/                 ← SPA React (سرو از ریشه توسط app.py)
#       static/calendar/               ← داده رویدادهای نماد (cache.json) -- وابستگی API فعال
#       app.py, api/, bors_config.py   ← بک‌اند
#   market.db.lzma                     ← کنار exe قرار می‌گیرد (نه داخل آن)؛
#                                        اولین اجرا خودکار extract می‌شود (بors_entry preflight)
#
# چرا DB داخل EXE نیست: market.db خام ~98MB است؛ در onefile هر اجرا یک بار
# استخراج کامل می‌شد (کندی چند ده ثانیه‌ای). الگوی lzma-کنار-exe همان
# قرارداد v10 قبل از فاز 7 است و "پوشه داده‌ها به مسیر اجرایی" را برآورده می‌کند.
a = Analysis(
    ['bors_entry.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('frontend/dist', 'frontend/dist'),
        ('static', 'static'),
        ('app.py', '.'),
        ('bootstrap_first_run.py', '.'),
        ('codal_fetcher.py', '.'),
        ('fts_engine.py', '.'),
        ('mstat_engine.py', '.'),
        ('fts_thresholds.json', '.'),
        ('test_tsetmc.py', '.'),
        ('tsetmc_p0_schema.py', '.'),
        ('watchlist_store.py', '.'),
        ('api', 'api'),
        # بستهٔ تصحیحِ نسخه‌دارِ RA365 (factors + raw_ohlc).  بدونِ این entry،
        # نسخهٔ نصب‌شده بسته را نمی‌بیند و تعدیل به زنجیرهٔ قدیم برمی‌گردد.
        ('data/ra365_corrections', 'data/ra365_corrections'),
        # آپدیتِ درون‌برنامه‌ای: bors_minisign در ریشهٔ ریپو است و فقط از داخلِ
        # api.update استفاده می‌شود که خود درونِ تابعِ api_router ایمپورت
        # می‌شود → اسکنِ ایستایِ PyInstaller آن را نمی‌بیند، پس صریحاً باندل
        # می‌کنیم تا نصبِ سایلنتِ آپدیت در نسخهٔ باندل‌شده کار کند.
        ('bors_minisign.py', '.'),
    ] + [t for t in (('adb_config.json', '.'), ('codal_control.json', '.'),
                    # setup.pw: رمزِ نصب‌کنندهٔ Inno برای /VERYSILENT (gitignored؛
                    # فقط اگر موجود باشد باندل می‌شود — بدون آن آپدیت به /SILENT
                    # تنزل می‌کند و کاربر یک‌بار رمز را وارد می‌کند).
                    # مقصدِ '.' یعنی فایلِ .setup_password.iss در _internal/
                    # می‌نشیند — که _setup_password() دقیقاً همان نام را می‌گردد
                    # (نکته: عنصر دومِ datas یک پوشهٔ مقصد است، نه نام فایل).
                    ('installer/.setup_password.iss', '.'))
         if os.path.exists(t[0])],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
                   'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on',
                   'codal_fetcher', 'app', 'test_tsetmc', 'fts_engine', 'orjson',
                   'adjustment_corrections',
                   'pandas', 'numpy', 'sqlite3',
                   # v9.8.1: app.py was split verbatim into the api/ package; the
                   # frozen build MUST bundle these or the EXE dies with
                   # ModuleNotFoundError on the first request. api_router()
                   # imports them inside the function body, so PyInstaller's
                   # static import scan cannot see them.
                   'bors_config', 'bors_flags', 'api',
                   # کارِ #73 قدمِ ۳: `price_basis` تنها نقطۀ انتخابِ ستونِ قیمت است و
                   # api.chart / api.screener / api.market_index / confidence_engine آن را
                   # سطح-بال import می‌کنند. مثل tape_flags صریح فهرست می‌شود: نبودنش
                   # EXE را روی اولین درخواستِ چارت می‌کشد.
                   'price_basis', 'candle_contract',
                   # مأموریتِ ماژور (۱۴۰۵-۰۷-۲۷): `major_swings` درجۀبندیِ سقف/کفِ
                   # ماژور است و api/chart آن را سطح-بال import می‌کند؛ مثلِ دو
                   # ماژولِ بالا صریح فهرست می‌شود — نبودنش EXE را رویِ اولین
                   # درخواستِ چارت/قیف می‌کشد.
                   'major_swings',
                   # دورِ قیف (1405-07-16): `funnel_registry` تک‌منبعِ فیلترها و
                   # presetهاست و api/funnel آن را سطح-بال import می‌کند؛ مثلِ بقیۀ
                   # ماژول‌هایِ ریشه صریح فهرست می‌شود وگرنه EXE رویِ اولین درخواستِ
                   # قیف ModuleNotFoundError می‌دهد.
                   'funnel_registry', 'funnel_engine', 'funnel_tech_scan',
                   # Universe زنده (وضعیت معاملاتیِ نماد): api/funnel آن را سطح-بال
                   # import می‌کند و خودِ api.funnel درِ function-body وارد می‌شود؛
                   # نبودنش EXE را روی اولین /api/universe/live می‌کشد.
                   'market_universe',
                   # کارِ #73 (بخشِ بنیادی، ۱۴۰۵-۰۷-۱۰): `codal_periods` تنها تعریفِ
                   # «دورۀ گزارش» است و fts_engine / api.fundamental / api.screener /
                   # codal_fetcher سطح-بال importش می‌کنند. نبودنش EXE را رویِ اولین
                   # درخواستِ بنیادی می‌کشد.
                   'codal_periods',
                   # مرحلۀ ۴ مأموریت بنیادی (۱۴۰۵-۰۷-۲۳): `codal_units` تنها
                   # تعریفِ «واحدِ پول» است؛ fts_engine (مقیاسِ هر ردیف),
                   # codal_fetcher (`_classify_unit`) و api.fundamental (ضریب‌های
                   # نمایش) سطح-بال importش می‌کنند. بی‌این خط EXE رویِ اولین
                   # درخواستِ بنیادی ModuleNotFoundError می‌دهد.
                   'codal_units',
                   # مأموریت «خطِ دریافت خودکار کدال» (۱۴۰۵-۰۷-۲۴):
                   # `codal_pipeline` صف/checkpoint/قفلِ worker است و `app.py`
                   # (حلقۀ استارتاپ) و `api/_sync_codal.py` (دستۀ چرخه و سلامت)
                   # سطح-بال importش می‌کنند؛ بی‌این خط EXE رویِ اولین چرخه
                   # ModuleNotFoundError می‌دهد.
                   'codal_pipeline',
                   # مرحلۀ ۱.۲ مأموریت بنیادی (۱۴۰۵-۰۷-۲۲): `symbol_identity` تنها
                   # تعریفِ «این ردیف مالکِ کدام ابزار است» است و fts_engine /
                   # api._core / api.fundamental / api.chart / api.screener و
                   # confidence_engine آن را صدا می‌زنند. بی‌این خط EXE رویِ اولین
                   # درخواستِ بنیادی ModuleNotFoundError می‌دهد (همان قاعدۀ
                   # AGENTS.md برایِ هر ماژولِ ریشه).
                   'symbol_identity',
                   # بند ۲ مأموریت (1405-07-20): `client_split` تنها تعریفِ
                   # درصدِ حقیقی/حقوقی است و api/market.py + mstat_engine آن را
                   # سطح-بال import می‌کنند؛ نبودنش EXE را رویِ اولین درخواستِ
                   # تابلو می‌کشد (همان الگوی price_basis/codal_periods).
                   'client_split',
                   # بند ۵ مأموریت (1405-07-20): `market_phase` تنها تعریفِ
                   # مرحلِ جلسه است و mstat_engine آن را import می‌کند؛ مثلِ
                   # بقیۀ ماژول‌هایِ ریشه صریح فهرست می‌شود.                       
                   'market_phase',
                   # بند ۶ مأموریت (1405-07-20): `notifications` تنها طبقه‌بندِ
                   # اطلاعیه‌هاست و api/notifications آن را سطح-بال import
                   # می‌کند؛ نبودنش EXE را رویِ اولین درخواستِ مرکزِ اعلان
                   # می‌کشد (همان قاعدۀ AGENTS.md برایِ هر ماژولِ ریشه).
                   'notifications',
                   # دورِ P0 (1405-07-13): `tsetmc_p0_schema` تک‌منبعِ DDL جدول‌هایِ
                   # canonical است و هم از test_tsetmc و هم از mstat_engine.
                   # ensure_schema خوانده می‌شود؛ نبودش درِ EXE یعنی 500 رویِ هر
                   # درخواستِ تابلو.
                   'tsetmc_p0_schema',
                   # پنج فیلترِ تابلو از api.market به ماژولِ خالصِ tape_flags
                   # منتقل شد تا نگهبانِ dev/tape_filters_v1034.py همان کد را
                   # بیازماید. ایمپورتش سطح-بال است اما صریح فهرست می‌شود:
                   # نبودنش EXE را روی اولین درخواست /api/market می‌کشد.
                   'tape_flags',
                   # سابقۀ ماندگارِ هفت فیلتر (مأموریتِ پروندۀ نماد، ۱۴۰۵-۰۷-۲۱):
                   # api/market.py آن را سطح-بال import می‌کند و هر دو نوشتنِ
                   # تابلو و خواندنِ /api/tape-history از همین ماژول می‌گذرند؛
                   # نبودنش EXE را رویِ اولین درخواستِ تابلو می‌کشد (همان قاعدۀ
                   # AGENTS.md برایِ هر ماژولِ ریشه).
                   'tape_flag_history',
                   # حالتِ داغِ تابلو (کار #73): api.market و test_tsetmc آن را import
                   # می‌کنند (test_tsetmc درِ بدنهٔ تابع، پس ایستیک‌اسکن نمی‌بیند).
                   # نبودنش EXE را روی اولین تیکِ زنده می‌کشد.
                   'market_state',
                   # دورِ ادغامِ System 2 (۱۴۰۵-۰۷-۲۸): سه ماژولِ ریشۀ تازه که هر
                   # کدام سطح-بال ازِ دروازۀ API خوانده می‌شوند —
                   # `adjustment_engine` و `corporate_ledger` از `api/chart.py:11,13`
                   # و `mstat_panels` از `api/market_status.py:18`. نبودنِ هر سه
                   # خودِ import آن دروازۀ API را می‌کشد، یعنی EXE روی اولین
                   # /api/chart یا /api/market-status می‌میرد. ایستیک‌اسکن احتمالاً
                   # پیدایشان می‌کند، ولی قاعدۀ مخزن این است: چیزی که درِ بستهٔ
                   # نهایی کشنده است، به حدسِ اسکن سپرده نشود.
                   'adjustment_engine', 'corporate_ledger', 'mstat_panels',
                   'api._core', 'api.market', 'api.chart', 'api.selection',
                   'api.watchlist', 'api.fundamental', 'api.market_status',
                   'api.screener',
                   # دورِ قیف: `api_router` ماژولِ funnel را هم درِ بدنهٔ تابع import
                   # می‌کند (api/__init__.py:13)، پس ایستیک‌اسکن آن را نمی‌بیند و
                   # ماژول درِ PYZ نبود — EXE رویِ اولین /api/funnel
                   # ModuleNotFoundError می‌داد. گاردِ dev/onedir_contract_v11.py
                   # همین را گرفت.
                   'api.funnel',
                   # بند ۶ مأموریت (1405-07-20): `api_router` مرکزِ اعلان را هم
                   # درِ بدنهٔ تابع import می‌کند (api/__init__.py)؛ بی‌این خط
                   # EXE رویِ اولین /api/notifications/* می‌شکند — همان چیزی که
                   # گاردِ dev/onedir_contract_v11.py درِ همین دور گرفت.
                   'api.notifications',
                   'api._sync_market', 'api._export',
                   'api._sync_codal', 'api.adb', 'api.notify',
                   'api._pipeline', 'api.engine', 'watchlist_store',
                   # api/__init__.py:12 از api_router دو ماژولِ دیگر را هم import
                   # می‌کند؛ تا حالا فقط به‌عنوان فایلِ کنارِ _internal روی دیسک
                   # بودند و در آرشیوِ PYZ نیستند. اگر مسیرِ import هرگز به دیسک
                   # نرسد، EXE با ModuleNotFoundError می‌میرد.
                   'api.market_index', 'api.diagnostics',
                   # دروازۀ اجرای سفارش (مأموریت ۱۴۰۵-۰۷-۲۳، بند ۵): مثلِ بقیه درِ
                   # بدنهٔ `api_router` ایمپورت می‌شود (api/__init__.py:12) و
                   # ایستیک‌اسکن آن را نمی‌بیند. بی‌این خط EXE روی اولین
                   # /api/execution/status می‌شکند — همان مسیرِی که
                   # frontend/src/features/portfolio/lib/orderClient.ts:147 صدا می‌زند.
                   # خودِ execution_contract/mock/service/timing/latency/ledger در
                   # سرِ api/execution.py سطح-بال import‌اند، پس اسکن ایستا می‌بیندشان.
                   'api.execution',
                   # آداپتورِ EasyTrader (مأموریتِ ۱۴۰۵-۰۷-۲۴): سطح-بال است و اسکن
                   # ایستا باید پیدایش کند — ولی قاعدۀ مخزن این است که چیزی که
                   # درِ EXE کشنده است، به حدسِ اسکن سپرده نشود. بی‌این خط، بیلدِ
                   # منجمد رویِ اولین /api/execution/status با ModuleNotFoundError
                   # می‌میرد و گاردِ HTTPِ محلی هیچ‌وقت این را نمی‌بیند.
                   'execution_easytrader',
                   'execution_connect',
                   # تنظیمِ اتصال (مأموریتِ ۱۴۰۵-۰۷-۲۹): درِ بدنهٔ تابع import می‌شود
                   # تا انتخابِ آداپتور از خودِ برنامه هم ممکن باشد؛ بی‌این خط
                   # بیلدِ منجمد رویِ اولین /api/execution/status می‌میرد.
                   'execution_settings',
                   # دروازۀ ربات (مأموریتِ ۱۴۰۵-۰۷-۲۴، فاز ۳): مثلِ بقیۀ api/*
                   # درِ بدنهٔ `api_router()` ایمپورت می‌شود، پس اسکن ایستا
                   # نمی‌بیندش؛ بی‌این خط هر /api/bot/* درِ EXE روی 404 می‌ماند.
                   # سه ماژولِ بعدی سطح‌بالِ خودِ api/bot.py‌اند و اسکن باید
                   # پیدایشان کند — اینجا هم فهرست شده‌اند چون قاعدۀ مخزن این
                   # است: چیزی که درِ بستهٔ نهایی کشنده است، به حدس سپرده نشود.
                   'api.bot', 'bot_signals', 'paper_trading', 'trade_sim',
                   'backtest_engine',
                   # مرحلۀ ۲ دورِ تطبیقِ دوم: `/api/structure3` موتورِ سوم را به‌عنوان
                   # رابطِ بی‌رأی منتشر می‌کند و `structure_engine3` را سطح-بال import
                   # می‌کند؛ `api_router` هم ماژول را درِ بدنهٔ تابع import می‌کند، پس
                   # هر دو صریح فهرست می‌شوند (گاردِ dev/onedir_contract_v11.py).
                   'api.structure3', 'structure_engine3',
                   # پنجرهٔ مستقلِ بومی (Edge WebView2): pywebview روی ویندوز به
                   # pythonnet/clr نیاز دارد. نبودشان کشنده نیست — bors_entry
                   # عمداً به پنجرهٔ مرورگر برمی‌گردد — ولی بودنشان همان پنجرهٔ
                   # بومیِ از پیش تست‌شده را تضمین می‌کند.
                   'webview', 'webview.platforms.edgechromium', 'webview.platforms.win32',
                   'clr', 'pythonnet', 'clr_loader',
                   # آپدیتِ درون‌برنامه‌ای: مثلِ بقیه درونِ خودِ api_router
                   # ایمپورت می‌شود و اسکنِ ایستا آن را نمی‌بیند.
                   'api.update', 'bors_minisign',
                   'pandas._libs.tslibs.np_datetime', 'pandas._libs.tslibs.offsets',
                   'docx', 'openpyxl', 'reportlab',
                   'lxml', 'lxml.etree', 'click', 'cryptography', 'dateutil',
                   'websockets', 'packaging', 'watchfiles',
                   'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont', 'PIL._imaging'],
    excludes=['tkinter', 'matplotlib', 'pytest', 'scipy', 'sympy', 'selenium',
              'setuptools', 'pip',
              'boto3', 'botocore', 's3transfer',
              'camoufox', 'playwright',
              'engineio', 'socketio',
              # هوکِ pywebview در PyInstaller همهٔ بک‌ندهایِ گرافیکی را جمع می‌کند،
              # نه فقط همان که رویِ ویندوز استفاده می‌شود: PySide6 به‌تنهایی ۴۴ مگ
              # (از آن ۲۰ مگ opengl32sw.dll) و jedi+parso ۲۳ مگ به _internal راه
              # می‌دادند. بک‌اندِ واقعیِ این برنامه winforms/edgechromium +
              # pythonnet است (در hiddenimports صریح listed شده) و هیچ کدِ پروژه
              # Qt یا IPython را import نمی‌کند. حجمِ نصاب و اندازهٔ پچِ دلتا
              # مستقیماً از همین‌جا کم می‌شود.
              'PySide6', 'PySide2', 'PyQt5', 'PyQt6', 'PyQt4',
              'jedi', 'parso', 'IPython', 'prompt_toolkit'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='BorsTerminal_Ultimate', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False,
          # console=False: پنجرهٔ کنسولِ خالی حذف. بی‌خطر است چون bors_entry._setup_streams()
          # از v1.0.13 هر stdout/stderr را به logs/bors.log می‌بَرَد (و در نبودِ نوشتن به
          # _Null)، پس None‌شدنِ جریان‌ها هیچ print فارسی‌ را نمی‌شکند. با BORS_SHOW_CONSOLE=1
          # در محیط، همان بیلد کنسول‌دارِ دیباگ می‌شود.
          console=False, icon='assets/bors.ico')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='BorsTerminal_Ultimate')
