# -*- coding: utf-8 -*-
"""client_split.py — تنها تعریفِ درصدِ حقیقی/حقوقی در BorsTerminal.

رأیِ مالک (1405-07-20، بند ۲ مأموریت): مبنایِ درصدها **ارزشِ خرید و فروش** است،
نه حجم — و ارزشِ گم‌شده از ضربِ حجم در آخرین قیمت بازسازی نمی‌شود. نبودِ ارزش
برایِ همان نماد در همان نشست یعنی «نامشخص»، نه صفر و نه عددِ تخمینی:

    سهمِ حقیقیِ خرید = ارزشِ خریدِ حقیقی ÷ (ارزشِ خریدِ حقیقی + ارزشِ خریدِ حقوقی) × 100
    سهمِ حقیقیِ فروش = ارزشِ فروشِ حقیقی ÷ (ارزشِ فروشِ حقیقی + ارزشِ فروشِ حقوقی) × 100

سه قواعدی که این فایل نگه می‌دارد:

۱) خرید و فروش **مستقل** محاسبه می‌شوند. سهمِ حقیقیِ خرید هرگز جای سهمِ حقیقیِ
   فروش را نمی‌گیرد؛ مخرجِ هر کسر فقط جمعِ همان سمت است.

۲) سهمِ حقوقی مکملِ سهمِ حقیقیِ **همان سمت** است، مشروط بر اینکه هر دو گروهِ
   آن سمت ارزشِ معتبر داشته باشند. یک سمتِ نصفه‌نیمه درصد ندارد.

۳) نبودِ داده جعل نمی‌شود: `None` یعنی «نامشخص». منفی، NaN، ±inf، رشته،
   مخرجِ صفر و نبودِ یکی از دو گروه — همه همان None می‌شوند (مخرجِ صفر یعنی در
   این سمت هیچ ارزشی ثبت نشده، نه اینکه سهمِ حقیقی صفر است).

منبعِ یگانهٔ ورودی، جدولِ canonical خودِ برنامه است: `client_type_value`
(ارزشِ ریالیِ مبدأ از `ClientType/GetClientTypeHistory`). `client_type` فقط
حجم و تعداد دارد — GetClientTypeAll همین‌ها را می‌فرستد (سنجشِ زنده
1405-07-20: کلیدهایِ buy_I_Value / buy_N_Value درِ آن پاسخ نیستند) — پس
درصدِ این فایل از آن جدول خوانده نمی‌شود و هیچ‌جا با «سهمِ حجم» یکی نمی‌شود.

`mstat_engine.money()` برایِ ترازِ کلِ بازار همان چهار خانه را وقتی مبدأ نبود
با حجم×VWAP بازسازی می‌کند و مبدأ را درِ `value_source` اعلام می‌کند. آن مسیر
دست‌نخورده است؛ این فایل فقط ریاضیِ محضِ درصد را تعریف می‌کند تا آن لایه هم
همین کسر را بسازد، نه کسرِ دومِ خودی.
"""
from __future__ import annotations

BASIS = "value"

# برچسبِ یکسانِ رابط: همان متنی که مالک درِ بند ۲ خواسته است. رابط عدد نمی‌سازد،
# فقط این دو رشته را کنارِ عددِ بک‌اند می‌گذارد.
LABEL_BUY = "سهم از ارزش خرید"
LABEL_SELL = "سهم از ارزش فروش"
UNKNOWN_TEXT = "نامشخص"

# خانه‌هایِ `client_type_value` که یک درصدِ سمت لازم دارد.
_SIDE_FIELDS = {
    "buy": ("buy_i_val", "buy_n_val"),
    "sell": ("sell_i_val", "sell_n_val"),
}


def money(v):
    """عددِ ریالیِ معتبر یا None — بی‌تخمین، بی‌مطلق‌سازی.

    منفی بودنِ ارزشِ یک گروه معنای فنی ندارد (سهمِ فروشِ همان گروه درِ TSETMC
    مثبت گزارش می‌شود)، پس منفی «مقدارِ نامعتبر» است نه «صفر».
    """
    if v is None or isinstance(v, bool):
        return None
    if not isinstance(v, (int, float)):
        # رشته/bytes هرچه که باشد (حتی «۱۲۳» که float() آن را می‌پذیرد) ورودیِ
        # این لایه نیست: عددِ خوانده‌شده از JSON/SQLite عدد است، و رشته یعنی
        # جایی بالایِ اینجا قراردادِ ستون را شکسته‌ایم — نه اینکه تبدیلش کنیم.
        return None
    x = float(v)
    if x != x or x in (float("inf"), float("-inf")):
        return None
    if x < 0:
        return None
    return x


def side_share(retail_val, legal_val, digits=1):
    """سهمِ حقیقی از ارزشِ **یک سمت** (۰ تا ۱۰۰) — یا None یعنی نامشخص."""
    r = money(retail_val)
    l = money(legal_val)
    if r is None or l is None:
        return None
    den = r + l
    if den <= 0:
        return None
    return round(100.0 * r / den, digits)


def complement(share, digits=1):
    """سهمِ حقوقیِ همان سمت — مکمل، با همان گردکردگیِ یک‌طرفه."""
    if share is None:
        return None
    return round(100.0 - share, digits)


def side_shares(retail_val, legal_val, digits=1):
    """یک درصدِ کاملِ یک سمت: (retail_pct, legal_pct) — یا (None, None)."""
    r = side_share(retail_val, legal_val, digits)
    return r, complement(r, digits)


def shares(buy_i_val=None, buy_n_val=None, sell_i_val=None, sell_n_val=None,
           digits=1):
    """درصدهایِ هر دو سمت از چهار ارزشِ مبدأ.

    ستون‌هایِ بازگشتی دقیقاً همان کلیدهایی‌اند که تابلو، سایدبار، دیده‌بان و
    کارتِ بنیادی می‌خوانند؛ هیچ‌کدام درِ رابط دوباره حساب نمی‌شوند.
    `pct_basis` تنها وقتی `value` است که حداقلِ یک سمت درصد داشته باشد —
    وگرنه None، یعنی «برایِ این نماد در این نشست ارزشِ مبدأ نداریم».
    """
    b_retail, b_legal = side_shares(buy_i_val, buy_n_val, digits)
    s_retail, s_legal = side_shares(sell_i_val, sell_n_val, digits)
    return {
        "retail_buy_pct": b_retail,
        "legal_buy_pct": b_legal,
        "retail_sell_pct": s_retail,
        "legal_sell_pct": s_legal,
        "pct_basis": BASIS if (b_retail is not None or s_retail is not None) else None,
    }


def shares_from_row(row, digits=1):
    """همان درصدها، از ردیفی که نامِ ستون‌هایِ `client_type_value` را دارد."""
    return shares(*[money(row.get(k)) if row.get(k) is not None else None
                    for k in ("buy_i_val", "buy_n_val", "sell_i_val", "sell_n_val")],
                  digits=digits)


def aggregate_shares(retail_val, legal_val, digits=1):
    """درصدِ تجمیعی (کلِ بازار یا یک صنعت) با همان ریاضیِ تک‌نمادی.

    `mstat_engine.client_split()` جمع‌هایِ ارزش را از `money()` می‌آورد — چه
    مبدأ چه بازسازیِ اعلام‌شده — و درصد را همین‌جا می‌سازد تا کسرِ دومِ خودیِ
    آن لایه حذف شود. مبدأ بودنِ ورودی مسئولیتِ همین فایل نیست؛ lایه‌اش
    `value_source` را جدا اعلام می‌کند.
    """
    return side_shares(retail_val, legal_val, digits)
