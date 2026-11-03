# tools/mstat_cache_benchmark.py — بنچمارکِ سه‌حالۀ لایۀ کشِ «وضعیت بازار»

"""رأیِ مالک (۱۴۰۵-۰۷-۲۸، گزینهٔ C): پویشِ مشترکِ حالتِ بانکِ System 1 حفظ می‌شود و
یک‌اتصال‌بودنِ System 2 (PERF-S3) رویش سوار می‌شود — «اما برتریِ عملکردی فقط پس از
بنچمارک معتبر پذیرفته می‌شود و سنجش‌های مأموریتِ پرفورمنسِ System 2 مبنایِ اصلی
مقایسه‌اند». بی‌این فایل، آن برتری یک ادعاست.

سه نسخۀ `api/market_status.py` ازِ تاریخچۀ git بیرون کشیده می‌شوند و هر سه با
ورودیِ یکسان سنجیده می‌شوند:

  s1        System 1 (`_mstat_state()` + stale-while-revalidate + تک‌پروازگی)
  s2        System 2 (`_mstat_call()` با نشانک روی همان اتصال پنل، بی‌stale و بی‌قفل)
  combined  نسخۀ ادغام‌شده (گزینهٔ C)

سنجش‌ها: کارنامه (p50/p95/p99 سر‌سرد و گرم)، شمارِ `get_db()`، شمارِ فراخوانیِ
موتور (محاسبۀِ تکراری)، هم‌زمانیِ شش‌تایی رویِ یکِ کلیدِ سرد، invalidation (جابه‌ja
شدنِ نشانۀ بانک ⇒ بازسازی)، و تازگی پس ازِ سوختنِ ttl (همان نقطه‌ای که System 1
را ۲٬۵۷۰ms می‌کرد). بدنهٔ پاسخ هم مقایسه می‌شود.

هر نسخۀ module درِ یکِ namespace جدا import می‌شود و شمارنده‌ها باِ wrapper روی
`get_db` و توابعِ موتورِ همان namespace می‌نشینند؛ هیچ فایلِ تولیدی عوض نمی‌شود.

فرمان:
    PYTHONIOENCODING=utf-8 python tools/mstat_cache_benchmark.py
خروجی:
    جدولِ فارسی رویِ stdout + `_audit/perf/MSTAT_CACHE_BENCH.json`
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT_JSON = os.path.join(ROOT, "_audit", "perf", "MSTAT_CACHE_BENCH.json")

DEFAULT_REFS = {
    "s1": "s12-premerge-checkpoint:api/market_status.py",
    "s2": "9594c7ff:api/market_status.py",
    "combined": None,            # همان فایلِ کارِ جاری (ادغام‌شدۀ حل‌شده)
}

#: پنل‌هایی که هر سه نسخّه دارند (بدنه‌هایِ مشترک؛ مقایسه‌پذیر).
SHARED_PANELS = ("summary", "thermometer", "histogram", "depth", "clientsplit",
                 "mainwatch", "industries", "smartmoney", "timeline", "phases")


def _load(ref: str | None, name: str):
    """یک نسخۀ module را درِ namespaceِ خودش بالا می‌آورد.

    فایلِ اصلی `from ._core import get_db` است، پس نسخه‌ها باید درونِ همان
    بستۀ `api` اجرا شوند — تنها تفاوت، نامِ ماژول است تا کشِ هر نسخه جدا بماند.
    """
    import api  # noqa: F401  (بستۀ میزبان برایِ import نسبی لازم است)
    if ref is None:
        path = os.path.join(ROOT, "api", "market_status.py")
        src = open(path, encoding="utf-8").read()
    else:
        src = subprocess.run(["git", "-C", ROOT, "show", ref], capture_output=True,
                             check=True, text=True, encoding="utf-8").stdout
    mod_name = "api.mstat_variant_" + name
    mod = type(sys)(mod_name)
    mod.__dict__["__file__"] = os.path.join(ROOT, "api", "market_status.py")
    mod.__dict__["__name__"] = mod_name
    mod.__dict__["__package__"] = "api"
    code = compile(src + "\n# variant: %s (%s)" % (name, ref or "working-tree"),
                   "<mstat_variant_%s>" % name, "exec")
    sys.modules[mod_name] = mod
    exec(code, mod.__dict__)
    return mod


class Probe:
    """شمارندۀ اتصال و شمارندۀ محاسبۀ موتور، بدونِ دست‌زدن به فایلِ تولیدی."""

    def __init__(self, mod):
        self.mod = mod
        self.conns = 0
        self.engine_calls = 0
        self._orig_get_db = mod.get_db
        self._patched = {}
        self._wrap_engine(mod)

    def _wrap_engine(self, mod):
        # هر تابعِ موتورِ که پنل‌ها صدا می‌زنند شمارش می‌شود؛ «یکِ حالتِ بانک دو بار
        # ساخته می‌شود؟» فقط باِ همین عدد جواب می‌گیرد.
        for holder_name in ("_mstat", "_panels"):
            holder = getattr(mod, holder_name, None)
            if holder is None:
                continue
            for attr in dir(holder):
                if attr.startswith("_"):
                    continue
                fn = getattr(holder, attr)
                if not callable(fn):
                    continue
                probe = self

                def make(f):
                    def wrapped(*a, **kw):
                        probe.engine_calls += 1
                        return f(*a, **kw)
                    return wrapped
                self._patched[(holder_name, attr)] = fn
                setattr(holder, attr, make(fn))

    def install(self):
        probe = self

        def counted_get_db():
            probe.conns += 1
            return probe._orig_get_db()

        self.mod.get_db = counted_get_db
        return self

    def reset(self):
        self.conns = 0
        self.engine_calls = 0

    def restore(self):
        self.mod.get_db = self._orig_get_db
        for holder_name in ("_mstat", "_panels"):
            holder = getattr(self.mod, holder_name, None)
            if holder is None:
                continue
            for (hn, attr), f in self._patched.items():
                if hn == holder_name:
                    setattr(holder, attr, f)


def _pct(values, q):
    if not values:
        return None
    s = sorted(values)
    i = min(len(s) - 1, max(0, int(round((q / 100.0) * (len(s) - 1)))))
    return round(s[i], 2)


def _profile(fn, n=25, warmup=3):
    for _ in range(warmup):
        fn()
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000.0)
    return {"p50": _pct(ts, 50), "p95": _pct(ts, 95), "p99": _pct(ts, 99),
            "mean": round(statistics.fmean(ts), 2), "n": len(ts)}


def measure(name, ref, group="eq_all", limit=60):
    mod = _load(ref, name)
    probe = Probe(mod).install()
    res = {"variant": name, "ref": ref or "working-tree"}
    try:
        mod._MSTAT_CACHE.clear()
        probe.reset()
        t0 = time.perf_counter()
        cold_body = mod.mstat_board(group, limit)
        res["board_cold_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        res["board_cold_conns"] = probe.conns
        res["board_cold_engine_calls"] = probe.engine_calls

        probe.reset()
        res["board_warm"] = _profile(lambda: mod.mstat_board(group, limit), n=25)
        res["board_warm_conns_per_call"] = round(probe.conns / 28.0, 3)
        res["board_warm_engine_calls"] = probe.engine_calls
        res["board_body_shared_keys"] = sorted(k for k in (cold_body or {}) if k in SHARED_PANELS)

        # تنها پنلِ سردِ تک‌پنلی (همان مسیری که UI همراه تب می‌زند)
        probe.reset()
        mod._MSTAT_CACHE.clear()
        t0 = time.perf_counter()
        mod.mstat_summary()
        res["summary_cold_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        res["summary_cold_conns"] = probe.conns
        res["summary_cold_engine_calls"] = probe.engine_calls

        # هم‌زمانی: شش رشته روی یکِ کلیدِ سرد
        mod._MSTAT_CACHE.clear()
        probe.reset()
        errs = []

        def worker():
            try:
                mod.mstat_thermometer("all")
            except Exception as e:  # noqa: BLE001
                errs.append(str(e)[:80])

        ths = [threading.Thread(target=worker) for _ in range(6)]
        t0 = time.perf_counter()
        for t in ths:
            t.start()
        for t in ths:
            t.join(timeout=120)
        res["concurrent_6_wall_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        res["concurrent_6_engine_calls"] = probe.engine_calls
        res["concurrent_6_conns"] = probe.conns
        res["concurrent_errors"] = errs[:2]

        # invalidation: نشاندۀ بانک جابه‌جا می‌شود ⇒ هیچِ نتیجه‌ای از کشِ قبلی نمی‌ماند
        mod._MSTAT_CACHE.clear()
        real_rev = mod._MS.revision

        def bump_rev():
            bump_rev.n += 1
            return "rev-%d" % bump_rev.n

        bump_rev.n = 0
        mod._MS.revision = bump_rev
        try:
            probe.reset()
            for _ in range(4):
                mod.mstat_histogram("all")
            res["invalidation_engine_calls_4_states"] = probe.engine_calls
            res["invalidation_cached_entries"] = len(mod._MSTAT_CACHE)
        finally:
            mod._MS.revision = real_rev

        # تازگی: کش عمداً کهنه می‌شود (پیشِ زمانِ ttl) و پاسخِ بعدی سنجیده می‌شود
        mod._MSTAT_CACHE.clear()
        mod._MS.revision = real_rev
        mod.mstat_industries()
        for k in list(mod._MSTAT_CACHE):
            ts, out = mod._MSTAT_CACHE[k]
            mod._MSTAT_CACHE[k] = (ts - float(mod._MSTAT_TTL_S) - 1.0, out)
        probe.reset()
        t0 = time.perf_counter()
        out_after = mod.mstat_industries()
        res["after_ttl_expiry_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        res["after_ttl_expiry_served_stale"] = bool(
            isinstance(out_after, dict) and out_after.get("status") == "ok")
        res["after_ttl_expiry_engine_calls"] = probe.engine_calls
        res["ttl_s"] = getattr(mod, "_MSTAT_TTL_S", None)
        res["stale_max_s"] = getattr(mod, "_MSTAT_STALE_MAX_S", None)
        res["board_body"] = cold_body
    finally:
        probe.restore()
    return res


def report(rows):
    print("\n═══ بنچمارکِ سه‌حالۀ کشِ «وضعیت بازار» ═══\n")
    hdr = ("سنجش", "s1", "s2", "ترکیبی")
    keys = (("board_cold_ms", "تب — سر‌سرد (ms)"),
            ("board_cold_conns", "تب — اتصال درِ سر‌سرد"),
            ("board_cold_engine_calls", "تب — محاسبۀ موتور درِ سر‌سرد"),
            ("board_warm_conns_per_call", "تب — اتصال به‌ازای درخواستِ گرم"),
            ("summary_cold_conns", "پنلِ تنها — اتصال درِ سر‌سرد"),
            ("concurrent_6_engine_calls", "شش رشتهٔ هم‌زمان — محاسبۀ موتور"),
            ("concurrent_6_wall_ms", "شش رشتهٔ هم‌زمان — زمانِ دیوار (ms)"),
            ("invalidation_engine_calls_4_states", "invalidation — بازسازی درِ چهار حالت"),
            ("invalidation_cached_entries", "invalidation — شمارِ رکوردِ کش"),
            ("after_ttl_expiry_ms", "پس ازِ سوختنِ ttl (ms)"),
            ("after_ttl_expiry_served_stale", "پس ازِ سوختنِ ttl — کهنه سرو شد؟"),
            ("ttl_s", "ttl (ثانیه)"), ("stale_max_s", "سقفِ کهنه (ثانیه)"))
    by = {r["variant"]: r for r in rows}
    print("| %s | %s | %s | %s |" % hdr)
    print("| --- | --- | --- | --- |")
    for k, label in keys:
        vals = []
        for v in ("s1", "s2", "combined"):
            got = by.get(v, {}).get(k)
            if isinstance(got, dict):
                got = got.get("p50")
            vals.append("—" if got is None else str(got))
        print("| %s | %s | %s | %s |" % (label, *vals))
    print("\n" + "| warm p50/p95/p99 (ms) | " +
          " | ".join("%s: %s/%s/%s" % (v, by.get(v, {}).get("board_warm", {}).get("p50"),
                                        by.get(v, {}).get("board_warm", {}).get("p95"),
                                        by.get(v, {}).get("board_warm", {}).get("p99"))
                     for v in ("s1", "s2", "combined")) + " |")
    sets = {r["variant"]: set(r.get("_body_keys") or []) for r in rows}
    base = sets.get("combined") or set()
    print("\nبرابریِ بدنهٔ /api/mstat/board (مجموعۀ کلیدها):")
    for v in ("s1", "s2"):
        other = sets.get(v) or set()
        print("  %s: %d کلید | غایب درِ ترکیبی: %s | تازه درِ ترکیبی: %s"
              % (v, len(other), sorted(base - other) or "هیچ", sorted(other - base) or "هیچ"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs-json", help="{'s1':'ref:path','s2':'ref:path'} برایِ تکرارِ سنجش رویِ SHAهایِ دیگر")
    ap.add_argument("--one", choices=tuple(DEFAULT_REFS), help="فقط یکِ نسخّه درِ همین فرآیند (حالتِ فرزند)")
    ap.add_argument("--out", help="جایِ نوشتنِ JSON درِ حالتِ فرزند")
    args = ap.parse_args()
    refs = dict(DEFAULT_REFS)
    if args.refs_json:
        refs.update(json.loads(args.refs_json))

    if args.one:
        row = measure(args.one, refs.get(args.one))
        body = row.pop("board_body", None)
        payload = {"variant": args.one, "row": row,
                   "board_body_keys": sorted(body or {})}
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        return 0

    rows = []
    for name in ("s1", "s2", "combined"):
        # هر نسخّه درِ فرآیندِ تازه: `mstat_engine` هم کشِ درونی دارد، پس سنجشِ
        # «سر‌سرد» درِ یکِ فرآیندِ مشترک به سودِ نسخۀ آخر دروغ می‌گفت (دورِ اولِ
        # همینBenchmark ترتیب را به عدد نشان داد: ۱٬۹۰۵ → ۵۰۵ → ۱۹۵ ms).
        tmp = os.path.join(ROOT, "_audit", "perf", "mstat_bench_%s.json" % name)
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        t0 = time.time()
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.abspath(__file__),
                            "--one", name, "--out", tmp],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=1800)
        if r.returncode != 0 or not os.path.exists(tmp):
            print("[mstat-bench] نسخۀ %s اجرا نشد rc=%s\n%s" % (name, r.returncode,
                                                                (r.stderr or "")[-600:]))
            return 1
        got = json.load(open(tmp, encoding="utf-8"))
        got["row"]["wall_s"] = round(time.time() - t0, 1)
        rows.append(dict(got["row"], _body_keys=got["board_body_keys"]))
        print("[mstat-bench] %s سنجیده شد" % name, flush=True)
    report(rows)
    slim = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump({"git_sha": subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                                             capture_output=True, text=True).stdout.strip(),
                   "refs": {k: (v or "working-tree") for k, v in refs.items()},
                   "panel_keys": {r["variant"]: r.get("_body_keys") for r in rows},
                   "rows": slim}, fh, ensure_ascii=False, indent=1)
    print("\n[mstat-bench] نوشته شد: " + OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
