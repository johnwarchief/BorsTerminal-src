#!/usr/bin/env python3
"""Stage 09 - build the Phase 4.9.1 Seed Candidate and its final manifest.

The candidate is a consistent copy of the backfilled work database plus the
three provenance tables the app reads (``adjust_pack_state``,
``history_validity``, ``seed_manifest``), vacuumed and compressed twice:

* ``market.db.lzma`` is the canonical XZ stream (preset ``9 | EXTREME``) with a
  round-trip SHA-256 proof;
* ``market.db.gz`` is the fast-boot stream built by
  ``scripts/make_fast_seed.py --force`` and decoded back to the same SHA-256.

``FINAL-SEED-MANIFEST.json`` records the hashes, sizes and counts the release
gate needs. It carries aggregates only: no raw rows, no symbol lists.

Inputs (base candidate, work database, pack, ledgers, capture summary) are
opened read-only; only ``--out-dir`` is written. The build is idempotent:
rerunning with ``--force`` replaces the four artifacts and yields the same
counts and statuses. Without ``--force`` a non-empty out directory is refused.

The real build waits for the C3 backfill. ``build_metadata`` is the testable
core: it needs no files and works on an in-memory connection.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import lzma
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MAKE_FAST_SEED = os.path.join(ROOT, "scripts", "make_fast_seed.py")
CHUNK = 1 << 22

SEED_SCHEMA = "phase49-full-verification-seed-v1"
MANIFEST_SCHEMA = "phase49-full-verification-final-seed-manifest-v1"
MANIFEST_NAME = "FINAL-SEED-MANIFEST.json"

# The six mission statuses map onto the three labels the app already knows.
# The detailed mission status stays in ``history_validity.notes``.
STATUS_MAP = {
    "VERIFIED_WITH_EVENTS": "verified",
    "VERIFIED_NO_APPLICABLE_EVENT": "verified",
    "RECONSTRUCTED_VERIFIED": "reconstructed_verified",
    "CONFLICT": "unverified",
    "BLOCKED_SOURCE": "unverified",
    "INSUFFICIENT_EVIDENCE": "unverified",
}

HISTORY_VALIDITY_SQL = """CREATE TABLE IF NOT EXISTS history_validity(
    symbol TEXT PRIMARY KEY, rows INTEGER, first_date TEXT, last_date TEXT,
    reference_coverage TEXT, ref_days INTEGER, ref_first TEXT, ref_last TEXT,
    factor_steps INTEGER, factor_verified INTEGER,
    factor_reconstructed INTEGER, factor_unverified INTEGER,
    raw_open_verified INTEGER, raw_open_corrected INTEGER,
    factor_parity TEXT, adjusted_max_abs REAL, status TEXT, notes TEXT)"""

ADJUST_PACK_STATE_SQL = """CREATE TABLE adjust_pack_state(
    version TEXT PRIMARY KEY, mode TEXT, as_of TEXT, factors_sha256 TEXT,
    raw_ohlc_sha256 TEXT, reference_sha256 TEXT, applied_at TEXT,
    steps INTEGER, symbols INTEGER, verified_steps INTEGER,
    reconstructed_verified_steps INTEGER, unverified_steps INTEGER,
    invalid_dropped_steps INTEGER)"""

SEED_MANIFEST_SQL = "CREATE TABLE IF NOT EXISTS seed_manifest(key TEXT PRIMARY KEY, value TEXT)"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _rel(path):
    """Repo-relative POSIX path; absolute when the two are on different drives."""
    try:
        value = os.path.relpath(os.path.abspath(path), ROOT)
    except ValueError:
        value = os.path.abspath(path)
    return value.replace("\\", "/")


def _db_uri(path):
    return "file:%s?mode=ro" % quote(os.path.abspath(path).replace("\\", "/"),
                                     safe="/:")


def _read_json(path, what):
    with open(path, encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except ValueError as exc:
            raise ValueError("%s %s is not valid JSON: %s" % (what, path, exc))


def _int(value, what, default=None):
    """An int from a ledger/JSON scalar; blanks become ``default``."""
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError("%s is not an integer: %r" % (what, value))


def _text(value):
    return "" if value is None else str(value)


def _merged(ref):
    return (ref or {}).get("merged") or {}


def _capture_sha(ref):
    """The reference provenance hash: explicit top-level, else the merged index."""
    ref = ref or {}
    merged = _merged(ref)
    index = merged.get("reference_index_all") or {}
    return _text(ref.get("capture_sha256") or ref.get("sha256")
                 or index.get("sha256")
                 or merged.get("aggregate_capture_sha256") or "")


def _captured_at(ref):
    ref = ref or {}
    source = ref.get("source")
    if isinstance(source, dict) and source.get("captured_at"):
        return _text(source["captured_at"])
    capture = ref.get("capture") or {}
    extra = ref.get("extra") or {}
    return _text(ref.get("captured_at") or capture.get("captured_at_max")
                 or extra.get("captured_at") or "")


def _reference_index_sha(ref):
    index = _merged(ref).get("reference_index_all") or {}
    return _text(index.get("sha256") or "")


def _aggregate_capture_sha(ref):
    return _text(_merged(ref).get("aggregate_capture_sha256") or "")


def _stored(value):
    """How a manifest value is stored in ``seed_manifest.value``."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def load_pack(path):
    """Read a correction pack and prove its declared file hashes."""
    manifest_path = os.path.join(path, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise ValueError("correction pack has no manifest.json: %s" % manifest_path)
    data = _read_json(manifest_path, "correction pack")
    if not isinstance(data, dict):
        raise ValueError("%s: expected a JSON object" % manifest_path)
    if not data.get("version"):
        raise ValueError("%s: pack manifest has no version" % manifest_path)
    files = data.get("files") or {}
    declared = data.get("file_sha256") or {}
    for name in ("factors", "raw_ohlc"):
        member = files.get(name)
        expected = declared.get(name) or data.get(name + "_sha256")
        if not member or not expected:
            raise ValueError("%s: pack manifest does not declare %s file/hash"
                             % (manifest_path, name))
        member_path = os.path.join(path, member)
        if not os.path.isfile(member_path):
            raise ValueError("pack file is missing: %s" % member_path)
        actual = sha256(member_path)
        if actual != expected:
            raise ValueError("pack %s sha256 mismatch: declared %s, actual %s"
                             % (name, expected, actual))
    data["_manifest_sha256"] = sha256(manifest_path)
    return data


def load_steps(path):
    """Read the adjustment evidence ledger; it must have symbols."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        names = reader.fieldnames or []
        if "symbol" not in names:
            raise ValueError("%s: step ledger has no 'symbol' column (columns: %s)"
                             % (path, ", ".join(names) or "none"))
        rows = []
        for number, row in enumerate(reader, start=2):
            symbol = _text(row.get("symbol"))
            if not symbol.strip():
                raise ValueError("%s row %d: empty symbol" % (path, number))
            row["symbol"] = symbol
            rows.append(row)
    return rows


def load_symbols(path):
    """Read the history-coverage ledger used for ``history_validity``."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        names = reader.fieldnames or []
        for column in ("symbol", "final_status"):
            if column not in names:
                raise ValueError("%s: symbol ledger has no %r column (columns: %s)"
                                 % (path, column, ", ".join(names) or "none"))
        rows = []
        for number, row in enumerate(reader, start=2):
            # Keep the ledger's exact symbol: two symbols carry a significant
            # leading/trailing space and the same bytes key price_history.
            symbol = _text(row.get("symbol"))
            if not symbol.strip():
                raise ValueError("%s row %d: empty symbol" % (path, number))
            status = _text(row.get("final_status")).strip()
            if not status:
                raise ValueError("%s row %d (%s): empty final_status"
                                 % (path, number, symbol))
            rows.append({
                "symbol": symbol,
                "final_status": status,
                "rows": _int(row.get("rows"), "%s row %d rows" % (path, number)),
                "first_date": row.get("first_date") or None,
                "last_date": row.get("last_date") or None,
                "ref_coverage": row.get("ref_coverage") or None,
                "factor_steps": _int(row.get("factor_steps"),
                                     "%s row %d factor_steps" % (path, number), 0),
                "factor_verified": _int(row.get("factor_verified"),
                                        "%s row %d factor_verified" % (path, number), 0),
                "factor_reconstructed": _int(
                    row.get("factor_reconstructed"),
                    "%s row %d factor_reconstructed" % (path, number), 0),
                "factor_unverified": _int(row.get("factor_unverified"),
                                          "%s row %d factor_unverified" % (path, number), 0),
                "remaining_blocker": _text(row.get("remaining_blocker")).strip(),
            })
    return rows


def load_reference_summary(path):
    """Read the capture summary; a capture hash is required for provenance."""
    data = _read_json(path, "reference summary")
    if not isinstance(data, dict):
        raise ValueError("%s: expected a JSON object" % path)
    if not _capture_sha(data):
        raise ValueError("%s: reference summary has no capture_sha256" % path)
    return data


def build_metadata(con, pack, steps, symbols, ref):
    """Write the three seed provenance tables and return the manifest dict.

    This is the unit-tested core: ``con`` may be an in-memory connection, and
    no file is read. Calling it twice on the same connection leaves exactly one
    row per symbol and the same counts.
    """
    con.execute(HISTORY_VALIDITY_SQL)
    con.execute(SEED_MANIFEST_SQL)
    con.execute("DELETE FROM history_validity")

    counts = collections.Counter()
    seen = set()
    for row in symbols:
        symbol = _text(row.get("symbol"))
        if not symbol.strip():
            raise ValueError("symbol ledger row has an empty symbol")
        if symbol in seen:
            raise ValueError("duplicate symbol in symbol ledger: %s" % symbol)
        seen.add(symbol)
        detailed = _text(row.get("final_status")).strip()
        if detailed not in STATUS_MAP:
            raise ValueError(
                "symbol %s has unknown final_status %r; expected one of %s"
                % (symbol, detailed, ", ".join(sorted(STATUS_MAP))))
        status = STATUS_MAP[detailed]
        blocker = _text(row.get("remaining_blocker"))
        notes = "%s; blocker=%s" % (detailed, blocker)
        con.execute("""INSERT OR REPLACE INTO history_validity VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (symbol,
                     _int(row.get("rows"), "rows for %s" % symbol),
                     row.get("first_date"), row.get("last_date"),
                     row.get("ref_coverage"), None, None, None,
                     _int(row.get("factor_steps"), "factor_steps for %s" % symbol, 0),
                     _int(row.get("factor_verified"), "factor_verified for %s" % symbol, 0),
                     _int(row.get("factor_reconstructed"),
                          "factor_reconstructed for %s" % symbol, 0),
                     _int(row.get("factor_unverified"),
                          "factor_unverified for %s" % symbol, 0),
                     None, None, None, None, status, notes))
        counts[status] += 1

    ref_rows = con.execute(
        "SELECT COUNT(*) FROM price_history WHERE src='rahavard365'").fetchone()[0]
    step_symbols = {_text(s.get("symbol")).strip() for s in (steps or [])}
    step_symbols.discard("")
    manifest = {
        "schema": SEED_SCHEMA,
        "pack_version": (pack or {}).get("version"),
        "pack_factors_sha256": ((pack or {}).get("file_sha256") or {}).get("factors", ""),
        "reference_derived_rows": ref_rows,
        "reference_capture_sha256": _capture_sha(ref),
        "reference_index_sha256": _reference_index_sha(ref),
        "aggregate_capture_sha256": _aggregate_capture_sha(ref),
        "reference_captured_at": _captured_at(ref),
        "validity_status_counts": dict(sorted(counts.items())),
        "adjustment_step_ledger_rows": len(steps or []),
        "adjustment_step_ledger_symbols": len(step_symbols),
    }
    con.execute("DELETE FROM seed_manifest")
    for key, value in manifest.items():
        con.execute("INSERT INTO seed_manifest VALUES(?,?)",
                    (key, _stored(value)))
    return manifest


def write_pack_state(con, pack, applied_at):
    """Recreate ``adjust_pack_state`` from the pack manifest, not old parity."""
    con.execute("DROP TABLE IF EXISTS adjust_pack_state")
    con.execute(ADJUST_PACK_STATE_SQL)
    counts = (pack or {}).get("counts") or {}
    con.execute("INSERT INTO adjust_pack_state VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ((pack or {}).get("version", ""),
                 (pack or {}).get("mode", ""),
                 (pack or {}).get("as_of", ""),
                 ((pack or {}).get("file_sha256") or {}).get("factors", ""),
                 ((pack or {}).get("file_sha256") or {}).get("raw_ohlc", ""),
                 (pack or {}).get("reference_sha256", ""),
                 applied_at,
                 _int(counts.get("steps"), "pack counts.steps", 0),
                 _int(counts.get("symbols"), "pack counts.symbols", 0),
                 _int(counts.get("verified_steps"), "pack counts.verified_steps", 0),
                 _int(counts.get("reconstructed_verified_steps"),
                      "pack counts.reconstructed_verified_steps", 0),
                 _int(counts.get("unverified_steps"),
                      "pack counts.unverified_steps", 0),
                 _int(counts.get("invalid_dropped_steps"),
                      "pack counts.invalid_dropped_steps", 0)))


def _read_db_summary(path):
    """Read-only counts the build needs from base/work databases."""
    con = sqlite3.connect(_db_uri(path), uri=True)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        if "price_history" not in tables:
            raise ValueError("%s has no price_history table" % path)
        rows, symbols = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT symbol) FROM price_history").fetchone()
        users = {}
        for name in sorted(tables):
            if name.startswith("user_"):
                users[name] = con.execute(
                    'SELECT COUNT(*) FROM "%s"' % name.replace('"', '""')).fetchone()[0]
    finally:
        con.close()
    return {"price_history_rows": rows, "symbols_with_history": symbols,
            "user_tables": users}


def _check_checkpointed(path, what):
    for suffix in ("-wal", "-journal"):
        sidecar = path + suffix
        if os.path.isfile(sidecar) and os.path.getsize(sidecar) > 0:
            raise ValueError(
                "%s database has a pending %s sidecar (%s); close or "
                "checkpoint the database first"
                % (what, suffix.lstrip("-"), sidecar))


def _copy_work(work, seed):
    _check_checkpointed(work, "work")
    shutil.copy2(work, seed)


def _hash_decompressed(path, opener):
    h = hashlib.sha256()
    with opener(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def compress_xz(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    with open(src, "rb") as fin, lzma.open(
            dst, "wb", format=lzma.FORMAT_XZ,
            preset=9 | lzma.PRESET_EXTREME) as fout:
        shutil.copyfileobj(fin, fout, CHUNK)


def build_gzip(src_lzma, dst_gz):
    if not os.path.isfile(MAKE_FAST_SEED):
        raise ValueError("fast seed builder is missing: %s" % MAKE_FAST_SEED)
    proc = subprocess.run(
        [sys.executable, MAKE_FAST_SEED, "--force", src_lzma, dst_gz],
        cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ValueError("make_fast_seed failed (%d): %s"
                         % (proc.returncode, (proc.stderr or proc.stdout).strip()))


def _write_json(path, payload):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def build(base, work, pack_path, steps_path, symbols_path, ref_path,
          out_dir, force=False):
    """Build the candidate and return the final manifest dict."""
    inputs = (("base", base), ("work", work),
              ("steps ledger", steps_path), ("symbol ledger", symbols_path),
              ("reference summary", ref_path))
    for label, path in inputs:
        if not os.path.isfile(path):
            raise ValueError("%s not found: %s" % (label, path))
    if not os.path.isdir(pack_path):
        raise ValueError("pack not found: %s" % pack_path)

    pack = load_pack(pack_path)
    steps = load_steps(steps_path)
    symbols = load_symbols(symbols_path)
    ref = load_reference_summary(ref_path)
    base_summary = _read_db_summary(base)
    _check_checkpointed(work, "work")
    work_summary = _read_db_summary(work)
    if work_summary["price_history_rows"] < base_summary["price_history_rows"]:
        raise ValueError(
            "work database has fewer price_history rows than the base "
            "(%d < %d); refusing to build a smaller candidate"
            % (work_summary["price_history_rows"],
               base_summary["price_history_rows"]))
    lost = sorted(set(base_summary["user_tables"]) - set(work_summary["user_tables"]))
    if lost:
        raise ValueError("work database lost user tables present in the base: %s"
                         % ", ".join(lost))
    reduced = {name: (base_summary["user_tables"][name],
                      work_summary["user_tables"][name])
               for name in base_summary["user_tables"]
               if work_summary["user_tables"].get(name, 0)
               < base_summary["user_tables"][name]}
    if reduced:
        raise ValueError("work database lost user rows: %s" % reduced)

    if os.path.exists(out_dir) and not os.path.isdir(out_dir):
        raise ValueError("out path is not a directory: %s" % out_dir)
    existing = os.listdir(out_dir) if os.path.isdir(out_dir) else []
    if existing and not force:
        raise ValueError(
            "out directory %s is not empty (%d entries); pass --force to "
            "rebuild the candidate" % (out_dir, len(existing)))
    os.makedirs(out_dir, exist_ok=True)

    seed = os.path.join(out_dir, "market.db")
    seed_lzma = seed + ".lzma"
    seed_gz = seed + ".gz"
    manifest_path = os.path.join(out_dir, MANIFEST_NAME)
    if force:
        for path in (manifest_path, seed, seed_lzma, seed_gz):
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.exists(path):
                raise ValueError("refusing to replace a non-file: %s" % path)
    _copy_work(work, seed)

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    con = sqlite3.connect(seed)
    try:
        con.execute("PRAGMA journal_mode=DELETE")
        for table in ("adjust_pack_state", "history_validity", "seed_manifest"):
            con.execute("DROP TABLE IF EXISTS %s" % table)
        write_pack_state(con, pack, now)
        metadata = build_metadata(con, pack, steps, symbols, ref)

        rows, db_symbols = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT symbol) FROM price_history").fetchone()
        db_symbols_set = {r[0] for r in con.execute(
            "SELECT DISTINCT symbol FROM price_history")}
        ledger_symbols = {row["symbol"] for row in symbols}
        missing = db_symbols_set - ledger_symbols
        ledger_without_history = ledger_symbols - db_symbols_set

        if "raw_history_corrections" in {
                r[0] for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}:
            corrections, correction_symbols = con.execute(
                "SELECT COUNT(*), COUNT(DISTINCT symbol) "
                "FROM raw_history_corrections").fetchone()
        else:
            corrections = correction_symbols = 0

        seed_users = {}
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        for name in sorted(tables):
            if name.startswith("user_"):
                seed_users[name] = con.execute(
                    'SELECT COUNT(*) FROM "%s"' % name.replace('"', '""')).fetchone()[0]

        extras = {
            "created_at": now,
            "price_history_rows": rows,
            "symbols_with_history": db_symbols,
            "pack_reference_sha256": pack.get("reference_sha256", ""),
            "reference_index_sha256": _reference_index_sha(ref),
            "aggregate_capture_sha256": _aggregate_capture_sha(ref),
            "open_corrections": corrections,
            "open_corrections_symbols": correction_symbols,
            "provenance": "rahavard365 licensed footprint (phase48 + phase49 "
                          "backfill) + phase49 reference-verified adjustment pack",
        }
        for key, value in extras.items():
            con.execute("INSERT OR REPLACE INTO seed_manifest VALUES(?,?)",
                        (key, _stored(value)))
        metadata.update(extras)

        duplicates = con.execute(
            "SELECT COUNT(*) FROM (SELECT symbol, date FROM price_history "
            "GROUP BY symbol, date HAVING COUNT(*) > 1)").fetchone()[0]
        con.commit()
        stored_manifest = dict(con.execute("SELECT key, value FROM seed_manifest"))
        con.execute("VACUUM")
        con.commit()
        integrity = [r[0] for r in con.execute("PRAGMA integrity_check")]
    finally:
        con.close()

    _check_checkpointed(seed, "seed")
    if integrity != ["ok"]:
        raise ValueError("seed integrity_check failed: %s" % ", ".join(integrity))
    if duplicates:
        raise ValueError("seed has %d duplicate (symbol,date) pairs" % duplicates)
    if not rows:
        raise ValueError("seed has no price_history rows")
    if metadata["reference_derived_rows"] <= 0:
        raise ValueError("seed has no reference-derived rows (src='rahavard365')")
    if missing:
        raise ValueError(
            "%d price_history symbols have no history_validity row: %s"
            % (len(missing), ", ".join(sorted(missing)[:5])))
    lost = sorted(set(base_summary["user_tables"]) - set(seed_users))
    if lost:
        raise ValueError("seed lost user tables present in the base: %s"
                         % ", ".join(lost))
    reduced = {name: (base_summary["user_tables"][name],
                      seed_users.get(name, 0))
               for name in base_summary["user_tables"]
               if seed_users.get(name, 0) < base_summary["user_tables"][name]}
    if reduced:
        raise ValueError("seed lost user rows: %s" % reduced)

    compress_xz(seed, seed_lzma)
    roundtrip_lzma = _hash_decompressed(seed_lzma, lzma.open)
    build_gzip(seed_lzma, seed_gz)
    roundtrip_gz = _hash_decompressed(seed_gz, gzip.open)

    db_sha = sha256(seed)
    if roundtrip_lzma != db_sha:
        raise ValueError("lzma round-trip SHA-256 mismatch")
    if roundtrip_gz != db_sha:
        raise ValueError("gzip round-trip SHA-256 mismatch")

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "created_at": now,
        "out_dir": _rel(out_dir),
        "inputs": {
            "base": {
                "path": _rel(base),
                "sha256": sha256(base),
                "size": os.path.getsize(base),
                "price_history_rows": base_summary["price_history_rows"],
                "symbols_with_history": base_summary["symbols_with_history"],
                "user_tables": base_summary["user_tables"],
            },
            "work": {
                "path": _rel(work),
                "sha256": sha256(work),
                "size": os.path.getsize(work),
                "price_history_rows": work_summary["price_history_rows"],
                "symbols_with_history": work_summary["symbols_with_history"],
                "user_tables": work_summary["user_tables"],
            },
            "pack": {
                "path": _rel(pack_path),
                "version": pack.get("version"),
                "mode": pack.get("mode"),
                "as_of": pack.get("as_of"),
                "manifest_sha256": pack.get("_manifest_sha256"),
                "factors_sha256": (pack.get("file_sha256") or {}).get("factors", ""),
                "raw_ohlc_sha256": (pack.get("file_sha256") or {}).get("raw_ohlc", ""),
                "reference_sha256": pack.get("reference_sha256", ""),
                "counts": pack.get("counts") or {},
            },
            "steps_ledger": {
                "path": _rel(steps_path),
                "sha256": sha256(steps_path),
                "rows": len(steps),
            },
            "symbols_ledger": {
                "path": _rel(symbols_path),
                "sha256": sha256(symbols_path),
                "rows": len(symbols),
            },
            "reference_summary": {
                "path": _rel(ref_path),
                "sha256": sha256(ref_path),
                "capture_sha256": metadata["reference_capture_sha256"],
                "reference_index_sha256": metadata["reference_index_sha256"],
                "aggregate_capture_sha256": metadata["aggregate_capture_sha256"],
                "captured_at": metadata["reference_captured_at"],
            },
        },
        "seed_db": {
            "path": _rel(seed),
            "sha256": db_sha,
            "size": os.path.getsize(seed),
        },
        "seed_lzma": {
            "path": _rel(seed_lzma),
            "sha256": sha256(seed_lzma),
            "size": os.path.getsize(seed_lzma),
            "format": "xz",
            "preset": "9|EXTREME",
            "roundtrip_sha256": roundtrip_lzma,
            "roundtrip_ok": roundtrip_lzma == db_sha,
        },
        "seed_gzip": {
            "path": _rel(seed_gz),
            "sha256": sha256(seed_gz),
            "size": os.path.getsize(seed_gz),
            "roundtrip_sha256": roundtrip_gz,
            "roundtrip_ok": roundtrip_gz == db_sha,
        },
        "counts": {
            "price_history_rows": rows,
            "symbols_with_history": db_symbols,
            "history_validity_rows": len(symbols),
            "reference_derived_rows": metadata["reference_derived_rows"],
            "open_corrections": corrections,
            "open_corrections_symbols": correction_symbols,
            "user_watchlists_rows": seed_users.get("user_watchlists", 0),
            "symbols_in_db_missing_from_ledger": len(missing),
            "ledger_symbols_without_history": len(ledger_without_history),
            "adjustment_step_ledger_rows": len(steps),
            "adjustment_step_ledger_symbols": metadata[
                "adjustment_step_ledger_symbols"],
            "rows_added_vs_base": rows - base_summary["price_history_rows"],
        },
        # Convenience copies for the release-gate checks; the same numbers
        # are above in ``counts`` and in the DB's ``seed_manifest``.
        "price_history_rows": rows,
        "symbols_with_history": db_symbols,
        "reference_derived_rows": metadata["reference_derived_rows"],
        "validity_status_counts": metadata["validity_status_counts"],
        "roundtrip_ok": roundtrip_lzma == db_sha and roundtrip_gz == db_sha,
        "integrity": {
            "integrity_check": integrity[0] if integrity else "missing",
            "duplicate_pairs": duplicates,
            "ok": integrity == ["ok"] and duplicates == 0,
        },
        "user_data": {
            "base_tables": base_summary["user_tables"],
            "seed_tables": seed_users,
            "preserved": not (set(base_summary["user_tables"]) - set(seed_users)),
        },
        "seed_manifest": stored_manifest,
    }
    _write_json(manifest_path, manifest)
    print("seed build OK: db=%s lzma=%s gzip=%s manifest=%s"
          % (manifest["seed_db"]["sha256"][:12],
             manifest["seed_lzma"]["sha256"][:12],
             manifest["seed_gzip"]["sha256"][:12], manifest_path))
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Build the Phase 4.9.1 Seed Candidate and its final manifest.")
    ap.add_argument("--base", required=True,
                    help="the previous seed candidate (read-only)")
    ap.add_argument("--work", required=True,
                    help="the backfilled work database (read-only)")
    ap.add_argument("--pack", required=True,
                    help="the v2 correction pack directory")
    ap.add_argument("--steps", required=True,
                    help="ADJUSTMENT-EVIDENCE-LEDGER.csv")
    ap.add_argument("--symbols", required=True,
                    help="HISTORY-COVERAGE-LEDGER.csv")
    ap.add_argument("--reference-summary", required=True,
                    help="capture-summary.json")
    ap.add_argument("--out-dir", required=True,
                    help="seed directory to create")
    ap.add_argument("--force", action="store_true",
                    help="replace the four artifacts in a non-empty out dir")
    args = ap.parse_args(argv)
    try:
        build(args.base, args.work, args.pack, args.steps, args.symbols,
              args.reference_summary, args.out_dir, force=args.force)
    except (OSError, ValueError, sqlite3.Error, lzma.LZMAError) as exc:
        sys.stderr.write("stage09_seed_build: %s\n" % exc)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
