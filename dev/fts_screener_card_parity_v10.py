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
import codal_periods as CP              # noqa: E402  (ترتیبِ «تازه‌ترین دوره اول»)
from api import fundamental as F        # noqa: E402
from api import screener as S           # noqa: E402
from api.market import load_fts_config  # noqa: E402

AX = ("1_growth", "2_eps_trend", "3_gross_margin", "4_sales_to_mcap", "5_industry")

cfg = load_fts_config()
# کشِ اسکرینر دو لایه است: payloadِ دیسک (تا ۱۲ ساعت کهنه) و جدولِ مادی‌شدهٔ
# `fts_results`. اگر سینکِ بازار بین دو اجرای ما ردیف‌ها را عوض کند — یا **کدِ
# محاسبه عوض شود** (مثل دروازهٔ بانِ مردهٔ ارزش بازار، ۱۴۰۵-۰۷-۱۱) — ناهم‌خوانیِ
# بندِ اول «باگِ کد» نیست که «کشِ کهنه». پس هر دو لایه با همان رویۀ خودِ محصول
# باطل می‌شوند. `fts_results` کشِ کاملاً مشتق است: پس ازِ این حذف، اسکرینر محاسبهٔ
# زنده می‌کند و legِ «codal FTS pipeline» درِ همین سوئیت دوباره مادی‌اش می‌کند.
try:
    S.invalidate_screener_cache()
except OSError:
    pass
res = S.get_screener()
rows = res.get("data") or []
print("اسکرینر: %d ردیف" % len(rows))

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cname_of = {}
for sym, cn in conn.execute("SELECT symbol, company_name FROM financial_statements "
                            "ORDER BY %s, tracing_no DESC" % CP.order_expr()):
    k = fts_engine.norm_fa(sym)
    if k and k not in cname_of:
        cname_of[k] = cn or ""

checked = 0
mismatches = []
# ── بندِ دوم: موتور ⇄ کارت، شاخص ۴ ────────────────────────────────────────
# مسیرِ موتور یک‌بارِ کل‌بازاری خوانده میشود (همان bulk_scan که /api/screener
# مصرف می‌کند)؛ از رأی ۱۶ معافیت در موتور با یک علامتِ تنها نشان داده می‌شود:
# نسبت N/A و `i4_pass is None` («نظر نمی‌دهد» — نه True و نه False).
eng_of = {r["symbol_norm"]: r for r in fts_engine.bulk_scan(conn, cfg=cfg)}
print("موتور (bulk_scan): %d ردیف" % len(eng_of))


def eng_exempt(b):
    # رأی ۱۶ (۱۴۰۵/۰۷/۰۳): پیش از این معافیت را `i4_pass=True` علامت می‌زد، یعنی
    # امتیازِ رایگانِ ۲۹۷ نماد. حالا علامت، None است — همان چیزی که کارت می‌داد.
    return b["sales_to_mcap"] is None and b["i4_pass"] is None


ind4_checked = 0
ind4_missing = 0
exempt_disagree = []      # حکمِ معافیت واگرا — خطای قطعی
value_disagree = []       # هر دو «معاف نیستند» ولی یکی عدد دارد و دیگری نه
score_inflation = []      # امتیازِ موتور چیزی جز شمارشِ پاس‌های واقعی نیست
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
    # رأی ۱۶ (قفلِ عددی): امتیازِ موتور باید دقیقاً شمارشِ پاس‌های True باشد.
    # اگر روزی معافیت دوباره True شود (یا None داخلِ جمع بیفتد)، همین‌جا قرمز
    # می‌شود — نه رویِ صفحه‌ای که کاربر نمرهٔ ۴ از ۵ را می‌خواند.
    _flags = tuple(b.get("i%d_pass" % i) for i in (1, 2, 3, 4, 5))
    if b.get("score") != sum(1 for x in _flags if x is True):
        score_inflation.append((r["symbol"], b.get("score"), _flags))
    # نمونه‌ای از مسیرِ تک‌نمادیِ موتور (/api/fts/{symbol} = scan_symbol) هم
    # سنجیده می‌شود: bulk_scan و scan_symbol دو ورودیِ ind4_exempt‌اند.
    if ind4_checked % 25 == 0:
        scan_probe.append((key, r["symbol"], mcap or 0.0, total, sector, ce, b))

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
for sym, sc, flags in score_inflation[:20]:
    print("  ✗ %-14s امتیازِ موتور %s با شمارشِ پاس‌های واقعی نمی‌خواند: %s"
          % (sym, sc, "".join("1" if x is True else ("n" if x is None else "0")
                              for x in flags)))
for sym, sector, er, cr in value_disagree[:20]:
    print("  ✗ %-14s هیچ‌کدام معاف نیست ولی یکی عدد ندارد: موتور=%s کارت=%s (%s)"
          % (sym, er, cr, sector))
scan_bad = []
for key, sym, mcap, total, sector, ce, bulk_row in scan_probe:
    _rec = fts_engine.scan_symbol(conn, key, mcap, total, sector, cfg=cfg)
    d = (_rec.get("detail") or {}).get("sales_to_mcap") or {}
    if bool(d.get("is_exempt")) != ce:
        scan_bad.append((sym, bool(d.get("is_exempt")), ce))
    # رأی ۱۶ رویِ مسیرِ تک‌نمادی هم قفل می‌شود: معاف = None، و امتیاز = شمارشِ Trueها.
    if bool(d.get("is_exempt")) and _rec.get("passes", {}).get("4_sales_to_mcap") is not None:
        scan_bad.append((sym, "معاف ولی پاسِ شاخص ۴ سنجیده شد",
                         _rec.get("passes", {}).get("4_sales_to_mcap")))
    if _rec.get("score") != sum(1 for v in (_rec.get("passes") or {}).values() if v is True):
        scan_bad.append((sym, "امتیازِ scan_symbol ≠ شمارشِ پاس‌ها", _rec.get("score")))
    # قفلِ «یکِ فرمول» رویِ خودِ اعداد: مسیرِ تک‌نمادیِ موتور (/api/fts/{symbol})
    # و bulk_scan (/api/screener) باید رقمِ یکسان بدهند، نه فقط حکمِ یکسان.
    # این بند روزی کور بود و واگراییِ طبقۀ مالی/خدماتی (کتوکا/حبندر: op_basis) و
    # باگِ shadowingِ متغیرِ `annual` درِ bulk از چنگِ گزارش در رفت.
    _det = _rec.get("detail") or {}
    _pairs = (("نسبتِ فروش÷ارزش", (d or {}).get("sales_to_mcap"),
               bulk_row.get("sales_to_mcap")),
              ("پتانسیل سود", (_det.get("profit_potential") or {}).get("potential_pct"),
               bulk_row.get("profit_potential_pct")),
              ("حاشیۀ ناخالص", (_det.get("gross_margin") or {}).get("margin_pct"),
               bulk_row.get("gross_margin")),
              ("رشد فروش", (_det.get("growth") or {}).get("growth_pct"),
               bulk_row.get("rev_growth")))
    for label, sv, bv in _pairs:
        if sv != bv:
            scan_bad.append((sym, "scan_symbol ⇄ bulk: %s = %s ≠ %s" % (label, sv, bv), ""))
    if _rec.get("score") != bulk_row.get("score"):
        scan_bad.append((sym, "امتیازِ scan_symbol ≠ امتیازِ bulk",
                         (_rec.get("score"), bulk_row.get("score"))))
for sym, ee, ce in scan_bad[:20]:
    print("  ✗ %-14s scan_symbol: %s | %s" % (sym, ee, ce))
print("نمونهٔ scan_symbol: %d | واگرایی: %d" % (len(scan_probe), len(scan_bad)))
print("توضیح: اختلافِ مبنای سالانه‌سازیِ عددی (>۰٫۰۵) خارج از حکمِ معافیت: %d ردیف"
      % ratio_far)
# رأی ۱۶ (۱۴۰۵/۰۷/۰۳) بحثِ «معاف بودن یعنی پاس؟» را بست: معافیت به هیچ‌وجه
# امتیازِ رایگان نیست و در هر سه مسیر همان None می‌ماند. پیش از این این بند
# عمداً قفل نشده و فقط گزارش می‌شد؛ حالا score_inflation و scan_bad می‌بندندش.
print("معافِ هر-دو-مسیر که هیچ‌کدام امتیاز نمی‌گیرد: %d ردیف" % n_ex)

# ── بندِ سوم: /api/fundamental/screen نباید اصلاً خودش محاسبه کند ──────────
# ریشهٔ #75: این endpoint دومین پیاده‌سازیِ امتیازدهی بود (bulk_scanِ خام) و
# هیچ‌یک از الحاقه‌هایِ مسیرِ کارت را نمی‌داشت — نردبانِ EPSِ تلفیقی،
# معافیتِ شاخص ۴، استثنای حاشیهٔ دارویی، وتوی هفتگی. اندازه‌گیری: امتیاز در
# ۴۵۶ نماد از ۸۷۳ واگرا (محور ۲: ۱۴۵ | محور ۴: ۳۰۶ | محور ۵: ۲۵ | محور ۱: ۸۵).
# رفع: endpoint حالا فیلتری رویِ همان payload است. این بند همِ ساختار و همِ
# عدد را قفل می‌کند، تا یک ویرایشِ بعدی نتواند بی‌صدا موتورِ دوم را برگرداند.
import inspect as _ins                                    # noqa: E402
band3 = []


def c3(cond, label, extra=""):
    if not cond:
        band3.append(label)
        print("  ✗ band3 %s %s" % (label, extra))


_body = _ins.getsource(F.api_fundamental_screen)
c3("bulk_scan(" not in _body,
   "endpoint دیگر fts_engine.bulk_scan را صدا نمی‌زند")
c3("from .screener import get_screener" in _body,
   "endpoint از همان get_screener می‌خواند")
c3("dict(r)" in _body,
   "ردیف‌ها کپیِ سطحی می‌شوند (fts_verdict روی کشِ مشترک نمی‌نشیند)")

ep = F.api_fundamental_screen()
ep_rows = ep.get("data") or []
by_sym = {r.get("symbol"): r for r in rows}
c3(len(ep_rows) == len(rows), "تعدادِ ردیفِ endpoint == اسکرینر",
   "%d vs %d" % (len(ep_rows), len(rows)))
ep_diff = []
for r in ep_rows:
    o = by_sym.get(r.get("symbol"))
    if o is None:
        ep_diff.append((r.get("symbol"), "not in screener"))
        continue
    for k in ("score", "name", "excluded", "applicable") + tuple("i%d_pass" % i for i in (1, 2, 3, 4, 5)):
        if r.get(k) != o.get(k):
            ep_diff.append((r.get("symbol"), k, o.get(k), r.get(k)))
c3(not ep_diff, "هر امتیاز/پرچمِ endpoint == اسکرینر (بی‌محاسبهٔ دوم)", str(ep_diff[:4]))
c3(all("fts_verdict" in r for r in ep_rows) and not any("fts_verdict" in r for r in rows),
   "fts_verdict فقط رویِ کپیِ endpoint است و کشِ اسکرینر آلوده نشده")
na_bad = [r.get("symbol") for r in ep_rows
          if r.get("fts_verdict") == "NOT_APPLICABLE" and r.get("applicable") is not False]
c3(not na_bad, "NOT_APPLICABLE فقط برایِ نمادی که واقعاً پنج‌شاخصه ندارد", str(na_bad[:4]))
rej_fund = [r.get("symbol") for r in ep_rows
            if r.get("applicable") is False and r.get("fts_verdict") != "NOT_APPLICABLE"]
c3(not rej_fund, "هیچ صندوقی در این endpoint مردود نمی‌شود (رأی ۱۵)", str(rej_fund[:4]))
print("بندِ سوم (endpoint): %d ردیف | ناهم‌خوانی: %d | صندوقِ NOT_APPLICABLE: %d | خطا: %d"
      % (len(ep_rows), len(ep_diff),
         sum(1 for r in ep_rows if r.get("fts_verdict") == "NOT_APPLICABLE"), len(band3)))

if (mismatches or exempt_disagree or value_disagree or scan_bad
        or score_inflation or band3):
    print("RESULT: FAIL — اسکرینر/موتور و کارت جزئیات هم‌راستا نیستند "
          "(امتیاز=%d، معافیت=%d، عدد-vs-N/A=%d، scan_symbol=%d، تورمِ امتیاز=%d، "
          "endpoint=%d)."
          % (len(mismatches), len(exempt_disagree), len(value_disagree),
             len(scan_bad), len(score_inflation), len(band3)))
    sys.exit(1)
print("RESULT: PASS — امتیاز/پرچم اسکرینر == کارت، معافیتِ شاخص ۴ در هر سه مسیر "
      "None است (نه پاسِ رایگانِ امتیاز)، و /api/fundamental/screen همان "
      "پاسخِ کارت را فیلتر می‌کند (%d نماد)." % len(ep_rows))
sys.exit(0)
