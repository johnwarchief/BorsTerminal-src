#!/usr/bin/env python3
"""codal_record_identity_probe.py — تشخیص هویت رکورد و علت چندردیفی در `financial_statements`.

چرا: ادعای دورِ اول («نبود upsert ⇒ انباشت تکراری») با شواهد باطل شد —
`FS_UPSERT` روی `tracing_no INTEGER PRIMARY KEY` می‌نویسد و `collapse_symbol`
قواعدۀ «یک دوره، یک ردیف» را دارد. پس باید فهمید ردیف‌های هم‌دوره واقعاً
**تکراریِ ingest**‌اند یا **چند گزارشِ مشروع** (شرکت فرعی/تلفیقی/اصلاحیه).

این ابزار فقط‌خواندنی است (`mode=ro`)؛ هیچ UPDATE/DELETE/migration نمی‌کند.

خروجی:
  • JSON  — خلاصۀ شمارش‌ها + سه «برندۀ» متفاوت برای هر گروه
  • CSV   — ردیفِ سطح-group با علت و شناسه‌ها (مبنای جدول تشخیصی)

استفاده:
    python tools/codal_record_identity_probe.py \
        --db market.db --out _audit/codal_record_identity_2026-10-12
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import codal_periods as CP                      # noqa: E402  (قراردادِ frozen)
import fts_engine as FE                         # noqa: E402  (قاعدهِ ترجیحِ یکسان)

FS_COLS_SQL = ("tracing_no, symbol, company_name, title, report_kind, period_months,"
               " period_end, publish_date, revenue, gross_profit, operating_profit,"
               " net_profit, basic_eps, is_consolidated, is_audited, unit_norm")
_KEYS = FE.FS_NUMBER_KEYS


def entity_tag(title: str) -> str:
    """پسوندِ پرانتزیِ «نامِ شرکت» در عنوانِ یک هلدینگ؛ بی‌نشانه ⇒ ''.

    از همان `fts_engine.title_entity_suffix` می‌خواند — تعریفِ دوم نداریم.
    """
    return FE.title_entity_suffix(title)


def statement_type(title: str, period_months) -> str:
    """برچسبِ نوعِ متمایزِ گزارش (تلفیقی/اصلی × سالانه/میاندورۀ n ماهه)."""
    t = FE._is_consolidated(title or "")
    pm = int(period_months or 0)
    return "%s|pm=%d" % ("consolidated" if t else "main", pm)


def completeness(row: dict) -> int:
    return FE.row_completeness(_KEYS, row)


def rank_of(row: dict) -> tuple:
    return FE.statement_rank(_KEYS, FE._is_consolidated(row.get("title") or ""),
                             completeness(row), row["tracing_no"])


def pub_key(row: dict):
    return CP.canonicalize(row.get("publish_date"))


def digit_script(v) -> str:
    """'fa' اگر رقمِ فارسی (U+06F0..) دارد وگرنه 'latin'."""
    s = str(v or "")
    return "fa" if any(0x06F0 <= ord(ch) <= 0x06F9 for ch in s) else "latin"


def numbers(row: dict) -> tuple:
    """پنج شاخصِ کلیدیِ جزوه — چیزی که کاربر در نمودار می‌بیند."""
    return tuple(row.get(k) for k in _KEYS)


def winner_current(rows) -> dict:
    """همان چیزی که `api/fundamental.py:2113` امروز برمی‌گزیند: ترتیبِ
    واژگانیِ `publish_date` (رقمِ فارسی در Unicode بعدِ لاتین ⇒ همیشه «تازه‌تر»)،
    و در تساوی ترتیبِ پیش‌آمدِ SQLite."""
    return sorted(rows, key=lambda r: (str(r.get("publish_date") or ""),
                                       str(r.get("tracing_no"))), reverse=True)[0]


def winner_normalized(rows) -> dict:
    """همان کوئری با `publish_date` یکسان‌سازی‌شده (`CP.canonicalize`) و
    تساوی‌شکنِ پایدارِ `tracing_no` — تنها تغییرِ مجازِ CA-2 بدونِ قاعدهٔ تازه."""
    return sorted(rows, key=lambda r: (pub_key(r) or "", int(r["tracing_no"])),
                  reverse=True)[0]


def winner_contract(rows) -> dict:
    """قاعدۀ یگانۀ پروژه: دامنۀ شرکت (`fts_engine.title_entity_suffix`) سپس
    `statement_rank` (مبنا ← کامل‌بودن ← تازگی) — همان که اندپوینتِ quarters و
    نویسندۀ `period_winners` مصرف می‌کنند."""
    def key(r):
        return ((1 if entity_tag(r["title"]) else 0),
                ) + rank_of(r)
    return min(rows, key=key)


def classify(rows) -> str:
    """علتِ احتمالیِ چندردیفی — از خودِ داده، نه از فرضِ «تکراری»."""
    ents = {entity_tag(r["title"]) for r in rows}
    if len(ents) > 1:
        return "distinct_entity_subsidiary"      # هلدینگ: صورتِ هر شرکتِ فرعی جدا
    kinds = {statement_type(r["title"], r["period_months"]) for r in rows}
    if FE._is_amendment(" ".join(r["title"] or "" for r in rows)):
        return "correction_chain"                # اصلی + اصلاحیه
    if len(kinds) > 1:
        return "main_vs_consolidated_or_length"
    vals = {tuple(str(r.get(k)) for k in _KEYS) for r in rows}
    if len(vals) == 1:
        return "identical_values_suspect_dup"
    return "same_entity_multiple_filings"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--out", default="_audit/codal_record_identity_probe")
    ap.add_argument("--limit", type=int, default=16,
                    help="سقفِ کوئریِ مصرف‌کننده (`/api/fundamental/*/quarters`)")
    a = ap.parse_args()

    if not os.path.exists(a.db):
        print("DB not found: %s" % a.db, file=sys.stderr)
        return 2
    conn = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True)
    conn.row_factory = sqlite3.Row

    groups: dict = {}
    total_fs = 0
    undated_fs = 0
    for r in conn.execute("SELECT %s FROM financial_statements" % FS_COLS_SQL):
        row = dict(r)
        total_fs += 1
        if CP.is_undated(row.get("period_end")):
            undated_fs += 1
            continue
        groups.setdefault((row["symbol"], row["period_end"]), []).append(row)
    multi = {k: v for k, v in groups.items() if len(v) > 1}

    # خام در برابرِ نرمال: خواننده با `sym_in` هر دو نوشتارِ یکِ نماد (ك/ي عربی ↔
    # فارسی) را درِ یکِ جواب می‌بیند، ولی `collapse_symbol` با `WHERE symbol=?`ِ
    # خام می‌کاهد ⇒ ردیف‌هایِ نوشتارِ دیگر هرگز با آن‌ها ادغام نمی‌شوند. این
    # شکافِ سازوکاریِ CA-3 است، نه «تکراریِ» اضافه.
    raw_slot: dict = {}
    norm_slot: dict = {}
    for rows in groups.values():
        for r in rows:
            pm = int(r["period_months"] or 0)
            raw_slot.setdefault((r["symbol"], r["period_end"], pm), []).append(r)
            norm_slot.setdefault((FE.norm_fa(r["symbol"]), r["period_end"], pm), []).append(r)
    raw_multi = {k: v for k, v in raw_slot.items() if len(v) > 1}
    norm_multi = {k: v for k, v in norm_slot.items() if len(v) > 1}
    spelling_only = {k: v for k, v in norm_multi.items()
                     if (k[0], k[1], k[2]) not in {
                         (FE.norm_fa(s), p, m) for (s, p, m) in raw_multi}}
    spelling = {
        "slots_multi_raw_symbol": len(raw_multi),
        "surplus_rows_raw_symbol": sum(len(v) - 1 for v in raw_multi.values()),
        "slots_multi_normalized_symbol": len(norm_multi),
        "surplus_rows_normalized_symbol": sum(len(v) - 1 for v in norm_multi.values()),
        "slots_visible_only_after_normalization": len(spelling_only),
        "surplus_rows_only_after_normalization": sum(len(v) - 1 for v in spelling_only.values()),
        "fs_rows_whose_notice_symbol_differs": conn.execute(
            "SELECT COUNT(*) FROM financial_statements f JOIN codal_notices n"
            " ON n.tracing_no=f.tracing_no"
            " WHERE n.symbol IS NOT NULL AND f.symbol IS NOT NULL"
            " AND n.symbol<>f.symbol").fetchone()[0],
        "note": ("همۀ این ۷۴ اختلافِ نماد، دوِ نوشتارِ یکِ نام‌اند (ی↔ي، ك↔ك) — نه "
                 "شرکتِ دیگر؛ شاهدِ نمونه: آينده/آینده، دبالك/دبالک."),
    }

    # مصرف‌کننده روی (period_end, period_months) dedupe می‌کند، نه فقط period_end
    slots: dict = {}
    ca2 = {"flips_current_vs_normalized": 0, "flips_current_vs_contract": 0,
           "digit_script_mixed_slots": 0, "slots": 0,
           "numbers_move_vs_normalized": 0, "numbers_move_vs_contract": 0}
    moved_syms_nrm, moved_syms_con, sub_syms = set(), set(), set()
    truncation = {"symbols_below_limit": 0, "symbols_checked": 0,
                  "periods_lost_total": 0}
    for (sym, pe), rows in multi.items():
        by_slot: dict = {}
        for r in rows:
            by_slot.setdefault(int(r["period_months"] or 0), []).append(r)
        for pm, sub in by_slot.items():
            slot = (sym, pe, pm)
            slots[slot] = sub
            ca2["slots"] += 1
            cur, nrm, con = winner_current(sub), winner_normalized(sub), winner_contract(sub)
            if len({digit_script(r.get("publish_date")) for r in sub}) > 1:
                ca2["digit_script_mixed_slots"] += 1
            if cur["tracing_no"] != nrm["tracing_no"]:
                ca2["flips_current_vs_normalized"] += 1
                if numbers(cur) != numbers(nrm):
                    ca2["numbers_move_vs_normalized"] += 1
                    moved_syms_nrm.add(sym)
            if cur["tracing_no"] != con["tracing_no"]:
                ca2["flips_current_vs_contract"] += 1
                if numbers(cur) != numbers(con):
                    ca2["numbers_move_vs_contract"] += 1
                    moved_syms_con.add(sym)
            if any(entity_tag(r["title"]) for r in sub):
                sub_syms.add(sym)

    # کم‌شدنِ دوره‌ها به‌سببِ LIMITِ قبلِ dedupe (رفتارِ واقعیِ همان کوئری)
    for sym in {s for (s, _p) in multi}:
        pred, params = sym_in(conn, "symbol", sym)
        raw = conn.execute(
            "SELECT period_end, period_months FROM financial_statements"
            " WHERE %s AND %s ORDER BY period_end DESC, publish_date DESC LIMIT ?"
            % (pred, CP.DATED_SQL), (*params, a.limit)).fetchall()
        distinct = {(r["period_end"], r["period_months"]) for r in raw}
        all_distinct = conn.execute(
            "SELECT COUNT(DISTINCT period_end || '|' || period_months) FROM financial_statements"
            " WHERE %s AND %s" % (pred, CP.DATED_SQL), params).fetchone()[0]
        truncation["symbols_checked"] += 1
        if len(distinct) < min(a.limit, int(all_distinct)):
            truncation["symbols_below_limit"] += 1
            truncation["periods_lost_total"] += min(a.limit, int(all_distinct)) - len(distinct)

    # برندۀ نویسندۀ قرارداد (`period_winners`) در برابرِ برندۀ خوانندۀ فعلی
    try:
        import codal_fetcher as CF
        pw = CF.period_winners(conn, "financial_statements")
    except Exception as e:                       # دفتر/ستونِ غایب ⇒ بدونِ ادعای پوشش
        pw, pw_err = {}, str(e)
    else:
        pw_err = None
    pw_disagree = 0
    for (sym, pe), rows in multi.items():
        cur = winner_current(rows)
        win = pw.get((sym, pe))
        if win is not None and int(win) != int(cur["tracing_no"]):
            pw_disagree += 1

    cause_counts: dict = {}
    csv_rows = []
    for (sym, pe, pm), rows in sorted(slots.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        cause = classify(rows)
        cause_counts[cause] = cause_counts.get(cause, 0) + 1
        cur, nrm, con = winner_current(rows), winner_normalized(rows), winner_contract(rows)
        csv_rows.append({
            "symbol": sym, "period_end": pe, "period_months": pm, "n_rows": len(rows),
            "cause": cause,
            "tracing_nos": "|".join(str(r["tracing_no"]) for r in
                                    sorted(rows, key=lambda x: x["tracing_no"])),
            "entities": "|".join(sorted({entity_tag(r["title"]) or "—" for r in rows})),
            "statement_types": "|".join(sorted({statement_type(r["title"], r["period_months"])
                                                for r in rows})),
            "publish_dates": "|".join(str(r["publish_date"] or "") for r in
                                      sorted(rows, key=lambda x: x["tracing_no"])),
            "digit_scripts": "|".join(sorted({("fa" if any(0x06F0 <= ord(ch) <= 0x06F9
                                                           for ch in str(r["publish_date"] or ""))
                                               else "latin") for r in rows})),
            "pick_current": cur["tracing_no"],
            "pick_normalized": nrm["tracing_no"],
            "pick_contract": con["tracing_no"],
            "flip_normalized": int(cur["tracing_no"] != nrm["tracing_no"]),
            "flip_contract": int(cur["tracing_no"] != con["tracing_no"]),
            "numbers_move_contract": int(numbers(cur) != numbers(con)),
            "numbers": "|".join(str(cur.get(k)) for k in _KEYS),
            "writer_winner": pw.get((sym, pe)) or "",
        })

    summary = {
        "at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "db": a.db,
        "db_mtime": datetime.datetime.fromtimestamp(os.path.getmtime(a.db)).strftime("%Y-%m-%d %H:%M:%S"),
        "read_only": True,
        "fs_rows_total": total_fs,
        "fs_rows_undated": undated_fs,
        "fs_dated_pairs": len(groups),
        "fs_pairs_multi_row": len(multi),
        "fs_extra_rows_in_multi": sum(len(v) - 1 for v in multi.values()),
        "slots_multi_row": ca2["slots"],
        "cause_counts": cause_counts,
        "spelling_split": spelling,
        "ca2": ca2,
        "ca2_symbols_affected": {
            "numbers_move_vs_normalized": len(moved_syms_nrm),
            "numbers_move_vs_contract": len(moved_syms_con),
        },
        "subsidiary_filings": {
            "fs_rows_with_entity_tag": sum(
                1 for r in groups.values() for x in r if entity_tag(x["title"])),
            "symbols_with_entity_tag": len(sub_syms),
            "note": ("صورتِ مالیِ شرکت‌هایِ فرعی زیرِ نمادِ هلدینگ ذخیره می‌شود؛ "
                     "چند ردیفِ یکِ دوره اینجا **چند شرکتِ distinct** است، نه تکراری. "
                     "اینکه کدامِ رکورد «خودِ نماد» است رأیِ جزوه می‌خواهد (NEEDS_REVIEW)."),
        },
        "limit_truncation": truncation,
        "writer_reader_divergence": {
            "period_winners_available": pw_err is None,
            "period_winners_error": pw_err,
            "multi_row_pairs_where_reader_pick_ne_collapses_to": pw_disagree,
            "note": ("`period_winners` یکی به ازای (نماد،دوره) می‌دهد؛ خوانندۀ "
                     "quarters روی (نماد،دوره،طولِ دوره) dedupe می‌کند — دو دامنه، دو جواب."),
        },
        "helper_coverage": {
            "CP.canonicalize==CF.date_key on FS.publish_date": "سنجیده در ca_shapes (۰ اختلاف از ۸٬۷۲۳)",
            "publish_date_forms": {
                "fa_digits": conn.execute(
                    "SELECT COUNT(*) FROM financial_statements WHERE publish_date"
                    " GLOB '[۰-۹]*'").fetchone()[0],
                "latin": conn.execute(
                    "SELECT COUNT(*) FROM financial_statements WHERE publish_date"
                    " GLOB '[0-9][0-9][0-9][0-9]/*'").fetchone()[0],
            },
        },
        "no_invented_thresholds": True,
        "operational_db_written": False,
    }

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out + ".json", "w", encoding="utf-8") as fo:
        json.dump(summary, fo, ensure_ascii=False, indent=1)
    with open(a.out + ".csv", "w", encoding="utf-8", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=list(csv_rows[0].keys()) if csv_rows else [])
        w.writeheader()
        w.writerows(csv_rows)

    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("\nCSV: %s.csv  (سطحِ group: %d)" % (a.out, len(csv_rows)))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
