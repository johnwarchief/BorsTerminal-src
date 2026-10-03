# -*- coding: utf-8 -*-
"""_audit/fts_fe_vs_backend.py — جدولِ واگراییِ UI بنیادی از منطقِ کاننیکالِ بک‌اند

سؤالِ مالک: «آیا جدول/کارت Fundamental در فرانت با منطق نهایی FTS همگام است؟»
پاسخ با حدس داده نمی‌شود؛ این اسکریپت یکِ پاسخِ زندۀ `/api/screener` را می‌گیرد و
همان منطقی را که `FtsScreenTable.tsx` رویِ ردیف‌ها اجرا می‌کند از رویِ *متنِ خودِ
فایل‌هایِ فرانت* بازسازی می‌کند (regexهایِ `assetScope.ts` عیناً همین‌جا کپی شده‌اند
و با گاردِ فرانت هم سنجیده می‌شوند) و تفاوت را ردیف‌به‌ردیف می‌شمارد:

  ۱) پری‌ست «سوپر بنیادی»: فرانت `score>=4 && pricing_mode==='free'` می‌شمارد،
     بک‌اند `verdict==='STRONG'` (= `score>=4 && primary_score===3`).
  ۲) پری‌ست «ساعت شنی»: فرانت `score===5`؛ بک‌اند پرچمِ `tech_hourglass_active`.
  ۳) «ب» رشد فیزیکی: فرانت با regexِ نام/صنعت «N/A» می‌گذارد و **حکمِ بک‌اند را
     می‌پوشاند** (`i1b_pass` برایِ همهٔ ردیف‌ها غیرnull است).
  ۴) reason برچسبِ «N/A (ماهیت مالی)」 درِ شاخص ۳/۴: آیا با null بودنِ همان پرچم
     می‌خواند یا نه.
  ۵) حالتِ چهارم EPS: `epsHistory` فرانت از `eps_years_available/required` — چند
     ردیف با حکمِ بک‌اند (`i2_pass`) در تعارض است.
  ۶) `i1a_pass ?? i1_pass`: اگر روزی i1a غایب باشد حکمِ «الف» از مجموع می‌آید.

فقط GET. بانک را نمی‌خواند تا منبعِ مقایسه یک چیز باشد.
"""
import json
import re
import sys
import urllib.request

APP = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"

# عینِ assetScope.ts (BROKER_RE / FUND_RE / FINANCIAL_HOLDING_RE)
BROKER_RE = re.compile(r"کارگزاری|كارگزاری")
FUND_RE = re.compile(r"صندوق|قابل معامله|اهرمی|اهرمى|شاخصی|شاخصى|کالایی|کامودیتی|کاموديتي|درآمد ثابت|ارز دیجیتال")
FIN_RE = re.compile(r"هلدينگ|هلدینگ|سرمايه گذاري|سرمایه گذاري|سرمایه‌گذاری|سرمایه گذاری|واسطه گري|واسطهگری|بانك|بانک|بيمه|بیمه|ليزينگ|لیزینگ|صندوق|تامين سرمايه|تأمین سرمایه")


def norm(s):
    s = (s or "").replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"[\u200c\u064b-\u0652]", "", s)


def is_financial(name, sector):
    return bool(FIN_RE.search(norm(name)) or FIN_RE.search(norm(sector)))


def main():
    rows = json.load(urllib.request.urlopen(APP + "/api/screener?limit=20000",
                                            timeout=300))["data"]
    n = len(rows)
    print(f"ردیف‌هایِ `/api/screener`: {n}")

    fe_super = [r for r in rows if (r.get("score") or 0) >= 4 and r.get("pricing_mode") == "free"]
    be_strong = [r for r in rows if r.get("verdict") == "STRONG"]
    only_fe = sorted({r["symbol"] for r in fe_super} - {r["symbol"] for r in be_strong})
    only_be = sorted({r["symbol"] for r in be_strong} - {r["symbol"] for r in fe_super})
    print(f"\n۱) سوپر بنیادی: فرانت {len(fe_super)} | بک‌اند STRONG {len(be_strong)} | "
          f"فقط‌فرانت {len(only_fe)} | فقط‌بک‌اند {len(only_be)}")
    print(f"   نمونهٔ فقط‌فرانت: {only_fe[:8]}")
    print(f"   نمونهٔ فقط‌بک‌اند: {only_be[:8]}")

    hg_fe = [r for r in rows if r.get("score") == 5]
    hg_be = [r for r in rows if r.get("tech_hourglass_active") is True]
    key_seen = sum(1 for r in rows if "tech_hourglass_active" in r)
    print(f"\n۲) ساعت شنی: فرانت score==5 → {len(hg_fe)} | پرچمِ بک‌اند → {len(hg_be)} "
          f"| ردیف‌هایِ دارایِ کلیدِ tech_hourglass_active: {key_seen}/{n}")

    hidden_i1b = [r for r in rows if is_financial(r.get("name"), r.get("sector_name"))
                  and r.get("i1b_pass") is not None]
    print(f"\n۳) «ب» رشد فیزیکی: ردیف‌هایی که فرانت با regexِ نام/صنعت N/A می‌گذارد و "
          f"حکمِ واقعیِ بک‌اند پوشیده می‌شود: {len(hidden_i1b)}")
    for r in hidden_i1b[:6]:
        print(f"   • {r['symbol']:10s} i1b_pass={r['i1b_pass']} "
              f"rev_growth={r.get('rev_growth')} sector={r.get('sector_name')}")
    null_i1b = [r for r in rows if r.get("i1b_pass") is None]
    print(f"   (ردیف‌هایی که بک‌اند واقعاً حکمی ندارد: {len(null_i1b)})")

    na3 = [r for r in rows if r.get("i3_pass") is None]
    na3_reg = [r for r in na3 if is_financial(r.get("name"), r.get("sector_name"))]
    na4 = [r for r in rows if r.get("i4_pass") is None]
    na4_reg = [r for r in na4 if is_financial(r.get("name"), r.get("sector_name"))]
    print(f"\n۴) برچسبِ «N/A (ماهیت مالی)» شاخص ۳: null={len(na3)} که از آن regex "
          f"{len(na3_reg)} را مالی می‌خواند و {len(na3) - len(na3_reg)} «شکاف داده» "
          f"می‌گیرد؛ شاخص ۴: null={len(na4)} / regex={len(na4_reg)}")
    reg_no_null = [r for r in rows if r.get("i3_pass") is not None
                   and is_financial(r.get("name"), r.get("sector_name"))]
    print(f"   ردیف‌هایِ مالی که بک‌اند برایشان حکمِ شاخص ۳ داده است "
          f"(پس برچسبِ N/A جایِ حکم را نمی‌گیرد — این شاخه درِ کد فعال نیست): {len(reg_no_null)}")

    req = [(r.get("eps_years_required") or 3) for r in rows]
    part = [r for r in rows if 2 <= (r.get("eps_years_available") or 0) < (r.get("eps_years_required") or 3)]
    part_pass = [r for r in part if r.get("i2_pass") is True]
    print(f"\n۵) EPS سابقهٔ ناقص (۲ از ۳): {len(part)} ردیف؛ که بک‌اند i2_pass=True "
          f"گفته: {len(part_pass)} | years_requiredِ ارسالی: {sorted(set(req))}")
    insuff = [r for r in rows if (r.get("eps_years_available") or 0) < 2]
    print(f"   سابقهٔ کمتر از ۲ سال: {len(insuff)}؛ eps_data_gap=True در همان‌ها: "
          f"{sum(1 for r in insuff if r.get('eps_data_gap'))}")

    fall = [r for r in rows if r.get("i1a_pass") is None and r.get("i1_pass") is not None]
    print(f"\n۶) `i1a_pass ?? i1_pass`: ردیف‌هایی که امروز از این برگشت استفاده "
          f"می‌کنند: {len(fall)} (برگشتِ خاموش = منطقی که با دادهٔ امروز سنجیده نمی‌شود)")

    app_false = [r for r in rows if r.get("applicable") is False]
    still_kept = [r for r in app_false
                  if not (FUND_RE.search(norm(r.get("name")))
                          or FUND_RE.search(norm(r.get("sector_name")))
                          or BROKER_RE.search(norm(r.get("name"))))]
    print(f"\n۷) قلمرو جدول: بک‌اند `applicable=False` برایِ {len(app_false)} ردیف "
          f"(داوری «FTS ندارد»). از آن‌ها {len(still_kept)} را regexهایِ نام/صنعتِ "
          f"فرانت «شرکت» می‌شناسند و در جدول می‌گذارند:")
    print(f"   نمونه: {[(r['symbol'], r.get('verdict'), r.get('sector_name')) for r in still_kept[:6]]}")
    print("   (تصمیمِ کاملِ `isFundamentalCompany` به `classifyAssetType` هم وابسته است؛"
          " آن درِ گاردِ فرانت با همان TS سنجیده می‌شود.)")
    json.dump({"rows": n,
               "super_fe": len(fe_super), "super_be": len(be_strong),
               "super_only_fe": only_fe, "super_only_be": only_be,
               "hourglass_fe": len(hg_fe), "hourglass_be": len(hg_be),
               "hidden_i1b": [r["symbol"] for r in hidden_i1b],
               "na3": len(na3), "na3_regex": len(na3_reg),
               "na4": len(na4), "na4_regex": len(na4_reg),
               "eps_partial": len(part), "eps_partial_backend_true": len(part_pass),
               "i1a_fallback_rows": len(fall),
               "applicable_false": len(app_false),
               "applicable_false_kept_by_fe_regex": [r["symbol"] for r in still_kept]},
              open("_audit/fts_fe_vs_backend.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nwrote _audit/fts_fe_vs_backend.json")


if __name__ == "__main__":
    main()
