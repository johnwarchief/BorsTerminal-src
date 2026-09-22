"""Why is eps_series None for 58% of FTS screen rows?

bulk_scan() iterates over financial_statements, so these symbols DO have
statement rows. The EPS trend needs 3 consecutive audited annual statements.
This probe compares, for a sample of the None-EPS symbols, what is actually
in financial_statements vs what the EPS path requires.
"""
import sqlite3
import sys

DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'
SAMPLE = ['وغدير', 'رمپنا', 'آريان', 'همراه', 'سيسكو', 'فولاد', 'وبملت', 'شستا']


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path.insert(0, r'C:\Users\PCMOD\Desktop\BorsTerminal')
    import fts_engine as F

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # what columns does financial_statements have?
    cols = [c['name'] for c in con.execute('PRAGMA table_info(financial_statements)')]
    print('financial_statements cols:', cols)
    print('rows:', con.execute('SELECT COUNT(*) FROM financial_statements').fetchone()[0])
    print('distinct symbols:', con.execute(
        'SELECT COUNT(DISTINCT symbol) FROM financial_statements').fetchone()[0])
    print()

    for sym in SAMPLE:
        rows = con.execute(
            'SELECT * FROM financial_statements WHERE symbol=? '
            'ORDER BY fiscal_year DESC, period_end DESC', (sym,)).fetchall()
        if not rows:
            print('%-8s NO financial_statements rows' % sym)
            continue
        print('%-8s rows=%d' % (sym, len(rows)))
        for r in rows[:4]:
            print('    fy=%-6s period=%-12s audited=%-5s eps=%-12s rev=%-14s gp=%-12s title=%.30s'
                  % (r['fiscal_year'], r['period_end'], r['is_audited'], r['basic_eps'],
                     r['revenue'], r['gross_profit'], (r['title'] or '')[:30]))
        # what does the real EPS path say?
        try:
            res = F.eps_trend_3y(con, sym)
            if res is None:
                print('    -> eps_trend_3y: None')
            else:
                print('    -> eps_trend_3y: pass=%s series=%s reason=%s'
                      % (res.get('pass'), res.get('eps_series'), res.get('reason', '')))
        except Exception as e:
            print('    -> eps_trend_3y RAISED %s: %s' % (type(e).__name__, e))
        print()

    con.close()


if __name__ == '__main__':
    main()
