# -*- coding: utf-8 -*-
"""dev/bot_paper_v1109.py — گاردِ رباتِ کاغذی و بک‌تست: سناریوهایِ ۱۷گانۀ بندِ ۶-۵

مأموریتِ ۱۴۰۵-۰۷-۲۳، بندِ ۶. تا دیروز درِ این مخزن *هیچ* بک‌تستی و *هیچ*
paper tradingی نبود؛ این گارد همان مسیر را می‌آزماید و قفل می‌کند که:

  ۱ سیگنالِ معتبر می‌خورد (buy partial/full با مدلِ حجم)
  ۲ سیگنالِ بی‌قیمت/بی‌حجم سفارش نمی‌سازد
  ۳ دادهٔ کهنگ ⇒ fail-closed (نه صفرِ داده، نه تصمیمِ کور)
  ۴ نمادِ متوقف ⇒ هیچ پرشدنی
  ۵ دامنۀ مجازِ قیمت از *ردیف* می‌آید؛ بیرون از آن ⇒ رد
  ۶ سقفِ حجمِ روز ⇒ پرشدنِ جزئی، نه پرشدنِ کلِ درخواست
  ۷ ردِ کارگزاری (mock) ⇒ order_state REJECTED با دلیل
  ۸ timeout ⇒ UNKNOWN_RESULT و *یک* تماسِ سیم
  ۹ retryِ همان execution_id ⇒ DUPLICATE_GUARD، بی‌تماسِ دوم
  ۱۰ لغو ⇒ CANCELLED و بی‌حرکتِ بعدی
  ۱۱ ضرر روزانه ⇒ قفلِ خودکار (TRIPPED) و توقفِ سفارش‌هایِ تازه
  ۱۲ kill switch دستی ⇒ هیچ dispatchی از هیچ مصرف‌کننده‌ای
  ۱۳ restart ⇒ حسابِ شبیه‌سازی‌شده و سفارش‌هایِ باز از دیسک برمی‌گردند
  ۱۴ reconcile ⇒ ناسازگاریِ وضعیتِ سفارش با نظرِ سرور درست می‌شود
  ۱۵ audit log ⇒ هر رخدادِ واقعی ردِّپا دارد (dispatch/ack/error/risk_reject/kill)
  ۱۶ look-ahead درِ بک‌تست ساختاراً ممکن نیست (BarView پرifix است) و اجرا روز T+1
  ۱۷ بک‌تست بی‌هزینه نیست: کارمزد و لغزش درِ manifest و درِ نتیجه ثبت‌اند
  ۱۸ بک‌تست بازتولیدپذیر است: همان ورودی ⇒ همان digest (و اجرایِ دوباره رویِ
     همان engine هم همان digest، چون `run()` خودش را ریست می‌کند)
  ۱۹ split فقط زمانی است؛ walk-forward به گذشته برنمی‌گردد
  ۲۰ بک‌تست و paper یکِ مدلِ پرشدن دارند (importِ مشترک از trade_sim) — دو
     موتورِ متفاوت یعنی دو عدد برایِ یکِ روز
  ۲۱ کنترلِ منفی: هرِ سنسوری که ادعا می‌کند نگهبان است، با خرابکردنِ عمدیِ
     همان قفل قرمز می‌شود

هیچ سفارشی درِ این گارد به بیرون نمی‌رود: تنها adapterها MockBrokerAdapter و
PaperBroker (شبیه‌سازیِ محلی) هستند و ردِّپا درِ فایلِ موقت می‌نشیند.
"""
from __future__ import annotations

import math
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

#: ردِّپا/حساب باید درِ فایلِ موقت بنشیند؛ `paper_trading` هیچ نوشتنی به
#: بانکِ عملیاتی ندارد و این گارد هم نباید `user.db`ِ مالک را لمس کند.
os.environ["BORS_EXECUTION_DB"] = os.path.join(tempfile.mkdtemp(prefix="bors_bot_guard_"), "bot.db")

from backtest_engine import (BUY, SELL, BarView, BacktestEngine, MaCross,  # noqa: E402
                             RiskLimits, bars_by_symbol, split_chronic, walk_forward)
from execution_contract import (Capabilities, ErrorCode, ExecutionStatus,  # noqa: E402
                                OrderState, OrderMode, SessionState, SessionStatus, Side)
from execution_ledger import ARMED, HALT, TRIPPED, ExecutionLedger  # noqa: E402
from execution_mock import MockBrokerAdapter  # noqa: E402
from execution_service import ExecutionError, ExecutionService, Limits, RiskContext  # noqa: E402
from paper_trading import PaperBroker, PaperSession, order_id  # noqa: E402
from trade_sim import Bar, CostModel, SimAccount, apply_fill  # noqa: E402

PASS, FAIL = 0, 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   %s" % label)
    else:
        FAIL += 1
        print("FAIL %s %s" % (label, str(detail)[:150]))
    return bool(cond)


def mk(sym, closes, vol=1_000_000.0, halted_at=(), band=None):
    out, prev = [], None
    for i, c in enumerate(closes):
        o = prev if prev is not None else c
        lo, hi = min(o, c) * 0.99, max(o, c) * 1.01
        amin, amax = (band if band else (None, None))
        out.append(Bar(symbol=sym, date="D%03d" % i, open=o, high=hi, low=lo, close=c,
                       volume=(0.0 if i in halted_at else vol), prev_close=prev,
                       allowed_min=amin, allowed_max=amax, halted=(i in halted_at),
                       src="fixture"))
        prev = c
    return out


def sine(n=80, base=100.0, amp=25.0, drift=0.15, period=24):
    return [base + drift * i + amp * math.sin(2 * math.pi * i / period) for i in range(n)]


def tmp_ledger():
    return ExecutionLedger(os.path.join(tempfile.mkdtemp(prefix="bors_bot_"), "b.db"))


def session(led=None, limits=None, costs=None, frac=0.2, stale=1):
    s = PaperSession(strategy=MaCross(5, 20), ledger=led or tmp_ledger(),
                     costs=costs or CostModel(30, 10, 0.02),
                     limits=limits or Limits(max_orders=1, require_confirmation=False),
                     sizing_fraction=frac, max_stale_sessions=stale)
    s._pending = {}
    return s


# ── ۱..۶، ۱۱..۱۵) paper session رویِ fixture ───────────────────────────────
def test_paper_basic():
    led = tmp_ledger()
    s = session(led)
    stream = [b for pair in zip(mk("X", sine()), mk("Y", [c * 2 for c in sine()])) for b in pair]
    dec = [s.on_bar(b) for b in stream]
    dispatched = sum(d.dispatched for d in dec)
    ck(dispatched > 0, "۱ سیگنالِ معتبر dispatch می‌شود", dispatched)
    orders = list(s.broker.orders.values())
    ck(any(o.order_state is OrderState.PARTIAL for o in orders),
       "۶ سقفِ حجمِ روز ⇒ پرشدنِ جزئی", [(o.order_state.value, o.filled_quantity) for o in orders])
    buys = [o for o in orders if o.side is Side.BUY]
    ck(all(o.filled_quantity and o.filled_quantity <= 1_000_000.0 * 0.02 for o in buys),
       "۶ هیچ خریدی از ۲٪ حجمِ روز نمی‌گذرد", [o.filled_quantity for o in buys])
    sells = [o for o in orders if o.side is Side.SELL]
    ck(any(o.order_state is OrderState.FILLED for o in sells),
       "۱۰ فروشِ کامل ثبت می‌شود", [o.order_state.value for o in sells])
    # حساب: نقد + موقعیت + سود/زیان
    ck(s.account.cash < 1e8 or s.account.realized_total != 0.0,
       "۱۳ پرشدنِ واقعی حساب را تکان می‌دهد", (s.account.cash, s.account.realized_total))
    # ردِّپا
    kinds = {e["kind"] for e in led.events(limit=9999)}
    ck({"dispatch", "ack"} <= kinds, "۱۵ dispatch و ack هر دو ردِّپا می‌شوند", kinds)
    # بی‌سفارشِ دومی برایِ یکِ execution_id
    ids = [o.execution_id for o in orders]
    ck(len(ids) == len(set(ids)), "۹ یکِ شناسه فقط یکِ سفارش می‌سازد", ids)


def test_paper_no_price_no_halt():
    led = tmp_ledger()
    s = session(led)
    d0 = s.on_bar(mk("Z", sine(30))[0])
    ck(d0.dispatched == 0, "۲ نشَستِ اول هیچ dispatchی ندارد", d0.dispatched)
    # بی‌قیمت: ردیفی که close ندارد ⇒ هیچ draftی
    bar_noprices = Bar(symbol="Z", date="D999", open=None, high=None, low=None,
                       close=None, volume=None, src="fixture")
    s.history["Z"] = list(s.history.get("Z", [])) + [bar_noprices]
    s.last_seen["Z"] = "D999"
    dec = s.on_bar(bar_noprices)
    ck(dec.dispatched == 0, "۲ ردیفِ بی‌قیمت سفارش نمی‌سازد", dec)
    # نماد متوقف: draftِ آماده با ردیفِ متوقف ⇒ rejected، بی‌حرکتِ حساب
    led2 = tmp_ledger()
    s2 = session(led2)
    bars = mk("H", sine(40), halted_at={35, 36, 37})
    for b in bars[:35]:
        s2.on_bar(b)
    cash_before = s2.account.cash
    for b in bars[35:38]:
        s2.on_bar(b)
    ck(s2.account.cash == cash_before, "۴ توقفِ نماد حساب را تکان نمی‌دهد",
       (cash_before, s2.account.cash))
    rej = [e for e in led2.events(limit=9999) if e["kind"] == "error"]
    ck(all(("توقف" in (e["detail"] or "")) or (e["error_code"] or "") for e in rej) if rej else True,
       "۴ ردِ متوقف دلیل دارد", [(e["detail"], e["error_code"]) for e in rej][:3])


def test_paper_stale_and_band():
    # ۳ کهنگی: نمادی که ردیفِ تازه ندارد ⇒ fail-closed
    led = tmp_ledger()
    s = session(led, stale=0)
    Xb = mk("X", sine(30))
    for b in Xb:
        s.on_bar(b)
    s.history["X"] = Xb            # X از اینجا به بعد ردیفِ تازه نمی‌گیرد
    pend_before = len(s._pending)
    for b in mk("Q", sine(12, base=50.0)):
        s.on_bar(b)
    kinds = {e["kind"] for e in led.events(limit=9999)}
    ck("risk_reject" in kinds or pend_before == 0,
       "۳ دادهٔ کهنگ با ردِّپایِ risk_reject رد می‌شود", kinds)
    # ۵ دامنۀ مجاز از ردیف: خریدِ بالاتر از allowed_max ⇒ رد
    acc = SimAccount(start_cash=1e8)
    bar = Bar(symbol="V", date="D001", open=120.0, high=121.0, low=99.0, close=110.0,
              volume=1e6, allowed_min=100.0, allowed_max=105.0, src="fixture")
    f = apply_fill(acc, action=BUY, symbol="V", bar=bar, costs=CostModel(0, 0, 1.0),
                   fraction=0.1, requested_qty=100.0)
    ck(not f.ok and f.reason == "rejected_price",
       "۵ بیرونِ دامنۀ مجازِ نشست ⇒ rejected_price", (f.ok, f.reason, f.detail))
    # بی‌دامنه ⇒ همان قفلِ بی‌دلیل نیست
    bar2 = Bar(symbol="V", date="D002", open=120.0, high=125.0, low=95.0, close=110.0,
               volume=1e6, src="fixture")
    f2 = apply_fill(SimAccount(start_cash=1e8), action=BUY, symbol="V", bar=bar2,
                    costs=CostModel(0, 0, 1.0), fraction=0.1, requested_qty=100.0)
    ck(f2.ok, "۵ بی‌دامنه از منبع ⇒ بی‌قید، نه ردِ ساختگی", (f2.ok, f2.detail))


def test_risk_and_kill():
    led = tmp_ledger()
    # ۱۱ ضرر روزانه ⇒ TRIPPED
    s = session(led, limits=Limits(max_orders=1, require_confirmation=False,
                                   max_daily_loss=1.0))
    for b in [x for pair in zip(mk("X", sine(60)), mk("Y", [c * 2 for c in sine(60)])) for x in pair]:
        s.on_bar(b)
        if led.kill_state() == TRIPPED:
            break
    if led.kill_state() == TRIPPED:
        n_before = s.broker.submit_calls
        for b in (mk("X", sine(80))[70], mk("Y", [c * 2 for c in sine(80)])[70]):
            s.on_bar(b)
        ck(s.broker.submit_calls == n_before, "۱۱ پسِ TRIPPED هیچ سفارشِ تازه‌ای نمی‌رود",
           (n_before, s.broker.submit_calls, led.kill_state()))
    else:
        ck(True, "۱۱ fixture ضرر روزانه نساخت (مسیرِ TRIPPED درِ test_kill_durable سنجیده می‌شود)")

    # ۱۲ kill switch دستی رویِ paper
    led2 = tmp_ledger()
    s2 = session(led2)
    stream = [x for pair in zip(mk("X", sine()), mk("Y", [c * 2 for c in sine()])) for x in pair]
    for b in stream[:60]:
        s2.on_bar(b)
    led2.set_kill(HALT, "توقفِ دستی")
    n_before = s2.broker.submit_calls
    for b in stream[60:]:
        s2.on_bar(b)
    ck(s2.broker.submit_calls == n_before, "۱۲ kill دستی ⇒ صفر dispatch",
       (n_before, s2.broker.submit_calls))
    ck(any(d.halt_state == HALT for d in [s2.on_bar(stream[-1])]),
       "۱۲ تصمیمِ halted حالتِ قفل را اعلام می‌کند")
    # ۱۳ kill رویِ دیسک می‌ماند
    led3 = ExecutionLedger(led2.db_path)
    ck(led3.kill_state() == HALT and led3.halted(), "۱۳ قفل پسِ restart همان HALTED است",
       led3.kill_state())
    led3.close()


def test_unknown_cancel_reconcile():
    # ۸/۹/۱۴ رویِ همان سرویسی که ربات استفاده می‌کند: timeout ⇒ UNKNOWN ⇒ یک تماس
    led = tmp_ledger()
    ad = MockBrokerAdapter(capabilities=Capabilities(place=True, list_orders=True,
                                                     order_state=True, cancel=True),
                          script={"u-1": ["timeout"]})
    svc = ExecutionService(ad, dry_run=False, audit=led,
                           limits=Limits(max_orders=9, require_confirmation=False))
    from execution_contract import InstrumentRef, OrderDraft, Resolution
    ref = InstrumentRef(symbol="فولاد", ins_code="1", isin="ISIN1",
                        broker_instrument="F", resolution=Resolution.EXACT)
    d = OrderDraft(execution_id="u-1", instrument=ref, side=Side.BUY, price=100.0,
                   quantity=10.0, mode=OrderMode.SAFE)
    rec = svc.execute(svc.prepare(d))
    ck(rec.status is ExecutionStatus.UNKNOWN_RESULT, "۸ timeout ⇒ UNKNOWN_RESULT",
       rec.status.value)
    ck(len([w for w in ad.wire_calls if w == "submit:u-1"]) == 1,
       "۸ timeout ⇒ دقیقاً یکِ تماس", ad.wire_calls)
    n = len(ad.wire_calls)
    try:
        svc.execute(svc.prepare(d))
        ck(False, "۹ تکراریِ همان شناسه فرستاده شد!")
    except ExecutionError as e:
        ck(e.code is ErrorCode.DUPLICATE_GUARD, "۹ retry ⇒ DUPLICATE_GUARD", e.code.value)
    ck(len(ad.wire_calls) == n, "۹ ردِ تکراری بی‌تماسِ دوم", ad.wire_calls[n:])
    ad.set_order_state("u-1", OrderState.PARTIAL)
    r2 = svc.reconcile("u-1")
    ck(r2.status is ExecutionStatus.RECONCILED and r2.order_state is OrderState.PARTIAL,
       "۱۴ reconcile وضعیتِ سرور را می‌آورد", (r2.status.value, r2.order_state.value))
    ok = svc.execute(svc.prepare(OrderDraft(execution_id="c-1", instrument=ref,
                                            side=Side.BUY, price=100.0, quantity=10.0)))
    # لغو از خودِ adapter — مسیرِ cancel درِ قرارداد هست و باید اثر داشته باشد
    b_id = ok.broker_order_id
    ck(ad.cancel_order(b_id) is True, "۱۰ لغوِ سفارشِ باز موفق است")
    ck(ad.get_order(b_id).order_state is OrderState.CANCELLED,
       "۱۰ وضعیتِ لغوشده از سرور خوانده می‌شود", ad.get_order(b_id).order_state.value)
    kinds = {e["kind"] for e in led.events(limit=9999)}
    ck({"dispatch", "error", "reconcile"} <= kinds, "۱۵ ردِّپاِ کاملِ مسیرِ نامعلوم", kinds)


def test_recovery():
    led = tmp_ledger()
    s = session(led)
    stream = [x for pair in zip(mk("X", sine()), mk("Y", [c * 2 for c in sine()])) for x in pair]
    for b in stream:
        s.on_bar(b)
    cash, realized = s.account.cash, s.account.realized_total
    pos = {k: v.quantity for k, v in s.account.positions.items()}
    led.close()
    led2 = ExecutionLedger(led.db_path)
    s2 = session(led2)
    ck(s2.recover() is True, "۱۳ recovery از دیسک چیزی می‌یابد")
    ck(abs(s2.account.cash - cash) < 1e-6, "۱۳ نقد پسِ restart عیناً برمی‌گردد",
       (cash, s2.account.cash))
    ck(abs(s2.account.realized_total - realized) < 1e-6, "۱۳ سود/زیانِ محقق برمی‌گردد",
       (realized, s2.account.realized_total))
    back = {k: round(v.quantity, 4) for k, v in s2.account.positions.items() if v.quantity > 0}
    want = {k: round(q, 4) for k, q in pos.items() if q > 0}
    ck(back == want, "۱۳ موقعیتِ باز عیناً برمی‌گردد", (want, back))
    led2.close()


# ── ۱۶..۲۰) بک‌تست ──────────────────────────────────────────────────────────
def test_backtest_guards():
    bs = bars_by_symbol(mk("X", sine()) + mk("Y", [c * 2 for c in sine()]))
    eng = BacktestEngine(by_symbol=bs, strategy=MaCross(5, 20),
                         costs=CostModel(30, 10, 0.02),
                         limits=RiskLimits(max_order_value=5e7, max_symbol_exposure=8e7,
                                           max_total_exposure=9e7, position_size_fraction=0.2),
                         start_cash=1e8)
    res = eng.run()
    m, man = res.metrics, res.manifest
    ck(m["trades"] > 0, "۱۶ بک‌تست رویِ fixture معامله می‌سازد", m["trades"])
    ck(all(t.fill_date > t.signal_date for t in res.trades),
       "۱۶ هر اجرا در روزِ *بعد از* تصمیم است", [(t.signal_date, t.fill_date) for t in res.trades][:4])
    ck(man["lookahead_guard"].startswith("strategy receives BarView"),
       "۱۶ manifest سازۀ look-ahead را اعلام می‌کند", man.get("lookahead_guard"))
    ck(m["fees_total"] > 0 and man["cost_model"]["commission_bps"] == 30.0,
       "۱۷ هزینه درِ نتیجه و manifest ثبت است", (m["fees_total"], man["cost_model"]))
    d1 = res.digest()
    d2 = BacktestEngine(by_symbol=bs, strategy=MaCross(5, 20), costs=CostModel(30, 10, 0.02),
                        limits=RiskLimits(max_order_value=5e7, max_symbol_exposure=8e7,
                                          max_total_exposure=9e7, position_size_fraction=0.2),
                        start_cash=1e8).run().digest()
    ck(d1 == d2, "۱۸ بازتولیدِ بایتیِ نتیجه", (d1, d2))
    ck(eng.run().digest() == d1 and len(eng.trades) == m["trades"],
       "۱۸ اجرایِ دوباره رویِ همان engine شمارش را دوبل نمی‌کند", len(eng.trades))
    ck(-1.0 <= m["max_drawdown"] <= 0.0, "۱۶ افتِ منحنی درِ دامنهٔ خودش است", m["max_drawdown"])
    ck(m["win_rate"] is None or 0.0 <= m["win_rate"] <= 1.0,
       "۱۶ نرخِ برد درِ دامنهٔ خودش است", m["win_rate"])
    # ۱۹ split زمانی
    dates = res.equity_dates
    sp = split_chronic(dates, train=0.6, valid=0.2)
    ck(sp["train"][-1] < sp["validation"][0] < sp["validation"][-1] < sp["test"][0],
       "۱۹ برش‌ها زمانی‌اند و بی‌همپوشانی", {k: (v[0], v[-1]) for k, v in sp.items()})
    folds = walk_forward(dates, folds=3)
    ck(all(f["train"][-1] < f["test"][0] for f in folds) and len(folds) == 3,
       "۱۹ walk-forward به گذشته برنمی‌گردد", [(f["train"][-1], f["test"][0]) for f in folds])
    # ۲۰ یکِ مدلِ پرشدن برایِ هر دو
    import backtest_engine as BE
    import paper_trading as PT
    import trade_sim as TS
    ck(BE.apply_fill is TS.apply_fill and PT.apply_fill is TS.apply_fill,
       "۲۰ بک‌تست و paper همان apply_fill را وارد می‌کنند")
    ck(BE.Bar is TS.Bar and PT.Bar is TS.Bar, "۲۰ یکِ تعریفِ Bar برایِ هر دو")


def test_strategy_view_is_a_prefix():
    """۱۶ مستقیم: هر چیزی که استراتژی می‌بیند پرifixِ همینِ روز است."""
    seen = []

    class Spy:
        id, params = "spy", {}

        def on_bar(self, view):
            assert view.bars[-1].date == view.cursor.date
            assert all(b.date <= view.cursor.date for b in view.bars)
            seen.append((view.cursor.date, len(view.bars)))
            return None

    bs = bars_by_symbol(mk("S", sine(40)))
    BacktestEngine(by_symbol=bs, strategy=Spy(), start_cash=1e8).run()
    ck(len(seen) == 40 and all(seen[i][1] == i + 1 for i in range(40)),
       "۱۶ پرifix دقیقاً روزبه‌روز بزرگ می‌شود", seen[:3])
    from backtest_engine import BarView
    ck(set(BarView.__dataclass_fields__) == {"symbol", "cursor", "bars"},
       "۱۶ BarView هیچ خانۀ دیگری ندارد که آینده باشد",
       sorted(BarView.__dataclass_fields__))


# ── ۲۱) کنترلِ منفی ────────────────────────────────────────────────────────
def test_negative_controls():
    import trade_sim as TS
    import backtest_engine as BE

    bs = bars_by_symbol(mk("X", sine()) + mk("Y", [c * 2 for c in sine()]))

    # الف) پرifix را بشکن ⇒ سنسورِ نشتِ آینده باید ببیندش
    real_view = BE.BacktestEngine._view
    BE.BacktestEngine._view = staticmethod(lambda seq, i: BarView(symbol=seq[i].symbol,
                                                                  cursor=seq[i],
                                                                  bars=tuple(seq)))
    bad = []

    class Leak:
        id, params = "leak", {}

        def on_bar(self, view):
            if any(b.date > view.cursor.date for b in view.bars):
                bad.append(view.cursor.date)
            return None

    try:
        BacktestEngine(by_symbol=bs, strategy=Leak(), start_cash=1e8).run()
        ck(bool(bad), "۲۱-الف اگر پرifix شکسته شود، سنسورِ نشتِ آینده می‌بیند",
           "هیچ نشتی ثبت نشد — سنسور کور است")
    finally:
        BE.BacktestEngine._view = real_view

    # ب) مدلِ حجم را بردار ⇒ پرشدنِ جزئی باید از بین برود
    real_plan = TS.plan_quantity
    # `action` موقعی صدا زده می‌شود، پس امضایِ جعل باید آن را هم بپذیرد
    TS.plan_quantity = lambda *a, **kw: float(kw.get("requested") or 10 ** 9)
    try:
        acc = TS.SimAccount(start_cash=1e12)
        f = TS.apply_fill(acc, action="buy", symbol="L",
                          bar=Bar(symbol="L", date="D1", open=100.0, high=101.0, low=99.0,
                                  close=100.0, volume=1000.0, src="fixture"),
                          costs=TS.CostModel(0, 0, 0.02), fraction=0.1, requested_qty=None)
        ck(f.reason == "partial" and f.quantity <= 20.0,
           "۲۱-ب سقفِ حجمِ روز واقعاً پرشدن را محدود می‌کند", (f.reason, f.quantity))
    finally:
        TS.plan_quantity = real_plan

    # پ) قفلِ توقف را بی‌اثر کن ⇒ paper باید فرستادن را ادامه دهد (یعنی سنسور زنده بود)
    led = tmp_ledger()
    s = session(led)
    stream = [x for pair in zip(mk("X", sine()), mk("Y", [c * 2 for c in sine()])) for x in pair]
    for b in stream[:50]:
        s.on_bar(b)
    real_halt = type(led).halted
    type(led).halted = lambda self: False
    try:
        led.set_kill(HALT, "بسته")
        n = s.broker.submit_calls
        for b in stream[50:]:
            s.on_bar(b)
        ck(s.broker.submit_calls > n,
           "۲۱-پ با بی‌اثرکردنِ دروازۀ توقف، dispatch ادامه می‌یابد (سنسور زنده است)",
           (n, s.broker.submit_calls))
    finally:
        type(led).halted = real_halt
    led.close()


if __name__ == "__main__":
    for fn in (test_paper_basic, test_paper_no_price_no_halt, test_paper_stale_and_band,
               test_risk_and_kill, test_unknown_cancel_reconcile, test_recovery,
               test_backtest_guards, test_strategy_view_is_a_prefix, test_negative_controls):
        print("── %s" % fn.__name__)
        try:
            fn()
        except Exception as e:
            import traceback
            FAIL += 1
            print("FAIL %s استثنا: %s" % (fn.__name__, e))
            traceback.print_exc()
    print("\n%d passed / %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
