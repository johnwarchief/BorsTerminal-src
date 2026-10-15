#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سنجشِ زنجیره‌ایِ بیلدِ منجمد: دروازۀ /api/execution و /api/bot داخلِ EXE

بخشی از زنجیرۀ راستی‌آزماییِ مأموریتِ سرخطی/EasyTrader/ربات. مسیرها ازِ ریشۀ ریپو حساب می‌شوند، نه ازِ یکِ ماشینِ خاص.
"""
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

EXE = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate", "BorsTerminal_Ultimate.exe")
PORT = 8077
if "--exe" in sys.argv:
    EXE = os.path.abspath(sys.argv[sys.argv.index("--exe") + 1])
if "--port" in sys.argv:
    PORT = int(sys.argv[sys.argv.index("--port") + 1])
BASE = "http://127.0.0.1:%d" % PORT
# لاگ و JSON کنارِ همین EXE نمی‌نشینند (بیلدِ منتشرشده فقط‌خواندنی حساب می‌شود);
# هر دو درِ `_audit/` ریشه می‌مانند تا شاهدِ اجرا بایگانی شود.
LOG = os.path.join(ROOT, "_audit", "frozen_smoke_stdout.log")
RESULT = os.path.join(ROOT, "_audit", "frozen_smoke_result%s.json" % (sys.argv[sys.argv.index("--out-tag") + 1] if "--out-tag" in sys.argv else ""))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

results = []


def note(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + " :: " + str(detail)[:400], flush=True)


def _call(method, path, body=None, timeout=30):
    data = json.dumps(body or {}).encode("utf-8") if method in ("POST", "PUT") else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8", "replace"))


def get(path, timeout=30):
    return _call("GET", path, timeout=timeout)


def post(path, body=None, timeout=60):
    return _call("POST", path, body, timeout)


def put(path, body, timeout=30):
    return _call("PUT", path, body, timeout)


env = dict(os.environ)
env["BORS_PORTABLE"] = "1"
env["BORS_PORT"] = str(PORT)
env["PYTHONIOENCODING"] = "utf-8"
env["BORS_CODAL_OFFLINE"] = "1"

logf = open(LOG, "wb")
proc = subprocess.Popen([EXE], cwd=os.path.dirname(EXE), env=env,
                        stdout=logf, stderr=subprocess.STDOUT)
print("started pid=%d port=%d" % (proc.pid, PORT), flush=True)

try:
    up = False
    t0 = time.time()
    while time.time() - t0 < 240:
        if proc.poll() is not None:
            break
        try:
            st, body = get("/api/update/version", timeout=3)
            note("frozen_http_up", st == 200,
                 "up in %.0fs version=%s" % (time.time() - t0, body.get("version")))
            up = True
            break
        except Exception:
            time.sleep(2)
    if not up:
        note("frozen_http_up", False, "exit=%s after 240s" % proc.poll())
        raise SystemExit(1)

    st, v = get("/api/update/version")
    note("version_is_1089", v.get("version") == "1.0.89", json.dumps(v, ensure_ascii=False)[:300])

    # --- market data actually readable inside the package -------------------
    try:
        st, m = get("/api/market", timeout=120)
        rows = m.get("data") if isinstance(m, dict) else m
        n = len(rows) if isinstance(rows, list) else -1
        note("frozen_market_rows", st == 200 and n > 300,
             "count=%s len(data)=%s live=%s fossil=%s" %
             (m.get("count"), n, m.get("live_count"), m.get("fossil_count")))
    except Exception as e:
        note("frozen_market_rows", False, repr(e)[:250])

    # --- execution door (api/execution.py lives in the bundle) --------------
    try:
        st, s = get("/api/execution/status")
        note("frozen_execution_status", st == 200 and s.get("dry_run") is True,
             "dry_run=%s live_enabled=%s wire_hypothesis=%s blocked_on=%s caps=%s" %
             (s.get("dry_run"), s.get("live_enabled"), s.get("wire_hypothesis"),
              s.get("blocked_on"), json.dumps(s.get("capabilities"), ensure_ascii=False)[:220]))
    except Exception as e:
        note("frozen_execution_status", False, repr(e)[:250])

    # --- adapter module reachable inside the frozen build -------------------
    try:
        st, s = get("/api/execution/session")
        note("frozen_execution_session_route", st == 200,
             "state=%s keys=%s" % (s.get("state"), ",".join(list(s)[:10])))
    except Exception as e:
        note("frozen_execution_session_route", False, repr(e)[:250])

    # warm-up: همان کاری که تبِ قیف درِ استفادهٔ عادی می‌کند (ساختِ history
    # windows + اسکنِ فنی). بدونِ این، اولینِ فشارِ ربات هزینهٔ bootstrapِ قیف
    # را می‌پردازد و عددِ «ربات کند است» می‌دهد.
    try:
        st, wu = get("/api/funnel?preset=trend&chain=f_roobi", timeout=900)
        note("frozen_funnel_warmup", st == 200 and wu.get("status") == "success",
             "handover=%s tech_scan=%s" % (len(wu.get("handover") or []),
                                           json.dumps(wu.get("tech_scan") or {}, ensure_ascii=False)[:160]))
    except Exception as e:
        note("frozen_funnel_warmup", False, repr(e)[:200])

    # --- bot door (api/bot.py + bot_signals + paper_trading) ----------------
    try:
        st, b = get("/api/bot/status")
        cfg0 = b.get("config") or {}
        # `enabled` پیش‌فرضِ نصبِ تازه است، نه چیزِ این سنجش (این پوشۀ داده از
        # دورِ قبل خاموش نبود); پیش‌فرضِ خاموش را گارد dev/bot_api_v1114 می‌بندد.
        note("frozen_bot_status", st == 200 and cfg0.get("mode") == "paper"
             and b.get("auto_run") is False,
             "kill=%s mode=%s enabled=%s gates_all_open=%s"
             % (b.get("kill"), cfg0.get("mode"), cfg0.get("enabled"),
                (b.get("live_gates") or {}).get("all_open")))
    except Exception as e:
        note("frozen_bot_status", False, repr(e)[:250])

    # run while disabled -> must refuse, not fabricate (config از دورِ قبل روشن
    # مانده باشد، همین‌جا صریح خاموش می‌کنیم تا درِ «رباتِ خاموش» سنجیده شود)
    put("/api/bot/config", {"enabled": False})
    try:
        st, r = post("/api/bot/run", {})
        note("frozen_run_refused_when_disabled", r.get("status") == "refused",
             json.dumps(r, ensure_ascii=False)[:250])
    except Exception as e:
        note("frozen_run_refused_when_disabled", False, repr(e)[:250])

    st, c = put("/api/bot/config", {"enabled": True, "chain": ["f_roobi"]})
    cfg1 = c.get("config") or {}
    note("frozen_bot_enable", st == 200 and cfg1.get("enabled") is True
         and cfg1.get("chain") == ["f_roobi"],
         "errors=%s enabled=%s chain=%s" % (c.get("errors"), cfg1.get("enabled"), cfg1.get("chain")))

    run = {}
    try:
        t0 = time.time()
        st, r = post("/api/bot/run", {}, timeout=900)
        run = r.get("run") or {}
        note("frozen_bot_run_real", r.get("status") == "ok" and run.get("bars", 0) > 0,
             "wall=%.1fs status=%s session=%s in=%s bars=%s unpriced=%s sig=%s ms=%s" % (
                 time.time() - t0, r.get("status"), run.get("session"), run.get("symbols_in"),
                 run.get("bars"), len(run.get("unpriced") or []),
                 sum(int(d.get("signals") or 0) for d in run.get("decisions") or []), run.get("ms")))
        note("frozen_bot_no_fabricated_zero",
             r.get("status") != "ok" or (run.get("symbols_in", 0) > 0 and run.get("bars", 0) > 0),
             json.dumps({k: run.get(k) for k in ("symbols_in", "bars", "note")}, ensure_ascii=False)[:220])
    except Exception as e:
        note("frozen_bot_run_real", False, repr(e)[:300])
        note("frozen_bot_no_fabricated_zero", False, "run failed")

    st, s2 = get("/api/bot/status")
    note("frozen_pending_book_after_run",
         (s2.get("pending_drafts") or 0) > 0 and str(s2.get("verdict_session") or "") == str(run.get("session")),
         "pending=%s verdict_session=%s" % (s2.get("pending_drafts"), s2.get("verdict_session")))

    # فشارِ دوم رویِ همان نشست ⇒ هیچ سیگنالِ تکراری
    try:
        t0 = time.time()
        st, r2 = post("/api/bot/run", {}, timeout=900)
        run2 = r2.get("run") or {}
        sig2 = sum(int(d.get("signals") or 0) for d in run2.get("decisions") or [])
        note("frozen_no_duplicate_signal", sig2 == 0,
             "wall=%.1fs signals2=%s prev=%s" % (time.time() - t0, sig2, run2.get("prev_session")))
    except Exception as e:
        note("frozen_no_duplicate_signal", False, repr(e)[:250])

    # halt must be durable across the ledger, in the frozen build
    try:
        st, h = post("/api/bot/halt", {"reason": "frozen smoke"})
        note("frozen_bot_halt", st == 200 and h.get("kill") == "HALTED",
             json.dumps(h, ensure_ascii=False)[:200])
        st, b2 = get("/api/bot/status")
        note("frozen_halt_visible_in_status", b2.get("halted") is True
             and b2.get("kill") == "HALTED", "kill=%s halted=%s" % (b2.get("kill"), b2.get("halted")))
        st, r = post("/api/bot/run", {})
        note("frozen_run_refused_while_halted", r.get("status") == "halted",
             json.dumps(r, ensure_ascii=False)[:200])
        st, rs = post("/api/bot/resume", {})
        note("frozen_bot_resume", st == 200 and rs.get("kill") == "ARMED",
             json.dumps(rs, ensure_ascii=False)[:200])
    except Exception as e:
        note("frozen_bot_halt", False, repr(e)[:250])

    try:
        st, h = get("/api/bot/history")
        runs = h.get("runs") or []
        note("frozen_bot_history", st == 200 and (len(runs) >= 1 or len(h.get("events") or []) > 0),
             "runs=%d events=%d" % (len(runs), len(h.get("events") or [])))
    except Exception as e:
        note("frozen_bot_history", False, repr(e)[:250])

    # the durable flag must survive a restart of the process -> checked outside

    try:
        with urllib.request.urlopen(BASE + "/", timeout=20) as r:
            html = r.read().decode("utf-8", "replace")
        note("frozen_spa_served", "assets/" in html or 'id="root"' in html, "len=%d" % len(html))
    except Exception as e:
        note("frozen_spa_served", False, repr(e)[:200])
finally:
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    except Exception as e:
        print("kill failed: %r" % e)
    logf.close()

time.sleep(3)
leaks = []
try:
    raw = open(LOG, "rb").read().decode("utf-8", "replace")
except Exception:
    raw = ""
for needle in ("password", "token", "cookie", "authorization", "set-cookie"):
    for line in raw.splitlines():
        if needle in line.lower():
            leaks.append(needle + ":" + line[:120])
            break
note("frozen_log_has_no_secret_words", not leaks, "; ".join(leaks)[:500])

fails = [n for n, ok, _ in results if not ok]
print("\nSUMMARY: %d checks, %d fail -> %s" % (len(results), len(fails), ",".join(fails) or "none"))
with open(RESULT, "w", encoding="utf-8") as f:
    json.dump([{"check": n, "ok": ok, "detail": d} for n, ok, d in results], f,
              ensure_ascii=False, indent=1)
sys.exit(1 if fails else 0)
