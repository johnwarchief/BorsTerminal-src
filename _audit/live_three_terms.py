# -*- coding: utf-8 -*-
"""_audit/live_three_terms.py — کالبدشکافیِ سه باقی‌ماندهٔ فرمول

اجرایِ triage3 سه ردیف را باقی گذاشت که پرچمِ محصول True است و متنِ فایل رویِ
همان ردیفِ بانک False: jet=دهدشت، jet=خصدرا، roobi=طخود8053. مقایسه‌هایِ
دومنبعه نمی‌توانند بگویند «فرمول غلط است» یا «دو ثانیه قیمت جابه‌جا شد»؛ این
اسکریپت هر شرطِ فرعیِ متنِ فایل را جدا می‌شکافد و هم‌زمان از سه منبع می‌خواند:

  1. بدنهٔ API (نام‌هایِ رویِ سیم)
  2. market_watch + client_type درِ بانک (همان لحظه)
  3. تابلویِ زندهٔ سایت (hEven/تغییر٪ و ct حقوقی/حقیقی)

هر شرطِ فرعی با مقدارِ هر سه منبع چاپ می‌شود ⇒ تکلیفِ «داده/فرمول/پوشش» روشن.
فقط خواندن.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests                            # noqa: E402
import tools.tse_live_filter_parity as P   # noqa: E402

APP = os.environ.get("TRIAGE_APP", "http://127.0.0.1:8001")
DB = os.environ.get("TRIAGE_DB", "market.db")
WANT = {"دهدشت": "jet", "خصدرا": "jet", "طخود8053": "roobi"}


def main():
    body = requests.get(APP + "/api/market", timeout=180).json()
    by_sym = {r.get("symbol"): r for r in body["data"]}
    c = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    mw = {r["ins_code"]: dict(r) for r in c.execute("SELECT * FROM market_watch")}
    ct = {r["ins_code"]: dict(r) for r in c.execute("SELECT * FROM client_type")}
    newest = c.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
    hist, hn, hsrc, hrows = P.load_hist(None, DB)
    c.close()

    site, _ = P.get(P.MW_URL, "marketwatch")
    ct_rows, _ = P.get(P.CT_URL, "clientTypeAllDto")
    site_ct = {r.get("insCode"): r for r in (ct_rows or [])}
    site_by = {}
    for m in (site or []):
        site_by[m.get("lVal18")] = (m, P.site_row(m, hist, site_ct))

    print(f"rev={body.get('rev')} بانک newest={newest} تاریخچه={hsrc}")
    for sym, fname in WANT.items():
        r = by_sym.get(sym)
        if not r:
            print(f"\n### {sym}: درِ بدنهٔ API نیست")
            continue
        code = r["ins_code"]
        d = mw.get(code, {})
        k = ct.get(code, {})
        srow, sv = site_by.get(sym, (None, None))
        print(f"\n### {sym} ({fname})  flag={r.get('f_' + fname)}  "
              f"d_even={d.get('d_even')} hEven={d.get('h_even')}")
        pl, pc, py = d.get("p_last"), d.get("p_closing"), d.get("price_yesterday")
        chg = d.get("price_change")
        plp = round(100.0 * chg / py, 2) if (chg is not None and py) else None
        print(f"  بانک : pl={pl} pc={pc} py={py} chg={chg} plp={plp} "
              f"tmin={d.get('allowed_min')} tvol={d.get('q_tot_tran')} tno={d.get('z_tot_tran')} "
              f"zd1={d.get('buy_q1_cnt')} qd1={d.get('buy_q1_vol')} "
              f"sd1={d.get('sell_q1_cnt')} qd1s={d.get('sell_q1_vol')}")
        print(f"  ct   : buy_i_vol={k.get('buy_i_vol')} buy_cnt={k.get('buy_count_i')} "
              f"sell_i_vol={k.get('sell_i_vol')} sell_cnt={k.get('sell_count_i')}")
        print(f"  API  : " + json.dumps({x: r.get(x) for x in
              ("p_last", "p_closing", "price_change", "yesterday", "tmin", "q_tot_tran",
               "z_tot_tran", "buy_q1_cnt", "buy_q1_vol", "last_px", "p_open")},
              ensure_ascii=False))
        if sv:
            print(f"  سایت : pl={sv['pl']} pc={sv['pc']} py={sv['py']} plp={sv['plp']} "
                  f"tmin={sv['tmin']} tvol={sv['tvol']} tno={sv['tno']} "
                  f"zd1={sv['zd1']} qd1={sv['qd1']} bp={sv['bp']} sp={sv['sp']}")
        else:
            print("  سایت : درِ تابلویِ زنده نیست (متوقف/حق‌تقدم؟)")
        ih = hist.get(code) or []
        v = {"code": code, "ih": ih, "pl": pl, "pc": pc, "py": py, "tmin": d.get("allowed_min"),
             "tmax": d.get("allowed_max"), "tvol": d.get("q_tot_tran"),
             "tno": d.get("z_tot_tran"), "zd1": d.get("buy_q1_cnt"),
             "qd1": d.get("buy_q1_vol"), "plp": plp,
             "bp": (k.get("buy_i_vol"), k.get("buy_count_i")),
             "sp": (k.get("sell_i_vol"), k.get("sell_count_i"))}
        ladder = P.ladder_high(v)
        base = P.vol_base30(v)
        print(f"  شرط‌ها: پلکان ih={len(ih)} سقفِ [59..2]={ladder} "
              f"مبناء30={base} 3×مبناء={(base * 3 if base else None)}")
        print(f"    jet: tvol>3Σ/30={bool(base) and (v['tvol'] or 0) > 3 * base} "
              f"bp_ratio={'%.3f' % (v['bp'][0] / v['bp'][1]) if v['bp'][1] else None} "
              f"sp_ratio={'%.3f' % (v['sp'][0] / v['sp'][1]) if v['sp'][1] else None} "
              f"pl>=pc={pl >= pc} plp>0={(plp or 0) > 0} tno>100={(v['tno'] or 0) > 100} "
              f"ladder<pl={None if ladder is None else ladder < pl}")
        print(f"    roobi: pl==tmin={pl == v['tmin']} zd1>1={(v['zd1'] or 0) > 1} "
              f"plp<-1={None if plp is None else plp < -1} qd1>100={(v['qd1'] or 0) > 100}")
        print(f"    evaluate(): jet={P.eval_jet(v)} roobi={P.eval_roobi(v)} "
              f"clock={P.eval_clock(v)} susp={P.eval_susp(v)}")


if __name__ == "__main__":
    main()
