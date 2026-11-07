# -*- coding: utf-8 -*-
# P0 (ریگ‌دار): بن‌بستِ قفلِ ساختِ قیف با گرم‌کردنِ اسکرینر، رویِ مسیرِ واقعیِ استارت‌آپ.
# کشِ دیسکیِ اسکرینر کنار گذاشته می‌شود (rename، برگشت‌پذیر، با هش) تا رشتهٔ گرمِ واقعی
# اسکنِ سرد بزند؛ بلافاصله پس از آماده‌شدنِ پورت یک POSTِ قیفِ پیش‌فرض (همان کلیدِ UI)
# فرستاده می‌شود. دو نسخه: نسخهٔ اصلاح‌شده و نسخهٔ معیوبِ B1 (هر دو با کپی+هش، نه git).
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a2_gzip_abba import FUNNEL_BODY, PORT, RIG, WT, ready, restore, sha  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(WT, "api", "funnel.py")
BUG_COPY = os.path.join(HERE, "b1-after-src", "api_funnel.py")
BUG_SHA = "32eb1841d2501a9278ca1e75f776006a6c6355cf73bf9fabf226d159f86aa1db"
FIX_COPY = os.path.join(HERE, "p0-after-src", "api_funnel.py")
HEAD_COPY = os.path.join(HERE, "a1-backup", "api_funnel.py")
HEAD_SHA = "0867f8814f578a24ca67dff2e0b6af7e8d91bded61236553526f6197997e54fb"
VARIANTS = sys.argv[1:] or ["fixed", "bug"]
SC = os.path.join(WT, ".screener_cache.json")
SC_ASIDE = os.path.join(RIG, "screener_cache.p0-aside.json")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", BORS_NO_FETCH_LOOPS="1", PYTHONUNBUFFERED="1")
BASE = "http://127.0.0.1:%d" % PORT
POST_TIMEOUT = 340.0


def put(src, want):
    shutil.copyfile(src, SRC)
    got = sha(SRC)
    assert got == want, "hash mismatch after copy: %s" % got
    return got


def tail(path, stop, sink, t0):
    pos = 0
    while not stop.is_set():
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                fh.seek(pos)
                for line in fh.read().splitlines():
                    if line.strip():
                        sink.append((round(time.time() - t0, 2), line.strip()[:200]))
                pos = fh.tell()
        except OSError:
            pass
        time.sleep(0.2)


def post_funnel():
    req = urllib.request.Request(BASE + "/api/funnel", data=json.dumps(FUNNEL_BODY).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=POST_TIMEOUT) as r:
            body = r.read()
            st, xc = r.status, r.headers.get("X-Cache")
    except urllib.error.HTTPError as e:
        body, st, xc = e.read() or b"", e.code, None
    except Exception as e:  # timeout
        return {"error": "%s: %s" % (type(e).__name__, e), "ms": round((time.perf_counter() - t) * 1000)}
    try:
        status = json.loads(body.decode("utf-8")).get("status")
    except ValueError:
        status = None
    return {"http": st, "x_cache": xc, "status": status, "bytes": len(body),
            "ms": round((time.perf_counter() - t) * 1000)}


def get_ms(path, timeout=120):
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            n = len(r.read())
            return {"http": r.status, "bytes": n, "ms": round((time.perf_counter() - t) * 1000)}
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, e), "ms": round((time.perf_counter() - t) * 1000)}


def variant(tag, src, want):
    out = {"tag": tag, "funnel_sha": put(src, want), "db_pristine": restore()}
    if os.path.exists(SC):
        os.remove(SC)  # فقط کشی که ریگِ قبلیِ همین اسکریپت ساخت؛ اصلی درِ SC_ASIDE است
    out["screener_disk_cache_absent"] = not os.path.exists(SC)
    logp = os.path.join(RIG, "rig-p0-%s.out" % tag)
    log = open(logp, "w", encoding="utf-8")
    t0 = time.time()
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(PORT),
                          "--log-level", "warning"], cwd=WT, env=ENV, stdout=log, stderr=log)
    lines, stop = [], threading.Event()
    th = threading.Thread(target=tail, args=(logp, stop, lines, t0), daemon=True)
    th.start()
    try:
        out["ready_s"] = ready()
        out["post_sent_at_s"] = round(time.time() - t0, 2)
        out["post_first"] = post_funnel()
        out["post_first_done_at_s"] = round(time.time() - t0, 2)
        out["post_second"] = post_funnel()
        out["screener"] = get_ms("/api/screener")
    finally:
        p.terminate()
        try:
            p.wait(20)
        except subprocess.TimeoutExpired:
            p.kill()
        time.sleep(1.0)
        stop.set()
        th.join(3)
        log.close()
        time.sleep(1.5)
    keep = ("[screener]", "[startup] screener", "Traceback", "Error", "deadlock")
    out["log_events"] = [l for l in lines if any(k in l[1] for k in keep)]
    out["log"] = os.path.basename(logp)
    return out


def main():
    os.makedirs(os.path.dirname(FIX_COPY), exist_ok=True)
    fix_sha = sha(SRC)
    shutil.copyfile(SRC, FIX_COPY)
    assert sha(FIX_COPY) == fix_sha and sha(BUG_COPY) == BUG_SHA and fix_sha != BUG_SHA
    assert sha(HEAD_COPY) == HEAD_SHA
    copies = {"fixed": (FIX_COPY, fix_sha), "bug": (BUG_COPY, BUG_SHA), "head": (HEAD_COPY, HEAD_SHA)}
    res = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "fix_sha": fix_sha, "bug_sha": BUG_SHA, "head_sha": HEAD_SHA,
           "variants": VARIANTS, "post_timeout_s": POST_TIMEOUT,
           "env": {"BORS_NO_FETCH_LOOPS": "1", "PYTHONUNBUFFERED": ENV["PYTHONUNBUFFERED"]}}
    sc_sha = sha(SC) if os.path.exists(SC) else None
    res["screener_cache_orig_sha"] = sc_sha
    if sc_sha:
        assert not os.path.exists(SC_ASIDE)
        os.replace(SC, SC_ASIDE)
    try:
        for v in VARIANTS:
            res[v] = variant(v, *copies[v])
    finally:
        res["final_funnel_sha"] = put(FIX_COPY, fix_sha)
        res["db_restored_after"] = restore()
        if os.path.exists(SC):
            os.remove(SC)
        if sc_sha:
            os.replace(SC_ASIDE, SC)
            res["screener_cache_restored"] = sha(SC) == sc_sha
    name = "p0-rig-repro.json" if VARIANTS == ["fixed", "bug"] else "p0-rig-repro-%s.json" % "-".join(VARIANTS)
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in res if k not in copies}, ensure_ascii=False))
    for k in VARIANTS:
        v = res[k]
        print(k, "ready", v.get("ready_s"), "post1", v.get("post_first"), "post2", v.get("post_second"),
              "screener", v.get("screener"))
        for e in v.get("log_events", []):
            print("   ", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
