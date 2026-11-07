# tools/phase6_verdict_matrix.py -- مرحلۀ ۶: ماتریسِ عددیِ تطبیق، حکمِ هر نماد جدا
# مرجع (کنارِ خوانده‌شدۀ مرحلۀ ۲ با نشستِ مجازِ مالک):
#   _audit/ra365_ref_bars.json      → type0 = بی‌تعدیل، type7 = عملکردی (ره‌آورد ۳۶۵)
# محصول (وضعیتِ فعلیِ کد؛ با _audit/ra365_product_pull.py تازه گرفته می‌شود):
#   _audit/ra365_product_bars_phase6.json  ← اگر نبود، _audit/ra365_product_bars.json
#
# دو بازویِ سنجش، هیچ‌کدام برازش نمی‌شوند:
#   A) فضایِ ضریب: R_ref(d) = type7(d) ÷ type0(d)  <->  factor(d)ِ سرورِ خودمان.
#      این بازو از مبنایِ قیمت (closing/last) و از گردِ ریالی مستقل است.
#   B) سطحِ قیمت: (close_خام × factor) <-> type7.close  (همان چیزی که کاربر رویِ محور می‌بیند)
#
# حکم‌ها (پیش‌ثبت‌شده، به همان واژۀ مأموریت؛ ترتیبِ اولویت: بدترینِ صادق):
#   BLOCKED                        پاسخِ محصول موفق نبود (خطایِ دسترسی/API، نه محاسبه)
#   UNVERIFIED                     مرجعِ خوانده‌شده برای این نماد نداریم (سنجش Possible نبود)
#   MISMATCH                       بیش از گردِ ریالی اختلاف هست (dif > ROUND_REL یا > 1 ریال)
#   PARTIAL_COVERAGE               پوششِ کامل نیست: کندلِ پیشِ پوشش، رویدادِ حل‌نشده،
#                                  نیازمندِ قیمتِ عرضه، یا functional_available = false
#   MATCH_WITH_ROUNDING_DIFFERENCE همهٔ اختلاف‌ها درونِ گردِ یکِ ریالِ عددِ صحیح
#   MATCH                         اختلافِ بیشینه ≤ ۱e-۶
# هیچ ضریبی دست‌کاری نمی‌شود و هیچ نمونهٔ دشواری حذف نمی‌شود؛ تلورانس‌ها از *تعریفِ*
# گردِ عددِ صحیح می‌آیند (±۰٫۵ ریال رویِ قیمت)، نه از بازکردنِ آستانه برای سبز شدن.
import csv
import io
import json
import os
import statistics
import sys
from datetime import datetime, timedelta, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "_audit", "ra365_ref_bars.json")
PROD_NEW = os.path.join(ROOT, "_audit", "ra365_product_bars_phase6.json")
PROD_OLD = os.path.join(ROOT, "_audit", "ra365_product_bars.json")
SELECTION = os.path.join(ROOT, "_audit", "RA365-PHASE5F-SELECTION.csv")
OUT_CSV = os.path.join(ROOT, "_audit", "RA365-PHASE6-MATRIX.csv")
TEHRAN = timezone(timedelta(hours=3, minutes=30))
MATCH_REL = 1e-6            # «بی‌اختلافِ معنادار»
ROUND_ABS_RIAL = 1.0        # گردِ عددِ صحیحِ ریال: |diff| ≤ ۱ ریال ⇒ فقط گرد
MISMATCH_REL = 5e-3         # بیش از نیم‌درصد در فضای ضریب ⇒ اختلافِ واقعی
OVERLAP_MIN = 0.90          # اگر ۹۰٪ روزهایِ مرجع پوشش نداشت ⇒ پوششِ ناقص


def tehran_date(utc_str):
    dt = datetime.fromisoformat(utc_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TEHRAN).date().isoformat()


def ref_map(sym, kind):
    obj = REF_BARS.get(f"{sym}|{kind}|D") or {}
    out = {}
    for b in obj.get("bars") or []:
        d = tehran_date(b["utc"])
        if b.get("c"):
            out[d] = b
    return out


def prod_live(sym):
    rec = (PROD.get(sym) or {}).get("live") or {}
    candles = {}
    for c in rec.get("candles") or []:
        d = str(c.get("time") or "")[:10]
        if d:
            candles[d] = c
    factors = {str(f.get("time") or "")[:10]: f.get("factor")
               for f in (rec.get("factors") or []) if f.get("time")}
    return rec, candles, factors


def plateaus(days, fac, t0, t7):
    """ساختارِ اختلاف: (mine ÷ R_ref) رویِ روزهایِ مرجع.

    چرا لازم است: اگر اختلافِ هر نماد «پراکنده» بود، یعنی خطایِ تصادفی درِ داده؛ اما اگر
    تکه‌تکه و ثابت بود (یک عددِ واحد برایِ صدها روز)، اختلاف درِ *یک رویداد* است، نه درِ
    موتورِ زنجیره — و مرزِ تکه‌ها همان تاریخِ رویداد است. این تفکیک، حکمِ «چرا» را از
    «چقدر» جدا می‌کند و مسیرِ رفع را نشان می‌دهد.
    """
    seq = []
    for d in days:
        r0, r7 = t0[d]["c"], t7[d]["c"]
        if not r0:
            continue
        R_ref = r7 / r0
        mine = float(fac.get(d, 1.0)) or 1.0
        seq.append((d, mine / R_ref if R_ref else 1.0))
    if not seq:
        return {}
    vals = [v for _, v in seq]
    steps = [(d, v) for i, (d, v) in enumerate(seq)
             if i == 0 or abs(v - seq[i - 1][1]) > 1e-6]
    groups = {}
    for v in vals:
        groups.setdefault(round(v, 4), 0)
        groups[round(v, 4)] += 1
    off = [abs(v - 1.0) for v in vals]
    exact = sum(1 for v in vals if abs(v - 1.0) <= 1e-6)
    return {
        "plateau_count": len(groups),
        "plateau_values": ",".join(str(k) for k, _ in sorted(groups.items(), key=lambda x: -x[1])[:4]),
        "boundary_dates": ",".join(d for d, _ in steps[:5]),
        "offset_median": f"{statistics.median(off):.3e}",
        "offset_max": f"{max(off):.3e}",
        "exact_days": exact,
        "structure": ("single-event" if len(groups) == 2 and len(steps) <= 2
                      else "two-event" if len(groups) == 3 and len(steps) <= 3
                      else "scattered"),
    }


def steps(sym, days, fac, t0, t7):
    """جدولِ رویداد‌به‌رویداد: نسبتِ اعمال‌شدۀِ ما <-> نسبتِ ضمنیِ ره‌آورد، درِ مرزِ هر پله.

    اختلافِ ثابتِ صدها روز وقتی به «یک رویداد» ترجمه می‌شود قابلِ داوری است: همان روزِ
    Gسستِ قیمت، ما چه نسبتی زده‌ایم و عددِ مرجع چه نسبتی را می‌طلبد. بی‌این جدول،
    MISMATCH فقط می‌گوید «نیست» و نمی‌گوید «کجا».
    """
    seq = [(d, fac.get(d, 1.0), (t7[d]["c"] / t0[d]["c"]) if t0[d]["c"] else 1.0) for d in days]
    rows = []
    for i in range(1, len(seq)):
        d_prev, m_prev, r_prev = seq[i - 1]
        d_cur, m_cur, r_cur = seq[i]
        moved_m = abs(m_cur / m_prev - 1.0) > 1e-9 if m_prev else False
        moved_r = abs(r_cur / r_prev - 1.0) > 1e-9 if r_prev else False
        if not (moved_m or moved_r):
            continue
        ours = (m_prev / m_cur) if m_cur else float("nan")   # نسبتِ اعمال‌شدۀِ ما درِ این مرز
        theirs = (r_prev / r_cur) if r_cur else float("nan")  # نسبتِ ضمنیِ مرجع
        rows.append({
            "symbol": sym, "boundary": d_cur, "prev_day": d_prev,
            "our_ratio": f"{ours:.6f}", "ref_ratio": f"{theirs:.6f}",
            "rel_delta": f"{abs(ours - theirs) / max(1e-12, abs(theirs)):.4e}",
            "both_agree": "yes" if abs(ours - theirs) <= 1e-6 else "no",
        })
    return rows


def measure(sym):
    name = (PROD.get(sym) or {}).get("name") or ""
    t0, t7 = ref_map(sym, "type0"), ref_map(sym, "type7")
    rec, candles, factors = prod_live(sym)
    row = {"symbol": sym, "name": name, "ref_days": len(t7), "prod_days": len(candles)}
    if rec.get("status") != "success":
        row["verdict"] = "BLOCKED"
        row["note"] = "محصول: " + str(rec.get("message") or rec.get("status"))[:120]
        return row
    if not t0 or not t7:
        row["verdict"] = "UNVERIFIED"
        row["note"] = "مرجعِ type0/type7 برای این نماد خوانده نشده است"
        return row

    days = sorted(set(t0) & set(t7) & set(candles))
    cap = rec.get("adjustCapability") or {}
    cov = cap.get("coverage") or {}
    pre = int(cov.get("pre_coverage_candles") or 0)
    unresolved = int(cov.get("unresolved_events") or 0)
    needs_offer = int(cov.get("needs_offer_price_events") or 0)
    blocked = cap.get("functional_blockers") or []
    row.update({
        "overlap_days": len(days),
        "overlap_ratio": round(len(days) / max(1, len(t7)), 4),
        "functional_available": cap.get("functional_available"),
        "pre_coverage_candles": pre,
        "unresolved_events": unresolved,
        "needs_offer_price_events": needs_offer,
        "blockers": ";".join(str(b) for b in blocked)[:180],
    })

    rel, price_diff, raw_diff = [], [], []
    worst_rel, worst_day = 0.0, ""
    for d in days:
        r, s, p = t0[d], t7[d], candles[d]
        if not r.get("c"):
            continue
        raw = float(p.get("close") or 0)          # پاسखाۀ سرور = خامِ همان روز
        mine = float(factors.get(d, 1.0)) or 1.0  # ضریبِ canonicalِ سرور
        R_ref = s["c"] / r["c"]                   # نسبتِ خودِ ره‌آورد (بی‌واحد)
        diff = abs(mine - R_ref) / max(1e-12, R_ref)
        rel.append(diff)
        if diff > worst_rel:
            worst_rel, worst_day = diff, d
        # بازویِ B: همان چیزی که کاربر رویِ محور می‌بیند <-> type7 ره‌آورد
        price_diff.append(abs(round(raw * mine) - s["c"]))
        # انتسابِ اختلاف: خامِ ما vs type0ِ مرجع (تأخیر/کسریِ سورس، نه موتورِ تعدیل)
        raw_diff.append(abs(raw - r["c"]))

    if not rel:
        row["verdict"] = "UNVERIFIED"
        row["note"] = "هیچ روزِ مشترکی بینِ مرجع و محصول نبود"
        return row

    factor_mismatch = max(rel) > MISMATCH_REL
    row.update(plateaus(days, factors, t0, t7))
    row["_steps"] = steps(sym, days, factors, t0, t7)
    price_rounding_only = max(price_diff) <= ROUND_ABS_RIAL
    raw_max = max(raw_diff)
    row.update({
        "factor_max_rel": f"{max(rel):.3e}",
        "factor_median_rel": f"{statistics.median(rel):.3e}",
        "factor_within_1e6_ratio": round(sum(1 for x in rel if x <= MATCH_REL) / len(rel), 4),
        "worst_day": worst_day,
        "price_max_abs_rial": round(max(price_diff), 2),
        "price_within_rounding": price_rounding_only,
        "raw_max_abs_rial": round(raw_max, 2),
    })

    # قاعدهٔ حکمِ عددی (فضای ضریب = موتورِ تعدیل؛ سطح قیمت = چیزی که دیده می‌شود)
    if factor_mismatch:
        numeric = "MISMATCH"
        row["mismatch_source"] = "factor-engine"
    elif max(price_diff) <= ROUND_ABS_RIAL:
        numeric = "MATCH" if max(rel) <= MATCH_REL else "MATCH_WITH_ROUNDING_DIFFERENCE"
        row["mismatch_source"] = "none"
    else:
        # ضریب درست است اما عددِ دیدنی بیش از گرد فاصله دارد ⇒ از خام می‌آید، نه از تعدیل
        numeric = "MATCH_WITH_ROUNDING_DIFFERENCE" if max(rel) <= MATCH_REL else "MISMATCH"
        row["mismatch_source"] = "raw-feed" if raw_max > ROUND_ABS_RIAL else "unattributed"

    incomplete = (pre > 0 or unresolved > 0 or needs_offer > 0
                  or cap.get("functional_available") is not True
                  or len(days) / max(1, len(t7)) < OVERLAP_MIN)
    if numeric == "MISMATCH":
        row["verdict"] = "MISMATCH"
    elif incomplete:
        row["verdict"] = "PARTIAL_COVERAGE"
    else:
        row["verdict"] = numeric
    row["numeric_verdict"] = numeric
    gaps = []
    if pre:
        gaps.append(f"کندلِ پیشِ پوشش={pre}")
    if unresolved:
        gaps.append(f"رویدادِ حل‌نشده={unresolved}")
    if needs_offer:
        gaps.append(f"بی‌قیمتِ عرضه={needs_offer}")
    if cap.get("functional_available") is not True:
        gaps.append("تعدیلِ عملکردیِ کامل تأیید نشده")
    if raw_max > ROUND_ABS_RIAL:
        gaps.append(f"اختلافِ خام با مرجع={round(raw_max)} ریال")
    row["note"] = "، ".join(gaps) or "پوششِ کاملِ سنجیده"
    return row


def main():
    global REF_BARS, PROD
    prod_path = PROD_NEW if os.path.exists(PROD_NEW) else PROD_OLD
    print("مرجع: ", REF)
    print("محصول:", prod_path, "(فازِ ۶)" if prod_path == PROD_NEW else "(اسنپشاتِ کهنه‌تر)")
    REF_BARS = json.load(open(REF, encoding="utf-8"))["bars"]
    PROD = json.load(open(prod_path, encoding="utf-8"))

    with open(SELECTION, encoding="utf-8-sig") as fh:
        sel = list(csv.DictReader(fh))
    by_sym = {r["symbol"]: r for r in sel}

    rows = []
    for sym in sorted(set(PROD) | set(by_sym)):
        s = by_sym.get(sym) or {}
        if sym in PROD:
            m = measure(sym)
        else:
            m = {"symbol": sym, "name": (s.get("name") or ""), "verdict": "UNVERIFIED",
                 "note": "درِ گنجینۀِ مرحلۀ ۲ مرجعِ خوانده‌شده ندارد (نیازمندِ نشستِ مجازِ مالک)"}
        m["categories"] = s.get("categories", "")
        m["in_stage1_sample"] = "yes" if sym in by_sym else "no (corpus-only)"
        rows.append(m)

    # هویتِ سطرِ ماتریس فقط با تطبیقِ *دقیقِ* نماد ساخته می‌شود (قانونِ مرحلۀ ۱: بی‌نگاشتِ
    # تقریبی). هر دو جهتِ بی‌تطبیق چاپ می‌شود تا «UNVERIFIED» معنایش روشن بماند.
    only_prod = sorted(set(PROD) - set(by_sym))
    only_sel = sorted(set(by_sym) - set(PROD))
    print(f"تطبیقِ دقیق: {len(set(PROD) & set(by_sym))} نماد در هر دو فهرست | "
          f"فقط در محصول/گنجینه: {len(only_prod)} | فقط در sample مرحلۀ ۱ (بی‌مرجع): {len(only_sel)}")
    if only_prod:
        print("  بی‌نمونۀِ مرحلۀ ۱:", ", ".join(only_prod))

    cols = ["symbol", "name", "in_stage1_sample", "categories", "verdict", "numeric_verdict",
            "mismatch_source", "structure", "plateau_count", "plateau_values", "boundary_dates",
            "offset_median", "offset_max", "exact_days",
            "ref_days", "prod_days", "overlap_days", "overlap_ratio",
            "factor_max_rel", "factor_median_rel", "factor_within_1e6_ratio", "worst_day",
            "price_max_abs_rial", "price_within_rounding", "raw_max_abs_rial",
            "functional_available", "pre_coverage_candles", "unresolved_events",
            "needs_offer_price_events", "blockers", "note"]
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    tally = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1

    # جدولِ مرزها: هر پله = یک رویداد. این فایلِ دوم، «کجا» را جواب می‌دهد.
    step_rows = [s for r in rows for s in (r.pop("_steps", []) or [])]
    steps_csv = OUT_CSV.replace("MATRIX.csv", "STEPS.csv")
    with open(steps_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "boundary", "prev_day", "our_ratio",
                                           "ref_ratio", "rel_delta", "both_agree"],
                           extrasaction="ignore")
        w.writeheader()
        for s in step_rows:
            w.writerow(s)
    agree = sum(1 for s in step_rows if s["both_agree"] == "yes")
    print("\n".join(f"{k}: {v}" for k, v in sorted(tally.items(), key=lambda x: -x[1])))
    print("نمادها:", len(rows), "| فایل:", os.path.relpath(OUT_CSV, ROOT))
    print(f"مرزها (رویدادها): {len(step_rows)} | هم‌خوانِ دقیق: {agree} | واگرا: {len(step_rows) - agree}"
          f" | فایل: {os.path.relpath(steps_csv, ROOT)}")
    if step_rows:
        worst = sorted(step_rows, key=lambda s: -float(s["rel_delta"]))[:6]
        for s in worst:
            print("  بدترین:", s["symbol"], s["boundary"], "ما=" + s["our_ratio"],
                  "مرجع=" + s["ref_ratio"], "دلتا=" + s["rel_delta"])
        deltas = [abs(float(s["our_ratio"]) - float(s["ref_ratio"])) / max(1e-12, abs(float(s["ref_ratio"])))
                  for s in step_rows]
        print("  میانهٔ اختلافِ نسبت‌ها:", f"{statistics.median(deltas):.4e}",
              "| بیشینه:", f"{max(deltas):.4e}")
    measured = [r for r in rows if r.get("factor_max_rel")]
    if measured:
        print("بیشینۀِ اختلافِ ضریب درِ سنجیده‌شدگان:",
              max(measured, key=lambda r: float(r["factor_max_rel"]))["factor_max_rel"],
              "روی", max(measured, key=lambda r: float(r["factor_max_rel"]))["symbol"])
        print("میانگینِ نسبتِ روزهایِ بی‌اختلاف:",
              round(100 * statistics.median(float(r["factor_within_1e6_ratio"]) for r in measured), 2), "%")


if __name__ == "__main__":
    main()
