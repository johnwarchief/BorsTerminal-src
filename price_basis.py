# -*- coding: utf-8 -*-
"""price_basis.py — تنها نقطۀ انتخابِ ستونِ قیمت در کلِ برنامه.

قرارداد: docs/CANDLE-CONTRACT.md §۱-ث. «Price Source» یک settingِ رسمیِ محصول است با دو
مقدارِ `last` | `closing` و پیش‌فرضِ `last`. انتخاب **سمتِ سرور** انجام می‌شود، نه فرانت:
قیفِ غربالگری، برچسب‌هایِ تابلو و کارتِ FTS باید همان مبنایِ چارت را ببینند (شرطِ ۲ِ قرارداد؛
شکلِ نقضِ آن درِ #66 دیدیم).

سه قاعده‌ای که این فایل نگه می‌دارد:

۱) `close` درِ payloadِ همهٔ سری‌دهنده‌ها == هماندازۀ منتخبِ کاربر. هیچ مصرف‌کننده‌ای
   (چارت، اندیکاتور، FTS، الگو، غربگر، اطمینان، سیگنال) حقِ انتخابِ ستونِ خودش را ندارد؛
   همه از `apply_basis()` می‌گذرند.

۲) لنگرِ زنجیرِ تعدیل **همیشه CLOSING** است و به این setting ربطی ندارد. سنجشِ ۸۰۰نمادیِ
   §۱-پ نشان داد اگر لنگر هم به `last` برود، لنگر درِ ۷۳۹ از ۸۰۰ نماد (۹۲٪) می‌شکند و
   مقیاسِ میانیِ ۱٬۲۳۷ روز جابه‌جا می‌شود. پس هر کندل پس از `apply_basis` این سه کلید را
   دارد: `closing` = قیمتِ پایانیِ خام (لنگر)، `last` = آخرینِ خام یا None، و `close` =
   منتخبِ کاربر. تشخیصِ رویدادِ تعدیل درِ `api/chart.py:_adjust_events_from_rows` از
   `all_rows` (base/close خامِ CSV) می‌آید و هرگز از این سه کلیدِ منتخب تغذیه نمی‌شود.

۳) جعلِ داده ممنوع (شرطِ ۳ِ قرارداد). اگر مبنایِ منتخب درِ آن سری موجود نباشد، سری
   **بی‌مخالفتِ مبنی** رویِ `closing` می‌نشیند و صریح اعلام می‌کند چرا:
   `basis_requested="last"`, `basis_applied="closing"`, `basis_reason="last_missing:<n>/<m>"`.
   یکِ سری هرگز دو مبنایِ قاطی ندارد، چون MA/RSI/MACD رویِ سریِ مخلوط معنا ندارند.

`closing` همیشه موجود است؛ پس تنها حالتِ «هیچ عددی» نبودِ خودِ کندل است، نه نبودِ مبنایِ منتخب.
"""
from __future__ import annotations

import json
import os
import threading

LAST = "last"
CLOSING = "closing"
ALLOWED = (LAST, CLOSING)
DEFAULT = LAST

_lock = threading.Lock()
# کشِ (mtime, size) → مقدار؛ تنظیمات در هر درخواست خوانده نمی‌شود، ولی تغییرِ فایل
# (پنلِ تنظیمات) بلافاصله اثر می‌کند چون امضایِ دیسک عوض می‌شود.
_cache: dict = {"sig": None, "value": DEFAULT}


def _path() -> str:
    from bors_config import PRICE_BASIS_PATH  # دایرۀ import را نمی‌شکند
    return PRICE_BASIS_PATH


def _read() -> str:
    try:
        p = _path()
        st = os.stat(p)
        sig = (p, st.st_mtime_ns, st.st_size)
        if _cache["sig"] == sig:
            return _cache["value"]
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        val = raw.get("basis") if isinstance(raw, dict) else raw
        val = val if val in ALLOWED else DEFAULT
        _cache["sig"], _cache["value"] = sig, val
        return val
    except Exception:
        # نبودِ فایل/فایلِ خراب/بانکِ قفل‌شده ⇒ پیش‌فرض، نه استثنا: هیچ endpointی
        # نباید به‌خاطرِ یک تنظیماتِ ناموجود ۵۰۰ بدهد.
        return DEFAULT


def current() -> str:
    """مبنایِ فعلیِ انتخابیِ کاربر (همیشه یکی از ALLOWED)."""
    return _read()


def set_basis(value) -> dict:
    """اعتبارسنجی + نوشتنِ اتمیک. هر مقدارِ خارج از `last|closing` مردود است."""
    val = (value or "").strip().lower() if isinstance(value, str) else value
    if val not in ALLOWED:
        return {"status": "error", "message": "Price Source فقط `last` یا `closing` است",
                "basis": None, "allowed": list(ALLOWED)}
    p = _path()
    with _lock:
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"basis": val}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        _cache["sig"], _cache["value"] = None, val
    return {"status": "success", "basis": val, "allowed": list(ALLOWED)}


def describe() -> dict:
    """برچسبِ مبنایی که درِ payloadها می‌نشیند تا گزارشِ parity بداند کدام حالت سنجیده شده."""
    return {"basis": current(), "default": DEFAULT, "allowed": list(ALLOWED)}


# ─────────────────────────────── انتخابِ ستون (تنها نقطه) ───────────────────────────────

def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def closing_of(c: dict):
    """لنگرِ تعدیل: قیمتِ پایانی. هرگز به setting وابسته نیست."""
    return _num(c.get("closing", c.get("close_raw"))) or _num(c.get("close"))


def last_of(c: dict):
    """آخرینِ خامِ همان روز، یا None وقتی منبع آن را نداشته (هیچ‌وقت جای‌نمایِ پایانی)."""
    return _num(c.get("last"))


def close_of(c: dict, basis: str = None):
    """تک‌کندل: عددی که باید نمایش داده/محاسبه شود.

    برایِ series از `apply_basis` استفاده کنید؛ این تابع جایِ مصرف‌کننده‌هایی است که یکِ
    ردیفِ تک دارند (ردیفِ تابلو، کندلِ زنده) و همان قاعده‌ی «بی‌جعل» را نگه می‌دارد.
    """
    b = basis or current()
    if b == LAST:
        v = last_of(c)
        if v is not None:
            return v
    return closing_of(c)


def basis_of_row(c: dict, basis: str = None) -> str:
    b = basis or current()
    return b if (b != LAST or last_of(c) is not None) else CLOSING


def apply_basis(candles, copy=False):
    """سازندۀ یکتای سری: هر کندل را به `(closing, last, close)` واحد تبدیل می‌کند.

    با `copy=True` رویِ نسخه‌ها کار می‌کند و نسخه‌ها را برمی‌گرداند. برایِ مسیرهایِ
    کش‌شده الزامی است: `CHART_CACHE` شیءهایِ کندل را بینِ دو حالتِ setting shared می‌کند،
    و تغییرِ در‌جا یعنی درخواستِ بعدی «مبنایِ قبلی» را درِ دستِ خودش می‌بیند و سنجشِ
    مقایسه‌ای هم صفرِ جابه‌جایی گزارش می‌کند (همان چیزی که درِ اولین اجرای
    `_audit/price_basis_anchor_invariance.py` پیش آمد — اندازه‌گیریِ بی‌محتوا، نه کدِ غلط).

    و بدونِ copy هم تابع idempotent است: `close` همیشه از `closing`/`last`ِ خام دوباره
    حساب می‌شود، پس دو‌بار صدا‌زدن با دو setting متوالی هم درست است.

    نتیجه را در‌جا رویِ همان لیست اعمال می‌کند (یا رویِ نسخه‌ها) و متادیتایِ سری را
    برمی‌گرداند:

        {"basis_requested","basis_applied","basis_reason","last_missing","count",
         "geometry_widened"}

    قاعدۀ هندسه: اگر عددِ منتخب بیرونِ [low, high] افتاد، **سایه گِشاد** می‌شود و قیمتِ
    منتخب خُرد نمی‌شود — همان قاعدۀ `candle_from_row` و کامنتِ v8.7 FIX-1b. Clampِ خودِ
    قیمت (قاعدۀ قدیمیِ `_parse_tsetmc_csv`) دقیقاً همان چیزی بود که «آخرین» را بی‌صدا
    عوض می‌کرد؛ درِ همین قدم برداشته شد و جابه‌جاییِ سایه درِ متادیتا شمرده می‌شود.
    """
    requested = current()
    if copy:
        candles = [dict(c) for c in candles]
    n = len(candles)
    missing = 0
    for c in candles:
        if last_of(c) is None:
            missing += 1
    applied = requested
    reason = None
    if requested == LAST and missing:
        # سری مخلوط نمی‌سازیم: یا همه «آخرین»، یا همه با اعلامِ صریح «پایانی».
        applied = CLOSING
        reason = f"last_missing:{missing}/{n}"
    widened = 0
    for c in candles:
        anchor = closing_of(c)
        c["closing"] = anchor
        chosen = last_of(c) if applied == LAST else anchor
        if chosen is None:
            chosen = anchor
        c["close"] = chosen
        hi = _num(c.get("high_raw", c.get("high")))
        lo = _num(c.get("low_raw", c.get("low")))
        op = _num(c.get("open"))
        if hi is not None and lo is not None:
            # هندسه از «سایۀ خام» حساب می‌شود تا دو‌بار صدا‌زدن (یا عوض‌شدنِ setting
            # رویِ یک سریِ کش‌شده) گِشاد‌کردنِ انباشته نسازد.
            c["high_raw"], c["low_raw"] = hi, lo
            nh, nl = max(hi, lo, chosen), min(hi, lo, chosen)
            if op is not None:
                nh, nl = max(nh, op), min(nl, op)
            if nh != hi or nl != lo:
                widened += 1
            c["high"], c["low"] = nh, nl
    meta = {"basis_requested": requested, "basis_applied": applied,
            "basis_reason": reason, "last_missing": missing, "count": n,
            "geometry_widened": widened}
    for c in candles:
        c["basis"] = applied
    if copy:
        meta["candles"] = candles
    return meta


def resolve_payload(res: dict, key: str = "candles",
                    colors: tuple = ("#10b981", "#f43f5e")) -> dict:
    """پایانِ هر سری‌دهنده: مبنایِ منتخب را رویِ آرایۀ کندل‌ها می‌نشیند، رنگِ حجم را
    هم با همان عدد دوباره حساب می‌کند، و متادیتا را ضمیمه می‌کند.

    کش‌ها باید **پیش** از این تابع پر شوند (سریِ خامِ هر دو مبن را نگه دارند) تا
    عوض‌شدنِ setting درِ درخواستِ بعدی اثر کند، نه بعد از TTLِ کش.
    `colors` جفتِ (صعودی، نزولی) خودِ endpoint است — هر سری‌دهنده‌ای رنگِ خودش را دارد
    و تبدیلِ آن‌ها به یکِ رنگِ مشترک، تغییرِ ظاهریِ بی‌ربط به این قدم است.
    """
    cands = res.get(key)
    if not cands:
        return res
    # copy=True: کشِ `/api/chart` (CHART_CACHE) شیءهایِ کندل را نگه می‌دارد و باید
    # **همیشه خام** بمانند تا عوض‌کردنِ setting درِ TTLِ کش هم اثر کند؛ بی‌copy،
    # درخواستِ حالتِ بعدی رویِ آرایۀ دست‌کاری‌شده‌یِ حالتِ قبل می‌نشست.
    meta = apply_basis(cands, copy=True)
    out = dict(res)
    out[key] = meta.pop("candles")
    vols = res.get("volumes")
    if vols:
        up_c, dn_c = colors
        by_time = {c.get("time") or c.get("date"): c for c in cands}
        fixed = []
        for v in vols:
            c = by_time.get(v.get("time"))
            vv = dict(v)
            if c is not None and c.get("open") is not None and c.get("close") is not None:
                vv["color"] = up_c if c["close"] >= c["open"] else dn_c
            fixed.append(vv)
        out["volumes"] = fixed
    return stamp(out, meta)


def stamp(payload: dict, meta: dict) -> dict:
    """متادیتایِ مبن را رویِ پاسخِ endpoint می‌گذارد (تضمینِ ۵ِ قرارداد: گزارشِ parity
    باید بداند این مقایسه درِ کدام حالت انجام شده)."""
    payload["priceBasis"] = meta.get("basis_applied")
    payload["priceBasisRequested"] = meta.get("basis_requested")
    if meta.get("basis_reason"):
        payload["priceBasisReason"] = meta["basis_reason"]
    payload["priceBasisLastMissing"] = meta.get("last_missing")
    return payload
