#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/portfolio_weights_v1035.py — وزنِ سبد باید از «قیمت × تعداد» بیاید، نه از حدس.

چرا این گارد متولد شد (PORT-1، ۲۶ سپتامبر ۲۰۲۶):

۱) **ستونِ «تعداد» وجود نداشت.** جدول selection_decisions فقط weight_pct و price
   داشت؛ کاربر نمی‌توانست بگوید «۲۰۰ سهمِ فولاد» و وزنش را ببیند. وزنِ دستی یا
   «مساوی ۱۰۰÷N» تنها گزینه بود — و همان است که جملهٔ «طلا ۷۰٪ از سبد — هدف ۴۵٪»
   را غیرممکن می‌کرد.

۲) **POSTِ جزئی، دادهٔ کاربر را پاک می‌کرد.** هر فیلدِ نیامده در payload به
   پیش‌فرضِ صفر می‌نشست و UPSERT همان را می‌نوشت؛ «ثبت پله» از تب ایجنت ارشد یا
   دیالوگ فشردهٔ جدول، قیمت/تعداد/نامِ قبلی را بی‌صدا صفر می‌کرد.

۳) **ارزشِ غایب نباید صفر شود.** اگر فقط برخی ردیف‌ها تعداد داشته باشند، جمعِ
   همان‌ها مخرجِ وزن می‌شود و وزنِ بقیه بزرگ‌نمایی — عددِ خوش‌قالبِ غلط. قاعدهٔ
   مخزن: «داده نبودن ≠ صفر».

گارد نه به market.db واقعی نیاز دارد (بانکِ درون‌حافظه‌ای می‌سازد) و نه به شبکه.
اجرا:  python dev/portfolio_weights_v1035.py
خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import fts_engine                       # noqa: E402
from api import selection as SEL        # noqa: E402
from api import _core as CORE           # noqa: E402

TS_BASKET = os.path.join(ROOT, "frontend", "src", "features", "portfolio",
                         "api", "useSymbolBasket.ts")
TS_PORT = os.path.join(ROOT, "frontend", "src", "features", "portfolio",
                       "api", "usePortfolio.ts")
TS_DONUT = os.path.join(ROOT, "frontend", "src", "features", "portfolio",
                        "components", "TwinDonuts.tsx")
TS_STD = os.path.join(ROOT, "frontend", "src", "features", "portfolio",
                      "model", "standardAllocation.ts")
TS_TARGET = os.path.join(ROOT, "frontend", "src", "features", "portfolio",
                         "stores", "targetAllocation.ts")
TS_DELTA = os.path.join(ROOT, "frontend", "src", "features", "portfolio",
                        "components", "DeltaBar.tsx")

PASS, FAIL = 0, []


def ck(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print("  ok   " + name)
    else:
        FAIL.append(name)
        print(f"  FAIL {name}" + (f"  ← {detail}" if detail else ""))


OLD_DDL = ("CREATE TABLE selection_decisions (symbol TEXT PRIMARY KEY,"
           " name TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'pending',"
           " reason TEXT DEFAULT '', note TEXT DEFAULT '', stop_loss TEXT DEFAULT '',"
           " asset_kind TEXT DEFAULT '', weight_pct REAL DEFAULT 0, price REAL DEFAULT 0,"
           " score INTEGER DEFAULT 0, pricing_mode TEXT DEFAULT '',"
           " sector TEXT DEFAULT '', updated_at TEXT DEFAULT '')")


def row(sym, status="accept", weight=0.0, price=0.0, qty=0.0):
    return {"symbol": sym, "name": "", "status": status, "reason": "", "note": "",
            "stop_loss": "", "asset_kind": "", "weight_pct": weight, "price": price,
            "qty": qty, "score": 0, "pricing_mode": "", "sector": "",
            "updated_at": "2026-09-26T10:00:00"}


def open_board_db(path):
    """اتصالِ تازه به بانکِ ساختگیِ get_db — endpoint هر بار می‌بنددش."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.create_function("norm_fa", 1, fts_engine.norm_fa, deterministic=True)
    return conn


def board_db(path=None):
    """بانکِ instruments + market_watch + norm_fa (جای market.db).

    روی فایل که هر فراخوانیِ get_db اتصالِ تازه (و خودِ endpoint آن را می‌بندد)
    به همان داده ببیند — درون‌حافظه‌ای با یک اتصالِ مشترک، نخستین close بقیه را
    بی‌نتیجه می‌کرد.
    """
    if path is None:
        conn = sqlite3.connect(":memory:")
    else:
        if os.path.exists(path):
            os.remove(path)
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.create_function("norm_fa", 1, fts_engine.norm_fa, deterministic=True)

    conn.execute("CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT, l_val30 TEXT,"
                 " sector_name TEXT, paper_type INTEGER)")
    conn.execute("CREATE TABLE market_watch (ins_code TEXT, d_even INTEGER,"
                 " p_last REAL, p_closing REAL)")
    conn.executemany("INSERT INTO instruments VALUES (?,?,?,?,?)", [
        ("1", "فولاد", "فولاد مبارکه اصفهان", "فلزات اساسي", 1),
        ("2", "عيار1", "صندوق سرمايه گذاري قابل معامله عيار",
         "صندوق سرمايه گذاري قابل معامله", 8),
        ("3", "اطلس", "صندوق سرمايه گذاري قابل معامله اطلس",
         "صندوق سرمايه گذاري قابل معامله", 8),
        ("4", "ضهرم5026", "اختيارخ اهرم-24000-1405/05/28",
         "صندوق سرمايه گذاري قابل معامله", 1),
        ("5", "اخزا1", "اوراق مشارکت خزانه", "اوراق تامين مالي", 2),
    ])
    conn.executemany("INSERT INTO market_watch VALUES (?,?,?,?)", [
        ("1", 20260923, 4470, 4450),
        ("2", 20260923, 15200, 15100),
        ("3", 20260923, None, 15100),      # صندوقی که «آخرین» ندارد
        ("4", 20260923, 300, 290),
        ("5", 20260923, 0, 0),             # بی‌قیمت
    ])
    conn.commit()
    return conn


_USER_PATH = os.path.join(ROOT, "dev", "_tmp_portfolio_user.db")


def open_user_db():
    """اتصالِ تازه به بانکِ کاربرِ ساختگی (get_user_db هم همین کار را می‌کند)."""
    u = sqlite3.connect(_USER_PATH)
    u.row_factory = sqlite3.Row
    return u


def user_db():
    """بانکِ کاربرِ ساختگی روی فایل، با اسکیمای کاملِ امروز."""
    if os.path.exists(_USER_PATH):
        os.remove(_USER_PATH)
    u = open_user_db()
    CORE.ensure_selection_schema(u)
    u.commit()
    return u


def drop_user_db():
    if os.path.exists(_USER_PATH):
        os.remove(_USER_PATH)
    for suf in ("-wal", "-shm"):
        if os.path.exists(_USER_PATH + suf):
            os.remove(_USER_PATH + suf)


# ── ۱) مایگریشنِ افزودنی روی بانکِ نسخهٔ قبل ────────────────────────────────
print("۱) ستون «تعداد» روی جدولِ نسخهٔ قبل")
tmp = os.path.join(ROOT, "dev", "_tmp_portfolio_v1035.db")
if os.path.exists(tmp):
    os.remove(tmp)
try:
    c = sqlite3.connect(tmp)
    c.execute(OLD_DDL)
    c.execute("INSERT INTO selection_decisions (symbol,status,weight_pct,price)"
              " VALUES ('فولاد','accept',40,4470)")
    c.commit()
    cols0 = [r[1] for r in c.execute("PRAGMA table_info(selection_decisions)")]
    ck("بانکِ مصنوعی بی‌«تعداد» ساخته شد", "qty" not in cols0, str(cols0))
    c.close()

    # اتصالِ تازه (مثلِ بازِشدنِ برنامه روی بانکِ نسخهٔ قبل)
    c2 = sqlite3.connect(tmp)
    CORE.ensure_selection_schema(c2)
    c2.close()
    c = sqlite3.connect(tmp)
    c.row_factory = sqlite3.Row
    cols = [r[1] for r in c.execute("PRAGMA table_info(selection_decisions)")]
    ck("ensure_selection_schema ستون qty را افزود", "qty" in cols, str(cols))
    kept = c.execute("SELECT weight_pct, price, status FROM selection_decisions").fetchone()
    ck("هیچ ردیفی از بین نرفت و مقادیر عوض نشد",
       tuple(kept) == (40.0, 4470.0, "accept"), str(tuple(kept)))
    n2 = c.execute("SELECT COUNT(*) FROM selection_decisions").fetchone()[0]
    ck("عددِ ردیف‌ها ثابت ماند", n2 == 1, f"count={n2}")
    # idempotent: اجرای دوم نباید بشکند
    CORE.ensure_selection_schema(c)
    ck("اجرای دومِ ensure بی‌خطر است (idempotent)", True)
    c.close()
finally:
    if os.path.exists(tmp):
        os.remove(tmp)

# ── ۲) محاسبهٔ وزن از ارزش ─────────────────────────────────────────────────
print("۲) _weights: ارزشِ ردیف، و عقب‌نشینیِ صادقانه")

rs = [row("فولاد", price=5000, qty=100), row("شپنا", price=5000, qty=300)]
meta = SEL._weights(rs)
ck("وزن از ارزش حساب می‌شود (۲۵٪ / ۷۵٪)",
   [d["weight_eff_pct"] for d in rs] == [25.0, 75.0],
   str([d["weight_eff_pct"] for d in rs]))
ck("منشأِ وزن «value» گزارش می‌شود", meta["weight_source"] == "value", meta["weight_source"])
ck("ارزشِ کل سبد برگردانده می‌شود", meta["total_value"] == 2_000_000, str(meta["total_value"]))
ck("هیچ ردیفی بی‌ارزش نیست", meta["value_missing_count"] == 0)
ck("وزنِ دستیِ صفر، weight_manual نمی‌شود", all(d["weight_manual"] is False for d in rs))

rs = [row("فولاد", price=5000, qty=100), row("شپنا", price=5000, qty=0)]
meta = SEL._weights(rs)
ck("با یک ردیفِ بی‌تعداد، وزنِ ارزشی ساخته نمی‌شود",
   meta["weight_source"] != "value", meta["weight_source"])
ck("ارزشِ کل None می‌ماند (نه جمعِ ناقص)", meta["total_value"] is None, str(meta["total_value"]))
ck("ردیف‌های بی‌ارزش شمرده می‌شوند", meta["value_missing_count"] == 1)
ck("ردیفِ بی‌تعداد صفرِ ساختگی نمی‌شود",
   all(d["weight_eff_pct"] > 0 for d in rs), str([d["weight_eff_pct"] for d in rs]))

rs = [row("فولاد", price=0, qty=100)]
meta = SEL._weights(rs)
ck("قیمتِ صفر ارزش نمی‌سازد", rs[0]["value_toman"] is None, str(rs[0]["value_toman"]))
ck("منشأ در نبودِ ارزش «equal» است", meta["weight_source"] == "equal", meta["weight_source"])

rs = [row("فولاد", weight=30), row("شپنا", weight=10)]
meta = SEL._weights(rs)
ck("وزنِ دستی (بدون تعداد) حفظ می‌شود",
   [d["weight_eff_pct"] for d in rs] == [30.0, 10.0], str([d["weight_eff_pct"] for d in rs]))
ck("منشأ «manual» گزارش می‌شود", meta["weight_source"] == "manual", meta["weight_source"])

rs = [row("فولاد", weight=-5), row("شپنا", weight=0)]
SEL._weights(rs)
ck("وزنِ منفی دستی حساب نمی‌شود",
   all(d["weight_source"] == "equal" for d in rs), str([d["weight_source"] for d in rs]))

rs = []
meta = SEL._weights(rs)
ck("سبدِ خالی بی‌خطا می‌گذرد", meta["eq"] == 0.0 and meta["total_value"] is None)

rs = [row("فولاد", price=1000, qty=900), row("شپنا", price=1000, qty=100)]
SEL._weights(rs)
ck("سقفِ وزن روی وزنِ ارزشی هم پرچم می‌گیرد",
   rs[0]["over_cap"] is True and rs[1]["over_cap"] is False,
   str([d["over_cap"] for d in rs]))

# ── ۳) طبقهٔ دارایی از همان classifyِ تابلو ────────────────────────────────
print("۳) طبقهٔ دارایی از mstat_engine.classify (نه نگاشتِ دوم در فرانت)")
_real_get_db = SEL.get_db
_board_path = os.path.join(ROOT, "dev", "_tmp_portfolio_board.db")
board_db(_board_path)                      # یک‌بار پر می‌شود
_opened = []


def _board_conn():
    c = open_board_db(_board_path)
    _opened.append(c)          # هر اتصالِ بازی مانده را در پایان می‌بندیم
    return c


SEL.get_db = _board_conn
try:
    cls = SEL._asset_classes(["فولاد", "عيار1", "نامعلوم"])
    ck("سهام شناسایی شد", cls.get("فولاد", {}).get("cls") == "stock", str(cls))
    ck("صندوقِ طلا از نامش شناخته شد", cls.get("عيار1", {}).get("kind") == "gold",
       str(cls.get("عيار1")))
    ck("نمادِ بی‌سطر حدس نمی‌خورد", cls.get("نامعلوم") is None, str(cls))

    got = [d["symbol"] for d in SEL.get_selection_symbols(q="عيار")["data"]]
    ck("جستجو صندوقِ طلا را پیدا می‌کند", "عيار1" in got, str(got))
    ck("اختیار در نتیجه‌ها نمی‌آید", all(not s.startswith("ضهرم") for s in got), str(got))

    got = [d["symbol"] for d in SEL.get_selection_symbols(q="اخزا1")["data"]]
    ck("اوراق به نامِ داراییِ سبد نمی‌آید", got == [], str(got))

    d0 = (SEL.get_selection_symbols(q="اطلس")["data"] or [{}])[0]
    ck("نام و قیمت از سرور می‌آید", d0.get("symbol") == "اطلس" and d0.get("price") == 15100,
       str(d0))
    ck("«آخرین» تهی با «پایانی» پر می‌شود", d0.get("price") not in (None, 0), str(d0))

    ck("جستجوی خالی چیزی نمی‌فرستد", SEL.get_selection_symbols(q="")["data"] == [])
    ck("جستجوی بی‌نتیجه لیستِ خالی می‌دهد (نه خطا)",
       SEL.get_selection_symbols(q="چیزی‌نیست")["data"] == [])

    # نوشتارِ عربیِ کاربر باید به نمادِ فارسی برسد (تستِ norm_fa سمت SQL)
    ck("جستجو با «ی» فارسی، نمادِ «ي» عربی را پیدا می‌کند",
       any(d["symbol"] == "عيار1" for d in SEL.get_selection_symbols(q="عیار")["data"]),
       str(SEL.get_selection_symbols(q="عیار")["data"]))

    # یک نشستِ اضافی: تکراریِ d_even نباید ردیفِ دوتایی بسازد
    b = open_board_db(_board_path)
    b.execute("INSERT INTO market_watch VALUES ('1', 20260922, 4300, 4300)")
    b.commit()
    b.close()
    rows = SEL.get_selection_symbols(q="فولاد")["data"]
    ck("نشستِ قدیمی در جستجو تکرار نمی‌سازد", len(rows) == 1 and rows[0]["price"] == 4470,
       str(rows))
finally:
    SEL.get_db = _real_get_db
    for _c in _opened:
        try:
            _c.close()
        except Exception:
            pass
    _opened.clear()

# ── ۴) پاسخِ سبد: ترکیبِ طبقات + ارزشِ کل ──────────────────────────────────
print("۴) پاسخ /api/selection/portfolio: ترکیب طبقات برای جملهٔ «۷۰٪ طلا»")
_real_get_user_db = SEL.get_user_db
_u = user_db()
_u.execute("INSERT INTO selection_decisions (symbol,name,status,price,qty)"
           " VALUES ('عيار1','صندوق عیار','accept',15100,100)")
_u.execute("INSERT INTO selection_decisions (symbol,name,status,price,qty)"
           " VALUES ('فولاد','فولاد مبارکه','accept',4450,50)")
_u.execute("INSERT INTO selection_decisions (symbol,name,status,price,qty)"
           " VALUES ('اطلس','صندوق اطلس','monitor',15100,10)")
_u.commit()
SEL.get_db = _board_conn
SEL.get_user_db = open_user_db
_u.execute("UPDATE selection_decisions SET updated_at = updated_at")
_u.commit()
_u.close()
try:
    feed = SEL.get_selection_portfolio()
    lim = feed["limits"]
    # ارزش‌ها: عيار1 = ۱۵٬۱۰۰×۱۰۰ = ۱٬۵۱۰٬۰۰۰ · فولاد = ۴٬۴۵۰×۵۰ = ۲۲۲٬۵۰۰
    ck("جمع وزن‌های ارزشی ۱۰۰٪ است", abs(lim["sum_weight_pct"] - 100.0) < 0.11,
       str(lim["sum_weight_pct"]))
    ck("ارزشِ کل به تومان برگردانده می‌شود",
       lim["portfolio_value_toman"] == 1_732_500, str(lim["portfolio_value_toman"]))
    gold_pct = [d["weight_eff_pct"] for d in feed["portfolio"] if d["symbol"] == "عيار1"][0]
    ck("سهمِ صندوق طلا از ارزشِ سبد (۸۷٪)", gold_pct == 87.2, str(gold_pct))
    ck("ترکیب طبقات ساخته شد", lim["class_mix_pct"] == {"gold": 87.2, "stock": 12.8},
       str(lim["class_mix_pct"]))
    ck("ردیف‌های monitor در ترکیب نمی‌آیند", len(feed["portfolio"]) == 2,
       str(feed["portfolio"]))
    ck("هر ردیفِ accept برچسبِ طبقه دارد",
       all(d.get("asset_class") for d in feed["portfolio"]), str(feed["portfolio"]))
    ck("class_missing_count صفرِ صادق است", lim["class_missing_count"] == 0, str(lim))
finally:
    SEL.get_db = _real_get_db
    SEL.get_user_db = _real_get_user_db
    for _c in _opened:
        try:
            _c.close()
        except Exception:
            pass
    import gc
    gc.collect()
    for _p in (_board_path, _board_path + "-wal", _board_path + "-shm"):
        if os.path.exists(_p):
            os.remove(_p)
    drop_user_db()

# ── ۵) POSTِ جزئی نباید داراییِ ثبت‌شده را پاک کند ─────────────────────────
print("۵) PATCH-semantics در /api/selection/decision")
_u = user_db()
_u.execute("INSERT INTO selection_decisions (symbol,name,status,price,qty,sector)"
           " VALUES ('فولاد','فولاد مبارکه','accept',4450,120,'فلزات اساسي')")
_u.commit()
_u.close()
SEL.get_user_db = open_user_db
try:
    res = SEL.post_selection_decision({"symbol": "فولاد", "status": "accept",
                                       "note": "فقط یادداشت", "weight_pct": 0})
    _v = open_user_db()
    got = dict(_v.execute("SELECT * FROM selection_decisions").fetchone())
    _v.close()
    ck("پاسخ موفق", res.get("status") == "success", str(res))
    ck("قیمتِ ثبت‌شده پاک نشد", got["price"] == 4450, str(got["price"]))
    ck("تعدادِ ثبت‌شده پاک نشد", got["qty"] == 120, str(got["qty"]))
    ck("نامِ ثبت‌شده پاک نشد", got["name"] == "فولاد مبارکه", str(got["name"]))
    ck("صنعتِ ثبت‌شده پاک نشد", got["sector"] == "فلزات اساسي", str(got["sector"]))
    ck("یادداشتِ تازه نوشته شد", got["note"] == "فقط یادداشت", str(got["note"]))

    SEL.post_selection_decision({"symbol": "فولاد", "status": "accept",
                                 "price": 4450, "qty": 0, "weight_pct": 0})
    _v = open_user_db()
    got = dict(_v.execute("SELECT qty FROM selection_decisions").fetchone())
    _v.close()
    ck("صفرِ صریح تعداد را پاک می‌کند", got["qty"] == 0, str(got["qty"]))

    SEL.post_selection_decision({"symbol": "عيار1", "status": "accept",
                                 "name": "صندوق عیار", "price": 15100, "qty": 40,
                                 "weight_pct": 0})
    _v = open_user_db()
    got = dict(_v.execute(
        "SELECT * FROM selection_decisions WHERE symbol='عيار1'").fetchone())
    _v.close()
    ck("رکوردِ تازه با تعداد ذخیره شد",
       got["qty"] == 40 and got["price"] == 15100 and got["name"] == "صندوق عیار", str(got))

    # حذفِ تصمیم و بازگشت
    SEL.post_selection_decision({"symbol": "عيار1", "status": "pending"})
    _v = open_user_db()
    n = _v.execute("SELECT COUNT(*) FROM selection_decisions WHERE symbol='عيار1'").fetchone()[0]
    _v.close()
    ck("pending رکورد را پاک می‌کند", n == 0, str(n))
finally:
    SEL.get_user_db = _real_get_user_db
    drop_user_db()

# ── ۶) قاعدهٔ «کلید = کلمه» در طبقهٔ صندوق ─────────────────────────────────
print("۶) fund_kind: «معيار» نباید «عیار» خوانده شود")
import mstat_engine as ME  # noqa: E402

ck("صندوقِ طلای واقعی طلا می‌ماند",
   ME.fund_kind("صندوق طلاي عيار مفيد", "عيار") == "gold")
ck("«ديباي معيار» صندوقِ کالا است نه طلا",
   ME.fund_kind("صندوق س.كالاي ديباي معيار", "ليان") == "commod")
ck("«آواي معيار-س» صندوقِ سهامی است",
   ME.fund_kind("صندوق س.سهام آواي معيار-س", "آوا") == "equity")
ck("«درآمدثابتِ» سرهم‌نویسی هم درآمدِ ثابت می‌ماند",
   ME.fund_kind("صندوق درآمدثابت مشترك البرز-د", "اصيل") == "fixed")
ck("«…دثابت» (مخففِ ص.س.دثابت) درآمدِ ثابت می‌ماند",
   ME.fund_kind("ص.س.دثابت مشترك صباي هدف-د", "هدف") == "fixed")
ck("«…ارزش-درسهام» بی‌طبقه نمی‌ماند",
   ME.fund_kind("صندوق س.انارنماد ارزش-درسهام", "انار") == "equity")
# هیچ کلیدی نباید با فاصله/خط تیره شروع شود و باز هم داخلِ کلمه‌ای بغلتد
ck("طبقهٔ ناشناخته به 'etf' می‌نشیند نه به یک طبقهٔ قرضی",
   ME.fund_kind("صندوق سرمایه‌گذاری بی‌نام و نشان", "ZZZ") == "etf")

# ── ۷) قراردادِ سمتِ فرانت ─────────────────────────────────────────────────
print("۷) سمتِ فرانت: کلیدهای تازه در zod و پایانِ صفرِ ساختگی")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


b = read(TS_BASKET)
ck("اسکیمای ردیف qty را می‌شناسد (زود آن را دور نمی‌ریزد)", "qty:" in b)
ck("اسکیمای ردیف value_toman را می‌شناسد", "value_toman:" in b)
ck("اسکیمای ردیف weight_source را می‌شناسد", "weight_source:" in b)
ck("اسکیمای ردیف asset_class را می‌شناسد", "asset_class:" in b)
_mut = b.split("mutationFn")[1][:1200] if "mutationFn" in b else ""
ck("mutation تعداد را به سرور می‌فرستد", "qty" in _mut, _mut[:120])
ck("mutation نام و صنعت را هم می‌فرستد", "name" in _mut and "sector" in _mut)

p = read(TS_PORT)
ck("اسکیمای limits ارزشِ کل را می‌شناسد", "portfolio_value_toman" in p)
ck("اسکیمای limits ترکیبِ طبقات را می‌شناسد", "class_mix_pct" in p)
ck("اسکیمای limits منشأِ وزن را می‌شناسد", "weight_source" in p)
# جدولِ پرتفوی با کلیدِ ['portfolio'] می‌خواند؛ اگر نوشتن فقط کلیدِ تصمیم را
# بی‌اعتبار کند، POST موفق است ولی ردیف هرگز در جدول نمی‌نشیند.
bk = read(TS_BASKET)
_helper = bk.split("function invalidateDecisionFeeds", 1)
_body = _helper[1].split("\n}", 1)[0] if len(_helper) == 2 else ""
ck("هلپرِ بی‌اعتبارسازی هر دو کلیدِ فید را می‌شناسد",
   "BASKET_QUERY_KEY" in _body and "PORTFOLIO_QUERY_KEY" in _body, _body[:120])
ck("هر دو نوشتن (POST و DELETE) از همان هلپر رد می‌شوند",
   bk.count("onSuccess") == 2 and bk.count("invalidateDecisionFeeds(qc)") == 2,
   f"onSuccess={bk.count('onSuccess')} helper={bk.count('invalidateDecisionFeeds(qc)')}")
ck("کلیدِ فیدِ جدول از همان‌جا صادر می‌شود که خوانده می‌شود",
   "export const PORTFOLIO_QUERY_KEY" in p and 'queryKey: PORTFOLIO_QUERY_KEY' in p
   and "PORTFOLIO_QUERY_KEY" in bk)

t = read(TS_TARGET)
_bd = t.split("export function buildDelta", 1)
_bd = _bd[1].split("\n}", 1)[0] if len(_bd) == 2 else ""
ck("buildDelta دیگر برای طبقاتِ غیرسهامی کسریِ صفر نمی‌سازد",
   ": 0;\n" not in _bd or "null" in _bd)
# «طلا» دو ردیفِ هدف دارد (فیزیکی + گواهی) ولی تابلو یک طبقه می‌دهد. اگر همان
# درصد روی هر دو ردیف بنشیند، «پوشش» ۱۸۷٪ می‌شود و کارتِ ری‌بالانس دو برابرِ
# لازم فروش پیشنهاد می‌دهد — پس اندازه باید به یک ردیفِ حمل‌کننده بخوابد.
ck("طبقاتِ هم‌alias در سطحِ گروه سنجیده می‌شوند", "CLASS_ALIAS[c.id] ?? c.id" in _bd
   and "groups" in _bd and "isCarrier" in _bd, _bd[:160])
ck("فقط ردیفِ حمل‌کننده عدد می‌گیرد؛ بقیه null می‌مانند",
   "if (isCarrier)" in _bd and _bd.count("pct = scaled.pct") == 1
   and "else {\n        reason =" in _bd, f"carrier-branch={_bd.count('pct = scaled.pct')}")
ck("دلتا با هدفِ جمعِ طبقه سنجیده می‌شود، نه هدفِ سطرِ تنها",
   "pct - goalPct" in _bd and "pct - c.pct" not in _bd)
# جانشینِ سهام: اگر وزنِ *همهٔ* ردیف‌ها جمع شود، سبدِ تک‌صندوقِ طلا هم «سهام ۱۰۰٪»
# می‌گیرد و همان وزن بارِ دوم شمرده می‌شود.
ck("جانشینِ سهام فقط ردیفِ بی‌طبقه/سهامی را جمع می‌کند",
   "eqUnknownRows" in _bd and "rowClassKey(ac)" in _bd
   and "holdings.reduce((s, h) => s + (typeof h.weight_eff_pct" not in _bd)
_ms = t.split("export function mixSentence", 1)
_ms = _ms[1].split("\n}", 1)[0] if len(_ms) == 2 else ""
ck("جملهٔ headline هم همان هدفِ گروه را می‌گوید",
   "classTargetPct ?? worst.targetPct" in _ms, _ms[:120])

# دوناتِ «تحلیل دارایی‌ها» و نوارِ شکاف باید یک عدد را بگویند. دونات پیش از این
# جمعِ وزنِ همهٔ پوزیشن‌ها را «سهام» می‌خواند و طبقات را از ارزشِ دستی.
_dk = read(TS_DONUT)
ck("دونات هم از همان buildDelta می‌خواند، نه از وزنِ دوباره‌ساختهٔ خودش",
   "buildDelta(" in _dk and "equityWeightPct" not in _dk,
   f"buildDelta={'buildDelta(' in _dk} equityWeightPct={'equityWeightPct' in _dk}")
_sa = read(TS_STD)
ck("compareToStandard ردیف‌های اندازه‌گیری‌شده را می‌گیرد نه ورودیِ خام",
   "export function compareToStandard(rows: DeltaRow[])" in _sa
   and "equityWeightPct" not in _sa, _sa.split("compareToStandard", 1)[:1][0][-80:])
ck("منبعِ اندازهٔ هر ردیف در DeltaRow ثبت می‌شود (dونات/نوار یکی بگویند)",
   "measure: DeltaMeasure" in t and "'class_mix'" in t and "'asset_value'" in t)

print(f"\n{PASS} بررسی سبز، {len(FAIL)} شکست")
if FAIL:
    print("شکست‌ها:\n  - " + "\n  - ".join(FAIL))
sys.exit(1 if FAIL else 0)
