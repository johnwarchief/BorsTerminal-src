"""چند رأیِ تابلو از «رد» به «سنجیده نشد» جابه‌جا می‌شوند؟

`tape_flags` سنجش‌ناشدنی را NaN می‌گذارد و تابلو آن را False می‌کند؛ قیف حالا
از شواهدِ خودِ ردیف می‌فهمد که False یعنی «رد» یا «سنجیده نشد». این اسکریپت
همان ردیف‌هایِ زنده را دو بار داوری می‌کند — یک بار با منطقِ پیشین (بدونِ
تمایز) و یک بار با تمایز — و جابه‌جایی‌ها را می‌شمارد. عددِ حدسی در کار نیست.

  python tools/funnel_unmeasured_impact.py [--api http://127.0.0.1:8002]
"""
import argparse
import json
import sys
import urllib.request

sys.path.insert(0, ".")
import funnel_engine as FE  # noqa: E402
from funnel_engine import screening_eligibility  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--api", default="http://127.0.0.1:8002")
ap.add_argument("--out", default="_audit/funnel_unmeasured_impact.json")
a = ap.parse_args()

with urllib.request.urlopen(f"{a.api}/api/market", timeout=120) as r:
    all_rows = json.load(r)["data"]
board = [x for x in all_rows if screening_eligibility(x)[0]]


CHAIN = ("f_susp", "f_noqteh")
orig = FE._tape_unmeasurable


def run(relabeled: bool) -> dict:
    FE._tape_unmeasurable = orig if relabeled else (lambda r, fid: False)
    rows = [dict(x) for x in board]
    return FE.tape_stage(rows, CHAIN)


without = run(False)
withnew = run(True)
FE._tape_unmeasurable = orig

out = {"board_rows_total": len(all_rows), "board_rows": len(board), "chain": list(CHAIN), "presets_note":
       "دو فیلترِ پرمصرفِ نوسان‌گیر؛ بقیه زنجیره‌ها همین مسیر را می‌روند", "steps": []}
for old, new in zip(without["steps"], withnew["steps"]):
    out["steps"].append({
        "filter_id": new["filter_id"],
        "input": new["input_count"],
        "before": {"matched": old["matched_count"], "removed": old["removed_count"],
                   "unmeasured": old["unmeasured_count"]},
        "after": {"matched": new["matched_count"], "removed": new["removed_count"],
                  "unmeasured": new["unmeasured_count"]},
        "moved_reject_to_unmeasured": old["removed_count"] - new["removed_count"],
    })
out["survivors_before"] = len(without["survivors"])
out["survivors_after"] = len(withnew["survivors"])
# نمادهایی که فقط به‌خاطرِ تمایز به گامِ بعد رفتند
sb = {str(r.get("symbol")) for r in without["survivors"]}
sa = {str(r.get("symbol")) for r in withnew["survivors"]}
out["newly_forwarded_count"] = len(sa - sb)
out["newly_forwarded_sample"] = sorted(sa - sb)[:25]
json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "newly_forwarded_sample"}, ensure_ascii=False, indent=1))
print("نمونه:", ", ".join(out["newly_forwarded_sample"][:10]))
