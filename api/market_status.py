"""Market-status dashboard: TradersArena proxy and the local mstat engine.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from ._core import get_db
from fastapi import APIRouter
from fastapi import Query
import mstat_engine as _mstat
import time


router = APIRouter()


def _ta_fetch(path: str, force: bool = False):
    """GET tradersarena.ir/data/<path> با کش کوتاه (TTL 30s) — بدون کرش در قطعی."""
    import requests as _rq
    now = time.time()
    if not force:
        c = TA_CACHE.get(path)
        if c and (now - c[0]) < TA_TTL:
            return c[1]
    try:
        r = _rq.get(TA_BASE + path, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                    timeout=15)
        j = r.json()
        TA_CACHE[path] = (now, j)
        return j
    except Exception as e:
        # کش کهنه را نگه دار (حالت قطعی اینترنت → آخرین داده)
        c = TA_CACHE.get(path)
        if c:
            return c[1]
        return {"status": "error", "message": str(e)}

@router.get("/api/market-status/overview")
def ta_overview():
    """وضعیت کلی بازار: M0 + totals0 + industries (برای پنل وضعیت بازار)."""
    m0 = _ta_fetch("/data/market0")
    tot = _ta_fetch("/data/market/chart/totals0")
    return {"status": "ok", "market": m0, "timeline": tot}

@router.get("/api/market-status/timeline")
def ta_timeline():
    return {"status": "ok", "data": _ta_fetch("/data/market/chart/totals0")}

@router.get("/api/market-status/industries")
def ta_industries():
    return {"status": "ok", "data": _ta_fetch("/data/industries-csv")}

@router.get("/api/market-status/mainwatch")
def ta_mainwatch():
    return {"status": "ok", "data": _ta_fetch("/data/mainwatch/symbols")}

@router.get("/api/market-status/histo")
def ta_histo():
    return {"status": "ok", "data": _ta_fetch("/data/market/histo-status")}

def _mstat_call(fn, *args, **kw):
    """یک اتصال، یک فراخوانی، همیشه بسته. خطای موتور ⇒ status=error نه ۵۰۰،
    چون یک پنلِ خراب نباید کل تب وضعیت بازار را از کار بیندازد."""
    conn = get_db()
    try:
        out = fn(conn, *args, **kw)
        out.setdefault("source", "local:market.db")
        return out
    except Exception as e:
        return {"status": "error", "message": str(e), "source": "local:market.db"}
    finally:
        conn.close()

@router.get("/api/mstat/summary")
def mstat_summary():
    """گام ۱ — جدول نه‌سطری خلاصهٔ معاملات خرد + برچسب سلامت کلان."""
    return _mstat_call(_mstat.summary)

@router.get("/api/mstat/histogram")
def mstat_histogram(group: str = Query("all")):
    """گام ۲.۱ و ۳.۳ — توزیع بازدهی ۱۲بازه + محدودهٔ قیمتی ۷بازه."""
    return _mstat_call(_mstat.histogram, group)

@router.get("/api/mstat/thermometer")
def mstat_thermometer(group: str = Query("all")):
    """گام ۲.۲ — نوار مثبت/منفی و قانون فرصت ورود."""
    return _mstat_call(_mstat.thermometer, group)

@router.get("/api/mstat/depth")
def mstat_depth(group: str = Query("all")):
    """گام ۲.۳ و ۳.۱ — ارزش ۵ خط اول + تفکیک صف‌ها."""
    return _mstat_call(_mstat.depth, group)

@router.get("/api/mstat/clientsplit")
def mstat_clientsplit(tab: str = Query("all")):
    """گام ۲.۴ و ۵.۱ — تفکیک حقیقی/حقوقی به تفکیک تب."""
    return _mstat_call(_mstat.client_split, tab)

@router.get("/api/mstat/mainwatch")
def mstat_mainwatch(group: str = Query("eq_all"), industry: str = Query(""),
                    sort: str = Query("clock"), desc: bool = Query(True),
                    limit: int = Query(120)):
    """گام ۵.۲ — تابلوی نمادها؛ ستونِ اختلاف آخرین/پایانی مرتب‌شدنی است."""
    return _mstat_call(_mstat.mainwatch, group, industry, sort, desc, limit)

@router.get("/api/mstat/industries")
def mstat_industries():
    """گام ۵.۳ — خلاصهٔ صنایع (کلیک ⇒ فیلتر جدول پایین)."""
    return _mstat_call(_mstat.industries)

@router.get("/api/mstat/smart-money")
def mstat_smart_money():
    """v9.8.0 — بنر نقدینگی کلان + جریان پول هوشمند FTS.

    سه خروجی دارد: شاخص نقدینگی (همت) با برچسب مساعد/نامساعد، شرط هشدار ۸۰٪
    (فرصت پایش برای ورود)، و مقایسهٔ ورود/خروج پولِ خردِ سهام ⇄ صندوق درآمد ثابت
    با برچسب «حالت ایده‌آل FTS». در board هم می‌نشیند تا رندرِ تب همان
    round-tripِ واحدِ همیشگی بماند.
    """
    return _mstat_call(_mstat.smart_money)

@router.get("/api/mstat/timeline")
def mstat_timeline(mode: str = Query("cum")):
    """گام ۴ — تایم‌لاین‌های ۰۹:۰۰ تا ۱۳:۰۰ (مجموع | لحظه‌ای).

    v9.8.1 — فیلتر پنجرهٔ رسمی بازار: mstat_engine._points فقط نقاطِ
    ۰۸:۵۵–۱۳:۰۰ را از mstat_snap برمی‌دارد؛ نقاطِ شبانه/تستیِ خارج از ساعات
    معاملات (که افتِ دروغین به صفر و خطوط مورب روی چارت میساختند) هرگز به
    فرانت‌اند ارسال نمیشوند — نه در تایم‌لاین، نه در شمارندهٔ فازها.
    """
    return _mstat_call(_mstat.timeline, mode)

@router.get("/api/mstat/phases")
def mstat_phases():
    """گام ۳.۲ — شمارندهٔ چرخش وضعیت‌ها (صف↼مثبت↼منفی)."""
    return _mstat_call(_mstat.phases)

@router.get("/api/mstat/board")
def mstat_board(group: str = Query("eq_all"), limit: int = Query(60)):
    """تک‌درخواستِ کل تب. polling هر ۳۰–۶۰ ثانیه است و ۹ درخواستِ جدا هم
    شبکه را درگیر می‌کند هم مرورگر را؛ این یکی باعث می‌شود هر بارِ رندر،
    یک round-trip باشد (خط قرمز: رندر روان بدون افت فریم)."""
    conn = get_db()
    try:
        return {"status": "ok", "source": "local:market.db",
                "summary": _mstat.summary(conn),
                "thermometer": _mstat.thermometer(conn, group),
                "histogram": _mstat.histogram(conn, group),
                "depth": _mstat.depth(conn, group),
                "clientsplit": _mstat.client_split(conn, "all"),
                "mainwatch": _mstat.mainwatch(conn, group, "", "clock", True, limit),
                "industries": _mstat.industries(conn),
                "smartmoney": _mstat.smart_money(conn),
                "timeline": _mstat.timeline(conn, "cum"),
                "phases": _mstat.phases(conn)}
    except Exception as e:
        return {"status": "error", "message": str(e), "source": "local:market.db"}
    finally:
        conn.close()

@router.post("/api/mstat/snapshot")
def mstat_snapshot_now():
    """یک نقطهٔ تایم‌لاین همین لحظه — دستیارِ تست و «بروزرسانی» دستی."""
    conn = get_db()
    try:
        return dict({"status": "ok"}, **_mstat.save_mstat_snapshot(conn))
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

TA_BASE = "https://tradersarena.ir"
TA_CACHE = {}          # path → (ts, data)
TA_TTL = 30            # ثانیه — polling سبک (UI هم interval خودش را دارد)
