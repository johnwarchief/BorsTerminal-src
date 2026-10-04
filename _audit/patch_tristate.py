import io

p = "dev/test_fts_technical_tristate.py"
t = io.open(p, encoding="utf-8", newline="").read()

old = """# ══════════════ ۵) مارکر = موتور (تک‌منبعی) ══════════════
# هر مارکرِ جتی که تاریخچۀ گذشته می‌سازد باید با همان قاعدۀ «امروز» بخواند:
ev = CH._fts_setup_history(hist, CH._fts_swings(hist, k=CH._FTS_SWING_K))
ck("تاریخچۀٔ ستاپ، مارکرِ جت دارد", any(e["kind"] == "jet" for e in ev), ev[-4:])
"""
# نکته: در فایلِ واقعی عبارت «تاریخچهٔ» با HAMZA است؛ با find عوض می‌شود
i = t.index("۵) مارکر = موتور")
i = t.rindex(chr(10), 0, i) + 1
j = t.index('ck("تاریخچه', i)
k = t.index("\n", t.index('ev[-4:])', j))
old_block = t[i:k + 1]

new_block = '''# ══════════════ ۵) مارکر = موتور (تک‌منبعی) — و جت هرگز تاریخی نمی‌شود ══════════════
# دورِ J: این پین برگردانده شد. پیش‌تر «تاریخچۀ ستاپ مارکرِ جت دارد» را الزام
# می‌کرد؛ حالا جت فقط کندلِ آخر است، پس تاریخچه نباید هیچ مارکرِ جتی بدهد.
ev = CH._fts_setup_history(hist, CH._fts_swings(hist, k=CH._FTS_SWING_K))
ck("تاریخچه هیچ مارکرِ جتی نمی‌سازد", not any(e["kind"] == "jet" for e in ev), ev[-4:])
ck("جدولِ برچسبِ رویدادها جت ندارد", "jet" not in CH._FTS_SETUP_LABELS,
   CH._FTS_SETUP_LABELS)
# و همان تاریخچه واقعهٔ شکست دارد، پس نبودنِ مارکر معنا دارد (کنترلِ شکست)
_L = CH.JET_LADDER
_broke = sum(1 for _i in range(1 + max(_L), len(hist))
             if max(float(hist[_i - 1 - _k]["high"]) for _k in _L) < float(hist[_i]["close"])
             and float(hist[_i]["close"]) >= float(hist[_i]["open"]))
ck("کنترل: همین سری چند شکستِ پلکان دارد (%d)" % _broke, _broke > 0, _broke)

# ══════════════ ۶) تریگرِ نقطه‌زنی از لنگرِ کف جداست ══════════════
ph3 = CH._fts_point_hunt(hist, CH._fts_swings(hist, k=CH._FTS_SWING_K))
ck("نقطه‌زنی هر دو تاریخ را منتشر می‌کند",
   "trigger_date" in ph3 and "floor_date" in ph3, sorted(ph3))
ck("بی‌تریگرِ فعال، trigger_date منتشر نمی‌شود (None، نه کندلِ آخر)",
   ph3["trigger_date"] is None or ph3["active"] is True, ph3)
if ph3["active"] is True:
    ck("تریگر رویِ کندلِ آخر است، لنگر رویِ کفِ گذشته",
       ph3["trigger_date"] == str(hist[-1]["time"])[:10]
       and ph3["floor_date"] != ph3["trigger_date"], ph3)

# ══════════════ ۷) taxonomyِ نقش‌ها و وضعیتِ اولویت‌دار ══════════════
fullj = CH._fts_analyze_candles("X", hist)
ck("نقشِ جت = entry و فیبو = context و سقفِ سوم = warning و MA14 = exit",
   fullj["roles"].get("jet") == "entry" and fullj["roles"].get("fib_zone") == "context"
   and fullj["roles"].get("third_peak") == "warning"
   and fullj["roles"].get("ma14_exit") == "exit", fullj["roles"])
ck("وضعیت یکی از کدهایِ اولویت‌دار است",
   fullj["status"]["code"] in CH.FTS_STATUS_PRIORITY, fullj["status"]["code"])
# وتوی هفتگی نباید «تریگرِ ورود» بدهد حتی با جتِ فعال
_o = dict(fullj)
_o["trend"] = {"D": {"trend": "up"}, "W": {"trend": "down"}, "M": {"trend": "up"},
               "alignment": "na", "matrix": {"decision": "REJECT"}}
_o["jet"] = {"active": True, "resistance": 123.0, "reason": None}
_st = CH._fts_status_block(hist, _o)
ck("وتوی هفتگی بر جتِ فعال غالب است", _st["code"] == "weekly_veto", _st["code"])
ck("متنِ وضعیت با وتو «پرواز» نمی‌گوید", "پرواز" not in _st["text"], _st["text"])

'''
t = t[:i] + new_block + t[k + 1:]
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("patched tristate guard")
