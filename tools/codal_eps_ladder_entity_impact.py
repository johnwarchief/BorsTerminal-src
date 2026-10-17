# -*- coding: utf-8 -*-
"""چند سابقۀ EPS عوض می‌شود اگر ردیفِ «شرکتِ دیگر» از نردبانِ شاخص ۲ بیرون برود؟

نردبانِ `eps_ladder` تنها readerِ شاخص ۲ است و تا این دور پرچمِ `other_entity`
را نمی‌دید. این ابزار همان نردبان را دو بار اجرا می‌گیرد — یک بار با قاعده،
یک بار بی‌قاعده (با پچِ موقتِ `title_entity_suffix` درِ **حافظه**) — و تفاوتِ
سابقه، رأی و شکافِ داده را می‌شمارد. بانک فقط‌خواندنی است.

usage: PYTHONIOENCODING=utf-8 python tools/codal_eps_ladder_entity_impact.py
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import fts_engine as FE          # noqa: E402

_real_suffix = FE.title_entity_suffix


def without_rule():
    """HEAD: نردبان هیچ ردیفی را به‌خاطرِ شرکتِ دیگر بیرون نمی‌گذارد."""
    FE.title_entity_suffix = lambda title: ""


def with_rule():
    FE.title_entity_suffix = _real_suffix


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--out", default="_audit/codal_eps_ladder_entity.json")
    a = ap.parse_args()
    conn = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True)
    conn.row_factory = sqlite3.Row
    FE.register_sql(conn)
    raw = [r[0] for r in conn.execute("SELECT DISTINCT symbol FROM financial_statements")
           if r[0]]
    import symbol_identity as SI
    # شمارِ واحد = کلیدِ هویت، نه نوشتار: «آريان» و «آریان» یکِ نمادند و دو بار
    # شمرده می‌شدند (سنسورِ نسخهٔ اول همین دوباره‌شماری داشت).
    syms, seen = [], set()
    for x in raw:
        k = SI.key(x)
        if k and k not in seen:
            seen.add(k)
            syms.append(x)
    series_changed = verdict_changed = gap_changed = years_changed = 0
    poisoned_now_clean = 0
    examples = []
    for s in syms:
        without_rule()
        try:
            old = FE.eps_ladder(conn, s, years=3)
        except Exception:                              # noqa: BLE001
            old = {}
        with_rule()
        try:
            new = FE.eps_ladder(conn, s, years=3)
        except Exception:                              # noqa: BLE001
            new = {}
        if not old and not new:
            continue
        o_se, n_se = old.get("eps_series"), new.get("eps_series")
        if o_se != n_se:
            series_changed += 1
        if bool(old.get("pass")) != bool(new.get("pass")):
            verdict_changed += 1
        if bool(old.get("data_gap")) != bool(new.get("data_gap")):
            gap_changed += 1
        if old.get("years_available") != new.get("years_available"):
            years_changed += 1
        # آیا سابقۀ پیشین ردیفِ شرکتِ دیگر را به‌عنوان EPSِ این نماد می‌فروخت؟
        ov = old.get("period_ends") or []
        nv = set(new.get("period_ends") or [])
        dropped = [pe for pe in ov if pe not in nv]
        if dropped:
            poisoned_now_clean += 1
            if len(examples) < 12:
                examples.append({"symbol": s, "old_series": o_se, "new_series": n_se,
                                 "old_pass": old.get("pass"), "new_pass": new.get("pass"),
                                 "dropped_periods": dropped,
                                 "old_evidence": old.get("evidence"),
                                 "new_evidence": new.get("evidence")})
    rep = {"db": a.db, "codal_symbols_unique_key": len(syms),
           "codal_spellings_scanned": len(raw),
           "series_changed": series_changed, "verdict_changed": verdict_changed,
           "data_gap_changed": gap_changed, "years_available_changed": years_changed,
           "symbols_losing_a_period": poisoned_now_clean, "examples": examples}
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != "examples"},
                     ensure_ascii=False, indent=1))
    for e in examples[:6]:
        print("   ", json.dumps(e, ensure_ascii=False)[:190])
    print("out=%s" % a.out)
    with_rule()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
