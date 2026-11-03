#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_dividend_ingest.py — واکشیِ DPSِ اعلامیِ مجمع و نوشتنِ جدولِ
`stock_dividend_events` (منبعِ درستِ D در فرمولِ رهاورد؛ R32H).

چرا این ابزار:
  • چارت D را از `pna − pcl`ِ دفترِ تعدیل می‌گرفت؛ آن عدد با DPSِ اعلامیِ مجمع
    یکی نیست (R32H: ۲۰ از ۳۲ گامِ دور با DPSِ مجمع + پایانیِ رسمی **دقیق** شد).
  • این ابزار برایِ هر ردیفِ `price_adjust_event_rows` یک‌بار DPS را از
    `Decision.aspx` می‌خواند و کنارِ پایانیِ رسمیِ همان روز ذخیره می‌کند؛
    چارت بعد از آن فقط جدول را می‌خواند (بی‌شبکه).

قواعدِ ایمنی:
  • `--db` اجباری است و هیچ پیش‌فرضی به `market.db`ِ عملیاتی ندارد؛ رویِ کپی
    اجرا کنید.
  • POLITE و بی‌چرخشِ IP: `rotate_ip_via_adb` خنثی می‌شود. بودجهٔ درخواست
    (`--budget`) سخت است؛ با ۴۲۹ همان‌جا متوقف می‌شود، نه با استراحتِ ۳۰
    دقیقه‌ایِ استخر (این ابزار تک‌رشته‌ای است).
  • resumable: ردیفِ موجود دوباره واکشی نمی‌شود؛ اجرای بعدی از همان‌جا ادامه
    می‌دهد. ردیفِ بی‌DPS/بی‌پایانی نوشته نمی‌شود و در لاگ با وضعیتش می‌ماند.

نمونه:
    python dev/codal_dividend_ingest.py --db D:/tmp/market_copy.db --budget 20
    python dev/codal_dividend_ingest.py --db ... --symbols سپيدار,كگهر --limit 50
    python dev/codal_dividend_ingest.py --db ... --dry-run
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import codal_dividends as CD          # noqa: E402
import codal_fetcher as CF            # noqa: E402
import jdatetime                      # noqa: E402
import tsetmc_p0_schema as SCHEMA     # noqa: E402


def _iso(d_even):
    s = str(int(d_even))
    return "%s-%s-%s" % (s[:4], s[4:6], s[6:8]) if len(s) == 8 else None


def _symbol_of(con, ins_code):
    row = con.execute(
        "SELECT l_val18, l_val30, paper_type FROM instruments WHERE ins_code=?"
        " ORDER BY updated_at DESC LIMIT 1", (str(ins_code),)).fetchone()
    return row


def select_candidates(con, symbols=None, date_from=None, date_to=None,
                      limit=None, pairs=None):
    """[(ins_code, symbol, d_even, p_closing)] از دفترِ PA، بی ردیفِ موجود.

    فقط سهام (paper_type 1/2، بی «حق تقدم»)؛ ردیفِ `stock_dividend_events`ِ
    موجود candidate نیست (resume). `pairs` = [(symbol, d_even)] برایِ اجرایِ
    هدف‌دار (مثلاً همان ۶۶ گامِ R32H).
    """
    have = set()
    try:
        have = {(str(a), int(b)) for a, b in con.execute(
            "SELECT ins_code, d_even FROM stock_dividend_events")}
    except Exception:
        pass
    out, seen = [], set()
    if pairs:
        for symbol, d_even in pairs:
            row = con.execute(
                "SELECT ins_code FROM instruments WHERE l_val18=?"
                " ORDER BY updated_at DESC LIMIT 1", (symbol,)).fetchone()
            if not row:
                continue
            d_even = int(d_even)
            if (str(row[0]), d_even) in have:
                continue
            out.append((str(row[0]), symbol, d_even, None))
        return out[:limit] if limit else out
    rows = None
    try:
        rows = con.execute(
            "SELECT ins_code, d_even, p_closing FROM price_adjust_event_rows"
            " GROUP BY ins_code, d_even ORDER BY d_even DESC").fetchall()
    except sqlite3.OperationalError:
        # بانکِ قدیمی فقط جدولِ کلیدِ واحد را دارد (همان fallbackِ چارت).
        try:
            rows = con.execute(
                "SELECT ins_code, d_even, p_closing FROM price_adjust_events"
                " ORDER BY d_even DESC").fetchall()
        except sqlite3.OperationalError:
            rows = []
    wanted = set(symbols or [])
    for ins_code, d_even, pcl in rows:
        ins_code = str(ins_code)
        if (ins_code, int(d_even)) in have or (ins_code, int(d_even)) in seen:
            continue
        meta = _symbol_of(con, ins_code)
        if not meta:
            continue
        symbol, full, ptype = meta
        if full and "حق تقدم" in str(full):
            continue
        if ptype is not None and int(ptype) not in (1, 2):
            continue
        if wanted and symbol not in wanted:
            continue
        iso = _iso(d_even)
        if not iso:
            continue
        if date_from and iso < date_from:
            continue
        if date_to and iso > date_to:
            continue
        seen.add((ins_code, int(d_even)))
        out.append((ins_code, symbol, int(d_even), pcl))
        if limit and len(out) >= limit:
            break
    return out


def reference_close(con, symbol, d_even, p_closing=None):
    """پایانیِ رسمیِ **اولین کندلِ هم‌روز یا پس از** روزِ مؤثرِ PA.

    همان نگاشتِ چارت (`next(t for t in candle_dates if t >= dt)`). روزِ PA
    می‌تواند بی‌معامله باشد؛ پایانیِ همان روزِ بی‌کندل نزدیک‌ترین عددِ اشتباه
    است (سپيدار ۲۰۲۵-۰۶-۰۲: p_closing=۱۱۸۶۰ ولی کندلِ ۰۶-۰۳ پایانیِ ۱۴۰۰۰
    دارد و مرجع با ۱۴۰۰۰ ساخته شده). p_closing فقط وقتی می‌ماند که هیچ
    کندلی پس از روزِ PA نباشد.
    """
    iso = _iso(d_even)
    if iso:
        row = con.execute(
            "SELECT close FROM price_history WHERE symbol=? AND date>=?"
            " ORDER BY date ASC LIMIT 1", (symbol, iso)).fetchone()
        if row and row[0]:
            return float(row[0])
    try:
        if p_closing is not None and float(p_closing) > 0:
            return float(p_closing)
    except (TypeError, ValueError):
        pass
    return None


def ingest(con, candidates, finder, budget=20, dry_run=False, log=None):
    """اجرایِ واکشی رویِ candidates؛ برگشتِ شمارش‌ها.

    `finder(symbol, eff_date)` → {'status','dps','notice_id','publish_date','url',
    'requests'}. status: OK | NO_DPS | NO_LETTER | BLOCKED.
    """
    counts = {"ok": 0, "no_dps": 0, "no_close": 0, "blocked": 0,
              "skipped": 0, "requests": 0}
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for ins_code, symbol, d_even, pcl in candidates:
        if counts["requests"] >= budget:
            counts["skipped"] = len(candidates) - (counts["ok"] + counts["no_dps"]
                                                   + counts["no_close"] + counts["blocked"])
            break
        ref = reference_close(con, symbol, d_even, pcl)
        if ref is None:
            counts["no_close"] += 1
            _log(log, {"symbol": symbol, "d_even": d_even,
                       "status": "NO_CLOSE", "source": "local"})
            continue
        res = finder(symbol, _iso(d_even))
        counts["requests"] += int(res.get("requests") or 0)
        status = res.get("status")
        if status == "BLOCKED":
            counts["blocked"] += 1
            _log(log, {"symbol": symbol, "d_even": d_even, "status": "BLOCKED"})
            break
        if status != "OK" or not res.get("dps"):
            counts["no_dps"] += 1
            _log(log, {"symbol": symbol, "d_even": d_even, "status": status or "NO_DPS"})
            continue
        dps = float(res["dps"])
        ratio = ref / (ref + dps)
        if not dry_run:
            con.execute(
                "INSERT OR REPLACE INTO stock_dividend_events"
                "(ins_code,d_even,symbol,dps,reference_price,ratio,publish_date,"
                "source,source_id,fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ins_code, int(d_even), symbol, dps, ref, ratio,
                 res.get("publish_date"), "codal-assembly",
                 str(res.get("notice_id") or res.get("url") or ""), now))
        counts["ok"] += 1
        _log(log, {"symbol": symbol, "d_even": d_even, "status": "OK",
                   "dps": dps, "reference_price": ref, "ratio": ratio,
                   "notice_id": res.get("notice_id")})
    if not dry_run:
        con.commit()
    return counts


def _log(path, obj):
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception:
        pass


def local_decision_urls(con, symbol, eff_date, window_days=150):
    """[(tracing_no, url, publish_date)] از `codal_notices`ِ محلی، جدید به قدیم.

    مجمع باید **پیش از** روزِ مؤثر بوده باشد (پنجرهٔ `window_days`). این مسیر
    جستجویِ WAF‌دار را حذف می‌کند؛ نبودِ جدول/ردیف → [].
    """
    try:
        rows = con.execute(
            "SELECT tracing_no, title, publish_date, url FROM codal_notices"
            " WHERE symbol=? AND url LIKE '%Decision.aspx%'", (symbol,)).fetchall()
    except sqlite3.OperationalError:
        return []
    try:
        eff = datetime.date.fromisoformat(str(eff_date)[:10])
        ex_j = jdatetime.date.fromgregorian(date=eff).strftime("%Y/%m/%d")
    except ValueError:
        return []
    out, seen = [], set()
    for tr, title, pdate, url in rows:
        t = str(title or "")
        if "مجمع" not in t and "سود" not in t:
            continue
        period = notice_period_end(t)
        if period and period > ex_j:
            continue
        try:
            y, m, d = [int(x) for x in str(pdate).split()[0].split("/")[:3]]
            g = jdatetime.date(y, m, d).togregorian()
        except (ValueError, TypeError):
            continue
        if not (eff - datetime.timedelta(days=window_days) <= g <= eff):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append((tr, url, pdate, period or "0000/00/00"))
    out.sort(key=lambda x: (x[3], str(x[2])), reverse=True)
    return [(tr, url, pdate) for tr, url, pdate, _p in out]


_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def notice_period_end(title):
    """"... دوره ۱۲ ماهه منتهی به ۱۴۰۳/۱۲/۲۹" → '1403/12/29' (بی‌دوره → None).

    انتخابِ DPS باید دوره‌محور باشد: سودِ سالِ مالیِ **آخرِ پیش از** روزِ مؤثر
    مرجع است؛ «جدیدترین انتشار» می‌تواند اصلاحیهٔ سالِ قدیم باشد و D اشتباه.
    """
    t = str(title or "").translate(_FA_DIGITS)
    m = re.search(r"منتهی\s*به\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})", t)
    if not m:
        return None
    y, mo, d = re.split(r"[/-]", m.group(1))
    return "%s/%02d/%02d" % (y, int(mo), int(d))


def _notice_key(x):
    return (notice_period_end(x.get("Title")) or "0000/00/00",
            CF._norm_date(x.get("PublishDateTime")))


def make_live_finder(session, page_pause=1.5, local_lookup=None):
    """finder: اول اطلاعیه‌هایِ محلی، بعد جستجویِ LetterType=20 → Decision.aspx."""
    state = {"requests": 0}

    def _page_dps(url):
        time.sleep(page_pause)
        state["requests"] += 1
        page = session.get(url, headers=CF._headers(), timeout=60)
        return CD.parse_dividend_per_share(page.text)

    def finder(symbol, eff_date):
        state["requests"] = 0
        local = local_lookup(symbol, eff_date) if local_lookup else []
        for tr, url, pdate in local:
            try:
                dps = _page_dps(url)
            except Exception:
                continue
            if dps is not None:
                return {"status": "OK", "dps": dps, "notice_id": tr,
                        "publish_date": CF._norm_date(pdate), "url": url,
                        "requests": state["requests"], "via": "local-notices"}
        try:
            gd = datetime.date.fromisoformat(eff_date)
            jd = jdatetime.date.fromgregorian(date=gd)
        except Exception:
            return {"status": "NO_LETTER", "requests": state["requests"]}
        ex_j = jd.strftime("%Y/%m/%d")
        frm = (jd - jdatetime.timedelta(days=100)).strftime("%Y/%m/%d")
        to = (jd + jdatetime.timedelta(days=10)).strftime("%Y/%m/%d")
        q = dict(CF.QUERY, Symbol=symbol, Category="-1", LetterType="20",
                 FromDate=frm, ToDate=to)
        state["requests"] += 1
        letters = CF.fetch_page(session, 1, q, quiet=True, max_429_retries=0)
        if letters is None:
            return {"status": "BLOCKED", "requests": state["requests"]}
        if not letters:
            q["LetterType"] = "-1"
            state["requests"] += 1
            letters = CF.fetch_page(session, 1, q, quiet=True, max_429_retries=0) or []
        dec = [x for x in letters
               if "Decision.aspx" in (x.get("Url") or "")
               and ("تصمیمات" in (x.get("Title") or "")
                    or "خلاصه" in (x.get("Title") or ""))]
        # دورهٔ پس از روزِ مؤثر (سالِ آینده/اصلاحیهٔ بعدی) نامزد نیست.
        dec = [x for x in dec
               if (notice_period_end(x.get("Title")) or "0000/00/00") <= ex_j]
        dec.sort(key=_notice_key)
        for x in reversed(dec):
            try:
                u = CF._abs_codal_url(x.get("Url"))
                dps = _page_dps(u)
            except Exception:
                continue
            if dps is not None:
                return {"status": "OK", "dps": dps,
                        "notice_id": x.get("TracingNo") or x.get("LetterSerial"),
                        "publish_date": CF._norm_date(x.get("PublishDateTime")),
                        "url": u, "requests": state["requests"], "via": "search"}
        return {"status": "NO_DPS", "requests": state["requests"]}

    return finder


def main(argv=None):
    ap = argparse.ArgumentParser(description="Codal assembly DPS ingest")
    ap.add_argument("--db", required=True, help="مسیرِ دیتابیسِ هدف (کپی، نه عملیاتی)")
    ap.add_argument("--symbols", default="", help="فهرستِ نماد با کاما")
    ap.add_argument("--from", dest="date_from", default="")
    ap.add_argument("--to", dest="date_to", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--budget", type=int, default=20, help="سقفِ درخواستِ شبکه")
    ap.add_argument("--pairs", default="", help="JSON: [[symbol,d_even],...]")
    ap.add_argument("--log", default="", help="JSONLِ لاگ")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.isfile(a.db):
        print("db not found: %s" % a.db)
        return 2
    con = sqlite3.connect(a.db, timeout=30)
    SCHEMA.create_all(con)
    pairs = json.loads(a.pairs) if a.pairs else None
    cand = select_candidates(
        con, symbols=[s for s in a.symbols.split(",") if s],
        date_from=a.date_from or None, date_to=a.date_to or None,
        limit=a.limit or None, pairs=pairs)
    print("candidates: %d" % len(cand))
    if a.dry_run:
        print(json.dumps([{"symbol": s, "d_even": d} for _i, s, d, _p in cand[:20]],
                         ensure_ascii=False))
        return 0
    # تک‌رشته‌ای + بودجهٔ سخت: استراحتِ استخر بی‌معناست؛ با ۴۲۹ همان‌جا می‌ایستیم.
    CF.POLITE = True
    CF.rotate_ip_via_adb = lambda *x, **k: False
    CF._trigger_backoff = lambda seconds=60: None
    CF._control_sleep = lambda total, slice_=5.0: (time.sleep(min(total, 15)), "")[1]
    session = CF.make_session()
    finder = make_live_finder(
        session, local_lookup=lambda sym, eff: local_decision_urls(con, sym, eff))
    res = ingest(con, cand, finder, budget=a.budget,
                 dry_run=a.dry_run, log=a.log or None)
    con.close()
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
