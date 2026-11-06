# یک‌بارمصرف — آیا TSETMC مکانیزم incremental می‌دهد؟ (MarketWatchPlus و نامزدها)
# فقط GET؛ بدون نوشتن روی anything. بازار بسته است؛ درخواست‌ها از polite_get خودِ اپ.
import json
import sys
import time

sys.path.insert(0, r"C:\Users\PCMOD\Desktop\BorsTerminal")
import test_tsetmc as T   # noqa: E402

s = T.make_session()
CANDS = [
    ("mwp-aspx-a=m", "https://cdn.tsetmc.com/tsev2/data/MarketWatchPlus.aspx?a=m&h=0&o=0,1&n=1&in="),
    ("mwp-aspx-a=s", "https://cdn.tsetmc.com/tsev2/data/MarketWatchPlus.aspx?a=s&h=0&o=0,1&n=1&in="),
    ("mwp-api-board", "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatchPlus?market=0&hEven=0"),
    ("mwp-api-2", "https://cdn.tsetmc.com/api/MarketWatch/GetMarketWatchPlus?market=0&hEven=0"),
    ("deven", "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatchDeven?market=0"),
    ("insinfo", "https://cdn.tsetmc.com/api/Instrument/GetInstrumentInsTradeDetailData"
                "?i=46348559193224090&ins=35366681030756042"),
    ("liveinfo", "https://cdn.tsetmc.com/api/Instrument/GetInstrumentLiveInfo?i=46348559193224090"),
    ("clienttype", "https://cdn.tsetmc.com/api/ClientType/GetClientTypeAll"),
    ("board-current", "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&showTraded=false"
                      "&withBestLimits=false&hEven=0&paperTypes[0]=1"),
]
for name, url in CANDS:
    t0 = time.time()
    try:
        r = s.get(url, headers=T.HEADERS, timeout=45, stream=True)
        raw = r.content
        dt = time.time() - t0
        head = raw[:120].decode("utf-8", "replace")
        kind = "JSON" if raw[:1] in (b"[", b"{") else ("HTML" if b"<html" in raw[:400].lower() else "other")
        rows = 0
        if kind == "JSON":
            try:
                d = json.loads(raw.decode("utf-8", "replace"))
                if isinstance(d, dict):
                    for v in d.values():
                        if isinstance(v, list):
                            rows = len(v)
                            break
                    print("   dict keys:", list(d)[:8])
                elif isinstance(d, list):
                    rows = len(d)
                    if d and isinstance(d[0], dict):
                        print("   row keys:", sorted(d[0].keys())[:14])
            except Exception as e:
                print("   json err", e)
        print(name + " | HTTP " + str(r.status_code) + " | " + kind + " | "
              + str(len(raw)) + " B | " + str(round(dt, 2)) + "s | rows=" + str(rows))
        if kind == "other":
            print("      head:", head[:100])
    except Exception as e:
        print(name + " | ERR " + str(e)[:90])
    time.sleep(0.4)
