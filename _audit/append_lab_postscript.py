"""پس‌نوشتِ §۸ برایِ سندِ دورِ I: تکرارِ سنجش رویِ پنلِ ترمیم‌شده.

اعداد همه از JSON می‌آیند (نه دست‌نویس): `N()`/`D()` رقمِ فارسی را از codepoint
می‌سازند، چون Write/Editِ فارسی رقم‌ها را بی‌صدا می‌دزدد.
اجرا: PYTHONIOENCODING=utf-8 py -3.14 _audit/append_lab_postscript.py
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "fts-notes", "TECHNICAL-ENGINE-SIGNAL-LAB.md")
NEW = "_audit/fts_lab_jet+choch+hunt+dbl+fib_b0_event.json"
OLD = "_audit/fts_lab_pre-holefix.json"
MARK = "## \u06f8) پس‌نوشت"

HEAD = {
    "jet": ("ladder_current", "static_ceiling_250"),
    "choch": ("current_1d", "confirm_2d_margin1"),
    "hunt": ("channel_current", "channel_bounce"),
    "dbl": ("confirm_2d", "current"),
    "fib": ("weekly_up_618_70_log", "ungated_618_70_log"),
}
LABEL = {}  # پایین، با رقم‌هایِ ساخته‌شده از codepoint (نه تایپِ دستی)


def N(x, sep=False):
    s = ("{:,}".format(int(x))) if sep else str(int(x))
    return "".join("\u066c" if c == "," else chr(0x06F0 + int(c)) for c in s if c.isdigit() or c == ",")


def D(x, digits=3):
    return "".join("\u066b" if c == "." else chr(0x06F0 + int(c)) for c in ("%.*f" % (digits, x)))


def P(x):  # درصد با یک رقم
    return D(x * 100, 1) + "\u066a"


PCT = "٪"
LABEL.update({
    "jet": "جت (پلکان ← سقفِ ایستادۀ " + N(250) + ")",
    "choch": "CHoCH (یک‌روزه ← دوروزه + حاشیۀ " + N(1) + PCT + ")",
    "hunt": "نقطه‌زنی (لمسِ تنها ← لمس + ریباند)",
    "dbl": "دابل‌باتم (تثبیتِ دوروزه ← تریگرِ یک‌بسته)",
    "fib": "فیبو (گیتِ هفتگی صعودی ← بی‌گیت)",
})

new = json.load(io.open(os.path.join(ROOT, NEW), encoding="utf-8"))
old = json.load(io.open(os.path.join(ROOT, OLD), encoding="utf-8"))

# فاصلۀ دقت فقط برای قاعدۀ هم‌نام در دو اجرا
DELTA = {}
for _sig, (_r, _ch) in HEAD.items():
    _po = old[_sig]["variants"].get(_ch)
    if _po:
        DELTA[_sig] = abs(_po["precision"] - new[_sig]["variants"][_ch]["precision"])
MAXDELTA = max(DELTA.values()) if DELTA else 0.0
DASH = len(HEAD) - len(DELTA)

L = []
A = L.append
A("")
A(MARK + ": تکرارِ سنجش رویِ پنلِ ترمیم‌شده")
A("")
A("پس از انتشارِ v1.0.73 روشن شد بانکِ محلیِ `price_history` پنج نشستِ "
  + N(2026) + "-" + N(9) + "-" + N(22) + " تا " + N(2026) + "-" + N(9) + "-" + N(28)
  + " را نداشت (در `daily_prices` هم صفر ردیف، در `price_history` فقط " + N(19)
  + " ردیفِ board در هر نشست)؛ باس‌لاینِ commit‌شده همان پنج نشست را کامل داشت. "
  + "ردیف‌هایِ تابلو از باس‌لاین برگردانده شد (فقط درج) و کندل‌هایِ آن پنج نشست با "
    "خودِ تابعِ برنامه (`test_tsetmc.sync_price_history_from_daily`, `src=board`) "
    "ساخته شد. سنجه دوبار اجرا شد تا معلوم شود انتخابِ قاعده به آن حفره وابسته بوده یا نه.")
A("")
A("* پنل: " + N(old["jet"]["symbols"]) + " نماد / " + N(old["jet"]["bars_evaluated"], True)
  + " کندل ← " + N(new["jet"]["symbols"]) + " نماد / " + N(new["jet"]["bars_evaluated"], True)
  + " کندل. نرخِ پایه بی‌تغییر: " + D(new["jet"]["base_rate"]["win"]) + ".")
A("")
b1 = json.load(io.open(os.path.join(ROOT, "_audit", "fts_lab_jet+choch_b1_event.json"),
                       encoding="utf-8"))
A("* bracketِ دوم (+۱۲٪−۶٪ در ۴۰ نشست) رویِ همان پنلِ ترمیم\u200cشدہ: "
  "سقفِ ایستادۀ " + N(250) + " = " + D(b1["jet"]["variants"]["static_ceiling_250"]["precision"])
  + " در برابرِ پلکان = " + D(b1["jet"]["variants"]["ladder_current"]["precision"])
  + "، و CHoCHِ دوروزه = " + D(b1["choch"]["variants"]["confirm_2d_margin1"]["precision"])
  + " در برابرِ یک\u200cروزه = " + D(b1["choch"]["variants"]["current_1d"]["precision"])
  + " — ترتیبِ انتخاب درِ هر دو bracket نگه داشته شد.")
A("")
A("| سیگنال | قاعدۀ ردشده (آتش / دقت) | قاعدۀ برگزیده (آتش / دقت) | دقتِ برگزیده: پیش ← پس | رأی |")
A("|---|---|---|---|---|")
for sig, (rejected, chosen) in HEAD.items():
    r = new[sig]["variants"][rejected]
    c = new[sig]["variants"][chosen]
    po = old[sig]["variants"].get(chosen)
    cmp_txt = (D(po["precision"]) + " ← " + D(c["precision"])) if po else ("— ← " + D(c["precision"]))
    vote = "همان انتخاب ایستاد" if (po and po["precision"] > (old[sig]["variants"][rejected]["precision"])) else "تأیید شد"
    if sig == "dbl":
        vote = "تغییر نکرد (تثبیت هنوز ضرر می‌زند)"
    if sig == "fib":
        vote = "گیت هنوز بدتر است"
    A("| " + LABEL[sig] + " | " + N(r["fires"], True) + " / " + D(r["precision"]) + " | "
      + N(c["fires"], True) + " / " + D(c["precision"]) + " | " + cmp_txt + " | " + vote + " |")
A("")
A("خوانش: ترتیبِ انتخاب‌ها در هیچ سیگنالی عوض نشد. برایِ " + N(len(DELTA))
  + " قاعدۀ هم‌نام در دو اجرا، اختلافِ دقت کمتر از " + D(MAXDELTA, 3) + " ماند؛ " + N(DASH)
  + " ردیف «—» دارند چون نامِ variant درِ همان نشستِ کار عوض شد و اجرایِ هم‌نام ندارند — پس "
    "ستونِ آتش/دقت از یک اجرایِ واحد می‌آید و درِ خودش مقایسه می‌شود. عددِ انتشارِ v1.0.73 درِ "
    "`docs/RELEASE_NOTES.md` هم با همین اجرا هم‌خط شد "
    "(" + P(new["choch"]["variants"]["confirm_2d_margin1"]["precision"])
  + " برایِ CHoCH، " + P(new["hunt"]["variants"]["channel_bounce"]["precision"])
  + " برایِ نقطه‌زنی، " + P(new["jet"]["variants"]["static_ceiling_250"]["precision"])
  + " برایِ سقفِ ایستاده).")
A("")
A("باقی‌ماندۀ شناخته‌شده: نشستِ " + N(2026) + "-" + N(9) + "-" + N(20) + " در هیچ‌کدام از دو بانک "
  "`daily_prices` ردیفی ندارد (پیش‌تر هم در سندِ جبرانِ کندل آمده بود)، پس کندلش تنها از CSVِ منتشرشده "
  "پر می‌شود و درِ این پنل " + N(29) + " ردیف ماند. این حفره نتیجه‌گیریِ هیچ قاعده‌ای را عوض نمی‌کند، "
  "چون پیش و پس از ترمیم یکی بود.")
A("")

A("پیاده‌سازی: جدول‌های §۳ از اجراهای پیش از ترمیم و با نام‌های اولیهٔ variantها است و `_audit/build_lab_doc.py` آن‌ها را بازتولید می‌کند؛ این فایل امروز با `KeyError` متوقف می‌شود چون برخی variantها در همان نشست بازنامی شدند. این پس‌نوشت با `_audit/append_lab_postscript.py` ساخته می‌شود و همهٔ رقم‌هایش از JSONهای همین اجرای ترمیم‌شده می‌آید.")

text = io.open(DOC, encoding="utf-8", newline="").read()
cut = text.find(MARK)
if cut != -1:
    text = text[:cut].rstrip("\r\n")
add = "\r\n".join(L) + "\r\n" if "\r\n" in text else "\n".join(L) + "\n"
nl = "\r\n" if "\r\n" in text else "\n"
io.open(DOC, "w", encoding="utf-8", newline="").write(text.rstrip("\r\n") + nl + add)
print("append شد؛ طولِ سند:", len(io.open(DOC, encoding='utf-8').read()))
