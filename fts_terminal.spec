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
        ('watchlist_store.py', '.'),
        ('api', 'api'),
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
                   'pandas', 'numpy', 'sqlite3',
                   # v9.8.1: app.py was split verbatim into the api/ package; the
                   # frozen build MUST bundle these or the EXE dies with
                   # ModuleNotFoundError on the first request. api_router()
                   # imports them inside the function body, so PyInstaller's
                   # static import scan cannot see them.
                   'bors_config', 'bors_flags', 'api',
                   'api._core', 'api.market', 'api.chart', 'api.selection',
                   'api.watchlist', 'api.fundamental', 'api.market_status',
                   'api.screener', 'api._sync_market', 'api._export',
                   'api._sync_codal', 'api.adb', 'api.notify',
                   'api._pipeline', 'api.engine', 'watchlist_store',
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
              'engineio', 'socketio'],
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
