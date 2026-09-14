"""
v9.5 — دود-تست سرور: بالا می‌آید، فایل‌های تازه را سرو می‌کند، FTS رد می‌شود.
اجرا:  python dev/serve_check_v95.py
"""
import json, os, re, subprocess, sys, time, urllib.request

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
BASE = 'http://127.0.0.1:8012'
env = dict(os.environ, PYTHONIOENCODING='utf-8')
fails = []


def say(ok, msg):
    print('  %s %s' % ('PASS' if ok else 'FAIL', msg))
    if not ok:
        fails.append(msg)


p = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app:app',
                      '--host', '127.0.0.1', '--port', '8012',
                      '--log-level', 'warning'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, env=env)
try:
    up = False
    for _ in range(60):
        try:
            with urllib.request.urlopen(BASE + '/', timeout=8) as r:
                up = (r.status == 200)
                html = r.read().decode('utf-8', 'replace')
            break
        except Exception:
            time.sleep(1)
    say(up, 'server answers GET /')
    if not up:
        sys.exit(1)

    _vers = set(re.findall(r'/static/[^"]*[?&]v=(\d+\.\d+\.\d+)', html))
    say(len(_vers) == 1 and tuple(int(x) for x in next(iter(_vers)).split('.')) >= (9, 7, 7),
        'served HTML uses ONE cache-bust version >= 9.7.7 (%s)' % sorted(_vers))
    say('v=9.5.1' not in html, 'no stale v=9.5.1 refs in served HTML')

    for asset in ['/archive/legacy_static/tech_365.js', '/archive/legacy_static/styles_365.css',
                  '/archive/legacy_static/tech_rtv.js', '/archive/legacy_static/tech_tools.js']:
        try:
            with urllib.request.urlopen(BASE + asset, timeout=8) as r:
                say(r.status == 200, '%s -> 200 (%d bytes)' % (asset, len(r.read())))
        except Exception as e:
            say(False, '%s fetchable (%r)' % (asset, e))

    with urllib.request.urlopen(BASE + '/archive/legacy_static/tech_365.js', timeout=8) as r:
        js = r.read().decode('utf-8', 'replace')
    say('bar: {' in js, 'served tech_365.js uses candle.bar')
    say(not re.search(r'candle:\s*\{\s*candle:', js), 'served tech_365.js free of candle.candle')
    say('overrideYAxis' in js, 'served tech_365.js uses overrideYAxis')
    say('rvToggleLogScale' not in js, 'served tech_365.js free of rvToggleLogScale')

    # --- v9.7: «آخرین قیمت» باید واقعاً از «قیمت پایانی» جدا سرو شود ---
    from urllib.parse import quote
    try:
        with urllib.request.urlopen(BASE + '/api/chart/' + quote('خودرو') + '?days=180',
                                    timeout=60) as r:
            cd = json.loads(r.read().decode('utf-8', 'replace'))
    except Exception as e:
        cd = {}
        say(False, '/api/chart responded (%r)' % e)
    cs = cd.get('candles') or []
    say(bool(cs), '/api/chart returned %d candles' % len(cs))
    say(all('last' in c for c in cs), 'every candle carries a "last" field')
    say(all(isinstance(c.get('last'), (int, float)) and c['last'] > 0 for c in cs),
        'every "last" is a positive number (fallback never emits 0/null)')
    d = sum(1 for c in cs if c.get('last') != c.get('close'))
    say(d > 0, '"last" genuinely differs from "close" on %d/%d candles' % (d, len(cs)))
    say(all(c.get('last') <= max(c.get('high', 0), c.get('close', 0)) * 1.001 for c in cs),
        'no "last" is wildly outside its candle (sanity bound)')

    r = subprocess.run([sys.executable, 'dev/fts_roundtrip_v91.py'],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=300, env=env)
    say(r.returncode == 0, 'fts_roundtrip_v91.py rc=%d' % r.returncode)
    tail = ((r.stdout or '') + (r.stderr or '')).strip().split('\n')[-1]
    print('       ' + tail.encode('ascii', 'replace').decode('ascii'))
finally:
    p.terminate()
    try:
        p.wait(timeout=10)
    except Exception:
        p.kill()

print('\n%d failed' % len(fails))
sys.exit(1 if fails else 0)
