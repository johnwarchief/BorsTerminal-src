#!/usr/bin/env python3
"""Stage 01 - reference-capture plan for the Phase 4.9.1 verification ledgers.

The capture universe (design spec D1) is the union of:

1. every symbol carrying at least one ``unverified`` step in the correction
   pack (the pack only marks a step; the symbol is the capture unit);
2. every symbol with at least one year of history in the Seed DB;
3. the six short-history symbols (they are backfilled in Plan C);
4. optional owner additions (``--extra-symbols``).

Sets are deduplicated by the normalised key from ``dev/symbol_identity.py``,
never by the raw spelling: the pack, the DB and the live asset map may write
one symbol as Arabic-kaf, Persian-kaf or with a leading space, and that must
stay one capture target, not three.

One year of history is measured on the DB's own trading calendar (the distinct
``price_history.date`` values), not on a 365-calendar-day string difference: a
symbol that trades twice a year for a decade is not a year of history. The
calendar's sessions-per-day density converts ``--min-span-days`` into trading
sessions, and a symbol qualifies when that many sessions lie between its first
and last DB date.

The live pack is the only asset-id map (828 symbols). A symbol without an
asset id is *not* dropped and no id is invented for it: it is written to
``capture-unmapped.json`` with ``reason=NO_ASSET_ID`` and counted as a blocker.
If one normalised key carries two different ids in the live pack, the first row
does not silently win: the key is left out of the map, listed under
``asset_map_ambiguous``, and its symbols are written with
``reason=AMBIGUOUS_ASSET_ID`` (plus the conflicting ``asset_ids``).

The Seed DB is opened read-only (``mode=ro``); neither the seed nor the packs
are written. Stdlib only. JSON is deterministic: UTF-8, sorted keys,
``indent=1``, LF, one trailing newline.

CLI:
    python _audit/phase49-full-verification/stage01_capture_plan.py \\
        --db _audit/phase49-finalization/seed/market.db \\
        --pack data/ra365_corrections/ra365-phase49-rebuild-full-v2 \\
        --live-pack data/ra365_corrections/ra365-live40-v1 \\
        --out-dir _audit/phase49-full-verification/capture-plan \\
        [--min-span-days 365] [--extra-symbols extra.json] \\
        [--manifest evidence/stage01_capture_plan.manifest.json]

Outputs (under ``--out-dir``, which is gitignored - a plan, not evidence):

* ``symbols.json`` - ``{asset_id, symbol, ins_code, basis, source}`` for capture;
* ``capture-unmapped.json`` - symbols without an asset id, with ``reason``;
* ``capture-plan.json`` - counts by source and the exact union.

The stage manifest (``evidence/stage01_capture_plan.manifest.json``) carries
the counts and the input/output SHA-256s, so the numbers are trackable without
tracking the 1,097-row plan.
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import date
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEV = os.path.join(ROOT, "dev")
if DEV not in sys.path:
    sys.path.insert(0, DEV)

import phase49_manifest as PM  # noqa: E402
from symbol_identity import key, load_instruments  # noqa: E402

SIX = ("شنفت", "فافق", "فخاس", "فولاژ", "لخزر", "مارون")
SOURCE_ORDER = ("pack-unverified", "long-history", "short-history-six",
                "owner-extra")
DEFAULT_MANIFEST = os.path.join(HERE, "evidence",
                                "stage01_capture_plan.manifest.json")
PLAN_FILES = ("symbols.json", "capture-unmapped.json", "capture-plan.json")


def _abs(path):
    """Resolve a repo-relative path against ROOT; leave absolute paths alone."""
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def _rel(path):
    """Repo-relative POSIX path (portable in the plan; no machine paths)."""
    try:
        rel = os.path.relpath(_abs(path), ROOT)
    except ValueError:  # different drive on Windows
        rel = _abs(path)
    return rel.replace("\\", "/")


def _db_uri(path):
    """Read-only SQLite URI; the Seed DB is never opened writable."""
    return "file:%s?mode=ro" % quote(_abs(path).replace("\\", "/"), safe="/:")


def _write_json(path, payload):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return path


def load_pack(path):
    rows = []
    with open(os.path.join(_abs(path), "factors.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def asset_map(rows):
    """``key(symbol) -> asset_id`` from the live pack; report ambiguous keys.

    A key mapped to two different ids is a real conflict, so the first row must
    not silently win: the key is omitted from ``out`` and recorded in
    ``ambiguous`` as ``key -> sorted ids``. Callers report those symbols with
    ``reason=AMBIGUOUS_ASSET_ID`` instead of treating them as unmapped-by-absence.
    """
    ids_by_key, order = {}, []
    for r in rows:
        k = key(r.get("symbol"))
        aid = r.get("asset_id")
        if not k or aid in (None, ""):
            continue
        if k not in ids_by_key:
            ids_by_key[k] = set()
            order.append(k)
        ids_by_key[k].add(str(aid))
    out, ambiguous = {}, {}
    for k in order:
        ids = ids_by_key[k]
        if len(ids) == 1:
            out[k] = next(iter(ids))
        else:
            ambiguous[k] = sorted(ids)
    return out, ambiguous


def trading_calendar(con):
    """The DB's own trading calendar and the density that turns days to sessions."""
    days = [r[0] for r in con.execute(
        "SELECT DISTINCT date FROM price_history ORDER BY date")]
    span_days = 0
    if len(days) > 1:
        try:
            span_days = (date.fromisoformat(str(days[-1]))
                         - date.fromisoformat(str(days[0]))).days
        except (TypeError, ValueError):
            span_days = 0
    per_day = (len(days) - 1) / span_days if span_days > 0 else 0.0
    meta = {"sessions": len(days),
            "first": days[0] if days else None,
            "last": days[-1] if days else None,
            "span_days": span_days,
            "sessions_per_day": round(per_day, 6)}
    return days, {d: i for i, d in enumerate(days)}, meta


def min_span_sessions(min_span_days, calendar):
    """``--min-span-days`` on the DB calendar: one year of *trading* sessions."""
    per_day = calendar["sessions_per_day"]
    if per_day <= 0:
        # No usable calendar: keep the conservative day count as sessions, so a
        # degenerate DB cannot promote a symbol to a year of history.
        return max(1, int(min_span_days))
    return max(1, int(round(min_span_days * per_day)))


def long_history(db, min_span_days):
    """Symbols spanning at least one calendar-year of DB trading sessions.

    Returns ``(long_syms, meta)`` where ``long_syms`` maps the DB spelling to
    the number of trading sessions elapsed between its first and last date, and
    ``meta`` carries the calendar, the resolved session threshold, the DB
    symbol set and the count of symbols whose dates are not on the calendar.
    """
    con = sqlite3.connect(_db_uri(db), uri=True)
    try:
        days, index, calendar = trading_calendar(con)
        threshold = min_span_sessions(min_span_days, calendar)
        long_syms, db_symbols, unindexed = {}, [], 0
        for sym, first, last in con.execute(
                "SELECT symbol, MIN(date), MAX(date) FROM price_history "
                "GROUP BY symbol"):
            if sym is None:
                continue
            db_symbols.append(sym)
            if first not in index or last not in index:
                unindexed += 1
                continue
            elapsed = index[last] - index[first]
            if elapsed >= threshold:
                long_syms[sym] = elapsed
        meta = {"calendar": calendar, "min_span_sessions": threshold,
                "db_symbols": db_symbols, "unindexed_symbols": unindexed}
        return long_syms, meta
    finally:
        con.close()


def build(db, pack, live_pack, out_dir, min_span_days=365, extra=None):
    pack_rows = load_pack(pack)
    unverified_rows = [r for r in pack_rows if r.get("validity") == "unverified"]
    unverified_raw = {str(r["symbol"]) for r in unverified_rows
                      if r.get("symbol")}
    long_syms, meta = long_history(db, min_span_days)

    con = sqlite3.connect(_db_uri(db), uri=True)
    try:
        inst = load_instruments(con)
    finally:
        con.close()
    db_by_key = {}
    for sym in sorted(meta["db_symbols"]):
        db_by_key.setdefault(key(sym), str(sym).strip())
    db_keys = set(db_by_key)

    live_map, ambiguous = asset_map(load_pack(live_pack))

    scope, source_keys, source_raw, raw_spellings = {}, {}, {}, set()

    def add(sym, source):
        k = key(sym)
        if not k:
            return
        raw_spellings.add(str(sym))
        rec = scope.setdefault(k, {"sources": set(), "spellings": set()})
        rec["sources"].add(source)
        rec["spellings"].add(str(sym))
        source_keys.setdefault(source, set()).add(k)
        source_raw.setdefault(source, set()).add(str(sym))

    for sym in sorted(unverified_raw):
        add(sym, "pack-unverified")
    for sym in sorted(long_syms):
        add(sym, "long-history")
    for sym in SIX:
        add(sym, "short-history-six")
    for item in extra or []:
        add(item.get("symbol") if isinstance(item, dict) else item,
            "owner-extra")

    symbols, unmapped, union = [], [], []
    for k in sorted(scope):
        rec = scope[k]
        sym = db_by_key.get(k) or min(rec["spellings"],
                                      key=lambda s: (len(s), s))
        sources = [s for s in SOURCE_ORDER if s in rec["sources"]]
        aid = live_map.get(k)
        num = None if aid is None else (int(aid) if str(aid).isdigit() else aid)
        union.append({"asset_id": num, "in_db": k in db_keys, "key": k,
                      "mapped": aid is not None, "sources": sources,
                      "symbol": sym})
        if aid is None:
            row = {"in_db": k in db_keys, "key": k, "reason": "NO_ASSET_ID",
                   "sources": sources, "symbol": sym}
            if k in ambiguous:
                row["reason"] = "AMBIGUOUS_ASSET_ID"
                row["asset_ids"] = ambiguous[k]
            unmapped.append(row)
            continue
        symbols.append({"asset_id": num, "symbol": sym,
                        "ins_code": inst.get(k, {}).get("ins_code", ""),
                        "basis": "real_close", "source": ",".join(sources)})

    per_source = {}
    for name in SOURCE_ORDER:
        keys = source_keys.get(name, set())
        per_source[name] = {
            "symbols": len(keys),
            "raw_symbols": len(source_raw.get(name, set())),
            "mapped": sum(1 for k in keys if k in live_map),
            "unmapped": sum(1 for k in keys if k not in live_map),
        }
    per_source["pack-unverified"]["steps"] = len(unverified_rows)
    per_source["short-history-six"]["names"] = list(SIX)

    counts = {
        "asset_map_ambiguous": sorted(ambiguous),
        "asset_map_symbols": len(live_map),
        "long_history": len(source_keys.get("long-history", set())),
        "mapped": len(symbols),
        "owner_extra": len(source_keys.get("owner-extra", set())),
        "pack_steps_unverified": len(unverified_rows),
        "pack_symbols_unverified": len(unverified_raw),
        "pack_unverified": len(source_keys.get("pack-unverified", set())),
        "scope_without_db_history": sum(1 for k in scope if k not in db_keys),
        "short_history_six": len(source_keys.get("short-history-six", set())),
        "union": len(scope),
        "union_by_symbol": len(raw_spellings),
        "unmapped": len(unmapped),
    }
    plan = {
        "calendar": {"first": meta["calendar"]["first"],
                     "last": meta["calendar"]["last"],
                     "sessions": meta["calendar"]["sessions"],
                     "sessions_per_day": meta["calendar"]["sessions_per_day"],
                     "span_days": meta["calendar"]["span_days"],
                     "unindexed_symbols": meta["unindexed_symbols"]},
        "counts": counts,
        "inputs": {"db": _rel(db), "live_pack": _rel(live_pack),
                   "pack": _rel(pack)},
        "min_span_days": min_span_days,
        "min_span_sessions": meta["min_span_sessions"],
        "per_source": per_source,
        "scope": {"six": list(SIX), "sources": list(SOURCE_ORDER)},
        "union": union,
    }
    os.makedirs(out_dir, exist_ok=True)
    _write_json(os.path.join(out_dir, "symbols.json"), symbols)
    _write_json(os.path.join(out_dir, "capture-unmapped.json"), unmapped)
    _write_json(os.path.join(out_dir, "capture-plan.json"), plan)
    return plan


def write_manifest(plan, args):
    """Stage manifest (dev/phase49_manifest.py) - the counts, not the plan."""
    inputs = [_rel(args.db),
              _rel(os.path.join(args.pack, "factors.jsonl")),
              _rel(os.path.join(args.pack, "manifest.json")),
              _rel(os.path.join(args.live_pack, "factors.jsonl"))]
    outputs = [_rel(os.path.join(args.out_dir, name)) for name in PLAN_FILES]
    counts = dict(plan["counts"])
    counts.update({"min_span_days": plan["min_span_days"],
                   "min_span_sessions": plan["min_span_sessions"]})
    return PM.write_manifest("stage01_capture_plan", inputs, outputs, counts,
                             args.manifest)


def _safe_stdout():
    """Never let a non-UTF-8 console turn a printed count into a crash.

    Windows consoles default to cp1252; one Persian symbol name in the summary
    must not raise ``UnicodeEncodeError`` after the plan files are written and
    before the manifest is. Non-UTF-8 streams replace unencodable glyphs; real
    UTF-8 streams are untouched. Streams without ``reconfigure`` (tests, pipes
    wrapped by a harness) are left alone.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="Seed market.db (read-only)")
    ap.add_argument("--pack", required=True, help="correction pack directory")
    ap.add_argument("--live-pack", required=True,
                    help="live reference pack carrying the asset-id map")
    ap.add_argument("--out-dir", required=True,
                    help="gitignored plan directory (symbols/plan/unmapped)")
    ap.add_argument("--min-span-days", type=int, default=365,
                    help="one year on the DB trading calendar (default 365)")
    ap.add_argument("--extra-symbols", default="",
                    help="JSON list of owner additions (optional)")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST,
                    help="stage manifest path ('' disables)")
    a = ap.parse_args(argv)

    _safe_stdout()
    os.chdir(ROOT)
    try:
        extra = []
        if a.extra_symbols:
            with open(_abs(a.extra_symbols), encoding="utf-8") as fh:
                extra = json.load(fh)
            if not isinstance(extra, list):
                raise ValueError("--extra-symbols must be a JSON list")
        plan = build(a.db, a.pack, a.live_pack, a.out_dir, a.min_span_days,
                     extra)
        # Evidence before commentary: the tracked manifest is written before
        # any summary print, so a console that cannot render a symbol name can
        # no longer cost the stage its manifest.
        if a.manifest:
            write_manifest(plan, a)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print("CAPTURE PLAN FAIL: %s" % exc, file=sys.stderr)
        return 2
    # The union lives in capture-plan.json; stdout keeps the reviewable counts.
    shown = {k: v for k, v in plan.items() if k != "union"}
    print(json.dumps(shown, ensure_ascii=False, indent=1, sort_keys=True))
    if a.manifest:
        print("CAPTURE PLAN MANIFEST: %s" % _rel(a.manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
