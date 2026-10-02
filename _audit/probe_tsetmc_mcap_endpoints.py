# یک‌بارمصرف — شکارِ «ارزش بازارِ مستقیمِ TSETMC» در endpoint هایِ نامزد
import json
import sqlite3
import sys

import requests

sys.path.insert(0, r"C:\Users\PCMOD\Desktop\BorsTerminal")
import test_tsetmc as T  # noqa: E402

db = sqlite3.connect("file:market.db?mode=ro", uri=True)
INS = dict(db.execute("SELECT l_val18, ins_code FROM instruments "
                      "WHERE l_val18 IN ('فولاد','نشار','شبندر')"))
s = requests.Session()
TIMEOUT = 45


def hit(sym, url, note=""):
    try:
        r = s.get(url, headers=T.HEADERS, timeout=TIMEOUT)
    except Exception as e:
        print("   %-8s %s → خطا %s" % (sym, note, str(e)[:70]))
        return None
    if r.status_code != 200 or not r.text.strip():
        print("   %-8s %s → HTTP %s (%d بایت)" % (sym, note, r.status_code, len(r.text or "")))
        return None
    try:
        d = r.json()
    except Exception:
        print("   %-8s %s → HTTP 200 ولی JSON نیست (%s…)" % (sym, note, r.text[:60]))
        return None
    flat = json.dumps(d, ensure_ascii=False)
    caps = [k for k in ("marketValue", "marketCap", "mv", "totalValue", "zValue")
            if ('"%s"' % k) in flat]
    print("   %-8s %s → HTTP 200 | %d بایت | کلیدهایِ ارزش‌بازار: %s"
          % (sym, note, len(flat), caps))
    for k in caps:
        i = flat.find('"%s"' % k)
        print("        %s" % flat[max(0, i - 40):i + 70])
    return d


print("نامزدها برایِ فولاد/نشار/شبندر:")
for sym, ins in INS.items():
    hit(sym, f"{T.BASE}/Instrument/GetInstrumentInfo?i={ins}&_language=en", "GetInstrumentInfo?_language=en")
    hit(sym, f"{T.BASE}/Instrument/GetInstrumentInfoRaw?i={ins}", "GetInstrumentInfoRaw")
    hit(sym, f"https://www.tsetmc.com/tsev2/data/instinfofast.aspx?i={ins}&p=0", "tsev2 instinfofast")
    hit(sym, f"https://cdn.tsetmc.com/tsev2/data/instinfofast.aspx?i={ins}&p=1", "cdn tsev2 instinfofast")
    hit(sym, f"{T.BASE}/Valued/GetPriceVolumeHistoryForSymbolRange?insCode={ins}"
             f"&startDate=20260901&endDate=20260930", "Valued history range")
    hit(sym, f"{T.BASE}/Instrument/GetInstrumentHistoryAll?i={ins}&m=0", "GetInstrumentHistoryAll")
