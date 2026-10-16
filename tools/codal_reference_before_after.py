import argparse
import csv
import json
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fts_engine as FE
import codal_periods as CP

ap = argparse.ArgumentParser()
ap.add_argument("--db", default="market.db")
ap.add_argument("--out", default="_audit/codal_ca2_before_after.csv")
_a = ap.parse_args()
db = os.path.abspath(_a.db).replace("\\", "/")
c = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
c.row_factory = sqlite3.Row

# همان دو قاعده، فقط برایِ نمادهایی که قاعدهٔ تازه ردیفِ دیگری می‌گزیند.
# «تازه» = خودِ لایۀ canonical (`fts_engine.quarter_reference_rows`)؛ این ابزار
# قاعدۀ سوم نمی‌سازد، فقط ردیفِ «قدیم» (ORDER BY واژگانیِ publish_date) را در
# برابرِ ردیفِ همان تابع می‌گذارد و جابه‌جایی را می‌شمارد.
rows_by_slot = {}
for r in c.execute("SELECT symbol, period_end, period_months, report_kind,"
                   " tracing_no, title, publish_date, revenue, gross_profit,"
                   " operating_profit, net_profit, basic_eps"
                   " FROM financial_statements WHERE " + CP.DATED_SQL +
                   " ORDER BY period_end DESC, publish_date DESC"):
    rows_by_slot.setdefault(
        (r["symbol"], r["period_end"], r["period_months"], r["report_kind"]),
        []).append(dict(r))

out = []
for k, rows in rows_by_slot.items():
    if len(rows) < 2:
        continue
    cur = rows[0]
    new = FE.quarter_reference_rows(rows, limit=len(rows))[0]
    if int(cur["tracing_no"]) == int(new["tracing_no"]):
        continue
    moved = tuple(cur[x] for x in FE.FS_NUMBER_KEYS) != tuple(new[x] for x in FE.FS_NUMBER_KEYS)
    out.append({"symbol": k[0], "period_end": k[1], "period_months": k[2],
                "numbers_moved": int(moved),
                "old_tracing_no": cur["tracing_no"], "old_rev": cur["revenue"],
                "old_gp": cur["gross_profit"], "old_eps": cur["basic_eps"],
                "old_pub": cur["publish_date"], "old_title": (cur["title"] or "")[:80],
                "new_tracing_no": new["tracing_no"], "new_rev": new["revenue"],
                "new_gp": new["gross_profit"], "new_eps": new["basic_eps"],
                "new_pub": new["publish_date"], "new_title": (new["title"] or "")[:80],
                "new_is_subsidiary": int(bool(FE.title_entity_suffix(new["title"]))),
                "old_is_subsidiary": int(bool(FE.title_entity_suffix(cur["title"])))})

out.sort(key=lambda d: (-d["numbers_moved"], d["symbol"]))
with open(_a.out, "w", encoding="utf-8", newline="") as fo:
    w = csv.DictWriter(fo, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)

n = len(out)
nm = sum(d["numbers_moved"] for d in out)
sub_new = sum(d["new_is_subsidiary"] for d in out)
sub_old = sum(d["old_is_subsidiary"] for d in out)
own_to_sub = sum(1 for d in out if d["old_is_subsidiary"] == 0 and d["new_is_subsidiary"] == 1)
print("اسلاتِ چندردیفی (کل بانک):", len([1 for v in rows_by_slot.values() if len(v) > 1]))
print("اسلاتی که ردیفش عوض می‌شود:", n, "| عددش عوض می‌شود:", nm)
print("ردیفِ برگزیده شرکتِ فرعی است — نو:", sub_new, "قدیم:", sub_old)
print("از ردیفِ خودِ نماد به شرکتِ فرعی:", own_to_sub)
print("\nنمونۀ عددجابه‌جا:")
for d in out[:8]:
    print("  %-10s %s pm=%s | قدیم rev=%s gp=%s eps=%s pub=%s" %
          (d["symbol"], d["period_end"], d["period_months"], d["old_rev"], d["old_gp"],
           d["old_eps"], d["old_pub"]))
    print("  %-10s %s          | نو    rev=%s gp=%s eps=%s pub=%s  [%s]" %
          ("", "", d["new_rev"], d["new_gp"], d["new_eps"], d["new_pub"],
           (d["new_title"] or "")[:58]))
