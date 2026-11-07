# _audit/_lakhazar_csv2.py -- ستون‌هایِ درستِ CSVِ مبدأ (<OPEN> = قیمتِ پایه)
import csv, io, sys, urllib.request
_keep = sys.stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
INS = "65414507129586385"
url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyListCSV/{INS}/20250101"
txt = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                             timeout=60).read().decode("utf-8-sig")
rows = list(csv.DictReader([l for l in txt.splitlines() if l.strip()]))
print("تعدادِ سطر:", len(rows), "| کلیدها:", list(rows[0].keys()))


def iso(r):
    v = str(r.get("<DTYYYYMMDD>") or "")
    if len(v) == 8 and v.isdigit():
        return f"{v[:4]}-{v[4:6]}-{v[6:]}"
    return ""


WINDOWS = [("2025-03-15", "2025-04-15"), ("2026-07-01", "2026-08-01")]
for lo, hi in WINDOWS:
    print(f"\n── پنجرۀِ {lo} … {hi} ──")
    prev = None
    for r in sorted(rows, key=iso):
        d = iso(r)
        if not (lo <= d <= hi):
            continue
        base = float(r.get("<OPEN>") or 0)
        close = float(r.get("<CLOSE>") or 0)
        last = float(r.get("<LAST>") or 0)
        vol = r.get("<VOL>")
        tag = ""
        if prev is not None and prev > 0 and abs(base / prev - 1) > 0.02:
            tag = f"  ← گسستِ پایه = {base / prev:.6f}"
        print(f"  {d}  پایه(OPEN)={base:>10.2f}  پایانی(CLOSE)={close:>10.2f}  "
              f"آخرین(LAST)={last:>10.2f}  VOL={vol:>14}{tag}")
        prev = base
