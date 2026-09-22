"""Exact before/after diff of the screen table.

Rule: a symbol may only GAIN values (None -> number). Any change to a value
that was already present is a regression.
"""
import json
import sys

FIELDS = ['eps_series', 'gross_margin', 'profit_potential_pct', 'score',
          'rev_growth', 'annual_sales_bt']


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    before = json.loads(open('_audit/_screen_before.json', encoding='utf-8').read())
    after = json.loads(open('_audit/_screen_after.json', encoding='utf-8').read())

    assert set(before) == set(after), 'symbol set changed!'
    regressions = []
    gains = {f: 0 for f in FIELDS}
    gain_examples = []
    for sym in before:
        for f in FIELDS:
            b, a = before[sym].get(f), after[sym].get(f)
            if b == a:
                continue
            if b is None or b == [] or b == 0:
                gains[f] += 1
                if len(gain_examples) < 12:
                    gain_examples.append((sym, f, b, a))
            else:
                regressions.append((sym, f, b, a))

    print('symbols: %d' % len(before))
    print('\n--- GAINS (None -> value) ---')
    for f in FIELDS:
        if gains[f]:
            print('  %-22s +%-4d' % (f, gains[f]))
    print('\n--- gain examples ---')
    for sym, f, b, a in gain_examples:
        print('  %-10s %-22s %s -> %s' % (sym, f, b, a))

    print('\n--- REGRESSIONS (existing value changed) ---')
    print('  count: %d' % len(regressions))
    for sym, f, b, a in regressions[:20]:
        print('  %-10s %-22s %s -> %s' % (sym, f, b, a))


if __name__ == '__main__':
    main()
