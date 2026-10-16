#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اجرایِ یکِ گارد درِ شرایطِ CI: بیِ `market.db` درِ درخت.

`market.db` و `codal.db` درِ گیت نیستند، پس runner هیچ‌وقت آن‌ها را ندارد. چند
گاردِ مسیرِ اجرا نماد را ازِ همان بانکِ محلی می‌گیرند، بنابراین درِ CI با
`NOT_ORDERABLE:resolution` (و بعد `KeyError`) می‌سوندند در حالی که محلی سبز
بودند — یعنی قرمزِ CI بی‌دلیل و سبزِ محلی بی‌معنی.

این ابزار `bors_config.DB_PATH` را *پیشِ* import شدنِ ماژول‌هایِ هدف به یکِ
مسیرِ نبودِ فایل می‌چرخاند و گارد را مثلِ `python dev/x.py` اجرا می‌کند.

اجرا:  python tools/guard_ci_sim.py dev/easytrader_adapter_v1113.py
خروجی: exit code خودِ گارد (۰ = درِ شرایطِ CI هم سبز)
"""
import os
import runpy
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("BORS_CODAL_OFFLINE", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import bors_config  # noqa: E402

MISSING = os.path.join(ROOT, "_audit", "ci_sim_no_market_db.db")
if os.path.exists(MISSING):
    print("REMOVE FIRST: " + MISSING + " (the simulation needs the path absent)")
    sys.exit(2)
bors_config.DB_PATH = MISSING

target = sys.argv[1] if len(sys.argv) > 1 else "dev/run_all_tests.py"
print("simulated CI: DB_PATH =", bors_config.DB_PATH)
sys.argv = [target] + sys.argv[2:]
runpy.run_path(target, run_name="__main__")
