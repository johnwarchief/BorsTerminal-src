"""برابریِ «متنِ فرمولِ مالک» با «آنچه در جدول اجرا می‌شود».

منبعِ حقیقت، فایل‌هایِ چهارگانۀ دسکتاپ‌اند (نه ترجمۀ داخلیِ ما):

    فیلتر جت.txt          حجم مشکوک.txt          کف روبی صف فروش.txt        نقطه زنی.txt

این ابزار همان متن را یک‌به‌یک با پایگاهِ داده می‌سازد (با `[ih][0]` = نشستِ
جاری، چون در نگاشتِ TSETMC شاخصِ صفر «امروز» است) و کنارِ پرچمِ واقعیِ
`api/market.py` می‌گذارد. اختلافِ عددی اگر بود، یعنی یا کد از متن فاصله
گرفته یا متنِ فایل با رأیِ مالکِ بعدی به‌روز نشده است.

اجرا:  python tools/tape_formula_parity.py

پایهٔ سنجیده‌شده روی تابلوی بستهٔ ۲۰۲۶۰۹۲۳ (۳٬۸۴۵ ردیف):
  جت          کد=۱   فایل=۱    ✓ یکی
  حجم مشکوک   کد=۱۱۳ فایل=۱۵۱  — هر ۵۵ ردیفِ «فقط فایل» کم‌سابقه‌اند؛ فایل همیشه
                                بر ۳۰ تقسیم می‌کند پس مبنای نمادِ ۱۰‌روزه یک‌سوم
                                درمی‌آید و «۳ برابر» بی‌دلیل رد می‌شود.
  نقطه‌زنی    کد=۳۸  فایل=۷۲   — ۳۱ ردیف همان علت، بقیه به‌خاطرِ اینکه فایل کفِ
                                امروز را هم داخلِ «کف ۳۰ روزه» می‌شمارد.
  کفروبی      قابلِ سنجش نیست: qd1 = تعدادِ معاملاتِ نشستِ پیش در هیچ جدولی
                                نیست (daily_prices ستونِ z_tot_tran ندارد)؛ کد
                                تعدادِ امروز را جانشین می‌کند → ۷۳ ردیف.
"""
import hashlib
import io
import os
import re
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

DESKTOP = os.path.join(os.environ.get("USERPROFILE", "C:/Users/PCMOD"), "Desktop")
FILES = {
    "جت": "فیلتر جت.txt",
    "حجم مشکوک": "حجم مشکوک.txt",
    "کفروبی": "کف روبی صف فروش.txt",
    "نقطه‌زنی": "نقطه زنی.txt",
}

SRC = "api/market.py"
SQL = re.search(r'query = """(.*?)"""', open(SRC, encoding="utf-8").read(), re.S)
if not SQL:
    sys.exit("کوئریِ تابلو در api/market.py پیدا نشد")
BOARD_SQL = SQL.group(1)

# دو مجموعۀ تازه که در کوئریِ تابلو نیست: مجموعِ ۲۹ نشستِ پیش و کمینۀ ۲۸ نشستِ پیش
# (هر دو «امروز» را هم می‌خواهند، چون فایل [ih][0] را داخلِ بازه می‌شمارد).
EXTRA_SQL = """
    WITH iso AS (SELECT MAX(d_even) AS d FROM market_watch),
    hist AS (
        SELECT symbol, dt, MAX(high) high, MAX(low) low, MAX(volume) volume FROM (
            SELECT i.l_val18 symbol, h.date dt, h.high, h.low, h.volume
            FROM price_history h JOIN instruments i ON i.l_val18 = h.symbol
            UNION ALL
            SELECT i.l_val18, printf('%04d-%02d-%02d', d.d_even/10000, (d.d_even/100)%100, d.d_even%100),
                   d.price_max, d.price_min, d.q_tot_tran
            FROM daily_prices d JOIN instruments i ON i.ins_code = d.ins_code
        ) GROUP BY symbol, dt
    ),
    rk AS (SELECT symbol, dt, low, volume,
                  ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY dt DESC) rn
           FROM hist
           WHERE dt <= (SELECT printf('%04d-%02d-%02d', d/10000, (d/100)%100, d%100) FROM iso))
SELECT symbol,
       SUM(CASE WHEN rn BETWEEN 1 AND 29 THEN volume END) AS prior29_vol,
       MIN(CASE WHEN rn BETWEEN 1 AND 28 THEN low END)    AS min_low_1_28,
       SUM(CASE WHEN rn BETWEEN 1 AND 29 THEN 1 END)      AS prior_n
FROM rk GROUP BY symbol
"""

conn = sqlite3.connect("market.db")
df = pd.read_sql_query(BOARD_SQL, conn)
df = df[df["d_even"] == df["d_even"].max()].copy()
ex = pd.read_sql_query(EXTRA_SQL, conn)
df = df.merge(ex, on="symbol", how="left")
conn.close()

n = lambda s: pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan)

# همان نرمال‌سازیِ api/market.py (تابلو «q_tot_tran» می‌دهد و درصدِ تغییر ساخته
# می‌شود)؛ بیرونِ این، tape_flags ستون‌ها را پیدا نمی‌کند.
df["tvol"] = n(df["q_tot_tran"])
_py, _pc, _chg = n(df["price_yesterday"]), n(df["p_closing"]), n(df["price_change"])
_py_ok = _py.where(_py > 1.0)
_pct = ((_pc - _py_ok) / _py_ok * 100).round(2)
_pct = _pct.fillna(_chg / _py_ok * 100)
df["percent_change"] = _pct.where(_pct.abs() <= 100.0)

from tape_flags import apply_tape_flags  # noqa: E402

df = apply_tape_flags(df)

for col in ("z_tot_tran", "prior29_vol", "min_low_1_28", "month_avg_vol",
            "min30_low", "prev_day_vol", "p_last", "p_closing", "p_min",
            "buy_i_vol", "buy_count_i", "sell_i_vol", "sell_count_i"):
    if col in df.columns:
        df[col] = n(df[col])

# ── عبارت‌های مشترک، دقیقاً به سبکِ فایل ────────────────────────────────────
today_vol = df["tvol"].fillna(0.0)
# Σ[ih][0..29].QTotTran5J = امروز + ۲۹ نشستِ پیش  →  ÷30
base_file = (today_vol + df["prior29_vol"]) / 30.0
# Σ[ih][0..29] برای نقطه‌زنی هم همان مخرج است
min_file = pd.concat([df["p_min"], df["min_low_1_28"]], axis=1).min(axis=1)   # [ih][0..28].PriceMin
avg_code = df["month_avg_vol"].where(lambda s: s > 0)

pl, pc, plp, tmin = df["p_last"], df["p_closing"], df["percent_change"], df["p_min"]
tno, zd1 = df["z_tot_tran"], df["prev_day_vol"]
buyer = (df["buy_i_vol"] / df["buy_count_i"].where(lambda s: s > 0)) / (
    df["sell_i_vol"] / df["sell_count_i"].where(lambda s: s > 0))


prior_short = pd.to_numeric(df["prior_n"], errors="coerce").fillna(0) < 29


def rep(name, code_col, file_rule):
    code = df[code_col].astype(bool)
    file_rule = file_rule.fillna(False)
    print(f"\n== {name}   کد={int(code.sum())}   فایل={int(file_rule.sum())}   "
          f"مشترک={int((code & file_rule).sum())}")
    only_code, only_file = (code & ~file_rule), (file_rule & ~code)
    if only_code.any():
        print(f"   فقط در کد ({int(only_code.sum())}): {df.loc[only_code, 'symbol'].tolist()[:12]}")
    if only_file.any():
        print(f"   فقط در فایل ({int(only_file.sum())}): {df.loc[only_file, 'symbol'].tolist()[:12]}")
    if not only_code.any() and not only_file.any():
        print("   ✓ یکی‌اند")
        return
    # علتِ اختلاف: فایل همیشه بر ۳۰ تقسیم می‌کند، پس نمادِ کم‌سابقه مبنایِ
    # مصنوعاً کوچکی دارد و شرطِ «۳ برابر» آسان می‌شود.
    print(f"   از اینها کم‌سابقه (کمتر از ۲۹ نشستِ پیش): "
          f"فقط‌فایل={int((only_file & prior_short).sum())}/{int(only_file.sum())}   "
          f"فقط‌کد={int((only_code & prior_short).sum())}/{int(only_code.sum())}")


# حجم مشکوک: tvol > 3*avg([ih][0..29]) && tno > 50
rep("حجم مشکوک", "f_susp",
    (today_vol > 3 * base_file) & (tno > 50))

# جت: سه قیدِ حجمی/قدرتی + پلکانِ هشت‌نقطه‌ای + tno>1 + tno>100
ladder_ok = pd.concat([(pl > df[f"h{k}_max"]) for k in (2, 5, 9, 19, 29, 39, 49, 59)], axis=1)
jet_file = ((today_vol > 3 * base_file) & (buyer >= 1.5) & (pl >= pc) & (plp > 0)
            & (tno > 1) & ladder_ok.notna().all(axis=1) & ladder_ok.all(axis=1) & (tno > 100))
rep("جت", "f_jet", jet_file)

# نقطه‌زنی: cfield2 = round((pc-min)/pc*100*100)/100 < 3 && tvol > avg && tno > 5
cfield2 = ((pc - min_file) / pc * 100 * 100).round(2) / 100
rep("نقطه‌زنی", "f_noqteh",
    (min_file > 0) & (cfield2 < 3) & (today_vol > 1 * base_file) & (tno > 5))

# کفروبی: qd1 در فایل «تعدادِ معاملاتِ نشستِ پیش» است؛ چنین ستونی در
# price_history و daily_prices نیست → بازگشتِ معنادار ممکن نیست، نه صفر.
print("\n== کفروبی   (qd1 = تعداد معاملاتِ نشستِ پیش)")
print(f"   ستونِ لازم در بانک هست؟  {'qd1' in df.columns or 'prev_day_tran' in df.columns}")
print(f"   کد فعلاً تعدادِ معاملاتِ امروز را جانشین می‌کند → {int(df['f_roobi'].sum())} ردیف")

# چقدر «مبنایِ فایل» از «مبنایِ کد» سخت‌گیرانه‌تر است
cmp_ = base_file.notna() & avg_code.notna() & (avg_code > 0)
ratio = (base_file[cmp_] / avg_code[cmp_])
print(f"\nمبنایِ حجم: فایل امروز را هم داخلِ میانگین می‌آورد → نسبتِ فایل/کد  "
      f"میانه={ratio.median():.3f}  کمینه={ratio.min():.3f}  بیشینه={ratio.max():.3f}")

# فایل‌ها هنوز همان‌اند؟ (تا ابزار از منبعش جدا نیفتد)
print("\nفایل‌هایِ مرجع:")
for k, fn in FILES.items():
    p = os.path.join(DESKTOP, fn)
    if os.path.isfile(p):
        txt = io.open(p, encoding="utf-8-sig").read().strip()
        print(f"  {k:<12} {len(txt):>5} نویسه  sha8={hashlib.sha256(txt.encode()).hexdigest()[:8]}")
    else:
        print(f"  {k:<12} پیدا نشد ← {p}")
