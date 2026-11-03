# -*- coding: utf-8 -*-
# برابریِ خروجیِ مسیرهایی که `_board_snapshot` را می‌خوانند، پیش و پس ازِ تغییرِ تجزیه‌گر.
# «ناپایدار» حدس زده نمی‌شود: دو برداشتِ پیاپی ازِ کدِ قدیم (before1/before2) هر برگی را
# که بی‌تغییرِ کد عوض می‌شود نشان می‌دهند؛ after فقط با همان برگ‌ها می‌تواند فرق کند.
#   python a1_parse_equal.py save <tag>          (رویِ ریگِ ۸۰۲۰)
#   python a1_parse_equal.py check before1 before2 after
import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8020"
DIR = os.path.join(os.environ.get("TEMP", "."), "bors_rig", "parse_equal")
UI_BODY = {"preset": "trend", "chain": [], "logic": "and", "fund_mode": "standard",
           "exceptions": {}, "drop_suffix": True}
PATHS = [
    ("funnel-post-ui", "POST", "/api/funnel", UI_BODY),
    ("funnel-get", "GET", "/api/funnel?preset=trend", None),
    ("mstat-board", "GET", "/api/mstat/board?group=eq_all&limit=60", None),
    ("mstat-mainwatch", "GET", "/api/mstat/mainwatch?group=eq_all&industry=", None),
    ("market", "GET", "/api/market", None),
]


def fetch(method, path, body):
    req = urllib.request.Request(
        BASE + urllib.parse.quote(path, safe="/?=&%,"),
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Accept-Encoding": "gzip",
                 **({"Content-Type": "application/json"} if body is not None else {})},
        method=method)
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return r.status, r.headers.get("X-Cache"), json.loads(raw.decode("utf-8"))


def leaves(o, p="$", out=None):
    out = {} if out is None else out
    if isinstance(o, dict):
        for k, v in o.items():
            leaves(v, "%s.%s" % (p, k), out)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            leaves(v, "%s[%d]" % (p, i), out)
    else:
        out[p] = repr(o)
    return out


def save(tag):
    os.makedirs(DIR, exist_ok=True)
    res = {}
    for name, method, path, body in PATHS:
        if name.startswith("funnel"):
            time.sleep(8.6)          # کشِ ۸ ثانیه‌ایِ قیف باید منقضی باشد: ساختِ واقعی
        st, xc, d = fetch(method, path, body)
        res[name] = {"status": st, "x_cache": xc}
        with open(os.path.join(DIR, "%s-%s.json" % (tag, name)), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    print(json.dumps({"tag": tag, "dir": DIR, "fetch": res}, ensure_ascii=False))


def check(b1, b2, a):
    def load(tag, name):
        with open(os.path.join(DIR, "%s-%s.json" % (tag, name)), encoding="utf-8") as f:
            return leaves(json.load(f))
    verdicts = {}
    for name, *_ in PATHS:
        L1, L2, LA = load(b1, name), load(b2, name), load(a, name)
        volatile = {k for k in set(L1) | set(L2) if L1.get(k) != L2.get(k)}
        drift = sorted(k for k in set(L1) | set(LA)
                       if k not in volatile and L1.get(k) != LA.get(k))
        verdicts[name] = {"leaves": len(L1), "volatile_in_control": len(volatile),
                          "volatile_sample": sorted(volatile)[:6],
                          "after_drift_outside_volatile": len(drift),
                          "drift_sample": drift[:10],
                          "verdict": "EQUAL" if not drift else "DATA-DIFF"}
    print(json.dumps(verdicts, ensure_ascii=False, indent=1))
    return 0 if all(v["verdict"] == "EQUAL" for v in verdicts.values()) else 1


if __name__ == "__main__":
    if sys.argv[1] == "save":
        save(sys.argv[2])
    else:
        sys.exit(check(*sys.argv[2:5]))
