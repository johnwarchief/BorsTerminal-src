# -*- coding: utf-8 -*-
"""Task 1+3: تست کامل روی 3 نماد NEW واقعی (بدون FS در DB). Per-symbol (از `_process_symbol`)"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import codal_fetcher as cf
from pipeline_updater import sanity_fs

DB = cf.DB_PATH
NEW_TICKS = ['ترنج', 'تاديكو', 'توسعه صنعت فضایی کیهان']

def run(sym):
    print(f'=== NEW: {sym} ===', flush=True)
    sess = cf.make_session()
    t0 = time.time()
    try:
        n_notices, n_fs, n_ms, status = cf._process_symbol(sym, sess)
        print(json.dumps({'sym': sym, 'notices': n_notices, 'fs': n_fs,
                          'ms': n_ms, 'status': status, 'sec': round(time.time() - t0, 1)},
                         ensure_ascii=False), flush=True)
    except Exception as e:
        print(json.dumps({'sym': sym, 'err': str(e)[:120]}, ensure_ascii=False), flush=True)

def main():
    for s in NEW_TICKS:
        run(s)
        time.sleep(1)
    # sanity of new rows
    print('=== SANITY NEW ===', flush=True)
    for s in NEW_TICKS:
        print(json.dumps(sanity_fs(s), ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
