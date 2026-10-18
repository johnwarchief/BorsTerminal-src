# -*- coding: utf-8 -*-
"""Smokeِ بستهٔ onedirِ همین مأموریت — بی‌دست‌زدنِ نصبِ کاربر و :8000.

ایزوله: `bors_portable.flag` + `data/market.db`ِ کپیِ pristine، `LOCALAPPDATA`ِ جعلی برایِ همین
فرایند، `BORS_PORT=8123` + `BORS_NO_FETCH_LOOPS=1`.

دورِ اول (۲۲:۲۳) دو اثرِ شبکه‌ای داشت که این نسخه می‌بندد: (۱) پیش‌پروازِ بسته `market.db.lzma`
را ازِ Release دانلود و ادغام کرد چون lzmaی کنارِ داده نبود؛ اینجا همان lzmaِ تأییدشدهٔ Release
(ذخیره‌شده ازِ دورِ اول) با مُهرِ baselineِ برابرش کنارِ داده گذاشته می‌شود ⇒ نه دانلود، نه ادغام.
(۲) پنجرهٔ WebView2 با درخواست‌هایِ چارت `_schedule_history_repair` را روشن کرد (این مسیر
زیرِ `BORS_NO_FETCH_LOOPS` نیست) ⇒ ~۲۰ دریافتِ واقعیِ CDN. اینجا پراکسیِ مرده
(`127.0.0.1:9`) با `NO_PROXY=127.0.0.1,localhost` هر خروجیِ HTTP(S)ِ فرایندِ بسته را می‌بندد و
لاگِ خودِ بسته (`logs/bors.log`؛ exeِ پنجره‌ای stdout ندارد) گواهِ نرسیدن است.

قراردادِ مشروط: GET ⇒ ۳۰۴، POST ⇒ ۴۱۲ (RFC 9110 §13.1.2). هر بررسی جدا گرفته می‌شود تا
خطایِ یکی بقیه و نوشتنِ `b2-smoke.json` را نبرد.
"""
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BUNDLE = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate")
EXE = os.path.join(BUNDLE, "BorsTerminal_Ultimate.exe")
RIG = r"C:\Users\Johnkallnaya\AppData\Local\Temp\bors_rig"
PRISTINE = os.path.join(RIG, "market.db.pristine")
PRISTINE_SHA = "9d557a533fc51e8356528da634e2f468154ad85625cdace713f6fb434eeb4f34"
REL_LZMA = os.path.join(RIG, "release-market.db.lzma")
REL_LZMA_SHA = "e7df91dc0af257715494fbf31d64047ab4043d4b9d165e2467ca73b52d308157"
TAG = os.environ.get("SMOKE_TAG", "run2")
PORT = int(os.environ.get("SMOKE_PORT", "8123"))
BASE = "http://127.0.0.1:%d" % PORT
DEAD_PROXY = "http://127.0.0.1:9"
FUNNEL = {"preset": "trend", "chain": [], "logic": "and", "fund_mode": "standard",
          "exceptions": {}, "drop_suffix": True}
out = {"bundle": BUNDLE, "port": PORT, "tag": TAG, "checks": [], "at": time.strftime("%Y-%m-%d %H:%M:%S")}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def rec(name, ok, detail):
    out["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
    print(("  ok   " if ok else "  FAIL ") + name + "  <- " + str(detail)[:160], flush=True)


def guard(name, fn):
    try:
        return fn()
    except Exception as e:
        rec(name, False, "exception %s: %s" % (type(e).__name__, e))
        return None


def fetch(path, method="GET", body=None, headers=None, timeout=180):
    h = {"Accept-Encoding": "gzip"}
    h.update(headers or {})
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        h["content-type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw, hd, st = r.read(), {k.lower(): v for k, v in r.headers.items()}, r.status
    except urllib.error.HTTPError as e:
        raw, hd, st = e.read(), {k.lower(): v for k, v in e.headers.items()}, e.code
    ms = round((time.perf_counter() - t0) * 1000, 1)
    wire = len(raw)
    if hd.get("content-encoding") == "gzip":
        raw = gzip.decompress(raw)
    return {"status": st, "wire": wire, "decoded": len(raw), "ms": ms, "etag": hd.get("etag", ""),
            "xc": hd.get("x-cache", ""), "enc": hd.get("content-encoding", "identity"), "body": raw}


def strip_cached_for(b):
    i = b.rfind(b',"cached_for_ms":')
    return b[:i] + b"}" if i > 0 and b.endswith(b"}") else b


def port_open():
    s = socket.socket()
    s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def prepare():
    """دادهٔ بسته را ازِ صفر می‌چیند (data/ و logs/ فقط ساختهٔ smokeهایِ همین مأموریت‌اند)."""
    for d in ("data", "logs"):
        p = os.path.join(BUNDLE, d)
        if os.path.isdir(p):
            shutil.rmtree(p)
    os.makedirs(os.path.join(BUNDLE, "data"))
    io.open(os.path.join(BUNDLE, "bors_portable.flag"), "w").close()
    db = os.path.join(BUNDLE, "data", "market.db")
    shutil.copyfile(PRISTINE, db)
    lz = os.path.join(BUNDLE, "data", "market.db.lzma")
    shutil.copyfile(REL_LZMA, lz)
    with open(os.path.join(BUNDLE, "data", "market.db.baseline"), "w", encoding="utf-8") as f:
        f.write(REL_LZMA_SHA)
    out["prep"] = {"market_db_sha256": sha(db), "lzma_sha256": sha(lz), "baseline_stamp": REL_LZMA_SHA,
                   "screener_disk_cache_present": os.path.exists(os.path.join(BUNDLE, "data", ".screener_cache.json"))}
    return out["prep"]["market_db_sha256"] == PRISTINE_SHA and out["prep"]["lzma_sha256"] == REL_LZMA_SHA


def checks(boot_s):
    v = json.loads(fetch("/api/update/version")["body"])
    out["version"] = v
    rec("نسخهٔ بسته", bool(v.get("version")), v)

    def spa():
        idx = fetch("/")
        rec("SPA ازِ داخلِ بسته سرو می‌شود", idx["status"] == 200 and b"root" in idx["body"],
            "%s %sB" % (idx["status"], idx["wire"]))
        m = re.search(rb'src="(/assets/index-[^"]+\.js)"', idx["body"])
        js = fetch(m.group(1).decode()) if m else None
        label = "ردیفی از نشستِ جاری".encode("utf-8")
        rec("بستهٔ سروشده برچسبِ اصلاحِ F1 را دارد", js is not None and js["status"] == 200 and label in js["body"],
            "%s sha256=%s" % (m.group(1).decode() if m else None, hashlib.sha256(js["body"]).hexdigest() if js else None))
    guard("SPA/F1", spa)

    mk = guard("`/api/market`", lambda: fetch("/api/market"))
    if mk:
        rec("`/api/market` gzip سطحِ پیش‌فرض (بی‌BORS_GZIP_LEVEL)", mk["status"] == 200 and mk["enc"] == "gzip"
            and 1_200_000 < mk["wire"] < 2_000_000 and mk["decoded"] > 6_000_000,
            "wire=%sB decoded=%sB %s %s %sms" % (mk["wire"], mk["decoded"], mk["enc"], mk["xc"], mk["ms"]))
        mk2 = guard("GETِ مشروطِ تابلو", lambda: fetch("/api/market", headers={"If-None-Match": mk["etag"]}))
        if mk2:
            rec("GETِ مشروطِ تابلو ⇒ ۳۰۴ِ صفر‌بایت", mk2["status"] == 304 and mk2["wire"] == 0, mk2["status"])

    # همان ترتیبِ دورِ اول: قیف بلافاصله پس ازِ تابلو، وقتی گرم‌کردنِ اسکرینر (بی‌کشِ دیسک) هنوز در کار است.
    t_rel = round(time.time() - T0, 1)
    f1 = guard("قیفِ POST", lambda: fetch("/api/funnel", "POST", FUNNEL))
    if not f1:
        return
    out["funnel_first"] = {"sent_at_s": t_rel, "ms": f1["ms"], "xc": f1["xc"], "status": f1["status"]}
    rec("قیفِ POST ⇒ ۲۰۰ + X-Cache", f1["status"] == 200 and f1["xc"] in ("MISS", "HIT"),
        "%s wire=%sB decoded=%sB %sms (sent at +%ss)" % (f1["xc"], f1["wire"], f1["decoded"], f1["ms"], t_rel))
    f2 = guard("قیفِ دوم", lambda: fetch("/api/funnel", "POST", FUNNEL))
    if f2:
        same = hashlib.sha256(strip_cached_for(f1["body"])).hexdigest() == hashlib.sha256(strip_cached_for(f2["body"])).hexdigest()
        rec("قیفِ دوم درِ همان TTL ⇒ HIT، بدنه (بی‌cached_for_ms) یکی", f2["xc"] == "HIT" and same and f1["etag"] == f2["etag"],
            "%sms vs %sms same=%s" % (f2["ms"], f1["ms"], same))
        f3 = guard("POSTِ مشروط", lambda: fetch("/api/funnel", "POST", FUNNEL, headers={"If-None-Match": f2["etag"]}))
        if f3:
            rec("POSTِ مشروط ⇒ ۴۱۲ِ بی‌بدنه (نه ۳۰۴)", f3["status"] == 412 and f3["wire"] == 0, f3["status"])

    def gets():
        g1 = fetch("/api/funnel?preset=trend")
        g2 = fetch("/api/funnel?preset=trend", headers={"If-None-Match": g1["etag"]})
        rec("GETِ مشروطِ قیف ⇒ ۳۰۴ِ صفر‌بایت", g1["status"] == 200 and g2["status"] == 304 and g2["wire"] == 0,
            "%s→%s %s" % (g1["status"], g2["status"], g2["xc"]))
    guard("GETِ مشروطِ قیف", gets)

    def screener():
        s = fetch("/api/screener")
        d = json.loads(s["body"].decode("utf-8", "replace"))
        gate = (d.get("funnel_gate") or {}).get("state")
        rec("اسکرینر ۲۰۰ با ردیف و دروازهٔ قیفِ اعمال‌شده", s["status"] == 200 and len(d.get("data") or []) > 100
            and gate == "applied", "%s ردیف، gate=%s %sms" % (len(d.get("data") or []), gate, s["ms"]))
    guard("اسکرینر", screener)

    def rows():
        r = json.loads(fetch("/api/market")["body"].decode("utf-8", "replace"))
        rec("دادهٔ واقعی ازِ بانکِ کپی‌شده", len(r.get("data") or []) > 1000,
            "%s ردیف، last_sync=%s" % (len(r.get("data") or []), (r.get("meta") or {}).get("last_sync")))
    guard("دادهٔ تابلو", rows)


def scan_log():
    src = os.path.join(BUNDLE, "logs", "bors.log")
    dst = os.path.join(HERE, "b2-smoke-%s-bors.log" % TAG)
    if not os.path.exists(src):
        rec("لاگِ بسته (`logs/bors.log`) نوشته شد", False, "نیست")
        return
    shutil.copyfile(src, dst)
    txt = open(dst, "rb").read().decode("utf-8", "replace")
    lines = txt.splitlines()
    bad = [ln for ln in lines if re.search(r"Traceback|ERROR|Exception", ln)]
    hist = [ln for ln in lines if "[history]" in ln]
    saved = [ln for ln in hist if "rows saved" in ln]
    out["bundle_log"] = {"path": os.path.basename(dst), "sha256": sha(dst), "lines": len(lines),
                         "error_lines": bad[:40], "history_lines": len(hist), "history_rows_saved": len(saved),
                         "history_samples": hist[:8],
                         "release_download": [ln for ln in lines if "downloaded from Release" in ln or "Release download" in ln],
                         "baseline_merge": [ln for ln in lines if "merged" in ln and "baseline" in ln],
                         "screener": [ln for ln in lines if "[screener]" in ln]}
    rec("لاگِ بسته بی‌Traceback/ERROR", not bad, "%d خط، %d خطِ خطا" % (len(lines), len(bad)))
    rec("پیش‌پرواز بی‌دانلود و بی‌ادغامِ baseline", not out["bundle_log"]["release_download"]
        and not out["bundle_log"]["baseline_merge"], out["bundle_log"]["release_download"] + out["bundle_log"]["baseline_merge"])
    rec("هیچ دریافتِ تاریخچه‌ای ازِ شبکه به بانک نرسید", not saved, "%d خطِ [history]، %d ذخیره" % (len(hist), len(saved)))


T0 = time.time()


def main():
    global T0
    if port_open():
        rec("پیش‌نیاز: پورتِ smoke آزاد است", False, "پورت %d اشغال است" % PORT)
        return 2
    if not guard("آماده‌سازیِ دادهٔ بسته", prepare):
        rec("آماده‌سازیِ دادهٔ بسته (هش‌ها)", False, out.get("prep"))
        return 2
    lad = os.path.join(ROOT, "_test_runs", "smoke-localappdata")
    os.makedirs(lad, exist_ok=True)
    env = dict(os.environ, BORS_PORT=str(PORT), BORS_NO_FETCH_LOOPS="1", LOCALAPPDATA=lad,
               HTTP_PROXY=DEAD_PROXY, HTTPS_PROXY=DEAD_PROXY, http_proxy=DEAD_PROXY, https_proxy=DEAD_PROXY,
               NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
    env.pop("BORS_GZIP_LEVEL", None)
    out["env_overrides"] = {k: env[k] for k in ("BORS_PORT", "BORS_NO_FETCH_LOOPS", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")}
    out["exe_sha256"] = sha(EXE)
    exe_log = os.path.join(HERE, "b2-smoke-%s-exe-stdout.txt" % TAG)
    logf = open(exe_log, "wb")
    T0 = time.time()
    p = subprocess.Popen([EXE], cwd=BUNDLE, env=env, stdout=logf, stderr=subprocess.STDOUT)
    out["pid"] = p.pid
    try:
        up = None
        while time.time() - T0 < 420:
            try:
                with urllib.request.urlopen(BASE + "/api/health", timeout=3) as r:
                    if r.status == 200:
                        up = round(time.time() - T0, 1)
                        break
            except Exception:
                time.sleep(2.0)
        out["boot_s"] = up
        rec("بوتِ بک‌اندِ بسته‌شده (بی‌pythonِ سیستم)", up is not None, "%ss" % up if up else "۴۲۰s بالا نیامد")
        if up is not None:
            guard("بررسی‌هایِ HTTP", lambda: checks(up))
    finally:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3.0)
        logf.close()
        rec("بسته بسته شد و پورت آزاد است", not port_open(), "pid=%s" % p.pid)
        out["exe_stdout_lines"] = len(open(exe_log, "rb").read().splitlines())
        guard("لاگِ بسته", scan_log)
        db = os.path.join(BUNDLE, "data", "market.db")
        out["market_db_sha256_after"] = sha(db) if os.path.exists(db) else None
    good = sum(1 for c in out["checks"] if c["ok"])
    out["summary"] = "%d/%d" % (good, len(out["checks"]))
    print("result: %s" % out["summary"])
    return 0 if good == len(out["checks"]) else 1


if __name__ == "__main__":
    rc = 3
    try:
        rc = main()
    except Exception as e:
        out["fatal"] = "%s: %s" % (type(e).__name__, e)
    finally:
        out["rc"] = rc
        io.open(os.path.join(HERE, "b2-smoke-%s.json" % TAG), "w", encoding="utf-8").write(
            json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(rc)
