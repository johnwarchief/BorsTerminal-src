# -*- coding: utf-8 -*-
"""dev/market_snapshot_gen_v1.py — گاردِ «هویتِ عکسِ تابلو» (M1.5، Gate A)

مسئلهٔ اثبات‌شده: revision فقط نوشتنِ زندهٔ `market_watch` را می‌شمارد. نویسندۀ
ایستا (client_type_value، پنجره‌هایِ تاریخ، وضعیت/نظارت) می‌تواند مقدارِ یک
ردیف را عوض کند، `note_static_change()` را صدا بزند و قاب را بسوزاند، بی‌آنکه
revision تکان بخورد. پیش از این، `/api/market/delta?since=همان‌rev` پاسخِ
«unchanged» می‌داد و کلاینتِ دلتایی تا ابد عددِ قدیمی را با برچسبِ زنده نگه
می‌داشت. این گارد همان سناریو را رویِ بانکِ ساختگی (بی‌دادهٔ عملیاتی) می‌سازد
و می‌سنجد:

  ۱) تغییرِ ایستا ⇒ `gen` بالا می‌رود، هرچند `rev` همان است.
  ۲) delta با `gen`ِ کهنه ⇒ `full` (reason=board-changed)، نه unchanged.
  ۳) تیکِ زنده ⇒ `gen` تکان نمی‌خورد و delta همان ردیف را می‌دهد.
  ۴) بازخوانیِ بی‌تغییرِ قاب ⇒ نسلِ بی‌دلیل نمی‌سازد (بدونِ full churn).
  ۵) ETagِ `/api/market/row` با تغییرِ ایستا عوض می‌شود (سایدبار ۳۰۴ِ کهنه نگیرد).
  ۶) delta وقتی قابِ ایستا کهنه است rebuild را تحریک می‌کند و «unchanged» را
     با `rebuilding: true` علامت می‌زند، نه بی‌علامت.

اجرا: `.venv/Scripts/python.exe dev/market_snapshot_gen_v1.py`
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import api.market as M          # noqa: E402
import market_state as MS       # noqa: E402
import test_tsetmc as T         # noqa: E402
import tsetmc_p0_schema         # noqa: E402

FAILS = []
CHECKS = [0]


def ck(label, cond, detail=""):
    CHECKS[0] += 1
    print(("  ok   " if cond else "  FAIL ") + label + ("" if cond else f"  — {detail}"))
    if not cond:
        FAILS.append(label)


class Req:
    def __init__(self, inm=None):
        self.headers = {} if inm is None else {"if-none-match": inm}


def build_fixture():
    """بانکِ فایل‌محور (نویسندۀ دوم واقعاً جدا) با دو نماد و مقادیرِ CTV."""
    d = tempfile.mkdtemp(prefix="bors_gen_")
    path = os.path.join(d, "market.db")
    c = sqlite3.connect(path)
    T.create_schema(c)
    tsetmc_p0_schema.create_all(c)
    rows = [("K1", "نماد۱"), ("K2", "نماد۲")]
    for code, sym in rows:
        c.execute("INSERT INTO instruments (ins_code, l_val18, l_val30, sector_name)"
                  " VALUES (?,?,?,?)", (code, sym, "شرکت" + sym, "صنعت۱"))
        c.execute("INSERT INTO boards (ins_code, board) VALUES (?,?)", (code, "بورس"))
        c.execute(
            "INSERT INTO market_watch (ins_code, d_even, h_even, p_closing, p_last,"
            " q_tot_tran, q_tot_cap, z_tot_tran, price_yesterday, price_change, pe, eps,"
            " price_max, price_min, price_first, allowed_min, allowed_max, buy_q_vol,"
            " buy_q1_vol, sell_q_vol, fetched_at, market_cap, market_cap_src)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (code, 20261014, 110000, 100.0, 100.0, 5000, 5e5, 50, 100, 0.0, 8.0,
             12.0, 105, 98, 100, 90, 110, 10, 5, 9, "2026-10-14 11:00:00",
             1e9, "tsetmc"))
        c.execute("INSERT INTO client_type (ins_code, d_even, buy_i_vol, buy_n_vol,"
                  " sell_i_vol, sell_n_vol, buy_count_i, sell_count_i)"
                  " VALUES (?,?,?,?,?,?,?,?)",
                  (code, 20261014, 3000, 2000, 1000, 500, 30, 10))
        c.execute("INSERT INTO daily_prices (ins_code, d_even, p_closing, q_tot_tran)"
                  " VALUES (?,?,?,?)", (code, 20261014, 100.0, 5000))
        # خریدِ حقیقی ۱۰۰۰ / خریدِ حقوقی ۲۰۰۰ / فروشِ حقیقی ۳۰۰۰ / فروشِ حقوقی ۴۰۰۰
        c.execute("INSERT INTO client_type_value (ins_code, d_even, buy_i_val, buy_n_val,"
                  " sell_i_val, sell_n_val, kind, fetched_at, source)"
                  " VALUES (?,?,?,?,?,?,?,?,?)",
                  (code, 20261014, 1000, 2000, 3000, 4000, "native",
                   "2026-10-14 10:00:00", "tsetmc"))
    c.execute("INSERT INTO tape_history_state (id, newest_d_even) VALUES (1, 20261014)")
    c.commit()
    c.close()
    return d, path


def _row(**kw):
    """ردیفِ کاملِ market_watch با ترتیبِ تک‌منبعِ MW_COLS."""
    d = {"ins_code": "K1", "d_even": 20261014, "h_even": 110000, "p_closing": 100.0,
         "p_last": 100.0, "q_tot_tran": 5000.0, "q_tot_cap": 5e5, "z_tot_tran": 50.0,
         "price_yesterday": 100.0, "price_change": 0.0, "pe": 8.0, "eps": 12.0,
         "price_max": 105.0, "price_min": 98.0, "price_first": 100.0,
         "allowed_min": 90.0, "allowed_max": 110.0, "buy_q_vol": 10.0,
         "buy_q1_vol": 5.0, "sell_q_vol": 9.0,
         "fetched_at": "2026-10-14 11:00:00", "market_cap": 1e9,
         "market_cap_src": "tsetmc"}
    d.update(kw)
    return tuple(d.get(c) for c in T.MW_COLS)


def full():
    resp = M._build_market_response(Req())
    body = resp.body if isinstance(resp.body, bytes) else resp.body.encode()
    d = json.loads(body.decode("utf-8"))
    return d, {r["ins_code"]: r for r in d["data"]}, resp.headers.get("etag")


def delta(since, gen=-1):
    return json.loads(M.get_market_delta(since=since, gen=gen).body.decode("utf-8"))


def set_ctv(path, buy_i, buy_n):
    w = sqlite3.connect(path)
    w.execute("UPDATE client_type_value SET buy_i_val=?, buy_n_val=? WHERE ins_code='K1'",
              (buy_i, buy_n))
    w.commit()
    w.close()


def race_part(path):
    """دو بازسازیِ هم‌زمان نباید کش و آینه را از هم جدا کنند یا عقب ببرند."""
    results = {}
    errors = []

    def build(name):
        try:
            d, by, _ = full()
            results[name] = (d, by)
        except Exception as e:                       # noqa: BLE001
            errors.append((name, repr(e)))

    def start(name):
        t = threading.Thread(target=build, args=(name,), name=name)
        t.start()
        return t

    # ── الف) انتشار جفت‌شده: A داخلِ قفل می‌ماند، B باید صبر کند ─────────
    orig_store = M._market_store
    inside = threading.Event()
    release = threading.Event()

    def slow_store(body, etag, when):
        if threading.current_thread().name == "pair-A":
            inside.set()
            release.wait(5)
        return orig_store(body, etag, when)

    M._market_store = slow_store
    ta = tb = None
    try:
        ta = start("pair-A")
        ck("A داخلِ انتشارِ عکسِ قدیمی ماند", inside.wait(5))
        set_ctv(path, 5000, 6000)          # مقدارِ ایستایِ تازه برایِ B
        MS.note_static_change()
        tb = start("pair-B")
        import time as _t
        _t.sleep(0.3)
        ck("B پشتِ قفلِ انتشار منتظر است (جفت نمی‌شکند)", tb.is_alive())
        release.set()
        ta.join(10)
        tb.join(10)
        cache = json.loads(M._market_snapshot()[0].decode("utf-8"))
        by_code, _m, _c, mrev, _r, mgen, _fk, _bt = M._mirror_snapshot()
        crow = next(r for r in cache["data"] if r["ins_code"] == "K1")
        ck("پس از دو انتشارِ هم‌زمان، کش و آینه یک نسل‌اند",
           cache.get("gen") == mgen and mrev == cache.get("rev"),
           f"cache_gen={cache.get('gen')} mirror_gen={mgen}")
        ck("ردیفِ کش و آینه یکی است",
           crow.get("retail_buy_pct") == by_code["K1"].get("retail_buy_pct"),
           f"{crow.get('retail_buy_pct')} / {by_code['K1'].get('retail_buy_pct')}")
        ck("عکسِ تازه‌تر (B) برنده شد",
           results.get("pair-B", ({}, {}))[1]["K1"]["retail_buy_pct"]
           == by_code["K1"].get("retail_buy_pct"),
           str(results.get("pair-B", ({}, {}))[1].get("K1", {}).get("retail_buy_pct")))
        ck("هیچ نخِ ساخت خطا نداد", not errors, str(errors))
    finally:
        M._market_store = orig_store
        if ta is not None and ta.is_alive():
            release.set()
            ta.join(2)
        if tb is not None and tb.is_alive():
            tb.join(2)

    # ── ب) انتشارِ دیررسِ قدیمی‌تر باید رد شود و همان عکسِ تازه برگردد ────
    orig_publish = M._publish
    at_publish = threading.Event()
    go = threading.Event()

    def slow_publish(*a, **k):
        if threading.current_thread().name == "late-A":
            at_publish.set()
            go.wait(5)
        return orig_publish(*a, **k)

    M._publish = slow_publish
    ta = tb = None
    try:
        ta = start("late-A")
        ck("A پیش از انتشارِ عکسِ قدیمی ایستاد", at_publish.wait(5))
        set_ctv(path, 7000, 1000)          # B با نسلِ تازه‌تر منتشر می‌کند
        MS.note_static_change()
        tb = start("late-B")
        tb.join(10)
        ck("B مستقل از A منتشر شد", not tb.is_alive())
        cache_new = json.loads(M._market_snapshot()[0].decode("utf-8"))
        go.set()
        ta.join(10)
        after = json.loads(M._market_snapshot()[0].decode("utf-8"))
        by_code, _m, _c, _r2, _rd, mgen2, _fk2, _bt2 = M._mirror_snapshot()
        ck("انتشارِ کهنه عکسِ تازه را عقب نبرد",
           after.get("gen") == mgen2 and after.get("gen") == cache_new.get("gen"),
           f"after={after.get('gen')} mirror={mgen2} before={cache_new.get('gen')}")
        ck("درخواستِ A هم همان عکسِ منتشرشده را گرفت (نه بدنهٔ کهنه)",
           results.get("late-A", ({}, {}))[0].get("gen") == mgen2,
           str(results.get("late-A", ({}, {}))[0].get("gen")))
        ck("ردیفِ تازه در کش و آینه ماند",
           next(r for r in after["data"] if r["ins_code"] == "K1").get("retail_buy_pct")
           == by_code["K1"].get("retail_buy_pct"))
        ck("نخ‌هایِ مسابقه بی‌خطا", not errors, str(errors))
    finally:
        M._publish = orig_publish
        if ta is not None and ta.is_alive():
            go.set()
            ta.join(2)
        if tb is not None and tb.is_alive():
            tb.join(2)


def main():
    tmp, path = build_fixture()
    user_path = os.path.join(tmp, "user.db")
    M.get_db = lambda: sqlite3.connect(path)
    M.get_user_db = lambda: sqlite3.connect(user_path)
    M.tape_flag_history.record_observations = lambda *a, **k: None
    M.tape_flag_history.note_error = lambda *a, **k: None
    M._observe_universe = lambda *a, **k: None
    MS.reset()
    M._STATIC_FRAME.update({"key": None, "df": None, "sig": None, "gen": 0})
    M._HIST_CACHE_KEY = (None,)
    M._reset_board_cache()
    M._delta_clear()
    try:
        d0, by0, etag0 = full()
        rev0, gen0 = d0["rev"], d0["gen"]
        ck("بدنۀ کامل gen دارد", isinstance(gen0, int) and gen0 >= 0, str(gen0))
        ck("آینه با همان rev/gen/etag ساخته شد",
           M._mirror_snapshot()[3] == rev0 and M._mirror_snapshot()[5] == gen0
           and M._market_snapshot()[2] == etag0)
        ck("delta با نسلِ جاری ⇒ unchanged",
           delta(rev0, gen0)["status"] == "unchanged")

        # ── ۱) بازخوانیِ بی‌تغییر نباید نسل بسازد ─────────────────────────
        MS.note_static_change()
        d1, by1, _ = full()
        ck("اعلامِ ایستایِ بی‌تغییر ⇒ gen ثابت می‌ماند (بی‌full churn)",
           d1["gen"] == gen0 and by1["K1"]["retail_buy_pct"] == by0["K1"]["retail_buy_pct"],
           f"gen={d1['gen']} old={gen0}")

        # ── ۲) تیکِ زنده: gen ثابت، delta همان ردیف ──────────────────────
        # مثلِ tick_live: اول دیسک، بعد commitِ RAM. اگر فقط RAM را عوض کنیم،
        # بازخوانیِ قاب از دیسک عددِ قدیمی را می‌آورد و این تست مسیرِ واقعیِ
        # تیک را نمی‌سنجد.
        w = sqlite3.connect(path)
        w.execute("UPDATE market_watch SET p_closing=150, price_change=50,"
                  " fetched_at='2026-10-14 11:05:00' WHERE ins_code='K1'")
        w.commit()
        w.close()
        wrote = MS.commit([_row(p_closing=150.0, price_change=50.0,
                                fetched_at="2026-10-14 11:05:00")])
        ck("commitِ زنده یک ردیف نوشت", wrote == 1, str(wrote))
        d2, by2, _ = full()
        ck("تیکِ زنده gen را تکان نمی‌دهد",
           d2["gen"] == gen0, f"gen={d2['gen']} old={gen0}")
        ck("revِ تیک بالا رفت", d2["rev"] > rev0, f"rev={d2['rev']} old={rev0}")
        dl_live = delta(rev0, gen0)
        ck("deltaِ نسلِ جاری ردیفِ زنده را می‌دهد (نه full)",
           dl_live["status"] == "delta"
           and [(r["ins_code"], r["p_closing"]) for r in dl_live["rows"]]
           == [("K1", 150.0)],
           str(dl_live.get("status")) + " " + str(dl_live.get("reason", "")))
        ck("بدنۀ کامل همان عددِ تیک را دارد", by2["K1"]["p_closing"] == 150.0)
        row_before = M.market_row(Req(), symbol="نماد۱")
        row_etag_before = row_before.headers.get("etag")

        # ── ۳) تغییرِ ایستا با همان revision ──────────────────────────────
        w = sqlite3.connect(path)
        w.execute("UPDATE client_type_value SET buy_i_val=9000, buy_n_val=100"
                  " WHERE ins_code='K1'")
        w.commit()
        w.close()
        MS.note_static_change()
        d3, by3, etag3 = full()
        ck("تغییرِ CTV در بدنۀ کامل دیده شد",
           by3["K1"]["retail_buy_pct"] != by2["K1"]["retail_buy_pct"],
           f"{by2['K1'].get('retail_buy_pct')} → {by3['K1'].get('retail_buy_pct')}")
        ck("revision همان ماند (تغییر ایستا بود)", d3["rev"] == d2["rev"],
           f"rev={d3['rev']} old={d2['rev']}")
        ck("gen بالا رفت", d3["gen"] > d2["gen"], f"gen={d3['gen']} old={d2['gen']}")
        ck("ETagِ بدنۀ کامل عوض شد", etag3 != etag0)
        dl_old = delta(d3["rev"], d2["gen"])
        ck("delta با genِ کهنه ⇒ full/board-changed، نه unchanged",
           dl_old["status"] == "full" and dl_old.get("reason") == "board-changed",
           str(dl_old.get("status")) + " " + str(dl_old.get("reason", "")))
        ck("delta با genِ تازه ⇒ unchanged",
           delta(d3["rev"], d3["gen"])["status"] == "unchanged")

        # ── ۴) ETagِ سایدبار (row) باید با gen عوض شود ────────────────────
        row_r1 = M.market_row(Req(), symbol="نماد۱")
        row_etag = row_r1.headers.get("etag")
        row_r2 = M.market_row(Req(row_etag), symbol="نماد۱")
        ck("row با ETagِ هم‌خوان ⇒ ۳۰۴", row_r2.status_code == 304)
        ck("row عددِ ایستایِ تازه را دارد",
           json.loads(row_r1.body.decode("utf-8"))["row"]["retail_buy_pct"]
           == by3["K1"]["retail_buy_pct"])
        ck("ETagِ row بعدِ تغییرِ ایستا عوض شد",
           row_etag_before != row_etag and row_etag is not None)

        # ── ۵) قابِ کهنه: delta باید rebuild را تحریک کند ─────────────────
        kicks = {"n": 0}
        orig_kick = M._kick_market_rebuild
        M._kick_market_rebuild = lambda: kicks.__setitem__("n", kicks["n"] + 1)
        try:
            MS.note_static_change()          # قاب سوخت، ولی بازسازی نشده
            dl_stale = delta(d3["rev"], d3["gen"])
            ck("delta قابِ کهنه را rebuilding علامت می‌زند",
               dl_stale["status"] == "unchanged" and dl_stale.get("rebuilding") is True,
               str(dl_stale))
            ck("delta بازسازیِ پس‌زمینه را تحریک کرد", kicks["n"] == 1, str(kicks["n"]))
            # نویسندۀ ناشناخته که note_static_change هم صدا نمی‌زند: سقفِ ۶۰ثانیه
            with M._DELTA_LOCK:
                M._DELTA["built_at"] = 0.0
            dl_old_time = delta(d3["rev"], d3["gen"])
            ck("آینۀ کهنه‌تر از سقف ⇒ rebuilding و rebuild",
               dl_old_time.get("rebuilding") is True and kicks["n"] == 2, str(kicks["n"]))
        finally:
            M._kick_market_rebuild = orig_kick

        # ── ۶) دو بازسازیِ هم‌زمان ────────────────────────────────────────
        race_part(path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILS:
        print("MARKET SNAPSHOT GEN GUARD FAILED: %d" % len(FAILS))
        for f in FAILS:
            print("  -", f)
        sys.exit(1)
    print("MARKET SNAPSHOT GEN GUARD OK (%d checks)" % CHECKS[0])


if __name__ == "__main__":
    main()
