# -*- coding: utf-8 -*-
"""dev/fts_trend_pit_v1.py — گاردِ «بدونِ نگاه‌به‌آینده / بدونِ نشتی» برایِ روندِ هفتگی و روزانه

چرا این گارد هست: تا امروز هیچ تستی رأیِ روند را رویِ یک برشِ تاریخی اجرا نکرده
بود (`as_of` درِ مسیرِ پایتون هیچ‌جا پارامتر نیست — ممیزیِ ۱۴۰۵-۰۷-۱۶). سبز بودنِ
تست‌هایِ داخلی یعنی «دستگاه داخلِ خودش سازگار است»، نه «رأیِ دیروز با رأیِ
دیروزِ امروز یکی است». این گارد دومی را می‌سنجد.

چه چیزی را با دندان می‌سنجد: `_fts_analyze_candles` تابعی از *ورودی* است، پس
«دادهٔ آینده را نمی‌بیند» را با برشِ پیشوند نمی‌شد ثابت کرد (بدیهی درست می‌شد).
دندانِ واقعی آن‌جاست که چه چیزی می‌تواند رأیِ یک برش را عوض کند:
  (الف) سبدِ هفتگیِ یک هفتهٔ بسته،
  (ب) ترتیبِ محاسبه و کلیدِ `FTS_ANALYSIS_CACHE`
      («نماد | آخرینِ close | entry_hint | basis» — `api/chart.py:2970`): اگر دو
      برشِ متفاوتِ یک نماد آخرینِ close یکسان داشته باشند، یکِ کلید می‌سازند و
      رأیِ سریِ کامل به برشِ تاریخی نشت می‌کند. این درِ همین معماری تنها راهِ
      واقعیِ «نگاه‌به‌آینده» است و بند ۱۲ همان را می‌گیرد.
  (ج) مرزِ هفته: کلیدِ سبد شنبه است (`api/chart.py:1354`) و تاریخِ کندلِ تجمیعی
      *آخرین روزِ سبد* است (`:1366`) — پس «کلیدِ سبد» را با پرسیدنِ «ادغام
      می‌شوند یا نه» می‌گیرم، نه با خواندنِ `time` و نه با بازتولیدِ فرمول.

اجرا:  python -X utf8 dev/fts_trend_pit_v1.py [--symbols 10]
خروجی: جدولِ فارسی + `_audit/fts_trend_pit_v1.json`
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from api import chart as CH  # noqa: E402

FAILED: list[str] = []
AUDIT: dict[str, object] = {}


def ck(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILED.append(msg)


def day(iso_day: str, px: float = 100.0) -> dict:
    return {"time": iso_day, "open": px, "high": px + 1, "low": px - 1,
            "close": px, "volume": 1}


def same_bucket(a_day: str, b_day: str) -> bool:
    """دو نشست درِ یک سبدِ هفتگی‌اند؟ از خودِ موتور پرسیده می‌شود (ادغام = یک سبد).
    `resample(...)[0]["time"]` کلیدِ سبد نیست: کندلِ تجمیعی تاریخِ آخرین روزِ
    سبد را می‌گیرد، پس با ورودیِ تک‌روز خودِ همان روز برمی‌گردد."""
    return len(CH._fts_resample([day(a_day), day(b_day)], "W")) == 1


def candles_from_db(conn, sym: str) -> list[dict]:
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume FROM price_history"
        " WHERE replace(replace(symbol,'ي','ی'),'ك','ک') = ?"
        " ORDER BY date ASC", (sym,)).fetchall()
    out = []
    for d, o, h, l, c, v in rows:
        dt = str(d)[:10]
        if len(dt) != 10 or None in (o, h, l, c):
            continue
        out.append({"time": dt, "open": float(o), "high": float(h), "low": float(l),
                    "close": float(c), "volume": float(v or 0)})
    return out


def verdicts(candles) -> dict:
    t = CH._fts_analyze_candles("p", candles)["trend"]
    return {"D": t["D"]["trend"], "W": t["W"]["trend"]}


def pick_symbols(conn, n: int) -> list[str]:
    rows = conn.execute(
        "SELECT replace(replace(symbol,'ي','ی'),'ك','ک') s, count(*) c,"
        "       max(date) d FROM price_history GROUP BY s"
        " HAVING c >= 260 ORDER BY d DESC, c DESC LIMIT ?", (n * 4,)).fetchall()
    seen, out = set(), []
    for s, _c, _d in rows:
        if not s or s[:3] in seen:
            continue
        seen.add(s[:3])
        out.append(s)
        if len(out) >= n:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=10)
    a = ap.parse_args()

    # ── مرزِ هفته و هندسۀ سبد ────────────────────────────────────────────
    # ۲۰۲۶-۱۰-۰۳ = شنبه (۱۱ مهر ۱۴۰۵)، ۱۰-۰۲ جمعه، ۱۰-۰۴ یکشنبه، ۱۰-۰۷ چهارشنبه؛
    # با datetime.date راستی‌آزمایی شد. اگر روزها جابه‌جا شوند این بندها می‌شکنند.
    sat, sun, mon, wed = "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-07"
    fri, next_sat, next_wed = "2026-10-02", "2026-10-10", "2026-10-14"
    ck(same_bucket(sat, sun) and same_bucket(sat, mon) and same_bucket(sat, wed),
       "۱) شنبه/یکشنبه/دوشنبه/چهارشنبه یکِ سبدند (هفتۀ ایران شنبه‌محور)")
    ck(not same_bucket(fri, sat),
       "۲) جمعه به سبدِ آن هفته نمی‌افتد — off-by-one درِ مرزِ هفته کل وتوی هفتگی"
       " را رویِ سه روزِ غلط می‌نشاند")
    ck(not same_bucket(wed, next_sat) and same_bucket(next_sat, next_wed),
       "۳) سبدِ تازه با شنبۀ بعد باز می‌شود")

    week_days = [sat, sun, mon, "2026-10-06", wed]
    days = [day(d, 100 + i) for i, d in enumerate(week_days)]
    w = CH._fts_resample(days, "W")
    ck(len(w) == 1 and w[0]["time"] == wed,
       "۴) یک سبد یک کندل است و تاریخش = آخرینِ روزِ سبد")
    ck(w[0]["open"] == 100 and w[0]["close"] == 104 and w[0]["high"] == 105
       and w[0]["low"] == 99 and w[0]["volume"] == 5,
       "۵) OHLCV سبد: open=اولین روز، close=آخرین روز، high/low=max/min، حجم=جمع")
    two = CH._fts_resample(days + [day(next_sat, 200)], "W")
    ck(len(two) == 2 and two[1]["open"] == 200 and two[1]["close"] == 200,
       "۶) نشستِ شنبۀ بعد سبدِ تازه می‌سازد و open خودش است")

    # ── بی‌داده و کم‌داده ────────────────────────────────────────────────
    ck(CH._fts_resample([], "W") == [] and verdicts([])["W"] == "na",
       "۷) سریِ تهی ⇒ `na` (نه up/down، و درِ قیف هم «رد» نیست)")
    flat = [day(d) for d in week_days] + [day("2026-10-11"), day("2026-10-14")]
    ck(verdicts(flat)["W"] == "na" and verdicts(flat)["D"] == "na",
       "۸) دادهٔ بی‌نوسان/کوتاه ⇒ `na`؛ آستانه‌ای برای UP/DOWN اختراع نمی‌شود")

    # ── خواصِ نقطۀ زمانی رویِ دادهٔ واقعی ────────────────────────────────
    db = os.path.join(ROOT, "market.db")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=60)
    try:
        syms = pick_symbols(conn, a.symbols)
        ck(len(syms) >= min(a.symbols, 3),
           f"۹) corpusِ واقعیِ بی‌شبکه: {len(syms)} نماد با ≥۲۶۰ نشست از price_history")
        base = candles_from_db(conn, syms[0]) if syms else []
        snap = json.dumps(base)
        CH._fts_analyze_candles(syms[0] if syms else "p", base)
        ck(json.dumps(base) == snap,
           "۱۰) سریِ ورودی بعد از تحلیل دست‌نخورده می‌ماند (sort/mutationِ مشترک نیست)")

        leak = bucket_bad = det_bad = det_runs = 0
        rows = []
        for sym in syms:
            cs = candles_from_db(conn, sym)
            if len(cs) < 200:
                continue
            n = len(cs)
            for cut in (n - 21, n - 42, n - 70, n - 120):
                if cut < 60:
                    continue
                head = cs[:cut]
                v_clean = verdicts(head)
                det_runs += 1
                if verdicts(head) != v_clean:
                    det_bad += 1
                # (الف) سبدِ بسته نباید با روزهایِ بعد عوض شود
                wk_all = CH._fts_resample(cs, "W")
                wk_head = CH._fts_resample(head, "W")
                if wk_head and wk_all:
                    last_closed = wk_head[-1]
                    twin = next((x for x in wk_all if x["time"] == last_closed["time"]), None)
                    if twin is not None and any(last_closed[k] != twin[k]
                                                 for k in ("open", "high", "low", "close")):
                        bucket_bad += 1
                        rows.append({"symbol": sym, "kind": "bucket", "week": last_closed["time"],
                                     "head": {k: last_closed[k] for k in ("open", "high", "low", "close")},
                                     "full": {k: twin[k] for k in ("open", "high", "low", "close")}})
                # (ب) نشتیِ کلیدِ کش: محاسبۀ سریِ کاملِ همان نماد نباید رأیِ برش را عوض کند
                before = verdicts(head)
                verdicts(cs)
                after = verdicts(head)
                if after != before:
                    leak += 1
                    rows.append({"symbol": sym, "kind": "cache-leak", "as_of": head[-1]["time"],
                                 "last_close": head[-1]["close"], "before": before, "after": after})
        ck(bucket_bad == 0,
           f"۱۱) سبدِ هفتگیِ یک هفتهٔ بسته با آمدنِ روزهایِ بعد یکی می‌ماند (تغییر: {bucket_bad})")
        ck(leak == 0,
           f"۱۲) رأیِ یکِ برش با محاسبهٔ سریِ کاملِ همان نماد عوض نمی‌شود "
           f"(نشتیِ کلیدِ کش / نگاه‌به‌آینده: {leak})")
        ck(det_bad == 0,
           f"۱۳) یکِ برش در {det_runs} محاسبه یکِ رأی می‌دهد (ناپایدار: {det_bad})")
        AUDIT.update({"symbols": len(syms), "cuts": det_runs, "cache_leak": leak,
                      "bucket_changes": bucket_bad, "determinism_bad": det_bad,
                      "details": rows[:40]})
    finally:
        conn.close()

    print()
    for r in AUDIT.get("details", []):
        print("  ", json.dumps(r, ensure_ascii=False)[:210])
    out = os.path.join(ROOT, "_audit", "fts_trend_pit_v1.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(AUDIT, fh, ensure_ascii=False, indent=1)
    print(f"written {out} — نماد={AUDIT.get('symbols')} برش={AUDIT.get('cuts')} "
          f"نشتی={AUDIT.get('cache_leak')} تغییرِ سبد={AUDIT.get('bucket_changes')}")
    print()
    if FAILED:
        print(f"fts_trend_pit guard: {len(FAILED)} FAILED")
        return 1
    print("fts_trend_pit guard OK — 13 band")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
