# _audit/ra365_phase2_coverage.py — RC4 (مرحلۀِ ۵): coverage-auditِ فقط-خواندنی، قابل‌بازتولید
# هیچ داده‌ای نمی‌سازد؛ فقط پوششِ تاریخِ price_history را با (الف) مرجعِ ره‌آوردِ یخ‌زده
# و (ب) دو مسارۀِ یخ‌زدۀِ خودی (/api/chartِ live در برابرِ /api/chart-db) مقایسه می‌کند
# و هر شکاف را به یکِ طبقه منتسب می‌کند. `market.db` فقط mode=ro باز می‌شود؛ نوشتن ناممکن.
import csv
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DB = f"file:{ROOT}/market.db?mode=ro"
REF = f"{ROOT}/_audit/ra365_ref_bars.json"
PROD = f"{ROOT}/_audit/ra365_product_bars.json"
CORPUS = f"{ROOT}/_audit/ra365_corpus.json"
OUT = f"{ROOT}/_audit/RA365-PHASE2-COVERAGE-2026-10-13.csv"
TEHRAN = timezone(timedelta(hours=3, minutes=30))
KEEP_FROM = "2024-01-01"


def tehran_date(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TEHRAN).date().isoformat()


def ref_dates(R, sym):
    e = R["bars"].get(f"{sym}|type0|D")
    if not e or e.get("status") != 200:
        return set()
    return {tehran_date(b) for b in e["bars"] if b.get("c") and tehran_date(b) >= KEEP_FROM}


def prod_dates(P, sym, path):
    rec = P.get(sym, {}).get(path) or {}
    return {str(c["time"])[:10] for c in (rec.get("candles") or []) if str(c["time"])[:10] >= KEEP_FROM}


def main():
    R = json.load(open(REF, encoding="utf-8"))
    P = json.load(open(PROD, encoding="utf-8"))
    CORP = json.load(open(CORPUS, encoding="utf-8"))
    rows = []
    tot_missing_db = tot_missing_live = 0
    for c in CORP:
        sym = c["sym"]
        rf = ref_dates(R, sym)
        live = prod_dates(P, sym, "live")
        dbp = prod_dates(P, sym, "db")
        # dateهایِ مسارۀِ زنده و بانک از همان ضبطِ یخ‌زدۀِ خودی می‌آیند (بدونِ لمسِ
        # نوشتنِ price_history): dbِ snapshot همان چیزی است که /api/chart-db می‌داد.
        missing_db = sorted(rf - dbp)      # درِ مرجع هست، درِ بانکِ محلی نیست
        missing_live = sorted(rf - live)   # درِ مرجع هست، درِ مسارۀِ زنده نیست
        tot_missing_db += len(missing_db)
        tot_missing_live += len(missing_live)
        # طبقه‌بندیِ شکافِ بانک: اگر مسارۀِ زنده هم ندارد ⇒ شکافِ منبع/دریافت، نه نوشتن
        src_gap = len(rf - live)
        writer_gap = len(live - dbp)       # زنده دارد ولی بانک ندارد ⇒ نوشتن/همگام‌سازی
        rows.append({
            "symbol": sym, "ref_days": len(rf), "live_days": len(live), "db_days": len(dbp),
            "missing_in_db": len(missing_db), "missing_in_live": len(missing_live),
            "writer_gap(live_has_db_missing)": writer_gap,
            "source_gap(neither_has)": src_gap,
            "sample_missing_db": "|".join(missing_db[-8:]),
        })
    with open(OUT, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("نوشته شد (جدید، بی‌بازنویسیِ شاهدِ پیشین):", os.path.basename(OUT))
    print(f"مجموعِ شکافِ بانکِ محلی (از {len(rows)} نماد، {KEEP_FROM}+): {tot_missing_db}")
    print(f"مجموعِ شکافِ مسارۀِ زنده: {tot_missing_live}")
    print("نمونۀِ ۵ سطر:")
    for r in rows[:5]:
        print(f"  {r['symbol']:8s} ref={r['ref_days']} live={r['live_days']} db={r['db_days']} "
              f"missing_db={r['missing_in_db']} writer_gap={r['writer_gap(live_has_db_missing)']} "
              f"source_gap={r['source_gap(neither_has)']}")


if __name__ == "__main__":
    main()
