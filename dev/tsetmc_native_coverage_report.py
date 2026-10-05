# -*- coding: utf-8 -*-
"""dev/tsetmc_native_coverage_report.py — سنجشِ پوششِ مبدأ، بی‌تکان‌دادنِ بودجه

دورِ مصرف‌کننده (docs/fts-notes/TSETMC-P0-CONSUMER-INTEGRATION.md بندِ ۱۰) گفت:
بودجهٔ 600 درخواست/روز را بالا نبر، اول *اندازه بگیر*. این گزارش همان اندازه‌گیری
است: فقط می‌خواند، هیچ درخواستی به TSETMC نمی‌زند و هیچ ستونی نمی‌نویسد.

چه چیزی گزارش می‌شود (همه از خودِ بانکِ canonical):
  • دامنهٔ هدفِ نشست — همان مجموعه‌ای که `ct_universe_sql()` انتخاب می‌کند
  • شمارِ native / mixed / reconstructed درِ همان نشست
  • پوششِ مبدأ (٪) و پوششِ کلِّ تابلو
  • میانگینِ درخواست به ازای هر نماد (هر ردیف = یک GetClientTypeHistory)
  • نرخِ برخوردِ کش: چه کسری از هدف از پیش درِ بانک بود (درخواست لازم نبود)
  • برآوردِ درخواست/روز برایِ دیده‌بان، قیف و کلِّ بازار، و «چند روز طول
    می‌کشد تا با همین سقفِ 600 پر شود»

فرمان:  python dev/tsetmc_native_coverage_report.py [--db market.db] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import test_tsetmc as T  # noqa: E402


def measure(conn) -> dict:
    """همهٔ عددها از یک اتصالِ خواندنی؛ بدونِ شبکه و بدونِ نوشتن."""
    day = conn.execute("SELECT MAX(d_even) FROM client_type_value").fetchone()[0] or 0
    board_day = conn.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0] or 0
    universe = conn.execute(
        "SELECT COUNT(*) FROM client_type WHERE d_even = ? "
        "AND (COALESCE(buy_i_vol,0)+COALESCE(buy_n_vol,0)"
        "     +COALESCE(sell_i_vol,0)+COALESCE(sell_n_vol,0)) > 0",
        (day,)).fetchone()[0] if day else 0
    kinds = {r[0] or "mixed": r[1] for r in conn.execute(
        "SELECT kind, COUNT(*) FROM client_type_value WHERE d_even=? GROUP BY kind",
        (day,)).fetchall()} if day else {}
    rows_day = sum(kinds.values())
    symbols_all = conn.execute(
        "SELECT COUNT(DISTINCT ins_code) FROM client_type_value").fetchone()[0]
    rows_all = conn.execute("SELECT COUNT(*) FROM client_type_value").fetchone()[0]
    sessions = conn.execute(
        "SELECT COUNT(DISTINCT d_even) FROM client_type_value").fetchone()[0] or 0
    board_rows = conn.execute(
        "SELECT COUNT(*) FROM market_watch WHERE COALESCE(q_tot_tran,0) > 0").fetchone()[0]
    watch = 0
    try:
        watch = conn.execute("SELECT COUNT(*) FROM user_watchlists").fetchone()[0]
    except sqlite3.Error:
        pass
    budget = T.CTV_BUDGET
    # هزینهٔ ثابتِ دو خانوادۀ دیگرِ P0 (تعدادِ درخواست در هر اجرا، نه دامنهٔ نماد):
    # corporate = ۴ درخواست، state/notices = ۳ درخواست (+1 فقط با پیکربندی webgw).
    # اینجا خوانده می‌شوند تا مجموعِ بارِ روزانهٔ P0 پنهان نماند.
    corp_rows = conn.execute("SELECT COUNT(*) FROM price_adjust_events").fetchone()[0]
    p0_runs = {r[0]: r[1] for r in conn.execute("SELECT name, last_run FROM tsetmc_p0_state")}
    return {
        "session_of_values": day,
        "session_of_board": board_day,
        "target_universe": universe,
        "native": kinds.get("native", 0),
        "mixed": kinds.get("mixed", 0),
        "reconstructed": max(universe - rows_day, 0),
        "rows_in_session": rows_day,
        "rows_total": rows_all,
        "distinct_symbols": symbols_all,
        "sessions_covered": sessions or 0,
        "board_traded_symbols": board_rows,
        "watchlist_symbols": watch,
        "corporate_rows_stored": corp_rows,
        "other_p0_requests_per_run": {"corporate_events": 4, "state_and_notices": 3},
        "p0_last_run": p0_runs,
        "budget_per_day": budget,
        "native_coverage_of_target_pct": round(100.0 * kinds.get("native", 0) / universe, 2) if universe else 0.0,
        "native_coverage_of_board_pct": round(100.0 * kinds.get("native", 0) / board_rows, 2) if board_rows else 0.0,
        "avg_requests_per_symbol": round(rows_all / symbols_all, 2) if symbols_all else 0.0,
        # «برخوردِ کش» درِ آخرین اجرا: هدف‌هایی که ردیف داشتند و درخواست نزدند
        "cache_hit_pct": round(100.0 * min(rows_day, universe) / universe, 2) if universe else 0.0,
        "estimated_requests_per_day": {
            "watchlist": min(watch, budget),
            "funnel_candidates": min(board_rows, budget),
            "full_target_universe": min(universe, budget),
            "all_board_traded": board_rows,
        },
        "days_to_fill_board_at_current_budget": (round(board_rows / budget, 1) if budget else None),
    }


def render(m: dict) -> str:
    def row(label, value):
        return "%-42s %s" % (label, value)

    out = [
        "گزارشِ پوششِ مبدأِ ClientType (بی‌درخواستِ تازه، بی‌تغییرِ بودجه)",
        "-" * 64,
        row("نشستِ دارایِ ارزشِ مبدأ", m["session_of_values"] or "-"),
        row("نشستِ جاریِ تابلو", m["session_of_board"] or "-"),
        row("دامنهٔ هدفِ آن نشست (نماد)", m["target_universe"]),
        row("native", m["native"]),
        row("mixed", m["mixed"]),
        row("reconstructed (بی‌ردیف = بازسازی)", m["reconstructed"]),
        row("پوششِ مبدأ از هدف (٪)", m["native_coverage_of_target_pct"]),
        row("پوششِ مبدأ از کلِّ تابلویِ معامله‌شده (٪)", m["native_coverage_of_board_pct"]),
        row("ردیفِ کل / نمادِ distinct / نشست", "%s / %s / %s" % (
            m["rows_total"], m["distinct_symbols"], m["sessions_covered"])),
        row("میانگینِ درخواست به ازای نماد", m["avg_requests_per_symbol"]),
        row("برخوردِ کشِ اجرایِ بعدی (٪)", m["cache_hit_pct"]),
        row("  (ردیفِ از پیش موجود ÷ هدف؛ این‌ها درخواست نمی‌خواهند)", ""),
        "",
        "برآوردِ درخواست/روز با همین سقفِ %s:" % m["budget_per_day"],
        row("  دیده‌بان", m["estimated_requests_per_day"]["watchlist"]),
        row("  نامزد‌هایِ قیف (معامله‌شده‌های تابلو)", m["estimated_requests_per_day"]["funnel_candidates"]),
        row("  دامنهٔ هدفِ نشست", m["estimated_requests_per_day"]["full_target_universe"]),
        row("  پرکردنِ کاملِ تابلو چند روز می‌برد",
            m["days_to_fill_board_at_current_budget"]),
        "",
        "دو خانوادۀ دیگرِ P0 (درخواستِ ثابت، بی‌بودجهٔ نمادی):",
        row("  رویدادِ شرکتی درِ هر اجرا", m["other_p0_requests_per_run"]["corporate_events"]),
        row("  وضعیت/پیام/نظارت درِ هر اجرا", m["other_p0_requests_per_run"]["state_and_notices"]),
        row("  ردیفِ رویدادِ ذخیره‌شده", m["corporate_rows_stored"]),
        "",
        "نکته: نشستِ جاریِ TSETMC برایِ GetClientTypeHistory پاسخ 500 می‌دهد؛",
        "پوششِ مبدأ برایِ «روزِ بسته‌شده» معنا دارد و درِ ساعاتِ بازار همه",
        "reconstructed است. این عدد را با پوششِ کاملِ یک نشستِ بسته مقایسه کنید.",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(REPO, "market.db"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.db):
        print("بانکی در کار نیست:", a.db)
        return 2
    conn = sqlite3.connect("file:%s?mode=ro" % a.db.replace(os.sep, "/"), uri=True)
    try:
        m = measure(conn)
    finally:
        conn.close()
    print(json.dumps(m, ensure_ascii=False, indent=2) if a.json else render(m))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
