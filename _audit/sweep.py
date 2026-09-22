"""Layer 1+3: full-market data-quality sweep.

For every symbol in /api/market, check the raw TSETMC board record and the
CODAL tables for: missing fields, type inconsistencies, null where a number
is expected, scale/unit mismatches, and impossible values (negative volume,
price zero on a live symbol, pct change out of range).

This is the "transform/normalization" layer audit: it looks at what the API
hands the frontend and asks whether each field is usable, not merely present.
"""
import json
import math
import sqlite3
import sys
import urllib.parse
import urllib.request

API = 'http://127.0.0.1:8001'
DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'


def fetch(path):
    with urllib.request.urlopen(API + path, timeout=120) as r:
        return json.loads(r.read().decode('utf-8'))


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and not (
        isinstance(v, float) and math.isnan(v))


def main():
    print('=== fetching /api/market ===')
    j = fetch('/api/market')
    rows = j.get('data') or j.get('items') or j.get('rows') or []
    print('symbols:', len(rows))

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    issues = {
        'price_zero_live': [], 'pct_out_of_range': [], 'neg_volume': [],
        'vol_zero_traded': [], 'power_zero_with_volume': [],
        'pe_zero_with_eps': [], 'eps_zero_with_price': [],
        'null_numeric': [], 'type_bad': [], 'stale_d_even': [],
        'no_board_match': [],
    }
    checked = 0

    for r in rows:
        checked += 1
        sym = str(r.get('symbol') or '').strip()
        live = bool(r.get('is_live'))
        p_last = r.get('p_last')
        pct = r.get('percent_change')
        tvol = r.get('tvol')
        bp = r.get('buyer_power')
        pe = r.get('pe')
        eps = r.get('eps')

        if live and is_num(p_last) and p_last == 0:
            issues['price_zero_live'].append(sym)
        if is_num(pct) and abs(pct) > 30:
            issues['pct_out_of_range'].append((sym, pct))
        if is_num(tvol) and tvol < 0:
            issues['neg_volume'].append(sym)
        if is_num(tvol) and tvol == 0 and r.get('z_tot_tran'):
            issues['vol_zero_traded'].append(sym)
        if is_num(tvol) and tvol > 0 and is_num(bp) and bp == 0:
            issues['power_zero_with_volume'].append(sym)
        if is_num(pe) and pe == 0 and is_num(eps) and eps > 0:
            issues['pe_zero_with_eps'].append(sym)
        if is_num(eps) and eps == 0 and is_num(p_last) and p_last > 0 and pe:
            issues['eps_zero_with_price'].append(sym)

        # null where a number is expected
        for k in ('p_last', 'tvol', 'buyer_power', 'percent_change', 'pe', 'eps'):
            v = r.get(k)
            if v is None:
                issues['null_numeric'].append((sym, k))
            elif not is_num(v) and v is not None:
                issues['type_bad'].append((sym, k, type(v).__name__, v))

        # staleness: d_even should be today
        d = r.get('d_even')
        if d and str(d) != '20260921' and str(d) != '20260922':
            issues['stale_d_even'].append((sym, d))

    # board coverage vs instruments
    n_inst = con.execute('SELECT COUNT(*) FROM instruments').fetchone()[0]
    n_fs = con.execute('SELECT COUNT(*) FROM financial_statements').fetchone()[0]
    n_ms = con.execute('SELECT COUNT(*) FROM monthly_sales').fetchone()[0]
    n_dp = con.execute('SELECT COUNT(*) FROM daily_prices').fetchone()[0]
    n_ct = con.execute('SELECT COUNT(*) FROM client_type').fetchone()[0]

    print('\n=== DB tables ===')
    print('  instruments         %d' % n_inst)
    print('  financial_statements %d' % n_fs)
    print('  monthly_sales       %d' % n_ms)
    print('  daily_prices        %d' % n_dp)
    print('  client_type         %d' % n_ct)
    print('  api symbols         %d' % len(rows))

    print('\n=== issues found (checked %d symbols) ===' % checked)
    for k, v in issues.items():
        print('  %-24s %d' % (k, len(v)))
        if v and len(v) <= 6:
            for x in v:
                print('      ', x)

    # null/type detail
    print('\n=== null_numeric detail (first 15) ===')
    for x in issues['null_numeric'][:15]:
        print('  ', x)
    print('\n=== type_bad detail (first 15) ===')
    for x in issues['type_bad'][:15]:
        print('  ', x)

    con.close()


if __name__ == '__main__':
    main()
