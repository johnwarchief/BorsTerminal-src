# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['bors_entry.py'],
    pathex=['C:/Users/PCMOD/Desktop/BorsTerminal_Ultimate'],
    binaries=[],
    datas=[
        ('static', 'static'),
        ('app.py', '.'),
        ('bootstrap_first_run.py', '.'),
        ('codal_fetcher.py', '.'),
        ('fts_engine.py', '.'),
        ('fts_thresholds.json', '.'),
        ('test_tsetmc.py', '.'),
    ] + [t for t in (('adb_config.json', '.'), ('codal_control.json', '.'))
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
                   'api._core', 'api.market', 'api.chart', 'api.selection',
                   'api.watchlist', 'api.fundamental', 'api.market_status',
                   'api.screener', 'api._sync_market', 'api._export',
                   'api._sync_codal', 'api.adb', 'api.notify',
                   'api._pipeline', 'api.engine',
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
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='BorsTerminal_Ultimate', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False,
          console=True, icon=None)
col = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='BorsTerminal_Ultimate')
