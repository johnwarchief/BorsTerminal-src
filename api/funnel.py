"""api/funnel.py — اندپوینتِ داورِ canonicalِ قیف FTS.

فرانت دیگر حکمِ دوم نمی‌سازد: همین‌جا ردیف‌هایِ تابلو (با پرچم‌هایِ `tape_flags`)
و ردیف‌هایِ اسکرینر (با پنج شاخص و `tech_*`) به `funnel_engine.evaluate()`
می‌روند و حکمِ نهایی + trace + شمارشِ هر مرحله برمی‌گردد.

سه مسیر:
  GET  /api/funnel?preset=trend&fund_mode=standard
  POST /api/funnel   {preset, chain, fund_mode, params, exceptions}
  GET  /api/funnel/trace?symbol=X&preset=…   (خطِ زمانِ یک نماد)

منبعِ داده همان کشِ `/api/market` و `/api/screener` است — یعنی قیف داده‌اش را
از همان جایی می‌خواند که جدولِ تابلو و جدولِ بنیادی می‌خوانند (نه یک نسخۀ
سوم). اگر هیچ‌کدام آماده نباشد، صادقاً `no_data` برمی‌گردد؛ عددِ ساختگی نیست.
"""
from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from typing import Any

from fastapi import APIRouter, Request

import funnel_engine as FE
import funnel_registry as REG
import market_universe as MU

router = APIRouter()

# ردیابِ وضعیتِ معاملاتیِ جهان دیگر درِ این فایل نیست: یکِ ردیابِ مشترک درِ
# `market_universe` است و **بازسازیِ کشِ تابلو** (`api/market.py:_observe_universe`)
# آن را جلو می‌بَرَد؛ دامنه از کلِ تابلو ساخته می‌شود، نه ۶۰ ردیفِ اول، و هیچ نمادِ
# واجدِ شرایطی حذف نمی‌شود — فقط برچسبِ وضعیت و اولویتِ نمایشش ثبت می‌گردد.
#
# مسیرِ `/api/universe/live` هم به `api/market.py` رفته است (پیش‌ازین `_UNIVERSE.observe`
# فقط با درخواستِ خودِ endpoint جلو می‌رفت، پس «وضعیتِ زندهٔ جهان» بی‌آن درخواست هرگز
# تازه نمی‌شد و با revisionِ بازار بی‌ربط بود).


def _universe_priority() -> dict:
    """نماد → اولویتِ نمایشِ زنده (کمتر = بالاتر)؛ خالی یعنی هنوز مشاهده نشده."""
    try:
        return dict(MU.latest().get("priority") or {})
    except Exception:
        return {}


def _universe_status() -> dict:
    try:
        return dict(MU.latest().get("status_by") or {})
    except Exception:
        return {}

# کشِ قیف یک‌خانۀ «کلیدِ آخر» بود. صفحۀ مستر دو مصرف‌کنندۀ هم‌زمان دارد
# (کاکپیت با presetِ horizon و جدولِ غربالگری با presetِ انتخابی، به‌علاوه
# پنلِ نماد که 'custom' می‌خواهد)؛ پس هر دو پرسشِ متناوب *miss* می‌خورد و
# موتورِ کامل (~۰.۸-۱.۵ ثانیه رویِ ۵۸۶۳ ردیف) درِ هر poll دوباره اجرا می‌شد —
# یعنی دقیقاً همان جایی که مالک «درِ ساعتِ بازار خیلی سریع» می‌خواهد.
# حالا چند کلیدِ آخر نگه داشته می‌شود. سقفِ تعداد از *حافظه* می‌آید نه سلیقه:
# هر payload چند مگابایت است، پس دو خانۀ LRU بیشترِ صفحۀ واقعی را پوشش می‌دهد
# و سومینِ تازه، کهنه‌ترین را بیرون می‌کند.
_FUNNEL_CACHE: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
_FUNNEL_CACHE_MAX = 2
_FUNNEL_CACHE_LOCK = threading.Lock()


def _cache_get(key: str, now: float) -> dict[str, Any] | None:
    with _FUNNEL_CACHE_LOCK:
        ent = _FUNNEL_CACHE.get(key)
        if not ent or not ent.get("payload") or now - ent["ts"] >= TTL_S:
            return None
        _FUNNEL_CACHE.move_to_end(key)
        return ent


def _cache_put(key: str, payload: dict, now: float) -> None:
    with _FUNNEL_CACHE_LOCK:
        _FUNNEL_CACHE[key] = {"payload": payload, "ts": now}
        _FUNNEL_CACHE.move_to_end(key)
        while len(_FUNNEL_CACHE) > _FUNNEL_CACHE_MAX:
            _FUNNEL_CACHE.popitem(last=False)
# قیف رویِ همان ریتمِ تابلو تازه می‌شود؛ کشِ کوتاه جلویِ هر-کلیدِ Custom را
# از دوباره‌خوانیِ ۳۷۰۰ ردیف می‌گیرد، بی‌آنکه حکمی را کهنه کند.
TTL_S = 8.0


def _board_snapshot() -> tuple[list[dict], int | None]:
    """ردیف‌هایِ تابلو + **شمارۀ نشست** از همان کشِ `/api/market`.

    نشست لازم است چون ردیفِ serialised شده `d_even` ندارد (درِ `drop_unused`
    می‌افتد) و برچسبِ زمان‌مندِ توقف (§۸ رأیِ مالک: «ممنوع-متوقف (طی معاملات)»)
    بدونِ آن یا دروغ می‌گوید یا هرگز روشن نمی‌شود. `meta.d_even` همان چیزی است
    که خودِ تابلو منتشر می‌کند — یک منبعِ واحد، نه حدسِ ثانیهٔ ساعت.
    """
    from api.market import (_MarketInternalRequest, _build_market_response,
                            _market_snapshot)

    body, _t, _etag = _market_snapshot()
    if not body:
        resp = _build_market_response(_MarketInternalRequest())
        body = getattr(resp, "body", None) or b""
    if not body:
        return [], None
    data = body if isinstance(body, dict) else json.loads(
        body.decode("utf-8") if isinstance(body, bytes) else body)
    if not isinstance(data, dict):
        return [], None
    rows = list(data.get("data") or [])
    try:
        session = int((data.get("meta") or {}).get("d_even") or 0) or None
    except (TypeError, ValueError):
        session = None
    return rows, session


def _board_rows() -> list[dict]:
    """فقط ردیف‌ها (برایِ مصرف‌کننده‌هایی که نشست لازم ندارند)."""
    return _board_snapshot()[0]


def _screen_rows() -> list[dict]:
    from api.screener import _screener_cached

    payload = _screener_cached() or {}
    return list(payload.get("data") or [])


# ── زمینۀ تکنیکال: داوریِ ازپیش‌ساخته + امضایِ داده ──────────────────────
_TECH_CTX: dict[str, Any] = {"ts": 0.0, "scan": {}, "sigs": {}}


def _tech_context(max_age_s: float = 60.0) -> tuple[dict, dict]:
    """ستون‌هایِ tech_* را از `funnel_tech_scan` می‌خواند، نه از پنجاه ردیفِ
    اولِ اسکرینر. امضا هم همان‌جا می‌گوید کدام نماد اصلاً سابقهٔ قیمتی دارد.

    یک دقیقه کش: خواندنِ امضا رویِ ۴۳۳ هزار ردیف ~۰٫۴s است و هر پرسشِ قیف
    لازم نیست دوباره بزند. رشتهٔ پس‌زمینه جدول را تازه می‌کند و این‌جا فقط
    خوانده می‌شود — پس هیچ درخواستی منتظرِ داوری نمی‌ماند."""
    import sqlite3

    import funnel_tech_scan as SCAN
    from bors_config import DB_PATH

    now = time.time()
    if _TECH_CTX["scan"] and now - _TECH_CTX["ts"] < max_age_s:
        return _TECH_CTX["scan"], _TECH_CTX["sigs"]
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        scan = SCAN.stored(conn)
        sigs = SCAN.sig_map(conn)
    except sqlite3.Error:
        # بانکِ نبوده یا قفل است: داوریِ ناقص بهتر از پاسخِ ساختگی نیست —
        # موتور همان حالت‌هایِ صریح (PENDING/UNAVAILABLE) را می‌گوید.
        return {}, {}
    finally:
        conn.close()
    _TECH_CTX.update({"ts": now, "scan": scan, "sigs": sigs})
    return scan, sigs


def _need_scan(payload: dict) -> list[str]:
    """نمادهایی که به این گام رسیده‌اند ولی داوریِ ساخته‌شدۀ تکنیکال ندارند."""
    out = []
    for dec in (payload.get("trace") or {}).get("technical") or []:
        codes = {w.get("code") for w in (dec.get("why") or [])}
        if codes & {"TECH_SCAN_PENDING", "TECH_UNMEASURED"}:
            out.append(str(dec.get("symbol") or ""))
    return [s for s in out if s]


@router.get("/api/funnel/registry")
def get_registry():
    """همان رجیستری که موتور می‌خواند — فهرستِ Custom از اینجا می‌آید."""
    return REG.as_json()


@router.get("/api/funnel/trace")
def get_trace(symbol: str, preset: str = "trend", chain: str = "",
              fund_mode: str = "standard", exceptions: str = ""):
    """خطِ زمانِ یک نماد: Universe ← تابلو ← هر فیلتر ← تکنیکال ← بنیادی ← تحویل.

    چرا جدا: `timeline` برایِ تک‌تکِ ۵٫۸ هزار نماد درِ پاسخِ فهرست می‌آمد و نیمی
    از حجمِ پاسخ می‌شد، در حالی که یک «چرا؟» درِ بازرِس فقط یک نماد را می‌خواهد.
    چیزی حذف نشده — همان داده، درِ درخواستِ خودش، از همان کشِ هشت‌ثانیه‌ای.
    """
    # همان پارامترهایی که جدولِ غربالگری می‌فرستد — وگرنه بازرِس و جدول دو
    # حکمِ متفاوت برایِ یک نماد نشان می‌دهند (کلیدِ کشِ `_run` هم همین است، پس
    # درخواستِ ردپا معمولاً به همان پاسخِ آماده می‌خورد و اجرایِ دوم نیست).
    try:
        exc = json.loads(exceptions) if exceptions else {}
        exc = exc if isinstance(exc, dict) else {}
    except ValueError:
        exc = {}
    payload = _run(preset, [c for c in chain.split(",") if c], fund_mode, {}, exc,
                   full=True)
    tl = (payload.get("timeline") or {}).get(symbol)
    cell = (payload.get("status_matrix") or {}).get(symbol)
    if tl is None and cell is None:
        return {"status": "not_found", "symbol": symbol,
                "message": "این نماد درِ جامعۀ این نشست نیست",
                "universe": payload.get("universe")}
    return {"status": "success", "symbol": symbol, "timeline": tl or [],
            "matrix": cell, "universe": payload.get("universe"),
            "engine_version": payload.get("engine_version"),
            "ruleset_version": payload.get("ruleset_version"),
            "as_of": payload.get("as_of")}


@router.get("/api/funnel")
def get_funnel(preset: str = "trend", chain: str = "", fund_mode: str = "standard"):
    return _run(preset, [c for c in chain.split(",") if c], fund_mode, {}, {})


@router.post("/api/funnel")
async def post_funnel(request: Request):
    b = await request.json()
    if not isinstance(b, dict):
        b = {}
    return _run(
        str(b.get("preset") or "trend"),
        [str(x) for x in (b.get("chain") or [])],
        str(b.get("fund_mode") or "standard"),
        b.get("params") if isinstance(b.get("params"), dict) else {},
        {str(k): [str(x) for x in (v or [])] for k, v in (b.get("exceptions") or {}).items()}
        if isinstance(b.get("exceptions"), dict) else {},
    )


def _strip(payload: dict) -> dict:
    """پاسخِ فهرست بی‌`timeline`: خطِ زمانِ همهٔ نمادها ۹ مگابایت از ۱۹ مگابایت
    پاسخ را می‌گرفت و جدول هیچ‌وقت همه‌اش را نمی‌خواند. `/api/funnel/trace`
    همان را نمادبه‌نماد می‌دهد؛ وضعیتِ هر نماد درِ هر گام همچنان درِ
    `status_matrix` هست، پس هیچ «سنجیده نشده»ای از پاسخ نمی‌افتد."""
    out = dict(payload)
    out.pop("timeline", None)
    return out


def _run(preset: str, chain: list[str], fund_mode: str,
         params: dict[str, dict[str, Any]], exceptions: dict[str, list[str]],
         full: bool = False) -> dict:
    if preset not in REG.PRESET_BY_ID:
        return {"status": "error", "message": f"presetِ ناشناخته: {preset}"}
    if fund_mode not in ("hard", "standard", "exception"):
        return {"status": "error", "message": f"fund_modeِ ناشناخته: {fund_mode}"}
    key = json.dumps([preset, chain, fund_mode, sorted(params.items()),
                      sorted((k, sorted(v)) for k, v in exceptions.items())],
                     ensure_ascii=False)
    now = time.time()
    hit = _cache_get(key, now)
    if hit:
        cached = hit["payload"]
        if full:
            return cached
        out = _strip(cached)
        out["cached_for_ms"] = int((now - hit["ts"]) * 1000)
        return out

    board, session = _board_snapshot()
    screen = _screen_rows()
    if not board:
        return {"status": "no_data", "message": "تابلو هنوز در این اجرا ساخته نشده",
                "universe": {"board": 0, "screened": len(screen)}}
    scan, sigs = _tech_context()
    uni_pri = _universe_priority()
    uni_st = _universe_status()
    try:
        payload = FE.evaluate(board, screen, preset=preset, custom_chain=chain,
                              fund_mode=fund_mode, params=params, exceptions=exceptions,
                              tech_scan=scan, tech_sigs=sigs, session_day=session,
                              universe_priority=uni_pri, universe_status=uni_st)
    except KeyError as e:
        return {"status": "error", "message": str(e)}
    # داوریِ ناکام‌نشده: همان نمادها درِ پس‌زمینه ساخته می‌شوند. پاسخِ همین
    # درخواست تغییرِ وضعیت نمی‌دهد (منتظر نمی‌مانیم)، ولی پرسشِ بعدی رأی دارد.
    todo = _need_scan(payload)
    if todo:
        import funnel_tech_scan as SCAN
        payload["tech_scan"] = {"pending_symbols": len(todo), **(SCAN.start_refresh(todo))}
    else:
        import funnel_tech_scan as SCAN
        payload["tech_scan"] = {"pending_symbols": 0, **SCAN.bg_status()}
    _cache_put(key, payload, now)
    return payload if full else _strip(payload)
