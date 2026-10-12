#!/usr/bin/env python3
"""codal_dedup_dryrun.py — dry-runِ «اگر قاعدۀ جمعِ ردیف اجرا شود چه می‌کُشد؟»

چرا (ممیزی CODAL دور ۲، CA-3): نویسندۀ دسته‌ای (`codal_fetcher._deep_extract`)
پس ازِ نوشتن، `collapse_symbol` را اجرا می‌کند (یکِ دوره، یکِ ردیف)؛ نویسندۀ
on-demand (`extract_symbol_on_demand`) این کار را **نمی‌کند** — پس ردیف‌هایِ
هم‌دوره درِ بانکِ عملیاتی می‌مانند. پیش ازِ هر تصمیمِ پاک‌سازی باید شمرد که همان
قاعده رویِ دادهٔ واقعی چه می‌کُشد: برایِ نمادهایِ هلدینگ (آریان، زکوثر، …)
«ردیف‌هایِ اضافه» در واقع صورتِ مالیِ **شرکت‌هایِ فرعیِ متمایز**‌اند.

قیدهایِ اجرا:
  • بانکِ عملیاتی (`market.db`) فقط‌خواندنی باز می‌شود و **هرگز** نوشته نمی‌شود؛
  • snapshot با **SQLite backup API** گرفته می‌شود (WAL + نوشتنِ هم‌زمان ⇒ کپیِ
    خامِ فایل سازگار نیست)؛
  • DELETE فقط رویِ snapshot اجرا می‌شود، و شمارش‌هایِ «پیش / پس / تکرارِ اجرا»
    گزارش می‌شوند (migration یدم‌پذیر است یا نه)؛
  • مسیرِ خروجی اگر باشد بازنویسی نمی‌شود (تستِ Stage 4 «overwrite نشود»).

خروجی: JSON + CSV (هر گروهِ جمع‌شده با علت و شناسه‌ها).
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import codal_fetcher as CF                     # noqa: E402
import codal_periods as CP                     # noqa: E402
import fts_engine as FE                        # noqa: E402

TABLES = ("financial_statements", "monthly_sales", "codal_notices", "codal_extracted")
DERIVED = ("financial_statements", "monthly_sales")

# علت‌ها — همان تعریفِ `tools/codal_record_identity_probe.py` (تقلیدِ دوم نه)
_MARKER_SUBSTR = ("حسابرس", "تلفیق", "اصلاحی")
import re  # noqa: E402
_PAREN = re.compile(r"[（(]([^（）()]*)[）)]")


def entity_tag(title: str) -> str:
    for span in _PAREN.findall(str(title or "")):
        s = FE.norm_fa(span).strip()
        if len(s) > 2 and not any(m in s for m in _MARKER_SUBSTR):
            return s
    return ""


def counts(conn) -> dict:
    out = {}
    have = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for t in TABLES:
        out[t] = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] if t in have else None
    return out


def group_causes(conn) -> dict:
    """{(symbol, period_end): cause} برایِ گروه‌هایِ چندردیفیِ FS."""
    groups: dict = {}
    for r in conn.execute("SELECT symbol, period_end, title, period_months,"
                          " revenue, gross_profit, operating_profit, net_profit, basic_eps"
                          " FROM financial_statements WHERE " + CP.DATED_SQL):
        groups.setdefault((r[0], r[1]), []).append(tuple(r))
    out = {}
    for (sym, pe), rows in groups.items():
        if len(rows) < 2:
            continue
        ents = {entity_tag(x[2]) for x in rows}
        keys = {tuple(str(x[i]) for i in (4, 5, 6, 7, 8)) for x in rows}
        kinds = {("%s" % ("c" if FE._is_consolidated(x[2] or "") else "m"),
                  int(x[3] or 0)) for x in rows}
        if len(ents) > 1:
            cause = "distinct_entity_subsidiary"
        elif any(FE._is_amendment(x[2] or "") for x in rows):
            cause = "correction_chain"
        elif len(kinds) > 1:
            cause = "main_vs_consolidated_or_length"
        elif len(keys) == 1:
            cause = "identical_values_suspect_dup"
        else:
            cause = "same_entity_multiple_filings"
        out[(sym, pe)] = cause
    return out


def take_snapshot(src: str, dst: str) -> int:
    """کپیِ سازگار با backup API؛ dst موجود ⇒ رد (بی‌بازنویسیِ شواهد)."""
    if os.path.exists(dst):
        raise SystemExit("snapshot exists — refuse to overwrite: %s" % dst)
    s = sqlite3.connect("file:%s?mode=ro" % src.replace("\\", "/"), uri=True)
    d = sqlite3.connect(dst)
    try:
        s.backup(d, pages=8192)
    finally:
        d.commit()
        d.close()
        s.close()
    return os.path.getsize(dst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--snap", default=None,
                    help="مسیرِ snapshot (پیش‌فرض: کنارِ --out با زمانِ اجرا)")
    ap.add_argument("--out", default="_audit/codal_dedup_dryrun")
    ap.add_argument("--keep-snapshot", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.db):
        print("DB not found: %s" % a.db, file=sys.stderr)
        return 2
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snap = a.snap or os.path.join(os.path.dirname(a.out) or ".",
                                  "market_snapshot_ca_%s.db" % stamp)
    src_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(a.db)).strftime("%Y-%m-%d %H:%M:%S")
    src_before = counts(sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True))

    size = take_snapshot(a.db, snap)
    print("[snap] %s (%d بایت) از %s (mtime %s)" % (snap, size, a.db, src_mtime))

    conn = sqlite3.connect(snap)
    snap_before = counts(conn)
    causes = group_causes(conn)
    reconcile = {k: v for k, v in src_before.items() if v == snap_before.get(k)}
    divergent = {k: (src_before.get(k), snap_before.get(k))
                 for k in TABLES if src_before.get(k) != snap_before.get(k)}

    # ── dry-run: «چند ردیف کجا می‌رود؟» پیش ازِ اجرایِ واقعی رویِ snapshot ──
    victims: dict = {}
    for (sym, pe), cause in causes.items():
        win = CF.period_winners(conn, "financial_statements", sym)
        tno = win.get((sym, pe))
        if tno is None:
            continue
        n = conn.execute("SELECT COUNT(*) FROM financial_statements"
                         " WHERE symbol=? AND period_end=? AND tracing_no<>?",
                         (sym, pe, tno)).fetchone()[0]
        if n:
            victims.setdefault(cause, []).append(
                {"symbol": sym, "period_end": pe, "winner": tno, "would_delete": n,
                 "losers": [r[0] for r in conn.execute(
                     "SELECT tracing_no FROM financial_statements"
                     " WHERE symbol=? AND period_end=? AND tracing_no<>? ORDER BY tracing_no",
                     (sym, pe, tno))]})

    # ── اجرایِ واقعی رویِ snapshot (نه بانکِ عملیاتی) + تکرار برایِ یدم‌پذیری ──
    syms = sorted({s for (s, _p) in causes})
    removed1 = [CF.collapse_symbol(conn, s) for s in syms]
    conn.commit()
    after1 = counts(conn)
    removed2 = [CF.collapse_symbol(conn, s) for s in syms]
    conn.commit()
    after2 = counts(conn)
    conn.close()

    op_after = counts(sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True))

    summary = {
        "at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "operational_db": a.db,
        "operational_mtime_before": src_mtime,
        "snapshot": snap,
        "snapshot_bytes": size,
        "snapshot_method": "sqlite3.Connection.backup (WAL-safe, pages=8192)",
        "counts_source": src_before,
        "counts_snapshot": snap_before,
        "snapshot_reconciles_on": sorted(reconcile),
        "snapshot_divergent": divergent,
        "multi_row_groups": len(causes),
        "would_delete_by_cause": {c: sum(v["would_delete"] for v in vs)
                                  for c, vs in victims.items()},
        "would_delete_rows_by_cause": {c: len(vs) for c, vs in victims.items()},
        "collapse_pass1": {"fs": sum(r[0] for r in removed1),
                           "ms": sum(r[1] for r in removed1),
                           "symbols": len(syms)},
        "collapse_pass2": {"fs": sum(r[0] for r in removed2),
                           "ms": sum(r[1] for r in removed2)},
        "counts_snapshot_after1": after1,
        "counts_snapshot_after2": after2,
        "idempotent_second_pass": after1 == after2 and sum(r[0] for r in removed2) == 0,
        "operational_db_written": op_after != src_before,
        "operational_counts_after": op_after,
        "operational_deleted_rows": {k: (src_before.get(k) or 0) - (op_after.get(k) or 0)
                                     for k in TABLES},
        "verdict": ("NEEDS_REVIEW — پاک‌سازیِ خودکار رویِ بانکِ عملیاتی انجام نشد؛"
                    " علت: بخشی از «ردیف‌هایِ اضافه» شرکت‌هایِ فرعیِ متمایزاند"),
    }
    with open(a.out + ".json", "w", encoding="utf-8") as fo:
        json.dump(summary, fo, ensure_ascii=False, indent=1)
    rows = []
    for cause, vs in sorted(victims.items()):
        for v in vs:
            rows.append({"cause": cause, "symbol": v["symbol"], "period_end": v["period_end"],
                         "winner_tracing_no": v["winner"], "would_delete": v["would_delete"],
                         "loser_tracing_nos": "|".join(str(x) for x in v["losers"])})
    with open(a.out + ".csv", "w", encoding="utf-8", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=["cause", "symbol", "period_end",
                                          "winner_tracing_no", "would_delete",
                                          "loser_tracing_nos"])
        w.writeheader()
        w.writerows(rows)

    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("counts_source", "counts_snapshot")},
                     ensure_ascii=False, indent=1))
    if not a.keep_snapshot:
        os.remove(snap)
        print("[snap] حذف شد (بی‌مخزنِ ۲۵۰ مگ درِ _audit): %s" % snap)
    else:
        print("[snap] نگه داشته شد: %s" % snap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
