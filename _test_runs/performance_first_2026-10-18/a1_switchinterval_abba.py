# a1_switchinterval_abba.py — آیا تأخیرِ درخواستِ ارزان درِ حینِ ساختِ قیف ازِ GIL است؟
# بازوها: sys.setswitchinterval پیش‌فرض (۵ms) در برابرِ ۰٫۵ms، ترتیبِ ABBA،
# هر بازو یک پردازشِ تازه با بانکِ pristine. فقط ریگِ :8020؛ به :8000/:8010 دست نمی‌زند.
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

WT = r"C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf"
EV = os.path.join(WT, "_test_runs", "performance_first_2026-10-18")
RIG = r"C:\Users\Johnkallnaya\AppData\Local\Temp\bors_rig"
PRISTINE = os.path.join(RIG, "market.db.pristine")
PRISTINE_SHA = "9d557a533fc51e8356528da634e2f468154ad85625cdace713f6fb434eeb4f34"
DB = os.path.join(WT, "market.db")
PORT = 8020
ARMS = [("A", 0.005), ("B", 0.0005), ("B", 0.0005), ("A", 0.005)]
# پیشوندِ خروجی: اجرایِ کدِ قدیم درِ a1-si-oldcode/ نگه داشته شده؛ اجرایِ تازه برچسبِ خودش را دارد
TAG = sys.argv[1] if len(sys.argv) > 1 else ""
WITH_DEVTEST = "--devtest" in sys.argv


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def restore():
    for suf in ("-wal", "-shm"):
        if os.path.exists(DB + suf):
            os.remove(DB + suf)
    shutil.copyfile(PRISTINE, DB)
    return sha(DB) == PRISTINE_SHA


def ready(timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/api/watchlist" % PORT, timeout=3).read()
            return time.time() - t0
        except Exception:
            time.sleep(0.5)
    return None


def main():
    assert sha(PRISTINE) == PRISTINE_SHA, "pristine تغییر کرده"
    results = []
    for i, (arm, si) in enumerate(ARMS):
        ok_db = restore()
        env = dict(os.environ, BORS_NO_FETCH_LOOPS="1", PYTHONIOENCODING="utf-8")
        code = ("import sys; sys.setswitchinterval(%r); import uvicorn; "
                "uvicorn.run('app:app', host='127.0.0.1', port=%d, log_level='warning')" % (si, PORT))
        log = open(os.path.join(RIG, "rig-si-%d-%s.out" % (i, arm)), "w", encoding="utf-8")
        p = subprocess.Popen([sys.executable, "-c", code], cwd=WT, env=env, stdout=log, stderr=log)
        try:
            up = ready()
            if up is None:
                results.append({"round": i, "arm": arm, "error": "rig not ready"})
                continue
            # گرم‌کردن: بارِ نخستِ تابلو/غربال درِ حافظه، تا دورها فقط ساختِ قیف را بسنجند
            urllib.request.urlopen(urllib.request.Request(
                "http://127.0.0.1:%d/api/funnel" % PORT, data=b'{"preset":"trend"}',
                headers={"Content-Type": "application/json"}, method="POST"), timeout=180).read()
            runs = {}
            for cheap, n, order in (("/api/mstat/phase", 1, "PGGP"), ("/api/update/version", 6, "PG")):
                out = os.path.join(EV, "a1-si%s-r%d-%s-%s-n%d.json" % (TAG, i, arm, cheap.strip("/").replace("/", "_"), n))
                r = subprocess.run([sys.executable, os.path.join(EV, "a1_hol_probe.py"), "--port", str(PORT),
                                    "--order", order, "--n", str(n), "--cheap", cheap,
                                    "--label", "switchinterval=%gms" % (si * 1000), "--out", out],
                                   env=env, capture_output=True, text=True, encoding="utf-8")
                runs[cheap] = json.load(open(out, encoding="utf-8")) if r.returncode == 0 else {"rc": r.returncode, "err": r.stderr[-500:]}
            devtest = None
            if WITH_DEVTEST:
                t = subprocess.run([sys.executable, os.path.join(WT, "dev", "funnel_body_cache_v1.py"),
                                    "--port", str(PORT)], cwd=WT, env=env,
                                   capture_output=True, text=True, encoding="utf-8")
                with open(os.path.join(EV, "a1-si%s-r%d-%s-devtest.txt" % (TAG, i, arm)), "w",
                          encoding="utf-8") as fh:
                    fh.write(t.stdout + t.stderr)
                devtest = {"rc": t.returncode,
                           "fails": [ln for ln in t.stdout.splitlines() if ln.startswith("FAIL")],
                           "tail": t.stdout.strip().splitlines()[-1:]}
            results.append({"round": i, "arm": arm, "switchinterval_s": si, "db_pristine": ok_db,
                            "ready_s": round(up, 1), "pid": p.pid, "runs": runs, "devtest": devtest})
        finally:
            p.terminate()
            try:
                p.wait(20)
            except subprocess.TimeoutExpired:
                p.kill()
            log.close()
            time.sleep(2)
    with open(os.path.join(EV, "a1-switchinterval-abba%s.json" % TAG), "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    for r in results:
        if "runs" not in r:
            print(r)
            continue
        if r.get("devtest"):
            print(r["round"], r["arm"], "devtest rc", r["devtest"]["rc"], r["devtest"]["tail"], r["devtest"]["fails"])
        for cheap, rr in r["runs"].items():
            if isinstance(rr, dict):
                print(r["round"], r["arm"], cheap, rr)
                continue
            for x in rr:
                print(r["round"], r["arm"], "si=%gms" % (r["switchinterval_s"] * 1000), x["verb"], cheap,
                      "n=%d" % len(x["x_cache"]), "build", x["build_ms"], "before", x["cheap_before_med"],
                      "during", x["cheap_during_series"][:8])


if __name__ == "__main__":
    main()
