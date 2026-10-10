# dev/test_client_split_v1.py — بند ۲ مأموریت: درصدِ حقیقی/حقوقی، ارزش‌محور، تک‌تعریف
"""رأیِ مالک (1405-07-20): مبنایِ درصدها **ارزشِ خرید و فروش** است، نه حجم، و
ارزشِ غایب از ضربِ حجم در قیمت بازسازی نمی‌شود. این گارد هر دو نیمۀِ آن رأی را
می‌سنجد:

    ۱) ریاضیِ `client_split.py` — فرمول، استقلالِ خرید از فروش، مکملِ حقوقی،
       و همهٔ حالت‌هایِ «نامشخص» (مخرجِ صفر، null، منفی، NaN/inf، یک‌طرفه).
    ۲) سیمِ برنامه — کوئریِ تابلو چهار ارزشِ مبدأ را می‌خواند، درصدها را با
       همین ماژول می‌سازد، و ارزشِ خامِ ctv_* رویِ سیم نمی‌آید تا رابط کسرِ
       دومِ خودی نسازد.

ردیفِ bankِ محلی هم مقابله می‌شود: همان عددِ GetClientTypeHistory که زنده
دیده شد (1405-07-20، نشست 20261007) باید ۸۷٫۸٪ و ۸۱٫۱٪ بدهد. بی‌شبکه.
بانک نباشد ⇒ آن دو بند SKIP (نه شکست).
"""
import io
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from client_split import (  # noqa: E402
    BASIS, LABEL_BUY, LABEL_SELL, UNKNOWN_TEXT, complement, money, shares,
    shares_from_row, side_share,
)

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


# ── ۱. فرمول، عینِ متنِ رأی ───────────────────────────────────────────────────
# سهمِ حقیقیِ خرید = ارزشِ خریدِ حقیقی ÷ (ارزشِ خریدِ حقیقی + ارزشِ خریدِ حقوقی) × 100
ck("فرمولِ خرید: 300 از 400 ⇒ 75.0٪", side_share(300, 100) == 75.0,
   side_share(300, 100))
ck("فرمولِ خرید: 1 از 3 ⇒ 33.3٪ (یک رقم، نه بیشتر)", side_share(1, 2) == 33.3,
   side_share(1, 2))
# عددِ زندۀِ خودِ TSETMC (نشست 20261007 — پروبِ مستقیمِ GetClientTypeHistory)
BUY_I, BUY_N = 96561868240443.0, 13383598927951.0
SELL_I, SELL_N = 89212137948924.0, 20733329219470.0
ck("ردیفِ زنده: سهمِ حقیقیِ خرید 87.8٪", side_share(BUY_I, BUY_N) == 87.8,
   side_share(BUY_I, BUY_N))
ck("ردیفِ زنده: سهمِ حقیقیِ فروش 81.1٪", side_share(SELL_I, SELL_N) == 81.1,
   side_share(SELL_I, SELL_N))

# ── ۲. دو سمت مستقل‌اند؛ درصدِ خرید جای درصدِ فروش را نمی‌گیرد ────────────────
s = shares(BUY_I, BUY_N, SELL_I, SELL_N)
ck("خرید و فروش هر دو مستقل حساب می‌شوند",
   s["retail_buy_pct"] == 87.8 and s["retail_sell_pct"] == 81.1, s)
asym = shares(100, 0, 0, 100)
ck("سمتِ یک‌طرفه: خرید 100٪ و فروش 0٪ (قرینۀِ یکدیگر نمی‌شوند)",
   asym["retail_buy_pct"] == 100.0 and asym["retail_sell_pct"] == 0.0, asym)

# ── ۳. حقوقی مکملِ حقیقیِ همان سمت ──────────────────────────────────────────
for pair in ((300, 100), (1, 2), (BUY_I, BUY_N)):
    r = side_share(*pair)
    l = complement(r)
    ck(f"مکمل: {r} + {l} = 100.0", r is not None and round(r + l, 6) == 100.0,
       (r, l))
ck("مکملِ بی‌درصد ⇒ None، نه 100", complement(None) is None)

# ── ۴. «نامشخص»: هیچ‌کدام از این‌ها عدد نمی‌سازد ──────────────────────────────
ZERO_DEN = [(None, None), (0, 0), (0.0, 0.0)]
ck("مخرجِ صفر ⇒ None (هر دو گروه صفر = هیچ ارزشی ثبت نشده)",
   all(side_share(a, b) is None for a, b in ZERO_DEN))
NULLS = [(None, 5), (5, None), (None, None)]
ck("null در هر گروه ⇒ None", all(side_share(a, b) is None for a, b in NULLS))
BAD = [(-5, 10), (10, -5), (float("nan"), 10), (10, float("nan")),
       (float("inf"), 10), (10, float("-inf")), ("۱۲۳", 10), (True, 10)]
ck("منفی/NaN/inf/رشته/bool ⇒ None، نه مقدارِ جاافتاده",
   all(side_share(a, b) is None for a, b in BAD))
ck("money() هم همین داوری را می‌کند: -1 و 'abc' و True ⇒ None",
   money(-1) is None and money("abc") is None and money(True) is None
   and money(0) == 0.0)

s_none = shares(None, None, None, None)
ck("بی‌چهارارزش ⇒ هر چهار درصد None و basis=null",
   all(s_none[k] is None for k in ("retail_buy_pct", "legal_buy_pct",
                                   "retail_sell_pct", "legal_sell_pct",
                                   "pct_basis")), s_none)
half = shares(300, 100, None, None)
ck("فقطِ خرید معلوم ⇒ فروش نامشخص می‌ماند (سرِ هم نمی‌نشینند)",
   half["retail_buy_pct"] == 75.0 and half["retail_sell_pct"] is None
   and half["pct_basis"] == BASIS, half)
ck("متنِ «نامشخص» و برچسب‌هایِ سمت از همان فایل خوانده می‌شوند",
   UNKNOWN_TEXT == "نامشخص" and LABEL_BUY == "سهم از ارزش خرید"
   and LABEL_SELL == "سهم از ارزش فروش", (UNKNOWN_TEXT, LABEL_BUY, LABEL_SELL))

# ── ۵. بازسازیِ ارزش از حجم ممنوع ────────────────────────────────────────────
# نمادی که حجمِ حقیقیِ 9 برابرِ حقوقی دارد ولی *هیچِ* ارزشی درِ مبدأ نیست:
# اگر روزی کسی حجم را جانشینِ ارزش کند، این بند 90.0 می‌دهد و قرمز می‌شود.
vol_only = shares_from_row({"buy_i_val": None, "buy_n_val": None,
                            "sell_i_val": None, "sell_n_val": None,
                            "buy_i_vol": 900, "buy_n_vol": 100})
ck("فقط‌حجم ⇒ درصد ندارد (ارزش از حجم ساخته نمی‌شود)",
   vol_only["retail_buy_pct"] is None and vol_only["pct_basis"] is None, vol_only)
mixed_row = shares_from_row({"buy_i_val": BUY_I, "buy_n_val": None,
                             "sell_i_val": SELL_I, "sell_n_val": SELL_N})
ck("ردیفِ mixed (یک خانۀِ خالی) ⇒ همان سمت نامشخص، سمتِ دیگر درست",
   mixed_row["retail_buy_pct"] is None and mixed_row["retail_sell_pct"] == 81.1,
   mixed_row)

# ── ۶. سیمِ برنامه: تک‌منبع، بی‌کسرِ دوم درِ رابط ─────────────────────────────
src = io.open(os.path.join(ROOT, "api", "market.py"), encoding="utf-8").read()
ck("کوئریِ تابلو چهار ارزشِ مبدأ را از client_type_value می‌خواند",
   all(c in src for c in ("cv.buy_i_val", "cv.buy_n_val",
                          "cv.sell_i_val", "cv.sell_n_val")))
ck("نشستِ خودِ ردیفِ مبدأ هم می‌آید (ctv_d + pct_is_current)",
   "cv.d_even AS ctv_d" in src and "pct_is_current" in src)
ck("درصدِ تابلو از همان client_split.shares() ساخته می‌شود",
   "from client_split import shares as _client_shares" in src
   and "_client_shares(bi, bn, si, sn)" in src)
ck("ارزشِ خامِ ctv_* رویِ سیم نمی‌آید (درصدها تنها خروجی‌اند)",
   all(('"%s"' % c) in src for c in ("ctv_buy_i_val", "ctv_buy_n_val",
                                     "ctv_sell_i_val", "ctv_sell_n_val"))
   and "_DROP_FIELDS" in src)
ck("ضربِ حجم در قیمت برایِ این درصد درِ api/market.py ساخته نمی‌شود",
   "buy_i_vol * " not in src and "* vwap" not in src)
# «نامشخص» باید از پاسِ «JSON safety»ِ تابلو زنده بیرون بیاید: اگر NaN به ۰
# بدل شود، صفرِ بی‌صدا یعنی «حقیقی هیچ سهمی ندارد» — همان دروغی که بند ۲ منع
# می‌کند. (سنجشِ زنده 1405-07-20: پیش از این فهرست، هر ۵۸۹۲ ردیف ۰.۰ می‌دادند.)
_KEEP = src.split("_KEEP_NULL = (", 1)[1] if "_KEEP_NULL = (" in src else ""
_KEEP = _KEEP.split(")" + chr(10), 1)[0] if _KEEP else ""
ck("پنج ستونِ درصد/مبنا درِ _KEEP_NULL (null می‌ماند، نه صفر)",
   all('"%s"' % c in _KEEP for c in ("retail_buy_pct", "legal_buy_pct",
                                        "retail_sell_pct", "legal_sell_pct",
                                        "pct_basis")), _KEEP[:120])

# رابط هم کسرِ دوم نمی‌سازد: هیچ‌جا درِ shared/ این درصدها تقسیم نمی‌شوند
FE = os.path.join(ROOT, "frontend", "src")
hits = []
for dirpath, _dirs, files in os.walk(FE):
    for f in files:
        if not f.endswith((".ts", ".tsx")):
            continue
        p = os.path.join(dirpath, f)
        if "ClientSharePct.tsx" in p:
            continue
        t = io.open(p, encoding="utf-8", errors="ignore").read()
        if "retail_buy_pct" in t and ("/" in t and "legal" in t.lower()):
            # مصرف‌کننده‌ای که ستونِ آماده را *تقسیم* کند، کسرِ دوم است
            if "retail_buy_pct /" in t or "retail_buy_pct/" in t:
                hits.append(p)
ck("هیچ پروندۀِ فرانت درصدِ حقیقی/حقوقی را دوباره تقسیم نمی‌کند",
   not hits, hits)

# ── ۷. مقابله با بانکِ واقعی (بی‌شبکه) ───────────────────────────────────────
db = os.path.join(ROOT, "market.db")
if not os.path.exists(db):
    ck("مقابله با market.db", None)
else:
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT buy_i_val, buy_n_val, sell_i_val, sell_n_val, kind, d_even"
            " FROM client_type_value WHERE kind='native'"
            " ORDER BY d_even DESC, buy_i_val DESC LIMIT 1").fetchone()
        if not row:
            ck("ردیفِ native درِ client_type_value", None)
        else:
            got = shares(row[0], row[1], row[2], row[3])
            manual = round(100.0 * row[0] / (row[0] + row[1]), 1)
            ck("ردیفِ واقعیِ بانک با فرمولِ دستی می‌خواند (خرید)",
               got["retail_buy_pct"] == manual, (got["retail_buy_pct"], manual))
            ck("مکملِ واقعی 100 را می‌بندد",
               round(got["retail_buy_pct"] + got["legal_buy_pct"], 6) == 100.0)
            # هیچ‌وقت بی‌ارزش نمی‌شود؛ و هیچ‌وقت از حجمِ همان ردیف نمی‌خواند
            ck("basis برایِ ردیفِ native همان value است",
               got["pct_basis"] == BASIS, got)
    finally:
        conn.close()

print("─" * 72)
print(f"نتیجۀِ گاردِ درصدِ حقیقی/حقوقی: {PASS}_pass / {FAIL}_fail / {SKIP}_skip")
sys.exit(1 if FAIL else 0)
