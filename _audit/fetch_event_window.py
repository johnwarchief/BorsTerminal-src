#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/fetch_event_window.py — ردیف‌هایِ رسمیِ TSETMC حولِ سه رویدادِ حل‌نشده

سه پلۀِ حل‌نشده درِ بانکِ محلی ردیفِ price_history نداشتند (سنجش:
_audit/UNRESOLVED-EVENTS-PROBE.json). پیش ازِ هرِ داوری باید ردیفِ **منتشرشده**
را دید، نه ضریبِ حدسی ساخت. این فایل فقط می‌خواند:

  • CSVِ رسمیِ GetClosingPriceDailyListCSV را ازِ تاریخِ خواستۀِ نماد می‌گیرد
  • روزهایِ اطرافِ رویداد را با ستون‌هایِ خام چاپ می‌کند
  • گسستِ پایه را همان‌طور که قاعدۀِ خودی می‌بیند حساب می‌کند
  • هیچ‌چیز درِ market.db نمی‌نویسد و هیچ ضریبی را با عددِ رهاورد عوض نمی‌کند

اگر شبکه/دسترسی نبود، صریحاً همان «نرسید» ثبت می‌شود.
اجرا: python _audit/fetch_event_window.py
"""
import csv
import datetime as dt
import io
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BASE = "https://cdn.tsetmc.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/csv,application/json;q=0.9,*/*;q=0.8",
    "Referer": "https://cdn.tsetmc.com/",
}
EVENTS = [
    ("فولاژ", "40808043719554948", "2024-07-27"),
    ("لخزر", "65414507129586385", "2026-07-27"),
    ("ولراز", "12901875871456398", "2024-01-30"),
]
OUT = os.path.join(ROOT, "_audit", "EVENT-WINDOW-OFFICIAL-ROWS.json")


def iso(d):
    d = str(d).strip()
    return f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 and d.isdigit() else None


def main():
    out = {"fetchedAt": dt.datetime.now().isoformat(timespec="seconds"), "symbols": []}
    for sym, ins, date in EVENTS:
        rec = {"symbol": sym, "ins_code": ins, "event_date": date, "status": None, "rows": []}
        if not ins:
            rec["status"] = "NO_INS_CODE_KNOWN_LOCALLY"
            out["symbols"].append(rec)
            print("%s %s: no ins_code in the local bank -> nothing to fetch" % (sym, date))
            continue
        frm = (dt.date.fromisoformat(date) - dt.timedelta(days=120)).strftime("%Y%m%d")
        url = f"{BASE}/ClosingPrice/GetClosingPriceDailyListCSV/{ins}/{frm}"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            raw = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as ex:
            rec["status"] = "FETCH_FAILED: %s" % type(ex).__name__
            rec["detail"] = str(ex)[:200]
            out["symbols"].append(rec)
            print("%s %s: FETCH FAILED (%s) %s" % (sym, date, type(ex).__name__, str(ex)[:120]))
            continue
        rows = list(csv.DictReader(io.StringIO(raw)))
        rec["status"] = "OK"
        rec["header"] = list(rows[0].keys()) if rows else []
        parsed = []
        for r in rows:
            k = {(x or "").strip("<>"): (y or "").strip() for x, y in r.items()}
            d = iso(k.get("DTYYYYMMDD", ""))
            if not d:
                continue
            parsed.append({"date": d, "first": k.get("FIRST"), "high": k.get("HIGH"),
                           "low": k.get("LOW"), "close": k.get("CLOSE"), "vol": k.get("VOL"),
                           "open_base": k.get("OPEN"), "last": k.get("LAST")})
        lo = (dt.date.fromisoformat(date) - dt.timedelta(days=14)).isoformat()
        hi = (dt.date.fromisoformat(date) + dt.timedelta(days=14)).isoformat()
        rec["window_rows"] = [p for p in parsed if lo <= p["date"] <= hi]
        rec["total_published_rows"] = len(parsed)
        # گسستِ پایه، همان‌طور که قاعدۀِ خودی تعریف می‌کند: base(t) != close(t-1)
        prev = None
        for p in parsed:
            try:
                b = float(p["open_base"] or 0)
                c = float(p["close"] or 0)
            except ValueError:
                prev = p
                continue
            if prev is not None and prev["close"]:
                try:
                    pc = float(prev["close"])
                except ValueError:
                    pc = 0
                if pc and b and abs(b - pc) / pc > 0.005:
                    rec.setdefault("discontinuities", []).append(
                        {"date": p["date"], "base": b, "prev_close": pc, "ratio": round(b / pc, 8)})
            prev = p
        out["symbols"].append(rec)
        print("%s %s: %d published rows; %d rows in +/-14d window" %
              (sym, date, rec["total_published_rows"], len(rec["window_rows"])))
        for p in rec["window_rows"]:
            print("    %s FIRST=%s CLOSE=%s OPEN(base)=%s VOL=%s" %
                  (p["date"], p["first"], p["close"], p["open_base"], p["vol"]))
        print("    discontinuities in whole series: %s" %
              json.dumps(rec.get("discontinuities", [])[-8:], ensure_ascii=False))

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("out: " + OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
