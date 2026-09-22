"""Reproduce the incomplete fundamental table on live v1.0.17.

Hits /api/fundamental/screen and classifies each row by what is actually
missing. The FTS table has 7 columns; a row is 'incomplete' when any of the
values the UI prints is null/0/empty even though the symbol has CODAL data.
"""
import json
import sys
import urllib.request

URL = 'http://localhost:8001/api/fundamental/screen?limit=0'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    payload = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
    rows = payload.get('data') or payload.get('symbols') or []
    print('rows returned:', len(rows), '| count field:', payload.get('count'))
    if not rows:
        print('EMPTY RESPONSE — keys:', list(payload.keys()))
        return

    keys = sorted(rows[0].keys())
    print('row keys:', keys)
    print()

    # which fields are null / zero / missing, and how often
    nulls = {}
    for r in rows:
        for k in keys:
            v = r.get(k)
            if v is None or v == '' or v == 0:
                nulls.setdefault(k, []).append(r.get('symbol'))
    for k in keys:
        n = len(nulls.get(k, []))
        if n:
            print('  %-22s null/0 in %4d/%d rows (%.0f%%)' % (k, n, len(rows), 100 * n / len(rows)))

    # the columns the UI actually renders
    ui = ['symbol', 'name', 'rev_growth', 'eps_series', 'gross_margin',
          'sales_to_mcap', 'profit_potential_pct', 'annual_sales_bt', 'score']
    print('\n--- UI columns ---')
    for k in ui:
        n = len(nulls.get(k, []))
        print('  %-22s %s' % (k, 'MISSING in %d rows' % n if n else 'ok'))

    # sample the worst rows
    print('\n--- sample rows ---')
    for r in rows[:6]:
        print('  %-10s score=%-2s rev=%-8s gm=%-8s s2m=%-8s pot=%-8s ann=%-10s eps=%s'
              % (r.get('symbol'), r.get('score'), r.get('rev_growth'),
                 r.get('gross_margin'), r.get('sales_to_mcap'),
                 r.get('profit_potential_pct'), r.get('annual_sales_bt'),
                 (r.get('eps_history_3y') or r.get('eps_series'))))


if __name__ == '__main__':
    main()
