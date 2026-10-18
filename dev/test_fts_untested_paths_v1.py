# -*- coding: utf-8 -*-
"""گاردِ سه مسارِ بی‌آزمونِ موتورِ اول — مرحلۀ ۳ دورِ تطبیقِ دوم.

ممیزیِ ارجاع‌ها (`dev/test_rule_map_citations.py`) کهنه‌هایِ سند را دید؛ این
سوئیت رفتارِ سه تابعِ موتورِ اول را می‌سنجد که پیش از این هیچ آزمونِ مستقیمی
نداشتند (grep در `dev/`، `_audit/` و `frontend/src/__tests__`: صفر ارجاع):

  الف) `_fts_pullback_setup` — شاخۀ پولبکِ روند صعودی (جزوه ص۸-۹؛ چارت ص۲:
     صعودی → جت یا پولبک). سه‌حالته: بی‌داده ≠ سنجیده‌شدن ≠ ستاپ نیست.
  ب) `_swing_extremes` + `_merge_levels` + `_key_levels_from_history` +
     `_order_blocks` — مسیرِ زندۀ `/api/chart/{symbol}/key-levels`؛ تبِ مستر از
     همین «مقاومت/حمایت» و بجِ ستونِ الگو را می‌سازد (`useKeyLevels.ts`).
  پ) `_fts_structure_points` — برچسب‌های HH/HL/LH/LL که لایۀ «ساختار روند»
     روی چارت رسم می‌کند (`structure_points.D`).

سنجه‌های این فایل (چهار شرطِ هشت‌گانۀ مرحلۀ ۳): تطابقِ قاعدۀ مرجع، سه‌حالتهٔ
بی‌داده/در-حال-تشکیل، بی‌دادهٔ آینده با پیشوند-پایداری، و درستِ ورودی
(پیوت‌ها از خودِ `_fts_swings` می‌آیند نه از فهرستِ دست‌نویس). دو شرطِ دیگر
(مصرفِ همان نماد+TF و رسمِ درست) در سندِ مرحلۀ ۳ با شاهدِ فایل:سطر ثبت‌اند و
در browser-evidence مرحلۀ ۵ راستی‌آزمایی می‌شوند.

اجرا:  python dev/test_fts_untested_paths_v1.py     (بی‌شبکه، بی‌market.db)
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from api import chart as CH  # noqa: E402

RES = []
K = CH._FTS_SWING_K


def ck(name, cond, got=""):
    RES.append((name if cond else "✗ " + name, bool(cond), "" if cond else repr(got)))


def bars(vals, start="2024-03-02"):
    """vals = [(high, low, open, close)] → کندلِ صعودیِ تاریخ‌دارِ ISO."""
    d0 = dt.date.fromisoformat(start)
    return [{"time": (d0 + dt.timedelta(days=i)).isoformat(),
             "open": v[2], "high": v[0], "low": v[1], "close": v[3]}
            for i, v in enumerate(vals)]


def zig(pivots, leg=5, start="2024-03-02"):
    """سریِ کندل از پیوت‌های هدف؛ هر پیوت دقیقاً روی سطرِ مضربِ `leg` می‌نشیند.

    `leg` باید دست‌کم `K+2` باشد تا پنجرۀ fractal دو پیوتِ پشت‌سرهم را نبیند.
    """
    assert leg >= K + 2, "پنجرهٔ پیوت با بازه‌ها قاتی می‌کند"
    d0 = dt.date.fromisoformat(start)
    vals = [pivots[0]]
    for a, b in zip(pivots, pivots[1:]):
        vals += [a + (b - a) * i / leg for i in range(1, leg + 1)]
    return [{"time": (d0 + dt.timedelta(days=i)).isoformat(),
             "open": p, "high": p * 1.001, "low": p * 0.999, "close": p}
            for i, p in enumerate(vals)]


def swing(kind, idx, price, k=K):
    """یک پیوتِ تأییدشده به‌شکلِ قراردادِ `_fts_swings`."""
    d0 = dt.date(2024, 5, 1)
    return {"kind": kind, "idx": idx, "price": price,
            "time": (d0 + dt.timedelta(days=idx)).isoformat(),
            "confirm_idx": idx + k,
            "confirm_time": (d0 + dt.timedelta(days=idx + k)).isoformat()}


# ──────────────────────────── الف) پولبک ─────────────────────────────────
# سقفِ تأییدشده در سطرِ ۶ (=۱۵.۰۰۰)؛ سطرهای ۷..۱۰ پایین‌تر؛ سطرِ ۱۱ سرنوشتِ ستاپ.
PB_BASE = [
    (101, 99, 100, 101), (103, 101, 101, 103), (105, 103, 103, 105), (107, 105, 105, 107),
    (109, 107, 107, 109), (111, 109, 109, 111), (115, 112, 111, 115),
    (112, 110, 112, 111), (111, 109, 111, 110), (110, 108, 110, 109),
    (109, 107, 109, 108),
]
LEVEL = 115.0


def pb(last, trend="up", weekly=None, series=None):
    c = bars(PB_BASE + [last])
    sw = CH._fts_swings(c, k=K) if series is None else series
    return CH._fts_pullback_setup(c, sw, trend, weekly_trend=weekly), c, sw


# ورودیِ درست: خودِ `_fts_swings` باید سقفِ ۶ را بدهد، وگرنه تستِ بی‌معنا می‌شود
_, c_in, sw_in = pb((108, 106, 108, 107))
hp = [s for s in sw_in if s["kind"] == "high"]
ck("ورودی: پیوت‌سازِ واقعی، یک سقفِ تأییدشده در سطرِ ۶ می‌دهد",
   len(hp) == 1 and hp[0]["idx"] == 6 and hp[0]["price"] == LEVEL,
   [(s["kind"], s["idx"], s["price"]) for s in sw_in])

r_ok, c_ok, _ = pb((116.5, 114.5, 114.6, 116.5))
ck("پولبکِ تأییدشده: لمسِ سطح + پایانی بالای سطح با بدنهٔ صعودی",
   r_ok["active"] is True and r_ok["touching"] is True, r_ok)
ck("سطحِ پولبک = آخرین سقفِ شکسته‌شده (جزوه ص۸)", r_ok["level"] == LEVEL, r_ok["level"])
ck("زمانِ سطح، سطرِ خودِ پیوت است نه سطرِ امروز",
   r_ok["level_date"] == c_ok[6]["time"][:10], r_ok["level_date"])
ck("سنِ سطح یعنی وقوع از تأیید جداست (anti-repaint)",
   r_ok["level_age_bars"] == len(c_ok) - 1 - 6 and r_ok["level_age_bars"] >= 1,
   r_ok["level_age_bars"])

r_form, _, _ = pb((112.0, 114.5, 115.4, 114.0))
ck("لمسِ بی‌بازگشت ⇒ «در حال تشکیل» (null ≠ false ≠ ستاپ نیست)",
   r_form["touching"] is True and r_form["active"] is False
   and "حال تشکیل" in (r_form["reason"] or ""), r_form)

r_far, _, _ = pb((132, 130, 131, 132))
ck("بی‌لمس ⇒ سنجیده شد و ستاپ نیست، با فاصلۀ عددی",
   r_far["touching"] is False and r_far["active"] is False
   and r_far["gap_pct"] is not None and r_far["gap_pct"] > 0, r_far)

r_na, _, _ = pb((116.5, 114.5, 114.6, 116.5), trend="na")
ck("روندِ سنجیده‌نشده ⇒ رأی نمی‌دهد (active/touching صفرِ معتبر نیست)",
   r_na["active"] is None and r_na["touching"] is None
   and "ارزیابی نشد" in (r_na["reason"] or ""), r_na)

r_none, _, _ = pb((116.5, 114.5, 114.6, 116.5), trend=None)
ck("روندِ بی‌فیلد هم «سنجیده نشد» است نه «ستاپ نیست»",
   r_none["active"] is None, r_none)

r_dn, _, _ = pb((116.5, 114.5, 114.6, 116.5), trend="down")
ck("روندِ نزولی ⇒ شاخۀ پولبک بسته است، ولی داوریِ سنجیده‌شده (False)",
   r_dn["active"] is False and r_dn["level"] is None, r_dn)

r_range, _, _ = pb((116.5, 114.5, 114.6, 116.5), trend="range")
ck("روندِ خنثی هم پولبک نمی‌سنجد (چارت ص۲: خنثی → کف دوقلو/آخرین کف)",
   r_range["active"] is False, r_range)

flat = bars([(100, 99, 100, 100)] * 14)
ck("سقفِ تأییدشدهٔ بی‌سابقه ⇒ بی‌داده با علت، نه صفر",
   CH._fts_pullback_setup(flat, CH._fts_swings(flat, k=K), "up")["active"] is None,
   CH._fts_pullback_setup(flat, CH._fts_swings(flat, k=K), "up"))

# قاعدۀ اکیدِ خودِ `_fts_swings` (docstring: «و اکیداً بزرگ‌تر از یک طرف»):
# کندلِ تک‌قیمتیِ TSETMC (H==L با حجمِ میلیاردی؛ فولاد ۱۲۷۸ سطر از ۴۲۴۲) نباید
# «سقف تأییدشده» بسازد، و سرهایِ یک فلات باید بمانند (فقط میانی حذف شود).
ck("سریِ تخت ⇒ هیچ پیوتی (بی‌ساختار ≠ ساختارِ پر از پیوتِ بی‌معنا)",
   CH._fts_swings(flat, k=K) == [], CH._fts_swings(flat, k=K))
plat = bars([(v, v - 2, v - 1, v) for v in
             (100, 105, 110, 115, 120, 120, 120, 115, 110, 105, 100, 95, 90, 85, 80)])
ph = [s["idx"] for s in CH._fts_swings(plat, k=K) if s["kind"] == "high"]
ck("فلاتِ سه‌کندلی ⇒ فقط دو سرِ آن پیوت است (اکیداً یک طرف، برابرِ طرف دیگر)",
   ph == [4, 6], ph)

only_lows = [swing("low", 4, 90.0), swing("low", 9, 92.0)]
ck("پیوتِ فقط‌کف ⇒ پولبک ارزیابی‌نشده می‌ماند",
   CH._fts_pullback_setup(bars(PB_BASE + [(116.5, 114.5, 114.6, 116.5)]),
                          only_lows, "up")["active"] is None)

today_top = [swing("high", 11, LEVEL)]
ck("سقفِ امروز ⇒ «پولبک بعد از سقف سنجیده می‌شود»، نه ستاپ",
   "خودِ کندلِ امروز" in (CH._fts_pullback_setup(
      bars(PB_BASE + [(116.5, 114.5, 114.6, 116.5)]), today_top, "up")["reason"] or ""))

ck("هفتگیِ صعودی زمینه می‌کند، فعال نمی‌کند",
   pb((116.5, 114.5, 114.6, 116.5), weekly="up")[0]["weekly_confirms"] is True
   and pb((116.5, 114.5, 114.6, 116.5), weekly="down")[0]["weekly_confirms"] is False
   and pb((116.5, 114.5, 114.6, 116.5))[0]["weekly_confirms"] is None)

# بی‌دادهٔ آینده: پیوت‌هایِ پیشوند،subsetِ پیوت‌هایِ سریِ کامل با همین عدد می‌مانند
full = bars(PB_BASE + [(116.5, 114.5, 114.6, 116.5), (150, 140, 141, 149),
                       (160, 150, 151, 159), (170, 160, 161, 169)])
cut = 13
sw_full = CH._fts_swings(full, k=K)
sw_pre = CH._fts_swings(full[:cut], k=K)
ck("پیشوند-پایداریِ پیوت‌ها (دادهٔ بعدِ برش رأیِ پولبک را جابهجا نمی‌کند)",
   [s["idx"] for s in sw_pre] == [s["idx"] for s in sw_full if s["confirm_idx"] < cut],
   ([s["idx"] for s in sw_pre], [(s["idx"], s["confirm_idx"]) for s in sw_full]))
ck("سطحِ پولبکِ برش‌خورده با سطحِ همان seriesِ کامل یکی است",
   CH._fts_pullback_setup(full[:cut], sw_pre, "up")["level"] == LEVEL,
   CH._fts_pullback_setup(full[:cut], sw_pre, "up")["level"])

# ──────────────── ب) سطوح کلیدی (key-levels) ─────────────────────────────
def rows(prices, vol=1000, start="2024-03-02", dirs=None):
    """prices = [(high, low)] → سطرِ key-levels؛ `dirs[i]='d'` بدنۀ نزولی (بلاکِ تقاضا)."""
    d0 = dt.date.fromisoformat(start)
    out = []
    for i, (h, l) in enumerate(prices):
        down = bool(dirs) and i < len(dirs) and dirs[i] == "d"
        o, c = ((h + l) * 0.5 + (h - l) * 0.1, l + (h - l) * 0.3) if down else \
               (l + (h - l) * 0.4, l + (h - l) * 0.6)
        out.append({"date": (d0 + dt.timedelta(days=i)).isoformat(),
                    "open": o, "high": h, "low": l, "close": c, "volume": vol})
    return out


# دو دندۀ سقف (high=200) و دو دندۀ کف (low=90)؛ کف‌ها با بدنۀ نزولی (تقاضا)
KL_SPEC = [(150, 140), (160, 150), (170, 160), (200, 170), (200, 170),
           (180, 160), (160, 140), (140, 120), (100, 90), (100, 90),
           (120, 100), (140, 120), (160, 150), (170, 160), (180, 170)]
KL_DIRS = [""] * 8 + ["d", "d"] + [""] * 5
KL = rows(KL_SPEC, dirs=KL_DIRS)
ext = CH._swing_extremes(KL)
ck("swing-extremes هر دو جنس را از خودِ_series_ می‌گیرد (سقف=high، کف=low)",
   {e["kind"] for e in ext} == {"high", "low"} and
   {e["price"] for e in ext if e["kind"] == "high"} == {200} and
   {e["price"] for e in ext if e["kind"] == "low"} == {90}, ext)
ck("فلاتِ دودندۀ یک‌قیمت دو سطرِ جدا می‌دهد (ادغام کارِ _merge_levels است)",
   [e["idx"] for e in ext if e["kind"] == "high"] == [3, 4] and
   [e["idx"] for e in ext if e["kind"] == "low"] == [8, 9], ext)
ck("هیچ سطحی از k کندلِ آخر نمی‌آید (پیوتِ نرسیده = repaint)",
   all(e["idx"] <= len(KL) - K - 1 for e in ext),
   [(e["idx"], len(KL) - K - 1) for e in ext])
ck("تاریخچۀ کم‌تر از ۲k+۱ ⇒ فهرستِ خالی، نه حدس",
   CH._swing_extremes(KL[:2 * K]) == [], len(CH._swing_extremes(KL[:2 * K])))

for m in (10, 11, 12, 13, 14):
    pre = CH._swing_extremes(KL[:m])
    same = [e for e in ext if e["idx"] <= m - K - 1]
    if pre != same:
        ck(f"پیشوند-پایداریِ سطوح در برشِ {m}", False, (pre, same))
        break
else:
    ck("پیشوند-پایداریِ سطوح (همان سطح با همان عدد، بی‌دیدنِ آینده)", True)

near = rows([(150, 140), (160, 150), (170, 160), (200.0, 190), (200.4, 190),
             (180, 170), (160, 150), (140, 130), (100, 90), (100.3, 90),
             (120, 110), (140, 130), (160, 150), (170, 160), (180, 170)])
merged = CH._merge_levels(CH._swing_extremes(near))
hi_prices = sorted({round(e["price"], 1) for e in merged if e["kind"] == "high"})
ck("ادغامِ سطوحِ نزدیک (۰٫۸٪) دو دندۀ چسبیده را یک سطح می‌کند",
   len([e for e in merged if e["kind"] == "high"]) == len(hi_prices), (merged, hi_prices))

kl = CH._key_levels_from_history(KL)
ck("سطحِ خالیِ بی‌تاریخچه ⇒ سه‌کلیدِ خالی، نه None",
   CH._key_levels_from_history([]) == {"levels": [], "blocks": [], "count": 0})
ck("حداکثر سه مقاومت و سه حمایت (قاعدهٔ شلوغ‌نشدنِ چارت)",
   len([e for e in kl["levels"] if e["kind"] == "high"]) <= 3 and
   len([e for e in kl["levels"] if e["kind"] == "low"]) <= 3, kl["levels"])
def level_matches(lv):
    """سطحِ منتشرشده باید سطرِ خودِ یک پیوتِ همان جنس/همان قیمت را ببرد."""
    return any(e["kind"] == lv["kind"] and abs(e["price"] - lv["price"]) <= 0.5
               and KL[e["idx"]]["date"] == lv["date"] for e in ext)


ck("تاریخِ هر سطح، سطرِ خودِ پیوت است (نه امروز) و قیمتِ گردشدۀ آن",
   bool(kl["levels"]) and all(level_matches(lv) for lv in kl["levels"]) and
   all(lv["date"] != KL[-1]["date"] for lv in kl["levels"]), kl["levels"])
ck("count با شمارِ سطوح+بلوک‌ها می‌خواند",
   kl["count"] == len(kl["levels"]) + len(kl["blocks"]), kl)
ck("سطوح نزولیِ زمانی‌اند (تازه‌ترین اول برای UI)",
   [lv["date"] for lv in kl["levels"]] == sorted((lv["date"] for lv in kl["levels"]),
                                                 reverse=True), kl["levels"])

# order blocks: بلاک فقط روی پیوتی ساخته می‌شود که هم حجمش ≥ ۱٫۵× میانگین باشد
# و هم بدنۀ هم‌جهت با جنسِ پیوت داشته باشد (تقاضا = کندلِ نزولی روی کف).
# حجمِ یکنواخت هرگز بلاک نمی‌سازد (۱٫۵× میانگین = خودش)؛ این هم یک سنجه است.
KL_VOL = dict.fromkeys((3, 4, 8, 9), 9000)
KLr = [{**r, "volume": KL_VOL.get(i, 1000)} for i, r in enumerate(KL)]
blocks = CH._order_blocks(KLr, CH._swing_extremes(KLr))
ck("حجمِ بالا + بدنۀ نزولی رویِ کف ⇒ بلاکِ تقاضا",
   any(b["type"] == "demand" for b in blocks), blocks)
ck("حجمِ بالا + بدنۀ صعودی رویِ سقف ⇒ بلاکِ عرضه",
   any(b["type"] == "supply" for b in blocks), blocks)


def window_box(rows_, idx, lookback=2):
    w = rows_[max(0, idx - lookback): min(len(rows_), idx + lookback + 1)]
    return min(x["low"] for x in w), max(x["high"] for x in w)


ck("مستطیلِ بلاک = پنجرۀ ±۲ کندلِ یک پیوتِ هم‌جنس (نه بازۀ دلخواه)",
   blocks and all(any((b["type"] == "demand") == (e["kind"] == "low")
                      and window_box(KLr, e["idx"]) == (b["bottom"], b["top"])
                      and b["time_start"] == KLr[max(0, e["idx"] - 2)]["date"]
                      and b["time_end"] == KLr[min(len(KLr) - 1, e["idx"] + 2)]["date"]
                      for e in CH._swing_extremes(KLr)) for b in blocks), blocks)
ck("بلاکِ صعودیِ محض ⇒ تقاضا ندارد (بدنۀ نزولی شرطِ تقاضاست)",
   [b for b in CH._order_blocks(
       [{**r, "volume": KL_VOL.get(i, 1000)} for i, r in enumerate(rows(KL_SPEC))],
       CH._swing_extremes(rows(KL_SPEC))) if b["type"] == "demand"] == [])
ck("بلاکِ نزولیِ محض ⇒ عرضه ندارد (بدنۀ صعودی شرطِ عرضۀ)",
   [b for b in CH._order_blocks(
       [{**r, "volume": KL_VOL.get(i, 1000)} for i, r in enumerate(
           rows(KL_SPEC, dirs=["d"] * 15))],
       CH._swing_extremes(rows(KL_SPEC, dirs=["d"] * 15)))
    if b["type"] == "supply"] == [])
ck("حجمِ یکنواخت ⇒ هیچ بلاکی (رشدِ حجم شرط است، نه پیش‌فرض)",
   CH._order_blocks(KL, ext) == [], CH._order_blocks(KL, ext))
ck("بی‌رشدِ حجم ⇒ هیچ بلاکی ساخته نمی‌شود",
   CH._order_blocks(rows([(150, 140)] * 15, vol=10), CH._swing_extremes(
       rows([(150, 140)] * 15, vol=10))) == [])
ck("بلاکِ بی‌پیوت ⇒ فهرستِ خالی", CH._order_blocks(KLr, []) == [])
ck("حداکثر سه بلاک (keep=3)", len(blocks) <= 3, blocks)

# ──────────────── پ) نقاطِ ساختاری (HH/HL/LH/LL) ─────────────────────────
seq = [swing("high", 3, 100.0), swing("low", 6, 100.0),
       swing("high", 9, 100.2), swing("low", 12, 100.3),
       swing("high", 15, 110.0), swing("low", 18, 105.0),
       swing("high", 21, 95.0), swing("low", 24, 90.0)]
pts = CH._fts_structure_points(seq)
lab = [(p["kind"], p["label"]) for p in pts]
ck("نخستین سقف/کفِ بی‌سابقه با «مقایسه‌شده» جا نمی‌زند (H/L خالص)",
   lab[0] == ("high", "H") and lab[1] == ("low", "L"), lab[:2])
ck("اختلافِ زیرِ تلورانسِ مساوی ⇒ HE/LE، نه HH/HL (جهتِ ساختگی نه)",
   lab[2] == ("high", "HE") and lab[3] == ("low", "LE"), lab[2:4])
ck("سقفِ بالاتر ⇒ HH و کفِ بالاتر ⇒ HL (جزوه ص۷)",
   lab[4] == ("high", "HH") and lab[5] == ("low", "HL"), lab[4:6])
ck("سقفِ پایین‌تر ⇒ LH و کفِ پایین‌تر ⇒ LL",
   lab[6] == ("high", "LH") and lab[7] == ("low", "LL"), lab[6:8])
ck("مرجعِ هر برچسب، هم‌جنسِ پیشینِ خودِ اوست (نه نزدیک‌ترین کندل)",
   pts[4]["ref_price"] == 100.2 and pts[5]["ref_price"] == 100.3
   and pts[6]["ref_price"] == 110.0, [pts[i]["ref_price"] for i in (4, 5, 6)])
ck("نخستین‌هایِ هر جنس مرجع ندارند", pts[0]["ref_price"] is None
   and pts[0]["ref_time"] is None, pts[0])
ck("زمانِ وقوع از زمانِ تأیید جدا منتشر می‌شود",
   all(p["confirm_idx"] == p["idx"] + K and p["confirm_time"] > p["time"] for p in pts),
   [(p["idx"], p["confirm_idx"]) for p in pts])
ck("ردیفِ خالی ⇒ فهرستِ خالی", CH._fts_structure_points([]) == [])

many = [swing("high", 3 + 3 * i, 100.0 + i) for i in range(20)]
lim = CH._fts_structure_points(many)
ck("سقفِ رسمِ نقاط (۱۴) با حفظِ ترتیبِ زمانی",
   len(lim) == 14 and lim[-1]["price"] == 119.0 and lim[0]["price"] == 106.0,
   (len(lim), lim[0]["price"], lim[-1]["price"]))
ck("limitِ بزرگ‌تر از موجود، همه را می‌دهد",
   len(CH._fts_structure_points(many, limit=99)) == 20)

# تطبیقِ متقابل: همان برچسب‌ها رأیِ روندِ موتورِ اول را می‌سازند
up_s = CH._fts_swings(zig([100, 110, 102, 115, 104, 118]), k=K)
dn_s = CH._fts_swings(zig([100, 110, 90, 105, 80, 95]), k=K)
fl_s = CH._fts_swings(zig([100, 110, 100, 110, 100, 110]), k=K)
ck("ساختارِ صعودیِ واقعی ⇒ HH+HL و رأیِ up",
   {p["label"] for p in CH._fts_structure_points(up_s)} >= {"HH", "HL"} and
   CH._fts_classify_trend(up_s, series=zig([100, 110, 102, 115, 104, 118]))["trend"] == "up",
   ([(p["label"]) for p in CH._fts_structure_points(up_s)],
    CH._fts_classify_trend(up_s, series=zig([100, 110, 102, 115, 104, 118]))["trend"]))
ck("ساختارِ نزولیِ واقعی ⇒ LH+LL و رأیِ down",
   {p["label"] for p in CH._fts_structure_points(dn_s)} >= {"LH", "LL"} and
   CH._fts_classify_trend(dn_s, series=zig([100, 110, 90, 105, 80, 95]))["trend"] == "down",
   ([(p["label"]) for p in CH._fts_structure_points(dn_s)],
    CH._fts_classify_trend(dn_s, series=zig([100, 110, 90, 105, 80, 95]))["trend"]))
ck("ساختارِ بی‌جهت ⇒ HE/LE و رأیِ نزولی/صعودی نمی‌دهد",
   {p["label"] for p in CH._fts_structure_points(fl_s)} <= {"H", "L", "HE", "LE"} and
   CH._fts_classify_trend(fl_s, series=zig([100, 110, 100, 110, 100, 110]))["trend"]
   in ("range", "na"),
   [(p["label"]) for p in CH._fts_structure_points(fl_s)])

fails = [n for n, ok_, _ in RES if not ok_]
for n, ok_, extra in RES:
    print(f"  {'PASS' if ok_ else 'FAIL'}  {n}{'  <<< ' + str(extra) if not ok_ else ''}")
print(f"\n{len(RES) - len(fails)}/{len(RES)} passed")
sys.exit(1 if fails else 0)
