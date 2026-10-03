# -*- coding: utf-8 -*-
"""_audit/live_filter_triage3.py — parityِ زنده رویِ نسخۀ **نصب‌شدۀ** کاربر

چرا این نسخه: اجرایِ دوم (triage2) رویِ `127.0.0.1:8001` سه چیز نشان داد که
باید قبلِ داوری درست خوانده شوند:

  • «خام» ۵٬۶۴۲ ردیف ناهمخوان زد، ولی همه‌شان رویِ یک کلید بودند: `d_even`.
    آن کلید درِ `_DROP_FIELDS` است (رویِ سیم فرستاده نمی‌شود) و `?fields=all`
    درِ این نسخه نیست ⇒ کلید درِ بدنه غایب است، نه اینکه عدد عوض شده باشد.
    پس مقایسه فقط رویِ کلیدهایی انجام می‌شود که واقعاً درِ بدنه‌اند، و کلیدهایِ
    غایب جداگانه اعلام می‌شوند.
  • «فرمول» ۶۴ ناهمخوانی زد، چون متنِ فایل بی‌درِ «همین نشست» اجرا شد؛ محصول
    هر پنج پرچم را `& _alive` می‌کند (tape_flags.py:283-287). اینجا درِ زنده
    مثلِ محصول گذاشته می‌شود تا باقی‌مانده‌ها واقعی باشند.
  • شمارِ زندهٔ سایت/برنامه درِ اجرایِ دوم برایِ چهار فیلتر برابر بود ⇒ همین
    حالا تکرار می‌شود و نمادهایِ اختلاف‌دار با مقادیرِ هر دو طرف چاپ می‌شوند.

فقط می‌خواند: بانک با `mode=ro` و API با GET. هیچ نوشتنی ندارد.
"""
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests                        # noqa: E402
import tools.tse_live_filter_parity as P  # noqa: E402

APP = os.environ.get("TRIAGE_APP", "http://127.0.0.1:8001")
DB = os.environ.get("TRIAGE_DB", "market.db")
RAW = ("p_last", "p_closing", "q_tot_tran", "z_tot_tran", "allowed_min",
       "buy_q1_vol", "buy_q1_cnt")
API_KEY = {"allowed_min": "tmin"}
FLAG = {"clock": "f_clock", "susp": "f_susp", "jet": "f_jet",
        "roobi": "f_roobi", "noqteh": "f_noqteh"}


def vals(d, code):
    """مقدارِ ستونِ خام از ردیفِ بانک، با نامِ رویِ سیم."""
    return d.get(API_KEY.get(code, code))


def main():
    t0 = time.time()
    body = requests.get(APP + "/api/market", timeout=180).json()
    app = {r["ins_code"]: r for r in body["data"]}
    t_api = time.time()
    c = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    db = {r["ins_code"]: dict(r) for r in c.execute("SELECT * FROM market_watch")}
    # client_type جدا از market_watch است (jt درِ کوئریِ تابلو) — بی‌این پیوند،
    # `bp`/`sp` تهی می‌ماندند و eval_jet برایِ *همه* ردیف‌ها False می‌شد، یعنی
    # سنجشِ «جت» صفرِ جعلی می‌داد (همه‌چیز با همه‌چیز می‌سوخت).
    ct = {r["ins_code"]: dict(r) for r in c.execute("SELECT * FROM client_type")}
    newest = c.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
    c.close()
    hist, hn, hsrc, hrows = P.load_hist(None, DB)
    print(f"[now] API {len(app)} ردیف در {t_api - t0:.2f}s (rev={body.get('rev')})، "
          f"بانک {len(db)} ردیف، تاریخچۀ {hsrc} ({hrows:,} سطر، newest={newest})")

    # ── A) خام: فقط کلیدهایی که رویِ سیم هست ───────────────────────────
    present = [k for k in RAW if any(k in r or API_KEY.get(k) in r for r in app.values())]
    absent = [k for k in RAW if k not in present]
    raw_bad = {}
    for code, d in db.items():
        r = app.get(code)
        if not r:
            continue
        for col in present:
            wire = API_KEY.get(col, col)
            av, dv = r.get(wire), d.get(col)
            if av is None and dv in (None, 0):
                continue
            if (av or 0) != (dv or 0):
                raw_bad.setdefault(code, []).append((col, av, dv))
    print(f"\nA) خامِ API == market_watch رویِ {len(present)} کلیدِ رویِ سیم: "
          f"{len(raw_bad)} نمادِ ناهمخوان از {len(db)}")
    print(f"   کلیدهایِ بیرونِ بدنه (حذفِ عمدی از payload، سنجیده نشدند): {absent}")
    for code, items in list(raw_bad.items())[:10]:
        print("   ", (app.get(code) or {}).get("symbol"), items[:4])

    # ── B) فرمولِ فایل با درِ «همین نشست»، مثلِ محصول ──────────────────
    rows = []
    for code, d in db.items():
        # plp عینِ تعریفِ محصول درِ مسیرِ خواندن (api/market.py:841):
        # «آخرین نسبت به دیروز» — نه price_change، که قیمتِ پایانی را نسبت به
        # دیروز می‌سنجد و برایِ حق‌تقدم‌هایِ بی‌معامله صفر می‌ماند.
        py, pl_ = d.get("price_yesterday"), d.get("p_last")
        plp = (round(100.0 * (pl_ - py) / py, 2)
               if (py and pl_ is not None) else None)
        k = ct.get(code, {})
        rows.append({"code": code, "ih": hist.get(code) or [], "pl": d.get("p_last"),
                     "pc": d.get("p_closing"), "py": py, "tmin": d.get("allowed_min"),
                     "tmax": d.get("allowed_max"), "tvol": d.get("q_tot_tran"),
                     "tno": d.get("z_tot_tran"), "zd1": d.get("buy_q1_cnt"),
                     "qd1": d.get("buy_q1_vol"),
                     "bp": (k.get("buy_i_vol"), k.get("buy_count_i")),
                     "sp": (k.get("sell_i_vol"), k.get("sell_count_i")),
                     "plp": plp,
                     "live": d.get("d_even") == newest})
    bad = {}
    for v in rows:
        r = app.get(v["code"])
        if not r:
            continue
        for name, fn in P.CHECKS:
            want = bool(fn(v)) and v["live"]          # درِ زنده، مثلِ _alive
            got = bool(r.get(FLAG[name]))
            if want != got:
                bad.setdefault(name, []).append((v["code"], want, got))
    cov = {"ct": sum(1 for v in rows if v["bp"][1] and v["sp"][1]),
           "ih30": sum(1 for v in rows if len(v["ih"]) >= 30)}
    print(f"\nB) پنج متنِ فایل + درِ «همین نشست» رویِ ردیفِ بانک == پرچمِ API? "
          f"ناهمخوانی={sum(len(x) for x in bad.values())} "
          f"(پوشش: {cov['ct']} ردیف ctِ کامل برایِ جت، {cov['ih30']} ردیف با ۳۰ نشستِ تاریخچه، "
          f"{len(rows)} ردیفِ کل)")
    for name, items in bad.items():
        syms = [((app.get(k) or {}).get("symbol"), w, g) for k, w, g in items[:8]]
        print(f"   {name}: {len(items)} → {syms}")

    # ── C) شمارِ زندهٔ سایت در برابرِ برنامه، با نمادها ─────────────────
    mw, _ = P.get(P.MW_URL, "marketwatch")
    ct_rows, _ = P.get(P.CT_URL, "clientTypeAllDto")
    ct = {r.get("insCode"): r for r in (ct_rows or [])}
    t_site = time.time()
    site = {n: {} for n in FLAG}
    for m in (mw or []):
        v = P.site_row(m, hist, ct)
        for name, fn in P.CHECKS:
            if fn(v):
                site[name][v["code"]] = v
    print(f"\nC) شمارِ زنده (فاصلۀ بدنۀ API تا نمونهٔ سایت: {t_site - t_api:.1f}s)")
    out = {"raw_mismatch": len(raw_bad), "raw_absent_keys": absent,
           "formula_mismatch": {k: len(v) for k, v in bad.items()}, "counts": {}}
    for name in FLAG:
        s = set(site[name])
        a = {k for k, r in app.items() if r.get(FLAG[name])}
        only_s = sorted(s - a)
        only_a = sorted(a - s)
        print(f"   {name:7s} site={len(s):4d} app={len(a):4d} مشترک={len(s & a):4d} "
              f"فقط‌سایت={len(only_s)} فقط‌برنامه={len(only_a)}")
        for k in only_s[:6]:
            m = next((x for x in (mw or []) if x.get("insCode") == k), {})
            v = site[name][k]
            print(f"      • {(m.get('lVal18') or '?'):10s} سایت pl={v['pl']} "
                  f"pc={v['pc']} tvol={v['tvol']} tno={v['tno']} "
                  f"| برنامه " +
                  " ".join(f"{c}={(app.get(k) or {}).get(c)}"
                           for c in ("p_last", "p_closing", "q_tot_tran", "z_tot_tran")))
        for k in only_a[:6]:
            r = app.get(k) or {}
            v = next((x for x in rows if x["code"] == k), {})
            print(f"      • {(r.get('symbol') or '?'):10s} برنامه pl={r.get('p_last')} "
                  f"pc={r.get('p_closing')} tvol={r.get('q_tot_tran')} "
                  f"tno={r.get('z_tot_tran')} | بانک tno={v.get('tno')} "
                  f"zd1={v.get('zd1')} qd1={v.get('qd1')} live={v.get('live')}")
        out["counts"][name] = {"site": len(s), "app": len(a),
                               "only_site": only_s, "only_app": only_a}
    out["api_rev"] = body.get("rev")
    out["api_seconds_before_site"] = round(t_site - t_api, 2)
    json.dump(out, open(os.path.join("_audit", "live_filter_triage3.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nwrote _audit/live_filter_triage3.json")


if __name__ == "__main__":
    main()
