#!/usr/bin/env python3
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage04_volana_rootcause as S  # noqa: E402


def main():
    steps = [
        {"symbol": "ولانا", "effective_date": "2020-01-02", "ratio": 0.9,
         "ref_ratio": 0.9, "validity": "unverified"},
        {"symbol": "ولانا", "effective_date": "2021-01-02", "ratio": 0.95,
         "ref_ratio": 0.96, "validity": "unverified"},
        {"symbol": "ولانا", "effective_date": "2022-01-02", "ratio": 0.8,
         "ref_ratio": 0.8, "validity": "unverified"},
    ]
    out = S.rootcause(steps)
    assert out["count"] == 3, out
    assert out["max_rel_error"] > 0.001, out
    assert out["steps"][1]["cause"] == "EVENT_RATIO_MISMATCH"

    # The mechanical filter must never admit another symbol or a verified row.
    mixed = steps + [
        {"symbol": "دیگر", "effective_date": "2020-01-02", "ratio": 0.9,
         "ref_ratio": 0.5, "validity": "unverified"},
        {"symbol": "ولانا", "effective_date": "2023-01-02", "ratio": 0.9,
         "ref_ratio": 0.9, "validity": "verified"},
    ]
    assert S.rootcause(mixed)["count"] == 3

    # Frozen thresholds: 0.1% stays exact, 1% stays material, never relaxed.
    assert S.EXACT == 1e-3 and S.MATERIAL == 1e-2
    rules = S.load_rules(S.DEFAULT_RULES)
    assert rules["tolerances"]["FACTOR_EXACT"] == 1e-3
    assert rules["tolerances"]["FACTOR_MATERIAL"] == 1e-2

    def classified(ratio_error=0.0, prev=0.0, group=0.0,
                   official=None, in_change=False):
        ref = {"ratio_error": ratio_error, "in_change_list": in_change,
               "change_error": None}
        off = {"exact_best_error": official}
        chain = {"prev_cum_error": prev}
        grp = {"group_effect": group}
        return S._classify(ref, off, chain, grp, rules)[0]

    assert classified() == "VERIFIED_REFERENCE"
    assert classified(ratio_error=0.0010001) == "PARTIAL_REFERENCE"
    assert classified(ratio_error=0.02) == "CONFLICT_RATIO"
    assert classified(prev=0.02) == "CONFLICT_CHAIN"
    assert classified(official=0.005) == "PARTIAL_OFFICIAL"
    assert classified(official=0.02) == "CONFLICT_RATIO"
    assert classified(official=0.0005) == "VERIFIED_OFFICIAL"

    # The six answers are always present, even for a no-product step.
    ref = {"date": "2020-03-11",
           "daily_q": {"prev_date": "2020-03-10", "q_prev": 1.0,
                       "q": 1.0009, "ratio": 1.0009},
           "implied_ratio": 0.9991, "pack_ratio": 0.9991,
           "step_size": 0.0009, "ratio_error": 0.0,
           "in_change_list": False, "change_error": None}
    prod = {"event": None, "nearest": None, "within_window": False,
            "o1_rows": 0, "codal_notices": [], "price_adjust_events": [],
            "share_change_events": [], "rel_error": None}
    off = {"exact_best_error": None}
    chain = {"prev_date": "2019-03-19", "prev_cum": 0.1,
             "prev_q": 0.1001, "prev_cum_error": 0.001}
    grp = {"chain_error_2016": 0.00198, "group_effect": 0.00198}
    answers = S._six_answers(ref, prod, off, chain, grp, {})
    assert set(answers) == {
        "real_product_event", "effective_date_wrong",
        "definition_or_ca_difference", "reference_applied_differently",
        "duplicate_or_misclassified", "previous_cum_factor_wrong"}, answers

    # The three real pack ratios multiply to the measured 0.198% group effect.
    real = (0.9990313041704958, 0.9991898460707485, 0.9997992371009847)
    product = 1.0
    for ratio in real:
        product *= ratio
    assert abs((1.0 / product - 1.0) - 0.001982393) < 1e-8, product
    assert max(abs(1.0 - r) for r in real) < S.EXACT

    print("VOLANA TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
