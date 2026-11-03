"""PERF Stage 1b-A — cost of ONE SQLite connection (the `get_db()` ladder).

`api/_core.get_db()` rebuilds the entire connection setup on every request:
5 PRAGMAs, an engine import + SQL-function registration, 2 CREATE INDEX IF NOT
EXISTS, ensure_market_schema, ensure_selection_schema, watchlist_store.ensure_table
and mstat_engine.ensure_schema. `get_user_db()` then adds a second connection to
*market.db* plus two SELECTs for the one-off migration probe.

This script measures each rung separately, on a throwaway copy of the databases,
so the operational market.db is never opened for writing.

usage: PYTHONIOENCODING=utf-8 python _audit/perf/sqlite_conn_probe.py --iters 15
"""
import argparse
import ctypes
import ctypes.wintypes
import gc
import importlib.util
import json
import os
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
os.chdir(REPO)


class _PMC(ctypes.Structure):
    _fields_ = [("cb", ctypes.wintypes.DWORD), ("PageFaultCount", ctypes.wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


_MEMFN = None
_HANDLE = None


def _memfn():
    global _MEMFN, _HANDLE
    if _MEMFN is not None:
        return _MEMFN
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
    _HANDLE = k32.GetCurrentProcess()
    for dll, fname in ((k32, "K32GetProcessMemoryInfo"),
                       (ctypes.windll.psapi, "GetProcessMemoryInfo")):
        try:
            f = getattr(dll, fname)
        except AttributeError:
            continue
        f.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(_PMC), ctypes.wintypes.DWORD]
        f.restype = ctypes.wintypes.BOOL
        _MEMFN = f
        return f
    return False


def mem():
    f = _memfn() if os.name == "nt" else False
    if not f:
        return {"ws": 0, "priv": 0, "peak_ws": 0}
    p = _PMC()
    p.cb = ctypes.sizeof(p)
    if not f(_HANDLE, ctypes.byref(p), p.cb):
        return {"ws": 0, "priv": 0, "peak_ws": 0}
    return {"ws": p.WorkingSetSize, "priv": p.PagefileUsage, "peak_ws": p.PeakWorkingSetSize}


def percentile(vals, q):
    if not vals:
        return float("nan")
    s = sorted(vals)
    return s[min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))]


def copy_dbs(dst_dir):
    """Consistent, checkpointed copies via the sqlite backup API (never touches sources)."""
    out = {}
    for name in ("market.db", "user.db"):
        src = os.path.join(REPO, name)
        if not os.path.exists(src):
            continue
        dst = os.path.join(dst_dir, name)
        s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        d = sqlite3.connect(dst)
        with s:
            s.backup(d, pages=8192)
        d.close()
        s.close()
        out[name] = dst
    return out


def load_core(market_path, user_path):
    spec = importlib.util.spec_from_file_location("perf_core", os.path.join(REPO, "api", "_core.py"))
    core = importlib.util.module_from_spec(spec)
    sys.modules["perf_core"] = core
    spec.loader.exec_module(core)
    core.DB_PATH = market_path
    core.USER_DB_PATH = user_path
    return core


def ladder(core, iters):
    """Time every rung of get_db() the same order and on the same connection."""
    import watchlist_store
    import mstat_engine

    steps = []

    def add(name, fn):
        steps.append((name, fn))

    def open_conn(st):
        st["conn"] = sqlite3.connect(core.DB_PATH, timeout=30)
    add("sqlite3.connect", open_conn)
    add("row_factory", lambda st: setattr(st["conn"], "row_factory", sqlite3.Row))
    add("PRAGMA journal_mode=WAL", lambda st: st["conn"].execute("PRAGMA journal_mode=WAL"))
    add("PRAGMA synchronous=NORMAL", lambda st: st["conn"].execute("PRAGMA synchronous=NORMAL"))
    add("PRAGMA cache_size=-64000", lambda st: st["conn"].execute("PRAGMA cache_size=-64000"))
    add("PRAGMA temp_store=MEMORY", lambda st: st["conn"].execute("PRAGMA temp_store=MEMORY"))
    add("PRAGMA mmap_size=256MB", lambda st: st["conn"].execute("PRAGMA mmap_size=268435456"))

    def reg(st):
        import importlib
        mod = importlib.import_module("fts_engine")
        mod.register_sql(st["conn"])
    add("import fts_engine + register_sql", reg)
    add("2x CREATE INDEX IF NOT EXISTS", lambda st: (
        st["conn"].execute("CREATE INDEX IF NOT EXISTS ix_ct_ins_deven ON client_type(ins_code, d_even)"),
        st["conn"].execute("CREATE INDEX IF NOT EXISTS ix_ph_sym_date2 ON price_history(symbol, date DESC)")))
    add("ensure_market_schema", lambda st: core.ensure_market_schema(st["conn"]))
    add("ensure_selection_schema", lambda st: core.ensure_selection_schema(st["conn"]))
    add("watchlist_store.ensure_table", lambda st: watchlist_store.ensure_table(st["conn"]))
    add("mstat_engine.ensure_schema", lambda st: mstat_engine.ensure_schema(st["conn"]))

    acc = {name: [] for name, _ in steps}
    err = {}
    for i in range(iters):
        st = {"conn": None}
        for name, fn in steps:
            t0 = time.perf_counter()
            try:
                fn(st)
            except Exception as e:                          # noqa: BLE001
                err[name] = f"{type(e).__name__}: {e}"
            acc[name].append((time.perf_counter() - t0) * 1000.0)
        if st["conn"]:
            st["conn"].close()
    return acc, err


def whole_get_db(core, iters):
    ms = []
    for _ in range(iters):
        t0 = time.perf_counter()
        c = core.get_db()
        ms.append((time.perf_counter() - t0) * 1000.0)
        c.close()
    return ms


def whole_get_user_db(core, iters):
    ms = []
    for _ in range(iters):
        t0 = time.perf_counter()
        c = core.get_user_db()
        ms.append((time.perf_counter() - t0) * 1000.0)
        c.close()
    return ms


def both_apis(core, iters):
    """The realistic single-request cost: most endpoints call get_db() and get_user_db()."""
    ms = []
    for _ in range(iters):
        t0 = time.perf_counter()
        a = core.get_db()
        b = core.get_user_db()
        ms.append((time.perf_counter() - t0) * 1000.0)
        a.close()
        b.close()
    return ms


def held_connections(core, n):
    """Memory of n connections opened with the current get_db() settings, held open at once."""
    gc.collect()
    base = mem()
    conns = []
    for _ in range(n):
        conns.append(core.get_db())
    after = mem()
    # touch a real query so the page cache actually allocates
    c = conns[0]
    c.execute("SELECT COUNT(*) FROM daily_prices").fetchone()
    used = mem()
    for x in conns:
        x.close()
    gc.collect()
    return {"n": n, "base_ws_kb": base["ws"] // 1024, "after_ws_kb": after["ws"] // 1024,
            "query_ws_kb": used["ws"] // 1024,
            "base_priv_kb": base["priv"] // 1024, "after_priv_kb": after["priv"] // 1024}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=15)
    ap.add_argument("--keep", action="store_true", help="keep the temp copy for inspection")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="bors_perf_")
    print(f"temp db copy dir: {tmp}")
    t0 = time.perf_counter()
    copies = copy_dbs(tmp)
    print(f"copy done in {time.perf_counter() - t0:.1f}s -> "
          + ", ".join(f"{k} {os.path.getsize(v) / 1e6:.1f}MB" for k, v in copies.items()))

    core = load_core(copies["market.db"], copies.get("user.db", copies["market.db"]))
    print(f"DB_PATH={core.DB_PATH}\nUSER_DB_PATH={core.USER_DB_PATH}")

    res = {"iters": args.iters, "db_mb": os.path.getsize(copies["market.db"]) / 1e6}

    print("\n=== get_db() ladder — per-rung cost (median / p95 / max, ms) ===")
    acc, err = ladder(core, args.iters)
    total = 0.0
    for name, vals in acc.items():
        med = statistics.median(vals)
        total += med
        line = (f"  {name:<34} med={med:7.2f}  p95={percentile(vals, 0.95):7.2f} "
                f"max={max(vals):8.2f}  min={min(vals):6.2f}")
        if err.get(name):
            line += f"   ERR {err[name]}"
        print(line)
        res.setdefault("ladder", {})[name] = {"med_ms": med, "p95_ms": percentile(vals, 0.95),
                                              "max_ms": max(vals), "min_ms": min(vals),
                                              "err": err.get(name)}
    print(f"  {'SUM of medians':<34} {total:7.2f} ms")
    res["ladder_sum_med_ms"] = total

    g = whole_get_db(core, args.iters)
    print(f"\n  full get_db()            med={statistics.median(g):7.2f} p95={percentile(g, 0.95):7.2f} "
          f"min={min(g):6.2f} max={max(g):8.2f}")
    res["get_db"] = {"med_ms": statistics.median(g), "p95_ms": percentile(g, 0.95),
                     "min_ms": min(g), "max_ms": max(g)}
    u = whole_get_user_db(core, args.iters)
    print(f"  full get_user_db()       med={statistics.median(u):7.2f} p95={percentile(u, 0.95):7.2f} "
          f"min={min(u):6.2f} max={max(u):8.2f}")
    res["get_user_db"] = {"med_ms": statistics.median(u), "p95_ms": percentile(u, 0.95),
                          "min_ms": min(u), "max_ms": max(u)}
    b = both_apis(core, args.iters)
    print(f"  get_db + get_user_db     med={statistics.median(b):7.2f} p95={percentile(b, 0.95):7.2f} "
          f"(what a typical request pays before any query)")
    res["both"] = {"med_ms": statistics.median(b), "p95_ms": percentile(b, 0.95),
                   "min_ms": min(b), "max_ms": max(b)}

    print("\n=== memory of held connections (get_db settings, per process) ===")
    for n in (1, 2, 4, 8):
        m = held_connections(core, n)
        print(f"  n={n:<3} WS {m['base_ws_kb']:>9,} -> {m['after_ws_kb']:>9,} KB "
              f"(after query {m['query_ws_kb']:>9,})   private {m['base_priv_kb']:>9,} -> {m['after_priv_kb']:>9,} KB")
        res.setdefault("conn_memory", {})[n] = m

    with open(os.path.join("_audit", "perf", "SQLITE_CONN_BASELINE.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("\nwrote _audit/perf/SQLITE_CONN_BASELINE.json")

    if args.keep:
        print(f"temp copy kept at {tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
