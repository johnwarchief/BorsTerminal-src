# -*- coding: utf-8 -*-
"""قدمِ ۲ — سنجشِ سرتاسری رویِ **کپیِ** بانک: مهاجرت ← نوشتن ← خواندن.

هیچ چیزی درِ market.db واقعی نوشته نمی‌شود؛ ابتدا با sqlite3.backup یک کپی گرفته
می‌شود (همان چیزی که مالک خواسته: «رویِ کپیِ دیتابیس کار کن»).

چهار چیز که باید ثابت شود (قراردادِ docs/CANDLE-CONTRACT.md §۱-ث و §۱-ج الف):
 ۱) `ensure_schema` دو ستونِ `last`/`value` را به `price_history` و `p_last` را به
    `daily_prices` اضافه می‌کند، بی‌دست‌زدنِ ردیف‌هایِ موجود.
 ۲) `fetch_price_history` از ردیفِ CSV: open == FIRST (نه OPEN)، close == CLOSE،
    last == LAST، value == VALUE — عددبهعدد با خودِ همان ردیفِ CSV مقابله می‌شود.
 ۳) `/api/chart-db` دیگر `last := close` نمی‌سازد؛ ردیفِ فاقدِ last صریح null می‌دهد.
 ۴) لنگرِ تعدیل دست‌نخورده: `_adjust_events_from_rows` همان base=OPEN/close=CLOSE را
    می‌خواند و رویدادهایش از presenceِ ستونِ last اثر نمی‌گیرد.
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_tsetmc as T  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "market.db")
SYMBOL = "فولاد"
INS = "46348559193224090"
PASS = FAIL = 0


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   " + what)
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  ← {detail}" if detail else ""))


def main():
    print("قدمِ ۲ — src:", SRC)
    fd, copy = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(copy)
    a = sqlite3.connect(SRC, timeout=60)
    b = sqlite3.connect(copy)
    with b:
        a.backup(b)
    a.close()
    b.close()
    print("کپی:", copy, f"{os.path.getsize(copy)//2**20} MB")
    T.DB_PATH = copy
    import api._core as C  # noqa: E402
    C.DB_PATH = copy
    import api.chart as CH  # noqa: E402
    CH.DB_PATH = copy

    conn = sqlite3.connect(copy)
    import mstat_engine  # noqa: E402
    mstat_engine.ensure_schema(conn)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(price_history)")]
    ck("last" in cols and "value" in cols, "مهاجرت: price_history حالا last/value دارد", str(cols))
    dcols = [r[1] for r in conn.execute("PRAGMA table_info(daily_prices)")]
    ck("p_last" in dcols, "مهاجرت: daily_prices حالا p_last دارد", str(dcols[-2:]))
    before = conn.execute("SELECT COUNT(*), SUM(close) FROM price_history").fetchone()
    ck(conn.execute("SELECT COUNT(*) FROM price_history WHERE last IS NOT NULL").fetchone()[0] == 0,
       "ردیف‌هایِ قدیمی بی‌last می‌مانند (NULLِ صادقانه، نه پرکردنِ دست‌جمعی)", str(before))
    conn.close()

    # ── ۲) نوشتنِ واقعی از CSV ────────────────────────────────────────────────
    n = T.fetch_price_history(SYMBOL, since="2026-09-01")
    print(f"  [fetch_price_history] {n} ردیف")
    ck(n > 0, "مسیرِ CSV ردیف می‌نویسد", str(n))
    conn = sqlite3.connect(copy)
    got = {r[0]: r[1:] for r in conn.execute(
        "SELECT date, open, high, low, close, volume, last, value FROM price_history "
        "WHERE symbol=? AND date>='2026-09-01'", (SYMBOL,))}
    import csv as _csv, io as _io, urllib.request  # noqa: E402
    u = f"{T.BASE}/ClosingPrice/GetClosingPriceDailyListCSV/{INS}/20260901"
    txt = urllib.request.urlopen(urllib.request.Request(u, headers=T.HEADERS),
                                 timeout=150).read().decode("utf-8", "replace")
    rr = list(_csv.reader(_io.StringIO(txt)))
    head = [h.strip("<>") for h in rr[0]]
    ix = {k: i for i, k in enumerate(head)}
    want = {}
    for f in rr[1:]:
        if len(f) < len(head) or not f[ix["DTYYYYMMDD"]].strip().isdigit():
            continue
        d = f[ix["DTYYYYMMDD"]]
        iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        if iso >= "2026-09-01":
            want[iso] = {k: float(f[ix[k]]) for k in
                         ("FIRST", "HIGH", "LOW", "CLOSE", "OPEN", "LAST", "VOL", "VALUE")}
    common = sorted(set(want) & set(got))
    ck(len(common) >= 5, "پنج ردیفِ مشترک برایِ مقابله هست", f"{len(common)}")
    bad_open = bad_last = bad_val = bad_close = 0
    for d in common:
        g = got[d]      # (open, high, low, close, volume, last, value)
        w = want[d]
        if abs(g[0] - w["FIRST"]) > 0.51:
            bad_open += 1
        if abs(g[3] - w["CLOSE"]) > 0.51:
            bad_close += 1
        if g[5] is None or abs(g[5] - w["LAST"]) > 0.51:
            bad_last += 1
        if g[6] is None or abs(g[6] - w["VALUE"]) > 1.0:
            bad_val += 1
    ck(bad_open == 0, "open == FIRST (سنجشِ §۱-ج الف؛ دیگر نه OPEN/پایه)",
       f"{bad_open} از {len(common)}")
    ck(bad_close == 0, "close == CLOSE (لنگرِ تعدیل جابه‌جا نشد)", f"{bad_close} از {len(common)}")
    ck(bad_last == 0, "last == LAST (آخرینِ خام، بی‌جعل)", f"{bad_last} از {len(common)}")
    ck(bad_val == 0, "value == VALUE (گردشِ ریالی درِ جدولِ کندل نشست)", f"{bad_val} از {len(common)}")
    disagree = [d for d in common if abs(want[d]["FIRST"] - want[d]["OPEN"]) > 0.51
                and abs(want[d]["LAST"] - want[d]["CLOSE"]) > 0.51]
    ck(len(disagree) > 0,
       "درِ این پنجره روزهایی هست که FIRST≠OPEN و LAST≠CLOSE (کنترلِ منفیِ واقعی، نه بی‌محتوا)",
       f"{len(disagree)} روز، نمونه: {disagree[:3]}")
    conn.close()

    # ── ۳) خواندن ─────────────────────────────────────────────────────────────
    res = CH.get_chart_db(SYMBOL)
    candles = res.get("candles") or []
    ck(res.get("status") == "success" and len(candles) > 0, "/api/chart-db می‌خواند",
       str(res.get("count")))
    n_null = sum(1 for c in candles if c.get("last") is None)
    n_eq = sum(1 for c in candles if c.get("last") is not None and c["last"] == c["close"])
    n_diff = sum(1 for c in candles if c.get("last") is not None and c["last"] != c["close"])
    print(f"  کندل‌ها: {len(candles)} | last=null: {n_null} | last==close: {n_eq} | "
          f"last!=close: {n_diff}")
    ck(n_diff > 0, "حداقلِ یکِ کندل با lastِ *متفاوت* از close هست (ستون واقعاً پر می‌شود)",
       str(n_diff))
    # قاعدۀ اصلیِ §۱-ث شرطِ ۳: هیچ کندلی lastی ندارد مگر عددِ خودش؛ پس هر lastِ
    # برابرِ close باید روزی باشد که خودِ مرجع LAST و CLOSE را یکسان زده.
    d_eq = {d for d in common if abs(want[d]["LAST"] - want[d]["CLOSE"]) <= 0.51}
    d_diff = set(common) - d_eq
    eq_days = {c["time"] for c in candles if c.get("last") == c["close"]}
    ck(len(eq_days - d_eq) == 0,
       "last==close فقط آن‌جاست که خودِ مرجع دو عدد را یکسان زده", str(sorted(eq_days - d_eq))[:120])
    ck(len([d for d in d_diff if d in eq_days]) == 0,
       "NEGATIVE CONTROL: روزهایی که مرجع LAST≠CLOSE را هیچ‌گاه one-number نمی‌کند",
       str([d for d in d_diff if d in eq_days])[:120])
    ck(all(c.get("last") is not None for c in candles if c["time"] in set(common)),
       "هر ردیفی که تازه از CSV نوشته شد lastِ خودش را دارد (نه null، نه جعل)",
       str([c["time"] for c in candles if c["time"] in set(common) and c.get("last") is None])[:120])

    # ── ۴) لنگرِ تعدیل ────────────────────────────────────────────────────────
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "api", "chart.py"), encoding="utf-8").read()
    body = src[src.index("def _adjust_events_from_rows"):src.index("def _d_even_to_date")]
    ck("base" in body and "close" in body and "last" not in body.split('"""')[-1],
       "زنجیرِ کشفِ لنگر همچنان base=OPEN و close=CLOSE را می‌خواند (بی‌last)",
       " ".join(body.split())[:120])
    os.unlink(copy)
    print(f"\nقیمت‌ستونِ تازه: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
