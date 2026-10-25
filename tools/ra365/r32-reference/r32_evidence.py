#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adapters that turn the tracked R26–R31 evidence into R32 records.

The corpus that Rounds 26–31 measured against lived under D:/BorsTerminal-tmp
and is gone from this machine, so the round cannot replay it.  What survived in
git is a set of frozen CSV ledgers.  These adapters read those ledgers and emit
records that satisfy the R32 contract, tagging every field they could not know
as unavailable instead of guessing it.

Sources understood
------------------
candle-diverge   _audit/RA365-CANDLE-DIVERGE-2026-10-12.csv
                 product raw OHLC beside reference adjusted OHLC, session by
                 session -> the pair the factor inference needs.
parity-diverge   _audit/RA365-PARITY-DIVERGE-2026-10-12.csv
                 four named arms, each carrying its own source + price basis +
                 adjust mode -> like-for-like pairs for the mismatch ledger.
steps            artifacts/ra365/r30/attribution/steps.csv
                 frozen factor-chain boundaries for 827 assets with the event
                 signature that sat between them.

None of these adapters writes to a database and none of them fetches anything.
"""
from __future__ import annotations

import csv
import os

import r32_schema as S

# Arm vocabulary, as it is written in the frozen ledger:
#   <transport> - <price basis> - <adjust mode>
_LIVE = "\u0632\u0646\u062f\u0647"          # zendeh  - live feed
_DB = "\u062f\u06cc\u062a\u0627\u0628\u06cc\u0633"  # database - stored history
_LAST = "\u0622\u062e\u0631\u06cc\u0646"    # akharin - last trade
_CLOSING = "\u067e\u0627\u06cc\u0627\u0646\u06cc"  # payani  - official closing
_RAW = "\u062e\u0627\u0645"                 # kham    - raw
_ADJUSTED = "\u0639\u0645\u0644\u06a9\u0631\u062f\u06cc"  # amalkardi - adjusted

ARM_TOKENS = {
    "transport": {_LIVE: "live", _DB: "db"},
    "basis": {_LAST: "last", _CLOSING: "closing"},
    "adjust": {_RAW: "raw", _ADJUSTED: "adjusted"},
}

CANDLE_COLUMNS = ("date", "our_c", "our_h", "our_l", "our_last", "our_o", "our_src",
                  "our_v", "ref_c", "ref_c_equals_our_last", "ref_h", "ref_l", "ref_o",
                  "ref_v", "symbol")
PARITY_COLUMNS = ("arm", "date", "prod_c", "prod_closing_raw", "prod_h", "prod_l",
                  "prod_last_raw", "prod_o", "ref_c", "ref_h", "ref_l", "ref_o",
                  "rel_err", "symbol")


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def arm_context(arm):
    """Split an arm label into (transport, price_basis, adjust)."""
    text = str(arm or "")
    out = {}
    for field, vocab in ARM_TOKENS.items():
        hit = None
        for token, value in vocab.items():
            if token in text:
                hit = value
                break
        out[field] = hit
    return out


def derive_timeframe(dates):
    """Infer D/W/M from the median spacing of sorted ISO dates."""
    ds = sorted({str(d)[:10] for d in dates if d})
    if len(ds) < 3:
        return "D", "assumed"
    import datetime as _dt
    parsed = [_dt.date.fromisoformat(d) for d in ds]
    gaps = sorted((b - a).days for a, b in zip(parsed, parsed[1:]))
    med = gaps[len(gaps) // 2]
    if med <= 2:
        return "D", "derived"
    if med <= 9:
        return "W", "derived"
    if med <= 20:
        return "W", "derived"
    return "M", "derived"


def _num(row, key):
    return S.normalize_number(row.get(key))


def bars_from_candle_diverge(path, url=None):
    """Product raw OHLC and reference adjusted OHLC, one pair per session."""
    rows = read_csv(path)
    if not rows:
        return [], []
    name = os.path.basename(path)
    src_prod = {
        "source_id": "product-raw@%s" % name,
        "kind": "product-frozen-ledger",
        "endpoint": url,
        "captured_at": None,
        "input_sha256": S.sha256_file(path),
        "adjust_scope": "raw",
        "price_basis": "unknown",
        "id_kind": "symbol-name",
        "license": "first-party product data",
        "note": "the frozen ledger does not name the product price basis; "
                "the raw close column is `our_c`",
    }
    src_ref = {
        "source_id": "rahavard-adjusted@%s" % name,
        "kind": "rahavard365-frozen-ledger",
        "endpoint": url,
        "captured_at": None,
        "input_sha256": S.sha256_file(path),
        "adjust_scope": "adjusted",
        "price_basis": "real_close",
        "id_kind": "symbol-name",
        "license": "owner subscription; not redistributable",
    }
    by_symbol = {}
    for row in rows:
        by_symbol.setdefault(S.normalize_symbol(row.get("symbol")), []).append(row)
    bars_prod, bars_ref = [], []
    for sym, sx in sorted(by_symbol.items()):
        tf, _ = derive_timeframe([r.get("date") for r in sx])
        for row in sorted(sx, key=lambda r: r.get("date") or ""):
            date = S.normalize_date(row.get("date"))
            for src, adjust, basis, cols in (
                (src_prod, "raw", "unknown", ("our_o", "our_h", "our_l", "our_c", "our_v")),
                (src_ref, "adjusted", "real_close", ("ref_o", "ref_h", "ref_l", "ref_c", "ref_v")),
            ):
                rec = {
                    "schema": S.SCHEMA_BAR,
                    "symbol_id": sym,
                    "symbol": sym,
                    "ins_code": None,
                    "timeframe": tf,
                    "date": date,
                    "adjust": adjust,
                    "basis": basis,
                    "source_id": src["source_id"],
                    "retrieved_at": src["captured_at"],
                    "precision": None,
                    "revision": None,
                    "unavailable": ["ins_code", "retrieved_at"],
                    "open": _num(row, cols[0]),
                    "high": _num(row, cols[1]),
                    "low": _num(row, cols[2]),
                    "close": _num(row, cols[3]),
                    "volume": _num(row, cols[4]),
                }
                rec["unavailable"] = sorted({f for f in ("open", "high", "low", "close", "volume")
                                             if rec[f] is None} | {"ins_code", "retrieved_at"})
                rec["row_hash"] = S.row_hash(rec)
                (bars_prod if adjust == "raw" else bars_ref).append(rec)
    return [src_prod, src_ref], bars_prod + bars_ref


def pairs_from_candle_diverge(path):
    """(product_raw, reference_adjusted) per session, for the factor inference."""
    rows = read_csv(path)
    by_symbol = {}
    for row in rows:
        by_symbol.setdefault(S.normalize_symbol(row.get("symbol")), []).append(row)
    out = []
    for sym, sx in sorted(by_symbol.items()):
        tf, tf_src = derive_timeframe([r.get("date") for r in sx])
        for row in sx:
            out.append({
                "symbol_id": sym, "symbol": sym, "timeframe": tf,
                "timeframe_source": tf_src,
                "date": S.normalize_date(row.get("date")),
                "basis": "unknown",
                "prod": {"o": _num(row, "our_o"), "h": _num(row, "our_h"),
                         "l": _num(row, "our_l"), "c": _num(row, "our_c"),
                         "v": _num(row, "our_v")},
                "ref": {"o": _num(row, "ref_o"), "h": _num(row, "ref_h"),
                        "l": _num(row, "ref_l"), "c": _num(row, "ref_c"),
                        "v": _num(row, "ref_v")},
                "ref_closing": _num(row, "ref_c"),
                "raw_closing": _num(row, "our_c"),
                "raw_last": _num(row, "our_last"),
                "event": None,
                "source_ref": "rahavard-adjusted@%s" % os.path.basename(path),
                "source_prod": "product-raw@%s" % os.path.basename(path),
            })
    return out


def pairs_from_parity_diverge(path, url=None):
    """Like-for-like pairs, one per (arm, symbol, date), each with its own basis."""
    rows = read_csv(path)
    out = []
    by_arm_symbol = {}
    for row in rows:
        ctx = arm_context(row.get("arm"))
        key = (row.get("arm"), S.normalize_symbol(row.get("symbol")))
        by_arm_symbol.setdefault(key, []).append((ctx, row))
    for (arm, sym), items in sorted(by_arm_symbol.items()):
        ctx = items[0][0]
        tf, tf_src = derive_timeframe([r.get("date") for _, r in items])
        for ctx2, row in items:
            out.append({
                "symbol_id": sym, "symbol": sym, "timeframe": tf,
                "timeframe_source": tf_src,
                "date": S.normalize_date(row.get("date")),
                "arm": arm,
                "transport": ctx2.get("transport"),
                "adjust": ctx2.get("adjust") or "unknown",
                "basis": ctx2.get("basis") or "unknown",
                "prod": {"o": _num(row, "prod_o"), "h": _num(row, "prod_h"),
                         "l": _num(row, "prod_l"), "c": _num(row, "prod_c"),
                         "v": None},
                "prod_raw": {"c": _num(row, "prod_closing_raw"),
                             "last": _num(row, "prod_last_raw")},
                "ref": {"o": _num(row, "ref_o"), "h": _num(row, "ref_h"),
                        "l": _num(row, "ref_l"), "c": _num(row, "ref_c"), "v": None},
                "proven_rel_err": _num(row, "rel_err"),
                "event": None,
                "source_ref": "rahavard-frozen-ledger@%s" % os.path.basename(path),
                "source_prod": "product-frozen-ledger@%s" % os.path.basename(path),
            })
    return out


def pairs_from_rahavard_capture(path):
    """type0 (raw) beside type7 (adjusted) from one capture, session by session.

    Both sides come from the same source and the same snapshot, so the ratio
    they produce is the reference's own factor chain with no cross-source noise:
    it is the cleanest evidence the round can get for `infer_factor_segments`.
    """
    import json as _json
    with open(path, encoding="utf-8-sig") as fh:
        doc = _json.load(fh)
    src = doc.get("source") or {}
    sid = "rahavard365-capture@%s" % (src.get("captured_at") or os.path.basename(path))
    groups = {}
    for series in doc.get("series") or []:
        key = (str(series.get("asset_id")), series.get("resolution") or series.get("timeframe"))
        groups.setdefault(key, {})[series.get("adjust")] = series
    out = []
    for (asset_id, resolution), sides in sorted(groups.items()):
        raw, adjusted = sides.get("raw"), sides.get("adjusted")
        if not raw or not adjusted:
            continue
        symbol = S.normalize_symbol(raw.get("symbol") or adjusted.get("symbol"))
        basis = raw.get("basis") or adjusted.get("basis") or "real_close"
        rmap = {str(b.get("utc"))[:10]: b for b in raw.get("bars") or [] if b.get("utc")}
        amap = {str(b.get("utc"))[:10]: b for b in adjusted.get("bars") or [] if b.get("utc")}
        for date in sorted(set(rmap) & set(amap)):
            r, a = rmap[date], amap[date]
            out.append({
                "symbol_id": asset_id, "symbol": symbol,
                "timeframe": S.normalize_timeframe(resolution),
                "timeframe_source": "declared",
                "date": date, "basis": basis, "adjust": "adjusted",
                "prod": {"o": S.normalize_number(r.get("open")),
                         "h": S.normalize_number(r.get("high")),
                         "l": S.normalize_number(r.get("low")),
                         "c": S.normalize_number(r.get("close")),
                         "v": S.normalize_number(r.get("volume"))},
                "prod_raw": {"c": S.normalize_number(r.get("close"))},
                "ref": {"o": S.normalize_number(a.get("open")),
                        "h": S.normalize_number(a.get("high")),
                        "l": S.normalize_number(a.get("low")),
                        "c": S.normalize_number(a.get("close")),
                        "v": S.normalize_number(a.get("volume"))},
                "event": (adjusted.get("marks") or {}).get("data") if isinstance(
                    adjusted.get("marks"), dict) else None,
                "source_ref": sid + "#type7",
                "source_prod": sid + "#type0",
            })
    return out


def segments_from_steps(path):
    """Frozen factor-chain boundaries -> step-boundary segments.

    What the ledger proves: at `date` the ratio between the two chains moved,
    by exactly `ref_ratio` on the reference side and `prod_ratio` on ours, with
    this event signature sitting between the boundaries.  What it does NOT
    prove: how many sessions the interval contains.  That lands in
    `unavailable`, never in a fabricated 0.
    """
    rows = read_csv(path)
    out = []
    per_asset = {}
    for row in rows:
        per_asset.setdefault(str(row.get("asset_id")), []).append(row)
    for asset_id, sx in sorted(per_asset.items()):
        sx.sort(key=lambda r: r.get("date") or "")
        for idx, row in enumerate(sx):
            ref_ratio = _num(row, "ref_ratio")
            prod_ratio = _num(row, "prod_ratio")
            factor = None
            if ref_ratio and prod_ratio:
                factor = prod_ratio / ref_ratio
            sources = (row.get("event_sources") or "").split(";")
            sources = [s for s in sources if s]
            sig = row.get("event_sig") or ""
            attributed = "unattributed"
            if sources and sig not in ("", "no_event"):
                attributed = "inferential"
            rec = {
                "schema": S.SCHEMA_SEGMENT,
                "symbol_id": asset_id,
                "symbol": S.normalize_symbol(row.get("symbol")),
                "timeframe": "D",
                "timeframe_source": "assumed",
                "segment_index": idx,
                "date_from": S.normalize_date(row.get("date")),
                "date_to": S.normalize_date(row.get("date")),
                "factor": factor,
                "factor_inverse": (1.0 / factor) if factor else None,
                "field_factors": None,
                "max_rel_residual": abs(_num(row, "err")) if _num(row, "err") is not None else None,
                "median_rel_residual": abs(_num(row, "err")) if _num(row, "err") is not None else None,
                "evidence": {
                    "evidence_kind": "step-boundary",
                    "n_sessions": None,
                    "n_boundaries": 1,
                    "n_field_samples": 0,
                    "n_distinct_ratios": 1,
                    "affected_rows": S.normalize_number(row.get("affected_rows")),
                    "attributed_rows": S.normalize_number(row.get("attributed_rows")),
                },
                "breakpoint": {
                    "date": S.normalize_date(row.get("date")),
                    "prev_factor": None,
                    "delta_rel": (abs(_num(row, "err")) if _num(row, "err") is not None else None),
                },
                "event_attribution": attributed,
                "event_evidence": [{"source": s, "kind": sig} for s in sources],
                "class_r31": row.get("class"),
                "err_bucket_r31": row.get("err_bucket"),
                "event_sig_r31": sig,
                "confidence": 0.5 if factor else 0.0,
                "confidence_basis": "one frozen boundary observation; the sessions inside the "
                                    "interval were not preserved, so the factor is a point "
                                    "witness, not a segment average",
                "source_ref": "rahavard-frozen-step-evidence@%s" % os.path.basename(path),
                "source_prod": "product-frozen-step-evidence@%s" % os.path.basename(path),
                "unavailable": ["sessions_in_segment", "field_factors"],
            }
            out.append(rec)
    return out