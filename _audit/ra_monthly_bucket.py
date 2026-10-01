# -*- coding: utf-8 -*-
"""قدمِ ۱(b) قراردادِ parity — سنجشِ bucketِ کندلِ ماهانۀ رهاورد (جلالی یا میلادی).

کدِ timeframe از markupِ خودِ صفحهٔ چارتشان خوانده شد (`_audit/ra_chartpage.html`):
    data-time="0" روزانه/D · data-time="1" هفتگی/W · data-time="2" ماهانه/M
و باندلِ `technicalChart.1.1.2.min.js` همین مقدار را در '/prices?timeframe=' می‌گذارد
(رشته‌هایِ decodeشدۀ string table: `_audit/ra_ta_strings.txt`، سطرهایِ 441 و 1563).

سنجش بدونِ هیچ تبدیلِ تقویمیِ دستِ من: هر ردیفِ candles ستونِ هفتمش تاریخِ جلالیِ
نشستِ شروع است (YYYYMMDD جلالیِ خودِ آن‌ها). پس دو «شمارندۀ ماه» مستقل ساخته می‌شود:
  - شاخصِ میلادیِ stamp (UTC و +۳:۳۰)
  - شاخصِ جلالیِ ستونِ jalaliِ خودِ API
اگر bucket میلادی باشد، اختلافِ شاخصِ میلادیِ دو کندلِ پشتِ هم **همیشه ۱** است و جلالی
در {۱،۲} می‌چرخد؛ اگر جلالی باشد، دقیقاً برعکس. روزِ شروعِ هر دو تقویم هم گزارش می‌شود.
"""
import datetime as dt
import json
import os
import urllib.request


UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://tradersarena.ir/"}
SYMS = [("فولاد", "46348559193224090"), ("پارس", "6110133418282108"),
        ("خگستر", "48990026850202503"), ("شبندر", "35366681030756042"),
        ("خودرو", "65883838195688438")]
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ra_probe_cache")
TF_MONTHLY = 2  # از markupِ خودشان، ببینید سرِ فایل


def get_json(url, timeout=90):
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, "".join(c for c in url if c.isalnum()) + ".json")
    if os.path.isfile(key):
        return json.load(open(key, encoding="utf-8"))
    req = urllib.request.Request(url, headers=UA)
    data = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    j = json.loads(data)
    json.dump(j, open(key, "w", encoding="utf-8"))
    return j


def rows(ins, tf):
    return get_json(f"https://tradersarena.ir/data/{ins}/prices?timeframe={tf}").get("candles") or []


def jparts(v):
    s = str(int(v)).zfill(8)
    return int(s[:4]) * 12 + int(s[4:6]), int(s[6:])  # (شاخصِ ماهِ جلالی، روز)


def gparts(epoch, off_sec=0):
    d = dt.datetime.fromtimestamp(epoch + off_sec, dt.timezone.utc)
    return d.year * 12 + d.month, d.day, d


def hist(dct, key, n=1):
    dct[key] = dct.get(key, 0) + n


def main():
    report = {"timeframe_code_evidence": "ra_chartpage.html data-time 0=D 1=W 2=M",
              "tf_monthly": TF_MONTHLY, "symbols": {}}
    tot = 0
    jd_day, gd_utc_day, gd_teh_day = {}, {}, {}
    jd_step, g_step_utc, g_step_teh = {}, {}, {}
    span_days = {}
    for name, ins in SYMS:
        r = [x for x in rows(ins, TF_MONTHLY) if len(x) >= 7]
        report["symbols"][name] = len(r)
        tot += len(r)
        prev_j = prev_g = prev_ep = None
        for x in r:
            ep, jal = int(x[0]), x[6]
            ji, jday = jparts(jal)
            gi, gday, gd_obj = gparts(ep)
            gti, gtday, _ = gparts(ep, 3 * 3600 + 1800)
            hist(jd_day, jday); hist(gd_utc_day, gday); hist(gd_teh_day, gtday)
            if prev_j is not None:
                hist(jd_step, ji - prev_j)
                hist(g_step_utc, gi - prev_g)
                hist(g_step_teh, gti - prev_gti)
            prev_j, prev_g, prev_gti = ji, gi, gti
        # بازهٔ زمانیِ هر کندل (stampِ این ردیف تا ردیفِ بعد)
        eps = [int(x[0]) for x in r]
        for a, b in zip(eps, eps[1:]):
            hist(span_days, round((b - a) / 86400))
    print(f"کندلِ ماهانه جمع: {tot} | تفکیک: {report['symbols']}\n")

    def show(title, d, keys=None):
        print(title)
        items = sorted(d.items(), key=lambda kv: -kv[1]) if keys is None else [(k, d.get(k, 0)) for k in keys]
        for k, v in items[:12]:
            print(f"   {k!s:>6}: {v}")

    show("الف) روزِ شروعِ کندل — تقویمِ جلالی (ستونِ jalali خودِ API):", jd_day)
    show("\nب) روزِ شروعِ کندل — تقویمِ میلادی (stamp، UTC):", gd_utc_day)
    show("\nپ) روزِ شروعِ کندل — تقویمِ میلادی (stamp، +۳:۳۰):", gd_teh_day)
    show("\nت) گامِ شاخصِ ماهِ جلالی بینِ دو کندلِ پشتِ هم:", jd_step)
    show("\nث) گامِ شاخصِ ماهِ میلادی (UTC) بینِ دو کندلِ پشتِ هم:", g_step_utc)
    show("\nج) فاصلۀ stamp دو کندلِ پشتِ هم (روز):", span_days)
    report["totals"] = {"candles": tot,
                        "jalali_start_day_hist": jd_day,
                        "greg_start_day_utc_hist": gd_utc_day,
                        "greg_start_day_tehran_hist": gd_teh_day,
                        "jalali_month_step_hist": jd_step,
                        "greg_month_step_utc_hist": g_step_utc,
                        "greg_month_step_tehran_hist": g_step_teh,
                        "stamp_gap_days_hist": span_days}
    n_j1 = sum(v for k, v in jd_step.items() if k == 1)
    n_g0 = sum(v for k, v in g_step_utc.items() if k <= 0)
    report["verdict"] = {
        "jalali_step_1": n_j1, "jalali_step_total": sum(jd_step.values()),
        "greg_step_le_0_pairs": n_g0,
        "reading": ("گامِ ماهِ جلالی همیشه ۱، و درِ میلادی "
                    f"{n_g0} جفتِ کندل درِ یکِ ماهِ میلادی شروع شده‌اند ⇒ bucket جلالی است"
                    if n_g0 else "گامِ جلالی همیشه ۱ و گامِ میلادی همیشه ۱ (مخدوش) — نیاز به نمادِ بیشتر"),
    }
    print("\nخلاصه:", json.dumps(report["verdict"], ensure_ascii=False))
    return report


if __name__ == "__main__":
    rep = main()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ra_monthly_bucket.json")
    json.dump(rep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nنوشته شد:", out)
