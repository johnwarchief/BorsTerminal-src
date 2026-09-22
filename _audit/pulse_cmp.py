"""Compare the local market-pulse (نبض بازار) numbers against TradersArena.

The pulse cards on the board are built by mstat_engine from market.db. This
fetches the same indicators from tradersarena.ir directly and diffs them, so
a divergence in value, scale or interpretation surfaces here.
"""
import json
import urllib.request

API = 'http://127.0.0.1:8001'
TA = 'https://tradersarena.ir'


def get(url, timeout=25, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    print('=== local /api/mstat/board ===')
    try:
        loc = get(API + '/api/mstat/board', timeout=60)
        print(json.dumps(loc, ensure_ascii=False, indent=1)[:2500])
    except Exception as e:
        print('  local mstat FAILED:', e)
        loc = None

    print('\n=== TradersArena market status ===')
    try:
        ta = get(TA + '/data/market_status.json', timeout=25)
        print(json.dumps(ta, ensure_ascii=False, indent=1)[:2500])
    except Exception as e:
        print('  tradersarena market_status FAILED:', e)

    print('\n=== TradersArena arena status ===')
    for path in ('/data/arena.json', '/data/market_overview.json',
                 '/api/v1/market/overview'):
        try:
            d = get(TA + path, timeout=20)
            print('  %s -> %s' % (path, json.dumps(d, ensure_ascii=False)[:600]))
        except Exception as e:
            print('  %s -> FAILED %s' % (path, e))


if __name__ == '__main__':
    main()
