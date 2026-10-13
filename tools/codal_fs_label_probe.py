# -*- coding: utf-8 -*-
"""چرا خطِ «سود ناخالص» خوانده نمی‌شود؟ — برچسب‌به‌برچسبِ همان شیتِ انتخابی.

سناریو: نمادهایی که حاشیۀ سودشان `None` است، در حالی که خروجیِ Excelِ **همان**
برگه (excel.codal.ir/…/GetAll) سطری به نام «سود (زیان) ناخالص» با عددِ غیرصفر
دارد. یعنی یا (الف) شیتِ انتخابیِ `scrape_report` آن سطر را ندارد، یا (ب) دارد و
قالبِ `PATTERNS["gross_profit"]` نمی‌گیرد، یا (پ) گرفته و `num()` صفر/None
کرده، یا (ت) نگهبانِ رتبه (`rank`) آن را دور ریخته. این ابزار هر چهار را جدا
چاپ می‌کند تا علت **دیده** شود، نه حدس زده.

usage: PYTHONIOENCODING=utf-8 python tools/codal_fs_label_probe.py <tracing_no> [...]
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import codal_fetcher as CF          # noqa: E402

KEYS = ("revenue", "gross_profit", "operating_profit", "net_profit", "basic_eps")


def probe(conn, tn):
    row = conn.execute("SELECT url, title, symbol, revenue, gross_profit FROM "
                       "financial_statements WHERE tracing_no=?", (tn,)).fetchone()
    if not row or not row[0]:
        print("tn=%s: ردیف یا url ندارد" % tn)
        return None
    url, title, sym, db_rev, db_gp = row
    print("tn=%s  %s" % (tn, sym))
    print("   title=%s" % str(title)[:96])
    print("   DB   : revenue=%s  gross_profit=%s" % (db_rev, db_gp))
    s = CF.requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (BorsTerminal probe)"})
    r = CF._resilient_get(s, url)
    if r is None:
        print("   BLOCKED: صفحه باز نشد")
        return None
    opts = CF._sheet_options(r.text)
    inc, cons, _bal = CF._pick_sheets(opts)
    print("   picked: income=%s (consol=%s) balance=%s" % (inc, cons, _bal))
    for sid_, name in opts:
        print("   sheet option: id=%s name=%r" % (sid_, str(name)[:60]))
    out, meta, unit = {}, {}, None
    rank = {}
    for role, sid_ in (("income", inc), ("balance", _bal)):
        if sid_ is None:
            continue
        sr = CF._resilient_get(s, "%s&sheetId=%s" % (url, sid_))
        ds = CF.datasource(sr.text) if sr is not None else None
        if not ds:
            print("   %s: datasource ندارد" % role)
            continue
        shs = ds.get("sheets") or []
        print("   %s: sheets=%d" % (role, len(shs)))
        for si, sheet in enumerate(shs):
            for ti, tbl in enumerate(sheet.get("tables", [])):
                grid = {}
                for c in tbl.get("cells", []):
                    grid.setdefault(c.get("rowSequence"), {})[c.get("columnSequence")] = c.get("value")
                for rr in sorted(k for k in grid if k is not None):
                    lab = CF.norm(grid[rr].get(1))
                    if not lab:
                        continue
                    hits = [k for k in KEYS for p in CF.PATTERNS[k] if re.search(p, lab)]
                    if not hits:
                        continue
                    vals = [(ci, CF.num(grid[rr].get(ci)))
                            for ci in sorted(k for k in grid[rr] if k)]
                    print("   [%s s%d t%d] %-40s keys=%s vals=%s" % (role, si, ti, lab[:40], hits,
                          [(ci, v) for ci, v in vals[:4]]))
                # ردیف‌هایِ برچسب‌دارِ بی‌hit، مخصوصِ واژۀ «ناخالص» — تا کوریِ
                # قالبِ PATTERNS از «نبودِ سطرِ واقعی» جدا بماند
                for rr in sorted(k for k in grid if k is not None):
                    lab = CF.norm(grid[rr].get(1))
                    if lab and "ناخالص" in lab and not any(
                            re.search(p, lab) for p in CF.PATTERNS["gross_profit"]):
                        print("   [%s s%d t%d] UNMATCHED-ناخالص: %r vals=%s"
                              % (role, si, ti, lab[:56],
                                 [(ci, CF.num(grid[rr].get(ci)))
                                  for ci in sorted(k for k in grid[rr] if k)][:4]))
        before = dict(out)
        CF.parse_tables(ds, out, rank)
        print("   after parse_tables(%s): %s" % (role, {k: out.get(k) for k in KEYS}))
        print("   new-dropped: %s" % {k: before.get(k) for k in KEYS
                                      if before.get(k) is not None and out.get(k) is None})
    print("   final: %s | unit=%s" % ({k: out.get(k) for k in KEYS}, str(unit)[:44]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tn", nargs="+", type=int)
    ap.add_argument("--db", default="market.db")
    a = ap.parse_args()
    conn = sqlite3.connect("file:%s?mode=ro" % os.path.abspath(a.db).replace("\\", "/"), uri=True)
    for tn in a.tn:
        probe(conn, tn)
        print("")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
