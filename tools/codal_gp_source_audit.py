# -*- coding: utf-8 -*-
"""حاشیۀ سودِ این نمادها در **منبع** کجا هست؟ — هر برگۀ منتشرشده ورق می‌خورد.

سنجشِ «بی‌داده» بدونِ دیدنِ منبع، حدس است. این ابزار برایِ هر نمادِ دارایِ
حاشیۀ رفته، تمامِ برگه‌هایِ «صورت سود و زیان» آن اطلاعیه را می‌خواند (مستقل و
تلفیقی، سالانۀ اصلی و میاندورۀ هم‌سال) و می‌گوید:

  * `gp_on_standalone`  — خطِ سودِ ناخالص درِ همان برگۀ مستقلِ **مصرفی** هست، ولی
    استخراجِ `scrape_report` آن را نگرفته ← **نقصِ استخراج، قابل‌رفعِ کد**
  * `gp_only_consolidated` — فقط درِ صورتِ **تلفیقی** همان اطلاعیه هست (مسیرِ
    واکشی عمداً برگۀ مستقل را برمی‌دارد، پس این عدد هرگز درِ بانک ننشسته)
  * `gp_nowhere` — درِ هیچ برگۀ این اطلاعیه خطِ «ناخالص» نیست ← **نبودِ واقعیِ داده**
  * `unreadable` — برچسبِ قابل‌خواندنِ سطرِ مستقل پیدا نشد (برگه‌ای با سه ستونِ
    تهی) ← دوره/چیدمانِ ردیف، نه عددِ گم‌شده

هر خطا درِ شبکه «UNVERIFIED» ثبت می‌شود، نه صفر. درخواست‌ها آهسته و با فاصله
می‌روند (سقفِ `_MAX_SHEETS` برایِ هر اطلاعیه).

usage: PYTHONIOENCODING=utf-8 python tools/codal_gp_source_audit.py \
        --symbols تابان,تيپيكو,اخشان
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import codal_fetcher as CF          # noqa: E402
import fts_engine as FE             # noqa: E402
import codal_periods as CP          # noqa: E402
import symbol_identity as SI        # noqa: E402

_MAX_SHEETS = 6
MAX_REPORTS = 1          # هر نماد فقط تازۀترین ردیفِ خودش — سقفِ درخواستِ این سنجش
_GROSS = re.compile(r"ناخالص")


def income_sheets(opts):
    out = []
    for sid, name in opts:
        n = CF.norm(name or "")
        if "سود" in (name or "") and "زیان" in (name or ""):
            out.append((sid, name, "consol" if "تلفیق" in n else "standalone"))
    return out[:_MAX_SHEETS]


def sheet_gross(s, url, sid):
    """(gp, rev, برچسب) از یک برگه — نخستین عددِ غیرصفرِ سطرِ «ناخالص» و «جمع درآمدها»."""
    r = CF._resilient_get(s, "%s&sheetId=%s" % (url, sid))
    if r is None:
        return None
    ds = CF.datasource(r.text)
    if not ds:
        return None
    gp = rev = None
    label = ""
    out, rank = {}, {}
    CF.parse_tables(ds, out, rank)
    gp = out.get("gross_profit")
    rev = out.get("revenue")
    for sheet in ds.get("sheets", []):
        for tbl in sheet.get("tables", []):
            grid = {}
            for c in tbl.get("cells", []):
                grid.setdefault(c.get("rowSequence"), {})[c.get("columnSequence")] = c.get("value")
            for rr in sorted(k for k in grid if k is not None):
                lab = CF.norm(grid[rr].get(1)) or ""
                if _GROSS.search(lab) and not label:
                    vals = [(ci, CF.num(grid[rr].get(ci)))
                            for ci in sorted(k for k in grid[rr] if k) if ci != 1]
                    nz = [v for _ci, v in vals if v not in (None, 0.0)]
                    label = "%s|%s" % (lab[:40], nz[:2])
    return {"gp": gp, "rev": rev, "gross_label": label,
            "op": out.get("operating_profit"), "np": out.get("net_profit")}


def audit(conn, sym):
    pred, params = FE.sym_in(conn, "symbol", sym)
    rows = conn.execute(
        "SELECT tracing_no, url, title, period_end, period_months, revenue, gross_profit "
        "FROM financial_statements WHERE " + pred + " AND url IS NOT NULL "
        "AND period_months >= 12 "
        "ORDER BY period_end DESC LIMIT 12", params).fetchall()
    s = CF.requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (BorsTerminal gp-audit)"})
    res = {"symbol": sym, "reports": []}
    rows = [r for r in rows if not FE.title_entity_suffix(str(r[2] or ""))][:MAX_REPORTS]
    for tn, url, title, pe, pm, rev, gp in rows:
        rec = {"tracing_no": tn, "period_end": CP.canonicalize(pe),
               "title": str(title or "")[:80], "db_gross_profit": gp, "db_revenue": rev,
               "sheets": [], "verdict": None}
        if gp is not None:
            rec["verdict"] = "already_has_gp"
            res["reports"].append(rec)
            continue
        if not url:
            rec["verdict"] = "no_url"
            res["reports"].append(rec)
            continue
        r = CF._resilient_get(s, url)
        if r is None:
            rec["verdict"] = "UNVERIFIED (صفحه باز نشد)"
            res["reports"].append(rec)
            continue
        opts = income_sheets(CF._sheet_options(r.text))
        any_gross = False
        standalone_gross = False
        for sid, name, basis in opts:
            d = sheet_gross(s, url, sid)
            time.sleep(2.0)
            if d is None:
                rec["sheets"].append({"sid": sid, "name": name[:30], "basis": basis,
                                      "error": "UNVERIFIED (datasource نبود)"})
                continue
            has = d["gp"] is not None or bool(d["gross_label"])
            any_gross = any_gross or has
            if basis == "standalone" and d["gp"] is not None:
                standalone_gross = True
            rec["sheets"].append({"sid": sid, "name": str(name)[:34], "basis": basis,
                                  "gp": d["gp"], "rev": d["rev"],
                                  "gross_label": d["gross_label"]})
        rec["sheets_seen"] = len(opts)
        if standalone_gross:
            rec["verdict"] = "gp_on_standalone"
        elif any_gross:
            rec["verdict"] = "gp_only_consolidated"
        elif any(x.get("gross_label") or x.get("gp") for x in rec["sheets"]):
            rec["verdict"] = "gp_only_consolidated"
        else:
            rec["verdict"] = "gp_nowhere" if opts else "no_income_sheet"
        res["reports"].append(rec)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--symbols", required=True, help="کاماسپش؛ از codal_margin_loss_diagnosis.json")
    ap.add_argument("--out", default="_audit/codal_gp_source_audit.json")
    a = ap.parse_args()
    conn = sqlite3.connect("file:%s?mode=ro" % os.path.abspath(a.db).replace("\\", "/"), uri=True)
    conn.row_factory = sqlite3.Row
    FE.register_sql(conn)
    res = []
    for sym in [x.strip() for x in a.symbols.split(",") if x.strip()]:
        r = audit(conn, sym)
        res.append(r)
        v = {}
        for rep in r["reports"]:
            v[rep["verdict"]] = v.get(rep["verdict"], 0) + 1
        print("%-11s %s" % (sym, v))
        for rep in r["reports"]:
            print("    tn=%s %s | %s | db.gp=%s" % (rep["tracing_no"], rep["period_end"],
                  rep["verdict"], rep["db_gross_profit"]))
            for sh in rep["sheets"]:
                print("       [%s] %-34s gp=%s rev=%s %s" % (sh.get("basis"), str(sh.get("name"))[:34],
                      sh.get("gp"), sh.get("rev"), str(sh.get("gross_label") or "")[:44]))
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    tally = {}
    for r in res:
        for rep in r["reports"]:
            tally[rep["verdict"]] = tally.get(rep["verdict"], 0) + 1
    print("تجمیعِ سطرها:", tally)
    print("out=%s" % a.out)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
