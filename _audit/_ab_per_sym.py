# _audit/_ab_per_sym.py -- جدولِ نماد‌به‌نمادِ دو بازویِ منتخب (ضریبِ مبدأ / هم‌تاریخِ تنها)
import io,sys
sys.path.insert(0,"."); sys.path.insert(0,"_audit")
import ra365_ledger_ab as AB
_keep = sys.stdout          # نگه‌داشتنِ مرجع وگرنه GC بافرِ مشترک را می‌بندد
sys.stdout = io.TextIOWrapper(_keep.buffer, encoding="utf-8", errors="replace")
base=AB.measure({s:[dict(x) for x in AB.RAW[s]] for s in AB.RAW},"V0")
for tag,kw in [("V3 ضریبِ مبدأ، پنجره ۱۰",dict(w=10,t=0.01,mode="ratio")),
               ("V7 هم‌تاریخِ تنها",dict(w=0,t=0.01,mode="ratio"))]:
    ev={s:AB.sharpen(AB.RAW[s],AB.LED[s],kw["w"],kw["t"],kw["mode"]) for s in AB.RAW}
    r=AB.measure(ev,tag)
    rows=[]
    for s in base["per"]:
        d=100*(r["per"][s][1]-base["per"][s][1])
        n=sum(1 for e in ev[s] if e.get("source") in ("priceAdjust","shareChange"))
        rows.append((d,s,100*base["per"][s][1],100*r["per"][s][1],len(AB.RAW[s]),n))
    rows.sort()
    print(f"\n== {tag}: میانه {r['median']:.4f}٪ (کنترل {base['median']:.4f}٪)  p90 {r['p90']:.4f} vs {base['p90']:.4f}")
    print(f"  {'sym':9s}{'کنترل٪':>9s}{'پس٪':>9s}{'دلتا٪':>9s}  رویداد  تیز")
    for d,s,mb,ma,ne,nn in rows:
        print(f"  {s:9s}{mb:9.4f}{ma:9.4f}{d:+9.4f}  {ne:5d}  {nn:4d}")
