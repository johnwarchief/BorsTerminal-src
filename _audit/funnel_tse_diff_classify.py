# -*- coding: utf-8 -*-
"""_audit/funnel_tse_diff_classify.py — رده‌بندیِ اختلاف‌هایِ باقی‌مانده درِ تابلو

بند ۳۳ِ مأموریت: اختلاف را برایِ سبز شدنِ تست پنهان نکن. این اسکریپت برایِ هر
نمادی که «فقط اپ» پرچم خورده، ورودیِ همان لحظۀ سایت را کنارِ ورودیِ اپ می‌گذارد
تا معلوم شود اختلاف از **داده** است (نماد درِ پاسخِ زندۀ سایت نیست / عدد فرق دارد)
یا از **قاعده** (همان عدد، دو رأی).

اجرا:  python -X utf8 _audit/funnel_tse_diff_classify.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import tse_live_filter_parity as P  # noqa: E402

APP = os.environ.get("BORS_APP", "http://127.0.0.1:8001")
EVALS = {"clock": P.eval_clock, "susp": P.eval_susp, "jet": P.eval_jet,
         "roobi": P.eval_roobi, "noqteh": P.eval_noqteh, "smart": P.eval_smart,
         "legal": P.eval_legal}


def main() -> int:
    rep = json.load(open(os.path.join(ROOT, "_audit", "tse_filter_parity_final.json"),
                         encoding="utf-8"))
    need = {}
    for filt, d in (rep.get("diffs") or {}).items():
        for code in d.get("only_app_codes") or []:
            need[code] = filt
    if not need:
        print("هیچ اختلافِ «فقط اپ»ی نمانده است.")
        return 0

    mw, err_mw = P.get(P.MW_URL, "marketwatch")
    ct, err_ct = P.get(P.CT_URL, "clientTypeAllDto")
    if err_mw or err_ct:
        print("پاسخِ سایت نشد:", err_mw, err_ct)
        return 1
    mw = mw or []
    ct = ct or []
    hist, newest, src, _rows = P.load_hist(None, os.path.join(ROOT, "market.db"))
    by_code = {str(r.get("insCode")): r for r in mw}
    ct_by = {str(c.get("insCode")): c for c in ct}

    rows = json.load(urllib.request.urlopen(f"{APP}/api/market", timeout=180))["data"]
    app_by = {str(r.get("ins_code")): r for r in rows}

    print(f"تاریخچۀ مرجع: {src} (تازۀترین نشست {newest})")
    print("| نماد | فیلتر | درِ پاسخِ سایت؟ | رأیِ سایت رویِ دادهٔ سایت | ورودیِ سایت (pl/pc/tvol/tno/tmin) | ورودیِ اپ (pl/pc/tvol/tno/tmin) | رده‌بندی |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    out = []
    for code, filt in sorted(need.items(), key=lambda kv: (kv[1], str(kv[0]))):
        a = app_by.get(code) or {}
        s = by_code.get(code)
        sym = a.get("symbol") or (s or {}).get("insName") or code
        if not s:
            verdict = "DATA_DIFFERENCE — نماد درِ GetMarketWatchِ زنده نیست"
            print(f"| {sym} | {filt} | نه | — | — | "
                  f"{a.get('p_last')}/{a.get('p_closing')}/{a.get('tvol')}/{a.get('q_tot_tran')}/{a.get('tmin')} "
                  f"| {verdict} |")
            out.append({"code": code, "symbol": sym, "filter": filt, "in_site_payload": False,
                        "classification": "DATA_DIFFERENCE"})
            continue
        v = P.site_row(s, hist, ct_by)
        site_says = bool(EVALS[filt](v))
        # مقایسهٔ *همۀ* متغیرهایی که خودِ فرمول می‌خواند — بی‌این، «ورودی یکی است»
        # را رویِ پنج ستون می‌گفتی و اختلافِ clientType پنهان می‌ماند.
        pairs = {
            "pl": (v["pl"], a.get("p_last")), "pc": (v["pc"], a.get("p_closing")),
            "tvol": (v["tvol"], a.get("tvol")), "tno": (v["tno"], a.get("z_tot_tran")),
            "tmin": (v["tmin"], a.get("tmin")), "zd1": (v["zd1"], a.get("min30_low")),
            "bp": (v["bp"], (a.get("buy_i_vol"), a.get("buy_count_i"))),
            "sp": (v["sp"], (a.get("sell_i_vol"), a.get("sell_count_i"))),
            "sn": (v["sn"], a.get("sell_n_vol")),
            "h_len": (len(v["ih"] or []), a.get("hist_sessions")),
        }
        diff_keys = [k for k, (x, y) in pairs.items() if str(x) != str(y)]
        # «ورودی یکی است» تنها وقتی گفته می‌شود که ده متغیرِ می‌خواندۀ فرمول
        # بخوانند؛ پنج‌تایی‌اش RULE_DIFFERENCEِ جعلی می‌ساخت (اختلافِ clientType
        # و تاریخچه پنهان می‌ماند).
        same_inputs = not diff_keys
        if site_says:
            cls = "DATA_DIFFERENCE — سایت در این لحظه همان رأی را می‌دهد (اسنپ‌شات‌ها فرق دارند)"
        elif same_inputs:
            cls = "**RULE_DIFFERENCE** — هر ده ورودی یکی است، رأی نه"
        else:
            cls = ("DATA_DIFFERENCE — ورودی‌ها فرق دارند: " + ",".join(diff_keys)) if diff_keys                   else "ورودیِ کامل یکی است"
        print(f"| {sym} | {filt} | بله ({s.get('dEven')}/{s.get('hEven')}) | {site_says} "
              f"| {v['pl']}/{v['pc']}/{v['tvol']}/{v['tno']}/{v['tmin']} "
              f"| {a.get('p_last')}/{a.get('p_closing')}/{a.get('tvol')}/{a.get('z_tot_tran')}/{a.get('tmin')} "
              f"| ستون‌هایِ فرقان: {','.join(diff_keys) or 'هیچ'} | {cls} |")
        out.append({"code": code, "symbol": sym, "filter": filt, "in_site_payload": True,
                    "site_verdict": site_says, "same_inputs": same_inputs,
                    "site_inputs": {k: (list(v[k]) if isinstance(v[k], tuple)
                                        else (len(v["ih"]) if k == "ih" else v[k]))
                                    for k in ("pl", "pc", "tvol", "tno", "tmin", "zd1", "bp", "sp", "sn")},
                    "app_inputs": {k: a.get(k) for k in ("p_last", "p_closing", "tvol", "z_tot_tran",
                                                         "tmin", "min30_low", "buy_i_vol", "buy_count_i",
                                                         "sell_i_vol", "sell_count_i", "hist_sessions")},
                    "differing_inputs": diff_keys,
                    "input_pairs": {k: [list(x) if isinstance(x, tuple) else x,
                                        list(y) if isinstance(y, tuple) else y]
                                    for k, (x, y) in pairs.items()},
                    "classification": cls})
    with open(os.path.join(ROOT, "_audit", "funnel_tse_diff_classify.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"written _audit/funnel_tse_diff_classify.json ({len(out)} ردیف)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
