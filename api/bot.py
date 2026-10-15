# -*- coding: utf-8 -*-
"""api/bot.py — دروازۀ ربات معاملاتی: کاغذی پیش‌فرض، واقعی فقط با سه قفل.

چرا این فایل هست: `paper_trading.py` و `bot_signals.py` از دورِ ۱۴۰۵-۰۷-۲۳
آماده بودند و ۵۴ سنجه هم می‌گذراندند، ولی **هیچ endpoint و هیچ پنلی** نداشتند؛
یعنی ربات درِ کد بود و درِ برنامه نبود. این فایل همان فاصله است: پیکربندی
اعتبارسنجی‌شده، اجرایِ یکِ نشست، وضعیت، تاریخچه، و توقف/ادامه روی همان
`execution_ledger` که دروازۀ سرخطی می‌نویسد — یک دفتر، دو مصرف‌کننده.

چه چیزی عمداً **نیست**:
• داورِ دوم: تنها منبعِ «تصمیم»، خروجیِ خودِ قیف است (`api/funnel._run` →
  `survivors`) که `bot_signals.verdicts_to_membership` آن را به in/out بدل
  می‌کند. هیچ آستانه، وزن یا امتیازی اینجا تعریف نمی‌شود.
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
from bot_signals import FunnelMembership, verdicts_to_membership
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
    "history_days": 40,
}
NUMERIC_BOUNDS = {
    "sizing_fraction": (0.001, 0.25),
    "max_orders": (1, 20),
    "max_stale_sessions": (0, 10),
    "start_cash": (1_000_000.0, 1e13),
    "commission_bps": (0.0, 300.0),
    "slippage_bps": (0.0, 300.0),
    "max_volume_share": (0.001, 0.25),
    "history_days": (5, 500),
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
            out[k] = int(n) if k in ("max_orders", "max_stale_sessions", "history_days") else n
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


def _judge(cfg: Mapping[str, Any]):
    """judge(session) → {symbol: in|out} از *خروجیِ خودِ قیف*.

    بی‌ردیف یا بی‌تابلو ⇒ نگاشتِ خالی؛ یعنی «نمی‌دانیم»، نه «همه خارج» —
    `FunnelMembership` با unknown هیچ فروشی نمی‌سازد.
    """
    from api.funnel import _run

    def judge(session: str) -> dict[str, str]:
        payload = _run(str(cfg["preset"]), list(cfg["chain"]), str(cfg["fund_mode"]),
                       {}, {}, drop_suffix=True, logic=str(cfg["logic"]))
        if not isinstance(payload, dict) or "survivors" not in payload:
            return {}
        from api.funnel import _board_rows
        board = _board_rows()
        allsyms = [str(r.get("symbol") or "") for r in board if r.get("symbol")]
        surv = [str(r.get("symbol") or "") for r in (payload.get("survivors") or [])
                if r.get("symbol")]
        if not allsyms or not surv:
            return {}
        return verdicts_to_membership(surv, allsyms)

    return judge


def _bars(cfg: Mapping[str, Any], session_day: int) -> list[Bar]:
    """ردیفِ *همان* نشستِ بسته‌شدۀ همهٔ نمادهایِ تابلو ازِ market.db.

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
        days = [r[0] for r in conn.execute(
            "SELECT DISTINCT d_even FROM daily_prices WHERE d_even<=? "
            "ORDER BY d_even DESC LIMIT ?", (int(session_day), int(cfg["history_days"])))][::-1]
        if not days:
            return out
        q = ("SELECT i.l_val18, p.ins_code, p.d_even, p.price_first, p.price_max, "
             "p.price_min, p.p_closing, p.q_tot_tran, p.price_yesterday "
             "FROM daily_prices p JOIN instruments i ON i.ins_code = p.ins_code "
             "WHERE p.d_even IN (%s)" % ",".join("?" * len(days)))
        by_sym: dict[str, list[tuple]] = {}
        for sym, code, d, o, hi, lo, c, vol, prev in conn.execute(q, days):
            if not sym:
                continue
            by_sym.setdefault(str(sym), []).append((int(d), o, hi, lo, c, vol, prev))
        for sym, rows in by_sym.items():
            rows.sort()
            for d, o, hi, lo, c, vol, prev in rows:
                out.append(Bar(symbol=sym, date=str(d),
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
    return out


def _session(cfg: Mapping[str, Any], led) -> tuple[PaperSession, int | None]:
    day = _board_day()
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
        "auto_run": False,
        "note": ("ربات تنها با POST /api/bot/run اجرا می‌شود؛ کاغذی پیش‌فرض است و "
                 "هیچ سفارشی به بازار نمی‌رود مگر سه قفلِ اجرایِ واقعی باز باشد."),
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
            if not g["all_open"] or str(body.get("confirm") or "") != LIVE_CONFIRM_PHRASE:
                merged["mode"] = "paper"
                merged["note"] = ("قفل‌های اجرایِ واقعی باز نبود ⇒ paper باقی ماند: "
                                  + json.dumps({k: g[k] for k in
                                                ("env_live", "live_capable", "session")},
                                               ensure_ascii=False))
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
        if not g["all_open"]:
            return {"status": "refused",
                    "message": "mode=live ولی قفل‌ها باز نیستند", "live_gates": g}
    with _LOCK:
        try:
            sess, day = _session(cfg, led)
            bars = _bars(cfg, int(day)) if day else []
        except Exception as e:
            log.exception("bot: نشست ساخته نشد")
            return {"status": "error",
                    "message": "دادهٔ بازار خوانده نشد: %s" % type(e).__name__,
                    "detail": str(e)[:180]}
        if not day:
            return {"status": "no_data", "message": "نشستِ تابلو در دسترس نیست — بی‌اقدام"}
        if not bars:
            return {"status": "no_data", "message": "ردیفی برایِ این نشست نیست — بی‌اقدام"}
        started = time.time()
        decisions = sess.run(bars)
        summary = [{
            "date": d.date, "signals": d.signals, "dispatched": d.dispatched,
            "rejected": d.rejected, "equity": d.equity, "halt_state": d.halt_state,
            "notes": list(d.notes)[:8],
        } for d in decisions if (d.signals or d.dispatched or d.rejected or d.notes)]
        run = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "session": str(day),
               "bars": len(bars), "symbols": len({b.symbol for b in bars}),
               "mode": str(cfg.get("mode")), "decisions": summary[-40:],
               "ms": int((time.time() - started) * 1000)}
        prev = led.load_state(RUNS_KEY) or {}
        runs = list(prev.get("runs") or [])[-19:] + [run]
        led.save_state(RUNS_KEY, {"runs": runs})
        led.record(execution_id="bot", kind="bot_run", symbol="-",
                   status="ok", detail="نشست %s · %d ردیف · %d تصمیم"
                   % (run["session"], run["bars"], len(summary)))
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
