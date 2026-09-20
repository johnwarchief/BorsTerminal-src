"""api -- router modules split verbatim out of app.py.

app.py builds the FastAPI application, mounts /static, installs the
no-cache middleware and include_router()s every module below in the same
order the routes originally appeared in app.py.
"""
from fastapi import APIRouter


def api_router() -> APIRouter:
    """Aggregate every module router into one APIRouter."""
    from . import (market, chart, selection, watchlist, fundamental, market_status, screener, _sync_market, _export, _sync_codal, adb, notify, update, _pipeline, engine, market_index)
    agg = APIRouter()
    for mod in (market, chart, selection, watchlist, fundamental, market_status, screener, _sync_market, _export, _sync_codal, adb, notify, update, _pipeline, engine, market_index):
        agg.include_router(mod.router)
    return agg
