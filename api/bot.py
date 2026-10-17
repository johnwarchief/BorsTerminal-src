# -*- coding: utf-8 -*-
"""api/bot.py — دروازۀ ربات معاملاتی: کاغذی پیش‌فرض، واقعی فقط با سه قفل.

چرا این فایل هست: `paper_trading.py` و `bot_signals.py` از دورِ ۱۴۰۵-۰۷-۲۳
آماده بودند و ۵۴ سنجه هم می‌گذراندند، ولی **هیچ endpoint و هیچ پنلی** نداشتند؛
یعنی ربات درِ کد بود و درِ برنامه نبود. این فایل همان فاصله است: پیکربندی
اعتبارسنجی‌شده، اجرایِ یکِ نشست، وضعیت، تاریخچه، و توقف/ادامه روی همان
`execution_ledger` که دروازۀ سرخطی می‌نویسد — یک دفتر، دو مصرف‌کننده.

چه چیزی عمداً **نیست**:
• داورِ دوم: تنها منبعِ «تصمیم»، خروجیِ خودِ قیف است (`api/funnel._run` →
  `status_matrix`) و `_membership_map` آن را به in/out/unknown بدل می‌کند.
  هیچ آستانه، وزن یا امتیازی اینجا تعریف نمی‌شود.
• زمان‌بندیِ خودکار: ربات با باز شدنِ برنامه اجرا نمی‌شود. تنها راه،
  `POST /api/bot/run` ازِ خودِ کاربر است.
• وعدهٔ اولی یا قطعی‌بودن اجرا: صف و پرشدن درِ paper **شبیه‌سازی** است
  (`trade_sim.apply_fill`) و درِ مسیرِ واقعی هم فقط «ثبت شد» معنی دارد.

سه قفلِ اجرایِ واقعی (همه با هم، وگرنه paper):
  ۱) `BORS_EXECUTION_LIVE` درِ محیط (همان دروازۀ `api/execution.py`)،
  ۲) نشستِ راستی‌آزمایی‌شدۀ آداپتور + capabilities اعلام‌شده از runtime،
  ۳) `confirm` دقیقاً برابرِ عبارتِ اعلامی درِ پاسخِ `/api/bot/status`.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from typing import Any, Mapping

from fastapi import APIRouter, Body, Request

import bors_config
from bot_signals import FunnelMembership
from execution_ledger import ARMED, HALT, TRIPPED, default_ledger
from execution_service import Limits
from paper_trading import STATE_KEY, PaperSession
from trade_sim import Bar, CostModel, SimAccount

log = logging.getLogger("bors.bot")
router = APIRouter()

CONFIG_KEY = "bot_config"
MEMBERSHIP_KEY = "bot_membership"
RUNS_KEY = "bot_runs"
#: عبارتِ تأییدِ اجرایِ واقعی — ازِ پاسخِ status خوانده می‌شود، پس کاربر چیزی
#: را حدس نمی‌زند و بی‌دیدنِ پیامِ صریح، قفل سوم باز نمی‌شود.
LIVE_CONFIRM_PHRASE = "اجرایِ واقعیِ سرخطی را تأیید می‌کنم"

#: پیش‌فرضِ محافظه‌کارانه؛ هیچ‌کدام «تنظیم‌شده» حساب نمی‌شود مگر کاربر بخواهد.
DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "mode": "paper",
    "preset": "trend",
    "chain": [],
    "fund_mode": "standard",
    "logic": "and",
    "sizing_fraction": 0.05,
    "max_orders": 1,
    "max_order_value": 200_000_000.0,
    "max_symbol_exposure": None,
    "max_total_exposure": None,
    "max_daily_loss": None,
    "max_stale_sessions": 1,
    "start_cash": 100_000_000.0,
    "commission_bps": 30.0,
    "slippage_bps": 10.0,
    "max_volume_share": 0.02,
}
NUMERIC_BOUNDS = {
    "sizing_fraction": (0.001, 0.25),
    "max_orders": (1, 20),
    "max_stale_sessions": (0, 10),
    "start_cash": (1_000_000.0, 1e13),
    "commission_bps": (0.0, 300.0),
    "slippage_bps": (0.0, 300.0),
    "max_volume_share": (0.001, 0.25),
}

_LOCK = threading.Lock()


# ── پیکربندی ────────────────────────────────────────────────────────────────
def _load(led) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    got = led.load_state(CONFIG_KEY) or {}
    if isinstance(got, dict):
        cfg.update({k: v for k, v in got.items() if k in DEFAULTS})
    return cfg


def _validate(body: Mapping[str, Any], current: Mapping[str, Any]) -> tuple[dict, list[str]]:
    """ادغامِ محافظه‌کارانه + ردِّ هر مقدارِ نامعتبر. هیچ مقدارِ ناشناخته‌ای
    ساکت پذیرفته نمی‌شود؛ بی‌این یکِ typo درِ UI یعنی «سقفِ تعریف‌نشده»."""
    out = dict(current)
    errs: list[str] = []
    for k, v in (body or {}).items():
        if k not in DEFAULTS:
            errs.append(f"کلیدِ ناشناخته: {k}")
            continue
        if k == "mode":
            if v not in ("paper", "live"):
                errs.append("mode فقط paper یا live")
                continue
            out["mode"] = v
        elif k in ("enabled",):
            out["enabled"] = bool(v)
        elif k == "preset":
            import funnel_registry as REG
            if str(v) not in REG.PRESET_BY_ID:
                errs.append(f"presetِ ناشناخته: {v}")
                continue
            out["preset"] = str(v)
        elif k == "chain":
            out["chain"] = [str(x) for x in (v or []) if str(x).strip()] if isinstance(v, list) else []
        elif k == "fund_mode":
            if v not in ("hard", "standard", "exception"):
                errs.append("fund_mode نامعتبر")
                continue
            out["fund_mode"] = str(v)
        elif k == "logic":
            if str(v) not in ("and", "or"):
                errs.append("logic فقط and یا or")
                continue
            out["logic"] = str(v)
        elif k in NUMERIC_BOUNDS:
            lo, hi = NUMERIC_BOUNDS[k]
            try:
                n = float(v)
            except (TypeError, ValueError):
                errs.append(f"{k} عدد نیست")
                continue
            if not (lo <= n <= hi):
                errs.append(f"{k} بیرونِ مجازِ {lo}…{hi}: {v}")
                continue
            out[k] = int(n) if k in ("max_orders", "max_stale_sessions") else n
        else:
            # سقف‌هایِ None-پذیر: None یعنی «تعریف نشده»، هر چیزِ دیگر عددِ مثبت
            if v is None:
                out[k] = None
                continue
            try:
                n = float(v)
            except (TypeError, ValueError):
                errs.append(f"{k} عدد یا null نیست")
                continue
            if n <= 0:
                errs.append(f"{k} باید مثبت باشد یا null")
                continue
            out[k] = n
    return out, errs


def _limits(cfg: Mapping[str, Any]) -> Limits:
    return Limits(max_orders=int(cfg["max_orders"]),
                  require_confirmation=False,
                  max_order_value=cfg["max_order_value"],
                  max_symbol_exposure=cfg["max_symbol_exposure"],
                  max_total_exposure=cfg["max_total_exposure"],
                  max_daily_loss=cfg["max_daily_loss"])


# ── داورِ canonical و ردیف‌هایِ بازار ────────────────────────────────────────
def _board_day() -> int | None:
    """شمارۀ نشستِ بسته‌شدۀ تابلو — همان چیزی که خودِ تابلو منتشر می‌کند.

    جدا شده تا مصرف‌کنندهٔ گارد بتواند نشستِ قطعی بدهد؛ بی‌این، آزمونِ ربات
    مجبور است کلِ `/api/market` را بسازد (۰٫۹ ثانیه و دست‌زدن به بانکِ واقعی).
    """
    from api.funnel import _board_snapshot
    return _board_snapshot()[1]


def _membership_map(payload: Any) -> dict[str, str]:
    """نگاشتِ in/out/unknown ازِ رأیِ *خودِ* قیف، نمادبه‌نماد.

    `status_matrix[symbol]["handover"]["status"]` یگانه حکمِ نهاییِ قیف است.
    دو چیزی که اینجا عمداً جدا می‌مانند:
      • `pass` ⇒ in، `reject`/`not_in_universe` ⇒ out — همان دو حکمی که دفترچه
        می‌شناسد؛
      • `pending`/`unavailable`/هر چیزِ دیگر ⇒ unknown: «سنجیده نشده» با
        «خارج است» یکی نیست و بی‌این تفکیک، یکِ نمادِ درِ صفِ اسکن می‌فروخت.
    بی‌`status_matrix` (پاسخِ کهنه/ ناقص) ⇒ نگاشتِ خالی = بی‌اقدام.
    """
    from funnel_engine import NOT_IN_UNIVERSE, PASS, REJECT
    sm = payload.get("status_matrix") if isinstance(payload, dict) else None
    if not isinstance(sm, dict) or not sm:
        return {}
    out: dict[str, str] = {}
    for sym, row in sm.items():
        st = str(((row or {}).get("handover") or {}).get("status") or "")
        if st == PASS:
            out[str(sym)] = "in"
        elif st in (REJECT, NOT_IN_UNIVERSE):
            out[str(sym)] = "out"
        else:
            out[str(sym)] = "unknown"
    return out


def _judge(cfg: Mapping[str, Any]):
    """judge(session) → {symbol: in|out|unknown} از *خروجیِ خودِ قیف*.

    بی‌تابلو/بی‌رأی ⇒ نگاشتِ خالی؛ یعنی «نمی‌دانیم»، نه «همه خارج» —
    `FunnelMembership` با unknown هیچ فروشی نمی‌سازد. داوریِ دوبارهٔ نشستِ
    گذشته ممکن نیست (`_run` بی‌`as_of`)، پس «دیروز» ازِ ردِّپا می‌آید
    (`MEMBERSHIP_KEY`) و اینجا فقط همین نشست سنجیده می‌شود.
    """
    from api.funnel import _run

    def judge(session: str) -> dict[str, str]:
        payload = _run(str(cfg["preset"]), list(cfg["chain"]), str(cfg["fund_mode"]),
                       {}, {}, drop_suffix=True, logic=str(cfg["logic"]))
        if not isinstance(payload, dict) or payload.get("status") != "success":
            return {}
        return _membership_map(payload)

    return judge


def _bars(cfg: Mapping[str, Any], session_day: int,
          symbols: set[str] | None = None) -> list[Bar]:
    """ردیفِ *همان یک نشستِ* بسته‌شدۀ نمادهایِ خواسته‌شده ازِ market.db.

    `symbols=None` ⇒ همهٔ تابلو (فقط برایِ آزمون). درِ اجرایِ واقعی همیشه
    فهرستِ کوچک «نمادهایِ اقدام‌پذیر» داده می‌شود: داوریِ ربات تنها رویِ
    بازماندگانِ قیف، موقعیت‌هایِ باز و سفارش‌هایِ درِ انتظار می‌تواند اثر
    بگذارد.feed کردنِ ۶٬۰۱۸ نماد × ۳۵ نشست (۱۲۹٬۶۱۳ ردیف ⇒ ۱٬۴۵۷ ثانیه
    سنجیده‌شده) نه تصمیمی می‌سازد نه پرشدنی — و ترتیبِ نماد-محورِ آن،
    «دیروز»ِ استراتژی را بی‌معنی می‌کرد (سنجش: ۱۵۶ صدایِ داور در ۴۰۰ ردیفِ اول).

    `allowed_min/max` عمداً None است: منبعِ آن تابلویِ زنده است نه
    daily_prices، و ساختنِ باندِ ±٪ ازِ حدس یعنی جعلِ ورودیِ اعتبارسنجی.
    """
    out: list[Bar] = []
    try:
        conn = sqlite3.connect(f"file:{bors_config.DB_PATH}?mode=ro", uri=True)
    except Exception as e:  # بانک نیست/قفل است
        log.warning("bot: market.db باز نشد: %s", e)
        return out
    try:
        q = ("SELECT i.l_val18, p.ins_code, p.d_even, p.price_first, p.price_max, "
             "p.price_min, p.p_closing, p.q_tot_tran, p.price_yesterday "
             "FROM daily_prices p JOIN instruments i ON i.ins_code = p.ins_code "
             "WHERE p.d_even = ?")
        args: list[Any] = [int(session_day)]
        if symbols is not None:
            if not symbols:
                return out
            q += " AND i.l_val18 IN (%s)" % ",".join("?" * len(symbols))
            args += sorted(symbols)
        for sym, code, d, o, hi, lo, c, vol, prev in conn.execute(q, args):
            if not sym:
                continue
            out.append(Bar(symbol=str(sym), date=str(d),
                           open=None if o is None else float(o),
                           high=None if hi is None else float(hi),
                           low=None if lo is None else float(lo),
                           close=None if c is None else float(c),
                           volume=None if vol is None else float(vol),
                           prev_close=None if prev is None else float(prev)))
    except Exception as e:
        log.warning("bot: ردیف‌ها ساخته نشد: %s", e)
    finally:
        conn.close()
    out.sort(key=lambda b: b.symbol)
    return out


def _session(cfg: Mapping[str, Any], led,
             day: int | None = None) -> tuple[PaperSession, int | None]:
    day = _board_day() if day is None else day
    strat = FunnelMembership(_judge(cfg))
    acc = SimAccount(start_cash=float(cfg["start_cash"]))
    costs = CostModel(commission_bps=float(cfg["commission_bps"]),
                      slippage_bps=float(cfg["slippage_bps"]),
                      max_volume_share=float(cfg["max_volume_share"]))
    s = PaperSession(strategy=strat, ledger=led, account=acc, costs=costs,
                     limits=_limits(cfg), sizing_fraction=float(cfg["sizing_fraction"]),
                     max_stale_sessions=int(cfg["max_stale_sessions"]),
                     fail_closed=True)
    s.recover()
    return s, day


def _step(cfg: Mapping[str, Any], led, day: int) -> dict[str, Any] | None:
    """یکِ فشارِ دکمه = یکِ نشست: داوری یک‌بار، ردیف فقط برایِ نمادهایِ اقدام‌پذیر.

    «دیروز» ازِ ردِّپا خوانده می‌شود (`MEMBERSHIP_KEY`)، نه با داوریِ دوبارهٔ
    گذشته: `api/funnel._run` بی‌`as_of` است و فقط تابلویِ جاری را می‌سنجد، پس
    رأیِ یکِ نشستِ پیشین بازسازی‌شدنی نیست و جاگذاریِ آن درِ گذشته نشتِ آینده
    بود. سیگنالِ همین نشست رویِ همین نشست پر **نمی‌شود**؛ پرشدنش به نشستِ
    بعد (یا انقضایش با همان سقفِ کهنگی) می‌ماند — همان T+1ِ دفترچه.
    """
    day = int(day)
    cur = _judge(cfg)(str(day)) or {}
    if not cur:
        return None
    prev_state = led.load_state(MEMBERSHIP_KEY) or {}
    prev_session = prev_state.get("session")
    prev_map = prev_state.get("map") or {}
    sess, _ = _session(cfg, led, day)
    sess.strategy.seed(str(prev_session) if prev_session else None, prev_map,
                       str(day), cur)
    want = {s for s, v in cur.items() if v == "in"}
    want |= {str(s) for s in sess.account.positions}
    want |= sess.pending_symbols()
    bars = _bars(cfg, day, symbols=want) if want else []
    if want and not bars:
        return None
    started = time.time()
    decisions = [sess.on_bar(b) for b in bars]
    seen = {b.symbol for b in bars}
    expired: list[str] = []
    for eid, d in list(getattr(sess, "_pending", {}).items()):
        if str(d.price_as_of or "") == str(day):
            continue
        sym = str(d.instrument.symbol)
        if sym in seen or not sess.stale(sym, str(day)):
            continue
        led.record(execution_id=eid, kind="risk_reject", status="expired", symbol=sym,
                   detail="ردیفِ تازه‌تر تا نشست %s نرسید ⇒ سفارشِ درِ انتظار بسته شد" % day)
        sess._pending.pop(eid, None)
        expired.append(sym)
    led.save_state(MEMBERSHIP_KEY, {"session": str(day), "map": cur,
                                    "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    sess.persist()
    summary = [{
        "date": d.date, "signals": d.signals, "dispatched": d.dispatched,
        "rejected": d.rejected, "equity": d.equity, "halt_state": d.halt_state,
        "notes": list(d.notes)[:8],
    } for d in decisions if (d.signals or d.dispatched or d.rejected or d.notes)]
    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "session": str(day),
        "bars": len(bars), "symbols": len(seen),
        "symbols_in": sum(1 for v in cur.values() if v == "in"),
        "unpriced": sorted({s for s, v in cur.items() if v == "in"} - seen)[:40],
        "acting": sorted(want)[:40], "expired": expired,
        "prev_session": prev_session or None,
        "note": None if want else "بی‌اقدام: نه بازمانده‌ای درِ قیف بود، نه موقعیتِ باز، نه سفارشِ درِ انتظار",
        "mode": str(cfg.get("mode")), "decisions": summary[-40:],
        "ms": int((time.time() - started) * 1000),
    }


# ── وضعیتِ اجرایِ واقعی ─────────────────────────────────────────────────────
def _live_gates() -> dict[str, Any]:
    """سه قفل از زبانِ خودِ ماژول‌ها، نه از حدسِ این فایل.

    `capabilities()` یک `Capabilities` (دیتاکلس) برمی‌گرداند، نه فهرست — اولین
    نسخهٔ همین تابع آن را `list()` می‌کرد و با `TypeError` بی‌صدا به `live_capable
    = False` می‌افتاد؛ یعنی دروازهٔ اجرایِ واقعی حتی با آداپتورِ آماده هم هرگز
    باز نمی‌شد. حالا فیلدها خوانده می‌شوند و «قابلِ اجرا» یعنی صریحاً:
    place + order_state + list_orders (بدونِ ردیابیِ وضعیت، ربات درِ نتیجهٔ
    مبهم کور است و نباید سفارشِ واقعی بدهد).
    """
    g: dict[str, Any] = {"env_live": False, "adapter": "mock", "session": "none",
                         "capabilities": {}, "live_capable": False, "dry_run": True}
    try:
        import dataclasses

        import api.execution as EX
        g["env_live"] = bool(getattr(EX, "LIVE_REQUESTED", False))
        g["adapter"] = str(getattr(EX, "ADAPTER_KIND", "mock"))
        g["dry_run"] = bool(getattr(EX, "DRY_RUN", True))
        br = EX._ACTIVE_ADAPTER
        caps = br.capabilities()
        d = dataclasses.asdict(caps) if dataclasses.is_dataclass(caps) else {}
        g["capabilities"] = {k: bool(v) for k, v in d.items()}
        g["live_capable"] = bool(d.get("place") and d.get("order_state") and d.get("list_orders"))
        st = br.session_status()
        g["session"] = getattr(getattr(st, "state", None), "value", str(getattr(st, "state", "none")))
    except Exception as e:
        g["error"] = "%s: %s" % (type(e).__name__, str(e)[:120])
    g["all_open"] = bool(g["env_live"] and g["live_capable"] and g["session"] == "connected")
    #: و اما نکتهٔ اصلی: سه قفلِ بالا فقط می‌گویند «اتصالِ واقعی وجود دارد».
    #: این ربات هیچ‌وقت ازِ آن استفاده نمی‌کند — `PaperSession` درِ سازندۀ خودش
    #: `PaperBroker` می‌سازد و هیچ راهی برایِ تزریقِ آداپتورِ کارگزاری ندارد. پس
    #: `mode=live` درِ این دروازه **ساختنی نیست**، و نگه‌داشتنِ برچسبِ «واقعی» برایِ
    #: کاربری که فکر می‌کند سفارشِ واقعی می‌رود، خطرناک‌تر از نبودِ قابلیت است.
    g["live_wired"] = False
    g["broker_wired"] = "paper_only"
    g["live_wired_reason"] = ("ربات کاغذی است: `PaperSession` فقط `PaperBroker` "
                              "می‌سازد و آداپتورِ کارگزاری به آن تزریق نمی‌شود")
    return g


# ── مسیرها ──────────────────────────────────────────────────────────────────
@router.get("/api/bot/status")
def get_status():
    led = default_ledger()
    cfg = _load(led)
    last = (led.load_state(RUNS_KEY) or {}).get("runs") or []
    acct = led.load_state(STATE_KEY) or {}
    return {
        "status": "ok",
        "config": cfg,
        "kill": led.kill_state(),
        "halted": led.halted(),
        "live_gates": _live_gates(),
        "confirm_phrase": LIVE_CONFIRM_PHRASE,
        "account": {"equity": acct.get("equity"), "cash": acct.get("cash"),
                    "positions": len(acct.get("positions") or {}),
                    "realized_total": acct.get("realized_total")},
        "last_runs": last[-5:],
        #: دفترِ سیگنال‌هایی که پر نشده‌اند (T+1) و نشستِ رأیِ ذخیره‌شده
        "pending_drafts": len(((led.load_state("paper_pending") or {}).get("drafts") or [])),
        "verdict_session": (led.load_state(MEMBERSHIP_KEY) or {}).get("session"),
        "auto_run": False,
        "note": ("ربات کاغذی است و همیشه کاغذی اجرا می‌شود: آداپتورِ کارگزاری به "
                 "این دروازه تزریق نمی‌شود، پس «واقعی» اینجا وجود ندارد. مسیرِ "
                 "ارسالِ واقعی، کنترل‌کنندۀ مرکزیِ سرخطی است."),
    }


@router.get("/api/bot/config")
def get_config():
    return {"status": "ok", "config": _load(default_ledger()), "defaults": DEFAULTS,
            "bounds": {k: list(v) for k, v in NUMERIC_BOUNDS.items()}}


@router.put("/api/bot/config")
async def put_config(request: Request):
    try:
        body = json.loads((await request.body()).decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return {"status": "error", "message": "بدنِ درخواست JSON نیست"}
    if not isinstance(body, dict):
        return {"status": "error", "message": "بدنِ درخواست شیء نیست"}
    led = default_ledger()
    with _LOCK:
        cur = _load(led)
        merged, errs = _validate(body, cur)
        if errs:
            return {"status": "error", "message": "پیکربندی رد شد", "errors": errs}
        if merged.get("mode") == "live":
            g = _live_gates()
            # «واقعی» را حتی باِ قفل‌هایِ باز هم نمی‌پذیریم: این ربات آداپتورِ
            # کارگزاری ندارد، پس تنها وضعیتِ صادق که می‌توان ذخیره کرد paper است.
            # (بازماندهٔ پیکربندیِ قدیمیِ live درِ /run هم رد می‌شود.)
            merged["mode"] = "paper"
            merged["note"] = ("mode=live ذخیره نشد — ربات کاغذی است "
                              "(broker_wired=%s)؛ اجرایِ واقعی فقط ازِ دروازۀ "
                              "کنترل‌کنندۀ مرکزیِ سرخطی" % g.get("broker_wired"))
        led.save_state(CONFIG_KEY, merged)
    return {"status": "ok", "config": merged,
            "errors": [], "changed": {k: v for k, v in merged.items() if cur.get(k) != v}}


@router.post("/api/bot/run")
async def run_once(request: Request):
    """یکِ نشست: ردیف‌هایِ آخرینِ روزِ بسته‌شده ← داورِ قیف ← پرشدنِ شبیه‌سازی‌شده.

    بی‌تابلو/بی‌بانک ⇒ `no_data` و صفر اقدام، نه صفرِ جعلی.
    """
    try:
        body = json.loads((await request.body()).decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        body = {}
    led = default_ledger()
    cfg = _load(led)
    if not cfg.get("enabled"):
        return {"status": "refused", "message": "ربات خاموش است (enabled=false)"}
    if led.halted():
        return {"status": "halted", "message": "قفلِ توقف فعال است: %s" % led.kill_reason(),
                "kill": led.kill_state()}
    if str(cfg.get("mode")) == "live":
        g = _live_gates()
        # حتی باِ قفل‌هایِ باز هم رد می‌شود: «واقعی» درِ این دروازه پیاده نیست، و
        # اجرایِ کاغذی زیرِ برچسبِ «واقعی» ازِ بی‌عملی بدتر است (کاربر فکر می‌کند
        # سفارشِ واقعی رفته). مسیرِ اجرایِ واقعی، کنترل‌کنندۀ مرکزیِ سرخطی است.
        return {"status": "refused", "code": "BOT_LIVE_NOT_WIRED",
                "message": "mode=live درِ ربات پیاده نیست — ربات همیشه کاغذی اجرا "
                           "می‌کند؛ برایِ ارسالِ واقعی ازِ کنترل‌کنندۀ مرکزیِ سرخطی "
                           "استفاده کنید",
                "live_gates": g}
    with _LOCK:
        try:
            day = _board_day()
            if not day:
                return {"status": "no_data", "message": "نشستِ تابلو در دسترس نیست — بی‌اقدام"}
            run = _step(cfg, led, int(day))
        except Exception as e:
            log.exception("bot: نشست ساخته نشد")
            return {"status": "error",
                    "message": "دادهٔ بازار خوانده نشد: %s" % type(e).__name__,
                    "detail": str(e)[:180]}
        if run is None:
            return {"status": "no_data",
                    "message": "رأیِ قیف یا ردیفِ این نشست نرسید — بی‌اقدام، نه صفرِ جعلی"}
        prev = led.load_state(RUNS_KEY) or {}
        runs = list(prev.get("runs") or [])[-19:] + [run]
        led.save_state(RUNS_KEY, {"runs": runs})
        led.record(execution_id="bot", kind="bot_run", symbol="-",
                   status="ok", detail="نشست %s · %d ردیف · %d تصمیم · %d منقضی"
                   % (run["session"], run["bars"], len(run.get("decisions") or []),
                      len(run.get("expired") or [])))
    return {"status": "ok", "run": run, "kill": led.kill_state()}


@router.get("/api/bot/history")
def get_history(limit: int = 60):
    led = default_ledger()
    n = max(1, min(int(limit or 60), 500))
    return {"status": "ok", "runs": ((led.load_state(RUNS_KEY) or {}).get("runs") or [])[-n:],
            "events": led.events(kinds=("bot_run", "order", "risk_reject", "dispatch",
                                        "ack", "reconcile", "kill", "halt"))[-n:],
            "account": led.load_state(STATE_KEY) or {}}


@router.post("/api/bot/halt")
async def halt(request: Request):
    try:
        body = json.loads((await request.body()).decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        body = {}
    led = default_ledger()
    led.set_kill(HALT, str(body.get("reason") or "توقفِ دستی از پنل ربات"), actor="bot-panel")
    return {"status": "ok", "kill": led.kill_state(), "reason": led.kill_reason()}


@router.post("/api/bot/resume")
async def resume(request: Request):
    led = default_ledger()
    st = led.kill_state()
    if st == TRIPPED:
        return {"status": "refused",
                "message": "قفلِ خودکار (TRIPPED) بی‌اقدامِ صریحِ ریسک باز نمی‌شود",
                "kill": st}
    led.set_kill(ARMED, "ادامه از پنل ربات", actor="bot-panel")
    return {"status": "ok", "kill": led.kill_state()}


@router.post("/api/bot/account/reset")
async def reset_account(request: Request):
    """فقط حسابِ کاغذی. دفترِ ردِّپا پاک نمی‌شود (تاریخچه باید بماند)."""
    led = default_ledger()
    led.save_state(STATE_KEY, {"reset_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    return {"status": "ok", "message": "حسابِ کاغذی از نو ساخته می‌شود",
            "ledger_kept": True}
