# dev/tape_flag_history_v1.py — گاردِ سابقۀ ماندگارِ هفت فیلترِ تابلو
#
# مأموریتِ پروندۀ نماد (۱۴۰۵-۰۷-۲۱)، بخشِ سوم: «کاربر باید بداند یک نماد در چند
# روزِ اخیر چند بار هر فیلتر تابلوخوانی را داشته است» و «اگر سابقه ذخیره نمی‌شود،
# سازوکار ماندگار و قابل‌تکرار برای ثبت مشاهده‌های جدید طراحی کن».
#
# این سوئیت رویِ یک بانکِ موقت می‌زند و چهار چیز را ثابت می‌کند که بی‌آن‌ها سابقه
# بی‌معنی است:
#   ۱) یک روز = یک ردیف (کلیدِ سه‌تایی)؛ اجرایِ دوبل همان داده «دفعات» را دو نمی‌کند
#   ۲) روزِ ثبت‌نشده ≠ روزِ بی‌فیلتر («ثبت نشده» در برابر «غیرفعال»)
#   ۳) ماضی بازسازی نمی‌شود — `reliable_from` اولین روزِ رصدِ واقعی است
#   ۴) نوشتنِ سابقه نمی‌تواند تابلو را بشکند (استثنا بلعیده و گزارش می‌شود)
#
# اجرا:  python dev/tape_flag_history_v1.py

import json
import os
import sqlite3
import sys
import tempfile

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import tape_flag_history as H  # noqa: E402

MARKET_PY = os.path.join(ROOT, "api", "market.py")
SPEC = os.path.join(ROOT, "fts_terminal.spec")

PASS = FAIL = 0


def ck(cond, what, got=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {what}")
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  -> {got}" if got else ""))


def frame(day, on):
    """قابِ تابلو، همان شکلی که `api/market` می‌دهد: ایندکس = ins_code."""
    rows = []
    for code, flags in on.items():
        r = {"ins_code": code, "d_even": day, "symbol": "آزمون-" + code,
             "tvol": 4_000_000.0,
             "p_closing": 1000.0, "p_last": 1025.0, "percent_last": 4.6,
             "z_tot_tran": 120.0, "vol_ratio_file": 1_000_000.0,
             "buyer_power_raw": float("nan"), "resistance_59": 59.0,
             "is6": 1_000_000.0}
        for f in H.FLAGS:
            r[f] = f in flags
        rows.append(r)
    df = pd.DataFrame(rows).set_index("ins_code")
    for f in H.FLAGS:                       # قابِ واقعی NaN را از پیش False کرده
        df[f] = df[f].fillna(False).astype(bool)
    return df


def main():
    tmp = os.path.join(tempfile.gettempdir(), "tfh_guard_v1.db")
    if os.path.exists(tmp):
        os.remove(tmp)
    # کفِ زمانیِ نوبت‌ها درِ گارد صفر می‌شود تا «نشانه» تنها داور بماند
    H.FLUSH_S = 0.0
    H._ensured = False
    H._last_flush.clear()
    H._last_token.clear()
    H._last_err = None

    conn = sqlite3.connect(tmp)
    H.ensure(conn)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    ck(set(H.TABLES) <= names, "هر دو جدول ساخته می‌شوند", str(sorted(names)))
    ck(conn.execute("SELECT COUNT(*) FROM tape_flag_day").fetchone()[0] == 0,
       "جدولِ خالی هیچ ردیفِ ساختگی‌ای ندارد")
    ck(H.reliable_from(conn) is None, "پیش از اولین رصد: reliable_from = None (هیچ روزی قابل‌اعتماد نیست)")

    d1, d2 = 20261010, 20261011
    n = H.record_observations(conn, frame(d1, {"A+": {"f_susp", "f_jet"},
                                               "B": {"f_susp"}}), d1, token=1)
    ck(n == 3, "نوبتِ اول: سه مشاهده (A+ دو فیلتر، B یک فیلتر)", str(n))
    ck(conn.execute("SELECT COUNT(*) FROM tape_flag_day").fetchone()[0] == 3,
       "سه ردیف، نه بیشتر")
    ck(H.reliable_from(conn) == d1, "اولین روزِ رصد، همان `reliable_from` است")

    # ── ۱) اجرایِ دوبل با همان نشانه = هیچ (دفعاتِ ساختگی ممنوع) ────────────────
    before = conn.execute("SELECT passes FROM tape_flag_day WHERE ins_code='A+' AND flag='f_susp'").fetchone()[0]
    again = H.record_observations(conn, frame(d1, {"A+": {"f_susp", "f_jet"},
                                                  "B": {"f_susp"}}), d1, token=1)
    ck(again == 0, "همان نشانه ⇒ نوبتی ثبت نمی‌شود", str(again))
    after = conn.execute("SELECT passes FROM tape_flag_day WHERE ins_code='A+' AND flag='f_susp'").fetchone()[0]
    ck(after == before == 1, "`passes` با رفرشِ بی‌داده تکان نمی‌خورد", f"{before}→{after}")

    # ── نشانهٔ نو = یک نوبتِ تازه؛ «اولین بار» و شواهد می‌مانند ──────────────────
    first_at = conn.execute("SELECT first_seen_at, evidence FROM tape_flag_day"
                            " WHERE ins_code='A+' AND flag='f_susp'").fetchone()
    n2 = H.record_observations(conn, frame(d1, {"A+": {"f_susp", "f_jet"},
                                                "B": {"f_susp"}}), d1, token=2)
    ck(n2 == 3, "نشانهٔ نو: نوبتِ دوم ثبت می‌شود", str(n2))
    row = conn.execute("SELECT first_seen_at, passes, evidence, last_seen_at FROM tape_flag_day"
                       " WHERE ins_code='A+' AND flag='f_susp'").fetchone()
    ck(row[0] == first_at[0], "first_seen_at با نوبتِ دوم عوض نمی‌شود")
    ck(row[1] == 2, "passes = شمارۀ نوبت‌هایِ ثبتِ همان روز", str(row[1]))
    ck(row[2] == first_at[1], "شواهد از اولین دیدار می‌مانند")
    ck(conn.execute("SELECT COUNT(*) FROM tape_flag_day").fetchone()[0] == 3,
       "ردیفِ تکراری برایِ همان (نماد، فیلتر، روز) ساخته نشد")
    ck(json.loads(row[2]).get("buyer_power_raw") is None,
       "NaN درِ شواهد کلید نمی‌سازد («بی‌مقدار» با «صفر» یکی نمی‌شود)", row[2])

    # ── نمادِ بدونِ فیلتر: هیچ ردیفی ندارد، نه ردیفِ «خاموش» ─────────────────────
    H.record_observations(conn, frame(d1, {"C": set()}), d1, token=3)
    ck(conn.execute("SELECT COUNT(*) FROM tape_flag_day WHERE ins_code='C'").fetchone()[0] == 0,
       "نمادِ بدونِ فیلترِ روشن ردیفِ «غیرفعال» نمی‌گیرد")

    # ── روزِ دوم ────────────────────────────────────────────────────────────────
    H.record_observations(conn, frame(d2, {"A+": {"f_jet"}, "D": {"f_roobi"}}), d2, token=9)
    cal = H.trading_days(conn)
    ck(cal == [d2, d1], "تقویم = روزهایِ واقعاً رصدشده (کهنه در انتهای فهرست)", str(cal))
    ck(H.reliable_from(conn) == d1, "reliable_from رویِ اولین رصد می‌ماند")

    # ── ۲) «غیرفعال» در برابر «ثبت نشده» ────────────────────────────────────────
    h = H.history_for(conn, ["A+", "B", "D"], days=20)
    a = h["by_symbol"]["A+"]["f_susp"]
    ck(a["total"] == 1 and a["days"][d1]["active"] is True,
       "فیلترِ روشن در روزِ خودش: active")
    ck(a["days"][d2]["active"] is False,
       "روزی که رصد شده ولی فیلتر روشن نبوده ⇒ غیرفعال (نه «بدون داده»)")
    d_fs = h["by_symbol"]["D"]["f_susp"]
    ck(d_fs["total"] == 0 and all(v["active"] is False for v in d_fs["days"].values()),
       "فیلتری که در هر روزِ رصدشده خاموش بوده: همه «غیرفعال»، مجموعِ صفر", str(d_fs["days"]))
    ck(len(h["days"]) == 2, "تقویمِ خروجی فقط دو روزِ رصدشده است", str(h["days"]))
    ck(h["by_symbol"]["A+"]["f_jet"]["total"] == 2,
       "جت در هر دو روز روشن بوده ⇒ مجموعِ دفعات = ۲", str(h["by_symbol"]["A+"]["f_jet"]["total"]))
    ck(h["by_symbol"]["A+"]["f_jet"]["last_seen_at"] is not None
       and h["by_symbol"]["A+"]["f_jet"]["last_seen_at"] >= h["by_symbol"]["A+"]["f_jet"]["days"][d1]["last_at"],
       "آخرین مشاهده از ردیف‌ها خوانده می‌شود")

    # روزی که هرگز رصد نشده نباید در تقویم ظاهر شود (وگرنه «غیرفعال»ِ ساختگی است)
    ck(20261012 not in h["days"], "روزِ رصدنشده در تقویم نیست ⇒ رابط آن را «ثبت نشده» می‌خواند")

    # ── ۳) نمادِ ناشناس: ساختار می‌آید، داده نمی‌شود ─────────────────────────────
    ck(H.history_for(conn, ["ZZ"], days=5)["by_symbol"]["ZZ"]["f_clock"]["total"] == 0,
       "نمادِ بی‌سابقه: صفر روز، نه «غیرفعال»ِ جعلیِ پرشده")

    # ── ۴) بقا پس از «راه‌اندازی مجدد» ──────────────────────────────────────────
    conn.close()
    H._ensured = False
    conn2 = sqlite3.connect(tmp)
    h2 = H.history_for(conn2, ["A+"], days=20)
    ck(h2["by_symbol"]["A+"]["f_jet"]["total"] == 2,
       "پس از بستن و بازکردنِ اتصال: سابقه درِ بانک است، نه RAM")
    ck(H.reliable_from(conn2) == d1, "reliable_from هم از بانک بازخوانده می‌شود")

    # ── ۵) نویزِ ورودی: نه کرش، نه دادهٔ ساختگی ─────────────────────────────────
    bad = frame(d2, {"E": {"f_susp"}}).drop(columns=["tvol", "is6"])
    ck(H.record_observations(conn2, bad, d2, token=11) == 1,
       "ستونِ شواهدِ غایب نوشتن را متوقف نمی‌کند")
    ev = json.loads(conn2.execute("SELECT evidence FROM tape_flag_day"
                                  " WHERE ins_code='E' AND flag='f_susp'").fetchone()[0])
    ck("tvol" not in ev and "is6" not in ev, "ستونِ نبودِ شواهد نمی‌شود ⇒ درِ JSON هم کلید ندارد", str(ev))
    ck(H.record_observations(conn2, None, d2, token=12) == 0, "قابِ None: صفر، بی‌استثنا")
    ck(H.record_observations(conn2, frame(d2, {"A+": {"f_susp"}}), 0, token=13) == 0,
       "بی‌روزِ معاملاتی: هیچ ردیفی نوشته نمی‌شود")
    conn2.close()

    # ── ۶) سیم‌کشی (تا کسی مسیرِ نوشتن/خواندن را بی‌صدا حذف نکند) ────────────────
    src = open(MARKET_PY, encoding="utf-8").read()
    ck("import tape_flag_history" in src, "api/market ماژول را وارد می‌کند")
    ck("tape_flag_history.record_observations(" in src, "مسیرِ تابلو نویسنده است")
    ck('df[df["is_live"]]' in src, "فقط ردیف‌هایِ زنده ثبت می‌شوند (ماضی بازسازی نمی‌شود)")
    ck('"token=market_state.sync_count()"' in src.replace("\n", " ").replace("  ", " ")
       or "token=market_state.sync_count()" in src, "نوبت‌ها به نشانۀ سینک بند‌اند")
    ck('@router.get("/api/tape-history")' in src, "اندپوینتِ خواندن ثبت شده")
    ck("get_user_db" in src, "سابقه در user.db می‌نشیند (بیس‌لاینِ ریلیز آن را پاک نمی‌کند)")
    spec = open(SPEC, encoding="utf-8").read()
    ck("'tape_flag_history'" in spec, "fts_terminal.spec: hiddenimports (EXE روی اولین درخواست نمیرد)")

    os.remove(tmp)
    print(f"\ntape_flag_history: {PASS} ok / {FAIL} fail")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
