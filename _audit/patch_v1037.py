import io

p = "dev/fts_chart_engine_v1037.py"
t = io.open(p, encoding="utf-8", newline="").read()

start = t.index("# ---------- ۴) تاریخِ مارکرها")
end = t.index("# ---------- ۵) چارت دیگر موتورِ دوم ندارد ----------")
new = '''# ---------- ۴) تاریخِ مارکرها: عینِ قاعدهٔ پنل، و بی‌جتِ تاریخی ----------
hist = CH._fts_setup_history(up, sw)
by_date = {c["time"]: i for i, c in enumerate(up)}
ck("مارکر می‌شناسد و ستاپ ثبت می‌کند", len(hist) > 0)
ck("هیچ رویدادی بیرون از تاریخچه نیست", all(e["date"] in by_date for e in hist))
ck("رویدادها صعودیِ زمانی‌اند", all(a["date"] <= b["date"] for a, b in zip(hist, hist[1:])))
ck("هیچ رویدادی به آینده نگاه نمی‌کند (همه پیش از کندلِ آخر)",
   all(e["date"] < up[-1]["time"] for e in hist) or not hist)
ck("برچسبِ هر رویداد از جدولِ خودِ موتور است",
   all(e["label"] == CH._FTS_SETUP_LABELS[e["kind"]] for e in hist))

# رأیِ مالک (دورِ J): جت فقط کندلِ آخر است، پس درِ تاریخچه هیچ مارکرِ جت نمی‌شود.
# پینِ این گارد درِ همین دور برگردانده شد (پیش‌تر «مارکرِ جت دارد» را الزام می‌کرد).
_ladder = CH.JET_LADDER
broke = []
for _i in range(1 + max(_ladder), len(up)):
    _res = max(float(up[_i - 1 - _k]["high"]) for _k in _ladder)
    _c = up[_i]
    if _res > 0 and float(_c["close"]) > _res and float(_c["close"]) >= float(_c["open"]):
        broke.append(_i)
ck("کنترل: همین تاریخچه واقعهٔ شکستِ نردبان دارد (آزمونِ بالا توخالی نیست)",
   len(broke) > 0, f"broke={len(broke)}")
ck("هیچ مارکرِ تاریخی جت ساخته نمی‌شود",
   not [e for e in hist if e["kind"] == "jet"], str(sorted({e["kind"] for e in hist})))
ck("جدولِ برچسبِ ستاپ‌هایِ تاریخی جت ندارد", "jet" not in CH._FTS_SETUP_LABELS)


def _day(s):
    return datetime.date.fromisoformat(s)


for kind in sorted({e["kind"] for e in hist}):
    ev = [e for e in hist if e["kind"] == kind]
    ck(f"رویدادهای زنجیره‌ایِ «{kind}» ادغام می‌شوند (بی‌برچسبِ تکراریِ روزِ بعد)",
       all((_day(b["date"]) - _day(a["date"])).days != 1 for a, b in zip(ev, ev[1:])),
       str([e["date"] for e in ev][:4]))

'''
t = t[:start] + new + t[end:]

# پینِ «جت با ۳۰ کندل» در گاردِ سه‌حالگی هنوز درست است؛ اینجا فقط سندِ بالای فایل
t = t.replace("  • هر مارکرِ جتِ تاریخ‌دار با `_fts_jet_setup` رویِ همان برشِ تاریخچه می‌خواند",
              "  • جت درِ تاریخچه مارکر نمی‌شود (فقط کندلِ آخر) و هر رویدادِ دیگری از قاعدۀ پنل می‌خواند")
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("patched v1037")
