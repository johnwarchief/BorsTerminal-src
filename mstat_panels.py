# -*- coding: utf-8 -*-
"""mstat_panels.py — پنل‌هایِ صفحۀ «وضعیت بازار» (مرجع: Binder1.pdf)

چرا فایلِ جدا و نه ادامه‌ی `mstat_engine.py`؟ همان موتورِ enrich و همان یک
اسکنِ تابلو مصرف می‌شود (گاردِ anti-N+1 دست‌نخورده)، ولی این لایه فقط
«نما» می‌سازد: نقشۀ بازار، برترین‌ها، سفارش‌ها، تغییرِ مالکیت، کارت‌هایِ
شاخص و بازارِ طلا. `mstat_engine` از پیش ۲٫۱ هزار سطرِ آزمون‌ پس‌خورده؛
اضافه‌کردنِ شش نمایِ تازه به آن، ریسکِ شکستنِ قراردادهایِ فاز ۵ برایِ
سودِ سازماندهی بود.

سه قاعده‌ای که کل فایل را نگه می‌دارد (صریحِ مأموریت):

۱) هیچ عددی ساخته نمی‌شود. نبودِ داده `None` است و نبودِ *منبع* در
   `no_source` / `blockers` با علتِ خوانا اعلام می‌شود. کارتِ بی‌منبع
   صفر نمی‌گیرد و برچسبِ «زنده» نمی‌گیرد.

۲) هر عدد یکا و مبنایِ خودش را درِ همان پاسخ دارد (`unit`, `basis`,
   `formula`). رابط هیچ تبدیلِ دوم نمی‌کند؛ پس دو درصدِ متفاوتِ یک
   مفهوم در دو گوشۀ صفحه ممکن نیست.

۳) تفکیکِ مفاهیمِ نزدیک: «حجمِ سفارش» ≠ «حجمِ معامله»، «تغییرِ مالکیت»
   ≠ «خالصِ ورودِ پول» ≠ «سرانه»، و «اثر بر شاخص» ≠ «درصدِ رشدِ قیمت».
   هر سه درِ مرجع پنلِ جدا دارد و اینجا هر سه فرمولِ جدا دارد.

مبنایِ «اثر بر شاخص» (سنجشِ همین بانک، ۱۴۰۵-۰۷-۲۳ رویِ نشستِ 20261014):
    اثر_i (واحدِ شاخص) = (پایانی_i − دیروز_i) × سهام_i × شاخص_کل ÷ ارزش_کل_بازار
دامنه = سهامِ عادی، نمایندۀِ هر شرکت یک ردیف (بیشترین گردش؛ بورس و فرابورسِ
یک شرکت دو سطرِ هم‌نام و هم‌سهام‌اند). جمعِ اثرها = −۴۳٬۵۷۷ در برابرِ تغییرِ
رسمیِ −۳۴٬۷۷۱ ⇒ ۲۵٪ پسماند، و پسماند **عمداً اعلام می‌شود** (`reconciliation`).
بدونِ نمایندگیِ یک‌ردیفی همان جمع −۴۴٬۹۰۰ می‌شد (۲۹٪) — یعنی دوباره‌نوشتیِ
۴۲۱ِ شرکتِ دوماّه‌ای هم عدد را بالا می‌برد.
دلیلِ پسماند: TSETMC شاخص را با *سهامِ شناور* وزن می‌دهد و شناور درِ این بانک
نیست (`market_watch.total_shares` = سهامِ کل؛ GetMarketWatch ستونِ شناور ندارد
— جست‌وجو: `grep -rn "floatSh|fsVal|شناور"` فقط یک سطرِ بی‌ربط می‌دهد).

یک فرمولِ دیگر (ارزشِ بازار × درصدِ تغییر) رویِ همین نشست ۰٫۷٪ خطا می‌داد، ولی
آن ۰٫۷٪ برازش نبود: ضریبِ `پایانی÷دیروز` در نمادهایِ افت‌کننده عدد را کوچک
می‌کند و چون اکثرِ نمادهایِ آن روز منفی بودند، جمعِ اثرها به عددِ رسمی نزدیک
شده بود. همان رقمِ تصادفی را به‌عنوانِ «دقت» ثبت نمی‌کنیم — صریحِ مأموریت:
برای بهترشدنِ درصدِ تطابق فاکتور را برازش نکن. پس همین تعریفِ واحدِ شاخص
می‌ماند و پسماندش درِ پاسخ می‌نشیند تا رابط «تقریبی» بودن را بگوید.

نتیجه برایِ رابط: رتبه و یکایِ ریالی (میلیارد تومانِ تغییرِ ارزشِ بازار) از
خودِ داده‌اند و بی‌فرض؛ «واحدِ شاخص» برآورد است و badgeی همراهش می‌آید.
"""
from __future__ import annotations

import datetime

import mstat_engine as E

# یکاهایِ نمایشی — همان ثابت‌هایِ موتور، پس تبدیلِ دومی درِ رابط نساخته می‌شود.
_B_TUMAN = E.B_TUMAN_FROM_RIAL      # ریال → میلیارد تومان
_M_TUMAN = E.M_TUMAN_FROM_RIAL      # ریال → میلیون تومان
_M_SHARE = 1e6                      # سهم → میلیون سهم

# معیارهایِ نقشۀ بازار. «اندوزۀِ مستطیل» باید از خودِ معیار بیاید، نه از
# یکِ عددِ ثابتِ تزئینی؛ انتخابِ معیار ⇒ سطح‌هایِ متفاوت (تستِ مرورگری همین).
TREEMAP_METRICS = {
    "value":   {"label": "ارزش معاملات", "unit": "میلیارد تومان", "field": "value_b_toman"},
    "volume":  {"label": "حجم معاملات", "unit": "میلیون سهم", "field": "volume_m_share"},
    "cap":     {"label": "ارزش بازار", "unit": "میلیارد تومان", "field": "market_cap_b_toman"},
    "trades":  {"label": "تعداد معاملات", "unit": "عدد", "field": "trades"},
}

# دستۀِ تب‌هایِ مرجع (صفحۀ ۲ کرکرۀ «سهام»). همان کلیدهایِ `CATEGORY_ROWS`
# تا نقشۀ بازار با نبض و جدولِ صنایع یک دامنه را بسازند، نه سه دامنه.
TREEMAP_GROUPS = {k: lbl for k, lbl in E.CATEGORY_ROWS}


def _stamp() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _company_key(row) -> tuple:
    """کلیدِ «یک شرکت» برایِ حذفِ دوباره‌نوشتیِ بورس/فرابورس.

    نام + تعدادِ سهام: دو ردیفِ «فارس» و «فارس۳» یک ISIN و یک تعدادِ سهام
    دارند و جمعِ زدنِ ارزشِ بازارِ آن‌ها دو‌برابر می‌کند (سنجشِ خودِ
    `market_total_rials`: جمعِ خامِ ستون ۷۰٬۳۸۶ همت در برابر ۲۴٬۸۵۷ همتِ
    رسمی). کلیدِ خالی بی‌نامِ تهی هرگز دو شرکتِ بی‌نام را یکی نمی‌کند، چون
    `ins_code` درِ انتهای tuple نشسته است.
    """
    nm = (row.get("name") or "").strip()
    if not nm:
        return ("#ins", row.get("ins_code"))
    return (nm, round(E._f(row.get("total_shares")), 2))


def _scope(rows, group: str, industry: str = "") -> list:
    """ردیف‌هایِ enrich درِ دامنه‌یِ کرکره‌ها — بدونِ کوئریِ تازه.

    `group` همان کلیدهایِ `CATEGORY_ROWS` است (کرکرۀِ مرجع «سهام/همه صنایع»
    را به همین دامنه‌ها نگاشت می‌کند)، پس نقشۀ بازار، برترین‌ها و نبض یک
    دامنه می‌سازند نه سه دامنهٔ متفاوت. کلیدِ ناشناخته ⇒ «کل بازار»، نه
    «هیچ»: فهرستِ خالی با سربرگِ سالم بدترین پیامِ ممکن به کاربر است.
    """
    cat = group if group in TREEMAP_GROUPS else "all"
    out = []
    for r in rows:
        if not E.in_category(r, cat, None):
            continue
        if industry and (r.get("sector_name") or "").strip() != industry:
            continue
        out.append(r)
    return out


def _pct_class(pct) -> str:
    """رنگِ معناییِ یکسانِ کلِ صفحه: مثبت / منفی / صفرِ سنجیده / بی‌داده.

    «بی‌داده» سطرِ چهارم است و با صفر یکی نمی‌شود؛ مرجع هم همین چهار حالت را
    دارد و تستِ رگرسیونِ رنگ رویِ همین کلید می‌خواند.
    """
    if pct is None:
        return "nodata"
    if pct > 0:
        return "pos"
    if pct < 0:
        return "neg"
    return "zero"


# ══════════════════════════════════════════════ ۱) نقشۀ بازار (صفحۀ ۲ و ۱۲)
def treemap(conn, group: str = "eq_all", industry: str = "",
             metric: str = "value", limit: int = 220) -> dict:
    """نقشۀ بازار: مستطیل‌هایِ نسبی، رنگ از درصد، سطح از معیارِ انتخابی.

    سه چیز را صریح برمی‌گرداند تا رابط عدد نسازد:
    · `rows[].size` = همان معیارِ انتخابی (مبنایِ سطح)
    · `rows[].pct`  = رنگ
    · `no_source`   = اگر ستونِ معیار درِ این بانک نیست (مثال: ارزشِ بازار در
      پایگاهِ کهنه) ⇒ پنل می‌گوید «منبع نیست»، نه اینکه مربع‌ها صفر شوند.
    """
    metric = metric if metric in TREEMAP_METRICS else "value"
    rows, meta = E.enrich(conn)
    sel = _scope(rows, group, industry)
    mcap_ok = bool(meta.get("market_cap"))
    nodes, skipped_nodata = [], 0
    for r in sel:
        m = r["_m"]
        cap = E._f(r.get("market_cap")) if mcap_ok else None
        size = {
            "value": m["val"] / _B_TUMAN,
            "volume": m["vol"] / _M_SHARE,
            "cap": (cap / _B_TUMAN) if cap else None,
            "trades": m["trades"],
        }[metric]
        if size is None or size <= 0:
            skipped_nodata += 1
            continue
        nodes.append({
            "symbol": r["symbol"], "ins_code": r["ins_code"], "name": r["name"],
            "industry": (r.get("sector_name") or "").strip() or None,
            "cls": r["cls"], "kind": r["kind"],
            "pct": None if r.get("pct") is None else round(r["pct"], 2),
            "tone": _pct_class(r.get("pct")),
            "size": round(size, 3),
            "size_field": TREEMAP_METRICS[metric]["field"],
            "unit": TREEMAP_METRICS[metric]["unit"],
            "p_closing": E._f(r.get("p_closing")),
            "value_b_toman": round(m["val"] / _B_TUMAN, 1),
            "volume_m_share": round(m["vol"] / _M_SHARE, 1),
            "market_cap_b_toman": round(cap / _B_TUMAN, 1) if cap else None,
            "trades": int(m["trades"]),
        })
    nodes.sort(key=lambda n: n["size"], reverse=True)
    total = sum(n["size"] for n in nodes)
    for n in nodes:
        n["share_pct"] = round(100.0 * n["size"] / total, 3) if total else None

    limit = max(1, min(int(limit or 220), 600))
    groups = {}
    for n in nodes[:limit]:
        g = n["industry"] or "بدونِ صنعت"
        b = groups.setdefault(g, {"industry": g, "symbols": 0, "size": 0.0,
                                  "pos": 0, "neg": 0, "nodata": 0})
        b["symbols"] += 1
        b["size"] += n["size"]
        if n["tone"] == "pos":
            b["pos"] += 1
        elif n["tone"] == "neg":
            b["neg"] += 1
        elif n["tone"] == "nodata":
            b["nodata"] += 1
    for b in groups.values():
        b["size"] = round(b["size"], 2)
        b["share_pct"] = round(100.0 * b["size"] / total, 2) if total else None

    no_source = []
    if metric == "cap" and not mcap_ok:
        no_source.append({
            "key": "market_cap", "label": "ارزش بازار",
            "why": "ستونِ market_cap در این بانک پر نشده است — همگام‌سازیِ کامل لازم است",
        })
    return {
        "status": "ok", "asof": meta, "computed_at": _stamp(),
        "group": group, "group_label": TREEMAP_GROUPS.get(group, group),
        "industry": industry or None, "metric": metric,
        "metric_label": TREEMAP_METRICS[metric]["label"],
        "metric_unit": TREEMAP_METRICS[metric]["unit"],
        "basis": "size=%s; color=p_closing_vs_price_yesterday" % metric,
        "formula": {"pct": "(p_closing − price_yesterday) ÷ price_yesterday × 100",
                    "size": "%s از ردیفِ تابلویِ همان نشست" % TREEMAP_METRICS[metric]["label"]},
        "total_nodes": len(nodes), "shown": min(len(nodes), limit),
        "skipped_nodata": skipped_nodata,
        "total_size": round(total, 2),
        "rows": nodes[:limit],
        "groups": sorted(groups.values(), key=lambda b: b["size"], reverse=True),
        "no_source": no_source,
    }


# ════════════════════════════════════════ ۲) برترین‌ها و تأثیرگذاران (صفحۀ ۸)
def _primary_listings(rows):
    """یک ردیفِ نمایندۀ هر شرکت: بیشترین گردشِ ریالی درِ همان نشست.

    دو بازارِ بورس و فرابورسِ یک شرکت را جدا می‌نویسند (۴۲۱ شرکت در نشستِ
    20261014؛ «وبملت» و «وبملت۳» یک نام و یک تعدادِ سهام). جمعِ زدنِ هر دو
    هم ارزشِ بازار و هم اثرِ شاخص را تا دو‌برابرِ واقعی بالا می‌برد. نمایندگی
    باید قطعی باشد: «بیشترین گردش» هم معنادار است (بازارِ اصلیِ همان سهم) و هم
    بی‌ابهام — با تساوی، نامِ نماد برنده است تا دو اجرایِ همان داده دو عدد
    ندهد.
    """
    best = {}
    for r in rows:
        ck = _company_key(r)
        cur = best.get(ck)
        if cur is None or (r["_m"]["val"], r["symbol"]) > (cur["_m"]["val"], cur["symbol"]):
            best[ck] = r
    return list(best.values())


def _impact_points(rows, idx_last, total_rials):
    """اثرِ هر نماد بر شاخصِ کل، در واحدِ شاخص + یکایِ ریالیِ بی‌تخمین.

    دو ستون عمداً کنارِ هم می‌نشینند:
      · `delta_cap_b_toman` = (پایانی − دیروز) × سهام — اندازه‌گیریِ خام، بدونِ
        هیچ فرضِ وزنی. رتبه‌بندی از همین می‌آید و جابه‌جا نمی‌شود.
      · `impact_points`     = همان عدد ÷ مقدارِ مشتقِ شاخص (تقریبی؛ پسماندش درِ
        `reconciliation`). واحدِ «نقطه» قطعی نیست و رابط باید همین را بگوید.
    """
    if not idx_last or not total_rials:
        return None
    out = []
    scale = float(idx_last) / float(total_rials)
    for r in _primary_listings([x for x in rows if x["cls"] == E.PAPER_STOCK]):
        pcl = E._f(r.get("p_closing"))
        ts = E._f(r.get("total_shares"))
        if r.get("pct") is None or not pcl or not ts:
            continue
        m = r["_m"]
        delta_cap_rial = (pcl - E._f(r.get("p_yesterday"))) * ts
        out.append({
            "symbol": r["symbol"], "ins_code": r["ins_code"], "name": r["name"],
            "industry": (r.get("sector_name") or "").strip() or None,
            "delta_cap_b_toman": round(delta_cap_rial / _B_TUMAN, 1),
            "impact_points": delta_cap_rial * scale,
            "p_closing": pcl,
            "p_yesterday": E._f(r.get("p_yesterday")),
            "pct": round(r["pct"], 2),
            "value_b_toman": round(m["val"] / _B_TUMAN, 1),
            "volume_m_share": round(m["vol"] / _M_SHARE, 1),
            "market_cap_b_toman": round(E._f(r.get("market_cap")) / _B_TUMAN, 1)
                                   if r.get("market_cap") else None,
            "tone": _pct_class(r["pct"]),
        })
    return out


def _panel(title, key, rows, value_field, unit, formula, limit=5, note=None):
    """پنلِ رتبه‌بندی‌شده با میله‌ای که طولش از خودِ مقدار می‌آید."""
    top = rows[:limit]
    mx = max((abs(r.get(value_field) or 0.0) for r in top), default=0.0)
    for i, r in enumerate(top, start=1):
        v = r.get(value_field) or 0.0
        r["rank"] = i
        r["bar_pct"] = round(100.0 * abs(v) / mx, 1) if mx else None
    return {"key": key, "title": title, "unit": unit, "formula": formula,
            "value_field": value_field, "candidates": len(rows), "note": note,
            "asof_note": None, "rows": top}


def tops(conn, group: str = "eq_all", limit: int = 5) -> dict:
    """چهار پنلِ صفحۀ ۸: تأثیر مثبت/منفی بر شاخص، بیشترین ارزش، بیشترین حجم.

    دو پنلِ اول «درصدِ رشدِ قیمت» نیستند: ترتیب از اثرِ شاخص می‌آید و درصد
    فقط یک ستونِ کمکی است. دو پنلِ آخر از گردشِ واقعیِ همان نشست‌اند.
    """
    rows, meta = E.enrich(conn)
    mi = E.market_index(conn)
    total_rials, total_src = E.market_total_rials(conn)
    blockers = []

    impact = None
    if mi and mi.get("last") and total_rials:
        impact = _impact_points(_scope(rows, group), mi["last"], total_rials)
    if not impact:
        blockers.append({
            "key": "index_impact", "label": "اثر بر شاخص",
            "why": ("شاخصِ رسمیِ نشست (market_index) یا ارزشِ کلِ بازار (market_totals) "
                    "در این بانک نیست — بدونِ آن هیچ واحدِ شاخصی محاسبه نمی‌شود"),
        })

    panels = []
    if impact:
        ssum = sum(r["impact_points"] for r in impact)
        # رتبه از یکایِ اندازه‌گیری‌شده می‌آید، نه از برآوردِ «واحدِ شاخص»: مقسوم‌علیهِ
        # هر دو یکی است، پس ترتیب عوض نمی‌شود ولی عددِ ریالی وابسته به فرضِ وزنی نیست.
        pos = sorted((r for r in impact if r["delta_cap_b_toman"] > 0),
                     key=lambda r: r["delta_cap_b_toman"], reverse=True)
        neg = sorted((r for r in impact if r["delta_cap_b_toman"] < 0),
                     key=lambda r: r["delta_cap_b_toman"])
        for r in pos + neg:
            r["impact_points"] = round(r["impact_points"], 1)
        _IMP_FORMULA = ("(پایانی − دیروز) × سهامِ شرکت — ستونِ واحدِ شاخص برآورد است "
                        "(بدونِ سهامِ شناور)")
        _IMP_NOTE = ("واحدِ شاخص از تقسیمِ همین عدد بر مقدارِ مشتقِ شاخص می‌آید و "
                     "پسماندش درِ `reconciliation` اعلام شده")
        panels.append(_panel("تأثیر مثبت بر شاخص کل", "impact_pos", pos,
                             "delta_cap_b_toman", "میلیارد تومانِ تغییرِ ارزشِ بازار",
                             _IMP_FORMULA, limit, note=_IMP_NOTE))
        panels.append(_panel("تأثیر منفی بر شاخص کل", "impact_neg", neg,
                             "delta_cap_b_toman", "میلیارد تومانِ تغییرِ ارزشِ بازار",
                             _IMP_FORMULA, limit, note=_IMP_NOTE))
        reconciliation = None
        if mi.get("change"):
            reconciliation = {
                "sum_of_impacts": round(ssum, 1),
                "official_index_change": round(mi["change"], 1),
                "rel_diff_pct": round(100.0 * (ssum - mi["change"]) / abs(mi["change"]), 2),
                "meaning": ("جمعِ اثرها باید با تغییرِ رسمیِ شاخص بخواند؛ فاصله فقط از "
                            "وزنِ سهامِ کل به‌جایِ سهامِ شناور است، نه از دادهٔ غلط"),
            }
        blockers.append({
            "key": "free_float", "label": "سهامِ شناور",
            "why": ("TSETMC شاخص را با سهامِ شناور وزن می‌دهد و شناور در این بانک "
                    "نیست؛ وزنِ اینجا سهامِ کل است ⇒ واحدِ شاخص تقریبی است (تفکیکِ "
                    "شرکتِ دوبهره‌شدنی اعمال شده). تفاوت را در `reconciliation` ببینید"),
            "official_attribution_available": False,
        })
    else:
        reconciliation = None
        for key, title in (("impact_pos", "تأثیر مثبت بر شاخص کل"),
                           ("impact_neg", "تأثیر منفی بر شاخص کل")):
            panels.append({"key": key, "title": title, "unit": "واحدِ شاخص",
                           "formula": None, "value_field": "impact_points",
                           "candidates": 0, "rows": [],
                           "note": "منبعِ محاسبه در دسترس نیست — عددی ساخته نمی‌شود"})

    sel = _scope(rows, group)
    by_val = sorted((r for r in sel if r["_m"]["val"] > 0),
                    key=lambda r: r["_m"]["val"], reverse=True)
    by_vol = sorted((r for r in sel if r["_m"]["vol"] > 0),
                    key=lambda r: r["_m"]["vol"], reverse=True)

    def money_panel(r):
        m = r["_m"]
        return {"symbol": r["symbol"], "ins_code": r["ins_code"], "name": r["name"],
                "industry": (r.get("sector_name") or "").strip() or None,
                "value_b_toman": round(m["val"] / _B_TUMAN, 1),
                "volume_m_share": round(m["vol"] / _M_SHARE, 1),
                "p_closing": E._f(r.get("p_closing")),
                "pct": None if r.get("pct") is None else round(r["pct"], 2),
                "tone": _pct_class(r.get("pct")), "trades": int(m["trades"])}

    panels.append(_panel("بیشترین ارزش معاملات", "most_value",
                         [money_panel(r) for r in by_val], "value_b_toman",
                         "میلیارد تومان", "q_tot_capِ ردیفِ تابلو (ارزشِ معاملاتِ روز)",
                         limit))
    panels.append(_panel("بیشترین حجم معاملات", "most_volume",
                         [money_panel(r) for r in by_vol], "volume_m_share",
                         "میلیون سهم", "q_tot_tranِ ردیفِ تابلو (حجمِ معاملاتِ روز)",
                         limit))

    return {"status": "ok", "asof": meta, "computed_at": _stamp(), "group": group,
            "group_label": TREEMAP_GROUPS.get(group, group), "panels": panels,
            "index": mi, "market_total_source": total_src,
            "reconciliation": reconciliation, "blockers": blockers,
            "traded_only": True}


# ═══════════════════════════ ۳) سفارش‌ها و تغییرِ مالکیت (صفحۀ ۹)
def order_book_flows(conn, group: str = "all", limit: int = 10) -> dict:
    """حجمِ *سفارش* (ماندهٔ دفترِ سفارش) در برابرِ حجمِ *معامله* (انجام‌شده).

    مرجع این دو را در دو پنلِ جدا می‌گیرد و اشتباه‌شان رایج‌ترین خطایِ این‌گونه
    داشبورد است. اینجا:
      · سفارش = buy_q_vol / sell_q_vol (پنجرۀ blDs/bsDsِ خودِ TSETMC)
      · معامله = q_tot_tran (گردشِ انجام‌شدۀ همان نشست)
    عمق در این بانک نباشد `orders_available=false` و پنل می‌گوید «منبعِ سفارش
    نرسیده» — صفرِ سبز/قرمز ساخته نمی‌شود.
    """
    rows, meta = E.enrich(conn)
    sel = _scope(rows, group)
    have = [r for r in sel if r["_m"]["bq_vol"] is not None]
    buy_v = sum(r["_m"]["bq_vol"] or 0.0 for r in have)
    sell_v = sum(r["_m"]["sq_vol"] or 0.0 for r in have)
    traded = sum(r["_m"]["vol"] for r in sel)

    def one(r):
        m = r["_m"]
        b, s = (m["bq_vol"] or 0.0), (m["sq_vol"] or 0.0)
        tv = m["vol"]
        return {"symbol": r["symbol"], "ins_code": r["ins_code"], "name": r["name"],
                "industry": (r.get("sector_name") or "").strip() or None,
                "buy_order_m_share": round(b / _M_SHARE, 3),
                "sell_order_m_share": round(s / _M_SHARE, 3),
                "imbalance_m_share": round((b - s) / _M_SHARE, 3),
                "imbalance_pct_of_traded": round(100.0 * (b - s) / tv, 1) if tv > 0 else None,
                "executed_m_share": round(tv / _M_SHARE, 3),
                "buy_queue_b_toman": round((m["bq_val"] or 0.0) / _B_TUMAN, 1),
                "sell_queue_b_toman": round((m["sq_val"] or 0.0) / _B_TUMAN, 1),
                "p_closing": E._f(r.get("p_closing")),
                "pct": None if r.get("pct") is None else round(r["pct"], 2),
                "tone": _pct_class(r.get("pct")), "queue": m["qstate"]}

    ranked_buy = sorted((one(r) for r in have),
                        key=lambda x: x["buy_order_m_share"], reverse=True)
    ranked_sell = sorted((one(r) for r in have),
                         key=lambda x: x["sell_order_m_share"], reverse=True)
    limit = max(1, min(int(limit or 10), 50))
    return {
        "status": "ok", "asof": meta, "computed_at": _stamp(), "group": group,
        "orders_available": bool(have),
        "symbols_with_orders": len(have), "symbols_in_scope": len(sel),
        "unit": "میلیون سهم",
        "basis": "order=buy_q_vol/sell_q_vol (ماندهٔ دفتر), executed=q_tot_tran (انجام‌شده)",
        "formula": {"buy_order": "Σ buy_q_vol", "sell_order": "Σ sell_q_vol",
                    "imbalance": "buy_q_vol − sell_q_vol (سهم)",
                    "imbalance_pct_of_traded": "(buy−sell) ÷ q_tot_tran × 100"},
        "totals": {
            "buy_order_m_share": round(buy_v / _M_SHARE, 1),
            "sell_order_m_share": round(sell_v / _M_SHARE, 1),
            "net_order_m_share": round((buy_v - sell_v) / _M_SHARE, 1),
            "executed_m_share": round(traded / _M_SHARE, 1),
            "buy_sell_ratio": round(buy_v / sell_v, 2) if sell_v > 0 else None,
            # سفارش هرگز با معامله یکی گرفته نمی‌شود؛ این نسبت فقط خوانشِ کمّی است.
            "order_vs_executed_note": "سفارش = ماندهٔ دفتر؛ معامله = گردشِ انجام‌شده",
        },
        "buy_panels": _panel("بیشترین حجمِ سفارشِ خرید", "order_buy", ranked_buy,
                             "buy_order_m_share", "میلیون سهم", "Σ buy_q_vol به تفکیک نماد",
                             limit),
        "sell_panels": _panel("بیشترین حجمِ سفارشِ فروش", "order_sell", ranked_sell,
                              "sell_order_m_share", "میلیون سهم", "Σ sell_q_vol به تفکیک نماد",
                              limit),
        "no_source": ([] if have else [{
            "key": "order_depth", "label": "حجمِ سفارش",
            "why": ("ستون‌هایِ عمقِ دفترِ سفارش (blDs/bsDs) در این بانک پر نشده‌اند؛ "
                    "پنلِ «سفارش» بدونِ منبع عدد نمی‌سازد"),
        }]),
    }


def ownership_change(conn, group: str = "all", limit: int = 10) -> dict:
    """تغییرِ مالکیت حقیقی ⇄ حقوقی، در *سهم* و در *درصدِ سهامِ شرکت*.

    سه تفکیک که مرجع هم پنلِ جدا دارد و قبلاً درِ این برنامه قاطی می‌شد:
      · تغییرِ مالکیت = خریدِ حقوقی − فروشِ حقوقی (سهم) — عددِ سهمی.
      · خالصِ ورودِ پول = ارزشِ خریدِ حقیقی − ارزشِ فروشِ حقیقی (ریال) — درِ
        `client_split` و `mainwatch`؛ اینجا تکرار نمی‌شود.
      · سرانه = ارزش ÷ تعدادِ سفارشِ همان گروه — درِ `money()`؛ اینجا نمی‌آید.
    مخرجِ «درصدِ سهام» تعدادِ سهامِ شرکت است، نه گردشِ روز؛ بی‌آنshare نسبت
    به نمادهایِ کم‌گردش بزرگ‌نمایی می‌شود.
    """
    rows, meta = E.enrich(conn)
    sel = [r for r in _scope(rows, group) if r["_m"]["has_ct"]]
    lag = bool((meta or {}).get("client_lag_days"))
    out = []
    tot_legal_net = tot_real_net = 0.0
    for r in sel:
        m = r["_m"]
        legal_net = m["nv_buy"] - m["nv_sell"]
        real_net = m["iv_buy"] - m["iv_sell"]
        ts = E._f(r.get("total_shares"))
        out.append({
            "symbol": r["symbol"], "ins_code": r["ins_code"], "name": r["name"],
            "industry": (r.get("sector_name") or "").strip() or None,
            "legal_net_share": legal_net,
            "real_net_share": real_net,
            "legal_net_m_share": round(legal_net / _M_SHARE, 2),
            "real_net_m_share": round(real_net / _M_SHARE, 2),
            "legal_net_pct_of_capital": (round(100.0 * legal_net / ts, 4)
                                         if ts > 0 else None),
            "legal_buy_pct_of_volume": (round(100.0 * m["nv_buy"] / m["vol"], 1)
                                        if m["vol"] > 0 else None),
            "legal_sell_pct_of_volume": (round(100.0 * m["nv_sell"] / m["vol"], 1)
                                         if m["vol"] > 0 else None),
            "executed_m_share": round(m["vol"] / _M_SHARE, 2),
            "p_closing": E._f(r.get("p_closing")),
            "pct": None if r.get("pct") is None else round(r["pct"], 2),
            "tone": _pct_class(r.get("pct")),
            "value_source": m["value_source"],
        })
        tot_legal_net += legal_net
        tot_real_net += real_net
    limit = max(1, min(int(limit or 10), 100))
    into_legal = sorted((r for r in out if r["legal_net_share"] > 0),
                        key=lambda x: (x["legal_net_pct_of_capital"] is None,
                                       -(x["legal_net_pct_of_capital"] or 0.0)))
    into_real = sorted((r for r in out if r["legal_net_share"] < 0),
                       key=lambda x: (x["legal_net_pct_of_capital"] is None,
                                      (x["legal_net_pct_of_capital"] or 0.0)))
    return {
        "status": "ok", "asof": meta, "computed_at": _stamp(), "group": group,
        "symbols_with_client_data": len(sel), "unit": "سهم / درصدِ سهامِ شرکت",
        "basis": "client_type volume (same session unless client_lag_days)",
        "formula": {"legal_net": "buy_n_vol − sell_n_vol",
                    "pct_of_capital": "legal_net ÷ total_shares × 100",
                    "not_to_be_confused": "خالصِ ورودِ پول (ریالی) و سرانه اینجا نیامده‌اند"},
        "client_data_lags_session": lag,
        "totals": {"legal_net_m_share": round(tot_legal_net / _M_SHARE, 1),
                   "real_net_m_share": round(tot_real_net / _M_SHARE, 1)},
        "to_legal_panel": _panel("تغییرِ مالکیت به سمتِ حقوقی", "ownership_to_legal",
                                 into_legal, "legal_net_pct_of_capital",
                                 "درصدِ سهامِ شرکت", "buy_n_vol − sell_n_vol ÷ سهام",
                                 limit),
        "to_real_panel": _panel("تغییرِ مالکیت به سمتِ حقیقی", "ownership_to_real",
                                into_real, "legal_net_pct_of_capital",
                                "درصدِ سهامِ شرکت", "sell_n_vol − buy_n_vol ÷ سهام",
                                limit),
        "no_source": ([] if sel else [{
            "key": "client_type", "label": "تفکیکِ مشتری",
            "why": "ردیفِ client_type برایِ این دامنه نرسیده است",
        }]),
    }


# ════════════════════════════════════ ۴) کارت‌هایِ شاخص + sparkline (صفحۀ ۶ و ۷)
_INDEX_COLS = ("d_even", "idx_last", "idx_change", "idx_pct", "ew_last",
               "ew_change", "ew_pct", "z_tot_tran", "q_tot_cap", "q_tot_tran")


def _index_history(conn, days: int = 30) -> list:
    """تاریخچۀِ شاخصِ رسمی، صعودیِ قدیمی‌به‌تازه، به شکلِ دیکشنری.

    ترتیبِ ستون‌ها یک‌بار درِ `_INDEX_COLS` قفل می‌شود؛ کوئریِ جایگاهی با
    PRAGMAِ خودش مقایسه می‌شود تا افزودنِ ستون به `market_index` این نما را
    بی‌صدا جابه‌جا نکند (همان شکلی که درِ `test_tsetmc.save_market_index`
    نوشتارِ نامی جای نوشتارِ جایگاهی را گرفت).
    """
    days = max(2, min(int(days or 30), 250))
    try:
        have = [r[1] for r in conn.execute("PRAGMA table_info(market_index)")]
    except Exception:
        return []
    if not have:
        return []
    picked = [c for c in _INDEX_COLS if c in have]
    try:
        recs = conn.execute(
            "SELECT %s FROM market_index ORDER BY d_even DESC LIMIT %d"
            % (", ".join(picked), days)).fetchall()
    except Exception:
        return []
    return [dict(zip(picked, r)) for r in reversed(recs)]


def index_cards(conn, days: int = 30) -> dict:
    """سه کارتِ صفحۀ ۶: کل بورس، کل هم‌وزن، قیمتِ وزنیِ ارزشی — با sparkline.

    «قیمتِ وزنیِ ارزشی» از خودِ همان ردیفِ رسمی می‌آید: ارزشِ کل ÷ حجمِ کل
    (q_tot_cap/q_tot_tran) — نه میانگینِ سادهٔ درصدها. نبودِ هر خانه ⇒ آن
    کارت `available:false` می‌گیرد و sparkline نمی‌کشد.
    """
    hist = _index_history(conn, days)          # صعودی: قدیمی‌ترین ← تازه‌ترین
    mi = E.market_index(conn)
    src = "market_index (GetMarketOverviewِ رسمیِ بورس)"
    cards = []

    def spark(key):
        """سریِ sparkline از همان ردیف‌هایِ رسمی — خانه‌هایِ تهی None می‌مانند
        تا رابط نقطه نپزد، نه اینکه خط را به صفر بکشاند."""
        return [r.get(key) for r in hist]

    def card(key, label, value, change, pct, unit, series, note=None):
        return {"key": key, "label": label, "available": value is not None,
                "value": None if value is None else round(value, 2),
                "change": None if change is None else round(change, 2),
                "pct": None if pct is None else round(pct, 2),
                "unit": unit, "tone": _pct_class(pct), "spark": series,
                "formula": note, "asof_d_even": hist[-1]["d_even"] if hist else None}

    # قیمتِ وزنیِ ارزشی: ارزشِ کل ÷ حجمِ کل درِ همان ردیفِ رسمی — میانگینِ
    # سادهٔ درصدها نیست و جایگزینِ شاخصِ کل هم نمی‌نشیند.
    wavg = [None if not r.get("q_tot_tran") else
            r["q_tot_cap"] / r["q_tot_tran"] for r in hist]
    prev = wavg[-2] if len(wavg) > 1 else None
    last = wavg[-1] if wavg else None
    cards.append(card("tedpix", "کل بورس", mi.get("last") if mi else None,
                      mi.get("change") if mi else None, mi.get("pct") if mi else None,
                      "واحدِ شاخص", spark("idx_last"), "indexLastValueِ رسمی"))
    cards.append(card("equal_weight", "کل هم‌وزن", mi.get("ew_last") if mi else None,
                      mi.get("ew_change") if mi else None,
                      mi.get("ew_pct") if mi else None,
                      "واحدِ شاخص", spark("ew_last"),
                      "indexEqualWeightedLastValueِ رسمی"))
    cards.append(card("value_weighted_price", "قیمتِ وزنیِ ارزشی", last,
                      None if (last is None or prev is None) else last - prev,
                      None if (last is None or not prev) else 100.0 * (last - prev) / prev,
                      "ریال", wavg, "q_tot_cap ÷ q_tot_tran"))
    total_rials, total_src = E.market_total_rials(conn)
    return {
        "status": "ok", "computed_at": _stamp(), "cards": cards, "source": src,
        "history_points": len(hist),
        "history_days": [r["d_even"] for r in hist],
        "trades": hist[-1]["z_tot_tran"] if hist else None,
        "market_total_b_toman": round(total_rials / _B_TUMAN, 1) if total_rials else None,
        "market_total_source": total_src,
        "note": ("sparkline فقط روزهایی را دارد که شاخصِ رسمی در این بانک ذخیره شده؛ "
                 "تعدادِ نقاط در `history_points` است و بازه‌ای که نبود ادعا نمی‌شود"),
        "blockers": ([] if hist else [{
            "key": "market_index_history", "label": "تاریخچۀِ شاخص",
            "why": "جدولِ market_index خالی است — شاخصِ رسمی از نخستین سینکِ موفق می‌آید",
        }]),
    }


# ════════════════════════════════════════ ۵) بازارِ طلا (صفحاتِ ۱، ۳، ۱۰، ۱۱، ۱۲)
GOLD_NO_SOURCE = [
    {"key": "gold_ounce", "label": "انسِ طلا (دلار/انس)",
     "why": "TSETMC انسِ جهانی را منتشر نمی‌کند و BorsTerminal منبعِ مجازِ دیگری برایِ آن ندارد",
     "needed": "اندپوینتِ قیمتِ جهانی (مثلاً feedِ انس) با مجوزِ دسترسی"},
    {"key": "tether", "label": "تتر",
     "why": "بازارِ رمزارز در دامنه‌یِ داده‌هایِ بورسیِ این بانک نیست",
     "needed": "منبعِ رمزارز + سیاستِ مجوز"},
    {"key": "usd", "label": "دلارِ آمریکا",
     "why": "نرخِ ارز در market.db نمی‌نشیند", "needed": "منبعِ نرخِ ارزِ مجاز"},
    {"key": "housing", "label": "یک مترِ مربعِ مسکن درِ تهران",
     "why": "داده‌یِ مسکن در این بانک نیست", "needed": "منبعِ بازارِ مسکن"},
    {"key": "inflation", "label": "نرخِ تورمِ نقطه‌به‌نقطه",
     "why": "شاخصِ تورمِ مرکزِ آمار در این بانک نیست", "needed": "منبعِ تورم"},
    {"key": "coin_physical", "label": "سکهٔ امامی / بهار آزادی / گرمی (بازارِ فیزیکی)",
     "why": "نمادهایِ تابلو صندوق‌ها و اوراقِ طلا هستند؛ قیمتِ فیزیکیِ سکه در داده‌هایِ TSETMC نیست",
     "needed": "منبعِ بازارِ فیزیکیِ طلا و سکه"},
    {"key": "forward_price", "label": "قیمتِ آینده و ٪ اختلافِ چهار ماهه",
     "why": ("تعریفِ فرمول درِ مرجع نامعلوم است و حدس‌زدن از رویِ نامِ کارت ممنوع است؛ "
             "ساختار می‌ماند، عدد ساخته نمی‌شود"),
     "needed": "تعریفِ رسمیِ «قیمتِ آینده» + منبعِ منحنی"},
    {"key": "intrinsic_value", "label": "ارزشِ ذاتی",
     "why": "درِ مرجع پشتِ «ورود/عضویت» قفل است — محدودیتِ دسترسی، نه نقصِ فنی",
     "needed": "مجوز/عضویتِ همان سرویس (دور زده نمی‌شود)"},
]


def gold_market(conn, history_days: int = 60) -> dict:
    """داشبوردِ طلا: صندوق‌ها و نمادهایِ طلا/نقرهٔ *واقعاً* رویِ تابلو + تاریخچه.

    طبقه از `classify()` می‌آید (طلا/نقره)، پس فهرستِ خودیِ دستی نساخته‌ایم؛
    اوراقِ مرابحۀ طلا و «سلفِ سکه» هم که نامشان طلا دارد ولی صندوق نیستند،
    با `cls` خودشان می‌آیند تا رابط بتواند آن‌ها را درِ گروه جدا بنشیند.
    """
    rows, meta = E.enrich(conn)
    keep = [r for r in rows
            if r["kind"] in ("gold", "silver")
            or "طلا" in (r["name"] or "") or "سكه" in (r["name"] or "")
            or "نقره" in (r["name"] or "")]
    out = []
    for r in keep:
        m = r["_m"]
        out.append({
            "symbol": r["symbol"], "ins_code": r["ins_code"], "name": r["name"],
            "cls": r["cls"], "kind": r["kind"],
            "p_closing": E._f(r.get("p_closing")), "p_last": E._f(r.get("p_last")),
            "p_yesterday": E._f(r.get("p_yesterday")),
            "pct": None if r.get("pct") is None else round(r["pct"], 2),
            "tone": _pct_class(r.get("pct")),
            "value_b_toman": round(m["val"] / _B_TUMAN, 1),
            "volume_m_share": round(m["vol"] / _M_SHARE, 2),
            "market_cap_b_toman": round(E._f(r.get("market_cap")) / _B_TUMAN, 1)
                                   if r.get("market_cap") else None,
            "trades": int(m["trades"]),
        })
    out.sort(key=lambda x: x["value_b_toman"], reverse=True)
    tot_val = sum(x["value_b_toman"] for x in out)
    for x in out:
        x["value_share_pct"] = round(100.0 * x["value_b_toman"] / tot_val, 2) if tot_val else None

    # تاریخچه از price_history (بستۀ روزانۀ خودِ بانک) — برایِ sparkline و نمودارِ
    # خطیِ «مدیریتِ سبد». بی‌ردیف ⇒ سریِ خالی، و رابط «تاریخچه نیست» می‌گوید.
    hist = _symbol_history(conn, [x["symbol"] for x in out], history_days)
    for x in out:
        x["spark"] = hist.get(x["symbol"], [])
    return {
        "status": "ok", "asof": meta, "computed_at": _stamp(),
        "unit": {"price": "ریال", "value": "میلیارد تومان", "volume": "میلیون سهم"},
        "basis": "classify() kind∈{gold,silver} + نامِ طلا/سکه/نقره درِ ردیفِ تابلو",
        "symbols": out, "symbols_count": len(out),
        "total_value_b_toman": round(tot_val, 1),
        "history_days": history_days,
        "history_source": "price_history (بستۀِ روزانۀِ همین بانک)",
        "no_source": GOLD_NO_SOURCE,
        "access_limits": [g for g in GOLD_NO_SOURCE if g["key"] == "intrinsic_value"],
    }


def _symbol_history(conn, symbols, days: int) -> dict:
    """بستۀِ روزانۀِ چند نماد در یک کوئری — sparkline‌ها بدونِ N+1."""
    syms = [s for s in symbols if s]
    if not syms:
        return {}
    days = max(2, min(int(days or 60), 500))
    ph = ",".join("?" * len(syms))
    try:
        recs = conn.execute(
            "SELECT symbol, date, close FROM price_history WHERE symbol IN (%s)"
            " ORDER BY symbol, date DESC" % ph, tuple(syms)).fetchall()
    except Exception:
        return {}
    out: dict = {}
    for sym, date, close in recs:
        lst = out.setdefault(sym, [])
        if len(lst) < days:
            lst.append({"d": date, "v": E._f(close) if close is not None else None})
    for lst in out.values():
        lst.reverse()
    return out


def gold_history(conn, symbol: str, days: int = 250) -> dict:
    """تاریخچۀِ خوانِ یک نمادِ طلا — برایِ نمودارِ خطیِ «مدیریتِ سبد» و مقایسه.

    بی‌ردیف `available:false` برمی‌گردد؛ خطِ صافِ یک‌نقطه‌ای یا سریِ ساختگی
    هرگز ساخته نمی‌شود.
    """
    got = _symbol_history(conn, [symbol], days).get(symbol, [])
    peak = None
    if got:
        vals = [r["v"] for r in got if r["v"]]
        if vals:
            peak = {"value": max(vals), "at": max((r for r in got if r["v"]),
                                                  key=lambda r: r["v"])["d"]}
    return {"status": "ok", "symbol": symbol, "computed_at": _stamp(),
            "available": bool(got), "points": len(got), "days": days,
            "unit": "ریال", "basis": "price_history.close (قیمتِ پایانیِ منتشرشده)",
            "series": got, "peak": peak,
            "note": None if got else "تاریخچه‌ای برایِ این نماد در بانک نیست"}
