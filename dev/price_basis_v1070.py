#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/price_basis_v1070.py — مبنایِ قیمت یک تصمیمِ سروری است؛ لنگرِ تعدیل هرگز با آن تکان نمی‌خورد.

چرا این گارد متولد شد (کارِ #73 قدمِ ۳، ۱۴۰۵-۰۷-۱۱):
قراردادِ `docs/CANDLE-CONTRACT.md` §۱-ث «Price Source» را settingِ محصول کرد
(`last` | `closing`، پیش‌فرض `last`) و پنج تضمین خواست. چهار تایِ آن‌ها آزمون‌پذیرند و
این فایل همان چهار را می‌سنجد:

  ۱) یکِ resolver، همه‌جا — هیچ مصرف‌کننده‌ای ستون را خودش انتخاب نمی‌کند.
  ۲) setting سمتِ سرور است، نه فرانت.
  ۳) مخفی‌سازیِ جعلِ داده — نبودِ «آخرین» صریح اعلام می‌شود، نه پرشدن با پایانی.
  ۴) **مقاومتِ لنگر** — با تغییرِ setting تعدادِ رویدادهایِ تعدیل و مقدارِ ضرایب باید
     بیت‌به‌بیت یکسان بماند. این شرطِ بقایِ کلِ طرح است: سنجشِ §۱-پ نشان داد اگر لنگر
     هم به `last` برود، لنگر درِ ۷۳۹ از ۸۰۰ نماد (۹۲٪) می‌شکند.

گارد بی‌شبکه و بی‌market.dbِ واقعی می‌دود (فیکسچرهایِ کوچکِ درون‌حافظه‌ای).
اجرا:  python dev/price_basis_v1070.py
خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
"""
import io
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import price_basis  # noqa: E402

PASS = FAIL = 0


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   " + what)
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  ← {detail}" if detail else ""))


# ── ردیف‌هایِ CSV با یکِ شکافِ «پایه» (تعدیل) درِ روزِ سوم ───────────────────────────
# base(t) == close(t-1) درِ همه جا به‌جز 2024-01-04 که پایه نصف شده ⇒ یکِ رویدادِ تعدیل.
# LAST درِ هر روز با CLOSE فرق دارد تا مبنایِ منتخب واقعاً عددِ دیگری بدهد.
CSV = "\n".join([
    "<TICKER>,<DTYYYYMMDD>,<FIRST>,<HIGH>,<LOW>,<CLOSE>,<VALUE>,<VOL>,<OPENINT>,<PER>,<OPEN>,<LAST>",
    "<X>,20240101,1000,1050,980,1040,1e12,1e9,0,100.0,1000,1035",
    "<X>,20240102,1040,1090,1030,1080,1e12,1e9,0,100.0,1040,1075",
    "<X>,20240103,1080,1130,1070,1120,1e12,1e9,0,100.0,1080,1115",
    # پایهٔ امروز = 560 (نصفِ 1120) ⇒ شکافِ ۵۰٪ = رویدادِ تعدیل
    "<X>,20240104,600,640,590,630,1e12,1e9,0,100.0,560,625",
    "<X>,20240105,630,660,620,655,1e12,1e9,0,100.0,630,650",
]) + "\n"


def main():
    print("price_basis_v1070")
    tmpdir = tempfile.mkdtemp(prefix="pb_guard_")
    import bors_config
    real_path = bors_config.PRICE_BASIS_PATH
    bors_config.PRICE_BASIS_PATH = os.path.join(tmpdir, "price_basis.json")
    price_basis._cache["sig"] = None

    # ── ۱) مقادیرِ مجاز و پیش‌فرض ────────────────────────────────────────────
    print("\n[۱] setting")
    ck(price_basis.ALLOWED == ("last", "closing"),
       "مقادیرِ مجاز فقط last و closing‌اند", str(price_basis.ALLOWED))
    ck(price_basis.DEFAULT == "last", "پیش‌فرضِ محصول last است", price_basis.DEFAULT)
    if os.path.exists(bors_config.PRICE_BASIS_PATH):
        os.unlink(bors_config.PRICE_BASIS_PATH)
    ck(price_basis.current() == "last", "فایلِ نبود ⇒ last (بی‌استثنا، بی‌۵۰۰)", price_basis.current())
    ck(price_basis.set_basis("closing")["status"] == "success", "نوشتنِ closing می‌پذیرد")
    ck(price_basis.current() == "closing", "خواندنِ بعد از نوشتن همان closing است", price_basis.current())
    for bad in ("", "Close", "close", None, "avg", 7):
        ck(price_basis.set_basis(bad)["status"] == "error",
           "مقدارِ مردود: %r" % (bad,), str(price_basis.set_basis(bad)))
    ck(price_basis.current() == "closing", "مقدارِ مردودِ بی‌واسطه تنظیمات را عوض نکرد", price_basis.current())
    price_basis.set_basis("last")

    # ── ۲) قاعدۀ «سریِ مخلوط نداریم» ────────────────────────────────────────
    print("\n[۲] honestyِ سری")
    full = [{"time": "d1", "open": 1000.0, "high": 1050.0, "low": 980.0,
             "close": 1040.0, "last": 1035.0}]
    m = price_basis.apply_basis(full)
    ck(m["basis_applied"] == "last" and full[0]["close"] == 1035.0,
       "با lastِ کامل، closeِ سری == آخرین", str(full[0]))
    ck(full[0]["closing"] == 1040.0, "لنگر (closing) دست‌نخورده کنارش ماند", str(full[0]["closing"]))
    mixed = [{"time": "d1", "open": 1000.0, "high": 1050.0, "low": 980.0,
              "close": 1040.0, "last": 1035.0},
             {"time": "d2", "open": 1040.0, "high": 1090.0, "low": 1030.0,
              "close": 1080.0, "last": None}]
    m2 = price_basis.apply_basis(mixed)
    ck(m2["basis_applied"] == "closing" and m2["basis_reason"] == "last_missing:1/2",
       "سریِ نیمه‌last با lastِ مخلوط بسته نمی‌شود؛ صریح closing + دلیل", str(m2))
    ck(all(c["close"] == c["closing"] for c in mixed),
       "NEGATIVE CONTROL: هیچ کندلی درِ حالتِ fallback عددِ «آخرین» را به‌عنوان close ندارد",
       str([(c["close"], c["closing"]) for c in mixed]))
    wid = [{"time": "d1", "open": 1000.0, "high": 1050.0, "low": 980.0,
            "close": 1040.0, "last": 1200.0}]
    m3 = price_basis.apply_basis(wid)
    ck(wid[0]["close"] == 1200.0 and wid[0]["high"] == 1200.0 and wid[0]["low"] == 980.0,
       "آخرینِ بیرونِ بازه ⇒ سایه گِشاد می‌شود، قیمتِ منتخب خُرد نمی‌شود", str(wid[0]))
    ck(m3["geometry_widened"] == 1, "گِشاد‌کردن شمرده و گزارش می‌شود", str(m3))
    again = price_basis.apply_basis(wid)
    ck(wid[0]["high"] == 1200.0 and again["geometry_widened"] == 1,
       "NEGATIVE CONTROL: دو‌بار صدا‌زدن سایه را انباشته بالا نمی‌برد", str(wid[0]["high"]))

    # ── ۳) بی‌تغیریِ لنگر تحتِ هر دو مبنای (شرطِ بقای §۱-پ) ──────────────────
    print("\n[۳] مقاومتِ لنگرِ تعدیل")
    import api.chart as CH
    candles, volumes, all_rows = CH._parse_tsetmc_csv(CSV)
    events, anchored = CH._adjust_events_from_rows(all_rows)
    ev_sig = [(e["date"], round(e["ratio"], 10)) for e in events]
    ck(anchored and len(events) == 1 and events[0]["date"] == "2024-01-04",
       "فیکسچر یکِ رویدادِ تعدیلِ واقعی دارد (شکافِ پایه درِ ۰۱-۰۴)", str(ev_sig))

    def factors_for(basis):
        """همان الگوریتمِ produção (get_chart_tsetmc): پیمایشِ نزولی با یکِ ارجحِ رویداد.

        یکِ فاکتورِ «تجمعِ دوباره‌شونده برایِ هر کندل» اشتباهِ خودِ این تست بود، نه کدِ
        تولیدی؛ اینجا آینه‌وارِ `api/chart.py` نوشته شده تا مقایسه معنادار باشد.
        """
        price_basis.set_basis(basis)
        cands = [dict(c) for c in candles]
        price_basis.apply_basis(cands)
        ev = sorted([(e["date"], e["ratio"]) for e in events], reverse=True)
        order = sorted(range(len(cands)), key=lambda i: cands[i]["time"])
        f, j = 1.0, 0
        out = {}
        for i in reversed(order):
            t = cands[i]["time"]
            while j < len(ev) and ev[j][0] > t:
                f *= ev[j][1]
                j += 1
            out[t] = round(f, 10)
        return out, {c["time"]: (c["close"], c["closing"]) for c in cands}

    fa, pa = factors_for("last")
    fc, pc = factors_for("closing")
    ck(fa == fc, "ضرایبِ تعدیل تحتِ دو مبنای **بیت‌به‌بیت یکسان‌اند**",
       "%s vs %s" % (sorted(fa.items()), sorted(fc.items())))
    ck(fa == {"2024-01-05": 1.0, "2024-01-04": 1.0, "2024-01-03": 0.5,
              "2024-01-02": 0.5, "2024-01-01": 0.5},
       "پلۀ فاکتور درست است (تازه‌ترها ۱٫۰، پیش‌ترها ۰٫۵)", str(sorted(fa.items())))
    ck(pa["2024-01-01"][0] == 1035.0 and pc["2024-01-01"][0] == 1040.0,
       "closeِ نمایشی با setting عوض می‌شود (last ⇄ closing)",
       "%s | %s" % (pa["2024-01-01"], pc["2024-01-01"]))
    ck(all(pa[t][1] == pc[t][1] == 1040.0 for t in ["2024-01-01"]),
       "و closing (لنگر) درِ هر دو حالت همان پایانی است", str([pc[t][1] for t in ["2024-01-01"]]))

    # ── ۴) هیچ مسیرِ مستقلی برای انتخابِ close نمانده ────────────────────────
    print("\n[۴] تک‌رزولور")
    src = {f: io.open(os.path.join(ROOT, f), encoding="utf-8").read()
           for f in ("api/chart.py", "api/screener.py", "api/market_index.py",
                     "confidence_engine.py")}
    ck('last": float(r[4])' not in src["api/chart.py"] and "last = c          # <LAST>"
       not in src["api/chart.py"],
       "NEGATIVE CONTROL: جعلِ `last := close` درِ chart.py بازنگشته", "")
    ck('"last": round(c, 2)' not in src["api/market_index.py"],
       "NEGATIVE CONTROL: شاخصِ کل دیگر last=close جعل می‌کند", "")
    for f, needle in (("api/chart.py", "price_basis.resolve_payload"),
                      ("api/chart.py", "price_basis.apply_basis"),
                      ("api/screener.py", "price_basis.resolve_payload"),
                      ("api/market_index.py", "price_basis.resolve_payload"),
                      ("confidence_engine.py", "price_basis.apply_basis")):
        ck(needle in src[f], "%s از ریزالو رد می‌شود (%s)" % (f, needle), "")
    # سازندگانِ کندل: هر دیکشنریِ OHLC باید `last` را هم ببرد. فهرستِ صریحِ همهٔ
    # هفت سازندۀ chart.py (inventory §۴) — شمارشِ کلیِ «close» جایِ این نیست، چون
    # `all_rows` (ورودیِ لنگر) و payloadهایِ بی‌کندلِ FTS هم "close": دارند و نباید
    # last داشته باشند.
    chart = src["api/chart.py"]
    OHLC_BUILDERS = (
        '"close": c, "last": last})',                             # مسیرِ ۵: _parse_tsetmc_csv
        '"close": p_close, "volume": vol,',                       # مسیرِ ۶: کندلِ زندۀ تابلو
        '"low": float(r[3]), "close": float(r[4]),',              # مسیرِ ۷: get_chart_db
        '"close": r[5], "volume": r[6], "last": r[7]}',           # مسیرِ key-levels و patterns
        '"time": r[0], "close": r[1], "last": r[3]',              # مسیرِ /api/ma
    )
    for _b in OHLC_BUILDERS:
        ck(_b in chart, "سازندۀ کندل درِ chart.py دست‌نخورده شناسایی می‌شود: %s" % _b[:34], "")
    ck(chart.count('"last": p_last if p_last > 0 else p_close') == 0,
       "NEGATIVE CONTROL: کندلِ زنده دیگر lastِ نبود را با پایانی پر نمی‌کند", "")
    ck('r(cl * k), "last": r(cl * k)' in chart,
       "استثنایِ ثبت‌شدۀ قدمِ ۵: `_fts_scaled` هنوز last را از close می‌سازد "
       "(موتورِ FTS درِ #73 معوق است — گزارشِ قدمِ ۳)", "")

    # ── ۵) bank-level: two series endpoints with the real columns ────────────
    print("\n[۵] مسیرِ بانک (کپیِ موقت)")
    fd, dbp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(dbp)
    conn.execute("CREATE TABLE price_history (symbol TEXT, date TEXT, open REAL, high REAL,"
                 " low REAL, close REAL, volume REAL, last REAL, value REAL,"
                 " PRIMARY KEY (symbol, date))")
    conn.execute("CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT, l_val30 TEXT)")
    conn.execute("CREATE TABLE market_watch (ins_code TEXT, d_even INTEGER, price_first REAL,"
                 " price_max REAL, price_min REAL, p_closing REAL, q_tot_tran REAL, p_last REAL)")
    rows = [("فولاد", d, 1000.0 + i * 10, 1060.0 + i * 10, 980.0 + i * 10, 1040.0 + i * 10,
             1e9, 1035.0 + i * 10, 5e12) for i, d in
            enumerate(["2024-01-0%d" % (i + 1) for i in range(9)])]
    conn.executemany("INSERT INTO price_history VALUES (?,?,?,?,?,?,?,?,?)", rows)
    conn.execute("INSERT INTO instruments VALUES ('X','فولاد','فولاد')")
    conn.commit(); conn.close()
    import test_tsetmc
    real_db = test_tsetmc.DB_PATH
    for mod in ("api.chart", "api._core"):
        __import__(mod)
    import api._core as CORE
    test_tsetmc.DB_PATH = dbp
    CH.DB_PATH = dbp
    CORE.DB_PATH = dbp
    try:
        price_basis.set_basis("last")
        r1 = CH.get_chart_db("فولاد")
        price_basis.set_basis("closing")
        r2 = CH.get_chart_db("فولاد")
        c1 = {c["time"]: c for c in r1["candles"]}
        c2 = {c["time"]: c for c in r2["candles"]}
        ck(r1.get("priceBasis") == "last" and r2.get("priceBasis") == "closing",
           "/api/chart-db مبنایِ هر دو حالت را درِ پاسخ اعلام می‌کند",
           "%s | %s" % (r1.get("priceBasis"), r2.get("priceBasis")))
        ck(all(c1[t]["close"] == 1035.0 + 10 * i for i, t in enumerate(sorted(c1))),
           "درِ last، closeِ payload == ستونِ lastِ بانک", str([c1[t]["close"] for t in sorted(c1)][:3]))
        ck(all(c2[t]["close"] == c1[t]["closing"] for t in c1),
           "درِ closing، closeِ payload == همان closingِ حالتِ قبل (لنگر یکی است)", "")
        ck(r1.get("adjustEvents") == r2.get("adjustEvents") == [],
           "رویدادهایِ تعدیل درِ بانکِ محلی تحتِ دو مبنای یکی‌اند (هر دو خالی)",
           "%s vs %s" % (r1.get("adjustEvents"), r2.get("adjustEvents")))
        ck(r1.get("factors") == r2.get("factors"),
           "ضرایبِ /api/chart-db تحتِ دو مبنای یکسان‌اند", "")
        price_basis.set_basis("last")
    finally:
        test_tsetmc.DB_PATH = real_db
        CH.DB_PATH = real_db
        CORE.DB_PATH = real_db
        os.unlink(dbp)

    bors_config.PRICE_BASIS_PATH = real_path
    price_basis._cache["sig"] = None
    print(f"\nprice_basis_v1070: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
