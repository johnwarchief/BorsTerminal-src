"""Confirm TSETMC leaks real stocks into the paperType=8 (fund) response.

fetch_paper_types() keeps the most-specific class (rank 8 > 4 > 2/1) because
funds leak into pt=1. But if real stocks ALSO leak into pt=8, they are
permanently mis-stored as funds — which empties the top50 bucket and inflates
the fund rows. Query TSETMC directly to measure the leak both ways.
"""
import json
import urllib.request

BASE = 'https://cdn.tsetmc.com/api'
HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://tsetmc.com/',
    'Origin': 'https://tsetmc.com',
}


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def fetch_pt(pt):
    j = get(f'{BASE}/ClosingPrice/GetMarketWatch?market=0'
            f'&paperTypes[0]={pt}&showTraded=false'
            '&withBestLimits=false&hEven=0')
    # the API wraps the array under a "marketwatch" key
    rows = j.get('marketwatch') if isinstance(j, dict) else j
    rows = rows or []
    out = {}
    for x in rows:
        ic = x.get('insCode')
        if not ic:
            continue
        nm = (x.get('lvc') or '') + ' ' + (x.get('lva') or '')
        if 'اختيار' in nm or 'اختیار' in nm:
            continue
        out[ic] = (x.get('lva') or '', nm)
    return out


def main():
    print('fetching paperType buckets from TSETMC ...')
    p1 = fetch_pt(1)
    p2 = fetch_pt(2)
    p4 = fetch_pt(4)
    p8 = fetch_pt(8)
    print('  pt=1 (stock) : %d' % len(p1))
    print('  pt=2         : %d' % len(p2))
    print('  pt=4 (right) : %d' % len(p4))
    print('  pt=8 (fund)  : %d' % len(p8))

    # stocks that ALSO appear in the fund bucket
    leaked_to_fund = {ic: p1[ic] for ic in p1 if ic in p8}
    print('\nstocks also present in pt=8 : %d' % len(leaked_to_fund))
    for ic, v in list(leaked_to_fund.items())[:12]:
        print('   ', ic, v[0], '|', v[1][:40])

    # funds that appear in the stock bucket
    leaked_to_stock = {ic: p8[ic] for ic in p8 if ic in p1}
    print('\nfunds also present in pt=1 : %d' % len(leaked_to_stock))
    for ic, v in list(leaked_to_stock.items())[:8]:
        print('   ', ic, v[0], '|', v[1][:40])

    # the specific companies we care about
    print('\n=== where do the big companies land? ===')
    want = ('فولاد', 'وبملت', 'فملي', 'شستا', 'شپنا', 'پارسه', 'خگستر')
    for ic, (sym, nm) in p8.items():
        if sym in want:
            in1 = ic in p1
            print('  %-8s in pt=8 (fund)  also in pt=1? %s   %s' % (sym, in1, nm[:40]))


if __name__ == '__main__':
    main()
