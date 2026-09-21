#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ممیزی زندهٔ داده‌های تابلو (TSETMC) و آرنا — گام ۲.

دادهٔ زنده را از وب می‌گیرد و با موتورِ محاسباتیِ پروژه (mstat_engine.money)
تطبیق می‌دهد. برخلافِ تست‌های محلی که رویِ fixture کار می‌کنند، اینجا
منبعِ حقیقت خودِ تابلو است.

منابع:
  * TSETMC  — GetMarketWatch (قیمت/حجم/عمق) + GetClientTypeAll (حقیقی/حقوقی)
  * Arena   — صفحهٔ مرجعِ تریدرزآرنا (تطبیقِ متقاطعِ قیمت/حجم)

نمادهای آزمون (ماهیت‌های متفاوت):
  * فولاد     — سهم شاخص‌سازِ بزرگ
  * وبملت     — نماد متوسط/کوچک نوسانی
  * طتوان918  — صندوق سرمایه‌گذاری (طلا)

پارامترهای تطبیقی: قیمت آخرین/پایانی، حجم/ارزش/تعداد معاملات، عمق ۵ خطی،
آمار حقیقی/حقوقی، سرانه‌ها، قدرت خریدار، جریان پول هوشمند.

حالاتِ مرزی: نماد متوقف / حجم صفر → باید None برگرداند، نه ZeroDivisionError.

استفاده:
    python dev/live_market_board_audit.py            # ممیزی کامل
    python dev/live_market_board_audit.py --symbols فولاد,عیار
    python dev/live_market_board_audit.py --offline   # فقط حالت‌های مرزی (بدون وب)
"""
import argparse
import datetime
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import test_tsetmc as tt          # لایهٔ فچِ زندهٔ پروژه
import mstat_engine as ME         # موتورِ محاسباتی

# نمادهای آزمون (ماهیت‌های متفاوت). کیان/عیار ممکن است در روزِ ممیزی رویِ
# تابلو نباشند (متوقف/مجاز نیست)؛ وبملت و یک صندوقِ طلا جایگزین می‌شوند.
DEFAULT_SYMBOLS = ("فولاد", "وبملت", "طتوان918")
TUMAN = ME.M_TUMAN_FROM_RIAL      # ریال → تومان (مرجعِ واحدِ پروژه)

_checks = []


def ck(cond, msg):
    _checks.append((bool(cond), msg))
    print("  %s %s" % ("✓" if cond else "✗", msg))
    return bool(cond)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def fmt_rial(v):
    """ریال → نمایشِ خوانای تومانی (میلیون تومان)."""
    if v is None:
        return "None"
    if not v:
        return "0"
    return "{:,.1f}".format(v / TUMAN)


# ══════════════════════════════════ منابع زنده ═════════════════════════════
def fetch_live_board(symbols):
    """یک درخواستِ MarketWatch + یک درخواستِ ClientTypeAll → دیکشنریِ نماد.

    از خودِ لایهٔ پروژه استفاده می‌کنیم (polite_get/make_session) تا ممیزی
    دقیقاً همان مسیری را برود که همگام‌سازِ تولید می‌رود.
    """
    sess = tt.make_session()
    mw = tt.polite_get(sess, tt.MW_URL, "marketwatch") or []
    ct = tt.polite_get(sess, f"{tt.BASE}/ClientType/GetClientTypeAll",
                       "clientTypeAllDto") or []
    sess.close()
    if not mw:
        raise SystemExit("[FAIL] GetMarketWatch returned nothing "
                         "(network/WAF). abort.")

    ct_map = {r.get("insCode"): r for r in ct if r.get("insCode")}
    # توجه: فیلدِ نماد در GetMarketWatch از نوعِ «lva» است (نامِ کوتاه).
    # «lVal18» در این endpoint وجود ندارد — نسخهٔ نخستِ این ممیزی آن را
    # می‌خواند و هیچ نمادی پیدا نمی‌کرد، در حالی که ۳۸۴۴ ردیف برمی‌گشت.
    out = {}
    for row in mw:
        sym = (row.get("lva") or "").strip()
        if sym and sym in symbols:
            out[sym] = {
                "ins_code": row.get("insCode"),
                "row": row,
                "ct": ct_map.get(row.get("insCode")),
                "queue": tt.queue_agg(row),
            }
    return out


def fetch_arena(symbols):
    """صفحهٔ مرجعِ آرنا — تطبیقِ متقاطعِ قیمت/حجم.

    تریدرزآرنا خلاصهٔ تابلو را برمی‌گرداند. اگر در دسترس نبود، ممیزی به‌جای
    شکست آن را به‌عنوانِ منبعِ مکمل علامت‌گذاری می‌کند — منبعِ اصلیِ حقیقت
    TSETMC است.
    """
    import requests
    out = {}
    try:
        for sym in symbols:
            r = requests.get(
                "https://api.tradersarena.ir/api/v1/market/quote",
                params={"symbol": sym}, timeout=20,
                headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                out[sym] = r.json()
    except Exception as e:
        print("  [arena] unavailable (%s) — marking as supplemental" % e)
    return out


# ═════════════════════════════════ تطبیق ════════════════════════════════════
def audit_symbol(sym, live, arena):
    """تطبیقِ ردیفِ زنده با خروجیِ mstat_engine.money."""
    print("\n── %s ─────────────────────────────────────" % sym)
    if sym not in live:
        print("  [skip] not in today's board (suspended or delisted)")
        return
    d = live[sym]
    row, ct, q = d["row"], d["ct"], d["queue"]

    # توجه — نامِ فیلدها در GetMarketWatch با ستونهایِ بانک فرق دارد:
    # تابلو: qtj=حجم، qtc=ارزش، ztt=تعداد معامله، pcl=پایانی، pmd=آخرین،
    #         ztd=ارزش بازار، pmn/pmx=کف/سقف.
    # بانک : q_tot_tran، q_tot_cap، z_tot_tran، p_closing، p_last، total_shares.
    # خواندنِ اشتباهِ این فیلدها حجمِ صفر می‌سازد و ممیزی را کور می‌کند.
    enriched = {
        "ins_code": row.get("insCode"),
        "lva": sym,
        "p_closing": _f(row.get("pcl")),
        "p_last": _f(row.get("pmd")),
        "q_vol": _f(row.get("qtj")),
        "q_val": _f(row.get("qtc")),
        "n_trades": _f(row.get("ztt")),
        "total_shares": _f(row.get("ztd")),
        "price_min": _f(row.get("pmn")),
        "price_max": _f(row.get("pmx")),
        "price_yesterday": _f(row.get("py")),
        "ct": None,
        "buy_q_vol": _f(q[0]) if q else None,
        "buy_q_val": _f(q[1]) if q else None,
        "buy_q_cnt": _f(q[2]) if q else None,
        "sell_q_vol": _f(q[3]) if q else None,
        "sell_q_val": _f(q[4]) if q else None,
        "sell_q_cnt": _f(q[5]) if q else None,
        "buy_q1_vol": _f(q[6]) if q else None,
        "buy_q1_px": _f(q[7]) if q else None,
        "sell_q1_vol": _f(q[8]) if q else None,
        "sell_q1_px": _f(q[9]) if q else None,
    }
    # ترتیبِ تاپلِ خام = ترتیبِ ستونهایِ جدولِ client_type، که
    # mstat_engine._CT_FIELDS تنها مرجعِ اندیس‌های آن است. توجه: اندیسِ ۰
    # به ins_code اختصاص دارد، پس buy_i_vol در ۱ و buy_count_i در ۴ است.
    # خواندن با نامِ ستون، نه با شمارهٔ دستی — همان قاعدهٔ mstat_engine.
    # توجه: endpointِ زنده از نام‌هایِ اختصاصی استفاده می‌کند
    # (buy_I_Volume، buy_CountI، ...) که نه snake_caseِ بانک است و نه
    # PascalCaseٔ یکنواخت — اولین کلمه کوچک است. خواندنِ اشتباه
    # همه‌چیز را صفر می‌سازد و ممیزی را کور می‌کند، پس نگاشتی صریح:
    _ALIAS = {
        "buy_i_vol":    ("buy_I_Volume", "Buy_I_Vol"),
        "buy_n_vol":    ("buy_N_Volume", "Buy_N_Vol"),
        "buy_ddd_vol":  ("buy_DDD_Volume", "Buy_DDD_Vol"),
        "buy_count_i":  ("buy_CountI", "Buy_CountI"),
        "buy_count_n":  ("buy_CountN", "Buy_CountN"),
        "buy_count_ddd": ("buy_CountDDD", "Buy_CountDDD"),
        "sell_i_vol":   ("sell_I_Volume", "Sell_I_Vol"),
        "sell_n_vol":   ("sell_N_Volume", "Sell_N_Vol"),
        "sell_count_i": ("sell_CountI", "Sell_CountI"),
        "sell_count_n": ("sell_CountN", "Sell_CountN"),
    }

    def ctf(name):
        if ct is None:
            return 0.0
        if name in ct:                     # ردیفِ بانک (snake_case)
            return _f(ct[name])
        for cand in _ALIAS.get(name, ()):  # پاسخِ زندهٔ TSETMC
            if cand in ct:
                return _f(ct[cand])
        return 0.0

    if ct:
        enriched["ct"] = (
            0,                                  # ins_code (placeholder)
            ctf("buy_i_vol"),                   # 1
            ctf("buy_n_vol"),                   # 2
            ctf("buy_ddd_vol"),                 # 3
            ctf("buy_count_i"),                 # 4
            ctf("buy_count_n"),                 # 5
            ctf("sell_i_vol"),                  # 6
            ctf("sell_n_vol"),                  # 7
            ctf("sell_count_i"),                # 8
            ctf("sell_count_n"),                # 9
        )

    m = ME.money(enriched, base_est={})

    # ── ۱) قیمت و حجم: تابلو vs موتور ──────────────────────────────────
    ck(m["vol"] == enriched["q_vol"], "حجم موتور = تابلو (%s)" % m["vol"])
    ck(m["val"] == enriched["q_val"], "ارزش موتور = تابلو (%s تومان)"
       % fmt_rial(m["val"]))
    ck(m["trades"] == enriched["n_trades"], "تعداد معامله = تابلو (%s)" % m["trades"])
    ck(enriched["q_vol"] == 0 or abs(m["vwap"] - m["val"] / m["vol"]) < 1.0,
       "VWAP = ارزش÷حجم (%s)" % fmt_rial(m["vwap"] * TUMAN))

    # ── ۲) عمق: ۵ مظنه برتر ─────────────────────────────────────────────
    if q:
        ck(m["bq_vol"] == _f(q[0]), "عمق خرید: حجم ۵ خط = تابلو")
        ck(m["sq_vol"] == _f(q[3]), "عمق فروش: حجم ۵ خط = تابلو")
        ck(m["bq1_px"] == _f(q[7]), "بهترین مظنه خرید = تابلو (%s)"
           % fmt_rial(m["bq1_px"] * TUMAN if m["bq1_px"] else 0))
        ck(m["sq1_px"] == _f(q[9]), "بهترین مظنه فروش = تابلو (%s)"
           % fmt_rial(m["sq1_px"] * TUMAN if m["sq1_px"] else 0))
    else:
        print("  [info] عمق در این ردیف نیست (blDs خالی)")

    # ── ۳) حقیقی/حقوقی و مشتقات ─────────────────────────────────────────
    if ct:
        # تعدادِ معامله‌گر حقیقی از همان منبعِ زنده خوانده می‌شود که موتور
        # استفاده می‌کند — نه از فیلدِ دیگری که ممکن است مقدارِ متفاوتی داشته
        # باشد (ztt تعدادِ کل معاملات است، buy_CountI تعدادِ خریداران).
        ck(m["n_buy_i"] == int(ctf("buy_count_i")),
           "تعداد خرید حقیقی = تابلو (%s)" % m["n_buy_i"])
        ck(m["n_sell_i"] == int(ctf("sell_count_i")),
           "تعداد فروش حقیقی = تابلو (%s)" % m["n_sell_i"])
        ck(m["pc_buy"] is None or m["pc_buy"] > 0 or m["n_buy_i"] == 0,
           "سرانه خرید محاسبه‌شدنی است یا مخرج صفر (None)")
        ck(m["pc_sell"] is None or m["pc_sell"] > 0 or m["n_sell_i"] == 0,
           "سرانه فروش محاسبه‌شدنی است یا مخرج صفر (None)")
        ck(m["power"] is None or 0 < m["power"] < 1e9,
           "قدرت خریدار در بازهٔ منطقی (%s)" % m["power"])
        ck(abs(m["flow"] - (m["retail_buy"] - m["retail_sell"])) < 1.0,
           "جریان پول = خرید−فروش حقیقی (%s تومان)" % fmt_rial(m["flow"]))
        print("    سرانه خرید: %s | سرانه فروش: %s | قدرت: %s"
              % (fmt_rial(m["pc_buy"]), fmt_rial(m["pc_sell"]), m["power"]))
        print("    ورود/خروج پول خرد: %s تومان" % fmt_rial(m["flow"]))
    else:
        print("  [info] ردیف ClientType برای این نماد نیست")

    # ── ۴) تطبیقِ متقاطع با آرنا (مکمل) ──────────────────────────────────
    a = arena.get(sym)
    if a:
        try:
            data = a.get("data") or a
            ap = _f(data.get("last_price") or data.get("p_last") or 0)
            if ap > 0:
                ck(abs(ap - enriched["p_last"]) / max(ap, 1) < 0.01,
                   "آرنا: آخرین معامله %s ≈ تابلو %s"
                   % (fmt_rial(ap * TUMAN),
                      fmt_rial(enriched["p_last"] * TUMAN)))
        except Exception:
            pass

    # ── ۵) جدولِ تطبیقِ نهایی ───────────────────────────────────────────
    print("    ┌────────────────────┬───────────────┬───────────────┐")
    print("    │ پارامتر            │ زنده (تابلو)  │ موتور         │")
    print("    ├────────────────────┼───────────────┼───────────────┤")
    for label, live_v, eng_v in (
        ("آخرین معامله", enriched["p_last"] * TUMAN, m["vwap"] * TUMAN),
        ("قیمت پایانی", enriched["p_closing"] * TUMAN, m["vwap"] * TUMAN),
        ("حجم کل", enriched["q_vol"], m["vol"]),
        ("ارزش کل (تومان)", enriched["q_val"], m["val"]),
        ("تعداد معامله", enriched["n_trades"], m["trades"]),
        ("سرانه خرید (تومان)", None, m["pc_buy"]),
        ("سرانه فروش (تومان)", None, m["pc_sell"]),
        ("قدرت خریدار", None, m["power"]),
        ("جریان پول (تومان)", None, m["flow"]),
    ):
        print("    │ %-18s │ %13s │ %13s │" % (
            label, fmt_rial(live_v) if live_v is not None else "-",
            fmt_rial(eng_v) if eng_v is not None else "-"))
    print("    └────────────────────┴───────────────┴───────────────┘")
    return m


# ═════════════════════════════ حالات مرزی ══════════════════════════════════
def edge_cases():
    """نماد متوقف / حجم صفر — موتور باید None بدهد، نه ZeroDivisionError."""
    print("\n== حالات مرزی (بدون وب) ==")
    zero = {"ins_code": "TEST0", "q_vol": 0.0, "q_val": 0.0, "n_trades": 0.0,
            "p_closing": 0.0, "ct": (0, 0, 0, 0, 0, 0, 0, 0, 0, 0)}
    try:
        m = ME.money(dict(zero), base_est={})
        ck(m["pc_buy"] is None, "حجم صفر: سرانه خرید None است (نه ZeroDivision)")
        ck(m["pc_sell"] is None, "حجم صفر: سرانه فروش None است")
        ck(m["power"] is None, "حجم صفر: قدرت خریدار None است")
        ck(m["flow"] == 0.0, "حجم صفر: جریان پول ۰ است")
    except ZeroDivisionError as e:
        ck(False, "ZeroDivisionError رخ داد: %s" % e)

    # مخرجِ صفر در تعدادِ معامله ولی حجمِ nonzero
    odd = {"ins_code": "TEST1", "q_vol": 1000.0, "q_val": 1e7, "n_trades": 0.0,
           "p_closing": 10000.0, "ct": (1000, 0, 0, 0, 0, 0, 1000, 0, 0, 0)}
    try:
        m = ME.money(dict(odd), base_est={})
        ck(m["pc_buy"] is None, "تعداد خرید صفر: سرانه None (نه تقسیم بر صفر)")
        ck(m["vwap"] > 0, "VWAP با تعدادِ صفر از قیمت پایانی می‌آید")
    except ZeroDivisionError as e:
        ck(False, "ZeroDivisionError در حالتِ تعدادِ صفر: %s" % e)

    # بدونِ ردیفِ ClientType اصلاً
    try:
        m = ME.money({"ins_code": "TEST3", "q_vol": 5.0, "q_val": 1e6,
                      "n_trades": 1.0, "p_closing": 2e5, "ct": None},
                     base_est={})
        ck(m["has_ct"] is False, "نبودِ ClientType: has_ct=False، نه استثنا")
        ck(m["retail_buy"] == 0.0, "نبودِ ClientType: ارقام حقیقی ۰")
    except Exception as e:
        ck(False, "نبودِ ClientType استثنا داد: %r" % e)

    # معاملات بلوکی: سرانه باید ارزش÷تعداد باشد، نه حجم÷تعداد
    # (این همان اشتباهی که mstat_engine در نظراتش هشدار داده — sell_n_vol
    #  به‌جای sell_count_n. این چک آن را برای همیشه غیرممکن می‌کند.)
    # توجه: _CT_FIELDS اندیسِ ۰ را به ins_code اختصاص داده، پس buy_i_vol در
    # اندیسِ ۱ و buy_count_i در اندیسِ ۴ نشسته. تاپلِ خام باید همین ترتیب را
    # داشته باشد، وگرنه سرانه بی‌صدا None می‌شود.
    blk = {"ins_code": "TEST2", "q_vol": 1e6, "q_val": 1e10, "n_trades": 10.0,
           "p_closing": 1e4,
           "ct": (0, 1e6, 0, 0, 100, 0, 1e6, 0, 100, 0)}
    m = ME.money(dict(blk), base_est={})
    vwap = 1e10 / 1e6
    expect = (1e6 * vwap) / 100.0          # vol × vwap ÷ count
    ck(m["pc_buy"] is not None and abs(m["pc_buy"] - expect) < 1.0,
       "سرانه از «ارزش÷تعداد» می‌آید نه «حجم÷تعداد» (%s)" % fmt_rial(m["pc_buy"]))
    ck(abs(m["vwap"] - vwap) < 1.0,
       "VWAP از ارزش÷حجمِ همان ردیف می‌آید (%s)" % fmt_rial(m["vwap"] * TUMAN))


# ═════════════════════════════════ main ════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    ap.add_argument("--offline", action="store_true",
                    help="فقط حالت‌های مرزی (بدون درخواستِ وب)")
    args = ap.parse_args()
    syms = tuple(s.strip() for s in args.symbols.split(",") if s.strip())

    print("== ممیزی زندهٔ تابلو و آرنا — %s =="
          % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("  نمادها: %s" % ", ".join(syms))

    edge_cases()

    if args.offline:
        n_bad = sum(1 for ok, _ in _checks if not ok)
        print("\n[offline] %d چک، %d شکست" % (len(_checks), n_bad))
        return 1 if n_bad else 0

    try:
        live = fetch_live_board(set(syms))
    except SystemExit as e:
        print(e)
        return 1
    arena = fetch_arena(set(syms))
    print("  منابع: TSETMC=%d نماد، Arena=%d نماد"
          % (len(live), len(arena)))

    for sym in syms:
        audit_symbol(sym, live, arena)

    n_bad = sum(1 for ok, _ in _checks if not ok)
    print("\n" + "=" * 52)
    print("  %d چک، %d شکست" % (len(_checks), n_bad))
    print("  %s" % ("ممیزی سبز ✓" if not n_bad else "ممیزی قرمز ✗"))
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
