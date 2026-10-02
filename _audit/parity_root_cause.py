# -*- coding: utf-8 -*-
"""_audit/parity_root_cause.py — طبقه‌بندیِ گزارشِ parity به علت، نه به آستانه.

ورودی: `_audit/ra_parity_report.json` (اجرای ۳۶ نماد × {۰،۱،۲} × {last، closing}).
خروجی: چهار جدول که مستقیمِ سؤالاتِ مالک درِ کارِ #73 است:

  ۱) تفکیکِ aggregation از adjustment با شاهدِ روز (قدمِ ۲) — کدامِ تایم‌فریم،
     کدامِ فیلد، و کدامِ رفتارِ تجمیع.
  ۲) پلکانِ ضریب (قدمِ ۳): رویدادهایِ ما در برابرِ گام‌هایِ k مرجع، با تطبیقِ
     «حاصل‌ضربِ معکوس» — یعنی اگر عددِ رویدادِ ما r باشد و گامِ آن‌ها ۱/r، همان
     یکِ رویداد است و اختلاف فقط درِ روزِ اثر است. سه طبقه: same-day / shifted /
     only-one-side.
  ۳) offsetِ ثابتِ هر دورۀ زمانی: اگر یکِ رویدادِ ما درِ پلکانِ آن‌ها وجود نداشته
     باشد، کلِ تاریخِ قبلِ آن روز با یکِ عددِ ثابت جابه‌جا می‌شود و هیچ گامی درِ gap
     نمی‌بینیم — همان چیزی که درِ فولاد (۰٫۳۱۷٪) و خودرو (۰٫۶۲۲٪) اندازه گرفته شد.
  ۴) حجمِ هفتگی/ماهانه: فقط اندازه‌گیری (§۱-ج پ)، بی‌تغییرِ تصمیم.

هیچ عددی اینجا حدس نیست: همه از همان JSONِ اجرای parity می‌آید.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "_audit", "ra_parity_report.json")
if len(sys.argv) > 1:                   # _audit/parity_root_cause.py <گزارش> [مبنای]
    P = sys.argv[1] if os.path.isabs(sys.argv[1]) else os.path.join(ROOT, sys.argv[1])
A_BASIS = sys.argv[2] if len(sys.argv) > 2 else "last"

PRICE = ("open", "high", "low", "close")


def load():
    return json.load(open(P, encoding="utf-8"))


def pct(x):
    return "—" if x is None else f"{x*100:.4f}%"


def table_1_split(d):
    """۱ — aggregation در برابرِ adjustment، درِ مبنایِ پیش‌فرضِ محصول (last).

    شمار از `by_mismatch_field_and_tfِ` خودِ گزارش است و نه از نمونۀ جدول (جدولِ نمونه
    سقف دارد و ترتیبش قدیمی‌ترینِ روزهاست — بی‌این تفکیک، شمارِ فیلد سوگیری داشت).
    """
    rows = [r for r in d["table"] if r["price_basis"] == A_BASIS]
    out = defaultdict(Counter)
    exact = d.get("by_mismatch_field_and_tf") or {}
    for key, n in exact.items():
        kind, tf, basis, field = key.split("|")
        if basis == A_BASIS and kind in ("aggregation", "adjustment"):
            out[kind][(int(tf.replace("tf", "")), field)] += n
    print(f"═══ ۱) تفکیکِ aggregation از adjustment (مبنایِ {A_BASIS}، شمارِ کاملِ سطرهایِ مقایسه) ═══")
    for kind in ("aggregation", "adjustment"):
        print(f"  {kind}: جمع {sum(out[kind].values())}")
        for (tf, field), n in sorted(out[kind].items(), key=lambda x: -x[1]):
            print(f"     tf={tf} {field:<6} {n:>6}")
    agg = [r for r in rows if r["mismatch_type"] == "aggregation"]
    by = Counter(r["field"] for r in agg)
    print("  فیلدهایِ aggregation درِ نمونۀ ذخیره‌شده:", dict(by))
    return out


def reciprocal_match(ours, theirs, tol=0.002, window=15):
    """رویدادهایِ ما (date, ratio) را با گام‌هایِ k آن‌ها (to_day, ratio) جفت می‌کند.

    قاعدۀ تطبیق از داده آمد، نه از فرض: درِ رویدادهایی که روز یکی است، ratioِ گامِ
    آن‌ها دقیقاً ۱/ratioِ ماست (فولاد ۰٫۹۶۰۳۸ ↔ ۱٫۰۴۱۲۵۴). پس معکوسِ ضریب همان ضریب
    است. ولی **چهاردهصدِ روز فاصله** هم با معکوس می‌خواند (دو تقسیمِ ۹۳٪ در دو دورۀ
    مختلف) — اولینِ نسخۀ همین تابع دقیقاً همین تطبیق‌هایِ بی‌ربط را ساخت و «جابه‌جایی»
    را به ۵۳۶۳ روز کشید. پس پنجرۀ زمانی هم شرط است: نزدیک‌ترین گام درِ ±window روز.
    """
    used = set()
    pairs = []
    for ev in ours:
        want = 1.0 / float(ev["ratio"]) if ev.get("ratio") else None
        if want is None:
            pairs.append((ev, None, None))
            continue
        cands = []
        for i, st in enumerate(theirs):
            if i in used or not st.get("ratio"):
                continue
            if abs(st["ratio"] / want - 1.0) >= tol:
                continue
            g = day_gap(ev["date"], st["to_day"])
            if abs(g) <= window:
                cands.append((abs(g), i, g))
        if not cands:
            pairs.append((ev, None, None))
            continue
        _, i, g = min(cands)
        used.add(i)
        pairs.append((ev, theirs[i], g))
    leftover = [st for i, st in enumerate(theirs) if i not in used]
    return pairs, leftover


def day_gap(a, b):
    import datetime as dt
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def table_2_ladder(d):
    """۲ — پلکانِ ضریب: چه کسی رویداد دارد و دیگری ندارد، و جابه‌جاییِ روز."""
    print("\n═══ ۲) پلکانِ تعدیل: رویدادِ ما ⇄ گامِ k مرجع (مبنایِ last) ═══")
    blocks = [b for b in d["per_symbol"]
              if b["basis"] == A_BASIS and b.get("factor_schedule")
              and b.get("adjust_events") is not None]
    cls = Counter()
    per_symbol_rows = []
    big_shift = []
    for b in blocks:
        s = b["factor_schedule"]
        ours = [e for e in (b["adjust_events"] or [])]
        theirs = s.get("reference_steps") or []
        pairs, only_theirs = reciprocal_match(ours, theirs)
        same = sum(1 for _, _, g in pairs if g == 0)
        shifted = [(e, st, g) for e, st, g in pairs if st and g not in (0, None)]
        only_ours = [e for e, st, g in pairs if st is None]
        cls["same_day"] += same
        cls["shifted"] += len(shifted)
        cls["only_ours"] += len(only_ours)
        cls["only_theirs"] += len(only_theirs)
        for e, st, g in shifted:
            big_shift.append((b["symbol"], e["date"], st["to_day"], g, e["ratio"]))
        per_symbol_rows.append({"symbol": b["symbol"], "our_events": len(ours),
                                "ref_steps": s.get("n_reference_steps"),
                                "same_day": same, "shifted": len(shifted),
                                "only_ours": len(only_ours), "only_theirs": len(only_theirs),
                                "only_ours_dates": [e["date"] for e in only_ours][:20],
                                "only_theirs_dates": [st["to_day"] for st in only_theirs][:20],
                                "only_theirs_ratios": [st["ratio"] for st in only_theirs][:20],
                                # برچسبِ رویداد رویِ روزی که کندل نیست → هیچ سطرِ مقابله‌ای
                                # نمی‌سازد و پس «اختلافِ خروجی» نیست، اختلافِ ثبت است.
                                "only_ours_not_candles": sorted(
                                    set(b.get("events_not_in_candles") or [])
                                    & {e["date"] for e in only_ours})})
        print(f"  {b['symbol']:<9} رویدادِ ما={len(ours):>3} گامِ k آن‌ها={s.get('n_reference_steps'):>3} "
              f"| روز‌یکی={same:>3} جابه‌جا={len(shifted):>3} فقطِ ما={len(only_ours):>3} "
              f"فقطِ آن‌ها={len(only_theirs):>3}")
    print("  جمعِ طبقات:", dict(cls))
    shifts = Counter(g for *_, g, _r in big_shift)
    print("  توزیعِ جابه‌جاییِ روز (میلادی):", dict(sorted(shifts.items())))
    print("  نمونه‌هایِ جابه‌جایی:")
    for sym, d0, d1, g, r in sorted(big_shift, key=lambda x: -abs(x[3]))[:12]:
        print(f"     {sym:<9} ما={d0} آن‌ها={d1} Δ={g:>3} روز ratio={r}")
    return cls, per_symbol_rows


def table_3_offset(d):
    """۳ — offsetِ ثابتِ دوره: خطایِ close که درِ یکِ بازۀ بلند یکِ عدد است.

    اگر کلِ یکِ دورۀ تاریخی با یکِ نسبتِ ثابت جابه‌جا باشد، علتِ آن **یکِ رویدادِ
    اضافه/کم** درِ زنجیرِ ضریب است، نه واگراییِ روزانه. عددِ ثابت را از میانۀ
    relative_errِ سطرهایِ close درِ همان نماد می‌گیریم و بازۀ تاریخ‌ها را هم.
    """
    print("\n═══ ۳) offsetِ ثابتِ دورۀ تاریخی (مبنایِ last، فیلدِ close) ═══")
    rows = [r for r in d["table"] if r["price_basis"] == A_BASIS and r["field"] == "close"
            and r["timeframe"] == 0 and r["relative_err"] is not None]
    by_sym = defaultdict(list)
    for r in rows:
        by_sym[r["symbol"]].append((r["date"], r["relative_err"], r["mismatch_type"]))
    out = []
    for sym, items in sorted(by_sym.items()):
        items.sort()
        bad = [(dte, e) for dte, e, t in items if t in ("adjustment", "data_source", "field_mapping")]
        if not bad:
            continue
        lvl = statistics.median([e for _, e in bad])
        spread = max(e for _, e in bad) - min(e for _, e in bad)
        out.append({"symbol": sym, "err_rows": len(bad), "median_rel_err": round(lvl, 6),
                    "spread": round(spread, 6), "first": bad[0][0], "last": bad[-1][0],
                    "flat_era": spread < 0.0002})
        print(f"  {sym:<9} سطرِ خطادار={len(bad):>4}  median_err={lvl*100:7.4f}%  "
              f"گستره={spread*100:6.4f}%  بازه={bad[0][0]}…{bad[-1][0]}  "
              f"{'ثابتِ کامل' if spread < 0.0002 else 'چندِ سطح'}")
    flat = sum(1 for o in out if o["flat_era"])
    print(f"  نمادهایِ دارایِ offset: {len(out)} از {len(by_sym)} | "
          f"که درِ {flat} نماد offset یکِ عددِ ثابت است (نه نویزِ پراکندۀ روزانه)")
    return out


def table_4_volume(d):
    """۴ — رفتارِ حجمِ هفتگی/ماهانه: فقط اندازه‌گیری (§۱-ج پ). تصمیمِ مالک باز است."""
    print("\n═══ ۴) حجمِ سطل: دو فرضیه در برابرِ سطلِ منتشرشدۀ خودِ مرجع (اندازۀ بی‌تصمیم) ═══")
    vr = [v for v in d["volume_rules"] if v["basis"] == A_BASIS and v.get("buckets_shared")]
    for rule in ("volume", "volume_sum"):
        comp = sum(v[rule]["compared"] for v in vr if v.get(rule))
        hit = sum(v[rule]["match_within_0.5pct"] for v in vr if v.get(rule))
        meds = [v[rule]["median_our_over_reference"] for v in vr
                if v.get(rule) and v[rule]["median_our_over_reference"]]
        print(f"  قاعدۀ «{rule}»: {hit}/{comp} سطل درِ ±۰٫۵٪ می‌خواند"
              + (f" | میانۀ ما/مرجع = {statistics.median(meds):.4f}" if meds else ""))
    per_tf = defaultdict(lambda: [0, 0, 0, 0])
    for v in vr:
        t = per_tf[v["tf"]]
        t[0] += v["volume"]["compared"]; t[1] += v["volume"]["match_within_0.5pct"]
        t[2] += v["volume_sum"]["compared"]; t[3] += v["volume_sum"]["match_within_0.5pct"]
    for tf, (c1, h1, c2, h2) in sorted(per_tf.items()):
        print(f"     tf={tf}: روزِ اول {h1}/{c1}   جمع {h2}/{c2}")
    return vr


def table_5_presence(d):
    """۵ — بود/نبودِ سطر: حلقۀ دادۀ مرجع در برابرِ عمقِ بانکِ ما."""
    print("\n═══ ۵) بود و نبودِ روز (بی‌ربط به قیمت) ═══")
    al = d["day_alignment"]
    tot = Counter()
    for a in al:
        for k in ("shared", "only_reference", "only_bors"):
            tot[f"tf{a['tf']}·{k}"] += a[k]
    for key, n in sorted(tot.items()):
        print(f"  {key:<22} {n:>7}")
    only_ref = [a for a in al if a["tf"] == 0 and a["only_reference"]]
    print(f"  نمادهایی که مرجع روزی دارد که ما نداریم (tf0): {len(only_ref)} — "
          f"نمونۀ تاریخ: {[a['sample_only_reference'][:2] for a in only_ref[:6]]}")
    holes = [a for a in al if a["tf"] == 0 and a.get("last_shared")]
    old = sorted(holes, key=lambda a: a["last_shared"])[:6]
    print("  قدیمی‌ترین «آخرین روزِ مشترک» (حلقۀ ۱۴۰۴-۱۲ خودِ مرجع):",
          [(a["symbol"], a["last_shared"]) for a in old])
    return tot


def main():
    d = load()
    print(f"گزارش: {d['generated']} · ردیفِ مقایسه={d['rows_compared']:,} · "
          f"منابعِ مرجع = Rahavard · فضایِ {d['space']}")
    print("طبقه‌ها (همۀ ۹۱۹هزار سطر):", json.dumps(d["by_mismatch_type"], ensure_ascii=False))
    split = table_1_split(d)
    cls, ladder_rows = table_2_ladder(d)
    offsets = table_3_offset(d)
    vols = table_4_volume(d)
    presence = table_5_presence(d)
    out = {"report": P, "basis": A_BASIS, "generated": d["generated"], "rows_compared": d["rows_compared"],
           "by_mismatch_type": d["by_mismatch_type"],
           "aggregation_vs_adjustment": {k: {f"tf{tf}|{field}": n for (tf, field), n in v.items()}
                                         for k, v in split.items()},
           "ladder_classes": dict(cls), "ladder_per_symbol": ladder_rows,
           "era_offsets": offsets, "volume_rules": vols,
           "day_presence": dict(presence)}
    dst = os.path.join(ROOT, "_audit", "parity_root_cause.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("نوشته شد:", dst)


if __name__ == "__main__":
    sys.exit(main())
