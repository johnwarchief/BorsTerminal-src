#!/usr/bin/env python
"""سرورِ پاریتی: app را رویِ کپیِ BORS_DATA_DIR بالا می‌آورد، بی‌شبکه.

`codal_fetcher.DB_PATH` ثابتِ ماژول است و به BORS_DATA_DIR گوش نمی‌دهد؛ هوکِ
استارتِ app همان را migrate می‌کند. برایِ سنجشِ پاریتی این یعنی بالقوه نوشتن رویِ
بانکِ عملیاتی، پس پیش از importِ app اشاره‌گر را به کپیِ موقت می‌بندیم. هیچ
حذف/بازنویسی‌ای این‌جا نیست — فقط مسیر عوض می‌شود.

اجرا: BORS_DATA_DIR=<copy> BORS_NO_FETCH_LOOPS=1 BORS_CODAL_OFFLINE=1 \
      BORS_CODAL_AUTO=0 python tools/parity/serve_market_copy.py
"""
import os
import sys

DATA_DIR = (os.environ.get("BORS_DATA_DIR") or "").strip()
if not DATA_DIR:
    raise SystemExit("BORS_DATA_DIR is required")
PORT = int(os.environ.get("BORS_PARITY_PORT", "8299"))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import codal_fetcher  # noqa: E402  (باید پیش از app بیاید)

codal_fetcher.DB_PATH = os.path.join(DATA_DIR, "market.db")

import uvicorn  # noqa: E402
from app import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
