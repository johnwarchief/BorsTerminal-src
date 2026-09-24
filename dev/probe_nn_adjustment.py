# -*- coding: utf-8 -*-
"""تطبیق سریِ تعدیل‌شدهٔ ما با حالت‌های ۰..۵ نهایت‌نگار، در تاریخ‌های یکسان."""
import sys, json, datetime
sys.stdout.reconfigure(encoding='utf-8')
import requests

B = "https://www.nahayatnegar.com/tv/chart/history"
HDRS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.nahayatnegar.com/tv/"}
F = int(datetime.datetime(2017, 1, 1, tzinfo=datetime.timezone.utc).timestamp())
T = int(datetime.datetime(2026, 10, 25, tzinfo=datetime.timezone.utc).timestamp())


def nn(sym_id, at):
    u = f"{B}?symbol={sym_id}{at}&resolution=1D&from={F}&to={T}&type=stock&adjustmentType={at}&countback=400"
    j = requests.get(u, headers=HDRS, timeout=30).json()
    if not j.get("t"):
        return None
    return {datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%d"): c
            for t, c in zip(j["t"], j["c"])}


def ours(sym):
    j = requests.get(f"http://127.0.0.1:8001/api/chart/{sym}", timeout=120).json()
    fac = {f["time"]: f["factor"] for f in j["factors"]}
    return ({c["time"]: round(c["close"] * fac[c["time"]], 2) for c in j["candles"]},
            {c["time"]: c["close"] for c in j["candles"]},
            j.get("adjustEvents") or [], j["count"])


for sym, sym_id in (("خودرو", "IRO1IKCO0001"), ("فولاد", "IRO1FOLD0001")):
    adj, raw, ev, n = ours(sym)
    print(f"\n=== {sym}  count={n}  events={len(ev)}  range={min(raw)}..{max(raw)}")
    dates = sorted(d for d in adj if d >= "2017-01-01")
    for at in range(6):
        s = nn(sym_id, at)
        if not s:
            print(f"  mode {at}: no_data"); continue
        common = [d for d in dates if d in s]
        diffs = [(d, round(s[d], 2), adj[d]) for d in common
                 if s[d] > 0 and abs(s[d] - adj[d]) > max(1.0, 0.01 * s[d])]
        rel = [s[d] / raw[d] for d in common if raw[d]]
        print(f"  mode {at}: n={len(common)}  diff_vs_ours={len(diffs)}  "
              f"factor_first={rel[0]:.6f} factor_mid={rel[len(rel)//2]:.6f} factor_last={rel[-1]:.6f}")
        for d, theirs, mine in diffs[:4]:
            print(f"      {d}  nn={theirs}  ours={mine}  raw={raw[d]}")
    print("  our events:", json.dumps(ev[-6:], ensure_ascii=False))
