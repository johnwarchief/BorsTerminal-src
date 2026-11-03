# -*- coding: utf-8 -*-
"""Ingest official monthly fund distributions into `fund_profit_events`.

Source: the fund manager's Rayan Ham Afza portal (`/api/v1/public/fundProfits/<id>`).
The portal gives `profitDate` (Jalali) and `unitProfit` (rials per unit).  The
effective date is the first trading session **after** that date; the reference
price is the LAST of the session immediately before it, so the engine's
cash-dividend formula is `(P - D) / P`.

Idempotent: rows are keyed by (ins_code, d_even) and replaced in place.
Never writes the operational DB unless it is explicitly passed as --db.
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import sys

import requests
import urllib3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from ra_parity import j2g  # noqa: E402  (single project Jalali conversion)


def _fetch_json(url, referer=None):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    if referer:
        headers["Referer"] = referer
    try:
        r = requests.get(url, headers=headers, timeout=45)
    except requests.exceptions.SSLError:
        urllib3.disable_warnings()
        r = requests.get(url, headers=headers, timeout=45, verify=False)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise ValueError("portal did not return a list")
    return data


def _fetch_csv(url, cache_path):
    if cache_path and os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        return open(cache_path, encoding="utf-8", errors="replace").read()
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=90)
    r.raise_for_status()
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(r.text)
    return r.text


def _date_of_profit(profit_date):
    try:
        jy, jm, jd = (int(x) for x in str(profit_date).split("/"))
    except Exception:
        return None
    return j2g(jy, jm, jd)


_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _num_fa(s):
    s = str(s or "").translate(_FA_DIGITS).replace(",", "").replace("٬", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _fetch_legacy(fund):
    """Legacy ASP.NET `FundDividendProfitReport`: 10 rows/page, Persian digits."""
    base = fund["portal"].rstrip("/") + fund.get("report_path", "/Reports/FundDividendProfitReport")
    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0"})
    urllib3.disable_warnings()
    first = sess.get(base, timeout=45, verify=False)
    first.raise_for_status()
    t = first.text
    pages = {1}
    for m in re.finditer(r"[?&]page=(\d+)", t):
        pages.add(int(m.group(1)))
    qs = ""
    m = re.search(r"[?&](FromDate=[^&\"']+&ToDate=[^&\"']+)", t)
    if m:
        qs = "?" + m.group(1)
    rows, seen = [], set()
    for page in sorted(pages):
        url = base + (qs + "&" if qs else "?") + f"page={page}"
        html = first.text if page == 1 else sess.get(url, timeout=45, verify=False).text
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(cells) < 6:
                continue
            pdate = cells[1].translate(_FA_DIGITS)
            if not re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", pdate):
                continue
            unit = _num_fa(cells[3])
            if unit is None:
                continue
            key = (pdate, unit)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"profitDate": pdate, "unitProfit": unit,
                         "extraProfit": 0, "units": _num_fa(cells[2]),
                         "total": _num_fa(cells[4])})
    return rows


def _rows_for_instrument(conn, symbol):
    return conn.execute(
        "SELECT ins_code, l_val18 FROM instruments WHERE l_val18=? "
        "ORDER BY updated_at DESC", (symbol,)).fetchall()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="target DB (use a copy, never the operational DB)")
    ap.add_argument("--sources", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache-dir", default="")
    a = ap.parse_args()

    import sqlite3
    import tsetmc_p0_schema as P0
    import api.chart as CH
    CH.DB_PATH = a.db

    sources = json.load(open(a.sources, encoding="utf-8"))
    con = sqlite3.connect(a.db, timeout=60)
    P0.create_all(con)
    # ensure the table exists even on an old bank
    con.execute(P0.FUND_PROFIT_EVENTS)
    con.commit()

    fetched_at = dt.datetime.now().isoformat(timespec="seconds")
    audit, summaries = [], []
    for fund in sources.get("funds", []):
        api = fund.get("endpoint") or fund.get("portal")
        if fund.get("no_distributions"):
            summaries.append({"symbol": fund.get("symbol"), "profits": 0,
                              "inserted_events": 0, "endpoint": api,
                              "note": "official portal reports no periodic distributions"})
            continue
        try:
            profits = (_fetch_legacy(fund) if fund.get("legacy")
                       else _fetch_json(api, fund.get("portal")))
        except Exception as e:
            summaries.append({"symbol": fund.get("symbol"), "error": f"{type(e).__name__}: {e}"})
            continue
        kept = 0
        symbols = fund.get("symbols") or [fund.get("symbol")]
        primary = symbols[0]
        symbol_ins = {}
        for symbol in symbols:
            r = con.execute(
                "SELECT ins_code FROM instruments WHERE l_val18=? ORDER BY updated_at DESC LIMIT 1",
                (symbol,)).fetchone()
            if r:
                symbol_ins[symbol] = str(r[0])
        if primary not in symbol_ins:
            audit.append({"fund": fund.get("symbol"), "symbol": primary,
                          "status": "INSTRUMENT_NOT_FOUND"})
            continue
        # idempotent: این صندوق از نو نوشته می‌شود، نه انبارِ ردیف‌هایِ دورِ قبل.
        for ins in symbol_ins.values():
            con.execute("DELETE FROM fund_profit_events WHERE ins_code=?", (ins,))
        ins_code = symbol_ins[primary]
        csv_url = ("https://cdn.tsetmc.com/api/ClosingPrice/"
                   f"GetClosingPriceDailyListCSV/{ins_code}/19900101")
        cache_path = (os.path.join(a.cache_dir, f"{ins_code}.csv")
                      if a.cache_dir else "")
        try:
            candles, _vols, _rows = CH._parse_tsetmc_csv(_fetch_csv(csv_url, cache_path))
        except Exception as e:
            audit.append({"fund": fund.get("symbol"), "symbol": primary, "ins_code": ins_code,
                          "status": "PRICE_CSV_FAILED", "error": f"{type(e).__name__}: {e}"})
            continue
        price = {}
        for c in candles:
            t = str(c.get("time"))[:10]
            p = c.get("last") or c.get("close")
            if t and p:
                price[t] = float(p)
        dates = sorted(price)
        pending = {}
        for rec in profits:
            pdate = rec.get("profitDate")
            d = _date_of_profit(pdate)
            row = {"fund": fund.get("symbol"), "symbol": primary, "ins_code": ins_code,
                   "profit_date": pdate, "unit_profit": rec.get("unitProfit"),
                   "extra_profit": rec.get("extraProfit"), "source": fund.get("source"),
                   "source_id": f"{fund.get('fund_id')}:{pdate}"}
            if d is None:
                row["status"] = "INVALID_PROFIT_DATE"
                audit.append(row)
                continue
            after = [t for t in dates if t > d.isoformat()]
            if not after:
                row["status"] = "NO_TRADING_DAY_AFTER_PROFIT"
                audit.append(row)
                continue
            event_date = after[0]
            before = [t for t in dates if t < event_date]
            if not before:
                row["status"] = "NO_REFERENCE_PRICE"
                audit.append(row)
                continue
            ref_date = before[-1]
            ref_price = price[ref_date]
            dps = float(rec.get("unitProfit") or 0) + float(rec.get("extraProfit") or 0)
            row.update({"event_date": event_date, "reference_date": ref_date,
                        "reference_price": ref_price, "dividend_per_share": dps})
            if dps <= 0:
                row["status"] = "ZERO_OR_NEGATIVE_DISTRIBUTION"
                audit.append(row)
                continue
            if dps >= ref_price:
                row["status"] = "DIVIDEND_GE_REFERENCE"
                audit.append(row)
                continue
            row["ratio"] = (ref_price - dps) / ref_price
            row["status"] = "RESOLVED_OFFICIAL_SOURCE"
            # چند ماهِ بی‌معامله ممکن است به یک سشنِ بازگشایی برسند؛ جمعِ
            # توزیع‌هایِ همان سشن اقتصادی درست است، نه حذفِ دومی.
            if event_date in pending:
                p0 = pending[event_date]
                p0["dividend_per_share"] += dps
                p0["profit_date"] += "," + pdate
                p0["source_id"] += "," + row["source_id"]
                p0["ratio"] = (p0["reference_price"] - p0["dividend_per_share"]) / p0["reference_price"]
                p0["status"] = "RESOLVED_OFFICIAL_SOURCE:MERGED_SAME_SESSION"
                row["status"] = "MERGED_INTO_SAME_SESSION"
                audit.append(row)
                continue
            pending[event_date] = row
            audit.append(row)
        inserted = []
        for event_date, row in sorted(pending.items()):
            dps = row["dividend_per_share"]
            ref_price = row["reference_price"]
            if dps >= ref_price:
                row["status"] = "DIVIDEND_GE_REFERENCE"
                continue
            ratio = (ref_price - dps) / ref_price
            row["ratio"] = ratio
            d_even = int(event_date.replace("-", ""))
            con.execute(
                "INSERT OR REPLACE INTO fund_profit_events"
                "(ins_code,d_even,symbol,profit_date,unit_profit,reference_price,ratio,"
                "source,source_id,fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ins_code, d_even, primary, row["profit_date"], dps, ref_price, ratio,
                 fund.get("source") or "fund-portal", row["source_id"], fetched_at))
            inserted.append(row)
            kept += 1
        # رویدادِ رسمی متعلق به خودِ صندوق است؛ رویِ همهٔ نمادهایِ variant همان
        # صندوق (با سریِ قیمتِ ۱ ریالی یا ناقص) کپی می‌شود.
        for symbol in symbols[1:]:
            if symbol not in symbol_ins:
                audit.append({"fund": fund.get("symbol"), "symbol": symbol,
                              "status": "INSTRUMENT_NOT_FOUND"})
                continue
            for b in inserted:
                d_even = int(b["event_date"].replace("-", ""))
                sid = f"{b['source_id']}:copied-from:{ins_code}"
                con.execute(
                    "INSERT OR REPLACE INTO fund_profit_events"
                    "(ins_code,d_even,symbol,profit_date,unit_profit,reference_price,ratio,"
                    "source,source_id,fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (symbol_ins[symbol], d_even, symbol, b["profit_date"],
                     b["dividend_per_share"], b["reference_price"], b["ratio"],
                     b["source"] or "fund-portal", sid, fetched_at))
                audit.append(dict(b, symbol=symbol, ins_code=symbol_ins[symbol],
                                  status="RESOLVED_OFFICIAL_SOURCE_COPIED_VARIANT",
                                  source_id=sid, copied_from=ins_code))
                kept += 1
        con.commit()
        summaries.append({"symbol": fund.get("symbol"), "profits": len(profits),
                          "inserted_events": kept, "endpoint": api})
    con.close()
    copied = {(r.get("fund"), r.get("symbol"), r.get("profit_date"))
              for r in audit
              if r.get("status") == "RESOLVED_OFFICIAL_SOURCE_COPIED_VARIANT"}
    for r in audit:
        if (r.get("status") in ("DIVIDEND_GE_REFERENCE", "NO_REFERENCE_PRICE",
                               "NO_TRADING_DAY_AFTER_PROFIT")
                and (r.get("fund"), r.get("symbol"), r.get("profit_date")) in copied):
            r["status"] = "SUPERSEDED_BY_COPIED_VARIANT"
    if audit:
        with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=sorted({k for r in audit for k in r}))
            w.writeheader()
            for r in audit:
                w.writerow(r)
    print(json.dumps({"summaries": summaries,
                      "status": dict((s, sum(1 for r in audit if r.get("status") == s))
                                     for s in sorted({r.get("status") for r in audit}))},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
