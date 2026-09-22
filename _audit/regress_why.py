"""For each regressed symbol, determine whether _solo_annual or _ref diverged.

Runs both old and new versions of the two pickers against the same `annual`
dict and reports the first field whose choice differs.
"""
import sqlite3
import sys

DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'
sys.path.insert(0, r'C:\Users\PCMOD\Desktop\BorsTerminal')
SYMS = ['رمپنا', 'آريان', 'ميدكو', 'شسپا', 'كاوه', 'سباقر', 'سمازن', 'سجام',
        'كساوه', 'اردستان', 'ثباغ', 'حآفرين']


def build(con, F):
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


def solo_old(annual, sym):
    last = []
    for req_aud in (True, False):
        out, seen = [], set()
        for r in annual.get(sym, []):
            if r['consolidated'] or (req_aud and not r['audited']):
                continue
            if not r['fiscal_year'] or r['fiscal_year'] in seen:
                continue
            seen.add(r['fiscal_year'])
            out.append(r)
        last = out
        if len(out) >= 2:
            return out
    return last


def ref_old(annual, sym):
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
    annual = build(con, F)
    con.close()

    for sym in SYMS:
        lst = annual.get(sym, [])
        if not lst:
            print('%-8s no rows' % sym)
            continue
        o_solo, n_solo = solo_old(annual, sym), F.bulk_scan.__defaults__  # placeholder
        # call the real new pickers via the module's closures is not possible;
        # instead recompute what the new code would pick with the same rules.
        def new_solo(req_aud, want_cons):
            out, seen = [], set()
            for r in lst:
                if r['consolidated'] != want_cons:
                    continue
                if req_aud and not r['audited']:
                    continue
                if not r['fiscal_year'] or r['fiscal_year'] in seen:
                    continue
                seen.add(r['fiscal_year'])
                out.append(r)
            return out
        ns = None
        for req_aud in (True, False):
            o = new_solo(req_aud, False)
            if len(o) >= 2:
                ns = o
                break
        if ns is None:
            for req_aud in (True, False):
                o = new_solo(req_aud, True)
                if len(o) >= 2:
                    ns = o
                    break

        o_ref = ref_old(annual, sym)
        def new_ref():
            for want_cons in (False, True):
                for req_aud in (True, False):
                    out, seen = [], set()
                    for r in lst:
                        if r['consolidated'] != want_cons:
                            continue
                        if req_aud and not r['audited']:
                            continue
                        if r['fiscal_year'] in seen:
                            continue
                        seen.add(r['fiscal_year'])
                        out.append(r)
                    if out:
                        return out[0]
            return None
        n_ref = new_ref()

        solo_same = [r['period_end'] for r in solo_old(annual, sym)] == \
                    [r['period_end'] for r in (ns or [])]
        ref_same = (o_ref or {}).get('period_end') == (n_ref or {}).get('period_end')
        print('%-8s solo_old=%s solo_new=%s same=%-5s | ref_old=%s ref_new=%s same=%s'
              % (sym,
                 [r['period_end'] for r in solo_old(annual, sym)],
                 [r['period_end'] for r in (ns or [])], solo_same,
                 (o_ref or {}).get('period_end'), (n_ref or {}).get('period_end'), ref_same))


if __name__ == '__main__':
    main()
