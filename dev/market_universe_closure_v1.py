"""رجیسترِ بستنِ universe تبِ بازار — هر ردیفِ Bors با وضعیتِ عضویت.

ورودی‌ها snapshotهایِ زمان‌دارند، نه fetchِ تازه در لحظۀ داوری:
  --bors   پاسخِ /api/market (حداقل ins_code/symbol/name/board/is_live/row_h/...)
  --tsetmc snapshotِ GetMarketWatch (insCode/lva/pdv/pcl/ztt/hEven)

داوری: insCode کلیدِ هویت است، نه نام. هیچ ردیفی از خروجی حذف نمی‌شود؛ ردیفِ
خارج از universeِ زنده با دلیلِ صریح می‌ماند. اعداد برایِ شمردن‌اند، نه اصلاح.
اجرا:  python dev/market_universe_closure_v1.py --bors X.json --tsetmc Y.json \
        --out-csv docs/...csv --out-json reports/...json
"""
import argparse
import csv
import io
import json
import os
import sys

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

DERIVATIVE_MARKERS = ('آتي', 'اختيار', 'سلف موازي', 'بار پايه', 'بارپايه',
                      'بار پيك', 'بارپيك', 'كم باري', 'ميان باري', 'پر باري',
                      'گواهي ظرفيت', 'امتياز')


def _load(path):
    with io.open(path, encoding='utf-8') as f:
        return json.load(f)


def _bors_rows(doc):
    rows = doc.get('data') if isinstance(doc, dict) else doc
    if isinstance(rows, dict):
        rows = rows.get('data') or []
    return rows or []


def _ts_rows(doc):
    rows = doc.get('rows') if isinstance(doc, dict) else doc
    return rows or []


def _outside_class(row):
    text = '%s %s' % (row.get('name') or '', row.get('symbol') or '')
    sector = row.get('sector_name') or ''
    if any(m in text for m in DERIVATIVE_MARKERS) or 'عرضه برق' in sector:
        return 'ENERGY_OR_DERIVATIVE'
    if 'صندوق' in sector or 'صندوق' in text or 'ص.س.' in text:
        return 'FUND_OR_ETF'
    return 'OTHER'


def classify(bors_rows, ts_rows):
    ts = {str(r.get('insCode')): r for r in ts_rows if r.get('insCode')}
    live = {str(r.get('ins_code')): r for r in bors_rows
            if r.get('is_live') and r.get('ins_code')}
    fossil = {str(r.get('ins_code')): r for r in bors_rows
              if not r.get('is_live') and r.get('ins_code')}
    out = []
    for code, r in live.items():
        t = ts.get(code)
        if t:
            status, reason = 'LIVE_MATCHED', 'present in TSETMC watch and Bors live'
        else:
            status = 'LIVE_ONLY_BORS'
            reason = '%s outside TSETMC equity watch' % _outside_class(r)
            if reason.startswith('OTHER'):
                reason = 'live in Bors, absent from this TSETMC watch snapshot'
        out.append(_row(r, t, status, reason))
    for code, r in fossil.items():
        t = ts.get(code)
        if t:
            status = 'STALE_BORS_FOSSIL'
            reason = 'TSETMC tick after Bors final sync; Bors row is not live'
        else:
            status, reason = 'HISTORICAL_FOSSIL', 'not in Bors live set or TSETMC watch'
        out.append(_row(r, t, status, reason))
    for code, t in ts.items():
        if code not in live and code not in fossil:
            out.append({
                'ins_code': code, 'symbol': t.get('lva') or '', 'name': '',
                'board': '', 'is_live': '', 'bors_row_h': '', 'ts_h_even': t.get('hEven') or '',
                'bors_p_last': '', 'ts_pdv': t.get('pdv') or '', 'bors_q_tot_tran': '',
                'ts_q_tot_tran': t.get('qtj') if t.get('qtj') is not None else '',
                'bors_z_tot_tran': '', 'ts_ztt': t.get('ztt') or '',
                'status': 'MISSING_IN_BORS',
                'reason': 'TSETMC instrument absent from Bors table entirely',
            })
    return out


def _row(r, t, status, reason):
    return {
        'ins_code': r.get('ins_code'), 'symbol': r.get('symbol') or '',
        'name': r.get('name') or '', 'board': r.get('board') if r.get('board') is not None else '',
        'is_live': bool(r.get('is_live')),
        'bors_row_h': r.get('row_h') if r.get('row_h') is not None else '',
        'ts_h_even': (t or {}).get('hEven') or '',
        'bors_p_last': r.get('p_last') if r.get('p_last') is not None else '',
        'ts_pdv': (t or {}).get('pdv') or '',
        'bors_q_tot_tran': r.get('q_tot_tran') if r.get('q_tot_tran') is not None else '',
        'ts_q_tot_tran': (t or {}).get('qtj') if (t or {}).get('qtj') is not None else '',
        'bors_z_tot_tran': r.get('z_tot_tran') if r.get('z_tot_tran') is not None else '',
        'ts_ztt': (t or {}).get('ztt') or '',
        'status': status, 'reason': reason,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bors', required=True)
    ap.add_argument('--tsetmc', required=True)
    ap.add_argument('--out-csv', required=True)
    ap.add_argument('--out-json', required=True)
    a = ap.parse_args()
    bdoc, tdoc = _load(a.bors), _load(a.tsetmc)
    rows = classify(_bors_rows(bdoc), _ts_rows(tdoc))
    fields = ['ins_code', 'symbol', 'name', 'board', 'is_live', 'bors_row_h',
              'ts_h_even', 'bors_p_last', 'ts_pdv', 'bors_q_tot_tran',
              'ts_q_tot_tran', 'bors_z_tot_tran', 'ts_ztt', 'status', 'reason']
    with io.open(a.out_csv, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    counts = Counter(r['status'] for r in rows)
    boards = Counter(str(r['board']) for r in rows if not r['is_live'])
    summary = {
        'bors_meta': {k: bdoc.get(k) for k in ('meta', 'count', 'live_count', 'fossil_count')},
        'tsetmc_meta': {k: tdoc.get(k) for k in ('fetched_at', 'count') if k in tdoc},
        'counts': dict(counts),
        'fossil_boards': dict(boards),
        'live_only_by_reason': dict(Counter(r['reason'] for r in rows
                                            if r['status'] == 'LIVE_ONLY_BORS')),
        'register_rows': len(rows),
        'out_csv': a.out_csv,
    }
    with io.open(a.out_json, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
