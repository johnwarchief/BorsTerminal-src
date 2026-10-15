#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اثباتِ ایستا: ماژول‌هایِ اجرا/ربات داخلِ PYZِ بیلدِ onedir

بخشی از زنجیرۀ راستی‌آزماییِ مأموریتِ سرخطی/EasyTrader/ربات. مسیرها ازِ ریشۀ ریپو حساب می‌شوند، نه ازِ یکِ ماشینِ خاص.
"""
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sys
from PyInstaller.archive.readers import CArchiveReader

EXE = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate", "BorsTerminal_Ultimate.exe")
WANT = ["api.bot", "api.execution", "execution_contract", "execution_service",
        "execution_ledger", "execution_easytrader", "execution_mock",
        "bot_signals", "paper_trading", "trade_sim", "backtest_engine",
        "api.funnel", "funnel_engine", "fts_engine", "mstat_engine"]

ca = CArchiveReader(EXE)
top = list(ca.toc)
pyz_name = next((n for n in top if n.startswith("PYZ")), None)
print("CArchive entries: %d, embedded PYZ: %s" % (len(top), pyz_name))
sub = ca.open_embedded_archive(pyz_name)
names = set(getattr(sub, "toc", {}) or {})
print("PYZ modules: %d" % len(names))
missing = [m for m in WANT if m not in names]
for m in WANT:
    print(("  OK   " if m in names else "  MISS ") + m)
extra = sorted(n for n in names if n.startswith(("api.", "execution", "bot_", "paper_", "trade_", "funnel", "backtest")))
print("collected %s-modules: %d" % ("execution/bot/funnel", len(extra)))
print("sample:", extra[:14])
sys.exit(1 if missing else 0)
