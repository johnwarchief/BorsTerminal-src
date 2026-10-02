# یک‌بارمصرف — آیا TSETMC ارزش بازارِ **هر نماد** را مستقیم می‌دهد؟
# آزمونِ زنده رویِ سه endpoint + مقایسه با بانکِ محلی.
import json
import sqlite3
import sys

import requests

sys.path.insert(0, r"C:\Users\PCMOD\Desktop\BorsTerminal")
import test_tsetmc as T            # noqa: E402

db = sqlite3.connect("file:market.db?mode=ro", uri=True)
LOCAL = dict(db.execute("SELECT i.l_val18, m.market_cap FROM market_watch m "
                        "JOIN instruments i ON i.ins_code=m.ins_code "
                        "WHERE i.l_val18 IN ('نشار','فولاد','شبندر','خوزارا','غپروما')"))
CODES = dict(db.execute("SELECT i.l_val18, i.ins_code FROM instruments i "
                        "WHERE i.l_val18 IN ('نشار','فولاد','شبندر','خوزارا','غپروما')"))
print("نمونه‌ها:", CODES)
print("ارزشِ بازارِ بانکِ محلی:", LOCAL)

s = requests.Session()

# ── ۱) تابلو ────────────────────────────────────────────────────────────────
rows = T.polite_get(s, T.MW_URL, "marketwatch") or []
print("\n۱) GetMarketWatch ردیف:", len(rows))
if rows:
    print("   کلیدهایِ یکِ ردیف:", sorted(rows[0].keys()))
    by = {str(r.get("insCode")): r for r in rows}
    for sym, ins in CODES.items():
        r = by.get(ins)
        if r is None:
            print("   %-8s درِ تابلو نیست" % sym)
            continue
        big = {k: v for k, v in r.items()
               if isinstance(v, (int, float)) and v and abs(v) >= 1e8}
        print("   %-8s pcl=%s ztd=%s insDisk=%s | >=1e8: %s | محلی=%s"
              % (sym, r.get("pcl"), r.get("ztd"), r.get("insDisk") or r.get("dsF")
                 or r.get("insDel"), json.dumps(big)[:150], LOCAL.get(sym)))

# ── ۲) GetInstrumentInfo ────────────────────────────────────────────────────
print("\n۲) GetInstrumentInfo (per instrument)")
for sym, ins in CODES.items():
    url = f"{T.BASE}/Instrument/GetInstrumentInfo?i={ins}"
    try:
        d = T.polite_get(s, url, "instrumentInfo")
    except Exception as e:
        print("   %-8s خطا: %s" % (sym, str(e)[:90]))
        continue
    if not d:
        print("   %-8s پاسخِ خالی/بی‌کلید" % sym)
        continue
    inner = d.get("instrumentInfo") if isinstance(d, dict) else d
    if isinstance(inner, dict):
        big = {k: v for k, v in inner.items()
               if isinstance(v, (int, float)) and v and abs(v) >= 1e8}
        print("   %-8s %s | بزرگها: %s" % (sym, sorted(inner.keys())[:14],
                                        json.dumps(big)[:140]))
    else:
        print("   %-8s شکلِ دیگر: %s" % (sym, str(d)[:140]))

# ── ۳) سرِ ستون‌هایِ غربالگرِ سایت (ممکن است marketValue داشته باشد) ────────
print("\n۳) Screen/GetInstrumentColumns — آیا ستونی به نامِ ارزش بازار هست؟")
try:
    d = requests.get(f"{T.BASE}/Screen/GetAllColumns", headers=T.HEADERS, timeout=60)
    txt = d.text
    hits = [w for w in ("marketValue", "mval", "marketCap", "totalValue") if w in txt]
    print("   HTTP %s | طول %s | کلیدهایِ ارزش‌بازارگونه: %s"
          % (d.status_code, len(txt), hits))
    if hits:
        print("   نمونه:", txt[txt.find(hits[0]) - 60:txt.find(hits[0]) + 120] if hits else "")
except Exception as e:
    print("   خطا:", str(e)[:120])
