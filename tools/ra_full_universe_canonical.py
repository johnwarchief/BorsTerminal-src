# -*- coding: utf-8 -*-
"""Canonical instrument/lifecycle table for the whole 5,981-instrument universe.

Usage:
  python tools/ra_full_universe_canonical.py \
    --db _audit/market_snapshot.db \
    --manifest _audit/RAHAVARD-FULL-UNIVERSE-MANIFEST-2026-10-20.csv \
    --out _audit/RAHAVARD-FULL-UNIVERSE-CANONICAL-2026-10-20.csv

No mapping is forced here: exact/variant/ambiguous/unmapped status is preserved and
each row carries its evidence. Rename groups are recorded for lifecycle auditing.
"""
import argparse, collections, csv, os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bors_config
import api.chart as CH  # pure name helpers only


def norm(s):
    return re.sub(r"\s+", "", (s or "").replace("\u200c", "").replace("ي", "ی").replace("ك", "ک"))


REF_CLASS = {"stocks": "stock", "etf_funds": "fund", "bonds": "bond",
             "options": "option", "futures": "future", "warrants": "right"}


def classify(name, paper_type, sector, ra_class=""):
    if ra_class in REF_CLASS:
        return REF_CLASS[ra_class]
    name = (name or "").replace("\u200c", " ")
    if CH._is_option_name(name):
        return "option"
    if CH._is_bond_name(name):
        return "bond"
    if CH._is_right_name(name, paper_type):
        return "right"
    if CH._is_future_name(name):
        return "future"
    if paper_type == 8 or "صندوق" in (sector or "") or "صندوق" in name:
        return "fund"
    return "stock"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    inst = {}
    for r in con.execute("SELECT ins_code, l_val18, l_val30, paper_type, sector_name, isin, updated_at FROM instruments"):
        inst[str(r[0])] = r
    spans = {}
    for r in con.execute("SELECT symbol, MIN(date), MAX(date), COUNT(*) FROM price_history GROUP BY symbol"):
        spans[r[0]] = (r[1], r[2], r[3])

    rows = []
    for m in csv.DictReader(open(a.manifest, encoding="utf-8-sig")):
        ins = str(m.get("ins_code") or "")
        db = inst.get(ins)
        sym = m.get("symbol") or ""
        name = (db[2] if db else m.get("name")) or ""
        pt = db[3] if db else m.get("paper_type")
        sector = (db[4] if db else m.get("sector_name")) or ""
        isin = (db[5] if db else "") or ""
        first, last, cnt = spans.get(sym, ("", "", 0))
        cls = classify(name, pt, sector, m.get("ra_class") or "")
        method = m.get("identity_method") or "NO_EXACT_IDENTITY"
        if method.startswith("rahavard-bulk-exact"):
            identity = "MAPPED_EXACT"
        elif method.startswith("rahavard-bulk-variant-of:"):
            identity = "MAPPED_VARIANT"
        elif method.startswith("IDENTITY_AMBIGUOUS"):
            identity = "IDENTITY_AMBIGUOUS"
        elif m.get("ra_asset_id"):
            identity = "MAPPED_OTHER"
        elif not cnt:
            identity = "NO_PRODUCT_DATA"
        else:
            identity = "UNMAPPED_NO_REFERENCE"
        base = method.split("rahavard-bulk-variant-of:", 1)[1] if identity == "MAPPED_VARIANT" else ""
        rows.append({
            "ins_code": ins, "symbol": sym, "name": name, "instrument_class": cls,
            "paper_type": pt, "sector_name": sector, "board": m.get("board"),
            "isin": isin, "first_price_date": first, "last_price_date": last,
            "price_rows": cnt, "lifecycle": m.get("status"),
            "ra_asset_id": m.get("ra_asset_id") or "", "ra_class": m.get("ra_class") or "",
            "identity_status": identity, "identity_method": method,
            "rename_base": base, "exclusion_reason": m.get("exclusion_reason") or "",
            "updated_at": (db[6] if db else ""),
        })
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"wrote {a.out}: {len(rows)} rows")
    print("identity:", dict(collections.Counter(r["identity_status"] for r in rows)))
    print("class:", dict(collections.Counter(r["instrument_class"] for r in rows)))
    print("class x identity:")
    c = collections.Counter((r["instrument_class"], r["identity_status"]) for r in rows)
    for k, v in sorted(c.items(), key=lambda x: (x[0][0], x[0][1])):
        print(" ", k, v)
    print("unmapped active by class:",
          dict(collections.Counter(r["instrument_class"] for r in rows
                                   if r["lifecycle"] == "active"
                                   and r["identity_status"] == "UNMAPPED_NO_REFERENCE")))
    con.close()


if __name__ == "__main__":
    main()
