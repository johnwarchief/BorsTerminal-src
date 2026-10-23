#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""autoclicker_round22_bench_v1174 — سنجشِ مسیرِ بحرانی، پیش و پس از Round 22.

دو مسیرِ مستقل، هر کدام در پروسۀ خودش و رویِ همان fixtureِ محلیِ 127.0.0.1:

  legacy  : موتورِ Round 14 (`StrategyEngine.prepare/trigger`) — یک اسنپ‌شاتِ
            پیش‌از‌هدف، `driver.click(selector)`، و گاردِ dry-run.
  round22 : `AutoClickRunner`ِ چنداقدامی — warm، داوریِ DOM، `click_nth` با
            بازبینیِ آخرین‌لحظه.

هر دو dry-run هستند: کلیک واقعی درِ مرورگرِ محلی، درخواستِ سفارش abort، صفر
POSTِ رسیده. هیچ اتصالی به کارگزاری نیست.

خروجی: p50/p95 هر مرحله + جدولِ RTL. عددِ ساختگی نمی‌سازیم: هر خانه از شاهدِ
خودش (monotonic) می‌آید و اگر مرحله اندازه‌گیری نشده باشد «—» می‌ماند.
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

N = 15


def _pct(vals, q):
    got = sorted(v for v in vals if v is not None)
    if not got:
        return None
    k = max(0, min(len(got) - 1, int(round((len(got) - 1) * q))))
    return round(got[k], 2)


def _stats(vals):
    got = [v for v in vals if v is not None]
    if not got:
        return {"n": 0, "p50": None, "p95": None, "min": None, "max": None}
    return {"n": len(got), "p50": _pct(got, 0.5), "p95": _pct(got, 0.95),
            "min": round(min(got), 2), "max": round(max(got), 2)}


class Fixture:
    """سرورِ fixture + Chromiumِ محلی؛ همان چیزی که گاردِ لایۀ ۲ می‌سازد."""

    def __init__(self):
        import dev.autoclicker_round22_browser_v1173 as G
        import execution_browser as EB
        self.G, self.EB = G, EB
        self.state = G.State()
        self.server = G.DualStackServer(("::", 0), G.Handler)
        self.server.state = self.state
        self.port = int(self.server.server_port)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.fix = "http://127.0.0.1:%d" % self.port
        G.FIX = self.fix
        G.STATE = self.state
        self.cdp_port = G.free_port()
        self.cdp = "http://127.0.0.1:%d" % self.cdp_port
        G.CDP = self.cdp
        self.tmp = tempfile.mkdtemp(prefix="ac22bench_")
        profile = os.path.join(self.tmp, "profile")
        os.makedirs(profile, exist_ok=True)
        ok, exe = EB.browser_runtime_available()
        if not ok:
            raise RuntimeError("no browser: %s" % exe)
        args = [exe, "--headless=new", "--remote-debugging-port=%d" % self.cdp_port,
                "--remote-allow-origins=*", "--user-data-dir=%s" % profile,
                "--no-first-run", "--no-default-browser-check",
                "--disable-extensions", "--no-proxy-server",
                "--window-size=1280,900", "about:blank"]
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        if not G.wait_cdp(self.cdp):
            raise RuntimeError("CDP did not open")
        if G.ensure_host_page(self.fix + "/order?mode=standard") != 1:
            raise RuntimeError("host page not loaded")
        self.profile = profile

    def driver(self, strategy_id):
        import execution_strategy_core as Core
        s = Core.default_settings(Core.AUTOCLICKER)
        s.options = {"cdp_url": self.cdp, "order_url": self.fix + "/order",
                     "headless": True, "action_timeout_ms": 2000,
                     "intercept_pattern": "**/core/api/v2/order*",
                     "keep_driver_alive": True}
        d = self.EB.PlaywrightBrowserDriver(s, strategy_id=strategy_id,
                                            profile_dir=self.profile)
        d.start()
        return d

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(10)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass


def bench_round22():
    import execution_autoclick_executor as AC
    import execution_autoclick_run as RC
    import execution_ui_state as UIS

    fx = Fixture()
    out = {"path": "round22", "warm_ms": [], "validation_ms": [],
           "click_to_request_ms": [], "target_error_ms": [], "total_ms": [],
           "clicks": 0, "order_hits": 0}
    try:
        drv = fx.driver("bench22")
        store = RC.AutoClickRunStore(os.path.join(fx.tmp, "runs.db"))
        ui = UIS.UIOptions(submit_selector="button.order-submit",
                           price_selector="#price", quantity_selector="#quantity",
                           symbol_selector="[data-cy='order-form-header-symbol-name']",
                           isin_selector="#isin", side_selector="#side-label",
                           form_scope_selector="#order-form", side="buy",
                           expected_price=1000.0, expected_quantity=10.0,
                           expected_symbol="TEST", expected_isin="IRO1TEST0001")
        ctx = AC.ExecutorContext(driver=drv, ui=ui, dry_run=True,
                                 order_paths=("/core/api/v2/order",),
                                 allowed_hosts=("127.0.0.1",),
                                 request_timeout_ms=1500, response_timeout_ms=4000)
        ex = AC.AutoClickExecutor(lambda: ctx)
        for i in range(N):
            run = store.create(RC.RunConfig(
                symbol="TEST", isin="IRO1TEST0001", side="buy",
                expected_price=1000.0, expected_quantity=10.0,
                target_at=RC.format_tehran(int(time.time() * 1000)),
                mode="single", total_actions=1, dry_run=True, prewarm_ms=0))
            store.arm(run.run_id, validation={}, ok_for_arm=True)
            store.start(run.run_id)
            act = store.claim_next(run.run_id, at_ms=int(time.time() * 1000),
                                   token="bench")
            if act is None:
                break
            t0 = time.monotonic()
            warm = ex.run_warm()
            t1 = time.monotonic()
            hooks = type("H", (), {
                "mark_fired": staticmethod(lambda at_ms=None: True),
                "should_stop": staticmethod(lambda: False)})()
            res = ex(store.get(run.run_id), act, hooks)
            t2 = time.monotonic()
            out["warm_ms"].append((t1 - t0) * 1000.0)
            out["validation_ms"].append(res.get("validation_ms"))
            out["total_ms"].append((t2 - t0) * 1000.0)
            m = res.get("metrics") or {}
            out["click_to_request_ms"].append(m.get("click_to_request_ms"))
            out["target_error_ms"].append(abs(float(m.get("target_error_ms") or 0.0)))
            if res.get("fired"):
                out["clicks"] += 1
            if not warm.get("ok"):
                out["warm_failed"] = out.get("warm_failed", 0) + 1
            try:
                store.cancel(run.run_id, "bench")
            except Exception:
                pass
        out["order_hits"] = fx.state.snap()["order_hits"]
        drv.close()
    finally:
        fx.close()
    return out


def bench_legacy():
    """مسیرِ Round 14: prepare (اسنپ‌شات) + trigger (کلیک/گارد)."""
    import execution_browser as EB
    import execution_intent_store as IS
    import execution_strategy_core as SC
    import execution_strategy_engine as SE
    from execution_contract import InstrumentRef, OrderDraft, OrderMode, Side, Resolution

    fx = Fixture()
    out = {"path": "legacy", "prepare_ms": [], "trigger_ms": [],
           "click_to_request_ms": [], "clicks": 0, "order_hits": 0,
           "error": ""}
    try:
        db = os.path.join(fx.tmp, "user.db")
        settings_store = SC.StrategySettingsStore(db)
        intent_store = IS.IntentStore(os.path.join(fx.tmp, "intents.db"))
        opts = {
            "order_url": fx.fix + "/order?mode=standard",
            "origin_allowlist": [fx.fix, "http://localhost:%d" % fx.port],
            "symbol_selector": "",
            "form_symbol_selector": "[data-cy='order-form-header-symbol-name']",
            "open_form_selector": "",
            "open_form_selector_buy": "",
            "open_form_selector_sell": "",
            "price_selector": "#price",
            "quantity_selector": "#quantity",
            "submit_selector": "button.order-submit",
            "submit_selector_buy": "button.order-submit",
            "submit_selector_sell": "button.order-submit",
            "form_selector": "#order-form",
            "side_selector": "#side-label",
            "isin_selector": "#isin",
            "intercept_pattern": "**/core/api/v2/order*",
            "order_paths": ["/core/api/v2/order"],
            "order_method": "POST",
            "action_timeout_ms": 700,
            "response_timeout_ms": 250,
            "navigation_timeout_ms": 10000,
            "autofill": False,
            "require_prefilled": True,
            "headless": True,
            "profile_dir": os.path.join(fx.tmp, "legacy-profile"),
            "browser_path": "",
            "no_proxy": True,
            "keep_driver_alive": False,
            "cdp_url": fx.cdp,
        }
        settings_store.save(SC.AUTOCLICKER, mode=SC.MODE_SHADOW, options=opts)
        instr = InstrumentRef(symbol="TEST", ins_code="1", isin="IRO1TEST0001",
                              broker_instrument="IRO1TEST0001",
                              resolution=Resolution.EXACT)
        for i in range(N):
            eng = SE.StrategyEngine(
                None, settings_store=settings_store, mock_browser=False,
                scheduler=None, server_clock=lambda: {
                    "verified": True, "delta_ms": 0.0, "rtt_ms": 1.0,
                    "broker_time": "2026-10-24T00:00:00"},
                live_allowed=False, halted=lambda: (False, ""),
                intent_store=intent_store, recover_intents=False)
            draft = OrderDraft(execution_id="BENCH-%d" % i, instrument=instr,
                               side=Side.BUY, price=1000.0, quantity=10.0,
                               mode=OrderMode.SAFE)
            t0 = time.monotonic()
            prepared = eng.prepare(draft, SC.AUTOCLICKER)
            t1 = time.monotonic()
            res = eng.trigger(prepared.prepared_id, live=False)
            t2 = time.monotonic()
            out["prepare_ms"].append((t1 - t0) * 1000.0)
            out["trigger_ms"].append((t2 - t1) * 1000.0)
            if str(res.status) not in ("dry_run", "blocked"):
                out.setdefault("states", {})
                out["states"][str(res.status)] = out["states"].get(str(res.status), 0) + 1
            ev = getattr(res, "evidence", None) or {}
            if i == 0 and isinstance(ev, dict):
                out["evidence_keys"] = sorted(ev.keys())[:16]
            a = ev.get("action_start_mono_ms") if isinstance(ev, dict) else None
            r = ev.get("request_mono_ms") if isinstance(ev, dict) else None
            out["click_to_request_ms"].append(
                round(float(r) - float(a), 3) if (a is not None and r is not None) else None)
            if str(res.status) == "dry_run":
                out["clicks"] += 1
        out["order_hits"] = fx.state.snap()["order_hits"]
    except Exception as e:                                  # noqa: BLE001
        out["error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
    finally:
        fx.close()
    return out


def _run_one(mode):
    try:
        got = bench_round22() if mode == "round22" else bench_legacy()
    except Exception as e:                                  # noqa: BLE001
        got = {"path": mode, "error": "%s: %s" % (type(e).__name__, str(e)[:200])}
    print("BENCH_JSON " + json.dumps(got, ensure_ascii=False))
    return 0


def main(argv):
    if len(argv) >= 2 and argv[0] == "--one":
        return _run_one(argv[1])
    rows = {}
    for mode in ("legacy", "round22"):
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--one", mode],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=900)
        line = ""
        for ln in (r.stdout or "").splitlines():
            if ln.startswith("BENCH_JSON "):
                line = ln[len("BENCH_JSON "):]
        if not line:
            rows[mode] = {"path": mode,
                          "error": ((r.stdout or "") + (r.stderr or ""))[-240:]}
            continue
        rows[mode] = json.loads(line)

    def cell(stats):
        if not stats or stats.get("p50") is None:
            return "—"
        return "%s / %s" % (stats["p50"], stats["p95"])

    def pack(vals):
        return _stats(vals or [])

    lg, n22 = rows.get("legacy", {}), rows.get("round22", {})
    table = [
        ("آماده‌سازی پیش از هدف (ms)", pack(lg.get("prepare_ms")),
         pack(n22.get("warm_ms"))),
        ("داوری/اعتبارسنجی در لحظۀ اقدام (ms)", _stats([]),
         pack(n22.get("validation_ms"))),
        ("کلیک → شروع درخواست (ms)",
         pack(lg.get("click_to_request_ms")), pack(n22.get("click_to_request_ms"))),
        ("کل مسیر هر اقدام (ms)", pack(lg.get("trigger_ms")), pack(n22.get("total_ms"))),
        ("خطای هدف (ms)", _stats([]), pack(n22.get("target_error_ms"))),
    ]
    print("")
    print("| مرحله | Round 14 (p50 / p95) | Round 22 (p50 / p95) |")
    print("| --- | --- | --- |")
    for name, a, b in table:
        print("| %s | %s | %s |" % (name, cell(a), cell(b)))
    print("| کلیک‌هایِ واقعی | %s | %s |" % (lg.get("clicks", "—"),
                                            n22.get("clicks", "—")))
    print("| POSTِ رسیده به سرور | %s | %s |" % (lg.get("order_hits", "—"),
                                                n22.get("order_hits", "—")))
    for mode in ("legacy", "round22"):
        if rows.get(mode, {}).get("error"):
            print("note %s: %s" % (mode, rows[mode]["error"]))
        for key in ("states", "warm_failed"):
            if rows.get(mode, {}).get(key):
                print("note %s %s: %s" % (mode, key, rows[mode][key]))
    print("\nAUTOCLICKER ROUND22 BENCH " + ("OK" if not lg.get("error") else "PARTIAL"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
