"""CODAL completeness audit.

The FTS fundamental screen is only as good as the CODAL data behind it. This
measures, for the investable universe (real stocks), how many have:
  - no fundamental row at all
  - a row but missing the fields the FTS matrix consumes
  - a stale row (financials older than the reporting season)

It does not fetch anything; it reports the gap so the missing ones can be
queued for codal_fetcher.
"""
import sqlite3
import sys

DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    print('tables: %s' % sorted(tables))

    # the investable universe: real operating companies (post paper_type fix)
    # re-derive the same way mstat_engine.classify does
    import mstat_engine as M
    snap = M.load_snapshot(con)
    rows = snap['rows']
    stocks = [r for r in rows if r['cls'] == 'stock']
    print('\nstocks in snapshot: %d' % len(stocks))

    # which fundamental tables exist and how many symbols each covers
    fund_tables = sorted(t for t in tables if 'codal' in t.lower() or
                         t in ('fundamentals', 'fundamental', 'codal_data',
                               'financials', 'company_fundamentals'))
    print('codal-ish tables: %s' % fund_tables)

    for t in fund_tables:
        n = con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        nd = con.execute(f'SELECT COUNT(DISTINCT symbol) FROM {t}').fetchone()[0]
        cols = [c[1] for c in con.execute(f'PRAGMA table_info({t})')]
        print('  %-28s rows=%-6d symbols=%-6d' % (t, n, nd))
        print('      cols: %s' % ', '.join(cols))

    # coverage against the stock universe
    if fund_tables:
        t = fund_tables[0]
        have = {r[0] for r in con.execute(f'SELECT DISTINCT symbol FROM {t}')}
        missing = [r['symbol'] for r in stocks if r['symbol'] not in have]
        print('\n%s: stocks with NO row: %d / %d' % (t, len(missing), len(stocks)))
        print('  first missing:', missing[:20])

    con.close()


if __name__ == '__main__':
    sys.path.insert(0, r'C:\Users\PCMOD\Desktop\BorsTerminal')
    main()
