# یک‌بارمصرف — ارقامِ «باقی‌ماندهٔ اختلاف» برایِ گزارشِ این دور
import json
import sqlite3
import sys

sys.path.insert(0, r"C:\Users\PCMOD\Desktop\BorsTerminal")
import bors_config as BC           # noqa: E402
import fts_engine as FE            # noqa: E402
from api import fundamental as FD  # noqa: E402

conn = sqlite3.connect("file:market.db?mode=ro", uri=True)

cfg = json.load(open(BC.FTS_CONFIG_PATH, encoding="utf-8"))
print("۱) کلیدهایِ fts_thresholds.json:", len(cfg))
print("   pharma_margin_exempt_min درِ فایل؟", "pharma_margin_exempt_min" in cfg,
      "| درِ DEFAULT_TH؟", "pharma_margin_exempt_min" in FE.DEFAULT_TH,
      "= ", FE.DEFAULT_TH.get("pharma_margin_exempt_min"),
      "| موتور برایِ این دور می‌خواند:", FE._th(cfg, "pharma_margin_exempt_min"))

print("\n۲) clampِ فقط-کارتیِ حاشیه (−99..200):")
for sym in ("ثتران", "دامین", " وملل", "وملل"):
    ref = FE.reference_annual(conn, sym)
    if ref is None:
        continue
    eng = FE.gross_margin(conn, sym, ref=ref)
    card = FD.ind3_gross_margin(conn, sym, ref=ref)
    print("   %-8s موتور=%s کارت=%s (na=%s)" % (
        sym, (eng or {}).get("margin_pct"), (card or {}).get("margin_pct"),
        (card or {}).get("na")))

print("\n۳) نشار (اختلافِ باقی‌مانده):")
key = FE.norm_fa("نشار")
bulk = [r for r in FE.bulk_scan(conn, cfg={}) if r["symbol_norm"] == key]
print("   bulk:", [(r["symbol"], r["sales_to_mcap"], r["mcap"]) for r in bulk])
mc = FD.get_tsetmc_market_cap_info("نشار", db=conn)
print("   کارت (منبعِ ارزش بازار):", {k: mc[k] for k in ("rials", "source", "asof", "error")})

print("\n۴) پهنایِ ماهانه (فقط کارت):")
print("   درِ موتور:", "monthly breadth" in str(FE.__doc__) or "no-op",
      "| درِ کارت: api/fundamental._growth_breadth")
