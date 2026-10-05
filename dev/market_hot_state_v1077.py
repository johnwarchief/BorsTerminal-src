# -*- coding: utf-8 -*-
"""dev/market_hot_state_v1077.py — گاردِ «حالتِ داغِ تابلو» (کار #73)

سه ادعا در این دور رویِ مسیرِ زنده گذاشته شده و هر سه باید ثابت شوند، وگرنه
«سریع‌تر شدن» فقط عوض‌کردنِ یک باگ با یک باگِ دیگر است:

  ۱) **دِلتا درست است**: امضا فقط ستون‌هایی را می‌بیند که همان نوبت واقعاً
     نوشته می‌شود. `fetched_at` هرگز دلیلِ نوشتن نیست، و درِ پس از بستنِ بازار
     تغییرِ صف نوشتنی نیست — پس نباید «تغییر» حساب شود.
  ۲) **RAM هرگز جلوتر از دیسک نمی‌رود**: بدنۀ ساخته‌شده از قابِ ایستا +
     overlayِ حالتِ داغ، سطر‌به‌سطر و ستون‌به‌ستون همان بدنه‌ای است که کوئریِ
     مستقیمِ SQLite می‌دهد. (الگویِ همین چک‌سام در board_hist_cache_v1056.)
  ۳) **دلتایِ HTTP بی‌ نقص است**: `/api/market/delta?since=R` یا همان ردیف‌هایِ
     تغییریافته را می‌دهد، یا «unchanged»، یا صریح می‌گوید `full`. هیچ‌وقت
     مجموعه‌ای ناقص از ژورنالِ چرخیده ساخته نمی‌شود.

بی‌شبکه و بی‌market.dbِ واقعی می‌دود: ساختار جدول‌ها از بانکِ مخزن (یا
market.db.lzma) کپی می‌شود و بدنه‌های TSETMC ساختگی‌اند.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import market_state as MS        # noqa: E402
import test_tsetmc as T          # noqa: E402
import api.market as M           # noqa: E402

FAILS = []
CHECKS = [0]


def ck(label, cond, detail=""):
    CHECKS[0] += 1
    print(("  ok   " if cond else "  FAIL ") + label + ("" if cond else f"  — {detail}"))
    if not cond:
        FAILS.append(label)


# ── فیکسچرِ بانک ----------------------------------------------------------
TABLES = ["instruments", "boards", "market_watch", "client_type",
          "price_history", "daily_prices", "tape_history", "tape_history_state"]


def _schema_source():
    plain = os.path.join(REPO, "market.db")
    if os.path.exists(plain):
        return plain
    packed = os.path.join(REPO, "market.db.lzma")
    assert os.path.exists(packed), "no market.db and no market.db.lzma"
    import lzma
    import shutil
    import tempfile
    out = os.path.join(tempfile.mkdtemp(prefix="bors_hot_"), "schema.db")
    with lzma.open(packed) as src, open(out, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return out


def build_fixture(n=12):
    """بانکِ ساختگی با همان ساختارِ واقعی و n نمادِ معامله‌شده."""
    src = sqlite3.connect(f"file:{_schema_source().replace(os.sep, '/')}?mode=ro", uri=True)
    c = sqlite3.connect(":memory:")
    for t in TABLES:
        cols = [r[1] for r in src.execute(f"PRAGMA table_info({t})")]
        assert cols, f"table {t} gone from schema — guard is stale"
        sel = ", ".join(f'NULL AS "{col}"' for col in cols)
        c.execute(f"CREATE TABLE {t} AS SELECT {sel} WHERE 0")
    src.close()
    # کوئریِ تابلو جدول‌هایِ P0 را JOIN می‌کند؛ این‌ها درِ TABLES نیستند چون
    # بانکِ مخزن ممکن است اصلاً آن‌ها را نداشته باشد. تک‌منبعِ DDL صدا زده
    # می‌شود تا فیکسچر و کوئری از یک ساختار بخوانند.
    import tsetmc_p0_schema
    tsetmc_p0_schema.create_all(c)
    # `CREATE TABLE AS` قیدها را کپی نمی‌کند و `INSERT OR REPLACE` بی‌UNIQUE
    # دیگر replace نمی‌کند — همان چیزی که تیکِ زنده رویش تعریف شده. پس کلیدهایِ
    # یکتایِ واقعیِ بانک را برمی‌گردانیم؛ بی‌این، گارد «۲ نوشتن» را سبز می‌دید
    # درحالی‌که بانکِ تست پر از ردیفِ تکراری می‌شد.
    UNIQUE = {"market_watch": ("ins_code",), "instruments": ("ins_code",),
              "boards": ("ins_code",), "daily_prices": ("ins_code", "d_even"),
              "client_type": ("ins_code", "d_even"),
              "tape_history": ("ins_code", "d_even"),
              "price_history": ("symbol", "date")}
    for t, key in UNIQUE.items():
        c.execute(f'CREATE UNIQUE INDEX ux_{t} ON {t} ({", ".join(key)})')
    for i in range(1, n + 1):
        code, sym = f"K{i}", f"نماد{i}"
        c.execute("INSERT INTO instruments (ins_code, l_val18, l_val30, sector_name)"
                  " VALUES (?,?,?,?)", (code, sym, f"شرکت{sym}", "صنعت۱"))
        c.execute("INSERT INTO boards (ins_code, board) VALUES (?,?)", (code, "بورس"))
        c.execute("INSERT INTO market_watch (ins_code, d_even, h_even, p_closing, p_last,"
                  " q_tot_tran, q_tot_cap, z_tot_tran, price_yesterday, price_change, pe, eps,"
                  " price_max, price_min, allowed_min, allowed_max, buy_q_vol, buy_q1_vol,"
                  " sell_q_vol, fetched_at, market_cap, market_cap_src)"
                  " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (code, 20260928, 110000 + i, 100 + i, 101 + i, 5000 + i * 10, 5e5 + i * 10,
                   50 + i, 100, 1.0, 8.0, 12.0, 105 + i, 98, 90, 110, 10, 5, 9,
                   "2026-09-28 11:00:00", 1e9, "tsetmc"))
        c.execute("INSERT INTO client_type (ins_code, d_even, buy_i_vol, buy_n_vol,"
                  " sell_i_vol, sell_n_vol, buy_count_i, sell_count_i)"
                  " VALUES (?,?,?,?,?,?,?,?)", (code, 20260928, 3000, 2000, 1000, 500, 30, 10))
        c.execute("INSERT INTO daily_prices (ins_code, d_even, p_closing, q_tot_tran)"
                  " VALUES (?,?,?,?)", (code, 20260928, 100 + i, 5000 + i * 10))
        for k in range(40):
            d = 20260928 - k - 1
            c.execute("INSERT INTO tape_history (ins_code, d_even, price_min, price_max,"
                      " q_tot_tran5j) VALUES (?,?,?,?,?)",
                      (code, d, 90 + (k % 5), 110 + (k % 7), 3000 + i * 100 + k))
            c.execute("INSERT OR REPLACE INTO price_history (symbol, date, open, high, low,"
                      " close, volume) VALUES (?,?,?,?,?,?,?)",
                      (sym, f"{d//10000}-{(d//100)%100:02d}-{d%100:02d}", 100 + k, 105 + k,
                       95 + k % 7, 102 + k, 1000 + k * 10))
    c.execute("INSERT INTO tape_history_state (id, newest_d_even) VALUES (1, 20260928)")
    c.commit()
    return c


class _NoClose:
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

    def rollback(self):
        # pandas رویِ خطایِ SQL اول rollback صدا می‌زند؛ بی‌این، AttributeError
        # جایِ خطایِ واقعیِ کوئری را می‌گیرد.
        return self._real.rollback()

    def close(self):
        pass


class Req:
    headers = {}


_SQL_RUNS = {"n": 0}


def _use(conn):
    """get_db/pd را جایِ واقعی می‌گیرد و شمارشِ کوئریِ تابلو را صفر می‌کند."""
    import pandas as real_pd

    class Shim:
        def read_sql_query(self, query, con, *a, **k):
            _SQL_RUNS["n"] += 1
            return real_pd.read_sql_query(query, con, *a, **k)

        def __getattr__(self, n):
            return getattr(real_pd, n)

    M.pd = Shim()
    M.get_db = lambda: _NoClose(conn)


def board_payload():
    out = M._build_market_response(Req())
    body = out.body if isinstance(out.body, (bytes, bytearray)) else out.body.encode()
    d = json.loads(body.decode("utf-8"))
    return d, {r["ins_code"]: r for r in d["data"]}


# ── ۱) معناشناسیِ خودِ market_state ------------------------------------
def unit_part():
    MS.reset()
    a = list(T.MW_COLS)                  # ترتیبِ تک‌منبع
    row = lambda **kw: _row(a, **kw)

    r1 = row(ins="A", pcl=100.0, vol=500.0, fa="2026-09-28 11:00:00")
    ck("RAMِ خالی ⇒ هر ردیف «تغییر» است (بی‌خطرترین حالتِ شکست)",
       len(MS.diff([r1])) == 1)
    MS.commit([r1])
    ck("بعد از commit ⇒ همان ردیف بی‌تغییری", MS.diff([r1]) == [])
    rev0 = MS.revision()
    MS.commit([r1])
    ck("commitِ بی‌تغییری revision را بالا نمی‌برد", MS.revision() == rev0)

    r2 = row(ins="A", pcl=101.0, vol=500.0, fa="2026-09-28 11:00:05")
    ck("تغییرِ قیمت ⇒ دِلتا", [w[0] for w in MS.diff([r2])] == ["A"])
    MS.commit([r2])
    ck("commitِ تغییریافته revision را بالا می‌برد", MS.revision() == rev0 + 1,
       f"rev={MS.revision()} rev0={rev0}")
    r3 = row(ins="A", pcl=101.0, vol=500.0, fa="2026-09-28 11:05:00")
    ck("تغییرِ *فقط* fetched_at ⇒ بی‌دِلتا (و بی‌نوشتن و بی‌rebuild)",
       MS.diff([r3]) == [])

    # درِ پس از بستن: صف‌ها نوشته نمی‌شوند، پس نباید «تغییر» باشند. یک
    # commitِ این حالت پیش‌نیاز است — امضایِ حالتِ دیگر (کامل) با این مقابله
    # نمی‌شود، و گاردِ «_stored_sig» دقیقاً همین را ثابت می‌کند.
    F = MS.AFTER_HOURS_FIELDS
    MS.commit([row(ins="A", pcl=101.0, vol=500.0)], F)
    q = row(ins="A", pcl=101.0, vol=500.0, buy_q=99.0)
    ck("پس از بستن: تغییرِ صف درِ امضا نیست", MS.diff([q], F) == [])
    ck("پس از بستن: همان تغییر برایِ مسیرِ کامل *نوشتنی* است", MS.diff([q]) != [])
    n_q = MS.stats()["rows_written"]
    MS.commit([q], F)
    ck("commitِ بی‌نوشتنی ⇒ نه revision و نه شمارِ نوشتن",
       MS.stats()["rows_written"] == n_q)

    # RAM باید دقیقاً دیسک باشد: عددِ زنده نشست، صف از آخرینِ نوشتنِ کامل بماند
    live = MS.rows_for(["A"])["A"]
    ck("patch رویِ ردیفِ کامل می‌نشیند و صفِ ننوشته‌شده را نمی‌سوزاند",
       live[3] == 101.0 and live[T.MW_COLS.index("buy_q_vol")] == 5.0,
       f"pcl={live[3]} buy_q_vol={live[T.MW_COLS.index('buy_q_vol')]}")

    # ژورنال و بازه‌ها
    MS.reset()
    for i in range(1, 6):
        rw = row(ins="A", pcl=100.0 + i)
        MS.commit([rw])
    ck("codes_between(2,4) دقیقاً ویرایش‌هایِ ۳ و ۴ را می‌بیند (Set A)",
       MS.codes_between(2, 4) == {"A"} and MS.changed_since(2) == {"A"})
    ck("since == revision ⇒ مجموعهٔ تهی، نه None (پاسخ «unchanged» مجاز است)",
       MS.changed_since(MS.revision()) == set())
    ck("since جلوتر از سروِکننده ⇒ None ⇒ بدنۀ کامل", MS.codes_between(9, 4) is None)
    MS.reset()
    ck("ژورنالِ خالی و rev>0 ⇒ None (بی‌ادعایِ دلتا)",
       MS.commit([row(ins="Z", pcl=1.0)]) == 1 and MS.codes_between(0, 1) == {"Z"})

    # prime: سینکِ کامل همه‌چیز را نوشت و patchها را می‌سوزاند
    MS.reset()
    MS.commit([row(ins="A", pcl=101.0)], F)
    ck("پیش از prime، ردیفِ فقط-patch درِ rows_for نیست", MS.rows_for(["A"]) == {})
    r_before = MS.revision()
    MS.prime([row(ins="A", pcl=200.0)])
    ck("prime هم sync_count را بالا می‌برد هم patch را پاک می‌کند",
       MS.sync_count() == 1 and MS.stats()["patched"] == 0
       and MS.rows_for(["A"])["A"][3] == 200.0)
    # prime «نوشتنِ کامل» است، نه تغییرِ داده ⇒ revision بالا نمی‌رود؛ کلیدِ
    # سوختنِ قابِ ایستا sync_count است، وگرنه هر سینکِ ۹۰ ثانیه یک rebuildِ
    # بی‌محتوا می‌ساخت.
    ck("prime بی‌revisionِ تازه (سینکِ کامل = همان دادهٔ رویِ دیسک)",
       MS.revision() == r_before and MS.sync_count() == 1)

    # زنده‌خوانیِ کندل و اشتراکِ عمق
    MS.commit([row(ins="A", pcl=210.0, vol=640.0)])
    v = MS.live_view("A")
    ck("live_view آخرینِ عددِ ثانیه‌ای را از RAM می‌دهد",
       v is not None and v[0] == 210.0 and v[2] == 640.0, str(v))
    MS.subscribe_orderbook("A")
    ck("اشتراکِ عمق فقط همان نماد است", MS.subscriptions() == frozenset({"A"}))
    ck("resetِ سخت هر سه نقشه را خالی می‌کند",
       (MS.reset(), MS.stats()["symbols"], MS.stats()["subscribed"]) == (None, 0, 0))


def _row(order, **kw):
    """ردیفِ market_watch با ترتیبِ تک‌منبعِ `MW_COLS` (نه جایگاهی)."""
    d = {"ins_code": "A", "d_even": 20260928, "h_even": 110000, "p_closing": 100.0,
         "p_last": 100.0, "q_tot_tran": 500.0, "q_tot_cap": 5e4, "z_tot_tran": 10.0,
         "price_yesterday": 100.0, "price_change": 0.0, "pe": 8.0, "eps": 1.0,
         "price_max": 105.0, "price_min": 95.0, "allowed_min": 90.0,
         "allowed_max": 110.0, "buy_q_vol": 5.0, "buy_q1_vol": 2.0, "sell_q_vol": 4.0,
         "fetched_at": "2026-09-28 11:00:00", "market_cap": 1e9, "market_cap_src": "tsetmc"}
    alias = {"ins": "ins_code", "pcl": "p_closing", "vol": "q_tot_tran",
             "fa": "fetched_at", "buy_q": "buy_q_vol", "d": "d_even"}
    for k, v in kw.items():
        d[alias.get(k, k)] = v
    return tuple(d.get(c) for c in order)


# ── ۲) برابریِ بدنه: RAM-overlay در برابرِ کوئریِ مستقیم -----------------
def board_part():
    conn = build_fixture()
    _use(conn)
    MS.reset()
    M._HIST_CACHE_KEY = (None,)
    M._reset_board_cache()

    d0, by0 = board_payload()
    ck("مسیرِ SQL کوئریِ تابلو را زد", _SQL_RUNS["n"] >= 1, str(_SQL_RUNS["n"]))
    ck("بدنه بی‌فیلدهایِ بی‌خواننده ساخته شد",
       all("eps" not in r and "p_max" not in r and "d_even" not in r
           for r in d0["data"]),
       str(sorted(k for k in d0["data"][0])[:6]))
    ck("بی‌تیکِ زنده، متا از کوئری می‌آید (نه صفرِ جعلی)",
       d0["meta"]["d_even"] in (None, 20260928) and MS.last_cycle_at() == "",
       str(d0["meta"]))

    # تیکِ زنده رویِ همان بانک: دو نماد نو می‌شوند، بقیه دست‌نخورده می‌مانند
    raw = [_mw("K3", pcl=130.0, vol=9000.0), _mw("K7", pcl=170.0, vol=7000.0)]
    _sent = {"n": 0}

    def fake_get(s, url, key=None, timeout=90):
        _sent["n"] += 1
        return raw
    orig_pg, T.polite_get = T.polite_get, fake_get
    orig_dt = T.datetime
    import datetime as _dt
    import types as _types

    class _Day:
        def weekday(self):
            return 0

        def strftime(self, fmt):
            return "20260928"

    class _Now:
        def strftime(self, fmt):
            return "1105" if fmt == "%H%M" else "2026-09-28 11:05:00"

    class _D:
        @classmethod
        def today(cls):
            return _Day()

    class _DT:
        @classmethod
        def now(cls):
            return _Now()

    T.datetime = _types.SimpleNamespace(date=_D, datetime=_DT)
    try:
        wrote = T.tick_live(conn)
        ck("تیک فقط ردیف‌هایِ تغییریافته را نوشت (۲ از ۱۲)", wrote == 2, str(wrote))
        ck("RAM همان دو نماد را دید", MS.stats()["rows_written"] == 2)

        # نخستین بازسازیِ پس از اولین تیک، روزِ نشستِ تازه را در کلید می‌بیند
        # (day از ۰ به ۲۰۲۶۰۹۲۸) و یک بار دیگر از بانک می‌خواند؛ از آن به بعد
        # سیکل‌ها بی‌کوئری‌اند.
        d1, by1 = board_payload()
        before = _SQL_RUNS["n"]
        d1b, by1b = board_payload()
        ck("بازسازیِ steady-state هیچ کوئریِ تابلو نزد (SQLite بیرونِ مسیرِ زنده)",
           _SQL_RUNS["n"] == before, f"before={before} after={_SQL_RUNS['n']}")
        d1, by1 = d1b, by1b
        ck("عددِ تازه در بدنه نشست", by1["K3"]["p_closing"] == 130.0
           and by1["K7"]["tvol"] == 7000.0, str(by1["K3"].get("p_closing")))
        ck("درصدِ تغییرِ تازه محاسبه شد (مشتقات رویِ overlay می‌چرخند)",
           by1["K3"]["percent_change"] == 30.0, str(by1["K3"].get("percent_change")))
        ck("متا از ضربانِ سیکلِ تیک آمد", d1["meta"]["d_even"] == 20260928
           and d1["meta"]["last_sync"].startswith("2026-"), str(d1["meta"]))

        # چک‌سام: همان لحظه از دو مسیر — RAM-overlay در برابرِ SQLite
        M._reset_board_cache()
        d2, by2 = board_payload()
        bad = _cmp_records(d1["data"], by2)
        ck("دو مسیرِ یکسان: سطر‌به‌سطر و ستون‌به‌ستون برابر", not bad,
           str(bad[:3]))
        ck("چکِ بی‌محتوا نبود: بدنه‌ها با دقتِ یکسان مقابله شدند",
           len(by2) == len(by1) and by1["K3"]["p_closing"] == by2["K3"]["p_closing"])

        # ── درِ ابزارِ ممیزی: ?fields=all بی‌کش ─────────────────────────
        before_body, before_etag, _ = M._market_snapshot()
        r_all = M.get_market(Req(), fields="all")
        b_all = json.loads((r_all.body if isinstance(r_all.body, bytes)
                            else r_all.body.encode()).decode("utf-8"))
        keys_all = set(b_all["data"][0])
        ck("?fields=all ستون‌هایِ بی‌خواننده را برایِ ابزارِ ممیزی برمی‌گرداند",
           {"eps", "p_max", "p_min", "suspicious_vol", "d_even", "prev_day_vol",
            "tmax", "vol_trend"} <= keys_all,
           str(sorted({"eps", "p_max", "d_even", "tmax"} - keys_all)))
        ck("بدنۀ عادی همان ستون‌ها را نمی‌فرستد (وگرنه صرفِ ۴۵٪ معنا ندارد)",
           not ({"eps", "p_max", "suspicious_vol"} & set(d1b["data"][0].keys())))
        after_body, after_etag, _ = M._market_snapshot()
        ck("و این بدنۀ ابزار جایِ کشِ تابلو را نمی‌گیرد (برقی‌ماندِ یکسان)",
           after_etag == before_etag and after_body == before_body)

        # ── ۳) endpoint دلتا ────────────────────────────────────────────
        rev0 = MS.revision()
        # `raw` همان متغیری است که fake_get برمی‌گرداند — پس *همین نام* باید
        # عوض شود؛ بی‌این تیکِ دوم همان بدنهٔ اول را می‌داد و «wrote=0» را
        # گارد به‌عنوان باگِ محصول می‌خواند (باگِ خودِ گارد بود).
        raw = [_mw("K5", pcl=150.0, vol=5000.0), _mw("K3", pcl=135.0, vol=9500.0)]
        wrote2 = T.tick_live(conn)
        ck("تیکِ دوم دو ردیفِ دیگر را نوشت", wrote2 == 2 and MS.revision() > rev0,
           f"wrote={wrote2} rev={MS.revision()}")
        _SQL_RUNS["n"] = 0
        M.warm_market_cache()
        dl = json.loads(M.get_market_delta(since=rev0).body.decode("utf-8"))
        ck("دلتا فقط K3 و K5 را فرستاد (نه کلِ تابلو)",
           dl["status"] == "delta" and sorted(r["ins_code"] for r in dl["rows"])
           == ["K3", "K5"], str(dl.get("status")) + " " + str(dl.get("reason", "")))
        ck("ردیفِ دلتا همان عددِ بدنهٔ کامل است",
           {r["ins_code"]: r["p_closing"] for r in dl["rows"]} == {"K3": 135.0, "K5": 150.0},
           str([(r["ins_code"], r["p_closing"]) for r in dl["rows"]]))
        dl2 = json.loads(M.get_market_delta(since=dl["rev"]).body.decode("utf-8"))
        ck("since == revِ آینه ⇒ unchanged با صفر ردیف", dl2["status"] == "unchanged",
           str(dl2))
        dl3 = json.loads(M.get_market_delta(since=9999).body.decode("utf-8"))
        ck("کلاینتِ جلوتر ⇒ full، نه دلتایِ ساختگی", dl3["status"] == "full", str(dl3))
        dl4 = json.loads(M.get_market_delta(since=-1).body.decode("utf-8"))
        ck("کلاینتِ بی‌rev ⇒ full", dl4["status"] == "full", str(dl4))
        # ژورنالِ چرخیده: هیچ دلتایِ ناقصی از آن ساخته نمی‌شود
        for i in range(1, 400):
            # ردیفِ *واقعاً* ساختۀ _mw_row (همان نگاشتِ نوشتن)، نه بدنهٔ خام —
            # commit رویِ tupleِ ستون‌ها کار می‌کند.
            _t = T._mw_row(_mw("K1", pcl=100.0 + i, vol=1000.0), 20260928,
                           20260928, "2026-09-28 11:05:00")
            MS.commit([_t[1]])
        gap = json.loads(M.get_market_delta(since=rev0).body.decode("utf-8"))
        ck("ژورنالِ چرخیده ⇒ full (بی‌دلتایِ نصفه)", gap["status"] == "full", str(gap))
    finally:
        T.polite_get = orig_pg
        T.datetime = orig_dt
        M.pd = __import__("pandas")
        conn.close()


def _mw(ins, pcl, vol):
    """بدنۀ خامِ GetMarketWatch برایِ یک نماد (همان شکلِ فیکسچرِ market_tick)."""
    return {"insCode": ins, "lva": "نام", "lvc": "شرکت", "csv": "S1", "dEven": 20260928,
            "hEven": 110500, "pcl": pcl, "pdv": pcl, "py": 100.0, "pf": pcl,
            "pmn": pcl * 0.95, "pmx": pcl * 1.05, "pMin": 92.0, "pMax": 110.0,
            "qtj": vol, "qtc": pcl * vol, "ztt": 50.0, "pc": (pcl - 100.0), "eps": 5.0,
            "pe": 10.0, "ztd": 1000.0, "bv": 50.0}


def _cmp_records(ram_rows, sql_by_code):
    """ستون‌به‌ستون؛ واگرایی‌ها را برمی‌گرداند (تهی ⇒ برابری)."""
    bad = []
    for r in ram_rows:
        code = r["ins_code"]
        s = sql_by_code.get(code)
        if s is None:
            bad.append(f"{code}: absent from SQL body")
            continue
        for k, v in r.items():
            sv = s.get(k)
            if isinstance(v, float) and isinstance(sv, (int, float)):
                if abs(v - sv) > 1e-9:
                    bad.append(f"{code}.{k}: ram={v} sql={sv}")
            elif v != sv:
                bad.append(f"{code}.{k}: ram={v!r} sql={sv!r}")
        for k, sv in s.items():
            if k not in r:
                bad.append(f"{code}.{k}: missing in ram body (sql={sv!r})")
    if len(sql_by_code) != len(ram_rows):
        bad.append(f"row count ram={len(ram_rows)} sql={len(sql_by_code)}")
    return bad


def wiring_part():
    """قراردادِ بینِ app.py و market_state: rebuild فقط با تغییرِ داده."""
    src = open(os.path.join(REPO, "app.py"), encoding="utf-8").read()
    m2 = re.search(r"def _board_tick_loop\(.*?\n    try:", src, re.DOTALL)
    blk = m2.group(0) if m2 else ""
    ck("حلقۀ تیک بازسازی را به revision گره زده، نه به «تیک خورد»",
       "market_state" in blk or "_MS" in blk, blk[:120])
    ck("و بی‌تغییری _kick_market_rebuild را صدا نمی‌زند",
       blk.count("_kick_market_rebuild()") == 1 and "rev != last_rev" in blk, blk[:400])
    tsrc0 = open(os.path.join(REPO, "test_tsetmc.py"), encoding="utf-8").read()
    for name in ("_save_market_snapshot", "main"):
        b = _block(tsrc0, name)
        ck(f"{name} با prime() حالتِ داغ را هم‌خطِ دیسک می‌کند", "market_state.prime" in b,
           f"block={len(b)} chars: {b[:80]}")
    tsrc = open(os.path.join(REPO, "test_tsetmc.py"), encoding="utf-8").read()
    tb = _block(tsrc, "tick_live")
    ck("tick_live دِلتا را با ستون‌هایِ همان نوبت می‌سنجد",
       "market_state.diff(watch, fields)" in tb and "AFTER_HOURS_FIELDS" in tb)
    ck("و commit پس از SQLite.commit انجام می‌شود (نه پیش از آن)",
       tb.index("conn.commit()") < tb.index("market_state.commit("))
    # hiddenimports: ماژولِ جدید در یخِ PyInstaller دیده شود
    spec = open(os.path.join(REPO, "fts_terminal.spec"), encoding="utf-8").read()
    ck("market_state در hiddenimportsِ فrozen هست (وگرنه EXE می‌میرد)",
       "market_state" in spec, spec[:80])


def _block(src, name):
    """بدنۀ تابعِ *سطح‌اول* (def در ستونِ صفر) تا def/next-top-level بعدی.

    نسخهٔ پیشین `src.find(name)` بود و نامِ تابع در docstring و کامنتِ توابعِ
    دیگر هم می‌آمد — گارد بدنهٔ اشتباه را می‌خواند و «prime نیست» می‌گفت.
    """
    m = re.search(r"^def %s\b.*?(?=\n(?:def |class |@|if __name__))" % re.escape(name),
                  src, re.DOTALL | re.MULTILINE)
    return m.group(0) if m else ""


def main():
    unit_part()
    board_part()
    wiring_part()
    print("\nmarket_hot_state_v1077: %d passed / %d failed"
          % (CHECKS[0] - len(FAILS), len(FAILS)))
    if FAILS:
        for f in FAILS:
            print("  FAILED:", f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
