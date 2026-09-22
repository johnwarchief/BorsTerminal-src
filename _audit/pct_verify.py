"""Verify the percent_change fix against the live API after restart."""
import json
import math
import urllib.request

API = 'http://127.0.0.1:8001'


def fetch(path):
    with urllib.request.urlopen(API + path, timeout=120) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    j = fetch('/api/market')
    rows = j.get('data') or j.get('items') or j.get('rows') or []

    impossible, consistent, none_ct, total = 0, 0, 0, 0
    bad = []
    for r in rows:
        pct = r.get('percent_change')
        total += 1
        if pct is None:
            none_ct += 1
            continue
        if not isinstance(pct, (int, float)):
            bad.append((r['symbol'], 'not numeric', pct))
            continue
        if abs(pct) > 100:
            impossible += 1
            bad.append((r['symbol'], 'impossible', pct))
            continue
        # recompute from the two source columns
        pc, py = r.get('price_change'), r.get('price_yesterday')
        if isinstance(pc, (int, float)) and isinstance(py, (int, float)) and py > 1:
            calc = pc / py * 100.0
            if abs(calc - pct) > 0.06:
                bad.append((r['symbol'], 'mismatch', pct, round(calc, 2)))
            else:
                consistent += 1

    print('total symbols          : %d' % total)
    print('percent_change is None : %d  (rights/options with no valid prior close)' % none_ct)
    print('|pct| > 100 (impossible): %d' % impossible)
    print('consistent with source : %d' % consistent)
    print('still broken           : %d' % len(bad))
    for x in bad[:12]:
        print('   ', x)


if __name__ == '__main__':
    main()
