# -*- coding: utf-8 -*-
"""Phase 4.9.7 Part 2 — read-only evidence for the 10 Phase-4.9.6 ambiguities.
Indexed point-queries only (fast); coverage-by-type from offline Phase-4.9.6 artifact.
Never writes to the reference DB.
"""
import os, json, sqlite3
from collections import Counter, defaultdict

DB = r"D:/BorsTerminal-worktrees/phase49-5-resume/_audit/phase49-5/api-all/reference_all.db"
P6 = r"D:/BorsTerminal-worktrees/phase49-6-classification/_audit/phase49-6"
OUT = r"D:/BorsTerminal-worktrees/phase49-7-discovery/_audit/phase49-7"
c = sqlite3.connect('file:' + DB + '?mode=ro&immutable=1', uri=True)

def series(aid, res, basis, adj):
    return {t: cl for t, cl in c.execute(
        "SELECT t,c FROM candles WHERE asset_id=? AND res=? AND basis=? AND adj=? ORDER BY t",
        (aid, res, basis, adj))}

def ohlc(aid, res, basis, adj):
    return list(c.execute(
        "SELECT t,o,h,l,c,v FROM candles WHERE asset_id=? AND res=? AND basis=? AND adj=? ORDER BY t",
        (aid, res, basis, adj)))

ev = {}

# ---- #8 coverage by asset type (offline artifact) ----
amap = json.load(open(os.path.join(P6, 'asset_map_candle_assets.json'), encoding='utf-8'))
by_type = defaultdict(lambda: {'assets': 0, 'rows': 0, 'full63': 0, 'with_symbol': 0})
for a in amap:
    t = a.get('type_name') or a.get('type_id')
    d = by_type[t]
    d['assets'] += 1
    d['rows'] += a.get('candle_rows', 0)
    if a.get('modes_count') == 63: d['full63'] += 1
    if a.get('trade_symbol'): d['with_symbol'] += 1
ev['coverage_by_type'] = dict(sorted(by_type.items(), key=lambda kv: -kv[1]['rows']))
ev['total_assets_with_data'] = len(amap)

# ---- #1/#2 basis comparison: real_close vs close vs last (D/type0) ----
basis_assets = [591, 461, 451, 66, 291, 419, 2]
bc = {}
for aid in basis_assets:
    rc = series(aid, 'D', 'real_close', 'type0')
    cl = series(aid, 'D', 'close', 'type0')
    la = series(aid, 'D', 'last', 'type0')
    common = set(rc) & set(cl) & set(la)
    eq_rc_cl = sum(1 for t in common if rc[t] == cl[t])
    eq_rc_la = sum(1 for t in common if rc[t] == la[t])
    eq_cl_la = sum(1 for t in common if cl[t] == la[t])
    diffs = [(t, rc[t], cl[t], la[t]) for t in sorted(common) if rc[t] != cl[t]][:3]
    bc[str(aid)] = {'common_bars': len(common), 'real_close==close': eq_rc_cl,
                    'real_close==last': eq_rc_la, 'close==last': eq_cl_la,
                    'sample_rc_cl_diff': diffs}
ev['basis_compare'] = bc

# ---- #3 adjustment comparison: type0 vs type5 vs type7 (D/close) ----
adj_assets = [591, 461, 451, 66]
ac = {}
for aid in adj_assets:
    a0 = series(aid, 'D', 'close', 'type0')
    a5 = series(aid, 'D', 'close', 'type5')
    a7 = series(aid, 'D', 'close', 'type7')
    common = set(a0) & set(a5) & set(a7)
    eq05 = sum(1 for t in common if a0[t] == a5[t])
    eq07 = sum(1 for t in common if a0[t] == a7[t])
    eq57 = sum(1 for t in common if a5[t] == a7[t])
    # earliest divergence samples
    d05 = [(t, a0[t], a5[t]) for t in sorted(common) if a0[t] != a5[t]][:2]
    d07 = [(t, a0[t], a7[t]) for t in sorted(common) if a0[t] != a7[t]][:2]
    ac[str(aid)] = {'common_bars': len(common), 'type0==type5': eq05, 'type0==type7': eq07,
                    'type5==type7': eq57, 'sample_05_diff': d05, 'sample_07_diff': d07}
ev['adj_compare'] = ac

# ---- #4 USD & market_cap ratios + dollar asset rate ----
usd = {}
for aid in [591, 461, 451]:
    cl = series(aid, 'D', 'close', 'type0')
    clu = series(aid, 'D', 'close_usd', 'type0')
    mc = series(aid, 'D', 'market_cap', 'type0')
    mcu = series(aid, 'D', 'market_cap_usd', 'type0')
    la = series(aid, 'D', 'last', 'type0')
    lau = series(aid, 'D', 'last_usd', 'type0')
    common = set(cl) & set(clu) & set(mc) & set(mcu) & set(la) & set(lau)
    ts = sorted(common)[-3:]
    rows = []
    for t in ts:
        rows.append({'t': t, 'close': cl[t], 'close_usd': clu[t],
                     'close/close_usd': (cl[t] / clu[t]) if clu[t] else None,
                     'market_cap': mc[t], 'market_cap_usd': mcu[t],
                     'mcap/mcap_usd': (mc[t] / mcu[t]) if mcu[t] else None,
                     'last': la[t], 'last_usd': lau[t], 'last_usd==last': lau[t] == la[t]})
    usd[str(aid)] = rows
# dollar asset (id=2) close = candidate USD rate in rial
dollar = series(2, 'D', 'close', 'type0')
dollar_rc = series(2, 'D', 'real_close', 'type0')
last_ts = sorted(set(cl) & set(dollar))[-3:] if (cl := series(591, 'D', 'close', 'type0')) else []
ev['usd_ratios'] = usd
ev['dollar_asset_id2'] = {'last_close_samples': [(t, dollar.get(t)) for t in sorted(dollar)[-3:]],
                          'aligned_to_591': [(t, dollar.get(t)) for t in last_ts]}

# ---- #5 W/M zero-price characterization (fund assets) ----
zero = {}
for aid in [1636, 1586, 1601]:
    rows = ohlc(aid, 'M', 'close', 'type0')
    z = [r for r in rows if r[4] == 0]
    nz = [r for r in rows if r[4] > 0]
    zv = Counter(r[5] for r in z)
    # timestamp spacing of zero bars
    zt = sorted(r[0] for r in z)
    gaps = Counter((zt[i+1] - zt[i]) // 86400000 for i in range(len(zt)-1)) if len(zt) > 1 else {}
    zero[str(aid)] = {'total_bars': len(rows), 'zero_close': len(z), 'nonzero_close': len(nz),
                      'zero_bar_volume_dist': dict(zv.most_common(5)),
                      'zero_gap_days_top': dict(gaps.most_common(5)),
                      'sample_zero': [list(r) for r in z[:2]], 'sample_nonzero': [list(r) for r in nz[:2]]}
ev['zero_char_M'] = zero

# ---- #6 duplicate-t characterization (source behavior) ----
dup = {}
for aid in [1709, 27056]:
    rows = ohlc(aid, 'D', 'real_close', 'type0')
    byt = defaultdict(list)
    for r in rows: byt[r[0]].append(r)
    dups = {t: v for t, v in byt.items() if len(v) > 1}
    identical = sum(1 for v in dups.values() if all(x == v[0] for x in v))
    conflicting = len(dups) - identical
    sample = [(t, [list(x) for x in v]) for t, v in list(dups.items())[:2]]
    dup[str(aid)] = {'total_bars': len(rows), 'distinct_t': len(byt), 'dup_t': len(dups),
                     'identical_dup_groups': identical, 'conflicting_dup_groups': conflicting,
                     'sample': sample}
ev['dup_char'] = dup

c.close()
with open(os.path.join(OUT, 'ambiguity_evidence.json'), 'w', encoding='utf-8') as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print('EVIDENCE_DONE', flush=True)
print('coverage_by_type:', json.dumps(ev['coverage_by_type'], ensure_ascii=False), flush=True)
print('basis_compare:', json.dumps(ev['basis_compare'], ensure_ascii=False), flush=True)
print('adj_compare:', json.dumps(ev['adj_compare'], ensure_ascii=False), flush=True)
print('dollar_asset_id2:', json.dumps(ev['dollar_asset_id2'], ensure_ascii=False), flush=True)