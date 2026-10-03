# -*- coding: utf-8 -*-
"""_audit/live_filter_triage2.py — parity بی‌دست‌کاریِ زمان

نسخۀ اول (triage.py) نشان داد تمامِ اختلاف‌هایِ شمارِ فیلترها از *جابه‌جاییِ
قیمت در فاصلۀ دو نمونه* می‌آید: site و app چند ثانیه فرق داشتند و بدنۀ app
خودش تا پنج ثانیه کهنه‌تر (سنجش: كايزد pl=3910 در سایت، p_last=3900 در برنامه؛
قصفها 2314 در سایت، 2315 در برنامه). پس برایِ داوریِ «فرمول غلط است یا داده»
باید زمان را از معادلۀ مقابله بیرون کرد.

سه سنجشِ بی‌دست‌کاریِ زمان، همه رویِ **یک** منبعِ عدد:

  A) بدنهٔ API در برابرِ market_watchِ همان لحظه (ستون‌هایِ خام) — ثابت می‌کند
     حالتِ داغ چیزی جزِ بانک نمی‌فروشد؛
  B) پرچم‌هایِ API در برابرِ پنج متنِ فیلترِ مالک که رویِ **همان ردیفِ بانک**
     اجرا می‌شوند — ثابت می‌کند فرمولِ محصول = فرمولِ فایل؛
  C) پوشش: کدام نمادهایِ تابلویِ سایت در بانکِ ما نیستند، و کدام ردیف‌هایِ بانک
     «زنده» شمرده نمی‌شوند.

اختلافِ شمارِ دو منبعِ زنده (site vs app) درِ این اسکریپت «اختلاف» نیست؛ فقط
گزارشِ فاصلۀ زمانی و تعدادش است.
"""
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd                    # noqa: E402
import requests                        # noqa: E402
import tape_flags                      # noqa: E402
import tools.tse_live_filter_parity as P  # noqa: E402
import test_tsetmc as T                 # noqa: E402

APP = os.environ.get("TRIAGE_APP", "http://127.0.0.1:8002")
DB = os.environ.get("TRIAGE_DB", "market.db")
RAW = ("p_last", "p_closing", "q_tot_tran", "z_tot_tran", "allowed_min",
       "buy_q1_vol", "buy_q1_cnt", "d_even")
FLAG = {"clock": "f_clock", "susp": "f_susp", "jet": "f_jet",
        "roobi": "f_roobi", "noqteh": "f_noqteh"}


def main():
    body = requests.get(APP + "/api/market?fields=all", timeout=180).json()
    app = {r["ins_code"]: r for r in body["data"]}
    t_app = time.time()
    c = sqlite3.connect(f"file:{DB.replace(os.sep,'/')}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    db = {r["ins_code"]: dict(r) for r in c.execute("SELECT * FROM market_watch")}
    newest = c.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
    c.close()
    hist, hn, hsrc, hrows = P.load_hist(None, DB)

    # ── A) خام: بدنۀ RAM/قاب در برابرِ بانک ────────────────────────────
    raw_bad = {}
    for code, d in db.items():
        r = app.get(code)
        if not r:
            continue
        for col in RAW:
            if col in ("buy_q1_vol", "buy_q1_cnt"):
                av = r.get("buy_q1_vol" if col == "buy_q1_vol" else "buy_q1_cnt")
            elif col == "allowed_min":
                av = r.get("tmin")
            elif col == "p_closing":
                av = r.get("p_closing")
            else:
                av = r.get(col)
            dv = d.get(col)
            if av is None and dv in (None, 0):
                continue
            if (av or 0) != (dv or 0):
                raw_bad.setdefault(code, []).append((col, av, dv))
    print(f"A) خامِ API == market_watch: {len(raw_bad)} نمادِ ناهمخوان از {len(db)} "
          f"(بدنۀ rev={body.get('rev')} در {time.time()-t_app:.2f}s پس از خواندنِ بانک)")
    for code, items in list(raw_bad.items())[:8]:
        print("   ", (app.get(code) or {}).get("symbol"), items[:4])

    # ── B) فرمول: پنج متنِ فایل رویِ ردیفِ بانک، در برابرِ پرچمِ API ──────
    mw, _ = P.get(P.MW_URL, "marketwatch")
    site_codes = {r.get("insCode") for r in (mw or [])}
    ct_rows, _ = P.get(P.CT_URL, "clientTypeAllDto")
    ct = {r.get("insCode"): r for r in (ct_rows or [])}
    rows = []
    for code, d in db.items():
        v = {"code": code, "ih": hist.get(code) or [], "pl": d.get("p_last"),
             "pc": d.get("p_closing"), "py": d.get("price_yesterday"),
             "tmin": d.get("allowed_min"), "tmax": d.get("allowed_max"),
             "tvol": d.get("q_tot_tran"), "tno": d.get("z_tot_tran"),
             "zd1": d.get("buy_q1_cnt"), "qd1": d.get("buy_q1_vol"),
             "bp": (d.get("buy_i_vol"), d.get("buy_count_i")),
             "sp": (d.get("sell_i_vol"), d.get("sell_count_i"))}
        chg = d.get("price_change")
        py = d.get("price_yesterday")
        v["plp"] = round(100.0 * chg / py, 2) if (chg is not None and py) else None
        rows.append(v)
    bad_formula = {}
    for v in rows:
        r = app.get(v["code"])
        if not r:
            continue
        for name, fn in P.CHECKS:
            want = bool(fn(v))
            got = bool(r.get(FLAG[name]))
            if want != got:
                bad_formula.setdefault((name, "want" if want else "got"), []).append(v["code"])
    print(f"\nB) فرمول: پنج متنِ فایل رویِ ردیفِ بانک == پرچمِ API? "
          f"ناهمخوانی={sum(len(x) for x in bad_formula.values())}")
    for (name, side), codes in list(bad_formula.items())[:10]:
        print(f"    {name} {side}: {len(codes)} → "
              f"{[ (app.get(k) or {}).get('symbol') for k in codes[:6] ]}")

    # ── C) پوشش ────────────────────────────────────────────────────────
    missing_in_db = sorted(site_codes - set(db))
    not_live = [k for k, r in app.items() if r.get("is_live") is False and k in site_codes]
    print(f"\nC) universe: site={len(site_codes)} db={len(db)} newest_d_even={newest}")
    print(f"    درِ سایت ولی درِ بانک نیست: {len(missing_in_db)} "
          f"{[ (r.get('lva'), r.get('insCode')) for r in (mw or []) if r.get('insCode') in set(missing_in_db)][:10] }")
    print(f"    درِ بانک و درِ سایت ولی 'زنده' نیست: {len(not_live)}")

    # ── D) شمارِ زندهٔ دو طرف + فاصلۀ زمانی ─────────────────────────────
    site_counts = {n: set() for n, _ in P.CHECKS}
    for mw_row in (mw or []):
        v = P.site_row(mw_row, hist, ct)
        for name, fn in P.CHECKS:
            if fn(v):
                site_counts[name].add(v["code"])
    app_counts = {n: {k for k, r in app.items() if r.get(FLAG[n])} for n in FLAG}
    print("\nD) شمارِ زنده (site در برابرِ app) — با فاصلۀ زمانیِ گزارش‌شده:")
    for name in FLAG:
        s, a = site_counts[name], app_counts.get(name, set())
        print(f"    {name:7s} site={len(s):4d} app={len(a):4d} "
              f"only_site={len(s-a):3d} only_app={len(a-s):3d} shared={len(s&a)}")
    json.dump({"raw_mismatch": len(raw_bad),
               "formula_mismatch": {f"{k[0]}/{k[1]}": len(v) for k, v in bad_formula.items()},
               "missing_in_db": missing_in_db,
               "site_counts": {k: len(v) for k, v in site_counts.items()},
               "app_counts": {k: len(v) for k, v in app_counts.items()}},
              open(os.path.join("_audit", "live_filter_triage2.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nwrote _audit/live_filter_triage2.json")


if __name__ == "__main__":
    main()
