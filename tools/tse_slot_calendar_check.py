"""اسلات‌به‌اسلات: `[ih]` خودِ سایت در برابرِ `tape_history`ِ بانکِ ما.

تقویم = نشست‌هایِ متمایزِ `tape_history` نزولی بر d_even (۰ = آخرینِ نشست).
فرضِ آزمون: اسلاتِ kِ سایت == تقویم[k]. سه چیز شمرده می‌شود:
  • سایت ردیف دارد، بانک ندارد (شکافِ سینک — همان «تاریخچۀ ناقص»)
  • بانک ردیف دارد، سایت ندارد
  • هر دو دارند ولی `QTotTran5J` نمی‌خواند (اختلافِ مقدار)
همۀ شمارش‌ها به‌تفکیکِ پنجرۀ [0..29] و [0..59] و برایِ نمادهایِ کم‌معامله
(کمتر از ۳۰ ردیفِ غیرصفر) جدا گزارش می‌شود.

اجرا: PYTHONIOENCODING=utf-8 python tools/tse_slot_calendar_check.py
"""
import collections
import io
import json
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
DB = os.environ.get("BORS_DB", "market.db")
CACHE = "_audit/tse_cache_ClosingPriceAll.txt"
FIELDS = ("PClosing", "PDrCotVal", "ZTotTran", "QTotTran5J", "QTotCap",
          "PriceMin", "PriceMax", "PriceYesterday", "PriceFirst")


def parse(txt):
    out, cur = {}, ""
    for row in txt.split(";"):
        if not row:
            continue
        c = row.split(",")
        if len(c) == 11:
            cur, slot, vals = c[0], int(float(c[1])), c[2:]
        elif len(c) == 10:
            slot, vals = int(float(c[0])), c[1:]
        else:
            continue
        out.setdefault(cur, {})[slot] = dict(zip(FIELDS, [float(v) for v in vals]))
    return out


def main():
    if not os.path.exists(CACHE):
        raise SystemExit("ابتدا tools/tse_is_series_probe.py را اجرا کن")
    hist = parse(io.open(CACHE, encoding="utf-8", errors="replace").read())
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cal = [r[0] for r in conn.execute(
        "SELECT DISTINCT d_even FROM tape_history ORDER BY d_even DESC LIMIT 60")]
    print("تقویمِ بانک:", len(cal), "نشست،", cal[-1], "→", cal[0])

    ours = collections.defaultdict(dict)
    for ins, d, vol, pmin, pmax, cap in conn.execute(
            "SELECT ins_code, d_even, q_tot_tran5j, price_min, price_max, q_tot_cap "
            "FROM tape_history WHERE d_even <= ?", (cal[0],)):
        ours[str(ins)][d] = {"vol": vol, "pmin": pmin, "pmax": pmax, "cap": cap}
    print("نماد در بانک:", len(ours), "| نماد در باندِ سایت:", len(hist))

    agg = collections.Counter()
    per_symbol = []
    low_activity = []
    for code, arr in hist.items():
        cal_slot = {k: cal[k] for k in arr if k < len(cal)}
        ob = ours.get(code, {})
        miss_app = miss_site = val_diff = both = 0
        win30_app = win30_site = 0
        for slot, day in cal_slot.items():
            srec, orec = arr[slot], ob.get(day)
            if orec is None:
                miss_site += 1
                if slot < 30:
                    win30_site += 1
                continue
            if slot >= 30:
                continue
            win30_app += 1
            sval = srec["QTotTran5J"] or 0
            oval = orec["vol"] or 0
            both += 1
            if abs(sval - oval) > 0.5:
                val_diff += 1
        for day in ob:
            if day not in cal_slot.values():
                miss_app += 1
        nz = sum(1 for r in arr.values() if r["QTotTran5J"])
        agg["symbols"] += 1
        agg["site_rows_in_window"] += len(cal_slot)
        agg["app_missing_rows"] += miss_site
        agg["app_rows_not_in_site_window"] += miss_app
        agg["compared"] += both
        agg["volume_mismatch"] += val_diff
        agg["site30_missing_in_app"] += win30_site
        if len(cal_slot) < 60:
            agg["site_short_arrays"] += 1
        rec = {"code": code, "site_slots": len(arr), "in_calendar": len(cal_slot),
               "app_missing": miss_site, "app_extra": miss_app,
               "compared": both, "vol_mismatch": val_diff,
               "app_rows": len(ob), "site_nonzero": nz}
        if miss_site or val_diff:
            per_symbol.append(rec)
        if nz < 30:
            low_activity.append({**rec, "site_slots": len(arr)})

    print("\n== جمعِ کل")
    for k in ("symbols", "site_rows_in_window", "app_missing_rows",
              "app_rows_not_in_site_window", "compared", "volume_mismatch",
              "site30_missing_in_app", "site_short_arrays"):
        print(f"   {k}: {agg[k]:,}")
    print("\n== نمادهایِ کم‌معامله (کمتر از ۳۰ اسلاتِ غیرصفر در سایت):", len(low_activity))
    for r in sorted(low_activity, key=lambda x: -x["app_missing"])[:12]:
        print("   ", json.dumps(r, ensure_ascii=False))
    print("\n== ۱۲ نماد با بدترین شکاف (نمونه)")
    for r in sorted(per_symbol, key=lambda x: -x["app_missing"])[:12]:
        print("   ", json.dumps(r, ensure_ascii=False))
    with io.open("_audit/tse_slot_calendar_check.json", "w", encoding="utf-8", newline="") as fh:
        json.dump({"calendar": cal, "totals": dict(agg), "low_activity": low_activity,
                   "gap_symbols": sorted(per_symbol, key=lambda x: -x["app_missing"])[:200]},
                  fh, ensure_ascii=False, indent=1)
    print("wrote _audit/tse_slot_calendar_check.json")


if __name__ == "__main__":
    main()
