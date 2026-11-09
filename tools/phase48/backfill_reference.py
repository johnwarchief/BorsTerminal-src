#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""backfill_reference.py — S4: backfillِ فقط-مفقودِ تاریخچهٔ خام از بستهٔ مرجع ره‌آورد.

قراردادها (همه اندازه‌گیری‌شده، نه حدس):
  * مرجع: `bars.ndjson.gz` با `adjust=raw`, `resolution=D`, `type=type0`؛ میدانِ
    `close` همان «آخرین معامله» است (همان قاعده‌ای که `tools/phase45/compare_raw.py`
    برایِ مقایسه با `last` به‌کار می‌برد).
  * نوشتن فقط رویِ تاریخ‌هایی که در `price_history` نیستند؛ هیچ ردیفِ موجودی حذف یا
    بازنویسی نمی‌شود (`INSERT OR IGNORE` + بررسیِ صریحِ تاریخ).
  * هندسه از `candle_contract.candle` می‌آید (همان قراردادِ کندلِ برنامه). ردیفِ
    بی‌حجم/بی‌قیمت/هندسهٔ نامعتبر نوشته نمی‌شود؛ `open` یا `last` جعل نمی‌شود.
  * `src='rahavard365'` مالکیتِ ردیف را می‌گوید. هر ردیف provenanceِ اجرا/مرجع دارد
    (`backfill_runs`, `backfill_rows`) و rollback فقط ردیف‌هایِ همان اجرا را برمی‌دارد.
  * خام و تعدیل‌شده جدا می‌مانند: فقط سریِ خام وارد `price_history` می‌شود؛ سریِ
    تعدیل‌شدهٔ مرجع برایِ سنجشِ زنجیرهٔ تعدیل است، نه برایِ نوشتن در ستونِ خام.

این ابزار رویِ کپیِ آزمایشگاهی کار می‌کند؛ مسیرِ `market.db`ِ عملیاتی را نه
می‌شناسد و نه تغییر می‌دهد. promotion به seed/نصب یک قدمِ جدا و gate‌دار است.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import sqlite3
import sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import candle_contract as CC  # noqa: E402

TOOL_VERSION = "phase48-backfill-v1"
SRC_RAHAVARD = "rahavard365"
PH_COLUMNS = ("symbol", "date", "open", "high", "low", "close", "volume",
              "last", "value", "src")
INSERT_SQL = ("INSERT OR IGNORE INTO price_history (" + ",".join(PH_COLUMNS) + ") "
              "VALUES (" + ",".join("?" * len(PH_COLUMNS)) + ")")
PROV_COLUMNS = ("run_id", "symbol", "date", "src", "asset_id", "ref_type",
                "ref_adjust", "ref_resolution", "open", "high", "low", "close",
                "volume")
RUNS_SQL = """CREATE TABLE IF NOT EXISTS backfill_runs (
    run_id TEXT PRIMARY KEY,
    tool TEXT, src TEXT, ref_path TEXT, ref_sha256 TEXT,
    source_db TEXT, source_db_sha256 TEXT,
    work_db TEXT, work_db_sha256_before TEXT, work_db_sha256_after TEXT,
    symbols INTEGER, ref_rows INTEGER, ref_only INTEGER,
    inserted INTEGER, skipped_existing INTEGER, invalid INTEGER,
    duplicate_conflicts INTEGER,
    started_at TEXT, finished_at TEXT, status TEXT, rolled_back_at TEXT)"""
ROWS_SQL = """CREATE TABLE IF NOT EXISTS backfill_rows (
    run_id TEXT, symbol TEXT, date TEXT, src TEXT,
    asset_id INTEGER, ref_type TEXT, ref_adjust TEXT, ref_resolution TEXT,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (run_id, symbol, date))"""


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_symbols(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        out = [r["symbol"].strip() for r in csv.DictReader(fh) if r.get("symbol")]
    seen, uniq = set(), []
    for s in out:
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def _ro_uri(path):
    p = os.path.abspath(path).replace("\\", "/")
    return "file:" + quote(p, safe="/:") + "?mode=ro"


def _ref_key(r):
    return tuple(repr(float(r[k])) for k in ("open", "high", "low", "close", "volume"))


def load_ref_daily(path, symbols):
    """فقط raw/D؛ تکرارِ تاریخ: اولی می‌ماند، تعارض شمرده می‌شود."""
    wanted = set(symbols)
    out = {s: {} for s in symbols}
    meta = {"ref_rows": 0, "duplicates": 0, "conflicts": 0}
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("adjust") != "raw" or r.get("resolution") != "D":
                continue
            sym = r.get("symbol")
            if sym not in wanted:
                continue
            d = r.get("date")
            if not d:
                continue
            meta["ref_rows"] += 1
            prev = out[sym].get(d)
            if prev is not None:
                if _ref_key(prev) != _ref_key(r):
                    meta["conflicts"] += 1
                else:
                    meta["duplicates"] += 1
                continue
            out[sym][d] = r
    return out, meta


def valid_ref_row(r):
    """شکل/هندسهٔ ردیفِ مرجع؛ هیچ عددی اینجا ساخته نمی‌شود."""
    d = r.get("date")
    try:
        dt.date.fromisoformat(str(d))
    except (TypeError, ValueError):
        return False, "bad-date"
    vals = [r.get(k) for k in ("open", "high", "low", "close", "volume")]
    if any(v is None for v in vals):
        return False, "missing-field"
    try:
        o, h, l, c, v = (float(x) for x in vals)
    except (TypeError, ValueError):
        return False, "not-a-number"
    if not all(math.isfinite(x) for x in (o, h, l, c, v)):
        return False, "not-finite"
    if c <= 0:
        return False, "close<=0"
    if o <= 0:
        return False, "open<=0"
    if v <= 0:
        return False, "volume<=0"
    if h < l or h < o or h < c or l > o or l > c:
        return False, "geometry"
    return True, ""


def ref_candle(sym, r):
    # close مرجع = آخرین معامله؛ همان مقدار در close و last می‌نشیند تا معنای
    # ستون در قراردادِ کندل حفظ شود (close لنگر، last آخرین معامله).
    return CC.candle(sym, r["date"], r["open"], r["high"], r["low"], r["close"],
                     r["volume"], last=r["close"], value=None, src=SRC_RAHAVARD)


def period_of(date_str):
    if date_str < "2010-01-01":
        return "pre2010"
    if date_str <= "2024-12-31":
        return "2010-2024"
    return "post2024"


def _norm_src(src):
    return src or "legacy-unknown"


def _digest_rows(rows):
    h = hashlib.sha256()
    for key in sorted(rows):
        row = rows[key]
        payload = [key[0], key[1]] + [row[k] for k in PH_COLUMNS[2:]]
        h.update(json.dumps(payload, ensure_ascii=False, separators=(",", ":"),
                            default=str).encode("utf-8"))
    return h.hexdigest()


def snapshot(con, symbols):
    ph = ",".join("?" * len(symbols))
    rows, by_symbol = {}, {}
    src_counts = collections.Counter()
    cur = con.execute("SELECT " + ",".join(PH_COLUMNS) + " FROM price_history "
                      "WHERE symbol IN (" + ph + ") ORDER BY symbol, date", symbols)
    for raw in cur:
        row = dict(zip(PH_COLUMNS, raw))
        key = (row["symbol"], row["date"])
        rows[key] = row
        src_counts[_norm_src(row["src"])] += 1
        b = by_symbol.setdefault(row["symbol"], {"count": 0, "first": row["date"],
                                                 "last": row["date"],
                                                 "src": collections.Counter()})
        b["count"] += 1
        b["first"] = min(b["first"], row["date"])
        b["last"] = max(b["last"], row["date"])
        b["src"][_norm_src(row["src"])] += 1
    total_all = con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    return {"rows": rows, "by_symbol": by_symbol,
            "src": dict(src_counts), "total_all": total_all,
            "digest": _digest_rows(rows)}


def _copy_db(src, dest):
    src_con = sqlite3.connect(_ro_uri(src), uri=True)
    dst_con = sqlite3.connect(dest)
    try:
        src_con.backup(dst_con)
    finally:
        dst_con.close()
        src_con.close()


def _ensure_provenance(con):
    con.execute(RUNS_SQL)
    con.execute(ROWS_SQL)


def _row_equal(a, b):
    for k in ("open", "high", "low", "close", "volume", "last", "value"):
        va, vb = a.get(k), b.get(k)
        if va is None or vb is None:
            if va is not vb:
                return False
            continue
        if float(va) != float(vb):
            return False
    return True


def compare_raw_rows(local_rows, ref_rows):
    """مقایسهٔ خام رویِ ردیف‌هایِ موجود (پیش از backfill) — قاعدهٔ compare_raw.py.

    close: first `last`, else `closing`; low==close/ last ⇒ حراج.
    """
    local = {r["date"]: r for r in local_rows if r.get("date")}
    ref = {r["date"]: r for r in ref_rows if r.get("date")}
    fields = ("local", "ref", "common", "only_local", "only_ref", "local_not_candle",
              "open_match", "open_mismatch", "high_match", "high_mismatch",
              "low_match", "low_mismatch", "low_auction", "close_by_last",
              "close_by_closing", "close_other", "last_missing", "volume_match",
              "volume_mismatch", "ref_degenerate")
    st = collections.Counter({k: 0 for k in fields})
    examples = []
    for r in local.values():
        if not ((r.get("close") or 0) > 0 and (r.get("volume") or 0) > 0):
            st["local_not_candle"] += 1
    candle_dates = {d for d, r in local.items()
                    if (r.get("close") or 0) > 0 and (r.get("volume") or 0) > 0}
    common = sorted(candle_dates & set(ref))
    st["local"] = len(candle_dates)
    st["ref"] = len(ref)
    st["common"] = len(common)
    st["only_local"] = len(candle_dates - set(ref))
    st["only_ref"] = len(set(ref) - candle_dates)
    for d in common:
        b, rr = local[d], ref[d]
        bad = []
        if float(b["open"]) != float(rr["open"]):
            st["open_mismatch"] += 1
            bad.append(("open", b["open"], rr["open"]))
        else:
            st["open_match"] += 1
        if float(b["high"]) != float(rr["high"]):
            st["high_mismatch"] += 1
            bad.append(("high", b["high"], rr["high"]))
        else:
            st["high_match"] += 1
        if float(b["low"]) != float(rr["low"]):
            st["low_mismatch"] += 1
            bad.append(("low", b["low"], rr["low"]))
        else:
            st["low_match"] += 1
        last = b.get("last")
        closing = b.get("close")
        ref_close = float(rr["close"])
        if last is None:
            st["last_missing"] += 1
        if last is not None and float(last) == ref_close:
            st["close_by_last"] += 1
        elif closing is not None and float(closing) == ref_close:
            st["close_by_closing"] += 1
        else:
            st["close_other"] += 1
            bad.append(("close", last if last is not None else closing, rr["close"]))
        if last is not None and float(b["low"]) != float(rr["low"]) and \
                float(b["low"]) == float(last):
            st["low_auction"] += 1
        if float(b["volume"]) == float(rr["volume"]):
            st["volume_match"] += 1
        else:
            st["volume_mismatch"] += 1
            bad.append(("volume", b["volume"], rr["volume"]))
        if float(rr["open"]) == float(rr["high"]) == float(rr["low"]) == float(rr["close"]):
            st["ref_degenerate"] += 1
        if bad and len(examples) < 8:
            examples.append({"date": d, "src": _norm_src(b.get("src")), "diffs": [
                {"field": f, "bors": bv, "ref": rv} for f, bv, rv in bad]})
    out = dict(st)
    out["examples"] = examples
    return out


def apply_backfill(src_db, work_dir, ref_path, symbols, run_id,
                   reuse_work=False, dry_run=False):
    symbols = list(dict.fromkeys(symbols))
    if not symbols:
        raise ValueError("symbols list is empty")
    src_db, ref_path = os.path.abspath(src_db), os.path.abspath(ref_path)
    ref_rows, ref_meta = load_ref_daily(ref_path, symbols)
    src_hash = sha256_file(src_db)
    ref_hash = sha256_file(ref_path)
    started = now_iso()
    if dry_run:
        con = sqlite3.connect(_ro_uri(src_db), uri=True)
        work_db = None
        work_hash_before = src_hash
    else:
        os.makedirs(work_dir, exist_ok=True)
        work_db = os.path.join(work_dir, "market.db")
        if os.path.exists(work_db):
            if not reuse_work:
                raise FileExistsError(
                    f"{work_db} exists; pass --reuse-work to keep it")
        else:
            _copy_db(src_db, work_db)
        work_hash_before = sha256_file(work_db)
        con = sqlite3.connect(work_db)
    try:
        pre = snapshot(con, symbols)
        totals = collections.Counter()
        inserted_by_period = collections.Counter()
        ref_only_by_period = collections.Counter()
        invalid_reasons = collections.Counter()
        per_symbol = []
        prov_rows = []
        inserted_dates = collections.defaultdict(list)
        if not dry_run:
            _ensure_provenance(con)
            con.commit()
            con.execute("BEGIN IMMEDIATE")
        for sym in symbols:
            local_dates = {d for (s, d) in pre["rows"] if s == sym}
            refs = ref_rows.get(sym, {})
            overlap = len(local_dates & set(refs))
            # ردیف‌هایی که اجرایِ قبلیِ همین ابزار نوشته است، «موجود»‌اند و دوباره
            # نوشته نمی‌شوند؛ شمارششان idempotency را قابلِ سنجش می‌کند.
            for d in local_dates & set(refs):
                row = pre["rows"].get((sym, d)) or {}
                if _norm_src(row.get("src")) == SRC_RAHAVARD:
                    totals["skipped_existing"] += 1
            ref_only = [d for d in sorted(refs) if d not in local_dates]
            ins = 0
            sym_invalid = collections.Counter()
            for d in ref_only:
                ref_only_by_period[period_of(d)] += 1
                ok, reason = valid_ref_row(refs[d])
                if not ok:
                    invalid_reasons[reason] += 1
                    sym_invalid[reason] += 1
                    continue
                c = ref_candle(sym, refs[d])
                if c is None:
                    invalid_reasons["candle-contract"] += 1
                    sym_invalid["candle-contract"] += 1
                    continue
                if dry_run:
                    ins += 1
                    totals["would_insert"] += 1
                    inserted_by_period[period_of(d)] += 1
                    inserted_dates[sym].append(d)
                    continue
                if d in local_dates:
                    totals["skipped_existing"] += 1
                    continue
                before_changes = con.total_changes
                con.execute(INSERT_SQL, tuple(c[k] for k in PH_COLUMNS))
                if con.total_changes == before_changes:
                    totals["skipped_existing"] += 1
                    continue
                ins += 1
                totals["inserted"] += 1
                inserted_by_period[period_of(d)] += 1
                inserted_dates[sym].append(d)
                prov_rows.append((
                    run_id, sym, d, SRC_RAHAVARD, refs[d].get("asset_id"),
                    refs[d].get("type"), refs[d].get("adjust"),
                    refs[d].get("resolution"), c["open"], c["high"], c["low"],
                    c["close"], c["volume"]))
            b = pre["by_symbol"].get(sym, {"count": 0, "src": {}})
            src_b = dict(b.get("src", {}))
            last_after = b.get("last")
            first_after = b.get("first")
            if insertable_dates := inserted_dates.get(sym):
                last_after = max([last_after] + insertable_dates) if last_after else max(insertable_dates)
                first_after = min([first_after] + insertable_dates) if first_after else min(insertable_dates)
            per_symbol.append({
                "symbol": sym, "local_before": b["count"],
                "ref": len(refs), "overlap": overlap, "ref_only": len(ref_only),
                "inserted": ins, "invalid": sum(sym_invalid.values()),
                "invalid_reasons": dict(sym_invalid),
                "first_before": b.get("first"), "last_before": b.get("last"),
                "first_after": first_after, "last_after": last_after,
                "src_before": src_b,
                "raw_compare": compare_raw_rows(
                    [r for (s, _), r in pre["rows"].items() if s == sym],
                    list(refs.values())),
            })
            totals["ref_only"] += len(ref_only)
            totals["overlap"] += overlap
        if not dry_run:
            if prov_rows:
                con.executemany(
                    "INSERT OR IGNORE INTO backfill_rows (" + ",".join(PROV_COLUMNS) +
                    ") VALUES (" + ",".join("?" * len(PROV_COLUMNS)) + ")", prov_rows)
            con.execute(
                "INSERT INTO backfill_runs (run_id,tool,src,ref_path,ref_sha256,"
                "source_db,source_db_sha256,work_db,work_db_sha256_before,"
                "work_db_sha256_after,symbols,ref_rows,ref_only,inserted,"
                "skipped_existing,invalid,duplicate_conflicts,started_at,finished_at,"
                "status,rolled_back_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(run_id) DO UPDATE SET tool=excluded.tool,"
                "ref_path=excluded.ref_path,ref_sha256=excluded.ref_sha256,"
                "source_db=excluded.source_db,source_db_sha256=excluded.source_db_sha256,"
                "work_db=excluded.work_db,work_db_sha256_before=excluded.work_db_sha256_before,"
                "symbols=excluded.symbols,ref_rows=excluded.ref_rows,ref_only=excluded.ref_only,"
                "inserted=excluded.inserted,skipped_existing=excluded.skipped_existing,"
                "invalid=excluded.invalid,duplicate_conflicts=excluded.duplicate_conflicts,"
                "finished_at=excluded.finished_at,status=excluded.status,rolled_back_at=NULL",
                (run_id, TOOL_VERSION, SRC_RAHAVARD, ref_path, ref_hash, src_db,
                 src_hash, work_db, work_hash_before, None, len(symbols),
                 sum(len(v) for v in ref_rows.values()), totals["ref_only"],
                 totals["inserted"], totals["skipped_existing"],
                 sum(invalid_reasons.values()), ref_meta["conflicts"], started,
                 now_iso(), "applied", None))
            con.commit()
        post = snapshot(con, symbols) if not dry_run else pre
        if not dry_run:
            # هشِ فایل فقط پس از checkpoint و بستنِ اتصال معنا دارد؛ وگرنه WAL
            # می‌تواند بخشی از نوشته‌ها را بیرونِ فایلِ اصلی نگه دارد.
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        changed = missing = 0
        for key, before in pre["rows"].items():
            after = post["rows"].get(key)
            if after is None:
                missing += 1
            elif not _row_equal(before, after):
                changed += 1
        raw_totals = collections.Counter()
        for entry in per_symbol:
            for k, v in entry["raw_compare"].items():
                if isinstance(v, int):
                    raw_totals[k] += v
        report = {
            "tool": TOOL_VERSION, "run_id": run_id, "dry_run": dry_run,
            "started_at": started, "finished_at": now_iso(),
            "source_db": src_db, "source_db_sha256": src_hash,
            "work_db": work_db, "work_db_sha256_before": work_hash_before,
            "work_db_sha256_after": None,
            "ref_path": ref_path, "ref_sha256": ref_hash,
            "symbols": len(symbols), "ref_rows": ref_meta["ref_rows"],
            "ref_duplicates": ref_meta["duplicates"],
            "duplicate_conflicts": ref_meta["conflicts"],
            "inserted": totals["inserted"], "would_insert": totals["would_insert"],
            "skipped_existing": totals["skipped_existing"],
            "invalid": sum(invalid_reasons.values()),
            "changed_existing": changed, "missing_existing": missing,
            "totals": {
                "rows_before": pre["total_all"], "rows_after": post["total_all"],
                "local_before": sum(b["count"] for b in pre["by_symbol"].values()),
                "local_after": sum(b["count"] for b in post["by_symbol"].values()),
                "inserted": totals["inserted"], "would_insert": totals["would_insert"],
                "skipped_existing": totals["skipped_existing"],
                "ref_only": totals["ref_only"], "overlap": totals["overlap"],
                "invalid": sum(invalid_reasons.values()),
                "invalid_reasons": dict(invalid_reasons),
                "inserted_by_period": dict(inserted_by_period),
                "ref_only_by_period": dict(ref_only_by_period),
                "src_before": pre["src"],
                "src_after": post["src"],
            },
            "non_destructive": {
                "changed_existing": changed, "missing_existing": missing,
                "digest_before": pre["digest"], "digest_after": post["digest"],
            },
            "raw_compare": dict(raw_totals),
            "per_symbol": per_symbol,
        }
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        con.close()
    if work_db:
        report["work_db_sha256_after"] = sha256_file(work_db)
    return report


def rollback_backfill(work_db, run_id):
    con = sqlite3.connect(work_db)
    try:
        row = con.execute("SELECT status FROM backfill_runs WHERE run_id=?",
                          (run_id,)).fetchone()
        if row is None:
            return {"run_id": run_id, "deleted": 0, "status": "not-found",
                    "remaining": con.execute(
                        "SELECT COUNT(*) FROM price_history WHERE src=?",
                        (SRC_RAHAVARD,)).fetchone()[0]}
        con.execute("BEGIN IMMEDIATE")
        cur = con.execute(
            "DELETE FROM price_history WHERE src=? AND EXISTS ("
            "SELECT 1 FROM backfill_rows b WHERE b.run_id=? AND "
            "b.symbol=price_history.symbol AND b.date=price_history.date)",
            (SRC_RAHAVARD, run_id))
        deleted = cur.rowcount
        con.execute("UPDATE backfill_runs SET status='rolled_back', rolled_back_at=? "
                    "WHERE run_id=?", (now_iso(), run_id))
        con.commit()
        remaining = con.execute("SELECT COUNT(*) FROM price_history WHERE src=?",
                                (SRC_RAHAVARD,)).fetchone()[0]
        return {"run_id": run_id, "deleted": deleted, "status": "rolled_back",
                "remaining": remaining}
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        con.close()


def write_json(report, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def write_markdown(report, path):
    t = report["totals"]
    rc = report.get("raw_compare", {})
    lines = [
        "# Backfillِ تاریخچهٔ خام از مرجع (کپیِ آزمایشگاهی)",
        "",
        f"- اجرا: `{report['run_id']}` — وضعیت: `{'dry-run' if report['dry_run'] else 'applied'}`",
        f"- منبع: `{report['ref_path']}` — sha256: `{report['ref_sha256']}`",
        f"- بانکِ مبدأ (دست‌نخورده): `{report['source_db']}` — sha256: `{report['source_db_sha256']}`",
        f"- کپیِ کاری: `{report['work_db']}`",
        f"- ردیف‌هایِ نوشته‌شده: **{t['inserted']}** (dry-run: {t['would_insert']})؛ "
        f"فقط-مفقود در مرجع: {t['ref_only']}؛ نامعتبر: {t['invalid']}",
        f"- دوره‌ها: {json.dumps(t['inserted_by_period'], ensure_ascii=False)}",
        f"- ردیف‌هایِ موجودِ تغییرکرده: **{report['non_destructive']['changed_existing']}**؛ "
        f"گم‌شده: {report['non_destructive']['missing_existing']}",
        "",
        "## پوششِ خامِ موجود (پیش از backfill)",
        "",
        "| قلم | تعداد |",
        "| --- | ---: |",
        f"| روزِ مشترک | {rc.get('common', 0)} |",
        f"| فقط محلی | {rc.get('only_local', 0)} |",
        f"| فقط مرجع | {rc.get('only_ref', 0)} |",
        f"| open نابرابر | {rc.get('open_mismatch', 0)} |",
        f"| high نابرابر | {rc.get('high_mismatch', 0)} |",
        f"| low نابرابر | {rc.get('low_mismatch', 0)} |",
        f"| low=حراج | {rc.get('low_auction', 0)} |",
        f"| close=last | {rc.get('close_by_last', 0)} |",
        f"| close=closing | {rc.get('close_by_closing', 0)} |",
        f"| close دیگر | {rc.get('close_other', 0)} |",
        f"| last غایب | {rc.get('last_missing', 0)} |",
        f"| حجم نابرابر | {rc.get('volume_mismatch', 0)} |",
        "",
        "## نمادها",
        "",
        "| نماد | محلی قبل | مرجع | مشترک | فقط مرجع | نوشته | نامعتبر | اول | آخر |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for s in report["per_symbol"]:
        lines.append(
            f"| {s['symbol']} | {s['local_before']} | {s['ref']} | {s['overlap']} | "
            f"{s['ref_only']} | {s['inserted']} | {s['invalid']} | "
            f"{s['first_after'] or '—'} | {s['last_after'] or '—'} |")
    lines += ["", "## بازگشت", "",
              f"`python tools/phase48/backfill_reference.py rollback --work "
              f"\"{report['work_db'] or '<work>'}\" --run-id {report['run_id']}`",
              ""]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main(argv=None):
    ap = argparse.ArgumentParser(description="S4 backfillِ مرجع رویِ کپیِ آزمایشگاهی")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--src", required=True)
    a.add_argument("--work", required=True)
    a.add_argument("--ref", required=True)
    a.add_argument("--symbols", required=True)
    a.add_argument("--run-id", default="")
    a.add_argument("--reuse-work", action="store_true")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--out", required=True)
    a.add_argument("--md", default="")
    r = sub.add_parser("rollback")
    r.add_argument("--work", required=True)
    r.add_argument("--run-id", required=True)
    r.add_argument("--out", default="")
    args = ap.parse_args(argv)
    if args.cmd == "rollback":
        rep = rollback_backfill(os.path.join(args.work, "market.db"), args.run_id)
        if args.out:
            write_json(rep, args.out)
        print(json.dumps(rep, ensure_ascii=False))
        return 0
    symbols = load_symbols(args.symbols)
    run_id = args.run_id or "rahavard-" + dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    rep = apply_backfill(args.src, args.work, args.ref, symbols, run_id,
                         reuse_work=args.reuse_work, dry_run=args.dry_run)
    write_json(rep, args.out)
    if args.md:
        write_markdown(rep, args.md)
    print(json.dumps({
        "run_id": rep["run_id"], "dry_run": rep["dry_run"],
        "inserted": rep["totals"]["inserted"],
        "would_insert": rep["totals"]["would_insert"],
        "ref_only": rep["totals"]["ref_only"],
        "invalid": rep["totals"]["invalid"],
        "changed_existing": rep["non_destructive"]["changed_existing"],
        "per_period": rep["totals"]["inserted_by_period"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
