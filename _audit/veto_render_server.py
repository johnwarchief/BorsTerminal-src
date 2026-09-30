# -*- coding: utf-8 -*-
"""_audit/veto_render_server.py -- بک‌اندِ موقتِ ۸۰۰۳ با تقویمِ کپی‌شده

فقط برایِ اثباتِ زندهٔ «بجِ وتوی مجمع» در مرورگر: تقویمِ واقعی دست‌نخورده می‌ماند و
یک رویدادِ مجمعِ شرکتیِ ساختگی روی **کپی**‌اش می‌نشیند، چون در تقویمِ امروز هیچ
شرکتی مجمعِ ۱۴ روزۀ پیشِ رو ندارد (هر ۱۷ رویدادِ پیشِ رو صندوق است).
اجرا:   VETO_SYM=<نماد> python _audit/veto_render_server.py
"""
from __future__ import annotations

import datetime
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import api.chart as chart  # noqa: E402

SYM = os.environ.get("VETO_SYM", "").strip()
TITLE = os.environ.get("VETO_TITLE", "آگهی دعوت به مجمع عمومی فوق العاده (اثباتِ رندر — دادهٔ ساختگی)")
if not SYM:
    raise SystemExit("VETO_SYM لازم است")

ALT = os.path.join(HERE, "cache.veto_render.json")
src = chart._CAL_CACHE_PATH
day = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
data = json.load(io.open(src, encoding="utf-8"))
data["events"] = [
    e for e in data.get("events", [])
    if str(e.get("asset_symbol_trade") or "").strip() != SYM
]
data["events"].append({
    "asset_id": "",
    "asset_symbol_trade": SYM,
    "date_time": f"{day}T11:00:00+03:30",
    "description": TITLE,
    "report_id": "0",
    "event_title": TITLE,
    "event_type_id": 2,
    "event_time": "11:00",
    "link": "",
})
json.dump(data, io.open(ALT, "w", encoding="utf-8"), ensure_ascii=False)

chart._CAL_CACHE_PATH = ALT
chart._cal_cache["mtime"] = 0.0
chart._cal_cache["events"] = []

from app import app  # noqa: E402

if __name__ == "__main__":
    print(f"[veto-render] تقویمِ کپی: {ALT} | نماد: {SYM} | مجمع: {day}", flush=True)
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8003, log_level="warning")
