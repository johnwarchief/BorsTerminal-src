# a1_si_solo_build.py — هزینهٔ خودِ switchinterval رویِ ساختِ قیف، بی‌هیچ درخواستِ هم‌زمان.
# چرا جدا: در a1_switchinterval_abba بازویِ 0.5ms درخواست‌هایِ ارزانِ بیشتری را
# درِ حینِ ساخت سرو می‌کند (۶-۸ در برابرِ ۱-۲)، پس «ساختِ کندتر» آنجا با بارِ اضافه قاطی است.
# اینجا: بازوها ABBA، هر بازو پردازهٔ تازه + بانکِ pristine، ۸ ساختِ سرد (POST/GET یک‌درمیان، هر کدام بعدِ TTL).
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a1_switchinterval_abba import EV, PORT, PRISTINE, PRISTINE_SHA, RIG, WT, ready, restore, sha  # noqa: E402

ARMS = [("A", 0.005), ("B", 0.0005), ("B", 0.0005), ("A", 0.005)]
# برچسبِ اجرا: اجرایِ نخست (پیش از refresh-aheadِ _tech_context) بی‌برچسب ماند
TAG = ("-" + sys.argv[1]) if len(sys.argv) > 1 else ""
UI_BODY = {"preset": "trend", "chain": [], "logic": "and", "fund_mode": "standard",
           "exceptions": {}, "drop_suffix": True}


def build(verb):
    if verb == "POST":
        req = urllib.request.Request("http://127.0.0.1:%d/api/funnel" % PORT, data=json.dumps(UI_BODY).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    else:
        req = urllib.request.Request("http://127.0.0.1:%d/api/funnel?preset=trend" % PORT)
    t0 = time.perf_counter()
    r = urllib.request.urlopen(req, timeout=180)
    r.read()
    return round((time.perf_counter() - t0) * 1000.0, 1), r.headers.get("X-Cache")


def main():
    assert sha(PRISTINE) == PRISTINE_SHA
    out = []
    for i, (arm, si) in enumerate(ARMS):
        ok_db = restore()
        env = dict(os.environ, BORS_NO_FETCH_LOOPS="1", PYTHONIOENCODING="utf-8")
        code = ("import sys; sys.setswitchinterval(%r); import uvicorn; "
                "uvicorn.run('app:app', host='127.0.0.1', port=%d, log_level='warning')" % (si, PORT))
        log = open(os.path.join(RIG, "rig-solo%s-%d-%s.out" % (TAG, i, arm)), "w", encoding="utf-8")
        p = subprocess.Popen([sys.executable, "-c", code], cwd=WT, env=env, stdout=log, stderr=log)
        try:
            up = ready()
            warm = build("POST")
            rows = []
            for j in range(8):
                time.sleep(8.6)
                rows.append((("POST", "GET")[j % 2],) + build(("POST", "GET")[j % 2]))
            out.append({"round": i, "arm": arm, "si_ms": si * 1000, "db_pristine": ok_db, "ready_s": round(up, 1),
                        "warmup": warm, "builds": rows})
            print(i, arm, "si=%gms" % (si * 1000), "warm", warm, [r[1] for r in rows], [r[2] for r in rows], flush=True)
        finally:
            p.terminate()
            try:
                p.wait(20)
            except subprocess.TimeoutExpired:
                p.kill()
            log.close()
            time.sleep(2)
    with open(os.path.join(EV, "a1-si-solo-build%s.json" % TAG), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
