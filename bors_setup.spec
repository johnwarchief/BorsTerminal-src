# -*- mode: python ; coding: utf-8 -*-
# BorsTerminal Ultimate - PyInstaller onedir spec (Base repo)
import os
BASE = os.path.abspath(os.path.dirname(SPEC)) if 'SPEC' in locals() else os.getcwd()

# رمزِ نصب‌کننده (gitignore شده، فقط محلی) برای /VERYSILENTِ آپدیتِر. بدون
# این فایل در _MEIPASS، _setup_password() آن را نمی‌یابد و نصبِ خودکار نمی‌تواند
# بدونِ پرسشِ رمز انجام شود.
_pw_file = os.path.join(BASE, 'installer', '.setup_password.iss')
a = Analysis(
    ['bors_entry.py'],
    pathex=[BASE],
    binaries=[],
    datas=[
        ('static', 'static'),
        ('public', 'public'),
        ('frontend/dist', 'frontend/dist'),
        ('app.py', '.'),
        ('bootstrap_first_run.py', '.'),
        ('codal_fetcher.py', '.'),
        ('fts_engine.py', '.'),
        ('mstat_engine.py', '.'),
        ('confidence_engine.py', '.'),
        ('watchlist_store.py', '.'),
        ('notifier.py', '.'),
        ('codal_engine.py', '.'),
        ('bors_config.py', '.'),
        ('bors_flags.py', '.'),
        ('fts_thresholds.json', '.'),
        ('test_tsetmc.py', '.'),
    ] + ([(os.path.join('installer', '.setup_password.iss'), '.')]
         if os.path.exists(_pw_file) else []),
    hiddenimports=[
        'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on',
        'codal_fetcher', 'app', 'test_tsetmc', 'fts_engine', 'mstat_engine',
        'confidence_engine', 'watchlist_store', 'notifier', 'codal_engine',
        'bors_config', 'bors_flags', 'api',
        'api._core', 'api.market', 'api.chart', 'api.selection',
        'api.watchlist', 'api.fundamental', 'api.market_status',
        'api.screener', 'api._sync_market', 'api._export',
        'api._sync_codal', 'api.adb', 'api.notify',
        'api._pipeline', 'api.engine', 'api.market_index',
        'api.update', 'bors_minisign', 'winreg',
        'orjson', 'pandas', 'numpy', 'docx', 'openpyxl', 'reportlab',
        'lxml', 'lxml.etree', 'click', 'cryptography', 'dateutil',
        'websockets', 'packaging',
        'pandas._libs.tslibs.np_datetime', 'pandas._libs.tslibs.offsets',
    ],
    excludes=['tkinter', 'matplotlib', 'pytest', 'scipy', 'sympy', 'selenium',
              'setuptools', 'pip', 'boto3', 'botocore', 's3transfer',
              'watchfiles', 'httptools'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='BorsTerminal_Ultimate', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False,
          console=True, icon=os.path.join(BASE, 'assets', 'bors.ico'))
col = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
              name='BorsTerminal_Ultimate')
