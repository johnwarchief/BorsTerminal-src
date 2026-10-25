#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Infer the effective adjustment factor between a raw series and an adjusted one.

Given, for one instrument, the product's RAW OHLC and the reference's ADJUSTED
OHLC on the same sessions, the effective factor of a session is

    factor(t) = reference_adjusted(t) / product_raw(t)

(the multiplier the reference applied to the raw series; same convention as the
R31 witness, where factor = H_type7 / H_type0).

The tool never guesses a factor from one candle.  For each instrument it
searches for the scalar that the largest number of (session, field) pairs
agree on, takes every session where at least `min_fields` fields agree with it
as that factor's evidence, splits that evidence into date-contiguous intervals,
and then repeats on what is left.  A field that does not follow the scalar (a
close computed on a different basis, say) is named as a dissenter rather than
averaged away.

It separates:
  rounding                  residual within one price unit of raw x factor
  dissenting field          one field tracks a different definition
  no single scalar          open/high/low disagree: not a factor at all, so it
                            belongs to the data/model ledger
  insufficient evidence     fewer than `min_run` sessions support the scalar
  revision                  only detectable with two snapshots; when a single
                            snapshot is all we have the field is reported as
                            unavailable instead

Every threshold is a tool parameter printed with the run and swept for
sensitivity; none of them is a methodology ruling.  A ratio break is a
computational witness only: `event_attribution` stays `unattributed` unless
independent event evidence is supplied.

Usage
  python infer_factor_segments.py --pairs <pairs.ndjson.gz> --out <dir>
  python infer_factor_segments.py --in _audit/RA365-CANDLE-DIVERGE-2026-10-12.csv \
      --kind candle-diverge --out <dir>
  python infer_factor_segments.py --in ... --kind candle-diverge --fields h,l --out <dir>
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import r32_evidence as EV  # noqa: E402
import r32_io as IO  # noqa: E402
import r32_schema as S  # noqa: E402

ALL_FIELDS = ("o", "h", "l", "c")

#: Tool parameters (printed with every run; not methodology rulings).
DEFAULTS = {
    "break_tol": 5e-4,      # relative agreement tolerance between a field and the scalar
    "tick": 1.0,            # a price unit; a residual below it is rounding
    "min_run": 3,           # sessions a scalar must cover before it is a segment
    "min_fields": 2,        # fields that must agree with the scalar on a session
    "max_candidates": 400,  # scalar candidates considered per instrument
    "max_score_rows": 6000, # entries used to score a candidate
    "merge_gap": 2,         # unexplained sessions that may be folded into a regime
}

CAUSES = ("exact_single_scalar", "single_scalar_with_rounding", "single_scalar",
          "single_scalar_with_dissent", "no_single_scalar", "insufficient_evidence")


def _entry(pair, fields):
    ratios, prices = {}, []
    for f in fields:
        p, r = (pair["prod"] or {}).get(f), (pair["ref"] or {}).get(f)
        if p and r and p > 0 and r > 0:
            ratios[f] = r / p
            prices.append(p)
    if not ratios:
        return None
    return {"date": pair["date"], "ratios": ratios, "pair": pair,
            "price_scale": statistics.median(sorted(prices))}


def _tol_for(entry, opts):
    """Agreement tolerance at this session's price scale.

    One unit of the raw price moves the ratio by about tick/price, so at small
    prices that wobble is rounding, not a factor change.
    """
    floor = opts["tick"] / entry["price_scale"] if entry.get("price_scale") else 0.0
    return max(opts["break_tol"], floor), floor > opts["break_tol"]


def _agree_fields(entry, factor, tol):
    return [f for f, v in entry["ratios"].items() if v and abs(v / factor - 1.0) <= tol]


def _best_scalar(entries, opts):
    """The scalar the most (session, field) pairs agree on."""
    cand = sorted(v for e in entries for v in e["ratios"].values() if v)
    if not cand:
        return None, 0
    if len(cand) > opts["max_candidates"]:
        step = len(cand) / opts["max_candidates"]
        cand = [cand[min(int(i * step), len(cand) - 1)] for i in range(opts["max_candidates"])]
    rows = entries
    if len(rows) > opts["max_score_rows"]:
        step = len(rows) / opts["max_score_rows"]
        rows = [rows[min(int(i * step), len(rows) - 1)] for i in range(opts["max_score_rows"])]
    best, best_n, best_score = None, -1, -1
    for f in cand:
        n = 0
        score = 0
        for e in rows:
            tol, _ = _tol_for(e, opts)
            k = len(_agree_fields(e, f, tol))
            if k >= opts["min_fields"]:
                n += 1
                score += k
        if (n, score) > (best_n, best_score):
            best, best_n, best_score = f, n, score
    return best, best_n


def _contiguous_runs(dates, order):
    """Split a set of dates into maximal runs that are adjacent in the sequence."""
    pos = sorted(order.index(d) for d in dates if d in order)
    runs, cur = [], []
    for i in pos:
        if cur and i != cur[-1] + 1:
            runs.append(cur)
            cur = []
        cur.append(i)
    if cur:
        runs.append(cur)
    return [[order[i] for i in r] for r in runs]


def _merge_across_gaps(runs, opts, order):
    """Fold a short unexplained gap back into the regime on either side of it.

    One session whose fields happen to disagree must not split a single factor
    regime into three pieces.  The absorbed sessions stay in the span but not
    in the evidence, and the count is recorded as `gaps_absorbed`.
    """
    out = []
    i = 0
    while i < len(runs):
        r = runs[i]
        if (r["kind"] == "residual" and out and i + 1 < len(runs)
                and out[-1]["kind"] == "scalar" and runs[i + 1]["kind"] == "scalar"
                and len(r["dates"]) <= opts["merge_gap"]
                and abs(runs[i + 1]["factor"] / out[-1]["factor"] - 1.0) <= opts["break_tol"]):
            out[-1]["dates"].extend(r["dates"])
            out[-1]["dates"].extend(runs[i + 1]["dates"])
            out[-1]["support"] |= runs[i + 1]["support"]
            out[-1]["gaps_absorbed"] = out[-1].get("gaps_absorbed", 0) + len(r["dates"])
            i += 2
            continue
        r.setdefault("gaps_absorbed", 0)
        out.append(r)
        i += 1
    return out


def _residuals(run_entries, factor, agreeing):
    abs_errs, rel_errs = [], []
    for e in run_entries:
        for f in agreeing:
            p, r = (e["pair"]["prod"] or {}).get(f), (e["pair"]["ref"] or {}).get(f)
            if p is None or r is None:
                continue
            want = p * factor
            abs_errs.append(abs(want - r))
            if r:
                rel_errs.append(abs(want - r) / abs(r))
    return (max(abs_errs) if abs_errs else None,
            max(rel_errs) if rel_errs else None,
            statistics.median(rel_errs) if rel_errs else None)


def _classify(agreeing, dissent, res_max_abs, res_max_rel, n, opts, factor=None):
    body = [f for f in ("o", "h", "l") if f in agreeing]
    if n < opts["min_run"]:
        return ("insufficient_evidence", "only %d session(s) support this scalar" % (n,))
    if len(body) < 2 and len(agreeing) < opts["min_fields"]:
        return ("no_single_scalar",
                "open/high/low do not agree on one scalar: the difference is not a factor, "
                "so it belongs to the data/model ledger")
    if dissent:
        return ("single_scalar_with_dissent",
                "%s agree on one scalar (%.6g); %s does not (%.6g). The two sides use a "
                "different %s definition, or a different session's %s; which is authoritative "
                "is the owner's ruling, not this tool's"
                % (",".join(sorted(agreeing)), factor or 0.0,
                   ",".join(sorted(dissent)), min(dissent.values()),
                   ",".join(sorted(dissent)), ",".join(sorted(dissent))))
    if res_max_abs is not None and res_max_abs <= opts["tick"]:
        if not res_max_abs:
            return ("exact_single_scalar", "raw x factor reproduces every agreeing field exactly")
        return ("single_scalar_with_rounding",
                "every agreeing field is within one price unit (%.4g) of raw x factor"
                % (opts["tick"],))
    if res_max_rel is not None and res_max_rel > opts["break_tol"]:
        return ("single_scalar",
                "fields agree on one scalar but leave up to %.3g relative residual" % (res_max_rel,))
    return ("single_scalar", "one scalar explains every measured field within tolerance")


def _confidence(cause, n, res_max_rel, res_max_abs, opts):
    if cause == "no_single_scalar":
        return 0.1, "no single scalar fits; the confidence is in the classification, not a factor"
    if cause == "insufficient_evidence":
        return 0.2, "fewer than %d sessions" % opts["min_run"]
    c = 0.9 if n >= 10 else 0.7 if n >= opts["min_run"] else 0.4
    notes = ["%d session(s)" % n]
    if cause == "single_scalar_with_dissent":
        c -= 0.2
        notes.append("a field dissents")
    if res_max_rel is not None and res_max_rel > opts["break_tol"]:
        c -= 0.2
        notes.append("relative residual %.2g exceeds the tolerance" % res_max_rel)
    if res_max_abs is not None and res_max_abs > opts["tick"]:
        notes.append("absolute residual %.3g exceeds one price unit" % res_max_abs)
    return max(c, 0.1), "; ".join(notes)


def _max_gap_days(entries):
    ds = [_dt.date.fromisoformat(e["date"]) for e in entries]
    return max((b - a).days for a, b in zip(ds, ds[1:])) if len(ds) > 1 else None


def infer_group(pairs, opts, extra_events=None):
    fields = opts["fields"]
    entries, skipped = [], []
    for pair in pairs:
        e = _entry(pair, fields)
        if e is None or len(e["ratios"]) < opts["min_fields"]:
            skipped.append(pair.get("date"))
            continue
        entries.append(e)
    entries.sort(key=lambda e: e["date"])
    if not entries:
        return [], {"sessions": 0, "skipped": len(skipped), "segments": 0, "breaks": 0, "causes": {}}

    order = [e["date"] for e in entries]
    by_date = {e["date"]: e for e in entries}

    events = defaultdict(list)
    for ev in (extra_events or []):
        events[ev.get("date")].append(ev)

    # Greedy: take the strongest scalar, keep its evidence, recurse on the rest.
    runs = []
    remaining = set(order)
    while remaining:
        subset = [by_date[d] for d in order if d in remaining]
        factor, n_support = _best_scalar(subset, opts)
        if factor is None:
            break
        members = []
        for e in subset:
            tol, _ = _tol_for(e, opts)
            if len(_agree_fields(e, factor, tol)) >= opts["min_fields"]:
                members.append(e["date"])
        if len(members) < opts["min_run"]:
            break
        for run in _contiguous_runs(set(members), order):
            runs.append({"kind": "scalar", "dates": run, "factor": factor,
                         "support": set(run)})
        remaining -= set(members)

    for run in _contiguous_runs(remaining, order):
        runs.append({"kind": "residual", "dates": run, "factor": None, "support": set()})

    runs.sort(key=lambda r: order.index(r["dates"][0]))
    runs = _merge_across_gaps(runs, opts, order)

    segments = []
    prev_factor = None
    for idx, run in enumerate(runs):
        kind, dates, factor = run["kind"], run["dates"], run["factor"]
        support = run["support"] or set(dates)
        run_entries = [by_date[d] for d in dates]
        support_entries = [by_date[d] for d in sorted(support)]
        n = len(run_entries)
        n_support = len(support_entries)
        if kind == "scalar":
            agreeing, dissenting = set(), {}
            for f in fields:
                vals = [e["ratios"][f] for e in support_entries if f in e["ratios"]]
                if not vals:
                    continue
                med = statistics.median(vals)
                tol, _ = _tol_for(support_entries[len(support_entries) // 2], opts)
                if abs(med / factor - 1.0) <= tol:
                    agreeing.add(f)
                else:
                    dissenting[f] = med
            agreeing = agreeing or set(fields)
            res_max_abs, res_max_rel, res_med_rel = _residuals(support_entries, factor, agreeing)
            cause, basis = _classify(agreeing, dissenting, res_max_abs, res_max_rel,
                                     n_support, opts, factor)
            eff_tol, rounding_dominated = _tol_for(support_entries[len(support_entries) // 2], opts)
        else:
            factor = None
            agreeing, dissenting = set(), {}
            res_max_abs = res_max_rel = res_med_rel = None
            cause, basis = ("no_single_scalar",
                            "no scalar covered these sessions: the difference is not a factor, "
                            "so it belongs to the data/model ledger")
            eff_tol, rounding_dominated = _tol_for(run_entries[len(run_entries) // 2], opts)

        date_from, date_to = run_entries[0]["date"], run_entries[-1]["date"]
        ev_here = [e for d, lst in events.items()
                   if d and date_from <= S.normalize_date(d) <= date_to for e in lst]
        attribution = ("independent" if any(e.get("independent") for e in ev_here)
                       else "inferential" if ev_here else "unattributed")
        confidence, why = _confidence(cause, n_support, res_max_rel, res_max_abs, opts)
        breakpoint = None
        if prev_factor and factor:
            breakpoint = {"date": date_from, "prev_factor": round(prev_factor, 12),
                          "delta_rel": round(factor / prev_factor - 1.0, 12)}
        if factor:
            prev_factor = factor

        segments.append({
            "schema": S.SCHEMA_SEGMENT,
            "symbol_id": run_entries[0]["pair"]["symbol_id"],
            "symbol": run_entries[0]["pair"]["symbol"],
            "timeframe": run_entries[0]["pair"]["timeframe"],
            "timeframe_source": run_entries[0]["pair"].get("timeframe_source", "derived"),
            "segment_index": idx,
            "date_from": date_from,
            "date_to": date_to,
            "n_sessions": n,
            "factor": round(factor, 12) if factor else None,
            "factor_inverse": round(1.0 / factor, 12) if factor else None,
            "factor_convention": "reference_adjusted / product_raw",
            "consensus_fields": sorted(agreeing) if factor else [],
            "dissent_fields": {f: round(v, 12) for f, v in sorted(dissenting.items())},
            "max_rel_residual": None if res_max_rel is None else round(res_max_rel, 12),
            "median_rel_residual": None if res_med_rel is None else round(res_med_rel, 12),
            "max_abs_residual": None if res_max_abs is None else round(res_max_abs, 6),
            "effective_tolerance": round(eff_tol, 12),
            "rounding_limited": bool(rounding_dominated),
            "gaps_absorbed": run.get("gaps_absorbed", 0),
            "evidence": {
                "evidence_kind": "series",
                "n_sessions": n,
                "n_support_sessions": n_support,
                "n_boundaries": 1 if breakpoint else 0,
                "n_field_samples": sum(len(e["ratios"]) for e in support_entries),
                "sessions_skipped_in_group": len(skipped),
                "date_gap_max_days": _max_gap_days(run_entries),
            },
            "cause": cause,
            "cause_basis": basis,
            "breakpoint": breakpoint,
            "event_attribution": attribution,
            "event_evidence": ev_here,
            "confidence": round(confidence, 3),
            "confidence_basis": why,
            "thresholds": {k: v for k, v in opts.items() if k != "fields"},
            "fields_used": list(fields),
            "source_ref": run_entries[0]["pair"].get("source_ref"),
            "source_prod": run_entries[0]["pair"].get("source_prod"),
            "unavailable": ([f for f in fields if f not in agreeing and factor]
                            + ([] if ev_here else ["independent_event_evidence"])
                            + ([] if factor else ["factor"])),
        })

    stats = {"sessions": len(entries), "skipped": len(skipped), "segments": len(segments),
             "breaks": sum(1 for s in segments if s["breakpoint"]),
             "causes": _count(segments, "cause")}
    return segments, stats


def infer_all(pairs, opts, events_by_symbol=None):
    groups = defaultdict(list)
    for p in pairs:
        groups[(p["symbol_id"], p["timeframe"])].append(p)
    segments, per_group = [], {}
    for (sid, tf), grp in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        segs, stats = infer_group(grp, opts, (events_by_symbol or {}).get(sid))
        segments.extend(segs)
        per_group["%s|%s" % (sid, tf)] = stats
    return segments, per_group


def load_pairs(args):
    if args.in_path:
        if args.kind == "candle-diverge":
            return EV.pairs_from_candle_diverge(args.in_path)
        if args.kind == "parity-diverge":
            return EV.pairs_from_parity_diverge(args.in_path)
        raise S.SchemaError("--in supports candle-diverge and parity-diverge")
    if not args.pairs:
        return []
    reader = IO.read_ndjson_gz if str(args.pairs).endswith(".gz") else IO.read_ndjson
    return list(reader(args.pairs))


def main():
    ap = argparse.ArgumentParser(description="Infer effective adjustment factor segments.")
    ap.add_argument("--pairs", default=None, help="paired-row ndjson(.gz) from import_reference")
    ap.add_argument("--in", dest="in_path", default=None, help="frozen ledger to read directly")
    ap.add_argument("--kind", default="candle-diverge",
                    choices=("candle-diverge", "parity-diverge"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default="factor_segments",
                    help="output basename, so a capture run does not overwrite the ledger run")
    ap.add_argument("--fields", default="o,h,l,c",
                    help="fields that vote on the factor (default o,h,l,c)")
    ap.add_argument("--min-fields", type=int, default=DEFAULTS["min_fields"])
    ap.add_argument("--break-tol", type=float, default=DEFAULTS["break_tol"])
    ap.add_argument("--tick", type=float, default=DEFAULTS["tick"])
    ap.add_argument("--min-run", type=int, default=DEFAULTS["min_run"])
    ap.add_argument("--merge-gap", type=int, default=DEFAULTS["merge_gap"],
                    help="unexplained sessions that may be folded back into a regime")
    ap.add_argument("--generated-at", default=None)
    ap.add_argument("--no-sweep", action="store_true")
    a = ap.parse_args()

    fields = tuple(f.strip() for f in a.fields.split(",") if f.strip() in ALL_FIELDS)
    if not fields:
        print("no valid fields in --fields")
        return 2
    opts = {"break_tol": a.break_tol, "tick": a.tick, "min_run": a.min_run,
            "min_fields": a.min_fields, "fields": fields,
            "max_candidates": DEFAULTS["max_candidates"],
            "max_score_rows": DEFAULTS["max_score_rows"],
            "merge_gap": a.merge_gap}

    pairs = load_pairs(a)
    if not pairs:
        print("no paired rows; pass --pairs or --in")
        return 2

    segments, per_group = infer_all(pairs, opts)
    out_path = os.path.join(a.out, a.name + ".ndjson.gz")
    n = IO.write_ndjson_gz(out_path, segments)

    sweep = {}
    if not a.no_sweep:
        for tol in (1e-5, 1e-4, 5e-4, 1e-3, 5e-3):
            segs2, _ = infer_all(pairs, dict(opts, break_tol=tol))
            sweep["%.0e" % tol] = {"segments": len(segs2),
                                   "breaks": sum(1 for s in segs2 if s["breakpoint"])}

    with_factor = [s for s in segments if s["factor"]]
    summary = {
        "schema": S.SCHEMA_SEGMENT,
        "generated_at": a.generated_at or S.now_utc(),
        "inputs": {
            "paired_rows": len(pairs),
            "source": os.path.basename(a.in_path or a.pairs or ""),
            "source_sha256": (S.sha256_file(a.in_path or a.pairs)
                              if (a.in_path or a.pairs) and os.path.exists(a.in_path or a.pairs)
                              else None),
        },
        "thresholds": {k: v for k, v in opts.items() if k != "fields"},
        "thresholds_note": "tool parameters, printed for reproducibility; not a methodology ruling",
        "fields_used": list(fields),
        "totals": {
            "segments": len(segments),
            "segments_with_factor": len(with_factor),
            "breaks": sum(1 for s in segments if s["breakpoint"]),
            "causes": _count(segments, "cause"),
            "attribution": _count(segments, "event_attribution"),
            "confidence_bins": _confidence_bins(segments),
            "sessions_covered": sum(s["n_sessions"] for s in segments),
            "sessions_explained_by_a_scalar": sum(s["n_sessions"] for s in with_factor),
        },
        "sensitivity": sweep,
        "per_group": per_group,
        "file": IO.file_entry(out_path, S.SCHEMA_SEGMENT, rows=n, rel=a.name + ".ndjson.gz"),
    }
    IO.write_json(os.path.join(a.out, a.name.replace("_", "-") + "-summary.json"), summary)
    print("segments: %d (%d with a factor)  breaks: %d  -> %s"
          % (len(segments), len(with_factor), summary["totals"]["breaks"], out_path))
    print("causes: %r" % (summary["totals"]["causes"],))
    if sweep:
        print("break-tol sweep: %r" % (sweep,))
    return 0


def _count(rows, key):
    out = {}
    for r in rows:
        out[r.get(key)] = out.get(r.get(key), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _confidence_bins(rows):
    bins = {"0.0-0.3": 0, "0.3-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    for r in rows:
        c = r.get("confidence") or 0
        if c < 0.3:
            bins["0.0-0.3"] += 1
        elif c < 0.6:
            bins["0.3-0.6"] += 1
        elif c < 0.8:
            bins["0.6-0.8"] += 1
        else:
            bins["0.8-1.0"] += 1
    return bins


if __name__ == "__main__":
    sys.exit(main())