#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""backfill_phase47.py — ترمیمِ idempotentِ یکپارچگیِ ingestion (فاز ۴٫۷ §۶).

دو عملیاتِ مستقل، هر دو با دامنهٔ اندازه‌گیری‌شده پیش از هر نوشتن:

  `--label-src`
      ردیف‌هایِ `price_history` که `src` تهی دارند برچسبِ `legacy-unknown`
      می‌گیرند. این **حدسِ منبع نیست**: برچسب می‌گوید «منشأ قابلِ اثبات نیست» و
      رتبهُ نوشتنش همان رتبهُ صفرِ NULL می‌ماند، پس هیچ ردیفِ منتشرشده‌ای را
      نمی‌بندد. سودِ واقعی: قیدِ مالکیتِ `candle_contract.UPSERT_SQL` دیگر رویِ
      NULLِ مبهم کار نمی‌کند و payload هم به‌جایِ ادعایِ «published» وضعیتِ
      نامعلوم را گزارش می‌دهد.

  `--repair-daily`
      ردیف‌هایِ `daily_prices` که با پاسخِ لاغر/صفرِ تابلو خالی شده‌اند و کندلِ
      `board`ِ همان نشست هنوز داده دارد، از همان کندل بازسازی می‌شوند. منبع
      اثبات‌پذیر است (کندل از همان ردیفِ تابلو ساخته شده بود)، ولی **دادهٔ
      مشتق‌شده** است: ستونِ `repair_src` با نسخهٔ منطق پر می‌شود تا خام و
      بازسازی‌شده از هم قابلِ تفکیک باشند (§۶).

قواعدِ ایمنی:
  * پیش‌فرض `dry-run` است؛ نوشتن فقط با `--apply`.
  * با `--apply` نخست یک snapshot کامل (sqlite backup API) ساخته و sha256 آن در
    manifest ثبت می‌شود؛ rollback = بازگرداندنِ همان فایل.
  * هر دو عملیات تک‌تراکنشی و idempotent‌اند: اجرایِ دوم صفر ردیف عوض می‌کند.
  * هیچ جدولِ دیگری نوشته نمی‌شود؛ هیچ ردیفی حذف نمی‌شود.

    python tools/phase47/backfill_phase47.py --db _audit/phase47/lab/market.db \\
        --label-src --repair-daily --out _audit/phase47/backfill-dry.json
    python tools/phase47/backfill_phase47.py --db ... --apply
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sqlite3
import sys

LOGIC_VERSION = "phase47-backfill-v1"
REPAIR_SRC = "candle-backfill:v1"

SYMBOL_MAP_SQL = ("SELECT l_val18 AS sym, MIN(ins_code) AS ins_code FROM instruments "
                  "WHERE l_val18 IS NOT NULL GROUP BY l_val18")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def connect(path: str, writable: bool) -> sqlite3.Connection:
    if writable:
        con = sqlite3.connect(path)
    else:
        con = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
    con.row_factory = sqlite3.Row
    return con


def scope_label_src(con) -> dict:
    row = con.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM price_history "
                      "WHERE src IS NULL OR TRIM(src) = ''").fetchone()
    return {"rows": row[0], "symbols": row[1]}


def scope_repair_daily(con) -> dict:
    """ردیف‌هایِ خالی‌شده‌ای که کندلِ board برایشان دادهٔ مثبت دارد."""
    try:
        con.execute("SELECT repair_src FROM daily_prices LIMIT 1")
        already = "AND d.repair_src IS NULL"
    except sqlite3.Error:
        already = ""
    sql = """
        SELECT COUNT(*), COUNT(DISTINCT d.ins_code)
        FROM daily_prices d
        JOIN (""" + SYMBOL_MAP_SQL + """) i ON i.ins_code = d.ins_code
        JOIN price_history p
          ON p.symbol = i.sym
         AND p.date = printf('%04d-%02d-%02d', d.d_even/10000, (d.d_even/100)%100, d.d_even%100)
        WHERE COALESCE(d.q_tot_tran, 0) <= 0
          AND COALESCE(p.src, '') = 'board'
          AND COALESCE(p.volume, 0) > 0
          AND COALESCE(p.close, 0) > 0
          AND COALESCE(p.open, 0) > 0
          """ + already
    row = con.execute(sql).fetchone()
    return {"rows": row[0], "symbols": row[1]}


def apply_label_src(con) -> int:
    cur = con.execute("UPDATE price_history SET src = ? "
                      "WHERE src IS NULL OR TRIM(src) = ''", ("legacy-unknown",))
    return cur.rowcount or 0


def apply_repair_daily(con) -> list[tuple]:
    cols = {r[1] for r in con.execute("PRAGMA table_info(daily_prices)")}
    if "repair_src" not in cols:
        con.execute("ALTER TABLE daily_prices ADD COLUMN repair_src TEXT")
    sql = """
        SELECT d.rowid, d.ins_code, d.d_even,
               d.q_tot_tran, d.price_first, d.p_closing, d.p_last,
               d.price_min, d.price_max,
               p.open, p.high, p.low, p.close, p.volume, p.last
        FROM daily_prices d
        JOIN (""" + SYMBOL_MAP_SQL + """) i ON i.ins_code = d.ins_code
        JOIN price_history p
          ON p.symbol = i.sym
         AND p.date = printf('%04d-%02d-%02d', d.d_even/10000, (d.d_even/100)%100, d.d_even%100)
        WHERE COALESCE(d.q_tot_tran, 0) <= 0
          AND COALESCE(p.src, '') = 'board'
          AND COALESCE(p.volume, 0) > 0
          AND COALESCE(p.close, 0) > 0
          AND COALESCE(p.open, 0) > 0
          AND d.repair_src IS NULL
    """
    rows = con.execute(sql).fetchall()
    upd = []
    touched = []
    for r in rows:
        # فقط ستون‌هایی که صفر/تهی‌اند پر می‌شوند؛ هیچ مقدارِ موجودی بازنویسی
        # نمی‌شود. high/low صفر با کندل پر می‌شوند و در manifest علامت می‌خورند
        # چون هندسهٔ کندل از widen گذشته است.
        q = r["q_tot_tran"] if (r["q_tot_tran"] or 0) > 0 else r["volume"]
        pf = r["price_first"] if (r["price_first"] or 0) > 0 else r["open"]
        pc = r["p_closing"] if (r["p_closing"] or 0) > 0 else r["close"]
        pl = r["p_last"] if (r["p_last"] or 0) > 0 else r["last"]
        pmn = r["price_min"] if (r["price_min"] or 0) > 0 else r["low"]
        pmx = r["price_max"] if (r["price_max"] or 0) > 0 else r["high"]
        upd.append((q, pf, pc, pl, pmn, pmx, REPAIR_SRC, r["rowid"]))
        touched.append({"ins_code": r["ins_code"], "d_even": r["d_even"]})
    if upd:
        con.executemany(
            "UPDATE daily_prices SET q_tot_tran = ?, price_first = ?, p_closing = ?,"
            " p_last = ?, price_min = ?, price_max = ?, repair_src = ? WHERE rowid = ?", upd)
    return touched


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--label-src", action="store_true")
    ap.add_argument("--repair-daily", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--snapshot-dir", default="")
    args = ap.parse_args()
    if not (args.label_src or args.repair_daily):
        print("nothing selected: pass --label-src and/or --repair-daily", file=sys.stderr)
        return 2
    if not os.path.exists(args.db):
        print("db not found: %s" % args.db, file=sys.stderr)
        return 2

    manifest = {"tool": LOGIC_VERSION, "db": os.path.abspath(args.db),
                "mode": "apply" if args.apply else "dry-run",
                "at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "snapshot": None, "before": {}, "after": {}, "applied": {}}

    con = connect(args.db, writable=False)
    try:
        if args.label_src:
            manifest["before"]["label_src"] = scope_label_src(con)
        if args.repair_daily:
            manifest["before"]["repair_daily"] = scope_repair_daily(con)
    finally:
        con.close()

    if not args.apply:
        print(json.dumps(manifest["before"], ensure_ascii=False, indent=1))
        print("dry-run: nothing written")
        if args.out:
            os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, ensure_ascii=False, indent=1)
                fh.write("\n")
        return 0

    # snapshot پیش از هر نوشتن — rollback = همین فایل
    snap_dir = args.snapshot_dir or (os.path.dirname(os.path.abspath(args.db)) or ".")
    os.makedirs(snap_dir, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    snap_path = os.path.join(snap_dir, os.path.basename(args.db) + ".phase47-%s.bak" % stamp)
    src = sqlite3.connect("file:%s?mode=ro" % args.db.replace("\\", "/"), uri=True)
    dst = sqlite3.connect(snap_path)
    src.backup(dst)
    dst.close()
    src.close()
    manifest["snapshot"] = {"path": os.path.abspath(snap_path),
                            "sha256": sha256_file(snap_path)}
    manifest["db_sha256_before"] = sha256_file(args.db)

    con = connect(args.db, writable=True)
    try:
        with con:      # یک تراکنش: یا همه، یا هیچ
            if args.label_src:
                manifest["applied"]["label_src"] = apply_label_src(con)
            if args.repair_daily:
                touched = apply_repair_daily(con)
                manifest["applied"]["repair_daily"] = len(touched)
                manifest["applied"]["repair_daily_keys_head"] = touched[:20]
        if args.label_src:
            manifest["after"]["label_src"] = scope_label_src(con)
        if args.repair_daily:
            manifest["after"]["repair_daily"] = scope_repair_daily(con)
    finally:
        con.close()

    manifest["db_sha256_after"] = sha256_file(args.db)
    manifest["rollback"] = ("copy %s over %s (close the app first), or run "
                            "VACUUM INTO from it" % (manifest["snapshot"]["path"],
                                                     manifest["db"]))
    print(json.dumps({"applied": manifest["applied"],
                      "after": manifest["after"]}, ensure_ascii=False, indent=1))
    out = args.out or (os.path.join(snap_dir, "backfill-manifest-%s.json" % stamp))
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("manifest:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
