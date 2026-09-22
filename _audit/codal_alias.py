"""Are the 737 'missing' CODAL symbols real companies, or board-class aliases?

TSETMC appends a digit to a symbol to distinguish market-board classes of the
SAME company: فولاد / فولاد3 / فولاد5 are one issuer. codal_notices is keyed
on the base symbol, so the suffixed variants report as 'missing' even though
their data exists under the base name.

This separates:
  - aliases whose base symbol HAS data  -> not really missing
  - genuine companies with no data      -> the real gap to fetch
"""
import sqlite3
import sys

DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'


def base_of(sym):
    """فولاد3 / فولاد۵ -> فولاد (keep the letter suffixes that are real)."""
    s = sym
    while len(s) > 2 and s[-1] in '0123456789' and s[-2] not in '۰۱۲۳۴۵۶۷۸۹':
        s = s[:-1]
    return s


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    sys.path.insert(0, r'C:\Users\PCMOD\Desktop\BorsTerminal')
    import mstat_engine as M
    snap = M.load_snapshot(con)
    stocks = [r['symbol'] for r in snap['rows'] if r['cls'] == 'stock']

    have = {r[0] for r in con.execute('SELECT DISTINCT symbol FROM codal_notices')}
    missing = [s for s in stocks if s not in have]
    print('stocks: %d | with codal: %d | missing: %d'
          % (len(stocks), len(stocks) - len(missing), len(missing)))

    alias_ok, truly_missing = [], []
    for s in missing:
        b = base_of(s)
        if b != s and b in have:
            alias_ok.append((s, b))
        else:
            truly_missing.append(s)

    print('\nboard-class aliases whose base HAS data: %d' % len(alias_ok))
    for s, b in alias_ok[:12]:
        print('   %-10s -> %-10s' % (s, b))

    print('\nGENUINELY missing (no data under any spelling): %d' % len(truly_missing))
    print('  first 30:', truly_missing[:30])

    # how many of the genuinely-missing are big? (market cap)
    q = "SELECT l_val18, total_shares FROM instruments WHERE l_val18 IN (%s)" % \
        ','.join('?' * len(truly_missing))
    rows = con.execute(q, truly_missing).fetchall()
    print('\ninstruments rows found for the missing: %d' % len(rows))
    rows.sort(key=lambda r: -(r['total_shares'] or 0))
    for r in rows[:12]:
        print('   %-10s shares=%s' % (r['l_val18'], f"{r['total_shares'] or 0:,}"))

    # sanity: do the aliases resolve to the same ins_code?
    n_alias_in_instruments = con.execute(
        "SELECT COUNT(*) FROM instruments WHERE l_val18 IN (%s)" %
        ','.join('?' * len(alias_ok)), [a[0] for a in alias_ok]).fetchone()[0]
    print('\nalias symbols present in instruments table: %d' % n_alias_in_instruments)
    con.close()


if __name__ == '__main__':
    main()
