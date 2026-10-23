"""api/execution_autoclicker.py — درِ AutoClicker واقعیِ Round 22.

سه چیز را یک‌جا وصل می‌کند: موتورِ اقدامِ مرورگری (`execution_autoclick_*`)،
پنلِ تب‌شده در همان پنجرهٔ EasyTrader (`execution_panel`)، و ladder وضعیتِ که
بند ۳ مأموریت می‌خواهد: ده واقعیتِ صریح با شاهد، و `UNKNOWN` با علت.

قفل‌هایِ این در:
  • هیچ مسیری خودش قضاوتِ تازه نمی‌سازد؛ فقط از `execution_ui_state.judge`،
    `execution_trading_rules.run_preflight` و `execution_rate_limiter` می‌خواند.
  • اجرایِ زنده بی‌`confirm-live` با عبارتِ صریح ممکن نیست؛ dry-run پیش‌فرض است.
  • شمارنده‌ها درِ SQLiteِ ماندگارِ مستقل است، نه درِ frontend؛ بسته‌شدنِ پنل
    شمارش را پاک نمی‌کند.
  • هیچ token/کوکی/مقدارِ فرمِ حساس در پاسخ یا لاگ نمی‌نشیند؛ نشانهٔ پنل فقط
    «هست/درست/نامعتبر» است.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import os
import threading
import time
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Query, Request

import bors_config
import execution_autoclick_executor as AEX
import execution_autoclick_run as AR
import execution_autoclick_scheduler as ASCH
import execution_browser as EB
import execution_browser_host as BH
import execution_panel as PANEL
import execution_rate_limiter as RL
import execution_schedule as SCH
import execution_strategy_core as SC
import execution_trading_rules as TR
import execution_ui_state as UIS

router = APIRouter()

#: وضعیت‌هایِ ladder؛ ترتیبِ نمایشِ همان ترتیبِ بند ۳ مأموریت است.
FACT_ORDER = ("browser_open", "page_loaded", "login_verified", "panel_connected",
              "form_usable", "symbol_side_detected", "price_quantity_match",
              "submit_button_ready", "constraints_checked", "schedule_state")
FACT_LABELS = {
    "browser_open": "مرورگر اختصاصی باز است",
    "page_loaded": "صفحهٔ EasyTrader بارگذاری شده",
    "login_verified": "ورود کاربر از شاهدِ قابلِ مشاهده تأیید شده",
    "panel_connected": "پنل کنترل به همان نشست مرورگر متصل است",
    "form_usable": "فرم سفارش باز و قابل استفاده است",
    "symbol_side_detected": "نماد و سمت سفارش تشخیص داده شده",
    "price_quantity_match": "قیمت و تعداد با تنظیم منطبق است",
    "submit_button_ready": "دکمهٔ ثبت یکتا، نمایان و فعال است",
    "constraints_checked": "محدودیت‌های زمانی/تعدادی/بازار بررسی شده",
    "schedule_state": "وضعیت اجرای زمان‌بندی‌شده",
}
PANEL_FRESH_S = 20.0
DEFAULT_MAX_DATA_AGE_S = 300.0

#: RLock، نه Lock: runner() قفل را می‌گیرد و داخلش store()/executor() همان
#: قفل را دوباره می‌خواهند؛ با Lockِ ساده اولین درخواست /state می‌خوابید.
_LOCK = threading.RLock()
_DRIVER_LOCK = threading.Lock()
_STORE: AR.AutoClickRunStore | None = None
_LIMITER: RL.OrderRateLimiter | None = None
_RUNNER: ASCH.AutoClickRunRunner | None = None
_EXECUTOR: AEX.AutoClickExecutor | None = None
_DRIVER: Any = None
_TICKETS = PANEL.PanelTicketStore()
_PANEL_SEEN: dict[str, float] = {}
_LAST_UI: dict[str, Any] = {}
_LAST_PREFLIGHT: dict[str, Any] = {}


# ── زیرساخت ----
def ex() -> Any:
    """api.execution دیر import می‌شود؛ هنگام import این ماژول بسته نیمه است."""
    from api import execution as _ex
    return _ex


def store() -> AR.AutoClickRunStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = AR.AutoClickRunStore(
                os.path.join(str(bors_config.WORK_DIR), "execution_autoclick.db"))
            _STORE.recover()
        return _STORE


def limiter() -> RL.OrderRateLimiter:
    global _LIMITER
    with _LOCK:
        if _LIMITER is None:
            _LIMITER = RL.OrderRateLimiter()
        return _LIMITER


def strategy_settings() -> SC.StrategySettings:
    """تنظیماتِ جاریِ استراتژیِ AutoClicker (selectorها از همین‌جا قابلِ تغییرند)."""
    base = SC.default_settings(SC.AUTOCLICKER)
    try:
        loaded = SC.StrategySettingsStore().load().get(SC.AUTOCLICKER)
    except Exception:                             # noqa: BLE001
        loaded = None
    if loaded is None:
        return base
    opts = dict(base.options)
    opts.update(dict(loaded.options or {}))
    return SC.StrategySettings(strategy_id=SC.AUTOCLICKER, enabled=loaded.enabled,
                               mode=loaded.mode, dry_run=loaded.dry_run,
                               priority=loaded.priority, options=opts)


def ui_options(cfg: AR.RunConfig) -> UIS.UIOptions:
    o = dict(strategy_settings().options or {})
    o.update(dict(cfg.ui or {}))
    ui = cfg.ui_options()
    for key in ("submit_selector", "price_selector", "quantity_selector",
                "symbol_selector", "isin_selector", "side_selector",
                "form_scope_selector"):
        val = str(o.get(key) or "")
        if key == "submit_selector" and ui.side == "sell" and not val:
            val = str(o.get("submit_selector_sell") or "")
        if key == "submit_selector" and ui.side == "buy" and not val:
            val = str(o.get("submit_selector_buy") or "")
        if val:
            setattr(ui, key, val)
    if not ui.symbol_selector:
        ui.symbol_selector = str(o.get("form_symbol_selector") or "")
    ui.expected_symbol = cfg.symbol or ui.expected_symbol
    ui.expected_isin = cfg.isin or ui.expected_isin
    ui.expected_price = cfg.expected_price
    ui.expected_quantity = cfg.expected_quantity
    ui.side = cfg.side
    return ui


def driver_for(host: Mapping[str, Any]) -> tuple[Any, str]:
    """درایورِ متصل به همان پنجرهٔ مالک؛ اگر ناسالم شد دوباره ساخته می‌شود."""
    global _DRIVER
    cdp = str(host.get("cdp_url") or "")
    if not cdp or not host.get("healthy"):
        return None, "host_not_healthy"
    with _DRIVER_LOCK:
        if (_DRIVER is not None and getattr(_DRIVER, "cdp_url", "") == cdp
                and getattr(_DRIVER, "is_alive", lambda: False)()):
            return _DRIVER, ""
        try:
            st = strategy_settings()
            opts = dict(st.options or {})
            opts["cdp_url"] = cdp
            opts["keep_driver_alive"] = True
            opts["order_url"] = str(opts.get("order_url") or BH.DEFAULT_URL)
            made = EB.PlaywrightBrowserDriver(dataclasses.replace(st, options=opts),
                                             strategy_id="autoclicker-panel")
            made.start()
        except Exception as e:                    # noqa: BLE001
            return None, "driver_failed:%s" % type(e).__name__
        stale = _DRIVER
        _DRIVER = made
    if stale is not None:
        try:
            stale.close()
        except Exception:                         # noqa: BLE001
            pass
    return made, ""


def ctx_provider(run_getter) -> Any:
    def build() -> AEX.ExecutorContext:
        run = run_getter()
        cfg = run.config if run is not None else AR.RunConfig()
        host = BH.read_status(check=True)
        drv, why = driver_for(host)
        st = strategy_settings()
        o = dict(st.options or {})
        return AEX.ExecutorContext(
            driver=drv, ui=ui_options(cfg), dry_run=bool(cfg.dry_run),
            order_paths=tuple(o.get("order_paths") or ("/core/api/v2/order",)),
            order_method=str(o.get("order_method") or "POST"),
            intercept_pattern=str(o.get("intercept_pattern") or "**/core/api/v2/order*"),
            allowed_hosts=tuple(o.get("origin_allowlist") or
                                ("d.easytrader.ir",)),
            request_timeout_ms=int(o.get("action_timeout_ms") or 1200),
            response_timeout_ms=int(o.get("response_timeout_ms") or 4000),
            clock_probe=lambda: ex().autoclicker_clock(),
            session_ok=lambda: panel_session_ok(host))
    return build


def allowed_hosts() -> tuple[str, ...]:
    o = dict(strategy_settings().options or {})
    allow = o.get("origin_allowlist") or ["https://d.easytrader.ir"]
    if isinstance(allow, str):
        allow = [allow]
    out = []
    for a in allow:
        host = urlparse(str(a)).hostname or str(a)
        if host:
            out.append(host.lower())
    return tuple(out) or PANEL.EASYTRADER_HOSTS


def panel_session_ok(host: Mapping[str, Any]) -> tuple[bool, str]:
    """ورود از شواهدِ قابلِ مشاهده: کلیدِ OIDC در همان host، نه حدس."""
    got = PANEL.session_presence(str(host.get("cdp_url") or ""),
                                 broker_hosts=allowed_hosts())
    state = str(got.get("state") or "UNKNOWN")
    if state == "LOGGED_IN":
        return True, "ok"
    return False, "%s|%s" % (state, got.get("code") or got.get("evidence") or "")


def executor() -> AEX.AutoClickExecutor:
    global _EXECUTOR
    with _LOCK:
        if _EXECUTOR is None:
            _EXECUTOR = AEX.AutoClickExecutor(ctx_provider(active_run))
        return _EXECUTOR


def runner() -> ASCH.AutoClickRunRunner:
    global _RUNNER
    with _LOCK:
        if _RUNNER is None:
            _RUNNER = ASCH.AutoClickRunRunner(
                store(), executor=executor(), limiter=limiter(),
                warm=lambda run: executor().run_warm(),
                halt_check=lambda: (bool(ex().autoclicker_halted()), "توقفِ اضطراریِ ثبت‌شده"),
                spin_ms=12.0)
        return _RUNNER


def active_run(run_id: str = "") -> Optional[AR.RunRecord]:
    st = store()
    rid = str(run_id or _SELECTED.get("run_id") or "")
    if rid:
        try:
            return st.get(rid)
        except AR.RunError:
            pass
    return st.active_run()


_SELECTED = {"run_id": ""}


# ── ladderِ وضعیت ----
def _fact(status: str, detail: str = "", source: str = "") -> dict[str, str]:
    return {"status": status, "detail": str(detail or "")[:240],
            "source": str(source or "")[:160]}


def build_facts(run: Optional[AR.RunRecord], *, host: Mapping[str, Any],
                tabs: Mapping[str, Any], session: Mapping[str, Any],
                ui: Mapping[str, Any], preflight: Mapping[str, Any],
                ticket_ok: bool) -> dict[str, dict[str, str]]:
    facts: dict[str, dict[str, str]] = {}
    facts["browser_open"] = _fact(
        "PASS" if host.get("healthy") else "FAIL",
        "پنجرهٔ host باز و CDP محلی پاسخ می‌دهد" if host.get("healthy")
        else "host باز نیست یا CDP پاسخ نمی‌دهد",
        "execution_browser_host.read_status")
    broker_tabs = [t for t in (tabs.get("tabs") or []) if t.get("is_broker")]
    facts["page_loaded"] = _fact(
        "PASS" if broker_tabs else ("FAIL" if host.get("healthy") else "UNKNOWN"),
        "%d تب روی میزبان کارگزاری" % len(broker_tabs) if broker_tabs
        else "تبِ EasyTrader در این پنجره نیست",
        "execution_panel.list_tabs")
    st_login = str(session.get("state") or "UNKNOWN")
    facts["login_verified"] = _fact(
        "PASS" if st_login == "LOGGED_IN" else ("FAIL" if st_login == "LOGIN_REQUIRED"
                                               else "UNKNOWN"),
        str(session.get("evidence") or session.get("code") or "")
        or ("host باز نیست؛ شاهدی از مرورگر دیده نمی‌شود"
            if not host.get("healthy") else "هیچ شاهدی از نشست دیده نشد"),
        "sessionStorage key presence + absence of a visible password field "
        "(مقدارِ نشست هرگز خوانده نمی‌شود)")
    panel_tabs = [t for t in (tabs.get("tabs") or []) if t.get("is_panel")]
    fresh = time.time() - float(_PANEL_SEEN.get("at") or 0.0) < PANEL_FRESH_S
    facts["panel_connected"] = _fact(
        "PASS" if (panel_tabs and ticket_ok and fresh) else "UNKNOWN",
        ("تبِ پنل باز است و با نشانهٔ درست به این بک‌اند می‌نویسد (%.0fs پیش)" % fresh
         if (panel_tabs and ticket_ok and fresh) else
         "تبِ پنل=%s نشانهٔ درست=%s تازه=%s" % (bool(panel_tabs), ticket_ok, fresh)),
        "execution_panel ticket bound to the host context")
    jud = dict(ui.get("resolution") or {})
    checks = dict(jud.get("checks") or {})
    form_ok = (checks.get("form_fields_present") == "PASS"
               and checks.get("form_fields_visible") == "PASS"
               and checks.get("form_fields_unique") == "PASS")
    facts["form_usable"] = _fact(
        "PASS" if form_ok else ("UNKNOWN" if not jud else "FAIL"),
        str(jud.get("reason") or "فرم خوانده نشده"), "execution_ui_state.judge")
    sym_side = (checks.get("symbol_verified") == "PASS"
                and checks.get("side_verified") == "PASS")
    facts["symbol_side_detected"] = _fact(
        "PASS" if sym_side else ("UNKNOWN" if not jud else "FAIL"),
        "نمادِ فرم: %s" % (jud.get("evidence", {}) or {}).get("form_symbol_text", "—")
        if jud else "فرمی خوانده نشده", "execution_ui_state.judge")
    pq = (checks.get("price_matches_expected") == "PASS"
          and checks.get("quantity_matches_expected") == "PASS")
    facts["price_quantity_match"] = _fact(
        "PASS" if pq else ("UNKNOWN" if not jud else "FAIL"),
        "خوانده‌شده از فرم: price=%s qty=%s" % (
            (jud.get("evidence") or {}).get("form_price"),
            (jud.get("evidence") or {}).get("form_quantity")) if jud else "—",
        "فقط‌خواندنی؛ برنامه مقداری نمی‌نویسد")
    btn = jud.get("button") or {}
    facts["submit_button_ready"] = _fact(
        "PASS" if jud.get("verdict") == "UNIQUE" and btn.get("visible") and
        btn.get("enabled") else ("UNKNOWN" if not jud else "FAIL"),
        "verdict=%s usable=%s hidden=%s opposite=%s" % (
            jud.get("verdict"), checks.get("submit_usable"),
            checks.get("submit_hidden_same_name"), checks.get("submit_opposite_visible"))
        if jud else "—", "یک‌تا، نمایان، فعال، داخل viewport، همان فرم")
    okpf = bool(preflight.get("ok_for_arm"))
    blockers = preflight.get("blockers") or []
    unknowns = preflight.get("unknowns") or []
    if not preflight:
        facts["constraints_checked"] = _fact(
            "UNKNOWN", "پیش‌نگاشتی اجرا نشده؛ «ذخیره و پیش‌نمایش» یا «بررسی آمادگی» "
                       "را بزنید", "execution_trading_rules.run_preflight")
    else:
        parts = []
        if blockers:
            parts.append("%d مسدودساز" % len(blockers))
        if unknowns:
            parts.append("%d خانة بدون داده" % len(unknowns))
        facts["constraints_checked"] = _fact(
            "PASS" if okpf and not unknowns else ("WARN" if okpf else
                                                 ("FAIL" if blockers else "UNKNOWN")),
            " | ".join(parts) or "همه چک‌ها با دادهٔ تازه",
            "execution_trading_rules.run_preflight")
    if run is None:
        facts["schedule_state"] = _fact("UNKNOWN", "اجرای ساخته‌شده‌ای انتخاب نشده",
                                        "execution_autoclick_run store")
    else:
        running = run.state in (AR.ARMED, AR.WARMING, AR.RUNNING)
        facts["schedule_state"] = _fact(
            "PASS" if run.state == AR.COMPLETED else
            ("WARN" if running else ("FAIL" if run.state in
                                    (AR.BLOCKED, AR.NEEDS_REVIEW, AR.MISSED_TARGET,
                                     AR.EXPIRED) else "UNKNOWN")),
            "%s | انجام %d/%d | مانده %d | بعدی %s" % (
                run.state, run.fired_actions, run.config.total_actions,
                max(0, run.config.total_actions - run.fired_actions),
                AR.format_tehran(max([a.planned_at_ms for a in run.actions
                                      if a.state in (AR.A_PENDING, AR.A_CLAIMED)] or [0]))
                if any(a.state in (AR.A_PENDING, AR.A_CLAIMED) for a in run.actions)
                else "—"),
            "store پایدار، نه شمارندهٔ frontend")
    return facts


def read_form_once(cfg: AR.RunConfig) -> dict[str, Any]:
    """یک خوانشِ فقط‌خواندنیِ فرم و داوری؛ بی‌کلیک و بی‌نگاشتِ مسیر."""
    host = BH.read_status(check=True)
    drv, why = driver_for(host)
    if drv is None:
        return {"ok": False, "reason": why, "resolution": {}}
    ui = ui_options(cfg)
    try:
        state = UIS.read_ui_state(drv, ui)
    except Exception as e:                        # noqa: BLE001
        return {"ok": False, "reason": "dom_read_failed:%s" % type(e).__name__,
                "resolution": {}}
    res = UIS.judge(state, ui)
    out = res.public()
    out["url"] = str(getattr(drv, "url", lambda: "")() or "")[:120]
    return {"ok": bool(res.ok), "reason": res.reason, "resolution": out}


def preflight_for(cfg: AR.RunConfig, *, now_ms: Optional[int] = None,
                  acknowledge: bool = False) -> dict[str, Any]:
    facts = local_facts(cfg)
    rep = TR.run_preflight(symbol=cfg.symbol, isin=cfg.isin, side=cfg.side,
                           price=cfg.expected_price, quantity=cfg.expected_quantity,
                           total_actions=cfg.total_actions,
                           interval_ms=(cfg.interval_ms if cfg.mode == "repeat" else None),
                           target_at_ms=cfg.planned_first_at_ms(), facts=facts,
                           acknowledge_preopen=acknowledge,
                           max_data_age_s=DEFAULT_MAX_DATA_AGE_S, now_ms=now_ms)
    got = rep.public()
    got["facts_source"] = facts.get("data_source") or "none"
    return got


def local_facts(cfg: AR.RunConfig) -> dict[str, Any]:
    """factsِ محلیِ فقط‌خواندنی؛ نبودِ هر کدام UNKNOWN است نه صفر."""
    out: dict[str, Any] = {"data_source": "none"}
    row = None
    try:
        con = ex().readonly_db()
        try:
            row = con.execute(
                "SELECT i.isin AS isin, m.p_last AS p_last, m.allowed_min AS amin, "
                "m.allowed_max AS amax, m.fetched_at AS fetched "
                "FROM instruments i JOIN market_watch m ON m.ins_code=i.ins_code "
                "WHERE i.l_val18=?", (cfg.symbol,)).fetchone()
        finally:
            try:
                con.close()
            except Exception:                     # noqa: BLE001
                pass
    except Exception:                             # noqa: BLE001
        row = None
    if row is not None:
        out["last_price"] = float(row["p_last"] or 0) or None
        out["allowed_min"] = float(row["amin"] or 0) or None
        out["allowed_max"] = float(row["amax"] or 0) or None
        out["isin"] = str(row["isin"] or "") or None
        out["data_source"] = "market.db:market_watch+instruments"
        try:
            got = dt.datetime.strptime(str(row["fetched_at"] or ""), "%Y-%m-%d %H:%M:%S")
            out["data_as_of_ms"] = int(time.mktime(got.timetuple()) * 1000)
        except ValueError:
            out["data_as_of_ms"] = None
    else:
        ident = SCH.local_identity_facts(str(bors_config.DB_PATH), cfg.symbol)
        if ident.isin:
            out["isin"] = str(ident.isin)
    try:
        day = dt.datetime.fromtimestamp(cfg.planned_first_at_ms() / 1000.0,
                                       AR.tehran_tz()[0]).date()
        status, why = SCH.LocalTradingCalendar(str(bors_config.DB_PATH)).status(day)
        out["calendar_open"] = (True if status is SCH.CalendarStatus.OPEN else
                                (False if status is SCH.CalendarStatus.CLOSED else None))
        out["calendar_detail"] = why
    except Exception:                             # noqa: BLE001
        out["calendar_open"] = None
    try:
        out["open_orders"] = ex().autoclicker_open_orders()
    except Exception:                             # noqa: BLE001
        out["open_orders"] = None
    try:
        power = ex().autoclicker_buying_power()
    except Exception:                             # noqa: BLE001
        power = None
    out["buying_power_value_rial"] = power
    if power is None or cfg.side != "buy" or not cfg.expected_price \
            or not cfg.expected_quantity:
        # فروش با «توان خرید» سنجیده نمی‌شود؛ موجودیِ قابلِ فروش منبعِ دیگری است.
        out["buying_power_ok"] = None
    else:
        out["buying_power_ok"] = float(power) >= (float(cfg.expected_price)
                                                 * float(cfg.expected_quantity))
    return out


# ── اندپوینت‌ها ----
def _ticket(request: Request) -> str:
    return PANEL.ticket_from_request(request.headers)


def _ticket_state(request: Request, host: Mapping[str, Any]) -> bool:
    value = _ticket(request)
    if not value:
        return False
    ok, _why = _TICKETS.verify(value, cdp_url=str(host.get("cdp_url") or ""))
    if ok:
        _PANEL_SEEN["at"] = time.time()
        _PANEL_SEEN["last"] = time.strftime("%H:%M:%S")
    return bool(ok)


@router.get("/api/execution/autoclicker/state")
def get_state(request: Request, run_id: str = Query(default="")) -> dict[str, Any]:
    if run_id:
        _SELECTED["run_id"] = str(run_id)
    host = BH.read_status(check=True)
    ticket_ok = _ticket_state(request, host)
    run = active_run(run_id)
    tabs = (PANEL.list_tabs(str(host.get("cdp_url") or ""),
                            broker_hosts=allowed_hosts())
            if host.get("healthy") else {"tabs": []})
    session = (PANEL.session_presence(str(host.get("cdp_url") or ""),
                                      broker_hosts=allowed_hosts())
               if host.get("healthy") else {"state": "UNKNOWN"})
    cfg = run.config if run is not None else AR.RunConfig(
        symbol=str(_LAST_UI.get("symbol") or ""), side="buy")
    ui = _LAST_UI if (run is None or not host.get("healthy")) else read_form_once(cfg)
    pf = _LAST_PREFLIGHT if (run is None or not host.get("healthy")) else preflight_for(cfg)
    facts = build_facts(run, host=host, tabs=tabs, session=session, ui=ui,
                        preflight=pf, ticket_ok=ticket_ok)
    for key, val in facts.items():
        val["label"] = FACT_LABELS.get(key, key)
    return {"status": "success", "app_version": bors_config.APP_VERSION,
            "fact_order": list(FACT_ORDER), "facts": facts,
            "run": run.public() if run else None,
            "limits": limiter().public(),
            "preflight": pf, "ui": ui,
            "panel": {"ticket_active": bool(ticket_ok),
                      "last_seen": _PANEL_SEEN.get("last"),
                      "asset": bool(PANEL.panel_asset_present()[0]),
                      "path": PANEL.PANEL_PATH},
            "tabs": tabs.get("tabs") or [],
            "session": {k: session.get(k) for k in ("state", "evidence", "code")},
            "host": {k: host.get(k) for k in ("status", "healthy", "url", "name")},
            "telemetry": executor().status(),
            "runner": {"alive": runner().alive, "last": runner().status()},
            "ceiling": {"max_actions": AR.HARD_MAX_ACTIONS,
                        "min_interval_ms": AR.MIN_INTERVAL_MS,
                        "note": "سقف‌های داخلی BorsTerminal؛ عددِ کارگزاری نیست"},
            "timezone": {"name": AR.TIMEZONE_NAME, "tz_source": AR.tehran_tz()[1],
                         "now_local": AR.format_tehran(int(time.time() * 1000))}}


@router.post("/api/execution/autoclicker/run")
def post_run(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """ساخت/جایگزینیِ اجرای زمان‌بندی‌شده از تنظیماتِ پنل. هیچ کلیکِ خودکاری ندارد."""
    try:
        cfg = AR.RunConfig(
            symbol=str(body.get("symbol") or "").strip(),
            isin=str(body.get("isin") or "").strip(),
            side=str(body.get("side") or "buy"),
            expected_price=body.get("expected_price"),
            expected_quantity=body.get("expected_quantity"),
            target_at=str(body.get("target_at") or ""),
            mode=str(body.get("mode") or "single"),
            total_actions=int(body.get("total_actions") or 1),
            interval_ms=float(body.get("interval_ms") or 0.0),
            dry_run=bool(body.get("dry_run", True)),
            prewarm_ms=int(body.get("prewarm_ms") or 1500),
            spin_ms=float(body.get("spin_ms") or AR.DEFAULT_SPIN_MS),
            ui=dict(body.get("ui") or {}),
            note=str(body.get("note") or "")[:160])
        cfg = cfg.normalized()
        if not cfg.isin:
            cfg = dataclasses.replace(cfg, isin=str(local_facts(cfg).get("isin") or ""))
        st = store()
        existing = st.active_run(cfg.account)
        if existing is not None and existing.state in (AR.ARMED, AR.WARMING, AR.RUNNING):
            return {"status": "error", "code": "ALREADY_RUNNING",
                    "detail": "اجرای فعال وجود دارد؛ اول توقف/لغو کنید",
                    "run": existing.public()}
        rec = st.create(cfg)
    except AR.RunError as e:
        return {"status": "error", "code": e.code, "detail": e.detail}
    except (TypeError, ValueError) as e:
        return {"status": "error", "code": "INVALID_CONFIG", "detail": str(e)[:200]}
    _SELECTED["run_id"] = rec.run_id
    pf = preflight_for(rec.config, acknowledge=bool(body.get("acknowledge_preopen")))
    _LAST_PREFLIGHT.clear()
    _LAST_PREFLIGHT.update(pf)
    global _EXECUTOR
    with _LOCK:
        _EXECUTOR = None                     # پیکربندی عوض شده؛ warm کهنه می‌میرد
    plan = limiter().check_plan(actions=rec.config.total_actions,
                                interval_ms=rec.config.interval_ms).public()
    return {"status": "success", "run": rec.public(), "preflight": pf,
            "plan": plan, "ui": read_form_once(rec.config)}


@router.post("/api/execution/autoclicker/check")
def post_check(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    run = active_run(str(body.get("run_id") or ""))
    if run is None:
        return {"status": "error", "code": "NO_RUN",
                "detail": "ابتدا اجرا را در پنل بسازید (ذخیره و پیش‌نمایش)"}
    global _EXECUTOR
    with _LOCK:
        _EXECUTOR = None
    ui = read_form_once(run.config)
    _LAST_UI.clear()
    _LAST_UI.update(ui)
    pf = preflight_for(run.config, acknowledge=bool(body.get("acknowledge_preopen")))
    _LAST_PREFLIGHT.clear()
    _LAST_PREFLIGHT.update(pf)
    warm = executor().run_warm()
    plan = limiter().check_plan(actions=run.config.total_actions,
                                interval_ms=run.config.interval_ms).public()
    return {"status": "success", "ui": ui, "warm": warm, "preflight": pf,
            "plan": plan, "run": store().get(run.run_id).public()}


@router.post("/api/execution/autoclicker/preflight")
def post_preflight(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    run = active_run(str(body.get("run_id") or ""))
    if run is None:
        return {"status": "error", "code": "NO_RUN", "detail": "اجرا نیست"}
    pf = preflight_for(run.config, acknowledge=bool(body.get("acknowledge_preopen")))
    _LAST_PREFLIGHT.clear()
    _LAST_PREFLIGHT.update(pf)
    return {"status": "success", "preflight": pf}


@router.post("/api/execution/autoclicker/arm")
def post_arm(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    run = active_run(str(body.get("run_id") or ""))
    if run is None:
        return {"status": "error", "code": "NO_RUN", "detail": "اجرا نیست"}
    pf = preflight_for(run.config, acknowledge=bool(body.get("acknowledge_preopen")))
    _LAST_PREFLIGHT.clear()
    _LAST_PREFLIGHT.update(pf)
    ui = read_form_once(run.config)
    _LAST_UI.clear()
    _LAST_UI.update(ui)
    plan = limiter().check_plan(actions=run.config.total_actions,
                                interval_ms=run.config.interval_ms)
    #: dry-run هیچ سفارشی به کارگزاری نمی‌فرستد، پس «بی‌داده» جلویِ اثباتِ کلیک را
    #: نمی‌گیرد. اجرایِ زنده برعکس: هر خانۀ UNKNOWN باید اول پر شده باشد.
    strict = not bool(run.config.dry_run)
    unknowns = list(pf.get("unknowns") or [])
    planpub = plan.public()
    ok = (bool(pf.get("ok_for_arm")) and bool(ui.get("ok")) and bool(planpub["fits"])
          and not (strict and unknowns))
    if strict and unknowns and not pf.get("blockers"):
        detail = "اجرایِ زنده با %d خانۀ بی‌داده مسدود است: %s" % (
            len(unknowns), "، ".join(u.split(":")[0] for u in unknowns))
    else:
        detail = ""
    gate = {"preflight": pf, "ui": ui, "plan": planpub,
            "armed_at": time.strftime("%H:%M:%S")}
    rec = store().arm(run.run_id, validation=gate, ok_for_arm=ok)
    if not ok:
        why = ([detail] if detail else []) + (pf.get("blockers") or []) + [
            ui.get("reason") or ""] + (planpub.get("reasons") or [""])
        why = [w for w in why if w]
        return {"status": "success", "armed": False, "run": rec.public(),
                "gate": gate, "strict_live": strict,
                "detail": str(why[0] if why else "پیش‌شرط‌ها کامل نیستند")[:240]}
    with _LOCK:
        runner().start()
    return {"status": "success", "armed": True, "run": rec.public(), "gate": gate}


@router.post("/api/execution/autoclicker/confirm-live")
def post_confirm(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    run = active_run(str(body.get("run_id") or ""))
    if run is None:
        return {"status": "error", "code": "NO_RUN", "detail": "اجرا نیست"}
    try:
        rec = store().set_confirmation(run.run_id, live=bool(body.get("live", True)),
                                       dry_run=bool(body.get("dry_run", False)),
                                       phrase=str(body.get("phrase") or ""))
    except AR.RunError as e:
        return {"status": "error", "code": e.code, "detail": e.detail}
    return {"status": "success", "run": rec.public(),
            "required_phrase": AR.LIVE_PHRASE, "confirmed": rec.config.live_confirmed}


@router.post("/api/execution/autoclicker/start")
def post_start(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    run = active_run(str(body.get("run_id") or ""))
    if run is None:
        return {"status": "error", "code": "NO_RUN", "detail": "اجرا نیست"}
    if run.state != AR.ARMED:
        return {"status": "error", "code": "NOT_ARMED",
                "detail": "اول «آماده‌سازی»؛ وضعیت فعلی %s" % run.state}
    if not run.config.dry_run and not run.config.live_confirmed:
        return {"status": "error", "code": "LIVE_NOT_CONFIRMED",
                "detail": "برای اجرای زنده باید عبارت «%s» وارد شود" % AR.LIVE_PHRASE}
    try:
        rec = store().start(run.run_id)
    except AR.RunError as e:
        return {"status": "error", "code": e.code, "detail": e.detail}
    with _LOCK:
        runner().start()
    return {"status": "success", "run": rec.public(),
            "runner": {"alive": runner().alive}}


@router.post("/api/execution/autoclicker/stop")
def post_stop(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    reason = str(body.get("reason") or "توقف از پنل")
    got = runner().stop(reason=reason)
    run = active_run(str(body.get("run_id") or ""))
    return {"status": "success", "stop": got,
            "run": store().get(run.run_id).public() if run else None}


@router.post("/api/execution/autoclicker/cancel")
def post_cancel(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    run = active_run(str(body.get("run_id") or ""))
    if run is None:
        return {"status": "error", "code": "NO_RUN", "detail": "اجرا نیست"}
    try:
        rec = store().cancel(run.run_id, str(body.get("reason") or "لغوِ کاربر"))
    except AR.RunError as e:
        return {"status": "error", "code": e.code, "detail": e.detail}
    return {"status": "success", "run": rec.public()}


@router.post("/api/execution/autoclicker/reset")
def post_reset(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """شروعِ دوبارۀ کنترل‌شده: ردیف‌هایِ مانده برمی‌گردند، اما هیچ کلیکی نمی‌شود."""
    run = active_run(str(body.get("run_id") or ""))
    if run is None:
        return {"status": "error", "code": "NO_RUN", "detail": "اجرا نیست"}
    try:
        rec = store().reset_for_restart(run.run_id,
                                       str(body.get("reason") or "شروع دوباره از پنل"))
    except AR.RunError as e:
        return {"status": "error", "code": e.code, "detail": e.detail}
    return {"status": "success", "run": rec.public(),
            "note": "برای ادامه باید دوباره arm و start شود"}


@router.get("/api/execution/autoclicker/runs")
def get_runs(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    return {"status": "success",
            "runs": [r.public() for r in store().list(limit=limit)]}


@router.get("/api/execution/autoclicker/run/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    try:
        rec = store().get(run_id)
    except AR.RunError as e:
        return {"status": "error", "code": e.code, "detail": e.detail}
    return {"status": "success", "run": rec.public(),
            "events": store().events(run_id, limit=120)}


@router.get("/api/execution/autoclicker/rules")
def get_rules() -> dict[str, Any]:
    return {"status": "success", "rules": TR.RULES,
            "tiers": list(TR.TIERS),
            "limits": limiter().public(),
            "unknowns": limiter().public()["unknowns"],
            "oms_codes": RL.OMS_THROTTLE_CODES}


@router.post("/api/execution/autoclicker/panel/open")
def post_panel_open(request: Request,
                    body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """پنجرهٔ host را (در صورت نیاز) باز می‌کند و تبِ پنل را در همان context می‌سازد."""
    host = BH.read_status(check=True)
    if not host.get("healthy"):
        #: پنل/تبِ کارگزاری هیچ‌گاه خودش مرورگر راه نمی‌اندازد؛ این «بازکردنِ
        #: پنجرهٔ EasyTrader» یک دکمهٔ جداست (بند ۱-۲ مأموریت) و یک پنجرهٔ
        #: ناخواسته رویِ میزِ کارِ کاربر ساختن، اثرِ جانبیِ بازگشت‌ناپذیر است.
        return {"status": "error", "code": "HOST_CLOSED",
                "detail": "اول پنجرهٔ EasyTrader را باز کنید (POST /api/execution/"
                          "browser-host)، سپس تبِ پنل",
                "host": {k: host.get(k) for k in ("status", "healthy", "url")}}
    base = str(body.get("base_url") or "").strip()
    if not base:
        u = getattr(request, "base_url", None)
        base = str(u or "http://127.0.0.1:8001").rstrip("/")
    tk = _TICKETS.mint(cdp_url=str(host.get("cdp_url") or ""),
                       host_pid=int(host.get("pid") or 0))
    url = PANEL.panel_url_for(base, tk.value)
    got = PANEL.open_panel_tab(str(host.get("cdp_url") or ""), url)
    if got.get("status") != "success":
        _TICKETS.revoke(tk.value)
        return {"status": "error", "code": got.get("code"),
                "detail": str(got.get("detail") or got.get("code") or "پنل باز نشد")[:200],
                "host": {k: host.get(k) for k in ("status", "healthy", "url")}}
    run = active_run()
    if run is not None:
        _SELECTED["run_id"] = run.run_id
    return {"status": "success", "host": {k: host.get(k) for k in
                                          ("status", "healthy", "pid", "url")},
            "opened": bool(got.get("opened")), "already_open": bool(got.get("already_open")),
            "run_id": run.run_id if run else "",
            "ticket_len": len(tk.value), "expires_in_s": int(_TICKETS.ttl_s)}


@router.post("/api/execution/autoclicker/panel/close")
def post_panel_close(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    host = BH.read_status(check=True)
    if not host.get("healthy"):
        return {"status": "error", "code": "HOST_CLOSED"}
    got = PANEL.close_panel_tab(str(host.get("cdp_url") or ""))
    n = _TICKETS.revoke_for_host(str(host.get("cdp_url") or ""))
    return {"status": "success", "closed": got.get("closed"), "revoked_tickets": n}


@router.get("/api/execution/autoclicker/browser")
def get_browser() -> dict[str, Any]:
    host = BH.read_status(check=True)
    tabs = (PANEL.list_tabs(str(host.get("cdp_url") or ""),
                            broker_hosts=allowed_hosts())
            if host.get("healthy") else {"tabs": []})
    session = (PANEL.session_presence(str(host.get("cdp_url") or ""),
                                      broker_hosts=allowed_hosts())
               if host.get("healthy") else {"state": "UNKNOWN"})
    return {"status": "success", "host": {k: host.get(k) for k in
                                          ("status", "healthy", "url", "profile", "pid")},
            "tabs": tabs.get("tabs") or [], "session": session,
            "panel_tab": any(t.get("is_panel") for t in (tabs.get("tabs") or [])),
            "asset_present": bool(PANEL.panel_asset_present()[0])}


__all__ = ["router"]
