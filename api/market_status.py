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
from fastapi.responses import JSONResponse
import threading
import time

import market_state as _MS
import mstat_engine as _mstat
import funnel_engine as _FE


router = APIRouter()


# ── گروهِ نامعتبر ⇒ خطایِ روشن، نه صفرِ معتبر ──────────────────────────────
# سنجشِ زندۀ 2026-10-17 (سرورِ نصبی، h_even 100502):
#   thermometer?group=all          ⇒ 254/749/8
#   thermometer?group=eq           ⇒ status:"ok" با 0/0/0
#   thermometer?group=idx|fund|bond|am|tf|mutual|fund_etf ⇒ همان صفرها
# علت: `_select(rows, cat)` برایِ دسته‌ناشناخته فهرستِ خالی می‌دهد و شمارشِ خالی
# درِ پاسخ «بازارِ صفر/آرام» خوانده می‌شود. این دادهٔ ناقص است که معتبر نمایش
# داده می‌شود، و درِ مقایسه باِ مرجع دقیقاً همان جایی است که عددِ بدل می‌سازد.
# `clientsplit?tab=<بیگانه>` هم بدتر بود: `_TAB_CAT.get(tab, "all")` آن را بی‌صدا
# به «کل بازار» تبدیل می‌کرد، یعنی پاسخِ درست برایِ پرسشِ غلط.
#
# چرا اصلاح بی‌خطر است: رابطِ ما فقط `all` و `eq_all` می‌فرستد
# (features/market/api/useMarketPulse.ts:368-369 و useMstatHistogram(group='all')
# در useMarketStatusFeed.ts:52). و صفرِ **واقعی** هنوز 200 است: دسته‌ای که امروز
# معامله‌ای ندارد (مثلاً `silver_fund`) همان `positive:0` را می‌گیرد — تفکیکِ
# «گروه نامعتبر» از «گروهِ معتبرِ بی‌معامله» عمدی است و گارد می‌سنجدش.
_VALID_GROUP = frozenset(k for k, _ in _mstat.CATEGORY_ROWS) | frozenset(_mstat._TAB_CAT)


def _bad_param(param: str, value: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={
        "status": "error", "code": "UNKNOWN_GROUP", param: value,
        "allowed": sorted(_VALID_GROUP),
        "detail": "گروه/تبِ داده‌شده درِ تعریفِ موتور نیست؛ بی‌داوریِ خالی "
                  "پاسخ داده نمی‌شود"})


def _check_group(param: str, value: str) -> bool:
    return str(value or "") in _VALID_GROUP

# ---- Phase پرفورمنس (N3): کشِ نتیجه به‌ازای revision واقعیِ بانک ----
# هر پنل mstat کل ۵٫۵هزار ردیف را می‌روبید (~250-830ms هسته در هر درخواست)؛
# سنجهٔ baseline: ~۱٫۵s CPU هر نفسِ نبض. کلیدِ کش همان چهار نشانه‌ای است که
# «حالتِ بانک» را کامل توصیف می‌کنند — revisionِ تابلو، static_rev (الگوی
# ازپیش‌پذیرفتۀ خودِ api/market.py:495-520)، روزِ نشست، و آخرین نقطۀ mstat_snap.
# بی‌هیچ محاسبهٔ موازی: همان fn، همان فرمول، همان عدد؛ فقط یک‌بار به‌ازای هر
# حالت. TTL سقفِ امانت هم نگهبانِ بی‌سر‌و‌صداست.
_MSTAT_TTL_S = 45.0
# سقفِ امانتِ پاسخِ کهنه: «کهنه» تنها تا این اندازه از محاسبهٔ تازه جلو می‌افتد؛
# بعد از آن درخواست‌کننده خودش می‌سازد. دادهٔ واقعی با جابه‌جاییِ نشانه (`mstat_snap`)
# کلید را عوض می‌کند، پس این سقف هیچ‌وقت دادهٔ روزِ *پیش* را جای روزِ تازه نمی‌زند —
# فقط همان حالتِ بانک را چند ثانیه بیشتر نگه می‌دارد تا بازسازیِ درِ پس‌زمینه برسد.
_MSTAT_STALE_MAX_S = 90.0
_MSTAT_CACHE: dict = {}
_MSTAT_LOCK = threading.Lock()
_MSTAT_WAIT: dict = {}          # کلید در حالِ ساختِ درون‌خطی ⇒ رویدادِ منتظرها
_MSTAT_BG: set = set()          # کلیدهایی که بازسازی‌شان درِ پس‌زمینه جاری است


def _mstat_marker(conn):
    """اثرِ حالتِ تایم‌لاین: آخرین (روز، ساعت) ثبت‌شده در mstat_snap.
    جدولِ نباشد None ⇒ کش بی‌استفاده (اولین دورِ بوت)."""
    try:
        row = conn.execute(
            "SELECT IFNULL(MAX(d_even),0), IFNULL(MAX(h_even),0) FROM mstat_snap"
        ).fetchone()
        return (int(row[0] or 0), int(row[1] or 0))
    except Exception:
        return None


def _mstat_state():
    """حالتِ بانک را یک‌بار می‌پویشد: (نشاندۀ تابلو، نشاندۀ ثابت، روزِ نشست،
    نشانۀ mstat_snap). نشانۀ None یعنی کش نباید درِ کار وسط بیاید.

    چرا جدا شده: «کل تب» ده پنل را از همین کش می‌خواند. اگر هر پنل این پویش را
    خودش تکرار کند (سنجشِ این شب: ~۸-۱۰ms به‌ازای پنل، از همین روپوشِ کوئری و
    کپی)، ترکیبِ بی‌کشِ تب ~۱۰۳ms می‌شود. با یکِ پویش درِ هر درخواست، ده پنل تنها
    یکِ خواندنِ کش + کپی‌اند.
    """
    conn = get_db()
    try:
        marker = _mstat_marker(conn)
    finally:
        conn.close()
    if marker is None:
        return None
    return (_MS.revision(), _MS.static_rev(), _MS.session_day(), marker)


def _mstat_key_for(key, state=None):
    """کلیدِ «حالتِ بانک» یا None وقتی که کش نباید درِ کار وسط بیاید."""
    if state is None:
        state = _mstat_state()
    if state is None:
        return None
    return (key,) + tuple(state)


def _mstat_store(full_key, now, out):
    """ذخیره در کش؛ خطا هرگز ذخیره نمی‌شود. `now` همان ساعتِ تزریقیِ فراخوان است."""
    if not isinstance(out, dict) or out.get("status") == "error":
        return False
    with _MSTAT_LOCK:
        if len(_MSTAT_CACHE) > 240:
            _MSTAT_CACHE.clear()
        _MSTAT_CACHE[full_key] = (now, out)
    return True


def _mstat_compute(fn, args, kw):
    """یک اتصال، یک فراخوانی. خطای موتور ⇒ status=error نه ۵۰۰، چون یک پنلِ خراب
    نباید کل تب وضعیت بازار را از کار بیندازد."""
    conn = get_db()
    try:
        out = fn(conn, *args, **kw)
        if isinstance(out, dict):
            out.setdefault("source", "local:market.db")
    except Exception as e:
        return {"status": "error", "message": str(e), "source": "local:market.db"}
    finally:
        conn.close()
    return out


def _mstat_bg_rebuild(full_key, fn, args, kw):
    """بازسازیِ پس‌زمینه: پاسخِ کهنه را نمی‌گیرد و درخواست‌کننده را نمی‌بلوکد."""
    try:
        out = _mstat_compute(fn, args, kw)
        _mstat_store(full_key, time.monotonic(), out)
    except Exception:
        # ساختِ پس‌زمینه شکست بخورد، کشِ کهنه می‌ماند و دورِ بعد دوباره تلاش می‌کند؛
        # هرگز خطا جای داده می‌نشیند یا منتظرِ بی‌پایان باز می‌ماند.
        pass
    finally:
        with _MSTAT_LOCK:
            _MSTAT_BG.discard(full_key)


def _mstat_call(fn, *args, ttl_s=None, refresh="bg", state=None, stale_ok=True, **kw):
    """پنلِ mstat با کشِ هر-حالت + stale-while-revalidate + تک‌پروازگی.

    چرا این لایه اضافه شد (سنجشِ همین شب، بک‌اندِ HEAD با حلقه‌هایِ روشن،
    `_audit/perf_live/loops_on_22h_*.jsonl`): پوششِ ttl تنها «بی‌محاسبه دوباره» را
    حل می‌کرد، نه «پایانِ ttl». هر بار که کش می‌سوخت — درِ عمل ۵۶ ثانیه یک‌بار —
    همان یکِ درخواستِ کاربر کلِ ده پنل را درون‌خطی می‌ساخت:
    `/api/mstat/board` p50 = ۱۸٫۰ms ولی p95 = ۲٬۵۷۰٫۴ms (نمونۀ ۰/۴/۸/۱۲)، و
    `/api/mstat/summary` هم‌زمان ۲۸۵ms. یعنی یکِ کاربرِ بی‌گناه به‌جایِ نبضِ بازار
    دو و نیم ثانیه منتظر می‌ماند. حالا پاسخِ کهنه فوراً می‌رود و بازسازیِ همان کلید
    یک‌بار درِ پس‌زمینه می‌دود (`_MSTAT_BG`)، و برایِ cold miss هم تک‌پروازگی
    (`_MSTAT_WAIT`) جلویِ «هر ده پولینگ، ده بازسازی» را می‌گیرد.

    `stale_ok=False` برایِ پنل‌هایی است که عددشان از *ساعتِ دیوار* ساخته می‌شود:

    تازگیِ لازم برایِ تصمیمِ حساس دست‌نخورده: `ttl_s=0` بی‌کش است، نشانه‌یِ جابه‌جا
    شده کلیدِ تازه می‌خواهد (پس هیچ دادهٔ روزِ پیشی سرو نمی‌شود)، و beyond-cap
    درون‌خطی می‌سازد. `refresh="inline"` رفتارِ قدیمِ کاملِ همین مسیر است.
    """
    ttl = _MSTAT_TTL_S if ttl_s is None else float(ttl_s)
    key = (fn.__name__, args, tuple(sorted(kw.items())))
    if ttl <= 0 or refresh == "inline":
        return dict(_mstat_compute(fn, args, kw))
    try:
        full_key = _mstat_key_for(key, state)
    except Exception:
        full_key = None
    if full_key is None:
        return dict(_mstat_compute(fn, args, kw))

    now = time.monotonic()
    with _MSTAT_LOCK:
        hit = _MSTAT_CACHE.get(full_key)
        if hit is not None and (now - hit[0]) < ttl:
            return dict(hit[1])
        stale = hit[1] if hit is not None else None
        age = None if hit is None else now - hit[0]
        serve_stale = (stale is not None and age is not None
                       and age <= _MSTAT_STALE_MAX_S and stale_ok)
        if serve_stale:
            if full_key not in _MSTAT_BG:
                _MSTAT_BG.add(full_key)
                spawn = True
            else:
                spawn = False
            ev, owner = None, False
        else:
            spawn = False
            ev = _MSTAT_WAIT.get(full_key)
            if ev is not None:
                owner = False
            else:
                _MSTAT_WAIT[full_key] = ev = threading.Event()
                owner = True
    if serve_stale:
        if spawn:
            threading.Thread(target=_mstat_bg_rebuild,
                             args=(full_key, fn, args, kw), daemon=True).start()
        return dict(stale)
    if not owner:
        # یکی دیگر دارندۀ همین cold miss است؛ منتظرِ همان یک نتیجه می‌مانیم،
        # بی‌این‌که دوباره بسازیم. بی‌پاسخ بماند، همان مسیرِ بی‌کش را می‌رویم.
        ev.wait(timeout=max(5.0, ttl + _MSTAT_STALE_MAX_S))
        with _MSTAT_LOCK:
            hit = _MSTAT_CACHE.get(full_key)
        if hit is not None:
            return dict(hit[1])
        return dict(_mstat_compute(fn, args, kw))
    try:
        out = _mstat_compute(fn, args, kw)
        _mstat_store(full_key, now, out)
    finally:
        with _MSTAT_LOCK:
            _MSTAT_WAIT.pop(full_key, None)
        ev.set()
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
    if not _check_group("group", group):
        return _bad_param("group", group)
    return _mstat_call(_mstat.histogram, group)

@router.get("/api/mstat/thermometer")
def mstat_thermometer(group: str = Query("all")):
    """گام ۲.۲ — نوار مثبت/منفی و قانون فرصت ورود."""
    if not _check_group("group", group):
        return _bad_param("group", group)
    return _mstat_call(_mstat.thermometer, group)

@router.get("/api/mstat/depth")
def mstat_depth(group: str = Query("all")):
    """گام ۲.۳ و ۳.۱ — ارزش ۵ خط اول + تفکیک صف‌ها."""
    if not _check_group("group", group):
        return _bad_param("group", group)
    return _mstat_call(_mstat.depth, group)

@router.get("/api/mstat/clientsplit")
def mstat_clientsplit(tab: str = Query("all")):
    """گام ۲.۴ و ۵.۱ — تفکیک حقیقی/حقوقی به تفکیک تب."""
    if not _check_group("tab", tab):
        return _bad_param("tab", tab)
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
    # `stale_ok=False`: سنجشِ این شب (B-2) نشان داد تنها فیلدی که میانِ دو ساختِ
    # یکسانِ حالتِ بانک فرق می‌کند `phase.clock_now` است — یعنی همین رأیِ جلسه.
    # پنلِ ارزان است (compute ~۷ms)؛ پس درِ انقضا *بازسازیِ درون‌خطی* می‌شود و
    # هرگز کهنه سرو نمی‌شود، تا نشانِ «باز/متوقف/پایان» با سقفِ ۹۰ ثانیه عقب نیفتد.
    return _mstat_call(_mstat.session_phase, stale_ok=False)


@router.get("/api/mstat/mainwatch")
def mstat_mainwatch(group: str = Query("eq_all"), industry: str = Query(""),
                    sort: str = Query("clock"), desc: bool = Query(True),
                    limit: int = Query(120)):
    """گام ۵.۲ — تابلوی نمادها؛ ستونِ اختلاف آخرین/پایانی مرتب‌شدنی است."""
    if not _check_group("group", group):
        return _bad_param("group", group)
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

def _panel(fn, *args, state=None):
    """یکِ پنل از کشِ هر-حالت، بی‌کلیدِ `source` که `_mstat_call` می‌افزاید.

    درِ «کل تب» آن کلیدِ افزوده بیرون می‌ماند تا بدنه با دیروز یکی بماند
    (سنجشِ ۱۴۰۵-۰۷-۲۷: تنها تفاوتِ پاسخِ دو نسخه، همین کلید بود؛ پنل‌هایِ
    mstat خودشان `source` تولید نمی‌کنند). `state` پویشِ حالتِ بانک را ازِ
    فراخوانِ بالاتر می‌گیرد، نه ده بار ازِ بانک.
    """
    out = _mstat_call(fn, *args, state=state)
    if isinstance(out, dict):
        out.pop("source", None)
    return out


def _board_all(conn, group: str, limit: int, state=None) -> dict:
    """ده پنلِ تب وضعیت بازار در یکِ بدنه — تنها پیاده‌سازیِ این ترکیب.

    هر پنل از **همان** `_mstat_call` می‌گذرد که مسیرهایِ تک‌پنلی می‌گذرند، پس
    «کل تب» و «پنلِ تنها» یک محاسبه را دو بار نمی‌سازند: UIِ امروز هم
    `/api/mstat/board` را می‌زند هم `summary`/`depth`/`thermometer` را
    (`useMarketPulse`) و پیش از این هر دو گروه، ده پنل را جدا جدا حساب
    می‌کردند (اندازه: 753ms p50 برایِ تابلو + ~۱۳۰ms برایِ هر پنلِ تنها).
    `conn` این‌جا مصرف نمی‌شود — هر پنل اتصالِ خودش را باز می‌کند تا کشِ
    هر-حالت درست کلید بخورد.

    خودِ این بدنه دیگر رکوردِ کشِ جدا ندارد (سنجشِ ۱۴۰۵-۰۷-۲۳، بندِ ۲.۲): کشِ
    دو سطحی هم «دو بار ساختنِ همان پنل» می‌ساخت (بازسازیِ پس‌زمینۀ تب درِ
    همان لحظه‌ای که پنلِ تنها هم بازسازی می‌خواست؛ CPUِ میانیگین ۷٫۳٪ ⇒ ۱۴٫۱٪)
    هم بدنه‌ای می‌ساخت که از پنل‌هایِ کهنه چسبیده بود. ترکیبِ بی‌کش با یکِ
    پویشِ مشترکِ حالت (`state`) ~۱۷ms است و هر پنل دقیقاً یک‌بار ساخته می‌شود.
    """
    st = _mstat_state() if state is None else state
    return {"status": "ok", "source": "local:market.db",
            "summary": _panel(_mstat.summary, state=st),
            "thermometer": _panel(_mstat.thermometer, group, state=st),
            "histogram": _panel(_mstat.histogram, group, state=st),
            "depth": _panel(_mstat.depth, group, state=st),
            "clientsplit": _panel(_mstat.client_split, "all", state=st),
            "mainwatch": _panel(_mainwatch_with_flags, group, "", "clock", True, limit, state=st),
            "industries": _panel(_mstat.industries, state=st),
            "smartmoney": _panel(_mstat.smart_money, state=st),
            "timeline": _panel(_mstat.timeline, "cum", state=st),
            "phases": _panel(_mstat.phases, state=st)}


@router.get("/api/mstat/board")
def mstat_board(group: str = Query("eq_all"), limit: int = Query(60)):
    """تک‌درخواستِ کل تب. polling هر ۳۰–۶۰ ثانیه است و ۹ درخواستِ جدا هم
    شبکه را درگیر می‌کند هم مرورگر را؛ این یکی باعث می‌شود هر بارِ رندر،
    یک round-trip باشد (خط قرمز: رندر روان بدون افت فریم).

    چرا از `_mstat_call` نمی‌گذرد (اندازۀ ۱۴۰۵-۰۷-۲۳، بندِ ۲.۲): قبلاً می‌گذشت و
    خودش هم کش داشت — یعنی یکِ حالتِ بانک دو بار درِ کش (تب + ده پنل). همان‌جا
    سنجیده شد که پایانِ ttlِ تب، ده پنل را درون‌خطی می‌ساخت و پاسخِ یکِ کاربر
    ۲٬۵۷۰ms می‌شد. حالا تب از پنل‌هایِ کش‌خورده می‌سازد: یکِ بازسازی به‌ازای هر
    پنل، سروِ کهنه به‌جایِ بلوکه‌شدن، و بدنه‌ای که همهٔ پنل‌هایش از یکِ حالتِ بانک
    اند. پاسخ و شمارِ ردیف‌ها دست‌نخورده (تطبیقِ بدنه: §بندِ ۲.۲ِ سندِ مأموریت)."""
    st = _mstat_state()
    conn = get_db()
    try:
        return _board_all(conn, group, limit, state=st)
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
