# -*- coding: utf-8 -*-
"""dev/sidebar_market_fields_v1082.py — Stage-2 «در یک نگاه»: سه قیمت + عمقِ هدفمند

اجرا:  python dev/sidebar_market_fields_v1082.py   [BENCH_DB=<bank>]

دو بخش، هردو رویِ دادهٔ واقعی یا فیکسچرِ کنترل‌شده — نه بازتابِ خودِ UI:

  A) رویِ بانکِ واقعی (BENCH_DB یا market.db کنارِ EXE):
     • `/api/market` سه کلیدِ `p_first`/`p_max`/`p_min` را می‌فرستد و هر سه با
       ستونِ واقعیِ `market_watch` (price_first/price_max/price_min) می‌خواند؛
       هیچ «قیمتِ جایگزین» یا محاسبهٔ حدسی درِ مسیر نیست.
     • بدنه عمقِ پنج‌سطحی هیچ نمادی را شامل نمی‌شود (آرایۀ سطرها هرگز درِ
       تابلو نمی‌آید) — مصرفِ تنبل، نه fan-out.
  B) رویِ مرزهایِ کنترل‌شده (که بانکِ واقعی ثابتشان نمی‌کند):
     • `_slim_records`: نبودِ مقدارِ float ⇒ کلید حذف، نه صفر و نه جایگزین.
     • `/api/order-book`: پنج سطحِ *همان* نماد؛ دفترِ یک نماد به نمادِ دیگر
       نمی‌چسبد؛ نمادِ نامعتبر ⇒ no_data/error نه دفترِ صفرشدهٔ ساختگی.

بانک واقعی هرگز نوشته نمی‌شود: A رویِ کپیِ read-copy.
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return cond


class Req:
    headers = {}


# ════════════════════════════════════════════════════════════════════════════
# A) بانکِ واقعی — سه قیمت از ستونِ واقعی، بی‌نشتِ عمق درِ تابلو
# ════════════════════════════════════════════════════════════════════════════
def part_a():
    src = os.environ.get("BENCH_DB") or os.path.join(ROOT, "market.db")
    if not os.path.exists(src):
        ck(False, "A: market.db برایِ سنجشِ واقعی پیدا نشد (%s) — این بخش اثبات‌نشده ماند" % src)
        return
    tmp = os.path.join(tempfile.mkdtemp(prefix="sb2_a_"), "bench.db")
    shutil.copy2(src, tmp)   # خودِ فایلِ بانک هرگز بازِ نوشتن نمی‌شود
    import bors_config
    import api._core as core
    bors_config.DB_PATH = tmp
    core.DB_PATH = tmp
    import api.market as M
    M.get_db = lambda: sqlite3.connect(tmp, timeout=30)
    import api.chart as CH
    CH.DB_PATH = tmp

    out = M._build_market_response(Req())
    body = out.body if isinstance(out.body, (bytes, bytearray)) else out.body.encode()
    d = json.loads(body.decode("utf-8"))
    by_code = {r["ins_code"]: r for r in d["data"]}

    c = sqlite3.connect(tmp)
    c.row_factory = sqlite3.Row
    sample = c.execute(
        "SELECT m.ins_code, m.price_first, m.price_max, m.price_min"
        " FROM market_watch m WHERE m.price_first>0 AND m.price_max>m.price_min"
        " LIMIT 8").fetchall()
    ck(len(sample) >= 3, "A: حداقلِ سه نمادِ نمونه با max>min پیدا شد (%d)" % len(sample))

    all_ok, mismatch = True, []
    for r in sample:
        row = by_code.get(r["ins_code"]) or {}
        if not (row.get("p_first") == r["price_first"] and row.get("p_max") == r["price_max"]
                and row.get("p_min") == r["price_min"]):
            all_ok = False
            mismatch.append((r["ins_code"], row.get("p_first"), r["price_first"]))
    ck(all_ok, "A: p_first/p_max/p_min درِ بدنه = ستونِ واقعیِ market_watch (%s)" % (mismatch[:2] or "بدونِ واگرایی"))

    # نبودِ عمقِ پنج‌سطحی درِ تابلو: هیچ ردیفی فهرستِ سطرها را ندارد
    depth_leak = [r for r in d["data"] if isinstance(r.get("levels"), list)
                  or "book_txt" in r or any(isinstance(v, list) for v in r.values())]
    ck(not depth_leak, "A: بدنهٔ /api/market عمقِ پنج‌سطحی هیچ نمادی را نمی‌فرستد (%d نشت)" % len(depth_leak))

    # ── order-book رویِ همان snapshot: پنج سطحِ *همان* نماد، بی‌مخلوطی ──
    two = c.execute(
        "SELECT i.l_val18 sym, b.book_txt FROM order_book b"
        " JOIN instruments i ON i.ins_code=b.ins_code"
        " WHERE b.book_txt NOT NULL AND json_array_length(b.book_txt)>=5 LIMIT 2").fetchall()
    c.close()
    if len(two) == 2:
        res0 = CH.get_order_book(two[0]["sym"])
        res1 = CH.get_order_book(two[1]["sym"])
        ck(res0["status"] == "ok" and len(res0["levels"]) >= 5,
           "A: order-book نمادِ نخست پنج سطح برگشت (status=%s n=%d)"
           % (res0["status"], len(res0["levels"])))
        top0 = json.loads(two[0]["book_txt"])[0]
        lvl0 = res0["levels"][0]
        ck(lvl0["buy_px"] == top0[0] and lvl0["sell_px"] == top0[3],
           "A: سطرِ اولِ دفتر = سطرِ اولِ book_txt همان نماد (بی‌دادهٔ ساختگی)")
        ck(res0["symbol"] != res1["symbol"] or res0["levels"][0]["buy_px"] == res1["levels"][0]["buy_px"],
           "A: پاسخِ هر دو برایِ نمادِ خودش است (هویتِ نماد حمل می‌شود)")


# ════════════════════════════════════════════════════════════════════════════
# B) مرزهایِ کنترل‌شده — نبودِ مقدار درِ سریال‌سازی و تطابقِ نماد درِ دفتر
# ════════════════════════════════════════════════════════════════════════════
def part_b_records():
    import numpy as np
    import pandas as pd
    import api.market as M
    df = pd.DataFrame(
        {"p_first": [1045.0, np.nan], "p_max": [1080.0, np.nan],
         "p_min": [1040.0, np.nan], "p_last": [1060.0, 2010.0]},
        index=["A1", "A2"])
    a1, a2 = M._slim_records(df, drop_unused=True)
    ck(a1.get("p_first") == 1045.0 and a1.get("p_max") == 1080.0 and a1.get("p_min") == 1040.0,
       "B: ردیفِ کامل، سه قیمتِ روزانه را با مقدارِ خود می‌فرستد")
    ck("p_first" not in a2 and "p_max" not in a2 and "p_min" not in a2,
       "B: NaN ⇒ کلید نمی‌آید؛ با صفر یا آخرین پر نمی‌شود (%s)"
       % sorted(k for k in a2 if k.startswith("p_")))
    ck(a2.get("p_last") == 2010.0,
       "B: نبودِ یک قیمت، بقیهٔ ردیف را نمی‌کُشد (p_lastِ خودش می‌ماند)")


def _seed_orderbook_file(path):
    c = sqlite3.connect(path)
    c.executescript("""
    CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT,
        sector_name TEXT, sector_code TEXT, updated_at TEXT);
    CREATE TABLE market_watch (ins_code TEXT PRIMARY KEY, d_even INTEGER, h_even INTEGER,
        p_closing REAL, p_last REAL, price_min REAL, price_max REAL, price_first REAL,
        buy_q_vol REAL, buy_q_cnt REAL, sell_q_vol REAL, sell_q_cnt REAL);
    CREATE TABLE order_book (ins_code TEXT PRIMARY KEY, book_txt TEXT, d_even INTEGER,
        h_even INTEGER, updated_at TEXT);
    """)
    five = lambda base: json.dumps([[base - i, 100 + i, 1, base + 500 + i, 90 + i, 1]
                                    for i in range(5)])
    c.execute("INSERT INTO instruments VALUES ('A1','تستیک','شرکت تستیک','صنعت۱','S','2026-10-07')")
    c.execute("INSERT INTO instruments VALUES ('A2','خالی','شرکت خالی','صنعت۲','S','2026-10-07')")
    c.execute("INSERT INTO order_book VALUES ('A1',?,20261007,110000,'2026-10-07 11:00:00')",
              (five(1060),))
    c.execute("INSERT INTO order_book VALUES ('A2',?,20261007,110000,'2026-10-07 11:00:00')",
              (five(2010),))
    c.commit()
    c.close()


def part_b_orderbook():
    import api.chart as CH
    tmp = os.path.join(tempfile.mkdtemp(prefix="sb2_b_"), "ob.db")
    _seed_orderbook_file(tmp)
    CH.DB_PATH = tmp

    r1 = CH.get_order_book("تستیک")
    r2 = CH.get_order_book("خالی")
    ck(r1["status"] == "ok" and len(r1.get("levels", [])) == 5,
       "B: دفترِ «تستیک» پنج سطح برگشت (n=%d)" % len(r1.get("levels", [])))
    ck(r1["levels"][0]["buy_px"] == 1060, "B: سطرِ اولِ دفترِ تستیک = ۱٬۰۶۰ (مبدأِ همان نماد)")
    ck(r2["levels"][0]["buy_px"] == 2010, "B: سطرِ اولِ دفترِ خالی = ۲٬۰۱۰ (نه دفترِ همسایه)")
    ck(r1["levels"][0]["buy_px"] != r2["levels"][0]["buy_px"],
       "B: دو نماد دو دفترِ جدا دارند — هیچ‌کدام به دیگری نسبت نمی‌خورد")

    rbad = CH.get_order_book("نماد_وجود_ندارد")
    ck(rbad["status"] in ("no_data", "error") and not rbad.get("levels"),
       "B: نمادِ نامعتبر ⇒ no_data/error با صفرِ سطر (نه دفترِ ساختگی) [%s]" % rbad["status"])


def main():
    part_a()
    part_b_records()
    part_b_orderbook()
    failed = 0
    for ok, msg in CHECKS:
        print(("  ok   " if ok else "  FAIL ") + msg)
        if not ok:
            failed += 1
    print("\nsidebar_market_fields_v1082: %d passed / %d failed"
          % (len(CHECKS) - failed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
