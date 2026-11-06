import sys
import datetime as dt

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from api.chart import _fts_swings, _fts_classify_trend

def week_bars(week_open, o, h, l, c, days=(0, 1, 2, 3)):
    out = []
    sat = week_open
    for i, d in enumerate(days):
        date = (sat + dt.timedelta(days=d)).isoformat()
        if i == 0:
            out.append({"time": date, "open": o, "high": h, "low": l, "close": (o + c) / 2, "volume": 1e6})
        elif i == len(days) - 1:
            out.append({"time": date, "open": (o + c) / 2, "high": h, "low": l, "close": c, "volume": 1e6})
        else:
            out.append({"time": date, "open": c if i % 2 else o, "high": h, "low": l,
                        "close": (o + c) / 2, "volume": 1e6})
    return out

def build(weeks, start=dt.date(2024, 1, 6)): 
    out = []
    for i, (h, l, o, c) in enumerate(weeks):
        out += week_bars(start + dt.timedelta(weeks=i), o, h, l, c)
    return out

def daily_tail(start, days):
    out = []
    curr = start
    for h, l, o, c in days:
        while curr.weekday() > 4:
            curr += dt.timedelta(days=1)
        out.append({"time": curr.isoformat(), "open": o, "high": h, "low": l, "close": c, "volume": 1e6})
        curr += dt.timedelta(days=1)
    return out

BEAR = [(120 - 8 * k, 100 - 8 * k, 118 - 8 * k, 102 - 8 * k) for k in range(14)]
TAIL_V = [(14, 6, 12, 7), (22, 7, 7, 14), (34, 12, 14, 30), (30, 16, 30, 20),
          (26, 14, 20, 16), (24, 12, 16, 13), (28, 13, 13, 24), (32, 15, 24, 30),
          (35, 18, 30, 33), (36, 20, 33, 35), (33, 24, 35, 28), (30, 22, 28, 26),
          (29, 21, 26, 25), (27, 22, 25, 24), (26, 23, 24, 25), (28, 24, 25, 27)]

tail_start = dt.date(2024, 1, 6) + dt.timedelta(weeks=12)
candles = build(BEAR[:12]) + daily_tail(tail_start, TAIL_V)

swings = _fts_swings(candles, k=3)
for s in swings:
    print(s)

out = _fts_classify_trend(swings, series=candles)
print("Resulting dict:", out)
