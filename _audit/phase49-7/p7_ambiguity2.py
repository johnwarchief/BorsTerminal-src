# -*- coding: utf-8 -*-
"""Phase 4.9.7 Part 2 follow-up — verify W/M dup-t == t=0 padding, broaden
type0/type5/type7 equality across asset types, confirm OHLC anomalies source-level.
Read-only indexed queries."""
import os, json, sqlite3
from collections import defaultdict, Counter

DB = r"D:/BorsTerminal-worktrees/phase49-5-resume/_audit/phase49-5/api-all/reference_all.db"
P6 = r"D:/BorsTerminal-worktrees/phase49-6-classification/_audit/phase49-6"
OUT = r"D:/BorsTerminal-worktrees/phase49-7-discovery/_audit/phase49-7"
c = sqlite3.connect('file:' + DB + '?mode=ro&immutable=1', uri=True)
ev = {}

def rows(aid, res, basis, adj):
    return list(c.execute("SELECT t,o,h,l,c,v FROM candles WHERE asset_id=? AND res=? AND basis=? AND adj=? ORDER BY t",
                          (aid, res, basis, adj)))

# ---- W/M dup-t == t=0 padding? (fund 1636) ----
for res in ['M', 'W']:
    rr = rows(1636, res, 'close', 'type0')
    byt = defaultdict(list)
    for r in rr: byt[r[0]].append(r)
    dupgroups = {t: v for t, v in byt.items() if len(v) > 1}
    t0_count = sum(1 for r in rr if r[0] == 0)
    dup_t0 = sum(1 for t in dupgroups if t == 0)
    dup_realt = sum(1 for t in dupgroups if t != 0)
    ev.setdefault('wm_dup_t0', {})[res] = {
        'total_bars': len(rr), 't0_bars': t0_count, 'distinct_t': len(byt),
        'dup_groups': len(dupgroups), 'dup_groups_t0': dup_t0, 'dup_groups_real_t': dup_realt,
        't0_group_size': len(byt.get(0, []))}

# ---- broaden type0/type5/type7 across types ----
amap = json.load(open(os.path.join(P6, 'asset_map_candle_assets.json'), encoding='utf-8'))
by_type = defaultdict(list)
for a in amap:
    if a.get('candle_rows', 0) > 1000:
        by_type[a.get('type_name')].append(a['asset_id'])
sample = []
for t, ids in by_type.items():
    sample += [(t, aid) for aid in ids[:4]]
adj_broad = []
for tname, aid in sample:
    a0 = {t: cl for t, cl in c.execute("SELECT t,c FROM candles WHERE asset_id=? AND res='D' AND basis='close' AND adj='type0'", (aid,))}
    a5 = {t: cl for t, cl in c.execute("SELECT t,c FROM candles WHERE asset_id=? AND res='D' AND basis='close' AND adj='type5'", (aid,))}
    a7 = {t: cl for t, cl in c.execute("SELECT t,c FROM candles WHERE asset_id=? AND res='D' AND basis='close' AND adj='type7'", (aid,))}
    common = set(a0) & set(a5) & set(a7)
    if not common:
        adj_broad.append({'type': tname, 'asset_id': aid, 'common': 0}); continue
    eq05 = sum(1 for t in common if a0[t] == a5[t])
    eq07 = sum(1 for t in common if a0[t] == a7[t])
    adj_broad.append({'type': tname, 'asset_id': aid, 'common': len(common),
                      'type0==type5': eq05, 'type0==type7': eq07,
                      'pct05': round(100*eq05/len(common), 1), 'pct07': round(100*eq07/len(common), 1)})
ev['adj_broad'] = adj_broad
n = len([x for x in adj_broad if x.get('common')])
full05 = sum(1 for x in adj_broad if x.get('common') and x['type0==type5'] == x['common'])
ev['adj_broad_summary'] = {'sampled': n, 'type0_fully_eq_type5': full05}

# ---- #7 OHLC anomalies source-level (D/close/type7 untouched) ----
anom = {}
for aid in [591, 461, 66]:
    rr = rows(aid, 'D', 'close', 'type7')
    hl = [r for r in rr if r[2] < r[3]]
    rng = [r for r in rr if r[4] > r[2] or r[4] < r[3] or r[1] > r[2] or r[1] < r[3]]
    anom[str(aid)] = {'bars': len(rr), 'hl_violation': len(hl), 'ohlc_range_violation': len(rng),
                      'sample_range': [list(r) for r in rng[:2]]}
ev['ohlc_anom_close_type7'] = anom
# market_cap OHLC semantic (D/market_cap/type0 for 591)
mc = rows(591, 'D', 'market_cap', 'type0')
ev['market_cap_ohlc_sample'] = {'bars': len(mc), 'sample': [list(r) for r in mc[:2]],
                                'note': 'OHLC fields carry market-cap values, not prices'}

# ---- t=0 padding prevalence across a fund + equity + crypto ----
pad = {}
for aid in [1636, 591, 2]:
    for res in ['D', 'M']:
        rr = rows(aid, res, 'close', 'type0')
        t0 = sum(1 for r in rr if r[0] == 0)
        pad[f'{aid}_{res}'] = {'bars': len(rr), 't0_bars': t0}
ev['t0_padding'] = pad

c.close()
with open(os.path.join(OUT, 'ambiguity_evidence2.json'), 'w', encoding='utf-8') as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print('DONE2', flush=True)
print('wm_dup_t0:', json.dumps(ev['wm_dup_t0'], ensure_ascii=False), flush=True)
print('adj_broad_summary:', json.dumps(ev['adj_broad_summary'], ensure_ascii=False), flush=True)
print('adj_broad:', json.dumps(ev['adj_broad'], ensure_ascii=False), flush=True)
print('ohlc_anom_close_type7:', json.dumps(ev['ohlc_anom_close_type7'], ensure_ascii=False), flush=True)
print('t0_padding:', json.dumps(ev['t0_padding'], ensure_ascii=False), flush=True)