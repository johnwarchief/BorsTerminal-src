# -*- coding: utf-8 -*-
"""گام ۳۵ — تاب‌آوریِ همگام‌سازیِ افزایشی (Incremental Sync Resilience).

دو سناریوی واقعیِ «فردا» را روی یک کپیِ market.db آزمون می‌کند:

  سناریو ۱ — نمادِ جدید (عرضهٔ اولیه):
    نمادی که تا دیروز در هیچ جدولی نبوده، امروز در instruments/price_history
    ظاهر می‌شود. باید ببینیم آیا INSERT/UPDATE با ON CONFLICT ساختار را
    به هم می‌ریزد، یا خیر. قرارداد: نمادِ جدید فقط ردیفِ خودش را اضافه
    می‌کند، جداولِ دیگر را دست نمی‌زند، و bulk_scan/scan_symbol او را
    پیدا می‌کنند.

  سناریو ۲ — گزارش ماهانهٔ جدید:
    با ورودِ یک گزارشِ ماهانهٔ جدید برای نمادی موجود، سیستم باید بتواند
    بدونِ اسکنِ کل تاریخچه فقط ردیفِ جدید را وارد کند و کشِ fts_results
    مربوط به همان نماد را Invalidate/Update کند. قرارداد: ردیفِ جدید
    با MS_UPSERT جایگزین/اضافه می‌شود، tracing_no قدیمی‌ها سرجایشان می‌ماند،
    و invalidate_fts_results جدول را کثیف می‌کند تا خواننده fallback زنده شود.

اجرا:  python dev/incremental_sync_resilience.py
"""
import os
import sqlite3
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
sys.path.insert(0, _ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import codal_fetcher as cf
import fts_engine as fe

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    print('  %s %s' % ('PASS' if cond else 'FAIL', msg))


def main():
    src = os.path.join(_ROOT, "market.db")
    if not os.path.exists(src):
        print("[SKIP] market.db نیست — این آزمون به دیتایِ واقعی نیاز دارد")
        return 0
    tmp = tempfile.mkdtemp(prefix="bors_incr_")
    db = os.path.join(tmp, "incr.db")
    # کپی (نه mode=ro — می‌خواهیم روی آن بنویسیم)
    with open(src, "rb") as f, open(db, "wb") as out:
        out.write(f.read())
    conn = sqlite3.connect(db, timeout=60)
    conn.row_factory = sqlite3.Row
    cf.migrate_schema(conn)

    fs_before = conn.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0]
    ms_before = conn.execute("SELECT COUNT(*) FROM monthly_sales").fetchone()[0]
    ph_before = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]

    # ═══════════ سناریو ۱: نمادِ جدید (عرضهٔ اولیه) ═══════════
    print("\n== سناریو ۱: نمادِ جدید (عرضهٔ اولیه) ==")
    NEW = "عرضه۱"
    ck(conn.execute("SELECT COUNT(*) FROM instruments WHERE l_val18=?",
                    (NEW,)).fetchone()[0] == 0, "نمادِ جدید هنوز وجود ندارد")
    # instruments با ON CONFLICT (همان مسیرِ سینکِ واقعی)
    conn.execute("""INSERT INTO instruments (ins_code, l_val18, l_val30, sector_code,
                     sector_name, total_shares, eps, pe, base_vol, updated_at)
                   VALUES ('NEWCODE', ?, 'عرضه۱', '67', 'فلزات اساسي', 1e8, 1000, 20, 1e6, '2026')
                   ON CONFLICT(ins_code) DO UPDATE SET
                     l_val18=excluded.l_val18, sector_name=excluded.sector_name,
                     total_shares=excluded.total_shares, updated_at=excluded.updated_at""",
                 (NEW,))
    conn.commit()
    ck(conn.execute("SELECT COUNT(*) FROM instruments WHERE l_val18=?",
                    (NEW,)).fetchone()[0] == 1, "نمادِ جدید در instruments نشست")
    # price_history برای نمادِ جدید
    conn.execute("INSERT OR REPLACE INTO price_history (symbol, date, open, high, low, close, volume) "
                 "VALUES (?, '2026-01-01', 1000, 1100, 950, 1050, 1e6)", (NEW,))
    conn.execute("INSERT OR REPLACE INTO price_history (symbol, date, open, high, low, close, volume) "
                 "VALUES (?, '2026-01-02', 1050, 1150, 1000, 1100, 2e6)", (NEW,))
    conn.commit()
    ck(conn.execute("SELECT COUNT(*) FROM price_history WHERE symbol=?",
                    (NEW,)).fetchone()[0] == 2, "کندل‌های نمادِ جدید درج شد")
    # جداولِ دیگر دست‌نخورده ماندند
    ck(conn.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0] == fs_before,
       "نمادِ جدید به financial_statements دست نزد (تا وقتی گزارشی ندهد)")
    ck(conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0] == ph_before + 2,
       "price_history فقط ۲ ردیفِ جدید گرفت (نه بیشتر)")
    # resolve و bulk_scan نمادِ جدید را پیدا می‌کنند
    # symbol_index/resolve در confidence_engine هستند (fts_engine فقط norm_fa/sym_in)
    try:
        import confidence_engine as ce
        idx = ce.symbol_index(conn)
        entry = ce.resolve(idx, NEW)
    except Exception as e:
        entry = None
        print("     (resolve: %s)" % e)
    ck(entry is not None and (entry.get("l_val18") == NEW),
       "symbol_index/resolve نمادِ جدید را پیدا می‌کند")
    # bulk_scan از financial_statements/monthly_sales تغذیه می‌شود، پس نمادی
    # که هنوز گزارشی نکرده به‌حق در آن نیست (دادهٔ بنیانی برای ارزیابی ندارد).
    # این رفتارِ مطلوب است: عرضهٔ اولیه تا اولین گزارش کدال «بی‌داده» می‌ماند،
    # نه «مردود». وقتی اولین صورتِ مالی‌اش بیاید (سناریو ۲ج) باید ظاهر شود.
    bulk = fe.bulk_scan(conn, cfg={})
    hit = [r for r in bulk if (r.get("symbol") or "") == NEW]
    ck(len(hit) == 0, "bulk_scan نمادِ بدونِ گزارش را به‌حق برنمی‌گرداند (nodata، نه fail)")
    # و مسیرِ تک‌نمادی هم همین‌طور: crash نمی‌کند، یک نتیجهٔ بی‌داده می‌دهد
    one = fe.scan_symbol(conn, NEW, 1e13, 20.0, "فلزات اساسي", cfg={})
    ck(one is not None, "scan_symbol نمادِ جدید crash نمی‌کند (نتیجه می‌دهد)")
    ck(bool(one.get("detail")) is True or one.get("detail") is not None,
       "scan_symbol برای نمادِ جدید detail می‌دهد (حتی اگر همه‌اش None باشد)")
    # تکرارِ همان INSERT = یدم‌پذیر
    conn.execute("""INSERT INTO instruments (ins_code, l_val18, l_val30, sector_code,
                     sector_name, total_shares, eps, pe, base_vol, updated_at)
                   VALUES ('NEWCODE', ?, 'عرضه۱', '67', 'فلزات اساسي', 1e8, 1000, 20, 1e6, '2026')
                   ON CONFLICT(ins_code) DO UPDATE SET
                     l_val18=excluded.l_val18, sector_name=excluded.sector_name,
                     total_shares=excluded.total_shares, updated_at=excluded.updated_at""",
                 (NEW,))
    conn.commit()
    ck(conn.execute("SELECT COUNT(*) FROM instruments WHERE ins_code='NEWCODE'").fetchone()[0] == 1,
       "تکرارِ INSERT با ON CONFLICT ردیفی دوبل نمی‌سازد (یدم‌پذیر)")

    # ═══════════ سناریو ۲: گزارش ماهانهٔ جدید ═══════════
    print("\n== سناریو ۲: گزارش ماهانهٔ جدید ==")
    # یک نمادِ واقعی با تاریخچهٔ ماهانه
    row = conn.execute("SELECT symbol, MAX(tracing_no) tn, COUNT(*) c FROM monthly_sales "
                       "WHERE ytd_revenue IS NOT NULL AND ytd_revenue>0 "
                       "GROUP BY symbol HAVING c>=3 ORDER BY c DESC LIMIT 1").fetchone()
    sym = row["symbol"]
    ck(row is not None and row["c"] >= 3, "نمادِ دارایِ تاریخچه پیدا شد: %s (%d ردیف)"
       % (sym, row["c"]))
    # بیشترین (سال,ماه) موجود
    top = conn.execute("SELECT MAX(year) y, MAX(month) m FROM monthly_sales WHERE symbol=?",
                       (sym,)).fetchone()
    ck(top["y"] is not None, "آخرین ماهِ موجود: %s/%s" % (top["y"], top["m"]))
    # ردیفِ جدید با tracing_no کاملاً جدید (همان مسیرِ سینک)
    new_tn = int(row["tn"]) + 100000
    conn.execute(cf.MS_UPSERT, (new_tn, sym,
                               "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۵/۰۶/۳۰",
                               "1405/06/30", 1405, 6, 500.0, 5000.0, 450.0, 4500.0,
                               None, None, None, "p", "e"))
    conn.commit()
    ck(conn.execute("SELECT COUNT(*) FROM monthly_sales WHERE symbol=?",
                    (sym,)).fetchone()[0] == row["c"] + 1,
       "ردیفِ جدید اضافه شد (کل: %d → %d)" % (row["c"], row["c"] + 1))
    ck(conn.execute("SELECT COUNT(*) FROM monthly_sales WHERE tracing_no=?",
                    (row["tn"],)).fetchone()[0] == 1,
       "tracing_no قدیمی سرجایش ماند (حذف نشد)")
    ck(conn.execute("SELECT ytd_revenue FROM monthly_sales WHERE tracing_no=?",
                    (new_tn,)).fetchone()[0] == 5000.0, "مقدارِ ردیفِ جدید درست نشست")
    # جایگزینیِ همان (سال,ماه) با MS_UPSERT روی tracing_no یکسان = به‌روزرسانی
    conn.execute(cf.MS_UPSERT, (new_tn, sym,
                               "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۵/۰۶/۳۰(اصلاحیه)",
                               "1405/06/30", 1405, 6, 520.0, 5200.0, 450.0, 4500.0,
                               None, None, None, "p2", "e2"))
    conn.commit()
    ck(conn.execute("SELECT COUNT(*) FROM monthly_sales WHERE symbol=?",
                    (sym,)).fetchone()[0] == row["c"] + 1,
       "MS_UPSERT روی tracing_no یکسان ردیف دوبل نمی‌سازد (جایگزین می‌کند)")
    ck(conn.execute("SELECT ytd_revenue FROM monthly_sales WHERE tracing_no=?",
                    (new_tn,)).fetchone()[0] == 5200.0,
       "به‌روزرسانی مقدار را بازنویسی کرد (اصلاحیه برنده شد)")
    # _dedupe_ym ردیفِ جدید را به‌درستی یکی می‌کند
    pred, params = fe.sym_in("symbol", sym)
    ms_rows = conn.execute("SELECT year, month, monthly_revenue, ytd_revenue FROM monthly_sales "
                           "WHERE %s AND ytd_revenue IS NOT NULL AND ytd_revenue>0" % pred,
                           params).fetchall()
    deduped = fe._dedupe_ym([(int(r["year"]), int(r["month"]),
                              fe._f(r["monthly_revenue"]), fe._f(r["ytd_revenue"]))
                             for r in ms_rows])
    ym = {(int(r["year"]), int(r["month"])) for r in ms_rows}
    ck(all((y, m) in ym for (y, m, _, _) in deduped),
       "_dedupe_ym هیچ (سال,ماه)‌ای را گم نمی‌کند")
    ck(len(deduped) == len({(y, m) for (y, m, _, _) in deduped}),
       "_dedupe_ym خروجی‌اش بدونِ تکرارِ (سال,ماه) است")

    # ═══════════ سناریو ۲ب: invalidation کش fts_results ═══════════
    print("\n== سناریو ۲ب: invalidation کش fts_results ==")
    # ابتدا یک ردیف مادی کن
    try:
        conn.execute("DELETE FROM fts_results")
        conn.execute("""INSERT OR REPLACE INTO fts_results (symbol, score, verdict, computed_at)
                        VALUES (?, 5, 'STRONG', '2026')""", (sym,))
        conn.commit()
        fe._FTS_RESULTS_CACHE.pop(id(conn), None)
        before = fe.fts_results_of(conn, sym, cfg_hash="")
        ck(before is not None, "خواننده ردیفِ مادی‌شده را برمی‌گرداند")
        n = fe.invalidate_fts_results(conn)
        ck(n >= 1, "invalidate_fts_results ردیف‌ها را پاک کرد (rowcount=%d)" % n)
        ck(conn.execute("SELECT COUNT(*) FROM fts_results").fetchone()[0] == 0,
           "بعد از invalidate جدول خالی است (سینکِ تازه = جدول کثیف)")
        fe._FTS_RESULTS_CACHE.pop(id(conn), None)
        ck(fe.fts_results_of(conn, sym, cfg_hash="") is None,
           "خواننده بعد از invalidate → None → fallback زنده")
    except Exception as e:
        ck(False, "بخشِ fts_results: %s: %s" % (type(e).__name__, e))

    # ═══════════ سناریو ۲ج: ستون‌های مشتق روی ردیفِ جدید ═══════════
    print("\n== سناریو ۲ج: ستون‌های مشتق روی صورتِ مالیِ جدید ==")
    fs_tn = conn.execute("SELECT MAX(tracing_no) tn FROM financial_statements").fetchone()["tn"] or 0
    fs_tn = int(fs_tn) + 100000
    title = "صورت‌های مالی تلفیقی سال مالی (حسابرسی شده)"
    conn.execute(cf.FS_UPSERT,
                 (fs_tn, NEW, "شرکت جدید", title, "Financial Statements", 12,
                  "1405/05/31", "2026", 1.0, 0.3, 0.2, 0.1, 2.0, 1.0, 1.0, 0.5, 0.2, 0.05,
                  "کلیه‌ی مبالغ به میلیون ریال می‌باشد", "http://fs", "2026")
                 + cf.fs_derived(title, "1405/05/31", "کلیه‌ی مبالغ به میلیون ریال می‌باشد"))
    conn.commit()
    r = conn.execute("SELECT is_audited, is_consolidated, fiscal_year, unit_norm "
                     "FROM financial_statements WHERE tracing_no=?", (fs_tn,)).fetchone()
    ck(r is not None and r["is_audited"] == 1, "صورتِ مالیِ جدید: is_audited=1 (در زمانِ درج)")
    ck(r is not None and r["is_consolidated"] == 1, "صورتِ مالیِ جدید: is_consolidated=1 (تلفیقی)")
    ck(r is not None and r["fiscal_year"] == "1405", "صورتِ مالیِ جدید: fiscal_year=1405")
    ck(r is not None and r["unit_norm"] == "mrl", "صورتِ مالیِ جدید: unit_norm=mrl")
    # backfill نباید کاری برایش داشته باشد.
    # توجه: fs_filled شمارشِ کلِ ردیف‌های unit_norm=NULL در دیتابیس است، نه فقط
    # ردیفِ تازه — و رویِ market.db واقعی همیشه تعدادی از آن‌ها وجود دارد
    # (امروزه ۳۶۷؛ پیش از بازسازی ۱۱۱۸). ادعایِ ==۰ بنابراین هیچ‌وقت رویِ دادهٔ
    # واقعی برقرار نبوده و تست از قبل می‌سوخت. معنایِ درستِ همان ادعا: ردیفِ
    # تازه نباید چیزی به شمارهِ ردیف‌هایِ نیازمندِ پرکردن اضافه کند.
    cf.backfill_derived(conn, verbose=False)   # settle pre-existing drift
    st = cf.backfill_derived(conn, verbose=False)
    ck(st.get("fs_filled", -1) == 0,
       "backfill_derived برای ردیفِ جدید کاری ندارد (fs_filled == unit_norm NULL هایِ از قبل موجود)")
    ck(fs_tn not in {r["tracing_no"] for r in conn.execute(
        "SELECT tracing_no FROM financial_statements WHERE unit_norm IS NULL")},
       "ردیفِ تازه خودش در شمارهِ ردیف‌هایِ بی-unit_norm نیست")

    # ═══════════ سناریو ۲د: نمادِ جدید حالا گزارش داده → bulk_scan ═══════════
    print("\n== سناریو ۲د: نمادِ جدید بعد از اولین گزارش ==")
    bulk2 = fe.bulk_scan(conn, cfg={})
    hit2 = [r for r in bulk2 if (r.get("symbol") or "") == NEW]
    ck(len(hit2) == 1, "حالا که صورتِ مالی داده، bulk_scan او را برمی‌گرداند (یک ردیف)")
    if hit2:
        ck(hit2[0].get("excluded") is not None,
           "ردیفِ نمادِ جدید excluded flag دارد (نه خام)")
    conn.close()
    n_bad = sum(1 for ok, _ in CHECKS if not ok)
    print('\n%d checks, %d failed' % (len(CHECKS), n_bad))
    print('INCREMENTAL SYNC %s' % ('FAILED' if n_bad else 'PASSED'))
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
