# dev/tsetmc_p0_v1076.py — گاردِ سه P0ِ لایۀ دادهٔ TSETMC
#
#   P0-1  ارزشِ ریالیِ حقیقی/حقوقی از مبدأ (ClientType/GetClientTypeHistory)
#         به‌جایِ حجم×VWAP — با اولویتِ مبدأ و fallbackِ سالم.
#   P0-2  رویدادهایِ شرکتیِ منتشرشده (GetPriceAdjustByFlow،
#         GetInstrumentShareChangeByFlow) درِ مدلِ canonical.
#   P0-3  وضعیتِ نماد / علتِ توقف / نظارت / پیامِ ناظر.
#
# سه حکمی که این سوئیت نگهبانشان است:
#   • مبدأ نباشد ⇒ هیچ ردیفی نمی‌نشیند؛ صفرِ جعلی ممنوع.
#   • بازسازیِ پیشین **حذف نشده** و جایی که مبدأ نیست همان کار می‌کند.
#   • هیچ‌کدام از این سه به فیلتر/گیت/طبقۀ روند وصل نمی‌شوند — چکِ ضدِ نشت.
#
# آفلاین است: هیچ درخواستِ شبکه‌ای نمی‌زند؛ پاسخ‌ها تزریق می‌شوند.
# شکلِ پاسخ‌ها از سنجشِ زندهٔ ۱۴-۰-۱۳ برداشته شده
# (docs/TSETMC-DATA-GAP-MATRIX.md §12/§17 و _audit درِ همان دور).
#
# اجرا:  python dev/tsetmc_p0_v1076.py

import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mstat_engine                      # noqa: E402
import test_tsetmc as T                  # noqa: E402

TS_PY = os.path.join(ROOT, "test_tsetmc.py")
MSTAT_PY = os.path.join(ROOT, "mstat_engine.py")
CHART_PY = os.path.join(ROOT, "api", "chart.py")
MARKET_PY = os.path.join(ROOT, "api", "market.py")
CODAL_PY = os.path.join(ROOT, "codal_fetcher.py")
FLAGS_PY = os.path.join(ROOT, "tape_flags.py")
CONF_PY = os.path.join(ROOT, "confidence_engine.py")
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


# ── پاسخ‌هایِ ضبط‌شده (شکلِ واقعیِ سنجشِ زنده) ────────────────────────────────
LIVE_CTV = {"clientType": {
    "recDate": 20261004, "insCode": "65883838195688438",
    "buy_I_Value": 9795900492781.0, "buy_N_Value": 1424869091632.0,
    "sell_I_Value": 8377684161902.0, "sell_N_Value": 2000000000000.0,
    "buy_DDD_Value": 0.0,
    "buy_I_Volume": 7382767422.0, "buy_N_Volume": 6896035430.0,
    "sell_I_Volume": 13254258707.0, "sell_N_Volume": 1024544145.0,
    "buy_I_Count": 1000, "buy_N_Count": 3, "sell_I_Count": 2000, "sell_N_Count": 5}}

LIVE_ADJ = {"priceAdjust": [
    {"insCode": 0, "dEven": 20261004, "pClosing": 5710.0,
     "pClosingNotAdjusted": 5730.0, "corporateTypeCode": None,
     "instrument": {"insCode": "67690708346979840", "lVal18AFC": "كماسه",
                    "lVal30": "تامين‌ ماسه‌ ريخته‌گري‌"}},
    {"insCode": "67690708346979840", "dEven": 20261003, "pClosing": 11360.0,
     "pClosingNotAdjusted": 11560.0, "corporateTypeCode": 2,
     "instrument": {"lVal18AFC": "كماسه"}}]}

LIVE_SHARE = {"instrumentShareChange": [
    {"dEven": 20261001, "idn": 11, "insCode": "46348559193224090",
     "lVal18AFC": "فولاد", "lVal30": "فولاد مباركه اصفهان",
     "numberOfShareOld": 50000000000.0, "numberOfShareNew": 60000000000.0}]}

LIVE_STATE = {"instrumentState": [
    {"idn": 2060063, "dEven": 20261005, "hEven": 162250, "insCode": "2109854662147869",
     "lVal18AFC": "پاسا3", "lVal30": "ايران‌ياساتايرورابر", "cEtaval": "IS ",
     "realHeven": 0, "underSupervision": 0, "cEtavalTitle": "ممنوع-متوقف"}]}

LIVE_SUP = {"supervision": [
    {"id": 0, "userName": None, "insCode": "33420285433308219",
     "insertionDateTime": "0001-01-01T00:00:00", "underSupervision": 3,
     "underSupervisionTitle": "زیر نظر",
     "reasons": "عدم ارائه صورتهای مالی میاندوره ای<br>عدم ارائه گزارش تفسیری<br>"}]}

LIVE_MSG = {"msg": [
    {"tseMsgIdn": 266456, "dEven": 20261005, "hEven": 162402, "flow": 0,
     "tseTitle": "اطلاعيه درخصوص عدم تاييد كليه معاملات", "tseDesc": "به اطلاع می‌رساند…"}]}

LIVE_STOPS = [
    {"kodenamaddarsamane": None, "nam": "اپال(فرآوری معدنی اپال کانی پارس)",
     "statusCode": 3, "vaziyatdesc": "مشمول فرایند تعلیق",
     "lastdatechange": "1405-07-13", "dalils": ["عدم ارائه گزارش تفسیری",
                                                "عدم ارائه صورتهای مالی"]},
    {"nam": "نمادناشناخته(هیچ)", "statusCode": 2, "vaziyatdesc": "تعلیق شده",
     "lastdatechange": "1405-07-01", "dalils": []}]


def _inst(sym, ins, isin=None):
    return ("INSERT INTO instruments (ins_code, l_val18, l_val30, sector_code,"
            " sector_name, total_shares, eps, pe, base_vol, updated_at, paper_type,"
            " isin, c_gr_val_cot) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ins, sym, sym, "34", "خودرو", 1.0, 1.0, 1.0, 1.0, "now", "stock",
             isin, None))


def fresh_db():
    """بانکِ کوچکِ آزمون با همان create_schemaِ واقعی + ردیف‌هایِ لازم."""
    conn = sqlite3.connect(":memory:")
    T.create_schema(conn)
    conn.execute(*_inst("خودرو", "65883838195688438", "IRO1IKCO0008"))
    conn.execute(*_inst("اپال", "2109854662147869"))
    conn.execute("INSERT INTO client_type (ins_code, d_even, buy_i_vol, buy_n_vol,"
                 " buy_ddd_vol, buy_count_i, buy_count_n, sell_i_vol, sell_n_vol,"
                 " sell_count_i, sell_count_n) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 ("65883838195688438", 20261004, 7382767422.0, 6896035430.0, 0.0,
                  1000, 3, 13254258707.0, 1024544145.0, 2000, 5))
    conn.execute("INSERT INTO market_watch (ins_code, d_even, q_tot_tran, q_tot_cap,"
                 " p_closing, p_last) VALUES (?,?,?,?,?,?)",
                 ("65883838195688438", 20261004, 15624360036.0, 11220769584413.0,
                  718.0, 697.0))
    conn.commit()
    return conn


def board_row(ctv=None):
    """ردیفِ ورودیِ mstat_engine.money — همان شکلی که _scan می‌سازد."""
    return {"ins_code": "65883838195688438", "q_vol": 15624360036.0,
            "q_val": 11220769584413.0, "p_closing": 718.0, "n_trades": 28943.0,
            "base_vol": 1000000.0, "buy_q_val": 1.0, "sell_q_val": 0.0,
            "ct": ("65883838195688438", 7382767422.0, 6896035430.0, 0.0,
                   1000, 3, 13254258707.0, 1024544145.0, 2000, 5),
            "ctv": ctv}


# ═════════════ P0-1 — ارزشِ مبدأ‌محور ═════════════
def part_ctv():
    print("\n[P0-1] ClientType: native value")
    rec = T.parse_client_type_value(LIVE_CTV, "65883838195688438", 20261004, "now")
    ck(rec is not None, "پاسخِ واقعیِ clientType (شیء، نه آرایه) خوانده می‌شود")
    ck(rec[2] == 9795900492781.0 and rec[4] == 8377684161902.0,
       "buy_I_Value و sell_I_Value عینِ مبدأ می‌نشینند (بدونِ ضرب)", str(rec[:5]))
    ck(rec[1] == 20261004 and rec[9] == T.CTV_SOURCE,
       "recDate و برچسبِ منبع درِ ردیف هست", str(rec))
    ck(rec[7] == "native",
       "kind درِ همان ردیف می‌نشیند (provenance یک‌بار درِ نویسنده حساب می‌شود)",
       str(rec[7]))
    half = T.parse_client_type_value(
        {"clientType": {"recDate": 20261004, "buy_I_Value": 5.0,
                        "sell_I_Value": 7.0}}, "x", 20261004, "n")
    ck(half is not None and half[7] == "mixed",
       "دو ارزشِ خالی و دو ارزشِ پر ⇒ kind = mixed (نه native)", str(half and half[7]))

    ck(T.parse_client_type_value(LIVE_CTV["clientType"], "x", 1, "n") is not None,
       "ورودیِ بی‌wrapper (خودِ dict) هم پذیرفته می‌شود")
    ck(T.parse_client_type_value([LIVE_CTV["clientType"]], "x", 1, "n") is not None,
       "ورودیِ آرایه‌ای هم پذیرفته می‌شود")
    ck(T.parse_client_type_value({"clientType": {"recDate": 20261004}}, "x", 1, "n") is None,
       "پاسخِ بی‌ارزش ⇒ None (صفرِ جعلی ساخته نمی‌شود)")
    ck(T.parse_client_type_value(None, "x", 1, "n") is None
       and T.parse_client_type_value([], "x", 1, "n") is None,
       "پاسخِ خالی/None ⇒ None")
    zero = T.parse_client_type_value(
        {"clientType": {"recDate": 20261004, "buy_I_Value": 0.0,
                        "buy_N_Value": 0.0, "sell_I_Value": 0.0,
                        "sell_N_Value": 0.0}}, "x", 1, "n")
    ck(zero is not None and zero[2] == 0.0,
       "صفرِ واقعیِ مبدأ «صفر» خوانده می‌شود، نه «نبودِ داده»", str(zero))

    # ── اولویتِ مبدأ بر بازسازی، و سالم‌ماندنِ fallback ──
    vwap = 11220769584413.0 / 15624360036.0
    recon_buy = 7382767422.0 * vwap
    m_rec = mstat_engine.money(board_row(ctv=None), {})
    ck(abs(m_rec["retail_buy"] - recon_buy) < 1.0,
       "بی‌ردیفِ مبدأ ⇒ همان حجم×VWAPِ پیشین (fallback حذف نشده)",
       f'{m_rec["retail_buy"]:.0f} vs {recon_buy:.0f}')
    ck(m_rec["value_source"] == "reconstructed", "provenance = reconstructed")

    nat = ("65883838195688438", 9795900492781.0, 1424869091632.0,
           8377684161902.0, 2000000000000.0, 0.0)
    m_nat = mstat_engine.money(board_row(ctv=nat), {})
    ck(m_nat["retail_buy"] == 9795900492781.0,
       "مبدأ بر بازسازی اولویت دارد و عیناً می‌نشیند", str(m_nat["retail_buy"]))
    ck(m_nat["retail_sell"] == 8377684161902.0
       and m_nat["inst_buy"] == 1424869091632.0
       and m_nat["inst_sell"] == 2000000000000.0,
       "هر چهار خانۀ ارزش از مبدأ خوانده می‌شود")
    ck(m_nat["value_source"] == "native", "provenance = native")
    ck(abs(m_nat["retail_buy"] - m_rec["retail_buy"]) > 1e9,
       "مبدأ و بازسازی درِ این نمونه واقعاً فرق دارند (چکِ بی‌معنا نمی‌شود)")

    # نگاشتِ I/N — همان که درِ پاریتیِ زنده ثابت شده؛ fima وارونه‌اش می‌کند
    ck(m_rec["retail_buy"] > 0 and m_rec["inst_buy"] > 0
       and abs(m_rec["retail_buy"] - 7382767422.0 * vwap) < 1.0
       and abs(m_rec["inst_buy"] - 6896035430.0 * vwap) < 1.0,
       "I = حقیقی (retail) و N = حقوقی (inst) — نگاشتِ I/N دست‌نخورده")
    src = open(MSTAT_PY, encoding="utf-8").read()
    ck('"retail_buy", "buy_i_val", "buy_i_vol"' in src
       and '"inst_buy", "buy_n_val", "buy_n_vol"' in src,
       "ترتیبِ slotها درِ money همان I→retail / N→inst می‌ماند")

    # سرانه و قدرت: VWAP درِ نسبت ساده می‌شود (ادعایِ کامنت، حالا سنجیده)
    m_half = mstat_engine.money(
        board_row(ctv=("65883838195688438", 9795900492781.0, None,
                       8377684161902.0, None, None)), {})
    ck(m_half["value_source"] == "mixed",
       "دو خانۀ مبدأ و دو خانۀ بازسازی ⇒ provenance = mixed", m_half["value_source"])
    ck(abs(m_half["retail_buy"] - 9795900492781.0) < 1.0
       and abs(m_half["inst_buy"] - 6896035430.0 * vwap) < 1.0,
       "درِ حالتِ mixed، خانۀ مبدأ native و خانۀ خالی reconstructed می‌ماند")

    m_rec2 = mstat_engine.money(board_row(ctv=None), {})
    ck(abs(m_rec2["power"] - ((7382767422.0 / 1000) / (13254258707.0 / 2000))) < 1e-9,
       "قدرت خریدار رویِ مبنایِ بازسازی از VWAP مستقل است (ساده می‌شود)")

    # ── نویسنده: تهیۀ ردیف، بی‌صفرِ جعلی، با throttle ──
    conn = fresh_db()
    calls = []

    def fake_fetch(code):
        calls.append(code)
        return LIVE_CTV if code.endswith("38") else None

    st = T.refresh_client_type_values(conn, day=20261004, fetch=fake_fetch,
                                      now="2026-10-05 13:00:00", force=True)
    ck(st["written"] == 1 and len(calls) >= 1,
       "نویسنده با fetchِ تزریق‌شده یک ردیف می‌نویسد", str(st))
    got = conn.execute("SELECT buy_i_val, sell_i_val, source FROM client_type_value"
                       " WHERE d_even=20261004").fetchall()
    ck(got == [(9795900492781.0, 8377684161902.0, T.CTV_SOURCE)],
       "ردیفِ نوشته‌شده عینِ مبدأ است", str(got))

    before = conn.execute("SELECT COUNT(*) FROM client_type_value").fetchone()[0]
    st2 = T.refresh_client_type_values(conn, day=20261004,
                                       fetch=lambda c: None,
                                       now="2026-10-05 13:00:00", force=True)
    ck(conn.execute("SELECT COUNT(*) FROM client_type_value").fetchone()[0] == before,
       "پاسخِ None ⇒ هیچ ردیفی نمی‌نشیند (نه صفر، نه ردیفِ خالی)", str(st2))

    st3 = T.refresh_client_type_values(conn, day=20261004, fetch=lambda c: LIVE_CTV,
                                       now="2026-10-05 13:00:01")
    ck(st3.get("skipped") in ("complete", "throttled"),
       "دوباره‌کاری با throttle/coverage رد می‌شود", str(st3))
    conn.close()


# ═════════════ P0-2 — رویدادهایِ شرکتی ═════════════
def part_corp():
    print("\n[P0-2] Corporate actions: source-native events")
    rows = T.parse_price_adjust(LIVE_ADJ["priceAdjust"], "now")
    ck(len(rows) == 2, "هر دو رویدادِ تعدیل خوانده می‌شوند", str(len(rows)))
    r0 = rows[0]
    ck(r0[0] == "67690708346979840" and r0[1] == 20261004,
       "insCode از wrapper یا از instrumentِ تودرتو درمی‌آید", str(r0[:3]))
    ck(r0[3] == 5710.0 and r0[4] == 5730.0,
       "پایانیِ تعدیل‌شده و پایانیِ خام جدا می‌مانند (یکی به‌جای دیگری نه)", str(r0[3:5]))
    ck(abs(r0[6] - round(5710.0 / 5730.0, 8)) < 1e-12,
       "ratio = pClosing / pClosingNotAdjusted (هشت رقمی، بی‌خطایِ گردکردن)")
    ck(r0[5] is None and rows[1][5] == 2,
       "corporateTypeCode خام ذخیره می‌شود — بی‌decode", str((r0[5], rows[1][5])))
    ck(r0[2] == "كماسه", "نماد از instrumentِ تودرتو")

    shr = T.parse_share_change(LIVE_SHARE["instrumentShareChange"], "now")
    ck(len(shr) == 1 and shr[0][3] == 50000000000.0 and shr[0][4] == 60000000000.0,
       "تعدادِ سهامِ قبل/بعد عینِ مبدأ", str(shr))
    ck(abs(shr[0][5] - round(50000000000.0 / 60000000000.0, 8)) < 1e-12,
       "ratio = shares_old / shares_new (قاعدهٔ ضریبِ سهام)")
    ck(len(shr[0]) == 8, "ردیفِ share_change هشت‌ستونی است (با DDL یکی)", str(len(shr[0])))

    conn = fresh_db()
    seen = {}

    def fake_get(url, key):
        seen[key] = seen.get(key, 0) + 1
        if "GetPriceAdjustByFlow" in url:
            return LIVE_ADJ["priceAdjust"]
        if "GetInstrumentShareChangeByFlow" in url:
            return LIVE_SHARE["instrumentShareChange"]
        return []

    stats = T.fetch_corporate_events(None, conn, now="now", get=fake_get)
    ck(stats["adjust"] == 2 and stats["share"] == 1,
       "هر دو خانواده درِ بانک نشستند", str(stats))
    ck(seen.get("priceAdjust") == 2 and seen.get("instrumentShareChange") == 2,
       "دو flow (بورس و فرابورس) — نه یکی", str(seen))
    ck(conn.execute("SELECT COUNT(*) FROM price_adjust_events").fetchone()[0] == 2,
       "دو رویدادِ هم‌نمادِ دو روزه، هر دو می‌مانند")
    ck(T.parse_price_adjust([], "now") == [] and T.parse_price_adjust(None) == [],
       "نمادِ بی‌رویداد ⇒ صفر ردیف، نه ردیفِ تهی")

    conn.execute("DELETE FROM price_adjust_events")
    boom = lambda u, k: (_ for _ in ()).throw(RuntimeError("429"))
    s2 = T.fetch_corporate_events(None, conn, now="now", get=boom)
    ck(s2["failed"] == 4 and s2["adjust"] == 0,
       "خطای مبدأ ⇒ بی‌نوشتن و بی‌سقوط، و failed شمرده می‌شود", str(s2))
    ck(conn.execute("SELECT COUNT(*) FROM price_adjust_events").fetchone()[0] == 0,
       "«رویداد نبود» فقط وقتی نوشته می‌شود که مبدأ واقعاً جواب داده باشد")
    conn.close()

    csrc = open(CHART_PY, encoding="utf-8").read()
    ck("GetPriceAdjustByFlow" in csrc and "رد شد" in csrc,
       "کامنتِ api/chart.py که می‌گفت «درِ فید نیست» با ارجاعِ سنجش اصلاح شده")
    # این چک درِ دورِ پیشین «نمی‌خواند» را pin کرده بود؛ دورِ مصرف‌کننده آن را
    # عمداً برگرداند: حالا چارت می‌خواند، ولی **برایِ نمایش**. چیزی که باید
    # ثابت بماند همین است: هیچ‌کدام از این ردیف‌ها به زنجیرۀ تعدیل راه نمی‌یابند.
    ck("_adjust_events_from_rows" in csrc
       and "FROM price_adjust_events" in csrc
       and "FROM share_change_events" in csrc,
       "رویدادهایِ مبدأ درِ canonical خوانده می‌شوند (pinِ دورِ پیشین، این دور برگشت)")
    ck("_corporate_events" in csrc,
       "یک تابعِ واحدِ خواندن، نه دو نگاشتِ جدا برایِ دو مسیرِ چارت")
    _calls = re.findall(r"_factors_from_events\([^)\n]*\)", csrc)
    ck(_calls and all("corporate" not in c.lower() for c in _calls),
       "هیچ حلقۀ تعدیلی از رویدادِ مبدأ نمی‌خواند (نمایش، بی‌محاسبهٔ دوم)",
       " | ".join(_calls))
    ck(csrc.count('"corporateEvents"') >= 3,
       "پاسخِ هر سه مسیرِ چارت (CDN، محلیِ فال‌بک، chart-db) کلید را دارد",
       str(csrc.count('"corporateEvents"')))
    ck('"corporateEvents": _corporate_events(symbol)' in csrc
       and '"corporateEvents": db_res.get("corporateEvents")' in csrc,
       "رویداد درِ همان پاسخ‌هایِ موجود می‌آید — اندپوینتِ دوم ساخته نشده")


# ═════════════ P0-3 — وضعیت / تعلیق / نظارت / پیام ═════════════
def part_state():
    print("\n[P0-3] Instrument state / stop reason / supervision / messages")
    st = T.parse_instrument_state(LIVE_STATE["instrumentState"], "now")
    ck(len(st) == 1 and st[0][2] == "IS" and st[0][3] == "ممنوع-متوقف",
       "وضعیتِ نماد: cEtaval (trim) و cEtavalTitle جدا می‌مانند", str(st))
    ck(len(st[0]) == 9, "ردیفِ instrument_state نه‌ستونی است (DDL با parse یکی)",
       str(len(st[0])))

    ms = T.parse_messages(LIVE_MSG["msg"], 1, "now")
    ck(ms and ms[0][0] == 266456 and "عدم تاييد" in (ms[0][4] or "")
       and (ms[0][5] or "").startswith("به اطلاع"),
       "پیامِ ناظر: کلیدِ tseMsgIdn، عنوان و متن جدا می‌مانند", str(ms[:1]))

    txt, n = T.split_supervision_reasons("الف<br>ب<br>")
    ck(txt == "الف\nب" and n == 2, "<br> به فهرستِ متنی تبدیل می‌شود", f"{txt!r},{n}")
    sup = T.parse_supervision({1: {1: LIVE_SUP["supervision"], 2: []}}, "now")
    ck(len(sup) == 1 and sup[0][6] == 2,
       "یک نماد از چند فهرست، دلیل‌هایش یکی می‌شود", str(sup))
    ck(all("0001-01-01" not in str(x) for x in sup),
       "insertionDateTime صفرِ مبدأ (0001-01-01) جایی درِ مدل نمی‌نشیند")

    sp = T.parse_stop_reasons(LIVE_STOPS, "now")
    ck(len(sp) == 2 and sp[0][0] == "اپال",
       "کلیدِ webgw پیشوندِ «نماد(نام)» است، نه insCode", str(sp[0][:2]))
    ck(sp[0][4] == "عدم ارائه گزارش تفسیری\nعدم ارائه صورتهای مالی",
       "dalils آرایه‌ای با \\n ذخیره می‌شود", str(sp[0][4]))

    conn = fresh_db()
    conn.execute("INSERT INTO supervision_state (ins_code, reasons) VALUES ('999','کهنه')")
    conn.commit()
    got = {}

    def fake_get(url, key):
        got[key] = got.get(key, 0) + 1
        if "GetInstrumentStateTop" in url:
            return LIVE_STATE["instrumentState"]
        if "GetMsgByFlow" in url:
            return LIVE_MSG["msg"]
        if "Supervision" in url:
            return LIVE_SUP["supervision"]
        return []

    stats = T.fetch_state_and_notices(None, conn, now="now", get=fake_get,
                                      webgw=lambda: LIVE_STOPS)
    ck(stats["state"] == 1 and stats["messages"] == 1 and stats["supervision"] == 1,
       "هر سه خانوادۀ CDN نوشته می‌شوند", str(stats))
    ck(stats["stops"] == 1,
       "علتِ توقف فقط برایِ نمادی که درِ instruments هست ذخیره می‌شود", str(stats))
    ck(conn.execute("SELECT COUNT(*) FROM supervision_state").fetchone()[0] == 1,
       "supervision_state snapshot است: ردیفِ کهنه می‌رود، تاریخچه ساخته نمی‌شود")
    ck(conn.execute("SELECT symbol FROM stop_reasons").fetchall() == [("اپال",)],
       "نمادِ بی‌همتاز درِ stop_reasons نمی‌نشیند (اتصالِ حدسی ممنوع)")

    s2 = T.fetch_state_and_notices(None, conn, now="now",
                                   get=lambda u, k: (_ for _ in ()).throw(
                                       RuntimeError("boom")),
                                   webgw=lambda: (_ for _ in ()).throw(
                                       RuntimeError("geo-blocked")))
    ck(s2["failed"] >= 5 and s2["stops"] == 0,
       "خطای upstream / بلاک‌بودنِ webgw ⇒ بی‌سقوط و بی‌دادهٔ جعلی", str(s2))
    ck(T.fetch_state_and_notices(None, conn, now="now",
                                 get=lambda u, k: [], webgw=None)["stops"] == 0,
       "webgw=None (پیکربندیِ بدونِ وب‌گی) مسیر را بی‌خطا رد می‌کند")
    conn.close()

    csrc = open(CODAL_PY, encoding="utf-8").read()
    ck("SAVE_USEFUL_ONLY = True" in csrc,
       "توقف/بازگشایی از کدال **همان‌طور که بود** حذف می‌ماند: یک مفهوم، یک منبع")


# ═════════════ سیم‌کشی و قیدهایِ ضدِ نشت ═════════════
def part_wiring():
    print("\n[wiring] canonical layer, no parallel judge")
    tsrc = open(TS_PY, encoding="utf-8").read()
    for needle in ("def refresh_client_type_values", "def fetch_corporate_events",
                   "def fetch_state_and_notices", "def p0_due", "def p0_mark",
                   "client_type_value", "price_adjust_events", "share_change_events",
                   "instrument_state", "stop_reasons", "supervision_state",
                   "tsetmc_messages"):
        ck(needle in tsrc, f"`{needle}` درِ موتورِ واکشی تعریف شده")
    for call in ("fetch_corporate_events(s, conn", "fetch_state_and_notices(s, conn",
                 "refresh_client_type_values(conn"):
        ck(call in tsrc, f"main() واقعاً `{call}` را صدا می‌زند")
    ck(tsrc.count("except Exception as e:") >= 4 and "p0_due(conn, _name" in tsrc,
       "هر سه خانواده try/except و throttle دارند (حلقۀ ۹۰ ثانیه‌ای نمی‌شکند)")

    # هیچ فیلتر/گیت/طبقۀ روندی به این سه وصل نشده — چکِ ضدِ نشت
    ck("client_type_value" not in open(FLAGS_PY, encoding="utf-8").read(),
       "tape_flags هیچ‌وقت client_type_value را نمی‌خواند (هفت فیلتر دست‌نخورده)")
    ck("client_type_value" not in open(CONF_PY, encoding="utf-8").read(),
       "confidence_engine همان حجم‌مبنا می‌ماند (بی‌موازی‌خوانیِ ارزش)")
    ck("value_source" not in open(MARKET_PY, encoding="utf-8").read(),
       "بدنۀ /api/market شلوغ نمی‌شود: provenance فقط درِ لایۀ mstat/audit")
    ck("price_adjust_events" not in open(MARKET_PY, encoding="utf-8").read(),
       "تابلو رویدادِ تعدیل را دور نمی‌ریزد ولی مسیرِ تازه هم نمی‌سازد")

    # spec: هیچ api/*.py تازه‌ای نیامده، پس hiddenimports دست‌نخورده می‌ماند
    spec = open(SPEC, encoding="utf-8").read()
    ck("test_tsetmc" in spec, "test_tsetmc همان‌طور درِ hiddenimports هست")
    import glob
    apis = {os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "api", "*.py"))}
    ck(all(("p0" not in a and "tsetmc_p0" not in a) for a in apis),
       "هیچ اندپوینتِ تازۀ api/ ساخته نشده ⇒ نیازی به ویرایشِ spec نبود",
       str(sorted(apis)))

    # پیکربندی‌پذیریِ دامنه: webgw hard-coded نباشد که از بیرونِ ایران بلاک است
    ck("WEBGW_BASE" in tsrc or "webgw is not None" in tsrc,
       "webgw اختیاری است (تابع/پیکربندی)، نه وابستگیِ اجباری")


def part_p1():
    print("\n[P1] رایگان‌ها: کلیدهایی که درِ همان پاسخ بودند")
    raw = {"insCode": "65883838195688438", "dEven": 20261005, "hEven": 120000,
           "lva": "خودرو", "lvc": "خودرو", "csv": "34", "pcl": 718.0, "pdv": 697.0,
           "py": 706.0, "pf": 712.0, "pmn": 692.0, "pmx": 727.0, "pMin": 636.0,
           "pMax": 776.0, "qtj": 15624360036.0, "qtc": 11220769584413.0,
           "ztt": 28943.0, "pc": -9.0, "eps": 1.0, "pe": 2.0, "ztd": 1.0, "bv": 1.0,
           "insID": "IRO1IKCO0008", "flow": 1, "pRedTran": 690.0, "buyOP": 700.0,
           "cGrValCot": "A1"}
    it, w, dy = T._mw_row(raw, 20261005, 20261005, "now", {"34": "خودرو"}, {"x": 1})
    ck(it is not None and len(it) == len(T._INST_COLS),
       "ردیفِ instruments با _INST_COLS هم‌طول است (INSERT نام‌دار، بی‌جابه‌جاییِ ستون)",
       f"{len(it) if it else None} vs {len(T._INST_COLS)}")
    ck(it[T._INST_COLS.index("isin")] == "IRO1IKCO0008",
       "ISIN از کلیدِ خامِ `insID` درِ همان پاسخِ تابلو می‌آید")
    ck(it[T._INST_COLS.index("c_gr_val_cot")] == "A1", "cGrValCot ذخیره می‌شود")
    ck(len(w) == len(T.MW_COLS),
       "ردیفِ market_watch با MW_COLS هم‌طول است (market_state هم همین را می‌خواند)",
       f"{len(w)} vs {len(T.MW_COLS)}")
    for col, want in (("flow", 1), ("p_red_tran", 690.0), ("buy_op", 700.0)):
        ck(w[T.MW_COLS.index(col)] == want, f"`{col}` از همان پاسخ می‌نشیند",
           str(w[T.MW_COLS.index(col)]))
    ck(len(dy) == 15, "ردیفِ daily_prices دست‌نخورده مانده (۱۵ ستون)", str(len(dy)))

    # تک‌منبعِ مهاجرت: DDL دو مسیر باید یک ستون‌بندی داشته باشد
    tsrc = open(TS_PY, encoding="utf-8").read()
    msrc = open(MSTAT_PY, encoding="utf-8").read()

    def ddl_cols(text, marker):
        i = text.find(marker)
        if i < 0:
            return set()
        body = text[i:].split("PRIMARY KEY")[0]
        body = re.sub(r"--[^\n]*", "", body)          # کامنت‌هایِ فارسیِ بینِ ستون‌ها
        body = body[body.find("(") + 1:]
        return {m.group(1) for m in re.finditer(r"([a-z_][a-z0-9_]*)\s+(?:TEXT|REAL|INTEGER)",
                                                body)}

    t_cols = ddl_cols(tsrc, "CREATE TABLE IF NOT EXISTS {TAPE_HIST_TABLE} (")
    m_cols = ddl_cols(msrc, "CREATE TABLE IF NOT EXISTS tape_history (")
    ck(t_cols and t_cols == m_cols,
       "دو DDLِ tape_history دقیقاً یک ستون‌ها را می‌گویند (بی‌ستونِ گم‌شده)",
       f"only-tsetmc={sorted(t_cols - m_cols)} only-mstat={sorted(m_cols - t_cols)}")
    ck("q_tot_cap" in t_cols, "q_tot_cap درِ هر دو DDL هست", str(sorted(t_cols)))
    ck('"tape_history": [("q_tot_cap", "REAL")]' in msrc,
       "ستونِ تازه از MIGRATIONS می‌آید، نه از ALTER دومِ موازی")
    ck("ALTER TABLE tape_history" not in tsrc and "ADD COLUMN q_tot_cap" not in tsrc,
       "درِ test_tsetmc برایِ tape_history دستی ALTER نشده (تک‌منبعِ مهاجرت)")

    # نوشتن باید با نامِ ستون باشد. `q_tot_cap` را MIGRATIONS رویِ بانکِ
    # ارتقایافته به **آخر** می‌افزاید، پس ترتیبِ ستون‌ها آنجا (…، fetched_at،
    # q_tot_cap) با بانکِ تازه یکی نیست و INSERT موقعیتی زمان را درِ ستونِ عددی
    # می‌نشاند. اثباتِ مستقیم: یک بانکِ «ارتقایافته» می‌سازیم و می‌خوانیم.
    ck("_TAPE_HIST_INSERT" in tsrc and "INTO {TAPE_HIST_TABLE} VALUES (" not in tsrc
       and "INTO tape_history VALUES (" not in tsrc,
       "نویسندۀ tape_history موقعیتی نیست (با نامِ ستون می‌نویسد)")
    up = sqlite3.connect(":memory:")
    up.execute("CREATE TABLE tape_history (ins_code TEXT NOT NULL, d_even INTEGER NOT"
               " NULL, price_min REAL, price_max REAL, q_tot_tran5j REAL, fetched_at"
               " TEXT, q_tot_cap REAL, PRIMARY KEY (ins_code, d_even))")
    up.executemany(T._TAPE_HIST_INSERT, [("K1", 20260928, 90.0, 110.0, 3000.0,
                                         5e8, "2026-09-28 11:00:00")])
    got = up.execute("SELECT typeof(q_tot_cap), typeof(fetched_at), q_tot_cap,"
                     " fetched_at FROM tape_history").fetchone()
    ck(got[0] == "real" and got[1] == "text" and got[2] == 5e8
       and got[3] == "2026-09-28 11:00:00",
       "رویِ بانکِ ارتقایافته هم مقدار درِ q_tot_cap و زمان درِ fetched_at می‌نشیند",
       str(got))
    up.close()

    # و بدنهٔ تابلو نباید بزرگ‌تر شده باشد
    mkt = open(MARKET_PY, encoding="utf-8").read()
    for col in ("p_red_tran", "buy_op", "c_gr_val_cot", "\"flow\""):
        ck(col not in mkt, f"ستونِ `{col}` درِ کوئری/بدنۀ تابلو نمی‌نشیند (بدنه یکی می‌ماند)")
    q = mkt.split("ctm AS (")[1].split('"""')[0] if "ctm AS (" in mkt else ""
    ck(q.count("SELECT") >= 1 and "i.isin" not in q and "m.flow" not in q,
       "کوئریِ قابِ تابلو به ستون‌هایِ تازهٔ instruments/market_watch دست نمی‌زند",
       "isin-in-frame=%s flow-in-frame=%s" % ("isin" in q, "m.flow" in q))

    # پاسِ «JSON safety» درِ api/market.py هر NaN را صفر می‌کند. کلیدهایِ
    # وضعیت/نظارت باید از آن پاس **بیرون** بمانند وگرنه «موردی ثبت نشده» به
    # «وضعیتِ صفر» بدل می‌شود. اندازۀ همین دور: با صفرها 5.60MB بدنه، و با
    # قاعدهٔ درست 4.90MB — یعنی آن 0.70MB فقط دروغِ صفر بود.
    keep = mkt.split("_KEEP_NULL = (")[1].split(")")[0] if "_KEEP_NULL = (" in mkt else ""
    for col in ("st_code", "st_title", "st_d", "st_h", "sup_flag", "sup_title",
                "sup_reason_count", "sup_reasons", "stop_state", "stop_since",
                "stop_reasons"):
        ck(f'"{col}"' in keep, f"`{col}` درِ _KEEP_NULL می‌ماند (نبود ≠ صفر)")


def part_report():
    print("\n[گزارش] سنجشِ پوششِ مبدأ (بندِ ۱۰: اندازه‌گیری، نه افزایشِ بودجه)")
    path = os.path.join(ROOT, "dev", "tsetmc_native_coverage_report.py")
    src = open(path, encoding="utf-8").read()
    ck(T.CTV_BUDGET == 600, "سقفِ 600 درخواست/روز دست‌نخورده باقی مانده")
    ck("mode=ro" in src, "گزارش بانک را فقط‌خواندنی باز می‌کند (بی‌نوشتن)")
    import importlib.util
    spec = importlib.util.spec_from_file_location("cov_report", path)
    rep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rep)

    c = fresh_db()
    day = 20261004
    # دامنهٔ هدف = چهار نمادِ دارایِ جریان؛ دو ردیفِ مبدأ (یکی native، یکی mixed)
    for i, ins in enumerate(("65883838195688438", "2109854662147869", "K3", "K4")):
        c.execute("INSERT OR REPLACE INTO client_type (ins_code, d_even, buy_i_vol,"
                  " sell_i_vol) VALUES (?,?,?,?)", (ins, day, 100.0 + i, 90.0 + i))
    c.execute("INSERT INTO client_type_value (ins_code, d_even, buy_i_val, buy_n_val,"
              " sell_i_val, sell_n_val, kind) VALUES (?,?,?,?,?,?,?)",
              ("65883838195688438", day, 1.0, 2.0, 3.0, 4.0, "native"))
    c.execute("INSERT INTO client_type_value (ins_code, d_even, buy_i_val, buy_n_val,"
              " sell_i_val, sell_n_val, kind) VALUES (?,?,?,?,?,?,?)",
              ("2109854662147869", day, 1.0, None, 3.0, None, "mixed"))
    c.commit()
    m = rep.measure(c)
    ck(m["target_universe"] == 4 and m["native"] == 1 and m["mixed"] == 1,
       "هدف و شمارِ native/mixed از خودِ بانک خوانده می‌شود", str(m["target_universe"]))
    ck(m["reconstructed"] == 2,
       "reconstructed = هدفِ بی‌ردیف (نه صفرِ جعلی، نه شمارِ ردیف‌ها)", str(m["reconstructed"]))
    ck(m["native_coverage_of_target_pct"] == 25.0, "پوششِ مبدأ = ۱ از ۴ هدف", str(m["native_coverage_of_target_pct"]))
    ck(m["cache_hit_pct"] == 50.0, "برخوردِ کش = ردیف‌هایِ موجود ÷ هدف", str(m["cache_hit_pct"]))
    ck(m["avg_requests_per_symbol"] == 1.0,
       "هر ردیف یک GetClientTypeHistory است → میانگینِ یک درخواست/نماد", str(m["avg_requests_per_symbol"]))
    ck(m["estimated_requests_per_day"]["funnel_candidates"] <= T.CTV_BUDGET,
       "برآوردِ روزانه از سقفِ بودجه فراتر نمی‌رود (کلیپ دارد)")
    ck(str(m["estimated_requests_per_day"]["watchlist"]) == "0",
       "بی‌جدولِ دیده‌بان عددِ جعلی نمی‌سازد (صفر = بی‌داده، نه خطا)")
    text = rep.render(m)
    ck("پوششِ مبدأ" in text and "برآوردِ درخواست/روز" in text,
       "گزارشِ متنی هر دو بخش را دارد", text[:40])
    c.close()


def main():
    part_ctv()
    part_corp()
    part_state()
    part_p1()
    part_wiring()
    part_report()
    print(f"\ntsetmc_p0_v1076: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
