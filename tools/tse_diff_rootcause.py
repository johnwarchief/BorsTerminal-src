"""ریشه‌یابیِ موردیِ اختلاف‌هایِ باقی‌مانده (نامِ نماد + ورودی‌ها + خروجیِ دو سامانه).

برایِ هر نمادی که درِ `tools/tse_app_flag_parity.py` اختلاف داشته، هم ردیفِ اپ
(از همان بدنهٔ `/api/market`) و هم آرایۀِ `[ih]`/`[is]`/ردیفِ سایت کنارِ هم
می‌نشیند تا علت *خوانده* شود، نه حدس.
"""
import argparse
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIELDS = ("PClosing", "PDrCotVal", "ZTotTran", "QTotTran5J", "QTotCap",
          "PriceMin", "PriceMax", "PriceYesterday", "PriceFirst")


def parse_closing(txt):
    out, cur = {}, ""
    for row in txt.split(";"):
        if not row:
            continue
        c = row.split(",")
        if len(c) == 11:
            cur, slot, vals = c[0], int(float(c[1])), c[2:]
        elif len(c) == 10:
            slot, vals = int(float(c[0])), c[1:]
        else:
            continue
        out.setdefault(cur, {})[slot] = dict(zip(FIELDS, [float(v) for v in vals]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="_audit/market_copy_slots3.db")
    ap.add_argument("--parity", default="_audit/tse_app_flag_parity.json")
    ap.add_argument("--ref", default="_audit/tse_saved_filter_eval.json")
    a = ap.parse_args()

    import api._core as C
    import api.market as M
    C.DB_PATH = a.db
    M.get_db = C.get_db

    class R:
        headers = {}

    body = json.loads(M._build_market_response(R(), drop_unused=False,
                                              store_cache=False).body)
    rows = body.get("data") or body.get("rows") or []
    by_code = {str(r["ins_code"]): r for r in rows}
    by_sym = {str(r.get("symbol")): r for r in rows}
    par = json.load(io.open(a.parity, encoding="utf-8"))
    ref = json.load(io.open(a.ref, encoding="utf-8"))
    hist = parse_closing(io.open("_audit/tse_cache_ClosingPriceAll.txt",
                                 encoding="utf-8", errors="replace").read())
    from test_tsetmc import parse_inst_value
    inst = parse_inst_value(io.open("_audit/tse_cache_InstValue.txt",
                                    encoding="utf-8", errors="replace").read())

    def site_inputs(code):
        ih = hist.get(code) or {}
        v30 = [ih[k]["QTotTran5J"] for k in range(30) if k in ih]
        isv = inst.get(code) or {}
        return {"ih_len": len(ih), "n30": sum(1 for k in range(30) if k in ih),
                "sum0_29": sum(v30) if len(v30) == 30 else None,
                "is5": isv.get("5"), "is6": isv.get("6"),
                "zero_slots0_29": sum(1 for k in range(30) if k in ih
                                      and not ih[k]["QTotTran5J"]),
                "min0_28": min([ih[k]["PriceMin"] for k in range(29) if k in ih], default=None),
                "ladder_max0_59": max([ih[k]["PriceMax"] for k in range(60) if k in ih], default=None)}

    print("نقشۀ اپ بر حسبِ کد:", len(by_code))
    for f in par["filters"]:
        for side, key in (("only_app", "فقط‌اپ"), ("only_ref", "فقط‌سایت")):
            for code in f[side] or []:
                app = by_code.get(code) or {}
                st = site_inputs(code)
                print(f"\n### {f['filter']} {key}  code={code} sym={app.get('symbol') or code}")
                if not app:
                    print("   اپ: ردیفی درِ بدنۀ /api/market ندارد (نماد در تابلوی ما نیست)")
                    print("   سایت:", json.dumps({k: v for k, v in st.items() if k != "slots0_2"},
                                                 ensure_ascii=False))
                    continue
                keep = ("symbol", "name", "tvol", "z_tot_tran", "p_last", "p_closing",
                        "price_yesterday", "plp_raw", "percent_last", "tmin", "tmax",
                        "allowed_min", "allowed_max", "buy_q1_cnt", "buy_q1_vol",
                        "sell_q1_cnt", "is_live", "hist_sessions", "prior30_vol",
                        "min_low_29", "is5", "is6", "vol_ratio_file", "buyer_power_raw",
                        "h2_max", "h5_max", "h29_max", "h59_max", "d_even", "f_roobi",
                        "f_jet", "f_susp", "f_clock", "f_noqteh", "f_smart", "f_legal")
                print("   اپ :", json.dumps({k: app.get(k) for k in keep}, ensure_ascii=False)[:700])
                print("   سایت:", json.dumps({k: v for k, v in st.items() if k != "slots0_2"},
                                             ensure_ascii=False)[:300])
    print("\n=== ردیفِ سایت برایِ نمادهایِ گمشده از تابلو (با نامِ واقعی)")
    for code in (par["filters"][1]["only_ref"] or []):
        r = by_sym.get(code)
        print("  ", code, "->", "در تابلو نیست" if not r else r.get("symbol"))


if __name__ == "__main__":
    main()
