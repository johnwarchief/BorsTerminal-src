"""ta_rows_decode.py — هر سطرِ `market0` (m, st, sf, nsf, cf, scf, lf, b, afl, um)
    را با جمعِ سطل‌هایِ خودِ برنامه می‌سنجد.

چرا: آرایه‌های ۱۸تاییِ TA بی‌برچسب‌اند و برازشِ آزاد (۲^n اتحاد) «تصادفِ عددی»
می‌سازد. راهِ بستنِ این: **خودِ TA هویتِ جبری می‌دهد** — مثلاً `m = st + sf + nsf`
در اندیس‌های ۰/۱/۵. اینجا اول آن هویت‌ها را رویِ پاسخِ زنده چک می‌کنیم (بی‌ما)،
بعد هر سطرِ TA را با سطل‌هایی که از `mstat_engine.classify` می‌آیند مقایسه
می‌کنیم؛ سطرهایی که هویتشان تأیید نشده باشد «سنجیده‌نشده» می‌ماند، نه حدس.

اجرا:  PYTHONIOENCODING=utf-8 python tools/ta_rows_decode.py [--db PATH] [--json OUT]
"""
import argparse
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mstat_engine as ME                                     # noqa: E402

TA_HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://tradersarena.ir/market"}
TA_URL = "https://tradersarena.ir/data/market0"
BT = 1e10          # ریال → میلیارد تومان
BS = 1e9           # سهم → میلیارد سهم
ROWS = ("m", "um", "b", "st", "sf", "nsf", "cf", "scf", "lf", "afl")


def fetch():
    with urllib.request.urlopen(urllib.request.Request(TA_URL, headers=TA_HDR),
                                timeout=60) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d[0] if isinstance(d, list) and d else d


def pct(a, b):
    if not b:
        return None
    return round((a - b) / abs(b) * 100.0, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--json", default="_audit/ta_rows_decode.json")
    args = ap.parse_args()
    ta = fetch()
    print("TA  j=%s d=%s" % (ta.get("j"), ta.get("d")))
    have = {k: ta.get(k) for k in ROWS if isinstance(ta.get(k), list) and len(ta[k]) >= 17}
    print("سطرهایِ موجود:", sorted(have))

    # ── ۱) هویت‌های جبریِ خود TA (بی‌دخالتِ ما) ─────────────────────────────
    print("\n--- هویت‌ها رویِ پاسخِ زنده (تأیید = خطایِ زیرِ ۰٫۵٪) ---")
    identities = []
    combos = [("m", ["st", "sf", "nsf"]), ("m", ["st", "sf", "cf", "scf", "lf"]),
              ("afl", ["st", "sf"]), ("um", ["st", "sf", "nsf"])]
    for tgt, parts in combos:
        if tgt not in have or not all(p in have for p in parts):
            continue
        for idx, unit, name in ((0, BS, "حجم"), (1, BT, "ارزش"), (5, BT, "جریان"),
                                (7, BT, "خرید حقیقی"), (10, BT, "فروش حقیقی"),
                                (13, BT, "خرید حقوقی"), (16, BT, "فروش حقوقی")):
            s = sum(have[p][idx] for p in parts) / unit
            t = have[tgt][idx] / unit
            e = pct(s, t)
            ok = e is not None and abs(e) < 0.5
            if ok or idx in (0, 1):
                print("  %-4s = %-22s در i=%d %-12s : جمع=%12.1f هدف=%12.1f  %+7.3f%% %s"
                      % (tgt, "+".join(parts), idx, name, s, t, e, "✓" if ok else ""))
            identities.append({"lhs": tgt, "parts": parts, "i": idx, "err_pct": e})

    # ── ۲) سطل‌هایِ خودِ برنامه، ردیف‌به‌ردیف ───────────────────────────────
    db = args.db or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs",
                                 "BorsTerminal Ultimate", "market.db")
    conn = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    rows, meta = ME.enrich(conn)
    conn.close()
    print("\nما: d_even=%s h_even=%s n=%s" % (meta.get("d_even"), meta.get("h_even"),
                                             meta.get("n")))
    b = {}
    for r in rows:
        m = r.get("_m") or {}
        key = "%s/%s" % (r.get("cls"), r.get("kind") or "-")
        a = b.setdefault(key, {"n": 0, "val": 0.0, "vol": 0.0, "rb": 0.0, "rs": 0.0,
                               "lb": 0.0, "ls": 0.0, "flow": 0.0})
        a["n"] += 1
        a["val"] += float(m.get("val") or 0.0) / BT
        a["vol"] += float(m.get("vol") or 0.0) / BS
        a["rb"] += float(m.get("retail_buy") or 0.0) / BT
        a["rs"] += float(m.get("retail_sell") or 0.0) / BT
        a["lb"] += float(m.get("inst_buy") or 0.0) / BT
        a["ls"] += float(m.get("inst_sell") or 0.0) / BT
        a["flow"] += float(m.get("flow") or 0.0) / BT
    print("سطل‌ها:")
    for k in sorted(b):
        a = b[k]
        print("  %-14s n=%-5d val=%11.1f vol=%8.3f rb=%11.1f rs=%11.1f flow=%10.1f"
              % (k, a["n"], a["val"], a["vol"], a["rb"], a["rs"], a["flow"]))

    # ── ۳) هر سطرِ TA با کدام اتحادِ معنادار از سطل‌هایِ ما می‌خواند؟ ────────
    GROUPS = {
        "stock_right": ["stock/stock", "right/right"],
        "eq_funds(equity,fof)": ["fund/equity", "fund/fof"],
        "eq_funds(+etf,mixed)": ["fund/equity", "fund/fof", "fund/etf", "fund/mixed"],
        "fixed": ["fund/fixed"],
        "gold": ["fund/gold"], "silver": ["fund/silver"], "lev": ["fund/lev"],
        "commod": ["fund/commod"],
        "other(اوراق/اختيار/تسهیلات…)": ["other/other"],
        "همه": sorted(b),
        "سهمی+ص.سهامی (بدون درآمدثابت)": ["stock/stock", "right/right", "fund/equity",
                                          "fund/fof", "fund/etf", "fund/mixed"],
        "سهمی+ص.سهامی+اهرمی": ["stock/stock", "right/right", "fund/equity", "fund/fof",
                              "fund/etf", "fund/mixed", "fund/lev"],
    }

    def gsum(keys, metric):
        return sum(b[k][metric] for k in keys if k in b)

    print("\n--- سطرِ mِ TA در برابرِ اتحادها (ارزش i=1) ---")
    tgt_val = have["m"][1] / BT
    for name, keys in GROUPS.items():
        s = gsum(keys, "val")
        print("  %-34s = %11.1f  | m[1]=%11.1f → %+7.3f%%" % (name, s, tgt_val,
                                                             pct(s, tgt_val)))
    print("--- سطرِ mِ TA در برابرِ اتحادها (حجم i=0) ---")
    tgt_vol = have["m"][0] / BS
    for name, keys in GROUPS.items():
        s = gsum(keys, "vol")
        print("  %-34s = %8.3f  | m[0]=%8.3f → %+7.3f%%" % (name, s, tgt_vol,
                                                            pct(s, tgt_vol)))
    out = {"taken_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "ta": {k: v for k, v in have.items()}, "our_asof": meta,
           "buckets": b, "groups": GROUPS, "identities": identities}
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    json.dump(out, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n→", args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
