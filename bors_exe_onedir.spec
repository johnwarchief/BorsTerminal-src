# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['bors_entry.py'],
    pathex=['C:/Users/PCMOD/Desktop/BorsTerminal'],
    binaries=[],
    datas=[
        ('static', 'static'),
        # v1.0.13: خروجیِ بیلدِ React را هم باندل کن. بدونِ این، app.py
        # _frontend_dist() را پیدا نمی‌کند و SPA با «frontend dist ساخته نشده»
        # پاسخ می‌دهد — یعنی نصبِ تمیز یک پوستهٔ خالی از API است.
        ('frontend/dist', 'frontend/dist'),
        ('app.py', '.'),
        ('bootstrap_first_run.py', '.'),
        ('codal_fetcher.py', '.'),
        ('fts_engine.py', '.'),
        ('fts_thresholds.json', '.'),
        ('test_tsetmc.py', '.'),
    ] + [t for t in (('adb_config.json', '.'), ('codal_control.json', '.'),
                     # v1.0.15: بدونِ این فایل، preflight می‌میرد و
                     # «market.db not found» می‌دهد — یعنی نصبِ تمیز
                     # یک پوستهٔ خالی است. این منبعِ دادهٔ آفلاین است.
                     ('market.db.lzma', '.'), ('market_sync.json', '.'))
         if os.path.exists(t[0])],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
                   'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on',
                   'codal_fetcher', 'app', 'test_tsetmc', 'fts_engine', 'orjson', 'pandas', 'numpy',
                   # v9.8.1: app.py was split verbatim into the api/ package; the
                   # frozen build MUST bundle these or the EXE dies with
                   # ModuleNotFoundError on the first request. api_router()
                   # imports them inside the function body, so PyInstaller's
                   # static import scan cannot see them.
                   'bors_config', 'bors_flags', 'api',
                   # هر ماژولی که api_router() import می‌کند باید اینجا باشد:
                   # import داخلِ بدنهٔ تابع است و اسکنِ استاتیکِ PyInstaller
                   # آن را نمی‌بیند (dev/onedir_contract_v11.py این را چک می‌کند).
                   'api._core', 'api.market', 'api.chart', 'api.selection',
                   'api.watchlist', 'api.fundamental', 'api.market_status',
                   'api.screener', 'api._sync_market', 'api._export',
                   'api._sync_codal', 'api.adb', 'api.notify',
                   'api.update', 'api._pipeline', 'api.engine', 'api.market_index',
                  # v1.0.13: مشاهدهٔ لاگ در UI وقتی کنسول مخفی است (console=False).
                  'api.diagnostics',
                   'pandas._libs.tslibs.np_datetime', 'pandas._libs.tslibs.offsets', 'docx', 'openpyxl', 'reportlab',
                   'lxml', 'lxml.etree', 'click', 'cryptography', 'dateutil', 'websockets', 'packaging',
                   'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont', 'PIL._imaging'],
    excludes=['tkinter', 'matplotlib', 'pytest', 'scipy', 'sympy', 'selenium',
              'setuptools', 'pip',
              'boto3', 'botocore', 's3transfer',
              'watchfiles', 'httptools'],
    noarchive=False,
)
pyz = PYZ(a.pure)

# v1.0.13: آیکونِ واقعی روی فایلِ اجرایی. مسیر باید مطلق باشد تا PyInstaller
# آن را از هر working-directoryی پیدا کند (نسبی رویِ ماشینِ بیلدِ دیگر می‌شکند).
_icon_path = os.path.join(
    os.path.dirname(os.path.abspath(SPEC)), 'assets', 'bors.ico')
if not os.path.isfile(_icon_path):
    _icon_path = None

# v1.0.13: console=False → پنجرهٔ ترمینال باز نمی‌شود. لاگ‌ها به جایِ صفحه
# در یک فایل می‌روند (بوت‌استرپِ زیر آن را تنظیم می‌کند) و در صورتِ نیاز
# از طریقِ منویِ برنامه قابلِ دیدن هستند.
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='BorsTerminal_Ultimate', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False,
          console=False, icon=_icon_path)
col = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='BorsTerminal_Ultimate')
