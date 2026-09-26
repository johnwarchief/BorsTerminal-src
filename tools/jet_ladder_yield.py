"""چرا «زیاد کردن تایم‌فریم» نامزدها را زیاد نمی‌کند؟ — بازدهِ جت به ازای هر پلکان.

کوئری را از خودِ api/market.py می‌خواند تا همان مسیرِ واقعیِ تابلو سنجیده شود.
خروجی برای هر گزینهٔ «بازه» (۲..۵۹ روزه): چند ردیف اصلاً همهٔ نقاطِ آن پلکان را
دارند و چند ردیف زیرِ همان بازه «جت» می‌خورند.
"""
import re
import sqlite3
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from tape_flags import JET_LADDER, resistance_ladder_high, jet_flag  # noqa: E402

SRC = "api/market.py"
SQL = re.search(r'query = """(.*?)"""', open(SRC, encoding="utf-8").read(), re.S)
if not SQL:
    sys.exit("کوئریِ تابلو در api/market.py پیدا نشد — ابزار باید به‌روز شود")

conn = sqlite3.connect("market.db")
df = pd.read_sql_query(SQL.group(1), conn)
df = df[df["d_even"] == df["d_even"].max()].copy()

df["tvol"] = pd.to_numeric(df["q_tot_tran"], errors="coerce").astype(float).fillna(0.0)
_py = pd.to_numeric(df["price_yesterday"], errors="coerce")
_pc = pd.to_numeric(df["p_closing"], errors="coerce")
_chg = pd.to_numeric(df["price_change"], errors="coerce")
pct = ((_pc - _py.where(_py > 1.0)) / _py.where(_py > 1.0) * 100).round(2)
pct = pct.fillna(_chg / _py.where(_py > 1.0) * 100)
df["percent_change"] = pct.where(pct.abs() <= 100.0)

print(f"ردیفِ نشستِ جاریِ تابلو: {len(df)}\n")
print(f"{'بازه':>8}  {'نقاطِ لازم':>10}  {'تاریخچه کافی':>14}  {'جت':>6}")
for lb in JET_LADDER:
    pts = [k for k in JET_LADDER if k <= lb]
    stack = pd.concat(
        [pd.to_numeric(df[f"h{k}_max"], errors="coerce").where(lambda s: s > 0) for k in pts],
        axis=1,
    )
    have = int(stack.notna().all(axis=1).sum())
    flags = int(jet_flag(df, lookback=lb).sum())
    print(f"{lb:>6}روز  {len(pts):>10}  {have:>9} ({have / len(df) * 100:>3.0f}%)  {flags:>6}")

# سقفِ مقاومती که «باید شکسته شود» با بازه بالا می‌رود — پس سخت‌تر، نه آسان‌تر
res2 = resistance_ladder_high(df, 2)
res59 = resistance_ladder_high(df, 59)
both = res2.notna() & res59.notna()
pl = pd.to_numeric(df["p_last"], errors="coerce")
print(f"\nردیف‌هایی که هر دو بازه را دارند: {int(both.sum())}")
print(f"  میانگینِ سقفِ ۲ روزه: {res2[both].mean():,.0f}   میانگینِ سقفِ ۵۹ روزه: {res59[both].mean():,.0f}")
print(f"  سقفِ ۵۹ روزه در {int((res59[both] > res2[both]).sum())} ردیف بالاتر است "
      f"(در {int((res59[both] == res2[both]).sum())} ردیف برابر).")
print(f"  آخرینِ معامله بالای سقفِ ۲ روزه: {int((pl[both] > res2[both]).sum())}   "
      f"بالای سقفِ ۵۹ روزه: {int((pl[both] > res59[both]).sum())}")
