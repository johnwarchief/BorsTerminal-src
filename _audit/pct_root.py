"""Root-cause the percent_change discrepancy.

Hypothesis: percent_change = (p_closing - price_yesterday)/price_yesterday*100
is correct arithmetic, but for some symbols price_yesterday is a near-zero
nominal (rights issues, newly listed), which inflates the ratio absurdly.
TSETMC's own p_change (exposed as price_change) is the authoritative change.

Confirm by inspecting the raw columns for the worst offenders.
"""
import json
import sqlite3
import urllib.request

API = 'http://127.0.0.1:8001'
DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'


def fetch(path):
    with urllib.request.urlopen(API + path, timeout=120) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    j = fetch('/api/market')
    rows = j.get('data') or j.get('items') or j.get('rows') or []

    worst = []
    for r in rows:
        pc, py, pct = r.get('price_change'), r.get('price_yesterday'), r.get('percent_change')
        if isinstance(pc, (int, float)) and isinstance(py, (int, float)) and py > 0:
            calc = pc / py * 100.0
            if abs(calc - (pct or 0)) > 0.05:
                worst.append((abs(pct or 0), r['symbol'], r.get('p_closing'),
                              py, pc, pct, calc, r.get('is_live')))
    worst.sort(reverse=True)
    print('=== worst percent_change offenders (|pct| desc) ===')
    print('%-14s %10s %10s %10s %12s %12s  live' % (
        'symbol', 'p_closing', 'p_yest', 'p_change', 'pct_api', 'pct_calc'))
    for _, s, cl, py, pc, pct, calc, live in worst[:20]:
        print('%-14s %10s %10s %10s %12s %12s  %s' % (
            s, cl, py, pc, pct, round(calc, 2), live))

    # how many have a tiny price_yesterday?
    tiny = [r for r in rows if isinstance(r.get('price_yesterday'), (int, float))
            and 0 < r['price_yesterday'] < 100]
    print('\nsymbols with 0 < price_yesterday < 100 : %d' % len(tiny))
    for r in tiny[:10]:
        print('   ', r['symbol'], r.get('price_yesterday'), r.get('p_closing'),
              r.get('percent_change'))

    # is price_change == p_closing - price_yesterday for the GOOD ones?
    agree = disagree = 0
    for r in rows:
        pc, py, cl = r.get('price_change'), r.get('price_yesterday'), r.get('p_closing')
        if isinstance(pc, (int, float)) and isinstance(py, (int, float)) and isinstance(cl, (int, float)):
            if abs(pc - (cl - py)) <= 1:
                agree += 1
            else:
                disagree += 1
    print('\nprice_change == p_closing - price_yesterday : agree %d | disagree %d'
          % (agree, disagree))

    # check the raw DB columns for one offender
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    sym = worst[0][1] if worst else 'فولاد'
    print('\n=== raw instrument row for %s ===' % sym)
    cols = [c[1] for c in con.execute('PRAGMA table_info(instruments)')]
    for row in con.execute('SELECT * FROM instruments WHERE l_val18=?', (sym,)):
        for c in cols:
            v = row[c]
            if v is not None and str(v).strip() != '':
                print('  %-22s %s' % (c, v))
    con.close()


if __name__ == '__main__':
    main()
