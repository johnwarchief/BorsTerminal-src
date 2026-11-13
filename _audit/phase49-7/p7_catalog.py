# -*- coding: utf-8 -*-
"""Phase 4.9.7 Part 1 — read-only catalog of every JSONL in the Rahavard archive.
Counts records, sums bar counts (n), verifies schema uniformity. Never writes to source.
"""
import os, re, json, sys, time

SRC = r"D:/BorsTerminal-worktrees/phase49-5-resume/_audit/phase49-5/api-all"
OUT = r"D:/BorsTerminal-worktrees/phase49-7-discovery/_audit/phase49-7"
N_RE = re.compile(r'"n":\s*(\d+)')
AID_RE = re.compile(r'"asset_id":\s*"?(\d+)"?')

def scan_bars(path):
    size = os.path.getsize(path)
    lines = 0
    sum_n = 0
    first = None
    last_aid = None
    rec_keys = None
    bar_keys = None
    aid_set_seen_dup = False
    seen = set()
    t0 = time.time()
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line:
                continue
            lines += 1
            prefix = line.split('"bars":', 1)[0]
            m = N_RE.search(prefix)
            n = int(m.group(1)) if m else 0
            sum_n += n
            am = AID_RE.search(prefix)
            aid = am.group(1) if am else None
            if aid is not None:
                if aid in seen:
                    aid_set_seen_dup = True
                else:
                    seen.add(aid)
                last_aid = aid
            if first is None:
                o = json.loads(line)
                rec_keys = list(o.keys())
                first = {k: o[k] for k in ('asset_id', 'trade_symbol', 'name', 'n') if k in o}
                if o.get('bars'):
                    bar_keys = list(o['bars'][0].keys())
    return {
        'file': os.path.basename(path), 'size_bytes': size, 'records': lines,
        'total_bars': sum_n, 'distinct_asset_ids': len(seen),
        'dup_asset_lines': aid_set_seen_dup, 'record_keys': rec_keys,
        'bar_keys': bar_keys, 'first_record': first, 'last_asset_id': last_aid,
        'scan_s': round(time.time() - t0, 1),
    }

def scan_errors(path):
    size = os.path.getsize(path)
    lines = 0
    statuses = {}
    keys = None
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lines += 1
            o = json.loads(line)
            if keys is None:
                keys = list(o.keys())
            s = str(o.get('status', o.get('err', '?')))
            statuses[s] = statuses.get(s, 0) + 1
    return {'file': os.path.basename(path), 'size_bytes': size, 'records': lines,
            'record_keys': keys, 'status_dist': statuses}

def main():
    files = sorted(os.listdir(SRC))
    bars = [f for f in files if f.startswith('bars_') and f.endswith('.jsonl')]
    orig = [f for f in files if f.endswith('.jsonl.orig')]
    catalog = {'source_dir': SRC, 'bars_files': [], 'orig_files': [], 'errors': None}
    print('START catalog: %d bars files, %d orig' % (len(bars), len(orig)), flush=True)
    for i, fn in enumerate(bars):
        r = scan_bars(os.path.join(SRC, fn))
        catalog['bars_files'].append(r)
        print('[%d/%d] %s records=%d bars=%d dup=%s %.1fs' % (
            i + 1, len(bars), fn, r['records'], r['total_bars'], r['dup_asset_lines'], r['scan_s']), flush=True)
        with open(os.path.join(OUT, 'catalog_jsonl.json'), 'w', encoding='utf-8') as o:
            json.dump(catalog, o, ensure_ascii=False, indent=1)
    for fn in orig:
        r = scan_bars(os.path.join(SRC, fn))
        catalog['orig_files'].append(r)
        print('[orig] %s records=%d bars=%d' % (fn, r['records'], r['total_bars']), flush=True)
    if 'errors.jsonl' in files:
        catalog['errors'] = scan_errors(os.path.join(SRC, 'errors.jsonl'))
        print('[errors] records=%d' % catalog['errors']['records'], flush=True)
    # uniformity check
    keysets = {tuple(b['record_keys']) for b in catalog['bars_files']}
    barsets = {tuple(b['bar_keys']) for b in catalog['bars_files']}
    catalog['schema_uniform'] = {'record_key_variants': len(keysets), 'bar_key_variants': len(barsets),
                                 'record_keys': sorted(keysets)[0] if keysets else None,
                                 'bar_keys': sorted(barsets)[0] if barsets else None}
    catalog['totals'] = {'bars_files': len(catalog['bars_files']),
                         'total_records': sum(b['records'] for b in catalog['bars_files']),
                         'total_bars': sum(b['total_bars'] for b in catalog['bars_files']),
                         'total_bytes': sum(b['size_bytes'] for b in catalog['bars_files'])}
    with open(os.path.join(OUT, 'catalog_jsonl.json'), 'w', encoding='utf-8') as o:
        json.dump(catalog, o, ensure_ascii=False, indent=1)
    print('DONE', json.dumps(catalog['totals']), 'uniform=', catalog['schema_uniform']['record_key_variants'], catalog['schema_uniform']['bar_key_variants'], flush=True)

if __name__ == '__main__':
    main()