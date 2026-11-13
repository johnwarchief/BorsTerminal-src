# -*- coding: utf-8 -*-
"""Phase 4.9.7 Part 4 — volume estimates for the separation design, from coverage.json."""
import os, json
P6 = r"D:/BorsTerminal-worktrees/phase49-6-classification/_audit/phase49-6"
P7 = r"D:/BorsTerminal-worktrees/phase49-7-discovery/_audit/phase49-7"
cov = json.load(open(os.path.join(P6, 'coverage.json'), encoding='utf-8'))
qual = json.load(open(os.path.join(P6, 'quality.json'), encoding='utf-8'))
pm = cov['per_mode']
total = sum(m['rows'] for m in pm)
# distinct modes: drop real_close basis (==last) and type5 adj (==type0)
distinct = [m for m in pm if not m['mode'].startswith(('D/real_close', 'W/real_close', 'M/real_close'))
            and not m['mode'].endswith('/type5')]
# parse basis/adj properly
def parts(mk):
    r, b, a = mk.split('/'); return r, b, a
distinct = [m for m in pm if parts(m['mode'])[1] != 'real_close' and parts(m['mode'])[2] != 'type5']
redundant = [m for m in pm if parts(m['mode'])[1] == 'real_close' or parts(m['mode'])[2] == 'type5']
d_rows = sum(m['rows'] for m in distinct)
r_rows = sum(m['rows'] for m in redundant)
# padding estimate: W/M nonpos (t=0 placeholders), from quality
pad_wm = qual['nonpos_price_by_res']['W'] + qual['nonpos_price_by_res']['M']
pad_d = qual['nonpos_price_by_res']['D']
db_bytes = 14612127744
out = {
    'total_modes': len(pm), 'total_rows': total,
    'distinct_modes': len(distinct), 'distinct_rows': d_rows,
    'redundant_modes': len(redundant), 'redundant_rows': r_rows,
    'redundant_pct_rows': round(100 * r_rows / total, 1),
    'est_t0_padding_wm': pad_wm, 'd_nonpos_real': pad_d,
    'operational_rows_est': d_rows - pad_wm,  # padding lives in W/M which are in distinct set
    'ref_db_bytes': db_bytes,
    'technical_db_bytes_est_full63': db_bytes,
    'technical_db_bytes_est_distinct': round(db_bytes * d_rows / total),
    'technical_db_bytes_est_distinct_nopad': round(db_bytes * (d_rows - pad_wm) / total),
}
with open(os.path.join(P7, 'arch_volumes.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1), flush=True)