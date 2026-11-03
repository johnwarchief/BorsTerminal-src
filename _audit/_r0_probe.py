# _audit/_r0_probe.py -- بازوِ خام (R0) نباید تیزکردنِ مبدأ به آن بخورد؛ اگر «بیشینه»
# عوض شد، باید معلوم شود کدام تاریخ و چرا (مبنا: سرریزِ روزِ معاملاتیِ درجریان).
import json, io, sys
from datetime import datetime, timezone, timedelta
_keep = sys.stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
R = json.load(open("_audit/ra365_ref_bars.json", encoding="utf-8"))
CORPUS = json.load(open("_audit/ra365_corpus.json", encoding="utf-8"))
B = json.load(open("_audit/ra365_product_bars.json", encoding="utf-8"))
A = json.load(open("_audit/ra365_product_bars_v3.json", encoding="utf-8"))
def td(b):
    s = str(b["utc"]).replace("Z", "+00:00"); dt = datetime.fromisoformat(s)
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=3, minutes=30))).date().isoformat()
def ref(sym):
    e = R["bars"].get(f"{sym}|type0|D")
    if not e or e.get("status") != 200: return {}
    return {td(b): b["c"] for b in e["bars"] if b.get("c")}
def raw(rec):
    return {c["time"]: c.get("last") for c in rec["candles"] if c.get("last")}
worst = []
for c in CORPUS:
    sym = c["sym"]; rf = ref(sym)
    for tag, P in (("پیش", B), ("پس", A)):
        pd_ = raw(P[sym]["live"])
        common = sorted(set(rf) & set(pd_))
        errs = [(abs(rf[d] - pd_[d]) / rf[d], d) for d in common if rf[d]]
        if errs:
            m, d = max(errs)
            worst.append((m, sym, tag, d, rf[d], pd_[d]))
worst.sort(reverse=True)
for m, sym, tag, d, rv, pv in worst[:8]:
    print(f"  {sym:8s} {tag:4s} {d}  مرجع {rv:14,.0f}  محصول {pv:14,.0f}  خطا {100*m:.4f}٪")
print("  بیشترینِ «پس» در یک نماد:", max((w for w in worst if w[2] == "پس"), default=None))
