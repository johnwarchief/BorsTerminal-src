# -*- coding: utf-8 -*-
"""_audit/live_filter_triage.py — سه‌نمونۀ هم‌زمان: سایت / بانک / بدنهٔ API

پرسشِ این دور: اختلافِ شمارِ پنج فیلتر (سنجش ۱۴۰۵-۰۷-۱۲ ۱۰:۱۳: کف‌روبی سایت ۵۰
در برابرِ برنامه ۴۹) از کدام طبقه است؟

سه منبع در یک لحظه (فاصله‌شان چاپ می‌شود، چون سنجشِ دو منبع در دو ساعتِ متفاوت
دو «اختلافِ دادهٔ جعلی» ساخت — قاعدۀ ثابتي در حافظهٔ پروژه):

  1) سایت: GetMarketWatch + GetClientTypeAll + [ih] از tape_history، با پنج
     متنِ فیلترِ رومیزیِ مالک (همانِ tools/tse_live_filter_parity.py).
  2) بانک: market_watchِ همان لحظه — یعنی «برنامه درست بنویسد، فیلتر چه می‌گوید».
  3) بدنهٔ API: ستون‌های f_* همان چیزی که کاربر در تابلو می‌بیند.

طبقه‌بندیِ هر نمادِ اختلاف‌دار:
  • app != db            → حالتِ داغ / قابِ ایستا کهنه است (باگِ کدِ ما)
  • app == db != site    → تاخیرِ داده (چرخۀ ۵ ثانیه، رفتارِ شناخته‌شده)
  • db != site با همان ورودی → اختلافِ فرمول/نگاشت
"""
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd                                    # noqa: E402
import requests                                        # noqa: E402
import tape_flags                                      # noqa: E402
import tools.tse_live_filter_parity as P               # noqa: E402

APP = os.environ.get("TRIAGE_APP", "http://127.0.0.1:8002")
DB = os.environ.get("TRIAGE_DB", "market.db")
NAMES = ("clock", "susp", "jet", "roobi", "noqteh")


def db_inputs(codes):
    c = sqlite3.connect(f"file:{DB.replace(os.sep,'/')}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    rows = {}
    q = ("SELECT ins_code, d_even, h_even, p_closing, p_last, price_yesterday,"
         " price_change, q_tot_tran, z_tot_tran, allowed_min, allowed_max,"
         " price_min, price_max, buy_q1_vol, buy_q1_cnt, pe, eps "
         " FROM market_watch")
    for r in c.execute(q):
        rows[r["ins_code"]] = dict(r)
    c.close()
    return rows


def verdicts_from_flags_df(df):
    f = tape_flags.apply_tape_flags(df)
    return {n: set(df.loc[f[{"clock": "f_clock", "susp": "f_susp", "jet": "f_jet",
                             "roobi": "f_roobi", "noqteh": "f_noqteh"}[n]].fillna(False)
                        .astype(bool).index, "ins_code"])
            for n in NAMES}, f


def main():
    t0 = time.time()
    mw, err = P.get(P.MW_URL, "marketwatch")
    if not mw:
        sys.exit("site fetch failed: " + str(err))
    t1 = time.time()
    ct_rows, _ = P.get(P.CT_URL, "clientTypeAllDto")
    ct = {r.get("insCode"): r for r in (ct_rows or [])}
    hist, newest, hsrc, hrows = P.load_hist(None, DB)
    body = requests.get(APP + "/api/market?fields=all", timeout=180).json()
    t2 = time.time()
    app_rows = {r["ins_code"]: r for r in body["data"]}
    db_rows = db_inputs(None)
    t3 = time.time()

    print(f"زمانِ نمونه‌ها: site={t1-t0:.2f}s  +ct/app={t2-t1:.2f}s  +db={t3-t2:.2f}s  "
          f"کل={t3-t0:.2f}s | مرجعِ [ih]: {hsrc} newest={newest}")
    print(f"universe: site_rows={len(mw)} app_rows={len(app_rows)} db_rows={len(db_rows)} "
          f"app_live={body.get('live_count')} rev={body.get('rev')}")
    sc = {r.get("insCode") for r in mw}
    print(f"universe ⊂: site\\app={len(sc - set(app_rows))}  app\\site(live)={len(set(app_rows) - sc)}")

    # ۱) سایت
    site = {n: set() for n in NAMES}
    site_v = {}
    for mw_row in mw:
        v = P.site_row(mw_row, hist, ct)
        site_v[v["code"]] = v
        for n, fn in P.CHECKS:
            if fn(v):
                site[n].add(v["code"])

    # ۲) بانک — همان نگاشتِ محصول، رویِ ردیفِ market_watch (بدونِ API)
    codes = sorted(sc & set(db_rows))
    df = pd.DataFrame([dict(db_rows[k], symbol=k) for k in codes])
    df["ins_code"] = df["ins_code"].astype(str)
    # متغیرهایِ موردنیاز tape_flags از جدول‌های دیگر می‌آیند؛ همان‌ها را از بدنهٔ
    # API (که سازندۀ تابلو ساخته) می‌گیریم تا «فرمولِ بانک» واقعاً فرمولِ محصول باشد.
    for col in ("tmin", "tmax", "min_low_29", "prior30_vol", "hist_sessions",
                "h2_max", "h5_max", "h9_max", "h19_max", "h29_max", "h39_max",
                "h49_max", "h59_max", "min30_low", "max30_high", "month_avg_vol",
                "prev_day_vol", "buy_count_i", "sell_count_i", "buy_i_vol",
                "sell_i_vol", "percent_last", "tvoll", "d1_vol"):
        if col in ("tmin", "tmax"):
            df[col] = df["allowed_min"] if col == "tmin" else df["allowed_max"]
        elif col == "percent_last":
            df[col] = [((app_rows.get(k) or {}).get("percent_last")) for k in df["ins_code"]]
        elif col not in df.columns:
            df[col] = [((app_rows.get(k) or {}).get(col)) for k in df["ins_code"]]
    df["tvol"] = df["q_tot_tran"]
    df["is_live"] = [((app_rows.get(k) or {}).get("is_live")) for k in df["ins_code"]]
    dbv, flags_db = verdicts_from_flags_df(df)

    # ۳) بدنهٔ API
    appv = {n: {k for k, r in app_rows.items()
               if r.get({"clock": "f_clock", "susp": "f_susp", "jet": "f_jet",
                         "roobi": "f_roobi", "noqteh": "f_noqteh"}[n])}
            for n in NAMES}

    label = {k: (app_rows.get(k) or {}).get("symbol") for k in app_rows}
    out = {"instant_s": round(t3 - t0, 2), "universe": {"site": len(sc),
           "app": len(app_rows), "db": len(db_rows)}, "filters": {}}
    for n in NAMES:
        only_site = site[n] - appv[n]
        only_app = appv[n] - site[n]
        # طبقه‌بندیِ تک‌تکِ اختلاف‌ها
        cls = {}
        for code in (only_site | only_app):
            in_db = code in dbv[n]
            if code in only_site:
                if not in_db:
                    k = "db-هم-ندارد ⇒ تاخیر/فقدانِ داده"
                else:
                    k = "db دارد ولی app نه ⇒ بدنهٔ کهنه (حالتِ داغ)"
            else:
                k = ("app دارد db ندارد ⇒ بدنهٔ کهنه" if not in_db
                     else "app زودتر از سایت ⇒ تاخیرِ سایت/زمان")
            v = site_v.get(code) or {}
            cls[code] = {"label": label.get(code), "dir": "only_site" if code in only_site else "only_app",
                         "in_db": in_db,
                         "site": {kk: v.get(kk) for kk in ("pl", "tmin", "pc", "plp", "zd1", "qd1", "tvol", "tno")},
                         "app": {kk: (app_rows.get(code) or {}).get(kk) for kk in
                                 ("p_last", "tmin", "percent_last", "buy_q1_cnt", "buy_q1_vol", "tvol",
                                  "z_tot_tran", "f_" + n)},
                         "class": k}
        out["filters"][n] = {"site": len(site[n]), "db": len(dbv[n]), "app": len(appv[n]),
                             "only_site": len(only_site), "only_app": len(only_app),
                             "detail": cls}
        d = out["filters"][n]
        print(f"  {n:7s} site={d['site']:4d} db={d['db']:4d} app={d['app']:4d} "
              f"only_site={d['only_site']} only_app={d['only_app']}")
        for code, cinfo in list(cls.items())[:8]:
            print(f"     {cinfo['label']} [{cinfo['dir']}] {cinfo['class']}")
            print(f"        site={cinfo['site']}")
            print(f"        app ={cinfo['app']}")
    outp = os.path.join("_audit", "live_filter_triage.json")
    json.dump(out, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", outp)


if __name__ == "__main__":
    main()
