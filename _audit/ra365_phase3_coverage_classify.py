# _audit/ra365_phase3_coverage_classify.py — RC4 (بخشِ ۵): بازتولیدِ مستقل + طبقه‌بندیِ شکلِ شکاف
# چرا: مرحلۀِ ۲ عددِ «۴۳۴۷ از نوعِ writer_gap» را با یک سطل داد. این مأموریت می‌گوید آن شمار
# را درست فرض نکن و شکاف را بینِ منشأها تفکیک کن. اینجا همان ضبطِ یخ‌زدۀِ خودی (/api/chart
# زنده در برابرِ /api/chart-db) و مرجعِ ره‌آورد خوانده می‌شود و هر نماد بر پایۀِ «کجایِ بازه
# غایب است» دسته می‌خورد؛ market.db فقط mode=ro. هیچ داده‌ای ساخته نمی‌شود.
#
# دسته‌ها (شکل‌محور، قابل‌برگشت به کدِ writer):
#   depth_old_end : تاریخ‌هایِ مفقود همه پیش از MIN(date)ِ بانک → truncationِ backfill=False
#   recent_tail   : مفقودها همه پس از MAX(date)ِ بانک → نشستِ افتاده درِ دورۀِ خاموشِ sync
#   interior      : مفقود میانِ MIN..MAXِ بانک → حلقۀِ increment هرگز میانیِ پر‌نشده را برنمی‌دارد
#   mixed         : ترکیبِ این‌ها
#   whole_symbol  : نماد درِ بانک سطر ندارد ولی درِ زنده دارد → mapping/ins_code یا هرگز-دریافت
#   source_gap    : نه زنده دارد نه بانک (درِ مرحلۀِ ۲ صفر بود؛ اینجا دوباره سنجیده می‌شود)
import csv
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD = f"{ROOT}/_audit/ra365_product_bars.json"
CORPUS = f"{ROOT}/_audit/ra365_corpus.json"
DB = f"file:{ROOT}/market.db?mode=ro&immutable=1"
OUT = f"{ROOT}/_audit/RA365-PHASE3-COVERAGE-CLASS-2026-10-13.csv"


def series_dates(rec):
    return sorted({str(c["time"])[:10] for c in (rec.get("candles") or [])})


def main():
    P = json.load(open(PROD, encoding="utf-8"))
    CORP = json.load(open(CORPUS, encoding="utf-8"))
    con = sqlite3.connect(DB, uri=True)
    rows = []
    tot = {k: 0 for k in ("depth_old_end", "recent_tail", "interior", "mixed", "whole_symbol", "source_gap")}
    tot_days = 0
    for c in CORP:
        sym = c["sym"]
        rec = P.get(sym) or {}
        live = set(series_dates(rec.get("live") or {}))
        db = set(series_dates(rec.get("db") or {}))
        # بانکِ امروز (ro) — برایِ این‌که ببینیم آیا سطرهایِ میانیِ افتاده هنوز درِ price_history هستند
        ph = {r[0] for r in con.execute(
            "SELECT DISTINCT date FROM price_history WHERE symbol=? OR symbol=?", (sym, sym))}
        missing_live = live - db          # زنده دارد، بانکِ snapshot ندارد (همان writer_gap)
        missing_src = (live - db) - ph    # و درِ بانکِ زنده هم نیست ⇒ واقعاً هنوز غایب
        if not db and live:
            cat = "whole_symbol"
        elif not missing_live:
            cat = None
        else:
            lo, hi = min(db), max(db)
            before = sum(1 for d in missing_live if d < lo)
            after = sum(1 for d in missing_live if d > hi)
            mid = len(missing_live) - before - after
            flags = sum([before > 0, after > 0, mid > 0])
            cat = "mixed" if flags > 1 else ("depth_old_end" if before else
                  ("recent_tail" if after else "interior"))
        if cat:
            tot[cat] += 1
            tot_days += len(missing_live)
        rows.append({"symbol": sym, "live_days": len(live), "db_days": len(db),
                     "price_history_rows_now": len(ph),
                     "missing_live_vs_db": len(missing_live),
                     "still_absent_in_live_db": len(missing_src),
                     "before_db_min": sum(1 for d in missing_live if db and d < min(db)),
                     "after_db_max": sum(1 for d in missing_live if db and d > max(db)),
                     "interior": sum(1 for d in missing_live if db and min(db) <= d <= max(db)),
                     "class": cat or "no_gap",
                     "sample": "|".join(sorted(missing_live)[:6])})
    con.close()
    hdr = list(rows[0].keys())
    with open(OUT, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=hdr)
        w.writeheader()
        w.writerows(rows)
    print(f"نوشته شد: {os.path.basename(OUT)}")
    print(f"مجموعِ روزهایِ مفقود (live دارد، db ندارد) درِ پنجرۀِ snapshot: {tot_days} در {len(CORP)} نماد")
    print("تعدادِ نماد بر پایۀِ شکلِ شکاف:")
    for k, v in tot.items():
        print(f"  {k:16s} {v}")
    ws = [r for r in rows if r["class"] == "whole_symbol"]
    print(f"\nنمادهایِ whole_symbol (درِ بانکِ snapshot هیچ سطر ندارند ولی زنده دارد): {[r['symbol'] for r in ws]}")
    still = sum(r["still_absent_in_live_db"] for r in rows)
    print(f"روزهایی که حتی درِ price_historyِ زندهٔ امروز هم نیستند (باید backfill شوند): {still}")


if __name__ == "__main__":
    main()
