# -*- coding: utf-8 -*-
"""tools/perf_market_open_analyze.py — تحلیلِ خروجیِ پایشِ بازشدنِ بازار.

ورودی: events.jsonlِ `perf_market_open_monitor.mts` و (اختیاری) sampler.jsonlِ
`perf_market_open_sampler.py`. خروجی: JSON + مارک‌داونِ فارسی (ارقام با اسکریپت ساخته می‌شوند).

معنایِ هر زمان (همه epochِ ساعتِ همین ماشین مگر خلافش گفته شود):
  dur      = tj − t0 (یا th − t0 اگر بدنه خوانده نشد: ۳۰۴/خطا) — انتظارِ کلاینت تا دادهٔ parseشده
  ttfb     = th − t0
  render   = paint − tj؛ paint = نخستین فریم بعد از نخستین جهشِ DOM پس از tj (به‌جز ناحیه‌هایِ کنارگذاشته)
  lag_cycle    = tj − last_sync   (last_sync = ساعتِ پایانِ سیکلِ همگام‌سازِ سرور، دقتِ ۱ ثانیه)
  lag_exchange = tj − (d_even + h_even)  (h_even = ساعتِ آخرین معاملهٔ TSETMC، ساعتِ بورس؛
                 کجیِ ساعتِ بورس با این ماشین اندازه‌گیری‌پذیر نیست ⇒ کرانِ بالایِ کهنگی، نه تأخیرِ خالص)
  lag_asof     = tj − as_of*1000  (فانل)؛  lag_computed = tj − computed_at (mstat)
هیچ آستانه‌ای برایِ «FROZEN» ساخته نمی‌شود: فقط «دادهٔ امروز نیست» (d_even ≠ تاریخِ نشست) و
«هیچ تغییرِ revی در پنجره دیده نشد» گزارش می‌شوند، با بلندترین بازهٔ بی‌تغییری.

    python tools/perf_market_open_analyze.py --events _audit/x/events.jsonl \
        --sampler _audit/x/sampler.jsonl --open 09:00 --close 12:30 --out _audit/x/analysis
"""
import argparse
import datetime as dt
import json
import os
import statistics
from collections import Counter, defaultdict

FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(x):
    return str(x).translate(FA)


def load_jsonl(path):
    out = []
    if not path or not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def pct(vals, p):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    k = (len(v) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 1)


def stats(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return {"n": 0, "median": None, "p95": None, "max": None}
    return {"n": len(v), "median": round(statistics.median(v), 1), "p95": pct(v, 0.95), "max": round(max(v), 1)}


def family(url):
    p = url.split("?")[0]
    if p.startswith("/api/mstat/"):
        return "/api/mstat/" + p[len("/api/mstat/"):].split("/")[0]
    return p


def local_ms(day, hhmmss):
    """d_even (YYYYMMDD) + h_even (HHMMSS عددی) ⇒ epoch msِ ساعتِ محلیِ ماشین (تهران)."""
    try:
        d = str(int(day))
        h = int(hhmmss)
        t = dt.datetime(int(d[:4]), int(d[4:6]), int(d[6:8]), h // 10000, (h // 100) % 100, h % 100)
        return t.timestamp() * 1000
    except (TypeError, ValueError):
        return None


def parse_local(s):
    if not s or not isinstance(s, str):
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return t.timestamp() * 1000
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", action="append", default=[])
    ap.add_argument("--sampler", default="")
    ap.add_argument("--date", default="", help="YYYY-MM-DD نشست؛ پیش‌فرض: تاریخِ نخستین رویداد")
    ap.add_argument("--open", default="09:00")
    ap.add_argument("--close", default="12:30")
    ap.add_argument("--bucket-min", type=float, default=5.0)
    ap.add_argument("--render-window-ms", type=float, default=2000.0)
    ap.add_argument("--exclude-area", action="append", default=[])
    ap.add_argument("--out", required=True, help="پیشوندِ خروجی (بی‌پسوند)")
    a = ap.parse_args()
    excl = set(a.exclude_area or ["freshness-badge"])

    ev = []
    for p in a.events:
        ev.extend(load_jsonl(p))
    smp = load_jsonl(a.sampler)
    if not ev and not smp:
        raise SystemExit("هیچ رویدادی نیست")
    # تمرین با ساعتِ میخکوب: زمان‌هایِ صفحه درِ خطِ زمانِ جابه‌جاشده‌اند، زمان‌هایِ Node/نمونه‌گیر واقعی
    mstart = next((e for e in ev if e.get("k") == "start" and "journey" in e), {})
    pin, off = mstart.get("clock_pin"), mstart.get("clock_offset_ms") or 0
    if off:
        for e in ev:
            for key in ("tn", "t_nav"):
                if isinstance(e.get(key), (int, float)):
                    e[key] += off
        for s in smp:
            if isinstance(s.get("t"), (int, float)):
                s["t"] += off / 1000.0
    first_t = min(e.get("tn") or e.get("t", 0) * 1000 for e in (ev or smp)) / 1000
    day = dt.date.fromisoformat(a.date) if a.date else dt.datetime.fromtimestamp(first_t).date()
    day_key = int(day.strftime("%Y%m%d"))

    def at(hhmm):
        h, m = (int(x) for x in hhmm.split(":"))
        return dt.datetime(day.year, day.month, day.day, h, m).timestamp() * 1000

    t_open, t_close = at(a.open), at(a.close)
    bms = a.bucket_min * 60_000

    def bucket(t):
        if t is None:
            return None
        if t < t_open:
            return "pre-open"
        if t > t_close:
            return "post-close"
        i = int((t - t_open) // bms)
        lo = i * a.bucket_min
        return "%02d-%02d" % (lo, lo + a.bucket_min)

    fetches = [e for e in ev if e.get("k") == "f"]
    heads = [e for e in ev if e.get("k") == "fh"]
    fails = [e for e in ev if e.get("k") == "ff"]
    nets = [e for e in ev if e.get("k") == "net"]
    netfails = [e for e in ev if e.get("k") == "netfail"]
    muts = sorted((e for e in ev if e.get("k") == "mut"), key=lambda e: e["t"])
    lts = [e for e in ev if e.get("k") == "lt"]
    smps = [e for e in ev if e.get("k") == "smp"]
    cons = [e for e in ev if e.get("k") in ("console", "pageerror")]
    loads = [e for e in ev if e.get("k") == "load"]

    # رویدادِ fh بی‌f (۳۰۴/بدنهٔ ناخوانده/خطا) هم یک درخواستِ کامل است
    read_ids = {(e.get("route"), e["id"], e["t0"]) for e in fetches}
    reqs = list(fetches) + [h for h in heads if (h.get("route"), h["id"], h["t0"]) not in read_ids]

    mut_ts = [m["t"] for m in muts]
    import bisect

    def first_burst(t, window):
        i = bisect.bisect_left(mut_ts, t)
        while i < len(muts) and muts[i]["t"] - t <= window:
            areas = set(muts[i].get("areas", {})) - excl
            if areas:
                return muts[i]
            i += 1
        return None

    fam_rows = defaultdict(list)
    for r in reqs:
        f = family(r["url"])
        end = r.get("tj") or r.get("th")
        ts = r.get("ts") or {}
        row = {"t0": r["t0"], "bucket": bucket(r["t0"]), "status": r.get("status"), "xc": r.get("xc", ""),
               "dur": round(end - r["t0"], 1) if end else None, "ttfb": round(r["th"] - r["t0"], 1),
               "json_ms": r.get("json_ms"), "method": r.get("method"), "dstatus": ts.get("status"),
               "rev": ts.get("rev"), "d_even": ts.get("meta.d_even"), "h_even": ts.get("meta.h_even")}
        if r.get("tj"):
            b = first_burst(r["tj"], a.render_window_ms)
            row["render"] = round(b["paint"] - r["tj"], 1) if b else None
            chance = first_burst(r["tj"] + 5000, a.render_window_ms)
            row["chance_burst"] = chance is not None
            row["display_t"] = b["paint"] if b else None
            tj_real = r["tj"] - off  # مهرهایِ سرور/بورس با ساعتِ واقعی‌اند، نه ساعتِ میخکوبِ کلاینت
            ls = ts.get("meta.last_sync")
            if isinstance(ls, str):
                p = parse_local(ls)
                row["lag_cycle"] = round(tj_real - p, 1) if p else None
            if row["d_even"] and row["h_even"] is not None:
                ex = local_ms(row["d_even"], row["h_even"])
                row["lag_exchange"] = round(tj_real - ex, 1) if ex else None
            if isinstance(ts.get("as_of"), (int, float)):
                row["lag_asof"] = round(tj_real - ts["as_of"] * 1000, 1)
            ca = parse_local(ts.get("computed_at"))
            if ca:
                row["lag_computed"] = round(tj_real - ca, 1)
        fam_rows[f].append(row)

    wire_by = defaultdict(list)
    for n in nets:
        wire_by[family(n["url"])].append(n)

    def summarize(rows, nets_):
        out = {"n": len(rows), "status": dict(Counter(str(r["status"]) for r in rows)),
               "x_cache": dict(Counter(r["xc"] or "-" for r in rows)),
               "delta_status": dict(Counter(r["dstatus"] for r in rows if r["dstatus"])),
               "errors": sum(1 for r in rows if not r["status"] or r["status"] >= 400),
               "dur_ms": stats([r["dur"] for r in rows]), "ttfb_ms": stats([r["ttfb"] for r in rows]),
               "json_ms": stats([r.get("json_ms") for r in rows]),
               "render_ms": stats([r.get("render") for r in rows]),
               "render_none": sum(1 for r in rows if "render" in r and r["render"] is None),
               "chance_burst_rate": (round(sum(1 for r in rows if r.get("chance_burst")) /
                                           max(1, sum(1 for r in rows if "chance_burst" in r)), 3)),
               "lag_cycle_ms": stats([r.get("lag_cycle") for r in rows]),
               "lag_exchange_ms": stats([r.get("lag_exchange") for r in rows]),
               "lag_asof_ms": stats([r.get("lag_asof") for r in rows]),
               "lag_computed_ms": stats([r.get("lag_computed") for r in rows])}
        w = [n.get("wire") for n in nets_ if isinstance(n.get("wire"), (int, float)) and n["wire"] >= 0]
        out["wire_bytes_total"] = int(sum(w)) if w else 0
        out["wire_bytes"] = stats(w)
        out["enc"] = dict(Counter(n.get("enc") for n in nets_))
        return out

    families = {}
    for f, rows in sorted(fam_rows.items()):
        nets_f = wire_by.get(f, [])
        by_b = defaultdict(list)
        for r in rows:
            by_b[r["bucket"]].append(r)
        nb = defaultdict(list)
        for n in nets_f:
            nb[bucket(n["tn"])].append(n)
        sess = [r for r in rows if r["bucket"] not in ("pre-open", "post-close")]
        families[f] = {"all": summarize(rows, nets_f),
                       "session": summarize(sess, [n for n in nets_f if t_open <= n["tn"] <= t_close]),
                       "buckets": {b: summarize(v, nb.get(b, [])) for b, v in sorted(by_b.items(), key=lambda x: str(x[0]))}}
        # «درخواست‌شده ولی خوانده‌نشده» را جدا می‌شماریم: لغوِ react-query هم ff/netfail می‌دهد
    fail_by = Counter(family(e["url"]) for e in fails)
    netfail_by = defaultdict(Counter)
    for e in netfails:
        netfail_by[family(e["url"])][e.get("err", "")] += 1

    # زنجیرهٔ تازگیِ تابلو: rev/h_even/d_even در طولِ نشست
    feed = sorted((r for f in ("/api/market", "/api/market/delta") for r in fam_rows.get(f, []) if r.get("rev") is not None or r.get("h_even") is not None),
                  key=lambda r: r["t0"])
    in_sess = [r for r in feed if t_open <= r["t0"] <= t_close]
    d_seen = sorted({r["d_even"] for r in feed if r["d_even"]})
    longest_rev, longest_h = 0.0, 0.0
    for key, store in (("rev", "rev"), ("h_even", "h")):
        last_v, since = None, None
        best = 0.0
        for r in in_sess:
            v = r.get(key)
            if v is None:
                continue
            if v != last_v:
                last_v, since = v, r["t0"]
            else:
                best = max(best, r["t0"] - since)
        if store == "rev":
            longest_rev = best
        else:
            longest_h = best
    rev_changes = sum(1 for i in range(1, len(in_sess)) if in_sess[i].get("rev") is not None and in_sess[i]["rev"] != in_sess[i - 1].get("rev"))
    today_seen = any(str(d) == str(day_key) for d in d_seen)
    freshness = {"session_day": day_key, "d_even_seen": d_seen, "today_in_feed": today_seen,
                 "requests_in_session": len(in_sess), "rev_changes_in_session": rev_changes,
                 "longest_unchanged_rev_s": round(longest_rev / 1000, 1),
                 "longest_unchanged_h_even_s": round(longest_h / 1000, 1),
                 "first_h_even": next((r["h_even"] for r in in_sess if r.get("h_even") is not None), None),
                 "last_h_even": next((r["h_even"] for r in reversed(in_sess) if r.get("h_even") is not None), None),
                 "verdict": ("NO_DATA" if not in_sess else "SNAPSHOT_NOT_TODAY" if not today_seen
                             else "NO_CHANGE_OBSERVED" if rev_changes == 0 else "CHANGING")}

    lt_b = defaultdict(list)
    for e in lts:
        lt_b[bucket(e["t"])].append(e["dur"])
    long_tasks = {b: {"n": len(v), "total_ms": int(sum(v)), "max_ms": max(v)} for b, v in sorted(lt_b.items(), key=lambda x: str(x[0]))}
    badge = defaultdict(Counter)
    for s in smps:
        badge[bucket(s["t"])][s.get("fresh") or "-"] += 1
    drift = [s.get("drift_ms") for s in smps if s.get("drift_ms") is not None]
    heap = [s.get("heap_mb") for s in smps if s.get("heap_mb") is not None]
    dom = [s.get("dom") for s in smps if s.get("dom") is not None]

    load_rows = []
    for e in loads:
        rt = (e.get("ready") or {}).get("t")
        nav = e.get("nav") or {}
        load_rows.append({"name": e["name"], "route": e["route"], "t_nav": e["t_nav"], "bucket": bucket(e["t_nav"]),
                          "rows_ready_ms": round(rt - e["t_nav"], 1) if rt else None,
                          "rows": (e.get("ready") or {}).get("rows"), "fcp_ms": nav.get("fcp"),
                          "dcl_ms": nav.get("dcl"), "err": e.get("err")})

    # sampler: CPU/RAMِ سرور (cpu_pct = درصدِ *یک* هسته)، CPUِ کلِ سیستم، کلاینت‌ها، نوشتنِ بانک
    s_rows = [s for s in smp if s.get("k") == "s"]
    cpu_b = defaultdict(list)
    for s in s_rows:
        cpu_b[bucket(s["t"] * 1000)].append(s)
    server = {}
    for b, v in sorted(cpu_b.items(), key=lambda x: str(x[0])):
        server[b] = {"cpu_pct_one_core": stats([x.get("cpu_pct") for x in v]),
                     "sys_cpu_pct": stats([x.get("sys_cpu_pct") for x in v]),
                     "ws_mb_max": max((x.get("ws_mb") or 0) for x in v),
                     "private_mb_max": max((x.get("private_mb") or 0) for x in v)}
    writes = defaultdict(Counter)
    last = {}
    for s in s_rows:
        for p, st in (s.get("files") or {}).items():
            m = st and st.get("mtime")
            if m and last.get(p) not in (None, m):
                writes[bucket(s["t"] * 1000)][os.path.basename(p)] += 1
            last[p] = m
    tops = [t for t in smp if t.get("k") == "top"]
    hogs = Counter()
    for t in tops:
        for x in t.get("top", []):
            if x.get("cpu_pct", 0) >= 50:
                hogs["%s:%s" % (x.get("pid"), x.get("name"))] += 1
    client_union = sorted({"%s:%s" % (c.get("pid"), c.get("name")) for t in tops + [s for s in smp if s.get("k") == "start"] for c in t.get("clients", [])})
    start = next((s for s in smp if s.get("k") == "start"), {})
    end = next((s for s in smp if s.get("k") == "end"), {})

    result = {"session_day": str(day), "open": a.open, "close": a.close, "bucket_min": a.bucket_min,
              "rehearsal_clock_pin": pin, "clock_offset_ms": off,
              "excluded_areas": sorted(excl), "events": len(ev), "sampler_records": len(smp),
              "loads": load_rows, "families": families, "fetch_errors_unread": dict(fail_by),
              "netfail": {k: dict(v) for k, v in netfail_by.items()}, "freshness_feed": freshness,
              "long_tasks": long_tasks, "badge": {b: dict(c) for b, c in badge.items()},
              "page": {"drift_ms": stats(drift), "heap_mb": stats(heap), "dom_nodes": stats(dom)},
              "console": {"n": len(cons), "first": [c.get("text") for c in cons[:8]]},
              "server": server, "db_writes": {b: dict(c) for b, c in writes.items()},
              "cpu_hogs_ge50pct": dict(hogs), "clients_seen": client_union,
              "ntp": {"start": start.get("ntp"), "end": end.get("ntp")}, "server_identity": start.get("server")}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out + ".json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    def s3(s):
        return "—" if not s or not s.get("n") else fa("%s / %s / %s" % (s["median"], s["p95"], s["max"]))

    md = ["# تحلیلِ پایشِ بازشدنِ بازار — %s" % fa(day), ""]
    if pin:
        md += ["**تمرین، نه پایشِ زنده:** ساعتِ کلاینت رویِ `%s` میخکوب شد (فاصله %s ms). سرور و بانک ساعتِ واقعی دارند؛"
               " هیچ عددِ این خروجی مدرکِ تازگیِ دادهٔ زنده نیست." % (pin, fa(off)), ""]
    md += ["بازهٔ نشست %s تا %s (ساعتِ محلیِ ماشین)؛ سطل‌ها %s دقیقه از آغاز. اعداد: میانه / p95 / بیشینه (ms)." % (
              fa(a.open), fa(a.close), fa(int(a.bucket_min))), "",
          "## بارِ اولیه", "", "| بار | مسیر | آمادگیِ ردیف‌ها | FCP | DCL | سطل |", "|---|---|---|---|---|---|"]
    for r in load_rows:
        md.append("| %s | %s | %s | %s | %s | %s |" % (r["name"], r["route"], fa(r["rows_ready_ms"]) if r["rows_ready_ms"] else "—",
                                                    fa(r["fcp_ms"]), fa(r["dcl_ms"]), r["bucket"]))
    md += ["", "## مسیرها (کلِ نشست)", "",
           "| مسیر | تعداد | وضعیت | X-Cache | خطا | انتظار | TTFB | رندر | بایتِ سیم | lag_cycle | lag_exchange | lag_asof/computed |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f, v in families.items():
        s = v["session"] if v["session"]["n"] else v["all"]
        md.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            f, fa(s["n"]), fa(json.dumps(s["status"])), fa(json.dumps(s["x_cache"])), fa(s["errors"]),
            s3(s["dur_ms"]), s3(s["ttfb_ms"]), s3(s["render_ms"]), fa(s["wire_bytes_total"]),
            s3(s["lag_cycle_ms"]), s3(s["lag_exchange_ms"]),
            s3(s["lag_asof_ms"]) if s["lag_asof_ms"]["n"] else s3(s["lag_computed_ms"])))
    md += ["", "## تازگیِ تابلو", "", "```", fa(json.dumps(freshness, ensure_ascii=False, indent=1)), "```",
           "", "## Long Taskها", "", "| سطل | تعداد | مجموع | بیشینه |", "|---|---|---|---|"]
    for b, v in long_tasks.items():
        md.append("| %s | %s | %s | %s |" % (b, fa(v["n"]), fa(v["total_ms"]), fa(v["max_ms"])))
    md += ["", "## سرور (CPU = درصدِ یک هسته)", "", "| سطل | CPU سرور | CPU سیستم | WS بیشینه MB | Private بیشینه MB |", "|---|---|---|---|---|"]
    for b, v in server.items():
        md.append("| %s | %s | %s | %s | %s |" % (b, s3(v["cpu_pct_one_core"]), s3(v["sys_cpu_pct"]),
                                              fa(v["ws_mb_max"]), fa(v["private_mb_max"])))
    md += ["", "کلاینت‌هایِ دیده‌شده: %s" % (", ".join(client_union) or "—"),
           "پردازه‌هایِ ≥۵۰٪ یک هسته: %s" % (fa(json.dumps(dict(hogs), ensure_ascii=False)) or "—"),
           "خطاهایِ console: %s" % fa(len(cons)), ""]
    with open(a.out + ".md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(json.dumps({"out": a.out, "families": {k: v["all"]["n"] for k, v in families.items()},
                      "freshness": freshness["verdict"], "loads": len(load_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
