"""ابزارِ تحقیقاتی — بازدهِ پنج فیلترِ تابلو رویِ market.db واقعی.

کوئری را از خودِ api/market.py می‌خواند (نه یک نسخهٔ دست‌نویس) تا هرگز از
مسیرِ واقعیِ کد جدا نیفتد. خروجی: چند ردیفِ تابلو تحتِ قاعدهٔ «جزوه» و تحتِ
قاعدهٔ «قدیمیِ NULL=قبول» هر کدام علامت می‌خورند.
"""
import json
import re
import sqlite3
import sys
import time

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from tape_flags import apply_tape_flags, JET_LADDER  # noqa: E402

SRC = "api/market.py"
SQL = re.search(r'query = """(.*?)"""', open(SRC, encoding="utf-8").read(), re.S)
if not SQL:
    sys.exit("کوئریِ تابلو در api/market.py پیدا نشد — ابزار باید به‌روز شود")
QUERY = SQL.group(1)

conn = sqlite3.connect("market.db")
t0 = time.perf_counter()
df = pd.read_sql_query(QUERY, conn)
print(f"کوئری: {len(df)} ردیف در {time.perf_counter() - t0:.2f} ثانیه")

day = df["d_even"].max()
df = df[df["d_even"] == day].copy()
print(f"ردیفِ نشستِ جاریِ تابلو ({day}): {len(df)}")

df["tvol"] = pd.to_numeric(df["q_tot_tran"], errors="coerce").astype(float).fillna(0.0)
_py = pd.to_numeric(df["price_yesterday"], errors="coerce")
_pc = pd.to_numeric(df["p_closing"], errors="coerce")
_chg = pd.to_numeric(df["price_change"], errors="coerce")
py_ok = _py.where(_py > 1.0)
pct = ((_pc - py_ok) / py_ok * 100).round(2)
pct = pct.fillna((_chg / py_ok * 100).round(2))
df["percent_change"] = pct.where(pct.abs() <= 100.0)

out = apply_tape_flags(df)

# پوششِ منابع — همان عددی که قبلاً غلط بود
for col in ("month_avg_vol", "h1_max", "h2_max", "h59_max", "min30_low", "prev_day_vol"):
    have = out[col].notna().sum()
    print(f"  {col:<14} موجود: {have:>5} از {len(out)} ({have / len(out) * 100:.0f}%)")

print("\nبازدهِ پرچم‌ها (قاعدهٔ جزوه، نبودنِ داده = رد):")
for k in ("f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh"):
    print(f"  {k:<9} {int(out[k].sum()):>5}")


# ── قاعدهٔ قدیمی، برای مقایسهٔ عددیِ «قبل/بعد» ─────────────────────────────
def old_rules(d):
    V = lambda s: d[s].astype(float)  # noqa: E731
    mav = d["month_avg_vol"].where(d["month_avg_vol"] > 0)
    old = {}
    old["f_clock"] = ((V("p_last") >= V("p_closing") * 1.01)
                      & (V("tvol") > mav) & (V("z_tot_tran") > 30)).fillna(False)
    old["f_susp"] = ((V("tvol") > 3 * mav) & (V("z_tot_tran") > 50)).fillna(False)
    ok = True
    buy_pow = V("buy_i_vol") / V("buy_count_i").replace(0, 1)
    sell_pow = V("sell_i_vol") / V("sell_count_i").replace(0, 1)
    for k in (5, 9, 19, 29, 39, 49, 59):
        ok = ok & (d[f"h{k}_max"].isna() | (d[f"h{k}_max"] < V("p_closing")))
    old["f_jet"] = ((V("tvol") > 3 * mav) & (buy_pow >= 1.5 * sell_pow)
                    & (V("p_last") >= V("p_closing"))
                    & (V("percent_change") > 0) & (V("z_tot_tran") > 100)
                    & ok).fillna(False)
    old["f_roobi"] = (np.isclose(V("p_closing"), V("p_min"), atol=0.5)
                      & (V("prev_day_vol") > 1) & (V("percent_change") < -1)
                      & (V("z_tot_tran") > 100)).fillna(False)
    low = d["min30_low"].where(d["min30_low"] > 0)
    dist = np.where(V("p_closing") > 0, (V("p_closing") - low) / V("p_closing") * 100, np.nan)
    old["f_noqteh"] = ((dist < 3) & (V("tvol") > mav)
                       & (V("z_tot_tran") > 5)).fillna(False)
    return old


old = old_rules(df)
print("\nقبل / بعد:")
for k in ("f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh"):
    a, b = int(old[k].sum()), int(out[k].sum())
    both = int((old[k] & out[k]).sum())
    print(f"  {k:<9} قبل={a:>5}  بعد={b:>5}  اشتراک={both:>5}")

# چند ردیفِ «جتِ قدیمی» واقعاً هیچ تاریخچه‌ای نداشتند؟
no_hist = old["f_jet"] & out["resistance_59"].isna()
print(f"\nجت‌هایِ قدیمی که هیچ پلکانِ کاملی نداشتند: {int(no_hist.sum())} از {int(old['f_jet'].sum())}")
print("نمونه‌ها:", json.dumps(df.loc[no_hist, "symbol"].head(8).tolist(), ensure_ascii=False))
conn.close()
