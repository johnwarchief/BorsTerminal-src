# -*- coding: utf-8 -*-
"""§۹ سندِ دورِ I را با نتایجِ walk-forward و regime دورِ J می‌سازد.

رقم‌ها همه از JSON می‌آیند (N/D/P)؛ هیچ عددی درِ این فایل تایپ نشده — قاعدۀ
مخزن: Write/Editِ فارسی رقم را بی‌صدا می‌دزدد.
اجرا: PYTHONIOENCODING=utf-8 py -3.14 _audit/append_lab_roundj.py
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "fts-notes", "TECHNICAL-ENGINE-SIGNAL-LAB.md")
SRC = "_audit/fts_lab_roundj_walkforward.json"
MARK = "## \u06f9) دورِ J"

PCT = "\u066a"


def N(x, sep=False):
    s = ("{:,}".format(int(x))) if sep else str(int(x))
    return "".join("\u066c" if c == "," else chr(0x06F0 + int(c)) for c in s if c.isdigit() or c == ",")


def D(x, digits=3):
    return "".join("\u066b" if c == "." else chr(0x06F0 + int(c)) for c in ("%.*f" % (digits, x)))


def P(x):
    return D(x * 100, 1) + PCT


d = json.load(io.open(os.path.join(ROOT, SRC), encoding="utf-8"))
jet = d["jet"]
base = jet["base_rate"]["win"]

CUR = {"jet": "ladder_current", "choch": "current_1d", "hunt": "channel_current",
       "dbl": "confirm_2d", "fib": "weekly_up_618_70_log"}
CHOSEN = {"jet": "static_ceiling_250", "choch": "confirm_2d_margin1",
          "hunt": "channel_bounce", "dbl": "current", "fib": "ungated_618_70_log"}
SIG_FA = {
    "jet": "\u062c\u062a",
    "choch": "CHoCH",
    "hunt": "\u0646\u0642\u0637\u0647\u200c\u0632\u0646\u06cc",
    "dbl": "\u062f\u0627\u0628\u0644\u200c\u0628\u0627\u062a\u0645",
    "fib": "\u0641\u06cc\u0628\u0648",
}
RULE_FA = {
    ("jet", "static_ceiling_250"): "\u0633\u0642\u0641\u0650 \u0627\u06cc\u0633\u062a\u0627\u062f\u0647 " + N(250),
    ("jet", "ladder_current"): "\u067e\u0644\u06a9\u0627\u0646",
    ("choch", "confirm_2d_margin1"): "\u062f\u0648\u0631\u0648\u0632\u0647 + \u062d\u0627\u0634\u06cc\u0647 " + N(1) + PCT,
    ("choch", "current_1d"): "\u06cc\u06a9\u200c\u0631\u0648\u0632\u0647",
    ("hunt", "channel_bounce"): "\u0644\u0645\u0633 + \u0631\u06cc\u0628\u0627\u0646\u062f",
    ("hunt", "channel_current"): "\u0644\u0645\u0633\u0650 \u062a\u0646\u0647\u0627",
    ("dbl", "current"): "\u062a\u0631\u06cc\u06af\u0631\u0650 \u06cc\u06a9\u200c\u0628\u0633\u062a\u0647",
    ("dbl", "confirm_2d"): "\u062a\u062b\u0628\u06cc\u062a\u0650 \u062f\u0648\u0631\u0648\u0632\u0647",
    ("fib", "ungated_618_70_log"): "\u0628\u06cc\u200c\u06af\u06cc\u062a",
    ("fib", "weekly_up_618_70_log"): "\u0628\u0627 \u06af\u06cc\u062a\u0650 \u0647\u0641\u062a\u06af\u06cc",
}


def folds(vs, name):
    fp = vs[name].get("fold_precision") or []
    return " / ".join(D(v) for v in fp) if fp else "\u2014"


def regimes(vs, name):
    rg = vs[name].get("by_regime") or {}
    keys = ("bull", "range", "bear")
    return " / ".join((D(rg[k]["win"]) + " (" + N(rg[k]["n"]) + ")") if k in rg else "\u2014"
                      for k in keys)


L = []
A = L.append
A("")
A(MARK + ": walk-forward، regime، و three-state کردنِ لایه‌های خروج")
A("")
A("پنلِ همین اجرا: " + N(jet["symbols"]) + " نماد / " + N(jet["bars_evaluated"], True)
  + " کندل، " + N(jet["folds"]) + " قطعهٔ زمانیِ متوالی (بیرونِ نمونه)، نرخِ پایه "
  + D(base) + ". ستون «قطعه‌ها» دقتِ همان قاعده در هر قطعه است؛ قطعه‌هایی که کمتر از "
  + N(20) + " بستۀ معتبر دارند شمرده نمی‌شوند (برایِ همین سقفِ ایستاده در دو قطعهٔ "
    "نخست آتش ندارد: به " + N(250) + " کندل پیش‌نیاز نیاز دارد).")
A("")
A("| سیگنال | قاعدۀ ردشده | دقت | قطعه‌ها | قاعدۀ برگزیده | دقت | قطعه‌ها | regime: صعودی / خنثی / نزولی |")
A("|---|---|---|---|---|---|---|---|")
for sig in ("jet", "choch", "hunt", "dbl", "fib"):
    vs = d[sig]["variants"]
    cur, ch = CUR[sig], CHOSEN[sig]
    A("| " + SIG_FA[sig] + " | " + RULE_FA[(sig, cur)] + " | " + D(vs[cur]["precision"])
      + " | " + folds(vs, cur) + " | " + RULE_FA[(sig, ch)] + " | " + D(vs[ch]["precision"])
      + " | " + folds(vs, ch) + " | " + regimes(vs, ch) + " |")
A("")
A("خوانشِ walk-forward (چیزی که میانگینِ کل پنهان می‌کند):")
A("")
A("* **جت**: سقفِ ایستاده در هر قطعه‌ای که آتش می‌زند بالایِ نرخِ پایه است و از پلکان "
  "جلوتر می‌ماند؛ انتخاب محکم است.")
_cm = d["choch"]["variants"]["confirm_2d_margin1"]["by_fold"]
_c1 = d["choch"]["variants"]["current_1d"]["by_fold"]
_both = [k for k in _cm if _cm[k]["closed"] >= 20 and k in _c1 and _c1[k]["closed"] >= 20]
_better = sum(1 for k in _both if _cm[k]["win"] > _c1[k]["win"])
_worst = min(_both, key=lambda k: _cm[k]["win"])
A("* **CHoCH**: در " + N(_better) + " از " + N(len(_both)) + " قطعهٔ قابل‌سنجی بهترِ "
  "یک‌روزه است و در قطعهٔ " + N(int(_worst) + 1) + " بدتر (" + D(_cm[_worst]["win"])
  + " در برابرِ " + D(_c1[_worst]["win"]) + ")؛ در بازارِ نزولی هم نزدیکِ بی‌اثر است ("
  + D(d["choch"]["variants"]["confirm_2d_margin1"]["by_regime"]["bear"]["win"])
  + " در برابرِ نرخِ پایهٔ " + D(base) + "). انتخاب برایِ «سیگنالِ کمتر، دقیق‌تر» می‌ماند،"
  " ولی ادعایِ برد در هر regime نیست؛ در بازارِ نزولی وتوی هفتگی حکم را می‌گوید، نه این پرچم.")
A("* **نقطه‌زنی**: در دو قطعهٔ نخست تقریباً رویِ نرخِ پایه است و در دو قطعهٔ آخر "
  "بالا؛ با این حال در *هر چهار* قطعه از قاعدۀ قبلی جلوتر است، و در بازارِ نزولی "
  "بهترینِ عدد را دارد (" + D(d["hunt"]["variants"]["channel_bounce"]["by_regime"]["bear"]["win"]) + ").")
A("* **دابل‌باتم**: در هر قطعه بالایِ پایه — باثبات‌ترینِ پنج.")
A("* **فیبو**: تنها قاعدۀ پنج‌گانه که در دو قطعهٔ نخست **زیرِ نرخِ پایه** می‌افتد "
  "(" + folds(d["fib"]["variants"], "ungated_618_70_log") + "). این مستقل از دورِ I "
  "تأیید می‌کند که کمربندِ فیبو تریگر نیست؛ دورِ J آن را از امتیازِ سیگنال هم بیرون آورد.")
A("")
A("دو اصلاحِ خودِ سنجه درِ همین دور: (۱) تقسیمِ regime/قطعه پیش‌تر رویِ «همۀ آتش‌ها» "
  "حساب می‌شد و «open» (بی‌نتیجه تا افق) را هم می‌شمرد — همان ستون حالا فقط "
  "بستۀِ معتبر (win+loss) را می‌شمارد و با precisionِ اصلی هم‌سنج شد؛ (۲) شمارشِ "
  "بستۀِ هر قطعه از " + N(20) + " به بالا گزارش می‌شود تا قطعهٔ کم‌داده حدس نباشد.")
A("")

text = io.open(DOC, encoding="utf-8", newline="").read()
cut = text.find(MARK)
if cut != -1:
    text = text[:cut].rstrip("\r\n")
nl = "\r\n" if "\r\n" in text else "\n"
io.open(DOC, "w", encoding="utf-8", newline="").write(text.rstrip("\r\n") + nl + nl.join(L) + nl)
print("appended; doc chars:", len(io.open(DOC, encoding="utf-8").read()))
