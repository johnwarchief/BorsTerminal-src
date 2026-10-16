# -*- coding: utf-8 -*-
"""سنجشِ فقط‌خواندنیِ دروازۀ ISIN — چند الحاقِ پسوندِ رقمی می‌ماند، چند رد می‌شود.

مرحلۀ ۱.۲ برای نمادهای «خطِ تابلو» (`آباد3`) یک قاعده گذاشت: فقط یک رقمِ انتهایی
حذف شود، و فقط با شاهدِ ISIN. نسخۀ اولِ آن قاعده پایۀ نام را تنها با ردیفِ خودش
می‌سنجید؛ نسخۀ تازه خط‌هایِ خواهر (`كم ر ۱` … `كم ر ۵`) را هم می‌شمارد — چند
صادرکننده زیرِ یک پایۀ نام یعنی الحاقِ ممنوع. این اسکریپت هر دو را رویِ همان
`market.db` کنارِ هم می‌گذارد تا عددِ داخلِ `symbol_identity.py` شاهدِ زنده
داشته باشد، نه ادعا.

اجرا:  PYTHONIOENCODING=utf-8 python tools/symbol_identity_isin_gate.py
"""
from __future__ import annotations

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

import bors_config                      # noqa: E402
import symbol_identity as SI            # noqa: E402
import fts_engine as FE                 # noqa: E402

ONE_DIGIT = SI._ONE_DIGIT


def old_rule(slot, k, base):
    """رفتارِ نسخۀ اول: فقط ISINِ خودِ پایۀ نام، بی‌خط‌هایِ خواهر."""
    mine = slot["isin"].get(k, set())
    theirs = slot["isin"].get(base, set())
    if mine and theirs:
        return "isin-agree" if (mine & theirs) else "isin-clash"
    return "no-isin"


def sibling_issuers(slot, k, base):
    out = set(slot["isin"].get(base, set()))
    for kk, segs in slot["isin"].items():
        if kk != base and kk != k and ONE_DIGIT.search(kk) and ONE_DIGIT.sub("", kk) == base:
            out |= segs
    return out


def main() -> int:
    if not os.path.exists(bors_config.DB_PATH):
        print("BLOCKED: market.db نیست (%s)" % bors_config.DB_PATH)
        return 2
    conn = sqlite3.connect("file:%s?mode=ro" % bors_config.DB_PATH.replace("\\", "/"),
                           uri=True)
    FE.register_sql(conn)
    try:
        codal = [r[0] for r in conn.execute(
            "SELECT DISTINCT symbol FROM financial_statements") if r[0]]
        board = [r[0] for r in conn.execute(
            "SELECT l_val18 FROM instruments WHERE l_val18 IS NOT NULL")]
        universe = sorted({s for s in codal + board if SI.key(s)})
        slot = SI._slot(conn)
        new_tally = {"isin-agree": 0, "isin-clash": 0, "no-isin": 0}
        old_tally = {"isin-agree": 0, "isin-clash": 0, "no-isin": 0}
        flipped, no_base = [], 0
        for s in universe:
            k = SI.key(s)
            if not (len(k) >= 3 and ONE_DIGIT.search(k)):
                continue
            base = ONE_DIGIT.sub("", k)
            if not SI._has_codal_rows(conn, base):
                no_base += 1                     # بی‌نامزد: اصلاً الحاقی مطرح نیست
                continue
            ev_new = SI.line_variants(conn, s)[1]
            ev_old = old_rule(slot, k, base)
            new_tally[ev_new] += 1
            old_tally[ev_old] += 1
            if ev_new == "isin-clash" and ev_old != "isin-clash":
                flipped.append({"symbol": s, "was": ev_old,
                                "issuers": sorted(sibling_issuers(slot, k, base))})
        out = {"db": bors_config.DB_PATH,
               "universe_symbols": len(universe),
               "skipped_no_codal_base": no_base,
               "new_rule": new_tally,
               "old_rule": old_tally,
               "merges_under_new_rule": new_tally["isin-agree"] + new_tally["no-isin"],
               "newly_refused_count": len(flipped),
               "newly_refused": flipped[:30]}
        print("خانۀ نمادها=%d   بی‌پایۀِ کدال=%d" % (len(universe), no_base))
        print("قاعدۀ تازه  :", new_tally)
        print("قاعدۀ پیشین :", old_tally)
        print("الحاقِ مجاز با قاعدۀ تازه:", out["merges_under_new_rule"])
        print("ردِ تازه‌شده:", len(flipped))
        for r in flipped[:8]:
            print("    %s  بود=%s  صادرکنندگان=%s" % (r["symbol"], r["was"], r["issuers"]))
        dest = os.path.join(ROOT, "_audit", "symbol_identity_isin_gate.json")
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        print("json:", dest)
    finally:
        SI.reset_cache(conn)
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
