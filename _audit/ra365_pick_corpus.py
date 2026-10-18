# _audit/ra365_pick_corpus.py -- شمارشِ معیارهایِ انتخابِ گنجینۀِ نماد برایِ دورِ تطبیق با ره‌آورد ۳۶۵
# مرجعِ انتخاب: دادۀِ واقعیِ خودِ محصول (market.db). فقط خواندن.
# خروجی: _audit/ra365_corpus_metrics.csv (همه) + چاپِ کاندیدها درِ هر دسته
import sqlite3
import sys
import io
import csv
import math

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WIN = 500  # آخرینِ ۵۰۰ جلسۀِ معاملاتی

con = sqlite3.connect("market.db")
cur = con.cursor()

cur.execute("select distinct date from price_history where date>='2024-08-24' order by date")
calendar = [r[0] for r in cur.fetchall()]
cal_index = {d: i for i, d in enumerate(calendar)}

q = f"""
with r as (
  select symbol, date, open, high, low, close, volume,
         row_number() over (partition by symbol order by date desc) rn
  from price_history
)
select symbol, group_concat(date || '|' || coalesce(close,0) || '|' || coalesce(high,0) || '|' || coalesce(low,0), ',')
from r where rn<={WIN} group by symbol
"""
cur.execute(q)
rows = cur.fetchall()

sec = dict(cur.execute("select symbol, sector_name from symbol_sectors").fetchall())
cap = dict(cur.execute("select symbol, market_cap from (select symbol, market_cap, row_number() over (partition by symbol order by date desc) rn from market_cap_snapshots) where rn=1").fetchall())
ev = dict(cur.execute("select symbol, count(*) from adjust_events group by symbol").fetchall())

out = []
for symbol, blob in rows:
    if not blob:
        continue
    recs = [b.split("|") for b in blob.split(",")][::-1]  # قدیمی‌به‌تازه
    if len(recs) < 60:
        continue
    closes = [float(x[1]) for x in recs]
    highs = [float(x[2]) for x in recs]
    lows = [float(x[3]) for x in recs]
    dates = [x[0] for x in recs]
    hi = max(highs)
    ret = closes[-1] / closes[0] - 1.0 if closes[0] else 0.0
    dd = (hi - closes[-1]) / hi if hi else 0.0
    rets = [(closes[i] / closes[i - 1] - 1.0) for i in range(1, len(closes)) if closes[i - 1]]
    vol_sd = math.sqrt(sum(r * r for r in rets) / len(rets)) if rets else 0.0
    idxs = [cal_index.get(d, -1) for d in dates]
    span = (idxs[-1] - idxs[0] + 1) if idxs[0] >= 0 and idxs[-1] >= 0 else len(idxs)
    missing = max(0, span - len(idxs))
    flat = sum(1 for i in range(len(recs)) if highs[i] == lows[i])
    out.append({
        "symbol": symbol,
        "bars": len(recs),
        "last_date": dates[-1],
        "last_close": closes[-1],
        "sector": (sec.get(symbol) or "").replace("ي", "ی").replace("ك", "ک"),
        "market_cap": cap.get(symbol),
        "return_500d": round(ret, 4),
        "max_drawdown": round(dd, 4),
        "daily_vol": round(vol_sd, 5),
        "missing_sessions": missing,
        "flat_candles": flat,
        "adjust_events": ev.get(symbol, 0),
    })

out.sort(key=lambda r: -r["bars"])
with open("_audit/ra365_corpus_metrics.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)

liquid = [r for r in out if r["bars"] >= 400 and (r["market_cap"] or 0) >= 2e12]


def show(title, items, n=12):
    print(f"\n### {title}")
    for r in items[:n]:
        print(f"  {r['symbol']:12s} bars={r['bars']:4d} last={r['last_date']} close={r['last_close']:>12,.0f} "
              f"ret={r['return_500d']:+8.2%} dd={r['max_drawdown']:6.2%} vol={r['daily_vol']:.4f} "
              f"miss={r['missing_sessions']:3d} flat={r['flat_candles']:3d} adj={r['adjust_events']:2d} cap={(r['market_cap'] or 0)/1e12:6.1f}T {r['sector'][:24]}")


show("اجباری", [r for r in out if r["symbol"] in ("شبهرن", "ولانا", "وبملت", "فولاد", "خودرو", "شپنا", "فنوال")])
show("سودِ دهیِ عمیق (downtrend)", sorted(liquid, key=lambda r: r["return_500d"]))
show("صعودیِ قوی", sorted(liquid, key=lambda r: -r["return_500d"]))
show("تعدیل‌محور (رویداد زیاد)", sorted(liquid, key=lambda r: -r["adjust_events"]))
show("حفرۀِ داداهی (جلسه کم)", sorted(liquid, key=lambda r: -r["missing_sessions"]))
show("تک‌قیمت/بی‌رمق (flat candle زیاد)", sorted(liquid, key=lambda r: -r["flat_candles"]))
show("بزرگ‌ترینِ بازار", sorted(liquid, key=lambda r: -(r["market_cap"] or 0))[:6] + sorted(liquid, key=lambda r: (r["market_cap"] or 1))[:6])
show("گران‌ترین / ارزان‌ترین (فشارِ محورِ لگاریتمی)", sorted(liquid, key=lambda r: -r["last_close"])[:6] + sorted(liquid, key=lambda r: r["last_close"])[:6])
print("\nمجموعِ نمادهایِ سنجیده‌شده:", len(out), "| نقدشونده:", len(liquid))
