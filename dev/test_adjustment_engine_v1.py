# dev/test_adjustment_engine_v1.py — مرحلۀِ ۷: اثباتِ ریاضیِ موتورِ canonicalِ تعدیل (نوع‌به‌نوع)
# خالصِ read-only و بی‌شبکه/دیتابیسِ عملیاتی. سه طبقۀِ شاهد:
#   (الف) مثال‌هایِ دستیِ قابل‌بررسی برایِ **هر** فرمولِ اثبات‌شدہ + مرزها + ورودیِ مفقود/نامعتبر.
#   (ب) رفتارِ زنجیره: ترتیب/هم‌تاریخ/متوالی، idempotent، بدونِ اعمالِ دوباره، لنگر، بی‌جعلِ
#       خنثی برایِ رویدادِ ناقص/ناشناخته (هیچ‌وقت ratio=۱ خاموش).
#   (ج) نمونۀِ واقعیِ مستند: بازسازیِ `وبصادر` (سودِ نقدی × افزایشِ از اندوخته، بی‌آورده) با خودِ
#       موتور و مقایسه با `type7/type0`؛ و `طلا` بی‌رویداد به‌عنوانِ کنترلِ بی‌تغییری.
# شاهدِ مرجع از `_audit/ra365_ref_bars.json` (read-only، آفلاین) خوانده می‌شود؛ هیچ ضریبِ حدسی
# و هیچ fallbackِ خاموش درِ موتور مجاز نیست — این تست همان را قفل می‌کند.
import io
import json
import math
import os
import statistics
import sys
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import adjustment_engine as AE  # noqa: E402

P = F = 0


def check(name, got, want):
    global P, F
    if got == want:
        P += 1
        print(f"  ✓ {name}")
    else:
        F += 1
        print(f"  ✗ {name}: got={got!r} want={want!r}")


def close(name, got, want, tol=1e-9):
    global P, F
    if got is not None and abs(got - want) <= tol:
        P += 1
        print(f"  ✓ {name}")
    else:
        F += 1
        print(f"  ✗ {name}: got={got!r} want={want!r} (tol={tol})")


CD = AE.KIND_CASH_DIVIDEND
CR = AE.KIND_CAPITAL_RESERVE
CC = AE.KIND_CAPITAL_CONTRIBUTION
SP = AE.KIND_SPLIT
MG = AE.KIND_MERGE

# ── (الف) فرمول‌هایِ دستیِ قابل‌بررسی ────────────────────────────────────────────
close("الف۱ سودِ نقدی: (P−D)/P = (1000−200)/1000 = 0.8", AE.event_factor({"kind": CD, "reference_price": 1000, "dividend_per_share": 200})[0], 0.8)
check("الف۱-ب وضعیتِ ok", AE.event_factor({"kind": CD, "reference_price": 1000, "dividend_per_share": 200})[1], AE.OK)
close("الف۲ سودِ صفرِ معتبر = ۱ (بی‌اثر، نه جعل)", AE.event_factor({"kind": CD, "reference_price": 1000, "dividend_per_share": 0})[0], 1.0)
check("الف۲-ب وضعیتِ ok برایِ صفر", AE.event_factor({"kind": CD, "reference_price": 1000, "dividend_per_share": 0})[1], AE.OK)
r, s = AE.event_factor({"kind": CD, "reference_price": 1000, "dividend_per_share": 1200})
check("الف۳ D≥P → invalid، ratio=None", (r, s), (None, "invalid:dividend>=reference_price"))
r, s = AE.event_factor({"kind": CD, "reference_price": 1000, "dividend_per_share": -5})
check("الف۴ D منفی → invalid", (r, s), (None, "invalid:dividend_negative"))
r, s = AE.event_factor({"kind": CD, "dividend_per_share": 100})
check("الف۵ P مفقود → incomplete:reference_price (بی‌حدس)", (r, s), (None, "incomplete:reference_price"))
r, s = AE.event_factor({"kind": CD, "reference_price": 1000})
check("الف۶ D مفقود → incomplete:dividend_per_share", (r, s), (None, "incomplete:dividend_per_share"))

close("الف۷ افزایشِ از اندوخته: PC/NC = 1e9/2e9 = 0.5", AE.event_factor({"kind": CR, "previous_capital": 1_000_000_000, "new_capital": 2_000_000_000})[0], 0.5)
r, s = AE.event_factor({"kind": CR, "previous_capital": 1000})
check("الف۸ NC مفقود → incomplete:capital", (r, s), (None, "incomplete:capital"))
r, s = AE.event_factor({"kind": CR, "previous_capital": 0, "new_capital": 5})
check("الف۹ PC≤۰ → invalid", (r, s), (None, "invalid:capital_nonpositive"))

# آورده: N_old=PC، N_new=NC−PC، ratio=(N_old+N_new·(S/P))/(N_old+N_new)
#   PC=1000، NC=1500 → N_new=500؛ P=1000، S=500 → (1000+500·0.5)/1500 = 1250/1500
close("الف۱۰ آورده: (1000+500·(500/1000))/1500 = 0.83333…",
      AE.event_factor({"kind": CC, "previous_capital": 1000, "new_capital": 1500, "reference_price": 1000, "offer_price": 500})[0],
      1250 / 1500)
r, s = AE.event_factor({"kind": CC, "previous_capital": 1000, "new_capital": 1500, "reference_price": 1000})
check("الف۱۱ آورده بی‌قیمتِ پذیره → incomplete:offer_price (هرگز حدس نه)", (r, s), (None, "incomplete:offer_price"))
r, s = AE.event_factor({"kind": CC, "previous_capital": 1000, "new_capital": 1500, "offer_price": 500})
check("الف۱۲ آورده بی‌مرجعِ پیش از رویداد → incomplete:reference_price", (r, s), (None, "incomplete:reference_price"))
close("الف۱۳ آورده با N_new=۰ (NC==PC) → ۱",
      AE.event_factor({"kind": CC, "previous_capital": 1000, "new_capital": 1000, "reference_price": 900, "offer_price": 500})[0], 1.0)
r, s = AE.event_factor({"kind": CC, "previous_capital": 1500, "new_capital": 1000, "reference_price": 900, "offer_price": 500})
check("الف۱۴ NC<PC درِ آورده → invalid", (r, s), (None, "invalid:new_capital_below_previous"))

close("الف۱۵ تجزیه: old/new = 100/200 = 0.5", AE.event_factor({"kind": SP, "old_shares": 100, "new_shares": 200})[0], 0.5)
close("الف۱۶ تجمیع: old/new = 200/100 = 2.0", AE.event_factor({"kind": MG, "old_shares": 200, "new_shares": 100})[0], 2.0)
r, s = AE.event_factor({"kind": SP, "old_shares": 100})
check("الف۱۷ سهمِ مفقود → incomplete:shares", (r, s), (None, "incomplete:shares"))
r, s = AE.event_factor({"kind": "تجزیه؟", "old_shares": 100, "new_shares": 200})
check("الف۱۸ نوعِ ناشناخته → unknown_type، ratio=None (بی‌خنثیِ خاموش)", (r, s), (None, "unknown_type"))

# ── (ب) زنجیره ──────────────────────────────────────────────────────────────────
d3 = ["2024-01-01", "2024-06-01", "2024-12-01"]
# رویدادها **داخلِ** پنجره (قدیمی‌تر از آخرین کندل) — همان واقعیتِ back-adjust: کندلِ تازه پس از
# همهٔ رویدادهاست و لنگرش ۱ می‌ماند. پلکانِ فاکتور: Jan×(0.8×0.5)، Jun×(0.5)، Dec=۱.
ev2 = [{"kind": CD, "date": "2024-04-01", "reference_price": 1000, "dividend_per_share": 200},
       {"kind": CR, "date": "2024-09-01", "previous_capital": 1, "new_capital": 2}]
f, meta = AE.chain_factors(d3, ev2)
close("ب۰ لنگرِ آخرین = ۱ (بی‌تغییرِ مصنوعی)", f[2], 1.0)
close("ب۱ میانه فقط × رویدادِ بعدِ خود (0.5)", f[1], 0.5)
close("ب۲ قدیمی‌ترین ×(۰٫۸×۰٫۵)=۰٫۴", f[0], 0.4)
check("ب۳ زنجیرۀِ کامل (بی‌ناقص)", meta["complete"], True)
check("ب۴ provenance دو رویداد دارد", len(meta["provenance"]), 2)
check("ب۵ anchored_last True", meta["anchored_last"], True)

# idempotent + بی‌اعمالِ دوباره: اجرای مکرر خروجیِ یکسان
f_again, _ = AE.chain_factors(d3, ev2)
check("ب۶ اجرایِ دوباره → خروجی یکسان (idempotent)", f_again, f)

# ترتیبِ ورودی حفظ می‌شود (نزولی مثلِ CSV واقعی)؛ لنگر = بزرگ‌ترینِ تاریخ، نه آخرینِ آرایه
fd = ["2024-12-01", "2024-06-01", "2024-01-01"]
fdown, mdown = AE.chain_factors(fd, ev2)
check("ب۷ فاکتور هم‌ردیفِ datesِ نزولی برمی‌گردد", fdown, [f[2], f[1], f[0]])
check("ب۸ لنگر = بزرگ‌ترینِ تاریخ (نه آخرینِ عنصرِ آرایه)", mdown["anchored_last"], True)

# هم‌تاریخ: رویدادِ دقیقاً رویِ تاریخِ langer نباید فاکتورِ آن روز را تکان دهد
f_same, _ = AE.chain_factors(d3, [{"kind": CD, "date": "2024-12-01", "reference_price": 1000, "dividend_per_share": 200}])
close("ب۹ رویداد رویِ langer → فاکتورِ langer هنوز ۱", f_same[2], 1.0)
close("ب۹-ب رویداد رویِ langer، روزِ قبل ×0.8 شد", f_same[1], 0.8)

# رویدادِ ناقص: نه اثرِ عددی، نه سکوت — درِ incomplete علامت می‌خورد
f_inc, m_inc = AE.chain_factors(d3, [{"kind": CC, "date": "2024-06-02", "previous_capital": 1000, "new_capital": 1500, "reference_price": 1000}])
check("ب۱۰ رویدادِ ناقص فاکتورِ عددی نساخت (همه ۱)", f_inc, [1.0, 1.0, 1.0])
check("ب۱۱ ناقص پنهان نشد (incomplete یک مورد)", len(m_inc["incomplete"]), 1)
check("ب۱۲ complete False به‌دلیلِ ناقص", m_inc["complete"], False)
check("ب۱۳ علتِ ناقص ثبت شد", m_inc["incomplete"][0]["status"], "incomplete:offer_price")

# نوعِ ناشناخته هم خاموش با ۱ رد نمی‌شود
_, m_un = AE.chain_factors(d3, [{"kind": "??", "date": "2024-06-02"}])
check("ب۱۴ ناشناخته درِ incomplete ثبت شد (بی‌ضریبِ ۱ِ خاموش)", m_un["incomplete"][0]["status"], "unknown_type")

# بی‌رویداد → کنترلِ بی‌تغییری
f0, m0 = AE.chain_factors(d3, [])
check("ب۱۵ بی‌رویداد همه ۱", f0, [1.0, 1.0, 1.0])
check("ب۱۵-ب بی‌رویداد complete", m0["complete"], True)

# ── (ج) نمونۀِ واقعیِ مستند (read-only، آفلاین) ──────────────────────────────────
REFP = os.path.join(ROOT, "_audit", "ra365_ref_bars.json")
if os.path.exists(REFP):
    TEHRAN = timezone(timedelta(hours=3, minutes=30))

    def tdate(b):
        s = str(b["utc"]).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TEHRAN).date().isoformat()

    R = json.load(open(REFP, encoding="utf-8"))

    def series(sym, suf):
        e = R["bars"].get(f"{sym}|{suf}|D")
        if not e or e.get("status") != 200:
            return {}
        return {tdate(b): b["c"] for b in e["bars"] if b.get("c")}

    def typed_events(sym, days, x0):
        data = ((R["meta"].get("marks|" + sym) or {}).get("json") or {}).get("data") or []
        ev = []
        for m in data:
            d = (m.get("date_time") or "")[:10]
            mid = str(m.get("id"))
            if "capital-change" in mid:
                cc = m["capital_change"]
                if (cc.get("contribution_percent") or 0):
                    continue  # آورده بی‌S؛ درِ موتور incomplete می‌ماند، اینجا کنارِ نمادِ پاک
                pc, nc = cc.get("previous_capital", 0), cc.get("new_capital", 0)
                if pc and nc and nc > pc:
                    ev.append({"kind": CR, "date": d, "previous_capital": pc, "new_capital": nc})
            elif mid.startswith("dps"):
                D = m["dps"].get("pure_dps") or 0
                prior = [x0[k] for k in days if k < d]
                ref = prior[-1] if prior else None
                if D and ref and ref > D:
                    ev.append({"kind": CD, "date": d, "reference_price": ref, "dividend_per_share": D})
        return ev

    # وبصادر: سودِ نقدی × افزایشِ از اندوخته، بی‌آورده → کاندیدِ پاکِ بازتولیدِ type7
    sym = "وبصادر"
    x0, x7 = series(sym, "type0"), series(sym, "type7")
    days = sorted(set(x0) & set(x7))
    if len(days) >= 5:
        ev = typed_events(sym, days, x0)
        fac, meta = AE.chain_factors(days, ev)
        errs = []
        for i, d in enumerate(days):
            rref = x7[d] / x0[d] if x0[d] else 0
            if rref:
                errs.append(abs(fac[i] / rref - 1))
        med = statistics.median(errs)
        # جهتِ درست: langer=۱، قدیمی‌ها ≤۱
        check(f"ج۱ [{sym}] موتور complete (بدونِ ناقص/ناشناخته)", meta["complete"], True)
        close(f"ج۲ [{sym}] فاکتورِ langer=۱", fac[days.index(max(days))], 1.0)
        check(f"ج۳ [{sym}] همه فاکتورها ≤۱ (تعدیلِ کاهنده)", all(x <= 1.0 + 1e-9 for x in fac), True)
        check(f"ج۴ [{sym}] میانۀِ خطا < ۰٫۱٪ در برابرِ type7/type0 (واقعی، بدونِ تنظیم)", med < 0.001, True)
        print(f"     ↳ [{sym}] نقاط={len(errs)} میانۀِ خطا={med*100:.4f}٪ رویدادها={len(ev)}")

    # طلا: بی‌رویداد → سریِ عملکردی == خام (کنترلِ بی‌تغییریِ مصنوعی)
    ta0, ta7 = series("طلا", "type0"), series("طلا", "type7")
    tad = sorted(set(ta0) & set(ta7))
    if tad:
        tfac, tmeta = AE.chain_factors(tad, typed_events("طلا", tad, ta0))
        check("ج۵ [طلا] بی‌رویداد، موتور complete", tmeta["complete"], True)
        check("ج۵-ب [طلا] همه فاکتورها ۱ (بدونِ جابه‌جاییِ مصنوعی)", all(math.isclose(x, 1.0) for x in tfac), True)
else:
    check("ج۰ شاهدِ مرجع موجود نیست (نمونۀِ واقعی رد شد — نباید بی‌شمارنده سبز شود)", False, True)

print(f"\nنتیجه: {P} سبز، {F} قرمز")
sys.exit(1 if F else 0)
