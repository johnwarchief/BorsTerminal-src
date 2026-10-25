#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32C: correction-pack safety fixes.

No network, no DB.  Covers the two defects the Round 32B review found:
  * authoritative mode must not suppress a corporate event dated after the
    pack's last effective date (the frozen pack cannot know future events);
  * a raw high_raw/low_raw correction must move the visible high/low with it
    unless the pack explicitly corrects high/low.

Also checks the guard for a raw-only pack (no factor rows): it must not wipe
the product's adjustment chain, and capability exposes the coverage horizon.
"""
import hashlib
import json
import os
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


def make_pack(root, factors, raws, mode="overlay"):
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
        "schema": "ra365-correction-pack-v1", "correction_version": "test-32c",
        "created_at": "2026-10-25T00:00:00+00:00", "mode": mode,
        "files": {"factors": "factors.jsonl", "raw_ohlc": "raw_ohlc.jsonl"},
        "file_sha256": {"factors": sha(fp), "raw_ohlc": sha(rp)},
        "source": "test", "reference_sha256": "test-sha",
    }
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    return d


def use(d):
    os.environ["BORS_CORRECTIONS_DIR"] = d
    AC._CACHE.clear()


def frow(date, ratio, ins="INS1", sym="SYM", action="replace_step"):
    return {"action": action, "ins_code": ins, "symbol": sym,
            "effective_date": date, "ratio": ratio}


def rrow(date, field, value, ins="INS1", sym="SYM"):
    return {"ins_code": ins, "symbol": sym, "date": date, "field": field,
            "value": value}


def main():
    tmp = tempfile.mkdtemp(prefix="r32c_test_")
    try:
        # 1) authoritative runtime must keep events after the pack horizon.
        d = make_pack(tmp, [frow("2020-01-01", 0.5)], [], mode="authoritative")
        use(d)
        events = [
            {"date": "2020-01-01", "ratio": 0.9, "source": "ledger"},
            {"date": "2026-10-20", "ratio": 0.8, "source": "dps"},
            {"date": "2027-03-01", "ratio": 0.7, "source": "future-dps"},
        ]
        kept, sup, meta = AC.apply_factor_events("SYM", events, "INS1")
        kd = sorted(str(e["date"])[:10] for e in kept)
        sd = sorted(str(e["date"])[:10] for e in sup)
        ck(kd == ["2020-01-01", "2026-10-20", "2027-03-01"],
           "authoritative keeps both future events and adds the pack step", kd)
        ck(sd == ["2020-01-01"],
           "only the product event on the pack date is suppressed", sd)
        ck(meta.get("future_events_kept") == 2,
           "future_events_kept reports the two kept events", meta)
        ck(meta.get("as_of") == "2020-01-01",
           "the pack horizon is exposed as as_of", meta)
        cap = AC.capability("SYM", "INS1")
        ck(cap.get("as_of") == "2020-01-01" and cap.get("mode") == "authoritative",
           "capability exposes as_of and mode", cap)

        # 2) a raw-only authoritative pack must not wipe the chain.
        d = make_pack(tmp, [], [rrow("2020-08-03", "open", 101.0)],
                      mode="authoritative")
        use(d)
        kept, sup, meta = AC.apply_factor_events("SYM", events, "INS1")
        ck([str(e["date"])[:10] for e in kept] ==
           ["2020-01-01", "2026-10-20", "2027-03-01"] and sup == [],
           "a raw-only pack leaves every product event intact", (kept, sup))

        # 3) high_raw/low_raw corrections move the visible high/low.
        d = make_pack(tmp, [], [
            rrow("2020-08-03", "high_raw", 111.0),
            rrow("2020-08-03", "low_raw", 80.0),
        ])
        use(d)
        src = {"time": "2020-08-03", "open": 100.0, "high": 110.0,
               "high_raw": 105.0, "low": 90.0, "low_raw": 92.0,
               "close": 104.0, "last": 104.0}
        out = C._literal_display_candles([dict(src)], symbol="SYM", ins_code="INS1")
        ck(out[0]["high"] == 111.0 and out[0]["high_raw"] == 111.0,
           "a high_raw correction updates the visible high", out[0])
        ck(out[0]["low"] == 80.0 and out[0]["low_raw"] == 80.0,
           "a low_raw correction updates the visible low", out[0])
        ck(out[0]["open"] == 100.0 and out[0]["close"] == 104.0,
           "unrequested fields keep their values", out[0])
        ck(src["high"] == 110.0 and src["low"] == 90.0,
           "the input payload is not mutated", src)

        # 4) an explicit high correction wins over the high_raw copy.
        d = make_pack(tmp, [], [
            rrow("2020-08-03", "high_raw", 111.0),
            rrow("2020-08-03", "high", 120.0),
        ])
        use(d)
        out = C._literal_display_candles([dict(src)], symbol="SYM", ins_code="INS1")
        ck(out[0]["high"] == 120.0 and out[0]["high_raw"] == 111.0,
           "an explicit high correction wins over the literal copy", out[0])

        # 5) no symbol / no pack stays a no-op.
        os.environ.pop("BORS_CORRECTIONS_DIR", None)
        AC._CACHE.clear()
        out = C._literal_display_candles([dict(src)], symbol="SYM")
        ck(out[0]["high"] == 105.0 and out[0]["high_raw"] == 105.0,
           "without a pack the literal high rule is unchanged", out[0])
    finally:
        os.environ.pop("BORS_CORRECTIONS_DIR", None)
        AC._CACHE.clear()
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("result: %d pass, %d fail" % (P, F))
    print("%d/%d" % (P, P + F))
    sys.exit(0 if F == 0 else 1)


if __name__ == "__main__":
    main()
