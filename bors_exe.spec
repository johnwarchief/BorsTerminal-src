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
        ('test_tsetmc.py', '.'),
        ('adb_config.json', '.'),
        ('codal_control.json', '.'),
        # DB ها از EXE خارج شدند — در کنار exe از ZIP قرار می‌گیرند (EXE کوچک‌تر)
    ],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
                   'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on',
                   'codal_fetcher', 'app', 'pandas', 'numpy',
                   # v9.8.1: app.py was split verbatim into these modules; the
                   # frozen build must bundle them (api_router imports them at
                   # call time, so PyInstaller's static pass may miss some).
                   'bors_config', 'bors_flags', 'api',
                   'api._core', 'api.market', 'api.chart', 'api.selection',
                   'api.watchlist', 'api.fundamental', 'api.market_status',
                   'api.screener', 'api._sync_market', 'api._export',
                   'api._sync_codal', 'api.adb', 'api.notify',
                   'api._pipeline', 'api.engine',
                   'pandas._libs.tslibs.np_datetime', 'pandas._libs.tslibs.offsets'],
    excludes=['tkinter', 'matplotlib', 'pytest', 'scipy', 'sympy'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    [],
    name='BorsTerminal_Ultimate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'vcruntime140_1.dll', 'python3*.dll'],
    console=True,
    icon=None,
)
