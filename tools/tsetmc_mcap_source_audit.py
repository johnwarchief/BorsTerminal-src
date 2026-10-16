# -*- coding: utf-8 -*-
"""tools/tsetmc_mcap_source_audit.py — از کجا «ارزشِ بازار» درِ خودِ صفحۀ TSETMC می‌آید؟

رأیِ مالک ۱۴۰۵-۰۷-۱۷: «پیش از canonical کردن market_watch.market_cap یک
API/network audit مجدد بکن و endpoint/field دقیقِ همان صفحۀ TSETMC را پیدا کن؛
اگر marketValue نماد live گرفته می‌شود، با عددِ ما مقایسه کن.»

این فایل عمداً چیزی را حدس نمی‌زند: نامِ pathها ازِ خودِ کدِ این ریپو
(`test_tsetmc.py`) برداشته شده (همان‌هایی که درِ production کار می‌کنند) و
برایِ هر مسیر، کلیدهایی که `cap`/`value`/`market` درِ نامشان هست چاپ می‌شود.
خروجی: جدولِ مقایسه + وضعیتِ هر مسیر (PONG/HTTP error/بی‌کلید).

اجرا:  python tools/tsetmc_mcap_source_audit.py [--symbol فولاد]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from typing import Any

sys.path.insert(0, ".")

import test_tsetmc as T          # BASE، HEADERS و مسیرهایِ اثبات‌شدۀ همین ریپو
from bors_config import DB_PATH

NEEDLE = re.compile(r"cap|value|mkt|market|turn", re.I)
HITS = re.compile(r"cap|value", re.I)


def _walk(obj: Any, path: str = "", out: dict | None = None) -> dict:
    """هر برگِ ساختارِ JSON که نامش cap/value دارد، با مسارِ کاملش."""
    if out is None:
        out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if isinstance(v, (dict, list)):
                _walk(v, p, out)
            elif HITS.search(str(k)):
                out[p] = v
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:3]):
            _walk(v, f"{path}[{i}]", out)
    return out


def _fetch(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers=dict(T.HEADERS))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:                      # noqa: BLE001 - شبکه/تایم‌اوت
        return None, f"{type(e).__name__}"
    try:
        return json.loads(raw), None
    except Exception:                             # noqa: BLE001
        # «غیرِ JSON» معمولاً یعنی SPA-shellِ سایت (۸۰۳ بایتِ index.html) —
        # یعنی آن path وجود ندارد، نه اینکه داده هست و ما نمی‌خوانیمش.
        if raw.lstrip().lower().startswith("<!doctype") or "<html" in raw[:400].lower():
            return None, "SPA-shell (path وجود ندارد)"
        return None, f"non-JSON ({len(raw)}B)"


def candidates(ins_code: str, isin: str) -> list[tuple[str, str]]:
    """فقط مسیرهایی که درِ همین ریپو تعریف/استفاده شده‌اند (بی‌حدسِ آدرسِ تازه)."""
    pt = "&".join(f"paperTypes[{i}]={i+1}" for i in range(9))
    b = T.BASE
    out = [
        ("GetInstrumentInfo", f"{b}/Instrument/GetInstrumentInfo?i={ins_code}"),
        ("InstmentDetali", f"{b}/InstmentDetali/GetInstrumentInfo?i={ins_code}"),
        ("ClosingPrice/GetMarketWatch", f"{b}/ClosingPrice/GetMarketWatch?market=0&{pt}"
                                        "&showTraded=false&withBestLimits=false&hEven=0"),
        ("MarketWatchLuvhi", f"{b}/MarketWatchLuvhi/GetMarketWatchAll?z=0"),
        ("OverviewForInstrument", f"{b}/OverviewForInstrument/GetFmkWeight?i={ins_code}"),
        ("OverviewForInstrument2", f"{b}/OverviewForInstrument/GetInsGroupState?i={ins_code}"),
        ("TSE-v2-instinfofast", f"https://www.tsetmc.com/tsev2/data/instinfofast.aspx?i={ins_code}"),
    ]
    if isin:
        out.append(("TSE-v2-instinfofast-isin",
                    f"https://www.tsetmc.com/tsev2/data/instinfofast.aspx?i={ins_code}&{isin}="))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="فولاد")
    args = ap.parse_args()

    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    r = c.execute("SELECT i.ins_code, i.l_val18, i.isin, m.market_cap, m.market_cap_src,"
                  " m.p_closing, m.p_last, i.total_shares, m.d_even"
                  " FROM instruments i LEFT JOIN market_watch m ON m.ins_code=i.ins_code"
                  " WHERE i.l_val18 = ?", (args.symbol,)).fetchone()
    if r is None:
        print(f"نمادِ {args.symbol!r} درِ instruments نیست")
        c.close()
        return 2
    ours = {
        "ins_code": str(r["ins_code"]), "symbol": r["l_val18"], "isin": r["isin"] or "",
        "market_cap_rial": r["market_cap"], "src": r["market_cap_src"],
        "p_closing": r["p_closing"], "p_last": r["p_last"], "total_shares": r["total_shares"],
        "d_even": r["d_even"],
    }
    c.close()
    ours["product_rial"] = (float(r["p_closing"] or 0) * float(r["total_shares"] or 0)) or None
    print("مقدارِ خودِ ما (market.db):")
    print(json.dumps(ours, ensure_ascii=False, default=str))

    rows = []
    for name, url in candidates(ours["ins_code"], ours["isin"]):
        time.sleep(0.6)
        js, err = _fetch(url)
        if err:
            rows.append((name, "خطا", err, ""))
            continue
        hits = _walk(js)
        if not hits:
            rows.append((name, "بدونِ کلیدِ cap/value", "", ""))
            continue
        keep = {k: v for k, v in hits.items() if NEEDLE.search(k)}
        top = list(keep.items())[:8]
        rows.append((name, f"{len(keep)} کلید", "; ".join(f"{k}={v}" for k, v in top[:4]), ""))
    print("\n" + "=" * 100)
    print(f"{'مسیر':32} {'وضعیت':22} آنچه پیدا شد")
    print("=" * 100)
    for name, st, found, _ in rows:
        print(f"{name:32} {st:22} {found[:130]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
