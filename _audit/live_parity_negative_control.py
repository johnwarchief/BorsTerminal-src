# -*- coding: utf-8 -*-
"""_audit/live_parity_negative_control.py — کنترلِ منفیِ سنجشِ B

قاعدۀ دورِ امروز: «صفرِ ناهمخوانی» بی‌اثباتِ اینکه سنجش **می‌تواند** ببیند،
هیچ نیست (سنجشِ جت هفته‌ها صفر می‌داد چون ستون‌هایِ client_type ازِ جدولِ
 اشتباه خوانده می‌شدند ⇒ هر دو طرف همیشه False). این اسکریپت همان لایۀ B را
با چهار متنِ **عمداً خراب** اجرا می‌کند و باید شمارِ ناهمخوانی‌ها منفجر شود:

  • ساعت با آستانۀ ۵٪ به‌جای ۲٪
  • مشکوک با ضریب ۱۰× به‌جای ۳×
  • کف‌روبی بی‌قیدِ «کمتر از −۱٪»
  • جتِ شل‌شده: بی‌قیدِ پلکانِ مقاومت و بی‌سقفِ ۱۰۰ معامله

اگر هر سه صفر بمانند، سنجش کور است و گزارشِ «parity کامل» بی‌اعتبار است.
فقط می‌خواند (بانک `mode=ro`، API GET).
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests                        # noqa: E402
import tools.tse_live_filter_parity as P  # noqa: E402

APP = os.environ.get("TRIAGE_APP", "http://127.0.0.1:8001")
DB = os.environ.get("TRIAGE_DB", "market.db")
FLAG = {"clock": "f_clock", "susp": "f_susp", "roobi": "f_roobi", "jet": "f_jet"}


def broken_jet(v):
    """جتِ لقی‌شده: قیدِ پلکانِ مقاومت و سقفِ ۱۰۰ معامله حذف شوند.

    (نسخۀ «سخت‌تر» — توانِ ۳٫۰× به‌جای ۱٫۵× — امروزِ واقعی بی‌تفاوت بود: دو
    ردیفِ جتِ امروز نسبتِ قدرتِ خریدارِشان ۱۴۴٬۰۰۰ و ۶۸۵٬۲۶۹ است، یعنی از هر دو
    آستانه رد می‌شوند. سخت‌کردنِ آستانه چیزی را عوض نمی‌کند وقتی مرجعِ زنده
    نزدیکِ آستانه نیست؛ پس کنترلِ منفی باید **شل** شود.)
    """
    base = P.vol_base30(v)
    if not base or (v["tvol"] or 0) <= 3 * base:
        return False
    bv, bc = v["bp"]
    sv, sc = v["sp"]
    if not (bv and bc and sv and sc):
        return False
    return bool((bv / bc) >= 1.5 * (sv / sc) and v["pc"] and v["pl"] >= v["pc"]
                and (v["plp"] or 0) > 0)


def broken_clock(v):
    base = P.vol_base30(v)
    return bool(base and v["pl"] and v["pc"] and v["pl"] >= v["pc"] * 1.05
                and (v["tvol"] or 0) > base and (v["tno"] or 0) > 30)


def broken_susp(v):
    base = P.vol_base30(v)
    return bool(base and (v["tvol"] or 0) > 10 * base and (v["tno"] or 0) > 50)


def broken_roobi(v):
    return bool(v["pl"] is not None and v["tmin"] and v["pl"] == v["tmin"]
                and (v["zd1"] or 0) > 1 and (v["qd1"] or 0) > 100)


BROKEN = {"clock": broken_clock, "susp": broken_susp, "roobi": broken_roobi,
          "jet": broken_jet}


def main():
    body = requests.get(APP + "/api/market", timeout=180).json()
    app = {r["ins_code"]: r for r in body["data"]}
    c = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    db = {r["ins_code"]: dict(r) for r in c.execute("SELECT * FROM market_watch")}
    ct = {r["ins_code"]: dict(r) for r in c.execute("SELECT * FROM client_type")}
    newest = c.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
    c.close()
    hist, hn, hsrc, hrows = P.load_hist(None, DB)

    rows = []
    for code, d in db.items():
        py, pl = d.get("price_yesterday"), d.get("p_last")
        rows.append({"code": code, "ih": hist.get(code) or [], "pl": pl,
                     "pc": d.get("p_closing"), "py": py, "tmin": d.get("allowed_min"),
                     "tvol": d.get("q_tot_tran"), "tno": d.get("z_tot_tran"),
                     "zd1": d.get("buy_q1_cnt"), "qd1": d.get("buy_q1_vol"),
                     "bp": (ct.get(code, {}).get("buy_i_vol"), ct.get(code, {}).get("buy_count_i")),
                     "sp": (ct.get(code, {}).get("sell_i_vol"), ct.get(code, {}).get("sell_count_i")),
                     "plp": (round(100.0 * (pl - py) / py, 2) if (py and pl is not None) else None),
                     "live": d.get("d_even") == newest})
    print(f"منبع: {len(rows)} ردیف، بدنة rev={body.get('rev')}")
    clean, broken = {}, {}
    for name, fn in BROKEN.items():
        b = sum(1 for v in rows if app.get(v["code"]) and
                (bool(fn(v)) and v["live"]) != bool(app.get(v["code"]).get(FLAG[name])))
        orig = dict(P.CHECKS)[name]
        broken[name] = b
        # همان متنِ درست، برایِ مقایسه
        clean[name] = sum(1 for v in rows if app.get(v["code"]) and
                          (bool(orig(v)) and v["live"]) != bool(app.get(v["code"]).get(FLAG[name])))
    for name in BROKEN:
        verdict = "حساس ✔" if broken[name] > 0 else "کور ✘ — سنجش بی‌اعتبار است"
        print(f"  {name:7s} ناهمخوانیِ متنِ درست={clean[name]:4d}   "
              f"متنِ خراب={broken[name]:4d}   {verdict}")
    return 0 if all(broken[n] > 0 for n in BROKEN) else 1


if __name__ == "__main__":
    sys.exit(main())
