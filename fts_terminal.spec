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
        ('codal_control.json', '.'),
        ('watchlist_store.py', '.'),
        ('api', 'api'),
    ] + ([('adb_config.json', '.')] if os.path.exists('adb_config.json') else []),
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
          console=True, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='BorsTerminal_Ultimate')
