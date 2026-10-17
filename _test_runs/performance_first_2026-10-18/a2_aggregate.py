# A2: جمع‌بندیِ ABBA ازِ خودِ فایل‌هایِ دور (بی‌رقمِ دست‌نویس). حکم فقط با جدایی کاملِ بازه‌هایِ میانهٔ دورها.
import glob
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 1)


def summ(xs):
    return {"n": len(xs), "median": pct(xs, 0.5), "p95": pct(xs, 0.95), "max": round(max(xs), 1) if xs else None}


def verdict(a, b, lower_better=True):
    """a/b = فهرستِ مقدارِ هر دور. جدایی کامل ⇒ برنده؛ هم‌پوشانی ⇒ INCONCLUSIVE."""
    if not a or not b:
        return "NOT_RUN"
    if max(a) < min(b):
        return "A_BETTER" if lower_better else "B_BETTER"
    if max(b) < min(a):
        return "B_BETTER" if lower_better else "A_BETTER"
    return "INCONCLUSIVE"


def cli():
    rounds = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(os.path.join(HERE, "a2", "round-*.json")))]
    arms = {"A": [r for r in rounds if r["arm"] == "A"], "B": [r for r in rounds if r["arm"] == "B"]}
    out = {"order": "".join(r["arm"] for r in rounds), "db_pristine_all": all(r["db_pristine"] for r in rounds),
           "errors_any": [r.get("error") for r in rounds if r.get("error")], "metrics": {}}
    for name in ("funnel-miss", "funnel-hit", "market", "cold-funnel", "cold-market"):
        for fld in ("ms", "ttfb_ms", "client_inflate_ms", "wire_bytes"):
            row = {}
            per_round = {}
            for arm, rs in arms.items():
                pooled, meds = [], []
                for r in rs:
                    st = [s for s in r["steps"] if s["name"] == name and "error" not in s] if "steps" in r else []
                    vals = [s[fld] for s in st]
                    pooled += vals
                    if vals:
                        meds.append(statistics.median(vals))
                row[arm] = summ(pooled)
                per_round[arm] = [round(m, 1) for m in meds]
            row["round_medians"] = per_round
            row["verdict"] = verdict(per_round["A"], per_round["B"])
            out["metrics"]["%s.%s" % (name, fld)] = row
    for name in ("funnel-miss", "funnel-hit", "market"):
        row = {}
        for arm, rs in arms.items():
            dec = [s["decoded_bytes"] for r in rs for s in r["steps"] if s["name"] == name and "error" not in s]
            wire = [s["wire_bytes"] for r in rs for s in r["steps"] if s["name"] == name and "error" not in s]
            row[arm] = {"decoded_median": pct(dec, 0.5), "wire_median": pct(wire, 0.5),
                        "ratio": round(pct(dec, 0.5) / pct(wire, 0.5), 2) if wire else None,
                        "errors": sum(1 for r in rs for s in r["steps"] if s["name"] == name and "error" in s),
                        "status": sorted({s["status"] for r in rs for s in r["steps"] if s["name"] == name and "status" in s}),
                        "x_cache": sorted({s["x_cache"] for r in rs for s in r["steps"] if s["name"] == name and "x_cache" in s})}
        out["metrics"]["%s.bytes" % name] = row
    for key in ("warm_cpu_pct_of_core", "ws_mb_max", "private_mb_end", "ext_10424_cpu_pct_of_core", "ready_s", "cold_cpu_ms"):
        a = [r[key] for r in arms["A"] if r.get(key) is not None]
        b = [r[key] for r in arms["B"] if r.get(key) is not None]
        out["metrics"][key] = {"A": a, "B": b, "verdict": verdict(a, b)}
    for key in ("median", "p95", "max"):
        a = [r["cheap_mstat_phase_ms"][key] for r in arms["A"]]
        b = [r["cheap_mstat_phase_ms"][key] for r in arms["B"]]
        out["metrics"]["cheap_mstat_phase_ms.%s" % key] = {"A": a, "B": b, "verdict": verdict(a, b)}
    out["metrics"]["cheap_errors"] = {"A": [r["cheap_errors"] for r in arms["A"]], "B": [r["cheap_errors"] for r in arms["B"]]}
    # بایتِ هر دقیقه با ریتمِ واقعیِ رابط (قیف ~۲۰٫۸s، تابلو یک بار در بارِ صفحه) — برایِ هزینهٔ ترافیک
    return out


def browser():
    p = os.path.join(HERE, "a2b", "a2b-all-rounds.json")
    if not os.path.exists(p):
        return None
    rounds = json.load(open(p, encoding="utf-8"))
    arms = {"A": [r for r in rounds if r["arm"] == "A"], "B": [r for r in rounds if r["arm"] == "B"]}
    out = {"order": "".join(r["arm"] for r in rounds), "db_pristine_all": all(r["db_pristine"] for r in rounds),
           "exits": [(r["round"], r.get("monitor_exit"), r.get("scroll_exit"), r.get("analyze_exit"), r.get("error")) for r in rounds],
           "metrics": {}}

    def g(r, *path):
        x = r
        for k in path:
            if x is None:
                return None
            x = x.get(k) if isinstance(x, dict) else None
        return x
    spec = [("cold.rows_ready_ms", ("loads", "cold-0", "rows_ready_ms")), ("cold.fcp_ms", ("loads", "cold-0", "fcp_ms")),
            ("warm.rows_ready_ms", ("loads", "warm-0", "rows_ready_ms")), ("warm.fcp_ms", ("loads", "warm-0", "fcp_ms")),
            ("long_tasks.n", ("long_tasks", "n")), ("long_tasks.total_ms", ("long_tasks", "total_ms")),
            ("long_tasks.max_ms", ("long_tasks", "max_ms")),
            ("funnel.dur_median", ("funnel", "dur_ms", "median")), ("funnel.dur_p95", ("funnel", "dur_ms", "p95")),
            ("funnel.dur_max", ("funnel", "dur_ms", "max")), ("funnel.ttfb_median", ("funnel", "ttfb_ms", "median")),
            ("funnel.json_ms_median", ("funnel", "json_ms", "median")), ("funnel.wire_median", ("funnel", "wire_bytes", "median")),
            ("funnel.n", ("funnel", "n")), ("funnel.errors", ("funnel", "errors")),
            ("market.dur_median", ("market", "dur_ms", "median")), ("market.dur_max", ("market", "dur_ms", "max")),
            ("market.wire_median", ("market", "wire_bytes", "median")), ("market.json_ms_median", ("market", "json_ms", "median")),
            ("delta.dur_median", ("delta", "dur_ms", "median")), ("delta.dur_p95", ("delta", "dur_ms", "p95")),
            ("delta.n", ("delta", "n")),
            ("screener.dur_median", ("screener", "dur_ms", "median")), ("screener.wire_median", ("screener", "wire_bytes", "median")),
            ("server.ws_mb_max", ("server", "ws_mb_max")), ("server.private_mb_max", ("server", "private_mb_max")),
            ("console_errors", ("console_errors",)),
            ("scroll.frame_ms_p95", ("scroll", "frame_ms_p95")), ("scroll.frame_ms_max", ("scroll", "frame_ms_max")),
            ("scroll.frames_over_50ms", ("scroll", "frames_over_50ms")), ("scroll.loaf_blocking_ms_total", ("scroll", "loaf_blocking_ms_total")),
            ("scroll.frames", ("scroll", "frames"))]
    # اسکرولِ دورِ ۰ با انتخاب‌گرِ غلط (`tbody tr`) ظرفِ ۹۰پیکسلی را پیمود؛ فقط دورهایی که تابلو را پیمودند معتبرند.
    def scroll_ok(r):
        return bool(g(r, "scroll", "rows_ready")) and bool(g(r, "scroll", "target"))
    out["scroll_valid_rounds"] = [r["round"] for r in rounds if scroll_ok(r)]
    out["scroll_excluded_rounds"] = [r["round"] for r in rounds if not scroll_ok(r)]
    for name, path in spec:
        keep = scroll_ok if name.startswith("scroll.") else (lambda r: True)
        a = [g(r, *path) for r in arms["A"] if keep(r)]
        b = [g(r, *path) for r in arms["B"] if keep(r)]
        a = [x for x in a if isinstance(x, (int, float))]
        b = [x for x in b if isinstance(x, (int, float))]
        out["metrics"][name] = {"A": a, "B": b,
                                "verdict": "INFO" if name in ("funnel.n", "delta.n", "scroll.frames") else verdict(a, b)}
    for arm, rs in arms.items():
        out["metrics"].setdefault("server.cpu_median_per_round", {})[arm] = [g(r, "server", "cpu_pct_one_core_median") for r in rs]
        out["metrics"].setdefault("hogs", {})[arm] = [g(r, "hogs") for r in rs]
        out["metrics"].setdefault("funnel.x_cache", {})[arm] = [g(r, "funnel", "x_cache") for r in rs]
    cpu = {arm: [x[0] for x in out["metrics"]["server.cpu_median_per_round"][arm] if x] for arm in arms}
    out["metrics"]["server.cpu_median"] = {"A": cpu["A"], "B": cpu["B"], "verdict": verdict(cpu["A"], cpu["B"])}

    # ریتمِ واقعیِ قیف ازِ خودِ رخدادهایِ fetchِ صفحه (t0ِ کلاینت، نه ساعتِ سرور)
    gaps = []
    for r in rounds:
        ev = os.path.join(HERE, "..", "..", r["dir"], "events.jsonl")
        if not os.path.exists(ev):
            continue
        t0s = sorted(e["t0"] for e in map(json.loads, open(ev, encoding="utf-8"))
                     if e.get("k") == "f" and str(e.get("url", "")).startswith("/api/funnel") and e.get("method") == "POST")
        gaps += [b - a for a, b in zip(t0s, t0s[1:])]
    out["funnel_poll_gap_ms"] = summ(gaps) | {"min": round(min(gaps), 1) if gaps else None}
    return out


if __name__ == "__main__":
    res = {"cli": cli(), "browser": browser()}
    with open(os.path.join(HERE, "a2-aggregate.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    for k, v in res["cli"]["metrics"].items():
        if "verdict" in v:
            print("cli", k, v.get("round_medians", {k2: v[k2] for k2 in ("A", "B")}), v["verdict"])
    if res["browser"]:
        for k, v in res["browser"]["metrics"].items():
            print("browser", k, {a: v[a] for a in ("A", "B") if a in v}, v.get("verdict"))
