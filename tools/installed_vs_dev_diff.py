# -*- coding: utf-8 -*-
"""داوریِ «باگِ کد یا باگِ داده» با گرفتنِ همان نماد/همان فیلد در یک لحظه از
دو بکاند: اپِ نصبی (پیش‌فرض ۸۰۰۱) و بکاندِ توسعه.

چرا یک لحظه: نمونه‌برداری در دو ساعتِ مختلف دو هشدارِ جعلیِ «شکافِ داده»
ساخته است. چرا scope نرمال: شمارِ کلِ بانک ردیف‌هایِ مردهٔ نشست‌هایِ پیش را هم
می‌گیرد؛ اینجا فقط ردیف‌هایِ `d_even = max` داوری می‌شوند.

قیدِ مهم: دو بکاند باید **همان بانک** را بخوانند. اگر یکی کپیِ کهنه‌ای از بانک
باز کند (سنجشِ ۱۴۰۵-۰۷-۰۸) اختلافِ ستون‌هایِ پنجره و عضویتِ فیلترها می‌تواند
فقط کهنه‌بودنِ همان کپی باشد، نه باگِ کد — و درِ ویندوز دو پروسه می‌توانند یک
پورت را هم‌زمان bind کنند، پس «پاسخِ دِو» ممکن است سرورِ نشستِ پیشین باشد.

    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tools/installed_vs_dev_diff.py \
        --installed http://127.0.0.1:8001 --dev http://127.0.0.1:8003 \
        --out _audit/inst_vs_dev_<stamp>.json
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import urllib.request

FLAGS = ("f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh")
# ستون‌هایی که دو پنجرۀ روزانۀ تابلو می‌سازند؛ اختلافِ این‌ها یعنی کد یا پنجره
# فرق دارد، نه دادهٔ زنده. نسبت‌هایِ حجم این‌جا نیستند چون تیکِ زنده در دو بکاند
# در دو لحظهٔ متفاوت خوانده می‌شود و اختلافِ آن‌ها بی‌معنی است.
WINDOW_COLS = ("month_avg_vol", "prev_day_vol", "d1_vol", "min30_low", "max30_high",
               "prior30_vol", "hist_sessions", "min_low_29")


def fetch(url: str):
    with urllib.request.urlopen(url.rstrip("/") + "/api/market", timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def live_rows(payload):
    data = payload.get("data") or []
    if not data:
        return [], None
    top = max(int(r.get("d_even") or 0) for r in data)
    return [r for r in data if int(r.get("d_even") or 0) == top], top


def summarize(payload):
    rows, top = live_rows(payload)
    by_sym = {r.get("symbol"): r for r in rows}
    flags = {k: {r["symbol"] for r in rows if r.get(k)} for k in FLAGS}
    return {"d_even": top, "live_rows": len(rows), "flags": flags, "by_symbol": by_sym}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--installed", default="http://127.0.0.1:8001")
    ap.add_argument("--dev", default="http://127.0.0.1:8003")
    ap.add_argument("--out", default="")
    ap.add_argument("--samples", default=12, type=int)
    args = ap.parse_args()

    t0 = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fi = ex.submit(fetch, args.installed)
        fd = ex.submit(fetch, args.dev)
        inst, dev = fi.result(), fd.result()
    t1 = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    si, sd = summarize(inst), summarize(dev)
    report = {
        "taken_at_first_response": t0, "taken_at_last_response": t1,
        "installed_url": args.installed, "dev_url": args.dev,
        "scope": {"installed_d_even": si["d_even"], "dev_d_even": sd["d_even"],
                  "installed_live_rows": si["live_rows"], "dev_live_rows": sd["live_rows"]},
        "filters": {}, "window_diff_rows": 0, "window_diff_samples": [],
    }
    for k in FLAGS:
        a, b = si["flags"][k], sd["flags"][k]
        report["filters"][k] = {
            "installed": len(a), "dev": len(b), "shared": len(a & b),
            "only_installed": sorted(a - b)[:20], "only_dev": sorted(b - a)[:20],
        }

    # اختلافِ ستون‌هایِ پنجره برایِ همان ردیف‌ها (نه اختلافِ تیکِ زنده)
    common = set(si["by_symbol"]) & set(sd["by_symbol"])
    for sym in sorted(common):
        ri, rd = si["by_symbol"][sym], sd["by_symbol"][sym]
        dif = {}
        for c in WINDOW_COLS:
            vi, vd = ri.get(c), rd.get(c)
            if isinstance(vi, float) and isinstance(vd, float):
                if abs(vi - vd) > max(1e-6, abs(vd) * 1e-6):
                    dif[c] = [vi, vd]
            elif vi != vd:
                dif[c] = [vi, vd]
        if dif:
            report["window_diff_rows"] += 1
            if len(report["window_diff_samples"]) < args.samples:
                report["window_diff_samples"].append({"symbol": sym, "cols": dif})
    report["window_diff_share_pct"] = round(
        100.0 * report["window_diff_rows"] / max(1, len(common)), 2)

    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text[:200000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
