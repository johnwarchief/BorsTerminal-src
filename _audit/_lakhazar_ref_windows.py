# _audit/_lakhazar_ref_windows.py — بارِ مرجعِ لخزر درِ پنجره‌هایِ July 2026 و March/April 2025
import json, io, sys, datetime as dt
_keep = sys.stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REF = json.load(open("_audit/ra365_ref_bars.json", encoding="utf-8"))["bars"]


def bydate(key):
    out = {}
    for b in REF[key]["bars"]:
        d = (b.get("utc") or "")[:10] or dt.datetime.utcfromtimestamp(b["t"] / 1000).date().isoformat()
        out[d] = b
    return out


RAW, ADJ = bydate("لخزر|type0|D"), bydate("لخزر|type7|D")
for lo, hi in [("2025-03-15", "2025-04-15"), ("2026-07-01", "2026-08-01")]:
    print(f"\n── مرجع · {lo} … {hi} ──")
    prev_f = None
    for d in sorted(RAW):
        if not (lo <= d <= hi):
            continue
        r, a = RAW[d], ADJ[d]
        f = a["c"] / r["c"]
        tag = ""
        if prev_f and abs(f / prev_f - 1) > 1e-6:
            tag = f"  ← گامِ مرجع = {f / prev_f:.6f}"
        print(f"  {d}  closeِ خام={r['c']:>9.0f}  closeِ تعدیل‌شده={a['c']:>11.2f}  "
              f"فاکتور={f:.6f}  VOL={r['v']:>12}{tag}")
        prev_f = f
