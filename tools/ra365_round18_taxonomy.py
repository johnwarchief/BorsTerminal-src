# -*- coding: utf-8 -*-
"""Round 18 row-level cause taxonomy for raw OHLC mismatches.

Reads the fixed cohort, the TSETMC reference DB, Rahavard type0/type7 and the
local price_history fallback.  A row gets one primary cause; every field that
contributed is recorded.  Missing bars stay in the coverage table and are never
counted as numeric differences.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import sqlite3
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get("RA365_R18_CACHE", "D:/BorsTerminal-tmp/ra365_round18")
ART = os.path.join(ROOT, "artifacts", "ra365", "r18")
DB = "D:/BorsTerminal-tmp/ra365_round17/market_r17_migrated.db"
CACHE_CSV = os.path.join(CACHE, "cache", "tsetmc_csv")

spec = importlib.util.spec_from_file_location(
    "r18", os.path.join(ROOT, "tools", "ra365_round18_raw.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

CONTRACT = ("open_eff", "high_contract", "low_contract", "close_official",
            "close_last", "close_display", "volume")
FALLBACK = ("local-db-fallback", "local-db-unseen")


def load_variant_rows(manifest_symbol_rows, date, ins_code):
    out = []
    for r in manifest_symbol_rows:
        if r["ins_code"] == ins_code:
            continue
        p = os.path.join(CACHE_CSV, r["ins_code"] + ".csv")
        if not os.path.exists(p):
            continue
        for ln in open(p, encoding="utf-8", errors="replace").read().splitlines()[1:]:
            q = [x.strip() for x in ln.split(",")]
            if len(q) < 12 or q[1] != date.replace("-", ""):
                continue
            try:
                out.append((r["symbol"], r["ins_code"], float(q[2] or 0), float(q[3]),
                            float(q[4]), float(q[5]), float(q[7] or 0),
                            float(q[10] or 0), float(q[11] or 0)))
            except ValueError:
                pass
    return out


def classify_row(asset, c, t, c0, c7, dbrow, variant_rows, near_t):
    """Return (cause, confidence, evidence, bad_fields)."""
    date = c[0]
    basis = asset.get("basis") or "last"
    t_first, t_high, t_low, t_close, t_vol, t_base, t_last = (
        t[1], t[2], t[3], t[4], t[5], t[6], t[7])
    o_eff = R._eff_open(t_first, t_base, t_high, t_low, t_close)
    hi_p, lo_p = R._widen(o_eff, t_high, t_low, t_close)
    chosen = t_last if (basis == "last" and t_last > 0) else t_close
    hi_c, lo_c = max(hi_p, chosen), min(lo_p, chosen)
    refs = {
        "open_eff": (o_eff, c[1]),
        "high_contract": (hi_c, c[2]),
        "low_contract": (lo_c, c[3]),
        "close_official": (t_close, c[5]),
        "close_last": (t_last if t_last > 0 else None, c[6]),
        "close_display": (chosen, c[4]),
        "volume": (t_vol, c[9]),
    }
    bad = []
    for f in CONTRACT:
        ref, prod = refs[f]
        st = R._status(ref, prod)
        if st not in ("EXACT", "TOL", "NULL"):
            bad.append((f, ref, prod, st))
    if not bad:
        return None
    # fallback / legacy DB: product row equals the local price_history row
    if dbrow is not None and asset.get("adjust_source") in FALLBACK:
        same = 0
        checks = [(c[1], dbrow[1]), (c[2], dbrow[2]), (c[3], dbrow[3]),
                  (c[5], dbrow[4]), (c[9], dbrow[5])]
        for a, b in checks:
            if a is not None and b is not None and abs(float(a) - float(b)) <= 0.5:
                same += 1
        if same >= 3:
            return ("FALLBACK_DB_SOURCE", "HIGH",
                    "product row equals local price_history (src=%s); published TSETMC differs"
                    % (dbrow[7] if len(dbrow) > 7 else "NULL"), bad)
    # wrong instrument version
    for (vsym, vins, vf, vh, vl, vc, vv, vb, vlast) in variant_rows:
        if abs(vf - c[1]) <= 0.5 and abs(vh - c[2]) <= 0.5 and abs(vl - c[3]) <= 0.5 \
                and abs(vc - c[5]) <= 0.5:
            return ("INSTRUMENT_MAPPING", "MEDIUM",
                    "product matches variant %s/%s" % (vsym, vins), bad)
    # adjusted data in the raw layer
    if c7 is not None and c0 is not None:
        for f, idx in (("open_eff", 1), ("high_contract", 2),
                       ("low_contract", 3), ("close_official", 5)):
            pv = c[idx]
            if pv is not None and c7[idx] is not None and abs(float(pv) - float(c7[idx])) <= 0.5 \
                    and abs(float(c0[idx]) - float(c7[idx])) > 0.5:
                return ("RAW_ADJUSTED_MISMATCH", "MEDIUM",
                        "product %s equals type7, not type0" % f, bad)
    # source divergence: product agrees with Rahavard type0, TSETMC differs
    if c0 is not None:
        for f, idx in (("open_eff", 1), ("high_contract", 2),
                       ("low_contract", 3), ("close_official", 5),
                       ("close_display", 4)):
            pv = c[idx]
            if pv is not None and c0[idx] is not None and abs(float(pv) - float(c0[idx])) <= 0.5:
                return ("SOURCE_DATA_DIVERGENCE", "HIGH",
                        "product %s matches type0 but TSETMC=%s" % (f, refs[f][0]), bad)
    # field mapping: open base vs first trade, close last vs official
    for f, ref, prod, st in bad:
        if f == "open_eff" and t_first > 0 and t_base > 0 and abs(prod - t_base) <= 0.5:
            return ("FIELD_MAPPING", "HIGH", "open equals base <OPEN>, not <FIRST>", bad)
        if f == "close_official" and abs(prod - t_last) <= 0.5 and abs(t_last - t_close) > 0.5:
            return ("FIELD_MAPPING", "MEDIUM", "official close compared to last trade", bad)
    # adjacent trading date (calendar +/-3 days)
    for f, ref, prod, st in bad:
        idx = {"open_eff": 1, "high_contract": 2, "low_contract": 3,
               "close_official": 4, "close_last": 7, "close_display": 4,
               "volume": 5}.get(f)
        if idx is None:
            continue
        for nt in near_t:
            if nt[idx] is not None and abs(float(nt[idx]) - float(prod)) <= max(0.5, 1e-6 * abs(float(nt[idx]))):
                return ("DATE_MAPPING", "MEDIUM",
                        "product %s matches TSETMC row at %s" % (f, nt[0]), bad)
    # scale / precision
    for f, ref, prod, st in bad:
        if st == "ROUNDING":
            return ("PRECISION_OR_ROUNDING", "HIGH", "relative diff <= 0.05%", bad)
        if ref and any(abs(prod / ref - k) <= 0.001 for k in
                       (10, 100, 1000, 0.1, 0.01, 0.001)):
            return ("PRICE_SCALE_OR_UNIT", "HIGH", "ratio=%.6f" % (prod / ref), bad)
    # current TSETMC is the only surviving source: the product snapshot is older
    if c0 is not None:
        for f, idx in (("close_official", 5), ("close_display", 4)):
            pv = c[idx]
            if pv is not None and c0[idx] is not None and abs(float(pv) - float(c0[idx])) > 0.5:
                return ("HISTORICAL_REVISION", "MEDIUM",
                        "product differs from both type0 and current TSETMC", bad)
    return ("UNCLASSIFIED", "LOW", "no single evidence path", bad)


def main():
    ref = sqlite3.connect(f"file:{os.path.join(CACHE, 'reference.db')}?mode=ro", uri=True)
    local = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    man = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(
            ROOT, "_audit", "RAHAVARD-FULL-UNIVERSE-MANIFEST-v2-2026-10-20.csv"),
            encoding="utf-8-sig")):
        if r.get("ra_asset_id"):
            man[r["ra_asset_id"]].append(r)
    tax = defaultdict(lambda: {"assets": set(), "rows": 0, "fields": 0,
                               "adjusted_rows": 0, "samples": [], "notes": Counter(),
                               "conf": Counter()})
    row_out = []
    total_rows = 0
    total_contract_rows = 0
    for line in open(os.path.join(CACHE, "cohort.jsonl"), encoding="utf-8"):
        j = json.loads(line)
        aid = j["ra_asset_id"]; sym = j["symbol"]; ins = j["ins_code"]
        P = {r[0]: r for r in j["candles"]}
        T = {r[0]: r for r in ref.execute(
            "SELECT date,first,high,low,close,volume,base,last FROM tsetmc WHERE ins_code=?",
            (ins,))}
        C0 = {r[0]: r for r in ref.execute(
            "SELECT date,open,high,low,close,volume FROM type0 WHERE ra_asset_id=?", (aid,))}
        C7 = {r[0]: r for r in ref.execute(
            "SELECT date,open,high,low,close,volume FROM type7 WHERE ra_asset_id=?", (aid,))}
        F = {r[0]: r[1] for r in j.get("factors") or []}
        D = {}
        if j.get("adjust_source") in FALLBACK:
            D = {r[0]: r for r in local.execute(
                "SELECT date,open,high,low,close,volume,last,src FROM price_history "
                "WHERE symbol=?", (sym,))}
        for d in sorted(set(P) & set(T)):
            t = T[d]
            if t[2] <= 0 or t[3] <= 0 or t[4] <= 0:
                continue
            total_contract_rows += 1
            c = P[d]
            c0 = C0.get(d); c7 = C7.get(d)
            dbrow = D.get(d)
            variants = []
            near_t = []
            try:
                from datetime import date as _date, timedelta as _td
                d0 = _date.fromisoformat(d)
                for delta in (-3, -2, -1, 1, 2, 3):
                    nd = (d0 + _td(days=delta)).isoformat()
                    if nd in T and T[nd][2] > 0 and T[nd][3] > 0 and T[nd][4] > 0:
                        near_t.append(T[nd])
            except ValueError:
                pass
            res = classify_row(j, c, t, c0, c7, dbrow, variants, near_t)
            if not res:
                continue
            if res[0] == "UNCLASSIFIED":
                variants = load_variant_rows(man[aid], d, ins)
                if variants:
                    res2 = classify_row(j, c, t, c0, c7, dbrow, variants, near_t)
                    if res2 and res2[0] == "INSTRUMENT_MAPPING":
                        res = res2
            cause, conf, note, bad = res
            adjusted = 0
            pf = F.get(d)
            if pf is not None and c7 is not None and c0 is not None and c0[4]:
                for f, idx in (("open_eff", 1), ("high_contract", 2),
                               ("low_contract", 3), ("close_official", 4)):
                    a = c[idx] * pf if c[idx] is not None else None
                    if a is not None and abs(a - c7[idx]) > max(0.5, 1e-6 * abs(c7[idx])):
                        adjusted = 1
                        break
            v = tax[cause]
            v["assets"].add(aid); v["rows"] += 1; v["fields"] += len(bad)
            v["conf"][conf] += 1
            v["adjusted_rows"] += adjusted
            v["notes"][note] += 1
            if len(v["samples"]) < 8:
                v["samples"].append([sym, d, ",".join(x[0] for x in bad)])
            row_out.append({"ra_asset_id": aid, "symbol": sym, "date": d,
                            "basis": j.get("basis"), "adjust_source": j.get("adjust_source"),
                            "cause": cause, "confidence": conf,
                            "fields": ",".join(x[0] for x in bad),
                            "evidence": note,
                            "ref_values": json.dumps([[x[0], x[1], x[2]] for x in bad]),
                            "type0": bool(c0 is not None), "type7": bool(c7 is not None),
                            "adjusted_still_bad": adjusted})
    if not row_out:
        print("no row mismatches")
        return
    with open(os.path.join(ART, "raw-ohlc-row-mismatches.csv"), "w", encoding="utf-8-sig",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row_out[0]))
        w.writeheader(); w.writerows(row_out)
    with open(os.path.join(ART, "raw-ohlc-mismatch-taxonomy.csv"), "w", encoding="utf-8-sig",
              newline="") as f:
        w = csv.writer(f)
        w.writerow(["cause", "confidence", "assets", "rows", "field_mismatches",
                    "share_of_row_mismatches_pct", "share_of_all_contract_rows_pct",
                    "adjusted_still_bad_rows", "top_evidence", "samples"])
        n = len(row_out) or 1
        for k in sorted(tax, key=lambda x: -tax[x]["rows"]):
            v = tax[k]
            w.writerow([k, (v["conf"].most_common(1) or [("", 0)])[0][0],
                        len(v["assets"]), v["rows"], v["fields"],
                        round(100.0 * v["rows"] / n, 4),
                        round(100.0 * v["rows"] / max(1, total_contract_rows), 6),
                        v["adjusted_rows"],
                        json.dumps(v["notes"].most_common(3), ensure_ascii=False),
                        json.dumps(v["samples"][:3], ensure_ascii=False)])
    summary = {"contract_rows": total_contract_rows, "row_mismatches": len(row_out),
               "assets_with_mismatch": len({r["ra_asset_id"] for r in row_out}),
               "causes": {k: {"assets": len(v["assets"]), "rows": v["rows"],
                              "fields": v["fields"], "adjusted_still_bad": v["adjusted_rows"]}
                          for k, v in tax.items()}}
    with open(os.path.join(ART, "raw-ohlc-taxonomy-summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
