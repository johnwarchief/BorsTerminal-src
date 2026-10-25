# -*- mode: python ; coding: utf-8 -*-
# M2 packaged sidecar (onedir). Run from the repository root:
#   .venv/Scripts/python.exe -m PyInstaller --noconfirm --clean \
#     --distpath prototypes/tinyjs-m2/packaging/build/dist \
#     --workpath prototypes/tinyjs-m2/packaging/build/work \
#     prototypes/tinyjs-m2/packaging/m2_sidecar.spec
# The seed files market.db.lzma and market.db.baseline are copied next to
# BorsTerminalSidecar.exe after the build; they are not baked into _internal.
import os
BASE = os.getcwd()
ENTRY = os.path.join(BASE, 'prototypes', 'tinyjs-m2', 'packaging', 'm2_sidecar.py')

a = Analysis(
    [ENTRY],
    pathex=[BASE],
    binaries=[],
    datas=[
        (os.path.join(BASE, 'static'), 'static'),
        (os.path.join(BASE, 'frontend', 'dist'), 'frontend/dist'),
        (os.path.join(BASE, 'app.py'), '.'),
        (os.path.join(BASE, 'bootstrap_first_run.py'), '.'),
        (os.path.join(BASE, 'codal_fetcher.py'), '.'),
        (os.path.join(BASE, 'fts_engine.py'), '.'),
        (os.path.join(BASE, 'mstat_engine.py'), '.'),
        (os.path.join(BASE, 'confidence_engine.py'), '.'),
        (os.path.join(BASE, 'watchlist_store.py'), '.'),
        (os.path.join(BASE, 'notifier.py'), '.'),
        (os.path.join(BASE, 'codal_engine.py'), '.'),
        (os.path.join(BASE, 'bors_config.py'), '.'),
        (os.path.join(BASE, 'bors_flags.py'), '.'),
        (os.path.join(BASE, 'fts_thresholds.json'), '.'),
        (os.path.join(BASE, 'test_tsetmc.py'), '.'),
    ],
    hiddenimports=[
        'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on',
        'codal_fetcher', 'app', 'test_tsetmc', 'fts_engine', 'mstat_engine',
        'codal_pipeline', 'confidence_engine', 'watchlist_store', 'notifier',
        'codal_engine', 'bors_config', 'bors_flags', 'api',
        'startup_trace',
        'api._core', 'api.market', 'api.chart', 'api.selection',
        'api.watchlist', 'api.fundamental', 'api.market_status',
        'api.screener', 'api._sync_market', 'api._export',
        'api._sync_codal', 'api.adb', 'api.notify',
        'api._pipeline', 'api.engine', 'api.market_index',
        'api.execution', 'execution_easytrader', 'execution_settings',
        'api.bot', 'bot_signals', 'paper_trading', 'trade_sim', 'backtest_engine',
        'api.update', 'bors_minisign', 'winreg',
        'orjson', 'pandas', 'numpy', 'docx', 'openpyxl', 'reportlab',
        'lxml', 'lxml.etree', 'click', 'cryptography', 'dateutil',
        'websockets', 'packaging',
        'pandas._libs.tslibs.np_datetime', 'pandas._libs.tslibs.offsets',
    ],
    excludes=['tkinter', 'matplotlib', 'pytest', 'scipy', 'sympy', 'selenium',
              'setuptools', 'pip', 'boto3', 'botocore', 's3transfer',
              'watchfiles', 'httptools',
              'webview', 'clr', 'pythonnet', 'clr_loader'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='BorsTerminalSidecar', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=True)
col = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
              name='BorsTerminalSidecar')
