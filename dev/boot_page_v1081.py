# -*- coding: utf-8 -*-
"""گاردمانِ صفحۀ بوت (v1.0.81): اولین اجرا باید پیشرفتِ واقعی نشان دهد.

سه چیز را با هم می‌سنجد، همه با دادهٔ جعلیِ کوچک و بی‌دست‌زدنِ market.dbِ ریپو:

۱) مسیرِ دریافت: `bors_config._download_market_db_lzma` از یک سرورِ محلی —
   گزارشِ پیشرفت با شمارِ درست، و ردّ کردنِ فایلِ با اثرانگشتِ غلط.
۲) مسیرِ استخراج: `ensure_market_db` روی یک market.db.lzmaِ مینیاتوری در
   پوشهٔ موقت — phases، درصدِ ۰ تا ۱۰۰، و ساختِ فایلِ سالم.
۳) خودِ صفحۀ بوت: HTTPِ واقعی — HTMLِ RTL، JSONِ `/boot-status`، درصد،
   حالتِ آماده/تسلیمِ آدرس، و حالتِ خطا.

اجرا: `python dev/boot_page_v1081.py`  (هیچ پروسهٔ بیرونی را نمی‌کشد،
هیچ فایلی بیرونِ tempfile نمی‌سازد.)
"""
import http.server
import json
import lzma
import os
import socket
import sqlite3
import sys
import tempfile
import threading
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
# bors_entry درِ import خودش stdout را به logs/bors.log می‌بَرَد؛ با این متغیر
# محیطی همان stdout می‌ماند و خروجیِ این گارد رویِ صفحه خوانده می‌شود.
os.environ['BORS_SHOW_CONSOLE'] = '1'

PASS = 0
FAIL = []


def ck(name, cond, extra=''):
    global PASS
    if cond:
        PASS += 1
        print('  [OK]   ' + name)
    else:
        FAIL.append(name)
        print('  [FAIL] ' + name + ('  <- ' + extra if extra else ''))


def _free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _mini_db_lzma(path, rows=200, noise=0):
    """یک market.db.lzmaِ کوچک با جدول‌هایِ لازمِ baseline.

    noise بایتِ بی‌فشرده (urandom) به جدولِ پرکننده می‌افزاید تا فایلِ
    فشرده چند مگابایت شود: با فایلِ چند-کیلوبایتی LZMAFile همه‌چیز در یک
    بلاک می‌خواند و «چند مرحلهٔ پیشرفت» هرگز سنجیده نمی‌شد.
    """
    import bors_config
    tmp = path + '.db'
    c = sqlite3.connect(tmp)
    c.execute('CREATE TABLE instruments (symbol TEXT PRIMARY KEY, name TEXT)')
    c.execute('CREATE TABLE daily_prices (symbol TEXT, d_even TEXT, '
              'PRIMARY KEY (symbol, d_even))')
    c.execute('CREATE TABLE financial_statements (symbol TEXT PRIMARY KEY)')
    for i in range(rows):
        c.execute('INSERT INTO instruments VALUES (?,?)', ('SYM%04d' % i, 'نماد'))
    if noise:
        c.execute('CREATE TABLE filler (id INTEGER PRIMARY KEY, blob BLOB)')
        step = 0
        while step < noise:
            c.execute('INSERT INTO filler (blob) VALUES (?)', (os.urandom(1 << 18),))
            step += 1 << 18
    c.commit()
    c.close()
    with open(tmp, 'rb') as f:
        raw = f.read()
    os.remove(tmp)
    with open(path, 'wb') as f:
        f.write(lzma.compress(raw))
    return os.path.getsize(path)


# ── ۱) سرورِ دادهٔ جعلی برایِ مسیرِ دریافت ────────────────────────────────
class _DataHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        import bors_config as B
        if self.path.endswith('/market.db.meta.json'):
            body = json.dumps({'sha256': SERVED_SHA, 'size': SERVED_SIZE}).encode()
        elif self.path.endswith('/market.db.lzma'):
            with open(SERVED_LZMA, 'rb') as f:
                body = f.read()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_download(scratch):
    global SERVED_SHA, SERVED_SIZE, SERVED_LZMA
    import hashlib
    import bors_config
    SERVED_LZMA = os.path.join(scratch, 'served.lzma')
    SERVED_SIZE = _mini_db_lzma(SERVED_LZMA, rows=120, noise=6 << 20)
    SERVED_SHA = hashlib.sha256(open(SERVED_LZMA, 'rb').read()).hexdigest()

    port = _free_port()
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', port), _DataHandler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, kwargs={'poll_interval': 0.2},
                     daemon=True).start()
    base = f'http://127.0.0.1:{port}/rel/'
    bors_config.MARKET_DATA_RELEASE_META = base + 'market.db.meta.json'
    bors_config.MARKET_DATA_RELEASE_ASSET = base + 'market.db.lzma'
    work = os.path.join(scratch, 'dl')
    os.makedirs(work, exist_ok=True)
    bors_config.WORK_DIR = work

    events = []
    got = bors_config._download_market_db_lzma(
        progress=lambda p, d, t: events.append((p, d, t)))
    ck('دریافت از Release انجام شد', got == os.path.join(work, 'market.db.lzma'))
    ck('فایلِ دریافت‌شده سرِ جایش است',
       got and os.path.getsize(got) == SERVED_SIZE)
    dl = [e for e in events if e[0] == 'download']
    ck('پیشرفتِ دریافت گزارش شد (%d مرحله)' % len(dl), len(dl) >= 3)
    ck('درصدِ دریافت یکنوا بالا می‌رود',
       [e[1] for e in dl] == sorted(e[1] for e in dl))
    if dl:
        ck('مجموعِ بایت‌ها با اندازهٔ فایل یکی است', dl[-1][1] == SERVED_SIZE,
           '%s vs %s' % (dl[-1][1], SERVED_SIZE))
        ck('آستانِ کل از متا درست رسیده', dl[-1][2] == SERVED_SIZE)
    ck('مرحلۀ نشانیِ داده هم دیده شد', any(e[0] == 'data-meta' for e in events))

    # اثرانگشتِ غلط ⇒ هرگز فایلِ نهایی نمی‌شود
    SERVED_SHA = '0' * 64
    events2 = []
    bad = bors_config._download_market_db_lzma(
        progress=lambda p, d, t: events2.append((p, d, t)))
    ck('اثرانگشتِ نادرست رد شد', bad is None)
    leftovers = [n for n in os.listdir(work) if n.startswith('market.db.')
                 and n.endswith('.lzma') and n != 'market.db.lzma']
    ck('فایلِ موقتِ ناموفق پاک شد', not leftovers, str(leftovers))
    srv.shutdown()


def test_extract_and_page(scratch):
    import bors_config
    import bors_entry

    work = os.path.join(scratch, 'first-run')
    os.makedirs(work, exist_ok=True)
    packed = os.path.join(work, 'market.db.lzma')
    _mini_db_lzma(packed, rows=400, noise=6 << 20)
    # کشفِ واقعیِ فایل: `_find_bundled_db_lzma` از _SRC_DIR (غیرفریز) و WORK_DIR
    # و مسیرِ نسبی می‌خواند؛ همه را به پوشهٔ موقت می‌بریم تا ریپو دست‌نخورد.
    bors_config._SRC_DIR = work
    bors_config.WORK_DIR = work
    bors_config.DB_PATH = os.path.join(work, 'market.db')

    events = []
    db = bors_config.ensure_market_db(progress=lambda p, d, t: events.append((p, d, t)))
    ck('market.db ساخته شد', bool(db) and os.path.exists(db))
    ck('پیشرفتِ استخراج گزارش شد', any(e[0] == 'extract' for e in events))
    ex = [e for e in events if e[0] == 'extract']
    if ex:
        dones = [e[1] for e in ex]
        ck('درصدِ استخراج یکنوا بالا می‌رود', dones == sorted(dones) and dones[-1] > dones[0],
           '%s' % dones[:3])
        ck('استخراج تا ۱۰۰٪ دیده شد', ex[-1][1] == ex[-1][2],
           '%s/%s' % (ex[-1][1], ex[-1][2]))
    # اجرایِ دوم نباید دوباره استخراج کند
    events2 = []
    bors_config.ensure_market_db(progress=lambda p, d, t: events2.append((p, d, t)))
    ck('اجرایِ دوم بی‌استخراج است (idempotent)',
       not any(e[0] == 'extract' for e in events2), str(events2[:3]))

    # ── صفحۀ بوت ──
    bors_entry._BOOT.update({'phase': 'check', 'pct': None, 'detail': '',
                             'ready': False, 'url': None, 'error': None})
    boot = bors_entry._start_boot_server()
    ck('سرورِ بوت بالا آمد', boot is not None)
    if boot is None:
        return
    srv, port = boot
    base = f'http://127.0.0.1:{port}'
    try:
        html = urllib.request.urlopen(base + '/', timeout=5).read().decode('utf-8')
        ck('صفحۀ HTML سرو می‌شود', '<!doctype html>' in html.lower())
        ck('صفحۀ RTL و فارسی است', 'dir="rtl"' in html and 'lang="fa"' in html)
        ck('نوارِ پیشرفت دارد', 'id="bar"' in html and 'boot-status' in html)
        ck('ارقامِ فارسی با کدپیونت ساخته می‌شوند (نه تایپِ دستی)',
           '0x06F0' in html and not any('۰' <= ch <= '۹' for ch in html))
        ck('جزئیاتِ مگابایتی هم فارسی می‌شود، نه لاتین', 'fa(p.detail)' in html)
        code = None
        try:
            code = urllib.request.urlopen(base + '/favicon.ico', timeout=5).status
        except urllib.error.HTTPError as e:
            code = e.code
        ck('آیکونِ درخواستیِ مرورگر بی‌خطا پاسخ می‌گیرد (۲۰۴)', code == 204, str(code))
        st = json.loads(urllib.request.urlopen(base + '/boot-status', timeout=5).read())
        ck('وضعیتِ اولی phase دارد', st.get('phase') == 'check')
        ck('وضعیتِ اولی percent ندارد (بی‌عدد = نوارِ بی‌پایان)',
           st.get('pct') is None)

        bors_entry._boot_progress('download', 1_572_864, 5_242_880)
        st = json.loads(urllib.request.urlopen(base + '/boot-status', timeout=5).read())
        ck('درصدِ دریافت درست محاسبه شد', st['pct'] == 30, str(st.get('pct')))
        ck('متنِ فارسیِ مرحلۀ دریافت رسیده', 'دریافت' in st['text'], st['text'])
        ck('جزئیاتِ مگابایتی هست', 'MB' in st['detail'], st['detail'])

        bors_entry._boot_progress('extract', 500, 500)
        st = json.loads(urllib.request.urlopen(base + '/boot-status', timeout=5).read())
        ck('استخراجِ کامل = ۱۰۰٪', st['pct'] == 100)

        bors_entry._boot_ready('http://127.0.0.1:8001/')
        st = json.loads(urllib.request.urlopen(base + '/boot-status', timeout=5).read())
        ck('آماده شدن، آدرسِ اپ را می‌دهد تا صفحه redirect کند',
           st['ready'] is True and st['url'] == 'http://127.0.0.1:8001/')

        bors_entry._boot_fail('پیامِ خطا')
        st = json.loads(urllib.request.urlopen(base + '/boot-status', timeout=5).read())
        ck('حالتِ خطا به صفحۀ برسید است', st['error'] == 'پیامِ خطا' and st['ready'] is False)

        code = None
        try:
            urllib.request.urlopen(base + '/nope', timeout=5)
        except urllib.error.HTTPError as e:
            code = e.code
        ck('هر مسیرِ دیگر ۴۰۴ است', code == 404, str(code))
    finally:
        srv.shutdown()


def test_worker_handoff(scratch):
    """`_bootstrap_worker` بی‌دانلودِ واقعی: پیشرفت، سپس تسلیمِ آدرس."""
    import bors_entry

    seen = {}
    bors_entry._BOOT.update({'phase': 'check', 'pct': None, 'detail': '',
                             'ready': False, 'url': None, 'error': None})

    def fake_preflight(progress=None):
        seen['progress'] = progress
        progress('download', 1024 * 1024, 4 * 1024 * 1024)
        progress('extract', 900, 1000)
        return True

    def fake_wait(p, timeout=30):
        seen['waited'] = p
        return True

    bors_entry._preflight = fake_preflight
    bors_entry._start_uvicorn = lambda p: seen.setdefault('uvicorn', p)
    bors_entry.wait_http = fake_wait
    out = {}
    bors_entry._bootstrap_worker(8123, out)
    ck('worker به preflight callbackِ پیشرفت می‌دهد', seen.get('progress') is not None)
    ck('worker سرور را روی همان پورت بالا می‌آورد', seen.get('uvicorn') == 8123)
    ck('بعد از آماده شدن، آدرس تسلیم می‌شود',
       bors_entry._BOOT['ready'] and bors_entry._BOOT['url'].endswith(':8123/'))
    ck('نتیجه به نخِ اصلی گزارش می‌شود', out.get('result') == 'serving')

    # شکستِ preflight ⇒ صفحۀ خطا، بی‌سرور
    bors_entry._BOOT.update({'ready': False, 'url': None, 'error': None})
    bors_entry._preflight = lambda progress=None: False
    out2 = {}
    bors_entry._bootstrap_worker(8124, out2)
    ck('شکستِ پیش‌اجرا پیامِ خطا می‌گذارد', bool(bors_entry._BOOT['error']))
    ck('شکستِ پیش‌اجرا سرور را باز نمی‌کند', out2.get('result') == 'preflight-failed')


def main():
    scratch = tempfile.mkdtemp(prefix='bors_boot_guard_')
    try:
        print('— ۱) مسیرِ دریافت —')
        test_download(scratch)
        print('— ۲) استخراج + صفحۀ بوت —')
        test_extract_and_page(scratch)
        print('— ۳) تسلیمِ آدرس در worker —')
        test_worker_handoff(scratch)
    finally:
        import shutil
        shutil.rmtree(scratch, ignore_errors=True)
    print('\n%d سنجش سبز، %d سرخ' % (PASS, len(FAIL)))
    if FAIL:
        for f in FAIL:
            print('  RED: ' + f)
        return 1
    print('BOOT PAGE GUARD OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
