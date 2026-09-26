#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/portfolio_live_check.py — سنجهٔ زندهٔ «افزودن دارایی» روی سرورِ در حال اجرا.

چرا این اسکریپت هست: گاردِ dev/portfolio_weights_v1035.py همه‌چیز را روی بانکِ
درون‌حافظه‌ای می‌سنجد (CI بانکِ واقعی ندارد)؛ این اسکریپت همان مسیر را روی
اتصالِ واقعیِ uvicorn می‌زند تا معلوم شود schema/زود/پاسخِ HTTP هم راست‌اند.

ایمنی: فقط نمادهایِ خودش را می‌نویسد و در پایانِ همان اجرا پاک می‌کند
(TRY/FINALLY). پیش از نوشتن، تعدادِ ردیف‌هایِ موجود را چاپ می‌کند تا اگر
سبدِ کاربر چیزی داشت، بداند دست نخورده است.

اجرا:  python tools/portfolio_live_check.py [--base http://127.0.0.1:8011]
خروج: ۰ اگر همه بررسی‌ها درست، ۱ در غیر این صورت.
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

TEST_SYMBOLS = ("فولاد", "عيار", "اطلس")


def call(base, path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json",
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8011")
    a = ap.parse_args()
    base, fails = a.base, []

    def ck(what, cond, got=""):
        print(("  ok   " if cond else "  FAIL ") + what + ("" if cond else f"  ← {got}"))
        if not cond:
            fails.append(what)

    print(f"پایه: {base}")
    before = call(base, "/api/selection/portfolio")
    print(f"ردیف‌هایِ موجودِ سبد پیش از آزمون: {len(before.get('decisions') or [])}")

    try:
        # ۱) جستجوی نماد: نام، قیمت و طبقه از سرور
        hits = call(base, "/api/selection/symbols?q=" + urllib.parse.quote("عیار"))["data"]
        ceyar = next((h for h in hits if h["symbol"] == "عيار"), None)
        ck("جستجو «عيار» را با قیمت برمی‌گرداند", bool(ceyar) and (ceyar or {}).get("price"),
           json.dumps(hits[:3], ensure_ascii=False))
        ck("طبقهٔ «عيار» طلا است", (ceyar or {}).get("kind") == "gold",
           json.dumps(ceyar, ensure_ascii=False))
        ck("«آوا» (معيار) دیگر طلا نیست",
           all(h["kind"] != "gold" for h in hits if h["symbol"] == "آوا"),
           json.dumps([h for h in hits if h["symbol"] == "آوا"], ensure_ascii=False))

        # ۲) ثبت دو دارایی با تعداد → وزن باید از ارزش بیاید
        px = (ceyar or {}).get("price") or 660000
        call(base, "/api/selection/decision", "POST",
             {"symbol": "فولاد", "name": "فولاد مبارکه", "status": "accept",
              "price": 4450, "qty": 1000, "weight_pct": 0, "sector": "فلزات اساسي"})
        call(base, "/api/selection/decision", "POST",
             {"symbol": "عيار", "name": "صندوق عیار", "status": "accept",
              "price": px, "qty": 10, "weight_pct": 0, "sector": "صندوق طلا"})
        feed = call(base, "/api/selection/portfolio")
        lim = feed["limits"]
        rows = {d["symbol"]: d for d in feed["portfolio"]}
        gold_val, stock_val = px * 10, 4450 * 1000
        ck("منشأِ وزن «value» است", lim.get("weight_source") == "value", str(lim))
        ck("ارزشِ کل = جمعِ قیمت×تعداد",
           lim.get("portfolio_value_toman") == round(gold_val + stock_val),
           f'{lim.get("portfolio_value_toman")} vs {gold_val + stock_val}')
        ck("وزنِ هر ردیف از ارزشِ همان ردیف است",
           rows.get("عيار", {}).get("weight_eff_pct") ==
           round(gold_val / (gold_val + stock_val) * 100, 1),
           json.dumps({k: v.get("weight_eff_pct") for k, v in rows.items()},
                      ensure_ascii=False))
        ck("ترکیبِ طبقات طلا و سهام را جدا می‌گوید",
           set(lim.get("class_mix_pct") or {}) == {"gold", "stock"},
           str(lim.get("class_mix_pct")))
        ck("هر ردیف طبقهٔ خودش را دارد",
           all(d.get("asset_class") for d in feed["portfolio"]),
           json.dumps([d.get("asset_class") for d in feed["portfolio"]],
                      ensure_ascii=False))

        # ۳) POSTِ جزئی (فقط یادداشت) نباید قیمت/تعداد را پاک کند
        call(base, "/api/selection/decision", "POST",
             {"symbol": "فولاد", "status": "accept", "note": "بروزرسانیِ یادداشت",
              "weight_pct": 0})
        rows2 = {d["symbol"]: d for d in call(base, "/api/selection/portfolio")["portfolio"]}
        ck("یادداشتِ تازه ثبت شد", rows2.get("فولاد", {}).get("note") == "بروزرسانیِ یادداشت",
           str(rows2.get("فولاد", {}).get("note")))
        ck("قیمت پس از POSTِ جزئی پاک نشد", rows2.get("فولاد", {}).get("price") == 4450,
           str(rows2.get("فولاد", {}).get("price")))
        ck("تعداد پس از POSTِ جزئی پاک نشد", rows2.get("فولاد", {}).get("qty") == 1000,
           str(rows2.get("فولاد", {}).get("qty")))

        # ۴) یک ردیفِ بی‌تعداد ⇒ کل سبد از «ارزش» می‌افتد (نه وزنِ ساختگی)
        call(base, "/api/selection/decision", "POST",
             {"symbol": "اطلس", "name": "صندوق اطلس", "status": "accept",
              "price": 0, "qty": 0, "weight_pct": 0})
        lim3 = call(base, "/api/selection/portfolio")["limits"]
        ck("با ردیفِ بی‌تعداد، وزنِ ارزشی اعلام نمی‌شود",
           lim3.get("weight_source") != "value", str(lim3.get("weight_source")))
        ck("ارزشِ کل null می‌شود (نه جمعِ ناقص)",
           lim3.get("portfolio_value_toman") is None, str(lim3.get("portfolio_value_toman")))
        ck("تعدادِ ردیف‌های بی‌ارزش گزارش می‌شود",
           lim3.get("value_missing_count") == 1, str(lim3.get("value_missing_count")))
    finally:
        for s in TEST_SYMBOLS:
            try:
                call(base, f"/api/selection/decision/{urllib.parse.quote(s)}", "DELETE")
            except urllib.error.HTTPError as e:      # نمادی که هرگز ساخته نشد
                print(f"  ..   پاک‌کردن {s}: {e.code}")
        left = call(base, "/api/selection/portfolio").get("decisions") or []
        print(f"ردیف‌هایِ باقی‌مانده پس از پاک‌سازی: {len(left)} "
              f"({[d['symbol'] for d in left]})")

    print(f"\n{0 if not fails else len(fails)} شکست")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
