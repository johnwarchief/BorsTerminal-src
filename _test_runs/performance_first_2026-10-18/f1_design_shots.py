# -*- coding: utf-8 -*-
# F1 × DESIGN.md §5: نشانِ تازگی پیش (HEAD) و پس (اصلاح) رویِ مرورگرِ واقعی، ۱۳۶۶×۷۶۸ و ۱۶۰۰×۹۰۰.
# فقط ساعتِ کلاینت (--clock) رویِ ریگِ :8020 میخکوب می‌شود؛ بانکِ pristine؛ BORS_NO_FETCH_LOOPS=1.
# جابه‌جاییِ سه فایلِ فرانت فقط با کپی و درستیِ هش، نه git checkout؛ در finally کدِ اصلاح برمی‌گردد و بیلد تازه می‌شود.
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a2_gzip_abba import BASE, PORT, RIG, WT, ready, restore, sha  # noqa: E402
from f1_badge_live import badge, dist_has_fix  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.join(HERE, "f1-design")
FE = os.path.join(WT, "frontend")
FILES = {
    "frontend/src/shared/lib/feedFreshness.ts":
        ("2e258ab8125011997b280b57561d0b96a92755dbd5bd4c2dbef4386304ed73b1",
         "c84a0689453aabda74b033ac70f8797c959d628bbd004aa47a5106a6409656eb"),
    "frontend/src/shared/components/FreshnessBadge.tsx":
        ("0f3b634673ace36b332714d72790e1023135b7b908abd5a696d88db435ea93ad",
         "dca05d9162c2288fc3356949dd940fccfcee0b85116d39471c8ac54e35810569"),
    "frontend/src/features/market/components/MarketStatusPanel.tsx":
        ("584d9bea5a717d63a5d514baf6f3aa608c07c6ee3f72384cc26b08af8f0537df",
         "4608b581e0cfd78a709fc75954be77380f3a1602eaf50b2339d84cf97596d08c"),
}
CLOCK = "2026-10-17T10:00:00+03:30"
VIEWS = [(1366, 768), (1600, 900)]
MON_S = 50
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", MSYS_NO_PATHCONV="1")


def head_copy(rel):
    return os.path.join(HERE, "f1-backup", os.path.basename(rel))


def fix_copy(rel):
    return os.path.join(EV, "fixed-src", os.path.basename(rel))


def put_all(which):
    out = {}
    for rel, (h, f) in FILES.items():
        src, want = (head_copy(rel), h) if which == "head" else (fix_copy(rel), f)
        dst = os.path.join(WT, rel)
        shutil.copyfile(src, dst)
        got = sha(dst)
        assert got == want, "%s: %s != %s" % (rel, got, want)
        out[rel] = got
    return out


def build(tag):
    log = os.path.join(EV, "build-%s.txt" % tag)
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as fh:
        rc = subprocess.run(["npm.cmd", "run", "build"], cwd=FE, stdout=fh, stderr=subprocess.STDOUT, env=ENV,
                            timeout=900).returncode
    return {"rc": rc, "dur_s": round(time.time() - t0, 1), "log": os.path.basename(log), "dist": dist_has_fix()}


def arm(tag, vw, vh):
    d = os.path.join(EV, "%s-%dx%d" % (tag, vw, vh))
    os.makedirs(d, exist_ok=True)
    rec = {"arm": tag, "viewport": [vw, vh], "clock": CLOCK, "db_pristine": restore()}
    log = open(os.path.join(RIG, "rig-f1d-%s-%d.out" % (tag, vw)), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(PORT),
                          "--log-level", "warning"], cwd=WT, env=dict(ENV, BORS_NO_FETCH_LOOPS="1"),
                         stdout=log, stderr=log)
    try:
        up = ready()
        rec["ready_s"] = round(up, 1) if up else None
        if up is None:
            rec["error"] = "rig not ready"
            return rec
        time.sleep(3.0)
        with open(os.path.join(d, "monitor-console.txt"), "w", encoding="utf-8") as fh:
            rec["monitor_exit"] = subprocess.run(
                ["node", os.path.join(WT, "tools", "perf_market_open_monitor.mts"), "--url", BASE, "--out", d,
                 "--duration", str(MON_S), "--journey", "market:%d" % MON_S, "--warm-after", "20",
                 "--clock", CLOCK, "--vw", str(vw), "--vh", str(vh)],
                cwd=WT, stdout=fh, stderr=fh, timeout=MON_S + 120, env=ENV).returncode
        rec["badge"] = badge(d)
        rec["shots"] = sorted(x for x in os.listdir(d) if x.endswith(".png"))
        return rec
    finally:
        p.terminate()
        try:
            p.wait(20)
        except subprocess.TimeoutExpired:
            p.kill()
        log.close()
        time.sleep(2)


def main():
    os.makedirs(os.path.join(EV, "fixed-src"), exist_ok=True)
    for rel, (h, f) in FILES.items():
        assert sha(os.path.join(WT, rel)) == f, "%s is not the fixed code" % rel
        assert sha(head_copy(rel)) == h
        shutil.copyfile(os.path.join(WT, rel), fix_copy(rel))
        assert sha(fix_copy(rel)) == f
    res = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "clock": CLOCK, "arms": []}
    try:
        res["head_put"] = put_all("head")
        res["build_head"] = build("head")
        if res["build_head"]["rc"] == 0 and not res["build_head"]["dist"]["files_with_fix"]:
            for vw, vh in VIEWS:
                res["arms"].append(arm("before", vw, vh))
    finally:
        res["fix_put"] = put_all("fixed")
    res["build_fixed"] = build("fixed")
    if res["build_fixed"]["rc"] == 0 and res["build_fixed"]["dist"]["files_with_fix"]:
        for vw, vh in VIEWS:
            res["arms"].append(arm("after", vw, vh))
    res["db_restored_after"] = restore()
    res["src_final"] = {rel: sha(os.path.join(WT, rel)) for rel in FILES}
    res["src_final_is_fixed"] = all(res["src_final"][rel] == f for rel, (h, f) in FILES.items())
    with open(os.path.join(HERE, "f1-design-shots.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "arms"}, ensure_ascii=False))
    for a in res["arms"]:
        print(a["arm"], a["viewport"], a.get("monitor_exit"), (a.get("badge") or {}).get("labels"), a.get("shots"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
