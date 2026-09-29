"""ta_scope_fit.py — کدام اتحادِ کلاس‌های ما عددِ تریدرزآرنا را بازتولید می‌کند؟

چرا این ابزار: پروکسۀ `/api/market-status/*` حذف شده و فیدِ خامِ `market0`
بی‌نامِ فارسی است؛ پس «تریدرزآرنا چه دامنه‌ای را می‌شمارد» نمی‌تواند حدس باشد.
اینجا همان موتورِ خودِ برنامه (`mstat_engine.enrich`) ردیف‌به‌ردیفِ نمادها را
می‌دهد؛ ما آن‌ها را به سطل‌هایِ جدای (cls × kind) تقسیم می‌کنیم و هر عددِ TA را
با هر اتحادِ ممکنِ سطل‌ها می‌سنجیم و نزدیک‌ترین‌ها را با درصدِ خطا چاپ می‌کنیم.
اگر یک اتحادِ کوچک، چند عددِ هم‌خانواده را هم‌زمان زیر ۱٪ بزند، آن‌وقت دامنهٔ
تریدرزآرنا کشف شده است — نه حدس.

فقط خواندنی: کوئری `mode=ro` رویِ بانک + یک GETِ عمومیِ TA.

اجرا:  PYTHONIOENCODING=utf-8 python tools/ta_scope_fit.py [--db PATH] [--json OUT]
"""
import argparse
import itertools
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mstat_engine as ME                                        # noqa: E402

TA_HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://tradersarena.ir/market"}
TA_URL = "https://tradersarena.ir/data/market0"
RIAL_TO_BT = 1e10          # ریال → میلیارد تومان (تأییدشده در tools/ta_local_parity.py)
SHARES_TO_B = 1e9          # سهم → میلیارد سهم
CLUSTER_KEYS = ("m", "um", "b", "st", "sf", "nsf", "cf", "scf", "lf", "afl")


def ta_feed():
    req = urllib.request.Request(TA_URL, headers=TA_HDR)
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8"))
    if isinstance(d, list):
        d = d[0] if d else {}
    return d


def bucketize(rows):
    """سطل = (cls, kind). واحدها: ارزش/جریان در میلیارد تومان، حجم در میلیارد سهم."""
    b = {}
    for r in rows:
        m = r.get("_m") or {}
        key = "%s/%s" % (r.get("cls"), r.get("kind") or "-")
        a = b.setdefault(key, {"n": 0, "val": 0.0, "vol": 0.0, "flow": 0.0,
                               "up": 0, "down": 0, "flat": 0})
        a["n"] += 1
        a["val"] += _num(m.get("val")) / RIAL_TO_BT
        a["vol"] += _num(m.get("vol")) / SHARES_TO_B
        a["flow"] += _num(m.get("flow")) / RIAL_TO_BT
        pc = r.get("price_change")
        if pc is None:
            pc = m.get("vwap") and None
        if isinstance(pc, (int, float)):
            if pc > 0:
                a["up"] += 1
            elif pc < 0:
                a["down"] += 1
            else:
                a["flat"] += 1
    return b


def _num(v):
    try:
        return float(v or 0.0)
    except (TypeError, ValueError):
        return 0.0


def best_fits(target, buckets, metric, top=5, tol=0.02, max_size=6):
    keys = sorted(buckets)
    out = []
    for size in range(1, min(max_size, len(keys)) + 1):
        for combo in itertools.combinations(keys, size):
            s = sum(buckets[k][metric] for k in combo)
            if target:
                out.append((abs((s - target) / target), (s - target) / target, size,
                            combo, s))
    out.sort()
    return [o for o in out[:top] if o[0] <= tol]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--json", default="_audit/ta_scope_fit.json")
    args = ap.parse_args()
    db = args.db or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs",
                                 "BorsTerminal Ultimate", "market.db")
    if not os.path.exists(db):
        print("بانک پیدا نشد:", db)
        return 1
    ta = ta_feed()
    m = ta.get("m") or []
    if len(m) < 18:
        print("پاسخِ TA کوتاه است:", len(m))
        return 1
    conn = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    rows, meta = ME.enrich(conn)
    conn.close()
    b = bucketize(rows)

    print("TA:", ta.get("j"), ta.get("d"), "| ما:", json.dumps(meta, ensure_ascii=False)[:160])
    print("سطل‌ها (%d):" % len(b))
    for k in sorted(b):
        a = b[k]
        print("  %-10s n=%-5d val=%12.1f vol=%9.3f flow=%10.1f up/dn/flat=%d/%d/%d"
              % (k, a["n"], a["val"], a["vol"], a["flow"], a["up"], a["down"], a["flat"]))

    targets = [("m1", "کل (ارزش)", m[1], "val"), ("m7", "سهمی (ارزش)", m[7], "val"),
               ("m0", "کل (حجم)", m[0], "vol"), ("m5", "کل (جریان)", m[5], "flow"),
               ("m13", "خوشۀ ۱۳", m[13], "val"), ("m16", "خوشۀ ۱۶", m[16], "val"),
               ("m12", "شمارد ۱۲", m[12], "n"), ("m17", "شمارد ۱۷", m[17], "n")]
    report = {"taken_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "ta_j": ta.get("j"), "ta_d": ta.get("d"), "ta_m": m,
              "buckets": b, "fits": {}}
    print("\n--- برازش (|خطا| ≤ ۲٪) ---")
    for name, label, tgt_raw, metric in targets:
        tgt = tgt_raw / (RIAL_TO_BT if metric in ("val", "flow") else
                         (SHARES_TO_B if metric == "vol" else 1.0))
        if metric == "n":
            tgt = float(tgt_raw)
        near = best_fits(tgt, b, metric, tol=0.02)
        print("\n%s %s = %s" % (name, label, f"{tgt:,.2f}"))
        if not near:
            near = best_fits(tgt, b, metric, top=3, tol=9e9, max_size=4)
            print("   ✗ هیچ اتحادی زیر ۲٪ نبود؛ نزدیک‌ترین‌ها:")
        for _, err, size, combo, s in near[:5]:
            print("   %+7.3f%% = %14s  ← %d سطل: %s"
                  % (err * 100, f"{s:,.2f}", size, ",".join(combo)))
        report["fits"][name] = {"label": label, "target": tgt, "metric": metric,
                                "cands": [{"err_pct": round(e * 100, 4), "sum": s,
                                           "buckets": list(c)}
                                          for _, e, _, c, s in near[:5]]}
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    json.dump(report, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n→", args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
