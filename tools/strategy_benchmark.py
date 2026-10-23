#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""strategy_benchmark.py — بنچمارکِ منصفانهٔ Strategyهای سرخطی روی یک Mock محلی.

چه چیزی تغییر کرده (مأموریتِ ۲۰۲۶-۱۰-۲۰، مرحلهٔ ۲):
  • Direct API دیگر adapterِ درون‌فرایندی نیست؛ همان EasyTraderAdapter و
    RequestsTransportِ برنامه به یک Mock HTTPSِ محلی POST می‌فرستد.
  • همهٔ روش‌ها (Direct، JS، DOM، Keyboard، AutoClicker) به همان Mock و همان
    مسیرِ /core/api/v2/order می‌رسند؛ سرور زمانِ دریافت/پاسخ را ثبت می‌کند.
  • مراحل جدا اندازه‌گیری می‌شوند: prepare، schedule drift، trigger-to-dispatch،
    mock-receive، HTTP RTT، server-processing، local action.
  • warm-up از measured جدا است؛ cold (اولین اجرا) جدا گزارش می‌شود.
  • ترتیبِ Strategyها در هر چرخه عوض می‌شود؛ ۱۰۰ تکرارِ measured.
  • هیچ مقصد خارجی وجود ندارد: Direct فقط 127.0.0.1 و مرورگر فقط همان مبدأ.

TLSِ Mock خودامضا است؛ Direct فقط همان certِ تولیدشده را به‌عنوان CA می‌شناسد
(نه خاموش‌کردنِ اعتبارسنجی) و مرورگر `ignore_https_errors` را فقط در contextِ
همین Mockِ محلی دارد. Production هیچ‌کدام را نمی‌بیند. هیچ سفارشِ واقعی و هیچ
اتصالی به کارگزاری انجام نمی‌شود.
"""
from __future__ import annotations

import argparse
import datetime
import ipaddress
import json
import os
import random
import shutil
import ssl
import sys
import tempfile
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import execution_browser as EB
import execution_strategy_core as SC
import execution_strategy_engine as SE
import execution_easytrader as ET
from execution_contract import (
    InstrumentRef, OrderDraft, OrderMode, Resolution, Side,
)
from execution_timing import Scheduler, TimeSource, percentile

ORDER_PATH = "/core/api/v2/order"
_LOCK = threading.Lock()
_SEQ = 0
_RECEIVED: dict[str, dict] = {}
_RESPONDED: dict[str, float] = {}
_REQUESTS: list[dict] = []
_COUNTS: Counter = Counter()
_DELAY_MS = 5.0

_PAGE = """<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>Mock Sarkhati</title>
<style>
body{font-family:sans-serif;background:#f4f6fa;padding:24px}
.box{max-width:520px;margin:auto;background:#fff;padding:20px;border-radius:12px}
label{display:block;margin:10px 0 4px}input{width:100%;padding:8px;box-sizing:border-box}
button{margin-top:16px;padding:10px 18px;background:#1f6feb;color:#fff;border:0;border-radius:8px}
#result{margin-top:12px}
</style></head><body><div class="box">
<h3>Mock EasyTrader Order</h3>
<label>نماد</label><input data-testid="symbol" value="">
<label>قیمت</label><input data-testid="price" value="">
<label>حجم</label><input data-testid="quantity" value="">
<button data-testid="submit" type="button">ارسال</button>
<div id="result"></div>
<script>
const q = new URLSearchParams(location.search);
if (q.get('prefill') === '1') {
  document.querySelector('[data-testid=symbol]').value = q.get('symbol') || '';
  document.querySelector('[data-testid=price]').value = q.get('price') || '';
  document.querySelector('[data-testid=quantity]').value = q.get('quantity') || '';
}
document.querySelector('[data-testid=submit]').addEventListener('click', async () => {
  const body = {symbol: document.querySelector('[data-testid=symbol]').value,
                price: Number(document.querySelector('[data-testid=price]').value),
                quantity: Number(document.querySelector('[data-testid=quantity]').value)};
  try {
    const r = await fetch('/core/api/v2/order', {method:'POST',
      headers:{'Content-Type':'application/json','Accept':'application/json'},
      body: JSON.stringify(body)});
    const j = await r.json();
    document.getElementById('result').textContent = JSON.stringify(j);
  } catch (e) {
    document.getElementById('result').textContent = 'error: ' + e;
  }
});
</script></div></body></html>"""


def _now_ms() -> float:
    return time.monotonic() * 1000.0


def _stats() -> dict:
    with _LOCK:
        posts = sum(1 for r in _REQUESTS if r["method"] == "POST")
        gets = sum(1 for r in _REQUESTS if r["method"] == "GET")
        hosts = sorted({r.get("host", "") for r in _REQUESTS if r.get("host")})
        paths = Counter("%s %s" % (r["method"], r["path"]) for r in _REQUESTS)
        return {
            "requests_total": len(_REQUESTS),
            "get_total": gets,
            "order_posts": posts,
            "hosts": hosts,
            "paths": dict(paths),
            "received_ids": len(_RECEIVED),
            "responded_ids": len(_RESPONDED),
        }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def _send(self, code: int, body: bytes,
              ctype: str = "application/json; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path)
        with _LOCK:
            _REQUESTS.append({"method": "GET", "path": p.path,
                              "host": self.headers.get("Host", "")})
            _COUNTS["GET " + p.path] += 1
        if p.path == "/order":
            self._send(200, _PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif p.path == "/core/api/order":
            # اولین submitِ آداپتور یک authenticateِ فقط‌خواندنی می‌زند.
            self._send(200, b'{"orders":[]}')
        elif p.path == "/stats":
            self._send(200, json.dumps(_stats()).encode())
        else:
            self._send(404, b"")

    def do_POST(self):
        p = urlparse(self.path)
        n = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        if p.path != ORDER_PATH:
            self._send(404, b"")
            return
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {"_raw_len": len(raw)}
        recv = _now_ms()
        global _SEQ
        with _LOCK:
            _SEQ += 1
            oid = "MOCK-%d" % _SEQ
            _RECEIVED[oid] = {
                "mono_ms": recv,
                "wall_ms": time.time() * 1000.0,
                "body_len": len(raw),
                "body_keys": sorted(body.keys()) if isinstance(body, dict) else [],
            }
            _REQUESTS.append({"method": "POST", "path": p.path, "id": oid,
                              "host": self.headers.get("Host", "")})
            _COUNTS["POST " + p.path] += 1
        if _DELAY_MS > 0:
            time.sleep(_DELAY_MS / 1000.0)
        resp = {"isSuccessful": True, "id": oid}
        done = _now_ms()
        with _LOCK:
            _RESPONDED[oid] = done
        self._send(200, json.dumps(resp).encode("utf-8"))


class _Server(ThreadingHTTPServer):
    daemon_threads = True


def _make_cert(tmp: str) -> tuple[str, str]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .sign(key, hashes.SHA256()))
    cert_path = os.path.join(tmp, "cert.pem")
    key_path = os.path.join(tmp, "key.pem")
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.TraditionalOpenSSL,
                                  serialization.NoEncryption()))
    return cert_path, key_path


def _start_mock(delay_ms: float) -> tuple[_Server, threading.Thread, int, str]:
    global _DELAY_MS
    _DELAY_MS = float(delay_ms)
    tmp = tempfile.mkdtemp(prefix="bench_tls_")
    cert, key = _make_cert(tmp)
    srv = _Server(("127.0.0.1", 0), _Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv, th, srv.server_address[1], tmp


def _options(port: int, *, headless: bool, prefill: bool, profile_dir: str) -> dict:
    base = "https://127.0.0.1:%d" % port
    url = base + "/order"
    if prefill:
        url += "?prefill=1&symbol=TEST&price=1000&quantity=10"
    return {
        "order_url": url,
        "origin_allowlist": [base],
        "symbol_selector": "[data-testid=symbol]",
        "price_selector": "[data-testid=price]",
        "quantity_selector": "[data-testid=quantity]",
        "submit_selector": "[data-testid=submit]",
        "focus_selector": "[data-testid=submit]",
        "intercept_pattern": "**" + ORDER_PATH + "*",
        "api_path": ORDER_PATH,
        "action_timeout_ms": 2000,
        "navigation_timeout_ms": 30000,
        "response_timeout_ms": 3000,
        "headless": bool(headless),
        "ignore_https_errors": True,
        "no_proxy": True,
        "keep_driver_alive": True,
        "profile_dir": profile_dir,
        "preclick_check": True,
    }


def _direct_adapter(port: int, cert_path: str):
    import requests
    os.environ["BORS_EXECUTION_WIRE_HOSTS"] = "127.0.0.1"
    sess = requests.Session()
    sess.trust_env = False
    transport = ET.RequestsTransport(session=sess, verify=True)
    # فقط certِ همین Mockِ محلی به‌عنوان CA؛ هیچ اعتبارسنجیِ عمومی خاموش نمی‌شود.
    transport._verify = cert_path
    return ET.EasyTraderAdapter(
        transport=transport, token="BENCH-MOCK-TOKEN",
        base_url="https://127.0.0.1:%d" % port, writes_allowed=True,
        allow_loopback_base_url=True)


def _fake_clock():
    return {"verified": True, "delta_ms": 0.0, "rtt_ms": 0.0,
            "broker_time": "2026-10-20T00:00:00"}


def _draft(eid: str) -> OrderDraft:
    instr = InstrumentRef(symbol="TEST", ins_code="1", isin="IRO1TEST0001",
                          broker_instrument="IRO1TEST0001",
                          resolution=Resolution.EXACT)
    return OrderDraft(execution_id=eid, instrument=instr, side=Side.BUY,
                      price=1000.0, quantity=10.0, mode=OrderMode.SAFE)


def _delta(a, b):
    try:
        return round(float(a) - float(b), 3)
    except (TypeError, ValueError):
        return None


def _run_one(engine: SE.StrategyEngine, sid: str, idx: int,
             lead_ms: int, expected_host: str) -> dict:
    draft = _draft("BENCH-%s-%s-%d" % (sid, time.strftime("%H%M%S"), idx))
    order = engine.prepare(draft, sid)
    target = int(time.time() * 1000) + int(lead_ms)
    order.target_wall_ms = target
    try:
        res = engine.trigger(order.prepared_id, live=True, live_allowed=True)
    except Exception:
        try:
            engine.abort(order.prepared_id)
        except Exception:
            pass
        raise
    t = dict(res.timings or {})
    send_mono = t.get("send_mono_ms")
    dispatch = t.get("request_mono_ms") or t.get("dispatch_mono_ms")
    action_start = t.get("action_start_mono_ms")
    resp_mono = t.get("response_mono_ms")
    bid = res.broker_order_id
    with _LOCK:
        srv = dict(_RECEIVED.get(bid)) if bid and bid in _RECEIVED else None
        srv_resp = _RESPONDED.get(bid) if bid else None
    hosts = []
    for h in (res.evidence or {}).get("hosts", []) or []:
        if h and h not in hosts:
            hosts.append(str(h))
    external = [h for h in hosts if h != expected_host]
    http_rtt = t.get("response")
    if http_rtt is None and resp_mono is not None and dispatch is not None:
        http_rtt = _delta(resp_mono, dispatch)
    recv_delta = _delta(srv["mono_ms"], dispatch) if (srv and dispatch is not None) else None
    trig_to_resp = _delta(resp_mono, send_mono) if (resp_mono is not None and send_mono is not None) else None
    if trig_to_resp is None:
        trig_to_disp = _delta(dispatch or action_start, send_mono) if send_mono is not None else None
        if trig_to_disp is not None and http_rtt is not None:
            trig_to_resp = round(trig_to_disp + float(http_rtt), 3)
    return {
        "strategy": sid,
        "status": res.status,
        "accepted": bool(res.accepted),
        "error": res.error_code or "",
        "detail": (res.detail or "")[:160],
        "prepare": order.preparation_ms,
        "schedule_drift": (round(float(t.get("drift_us") or 0.0) / 1000.0, 3)
                           if "drift_us" in t else None),
        "trigger_to_dispatch": (_delta(dispatch or action_start, send_mono)
                                if (dispatch is not None or action_start is not None)
                                and send_mono is not None else None),
        "trigger_to_response": trig_to_resp,
        "mock_receive": recv_delta,
        "http_rtt": http_rtt,
        "server_processing": (_delta(srv_resp, srv["mono_ms"])
                              if (srv and srv_resp is not None) else None),
        "local_execution": t.get("total"),
        "local_action": t.get("action"),
        "broker_order_id": bid,
        "request_path": (res.evidence or {}).get("request_path"),
        "hosts": hosts,
        "external_hosts": external,
        "post_seen": srv is not None,
    }


def _metric(vals: list) -> dict:
    vals = [float(v) for v in vals if isinstance(v, (int, float))]
    if not vals:
        return {"n": 0, "p50": None, "p95": None, "p99": None,
                "min": None, "max": None}
    return {
        "n": len(vals),
        "p50": round(percentile(vals, 50), 3),
        "p95": round(percentile(vals, 95), 3) if len(vals) >= 20 else None,
        "p99": round(percentile(vals, 99), 3) if len(vals) >= 100 else None,
        "min": round(min(vals), 3),
        "max": round(max(vals), 3),
    }


PHASES = ("prepare", "schedule_drift", "trigger_to_dispatch",
          "trigger_to_response", "mock_receive", "http_rtt",
          "server_processing", "local_execution", "local_action")


def _summarize(rows: list[dict], expected_host: str) -> dict:
    statuses = Counter(str(r.get("status")) for r in rows)
    errors = Counter(str(r.get("error")) for r in rows if r.get("error"))
    return {
        "n": len(rows),
        "statuses": dict(statuses),
        "errors": dict(errors),
        "metrics": {ph: _metric([r.get(ph) for r in rows]) for ph in PHASES},
        "received_at_mock": sum(1 for r in rows if r.get("post_seen")),
        "external_hosts": sorted({h for r in rows for h in r.get("external_hosts", [])}),
        "hosts": sorted({h for r in rows for h in r.get("hosts", [])}),
    }


def _print_table(title: str, summary: dict[str, dict]) -> None:
    print("\n" + title)
    hdr = ("strategy", "n", "ok", "prep50/prep95", "drift50",
           "trig->disp50/95/99", "mockRecv50/95", "httpRTT50/95/99",
           "srvProc50", "posts", "ext")
    print(("%-14s %4s %4s %15s %9s %22s %17s %22s %10s %6s %4s" % hdr))
    for sid, s in summary.items():
        m = s["metrics"]
        def two(ph):
            x = m[ph]
            return "%s/%s" % (x["p50"] if x["p50"] is not None else "—",
                              x["p95"] if x["p95"] is not None else "—")
        def three(ph):
            x = m[ph]
            f = lambda v: v if v is not None else "—"
            return "%s/%s/%s" % (f(x["p50"]), f(x["p95"]), f(x["p99"]))
        ok = sum(v for k, v in s["statuses"].items() if k in ("accepted", "submitted"))
        print("%-14s %4d %4d %15s %9s %22s %17s %22s %10s %6d %4d" % (
            sid, s["n"], ok, two("prepare"),
            m["schedule_drift"]["p50"] if m["schedule_drift"]["p50"] is not None else "—",
            three("trigger_to_dispatch"),
            "%s/%s" % (m["mock_receive"]["p50"] if m["mock_receive"]["p50"] is not None else "—",
                       m["mock_receive"]["p95"] if m["mock_receive"]["p95"] is not None else "—"),
            three("http_rtt"),
            m["server_processing"]["p50"] if m["server_processing"]["p50"] is not None else "—",
            s["received_at_mock"], len(s["external_hosts"])))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=100,
                    help="measured iterations per strategy (default 100)")
    ap.add_argument("--warmup", type=int, default=3,
                    help="discarded warm-up iterations per strategy")
    ap.add_argument("--strategies",
                    default="direct_api,autoclicker,playwright_dom,javascript,keyboard")
    ap.add_argument("--target-lead-ms", type=int, default=200)
    ap.add_argument("--mock-delay-ms", type=float, default=5.0)
    ap.add_argument("--headless", action="store_true", default=True)
    ap.add_argument("--headed", dest="headless", action="store_false")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    sids = [s.strip() for s in args.strategies.split(",") if s.strip()]
    bad = [s for s in sids if s not in SC.ALL_STRATEGIES]
    if bad:
        print("unknown strategies: %s" % bad, file=sys.stderr)
        return 2
    sids = [s for s in sids if s != SC.SELENIUM]
    rng = random.Random(args.seed)
    srv, th, port, tls_tmp = _start_mock(args.mock_delay_ms)
    tmp = tempfile.mkdtemp(prefix="strategy_bench_")
    db = os.path.join(tmp, "user.db")
    store = SC.StrategySettingsStore(db)
    for sid in sids:
        opts = _options(port, headless=args.headless,
                        prefill=(sid == SC.AUTOCLICKER),
                        profile_dir=os.path.join(tmp, "profile-%s" % sid))
        if sid == SC.AUTOCLICKER:
            opts.update({"autofill": False, "require_prefilled": True})
        if sid == SC.KEYBOARD:
            opts.update({"key_sequence": ["Enter"]})
        store.save(sid, mode=SC.MODE_LIVE, options=opts)
    adapter = _direct_adapter(port, os.path.join(tls_tmp, "cert.pem"))
    engine = SE.StrategyEngine(
        adapter, settings_store=store, mock_browser=False,
        scheduler=Scheduler(TimeSource()),
        server_clock=_fake_clock, live_allowed=True,
        halted=lambda: (False, ""))
    # بنچمارکِ محلی بودجهٔ حسابِ واقعی مصرف نمی‌کند.
    try:
        engine.limiter.max_events = None
    except Exception:
        pass
    expected_host = "127.0.0.1:%d" % port
    report: dict = {
        "mode": "mock-live-https",
        "note": ("LOCAL MOCK ONLY — no broker is contacted. Direct API uses the "
                 "app's real EasyTraderAdapter/RequestsTransport against "
                 "127.0.0.1 and trusts only the generated test certificate as CA. "
                 "Browser contexts use ignore_https_errors=True, scoped to the "
                 "local mock context."),
        "iterations": args.iterations,
        "warmup": args.warmup,
        "target_lead_ms": args.target_lead_ms,
        "mock_delay_ms": args.mock_delay_ms,
        "seed": args.seed,
        "port": port,
        "expected_host": expected_host,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "unavailable": {},
        "cold": {},
        "measured": {},
    }
    measured: dict[str, list] = {sid: [] for sid in sids}
    warm: dict[str, list] = {sid: [] for sid in sids}
    try:
        def cycle(idx: int, *, is_measured: bool) -> None:
            order = list(sids)
            rng.shuffle(order)
            for sid in order:
                try:
                    row = _run_one(engine, sid, idx, args.target_lead_ms,
                                   expected_host)
                except Exception as e:               # noqa: BLE001
                    row = {"strategy": sid, "status": "error",
                           "error": "%s: %s" % (type(e).__name__, str(e)[:160]),
                           "detail": "", "external_hosts": [], "hosts": []}
                if is_measured:
                    measured[sid].append(row)
                else:
                    warm[sid].append(row)
                    if len(warm[sid]) == 1:
                        report["cold"][sid] = row

        for i in range(max(0, args.warmup)):
            cycle(-1 - i, is_measured=False)
        for i in range(max(1, args.iterations)):
            cycle(i, is_measured=True)

        for sid in sids:
            report["measured"][sid] = _summarize(measured[sid], expected_host)
            if not measured[sid]:
                report["unavailable"][sid] = "no measured rows"
        stats = _stats()
        report["server"] = stats
        report["server"]["external_hosts_seen_by_browser"] = sorted({
            h for s in report["measured"].values() for h in s["external_hosts"]})
        warm_posts = sum(1 for rows in warm.values() for r in rows
                         if r.get("post_seen"))
        report["server"]["warmup_posts"] = warm_posts
        report["server"]["expected_order_posts"] = (
            sum(s["received_at_mock"] for s in report["measured"].values())
            + warm_posts)
        report["server"]["order_posts_match"] = (
            stats["order_posts"] == report["server"]["expected_order_posts"])
        # رتبه‌بندیِ دو دستهٔ جدا: محلی و HTTP.
        def rank(phase: str) -> list[dict]:
            out = []
            for sid, s in report["measured"].items():
                m = s["metrics"].get(phase) or {}
                accepted = s["statuses"].get("accepted", 0) + s["statuses"].get("submitted", 0)
                usable = bool(m.get("n")) and accepted > 0 and not s["external_hosts"]
                out.append({"strategy": sid, "usable": usable,
                            "p50": m.get("p50"), "p95": m.get("p95"),
                            "p99": m.get("p99"), "accepted": accepted,
                            "errors": sum(s["errors"].values())})
            out.sort(key=lambda x: (not x["usable"],
                                    x["p95"] if x["p95"] is not None else 1e18,
                                    x["p50"] if x["p50"] is not None else 1e18,
                                    x["strategy"]))
            return out
        report["rank_local"] = rank("trigger_to_dispatch")
        report["rank_http"] = rank("http_rtt")
        report["rank_end_to_end"] = rank("trigger_to_response")
        report["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as f:
                f.write(text + "\n")
        print("LOCAL MOCK ONLY — no broker endpoint is contacted.")
        print("iterations=%d warmup=%d target_lead=%dms mock_delay=%sms port=%d"
              % (args.iterations, args.warmup, args.target_lead_ms,
                 args.mock_delay_ms, port))
        _print_table("MEASURED (warm)", report["measured"])
        print("\nCOLD (first warm-up per strategy)")
        for sid, r in report["cold"].items():
            print("  %-14s %-10s prep=%s trig->disp=%s recv=%s rtt=%s"
                  % (sid, r.get("status"), r.get("prepare"),
                     r.get("trigger_to_dispatch"), r.get("mock_receive"),
                     r.get("http_rtt")))
        print("\nSERVER", json.dumps({k: stats[k] for k in
              ("requests_total", "order_posts", "hosts", "paths")}, ensure_ascii=False))
        print("RANK local", [(x["strategy"], x["p95"]) for x in report["rank_local"]])
        print("RANK http ", [(x["strategy"], x["p95"]) for x in report["rank_http"]])
        print("RANK e2e  ", [(x["strategy"], x["p95"]) for x in report["rank_end_to_end"]])
        return 0
    finally:
        try:
            engine.close()
        except Exception:
            pass
        try:
            srv.shutdown()
            srv.server_close()
            th.join(timeout=3)
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(tls_tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
