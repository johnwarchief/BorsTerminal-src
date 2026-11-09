#!/usr/bin/env python
"""وکتورهایِ نمادهایِ واقعی برایِ پاریتیِ موتور FTS (پایتون ← Go).

برخلافِ gen_fts_vectors.py (سری‌هایِ ساختگیِ نام‌دار)، اینجا سریِ واقعیِ همان
`_fts_analysis_series` تولید می‌شود که `/api/fts/{symbol}` می‌بیند؛ اما مقایسه
رویِ **همان کندل‌ها** انجام می‌شود تا اختلافِ موتور از اختلافِ منبعِ داده جدا شود.
خروجی یک فایلِ موقت است (پیش‌فرض `_audit/fts_real_vectors.json`) و در گیت
کامیت نمی‌شود؛ تستِ Go با `BORS_FTS_REAL_VECTORS=<path>` آن را می‌خواند.

اجرا:
  python tools/parity/gen_fts_real_vectors.py --db market.db --count 6
  cd backend-go && BORS_FTS_REAL_VECTORS=../_audit/fts_real_vectors.json \
      go test ./internal/chart -run TestFTSRealSymbolParity -v
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
DEFAULT_OUT = os.path.join(ROOT, "_audit", "fts_real_vectors.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare(db_path):
    tmp = tempfile.mkdtemp(prefix="bors-fts-real-")
    shutil.copy2(db_path, os.path.join(tmp, "market.db"))
    user = os.path.join(os.path.dirname(os.path.abspath(db_path)), "user.db")
    if os.path.exists(user):
        shutil.copy2(user, os.path.join(tmp, "user.db"))
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_CHART_CDN"] = "off"
    os.environ["BORS_CODAL_OFFLINE"] = "1"
    os.environ["BORS_NO_FETCH_LOOPS"] = "1"
    os.environ["BORS_TREND_ENGINE"] = "legacy"
    return tmp


def candidate_symbols(db_path, limit):
    conn = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    try:
        rows = conn.execute(
            "SELECT symbol, COUNT(*) c FROM price_history "
            "GROUP BY symbol ORDER BY c DESC LIMIT ?", (limit * 6,)).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "market.db"))
    ap.add_argument("--symbols", default="")
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--slices", type=int, default=1)
    ap.add_argument("--slice-bars", type=int, default=90)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()
    if not os.path.exists(args.db):
        print("market DB not found:", args.db, file=sys.stderr)
        return 2
    prepare(args.db)
    import api.chart as ch

    syms = ([s.strip() for s in args.symbols.split(",") if s.strip()]
            if args.symbols else candidate_symbols(args.db, args.count))
    cases = []
    used = set()
    for sym in syms:
        if sym in used:
            continue
        try:
            candles, basis = ch._fts_analysis_series(sym)
        except Exception as e:
            print("skip", sym, "series error:", e)
            continue
        if len(candles) < 120:
            continue
        used.add(sym)
        variants = [("latest", None)]
        for j in range(args.slices):
            idx = len(candles) - 1 - args.slice_bars * (j + 1)
            if idx < 60:
                continue
            as_of = str(candles[idx]["time"])[:10]
            variants.append(("slice%02d" % (j + 1), as_of))
        for label, as_of in variants:
            seg = ([c for c in candles if str(c["time"])[:10] <= as_of]
                   if as_of else candles)
            if len(seg) < 60:
                continue
            out = ch._fts_analyze_candles(sym, seg)
            cases.append({"name": "%s@%s" % (sym, label), "symbol": sym,
                          "as_of": as_of, "basis": basis,
                          "bars": len(seg), "candles": seg, "analyze": out})
        print("added", sym, "bars", len(candles), "cases", len(variants))
        if len(used) >= args.count:
            break
    if not used:
        print("no usable symbols", file=sys.stderr)
        return 1
    data = {
        "schema": "fts-real-vectors-v1",
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "db_sha256": sha256(args.db),
        "symbols": sorted(used),
        "cases": cases,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False)
        f.write("\n")
    print("wrote", args.out, os.path.getsize(args.out), "bytes",
          "symbols", len(used), "cases", len(cases))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
