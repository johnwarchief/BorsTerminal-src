# -*- coding: utf-8 -*-
"""dev/phase5_isolated_server.py — سرورِ ایزولۀِ Stage 9 با **کپیِ** market.db.

چرا این فایل: گِیتِ Phase 5 می‌گوید «هیچ write روی market.db عملیاتی» و «برای تستِ
تغییردهنده از کپیِ ایزوله». ماژول‌های api با `from bors_config import DB_PATH` مقدار
را درِ import می‌خوانند؛ پس باید پیش از importِ `app` مسیرها را جایگزین کرد — همان
روشِ dev/boot_page_v1081.py.

کپی با shutil.copy2 ساخته می‌شود (بانکِ عملیاتی فقط خوانده می‌شود). تمامِ مسیرهای
نوشتنیِ WORK_DIR (user.db، sync_status، market_sync، codal_control، fts_thresholds،
price_basis) هم به همان پوشۀِ موقت می‌روند تا هیچ فایلِ جانبیِ مخزن دست‌نخورده بماند.

اجرا:  python dev/phase5_isolated_server.py [--port=8123]
خروجی: یک خطِ `ISOLATED-PORT <port>` و `ISOLATED-DB <path>` (برایِ هارنس مرورگر)
"""
import os
import shutil
import socket
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

SRC_DB = os.path.join(ROOT, "market.db")
OPER_DB = os.path.abspath(SRC_DB)


def _arg(name, default):
    kv = [a for a in sys.argv if a.startswith("--" + name + "=")]
    return kv[0].split("=", 1)[1] if kv else default


def free_port():
    p = int(_arg("port", "0") or 0)
    if p:
        return p
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    if not os.path.exists(SRC_DB):
        print("market.db نیست:", SRC_DB)
        return 2
    work = tempfile.mkdtemp(prefix="bors-phase5-e2e-")
    db = os.path.join(work, "market.db")
    shutil.copy2(SRC_DB, db)

    import bors_config as BC

    BC.WORK_DIR = work
    BC.DB_PATH = db
    BC.USER_DB_PATH = os.path.join(work, "user.db")
    BC.STATUS_PATH = os.path.join(work, "sync_status.json")
    BC.OD_STATUS_PATH = os.path.join(work, "sync_ondemand.json")
    BC.MARKET_STATUS_PATH = os.path.join(work, "market_sync.json")
    BC.CONTROL_PATH = os.path.join(work, "codal_control.json")
    BC.FTS_CONFIG_PATH = os.path.join(work, "fts_thresholds.json")
    BC.PRICE_BASIS_PATH = os.path.join(work, "price_basis.json")

    port = free_port()
    print("ISOLATED-PORT %d" % port, flush=True)
    print("ISOLATED-DB %s" % db, flush=True)

    import uvicorn
    import app as APP

    try:
        uvicorn.run(APP.app, host="127.0.0.1", port=port, log_level="warning")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
