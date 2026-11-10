#!/usr/bin/env python3
"""Stage 07 - reconcile the history, instruments and pack inventory counts.

B9 asks one question: do the counts that travel through the Phase 4.9 reports
describe the same population? They do not, and this stage names every bucket
instead of forcing a zero-difference story.

Measured on the Seed DB (``_audit/phase49-finalization/seed/market.db``) with
the rebuild pack ``data/ra365_corrections/ra365-phase49-rebuild-full-v2``.

History and instruments
    6,103 ``price_history`` symbols (511,139 rows), 6,103 identity keys.
    ``instruments`` has 5,944 rows but only 5,941 distinct names / keys:
    آواپارس, کیمازی and حیان072 appear twice. 4,635 keys are shared (4,637
    rows); 1,468 history symbols have no instruments row (B7's
    ``unresolved_no_instruments``); 1,306 named instruments have no history
    (1,307 rows) and none of them carries adjustment evidence, because the pack
    and ``adjust_events`` are both subsets of the history keys. The two
    universes together hold 7,409 keys. No spelling variant hides the gap: for
    every shared key the instruments spelling equals the history spelling.

Pack
    ``factors.jsonl`` has 8,280 ``replace_step`` rows under 951 raw symbols but
    only 915 normalised keys; the 36 extra spellings are Persian/Arabic
    variants of the same companies. All 915 keys are in the history universe
    and no pack symbol lacks history. 6,103 - 915 = 5,188 history symbols have
    no pack step - exactly the ``history_validity`` ``unverified`` population
    (5,188 rows, 0 of them with a pack step; all 915 pack symbols are
    verified or reconstructed).

Product events
    ``adjust_events`` carries 12,829 rows under 1,087 raw symbols (1,051
    keys). 37 raw spellings do not match a history spelling, but every key
    resolves inside the history universe. 890 pack keys already have product
    events; 161 symbols have product events and no pack step.

The 6,328 "no adjustment evidence" figure
    ``_audit/phase49-finalization/evidence/db-inventory.json``
    ``flags.no_adjustment_evidence`` = 6,328 (``DB-INVENTORY.md`` line 38,
    quoted by ``docs/opportunity-center/phase49/FINALIZATION-REPORT.md``). It
    was produced by ``_audit/phase49-finalization/stageB_inventory.py`` on
    ``_audit/phase49-finalization/db/restored-work.db`` with the *r32b* pack
    (827 symbols). Its universe is the union
    ``history | instruments | pack | adjust_events`` (7,446 raw symbols) and
    the flag means "no ``adjust_events`` row and no pack step". It is not a
    history-symbol count (6,103) and not a pack-step count: history without a
    pack step is 5,188 raw spellings and 5,188 keys, because history spells
    every key exactly once and the pack's 36 alias spellings are not history
    spellings.

    Reproduced here exactly: 6,328 = 5,022 history symbols without evidence
    + 1,306 instruments without history, using that r32b pack. With the
    current pack the same definition gives 6,333 = 5,027 + 1,306: the rebuild
    adds 96 keys (all already had product events) and drops 8 keys (5 of them
    had no product event), hence +5. The history-only current figures are
    5,027 (no product event, no pack step) and 5,188 (no pack step).

The 827/828 asset map is a third population and is not the pack: the r32b
correction pack has 827 symbols, the live pack ``ra365-live40-v1`` has 828
asset-map entries, and B2's capture union is 1,097 keys (758 mapped).

Outputs
    ``evidence/inventory-reconcile.json`` (small, tracked) and the raw
    ``ledgers/INVENTORY-RECONCILIATION.csv`` (gitignored, one row per union
    key). The stage manifest records the input/output SHA-256s.

The Seed DB is opened read-only; stdlib only; no network call; LF output.

CLI:
    python _audit/phase49-full-verification/stage07_inventory_reconcile.py \\
        --db _audit/phase49-finalization/seed/market.db \\
        --pack data/ra365_corrections/ra365-phase49-rebuild-full-v2 \\
        --legacy-pack data/ra365_corrections/ra365-r32b-v2 \\
        --out _audit/phase49-full-verification/evidence/inventory-reconcile.json
"""
import argparse
import collections
import csv
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.append(ROOT)
_DEV = os.path.join(ROOT, "dev")
while _DEV in sys.path:
    sys.path.remove(_DEV)
sys.path.insert(0, _DEV)  # dev/symbol_identity wins over any root shim

from symbol_identity import key  # noqa: E402
import phase49_manifest as PM  # noqa: E402

DEFAULT_LEGACY_PACK = os.path.join(ROOT, "data", "ra365_corrections",
                                   "ra365-r32b-v2")
DEFAULT_REPORT = os.path.join(ROOT, "_audit", "phase49-finalization",
                              "evidence", "db-inventory.json")
DEFAULT_CSV = os.path.join(HERE, "ledgers", "INVENTORY-RECONCILIATION.csv")
DEFAULT_MANIFEST = os.path.join(HERE, "evidence",
                                "stage07_inventory_reconcile.manifest.json")
REPORT_NO_EVIDENCE = 6328
NO_EVIDENCE_DEFINITION = (
    "a symbol with no adjust_events row and no pack step, counted over the "
    "union of price_history symbols, instruments names, pack symbols and "
    "adjust_events symbols")

FIELDS = ["key", "bucket", "history", "history_raw", "instruments",
          "instrument_names", "ins_codes", "in_pack", "pack_raw",
          "in_product_events", "product_event_rows", "evidence",
          "validity_status"]


def _rel(path):
    """Repo-relative POSIX path for tracked evidence; absolute outside."""
    if not path:
        return ""
    try:
        rel = os.path.relpath(os.path.abspath(path), ROOT)
    except ValueError:  # different drive on Windows
        rel = os.path.abspath(path)
    return rel.replace("\\", "/")


def _connect(db):
    return sqlite3.connect("file:%s?mode=ro" % os.path.abspath(db).replace(
        "\\", "/"), uri=True)


def _load_pack(path):
    """(raw symbol set, Counter of actions) from ``factors.jsonl``."""
    raw, actions = set(), collections.Counter()
    with open(os.path.join(path, "factors.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            actions[str(rec.get("action") or "step")] += 1
            symbol = rec.get("symbol")
            if symbol is not None and str(symbol).strip():
                raw.add(str(symbol))
    return raw, actions


def _product_rows(con):
    """``adjust_events`` symbol -> rows; ``None`` when the table is absent."""
    try:
        rows = con.execute(
            "SELECT symbol,COUNT(*) FROM adjust_events GROUP BY symbol"
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    return {str(symbol): int(count) for symbol, count in rows
            if symbol is not None and str(symbol).strip()}


def _validity_rows(con):
    """``history_validity`` summary; ``None`` when the table is absent."""
    try:
        rows = con.execute(
            "SELECT symbol,status,COALESCE(factor_steps,0) "
            "FROM history_validity").fetchall()
    except sqlite3.OperationalError:
        return None
    by_status = collections.Counter()
    status_by_key = {}
    unverified, unverified_with_steps = set(), 0
    for symbol, status, steps in rows:
        status = str(status or "")
        by_status[status] += 1
        if symbol is None or not str(symbol).strip():
            continue
        status_by_key[key(symbol)] = status
        if status == "unverified":
            unverified.add(key(symbol))
            if int(steps or 0):
                unverified_with_steps += 1
    return {"rows": len(rows),
            "by_status": dict(sorted(by_status.items())),
            "status_by_key": status_by_key,
            "unverified_keys": unverified,
            "unverified_with_steps": unverified_with_steps}


def _weights(product_symbols):
    """Normalise product events to ``{raw symbol: row count}``."""
    if product_symbols is None:
        return None
    if isinstance(product_symbols, dict):
        return {str(s): int(n) for s, n in product_symbols.items()
                if s is not None and str(s).strip()}
    return {str(s): 1 for s in product_symbols
            if s is not None and str(s).strip()}


def _split(part, total):
    """Share-of-total string used by the notes."""
    return "%.1f%% of %d" % (100.0 * part / total if total else 0.0, total)


def reconcile(con, pack_symbols=None, pack_steps=0, legacy_pack_symbols=None,
              legacy_pack_steps=0, product_symbols=None,
              report_value=REPORT_NO_EVIDENCE):
    """Compare the four symbol universes and return the reconciliation.

    Only ``price_history`` and ``instruments`` are required; the pack sets are
    passed in and ``adjust_events`` / ``history_validity`` are read when the
    tables exist, so the same function runs on the Seed and on a bare test DB.
    """
    hist_raw = [str(r[0]) for r in con.execute(
        "SELECT symbol FROM price_history GROUP BY symbol ORDER BY symbol")
        if r[0] is not None and str(r[0]).strip()]
    hist_by_key = collections.defaultdict(list)
    for symbol in hist_raw:
        hist_by_key[key(symbol)].append(symbol)
    hist_keys = set(hist_by_key)
    null_symbols = con.execute(
        "SELECT COUNT(*) FROM price_history WHERE symbol IS NULL "
        "OR TRIM(symbol)=''").fetchone()[0]

    inst_rows = con.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
    inst_rows_list = [(str(code), str(name)) for code, name in con.execute(
        "SELECT ins_code,l_val18 FROM instruments "
        "WHERE l_val18 IS NOT NULL AND TRIM(l_val18)<>'' "
        "ORDER BY ins_code")]
    inst_names = collections.defaultdict(list)
    inst_codes = collections.defaultdict(list)
    for ins_code, name in inst_rows_list:
        inst_names[key(name)].append(name)
        inst_codes[key(name)].append(ins_code)
    inst_keys = set(inst_names)
    rows_with_history = sum(len(v) for k, v in inst_names.items()
                            if k in hist_keys)
    exact_duplicates = con.execute(
        "SELECT COUNT(*) FROM (SELECT l_val18 FROM instruments "
        "WHERE TRIM(COALESCE(l_val18,''))<>'' GROUP BY l_val18 "
        "HAVING COUNT(*)>1)").fetchone()[0]

    rep = {
        "history_symbols": len(hist_raw),
        "instruments": inst_rows,
        "instruments_named": len(inst_keys),
        "history_outside_instruments": len(hist_keys - inst_keys),
        "instruments_without_history": len(inst_keys - hist_keys),
        "duplicate_instrument_names": exact_duplicates,
        "history_keys": len(hist_keys),
        "history_price_rows": con.execute(
            "SELECT COUNT(*) FROM price_history").fetchone()[0],
        "history_null_or_empty_symbols": int(null_symbols),
        "instruments_rows_named": len(inst_rows_list),
        "instruments_duplicate_name_rows": len(inst_rows_list) - len(
            {n for names in inst_names.values() for n in names}),
        "instruments_rows_with_history": rows_with_history,
        "instruments_rows_without_history": len(inst_rows_list)
        - rows_with_history,
        "instruments_with_history": len(inst_keys & hist_keys),
        "shared_keys_with_different_spelling": sum(
            1 for k in inst_keys & hist_keys
            if set(inst_names[k]) != set(hist_by_key[k])),
        "union_symbols": len(hist_keys | inst_keys),
        "duplicate_instrument_keys": [
            {"key": k,
             "rows": len(inst_names[k]),
             "candidates": len(inst_codes[k]),
             "ins_codes": sorted(inst_codes[k]),
             "in_history": k in hist_keys}
            for k in sorted(inst_names) if len(inst_names[k]) > 1],
    }

    product = _weights(product_symbols)
    if product is None:
        product = _product_rows(con)
    product_keys = None
    if product is not None:
        product_keys = {key(s) for s in product}
        rep["product_events"] = {
            "table": "adjust_events",
            "rows": sum(product.values()),
            "raw_symbols": len(product),
            "symbols": len(product_keys),
            "history_symbols_with_events": len(hist_keys & product_keys),
            "symbols_outside_history": len(product_keys - hist_keys),
            "raw_symbols_outside_history": sum(
                1 for s in product if s not in set(hist_raw)),
        }

    pack_keys, pack_raw = None, set()
    if pack_symbols is not None:
        pack_raw = {str(s) for s in pack_symbols
                    if s is not None and str(s).strip()}
        pack_keys = {key(s) for s in pack_raw}
        rep["pack_symbols"] = len(pack_keys)
        rep["pack_raw_symbols"] = len(pack_raw)
        rep["pack_steps"] = int(pack_steps)
        rep["pack_alias_spellings"] = len(pack_raw) - len(pack_keys)
        rep["history_symbols_with_pack_steps"] = len(hist_keys & pack_keys)
        rep["history_symbols_without_pack_steps"] = len(hist_keys - pack_keys)
        rep["pack_symbols_without_history"] = len(pack_keys - hist_keys)

    if pack_keys is not None and product_keys is not None:
        evidence = pack_keys | product_keys
        history_without = hist_keys - evidence
        instrument_only = inst_keys - hist_keys
        rep["no_adjustment_evidence"] = {
            "definition": NO_EVIDENCE_DEFINITION,
            "pack": "current",
            "history_symbols_with_evidence": len(hist_keys & evidence),
            "history_symbols_without_evidence": len(history_without),
            "instruments_without_history": len(instrument_only),
            "union_symbols_without_evidence": len(
                (hist_keys | inst_keys) - evidence),
            "history_plus_instruments_identity": (
                len(history_without) + len(instrument_only - evidence)),
        }
        hist_spellings = set(hist_raw)
        inst_raw = {name for _, name in inst_rows_list}
        raw_union = hist_spellings | inst_raw | set(product) | pack_raw
        no_history = raw_union - hist_spellings
        instrument_only_raw = {s for s in no_history if s in inst_raw}
        aliases = {s for s in no_history - instrument_only_raw
                   if key(s) in hist_keys}
        other = no_history - instrument_only_raw - aliases
        rep["raw_universe"] = {
            "symbols": len(raw_union),
            "keys": len({key(s) for s in raw_union}),
            "no_price_history": len(no_history),
            "no_price_history_instrument_only": len(instrument_only_raw),
            "no_price_history_alias_spellings": len(aliases),
            "no_price_history_other": len(other),
            "alias_spellings_from_pack": len(aliases & pack_raw),
            "alias_spellings_from_product_events": len(aliases & set(product)),
            "definition": "distinct raw spellings across price_history, "
                          "instruments, pack and adjust_events; "
                          "no_price_history counts the spellings with no "
                          "price_history row, split into instrument-only "
                          "names, pack/adjust_events alias spellings whose "
                          "normalised key is in history, and other",
        }

    validity = _validity_rows(con)
    if validity is not None:
        block = {
            "rows": validity["rows"],
            "by_status": validity["by_status"],
            "unverified_symbols": len(validity["unverified_keys"]),
            "unverified_with_factor_steps": validity["unverified_with_steps"],
        }
        if pack_keys is not None:
            block["unverified_with_pack_step"] = len(
                validity["unverified_keys"] & pack_keys)
            block["unverified_equals_history_without_pack_steps"] = (
                validity["unverified_keys"] == (hist_keys - pack_keys))
        rep["history_validity"] = block

    if legacy_pack_symbols is not None and product_keys is not None:
        legacy_raw = {str(s) for s in legacy_pack_symbols
                      if s is not None and str(s).strip()}
        legacy_keys = {key(s) for s in legacy_raw}
        evidence = legacy_keys | product_keys
        history_without = hist_keys - evidence
        instrument_only = inst_keys - hist_keys
        block = {
            "report_value": int(report_value),
            "definition": NO_EVIDENCE_DEFINITION,
            "legacy_pack_symbols": len(legacy_keys),
            "legacy_pack_raw_symbols": len(legacy_raw),
            "legacy_pack_steps": int(legacy_pack_steps),
            "history_symbols_without_evidence": len(history_without),
            "instruments_without_history": len(instrument_only),
            "union_symbols_without_evidence": len(
                (hist_keys | inst_keys) - evidence),
        }
        block["history_plus_instruments_identity"] = (
            block["history_symbols_without_evidence"]
            + len(instrument_only - evidence))
        block["reproduces_report_value"] = (
            block["union_symbols_without_evidence"] == int(report_value))
        if pack_keys is not None:
            added = pack_keys - legacy_keys
            dropped = legacy_keys - pack_keys
            block["current_pack"] = {
                "pack_symbols": len(pack_keys),
                "history_symbols_without_evidence": rep[
                    "no_adjustment_evidence"]["history_symbols_without_evidence"],
                "history_symbols_without_pack_steps": len(hist_keys - pack_keys),
                "union_symbols_without_evidence": rep[
                    "no_adjustment_evidence"]["union_symbols_without_evidence"],
                "pack_delta": {
                    "added_keys": len(added),
                    "added_without_product_event": len(added - product_keys),
                    "dropped_keys": len(dropped),
                    "dropped_without_product_event": len(
                        dropped - product_keys),
                    "dropped_key_list": sorted(dropped),
                    "net_no_evidence_delta": (
                        len(dropped - product_keys)
                        - len(added - product_keys)),
                },
            }
        rep["report_no_evidence"] = block
    return rep


def _write_csv(path, hist_by_key, inst_names, inst_codes, pack_by_key,
               product_by_key, status_by_key):
    """One row per union key: membership in each universe and the evidence."""
    pack_keys = set(pack_by_key)
    product_keys = set(product_by_key)
    hist_keys = set(hist_by_key)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n",
                                extrasaction="raise")
        writer.writeheader()
        for k in sorted(hist_keys | set(inst_names)):
            names = inst_names.get(k, [])
            in_history = k in hist_keys
            evidence = "+".join(
                tag for tag, on in (("pack", k in pack_keys),
                                    ("product", k in product_keys)) if on)
            writer.writerow({
                "key": k,
                "bucket": ("history_and_instruments" if in_history and names
                           else ("history_only" if in_history
                                 else "instruments_only")),
                "history": 1 if in_history else 0,
                "history_raw": "|".join(sorted(hist_by_key.get(k, ()))),
                "instruments": 1 if names else 0,
                "instrument_names": "|".join(sorted(names)),
                "ins_codes": "|".join(sorted(inst_codes.get(k, ()))),
                "in_pack": 1 if k in pack_keys else 0,
                "pack_raw": "|".join(sorted(pack_by_key.get(k, ()))),
                "in_product_events": 1 if k in product_keys else 0,
                "product_event_rows": product_by_key.get(k, 0),
                "evidence": evidence or "none",
                "validity_status": status_by_key.get(k, ""),
            })


def _note_checks(rep):
    """Set-identity checks that must hold for the counts to be trustworthy."""
    checks = {
        "history_with_plus_without_equals_total": (
            rep["instruments_with_history"]
            + rep["history_outside_instruments"] == rep["history_symbols"]),
        "instruments_rows_split": (
            rep["instruments_rows_with_history"]
            + rep["instruments_rows_without_history"]
            == rep["instruments_rows_named"]),
        "named_keys_split": (
            rep["instruments_with_history"]
            + rep["instruments_without_history"] == rep["instruments_named"]),
        "union_equals_history_plus_instrument_only": (
            rep["union_symbols"] == rep["history_symbols"]
            + rep["instruments_without_history"]),
    }
    if "pack_symbols" in rep:
        checks["pack_keys_split"] = (
            rep["history_symbols_with_pack_steps"]
            + rep["history_symbols_without_pack_steps"]
            == rep["history_symbols"])
        checks["pack_symbols_inside_history"] = (
            rep["pack_symbols"] - rep["pack_symbols_without_history"]
            == rep["history_symbols_with_pack_steps"])
    if "no_adjustment_evidence" in rep:
        checks["no_evidence_adds_up"] = (
            rep["no_adjustment_evidence"]["union_symbols_without_evidence"]
            == rep["no_adjustment_evidence"][
                "history_plus_instruments_identity"])
        checks["no_evidence_history_split"] = (
            rep["no_adjustment_evidence"]["history_symbols_with_evidence"]
            + rep["no_adjustment_evidence"]["history_symbols_without_evidence"]
            == rep["history_symbols"])
    if "raw_universe" in rep:
        raw = rep["raw_universe"]
        checks["raw_no_history_split"] = (
            raw["no_price_history_instrument_only"]
            + raw["no_price_history_alias_spellings"]
            + raw["no_price_history_other"]
            == raw["no_price_history"])
    if "report_no_evidence" in rep:
        checks["report_no_evidence_adds_up"] = (
            rep["report_no_evidence"]["union_symbols_without_evidence"]
            == rep["report_no_evidence"][
                "history_plus_instruments_identity"])
    return checks


def _notes(rep):
    product = rep.get("product_events") or {}
    validity = rep.get("history_validity") or {}
    report = rep.get("report_no_evidence") or {}
    current = report.get("current_pack") or {}
    delta = current.get("pack_delta") or {}
    return [
        "Two universes, named: %d history symbols split into %d with an "
        "instruments key and %d without; the %d named instruments split into "
        "%d with history and %d without. %d instruments rows minus %d "
        "duplicate-name rows equals %d named keys; %d shared keys spell the "
        "instruments name differently from the history symbol. Union = %d."
        % (rep["history_symbols"], rep["instruments_with_history"],
           rep["history_outside_instruments"], rep["instruments_named"],
           rep["instruments_with_history"], rep["instruments_without_history"],
           rep["instruments"], rep["instruments_duplicate_name_rows"],
           rep["instruments_named"],
           rep["shared_keys_with_different_spelling"], rep["union_symbols"]),
        "Raw spellings: %d symbols = %d history + %d without a price_history "
        "row (the inventory's no_price_history flag). The %d split into %d "
        "instruments-only raw names + %d pack/adjust_events alias spellings "
        "whose normalised keys are in history (%d of them are also pack "
        "spellings, %d are adjust_events spellings; %d other), so the %d "
        "raw spellings double-count %d keys against the %d-key union."
        % ((rep.get("raw_universe") or {}).get("symbols", 0),
           rep["history_symbols"],
           (rep.get("raw_universe") or {}).get("no_price_history", 0),
           (rep.get("raw_universe") or {}).get("no_price_history", 0),
           (rep.get("raw_universe") or {}).get(
               "no_price_history_instrument_only", 0),
           (rep.get("raw_universe") or {}).get(
               "no_price_history_alias_spellings", 0),
           (rep.get("raw_universe") or {}).get("alias_spellings_from_pack", 0),
           (rep.get("raw_universe") or {}).get(
               "alias_spellings_from_product_events", 0),
           (rep.get("raw_universe") or {}).get("no_price_history_other", 0),
           (rep.get("raw_universe") or {}).get("symbols", 0),
           (rep.get("raw_universe") or {}).get("symbols", 0)
           - (rep.get("raw_universe") or {}).get("keys", 0),
           (rep.get("raw_universe") or {}).get("keys", 0)),
        "The corrections pack is %d raw symbols under %d keys (%d alias "
        "spellings) and %d step rows; %d of its keys are inside the history "
        "universe. History without a pack step = %d (%s)."
        % (rep.get("pack_raw_symbols", 0), rep.get("pack_symbols", 0),
           rep.get("pack_alias_spellings", 0), rep.get("pack_steps", 0),
           rep.get("pack_symbols", 0) - rep.get("pack_symbols_without_history", 0),
           rep.get("history_symbols_without_pack_steps", 0),
           _split(rep.get("history_symbols_without_pack_steps", 0),
                  rep["history_symbols"])),
        ("history_validity: table absent; no validity cross-check."
         if "history_validity" not in rep else
         "history_validity: %d rows (%s), %d unverified with %d of them "
         "carrying a pack step; the unverified set %s the history symbols "
         "without a pack step."
         % (validity.get("rows", 0),
            ", ".join("%s=%d" % kv for kv in
                      (validity.get("by_status") or {}).items()),
            validity.get("unverified_symbols", 0),
            validity.get("unverified_with_factor_steps", 0),
            "matches" if validity.get(
                "unverified_equals_history_without_pack_steps")
            else "does not match")),
        "adjust_events: %d rows under %d raw symbols (%d keys); %d raw "
        "spellings are outside the history spelling set but %d keys are "
        "outside the history key set. %d of the pack keys already have "
        "product events; %d symbols have product events and no pack step."
        % (product.get("rows", 0), product.get("raw_symbols", 0),
           product.get("symbols", 0),
           product.get("raw_symbols_outside_history", 0),
           product.get("symbols_outside_history", 0),
           (rep.get("overlaps") or {}).get("pack_and_product", 0),
           (rep.get("overlaps") or {}).get("product_without_pack", 0)),
        "The report's %d is a union-universe count on the r32b pack, not a "
        "history count: %d = %d history symbols with neither source + %d "
        "instruments with no history; the r32b pack %s the recorded value. "
        "With the current pack the same definition gives %d = %d + %d. "
        "History-only: %d without any evidence, %d without a pack step."
        % (report.get("report_value", REPORT_NO_EVIDENCE),
           report.get("union_symbols_without_evidence", 0),
           report.get("history_symbols_without_evidence", 0),
           report.get("instruments_without_history", 0),
           "reproduces" if report.get("reproduces_report_value")
           else "does not reproduce",
           current.get("union_symbols_without_evidence", 0),
           current.get("history_symbols_without_evidence", 0),
           report.get("instruments_without_history", 0),
           rep.get("no_adjustment_evidence", {}).get(
               "history_symbols_without_evidence", 0),
           rep.get("history_symbols_without_pack_steps", 0)),
        "The pack version moves the no-evidence count by %d: the rebuild adds "
        "%d keys (%d of them without a product event) and drops %d keys (%d "
        "of them without a product event)."
        % (delta.get("net_no_evidence_delta", 0), delta.get("added_keys", 0),
           delta.get("added_without_product_event", 0),
           delta.get("dropped_keys", 0),
           delta.get("dropped_without_product_event", 0)),
        "827/828 is a third population, not the pack: the r32b correction "
        "pack has 827 symbols while the live pack ra365-live40-v1 supplies "
        "828 asset-map entries to B2's capture plan (1,097 keys in the "
        "capture union, 758 mapped). Neither number is the 951-symbol step "
        "pack and neither is a history count.",
    ]


def build(db, pack_dir, legacy_pack_dir, out, csv_path, manifest_path,
          report_evidence=""):
    """Run the reconciliation and write the evidence JSON, CSV and manifest."""
    pack_symbols, pack_actions = (None, collections.Counter())
    legacy_symbols, legacy_actions = (None, collections.Counter())
    if pack_dir:
        pack_symbols, pack_actions = _load_pack(pack_dir)
    if legacy_pack_dir:
        legacy_symbols, legacy_actions = _load_pack(legacy_pack_dir)

    con = _connect(db)
    try:
        rep = reconcile(con, pack_symbols, sum(pack_actions.values())
                        if pack_symbols is not None else 0,
                        legacy_symbols, sum(legacy_actions.values())
                        if legacy_symbols is not None else 0)
        hist_by_key = collections.defaultdict(list)
        for symbol, in con.execute(
                "SELECT symbol FROM price_history GROUP BY symbol "
                "ORDER BY symbol"):
            if symbol is not None and str(symbol).strip():
                hist_by_key[key(symbol)].append(str(symbol))
        inst_names = collections.defaultdict(list)
        inst_codes = collections.defaultdict(list)
        for ins_code, name in con.execute(
                "SELECT ins_code,l_val18 FROM instruments "
                "WHERE l_val18 IS NOT NULL AND TRIM(l_val18)<>'' "
                "ORDER BY ins_code"):
            inst_names[key(name)].append(str(name))
            inst_codes[key(name)].append(str(ins_code))
        product_rows = _product_rows(con) or {}
        validity = _validity_rows(con) or {}
    finally:
        con.close()

    pack_by_key = collections.defaultdict(list)
    for symbol in pack_symbols or ():
        pack_by_key[key(symbol)].append(symbol)
    product_by_key = collections.Counter()
    for symbol, count in product_rows.items():
        product_by_key[key(symbol)] += int(count)

    if pack_symbols is not None and product_rows:
        pack_key_set, product_key_set = set(pack_by_key), set(product_by_key)
        rep["overlaps"] = {
            "pack_and_product": len(pack_key_set & product_key_set),
            "pack_without_product": len(pack_key_set - product_key_set),
            "product_without_pack": len(product_key_set - pack_key_set),
        }

    checks = _note_checks(rep)
    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        raise ValueError("reconciliation identity failed: %s"
                         % ", ".join(failed))
    rep["checks"] = checks

    if str(csv_path):
        _write_csv(csv_path, hist_by_key, inst_names, inst_codes, pack_by_key,
                   product_by_key, validity.get("status_by_key") or {})

    provenance = {}
    if report_evidence and os.path.isfile(report_evidence):
        with open(report_evidence, encoding="utf-8-sig") as fh:
            recorded = json.load(fh)
        flags = recorded.get("flags") or {}
        provenance = {
            "path": _rel(report_evidence),
            "schema": recorded.get("schema", ""),
            "db": recorded.get("db", ""),
            "recorded_no_adjustment_evidence": int(
                flags.get("no_adjustment_evidence") or 0),
            "recorded_symbols_with_history": recorded.get(
                "symbols_with_history"),
            "recorded_symbols_in_instruments": recorded.get(
                "symbols_in_instruments"),
            "recorded_symbols_with_product_events": recorded.get(
                "symbols_with_product_events"),
            "recorded_symbols_with_pack_steps": recorded.get(
                "symbols_with_pack_steps"),
        }
        block = rep.get("report_no_evidence") or {}
        if block and provenance["recorded_no_adjustment_evidence"]:
            block["recorded_report_value"] = provenance[
                "recorded_no_adjustment_evidence"]
            block["matches_recorded_report_value"] = (
                block["union_symbols_without_evidence"]
                == provenance["recorded_no_adjustment_evidence"]
                == block["report_value"])
    rep["provenance"] = provenance

    rep["inputs"] = {
        "db": _rel(db),
        "pack": _rel(pack_dir),
        "pack_actions": dict(sorted(pack_actions.items())),
        "legacy_pack": _rel(legacy_pack_dir),
        "legacy_pack_actions": dict(sorted(legacy_actions.items())),
        "report_evidence": _rel(report_evidence),
    }
    rep["notes"] = _notes(rep)
    rep["schema"] = 1
    rep["stage"] = "stage07_inventory_reconcile"

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    if manifest_path:
        inputs = [_rel(db)]
        if pack_dir:
            inputs.append(_rel(os.path.join(pack_dir, "factors.jsonl")))
        if legacy_pack_dir:
            inputs.append(_rel(os.path.join(legacy_pack_dir, "factors.jsonl")))
        if report_evidence:
            inputs.append(_rel(report_evidence))
        outputs = [_rel(out)]
        if str(csv_path):
            outputs.append(_rel(csv_path))
        PM.write_manifest("stage07_inventory_reconcile", inputs, outputs,
                          {"history_symbols": rep["history_symbols"],
                           "instruments": rep["instruments"],
                           "instruments_named": rep["instruments_named"],
                           "history_outside_instruments":
                               rep["history_outside_instruments"],
                           "instruments_without_history":
                               rep["instruments_without_history"],
                           "union_symbols": rep["union_symbols"],
                           "pack_symbols": rep.get("pack_symbols", 0),
                           "history_symbols_without_pack_steps":
                               rep.get("history_symbols_without_pack_steps", 0),
                           "report_no_evidence_current":
                               rep.get("no_adjustment_evidence", {}).get(
                                   "union_symbols_without_evidence", 0),
                           "report_no_evidence_r32b":
                               rep.get("report_no_evidence", {}).get(
                                   "union_symbols_without_evidence", 0)},
                          manifest_path)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--pack", default="")
    ap.add_argument("--legacy-pack", default=(
        DEFAULT_LEGACY_PACK
        if os.path.isfile(os.path.join(DEFAULT_LEGACY_PACK, "factors.jsonl"))
        else ""))
    ap.add_argument("--report-evidence", default=DEFAULT_REPORT)
    ap.add_argument("--out", required=True)
    ap.add_argument("--csv", default=DEFAULT_CSV,
                    help="raw reconciliation CSV ('' disables)")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST,
                    help="stage manifest path ('' disables)")
    args = ap.parse_args(argv)
    os.chdir(ROOT)
    try:
        rep = build(args.db, args.pack, args.legacy_pack, args.out, args.csv,
                    args.manifest, args.report_evidence)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print("INVENTORY RECONCILE FAIL: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps({
        "history_symbols": rep["history_symbols"],
        "instruments": rep["instruments"],
        "instruments_named": rep["instruments_named"],
        "history_outside_instruments": rep["history_outside_instruments"],
        "instruments_without_history": rep["instruments_without_history"],
        "union_symbols": rep["union_symbols"],
        "pack_symbols": rep.get("pack_symbols"),
        "history_symbols_without_pack_steps": rep.get(
            "history_symbols_without_pack_steps"),
        "report_no_evidence_current": rep.get(
            "no_adjustment_evidence", {}).get("union_symbols_without_evidence"),
        "report_no_evidence_r32b": rep.get(
            "report_no_evidence", {}).get("union_symbols_without_evidence"),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
