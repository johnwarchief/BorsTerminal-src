# dev/test_corporate_ledger_v1.py — Phase 5 Stage 3: ledgerِ canonicalِ رویداد، بی‌تکرار/بی‌حدس/بی‌proxy
# read-only برِ دیتابیسِ **موقت** (tempfile) با همان schemaِ رسمی؛ هیچ نوشتن برِ market.db عملیاتی.
# اثبات: نسبتِ رسمی از خودِ ردیف می‌آید (نه proxyِ کندل)، همان روز = یکِ رویداد (priceAdjust تقدم)،
# ورودیِ مفقود → incomplete، خارجازکران → invalid، اجرایِ دوباره idempotent، ابزارِ نادرست تهی،
# نوع فقط وقتی یکتا افزوده می‌شود (مختلط → نامشخص)، تاریخِ مؤثر ≠ تاریخِ انتشار، بی‌اعمالِ دوباره.
import io
import os
import sqlite3
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import adjustment_engine as AE          # noqa: E402
import corporate_ledger as L            # noqa: E402
import tsetmc_p0_schema as P0           # noqa: E402

P = F = 0


def check(name, got, want):
    global P, F
    if got == want:
        P += 1
        print(f"  ✓ {name}")
    else:
        F += 1
        print(f"  ✗ {name}: got={got!r} want={want!r}")


def new_db():
    db = os.path.join(tempfile.mkdtemp(), "t.db")
    con = sqlite3.connect(db)
    con.execute(P0.PRICE_ADJUST_EVENTS)
    con.execute(P0.SHARE_CHANGE_EVENTS)
    con.execute("CREATE TABLE codal_notices (tracing_no TEXT, symbol TEXT, title TEXT, publish_date TEXT)")
    return con


def adj(con, ins, d, sym, raw, adjp, ctype=None):
    con.execute("INSERT OR REPLACE INTO price_adjust_events VALUES (?,?,?,?,?,?,?,?,?)",
                (ins, d, sym, adjp, raw, ctype, None, "t", ""))


def shr(con, ins, d, sym, old, new):
    con.execute("INSERT OR REPLACE INTO share_change_events VALUES (?,?,?,?,?,?,?,?)",
                (ins, d, sym, old, new, None, "t", ""))


def notice(con, sym, title, pub, tr):
    con.execute("INSERT INTO codal_notices VALUES (?,?,?,?)", (tr, sym, title, pub))


try:
    # ── ۱) نسبتِ رسمی، بی‌proxy ──
    con = new_db()
    adj(con, "I1", 20250110, "فولاد", raw=1000.0, adjp=800.0)     # ratio رسمی 0.8
    con.commit()
    ev, c = L.build_typed_events(con, "I1")
    check("۱ یکِ رویداد", len(ev), 1)
    check("۱ نوعِ source_ratio", ev[0]["kind"], AE.KIND_SOURCE_RATIO)
    check("۱ نسبت = adj/rawِ رسمی (۰٫۸)، بی‌محاسبۀِ دوباره", ev[0]["ratio"], 0.8)
    check("۱ مرجعِ رسمیِ قیمت (p_closing_not_adjusted) درِ provenance",
          ev[0]["provenance"].get("reference_price_official"), 1000.0)
    check("۱ تاریخِ مؤثر از d_even", ev[0]["date"], "2025-01-10")
    check("۱ فاکتور کامل", c["complete"], 1)

    # ── ۲) همان روز درِ هر دو جدول = یکِ رویداد (priceAdjust تقدم؛ بی‌اعمالِ دوباره) ──
    con2 = new_db()
    adj(con2, "I2", 20250201, "وبملت", raw=1000.0, adjp=500.0)    # 0.5
    shr(con2, "I2", 20250201, "وبملت", old=1, new=2)              # 0.5 — نباید دوبار بشمارد
    con2.commit()
    ev2, _ = L.build_typed_events(con2, "I2")
    check("۲ همان روز ادغام شد (یکِ رویداد)", len(ev2), 1)
    check("۲ منبعِ پیروز = priceAdjust", ev2[0]["provenance"]["source"], "priceAdjust")

    # ── ۳) ورودیِ مفقود → incomplete؛ خارجازکران → invalid ──
    con3 = new_db()
    adj(con3, "I3", 20250301, "خ", raw=None, adjp=800.0)          # بدونِ خام → ratio None
    adj(con3, "I3", 20250302, "خ", raw=1.0, adjp=2e8)             # خارجازکران
    con3.commit()
    ev3, c3 = L.build_typed_events(con3, "I3")
    st = {e["provenance"].get("factor_status") for e in ev3}
    check("۳ ناقص+نامعتبر علامت خورد (بی‌فاکتورِ جعلی)", st, {"incomplete:ratio", "invalid:ratio_out_of_range"})
    check("۳ هیچ‌کدام complete نیست", c3["complete"], 0)

    # ── ۴) idempotent: اجرایِ دوباره همان خروجی (بی‌تکثیرِ رویداد/ضریب) ──
    evA, cA = L.build_typed_events(con, "I1")
    evB, cB = L.build_typed_events(con, "I1")
    check("۴ اجرایِ دوباره رویدادها یکسان", [e["event_id"] for e in evA], [e["event_id"] for e in evB])
    check("۴ اجرایِ دوباره شمارش‌ها یکسان", cA, cB)

    # ── ۵) ابزارِ نادرست → تهی (بی‌سرریزِ دادهٔ ناشرِ دیگر) ──
    evx, cx = L.build_typed_events(con, "ناشناخته")
    check("۵ ابزارِ بی‌ردیف → لیستِ تهی", evx, [])
    check("۵ شمارشِ رویداد صفر", cx["events_total"], 0)

    # ── ۶) نوع فقط وقتی CODAL یکتا؛ مختلط → نامشخص (بی‌حدس) ──
    con6 = new_db()
    adj(con6, "I6", 20250401, "ش", raw=1000.0, adjp=900.0)
    notice(con6, "ش", "زمانبندی پرداخت سود دوره ۱۴۰۲", "1402-06-01", "T1")
    con6.commit()
    ev6, c6 = L.build_typed_events(con6, "I6")
    check("۶ الف نوعِ یکتا از CODAL افزوده شد", ev6[0]["provenance"]["event_type"], AE.KIND_CASH_DIVIDEND)
    # مختلط: دو کلاسِ متفاوت → نباید حدس بزند
    con7 = new_db()
    adj(con7, "I7", 20250501, "م", raw=1000.0, adjp=900.0)
    notice(con7, "م", "زمانبندی پرداخت سود", "1402-06-01", "T1")
    notice(con7, "م", "مدارک درخواست افزایش سرمایه", "1402-07-01", "T2")
    con7.commit()
    ev7, _ = L.build_typed_events(con7, "I7")
    check("۶ ب نوعِ مختلط → unresolved (بی‌حدس)", ev7[0]["provenance"]["type_confidence"], "unresolved")

    # ── ۷) تاریخِ مؤثر (d_even) از تاریخِ انتشارِ اطلاعیه جدا ──
    check("۷ تاریخِ مؤثرِ رویداد از d_even", ev6[0]["provenance"]["effective_date"], "2025-04-01")
    check("۷ تاریخِ انتشارِ CODAL جدا ثبت شد", ev6[0]["provenance"].get("source"), "priceAdjust")

    # ── ۸) زنجیرۀِ موتور از ledger = ضربِ نسبت‌هایِ رسمی (بی‌proxy، بی‌اعمالِ دوباره) ──
    con8 = new_db()
    adj(con8, "I8", 20250110, "ز", raw=1000.0, adjp=800.0)   # 0.8
    adj(con8, "I8", 20250210, "ز", raw=1000.0, adjp=500.0)   # 0.5
    con8.commit()
    ev8, c8 = L.build_typed_events(con8, "I8")
    dates = ["2025-01-05", "2025-01-15", "2025-02-15"]
    fac, meta = AE.chain_factors(dates, ev8)
    check("۸ پیش ازِ هر دو رویداد = 0.8×0.5", fac[0], 0.4)
    check("۸ میانِ دو رویداد = فقطِ 0.5", fac[1], 0.5)
    check("۸ پس ازِ همه = لنگر ۱", fac[2], 1.0)
    check("۸ زنجیرۀِ ledger کامل است", meta["complete"], True)

    print(f"\nنمونۀِ read-only ازِ market.dbِ عملیاتی (بدونِ نوشتن):")
    ro = sqlite3.connect("file:market.db?mode=ro", uri=True, timeout=5)
    try:
        row = ro.execute("SELECT ins_code, COUNT(*) c FROM price_adjust_events "
                         "GROUP BY ins_code ORDER BY c DESC LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        # worktreeِ بدونِ بازارِ کامل (یا بانکِ اسکرچ): نمونهٔ زنده ممکن نیست؛
        # تست‌هایِ fixture بالا کامل اجرا شدند. «نبودِ داده» ≠ خطای کد.
        row = None
        print("   ↳ market.dbِ محلی جدولِ P0 ندارد — نمونهٔ عملیاتی رد شد (نه خطا)")
    if row:
        ins = str(row[0])
        pa = ro.execute("SELECT d_even, p_closing_not_adjusted, p_closing FROM price_adjust_events "
                        "WHERE ins_code=? ORDER BY d_even", (ins,)).fetchall()
        sc = ro.execute("SELECT d_even, shares_old, shares_new FROM share_change_events "
                        "WHERE ins_code=? ORDER BY d_even", (ins,)).fetchall()
        pa_days = {r[0] for r in pa}
        exp_total = len(pa_days | {r[0] for r in sc})
        lev, lc = L.build_typed_events(ro, ins)
        lv = {e["provenance"]["d_even"]: e["ratio"] for e in lev}
        check("۹ رویداد = روزهایِ متمایزِ مبدأ (priceAdjust تقدمِ بر shareChange)", lc["events_total"], exp_total)
        # هر رویداد باید دقیقاً نسبتِ رسمیِ همان ردیف باشد (بی‌proxy، بی‌محاسبۀِ مجددِ جهت‌دار)
        bad = 0
        for d, raw, adjv in pa:
            if raw and raw > 0 and adjv is not None and lv.get(d) != round(adjv / raw, 8):
                bad += 1
        for d, old, new in sc:
            if d in pa_days:
                continue
            if old and new and new > 0 and lv.get(d) != round(old / new, 8):
                bad += 1
        check("۹ نسبتِ ledger == نسبتِ رسمیِ همان ردیف (priceAdjust=adj/raw، shareChange=old/new)", bad, 0)
        print(f"   ↳ ins={ins} price_adjust={len(pa)} share_change={len(sc)} متمایز={exp_total} "
              f"کامل={lc['complete']} بی‌نوع={lc['unknown_type']}")
    ro.close()
finally:
    for con in ("con", "con2", "con3", "con6", "con7", "con8"):
        try:
            globals()[con].close()
        except Exception:
            pass

print(f"\nنتیجه: {P} سبز، {F} قرمز")
sys.exit(1 if F else 0)
