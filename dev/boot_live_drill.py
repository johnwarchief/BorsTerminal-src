# -*- coding: utf-8 -*-
"""رانندۀ زندهٔ صفحۀ بوت — برایِ `_audit/ws13_boot_page.mts`.

دو حالت:

  --mode real        : همان مسیرِ لانچر (`_serve_with_boot`) با اپِ واقعیِ
                       ریپو روی پورتی که --app-port می‌دهد. پنجرهٔ واقعی
                       باز نمی‌شود (stub)، فقط URLها ثبت می‌شوند.
  --mode synthetic   : پیشرفتِ *واقعاً* سنگین: market.db.lzmaِ ~۳۰ مگابایتی
                       در tempfile و استخراجِ واقعی با گزارشِ درصد.

خطوطِ stdout (پروب این‌ها را می‌خواند):
  BOOT_URL=http://127.0.0.1:<port>/
  APP_PORT=<port>
  RESULT=<serving|preflight-failed|...>
"""
import argparse
import os
import sys

os.environ['BORS_SHOW_CONSOLE'] = '1'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bors_entry as BE          # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('real', 'synthetic'), default='real')
    ap.add_argument('--app-port', type=int, default=8021)
    args = ap.parse_args()

    opened = []
    BE.open_native_window = lambda url: (opened.append(url), False)[1]
    BE.open_app_window = lambda url: (opened.append(url), False)[1]

    boot = BE._start_boot_server()
    if boot is None:
        print('BOOT_FAIL=server could not bind', flush=True)
        return 1
    srv, boot_port = boot
    print('BOOT_URL=http://127.0.0.1:%d/' % boot_port, flush=True)
    print('APP_PORT=%d' % args.app_port, flush=True)

    out = {}
    if args.mode == 'real':
        th = __import__('threading').Thread(target=BE._bootstrap_worker,
                                            args=(args.app_port, out), daemon=True)
    else:
        th = __import__('threading').Thread(target=_synthetic_worker,
                                            args=(args.app_port, out), daemon=True)
    th.start()
    # صفحۀ بوت تا بستنِ این پروسه سرو می‌ماند (Ctrl+C یا taskkillِ PIDِ خودش).
    try:
        while not out.get('result'):
            __import__('time').sleep(0.2)
    except KeyboardInterrupt:
        pass
    print('RESULT=%s' % out.get('result'), flush=True)
    print('WINDOW_URLS=%s' % ','.join(opened), flush=True)
    try:
        while True:
            __import__('time').sleep(3600)
    except KeyboardInterrupt:
        return 0


def _synthetic_worker(app_port, out):
    """استخراجِ واقعیِ یک baselineِ ~۳۰ مگابایتی، با همان callbackِ لانچر."""
    import lzma
    import os as _os
    import shutil
    import sqlite3
    import tempfile
    import time

    import bors_config

    scratch = tempfile.mkdtemp(prefix='bors_boot_drill_')
    try:
        db_tmp = _os.path.join(scratch, 'seed.db')
        c = sqlite3.connect(db_tmp)
        c.execute('CREATE TABLE instruments (symbol TEXT PRIMARY KEY, name TEXT)')
        c.execute('CREATE TABLE daily_prices (symbol TEXT, d_even TEXT, '
                  'PRIMARY KEY (symbol, d_even))')
        c.execute('CREATE TABLE financial_statements (symbol TEXT PRIMARY KEY)')
        c.execute('CREATE TABLE filler (id INTEGER PRIMARY KEY, blob BLOB)')
        step = 0
        while step < (30 << 20):
            c.execute('INSERT INTO filler (blob) VALUES (?)', (_os.urandom(1 << 18),))
            step += 1 << 18
        c.commit()
        c.close()
        raw = open(db_tmp, 'rb').read()
        _os.remove(db_tmp)
        packed = _os.path.join(scratch, 'market.db.lzma')
        open(packed, 'wb').write(lzma.compress(raw))
        print('SEED_MB=%.1f' % (_os.path.getsize(packed) / 1048576.0), flush=True)

        work = _os.path.join(scratch, 'data')
        _os.makedirs(work, exist_ok=True)
        bors_config._SRC_DIR = work
        bors_config.WORK_DIR = work
        bors_config.DB_PATH = _os.path.join(work, 'market.db')
        t0 = time.time()
        db = bors_config.ensure_market_db(progress=BE._boot_progress)
        print('EXTRACT_S=%.1f' % (time.time() - t0), flush=True)
        if not db or not _os.path.exists(db):
            BE._boot_fail('استخراج نشد (drill)')
            out['result'] = 'extract-failed'
            return
        # در این حالت اپِ واقعی بالا نمی‌آید، پس آدرسی برایِ redirect نمی‌دهیم؛
        # probe فقط حرکتِ نوار و ۱۰۰٪ شدنش را می‌سنجد.
        BE._boot_update(phase='extract', pct=100, detail='')
        out['result'] = 'extracted'
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
