#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32F: the formula audit classifies steps and official coverage.

Synthetic, no network:
  * exact / near / far / missing product steps land in the right buckets;
  * a nearest official PA/SH row within ±7 days counts as a hit, and only an
    agreeing ratio counts as agreement;
  * a fund portal row is compared with both the product and the reference;
  * input file hashes are recorded in the output.
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "ra365_round32f_formula_audit.py")

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   <- %s" % (detail,)) if detail else ""))


def write_json(path, doc):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)


def main():
    root = tempfile.mkdtemp(prefix="r32f_audit_")
    pack = os.path.join(root, "factors.jsonl")
    ratio_a = 1.0 / 1.07
    rows = [
        {"action": "replace_step", "ins_code": "A", "symbol": "TESTA",
         "effective_date": "2020-01-10", "ratio": ratio_a,
         "prod_ratio": ratio_a, "event_sig": "dps"},
        {"action": "replace_step", "ins_code": "B", "symbol": "TESTB",
         "effective_date": "2021-03-01", "ratio": 0.4,
         "prod_ratio": 0.40000001, "event_sig": "share"},
        {"action": "replace_step", "ins_code": "C", "symbol": "TESTC",
         "effective_date": "2022-05-01", "ratio": 0.9,
         "prod_ratio": 0.95, "event_sig": "base_gap"},
        {"action": "replace_step", "ins_code": "D", "symbol": "TESTD",
         "effective_date": "2023-06-01", "ratio": 0.98,
         "prod_ratio": None, "event_sig": "no_event"},
        {"action": "replace_step", "ins_code": "E", "symbol": "TESTE",
         "effective_date": "2024-07-01", "ratio": 1.0 / 1.03,
         "prod_ratio": 0.97, "event_sig": "fund_dps"},
        {"action": "suppress_step", "ins_code": "A", "symbol": "TESTA",
         "effective_date": "2020-02-01", "ratio": None,
         "prod_ratio": 0.5, "event_sig": "dps"},
    ]
    with open(pack, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    off = os.path.join(root, "official")
    os.makedirs(off)
    write_json(os.path.join(off, "pa_flow1.json"), {"priceAdjust": [
        {"dEven": 20200112, "pClosing": 100.0, "pClosingNotAdjusted": 107.0,
         "instrument": {"insCode": "A", "lVal18AFC": "TESTA"}},
        {"dEven": 20220501, "pClosing": 90.0, "pClosingNotAdjusted": 100.0,
         "instrument": {"insCode": "C", "lVal18AFC": "TESTC"}},
    ]})
    write_json(os.path.join(off, "pa_flow2.json"), {"priceAdjust": []})
    write_json(os.path.join(off, "sh_flow1.json"), {"instrumentShareChange": [
        {"dEven": 20210228, "insCode": "B", "lVal18AFC": "TESTB",
         "numberOfShareOld": 200.0, "numberOfShareNew": 500.0},
    ]})
    write_json(os.path.join(off, "sh_flow2.json"), {"instrumentShareChange": []})

    fund_db = os.path.join(root, "fund.db")
    con = sqlite3.connect(fund_db)
    con.execute("CREATE TABLE fund_profit_events("
                "ins_code TEXT, d_even INTEGER, unit_profit REAL,"
                " reference_price REAL, ratio REAL, source TEXT)")
    con.execute("INSERT INTO fund_profit_events VALUES (?,?,?,?,?,?)",
                ("E", 20240701, 300.0, 10000.0, 0.97, "test-portal"))
    con.commit()
    con.close()

    out = os.path.join(root, "audit.json")
    proc = subprocess.run(
        [sys.executable, TOOL, "--pack", pack, "--official-dir", off,
         "--fund-db", fund_db, "--out", out],
        capture_output=True, text=True, encoding="utf-8")
    ck(proc.returncode == 0, "tool exits 0", proc.stderr[-400:])
    doc = json.load(open(out, encoding="utf-8")) if os.path.exists(out) else {}
    ck(doc.get("schema") == "ra365-round32f-formula-audit-v1", "schema tag")

    totals = doc.get("totals") or {}
    ck(totals.get("n") == 5, "five replace steps counted", totals)
    ck(totals.get("exact") == 1, "one exact step", totals)
    ck(totals.get("le1e-6") == 1, "one near step", totals)
    ck(totals.get("gt1e-4") == 2, "two far steps", totals)
    ck(totals.get("no_prod") == 1, "one missing product step", totals)
    ck(totals.get("pa_hit") == 2, "two PA hits within tolerance", totals)
    ck(totals.get("sh_hit") == 1, "one SH hit within tolerance", totals)
    ck(totals.get("no_official") == 2, "two steps without official rows", totals)
    ck(totals.get("pa_agree") == 2, "both PA hits agree with the reference", totals)
    ck(totals.get("sh_agree") == 1, "the SH hit agrees with the reference", totals)

    fam = doc.get("families") or {}
    ck(fam.get("dps", {}).get("exact") == 1, "dps bucket", fam.get("dps"))
    ck(fam.get("share", {}).get("le1e-6") == 1, "share bucket", fam.get("share"))
    ck(fam.get("base_gap", {}).get("gt1e-4") == 1, "base_gap bucket", fam.get("base_gap"))
    ck(fam.get("no_event", {}).get("no_prod") == 1, "no_event bucket", fam.get("no_event"))
    ck(fam.get("fund_dps", {}).get("fund_hit") == 1, "fund step matched", fam.get("fund_dps"))

    fc = doc.get("fund_comparison") or {}
    ck(fc.get("fund_steps_with_official") == 1, "one official fund step", fc)
    ck(fc.get("official_vs_product_agree") == 1, "official agrees with product", fc)
    ck(fc.get("official_vs_reference_agree", 0) == 0,
       "official disagrees with the reference (convention)", fc)

    meta = doc.get("official") or {}
    ck(meta.get("pa", {}).get("rows") == 2, "PA row count", meta.get("pa"))
    ck(meta.get("sh", {}).get("rows") == 1, "SH row count", meta.get("sh"))
    ck((doc.get("fund_db") or {}).get("rows") == 1, "fund row count",
       doc.get("fund_db"))
    sha = (doc.get("pack") or {}).get("sha256") or ""
    ck(len(sha) == 64 and all(c in "0123456789abcdef" for c in sha),
       "pack hash recorded", sha)

    print("\n%d passed, %d failed" % (P, F))
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
