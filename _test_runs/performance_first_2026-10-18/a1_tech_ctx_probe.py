# a1_tech_ctx_probe.py — آیا ساختِ کندِ «هر دقیقه یک‌بار» از تازه‌سازیِ همزمانِ _tech_context است؟
# درون‌پردازه، رویِ کپیِ pristineِ بانک؛ هیچ سرور/پورتی باز نمی‌شود.
# برای هر دور: یک ساختِ سرد با زمینهٔ تکنیکالِ تازه، یک ساختِ سرد با زمینهٔ منقضی (ts-61s)،
# و جداگانه هزینهٔ SCAN.stored / SCAN.sig_map.
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a1_switchinterval_abba import EV, WT, restore  # noqa: E402

assert restore(), "pristine copy mismatch"
os.chdir(WT)
sys.path.insert(0, WT)
os.environ["BORS_NO_FETCH_LOOPS"] = "1"

import sqlite3  # noqa: E402

from api import funnel as F  # noqa: E402
import funnel_tech_scan as SCAN  # noqa: E402
from bors_config import DB_PATH  # noqa: E402

ARGS = ("trend", [], "standard", {}, {}, True, "and")


def ms(fn):
    t = time.perf_counter()
    fn()
    return round((time.perf_counter() - t) * 1000, 1)


out = {"db": DB_PATH, "first_ctx_ms": None, "warm_build_ms": None, "rounds": []}
out["warm_build_ms"] = ms(lambda: F._run_entry(*ARGS))
for i in range(6):
    r = {}
    F._FUNNEL_CACHE.clear()
    r["build_ctx_fresh_ms"] = ms(lambda: F._run_entry(*ARGS))
    F._FUNNEL_CACHE.clear()
    F._TECH_CTX["ts"] -= 61.0
    r["build_ctx_expired_ms"] = ms(lambda: F._run_entry(*ARGS))
    F._TECH_CTX["ts"] -= 61.0
    r["ctx_refresh_ms"] = ms(F._tech_context)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        r["scan_stored_ms"] = ms(lambda: SCAN.stored(conn))
        r["sig_map_ms"] = ms(lambda: SCAN.sig_map(conn))
    finally:
        conn.close()
    out["rounds"].append(r)
    print(i, r, flush=True)
for k in out["rounds"][0]:
    v = [r[k] for r in out["rounds"]]
    out[k + "_median"] = statistics.median(v)
sizes = {"scan_symbols": len(F._TECH_CTX["scan"]), "sig_symbols": len(F._TECH_CTX["sigs"])}
out.update(sizes)
print(json.dumps({k: v for k, v in out.items() if k != "rounds"}, ensure_ascii=False))
with open(os.path.join(EV, "a1-tech-ctx-probe.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
