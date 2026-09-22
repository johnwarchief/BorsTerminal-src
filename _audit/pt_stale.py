"""Is the DB's paper_type stale, or is TSETMC itself inconsistent?

TSETMC's paperType buckets are clean today (no overlap), yet market.db stores
فولاد/وبملت/شستا as pt=8 (fund). Two possibilities:
  a) the DB was written by an older, buggier fetch_paper_types and never fixed;
  b) TSETMC's instrument-level API disagrees with its MarketWatch buckets.

Compare the DB against the live map to decide which.
"""
import json
import sqlite3
import urllib.request

BASE = 'https://cdn.tsetmc.com/api'
HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://tsetmc.com/',
    'Origin': 'https://tsetmc.com',
}
DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def live_pt_map():
    out = {}
    for pt in (1, 2, 4, 8):
        j = get(f'{BASE}/ClosingPrice/GetMarketWatch?market=0'
                f'&paperTypes[0]={pt}&showTraded=false'
                '&withBestLimits=false&hEven=0')
        rows = (j.get('marketwatch') if isinstance(j, dict) else j) or []
        for x in rows:
            ic = x.get('insCode')
            if not ic:
                continue
            nm = (x.get('lvc') or '') + ' ' + (x.get('lva') or '')
            if 'اختيار' in nm or 'اختیار' in nm:
                continue
            out[ic] = pt
    return out


def main():
    live = live_pt_map()
    print('live TSETMC paper_type map: %d instruments' % len(live))

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    db = {r['ins_code']: r['paper_type'] for r in
          con.execute('SELECT ins_code, paper_type FROM instruments')}
    print('db instruments: %d' % len(db))

    disagree = []
    for ic, dbpt in db.items():
        lpt = live.get(ic)
        if lpt is None:
            continue
        if dbpt != lpt:
            disagree.append((ic, dbpt, lpt))
    print('\nDB vs live TSETMC disagree: %d' % len(disagree))
    for ic, a, b in disagree[:15]:
        nm = con.execute('SELECT l_val18 FROM instruments WHERE ins_code=?',
                         (ic,)).fetchone()[0]
        print('   %-10s db=%s  live=%s' % (nm, a, b))

    # the companies we care about
    print('\n=== big companies: db vs live ===')
    for r in con.execute("SELECT ins_code, l_val18, paper_type FROM instruments "
                         "WHERE l_val18 IN ('فولاد','وبملت','فملي','شستا','شپنا','پارسه','خگستر')"):
        print('   %-8s db=%-5s live=%s' % (r['l_val18'], r['paper_type'], live.get(r['ins_code'])))

    # how many DB rows have pt=8 but a non-fund sector?
    n = con.execute("SELECT COUNT(*) FROM instruments WHERE paper_type=8 "
                    "AND sector_name NOT LIKE '%صندوق%'").fetchone()[0]
    n8 = con.execute("SELECT COUNT(*) FROM instruments WHERE paper_type=8").fetchone()[0]
    print('\npt=8 rows: %d | of those with a non-fund sector: %d' % (n8, n))
    con.close()


if __name__ == '__main__':
    main()
