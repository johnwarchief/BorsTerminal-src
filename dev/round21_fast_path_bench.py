#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round21_fast_path_bench — سنجشِ مسیرِ بحرانی با ترافیکِ بدیلِ زمان‌دار.

هیچ شبکه/سفارشِ واقعی. تأخیرِ هر پرسش *شبیه‌سازی* شده تا تفکیکِ «کارِ کندِ
پیش‌نمایش» از «مسیرِ تأیید» قابلِ اندازه‌گیری باشد:

  preview : GET نشست + GET موجودی + preflight + ساختِ بدنه
  confirm : claim + audit + یک POST
  old     : preflight (GET موجودی) + audit + POST + read-back (GET فهرست)

اعدادِ این فایل «عملکردِ واقعیِ کارگزاری» نیستند؛ فقط هزینهٔ ساختاریِ مسیر را
نشان می‌دهند. برایِ عملکردِ واقعی، آزمونِ مالک با نشستِ زنده لازم است.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DELAYS_MS = {"/core/api/order": 30.0, "/easy/api/money": 25.0,
             "/core/api/v2/order": 20.0}
ITERATIONS = 15


class TimedTransport:
    name = "timed-mock"
    is_live = True

    def __init__(self, delays=None):
        self.delays = dict(delays or DELAYS_MS)
        self.calls: list[tuple[str, str, float]] = []

    def request(self, *, method, url, headers, payload=None, timeout_s=7.0):
        path = urlparse(url).path or ""
        t0 = time.monotonic()
        time.sleep(self.delays.get(path, 0.0) / 1000.0)
        elapsed = (time.monotonic() - t0) * 1000.0
        self.calls.append((method, path, elapsed))
        from execution_easytrader import WireResponse
        if path.endswith("/core/api/order") and method == "GET":
            return WireResponse(200, {}, json.dumps(
                {"isSuccessful": True, "data": []}))
        if path.endswith("/easy/api/money"):
            return WireResponse(200, {}, json.dumps(
                {"buyPowerT2": 10_000_000_000, "credit": 0,
                 "avandCredit": 0}))
        if path.endswith("/core/api/v2/order") and method == "POST":
            return WireResponse(200, {}, json.dumps(
                {"isSuccessful": True, "id": "BR-BENCH"}))
        return WireResponse(404, {}, "{}")


def _draft(n: int, mode=None):
    from execution_contract import InstrumentRef, OrderDraft, OrderMode, Resolution, Side
    return OrderDraft(
        execution_id="bench-%03d" % n, side=Side.BUY, price=12345.0,
        quantity=100.0, mode=mode or OrderMode.SAFE,
        instrument=InstrumentRef(symbol="TEST", isin="IRO1TEST0001",
                                 broker_instrument="IRO1TEST0001",
                                 resolution=Resolution.EXACT))


def _pct(xs, p):
    if not xs:
        return None
    ys = sorted(xs)
    if len(ys) == 1:
        return round(ys[0], 2)
    k = (len(ys) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(ys) - 1)
    return round(ys[lo] + (ys[hi] - ys[lo]) * (k - lo), 2)


def main() -> int:
    os.environ["BORS_EXECUTION_DB"] = os.path.join(
        tempfile.mkdtemp(prefix="bench21_"), "execution.db")
    from execution_easytrader import EasyTraderAdapter
    from execution_fast_order import FastOrderGateway
    from execution_ledger import default_ledger
    from execution_service import ExecutionService, Limits

    tr = TimedTransport()
    ad = EasyTraderAdapter(transport=tr, token="bench-token",
                           base_url="https://api-mts.orbis.easytrader.ir")
    svc = ExecutionService(ad, dry_run=False, limits=Limits(),
                           audit=default_ledger())
    gw = FastOrderGateway()

    preview_ms: list[float] = []
    confirm_ms: list[float] = []
    old_ms: list[float] = []
    net = {"preview": [], "confirm": [], "old": []}
    for i in range(ITERATIONS):
        n = i * 2
        # ---- preview: کارِ کند ----
        c0 = len(tr.calls)
        t0 = time.monotonic()
        if not ad.session_proven():
            ad.authenticate()
        prepared = svc.prepare(_draft(n))
        snap = gw.create(prepared=prepared, payload={}, epoch=1,
                         token_ref=None, summary={})
        preview_ms.append((time.monotonic() - t0) * 1000.0)
        net["preview"].append(len(tr.calls) - c0)

        # ---- confirm: claim + audit + یک POST ----
        c0 = len(tr.calls)
        t0 = time.monotonic()
        gw.claim(snap.token, epoch=1, token_ref=None, halted=False)
        svc.execute(prepared, verify=False)
        confirm_ms.append((time.monotonic() - t0) * 1000.0)
        net["confirm"].append(len(tr.calls) - c0)

        # ---- old: preflight (موجودی) + audit + POST + read-back ----
        old_prepared = svc.prepare(_draft(n + 1))
        c0 = len(tr.calls)
        t0 = time.monotonic()
        svc.execute(old_prepared, verify=True)
        old_ms.append((time.monotonic() - t0) * 1000.0)
        net["old"].append(len(tr.calls) - c0)

    def block(xs):
        return {"n": len(xs), "p50": _pct(xs, 50), "p95": _pct(xs, 95),
                "min": round(min(xs), 2), "max": round(max(xs), 2)}

    out = {
        "clock": "monotonic",
        "transport": "timed-mock (no network)",
        "simulated_delay_ms": DELAYS_MS,
        "iterations": ITERATIONS,
        "phases": {
            "preview": block(preview_ms),
            "fast_confirm": block(confirm_ms),
            "old_dispatch_with_readback": block(old_ms),
        },
        "network_requests_per_phase": {
            k: {"p50": _pct([float(x) for x in v], 50),
                "calls": v[:5]} for k, v in net.items()},
        "note": ("شبیه‌سازیِ ساختاری؛ عددِ کارگزاریِ واقعی نیست. "
                 "confirm فقط یک POST دارد و read-back/صف در آن نیست."),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("\nmedian confirm: %.1f ms · median old: %.1f ms · delta: %.1f ms"
          % (statistics.median(confirm_ms), statistics.median(old_ms),
             statistics.median(old_ms) - statistics.median(confirm_ms)))
    print("EXIT=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
