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

if os.environ.get("BORS_NO_FETCH_LOOPS") == "1":
    import subprocess
    _orig_popen = subprocess.Popen
    def _safe_popen(args, *a, **kw):
        arg_str = " ".join(args) if isinstance(args, (list, tuple)) else str(args)
        if "codal_fetcher" in arg_str or "codal_fts_updater" in arg_str:
            class FakeProc:
                pid = 99999
                def poll(self): return 0
                def wait(self, timeout=None): return 0
            return FakeProc()
        return _orig_popen(args, *a, **kw)
    subprocess.Popen = _safe_popen

    import api._sync_market as _sm
    _sm._run_market_sync = lambda: None

    import api._sync_codal as _sc
    _sc._codal_db_worker = lambda *a, **kw: None

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
