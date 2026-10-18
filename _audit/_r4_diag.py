# _audit/_r4_diag.py -- ریشۀِ بدترشدنِ دُمِِ R4 (دیتابیس) پس از رفعِ RC3
import json, io, sys
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT="."
R=json.load(open("_audit/ra365_ref_bars.json",encoding="utf-8"))
CORPUS=json.load(open("_audit/ra365_corpus.json",encoding="utf-8"))
B=json.load(open("_audit/ra365_product_bars.json",encoding="utf-8"))
A=json.load(open("_audit/ra365_product_bars_after.json",encoding="utf-8"))
def td(b):
    s=str(b["utc"]).replace("Z","+00:00"); dt=datetime.fromisoformat(s)
    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=3,minutes=30))).date().isoformat()
def ref(sym,suf):
    e=R["bars"].get(f"{sym}|{suf}|D")
    if not e or e.get("status")!=200: return {}
    return {td(b):b["c"] for b in e["bars"] if b.get("c")}
def series(live,adj,basis):
    fac={f["time"]:f["factor"] for f in (live.get("factors") or [])}
    out={}
    for c in live["candles"]:
        base=c.get("last") if basis=="last" else c.get("closing",c.get("close"))
        out[c["time"]]=(base*fac.get(c["time"],1.0)) if adj else base
    return out
rows=[]
for c in CORPUS:
    sym=c["sym"]; rf=ref(sym,"type7")
    fb=series(B[sym]["db"],True,"closing"); fa=series(A[sym]["db"],True,"closing")
    common=sorted(set(rf)&set(fa))
    eb=[(abs(rf[d]-fa[d])/rf[d],d) for d in common if rf[d]]
    eb.sort(reverse=True)
    db_=[(abs(rf[d]-fb[d])/rf[d],d) for d in common if rf[d]]; db_.sort(reverse=True)
    nb=sorted(x for x,_ in db_); na=sorted(x for x,_ in eb)
    medb=nb[len(nb)//2] if nb else 0; meda=na[len(na)//2] if na else 0
    facb={f["time"]:f["factor"] for f in (B[sym]["db"].get("factors") or [])}
    faca={f["time"]:f["factor"] for f in (A[sym]["db"].get("factors") or [])}
    rows.append((eb[0][0] if eb else 0, sym, medb, meda, eb[0][1] if eb else "",
                 db_[0][0] if db_ else 0, db_[0][1] if db_ else "",
                 len(B[sym]["db"].get("factors") or []), len(A[sym]["db"].get("factors") or []),
                 len(B[sym]["db"].get("adjustEvents") or []), len(A[sym]["db"].get("adjustEvents") or []),
                 B[sym]["db"].get("adjustSource"), A[sym]["db"].get("adjustSource"),
                 facb.get(eb[0][1]) if eb else None, faca.get(eb[0][1]) if eb else None,
                 rf.get(eb[0][1]) if eb else None, fa[eb[0][1]] if eb and eb[0][1] in fa else None,
                 fb[eb[0][1]] if eb and eb[0][1] in fb else None))
rows.sort(reverse=True)
print(f"{'sym':9s}{'medB%':>8s}{'medA%':>8s}{'maxA%':>9s} {'dateA':10s} {'maxB%':>8s} {'dateB':10s} nfacB nfacA evB evA srcB->srcA  facA/facB ref valA valB")
for r in rows[:12]:
    print(f"{r[1]:9s}{100*r[2]:8.3f}{100*r[3]:8.3f}{100*r[0]:9.3f} {r[4]:10s} {100*r[5]:8.3f} {r[6]:10s} {r[7]:5d} {r[8]:5d} {r[9]:3d} {r[10]:3d}  {str(r[11])[:18]}->{str(r[12])[:18]}  {r[13]}/{r[14]} ref={r[15]} a={r[16]} b={r[17]}")
