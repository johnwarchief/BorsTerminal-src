# -*- coding: utf-8 -*-
"""codal_dividends.py — قراردادِ خواندنِ DPSِ اعلامیِ مجمع از صفحهٔ تصمیماتِ کدال.

منبع: صفحهٔ `Decision.aspx`ِ اطلاعیهٔ «تصمیمات مجمع عمومی عادی سالیانه». این صفحه
فیلدِ ساختاریِ `DividendPerShare` را در متنِ HTML دارد؛ مقدارش **DPSِ اعلامی**
است، نه اختلافِ تعدیلِ بورس (`p_closing_not_adjusted − p_closing`).

فرمولِ رهاورد با همین DPS و **پایانیِ رسمیِ روزِ رویداد** (`CLOSE`، نه `LAST`):
`close_ex / (close_ex + dps)` — پنج موردِ زنده در R32H تا 1e-12 تأیید شد.

این ماژول خالص است: شبکه/پایگاه‌داده ندارد. جستجو/واکشی در ابزارِ
`tools/ra365_round32h_codal_dps.py` است؛ مصرف‌کنندهٔ زمانِ اجرا فقط جدولِ
`stock_dividend_events` را می‌خواند.
"""
from __future__ import annotations

import re

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_LETTERS = str.maketrans({"ي": "ی", "ك": "ک", "\u200c": "", "\u200f": ""})


def _text(html):
    s = re.sub(r"<script.*?</script>", " ", html or "", flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    s = re.sub(r"\s+", " ", s).strip()
    return s.translate(_FA_DIGITS).translate(_LETTERS)


def _num(token):
    t = token.replace("٬", "").replace(",", "").replace("٫", ".").strip()
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").strip()
    try:
        value = float(t)
    except ValueError:
        return None
    return -value if neg else value


def parse_dividend_per_share(html):
    """DPSِ اعلامیِ مجمع (ریال) از HTMLِ صفحهٔ تصمیمات؛ نبودِ فیلد → None.

    فقط برچسبِ `DividendPerShare`/«سود نقدی هر سهم» خوانده می‌شود؛ اعدادِ دیگرِ
    همان صفحه (سودِ انباشته، سرمایه) هرگز جای DPS نمی‌نشینند.
    """
    text = _text(html)
    m = re.search(
        r"DividendPerShare\s*سود نقدی هر سهم\s*\(ریال\)\s*([()\d,.\u066c\u066b]+)",
        text)
    if not m:
        m = re.search(
            r"سود نقدی هر سهم[^0-9]{0,80}([()\d,.\u066c\u066b]+)", text)
    if not m:
        return None
    return _num(m.group(1))
