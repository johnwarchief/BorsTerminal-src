#!/usr/bin/env python3
"""Stage 03 - classify every adjustment step into evidence statuses.

One row per pack step (8,280 valid rows) plus the pack manifest's
``dropped_steps`` (28 invalid rows). A row is classified by the evidence that
actually exists today:

* ``O1`` - a TSETMC flow event row (``price_adjust_events`` /
  ``share_change_events``) with the same (normalised) symbol and a date within
  the frozen step-date shift window (``STEP_DATE_SHIFT_MAX_DAYS`` in the rules
  file, 1-3 / 4-5 day tiers per spec §7.3).
* ``O2`` - a CODAL notice whose corporate-action title sits within +-10 days.
  O2 only corroborates existence/date; it never changes a status by itself.
* ``R1`` - the B3 reference factor index (Rahavard type0/type7), joined on
  ``dev.symbol_identity.key`` and compared with the frozen 0.1% rule.
* ``I1`` - the internal reconstruction audit (formula inputs, provenance,
  cumulative chain, duplicate dates). I1 is not independent evidence.

Conventions fixed here (and why)
--------------------------------
* The B3 index is keyed by the *normalised* symbol and its ``factor_changes``
  carry the cumulative level in ``factor`` plus the step ratio in
  ``ratio_change`` (``factor_t / factor_{t-1}``). The step ratio used by the
  pack is the inverse direction (``1 / ratio_change``), exactly as
  ``stageC_reference_parity.py`` and ``stageD_merge_reference.py`` define it.
  Comparing a step ratio to the cumulative ``factor`` would turn almost every
  captured step into a false ``CONFLICT_RATIO``.
* ``cum_factor_after`` grows towards 1.0 at the newest step (it is the product
  of the ratios of the *later* steps), so the audit checks
  ``cum(prev) == cum(next) * ratio(next)`` instead of assuming a decreasing
  chain. The brief's "cum-factor-increase" test was inverted.
* Duplicate detection uses ``DEDUPE_RATIO_TOL`` from the rules file (1%), not
  ``FACTOR_EXACT`` (0.1%): the two spellings of one event are a duplicate only
  when their ratios differ by more than the frozen dedupe tolerance.
* The final status is the highest one in the rules file's
  ``step_status_precedence`` order among the statuses the evidence supports, so
  ``CONFLICT_RATIO`` outranks ``CONFLICT_DUPLICATE`` exactly as the spec's
  status table does. The precedence list is an order, never a membership set.
* The CODAL ``publish_date`` column is unusable as a letter date (13,788 rows
  share one page date), but ``sent_date`` is the real Jalali letter date; it is
  converted with the frozen ``codal_periods.j2g_date``. Two rows have no
  ``sent_date`` and are skipped.
* A shifted O1/R1 witness is only evidence when its ratio also lands within
  ``FACTOR_MATERIAL``; otherwise it is a different nearby event, not a
  conflict. Only an exact-date mismatch is reported as ``CONFLICT_RATIO``.
* ``dropped_steps`` rows are normalised (``date`` -> ``effective_date``,
  ``our_ratio`` -> ``ratio``) so the ledger has one uniform schema.

CLI:
    python _audit/phase49-full-verification/stage03_step_ledger.py \\
        --db _audit/phase49-finalization/seed/market.db \\
        --pack data/ra365_corrections/ra365-phase49-rebuild-full-v2 \\
        --reference _audit/phase49-full-verification/captures/reference-index-30.json \\
        --reference _audit/phase49-full-verification/captures/reference-index-7.json \\
        --rules dev/phase49_status_rules.json \\
        --out _audit/phase49-full-verification/ledgers/ADJUSTMENT-EVIDENCE-LEDGER.csv

The CSV belongs in the gitignored ``ledgers/`` area. The tracked outputs are
the small count summary and the stage manifest under ``evidence/``; no raw
factor series or bars are written there. Stdlib only, DB opened read-only.
"""
import argparse
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
if os.path.join(ROOT, "dev") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "dev"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from symbol_identity import key  # noqa: E402
from codal_periods import j2g_date  # noqa: E402
import phase49_manifest as PM  # noqa: E402

NOTICE_DAYS = 10
CORP_ACTION_WORDS = ("افزایش سرمایه", "سود نقدی", "حق تقدم", "تعدیل", "درصد")

FIELDS = ["symbol", "ins_code", "asset_id", "effective_date", "action", "ratio",
          "prod_ratio", "ref_ratio", "cum_factor_after", "provenance", "method",
          "evidence_tier", "evidence_ref", "comparison_result",
          "discrepancy_cause", "final_status", "risk_score", "notes"]

DEFAULT_COUNTS = os.path.join(HERE, "evidence", "step-ledger-counts.json")
DEFAULT_MANIFEST = os.path.join(HERE, "evidence",
                                "stage03_step_ledger.manifest.json")


def _d(s):
    """ISO date; ``None`` for anything that is not a real calendar day."""
    try:
        return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def _num(s):
    return int(str(s)[:8])


def _ratio(v):
    try:
        r = float(v)
    except (TypeError, ValueError):
        return None
    return r if math.isfinite(r) else None


def _iso_even(d_even):
    """``20200102`` -> ``2020-01-02``; ``None`` when the integer is invalid."""
    try:
        n = _num(d_even)
    except (TypeError, ValueError):
        return None
    y, m, d = n // 10000, (n // 100) % 100, n % 100
    out = "%04d-%02d-%02d" % (y, m, d)
    return out if _d(out) else None


def _connect(db):
    return sqlite3.connect("file:%s?mode=ro" % str(db).replace("\\", "/"),
                           uri=True)


def _rel(path):
    """Repo-relative POSIX path for evidence manifests; absolute outside."""
    try:
        rel = os.path.relpath(os.path.abspath(path), ROOT)
    except ValueError:  # different drive on Windows
        rel = os.path.abspath(path)
    return rel.replace("\\", "/")


class OfficialIndex(dict):
    """Exact-date O1 index plus a per-symbol list for the shift window."""

    def __init__(self):
        super().__init__()
        self.by_symbol = collections.defaultdict(list)

    def add(self, sym, ds, ev):
        self.setdefault((sym, ds), []).append(ev)
        self.by_symbol[sym].append((ds, ev))

    def near(self, sym, ds, days):
        """``[(delta_days, event)]`` inside the frozen shift window."""
        d0 = _d(ds)
        if d0 is None:
            return []
        out = []
        for eds, ev in self.by_symbol.get(sym, ()):
            d1 = _d(eds)
            if d1 is None:
                continue
            delta = abs((d1 - d0).days)
            if delta <= days:
                out.append((delta, ev))
        out.sort(key=lambda x: (x[0], x[1].get("ratio") or 0))
        return out


def load_steps(pack):
    """Valid pack steps, then the manifest's invalid/dropped rows."""
    out = []
    with open(os.path.join(pack, "factors.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    with open(os.path.join(pack, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    counts = manifest.get("counts") or {}
    if counts.get("steps") not in (None, len(out)):
        raise ValueError("manifest counts.steps=%s but factors.jsonl has %d"
                         % (counts.get("steps"), len(out)))
    dropped = manifest.get("dropped_steps", [])
    if counts.get("invalid_dropped_steps") not in (None, len(dropped)):
        raise ValueError("manifest invalid_dropped_steps=%s but list has %d"
                         % (counts.get("invalid_dropped_steps"), len(dropped)))
    for raw in dropped:
        r = dict(raw)
        r["validity"] = "invalid_dropped"
        r["effective_date"] = r.get("date")
        r["ratio"] = r.get("our_ratio")
        r["action"] = r.get("decision") or "invalid_dropped"
        r["prov_kind"] = "manifest"
        r["reason"] = ("%s; our_ratio=%s; ref_ratio=%s"
                       % (r.get("decision"), r.get("our_ratio"),
                          r.get("ref_ratio")))
        out.append(r)
    return out


def load_official(db):
    """O1 rows keyed ``(normalised symbol, ISO date)``."""
    out = OfficialIndex()
    con = _connect(db)
    try:
        for sym, d_even, ratio in con.execute(
                "SELECT symbol,d_even,ratio FROM price_adjust_events"):
            ds, r = _iso_even(d_even), _ratio(ratio)
            if not ds or r is None or r <= 0:
                continue
            out.add(key(sym), ds, {"ratio": r, "tier": "O1",
                                   "source": "price_adjust_events",
                                   "date": ds})
        for sym, d_even, old, new in con.execute(
                "SELECT symbol,d_even,shares_old,shares_new "
                "FROM share_change_events"):
            ds, old, new = _iso_even(d_even), _ratio(old), _ratio(new)
            if not ds or not old or not new or old <= 0 or new <= 0:
                continue
            out.add(key(sym), ds, {"ratio": old / new, "tier": "O1",
                                   "source": "share_change_events",
                                   "date": ds})
    finally:
        con.close()
    return out


def load_notices(db):
    """O2 notices keyed by normalised symbol; dates from ``sent_date``."""
    out = collections.defaultdict(list)
    con = _connect(db)
    try:
        for sym, sent, published, title, url in con.execute(
                "SELECT symbol,sent_date,publish_date,title,url "
                "FROM codal_notices"):
            g = j2g_date(sent) or j2g_date(published)
            if not g:
                continue
            out[key(sym)].append({"date": g[:10], "title": title, "url": url,
                                  "tier": "O2"})
    finally:
        con.close()
    for items in out.values():
        items.sort(key=lambda n: n["date"])
    return dict(out)


def notice_near(notices, sym, ds, days=NOTICE_DAYS):
    """Nearest corporate-action notice within ``days``; existence only."""
    d0 = _d(ds)
    if d0 is None or not notices:
        return None
    best = None
    for n in notices.get(key(sym), ()):
        d1 = _d(n.get("date"))
        if d1 is None:
            continue
        delta = abs((d1 - d0).days)
        if delta > days:
            continue
        if not any(w in str(n.get("title") or "") for w in CORP_ACTION_WORDS):
            continue
        if best is None or delta < best[0]:
            best = (delta, n)
    return best[1] if best else None


def _ref_step_ratio(change):
    """Reference step ratio in the pack's direction.

    The frozen index stores ``ratio_change = factor_t / factor_{t-1}``; the
    price ratio is its inverse. A change entry without ``ratio_change`` (the
    unit-test fixture) falls back to its factor.
    """
    rc = _ratio(change.get("ratio_change"))
    if rc is not None and rc > 0:
        return 1.0 / rc
    f = _ratio(change.get("factor"))
    if f is not None and f > 0:
        return f
    return None


def _status_for_comparison(err, exact, material):
    if err <= exact:
        return "MATCH"
    if err <= material:
        return "PARTIAL"
    return "MISMATCH"


def _pick_witness(cands, ratio, exact, material):
    """Best witness from ``[(delta_days, item, witness_ratio)]``.

    A matching witness outranks a conflicting one, and a shifted mismatch is
    dropped entirely: an event a few days away with another ratio is a
    different event, not proof against this step. Only an exact-date mismatch
    remains as a conflict.
    """
    scored = []
    for delta, item, wr in cands:
        if wr is None or wr <= 0:
            continue
        err = abs(wr / ratio - 1.0)
        outcome = _status_for_comparison(err, exact, material)
        if outcome == "MISMATCH" and delta > 0:
            continue
        rank = {"MATCH": 0, "PARTIAL": 1, "MISMATCH": 2}[outcome]
        scored.append((rank, delta, err, item, outcome))
    if not scored:
        return None
    scored.sort(key=lambda x: (x[0], x[1], x[2]))
    _, delta, _, item, outcome = scored[0]
    return delta, item, outcome


def _audit_reasons(step):
    """Inline provenance/contract checks used when ``audit`` is not supplied."""
    ratio = _ratio(step.get("ratio"))
    reasons = []
    if ratio is None or not (0 < ratio <= 1):
        reasons.append("ratio-out-of-range")
    if step.get("cum_factor_after") in (None, ""):
        reasons.append("missing-cum-factor")
    if not (step.get("method") and step.get("fields_used")
            and step.get("prov_kind")):
        reasons.append("missing-provenance")
    return reasons


def audit_reconstruction(steps, tol=1e-3, dup_tol=1e-2):
    """Chain/provenance audit keyed ``(raw symbol, ISO date)``.

    ``cum_factor_after`` is the product of the ratios of the later steps, so
    for consecutive steps ``a`` (older) and ``b`` (newer):
    ``cum(a) == cum(b) * ratio(b)``. The newest step must sit at 1.0.
    Invalid/dropped rows are not part of the valid chain.

    ``tol`` and ``dup_tol`` default to the frozen §7.3 values (``FACTOR_EXACT``
    and ``DEDUPE_RATIO_TOL``); :func:`build` always passes the rules-file
    values, so the defaults only serve direct callers.

    The chain is audited per **raw** symbol: the pack carries the same
    instrument under Arabic and Persian kaf spellings (e.g. ``تاپيكو`` /
    ``تاپیکو``), and each spelling has its own complete cumulative chain.
    Duplicate detection is done once per normalised key + date; two spellings
    with a ratio difference above ``dup_tol`` for the same day are a duplicate
    event, and both rows carry that reason.
    """
    by_symbol = collections.defaultdict(list)
    groups = collections.defaultdict(list)
    for s in steps:
        if s.get("validity") == "invalid_dropped":
            continue
        raw = str(s.get("symbol"))
        ds = str(s.get("effective_date"))[:10]
        by_symbol[raw].append(s)
        groups[(key(raw), ds)].append(s)
    audit = {}
    for raw, rows in by_symbol.items():
        rows.sort(key=lambda s: str(s.get("effective_date")))
        for i, s in enumerate(rows):
            ds = str(s.get("effective_date"))[:10]
            reasons = []
            ratio = _ratio(s.get("ratio"))
            cum = _ratio(s.get("cum_factor_after"))
            if ratio is None or not (0 < ratio <= 1):
                reasons.append("ratio-out-of-range")
            if cum is None:
                reasons.append("missing-cum-factor")
            if not (s.get("method") and s.get("fields_used")
                    and s.get("prov_kind")):
                reasons.append("missing-provenance")
            if i + 1 < len(rows):
                nxt = rows[i + 1]
                nr, nc = _ratio(nxt.get("ratio")), _ratio(
                    nxt.get("cum_factor_after"))
                if ratio is not None and cum is not None and nr and nc:
                    expected = nc * nr
                    if abs(cum / expected - 1.0) > tol:
                        reasons.append("cum-factor-chain")
            elif cum is not None and abs(cum - 1.0) > 1e-9:
                reasons.append("cum-factor-terminal")
            audit[(raw, ds)] = {"ok": not reasons, "notes": reasons}

    for (sym, ds), group in groups.items():
        if len(group) < 2:
            continue
        ratios = [r for r in (_ratio(s.get("ratio")) for s in group)
                  if r is not None and r > 0]
        inconsistent = any(
            abs(a / b - 1.0) > dup_tol
            for i, a in enumerate(ratios) for b in ratios[i + 1:])
        if not inconsistent:
            continue
        spellings = {str(s.get("symbol")) for s in group}
        for s in group:
            entry = audit[(str(s.get("symbol")), ds)]
            if "duplicate-date" not in entry["notes"]:
                entry["notes"].append("duplicate-date")
            if len(spellings) > 1 and "symbol-identity" not in entry["notes"]:
                entry["notes"].append("symbol-identity")
            entry["ok"] = False
    return audit


def _first_by_precedence(candidates, precedence):
    """Highest-priority status among ``candidates`` (real order, not a set).

    ``precedence`` is ``step_status_precedence`` from the rules file: an
    ordered list every status must appear in. A candidate outside the frozen
    list is a bug, not a fallback, so it raises.
    """
    order = {}
    for i, name in enumerate(precedence):
        order.setdefault(name, i)
    unknown = [s for s in candidates if s not in order]
    if unknown:
        raise ValueError("status %r is not in the frozen step_status_precedence"
                         % unknown[0])
    return min(candidates, key=lambda s: order[s])


def classify(step, official, reference, rules, audit=None, notices=None):
    """Classify one step; returns the ledger fields added by stage 03.

    ``official`` is the exact-date O1 map from :func:`load_official` (a plain
    dict is accepted, which keeps the unit test independent of sqlite).
    ``reference`` is the B3 index keyed by normalised symbol.
    """
    t = rules["tolerances"]
    exact, material = t["FACTOR_EXACT"], t["FACTOR_MATERIAL"]
    shift_days = t["STEP_DATE_SHIFT_MAX_DAYS"]
    precedence = rules["step_status_precedence"]
    sym = key(step.get("symbol"))
    ds = str(step.get("effective_date"))[:10]
    ratio = _ratio(step.get("ratio"))
    if ratio is not None and ratio <= 0:
        ratio = None
    dropped = step.get("validity") == "invalid_dropped"
    reasons = [] if dropped else (
        list((audit or {}).get("notes") or []) if audit is not None else [])

    tiers, refs = [], []
    notes = [str(step.get("reason") or "").strip()]

    # ---- O1: official TSETMC flow events ---------------------------------
    o1 = None            # MATCH / PARTIAL / MISMATCH
    o1_shift = None
    if ratio is not None:
        if hasattr(official, "near"):
            cands = [(delta, e, e.get("ratio"))
                     for delta, e in official.near(sym, ds, shift_days)]
        else:
            cands = [(0, e, e.get("ratio"))
                     for e in official.get((sym, ds), [])]
        picked = _pick_witness(cands, ratio, exact, material)
        if picked:
            o1_shift, best, o1 = picked
            tiers.append("O1")
            ref = "%s:%s" % (best.get("source", "official"),
                             best.get("date", ds))
            if o1_shift:
                ref += "@shift%dd" % o1_shift
                notes.append("O1 date shifted %dd; witness ratio %.12g"
                             % (o1_shift, best["ratio"]))
            refs.append(ref)
            if o1 == "MISMATCH":
                notes.append("O1 ratio %.12g vs step ratio %.12g"
                             % (best["ratio"], ratio))

    # ---- R1: reference factor index --------------------------------------
    r1 = None
    rec = reference.get(sym) or {}
    changes = rec.get("factor_changes") or []
    if changes and ratio is not None:
        cands = []
        d0 = _d(ds)
        for c in changes:
            cd = _d(c.get("date"))
            if cd is None or d0 is None:
                continue
            delta = abs((cd - d0).days)
            if delta <= shift_days:
                cands.append((delta, c, _ref_step_ratio(c)))
        picked = _pick_witness(cands, ratio, exact, material)
        if picked:
            ref_delta, ref, r1 = picked
            rr = _ref_step_ratio(ref)
            tiers.append("R1")
            refs.append("capture:%s" % ref.get("date"))
            if ref_delta:
                notes.append("R1 date shifted %dd; witness ratio %.12g"
                             % (ref_delta, rr))
            if r1 == "MISMATCH":
                notes.append("R1 ratio %.12g vs step ratio %.12g"
                             % (rr, ratio))

    # ---- O2: CODAL corroboration (existence/date only) -------------------
    n = notice_near(notices or {}, step.get("symbol"), ds)
    if n:
        tiers.append("O2")
        refs.append("codal:%s" % n.get("url"))

    # ---- status precedence ----------------------------------------------
    # Collect every status the evidence supports, then let the frozen
    # ``step_status_precedence`` list pick the strongest one. This is a real
    # order, not a membership test: CONFLICT_RATIO outranks CONFLICT_DUPLICATE,
    # so a duplicated spelling whose ratio also disagrees with a witness is
    # reported as the ratio conflict the spec's table names first.
    compare = "NO_EVIDENCE"
    cause = ""
    candidates = []
    causes = {}
    if o1 and r1:
        if o1 == "MATCH" and r1 == "MATCH":
            status, compare = "VERIFIED_MULTI_SOURCE", "MATCH"
        elif "MISMATCH" in (o1, r1):
            status, compare = "CONFLICT_RATIO", "MISMATCH"
            cause = ("SOURCE_MISMATCH" if "MATCH" in (o1, r1)
                     else "EVENT_RATIO_MISMATCH")
        elif o1 == "PARTIAL":
            status, compare = "PARTIAL_OFFICIAL", "PARTIAL"
        else:
            status, compare = "PARTIAL_REFERENCE", "PARTIAL"
        candidates.append(status)
        if cause:
            causes[status] = cause
    elif o1:
        compare = o1
        if o1 == "MATCH":
            status = "VERIFIED_OFFICIAL"
        elif o1 == "PARTIAL":
            status = "PARTIAL_OFFICIAL"
        else:
            status, cause = "CONFLICT_RATIO", "EVENT_RATIO_MISMATCH"
        candidates.append(status)
        if cause:
            causes[status] = cause
    elif r1:
        compare = r1
        if r1 == "MATCH":
            status = "VERIFIED_REFERENCE"
        elif r1 == "PARTIAL":
            status = "PARTIAL_REFERENCE"
        else:
            status, cause = "CONFLICT_RATIO", "EVENT_RATIO_MISMATCH"
        candidates.append(status)
        if cause:
            causes[status] = cause
    else:
        if audit is None and not dropped:
            reasons = _audit_reasons(step)
        ok = bool((audit or {}).get("ok")) if audit is not None else not reasons
        if ok:
            candidates.append("RECONSTRUCTED_AUDITED")
            compare = "NO_EVIDENCE"
        else:
            candidates.append("INSUFFICIENT_EVIDENCE")
            causes["INSUFFICIENT_EVIDENCE"] = "UNRESOLVED_SOURCE_GAP"
            compare = "NO_EVIDENCE"

    # A duplicate/chain defect is a hard conflict even when a witness agrees:
    # the row is still a second record of the same event or sits on a broken
    # cumulative chain. Both join the candidate list and the precedence order
    # decides against the witness status. Missing provenance alone never
    # overrides a witness.
    if not dropped:
        if "duplicate-date" in reasons:
            candidates.append("CONFLICT_DUPLICATE")
            causes["CONFLICT_DUPLICATE"] = (
                "SYMBOL_IDENTITY_MISMATCH" if "symbol-identity" in reasons
                else "INVALID_SOURCE_RECORD")
        if ("cum-factor-chain" in reasons
                or "cum-factor-terminal" in reasons):
            candidates.append("CONFLICT_CHAIN")
            causes["CONFLICT_CHAIN"] = "SOURCE_REVISION"
    status = _first_by_precedence(candidates, precedence)
    cause = causes.get(status, "")
    if not dropped:
        notes.append("audit:" + (",".join(reasons) if reasons else "pass"))

    if dropped:
        status = "INVALID_DROPPED"
        compare, cause = "NO_EVIDENCE", ""
        if r1 == "MATCH":
            notes.append("new R1 matches the dropped ratio; the manifest "
                         "drop predates the B3 reference index")
        base = "R1" if (reference.get(sym) and _d(ds)
                        and (rec.get("type0") or {}).get("first")
                        and rec["type0"]["first"] <= ds
                        and (rec.get("type0") or {}).get("last")
                        and ds <= rec["type0"]["last"]) else "I1"
        tiers.append(base)
        tiers.append("I1")
        refs.append("capture:no-event@%s" % ds if base == "R1"
                    else "manifest:dropped")

    if not tiers:
        tiers.append("I1")
    tier = "+".join(dict.fromkeys(tiers))
    if status in ("RECONSTRUCTED_AUDITED", "INSUFFICIENT_EVIDENCE",
                  "CONFLICT_CHAIN", "CONFLICT_DUPLICATE") and "I1" not in tiers:
        tier += "+I1"

    return {"final_status": status, "evidence_tier": tier,
            "evidence_ref": ";".join(r for r in refs if r),
            "comparison_result": compare, "discrepancy_cause": cause,
            "risk_score": round(abs(1.0 - ratio), 8) if ratio is not None
            else 1.0,
            "notes": " | ".join(x for x in notes if x),
            "_o1": o1 or "", "_r1": r1 or ""}


def _load_rules(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _validate_rules(rules):
    need = ("tolerances", "step_status_precedence", "evidence_tiers",
            "reconciliation_categories")
    missing = [k for k in need if k not in rules]
    if missing:
        raise ValueError("rules file missing: %s" % ", ".join(missing))
    tolerances = rules["tolerances"]
    for k in ("FACTOR_EXACT", "FACTOR_MATERIAL", "EXACT_EQ",
              "DEDUPE_RATIO_TOL", "STEP_DATE_SHIFT_MAX_DAYS",
              "STEP_DATE_SHIFT_TIERS"):
        if k not in tolerances:
            raise ValueError("rules tolerances missing %s" % k)
    shift_max = tolerances["STEP_DATE_SHIFT_MAX_DAYS"]
    if not isinstance(shift_max, int) or isinstance(shift_max, bool) \
            or shift_max <= 0:
        raise ValueError("STEP_DATE_SHIFT_MAX_DAYS must be a positive integer")
    tiers = tolerances["STEP_DATE_SHIFT_TIERS"]
    if not (isinstance(tiers, list) and tiers
            and all(isinstance(p, list) and len(p) == 2 for p in tiers)):
        raise ValueError("STEP_DATE_SHIFT_TIERS must be [start, end] pairs")
    if tiers[-1][-1] != shift_max:
        raise ValueError("STEP_DATE_SHIFT_TIERS does not end at "
                         "STEP_DATE_SHIFT_MAX_DAYS")
    precedence = rules["step_status_precedence"]
    if (not isinstance(precedence, list)
            or len(set(map(str, precedence))) != len(precedence)):
        raise ValueError("step_status_precedence must be a list of unique "
                         "statuses")
    return (precedence, set(rules["evidence_tiers"]),
            set(rules["reconciliation_categories"]))


def _merge_reference(paths):
    ref = {}
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        for k, v in data.items():
            k = key(k)
            old = ref.get(k)
            if old is not None and old.get("factor_changes") != v.get(
                    "factor_changes"):
                raise ValueError(
                    "reference indexes disagree for %s (%s)" % (k, p))
            ref[k] = v
    return ref


def build(db, pack, references, rules_path, out, counts_path, manifest_path=""):
    rules = _load_rules(rules_path)
    precedence, tiers_ok, categories = _validate_rules(rules)
    official = load_official(db)
    notices = load_notices(db)
    reference = _merge_reference(references)
    steps = load_steps(pack)
    valid_steps = sum(1 for s in steps
                      if s.get("validity") != "invalid_dropped")
    audit = audit_reconstruction(steps,
                                 rules["tolerances"]["FACTOR_EXACT"],
                                 rules["tolerances"]["DEDUPE_RATIO_TOL"])

    rows = []
    by_status = collections.Counter()
    by_tier = collections.Counter()
    by_validity = collections.Counter()
    by_compare = collections.Counter()
    audit_stat = collections.Counter()
    audit_by_validity = collections.defaultdict(collections.Counter)
    audit_reasons = collections.Counter()
    status_by_validity = collections.defaultdict(collections.Counter)
    o1_stat = collections.Counter()
    r1_stat = collections.Counter()
    errors = []
    for step in steps:
        a = audit.get((str(step.get("symbol")),
                       str(step.get("effective_date"))[:10]))
        c = classify(step, official, reference, rules, audit=a,
                     notices=notices)
        validity = str(step.get("validity"))
        status_by_validity[validity][c["final_status"]] += 1
        audit_by_validity[validity]["rows"] += 1
        if a is not None:
            audit_stat["passed" if a["ok"] else "failed"] += 1
            audit_by_validity[validity]["passed" if a["ok"] else "failed"] += 1
            for reason in a["notes"]:
                audit_reasons[reason] += 1
        if c.get("_o1"):
            o1_stat["used"] += 1
            o1_stat[c["_o1"].lower()] += 1
        if c.get("_r1"):
            r1_stat["used"] += 1
            r1_stat[c["_r1"].lower()] += 1
        if c["final_status"] not in precedence:
            errors.append("status %r" % c["final_status"])
        for tier in c["evidence_tier"].split("+"):
            if tier not in tiers_ok:
                errors.append("tier %r" % tier)
        if c["discrepancy_cause"] and c["discrepancy_cause"] not in categories:
            errors.append("cause %r" % c["discrepancy_cause"])
        row = {k: step.get(k) for k in
               ("symbol", "ins_code", "asset_id", "effective_date", "action",
                "ratio", "prod_ratio", "ref_ratio", "cum_factor_after",
                "method")}
        row["provenance"] = step.get("prov_kind")
        row.update(c)
        rows.append(row)
        by_status[c["final_status"]] += 1
        by_tier[c["evidence_tier"]] += 1
        by_validity[str(step.get("validity"))] += 1
        by_compare[c["comparison_result"]] += 1

    if errors:
        raise ValueError("classification outside the frozen rules: %s"
                         % "; ".join(sorted(set(errors))[:5]))
    if len(rows) != len(steps):
        raise ValueError("unexpected row count: %d (steps %d)"
                         % (len(rows), len(steps)))

    parent = os.path.dirname(os.path.abspath(out))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in FIELDS})

    counts = {
        "schema": 1,
        "stage": "stage03_step_ledger",
        "pack": os.path.basename(os.path.abspath(pack)),
        "inputs": {
            "pack_valid_steps": valid_steps,
            "pack_dropped_steps": len(steps) - valid_steps,
            "official_exact_keys": len(official),
            "official_events": sum(len(v) for v in official.values()),
            "notices": sum(len(v) for v in notices.values()),
            "reference_symbols": len(reference),
            "reference_changes": sum(len(v.get("factor_changes") or [])
                                     for v in reference.values()),
            "dedupe_ratio_tol": rules["tolerances"]["DEDUPE_RATIO_TOL"],
            "step_date_shift_max_days":
                rules["tolerances"]["STEP_DATE_SHIFT_MAX_DAYS"],
        },
        "rows": len(rows),
        "by_status": dict(sorted(by_status.items())),
        "by_evidence_tier": dict(sorted(by_tier.items())),
        "by_validity": dict(sorted(by_validity.items())),
        "comparison_result": dict(sorted(by_compare.items())),
        "reconstruction_audit": {
            "audited_rows": audit_stat["passed"] + audit_stat["failed"],
            "passed": audit_stat["passed"],
            "failed": audit_stat["failed"],
            "by_validity": {v: dict(sorted(c.items()))
                            for v, c in sorted(audit_by_validity.items())},
            "reasons": dict(sorted(audit_reasons.items())),
        },
        "status_by_validity": {v: dict(sorted(c.items()))
                               for v, c in sorted(status_by_validity.items())},
        "official_witness": dict(sorted(o1_stat.items())),
        "reference_witness": dict(sorted(r1_stat.items())),
        "notes": ("O1 joined on normalised symbol inside the rules-file step "
                  "date shift window; R1 joined on key with ratio = "
                  "1/ratio_change; duplicate detection uses DEDUPE_RATIO_TOL; "
                  "statuses resolved by step_status_precedence order; I1 is "
                  "internal reconstruction, not independent evidence."),
    }
    os.makedirs(os.path.dirname(os.path.abspath(counts_path)), exist_ok=True)
    with open(counts_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(counts, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    if manifest_path:
        PM.write_manifest(
            "stage03_step_ledger",
            [_rel(p) for p in
             [db, os.path.join(pack, "factors.jsonl"),
              os.path.join(pack, "manifest.json"), rules_path] + list(references)],
            [_rel(out), _rel(counts_path)],
            {"rows": len(rows), **counts["by_status"]},
            manifest_path)
    return rows, counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--reference", action="append", default=[])
    ap.add_argument("--rules", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--counts", default=DEFAULT_COUNTS)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST,
                    help="stage manifest path ('' disables)")
    a = ap.parse_args(argv)
    os.chdir(ROOT)
    try:
        rows, counts = build(a.db, a.pack, a.reference, a.rules, a.out,
                             a.counts, a.manifest)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print("STEP LEDGER FAIL: %s" % exc, file=sys.stderr)
        return 2
    print("step ledger: %d rows -> %s" % (len(rows), a.out))
    print(json.dumps(counts["by_status"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
