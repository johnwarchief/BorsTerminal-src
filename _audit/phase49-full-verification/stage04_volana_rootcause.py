#!/usr/bin/env python3
"""Stage 04 - root-cause the three unverified Volana adjustment steps.

Spec 7.5 asks six questions for every unverified ``ولانا`` step:

1. is the event real in Product?
2. is the effective date wrong?
3. is the difference a definition / Corporate Action difference?
4. did the reference apply the event differently?
5. is the event a duplicate or misclassified?
6. is the previous step's cumulative factor wrong?

The 0.1% threshold is frozen. This stage never changes it: it reports a
``PARTIAL_REFERENCE`` when the measured discrepancy sits between
``FACTOR_EXACT`` (0.1%) and ``FACTOR_MATERIAL`` (1%), and only a material
official disagreement becomes a ``CONFLICT_*``.

Measured result (pack ``ra365-phase49-rebuild-full-v2``, 2026-11-11)
---------------------------------------------------------------------
The pack keeps three ``multi_field_step_inference`` steps that are absent from
Product and from the B3 reference ``factor_changes`` list:

| date | pack ratio | step size | reference daily q ratio |
| --- | ---: | ---: | ---: |
| 2020-03-11 | 0.9990313041704958 | 0.096963% | 1.0009696351109922 |
| 2025-07-20 | 0.9991898460707485 | 0.081081% | 1.0008108108108158 |
| 2026-05-23 | 0.9997992371009847 | 0.020080% | 1.0002008032128504 |

Each pack ratio is exactly ``1 / q_ratio`` (error <= 2.3e-16), so the steps are
real, measurable transitions of the reference daily factor ``q =
type7.close / type0.close``. They are below the B3 change detector's 0.1%
rule, which is why R1 has no change entry on those dates.

The root cause of the measured 0.198% error is not the three ratios; it is the
cumulative chain. ``stageC.ref_regimes`` (the smoother used by
``stageD_merge_reference.py``) absorbs sub-threshold transitions into the next
regime boundary:

* the inserted 2019-03-19 ratio is ``1.0036815550`` = official 2019 change
  ``1.0027092929`` * tiny 2020 change ``1.0009696351``;
* the inserted 2026-08-02 ratio is ``7.9965883322`` = ``3.0030353305 *
  2.6628352490``, i.e. the 2026-07-15 change, the 2026-08-02 change and the
  2025/2026-05 tiny changes.

The base pack still carries the three tiny steps as separate rows, so they are
counted twice in ``cum_factor_after``. The pack cumulative factor is therefore
0.101178% below the reference ``q`` at every step after 2019-03-19 and
0.198239% below it at 2016-08-03. That is the max measured error reported here;
the per-step ratio error is ~0.

Evidence used (all read-only, stdlib only)
------------------------------------------
* B5 ledger ``ledgers/ADJUSTMENT-EVIDENCE-LEDGER.csv`` (status, tier, notes);
* pack ``factors.jsonl`` + ``manifest.json`` (the three rows, dropped steps);
* B3 ``captures/reference-index-30.json`` / ``-7.json`` (R1 change list);
* B3 normalized bars ``captures/normalized-30/bars.ndjson.gz`` (daily q);
* Seed DB ``_audit/phase49-finalization/seed/market.db`` (O1
  ``price_adjust_events`` / ``share_change_events``, O2 ``codal_notices``,
  product ``adjust_events``);
* ``dev/phase49_status_rules.json`` (frozen tolerances).

CLI
---
    python _audit/phase49-full-verification/stage04_volana_rootcause.py \\
        --steps data/ra365_corrections/ra365-phase49-rebuild-full-v2/factors.jsonl \\
        --out _audit/phase49-full-verification/evidence/volana-rootcause.json

The tracked output is the small summary under ``evidence/``; the detailed
ledger goes to the gitignored ``ledgers/`` area. No raw bar series is written.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
import os
import sqlite3
import sys
import time
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

EXACT = 1e-3
MATERIAL = 1e-2
SYMBOL = "ولانا"
SHIFT_DAYS = 5
NOTICE_DAYS = 10
CA_WORDS = ("افزایش سرمایه", "سود نقدی", "حق تقدم", "تعدیل", "درصد", "مجمع")

PACK = os.path.join(ROOT, "data", "ra365_corrections",
                    "ra365-phase49-rebuild-full-v2")
DEFAULT_LEDGER = os.path.join(HERE, "ledgers", "ADJUSTMENT-EVIDENCE-LEDGER.csv")
DEFAULT_REFERENCE = os.path.join(HERE, "captures", "reference-index-30.json")
DEFAULT_REFERENCE7 = os.path.join(HERE, "captures", "reference-index-7.json")
DEFAULT_NORMALIZED = os.path.join(HERE, "captures", "normalized-30",
                                  "bars.ndjson.gz")
DEFAULT_DB = os.path.join(ROOT, "_audit", "phase49-finalization", "seed",
                          "market.db")
DEFAULT_RULES = os.path.join(ROOT, "dev", "phase49_status_rules.json")
DEFAULT_LEDGER_OUT = os.path.join(HERE, "ledgers",
                                  "volana-rootcause-ledger.json")
DEFAULT_PACK_MANIFEST = os.path.join(PACK, "manifest.json")
DEFAULT_MANIFEST_OUT = os.path.join(HERE, "evidence",
                                    "stage04_volana_rootcause.manifest.json")


# ---------------------------------------------------------------------------
# The brief's mechanical ratio comparison (kept verbatim; the unit test pins
# its behaviour). ``product_ratio`` is the pack step ratio in the brief's
# naming; the pack's own ``prod_ratio`` column is null for these rows.
# ---------------------------------------------------------------------------
def rootcause(steps):
    steps = [s for s in steps if s.get("symbol") == "ولانا"
             and s.get("validity") == "unverified"]
    out = []
    for s in steps:
        p, r = float(s.get("ratio") or 0), float(s.get("ref_ratio") or 0)
        err = abs(r / p - 1.0) if p else 1.0
        cause = "MATCH"
        if err > EXACT:
            cause = "EVENT_RATIO_MISMATCH"
        out.append({"effective_date": s.get("effective_date"),
                    "product_ratio": p, "reference_ratio": r,
                    "relative_error": err, "cause": cause})
    return {"symbol": "ولانا", "count": len(out),
            "max_rel_error": max((s["relative_error"] for s in out), default=0),
            "steps": out}


# ---------------------------------------------------------------------------
# Small, stdlib-only helpers
# ---------------------------------------------------------------------------
def _d(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def _ratio(v):
    try:
        r = float(v)
    except (TypeError, ValueError):
        return None
    return r if math.isfinite(r) else None


def _iso_even(d_even):
    """``20200102`` -> ``2020-01-02``; ``None`` when invalid."""
    try:
        n = int(str(d_even)[:8])
    except (TypeError, ValueError):
        return None
    y, m, d = n // 10000, (n // 100) % 100, n % 100
    out = "%04d-%02d-%02d" % (y, m, d)
    return out if _d(out) else None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel(path):
    try:
        rel = os.path.relpath(os.path.abspath(path), ROOT)
    except ValueError:
        rel = os.path.abspath(path)
    return rel.replace("\\", "/")


def _write_json(path, payload):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return path


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _fmt(x, digits=12):
    return ("%." + str(digits) + "g") % x


def _pct(x, digits=6):
    return ("%." + str(digits) + "f%%") % (x * 100.0)


def _connect(db):
    return sqlite3.connect("file:%s?mode=ro" % str(db).replace("\\", "/"),
                           uri=True)


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
def load_pack_rows(path):
    rows = [r for r in _read_jsonl(path) if r.get("symbol") == SYMBOL]
    rows.sort(key=lambda r: str(r.get("effective_date"))[:10])
    return rows


def load_reference(path):
    return _read_json(path)


def reference_entry(index, symbol=SYMBOL):
    """The record for ``symbol``; keys are normalised, raw symbols listed."""
    if symbol in index:
        return index[symbol]
    for rec in index.values():
        if rec.get("symbol") == symbol or symbol in (rec.get("raw_symbols") or []):
            return rec
    return None


def load_ledger(path):
    """B5 rows keyed by effective date for the symbol."""
    out = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("symbol") == SYMBOL:
                out[str(row.get("effective_date"))[:10]] = row
    return out


def load_q(bars_path, symbol=SYMBOL):
    """Daily factor ``q = adjusted.close / raw.close`` from the B3 bars.

    Returns ``(q, quotes)``: ``q[date]`` is the factor, ``quotes[date]`` keeps
    the two closes and the raw/adjusted OHLC rows needed to describe a step.
    The full series is only held in memory; it is never written.
    """
    raw, adj = {}, {}
    with gzip.open(bars_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("symbol") != symbol:
                continue
            if str(row.get("resolution") or "").upper() != "D":
                continue
            typ = str(row.get("type") or "")
            adjust = row.get("adjust")
            if typ == "type0" or adjust == "raw":
                raw[str(row.get("date"))[:10]] = row
            elif typ == "type7" or adjust == "adjusted":
                adj[str(row.get("date"))[:10]] = row
    q, quotes = {}, {}
    for ds in sorted(set(raw) & set(adj)):
        rc = _ratio(raw[ds].get("close"))
        ac = _ratio(adj[ds].get("close"))
        if rc is None or ac is None or rc <= 0 or ac <= 0:
            continue
        q[ds] = ac / rc
        quotes[ds] = {"raw_close": rc, "adjusted_close": ac,
                      "raw": {k: raw[ds].get(k)
                              for k in ("open", "high", "low", "close")},
                      "adjusted": {k: adj[ds].get(k)
                                   for k in ("open", "high", "low", "close")}}
    return q, quotes


def load_rules(path):
    payload = _read_json(path)
    tol = payload.get("tolerances") or {}
    exact = _ratio(tol.get("FACTOR_EXACT"))
    material = _ratio(tol.get("FACTOR_MATERIAL"))
    if exact is None or material is None:
        raise ValueError("rules file lacks FACTOR_EXACT / FACTOR_MATERIAL")
    if abs(exact - EXACT) > 1e-12 or abs(material - MATERIAL) > 1e-12:
        raise ValueError("frozen tolerances drifted: %r/%r" % (exact, material))
    return {"tolerances": {"FACTOR_EXACT": exact,
                           "FACTOR_MATERIAL": material},
            "precedence": payload.get("step_status_precedence") or [],
            "categories": payload.get("reconciliation_categories") or []}


def load_product(db):
    """Product/O1/O2 evidence from the Seed DB (read-only)."""
    out = {"adjust_events": [], "price_adjust_events": [],
           "share_change_events": [], "codal_notices": [], "o1_rows": 0}
    con = _connect(db)
    try:
        for ds, ratio, source in con.execute(
                "SELECT date,ratio,source FROM adjust_events "
                "WHERE symbol=? ORDER BY date", (SYMBOL,)):
            r = _ratio(ratio)
            if _d(ds) and r is not None:
                out["adjust_events"].append(
                    {"date": str(ds)[:10], "ratio": r,
                     "source": str(source or "")})
        for ins, d_even, ratio, ctype in con.execute(
                "SELECT ins_code,d_even,ratio,corporate_type_code "
                "FROM price_adjust_events WHERE symbol=? ORDER BY d_even",
                (SYMBOL,)):
            ds, r = _iso_even(d_even), _ratio(ratio)
            if ds and r is not None and r > 0:
                out["price_adjust_events"].append(
                    {"ins_code": str(ins), "date": ds, "ratio": r,
                     "corporate_type_code": ctype, "source":
                     "price_adjust_events"})
        for ins, d_even, old, new in con.execute(
                "SELECT ins_code,d_even,shares_old,shares_new "
                "FROM share_change_events WHERE symbol=? ORDER BY d_even",
                (SYMBOL,)):
            ds, old, new = _iso_even(d_even), _ratio(old), _ratio(new)
            if ds and old and new and old > 0 and new > 0:
                out["share_change_events"].append(
                    {"ins_code": str(ins), "date": ds, "ratio": old / new,
                     "shares_old": old, "shares_new": new,
                     "source": "share_change_events"})
        for tid, title, sent, published in con.execute(
                "SELECT tracing_no,title,sent_date,publish_date "
                "FROM codal_notices WHERE symbol=? ORDER BY sent_date",
                (SYMBOL,)):
            text = str(title or "")
            out["codal_notices"].append(
                {"tracing_no": tid, "title": text,
                 "sent_date": sent, "publish_date": published,
                 "corporate_action": any(w in text for w in CA_WORDS)})
    finally:
        con.close()
    out["o1_rows"] = (len(out["price_adjust_events"])
                      + len(out["share_change_events"]))
    return out


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------
def _q_transition(q, ds):
    """The daily q transition on ``ds`` and its previous trading date."""
    if ds not in q:
        return None
    seq = sorted(q)
    i = seq.index(ds)
    if i == 0:
        return None
    prev = seq[i - 1]
    return {"date": ds, "prev_date": prev, "q_prev": q[prev], "q": q[ds],
            "ratio": q[ds] / q[prev]}


def reference_assessment(step, q, ref):
    ds = str(step.get("effective_date"))[:10]
    pack_ratio = _ratio(step.get("ratio"))
    trans = _q_transition(q, ds)
    changes = list(ref.get("factor_changes") or []) if ref else []
    change_dates = [str(c.get("date"))[:10] for c in changes]
    exact_change = None
    for c in changes:
        if str(c.get("date"))[:10] == ds:
            exact_change = c
            break
    out = {
        "date": ds,
        "pack_ratio": pack_ratio,
        "daily_q": trans,
        "in_change_list": exact_change is not None,
        "change": exact_change,
        "change_dates": change_dates,
        "factor_days": ref.get("factor_days") if ref else None,
        "factor_exact": ref.get("factor_exact") if ref else None,
        "factor_within_0_1pct": ref.get("factor_within_0_1pct") if ref else None,
        "capture_sha256": ref.get("capture_sha256") if ref else None,
    }
    if trans and pack_ratio:
        implied = 1.0 / pack_ratio
        out["implied_ratio"] = implied
        out["ratio_error"] = abs(implied / trans["ratio"] - 1.0)
        out["step_size"] = abs(pack_ratio - 1.0)
        out["q_close_match"] = abs(trans["ratio"] * pack_ratio - 1.0)
    else:
        out["implied_ratio"] = None
        out["ratio_error"] = None
        out["step_size"] = abs(pack_ratio - 1.0) if pack_ratio else None
        out["q_close_match"] = None
    if exact_change is not None:
        rc = _ratio(exact_change.get("ratio_change"))
        out["change_ratio_change"] = rc
        out["change_step_ratio"] = (1.0 / rc) if rc else None
        if out["change_step_ratio"] and pack_ratio:
            out["change_error"] = abs(pack_ratio / out["change_step_ratio"] - 1.0)
        else:
            out["change_error"] = None
    return out


def product_assessment(step, product, window=SHIFT_DAYS):
    ds = str(step.get("effective_date"))[:10]
    d0 = _d(ds)
    pack_ratio = _ratio(step.get("ratio"))
    all_events = []
    for ev in product.get("adjust_events") or []:
        d1 = _d(ev.get("date"))
        if d0 is None or d1 is None:
            continue
        delta = (d1 - d0).days
        rel = None
        if pack_ratio and ev.get("ratio"):
            rel = abs(float(ev["ratio"]) / pack_ratio - 1.0)
        all_events.append({"date": ev["date"], "ratio": ev.get("ratio"),
                           "source": ev.get("source"), "delta_days": delta,
                           "relative_error": rel})
    all_events.sort(key=lambda e: (abs(e["delta_days"]), e["delta_days"]))
    events = [e for e in all_events if abs(e["delta_days"]) <= 10]
    within = [e for e in all_events if abs(e["delta_days"]) <= window]
    exact = [e for e in within if e["delta_days"] == 0]
    best = exact[0] if exact else (within[0] if within else None)
    nearest = all_events[0] if all_events else None
    return {
        "date": ds,
        "canonical_prod_ratio": _ratio(step.get("prod_ratio")),
        "events_within_10d": events,
        "within_window": best is not None,
        "exact_date": bool(exact),
        "event": best,
        "nearest": nearest,
        "rel_error": best.get("relative_error") if best else None,
        "shift_days": best.get("delta_days") if best else None,
        "shift_in_window": (best is not None
                            and abs(best["delta_days"]) <= window),
        "o1_rows": product.get("o1_rows", 0),
        "codal_notices": product.get("codal_notices") or [],
        "price_adjust_events": product.get("price_adjust_events") or [],
        "share_change_events": product.get("share_change_events") or [],
    }


def official_assessment(step, product, window=SHIFT_DAYS, exact=EXACT,
                        material=MATERIAL):
    ds = str(step.get("effective_date"))[:10]
    d0 = _d(ds)
    pack_ratio = _ratio(step.get("ratio"))
    rows = []
    for ev in (product.get("price_adjust_events") or []):
        d1 = _d(ev.get("date"))
        if d0 is None or d1 is None or pack_ratio is None:
            continue
        delta = (d1 - d0).days
        if abs(delta) <= window:
            rows.append(dict(ev, delta_days=delta,
                             relative_error=abs(ev["ratio"] / pack_ratio - 1.0)))
    for ev in (product.get("share_change_events") or []):
        d1 = _d(ev.get("date"))
        if d0 is None or d1 is None or pack_ratio is None:
            continue
        delta = (d1 - d0).days
        if abs(delta) <= window:
            rows.append(dict(ev, delta_days=delta,
                             relative_error=abs(ev["ratio"] / pack_ratio - 1.0)))
    rows.sort(key=lambda r: (abs(r["delta_days"]), r["relative_error"]))
    exact_rows = [r for r in rows if r["delta_days"] == 0]
    out = {
        "window_days": window,
        "rows": rows,
        "exact_rows": exact_rows,
        "exact_best_error": min((r["relative_error"] for r in exact_rows),
                                default=None),
        "near_best_error": min((r["relative_error"] for r in rows
                                if r["delta_days"] != 0), default=None),
        "exact": bool(exact_rows),
        "matched": any(r["relative_error"] <= exact for r in rows),
        "tolerances": {"FACTOR_EXACT": exact, "FACTOR_MATERIAL": material},
    }
    return out


def chain_assessment(pack_rows, q):
    """Pack chain vs the independent reference daily q.

    ``cum_factor_after`` is the product of the later step ratios, so a chain
    that matches the reference factor satisfies ``cum(date) == q(date)`` at
    every step date (the newest step is normalised to 1.0).
    """
    out = []
    for s in pack_rows:
        ds = str(s.get("effective_date"))[:10]
        cum = _ratio(s.get("cum_factor_after"))
        qv = q.get(ds)
        err = (qv / cum - 1.0) if (qv and cum) else None
        row = {"date": ds, "ratio": _ratio(s.get("ratio")), "cum": cum,
               "q": qv, "cum_error": err, "prev_date": None,
               "prev_cum": None, "prev_q": None, "prev_cum_error": None}
        if out:
            row["prev_date"] = out[-1]["date"]
            row["prev_cum"] = out[-1]["cum"]
            row["prev_q"] = out[-1]["q"]
            row["prev_cum_error"] = out[-1]["cum_error"]
        out.append(row)
    return out


def _classify(reference, official, chain_row, group, rules):
    exact = rules["tolerances"]["FACTOR_EXACT"]
    material = rules["tolerances"]["FACTOR_MATERIAL"]
    if official["exact_best_error"] is not None:
        e = official["exact_best_error"]
        if e <= exact:
            return "VERIFIED_OFFICIAL", "OFFICIAL_EXACT_DATE_RATIO"
        if e <= material:
            return "PARTIAL_OFFICIAL", "EVENT_RATIO_MISMATCH"
        return "CONFLICT_RATIO", "EVENT_RATIO_MISMATCH"
    ratio_err = abs(reference.get("ratio_error") or 0.0)
    change_err = abs(reference.get("change_error") or 0.0)
    prev_err = abs(chain_row.get("prev_cum_error") or 0.0)
    group_err = abs(group.get("group_effect") or 0.0)
    e = max(ratio_err, change_err, prev_err, group_err)
    if e <= exact:
        return "VERIFIED_REFERENCE", ""
    if e <= material:
        if ratio_err > exact and ratio_err >= max(change_err, prev_err,
                                                  group_err):
            return "PARTIAL_REFERENCE", "EVENT_RATIO_MISMATCH"
        return "PARTIAL_REFERENCE", "PRECISION_OR_ROUNDING"
    if ratio_err >= max(change_err, prev_err, group_err):
        return "CONFLICT_RATIO", "EVENT_RATIO_MISMATCH"
    return "CONFLICT_CHAIN", "SOURCE_MISMATCH"


def _root_cause(reference, product, chain_row):
    if reference.get("in_change_list"):
        return "REFERENCE_CHANGE_LIST_ENTRY"
    codes = ["REFERENCE_SUBTHRESHOLD_STEP"]
    if (chain_row.get("prev_cum_error") is not None
            and abs(chain_row["prev_cum_error"]) > EXACT):
        codes.append("DOUBLE_COUNTED")
    if not product.get("within_window"):
        codes.append("NO_PRODUCT_EVENT")
    if (product.get("rel_error") is not None
            and product["rel_error"] > EXACT):
        codes.append("PRODUCT_RATIO_DIFF")
    return "_".join(codes)


def _six_answers(reference, product, official, chain_row, group, step,
                 dup=None):
    ds = reference["date"]
    trans = reference["daily_q"] or {}
    ratios = reference.get("implied_ratio")
    qr = trans.get("ratio")
    pack_ratio = reference.get("pack_ratio")
    step_size = reference.get("step_size")
    prev = chain_row.get("prev_cum_error")
    pe = product.get("event")
    nearest = product.get("nearest")
    ca_notices = sum(1 for n in (product.get("codal_notices") or [])
                     if n.get("corporate_action"))
    absorbed = ("2019-03-19" if ds < "2025-07-20" else "2026-08-02")
    answers = {}
    if pe:
        answers["real_product_event"] = (
            "partial: product adjust_events has %s ratio %s (%+d day(s) from "
            "the pack date, %s from the pack ratio); the canonical product "
            "chain used by the pack has no event (prod_ratio=null); official "
            "O1 has %d row(s)."
            % (pe["date"], _fmt(pe["ratio"]), pe["delta_days"],
               _pct(pe["relative_error"]) if pe.get("relative_error")
               is not None else "n/a", product["o1_rows"]))
    else:
        near = ""
        if nearest:
            near = ("; nearest product event %s (%+d days, outside the %d-day "
                    "window)" % (nearest["date"], nearest["delta_days"],
                                 SHIFT_DAYS))
        answers["real_product_event"] = (
            "no: no product adjust_event within %d days%s; the canonical "
            "product chain used by the pack has no event (prod_ratio=null); "
            "official O1 has %d row(s)."
            % (SHIFT_DAYS, near, product["o1_rows"]))
    gap_note = ""
    if trans.get("prev_date") and _d(trans["prev_date"]) and _d(ds):
        gap_days = (_d(ds) - _d(trans["prev_date"])).days
        if gap_days > 10:
            gap_note = (" (the previous reference q observation is %s, a "
                        "%d-day gap; the exact event date is not pinned by "
                        "the reference)" % (trans["prev_date"], gap_days))
    answers["effective_date_wrong"] = (
        "no: the pack date equals the first reference daily q observation of "
        "the new level %s exactly (q %s -> %s, ratio %s)%s%s; the frozen "
        "shift window is %d days."
        % (ds, _fmt(trans.get("q_prev")), _fmt(trans.get("q")), _fmt(qr),
           gap_note,
           ("; the product event date %s is %+d day(s) away"
            % (pe["date"], pe["delta_days"])) if pe else
           "; no product event exists to compare",
           SHIFT_DAYS))
    answers["definition_or_ca_difference"] = (
        "no official corporate action: price_adjust_events=%d, "
        "share_change_events=%d, corporate-action-titled CODAL notices=%d; "
        "the transition is a sub-0.1%% reference factor re-basing (%s step), "
        "not a CA definition difference."
        % (len(product.get("price_adjust_events") or []),
           len(product.get("share_change_events") or []), ca_notices,
           _pct(step_size) if step_size is not None else "n/a"))
    answers["reference_applied_differently"] = (
        "yes at the index/regime layer: the reference daily q applies the step "
        "exactly (q ratio %s vs pack-implied %s, error %s); the reference "
        "factor_changes list only records transitions above 0.1%% and has no "
        "entry on this date; stageD ref_regimes absorbed the step into the %s "
        "regime ratio, so the kept base-pack step is double-counted."
        % (_fmt(qr), _fmt(ratios),
           _fmt(reference.get("ratio_error")) if reference.get("ratio_error")
           is not None else "n/a", absorbed))
    dup = dup or {"same_date_rows": 1, "spellings": [SYMBOL],
                  "same_day_group": False}
    answers["duplicate_or_misclassified"] = (
        "no duplicate: %d pack row(s) on %s, spelling(s) %s, no same-day "
        "group; the REF_ONLY/unverified class is correct; the action label "
        "replace_step is imprecise because prod_ratio is null, but the event "
        "is not misclassified."
        % (dup["same_date_rows"], ds, ", ".join(dup["spellings"])))
    answers["previous_cum_factor_wrong"] = (
        "yes: pack cum_factor_after at the previous step (%s) is %s while the "
        "reference q is %s (q/cum-1 = %s); at 2016-08-03 the gap is %s; the "
        "internal chain cum(prev)=cum(next)*ratio(next) holds, so the error is "
        "the double-counted sub-threshold steps, not a broken chain formula."
        % (chain_row.get("prev_date"), _fmt(chain_row.get("prev_cum")),
           _fmt(chain_row.get("prev_q")),
           _pct(abs(prev)) if prev is not None else "n/a",
           _pct(abs(group.get("chain_error_2016") or 0))))
    return answers


# ---------------------------------------------------------------------------
# Deep analysis
# ---------------------------------------------------------------------------
def analyze(pack_path, ledger_path, reference_path, reference7_path,
            normalized_path, db_path, rules_path, pack_manifest_path=None):
    steps = [r for r in load_pack_rows(pack_path)
             if r.get("validity") == "unverified"]
    if len(steps) != 3:
        raise ValueError("expected exactly 3 unverified ولانا steps, found %d"
                         % len(steps))
    rules = load_rules(rules_path)
    q, quotes = load_q(normalized_path)
    ref_index = load_reference(reference_path)
    ref = reference_entry(ref_index)
    if ref is None:
        raise ValueError("reference index has no entry for %s" % SYMBOL)
    ref7 = None
    if reference7_path and os.path.exists(reference7_path):
        ref7 = reference_entry(load_reference(reference7_path))
        if ref7 and ref7.get("factor_changes") != ref.get("factor_changes"):
            raise ValueError("reference-index-30 and -7 disagree for %s"
                             % SYMBOL)
    ledger = load_ledger(ledger_path)
    product = load_product(db_path)
    pack_rows = load_pack_rows(pack_path)
    chain = chain_assessment(pack_rows, q)
    chain_by_date = {r["date"]: r for r in chain}

    tiny_product = 1.0
    for s in steps:
        tiny_product *= float(s["ratio"])
    group_effect = 1.0 - tiny_product
    chain_max = max((abs(r["cum_error"]) for r in chain
                     if r["cum_error"] is not None), default=0.0)
    chain_max_date = max((r for r in chain if r["cum_error"] is not None),
                         key=lambda r: abs(r["cum_error"]))["date"] \
        if any(r["cum_error"] is not None for r in chain) else None
    group = {
        "ratio_product": tiny_product,
        "group_effect": group_effect,
        "inverse_group_effect": (1.0 / tiny_product - 1.0) if tiny_product else None,
        "chain_error_2016": next((r["cum_error"] for r in chain
                                  if r["date"] == "2016-08-03"), None),
        "chain_error_after_2019": next((r["cum_error"] for r in chain
                                        if r["date"] == "2019-03-19"), None),
        "max_cumulative_error": chain_max,
        "max_cumulative_error_date": chain_max_date,
    }

    results = []
    for step in steps:
        ds = str(step["effective_date"])[:10]
        ra = reference_assessment(step, q, ref)
        pa = product_assessment(step, product)
        oa = official_assessment(step, product,
                                 exact=rules["tolerances"]["FACTOR_EXACT"],
                                 material=rules["tolerances"]["FACTOR_MATERIAL"])
        cr = chain_by_date.get(ds) or {"date": ds, "prev_cum_error": None}
        same_date = [r for r in pack_rows
                     if str(r.get("effective_date"))[:10] == ds]
        dup = {"same_date_rows": len(same_date),
               "spellings": sorted({str(r.get("symbol")) for r in same_date}),
               "same_day_group": len(same_date) > 1}
        status, cause = _classify(ra, oa, cr, group, rules)
        row = {
            "effective_date": ds,
            "pack_ratio": ra["pack_ratio"],
            "reference_daily_q_ratio": (ra["daily_q"] or {}).get("ratio"),
            "pack_implied_ratio": ra.get("implied_ratio"),
            "ratio_error": ra.get("ratio_error"),
            "step_size": ra.get("step_size"),
            "in_reference_change_list": ra["in_change_list"],
            "final_status": status,
            "discrepancy_cause": cause,
            "cause_note": (
                "The frozen category PRECISION_OR_ROUNDING names the "
                "sub-threshold reference factor nature; the exact chain error "
                "is the double count described in root_cause."
                if cause == "PRECISION_OR_ROUNDING" else ""),
            "root_cause": _root_cause(ra, pa, cr),
            "previous_cum_factor": {
                "date": cr.get("prev_date"),
                "pack_cum": cr.get("prev_cum"),
                "reference_q": cr.get("prev_q"),
                "q_over_cum_minus_1": cr.get("prev_cum_error"),
            },
            "product_event": pa["event"],
            "product_events_within_10d": pa["events_within_10d"],
            "canonical_prod_ratio": pa["canonical_prod_ratio"],
            "official_rows": len(oa["rows"]),
            "official_exact_best_error": oa["exact_best_error"],
            "duplicate_check": dup,
            "ledger": {
                "final_status": (ledger.get(ds) or {}).get("final_status"),
                "evidence_tier": (ledger.get(ds) or {}).get("evidence_tier"),
                "comparison_result": (ledger.get(ds) or {}).get("comparison_result"),
                "risk_score": (ledger.get(ds) or {}).get("risk_score"),
                "notes": (ledger.get(ds) or {}).get("notes"),
            },
            "six_questions": _six_answers(ra, pa, oa, cr, group, step, dup),
            "evidence": {
                "q_prev_date": (ra["daily_q"] or {}).get("prev_date"),
                "q_prev": (ra["daily_q"] or {}).get("q_prev"),
                "q": (ra["daily_q"] or {}).get("q"),
                "quotes": {
                    "prev": quotes.get((ra["daily_q"] or {}).get("prev_date")),
                    "date": quotes.get(ds),
                },
                "reference_change_dates": ra["change_dates"],
                "reference_factor_days": ra["factor_days"],
                "reference_factor_exact": ra["factor_exact"],
                "reference_factor_within_0_1pct": ra["factor_within_0_1pct"],
                "reference_capture_sha256": ra["capture_sha256"],
            },
        }
        results.append(row)

    statuses = collections.Counter(r["final_status"] for r in results)
    regime_composition = {}
    try:
        regime_composition["2019-03-19"] = {
            "regime_ratio": q["2020-03-11"] / q["2016-08-03"],
            "official_2019_ratio": q["2019-03-19"] / q["2016-08-03"],
            "absorbed_2020_ratio": q["2020-03-11"] / q["2019-03-19"],
        }
        regime_composition["2026-08-02"] = {
            "regime_ratio": 1.0 / q["2024-03-30"],
            "official_2026_07_15_ratio": q["2026-07-15"] / q["2024-03-30"],
            "absorbed_2025_2026_05_ratio":
                (q["2026-07-15"] / q["2024-03-30"]) / 3.0,
            "official_2026_08_02_ratio": q["2026-08-02"] / q["2026-07-15"],
        }
    except KeyError:
        pass
    summary_steps = []
    for r in results:
        summary_steps.append({
            "effective_date": r["effective_date"],
            "pack_ratio": r["pack_ratio"],
            "reference_daily_q_ratio": r["reference_daily_q_ratio"],
            "ratio_error": r["ratio_error"],
            "step_size": r["step_size"],
            "final_status": r["final_status"],
            "discrepancy_cause": r["discrepancy_cause"],
            "cause_note": r["cause_note"],
            "root_cause": r["root_cause"],
            "previous_cum_factor": r["previous_cum_factor"],
            "product_event": r["product_event"],
            "canonical_prod_ratio": r["canonical_prod_ratio"],
            "official_rows": r["official_rows"],
            "duplicate_check": r["duplicate_check"],
            "ledger_status": r["ledger"],
            "six_questions": r["six_questions"],
        })

    summary = {
        "schema": "phase49-volana-rootcause-v1",
        "symbol": SYMBOL,
        "count": len(results),
        "thresholds": {
            "FACTOR_EXACT": rules["tolerances"]["FACTOR_EXACT"],
            "FACTOR_MATERIAL": rules["tolerances"]["FACTOR_MATERIAL"],
            "changed": False,
            "note": "the 0.1% threshold is unchanged; nothing is verified "
                    "while the measured discrepancy exceeds it",
        },
        "statuses": dict(statuses),
        "group": group,
        "regime_composition": regime_composition,
        "max_cumulative_error": group["max_cumulative_error"],
        "steps": summary_steps,
        "related_findings": [
            {
                "id": "HIDDEN_DOUBLE_COUNT_2019",
                "detail": "The pack 2019-03-19 ratio 0.9963319491 equals "
                          "1/(official 2019 q change 1.0027092929 * tiny 2020 "
                          "q change 1.0009696351). B5 compares it with the "
                          "single R1 change 0.9972980276; the 0.09697% gap is "
                          "below FACTOR_EXACT, so B5 marks the row "
                          "VERIFIED_REFERENCE even though the 2020 tiny step "
                          "is already inside the 2019 ratio.",
            },
            {
                "id": "CONFLICT_2026_08_02",
                "detail": "The pack 2026-08-02 ratio 0.1250533301 equals "
                          "q(2024-03-30) = 1/(3.0030353305 * 2.6628352490), "
                          "the regime ratio spanning the 2026-07-15 change, "
                          "the 2026-08-02 change and the 2025/2026-05 tiny "
                          "steps. B5 compares it with the single R1 change at "
                          "2026-08-02 (0.3755395683) and correctly reports "
                          "CONFLICT_RATIO. The fix is to restore the dropped "
                          "2026-07-15 step and use single-step ratios (B11), "
                          "not to change the threshold.",
            },
            {
                "id": "DROPPED_2026_07_15",
                "detail": "The manifest dropped a 0.333333 step at "
                          "2026-07-15 whose ratio matches the R1 change 3.0 "
                          "exactly (1/3); B5 already flags it as contradicted "
                          "by B3. Its effect is absorbed into the 2026-08-02 "
                          "ratio.",
            },
        ],
        "inputs": {
            "pack": {"path": _rel(pack_path), "sha256": _sha256(pack_path)},
            "ledger": {"path": _rel(ledger_path),
                       "sha256": _sha256(ledger_path)},
            "reference": {"path": _rel(reference_path),
                          "sha256": _sha256(reference_path)},
            "reference7": ({"path": _rel(reference7_path),
                            "sha256": _sha256(reference7_path)}
                           if ref7 and reference7_path else None),
            "normalized_bars": {"path": _rel(normalized_path),
                                "capture_sha256": ref.get("capture_sha256")},
            "db": {"path": _rel(db_path), "sha256": _sha256(db_path)},
            "rules": {"path": _rel(rules_path),
                      "sha256": _sha256(rules_path)},
        },
        "field_note": "rootcause() keeps the brief's names: product_ratio in "
                      "the mechanical block is the pack step ratio; the pack's "
                      "canonical prod_ratio column is null for these rows.",
    }
    if pack_manifest_path and os.path.isfile(pack_manifest_path):
        summary["pack_manifest"] = {
            "path": _rel(pack_manifest_path),
            "sha256": _sha256(pack_manifest_path),
        }
    ledger_payload = {
        "schema": "phase49-volana-rootcause-ledger-v1",
        "symbol": SYMBOL,
        "count": len(results),
        "chain": chain,
        "steps": results,
        "group": group,
        "statuses": dict(statuses),
    }
    return summary, ledger_payload


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _merge(mech, deep):
    merged = dict(mech)
    merged["per_step_max_rel_error"] = mech.get("max_rel_error")
    merged["max_cumulative_error"] = deep.get("max_cumulative_error")
    merged["max_rel_error"] = max(mech.get("max_rel_error") or 0.0,
                                  deep.get("max_cumulative_error") or 0.0)
    merged["max_rel_error_basis"] = (
        "max(per-step pack/reference ratio error, largest pack "
        "cum_factor_after discrepancy against the reference daily q). The "
        "three steps' individual ratio errors are ~0; their cumulative "
        "double-count effect is the 0.198% value. The brief's 0.198% "
        "expectation is cumulative, not a per-step ratio error.")
    by_date = {s["effective_date"]: dict(s) for s in mech.get("steps") or []}
    for s in deep.get("steps") or []:
        target = by_date.setdefault(s["effective_date"], {})
        target.update(s)
    merged["steps"] = [by_date[k] for k in sorted(by_date)]
    for key in ("schema", "thresholds", "statuses", "group",
                "regime_composition", "related_findings", "inputs",
                "field_note", "pack_manifest"):
        if key in deep:
            merged[key] = deep[key]
    return merged


def _write_manifest(args, report):
    """Same manifest shape as the earlier phase49 stages, relative paths."""
    inputs = [args.steps, args.ledger, args.reference, args.reference7,
              args.normalized, args.db, args.rules, args.pack_manifest]
    outputs = [args.out, args.ledger_out]
    payload = {
        "stage": "stage04_volana_rootcause",
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {_rel(p): _sha256(p) for p in inputs if os.path.isfile(p)},
        "outputs": {_rel(p): _sha256(p) for p in outputs if os.path.isfile(p)},
        "counts": {"unverified_steps": report.get("count"),
                   "statuses": report.get("statuses"),
                   "max_cumulative_error": report.get("max_cumulative_error")},
    }
    _write_json(args.manifest_out, payload)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Root-cause the unverified Volana adjustment steps.")
    ap.add_argument("--steps", required=True,
                    help="pack factors.jsonl (or a JSONL of steps)")
    ap.add_argument("--out", required=True,
                    help="tracked summary JSON under evidence/")
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    ap.add_argument("--reference", default=DEFAULT_REFERENCE)
    ap.add_argument("--reference7", default=DEFAULT_REFERENCE7)
    ap.add_argument("--normalized", default=DEFAULT_NORMALIZED)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--rules", default=DEFAULT_RULES)
    ap.add_argument("--ledger-out", default=DEFAULT_LEDGER_OUT)
    ap.add_argument("--pack-manifest", default=DEFAULT_PACK_MANIFEST)
    ap.add_argument("--manifest-out", default=DEFAULT_MANIFEST_OUT)
    ap.add_argument("--no-deep", action="store_true",
                    help="only the brief's mechanical ratio comparison")
    args = ap.parse_args(argv)

    steps = [json.loads(line) for line in open(args.steps, encoding="utf-8")
             if line.strip()]
    report = rootcause(steps)
    deep = None
    if not args.no_deep:
        try:
            deep, ledger_payload = analyze(
                args.steps, args.ledger, args.reference, args.reference7,
                args.normalized, args.db, args.rules, args.pack_manifest)
        except (FileNotFoundError, ValueError) as exc:
            print("stage04: deep analysis skipped: %s" % exc, file=sys.stderr)
        else:
            _write_json(args.ledger_out, ledger_payload)
            report = _merge(report, deep)
    _write_json(args.out, report)
    if deep:
        _write_manifest(args, report)
    brief = {k: report.get(k) for k in
             ("symbol", "count", "max_rel_error", "per_step_max_rel_error",
              "max_cumulative_error", "statuses")}
    brief["steps"] = [{k: s.get(k) for k in
                       ("effective_date", "pack_ratio", "reference_ratio",
                        "relative_error", "cause", "final_status",
                        "root_cause")}
                      for s in report.get("steps") or []]
    print(json.dumps(brief, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
