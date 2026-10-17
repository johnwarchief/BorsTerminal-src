"""tools/symbol_identity_before_after.py — واگراییِ هویتِ نماد، پیش و پس ازِ Stage 1.2.

سه چیز را جدا می‌سنجد و هر سه را با همان منطقِ اجراییِ خودِ مسیرها (نه با دست‌چین):

  ۱) واگراییِ «کارت در برابرِ قیف» **پیش ازِ** اصلاح:
     card_old = `symbol IN (جایگشتِ ي/ك/ى + حذفِ نیم‌فاصله از ورودی + حذفِ یک رقم)`
     bulk_old = ردیف‌هایی که `norm_fa(symbol)`شان با کلیدِ ورودی یکی است
     این همان عددِ ۱٬۶۷۵ جفتِ گزارشِ دورِ دوم است (همیشه در جهت «قیف می‌بیند،
     کارت نمی‌بیند»).

  ۲) اثرِ اصلاح رویِ هر دو مسیر: کارتِ تازه چند ردیفِ تازه می‌بیند، و قیفِ تازه
     (کلیدِ بی‌فاصله) چند ردیف را ادغام می‌کند که پیش‌تر جدا بودند.

  ۳) باقی‌ماندۀ واگرایی: کارتِ تازه در برابرِ قیفِ تازه. صفر نبودن یعنی هنوز
     جایی دو کلید مصرف می‌شود. (تطبیقِ *رفتاری*ِ دو مسیر را گاردِ
     `dev/fts_engine_paths_parity_v1076.py` می‌سنجد؛ این‌جا سنجشِ *دستۀ ردیف* است.)

الگوریتمِ بازنشسته درِ همین فایل کپی شده تا سنجش به کدِ امروز وابسته نباشد؛
درِ پروداکشن دیگر هیچ مصرف‌کننده‌ای ندارد (گاردِ `dev/symbol_identity_v1090.py`
این را با AST می‌سنجد). بانک فقط‌خواندنی باز می‌شود و هیچ‌چیز نوشته نمی‌شود.

usage: PYTHONIOENCODING=utf-8 python tools/symbol_identity_before_after.py [--db market.db]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fts_engine as FE            # noqa: E402
import symbol_identity as SI       # noqa: E402

# ── الگوریتمِ بازنشستۀ کارت (کپیِ وفادار از v9.10.4) ────────────────────────
_YA = ("\u06cc", "\u064a", "\u0649")
_KAF = ("\u06a9", "\u0643")
_CLS = {}
for _c in _YA:
    _CLS[_c] = _YA
for _c in _KAF:
    _CLS[_c] = _KAF


def retired_aliases(symbol, limit=27):
    s = "" if symbol is None else str(symbol)
    if not s:
        return ()
    base = s.replace("\u200c", "")
    out, seen = [], set()
    for cand in (s, base):
        if cand and cand not in seen:
            seen.add(cand)
            out.append(cand)
    if len(base) >= 3 and base[-1] in "0123456789" and base[-2] not in "0123456789":
        stripped = base[:-1]
        if len(stripped) >= 2 and stripped not in seen:
            seen.add(stripped)
            out.append(stripped)
    pos = [i for i, ch in enumerate(base) if ch in _CLS]
    variants = [base]
    for i in pos:
        if len(variants) >= max(int(limit), 1):
            break
        nxt = []
        for v in variants:
            for al in _CLS[base[i]]:
                w = v[:i] + al + v[i + 1:]
                if w not in nxt:
                    nxt.append(w)
        variants = nxt
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return tuple(out)


def measure(conn, board, codal_syms, table):
    """سه جهانِ مقایسه، با همان منطقِ اجراییِ خودِ مسیرها.

    «جهانِ قیف» = `bulk_scan` که ردیف‌های یک جدول را با کلیدِ نمادِ **خودِ ردیف**
    دسته می‌زند؛ پس مرجعِ آن نمادهایِ کدال‌اند، نه نمادهایِ تابلو. «جهانِ کارت» =
    کوئریِ تک‌نمادی که با رشته‌ای که رابط می‌فرستد کار می‌کند (نمادِ کدال یا
    نمادِ تابلو). واگراییِ واقعیِ پیشین همین‌جا بود: برای نمادِ کدال `شهر فرش`
    قیف ۷ ردیف می‌دید و کارت ۱.
    """
    rows = conn.execute("SELECT tracing_no, symbol FROM %s" % table).fetchall()
    by_raw = collections.defaultdict(set)
    by_old_key = collections.defaultdict(set)
    by_new_key = collections.defaultdict(set)
    for tn, raw in rows:
        if raw is None:
            continue
        by_raw[raw].add(tn)
        by_old_key[FE.norm_fa(raw)].add(tn)
        by_new_key[SI.key(raw)].add(tn)

    r = {"table": table, "rows": len(rows), "codal_symbols": len(codal_syms),
         "codal_divergent_before": 0, "codal_divergent_after": 0,
         "codal_sym_diff_before": 0, "codal_sym_diff_after": 0,
         "codal_examples_after": [], "codal_examples_before": [],
         "board_card_gained_rows": 0, "board_card_lost_rows": 0,
         "board_was_empty_now_has": 0, "board_examples": []}

    # ── الف) قیف در برابرِ کارت، رویِ جهانِ قیف (نمادهای کدال) ────────────────
    for s in codal_syms:
        card_old = set()
        for x in retired_aliases(s):
            card_old |= by_raw.get(x, set())
        funnel_old = by_old_key.get(FE.norm_fa(s), set())
        card_new = set()
        for x in SI.pred(conn, "symbol", s)[1]:
            card_new |= by_raw.get(x, set())
        funnel_new = by_new_key.get(SI.key(s), set())
        if card_old != funnel_old:
            r["codal_divergent_before"] += 1
            r["codal_sym_diff_before"] += len(card_old ^ funnel_old)
            if len(r["codal_examples_before"]) < 8:
                r["codal_examples_before"].append(
                    {"symbol": s, "card_rows": len(card_old), "funnel_rows": len(funnel_old)})
        if card_new != funnel_new:
            r["codal_divergent_after"] += 1
            r["codal_sym_diff_after"] += len(card_new ^ funnel_new)
            if len(r["codal_examples_after"]) < 8:
                r["codal_examples_after"].append(
                    {"symbol": s, "card_rows": len(card_new), "funnel_rows": len(funnel_new),
                     "evidence": SI.evidence(conn, s)})

    # ── ب) اثرِ اصلاح رویِ پرسشِ سمتِ تابلو ─────────────────────────────────
    for b in board:
        card_old = set()
        for x in retired_aliases(b):
            card_old |= by_raw.get(x, set())
        card_new = set()
        for x in SI.pred(conn, "symbol", b)[1]:
            card_new |= by_raw.get(x, set())
        r["board_card_gained_rows"] += len(card_new - card_old)
        r["board_card_lost_rows"] += len(card_old - card_new)
        if not card_old and card_new:
            r["board_was_empty_now_has"] += 1
            if len(r["board_examples"]) < 8:
                r["board_examples"].append(
                    {"symbol": b, "rows_now": len(card_new),
                     "evidence": SI.evidence(conn, b)})
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--out", default="_audit/symbol_identity_before_after.json")
    a = ap.parse_args()
    conn = sqlite3.connect("file:%s?mode=ro" % a.db, uri=True)
    FE.register_sql(conn)
    board = [r[0] for r in conn.execute(
        "SELECT DISTINCT l_val18 FROM instruments WHERE l_val18 IS NOT NULL "
        "AND trim(l_val18)<>''")]
    out = {"db": a.db, "board_symbols": len(board), "tables": [],
           "identity": SI.identity_stats(conn),
           "evidence_mix": dict(collections.Counter(SI.evidence(conn, b) for b in board))}
    for table in ("financial_statements", "monthly_sales"):
        codal_syms = [r[0] for r in conn.execute(
            "SELECT DISTINCT symbol FROM %s" % table)]
        out["tables"].append(measure(conn, board, codal_syms, table))
    multi = sum(1 for r in conn.execute("SELECT DISTINCT symbol FROM financial_statements")
                if len(SI.variants(conn, r[0])) > 1)
    out["codal_rows_family_multispelling"] = multi

    d = os.path.dirname(a.out)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    for t in out["tables"]:
        print("%-22s rows=%-6d codal_syms=%-5d  کارت≠قیف پیش=%-5d پس=%-4d  "
              "ردیف‌تازۀ کارت(تابلو)=%-6d کاستی=%-4d بی‌داده→داده=%-4d"
              % (t["table"], t["rows"], t["codal_symbols"],
                 t["codal_divergent_before"], t["codal_divergent_after"],
                 t["board_card_gained_rows"], t["board_card_lost_rows"],
                 t["board_was_empty_now_has"]))
        if t["codal_examples_after"]:
            print("   ✗Remaining: ", t["codal_examples_after"][:3])
        if t["codal_examples_before"]:
            print("   پیش:", t["codal_examples_before"][:3])
    print("identity=%s" % (out["identity"],))
    print("evidence=%s" % (out["evidence_mix"],))
    print("multi-spelling-family codal symbols=%d" % multi)
    print("out=%s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
