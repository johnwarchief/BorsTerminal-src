"""Compare local mstat pulse against the real TradersArena endpoints.

Endpoints used by the app: /data/market0 and /data/market/chart/totals0.
Also investigate the top50 bucket, which reports symbols=0.
"""
import json
import urllib.request

API = 'http://127.0.0.1:8001'
TA = 'https://tradersarena.ir'


def get(url, timeout=25):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    print('=== TradersArena /data/market0 ===')
    try:
        m0 = get(TA + '/data/market0')
        print(json.dumps(m0, ensure_ascii=False, indent=1)[:3000])
    except Exception as e:
        print('  FAILED:', e)

    print('\n=== TradersArena /data/market/chart/totals0 (tail) ===')
    try:
        t0 = get(TA + '/data/market/chart/totals0')
        s = json.dumps(t0, ensure_ascii=False)
        print('  len:', len(s))
        print('  ...', s[-1200:])
    except Exception as e:
        print('  FAILED:', e)

    print('\n=== local mstat: top50 bucket ===')
    loc = get(API + '/api/mstat/board', timeout=60)
    for row in loc.get('summary', {}).get('rows', []):
        if row.get('key') == 'top50':
            print(json.dumps(row, ensure_ascii=False, indent=1))
    print('  asof:', json.dumps(loc['summary']['asof'], ensure_ascii=False))


if __name__ == '__main__':
    main()
