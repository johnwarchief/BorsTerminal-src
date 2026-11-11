#!/usr/bin/env python3
"""Stage 05 - per-symbol history coverage ledger for all 6,103 symbols.

One row per distinct ``price_history.symbol`` (6,103 in the seed). The row
carries the raw symbol, the normalised identity key, the instruments ISIN and
the six mission statuses from the frozen rules file.

Identity
--------
``dev.symbol_identity.key`` is the join key for every source (instruments,
step ledger, reference index, official witness tables). The raw symbol and the
ISIN are carried in the row so a key join never hides a spelling. 1,468
history symbols have no ``instruments`` row; they are counted and classified
explicitly as ``unresolved_no_instruments`` and never dropped. The three
duplicate instruments keys are resolved with B1's ISIN-first preference and
exposed through ``instrument_candidates`` (2 for a duplicated key).

Step rollup and the validity defect
-----------------------------------
The B5 ledger has 8,280 valid step rows under 951 raw symbols but only 915
normalised keys: 36 pairs are the Persian/Arabic spellings of one company
(e.g. تاپیکو / تاپيكو). A raw-symbol join loses 550 rows; a blind key join
double-counts 82 effective dates that exist under both spellings. This stage
groups by key, then by effective date, prefers the history symbol's own
spelling on an overlapping date, and collapses the 82 duplicates. The merge is
conservative: any conflict row wins, a ratio spread above FACTOR_MATERIAL is
``CONFLICT_DUPLICATE``, a spread above FACTOR_EXACT takes the weaker status.

``history_validity`` has 5,188 rows with status ``unverified`` and
``factor_steps=0``. None of those rows carries a pack step: the 782 pack
symbols with 1,358 unverified steps are all inside the 951 step-bearing pack
symbols, not inside the 5,188. The real defect is different and is reported
by this stage: the validity table joins on the raw spelling, so it cannot see
the 36 alias spellings and undercounts unverified steps by 550 (808 vs
1,358). Key joining recovers the 550; collapsing the 82 duplicate dates leaves
468 additional applicable steps (8,280 - 82 = 8,198 = 7,730 + 468).

Statuses
--------
The six mission statuses are read verbatim from
``dev/phase49_status_rules.json`` ``symbol_status_precedence`` and resolved in
that order. A symbol is verified only from a step chain or from a *full*
reference window with no factor changes. Official O1/O2 rows are positive
witnesses only; their absence is never treated as proof of no event because no
ingest-completeness proof exists in this round.

Freshness
---------
``latest_session`` is the DB's own last date (2026-11-09). A symbol at that
date is ``fresh``; up to 21 sessions behind is ``recent``; more is ``stale``.
A latest ``instrument_state`` title containing توقف/معلق/ممنوع is ``halted``
when the last bar is older than the latest session; bars on the latest session
win over an outdated state (``calendar_over_state``).

CLI:
    python _audit/phase49-full-verification/stage05_symbol_ledger.py \\
        --db _audit/phase49-finalization/seed/market.db \\
        --steps _audit/phase49-full-verification/ledgers/ADJUSTMENT-EVIDENCE-LEDGER.csv \\
        --reference _audit/phase49-full-verification/captures/reference-index-30.json \\
        --reference _audit/phase49-full-verification/captures/reference-index-7.json \\
        --asset-map _audit/phase49-full-verification/capture-plan/symbols.json \\
        --capture-plan _audit/phase49-full-verification/capture-plan/capture-plan.json \\
        --step-counts _audit/phase49-full-verification/evidence/step-ledger-counts.json \\
        --out _audit/phase49-full-verification/ledgers/HISTORY-COVERAGE-LEDGER.csv

The CSV belongs in the gitignored ``ledgers/`` area; the tracked outputs are
the small counts summary and the stage manifest under ``evidence/``. Stdlib
only, the Seed DB is opened read-only, no network call.
"""
import argparse
import bisect
import collections
import csv
import json
import math
import os
import sqlite3
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.append(ROOT)
_DEV = os.path.join(ROOT, "dev")
while _DEV in sys.path:
    sys.path.remove(_DEV)
sys.path.insert(0, _DEV)  # dev/symbol_identity wins over the root shim

from symbol_identity import key, load_instruments  # noqa: E402
import phase49_manifest as PM  # noqa: E402

MISSION_STATUSES = (
    "VERIFIED_WITH_EVENTS", "VERIFIED_NO_APPLICABLE_EVENT",
    "RECONSTRUCTED_VERIFIED", "CONFLICT", "BLOCKED_SOURCE",
    "INSUFFICIENT_EVIDENCE",
)
CONFLICT_STEP_STATUSES = (
    "CONFLICT_RATIO", "CONFLICT_DATE", "CONFLICT_DUPLICATE", "CONFLICT_CHAIN",
)
VERIFIED_STEP_STATUSES = (
    "VERIFIED_OFFICIAL", "VERIFIED_MULTI_SOURCE", "VERIFIED_REFERENCE",
)
HALT_WORDS = ("توقف", "معلق", "ممنوع")
RECENT_SESSIONS = 21

DEFAULT_RULES = os.path.join(ROOT, "dev", "phase49_status_rules.json")
DEFAULT_COUNTS = os.path.join(HERE, "evidence", "symbol-ledger-counts.json")
DEFAULT_MANIFEST = os.path.join(HERE, "evidence",
                                "stage05_symbol_ledger.manifest.json")

FIELDS = [
    "symbol", "key", "ins_code", "isin", "asset_id", "identity_status",
    "instrument_candidates", "instrument_status", "instrument_state_date",
    "first_date", "last_date", "latest_session", "rows", "trading_sessions",
    "duplicate_dates", "sessions_behind", "stale_status", "stale_basis",
    "source_coverage", "raw_ohlc_valid", "anomalies", "gaps",
    "adjusted_available", "evidence_tier", "event_coverage", "official_o1",
    "official_o2", "official_o1_in_range", "official_o1_material",
    "ref_coverage", "ref_days", "ref_first", "ref_last", "step_rows",
    "factor_steps", "factor_verified", "factor_reconstructed",
    "factor_unverified", "factor_conflict", "factor_partial",
    "factor_insufficient", "factor_blocked", "factor_invalid_dropped",
    "alias_duplicate_dates", "alias_ratio_conflicts", "alias_ratio_partials",
    "alias_only_steps", "validity_status", "validity_factor_steps",
    "validity_factor_unverified", "validity_delta", "validity_match",
    "verification_method", "final_status", "remaining_blocker",
    "no_event_basis",
]

_RULES_CACHE = {}
_CACHE = {}


class _Rules(object):
    def __init__(self, payload):
        self.payload = payload
        self.precedence = list(payload.get("symbol_status_precedence") or [])
        self.step_precedence = list(payload.get("step_status_precedence") or [])
        self.tiers = list(payload.get("evidence_tiers") or [])
        self.tolerances = dict(payload.get("tolerances") or {})

    def tol(self, name, default):
        try:
            value = float(self.tolerances[name])
        except (KeyError, TypeError, ValueError):
            return default
        return value if math.isfinite(value) else default


def load_rules(path=DEFAULT_RULES):
    path = os.path.abspath(path)
    if path in _RULES_CACHE:
        return _RULES_CACHE[path]
    with open(path, encoding="utf-8-sig") as fh:
        payload = json.load(fh)
    rules = _Rules(payload)
    if set(rules.precedence) != set(MISSION_STATUSES):
        raise ValueError(
            "symbol_status_precedence is not the six mission statuses: %r"
            % (rules.precedence,))
    _RULES_CACHE[path] = rules
    return rules


def _connect(db):
    return sqlite3.connect("file:%s?mode=ro" % os.path.abspath(db).replace(
        "\\", "/"), uri=True)


def _rel(path):
    """Repo-relative POSIX path for tracked manifests; absolute outside."""
    try:
        rel = os.path.relpath(os.path.abspath(path), ROOT)
    except ValueError:  # different drive on Windows
        rel = os.path.abspath(path)
    return rel.replace("\\", "/")


def _load_json(path):
    if not path:
        return {}
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def _ratio(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _pack_validity(step_counts):
    if not step_counts:
        return None
    by_validity = step_counts.get("by_validity") or {}
    return {name: int(by_validity.get(name, 0) or 0)
            for name in ("verified", "reconstructed_verified", "unverified",
                         "invalid_dropped")}


def _iso_even(value):
    """``20200102`` -> ``2020-01-02``; ``""`` when it is not a real day."""
    try:
        text = str(int(str(value)[:8]))
    except (TypeError, ValueError):
        return ""
    if len(text) < 8:
        return ""
    y, m, d = int(text[:4]), int(text[4:6]), int(text[6:8])
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return ""


def _cache(con):
    entry = _CACHE.get(id(con))
    if entry is None or entry["con"] is not con:
        entry = {"con": con, "ident": None, "candidates": None,
                 "states": None, "validity": None, "validity_key": None}
        _CACHE[id(con)] = entry
    return entry


def _identity_maps(con):
    cache = _cache(con)
    if cache["ident"] is not None:
        return cache["ident"], cache["candidates"]
    ident = load_instruments(con)
    candidates = collections.Counter()
    for (name,) in con.execute(
            "SELECT l_val18 FROM instruments WHERE l_val18 IS NOT NULL "
            "AND TRIM(l_val18)<>''"):
        candidates[key(name)] += 1
    cache["ident"] = ident
    cache["candidates"] = candidates
    return ident, candidates


def _states(con):
    cache = _cache(con)
    if cache["states"] is not None:
        return cache["states"]
    out = {}
    try:
        rows = con.execute(
            "SELECT ins_code,c_etaval_title,d_even FROM instrument_state "
            "ORDER BY d_even").fetchall()
    except sqlite3.OperationalError:
        rows = []
    for ins_code, title, d_even in rows:
        if ins_code is None:
            continue
        out[str(ins_code)] = (str(title or ""), _iso_even(d_even))
    cache["states"] = out
    return out


def _validity_maps(con):
    cache = _cache(con)
    if cache["validity"] is not None:
        return cache["validity"], cache["validity_key"]
    by_raw, by_key = {}, {}
    try:
        rows = con.execute(
            "SELECT symbol,status,factor_steps,factor_verified,"
            "factor_reconstructed,factor_unverified "
            "FROM history_validity").fetchall()
    except sqlite3.OperationalError:
        rows = []
    for symbol, status, steps, verified, reconstructed, unverified in rows:
        rec = {"status": str(status or ""),
               "factor_steps": int(steps or 0),
               "factor_verified": int(verified or 0),
               "factor_reconstructed": int(reconstructed or 0),
               "factor_unverified": int(unverified or 0)}
        if symbol is not None:
            by_raw[str(symbol)] = rec
            by_key.setdefault(key(symbol), rec)
    cache["validity"] = by_raw
    cache["validity_key"] = by_key
    return by_raw, by_key


def _latest_session(calendar):
    if not calendar:
        return ""
    if isinstance(calendar, (list, tuple)):
        return calendar[-1]
    return max(calendar)


def _sessions_behind(calendar, last):
    if not last:
        return 0
    if isinstance(calendar, (list, tuple)):
        return len(calendar) - bisect.bisect_right(calendar, last)
    return sum(1 for d in calendar if d > last)


def _gap_count(calendar, first, last, dates):
    if not first or not last:
        return 0
    if isinstance(calendar, (list, tuple)):
        span = (bisect.bisect_right(calendar, last)
                - bisect.bisect_left(calendar, first))
        return max(span - len(dates), 0)
    return len({d for d in calendar if first <= d <= last} - set(dates))


def _as_step_rows(steps):
    if not steps:
        return []
    if isinstance(steps, dict):
        return [v for v in steps.values() if isinstance(v, dict)]
    return list(steps)


def _severity(status):
    """0 = most severe; 4 = independently verified."""
    if status in CONFLICT_STEP_STATUSES:
        return 0
    if status == "BLOCKED_SOURCE":
        return 1
    if status == "INSUFFICIENT_EVIDENCE" or status.startswith("PARTIAL_"):
        return 2
    if status == "RECONSTRUCTED_AUDITED":
        return 3
    if status in VERIFIED_STEP_STATUSES:
        return 4
    return 5


def _step_index(status, rules):
    try:
        return rules.step_precedence.index(status)
    except ValueError:
        return len(rules.step_precedence)


def _tier_union(rows, rules):
    tokens = set()
    for row in rows:
        for token in str(row.get("evidence_tier") or "").split("+"):
            if token:
                tokens.add(token)
    ordered = [t for t in rules.tiers if t in tokens]
    for token in sorted(tokens):
        if token not in ordered:
            ordered.append(token)
    return "+".join(ordered)


def _merge_steps(step_rows, db_symbol, rules):
    """Collapse key-coupled rows into one step per effective date.

    ``db_symbol`` is the raw history spelling. On an overlapping date its own
    row is the identity-consistent witness; if the two spellings disagree by
    more than the frozen DEDUPE_RATIO_TOL (1%) the merged step is
    CONFLICT_DUPLICATE, and a spread above FACTOR_EXACT keeps the weaker
    status instead of claiming an exact match. Rows under the other spelling
    only (the old-history half of a split pack) are kept: they are the steps
    the raw-symbol validity table cannot see.
    """
    exact = rules.tol("FACTOR_EXACT", 1e-3)
    material = rules.tol("FACTOR_MATERIAL", 1e-2)
    dedupe = rules.tol("DEDUPE_RATIO_TOL", material)
    valid = [r for r in step_rows
             if str(r.get("final_status") or "") != "INVALID_DROPPED"]
    invalid = len(step_rows) - len(valid)
    by_date = collections.defaultdict(list)
    for row in valid:
        by_date[str(row.get("effective_date") or "")].append(row)

    merged = []
    for effective_date in sorted(by_date):
        group = by_date[effective_date]
        raws = {str(r.get("symbol") or "") for r in group}
        primary = None
        for row in group:
            if str(row.get("symbol") or "") == db_symbol:
                primary = row
                break
        ordered = sorted(
            group, key=lambda r: (
                _severity(str(r.get("final_status") or "")),
                _step_index(str(r.get("final_status") or ""), rules)))
        chosen = ordered[0]
        status = str(chosen.get("final_status") or "")
        has_conflict = any(
            str(r.get("final_status") or "") in CONFLICT_STEP_STATUSES
            for r in group)
        ratios = [r for r in (_ratio(x.get("ratio")) for x in group)
                  if r is not None]
        spread = None
        if len(ratios) > 1:
            top = max(abs(r) for r in ratios)
            spread = (max(ratios) - min(ratios)) / top if top else 0.0
        ratio_conflict = spread is not None and spread > dedupe
        ratio_partial = (spread is not None and spread > exact
                         and not ratio_conflict)
        if has_conflict:
            chosen = ordered[0]
            status = str(chosen.get("final_status") or "")
        elif ratio_conflict:
            status = "CONFLICT_DUPLICATE"
            chosen = ordered[0]
        elif ratio_partial:
            chosen = ordered[0]
            status = str(chosen.get("final_status") or "")
        elif primary is not None:
            # Exact date and exact ratio under both spellings: the history
            # symbol's own row is the authoritative witness.
            chosen = primary
            status = str(primary.get("final_status") or "")
        merged.append({
            "date": effective_date,
            "status": status,
            "ratio": _ratio(chosen.get("ratio")),
            "tier": _tier_union(group, rules),
            "raws": sorted(raws),
            "duplicate": len(raws) > 1,
            "alias_only": primary is None,
            "ratio_conflict": ratio_conflict,
            "ratio_partial": ratio_partial,
        })
    return merged, {
        "invalid": invalid,
        "step_rows": len(valid),
        "alias_duplicate_dates": sum(1 for m in merged if m["duplicate"]),
        "alias_ratio_conflicts": sum(1 for m in merged
                                     if m["ratio_conflict"]),
        "alias_ratio_partials": sum(1 for m in merged
                                    if m["ratio_partial"]),
        "alias_only_steps": sum(1 for m in merged if m["alias_only"]),
    }


def _first_by_precedence(candidates, precedence):
    for status in precedence:
        if status in candidates:
            return status
    return "INSUFFICIENT_EVIDENCE"


def _reference_for(reference, k, symbol):
    if not reference:
        return {}
    rec = reference.get(k)
    if rec is None:
        rec = reference.get(symbol)
    return rec or {}


def _official_for(official_counts, k):
    rec = (official_counts or {}).get(k) or {}
    return (int(rec.get("o1") or 0), int(rec.get("o2") or 0),
            list(rec.get("events") or []))


def _event_is_material(event, material):
    ratio = event.get("ratio")
    if ratio is None:
        return True
    try:
        value = float(ratio)
    except (TypeError, ValueError):
        return True
    return abs(value - 1.0) > material


def _identity_for(con, symbol, asset_map):
    ident, candidates = _identity_maps(con)
    k = key(symbol)
    asset_rec = (asset_map or {}).get(k)
    asset_id = ""
    plan_ins = ""
    if isinstance(asset_rec, dict):
        asset_id = str(asset_rec.get("asset_id") or "")
        plan_ins = str(asset_rec.get("ins_code") or "")
    elif asset_rec is not None:
        asset_id = str(asset_rec or "")
    rec = ident.get(k)
    if rec is not None:
        count = int(candidates.get(k, 1))
        return {
            "key": k,
            "ins_code": str(rec.get("ins_code") or ""),
            "isin": str(rec.get("isin") or ""),
            "asset_id": asset_id,
            "identity_status": ("resolved_instruments_ambiguous"
                                if count > 1 else "resolved_instruments"),
            "instrument_candidates": count,
        }
    if plan_ins or asset_id:
        return {"key": k, "ins_code": plan_ins, "isin": "",
                "asset_id": asset_id,
                "identity_status": "resolved_capture_plan",
                "instrument_candidates": 0}
    return {"key": k, "ins_code": "", "isin": "", "asset_id": asset_id,
            "identity_status": "unresolved_no_instruments",
            "instrument_candidates": 0}


def _blocker(final, status_counts, stats, identity, ref_cov, changes,
             official_in_range, invalid):
    parts = []
    if final == "CONFLICT":
        details = []
        for status in CONFLICT_STEP_STATUSES:
            if status_counts.get(status):
                details.append("%s:%d" % (status, status_counts[status]))
        parts.append("STEP_CONFLICT")
        parts.extend(details)
    elif final == "BLOCKED_SOURCE":
        parts.append("STEP_BLOCKED_SOURCE:%d"
                     % status_counts.get("BLOCKED_SOURCE", 0))
    elif final == "INSUFFICIENT_EVIDENCE":
        if stats["step_rows"]:
            for status in ("INSUFFICIENT_EVIDENCE", "PARTIAL_OFFICIAL",
                           "PARTIAL_REFERENCE", "BLOCKED_SOURCE"):
                if status_counts.get(status):
                    parts.append("%s:%d" % (status, status_counts[status]))
        else:
            if invalid:
                parts.append("ONLY_INVALID_DROPPED_STEPS:%d" % invalid)
            if ref_cov == "partial":
                parts.append("REFERENCE_WINDOW_PARTIAL")
            elif ref_cov == "full" and changes:
                parts.append("REFERENCE_FACTOR_CHANGES_WITHOUT_STEPS:%d"
                             % len(changes))
            elif ref_cov == "none":
                parts.append("NO_REFERENCE_WINDOW")
            if official_in_range:
                parts.append("OFFICIAL_EVENT_WITHOUT_STEP:%d"
                             % official_in_range)
            if not invalid:
                parts.append("NO_PACK_STEPS")
    elif final == "RECONSTRUCTED_VERIFIED":
        parts.append("NO_INDEPENDENT_EVIDENCE:RECONSTRUCTED_AUDITED:%d"
                     % status_counts.get("RECONSTRUCTED_AUDITED", 0))
    if final == "INSUFFICIENT_EVIDENCE" and not parts:
        parts.append("UNRECOGNISED_STEP_STATUS:%d" % stats["step_rows"])
    if (identity["identity_status"] == "unresolved_no_instruments"
            and final not in ("VERIFIED_WITH_EVENTS",
                              "VERIFIED_NO_APPLICABLE_EVENT")):
        parts.insert(0, "SYMBOL_IDENTITY_MISMATCH:NO_INSTRUMENTS_ROW")
    return ";".join(parts)


def symbol_row(con, symbol, steps, reference, calendar, asset_map=None,
               official_counts=None, rules=None):
    """One ledger row; ``None`` only when the symbol has no price history."""
    rules = rules or load_rules()
    total, first, last, zero_vol, bad_hl, bad_close = con.execute(
        "SELECT COUNT(*),MIN(date),MAX(date),"
        "SUM(CASE WHEN COALESCE(volume,0)=0 THEN 1 ELSE 0 END),"
        "SUM(CASE WHEN low IS NOT NULL AND high IS NOT NULL AND low>high "
        "THEN 1 ELSE 0 END),"
        "SUM(CASE WHEN close IS NOT NULL AND low IS NOT NULL "
        "AND high IS NOT NULL AND (close<low OR close>high) THEN 1 ELSE 0 END) "
        "FROM price_history WHERE symbol=?", (symbol,)).fetchone()
    rows = int(total or 0)
    if not rows:
        return None
    zero_vol = int(zero_vol or 0)
    bad_hl = int(bad_hl or 0)
    bad_close = int(bad_close or 0)
    dates = [r[0] for r in con.execute(
        "SELECT date FROM price_history WHERE symbol=?", (symbol,))]
    unique_dates = set(dates)
    sources = dict(con.execute(
        "SELECT COALESCE(src,'legacy-unknown'),COUNT(*) FROM price_history "
        "WHERE symbol=? GROUP BY 1", (symbol,)))

    identity = _identity_for(con, symbol, asset_map)
    state_title, state_date = "", ""
    if identity["ins_code"]:
        state_title, state_date = _states(con).get(
            identity["ins_code"], ("", ""))

    validity_raw, validity_key = _validity_maps(con)
    validity = validity_raw.get(symbol) or validity_key.get(identity["key"])

    ref = _reference_for(reference, identity["key"], symbol)
    type0 = ref.get("type0") or {}
    type7 = ref.get("type7") or {}
    ref_present = bool(ref)
    ref_full = bool(
        ref_present and type0.get("first") and type0.get("last")
        and type7.get("first") and type7.get("last")
        and type0["first"] <= first and type7["first"] <= first
        and type0["last"] >= last and type7["last"] >= last)
    ref_cov = "full" if ref_full else ("partial" if ref_present else "none")
    changes = list(ref.get("factor_changes") or [])

    official_o1, official_o2, events = _official_for(
        official_counts, identity["key"])
    in_range = [e for e in events
                if e.get("date") and first <= str(e["date"]) <= last]
    material_events = [
        e for e in in_range
        if _event_is_material(e, rules.tol("FACTOR_MATERIAL", 1e-2))]

    merged, stats = _merge_steps(_as_step_rows(steps), symbol, rules)
    status_counts = collections.Counter(m["status"] for m in merged)
    factor_steps = len(merged)
    factor_verified = sum(
        1 for m in merged if m["status"] in VERIFIED_STEP_STATUSES)
    factor_reconstructed = status_counts.get("RECONSTRUCTED_AUDITED", 0)
    factor_conflict = sum(status_counts.get(s, 0)
                          for s in CONFLICT_STEP_STATUSES)
    factor_partial = (status_counts.get("PARTIAL_OFFICIAL", 0)
                      + status_counts.get("PARTIAL_REFERENCE", 0))
    factor_insufficient = status_counts.get("INSUFFICIENT_EVIDENCE", 0)
    factor_blocked = status_counts.get("BLOCKED_SOURCE", 0)
    factor_unverified = (factor_steps - factor_verified
                         - factor_reconstructed)
    if factor_unverified != (factor_conflict + factor_partial
                             + factor_insufficient + factor_blocked):
        raise ValueError(
            "step status residual mismatch for %r: %d != %d"
            % (symbol, factor_unverified,
               factor_conflict + factor_partial + factor_insufficient
               + factor_blocked))

    identity_unresolved = (
        identity["identity_status"] == "unresolved_no_instruments")
    if factor_steps:
        candidates = set()
        if factor_conflict:
            candidates.add("CONFLICT")
        if factor_blocked:
            candidates.add("BLOCKED_SOURCE")
        if factor_insufficient or factor_partial:
            candidates.add("INSUFFICIENT_EVIDENCE")
        if factor_reconstructed:
            candidates.add("RECONSTRUCTED_VERIFIED")
        if (factor_verified == factor_steps):
            candidates.add("VERIFIED_WITH_EVENTS")
        if identity_unresolved:
            candidates.add("INSUFFICIENT_EVIDENCE")
        final = _first_by_precedence(candidates, rules.precedence)
    elif identity_unresolved:
        final = "INSUFFICIENT_EVIDENCE"
    elif stats["invalid"]:
        final = "INSUFFICIENT_EVIDENCE"
    elif ref_full and not changes:
        final = "VERIFIED_NO_APPLICABLE_EVENT"
    else:
        final = "INSUFFICIENT_EVIDENCE"
    if final not in MISSION_STATUSES:
        raise ValueError("unknown final status %r for %r" % (final, symbol))

    latest = _latest_session(calendar)
    behind = _sessions_behind(calendar, last)
    halted_state = bool(state_title) and any(
        word in state_title for word in HALT_WORDS)
    if last >= latest:
        stale_status = "fresh"
        stale_basis = "calendar_over_state" if halted_state else "calendar"
    elif halted_state:
        stale_status = "halted"
        stale_basis = "instrument_state"
    elif behind > RECENT_SESSIONS:
        stale_status = "stale"
        stale_basis = "calendar"
    else:
        stale_status = "recent"
        stale_basis = "calendar"

    if identity_unresolved:
        adjusted = "none" if not factor_steps else "pack"
        method = "step-ledger" if factor_steps else "none"
    else:
        adjusted = "pack" if factor_steps else "none"
        method = ("step-ledger" if factor_steps
                  else ("reference-window" if ref_present else "none"))
    if factor_steps:
        evidence_tier = _tier_union(
            [r for r in _as_step_rows(steps)
             if str(r.get("final_status") or "") != "INVALID_DROPPED"],
            rules)
    elif final == "VERIFIED_NO_APPLICABLE_EVENT":
        evidence_tier = "R1"
    else:
        evidence_tier = ""

    event_coverage = "pack" if factor_steps else "none"
    if official_o1 or official_o2:
        event_coverage += ";O1=%d;O2=%d" % (official_o1, official_o2)

    if validity is not None:
        validity_status = validity["status"]
        validity_steps = validity["factor_steps"]
        validity_unverified = validity["factor_unverified"]
        validity_verified = validity.get("factor_verified", 0)
        validity_reconstructed = validity.get("factor_reconstructed", 0)
        validity_delta = factor_steps - validity_steps
        if validity_delta == 0:
            validity_match = "match"
        elif (stats["alias_only_steps"] > 0
              and validity_delta == stats["alias_only_steps"]):
            validity_match = "alias_steps_omitted"
        else:
            validity_match = "step_count_mismatch"
    else:
        validity_status = ""
        validity_steps = ""
        validity_unverified = ""
        validity_verified = 0
        validity_reconstructed = 0
        validity_delta = ""
        validity_match = "missing"

    blocker = _blocker(final, status_counts, stats, identity, ref_cov,
                       changes, len(in_range), stats["invalid"])
    return {
        "symbol": symbol,
        "key": identity["key"],
        "ins_code": identity["ins_code"],
        "isin": identity["isin"],
        "asset_id": identity["asset_id"],
        "identity_status": identity["identity_status"],
        "instrument_candidates": identity["instrument_candidates"],
        "instrument_status": state_title,
        "instrument_state_date": state_date,
        "first_date": first,
        "last_date": last,
        "latest_session": latest,
        "rows": rows,
        "trading_sessions": len(unique_dates),
        "duplicate_dates": rows - len(unique_dates),
        "sessions_behind": behind,
        "stale_status": stale_status,
        "stale_basis": stale_basis,
        "source_coverage": json.dumps(sources, ensure_ascii=False,
                                      sort_keys=True),
        "raw_ohlc_valid": ("ok" if not (bad_hl or bad_close) else "invalid"),
        "anomalies": zero_vol + bad_hl + bad_close,
        "gaps": _gap_count(calendar, first, last, dates),
        "adjusted_available": adjusted,
        "evidence_tier": evidence_tier,
        "event_coverage": event_coverage,
        "official_o1": official_o1,
        "official_o2": official_o2,
        "official_o1_in_range": len(in_range),
        "official_o1_material": len(material_events),
        "ref_coverage": ref_cov,
        "ref_days": int(type0.get("n") or 0),
        "ref_first": type0.get("first") or "",
        "ref_last": type0.get("last") or "",
        "step_rows": stats["step_rows"],
        "factor_steps": factor_steps,
        "factor_verified": factor_verified,
        "factor_reconstructed": factor_reconstructed,
        "factor_unverified": factor_unverified,
        "factor_conflict": factor_conflict,
        "factor_partial": factor_partial,
        "factor_insufficient": factor_insufficient,
        "factor_blocked": factor_blocked,
        "factor_invalid_dropped": stats["invalid"],
        "alias_duplicate_dates": stats["alias_duplicate_dates"],
        "alias_ratio_conflicts": stats["alias_ratio_conflicts"],
        "alias_ratio_partials": stats["alias_ratio_partials"],
        "alias_only_steps": stats["alias_only_steps"],
        "validity_status": validity_status,
        "validity_factor_steps": validity_steps,
        "validity_factor_unverified": validity_unverified,
        "validity_delta": validity_delta,
        "validity_match": validity_match,
        "verification_method": method,
        "final_status": final,
        "remaining_blocker": blocker,
        "no_event_basis": ("R1_FULL_WINDOW"
                           if final == "VERIFIED_NO_APPLICABLE_EVENT" else ""),
        "_validity_verified": validity_verified,
        "_validity_reconstructed": validity_reconstructed,
    }


# --------------------------------------------------------------------------
# Build / CLI
# --------------------------------------------------------------------------

def _load_references(paths):
    out = {}
    for path in paths:
        data = _load_json(path)
        if not isinstance(data, dict):
            raise ValueError("reference index %s is not a JSON object" % path)
        for raw_key, rec in data.items():
            k = str(rec.get("key") or raw_key)
            current = out.get(k)
            if current is None:
                out[k] = rec
                continue
            merged = dict(current)
            for series in ("type0", "type7"):
                a = current.get(series) or {}
                b = rec.get(series) or {}
                merged[series] = (a if int(a.get("n") or 0)
                                  >= int(b.get("n") or 0) else b)
            changes = {}
            for change in (list(current.get("factor_changes") or [])
                           + list(rec.get("factor_changes") or [])):
                changes[(str(change.get("date") or ""),
                         round(float(change.get("ratio_change") or 0), 12))] = \
                    change
            merged["factor_changes"] = [
                changes[x] for x in sorted(changes)]
            merged["asset_ids"] = sorted(
                set(current.get("asset_ids") or [])
                | set(rec.get("asset_ids") or []))
            merged["raw_symbols"] = sorted(
                set(current.get("raw_symbols") or [])
                | set(rec.get("raw_symbols") or []))
            out[k] = merged
    return out


def _load_asset_map(path):
    if not path:
        return {}, []
    out, ambiguous = {}, []
    data = _load_json(path)
    if not isinstance(data, list):
        raise ValueError("asset map %s is not a JSON array" % path)
    for rec in data:
        if not isinstance(rec, dict):
            continue
        k = key(rec.get("symbol"))
        if not k:
            continue
        if k in out:
            ambiguous.append(k)
            continue
        out[k] = rec
    return out, ambiguous


def _load_official(con):
    counts = {}
    totals = {"o1": 0, "o2": 0}
    for table in ("price_adjust_events", "share_change_events"):
        try:
            rows = con.execute(
                "SELECT symbol,d_even,ratio FROM %s" % table).fetchall()
        except sqlite3.OperationalError:
            continue
        for symbol, d_even, ratio in rows:
            totals["o1"] += 1
            if symbol is None or not str(symbol).strip():
                continue
            rec = counts.setdefault(key(symbol), {"o1": 0, "o2": 0,
                                                  "events": []})
            rec["o1"] += 1
            rec["events"].append({
                "date": _iso_even(d_even),
                "ratio": _ratio(ratio),
                "table": table,
            })
    try:
        rows = con.execute(
            "SELECT symbol,COUNT(*) FROM codal_notices GROUP BY symbol"
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    for symbol, count in rows:
        totals["o2"] += int(count)
        if symbol is None or not str(symbol).strip():
            continue
        rec = counts.setdefault(key(symbol), {"o1": 0, "o2": 0,
                                              "events": []})
        rec["o2"] = int(rec.get("o2") or 0) + int(count)
    return counts, totals


def _counts(rows, field):
    out = collections.Counter(str(r[field]) for r in rows)
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def _status_counts(rows):
    out = collections.Counter(r["final_status"] for r in rows)
    return {status: out.get(status, 0) for status in MISSION_STATUSES}


def _cross(rows, left, right):
    out = collections.defaultdict(lambda: collections.Counter())
    for row in rows:
        out[str(row[left])][str(row[right])] += 1
    return {k: dict(sorted(v.items())) for k, v in sorted(out.items())}


def _blocker_counts(rows):
    out = collections.defaultdict(lambda: collections.Counter())
    for row in rows:
        blocker = str(row.get("remaining_blocker") or "")
        if not blocker:
            continue
        for token in blocker.split(";"):
            name = token.split(":")[0]
            if name:
                out[row["final_status"]][name] += 1
    return {k: dict(sorted(v.items())) for k, v in sorted(out.items())}


def build(db, steps_path, references, asset_map_path, out, counts_path,
          manifest_path="", capture_plan_path="", step_counts_path="",
          rules_path=DEFAULT_RULES, expect_symbols=0):
    rules = load_rules(rules_path)
    reference = _load_references(references)
    asset_map, asset_ambiguous = _load_asset_map(asset_map_path)
    with open(steps_path, encoding="utf-8-sig", newline="") as fh:
        step_rows = list(csv.DictReader(fh))
    steps_by_key = collections.defaultdict(list)
    raw_step_symbols, raw_step_keys = set(), set()
    valid_raw = invalid_raw = 0
    for row in step_rows:
        symbol = row.get("symbol")
        if symbol is None or not str(symbol).strip():
            continue
        k = key(symbol)
        steps_by_key[k].append(row)
        raw_step_symbols.add(str(symbol))
        raw_step_keys.add(k)
        if str(row.get("final_status") or "") == "INVALID_DROPPED":
            invalid_raw += 1
        else:
            valid_raw += 1

    con = _connect(db)
    try:
        calendar = [r[0] for r in con.execute(
            "SELECT DISTINCT date FROM price_history ORDER BY date")]
        symbols = [r[0] for r in con.execute(
            "SELECT symbol FROM price_history GROUP BY symbol ORDER BY symbol")]
        db_raw_by_key = {key(s): s for s in symbols}
        official, official_totals = _load_official(con)
        _, candidates = _identity_maps(con)
        source_counts = {
            str(src or "legacy-unknown"): int(count)
            for src, count in con.execute(
                "SELECT COALESCE(src,'legacy-unknown'),COUNT(*) "
                "FROM price_history GROUP BY 1")}
        ledger = []
        for symbol in symbols:
            row = symbol_row(con, symbol, steps_by_key.get(key(symbol), []),
                             reference, calendar, asset_map=asset_map,
                             official_counts=official, rules=rules)
            if row is not None:
                ledger.append(row)
    finally:
        con.close()
        _CACHE.pop(id(con), None)

    if expect_symbols and len(ledger) != expect_symbols:
        raise ValueError("expected %d symbols, found %d"
                         % (expect_symbols, len(ledger)))
    by_final = _status_counts(ledger)
    if sum(by_final.values()) != len(ledger):
        raise ValueError("final status counts do not sum to the row count")
    if sum(int(r["factor_steps"]) for r in ledger) != (
            sum(int(r["step_rows"]) for r in ledger)
            - sum(int(r["alias_duplicate_dates"]) for r in ledger)):
        raise ValueError("step_rows - duplicate dates != factor_steps")
    delta_rows = [r for r in ledger if r["validity_delta"] != ""]
    if sum(int(r["validity_delta"]) for r in delta_rows) != (
            sum(int(r["factor_steps"]) for r in delta_rows)
            - sum(int(r["validity_factor_steps"]) for r in delta_rows)):
        raise ValueError("validity delta does not reconcile with step counts")

    capture_plan = _load_json(capture_plan_path)
    if capture_plan and not isinstance(capture_plan, dict):
        raise ValueError("capture plan %s is not a JSON object"
                         % capture_plan_path)
    capture_counts = dict((capture_plan or {}).get("counts") or {})
    step_counts = _load_json(step_counts_path)
    if step_counts and not isinstance(step_counts, dict):
        raise ValueError("step counts %s is not a JSON object"
                         % step_counts_path)
    if step_counts:
        if int(step_counts.get("rows") or 0) != len(step_rows):
            raise ValueError("step-ledger-counts rows=%s but the CSV has %d"
                             % (step_counts.get("rows"), len(step_rows)))
        inputs = step_counts.get("inputs") or {}
        if int(inputs.get("pack_valid_steps") or 0) != valid_raw:
            raise ValueError("pack_valid_steps=%s but the CSV has %d valid"
                             % (inputs.get("pack_valid_steps"), valid_raw))
        if int(inputs.get("pack_dropped_steps") or 0) != invalid_raw:
            raise ValueError("pack_dropped_steps=%s but the CSV has %d invalid"
                             % (inputs.get("pack_dropped_steps"), invalid_raw))
    latest = _latest_session(calendar)
    cp_last = (capture_plan.get("calendar") or {}).get("last")
    if cp_last and cp_last != latest:
        raise ValueError("capture-plan calendar last %r != DB latest %r"
                         % (cp_last, latest))

    multi_keys = {k for k, rows in steps_by_key.items()
                  if len({str(r.get("symbol")) for r in rows}) > 1}
    alias_raw_steps = 0
    for row in step_rows:
        if str(row.get("final_status") or "") == "INVALID_DROPPED":
            continue
        raw_symbol = str(row.get("symbol") or "")
        k = key(raw_symbol)
        if k in multi_keys and raw_symbol != db_raw_by_key.get(k):
            alias_raw_steps += 1

    ordered = [{field: r.get(field, "") for field in FIELDS} for r in ledger]
    with open(out, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n",
                                extrasaction="raise")
        writer.writeheader()
        writer.writerows(ordered)

    unresolved = [r for r in ledger
                  if r["identity_status"] == "unresolved_no_instruments"]
    no_steps = [r for r in ledger if int(r["factor_steps"]) == 0]
    with_steps = [r for r in ledger if int(r["factor_steps"]) > 0]
    duplicate_keys = sorted(k for k, n in candidates.items() if n > 1)
    history_keys = {r["key"] for r in ledger}
    duplicate_in_history = [k for k in duplicate_keys if k in history_keys]

    unverified = [r for r in ledger if r["validity_status"] == "unverified"]
    validity_by_status = _counts(ledger, "validity_status")
    validity_by_status.pop("", None)
    hv_factor_steps = sum(int(r["validity_factor_steps"])
                          for r in delta_rows)
    hv_factor_unverified = sum(int(r["validity_factor_unverified"])
                               for r in delta_rows)
    hv_factor_verified = sum(int(r.get("_validity_verified") or 0)
                             for r in delta_rows)
    hv_factor_reconstructed = sum(
        int(r.get("_validity_reconstructed") or 0) for r in delta_rows)
    hv_unverified_positive = sum(
        1 for r in delta_rows if int(r["validity_factor_unverified"]) > 0)
    factor_steps_total = sum(int(r["factor_steps"]) for r in ledger)
    factor_verified_total = sum(int(r["factor_verified"]) for r in ledger)
    factor_reconstructed_total = sum(
        int(r["factor_reconstructed"]) for r in ledger)
    factor_unverified_total = sum(
        int(r["factor_unverified"]) for r in ledger)
    factor_conflict_total = sum(int(r["factor_conflict"]) for r in ledger)
    factor_partial_total = sum(int(r["factor_partial"]) for r in ledger)
    factor_insufficient_total = sum(
        int(r["factor_insufficient"]) for r in ledger)
    factor_blocked_total = sum(int(r["factor_blocked"]) for r in ledger)
    step_rows_total = sum(int(r["step_rows"]) for r in ledger)
    invalid_total = sum(int(r["factor_invalid_dropped"]) for r in ledger)
    duplicate_dates_total = sum(
        int(r["alias_duplicate_dates"]) for r in ledger)
    alias_only_total = sum(int(r["alias_only_steps"]) for r in ledger)
    alias_ratio_conflict_total = sum(
        int(r["alias_ratio_conflicts"]) for r in ledger)
    alias_ratio_partial_total = sum(
        int(r["alias_ratio_partials"]) for r in ledger)
    factor_steps_all = sum(int(r["factor_steps"]) for r in ledger)
    delta_total = sum(int(r["validity_delta"]) for r in delta_rows)
    mismatch_rows = sum(1 for r in ledger
                        if r["validity_match"] != "match")
    pack_validity = _pack_validity(step_counts) or {}
    alias_omitted_rows = sum(
        1 for r in ledger if r["validity_match"] == "alias_steps_omitted")
    if step_counts:
        proof = (
            "history_validity reconstructed_verified+verified = %d+%d; "
            "pack = %d+%d (%s). The %d raw steps under the %d alias "
            "spellings are all unverified; %d of them are duplicate dates "
            "already present under the history spelling, leaving %d "
            "alias-only merged steps on %d validity rows. history_validity "
            "unverified %d + alias %d = %d; pack unverified %d (%s). %d "
            "valid rows - %d duplicate dates = %d merged steps = %d validity "
            "steps + %d (%s)."
            % (hv_factor_reconstructed, hv_factor_verified,
               pack_validity.get("reconstructed_verified", 0),
               pack_validity.get("verified", 0),
               "equal" if (hv_factor_reconstructed
                           == pack_validity.get("reconstructed_verified", 0)
                           and hv_factor_verified
                           == pack_validity.get("verified", 0)) else "DIFFERS",
               alias_raw_steps, len(multi_keys), duplicate_dates_total,
               alias_raw_steps - duplicate_dates_total, alias_omitted_rows,
               hv_factor_unverified, alias_raw_steps,
               hv_factor_unverified + alias_raw_steps,
               pack_validity.get("unverified", 0),
               "equal" if (hv_factor_unverified + alias_raw_steps
                           == pack_validity.get("unverified", 0))
               else "DIFFERS",
               valid_raw, duplicate_dates_total, factor_steps_all,
               hv_factor_steps, delta_total,
               "equal" if factor_steps_all == hv_factor_steps + delta_total
               else "DIFFERS"))
    else:
        proof = ("%d valid rows - %d duplicate dates = %d merged steps = %d "
                 "history_validity steps + %d."
                 % (valid_raw, duplicate_dates_total, factor_steps_all,
                    hv_factor_steps, delta_total))

    stale_counts = _counts(ledger, "stale_status")
    identity_counts = _counts(ledger, "identity_status")
    instrument_counts = _counts(ledger, "instrument_status")
    method_counts = _counts(ledger, "verification_method")
    validity_match_counts = _counts(ledger, "validity_match")
    stale = {
        "latest_session": latest,
        "trading_sessions": len(calendar),
        "fresh": stale_counts.get("fresh", 0),
        "recent": stale_counts.get("recent", 0),
        "stale": stale_counts.get("stale", 0),
        "halted": stale_counts.get("halted", 0),
        "instrument_state_coverage": sum(
            1 for r in ledger if r["instrument_status"]),
        "state_allowed_but_not_fresh": sum(
            1 for r in ledger if "مجاز" in r["instrument_status"]
            and r["stale_status"] in ("recent", "stale")),
        "fresh_over_state": sum(
            1 for r in ledger if r["stale_basis"] == "calendar_over_state"),
        "no_state": sum(1 for r in ledger if not r["instrument_status"]),
        "state_source": "instrument_state latest c_etaval_title; the boards "
                        "table carries only the board number and "
                        "board_hist_v has no status column, so neither can "
                        "distinguish a halt",
        "state_uncovered": sum(
            1 for r in ledger if not r["instrument_status"]),
        "halted_by_title": {
            "توقف": sum(1 for r in ledger if r["stale_status"] == "halted"
                        and "توقف" in r["instrument_status"]),
            "ممنوع": sum(1 for r in ledger if r["stale_status"] == "halted"
                         and "ممنوع" in r["instrument_status"]),
            "معلق": sum(1 for r in ledger if r["stale_status"] == "halted"
                        and "معلق" in r["instrument_status"]),
        },
        "recent_sessions_threshold": RECENT_SESSIONS,
    }
    identity = {
        "resolved_instruments": identity_counts.get(
            "resolved_instruments", 0),
        "resolved_instruments_ambiguous": identity_counts.get(
            "resolved_instruments_ambiguous", 0),
        "resolved_capture_plan": identity_counts.get(
            "resolved_capture_plan", 0),
        "unresolved_no_instruments": identity_counts.get(
            "unresolved_no_instruments", 0),
        "isin_present": sum(1 for r in ledger if r["isin"]),
        "ambiguous_rows": sum(1 for r in ledger
                              if int(r["instrument_candidates"]) > 1),
        "empty_keys": sum(1 for r in ledger if not r["key"]),
        "duplicate_instrument_keys_total": len(duplicate_keys),
        "duplicate_instrument_keys_in_history": len(duplicate_in_history),
        "duplicate_instrument_keys": [
            {"key": k,
             "candidates": int(candidates.get(k, 0)),
             "in_history": k in history_keys}
            for k in duplicate_keys],
        "asset_map_ambiguous_keys": sorted(set(asset_ambiguous)),
    }
    asset_coverage = {
        "with_asset_id": sum(1 for r in ledger if r["asset_id"]),
        "without_asset_id": sum(1 for r in ledger if not r["asset_id"]),
        "with_steps_with_asset_id": sum(
            1 for r in with_steps if r["asset_id"]),
        "with_steps_without_asset_id": sum(
            1 for r in with_steps if not r["asset_id"]),
        "no_steps_with_asset_id": sum(
            1 for r in no_steps if r["asset_id"]),
        "no_instruments_with_asset_id": sum(
            1 for r in unresolved if r["asset_id"]),
        "asset_map_entries": len(asset_map),
        "capture_plan": {
            "asset_map_symbols": capture_counts.get("asset_map_symbols"),
            "mapped": capture_counts.get("mapped"),
            "unmapped": capture_counts.get("unmapped"),
            "pack_unverified": capture_counts.get("pack_unverified"),
            "pack_symbols_unverified": capture_counts.get(
                "pack_symbols_unverified"),
            "pack_steps_unverified": capture_counts.get(
                "pack_steps_unverified"),
        },
    }
    event_coverage = {
        "pack": len(with_steps),
        "none": len(no_steps),
        "official_o1_symbols": sum(1 for r in ledger
                                   if int(r["official_o1"]) > 0),
        "official_o2_symbols": sum(1 for r in ledger
                                   if int(r["official_o2"]) > 0),
        "official_o1_rows": sum(int(r["official_o1"]) for r in ledger),
        "official_o2_rows": sum(int(r["official_o2"]) for r in ledger),
        "official_o1_rows_all": official_totals["o1"],
        "official_o2_rows_all": official_totals["o2"],
        "official_o1_rows_without_history": (
            official_totals["o1"]
            - sum(int(r["official_o1"]) for r in ledger)),
        "official_o2_rows_without_history": (
            official_totals["o2"]
            - sum(int(r["official_o2"]) for r in ledger)),
        "official_o1_in_range_symbols": sum(
            1 for r in ledger if int(r["official_o1_in_range"]) > 0),
        "official_o1_in_range_events": sum(
            int(r["official_o1_in_range"]) for r in ledger),
        "official_o1_material_events": sum(
            int(r["official_o1_material"]) for r in ledger),
        "no_step_symbols_with_official_in_range": sum(
            1 for r in no_steps if int(r["official_o1_in_range"]) > 0),
        "no_step_official_in_range_events": sum(
            int(r["official_o1_in_range"]) for r in no_steps),
        "step_symbols_with_official_rows": sum(
            1 for r in with_steps if int(r["official_o1"]) > 0),
        "official_absence_proof": "none",
        "rule": "O1/O2 rows are positive witnesses only; no ingest-complete "
                "proof exists in this round, so their absence is never used "
                "as proof of no event.",
    }
    covered_raw = sum(1 for s in raw_step_symbols if key(s) in reference)
    covered_keys = sum(1 for k in raw_step_keys if k in reference)
    coverage_pct_raw = (round(100.0 * covered_raw / len(raw_step_symbols), 1)
                        if raw_step_symbols else 0.0)
    reference_summary = {
        "index_symbols": len(reference),
        "index_symbols_in_history": sum(
            1 for k in reference if k in history_keys),
        "pack_symbols_raw": len(raw_step_symbols),
        "pack_symbols_keys": len(raw_step_keys),
        "pack_symbols_covered_raw": covered_raw,
        "pack_symbols_covered_keys": covered_keys,
        "coverage_pct_raw": coverage_pct_raw,
        "full": sum(1 for r in ledger if r["ref_coverage"] == "full"),
        "partial": sum(1 for r in ledger if r["ref_coverage"] == "partial"),
        "none": sum(1 for r in ledger if r["ref_coverage"] == "none"),
        "with_steps": sum(1 for r in with_steps
                          if r["ref_coverage"] != "none"),
        "no_steps_full": sum(1 for r in no_steps
                             if r["ref_coverage"] == "full"),
        "no_steps_partial": sum(1 for r in no_steps
                                if r["ref_coverage"] == "partial"),
        "verified_no_applicable_event": by_final.get(
            "VERIFIED_NO_APPLICABLE_EVENT", 0),
        "coverage_note": (
            "%d of %d raw pack spellings (%.1f%%) and %d of %d normalised "
            "pack keys carry a reference index in this run; %d of %d history "
            "symbols do too. %d step-bearing and %d no-step symbols are "
            "covered."
            % (covered_raw,
               len(raw_step_symbols),
               coverage_pct_raw,
               covered_keys,
               len(raw_step_keys),
               sum(1 for k in reference if k in history_keys),
               len(history_keys),
               sum(1 for r in with_steps if r["ref_coverage"] != "none"),
               sum(1 for r in no_steps if r["ref_coverage"] == "full"))),
    }
    factor_totals = {
        "step_rows_valid": step_rows_total,
        "step_rows_invalid": invalid_total,
        "step_rows_total": step_rows_total + invalid_total,
        "factor_steps": factor_steps_total,
        "verified": factor_verified_total,
        "reconstructed": factor_reconstructed_total,
        "unverified": factor_unverified_total,
        "conflict": factor_conflict_total,
        "partial": factor_partial_total,
        "insufficient": factor_insufficient_total,
        "blocked": factor_blocked_total,
        "alias_duplicate_dates": duplicate_dates_total,
        "alias_ratio_conflicts": alias_ratio_conflict_total,
        "alias_ratio_partials": alias_ratio_partial_total,
        "alias_only_steps": alias_only_total,
        "alias_symbols": sum(1 for r in ledger
                             if int(r["alias_only_steps"]) > 0),
        "consistency": "step_rows_valid - alias_duplicate_dates == "
                       "factor_steps",
        "pack_validity": _pack_validity(step_counts),
    }
    validity_reconciliation = {
        "rows": len(ledger),
        "by_status": validity_by_status,
        "sum_factor_steps": hv_factor_steps,
        "sum_factor_verified": hv_factor_verified,
        "sum_factor_reconstructed": hv_factor_reconstructed,
        "sum_factor_unverified": hv_factor_unverified,
        "rows_with_factor_unverified_positive": hv_unverified_positive,
        "unverified_rows": len(unverified),
        "unverified_rows_with_pack_steps": sum(
            1 for r in unverified if int(r["factor_steps"]) > 0),
        "unverified_rows_with_any_step_row": sum(
            1 for r in unverified
            if int(r["step_rows"]) + int(r["factor_invalid_dropped"]) > 0),
        "unverified_rows_with_reference": sum(
            1 for r in unverified if r["ref_coverage"] != "none"),
        "unverified_rows_with_asset_id": sum(
            1 for r in unverified if r["asset_id"]),
        "unverified_rows_identity_resolved": sum(
            1 for r in unverified if r["identity_status"]
            != "unresolved_no_instruments"),
        "unverified_rows_no_instruments": sum(
            1 for r in unverified if r["identity_status"]
            == "unresolved_no_instruments"),
        "pack_valid_steps": valid_raw,
        "pack_invalid_steps": invalid_raw,
        "pack_symbols_raw": len(raw_step_symbols),
        "pack_symbols_keys": len(raw_step_keys),
        "pack_symbols_unverified": capture_counts.get(
            "pack_symbols_unverified"),
        "pack_unverified_keys": capture_counts.get("pack_unverified"),
        "pack_steps_unverified": capture_counts.get("pack_steps_unverified"),
        "alias_spelling_keys": len(multi_keys),
        "alias_spelling_raw_symbols": 2 * len(multi_keys),
        "alias_raw_steps": alias_raw_steps,
        "alias_duplicate_dates": duplicate_dates_total,
        "alias_only_merged_steps": alias_only_total,
        "merged_factor_steps": factor_steps_all,
        "delta_merged_minus_validity": delta_total,
        "rows_factor_steps_match": sum(
            1 for r in ledger if r["validity_match"] == "match"),
        "rows_factor_steps_mismatch": mismatch_rows,
        "rows_alias_steps_omitted": sum(
            1 for r in ledger
            if r["validity_match"] == "alias_steps_omitted"),
        "rows_validity_missing": sum(
            1 for r in ledger if r["validity_match"] == "missing"),
        "proof": proof,
    }
    no_instruments = {
        "symbols": len(unresolved),
        "by_final_status": _status_counts(unresolved),
        "with_pack_steps": sum(1 for r in unresolved
                               if int(r["factor_steps"]) > 0),
        "with_reference": sum(1 for r in unresolved
                              if r["ref_coverage"] != "none"),
        "with_asset_id": sum(1 for r in unresolved if r["asset_id"]),
        "with_isin": sum(1 for r in unresolved if r["isin"]),
        "no_pack_no_reference": sum(
            1 for r in unresolved if not int(r["factor_steps"])
            and r["ref_coverage"] == "none"),
    }
    data_shape = {
        "first_date_min": min(r["first_date"] for r in ledger),
        "last_date_max": max(r["last_date"] for r in ledger),
        "price_rows": sum(int(r["rows"]) for r in ledger),
        "source_rows": dict(sorted(source_counts.items())),
        "invalid_ohlc_symbols": sum(
            1 for r in ledger if r["raw_ohlc_valid"] == "invalid"),
        "anomaly_rows": sum(int(r["anomalies"]) for r in ledger),
        "gap_symbols": sum(1 for r in ledger if int(r["gaps"]) > 0),
        "gap_sessions": sum(int(r["gaps"]) for r in ledger),
        "duplicate_date_rows": sum(
            int(r["duplicate_dates"]) for r in ledger),
        "single_candle_symbols": sum(
            1 for r in ledger if int(r["trading_sessions"]) == 1),
    }
    payload = {
        "schema": 1,
        "stage": "stage05_symbol_ledger",
        "rows": len(ledger),
        "by_final_status": by_final,
        "by_stale_status": stale_counts,
        "by_instrument_status": instrument_counts,
        "by_identity_status": identity_counts,
        "by_verification_method": method_counts,
        "by_validity_match": validity_match_counts,
        "status_x_stale": _cross(ledger, "final_status", "stale_status"),
        "halted_by_instrument_status": _counts(
            [r for r in ledger if r["stale_status"] == "halted"],
            "instrument_status"),
        "stale": stale,
        "identity": identity,
        "asset_coverage": asset_coverage,
        "event_coverage": event_coverage,
        "reference": reference_summary,
        "factor_totals": factor_totals,
        "validity_reconciliation": validity_reconciliation,
        "no_instruments": no_instruments,
        "data_shape": data_shape,
        "blockers": _blocker_counts(ledger),
        "inputs": {
            "db": _rel(db),
            "steps": _rel(steps_path),
            "references": [_rel(p) for p in references],
            "asset_map": _rel(asset_map_path) if asset_map_path else "",
            "capture_plan": _rel(capture_plan_path)
                            if capture_plan_path else "",
            "step_counts": _rel(step_counts_path)
                           if step_counts_path else "",
            "rules": _rel(rules_path),
            "symbols": len(ledger),
            "trading_sessions": len(calendar),
            "latest_session": latest,
            "step_rows": len(step_rows),
            "step_rows_valid": valid_raw,
            "step_rows_invalid": invalid_raw,
            "step_symbols_raw": len(raw_step_symbols),
            "step_symbols_keys": len(raw_step_keys),
            "asset_map_entries": len(asset_map),
            "reference_index_symbols": len(reference),
        },
        "notes": [
            "Join key is dev.symbol_identity.key; the raw symbol and ISIN are "
            "carried in every row. %d Persian/Arabic spelling pairs share a "
            "key; the %d duplicate effective dates they produce are collapsed "
            "with the history symbol's own spelling as the primary witness."
            % (len(multi_keys), duplicate_dates_total),
            "%d symbols have no instruments row. They stay in the ledger as "
            "unresolved_no_instruments and INSUFFICIENT_EVIDENCE with "
            "SYMBOL_IDENTITY_MISMATCH in the blocker; they are not dropped. "
            "The %d duplicate instruments keys are reported; %d occur in the "
            "history universe and resolve through B1's ISIN-first choice."
            % (len(unresolved), len(duplicate_keys),
               len(duplicate_in_history)),
            "Official O1/O2 rows are positive witnesses only. No "
            "ingest-completeness proof exists in this round, so O1=0/O2=0 is "
            "never used as proof of no event. %d no-step symbols carry %d "
            "in-range O1 events and are flagged OFFICIAL_EVENT_WITHOUT_STEP, "
            "not promoted or failed."
            % (event_coverage["no_step_symbols_with_official_in_range"],
               event_coverage["no_step_official_in_range_events"]),
            "VERIFIED_NO_APPLICABLE_EVENT requires a resolved identity and a "
            "full R1 type0/type7 window with no factor changes. %d of %d raw "
            "pack spellings (%d of %d normalised keys) carry a reference "
            "index and %d no-step symbols have a full window, so the count "
            "is %d."
            % (reference_summary["pack_symbols_covered_raw"],
               len(raw_step_symbols),
               reference_summary["pack_symbols_covered_keys"],
               len(raw_step_keys), reference_summary["no_steps_full"],
               reference_summary["verified_no_applicable_event"]),
            "%d history_validity rows are unverified with factor_steps=0. "
            "None carries a pack step; the zero is accurate as a step count "
            "but is not a no-event claim. The raw-symbol validity table "
            "cannot see the %d alias spellings: %d raw alias steps (%d "
            "duplicate dates + %d applicable) sit outside its count, so its "
            "unverified total is %d vs the pack's %d."
            % (len(unverified), len(multi_keys), alias_raw_steps,
               duplicate_dates_total, alias_only_total, hv_factor_unverified,
               capture_counts.get("pack_steps_unverified") or 0),
            "Halted means the latest instrument_state title contains "
            "توقف/معلق/ممنوع and the last bar is older than the latest "
            "session. A bar on the latest session wins over an outdated "
            "state. Up to %d sessions behind is recent; more is stale."
            % RECENT_SESSIONS,
            "BLOCKED_SOURCE is %d: no step carried it and identity failure is "
            "classified as SYMBOL_IDENTITY_MISMATCH / INSUFFICIENT_EVIDENCE "
            "per the design's identity rule."
            % by_final.get("BLOCKED_SOURCE", 0),
            "The six final statuses are read verbatim from "
            "dev/phase49_status_rules.json symbol_status_precedence.",
        ],
    }
    os.makedirs(os.path.dirname(os.path.abspath(counts_path)), exist_ok=True)
    with open(counts_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    if manifest_path:
        inputs = [_rel(db), _rel(steps_path)] + [_rel(p) for p in references]
        if asset_map_path:
            inputs.append(_rel(asset_map_path))
        if capture_plan_path:
            inputs.append(_rel(capture_plan_path))
        if step_counts_path:
            inputs.append(_rel(step_counts_path))
        inputs.append(_rel(rules_path))
        PM.write_manifest(
            "stage05_symbol_ledger", inputs,
            [_rel(out), _rel(counts_path)],
            {"rows": len(ledger), **by_final}, manifest_path)
    return ledger, payload


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--steps", required=True)
    ap.add_argument("--reference", action="append", default=[])
    ap.add_argument("--asset-map", default="")
    ap.add_argument("--capture-plan", default="")
    ap.add_argument("--step-counts", default="")
    ap.add_argument("--rules", default=DEFAULT_RULES)
    ap.add_argument("--out", required=True)
    ap.add_argument("--counts", default=DEFAULT_COUNTS)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST,
                    help="stage manifest path ('' disables)")
    ap.add_argument("--expect-symbols", type=int, default=0,
                    help="fail when the price_history symbol count differs")
    args = ap.parse_args(argv)
    os.chdir(ROOT)
    try:
        ledger, payload = build(
            args.db, args.steps, args.reference, args.asset_map, args.out,
            args.counts, args.manifest, args.capture_plan, args.step_counts,
            args.rules, args.expect_symbols)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print("SYMBOL LEDGER FAIL: %s" % exc, file=sys.stderr)
        return 2
    print("symbol ledger: %d rows -> %s" % (len(ledger), args.out))
    print(json.dumps({
        "final": payload["by_final_status"],
        "stale": payload["by_stale_status"],
        "identity": payload["by_identity_status"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
