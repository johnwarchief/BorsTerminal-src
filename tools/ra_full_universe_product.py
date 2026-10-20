# -*- coding: utf-8 -*-
"""Pull product chart payloads for the mapped universe, on a DB COPY.

Never touches operational market.db: --source-db is copied to --db once, and all
reads/writes of this run (including history repair triggered by the live path) stay
on that copy.

Usage examples:
  python tools/ra_full_universe_product.py --manifest _audit/universe_manifest.csv \
    --source-db market.db --db _scratch/market_copy.db --live \
    --out _audit/product_live.jsonl
  python tools/ra_full_universe_product.py ... --classes=stocks,etf_funds \
    --done-from _audit/product_live_old.jsonl
"""
import argparse, csv, json, os, shutil, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--source-db", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--live", action="store_true", help="call get_chart_tsetmc (CDN) instead of get_chart_db")
    ap.add_argument("--symbols", default="")
    ap.add_argument("--classes", default="")
    ap.add_argument("--done-from", default="")
    ap.add_argument("--no-fts", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    if not os.path.exists(a.db):
        t0 = time.time()
        shutil.copy2(a.source_db, a.db)
        print(f"copied {a.source_db} -> {a.db} ({time.time() - t0:.1f}s)")

    import bors_config
    bors_config.DB_PATH = a.db
    bors_config.PRICE_BASIS_PATH = a.db + ".price_basis.json"
    try:
        os.remove(bors_config.PRICE_BASIS_PATH)
    except OSError:
        pass
    import api.chart as CH
    for name in ("api._core", "api.chart", "api.market", "api.screener", "api.fundamental"):
        mod = sys.modules.get(name)
        if mod is not None:
            mod.DB_PATH = a.db
    if a.no_fts:
        CH._fts_analyze_candles = lambda *x, **k: None

    mapped, sym_class = [], {}
    for r in csv.DictReader(open(a.manifest, encoding="utf-8-sig")):
        if r.get("ra_asset_id") and int(r.get("product_candles") or 0) > 0:
            mapped.append(r["symbol"])
            sym_class[r["symbol"]] = r.get("ra_class") or ""
    if a.symbols:
        mapped = [s.strip() for s in a.symbols.split(",") if s.strip()]
    if a.classes:
        keep = {c.strip() for c in a.classes.split(",") if c.strip()}
        mapped = [s for s in mapped if sym_class.get(s) in keep]
    done = set()
    for path in [a.out] + [x for x in a.done_from.split(",") if x]:
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            try:
                done.add(json.loads(line)["symbol"])
            except Exception:
                pass
    seen = set()
    todo = [s for s in mapped if s not in done and not (s in seen or seen.add(s))]
    if a.limit:
        todo = todo[:a.limit]
    print(f"mapped={len(mapped)} done={len(done)} todo={len(todo)}")

    with open(a.out, "a", encoding="utf-8") as fh:
        for i, sym in enumerate(todo, 1):
            t0 = time.time()
            try:
                res = CH.get_chart_tsetmc(sym) if a.live else CH.get_chart_db(sym)
                if res.get("status") != "success":
                    rec = {"symbol": sym, "error": res.get("message") or f"status:{res.get('status')}"}
                else:
                    rec = {
                        "symbol": sym, "status": "success", "count": res.get("count"),
                        "priceBasis": res.get("priceBasis"),
                        "priceBasisRequested": res.get("priceBasisRequested"),
                        "priceBasisReason": res.get("priceBasisReason"),
                        "adjustSource": res.get("adjustSource"),
                        "dbRows": res.get("dbRows"), "dbNoTradeRows": res.get("dbNoTradeRows"),
                        "dbInvalidRows": res.get("dbInvalidRows"), "liveInjected": res.get("liveInjected"),
                        "candles": res.get("candles") or [], "volumes": res.get("volumes") or [],
                        "factors": res.get("factors") or [], "adjustEvents": res.get("adjustEvents") or [],
                        "adjustRejected": res.get("adjustRejected") or [],
                        "adjustCapability": res.get("adjustCapability") or {},
                    }
            except Exception as e:  # one symbol must not kill the run
                rec = {"symbol": sym, "error": f"{type(e).__name__}: {str(e)[:200]}"}
            fh.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
            fh.flush()
            if i % 10 == 0 or i == len(todo):
                print(f"{i}/{len(todo)} {sym} {time.time() - t0:.2f}s", flush=True)


if __name__ == "__main__":
    main()
