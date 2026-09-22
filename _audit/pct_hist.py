"""Is price_yesterday=1 a real close or a TSETMC sentinel?

Check price_history for the offenders: if a genuine prior-day close exists
there, we can recover the true percent. If not, the percent is genuinely
undefined and must be suppressed rather than shown as +4,195,600%.
"""
import sqlite3

DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'
SYMS = ['ضموج715', 'ضموج921', 'ضفزر726', 'ضاطلس071905', 'طهرم9026', 'ضستا8062']


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cols = [c[1] for c in con.execute('PRAGMA table_info(price_history)')]
    print('price_history cols:', cols)

    for s in SYMS:
        rows = list(con.execute(
            'SELECT * FROM price_history WHERE symbol=? ORDER BY date DESC LIMIT 4', (s,)))
        print('\n=== %s (%d history rows) ===' % (s, len(rows)))
        for r in rows:
            print('  ', dict(r))

    # how many symbols have price_yesterday == 1 in the board snapshot?
    n1 = con.execute(
        "SELECT COUNT(*) FROM market_snapshot WHERE price_yesterday=1").fetchone()[0]
    ntot = con.execute("SELECT COUNT(*) FROM market_snapshot").fetchone()[0]
    print('\nmarket_snapshot rows: %d | price_yesterday==1: %d' % (ntot, n1))

    # of those with price_yesterday==1, how many have a real price_history?
    with1 = [r[0] for r in con.execute(
        "SELECT l_val18 FROM market_snapshot WHERE price_yesterday=1")]
    have_hist = con.execute(
        "SELECT COUNT(DISTINCT symbol) FROM price_history WHERE symbol IN (%s)"
        % ','.join('?' * len(with1)), with1).fetchone()[0] if with1 else 0
    print('symbols with price_yesterday==1: %d | of those with price_history: %d'
          % (len(with1), have_hist))
    con.close()


if __name__ == '__main__':
    main()
