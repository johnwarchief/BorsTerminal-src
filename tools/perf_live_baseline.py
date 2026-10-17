#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/perf_live_baseline.py — ثبتِ baseline عملکردِ بازارِ زنده (فقط‌خواندنی).

چرا این فایل: مأموریت «کاراییِ بازارِ زنده + تطبیقِ وضعیتِ بازار» می‌گوید پیش از
هر بهینۀ‌ای، baselineِ واقعی گرفته شود. این ابزار هیچ چیزی را restart نمی‌کند،
هیچ cache‌ای را پاک نمی‌کند و هیچ نوشتنی رویِ بانک نمی‌زند — فقط همان endpointهایی
را که رابطِ کاربر می‌زند، در بازۀِ زمانیِ مشخص نمونه‌برداری می‌کند و زمان/حجم/
تازگی را ثبت می‌کند.

`/api/screener` عمداً درِ حلقه نیست: کشِ آن ۴۳۲۰۰ ثانیه است و یکِ تماسِ سرد درِ
ساعتِ بازار یعنی ~۲۷ ثانۀ محاسبۀ سنگین رویِ همان CPU که تابلو به آن نیاز دارد.
با `--screener-once` یک‌بار و بیرونِ حلقه سنجیده می‌شود.

نمون:
  PYTHONIOENCODING=utf-8 python tools/perf_live_baseline.py \
      --base http://127.0.0.1:8012 --samples 20 --interval 10 --pid 22520
خروجی: `_audit/perf_live/baseline_<stamp>.jsonl` (هر خط یکِ نمونه) و
       `_audit/perf_live/baseline_<stamp>.summary.json` (p50/p95/max + حجم + تازگی)
"""
from __future__ import annotations

import argparse
import ast
import datetime
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "_audit", "perf_live")

DEFAULT_PATHS = [
    "/api/market",
    "/api/market/delta",
    "/api/market/sync-state",
    "/api/mstat/summary",
    "/api/mstat/phase",
    "/api/mstat/board",
]
# کوئری‌هایی که «زمان اجرای queryهای اصلی» مأموریت روی‌شان سنجیده می‌شود. متنِ
# هر کوئری از خودِ ماژولِ منبع خوانده می‌شود (`sql_const`) — کپیِ متن یعنی یک
# source دوم که بی‌صدا از کوئریِ واقعیِ اپ جدا می‌افتد.
DEFAULT_QUERIES = [
    ("api/market.py", "_BOARD_SQL", "board"),
    ("api/market.py", "_HIST_V_SQL", "hist_window_60"),
    ("api/market.py", "_HIST_FV_SQL", "hist_flow"),
    ("api/market.py", "_HIST_FV_SLOT_SQL", "hist_flow_slot"),
]
# کلیدهایی که «زمانِ داده» را می‌گویند — برایِ تفکیکِ سرعتِ پاسخ از تازگیِ داده
TIME_KEYS = ("fetched_at", "as_of", "updated_at", "last_update", "generated_at",
             "synced_at", "ts", "d_even", "server_time", "checked_at")


def sql_const(rel_path, name):
    """متنِ کوئری را از خودِ ماژولِ منبع درمی‌آورد (بدونِ ایمپورت‌کردنِ اپ).

    چرا `ast` و نه `import api.market`: ایمپورت، FastAPI و کشِ ماژول را بالا
    می‌آورد و زمانِ سنجیده‌شده را با کارِ خودش قاطی می‌کند. `ast.literal_eval`
    رویِ همان Constant فقط رشته را می‌دهد، بی‌هیچ اثرِ جانبی.
    """
    with io.open(os.path.join(ROOT, rel_path), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return ast.literal_eval(node.value)
    raise KeyError("%s in %s" % (name, rel_path))


def query_times(conn, specs):
    """زمانِ اجرایِ هر کوئری رویِ همان bank که اپ می‌خواند (فقط‌خواندنی)."""
    out = []
    for sql, label in specs:
        t0 = time.perf_counter()
        try:
            rows = conn.execute(sql).fetchall()
            out.append({"q": label, "ms": round((time.perf_counter() - t0) * 1000.0, 1),
                        "rows": len(rows)})
        except Exception as e:
            out.append({"q": label, "ms": None,
                        "error": "%s: %s" % (type(e).__name__, str(e)[:90])})
    return out


def pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    i = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
    return s[i]


def proc_mem_kb(pid):
    """RAM (MB) و زمانِ CPU (ثانیه) فرایند از `Get-Process`.

    چرا PowerShell نه `tasklist`: ستونِ "Memory Usage" در tasklist رشته‌ای مثل
    `512,872 K` است و بدونِ واحد، CPU را هیچ‌وقت نمی‌دهد — baselineِ مأموریت
    «کاراییِ بازار» هر دو را می‌خواهد. فقط‌خواندنی، بدونِ هیچ اثری رویِ فرایند.
    """
    if not pid:
        return None
    try:
        ps = ("$p=Get-Process -Id %d -ErrorAction SilentlyContinue;"
              "if($p){'{0}|{1}' -f [math]::Round($p.WorkingSet64/1MB,1),"
              "[math]::Round($p.CPU,1)}") % int(pid)
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=20)
        line = (out.stdout or "").strip().splitlines()
        if not line or "|" not in line[-1]:
            return None
        mem_mb, cpu_s = line[-1].split("|")[:2]
        return {"mem_mb": float(mem_mb), "cpu_s": float(cpu_s)}
    except Exception:
        return None



def walk_times(obj, found, depth=0):
    if depth > 6 or found is None:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in TIME_KEYS and isinstance(v, (str, int, float)) and v:
                found[k] = str(v)[:32]
            elif isinstance(v, (dict, list)):
                walk_times(v, found, depth + 1)
    elif isinstance(obj, list):
        for v in obj[:3]:
            walk_times(v, found, depth + 1)


def shape(obj):
    """اندازه و شمارِ ردیفِ پاسخ — برایِ اثباتِ «پوشش کم نشده»."""
    if isinstance(obj, dict):
        for key in ("rows", "data", "items", "list", "markets", "board"):
            v = obj.get(key)
            if isinstance(v, list):
                return len(v), sorted(obj.keys())[:8]
        n = 0
        for v in obj.values():
            if isinstance(v, list):
                n = max(n, len(v))
        return n, sorted(obj.keys())[:8]
    if isinstance(obj, list):
        return len(obj), ["<list>"]
    return None, None


def one(base, path, timeout=30):
    url = base.rstrip("/") + path
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip, deflate",
                                               "User-Agent": "bors-perf-baseline"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            dt = (time.perf_counter() - t0) * 1000.0
            enc = (r.headers.get("Content-Encoding") or "identity").lower()
            code = r.status
    except urllib.error.HTTPError as e:
        return {"path": path, "error": "http-%s" % e.code, "ms": None}
    except Exception as e:
        return {"path": path, "error": "%s: %s" % (type(e).__name__, str(e)[:80]),
                "ms": None}
    out = {"path": path, "ms": round(dt, 1), "bytes": len(raw), "encoding": enc,
           "code": code, "sha8": hashlib.sha256(raw).hexdigest()[:8]}
    # پیش‌تر همین‌جا `raw` مستقیم به json.loads می‌رفت: با `Content-Encoding: gzip`
    # (که اپ برایِ `/api/market` می‌دهد) تجزیه شکست می‌خورد و `rows` هیچ‌وقت
    # پر نمی‌شد — یعنی سنسورِ «تعداد نمادهای خروجی» برایِ بزرگ‌ترین پاسخِ اپ
    # کور بود، نه اینکه داده صفر باشد.
    body = raw
    if enc in ("gzip", "x-gzip"):
        try:
            body = zlib.decompress(raw, 16 + zlib.MAX_WBITS)
        except Exception as e:
            out["gunzip_error"] = str(e)[:60]
            body = b""
    elif enc == "deflate":
        try:
            body = zlib.decompress(raw)
        except Exception as e:
            out["gunzip_error"] = str(e)[:60]
            body = raw
    out["decoded_bytes"] = len(body)
    out["compression_ratio"] = (round(len(raw) * 100.0 / len(body), 1)
                                if body else None)
    try:
        obj = json.loads(body.decode("utf-8", "replace"))
        n, keys = shape(obj)
        found = {}
        walk_times(obj, found)
        out["rows"] = n
        out["top_keys"] = keys
        out["times"] = found
    except Exception as e:
        out["parse_error"] = str(e)[:80]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8012")
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--interval", type=float, default=10.0)
    ap.add_argument("--pid", type=int, default=None)
    ap.add_argument("--paths", default=",".join(DEFAULT_PATHS))
    ap.add_argument("--screener-once", action="store_true")
    ap.add_argument("--db", default=os.path.join(ROOT, "market.db"),
                    help="بانکِ بازار برایِ سنجشِ کوئری‌ها (فقط‌خواندنی؛ صفر ⇒ بی‌سنجش)")
    ap.add_argument("--tag", default="baseline")
    a = ap.parse_args(argv)
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    jsl = os.path.join(OUT_DIR, "%s_%s.jsonl" % (a.tag, stamp))
    summ = os.path.join(OUT_DIR, "%s_%s.summary.json" % (a.tag, stamp))
    paths = [p.strip() for p in a.paths.split(",") if p.strip()]
    qspec, qconn = [], None
    if a.db and os.path.exists(a.db):
        try:
            # `?mode=ro` عمدی است: این baseline رویِ همان بانکِ عملیاتیِ اپ اجرا
            # می‌شود و هیچ نوشتنی نباید در آن دیده شود.
            qconn = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True,
                                    timeout=20)
            for rel, name, label in DEFAULT_QUERIES:
                try:
                    qspec.append((sql_const(rel, name), label))
                except Exception as e:
                    print("QUERY-SKIP %s: %s" % (name, str(e)[:80]))
        except Exception as e:
            print("QUERY-SKIP db-unavailable: %s" % str(e)[:90])
            qconn = None
    started = datetime.datetime.now()
    per = {p: [] for p in paths}
    bytes_ = {p: [] for p in paths}
    dec_bytes = {p: [] for p in paths}
    rows = {p: [] for p in paths}
    errs = {p: [] for p in paths}
    mems, cpus, samples = [], [], []
    qms = {label: [] for _, _, label in DEFAULT_QUERIES}
    qrows = {label: [] for _, _, label in DEFAULT_QUERIES}
    qerr = {label: [] for _, _, label in DEFAULT_QUERIES}
    with open(jsl, "w", encoding="utf-8") as f:
        for i in range(a.samples):
            t_cycle = datetime.datetime.now().strftime("%H:%M:%S")
            line = {"i": i, "at": t_cycle, "calls": []}
            # نمونه‌برداریِ فرایند یک‌بار در هر چرخه و *بیرونِ* حلقۀ endpoint:
            # داخلِ حلقه یعنی شش فراخوانیِ PowerShell بین هر دو سنجش، که خودش
            # زمانِ پاسخِ همان سنجش‌ها را بالا می‌برد.
            st = proc_mem_kb(a.pid)
            if st:
                mems.append(st["mem_mb"])
                cpus.append(st["cpu_s"])
                line["proc"] = st
            for p in paths:
                r = one(a.base, p)
                r["at"] = t_cycle
                line["calls"].append(r)
                if r.get("ms") is None:
                    errs[p].append(r.get("error", "?"))
                else:
                    per[p].append(r["ms"])
                    bytes_[p].append(r.get("bytes") or 0)
                    if r.get("decoded_bytes"):
                        dec_bytes[p].append(r["decoded_bytes"])
                    if r.get("rows") is not None:
                        rows[p].append(r["rows"])
            if qspec:
                qr = query_times(qconn, qspec)
                line["queries"] = qr
                for r in qr:
                    if r.get("ms") is None:
                        qerr[r["q"]].append(r.get("error", "?"))
                    else:
                        qms[r["q"]].append(r["ms"])
                        if r.get("rows") is not None:
                            qrows[r["q"]].append(r["rows"])
            samples.append(line)
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
            f.flush()
            if i < a.samples - 1:
                time.sleep(a.interval)
    if qconn is not None:
        qconn.close()
    screen = one(a.base, "/api/screener", timeout=90) if a.screener_once else None
    ended = datetime.datetime.now()
    wall = (ended - started).total_seconds()
    out = {
        "meta": {
            "base": a.base, "pid": a.pid, "tag": a.tag,
            "branch": os.popen("git -C %s rev-parse --abbrev-ref HEAD" % ROOT).read().strip(),
            "head": os.popen("git -C %s rev-parse --short HEAD" % ROOT).read().strip(),
            "started_local": started.strftime("%Y-%m-%d %H:%M:%S"),
            "ended_local": ended.strftime("%Y-%m-%d %H:%M:%S"),
            "seconds": (ended - started).total_seconds(),
            "samples": a.samples, "interval_s": a.interval,
            "raw_lines": jsl,
        },
        "endpoints": {},
        "process": {
            "pid": a.pid,
            "mem_mb_p50": pct(mems, 50) if mems else None,
            "mem_mb_max": max(mems) if mems else None,
            "mem_samples": len(mems),
            # زمانِ CPU *تجمعی* است؛ آنچه معنی دارد اختلافِ دو نمونه است، نه مقدارِ خام.
            "cpu_total_s": round(cpus[-1] - cpus[0], 1) if len(cpus) >= 2 else None,
            "cpu_pct_avg": (round((cpus[-1] - cpus[0]) / wall * 100.0, 1)
                            if len(cpus) >= 2 and wall > 0 else None),
        },

    }
    for p in paths:
        out["endpoints"][p] = {
            "n": len(per[p]), "p50_ms": pct(per[p], 50), "p95_ms": pct(per[p], 95),
            "max_ms": max(per[p]) if per[p] else None,
            "bytes_p50": pct(bytes_[p], 50), "bytes_max": max(bytes_[p]) if bytes_[p] else None,
            "decoded_bytes_p50": pct(dec_bytes[p], 50) if dec_bytes[p] else None,
            "rows_min": min(rows[p]) if rows[p] else None,
            "rows_max": max(rows[p]) if rows[p] else None,
            "errors": errs[p][:5], "error_count": len(errs[p]),
        }
    if qspec:
        out["queries"] = {}
        for _, _, label in DEFAULT_QUERIES:
            v = qms.get(label) or []
            if not v and not qerr.get(label):
                continue
            out["queries"][label] = {
                "n": len(v), "p50_ms": pct(v, 50), "p95_ms": pct(v, 95),
                "max_ms": max(v) if v else None,
                "rows_last": (qrows.get(label) or [None])[-1],
                "errors": qerr.get(label, [])[:3], "error_count": len(qerr.get(label, [])),
            }
    if screen:
        out["screener_once"] = screen
    with open(summ, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out["meta"], ensure_ascii=False), flush=True)
    print(json.dumps(out["endpoints"], ensure_ascii=False, indent=2), flush=True)
    print("saved: %s" % summ)
    return 0


if __name__ == "__main__":
    sys.exit(main())
