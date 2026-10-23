# -*- coding: utf-8 -*-
"""Round 20 projection: type7 OHLC parity before/after raw H/L preservation.

Uses the frozen 29-symbol product/ref fixtures and the cached TSETMC CSV.  The
after arm replaces only the display H/L source with the raw CSV H/L, then
re-applies the existing factor and widen rule.  This is a projection on the
same dates, not a live re-pull; it isolates the raw-field fix.
"""
import io
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
OUT = "artifacts/ra365/r20-fix"
CACHE = "D:/BorsTerminal-tmp/ra365_round18"
TEHRAN = timezone(timedelta(hours=3, minutes=30))
TOL = 0.0005
ABS = 0.6


def td(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(TEHRAN).date().isoformat()


def csv_by_date(ins):
    p = os.path.join(CACHE, "cache", "tsetmc_csv", str(ins) + ".csv")
    if not os.path.exists(p):
        return {}
    out = {}
    for ln in io.open(p, encoding="utf-8-sig", errors="replace"):
        parts = ln.strip().split(",")
        if len(parts) < 12 or not parts[1].isdigit() or len(parts[1]) != 8:
            continue
        try:
            hi, lo, first = float(parts[3]), float(parts[4]), float(parts[2])
        except ValueError:
            continue
        d = f"{parts[1][:4]}-{parts[1][4:6]}-{parts[1][6:]}"
        out[d] = {"h": hi, "l": lo, "o": first}
    return out


def main():
    R = json.load(open("_audit/ra365_ref_bars.json", encoding="utf-8"))
    P = json.load(open("_audit/ra365_product_bars.json", encoding="utf-8"))
    corpus = json.load(open("_audit/ra365_corpus.json", encoding="utf-8"))
    ins_by_sym = {}
    for line in io.open(os.path.join(CACHE, "cohort.jsonl"), encoding="utf-8"):
        d = json.loads(line)
        ins_by_sym[d.get("symbol")] = d.get("ins_code")
    counts = Counter()
    for c in corpus:
        sym = c["sym"]
        ref = R["bars"].get(f"{sym}|type7|D") or {}
        rf = {td(b): b for b in (ref.get("bars") or [])}
        live = P[sym]["live"]
        fac = {f["time"]: f["factor"] for f in (live.get("factors") or [])}
        csv = csv_by_date(ins_by_sym.get(sym))
        for cd in live.get("candles") or []:
            d = cd["time"]
            r = rf.get(d)
            if not r:
                continue
            f = fac.get(d, 1.0)
            base = cd.get("last") if cd.get("last") is not None else cd.get("closing")
            if base is None:
                continue
            before = {"o": cd["open"] * f, "h": cd["high"] * f,
                      "l": cd["low"] * f, "c": base * f}
            raw = csv.get(d) or {}
            rh = raw.get("h", cd.get("high_raw"))
            rl = raw.get("l", cd.get("low_raw"))
            op = cd["open"]
            nh = max(rh, op, base) if rh else cd["high"]
            nl = min(rl, op, base) if rl else cd["low"]
            after = {"o": op * f, "h": nh * f, "l": nl * f, "c": base * f}
            for fld in ("o", "h", "l", "c"):
                for arm, vals in (("before", before), ("after", after)):
                    refv = r[fld]
                    ok = abs(vals[fld] - refv) <= max(abs(refv) * TOL, ABS)
                    counts[(arm, fld, "cmp")] += 1
                    if ok:
                        counts[(arm, fld, "ok")] += 1
    out = {}
    for arm in ("before", "after"):
        out[arm] = {}
        for fld in ("o", "h", "l", "c"):
            cmp = counts[(arm, fld, "cmp")]; ok = counts[(arm, fld, "ok")]
            out[arm][fld] = {"compared": cmp, "ok": ok,
                             "ok_pct": round(100.0 * ok / cmp, 4) if cmp else None}
    json.dump(out, open(os.path.join(OUT, "type7-ohlc-projection.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
