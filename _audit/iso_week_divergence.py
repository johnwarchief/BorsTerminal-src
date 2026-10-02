# -*- coding: utf-8 -*-
"""_audit/iso_week_divergence.py — دروازۀ نرمِ هفتگیِ اطمینان با تقویمِ خودِ بازار می‌خواند؟

سؤالِ مالک (کارِ #73، بندِ ۵): «confidence_engine._week_key و مشخص کن آیا ISO Monday با
calendar مورد استفاده Reference تفاوت ایجاد می‌کند یا خیر. این موضوع را با Candle Contract
قاطی نکن.» پس این فایل نه به کندل دست می‌زند نه به parity؛ فقط یکِ تقویم را می‌سنجد.

سه سنجیِ مقابله:

  ۱) `confidence_engine._week_key` → (سال ایزو، هفته ایزو) = سطلِ **دوشنبه‌محور**.
     `_weekly_closes` ردیف‌ها را نزولی می‌پیماید و اولینِ ردیفِ هر کلید را می‌گیرد، پس
     «بستۀ هفتگی» = **تازۀ‌ترینِ روزِ همان هفتهٔ ایزو** = یکشنبه/شنبه.
  ۲) `api/chart.py:1160` (بازنمونهٔ هفتگیِ خودِ چارت) = `d - (weekday+2)%7` → سطلِ
     **شنبه‌محور**: تازۀ‌ترینِ روزِ هفتهٔ ایرانی = چهارشنبه/پنجشنبه.
  ۳) رفرنس: سطلِ هفتگیِ رهاورد شنبه‌محور است — §۱-ج ب با دادۀ خودِ آن‌ها سنجیده شد
     (درِ اجرای آخر: ۱۵٬۷۳۲ از ۱۵٬۷۸۳ سطل با حجمِ روزِ اولِ سطل می‌خواند).

سنجه‌ها (هیچ‌کدام مقابلهٔ ترتیبیِ دو سری نیست — چون شمارِ سطل‌ها فرق دارد و اولین سطلِ
اضافه همه‌چیز را جابه‌جا می‌کند؛ این اشتباهِ نسخهٔ اولِ همین فایل بود و اصلاح شد):

  • تأخیرِ نمونه: نمونۀ هر سطلِ ISO چندِ **نشست** پیش‌تر از پایانِ همان هفتهٔ ایرانی است.
  • قیمتِ از دست رفته: برایِ هر هفتهٔ ایرانی، closeِ روزِ نمونه در برابرِ closeِ پایانِ هفته.
  • اثرِ نهایی رویِ محصول: RSI7 و مقایسهٔ MA، همان‌ها که `_weekly_gate` مصرف می‌کند،
    و این‌که آیا «تصمیمِ دروازه» (oversold ≤ 30) عوض می‌شود.

فقط اندازه‌گیری — هیچ کدی اینجا عوض نمی‌شود. اجرا:
  python _audit/iso_week_divergence.py "فولاد,وبملت,…"     # یا بی‌arg: ۱۲۰ نمادِ پُردata
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import statistics
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import confidence_engine as CE  # noqa: E402


def sat_week(d):
    """شنبه‌محور — همان `d - timedelta((weekday+2)%7)` درِ api/chart.py:1160."""
    return (d - dt.timedelta(days=(d.weekday() + 2) % 7)).isoformat()


def weekly_by_rule(rows, keyfn):
    """ردیف‌هایِ نزولی (تازه‌ترین اول) → بستۀ هر سطل = اولینِ ردیفِ آن کلید (قاعدۀ خودِ برنامه)."""
    out, seen, ends = [], set(), {}
    for date_s, close in rows:
        d = dt.date.fromisoformat(str(date_s)[:10])
        k = keyfn(d)
        if k in seen:
            continue
        seen.add(k)
        out.append(float(close))
        ends[k] = d
    return out, ends


def main():
    argv = [a for a in sys.argv[1:] if a.strip()]
    con = sqlite3.connect(f"file:{os.path.join(ROOT, 'market.db')}?mode=ro", uri=True, timeout=30)
    if argv:
        syms = [s.strip() for s in argv[0].split(",") if s.strip()]
        src = "فهرستِ arg (سبدِ parity + نام‌هایِ مالک)"
    else:
        syms = [s for (s,) in con.execute(
            "SELECT symbol FROM price_history GROUP BY symbol HAVING COUNT(*) >= 250 "
            "ORDER BY COUNT(*) DESC LIMIT 120")]
        src = "۱۲۰ نمادِ پُردata"
    print(f"نماد: {len(syms)} · {src} · بانک فقط‌خواندنی (market.db دست‌نخورده)")

    lag = Counter()
    diffs = []
    rsi_delta, gate_swaps, bull_swaps, verdicts = [], 0, 0, 0
    elig = [0, 0]          # چند نماد زیرِ ۵۲ سطلِ ISO / شنبه از دروازه بیرون می‌مانند
    done = skipped = 0
    n_iso_tot = n_sat_tot = rows_tot = 0
    examples = []
    for s in syms:
        rows = [(r[0], r[1]) for r in con.execute(
            "SELECT date, close FROM price_history WHERE symbol=? AND close > 0 "
            "ORDER BY date DESC", (s,)).fetchall()]
        if len(rows) < 120:      # برایِ دو سریِ RSI7 و مقایسۀ MA52 به ≥۵۲ سطل نیاز است
            skipped += 1
            continue
        done += 1
        rows_tot += len(rows)
        iso, ends_iso = weekly_by_rule(rows, lambda d: d.isocalendar()[:2])
        sat, ends_sat = weekly_by_rule(rows, sat_week)
        n_iso_tot += len(iso)
        n_sat_tot += len(sat)

        # پایانِ هر هفتهٔ ایرانی (تازۀ‌ترینِ ردیفِ آن هفته) — صعودی مرتب می‌شود تا فاصلۀ
        # «نشست» شمârده شود، نه «روز».
        by_wk = {}
        for date_s, _ in rows:
            d = dt.date.fromisoformat(str(date_s)[:10])
            by_wk.setdefault(sat_week(d), []).append(d)
        asc_days = sorted({d for wk in by_wk.values() for d in wk})
        pos = {d: i for i, d in enumerate(asc_days)}
        for k, sample in ends_iso.items():
            wk = sat_week(sample)
            end = max(by_wk[wk])
            lag[pos[end] - pos[sample]] += 1
        # قیمتِ از دست رفته: closeِ روزِ نمونه در برابرِ closeِ پایانِ همان هفتهٔ ایرانی
        close_of = {str(d): None for d in asc_days}
        for date_s, c in rows:
            close_of[str(dt.date.fromisoformat(str(date_s)[:10]))] = float(c)
        for sample in ends_iso.values():
            wk_end = max(by_wk[sat_week(sample)])
            a, b = close_of[str(sample)], close_of[str(wk_end)]
            if a and b:
                diffs.append(abs(b - a) / b * 100.0)

        r_i, r_s = CE._rsi(iso, 7), CE._rsi(sat, 7)
        # رأیِ خودِ دروازه (`_weekly_gate`): bullish = close > MA52 ، oversold = RSI7 ≤ 30
        def verdict(series):
            if len(series) < 52 or series[0] <= 0:
                return None
            ma = sum(series[:52]) / 52.0
            r = CE._rsi(series, 7)
            return {"bullish": series[0] > ma, "oversold": (r is not None and r <= 30.0),
                    "rsi": r}
        vi, vs = verdict(iso), verdict(sat)
        if len(iso) >= 52:
            elig[0] += 1
        if len(sat) >= 52:
            elig[1] += 1
        if vi and vs:
            verdicts += 1
            rsi_delta.append(abs(vi["rsi"] - vs["rsi"]))
            if vi["oversold"] != vs["oversold"]:
                gate_swaps += 1
            if vi["bullish"] != vs["bullish"]:
                bull_swaps += 1
            if len(examples) < 6 and (vi["bullish"] != vs["bullish"] or abs(vi["rsi"] - vs["rsi"]) > 5):
                examples.append({"symbol": s, "rsi_iso": round(vi["rsi"], 2),
                                 "rsi_sat": round(vs["rsi"], 2),
                                 "bullish_iso": vi["bullish"], "bullish_sat": vs["bullish"],
                                 "oversold_iso": vi["oversold"], "oversold_sat": vs["oversold"],
                                 "iso_sample_days": [str(d) for d in list(ends_iso.values())[:5]],
                                 "sat_sample_days": [str(d) for d in list(ends_sat.values())[:5]]})
    con.close()

    tot_lag = sum(lag.values())
    print("\n═══ نتیجه ═══")
    print(f"  نماد سنجیده‌شده: {done} (رد شد: {skipped}) · ردیفِ روزانۀ مجموع: {rows_tot:,}")
    print(f"  شمارِ سطل: ISO میانگینِ {n_iso_tot/max(1,done):.1f} · "
          f"شنبه‌محور {n_sat_tot/max(1,done):.1f} → ISO {(n_iso_tot-max(0,n_sat_tot))/max(1,n_sat_tot):+.2%} سطل بیشتر")
    print(f"  تأخیرِ نمونۀ ISO از پایانِ همان هفتهٔ ایرانی (تعداد نشست): "
          f"{dict(sorted(lag.items()))}")
    print(f"  یعنی درِ {lag[0]/max(1,tot_lag):.1%} سطل‌ها نمونه هم‌زمان با پایانِ هفته است و "
          f"درِ {1 - lag[0]/max(1,tot_lag):.1%} پیش‌تر")
    print(f"  دروازۀ ۵۲ هفته: ISO درِ {elig[0]}/{done} نماد اجازهٔ رأی می‌دهد، "
          f"شنبه‌محور درِ {elig[1]}/{done}")
    if diffs:
        print(f"  اختلافِ close درِ همان هفتهٔ ایرانی (٪): میانه {statistics.median(diffs):.2f} · "
              f"p90 {sorted(diffs)[int(len(diffs)*0.9)]:.2f} · بیشینه {max(diffs):.2f}")
    if rsi_delta:
        print(f"  اختلافِ RSI7 هفتگی (واحد): میانه {statistics.median(rsi_delta):.2f} · "
              f"p90 {sorted(rsi_delta)[int(len(rsi_delta)*0.9)]:.2f} · بیشینه {max(rsi_delta):.2f}")
        print(f"  رأیِ دروازه رویِ {verdicts} نمادِ سنجیدنی: oversold درِ {gate_swaps} نماد و "
              f"bullish درِ {bull_swaps} نماد عوض می‌شود")
    print("  نمونه:")
    for e in examples:
        print(f"    {e['symbol']}: RSI {e['rsi_iso']} ⇄ {e['rsi_sat']} · "
              f"روزهایِ نمونه ISO={e['iso_sample_days']} شنبه={e['sat_sample_days']}")
    out = os.path.join(ROOT, "_audit", "iso_week_divergence.json")
    json.dump({"source": src, "symbols": done, "skipped": skipped, "rows": rows_tot,
               "buckets_iso_avg": n_iso_tot / max(1, done), "buckets_sat_avg": n_sat_tot / max(1, done),
               "lag_sessions": dict(sorted(lag.items())),
               "share_sampled_on_week_end": lag[0] / max(1, tot_lag),
               "week_close_diff_pct_median": statistics.median(diffs) if diffs else None,
               "rsi_delta_median": statistics.median(rsi_delta) if rsi_delta else None,
               "rsi_gate_swaps": gate_swaps, "bullish_swaps": bull_swaps,
               "verdict_symbols": verdicts, "eligible_iso": elig[0], "eligible_sat": elig[1],
               "rsi_samples": len(rsi_delta),
               "examples": examples}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("  نوشته شد:", out)


if __name__ == "__main__":
    main()
