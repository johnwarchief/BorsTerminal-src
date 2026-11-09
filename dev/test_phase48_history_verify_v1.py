# dev/test_phase48_history_verify_v1.py — S4: منطقِ سنجشِ API (بدونِ شبکه)
# payloadِ ساختگی: خامِ موجود (close=closing، last غایب)، خامِ backfill (مشتق از
# مرجع)، و یک تاریخ با ضریبِ ناسازگار. هیچ تماسی با سرور/بانک ندارد.
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "phase48"))

import verify_history_api as V  # noqa: E402

P = F = 0


def check(name, got, want):
    global P, F
    if got == want:
        P += 1
        print(f"  ✓ {name}")
    else:
        F += 1
        print(f"  ✗ {name}: got={got!r} want={want!r}")


def row(o, h, l, c, v):
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}


def main():
    ref_raw = {
        "2024-01-01": row(10, 12, 8, 10, 100),
        "2024-01-02": row(20, 22, 18, 20, 200),
        "2024-01-03": row(30, 32, 28, 30, 300),
    }
    ref_adj = {
        "2024-01-01": row(5, 6, 4, 5, 100),
        "2024-01-02": row(10, 11, 9, 10, 200),
        "2024-01-03": row(15, 16, 14, 15, 300),
    }
    payload = {
        "candles": [
            {"time": "2024-01-01", "open": 10, "high": 12, "low": 8, "high_raw": 12,
             "low_raw": 8, "close": 10, "last": None, "volume": 100,
             "src": "legacy-unknown"},
            {"time": "2024-01-02", "open": 20, "high": 22, "low": 18, "high_raw": 22,
             "low_raw": 18, "close": 20, "last": 20, "volume": 200,
             "src": "rahavard365"},
            {"time": "2024-01-03", "open": 30, "high": 32, "low": 28, "high_raw": 32,
             "low_raw": 28, "close": 30, "last": 30, "volume": 300,
             "src": "rahavard365"},
            {"time": "2024-01-04", "open": 1, "high": 2, "low": 1, "high_raw": 2,
             "low_raw": 1, "close": 2, "last": 2, "volume": 10,
             "src": "legacy-unknown"},
        ],
        "factors": [{"time": "2024-01-01", "factor": 0.5}, {"time": "2024-01-02", "factor": 0.5},
                    {"time": "2024-01-03", "factor": 0.8}, {"time": "2024-01-04", "factor": 1.0}],
        "dbRows": 4, "liveInjected": False,
        "adjustSource": "local-cache",
        "adjustCapability": {
            "functional_status": "AVAILABLE_REFERENCE_CORRECTION",
            "functional_available": True, "combined_available": True,
            "chain_complete": True, "event_count": 3,
            "availability": {"status": "UNVERIFIED", "window_start": "2024-01-01",
                             "window_end": "2024-01-04", "window_available": False},
            "coverage": {"coverage_start": "2024-01-01", "coverage_end": "2024-01-03",
                         "pre_coverage_candles": 0},
            "corrections": {"covered": True, "mode": "authoritative",
                            "version": "ra365-r32b-v2",
                            "reference_sha256": "abc"},
        },
    }
    out = V.compare_symbol("فولاد", payload, ref_raw, ref_adj)
    rp, rn = out["raw"]["pre"], out["raw"]["new"]
    ap, an = out["adj"]["pre"], out["adj"]["new"]
    check("خامِ موجود: یک روزِ مشترک", rp["common"], 1)
    check("خامِ موجود: close=closing", rp["close_by_closing"], 1)
    check("خامِ موجود: last غایب", rp["last_missing"], 1)
    check("خامِ موجود: open/high/low/حجم برابر", (rp["open_mismatch"],
          rp["high_mismatch"], rp["low_mismatch"], rp["volume_mismatch"]), (0, 0, 0, 0))
    check("خامِ backfill: دو روز", rn["common"], 2)
    check("خامِ backfill: بی‌نابرابری", (rn["open_mismatch"], rn["high_mismatch"],
          rn["low_mismatch"], rn["volume_mismatch"]), (0, 0, 0, 0))
    check("فقط-API", out["raw"]["api_only"], 1)
    check("تعدیلِ موجود: OHLC با closing", ap["ohlc_ok_closing"], 1)
    check("تعدیلِ موجود: OHLC با last غایب", ap["ohlc_ok_last"], 0)
    check("تعدیلِ backfill: یک OHLC درست (d2)", an["ohlc_ok_closing"], 1)
    check("تعدیلِ backfill: factor بد (d3)", an["factor_bad"], 1)
    check("بیشینهٔ انحرافِ ضریب", round(out["adj"]["factor_max_rel"]["new"], 6), 0.6)
    check("capability", (out["capability"]["functional_status"],
                         out["capability"]["availability_status"],
                         out["capability"]["correction_version"]),
          ("AVAILABLE_REFERENCE_CORRECTION", "UNVERIFIED", "ra365-r32b-v2"))
    check("روز/هفته/ماه", (out["wm"]["days"], out["wm"]["weeks"], out["wm"]["months"]),
          (4, 1, 1))
    print(f"\n{P} passed / {F} failed")
    return 0 if F == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
