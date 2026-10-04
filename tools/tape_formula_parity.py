"""برابریِ «متنِ فرمولِ مالک» با «آنچه در جدول اجرا می‌شود».

منبعِ حقیقت، پنج فایلِ دسکتاپ‌اند (نه ترجمۀ داخلیِ ما):

    فیلتر جت.txt   حجم مشکوک.txt   کف روبی صف فروش.txt   نقطه زنی.txt   الگوی ساعت.txt

این ابزار همان متن را یک‌به‌یک با پایگاهِ داده می‌سازد (با `[ih][0]` = نشستِ
جاری، چون در نگاشتِ TSETMC شاخصِ صفر «امروز» است) و کنارِ پرچمِ واقعیِ
`api/market.py` می‌گذارد. اختلافِ عددی اگر بود، یعنی یا کد از متن فاصله
گرفته یا متنِ فایل با رأیِ مالکِ بعدی به‌روز نشده است.

اجرا:  python tools/tape_formula_parity.py

پایهٔ سنجیده‌شده روی تابلوی *میانِ نشست* ۱۴۰۵-۰۷-۰۴ (۳٬۳۱۳ ردیفِ معامله‌شده):
  جت          کد=۰   فایل=۰   ✓ یکی
  حجم مشکوک   کد=۴۴  فایل=۸۲  — هر ۳۸ ردیفِ «فقط فایل» کم‌سابقه‌اند و هیچ ردیفی
                                «فقط کد» نیست.
  الگوی ساعت  کد=۶۰  فایل=۸۳  — همان، ۲۳ ردیفِ کم‌سابقه.
  نقطه‌زنی    کد=۱۴  فایل=۲۶  — ۱۶ ردیفِ کم‌سابقه؛ ۴ ردیف «فقط کد» که هر چهار
                                درِ پنجرۀِ فایل کمینۀِ صفر دارند (نشستِ
                                بی‌معامله). کد آن صفر را از کف بیرون می‌گذارد —
                                تنها انحرافِ ثبت‌شده به سمتِ قبولِ بیشتر، و
                                دلیلش در api/market.py (`AND low > 0`) است.
  کفروبی      سه قیدِ اول سنجیده می‌شود (۲۹۱ ردیف)؛ قیدِ چهارم (qd1) از
                                نخستین نشستِ پس از این نسخه پر می‌شود، چون
                                ستونش تازه به daily_prices افزوده شده است.

دو انحرافِ عمدیِ کد از متنِ فایل (ثبت‌شده در رأیِ ۱۸):
  ۱) مبناءِ حجم بر تعدادِ نشست‌هایِ *موجود* تقسیم می‌شود (کفِ ۱۰)، نه ۳۰ِ ثابت:
     بانکِ ما برایِ نیمیِ تابلو ۳۰ نشستِ کامل ندارد.
  ۲) قیدِ چهارمِ کف‌روبی تا نبودِ ستونش سنجیده نمی‌شود و جانشین هم نمی‌خواهد.
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
    "الگوی ساعت": "الگوی ساعت.txt",
    "پول هوشمند": "ورود پول هوشمند.txt",
    "کد به کد": "ورود پول هوشمند و کد به کد حقوقی به حقیقی.txt",
}


def resolve(fname: str) -> str:
    """اول دسکتاپ (مبدأِ فایل‌هایِ مالک)، بعد `docs/` — نسخهٔ کامیت‌شده درِ ریپو."""
    for d in (DESKTOP, "docs"):
        p = os.path.join(d, fname)
        if os.path.isfile(p):
            return p
    return os.path.join(DESKTOP, fname)

SRC = "api/market.py"
SQL = re.search(r'(?:query|_BOARD_SQL) = """(.*?)"""', open(SRC, encoding="utf-8").read(), re.S)
if not SQL:
    sys.exit("کوئریِ تابلو در api/market.py پیدا نشد")
BOARD_SQL = SQL.group(1)

# پنجرۀ [ih] از `tape_history` ساخته می‌شود — همان آرایۀِ خودِ سایت
# (`GetClosingPriceDailyAllInst`، با ردیفِ صفر برایِ نشستِ بی‌معامله). پنجرۀِ
# پیشینِ این ابزار از price_history ∪ daily_prices بود و پس از board_hist_fv
# (سینکِ [ih]) با منبعِ فایل واگرفت شد: اندازه‌گیریِ ۱۴۰۵-۰۷-۱۲ — غمينو3 درِ
# tape_history ۱٬۰۳۹٬۲۹۸ و درِ پنجرۀِ کهنه ۴۷٬۶۸۸٬۷۵۶ (سریِ والِد درِ
# price_history رویِ نامِ یکسان می‌نشیند). مرجعِ فایل باید مستقل از
# کوئریِ تابلو ساخته شود، ولی از همانِ منبعِ فایل.
EXTRA_SQL = """
WITH th AS (
    SELECT i.l_val18 AS symbol,
           ROW_NUMBER() OVER (PARTITION BY t.ins_code ORDER BY t.d_even DESC) AS rn,
           t.q_tot_tran5j AS volume, t.price_min AS low
    FROM tape_history t JOIN instruments i ON i.ins_code = t.ins_code
)
SELECT symbol,
       SUM(CASE WHEN rn <= 30 THEN volume END) AS x_sum30,
       MIN(CASE WHEN rn <= 29 THEN low END)    AS min_low_1_28,
       MAX(rn)                                  AS prior_n
FROM th WHERE rn <= 60 GROUP BY symbol
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
# jet_flag به percent_last (آخرین نسبت به دیروز) نیاز دارد؛ محصول آن را در
# pandas می‌سازد، این ابزارِ خام هم باید بسازد وگرنه KeyError می‌دهد.
_pl = n(df["p_last"])
df["percent_last"] = ((_pl - _py_ok) / _py_ok * 100).round(2)

from tape_flags import apply_tape_flags  # noqa: E402

df = apply_tape_flags(df)

for col in ("z_tot_tran", "x_sum30", "min_low_1_28", "month_avg_vol",
            "min30_low", "prev_day_vol", "p_last", "p_closing", "p_min",
            "buy_i_vol", "buy_count_i", "sell_i_vol", "sell_count_i",
            "sell_n_vol", "buy_n_vol"):
    if col in df.columns:
        df[col] = n(df[col])

# ── عبارت‌های مشترک، دقیقاً به سبکِ فایل ────────────────────────────────────
today_vol = df["tvol"].fillna(0.0)
# Σ[ih][0..29].QTotTran5J = امروز + ۲۹ نشستِ پیش  →  ÷30
# Σ[ih][0..29] خودش امروز را داخل دارد → تقسیم بر ۳۰، بدون افزودنِ دوبارهٔ امروز
base_file = df["x_sum30"] / 30.0
# Σ[ih][0..29] برای نقطه‌زنی هم همان مخرج است
min_file = df["min_low_1_28"]   # [ih][0..28].PriceMin — پنجره خودش امروز را دارد
avg_code = df["month_avg_vol"].where(lambda s: s > 0)

pl, pc, plp, tmin = df["p_last"], df["p_closing"], df["percent_change"], df["p_min"]
tno, zd1 = df["z_tot_tran"], df["prev_day_vol"]
buyer = (df["buy_i_vol"] / df["buy_count_i"].where(lambda s: s > 0)) / (
    df["sell_i_vol"] / df["sell_count_i"].where(lambda s: s > 0))


prior_short = pd.to_numeric(df["prior_n"], errors="coerce").fillna(0) < 30


def rep(name, code_col, file_rule):
    code = df[code_col].astype(bool)
    # رفتارِ خودِ ExecFilter: شاخصِ [ih][29] از طولِ آرایه بیرون بزند استثنا
    # می‌دهد و ردیف از *همان* فیلتر می‌افتد — کم‌سابقه درِ فایل هم «نسنجیده»
    # است، نه تقسیمِ ناقص (سرآمدِ tape_flags.py).
    file_rule = file_rule.fillna(False) & ~prior_short
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
    # علتِ «فقط فایل»: فایل بر ۳۰ِ ثابت تقسیم می‌کند، پس نمادِ کم‌سابقه مبنایِ
    # مصنوعاً کوچکی دارد و شرطِ «۳ برابر» آسان می‌شود؛ کد بر تعدادِ نشست‌هایِ
    # موجود تقسیم می‌کند و زیرِ ۱۰ نشست اصلاً داوری نمی‌کند (هر دو سخت‌گیرانه‌تر).
    print(f"   از اینها کم‌سابقه (کمتر از ۲۹ نشستِ پیش): "
          f"فقط‌فایل={int((only_file & prior_short).sum())}/{int(only_file.sum())}   "
          f"فقط‌کد={int((only_code & prior_short).sum())}/{int(only_code.sum())}")
    # علتِ «فقط کد» — جهتِ خطرناک، پس نامش را می‌نویسیم. تنها انحرافِ مجازِ
    # شناخته‌شده: صفرِ نشستِ بی‌معامله درِ کمینۀِ فایل، که کد از کف بیرون
    # می‌گذارد (api/market.py: `AND low > 0`).
    if only_code.any():
        zlow = only_code & (pd.to_numeric(df["min_low_1_28"], errors="coerce") == 0)
        if int(zlow.sum()):
            print(f"   فقط‌کد با کمینۀِ صفرِ فایل (کد صفرِ نشستِ بی‌معامله را از کف "
                  f"بیرون می‌گذارد — انحرافِ ثبت‌شده): {int(zlow.sum())}/{int(only_code.sum())}")
        rest = only_code & ~zlow
        if rest.any():
            print("   فقط‌کدِ بی‌دلیل (باید صفر باشد): "
                  f"{int(rest.sum())} → {df.loc[rest, 'symbol'].tolist()[:8]}")


# حجم مشکوک: tvol > 3*avg([ih][0..29]) && tno > 50
rep("حجم مشکوک", "f_susp",
    (today_vol > 3 * base_file) & (tno > 50))

# جت: سه قیدِ حجمی/قدرتی + پلکانِ هشت‌نقطه‌ای + tno>1 + tno>100
ladder_ok = pd.concat([(pl > df[f"h{k}_max"]) for k in (2, 5, 9, 19, 29, 39, 49, 59)], axis=1)
jet_file = ((today_vol > 3 * base_file) & (buyer >= 1.5) & (pl >= pc) & (plp > 0)
            & (tno > 1) & ladder_ok.notna().all(axis=1) & ladder_ok.all(axis=1) & (tno > 100))
rep("جت", "f_jet", jet_file)

# الگوی ساعت: pl >= pc*1.02 && tvol > 1*avg([ih][0..29]) && tno > 30
rep("الگوی ساعت", "f_clock",
    (pl >= pc * 1.02) & (today_vol > 1 * base_file) & (tno > 30))

# نقطه‌زنی: cfield2 = round((pc-min)/pc*100*100)/100 < 3 && tvol > avg && tno > 5
cfield2 = ((pc - min_file) / pc * 100 * 100).round(2) / 100
rep("نقطه‌زنی", "f_noqteh",
    (min_file > 0) & (cfield2 < 3) & (today_vol > 1 * base_file) & (tno > 5))

# پول هوشمند (سطرِ ۱ فایل): tvol > 1.5*avg([ih][0..29]) && BuyI/ctBuyI >= SellI/ctSellI
# && pl >= pc && plp > 0 — «plp» درِ ExecFilter درصدِ **آخرین** است (percent_last).
plp_last = df["percent_last"] if "percent_last" in df.columns else plp
sm_file = ((today_vol > 1.5 * base_file) & (buyer >= 1.0) & (pl >= pc) & (plp_last > 0))
rep("پول هوشمند", "f_smart", sm_file)

# کد به کد: همان چهار قید + Buy_I_Volume > 0.5*tvol && Sell_N_Volume > 0.5*tvol
rep("کد به کد", "f_legal",
    sm_file & (df["buy_i_vol"] > 0.5 * today_vol) & (df["sell_n_vol"] > 0.5 * today_vol))

# کفروبی: qd1 در فایل «تعدادِ معاملاتِ نشستِ پیش» است؛ چنین ستونی در
# price_history و daily_prices نیست → بازگشتِ معنادار ممکن نیست، نه صفر.
print("\n== کفروبی   (qd1 = تعداد معاملاتِ نشستِ پیش)")
_has_qd1 = 'qd1' in df.columns or 'prev_day_tran' in df.columns
print(f"   ستونِ لازم در بانک هست؟  {_has_qd1}")
_qd1_have = int(df['prev_day_tran'].notna().sum()) if 'prev_day_tran' in df.columns else 0
print(f"   کد بدونِ قیدِ چهارم (سه قیدِ اول) → {int(df['f_roobi'].sum())} ردیف؛ "
      f"با قیدِ qd1 سنجیده می‌شود به‌محضِ این‌که prev_day_tran پر شود "
      f"(ردیف‌هایِ دارای qd1: {_qd1_have} از {len(df)})")

# چقدر «مبنایِ فایل» از «مبنایِ کد» سخت‌گیرانه‌تر است
cmp_ = base_file.notna() & avg_code.notna() & (avg_code > 0)
ratio = (base_file[cmp_] / avg_code[cmp_])
print(f"\nمبنایِ حجم: فایل امروز را هم داخلِ میانگین می‌آورد → نسبتِ فایل/کد  "
      f"میانه={ratio.median():.3f}  کمینه={ratio.min():.3f}  بیشینه={ratio.max():.3f}")

# فایل‌ها هنوز همان‌اند؟ (تا ابزار از منبعش جدا نیفتد)
print("\nفایل‌هایِ مرجع:")
for k, fn in FILES.items():
    p = resolve(fn)
    if os.path.isfile(p):
        txt = io.open(p, encoding="utf-8-sig").read().strip()
        print(f"  {k:<12} {len(txt):>5} نویسه  sha8={hashlib.sha256(txt.encode()).hexdigest()[:8]}")
    else:
        print(f"  {k:<12} پیدا نشد ← {p}")
