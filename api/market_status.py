"""Market-status dashboard: the local mstat engine.

Split verbatim out of app.py (v9.8.1 modularisation).
Audit map of source line spans: MIGRATED_LINES.txt

پنج روتِ پروکسۀ tradersarena.ir (`/api/market-status/*`) و `_ta_fetch` از این فایل
حذف شدند: هیچ مصرف‌کننده‌ای در وب‌اپ نداشتند و همان پنل‌ها از `market.db` خودِ
برنامه ساخته می‌شوند. سنجشِ پوشش: `tools/ta_local_parity.py`.
"""
from ._core import get_db
from fastapi import APIRouter
from fastapi import Query
import threading
import time

import market_state as _MS
import mstat_engine as _mstat
import funnel_engine as _FE


router = APIRouter()

# ---- Phase پرفورمنس (N3): کشِ نتیجه به‌ازای revision واقعیِ بانک ----
# هر پنل mstat کل ۵٫۵هزار ردیف را می‌روبید (~250-830ms هسته در هر درخواست)؛
# سنجهٔ baseline: ~۱٫۵s CPU هر نفسِ نبض. کلیدِ کش همان چهار نشانه‌ای است که
# «حالتِ بانک» را کامل توصیف می‌کنند — revisionِ تابلو، static_rev (الگوی
# ازپیش‌پذیرفتۀ خودِ api/market.py:495-520)، روزِ نشست، و آخرین نقطۀ mstat_snap.
# بی‌هیچ محاسبهٔ موازی: همان fn، همان فرمول، همان عدد؛ فقط یک‌بار به‌ازای هر
# حالت. TTL سقفِ امانت هم نگهبانِ بی‌سر‌و‌صداست.
_MSTAT_TTL_S = 45.0
_MSTAT_CACHE: dict = {}
_MSTAT_LOCK = threading.Lock()


def _mstat_marker(conn):
    """اثرِ حالتِ تایم‌لاین: آخرین (روز، ساعت) ثبت‌شده در mstat_snap.
    جدول نباشد None ⇒ کش بی‌استفاده (اولین دورِ بوت)."""
    try:
        row = conn.execute(
            "SELECT IFNULL(MAX(d_even),0), IFNULL(MAX(h_even),0) FROM mstat_snap"
        ).fetchone()
        return (int(row[0] or 0), int(row[1] or 0))
    except Exception:
        return None


def _mstat_call(fn, *args, **kw):
    """یک اتصال، یک فراخوانی، همیشه بسته. خطای موتور ⇒ status=error نه ۵۰۰،
    چون یک پنلِ خراب نباید کل تب وضعیت بازار را از کار بیندازد.
    نتیجه‌های موفق به‌ازای هر «حالتِ بانک» کش می‌خورند؛ خطا هرگز نه."""
    key = (fn.__name__, args, tuple(sorted(kw.items())))
    now = time.monotonic()
    conn = get_db()
    try:
        marker = _mstat_marker(conn)
        if marker is not None:
            full_key = (key, _MS.revision(), _MS.static_rev(), _MS.session_day(), marker)
            with _MSTAT_LOCK:
                hit = _MSTAT_CACHE.get(full_key)
                if hit and now - hit[0] < _MSTAT_TTL_S:
                    return dict(hit[1])
        else:
            full_key = None
    except Exception:
        full_key = None
    finally:
        conn.close()
    conn = get_db()
    try:
        out = fn(conn, *args, **kw)
        out.setdefault("source", "local:market.db")
    except Exception as e:
        return {"status": "error", "message": str(e), "source": "local:market.db"}
    finally:
        conn.close()
    if full_key is not None and isinstance(out, dict) and out.get("status") != "error":
        with _MSTAT_LOCK:
            if len(_MSTAT_CACHE) > 240:
                _MSTAT_CACHE.clear()
            _MSTAT_CACHE[full_key] = (now, out)
    return dict(out)

# ── پرچم‌هایِ تابلو درِ «نمادهای زیرِ نظر» ─────────────────────────────────
# هفت پرچم را `tape_flags.apply_tape_flags` می‌سازد و `/api/market` رویِ ردیف‌ها
# می‌نشاند. موتورِ نبض (`mstat_engine.mainwatch`) آن‌ها را حساب نمی‌کند، پس
# اینجا فقط *منتقل* می‌شوند: هیچ فرمولِ دومی درِ این فایل نساخته می‌شود — رأیِ
# مالک (۱۴۰۵-۰۷-۲۲) «حجمِ مشکوک / ورودِ پول / کد به کد» را درِ این جدول هم
# می‌خواهد، نه درِ تبِ تابلو تنها.
TAPE_FLAG_KEYS = ("f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh", "f_smart", "f_legal")


def _tape_flag_map() -> dict:
    """نماد → پرچم‌ها. `{}` یعنی منبع نرسید — با «پرچمی ندارد» یکی نیست."""
    try:
        from api.funnel import _board_rows
        rows = _board_rows() or []
    except Exception:
        return {}
    out: dict = {}
    for r in rows:
        key = _FE.norm_symbol(r.get("symbol"))
        if not key or key in out:
            continue
        out[key] = {k: bool(r.get(k)) for k in TAPE_FLAG_KEYS}
    return out


def _attach_tape_flags(payload):
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return payload
    flags = _tape_flag_map()
    if not flags:
        payload["tape_flags_source"] = "unavailable"
        return payload
    for r in (payload.get("rows") or []):
        r["tape_flags"] = flags.get(_FE.norm_symbol(r.get("symbol")))
    payload["tape_flags_source"] = "api/market"
    return payload


def _mainwatch_with_flags(conn, group, industry, sort, desc, limit):
    return _attach_tape_flags(_mstat.mainwatch(conn, group, industry, sort, desc, limit))


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

@router.get("/api/mstat/phase")
def mstat_phase():
    """مرحلِ جلسه از وضعیتِ **رسمیِ** بازار (بند ۵ مأموریت، 1405-07-20).

    تنها منبعش `MarketData/GetMarketOverviewِ` خودِ بورس است که درِ جدولِ
    `market_index` می‌نشیند (نویسنده: `test_tsetmc.save_market_index`)؛
    `market_phase.py` فقط ترجمه می‌کند و آستانۀ تازۀ نمی‌سازد. بی‌ردیفِ رسمی
    `phase_source` برچسبِ ساعتی می‌گیرد و `official: false` — تا رابط بگوید
    این حدسِ تقویم است، نه رأیِ بازار. (توجه: `/api/mstat/phases` چیزِ دیگری
    است — شمارندهٔ چرخشِ وضعیتِ نمادها.)
    """
    return _mstat_call(_mstat.session_phase)


@router.get("/api/mstat/mainwatch")
def mstat_mainwatch(group: str = Query("eq_all"), industry: str = Query(""),
                    sort: str = Query("clock"), desc: bool = Query(True),
                    limit: int = Query(120)):
    """گام ۵.۲ — تابلوی نمادها؛ ستونِ اختلاف آخرین/پایانی مرتب‌شدنی است."""
    return _mstat_call(_mainwatch_with_flags, group, industry, sort, desc, limit)

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
                "mainwatch": _mainwatch_with_flags(conn, group, "", "clock", True, limit),
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
