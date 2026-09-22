"""Quantify the EPS-gap: which of the 498 blank-EPS symbols could be filled?

bulk_scan() builds the EPS series from _solo_annual(), which skips rows where
_is_consolidated(title) is true. But for many companies the ONLY 12-month
audited statement is the consolidated one (فولاد: 1404/12/29 audited=1,
title=صورت‌های مالی تلفیقی). Those get zero usable EPS rows.

This counts, across all symbols in financial_statements:
  A) symbols with >= eps_years non-consolidated annual rows  -> series works
  B) symbols with >= 2 non-consolidated annual rows           -> partial series
  C) symbols whose ONLY audited 12-month row is consolidated  -> blank, fixable
  D) symbols with < 2 annual rows of any kind                 -> genuinely thin
"""
import sqlite3
import sys

DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'
sys.path.insert(0, r'C:\Users\PCMOD\Desktop\BorsTerminal')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import fts_engine as F

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    rows = con.execute(
        "SELECT symbol, period_end, title, basic_eps, is_audited, is_consolidated "
        "FROM financial_statements WHERE period_months>=12 "
        "ORDER BY symbol, period_end DESC").fetchall()

    per = {}
    for r in rows:
        key = F.norm_fa(r['symbol'])
        if not key:
            continue
        per.setdefault(key, []).append({
            'fy': str(r['period_end'] or '')[:4],
            'audited': bool(r['is_audited']) or F._is_audited(r['title'] or ''),
            'consolidated': bool(r['is_consolidated']) or F._is_consolidated(r['title'] or ''),
            'eps': r['basic_eps'],
        })

    a = b = c = d = 0
    c_examples = []
    for key, lst in per.items():
        # dedupe by fiscal year, non-consolidated preferred (mirrors _solo_annual)
        solo = []
        seen = set()
        for r in lst:
            if r['consolidated']:
                continue
            if r['fy'] in seen:
                continue
            seen.add(r['fy'])
            solo.append(r)
        any_rows = []
        seen2 = set()
        for r in lst:
            if r['fy'] in seen2:
                continue
            seen2.add(r['fy'])
            any_rows.append(r)

        if len(solo) >= 3:
            a += 1
        elif len(solo) >= 2:
            b += 1
        elif len(any_rows) >= 2:
            c += 1
            if len(c_examples) < 10:
                c_examples.append((key, len(any_rows),
                                   [ (r['fy'], 'cons' if r['consolidated'] else 'solo',
                                      'aud' if r['audited'] else 'unaud', r['eps'])
                                     for r in any_rows[:3]]))
        else:
            d += 1

    print('symbols in financial_statements (period_months>=12): %d' % len(per))
    print('  A) >=3 non-consolidated annual rows (series works) : %d' % a)
    print('  B) 2 non-consolidated annual rows (partial)        : %d' % b)
    print('  C) only consolidated annual rows (BLANK, fixable)  : %d' % c)
    print('  D) <2 annual rows of any kind (genuinely thin)     : %d' % d)
    print()
    print('--- category C examples ---')
    for key, n, lst in c_examples:
        print('  %-10s rows=%d %s' % (key, n, lst))
    con.close()


if __name__ == '__main__':
    main()
