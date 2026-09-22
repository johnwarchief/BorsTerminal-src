"""Classify the three flags from the sweep: real bug vs expected behavior.

1. pct_out_of_range  — |percent_change| > 30. TSETMC allows +/-35% for
   suspicious symbols and funds can move more. Check the actual distribution
   and whether price_change / price_yesterday reproduces the number.
2. power_zero_with_volume — buyer_power 0 while tvol > 0. This is the
   formula's zero-denominator case; verify it is genuinely undefined rather
   than a dropped value.
3. stale_d_even — d_even != today. Determine which symbols and whether they
   are suspended or just untraded today.
"""
import json
import math
import urllib.request

API = 'http://127.0.0.1:8001'


def fetch(path):
    with urllib.request.urlopen(API + path, timeout=120) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    j = fetch('/api/market')
    rows = j.get('data') or j.get('items') or j.get('rows') or []

    # ---- 1. percent_change consistency ----
    print('=== percent_change vs price_change/price_yesterday ===')
    bad, ok, missing = [], 0, 0
    for r in rows:
        pc, py, pct = r.get('price_change'), r.get('price_yesterday'), r.get('percent_change')
        if pc is None or py in (None, 0) or pct is None:
            missing += 1
            continue
        calc = round(pc / py * 100.0, 2)
        if abs(calc - pct) > 0.05:
            bad.append((r['symbol'], pct, calc))
        else:
            ok += 1
    print('  consistent: %d | inconsistent: %d | missing inputs: %d' % (ok, len(bad), missing))
    for x in bad[:8]:
        print('   ', x)

    print('\n=== percent_change distribution ===')
    buckets = {}
    for r in rows:
        v = r.get('percent_change')
        if not isinstance(v, (int, float)):
            continue
        b = int(math.floor(v / 5) * 5)
        buckets[b] = buckets.get(b, 0) + 1
    for k in sorted(buckets):
        print('  %+4d%% .. %+4d%% : %d' % (k, k + 5, buckets[k]))

    # ---- 2. buyer_power zero with volume ----
    print('\n=== buyer_power == 0 with tvol > 0 ===')
    n = 0
    examples = []
    for r in rows:
        tvol, bp = r.get('tvol'), r.get('buyer_power')
        if isinstance(tvol, (int, float)) and tvol > 0 and bp == 0:
            n += 1
            if len(examples) < 5:
                examples.append((r['symbol'], tvol, bp,
                                 r.get('buy_power_i'), r.get('sell_power_i'),
                                 r.get('buy_count_i'), r.get('sell_count_i')))
    print('  count:', n)
    for e in examples:
        print('   ', e)

    # ---- 3. stale d_even ----
    print('\n=== d_even staleness ===')
    days = {}
    for r in rows:
        d = str(r.get('d_even') or '')
        days[d] = days.get(d, 0) + 1
    for k in sorted(days, reverse=True)[:6]:
        print('  %s : %d' % (k, days[k]))

    # of the stale ones, how many have zero volume (untraded)?
    stale_untraded = stale_traded = 0
    for r in rows:
        d = str(r.get('d_even') or '')
        if d not in ('20260921', '20260922'):
            if (r.get('tvol') or 0) == 0:
                stale_untraded += 1
            else:
                stale_traded += 1
    print('  stale + zero volume (untraded/suspended): %d' % stale_untraded)
    print('  stale + volume > 0 (traded on an older day): %d' % stale_traded)


if __name__ == '__main__':
    main()
