# a1_tech_ctx_after_probe.py — پس از refresh-aheadِ _tech_context (درون‌پردازه، بانکِ pristine، بی‌پورت).
# سه پرسش:
#   ۱. سنِ ۳۰-۵۹s: ساخت سریع می‌ماند، نخِ پس‌زمینه یک‌بار راه می‌افتد و ts تازه می‌شود؟
#   ۲. سنِ ≥۶۰s: همان مسیرِ همزمانِ قبلی (هزینه ≈ before-probe) — قرارداد عوض نشده؟
#   ۳. نخِ پس‌زمینه GIL را نگه می‌دارد؟ دیرکردِ sleep(1ms)ِ نخِ اصلی درِ حینِ آن،
#      در برابرِ پایه (بی‌نخ) و کنترلِ مثبت (json.loads بزرگ درِ نخ = نگه‌داشتنِ GIL).
#   ۴. payloadِ ساخته‌شده با زمینهٔ همزمان = با زمینهٔ پس‌زمینه (جز کلیدهایِ ساعت)؟
import json
import os
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a1_switchinterval_abba import EV, WT, restore  # noqa: E402

assert restore(), "pristine copy mismatch"
os.chdir(WT)
sys.path.insert(0, WT)
os.environ["BORS_NO_FETCH_LOOPS"] = "1"

from api import funnel as F  # noqa: E402

ARGS = ("trend", [], "standard", {}, {}, True, "and")
CLOCK_KEYS = {"as_of", "cached_for_ms", "elapsed_ms", "timing", "built_at", "computed_at"}


def ms(fn):
    t = time.perf_counter()
    r = fn()
    return round((time.perf_counter() - t) * 1000, 1), r


def bg_threads():
    return [t for t in threading.enumerate() if t.name == "funnel-tech-ctx"]


def join_bg():
    t0 = time.perf_counter()
    for t in bg_threads():
        t.join(30)
    return round((time.perf_counter() - t0) * 1000, 1)


def lateness_while(cond, tick=0.001):
    lates = []
    while cond():
        t = time.perf_counter()
        time.sleep(tick)
        lates.append((time.perf_counter() - t - tick) * 1000)
    if not lates:
        return None
    lates.sort()
    return {"n": len(lates), "median_ms": round(statistics.median(lates), 2),
            "p95_ms": round(lates[int(0.95 * (len(lates) - 1))], 2), "max_ms": round(lates[-1], 2)}


def diff_paths(a, b, path="$", out=None):
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(path + "." + str(k))
            else:
                diff_paths(a[k], b[k], path + "." + str(k), out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            diff_paths(x, y, "%s[%d]" % (path, i), out)
    elif a != b:
        out.append(path)
    return out


out = {"db_pristine": True, "rounds": []}
out["warm_build_ms"], _ = ms(lambda: F._run_entry(*ARGS))
join_bg()

for i in range(6):
    r = {}
    # ۱. سنِ ۳۵s ⇒ ساختِ سریع + یک نخِ پس‌زمینه
    F._FUNNEL_CACHE.clear()
    F._TECH_CTX["ts"] = time.time() - 35.0
    old_ts = F._TECH_CTX["ts"]
    r["build_age35_ms"], (p_bg_parent, _, built) = ms(lambda: F._run_entry(*ARGS))
    r["bg_threads_after_build"] = len(bg_threads())
    r["bg_join_wait_ms"] = join_bg()
    r["ts_refreshed"] = F._TECH_CTX["ts"] > old_ts + 30
    r["ctx_age_after_s"] = round(time.time() - F._TECH_CTX["ts"], 2)
    # ۲. سنِ ۴۵s دو فراخوانِ پیاپی ⇒ فقط یک نخ (single-flight)
    F._TECH_CTX["ts"] = time.time() - 45.0
    F._tech_context()
    F._tech_context()
    r["bg_threads_two_calls"] = len(bg_threads())
    join_bg()
    # ۳. سنِ ۶۱s ⇒ مسیرِ همزمانِ قبلی
    F._FUNNEL_CACHE.clear()
    F._TECH_CTX["ts"] = time.time() - 61.0
    r["build_age61_ms"], (p_sync, _, _) = ms(lambda: F._run_entry(*ARGS))
    r["bg_threads_after_sync"] = len(bg_threads())
    # ۴. برابریِ payload: زمینهٔ همزمان (همین الان) در برابرِ زمینهٔ پس‌زمینه
    F._FUNNEL_CACHE.clear()
    F._TECH_CTX["ts"] = time.time() - 35.0
    F._tech_context()
    join_bg()
    F._FUNNEL_CACHE.clear()
    _, (p_bg, _, _) = ms(lambda: F._run_entry(*ARGS))
    join_bg()
    d = diff_paths(p_sync, p_bg)
    r["payload_diff_paths"] = d[:20]
    r["payload_diff_non_clock"] = [p for p in d if not any(("." + k) in p for k in CLOCK_KEYS)][:20]
    out["rounds"].append(r)
    print(i, {k: v for k, v in r.items() if k != "payload_diff_paths"}, flush=True)

# ۵. دیرکردِ نخِ اصلی: پایه / حینِ refreshِ پس‌زمینه / کنترلِ مثبتِ نگه‌دارندهٔ GIL
gil = {"baseline": [], "during_bg_refresh": [], "control_json_loads": []}
big = json.dumps([{"a": i, "b": str(i), "c": [i, i + 1]} for i in range(400_000)])
for i in range(4):
    t_end = time.perf_counter() + 1.3
    gil["baseline"].append(lateness_while(lambda: time.perf_counter() < t_end))
    F._TECH_CTX["ts"] = time.time() - 35.0
    F._tech_context()
    gil["during_bg_refresh"].append(lateness_while(lambda: bool(bg_threads())))
    th = threading.Thread(target=lambda: [json.loads(big) for _ in range(3)], name="ctl")
    th.start()
    gil["control_json_loads"].append(lateness_while(th.is_alive))
    th.join()
out["gil_lateness"] = gil
print(json.dumps(gil, ensure_ascii=False), flush=True)

for k in ("build_age35_ms", "build_age61_ms", "bg_join_wait_ms"):
    out[k + "_median"] = statistics.median(r[k] for r in out["rounds"])
for k in ("baseline", "during_bg_refresh", "control_json_loads"):
    out["gil_" + k + "_max_ms_median"] = statistics.median(x["max_ms"] for x in gil[k])
summary = {k: v for k, v in out.items() if k not in ("rounds", "gil_lateness")}
summary["all_ts_refreshed"] = all(r["ts_refreshed"] for r in out["rounds"])
summary["single_flight_ok"] = all(r["bg_threads_two_calls"] <= 1 for r in out["rounds"])
summary["no_bg_on_sync_path"] = all(r["bg_threads_after_sync"] == 0 for r in out["rounds"])
summary["payload_non_clock_diffs"] = sorted({p for r in out["rounds"] for p in r["payload_diff_non_clock"]})
out.update(summary)
print(json.dumps(summary, ensure_ascii=False), flush=True)
with open(os.path.join(EV, "a1-tech-ctx-after-probe.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
