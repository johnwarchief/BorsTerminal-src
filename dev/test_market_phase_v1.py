# dev/test_market_phase_v1.py — بند ۵: مرحلِ جلسه از وضعیتِ رسمی، نه از ساعت
"""پنج سناریویِ خواستۀِ مالک با fixture کنترل‌شده (bi‑شبکه، bi‑SQLite):

    پیش از آغاز / آغازِ نشست با دادهٔ کم / معاملات جاری / تعطیل / دادهٔ کهنه

و دو کنترلِ instrument که بی‌آنها هر دروازۀِ کوری سبز می‌ماند:
    • شنبه تعطیل نیست (مرتبۀِ weekdayِ پایتون شنبه را ۵ می‌دهد؛ (4,5) نشستِ
      امروز را تعطیل می‌خواند).
    • درِ «معاملات جاری» با ارزشِ پایین، داوری **واقعاً** نامساعد می‌شود —
      پس دروازۀِ مرحل کور نیست و فقط «بی‌حکم» برنمی‌گرداند.

تستِ مصنوعی اثباتِ منطق است، نه اثباتِ سلامتِ فیدِ زنده؛ سنجشِ زنده درِ
گزارشِ دور جدا آمده است.
"""
import datetime
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import market_phase as MP                       # noqa: E402
import mstat_engine as MS                       # noqa: E402

PASS = FAIL = SKIP = 0


def ck(label, cond, detail=""):
    global PASS, FAIL, SKIP
    if cond is None:
        SKIP += 1
        print(f"  SKIP  {label}")
        return
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


def at(s):
    return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


CLOSED_F = {"official_state": "F", "official_title": "بسته"}

# ── ۱) پیش از آغازِ معاملات ──────────────────────────────────────────────────
pre = MP.resolve(**CLOSED_F, activity_day=20261010, now=at("2026-10-10 08:20:00"))
ck("پیش از آغاز ⇒ pre_open، با منشأِ رسمی",
   pre["phase"] == "pre_open" and pre["official"] is True, pre)
ck("پیش از آغاز ⇒ جریانِ محقق‌شدۀ پول تعریف ندارد",
   pre["computable"]["realized_flow"] is False
   and "realized_flow" in pre["not_computable"], pre["not_computable"])
ck("پیش از آغاز ⇒ جمعِ نشست با آستانۀ تمام‌روز سنجیده نمی‌شود",
   pre["computable"]["session_vs_threshold"] is False, pre["computable"])
ck("پیش از آغاز ⇒ داوری ممنوع (neither مساعد nor نامساعد)",
   pre["verdict_allowed"] is False and pre["is_live"] is False, pre)
ck("پیش از آغاز ⇒ علتِ هر ممنوعیت نوشته شده، نه فقط فهرستِ کلید",
   all(v for v in pre["why_not"].values()), pre["why_not"])

# ── ۲) معاملات جاری (وضعیتِ رسمیِ باز) ───────────────────────────────────────
opn = MP.resolve(official_state="O", official_title="باز", activity_day=20261010,
                 now=at("2026-10-10 10:05:00"))
ck("وضعیتِ رسمیِ باز ⇒ continuous و is_live",
   opn["phase"] == "continuous" and opn["is_live"] is True, opn)
ck("معاملات جاری ⇒ جریانِ پول و پهنای بازار محاسبه‌شدنی‌اند",
   opn["computable"]["realized_flow"] and opn["computable"]["order_pressure"], opn)
ck("معاملات جاری ⇒ قیمتِ پایانی هنوز نهایی نیست",
   opn["computable"]["close_price_final"] is False, opn)

# ── ۳) پایانِ نشست ───────────────────────────────────────────────────────────
end = MP.resolve(**CLOSED_F, activity_day=20261010, now=at("2026-10-10 16:30:00"))
ck("پس از ساعتِ اعلامیِ بازار ⇒ closed، با مرحلِ تمام‌شده داوری‌پذیر",
   end["phase"] == "closed" and end["verdict_allowed"] is True, end)
ck("پایانِ نشست ⇒ صفِ زنده معنا ندارد (دفترِ سفارشِ نشستِ بسته)",
   end["computable"]["order_pressure"] is False, end)
ck("پایانِ نشست ⇒ نشستِ خودش با تاریخِ خودش اعلام می‌شود",
   end["session_day"] == 20261010 and end["is_live"] is False, end)

# ── ۴) تعطیلی ────────────────────────────────────────────────────────────────
hol_fri = MP.resolve(**CLOSED_F, activity_day=20261009, now=at("2026-10-09 10:00:00"))
hol_thu = MP.resolve(**CLOSED_F, activity_day=20261008, now=at("2026-10-08 10:00:00"))
ck("جمعه ⇒ holiday", hol_fri["phase"] == "holiday", hol_fri)
ck("پنجشنبه ⇒ holiday", hol_thu["phase"] == "holiday", hol_thu)
# کنترلِ منفیِ همان تابع: شنبه روزِ معاملاتی است
ck("کنترلِ منفی: شنبه تعطیل نیست",
   MP.is_tehran_weekend(datetime.date(2026, 10, 10)) is False
   and MP.is_tehran_weekend(datetime.date(2026, 10, 9)) is True)
sat = MP.resolve(**CLOSED_F, activity_day=20261010, now=at("2026-10-10 16:30:00"))
ck("کنترلِ منفی: شنبۀِ پس از نشست ⇒ holiday نمی‌شود", sat["phase"] != "holiday", sat)

# ── ۵) دادهٔ کهنه / بی‌وضعیتِ رسمی ───────────────────────────────────────────
stale = MP.resolve(activity_day=None, board_day=20261007, now=at("2026-10-12 10:00:00"))
ck("بی‌وضعیتِ رسمی و تابلویِ کهنه ⇒ unknown (نه «باز»، نه «بسته»)",
   stale["phase"] == "unknown" and stale["verdict_allowed"] is False, stale)
ck("بی‌وضعیتِ رسمی ⇒ official false و منشأ اعلام می‌شود",
   stale["official"] is False and stale["phase_source"] in ("none", "calendar"), stale)
inside = MP.resolve(board_day=20261010, now=at("2026-10-10 10:00:00"))
ck("ساعت داخلِ پنجره ولی بی‌وضعیتِ رسمی ⇒ باز ادعا نمی‌شود",
   inside["phase"] == "unknown", inside)
unmapped = MP.resolve(official_state="Q", activity_day=20261010,
                      now=at("2026-10-10 10:00:00"))
ck("حرفِ نا‌شناختهٔ رسمی ⇒ unknown با برچسبِ unmapped (ترجمۀِ حدسی نه)",
   unmapped["phase"] == "unknown"
   and unmapped["phase_source"] == "tsetmc_marketState_unmapped"
   and unmapped["official_state"] == "Q", unmapped)
midclosed = MP.resolve(**CLOSED_F, activity_day=20261010, now=at("2026-10-10 10:00:00"))
ck("«بسته» در میانهٔ پنجره ⇒ مرحلِ تازه اختراع نمی‌شود، unknown می‌ماند",
   midclosed["phase"] == "unknown", midclosed)

# ── دروازۀِ داوری درِ خودِ برچسبِ سلامت ───────────────────────────────────────
EQ_EMPTY = {"n_traded": 0, "val_hemat": 0.0}
EQ_LOW = {"n_traded": 900, "val_hemat": 3.0}          # ۳ همت — زیرِ HEMAT_BAD
EQ_HIGH = {"n_traded": 1200, "val_hemat": 40.0}
h_pre = MS.macro_health_from(EQ_EMPTY, None, 0.0, "", phase=pre)
ck("پیش از آغاز با صفِ خالی ⇒ «بدون داده»، نه «نامساعد/رکود»",
   h_pre["state"] == "nodata" and "نامساعد" not in (h_pre["label"] or ""), h_pre)
h_low_pre = MS.macro_health_from(EQ_LOW, None, 0.0, "", phase=pre)
ck("پیش از آغاز با ارزشِ پایین ⇒ همان «بدون داده» (نبودِ داده منفی نیست)",
   h_low_pre["state"] == "nodata", h_low_pre)
h_cont = MS.macro_health_from(EQ_LOW, None, 0.0, "", phase=opn)
ck("کنترلِ instrument: درِ معاملات جاری همان عدد ⇒ نامساعد (دروازه کور نیست)",
   h_cont["state"] == "bad" and h_cont["label"] == "نامساعد", h_cont)
h_good = MS.macro_health_from(EQ_HIGH, None, 0.0, "", phase=opn)
ck("کنترلِ instrument: درِ معاملات جاری عددِ بالا ⇒ مساعد",
   h_good["state"] == "good", h_good)
h_closed = MS.macro_health_from(EQ_LOW, None, 0.0, "", phase=end)
ck("نشستِ بسته داوری می‌شود (با تاریخِ خودش، نه به‌عنوان زنده)",
   h_closed["state"] == "bad" and h_closed.get("phase") == "closed", h_closed)
h_none = MS.macro_health_from(EQ_EMPTY, None, 0.0, "")
ck("بی‌مرحل (فراخوانِ قدیمی) ⇒ همان رفتارِ پیشین، نه کرش",
   h_none["state"] == "nodata", h_none)

# ── بی‌آستانه‌سازیِ اختراعی ───────────────────────────────────────────────────
src = io.open(os.path.join(ROOT, "market_phase.py"), encoding="utf-8").read()
nums = set(re.findall(r"=\s*([0-9]+(?:\.[0-9]+)?)", src))
allowed = {"9", "0", "12", "30", "3", "4", "100", "10000", "2026", "1", "2"}
ck("درِ market_phase عددِ تازۀِ آستانه‌ای نیست (جز مرزهایِ اعلامی و قالبِ تاریخ)",
   all(float(n) in {float(a) for a in allowed} for n in nums), sorted(nums - allowed))
# فقط کدِ خالص سنجیده می‌شود: توضیحِ فارسیِ فایل عمداً نامِ آستانه‌هایِ سندِ FTS
# را می‌برد تا بگوید آن‌ها را از اینجا صدا نمی‌زند.
code = chr(10).join(l for l in src.split(chr(10)) if not l.strip().startswith("#"))
ck("لایۀِ مرحل هیچ واژگانِ حکمی ندارد (مساعد/نامساعد/آستانه درِ کدش نیست)",
   '"good"' not in code and '"bad"' not in code
   and "import mstat_engine" not in code and "HEMAT_GOOD =" not in code,
   [w for w in ('"good"', '"bad"', "import mstat_engine", "HEMAT_GOOD =") if w in code])
ck("هر پنج مرحل برچسب و جدولِ محاسبه‌پذیری دارد",
   all(p in MP.LABEL and p in MP.COMPUTABLE for p in MP.PHASES), MP.PHASES)
ck("ازِ هر مرحل زیرمجموعۀِ PHASES است (کلیدِ ناشناخته نمی‌افتد)",
   set(MP.COMPUTABLE) == set(MP.PHASES) and set(MP.LABEL) == set(MP.PHASES))

print("─" * 72)
print(f"نتیجۀِ گاردِ مرحلِ جلسه: {PASS}_pass / {FAIL}_fail / {SKIP}_skip")
sys.exit(1 if FAIL else 0)
