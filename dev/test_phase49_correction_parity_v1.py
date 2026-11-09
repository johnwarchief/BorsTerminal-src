#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 4.9 — Python↔Go correction parity fixture.

Exercises the two behaviours that must be identical in Python and Go:
  1. the display pipeline: literal H/L (high_raw/low_raw) followed by the
     versioned pack's per-field raw corrections (AC.apply_raw_candles);
  2. the chain pipeline: pack overlay with evidence-based near-date dedup
     (AC.apply_factor_events) + canonical cumulative factors (AE.chain_factors).

The same fixture is read by the Go test
`backend-go/internal/chart/phase49_parity_test.go`; a shared golden file is
what makes the two engines provably agree instead of merely "close".

Usage:
  python dev/test_phase49_correction_parity_v1.py            # verify (CI/gates)
  python dev/test_phase49_correction_parity_v1.py --emit     # regenerate fixture
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, "backend-go", "internal", "chart", "testdata", "phase49", "pack")
FIXTURE = os.path.join(ROOT, "backend-go", "internal", "chart", "testdata",
                       "phase49", "fixture.json")

os.environ.pop("BORS_CORRECTIONS_DISABLE", None)
os.environ["BORS_CORRECTIONS_DIR"] = PACK

sys.path.insert(0, ROOT)
import adjustment_corrections as AC  # noqa: E402
import adjustment_engine as AE  # noqa: E402

CANDLES = [
    {"symbol": "TESTSYM", "time": "2024-06-27", "open": 100, "high": 102, "low": 99,
     "high_raw": 101, "low_raw": 99.5, "close": 100, "last": 101, "volume": 1000},
    {"symbol": "TESTSYM", "time": "2024-06-29", "open": 69, "high": 71, "low": 68,
     "high_raw": 70, "low_raw": 68.5, "close": 70, "last": 70.5, "volume": 900},
    {"symbol": "TESTSYM", "time": "2024-07-01", "open": 63, "high": 65, "low": 62,
     "high_raw": 64, "low_raw": 62.5, "close": 63, "last": 64, "volume": 800},
    {"symbol": "TESTSYM", "time": "2024-07-03", "open": 64, "high": 66, "low": 63,
     "high_raw": 65, "low_raw": 63.5, "close": 64, "last": 65, "volume": 700},
    {"symbol": "TESTSYM", "time": "2025-06-09", "open": 50, "high": 52, "low": 49,
     "high_raw": 51, "low_raw": 49.5, "close": 50, "last": 51, "volume": 600},
    {"symbol": "TESTSYM", "time": "2025-06-10", "open": 40, "high": 42, "low": 39,
     "high_raw": 41, "low_raw": 39.5, "close": 40, "last": 41, "volume": 500},
]

EVENTS = [
    {"date": "2024-06-27", "ratio": 0.95, "source": "test-product"},      # kept
    {"date": "2024-06-30", "ratio": 0.85, "source": "test-product"},      # near 07-01, ratio conflict -> kept
    {"date": "2024-07-01", "ratio": 0.9, "source": "test-product"},       # exact pack step -> suppressed
    {"date": "2024-07-03", "ratio": 0.6, "source": "test-product"},       # exact suppress -> suppressed
    {"date": "2024-07-10", "ratio": 0.98, "source": "test-product"},      # kept
    {"date": "2024-07-12", "ratio": 0.97, "source": "test-product"},      # kept
    {"date": "2025-06-09", "ratio": 0.8004, "source": "test-product"},    # near 06-10, ratio agrees -> deduped
]

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   <- %s" % (detail,)) if detail else ""))


def near(a, b, tol=1e-12):
    return abs(float(a) - float(b)) <= tol


def display(candles):
    out = []
    for c in candles:
        d = dict(c)
        if d.get("high_raw") is not None:
            d["high"] = d["high_raw"]
        if d.get("low_raw") is not None:
            d["low"] = d["low_raw"]
        out.append(d)
    AC.apply_raw_candles("TESTSYM", out, "INS1")
    return out


def chain(events):
    kept, suppressed, meta = AC.apply_factor_events("TESTSYM", events, "INS1")
    times = [c["time"] for c in CANDLES]
    # Same normalisation as api/chart.py::_engine_events: a discovered event is
    # validated by the engine as a source_ratio (the ratio is already observed).
    wrapped = [dict(e, kind=AE.KIND_SOURCE_RATIO, date=str(e.get("date"))[:10])
               for e in kept]
    factors, prov = AE.chain_factors(times, wrapped)
    return kept, suppressed, meta, factors, prov


def snapshot():
    kept, suppressed, meta, factors, prov = chain(EVENTS)
    disp = display(CANDLES)
    return {
        "display_candles": [{k: d.get(k) for k in
                             ("time", "open", "high", "low", "high_raw", "low_raw",
                              "close", "last", "volume")} for d in disp],
        "kept_events": [{k: e.get(k) for k in ("date", "ratio", "source")} for e in kept],
        "suppressed_events": suppressed,
        "factors": [{"time": t, "factor": f} for t, f in zip([c["time"] for c in CANDLES],
                                                             factors)],
        "chain_anchored_last": prov.get("anchored_last"),
        "chain_complete": prov.get("complete"),
        "near_deduped": meta.get("near_deduped"),
    }


def load_fixture():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def emit():
    fx = {
        "schema": "phase49-correction-parity-v1",
        "pack": "backend-go/internal/chart/testdata/phase49/pack",
        "ins_code": "INS1", "symbol": "TESTSYM",
        "candles": CANDLES, "events": EVENTS,
        "expected": snapshot(),
    }
    os.makedirs(os.path.dirname(FIXTURE), exist_ok=True)
    with open(FIXTURE, "w", encoding="utf-8") as fh:
        json.dump(fx, fh, ensure_ascii=False, indent=1)
    print("fixture written:", FIXTURE)


def verify():
    got = snapshot()
    exp = load_fixture()["expected"]
    ck(len(got["display_candles"]) == len(exp["display_candles"]),
       "display candle count", len(got["display_candles"]))
    by_time = {c["time"]: c for c in got["display_candles"]}
    for want in exp["display_candles"]:
        have = by_time.get(want["time"])
        ck(have is not None, "display %s present" % want["time"])
        if have is None:
            continue
        for k, v in want.items():
            if isinstance(v, (int, float)):
                ck(near(have.get(k), v), "display %s.%s = %s" % (want["time"], k, v),
                   have.get(k))
            else:
                ck(have.get(k) == v, "display %s.%s = %r" % (want["time"], k, v),
                   have.get(k))
    # literal + raw corrections, explicitly
    c = by_time["2024-06-29"]
    ck(near(c["high"], 71.5) and near(c["low"], 68.5),
       "literal H/L then high_raw correction (high=71.5, low=68.5)")
    ck(near(c["open"], 69.5) and near(c["close"], 70.25) and near(c["last"], 70.75),
       "raw field corrections open/close/last")
    c4 = by_time["2024-07-03"]
    ck(near(c4["high"], 66.0) and near(c4["low"], 63.25),
       "explicit high wins; low_raw is copied to literal low")
    # chain
    got_dates = [e["date"] for e in got["kept_events"]]
    exp_dates = [e["date"] for e in exp["kept_events"]]
    ck(got_dates == exp_dates, "kept event dates", got_dates)
    ck(not any(e["date"] == "2025-06-09" for e in got["kept_events"]),
       "near-date product event is not applied twice")
    ded = [e for e in got["suppressed_events"] if e.get("dedupe")]
    ck(len(ded) == 1 and ded[0]["date"] == "2025-06-09",
       "suppressed near-date event carries dedupe evidence",
       json.dumps(got["suppressed_events"], ensure_ascii=False))
    ck(any(e["date"] == "2024-06-30" for e in got["kept_events"]),
       "near-date event with conflicting ratio is kept")
    for want in exp["factors"]:
        have = next((x for x in got["factors"] if x["time"] == want["time"]), None)
        ck(have is not None and near(have["factor"], want["factor"], 1e-9),
           "factor %s = %.12g" % (want["time"], want["factor"]),
           have and have["factor"])
    ck(got["chain_anchored_last"] is True, "chain anchored at last candle")
    ck(got["chain_complete"] is True, "chain provenance complete")
    print("---")
    print("%d passed / %d failed" % (P, F))
    return 0 if F == 0 else 1


if __name__ == "__main__":
    if "--emit" in sys.argv:
        emit()
        sys.exit(0)
    sys.exit(verify())
