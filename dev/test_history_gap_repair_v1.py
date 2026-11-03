# dev/test_history_gap_repair_v1.py — RC4 (بخشِ C): ترمیمِ شکاف رویِ بانکِ موقتِ مستقل
# هیچ‌مسیری به market.db ندارد (tempfile.mkdtemp)؛ بی‌شبکه. ثابت می‌کند:
#   • missing_blocks فقط «درِ منبع هست، بانک نیست» را می‌شمارد، نه تعطیلی/جمعه را.
#   • repair رویِ روزهایِ مفقود کندل می‌نشیند؛ ردیفِ موجود را حذف/بازنویسی/مکرر نمی‌کند.
#   • idempotent است: اجرایِ دوم صفر نوشتن.
#   • dry_run هیچ اثری رویِ بانک نمی‌گذارد.
#   • open/last مفقود با close جعل نمی‌شود؛ روزِ بی‌معامله (vol≤0) کندل نمی‌شود.
#   • ردیفِ «منتشرشده» با barِ board جای خود را نمی‌دهد (قیدِ اولویتِ src).
import os
import sys
import io
import tempfile
import sqlite3

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import candle_contract as CC                    # noqa: E402
from dev import history_gap_repair as H         # noqa: E402

P = F = 0


def check(name, got, want):
    global P, F
    if got == want:
        P += 1
        print(f"  ✓ {name}")
    else:
        F += 1
        print(f"  ✗ {name}: got={got!r} want={want!r}")


def new_db():
    path = os.path.join(tempfile.mkdtemp(prefix="gaprepair_"), "t.db")
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE price_history (symbol TEXT, date TEXT, open REAL, high REAL,"
                " low REAL, close REAL, volume REAL, last REAL, value REAL, src TEXT,"
                " PRIMARY KEY (symbol, date))")
    con.commit()
    return con


def mk(date, o, c, vol=1000, last=None, src=CC.SRC_PUBLISHED):
    return CC.candle("خودرو", date, o, o, o, c, vol, last, None, src)


def dates(con):
    return [r[0] for r in con.execute(
        "SELECT date FROM price_history WHERE symbol='خودرو' ORDER BY date")]


# ── ۱) missing_blocks: فقطِ شکافِ واقعی، نه تعطیلی
expected = ["2024-01-06", "2024-01-07", "2024-01-08", "2024-01-09", "2024-01-10"]
actual = ["2024-01-06", "2024-01-10"]
check("۱ بلوکِ مفقود = میانیِ ۳ روزه", H.missing_blocks(expected, actual),
      [("2024-01-07", "2024-01-09", 3)])
check("۱ بی‌شکاف → فهرستِ خالی", H.missing_blocks(expected, expected), [])

# ── ۲) repair رویِ بانکِ موقت: مفقود پر می‌شود، موجود دست‌نخورد
con = new_db()
con.execute(CC.UPSERT_SQL, CC.upsert_row(mk("2024-01-06", 1000, 1000, last=1010)))
con.execute(CC.UPSERT_SQL, CC.upsert_row(mk("2024-01-10", 1005, 1010, last=1012)))
con.commit()
bars = [mk("2024-01-06", 1000, 1000, last=1010),          # موجود (باید نادیده/بی‌بازنویسی)
        mk("2024-01-07", 980, 990, last=995),             # مفقود
        mk("2024-01-08", 990, 985, last=None),            # مفقود، بی‌last
        mk("2024-01-10", 1005, 1010, last=1012)]          # موجود
filled, present, no_src = H.repair_from_bars(con, "خودرو", bars, dry_run=False)
check("۲ دو روزِ مفقود پر شد", filled, 2)
check("۲ دو روزِ موجود رد شد (بی‌duplicate)", present, 2)
check("۲ تاریخ‌هایِ نهاییِ صعودی و کامل", dates(con),
      ["2024-01-06", "2024-01-07", "2024-01-08", "2024-01-10"])

# ── ۳) idempotent: اجرایِ دوم هیچ چیز نمی‌نویسد
f2, p2, _ = H.repair_from_bars(con, "خودرو", bars, dry_run=False)
check("۳ اجرایِ دوم صفر نوشتن", f2, 0)
check("۳ تعدادِ سطر ثابت ماند", len(dates(con)), 4)

# ── ۴) dry_run هیچ اثری نمی‌گذارد
con2 = new_db()
w, pr, ns = H.repair_from_bars(con2, "خودرو", [mk("2024-01-07", 1, 1)], dry_run=True)
check("۴ dry_run بشمارد ولی ننویسد", (w, pr, ns), (1, 0, 0))
check("۴ بانکِ dry_run خالی ماند", dates(con2), [])

# ── ۵) جعلی‌سازیِ ممنوع: بی‌barِ مبدأ چیزی ساخته نمی‌شود؛ lastِ مفقود None می‌ماند
row8 = con.execute("SELECT last FROM price_history WHERE date='2024-01-08'").fetchone()[0]
check("۵ lastِ مفقود با close جعل نشد (None ماند)", row8, None)
check("۵ روزی که بارِ مبدأ نداشت ساخته نشد", "2024-01-09" in dates(con), False)

# ── ۶) روزِ بی‌معامله کندل نمی‌شود (vol≤0 → candle None)
check("۶ حجمِ صفر → None، نه کندلِ جعلی", mk("2024-01-11", 1000, 1000, vol=0), None)

# ── ۷) اولویتِ src: ردیفِ «منتشرشده» با barِ board بازنویسی نمی‌شود
con3 = new_db()
con3.execute(CC.UPSERT_SQL, CC.upsert_row(mk("2024-02-01", 500, 500, last=505)))   # published
con3.commit()
board_bar = CC.candle("خودرو", "2024-02-01", 1, 1, 1, 1, 50, None, None, CC.SRC_BOARD)
# بارِ board رویِ روزِ *موجود* است → repair آن را رد می‌کند؛ و حتی UPSERTِ مستقیم هم
# ردیفِ published را با board جایگزین نمی‌کند (قیدِ WHERE).
f7, p7, _ = H.repair_from_bars(con3, "خودرو", [board_bar], dry_run=False)
close_after = con3.execute("SELECT close FROM price_history WHERE date='2024-02-01'").fetchone()[0]
check("۷ ردیفِ published بی‌بازنویسی ماند (close=500)", close_after, 500.0)
check("۷ روزِ موجود → present، نه نوشتن", (f7, p7), (0, 1))

for c in (con, con2, con3):
    c.close()

print(f"\nنتیجه: {P} سبز، {F} قرمز")
sys.exit(1 if F else 0)
