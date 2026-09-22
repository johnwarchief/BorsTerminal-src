"""Verify the consolidated-fallback fix.

1) Fill rate: how many rows now have eps_series / gross_margin / profit_potential?
2) No-regression: for symbols that already worked, the series must be IDENTICAL
   to the pre-fix (consolidated-excluding) behaviour.
"""
import sqlite3
import sys

DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'
sys.path.insert(0, r'C:\Users\PCMOD\Desktop\BorsTerminal')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import fts_engine as F
    import json

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cfg = json.loads(open(r'C:\Users\PCMOD\Desktop\BorsTerminal\fts_config.json',
                         encoding='utf-8').read()) if __import__('os').path.exists(
        r'C:\Users\PCMOD\Desktop\BorsTerminal\fts_config.json') else {}

    rows = F.bulk_scan(con, cfg=cfg)
    n = len(rows)
    eps = sum(1 for r in rows if r.get('eps_series'))
    gm = sum(1 for r in rows if r.get('gross_margin') is not None)
    pot = sum(1 for r in rows if r.get('profit_potential_pct') is not None)
    print('rows: %d' % n)
    print('  eps_series filled        : %4d (%.0f%%)  was 367 (42%%)' % (eps, 100 * eps / n))
    print('  gross_margin filled      : %4d (%.0f%%)  was 548 (63%%)' % (gm, 100 * gm / n))
    print('  profit_potential filled  : %4d (%.0f%%)  was 512 (59%%)' % (pot, 100 * pot / n))

    # spot-check previously-broken symbols
    print('\n--- previously blank (only-consolidated) symbols ---')
    for sym in ('فولاد', 'وبملت', 'اخابر', 'اسياتك', 'اردستان', 'آريان'):
        r = next((x for x in rows if x['symbol'] == sym), None)
        if not r:
            print('  %-8s not in screen' % sym)
            continue
        print('  %-8s eps=%-22s gm=%-8s pot=%-8s score=%s'
              % (sym, r.get('eps_series'), r.get('gross_margin'),
                 r.get('profit_potential_pct'), r.get('score')))

    # regression: symbols that had >=3 non-consolidated rows must be unchanged.
    # Recompute the pre-fix series with the old exclusion rule.
    annual = {}
    for sym, pe, title, rev, gp, eps_ in con.execute(
            "SELECT symbol, period_end, title, revenue, gross_profit, basic_eps "
            "FROM financial_statements WHERE period_months>=12 "
            "ORDER BY symbol, period_end DESC"):
        key = F.norm_fa(sym)
        if not key:
            continue
        annual.setdefault(key, []).append({
            'fy': str(pe or '')[:4], 'audited': F._is_audited(title or ''),
            'consolidated': F._is_consolidated(title or ''), 'eps': F._fn(eps_)})

    changed = []
    for r in rows:
        key = r.get('symbol_norm') or r['symbol']
        lst = annual.get(key)
        if not lst:
            continue
        old = []
        seen = set()
        for x in lst:
            if x['consolidated']:
                continue
            if x['fy'] in seen:
                continue
            seen.add(x['fy'])
            old.append(x)
        if len(old) < 3:
            continue  # this symbol had no full series before; not a regression risk
        old_ser = [round(x['eps'], 1) if x['eps'] is not None else None
                   for x in reversed(old[:3])]
        new_ser = r.get('eps_series')
        if new_ser != old_ser:
            changed.append((key, old_ser, new_ser))

    print('\n--- regression check (symbols that had a full 3y solo series) ---')
    print('  checked, series differ: %d' % len(changed))
    for key, o, nw in changed[:10]:
        print('    %-10s old=%s new=%s' % (key, o, nw))
    con.close()


if __name__ == '__main__':
    main()
