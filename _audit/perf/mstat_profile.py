"""PERF Stage 2 — where the seconds of the market-status panels actually go.

Measured on a throwaway copy of market.db (never the operational file), in one
process, with a SQL-timing proxy in front of the connection so every statement
is attributed. Two regimes are compared because they are not the same cost:

  (a) warm — ONE connection, snapshot already loaded (per-panel aggregation only)
  (b) real — a NEW `get_db()` connection per panel, which is exactly what every
             HTTP request does and what `/api/mstat/board` pays 16 times over

usage: PYTHONIOENCODING=utf-8 python _audit/perf/mstat_profile.py
"""
import json
import os
import re
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
os.chdir(REPO)

CACHE_DIR = os.path.join(tempfile.gettempdir(), "bors_perf_dbcopy")


def ensure_copy():
    os.makedirs(CACHE_DIR, exist_ok=True)
    dst = os.path.join(CACHE_DIR, "market.db")
    if not os.path.exists(dst):
        src = os.path.join(REPO, "market.db")
        t0 = time.perf_counter()
        s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        d = sqlite3.connect(dst)
        with s:
            s.backup(d, pages=8192)
        d.close()
        s.close()
        print(f"copied market.db -> {dst} in {time.perf_counter() - t0:.1f}s")
    u = os.path.join(CACHE_DIR, "user.db")
    if not os.path.exists(u):
        shutil.copy2(os.path.join(REPO, "user.db"), u)
    return dst, u


class Replay:
    """A cursor stand-in for a statement whose rows were already fetched."""

    def __init__(self, rows, description):
        self._rows = rows
        self._i = 0
        self.description = description

    def fetchall(self):
        out = self._rows[self._i:]
        self._i = len(self._rows)
        return out

    def fetchone(self):
        if self._i < len(self._rows):
            r = self._rows[self._i]
            self._i += 1
            return r
        return None

    def __iter__(self):
        return iter(self.fetchall())


class TimedConn:
    """Delegation shim recording the wall time and row count of every statement."""

    def __init__(self, conn):
        self._c = conn
        self.records = []

    def execute(self, sql, *a, **kw):
        t0 = time.perf_counter()
        cur = self._c.execute(sql, *a, **kw)
        rows = cur.fetchall()
        ms = (time.perf_counter() - t0) * 1000.0
        self.records.append((re.sub(r"\s+", " ", sql).strip()[:110], ms, len(rows)))
        return Replay(rows, None)

    def __getattr__(self, name):
        return getattr(self._c, name)

    def close(self):
        self._c.close()


def bucketize(records):
    agg = {}
    for sql, ms, n in records:
        a = agg.setdefault(sql[:74], [0.0, 0, 0])
        a[0] += ms
        a[1] += 1
        a[2] += n
    return sorted(({"sql": k, "ms_total": round(v[0], 2), "calls": v[1], "rows": v[2]}
                   for k, v in agg.items()), key=lambda x: -x["ms_total"])


def timeit(fn, reps=3):
    vals, out = [], None
    for _ in range(reps):
        t0 = time.perf_counter()
        out = fn()
        vals.append((time.perf_counter() - t0) * 1000.0)
    return statistics.median(vals), max(vals), out


def main():
    mpath, upath = ensure_copy()
    import mstat_engine as E
    import mstat_panels as P
    import api.market_status as MS
    import api._core as CORE
    CORE.DB_PATH = mpath
    CORE.USER_DB_PATH = upath
    MS.get_db = CORE.get_db

    print(f"DB = {mpath} ({os.path.getsize(mpath) / 1e6:.1f} MB)\n")
    res = {"db_mb": os.path.getsize(mpath) / 1e6}

    c = sqlite3.connect(mpath)
    counts = {}
    for t in ("market_watch", "instruments", "client_type", "client_type_value",
              "daily_prices", "price_history", "mstat_snap"):
        try:
            counts[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception as e:                                # noqa: BLE001
            counts[t] = f"err {e}"
    print("rows:", json.dumps(counts, ensure_ascii=False))
    res["table_rows"] = counts
    c.close()

    # Every panel called the way api/market_status.mstat_board() calls it.
    panels = [
        ("mstat.summary", lambda cn: E.summary(cn)),
        ("mstat.thermometer", lambda cn: E.thermometer(cn, "eq_all")),
        ("mstat.histogram", lambda cn: E.histogram(cn, "eq_all")),
        ("mstat.depth", lambda cn: E.depth(cn, "eq_all")),
        ("mstat.client_split", lambda cn: E.client_split(cn, "all")),
        ("mstat.mainwatch", lambda cn: E.mainwatch(cn, "eq_all", "", "clock", True, 60)),
        ("mstat.industries", lambda cn: E.industries(cn)),
        ("mstat.smart_money", lambda cn: E.smart_money(cn)),
        ("mstat.timeline", lambda cn: E.timeline(cn, "cum")),
        ("mstat.phases", lambda cn: E.phases(cn)),
        ("panels.treemap", lambda cn: P.treemap(cn, "eq_all", "", "value", 220)),
        ("panels.tops", lambda cn: P.tops(cn, "eq_all", 5)),
        ("panels.orderflows", lambda cn: P.order_book_flows(cn, "all", 10)),
        ("panels.ownership", lambda cn: P.ownership_change(cn, "all", 10)),
        ("panels.indexcards", lambda cn: P.index_cards(cn, 30)),
        ("panels.gold", lambda cn: P.gold_market(cn, 60)),
    ]

    # ---- regime (a): one connection, warm snapshot
    tc = TimedConn(CORE.get_db())
    t, mx, _ = timeit(lambda: E.load_snapshot(tc, force=True), 3)
    scan_sqls = bucketize(tc.records)
    tc.records.clear()
    print(f"\n(a) load_snapshot(force), one conn : med={t:8.1f}ms max={mx:8.1f}ms")
    res["warm"] = {"load_snapshot_ms": t, "max_ms": mx, "snapshot_sql": scan_sqls[:12]}
    print("    snapshot SQL breakdown:")
    for s in scan_sqls[:10]:
        print(f"      {s['ms_total']:8.1f}ms x{s['calls']:<2} rows={s['rows']:<7} {s['sql']}")

    t, mx, _ = timeit(lambda: E.enrich(tc), 3)
    print(f"(a) enrich() with warm snapshot    : med={t:8.1f}ms max={mx:8.1f}ms")
    res["warm"]["enrich_ms"] = t

    print("\n(a) per-panel cost with the snapshot ALREADY warm:")
    warm_sum = 0.0
    res["warm_panels"] = {}
    for name, fn in panels:
        try:
            t, mx, out = timeit(lambda: fn(tc), 3)
        except Exception as e:                                # noqa: BLE001
            print(f"      {name:<24} ERROR {type(e).__name__}: {e}")
            res["warm_panels"][name] = {"err": f"{type(e).__name__}: {e}"[:150]}
            continue
        warm_sum += t
        bad = isinstance(out, dict) and out.get("status") == "error"
        print(f"      {name:<24} med={t:8.1f}ms max={mx:8.1f}ms"
              + (f"  status=error {out.get('message')}" if bad else ""))
        res["warm_panels"][name] = {"med_ms": round(t, 1), "max_ms": round(mx, 1),
                                    "err": out.get("message") if bad else None}
    print(f"      SUM warm, one conn              {warm_sum:8.1f}ms")
    res["warm_panel_sum_ms"] = round(warm_sum, 1)
    tc.close()

    # ---- regime (b): the real request path — fresh connection per panel
    print("\n(b) same panels, a NEW get_db() connection each (what HTTP actually does):")
    res["cold_panels"] = {}
    cold_sum = 0.0
    for name, fn in panels:
        tcn = TimedConn(CORE.get_db())
        t0 = time.perf_counter()
        try:
            out = fn(tcn)
            ms = (time.perf_counter() - t0) * 1000.0
            cold_sum += ms
            bad = isinstance(out, dict) and out.get("status") == "error"
            res["cold_panels"][name] = {"med_ms": round(ms, 1),
                                        "sql": bucketize(tcn.records)[:5],
                                        "err": out.get("message") if bad else None}
            print(f"      {name:<24} {ms:8.1f}ms  stmts={len(tcn.records)}"
                  + (f"  status=error {out.get('message')}" if bad else ""))
        except Exception as e:                                # noqa: BLE001
            res["cold_panels"][name] = {"err": f"{type(e).__name__}: {e}"[:150]}
            print(f"      {name:<24} ERROR {type(e).__name__}: {e}")
        finally:
            tcn.close()
    print(f"      SUM fresh-conn                    {cold_sum:8.1f}ms")
    res["cold_panel_sum_ms"] = round(cold_sum, 1)

    # ---- the whole board route, exactly as the endpoint runs it
    t, mx, out = timeit(lambda: MS.mstat_board("eq_all", 60), 3)
    errs = [k for k, v in (out or {}).items() if isinstance(v, dict) and v.get("status") == "error"]
    print(f"\n  /api/mstat/board (fresh conn, 16 panels): med={t:8.1f}ms max={mx:8.1f}ms "
          f"panels={len(out)} errors={errs}")
    res["board"] = {"med_ms": round(t, 1), "max_ms": round(mx, 1), "errors": errs}

    # ---- _mstat_call miss vs hit
    t, mx, _ = timeit(lambda: MS._mstat_call(E.summary), 3)
    print(f"  _mstat_call(summary) miss             : med={t:8.1f}ms")
    res["mstat_call_miss_ms"] = round(t, 1)
    t, mx, _ = timeit(lambda: MS._mstat_call(E.summary), 5)
    print(f"  _mstat_call(summary) hit              : med={t:8.1f}ms")
    res["mstat_call_hit_ms"] = round(t, 1)

    # ---- pure connection cost
    def open_close():
        CORE.get_db().close()
    t, mx, _ = timeit(open_close, 7)
    print(f"  get_db() open+DDL storm, no query     : med={t:8.1f}ms")
    res["get_db_ms"] = round(t, 1)

    with open(os.path.join("_audit", "perf", "MSTAT_PROFILE.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("\nwrote _audit/perf/MSTAT_PROFILE.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
