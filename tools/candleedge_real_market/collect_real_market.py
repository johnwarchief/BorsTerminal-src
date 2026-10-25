"""Collect real BorsTerminal candles for the CandleEdge research harness.

Reads a **copy** of market.db through the production `api.chart.get_chart_db`
path (raw candles + production adjustment factors). Never writes to the
operational database: `BORS_DB` and `BORS_WORK_DIR` are set before importing
the app, and the input must be a file outside the live install.

Usage:
  python tools/candleedge_real_market/collect_real_market.py \
      --db <path-to-market.db-copy> \
      --work <empty-temp-dir> \
      --out <ndjson> \
      --min-bars 250 --short-sample 30 --workers 3
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sqlite3
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

SCHEMA = 'candleedge-real-market/v1'
_SHORT_LOW, _SHORT_HIGH = 60, 120
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _canonical_candle(c: dict) -> str:
    return 'C|%s|%.6f|%.6f|%.6f|%.6f|%d' % (
        str(c['time'])[:10],
        float(c['open']), float(c['high']), float(c['low']), float(c['close']),
        round(float(c.get('volume') or 0.0)),
    )


def input_hash(candles: list[dict], factors: list[dict]) -> str:
    """Cross-language hash definition, mirrored by the TypeScript harness."""
    parts = [_canonical_candle(c) for c in candles]
    parts.append('F')
    for f in factors:
        parts.append('F|%s|%.6f' % (str(f.get('time'))[:10], float(f.get('factor', 0.0))))
    return hashlib.sha256('\n'.join(parts).encode('utf-8')).hexdigest()


def load_universe(db_path: str, min_bars: int, short_sample: int) -> tuple[list[dict], dict]:
    import symbol_identity  # stdlib-only repository module

    con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    try:
        rows = con.execute(
            """
            SELECT symbol, COUNT(*) AS rows,
                   MIN(date) AS first_date, MAX(date) AS last_date,
                   SUM(CASE WHEN volume IS NULL OR volume <= 0 THEN 1 ELSE 0 END) AS zero_vol,
                   AVG(CASE WHEN volume > 0 THEN COALESCE(value, volume * close) END) AS avg_turnover
            FROM price_history
            WHERE symbol IS NOT NULL AND TRIM(symbol) <> ''
            GROUP BY symbol
            HAVING COUNT(*) >= 1
            """
        ).fetchall()
        meta = {}
        for symbol, *rest in con.execute(
            'SELECT l_val18, sector_name, paper_type FROM instruments WHERE l_val18 IS NOT NULL'
        ):
            meta.setdefault(symbol, {'sector': rest[0], 'paperType': rest[1]})
    finally:
        con.close()

    grouped: dict[str, dict] = {}
    for symbol, n, first_date, last_date, zero_vol, avg_turnover in rows:
        k = symbol_identity.key(symbol)
        if not k:
            continue
        item = {
            'symbol': symbol,
            'rows': int(n),
            'firstDate': first_date,
            'lastDate': last_date,
            'zeroVolumeRows': int(zero_vol or 0),
            'avgTurnover': float(avg_turnover or 0.0),
            **meta.get(symbol, {}),
        }
        prev = grouped.get(k)
        if prev is None:
            item['aliasCount'] = 1
            grouped[k] = item
        else:
            prev['aliasCount'] += 1
            if item['rows'] > prev['rows']:
                item['aliasCount'] = prev['aliasCount']
                grouped[k] = item

    items = sorted(grouped.values(), key=lambda x: (-x['rows'], x['symbol']))
    for x in items:
        if x['rows'] >= 400:
            x['historyBand'] = '400+'
        elif x['rows'] >= 250:
            x['historyBand'] = '250-399'
        elif x['rows'] >= _SHORT_HIGH:
            x['historyBand'] = '120-249'
        elif x['rows'] >= _SHORT_LOW:
            x['historyBand'] = '60-120'
        else:
            x['historyBand'] = 'under-60'
    full = [x for x in items if x['rows'] >= min_bars]
    short_pool = [x for x in items if _SHORT_LOW <= x['rows'] <= _SHORT_HIGH]
    short = short_pool[:: max(1, len(short_pool) // max(1, short_sample))][:short_sample]

    turnovers = sorted(x['avgTurnover'] for x in full if x['avgTurnover'] > 0)
    def band(value: float) -> str:
        if not turnovers or value <= 0:
            return 'unknown'
        rank = sum(1 for t in turnovers if t <= value) / len(turnovers)
        if rank <= 0.25:
            return 'Q1-low'
        if rank <= 0.5:
            return 'Q2'
        if rank <= 0.75:
            return 'Q3'
        return 'Q4-high'

    for x in full:
        x['historyBand'] = '400+' if x['rows'] >= 400 else '250-399'
        x['liquidityBand'] = band(x['avgTurnover'])
        x['stratum'] = 'full'
    for x in short:
        x['historyBand'] = '60-120'
        x['liquidityBand'] = band(x['avgTurnover'])
        x['stratum'] = 'short'

    covered_rows = sum(x['rows'] for x in full)
    summary = {
        'allSymbols': len(items),
        'fullSymbols': len(full),
        'shortSymbols': len(short),
        'minBars': min_bars,
        'fullRows': covered_rows,
        'fullFirstDate': min((x['firstDate'] for x in full), default=None),
        'fullLastDate': max((x['lastDate'] for x in full), default=None),
        'liquidityBands': {b: sum(1 for x in full if x['liquidityBand'] == b)
                           for b in ('Q1-low', 'Q2', 'Q3', 'Q4-high', 'unknown')},
        'historyBands': {b: sum(1 for x in items if x['historyBand'] == b)
                         for b in ('400+', '250-399', '120-249', '60-120', 'under-60')},
        'turnoverDefinition': 'avg(COALESCE(value, volume*close)) on volume>0 rows',
    }
    return full + short, summary


def _collect_one(item: dict) -> dict:
    import api.chart as chart

    started = time.perf_counter()
    out = {
        'schema': SCHEMA,
        'symbol': item['symbol'],
        'collectedAt': _dt.datetime.now(_dt.timezone.utc).isoformat(timespec='seconds'),
        'universe': item,
        'collector': 'api.chart.get_chart_db',
    }
    try:
        payload = chart.get_chart_db(item['symbol'])
    except Exception as exc:  # collector must report, never silently drop
        out.update({'status': 'error', 'error': f'{type(exc).__name__}: {exc}'})
        out['runtimeMs'] = round((time.perf_counter() - started) * 1000, 1)
        return out

    if not isinstance(payload, dict) or payload.get('status') != 'success':
        out.update({
            'status': 'error',
            'error': str((payload or {}).get('message') if isinstance(payload, dict) else payload),
        })
        out['runtimeMs'] = round((time.perf_counter() - started) * 1000, 1)
        return out

    raw = []
    for c in payload.get('candles') or []:
        raw.append({
            'time': str(c.get('time'))[:10],
            'open': float(c['open']), 'high': float(c['high']),
            'low': float(c['low']), 'close': float(c['close']),
            'volume': float(c.get('volume') or 0.0),
        })
    factors = [
        {'time': str(f.get('time'))[:10], 'factor': float(f.get('factor'))}
        for f in payload.get('factors') or []
    ]
    cap = payload.get('adjustCapability') or {}
    out.update({
        'status': 'success',
        'candleCount': len(raw),
        'firstDate': raw[0]['time'] if raw else None,
        'lastDate': raw[-1]['time'] if raw else None,
        'rawCandles': raw,
        'factors': factors,
        'factorCount': len(factors),
        'adjustEvents': payload.get('adjustEvents') or [],
        'adjustRejected': payload.get('adjustRejected') or [],
        'adjustSource': payload.get('adjustSource'),
        'adjustCapability': cap,
        'corporateEventCount': len(payload.get('corporateEvents') or []),
        'dbRows': payload.get('dbRows'),
        'dbNoTradeRows': payload.get('dbNoTradeRows'),
        'dbInvalidRows': payload.get('dbInvalidRows'),
        'liveInjected': bool(payload.get('liveInjected')),
        'liveError': payload.get('liveError'),
        'priceBasis': payload.get('priceBasis'),
        'priceBasisNote': payload.get('priceBasisNote'),
        'ftsPresent': bool(payload.get('fts')),
        'inputSha256': input_hash(raw, factors),
    })
    out['runtimeMs'] = round((time.perf_counter() - started) * 1000, 1)
    return out


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--work', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--min-bars', type=int, default=250)
    ap.add_argument('--short-sample', type=int, default=30)
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--limit', type=int, default=0, help='smoke-test cap on records')
    args = ap.parse_args(argv)

    db = os.path.abspath(args.db)
    work = os.path.abspath(args.work)
    if not os.path.isfile(db):
        print(f'missing db: {db}', file=sys.stderr)
        return 2
    os.makedirs(work, exist_ok=True)
    os.environ['BORS_DB'] = db
    os.environ['BORS_WORK_DIR'] = work
    os.environ['BORS_NO_FETCH_LOOPS'] = '1'
    os.environ['BORS_CODAL_OFFLINE'] = '1'
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

    universe, summary = load_universe(db, args.min_bars, args.short_sample)
    if args.limit > 0:
        universe = universe[:args.limit]
    summary['selected'] = len(universe)
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + '.part')
    started = time.perf_counter()
    done = 0
    errors = 0
    with tmp_path.open('w', encoding='utf-8', newline='\n') as fh:
        if args.workers <= 1:
            iterator = (_collect_one(item) for item in universe)
        else:
            pool = ProcessPoolExecutor(max_workers=args.workers)
            iterator = pool.map(_collect_one, universe, chunksize=1)
        for rec in iterator:
            if rec.get('status') != 'success':
                errors += 1
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n')
            done += 1
            if done % 25 == 0:
                print(f'[{done}/{len(universe)}] errors={errors} '
                      f'elapsed={time.perf_counter() - started:.0f}s', file=sys.stderr)
        if args.workers > 1:
            pool.shutdown(wait=True)
    tmp_path.replace(out_path)
    summary.update({
        'records': done,
        'errors': errors,
        'seconds': round(time.perf_counter() - started, 1),
        'out': str(out_path),
    })
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)
    return 0 if done else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
