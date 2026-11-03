# _audit/_shipped_probe.py -- خودِ تابعِ نهاییِ api/chart.py روی رویدادهایِ ضبط‌شده
import io,json,sys
sys.path.insert(0,"."); sys.path.insert(0,"_audit")
import ra365_ledger_ab as AB
_keep=sys.stdout
sys.stdout=io.TextIOWrapper(_keep.buffer,encoding="utf-8",errors="replace")
from api.chart import _sharpen_events_with_ledger
for s in ("شبهرن","خودرو","وبملت","ولانا","لخزر","ومعادن","شنفت"):
    ev,sh,amb=_sharpen_events_with_ledger(s,AB.RAW[s])
    assert len(ev)==len(AB.RAW[s]), f"RODED! {s} {len(AB.RAW[s])}->{len(ev)}"
    src=sorted(AB.RAW[s],key=lambda x:x['date']); dst=sorted(ev,key=lambda x:x['date'])
    moved=sum(1 for a,b in zip(src,dst) if a["date"]!=b["date"])
    print(f"{s:8s} رویداد {len(AB.RAW[s])}→{len(ev)}  تیز={sh} مبهم={amb} چرخشِ‌تاریخ={moved}")
    for a,b in zip(src,dst):
        if abs(float(a['ratio'])-float(b['ratio']))>1e-12:
            print(f"      {a['date']}: {a['ratio']} → {b['ratio']}  [{b.get('source')}]")
print("OK: هیچ رویدادی حذف نشد")
