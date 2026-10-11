# _audit/_lakhazar_step_probe.py -- میانۀِ ۶٫۹٪ لخزر: گامِ ما در برابرِ گامِ خودِ مرجع
# مرجعِ مستقلِ گام: نسبتِ type7/type0 درِ همان تاریخ (فاکتورِ خودِ رهاورد). اگر یک
# رویدادِ ما ~۷٪ با آن اختلاف داشته باشد، همان «سطحِ ثابتِ خطا»یِ سنجیده‌شده توضیح
# می‌یابد (خطایِ یک ضریب روی کلِ تاریخِ پیشِ خودش مقیاس می‌گذارد).
import json, io, sys
from datetime import datetime, timezone, timedelta
_keep = sys.stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
SYM = sys.argv[1] if len(sys.argv) > 1 else "لخزر"
R = json.load(open("_audit/ra365_ref_bars.json", encoding="utf-8"))
P = json.load(open(sys.argv[2] if len(sys.argv) > 2 else "_audit/ra365_product_bars_v3.json",
                   encoding="utf-8"))


def td(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=3, minutes=30))).date().isoformat()


def ref(suf):
    e = R["bars"].get(f"{SYM}|{suf}|D")
    return {} if not e or e.get("status") != 200 else {td(b): b for b in e["bars"] if b.get("c")}


r7, r0 = ref("type7"), ref("type0")
days = sorted(set(r7) & set(r0))
fac = {d: r7[d]["c"] / r0[d]["c"] for d in days if r0[d]["c"]}
dord = sorted(fac)
refsteps = []
for i in range(1, len(dord)):
    a, b = dord[i - 1], dord[i]
    if fac[a]:
        s = fac[b] / fac[a]
        if abs(s - 1.0) > 0.002:
            refsteps.append((b, s))
ours = {str(e["date"])[:10]: float(e["ratio"]) for e in (P[SYM]["live"].get("adjustEvents") or [])}
print(f"گام‌هایِ مرجع: {len(refsteps)}   رویدادهایِ ما: {len(ours)}")
print(f"{'تاریخ':12s} {'گامِ مرجع':>12s} {'ضریبِ ما':>12s} {'گامِ ما(۱/)':>12s} {'اختلاف':>10s}")
for d, s in refsteps:
    o = None
    for i in range(0, 12):
        try:
            dd = (datetime.strptime(d, "%Y-%m-%d").date() - timedelta(days=i)).isoformat()
        except Exception:
            continue
        if dd in ours:
            o = ours[dd]
            break
    if o is None:
        print(f"{d:12s} {s:12.5f} {'—':>12s} {'—':>12s}  بی‌رویدادِ ما درِ ±۱۲ روز")
    else:
        print(f"{d:12s} {s:12.5f} {o:12.6f} {1.0/o:12.5f} {100*(1.0/o/s-1.0):9.3f}٪")
