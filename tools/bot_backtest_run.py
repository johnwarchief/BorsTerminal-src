#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/bot_backtest_run.py — اجرایِ واقعیِ بک‌تست رویِ price_history (فقط‌خواندنی)

مأموریتِ ۱۴۰۵-۰۷-۲۳، بندِ ۶-۲/۶-۵. گاردِ `dev/bot_paper_v1109.py` رفتار را رویِ
fixture قفل می‌کند؛ این ابزار همان موتور را رویِ دادهٔ *واقعاً* جمع‌شده می‌اندازد
تا عددی که درِ گزارش می‌آید از تاریخچهٔ بازار باشد، نه از موجِ سینوسیِ تست.

خواندنی: `sqlite3` با `file:...?mode=ro`. هیچ نوشتنِ رویِ بانکِ عملیاتی.

نمونه:
  PYTHONIOENCODING=utf-8 py -3.14 tools/bot_backtest_run.py \\
      --min-bars 250 --limit 120 --strategy ma_cross --fast 20 --slow 60 --folds 3
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backtest_engine import (BUY, SELL, BacktestEngine, MaCross, RiskLimits,  # noqa: E402
                             BuyAndHold, bars_by_symbol, session_dates,
                             split_chronic, walk_forward)
from trade_sim import Bar, CostModel  # noqa: E402

OUT_DIR = os.path.join(ROOT, "_audit", "bot_backtest")


def market_db(cli: str | None) -> str:
    if cli:
        return cli
    import bors_config
    return bors_config.DB_PATH


def load(db: str, *, min_bars: int, limit: int, only: list[str] | None) -> list[Bar]:
    """بارگذاریِ کندل‌ها با prev_close از خودِ توالیِ همان نماد."""
    conn = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    where, args = [], []
    if only:
        where.append("symbol IN (%s)" % ",".join("?" * len(only)))
        args.extend(only)
    sql = ("SELECT symbol, date, open, high, low, close, volume, value, src"
           " FROM price_history")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY symbol, date"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    out: list[Bar] = []
    per_symbol: dict[str, int] = {}
    prev_by: dict[str, tuple] = {}
    for r in rows:
        s = r["symbol"]
        if only is None:
            per_symbol[s] = per_symbol.get(s, 0) + 1
        pc = prev_by.get(s)
        out.append(Bar(symbol=s, date=r["date"],
                       open=_f(r["open"]), high=_f(r["high"]), low=_f(r["low"]),
                       close=_f(r["close"]), volume=_f(r["volume"]), value=_f(r["value"]),
                       prev_close=(pc[1] if pc else None), src=r["src"]))
        prev_by[s] = (r["date"], _f(r["close"]))
    if only is None:
        keep = {s for s, n in per_symbol.items() if n >= min_bars}
        # انتخابِ *قطعی*: نمادهایِ پُربارِ بیشتر، و درِ تساویِ شمار نامِ ترتیبی.
        # بی‌این، universe با هر اجرا عوض می‌شد و digest بی‌معنی می‌ماند.
        ranked = sorted(keep, key=lambda s: (-per_symbol[s], s))
        if limit:
            ranked = ranked[:limit]
        out = [b for b in out if b.symbol in set(ranked)]
    return out


def _f(v):
    return None if v is None else float(v)


def fmt(x, nd=0):
    if x is None:
        return "—"
    return ("{:,.%df}" % nd).format(x).replace(",", "٬")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--min-bars", type=int, default=250)
    ap.add_argument("--limit", type=int, default=60, help="سقفِ نماد (۰ = بی‌سقف)")
    ap.add_argument("--strategy", default="ma_cross", choices=("ma_cross", "buy_hold"))
    ap.add_argument("--fast", type=int, default=20)
    ap.add_argument("--slow", type=int, default=60)
    ap.add_argument("--symbol", action="append", default=None, help="فقط این نمادها")
    ap.add_argument("--cash", type=float, default=1_000_000_000.0)
    ap.add_argument("--commission-bps", type=float, default=30.0)
    ap.add_argument("--slippage-bps", type=float, default=10.0)
    ap.add_argument("--volume-share", type=float, default=0.02)
    ap.add_argument("--size-fraction", type=float, default=0.1)
    ap.add_argument("--max-order-value", type=float, default=None)
    ap.add_argument("--max-symbol-exposure", type=float, default=None)
    ap.add_argument("--max-total-exposure", type=float, default=None)
    ap.add_argument("--max-daily-loss", type=float, default=None)
    ap.add_argument("--folds", type=int, default=0, help="walk-forward (۰ = خاموش)")
    ap.add_argument("--tag", default=None)
    a = ap.parse_args(argv)

    db = market_db(a.db)
    if not os.path.exists(db):
        print("بانکِ بازار پیدا نشد: %s" % db)
        return 2
    bars = load(db, min_bars=a.min_bars, limit=a.limit, only=a.symbol)
    if not bars:
        print("هیچ ردیفی برایِ این universe نیست")
        return 2
    by = bars_by_symbol(bars)
    dates = session_dates(by)
    costs = CostModel(a.commission_bps, a.slippage_bps, a.volume_share)
    limits = RiskLimits(max_order_value=a.max_order_value,
                        max_symbol_exposure=a.max_symbol_exposure,
                        max_total_exposure=a.max_total_exposure,
                        max_daily_loss=a.max_daily_loss,
                        position_size_fraction=a.size_fraction)
    strat = (MaCross(a.fast, a.slow) if a.strategy == "ma_cross" else BuyAndHold())

    runs: dict[str, dict] = {}
    plans = {"full": (dates,)}
    sp = split_chronic(dates)
    plans["split"] = tuple((sp[k], (k,)) for k in ("train", "validation", "test"))
    if a.folds:
        plans["walk"] = tuple((f["test"], ("fold%d" % i,)) for i, f in
                             enumerate(walk_forward(dates, folds=a.folds), 1))

    def run_once(dates_subset, label):
        eng = BacktestEngine(by_symbol=by, strategy=strat, costs=costs, limits=limits,
                             start_cash=a.cash, dates=dates_subset)
        res = eng.run()
        runs[label] = {"metrics": res.metrics, "digest": res.digest(),
                       "manifest": res.manifest,
                       "span": [dates_subset[0], dates_subset[-1]] if len(dates_subset) else [None, None],
                       "n_sessions": len(dates_subset)}
        return res

    whole = run_once(dates, "full")
    for subset, (label,) in plans["split"]:
        run_once(subset, "split_" + label)
    for subset, (label,) in plans.get("walk", ()):
        run_once(subset, "walk_" + label)

    stamp = a.tag or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs(OUT_DIR, exist_ok=True)
    payload = {"universe": {"symbols": len(by), "min_bars": a.min_bars,
                            "sessions": len(dates), "span": [dates[0], dates[-1]],
                            "bar_rows": len(bars)},
               "strategy": getattr(strat, "id", str(strat)), "params": dict(strat.params),
               "cost_model": costs.as_dict(), "risk_limits": dict(limits.__dict__),
               "start_cash": a.cash, "runs": runs, "db": db}
    path = os.path.join(OUT_DIR, "run_%s.json" % stamp)
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    m = whole.metrics
    print("── universe: %s نماد، %s نشَست، %s ← %s، %s ردیف"
          % (fmt(len(by)), fmt(len(dates)), dates[0], dates[-1], fmt(len(bars))))
    print("── استراتژی: %s %s | کارمزد %sbp لغزش %sbp | سهمِ حجم %s"
          % (getattr(strat, "id", "?"), json.dumps(dict(strat.params), ensure_ascii=False),
             a.commission_bps, a.slippage_bps, a.volume_share))
    print("── کلِ دورۀ تاریخی:")
    for k in ("trades", "buys", "sells", "win_rate", "fees_total", "turnover",
              "total_return", "max_drawdown", "sharpe_like", "rejected_total"):
        v = m.get(k)
        print("   %-16s %s" % (k, ("%.4f" % v) if isinstance(v, float) and abs(v) < 10
                               else fmt(v) if isinstance(v, (int, float)) else v))
    print("   rejections      %s" % json.dumps(m.get("rejections", {}), ensure_ascii=False))
    print("   kill switch     %s" % json.dumps(m.get("kill_switch"), ensure_ascii=False))
    print("── برشِ زمانی (هر پنجره جدا، بی‌نشتِ آینده):")
    for label in ("split_train", "split_validation", "split_test"):
        r = runs.get(label)
        if not r:
            continue
        mm = r["metrics"]
        print("   %-14s %s←%s trades=%s return=%s mdd=%s fees=%s digest=%s"
              % (label, r["span"][0], r["span"][1], mm.get("trades"),
                 "%.4f" % mm["total_return"] if mm.get("total_return") is not None else "—",
                 "%.4f" % mm["max_drawdown"] if mm.get("max_drawdown") is not None else "—",
                 fmt(mm.get("fees_total")), r["digest"]))
    if a.folds:
        print("── walk-forward:")
        for label, r in runs.items():
            if not label.startswith("walk_"):
                continue
            mm = r["metrics"]
            print("   %-10s %s←%s trades=%s return=%s" % (label[5:], r["span"][0], r["span"][1],
                                                          mm.get("trades"),
                                                          "%.4f" % mm["total_return"]
                                                          if mm.get("total_return") is not None else "—"))
    d1 = runs["full"]["digest"]
    verify = BacktestEngine(by_symbol=by, strategy=strat, costs=costs, limits=limits,
                            start_cash=a.cash, dates=dates).run().digest()
    print("── بازتولیدِ همان digest: %s (%s در برابرِ %s)" % (d1 == verify, d1, verify))
    print("saved: %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
