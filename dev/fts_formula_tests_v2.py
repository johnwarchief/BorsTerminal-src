#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FTS formula unit tests (mock / pure logic) -- reference: docs/FTS_SYSTEM_SPECIFICATION_v2.md v2.1

Self-contained: no database, no network, no project imports.
It re-expresses the FTS index formulas exactly as written in spec v2.1 and
checks the arithmetic, the acceptance thresholds and the veto rules against
hand-computed expectations. The sample numbers in the spec are used only as
fixtures.

Run:  python dev/fts_formula_tests_v2.py
Exit: 0 if every check passes, 1 otherwise.
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ----------------------------------------------------------------------------
# tiny assertion harness
# ----------------------------------------------------------------------------
RESULTS = []  # (group, name, ok, detail)


def T(group, name, cond, detail=""):
    RESULTS.append((group, name, bool(cond), detail))


def approx(a, b, tol=1e-6):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def is_none(v):
    return v is None


# threshold comparisons are boundary-inclusive ("≥") with a float epsilon so a
# value that is mathematically exactly on the threshold is not rejected by
# binary rounding (e.g. (140/100 - 1)*100 == 39.99999999999999).
EPS = 1e-9


def ge(a, b):
    return a is not None and a >= b - EPS


# ----------------------------------------------------------------------------
# unit normalization (spec: codal figures are million-rial -> billion-toman)
# ----------------------------------------------------------------------------
def mrl_to_btom(value_million_rials):          # / 10,000  ("drop 4 digits")
    return value_million_rials / 10000.0


# ============================================================================
# F-01  sales / operating-revenue growth
#   Sales_Growth = ((current_cumulative / prev_cumulative) - 1) * 100
#   min boundary : >= 40%      full FTS score : >= 60%      (inflation 58%)
# ============================================================================
GROWTH_MIN = 40.0
GROWTH_FULL = 60.0
INFLATION_BENCH = 58.0


def sales_growth(current, prev):
    if current is None or prev is None or prev <= 0:
        return None
    return (current / prev - 1.0) * 100.0


def growth_pass(g):
    return ge(g, GROWTH_MIN)


def growth_full(g):
    return ge(g, GROWTH_FULL)


def growth_beats_inflation(g):
    return ge(g, INFLATION_BENCH)


# ============================================================================
# F-04  dynamic annualization
#   Annualized_Sales = Sales_n * (12 / n)   for n = 3, 4, 6, 12 ...
# ============================================================================
ANNUALIZATION_SCALE = (3, 4, 5, 6, 9, 12)


def annualize(sales_n, n_months):
    if sales_n is None or n_months is None or n_months <= 0:
        return None
    return sales_n * (12.0 / n_months)


def annualize_factor(n_months):
    return 12.0 / n_months


# ============================================================================
# F-03  gross profit margin
#   GPM = (gross_profit / operating_revenue) * 100
#   standard : >= 30%      min boundary : >= 20%      below 20% -> REJECT
# ============================================================================
GPM_MIN = 20.0
GPM_STD = 30.0


def gpm(gross_profit, operating_revenue):
    if operating_revenue is None or operating_revenue <= 0 or gross_profit is None:
        return None
    return gross_profit / operating_revenue * 100.0


def gpm_pass(m):
    return ge(m, GPM_MIN)


def gpm_standard(m):
    return ge(m, GPM_STD)


# ============================================================================
# F-04  market-cap ratios
#   Sales_to_Cap_Ratio      = Annualized_Sales / Market_Cap        (>= 1.0)
#   Estimated_Gross_Profit  = Annualized_Sales * (GPM / 100)
#   pass if ratio >= 1.0  OR  (Est_GP / Market_Cap) >= 0.40        (spec v2.1)
# ============================================================================
CAP_RATIO_MIN = 1.0
GP_COVERAGE_MIN = 0.40


def sales_to_cap(annualized, market_cap):
    if annualized is None or market_cap is None or market_cap <= 0:
        return None
    return annualized / market_cap


def est_gross_profit(annualized, gpm_pct):
    if annualized is None or gpm_pct is None:
        return None
    return annualized * (gpm_pct / 100.0)


def gp_coverage(est_gp, market_cap):
    if est_gp is None or market_cap is None or market_cap <= 0:
        return None
    return est_gp / market_cap


def index4_verdict(annualized, market_cap, gpm_pct):
    ratio = sales_to_cap(annualized, market_cap)
    egp = est_gross_profit(annualized, gpm_pct)
    cov = gp_coverage(egp, market_cap)
    sales_ok = ge(ratio, CAP_RATIO_MIN)
    cov_ok = ge(cov, GP_COVERAGE_MIN)
    return {"ratio": ratio, "est_gp": egp, "coverage": cov,
            "sales_ok": sales_ok, "coverage_ok": cov_ok, "pass": sales_ok or cov_ok}


# ============================================================================
# F-02  three-year EPS trend
#   EPS(t-2) < EPS(t-1) < EPS(t)  AND  EPS(t) > 0 ; veto on any fall / negative
# ============================================================================
def eps_trend_ok(series):
    s = list(series)
    if len(s) < 3:
        return False
    strictly_rising = all(s[i] < s[i + 1] for i in range(len(s) - 1))
    all_positive = all(v > 0 for v in s)
    return strictly_rising and all_positive


# ============================================================================
# rejection / eligibility rules
# ============================================================================
INSURANCE_TOKENS = ("بیمه", "بازنشستگی")
FREE_21 = ("سیمان", "فلزات اساسی", "پتروشیمی", "کانی", "زنجیره فولاد", "فولاد",
           "کاشی", "سرامیک", "شیشه")
MANDATORY_21 = ("خودرو", "نیروگاه", "شوینده", "لاستیک",
                "غذایی مشمول تنظیم بازار")
HOLDING_KINDS = ("holding", "investment")


def _norm(s):
    return (s or "").strip()


def is_insurance(sector):
    s = _norm(sector)
    return any(t in s for t in INSURANCE_TOKENS)


def is_suspended(sign):
    return _norm(sign).upper() == "A"


def index4_available(profile_kind):
    # spec: market-cap ratio computation is FORBIDDEN for holding/investment -> N/A
    return profile_kind not in HOLDING_KINDS


def nav_substitute_allowed(profile_kind):
    # spec: using EPS (neg or pos) as a NAV substitute is FORBIDDEN -> N/A
    return profile_kind not in HOLDING_KINDS


def sector_verdict(sector, gpm_pct=None, bank_fx_positive=None, bank_loan_growth=None):
    """Reference encoder of spec v2.1 F-05 (+ insurance veto from F-01)."""
    s = _norm(sector)
    if is_insurance(s):
        return "reject"
    if any(t in s for t in MANDATORY_21):
        return "reject"
    if "دارو" in s:
        return "allow" if (gpm_pct is not None and gpm_pct > 50.0) else "reject"
    if "بانک" in s:
        return "allow" if (bank_fx_positive and bank_loan_growth) else "neutral"
    if any(t in s for t in FREE_21):
        return "allow"
    return "neutral"


# ============================================================================
# TESTS
# ============================================================================
def run_tests():
    # ---------------- G1: sales growth (F-01) ----------------
    g = sales_growth(120, 100)
    T("G1", "F-01 formula (120/100-1)*100 = 20", approx(g, 20.0), "got=%s" % g)
    g = sales_growth(140, 100)
    T("G1", "F-01 min boundary 40% -> pass", approx(g, 40.0) and growth_pass(g), "got=%s" % g)
    g = sales_growth(139, 100)
    T("G1", "F-01 39% below min -> not pass", approx(g, 39.0) and not growth_pass(g), "got=%s" % g)
    g = sales_growth(150, 100)
    T("G1", "F-01 50% pass but not full", growth_pass(g) and not growth_full(g),
      "pass=%s full=%s" % (growth_pass(g), growth_full(g)))
    g = sales_growth(160, 100)
    T("G1", "F-01 full-score boundary 60%", approx(g, 60.0) and growth_full(g), "got=%s" % g)
    g = sales_growth(175, 100)
    T("G1", "F-01 75% >= full", growth_full(g), "got=%s" % g)
    g = sales_growth(90, 100)
    T("G1", "F-01 negative growth -10% -> reject", approx(g, -10.0) and not growth_pass(g), "got=%s" % g)
    T("G1", "F-01 prev=0 -> None (data gap, not pass)",
      is_none(sales_growth(100, 0)) and not growth_pass(sales_growth(100, 0)))
    T("G1", "F-01 prev=None -> None", is_none(sales_growth(100, None)))
    g = sales_growth(158, 100)
    T("G1", "F-01 58% meets inflation benchmark", approx(g, 58.0) and growth_beats_inflation(g), "got=%s" % g)
    g = sales_growth(150, 100)
    T("G1", "F-01 50% below inflation benchmark", not growth_beats_inflation(g), "got=%s" % g)

    # ---------------- G2: dynamic annualization (F-04) ----------------
    T("G2", "F-04 annualize n=3 -> x4", approx(annualize(1000, 3), 4000.0), "got=%s" % annualize(1000, 3))
    T("G2", "F-04 annualize n=4 -> x3", approx(annualize(1000, 4), 3000.0), "got=%s" % annualize(1000, 4))
    T("G2", "F-04 annualize n=6 -> x2", approx(annualize(1000, 6), 2000.0), "got=%s" % annualize(1000, 6))
    T("G2", "F-04 annualize n=12 -> x1", approx(annualize(1000, 12), 1000.0), "got=%s" % annualize(1000, 12))
    T("G2", "F-04 annualize n=5 -> x2.4 (generic 12/n)",
      approx(annualize(1000, 5), 2400.0), "got=%s" % annualize(1000, 5))
    T("G2", "F-04 factor table 12/n = [4,3,2,1]",
      [annualize_factor(m) for m in (3, 4, 6, 12)] == [4.0, 3.0, 2.0, 1.0])
    T("G2", "F-04 unit: 1,000,000 mRial -> 100 btoman", approx(mrl_to_btom(1000000), 100.0))
    T("G2", "F-04 unit: 150,000 mRial -> 15 btoman", approx(mrl_to_btom(150000), 15.0))
    T("G2", "F-04 unit: 10,000 mRial -> 1 btoman", approx(mrl_to_btom(10000), 1.0))
    T("G2", "F-04 annualize guard n=0 -> None", is_none(annualize(1000, 0)))

    # ---------------- G3: gross profit margin (F-03) ----------------
    m = gpm(30, 100)
    T("G3", "F-03 (30/100)*100 = 30 standard", approx(m, 30.0) and gpm_standard(m) and gpm_pass(m), "got=%s" % m)
    m = gpm(20, 100)
    T("G3", "F-03 20% min boundary pass, not standard",
      approx(m, 20.0) and gpm_pass(m) and not gpm_standard(m), "got=%s" % m)
    m = gpm(19.9, 100)
    T("G3", "F-03 19.9% below min -> reject",
      approx(m, 19.9) and not gpm_pass(m), "got=%s" % m)
    m = gpm(50, 100)
    T("G3", "F-03 50%", approx(m, 50.0), "got=%s" % m)
    m = gpm(0, 100)
    T("G3", "F-03 zero profit -> 0%, not pass",
      approx(m, 0.0) and not gpm_pass(m), "got=%s" % m)
    T("G3", "F-03 gross_profit None -> None (bank/fund)", is_none(gpm(None, 100)))
    T("G3", "F-03 revenue 0 -> None", is_none(gpm(30, 0)))

    # ---------------- G4: sales/mcap + gp potential (F-04) ----------------
    T("G4", "F-04 ratio 1000/800 = 1.25", approx(sales_to_cap(1000, 800), 1.25))
    T("G4", "F-04 est_gross_profit = annualized*GPM = 1000*30% = 300",
      approx(est_gross_profit(1000, 30), 300.0))
    T("G4", "F-04 gp coverage 300/800 = 0.375", approx(gp_coverage(300, 800), 0.375))
    v = index4_verdict(1000, 800, 30)
    T("G4", "F-04 ratio>=1.0 -> pass", v["sales_ok"] and v["pass"], "ratio=%s" % v["ratio"])
    v = index4_verdict(800, 800, 10)
    T("G4", "F-04 ratio boundary 1.0 -> pass", approx(v["ratio"], 1.0) and v["pass"])
    v = index4_verdict(600, 800, 50)
    T("G4", "F-04 ratio 0.75 & coverage 0.375 -> reject",
      (not v["sales_ok"]) and (not v["coverage_ok"]) and (not v["pass"]), "cov=%s" % v["coverage"])
    v = index4_verdict(600, 800, 60)
    T("G4", "F-04 OR: ratio<1 but coverage 0.45 -> pass",
      (not v["sales_ok"]) and v["coverage_ok"] and v["pass"], "cov=%s" % v["coverage"])
    v = index4_verdict(640, 800, 50)
    T("G4", "F-04 coverage boundary 0.40 -> pass",
      approx(v["coverage"], 0.40) and (not v["sales_ok"]) and v["pass"], "cov=%s" % v["coverage"])
    v = index4_verdict(1000, 0, 30)
    T("G4", "F-04 mcap<=0 -> no verdict", is_none(v["ratio"]) and not v["pass"])
    T("G4", "F-04 spec v2.1 coverage threshold is 0.40", approx(GP_COVERAGE_MIN, 0.40), "th=%s" % GP_COVERAGE_MIN)

    # ---------------- G5: three-year EPS trend (F-02) ----------------
    T("G5", "F-02 [100,150,200] rising -> pass", eps_trend_ok([100, 150, 200]))
    T("G5", "F-02 [100,150,150] flat -> reject", not eps_trend_ok([100, 150, 150]))
    T("G5", "F-02 [100,90,200] dip -> reject", not eps_trend_ok([100, 90, 200]))
    T("G5", "F-02 [100,150,-10] negative last -> reject", not eps_trend_ok([100, 150, -10]))
    T("G5", "F-02 [-5,10,20] negative earlier -> reject", not eps_trend_ok([-5, 10, 20]))
    T("G5", "F-02 [100,120,110] last-year fall -> reject", not eps_trend_ok([100, 120, 110]))
    T("G5", "F-02 [100,200,300] rising -> pass", eps_trend_ok([100, 200, 300]))
    T("G5", "F-02 fewer than 3 years -> reject", not eps_trend_ok([10, 20]))
    T("G5", "F-02 [100,150,0] zero last -> reject (EPS(t)>0)", not eps_trend_ok([100, 150, 0]))

    # ---------------- G6: veto / rejection rules ----------------
    T("G6", "F-01 insurance sector detected", is_insurance("بیمه و صندوق بازنشستگی"))
    T("G6", "non-insurance sector not flagged", not is_insurance("سیمان"))
    T("G6", "F-01 insurance is ABSOLUTE reject despite great fundamentals",
      sector_verdict("بیمه", gpm_pct=60.0) == "reject")
    T("G6", "F-01 suspended flag 'A' -> reject", is_suspended("A"))
    T("G6", "F-01 empty flag -> not suspended", not is_suspended(""))
    T("G6", "F-01 flag 'B' -> not suspended", not is_suspended("B"))
    T("G6", "F-01 lowercase 'a' -> suspended", is_suspended("a"))
    T("G6", "F-04 holding -> market-cap ratio N/A", not index4_available("holding"))
    T("G6", "F-04 investment -> market-cap ratio N/A", not index4_available("investment"))
    T("G6", "F-04 production -> market-cap ratio available", index4_available("production"))
    T("G6", "F-04 holding -> NAV substitute forbidden", not nav_substitute_allowed("holding"))
    T("G6", "F-04 holding N/A even with perfect EPS/GPM",
      (not index4_available("holding")) and eps_trend_ok([100, 200, 300]) and gpm_pass(gpm(60, 100)))

    # ---------------- G7: spec v2.1 new / changed clauses ----------------
    T("G7", "v2.1 dynamic annualization explicit example n=4 -> x3",
      approx(annualize(500, 4), 1500.0))
    T("G7", "v2.1 GP coverage threshold 40% (0.40)", approx(GP_COVERAGE_MIN, 0.40))
    T("G7", "v2.1 free-industry list contains شیشه (glass)",
      any("شیشه" in t for t in FREE_21))
    T("G7", "v2.1 free-industry list core members",
      all(any(k in t for t in FREE_21) for k in ("سیمان", "پتروشیمی", "فلزات", "کاشی", "سرامیک")))
    T("G7", "v2.1 دارو exception: GPM 55% -> allow",
      sector_verdict("دارو", gpm_pct=55.0) == "allow")
    T("G7", "v2.1 دارو exception: GPM 45% -> reject",
      sector_verdict("دارو", gpm_pct=45.0) == "reject")
    T("G7", "v2.1 دارو exception is strictly > 50% (GPM 50 -> reject)",
      sector_verdict("دارو", gpm_pct=50.0) == "reject")
    T("G7", "v2.1 بانک exception: positive FX + loan growth -> allow",
      sector_verdict("بانک", bank_fx_positive=True, bank_loan_growth=True) == "allow")
    T("G7", "v2.1 بانک without FX surplus -> neutral",
      sector_verdict("بانک", bank_fx_positive=False, bank_loan_growth=True) == "neutral")
    T("G7", "v2.1 mandatory (خودرو) absolute reject even at 80% margin",
      sector_verdict("خودرو و ساخت قطعات", gpm_pct=80.0) == "reject")
    T("G7", "v2.1 free (سیمان) -> allow", sector_verdict("سیمان") == "allow")
    T("G7", "v2.1 free (شیشه) -> allow", sector_verdict("شیشه") == "allow")
    T("G7", "v2.1 unknown sector -> neutral", sector_verdict("ناشناخته") == "neutral")


# ----------------------------------------------------------------------------
# divergence log: spec v2.1 vs the current project implementation.
# Informational only -- never affects pass/fail or exit code.
# ----------------------------------------------------------------------------
DIVERGENCES = [
    ("F-04/cov", "spec v2.1 GP coverage threshold = 40% ; impl profit_potential_min=30 (bors_config.py) and v10_potential_min=33 (api/fundamental.py FTS_V10_DEFAULTS)"),
    ("F-04/pass", "spec v2.1 pass = ratio>=1.0 OR coverage>=40% ; impl api/fundamental.py ind4_valuation pass = sales_pass AND pot_pass (AND, not OR)"),
    ("F-04/holding", "spec v2.1: holding/investment ratio must be N/A ; impl dynamic_annualized_sales still emits a ratio on op-revenue basis (no N/A)"),
    ("F-05/free", "spec v2.1 free list includes 'شیشه' (glass) ; impl FREE_PRICING_TOKENS (fts_engine.py) has no 'شیشه'"),
    ("F-05/daroo", "spec v2.1 allows pharma with GPM>50% ; impl marks all 'دارو' as mandatory reject (no exception)"),
    ("F-05/breadth", "spec v2.1 mandatory = severe-regulated food only ; impl also blanket-rejects 'قند و شکر' and generic 'غذا'"),
    ("F-01/suspend", "spec v2.1 rejects literal suspension flag 'A' ; impl is_suspended() uses a stale-session heuristic, no 'A' flag test"),
]


def main():
    run_tests()
    groups = {}
    for group, name, ok, detail in RESULTS:
        groups.setdefault(group, []).append((name, ok, detail))

    titles = {
        "G1": "F-01 sales growth",
        "G2": "F-04 dynamic annualization",
        "G3": "F-03 gross profit margin",
        "G4": "F-04 sales/mcap + gross-profit potential",
        "G5": "F-02 three-year EPS trend",
        "G6": "veto / rejection rules",
        "G7": "spec v2.1 new & changed clauses",
    }
    print("=" * 72)
    print("FTS formula unit tests  (spec v2.1)")
    print("=" * 72)
    for group in sorted(groups):
        print("\n-- %s : %s --" % (group, titles.get(group, group)))
        for name, ok, detail in groups[group]:
            tag = "PASS" if ok else "FAIL"
            line = "  [%s] %s" % (tag, name)
            if detail and not ok:
                line += "  <%s>" % detail
            print(line)

    print("\n-- spec v2.1 vs current implementation (informational) --")
    for cid, text in DIVERGENCES:
        print("  [WARN] %s: %s" % (cid, text))

    total = len(RESULTS)
    passed = sum(1 for _, _, ok, _ in RESULTS if ok)
    failed = total - passed
    print("\n" + "=" * 72)
    print("SUMMARY: %d/%d passed, %d failed" % (passed, total, failed))
    print("=" * 72)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
