# -*- coding: utf-8 -*-
"""dev/test_codal_snapshot_meta_v11.py — Task 4: snapshot metadata.

Proves, on a throwaway DB built with codal_fetcher.create_schema/migrate_schema:

  1) ``build_snapshot`` writes the lzma and a meta JSON with the required
     schema_version / published_at / latest periods / row_counts / sha256 /
     size / min_client_version / calendar_version fields;
  2) sha256 and size describe the lzma bytes actually on disk;
  3) the decompressed lzma carries exactly the three CODAL tables (plus their
     indexes) — no codal_extracted, no price_history;
  4) a missing source table raises from build_snapshot, and ``main()`` still
     returns non-zero with a clear message;
  5) the CLI wrapper keeps ``-o/--out`` and defaults ``--meta`` to
     ``<out>.meta.json``.

No network, no ADB, no operational market.db: temp files only.
Run:  python dev/test_codal_snapshot_meta_v11.py
"""
import contextlib
import datetime
import hashlib
import io
import json
import lzma
import os
import shutil
import sqlite3
import sys
import tempfile

try:                       # Persian/UTF-8 output on a cp1252 Windows console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import bors_config as BC          # noqa: E402  (APP_VERSION)
import codal_fetcher as cf        # noqa: E402  (create_schema/migrate_schema)
import scripts.build_codal_snapshot as B  # noqa: E402  (build_snapshot/main)

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return bool(cond)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


REQUIRED_META = ("schema_version", "published_at", "latest_financial_period",
                 "latest_monthly_period", "row_counts", "sha256", "size",
                 "min_client_version", "calendar_version")

tmp = tempfile.mkdtemp(prefix="codal_snap_meta_")
try:
    db = os.path.join(tmp, "source.db")
    lz = os.path.join(tmp, "codal.db.lzma")
    meta_path = os.path.join(tmp, "codal.meta.json")

    conn = sqlite3.connect(db)
    cf.create_schema(conn)
    cf.migrate_schema(conn)
    conn.execute(
        "INSERT INTO financial_statements (tracing_no, symbol, period_end) "
        "VALUES (?,?,?)", (101, "TEST", "1405/06/31"))
    conn.execute(
        "INSERT INTO monthly_sales (tracing_no, symbol, period_end) "
        "VALUES (?,?,?)", (202, "TEST", "1405/07/30"))
    conn.commit()
    conn.close()

    meta = B.build_snapshot(db, lz, meta_path)

    # ── meta shape and values ────────────────────────────────────────────
    ck(isinstance(meta, dict), "build_snapshot returns a dict")
    missing = [k for k in REQUIRED_META if k not in meta]
    ck(not missing, "meta has all required keys (missing: %r)" % (missing,))
    ck(meta.get("schema_version") == 1, "schema_version == 1")
    ck(meta.get("latest_financial_period") == "1405/06/31",
       "latest_financial_period == 1405/06/31 (got %r)"
       % (meta.get("latest_financial_period"),))
    ck(meta.get("latest_monthly_period") == "1405/07/30",
       "latest_monthly_period == 1405/07/30 (got %r)"
       % (meta.get("latest_monthly_period"),))
    ck(meta.get("row_counts") == {"codal_notices": 0,
                                  "financial_statements": 1,
                                  "monthly_sales": 1},
       "row_counts cover the three CODAL tables (got %r)"
       % (meta.get("row_counts"),))
    ck(meta.get("min_client_version") == BC.APP_VERSION,
       "min_client_version == bors_config.APP_VERSION (%r != %r)"
       % (meta.get("min_client_version"), BC.APP_VERSION))
    ck(meta.get("calendar_version") == "",
       "calendar_version is empty for now (got %r)"
       % (meta.get("calendar_version"),))
    ck(isinstance(meta.get("sha256"), str) and len(meta["sha256"]) == 64,
       "sha256 is 64 hex chars")

    # ── published_at is fresh UTC ISO ────────────────────────────────────
    try:
        pub = datetime.datetime.fromisoformat(meta["published_at"])
        ck(pub.tzinfo is not None and pub.utcoffset() == datetime.timedelta(0),
           "published_at is UTC (got %r)" % (meta["published_at"],))
        now = datetime.datetime.now(datetime.timezone.utc)
        ck(abs((now - pub).total_seconds()) < 300,
           "published_at is fresh (got %r)" % (meta["published_at"],))
    except Exception as e:
        ck(False, "published_at is ISO-8601 parseable (%r: %s)"
           % (meta.get("published_at"), e))

    # ── lzma bytes on disk match the meta ────────────────────────────────
    ck(os.path.isfile(lz) and os.path.getsize(lz) > 0,
       "lzma exists and is non-empty")
    ck(meta.get("size") == os.path.getsize(lz),
       "meta size == file size (%r != %r)"
       % (meta.get("size"), os.path.getsize(lz)))
    ck(meta.get("sha256") == sha256_file(lz),
       "meta sha256 == sha256(lzma on disk)")
    ck(not os.path.exists(lz + ".raw.db"),
       "build_snapshot removes its .raw.db scratch file")

    # ── meta JSON on disk ────────────────────────────────────────────────
    ck(os.path.isfile(meta_path), "meta JSON exists")
    with open(meta_path, encoding="utf-8") as f:
        on_disk = json.load(f)
    ck(on_disk == meta, "meta JSON on disk equals the returned dict")
    ck(on_disk.get("sha256") == sha256_file(lz),
       "meta JSON sha256 == sha256(lzma on disk)")

    # ── decompressed lzma: three CODAL tables only ───────────────────────
    raw = os.path.join(tmp, "snapshot.raw.db")
    with lzma.open(lz, "rb") as fin, open(raw, "wb") as fout:
        shutil.copyfileobj(fin, fout, 1 << 20)

    snap = sqlite3.connect(raw)
    try:
        tables = {r[0] for r in snap.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        ck(tables == set(B.TABLES),
           "lzma contains only the three CODAL tables (got %r)" % (tables,))
        ck(not ({"codal_extracted", "price_history"} & tables),
           "lzma excludes codal_extracted/price_history")
        idx_tables = {r[0] for r in snap.execute(
            "SELECT tbl_name FROM sqlite_master WHERE type='index' "
            "AND sql IS NOT NULL")}
        ck(idx_tables == set(B.TABLES),
           "lzma indexes belong only to the three CODAL tables (got %r)"
           % (idx_tables,))
        counts = {t: snap.execute(
            "SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in B.TABLES}
        ck(counts == meta["row_counts"],
           "snapshot row counts match meta (%r != %r)"
           % (counts, meta["row_counts"]))
        ck(snap.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
           "snapshot integrity_check is ok")
    finally:
        snap.close()
        os.remove(raw)

    # ── missing source table: build_snapshot raises, main exits non-zero ──
    db_bad = os.path.join(tmp, "missing_table.db")
    shutil.copyfile(db, db_bad)
    bad = sqlite3.connect(db_bad)
    bad.execute("DROP TABLE codal_notices")
    bad.commit()
    bad.close()

    raised = None
    try:
        B.build_snapshot(db_bad, os.path.join(tmp, "bad.lzma"),
                         os.path.join(tmp, "bad.meta.json"))
    except Exception as e:          # noqa: BLE001 — the type is asserted below
        raised = e
    ck(raised is not None and "codal_notices" in str(raised),
       "missing source table raises with the table name (got %r)" % (raised,))
    ck(not os.path.exists(os.path.join(tmp, "bad.lzma")),
       "missing table leaves no lzma behind")

    argv = sys.argv
    out = io.StringIO()
    try:
        sys.argv = ["build_codal_snapshot.py", db_bad,
                    "-o", os.path.join(tmp, "bad_cli.lzma"),
                    "--meta", os.path.join(tmp, "bad_cli.meta.json")]
        with contextlib.redirect_stdout(out):
            rc = B.main()
    finally:
        sys.argv = argv
    ck(rc != 0, "main() returns non-zero on a missing table (got %r)" % (rc,))
    ck("codal_notices" in out.getvalue() and "missing" in out.getvalue(),
       "main() prints a clear missing-table message (got %r)"
       % (out.getvalue(),))

    # ── CLI wrapper: -o works, --meta defaults to <out>.meta.json ────────
    lz_cli = os.path.join(tmp, "cli.db.lzma")
    argv = sys.argv
    out = io.StringIO()
    try:
        sys.argv = ["build_codal_snapshot.py", db, "-o", lz_cli]
        with contextlib.redirect_stdout(out):
            rc = B.main()
    finally:
        sys.argv = argv
    ck(rc == 0, "main() returns 0 on a good db (got %r)" % (rc,))
    ck(os.path.isfile(lz_cli) and os.path.getsize(lz_cli) > 0,
       "CLI -o writes the lzma")
    cli_meta_path = lz_cli + ".meta.json"
    ck(os.path.isfile(cli_meta_path),
       "CLI --meta defaults to <out>.meta.json")
    with open(cli_meta_path, encoding="utf-8") as f:
        cli_meta = json.load(f)
    ck(cli_meta.get("sha256") == sha256_file(lz_cli),
       "default meta JSON sha256 matches the CLI lzma")
    ck(not os.path.exists(lz_cli + ".raw.db"),
       "CLI build leaves no .raw.db scratch file")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

failed = [m for ok, m in CHECKS if not ok]
print("%d PASS / %d FAIL" % (len(CHECKS) - len(failed), len(failed)))
for m in failed:
    print("FAIL: %s" % m)
if failed:
    sys.exit(1)
print("OK snapshot meta")
