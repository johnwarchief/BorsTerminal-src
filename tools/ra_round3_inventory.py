# -*- coding: utf-8 -*-
"""Round-3 inventory: one row per canonical asset with a product record.

Recomputes functional availability with the shipped `_functional_state` so the
denominators do not depend on which payload version happened to carry a status.
Falls back to the recorded capability only when coverage is absent.
"""
import argparse
import collections
import csv
import datetime as dt
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def is_stale(p):
    if p.get("adjustSource") not in ("local-db-fallback", "local-cache", "local-db-unseen"):
        return False
    if p.get("liveInjected"):
        return False
    try:
        last = dt.date.fromisoformat(
            max(str(c["time"])[:10] for c in (p.get("candles") or [])))
        return (dt.date.today() - last).days > 7
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "market.db"))
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--product", action="append", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary", default="")
    a = ap.parse_args()

    import bors_config
    bors_config.DB_PATH = a.db
    bors_config.PRICE_BASIS_PATH = os.path.join(
        os.path.dirname(os.path.abspath(a.out)), "price_basis_round3.json")
    try:
        os.remove(bors_config.PRICE_BASIS_PATH)
    except OSError:
        pass
    import api.chart as CH
    CH.DB_PATH = a.db

    man = {}
    for r in csv.DictReader(open(a.manifest, encoding="utf-8-sig")):
        if r.get("ra_asset_id"):
            man.setdefault(str(r["ra_asset_id"]), []).append(r)

    prod = {}
    for fn in a.product:
        if not os.path.exists(fn):
            continue
        for line in open(fn, encoding="utf-8"):
            try:
                j = json.loads(line)
            except Exception:
                continue
            if j.get("status") != "success":
                continue
            # فقط تاریخ‌ها و capability لازم است؛ OHLC کامل حافظه را می‌بلعد.
            slim = {k: v for k, v in j.items()
                    if k not in ("candles", "volumes", "factors", "adjustEvents",
                                 "adjustRejected", "corporateEvents", "fts")}
            slim["candles"] = [{"time": c.get("time")} for c in (j.get("candles") or [])]
            prod.setdefault(j["symbol"], slim)

    rows = []
    for aid, mrows in man.items():
        p = None
        for r in mrows:
            if r["symbol"] in prod:
                p = prod[r["symbol"]]
                break
        if not p:
            continue
        cap = p.get("adjustCapability") or {}
        cov = cap.get("coverage")
        times = sorted(str(c.get("time"))[:10] for c in p.get("candles") or [])
        stale = is_stale(p)
        if isinstance(cov, dict):
            chain = {"complete": cap.get("chain_complete") is True,
                     "incomplete": [{}] * int(cap.get("chain_incomplete_events") or 0)}
            kind = CH._instrument_kind(p["symbol"])
            av, blockers, status, info = CH._functional_state(
                chain, cov, kind=kind, source=p.get("adjustSource"), times=times,
                stale=stale)
        else:
            av = cap.get("functional_available") is True
            blockers = cap.get("functional_blockers") or []
            status = cap.get("functional_status") or "UNMEASURED"
            info = cap.get("availability") or {}
        src = p.get("adjustSource") or ""
        rows.append({
            "asset_id": aid,
            "symbol": p["symbol"],
            "ins_code": (mrows[0].get("ins_code") or ""),
            "class": mrows[0].get("ra_class") or "",
            "lifecycle": mrows[0].get("status") or "",
            "product_records": len(mrows),
            "basis": p.get("priceBasis") or "",
            "adjust_source": src,
            "fallback": src in ("local-db-fallback", "local-cache", "local-db-unseen"),
            "candles": len(times),
            "first_candle": times[0] if times else "",
            "last_candle": times[-1] if times else "",
            "stale": stale,
            "functional_status": status,
            "functional_available": av,
            "window_available": bool(info.get("window_available")),
            "window_start": info.get("window_start") or "",
            "blockers": " | ".join(blockers),
            "coverage_available": bool(isinstance(cov, dict) and cov.get("available")),
            "coverage_start": (cov or {}).get("coverage_start") or "",
            "coverage_end": (cov or {}).get("coverage_end") or "",
            "pre_coverage_candles": (cov or {}).get("pre_coverage_candles") or 0,
            "unresolved_events": (cov or {}).get("unresolved_events") or 0,
            "rows_unmatched": (cov or {}).get("rows_unmatched") or 0,
            "rows_total": (cov or {}).get("rows_total") or 0,
            "typed_events": (cov or {}).get("typed_events") or 0,
            "chain_complete": cap.get("chain_complete"),
            "chain_incomplete_events": cap.get("chain_incomplete_events") or 0,
        })

    rows.sort(key=lambda r: (r["class"], r["symbol"]))
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    stats = collections.Counter(r["functional_status"] for r in rows)
    by_class = collections.defaultdict(collections.Counter)
    for r in rows:
        by_class[r["class"]][r["functional_status"]] += 1
    fallback = [r for r in rows if r["fallback"]]
    summary = {
        "assets": len(rows),
        "status": dict(stats),
        "available_true": sum(1 for r in rows if r["functional_available"]),
        "window_available": sum(1 for r in rows if r["window_available"]),
        "fallback_assets": len(fallback),
        "fallback_status": dict(collections.Counter(r["functional_status"] for r in fallback)),
        "fallback_class": dict(collections.Counter(r["class"] for r in fallback)),
        "by_class": {c: dict(v) for c, v in by_class.items()},
        "source": dict(collections.Counter(r["adjust_source"] for r in rows)),
        "stale": sum(1 for r in rows if r["stale"]),
        "overlap": {
            "fallback_and_source_gap": sum(1 for r in fallback if r["functional_status"] == "SOURCE_GAP"),
            "fallback_and_unverified": sum(1 for r in fallback if r["functional_status"] == "UNVERIFIED"),
            "fallback_and_stale": sum(1 for r in fallback if r["functional_status"] == "STALE"),
            "fallback_and_available_no_events": sum(1 for r in fallback if r["functional_status"] == "AVAILABLE_NO_EVENTS"),
        },
    }
    if a.summary:
        json.dump(summary, open(a.summary, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
