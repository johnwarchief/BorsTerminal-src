# _audit/_tol_probe.py -- توزیعِ agreementِ دو منبعِ مستقل (گسستِ CSV در برابرِ ردیفِ مبدأ)
import io,json,sys
sys.path.insert(0,".")
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
import ra365_ledger_ab as AB   # noqa
_keep=sys.stdout
out=io.TextIOWrapper(_keep.buffer,encoding="utf-8",errors="replace")
cands=[]
for s,ev in AB.RAW.items():
    led=AB.LED[s]
    for e in ev:
        d0=AB.dparse(e["date"]); r0=float(e["ratio"])
        for lr in led:
            dd=abs((AB.dparse(lr["date"])-d0).days)
            if dd<=10:
                cands.append((abs(lr["ratio"]/r0-1.0),dd,s,lr["kind"]))
cands.sort()
out.write(f"نامزدِ هم‌خوانی (پنجرۀِ ±۱۰ روز): {len(cands)} جفت\n")
buckets=[0,0.0001,0.0005,0.001,0.002,0.005,0.01,0.02,0.05,0.1,1.0,1e9]
for i in range(len(buckets)-1):
    n=sum(1 for x in cands if buckets[i]<=x[0]<buckets[i+1])
    if n: out.write(f"  {100*buckets[i]:8.4f}٪ .. {100*buckets[i+1]:9.4f}٪ : {n:4d}\n")
far=[c for c in cands if c[0]>=0.01]
out.write(f"\nبالایِ ۱٪ (ردِشدۀِ قطعی): {len(far)}  بیشینه {100*far[-1][0]:.1f}٪\n")
for th in (0.0005,0.001,0.002,0.005,0.01):
    out.write(f"پذیرفته با تلورانس {100*th:.2f}٪: {sum(1 for c in cands if c[0]<th)} از {len(cands)} جفت\n")
out.flush(); sys.stdout=_keep
