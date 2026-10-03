# -*- coding: utf-8 -*-
"""_audit/ta_field_identity.py — معنایِ فیلدهایِ تریدرزآرنا را با *برابریِ عددی* پیدا می‌کند

چرا این روش: باندلِ آن‌ها obfuscate است (`_0x…`) و `/market` شان ۴۰۴ می‌دهد، پس
«فرمولِ آن‌ها» از کدِ خودشان خوانده نمی‌شود. حدس زدنِ معنیِ `m[7]` هم ممنوع است
(قاعدهٔ مالک: هیچ فرمولی حدس نشود). تنها راهِ اثبات‌پذیر: **همان مقدار را از
خودِ TSETMC حساب کن و ببین کدام عددِ آن‌ها با کدام جمعِ ما برابری می‌کند.**
برابریِ دقیق در چند نمونهٔ پشت‌سرهم (با دادهٔ متحرک) تصادفی نیست ⇒ هویت ثابت شده.

سه طرف در یک لحظه:
  TSETMC  = مرجعِ خام (GetMarketWatch + GetClientTypeAll)
  TA      = فیدهایِ عمومیِ tradersarena.ir (/data/market0، /data/market/chart/totals0،
            /data/market/histo-status)
  ما      = /api/mstat/{summary,smart-money,depth,thermometer}

خروجی: برایِ هر عنصرِ آرایهٔ TA، کاندیداهایی که عیناً برابرند (با تلورانسِ گردکردن)
و برایِ هر عددِ نبضِ ما، هم‌ارزِ TA و اختلاف.
"""
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests                      # noqa: E402
import tools.tse_live_filter_parity as P  # noqa: E402

TA = "https://tradersarena.ir"
TA_H = {"User-Agent": "Mozilla/5.0", "Referer": TA + "/", "Accept": "application/json"}
APP = os.environ.get("ID_APP", "http://127.0.0.1:8002")
RIAL = 1.0
BT = 1e9          # میلیارد تومان
HT = 1e13         # همت (تومان)


def jget(url, hdr=None):
    r = requests.get(url, headers=hdr or TA_H, timeout=90)
    r.raise_for_status()
    return r.json()


def candidates(mw, ct):
    """جمع‌هایِ مستقیمِ TSETMC — هر کاندید با واحدِ خودش."""
    tot = {"val": 0.0, "vol": 0.0, "trn": 0.0, "buy_i": 0.0, "sell_i": 0.0,
           "buy_n": 0.0, "sell_n": 0.0, "bq_val": 0.0, "sq_val": 0.0,
           "pos": 0, "neg": 0, "zero": 0, "notraded": 0, "n": 0,
           "val_stock": 0.0, "flow_stock": 0.0}
    byc = {r.get("insCode"): r for r in ct}
    for r in mw:
        c = byc.get(r.get("insCode")) or {}
        val = float(r.get("qtc") or 0)          # ریال
        vol = float(r.get("qtj") or 0)
        trn = float(r.get("ztt") or 0)
        pcl = float(r.get("pcl") or 0)
        py = float(r.get("py") or 0)
        tot["n"] += 1
        tot["val"] += val
        tot["vol"] += vol
        tot["trn"] += trn
        tot["buy_i"] += float(c.get("buy_I_Volume") or 0)
        tot["sell_i"] += float(c.get("sell_I_Volume") or 0)
        tot["buy_n"] += float(c.get("buy_N_Volume") or 0)
        tot["sell_n"] += float(c.get("sell_N_Volume") or 0)
        tot["bq_val"] += float(r.get("bv") or 0) * 0.0   # جمعِ صف از blDs نمی‌آید؛ جایِ خودکار
        tot["sq_val"] += 0.0
        if val > 0:
            if pcl > py:
                tot["pos"] += 1
            elif pcl < py:
                tot["neg"] += 1
            else:
                tot["zero"] += 1
        else:
            tot["notraded"] += 1
    tot["flow_stock"] = tot["buy_i"] - tot["sell_i"]
    return tot


def match_arrays(ta_obj, cands, samples):
    """برایِ هر شاخصِ آرایه‌ایِ TA، کاندیداهایی که در *همه* نمونه‌ها برابرند."""
    out = {}
    n = len(samples[0])
    for i in range(n):
        vals = [s[i] for s in samples]
        hits = []
        for name, cv in cands.items():
            if not isinstance(cv, (int, float)) or cv == 0:
                continue
            ok = True
            for v in vals:
                if v is None:
                    ok = False
                    break
                # نسبتِ واحدِ ثابت: ریال/تومان/ب.ت/همت
                m = any(abs(v - cv / u) <= max(0.02 * abs(v), 1.0) for u in
                        (1.0, 10.0, BT, HT, BT * 10, HT / 100.0))
                if not m:
                    ok = False
                    break
            if ok:
                hits.append(name)
        if hits:
            out[i] = {"values": vals, "equal_candidates": hits}
    return out


def main():
    t0 = datetime.now()
    samples = []
    for k in range(3):
        mw, err = P.get(P.MW_URL, "marketwatch")
        ct_rows, _ = P.get(P.CT_URL, "clientTypeAllDto")
        ta0 = jget(TA + "/data/market0")
        cands = candidates(mw, ct_rows or [])
        samples.append({"t": datetime.now().isoformat(timespec="seconds"),
                        "ta": ta0, "cands": cands})
        print(f"نمونۀ {k+1}: {cands['n']} ردیفِ تابلو، TA m[-1]={ta0.get('m')[-1] if isinstance(ta0.get('m'), list) else '?'} "
              f"@ {samples[-1]['t']}")
        if k < 2:
            time.sleep(7)

    # آرایه‌هایِ TA که شکلِ عددی دارند
    arr_keys = [k for k, v in samples[0]["ta"].items() if isinstance(v, list)]
    report = {"taken_at": samples[0]["t"], "arr_keys": arr_keys, "identity": {}}
    for key in arr_keys:
        series = [s["ta"][key] for s in samples]
        n = min(len(x) for x in series)
        report["identity"][key] = match_arrays(series[0], samples[-1]["cands"], [x[:n] for x in series])
        print(f"\n== TA['{key}'] (len {n}) — برابریِ عددی با جمع‌هایِ TSETMC ==")
        for i, info in sorted(report["identity"][key].items()):
            print(f"   m[{i}] {info['values']} ≡ {info['equal_candidates']}")
        un = [i for i in range(n) if i not in report["identity"][key]]
        print("   بی‌هم‌ارز:", un[:20])

    app = {}
    for path in ("/api/mstat/summary", "/api/mstat/smart-money", "/api/mstat/depth",
                 "/api/mstat/thermometer"):
        try:
            app[path] = requests.get(APP + path, timeout=90).json()
        except Exception as e:
            app[path] = {"error": str(e)[:80]}
    report["app"] = app
    out = os.path.join("_audit", "ta_field_identity.json")
    json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nما (خلاصه):")
    s = (app.get("/api/mstat/summary") or {}).get("rows") or []
    for r in s[:4]:
        print("  ", {k: r.get(k) for k in ("label", "symbols", "value_b_toman", "money_flow_b_toman",
                                          "pc_buy_m_toman", "pc_sell_m_toman", "buy_power")})
    print(f"  depth: {json.dumps({k:(app.get('/api/mstat/depth') or {}).get(k) for k in ('buy_value','sell_value','ratio','symbols_with_depth')},ensure_ascii=False)}")
    print(f"  thermo: {json.dumps({k:(app.get('/api/mstat/thermometer') or {}).get(k) for k in ('positive','negative','zero','not_traded','known','positive_pct')},ensure_ascii=False)}")
    print("wrote", out, " elapsed", round((datetime.now()-t0).total_seconds(), 1), "s")


if __name__ == "__main__":
    main()
