# _audit/ra365_phase2_replay.py — Phase 2 read-only parity replay on the FROZEN snapshot
# هدف: baseline قابل‌بازتولید + قبل/after اثبات‌پذیر برایِ RC3، بدونِ بازنویسیِ شواهدِ
# پیشین و بدونِ لمسِ `market.db`. روشِ آماری عیناً همان را365_stage3_summary.py است:
# **تجمیعِ خطایِ تکتکِ کندل‌ها رویِ همهٔ تاریخ** (نه میانگیِ میانه‌هایِ نمادی).
# هیچ عددی جعل نمی‌شود؛ بازوها فقط رویِ کندل‌هایِ مشترکِ همان snapshot سنجیده می‌شوند.
import json
import os
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from api import chart as CH  # noqa: E402  # _factors_from_eventsِ زنگی، برایِ بازسازیِ فاکتور

REF_PATH = f"{ROOT}/_audit/ra365_ref_bars.json"
PROD_PATH = f"{ROOT}/_audit/ra365_product_bars.json"
CORPUS_PATH = f"{ROOT}/_audit/ra365_corpus.json"
TEHRAN = timezone(timedelta(hours=3, minutes=30))
TOL = 0.0005          # تلورانسِ نسبیِ مرجع (۰٫۰۵٪)
TOL_ABS_RIAL = 0.6    # کفِ ریالیِ ضدِ واگراییِ جعلیِ گردکردنِ TSETMC


def _tehran_date(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TEHRAN).date().isoformat()


def ref_close(R, sym, suf):
    e = R["bars"].get(f"{sym}|{suf}|D")
    if not e or e.get("status") != 200:
        return {}
    return {_tehran_date(b): b["c"] for b in e["bars"] if b.get("c")}


def prod_series(P, sym, path, basis, adjust):
    rec = P[sym][path]
    fac = {f["time"]: f["factor"] for f in (rec.get("factors") or [])}
    out = {}
    for c in rec["candles"]:
        base = c.get("last") if basis == "last" else c.get("closing", c.get("close"))
        out[c["time"]] = (base, fac.get(c["time"], 1.0) if adjust else 1.0)
    return out


def quant(a, q):
    if not a:
        return float("nan")
    return a[min(len(a) - 1, max(0, int(round(q * (len(a) - 1)))))]


def measure(P, ref_suf, path="live", basis="last", adjust=True, keep_from=None):
    """تجمیعِ close-only. برمی‌گرداند: n، within_tol_pct، median/p90/p95/p99، max، و per_sym."""
    R = json.load(open(REF_PATH, encoding="utf-8"))
    CORPUS = json.load(open(CORPUS_PATH, encoding="utf-8"))
    errs, per_sym = [], []
    hit = 0
    for c in CORPUS:
        sym = c["sym"]
        if sym not in P:
            continue
        rf = ref_close(R, sym, ref_suf)
        pd_ = prod_series(P, sym, path, basis, adjust)
        common = sorted(set(rf) & set(pd_))
        if keep_from:
            common = [d for d in common if d >= keep_from]
        se = []
        sym_hit = 0
        for d in common:
            base, f = pd_[d]
            ours = base * f
            rel = abs(ours - rf[d]) / rf[d] if rf[d] else 0.0
            se.append(rel)
            if abs(ours - rf[d]) <= max(abs(rf[d]) * TOL, TOL_ABS_RIAL):
                sym_hit += 1
                hit += 1
        se.sort()
        errs.extend(se)
        per_sym.append({"symbol": sym, "common": len(common), "hit": sym_hit,
                        "within_pct": round(100 * sym_hit / len(common), 2) if common else 0.0,
                        "median_pct": round(100 * quant(se, 0.5), 4),
                        "p95_pct": round(100 * quant(se, 0.95), 4),
                        "max_pct": round(100 * (se[-1] if se else 0), 4)})
    e = sorted(errs)
    return {"n": len(errs), "within_tol_pct": round(100 * hit / len(errs), 2) if errs else 0.0,
            "median_pct": round(100 * quant(e, 0.5), 4), "p90_pct": round(100 * quant(e, 0.9), 4),
            "p95_pct": round(100 * quant(e, 0.95), 4), "p99_pct": round(100 * quant(e, 0.99), 4),
            "max_pct": round(100 * (e[-1] if e else 0), 4), "per_symbol": per_sym}


def rebuild_product(prod, new_events_by_sym):
    """نسخۀِ prodِ تازه با رویدادهایِ regroup‌شده؛ فاکتورِ جدید با خودِ
    _factors_from_eventsِ زنگی. کندل/حجم دست‌نخورده. بی‌تغییری‌ها همان‌جا می‌مانند."""
    import copy
    prod2 = copy.deepcopy(prod)
    for sym, events in new_events_by_sym.items():
        if sym not in prod2:
            continue
        rec = prod2[sym]["live"]
        times = [c["time"] for c in rec["candles"]]
        fct = CH._factors_from_events(times, events)
        rec["factors"] = [{"time": t, "factor": f} for t, f in zip(times, fct)]
        rec["adjustEvents"] = events
    return prod2


def main():
    prod = json.load(open(PROD_PATH, encoding="utf-8"))
    print("=== BASELINE (snapshot یخ‌زدۀِ مرحلۀِ ۳، همهٔ تاریخ، فقط close) ===")
    r0 = measure(prod, "type0", path="live", basis="last", adjust=False)
    r1 = measure(prod, "type7", path="live", basis="last", adjust=True)
    for label, m in (("R0 خام↔type0", r0), ("R1 عملکردی↔type7", r1)):
        print(f"  {label:20s} n={m['n']:6d} within={m['within_tol_pct']:5.2f}% "
              f"median={m['median_pct']:6.4f}% p90={m['p90_pct']:5.3f}% "
              f"p95={m['p95_pct']:5.3f}% p99={m['p99_pct']:6.3f}% max={m['max_pct']:6.3f}%")
    print("  مرجعِ داوری (RA365-STAGE3-SUMMARY): R0 n=17467 within=99.99% | "
          "R1 within=23.79% median=0.2105% p90=1.5364% p99=6.992% max=12.954%")


if __name__ == "__main__":
    main()
