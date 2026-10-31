#!/usr/bin/env python
"""وکتورهایِ لایه‌به‌لایۀ بنیادی از خودِ پایتون → internal/fundamental/testdata/vectors/

چرا جدا از طلایی‌هایِ پیلود: `golden/*.json` رأیِ نهایی است و اگر یکِ لایه غلط
باشد، خطا درِ کلِ بدنه گم می‌شود. این فایل هر لایه را **تنها** می‌سنجد، تا
fan-outِ کارتِ پنج‌محور داورِ محلی داشته باشد: شاخه‌ای که وکتورِ خودش را نبیند،
بسته نمی‌شود.

پوششِ هدفمند (همین‌ها درِ بازبینیِ B4a «سنجۀ کور» خوانده شدند):
  * ترتیبِ پرابِ آستانه‌ها — به‌خصوصِ `monetary_growth_min` که پرابِ `v10_` ندارد
    و `monetary_growth_target` که از همان کلیدِ پنل نگاشت می‌شود؛
  * مبنای تورم: صفرِ کاربر باید صفر بماند (`or` درِ پایتون ممنوع است)؛
  * پاک‌سازیِ نوعِ load_fts_config: لیستِ رشته‌ای با «،»، کلیدهایِ _years/_max/
    _sessions/_period، بولِ تاریخی، و سه boundِ ساعت‌شنی؛
  * مهاجرتِ کلیدهایِ نسل‌قدیم (فقط اگر کلیدِ تازه درِ فایل نباشد)؛
  * سریِ ماهانه: `_dedupe_ym` (بردِ ytd بزرگ‌تر، تساوی ⇒ نخستین)،
    `ytd_denominator` (سه رابطۀ مخرج)، `title_entity_suffix` رویِ ردیفِ ماهانه.

اوراکل هیچ‌وقت بانکِ ریشه را نمی‌خواند و هیچ‌وقت درِ WORK_DIR نمی‌نویسد: مسیرِ
`fts_thresholds.json` با patch کردنِ ماژول به یکِ پوشۀ موقت بدل می‌شود.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, "backend-go", "internal", "fundamental", "testdata", "vectors")


def digits(text, base):
    return text.translate(str.maketrans("0123456789", "".join(chr(base + d) for d in range(10))))


FA = lambda s: digits(s, 0x06F0)  # noqa: E731


def threshold_vectors():
    """هر حالتی که دو پرابِ متفاوت را از هم جدا می‌کند."""
    cases = [
        {},
        {"growth_min": 70.0},
        {"v10_margin_min": 40.0, "margin_min": 40.0},
        {"v10_margin_min": 5.0, "margin_min": 25.0},
        {"margin_min": 25.0},
        {"v10_monetary_growth_min": 55.0},
        {"v10_monetary_growth_min": 55.0, "growth_min": 30.0},
        {"growth_min": 30.0},
        {"eps_years": "5"},
        {"v10_eps_years": 4, "eps_years": 2},
        {"v10_volume_breadth_min": 0.75},
        {"volume_breadth_min": 0.5},
        {"v10_sales_to_mcap_min": 0.5, "sales_to_mcap_min": 0.25},
        {"v10_potential_min": 20.0, "profit_potential_min": 35.0},
        {"v10_inflation_basis": 0.0},
        {"v10_inflation_basis": "42.5"},
        {"v10_inflation_basis": -1.0},
        {"v10_inflation_basis": "abc"},
        {"margin_min": "bad"},
        {"margin_min": None},
    ]
    import api.fundamental as fd
    return {"cases": [{"cfg": c, "out": fd.v10_thresholds(dict(c))} for c in cases]}


def config_vectors():
    """load_fts_config رویِ سیزده بدنهٔ فایل — با مسیرِ patchشده، بی‌نوشتن به ریشه."""
    import api.market as mk

    bodies = [
        None,                                     # فایل نیست
        {},
        [],                                       # بدنهٔ غیرdict
        {"growth_min": 55},
        {"eps_years": 4, "watchlist_max": "12", "suspended_max_stale_sessions": 5.9},
        {"hourglass_rsi_period": 14, "hourglass_rsi_oversold": 40.0,
         "hourglass_ma52_position": "either"},
        {"hourglass_rsi_period": 101, "hourglass_rsi_oversold": 90.0,
         "hourglass_ma52_position": "sideways"},
        {"hourglass_rsi_period": 7.0, "hourglass_rsi_oversold": "30"},
        {"mandatory_sectors": "خودرو، نیروگاه , دارو"},
        {"include_industries": ["فلزات", "  ", "پتروشیمی"],
         "exclude_industries": []},
        {"streak_periods": 6},
        {"streak_periods": 6, "eps_years": 2},
        {"ps_good": 2.0, "potential_min": 33.0},
        {"bad_sectors": ["الف"], "good_sectors": ["ب"]},
        {"filter_m141": 1, "exclude_base_market": 0, "holdings_sales_na": "no"},
        {"industry_mode": 7, "bogus_key": 1},
        {"margin_min": "bad"},
        {"min_trade_val": FA("۲"), "mcap_min_hmt": FA("۱۲٫۵")},
    ]
    tmp = tempfile.mkdtemp(prefix="b4-cfg-")
    saved = mk.FTS_CONFIG_PATH
    out = []
    try:
        for i, body in enumerate(bodies):
            path = os.path.join(tmp, "fts_thresholds_%d.json" % i)
            if body is None:
                if os.path.exists(path):
                    os.remove(path)
                label = "missing"
            else:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(body, f, ensure_ascii=False)
                label = "body%d" % i
            mk.FTS_CONFIG_PATH = path
            try:
                cfg = mk.load_fts_config()
                err = None
            except Exception as exc:                          # noqa: BLE001
                cfg, err = None, "%s: %s" % (type(exc).__name__, exc)
            out.append({"label": label, "file": body, "out": cfg, "error": err})
    finally:
        mk.FTS_CONFIG_PATH = saved
        shutil.rmtree(tmp, ignore_errors=True)
    return {"cases": out}


def series_vectors():
    """_dedupe_ym، ytd_denominator و فیلترِ «شرکتِ دیگر» رویِ سریِ ماهانه."""
    import fts_engine as fe

    rows = [
        [1404, 6, 50.0, 300.0, 200.0, "1404/06/31", "دوره ۶ ماهه"],
        [1404, 6, 45.0, 350.0, None, "1404/06/31", "دوره ۶ ماهه"],   # ytd بزرگ‌تر ⇒ برد
        [1404, 5, 40.0, 250.0, None, "1404/05/31", "دوره ۵ ماهه"],
        [1403, 6, 30.0, 150.0, None, "1403/06/31", "دوره ۶ ماهه"],
        [1403, 5, 28.0, 120.0, None, "1403/05/31", "دوره ۵ ماهه"],
    ]
    dedupe_cases = [
        rows,
        list(reversed(rows)),
        [[1404, 6, 1.0, 100.0, None, "1404/06/31", "a"],
         [1404, 6, 2.0, 100.0, None, "1404/06/31", "b"]],          # تساوی ⇒ نخستین
        [[1404, 6, 1.0, 100.0, None, "1404/06/31", "a"],
         [1404, 6, 2.0, 90.0, None, "1404/06/31", "b"]],
        [[None, None, 1.0, 10.0, None, "", "x"], [None, None, 2.0, 20.0, None, "", "y"]],
        [["1404", "06", 1.0, 10.0, None, "1404/06/31", "ز"], ["1404", "6", 2.0, 20.0, None,
                                                               "1404/06/31", "ح"]],
    ]
    denom_cases = [
        rows,
        [rows[0], rows[3]],                       # ستونِ مقایسه ⇒ مخرج از همان گزارش
        [r for r in rows if r[4] is None],        # مخرج از ردیفِ سالِ قبل
        [r for r in rows if r[4] is None][1:],    # سالِ قبل نیست ⇒ ناموجود
        [[1404, 0, 10.0, 100.0, None, "1404-01-01", ""]],      # ماه صفر ⇒ None
        [[1404, 6, 10.0, 0.0, None, "1404/06/31", ""]],        # تجمیعی صفر ⇒ None
        [],
    ]
    return {
        "dedupe_rows": [{"in": r, "out": [list(x) for x in fe._dedupe_ym([list(x) for x in r])]}
                        for r in dedupe_cases],
        "denominator": [{"in": r, "out": fe.ytd_denominator([list(x) for x in r])}
                        for r in denom_cases],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args(argv)

    import api.fundamental as fd
    import fts_engine as fe

    os.makedirs(args.out, exist_ok=True)
    files = {
        "thresholds.json": threshold_vectors(),
        "config.json": config_vectors(),
        "series.json": series_vectors(),
    }
    # دو وکتورِ تک‌تابعی که شاخه‌هایِ D/E/F به آن‌ها تکیه می‌کنند
    files["profile.json"] = {"cases": [
        {"sector": s, "company": c, "out": fe.company_profile(s, c)}
        for s, c in [
            ("بانک", ""), ("", "بانك Mellat"), ("صندوق سرمايه گذاري", ""),
            ("", "صندوق سرمایه‌گذاری آوینه"), ("بیمه", ""), ("لیزینگ", ""),
            ("کارگزاری", ""), ("اوراق بهادار", ""), ("هلدینگ", ""),
            ("واسطه گری", ""), ("خدمات نوآوری مالی", ""), ("حمل و نقل", ""),
            ("پتروشیمی", ""), ("فلزات اساسي", ""), ("سیمان", ""), ("", ""),
            ("کشاورانی", "شرکت کشت و صنعت مغان"),
        ]]}
    files["entity.json"] = {"cases": [
        {"in": t, "out": fe.title_entity_suffix(t)} for t in [
            "", "صورت مالی ۱۲ ماهه (حسابرسی شده)",
            "صورت مالی (حسابرسی شده) (شرکت هلپاک)",
            "صورت مالی (شرکت اصلی)", "صورت مالی (گروه الف)",
            "صورت مالی (موسسه)", "صورت مالی (بانك ب)",
            "صورت مالی (الف)", "صورت مالی （شرکت پارس）",
            "صورت مالی (شامل مقادیر برآوردی)", "صورت مالی (صندوق سرمایه‌گذاری)",
            "بیمه (بیمه البرز)", "اصلاحی (تلفیقی) (شرکت ب)",
            "سرمایه‌گذار (مؤسسه اعتباری ملل)",
        ]]}
    # جدولِ فیلترِ صنعت و آستانه‌هایش (شاخۀ F)
    files["sector.json"] = {"cases": [
        {"sector": s, "cfg": c, "out": fe.sector_filter(s, cfg=c, market_cap_rials=mc,
                                                        total_market_cap_rials=tm,
                                                        gpm=gpm, sales_growth=sg)}
        for s, c, mc, tm, gpm, sg in [
            ("خودرو", {}, 0.0, 0.0, None, None),
            ("خودرو", {"industry_mode": "Rank_Only"}, 0.0, 0.0, None, None),
            ("سیمان", {}, 0.0, 0.0, None, None),
            ("دارو", {}, 0.0, 0.0, 35.0, 45.0),
            ("دارو", {"pharma_margin_exempt_min": 30.0}, 0.0, 0.0, 35.0, 45.0),
            ("بانك", {"pharma_margin_exempt_min": 30.0}, 0.0, 0.0, 12.0, 90.0),
            ("غیرفعال", {}, 5e12, 1e15, None, None),
            ("پتروشیمی", {}, 5e12, 1e15, None, None),
            ("", {}, 0.0, 0.0, None, None),
        ]]}

    n = 0
    for name, payload in files.items():
        path = os.path.join(args.out, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        cases = payload.get("cases") or payload.get("dedupe_rows") or []
        n += len(cases)
        print("vectors ->", path, "(%d cases)" % len(cases))
    print("total vectors:", n)
    _ = fd  # imported for the oracle's own module dependencies
    return 0


if __name__ == "__main__":
    sys.exit(main())
