# -*- coding: utf-8 -*-
"""corporate_ledger.py — ledgerِ canonicalِ رویدادهایِ شرکتی: خوانشِ **فقط‌خواندنی** از جداولِ
رسمیِ TSETMC + افزودنِ نوع از CODAL، و تبدیل به رویدادهایِ type-awareِ `adjustment_engine`.

چرا این فایل (نقش درِ معماری):
  • جداولِ `price_adjust_events` / `share_change_events` تنها منبعِ رسمیِ «ضریبِ اقدامِ شرکتی»
    هستند (نسبتِ adj/raw و old/new، منتشرشدهٔ خودِ TSETMC). موتورِ تعدیل باید از همین منبعِ
    یکتا بخواند، نه از queryهایِ پراکنده یا دوباره‌محاسبهٔ ضریب.
  • `corporate_type_code` درِ TSETMC صددرصد null است (سنجشِ ۱۴۰۵: ۱۰۰۱/۱۰۰۱ null). پس «نوعِ
    رویداد» از CODAL (عنوانِ اطلاعیه) به‌صورتِ best-effort افزوده می‌شود؛ جایی که مطمئن نیستیم
    نوع **ناشناخته** می‌ماند و هرگز حدس نمی‌خورد.
  • این ماژول بی‌نوشتن برِ دیتابیس، بی‌شبکه. نوشتنِ عملیاتیِ جدول‌ها درِ `test_tsetmc.py` است
    (fetch_corporate_events، روزی یک‌بار)؛ اینجا فقط **استخراج/سازمان‌دهیِ canonical** انجام می‌شود.

قواعدِ ledger (طبقِ Stage 3):
  • شناسۀِ پایدار = (ins_code, d_even)؛ کلیدِ PRIMARY KEYِ خودِ جداول → بی‌تکرارِ ذاتی.
  • همان روز درِ هر دو جدول = یکِ رویدادِ واحد (priceAdjust تقدمِ بر shareChange — همان قاعدۀِ
    `_sharpen_events_with_ledger`ِ چارت)؛ پس هیچ ضریبی دوبار اعمال نمی‌شود.
  • نسبتِ رسمی از خودِ ردیف خوانده می‌شود؛ نبودِ ستونِ لازم → incomplete؛ خارجازکران → invalid.
  • تاریخِ مؤثر = d_even (روزِ ظهورِ قیمتِ تعدیل‌شده)؛ تاریخِ انتشارِ اطلاعیه درِ provenance جدا می‌ماند.
  • دادهٔ خامِ رسمی (adj/raw، old/new) از مقادیرِ مشتق جدا می‌ماند؛ provenanceِ هر فاکتور درِ خروجی.
"""
from __future__ import annotations

import adjustment_engine as AE

# نوع‌دهی از عنوانِ CODAL — تنها کلماتی که درِ دادهٔ موجود معنا دارند (بدونِ ساختنِ دسته‌هایِ ساختگی)
_TYPE_KEYWORDS = (
    (AE.KIND_CAPITAL_CONTRIBUTION, ("حق تقدم", "حق تقدم", "پذیره‌نویسی", "پذیرهنویسی", "آورده")),
    (AE.KIND_CAPITAL_RESERVE, ("افزایش سرمایه",)),
    (AE.KIND_CASH_DIVIDEND, ("پرداخت سود", "تقسیم سود", "سود نقدی", "سود دوره")),
    (AE.KIND_SPLIT, ("تجزیه سهم", "تقسیم سهام",)),
    (AE.KIND_MERGE, ("تجمیع سهم", "تجمیع سهام",)),
)


def normalize_fa(s):
    return str(s or "").translate(str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی"})).strip()


def normalize_title(s):
    """عنوانِ اطلاعیه برایِ تطبیقِ کلیدواژه.

    نیم‌فاصله باید حذف شود، وگرنه «حق‌تقدم»ِ نوشته‌شده با ZWNJ هرگز با کلیدواژهٔ
    «حق تقدم» (فاصله) نمی‌خوانده و آن اطلاعیه‌ها بی‌سروصدا `unresolved` می‌ماندند.
    (سنجشِ واقعیِ همین دور: `codal_notices` هم با «حق تقدم» و هم با «حق‌تقدم» دارد.)
    """
    return normalize_fa(s).replace(chr(0x200C), " ").replace(chr(0x200B), " ").strip()


def title_type(title):
    """نوعِ canonical از عنوانِ اطلاعیه؛ None یعنی قابلِ تعیین نیست (نه حدس)."""
    t = normalize_title(title)
    for kind, keys in _TYPE_KEYWORDS:
        if any(k in t for k in keys):
            return kind
    return None


def _ratio(a, b):
    """b/a با گاردِ a>0 و گردکردنِ ۸ رقم؛ None اگر قابلِ محاسبه نیست."""
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    if a <= 0:
        return None
    return round(b / a, 8)


def build_typed_events(conn, ins_code):
    """(events, meta) — رویدادهایِ type-awareِ موتور برایِ یک ابزار، از جداولِ رسمی.

    هر رویداد: {'kind','date','ratio'/'...','reference_price'?,'provenance':{...},'event_id'}.
    meta: شمارش‌هایِ Stage 2.5 (دارایِ نوع معتبر / مرجعِ رسمی / کامل / نیازمندِ S / بی‌نوع / …).
    """
    # codal: نوع/پیامِ مرتبط برایِ این ابزار (best-effort؛ تاریخِ انتشار جدا).
    # `observed_at` (= `fetched_at`ِ خودِ ردیفِ مبدأ) و `published_at` (= تاریخِ اطلاعیهٔ
    # کدال) از `effective_date` جدا می‌مانند: روزِ انتشارِ اطلاعیه لزوماً روزِ ظهورِ قیمتِ
    # تعدیل‌شده نیست، و روزِ دیدنِ ما درِ TSETMC هم هیچ‌کدام از آن دو نیست.
    codal = []
    sym = None
    try:
        sym = conn.execute("SELECT symbol FROM price_adjust_events WHERE ins_code=? AND symbol IS NOT NULL LIMIT 1",
                           (ins_code,)).fetchone()
        sym = sym[0] if sym else None
    except Exception:
        sym = None
    if sym:
        try:
            for title, pdate, tr in conn.execute(
                    "SELECT title, publish_date, tracing_no FROM codal_notices "
                    "WHERE symbol=? ORDER BY publish_date", (normalize_fa(sym),)):
                codal.append({"type": title_type(title), "publish_date": pdate,
                              "tracing_no": tr, "title": title})
        except Exception:
            pass
    # نوعِ غالبِ ابزار فقط وقتی یکتا است افزوده می‌شود؛ مختلط → نامشخص (بی‌حدس).
    instrument_types = {c["type"] for c in codal if c["type"]}
    unique_type = instrument_types.pop() if len(instrument_types) == 1 else None

    # ردیف‌هایِ رسمی؛ dedupِ خودِ PK. یکِ g_even = یکِ رویداد (priceAdjust تقدم).
    by_date = {}
    for d, raw, adj, ctype, seen in conn.execute(
            "SELECT d_even, p_closing_not_adjusted, p_closing, corporate_type_code, fetched_at "
            "FROM price_adjust_events WHERE ins_code=?", (ins_code,)):
        dt = _d_even_to_date(d)
        if dt:
            by_date[dt] = {"d_even": d, "kind": AE.KIND_SOURCE_RATIO, "date": dt,
                           "adj": adj, "raw": raw, "src": "priceAdjust",
                           "tsetmc_ctype": ctype, "seen": seen}
    for d, old, new, seen in conn.execute(
            "SELECT d_even, shares_old, shares_new, fetched_at "
            "FROM share_change_events WHERE ins_code=?", (ins_code,)):
        dt = _d_even_to_date(d)
        if dt and dt not in by_date:          # priceAdjust تقدم دارد (بی‌اعمالِ دوباره)
            by_date[dt] = {"d_even": d, "kind": AE.KIND_SOURCE_RATIO, "date": dt,
                           "old": old, "new": new, "src": "shareChange", "seen": seen}

    events, counts = [], {
        "events_total": 0, "typed_ok": 0, "with_official_ref": 0, "complete": 0,
        "needs_offer_price": 0, "unknown_type": 0, "bad_identity_date": 0, "incomplete_or_invalid": 0}
    for dt in sorted(by_date):
        rec = by_date[dt]
        counts["events_total"] += 1
        prov = {"ins_code": ins_code, "symbol": sym, "d_even": rec["d_even"],
                "source": rec["src"], "effective_date": dt,
                # «رویت‌شدن» توسطِ ما ≠ «انتشارِ اطلاعیه» ≠ «روزِ مؤثرِ ضریب». سه میدانِ جدا،
                # و `observed_at` ازِ خودِ ستونِ `fetched_atِ` مبدأ خوانده می‌شود (نه ازِ ساعتِ
                # این اجرا) تا ثابت باشد ردیفِ بانکیِ همین رویداد کِی تازه شده است.
                "observed_at": rec.get("seen")}
        # پیوندِ اطلاعیهٔ کدال: فقط وقتی **یگتا** است می‌چسبد. تقویمِ `publish_date` جلالی
        # است (سنجشِ واقعی: `1405-06-01`) و این مخزن یگانۀِ تبدیلِ جلالی←میلادی ندارد؛
        # پس عددِ تبدیل‌شده نمی‌سازیم، خودِ مقدارِ مبدأ را با تقویمِ اعلام‌شده می‌بریم.
        # نبودِ پیوند = «نامطمئن» است، نه «بی‌اطلاعیه» (`notice_candidates` ثبت می‌شود).
        if len(codal) == 1:
            n = codal[0]
            prov.update({"published_at": n["publish_date"], "published_calendar": "jalali",
                         "tracing_no": n["tracing_no"], "notice_title": n["title"]})
        prov["notice_candidates"] = len(codal)

        # نسبتِ رسمی — هر مبدأ درِ واحدِ خودش؛ جهتِ canonical: تعدیلِ کاهنده نسبتِ «بعد/قبلِ واقعی».
        if rec["src"] == "priceAdjust":
            ratio = _ratio(rec.get("raw"), rec.get("adj"))          # = p_closing / p_closing_not_adjusted
            ref = rec.get("raw")
            if ref:
                prov["reference_price_official"] = ref
                counts["with_official_ref"] += 1
        else:
            ratio = _ratio(rec.get("new"), rec.get("old"))          # = shares_old / shares_new (canonical)
            ref = None
        ev = {"kind": rec["kind"], "date": dt, "ratio": ratio, "event_id": f"{ins_code}:{rec['d_even']}"}
        if ref:
            ev["reference_price"] = ref
        ev["provenance"] = prov

        # نوع (metadata)؛ برایِ source_ratio موتورِ عدد از نسبتِ رسمی می‌آید، نوع فقطِ برچسب است.
        etype = unique_type
        if etype:
            prov["event_type"] = etype
            prov["type_confidence"] = "instrument-unique-codal"
            counts["typed_ok"] += 1
        else:
            prov["event_type"] = None
            prov["type_confidence"] = "unresolved"     # بی‌حدس
            counts["unknown_type"] += 1
        if etype == AE.KIND_CAPITAL_CONTRIBUTION:
            prov["needs_offer_price"] = True
            counts["needs_offer_price"] += 1

        _, status = AE.event_factor(ev)
        # وضعیتِ اعتبار **همیشه** می‌نشیند (پیش‌تر فقط ردیف‌هایِ خراب علامت می‌خوردند؛
        # «علامت‌نشده» با «سالم» یکی نبود و مصرف‌کننده نمی‌توانست تفاوت بگذارد).
        prov["factor_status"] = status
        ev["validity"] = "valid" if status == AE.OK else "rejected"
        if status == AE.OK:
            counts["complete"] += 1
        else:
            counts["incomplete_or_invalid"] += 1
        events.append(ev)

    counts["published_vs_effective_separated"] = bool(codal)
    return events, counts


def _d_even_to_date(d_even):
    s = str(d_even or "").strip()
    if len(s) != 8 or not s.isdigit():
        return None
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"
