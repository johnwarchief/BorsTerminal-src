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

import atexit
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

# هر دو بانکِ کپیِ نوشتنیِ این گارد در %TEMP% می‌نشینند (~۱۵۰ مگ هر کدام) و اگر
# پاک نشوند، هر اجرایِ CI یک‌سومِ گیگ جا می‌گذارد.
def _temp_db(name="schema.db"):
    d = tempfile.mkdtemp(prefix="bors_hist_")
    atexit.register(shutil.rmtree, d, ignore_errors=True)
    return os.path.join(d, name)

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
    out = _temp_db("schema.db")
    with lzma.open(packed) as src, open(out, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return out, out


def _real_db_copy() -> str:
    """کپیِ نوشتنیِ بانکِ واقعی، تا پنجره‌ها در فایلِ اصلیِ کاربر ساخته نشوند.

    دادهٔ واقعی لازماً لازم است: فیکسچرِ ساختگی هیچ فیلتری را روشن نمی‌کند و
    مقایسهٔ مجموعهٔ خالی با مجموعهٔ خالی سبز می‌شود.
    """
    src_path, _tmp = _schema_source()
    out = _temp_db("market.db")
    shutil.copyfile(src_path, out)
    return out


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
    # سینکِ کندل از تابلو، ردیفِ *همین نشست* را هم درِ price_history می‌نویسد و
    # هر ۹۰ ثانیه بازنویسی‌اش می‌کند. پنجرۀ نمایش و امضایِ کش هر دو باید آن را
    # نبینند؛ بی‌این دو ردیف، گارد هیچ‌وقت این حالت را آزموده نبود.
    for code, sym in ((1, "A"), (2, "B")):
        ins("price_history",
            ["symbol", "date", "open", "high", "low", "close", "volume"],
            (sym, "2026-09-28", 100.0, 106.0, 99.0, 103.0, 300.0 + code))
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
    m = re.search(r'_BOARD_SQL = """(.*?)"""\n', src, re.DOTALL)
    assert m, "board query text not found in api/market.py (_BOARD_SQL)"
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


class _FakeReq:
    headers = {}


class _NoCloseConn:
    """`_build_market_response` درِ پایان conn.close() را صدا می‌زند؛ اتصالِ
    فیکسچر در حافظه است و بسته شدنش کلِ تست را بی‌محتوا خراب می‌کند."""

    def __init__(self, real):
        self._real = real

    def cursor(self):
        return self._real.cursor()

    def execute(self, *a, **k):
        return self._real.execute(*a, **k)

    def executemany(self, *a, **k):
        return self._real.executemany(*a, **k)

    def commit(self):
        return self._real.commit()

    def close(self):
        pass


def _pipeline_flags(mk, conn, sql_text):
    """لولۀ واقعیِ تابلو را اجرا می‌کند، بی‌آنکه چیزی جز *متنِ SQL* عوض شود."""
    import json as _json
    import pandas as real_pd

    class _PdShim:
        def read_sql_query(self, query, con, *a, **k):
            self.calls += 1
            return real_pd.read_sql_query(sql_text, con, *a, **k)

        calls = 0

        def __getattr__(self, n):
            return getattr(real_pd, n)

    old_pd, old_getdb = mk.pd, mk.get_db
    shim = _PdShim()
    mk.pd, mk.get_db = shim, (lambda: _NoCloseConn(conn))
    # حالتِ داغ (کار #73) قابِ تابلو را در RAM نگه می‌دارد؛ این گارد همین
    # متنِ SQL را دو بار می‌سنجد (با جدولِ مادی و تک‌پیسّه)، پس بینِ دو اجرا
    # باید قاب بسوزد، وگرنه اجرای دوم پاسخِ اجرای اول را می‌بیند و مقایسه
    # با خودش یکی می‌شود — سبزِ بی‌محتوا.
    mk._reset_board_cache()
    try:
        out = mk._build_market_response(_FakeReq())
        body = out.body if isinstance(out.body, (bytes, bytearray)) else out.body.encode()
        payload = _json.loads(body.decode("utf-8"))
    finally:
        mk.pd, mk.get_db = old_pd, old_getdb
        mk._reset_board_cache()
    assert shim.calls == 1, f"pipeline did not run the SQL (calls={shim.calls})"
    got = {k: set() for k in ("f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh")}
    for rec in payload["data"]:
        for k in got:
            if rec.get(k):
                got[k].add(rec["symbol"])
    return got, payload["data"]


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

    # برابریِ *داوری‌ها* رویِ دادهٔ واقعی به انتهای main منتقل شده است: این
    # بخش ensure_board_history را رویِ اتصالِ دیگری اجرا می‌کند و شمارنده و
    # کلیدِ کشِ تست‌هایِ بالا را آلوده می‌کرد (سه چک بی‌دلیل قرمز شدند).
    ck("پنجره‌ها ستون‌هایِ پنج فیلتر را می‌سازند (prior30_vol/hist_sessions)",
       "prior30_vol" in names_a and "hist_sessions" in names_a
       and all(r[names_a.index("prior30_vol")] is not None for r in rows_a[:1]))

    # نشستِ باز درِ price_history ردیف دارد (کارِ خودِ سینک) — پنجرۀ نمایش نباید
    # آن را «دیروز» بخوانَد. بی‌این چک، «حجمِ دیروز» نیم‌بهایِ همین نشست می‌شد.
    # مبناءِ درستِ خودِ پنجره است: آخرینِ نشستِ تمام‌شده از اتحادِ دو منبع.
    exp_prev = c.execute("SELECT q_tot_tran FROM daily_prices "
                         "WHERE ins_code=1 AND d_even=20260927").fetchone()[0]
    live_vol = c.execute("SELECT volume FROM price_history WHERE symbol='A' "
                         "AND date='2026-09-28'").fetchone()[0]
    pv = c.execute("SELECT prev_day_vol FROM board_hist_v WHERE symbol='A'").fetchone()[0]
    ck("«حجمِ دیروز»ِ پنجره، ردیفِ نشستِ باز را نمی‌خواند",
       pv == exp_prev and pv != live_vol,
       f"پنجره={pv} · نشستِ پیش={exp_prev} · کندلِ نشستِ باز={live_vol}")

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

    # تیکِ کندل‌ساز: سینکِ کندل از تابلو همان ردیفِ نشستِ باز را درِ
    # price_history می‌نویسد؛ اگر امضا آن را ببیند، کش هر دو دقیقه می‌سوزد.
    c.execute("UPDATE price_history SET volume=volume+4000, high=high+2 "
              "WHERE date='2026-09-28'")
    c.execute("INSERT OR REPLACE INTO price_history (symbol, date, open, high, low,"
              " close, volume) VALUES ('C','2026-09-28',1,2,1,2,3)")
    c.commit()
    mk.ensure_board_history(c)
    ck("بازنویسیِ کندلِ نشستِ باز درِ price_history کش را نمی‌سوزاند",
       calls["n"] == 1, f"rebuilds={calls['n']}")

    # کنترلِ منفی ۱: تصحیحِ درجایِ یک نشستِ *پیشین*
    before = c.execute("SELECT month_avg_vol FROM board_hist_v WHERE symbol='A'").fetchone()
    c.execute("UPDATE daily_prices SET q_tot_tran=1 WHERE ins_code=1 AND d_even=20260927")
    c.commit()
    mk.ensure_board_history(c)
    ck("تصحیحِ درجایِ نشستِ پیشین بازسازی می‌کند", calls["n"] == 2,
       f"rebuilds={calls['n']}")
    after = c.execute("SELECT month_avg_vol FROM board_hist_v WHERE symbol='A'").fetchone()
    ck("و پنجره واقعاً عددِ تازه می‌گیرد", before != after, f"{before} → {after}")

    # کنترلِ مثبت ۱ب: کندلِ یک نشستِ *تمام‌شده* درِ price_history عوض شود
    c.execute("UPDATE price_history SET volume=volume+1 WHERE symbol='A' "
              "AND date='2026-09-07'")
    c.commit()
    mk.ensure_board_history(c)
    ck("تصحیحِ کندلِ یک نشستِ تمام‌شده بازسازی می‌کند", calls["n"] == 3,
       f"rebuilds={calls['n']}")

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

    # ── ۴) داوریِ پنج فیلتر رویِ دادهٔ واقعی، دو مسیر، متنِ بی‌تنها SQL عوض ──
    # چرا رویِ دادهٔ واقعی: با ردیف‌هایِ ساختگی هیچ‌یک از پنج فیلتر نمادی پیدا
    # نمی‌کند و مقایسهٔ «خالی با خالی» سبز می‌شود بی‌آنکه چیزی ثابت شده باشد —
    # دقیقاً همین در نسخۀ اولِ این گارد افتاد. کپیِ نوشتنی ساخته می‌شود تا
    # جدول‌های پنجره در فایلِ اصلیِ کاربر ننشینند.
    real_path = _real_db_copy()
    c2 = sqlite3.connect(real_path)
    # «جت» درِ دادۀِ زنده تقریباً هیچ‌وقت نماد ندارد (سنجشِ ۱۴۰۵-۰۷-۰۸: شمارِ
    # خودِ سایت هم صفر بود) و مقایسهٔ «صفر با صفر» هیچ چیز را اثبات نمی‌کرد.
    # پس یک نماد را عمداً جت می‌کنیم: پلکان از tape_history می‌آید (دست‌نخورده)
    # و قیدهایِ زنده از market_watch/client_type. حالا چک هم بی‌محتوا نیست و
    # هم گذارِ «مثبت» را در دو مسیر می‌سنجد.
    seed = c2.execute(
        "WITH r AS (SELECT ins_code, d_even, price_max, q_tot_tran5j, "
        "                  ROW_NUMBER() OVER (PARTITION BY ins_code ORDER BY d_even DESC) srn "
        "           FROM tape_history) "
        "SELECT ins_code, "
        "       MAX(CASE WHEN srn IN (3,6,10,20,30,40,50,60) THEN price_max END) lad, "
        "       SUM(CASE WHEN srn <= 30 THEN q_tot_tran5j END)/30.0 base30 "
        " FROM r GROUP BY ins_code "
        " HAVING COUNT(*) >= 60 AND lad > 0 AND base30 > 0 "
        "   AND ins_code IN (SELECT ins_code FROM market_watch "
        "                    WHERE d_even = (SELECT MAX(d_even) FROM market_watch)) "
        " ORDER BY lad DESC LIMIT 1").fetchone()
    seed_symbol = None
    if seed:
        code_s, lad, base30 = seed
        pl = round(lad * 1.9, 0)
        c2.execute(
            "UPDATE market_watch SET p_last=?, p_closing=?, price_yesterday=?, "
            "       q_tot_tran=?, z_tot_tran=? "
            " WHERE ins_code=? AND d_even=(SELECT MAX(d_even) FROM market_watch)",
            (pl, round(pl * 0.95), round(pl / 1.12),
             max(1.0, base30 * 40.0), 400.0, code_s))
        # client_type درِ تابلو از *آخرینِ ردیفِ خودِ نماد* خوانده می‌شود، نه از
        # بیشترینِ روزنۀِ کلِ جدول؛ بی‌این قیدِ درونِ نمادی، ساختگی بی‌اثر می‌ماند.
        c2.execute(
            "UPDATE client_type SET buy_i_vol=400000, buy_count_i=2, "
            "                     sell_i_vol=100000, sell_count_i=20 "
            " WHERE ins_code=? AND d_even=(SELECT MAX(ct2.d_even) FROM client_type ct2 "
            "                               WHERE ct2.ins_code = client_type.ins_code)",
            (code_s,))
        c2.commit()
        seed_symbol = c2.execute(
            "SELECT l_val18 FROM instruments WHERE ins_code=?", (code_s,)).fetchone()[0]
    mk._HIST_CACHE_KEY = (None,)
    flags = {}
    recs_by_label = {}
    for label, sql in (("materialized", live_sql), ("monolithic", mono_sql)):
        flags[label], recs_by_label[label] = _pipeline_flags(mk, c2, sql)
    if seed_symbol:
        hit = {k: (seed_symbol in flags[k]["f_jet"]) for k in flags}
        ck("جتِ ساختگی در هر دو مسیر جت است (چکِ بی‌محتوا نبود)",
           all(hit.values()), f"{seed_symbol} → {hit}")
    for k in ("f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh"):
        n = len(flags["materialized"][k])
        m = len(flags["monolithic"][k])
        if n == 0 or m == 0:
            ck(f"فیلترِ {k} رویِ دادهٔ واقعی نماد دارد (چک بی‌محتوا نیست)", False,
               f"materialized={n} monolithic={m}")
            continue
        diff = flags["materialized"][k] ^ flags["monolithic"][k]
        ck(f"فیلترِ {k} در دو مسیر یکی است ({n} نماد)", not diff,
           "" if not diff else f" differences={sorted(diff)[:6]}")

    # «قیمتِ دیروز» درِ نمادهایِ اختیار و حق‌تقدم مقدارِ نگهبانِ ۱ است، پس درصدِ
    # تغییر هیچ‌وقت سنجیده نمی‌شود. fail-safeِ انتهای لوله (fillna(0)) این
    # بی‌مقداری را به «تغییر٪ ۰٫۰۰» تبدیل می‌کرد، یعنی «بدونِ تغییر» رویِ داده‌ای
    # که هیچ‌وقت اندازه گرفته نشده. سنجشِ ۱۴۰۵-۰۷-۰۷ رویِ بانکِ نصبی: ۸۹۳ ردیف.
    recs = recs_by_label["materialized"]
    guard_recs = [r for r in recs if (r.get("price_yesterday") or 0) <= 1]
    ck("ردیفِ نگهبان‌دار درِ بانکِ واقعی هست (چکِ بی‌محتوا نیست)", len(guard_recs) > 0,
       f"{len(guard_recs)} ردیف")
    invented = [r.get("symbol") for r in guard_recs if r.get("percent_change") is not None]
    ck("هیچ ردیفِ نگهبان‌داری درصدِ تغییرِ ساختگی نمی‌گیرد", not invented,
       f"نمونه: {invented[:5]}")
    c2.close()

    print(f"\n{len(PASS)} pass / {len(FAIL)} fail")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
