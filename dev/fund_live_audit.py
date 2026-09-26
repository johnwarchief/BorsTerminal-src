"""dev/fund_live_audit.py — تطبیق زندهٔ اعدادِ جدول بنیادی با خودِ صورتِ مالیِ کدال

چرا: اسکنِ داخلیِ market.db ردیف‌هایی با پُلِ غیرمنطقی نشان داد (مثلاً صندوقِ
ساحل: فروشِ 1401 = 9.27e11 «میلیون ریال» ولی فروشِ 1404 = 1.7e7). قبل از هر
تغییری باید معلوم شود تقصیرِ ماست یا خودِ فایلِ کدال.

چطور: همان مسیری که codal_fetcher می‌رود را بی‌side-effect طی می‌کند —
صفحهٔ اطلاعیه را می‌گیرد، شیتِ «سود و زیان» را از dropdown پیدا می‌کند،
سپس سلول‌های JSON-درونِ صفحه را به شبکه برمی‌گرداند و ردیفِ عددِ ذخیره‌شده
(بر اساسِ آدرسِ سلول) را با برچسبش چاپ می‌کند. واحدِ درج‌شده در همان شیت هم
چاپ می‌شود، چون باگِ پل دقیقاً از همان‌جا خوانده می‌شود.

عمداً codal_fetcher import نمی‌شود: آن ماژول در خطای متوالیِ درخواست IP را با
ADB می‌چرخاند (قطعِ واقعیِ شبکه). اینجا فقط requestsِ ساده با مکث.

  python dev/fund_live_audit.py ساحل آلا فولاد دعبید مبین خودرو
"""
from __future__ import annotations

import html as _html
import json
import re
import sqlite3
import sys
import time

import requests

DB = "market.db"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "Referer": "https://codal.ir/", "Accept-Language": "fa,en;q=0.8"}
CELL_RE = re.compile(r'\{"metaTableId".*?"isAudited":(?:true|false)\}')
FA = "۰۱۲۳۴۵۶۷۸۹"
AR = "٠١٢٣٤٥٦٧٨٩"


def norm_digits(s: str) -> str:
    out = []
    for c in s:
        i = FA.find(c)
        if i < 0:
            i = AR.find(c)
        out.append(str(i) if i >= 0 else c)
    return "".join(out)


def get(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.text


def sheet_ids(page: str):
    """[(id, label)] از dropdownِ شیت‌ها."""
    return [(v, _html.unescape(l).strip())
            for v, l in re.findall(r'<option[^>]*value="(\d+)"[^>]*>([^<]{2,80})', page)]


def cells_of(sheet_html: str):
    """سلول‌های JSON-درونِ صفحه → {row: {col: text}} به‌همراه متنِ واحد."""
    grid: dict[int, dict[str, str]] = {}
    for raw in CELL_RE.findall(sheet_html):
        try:
            c = json.loads(raw)
        except Exception:
            continue
        addr = c.get("address") or ""
        m = re.match(r"([A-Z]+)(\d+)", addr)
        if not m:
            continue
        val = str(c.get("value") or "").strip()
        if not val:
            continue
        grid.setdefault(int(m.group(2)), {})[m.group(1)] = val
    unit = ""
    mu = re.search(r"(?:مبالغ|مابالغ)[^.<>]{0,60}(?:ريال|ریال)[^.<>]{0,20}",
                   _html.unescape(sheet_html))
    if mu:
        unit = norm_digits(mu.group(0))
    if not unit:
        mu = re.search(r"(?:هزار|ميليون|میلیون|مليارد|مليار)[^.<>]{0,10}(?:ريال|ریال)",
                       _html.unescape(sheet_html))
        if mu:
            unit = norm_digits(mu.group(0))
    return grid, unit


def num(s: str):
    s = norm_digits(s).replace(",", "").replace("٬", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def find_row(grid, target: float):
    hits = []
    for row, cols in grid.items():
        for col, txt in cols.items():
            v = num(txt)
            if v is None or abs(v) < 1:
                continue
            for scale, tag in ((1.0, "دقیق"), (1e-6, "/۱e۶"), (1e6, "×۱e۶")):
                if abs(v * scale - target) <= max(1.0, abs(target) * 1e-6):
                    hits.append((row, col, tag, cols.get("A") or cols.get("B") or ""))
    return hits


def abs_url(u: str) -> str:
    if u.startswith("http"):
        return u
    return "https://codal.ir" + (u if u.startswith("/") else "/" + u)


def audit(symbol: str, con):
    rows = con.execute(
        "select period_end, url, revenue, net_profit, gross_profit, basic_eps, unit "
        "from financial_statements where symbol=? order by period_end desc limit 3",
        (symbol,)).fetchall()
    print(f"\n===== {symbol}")
    if not rows:
        print("  ردیفی در جدول نیست")
        return
    for period_end, url, revenue, net_profit, _gp, _eps, unit in rows:
        if not url:
            print(f"  {period_end}: نشانیِ منبع ثبت نشده")
            continue
        try:
            page = get(abs_url(url))
            sheets = sheet_ids(page)
            # «صورت سود و زیان» باید دقیقاً همان شیت باشد. انتخابِ نخستین شیتی که
            # برچسبش *شامل* «سود و زیان» است روی اطلاعیه‌های ۱۷–۲۴ شیتی «صورت سود
            # و زیان جامع» را برمی‌داشت و بعد عددِ درستِ فروش را «در هیچ سلولی
            # نیست» اعلام می‌کرد — هشدارِ کاذب، نه باگِ داده. (تلفیقی هم مبنای
            # شاخص‌ها نیست؛ آخرین اولویت است.)
            def _rank(label: str) -> int:
                l = norm_digits(label).replace("ي", "ی")
                if "سود و زیان" not in l:
                    return 9
                if "جامع" in l or "بین الف" in l or "بين الف" in l:
                    return 3
                if "تلفیقی" in l:
                    return 2
                return 0
            inc = sorted([s for s in sheets if _rank(s[1]) < 9], key=lambda s: _rank(s[1]))
            if not inc:
                print(f"  {period_end}: شیت سود و زیان در {len(sheets)} شیت نیست")
                continue
            grid, s_unit = cells_of(get(abs_url(url) + "&sheetId=" + inc[0][0]))
        except Exception as exc:
            print(f"  {period_end}: خواندن منبع شکست - {type(exc).__name__} {exc}")
            continue
        print(f"  {period_end}: شیت={inc[0][1]}  واحدِ شیت={s_unit or '؟'}  "
              f"واحدِ ردیفِ ما={(unit or '—')[:34]}")
        for label, val in (("فروش", revenue), ("سود خالص", net_profit)):
            if not val:
                continue
            hits = find_row(grid, float(val))
            tags = sorted({h[2] for h in hits}) or ["در هیچ سلولی نیست"]
            rowlbl = (hits[0][3] if hits else "")[:38]
            print(f"    {label} = {val:,.0f} → {' یا '.join(tags)}"
                  + (f"  (ردیف: {rowlbl})" if rowlbl else ""))
        time.sleep(2.0)


if __name__ == "__main__":
    syms = sys.argv[1:] or ["فولاد", "دعبید", "مبین", "ساحل", "آلا", "خودرو"]
    con = sqlite3.connect(DB)
    for s in syms:
        try:
            audit(s, con)
        except Exception as exc:      # یک نماد نباید کلِ حسابرسی را بخواباند
            print(f"[!] {s}: {type(exc).__name__} {exc}")
        time.sleep(2.5)
    con.close()
