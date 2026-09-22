"""Strict check: every change must be an improvement only.

- eps_series: None -> list  (gain)
- score: may only increase, and only when eps_series went None -> list
- any other field changing, or a score DECREASE, is a hard regression.
"""
import json
import sys


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    before = json.loads(open('_audit/_screen_before.json', encoding='utf-8').read())
    after = json.loads(open('_audit/_screen_after.json', encoding='utf-8').read())
    assert set(before) == set(after)

    hard = []
    score_up = []
    eps_gain = 0
    for sym in before:
        b, a = before[sym], after[sym]
        if (b['eps_series'] or []) != (a['eps_series'] or []):
            if not b['eps_series'] and a['eps_series']:
                eps_gain += 1
            else:
                hard.append(('eps_series', sym, b['eps_series'], a['eps_series']))
        if b['score'] != a['score']:
            if a['score'] > b['score'] and not b['eps_series'] and a['eps_series']:
                score_up.append((sym, b['score'], a['score']))
            else:
                hard.append(('score', sym, b['score'], a['score']))
        for f in ('gross_margin', 'profit_potential_pct', 'rev_growth', 'annual_sales_bt'):
            if b[f] != a[f]:
                hard.append((f, sym, b[f], a[f]))

    print('eps_series gains: %d' % eps_gain)
    print('score increases (from new EPS data): %d' % len(score_up))
    for sym, s0, s1 in score_up:
        print('   %-10s %d -> %d' % (sym, s0, s1))
    print()
    print('HARD REGRESSIONS: %d' % len(hard))
    for f, sym, v0, v1 in hard[:20]:
        print('   %-10s %-22s %s -> %s' % (sym, f, v0, v1))
    print()
    print('RESULT: %s' % ('PASS — gains only' if not hard else 'FAIL — regressions present'))


if __name__ == '__main__':
    main()
