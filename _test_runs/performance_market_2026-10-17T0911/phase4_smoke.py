# -*- coding: utf-8 -*-
"""Smokeِ آرتیفکت‌سازِ بیلدِ دسکتاپ — بی‌دست‌زدنِ نصبِ کاربر.

چرا اسکریپت و نه لاگِ دست‌نویس: اعدادِ §۴ گزارش باید ازِ فایلِ خامِ همین دور
بازتولید شوند، نه ازِ حافظهٔ اجرایِ اول.

ایزوله‌سازی (سه لایه):
  * `bors_portable.flag` + `data/market.db`ِ کپی → بانک و پوشۀ داده داخلِ خودِ
    بسته می‌مانند، نه `%LOCALAPPDATA%`ِ نصبِ کاربر.
  * `LOCALAPPDATA`ِ جعلی برایِ همین فرایند → پروفایلِ WebView2/app_profile هم
    جایِ دیگری می‌نشیند.
  * `BORS_PORT=8123` و `BORS_NO_FETCH_LOOPS=1` → نه رقابت با :8000، نه هیچ
    دریافتِ TSETMC/CODAL.
"""
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BUNDLE = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate")
EXE = os.path.join(BUNDLE, "BorsTerminal_Ultimate.exe")
PORT = int(os.environ.get("SMOKE_PORT", "8123"))
BASE = "http://127.0.0.1:%d" % PORT
def fa(v):
    return "".join(chr(0x06F0 + int(c)) for c in str(v))


FUNNEL = {"preset": "trend", "chain": [], "logic": "and", "fund_mode": "standard",
          "exceptions": {}, "drop_suffix": True}
out = {"bundle": BUNDLE, "port": PORT, "checks": [], "at": time.strftime("%Y-%m-%d %H:%M:%S")}


def rec(name, ok, detail):
    out["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
    print(("  ok   " if ok else "  FAIL ") + name + "  ← " + str(detail)[:150])


def fetch(path, method="GET", body=None, headers=None):
    h = {"Accept-Encoding": "gzip"}
    h.update(headers or {})
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        h["content-type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read()
            hd = {k.lower(): v for k, v in r.headers.items()}
            st = r.status
    except urllib.error.HTTPError as e:
        raw, hd, st = e.read(), {k.lower(): v for k, v in e.headers.items()}, e.code
    ms = round((time.perf_counter() - t0) * 1000, 1)
    if hd.get("content-encoding") == "gzip":
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
    # `wire` = بایتِ واقعیِ رویِ سوکت (content-lengthِ فشرده)؛ `decoded` = بدنهٔ
    # بازکرده. ادعایِ «gzipِ سطحِ ۱» باید رویِ اولی سنجیده شود، نه دومی.
    return {"status": st, "wire": int(hd.get("content-length") or len(raw)),
            "decoded": len(raw), "ms": ms,
            "etag": hd.get("etag", ""), "xc": hd.get("x-cache", ""),
            "enc": hd.get("content-encoding", "identity"), "body": raw}


def main():
    env = dict(os.environ)
    env.update({"BORS_PORT": str(PORT), "BORS_NO_FETCH_LOOPS": "1",
                "LOCALAPPDATA": os.path.join(ROOT, "_test_runs", "smoke-localappdata")})
    if not os.path.exists(os.path.join(BUNDLE, "bors_portable.flag")):
        io.open(os.path.join(BUNDLE, "bors_portable.flag"), "w").close()
    if not os.path.exists(os.path.join(BUNDLE, "data", "market.db")):
        rec("پیش‌نیاز: data/market.dbِ کپی", False, "نیست — بیلد را آماده نکرده‌اید")
        return 2
    t0 = time.time()
    p = subprocess.Popen([EXE], cwd=BUNDLE, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    up = None
    while time.time() - t0 < 420:
        try:
            with urllib.request.urlopen(BASE + "/api/health", timeout=3) as r:
                if r.status == 200:
                    up = round(time.time() - t0, 1)
                    break
        except Exception:
            time.sleep(2.0)
    rec("بوتِ بک‌اندِ بسته‌شده (بی‌`python`ِ سیستم)", up is not None,
        "%ss" % up if up else "۴۲۰ ثانیه صبر کرد و بالا نیامد")
    if up is None:
        return 1
    try:
        h = fetch("/api/health")
        rec("`/api/health` ازِ EXE", h["status"] == 200 and h["wire"] > 0, h["status"])
        idx = fetch("/")
        rec("SPA ازِ داخلِ بسته سرو می‌شود (نه dev server)",
            idx["status"] == 200 and b"root" in idx["body"],
            "%s %sB" % (idx["status"], idx["wire"]))
        mk = fetch("/api/market")
        rec("`/api/market` با gzipِ سطحِ " + fa(1) + " (بی‌`BORS_GZIP_LEVEL`ِ محیطی)",
            mk["status"] == 200 and mk["enc"] == "gzip" and 1_200_000 < mk["wire"] < 2_000_000
            and mk["decoded"] > 6_000_000,
            "wire=%sB decoded=%sB %s %s" % (mk["wire"], mk["decoded"], mk["enc"], mk["xc"]))
        mk5 = fetch("/api/market", headers={"If-None-Match": mk["etag"]})
        rec("اعتبارسنجیِ مشروطِ تابلو ⇒ `304` با صفر بایت",
            mk5["status"] == 304 and mk5["wire"] == 0, mk5["status"])
        f1 = fetch("/api/funnel", "POST", FUNNEL)
        rec("قیفِ سرد ⇒ `200` + `X-Cache: MISS`", f1["status"] == 200 and f1["xc"] == "MISS",
            "wire=%sB decoded=%sB %sms" % (f1["wire"], f1["decoded"], f1["ms"]))
        f2 = fetch("/api/funnel", "POST", FUNNEL)
        rec("قیفِ گرم درِ همان TTL ⇒ `HIT` با بدنهٔ بایت‌به‌بایت یکی",
            f2["xc"] == "HIT" and hashlib.sha256(f1["body"]).hexdigest() ==
            hashlib.sha256(f2["body"]).hexdigest(),
            "%sms vs %sms، etag یکی=%s" % (f2["ms"], f1["ms"], f1["etag"] == f2["etag"]))
        f3 = fetch("/api/funnel", "POST", FUNNEL, headers={"If-None-Match": f1["etag"]})
        rec("POSTِ مشروط ⇒ `304` با صفر بایت", f3["status"] == 304 and f3["wire"] == 0,
            f3["status"])
        rows = json.loads(fetch("/api/market")["body"].decode("utf-8", "replace"))
        rec("دادهٔ واقعی ازِ بانکِ کپی‌شده می‌آید", len(rows.get("data") or []) > 1000,
            "%s ردیف، last_sync=%s" % (len(rows.get("data") or []),
                                       (rows.get("meta") or {}).get("last_sync")))
    finally:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2.0)
        rec("بسته بسته شد و پورت آزاد است", not _port_open(), "pid=%s" % p.pid)
    good = sum(1 for c in out["checks"] if c["ok"])
    out["summary"] = "%d/%d" % (good, len(out["checks"]))
    print("\nنتیجه: %s" % out["summary"])
    return 0 if good == len(out["checks"]) else 1


def _port_open():
    import socket
    s = socket.socket()
    s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", PORT))
        return True
    except Exception:
        return False
    finally:
        s.close()


if __name__ == "__main__":
    rc = main()
    io.open(os.path.join(HERE, "phase4-smoke.json"), "w", encoding="utf-8").write(
        json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(rc)
