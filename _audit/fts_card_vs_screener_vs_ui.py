# -*- coding: utf-8 -*-
"""_audit/fts_card_vs_screener_vs_ui.py — سه‌سوزنهٔ بنیادی: کارت ⇄ اسکرینر ⇄ منطقِ UI

سؤالِ مالک: «منطقِ کاننیکال درِ بک‌اند اصلاح شده؛ جدول/کارتِ فرانت همگام‌اند؟»
برایِ پاسخِ عددی، هر ۸۷۳ نمادِ `/api/screener` با کارتِ همان نماد
(`/api/fundamental/{symbol}`) و با آن چیزی که `FtsScreenTable.tsx` نشان می‌دهد
مقایسه می‌شود. سه چیز جدا سنجیده می‌شود:

  الف) **کارت ⇄ اسکرینر (خودِ بک‌اند):** پرچم‌هایِ پنج محور، امتیاز، ارزش‌ها و
      رای. هر ناهمخوانی یعنی «Card = API = Screener» هنوز درست نیست.
  ب) **منطقِ محلیِ UI برایِ N/A:** `assetScope.isFinancialOrHolding` (regex رویِ
      نام/صنعت) در برابرِ `indicators.1.volume.applicable` و `indicators.3.band`
      و `indicators.4.na` از خودِ کارت. اگر یکی باشند، UI اگرچه از منبعِ درست
      نمی‌خواند ولی امروز می‌گردد؛ اگر نبودند، تعدادِ واگرایی گزارش می‌شود.
  ج) **پری‌ست‌هایِ فرانت:** «سوپر بنیادی» که فرانت با `score>=4 && free` می‌شمارد
      در برابرِ `verdict === 'STRONG'` (جزوه: امتیازِ ۴+ **و** سه محورِ بلاکر).

فقط GET. نوشتنِ هیچ. کارت‌ها با سه نخ خوانده می‌شوند (محلی، بی‌فشار).
"""
import concurrent.futures as cf
import json
import re
import sys
import urllib.parse
import urllib.request

APP = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001").rstrip("/")

# عینِ assetScope.ts / FINANCIAL_HOLDING_RE — برایِ سنجشِ «آیا regex همان
# applicableِ کارت را می‌گوید». گاردِ فرانت (`fts-ui-canonical.spec.ts`) همین
# فهرست را با خودِ TS می‌سنجد؛ اینجا فقط شمارشِ سریع است.
FIN_RE = re.compile(
    r"هلدينگ|هلدینگ|سرمايه گذاري|سرمایه گذاري|سرمایه‌گذاری|سرمایه گذاری|واسطه گري|واسطهگری"
    r"|بانك|بانک|بيمه|بیمه|ليزينگ|لیزینگ|صندوق|تامين سرمايه|تأمین سرمایه")


def norm(s):
    s = (s or "")
    s = s.replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"[\u200c]", "", s)


def get(path):
    with urllib.request.urlopen(APP + path, timeout=180) as r:
        return json.load(r)


def card_of(sym):
    d = get("/api/fundamental/" + urllib.parse.quote(sym))
    return d.get("data") or d


def cmp(a, b):
    return "≠" if a != b else "="


def main():
    body = get("/api/screener?limit=20000")
    rows = {r["symbol"]: r for r in body["data"]}
    syms = sorted(rows)
    print(f"نمادها درِ /api/screener: {len(syms)}")
    cards = {}
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(card_of, s): s for s in syms}
        for i, f in enumerate(cf.as_completed(futs), 1):
            s = futs[f]
            try:
                cards[s] = f.result()
            except Exception as e:
                print("  card failed:", s, str(e)[:80])
            if i % 150 == 0:
                print(f"  {i}/{len(syms)} کارت خوانده شد")

    diff = {k: [] for k in ("i1", "i1a", "i1b", "i2", "i3", "i4", "i5", "score",
                            "verdict", "rev_growth", "gross_margin", "sales_to_mcap",
                            "potential", "applicable_false_strong")}
    ui = {k: [] for k in ("i1b_regex_vs_applicable", "i3_na_regex_vs_band",
                          "i4_na_regex_vs_na", "i3_gap_not_na", "i4_gap_not_na",
                          "i1b_hidden_pass")}
    presets = {"fe_super": [], "be_strong": []}
    for s, r in rows.items():
        c = cards.get(s)
        if not c:
            continue
        p = c.get("passes") or {}
        ind = c.get("indicators") or {}
        v1 = (ind.get("1") or {}).get("volume") or {}
        g3 = (ind.get("3") or {}) or {}
        v4 = (ind.get("4") or {}) or {}
        for key, a, b in (("i1", r.get("i1_pass"), p.get("1_growth")),
                          ("i1a", r.get("i1a_pass"), p.get("1a_monetary_growth")),
                          ("i1b", r.get("i1b_pass"), p.get("1b_volume_growth")),
                          ("i2", r.get("i2_pass"), p.get("2_eps_trend")),
                          ("i3", r.get("i3_pass"), None if g3.get("na") else p.get("3_gross_margin")),
                          ("i4", r.get("i4_pass"), None if v4.get("na") else p.get("4_sales_to_mcap")),
                          ("i5", r.get("i5_pass"), p.get("5_industry")),
                          ("score", r.get("score"), c.get("score")),
                          ("verdict", r.get("verdict"), c.get("verdict"))):
            if a != b:
                diff[key].append((s, a, b))
        for key, a, b in (("rev_growth", r.get("rev_growth"),
                           ((ind.get("1") or {}).get("monetary") or {}).get("monetary_pct")),
                          ("gross_margin", r.get("gross_margin"), g3.get("margin_pct")),
                          ("sales_to_mcap", r.get("sales_to_mcap"), v4.get("sales_to_mcap")),
                          ("potential", r.get("profit_potential_pct"), v4.get("potential_pct"))):
            if (a or 0) and (b or 0) and abs(float(a) - float(b)) > 0.051:
                diff[key].append((s, a, b))
            elif not (a or 0) and (b or 0):
                diff[key].append((s, a, b))
        # منطقِ N/A خودِ UI در برابرِ اعلامِ کارت
        fin = bool(FIN_RE.search(norm(r.get("name"))) or FIN_RE.search(norm(r.get("sector_name"))))
        if bool(v1.get("applicable", True)) is False:
            ui["i1b_regex_vs_applicable"].append((s, fin))
            if fin:
                ui["i1b_hidden_pass"].append(s)
        elif fin:
            ui["i1b_hidden_pass"].append(s + "؟")
        na3 = bool(g3.get("na")) or g3.get("band") == "not_applicable"
        if na3:
            ui["i3_na_regex_vs_band"].append((s, fin))
            if not fin:
                ui["i3_gap_not_na"].append(s)
        if bool(v4.get("na")):
            ui["i4_na_regex_vs_na"].append((s, fin))
            if not fin:
                ui["i4_gap_not_na"].append(s)
        if (r.get("score") or 0) >= 4 and r.get("pricing_mode") == "free":
            presets["fe_super"].append(s)
        if r.get("verdict") == "STRONG":
            presets["be_strong"].append(s)

    n = len(rows)
    print(f"\nالف) کارت ⇄ اسکرینر رویِ {n} نماد:")
    for k in ("i1", "i1a", "i1b", "i2", "i3", "i4", "i5", "score", "verdict",
              "rev_growth", "gross_margin", "sales_to_mcap", "potential"):
        v = diff[k]
        print(f"   {k:14s} ناهمخوان={len(v):4d}  {v[:3]}")

    print("\nب) منطقِ محلیِ UI (regex نام/صنعت) در برابرِ اعلامِ کارت:")
    print(f"   ۱b: کارت «applicable=False» برایِ {len(ui['i1b_regex_vs_applicable'])} نماد؛"
          f" regex هم‌راستا: {sum(1 for _, f in ui['i1b_regex_vs_applicable'] if f)}"
          f" | واگرا: {sum(1 for _, f in ui['i1b_regex_vs_applicable'] if not f)}")
    print(f"   ۳:  کارت na/band=not_applicable برایِ {len(ui['i3_na_regex_vs_band'])} نماد؛"
          f" regex هم‌راستا: {sum(1 for _, f in ui['i3_na_regex_vs_band'] if f)}"
          f" | واگرا: {len(ui['i3_gap_not_na'])}")
    print(f"   ۴:  کارت na=True برایِ {len(ui['i4_na_regex_vs_na'])} نماد؛"
          f" regex هم‌راستا: {sum(1 for _, f in ui['i4_na_regex_vs_na'] if f)}"
          f" | واگرا: {len(ui['i4_gap_not_na'])}")
    print(f"   نمونهٔ واگرایِ ۳: {ui['i3_gap_not_na'][:8]}")
    print(f"   نمونهٔ واگرایِ ۴: {ui['i4_gap_not_na'][:8]}")

    only_fe = sorted(set(presets["fe_super"]) - set(presets["be_strong"]))
    only_be = sorted(set(presets["be_strong"]) - set(presets["fe_super"]))
    print(f"\nج) پری‌ست «سوپر بنیادی»: فرانت {len(presets['fe_super'])} | "
          f"verdict STRONG {len(presets['be_strong'])} | فقط‌فرانت {len(only_fe)} | "
          f"فقط‌بک‌اند {len(only_be)}")
    print(f"   فقط‌بک‌اند (کاربردِ فرانت این‌ها را از «سوپر» بیرون می‌اندازد): {only_be[:10]}")
    json.dump({"n": n,
               "card_vs_screener": {k: v for k, v in diff.items()},
               "ui_na_vs_card": {k: [list(x) if isinstance(x, tuple) else x for x in v]
                                 for k, v in ui.items()},
               "counts": {k: len(v) for k, v in ui.items()},
               "super_fe": presets["fe_super"], "super_be": presets["be_strong"]},
              open("_audit/fts_three_way.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nwrote _audit/fts_three_way.json")


if __name__ == "__main__":
    main()
