# -*- coding: utf-8 -*-
"""execution_connection.py — تشخیصِ مرحله‌به‌مرحلهٔ اتصال، بدونِ خواندنِ راز.

ده مرحله از «Backend پاسخ می‌دهد» تا «قابلیت‌های آداپتور». هر مرحله شاهدِ
قابل‌نمایش، دلیل، اقدام بعدی و زمان دارد. برخلافِ یک «متصل/قطع» ساده:

  * بازبودنِ مرورگر فقط مرحلهٔ ۲–۴ است، نه نشست؛
  * بازبودنِ صفحهٔ UI فقط «مرورگر آماده» است، نه احراز هویت؛
  * API فقط وقتی تأیید می‌شود که پرسشِ واقعیِ read-only شاهد داشته باشد؛
  * `WIRE_HYPOTHESIS` با هیچ تغییرِ ثابتی سبز نمی‌شود.

هیچ token/cookie خوانده یا برگردانده نمی‌شود. صفحه‌ها فقط URL/titleشان از
`/json/list` محلی خوانده می‌شوند؛ هیچ input یا مقدارِ حساب خوانده نمی‌شود.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

import execution_browser_host as BH
import execution_connect as EXC
from execution_contract import redact

PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED"
UNVERIFIED = "UNVERIFIED"
NOT_RUN = "NOT_RUN"

STATE_CONNECTED = "CONNECTED"
STATE_READ_ONLY_VERIFIED = "READ_ONLY_VERIFIED"
STATE_LOGIN_REQUIRED = "LOGIN_REQUIRED"
STATE_HOST_DOWN = "HOST_DOWN"
STATE_CDP_DOWN = "CDP_DOWN"
STATE_PAGE_MISSING = "PAGE_MISSING"
STATE_API_UNVERIFIED = "BROWSER_READY_API_UNVERIFIED"
STATE_BACKEND_DOWN = "BACKEND_DOWN"

STATE_LABEL = {
    STATE_CONNECTED: "ارتباط کامل با کارگزاری تأیید شد",
    STATE_READ_ONLY_VERIFIED: "خواندن اطلاعات حساب تأیید شد؛ ارسال سفارش هنوز فعال نیست",
    STATE_LOGIN_REQUIRED: "مرورگر باز است؛ لطفاً خودتان وارد کارگزاری شوید",
    STATE_HOST_DOWN: "پنجرهٔ مرورگر کارگزاری باز نیست",
    STATE_CDP_DOWN: "ارتباط فنی با مرورگر برقرار نیست",
    STATE_PAGE_MISSING: "صفحهٔ کارگزاری در پنجرهٔ مرورگر پیدا نشد",
    STATE_API_UNVERIFIED: "مرورگر آماده است؛ هنوز دسترسی به حساب تأیید نشده است",
    STATE_BACKEND_DOWN: "برنامهٔ اصلی پاسخ نمی‌دهد",
}

STEP_TITLES = {
    "backend": "برنامهٔ اصلی",
    "host": "پنجرهٔ مرورگر",
    "cdp": "ارتباط فنی مرورگر",
    "page": "صفحهٔ کارگزاری",
    "login": "ورود شما در مرورگر",
    "session": "دسترسی به حساب",
    "contract": "ارسال سفارش",
    "read_only": "خواندن اطلاعات از کارگزاری",
    "account": "اطلاعات حساب",
    "capabilities": "امکانات اتصال",
}


def _iso(now: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if now is None else now).strftime(
        "%Y-%m-%dT%H:%M:%S")


def _host_of(url: str) -> str:
    try:
        return (urlparse(str(url or "")).hostname or "").lower()
    except ValueError:
        return ""


def cdp_pages(cdp_url: str, timeout: float = 3.0) -> tuple[list[dict[str, Any]], str]:
    """فهرستِ صفحه‌های host؛ فقط url/title/type، نه webSocketDebuggerUrl یا محتوا."""
    if not cdp_url:
        return [], "CDP URL خالی است"
    try:
        with urllib.request.urlopen(str(cdp_url).rstrip("/") + "/json/list",
                                    timeout=timeout) as r:
            raw = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:                       # noqa: BLE001
        return [], "%s: %s" % (type(e).__name__, str(e)[:120])
    if not isinstance(raw, list):
        return [], "پاسخ /json/list فهرست نیست"
    out = []
    for item in raw:
        if not isinstance(item, dict) or str(item.get("type") or "") != "page":
            continue
        out.append({"title": str(item.get("title") or "")[:200],
                    "url": str(item.get("url") or "")[:500],
                    "host": _host_of(str(item.get("url") or ""))})
    return out, ""


def _step(key: str, status: str, evidence: str, reason: str, action: str = "",
          started: float | None = None) -> dict[str, Any]:
    now = time.time()
    return {"key": key, "title": STEP_TITLES[key], "status": status,
            "evidence": evidence[:500], "reason": reason[:500], "action": action[:500],
            "observed_at": _iso(now),
            "duration_ms": None if started is None else round((time.monotonic() - started) * 1000, 1)}


def diagnose(*, app_version: str, host: Mapping[str, Any],
             execution: Mapping[str, Any], portfolio: Mapping[str, Any],
             pages_fn: Callable[[str], tuple[list[dict[str, Any]], str]] = cdp_pages,
             now: float | None = None) -> dict[str, Any]:
    t_all = time.monotonic()
    host = dict(host or {})
    execution = dict(execution or {})
    portfolio = dict(portfolio or {})
    steps: list[dict[str, Any]] = []
    login_hosts = set(EXC.login_hosts())
    ui_hosts = set(EXC.ui_hosts())

    t0 = time.monotonic()
    backend_ok = str(execution.get("status") or "") == "success"
    adapter = str(execution.get("adapter") or "?")
    steps.append(_step(
        "backend", PASS if backend_ok else FAIL,
        "app_version=%s adapter=%s traffic=%s" % (
            app_version, adapter, "allowed" if execution.get("traffic_allowed") else "blocked"),
        "برنامه پاسخ داد" if backend_ok else "وضعیت اجرا از برنامه نیامد",
        "" if backend_ok else "برنامه را اجرا/بررسی کنید", t0))

    t0 = time.monotonic()
    host_ok = bool(host.get("healthy"))
    steps.append(_step(
        "host", PASS if host_ok else FAIL,
        "healthy=%s status=%s port=%s" % (host_ok, host.get("status"),
                                           host.get("port")),
        "پنجرهٔ مرورگر آماده است" if host_ok else
        "پنجرهٔ مرورگر باز نشده یا در دسترس نیست",
        "" if host_ok else "«باز کردن پنجرهٔ اتصال» را بزنید", t0))

    t0 = time.monotonic()
    pages: list[dict[str, Any]] = []
    cdp_err = ""
    if host_ok:
        pages, cdp_err = pages_fn(str(host.get("cdp_url") or ""))
    cdp_ok = host_ok and not cdp_err
    steps.append(_step(
        "cdp", PASS if cdp_ok else (NOT_RUN if not host_ok else FAIL),
        "pages=%d%s" % (len(pages), "" if not cdp_err else " error=" + cdp_err),
        "ارتباط فنی با مرورگر پاسخ داد (%d صفحه)" % len(pages) if cdp_ok else
        (cdp_err or "بدون پنجرهٔ مرورگر، ارتباط فنی بررسی نشد"),
        "" if cdp_ok else "پنجرهٔ مرورگر را دوباره باز کنید", t0))

    allowed = login_hosts | ui_hosts
    chosen = next((p for p in pages if p.get("host") in ui_hosts), None) \
        or next((p for p in pages if p.get("host") in allowed), None) \
        or (pages[0] if pages else None)
    if not host_ok:
        page_status = NOT_RUN
    elif chosen is None:
        page_status = FAIL
    elif chosen.get("host") in allowed:
        page_status = PASS
    else:
        page_status = UNVERIFIED
    steps.append(_step(
        "page", page_status,
        "" if chosen is None else "host=%s title=%s" % (
            chosen.get("host"), chosen.get("title")),
        "صفحهٔ کارگزاری پیدا شد" if page_status == PASS else
        ("صفحه‌ای در پنجرهٔ مرورگر نیست" if chosen is None else "صفحهٔ فعلی صفحهٔ کارگزاری نیست"),
        "" if page_status == PASS else "در همان پنجره کارگزاری را باز کنید"))

    title = str((chosen or {}).get("title") or "")
    page_host = str((chosen or {}).get("host") or "")
    login_markers = ("ورود", "login", "sign in", "signin")
    if not chosen:
        login_status, login_reason, login_action = NOT_RUN, "صفحه‌ای برای بررسی نیست", ""
    elif page_host in set(EXC.auth_hosts()) or any(m in title.lower() for m in login_markers):
        login_status = BLOCKED
        login_reason = "صفحهٔ ورود کارگزاری باز است؛ هنوز وارد نشده‌اید"
        login_action = "در همان پنجره وارد کارگزاری شوید"
    elif page_host in ui_hosts:
        login_status = UNVERIFIED
        login_reason = "صفحهٔ کارگزاری باز است، اما ورود از ظاهر صفحه ثابت نمی‌شود"
        login_action = "پس از ورود، «بررسی وضعیت» را بزنید"
    else:
        login_status = UNVERIFIED
        login_reason = "این صفحه برای تشخیص ورود شناخته‌شده نیست"
        login_action = "صفحهٔ کارگزاری را در همان پنجره باز کنید"
    steps.append(_step("login", login_status,
                       "page_host=%s title=%s" % (page_host, title),
                       login_reason, login_action))

    session = execution.get("session") or {}
    session_state = str(session.get("state") or "unknown").lower()
    proven = bool(session.get("proven"))
    # `live_enabled` دروازهٔ *نوشتن* است؛ ترافیکِ فقط‌خواندنی با آن سنجیده
    # نمی‌شود. این اشتباه پس از دریافتِ نشست با read_only=true، مرحله را BLOCKED
    # نگه می‌داشت و دریافت خودکار را بی‌پایان می‌کرد.
    traffic_live = bool(execution.get("traffic_allowed"))
    token_present = session_state != "disconnected"
    if adapter == "mock":
        session_status, session_reason = BLOCKED, "این حالت آزمایشی است و به حساب واقعی وصل نیست"
        session_action = "روش اتصال را روی EasyTrader بگذارید و برنامه را دوباره باز کنید"
    elif proven and traffic_live:
        session_status, session_reason = PASS, "دسترسی به حساب با پاسخ واقعی کارگزاری تأیید شد"
        session_action = ""
    elif not traffic_live:
        session_status = BLOCKED
        session_reason = "ارتباط با کارگزاری خاموش است (نوشتن و خواندن هر دو)"
        session_action = "روش اتصال را روی EasyTrader + فقط‌خواندنی بگذارید و برنامه را دوباره باز کنید"
    elif session_state == "expired":
        session_status = BLOCKED
        session_reason = "دسترسی به حساب منقضی شده است"
        session_action = "در پنجرهٔ مرورگر دوباره وارد شوید"
    elif session_state == "auth_failed":
        session_status = BLOCKED
        session_reason = "کارگزاری اجازهٔ دسترسی نداد"
        session_action = "ورود و حساب را بررسی کنید و دوباره تلاش کنید"
    elif not token_present:
        session_status = BLOCKED
        session_reason = "هنوز دسترسی به حساب دریافت نشده است"
        session_action = "دسترسی را از مرورگر دریافت کنید (خودکار یا دستی)"
    else:
        session_status = UNVERIFIED
        session_reason = "دسترسی به حساب دریافت شد، اما هنوز امتحان نشده است"
        session_action = "«بررسی وضعیت» را بزنید"
    steps.append(_step("session", session_status,
                       "adapter=%s state=%s proven=%s traffic=%s session_present=%s" % (
                           adapter, session_state, proven, traffic_live,
                           token_present),
                       session_reason, session_action))

    contract_raw = execution.get("wire_hypothesis")
    contract_hypothesis = contract_raw is True
    contract_known = contract_raw is not None
    mock_adapter = adapter == "mock"
    contract_pass = (not mock_adapter and contract_known
                     and not contract_hypothesis)
    if mock_adapter:
        contract_reason = "این حالت آزمایشی است؛ مسیر ارسال سفارش آزموده نشده"
        contract_action = "برای آزمون قرارداد، روش اتصال را روی EasyTrader بگذارید"
    elif not contract_known:
        contract_reason = "وضعیت ارسال سفارش از سرویس نیامده"
        contract_action = "بدون شاهد واقعی، تأییدنشده می‌ماند"
    elif contract_hypothesis:
        contract_reason = "مسیر ارسال سفارش هنوز تأیید نشده است"
        contract_action = "بدون شاهد واقعی، تأییدنشده می‌ماند"
    else:
        contract_reason = "مسیر ارسال سفارش تأیید شده است"
        contract_action = ""
    steps.append(_step(
        "contract", PASS if contract_pass else UNVERIFIED,
        "wire_hypothesis=%s source=%s" % (
            contract_raw,
            (execution.get("wire_provenance") or {}).get("order_create", {}).get("kind", "?")),
        contract_reason, contract_action))

    proof = session.get("verified_by") or {}
    read_status = PASS if proven and proof.get("path") else BLOCKED
    steps.append(_step(
        "read_only", read_status,
        "path=%s status=%s kind=%s" % (
            proof.get("path"), proof.get("status"), proof.get("kind")),
        "خواندن اطلاعات از کارگزاری با شاهد ثبت شده" if read_status == PASS
        else "هنوز خواندن اطلاعات تأیید نشده است",
        "" if read_status == PASS else "پس از ورود، «بررسی وضعیت» را بزنید"))

    pf = str(portfolio.get("status") or "unknown")
    if pf == "success" and portfolio.get("rows") is not None:
        account_status, account_reason = PASS, "اطلاعات حساب خوانده شد"
    elif pf in ("no_source", "blocked", "unverified_session"):
        account_status = BLOCKED
        account_reason = "اطلاعات حساب در دسترس نیست"
    else:
        account_status, account_reason = UNVERIFIED, "وضعیت اطلاعات حساب معلوم نیست"
    steps.append(_step("account", account_status,
                       "portfolio_status=%s rows=%s" % (pf, portfolio.get("rows")),
                       account_reason,
                       "" if account_status == PASS else "اطلاعات خواندنی حساب را وصل کنید"))

    caps = execution.get("capabilities") or {}
    caps_ok = bool(isinstance(caps, Mapping) and caps)
    caps_bits = ", ".join("%s=%s" % (k, caps.get(k)) for k in
                          ("place", "list_orders", "order_state", "balances", "cancel"))
    steps.append(_step("capabilities", PASS if caps_ok else UNVERIFIED,
                       "caps: " + (caps_bits or "—"),
                       "امکانات اتصال خوانده شد" if caps_ok else "امکانات اتصال نیامده",
                       "" if caps_ok else "وضعیت اتصال را بررسی کنید"))

    statuses = {s["key"]: s["status"] for s in steps}
    if statuses["host"] != PASS:
        state = STATE_HOST_DOWN
    elif statuses["cdp"] != PASS:
        state = STATE_CDP_DOWN
    elif statuses["page"] != PASS:
        state = STATE_PAGE_MISSING
    elif statuses["login"] == BLOCKED:
        state = STATE_LOGIN_REQUIRED
    elif statuses["session"] == PASS and statuses["read_only"] == PASS \
            and statuses["contract"] == PASS:
        state = STATE_CONNECTED
    elif statuses["session"] == PASS and statuses["read_only"] == PASS:
        state = STATE_READ_ONLY_VERIFIED
    elif statuses["backend"] != PASS:
        state = STATE_BACKEND_DOWN
    else:
        state = STATE_API_UNVERIFIED

    first_action = next((s["action"] for s in steps
                         if s["status"] != PASS and s["action"]), "")
    if state == STATE_READ_ONLY_VERIFIED:
        account_action = next((s["action"] for s in steps
                               if s["key"] == "account" and s["status"] != PASS
                               and s["action"]), "")
        first_action = (account_action or
                        "نشست خواندنی تأیید شد؛ نوشتن سفارش همچنان بسته است")
    return {
        "status": "success", "backend_instance": "local",
        "app_version": app_version, "adapter": adapter,
        "state": state, "state_label": STATE_LABEL.get(state, state),
        "steps": steps, "step_count": len(steps),
        "next_action": first_action,
        "secrets_stored": False,
        "acceptance_time_observed": False,
        "observed_at": _iso(now), "diagnose_ms": round((time.monotonic() - t_all) * 1000, 1),
    }


def report(*, diagnosis: Mapping[str, Any]) -> dict[str, Any]:
    return redact({
        "status": "success", "mode": "READ_ONLY",
        "generated_at": _iso(),
        "live_ready": False,
        "secrets_stored": False,
        "connection": dict(diagnosis),
        "unverified": True,
        "note": "گزارش از host/CDP محلی خوانده می‌شود؛ هیچ token/cookie/payloadی در آن نیست",
    })


__all__ = ["PASS", "FAIL", "BLOCKED", "UNVERIFIED", "NOT_RUN", "STATE_LABEL",
           "cdp_pages", "diagnose", "report"]
