# dev/test_notifications_v1.py — بند ۶: مرکزِ اعلان از منبعِ معتبر، بی‌تيترِ ساختگی
"""هیچ خبری درِ این برنامه ساخته نمی‌شود. این گارد همان را رویِ دو چیز می‌سنجد:

  ۱) طبقه‌بندِ `notifications.py` رویِ عنوان‌هایِ واقعیِ کدال — و اینکه
     «بی‌طبقه» هرگز «کم‌اهمیت» خوانده نمی‌شود؛
  ۲) لولۀِ feed رویِ یک بانکِ ساختگیِ درون‌حافظه‌ای: ادغامِ تکراری،
     شمارشِ ادغام‌شدگان، فیلترِ سطح، و اینکه هر آیتمِ خروجی یک `tracing_no`
     و یک `url`ِ کدالیِ واقعی دارد (بی‌آن، «خبر» یعنی اختراع).

مقابلهٔ آخر رویِ `market.db` واقعی اجرا می‌شود؛ بانک نباشد ⇒ SKIP.
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import notifications as N                        # noqa: E402

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


# ── ۱) طبقه‌بندیِ عنوان‌هایِ واقعیِ کدال ──────────────────────────────────────
CASES = [
    ("اطلاعات و صورت‌های مالی میاندوره‌ای  دوره ۶ ماهه منتهی به  ۱۴۰۵/۰۳/۳۱", "statements", N.LEVEL_HIGH),
    ("اطلاعات و صورتهای مالی سالانه (حسابرسی شده) دوره ۱۲ ماهه منتهی به ۱۴۴/۱۲/۲۹", "statements", N.LEVEL_HIGH),
    ("آگهی دعوت به مجمع عمومی عادی سالیانه مورخ ۱۴۰۵/۰۷/۲۰", "assembly", N.LEVEL_HIGH),
    ("افزایش سرمایه از محل آورده نقدی و مطالبات حال شده سهامداران", "capital", N.LEVEL_HIGH),
    ("تقسیم سود نقدی مجمع ۸۰۰ ریال به ازای هر سهم", "dividend", N.LEVEL_HIGH),
    ("گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به  ۱۴۰۵/۰۶/۳۱", "monthly", N.LEVEL_MED),
    ("گزارش تولید ماهانه مرداد ۱۴۰۵", "production", N.LEVEL_MED),
    ("بازخرید سهام به مبلغ ۵۰ میلیارد ریال", "other", N.LEVEL_UNKNOWN),
    ("", "other", N.LEVEL_UNKNOWN),
]
for title, kind, level in CASES:
    got = N.classify(title, "ن-۳۰")
    ck(f"طبقه: «{(title or 'خالی')[:34]}…» ⇒ {kind}/{level}",
       got["kind"] == kind and got["level"] == level, got)

ck("«بی‌طبقه» با «کم‌اهمیت» یکی نیست (دلیلِ جدا دارد)",
   N.classify("بازخرید سهام")["level"] == N.LEVEL_UNKNOWN
   and "نشناخت" in N.classify("بازخرید سهام")["reason"], N.classify("بازخرید سهام"))
ck("هر سطح برچسبِ فارسی دارد (رابط واژگانِ خامِ انگلیسی نمی‌بیند)",
   all(v in N.LEVEL_LABEL.values() for v in ("بالا", "متوسط", "پایین", "بی‌طبقه"))
   and len(N.LEVEL_LABEL) == 4)
ck("دلیلِ اهمیت برایِ هر نوعِ شناخته‌شده نوشته شده، نه خالی",
   all(N.classify(t)["reason"] for t, _k, _l in CASES if _l != N.LEVEL_UNKNOWN))

# ── ۲) لولۀِ feed رویِ بانکِ ساختگی ──────────────────────────────────────────
DDL = ("CREATE TABLE codal_notices (tracing_no INTEGER PRIMARY KEY, symbol TEXT,"
       " company_name TEXT, title TEXT, letter_code TEXT, publish_date TEXT,"
       " sent_date TEXT, url TEXT, fetched_at TEXT, pdf_url TEXT, excel_url TEXT)")


def bank(rows):
    c = sqlite3.connect(":memory:")
    c.execute(DDL)
    c.executemany("INSERT INTO codal_notices VALUES (" + ",".join(["?"] * 11) + ")", rows)
    return c


def row(tno, sym, title, pub="۱۴۰۵/۰۷/۱۰ ۱۰:۰۰:۰۰"):
    return (tno, sym, "شرکتِ " + sym, title, "ن-۳۰", pub, pub,
            f"https://codal.ir/Reports/Decision.aspx?hs={tno}", "2026-10-10 10:02:00",
            f"https://codal.ir/DownloadFile.aspx?hs={tno}", None)


c = bank([
    row(1, "شپنا", "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به  ۱۴۰۵/۰۶/۳۱"),
    row(2, "شپنا", "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به  ۱۴۰۵/۰۶/۳۱"),
    row(3, "فولاد", "اطلاعات و صورت‌های مالی سالانه (حسابرسی شده)"),
    row(4, "خودرو", "بازخرید سهام به مبلغ ۵۰ میلیارد ریال"),
])
f = N.feed(c, limit=50)
ck("feed سه اطلاعیۀِ یکتا می‌دهد، نه چهارتا", f["count"] == 3, f["count"])
ck("تکراری ادغام می‌شود و شمارشِ ادغام اعلام می‌شود (حذفِ بی‌صدا نه)",
   f["merged_duplicates"] == 1
   and [i for i in f["items"] if i["symbol"] == "شپنا"][0]["occurrences"] == 2, f)
ck("اهمیتِ هر آیتم از همان طبقه‌بند می‌آید",
   {i["symbol"]: i["level"] for i in f["items"]} ==
   {"شپنا": N.LEVEL_MED, "فولاد": N.LEVEL_HIGH, "خودرو": N.LEVEL_UNKNOWN}, f)
ck("فیلترِ سطح فقط «بالا» را نگه می‌دارد",
   [i["symbol"] for i in N.feed(c, levels=["high"], limit=50)["items"]] == ["فولاد"])
ck("sinceِ آینده ⇒ صفر آیتم، نه همه", N.feed(c, since="۱۴۰۵/۰۷/۱۱ ۰۰:۰۰:۰۰")["count"] == 0)
ck("هیچ آیتمی بی‌لینکِ کدال نیست (تيترِ بی‌منبع سرو نمی‌شود)",
   all(str(i["url"]).startswith("https://codal.ir/") and i["source"] == "codal"
       and i["id"] for i in f["items"]), f["items"][:1])
ck("زمانِ انتشار و زمانِ دریافتِ خودِ برنامه جدا می‌آیند",
   all(i["publish_date"] and i["received_at"] for i in f["items"]), f["items"][:1])

e = N.feed(bank([]), limit=10)
ck("بانکِ خالی ⇒ count=0 با status=ok (نه خطا، نه خبرِ جعلی)",
   e["status"] == "ok" and e["count"] == 0, e)
nobuf = sqlite3.connect(":memory:")
g = N.feed(nobuf, limit=10)
ck("جدولِ نبود ⇒ status=error با پیام، نه فهرستِ خالیِ بی‌دلیل",
   g["status"] == "error" and g["items"] == [] and "نیست" in g["message"], g)
ck("sources هم نبودِ جدول را «unavailable» می‌گوید نه «خالی»",
   N.sources(nobuf)["sources"][0]["state"] == "unavailable")
ck("sources ردیفِ صفر را «empty» می‌گوید (تفاوتِ «نیست» و «نرسیده»)",
   N.sources(bank([]))["sources"][0]["state"] == "empty")
ck("sourcesِ سالم تعداد و تازه‌ترینِ انتشار را می‌دهد",
   N.sources(c)["sources"][0]["rows"] == 4
   and N.sources(c)["sources"][0]["newest_publish"].startswith("۱۴۰۵"), N.sources(c))

# ── ۳) مقابله با بانکِ واقعی ─────────────────────────────────────────────────
db = os.path.join(ROOT, "market.db")
if not os.path.exists(db):
    ck("مقابله با market.db", None)
else:
    conn = sqlite3.connect(db)
    real = N.feed(conn, limit=200)
    ck("بانکِ واقعی: اطلاعیه هست و همه از کدال‌اند",
       real["status"] == "ok" and real["count"] > 0
       and all(str(i["url"]).startswith("https://codal.ir/") for i in real["items"]),
       real["count"])
    ck("بانکِ واقعی: هیچ آیتمی بی‌نماد یا بی‌عنوان نیست",
       all(i["symbol"] and i["title"] for i in real["items"]), real["items"][:1])
    kinds = {i["kind"] for i in real["items"]}
    ck("بانکِ واقعی: طبقه‌بند رویِ متنِ واقعی بی‌کار نمی‌ماند (بیش از یک نوع)",
       len(kinds) > 1, kinds)
    src = N.sources(conn)["sources"][0]
    ck("بانکِ واقعی: سلامتِ منبع اعلام می‌شود (ردیف + آخرینِ واکشی)",
       src["rows"] > 0 and src["last_fetch"], src)
    conn.close()

print("─" * 72)
print(f"نتیجۀِ گاردِ مرکزِ اعلان: {PASS}_pass / {FAIL}_fail / {SKIP}_skip")
sys.exit(1 if FAIL else 0)
