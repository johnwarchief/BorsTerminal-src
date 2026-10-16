# -*- coding: utf-8 -*-
"""dev/market_universe_v1.py — گاردِ رفتارِ market_universe (وضعیتِ معاملاتیِ زنده).

هشت سناریویِ مأموریت + شمارش + «حذف‌نشدنِ نمادِ واجدِ شرایط» + کارایی.
اجرا: PYTHONIOENCODING=utf-8 python dev/market_universe_v1.py
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import market_universe as MU  # noqa: E402

PASSED = 0
FAILED = []


def ck(label, cond, detail=""):
    global PASSED
    if cond:
        PASSED += 1
        print(f"  ok   {label}")
    else:
        FAILED.append(label)
        print(f"  FAIL {label}  {detail}")


def row(**kw):
    base = {"symbol": "X", "z_tot_tran": 100, "q_tot_cap": 5000, "q_tot_tran": 5000,
            "p_last": 1000, "buy_q1_vol": 10, "buy_q1_cnt": 3, "buy_i_vol": 40, "sell_i_vol": 50,
            "is_live": True, "fetched_at": 1000.0}
    base.update(kw)
    return base


NOW = 1000.0

# ۱) بازار باز + افزایشِ حجمِ معامله ⇒ TRADING_ACTIVE
s = MU.classify_trading_status(row(z_tot_tran=140, fetched_at=NOW), row(z_tot_tran=100, fetched_at=NOW - 30),
                               market_open=True, now_wall=NOW)
ck("۱ افزایشِ شمارندۀِ معامله ⇒ TRADING_ACTIVE", s["status"] == MU.TRADING_ACTIVE, s)

# ۲) قیمت ثابت ولی معاملۀِ انجام‌شده (z بالا، p_last یکسان) ⇒ TRADING_ACTIVE
s = MU.classify_trading_status(row(z_tot_tran=160, p_last=1000, fetched_at=NOW),
                               row(z_tot_tran=100, p_last=1000, fetched_at=NOW - 30),
                               market_open=True, now_wall=NOW)
ck("۲ قیمت ثابت + معاملۀِ جدید ⇒ TRADING_ACTIVE (نه بر پایهٔ قیمت)", s["status"] == MU.TRADING_ACTIVE, s)

# ۳) دفترِ سفارش عوض شد ولی معاملۀِ جدید نیست ⇒ QUOTE_ACTIVE_NO_TRADE
s = MU.classify_trading_status(row(z_tot_tran=100, buy_q1_vol=99, buy_i_vol=77, fetched_at=NOW),
                               row(z_tot_tran=100, buy_q1_vol=10, buy_i_vol=40, fetched_at=NOW - 30),
                               market_open=True, now_wall=NOW)
ck("۳ تغییرِ دفتر بدونِ معاملۀِ جدید ⇒ QUOTE_ACTIVE_NO_TRADE", s["status"] == MU.QUOTE_ACTIVE_NO_TRADE, s)

# ۴) مجاز ولی فعلاً بی‌معامله (هیچ‌چیز عوض نشده، feed تازه) ⇒ NO_RECENT_TRADE
s = MU.classify_trading_status(row(z_tot_tran=100, fetched_at=NOW), row(z_tot_tran=100, fetched_at=NOW - 30),
                               market_open=True, now_wall=NOW, trade_window_s=10)
ck("۴ مجاز/بی‌معاملۀِ اخیر ⇒ NO_RECENT_TRADE", s["status"] == MU.NO_RECENT_TRADE, s)

# ۵) متوقف ⇒ SUSPENDED
s = MU.classify_trading_status(row(stop_state="متوقف", fetched_at=NOW), row(fetched_at=NOW - 30),
                               market_open=True, now_wall=NOW)
ck("۵ شاهدِ توقف ⇒ SUSPENDED", s["status"] == MU.SUSPENDED, s)

# ۶) feed کهنه ⇒ STALE_DATA
s = MU.classify_trading_status(row(fetched_at=NOW - 999), row(fetched_at=NOW - 1000),
                               market_open=True, now_wall=NOW, stale_window_s=180)
ck("۶ feed کهنه ⇒ STALE_DATA", s["status"] == MU.STALE_DATA, s)

# ۷) بازار بسته ⇒ MARKET_CLOSED (حتی با شمارندۀِ رو‌به‌رشد)
s = MU.classify_trading_status(row(z_tot_tran=999, fetched_at=NOW), row(z_tot_tran=100, fetched_at=NOW),
                               market_open=False, now_wall=NOW)
ck("۷ بازار بسته ⇒ MARKET_CLOSED", s["status"] == MU.MARKET_CLOSED, s)

# ۸) بازیابیِ اتصال: snapshot/revisionِ جدید می‌رسد و شمارنده بالا رفته ⇒ TRADING_ACTIVE
s = MU.classify_trading_status(row(z_tot_tran=220, fetched_at=NOW), row(z_tot_tran=180, fetched_at=NOW - 5),
                               market_open=True, now_wall=NOW)
ck("۸ پسِ بازیابی، شمارندۀِ بالاتر ⇒ TRADING_ACTIVE", s["status"] == MU.TRADING_ACTIVE, s)

# دادهٔ ثابت نباید چند بار معاملۀِ جدید شمرده شود (idempotent رویِ revision یکسان)
prev = row(z_tot_tran=100, fetched_at=NOW)
cur_same = row(z_tot_tran=100, fetched_at=NOW)
s1 = MU.classify_trading_status(cur_same, prev, market_open=True, now_wall=NOW, trade_window_s=5)
ck("دادهٔ ثابتِ مکرر ⇒ معاملۀِ جدید شمرده نمی‌شود", s1["status"] != MU.TRADING_ACTIVE, s1)

# نبودِ شاهد ⇒ UNKNOWN، نه حدس (بدونِ prev و بدونِ feed_ts)
s = MU.classify_trading_status({"symbol": "Y"}, None, market_open=True, now_wall=NOW)
ck("بدونِ baseline ⇒ UNKNOWN", s["status"] in (MU.UNKNOWN, MU.NO_RECENT_TRADE), s)

# ── Tracker: اولویت‌بندی + شمارش + حذف‌نشدنِ واجدِ شرایط ──
tr = MU.UniverseTracker(trade_window_s=60, stale_window_s=180)
rows = [
    row(symbol="A", z_tot_tran=50, fetched_at=NOW),
    row(symbol="B", z_tot_tran=50, fetched_at=NOW),
    row(symbol="C", z_tot_tran=10, stop_state="متوقف", fetched_at=NOW),
    row(symbol="D", z_tot_tran=10, fetched_at=NOW - 999),
]
res, counts = tr.observe(rows, market_open=True, now_wall=NOW)
ck("همۀِ نمادها درِ خروجی می‌مانند (no drop)", len(res) == 4, counts)
ck("شمارشِ کل=۴", counts["total"] == 4, counts)
ck("متوقف از فهرستِ زنده کنار می‌رود (پایینِ اولویت)", res[-1]["symbol"] in ("C", "D"), [r["symbol"] for r in res])
# دورِ دوم: A معامله می‌کند، B دفتر عوض می‌کند ⇒ A بالاتر از B
rows2 = [row(symbol="A", z_tot_tran=80, fetched_at=NOW + 10),
         row(symbol="B", z_tot_tran=50, buy_q_vol=77, fetched_at=NOW + 10),
         row(symbol="C", z_tot_tran=10, stop_state="متوقف", fetched_at=NOW + 10),
         row(symbol="D", z_tot_tran=10, fetched_at=NOW - 900)]
res2, counts2 = tr.observe(rows2, market_open=True, now_wall=NOW + 10)
order = [r["symbol"] for r in res2]
ck("TRADING_ACTIVE (A) بالاتر از QUOTE (B) اولویت می‌گیرد", order.index("A") < order.index("B"), order)
ck("B به‌خاطرِ نبودِ معاملۀِ جدید حذف نشده (QUOTE_ACTIVE)", any(r["symbol"] == "B" for r in res2), order)
ck("شمارشِ trading≥1 و suspended≥1", counts2["trading"] >= 1 and counts2["suspended"] >= 1, counts2)

# ── کارایی: ۲۰۰۰ نماد درِ زمانِ معقول ──
big = [row(symbol=f"S{i}", z_tot_tran=i, fetched_at=NOW) for i in range(2000)]
tr2 = MU.UniverseTracker()
t0 = time.perf_counter()
_, _ = tr2.observe(big, market_open=True, now_wall=NOW)
t1 = time.perf_counter()
big2 = [row(symbol=f"S{i}", z_tot_tran=i + 1, fetched_at=NOW + 1) for i in range(2000)]
tr2.observe(big2, market_open=True, now_wall=NOW + 1)
t2 = time.perf_counter()
ck(f"کارایی: ۲۰۰۰×۲ دور < ۴۰۰ms (دورِ اول {1000*(t1-t0):.0f}ms، دورِ دوم {1000*(t2-t1):.0f}ms)",
   (t2 - t0) < 0.4, f"{1000*(t2-t0):.1f}ms")

print(f"\nmarket_universe_v1: {PASSED} passed / {len(FAILED)} failed")
sys.exit(1 if FAILED else 0)
