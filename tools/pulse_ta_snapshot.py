"""پیانگِ نبض بازار در برابرِ تریدرزآرنا — یک لحظه، دو طرف، بی‌دست‌کاریِ کد

فقط GETِ خواندنی: چهار اندپوینتِ `/api/mstat/*` خودِ برنامه و چهار فیدِ عمومیِ
tradersarena. همه درِ یک لحظه (کمتر از ۲۰ ثانیه فاصله) و عیناً در JSON می‌نشینند
تا مقایسه «با حدس» نباشد. تبدیلِ واحد این‌جا انجام نمی‌شود؛ فقط خامِ دو طرف.

اجرا:  python tools/pulse_ta_snapshot.py [--out _audit/pulse_ta_snapshot.json]
"""
import argparse
import io
import json
import os
import time
import urllib.request

APP = "http://127.0.0.1:8001"
TA = "https://tradersarena.ir"
TA_HDR = {"User-Agent": "Mozilla/5.0", "Referer": TA + "/market",
          "Accept": "application/json"}

APP_PATHS = ["/api/update/version", "/api/mstat/summary", "/api/mstat/smart-money",
             "/api/mstat/thermometer", "/api/mstat/depth", "/api/mstat/industries",
             "/api/mstat/timeline?mode=cum", "/api/mstat/mainwatch"]
TA_PATHS = ["/data/market0", "/data/market/chart/totals0",
            "/data/market/histo-status", "/data/industries-csv",
            "/data/mainwatch/symbols"]


def get(url, hdr=None):
    try:
        req = urllib.request.Request(url, headers=hdr or {})
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read().decode("utf-8", "replace")
        try:
            return json.loads(body), None
        except Exception:
            return body[:2000], None      # CSVهایِ ta/ عیناً متن‌اند
    except Exception as e:                 # noqa: BLE001 — سنجش نباید بشکند
        return None, "%s: %s" % (type(e).__name__, e)


def tail_list(v, n=3):
    """فیدِ TA آرایه‌ایِ طولانی است؛ برایِ JSONِ شهود تنها چندهایِ آخر می‌ماند."""
    if isinstance(v, list) and len(v) > 12:
        return {"__len__": len(v), "__tail__": v[-n:]}
    if isinstance(v, dict):
        return {k: tail_list(x, n) for k, x in v.items()}
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_audit/pulse_ta_snapshot.json")
    args = ap.parse_args()
    snap = {"taken_at_local": time.strftime("%Y-%m-%d %H:%M:%S")}
    for p in APP_PATHS:
        d, err = get(APP + p)
        snap.setdefault("app", {})[p] = tail_list(d) if d is not None else err
    app_done = time.strftime("%H:%M:%S")
    for p in TA_PATHS:
        d, err = get(TA + p, TA_HDR)
        snap.setdefault("ta", {})[p] = tail_list(d, 4) if d is not None else err
    snap["app_done_at"] = app_done
    snap["ta_done_at"] = time.strftime("%H:%M:%S")
    io.open(args.out, "w", encoding="utf-8").write(
        json.dumps(snap, ensure_ascii=False, indent=1))
    print("snapshot →", args.out, "| app", snap["app_done_at"], "ta", snap["ta_done_at"])
    bad = [k for side in ("app", "ta") for k, v in snap[side].items() if isinstance(v, str)]
    print("unreachable:", bad or "none")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
