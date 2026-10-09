# -*- coding: utf-8 -*-
"""tools/funnel_universe_benchmark.py — بند ۳۵: سنجشِ کلِجامعه، بی‌کوتاه‌کردنِ داوری

ثابت می‌کند که سرعت با **حذف نکردن** نمادها به دست آمده است: شمارِ نمادهایِ
داوری‌شده درِ هر گام باید با جامعۀ ورودی بخواند. اگر روزی `slice`/`cap`/`top-N`
به مسیرِ تصمیم برگردد، همین ابزار قرمز می‌شود (نه گاردِ UI).

اجرا:  python -X utf8 tools/funnel_universe_benchmark.py
خروجی: `_audit/funnel_universe_benchmark.json` + جدولِ فارسیِ stdout
"""
from __future__ import annotations

import json
import os
import sys
import time
import tracemalloc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import funnel_engine as FE  # noqa: E402

# واژگانِ وضعیت ازِ خودِ موتور خوانده می‌شود، نه از کپیِ دستِ این‌جا: §۱۵.۱۷
# ششمین حالت (not_in_universe) را افزود و این ابزار بی‌آن پنج حالت را با
# جامعۀ کامل نمی‌خواند و «ثابتِ no-truncation» را دروغ می‌گفت (سنجش: جمعِ هر
# گام ۵۸۶۳ است، نه ۳۶۵).
STATUSES = FE.STATUSES



def _read_scan():
    """ردیف‌هایِ اسکن + امضا، با اتصالِ read-only (قفلِ نوشتن نمی‌گیرد)."""
    import sqlite3
    from bors_config import DB_PATH
    import funnel_tech_scan as SCAN
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30)
    try:
        return SCAN.stored(conn), SCAN.sig_map(conn)
    finally:
        conn.close()

def _get_json(url: str):
    import urllib.request
    with urllib.request.urlopen(url, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    # داده از همان HTTPِ اپ خوانده می‌شود (نه buildِ درون‌فرآیند): بانک درِ این
    # ساعت در دستِ سرورِ در حالِ اجراست و ساختنِ دوبارهٔ فریم «database is
    # locked» می‌دهد — همان قفلی که خودِ اپ حلش کرده است.
    base = os.environ.get("BORS_BASE", "http://127.0.0.1:8001")
    t_load = time.time()
    board = (_get_json(f"{base}/api/market") or {}).get("data") or []
    screen = (_get_json(f"{base}/api/screener") or {}).get("data") or []
    load_ms = int((time.time() - t_load) * 1000)
    t_scan = time.time()
    scan, sigs = _read_scan()
    scan_ms = int((time.time() - t_scan) * 1000)

    runs = []
    for label, kw in (
        ("swing (preset)", dict(preset="swing")),
        ("trend (preset)", dict(preset="trend")),
        ("custom f_susp,f_noqteh", dict(preset="custom", custom_chain=["f_susp", "f_noqteh"])),
        ("custom f_clock,f_susp", dict(preset="custom", custom_chain=["f_clock", "f_susp"])),
        ("custom بی‌فیلتر (کلِ universe)", dict(preset="custom", custom_chain=[])),
        ("hard fundamental", dict(preset="custom", custom_chain=["f_susp"], fund_mode="hard")),
    ):
        tracemalloc.start()
        t0 = time.time()
        out = FE.evaluate(board, screen, tech_scan=scan, tech_sigs=sigs, **kw)
        ms = int((time.time() - t0) * 1000)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        joined = out["universe"]["joined"]
        cov = out["coverage"]
        bad = [s for s in ("tape", "technical", "fundamental", "handover")
               if sum(cov[s].get(k, 0) for k in STATUSES) != joined]
        u = out["universe"]
        # رأیِ §۱۵.۱۷: جامعۀ تابلو = واجدانِ غربال + خارج‌شدگان. بی‌این خط،
        # ابزارِ benchmark خودِ تقسیمِ تازه را نمی‌دید.
        assert u["market"] == u["screening"] + u["excluded"], (
            "X = Y + شکست نشد: " + json.dumps({k: u[k] for k in ("market", "screening", "excluded")}))
        runs.append({
            "case": label,
            "ms": ms,
            "peak_memory_mb": round(peak / 1e6, 1),
            "universe_count": joined,
            "board_rows": out["universe"]["board"],
            "duplicate_rows": out["universe"].get("duplicate_rows", 0),
            "screened": out["universe"]["screened"],
            "stages_not_summing": bad,
            "tape_matched": out["stages"]["tape"]["matched"],
            "technical": cov["technical"],
            "fundamental": cov["fundamental"],
            "handover": cov["handover"],
            "final_survivor_count": cov["handover"].get("pass", 0),
            "matrix_rows": len(out["status_matrix"]),
        })

    # کشِ هشت‌ثانیه‌ایِ خودِ اندپوینت: دو پرسشِ پیاپیِ یک‌کلید رویِ HTTP
    q = "?preset=trend&fund_mode=standard"
    t0 = time.time(); first = _get_json(f"{base}/api/funnel{q}"); cold = int((time.time() - t0) * 1000)
    t0 = time.time(); second = _get_json(f"{base}/api/funnel{q}"); warm = int((time.time() - t0) * 1000)
    cache_hit = bool(second.get("cached_for_ms") is not None) and not first.get("cached_for_ms")

    try:
        import sqlite3
        from bors_config import DB_PATH
        import funnel_tech_scan as SCAN
        c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30)
        fresh = SCAN.freshness(c)
        c.close()
    except Exception as e:  # بانک نبود: خطا درِ JSON می‌نشیند، نه صفرِ ساختگی
        fresh = {"error": str(e)}

    result = {
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "load_ms": load_ms,
        "scan_read_ms": scan_ms,
        "scan_stored_rows": len(scan),
        "symbols_with_history": len(sigs),
        "cache_cold_ms": cold,
        "cache_warm_ms": warm,
        "cache_hit_rate": "۱/۲ (دوم از کشِ ۸ثانیه‌ایِ اندپوینت)" if cache_hit else "۰/۲ - بی‌کش",
        "cached_for_ms": second.get("cached_for_ms"),
        "concurrency": "evaluate() تک‌رشته است؛ داوریِ تکنیکال درِ رشتهٔ پس‌زمینه "
                       "ساخته می‌شود و درِ درخواست فقط خوانده می‌شود",
        "tech_scan_freshness": fresh,
        "runs": runs,
        "no_truncation_proof": all(not r["stages_not_summing"] and r["matrix_rows"] == r["universe_count"]
                                   for r in runs),
    }
    os.makedirs(os.path.join(ROOT, "_audit"), exist_ok=True)
    out_path = os.path.join(ROOT, "_audit", "funnel_universe_benchmark.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)

    print("| case | زمان (ms) | اوج حافظه (MB) | universe | به تابلو رسید | ماندگان | تحویل PASS | جمعِ وضعیت‌ها = universe |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in runs:
        ok = "✓" if not r["stages_not_summing"] else "✗ " + ",".join(r["stages_not_summing"])
        print(f"| {r['case']} | {r['ms']} | {r['peak_memory_mb']} | {r['universe_count']} "
              f"| {r['tape_matched']} | {r['handover'].get('pass', 0) + r['handover'].get('reject', 0)} "
              f"| {r['final_survivor_count']} | {ok} |")
    print()
    print(f"cold {cold} ms → warm {warm} ms (کشِ ۸ثانیه‌ای)")
    print(f"ردیف‌هایِ اسکنِ ذخیره‌شده: {len(scan)} | نماد با سابقه: {len(sigs)}")
    print(f"ثابتِ no-truncation: {result['no_truncation_proof']}")
    print(f"written {out_path}")
    return 0 if result["no_truncation_proof"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
