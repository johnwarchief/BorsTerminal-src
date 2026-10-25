# -*- coding: utf-8 -*-
"""adjustment_engine.py — موتورِ canonicalِ تعدیلِ عملکردی (ریاضیِ خالص، نوع‌محور، بی‌جعل).

قرارداد (اثبات‌شده درِ `_audit/ra365_phase4_derive_formula.py`):
    سریِ «عملکردی» = تعدیلِ معکوسِ ضریبی (multiplicative back-adjustment) است؛ لنگر = آخرینِ کندل
    (فاکتورِ آخر = ۱)، و قیمت‌هایِ تاریخی در `factor(t) = ∏ ratio` برایِ رویدادهای `date > t`
    مقیاس می‌شوند (به پایین، چون رویداد قیمت را خُرد کرده). این همان جهتِ `api/chart.py` است؛
    این فایل تنها «منبعِ ریاضیِ ضریبِ هر رویداد» را از «کشفِ رویداد از CSV» جدا می‌کند.

فرمول‌هایِ اثبات‌شده بر پایۀِ نوعِ رویداد (هر رویداد یک `ratio ≤ 1` برایِ زنجیرۀِ پس‌رو):
    • cash_dividend (سودِ نقدی):        ratio = P / (P + D)        P = پایانیِ روزِ رویداد (بازسرمایه‌گذاریِ سود)
      صندوق‌ها (توزیع بر مبنایِ ارزشِ اسمی): ratio = par / (par + D)، par = ۱۰٬۰۰۰ ریال
    • capital_increase_reserve (از اندوخته/سودِ انباشته، آورده=۰):
                                         ratio = previous_capital / new_capital
    • capital_increase_contribution (آورده/حق‌تقدم):
                                         N_old=PC، N_new=NC−PC،
                                         ratio = (N_old + N_new·(S/P)) / (N_old + N_new)
                                         S = قیمتِ پذیره‌نویسیِ هر سهمِ جدید؛ P = مرجعِ پیش از رویداد
    • stock_split (تجزیه/تغییرِ تعداد):  ratio = old_shares / new_shares
    • stock_merge  (تجمیع):              ratio = old_shares / new_shares (>۱ → درِ همین قرارداد)

قواعدِ سخت (طبقِ مأموریت):
    • هیچ ورودیِ لازمِ مفقود را با حدس پر نمی‌کند؛ به‌جاش `status="incomplete:<فیلد>"` می‌دهد و
      `ratio=None` می‌ماند — تا هیچ‌وقت «خنثیِ جعلی» جای ضریبِ درست را نگیرد.
    • ورودیِ نامعتبر (P≤D، سهمِ منفی، صفر) → `status="invalid:<علت>"`، `ratio=None`.
    • «فرمولِ شناخته‌شده ولی دادهٔ ناقص» از «فرمولِ ناشناخته» جداست: نوعِ ناشناخته →
      `status="unknown_type"`. هیچ رویدادی خاموش با ratio=۱ رد نمی‌شود؛ caller باید وضعیتِ incomplete/
      unknown را درِ زنجیره اعلام کند (بی‌دوبار‌تعدیل، بی‌سکوت).
این موتور بهِ `market.db` و شبکه وابسته نیست؛ ورودی‌اش رویدادهایِ ساخت‌یافته است (از ingestِ Type6).
"""
from __future__ import annotations

KIND_CASH_DIVIDEND = "cash_dividend"
KIND_CAPITAL_RESERVE = "capital_increase_reserve"
KIND_CAPITAL_CONTRIBUTION = "capital_increase_contribution"
KIND_SPLIT = "stock_split"
KIND_MERGE = "stock_merge"
# رویدادی که نسبتِ تعدیلِ آن را **خودِ مبدأ رسمی** (TSETMC p_closing/p_closing_not_adjusted
# یا shares_old/shares_new) منتشر کرده: قوی‌ترینِ منشأ، بی‌محاسبۀِ مجدد و بی‌proxy.
KIND_SOURCE_RATIO = "source_ratio"
KNOWN_KINDS = (KIND_CASH_DIVIDEND, KIND_CAPITAL_RESERVE, KIND_CAPITAL_CONTRIBUTION,
               KIND_SPLIT, KIND_MERGE, KIND_SOURCE_RATIO)

# کرانِ معقولِ نسبتِ یکِ اقدامِ شرکتی؛ بیرونِ آن یعنی دادهٔ خراب (مثلِ artifactِ ۱e۸ درِ
# share_change صندوق‌ها) یا صفر → هرگز به‌عنوانِ ضریبِ صحیح رد نمی‌شود.
_RATIO_MIN, _RATIO_MAX = 1e-4, 1e4

OK = "ok"


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def event_factor(ev):
    """(ratio, status) — ضریبِ یکِ رویدادِ نوع‌دار. ratio درِ زنجیرۀِ پس‌رو ضرب می‌شود (≤۱ برایِ تعدیلِ کاهنده).

    `ev` دیکشنریِ حداقلِ {'kind','date', ...ورودی‌هایِ نوع...}. هیچ مقدارِ مفقود را نمی‌سازد.
    """
    kind = ev.get("kind")
    if kind not in KNOWN_KINDS:
        return None, "unknown_type"

    if kind == KIND_CASH_DIVIDEND:
        P, D = _num(ev.get("reference_price")), _num(ev.get("dividend_per_share"))
        par = _num(ev.get("par_value"))
        if P is None:
            return None, "incomplete:reference_price"
        if D is None:
            return None, "incomplete:dividend_per_share"
        if P <= 0:
            return None, "invalid:reference_price<=0"
        if D < 0:
            return None, "invalid:dividend_negative"
        if D >= P:
            return None, "invalid:dividend>=reference_price"
        if D == 0:
            return 1.0, OK            # سودِ صفرِ معتبر = بی‌اثر (نه جعل)
        # Rahavard's performance series reinvests the cash dividend at the
        # event price: close_ex / (close_ex + dps).  The exchange's price
        # adjustment ((P-D)/P) is a different series and does not match type7.
        # Fund distributions are quoted as a percentage of the nominal value,
        # so their reference price is par (10,000 rial) rather than the close.
        if par is not None:
            if par <= 0:
                return None, "invalid:par_value<=0"
            return par / (par + D), OK
        return P / (P + D), OK

    if kind == KIND_CAPITAL_RESERVE:
        pc, nc = _num(ev.get("previous_capital")), _num(ev.get("new_capital"))
        if pc is None or nc is None:
            return None, "incomplete:capital"
        if pc <= 0 or nc <= 0:
            return None, "invalid:capital_nonpositive"
        return pc / nc, OK             # افزایشِ رایگانِ سهام → خُردشدنِ قیمتِ تاریخی

    if kind == KIND_CAPITAL_CONTRIBUTION:
        pc, nc = _num(ev.get("previous_capital")), _num(ev.get("new_capital"))
        P = _num(ev.get("reference_price"))
        S = _num(ev.get("offer_price"))
        if pc is None or nc is None:
            return None, "incomplete:capital"
        if P is None:
            return None, "incomplete:reference_price"
        if S is None:
            # بدونِ قیمتِ پذیره، حق‌تقدم قابلِ محاسبه نیست — حدس نمی‌زنیم.
            return None, "incomplete:offer_price"
        if pc <= 0 or P <= 0:
            return None, "invalid:capital/reference_price_nonpositive"
        n_old, n_new = pc, nc - pc
        if n_new < 0:
            return None, "invalid:new_capital_below_previous"
        if n_new == 0:
            return 1.0, OK
        return (n_old + n_new * (S / P)) / (n_old + n_new), OK

    if kind in (KIND_SPLIT, KIND_MERGE):
        old, new = _num(ev.get("old_shares")), _num(ev.get("new_shares"))
        if old is None or new is None:
            return None, "incomplete:shares"
        if old <= 0 or new <= 0:
            return None, "invalid:shares_nonpositive"
        return old / new, OK

    if kind == KIND_SOURCE_RATIO:
        r = _num(ev.get("ratio"))
        if r is None:
            return None, "incomplete:ratio"
        if r <= 0:
            return None, "invalid:ratio_nonpositive"
        if r < _RATIO_MIN or r > _RATIO_MAX:
            return None, "invalid:ratio_out_of_range"
        return r, OK            # نسبتِ منتشرشدهٔ مبدأ = خودش مرجعِ رسمی، بی‌بازمحاسبه

    return None, "unknown_type"         # هرگز بی‌سکوت با ratio=۱


def chain_factors(dates, events):
    """(factors, provenance) — زنجیرۀِ deterministicِ `factor(t)=∏ ratio` برایِ رویدادهایِ date>t.

    `dates` فهرستِ 'YYYY-MM-DD' در **هر** ترتیبی (CSV نزولیِ TSETMC هم مجاز)؛ `factors` دقیقاً
    هم‌ردیفِ همان `dates` برمی‌گردد (factors[i] برایِ dates[i]) — بی‌jابه‌جاییِ پنهانیِ اندیس.
    لنگر = **بزرگ‌ترینِ تاریخ** (نه آخرینِ عنصرِ آرایه) و فاکتورش ۱ است. برگشتِ دوم provenance:
    [{'date','kind','ratio','status'}] برایِ هر رویداد + `incomplete` (رویدادهایِ کامل‌نبوده) +
    `complete` + `anchored_last`. رویدادِ ratio=None (incomplete/unknown/invalid) درِ زنجیره
    اثرِ عددی ندارد ولی درِ provenance علامت می‌خورد تا caller آن را پنهان نکند (بی‌سکوت).
    """
    ds = [str(d)[:10] for d in dates]
    # رویدادهایِ معتبرِ type-aware: (تاریخِ مؤثر, ratio) — ترتیبِ پیمایش برایِ determinism
    valid = []
    prov = []
    for ev in sorted(events or [], key=lambda e: str(e.get("date"))[:10]):
        ratio, status = event_factor(ev)
        de = str(ev.get("date"))[:10]
        prov.append({"date": de, "kind": ev.get("kind"),
                     "ratio": None if ratio is None else round(ratio, 12), "status": status})
        if ratio is not None:
            valid.append((de, ratio))
    factors = [1.0] * len(ds)
    # پیمایشِ معکوسِ دو‌اشاره‌ای O(n+m) — جای حلقۀِ تو‌در‌توی n×m (۵۲۸۸ کندل × رویدادها
    # درِ مسیرِ واقعیِ چارت). خروجی بیتغییر است: `valid` صعودی مرتب است و `order` هم
    # صعودی، پس با پایین‌آمدنِ `t` اشاره‌گرِ رویداد فقط جلو می‌رود و هر `ratio` با
    # `date > t` دقیقاً یک‌بار درِ `f` می‌نشیند. دو کندلِ هم‌تاریخ همان `f` را می‌گیرند
    # (حلقۀِ `while` درِ دیدِ دوم چیزی مصرف نمی‌کند) و بی‌رویداد همه ۱ می‌مانند.
    #
    # Round 32B: no lossy 10-decimal rounding of the cumulative factor.  The
    # previous `round(f, 10)` changed the visible adjusted price of high-priced
    # candles by up to ~5e-7 rial (within tolerance, never exact) and made the
    # exact-parity target unreachable by construction.  The chain is a product
    # of double ratios; keeping the double is the reproducible value.
    order = sorted(range(len(ds)), key=lambda i: ds[i])
    f, j = 1.0, len(valid) - 1
    for i in reversed(order):
        t = ds[i]
        while j >= 0 and valid[j][0] > t:
            f *= valid[j][1]
            j -= 1
        factors[i] = f
    anchor_i = ds.index(max(ds)) if ds else -1
    anchored = (factors[anchor_i] == 1.0) if ds else True
    incomplete = [p for p in prov if p["status"] != OK]
    return factors, {"provenance": prov, "incomplete": incomplete,
                     "complete": len(incomplete) == 0, "anchored_last": anchored}
