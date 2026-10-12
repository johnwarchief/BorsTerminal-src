"""`[is6]` را از خودِ باند TSETMC شناسایی می‌کند (بی‌مرورگر).

سه باندِ خامِ سایت که فیلترنویسِ دیده‌بانِ پیشرفته را تغذیه می‌کنند:
  InstValue.aspx?t=a        → mw.InstStat[inscode][key]      (متنِ ۲٫۸MB، ۸٬۸۷۷ موجودیت)
  ClosingPriceAll.aspx      → mw.InstHistory[inscode][slot]  (متنِ ۸٫۳MB، ۱۸۱٬۹۷۱ ردیف)
  GetMarketWatch (API)      → ستون‌هایِ ردیفِ تابلو (tvol/pc/pl/tval…)

خروجی: برایِ هر کلیدِ InstStat، کدام کرانِ [ih] یا کدام ستونِ ردیف دقیقاً همان
عدد است. اگر کلید ۶ با هیچ‌کدام برابر نبود، همین درِ گزارش می‌آید (نه حدس).

اجرا:  PYTHONIOENCODING=utf-8 python tools/tse_is_series_probe.py [--out _audit/...]
"""
import argparse
import gzip
import io
import json
import os
import statistics
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

OLD = "https://old.tsetmc.com/tsev2/data/"
BASE = "https://cdn.tsetmc.com/api"
HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://old.tsetmc.com/",
    "Accept": "*/*",
    "Accept-Encoding": "gzip",
}


def fetch_text(url, cache, timeout=180):
    if os.path.exists(cache):
        with io.open(cache, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with io.open(cache, "w", encoding="utf-8", newline="") as fh:
        fh.write(raw.decode("utf-8", "replace"))
    return raw.decode("utf-8", "replace")


def parse_inst_value(txt):
    """→ {inscode: {key: value}}؛ همان منطقِ mw.LoadInstStat (خطایِ ۱۱/۱۰ ستونه)."""
    out = {}
    cur = ""
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


def parse_closing_all(txt):
    """→ {inscode: {slot: {field: value}}}؛ همان منطقِ mw.LoadInstHistory."""
    out = {}
    cur = ""
    FIELDS = ("PClosing", "PDrCotVal", "ZTotTran", "QTotTran5J", "QTotCap",
              "PriceMin", "PriceMax", "PriceYesterday", "PriceFirst")
    for row in txt.split(";"):
        if not row:
            continue
        c = row.split(",")
        if len(c) == 11:
            cur, vals = c[0], c[2:]
        elif len(c) == 10:
            vals = c[1:]
        else:
            continue
        try:
            slot = int(float(c[0] if len(c) == 10 else c[1]))
        except ValueError:
            continue
        rec = {}
        for i, f in enumerate(FIELDS):
            try:
                rec[f] = float(vals[i])
            except (ValueError, IndexError):
                rec[f] = None
        out.setdefault(cur, {})[slot] = rec
    return out


def market_watch(cache):
    """ردیف‌هایِ تابلو از API رسمی (همان منبعِ اپ)."""
    if os.path.exists(cache):
        with io.open(cache, "r", encoding="utf-8") as fh:
            return json.load(fh)
    pt = "&".join(f"paperTypes[{i}]={i+1}" for i in range(9))
    url = (f"{BASE}/ClosingPrice/GetMarketWatch?market=0&{pt}"
           f"&showTraded=false&withBestLimits=true&hEven=0")
    req = urllib.request.Request(url, headers={**HDRS, "Accept": "application/json",
                                               "Origin": "https://tsetmc.com"})
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    data = json.loads(raw.decode("utf-8", "replace"))
    rows = data.get("marketwatch") or data.get("marketWatchTrack") or []
    with io.open(cache, "w", encoding="utf-8") as fh:
        json.dump(rows, fh)
    return rows


def row_fields(r):
    """نگاشتِ نام‌های ExecFilter به فیلدهایِ API (مستند درِ tape_flags.py)."""
    return {
        "tvol": r.get("qtj"), "tno": r.get("ztt"), "tval": r.get("qtc"),
        "pc": r.get("pcl"), "pl": r.get("pdv"), "py": r.get("pd1"),
        "pmin": r.get("pmn"), "pmax": r.get("pmx"), "pf": r.get("pF"),
        "mv": r.get("bv"), "eps": r.get("eps"), "pe": r.get("pes"),
        "tmin": r.get("pMin"), "tmax": r.get("pMax"), "z": r.get("z"),
        "yval": r.get("yval"), "bvol": r.get("bv"),
    }


def describe(vols, is_v):
    """هر کرانِ ممکن از سریِ حجم که با عددِ سایت برابر است را برمی‌گرداند."""
    hits = []
    n = len(vols)
    if not n or is_v in (None, 0):
        return hits
    for a in range(0, min(n, 61)):
        for b in range(a + 1, min(n, 61) + 1):
            w = vols[a:b]
            if not w:
                continue
            cands = {"mean": sum(w) / len(w), "mean_div_n": sum(w) / (b - a),
                     "median": statistics.median(w), "max": max(w), "min": min(w)}
            for name, q in cands.items():
                if q and abs(q - is_v) / is_v < 0.0008:
                    hits.append({"window": f"[{a}:{b}]", "n": b - a, "stat": name})
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_audit/tse_is_series_probe.json")
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args()
    d = os.path.dirname(a.out) or "."
    iv_path = os.path.join(d, "tse_cache_InstValue.txt")
    ih_path = os.path.join(d, "tse_cache_ClosingPriceAll.txt")
    mw_path = os.path.join(d, "tse_cache_market_watch.json")

    inst = parse_inst_value(fetch_text(OLD + "InstValue.aspx?t=a", iv_path))
    hist = parse_closing_all(fetch_text(OLD + "ClosingPriceAll.aspx", ih_path))
    rows = {r.get("insCode"): r for r in market_watch(mw_path) if r.get("insCode")}

    universe = [c for c in rows if c in inst]
    keys_present = {}
    for c, m in inst.items():
        for k in m:
            if int(k) < 50:
                keys_present[k] = keys_present.get(k, 0) + 1

    sample = []
    for c in universe[:a.limit]:
        m = inst[c]
        if "6" not in m:
            continue
        ih = hist.get(c) or {}
        vols = [ih.get(k, {}).get("QTotTran5J") for k in range(0, 60)]
        vols = [v for v in vols if v is not None]
        caps = [ih.get(k, {}).get("QTotCap") for k in range(0, 60)]
        caps = [v for v in caps if v is not None]
        rf = row_fields(rows[c])
        rec = {"code": c, "sym": rows[c].get("l18"), "is": {k: m[k] for k in sorted(m, key=int)},
               "row": rf, "ih_len": len(ih), "vols_len": len(vols),
               "vols_head": vols[:12]}
        for key in ("5", "6", "16", "15", "1"):
            if key in m:
                rec.setdefault("matches", {})[key] = {
                    "vs_volume": describe(vols, m[key])[:6],
                    "vs_value": describe(caps, m[key])[:3],
                    "vs_row": [f for f, v in rf.items() if v and abs(float(v) - m[key]) / max(1e-9, abs(m[key])) < 0.0008],
                }
        sample.append(rec)

    out = {"generated": "tools/tse_is_series_probe.py",
           "inst_codes": len(inst), "hist_codes": len(hist), "mw_rows": len(rows),
           "universe_overlap": len(universe),
           "keys_present_in_universe": keys_present,
           "key6_present": sum(1 for c, m in inst.items() if "6" in m),
           "samples": sample}
    os.makedirs(d, exist_ok=True)
    with io.open(a.out, "w", encoding="utf-8", newline="") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("universe overlap:", len(universe), "| key6 present:", out["key6_present"])
    print("keys_present_in_universe:", json.dumps(keys_present, sort_keys=True))
    for s in sample[:6]:
        print("==", s["sym"], "| ih", s["ih_len"], "| is6", s["is"].get("6"),
              "| tvol", s["row"]["tvol"])
        print("   matches6:", json.dumps(s.get("matches", {}).get("6"), ensure_ascii=False)[:400])
    print("wrote", a.out)


if __name__ == "__main__":
    main()
