"""Live parity of the five tape filters against TSETMC's own feed.

Reference side ("site") = the site's raw payloads (GetMarketWatch +
GetClosingPriceDailyAllInst + GetClientTypeAll) evaluated with the owner's five
desktop filter texts, using the variable mapping the site's own ExecFilter uses
(documented in tape_flags.py). App side = /api/market flags of a running backend.

History source: --hist FILE (a dumped GetClosingPriceDailyAllInst) or --hist-db,
which reads tape_history -- the same endpoint's rows, cached by the app's own sync.

Usage: python tools/tse_live_filter_parity.py [--app URL] [--hist FILE|db] [--out FILE]
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime

import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://cdn.tsetmc.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://tsetmc.com/",
    "Origin": "https://tsetmc.com",
    "Accept": "application/json",
}
_PT = "&".join(f"paperTypes[{i}]={i+1}" for i in range(9))
MW_URL = f"{BASE}/ClosingPrice/GetMarketWatch?market=0&{_PT}&showTraded=false&withBestLimits=true&hEven=0"
HIST_URL = f"{BASE}/ClosingPrice/GetClosingPriceDailyAllInst"
CT_URL = f"{BASE}/ClientType/GetClientTypeAll"

JET_LADDER = (2, 5, 9, 19, 29, 39, 49, 59)
APP_FLAG = {"clock": "f_clock", "susp": "f_susp", "jet": "f_jet",
            "roobi": "f_roobi", "noqteh": "f_noqteh"}


def get(url, key, tries=3, timeout=180):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            j = r.json()
            rows = j.get(key) if isinstance(j, dict) else j
            if rows:
                return rows, None
            last = "empty"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:120]}"
        time.sleep(3)
    return None, last


def load_hist(path, db):
    """ins_code -> [ih] (descending by dEven, at most 60 sessions)."""
    if path:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        recs = [(r.get("insCode"), int(r.get("dEven") or 0),
                 float(r.get("priceMin") or 0.0), float(r.get("priceMax") or 0.0),
                 float(r.get("qTotTran5J") or 0.0)) for r in raw]
        src = f"file:{os.path.basename(path)}"
    else:
        conn = sqlite3.connect(db)
        recs = [(i, int(d), float(mn or 0), float(mx or 0), float(v or 0))
                for i, d, mn, mx, v in conn.execute(
                    "SELECT ins_code, d_even, price_min, price_max, q_tot_tran5j FROM tape_history")]
        src = f"db:{db}"
    by = {}
    for ins, d, mn, mx, vol in recs:
        if not ins or not d:
            continue
        by.setdefault(ins, []).append((d, mn, mx, vol))
    out = {}
    for ins, lst in by.items():
        lst.sort(key=lambda x: -x[0])
        out[ins] = lst[:60]
    newest = max((l[0][0] for l in out.values() if l), default=0)
    return out, newest, src, len(recs)


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def site_row(mw, hist, ct):
    """The ExecFilter variable set for one live board row."""
    code = mw.get("insCode")
    ih = hist.get(code) or []
    py, pcl, pdv = num(mw.get("py")), num(mw.get("pcl")), num(mw.get("pdv"))
    chg = num(mw.get("pc"))                       # absolute change of LAST price
    pl = pdv if pdv is not None else None
    plp = round(100.0 * chg / py, 2) if (chg is not None and py and py > 0) else None
    bld = mw.get("blDs") or []
    line = bld[0] if bld else {}
    c = ct.get(code) or {}
    return {
        "code": code, "tsa": mw.get("lva"), "ih": ih,
        "pl": pl, "pc": pcl, "py": py, "plp": plp,
        "tmin": num(mw.get("pMin")), "tmax": num(mw.get("pMax")),
        "tvol": num(mw.get("qtj")), "tno": num(mw.get("ztt")),
        "zd1": num(line.get("zmd")), "qd1": num(line.get("qmd")),
        "bp": (num(c.get("buy_I_Volume")), num(c.get("buy_CountI"))),
        "sp": (num(c.get("sell_I_Volume")), num(c.get("sell_CountI"))),
        "dEven": mw.get("dEven"), "hEven": mw.get("hEven"),
    }


def vol_base30(v):
    """Σ[ih][0..29].QTotTran5J / 30 -- the site raises for short history (row dropped)."""
    ih = v["ih"]
    if len(ih) < 30:
        return None
    return sum(r[3] for r in ih[:30]) / 30.0


def min_low29(v):
    """عینِ MinPriceOfMonth فایل نقطه‌زنی: کمینۀ [ih][0..28].PriceMin، صفر هم معتبر."""
    ih = v["ih"]
    if len(ih) < 29:
        return None
    m = ih[0][1]
    for n in range(1, 29):
        if m > ih[n][1]:
            m = ih[n][1]
    return m


def ladder_high(v):
    ih = v["ih"]
    if len(ih) < max(JET_LADDER) + 1:
        return None
    return max(ih[k][2] for k in JET_LADDER)


def eval_clock(v):
    base = vol_base30(v)
    if not base:
        return False
    return bool(v["pl"] is not None and v["pc"] and v["pc"] > 0
                and v["pl"] >= v["pc"] * 1.02 and (v["tvol"] or 0) > base
                and (v["tno"] or 0) > 30)


def eval_susp(v):
    base = vol_base30(v)
    if not base:
        return False
    return bool((v["tvol"] or 0) > 3 * base and (v["tno"] or 0) > 50)


def eval_jet(v):
    base = vol_base30(v)
    if not base or (v["tvol"] or 0) <= 3 * base:
        return False
    bv, bc = v["bp"]
    sv, sc = v["sp"]
    if not (bv and bc and sv is not None and sc):
        return False
    if (bv / bc) < 1.5 * (sv / sc):
        return False
    if not (v["pc"] and v["pc"] > 0 and v["pl"] is not None and v["pl"] >= v["pc"]):
        return False
    if not (v["plp"] is not None and v["plp"] > 0):
        return False
    if not ((v["tno"] or 0) > 100):
        return False
    res = ladder_high(v)
    if res is None or res <= 0:
        return False
    return bool(v["pl"] > res)


def eval_roobi(v):
    return bool(v["pl"] is not None and v["tmin"] and v["tmin"] > 0
                and v["pl"] == v["tmin"]
                and (v["zd1"] or 0) > 1
                and v["plp"] is not None and v["plp"] < -1
                and (v["qd1"] or 0) > 100)


def eval_noqteh(v):
    pc = v["pc"]
    if not (pc and pc > 0):
        return False
    m = min_low29(v)
    if m is None or m == 0:
        return False
    dist = round((pc - m) / pc * 100 * 100) / 100.0
    if not (dist < 3):
        return False
    base = vol_base30(v)
    return bool(base and (v["tvol"] or 0) > base and (v["tno"] or 0) > 5)


CHECKS = (("clock", eval_clock), ("susp", eval_susp), ("jet", eval_jet),
          ("roobi", eval_roobi), ("noqteh", eval_noqteh))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="http://127.0.0.1:8002")
    ap.add_argument("--hist", default="db", help="JSON dump path, or 'db' for tape_history")
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--out", default=os.path.join("_audit", "tse_live_filter_parity.json"))
    args = ap.parse_args()

    if args.hist == "db":
        hist, newest, hsrc, hrows = load_hist(None, args.db)
    else:
        hist, newest, hsrc, hrows = load_hist(args.hist, args.db)

    t0 = datetime.now()
    mw_rows, err = get(MW_URL, "marketwatch")
    if not mw_rows:
        sys.exit("market watch fetch failed: " + str(err))
    ct_rows, err = get(CT_URL, "clientTypeAllDto")
    ct = {r.get("insCode"): r for r in (ct_rows or [])}
    t_site = datetime.now()
    print(f"[site] history {hsrc}: {hrows:,} rows, {len(hist)} symbols, newest session {newest}")
    print(f"[site] market watch {len(mw_rows)} rows, clientType {len(ct)} @ {t_site:%H:%M:%S}")

    site = {k: set() for k, _ in CHECKS}
    traded = 0
    site_codes = {mw.get("insCode") for mw in mw_rows}
    for mw in mw_rows:
        v = site_row(mw, hist, ct)
        if (v["tvol"] or 0) > 0:
            traded += 1
        for name, fn in CHECKS:
            if fn(v):
                site[name].add(v["code"])

    r = requests.get(args.app + "/api/market", headers={"Accept": "application/json"}, timeout=180)
    r.raise_for_status()
    body = r.json()
    app_rows = body.get("data") or []
    app = {k: set() for k, _ in CHECKS}
    app_live = set()
    for row in app_rows:
        code = row.get("ins_code")
        if row.get("is_live") is not False:
            app_live.add(code)
        for name, _ in CHECKS:
            if row.get(APP_FLAG[name]):
                app[name].add(code)
    meta = body.get("meta") or {}
    print(f"[app ] {args.app} rows={len(app_rows)} live={body.get('live_count')} "
          f"traded>0={traded} last_sync={meta.get('last_sync')} h_even={meta.get('h_even')} "
          f"@ {datetime.now():%H:%M:%S}")

    report = {
        "site_instant": t_site.isoformat(timespec="seconds"),
        "app_meta": meta,
        "history_source": hsrc, "history_newest_session": newest,
        "site_traded_rows": traded,
        "site_counts": {k: len(v) for k, v in site.items()},
        "app_counts": {k: len(v) for k, v in app.items()},
        "diffs": {},
    }
    for name, _ in CHECKS:
        both = site[name] & app[name]
        only_site = sorted(site[name] - app[name])
        only_app = sorted(app[name] - site[name])
        # «فقطما» دو چیزِ متفاوت است: یا سایت همان ردیف را درِ پاسخِ خود دارد و
        # علامت نزده (اختلافِ واقعی)، یا آن ردیف درِ هیچ بازاری از پاسخِ سایت
        # نیست و هیچ فیلتری هم رویش اجرا نمی‌شود (اختلافِ پوششِ مرجع). دومی را
        # نمی‌توان «ما زیاد علامت زدیم» خواند.
        off_ref = sorted(c for c in only_app if c not in site_codes)
        report["diffs"][name] = {"both": len(both), "only_site": len(only_site),
                                 "only_app": len(only_app),
                                 "only_app_not_in_site_payload": len(off_ref),
                                 "only_app_codes": only_app[:80],
                                 "only_site_codes": only_site[:80],
                                 "only_app_off_reference_codes": off_ref[:80]}
        print(f"  {name:<7} site={len(site[name]):>4} app={len(app[name]):>4} "
              f"match={len(both):>4} only_site={len(only_site):>3} only_app={len(only_app):>3}"
              f" (بیرونِ پاسخِ سایت: {len(off_ref)})")

    # symbol labels for the mismatch rows, from the app's own rows
    label = {row.get("ins_code"): row.get("symbol") for row in app_rows}
    report["labels"] = label
    tsym = {v.get("insCode"): v.get("lva") for v in mw_rows}
    report["site_symbols"] = tsym
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False)
    print("wrote " + args.out)


if __name__ == "__main__":
    main()
