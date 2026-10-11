# -*- coding: utf-8 -*-
"""dev/test_mainwatch_flags_v1.py — انتقالِ پرچم‌هایِ تابلو به «نمادهای زیرِ نظر»

رأیِ مالک (۱۴۰۵-۰۷-۲۲): جدولِ «نمادهای زیرِ نظر» درِ «وضعیت بازار» جز پرچمِ
«الگوی ساعت» چیزی نمی‌دید؛ حجمِ مشکوک، ورودِ پولِ هوشمند و کد به کد هم باید
دیده شوند. داوری درِ `tape_flags.apply_tape_flags` است و `api/market_status.py`
آن را از فیدِ تابلو *منتقل* می‌کند. چیزی که این گارد اثبات می‌کند:

  ۱) پیوندِ نماد با نرمال‌سازیِ خودِ قیف انجام می‌شود (املاىِ دوگانه ك/ک)،
  ۲) پرچمِ نرسیده `None` می‌ماند — نه `False`، نه صفرِ جعلی،
  ۳) بی‌منبع هیچ ردیفی دست‌کاری نمی‌شود و `tape_flags_source` همین را می‌گوید،
  ۴) پاسخِ خطا هرگز پرچم نمی‌گیرد (تا یک خرابیِ جانبی جدول را نیمه‌سازِه نکند).

اجرا:  python dev/test_mainwatch_flags_v1.py
"""
from __future__ import annotations

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import api.market_status as MS  # noqa: E402

FAILED: list[str] = []


def ck(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILED.append(msg)


FLAGS = dict.fromkeys(MS.TAPE_FLAG_KEYS, False)


def board(flags_by_symbol: dict) -> None:
    """جانشینِ `_tape_flag_map` — بی‌نیازِ کشِ تابلو، با همان شکلِ پاسخ.

    کلیدها همان‌جا نرمال می‌شوند که تابعِ واقعی هم نرمال می‌کند
    (`_FE.norm_symbol` رویِ ردیفِ تابلو)؛ بی‌این، بندِ ۲ نرمال‌سازی را نمی‌سنجد.
    """
    import funnel_engine as FE
    MS._tape_flag_map = lambda: {
        FE.norm_symbol(k): {**FLAGS, **v} for k, v in flags_by_symbol.items()
    }


# ── ۱) پیوند و انتقال ─────────────────────────────────────────────────────
board({"شپنا": {"f_susp": True}, "كفپاه": {"f_smart": True, "f_legal": True}})
payload = {"status": "ok", "rows": [{"symbol": "شپنا"}, {"symbol": "كفپاه"},
                                    {"symbol": "ولرز"}]}
out = MS._attach_tape_flags(payload)
by = {r["symbol"]: r for r in out["rows"]}
ck(out.get("tape_flags_source") == "api/market", "۱) منبعِ پرچم درِ پاسخ اعلام می‌شود")
ck(by["شپنا"]["tape_flags"]["f_susp"] is True
   and by["شپنا"]["tape_flags"]["f_clock"] is False,
   "۱) پرچمِ روشن منتقل می‌شود و بقیه از خودِ فید می‌آید (نه حدسِ این فایل)")
ck(by["كفپاه"]["tape_flags"]["f_smart"] is True
   and by["كفپاه"]["tape_flags"]["f_legal"] is True,
   "۲) املاىِ عربی/فارسی با نرمال‌سازیِ خودِ قیف one-به-one می‌خورد")
ck(by["ولرز"]["tape_flags"] is None,
   "۳) نمادی که درِ فیدِ تابلو نیست None می‌ماند — نه False، نه صفرِ جعلی")
ck(set(by["شپنا"]["tape_flags"]) == set(MS.TAPE_FLAG_KEYS),
   "۴) همان هفت پرچم منتقل می‌شود؛ پرچمِ دومی اینجا ساخته نمی‌شود")

# ── ۵) بی‌منبع ────────────────────────────────────────────────────────────
MS._tape_flag_map = lambda: {}
p2 = {"status": "ok", "rows": [{"symbol": "شپنا"}]}
o2 = MS._attach_tape_flags(p2)
ck(o2.get("tape_flags_source") == "unavailable", "۵) بی‌منبع صریح «unavailable» است")
ck("tape_flags" not in o2["rows"][0],
   "۵) بی‌منبع هیچ ردیفی نیمه‌سازِه نمی‌شود (کلیدِ جعلیِ پرچم اضافه نمی‌شود)")

# ── ۶) خرابیِ منبع: همان مسیری که درِ اجرایِ واقعی می‌افتد ────────────────
import api.funnel as F  # noqa: E402

_real_board_rows = F._board_rows


def _boom():
    raise RuntimeError("تابلو هنوز درِ این اجرا نساخته")


F._board_rows = _boom
p3 = {"status": "ok", "rows": [{"symbol": "شپنا"}]}
o3 = MS._attach_tape_flags(p3)   # `_tape_flag_map` واقعی خودِ استثنا را می‌گیرد
ck(o3.get("tape_flags_source") == "unavailable" and "tape_flags" not in o3["rows"][0],
   "۶) خرابیِ منبع جدول را نمی‌شکند و «بی‌پرچم» جا نمی‌زند")
F._board_rows = _real_board_rows

# ── ۷) پاسخِ خطا پرچم نمی‌گیرد ────────────────────────────────────────────
board({"شپنا": {"f_susp": True}})
err = {"status": "error", "message": "x", "rows": [{"symbol": "شپنا"}]}
ck(MS._attach_tape_flags(err).get("tape_flags_source") is None,
   "۷) پاسخِ خطا هیچ برچسبِ پرچمی نمی‌گیرد")

print()
if FAILED:
    print(f"mainwatch tape-flags guard: {len(FAILED)} FAILED")
    sys.exit(1)
print("mainwatch tape-flags guard OK — ۷ بند")
