#!/usr/bin/env python3
"""import_capture.py — خروجیِ `capture_rahavard.mjs` را به یک سریِ نرمال تبدیل می‌کند.

چرا این فایل لازم است: درایور ضبط، دنبالهٔ خامِ API را همان‌طور که می‌آید
ذخیره می‌کند؛ مقایسهٔ §4 باید تاریخِ ISO، کلیدِ یکتا و شمارشِ تکرارها داشته
باشد. این‌جا هیچ تخمینی زده نمی‌شود: هر فیلدی که منبع نداد `null` می‌ماند و
نامش در `unavailable` می‌آید. تکرارِ ماهانه (هر کندل ~۳ بار با مقادیرِ یکسان)
از تضاد (همان کلید، مقدارِ متفاوت) جدا شمرده می‌شود.

خروجی:
  bars.ndjson.gz   یک ردیف برایِ (asset_id, resolution, type, date)
  coverage.json    پوششِ هر سری + شمارشِ تکرار/تضاد
  summary.json     متادیتایِ ضبط و هش‌ها (بی‌توکن/بی‌کوکی)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timezone

FIELDS = ("open", "high", "low", "close", "volume")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_date(value):
    """ISO، epoch ثانیه یا میلی‌ثانیه را به YYYY-MM-DD می‌برد؛ ناشناخته None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        x = float(value)
        if x > 1e11:              # میلی‌ثانیه
            x /= 1000.0
        try:
            return datetime.fromtimestamp(x, tz=timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return norm_date(int(text))
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10] if len(text) >= 10 else None


def type_of(series) -> str:
    ticker = str(series.get("ticker") or "")
    tail = ticker.rsplit(":", 1)[-1]
    if tail.startswith("type"):
        return tail
    return "type0" if series.get("adjust") == "raw" else "type7"


def same_bar(a, b) -> bool:
    for field in FIELDS:
        va, vb = a.get(field), b.get(field)
        if va is None or vb is None:
            if va is not vb:
                return False
            continue
        if abs(float(va) - float(vb)) > 1e-9:
            return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with io.open(args.inp, encoding="utf-8") as fh:
        doc = json.load(fh)
    source = doc.get("source") or {}
    series_list = doc.get("series") or []
    if not series_list:
        print("no series in capture", file=sys.stderr)
        return 2

    os.makedirs(args.out, exist_ok=True)
    rows, seen = [], {}
    coverage, totals = {}, {"rows": 0, "duplicate_rows_dropped": 0,
                            "conflicting_duplicates": 0, "undated_rows": 0,
                            "null_field_rows": 0}
    for series in series_list:
        asset = series.get("asset_id")
        symbol = series.get("symbol")
        resolution = str(series.get("resolution") or "")
        typ = type_of(series)
        basis = series.get("basis")
        ckey = (asset, resolution, typ)
        cov = coverage.setdefault("|".join(str(x) for x in ckey), {
            "asset_id": asset, "symbol": symbol, "resolution": resolution,
            "type": typ, "basis": basis, "adjust": series.get("adjust"),
            "status": series.get("status"), "rows": 0,
            "first": None, "last": None, "duplicate_rows_dropped": 0,
            "conflicting_duplicates": 0, "undated_rows": 0,
            "unavailable": {},
        })
        for bar in series.get("bars") or []:
            day = norm_date(bar.get("utc") if bar.get("utc") is not None
                            else bar.get("time"))
            if not day:
                cov["undated_rows"] += 1
                totals["undated_rows"] += 1
                continue
            row = {"asset_id": asset, "symbol": symbol,
                   "resolution": resolution, "type": typ, "basis": basis,
                   "adjust": series.get("adjust"), "date": day}
            unavailable = []
            for field in FIELDS:
                val = bar.get(field)
                row[field] = val
                if val is None:
                    unavailable.append(field)
            if unavailable:
                row["unavailable"] = unavailable
                cov["unavailable"][",".join(unavailable)] = \
                    cov["unavailable"].get(",".join(unavailable), 0) + 1
                totals["null_field_rows"] += 1
            key = (asset, resolution, typ, day)
            if key in seen:
                if same_bar(seen[key], row):
                    cov["duplicate_rows_dropped"] += 1
                    totals["duplicate_rows_dropped"] += 1
                else:
                    cov["conflicting_duplicates"] += 1
                    totals["conflicting_duplicates"] += 1
                continue
            seen[key] = row
            rows.append(row)
            cov["rows"] += 1
            totals["rows"] += 1
            cov["first"] = day if not cov["first"] or day < cov["first"] else cov["first"]
            cov["last"] = day if not cov["last"] or day > cov["last"] else cov["last"]

    rows.sort(key=lambda r: (str(r["asset_id"]), r["resolution"], r["type"], r["date"]))
    bars_path = os.path.join(args.out, "bars.ndjson.gz")
    with gzip.open(bars_path, "wt", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    summary = {
        "capture_file": os.path.basename(args.inp),
        "capture_sha256": sha256_file(args.inp),
        "source": {k: source.get(k) for k in
                   ("kind", "endpoint", "captured_at", "browser", "types",
                    "resolutions", "countback", "from", "to", "input_sha256")},
        "series": len(series_list),
        "totals": totals,
        "per_resolution": {
            res: sum(1 for r in rows if r["resolution"] == res)
            for res in sorted({r["resolution"] for r in rows})},
        "per_adjust": {
            adj: sum(1 for r in rows if r["adjust"] == adj)
            for adj in sorted({str(r["adjust"]) for r in rows})},
        "bars_sha256": sha256_file(bars_path),
    }
    with io.open(os.path.join(args.out, "coverage.json"), "w", encoding="utf-8") as fh:
        json.dump({"series": list(coverage.values()),
                   "totals": totals}, fh, ensure_ascii=False, indent=1)
    with io.open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0 if rows else 2


if __name__ == "__main__":
    sys.exit(main())
