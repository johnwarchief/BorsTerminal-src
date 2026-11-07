"""تطبیقِ فیلدبه‌فیلدِ snapshotهایِ ذخیره‌شده — با تفکیکِ same-tick و تیکِ بعدی.

این ابزار شبکه/DB نمی‌زند؛ دو snapshotِ زمان‌دار می‌گیرد و فقط همان‌ها را
می‌سنجد. ردیفی که `row_h`ش با `hEven` منبع یکی نیست، «اختلافِ تیک» است نه
باگِ محاسبه؛ جدا شمرده می‌شود تا مخرج پنهان نشود.

اجرا:
  python dev/market_postclose_parity_v1.py \
    --bors reports/.../bors-board.json --tsetmc reports/.../tsetmc.json \
    --out reports/.../postclose-field-parity.json
"""
import argparse
import io
import json
import os
import sys

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

FIELDS = (
    ('p_last', 'p_last', 'pdv'),
    ('p_closing', 'p_closing', 'pcl'),
    ('price_yesterday', 'price_yesterday', 'py'),
    ('p_first', 'p_first', 'pf'),
    ('p_max', 'p_max', 'pmx'),
    ('p_min', 'p_min', 'pmn'),
    ('tmin', 'tmin', 'pMin'),
    ('price_change', 'price_change', 'pc'),
    ('q_tot_tran', 'q_tot_tran', 'qtj'),
    ('q_tot_cap', 'q_tot_cap', 'qtc'),
    ('z_tot_tran', 'z_tot_tran', 'ztt'),
)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bors', required=True)
    ap.add_argument('--tsetmc', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    b = json.load(io.open(a.bors, encoding='utf-8'))
    t = json.load(io.open(a.tsetmc, encoding='utf-8'))
    ts = {str(r.get('insCode')): r for r in t.get('rows') or [] if r.get('insCode')}
    live = [r for r in b.get('data') or [] if r.get('is_live')]
    joined = [(r, ts[str(r.get('ins_code'))]) for r in live
              if str(r.get('ins_code')) in ts]
    out = {
        'observed': {
            'bors_sync': (b.get('meta') or {}).get('last_sync'),
            'tsetmc_fetched_at': t.get('fetched_at'),
            'bors_live': len(live), 'tsetmc': len(ts), 'joined': len(joined),
            'same_tick': sum(1 for r, x in joined
                             if _num(r.get('row_h')) == _num(x.get('hEven'))),
        },
        'fields': {},
    }
    for name, bk, tk in FIELDS:
        stats = {k: {'compared': 0, 'agree': 0, 'differ': 0, 'missing': 0, 'examples': []}
                 for k in ('all', 'same_tick', 'later_tick')}
        for r, x in joined:
            tick = ('same_tick' if _num(r.get('row_h')) == _num(x.get('hEven'))
                    else 'later_tick')
            for key in ('all', tick):
                st = stats[key]
                bv, sv = _num(r.get(bk)), _num(x.get(tk))
                if bv is None or sv is None:
                    st['missing'] += 1
                elif bv == sv:
                    st['agree'] += 1
                else:
                    st['differ'] += 1
                    if len(st['examples']) < 5:
                        st['examples'].append(
                            {'symbol': r.get('symbol'), 'bors': bv, 'source': sv})
                st['compared'] += 1
        for st in stats.values():
            st['exact_rate'] = round(st['agree'] / st['compared'], 6) if st['compared'] else None
        out['fields'][name] = stats
    sums = {}
    for name, bk, tk in (('volume', 'q_tot_tran', 'qtj'),
                         ('value', 'q_tot_cap', 'qtc'),
                         ('trades', 'z_tot_tran', 'ztt')):
        diff_rows = sum(1 for r, x in joined if _num(r.get(bk)) != _num(x.get(tk)))
        sums[name] = {
            'bors': round(sum(_num(r.get(bk)) or 0 for r, _ in joined), 2),
            'source': round(sum(_num(x.get(tk)) or 0 for _, x in joined), 2),
            'diff_rows': diff_rows,
        }
    out['sums'] = sums
    with io.open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({'observed': out['observed'],
                      'same_tick_diffs': {k: v['same_tick']['differ']
                                          for k, v in out['fields'].items()},
                      'later_tick_diffs': {k: v['later_tick']['differ']
                                           for k, v in out['fields'].items()}},
                     ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
