import io

p = "dev/fts_chart_engine_v1037.py"
t = io.open(p, encoding="utf-8", newline="").read()

start = t.index("# ---------- ۴) تاریخِ مارکرها")
end = t.index("# ---------- ۵) چارت دیگر موتورِ دوم ندارد ----------")
new = '''# ---------- ۴) تاریخِ مارکرها: عینِ قاعدهٔ پنل، و بی‌جتِ تاریخی ----------
# فیکسچرِ آرواره‌ای: پیوت‌هایِ fractal واقعی می‌سازد و CHoCHِ تاریخی می‌دهد،
# پس آزمون‌هایِ ترتیب/برچسب/ادغام رویِ دادهٔ راست می‌ایستند (فیکسچرِ `up`
# تنها جت می‌ساخت و با حذفِ جت خالی می‌ماند).
def _saw(n_cycles, start_px=200.0, depth=0.9, decay=0.96):
    out, top = [], start_px
    for _c in range(n_cycles):
        for j in range(4):
            out.append(top * (1 + 0.02 * j))
        nxt = top * depth
        for j in range(4):
            out.append(top - (top - nxt) * (j + 1) / 4)
        top = nxt * decay
    return out


_saw_px = _saw(8)
_ceil = max(_saw_px[-10:])
saw_series = series(_saw_px + [_ceil * 1.02, _ceil * 1.035, _ceil * 1.05])
sw_saw = CH._fts_swings(saw_series, k=CH._FTS_SWING_K)
hist = CH._fts_setup_history(saw_series, sw_saw)
by_date = {c["time"]: i for i, c in enumerate(saw_series)}
ck("مارکر می‌شناسد و ستاپ ثبت می‌کند", len(hist) > 0, str(len(hist)))
ck("کنترل: فیکسچر پیوتِ کافی دارد", len(sw_saw) >= 6, str(len(sw_saw)))
ck("هیچ رویدادی بیرون از تاریخچه نیست", all(e["date"] in by_date for e in hist))
ck("رویدادها صعودیِ زمانی‌اند", all(a["date"] <= b["date"] for a, b in zip(hist, hist[1:])))
ck("هیچ رویدادی به آینده نگاه نمی‌کند (همه پیش از کندلِ آخر)",
   all(e["date"] < saw_series[-1]["time"] for e in hist) or not hist)
ck("برچسبِ هر رویداد از جدولِ خودِ موتور است",
   all(e["label"] == CH._FTS_SETUP_LABELS[e["kind"]] for e in hist))

# رأیِ مالک (دورِ J): جت فقط کندلِ آخر است، پس درِ تاریخچه هیچ مارکرِ جت نمی‌شود.
# پینِ این گارد درِ همین دور برگردانده شد (پیش‌تر «مارکرِ جت دارد» را الزام می‌کرد).
_ladder = CH.JET_LADDER
broke = []
for _i in range(1 + max(_ladder), len(saw_series)):
    _res = max(float(saw_series[_i - 1 - _k]["high"]) for _k in _ladder)
    _c = saw_series[_i]
    if _res > 0 and float(_c["close"]) > _res and float(_c["close"]) >= float(_c["open"]):
        broke.append(_i)
ck("کنترل: همین تاریخچه واقعهٔ شکستِ نردبان دارد (آزمونِ نبودِ جت توخالی نیست)",
   len(broke) > 0, f"broke={len(broke)}")
ck("هیچ مارکرِ تاریخی جت ساخته نمی‌شود",
   not [e for e in hist if e["kind"] == "jet"], str(sorted({e["kind"] for e in hist})))
ck("جدولِ برچسبِ ستاپ‌هایِ تاریخی جت ندارد", "jet" not in CH._FTS_SETUP_LABELS)


def _day(s):
    return datetime.date.fromisoformat(s)


for _kind in sorted({e["kind"] for e in hist}):
    _ev = [e for e in hist if e["kind"] == _kind]
    ck(f"رویدادهای زنجیره‌ایِ «{_kind}» ادغام می‌شوند (بی‌برچسبِ تکراریِ روزِ بعد)",
       all((_day(b["date"]) - _day(a["date"])).days != 1 for a, b in zip(_ev, _ev[1:])),
       str([e["date"] for e in _ev][:4]))

'''
t = t[:start] + new + t[end:]
t = t.replace("  • هر مارکرِ جتِ تاریخ‌دار با `_fts_jet_setup` رویِ همان برشِ تاریخچه می‌خواند",
              "  • جت درِ تاریخچه مارکر نمی‌شود (فقط کندلِ آخر)، و هر رویدادِ دیگری از قاعدۀ پنل می‌خواند")
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("patched section 4")
