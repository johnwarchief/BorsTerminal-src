"""api/funnel.py — اندپوینتِ داورِ canonicalِ قیف FTS.

فرانت دیگر حکمِ دوم نمی‌سازد: همین‌جا ردیف‌هایِ تابلو (با پرچم‌هایِ `tape_flags`)
و ردیف‌هایِ اسکرینر (با پنج شاخص و `tech_*`) به `funnel_engine.evaluate()`
می‌روند و حکمِ نهایی + trace + شمارشِ هر مرحله برمی‌گردد.

دو مسیر:
  GET  /api/funnel?preset=trend&fund_mode=standard
  POST /api/funnel   {preset, chain, fund_mode, params, exceptions}

منبعِ داده همان کشِ `/api/market` و `/api/screener` است — یعنی قیف داده‌اش را
از همان جایی می‌خواند که جدولِ تابلو و جدولِ بنیادی می‌خوانند (نه یک نسخۀ
سوم). اگر هیچ‌کدام آماده نباشد، صادقاً `no_data` برمی‌گردد؛ عددِ ساختگی نیست.
"""
from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, Request

import funnel_engine as FE
import funnel_registry as REG

router = APIRouter()

_FUNNEL_CACHE: dict[str, Any] = {"key": "", "payload": None, "ts": 0.0}
# قیف رویِ همان ریتمِ تابلو تازه می‌شود؛ کشِ کوتاه جلویِ هر-کلیدِ Custom را
# از دوباره‌خوانیِ ۳۷۰۰ ردیف می‌گیرد، بی‌آنکه حکمی را کهنه کند.
TTL_S = 8.0


def _board_rows() -> list[dict]:
    """ردیف‌هایِ تابلو از همان کشِ `/api/market`؛ اگر اجرا سرد بود، یک‌بار
    هم‌زمان ساخته می‌شود (همان مسیری که نخِ پس‌زمینه می‌رود) — نه یک بدنۀ
    سومِ بی‌ربط، و نه «بدونِ داده»ای که فقط به‌خاطرِ زمانِ بوت باشد."""
    from api.market import (_MarketInternalRequest, _build_market_response,
                            _market_snapshot)

    body, _t, _etag = _market_snapshot()
    if not body:
        resp = _build_market_response(_MarketInternalRequest())
        body = getattr(resp, "body", None) or b""
    if not body:
        return []
    data = body if isinstance(body, dict) else json.loads(
        body.decode("utf-8") if isinstance(body, bytes) else body)
    rows = data.get("data") if isinstance(data, dict) else None
    return list(rows or [])


def _screen_rows() -> list[dict]:
    from api.screener import _screener_cached

    payload = _screener_cached() or {}
    return list(payload.get("data") or [])


@router.get("/api/funnel/registry")
def get_registry():
    """همان رجیستری که موتور می‌خواند — فهرستِ Custom از اینجا می‌آید."""
    return REG.as_json()


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


def _run(preset: str, chain: list[str], fund_mode: str,
         params: dict[str, dict[str, Any]], exceptions: dict[str, list[str]]) -> dict:
    if preset not in REG.PRESET_BY_ID:
        return {"status": "error", "message": f"presetِ ناشناخته: {preset}"}
    if fund_mode not in ("hard", "standard", "exception"):
        return {"status": "error", "message": f"fund_modeِ ناشناخته: {fund_mode}"}
    key = json.dumps([preset, chain, fund_mode, sorted(params.items()),
                      sorted((k, sorted(v)) for k, v in exceptions.items())],
                     ensure_ascii=False)
    now = time.time()
    if _FUNNEL_CACHE["key"] == key and now - _FUNNEL_CACHE["ts"] < TTL_S and _FUNNEL_CACHE["payload"]:
        out = dict(_FUNNEL_CACHE["payload"])
        out["cached_for_ms"] = int((now - _FUNNEL_CACHE["ts"]) * 1000)
        return out

    board, screen = _board_rows(), _screen_rows()
    if not board:
        return {"status": "no_data", "message": "تابلو هنوز در این اجرا ساخته نشده",
                "universe": {"board": 0, "screened": len(screen)}}
    try:
        payload = FE.evaluate(board, screen, preset=preset, custom_chain=chain,
                              fund_mode=fund_mode, params=params, exceptions=exceptions)
    except KeyError as e:
        return {"status": "error", "message": str(e)}
    _FUNNEL_CACHE.update({"key": key, "payload": payload, "ts": now})
    return payload
