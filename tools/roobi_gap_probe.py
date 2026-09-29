"""شکافِ یک فیلتر: همان نماد را در یک لحظه از دو سو، قید‌به‌قید بخوان.

`tse_live_filter_parity.py` شمار را می‌دهد؛ این ابزار می‌گوید کدام قید جابه‌جا
شده — برایِ نمادهایِ only_site/only_app، در چند نمونۀِ پشت‌سرهم تا مکشِ
زمانیِ خودِ داده از «باگِ فرمول» جدا شود.

  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tools/roobi_gap_probe.py \
      --app http://127.0.0.1:8001 --db "<installed market.db>" \
      --from-json _audit/parity_live_X.json --out _audit/roobi_gap_X.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from tse_live_filter_parity import CT_URL, MW_URL, get, load_hist, site_row  # noqa: E402

# roobi، عینِ tape_flags.roobi_flag: pl==tmin && tmin>0 && pl>0 && zd1>1 && plp<-1 && qd1>100
ROOBI = (
    ("pl>0", lambda v: v["pl"] is not None and v["pl"] > 0),
    ("tmin>0", lambda v: v["tmin"] is not None and v["tmin"] > 0),
    ("pl==tmin", lambda v: v["pl"] is not None and v["tmin"] is not None and v["pl"] == v["tmin"]),
    ("zd1>1", lambda v: (v["zd1"] or 0) > 1),
    ("plp<-1", lambda v: v["plp"] is not None and v["plp"] < -1),
    ("qd1>100", lambda v: (v["qd1"] or 0) > 100),
)
APP_FIELDS = ("symbol", "p_last", "p_closing", "price_yesterday", "percent_last",
              "p_min", "tmin", "buy_q1_cnt", "buy_q1_vol", "is_live", "f_roobi",
              "d_even", "fetched_at")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="http://127.0.0.1:8001")
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--gap", type=int, default=20)
    ap.add_argument("--codes", default="")
    ap.add_argument("--from-json", default="")
    ap.add_argument("--check", default="roobi")
    args = ap.parse_args()

    codes = [c for c in args.codes.split(",") if c.strip()]
    if not codes and args.from_json:
        rep = json.load(open(args.from_json, encoding="utf-8"))
        d = rep["diffs"][args.check]
        codes = sorted(set(d["only_site_codes"] + d["only_app_codes"]))
    if not codes:
        sys.exit("no codes given")

    hist, newest, _src, _rows = load_hist(None, args.db)
    runs = []
    for i in range(args.samples):
        mw_rows, err = get(MW_URL, "marketwatch")
        if not mw_rows:
            print(f"[sample {i}] site fetch failed: {err}")
            continue
        ct = {r.get("insCode"): r
              for r in (get(CT_URL, "clientTypeAllDto")[0] or [])}
        t_site = datetime.now()
        body = requests.get(args.app + "/api/market", timeout=180).json()
        app_rows = {x.get("ins_code"): x for x in (body.get("data") or [])}
        by_code = {mw.get("insCode"): mw for mw in mw_rows}
        sample = {"site_instant": t_site.isoformat(timespec="seconds"),
                  "app_instant": datetime.now().isoformat(timespec="seconds"),
                  "app_meta": body.get("meta"), "rows": {}}
        print(f"[sample {i}] site@{sample['site_instant']} "
              f"app@{sample['app_instant']} hist_newest={newest}")
        for code in codes:
            mw = by_code.get(code)
            rec = {"in_site_payload": mw is not None}
            if mw is not None:
                v = site_row(mw, hist, ct)
                rec["site"] = {name: bool(fn(v)) for name, fn in ROOBI}
                rec["site"]["pass"] = all(rec["site"][n] for n, _ in ROOBI)
                rec["site_vals"] = {k: v[k] for k in ("pl", "pc", "py", "plp",
                                                      "tmin", "zd1", "qd1")}
                rec["site_raw"] = {k: mw.get(k) for k in
                                   ("lva", "pdv", "pcl", "py", "pc", "pMin", "pMax",
                                    "qtj", "ztt", "dEven", "hEven")}
                rec["site_bld1"] = (mw.get("blDs") or [{}])[0]
            a = app_rows.get(code) or {}
            rec["app"] = {k: a.get(k) for k in APP_FIELDS}
            rec["app_flag"] = bool(a.get("f_roobi"))
            sample["rows"][code] = rec
            s = rec.get("site") or {}
            sv = rec.get("site_vals") or {}
            bad = [n for n, _ in ROOBI if not s.get(n)]
            def pair(k_app):
                k_site = {"p_last": "pl", "tmin": "tmin", "buy_q1_cnt": "zd1",
                          "buy_q1_vol": "qd1", "percent_last": "plp"}[k_app]
                return f"{k_app} {sv.get(k_site)}/{a.get(k_app)}"
            print(f"  {(rec['app'].get('symbol') or code):<14} site={s.get('pass')} "
                  f"app={rec['app_flag']} site_fails={bad} | "
                  + " ".join(pair(k) for k in ("p_last", "tmin", "buy_q1_cnt",
                                               "buy_q1_vol", "percent_last"))
                  + f" | app_fetched={a.get('fetched_at')} bld1={rec.get('site_bld1')}")
        runs.append(sample)
        if i + 1 < args.samples:
            time.sleep(args.gap)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"codes": codes, "history_newest": newest, "runs": runs},
                  fh, ensure_ascii=False)
    print("wrote " + args.out)


if __name__ == "__main__":
    main()
