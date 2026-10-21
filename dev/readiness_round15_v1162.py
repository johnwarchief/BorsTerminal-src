#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""readiness_round15_v1162 — گیت‌هایِ readiness از ورودیِ واقعی تغییر می‌کنند."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
PASS = FAIL = 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   " + label)
    else:
        FAIL += 1
        print("FAIL " + label + "  -> " + str(detail)[:240])


def main() -> int:
    import execution_readiness as RD
    from execution_owner_approval import OwnerApprovalStore

    tmp = tempfile.mkdtemp(prefix="ready15_")
    store = OwnerApprovalStore(os.path.join(tmp, "user.db"))
    s0 = store.state("live-order")
    ck(s0["approved"] is False and "execution_owner_approval" in s0["source"],
       "پیش‌فرضِ مجوزِ مالک false و قابلِ‌ردیابی است", s0)
    os.environ["BORS_OWNER_APPROVAL_PHRASE"] = "تأییدِ آزمونِ Round15"
    s1 = store.approve("تأییدِ آزمونِ Round15", note="unit")
    ck(s1["approved"] is True and s1["approved_at"],
       "تأییدِ صریح با عبارت ثبت می‌شود", s1)
    s2 = store.revoke("unit-revoke")
    ck(s2["approved"] is False, "revoke مجوز را برمی‌دارد", s2)

    checks = {k: RD.PASS for k in (
        "execution_id", "instrument", "side", "price", "quantity", "session",
        "duplicate", "place", "kill_switch")}
    base = dict(session_proven=True, read_only=True,
                buying_power={"state": "BUYING_POWER_VERIFIED",
                              "value": 10_000_000, "unit": "IRR",
                              "source": "test"},
                symbol_ready=True, preflight_checks=checks,
                lifecycle_tests=True, full_gate=True)
    r0 = RD.build_readiness(**base, contract_operational=False,
                            owner_approved=False)
    write = next(g for g in r0["gates"] if g["id"] == "write_contract")
    owner = next(g for g in r0["gates"] if g["id"] == "owner_approval")
    ck(r0["live_ready"] is False and write["status"] != RD.PASS
       and owner["status"] == RD.REQUIRED,
       "قراردادِ عملیاتیِ نامعلوم و مجوزِ نبوده ⇒ live_ready=false",
       {"live": r0["live_ready"], "write": write["status"],
        "owner": owner["status"]})

    r1 = RD.build_readiness(**base, contract_operational=True,
                            owner_approved=False)
    ck(r1["live_ready"] is False
       and any(g["id"] == "owner_approval" and g["status"] == RD.REQUIRED
               for g in r1["gates"]),
       "قرارداد سبز ولی بدونِ مجوزِ مالک ⇒ هنوز live_ready=false")

    r2 = RD.build_readiness(**base, contract_operational=True,
                            owner_approved=True)
    ck(r2["live_ready"] is True, "همهٔ گیت‌هایِ واقعی PASS ⇒ live_ready=true")
    r3 = RD.build_readiness(**{**base, "buying_power": {"state": "BLOCKED"}},
                            contract_operational=True, owner_approved=True)
    ck(r3["live_ready"] is False and r3["blocking_count"] >= 1,
       "تغییرِ یک گیتِ واقعی، حکمِ نهایی را برمی‌گرداند", r3["next_action"])

    shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d checks, %d failed" % (PASS + FAIL, FAIL))
    print("READINESS ROUND15 " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
