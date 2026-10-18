# _audit/_source_rewrite_probe.py -- مبدأ چقدر تاریخِ قدیم را بازنویسی می‌کند؟
# چرا: بازوِ خام (R0) باید از تیزکردنِ مبدأ دست‌نخورده بماند؛ اگر «بیشینه»ِ آن جابه‌جا
# شد، تنها توضیحِ قابلِ پذیرشِ پیش از اتهامِ کدِ خودمان این است که CSVِ مبدأ خودش
# ردیفِ قدیمی را عوض کرده باشد. این سنجشِ مستقیمِ همان ادعاست: دو ضبطِ زنده از همان
# نماد، مقایسهٔ قلم‌به‌قلمِ ستون‌هایِ خام.
import json, io, sys
_keep = sys.stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
B = json.load(open("_audit/ra365_product_bars.json", encoding="utf-8"))
A = json.load(open("_audit/ra365_product_bars_v3.json", encoding="utf-8"))
COLS = ("last", "closing", "open", "high", "low")
tot_bars = tot_diff = 0
newest = {}
rows = []
for sym in A:
    gb = {c["time"]: c for c in B[sym]["live"]["candles"]}
    ga = {c["time"]: c for c in A[sym]["live"]["candles"]}
    common = sorted(set(gb) & set(ga))
    d_ = [(d, col, gb[d].get(col), ga[d].get(col)) for d in common for col in COLS
          if (gb[d].get(col) or 0) and (ga[d].get(col) or 0)
          and abs(gb[d][col] - ga[d][col]) > 1e-9]
    tot_bars += len(common)
    tot_diff += len(d_)
    if d_:
        days = sorted({x[0] for x in d_})
        rows.append((len(d_), sym, days[:3], d_[:2]))
    newest[sym] = (min(common) if common else "-", max(common) if common else "-",
                   len(set(ga) - set(gb)), len(set(gb) - set(ga)))
print(f"تکۀ‌هایِ خامِ تغییرکرده: {tot_diff} روی {tot_bars} کندلِ مشترک "
      f"({100.0*tot_diff/tot_bars:.3f}٪ از کندل‌ها)")
for n, sym, days, sample in sorted(rows, reverse=True)[:10]:
    print(f"  {sym:8s} {n:3d} تغییر  تاریخ‌ها {days}  نمونه {sample}")
print("\nتغییرِ پنجرۀِ تاریخ (کمترین/بیشترین/ردیفِ تازه/ردیفِ رفته):")
for sym, v in list(newest.items())[:6]:
    print(f"  {sym:8s} {v}")
