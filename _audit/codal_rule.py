"""Validate the board-class digit rule before touching symbol_aliases().

TSETMC appends ONE trailing digit to mark the market-board class of the SAME
issuer (مبين / مبين3). symbol_aliases() today only handles ی/ي/ى and ک/ك, so
مبين3 never matches CODAL rows stored under مبين.

Rule to test: strip exactly ONE trailing ASCII digit, keep the base if it is
>= 2 chars. Multi-digit tails (صشرق512, سبرق061) are part of the symbol and
must NOT be touched.

Safety check: does stripping ever match a DIFFERENT company? Verify with
total_shares — the same issuer shares that value exactly.
"""
import sqlite3
import sys

DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'


def strip_board_digit(s):
    """مبين3 -> مبين ; صشرق512 -> صشرق512 (multi-digit tail is part of name)."""
    if not s or len(s) < 3:
        return None
    if s[-1] in '0123456789' and s[-2] not in '0123456789':
        b = s[:-1]
        return b if len(b) >= 2 else None
    return None


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    sys.path.insert(0, r'C:\Users\PCMOD\Desktop\BorsTerminal')
    import mstat_engine as M
    snap = M.load_snapshot(con)
    stocks = [r['symbol'] for r in snap['rows'] if r['cls'] == 'stock']
    have = {r[0] for r in con.execute('SELECT DISTINCT symbol FROM codal_notices')}
    missing = [s for s in stocks if s not in have]

    would_fix, no_base = [], []
    for s in missing:
        b = strip_board_digit(s)
        if b and b in have:
            would_fix.append((s, b))
        else:
            no_base.append(s)

    print('missing: %d' % len(missing))
    print('rule would link to existing CODAL data: %d' % len(would_fix))
    print('still missing after rule:            %d' % len(no_base))

    # SAFETY: are the linked pairs really the same issuer?
    print('\n--- same-issuer check (total_shares must match) ---')
    same = diff = 0
    bad = []
    for s, b in would_fix:
        r = con.execute(
            "SELECT a.total_shares AS sa, b.total_shares AS sb FROM instruments a,"
            " instruments b WHERE a.l_val18=? AND b.l_val18=? AND a.total_shares>0"
            " AND b.total_shares>0", (s, b)).fetchone()
        if r is None:
            continue
        if abs((r['sa'] or 0) - (r['sb'] or 0)) < 1:
            same += 1
        else:
            diff += 1
            if len(bad) < 8:
                bad.append((s, b, r['sa'], r['sb']))
    print('  shares match (same issuer): %d' % same)
    print('  shares differ (DANGER):     %d' % diff)
    for s, b, sa, sb in bad:
        print('    %-10s vs %-10s  %s vs %s' % (s, b, f"{sa:,.0f}", f"{sb:,.0f}"))

    # does the rule ever fire on a symbol that is NOT missing? (false positive)
    fp = 0
    for s in have:
        b = strip_board_digit(s)
        if b and b in have and b != s:
            fp += 1
    print('\nfalse-positive pairs among symbols that already have data: %d' % fp)

    # the genuinely missing, biggest first
    print('\n--- genuinely missing after the rule (top by shares) ---')
    q = "SELECT l_val18, total_shares FROM instruments WHERE l_val18 IN (%s)" % \
        ','.join('?' * len(no_base))
    rows = sorted(con.execute(q, no_base).fetchall(),
                  key=lambda r: -(r['total_shares'] or 0))
    for r in rows[:15]:
        print('   %-10s shares=%s' % (r['l_val18'], f"{r['total_shares'] or 0:,.0f}"))
    con.close()


if __name__ == '__main__':
    main()
