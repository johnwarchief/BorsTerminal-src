"""Why does the top50 bucket report 0 symbols?

top50_codes() needs rows with cls == PAPER_STOCK and a positive
total_shares * p_closing. Inspect the snapshot the engine actually builds.
"""
import sqlite3
import sys

sys.path.insert(0, r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal')
sys.path.insert(0, r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\python')

DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'


def main():
    import os
    import sqlite3
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import mstat_engine as M
    con = sqlite3.connect(DB)
    snap = M.load_snapshot(con)
    rows = snap['rows']
    print('snapshot rows:', len(rows))
    print('sample row keys:', sorted(rows[0].keys())[:40])

    from collections import Counter
    print('\ncls distribution:', Counter(r.get('cls') for r in rows))
    print('kind distribution:', Counter(r.get('kind') for r in rows))

    print('\nPAPER_STOCK =', M.PAPER_STOCK)
    n_stock = sum(1 for r in rows if r.get('cls') == M.PAPER_STOCK)
    print('rows with cls==PAPER_STOCK:', n_stock)

    n_cap = 0
    n_shares = 0
    for r in rows:
        if r.get('cls') != M.PAPER_STOCK:
            continue
        ts = r.get('total_shares')
        pc = r.get('p_closing')
        try:
            cap = float(ts or 0) * float(pc or 0)
        except Exception:
            cap = 0
        if cap > 0:
            n_cap += 1
        if not ts:
            n_shares += 1
    print('stock rows with cap>0:', n_cap)
    print('stock rows missing total_shares:', n_shares)

    t50 = M.top50_codes(rows)
    print('top50_codes() ->', len(t50))


if __name__ == '__main__':
    main()
