"""Dump symbol -> (eps_series, gross_margin, profit_potential_pct, score) for
every screen row, so the pre-fix and post-fix outputs can be diffed exactly."""
import json
import os
import sqlite3
import sys

DB = r'C:\Users\PCMOD\AppData\Local\BorsTerminalUltimate\current\_internal\market.db'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'screen_dump.json'
sys.path.insert(0, r'C:\Users\PCMOD\Desktop\BorsTerminal')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import fts_engine as F

    cfg_path = r'C:\Users\PCMOD\Desktop\BorsTerminal\fts_config.json'
    cfg = json.loads(open(cfg_path, encoding='utf-8').read()) if os.path.exists(cfg_path) else {}

    con = sqlite3.connect(DB)
    rows = F.bulk_scan(con, cfg=cfg)
    con.close()

    dump = {}
    for r in rows:
        dump[r['symbol']] = {
            'eps_series': r.get('eps_series'),
            'gross_margin': r.get('gross_margin'),
            'profit_potential_pct': r.get('profit_potential_pct'),
            'score': r.get('score'),
            'rev_growth': r.get('rev_growth'),
            'annual_sales_bt': r.get('annual_sales_bt'),
        }
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(dump, fh, ensure_ascii=False, indent=0)
    print('wrote %s (%d symbols)' % (OUT, len(dump)))


if __name__ == '__main__':
    main()
