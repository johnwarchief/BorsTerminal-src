# -*- coding: utf-8 -*-
"""Build the full-universe manifest: one row per instrument, exact identity only.

Inputs:
  --db      operational market.db (opened read-only; never written)
  --bulk    RAHAVARD-BULK-ASSETS-*.csv (class, asset_id, name, exchange_id, slug)
  --out     output manifest CSV

Identity rules (mission 2026-10-20):
  * exact trade_symbol equality with the Rahavard bulk lists;
  * on duplicate names, the class consistent with paper_type wins, else IDENTITY_AMBIGUOUS;
  * historical symbol variants (suffix 2..9) map to the base asset ONLY with identical
    normalized company name and non-overlapping series continuity;
  * every instrument stays in the manifest, with an explicit exclusion reason.
"""
import argparse, collections, csv, re, sqlite3, sys


def norm(s):
    return re.sub(r"\s+", "", (s or "").replace("\u200c", "").replace("ي", "ی").replace("ك", "ک"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--bulk", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    name_map = collections.defaultdict(list)
    for r in csv.DictReader(open(a.bulk, encoding="utf-8-sig")):
        if r.get("class") == "funds" or not r.get("name"):
            continue
        name_map[r["name"]].append({"class": r["class"], "asset_id": str(r["asset_id"]),
                                    "exchange_id": r.get("exchange_id")})
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    con.row_factory = sqlite3.Row
    inst = con.execute("""
        SELECT i.ins_code, i.l_val18 AS symbol, i.l_val30 AS name, i.paper_type,
               i.sector_code, i.sector_name, i.updated_at, b.board,
               (SELECT MAX(d_even) FROM market_watch w WHERE w.ins_code=i.ins_code) AS watch_last,
               (SELECT MAX(date) FROM price_history p WHERE p.symbol=i.l_val18) AS hist_last,
               (SELECT COUNT(*) FROM price_history p WHERE p.symbol=i.l_val18) AS hist_count,
               (SELECT COUNT(*) FROM price_adjust_events x WHERE x.ins_code=i.ins_code) AS adjust_rows,
               (SELECT COUNT(*) FROM share_change_events s WHERE s.ins_code=i.ins_code) AS share_rows
        FROM instruments i LEFT JOIN boards b ON b.ins_code=i.ins_code
        ORDER BY i.l_val18
    """).fetchall()
    by_sym = {r["symbol"]: r for r in inst}
    variant_map = {}
    for r in inst:
        m = re.match(r"^(.*?)([2-9])$", r["symbol"])
        if not m:
            continue
        base = by_sym.get(m.group(1))
        if not base or not name_map.get(base["symbol"]):
            continue
        if norm(base["name"]) != norm(r["name"]):
            continue
        if not (r["hist_last"] and base["hist_last"] and r["hist_last"] < base["hist_last"]):
            continue
        variant_map[r["symbol"]] = base["symbol"]

    rows = []
    for r in inst:
        hits = name_map.get(r["symbol"])
        hit, method = None, None
        if hits:
            if len(hits) == 1:
                hit, method = hits[0], "rahavard-bulk-exact-trade-symbol"
            else:
                pref = {1: "stocks", 8: "etf_funds", 2: "bonds", 4: "warrants"}.get(r["paper_type"])
                cand = [h for h in hits if h["class"] == pref]
                if len(cand) == 1:
                    hit, method = cand[0], "rahavard-bulk-exact-trade-symbol+class"
                else:
                    method = "IDENTITY_AMBIGUOUS:" + ",".join(sorted(h["asset_id"] for h in hits))
        elif r["symbol"] in variant_map:
            base = variant_map[r["symbol"]]
            hit = name_map[base][0]
            method = f"rahavard-bulk-variant-of:{base}"
        status = ("active" if int(r["watch_last"] or 0) >= 20261001
                  else ("historical" if r["hist_count"] else "no-product-data"))
        rows.append({
            "ins_code": r["ins_code"], "symbol": r["symbol"], "name": r["name"],
            "paper_type": r["paper_type"], "board": r["board"],
            "sector_code": r["sector_code"], "sector_name": r["sector_name"],
            "status": status, "last_price_date": r["hist_last"], "watch_last": r["watch_last"],
            "product_candles": r["hist_count"], "adjust_rows": r["adjust_rows"],
            "share_rows": r["share_rows"],
            "ra_asset_id": hit["asset_id"] if hit else "",
            "ra_class": hit["class"] if hit else "",
            "identity_method": method or "NO_EXACT_IDENTITY",
            "exclusion_reason": "" if hit else ("NO_REFERENCE_DATA" if not hits else "IDENTITY_AMBIGUOUS"),
        })
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {a.out}: {len(rows)} rows; mapped={sum(1 for r in rows if r['ra_asset_id'])}")
    con.close()


if __name__ == "__main__":
    main()
