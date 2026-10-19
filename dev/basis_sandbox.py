# -*- coding: utf-8 -*-
"""dev/basis_sandbox.py — جعبۀِ امنِ «مبنایِ قیمت» برایِ سوئیت‌هایِ تست

چرا لازم است: `price_basis.set_basis()` تنها مصرف‌کنندۀِ فایلِ تنظیمِ **واقعیِ**
محصول (`price_basis.json` کنارِ app.py) است. سوئیتی که آن را صدا بزند و مسیر را
به پوشۀِ موقت نبرد، تنظیمِ محصول را جاودانه عوض می‌کند. سنجشِ ۱۴-۰۷-۲۷:
پس ازِ گیت، همان فایل رویِ `closing` می‌ماند و چارتِ بازِ بعدی بی‌صدا با مبنایِ
دیگری عدد می‌داد — درِ فولاد ۵۰۲ از ۶۰۱ بستۀِ خامِ متفاوت با منبعِ مرجع، وِ هر
ممیزیِ بعدی رویِ همانِ تنظیمِ خراب شروع می‌شد.

`use_sandboxed_basis()` مسیر را به پوشۀِ موقت می‌برد، کشِ `price_basis` را بی‌اعتبار
می‌کند، و بازگردانی را با `atexit` ثبت می‌کند — پس حتی اگر سوئیت میانه‌اش بمیرد،
تنظیمِ واقعیِ محصول دست‌نخورده برمی‌گردد.
"""
from __future__ import annotations

import atexit
import os
import tempfile


def use_sandboxed_basis(label: str = "") -> str:
    """مسیرِ تنظیمِ مبنایِ قیمت را به پوشۀِ موقت می‌برد. پوشه را برمی‌گرداند."""
    import bors_config
    import price_basis

    real = bors_config.PRICE_BASIS_PATH
    if os.path.abspath(real).startswith(tempfile.gettempdir()):
        return os.path.dirname(real)          # از قبل درِ جعبه است
    work = tempfile.mkdtemp(prefix="pb_sandbox_")
    bors_config.PRICE_BASIS_PATH = os.path.join(work, "price_basis.json")
    price_basis._cache["sig"] = None

    def restore():
        try:
            bors_config.PRICE_BASIS_PATH = real
            price_basis._cache["sig"] = None
        except Exception:
            pass

    atexit.register(restore)
    return work
