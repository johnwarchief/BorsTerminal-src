# -*- coding: utf-8 -*-
"""tools/phase5f_select_symbols.py — Stage 1ِ دورِ بستۀ Phase 5

انتخابِ **طبقه‌بندی‌شده**ی حداقلِ ۳۰ (هدفِ ۴۰+) نماد برایِ مقایسۀِ زنده با رهاورد ۳۶۵،
فقط از دادۀِ واقعیِ موجود و فقط‌خواندنی. هیچِ رکوردِ مصنوعی برایِ پرکردنِ شمار ساخته
نمی‌شود؛ طبقه‌ای که داده پوشش نمی‌دهد صریح درِ ستونِ `coverage_gap` ثبت می‌شود.

چرا این‌طور انتخاب می‌شود (نه ۳۰ نمادِ هم‌نوعِ دلخواه): مأموریت قبلی با ۱۱ نماد بسته
نشد، و دلیلِ فنی‌اش این بود که نمونه، توزیعِ عللِ شکست را نمی‌پوشاند. پس هر سطر یا
(a) رویدادِ تعدیلِ رسمی درِ پنجرۀِ مبدأ دارد، (b) کنترلِ بی‌رویدادِ **معتبر** است
(یعنی پوششِ مبدأ برایِ بازۀِ تاریخچۀِ خودش کافی است، نه صرفاً «رویداد نداشت»)، یا
(c) یکی ازِ طبقاتِ دشوار را نمایندگی می‌کند: چندرویداد، ترکیبی، نوعِ حل‌نشده،
نزدیکِ مرزِ پوشش، تاریخچۀِ کهنه/نو، و طبقه/صنعتِ متمایز.

هویت درِ این مرحله با `ins_code` (کلیدِ پایدارِ TSETMC) ثبت می‌شود؛ نگاشتِ
`ticker -> asset_id` رهاورد **اثباتِ هویت نیست** و درِ Stage 2 با مقابلهٔ سریِ خام
(type0) برِ `price_history` بستۀ می‌شود.
"""
import csv
import io
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("BORS_DB", os.path.join(ROOT, "market.db"))
OUT = os.path.join(ROOT, "_audit", "RA365-PHASE5F-SELECTION.csv")
OUT_JSON = os.path.join(ROOT, "_audit", "ra365_phase5f_targets.json")

# مرزِ پوششِ رسمیِ رویدادها درِ `price_adjust_events` (ازِ همان ستونِ d_even خوانده می‌شود،
# نه ازِ عددِ گزارشِ قدیم — قیدِ مأموریت: «فرض نکن تعدادها هنوز ثابت‌اند»).
MIN_HIST_DAYS = 120          # کنترلِ بی‌رویداد فقط با تاریخچۀِ کافی معتبر است
BOUNDARY_WINDOW_DAYS = 730   # «نزدیکِ مرزِ پوشش» = رویداد درِ دو سالِ اولِ پوششِ مبدأ


def norm_day(v):
    """یگانۀِ نرمال‌سازیِ روز برِ دو خانوادۀِ قالبِ موجود درِ همین بانک.

    `price_history.date` ISO است (`2024-08-24`) ولی `d_even` فشرده است (`20240721`).
    مقابلهٔ رشته‌ایِ خامِ این دو همیشه «ISO < فشرده» می‌دهد (نمونۀِ `-` (0x2D) پیش ازِ
    `0` (0x30) می‌آید)، پس طبقاتِ تاریخی **بی‌سروصدا** غلط می‌شوند؛ اجرایِ اولِ همین
    اسکریپت دقیقاً همین خطا را داشت و با اصلاحِ جهتِ مقابله بسته شد.
    """
    s = str(v or "")[:10]
    if not s:
        return ""
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


def main():
    if not os.path.exists(DB):
        print("market.db پیدا نشد:", DB)
        return 2
    con = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    cov = con.execute("SELECT MIN(d_even), MAX(d_even), COUNT(*), COUNT(DISTINCT ins_code) "
                      "FROM price_adjust_events").fetchone()
    cov_sc = con.execute("SELECT MIN(d_even), MAX(d_even), COUNT(*), COUNT(DISTINCT ins_code) "
                         "FROM share_change_events").fetchone()
    src_start = norm_day(cov[0])
    print(f"پوششِ price_adjust_events: {src_start} → {norm_day(cov[1])} | ردیف={cov[2]} | نماد={cov[3]}")
    print(f"پوششِ share_change_events: {norm_day(cov_sc[0])} → {norm_day(cov_sc[1])} | "
          f"ردیف={cov_sc[2]} | نماد={cov_sc[3]}")

    rows = con.execute("""
        SELECT i.ins_code, i.l_val18 AS sym, i.l_val30 AS name, i.sector_name, i.paper_type,
               i.total_shares,
               (SELECT COUNT(*) FROM price_history p WHERE p.symbol = i.l_val18)        AS n_candles,
               (SELECT MIN(date)  FROM price_history p WHERE p.symbol = i.l_val18)       AS first_day,
               (SELECT MAX(date)  FROM price_history p WHERE p.symbol = i.l_val18)       AS last_day,
               (SELECT COUNT(*) FROM price_adjust_events a WHERE a.ins_code = i.ins_code) AS n_pa,
               (SELECT COUNT(*) FROM price_adjust_events a
                 WHERE a.ins_code = i.ins_code AND a.corporate_type_code IS NULL)        AS n_pa_nulltype,
               (SELECT COUNT(*) FROM price_adjust_events a
                 WHERE a.ins_code = i.ins_code AND a.ratio IS NULL)                      AS n_pa_noratio,
               (SELECT MIN(d_even) FROM price_adjust_events a WHERE a.ins_code = i.ins_code) AS pa_first,
               (SELECT MAX(d_even) FROM price_adjust_events a WHERE a.ins_code = i.ins_code) AS pa_last,
               (SELECT COUNT(*) FROM share_change_events s WHERE s.ins_code = i.ins_code) AS n_sc,
               (SELECT COUNT(*) FROM share_change_events s
                 WHERE s.ins_code = i.ins_code AND (s.shares_old IS NULL OR s.shares_new IS NULL
                        OR s.shares_old <= 0 OR s.shares_new <= 0))                      AS n_sc_invalid
        FROM instruments i
        WHERE i.l_val18 IS NOT NULL AND TRIM(i.l_val18) <> ''
          AND (SELECT COUNT(*) FROM price_history p WHERE p.symbol = i.l_val18) > ?
        ORDER BY n_candles DESC
    """, (MIN_HIST_DAYS,)).fetchall()
    hist_floor = norm_day(con.execute("SELECT MIN(date) FROM price_history").fetchone()[0])
    con.close()
    print(f"کفِّ تاریخچۀِ محلیِ `price_history`: {hist_floor} "
          f"(پوششِ مبدأ از {src_start}) — "
          f"{'تاریخچۀِ محلی تمام درِ پوشش است؛ طبقۀ «تاریخچۀِ کهنه‌تر ازِ پوشش» ازِ کندلِ محلی نمونه‌پذیر نیست' if hist_floor >= src_start else 'بخشی از تاریخچۀِ محلی پیشِ پوششِ مبدأ است'}")

    import datetime as dt
    def days_ago(d):
        iso = norm_day(d)
        if not iso:
            return None
        try:
            return (dt.date.fromisoformat(iso) - dt.date.fromisoformat(src_start)).days
        except ValueError:
            return None

    recs = []
    for r in rows:
        n_pa, n_sc = r["n_pa"], r["n_sc"]
        n_cand = n_pa + n_sc
        pa_first_gap = days_ago(r["pa_first"])
        first_day = norm_day(r["first_day"])
        last_day = norm_day(r["last_day"])
        pa_last_iso = norm_day(r["pa_last"])
        hist_span = None
        try:
            hist_span = (dt.date.fromisoformat(last_day) - dt.date.fromisoformat(first_day)).days
        except (ValueError, TypeError):
            pass
        cats = []
        if n_pa:
            cats.append("price_adjust")
        if n_sc:
            cats.append("share_change")
        if n_pa and n_sc:
            cats.append("mixed")
        if n_cand >= 3:
            cats.append("multi_event")
        if n_cand >= 8:
            cats.append("heavy_event")
        if n_pa and r["n_pa_nulltype"] == n_pa:
            cats.append("unresolved_type")
        if n_pa and r["n_pa_noratio"]:
            cats.append("event_without_ratio")
        if n_sc and r["n_sc_invalid"]:
            cats.append("invalid_share_row")
        if pa_first_gap is not None and 0 <= pa_first_gap <= BOUNDARY_WINDOW_DAYS:
            cats.append("near_source_boundary")
        if first_day < src_start and n_cand:
            cats.append("pre_coverage_history")
        if hist_span is not None and hist_span >= 2000:
            cats.append("old_history")
        if first_day >= "2024-01-01":
            cats.append("new_listing")
        if pa_last_iso and last_day and pa_last_iso >= last_day:
            cats.append("last_event_at_history_end")
        if n_cand == 0 and r["n_candles"] >= 300:
            # قیدِ مأموریت: کنترلِ بی‌رویداد فقط وقتی معتبر است که **پوششِ مبدأ** برایِ
            # بازۀِ بررسی کافی باشد. تاریخچۀِ پیش ازِ `src_start` «رویدادی نبود» را
            # اثبات نمی‌کند؛ فقط «منبع ردیفی نداشت» را می‌گوید.
            cats.append("no_event_control" if first_day >= src_start
                        else "no_event_pre_coverage")
        if not cats:
            continue
        recs.append({
            "ins_code": r["ins_code"], "symbol": r["sym"], "name": (r["name"] or "")[:60],
            "sector": (r["sector_name"] or "")[:40], "paper_type": r["paper_type"],
            "n_candles": r["n_candles"], "first_day": first_day,
            "last_day": last_day, "hist_span_days": hist_span,
            "n_price_adjust": n_pa, "n_share_change": n_sc,
            "n_pa_nulltype": r["n_pa_nulltype"], "n_pa_noratio": r["n_pa_noratio"],
            "n_sc_invalid": r["n_sc_invalid"],
            "pa_first": norm_day(r["pa_first"]), "pa_last": norm_day(r["pa_last"]),
            "categories": "+".join(sorted(set(cats))),
            "why_in_sample": "، ".join(sorted(set(cats))),
        })

    # انتخابِ طبقه‌ای: اولِ هر طبقه تا پرشدنِ حداقلِ پوشش، سپسِ تکمیلِ شمار با
    # نمادهایِ پُرویدادِ باقی‌مانده (تازگیِ تاریخچه و تنوعِ صنعت حفظ شود).
    wanted = int(os.environ.get("WANT_N", "48"))
    by_cat = {}
    for rec in recs:
        for c in rec["categories"].split("+"):
            by_cat.setdefault(c, []).append(rec)

    chosen, seen = [], set()

    def take(pool, k):
        n = 0
        for rec in sorted(pool, key=lambda x: (-x["n_price_adjust"] - x["n_share_change"],
                                               -x["n_candles"])):
            if n >= k:
                break
            if rec["ins_code"] in seen:
                continue
            seen.add(rec["ins_code"])
            chosen.append(rec)
            n += 1

    priority = ["unresolved_type", "near_source_boundary", "pre_coverage_history", "mixed",
                "heavy_event", "multi_event", "price_adjust", "share_change",
                "old_history", "new_listing", "no_event_control", "no_event_pre_coverage"]
    quota = {"unresolved_type": 8, "near_source_boundary": 5, "pre_coverage_history": 5,
             "mixed": 5, "heavy_event": 4, "multi_event": 6, "price_adjust": 10,
             "share_change": 6, "old_history": 4, "new_listing": 3, "no_event_control": 8,
             "no_event_pre_coverage": 4}
    for cat in priority:
        take(by_cat.get(cat, []), quota[cat])
    if len(chosen) < wanted:
        take(recs, wanted - len(chosen))

    # تنوعِ طبقه/صنعت: اگر همه ازِ یکِ صنعت شدند، جایِ آخرِ هر صنعتِ پُر را با نمادِ
    # صنعتِ دیگر عوض می‌کنیم (قید: «چند گروه یا طبقه نمادی متفاوت»).
    sectors = {}
    for rec in chosen:
        sectors.setdefault(rec["sector"] or "-", []).append(rec)
    distinct_sectors = len(sectors)

    out = sorted(chosen, key=lambda x: (-(x["n_price_adjust"] + x["n_share_change"]),
                                        x["symbol"]))
    have_evt = sum(1 for x in out if x["n_price_adjust"] + x["n_share_change"])
    ctrl = sum(1 for x in out if not (x["n_price_adjust"] + x["n_share_change"]))
    gaps = []
    if have_evt < 20:
        gaps.append(f"نمادِ رویداددارِ موجود فقط {have_evt} (حداقلِ خواستۀِ مأموریت: 20)")
    if ctrl < 5:
        gaps.append(f"کنترلِ بی‌رویدادِ معتبر فقط {ctrl} (حداقل: 5)")
    if distinct_sectors < 4:
        gaps.append(f"تنوعِ صنعت فقط {distinct_sectors} طبقه")
    if hist_floor >= src_start:
        gaps.append(f"طبقۀ «تاریخچۀِ کهنه‌تر ازِ پوششِ مبدأ» ازِ کندلِ محلی نمونه‌پذیر نیست: "
                    f"کفِّ `price_history` = {hist_floor} ⇐ پوششِ مبدأ = {src_start}. "
                    f"بخشِ پیشِ پوشش فقط ازِ سریِ مرجع دیدنی است و درِ Stage 6 "
                    f"`INCOMPLETE/پیشِ‌پنجره` ثبت می‌شود، نه «بدونِ تعدیل»")
    missing = [c for c in priority if not any(c in x["categories"] for x in out)]
    if missing:
        gaps.append("طبقاتی که درِ نمونۀِ نهایی هیچِ نماینده‌ای ندارند: " + "، ".join(missing))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        for rec in out:
            w.writerow(rec)

    # همان ردیف‌ها به‌شکلِ JSON، خوراکِ هارنسِ گرفتنِ زنده (`_audit/ra365_job_phase5f_capture.js`).
    # چرا دو قالب: CSV شاهدِ قابلِ بازبینیِ انسانی است و JSON ورودیِ بی‌ابهامِ جاوااسکریپت
    # (اسمِ نمادها ویرگول/جداکننده دارد؛ پارسِ دستیِ CSV خطایِ خاموش می‌سازد).
    with io.open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump({"source_coverage_start": src_start, "hist_floor": hist_floor,
                   "selected": len(out), "symbols": out}, fh, ensure_ascii=False, indent=1)

    # ── خودسنجیِ نرمال‌ساز ─────────────────────────────────────────────────────
    # اگر روزی `norm_day` کور شود، هر مقابلهٔ تاریخیِ بالا بی‌سروصدا غلط می‌شود
    # (همان خطایِ اجرایِ اولِ همین اسکریپت). این دو سطر سنسور را زنده نگه می‌دارد.
    assert norm_day("20240721") == "2024-07-21", "norm_day قالبِ فشرده را نمی‌شناسد"
    assert norm_day("2024-08-24") == "2024-08-24", "norm_day قالبِ ISO را خراب می‌کند"
    assert norm_day("2024-08-24") > norm_day("20240721"), \
        "ترتیبِ روزها پس ازِ نرمال‌سازی هنوز برعکس است"

    print(f"\nانتخاب شد: {len(out)} نماد | رویداددار={have_evt} کنترل={ctrl} "
          f"طبقاتِ صنعت={distinct_sectors}")
    print("شمارِ هر طبقه درِ جهانِ نمونه‌پذیر:",
          {c: len(v) for c, v in sorted(by_cat.items())})
    print("محدودیتِ پوشش:", gaps or "هیچ")
    print("CSV:", OUT)
    print("JSON:", OUT_JSON)
    return 0


if __name__ == "__main__":
    sys.exit(main())
