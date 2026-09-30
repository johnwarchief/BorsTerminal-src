# -*- coding: utf-8 -*-
"""کوئریِ کهنۀ پنجرۀ نمایش در برابرِ کوئریِ تازه، رویِ یک بانکِ کپیِ یکسان.
دو شرطِ «کمتر از نشستِ جاری» را از متنِ ماژول برمی‌داریم تا فقط کد فرق داشته
باشد، نه داده. خروجی: چند نماد، و سه نمادِ نمونه با عدد."""
import json
import re
import sqlite3
import sys
import time

sys.path.insert(0, ".")
import api.market as mk  # noqa: E402

SPINE_CLAUSE = re.compile(
    r"\n\s*WHERE date < \(SELECT printf\('%04d-%02d-%02d', d/10000,\n"
    r"\s*\(d/100\)%100, d%100\) FROM iso\)")
HIST_CLAUSE = re.compile(
    r"\n\s*AND h\.date < \(SELECT printf\('%04d-%02d-%02d', d/10000,\n"
    r"\s*\(d/100\)%100, d%100\) FROM iso\)")

NEW = mk._HIST_V_SQL
OLD = HIST_CLAUSE.sub("", SPINE_CLAUSE.sub("", NEW))
assert NEW.count("date < (SELECT printf") == 2 and OLD.count("date < (SELECT printf") == 0, "surgery failed"

COLS = ("month_avg_vol", "prev_day_vol", "d1_vol", "min30_low", "max30_high")
db = sys.argv[1] if len(sys.argv) > 1 else "_audit/liveprobe_copy.db"
c = sqlite3.connect(db)


def build(sql):
    t = time.time()
    cur = c.execute(sql)
    names = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return names, rows, time.time() - t


n1, r_new, t_new = build(NEW)
n2, r_old, t_old = build(OLD)
ix = {n: i for i, n in enumerate(n1)}
mo = {r[ix["symbol"]]: r for r in r_old}
mn = {r[ix["symbol"]]: r for r in r_new}
common = sorted(set(mo) & set(mn))
diff = [s for s in common if any(mo[s][ix[k]] != mn[s][ix[k]] for k in COLS)]
live = c.execute("SELECT printf('%04d-%02d-%02d', d/10000,(d/100)%100,d%100) "
                 "FROM (SELECT MAX(d_even) d FROM market_watch)").fetchone()[0]
n_live = c.execute("SELECT COUNT(DISTINCT symbol) FROM price_history WHERE date = ?",
                   (live,)).fetchone()[0]
samples = []
for s in diff[:3]:
    tail = c.execute("SELECT date, volume FROM price_history WHERE symbol=? "
                     "ORDER BY date DESC LIMIT 2", (s,)).fetchall()
    samples.append({"symbol": s,
                    "prev_day_vol_old": mo[s][ix["prev_day_vol"]],
                    "prev_day_vol_new": mn[s][ix["prev_day_vol"]],
                    "month_avg_old": mo[s][ix["month_avg_vol"]],
                    "month_avg_new": mn[s][ix["month_avg_vol"]],
                    "last_two_candles": tail})
out = {"db": db, "live_date": live, "symbols_with_live_candle": n_live,
       "rows_old": len(r_old), "rows_new": len(r_new), "common": len(common),
       "symbols_differing": len(diff),
       "differ_share_pct": round(100.0 * len(diff) / max(1, len(common)), 2),
       "build_seconds_old": round(t_old, 3), "build_seconds_new": round(t_new, 3),
       "samples": samples}
print(json.dumps(out, ensure_ascii=False, indent=1))
