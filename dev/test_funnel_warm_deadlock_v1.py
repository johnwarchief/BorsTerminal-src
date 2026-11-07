# dev/test_funnel_warm_deadlock_v1.py — قفلِ ساختِ قیف نباید با گرم‌کردنِ اسکرینر گره بخورد
"""اسکنِ گرمِ استارت‌آپ (`warm_screener_cache`) پیش از آنکه `_WARM_EVENT` را بزند
`_funnel_gate` → `api.funnel._run` را با همان کلیدِ پیش‌فرضِ UI صدا می‌زند. اگر
درخواستِ قیف قفلِ ساختِ همان کلید را گرفته باشد و درونِ آن منتظرِ همین رویداد
بماند، هر دو تا سقفِ `wait(timeout=300)` می‌ایستند (اسموکِ B2: POSTِ قیف ۱۸۰
ثانیه بی‌پاسخ). این گارد همان ترتیب را قطعی می‌سازد: رشتهٔ گرمِ واقعی، `_run_entry`ِ
واقعی، `_screener_cached`ِ واقعی؛ فقط بانک/تابلو/موتور جعلی‌اند و انتظار به ۱۲
ثانیه سقف دارد تا نسخهٔ معیوب هم تمام شود (نه آویزان).
"""
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import sqlite3                                    # noqa: E402

import api.funnel as F                            # noqa: E402
import api.screener as S                          # noqa: E402

PASS = FAIL = 0
WAIT_CAP_S = 12.0


def ck(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


class _Ev(threading.Event):
    """همان رویداد، با گزارشِ «کسی منتظر شد» و سقفِ انتظار."""

    def __init__(self):
        super().__init__()
        self.waiting = threading.Event()
        self.results = []

    def wait(self, timeout=None):
        self.waiting.set()
        t = WAIT_CAP_S if timeout is None else min(timeout, WAIT_CAP_S)
        r = super().wait(t)
        self.results.append(r)
        return r


ev = _Ev()
warm_started = threading.Event()
orig_cached = S._screener_cached
ROWS = [{"symbol": "نماد۱", "score": 4}]
payload_key = {}


def fake_cached():
    if threading.current_thread() is S._WARM_THREAD:
        warm_started.set()
        ev.waiting.wait(20.0)
        S._SCREENER_CACHE.update(key=payload_key["k"], payload={"data": list(ROWS)},
                                 ts=time.time())
        return S._SCREENER_CACHE["payload"]
    return orig_cached()


class _FE:
    @staticmethod
    def evaluate(board, screen, **kw):
        return {"status": "success", "stages": {}, "status_matrix": {},
                "trace": {}, "screened_rows": len(screen)}


tmp = tempfile.mkdtemp(prefix="bors_deadlock_")
saved = {
    (S, "_screener_cached"): S._screener_cached,
    (S, "_WARM_EVENT"): S._WARM_EVENT,
    (S, "CACHE_FILE"): S.CACHE_FILE,
    (S, "get_db"): S.get_db,
    (S, "load_fts_config"): S.load_fts_config,
    (S, "_apply_assembly_veto"): S._apply_assembly_veto,
    (F, "_board_snapshot"): F._board_snapshot,
    (F, "_tech_context"): F._tech_context,
    (F, "_universe_priority"): F._universe_priority,
    (F, "_universe_status"): F._universe_status,
    (F, "FE"): F.FE,
}
try:
    S._screener_cached = fake_cached
    S._WARM_EVENT = ev
    S.CACHE_FILE = os.path.join(tmp, "absent.json")
    S.get_db = lambda: sqlite3.connect(":memory:")
    S.load_fts_config = lambda: {}
    S._apply_assembly_veto = lambda rows: rows
    payload_key["k"] = "%s#v%s" % ("{}", S.APP_VERSION)
    S._SCREENER_CACHE.update(key=None, payload=None, ts=0.0)
    F._board_snapshot = lambda: ([{"symbol": "نماد۱"}], 20261018)
    F._tech_context = lambda max_age_s=60.0: ({}, {})
    F._universe_priority = lambda: {}
    F._universe_status = lambda: {}
    F.FE = _FE
    F._FUNNEL_CACHE.clear()

    warm = threading.Thread(target=S.warm_screener_cache, name="warm", daemon=True)
    warm.start()
    ck("رشتهٔ گرم به اسکن رسید", warm_started.wait(10.0))

    out = {}

    def request():
        t0 = time.perf_counter()
        out["res"] = F._run("trend", [], "standard", {}, {}, full=True)
        out["ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    req = threading.Thread(target=request, name="funnel-request", daemon=True)
    req.start()
    req.join(WAIT_CAP_S + 20)
    warm.join(WAIT_CAP_S + 20)
    total_ms = (time.perf_counter() - t0) * 1000

    ck("هر دو رشته تمام شدند", not req.is_alive() and not warm.is_alive())
    ck("درخواستِ قیف منتظرِ رویدادِ گرم شد (سناریو واقعاً ساخته شد)", bool(ev.results),
       ev.results)
    ck("انتظارِ درخواست با پایانِ گرم تمام شد، نه با timeout",
       ev.results[:1] == [True], f"wait() → {ev.results}")
    ck("کلِ ماجرا زیرِ سقفِ انتظار ماند", total_ms < WAIT_CAP_S * 1000 * 0.5,
       f"{total_ms:.0f}ms")
    res = out.get("res") or {}
    ck("پاسخِ قیف موفق و با ردیف‌هایِ همان اسکن",
       res.get("status") == "success" and res.get("screened_rows") == len(ROWS), res)
    ck("یک ساخت برای کلید (یکی ساخت، دیگری از کش)",
       len(F._FUNNEL_CACHE) == 1, list(F._FUNNEL_CACHE))
    print(f"  total {total_ms:.0f}ms  request {out.get('ms', -1):.0f}ms  wait→{ev.results}")
finally:
    ev.set()
    for (mod, name), val in saved.items():
        setattr(mod, name, val)
    S._SCREENER_CACHE.update(key=None, payload=None, ts=0.0)
    F._FUNNEL_CACHE.clear()

print(f"\nfunnel_warm_deadlock_v1: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
