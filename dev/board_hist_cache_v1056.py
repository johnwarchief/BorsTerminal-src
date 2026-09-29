# -*- coding: utf-8 -*-
"""
dev/board_hist_cache_v1056.py — گاردِ «مادی‌سازیِ دو پنجرۀ تابلو».

دو پنجرۀ روزانۀ کوئریِ تابلو (نمایشِ ۳۰ روزه و [ih] شصت‌نشسته) به دو جدولِ
`board_hist_v` / `board_hist_fv` منتقل شده‌اند. این گارد سه چیز را می‌گیرد،
هر کدام با کنترلِ منفی:

  ۱) برابریِ نتیجه: کوئریِ «با جدول‌هایِ مادی» باید سطر‌به‌سطر و
     ستون‌به‌ستون همان کوئریِ «تک‌پیسّهٔ قدیمی» را بدهد. پنجره‌ها از متنِ
     خودِ ماژول به‌عنوانِ CTE درونِ کوئری برمی‌گردانده می‌شوند، پس تست با
     منبعِ واقعی می‌خواند نه با بازنویسیِ دستی.
  ۲) بی‌اعتباری: بازنویسیِ ردیفِ *نشستِ جاری* (کاری که تیکِ ۵ ثانیه می‌کند)
     نباید کش را بسوزاند؛ ولی تصحیحِ درجایِ *نشستِ پیشین* و تصحیحِ درجایِ
     tape_history (که هیچ شمارشی را تکان نمی‌دهد) باید بازسازی کند.
  ۳) صفرِ بی‌دلیل: اگر پنجره بی‌دلیل خالی شد، خطا بدهد و جدولِ قبلی را
     نگه دارد؛ ولی tape_historyِ خالیِ *واقعی* (نصبِ تازه) خطا ندهد.

فیکسچر: ساختارِ جدول‌ها از market.db واقعی کپی می‌شود (و نبودِ آن از
market.db.lzma)، ردیف‌ها ساختگی است. پس هیچ دادهٔ زنده‌ای لازم نیست و
تست رویِ ماشینِ CI هم همان چیزهایی را می‌بیند که رویِ این ماشین.
"""
from __future__ import annotations

import lzma
import os
import re
import shutil
import sqlite3
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ.setdefault("BORS_SHOW_CONSOLE", "1")

TABLES = ["instruments", "boards", "market_watch", "client_type",
          "price_history", "daily_prices", "tape_history", "tape_history_state"]

PASS, FAIL = [], []


def ck(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def _schema_source():
    """مسیرِ بانکِ ساختار. market.dbِ مخزن اگر هست، وگرنه baselineِ فشرده."""
    plain = os.path.join(REPO, "market.db")
    if os.path.exists(plain):
        return plain, None
    packed = os.path.join(REPO, "market.db.lzma")
    if not os.path.exists(packed):
        raise SystemExit("no market.db and no market.db.lzma — nothing to copy the schema from")
    out = os.path.join(tempfile.mkdtemp(prefix="bors_hist_schema_"), "schema.db")
    with lzma.open(packed) as src, open(out, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return out, out


def _build_fixture() -> sqlite3.Connection:
    src_path, tmp = _schema_source()
    src = sqlite3.connect(f"file:{src_path.replace(os.sep, '/')}?mode=ro", uri=True)
    c = sqlite3.connect(":memory:")
    for t in TABLES:
        cols = [r[1] for r in src.execute(f"PRAGMA table_info({t})")]
        if not cols:
            raise SystemExit(f"table {t} is gone from the schema source — guard is stale")
        # ساختار کپی می‌شود، ردیف نه؛ و بی‌قید‌وپیشه (CREATE TABLE AS) تا
        # هیچ NOT NULLِ اضافه‌ای مانعِ ردیفِ ساختگیِ تست نشود.
        sel = ", ".join(f"NULL AS \"{col}\"" for col in cols)
        c.execute(f"CREATE TABLE {t} AS SELECT {sel} WHERE 0")
    src.close()

    def ins(table, cols, rows):
        ph = ",".join("?" * len(cols))
        c.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph})", rows)

    # چهار نماد: A کامل، B کامل، C کم‌سابقه (درِ «کمتر از ۳۰ نشست»)،
    # D بی‌تاریخچه (LEFT JOINِ fv باید NULL بدهد نه صفر).
    for code, sym in ((1, "A"), (2, "B"), (3, "C"), (4, "D")):
        ins("instruments", ["ins_code", "l_val18", "l_val30", "sector_name"],
            (code, sym, "نام " + sym, "صنعت‌۱"))
        ins("boards", ["ins_code", "board"], (code, "بورس"))
        ins("market_watch",
            ["ins_code", "d_even", "p_closing", "p_last", "q_tot_tran", "z_tot_tran",
             "price_yesterday", "q_tot_cap", "price_change", "pe", "eps",
             "price_max", "price_min", "allowed_min", "allowed_max",
             "buy_q_vol", "buy_q_val", "buy_q_cnt", "sell_q_vol", "sell_q_val",
             "sell_q_cnt", "buy_q1_vol", "buy_q1_px", "sell_q1_vol", "sell_q1_px",
             "buy_q1_cnt"],
            (code, 20260928, 100 + code, 101 + code, 5000 + code * 100, 505000,
             100, 1e9, 1.0, 8.0, 12.0, 105 + code, 98 + code, 90, 110,
             10, 1000, 3, 9, 900, 2, 5, 101, 4, 100, 1))
        ins("client_type",
            ["ins_code", "d_even", "buy_i_vol", "buy_n_vol", "sell_i_vol", "sell_n_vol",
             "buy_count_i", "sell_count_i"],
            (code, 20260928, 3000, 2000, 1000, 500, 30, 10))

    ISO = 20260928
    # price_history: ۷۰ روز برایِ A/B، ۵ روز برایِ C، هیچ برایِ D
    days = [f"2026-{m:02d}-{d:02d}" for m, n in ((7, 31), (8, 31), (9, 8))
            for d in range(1, n + 1)]
    for code, sym in ((1, "A"), (2, "B"), (3, "C")):
        limit = 70 if sym in ("A", "B") else 5
        for k, dt in enumerate(days[:limit]):
            ins("price_history",
                ["symbol", "date", "open", "high", "low", "close", "volume"],
                (sym, dt, 100 + k, 105 + k, 95 + k % 7, 102 + k, 1000 + k * 10))
    # daily_prices: نشست‌هایِ پیشین (پنجره این‌ها را می‌خواند) و نشستِ جاری
    for code in (1, 2, 3, 4):
        for k, d in enumerate([20260920, 20260921, 20260922, 20260926, 20260927]):
            ins("daily_prices",
                ["ins_code", "d_even", "p_closing", "price_max", "price_min",
                 "q_tot_tran"],
                (code, d, 100 + k, 104 + k, 96 + k, 4000 + code * 10 + k))
        ins("daily_prices", ["ins_code", "d_even", "p_closing", "price_max",
                             "price_min", "q_tot_tran"],
            (code, ISO, 100 + code, 105 + code, 98 + code, 5000 + code))
    # tape_history: شصت نشست برایِ A/B، ده نشست برایِ C، هیچ برایِ D
    for code in (1, 2, 3, 4):
        n = 60 if code in (1, 2) else (10 if code == 3 else 0)
        for k in range(n):
            d = 20260928 - k
            ins("tape_history",
                ["ins_code", "d_even", "price_min", "price_max", "q_tot_tran5j"],
                (code, d, 90 + (k % 5), 110 + (k % 7), 3000 + code * 100 + k))
    ins("tape_history_state", ["id", "last_attempt", "last_ok", "newest_d_even", "note"],
        (1, "2026-09-28 21:00:00", "2026-09-28 21:00:00", ISO, ""))
    c.commit()
    return c


# ── بازگردانیِ کوئریِ تک‌پیسّه از متنِ ماژول ───────────────────────────────
def _queries():
    """(live_with_tables, monolithic) — هر دو از خودِ api/market.py."""
    import api.market as mk
    src = open(os.path.join(REPO, "api", "market.py"), encoding="utf-8").read()
    m = re.search(r'query = """(.*?)"""\n', src, re.DOTALL)
    assert m, "board query text not found in api/market.py"
    live = m.group(1)
    assert "board_hist_v" in live and "board_hist_fv" in live, \
        "the live query no longer reads the materialized windows — this guard is stale"

    def cte_body(sql, name):
        # _HIST_V_SQL = "WITH iso AS (...), <cte‌ها> SELECT * FROM v"
        body = sql.split("WITH", 1)[1].lstrip()
        body = re.sub(r"^iso AS \(SELECT MAX\(d_even\) AS d FROM market_watch\),\s*",
                      "", body)
        body = body.rsplit(f"SELECT * FROM {name}", 1)[0]
        return strip_tail(body)

    vcte = cte_body(mk._HIST_V_SQL, "v")
    fcte = cte_body(mk._HIST_FV_SQL, "fv")
    stub_v = re.search(r"\n *v AS MATERIALIZED \(SELECT \* FROM board_hist_v\),", live)
    stub_f = re.search(r"\n *fv AS MATERIALIZED \(SELECT \* FROM board_hist_fv\),", live)
    assert stub_v and stub_f, "stub CTE text changed — update this guard"
    # stubها کامِ آخرِ خودشان را مصرف می‌کنند، پس CTEِ بعدی باید کامِ تازه بگیرد
    # وگرنه کوئریِ بازسازی‌شده ناقص می‌ماند («incomplete input»).
    mono = (live[:stub_v.start()] + ",\n" + indent(vcte) + ",\n" + indent(fcte) + ","
            + live[stub_f.end():])
    # فقط ارجاعِ اجرایی مهم است: خودِ سطرهایِ توضیحیِ کنارِ stub نامِ جدول را
    # می‌آورند و اگر بی‌بررسی جلوی‌شان گرفته شود، گارد از خودِ متن شکایت می‌کند.
    assert "FROM board_hist" not in mono, "monolithic rebuild still reads the tables"
    return mk, live, mono


def strip_tail(s):
    lines = s.rstrip().splitlines()
    while lines and lines[-1].lstrip().startswith("--"):
        lines.pop()
    return "\n".join(lines).rstrip().rstrip(",").rstrip()


def indent(s):
    return "\n".join((" " * 12 + l).rstrip() for l in s.splitlines())


def _rows(c, sql):
    cur = c.execute(sql)
    names = [d[0] for d in cur.description]
    return names, cur.fetchall()


def compare(cached, mono, names_a, names_b):
    if names_a != names_b:
        return False, f"column sets differ: {set(names_a) ^ set(names_b)}"
    if len(cached) != len(mono):
        return False, f"row count {len(cached)} vs {len(mono)}"
    for i, (ra, rb) in enumerate(zip(cached, mono)):
        if ra != rb:
            bad = [names_a[j] for j in range(len(ra)) if ra[j] != rb[j]]
            return False, f"row {i} differs in {bad}"
    return True, ""


def main():
    mk, live_sql, mono_sql = _queries()
    c = _build_fixture()

    # ── ۱) ساختِ جدول‌ها و برابریِ نتایج ────────────────────────────────────
    calls = {"n": 0}
    real_rebuild = mk._rebuild_history_windows

    def counting_rebuild(conn):
        calls["n"] += 1
        return real_rebuild(conn)
    mk._rebuild_history_windows = counting_rebuild
    mk._HIST_CACHE_KEY = (None,)

    built = mk.ensure_board_history(c)
    ck("اولین فراخوانیِ ensure دو پنجره را می‌سازد", built and calls["n"] == 1,
       f"rebuilds={calls['n']}")

    names_a, rows_a = _rows(c, live_sql)
    names_b, rows_b = _rows(c, mono_sql)
    same, why = compare(rows_a, rows_b, names_a, names_b)
    ck("کوئریِ مادی‌شده سطر‌به‌سطر همان نتیجهٔ کوئریِ تک‌پیسّه است", same, why)
    ck("پنجره‌ها ستون‌هایِ پنج فیلتر را می‌سازند (prior30_vol/hist_sessions)",
       "prior30_vol" in names_a and "hist_sessions" in names_a
       and all(r[names_a.index("prior30_vol")] is not None for r in rows_a[:1]))

    # ── ۲) کش: نشستِ جاری عوض شود، پنجره نه ────────────────────────────────
    mk.ensure_board_history(c)
    ck("فراخوانیِ دومِ بی‌تغییری بازسازی نمی‌کند", calls["n"] == 1,
       f"rebuilds={calls['n']}")

    # تیکِ زنده: بازنویسیِ ردیفِ نشستِ جاری (۲۰۲۶۰۹۲۸)
    c.execute("UPDATE daily_prices SET p_closing=111, q_tot_tran=99999 WHERE d_even=20260928")
    c.commit()
    mk.ensure_board_history(c)
    ck("بازنویسیِ ردیفِ نشستِ جاری کش را نمی‌سوزاند (تیکِ ۵ ثانیه)", calls["n"] == 1,
       f"rebuilds={calls['n']}")

    # کنترلِ منفی ۱: تصحیحِ درجایِ یک نشستِ *پیشین*
    before = c.execute("SELECT month_avg_vol FROM board_hist_v WHERE symbol='A'").fetchone()
    c.execute("UPDATE daily_prices SET q_tot_tran=1 WHERE ins_code=1 AND d_even=20260927")
    c.commit()
    mk.ensure_board_history(c)
    ck("تصحیحِ درجایِ نشستِ پیشین بازسازی می‌کند", calls["n"] == 2,
       f"rebuilds={calls['n']}")
    after = c.execute("SELECT month_avg_vol FROM board_hist_v WHERE symbol='A'").fetchone()
    ck("و پنجره واقعاً عددِ تازه می‌گیرد", before != after, f"{before} → {after}")

    # کنترلِ منفی ۲: tape_history با همان شمارِ ردیف و همان rowid فقط مقدار عوض کند
    calls["n"] = 0
    mk.ensure_board_history(c)
    ck("بی‌تغیریِ مطلق دوباره بازسازی نمی‌کند", calls["n"] == 0, f"rebuilds={calls['n']}")
    c.execute("UPDATE tape_history SET price_max=999 WHERE ins_code=1 AND d_even=20260928")
    c.commit()
    mk.ensure_board_history(c)
    ck("تصحیحِ درجایِ [ih] (بی‌تغییریِ شمارش و rowid) بازسازی می‌کند",
       calls["n"] == 1, f"rebuilds={calls['n']}")

    # ── ۳) صفرِ بی‌دلیل و صفرِ با دلیل ─────────────────────────────────────
    # «بی‌دلیل» را نمی‌توان با داده ساخت (هر ردیفِ tape_history حداقل یک گروه
    # می‌سازد)، پس درِ آن مستلاً آزموده می‌شود: پنجرهٔ بی‌ردیف درحالی‌که منبع
    # ردیف دارد.
    keep = c.execute("SELECT COUNT(*) FROM board_hist_fv").fetchone()[0]
    good_fv_sql = mk._HIST_FV_SQL
    mk._HIST_FV_SQL = "SELECT 'zzz' AS ins_code WHERE 0"
    mk._HIST_CACHE_KEY = (None,)
    try:
        mk.ensure_board_history(c)
        ck("پنجرۀ خالیِ بی‌دلیل خطا می‌دهد", False, "هیچ خطایی رخ نداد")
    except Exception as e:
        ck("پنجرۀ خالیِ بی‌دلیل خطا می‌دهد", "zero rows" in str(e), str(e)[:70])
    ck("خطا جدولِ قبلی را نگه می‌دارد (نه خالی‌کردنِ بی‌صدا)",
       c.execute("SELECT COUNT(*) FROM board_hist_fv").fetchone()[0] == keep,
       f"rows={keep}")
    mk._HIST_FV_SQL = good_fv_sql

    # حالا منبعِ واقعی هم خالی است → مجاز، بی‌خطا (نصبِ تازه‌ای که هنوز [ih]
    # ندارد؛ کوئریِ تک‌پیسّه هم همین را می‌داد: LEFT JOIN رویِ fvِ خالی ⇒ NULL)
    c.execute("DELETE FROM tape_history")
    c.commit()
    mk._HIST_CACHE_KEY = (None,)
    try:
        mk.ensure_board_history(c)
        zero = c.execute("SELECT COUNT(*) FROM board_hist_fv").fetchone()[0]
        ck("tape_historyِ خالیِ واقعی خطا نمی‌دهد (نصبِ تازه)", zero == 0, f"rows={zero}")
        names_x, rows_x = _rows(c, live_sql)
        idx = names_x.index("prior30_vol")
        ck("و آنجا ستون‌هایِ [ih] NULL می‌مانند نه صفر",
           len(rows_x) > 0 and all(r[idx] is None for r in rows_x))
    except Exception as e:
        ck("tape_historyِ خالیِ واقعی خطا نمی‌دهد (نصبِ تازه)", False, str(e)[:80])

    print(f"\n{len(PASS)} pass / {len(FAIL)} fail")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
