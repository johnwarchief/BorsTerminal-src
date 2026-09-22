"""Why does the new _ref() pick a different row for the 58 regressed symbols?

Rebuilds the exact `annual` dict bulk_scan builds, then runs BOTH the v1.0.17
_ref() logic and the new one, printing which row each picks.
"""
import json
import sqlite3
import sys

DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'
sys.path.insert(0, r'C:\Users\PCMOD\Desktop\BorsTerminal')
REGRESSED = ['رمپنا', 'آريان', 'سيسكو', 'ميدكو', 'كچاد', 'كاوه']


def build_annual(con, F):
    annual = {}
    for sym, pe, title, rev, gp, eps in con.execute(
            "SELECT symbol, period_end, title, revenue, gross_profit, basic_eps "
            "FROM financial_statements WHERE period_months>=12 "
            "ORDER BY symbol, period_end DESC"):
        key = F.norm_fa(sym)
        if not key:
            continue
        annual.setdefault(key, []).append({
            'period_end': pe, 'fiscal_year': str(pe or '')[:4], 'title': title or '',
            'audited': F._is_audited(title or ''), 'consolidated': F._is_consolidated(title or ''),
            'revenue': F._fn(rev), 'gross_profit': F._fn(gp), 'basic_eps': F._fn(eps)})
    for key in annual:
        annual[key].sort(key=lambda r: str(r['period_end'] or ''), reverse=True)
    return annual


def ref_old(annual, sym):
    """verbatim v1.0.17"""
    for req_aud in (True, False):
        out, seen = [], set()
        for r in annual.get(sym, []):
            if r['consolidated'] or (req_aud and not r['audited']):
                continue
            if r['fiscal_year'] in seen:
                continue
            seen.add(r['fiscal_year'])
            out.append(r)
        if out:
            return out[0]
    dedup, seen = [], set()
    for r in annual.get(sym, []):
        if not r['fiscal_year'] or r['fiscal_year'] in seen:
            continue
        seen.add(r['fiscal_year'])
        dedup.append(r)
    return dedup[0] if dedup else None


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import fts_engine as F
    con = sqlite3.connect(DB)
    annual = build_annual(con, F)
    con.close()

    for sym in REGRESSED:
        lst = annual.get(sym, [])
        o = ref_old(annual, sym)
        print('%-8s rows=%d' % (sym, len(lst)))
        print('   OLD ref: pe=%-12s cons=%-5s aud=%-5s rev=%-14s gp=%s'
              % (o['period_end'], o['consolidated'], o['audited'], o['revenue'], o['gross_profit']))
        for r in lst:
            print('      pe=%-12s cons=%-5s aud=%-5s rev=%-14s gp=%-14s %s'
                  % (r['period_end'], r['consolidated'], r['audited'],
                     r['revenue'], r['gross_profit'], r['title'][:34]))
        print()


if __name__ == '__main__':
    main()
