#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fts_screener_card_parity_v10.py — پاریتیِ اسکرینر و کارت جزئیات (v10).

قاعدهٔ سختِ سند v10 (بالای api/fundamental.py): «منبع واحد حقیقت» مسیر
کارت جزئیات است و هیچ مسیرِ خواندنی — از جمله /api/screener — حق ندارد
امتیاز/پرچم را جدا حساب کند یا ارزش بازار را دوباره بسازد.

این اسکریپت هر ردیفِ اسکرینر را با همان evaluate_v10 (همان مسیر کارت) دوباره
محاسبه می‌کند و امتیاز/پنج پاس/excluded را مقایسه می‌کند. روی دیتابیسِ کامل
باید صفر ناهم‌خوانی بدهد؛ اگر market.db نبود، با پیام «بدون داده» رد می‌شود
(نه شکست کاذب).

⚠️ بندِ دوم (v10.2 — قفلِ باگِ واقعی): مقایسهٔ بالا به‌تنهایی پاریتیِ
اسکرینر/کارت را نمی‌گیرد؛ آن «کارت را با خودش» می‌سنجد (ردیف‌های اسکرینر از
همان evaluate_v10 ساخته میشوند)، پس اگر دو مسیرِ مستقلِ موتور و کارت روی
معافیتِ شاخص ۴ دو معیارِ متفاوت داشته باشند، سبز می‌ماند. همین خود-سنجی باعث شد
واگراییِ ۲۳۱ نماد از ۸۷۳ (تجارت: موتور عدد می‌دهد، کارت N/A — و اطلس/آسا/آلا:
کارت عدد می‌دهد، موتور معاف) بی‌صدا منتشر شود. بندِ دوم، حکمِ معافیت و عددِ
`sales_to_mcap` را برای هر نماد بین دو مسیرِ مستقل مقایسه می‌کند:
  موتور: fts_engine.bulk_scan (و نمونه‌ای از scan_symbol) → is_exempt
  کارت : api/fundamental.evaluate_v10 → indicators["4"].{na, available, sales_to_mcap}
تک‌مرجعِ هر دو: fts_engine.ind4_exempt. گیتِ کانفیگِ holdings_sales_na هم هر دو
مسیر می‌خوانند (خاموش = بی‌معافیت در اسکرینر و کارت با هم)، پس بندِ دوم زیرِ
هر حالتِ آن کلید سنجیده می‌شود.

Run:  python dev/fts_screener_card_parity_v10.py
Exit: 0 اگر همه‌ی ردیف‌ها هم‌راستا بودند (یا دیتابیس نبود)؛ 1 در غیر این صورت.
"""
import os
import sqlite3
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

DB = "market.db"
if not os.path.isfile(DB):
    print("[SKIP] %s نیست — «بدون دادهٔ محلی»؛ پاریتی اجرا نشد." % DB)
    sys.exit(0)

import fts_engine                       # noqa: E402
from api import fundamental as F        # noqa: E402
from api import screener as S           # noqa: E402
from api.market import load_fts_config  # noqa: E402

AX = ("1_growth", "2_eps_trend", "3_gross_margin", "4_sales_to_mcap", "5_industry")

cfg = load_fts_config()
# کشِ دیسکِ اسکرینر تا ۱۲ ساعت کهنه می‌ماند؛ اگر سینکِ بازار بین دو اجرای ما
# ردیف‌ها را عوض کند، ناهم‌خوانیِ بندِ اول «باگِ کد» نیست که «داده عوض شده».
# پس کش پاک می‌شود تا هر دو بند روی یک محاسبهٔ زنده سنجیده شوند
# (get_screener خودش کشِ تازه را دوباره می‌نویسد). فقط فایلِ کش — دیتابیس
# دست‌نخورده می‌ماند، پس سوئیت هیچ چیزی را در market.db تغییر نمی‌دهد.
try:
    if os.path.exists(S.CACHE_FILE):
        os.remove(S.CACHE_FILE)
except OSError:
    pass
res = S.get_screener()
rows = res.get("data") or []
print("اسکرینر: %d ردیف" % len(rows))

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cname_of = {}
for sym, cn in conn.execute("SELECT symbol, company_name FROM financial_statements "
                            "ORDER BY period_end DESC"):
    k = fts_engine.norm_fa(sym)
    if k and k not in cname_of:
        cname_of[k] = cn or ""

checked = 0
mismatches = []
# ── بندِ دوم: موتور ⇄ کارت، شاخص ۴ ────────────────────────────────────────
# مسیرِ موتور یک‌بارِ کل‌بازاری خوانده میشود (همان bulk_scan که /api/screener
# مصرف می‌کند)؛ ردیفِ آن `is_exempt` را جدا نمی‌دهد و معافیت را دو علامتِ
# مستقل می‌سازد: نسبت N/A و i4_pass=True (معاف یعنی «رد نیست، نظر نمی‌دهم»).
eng_of = {r["symbol_norm"]: r for r in fts_engine.bulk_scan(conn, cfg=cfg)}
print("موتور (bulk_scan): %d ردیف" % len(eng_of))


def eng_exempt(b):
    return b["sales_to_mcap"] is None and bool(b["i4_pass"])


ind4_checked = 0
ind4_missing = 0
exempt_disagree = []      # حکمِ معافیت واگرا — خطای قطعی
value_disagree = []       # هر دو «معاف نیستند» ولی یکی عدد دارد و دیگری نه
ratio_far = 0             # اختلافِ عددی (غیرِکشنده؛ مبنای سالانه‌سازی متفاوت)
ind4_rows = []
scan_probe = []           # نمونه‌ای از مسیرِ تک‌نمادیِ موتور (scan_symbol)
for r in rows:
    key = r.get("symbol_norm") or fts_engine.norm_fa(r["symbol"])
    mcap, sector, total, _info = F._fts_market_ctx(conn, key)
    card = F.evaluate_v10(conn, key, mcap or 0.0, total, sector, cfg=cfg,
                          company_name=cname_of.get(key, ""))
    checked += 1
    sp = [bool(r["i1_pass"]), bool(r["i2_pass"]), bool(r["i3_pass"]),
          bool(r["i4_pass"]), bool(r["i5_pass"])]
    cp = [bool(card["passes"][k]) for k in AX]
    if r["score"] != card["score"] or sp != cp or bool(r["excluded"]) != bool(card["excluded"]):
        mismatches.append((r["symbol"], r["score"], sp, bool(r["excluded"]),
                           card["score"], cp, bool(card["excluded"])))

    b = eng_of.get(key)
    v4 = (card.get("indicators") or {}).get("4") or {}
    if b is None:
        ind4_missing += 1
        continue
    ind4_checked += 1
    ee, ce = eng_exempt(b), bool(v4.get("na"))
    er, cr = b["sales_to_mcap"], v4.get("sales_to_mcap")
    if ee != ce:
        exempt_disagree.append((r["symbol"], sector, ee, er, ce, cr,
                                v4.get("reason") or ""))
    elif (er is None) != (cr is None):
        value_disagree.append((r["symbol"], sector, er, cr))
    elif er is not None and cr is not None and abs(er - cr) > 0.05:
        ratio_far += 1
    ind4_rows.append((r["symbol"], ee, er, ce, cr))
    # نمونه‌ای از مسیرِ تک‌نمادیِ موتور (/api/fts/{symbol} = scan_symbol) هم
    # سنجیده می‌شود: bulk_scan و scan_symbol دو ورودیِ ind4_exempt‌اند.
    if ind4_checked % 25 == 0:
        scan_probe.append((key, r["symbol"], mcap or 0.0, total, sector, ce))

print("بررسی‌شده: %d | ناهم‌خوانی: %d" % (checked, len(mismatches)))
for sym, ss, sp, se, cs, cp, ce in mismatches[:15]:
    print("  ✗ %-14s اسکرینر=%d %s exc=%s | کارت=%d %s exc=%s"
          % (sym, ss, "".join("1" if x else "0" for x in sp), se,
             cs, "".join("1" if x else "0" for x in cp), ce))

# ── گزارشِ بندِ دوم ────────────────────────────────────────────────────────
n_ex = sum(1 for _s, ee, _er, _ce, _cr in ind4_rows if ee)
print("\nشاخص ۴ — موتور ⇄ کارت: مقایسه‌شده %d (بی‌ردیفِ موتوری: %d) | هر دو معاف: %d"
      % (ind4_checked, ind4_missing, n_ex))
for sym, sector, ee, er, ce, cr, why in exempt_disagree[:20]:
    print("  ✗ %-14s موتور: exempt=%s نسبت=%s | کارت: na=%s نسبت=%s | %s"
          % (sym, ee, er, ce, cr, why[:70]))
for sym, sector, er, cr in value_disagree[:20]:
    print("  ✗ %-14s هیچ‌کدام معاف نیست ولی یکی عدد ندارد: موتور=%s کارت=%s (%s)"
          % (sym, er, cr, sector))
scan_bad = []
for key, sym, mcap, total, sector, ce in scan_probe:
    d = (fts_engine.scan_symbol(conn, key, mcap, total, sector, cfg=cfg)
         .get("detail") or {}).get("sales_to_mcap") or {}
    if bool(d.get("is_exempt")) != ce:
        scan_bad.append((sym, bool(d.get("is_exempt")), ce))
for sym, ee, ce in scan_bad[:20]:
    print("  ✗ %-14s scan_symbol: exempt=%s | کارت: na=%s" % (sym, ee, ce))
print("نمونهٔ scan_symbol: %d | واگرایی: %d" % (len(scan_probe), len(scan_bad)))
print("توضیح: اختلافِ مبنای سالانه‌سازیِ عددی (>۰٫۰۵) خارج از حکمِ معافیت: %d ردیف"
      % ratio_far)
# یادداشت — عمداً قفل نشده و فقط گزارش می‌شود: «معاف بودن یعنی پاس؟» در دو
# مسیر یکی نیست (موتور معافیت را پاسِ نرم می‌شمارد: i4_pass=True؛ کارت N/A را
# پاس نمی‌شمارد). تغییرِ یکی از دو طرف امتیازِ صدها نماد را جابه‌جا می‌کند و
# تصمیمِ مالک است، نه بخشی از رفعِ این واگرایی.
print("یادداشت: معافِ هر-دو-مسیر که کارت آن‌ها را پاس نمی‌شمارد: %d ردیف" % n_ex)

if mismatches or exempt_disagree or value_disagree or scan_bad:
    print("RESULT: FAIL — اسکرینر/موتور و کارت جزئیات هم‌راستا نیستند "
          "(امتیاز=%d، معافیت=%d، عدد-vs-N/A=%d، scan_symbol=%d)."
          % (len(mismatches), len(exempt_disagree), len(value_disagree), len(scan_bad)))
    sys.exit(1)
print("RESULT: PASS — امتیاز/پرچم اسکرینر == کارت، و حکمِ معافیتِ شاخص ۴ "
      "برای هر %d نماد بین موتور و کارت یکسان است." % ind4_checked)
sys.exit(0)
