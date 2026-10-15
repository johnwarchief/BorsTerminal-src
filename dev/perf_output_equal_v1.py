"""PERF Stage 10 — output-equality gate: faster must never mean different.

Every endpoint on the user's real paths is fetched from a running backend and
canonicalized. `save` writes a snapshot; `check` compares two snapshots and
classifies every difference:

  IDENTICAL          — byte-identical canonical JSON
  VOLATILE-ONLY      — only wall-clock stamps declared below differ
  DATA-DIFF          — any other difference (verdict: FAIL, with the paths)

Snapshots live in %TEMP% (they are copies of market data, not repo content);
only the small digest report is written under _audit/perf/.

usage:
  python dev/perf_output_equal_v1.py save  --tag before
  python dev/perf_output_equal_v1.py check --before before --after after
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

VOLATILE_KEYS = {
    "computed_at", "generated_at", "server_now", "now", "checked_at",
    "requested_at", "built_at", "fetched_at_wall", "age_ms", "age_s",
    "elapsed", "duration_ms", "payload_age_s", "asof_wall", "ts_wall",
    "history_repair_scheduled", "last_cycle_at",
    # سِنِ پاسخ، نه داده: یکِ درخواست ازِ کشِ چارت می‌آید و بعدی از CDN
    "payloadAgeS", "cache_age_sec",
}

# اندپوینت‌هایی که بدنشان از *منبعِ زنده بیرونی* می‌آید، نه از market.db.
# برابریِ این‌ها گیتِ تغییرِ کد نیست (سنجشِ کنترل: دو گرفتنِ پیاپی از یکِ
# سرورِ دست‌نخورده هم differ می‌کند — شمعدانِ نشستِ جدید / رویدادِ تعدیلِ تازه
# از سایت می‌آید). تفاوتشان گزارش می‌شود ولی حکم را نمی‌سازد.
EXTERNAL_PATHS = {"/api/chart/فولاد", "/api/index/tedpix?limit=0"}

# The real UI paths, with the exact query strings the frontend sends.
ENDPOINTS = [
    ("market", "/api/market"),
    ("live-stats", "/api/live-stats"),
    ("mstat-summary", "/api/mstat/summary"),
    ("mstat-histogram", "/api/mstat/histogram?group=eq_all"),
    ("mstat-thermometer", "/api/mstat/thermometer?group=eq_all"),
    ("mstat-depth", "/api/mstat/depth?group=eq_all"),
    ("mstat-clientsplit", "/api/mstat/clientsplit?tab=all"),
    ("mstat-phase", "/api/mstat/phase"),
    ("mstat-mainwatch", "/api/mstat/mainwatch?group=eq_all&industry="),
    ("mstat-industries", "/api/mstat/industries"),
    ("mstat-smart-money", "/api/mstat/smart-money"),
    ("mstat-timeline", "/api/mstat/timeline?mode=cum"),
    ("mstat-phases", "/api/mstat/phases"),
    ("mstat-treemap", "/api/mstat/treemap?group=eq_all&industry=&metric=value"),
    ("mstat-tops", "/api/mstat/tops?group=eq_all"),
    ("mstat-orderflows", "/api/mstat/orderflows?group=eq_all"),
    ("mstat-ownership", "/api/mstat/ownership?group=eq_all"),
    ("mstat-indexcards", "/api/mstat/indexcards?days=30"),
    ("mstat-gold", "/api/mstat/gold?history_days=60"),
    ("mstat-series", "/api/mstat/series?symbols=فولاد,خوز,تاپيستا&days=90"),
    ("mstat-board", "/api/mstat/board?group=eq_all&limit=60"),
    ("screener", "/api/screener"),
    ("funnel-registry", "/api/funnel/registry"),
    ("fts-config", "/api/fts/config"),
    ("chart-foulad", "/api/chart/فولاد"),
    ("index-tedpix", "/api/index/tedpix?limit=0"),
    ("watchlist", "/api/watchlist"),
]

LIST_KEYS = ("data", "rows", "symbols", "candles", "panels", "series", "items")


def fetch(base, path, timeout=180.0):
    req = urllib.request.Request(base + urllib.parse.quote(path, safe="/?=&%,"),
                                 headers={"User-Agent": "perf-equal/1"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8", "replace")), (time.perf_counter() - t0) * 1000.0, r.status
    except urllib.error.HTTPError as e:
        return {"__http_error__": e.code}, (time.perf_counter() - t0) * 1000.0, e.code
    except Exception as e:                                    # noqa: BLE001
        return {"__error__": f"{type(e).__name__}: {e}"}, (time.perf_counter() - t0) * 1000.0, -1


def canonical(obj, path="$", diffs=None):
    """Sorted-key JSON text, plus (for check) the volatile-stripped variant.

    Returns (strict_text, stable_text). `stable_text` replaces the value of any
    declared volatile key with the literal '<vol>' so timestamps can never be
    mistaken for data drift.
    """
    if isinstance(obj, dict):
        items = []
        for k in sorted(obj.keys()):
            v = obj[k]
            sub = canonical(v, f"{path}.{k}", diffs)
            items.append((k, sub[0], sub[1]))
            if diffs is not None and k in VOLATILE_KEYS and sub[1] != sub[0]:
                diffs.append(f"{path}.{k}")
        strict = "{" + ",".join(f"{json.dumps(k, ensure_ascii=False)}:{s}" for k, s, _ in items) + "}"
        stable = "{" + ",".join(f"{json.dumps(k, ensure_ascii=False)}:{v}" for k, s, v in items) + "}"
        return strict, stable
    if isinstance(obj, list):
        parts = [canonical(x, f"{path}[{i}]", diffs) for i, x in enumerate(obj)]
        return ("[" + ",".join(p[0] for p in parts) + "]",
                "[" + ",".join(p[1] for p in parts) + "]")
    if isinstance(obj, float):
        # 12 decimals: enough for rial-level money, tight enough that a real
        # numeric change can never hide inside the rounding
        s = repr(round(obj, 12))
        return s, s
    t = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    return t, t


def summarize(obj):
    out = {}
    if isinstance(obj, dict):
        for k in LIST_KEYS:
            v = obj.get(k)
            if isinstance(v, list):
                out[f"{k}_count"] = len(v)
                if v and isinstance(v[0], dict):
                    out[f"{k}_keys"] = sorted(v[0].keys())
                    out[f"{k}_first"] = json.dumps(v[0], ensure_ascii=False, sort_keys=True)[:400]
        for k in ("status", "count", "rev", "asof_d_even", "source"):
            if k in obj and not isinstance(obj[k], (list, dict)):
                out[k] = obj[k]
        a = obj.get("asof")
        if isinstance(a, dict):
            out["asof"] = a
    return out


def snap_path(tag):
    return os.path.join(tempfile.gettempdir(), "bors_perf_golden", f"{tag}.json.gz")


def do_save(base, tag):
    os.makedirs(os.path.dirname(snap_path(tag)), exist_ok=True)
    data = {}
    for name, path in ENDPOINTS:
        obj, ms, code = fetch(base, path)
        strict, stable = canonical(obj)
        data[name] = {"path": path, "http": code, "ms": round(ms),
                      "sha_strict": hashlib.sha256(strict.encode()).hexdigest()[:16],
                      "sha_stable": hashlib.sha256(stable.encode()).hexdigest()[:16],
                      "bytes": len(strict), "summary": summarize(obj), "json": obj}
        s = data[name]["summary"]
        print(f"  {name:<20} {code}  {ms:7.0f}ms  bytes={data[name]['bytes']:>10,}  "
              f"rows={s.get('data_count', s.get('rows_count', s.get('symbols_count', s.get('candles_count', '—'))))}")
    with gzip.open(snap_path(tag), "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"saved '{tag}' -> {snap_path(tag)}")
    return 0


def diff_tree(a, b, path="$", out=None, limit=40):
    """Every path whose canonical value differs, classified by volatile status."""
    if out is None:
        out = [[], [], set()]
    if len(out[0]) >= limit:
        return out
    if type(a) is not type(b):
        out[0].append(f"{path}: TYPE {type(a).__name__} vs {type(b).__name__}")
        return out
    if isinstance(a, dict):
        for k in set(a) | set(b):
            if k not in a or k not in b:
                if k in VOLATILE_KEYS:
                    out[1].append(f"{path}.{k}")
                else:
                    side = "ADDED (only in after)" if k not in a else "REMOVED (only in before)"
                    out[0].append(f"{path}.{k}: {side}")
            elif k in VOLATILE_KEYS:
                if canonical(a[k])[0] != canonical(b[k])[0]:
                    out[1].append(f"{path}.{k}")
            else:
                diff_tree(a[k], b[k], f"{path}.{k}", out, limit)
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            out[0].append(f"{path}: LENGTH {len(a)} vs {len(b)}")
            return out
        for i, (x, y) in enumerate(zip(a, b)):
            diff_tree(x, y, f"{path}[{i}]", out, limit)
        return out
    sa, sb = canonical(a)
    if sa[0] != sb[0]:
        out[0].append(f"{path}: {sa[0]} -> {sb[0]}")
    return out


def do_check(before, after, report_name="OUTPUT_EQUALITY.json"):
    pa, pb = snap_path(before), snap_path(after)
    for p in (pa, pb):
        if not os.path.exists(p):
            print(f"MISSING snapshot: {p}")
            return 2
    with gzip.open(pa, "rt", encoding="utf-8") as f:
        A = json.load(f)
    with gzip.open(pb, "rt", encoding="utf-8") as f:
        B = json.load(f)
    fails = 0
    report = {"before": before, "after": after, "endpoints": {}, "verdict": ""}
    print(f"\n{'endpoint':<22} {'http':>6} {'bytes before':>13} {'bytes after':>13}  verdict")
    print("-" * 96)
    for name in A:
        a, b = A[name], B.get(name)
        if b is None:
            print(f"{name:<22}  MISSING in after snapshot")
            fails += 1
            continue
        hard, vol = [], []
        diff_tree(a["json"], b["json"], "$", [hard, vol, set()])
        external = a.get("path") in EXTERNAL_PATHS
        verdict = "IDENTICAL" if not hard and not vol else (
            "VOLATILE-ONLY" if not hard else f"DATA-DIFF ({len(hard)})")
        if external and hard:
            verdict = f"EXTERNAL-SOURCE ({len(hard)} drift, not gated)"
        if hard and not external:
            fails += 1
        print(f"{name:<22} {b['http']:>6} {a['bytes']:>13,} {b['bytes']:>13,}  {verdict}"
              + ("" if not hard else f"   e.g. {hard[0][:70]}"))
        report["endpoints"][name] = {
            "verdict": verdict, "external_source": external, "http_before": a["http"], "http_after": b["http"],
            "bytes_before": a["bytes"], "bytes_after": b["bytes"],
            "ms_before": a["ms"], "ms_after": b["ms"],
            "data_diffs": hard[:20], "volatile_diffs": len(vol),
            "summary_before": a["summary"], "summary_after": b["summary"],
        }
    report["verdict"] = "OUTPUTS_EQUAL" if fails == 0 else f"OUTPUTS_DIVERGED({fails})"
    print(f"\n{report['verdict']}")
    out = os.path.join("_audit", "perf", report_name)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"wrote {out}")
    return 0 if fails == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["save", "check"])
    ap.add_argument("--base", default=os.environ.get("BORS_PERF_BASE", "http://127.0.0.1:8000"))
    ap.add_argument("--tag", default="before")
    ap.add_argument("--before", default="before")
    ap.add_argument("--after", default="after")
    ap.add_argument("--report", default="OUTPUT_EQUALITY.json")
    a = ap.parse_args()
    if a.mode == "save":
        return do_save(a.base, a.tag)
    return do_check(a.before, a.after, a.report)


if __name__ == "__main__":
    sys.exit(main())
