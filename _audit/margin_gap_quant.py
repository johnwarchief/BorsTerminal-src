"""Is the gross-margin / profit-potential gap the SAME consolidated-exclusion bug?

_ref() (which feeds indicator 3 = gross margin and indicator 5 = profit
potential) also skips consolidated rows. If a company's only row with a
non-NULL gross_profit is the consolidated one, the margin column is blank
even though the data exists in the DB.
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
        "SELECT symbol, period_end, title, revenue, gross_profit, basic_eps "
        "FROM financial_statements WHERE period_months>=12 "
        "ORDER BY symbol, period_end DESC").fetchall()

    per = {}
    for r in rows:
        key = F.norm_fa(r['symbol'])
        if not key:
            continue
        per.setdefault(key, []).append(r)

    # margin blank under current rule, but a consolidated row has gp?
    fixable_margin = 0
    genuinely_no_gp = 0
    examples = []
    for key, lst in per.items():
        solo = [r for r in lst if not F._is_consolidated(r['title'] or '')]
        ref = next((r for r in solo
                    if r['gross_profit'] is not None and (r['revenue'] or 0) > 0), None)
        if ref:
            continue  # margin already computable
        any_gp = next((r for r in lst
                       if r['gross_profit'] is not None and (r['revenue'] or 0) > 0), None)
        if any_gp:
            fixable_margin += 1
            if len(examples) < 8:
                examples.append((key, 'cons' if F._is_consolidated(any_gp['title'] or '') else 'solo',
                                 any_gp['gross_profit'], any_gp['revenue']))
        else:
            genuinely_no_gp += 1

    print('symbols with blank gross-margin column: %d' % (fixable_margin + genuinely_no_gp))
    print('  fixable via consolidated fallback    : %d' % fixable_margin)
    print('  genuinely no gross_profit in DB      : %d' % genuinely_no_gp)
    print()
    for key, kind, gp, rev in examples:
        print('  %-10s (%s) gp=%s rev=%s' % (key, kind, gp, rev))
    con.close()


if __name__ == '__main__':
    main()
