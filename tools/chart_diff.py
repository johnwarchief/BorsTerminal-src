"""مقایسهٔ خروجِ /api/chart بین بیلدِ نصب‌شده و سورسِ وصله‌شده."""
import sys

import requests

S = requests.Session()
S.headers['User-Agent'] = 'Mozilla/5.0'


def bad_candles(d):
    return sum(1 for x in d.get('candles', [])
               if not (x['low'] <= x['open'] <= x['high']
                       and x['low'] <= x['close'] <= x['high']))


def comp_max_drift(d):
    """بیشترین نسبتِ سایه به بدنه — نشانهٔ گِشاد شدنِ سایه."""
    worst = 0.0
    for x in d.get('candles', []):
        body = abs(x['close'] - x['open']) or 1
        r = (x['high'] - x['low']) / body
        worst = max(worst, r)
    return worst


def main(old, new):
    syms = sys.argv[3:] or ['فولاد', 'آسود', 'آسود2', 'اعتماد4', 'آبادا3',
                            'اخابر', 'خودرو', 'وبملت', 'البرز', 'اميد']
    print(f"{'نماد':<10}{'کندل':>7}{'هندسی‌خراب':>16}{'رویداد':>14}  adjustSource")
    for sym in syms:
        try:
            a = S.get(f'http://127.0.0.1:{old}/api/chart/{sym}', timeout=240).json()
            b = S.get(f'http://127.0.0.1:{new}/api/chart/{sym}', timeout=240).json()
        except Exception as e:
            print(f'{sym:<10} ERR {e}')
            continue
        if a.get('status') != 'success' or b.get('status') != 'success':
            print(f"{sym:<10} status={a.get('status')}/{b.get('status')} "
                  f"{str(b.get('message', ''))[:70]}")
            continue
        print(f"{sym:<10}{b['count']:>7}"
              f"{f'{bad_candles(a)} -> {bad_candles(b)}':>16}"
              f"{f'{len(a['adjustEvents'])} -> {len(b['adjustEvents'])}':>14}"
              f"  {a.get('adjustSource')} | {b.get('adjustSource')}")
        closes_a = {c['time']: c['close'] for c in a['candles']}
        closes_b = {c['time']: c['close'] for c in b['candles']}
        diff = [t for t in closes_a if closes_b.get(t) != closes_a[t]]
        print(f"{'':10} پایانیِ تغییریافته: {len(diff)} (باید ۰ باشد)"
              f"  فاکتورِ قدیمی‌ترین: {a['factors'][-1]['factor']} -> {b['factors'][-1]['factor']}")


if __name__ == '__main__':
    main(int(sys.argv[1]), int(sys.argv[2]))
