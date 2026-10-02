# -*- coding: utf-8 -*-
"""dev/test_fts_results_materialize.py — تسک ۱۹: مادی‌سازی fts_results (پایانِ N+1)

قراردادِ آزمون (تصمیم ۴ — همان sector_of/market_cap_at):
  * نویسنده در dev/codal_fts_updater.sync_fts_results، خواننده در
    fts_engine.fts_results_of/bulk با fallback به evaluate_v10 زنده.
  * جدول غایب/خالی، cfg_hash ناهم‌خوان، یا نمادِ غایب → None → مسیرِ زنده.
    یعنی یک DB قدیمی/خالی دقیقاً همان رفتارِ قبلی را دارد (رفتارِ v8 اسکرینر
    دست‌نخورده می‌ماند).

این پروب روی یک DB ساختگی (همان سبکِ test_fts_market_cap.py) چهار چیز را
اثبات می‌کند:
  ۱) writer با ۲۷ ستون/۲۷ placeholder می‌نشیند (باگِ ۲۸→۲۷ دیگر برنمی‌گردد).
  ۲) خروجیِ خواننده برای هر نماد **دقیقاً** همان evaluate_v10 زنده است
     (score / verdict / excluded / ۹ پرچم / ۵ مقدار).
  ۳) fallback: جدول غایب، جدول خالی، cfg_hash ناهم‌خوان، نمادِ غایب → None.
  ۴) invalidate_fts_results کشِ خواننده را کثیف می‌کند (ردیفِ تازه دیده می‌شود).

اجرا:  python dev/test_fts_results_materialize.py     (بدون سرور، بدون شبکه)
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

try:                       # پیامهای فارسی روی کنسولِ cp1252 ویندوز
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import codal_fetcher as cf            # noqa: E402  (create_schema/migrate_schema)
import codal_periods as CP            # noqa: E402  (ترتیبِ «تازه‌ترین دورۀ اول»)
import fts_engine                     # noqa: E402  (خواننده + norm_fa)
from api import fundamental as FD     # noqa: E402  (evaluate_v10 زنده)

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return cond


# ═══════════════════════════════════════════════════════════════════════════
#  DB ساختگی — سه شرکت با دادهٔ کافی برای همهٔ ۵ شاخص
# ═══════════════════════════════════════════════════════════════════════════
#  · فولاد  : تولیدی قوی — رشد ۱۰۰٪، حاشیه ۳۵٪، EPS صعودی، فروش÷ارزش ۰٫۶
#  · شبندر  : تولیدی متوسط — رشد ۲۰٪ (زیر آستانه) → شاخص ۱ مردود
#  * داروک  : دارویی — برای تنوعِ profile و industry_gate
#
#  ماهانه: ۱۲ ماه از سال ۱۴۰۴ + ۱۲ ماه از ۱۴۰۳ (برای مخرجِ YoY و پهنای رشد).
#  سالانه : ۱۴۰۲/۱۴۰۳/۱۴۰۴ حسابرسی‌شده غیرتلفیقی (برای EPS ۳ساله و حاشیه).
#  market_watch.market_cap ستونِ رسمیِ تابلوست (قاعدهٔ v10: فقط همان خوانده می‌شود).

# جداولِ TSETMC (instruments/market_watch/daily_prices) توسطِ create_schemaِ
# کدال ساخته نمیشوند — اینها جدولهای سمتِ بورس هستند. همان DDLِ
# test_fts_market_cap.py، به‌علاوهٔ ستونهای رسمیِ ارزش بازار.
_TSETMC_DDL = """
CREATE TABLE instruments (
    ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT, sector_code TEXT,
    sector_name TEXT, total_shares REAL, eps REAL, pe REAL, base_vol REAL,
    updated_at TEXT, paper_type INTEGER);
CREATE TABLE market_watch (
    ins_code TEXT PRIMARY KEY, d_even INTEGER, h_even INTEGER, p_closing REAL,
    p_last REAL, price_min REAL, price_max REAL, allowed_min REAL, allowed_max REAL,
    price_yesterday REAL, price_first REAL, q_tot_tran REAL, q_tot_cap REAL,
    z_tot_tran REAL, price_change REAL, eps REAL, pe REAL, total_shares REAL,
    sector_code TEXT, fetched_at TEXT, market_cap REAL, market_cap_src TEXT);
CREATE TABLE daily_prices (
    ins_code TEXT, d_even INTEGER, p_closing REAL, price_min REAL, price_max REAL,
    price_yesterday REAL, price_first REAL, q_tot_tran REAL, q_tot_cap REAL,
    price_change REAL, fetched_at TEXT, PRIMARY KEY (ins_code, d_even));
"""


def make_db():
    path = os.path.join(tempfile.mkdtemp(prefix="ftsmat_"), "market.db")
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(_TSETMC_DDL)
    cf.create_schema(con)
    cf.migrate_schema(con)          # افزودنی: fts_results + ستونهای volume/derived

    # ── instruments + market_watch (ارزش بازارِ رسمی) ──────────────────
    con.executemany(
        "INSERT INTO instruments (ins_code,l_val18,l_val30,sector_code,sector_name,"
        "total_shares,eps,pe,base_vol,updated_at,paper_type) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [("I1", "فولاد", "فولاد مبارکه", "1", "فلزات اساسی", 1000000.0, 500, 10, 1,
          "2026-09-09", 1),
         ("I2", "شبندر", "پتروشیمی بندر", "2", "شیمیایی", 2000000.0, 300, 8, 1,
          "2026-09-09", 1),
         ("I3", "داروک", "دارویی داروک", "3", "دارو", 4000000.0, 900, 12, 1,
          "2026-09-09", 1)])
    # ۱ همت = ۱e13 ریال. فولاد ۲ همت، شبندر ۱ همت، داروک ۰٫۵ همت.
    con.executemany(
        "INSERT INTO market_watch (ins_code,d_even,p_closing,total_shares,sector_code,"
        "market_cap,market_cap_src) VALUES (?,?,?,?,?,?,?)",
        [("I1", 20260909, 2881.0, 1000000.0, "1", 2.0e13, "tse_raw"),
         ("I2", 20260909, 13920.0, 2000000.0, "2", 1.0e13, "tse_raw"),
         ("I3", 20260909, 9100.0, 4000000.0, "3", 5.0e12, "tse_raw")])
    # bulk_scan نشست‌های معاملاتی را از daily_prices می‌خواند (فیلترِ نمادِ
    # تعلیق‌شده) و avg_trade_value_hmt هم از همین جدول است.
    con.executemany(
        "INSERT INTO daily_prices (ins_code,d_even,p_closing,q_tot_cap) VALUES (?,?,?,?)",
        [("I1", 20260909, 2881.0, 2.0e13), ("I2", 20260909, 13920.0, 1.0e13),
         ("I3", 20260909, 9100.0, 5.0e12)])

    # ── monthly_sales: ۱۲ ماه ۱۴۰۴ + ۱۲ ماه ۱۴۰۳ برای هر نماد ─────────
    #  فولاد: ۱۴۰۴ تجمیعیِ ماهِ m = ۱۰۰۰e9 * m (یعنی ماهانه ثابت ۱۰۰۰ میلیارد)
    #          ۱۴۰۳ تجمیعیِ ماهِ m =  ۵۰۰e9 * m  → رشد = ۱۰۰٪
    #  شبندر: ۱۴۰۴ =  ۶۰۰e9 * m ، ۱۴۰۳ =  ۵۰۰e9 * m → رشد = ۲۰٪ (زیر ۶۰٪)
    #  داروک: ۱۴۰۴ =  ۳۰۰e9 * m ، ۱۴۰۳ =  ۲۰۰e9 * m → رشد = ۵۰٪
    plans = {"فولاد": (1000e9, 500e9), "شبندر": (600e9, 500e9), "داروک": (300e9, 200e9)}
    tn = 0
    for sym, (cur_m, prv_m) in plans.items():
        # (سال, ماهانهٔ این سال, ماهانهٔ سال قبل) — ytd_revenue_prev باید تجمیعیِ
        # همان دوره از سالِ قبل باشد، نه تکرارِ تجمیعیِ همین سال (وگرنه رشد = ۰٪).
        for year, per_m, prev_per_m in ((1404, cur_m, prv_m),
                                       (1403, prv_m, prv_m * 0.5)):
            for m in range(1, 13):
                tn += 1
                con.execute(
                    "INSERT INTO monthly_sales (tracing_no,symbol,title,period_end,year,month,"
                    "monthly_revenue,ytd_revenue,ytd_revenue_prev,pdf_url,excel_url) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (tn, sym, "گزارش فعالیت ماهانه", "1404/12/29", year, m,
                     per_m, per_m * m, prev_per_m * m, None, None))

    # ── financial_statements: ۳ سال حسابرسی‌شده غیرتلفیقی ───────────────
    #  فولاد: درآمد ۴۰۰۰ میلیارد، ناخالص ۳۵٪، EPS ۵۰۰→۶۰۰→۷۰۰ (صعودی)
    #  شبندر: درآمد ۳۰۰۰ میلیارد، ناخالص ۱۸٪ (زیر ۲۰٪)، EPS نزولی
    #  داروک: درآمد ۱۲۰۰ میلیارد، ناخالص ۵۵٪، EPS صعودی
    fs_plans = {
        "فولاد": [(1402, 4000e9, 0.35, 500.0), (1403, 4000e9, 0.35, 600.0),
                  (1404, 4000e9, 0.35, 700.0)],
        "شبندر": [(1402, 3000e9, 0.18, 400.0), (1403, 3000e9, 0.18, 350.0),
                  (1404, 3000e9, 0.18, 300.0)],
        "داروک": [(1402, 1200e9, 0.55, 900.0), (1403, 1200e9, 0.55, 1000.0),
                  (1404, 1200e9, 0.55, 1100.0)],
    }
    tn = 0
    for sym, rows in fs_plans.items():
        for fy, rev, gm_ratio, eps in rows:
            tn += 1
            _fs_cols = ("tracing_no,symbol,company_name,title,report_kind,"
                        "period_months,period_end,publish_date,revenue,gross_profit,"
                        "operating_profit,net_profit,total_assets,total_liabilities,"
                        "total_equity,capital,retained_earnings,basic_eps,unit,url,"
                        "fetched_at,is_audited,is_consolidated,fiscal_year,unit_norm")
            _fs_vals = (tn, sym, sym, "صورت مالی 12 ماهه حسابرسی شده غيرتلفيقي",
                        "annual", 12, "%d/12/29" % fy, "2026-04-01", rev,
                        rev * gm_ratio, rev * gm_ratio * 0.8, rev * gm_ratio * 0.6,
                        500e9, 410e9, 90e9, 100e9, 40e9, eps, "mrl", None, "t",
                        1, 0, str(fy), "mrl")
            con.execute("INSERT INTO financial_statements (%s) VALUES (%s)"
                        % (_fs_cols, ",".join(["?"] * len(_fs_vals))), _fs_vals)
    con.commit()
    return path, con


def cfg_hash_of(cfg):
    """همان فرمولِ نویسنده و اسکرینر — تا قراردادِ یکپارچگی دقیق سنجیده شود."""
    return json.dumps(cfg or {}, sort_keys=True, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════════════
#  ۱) writer: ۲۷ ستون، ۲۷ placeholder، یک تراکنش
# ═══════════════════════════════════════════════════════════════════════════
import codal_fts_updater as UPD          # noqa: E402  (نویسنده)


def _absent_db(ch):
    """۴) جدولِ غایب/ناقص = همان رفتارِ قبلی (یک DB قبل از مهاجرت).

    تابعِ جداگانه تا بتوان آن را مستقل از بدنهٔ اصلیِ آزمون فراخواند و
    پاکسازیِ دایرکتوریِ موقتِ خودش را خودش انجام دهد.
    """
    path2, con2 = make_db()
    try:
        con2.execute("DROP TABLE fts_results")
        con2.commit()
        fts_engine._FTS_RESULTS_CACHE.pop(id(con2), None)
        ck(fts_engine.fts_results_bulk(con2, cfg_hash=ch) is None,
           "absent table → None → the screener runs its exact pre-existing live path")
        ck(fts_engine.fts_results_of(con2, "فولاد", cfg_hash=ch) is None,
           "absent table → None for the single-symbol reader too")
        # و خواننده با یک جدولِ ناقص (فقط ستونهای پایه، بدون ستونهای افزودنی)
        con2.execute("CREATE TABLE fts_results (symbol TEXT PRIMARY KEY, score INTEGER, "
                     "verdict TEXT, computed_at TEXT)")
        con2.execute("INSERT INTO fts_results VALUES ('فولاد', 5, 'STRONG', 't')")
        con2.commit()
        fts_engine._FTS_RESULTS_CACHE.pop(id(con2), None)
        ck(fts_engine.fts_results_bulk(con2, cfg_hash=ch) is None,
           "a legacy pre-additive-column table → None, not a crash (reader is defensive)")
    finally:
        con2.close()
        shutil.rmtree(os.path.dirname(path2), ignore_errors=True)


def _run_checks():
    """بدنهٔ آزمون — داخلِ یک تابع تا make_db بتواند از بیرون import شود."""

ck(UPD._FTSR_COLS.count(",") == 26 and UPD._FTSR_COLS.strip().count(" ") >= 0,
   "_FTSR_COLS has 27 column names (commas+1)")
ck(UPD._FTSR_PLACE == ",".join(["?"] * 27),
   "_FTSR_PLACE has 27 placeholders matching the 27 columns (was 28 — bug fixed)")
ck(UPD._FTSR_UPSERT.count("?") == 27,
   "the upsert statement binds exactly 27 values (SQLite column-count check)")

path, con = make_db()
try:
    cfg = FD.v10_thresholds()                      # یک cfg واقعی از همان مسیرِ پنل
    _rc = 1
    full_cfg = {"industry_mode": "Rank_Only"}      # فیلتر صنعت خنثی تا همه عبور کنند
    ch = cfg_hash_of(full_cfg)

    ctx, total_mcap = UPD.local_market_ctx(con)
    ck(len(ctx) == 3, "local_market_ctx sees the 3 seeded symbols (%d)" % len(ctx))
    ck(total_mcap > 0, "total market cap is summed from the board (%s)" % total_mcap)

    n, ev = UPD.sync_fts_results(con, ctx, total_mcap, full_cfg, verbose=False)
    ck(n == 3 and ev == 3, "writer materialized all 3 symbols without error (n=%s ev=%s)"
       % (n, ev))

    cols = [r[1] for r in con.execute("PRAGMA table_info(fts_results)")]
    for c in ("symbol", "f01_growth_pct", "f01_pass", "f02_eps_series", "f02_pass",
              "f03_margin_pct", "f03_pass", "f04_ratio", "f04_pass", "f05_verdict",
              "f05_pass", "score", "verdict", "excluded", "exclusion_reasons",
              "i1a_pass", "i1b_pass", "i4a_pass", "i4b_pass", "rev_growth",
              "gross_margin", "sales_to_mcap", "profit_potential_pct",
              "annual_sales_bt", "annualize_months", "cfg_hash", "computed_at"):
        ck(c in cols, "fts_results has the additive column %r" % c)
    ck(con.execute("SELECT COUNT(*) FROM fts_results").fetchone()[0] == 3,
       "fts_results holds exactly the writer's rows (no stale leftovers)")
    ck(con.execute("SELECT COUNT(DISTINCT cfg_hash) FROM fts_results").fetchone()[0] == 1,
       "all rows share one cfg_hash (one transaction, one config)")
    ck(con.execute("SELECT cfg_hash FROM fts_results LIMIT 1").fetchone()[0] == ch,
       "stored cfg_hash is byte-identical to the screener's json.dumps formula")
    ck(all(r[0] and r[1] for r in con.execute(
        "SELECT symbol, computed_at FROM fts_results")),
       "symbol (the join key) and computed_at are never NULL")

    # ── ۲) خواننده = همان evaluate_v10 زنده (برای هر نماد، فیلد به فیلد) ──
    mcap_official = {}
    for l18, mc in con.execute("SELECT i.l_val18, m.market_cap FROM instruments i "
                               "JOIN market_watch m ON m.ins_code = i.ins_code"):
        k = fts_engine.norm_fa(l18)
        if k and k not in mcap_official:
            mcap_official[k] = FD._num(mc)
    _tot, _src = FD.board_total_market_cap(con)
    _m141m = fts_engine.m141_map(con)
    _liqm = fts_engine.avg_trade_value_hmt(con)
    cname_of = {}
    for sym, cn in con.execute("SELECT symbol, company_name FROM financial_statements "
                               "ORDER BY %s, tracing_no DESC" % CP.order_expr()):
        k = fts_engine.norm_fa(sym)
        if k and k not in cname_of:
            cname_of[k] = cn or ""

    def live(key, sector):
        return FD.evaluate_v10(con, key, mcap_official.get(key, 0.0), _tot, sector,
                               cfg=full_cfg, company_name=cname_of.get(key, ""),
                               m141_map=_m141m, liq_map=_liqm)

    bulk = fts_engine.fts_results_bulk(con, cfg_hash=ch)
    ck(bulk is not None and len(bulk) == 3,
       "fts_results_bulk returns the materialized map in one SELECT (%r)" %
       (None if bulk is None else len(bulk)))

    FIELDS = ("score", "verdict", "excluded", "pricing_mode")
    PASSES = ("1_growth", "2_eps_trend", "3_gross_margin", "4_sales_to_mcap",
              "5_industry", "1a_monetary_growth", "1b_volume_growth",
              "4a_sales_to_mcap", "4b_profit_potential")

    for key, sector in (("فولاد", "فلزات اساسی"), ("شبندر", "شیمیایی"),
                        ("داروک", "دارو")):
        mat = fts_engine.fts_results_of(con, key, cfg_hash=ch)
        ck(mat is not None, "fts_results_of(%r) resolves the row" % key)
        ref = live(key, sector)
        for f in FIELDS:
            ck(mat.get(f) == ref.get(f), "%s.%s identical to live (%r vs %r)"
               % (key, f, mat.get(f), ref.get(f)))
        mp, rp = mat.get("passes") or {}, ref.get("passes") or {}
        for p in PASSES:
            ck(mp.get(p) == rp.get(p), "%s.passes[%s] identical (%r vs %r)"
               % (key, p, mp.get(p), rp.get(p)))
        mi, ri = mat.get("indicators") or {}, ref.get("indicators") or {}
        ck(((mi.get("1") or {}).get("monetary") or {}).get("monetary_pct")
           == ((ri.get("1") or {}).get("monetary") or {}).get("monetary_pct"),
           "%s.ind1 monetary_pct identical" % key)
        ck((mi.get("3") or {}).get("margin_pct") == (ri.get("3") or {}).get("margin_pct"),
           "%s.ind3 margin_pct identical" % key)
        ck((mi.get("4") or {}).get("sales_to_mcap")
           == (ri.get("4") or {}).get("sales_to_mcap"),
           "%s.ind4 sales_to_mcap identical" % key)
        ck((mi.get("4") or {}).get("potential_pct")
           == (ri.get("4") or {}).get("potential_pct"),
           "%s.ind4 potential_pct identical" % key)
        ck((mi.get("2") or {}).get("eps_series") == (ri.get("2") or {}).get("eps_series"),
           "%s.ind2 eps_series (JSON round-trip) identical" % key)

    # اعدادِ غیربدیهی: پروب واقعاً شاخص‌ها را محاسبه کرده، نه اینکه همگی None باشند
    folad = bulk[fts_engine.norm_fa("فولاد")]
    ck(folad["score"] >= 3, "فولاد scores well on the seeded data (score=%s)"
       % folad["score"])
    _f1m = ((((folad.get("indicators") or {}).get("1") or {}).get("monetary") or {})
            .get("monetary_pct"))
    ck(_f1m == 100.0, "فولاد monetary growth is exactly 100%% (1000/500) — got %r" % (_f1m,))
    ck(folad.get("excluded") is False,
       "فولاد is not excluded (neutral industry filter)")
    shen = bulk[fts_engine.norm_fa("شبندر")]
    ck((shen.get("passes") or {}).get("1_growth") is False,
       "شبندر fails ind1 (20%% < the monetary floor) — the probe data really bites")

    # ── ۳) قراردادِ fallback (تصمیم ۴) ───────────────────────────────────
    ck(fts_engine.fts_results_of(con, "ناموجود", cfg_hash=ch) is None,
       "unknown symbol → None (caller falls back to live evaluate_v10)")
    ck(fts_engine.fts_results_bulk(con, cfg_hash="some-other-hash") is None,
       "cfg_hash mismatch → None (a threshold change invalidates the whole table)")
    ck(fts_engine.fts_results_of(con, "فولاد", cfg_hash="some-other-hash") is None,
       "single-symbol reader also honours the cfg_hash contract")

    # invalidate_fts_results قراردادِ «سینکِ تازه → جدول کثیف»: ردیفها را
    # حذف میکند و کشِ RAM را پاک می‌کند تا خواننده fallback زنده شود.
    ck(fts_engine.fts_results_bulk(con, cfg_hash=ch) is not None,
       "reader still serves the materialized rows before invalidate")
    n_del = fts_engine.invalidate_fts_results(con)
    ck(n_del == 3, "invalidate deletes the materialized rows (rowcount=%s)" % n_del)
    ck(fts_engine.fts_results_bulk(con, cfg_hash=ch) is None,
       "after invalidate → None → live fallback (a fresh sync made the table dirty)")
    ck(fts_engine.fts_results_of(con, "فولاد", cfg_hash=ch) is None,
       "single-symbol reader also falls back after invalidate")

    # ── ۴) جدولِ غایب = همان رفتارِ قبلی (یک DB قبل از مهاجرت) ──────────
    _absent_db(ch)

    bad = [msg for ok, msg in CHECKS if not ok]
    print("\n".join("%s %s" % ("PASS" if ok else "FAIL", msg) for ok, msg in CHECKS))
    print("%d/%d passed" % (len(CHECKS) - len(bad), len(CHECKS)))
    raise SystemExit(1 if bad else 0)
finally:
    con.close()
    shutil.rmtree(os.path.dirname(path), ignore_errors=True)


if __name__ == "__main__":
    try:
        _run_checks()
    except SystemExit as _e:
        sys.exit(int(_e.code) if _e.code is not None else 0)
    sys.exit(1)
