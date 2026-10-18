# _audit/_lakhazar_detail.py -- دو پروندۀِ لخزر: گامِ ۱٫۵ بی‌رویدادِ ما، و گامِ ۲۰۲۶-۰۷-۲۷
# چاپِ کنارِ هم: کندلِ خامِ ما، پایانیِ تعدیل‌شده/خامِ مرجع، و رویدادهایِ ما درِ پنجره.
import json, io, sys
from datetime import datetime, timezone, timedelta
_keep = sys.stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
SYM = "لخزر"
R = json.load(open("_audit/ra365_ref_bars.json", encoding="utf-8"))
P = json.load(open("_audit/ra365_product_bars_v3.json", encoding="utf-8"))


def td(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=3, minutes=30))).date().isoformat()


def ref(suf):
    e = R["bars"].get(f"{SYM}|{suf}|D")
    return {} if not e or e.get("status") != 200 else {td(b): b["c"] for b in e["bars"] if b.get("c")}


r7, r0 = ref("type7"), ref("type0")
raw = {c["time"]: c for c in P[SYM]["live"]["candles"]}
ev = [(str(e["date"])[:10], float(e["ratio"]), str(e.get("source")))
      for e in (P[SYM]["live"].get("adjustEvents") or [])]
days = sorted(set(r7) & set(r0))
for lo, hi in (("2025-03-20", "2025-04-20"), ("2026-07-05", "2026-08-05")):
    print(f"\n── {lo} … {hi} ──")
    for d in [x for x in days if lo <= x <= hi]:
        print(f"  {d}  مرجع خام {r0[d]:12,.0f}  مرجع تعدیل {r7[d]:14,.2f}  "
              f"نسبت {r7[d]/r0[d]:8.5f} | محصول last {raw.get(d,{}).get('last')!r:>12} "
              f"closing {raw.get(d,{}).get('closing')!r:>12}")
    print("  رویدادهایِ ما: " + str([e for e in ev if lo <= e[0] <= hi]))
    print("  کندل‌هایِ محصول درِ پنجره:", len([d for d in raw if lo <= d <= hi]))
