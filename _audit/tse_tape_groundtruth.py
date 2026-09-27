"""مرجعِ TSETMC برایِ پنج فیلتر، ساخته‌شدە از خودِ دادهٔ سایت — نه از تفسیرِ ما.

نگاشتِ متغیرها عیناً از `ExecFilter` درِ باندلِ tsetmc.com برداشته شده است:

    (pl)=pdv  (pc)=pcl  (plc)=pc  (plp)=round(100*pc/py,2)  (py)=py
    (tno)=ztt (tvol)=qtj (tval)=qtc (bvol)=bv (cs)=csv
    (tmin)=pMin  (tmax)=pMax          ← آستانۀ مجاز، نه کفِ نشست
    (zd1)=blDs[0].zmd  (qd1)=blDs[0].qmd  (pd1)=blDs[0].pmd  ← سطر اولِ صف خرید
    (ct)  = clientType[ins]            ← Buy_I_Volume / Buy_CountI / …
    [ih][k].QTotTran5J = qtjِ ردیفِ kِمین روزنەِ منتشرشده (حجمِ همان نشست)
    [ih][k].PriceMin/PriceMax = pmn/pmxِ همان روزنە
    [ih] = ردیف‌هایِ روزینۀ همان نماد، نزولی بر dEven
           (سایت `GetClosingPriceDailyAllInst` را می‌گیرد؛ اینجا همان‌ها از
            `GetClosingPriceDailyList/{insCode}/0` — یکِ درخواست بر نماد)

خروجی: برایِ هر فیلتر، شمارِ ردیفِ «مرجع» و شمارِ «جدولِ ما» و سه نمونۀ اختلاف
به‌همراه قیدی که باعثِ اختلاف شده. کف‌روبی بی‌تاریخچه سنجیده می‌شود، پس رویِ
**کلِ تابلو** دقیق است؛ چهار فیلترِ دیگر به نمونۀ [ih] نیاز دارند و نمونه‌ای
سنجیده می‌شوند (در گزارش همینی ذکر می‌شود).

اجرا:
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe _audit/tse_tape_groundtruth.py [N]
"""
import json
import math
import os
import random
import sqlite3
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://cdn.tsetmc.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://tsetmc.com/",
    "Origin": "https://tsetmc.com",
}
_PT = "&".join(f"paperTypes[{i}]={i+1}" for i in range(9))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 250
DB = os.environ.get("BORS_DB", "market.db")

JET_LADDER = (2, 5, 9, 19, 29, 39, 49, 59)


def f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return math.nan
    return x if math.isfinite(x) else math.nan


def r2(v):
    return round(v, 2) if isinstance(v, (int, float)) and math.isfinite(v) else math.nan


def get_board():
    url = f"{BASE}/ClosingPrice/GetMarketWatch?market=0&{_PT}&showTraded=true&withBestLimits=true&hEven=0"
    rows = requests.get(url, headers=HEADERS, timeout=90).json().get("marketwatch") or []
    out = {}
    for r in rows:
        ins = r.get("insCode")
        if not ins:
            continue
        lines = r.get("blDs") or []
        out[ins] = {
            "sym": r.get("lva"), "pl": f(r.get("pdv")), "pc_close": f(r.get("pcl")),
            "pc_chg": f(r.get("pc")), "py": f(r.get("py")), "tno": f(r.get("ztt")),
            "tvol": f(r.get("qtj")), "tval": f(r.get("qtc")), "bvol": f(r.get("bv")),
            "sector": (r.get("csv") or "").strip(), "tmin": f(r.get("pMin")),
            "tmax": f(r.get("pMax")), "shares": f(r.get("ztd")),
            "zd1": f(lines[0].get("zmd")) if lines else math.nan,
            "qd1": f(lines[0].get("qmd")) if lines else math.nan,
            "pd1": f(lines[0].get("pmd")) if lines else math.nan,
            "plp": r2(100.0 * f(r.get("pc")) / f(r.get("py"))) if f(r.get("py")) else math.nan,
        }
    return out


def get_history(ins):
    """[ih]ِ همان نماد: ردیف‌هایِ روزینة منتشرشده، نزولی بر dEven."""
    url = f"{BASE}/ClosingPrice/GetClosingPriceDailyList/{ins}/0"
    rows = requests.get(url, headers=HEADERS, timeout=60).json().get("closingPriceDaily") or []
    rows.sort(key=lambda x: -(x.get("dEven") or 0))
    return [{"dEven": x.get("dEven"), "vol": f(x.get("qTotTran5J")), "lo": f(x.get("priceMin")),
             "hi": f(x.get("priceMax")), "tran": f(x.get("zTotTran")),
             "close": f(x.get("pClosing")), "last": f(x.get("pDrCotVal"))} for x in rows]


def get_client_types():
    """کلیدها عیناً همان‌اند که DTO می‌فرستد: `buy_I_Volume` با بِ کوچک.

    پیش از این «Buy_I_Volume» خوانده می‌شد، پس همه NaN و `power` برایِ همه
    False — یعنی مرجعِ جت برایِ همیشه صفر می‌ماند و اختلافِ واقعیِ جت هیچ‌وقت
    دیده نمی‌شد (درست همان چیزی که باید می‌سنجید).
    """
    keys = ("buy_I_Volume", "buy_CountI", "sell_I_Volume", "sell_CountI",
            "buy_N_Volume", "sell_N_Volume")
    rows = requests.get(f"{BASE}/ClientType/GetClientTypeAll", headers=HEADERS, timeout=90).json()
    out = {}
    for x in rows.get("clientTypeAllDto") or []:
        ins = x.get("insCode")
        if ins:
            out[ins] = {k: f(x.get(k)) for k in keys}
    return out


# ---- پنج فیلتر، عینِ فایل‌ها، با همان حسابِ JS (NaN → مردود) ----------------
def base30(ih):
    """Σ[ih][0..29].QTotTran5J / 30 — بی‌سیِ کامل NaN است، همان‌طور که در JS."""
    if len(ih) < 30:
        return math.nan
    return sum(x["vol"] for x in ih[:30]) / 30.0


def low29(ih):
    """کمینۀ [ih][0..28].PriceMin — حلقۀِ فایلِ نقطه‌زنی."""
    if len(ih) < 29:
        return math.nan
    vals = [x["lo"] for x in ih[:29]]
    return min(vals) if vals else math.nan


def ladder_ok(ih, pl):
    for k in JET_LADDER:
        if len(ih) <= k or not math.isfinite(ih[k]["hi"]):
            return False
        if not (ih[k]["hi"] < pl):
            return False
    return True


def f_roobi(b):
    return (b["pl"] == b["tmin"]) and (b["zd1"] > 1) and (b["plp"] < -1) and (b["qd1"] > 100)


def f_clock(b, ih):
    bs = base30(ih)
    return (b["pl"] >= b["pc_close"] * 1.02 and math.isfinite(bs)
            and b["tvol"] > bs and b["tno"] > 30)


def f_susp(b, ih):
    bs = base30(ih)
    return math.isfinite(bs) and b["tvol"] > 3 * bs and b["tno"] > 50


def f_noqteh(b, ih):
    bs, lo = base30(ih), low29(ih)
    if not (math.isfinite(bs) and math.isfinite(lo) and lo != 0 and b["pc_close"]):
        return False
    dist = round((b["pc_close"] - lo) / b["pc_close"] * 100 * 100) / 100
    return dist < 3 and b["tvol"] > bs and b["tno"] > 5


def f_jet(b, ih, ct):
    bs = base30(ih)
    c = ct.get(b["ins"]) or {}
    bc, sc = c.get("buy_CountI", 0.0), c.get("sell_CountI", 0.0)
    power = (c.get("buy_I_Volume", 0.0) / bc) >= 1.5 * (c.get("sell_I_Volume", 0.0) / sc) if (bc and sc) else False
    return (math.isfinite(bs) and b["tvol"] > 3 * bs and power
            and b["pl"] >= b["pc_close"] and b["plp"] > 0
            and b["tno"] > 1 and b["tno"] > 100 and ladder_ok(ih, b["pl"]))


# ---- جدولِ ما ---------------------------------------------------------------
def our_flags():
    import urllib.request
    raw = json.load(urllib.request.urlopen("http://127.0.0.1:8001/api/market", timeout=120))
    rows = raw.get("rows") or raw.get("data") or []
    if isinstance(raw, dict) and not rows:
        for v in raw.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "symbol" in v[0]:
                rows = v
                break
    return {r.get("ins_code") or r.get("insCode"): r for r in rows}, rows


def main():
    t0 = time.time()
    board = get_board()
    print(f"تابلو: {len(board)} ردیف  ({time.time()-t0:.1f}s)")
    ours, orows = our_flags()
    print(f"جدولِ ما: {len(ours)} ردیف")
    ct = get_client_types()
    print(f"clientType: {len(ct)} ردیف")

    # ۱) کف‌روبی رویِ کلِ تابلو (بی‌نیاز از تاریخچه)
    gt_roobi = {i for i, b in board.items() if f_roobi(b)}
    our_roobi = {i for i, r in ours.items() if r.get("f_roobi")}
    print(f"\n=== کف‌روبی (کلِ تابلو) ===\n  مرجعِ TSETMC: {len(gt_roobi)}   جدولِ ما: {len(our_roobi)}")
    for i in list(gt_roobi - our_roobi)[:8]:
        b = board[i]
        print(f"   فقط TSETMC: {b['sym']}  pl={b['pl']:,.0f} tmin={b['tmin']:,.0f} "
              f"zd1={b['zd1']:,.0f} qd1={b['qd1']:,.0f} plp={b['plp']}")
    for i in list(our_roobi - gt_roobi)[:8]:
        b = board.get(i, {})
        print(f"   فقط ما:      {b.get('sym')}  pl={b.get('pl')} tmin={b.get('tmin')} "
              f"zd1={b.get('zd1')} qd1={b.get('qd1')} plp={b.get('plp')} "
              f"| ستون‌هایِ ما: " + json.dumps({k: ours[i].get(k) for k in
                  ("p_last", "tmin", "buy_q1_cnt", "buy_q1_vol",
                   "percent_last", "percent_change")}, ensure_ascii=False))

    # ۲) چهار فیلترِ دیگر رویِ نمونە
    traded = [i for i, b in board.items() if f(b["tno"]) > 0]
    random.seed(1405)
    sample = random.sample(traded, min(N, len(traded)))
    hist, done = {}, 0
    for i in sample:
        try:
            hist[i] = get_history(i)
        except Exception as e:  # noqa: BLE001
            hist[i] = []
            print(f"   تاریخچۀ {board[i]['sym']} نیامد: {type(e).__name__}")
        done += 1
        if done % 25 == 0:
            print(f"  تاریخچه: {done}/{len(sample)}  ({time.time()-t0:.0f}s)")
        time.sleep(0.12)

    name = {"f_jet": "جت", "f_susp": "حجم مشکوک", "f_noqteh": "نقطه‌زنی", "f_clock": "الگوی ساعت"}
    print(f"\n=== چهار فیلتر رویِ نمونۀ {len(sample)} نمادی ===")
    for key, fn in (("f_clock", f_clock), ("f_susp", f_susp), ("f_noqteh", f_noqteh),
                    ("f_jet", lambda b, ih: f_jet(b, ih, ct))):
        gt = {i for i in sample if fn({**board[i], "ins": i}, hist[i])}
        our = {i for i in sample if ours.get(i, {}).get(key)}
        print(f"\n  {name[key]:<12} مرجع={len(gt):>4}   ما={len(our):>4}   "
              f"فقط TSETMC={len(gt-our):>3}  فقط ما={len(our-gt):>3}")
        for i in list(gt - our)[:5]:
            b, ih = board[i], hist[i]
            print(f"     − {b['sym']:<10} ih={len(ih)} tvol={b['tvol']:,.0f} base={base30(ih):,.0f} "
                  f"ratio={b['tvol']/base30(ih) if base30(ih) else float('nan'):.2f} tno={b['tno']:,.0f} "
                  f"| ما: vol_ratio_file={ours[i].get('vol_ratio_file')} tno={ours[i].get('z_tot_tran')}")
        for i in list(our - gt)[:5]:
            b, ih = board[i], hist[i]
            print(f"     + {b['sym']:<10} ih={len(ih)} tvol={b['tvol']:,.0f} base={base30(ih):,.0f} "
                  f"low29={low29(ih)} | ما: vol_ratio_file={ours[i].get('vol_ratio_file')} "
                  f"hist_sessions={ours[i].get('hist_sessions')} min_low_29={ours[i].get('min_low_29')}")

    json.dump({"roobi_gt": sorted(gt_roobi), "sample": sample,
               "hist_lens": {i: len(v) for i, v in hist.items()}},
              open("_audit/tse_groundtruth_sets.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\nنمونە و شمارش‌ها در _audit/tse_groundtruth_sets.json — {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
