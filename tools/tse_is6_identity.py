"""هویتِ `[is6]`: هر عددِ Publish-shدهٔ `GetInstrumentInfo` را با `[is5]`/`[is6]` می‌سنجد.

مبنایِ تطبیق، خودِ باندِ TSETMC است (نه بازسازیِ محلی):
  [is6] = mw.InstStat[inscode][6] از `tsev2/data/InstValue.aspx?t=a`
و نامزدِ معنا: فیلدهایِ عددیِ `Instrument/GetInstrumentInfo/{insCode}` — از جمله
`qTotTran5JAvg` (میانگین حجم) که درِ `tools/market_tape_live_audit.py` هم ثبت شده.

اجرا: PYTHONIOENCODING=utf-8 python tools/tse_is6_identity.py [--n 14]
"""
import argparse
import gzip
import io
import json
import os
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://cdn.tsetmc.com/api"
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://tsetmc.com/", "Origin": "https://tsetmc.com",
        "Accept": "application/json"}


def jget(url, timeout=60):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8", "replace"))


def inst_values(path="_audit/tse_cache_InstValue.txt"):
    if not os.path.exists(path):
        raise SystemExit("ابتدا tools/tse_is_series_probe.py را اجرا کن تا " + path)
    txt = io.open(path, encoding="utf-8", errors="replace").read()
    out, cur = {}, ""
    for row in txt.split(";"):
        if not row:
            continue
        c = row.split(",")
        if len(c) == 3:
            cur = c[0]
            out.setdefault(cur, {})[c[1]] = float(c[2])
        elif len(c) == 2 and cur:
            out.setdefault(cur, {})[c[0]] = float(c[1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=14)
    a = ap.parse_args()
    iv = inst_values()
    codes = [c for c, m in iv.items() if "6" in m and m["6"] > 0][: a.n]
    report = []
    for c in codes:
        m = iv[c]
        try:
            d = jget(f"{BASE}/Instrument/GetInstrumentInfo/{c}")
        except Exception as e:
            report.append({"code": c, "error": repr(e)[:90]})
            continue
        ii = d.get("instrumentInfo") or {}
        nums = {k: v for k, v in ii.items() if isinstance(v, (int, float)) and v}
        hits = []
        for k, v in nums.items():
            for want, label in ((m.get("6"), "is6"), (m.get("5"), "is5")):
                if want and abs(v - want) / max(1.0, abs(want)) < 0.0009:
                    hits.append({"field": k, "field_value": v, "equals": label, "is": want})
        report.append({"code": c, "symbol": ii.get("symbol"), "is5": m.get("5"), "is6": m.get("6"),
                       "info_fields": {k: nums[k] for k in sorted(nums)}, "hits": hits})
        time.sleep(0.4)
    out = "_audit/tse_is6_identity.json"
    with io.open(out, "w", encoding="utf-8", newline="") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    for r in report:
        if "error" in r:
            print(r["code"], "ERR", r["error"])
            continue
        print("==", r.get("symbol") or r["code"], "is5", r["is5"], "is6", r["is6"])
        print("   info:", json.dumps(r["info_fields"], ensure_ascii=False)[:300])
        print("   hits:", json.dumps(r["hits"], ensure_ascii=False)[:240])
    print("wrote", out)


if __name__ == "__main__":
    main()
