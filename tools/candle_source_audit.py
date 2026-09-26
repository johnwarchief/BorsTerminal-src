"""سنشِ منبع کندل (CDN TSETMC) بر پایهٔ خودِ داده — ابزار تشخیص، نه بخشی از اپ.

دو پرسش که با «حسّ ششم» قابل جواب دادن نیست:
  ۱) چه کسری از روزها «قیمت پایه» دقیقاً برابر پایانیِ روز قبل است؟
     آن کسر، شرطِ صحتِ تشخیصِ تعدیل از گسستِ پایه است. اگر پایه لنگرِ
     پایانیِ دیروز نباشد (صندوق‌هایی که بازارگردان/NAV قیمت پایه را می‌گذارند)،
     گسستِ پایه هر روز رخ می‌دهد و شمارشگرِ تعدیل، رویدادِ جعلی می‌سازد.
  ۲) چند کندل در منبع، پایانی یا اولین‌معاملهٔ بیرونِ [کمینه، بیشینه] دارد؟

خرج: ردیف‌های خامِ CSV + دو شاخصِ بالا به ازای هر نماد.
"""
from __future__ import annotations

import concurrent.futures as cf
import sqlite3
import statistics
import sys

import requests

CSV = "https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyListCSV/{code}/19900101"
HDR = {"User-Agent": "Mozilla/5.0", "Accept": "text/csv"}
ADJ_TOL = 0.001  # همان آستانهٔ api/chart.py


def probe(code: str):
    try:
        r = requests.get(CSV.format(code=code), headers=HDR, timeout=(3, 15))
        if r.status_code != 200:
            return None
        rows = []
        for ln in r.text.splitlines()[1:]:
            p = [x.strip() for x in ln.split(",")]
            if len(p) < 11:
                continue
            d = p[1]
            if len(d) != 8 or not d.isdigit():
                continue
            try:
                rows.append((d, float(p[2] or 0), float(p[3]), float(p[4]),
                             float(p[5]), float(p[10] or 0)))
            except ValueError:
                continue
    except Exception:
        return None
    if len(rows) < 30:
        return None
    rows.sort(key=lambda x: x[0])
    anchored = pairs = 0
    events = 0
    prev = None
    for d, first, hi, lo, c, base in rows:
        if prev and prev[4] > 0 and base > 0:
            pairs += 1
            if base == prev[4]:
                anchored += 1
            gap = abs(base - prev[4])
            if gap >= 1.0 and gap / prev[4] > ADJ_TOL:
                events += 1
        prev = (d, first, hi, lo, c, base)
    kept = [x for x in rows if x[2] > 0 and x[3] > 0 and x[4] > 0]
    geo = 0
    for d, first, hi, lo, c, base in kept:
        o = first if first > 0 else base
        if o > 0 and not (lo <= o <= hi and lo <= c <= hi):
            geo += 1
    return dict(n=len(rows), pairs=pairs, rate=anchored / pairs if pairs else 0.0,
                events=events, geo=geo, geo_rate=geo / len(kept) if kept else 0.0)


def main(limit: int = 120) -> None:
    db = sqlite3.connect("market.db")
    q = """SELECT ins_code, l_val18, paper_type,
                  (SELECT count(*) FROM daily_prices h WHERE h.ins_code=i.ins_code) n
           FROM instruments i WHERE l_val18 IS NOT NULL AND trim(l_val18)<>''
           GROUP BY l_val18 ORDER BY n DESC LIMIT ?"""
    syms = db.execute(q, (limit,)).fetchall()
    print(f"{'نماد':<12}{'ptype':>6}{'ردیف':>7}{'لنگر%':>8}{'رویداد':>8}{'هندسی‌خراب':>11}")
    bad = []
    with cf.ThreadPoolExecutor(16) as ex:
        futs = {ex.submit(probe, s[0]): s for s in syms}
        for f in cf.as_completed(futs):
            s = futs[f]
            d = f.result()
            if not d:
                continue
            print(f"{s[1]:<12}{str(s[2]):>6}{d['n']:>7}{d['rate']*100:>7.1f}%"
                  f"{d['events']:>8}{d['geo']:>8} ({d['geo_rate']*100:.1f}%)")
            if d["rate"] < 0.9:
                bad.append((s[1], s[2], d))
    print("\n=== نمادهایی که پایه‌شان لنگرِ پایانیِ دیروز نیست (تشخیص تعدیل در آن‌ها بی‌اعتبار) ===")
    for sym, pt, d in sorted(bad, key=lambda x: x[2]["rate"])[:40]:
        print(f"  {sym:<12} ptype={pt} anchored={d['rate']*100:.1f}%  fake_events={d['events']}")
    print(f"\ntotal probed={limit} unanchored={len(bad)}")
    sys.stdout.flush()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 120)
