# tools/ui_mstat_backend_cost.py -- هزینهِٔ خودِ بک‌اند برایِ پنل‌هایِ mstat (فاز G، بندِ ۵)
#
# رابط می‌گوید اولینِ پرسشِ صفحه درِ ~۱.۷ ثانیه ازِ ناوبری آغاز می‌شود وِ کارتِ شاخص
# ~۲.۱ ثانیه بعدِ آنِ پرسش عدد می‌گیرد. اینِ فایل همانِ فاصلۀِ دوم را جدا می‌سنجد:
# هرِ پنل رویِ localhost چقدر هزینه دارد، بارِ سرد (اولینِ تماس) وِ بارِ گرم (تماسِ دوم
# باِ همانِ کلید). بی‌دست‌زدنِ هیچِ کشی؛ فقطِ اندازه‌گیری.
#
# اجرا:  PYTHONIOENCODING=utf-8 python tools/ui_mstat_backend_cost.py --port=8010 --rounds=2
import json
import socket
import sys
import time
import urllib.request


def arg(name, default=None):
    for a in sys.argv[1:]:
        if a.startswith(f'--{name}='):
            return a.split('=', 1)[1]
    return default


PORT = int(arg('port', '8010'))
ROUNDS = int(arg('rounds', '2'))
BASE = f'http://127.0.0.1:{PORT}'

PANELS = [
    'mainwatch', 'timeline', 'treemap', 'gold', 'series', 'industries',
    'smart-money', 'summary', 'depth', 'thermometer', 'histogram',
    'clientsplit', 'phases', 'indexcards',
]


def timed(path):
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(BASE + path, timeout=60) as r:
            body = r.read()
    except Exception as e:  # noqa: BLE001
        return round((time.perf_counter() - t) * 1000), 0, f'ERR {type(e).__name__}'[:60], None
    ms = round((time.perf_counter() - t) * 1000)
    try:
        st = json.loads(body).get('status')
    except Exception:  # noqa: BLE001
        st = 'NOT-JSON(HTML?)'
    return ms, len(body), st, None


print(f'هدف: {BASE} · {ROUNDS} دور · {len(PANELS)} پنل')
sock = socket.socket()
sock.settimeout(3)
try:
    sock.connect(('127.0.0.1', PORT))
except OSError:
    print('پورت بسته است — اولِ سرور را بالا بیاور.')
    sys.exit(2)
finally:
    sock.close()

results = {}
for rnd in range(ROUNDS):
    row = {}
    for p in PANELS:
        ms, size, st, _ = timed(f'/api/mstat/{p}')
        row[p] = (ms, size, st)
    results[rnd] = row
    worst = sorted(row.items(), key=lambda kv: -kv[1][0])[:5]
    tot = sum(v[0] for v in row.values())
    med = sorted(v[0] for v in row.values())[len(row) // 2]
    print(f'دور {rnd + 1}: مجموع={tot}ms  میانه={med}ms')
    for k, (ms, size, st) in worst:
        print(f'   {k:<13} {ms:>6}ms  {size:>8}B  status={st}')

if ROUNDS > 1:
    print('\nسرد→گرم (اختلافِ هرِ پنل، ms):')
    for p in PANELS:
        c = results[0][p][0]
        w = results[1][p][0]
        print(f'   {p:<13} سرد={c:>6}  گرم={w:>6}  Δ={c - w:>6}')
