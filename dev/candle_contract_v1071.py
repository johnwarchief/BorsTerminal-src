#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/candle_contract_v1071.py — یکِ ردیفِ یکسان، یکِ کندل؛ تابلو سطرِ منتشرشده را له نمی‌کند.

چرا این گارد متولد شد (Step 4 کارِ #73، ۱۴۰۵-۰۷-۱۲). واگرایی پیش از این **اندازه** گرفته
شد، نه حدس (`_audit/candle_builder_divergence.py`،
`_audit/candle_source_priority_probe.py`، `_audit/legacy_open_basis.json`):

  • از ۱٬۱۹۵ روزِ مشترکِ «کندلِ RAMِ /api/chart» ⇄ «/api/chart-db»: open در ۳۰۴ روز،
    high در ۷۶، low در ۱۰۹، close در ۳ روز فرق داشت. مصرف‌کننده‌ها (غربگر/اطمینان)
    رویِ OHLC واگرایی نداشتند ⇒ مشکل درِ **ساخت** بود، نه خواندن.
  • ۴۷۰ از ۱٬۲۷۲ ردیفِ بانک (۳۷٪) open‌شان قیمتِ *پایه* بود نه «اولین» — و همه درِ یکِ
    نماد (شبندر ۴۷۰/۴۸۱؛ فولاد و خگستر صفر). یعنی مبنایِ open نماد‌به‌نماد به این
    بستگی داشت که کدامِ نویسندۀ آخر نوشته باشد.
  • از ۷۲ نشستِ مشترکِ تابلو/CSV، ۴ نشست (همه ۲۰۲۶-۰۹-۰۱) snapshotِ میانهٔ تابلو را
    رویِ ردیفِ **منتشرشده** نشانده بود، و ۸ روزِ «شبح» درِ بانک بود که درِ فهرستِ
    منتشرشده هیچ‌وقت نبودند.
  • هندسه چهار پیاده داشت: سه‌تایِ «گِشاد» (parser، candle_from_row، normalize_geometry) و
    یکی «clamp» (شاخصِ کل) که قیمتِ ساختگی را جابه‌جا می‌کرد.

پاسخِ این‌ها درِ `candle_contract.py` است و این فایل همان را می‌بندد. بی‌شبکه و
بی‌market.dbِ واقعی. اجرا:  python dev/candle_contract_v1071.py   → ۰ سبز، ۱ قرمز
"""
import io
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import candle_contract as K  # noqa: E402
import test_tsetmc as t  # noqa: E402

PASS = FAIL = 0

CSV_ROW = "<X>,20260901,2820,2855,2790,2751,5.6e12,1.9e9,0,100.0,2669,2800"
# همان روز از تابلو: price_first=2820، max/min/p_closing/qTotTran/qTotCapِ برابر
BOARD_ROW = dict(l_val18="فولاد", d_even=20260901, first=2820.0, high=2855.0, low=2790.0,
                 closing=2751.0, vol=1.9e9, last=2800.0, value=5.6e12)


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   " + what)
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  ← {detail}" if detail else ""))


def new_db():
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    c = sqlite3.connect(p)
    t.create_schema(c)
    c.execute("INSERT INTO instruments (ins_code, l_val18, l_val30) VALUES ('1','فولاد','فولاد')")
    c.commit()
    return c, p


def read(c, sym="فولاد"):
    """روز → دیکشنریِ ستون‌ها. برگرداندنِ tupleِ بی‌نام باعث شد خودِ همین گارد
    indexهایِ src را اشتباه بگیرد (row[5]=last نبود src)؛ پس نام‌دار خوانده می‌شود."""
    cols = ("date", "open", "high", "low", "close", "volume", "last", "value", "src")
    return {r[0]: dict(zip(cols[1:], r[1:])) for r in c.execute(
        "SELECT %s FROM price_history WHERE symbol=? ORDER BY date" % ", ".join(cols), (sym,))}


def main():
    print("candle_contract_v1071")

    # ── ۱) سه منبع، یکِ کندل ─────────────────────────────────────────────────
    print("\n[۱] هم‌شکلیِ سازنده‌ها")
    from_csv = K.from_csv_row("فولاد", CSV_ROW.split(","))
    from_board = K.from_board_row(BOARD_ROW["l_val18"], BOARD_ROW["d_even"],
                                  BOARD_ROW["first"], BOARD_ROW["high"], BOARD_ROW["low"],
                                  BOARD_ROW["closing"], BOARD_ROW["vol"], BOARD_ROW["last"],
                                  BOARD_ROW["value"])
    fields = ("open", "high", "low", "close", "last", "value", "volume")
    ck(from_csv and from_board and all(from_csv[f] == from_board[f] for f in fields),
       "ردیفِ CSV و ردیفِ تابلو برایِ یکِ روز، کندلِ عددبهعدد یکسان می‌سازند",
       str(({f: from_csv[f] for f in fields}, {f: from_board[f] for f in fields}))[:220])
    ck(from_csv["src"] == K.SRC_PUBLISHED and from_board["src"] == K.SRC_BOARD,
       "منبعِ هر سطر ثبت می‌شود (published | board)",
       "%s | %s" % (from_csv["src"], from_board["src"]))
    db = K.from_db_row(("فولاد", "2026-09-01", from_csv["open"], from_csv["high"],
                        from_csv["low"], from_csv["close"], from_csv["volume"],
                        from_csv["last"], from_csv["value"], K.SRC_PUBLISHED))
    ck(all(db[f] == from_csv[f] for f in fields),
       "خواندنِ همان سطر از بانک هم همان اعداد را می‌دهد (no read-side reshaping)",
       str({f: (db[f], from_csv[f]) for f in fields if db[f] != from_csv[f]})[:160])

    # ── ۲) تنها قاعدۀ هندسه ─────────────────────────────────────────────────
    print("\n[۲] هندسه")
    ck(K.widen(1200, 1100, 0, 1150) == (1200, 1150),
       "highِ بی‌اعتبار کفِ بدنه نمی‌شود؛ کف از بدنه ساخته می‌شود (پالایش ۲۰۲۴-۱۰-۲۳)",
       str(K.widen(1200, 1100, 0, 1150)))
    ck(K.widen(1973, 1973, 1973, 1917) == (1973, 1917),
       "پایانیِ زیرِ low ⇒ سایه باز می‌شود، پایانی خُرد نمی‌ماند (فولاد ۲۰۰-۱۲-۲۲)",
       str(K.widen(1973, 1973, 1973, 1917)))
    ck(K.widen(3520, 3520, 3450, 3520, 3600) == (3600, 3450),
       "lastِ بیرونِ بازه ⇒ سقف باز می‌شود (قیمتِ منتخب جابه‌جا نمی‌شود)",
       str(K.widen(3520, 3520, 3450, 3520, 3600)))
    ck(K.candle("x", "2026-09-01", 100, 110, 90, 105, 0) is None,
       "NEGATIVE CONTROL: روزِ بی‌معامله کندل نمی‌شود (کندلِ شبحِ ۱۴۰۵-۰۷-۰۸)", "")
    ck(K.candle("x", "2026-09-01", 100, 110, 90, 0) is None,
       "بی‌پایانیِ معتبر ⇒ هیچ کندلی، نه کندلِ نصفه", "")
    for f in ("api/chart.py", "test_tsetmc.py", os.path.join("tools", "backfill_daily_history.py"),
              os.path.join("api", "market_index.py")):
        src = io.open(os.path.join(ROOT, f), encoding="utf-8").read()
        dbl = ("max(hi, lo, o, c)" in src) or ("h = max(h, o, c)" in src) or ("min(max(o, l), h)" in src)
        ck(not dbl and ("candle_contract.widen(" in src or f.endswith("backfill_daily_history.py")),
           "%s: پیادۀ دومِ هندسه نمانده" % f, "")

    # ── ۳) مالکیتِ سطر: published بر board ──────────────────────────────────
    print("\n[۳] اولویتِ نوشتن")
    c, p = new_db()
    c.execute(K.UPSERT_SQL, K.upsert_row(from_csv)); c.commit()
    stale = K.from_board_row("فولاد", 20260901, 2669, 2669, 2669, 2669, 1.8e9)  # اسنپشاتِ بد
    c.execute(K.UPSERT_SQL, K.upsert_row(stale)); c.commit()
    row = read(c)["2026-09-01"]
    ck(row["open"] == 2820.0 and row["src"] == K.SRC_PUBLISHED,
       "board ردیفِ منتشرشده را بازنویسی نکرد (open همان FIRST ماند)", str(row))
    # روزی که فقط تابلویش داریم: board می‌نویسد
    b2 = K.from_board_row("فولاد", 20260902, 2700, 2760, 2680, 2740, 1.9e9)
    c.execute(K.UPSERT_SQL, K.upsert_row(b2)); c.commit()
    ck("2026-09-02" in read(c) and read(c)["2026-09-02"]["src"] == K.SRC_BOARD,
       "برایِ روزی که هنوز منتشر نشده، board سطر می‌سازد (کندلِ امروز جا نمی‌افتد)",
       str(read(c).get("2026-09-02")))
    # و بعد از انتشار، published جایش می‌نشیند
    pub2 = K.candle("فولاد", "2026-09-02", 2700, 2760, 2680, 2745, 1.95e9, 2755, 6.1e12)
    c.execute(K.UPSERT_SQL, K.upsert_row(pub2)); c.commit()
    ck(read(c)["2026-09-02"]["src"] == K.SRC_PUBLISHED
       and read(c)["2026-09-02"]["close"] == 2745.0,
       "published بعداً حقِّ بازنویسیِ board را دارد", str(read(c)["2026-09-02"]))
    n_before = c.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    for _ in range(3):
        c.execute(K.UPSERT_SQL, K.upsert_row(from_csv)); c.commit()
    ck(c.execute("SELECT COUNT(*) FROM price_history").fetchone()[0] == n_before,
       "NEGATIVE CONTROL: سه نوشتنِ پیاپیِ یکِ سطر سطرِ دوم نمی‌سازد", "")
    c.close(); os.unlink(p)

    # ── ۴) مسیرهایِ واقعی از همان قرارداد می‌گذرند ──────────────────────────
    print("\n[۴] سیم‌کشی")
    ts = io.open(os.path.join(ROOT, "test_tsetmc.py"), encoding="utf-8").read()
    body = ts[ts.index("def fetch_price_history"):ts.index("def update_existing")]
    ck("candle_contract.from_csv_row(" in body and "candle_contract.UPSERT_SQL" in body,
       "مسیرِ CSV از from_csv_row + UPSERTِ اولویت‌دار می‌گذرد", "")
    cf = ts[ts.index("def candle_from_row"):ts.index("def sync_price_history_from_daily")]
    ck("candle_contract.from_board_row(" in cf and "max(h, o, c)" not in cf,
       "مسیرِ تابلو هم همان قرارداد است، نه قاعدۀ دوم", "")
    ng = ts[ts.index("def normalize_price_history_geometry"):ts.index("def _history_start")]
    ck("candle_contract.widen(" in ng, "نرمال‌سازِ هندسه از همان widen می‌خواند", "")
    mig = io.open(os.path.join(ROOT, "mstat_engine.py"), encoding="utf-8").read()
    ck('"src", "TEXT"' in mig, "src درِ منبعِ یکتای مهاجرت (MIGRATIONS) تعریف شده", "")
    for f in ("test_tsetmc.py", os.path.join("codal_fetcher.py")):
        s2 = io.open(os.path.join(ROOT, f), encoding="utf-8").read()
        ck("src TEXT" in s2, "%s: DDLِ تازه هم src دارد" % f, "")

    print(f"\ncandle_contract_v1071: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
