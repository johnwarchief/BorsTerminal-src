# -*- coding: utf-8 -*-
"""execution_readiness.py — دروازهٔ متمرکزِ «آماده برای تأیید مالک».

این ماژول هیچ شبکه‌ای نمی‌زند و هیچ سفارشی نمی‌سازد. ورودی‌اش وضعیتِ
فقط‌خواندنیِ سرویس، منبعِ قدرت خرید، و نتیجهٔ preflight یکِ قصدِ نمونه است.
خروجی، گیت‌هایِ جدا و یک `live_ready` است که تا وقتی قرارداد نوشتن *عملیاتی*
تأیید نشده و مالک اجازه نداده باشد، هرگز true نمی‌شود.

تفکیکِ اصلی: «داده و ریسک آماده است» با «ارسال مجاز است» یکی نیست.
`preflight` فعلی `place` را هم رد می‌کند (چون نوشتن خاموش است)؛ اینجا
`data_risk_ready` همان preflight را بدونِ `place` می‌خواند و مانعِ نوشتن را
جدا گزارش می‌کند.
"""
from __future__ import annotations

from typing import Any, Mapping

from execution_write_contract import CONTRACT_STATE, contract_report

PASS = "PASS"
BLOCKED = "BLOCKED"
UNVERIFIED = "UNVERIFIED"
NOT_RUN = "NOT_RUN"
REQUIRED = "REQUIRED"


def _gate(gid: str, label: str, status: str, detail: str, *,
          action: str = "", source: str = "") -> dict[str, Any]:
    return {"id": gid, "label": label, "status": status, "detail": detail,
            "action": action, "source": source}


def _preflight_without_write(checks: Mapping[str, str] | None) -> str:
    if not checks:
        return NOT_RUN
    relevant = {k: v for k, v in checks.items() if k not in ("place",)}
    if any(v == "FAIL" for v in relevant.values()):
        return BLOCKED
    if any(v != PASS for v in relevant.values()):
        return BLOCKED
    return PASS


def build_readiness(*, session_proven: bool, read_only: bool,
                    buying_power: Mapping[str, Any] | None,
                    symbol_ready: bool | None = None,
                    preflight_checks: Mapping[str, str] | None = None,
                    contract_operational: bool = False,
                    owner_approved: bool = False,
                    lifecycle_tests: bool | None = None,
                    full_gate: bool | None = None) -> dict[str, Any]:
    gates: list[dict[str, Any]] = []
    gates.append(_gate(
        "read_only_session", "نشستِ فقط‌خواندنی",
        PASS if (session_proven and read_only) else BLOCKED,
        "نشست با پرسشِ فقط‌خواندنی تأیید شده" if (session_proven and read_only)
        else "نشستِ تأییدشده یا حالتِ فقط‌خواندنی موجود نیست",
        action="" if (session_proven and read_only) else "در پنجرهٔ کارگزاری وارد شوید و «بررسی وضعیت» را بزنید",
        source="execution status/session"))
    gates.append(_gate(
        "symbol_identity", "نماد و ISIN",
        PASS if symbol_ready is True else (BLOCKED if symbol_ready is False else NOT_RUN),
        "ISIN و ins_code از بانکِ محلی resolve شد" if symbol_ready is True
        else ("نماد/ISIN قابلِ سفارش نیست" if symbol_ready is False else "نمادی برایِ سنجش انتخاب نشده"),
        action="" if symbol_ready is True else "نماد را از دیده‌بان/پرتفوی انتخاب کنید",
        source="market.db.instruments"))
    bp_state = str((buying_power or {}).get("state") or "")
    bp_val = (buying_power or {}).get("value")
    bp_ok = bp_state == "BUYING_POWER_VERIFIED" and bp_val is not None
    gates.append(_gate(
        "buying_power", "قدرت خرید",
        PASS if bp_ok else BLOCKED,
        ("مقدار %s %s" % (bp_val, (buying_power or {}).get("unit") or "")) if bp_ok
        else "منبعِ قدرت خرید تأییدشده/عددی نیست",
        action="" if bp_ok else "منبعِ /easy/api/money را با نشستِ معتبر بخوانید",
        source=str((buying_power or {}).get("source") or "none")))
    checks = preflight_checks or None
    price_ok = bool(checks and checks.get("price") == PASS and checks.get("quantity") == PASS)
    gates.append(_gate(
        "price_quantity", "قیمت و مقدار",
        PASS if price_ok else (BLOCKED if checks else NOT_RUN),
        "قیمت و مقدارِ مثبت و معتبر" if price_ok else "قیمت/مقدار هنوز سنجیده نشده",
        action="" if price_ok else "پیش‌فرودِ پنلِ سفارش را با قیمت/مقدار اجرا کنید",
        source="preflight"))
    risk = _preflight_without_write(checks)
    gates.append(_gate(
        "data_risk", "داده و ریسک (بی‌نوشتن)",
        risk,
        "همهٔ بررسی‌هایِ داده/ریسک سبز؛ فقط نوشتن جداگانه بسته است" if risk == PASS
        else ("یک بررسیِ داده/ریسک رد یا نامعلوم است" if risk == BLOCKED
              else "preflightِ نمونه اجرا نشده"),
        action="" if risk == PASS else "پیش‌فرود را اجرا و موانعِ داده/حساب را رفع کنید",
        source="preflight بدونِ place"))
    gates.append(_gate(
        "write_contract", "قرارداد نوشتن",
        PASS if contract_operational else UNVERIFIED,
        ("قرارداد عملیاتی تأیید شد" if contract_operational
         else "قرارداد فقط از کدِ اول‌طرفی بازسازی شده؛ پاسخِ واقعیِ ثبت دیده نشده"),
        action="" if contract_operational else "آزمونِ مجازِ ثبت با تأییدِ مالک",
        source=CONTRACT_STATE))
    gates.append(_gate(
        "order_response", "معنای پاسخ سفارش",
        PASS if contract_operational else UNVERIFIED,
        "2xx فقط «ثبتِ درخواست» است؛ accepted/filled ادعا نمی‌شود" if not contract_operational
        else "معنای پاسخ با آزمونِ عملیاتی تأیید شد",
        action="" if contract_operational else "پس از قرارداد، پاسخِ واقعی را با فهرست/OMS تطبیق دهید",
        source="execution_easytrader.interpret_easytrader_response"))
    gates.append(_gate(
        "duplicate_guard", "جلوگیری از تکرار",
        PASS if lifecycle_tests is True else NOT_RUN,
        "ledger + prepared + durable trail" if lifecycle_tests is True
        else "کد پیاده است؛ نتیجهٔ گاردِ چرخهٔ عمر جداگانه گزارش می‌شود",
        action="" if lifecycle_tests is True else "گاردِ قرارداد/چرخهٔ عمر را اجرا کنید",
        source="execution_service.preflight"))
    gates.append(_gate(
        "timeout_reconcile", "timeout و تطبیق",
        PASS if lifecycle_tests is True else NOT_RUN,
        "UNKNOWN + reconcile، بی‌retry کور" if lifecycle_tests is True
        else "کد پیاده است؛ نتیجهٔ گاردِ چرخهٔ عمر جداگانه گزارش می‌شود",
        action="" if lifecycle_tests is True else "گاردِ قرارداد/چرخهٔ عمر را اجرا کنید",
        source="execution_service.preflight/execute"))
    gates.append(_gate(
        "audit_secrets", "ردِّپا و حفاظتِ راز",
        PASS if lifecycle_tests is True else NOT_RUN,
        "redact + log_body=False + گاردِ نشت" if lifecycle_tests is True
        else "کد پیاده است؛ نتیجهٔ گاردِ امنیت جداگانه گزارش می‌شود",
        action="" if lifecycle_tests is True else "گاردِ حساب/redaction را اجرا کنید",
        source="dev/execution_account_sources_v1146.py"))
    gates.append(_gate(
        "lifecycle_tests", "تستِ قرارداد و چرخهٔ عمر",
        PASS if lifecycle_tests is True else NOT_RUN,
        "گاردِ قرارداد/چرخهٔ عمر سبز است" if lifecycle_tests is True
        else "در این پاسخ اجرا نشده",
        action="" if lifecycle_tests is True else "dev/execution_write_contract_v1147.py را اجرا کنید",
        source="dev/execution_write_contract_v1147.py"))
    gates.append(_gate(
        "full_project_gate", "گیتِ کاملِ پروژه",
        PASS if full_gate is True else (BLOCKED if full_gate is False else NOT_RUN),
        "run_all_tests سبز است" if full_gate is True
        else ("گیتِ کامل قرمز است" if full_gate is False else "در این پاسخ اجرا نشده"),
        action="" if full_gate is True else "python dev/run_all_tests.py",
        source="dev/run_all_tests.py"))
    gates.append(_gate(
        "owner_approval", "مجوزِ مالک",
        PASS if owner_approved else REQUIRED,
        "مالک اجازهٔ آزمونِ واقعیِ مشخص را داده" if owner_approved
        else "هیچ ردیفِ تأییدی در execution_owner_approval نیست",
        action="" if owner_approved else "درخواستِ مشخصِ مالک برایِ نخستین سفارش",
        source="execution_owner_approval"))

    hard = [g for g in gates if g["id"] in (
        "read_only_session", "symbol_identity", "buying_power", "price_quantity",
        "write_contract", "order_response", "duplicate_guard", "timeout_reconcile",
        "audit_secrets", "lifecycle_tests", "full_project_gate", "owner_approval")]
    live_ready = all(g["status"] == PASS for g in hard)
    data_risk_ready = all(g["status"] == PASS for g in gates
                          if g["id"] in ("read_only_session", "symbol_identity",
                                         "buying_power", "price_quantity", "data_risk"))
    blocking = [g for g in gates if g["status"] != PASS]
    return {
        "data_risk_ready": bool(data_risk_ready),
        "live_ready": bool(live_ready),
        "live_enabled": False,
        "contract_state": CONTRACT_STATE,
        "contract": contract_report(),
        "gates": gates,
        "blocking_count": len(blocking),
        "next_action": next((g["action"] for g in blocking if g["action"]),
                            "هیچ مانعی نیست"),
        "status": "success",
    }


__all__ = ["PASS", "BLOCKED", "UNVERIFIED", "NOT_RUN", "REQUIRED",
           "build_readiness"]
