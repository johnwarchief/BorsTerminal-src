#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32B: versioned correction pack semantics.

No network, no DB.  A temporary pack exercises:
  * replace_step suppresses the product event on the effective date and inserts
    the reference step ratio;
  * suppress_step removes a product-only step without inventing a ratio;
  * DATE_DIFF is represented as suppress(old) + replace(new);
  * raw OHLC corrections change only the requested display fields;
  * authoritative mode ignores every product event for a covered symbol;
  * provenance (version, source, reference sha) survives;
  * a tampered pack is refused, not silently applied;
  * the Round 31 literal high/low rule still wins after a raw high_raw
    correction (a corrected high is not widened back to the body).
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import adjustment_corrections as AC  # noqa: E402
import api.chart as C  # noqa: E402

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   <- %s" % (detail,)) if detail else ""))


def chain(times, events):
    evs = sorted((str(e["date"])[:10], float(e["ratio"]))
                 for e in events if e.get("ratio") is not None)
    out = {}
    f, j = 1.0, len(evs) - 1
    for t in sorted(set(times), reverse=True):
        while j >= 0 and evs[j][0] > t:
            f *= evs[j][1]
            j -= 1
        out[t] = f
    return out


def make_pack(root, factors, raws, mode="overlay", bad_hash=False):
    d = os.path.join(root, "pack")
    os.makedirs(d, exist_ok=True)
    fp = os.path.join(d, "factors.jsonl")
    rp = os.path.join(d, "raw_ohlc.jsonl")
    with open(fp, "w", encoding="utf-8") as fh:
        for r in factors:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(rp, "w", encoding="utf-8") as fh:
        for r in raws:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def sha(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        return h.hexdigest()

    manifest = {
        "schema": "ra365-correction-pack-v1",
        "correction_version": "test-v1",
        "created_at": "2026-10-25T00:00:00+00:00",
        "source": "test-reference",
        "mode": mode,
        "reference_sha256": "test-ref-sha",
        "files": {"factors": "factors.jsonl", "raw_ohlc": "raw_ohlc.jsonl"},
        "file_sha256": {"factors": "0" * 64 if bad_hash else sha(fp),
                        "raw_ohlc": sha(rp)},
    }
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    return d


def factor_row(action, date, ratio=None, ins="INS1", symbol="TESTSYM"):
    return {"ins_code": ins, "asset_id": "1", "symbol": symbol,
            "action": action, "effective_date": date, "ratio": ratio,
            "class": "TEST", "event_sig": "dps", "confidence": "test",
            "fields_used": "close", "samples": 2, "max_field_dev": 0.0,
            "source": "test-reference", "method": "test",
            "ref_bars_sha256": "test-ref-sha", "correction_version": "test-v1",
            "created_at": "2026-10-25T00:00:00+00:00", "reason": "test"}


def raw_row(date, field, value, ins="INS1", symbol="TESTSYM"):
    return {"ins_code": ins, "asset_id": "1", "symbol": symbol, "date": date,
            "field": field, "value": value, "source": "test-reference",
            "method": "test", "confidence": "test",
            "ref_bars_sha256": "test-ref-sha", "correction_version": "test-v1",
            "created_at": "2026-10-25T00:00:00+00:00", "reason": "test"}


def main():
    global P, F
    old_env = os.environ.get("BORS_CORRECTIONS_DIR")
    old_dis = os.environ.pop("BORS_CORRECTIONS_DISABLE", None)
    tmp = tempfile.mkdtemp(prefix="r32b_pack_")
    try:
        events = [{"date": "2024-01-01", "ratio": 0.9},
                  {"date": "2024-06-01", "ratio": 0.8}]
        # factor(t) = product(ratio for event.date > t); an event on t does not
        # apply to t.  Include a date before the first event to see its effect.
        times = ["2023-12-01", "2024-01-01", "2024-06-01", "2024-12-01"]

        # 1) replace_step
        d = make_pack(os.path.join(tmp, "replace"), [factor_row("replace_step", "2024-06-01", 0.7)], [])
        os.environ["BORS_CORRECTIONS_DIR"] = d
        corr, sup, meta = AC.apply_factor_events("TESTSYM", events, "INS1")
        ck(len(sup) == 1 and str(sup[0]["date"])[:10] == "2024-06-01",
           "replace_step suppresses the product event on the effective date", sup)
        ck(any(str(e["date"])[:10] == "2024-06-01" and abs(e["ratio"] - 0.7) < 1e-15
               for e in corr), "replace_step inserts the reference ratio", corr)
        ch = chain(times, corr)
        ck(abs(ch["2023-12-01"] - 0.63) < 1e-12
           and abs(ch["2024-01-01"] - 0.7) < 1e-12
           and ch["2024-06-01"] == 1.0 and ch["2024-12-01"] == 1.0,
           "chain becomes 0.9 x 0.7 before the events, 0.7 on 01-01, anchor 1", ch)
        corr_ev = [e for e in corr if e.get("source") == "rahavard-reference-correction"]
        ck(len(corr_ev) == 1
           and corr_ev[0].get("correction", {}).get("version") == "test-v1"
           and corr_ev[0].get("correction", {}).get("ref_bars_sha256") == "test-ref-sha",
           "correction provenance (source/version/reference sha) is preserved", corr_ev)

        # 2) suppress_step
        d = make_pack(os.path.join(tmp, "suppress"), [factor_row("suppress_step", "2024-06-01")], [])
        os.environ["BORS_CORRECTIONS_DIR"] = d
        corr, sup, _ = AC.apply_factor_events("TESTSYM", events, "INS1")
        ch = chain(times, corr)
        ck(len(corr) == 1 and len(sup) == 1
           and abs(ch["2023-12-01"] - 0.9) < 1e-12
           and ch["2024-01-01"] == 1.0 and ch["2024-06-01"] == 1.0,
           "suppress_step removes a product-only step without inventing a ratio", ch)

        # 3) DATE_DIFF == suppress(old) + replace(new)
        d = make_pack(os.path.join(tmp, "move"),
                      [factor_row("suppress_step", "2024-06-01"),
                       factor_row("replace_step", "2024-07-01", 0.8)], [])
        os.environ["BORS_CORRECTIONS_DIR"] = d
        corr, sup, _ = AC.apply_factor_events("TESTSYM", events, "INS1")
        ch = chain(times + ["2024-07-01"], corr)
        ck(abs(ch["2023-12-01"] - 0.72) < 1e-12
           and abs(ch["2024-06-01"] - 0.8) < 1e-12
           and ch["2024-07-01"] == 1.0,
           "DATE_DIFF moves the step to the reference effective date", ch)

        # 4) raw corrections on the display copy only
        candle = {"time": "2024-01-01", "open": 120.0, "high": 120.0, "low": 90.0,
                  "high_raw": 105.0, "low_raw": 92.0, "close": 103.0, "last": 103.0}
        d = make_pack(os.path.join(tmp, "raw"),
                      [],
                      [raw_row("2024-01-01", "high_raw", 111.0),
                       raw_row("2024-01-01", "high", 111.0),
                       raw_row("2024-01-01", "close", 104.0),
                       raw_row("2024-01-01", "last", 104.0)])
        os.environ["BORS_CORRECTIONS_DIR"] = d
        src = [dict(candle)]
        out = C._literal_display_candles(src, symbol="TESTSYM", ins_code="INS1")
        ck(out[0]["high_raw"] == 111.0 and out[0]["high"] == 111.0
           and out[0]["close"] == 104.0 and out[0]["last"] == 104.0,
           "raw corrections change only the requested display fields", out)
        ck(out[0]["open"] == 120.0 and out[0]["low_raw"] == 92.0
           and out[0]["low"] == 92.0, "unrequested fields stay untouched", out)
        ck(out[0]["high"] == 111.0 and src[0]["high_raw"] == 105.0,
           "corrected high is not widened back and the input is not mutated", out)
        ck(C._literal_display_candles([dict(candle)])[0]["high"] == 105.0,
           "no symbol => no raw correction; literal high_raw still wins")

        # 5) unknown symbol is a no-op
        os.environ["BORS_CORRECTIONS_DIR"] = os.path.join(tmp, "replace", "pack")
        corr, sup, meta = AC.apply_factor_events("OTHER", events, "OTHER-INS")
        ck(corr == events and sup == [] and meta.get("covered") is False,
           "unknown symbol/ins_code is a no-op", meta)

        # 6) authoritative mode drops every product event for a covered symbol
        d = make_pack(os.path.join(tmp, "auth"),
                      [factor_row("replace_step", "2024-06-01", 0.7)], [], mode="authoritative")
        os.environ["BORS_CORRECTIONS_DIR"] = d
        corr, sup, _ = AC.apply_factor_events("TESTSYM", events, "INS1")
        ch = chain(times, corr)
        ck(len(sup) == 2 and len(corr) == 1 and ch["2024-01-01"] == 0.7
           and ch["2024-06-01"] == 1.0,
           "authoritative mode keeps only the pack step", ch)

        # 7) tampered pack is refused
        d = make_pack(os.path.join(tmp, "bad"), [factor_row("replace_step", "2024-06-01", 0.7)], [],
                      bad_hash=True)
        refused = False
        try:
            AC.load_pack(d)
        except AC.CorrectionPackError:
            refused = True
        ck(refused, "a pack with a mismatched file hash is refused, not applied")

        # 8) disabled pack is a no-op
        os.environ["BORS_CORRECTIONS_DISABLE"] = "1"
        os.environ["BORS_CORRECTIONS_DIR"] = os.path.join(tmp, "replace")
        corr, sup, meta = AC.apply_factor_events("TESTSYM", events, "INS1")
        ck(corr == events and sup == [] and AC.get_pack() is None,
           "BORS_CORRECTIONS_DISABLE=1 disables the pack")
    finally:
        if old_env is None:
            os.environ.pop("BORS_CORRECTIONS_DIR", None)
        else:
            os.environ["BORS_CORRECTIONS_DIR"] = old_env
        if old_dis is None:
            os.environ.pop("BORS_CORRECTIONS_DISABLE", None)
        else:
            os.environ["BORS_CORRECTIONS_DISABLE"] = old_dis
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("result: %d pass, %d fail" % (P, F))
    print("%d/%d" % (P, P + F))
    return 0 if F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
